# Raiz AU Android — Navigation Coverage Matrix

**Build:** 2.39.1d / 3223 (LEGACY layout). Package `com.acornsau.android.development` (single `MainActivity`; whole app is one React/Compose surface).
**Synthesised from:** `docs/nav_map_5554.md`, `docs/nav_map_5556.md`, `docs/nav_map_5558.md` (live crawls) + 6 analyst case specs (236 cases).
**Purpose:** prove the suite navigates to EVERY area of the app. Every deep-link area (41 in `utils/deep_links.py`), every nav-drawer item (13), every Settings row (14 + Log out + Dev Settings), every Home tab / modal / onboarding gate / empty state, and every discovered in-screen sub-area is accounted for below.

Status legend:
- **covered** — an existing test already asserts this destination (cited).
- **new** — `tests/test_navigation_coverage.py` adds the (gap or strengthened) test.
- **xfail-mismatch** — registry/product mismatch encoded as `xfail(strict=False)` on the intended destination; the *real* destination is asserted by a non-xfail case.

The `NEW test name` column gives the `Class::param` in `tests/test_navigation_coverage.py`. Existing tests are in `tests/test_navigation.py` unless another file is named.

---

## 1. Deep-link areas (all 41 constants in `utils/deep_links.py`)

| Area (deep link) | How reached | Actual destination (per maps) | Existing test | NEW test | Status |
|---|---|---|---|---|---|
| `raiz://home` | deep link / drawer Home / launcher | Home dashboard ("Hello, Jsoj", total value, Today/Past/Future tabs) | `TestDeepLinks::test_deep_link_home` | `TestDeepLinkLoadsRealDestination[home]`, `TestDeepLinkBackStack[home]` (exits to launcher) | covered + new |
| `raiz://invest` | deep link / drawer Main portfolio | Main Portfolio summary (Add funds/Withdraw/Performance details/Invested) | `test_deep_link_portfolio` | `TestDeepLinkLoadsRealDestination[invest]`, `TestDeepLinkBackStack[invest]` | covered + new |
| `raiz://deposit` | deep link / Home Add funds > Lump Sum | Lump Sum investment keypad (Minimum of $5, $10/$25/$50/$100) | `lump_sum` fixture, `TestLumpSumScreen` | `TestDeepLinkLoadsRealDestination[deposit]`, `TestDeepLinkBackStack[deposit]` | new (no named direct-nav test before) |
| `raiz://withdraw` | deep link / Home Withdraw | Withdraw keypad (Available:) | `test_deep_link_withdraw` (title only) | `TestDeepLinkLoadsRealDestination[withdraw]`, `TestDeepLinkBackStack[withdraw]` | covered + new (back) |
| `raiz://recurring_investments` | deep link / drawer Recurring / Add funds > Recurring | Recurring investments (MAIN PORTFOLIO, Raiz Kids, Raiz Jars) | `test_deep_link_recurring_investments` | `TestDeepLinkLoadsRealDestination[recurring]`, `TestDeepLinkBackStack[recurring]` | covered + new (back) |
| `raiz://performance` | deep link / Invest > Performance details | Performance (range pills 1D..All) | `test_deep_link_performance`, back covered | `TestDeepLinkLoadsRealDestination[performance]` | covered |
| `raiz://performance/day` | deep link | **Home** (MISMATCH — not day-performance) | `test_deep_link_performance_day` (xfail) | `TestNavigationMismatches::test_performance_day_routes_home` (xfail), `TestDeepLinkBackStack[performance_day]` (exits launcher) | xfail-mismatch + new |
| `raiz://performance/month` | deep link | **Home** (MISMATCH — not month-performance) | `test_deep_link_performance_month` (xfail) | `TestNavigationMismatches::test_performance_month_routes_home` (xfail), `TestDeepLinkBackStack[performance_month]` | xfail-mismatch + new |
| `raiz://transactions` | deep link / Invest > Transaction history / journey link | Transaction History list (Filter, Buy rows) | `test_deep_link_transactions`, back covered | `TestDeepLinkLoadsRealDestination[transactions]` | covered |
| `raiz://history` | deep link / Home Past tab | **Investing-journey summary** (MISMATCH — not a txn list; == Past tab) | `test_deep_link_history` (asserts journey summary) | `TestDeepLinkBackStack[history]` (exits launcher), `TestUiPathNavigation::test_journey_transaction_history_link_reaches_list` | covered + new |
| `raiz://dividends` | deep link / Invest > Dividends row | Dividends screen (flaky cold-load: "Oops!"→PIN) | `test_deep_link_dividends` (no retry) | `TestDeepLinkLoadsRealDestination[dividends]` (retry-guarded), `TestDeepLinkBackStack[dividends]` | covered + new |
| `raiz://future` | deep link / Home Future tab | Future projection (Projected Value, age slider, View my portfolio) | none | `TestDeepLinkLoadsRealDestination[future]`, `TestDeepLinkBackStack[future]` (exits launcher) | new (hard gap) |
| `raiz://portfolio` | deep link | **Allocation breakdown** (MISMATCH — ETF % list, not overview) | `test_deep_link_portfolio_alias` | `TestDeepLinkBackStack[portfolio]` | covered + new (back) |
| `raiz://portfolio/custom` | deep link | Customise portfolio (Your Portfolio, ETFs, Bitcoin) | `test_deep_link_portfolio_custom` | `TestDeepLinkBackStack[portfolio_custom]` | covered + new (back) |
| `raiz://raiz_rewards` | deep link / drawer Rewards | Rewards — Earn tab (Featured rewards, merchant cards) | `test_deep_link_rewards` | `TestDeepLinkLoadsRealDestination[rewards]`, `TestDeepLinkBackStack[rewards]` | covered + new (back) |
| `raiz://rewards_linked_accounts` | deep link | Automatic Rewards Dag/Yodlee account picker (3-way convergence) | `test_deep_link_rewards_linked_accounts` (loose) | `TestDeepLinkLoadsRealDestination[rewards_linked_accounts]`, `TestDeepLinkBackStack[rewards_linked_accounts]` | covered + new |
| `raiz://rewards_auto` | deep link / drawer Surveys | **Rewards — Earn (Surveys section)** (ALIAS of raiz_rewards) | `test_deep_link_rewards_auto` (loose) | `TestNavigationMismatches::test_rewards_auto_is_earn_alias` (xfail), `TestDeepLinkBackStack[rewards_auto]` | xfail-mismatch + new |
| `raiz://accounts/rewards` | deep link | Automatic Rewards Dag picker (DUPLICATE of rewards_linked_accounts) | `test_deep_link_rewards_accounts` (loose) | `TestDeepLinkLoadsRealDestination[accounts_rewards]`, `TestDeepLinkBackStack[accounts_rewards]` | covered + new |
| `raiz://finance` | deep link / drawer My Finance | My Finance — "Set up your financial insights" empty state | `test_deep_link_finance`, back covered | `TestDeepLinkLoadsRealDestination[finance]` | covered |
| `raiz://accounts/financial_insights` | deep link / Settings > Accounts for financial insights | Financial-insights Dag picker (3-way convergence) | `test_deep_link_financial_insights_accounts` (loose) | `TestDeepLinkLoadsRealDestination[accounts_financial_insights]`, `TestDeepLinkBackStack[accounts_financial_insights]` | covered + new |
| `raiz://profile/personal` | deep link / Settings > Personal details | Personal details form (Legal First/Last Name, Email, Phone, address) | `test_deep_link_profile_personal` (loose) | `TestDeepLinkLoadsRealDestination[profile_personal]`, `TestDeepLinkBackStack[profile_personal]` | covered + new |
| `raiz://profile/financial` | deep link | Financial profile form (Employment, Household income, goal) | `test_deep_link_profile_financial` (loose) | `TestDeepLinkLoadsRealDestination[profile_financial]`, `TestDeepLinkBackStack[profile_financial]` | covered + new |
| `raiz://notifications_settings` | deep link / Settings > Manage notifications | Manage notifications (Email/Push toggles) | `test_deep_link_notifications_settings` (loose) | `TestDeepLinkLoadsRealDestination[notifications_settings]`, `TestDeepLinkBackStack[notifications_settings]` | covered + new |
| `raiz://fees` | deep link / Settings > Plans and fees | Plans and fees ("account fee of 0.275%", PLAN) | `test_deep_link_fees` | `TestDeepLinkLoadsRealDestination[fees]`, `TestDeepLinkBackStack[fees]` | covered + new |
| `raiz://offsetters` | deep link / drawer Offsetters | Offsetters (Offset/Impact/Win tabs, Learn More) | `test_deep_link_offsetters` | `TestDeepLinkLoadsRealDestination[offsetters]`, `TestDeepLinkBackStack[offsetters]` | covered + new |
| `raiz://blog` | deep link | Blog/articles list (Market update articles) | `test_deep_link_blog` (loose) | `TestDeepLinkLoadsRealDestination[blog]`, `TestDeepLinkBackStack[blog]` | covered + new |
| `raiz://invite_friends` | deep link / Settings > Refer a friend | Invite friends (code MYE3QG, "get $5 invested") | `test_deep_link_invite_friends` (loose) | `TestDeepLinkLoadsRealDestination[invite_friends]`, `TestDeepLinkBackStack[invite_friends]` | covered + new |
| `raiz://jars` | deep link / drawer Jars / Home Jars card | **Customise your Jar** create form (empty state; skips list) | `test_deep_link_jars`, back covered | `TestDeepLinkLoadsRealDestination[jars]` | covered |
| `raiz://raiz_kids` | deep link / drawer Kids / Home Kids card | Raiz Kids identity-consent gate ("I consent") | `test_deep_link_raiz_kids`, back covered (drawer) | `TestDeepLinkLoadsRealDestination[raiz_kids]`, `TestDeepLinkBackStack[raiz_kids]` | covered + new |
| `raiz://raiz_kids_2` | deep link | Raiz Kids consent gate (DUPLICATE of raiz_kids) | `test_deep_link_raiz_kids_2` | `TestDeepLinkBackStack[raiz_kids_2]` | covered + new (back) |
| `raiz://raiz_super` | deep link / drawer Super / Home Super card | Raiz Invest Super — fund-search error/contact state (unfunded) | `test_deep_link_raiz_super` (any surface) | `TestDeepLinkLoadsRealDestination[raiz_super]`, `TestDeepLinkBackStack[raiz_super]` | covered + new |
| `raiz://raiz_super/account_info` | deep link | **Falls back to Super error/contact** (MISMATCH — no account-info screen) | `test_deep_link_super_account_info` (tolerant) | `TestNavigationMismatches::test_super_account_info_intended_xfail` (xfail), `TestDeepLinkBackStack[super_account_info]` | xfail-mismatch + new |
| `raiz://raiz_super/important_documents` | deep link | **Falls back to Super error/contact** (MISMATCH — no docs screen) | `test_deep_link_super_important_documents` (tolerant) | `TestNavigationMismatches::test_super_important_docs_intended_xfail` (xfail), `TestDeepLinkBackStack[super_important_docs]` | xfail-mismatch + new |
| `raiz://round_ups` | deep link / drawer Round-Ups | Round-Ups dashboard (empty activity: Auto/Manual, tabs) | `test_deep_link_round_ups` | `TestDeepLinkLoadsRealDestination[round_ups]`, `TestDeepLinkBackStack[round_ups]` | covered + new (back) |
| `raiz://round_ups/settings` | deep link / Settings > Manage Round-Ups | Round-Up settings (Auto toggle, Minimum threshold) | `test_deep_link_round_ups_settings` | `TestDeepLinkLoadsRealDestination[round_ups_settings]`, `TestDeepLinkBackStack[round_ups_settings]` | covered + new (back) |
| `raiz://accounts/round_ups` | deep link / settings link | Linked accounts for Round-Ups (Dag accounts) | `test_deep_link_round_ups_accounts` | `TestDeepLinkLoadsRealDestination[accounts_round_ups]`, `TestDeepLinkBackStack[accounts_round_ups]` | covered + new (back) |
| `raiz://funding_account` | deep link / Settings > Funding account | Funding Account ((1234), Change, Account verified) | `test_deep_link_funding_account` (title) | `TestDeepLinkLoadsRealDestination[funding_account]`, `TestDeepLinkBackStack[funding_account]` | covered + new |
| `raiz://spending_account` | deep link | **Linked accounts for Round-Ups** (MISMATCH — no spending screen) | `test_deep_link_spending_account` (asserts real dest) | `TestNavigationMismatches::test_spending_account_intended_xfail` (xfail), `TestDeepLinkBackStack[spending_account]` | xfail-mismatch + new |
| `raiz://milestone` | deep link | Milestone overview ("Up next", progress, Fastest ways) | `test_deep_link_milestone` (title) | `TestDeepLinkLoadsRealDestination[milestone]`, `TestDeepLinkBackStack[milestone]` | covered + new |
| `raiz://achievements` | deep link / drawer My Achievements | Achievements badge grid (Goals/Round-Ups/Rewards) | `test_deep_link_achievements` | `TestDeepLinkLoadsRealDestination[achievements]`, `TestDeepLinkBackStack[achievements]` | covered + new (back) |
| `raiz://plans` | deep link | Pricing plans (Lite/Regular/Plus, Current plan, PDS/AID) | `test_deep_link_plans` (title) | `TestDeepLinkLoadsRealDestination[plans]`, `TestDeepLinkBackStack[plans]` | covered + new |

