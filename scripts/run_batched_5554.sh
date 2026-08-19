#!/usr/bin/env bash
# Resumable single-device batch runner (emulator-5554). Runs the suite in small
# groups so each finishes (~8-12 min) and records its result immediately. If the
# process is stopped mid-way, relaunching SKIPS already-DONE groups and continues.
# Aggregated results: $RESULTS ; per-group logs: $LOGDIR/<group>.log
set -o pipefail
cd "$(dirname "$0")/.." || exit 1
PY=./venv/bin/python
LOGDIR=/tmp/raiz_2dev/batch3317
RESULTS="$LOGDIR/results.txt"
mkdir -p "$LOGDIR"; touch "$RESULTS"
CAFFEINATE="${CAFFEINATE-caffeinate -i}"; command -v caffeinate >/dev/null 2>&1 || CAFFEINATE=""
TIMEOUT="${TIMEOUT:-700}"
ADB="$HOME/Library/Android/sdk/platform-tools/adb"

K_SAFE="not TestLogin and not TestLoginErrorHandling and not TestPasswordVisibility and not TestForgotPassword and not test_log_out_from_pin_screen and not TestSessionLifecycleE2E and not test_logout_prompts_and_cancel_keeps_session"

# --- batch definitions (name => file list). Ordered fast/light first. ---
declare -a NAMES=(units_api navigation home_auth_settings portfolio_invest jars_kids flows_value_recon)
declare -a G_units_api="tests/test_assertions_unit.py tests/test_deep_links_registry_unit.py tests/test_value_validation_api.py tests/test_auth_states_api.py tests/test_auth_account_states_api.py"
declare -a G_navigation="tests/test_navigation_coverage.py tests/test_navigation.py"
declare -a G_home_auth_settings="tests/test_home.py tests/test_home_total_conservation.py tests/test_auth.py tests/test_settings.py tests/test_settings_profile_value.py tests/test_funding_source_contents.py"
declare -a G_portfolio_invest="tests/test_portfolio.py tests/test_investments.py tests/test_per_account_performance_tab.py tests/test_per_jar_portfolio_independent.py tests/test_per_kid_portfolio_independent.py tests/test_main_portfolio_reconciliation.py tests/test_portfolio_style_allocation_weights.py"
declare -a G_jars_kids="tests/test_jars.py tests/test_jars_value_on_device.py tests/test_jars_count_after_create.py tests/test_jar_below_min_deposit_rejected.py tests/test_jar_goal_progress_ring.py tests/test_jar_name_icon_persist.py tests/test_jar_six_cap_enforced.py tests/test_jar_target_roundtrip.py tests/test_kids.py tests/test_kids_value_on_device.py tests/test_kid_eight_cap_enforced.py tests/test_kid_fund_no_cross_post.py tests/test_kid_initial_below5_rejected.py tests/test_kid_summary_rows_recon.py tests/test_new_kid_zero_start.py tests/test_allocation_jars_kids_e2e.py tests/test_main_jar_transfer_conserves.py tests/test_recurring_into_jar_no_goal.py tests/test_tier_gating_kids_jars.py"
declare -a G_flows_value_recon="tests/test_rewards.py tests/test_rewards_track_value.py tests/test_rewards_webview_loads.py tests/test_e2e_flows.py tests/test_more_e2e_flows.py tests/test_edge_cases_e2e.py tests/test_myfinance_empty_state.py tests/test_my_finance_networth_recon.py tests/test_networth_total_investments_recon.py tests/test_net_invested_ledger_recon.py tests/test_inflow_triple_oracle.py tests/test_deposit_main_routing_isolation.py tests/test_deposit_sub5_rejected.py tests/test_withdrawal_e2e.py tests/test_withdraw_available_value.py tests/test_withdraw_over_balance_rejected.py tests/test_txn_history_ledger.py tests/test_recurring_create_roundtrip.py tests/test_recurring_value_and_save.py tests/test_generated_user_onboarding_e2e.py tests/test_main_value_on_device.py tests/test_value_reconciliation.py tests/test_pending_vs_settled_distinction.py"

for name in "${NAMES[@]}"; do
  if grep -q "^DONE ${name}:" "$RESULTS"; then echo "== skip ${name} (already done) =="; continue; fi
  files_var="G_${name}"; files="${!files_var}"
  echo "== RUN ${name} =="
  "$ADB" -s emulator-5554 forward --remove-all >/dev/null 2>&1
  "$ADB" -s emulator-5554 shell am force-stop io.appium.uiautomator2.server >/dev/null 2>&1
  glog="$LOGDIR/${name}.log"
  ANDROID_UDID=emulator-5554 APPIUM_HOST="http://127.0.0.1:4723" ANDROID_SYSTEM_PORT=8201 ANDROID_MJPEG_PORT=7811 \
    $CAFFEINATE "$PY" -m pytest $files -k "$K_SAFE" \
      -o addopts="" -p no:cacheprovider -q --timeout="$TIMEOUT" --timeout_method=signal --tb=line > "$glog" 2>&1
  rc=$?
  summary=$(grep -E ' (passed|failed|error|skipped|xfailed)' "$glog" | tail -1)
  echo "DONE ${name}: rc=${rc} ${summary}" >> "$RESULTS"
  # record failure names for this group
  grep -E "^(FAILED|ERROR)" "$glog" | sed "s/^/  [${name}] /" >> "$RESULTS"
  echo "   -> ${summary}"
done

echo ""
echo "===== AGGREGATE ====="
cat "$RESULTS"
echo "ALL_BATCHES_DONE"
