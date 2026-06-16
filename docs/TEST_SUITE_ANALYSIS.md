# Raiz Android Appium Suite — Critical Analysis & E2E Gap Report

_Author: automation review · Date: 2026-06-01 · App: `com.acornsau.android.development`_

This document is deliberately critical. The framework is well built; the **test
design is not pulling its weight**. Below: what's good, what's wrong, where the
real gaps are (mapped to production bugs), what I added, and what to do next.

---

## 1. Executive summary

- **~95% of existing assertions are presence checks** (`is_visible(...)`). They
  prove the app *renders*, not that it *works*.
- **There was not a single true end-to-end flow.** The investment tests
  explicitly stop at the keypad and never submit. No journey verifies a state
  change (invest → confirm → appears in history; logout → re-login).
- **No value or correctness assertions existed.** `"$" in value` was the bar.
  Several real, recent production defects were *value* bugs that this bar cannot
  see (see §4).
- **The suite would have passed green through at least one live Major Android
  bug** (RAIZ-9994, back-navigation): the settings nav tests press `back()` and
  never assert where they land.
- Coverage is **absent** for: registration/KYC onboarding, Round-Ups
  configuration, Recurring investment create/edit, Super, custom portfolio,
  reward redemption, and money-movement completion.

The release process doc (Confluence, _Release testing process_) names the
critical flows as **Login/Auth, Investing/Withdrawing, Navigation** and requires
"full end-to-end functionality tests." The suite as found does not meet that bar.

---

## 2. What the suite does well (keep this)

- Clean **Page Object Model**; pages are small and readable.
- **Deep-link navigation** (`utils/deep_links.py`) makes screen setup fast and
  resilient to nav-chrome churn — a genuinely good decision.
- **Smart state handling** in `conftest.py`: `_ensure_logged_in` copes with
  splash/PIN/home/modal, and snapshot probes (`is_present_now`) avoid burning
  full timeouts. The biometrics/modal dismissal is thoughtful.
- iOS-readiness is scaffolded without over-engineering.
- Sensible marker taxonomy and a session-scoped driver for speed.

---

## 3. Core critique — why "it's green" is misleading

