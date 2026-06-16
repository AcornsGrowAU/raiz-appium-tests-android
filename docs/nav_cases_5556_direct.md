# Direct-Navigation Test Cases — Bucket B (Accounts/Growth, emulator-5556)

**Author:** ANALYST-1 (direct-navigation angle) — pure analysis, no device touched.
**Angle:** deep-link loads + back-stack correctness. Every bucket-B area and discovered sub-area gets a direct-navigation case.
**Authoritative source:** `docs/nav_map_5556.md` (LIVE crawl, build 2.39.1d/3223). Assertions below target the **ACTUAL** destination from that map, not the nominal/intended one.
**Account state (per map):** logged in (PIN 0000); NO active jars, NO kids, UNFUNDED super; Round-Ups linked (Dag Site sandbox); portfolio funded (~$1.5k).

## Conventions
- **Deep link** uses the `utils.deep_links.DeepLinks` constant.
- **Destination assertion** references real `is_loaded()` / locator signals from the page objects (or the `BasePage` `contains()` title matcher convention already used in `tests/test_navigation.py` where no dedicated page object exists — milestone/achievements/plans/funding have no page object).
- **Back-stack assertion** encodes the map's finding #8: `driver.back()` from every deep-linked area returns to **Home** (RAIZ-9994 back-stack class — assert `HomePage.is_loaded()`, recover to Home if it pops an intermediate first, as `TestDeepLinkBackNavigationE2E` already does).
- **Priority:** P1 = core area entry + its back-stack; P2 = sub-area / settings depth; P3 = duplicate-route / dead-end / cross-link documentation.
- **Mismatch findings** are asserted as the REAL destination and flagged; the 3 hard route mismatches (`spending_account`, `raiz_super/account_info`, `raiz_super/important_documents`) are recommended `xfail(strict=False)` on the *intended* destination so the registry defect stays visible, mirroring the existing `performance/day|month` xfail pattern.

---

## A. Deep-link load cases (CORRECT-screen assertions)

