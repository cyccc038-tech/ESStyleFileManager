#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
RESULTS="$ROOT/results/full"
PCAP="$ROOT/results/full.pcap"
mkdir -p "$RESULTS"

if [[ -s "$PCAP" ]]; then
  tshark -r "$PCAP" -Y 'dns.flags.response == 0 && dns.qry.name' -T fields \
    -e frame.time_epoch -e ip.src -e ip.dst -e dns.qry.name 2>/dev/null > "$RESULTS/dns.tsv" || true
  cut -f4 "$RESULTS/dns.tsv" | sed '/^$/d' | sort -fu > "$RESULTS/dns-domains.txt" || true

  tshark -r "$PCAP" -Y 'tls.handshake.extensions_server_name' -T fields \
    -e frame.time_epoch -e ip.dst -e tls.handshake.extensions_server_name 2>/dev/null > "$RESULTS/tls-sni.tsv" || true
  cut -f3 "$RESULTS/tls-sni.tsv" | sed '/^$/d' | sort -fu > "$RESULTS/tls-sni-domains.txt" || true

  tshark -r "$PCAP" -Y 'http.request' -T fields \
    -e frame.time_epoch -e ip.dst -e tcp.dstport -e http.request.method -e http.host -e http.request.uri 2>/dev/null \
    > "$RESULTS/http-requests.tsv" || true

  tshark -r "$PCAP" -Y 'ip.addr == 10.0.2.2 && tcp' -T fields \
    -e frame.time_epoch -e ip.src -e tcp.srcport -e ip.dst -e tcp.dstport -e tcp.flags.syn -e tcp.flags.ack 2>/dev/null \
    > "$RESULTS/host-service-tcp.tsv" || true

  tshark -r "$PCAP" -q -z conv,tcp > "$RESULTS/tcp-conversations.txt" 2>/dev/null || true
  tshark -r "$PCAP" -q -z endpoints,ip > "$RESULTS/ip-endpoints.txt" 2>/dev/null || true

  for canary in ES_LOCAL_CANARY_62C4F9B1 ES_REMOTE_CANARY_7A9C41D3 ES_ARCHIVE_CANARY_C11A7E22; do
    if grep -aFq "$canary" "$PCAP"; then
      echo "$canary FOUND_IN_PACKET_BYTES"
    else
      echo "$canary not_found_in_packet_bytes"
    fi
  done > "$RESULTS/canary-results.txt"
fi

BLOCK_RE='stat\.doglobal\.net|umeng\.com|bugly\.qcloud\.com|snssdk\.com|ctobsnssdk\.com|bytedance\.com|pglstatp-toutiao\.com|bytesfield(-b)?\.com|bytesmanager\.com|kuaishou\.com|adkwai\.com|heytapmobi\.com|heytapimage\.com|yfanads\.com|nsclick\.baidu\.com|loggw-exsdk\.alipay\.com'
cat "$RESULTS/dns-domains.txt" "$RESULTS/tls-sni-domains.txt" "$RESULTS/http-requests.tsv" 2>/dev/null \
  | grep -Eio "$BLOCK_RE" | sort -fu > "$RESULTS/telemetry-network-hits.txt" || true

# Copy local protocol service evidence produced on the runner host.
mkdir -p "$RESULTS/protocol-server-logs"
cp -a /tmp/es-protocol-logs/. "$RESULTS/protocol-server-logs/" 2>/dev/null || true
ss -lntp > "$RESULTS/listening-ports-after.txt" 2>&1 || true

python3 - "$RESULTS" <<'PY'
from pathlib import Path
import re, sys
r=Path(sys.argv[1])
def text(name):
    p=r/name
    return p.read_text(errors='ignore') if p.exists() else ''
def lines(name): return [x for x in text(name).splitlines() if x.strip()]

dns=lines('dns-domains.txt'); sni=lines('tls-sni-domains.txt'); http=lines('http-requests.tsv')
tele=lines('telemetry-network-hits.txt'); canary=lines('canary-results.txt')
crash=text('crash-and-permission-summary.txt')
appops=text('appops-diff.txt')
hosttcp=text('host-service-tcp.tsv')

ports={'FTP':2121,'SFTP':2222,'WebDAV':8080,'SMB':445}
port_hits={name: bool(re.search(rf'\t{port}(\t|$)', hosttcp, re.M)) for name,port in ports.items()}

server_evidence={}
for name in ['ftp','sftp','webdav','smb']:
    p=r/'protocol-server-logs'/f'{name}.log'
    t=p.read_text(errors='ignore') if p.exists() else ''
    server_evidence[name]=bool(t.strip()) and any(k in t.lower() for k in ['connect','login','session','request','authenticated','open','list','sftp listening','serving'])

fatal=bool(re.search(r'FATAL EXCEPTION|ANR in com\.estrongs\.android\.pop',crash,re.I))
loc_used=bool(re.search(r'fine_location|coarse_location|location',appops,re.I))
id_used=bool(re.search(r'read_device_identifiers|phone|imei|device',appops,re.I))

out=[]
out += ['# ES 4.4.3.7 云端综合动态审计','']
out += [f'- DNS 唯一域名：{len(dns)}',f'- TLS SNI 唯一域名：{len(sni)}',f'- 明文 HTTP 请求：{len(http)}',f'- 已知识别的遥测/广告网络命中：{len(tele)}',f'- ES FATAL/ANR：{"发现" if fatal else "未发现"}','']
out += ['## 本地协议专项']
for name in ['FTP','SFTP','WebDAV','SMB']:
    ev=server_evidence[name.lower()]
    out.append(f'- {name}: TCP 目标端口={"命中" if port_hits[name] else "未命中"}；服务端日志={"有活动" if ev else "未确认活动"}')
out += ['','## Canary 泄露检查']
out += [f'- {x}' for x in canary] or ['- 无结果']
out += ['','## 权限/AppOps 观察',f'- 位置类 AppOps 是否出现变化线索：{"是" if loc_used else "未观察到"}',f'- 设备标识/电话类 AppOps 是否出现变化线索：{"是" if id_used else "未观察到"}']
out += ['','## 网络域名']
out += [f'- DNS: {x}' for x in dns[:100]]
out += [f'- TLS SNI: {x}' for x in sni[:100]]
out += ['','## 已知遥测命中']
out += [f'- {x}' for x in tele] or ['- 未发现']
out += ['','## 解释限制','- 云端测试使用 Android 模拟器和合成文件，不包含用户真实账号/照片/文档。','- Google Drive、OneDrive、百度网盘等 OAuth 流程只测试入口和未登录网络行为；没有账号凭据，因此不能把“未完成登录”误写成完整云盘功能回归。','- FTP/HTTP WebDAV 本身允许明文协议；是否出现明文连接不等于隐私泄露，关键是目标是否由用户配置、是否夹带无关遥测。']
(r/'COMPREHENSIVE_AUDIT.md').write_text('\n'.join(out)+'\n',encoding='utf-8')
PY