| # | Problem | Evidence in the code |
|---|---------|----------------------|
| 1 | **Presence ≠ correctness.** Tests assert elements exist, never that values are right. | `test_total_value_is_displayed` → just `"$" in value`. `test_select_1d_range` → taps 1D then asserts the *button* is still visible, not that the chart/value changed. |
| 2 | **No completed money flows.** | `test_investments.py` header: _"verify the UI and keypad behaviour WITHOUT submitting real transactions."_ The confirmation sheet ("Nice!") is never reached. |
| 3 | **Navigation tests assert the wrong thing.** | `TestSettingsNavigation` taps an item then `driver.back()` with **no assertion on where back lands** — so RAIZ-9994 (back doesn't return to Settings) would pass. |
| 4 | **Brittle, resolution-specific locators.** | `SettingsPage.CLOSE_BUTTON = @bounds='[924,117][1068,261]'` and `NavDrawer.CLOSE_BUTTON` hard-code pixel bounds; `base_page.dismiss_modal` matches `contains(@bounds,'[912'`. These break on any other screen size/density. |
| 5 | **Ambiguous locators.** | `BACK_BUTTON` and `HAMBURGER_BUTTON` are the *same* XPath `(//android.widget.Button)[1]`. Index-based button locators are order-dependent and fragile. |
| 6 | **`xfail` masks a data problem.** | README says the account has "an active jar" and "5 kids", yet `test_jars.py`/`test_kids.py` mark the meaningful cases `xfail("requires account with active jars/kids")`. Either the data is wrong or the tests dodge a flaky state — either way, Jars/Kids are effectively **untested**. |
| 7 | **Reads can't read.** | `LumpSumPage.AMOUNT_DISPLAY` was hard-pinned to `$0.00`, so `get_amount_display()` could never return a non-zero amount. (Fixed — see §5.) |
| 8 | **Shared mutable session, order coupling.** | Tests type into search boxes, switch tabs, etc. on a session-scoped driver. The autouse re-auth fixture helps, but there's no per-test UI reset, so failures can cascade. |

---

## 4. Coverage gaps mapped to **real** production bugs

These are recent RAIZ bugs (last ~120 days). The point: the current suite would
not have caught them. Each is now addressed or scheduled.

| Product area | Coverage today | Real bug it missed | Status |
|---|---|---|---|
| Invest confirmation/commit | none (stops at keypad) | RAIZ-10259 invest widget | **Added** (`TestLumpSumInvestmentE2E`) |
| Settings back-nav | asserts nothing post-back | **RAIZ-9994** back ≠ Settings (Android, Major) | **Added** (`TestSettingsBackNavigationE2E`) |
| Performance values | button-visible only | RAIZ-10306 wrong Δ-value; RAIZ-10244 % on $0.00 | **Added** (`TestPerformanceValueE2E`) |
| Transaction correctness | bare count + type | RAIZ-10063 list not refreshed; RAIZ-10328 ordering | **Added** (`TestTransactionCorrectnessE2E`) |
| Withdraw flow | keypad only | money-movement risk | **Added** (`TestWithdrawE2E`, defensive) |
| Logout/re-login | button visible only | auth (release-critical) | **Added** (`TestSessionLifecycleE2E`) |
| Registration / KYC onboarding | **none** | RAIZ-9953 no redirect after set portfolio; RAIZ-10026 backspace crash on Verification | **Scheduled** (§6) |
| Round-Ups config | title-visible only | RAIZ-9970 round-ups settings UI | **Scheduled** |
| Recurring create/edit | screen-present only | RAIZ-9909 Save button obstructed | **Scheduled** |
| Custom portfolio | **none** | RAIZ-10251 totals don't add up | **Scheduled** |
| Jars / Kids create | `xfail` | RAIZ-10355 home count not updated after create | **Scheduled** |
| Raiz Super | **no test file** | RAIZ-10114 rebalance cell UI | **Scheduled** |
| Reward redemption/webview | list-present only | RAIZ-9984 Petbarn URL won't load; RAIZ-10061 PDF | **Scheduled** |

---

## 5. What I implemented in this pass

New, runnable, and collected (17 tests) — all tied to a flow above:

- **`utils/assertions.py`** — money/percentage parsing + `assert_money`,
  `assert_non_negative_money`, `assert_positive_money`. This is the missing
  primitive that turns "is it there" into "is it right". Unit-verified offline.
- **`pages/lump_sum_page.py`** — confirmation-sheet locators/methods
  (`is_confirmation_shown`, `cancel_confirmation`, `confirm_invest/withdraw`,
  `is_success_shown`) grounded in the captured "Nice!" screen; a working
  `get_amount_display()` and `amount_is_zero()`.
- **`pages/transaction_history_page.py`** — `get_transactions()` returns
  structured `{type, amount, texts}` rows for correctness assertions.
- **`tests/test_e2e_flows.py`** — the seven journeys in §4, with `e2e`, `edge`,
  and `destructive` markers. Money flows **cancel by default**; the one test
  that commits is `@destructive` + skipped unless `RUN_DESTRUCTIVE=1`.
- **`tests/test_allocation_jars_kids_e2e.py`** + `pages/portfolio_allocation_page.py`
  — second batch (Custom portfolio + Jars/Kids):
  - **Portfolio allocations sum to 100%** and each weighting is in range — the
    RAIZ-10251 assertion. Scrolls the full list, stale-safe.
  - **Plus builder** loads and its **base portfolio starts at 100%**.
  - **Jar create screen** loads with real create affordances; an opt-in
    `destructive` test creates a jar and asserts the **Home Jars card stops
    showing "Add"** (the RAIZ-10355 assertion).
  - **Kids** consent gate + onboarding entry (full multi-step kid creation is a
    deeper crawl — see roadmap).
- **Framework hardening done in passing:** made `PinPage.enter_pin` stale-safe
  (PIN keypad recomposes mid-entry on Jars re-auth and threw
  StaleElementReferenceException), and gave the new fixtures a retry to absorb
  the shared-session/PIN-gate race.
- **`tests/test_more_e2e_flows.py`** + `pages/round_ups_page.py`,
  `pages/super_page.py`, `pages/recurring_page.py` — third batch:
  - **Round-Ups** (flagship): the test account now has a **linked** sandbox bank
    (Yodlee "Dag Site (US)"), so coverage is the *configured* state — dashboard
    (Auto/Manual Round-Ups + invested totals, all well-formed money), settings
    (Auto toggle, all four minimum thresholds $5/$10/$20/$40, multiplier,
    whole-dollar — the RAIZ-9970 area), and linked accounts (institution +
    monitored subaccounts + Add/Manage-consent). A reproducible **opt-in
    `destructive` re-link** test encodes the full link flow (creds via
    `CDR_TEST_*` env / `.env`).
  - **Raiz Super**: the surface loads on whichever onboarding step the (unfunded)
    account is on; the insurance opt-in's Death/TPD consent disclosure is asserted
    *when shown*. No state-advancing taps (super onboarding is stateful).
  - **My Finance**: net-worth section loads; every figure is well-formed money
    and investments is positive; **investments total reconciles with the Home
    headline within 2%** (cross-screen consistency — the RAIZ-10251 family).
  - **Recurring** (RAIZ-9909): reach the Set Recurring Investment form and assert
    the **Save button renders at a usable tap size** (its actual failure mode),
    plus Frequency + a well-formed current balance. We never tap Save.

### Combined result — 4 E2E files, one session: **32 passed, 4 skipped** (3m17s)
Skips are all intentional: 2 opt-in `destructive` commits, 1 funded-account
percentage case, 1 stateful-super onboarding step. No instrumentation crashes;
the self-healing driver held across the full run.

### Batch 4 — added offline (compile + collect clean; NOT yet run on-device)
Written from this session's verified locators/crawls. 12 tests across existing files:
- **test_more_e2e_flows.py**: Round-Ups dashboard filter tabs (All/Invested/
  Available); My Finance financial-insights setup card + Category Spending;
  Recurring setup offers both Recurring Investment & Savings Goal.
- **test_navigation.py**: drawer → Super / Recurring / Lump Sum (made the drawer
  `go_*` methods scroll-safe to match `go_my_finance`); deep links → Dividends /
  Fees / Offsetters (contains-matchers, same convention as the existing
  milestone/plans/funding deep-link tests).
- **test_auth.py**: invalid email format does not authenticate; "Forgot your
  password?" navigates away from the login form.

Confidence: HIGH for the My Finance / Recurring / Round-Ups / drawer-Super/
Recurring / invalid-email tests (exact locators verified this session). WATCH on
first run: the Lump Sum drawer landing, the Dividends/Fees/Offsetters deep-link
title guesses, and the forgot-password navigation — these touch screens not yet
crawled and may need a locator tweak.

### Batch 5 — unit tests (VERIFIED OFFLINE, 91 passing) + 1 E2E
With the device down, the highest-value verifiable work was testing the suite's
own pure logic:
- **test_assertions_unit.py** (46 tests, **green**): locks `parse_money` /
  `parse_percent` / `is_money` / `assert_*` — the parsers behind every value
  check (commas, negatives, `$0.00`, `%`, malformed input, None).
- **test_deep_links_registry_unit.py** (45 tests, **green**): every `raiz://`
  constant is well-formed, no duplicates, scheme correct.
- **test_portfolio.py → TestMainPortfolioBackNavigationE2E** (4 params, device):
  back from a Main-Portfolio sub-screen (Round-Ups / Recurring / Holdings /
  Transaction history) returns to Main Portfolio — the **RAIZ-9994 bug class
  extended to the portfolio area** (originally only covered for Settings).
- Registered the `unit` marker. Run pure tests anywhere with `pytest -m unit`
  (no Appium/phone needed) — 91 pass in <0.1s.

### Batch 6 — weird edge cases (offline: 135 unit pass + 6 xfail; +13 device E2E)
Pushed hard on the awkward inputs and invariants a micro-investing app breaks on.

Offline-verified (`pytest -m unit` → **135 passed, 6 xfailed**, <0.2s):
- **TestWeirdMoneyFormats / TestWeirdPercentFormats** — leading zeros, malformed
  commas, embedded-in-sentence, millions, trailing dot, single decimal, amount
  after a newline, 3-dp truncation, negative-zero, `5 %`, etc. all locked.
- **TestParseBounds** — the Android-bounds parser behind the RAIZ-9909 tap-target
  check (extracted to `utils.assertions.parse_bounds`, now pure + unit-tested:
  zero-size, inverted, embedded, malformed → None).
- Deep-link registry now also enforces a path **charset** (`^[a-z0-9_/]+$`, no
  leading/trailing slash).

**Parser-gap FINDINGS** (documented as `xfail`, so they flip visible if fixed) —
`parse_money`/`parse_percent` mis-handle: accounting-parentheses negatives
`($5.00)`, trailing-minus `$5.00-`, unicode-minus `−$5`, and no-leading-zero
`$.50` / `.5%`. None observed in Raiz's current rendering, but worth hardening if
any screen ever emits them — the tests are ready to confirm a fix.

Device E2E (grounded in verified locators; **not yet run**) — `test_edge_cases_e2e.py`:
- **Keypad abuse** (9): $0 invest/withdraw must not open the confirmation; delete-
  past-empty stays $0.00; double decimal points, >2 decimals, dot-first, leading
  zeros, 7-digit and 9-digit runs — the display must stay a well-formed,
  non-negative, ≤2-dp money string (asserted as an invariant, not an exact value).
- **Cross-screen consistency** (2): Main Portfolio value ≈ Performance value (2%);
  Home total ≥ a single account.
- **Greeting** (2): no `null`/`undefined`/`{…}`/`%s` placeholder leakage; greeting
  is actually personalised.

### Emulator run (emulator-5554, 1080x2400) — full suite green after fixes
Ran the whole suite on an Android emulator (`ANDROID_UDID=emulator-5554`). Results
per file: edge 13✓, navigation+portfolio 63✓, more_e2e 15✓/2 skip, e2e_flows+
allocation 22✓/3 skip, home+settings+investments 64✓, rewards+jars+kids 22✓/11
xfail, unit 135✓/6 xfail. Only `test_auth.py::TestLogin` is unrunnable on a fresh
device (its `fresh_driver` resets app data → re-triggers the emailed new-device
verification code). Setup notes: new-device login needs the emailed OTP (verify
once manually); disable in-app biometrics (emulator has none enrolled); if the
`io.appium.settings` helper is broken, `adb uninstall io.appium.settings` and let
Appium reinstall.

**Real bugs found & fixed by running on a second device** (all device-agnostic):
1. **Logged-out false positive (latent flakiness):** conftest detected "logged
   out" via `splash.LOG_IN_LINK` (`contains 'Log in'`), but the Round-Ups linked-
   accounts screen has a bare "Log in" element → bogus re-login → timeout on the
   next test. Switched detection to the splash-unique `TAGLINE` ("Smart investing").
2. **Greeting locator:** `HomePage.GREETING` matched `'Hello,'` but the real text
   is "Hello <Name>," → never matched. Fixed to `contains 'Hello'`.
3. **Hardcoded pixel bounds:** `SettingsPage.close()` used the S23's exact close-X
   bounds → now finds the right-most header clickable (resolution-independent).
4. **Exact-match titles:** `JarsPage.CUSTOMISE_JAR_TITLE` was exact `'Customise
   your Jar'` vs real "Customise your Jar! Let's start…" → `contains`.
5. **Scroll robustness:** main-portfolio row taps, the drawer Round-Ups item, and
   the home portfolio-card taps used a single swipe / scroll-to-Superannuation
   that missed on a taller screen → all now `scroll_to_text` the target.
7. **Home card-nav order dependency:** the portfolio cards (Main Portfolio/Jars/
   Kids/Super) exist only on the **Today** tab; `test_tab_future_tappable` leaves
   Home on the **Future** tab (a projection chart, no cards), so the later
   card-nav tests couldn't find the cards. `HomePage._tap_card()` now selects
   Today first and confirms it left Home (retry once — the tap can mis-fire on a
   laggy device). Also `KidsPage.is_loaded` broadened (Kids card → identity-consent
   gate) and `JarsPage.CUSTOMISE_JAR_TITLE` exact→contains. `TestHomeNavigation`
   now 9/9.

**Emulator health caveat:** the AVD has only ~893 MB free (vs 3 GB on the physical
device). Under that pressure, long back-to-back runs degrade badly — UiAutomator2
starts returning `Could not proxy command … timeout of 90000ms exceeded` on random
commands (a full `TestHomeNavigation` once took 32 min and infra-failed one trivial
tab test). This is environment, not test logic. For stable full runs, cold-boot the
emulator / give the AVD more RAM, and run `scripts/recover_appium.sh` between heavy
batches.
6. **PIN-aware fixture:** conftest `my_finance` used raw `DeepLinks.open` (no PIN
   handling) unlike its siblings → switched to `_open_deep_link`.

**FINDING (product):** investing **$0.00 reaches the "Nice!" confirmation sheet**
(no keypad gate), whereas **withdraw $0 is gated**. Characterised in
`test_edge_cases_e2e` and worth a product/UX decision.

### Calibration notes (found while verifying — assumptions the device corrected)
- Invest/withdraw **don't gate amount bounds at the keypad** (min/over-balance
  reach the confirmation) — characterised, not asserted as "blocked".