| Proposed test name | Area | Deep link | Expected ACTUAL destination + assertion | Back-stack assertion | Covered already? | Priority | Notes (mismatch/finding) |
|---|---|---|---|---|---|---|---|
| `test_deep_link_jars_opens_create_form` | jars | `DeepLinks.JARS` | **Customise your Jar** create form (empty state). Assert `JarsPage.is_create_screen()` AND `JarsPage.is_present_now(NAME_FIELD)` AND `is_present_now(CREATE_JAR_BUTTON)`. NOT a jars list. | back → Home (`HomePage.is_loaded()`) | partial — `test_navigation.py::test_deep_link_jars` asserts only generic `JarsPage.is_loaded()` (passes on either state); `test_jars.py::test_empty_state_shows_create_screen` asserts the create form but is data-adaptive/skips. No combined load+empty-state assertion in the nav suite. | P1 | Finding #7: with no jars the deep link SKIPS the Jars list and drops straight into the create form. Assert the create form as the real empty-state destination. |
| `test_deep_link_raiz_kids_opens_consent_gate` | raiz_kids | `DeepLinks.RAIZ_KIDS` | **Raiz Kids** identity-consent gate (empty state). Assert `KidsPage.is_consent_screen()` (CONSENT_PROMPT "I consent" visible). NOT a kids list. | back → Home | partial — `test_navigation.py::test_deep_link_raiz_kids` asserts only `KidsPage.is_loaded()` (any entry surface). Consent-gate specificity is in `test_kids.py::test_empty_state_shows_consent_or_welcome` (data-adaptive). | P1 | Map: consent gate IS the real onboarding destination for an account with no kids. "I consent" is the only forward control. |
| `test_deep_link_raiz_kids_2_duplicates_consent_gate` | raiz_kids_2 | `DeepLinks.RAIZ_KIDS_2` | Same **Raiz Kids** consent gate as `raiz_kids`. Assert `KidsPage.is_consent_screen()` (identical surface). | back → Home | partial — `test_navigation.py::test_deep_link_raiz_kids_2` asserts only `KidsPage.is_loaded()`; does not assert it equals the `raiz_kids` consent gate. | P3 | Finding #5: `raiz_kids_2` is NOT a distinct screen — resolves to the same consent gate. Document as duplicate route. |
| `test_deep_link_raiz_super_opens_fund_search_error` | raiz_super | `DeepLinks.RAIZ_SUPER` | **Raiz Invest Super** super-fund-search ERROR/contact state (unfunded). Assert `SuperPage.is_loaded()` AND presence of the error/contact copy `//*[contains(@text,'existing Super funds')]` OR Contact US (`//*[contains(@text,'Contact')]`). | back → Home | partial — `test_navigation.py::test_deep_link_raiz_super` + `test_more_e2e_flows.py::test_super_surface_loads` assert generic `SuperPage.is_loaded()`, which also matches insurance/ready interstitials. No assertion pinning the fund-search error/contact dead-end. | P1 | Finding #4: for an unfunded account the super entry is an effective dead-end contact screen ("We were unable to search for your existing Super funds"), not a clean onboarding intro. Assert the error/contact state. |
| `test_deep_link_super_account_info_falls_back_to_super_error` | raiz_super/account_info | `DeepLinks.RAIZ_SUPER_ACCOUNT_INFO` | Falls back to the **base Raiz Invest Super error/contact** screen — NOT an account-info screen. Assert `SuperPage.is_loaded()` (same surface as base). | back → Home | partial — `test_navigation.py::test_deep_link_super_account_info` + `test_more_e2e_flows.py::test_super_account_info_screen_loads` assert `is_account_info_loaded()`, which falls through to `is_loaded()` — they tolerate the fallback but do NOT flag the mismatch. | P3 | **MISMATCH #2 (hard route).** Recommend `xfail(strict=False)` on the INTENDED account-info destination (`ACCOUNT_INFO_TITLE`/USI/Member#), asserting the REAL fallback. Mirrors the `performance/day` xfail convention. |
| `test_deep_link_super_important_docs_falls_back_to_super_error` | raiz_super/important_documents | `DeepLinks.RAIZ_SUPER_IMPORTANT_DOCS` | Falls back to the **base Raiz Invest Super error/contact** screen — NOT an important-documents list. Assert `SuperPage.is_loaded()`. | back → Home | partial — `test_navigation.py::test_deep_link_super_important_documents` + `test_more_e2e_flows.py::test_super_important_documents_screen_loads` assert `is_docs_loaded()` which falls through to `is_loaded()`; mismatch not flagged. | P3 | **MISMATCH #3 (hard route).** Recommend `xfail(strict=False)` on the INTENDED docs destination (`DOCS_TITLE`/PDS/TMD), asserting the REAL fallback. |
| `test_deep_link_round_ups_opens_dashboard_empty` | round_ups | `DeepLinks.ROUND_UPS` | **Round-Ups** dashboard, empty activity state. Assert `RoundUpsPage.is_loaded()` AND (`is_linked()` showing AUTO/MANUAL Round-Ups OR `NO_SPENDING` "You don't have any spending yet." empty line). | back → Home | yes (load) — `test_navigation.py::test_deep_link_round_ups`. Back-stack to Home NOT covered. | P1 | Map: empty/activity state is the real destination (Round-Ups invested $0, Auto $5.00-until-$5, Manual "tap to invest", tabs All/Invested/Available). |
| `test_deep_link_round_ups_settings_opens_settings` | round_ups/settings | `DeepLinks.ROUND_UPS_SETTINGS` | **Round-Up settings**. Assert `is_visible(SETTINGS_TITLE)` OR `is_present_now(MINIMUM_AMOUNT_HEADER)`. | back → Home | yes (load) — `test_navigation.py::test_deep_link_round_ups_settings`. Back-stack to Home NOT covered. | P1 | RAIZ-9970 area. Settings is a real, distinct screen. |
| `test_deep_link_round_ups_accounts_opens_linked_accounts` | accounts/round_ups | `DeepLinks.ROUND_UPS_ACCOUNTS` | **Linked accounts for Round-Ups**. Assert `is_visible(ACCOUNTS_TITLE)` AND `is_present_now(LINKED_INSTITUTION)` (Dag Site). | back → Home | yes (load) — `test_navigation.py::test_deep_link_round_ups_accounts`. Back-stack to Home NOT covered. | P1 | Real destination; also where `spending_account` (mis)lands — see below. |
| `test_deep_link_funding_account_opens_funding` | funding_account | `DeepLinks.FUNDING_ACCOUNT` | **Funding Account**. Assert `BasePage.is_visible(//*[contains(@text,'Funding') or contains(@text,'funding')])` AND account-verified copy `//*[contains(@text,'funds all investments') or contains(@text,'Account verified')]`. | back → Home | partial — `test_navigation.py::test_deep_link_funding_account` asserts the title only; does not assert the verified/account-(1234) content or back-stack. | P1 | Map: real screen with account (1234), Change, Account verified, funding-source warnings. |
| `test_deep_link_spending_account_lands_on_linked_accounts` | spending_account | `DeepLinks.SPENDING_ACCOUNT` | **Linked accounts for Round-Ups** (byte-identical to `accounts/round_ups`) — NOT a Spending Account screen. Assert `RoundUpsPage.is_visible(ACCOUNTS_TITLE)` (Linked-accounts title / Dag Site). | back → Home | yes (load, asserts the real linked-accounts destination) — `test_navigation.py::test_deep_link_spending_account`. Back-stack NOT covered; mismatch documented in test docstring but NOT as an xfail on the intended screen. | P2 | **MISMATCH #1 (hard route).** No distinct spending-account destination exists in this build. Recommend an additional `xfail(strict=False)` case asserting the INTENDED "Spending Account" title to keep the registry defect visible, while this case asserts the REAL destination. |
| `test_deep_link_milestone_opens_overview` | milestone | `DeepLinks.MILESTONE` | **Milestone overview**. Assert `BasePage.is_visible(//*[contains(@text,'Milestone') or contains(@text,'milestone')])` AND a progress money figure `//android.widget.TextView[contains(@text,'$')]` (map: $1,564.03 / $2,000). | back → Home | partial — `test_navigation.py::test_deep_link_milestone` asserts title only; no progress content or back-stack. | P1 | Real screen: "Up next", Edit, progress bar, "Fastest ways to get there" cross-links. |
| `test_deep_link_achievements_opens_grid` | achievements | `DeepLinks.ACHIEVEMENTS` | **Achievements** badge grid. Assert `BasePage.is_visible(//*[@text='Achievements'])` AND at least one badge-group label present (`//*[contains(@text,'Goal') or contains(@text,'Round-Ups') or contains(@text,'Rewards')]`). | back → Home | partial — `test_navigation.py::test_deep_link_achievements` asserts the title only; no grid content or back-stack. | P1 | Real screen: grouped grid (Goals / Round-Ups / Raiz Rewards). |
| `test_deep_link_plans_opens_pricing_plans` | plans | `DeepLinks.PLANS` | **Pricing plans**. Assert `BasePage.is_visible(//*[contains(@text,'Plan') or contains(@text,'plan')])` AND tier copy `//*[contains(@text,'Lite') or contains(@text,'Regular') or contains(@text,'Plus')]` AND "Current plan" marker. | back → Home | partial — `test_navigation.py::test_deep_link_plans` asserts the title only; no tier content or back-stack. | P1 | Real screen: Lite/Regular/Plus tiers, "from $5.50 / month", Current plan marker, PDS/AID links. |

