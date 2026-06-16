# Direct-Navigation Test Cases — Bucket A (Investing / Money-core), Device A (emulator-5554)

ANALYST-1 (direct-navigation angle). Source of truth: `docs/nav_map_5554.md` (LIVE crawl, build 2.39.1d/3223).
Pure analysis — no device. Each area gets a deep-link LOAD case (asserting the **actual** crawl-confirmed destination)
plus a BACK-STACK case (launcher-exit vs return-to-Home per the RAIZ-9994 split). Mismatches are encoded as the
actual destination + documented finding, never as the wrong expectation.

## Back-stack split (RAIZ-9994 class) — encode this exactly
- **EXIT TO LAUNCHER on back** (Home-tab-surface screens): `home`, `performance/day`, `performance/month`, `history`, `future`.
- **RETURN TO HOME on back** (modally-pushed screens): `invest`, `deposit`, `withdraw`, `recurring_investments`, `performance`, `transactions`, `portfolio`, `portfolio/custom`.

## Deep-link mismatches to document (assert ACTUAL, flag as finding/xfail)
1. `raiz://performance/day` → **Home** (not day-performance).
2. `raiz://performance/month` → **Home** (not month-performance).
3. `raiz://portfolio` → **allocation breakdown** (ETF % list), not a portfolio overview.
4. `raiz://history` → **investing-journey summary** (== Home > Past tab), not the transaction list.
5. `raiz://dividends` → flaky cold-load ("Oops!" → PIN); needs retry/robustness.

---

## LOAD cases (deep-link → actual destination)

