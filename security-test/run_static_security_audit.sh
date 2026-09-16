#!/usr/bin/env bash
set -euo pipefail

APK="${1:?apk path required}"
OUT="${2:?output directory required}"
mkdir -p "$OUT"

BUILD_TOOLS="$(find "$ANDROID_HOME/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
AAPT="$BUILD_TOOLS/aapt"

"$AAPT" dump badging "$APK" > "$OUT/aapt-badging.txt" || true
"$AAPT" dump permissions "$APK" > "$OUT/permissions.txt" || true
"$AAPT" dump xmltree "$APK" AndroidManifest.xml > "$OUT/manifest-tree.txt" || true

# Extract printable DEX strings without uploading proprietary decompiled source.
mkdir -p "$OUT/dex"
for n in '' 2 3 4 5 6 7 8; do
  unzip -p "$APK" "classes${n}.dex" > "$OUT/dex/classes${n}.dex"
  strings -a -n 5 "$OUT/dex/classes${n}.dex" > "$OUT/dex/classes${n}.strings"
done
cat "$OUT"/dex/*.strings > "$OUT/all-dex-strings.txt"

# URLs and host-like strings. This is intentionally broad; the report later classifies known service
# providers separately from telemetry/advertising endpoints.
grep -Eio 'https?://[^[:space:]"<>]+' "$OUT/all-dex-strings.txt" | sort -fu > "$OUT/http-urls.txt" || true
grep -Eio '([a-z0-9-]+\.)+[a-z]{2,}(:[0-9]+)?' "$OUT/all-dex-strings.txt" | tr '[:upper:]' '[:lower:]' | sort -fu > "$OUT/host-like-strings.txt" || true

cat > "$OUT/known-telemetry-regex.txt" <<'EOF'
stat\.doglobal\.net
umeng\.com
bugly\.qcloud\.com
snssdk\.com
ctobsnssdk\.com
bytedance\.com
pglstatp-toutiao\.com
bytesfield(-b)?\.com
bytesmanager\.com
kuaishou\.com
adkwai\.com
heytapmobi\.com
heytapimage\.com
yfanads\.com
nsclick\.baidu\.com
loggw-exsdk\.alipay\.com
EOF
TELEMETRY_RE="$(paste -sd'|' "$OUT/known-telemetry-regex.txt")"
grep -Ei "$TELEMETRY_RE" "$OUT/host-like-strings.txt" > "$OUT/telemetry-hosts-still-present.txt" || true

# Functional service endpoints we do not want to delete merely because they are networked.
grep -Ei 'google|googleapis|microsoft|live\.com|onedrive|baidu|pcs|dropbox|box\.com|amazon|webdav|oauth|smb|ftp|sftp' \
  "$OUT/http-urls.txt" "$OUT/host-like-strings.txt" > "$OUT/functional-network-endpoints.txt" || true

# High-risk data APIs and accessibility implementation markers. Only symbol/call-name evidence is
# emitted, not proprietary source bodies.
for token in \
  'TelephonyManager' 'getDeviceId' 'getImei' 'getSubscriberId' 'getSimSerialNumber' \
  'Settings$Secure' 'ANDROID_ID' 'AdvertisingIdClient' 'getAdvertisingIdInfo' \
  'LocationManager' 'getLastKnownLocation' 'requestLocationUpdates' \
  'WifiInfo' 'getSSID' 'getBSSID' 'getMacAddress' \
  'AutoAuthService' 'AuthServiceHelper' 'AccessibilityService' \
  'findAccessibilityNodeInfosByText' 'performAction' 'performGlobalAction' \
  'takePersistableUriPermission' 'DocumentsContract'; do
  count="$(grep -F "$token" "$OUT/all-dex-strings.txt" | wc -l | tr -d ' ')"
  printf '%s\t%s\n' "$token" "$count"
done > "$OUT/high-risk-api-symbol-counts.tsv"

# Cleartext-related static evidence.
{
  echo '=== manifest cleartext markers ==='
  grep -Ei 'usesCleartextTraffic|networkSecurityConfig' "$OUT/manifest-tree.txt" || true
  echo '=== cleartext URL samples ==='
  grep -Ei '^http://' "$OUT/http-urls.txt" | head -200 || true
} > "$OUT/cleartext-static.txt"

# Accessibility component and its manifest declaration.
grep -n -B4 -A16 -E 'AutoAuthService|BIND_ACCESSIBILITY_SERVICE|accessibilityservice' \
  "$OUT/manifest-tree.txt" > "$OUT/accessibility-manifest.txt" || true

# Build a concise Markdown report from the machine-readable evidence.
python3 - "$OUT" <<'PY'
from pathlib import Path
import re, sys
out=Path(sys.argv[1])
def lines(name):
    p=out/name
    return p.read_text(errors='ignore').splitlines() if p.exists() else []
perms=lines('permissions.txt')
hosts=lines('host-like-strings.txt')
tele=lines('telemetry-hosts-still-present.txt')
urls=lines('http-urls.txt')
api=lines('high-risk-api-symbol-counts.tsv')
clear=[u for u in urls if u.lower().startswith('http://')]
critical_perms=['MANAGE_EXTERNAL_STORAGE','READ_PHONE_STATE','ACCESS_FINE_LOCATION','ACCESS_BACKGROUND_LOCATION','QUERY_ALL_PACKAGES','SYSTEM_ALERT_WINDOW','INTERNET']
found={p: any(p in x for x in perms) for p in critical_perms}
report=[]
report += ['# ES 4.4.3.7 静态安全审计','']
report += [f'- 权限声明总行数：{len(perms)}', f'- DEX 中域名样式字符串：{len(hosts)}', f'- HTTP/HTTPS URL 字符串：{len(urls)}', f'- 明文 HTTP URL 字符串：{len(clear)}', f'- 已知遥测/广告域残留匹配：{len(tele)}','']
report += ['## 关键权限']
for p,v in found.items(): report.append(f'- {p}: {"存在" if v else "未发现"}')
report += ['','## 高风险 API / Android-data 相关符号']
for x in api: report.append(f'- {x.replace(chr(9), ": ")}')
report += ['','## 已知遥测域残留']
report += [f'- {x}' for x in tele[:100]] or ['- 未发现已知清单中的有效域名字符串']
report += ['','## 结论说明','- 仅凭字符串存在不能证明运行时一定调用；动态 AppOps、PCAP 和服务端日志用于交叉验证。','- INTERNET/QUERY_ALL_PACKAGES/SAF/无障碍相关能力与 ES 的网络功能、应用管理、Android/data 兼容存在功能关系，不应仅因“权限高”而直接删除。','- 全局关闭 cleartext 可能破坏 FTP、HTTP WebDAV 及老旧局域网设备兼容，因此必须结合动态专项测试决定。']
(out/'STATIC_AUDIT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
PY

# Do not retain raw DEX copies in the artifact.
rm -rf "$OUT/dex" "$OUT/all-dex-strings.txt"