**Total deep-link areas: 41 — all accounted for.**

---

## 2. Nav-drawer items (13; hamburger = `(//android.widget.Button)[1]`)

| Drawer item | Actual destination | Back behavior (per map) | Existing test | NEW test | Status |
|---|---|---|---|---|---|
| Home | Home dashboard | exits to launcher (NOT auto-pressed) | `TestDrawerOpenCloseRobustness::test_drawer_home_item_returns_home` | `TestNavDrawerCoverage[Home]` (open only) | covered + new |
| Rewards | Rewards — Earn | Home | `test_drawer_navigates_to_rewards`, back covered | `TestNavDrawerCoverage[Rewards]` | covered + new |
| Surveys | Rewards — Earn (Surveys section) | Home | `test_drawer_navigates_to_surveys` (loose) | `TestNavDrawerCoverage[Surveys]` | covered + new |
| Main portfolio | Main Portfolio summary | **drawer** (nested) | `test_drawer_navigates_to_main_portfolio`, back-to-Home covered | `TestNavDrawerCoverage[Main portfolio]`; mismatch `TestNavigationMismatches::test_nested_drawer_back_returns_to_drawer` (xfail) | covered + new |
| Jars | Customise your Jar | drawer | `test_drawer_navigates_to_jars`, back covered | `TestNavDrawerCoverage[Jars]` | covered + new |
| Kids | Raiz Kids consent gate | drawer | `test_drawer_navigates_to_kids`, back covered | `TestNavDrawerCoverage[Kids]` | covered + new |
| Super | Raiz Invest Super | Home (top-level) | `test_drawer_navigates_to_super` | `TestNavDrawerCoverage[Super]` | covered + new |
| Round-Ups | Round-Ups dashboard | drawer | `test_drawer_navigates_to_round_ups` | `TestNavDrawerCoverage[Round-Ups]` | covered + new |
| Recurring investments | Recurring investments | drawer | `test_drawer_navigates_to_recurring` | `TestNavDrawerCoverage[Recurring investments]` | covered + new |
| Lump Sum investments | Lump Sum keypad | drawer | `test_drawer_navigates_to_lump_sum` | `TestNavDrawerCoverage[Lump Sum investments]` | covered + new |
| My Finance | My Finance empty state | drawer | `test_drawer_navigates_to_my_finance`, back covered | `TestNavDrawerCoverage[My Finance]` | covered + new |
| My Achievements | Achievements grid | drawer | `test_drawer_navigates_to_achievements` | `TestNavDrawerCoverage[My Achievements]` | covered + new |
| Offsetters | Offsetters | drawer | `test_drawer_navigates_to_offsetters` (loose) | `TestNavDrawerCoverage[Offsetters]` | covered + new |