---

## B. Back-stack cases (RAIZ-9994 class — back returns to Home for every area)

Finding #8: back is uniform — every deep-linked area returns to **Home** on `driver.back()`; no intermediate back-stack. Encode one back-stack case per area. Pattern reuses `TestDeepLinkBackNavigationE2E._assert_back_lands_on_home` (open link → assert dest loaded → `driver.back()` → assert `HomePage.is_loaded()`, recover to Home if an intermediate pops first).

| Proposed test name | Area | Deep link | Dest precondition | Back-stack assertion | Covered already? | Priority | Notes |
|---|---|---|---|---|---|---|---|
| `test_back_from_jars_returns_home` | jars | `DeepLinks.JARS` | `JarsPage.is_loaded()` | back → `HomePage.is_loaded()` | **yes** — `TestDeepLinkBackNavigationE2E::test_back_from_jars_returns_home`. | P2 | Already covered; keep. |
| `test_back_from_raiz_kids_returns_home` | raiz_kids | `DeepLinks.RAIZ_KIDS` | `KidsPage.is_loaded()` (consent gate) | back → Home | no | P2 | Gap. Back from the consent gate must land on Home, not strand mid-consent. |
| `test_back_from_raiz_super_returns_home` | raiz_super | `DeepLinks.RAIZ_SUPER` | `SuperPage.is_loaded()` (error/contact) | back → Home | no | P2 | Gap. Back from the super error/contact dead-end must recover to Home. |
| `test_back_from_round_ups_returns_home` | round_ups | `DeepLinks.ROUND_UPS` | `RoundUpsPage.is_loaded()` | back → Home | no | P2 | Gap. |
| `test_back_from_round_ups_settings_returns_home` | round_ups/settings | `DeepLinks.ROUND_UPS_SETTINGS` | `is_visible(SETTINGS_TITLE)` | back → Home | no | P2 | Gap. Map: back goes straight to Home (not to the Round-Ups dashboard). |
| `test_back_from_round_ups_accounts_returns_home` | accounts/round_ups | `DeepLinks.ROUND_UPS_ACCOUNTS` | `is_visible(ACCOUNTS_TITLE)` | back → Home | no | P2 | Gap. |
| `test_back_from_funding_account_returns_home` | funding_account | `DeepLinks.FUNDING_ACCOUNT` | Funding title visible | back → Home | no | P2 | Gap. |
| `test_back_from_spending_account_returns_home` | spending_account | `DeepLinks.SPENDING_ACCOUNT` | `is_visible(ACCOUNTS_TITLE)` (real dest) | back → Home | no | P2 | Gap. Back from the mislanded linked-accounts screen returns to Home. |
| `test_back_from_milestone_returns_home` | milestone | `DeepLinks.MILESTONE` | Milestone title visible | back → Home | no | P2 | Gap. |
| `test_back_from_achievements_returns_home` | achievements | `DeepLinks.ACHIEVEMENTS` | Achievements title visible | back → Home | no | P2 | Gap. |
| `test_back_from_plans_returns_home` | plans | `DeepLinks.PLANS` | Plans title visible | back → Home | no | P2 | Gap. |
| `test_back_from_super_account_info_returns_home` | raiz_super/account_info | `DeepLinks.RAIZ_SUPER_ACCOUNT_INFO` | `SuperPage.is_loaded()` (fallback) | back → Home | no | P3 | Gap. Back from the mismatched fallback returns to Home. |
| `test_back_from_super_important_docs_returns_home` | raiz_super/important_documents | `DeepLinks.RAIZ_SUPER_IMPORTANT_DOCS` | `SuperPage.is_loaded()` (fallback) | back → Home | no | P3 | Gap. |
| `test_back_from_raiz_kids_2_returns_home` | raiz_kids_2 | `DeepLinks.RAIZ_KIDS_2` | `KidsPage.is_loaded()` | back → Home | no | P3 | Gap (duplicate route, but back-stack still asserted). |