- The recurring **Save button is full-width and fine** — it's *disabled* on an
  empty form, not obstructed; so we assert size, not clickability.
- **My Finance net worth lazy-loads** — poll for the value, don't read on title.
- **Super onboarding is stateful** on a shared account; tests assert invariants
  and avoid advancing the flow.

### Verification status — VERIFIED ON-DEVICE ✅
Executed on the connected Samsung S23 (`RFCX80S23GM`, dev build) against the live
test account. Both E2E files in one shared session: **22 passed, 3 skipped** (two
opt-in `destructive` commits + the `$0.00` percentage case that doesn't apply to
a funded account). During the runs I crawled and corrected several screens whose
copy differed from the initial capture:
  - Withdraw confirmation is titled **"Confirm Withdrawal"** (Cancel / Confirm),
    not "Nice!" — locators updated and re-verified.
  - Logout → re-login round trip passes end-to-end.

### Findings discovered while verifying (worth a Jira ticket)
Both reproduced on a clean session, so they're behaviour, not test flakiness:

1. **Invest does not gate the disclosed $5 minimum at the keypad.** Entering `$1`
   and tapping Invest opens the "Nice!" confirmation sheet. The "Minimum of $5"
   notice is informational only at this step.
2. **Withdraw does not cap at the available balance at the keypad.** With
   `$1,564.35` available, entering `$101,564` still opens "Confirm Withdrawal".