**Total drawer items: 13 — all accounted for** (open+destination via `TestNavDrawerCoverage`; back-stack quirk documented in `TestNavigationMismatches`).

---

## 3. Settings rows (gear = `(//android.widget.Button)[2]`; 14 rows + Dev Settings + Log out)

| Settings row | Actual destination | Existing test | NEW test | Status |
|---|---|---|---|---|
| Notifications inbox | dated notification feed | `TestSettingsBackNavigationE2E[Notifications inbox]` | `TestSettingsCoverage[Notifications inbox]` | covered + new |
| Funding account | Funding Account ((1234), verified) | `TestSettingsBackNavigationE2E[Funding account]` | `TestSettingsCoverage[Funding account]` | covered + new |
| Accounts for financial insights | Dag/Yodlee picker | `TestSettingsBackNavigationExtraE2E[...]` | `TestSettingsCoverage[Accounts for financial insights]` | covered + new |
| Plans and fees | Plans and fees | `TestSettingsItemDestinationE2E::test_plans_and_fees...` | `TestSettingsCoverage[Plans and fees]` | covered + new |
| Personal details | Personal details form | `TestSettingsBackNavigationE2E[Personal details]` | `TestSettingsCoverage[Personal details]` | covered + new |
| Security and privacy | Change Password / PIN / Close account | `TestSettingsBackNavigationE2E[Security and privacy]` | `TestSettingsCoverage[Security and privacy]` (no destructive tap) | covered + new |
| Manage notifications | Manage notifications toggles | `TestSettingsBackNavigationExtraE2E[...]` | `TestSettingsCoverage[Manage notifications]` | covered + new |
| Manage Round-Ups | Round-Ups invested / settings | `TestSettingsBackNavigationExtraE2E[...]` | `TestSettingsCoverage[Manage Round-Ups]` | covered + new |
| Refer a friend | Invite friends (code MYE3QG) | `TestSettingsHelpLegalBackNavigationE2E[Refer a friend]` (tolerant) | `TestSettingsCoverage[Refer a friend]` | covered + new |
| Rate Raiz | "How would you rate Raiz?" modal (Not Now) | none | `TestSettingsCoverage[Rate Raiz]` (modal; dismiss via Not Now) | new |
| How to start guide | "What can I invest in?" FAQ | none | `TestSettingsCoverage[How to start guide]` | new (gap) |
| Get support | "Need a hand?" sub-tabs | `TestSettingsHelpLegalBackNavigationE2E[Get support]` (tolerant) | `TestSettingsCoverage[Get support]` | covered + new |
| Our terms | T&C / PDS / TMD list | `TestSettingsHelpLegalBackNavigationE2E[Our terms]` (tolerant) | `TestSettingsCoverage[Our terms]` | covered + new |
| Statements and reports | dated statements, CSV | `TestSettingsHelpLegalBackNavigationE2E[Statements...]` (tolerant) | `TestSettingsCoverage[Statements and reports]` | covered + new |
| Dev Settings | Dev settings (dev build only) | none | `TestSettingsCoverage::test_dev_settings_row_present` (presence only — destructive surface, not entered) | new |
| **Log out** | logs out IMMEDIATELY, no confirm | `TestSettingsScreen::test_log_out_visible_after_scroll` (presence) | `TestSettingsCoverage::test_log_out_row_present_not_tapped` (presence ONLY — SKIPPED from completion, see Safety) | covered + new |