---

## C. Discovered sub-area cases (cross-links / onboarding gates / dead-ends)

These are surfaced on-screen (no dedicated deep link). Each is reached by deep-linking the parent then asserting the sub-area entry point is present/navigable. Direct-navigation angle = "every area is navigated to and verified," so the sub-area's reachability is asserted from its parent.

| Proposed test name | Sub-area | Reached from (deep link → action) | Expected ACTUAL destination + assertion | Back-stack assertion | Covered already? | Priority | Notes |
|---|---|---|---|---|---|---|---|
| `test_round_ups_settings_links_to_linked_accounts` | Linked accounts for Round-Ups (from Settings) | `ROUND_UPS_SETTINGS` → scroll → "Linked accounts for Round-Ups" row | `is_present_now(LINKED_ACCOUNTS_ROW)` (entry point present). | n/a (entry-point presence) | **yes** — `test_more_e2e_flows.py::test_round_ups_settings_links_to_linked_accounts`. | P2 | Settings is the bridge to linked-accounts admin. |
| `test_round_ups_accounts_offers_add_account` | Add an account | `ROUND_UPS_ACCOUNTS` → assert "Add an account" | `is_present_now(ADD_ACCOUNT)`. | back → Home | **yes** — `test_more_e2e_flows.py::test_round_ups_linked_accounts_listed` asserts `ADD_ACCOUNT` present. | P2 | Sub-action; do NOT complete the add flow (only `test_link_round_ups_account_via_dag_sandbox`, destructive/opt-in, does). |
| `test_round_ups_accounts_offers_manage_consent` | Manage consent & data sharing | `ROUND_UPS_ACCOUNTS` → assert "Manage consent and data sharing" | `is_present_now(MANAGE_CONSENT)`. | back → Home | **yes** — same `test_round_ups_linked_accounts_listed`. | P2 | Sub-action present; CDR consent surface. |
| `test_round_ups_accounts_shows_nab_relogin` | NAB re-login | `ROUND_UPS_ACCOUNTS` → assert NAB "unable to connect — Log in" | `is_present_now(//*[contains(@text,'NAB')])` AND `//*[contains(@text,'Log in') or contains(@text,'unable to connect')]`. | back → Home | no | P3 | Map: NAB shows an "unable to connect — Log in" re-auth affordance. Gap. Do not tap. |
| `test_funding_account_offers_change` | Change funding account | `FUNDING_ACCOUNT` → assert "Change" | `is_present_now(//*[contains(@text,'Change')]')` as the change-funding-account entry. | back → Home | no | P2 | Gap. The "Change" control is the entry to the change-funding-account flow. Do not complete it. |
| `test_round_ups_dashboard_offers_manual_invest` | Manual Round-Ups "tap to invest" | `ROUND_UPS` → assert Manual Round-Ups "tap to invest" | `is_visible(MANUAL_ROUND_UPS)` AND `//*[contains(@text,'tap to invest')]`. | back → Home | partial — `test_more_e2e_flows.py::test_round_ups_dashboard_shows_auto_and_manual` asserts `MANUAL_ROUND_UPS` present but is data/link-gated and does not assert the "tap to invest" manual-invest entry specifically. | P3 | Manual Round-Ups invest entry point. Do not tap. |
| `test_milestone_offers_fastest_ways_crosslinks` | Milestone "Fastest ways to get there" cross-links | `MILESTONE` → assert cross-link rows | Presence of `//*[contains(@text,'Set recurring investment')]`, `//*[contains(@text,'lump-sum') or contains(@text,'lump sum')]`, `//*[contains(@text,'Raiz Rewards')]`, `//*[contains(@text,'new Jar') or contains(@text,'Open a new Jar')]`. | back → Home | no | P3 | Gap. Four cross-links to recurring / deposit / rewards / jars. Assert presence only; do not follow (they leave the bucket). |
| `test_raiz_super_offers_contact_us` | Contact US (email + phone) | `RAIZ_SUPER` → assert Contact US | `//*[contains(@text,'Contact')]` AND phone `//*[contains(@text,'1300 75 47 48')]` / email link. | back → Home | no | P3 | Gap. The only forward control on the super dead-end. Do not dial/email. |
| `test_raiz_kids_consent_lists_legal_docs` | Legal/document links on Kids consent | `RAIZ_KIDS` → assert doc references | Presence of `//*[contains(@text,'Privacy Policy')]`, `//*[contains(@text,'PDS') or contains(@text,'AID')]`, `//*[contains(@text,'Investment Guide')]`, `//*[contains(@text,'Target Market') or contains(@text,'TMD')]`. | back → Home | no | P3 | Gap. Compliance doc links repeated on the consent gate (and on Plans). Assert presence; do not open external docs. |
| `test_plans_links_to_pds_aid` | Legal docs on Plans | `PLANS` → assert "read PDS and AID" | `//*[contains(@text,'PDS')]` AND `//*[contains(@text,'AID')]`. | back → Home | no | P3 | Gap. PDS/AID disclosure links on the pricing-plans screen. |
| `test_jars_create_form_offers_recurring_row` | Jars recurring-investments sub-control | `JARS` → assert "Set recurring investments" on the create form | `is_present_now(SET_RECURRING_ROW)` on the Customise-your-Jar form. | back → Home | no | P3 | Gap. The create form embeds a recurring-investments row (single-screen form, not a wizard — UI-only flow #1). Do not tap Create Jar. |

---

## D. Mismatch documentation cases (xfail on the INTENDED destination)

To keep the 3 hard route mismatches visible to the deep-link-registry owner (cross-owned `utils/deep_links.py`), add a paired `xfail(strict=False)` case per mismatch asserting the **intended** destination. The non-xfail cases in section A assert the **real** destination so the suite stays green and honest. This mirrors the existing `test_deep_link_performance_day|month` xfail convention in `tests/test_navigation.py`.

| Proposed test name | Deep link | INTENDED (asserted, xfail) destination | REAL destination (per map) | Covered already? | Priority | Notes |
|---|---|---|---|---|---|---|
| `test_deep_link_spending_account_intended_screen_xfail` | `DeepLinks.SPENDING_ACCOUNT` | A distinct **Spending Account** screen (title "Spending account"). | Linked accounts for Round-Ups (mismatch #1). | no (the real-dest case exists; the xfail-on-intended does not) | P3 | `xfail(strict=False, reason="REGISTRY FINDING: raiz://spending_account resolves to Linked-accounts-for-Round-Ups, no distinct spending screen in build 2.39.1d")`. |
| `test_deep_link_super_account_info_intended_screen_xfail` | `DeepLinks.RAIZ_SUPER_ACCOUNT_INFO` | A super **Account information** screen (USI / Member number / ABN). | Base Raiz Super error/contact screen (mismatch #2). | no | P3 | `xfail(strict=False)` asserting `SuperPage.is_visible(ACCOUNT_INFO_TITLE)` or a member identifier. |
| `test_deep_link_super_important_docs_intended_screen_xfail` | `DeepLinks.RAIZ_SUPER_IMPORTANT_DOCS` | A super **Important documents** list (PDS/TMD/Guide). | Base Raiz Super error/contact screen (mismatch #3). | no | P3 | `xfail(strict=False)` asserting `SuperPage.is_visible(DOCS_TITLE)` or `DOC_TEXTS`. |

---

## E. Dead-end / duplicate findings to record (no new assertion required beyond above)

| Finding | Map ref | Where encoded above |
|---|---|---|
| `raiz_kids_2` duplicates `raiz_kids` consent gate | #5 | `test_deep_link_raiz_kids_2_duplicates_consent_gate` (A) |
| Achievements badges are display-only dead-ends (no-progress account) | #6 | Note on `test_deep_link_achievements_opens_grid` — assert grid only; do NOT assert a badge detail screen (tapping "Goal Setter" opens nothing). |
| `raiz://jars` skips a Jars list (empty state) | #7 | `test_deep_link_jars_opens_create_form` (A) |
| Back is uniform → Home for all areas | #8 | All of section B |
| Super base is an effective dead-end (unfunded) | #4 | `test_deep_link_raiz_super_opens_fund_search_error` (A) + `test_raiz_super_offers_contact_us` (C) |

---

## Coverage rollup

- **Total direct-navigation cases:** 41
  - A. Deep-link load: 14
  - B. Back-stack: 14
  - C. Discovered sub-areas: 11
  - D. Mismatch-intended xfail: 3 (the 14th load case `spending_account` real-dest counted in A; 3 here are the paired intended-destination xfails)
- **Gaps not yet covered (no/partial in the nav-test sense):** the bulk are new. Fully covered already: 4 (back-from-jars; settings→linked-accounts link; add-account present; manage-consent present). The remaining 37 are gaps (new or only loosely/partially covered — e.g. load cases that today assert a generic title or `is_loaded()` rather than the real content + empty/onboarding state, and 13 of 14 back-stack cases).
- **Mismatches to document:** 3 hard route mismatches (`spending_account`, `raiz_super/account_info`, `raiz_super/important_documents`) → paired xfail-on-intended (section D); plus 3 softer findings (raiz_kids_2 duplicate, jars-skips-list, super dead-end) folded into the load cases.
- **P1 cases:** 11 (all the core area-entry load cases asserting the real destination/empty state: jars, raiz_kids, raiz_super, round_ups, round_ups/settings, accounts/round_ups, funding_account, milestone, achievements, plans).