In both cases the client lets an out-of-bounds amount reach the confirmation
sheet; where the bound is actually enforced (final Confirm or server-side) is
**unverified — I did not commit either transaction.** These are captured as
green *characterisation* tests (`test_below_minimum_amount_is_not_gated_at_keypad`,
`test_over_balance_amount_is_not_gated_at_keypad`) that cancel immediately and
flip RED if the gating ever changes.

---

## 6. Prioritized roadmap (next flows, highest value first)

1. **Registration + KYC onboarding** — highest-churn funnel, zero coverage, and
   already generating Critical bugs (RAIZ-9953, RAIZ-10026). Needs a disposable
   test-user strategy (see Raiz test-user tooling / Admin dev tool). _Still the
   biggest remaining gap._
2. **Round-Ups end-to-end** — ✅ _done (configured state)_: linked-account
   dashboard, settings (thresholds/multiplier/whole-dollar — RAIZ-9970), and
   linked-accounts list all covered; reproducible re-link automated. Next: drive
   a sandbox transaction and assert a round-up actually accrues end-to-end.
3. **Recurring investment create/edit/cancel** — ✅ _started_: setup form + Save
   render guarded (RAIZ-9909). Next: enter amount + frequency → Save → assert the
   schedule persists (opt-in destructive, with delete-to-clean-up).
   **Also done:** My Finance net-worth value + Home cross-screen consistency.