**Total Settings rows: 14 + Dev Settings + Log out — all accounted for.**

---

## 4. Home tabs / modals / cards / onboarding gates / in-screen sub-areas

| Area | How reached | Actual destination | Existing test | NEW test | Status |
|---|---|---|---|---|---|
| Home tab: Today | Home > Today | Home default surface (account cards) | partial | `TestUiPathNavigation::test_home_today_tab_shows_cards` | new |
| Home tab: Past | Home > Past | Investing-journey summary (== history) | none | `TestUiPathNavigation::test_home_past_tab_opens_journey` | new |
| Home tab: Future | Home > Future | Future projection (== future) | none | `TestUiPathNavigation::test_home_future_tab_opens_projection` | new |
| Add funds modal | Home > Add funds | bottom sheet (Lump Sum / Recurring) | `test_investments.py::TestAddFundsModal` | `TestUiPathNavigation::test_add_funds_modal_opens` | covered + new |
| Add funds > Lump Sum | sheet > Lump Sum Investment | Lump Sum keypad | `TestAddFundsModalNavigation::test_lump_sum_option...` | `TestUiPathNavigation::test_add_funds_lump_sum_navigates` | covered + new |
| Add funds > Recurring | sheet > Recurring investments | Recurring screen | `TestAddFundsModalNavigation::test_recurring_option...` | (covered) | covered |
| Home Jars card | Home > Today > Jars card (`tap_jars`) | Customise your Jar | none | `TestUiPathNavigation::test_home_jars_card_opens_jars` | new |
| Home Kids card | Home > Today > Kids card (`tap_kids`) | Raiz Kids consent | none | `TestUiPathNavigation::test_home_kids_card_opens_kids` | new |
| Home Super card | Home > Today > Super card (`tap_superannuation`) | Raiz Super | none | `TestUiPathNavigation::test_home_super_card_opens_super` | new |
| Journey > Transaction history link | history > "Transaction history" | real Transaction History list (only UI path) | none | `TestUiPathNavigation::test_journey_transaction_history_link_reaches_list` | new |
| Future > View my portfolio | future > "View my portfolio" | portfolio surface | none | `TestUiPathNavigation::test_future_view_my_portfolio_navigates` | new |
| Recurring > Add a Raiz Kid | recurring > "Add a Raiz Kid now" | Kids surface | none | `TestUiPathNavigation::test_recurring_add_kid_navigates` | new |
| Recurring > Create your first Jar | recurring > "Create your first Jar" | Jars surface | none | `TestUiPathNavigation::test_recurring_create_jar_navigates` | new |
| Milestone > Fastest ways cross-links | milestone (presence) | Recurring/Deposit/Rewards/Jars rows | none | `TestUiPathNavigation::test_milestone_fastest_ways_crosslinks_present` | new |
| Round-Up Settings > Linked accounts row | round_ups/settings > row | Linked accounts | `test_more_e2e_flows.py::test_round_ups_settings_links...` (presence) | (covered) | covered |
| Round-Ups linked accounts > Add an account | accounts/round_ups (presence) | add-account affordance | `test_round_ups_linked_accounts_listed` | (covered) | covered |
| Funding account > Change | funding_account (presence) | change-funding entry | none | `TestUiPathNavigation::test_funding_account_change_present` | new |
| Kids consent legal-doc links | raiz_kids (presence) | Privacy/PDS/TMD links | none | `TestUiPathNavigation::test_kids_consent_legal_docs_present` | new |
| Plans PDS/AID links | plans (presence) | PDS/AID disclosure | none | `TestUiPathNavigation::test_plans_pds_aid_present` | new |
| Super Contact Us | raiz_super (presence) | Contact US / phone | none | `TestUiPathNavigation::test_super_contact_us_present` | new |
| Jars empty-state create form | jars | Customise-your-Jar (NAME_FIELD + Create Jar) | `test_jars.py::test_empty_state_shows_create_screen` | (covered) | covered |
| Kids consent gate | raiz_kids | consent gate ("I consent") | `test_kids.py::test_empty_state_shows_consent_or_welcome` | (covered) | covered |
| My Finance insights setup gate | finance | "0 of 3 completed" card | `test_more_e2e_flows.py::test_financial_insights_setup_card_present` | (covered) | covered |
| Rewards Earn↔Track tabs | rewards | tab content swaps | `test_rewards.py::TestRewardsTabContentSwitch` | (covered) | covered |
| Reward detail | rewards > first card | detail screen | `test_rewards.py::TestRewardsDetailNavigation` | (covered) | covered |

