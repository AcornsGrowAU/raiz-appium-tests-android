# Skipped Tests — ranked by reason frequency

_78 skip sites, 62 distinct reasons._


## (5×) skip-with-reason:

- `test_per_jar_portfolio_independent.py::test_per_jar_portfolio_stored_independently`
- `test_per_kid_portfolio_independent.py::test_per_kid_portfolio_stored_independently`
- `test_portfolio_style_allocation_weights.py::test_portfolio_style_allocation_weights`

## (4×) Bitcoin category not reachable in the Plus builder this run

- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_bitcoin_holding_clamped_at_5_percent`
- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_reallocating_a_holding_steps_without_drift`
- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_running_total_stays_100_during_reallocation`
- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_saving_a_custom_allocation_is_gated`

## (4×) No linked Round-Ups account — re-link

- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_dashboard_filter_tabs`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_dashboard_shows_auto_and_manual`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_filter_tabs_change_content`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_invested_total_is_well_formed_money`

## (3×) No jar tab on Performance — account/build does not surface the Portfolio/Jar split

- `test_portfolio.py::TestPerformanceScreen::test_jar_tab_navigates`
- `test_portfolio.py::TestPerformanceScreen::test_jar_tab_visible`
- `test_portfolio.py::TestPerformanceScreen::test_portfolio_tab_visible`

## (3×) Round-Ups settings not available (account unlinked?)

- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_settings_links_to_linked_accounts`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_settings_multiplier_options_render`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_settings_render_fully`

## (2×) Linked accounts screen not available (account unlinked?)

- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_linked_accounts_listed`
- `test_more_e2e_flows.py::TestRoundUpsE2E::test_round_ups_monitored_accounts_are_described`

## (2×) Plus intro variant shown; builder not reachable via Next this run

- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_plus_base_portfolio_starts_at_100_percent`

## (1×) Account has active kids — list screen shown, not onboarding

- `test_kids.py::TestKidsScreen::test_empty_state_shows_consent_or_welcome`

## (1×) Account has active kids — list screen shown, not the consent gate

- `test_allocation_jars_kids_e2e.py::TestKidsCreationE2E::test_kids_consent_gate_present_for_new_user`

## (1×) Account has already completed financial-insights setup —

- `test_more_e2e_flows.py::TestMyFinanceE2E::test_financial_insights_setup_card_present`

## (1×) Account has an active jar — list screen shown, not create

- `test_jars.py::TestJarsCreateScreen::test_empty_state_shows_create_screen`

## (1×) Account has an active jar — list screen shown, not the create screen

- `test_allocation_jars_kids_e2e.py::TestJarCreationE2E::test_create_jar_screen_loads`

## (1×) Account is funded; the $0.00 percentage case doesn

- `test_e2e_flows.py::TestPerformanceValueE2E::test_no_percentage_against_zero_value`

## (1×) Account-info detail not shown (account on onboarding step)

- `test_more_e2e_flows.py::TestSuperE2E::test_super_account_info_shows_member_identifiers_when_present`

## (1×) Change value is non-zero (or absent); the $0.00 % case doesn

- `test_portfolio.py::TestPerformanceRangeChangesValue::test_no_percentage_against_zero_change_value`

## (1×) Commits a real DEV investment; set RUN_DESTRUCTIVE=1 to run

- `test_e2e_flows.py::(skipif)`

## (1×) Could not confirm Super surface state (deep link did not resolve)

- `test_more_e2e_flows.py::TestMyFinanceE2E::test_super_component_reconciles_with_super_surface`

## (1×) Creates a real DEV jar (and leaves it on the account); set RUN_DESTRUCTIVE=1

- `test_allocation_jars_kids_e2e.py::(skipif)`

## (1×) Creates a real DEV jar (left on a throwaway user); opt-in via RUN_DESTRUCTIVE=1

- `test_jar_name_icon_persist.py::(skipif)`

## (1×) Creates a real DEV jar (left on the account); opt-in via RUN_DESTRUCTIVE=1

- `test_jars_count_after_create.py::(skipif)`

## (1×) Important-documents list not shown (account on onboarding step)

- `test_more_e2e_flows.py::TestSuperE2E::test_super_important_documents_lists_disclosures_when_present`

## (1×) Insurance opt-in is not the current super onboarding step

- `test_more_e2e_flows.py::TestSuperE2E::test_insurance_opt_in_discloses_consent_when_shown`

## (1×) Invest is disabled at $0 (gated at the button) on this build

- `test_edge_cases_e2e.py::TestAmountEntryEdgeCases::test_invest_zero_amount_reaches_confirmation`

## (1×) Links a bank account via the Yodlee sandbox; set RUN_DESTRUCTIVE=1

- `test_more_e2e_flows.py::(skipif)`

## (1×) Need at least two dated transactions to assert ordering

- `test_portfolio.py::TestTransactionOrderingAndFilter::test_transactions_are_newest_first`

## (1×) No $-denominated reward amounts rendered on this screen

- `test_rewards.py::TestRewardsEarnValues::test_reward_amounts_are_well_formed_money`

## (1×) No $-denominated tracked-reward amounts rendered

- `test_rewards.py::TestRewardsTrackValues::test_pending_and_invested_amounts_well_formed`

## (1×) No Featured/Boosted reward cards on the Earn tab to open

- `test_rewards_webview_loads.py::TestRewardsBrandDetailWebview::test_brand_detail_webview_renders_content`

## (1×) No KIDS recurring section on this account/build —

- `test_investments.py::TestRecurringInvestments::test_kids_section_visible`

## (1×) No active jar on this account — nothing to reconcile against Home

- `test_allocation_jars_kids_e2e.py::TestJarCreationE2E::test_active_jar_reflected_on_home_card`

## (1×) No active kids on this account — nothing to reconcile against Home

- `test_allocation_jars_kids_e2e.py::TestKidsCreationE2E::test_active_kids_reflected_on_home_card`

## (1×) No category-spending data (empty state) — nothing to validate

- `test_more_e2e_flows.py::TestMyFinanceE2E::test_category_spending_amounts_well_formed_when_present`

## (1×) No notification toggles rendered on this build

- `test_settings.py::TestNotificationPreferences::test_notification_toggle_is_togglable_without_persisting`

## (1×) No transactions for this account

- `test_portfolio.py::TestTransactionOrderingAndFilter::test_rows_carry_a_recognisable_date`

## (1×) No transactions to filter

- `test_portfolio.py::TestTransactionOrderingAndFilter::test_transaction_type_filter_actually_filters`

## (1×) Personal details screen does not surface an email on this build

- `test_settings.py::TestProfileContentCorrectness::test_personal_details_shows_account_email`

## (1×) Raiz Property Fund category not reachable in the Plus builder this run

- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_raiz_property_holding_clamped_at_30_percent`

