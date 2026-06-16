# Nav-Path UI Test Cases — Device C / ANALYST-2 (Drawer + Settings)

Source of truth: `docs/nav_map_5558.md` (Navigator live map). Page objects: `pages/nav_drawer.py`,
`pages/settings_page.py`, `pages/home_page.py`, `pages/rewards_page.py`. Coverage cross-referenced against
`tests/test_navigation.py`, `tests/test_settings.py`, `tests/test_e2e_flows.py`, `tests/test_rewards.py`.

Scope: pure UI-PATH navigation (tap → destination → back-stack). Drawer opens from hamburger
`(//android.widget.Button)[1]`; Settings opens from the gear `(//android.widget.Button)[2]` (NOT a drawer
item). Back-stack rule from the map: nested drawer screens (Main portfolio, Jars, Kids, Round-Ups, Recurring,
Lump Sum, My Finance, My Achievements, Offsetters) Back → **drawer**; top-level surfaces (Rewards, Surveys,
Super) Back → **Home**; Home Back → launcher. Every Settings sub-screen Back → **Settings** (RAIZ-9994).

SAFETY: Log out commits immediately with NO confirmation dialog (map Mismatch #2) — its case is
presence/intent-only or manual; it must NOT strand the shared session. No reward redemption, no money movement,
no Close account / Dev Settings destructive actions.

Legend — COVERED: yes = full UI-path incl. back-stack; partial = destination or open covered but back-stack
weak/asserts-Home not drawer, or destination matcher loose; no = gap.

---

## 1. DRAWER — open / structure / close

| # | Proposed test name | Item | UI path (taps) | Destination assertion (real element) | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|------|----------------|---------------------------------------|----------------------|----------|----------|-------|
| D0 | test_drawer_opens_from_hamburger | Drawer open | Home → hamburger `Button[1]` | `NAV_HOME` visible (drawer 'Home' item) | n/a | yes — `test_navigation.py::TestNavDrawer::test_drawer_opens` + `test_drawer_has_home_item` | P1 | nav_drawer fixture does the open |
| D1 | test_drawer_section_save_earn_present | Section header | drawer open | `SECTION_SAVE_EARN` ('SAVE & EARN') visible | n/a | yes — `TestDrawerCoverage::test_drawer_has_save_earn_section` | P2 | top, no scroll |
| D2 | test_drawer_section_investment_accounts_present | Section header | drawer open | `SECTION_INVESTMENT_ACCOUNTS` visible | n/a | yes — `TestNavDrawer::test_drawer_has_investment_accounts_section` | P2 | |
| D3 | test_drawer_section_investment_prefs_present | Section header | drawer open → scroll | `SECTION_INVESTMENT_PREFS` visible | n/a | yes — `TestDrawerCoverage::test_drawer_scrolls_to_investment_prefs_section` | P2 | below fold |
| D4 | test_drawer_section_do_more_present | Section header | drawer open → scroll | `SECTION_DO_MORE` ('DO MORE WITH RAIZ') visible | n/a | yes — `TestNavDrawer::test_drawer_scrolls_to_do_more_section` | P2 | 4th/last section |
| D5 | test_drawer_closes_on_back | Drawer close | drawer open → Back | `HomePage.is_loaded()` | drawer→Home | yes — `TestNavDrawer::test_drawer_closes_on_back` | P1 | |
| D6 | test_drawer_reopens_after_close | Drawer robustness | close → `tap_hamburger` → close | `is_open()` true after reopen; Home after final close | n/a | yes — `TestDrawerOpenCloseRobustness::test_drawer_reopens_after_close` | P2 | |

## 1a. DRAWER — per-item navigation (13 items) + back-stack

| # | Proposed test name | Item | UI path (taps) | Destination assertion (real element) | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|------|----------------|---------------------------------------|----------------------|----------|----------|-------|
| DI1 | test_drawer_home_item_opens_home | Home | drawer → `go_home` | `HomePage.is_loaded()` ("Hello, Jsoj"/tab bar) | Home Back → launcher (do NOT press Back — would exit app; assert open only) | yes (open) — `TestDrawerOpenCloseRobustness::test_drawer_home_item_returns_home`; back-to-launcher **no** | P2 | Home Back exits to launcher — keep manual/observe, never auto-press Back |
| DI2 | test_drawer_rewards_opens_rewards_back_home | Rewards | drawer → `go_rewards` | `RewardsPage.is_loaded()` (Earn/Track tabs) | Back → Home (top-level) | partial — open: `TestNavDrawer::test_drawer_navigates_to_rewards`; back→Home: `TestDrawerBackNavigationE2E[Rewards]` asserts recoverable Home | P1 | back-nav exists but tolerant (recovers via deep link) |
| DI3 | test_drawer_surveys_opens_rewards_earn_back_home | Surveys | drawer → `go_surveys` | Earn surface w/ Surveys section ('Survey'/'Earn' copy) | Back → Home (top-level) | partial — open: `TestDrawerCoverage::test_drawer_navigates_to_surveys` (loose matcher); back→Home **no** | P2 | map: Surveys is a section of Rewards Earn, not its own screen |
| DI4 | test_drawer_main_portfolio_opens_back_drawer | Main portfolio | drawer → `go_main_portfolio` | `MainPortfolioPage.is_loaded()` (Add funds/Withdraw/Invested) | Back → **drawer** (nested) | partial — open: `TestNavDrawer::test_drawer_navigates_to_main_portfolio`; back→**drawer** **no** (e2e asserts Home not drawer) | P1 | back-to-drawer behavior unverified by any test |
| DI5 | test_drawer_jars_opens_back_drawer | Jars | drawer → `go_jars` | `JarsPage.is_loaded()` ("Customise your Jar!"/Create Jar) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_jars`; back→**drawer** **no** | P1 | |
| DI6 | test_drawer_kids_opens_back_drawer | Kids | drawer → `go_kids` | `KidsPage.is_loaded()` (consent copy / 'I consent') | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_kids`; back→**drawer** **no** | P1 | do not tap 'I consent' |
| DI7 | test_drawer_super_opens_back_home | Super | drawer → `go_super` (scrolls) | `SuperPage.is_loaded()` ("Raiz Invest Super"/1300 75 47 48) | Back → Home (top-level) | partial — open: `TestNavDrawer::test_drawer_navigates_to_super`; back→Home **no** | P2 | top-level back target differs from siblings |
| DI8 | test_drawer_round_ups_opens_back_drawer | Round-Ups | drawer → `go_round_ups` (scrolls) | `RoundUpsPage.is_loaded()` ("Round-Ups invested"/Min $5/$10) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_round_ups`; back→**drawer** **no** | P2 | |
| DI9 | test_drawer_recurring_opens_back_drawer | Recurring investments | drawer → `go_recurring` (scrolls) | `RecurringPage.is_loaded()` ("MAIN PORTFOLIO"/Raiz Kids/Raiz Jars) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_recurring`; back→**drawer** **no** | P2 | |
| DI10 | test_drawer_lump_sum_opens_back_drawer | Lump Sum investments | drawer → `go_lump_sum` (scrolls) | `LumpSumPage.is_lump_sum_loaded()` (Invest keypad 1-9) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_lump_sum`; back→**drawer** **no** | P2 | keypad only; do NOT enter amount |
| DI11 | test_drawer_my_finance_opens_back_drawer | My Finance | drawer → `go_my_finance` (scrolls) | `MyFinancePage.is_loaded()` ("Set up your financial insights"/0 of 3) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_my_finance`; back→**drawer** **no** (e2e asserts Home) | P2 | |
| DI12 | test_drawer_achievements_opens_back_drawer | My Achievements | drawer → `go_my_achievements` (scrolls) | "Achievements"/"Goals" title (Goal Setter, Quarter Closer) | Back → **drawer** | partial — open: `TestNavDrawer::test_drawer_navigates_to_achievements`; back→**drawer** **no** | P2 | map title 'Goals'; test uses 'Achievements' |
| DI13 | test_drawer_offsetters_opens_back_drawer | Offsetters | drawer → `go_offsetters` (scrolls) | "Offset" copy (Offset/Impact/Win tabs, Learn More) | Back → **drawer** | partial — open: `TestDrawerCoverage::test_drawer_navigates_to_offsetters`; back→**drawer** **no** | P2 | loose 'Offset' matcher |

## 1b. DRAWER — back-stack quirk gap (dedicated cases)

| # | Proposed test name | Item | UI path (taps) | Destination assertion | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|------|----------------|------------------------|----------------------|----------|----------|-------|
| DB1 | test_back_from_nested_drawer_item_returns_to_drawer | Main portfolio (representative) | drawer → `go_main_portfolio` → Back | left Home (dest loaded) | **drawer reopened**: `NavDrawer.is_open()` true after Back | no — existing `TestDrawerBackNavigationE2E` asserts Back→**Home**, contradicting map's drawer-reopen behavior | P1 | NEW: pin the map's nested→drawer contract; if app actually returns Home this is a finding to flag |
| DB2 | test_back_from_topbar_drawer_item_returns_home | Super (representative) | drawer → `go_super` → Back | dest loaded | Home loaded (top-level rule) | no | P3 | distinguishes top-level vs nested back rule |

---

## 2. SETTINGS — open + per-row navigation (14 rows) + back→Settings (RAIZ-9994)

Open path: Home → gear `Button[2]` → `SettingsPage.is_loaded()` (TITLE 'Settings'). `settings` fixture does this.

| # | Proposed test name | Row | UI path (taps) | Destination assertion (real element) | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|-----|----------------|---------------------------------------|----------------------|----------|----------|-------|
| S0 | test_settings_opens_from_gear | (open) | Home → gear `Button[2]` | `SettingsPage.is_loaded()` (TITLE 'Settings') | n/a | yes — `TestSettingsScreen::test_settings_loads` | P1 | gear path, NOT drawer |
| S1 | test_notifications_inbox_opens_back_settings | Notifications inbox | settings → `tap_notifications_inbox` | dated feed ("08.05.2026"/'$500.00 has been invested') | Back → Settings | yes — `TestSettingsBackNavigationE2E[Notifications inbox]` (test_e2e_flows.py) | P1 | badge '6' visible on row |
| S2 | test_funding_account_opens_back_settings | Funding account | settings → `tap_funding_account` | "funds all investments…"/(1234)/Account verified | Back → Settings | yes — `TestSettingsBackNavigationE2E[Funding account]` | P1 | do NOT tap Change |
| S3 | test_accounts_financial_insights_opens_back_settings | Accounts for financial insights | settings → `tap_accounts_financial_insights` | "Connect and give read only access…"/Dag Site (US) | Back → Settings | yes — `TestSettingsBackNavigationExtraE2E[Accounts for financial insights]` (test_settings.py) | P1 | |
| S4 | test_plans_and_fees_opens_back_settings | Plans and fees | settings → `tap_plans_and_fees` | "account fee of 0.275%"/PLAN/Pricing plan | Back → Settings | yes — `TestSettingsBackNavigationE2E[Plans and fees]` + `TestSettingsItemDestinationE2E::test_plans_and_fees_opens_plans_or_fees` | P1 | |
| S5 | test_personal_details_opens_back_settings | Personal details | settings → `tap_personal_details` | "Legal First Name"/Email/Phone | Back → Settings | yes — `TestSettingsBackNavigationE2E[Personal details]` (back); content: `TestProfileContentCorrectness` | P1 | |
| S6 | test_security_privacy_opens_back_settings | Security and privacy | settings → `tap_security_privacy` | "Change Password"/Change PIN/Use biometrics | Back → Settings | yes — `TestSettingsBackNavigationE2E[Security and privacy]` | P1 | do NOT tap Close account (destructive) |
| S7 | test_manage_notifications_opens_back_settings | Manage notifications | settings → `tap_manage_notifications` | "modify your push notifications…"/Email+Push toggles | Back → Settings | yes — `TestSettingsBackNavigationExtraE2E[Manage notifications]` + `TestSettingsItemDestinationE2E::test_manage_notifications_opens_notification_settings` | P1 | not the inbox |
| S8 | test_manage_round_ups_opens_back_settings | Manage Round-Ups | settings → `tap_manage_round_ups` | "Round-Ups invested"/Min Round-Ups $5/$10 | Back → Settings | yes — `TestSettingsBackNavigationExtraE2E[Manage Round-Ups]` + `TestSettingsItemDestinationE2E::test_manage_round_ups_opens_round_ups` | P2 | |
| S9 | test_refer_a_friend_opens_back_settings | Refer a friend | settings → `tap_refer_a_friend` | "Invite friends."/code MYE3QG/Your reward | Back → Settings | partial — `TestSettingsHelpLegalBackNavigationE2E[Refer a friend]` (tolerant: skips/Home-fallback if external) | P2 | == invite_friends screen |
| S10 | test_rate_raiz_opens_modal_dismiss | Rate Raiz | settings → tap 'Rate Raiz' | "How would you rate Raiz?" modal (1–5, Not Now) | dismiss via 'Not Now' → returns to modal's prior state (NOT clean Settings — map Mismatch #4) | no | P2 | NEW: modal, not a screen; assert modal opens + Not Now dismisses; document non-clean back |
| S11 | test_how_to_start_opens_back_settings | How to start guide | settings → tap 'How to start guide' | "What can I invest in?" FAQ (funding vs Round-Ups) | Back → Settings | no | P2 | NEW gap — no test taps this row |
| S12 | test_get_support_opens_back_or_subtabs | Get support | settings → `tap_get_support` | "Need a hand?"/Raiz Invest/Super/Contact Us tabs/1300 75 47 48 | Back → Settings OR self (sub-tabs dead-end per map §3) | partial — `TestSettingsHelpLegalBackNavigationE2E[Get support]` (tolerant) | P2 | map flags sub-tab/dead-end back behavior |
| S13 | test_our_terms_opens_back_settings | Our terms | settings → `tap_our_terms` | "Last updated: 14 May 2026"/T&C/PDS/TMD | Back → Settings | partial — `TestSettingsHelpLegalBackNavigationE2E[Our terms]` (tolerant) | P2 | |
| S14 | test_statements_reports_opens_back_settings | Statements and reports | settings → `tap_statements_reports` | dated statements ("May 8th")/"Send CSV of all trades"/Select | Back → Settings | partial — `TestSettingsHelpLegalBackNavigationE2E[Statements and reports]` (tolerant) | P2 | do NOT trigger CSV send |

## 2a. SETTINGS — special rows (Dev Settings, Log out)

| # | Proposed test name | Row | UI path (taps) | Destination assertion | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|-----|----------------|------------------------|----------------------|----------|----------|-------|
| S15 | test_dev_settings_row_present_dev_build | Dev Settings | settings → scroll | row 'Dev Settings' present (dev-build only) | (do NOT enter — Clear Preference/Data Store are destructive) | no | P3 | NEW: presence-only; do not tap into it. Map §5/§6: destructive surface |
| S16 | test_log_out_row_present_and_no_confirm_dialog_FINDING | **Log out** | settings → scroll → (presence only) | row `LOG_OUT` present + version footer present | **DO NOT TAP to completion** — map Mismatch #2: tapping logs out IMMEDIATELY, no confirm dialog; strands shared session | partial/FINDING — `TestSettingsScreen::test_log_out_visible_after_scroll` (presence). `TestLogoutEntryPoint::test_logout_prompts_and_cancel_keeps_session` taps it and **expects a prompt that does NOT exist** → recovers + fails as a documented finding | P1 | DOCUMENTED PRODUCT FINDING: `settings_page.logout_prompt_shown()/cancel_logout()` assume a cancellable dialog that the build does not show. Keep Log-out as presence-only OR mark manual/destructive. Real logout→re-login is owned by `test_e2e_flows.py::TestSessionLifecycleE2E`, not this UI-path suite |

---

## 3. REWARDS — Earn/Track tab switch + open reward detail (observe only)

| # | Proposed test name | Item | UI path (taps) | Destination assertion (real element) | Back-stack assertion | COVERED? | Priority | Notes |
|---|--------------------|------|----------------|---------------------------------------|----------------------|----------|----------|-------|
| R1 | test_rewards_earn_to_track_switches_content | Earn→Track tab | rewards → `switch_to_track` | Track content (`is_track_content_loaded`: Pending/Invested) AND Earn featured list gone | n/a (tab, not back-stack) | yes — `TestRewardsTabContentSwitch::test_track_shows_tracked_content_not_just_tab` + `test_track_does_not_show_earn_featured_list` | P1 | content-differs assertion, not just tab-still-visible |
| R2 | test_rewards_track_to_earn_restores_featured | Track→Earn tab | rewards → switch_to_track → `switch_to_earn` | `is_earn_content_loaded()` (featured list back) | n/a | yes — `TestRewardsTabContentSwitch::test_earn_shows_featured_list_after_returning_from_track` | P2 | |
| R3 | test_open_reward_opens_detail | Reward card | rewards Earn → `open_first_reward` | `is_detail_screen_shown()` (Shop online here / T&C; 'Neat test') | n/a | yes — `TestRewardsDetailNavigation::test_opening_reward_navigates_to_detail` | P2 | observe only; do NOT tap 'Shop online here' (webview) |
| R4 | test_reward_detail_back_returns_to_list | Reward detail back | open reward → Back | `EARN_TAB` visible again (list restored) | detail → Earn list | yes — `TestRewardsDetailNavigation::test_detail_back_returns_to_rewards_list` | P2 | no redemption |
| R5 | test_track_tab_resolves_to_definite_state | Track empty-state | rewards → switch_to_track | loaded OR explicit empty-state (never blank) | n/a | yes — `TestRewardsTrackValues::test_track_state_is_empty_or_loaded` | P3 | account has no rewards (map §4) |

---

## Coverage rollup

- **Drawer items (13):** all 13 have an OPEN/destination case (12 in TestNavDrawer/TestDrawerCoverage + Home).
  Back-stack per the map's nested→drawer rule is a GAP for every nested item (existing e2e asserts Back→Home, not
  Back→drawer): DI4–DI6, DI8–DI13 + DB1/DB2. Top-level back→Home (Rewards/Surveys/Super) only loosely covered.