---

## Coverage gaps closed

These had NO navigation test (or only a loose `contains()` / `is_loaded()` probe) before this initiative; each is now covered in `tests/test_navigation_coverage.py`:

1. **`raiz://future`** — had no test anywhere (load + launcher-exit back).
2. **`raiz://deposit`** — no named direct-nav load test (only used via fixture); now load + back.
3. **Launcher-exit back-stack half** (`home`, `performance/day`, `performance/month`, `history`, `future`) — entirely uncovered; existing back E2E only asserted the return-to-Home half.
4. **Return-to-Home back-stack** for `invest`, `withdraw`, `recurring`, `dividends`, `portfolio`, `portfolio/custom`, `rewards`, `round_ups*`, `funding_account`, `milestone`, `achievements`, `plans`, `profile/*`, `fees`, `offsetters`, `blog`, `invite_friends`, `notifications_settings`, the Dag pickers — none had a deep-link back test.
5. **Real-destination assertions** replacing loose matchers for the Dag-picker convergence, rewards_linked_accounts/accounts_rewards, profile forms, milestone progress, achievements grid, plans tiers, funding verified state, blog articles, invite code.
6. **Home cards** (`tap_jars`/`tap_kids`/`tap_superannuation`) — page-object methods existed but no test drove them.
7. **Journey-summary "Transaction history" link** — the only UI path to the real txn list (other than the Invest row / deep link).
8. **Cross-area discovered links** — Future→portfolio, Recurring→Kids/Jars, Milestone fastest-ways.
9. **Settings rows** Rate Raiz, How to start guide, Dev Settings (presence) — never tapped before.
10. **Drawer per-item coverage** consolidated into one parametrized class over all 13 items.

