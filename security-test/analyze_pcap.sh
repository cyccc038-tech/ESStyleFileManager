#!/usr/bin/env bash
set -euo pipefail

VARIANT="${1:?variant required}"
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
RESULTS="$ROOT/results/$VARIANT"
PCAP="$ROOT/results/${VARIANT}.pcap"

mkdir -p "$RESULTS"
if [[ ! -s "$PCAP" ]]; then
  echo "PCAP missing or empty: $PCAP" | tee "$RESULTS/pcap-error.txt"
  exit 2
fi

printf 'pcap_sha256=' > "$RESULTS/pcap-summary.txt"
sha256sum "$PCAP" | awk '{print $1}' >> "$RESULTS/pcap-summary.txt"
printf 'pcap_bytes=' >> "$RESULTS/pcap-summary.txt"
stat -c '%s' "$PCAP" >> "$RESULTS/pcap-summary.txt"

# DNS queries made by the emulator.
tshark -r "$PCAP" -Y 'dns.flags.response == 0 && dns.qry.name' \
  -T fields -e frame.time_epoch -e ip.src -e ip.dst -e dns.qry.name 2>/dev/null \
  > "$RESULTS/dns-queries.tsv" || true
cut -f4 "$RESULTS/dns-queries.tsv" | sed '/^$/d' | sort -fu > "$RESULTS/dns-domains.txt" || true

# TLS SNI provides destination hostname even when HTTPS payloads remain encrypted.
tshark -r "$PCAP" -Y 'tls.handshake.extensions_server_name' \
  -T fields -e frame.time_epoch -e ip.src -e ip.dst -e tls.handshake.extensions_server_name 2>/dev/null \
  > "$RESULTS/tls-sni.tsv" || true
cut -f4 "$RESULTS/tls-sni.tsv" | sed '/^$/d' | sort -fu > "$RESULTS/tls-sni-domains.txt" || true

# Any unencrypted HTTP requests are fully visible and especially important for this legacy app.
tshark -r "$PCAP" -Y 'http.request' \
  -T fields -e frame.time_epoch -e ip.dst -e http.request.method -e http.host -e http.request.uri 2>/dev/null \
  > "$RESULTS/http-requests.tsv" || true

# Destination endpoints and conversations.
tshark -r "$PCAP" -q -z endpoints,ip > "$RESULTS/ip-endpoints.txt" 2>/dev/null || true
tshark -r "$PCAP" -q -z conv,tcp > "$RESULTS/tcp-conversations.txt" 2>/dev/null || true

# Search both parsed hostnames and packet bytes for known tracking/advertising endpoints.
BLOCK_RE='stat\.doglobal\.net|errnewlog\.umeng\.com|errnewlogos\.umeng\.com|cnlogs\.umeng\.com|aspect-upush\.umeng\.com|utoken\.umeng\.com|ucc\.umeng\.com|astat\.bugly\.qcloud\.com|astat\.bugly\.cros\.wr\.pvp\.net|applog\.snssdk\.com|log\.snssdk\.com|rtapplog\.snssdk\.com|rtlog\.snssdk\.com|tobapplog\.ctobsnssdk\.com|toblog\.ctobsnssdk\.com|scc\.bytedance\.com|sf3-fe-tos\.pglstatp-toutiao\.com|cdn-tos-cn\.bytedance\.net|apps\.bytesfield\.com|apps\.bytesfield-b\.com|sf1-amtos-cdn\.bytesmanager\.com|open\.e\.kuaishou\.com|p[1-5]-lm\.adkwai\.com|stg-data\.ads\.heytapmobi\.com|adsfs\.heytapimage\.com|mdp-usertrace-cn\.heytapmobi\.com|api-audit\.heytapmobi\.com|adx-data\.yfanads\.com|api\.yfanads\.com|log\.yfanads\.com|tracker\.yfanads\.com|nsclick\.baidu\.com|loggw-exsdk\.alipay\.com'
cat "$RESULTS/dns-domains.txt" "$RESULTS/tls-sni-domains.txt" "$RESULTS/http-requests.tsv" 2>/dev/null \
  | grep -Eio "$BLOCK_RE" | sort -fu > "$RESULTS/blocked-host-hits.txt" || true

# Canary leakage is detectable if any synthetic filename/content is sent over cleartext protocols.
CANARY='ES_PRIVACY_CANARY_DO_NOT_UPLOAD_9F4C2D71'
if grep -aFq "$CANARY" "$PCAP"; then
  echo "CRITICAL: synthetic canary appeared in captured packet bytes" > "$RESULTS/canary-result.txt"
else
  echo "No synthetic canary found in cleartext packet bytes" > "$RESULTS/canary-result.txt"
fi

# Summarize counts for quick comparison.
{
  echo "variant=$VARIANT"
  echo "dns_unique=$(wc -l < "$RESULTS/dns-domains.txt" | tr -d ' ')"
  echo "tls_sni_unique=$(wc -l < "$RESULTS/tls-sni-domains.txt" | tr -d ' ')"
  echo "http_requests=$(wc -l < "$RESULTS/http-requests.tsv" | tr -d ' ')"
  echo "blocked_host_hits=$(wc -l < "$RESULTS/blocked-host-hits.txt" | tr -d ' ')"
  cat "$RESULTS/canary-result.txt"
  echo "--- blocked hosts observed ---"
  cat "$RESULTS/blocked-host-hits.txt"
} | tee -a "$RESULTS/pcap-summary.txt"
