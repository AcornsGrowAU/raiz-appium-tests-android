# Bucket B — UI-PATH & EDGE Navigation Cases (emulator-5556)

**Analyst:** ANALYST-2 (UI-path / edge-navigation angle) — Accounts/Growth bucket (Device B).
**Scope:** Every way of REACHING bucket-B areas *through the UI* (drawer, Home cards/tabs/Add-funds, in-screen cross-links, onboarding/empty-state gates, cross-area jumps, state-preservation, drawer open/close). Complements Analyst-1's deep-link cases.
**Bucket-B areas:** jars, raiz_kids, raiz_super, round_ups (+settings/accounts), funding_account, spending_account, milestone, achievements, plans.
**Account state (from `docs/nav_map_5556.md`):** logged in (PIN 0000); NO active jars, NO kids, UNFUNDED super, Round-Ups LINKED ("Dag Site (US)" Yodlee sandbox), portfolio funded (~$1.5k). Back button is **uniform → Home** for every area (nav_map finding #8).
**Safety:** No logout, no jar/kid creation, no money movement, no real reward redemption. STOP before completing any onboarding/consent/Save action.

## Key references used
- Drawer items + scroll helpers: `pages/nav_drawer.py` (NAV_JARS, NAV_KIDS, NAV_SUPER, NAV_ROUND_UPS, NAV_RECURRING, NAV_LUMP_SUM, NAV_MY_FINANCE, NAV_MY_ACHIEVEMENTS, NAV_OFFSETTERS; `go_*` methods).
- Home cards/tabs/Add-funds: `pages/home_page.py` (JARS_CARD, KIDS_CARD, SUPERANNUATION_CARD, TAB_PAST/TODAY/FUTURE, ADD_FUNDS_BUTTON, `tap_jars/tap_kids/tap_superannuation`, `jars_card_is_empty/kids_card_is_empty`).
- Page objects: `pages/jars_page.py`, `pages/kids_page.py`, `pages/super_page.py`, `pages/round_ups_page.py`, `pages/my_finance_page.py`, `pages/portfolio_allocation_page.py`. (NOTE: there is **no** milestone/achievements/plans/funding page object — deep-link tests use inline `contains()` matchers in `tests/test_navigation.py`.)
- Existing coverage: `tests/test_navigation.py` (drawer + deep-link + RAIZ-9994 back-stack classes), `tests/test_jars.py`, `tests/test_kids.py`, `tests/test_more_e2e_flows.py`.
- Map / mismatches: `docs/nav_map_5556.md` (spending_account==Round-Ups linked-accounts; super sub-routes fall back to base; raiz_kids_2==raiz_kids; jars skips list; achievements badges dead-end; uniform back).

## Legend
- **COVERED:** yes (exact existing test cited) / partial (related test, different angle) / no (gap).
- **Priority:** P1 = primary UI entry path for a bucket-B area, must work; P2 = secondary path / in-screen cross-link / state preservation; P3 = duplicate/dead-end/low-value edge.

---

## A. Nav drawer → bucket-B destination (forward + back)

| # | Proposed test name | Area | UI path (taps) | Assertion (destination + key element) | Back-stack assertion | COVERED? | Pri | Notes |
|---|--------------------|------|----------------|----------------------------------------|----------------------|----------|-----|-------|
| A1 | test_drawer_jars_loads | jars | Home → hamburger → `go_jars` | JarsPage.is_loaded (Raiz Jars title OR Customise-your-Jar create form) | — | yes — `test_navigation.py::TestNavDrawer::test_drawer_navigates_to_jars` | P1 | Empty acct lands on create form (map #7). |
| A2 | test_drawer_kids_loads | raiz_kids | Home → hamburger → `go_kids` | KidsPage.is_loaded (Raiz Kids title OR consent/welcome gate) | — | yes — `test_drawer_navigates_to_kids` | P1 | Empty acct → consent gate. |
| A3 | test_drawer_super_loads | raiz_super | Home → hamburger → scroll → `go_super` | SuperPage.is_loaded (ANY_SUPER_SURFACE) | — | yes — `test_drawer_navigates_to_super` | P1 | Stateful onboarding surface. |
| A4 | test_drawer_round_ups_loads | round_ups | Home → hamburger → scroll → `go_round_ups` | RoundUpsPage.is_loaded | — | yes — `test_drawer_navigates_to_round_ups` | P1 | Linked dashboard or intro. |
| A5 | test_drawer_recurring_loads | round_ups-adjacent (recurring) | Home → hamburger → scroll → `go_recurring` | RecurringPage.is_loaded | — | yes — `test_drawer_navigates_to_recurring` | P1 | Drawer "Recurring investments". |
| A6 | test_drawer_lump_sum_loads | (invest pref) | Home → hamburger → scroll → `go_lump_sum` | Lump Sum flow loaded | — | yes — `test_drawer_navigates_to_lump_sum` | P2 | Adjacent to bucket B. |
| A7 | test_drawer_my_finance_loads | my_finance | Home → hamburger → scroll → `go_my_finance` | MyFinancePage.is_loaded (My Finance title) | — | yes — `test_drawer_navigates_to_my_finance` | P1 | Net-worth surface (spending/super totals). |
| A8 | test_drawer_achievements_loads | achievements | Home → hamburger → scroll → `go_my_achievements` | "Achievements" title visible | — | yes — `test_drawer_navigates_to_achievements` | P1 | — |
| A9 | **test_drawer_jars_back_returns_home** | jars | drawer → `go_jars` → `driver.back()` | left Home on forward; HomePage.is_loaded after back | back → Home | yes — `TestDrawerBackNavigationE2E[Jars]` | P1 | Parametrized RAIZ-9994 class. |
| A10 | **test_drawer_kids_back_returns_home** | raiz_kids | drawer → `go_kids` → back | left Home; HomePage.is_loaded | back → Home | yes — `TestDrawerBackNavigationE2E[Kids]` | P1 | — |
| A11 | **test_drawer_super_back_returns_home** | raiz_super | drawer → `go_super` → back | SuperPage left Home; HomePage.is_loaded | back → Home | **no** | P2 | Super NOT in `TestDrawerBackNavigationE2E.DESTINATIONS` list (only main_portfolio/jars/kids/rewards/my_finance). Gap. |
| A12 | **test_drawer_round_ups_back_returns_home** | round_ups | drawer → `go_round_ups` → back | left Home; HomePage.is_loaded | back → Home | **no** | P2 | Round-Ups not in the parametrized back list. Gap. |
| A13 | **test_drawer_recurring_back_returns_home** | recurring | drawer → `go_recurring` → back | left Home; HomePage.is_loaded | back → Home | **no** | P2 | Gap. |
| A14 | **test_drawer_achievements_back_returns_home** | achievements | drawer → `go_my_achievements` → back | left Home; HomePage.is_loaded | back → Home | **no** | P2 | Gap. |
| A15 | test_drawer_my_finance_back_returns_home | my_finance | drawer → `go_my_finance` → back | left Home; HomePage.is_loaded | back → Home | yes — `TestDrawerBackNavigationE2E[My Finance]` | P1 | — |
| A16 | **test_drawer_super_below_fold_requires_scroll** | raiz_super | drawer → assert Super NOT initially present → `scroll_to_text("Super")` → present | NAV_SUPER visible only after scroll | drawer stays open | partial — `go_super` scrolls implicitly; no test asserts the below-fold gate | P3 | Validates `scroll_to_text` in `go_super`. |
| A17 | **test_drawer_round_ups_below_fold_requires_scroll** | round_ups | drawer → `has_item(NAV_ROUND_UPS)` after scroll | NAV_ROUND_UPS reachable via `has_item` | drawer stays open | **no** | P3 | Uses `nav_drawer.has_item` scroll-safe probe. |

## B. Home account cards / Add-funds / Past·Today·Future tabs → bucket-B

| # | Proposed test name | Area | UI path (taps) | Assertion (destination + key element) | Back-stack assertion | COVERED? | Pri | Notes |
|---|--------------------|------|----------------|----------------------------------------|----------------------|----------|-----|-------|
| B1 | **test_home_jars_card_opens_jars** | jars | Home → Today tab → scroll to Jars card → `tap_jars` | JarsPage.is_loaded (create form for empty acct) | back → Home | **no** | P1 | `tap_jars` exists in page object; no test drives it. Card shows only "Add" (empty). |
| B2 | **test_home_kids_card_opens_kids** | raiz_kids | Home → Today → scroll → `tap_kids` | KidsPage.is_loaded (consent gate) | back → Home | **no** | P1 | `tap_kids` exists; untested. |
| B3 | **test_home_superannuation_card_opens_super** | raiz_super | Home → Today → scroll → `tap_superannuation` | SuperPage.is_loaded | back → Home | **no** | P1 | `tap_superannuation` exists; untested. |
| B4 | **test_home_jars_card_empty_shows_add_affordance** | jars | Home → Today → `jars_card_is_empty()` | card text contains "Add" (no jar balance) | n/a | **no** | P2 | Empty-state assertion on the card itself (`home_page.jars_card_is_empty`). |
| B5 | **test_home_kids_card_empty_shows_add_affordance** | raiz_kids | Home → Today → `kids_card_is_empty()` | card text contains "Add" | n/a | **no** | P2 | `home_page.kids_card_is_empty`. |
| B6 | **test_home_add_funds_opens_deposit_surface** | (funding-adjacent) | Home → `tap_add_funds` | Deposit/Add-funds surface loads (amount entry / funding source) | back → Home | **no** | P2 | `ADD_FUNDS_BUTTON` + `tap_add_funds` exist; untested. STOP before confirming any deposit. |
| B7 | **test_home_today_tab_shows_account_cards** | jars/kids/super (cards) | Home → `tap_tab_today` | Total-investments section + Main Portfolio/Jars/Kids/Superannuation cards present | stays on Home | **no** | P2 | Cards only exist on the Today tab (per `_scroll_portfolio_cards_into_view`). |
| B8 | **test_home_past_tab_hides_account_cards** | (negative card-gate) | Home → `tap_tab_past` | account cards NOT present (Past view differs) | `tap_tab_today` restores cards | **no** | P3 | Confirms tab gating noted in `_tap_card`. |
| B9 | **test_home_future_tab_loads** | (Future tab) | Home → `tap_tab_future` | Future view loads, no card crash; `tap_tab_today` returns | tab switch reversible | **no** | P3 | Edge: tabs change card availability. |
| B10 | **test_home_card_tap_then_today_tab_restores_cards** | jars (state) | Home → `tap_jars` → back → ensure Today re-selected → cards re-render | after returning, Jars card present again on Today | back → Home, cards restored | **no** | P2 | State-preservation: `_tap_card` re-selects Today defensively. |

## C. In-screen cross-links discovered in the map (tap → navigates; back returns)

| # | Proposed test name | Area | UI path (taps) | Assertion (destination + key element) | Back-stack assertion | COVERED? | Pri | Notes |
|---|--------------------|------|----------------|----------------------------------------|----------------------|----------|-----|-------|
| C1 | **test_milestone_recurring_link_opens_recurring** | milestone → recurring | deep-link/drawer to Milestone → tap "Set recurring investment" (Fastest ways to get there) | Recurring setup surface loads | back → Milestone | **no** | P1 | Map line 25/45 cross-link. No milestone page object — use `contains('Recurring')`. |
| C2 | **test_milestone_deposit_link_opens_deposit** | milestone → deposit | Milestone → tap "Make a lump-sum deposit" | Deposit/Add-funds surface loads | back → Milestone | **no** | P2 | STOP before any money movement. |
| C3 | **test_milestone_rewards_link_opens_rewards** | milestone → rewards | Milestone → tap "Explore Raiz Rewards" | RewardsPage loads | back → Milestone | **no** | P2 | Cross-area jump out of bucket B (verify, then back). |
| C4 | **test_milestone_open_new_jar_link_opens_jars** | milestone → jars | Milestone → tap "Open a new Jar" | JarsPage.is_loaded (create form) | back → Milestone | **no** | P1 | Bucket-B cross-link; do NOT create a jar. |
| C5 | **test_milestone_up_next_edit_present** | milestone | Milestone → assert "Up next" / "Edit" present (do not tap Edit) | "Up next" + progress ($x / $y) rendered; Edit visible | n/a | partial — `test_deep_link_milestone` only asserts title | P2 | Edit could mutate the milestone target — assert presence only, don't open. |
| C6 | **test_round_ups_settings_links_to_linked_accounts** | round_ups settings → accounts | Round-Up settings → scroll → tap "Linked accounts for Round-Ups" row | Linked-accounts screen (ACCOUNTS_TITLE) loads | back → settings | yes — `test_more_e2e_flows.py::test_round_ups_settings_links_to_linked_accounts` (presence) / partial on nav | P1 | Existing test asserts the row is PRESENT but does not tap-and-navigate. Add the tap+destination+back. |
| C7 | **test_round_ups_dashboard_to_settings_link** | round_ups → settings | Round-Ups dashboard → tap settings entry → Round-Up settings loads | SETTINGS_TITLE / MINIMUM_AMOUNT_HEADER visible | back → dashboard | **no** | P2 | Map line 20/43: settings reached from the Round-Ups empty/dashboard screen. |
| C8 | **test_linked_accounts_add_account_opens_add_flow** | accounts/round_ups | Linked-accounts → tap "Add an account" → assert Add-account flow opens | add-account / institution-search surface loads | back → linked-accounts | partial — `test_round_ups_linked_accounts_listed` asserts ADD_ACCOUNT present, not tapped | P2 | STOP before linking a bank (no creds). |
| C9 | **test_linked_accounts_manage_consent_opens_consent** | accounts/round_ups | Linked-accounts → tap "Manage consent and data sharing" → consent/data-sharing screen | consent management surface loads | back → linked-accounts | partial — MANAGE_CONSENT presence only | P2 | Read-only inspection; do not revoke consent. |
| C10 | **test_funding_account_change_link_opens_change** | funding_account | Funding Account → tap "Change" → Change-funding-account surface | change-funding surface loads (account list / picker) | back → Funding Account | **no** | P2 | Map line 23/44. STOP before changing funding source. No funding page object. |
| C11 | **test_super_contact_us_link_present** | raiz_super → Contact Us | Raiz Super (error/contact state) → assert "Contact US" / email / phone 1300 75 47 48 present (do not tap) | Contact US + email + phone rendered | n/a | **no** | P2 | Map line 17/47. On unfunded acct this is the only forward affordance; tapping launches mail/dialer (external) — assert presence only. |
| C12 | **test_super_contact_email_intent_optional** | raiz_super → Contact Us | Raiz Super → tap email → external mail intent (then back to app) | leaving app to mail intent OR no crash; back returns to Super | back → Super | **no** | P3 | EDGE: external-app intent. Optional/risky (launches another app) — keep P3, presence-check (C11) preferred. |
| C13 | **test_plans_pds_aid_link_present** | plans → legal docs | deep-link/Home to Plans → assert "read PDS and AID" link present (do not open) | PDS/AID link rendered on Pricing plans | n/a | partial — `test_deep_link_plans` asserts title only | P2 | Legal doc link (map line 27). Opening may launch a webview/PDF; assert presence. |
| C14 | **test_kids_consent_legal_doc_links_present** | raiz_kids → legal docs | Kids consent gate → assert Privacy Policy / T&Cs / PDS/AID / Plus Portfolio Guide / TMD link texts present (do not tap) | the 5 legal-doc link labels rendered on consent screen | n/a | **no** | P2 | Map line 15/48. Tapping opens external docs — presence only. |
| C15 | **test_round_ups_manual_tap_to_invest_present** | round_ups | Round-Ups dashboard → assert Manual Round-Ups "tap to invest" affordance present (do not invest) | MANUAL_ROUND_UPS + "tap to invest" rendered | n/a | partial — `test_round_ups_dashboard_shows_auto_and_manual` asserts label | P3 | Tapping "tap to invest" moves money — presence only. |

## D. Onboarding / empty-state gates AS navigation (reach the gate, STOP)

| # | Proposed test name | Area | UI path (taps) | Assertion (destination + key element) | Back-stack assertion | COVERED? | Pri | Notes |
|---|--------------------|------|----------------|----------------------------------------|----------------------|----------|-----|-------|
| D1 | test_jars_empty_state_opens_create_form | jars | drawer/card → Jars (empty) | is_create_screen: NAME_FIELD + CREATE_JAR_BUTTON present | back → Home | yes — `test_jars.py::test_empty_state_shows_create_screen` | P1 | Empty-state IS the navigation destination. Do NOT tap Create Jar. |
| D2 | test_kids_consent_gate_is_entry | raiz_kids | drawer/card → Kids (empty) | is_consent_screen OR is_welcome_screen ("I consent" body) | back → Home | yes — `test_kids.py::test_empty_state_shows_consent_or_welcome` | P1 | STOP before tapping "I consent" (creates onboarding state). |
| D3 | **test_kids_consent_i_consent_button_present_not_tapped** | raiz_kids | Kids consent gate → assert I_CONSENT_BUTTON present | "I consent" button rendered; NOT tapped | n/a | **no** | P2 | Validates the only forward control without advancing (map UI-flow line 34). |
| D4 | **test_super_unfunded_lands_on_contact_state** | raiz_super | drawer/card → Super (unfunded) | "unable to search for your existing Super funds" / Contact US state OR any super surface | back → Home | partial — `test_super_surface_loads` accepts any surface | P2 | Empty/error state IS the destination for unfunded acct (map #4). Pin the contact-state copy. |
| D5 | **test_super_insurance_interstitial_when_shown** | raiz_super | Super → if insurance step: assert Death&TPD consent + "Not now" | INSURANCE_CONSENT_TEXT + NOT_NOW present | n/a | yes — `test_more_e2e_flows.py::test_insurance_opt_in_discloses_consent_when_shown` | P2 | STOP — never tap "Apply for insurance"/"Not now"/"Finish". |
| D6 | **test_round_ups_empty_state_no_spending_copy** | round_ups | Round-Ups dashboard (no activity) | NO_SPENDING ("don't have any spending") empty-state present | back → Home | partial — `has_round_ups_data` keys off it; no direct empty-state nav test | P3 | Empty-state copy as the reached destination. |
| D7 | **test_my_finance_insights_setup_gate_present** | my_finance | drawer → My Finance | SETUP_INSIGHTS_HEADER + "0 of 3 completed" + a setup row | back → Home | yes — `test_more_e2e_flows.py::test_financial_insights_setup_card_present` | P2 | Onboarding gate within My Finance. |
| D8 | **test_jars_create_form_validation_gate** | jars | Jars create form → tap Create Jar with empty name → "Oops!" modal → dismiss | OOPS_TITLE shown; dismiss returns to create form | dismiss → create form (NOT Home) | **no** | P3 | Map UI-flow line 33. SAFE (no jar created). Uses `is_oops_shown`/`dismiss_oops`. |

## E. EDGE: cross-area jumps, state preservation, drawer open/close

| # | Proposed test name | Area | UI path (taps) | Assertion (destination + key element) | Back-stack assertion | COVERED? | Pri | Notes |
|---|--------------------|------|----------------|----------------------------------------|----------------------|----------|-----|-------|
| E1 | **test_deep_link_jars_while_on_round_ups** | jars (mid-flow) | Round-Ups loaded → deep-link `raiz://jars` (no return Home first) | JarsPage.is_loaded directly from another bucket-B screen | back → Home (uniform, #8) | **no** | P1 | EDGE: deep-link into a bucket-B area while already on another screen. Complements Analyst-1 (who starts from Home). |
| E2 | **test_deep_link_super_while_on_my_finance** | raiz_super (mid-flow) | My Finance loaded → deep-link `raiz://raiz_super` | SuperPage.is_loaded | back → Home | **no** | P2 | Cross-area jump without first popping to Home. |
| E3 | **test_drawer_jump_jars_to_super_via_home** | jars→super | drawer→Jars → back→Home → drawer→Super | SuperPage.is_loaded after the second drawer hop | back → Home | **no** | P2 | EDGE: sequential drawer jumps between two bucket-B areas. |
| E4 | **test_round_ups_navigate_away_and_return_state** | round_ups (state) | Round-Ups dashboard → note tab/total → deep-link Home → back to Round-Ups | dashboard reloads cleanly (RoundUpsPage.is_loaded; invested total well-formed) | back → Home | **no** | P2 | State-preservation/re-entry. App is single RN host — re-entry must re-render, not crash. |
| E5 | **test_my_finance_navigate_to_super_and_back** | my_finance↔super | My Finance → (cross-screen reconcile) open Super → back/Home → My Finance reloads | both surfaces load on the round trip | back → Home each hop | yes — `test_more_e2e_flows.py::test_super_component_reconciles_with_super_surface` | P2 | Existing reconcile test already does the My-Finance→Super round trip. |
| E6 | **test_drawer_reopens_after_close** | (drawer) | Home → drawer → close (back) → Home → hamburger → drawer open again | drawer reopens cleanly; ends on Home | open→close→open stable | yes — `test_navigation.py::TestDrawerOpenCloseRobustness::test_drawer_reopens_after_close` | P1 | — |
| E7 | **test_drawer_closes_on_back_to_home** | (drawer) | Home → drawer → `close()` (back) | HomePage.is_loaded | drawer→Home | yes — `TestNavDrawer::test_drawer_closes_on_back` | P1 | — |
| E8 | **test_drawer_home_item_returns_home** | (drawer) | Home → drawer → `go_home` | HomePage.is_loaded | drawer "Home"→Home | yes — `TestDrawerOpenCloseRobustness::test_drawer_home_item_returns_home` | P2 | — |
| E9 | **test_drawer_open_from_round_ups_not_only_home** | (drawer edge) | Round-Ups loaded → open hamburger (if present) OR back→Home→hamburger | drawer opens; `go_jars` reachable | back → Home | **no** | P3 | EDGE: drawer is opened from Home only in fixtures; confirm reachability after a deep-linked bucket-B screen. |
| E10 | **test_spending_account_lands_on_round_ups_linked_accounts** | spending_account | drawer/deep-link `raiz://spending_account` | Linked-accounts-for-Round-Ups screen (ACCOUNTS_TITLE) — NOT a distinct spending screen | back → Home | yes — `test_navigation.py::test_deep_link_spending_account` | P2 | Mismatch #1: documents the alias. (No drawer item for spending_account — deep-link only.) |
| E11 | **test_raiz_kids_2_duplicates_consent_gate** | raiz_kids_2 | deep-link `raiz://raiz_kids_2` | same consent/welcome gate as raiz_kids (KidsPage.is_loaded) | back → Home | yes — `test_navigation.py::test_deep_link_raiz_kids_2` | P3 | Mismatch #5 duplicate. |
| E12 | **test_super_account_info_falls_back_to_super** | raiz_super sub-route | deep-link `raiz://raiz_super/account_info` | SuperPage.is_loaded (falls back to base super surface) | back → Home | yes — `test_navigation.py::test_deep_link_super_account_info` | P3 | Mismatch #2. |
| E13 | **test_super_important_docs_falls_back_to_super** | raiz_super sub-route | deep-link `raiz://raiz_super/important_documents` | SuperPage.is_loaded (fallback) | back → Home | yes — `test_navigation.py::test_deep_link_super_important_documents` | P3 | Mismatch #3. |
| E14 | **test_achievements_badge_is_dead_end** | achievements | Achievements grid → tap a badge ("Goal Setter") → view stays on grid | still on Achievements grid (no detail screen opens) | n/a | **no** | P3 | Mismatch #6: badges non-tappable for no-progress acct. Documents the dead-end as expected behaviour. |

---

## Coverage tally
- **Total cases:** 64 (A:17, B:10, C:15, D:8, E:14).
- **Gaps (COVERED = no):** 33 — A11,A12,A13,A14,A17; B1,B2,B3,B4,B5,B6,B7,B8,B9,B10; C1,C2,C3,C4,C7,C10,C11,C12,C14; D3,D4,D6,D8; E1,E2,E3,E4,E9,E14.
- **Partial (related test exists but different angle — strengthen):** 8 — A16, C5, C6, C8, C9, C13, C15, D6.
- **Fully covered (cite-and-skip):** 23 — A1–A8,A9,A10,A15; D1,D2,D5,D7; E5,E6,E7,E8,E10,E11,E12,E13.
- **P1 cases:** 20 — A1–A5,A7,A8,A9,A10,A15,B1,B2,B3,C1,C4,C6,D1,D2,E1,E6,E7.
