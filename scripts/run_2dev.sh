#!/usr/bin/env bash
# Temporary 2-device parallel run (5554 + 5556, both build 3252).
# Shard A = heavy navigation/home/auth files + device-free unit & API tests.
# Shard B = everything else (portfolio/investments/settings family + the new
# scenario/value tests) via tests/ with --ignore of shard A's files.
set -o pipefail
cd "$(dirname "$0")/.." || exit 1

PY=./venv/bin/python
TIMEOUT="${TIMEOUT:-120}"
LOGDIR=/tmp/raiz_2dev
mkdir -p "$LOGDIR"

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

ADB="$HOME/Library/Android/sdk/platform-tools/adb"
for d in emulator-5554 emulator-5556; do
  "$ADB" -s "$d" forward --remove-all >/dev/null 2>&1
  "$ADB" -s "$d" shell am force-stop io.appium.uiautomator2.server >/dev/null 2>&1
  "$ADB" -s "$d" shell am force-stop io.appium.uiautomator2.server.test >/dev/null 2>&1
  echo "cleaned $d"
done

echo "== Launching 2 shards (timeout=${TIMEOUT}s) =="
(
  ANDROID_UDID=emulator-5554 APPIUM_HOST="http://127.0.0.1:4723" \
  ANDROID_SYSTEM_PORT=8201 ANDROID_MJPEG_PORT=7811 \
    $CAFFEINATE "$PY" -m pytest "${A_FILES[@]}" -k "$K_SAFE" \
      -o addopts="" -p no:cacheprovider -q --timeout="$TIMEOUT" \
      --timeout_method=signal --tb=line > "$LOGDIR/run_5554.log" 2>&1
  echo "EXIT=$?" >> "$LOGDIR/run_5554.log"
) &
P1=$!
(
  ANDROID_UDID=emulator-5556 APPIUM_HOST="http://127.0.0.1:4724" \
  ANDROID_SYSTEM_PORT=8202 ANDROID_MJPEG_PORT=7812 \
    $CAFFEINATE "$PY" -m pytest tests/ "${B_IGNORES[@]}" -k "$K_SAFE" \
      -o addopts="" -p no:cacheprovider -q --timeout="$TIMEOUT" \
      --timeout_method=signal --tb=line > "$LOGDIR/run_5556.log" 2>&1
  echo "EXIT=$?" >> "$LOGDIR/run_5556.log"
) &
P2=$!
wait $P1; wait $P2

echo ""
echo "===== SUMMARY ====="
for d in 5554 5556; do
  printf "  emulator-%s  %s\n" "$d" \
    "$(grep -E ' (passed|failed|error|skipped|xfailed)' "$LOGDIR/run_${d}.log" | tail -1)"
done
echo "ALL_DONE"
