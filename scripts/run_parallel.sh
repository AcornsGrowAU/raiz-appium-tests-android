#!/usr/bin/env bash
#
# run_parallel.sh — run the Raiz Appium suite across multiple emulators/devices
# concurrently, one pytest process per device, with the work split by feature.
#
# WHY: the suite uses a session-scoped driver, so a single device runs serially
# (~2h for the full suite). Sharding across N devices runs in ~max(shard) time.
# Concurrent UiAutomator2 sessions MUST each get a distinct systemPort/mjpegPort
# or they collide on the 8200/7810 defaults — config/capabilities.py reads
# ANDROID_SYSTEM_PORT / ANDROID_MJPEG_PORT from the env for exactly this.
#
# PREREQUISITES
#   - One Appium server per device, on the ports below (see start_servers note).
#       appium --relaxed-security -p 4723   # and 4724, 4725 ...
#   - Each device logged in to the test account (PIN 0000), autofill disabled:
#       adb -s <udid> shell settings put secure autofill_service null
#   - All devices on the SAME app build.
#
# SHARED-ACCOUNT SAFETY: all devices use one Raiz account, so tests that log out
# or cold-reset (fresh_driver) would invalidate the other devices' sessions and
# re-trigger OTP. Those are deselected per-shard via the K_* filters below.
# Destructive tests stay skipped unless you export RUN_DESTRUCTIVE=1 (don't, on a
# shared account).
#
# USAGE
#   ./scripts/run_parallel.sh                 # run all shards in parallel
#   TIMEOUT=90 ./scripts/run_parallel.sh      # override per-test timeout (s)
#   HTML=1 ./scripts/run_parallel.sh          # also emit per-device HTML reports
#   ./scripts/run_parallel.sh smoke           # only tests marked 'smoke' (extra -m)
#
# Exit code is non-zero if any shard had failures/errors.

# NOTE: no `set -u` — macOS ships bash 3.2, where expanding an empty array
# ("${arr[@]}" when a shard has no -k/-m) raises "unbound variable" under nounset
# and would kill the shard before pytest runs.
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
TIMEOUT="${TIMEOUT:-120}"
EXTRA_MARK="${1:-}"                       # optional pytest -m marker, e.g. smoke
LOGDIR="${LOGDIR:-/tmp/raiz_parallel}"
ALLURE_DIR="${ALLURE_DIR:-reports/allure-results}"
ALLURE_REPORT="${ALLURE_REPORT:-reports/allure-report}"
mkdir -p "$LOGDIR" reports
# Fresh Allure results each run; all shards write into this one dir (Allure merges
# the per-test result files — concurrent writes are safe, no clobbering).
rm -rf "$ALLURE_DIR" && mkdir -p "$ALLURE_DIR"

# Shared-account safety deselections (substring match on node names).
K_AUTH_SAFE="not TestLogin and not TestLoginErrorHandling and not TestPasswordVisibility and not TestForgotPassword and not test_log_out_from_pin_screen"
# Also exclude the settings logout-entry test: on build 3223 logout commits with
# NO confirmation dialog, so it ends the session and can invalidate the OTHER
# devices' shared-account sessions mid-run (the logout->re-login flow is owned by
# the dedicated session-lifecycle tests, which are already deselected).
K_E2E_SAFE="not TestSessionLifecycleE2E and not test_logout_prompts_and_cancel_keeps_session"

# Shard config: one line per device.
#   udid | appium_port | system_port | mjpeg_port | -k filter (or "-") | files...
SHARDS=(
  "emulator-5554|4723|8201|7811|${K_AUTH_SAFE}|tests/test_home.py tests/test_navigation.py tests/test_navigation_coverage.py tests/test_auth.py"
  "emulator-5556|4724|8202|7812|-|tests/test_portfolio.py tests/test_investments.py tests/test_rewards.py"
  "emulator-5558|4725|8204|7814|${K_E2E_SAFE}|tests/test_settings.py tests/test_jars.py tests/test_kids.py tests/test_allocation_jars_kids_e2e.py tests/test_more_e2e_flows.py tests/test_e2e_flows.py tests/test_edge_cases_e2e.py"
)