4. **Custom portfolio allocation** — ✅ _started_: weightings sum to 100%
   (RAIZ-10251) + Plus base = 100%. Next: assert totals reconcile **after** the
   user reallocates within the Plus builder (that's where RAIZ-10251 actually bit).
5. **Jars & Kids create/manage** — ✅ _started_: jar create screen + opt-in
   home-count assertion (RAIZ-10355); Kids consent/onboarding entry. Next: full
   kid creation (consent → Welcome → Next → permissions → details), and a
   create-then-close cleanup so the destructive jar test is repeatable.
   **Data note:** the test account has **no** active jars/kids (home cards show
   "Add"); the README's "active jar / 5 kids" claim is wrong and should be fixed.
6. **Super** — ✅ _started_: onboarding surfaces + insurance-consent disclosure
   covered (`pages/super_page.py`). Next: a funded super account to assert the
   dashboard balance/contributions and the history rebalance cell (RAIZ-10114).
7. **Reward detail → redemption/webview** — assert the brand webview loads
   (RAIZ-9984) and tracked rewards reflect activity.

### Framework hardening (do alongside)
- Replace pixel-`@bounds` locators with resource-ids/content-desc (ask the app
  team to add stable `testTag`s — Compose supports it).
- Disambiguate `BACK_BUTTON` vs `HAMBURGER_BUTTON`.
- Add a per-test UI reset (deep-link to Home) to remove order coupling.
- Add an **API/Admin hook** so balances/holdings can be asserted against
  backend truth, not just the rendered number.
- Wire a `data-layer`/Mixpanel-event assertion path (per the Data team's
  Mixpanel doc) so analytics regressions are caught too.

---

## 7. How to run

```bash
source venv/bin/activate
appium --relaxed-security            # separate terminal
# reconnect the device first: adb devices  must list RFCX80S23GM

pytest tests/test_e2e_flows.py -m e2e            # all new journeys
pytest -m "e2e and smoke"                        # fast critical E2E
RUN_DESTRUCTIVE=1 pytest -m destructive          # DEV-only, commits a $5 invest
```