| Proposed test name | Area | Deep link | Expected ACTUAL destination + assertion (real element/title) | Back-stack assertion | Covered already? | Priority | Notes |
|--------------------|------|-----------|--------------------------------------------------------------|----------------------|------------------|----------|-------|
| `test_direct_home_loads` | home | `raiz://home` | Home dashboard. Assert `HomePage.is_loaded()` (TOTAL_VALUE_LABEL `"Your total investments value"` OR HOME_TABS `Today`) and greeting `//*[contains(@text,'Hello')]`. | see back case | **yes** — `test_deep_link_home` (tests/test_navigation.py) | P1 | Baseline anchor. |
| `test_direct_invest_loads` | invest | `raiz://invest` | Main Portfolio summary. Assert `MainPortfolioPage.is_loaded()`; cite `ADD_FUNDS_BUTTON`, `WITHDRAW_BUTTON`, `PERFORMANCE_DETAILS_ROW`, `INVESTED_HEADER`. | see back case | **yes** — `test_deep_link_portfolio` (uses `DeepLinks.INVEST`→MainPortfolioPage) | P1 | Naming wart: test is named `_portfolio` but opens INVEST. |
| `test_direct_deposit_loads` | deposit | `raiz://deposit` | Lump Sum investment keypad. Assert `LumpSumPage.is_lump_sum_loaded()` (LUMP_SUM_TITLE `Lump Sum investment`/`Minimum of $5 Investment`); cite presets `$10/$25/$50/$100`, keypad KEY_0. | see back case | **partial** — exercised via `lump_sum` fixture + `TestLumpSumScreen`, but **no deep-link-named direct-nav test** in test_navigation.py | P1 | Gap: add an explicit direct-nav load assertion for `DEPOSIT`. |
| `test_direct_withdraw_loads` | withdraw | `raiz://withdraw` | Withdraw keypad. Assert WITHDRAW title `//*[@text='Withdraw']` + `LumpSumPage.is_withdraw_loaded()`; cite `AVAILABLE_BALANCE` (`Available:`). | see back case | **yes** — `test_deep_link_withdraw` | P1 | Existing test only checks the `Withdraw` title; consider adding AVAILABLE_BALANCE. |
| `test_direct_recurring_loads` | recurring_investments | `raiz://recurring_investments` | Recurring investments list. Assert `RecurringPage.is_loaded()` (TITLE `Recurring investments` OR MAIN_PORTFOLIO_SECTION `MAIN PORTFOLIO`). | see back case | **yes** — `test_deep_link_recurring_investments` + `test_recurring_investments_loads` (test_investments.py) | P1 | Double-covered. |
| `test_direct_performance_loads` | performance | `raiz://performance` | Performance screen. Assert `PerformancePage.is_loaded()` (TITLE `Performance`); cite INVESTMENT_VALUE_LABEL `Main Portfolio investment value`, range pills 1D..All, MARKET_STATUS. | see back case | **yes** — `test_deep_link_performance` | P1 | Plain link works (only /day,/month broken). |
| `test_direct_performance_day_lands_on_home` | performance/day | `raiz://performance/day` | **MISMATCH** → lands on **Home**, NOT Performance. Assert ACTUAL: `HomePage.is_loaded()` and `PerformancePage.TITLE` absent. | see back case (launcher exit) | **partial** — `test_deep_link_performance_day` exists but is **xfail asserting the WRONG dest** (PerformancePage) | P2 | **Document mismatch #1.** Recommend either (a) flip to assert Home (actual), or (b) keep xfail-strict against Performance to track the registry fix. Current xfail `strict=False` asserts Performance. |
| `test_direct_performance_month_lands_on_home` | performance/month | `raiz://performance/month` | **MISMATCH** → lands on **Home**, NOT Performance. Assert ACTUAL: `HomePage.is_loaded()` and Performance TITLE absent. | see back case (launcher exit) | **partial** — `test_deep_link_performance_month` is xfail asserting wrong dest (PerformancePage) | P2 | **Document mismatch #2.** Same treatment as /day. |
| `test_direct_transactions_loads` | transactions | `raiz://transactions` | Transaction History list. Assert `TransactionHistoryPage.is_loaded()` (TITLE `Transaction History`); cite FILTER_BUTTON, dated Buy rows. | see back case | **yes** — `test_deep_link_transactions` | P1 | The REAL transaction list (distinct from history). |
| `test_direct_history_lands_on_journey_summary` | history | `raiz://history` | **MISMATCH** → **investing-journey summary** ("Your investing journey since <year>", `Transaction history` link, Net invested, Past/Today/Future tabs), NOT a transaction list. Assert `//*[@text='Transaction history' or contains(@text,'Your investing journey') or @text='Total invested to date']`. | see back case (launcher exit) | **yes** — `test_deep_link_history` (asserts the journey summary, correct ACTUAL) | P2 | **Document mismatch #4.** Same screen as Home > Past. Already correctly asserts actual. |
| `test_direct_dividends_loads` | dividends | `raiz://dividends` | Dividends screen. Assert `//*[contains(@text,'Dividend')]`; cite `Expected Amount`, `Upcoming`, empty-state copy. **Add cold-load retry**: if "Oops!"/PIN appears, dismiss + re-open once before asserting. | see back case | **partial** — `test_deep_link_dividends` asserts the title but has **NO retry/robustness** for the cold-load flake | P2 | **Document flake #5.** Gap = retry guard. |
| `test_direct_future_loads` | future | `raiz://future` | Future projection. Assert `//*[@text='Projected Value' or contains(@text,'Projected')]`; cite age slider 18-38, `Periodic Investment`, `View my portfolio`, Past/Today/Future tabs. | see back case (launcher exit) | **no** — `DeepLinks.FUTURE` has **no direct-nav test** anywhere | P2 | **GAP.** No FuturePage object; use BasePage title matcher. |
| `test_direct_portfolio_lands_on_allocation` | portfolio | `raiz://portfolio` | **MISMATCH** → **portfolio allocation breakdown** (Standard/Plus toggle, risk levels, ETF % rows IAA/AAA/STW/IEU/IAF/RCB/IVV), NOT a portfolio overview. Assert `PortfolioAllocationPage.is_loaded()` (PORTFOLIO_TABS). | see back case | **yes** — `test_deep_link_portfolio_alias` (asserts PortfolioAllocationPage, correct ACTUAL) | P2 | **Document mismatch #3.** Correctly asserts actual. Coachmark `Got it` may overlay first visit. |
| `test_direct_portfolio_custom_loads` | portfolio/custom | `raiz://portfolio/custom` | Customise portfolio. Assert `//*[contains(@text,'Custom') or contains(@text,'Portfolio') or contains(@text,'Plus')]`; cite `Your Portfolio`, `Base Portfolio (Conservative) 100.0%`, ETFs Add, Stocks, Raiz Property Fund, Bitcoin. | see back case | **yes** — `test_deep_link_portfolio_custom` (BasePage title matcher) | P2 | Title inferred (WATCH) per existing comment; RAIZ-10251 area. |

---

## BACK-STACK cases (RAIZ-9994 split)

