#!/usr/bin/env bash
#
# run_queue.sh — DYNAMIC work-queue run across all connected emulators using
# pytest-xdist. Unlike run_parallel.sh (static: whole files pre-assigned to a
# device), this puts every test in ONE shared queue and each worker pulls the
# next test the moment it frees up — so all devices finish together instead of
# one shard being the long pole.
#
# HOW: `pytest -n <devices> --dist loadscope`. xdist spawns one worker process
# per device; conftest._xdist_device() pins gw0->5554, gw1->5556, gw2->5558 (each
# its own Appium server + systemPort). The session-scoped driver means each worker
# logs in ONCE and reuses that session for every test it pulls.
#
# WHY loadscope (not load): with per-test `--dist load`, the dynamic queue can let
# all 3 workers render the same HEAVY screen (rewards/settings/performance) at the
# SAME moment, spiking RAM past this Mac's ~3-session ceiling -> fixture timeouts
# (observed: whole test_rewards file erroring). `loadscope` keeps a whole module on
# one worker, so only one device renders a given heavy screen at a time (like the
# static shards, which run green) while STILL load-balancing files dynamically
# across free workers. Override with DIST=load if you have RAM headroom.
#
# PREREQUISITES: one Appium server per device (4723/4724/4725), all devices on the
# same build and logged in (PIN 0000). `-n` must equal the device count.
#
# USAGE:  ./scripts/run_queue.sh            # all tests, dynamic queue
#         TIMEOUT=90 ./scripts/run_queue.sh
set -o pipefail
cd "$(dirname "$0")/.." || exit 1

PY=./venv/bin/python
# Keep the Mac awake for the whole run: a maintenance/idle sleep mid-run freezes
# the emulators + Appium and crashes whatever test is executing. `caffeinate -i`
# holds an idle-sleep assertion until pytest exits. No-ops if caffeinate is absent
# (non-macOS); override with CAFFEINATE="" to disable. NOTE: still sleeps if the
# LID is closed — keep it open (or on AC + external display) for unattended runs.
CAFFEINATE="${CAFFEINATE-caffeinate -i}"
command -v caffeinate >/dev/null 2>&1 || CAFFEINATE=""
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
command -v adb >/dev/null 2>&1 && ADB="adb"
TIMEOUT="${TIMEOUT:-120}"
ALLURE_DIR="${ALLURE_DIR:-reports/allure-results}"
ALLURE_REPORT="${ALLURE_REPORT:-reports/allure-report}"
LOG="${LOG:-/tmp/raiz_queue.log}"
APP="${ANDROID_APP_PACKAGE:-com.acornsau.android.development}"

# Devices + Appium ports — MUST match the order of conftest._DEFAULT_DEVICE_MAP.
DEVICES=("emulator-5554:4723" "emulator-5556:4724" "emulator-5558:4725")
NPROC="${NPROC:-${#DEVICES[@]}}"

# Session-ending / OTP-reset tests deselected GLOBALLY: under a dynamic queue ANY
# worker could otherwise pull a logout/reset and invalidate the other workers'
# shared-account sessions.
K_SAFE="not TestLogin and not TestLoginErrorHandling and not TestPasswordVisibility and not TestForgotPassword and not test_log_out_from_pin_screen and not TestSessionLifecycleE2E and not test_logout_prompts_and_cancel_keeps_session"

TARGET="${*:-tests/}"

echo "== Preflight =="
fail=0
for d in "${DEVICES[@]}"; do
  udid="${d%%:*}"; port="${d##*:}"
  printf "  %-16s appium:%s " "$udid" "$port"
  if ! curl -s -m2 "http://127.0.0.1:${port}/status" >/dev/null 2>&1; then echo "[Appium DOWN -> appium --relaxed-security -p ${port}]"; fail=1; continue; fi
  if ! "$ADB" devices | grep -q "^${udid}[[:space:]]\+device"; then echo "[device NOT connected]"; fail=1; continue; fi
  "$ADB" -s "$udid" forward --remove-all >/dev/null 2>&1
  "$ADB" -s "$udid" shell am force-stop io.appium.uiautomator2.server >/dev/null 2>&1
  "$ADB" -s "$udid" shell am force-stop io.appium.uiautomator2.server.test >/dev/null 2>&1
  echo "[ok, cleaned]"
done
[ "$fail" -ne 0 ] && { echo "Preflight failed — fix the above and retry."; exit 2; }

echo "== Fresh allure dir =="
rm -rf "$ALLURE_DIR" && mkdir -p "$ALLURE_DIR" reports

DIST="${DIST:-loadscope}"
echo "== Queue run: pytest -n ${NPROC} --dist ${DIST}  (timeout=${TIMEOUT}s) =="
echo "   target: ${TARGET}"
: > "$LOG"
$CAFFEINATE "$PY" -m pytest $TARGET -k "$K_SAFE" \
  -n "$NPROC" --dist "$DIST" \
  -o addopts="" -p no:cacheprovider \
  --alluredir="$ALLURE_DIR" \
  --timeout="$TIMEOUT" --timeout_method=signal \
  -q 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}

echo ""
echo "===== SUMMARY ====="
grep -E " (passed|failed|error|skipped|xfailed|xpassed)" "$LOG" | tail -1
grep -E "^(FAILED|ERROR)" "$LOG" | sed 's#^#  #'
echo "rc=$rc"

build=$("$ADB" -s "${DEVICES[0]%%:*}" shell dumpsys package "$APP" 2>/dev/null | grep -m1 versionName | tr -d ' ')
{
  echo "Platform=android"
  echo "AppBuild=${build:-unknown}"
  echo "Devices=$(printf '%s\n' "${DEVICES[@]}" | grep -o 'emulator-[0-9]*' | paste -sd, -)"
  echo "Run=xdist dynamic queue (-n ${NPROC} --dist ${DIST})"
} > "${ALLURE_DIR}/environment.properties"

if command -v allure >/dev/null 2>&1; then
  allure generate --clean "$ALLURE_DIR" -o "$ALLURE_REPORT" >/dev/null 2>&1 \
    && echo "Allure report: ${ALLURE_REPORT}/index.html   (live: allure serve ${ALLURE_DIR})" \
    || echo "(allure generate failed — raw results in ${ALLURE_DIR})"
fi
exit "$rc"