## Documented mismatches / findings (encoded as xfails or asserted-as-real)

Encoded in `TestNavigationMismatches` (all `xfail(strict=False)` so the suite stays green while keeping the registry defect visible), plus real-destination assertions in the load classes:

1. **`raiz://performance/day` → Home** (not day-performance). `test_performance_day_routes_home` xfails on the intended Performance destination; back-stack treats it as a Home-tab surface (exits launcher).
2. **`raiz://performance/month` → Home** (not month-performance). `test_performance_month_routes_home`, same treatment.
3. **`raiz://rewards_auto` → Rewards Earn alias** (no distinct auto-rewards screen). `test_rewards_auto_is_earn_alias` xfails on the intended dedicated screen; real Earn destination asserted via back-stack param.
4. **3-way Dag-picker convergence**: `rewards_linked_accounts`, `accounts/rewards`, `accounts/financial_insights` all land on the same Yodlee/Dag account-consent picker (`accounts/rewards` is a byte-duplicate of `rewards_linked_accounts`). Asserted as the real (convergent) destination in `TestDeepLinkLoadsRealDestination`; no xfail needed (working as built).
5. **`raiz://spending_account` → Linked accounts for Round-Ups** (no distinct spending screen). `test_spending_account_intended_xfail` xfails on the intended "Spending account" title; real destination asserted by load case.
6. **`raiz://raiz_super/account_info` → Super error/contact fallback** (no account-info screen). `test_super_account_info_intended_xfail`.
7. **`raiz://raiz_super/important_documents` → Super error/contact fallback** (no docs screen). `test_super_important_docs_intended_xfail`.
8. **`raiz://raiz_kids_2` duplicates `raiz_kids`** — same consent gate; documented as duplicate (asserted as real Kids surface).
9. **Drawer nested-item Back quirk**: maps disagree — bucket-A/B saw uniform Back→Home; bucket-C (drawer map) saw nested drawer items (Main portfolio, Jars, …) reopen the **drawer** on Back while top-level surfaces (Rewards/Surveys/Super) return Home. `test_nested_drawer_back_returns_to_drawer` xfails on the drawer-reopen expectation, documenting the discrepancy vs the existing `TestDrawerBackNavigationE2E` Back→Home assumption.
10. **`raiz://dividends` flaky cold-load** — "Oops!"→PIN on first hit. Not a routing mismatch; handled with a dismiss-and-retry guard in the load case (not an xfail).
11. **Settings "Log out" has NO confirmation dialog** (map 5558 #2) — committing it logs out the shared account. The `settings_page.logout_prompt_shown()/cancel_logout()` assumption of a cancellable dialog is wrong for this build. NOT tested to completion here; the row is asserted present/reachable only (see Safety).

## Safety / deliberately skipped

- **Log out**: presence/reachability only. Never tapped to completion — would log out the shared account with no confirmation. (`TestSettingsCoverage::test_log_out_row_present_not_tapped`.)
- **Close account** (under Security & privacy) and **Dev Settings** actions (Clear Preference/Data Store): navigate to / assert the parent row only; never invoked.
- No money movement (no Invest/Withdraw/Save committed), no reward redemption ("Shop online here" not tapped), no jar/kid creation (no Create Jar / I consent), no bank linking. `RUN_DESTRUCTIVE` is never set.