| Proposed test name | Area | Deep link | Expected back behavior + assertion | Covered already? | Priority | Notes |
|--------------------|------|-----------|------------------------------------|------------------|----------|-------|
| `test_back_from_home_exits_to_launcher` | home | `raiz://home` | **EXIT TO LAUNCHER**. After `driver.back()`, assert app no longer foreground (e.g. `current_package != com.acornsau.android.development` / activity not MainActivity), NOT a Home re-render. | **no** | P3 | Home-tab surface. Destructive (backgrounds app) — run last / isolated; re-launch in teardown. |
| `test_back_from_invest_returns_home` | invest | `raiz://invest` | **RETURN TO HOME**. Open INVEST, assert MainPortfolioPage loaded, `back()`, assert `HomePage.is_loaded()`. | **no** — invest is NOT in `TestDeepLinkBackNavigationE2E` (only performance/jars/transactions/finance) | P1 | **GAP.** Modally-pushed. |
| `test_back_from_deposit_returns_home` | deposit | `raiz://deposit` | **RETURN TO HOME**. Lump Sum loaded → `back()` → `HomePage.is_loaded()`. | **no** | P1 | **GAP.** Modally-pushed. |
| `test_back_from_withdraw_returns_home` | withdraw | `raiz://withdraw` | **RETURN TO HOME**. Withdraw keypad loaded → `back()` → `HomePage.is_loaded()`. | **no** | P1 | **GAP.** Modally-pushed. |
| `test_back_from_recurring_returns_home` | recurring_investments | `raiz://recurring_investments` | **RETURN TO HOME**. Recurring list loaded → `back()` → `HomePage.is_loaded()`. | **no** | P2 | **GAP.** Modally-pushed. |
| `test_back_from_performance_returns_home` | performance | `raiz://performance` | **RETURN TO HOME**. Performance loaded → `back()` → recoverable Home. | **yes** — `test_back_from_performance_returns_home` (TestDeepLinkBackNavigationE2E) | P1 | Modally-pushed. |
| `test_back_from_performance_day_exits_to_launcher` | performance/day | `raiz://performance/day` | **EXIT TO LAUNCHER** (it landed on Home). After `back()`, assert app backgrounded, not a Home re-render. | **no** | P3 | Lands on Home → Home-tab surface back behavior. Destructive. |
| `test_back_from_performance_month_exits_to_launcher` | performance/month | `raiz://performance/month` | **EXIT TO LAUNCHER** (landed on Home). After `back()`, app backgrounded. | **no** | P3 | Same as /day. Destructive. |
| `test_back_from_transactions_returns_home` | transactions | `raiz://transactions` | **RETURN TO HOME**. Transaction History loaded → `back()` → recoverable Home. | **yes** — `test_back_from_transactions_returns_home` | P1 | Modally-pushed. |
| `test_back_from_history_exits_to_launcher` | history | `raiz://history` | **EXIT TO LAUNCHER**. Journey summary loaded → `back()` → app backgrounded (NOT return-to-Home). | **no** | P2 | **GAP + contrast case.** History is a Home-tab surface (== Past tab) → exits, UNLIKE transactions which returns to Home. High-value distinction. Destructive. |
| `test_back_from_dividends_returns_home` | dividends | `raiz://dividends` | **RETURN TO HOME**. Dividends loaded (with cold-load retry) → `back()` → `HomePage.is_loaded()`. | **no** | P2 | **GAP.** Modally-pushed. Map shows back behavior only as "Oops dialog on first hit" — needs the retry-stabilised load before back. |
| `test_back_from_future_exits_to_launcher` | future | `raiz://future` | **EXIT TO LAUNCHER**. Future projection loaded → `back()` → app backgrounded. | **no** | P2 | **GAP.** Home-tab surface. Destructive. |
| `test_back_from_portfolio_returns_home` | portfolio | `raiz://portfolio` | **RETURN TO HOME**. Allocation breakdown loaded → `back()` → `HomePage.is_loaded()`. | **no** | P2 | **GAP.** Modally-pushed (despite the mismatched destination). |
| `test_back_from_portfolio_custom_returns_home` | portfolio/custom | `raiz://portfolio/custom` | **RETURN TO HOME**. Customise portfolio loaded → `back()` → `HomePage.is_loaded()`. | **no** | P2 | **GAP.** Modally-pushed. |

---

## Coverage rollup

- **Areas (13):** home, invest, deposit, withdraw, recurring_investments, performance, performance/day, performance/month, transactions, history, dividends, future, portfolio, portfolio/custom (14 deep-link targets counting both performance ranges).
- **LOAD cases (14):** 8 fully covered, 4 partial (deposit no named direct-nav test; performance/day & /month xfail asserting wrong dest; dividends no retry), 2 actual mismatches already-correctly-asserted (history, portfolio), 1 hard gap (future).
- **BACK-STACK cases (14):** 3 covered (performance, transactions, [home/finance pattern exists]), 11 gaps. Notably the launcher-exit half of the split is **entirely uncovered** (home, performance/day, performance/month, history, future) — existing back E2E only asserts the return-to-Home half.

### Implementation notes for the test author
- Launcher-exit assertions are **destructive** (background the app); isolate them, mark e2e, and re-foreground via `DeepLinks.HOME` in teardown so the serial suite stays order-independent.
- Existing `TestDeepLinkBackNavigationE2E._assert_back_lands_on_home` is the right helper for the return-to-Home half; add invest/deposit/withdraw/recurring/dividends/portfolio/portfolio_custom to it.
- Dividends needs a retry wrapper (dismiss "Oops!", re-open once) before any load/back assertion.
- performance/day & /month: keep the registry-fix tracker but assert the ACTUAL Home landing (or xfail-strict against Performance) — do not silently assert Performance as if it passed.
