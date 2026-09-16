#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
RESULTS="$ROOT/results/full"
APK="$ROOT/test-clean.apk"
PKG="com.estrongs.android.pop"
MAIN="com.estrongs.android.pop/.view.FileExplorerActivity"
mkdir -p "$RESULTS"

echo "android_release=$(adb shell getprop ro.build.version.release | tr -d '\r')" | tee "$RESULTS/runtime-info.txt"
echo "android_sdk=$(adb shell getprop ro.build.version.sdk | tr -d '\r')" | tee -a "$RESULTS/runtime-info.txt"

adb install -r -g "$APK" | tee "$RESULTS/install.txt"
for perm in \
  android.permission.READ_EXTERNAL_STORAGE \
  android.permission.WRITE_EXTERNAL_STORAGE \
  android.permission.READ_PHONE_STATE \
  android.permission.ACCESS_FINE_LOCATION \
  android.permission.ACCESS_COARSE_LOCATION \
  android.permission.CAMERA; do
  adb shell pm grant "$PKG" "$perm" >/dev/null 2>&1 || true
done
adb shell appops set "$PKG" MANAGE_EXTERNAL_STORAGE allow >/dev/null 2>&1 || true
adb shell appops set "$PKG" READ_DEVICE_IDENTIFIERS allow >/dev/null 2>&1 || true

# Synthetic local files. Any exfiltration of these exact canaries over cleartext will be detected.
LOCAL_CANARY="ES_LOCAL_CANARY_62C4F9B1"
adb shell 'mkdir -p /sdcard/Download /sdcard/Documents /sdcard/DCIM/Camera /sdcard/Android/data' || true
adb shell "printf '%s\n' '$LOCAL_CANARY document' > /sdcard/Documents/privacy_test.txt" || true
adb shell "printf '%s\n' '$LOCAL_CANARY hidden' > /sdcard/Download/.es_hidden_test" || true
adb shell "printf '%s\n' '$LOCAL_CANARY photo' > /sdcard/DCIM/Camera/privacy_test.jpg" || true

# Build small ZIP/TXT artifacts locally and push them so archive/text entry points can be exercised.
python3 - <<'PY'
from pathlib import Path
import zipfile
p=Path('/tmp/es-regression')
p.mkdir(exist_ok=True)
(p/'inside.txt').write_text('ES_ARCHIVE_CANARY_C11A7E22\n', encoding='utf-8')
with zipfile.ZipFile(p/'sample.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.write(p/'inside.txt','inside.txt')
PY
adb push /tmp/es-regression/sample.zip /sdcard/Download/sample.zip >/dev/null

adb logcat -c || true
adb shell dumpsys appops "$PKG" > "$RESULTS/appops-before.txt" || true
adb shell dumpsys package "$PKG" > "$RESULTS/package.txt" || true

# Record active sockets once per second while the test is running.
(
  for i in $(seq 1 150); do
    echo "===== $(date -u +%FT%TZ) ====="
    adb shell 'cat /proc/net/tcp 2>/dev/null; cat /proc/net/tcp6 2>/dev/null; cat /proc/net/udp 2>/dev/null; cat /proc/net/udp6 2>/dev/null' || true
    sleep 1
  done
) > "$RESULTS/socket-snapshots.txt" 2>&1 &
SOCKET_PID=$!

launch_uri() {
  local label="$1" uri="$2"
  echo "===== $label : $uri =====" | tee -a "$RESULTS/deep-links.txt"
  adb shell am force-stop "$PKG" || true
  adb shell am start -W -n "$MAIN" -a android.intent.action.VIEW -d "$uri" \
    >> "$RESULTS/deep-links.txt" 2>&1 || true
  sleep 8
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  adb pull /sdcard/window.xml "$RESULTS/ui-${label}.xml" >/dev/null 2>&1 || true
  adb exec-out screencap -p > "$RESULTS/ui-${label}.png" 2>/dev/null || true
}

# Cold launch first: startup analytics / background jobs.
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > "$RESULTS/launch.txt" 2>&1 || true
sleep 18

# ES recognizes these virtual/root URI schemes internally. They cover core advanced features without
# needing fragile screen coordinates.
launch_uri "app-manager" "app://"
launch_uri "storage-analysis" "du:///sdcard/"
launch_uri "remote-manager" "remote://"
launch_uri "archive" "file:///sdcard/Download/sample.zip"
launch_uri "text" "file:///sdcard/Documents/privacy_test.txt"

# Network clients against disposable services on the GitHub runner host (10.0.2.2 from emulator).
launch_uri "ftp" "ftp://esuser:espass@10.0.2.2:2121/"
launch_uri "sftp" "sftp://esuser:espass@10.0.2.2:2222/"
launch_uri "webdav" "webdav://10.0.2.2:8080/"
launch_uri "smb" "smb://esuser:espass@10.0.2.2/SHARE/"

# Open cloud/network roots. This verifies entry points and records any OAuth/provider traffic, but
# deliberately does not log in because no user credentials are used in the disposable emulator.
launch_uri "cloud-root" "net://"
launch_uri "lan-root" "smb://"
launch_uri "ftp-root" "ftp://"

# Broad regression / crash sweep. Restrict to target package and avoid app-switch/system-key noise.
adb shell monkey -p "$PKG" --pct-syskeys 0 --pct-appswitch 0 --pct-anyevent 0 \
  --throttle 80 -v 1800 > "$RESULTS/monkey-1800.txt" 2>&1 || true
sleep 15

adb logcat -d -v threadtime > "$RESULTS/logcat.txt" || true
adb shell dumpsys appops "$PKG" > "$RESULTS/appops-after.txt" || true
adb shell dumpsys netstats detail > "$RESULTS/netstats.txt" || true
adb shell dumpsys activity processes > "$RESULTS/processes.txt" || true

kill "$SOCKET_PID" >/dev/null 2>&1 || true
wait "$SOCKET_PID" >/dev/null 2>&1 || true
adb shell am force-stop "$PKG" || true

# Fast crash summary.
{
  echo "=== Fatal/ANR markers ==="
  grep -E 'FATAL EXCEPTION|ANR in com\.estrongs\.android\.pop|Process: com\.estrongs\.android\.pop' "$RESULTS/logcat.txt" || true
  echo "=== Security/permission markers ==="
  grep -Ei 'SecurityException|Permission Denial|denied.*com\.estrongs\.android\.pop' "$RESULTS/logcat.txt" | head -200 || true
} > "$RESULTS/crash-and-permission-summary.txt"

# Package-level appops changes are useful to see whether location/device-ID APIs were actually used.
diff -u "$RESULTS/appops-before.txt" "$RESULTS/appops-after.txt" > "$RESULTS/appops-diff.txt" || true

echo "comprehensive runtime regression completed"