echo "== Preflight =="
fail_pre=0
for shard in "${SHARDS[@]}"; do
  IFS='|' read -r udid aport sport mport kfilter files <<< "$shard"
  printf "  %-16s appium:%s " "$udid" "$aport"
  if ! curl -s -m2 "http://127.0.0.1:${aport}/status" >/dev/null 2>&1; then
    echo "[Appium DOWN — start: appium --relaxed-security -p ${aport}]"; fail_pre=1; continue
  fi
  if ! adb devices | grep -q "^${udid}[[:space:]]\+device"; then
    echo "[device NOT connected]"; fail_pre=1; continue
  fi
  # Self-heal: clear stale adb port-forwards and any leftover UiAutomator2 server
  # from a previously killed/orphaned session, which otherwise leaves the
  # systemPort "busy" and fails session creation on the next run.
  adb -s "$udid" forward --remove-all >/dev/null 2>&1
  adb -s "$udid" shell am force-stop io.appium.uiautomator2.server >/dev/null 2>&1
  adb -s "$udid" shell am force-stop io.appium.uiautomator2.server.test >/dev/null 2>&1
  echo "[ok, cleaned]"
done
[ "$fail_pre" -ne 0 ] && { echo "Preflight failed — fix the above and retry."; exit 2; }

echo "== Launching $(echo "${#SHARDS[@]}") shards (timeout=${TIMEOUT}s${EXTRA_MARK:+, -m ${EXTRA_MARK}}) =="
pids=()
for shard in "${SHARDS[@]}"; do
  IFS='|' read -r udid aport sport mport kfilter files <<< "$shard"
  log="${LOGDIR}/run_${udid}.log"
  : > "$log"
  k_args=(); [ "$kfilter" != "-" ] && k_args=(-k "$kfilter")
  m_args=(); [ -n "$EXTRA_MARK" ] && m_args=(-m "$EXTRA_MARK")
  # Drop pytest.ini's default addopts (its single --html/--alluredir would have all
  # 3 shards fight over one file); write Allure results for THIS shard into the
  # shared dir instead.
  out_args=(-o addopts="" --alluredir="$ALLURE_DIR")
  (
    ANDROID_UDID="$udid" APPIUM_HOST="http://127.0.0.1:${aport}" \
    ANDROID_SYSTEM_PORT="$sport" ANDROID_MJPEG_PORT="$mport" \
      $CAFFEINATE "$PY" -m pytest $files "${k_args[@]}" "${m_args[@]}" "${out_args[@]}" \
        -q --timeout="$TIMEOUT" --timeout_method=signal --tb=line >> "$log" 2>&1
    echo "EXIT=$?" >> "$log"
  ) &
  pids+=("$!")
  echo "  -> $udid (sysPort $sport) : $files  [log: $log]"
done

echo "== Waiting for all shards =="
rc=0
for pid in "${pids[@]}"; do wait "$pid" || rc=1; done

echo ""
echo "===== SUMMARY ====="
overall=0
for shard in "${SHARDS[@]}"; do
  IFS='|' read -r udid aport sport mport kfilter files <<< "$shard"
  log="${LOGDIR}/run_${udid}.log"
  summary=$(grep -E " (passed|failed|error)" "$log" | tail -1)
  printf "  %-16s %s\n" "$udid" "${summary:-<no result — check $log>}"
  if grep -qE "^(FAILED|ERROR)" "$log"; then
    overall=1
    grep -E "^(FAILED|ERROR)" "$log" | sed 's/^/      /'
  fi
done
echo "==================="
[ "$overall" -eq 0 ] && echo "All shards green (failures, if any, are listed above)." \
                      || echo "Failures present — see lines above and per-device logs in ${LOGDIR}."

# --- Allure: combined environment + merged report across all shards ---
build=$(adb -s "$(echo "${SHARDS[0]}" | cut -d'|' -f1)" shell dumpsys package "$(./venv/bin/python -c 'from config.settings import ANDROID_APP_PACKAGE; print(ANDROID_APP_PACKAGE)' 2>/dev/null)" 2>/dev/null | grep -m1 versionName | tr -d ' ')
{
  echo "Platform=android"
  echo "AppBuild=${build:-unknown}"
  echo "Devices=$(printf '%s ' "${SHARDS[@]}" | tr ' ' '\n' | grep -o 'emulator-[0-9]*' | paste -sd, -)"
  echo "Run=parallel (${#SHARDS[@]} shards)"
} > "${ALLURE_DIR}/environment.properties"

if command -v allure >/dev/null 2>&1; then
  echo ""
  echo "== Allure =="
  allure generate --clean "$ALLURE_DIR" -o "$ALLURE_REPORT" >/dev/null 2>&1 \
    && echo "  Report:  ${ALLURE_REPORT}/index.html" \
    || echo "  (allure generate failed — raw results in ${ALLURE_DIR})"
  echo "  Open it: allure open ${ALLURE_REPORT}"
  echo "  Or live: allure serve ${ALLURE_DIR}"
  [ "${SERVE:-0}" = "1" ] && allure serve "$ALLURE_DIR"
else
  echo "  Allure CLI not found — install with: brew install allure ; then: allure serve ${ALLURE_DIR}"
fi

exit "$overall"