## (1×) Round-Ups account already linked — nothing to do

- `test_more_e2e_flows.py::TestRoundUpsE2E::test_link_round_ups_account_via_dag_sandbox`

## (1×) Save Allocation control not present in this editor variant

- `test_allocation_jars_kids_e2e.py::TestCustomPortfolioPlusE2E::test_saving_a_custom_allocation_is_gated`

## (1×) Test account has insufficient balance to withdraw (${available})

- `test_e2e_flows.py::TestWithdrawE2E::test_withdraw_reaches_confirmation_then_cancels`

## (1×) Track tab is in its empty state — no pending/invested split to reconcile

- `test_rewards_track_value.py::TestRewardsTrackPendingInvestedSplit::test_track_pending_invested_split_reconciles`

## (1×) destructive (submits a real DEV withdrawal); set RUN_DESTRUCTIVE=1 to run

- `test_withdraw_available_value.py::_BalanceReader::test_withdraw_available_matches_backend_and_completes`

## (1×) on-device read-back blocked by onboarding gauntlet: {e}

- `test_jar_target_roundtrip.py::OnboardingBlocked::test_jar_goal_roundtrips_exactly_on_device`

## (1×) skip-with-reason: $4.99 commit kept returning transient HTTP

- `test_deposit_sub5_rejected.py::test_sub_five_dollar_lump_sum_rejected_five_accepted`

## (1×) skip-with-reason: $5.00 commit kept returning transient HTTP

- `test_deposit_sub5_rejected.py::test_sub_five_dollar_lump_sum_rejected_five_accepted`

## (1×) skip-with-reason: GET /jars/v1/users failed (HTTP {status}

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: GET /v1/user returned HTTP {su} for {email};

- `test_myfinance_empty_state.py::test_unlinked_user_shows_empty_my_finance_state`

## (1×) skip-with-reason: GET {SUMMARY_PATH} returned HTTP {s}

- `test_myfinance_empty_state.py::test_unlinked_user_shows_empty_my_finance_state`

## (1×) skip-with-reason: could not list the throwaway jar (HTTP {s});

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: could not log in as

- `test_deposit_sub5_rejected.py::(module)`

## (1×) skip-with-reason: could not log in as the jar_below_min parent

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: could not log in as the throwaway acceptance parent

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: could not log in fixture myfinance_unlinked

- `test_myfinance_empty_state.py::test_unlinked_user_shows_empty_my_finance_state`

## (1×) skip-with-reason: could not obtain

- `test_deposit_sub5_rejected.py::(module)`

## (1×) skip-with-reason: could not re-auth before the $5 accept leg

- `test_deposit_sub5_rejected.py::test_sub_five_dollar_lump_sum_rejected_five_accepted`

## (1×) skip-with-reason: could not read back one or more sub-account

- `test_home_total_conservation.py::test_home_total_reconciles_to_jar_and_kid_cards_and_backend_aggregate`

## (1×) skip-with-reason: could not read jar/kid balances back

- `test_deposit_main_routing_isolation.py::test_deposit_into_main_does_not_move_jar_or_kid`

## (1×) skip-with-reason: could not resolve

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: could not seed the throwaway $5-acceptance rig

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: fixture jar

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: jar entity missing uuid id (fixture-shape gate)

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`

## (1×) skip-with-reason: re-read of jars failed (HTTP {status});

- `test_jar_below_min_deposit_rejected.py::test_jar_below_min_deposit_rejected`
