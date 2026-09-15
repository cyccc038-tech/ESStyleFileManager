#!/usr/bin/env bash
set -euo pipefail

VARIANT="${1:?variant required: original|clean}"
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
RESULTS="$ROOT/results/$VARIANT"
mkdir -p "$RESULTS"

SOURCE_URL="https://apps.apk4free.net/es-file-explorer/ES_File_Explorer-Premium-v4.4.3.7_build_10353-Mod.apk"
EXPECTED_SOURCE_SHA256="cdca718efd9966697940b9013b57c20057e6c8b1f86b73708bdefa487b684922"
PKG="com.estrongs.android.pop"
SOURCE_APK="$RESULTS/source.apk"
TEST_APK="$RESULTS/test.apk"

printf 'variant=%s\n' "$VARIANT" | tee "$RESULTS/test-info.txt"
printf 'source_url=%s\n' "$SOURCE_URL" | tee -a "$RESULTS/test-info.txt"

curl -fL --retry 4 --retry-all-errors --connect-timeout 30 \
  "$SOURCE_URL" -o "$SOURCE_APK"
ACTUAL_SHA="$(sha256sum "$SOURCE_APK" | awk '{print $1}')"
printf 'source_sha256=%s\n' "$ACTUAL_SHA" | tee -a "$RESULTS/test-info.txt"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SOURCE_SHA256" ]]; then
  echo "ERROR: public Balatan file does not match the user's uploaded APK." | tee -a "$RESULTS/test-info.txt"
  exit 41
fi

if [[ "$VARIANT" == "clean" ]]; then
  python3 "$ROOT/security-test/privacy_patch_apk.py" \
    "$SOURCE_APK" "$RESULTS/patched-unsigned.apk" | tee "$RESULTS/patch-log.txt"

  BUILD_TOOLS="$(find "${ANDROID_HOME:-$ANDROID_SDK_ROOT}/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
  "$BUILD_TOOLS/zipalign" -f -p 4 "$RESULTS/patched-unsigned.apk" "$RESULTS/patched-aligned.apk"

  keytool -genkeypair -noprompt \
    -keystore "$RESULTS/test.keystore" -storepass changeit -keypass changeit \
    -alias esprivacytest -keyalg RSA -keysize 2048 -validity 3650 \
    -dname "CN=ES Privacy Dynamic Test, O=OpenAI Test Build, C=US"

  "$BUILD_TOOLS/apksigner" sign \
    --ks "$RESULTS/test.keystore" --ks-pass pass:changeit --key-pass pass:changeit \
    --out "$TEST_APK" "$RESULTS/patched-aligned.apk"
  "$BUILD_TOOLS/apksigner" verify --verbose --print-certs "$TEST_APK" \
    | tee "$RESULTS/apksigner-verify.txt"
else
  cp "$SOURCE_APK" "$TEST_APK"
fi

sha256sum "$TEST_APK" | tee "$RESULTS/test-apk-sha256.txt"

adb wait-for-device
adb shell getprop ro.build.version.release | tr -d '\r' | sed 's/^/android_release=/' | tee -a "$RESULTS/test-info.txt"
adb shell getprop ro.build.version.sdk | tr -d '\r' | sed 's/^/android_sdk=/' | tee -a "$RESULTS/test-info.txt"

adb install -r -g "$TEST_APK" | tee "$RESULTS/install.txt"

# Grant a deliberately broad permission set in the disposable emulator so the test observes the
# maximum data exposure possible from the app, rather than giving a false sense of safety because a
# permission happened to be denied.
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

# Synthetic canary data. If any of these literal values appear in cleartext traffic, flag them.
CANARY="ES_PRIVACY_CANARY_DO_NOT_UPLOAD_9F4C2D71"
adb shell 'mkdir -p /sdcard/Download /sdcard/Documents /sdcard/DCIM/Camera' || true
adb shell "printf '%s\\n' '$CANARY private document' > /sdcard/Documents/private_canary.txt" || true
adb shell "printf '%s\\n' '$CANARY fake photo payload' > /sdcard/DCIM/Camera/private_canary.jpg" || true
adb shell "printf '%s\\n' '$CANARY download payload' > /sdcard/Download/private_canary.dat" || true
printf 'canary=%s\n' "$CANARY" | tee -a "$RESULTS/test-info.txt"

# Set a synthetic emulator location; never use the user's real location for this test.
adb emu geo fix -73.9857 40.7484 >/dev/null 2>&1 || true

adb logcat -c || true

# Snapshot package state before launch.
adb shell dumpsys package "$PKG" > "$RESULTS/dumpsys-package.txt" || true
adb shell dumpsys appops "$PKG" > "$RESULTS/dumpsys-appops-before.txt" || true

# Sample kernel socket tables while the app is active. The PCAP is captured by the emulator itself;
# these snapshots provide a second independent record of outbound socket activity.
(
  for i in $(seq 1 100); do
    echo "===== $(date -u +%FT%TZ) ====="
    adb shell 'cat /proc/net/tcp 2>/dev/null; cat /proc/net/tcp6 2>/dev/null; cat /proc/net/udp 2>/dev/null; cat /proc/net/udp6 2>/dev/null' || true
    sleep 1
  done
) > "$RESULTS/socket-snapshots.txt" 2>&1 &
SOCKET_SAMPLER_PID=$!

# 1) Cold launch and idle period: catches startup analytics and background telemetry.
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 \
  > "$RESULTS/launch-monkey.txt" 2>&1 || true
sleep 25

# 2) Exercise a broad set of in-app screens/actions without leaving the target package.
# The emulator contains only synthetic files and no user accounts.
adb shell monkey -p "$PKG" \
  --pct-syskeys 0 --pct-appswitch 0 --pct-anyevent 0 \
  --throttle 120 -v 500 > "$RESULTS/exercise-monkey.txt" 2>&1 || true
sleep 25

# 3) Background/foreground cycle, which commonly triggers session/analytics uploads.
adb shell input keyevent KEYCODE_HOME || true
sleep 15
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 \
  >> "$RESULTS/launch-monkey.txt" 2>&1 || true
sleep 20

adb logcat -d -v threadtime > "$RESULTS/logcat.txt" || true
adb shell dumpsys netstats detail > "$RESULTS/dumpsys-netstats.txt" || true
adb shell dumpsys appops "$PKG" > "$RESULTS/dumpsys-appops-after.txt" || true
adb shell dumpsys activity processes > "$RESULTS/dumpsys-processes.txt" || true

kill "$SOCKET_SAMPLER_PID" >/dev/null 2>&1 || true
wait "$SOCKET_SAMPLER_PID" >/dev/null 2>&1 || true

adb shell am force-stop "$PKG" || true

# Do not retain the downloaded/test APK in workflow artifacts; only hashes, logs and packet capture
# are uploaded. This keeps the public repository/workflow from redistributing the proprietary APK.
rm -f "$SOURCE_APK" "$TEST_APK" "$RESULTS/patched-unsigned.apk" "$RESULTS/patched-aligned.apk" "$RESULTS/test.keystore"

echo "runtime test completed: $VARIANT"
