#!/usr/bin/env bash
# 2-device parallel run (5554 + 5556). Shard A = heavy navigation/home/auth files
# + device-free unit & API tests. Shard B = everything else (portfolio/investments
# /settings + scenario/value tests) via tests/ with --ignore of shard A's files.
#
# Streams both shards LIVE to the terminal (prefixed [5554]/[5556]) AND to per-shard
# logs, and writes FRESH allure results so `allure serve` shows THIS run.
set -o pipefail
cd "$(dirname "$0")/.." || exit 1

PY=./venv/bin/python
TIMEOUT="${TIMEOUT:-120}"
LOGDIR=/tmp/raiz_2dev
mkdir -p "$LOGDIR"
ALLURE_DIR="${ALLURE_DIR:-reports/allure-results}"
ALLURE_REPORT="${ALLURE_REPORT:-reports/allure-report}"

CAFFEINATE="${CAFFEINATE-caffeinate -i}"
command -v caffeinate >/dev/null 2>&1 || CAFFEINATE=""

# Shared-account safety deselections (same set as the green baseline runs).
K_SAFE="not TestLogin and not TestLoginErrorHandling and not TestPasswordVisibility and not TestForgotPassword and not test_log_out_from_pin_screen and not TestSessionLifecycleE2E and not test_logout_prompts_and_cancel_keeps_session"

A_FILES=(
  tests/test_navigation_coverage.py tests/test_navigation.py tests/test_home.py
  tests/test_auth.py tests/test_settings.py tests/test_rewards.py
  tests/test_assertions_unit.py tests/test_deep_links_registry_unit.py
  tests/test_value_validation_api.py tests/test_auth_states_api.py
  tests/test_auth_account_states_api.py
)
B_IGNORES=()
for f in "${A_FILES[@]}"; do B_IGNORES+=(--ignore="$f"); done

# Fresh allure dir so `allure serve` reflects THIS run, not a stale one. Both shards
# write into the same dir concurrently — allure-pytest names each result file by UUID,
# so parallel writes don't collide.
rm -rf "$ALLURE_DIR" && mkdir -p "$ALLURE_DIR" reports

ADB="$HOME/Library/Android/sdk/platform-tools/adb"
for d in emulator-5554 emulator-5556; do
  "$ADB" -s "$d" forward --remove-all >/dev/null 2>&1
  "$ADB" -s "$d" shell am force-stop io.appium.uiautomator2.server >/dev/null 2>&1
  "$ADB" -s "$d" shell am force-stop io.appium.uiautomator2.server.test >/dev/null 2>&1
  echo "cleaned $d"
done

# One shard: run pytest unbuffered (-v so each test streams a line), prefix every
# line with the device tag, and tee to BOTH the terminal and the shard log. Uses
# --alluredir explicitly because -o addopts="" drops pytest.ini's default flags.
run_shard() {  # $1=udid $2=appium $3=sysport $4=mjpeg $5=logname ; rest=pytest targets
  local udid="$1" host="$2" sysp="$3" mjpeg="$4" name="$5"; shift 5
  ANDROID_UDID="$udid" APPIUM_HOST="$host" ANDROID_SYSTEM_PORT="$sysp" ANDROID_MJPEG_PORT="$mjpeg" \
  PYTHONUNBUFFERED=1 \
    $CAFFEINATE "$PY" -m pytest "$@" -k "$K_SAFE" \
      -o addopts="" -p no:cacheprovider -v --timeout="$TIMEOUT" \
      --timeout_method=signal --tb=short --alluredir="$ALLURE_DIR" 2>&1 \
    | sed -l "s/^/[$name] /" | tee "$LOGDIR/run_${name}.log"
  echo "EXIT=${PIPESTATUS[0]}" >> "$LOGDIR/run_${name}.log"
}

echo "== Launching 2 shards LIVE (timeout=${TIMEOUT}s) — output streams below =="
run_shard emulator-5554 "http://127.0.0.1:4723" 8201 7811 5554 "${A_FILES[@]}" &
P1=$!
run_shard emulator-5556 "http://127.0.0.1:4724" 8202 7812 5556 tests/ "${B_IGNORES[@]}" &
P2=$!
wait $P1; wait $P2

echo ""
echo "===== SUMMARY ====="
for d in 5554 5556; do
  printf "  emulator-%s  %s\n" "$d" \
    "$(grep -E ' (passed|failed|error|skipped|xfailed)' "$LOGDIR/run_${d}.log" | tail -1)"
done

# Environment + report so `allure serve` (or the generated report) shows this run.
build=$("$ADB" -s emulator-5554 shell dumpsys package com.acornsau.android.development 2>/dev/null | grep -m1 versionName | tr -d ' \r')
{ echo "Platform=android"; echo "AppBuild=${build:-unknown}"; echo "Devices=emulator-5554,emulator-5556"; echo "Run=2-device parallel"; } > "$ALLURE_DIR/environment.properties"
if command -v allure >/dev/null 2>&1; then
  allure generate --clean "$ALLURE_DIR" -o "$ALLURE_REPORT" >/dev/null 2>&1 \
    && echo "Allure report: ${ALLURE_REPORT}/index.html" || true
fi
echo "Fresh allure results: $ALLURE_DIR   →   allure serve $ALLURE_DIR"
echo "ALL_DONE"