- **Settings rows (14 + Log out + Dev Settings):** 8 rows fully covered for open+back→Settings (S1–S8); 4 rows
  partial via tolerant Help/Legal back-nav (S9, S12–S14); GAPS: Rate Raiz (S10), How to start guide (S11),
  Dev Settings presence (S15). Log out (S16) is a documented finding (no confirm dialog).
- **Rewards tab/detail (R1–R5):** fully covered.

### Gaps requiring NEW cases (no existing coverage)
1. DB1 — back from a nested drawer item returns to the **drawer** (map's documented behavior; existing e2e
   asserts Home — needs reconciliation/finding). **P1**
2. DB2 — back from a top-level drawer item (Super) returns to **Home**. P3
3. S10 — Rate Raiz modal opens + 'Not Now' dismisses (non-clean back per Mismatch #4). P2
4. S11 — How to start guide opens FAQ + back→Settings. P2
5. S15 — Dev Settings row presence (dev build), do not enter. P3
6. S16 (finding) — Log out has NO confirmation dialog; the page-object `logout_prompt_shown()/cancel_logout()`
   assumption is wrong. Keep presence-only / manual. P1

### Notes / safety flags
- Log out (S16): presence/intent only. NEVER complete logout in this suite — strands the shared account.
- Close account (under Security & privacy) and Dev Settings actions (Clear Preference/Data Store): destructive —
  navigate to the parent screen only, never invoke.
- 'Shop online here' / external Get support / Our terms links open webviews/share sheets — Back may not return
  cleanly to the in-app screen; treat as tolerant (skip/recover) per existing Help/Legal pattern.
- Home drawer item (DI1): never auto-press Back from Home (exits to launcher) — assert open only.
