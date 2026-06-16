# Raiz AU Android — Navigation Map (emulator-5554)

- Build: 2.39.1d / 3223, logged in, PIN 0000
- Package: `com.acornsau.android.development` (single activity `com.raiz.main.MainActivity` — entire app is one React/Compose surface, so `current_activity` is always `MainActivity`)
- Explored: 2026-06-05, one Appium session, foreground, deep links + UI taps
- "Total investments value" figure drifts cent-by-cent between captures (live mock backend); ignore the dollar amounts as identity signals.

## Deep-link areas

| Area | Deep link | Actual screen title | Key visible elements | Lands on expected screen? | Back-button behavior | On-screen links to other areas |
|------|-----------|---------------------|----------------------|---------------------------|----------------------|--------------------------------|
| Home | `raiz://home` | Home ("Hello, Jsoj") | Total investments value, "2 issues that need to be solved", Set up your account (2 of 5), Add funds, Withdraw, Performance details, Rewards, Main Portfolio, Jars, Past/Today/Future tabs | YES | Exits app -> launcher | Add funds, Withdraw, Performance details, Rewards, Jars, Set a recurring investment, Turn on Round-Ups, View all (account setup), Past/Today/Future |
| Invest | `raiz://invest` | Invest / portfolio summary ("Your main portfolio's investment value") | Add funds, Withdraw, Performance details, Invested, Net invested by you $1,550, Rewards, Promos & Referrals, Performance, Market return 1.98%, Dividends:, Total returns: | YES | Returns to Home | Add funds, Withdraw, Performance details, Rewards (expands cashback/surveys), Performance |
| Deposit | `raiz://deposit` | Lump Sum investment (keypad) | "Invest", number pad 0-9, "Lump Sum investment", Portfolio, $0.00, Minimum of $5 Investment, quick amounts $10/$25/$50/$100 | YES | Returns to Home | quick-amount chips, Portfolio selector |
| Withdraw | `raiz://withdraw` | Withdraw (keypad) | "Withdraw", number pad, Portfolio, $0.00, Available: $1,565 | YES | Returns to Home | Portfolio selector |
| Recurring investments | `raiz://recurring_investments` | Recurring investments | MAIN PORTFOLIO (Jsoj Jdjd, Conservative, $0), Raiz Kids ("Add a Raiz Kid now"), Raiz Jars ("Create your first Jar") | YES | Returns to Home | Add a Raiz Kid now, Create your first Jar |
| Performance | `raiz://performance` | Performance | Main Portfolio investment value, Change in value (All) +$15.49 +1.98%, Total invested $1,550, Total returns $15.49, range tabs 1D/1M/3M/6M/1Y/All, "market is currently open", Date | YES | Returns to Home | range tabs (1D/1M/3M/6M/1Y/All) |
| Performance (day) | `raiz://performance/day` | **Home** (NOT a day-performance screen) | Hello Jsoj, total investments value, Add funds, Withdraw, Performance details, Past/Today/Future | **NO — lands on Home** (known mismatch CONFIRMED) | Exits app -> launcher | same as Home |
| Performance (month) | `raiz://performance/month` | **Home** (NOT a month-performance screen) | Hello Jsoj, total investments value, Add funds, Withdraw, Performance details, Past/Today/Future | **NO — lands on Home** (known mismatch CONFIRMED) | Exits app -> launcher | same as Home |
| Transactions | `raiz://transactions` | Transaction History | Filter, Buy entries ($500/$400/$150), Main Portfolio, dated rows (07/08 May 2026) | YES | Returns to Home | Filter |
| History | `raiz://history` | **Investing-journey summary** ("Your investing journey since 2026") — NOT a transaction history list | Portfolios 1, Net invested by you $1,550, Rewards $0, Promos & Referrals, Your returns so far, Market return 1.98%, Dividends:, Total returns:, **Transaction history** link, Past/Today/Future tabs | **NO — lands on investing-journey summary, not a "history" list** (known mismatch CONFIRMED). This is the same screen as the Home > Past tab. | Exits app -> launcher | Transaction history (-> the real Transaction History list), Past/Today/Future |
| Dividends | `raiz://dividends` | Dividends | Dividends, AAA, Expected Amount $1.42, Reinvested, "You haven't received any dividends yet", Upcoming $0 | YES (see note) | (Oops dialog on first hit) | — |
| Future | `raiz://future` | Future projection | Projected Value $5,258, age slider 18-38, Periodic Investment $20/monthly, Portfolio Conservative, **View my portfolio**, Past/Today/Future tabs | YES | Exits app -> launcher | View my portfolio, Past/Today/Future, age/investment sliders |
| Portfolio | `raiz://portfolio` | **Portfolio allocation breakdown** (NOT a portfolio overview) | Standard/Plus toggle, risk levels (Conservative…Aggressive), ETF allocation list (IAA 3%, AAA 24.5%, STW 13.5%, IEU, IAF 30%, RCB 23%, IVV) | **NO — lands on allocation breakdown** (known mismatch CONFIRMED) | Returns to Home | Standard/Plus toggle, risk-level selectors |
| Portfolio (custom) | `raiz://portfolio/custom` | Customise portfolio | Standard/Plus, Your Portfolio, Base Portfolio (Conservative) 100.0%, ETFs ("New ETFs added", Add), Stocks, Raiz Property Fund, Bitcoin | YES | Returns to Home | Add (ETFs), Stocks, Raiz Property Fund, Bitcoin selectors |

### Note on Dividends
First `raiz://dividends` hit showed a transient **"Oops!" / Ok** error dialog and dismissing it dropped to the PIN screen (intermittent backend/load glitch). A second navigation loaded the real Dividends screen correctly. Treat the deep link as working but **flaky on cold-load**.

## UI-only areas (reached by tapping)

| Area | UI path | Actual screen | Key elements | Notes / leads to |
|------|---------|---------------|--------------|------------------|
| Home tab: Today | Home > "Today" | Home (default) | total investments value, Add funds, Withdraw, Performance details, Main Portfolio, Jars | Default Home tab |
| Home tab: Past | Home > "Past" | Investing-journey summary | Same screen as `raiz://history` (Net invested, returns, Market return, **Transaction history** link) | == `raiz://history` |
| Home tab: Future | Home > "Future" | Future projection | Same screen as `raiz://future` (Projected Value, age slider, View my portfolio) | == `raiz://future` |
| Add funds modal | Home > "Add funds" | Bottom sheet "Add funds" | Lump Sum Investment, Recurring investments, Close sheet | Two options below |
| Add funds > Lump Sum | Add funds > "Lump Sum Investment" | Lump Sum investment (keypad) | Invest, keypad, Portfolio, Minimum of $5, $10/$25/$50/$100 | Same screen as `raiz://deposit` |
| Add funds > Recurring | Add funds > "Recurring investments" | Recurring investments | MAIN PORTFOLIO, Raiz Kids, Raiz Jars | Same screen as `raiz://recurring_investments` |
| Invest row: Add funds | Invest > "Add funds" | Add funds bottom sheet | Lump Sum Investment, Recurring investments | -> Lump Sum / Recurring |
| Invest row: Withdraw | Invest > "Withdraw" | Withdraw (keypad) | Withdraw, keypad, Available | Same as `raiz://withdraw` |
| Invest row: Performance details | Invest > "Performance details" | Performance | Change in value, range tabs 1D..All | Same as `raiz://performance` |
| Invest row: Rewards | Invest > "Rewards" | Invest screen (Rewards section expands inline) | reveals Cashback invested, Surveys under Rewards | In-page expand, not a new screen |
| Invest "Dividends:" / "Promos & Referrals" | Invest screen | (inline labels) | These are read-only summary rows in the Invest body, **not tappable navigation rows** | No navigation |

## Discovered areas not in my bucket / registry
- **Raiz Kids entry points**: "Add a Raiz Kid now" on the Recurring investments screen (registry has `raiz://raiz_kids`).
- **Raiz Jars entry point**: "Create your first Jar" on the Recurring investments screen (registry has `raiz://jars`).
- **Account setup checklist**: Home "Set up your account (2 of 5 completed)" + "View all" and "2 issues that need to be solved" — an onboarding/issues flow with no deep link in my bucket.
- **Transaction history link inside the investing-journey summary** (Home Past tab / `raiz://history`) — the only in-app path to the real transaction list other than `raiz://transactions`.
- **Future > "View my portfolio"** — link from the Future projection back into portfolio.
- **Invest > Rewards expansion**: Cashback invested, Surveys sub-rows (registry has `raiz://raiz_rewards`).
- **Portfolio customisation building blocks**: Raiz Property Fund, Bitcoin, Stocks, add-ETF on `raiz://portfolio/custom`.

## Mismatches / dead-ends
1. `raiz://performance/day` -> lands on **Home** (expected day-performance). CONFIRMED mismatch.
2. `raiz://performance/month` -> lands on **Home** (expected month-performance). CONFIRMED mismatch.
3. `raiz://portfolio` -> lands on **allocation breakdown** (ETF % list), not a portfolio overview. CONFIRMED mismatch.
4. `raiz://history` -> lands on the **investing-journey summary** (same as Home > Past), not a transaction-history list. The actual transaction list is reached via the "Transaction history" link there or via `raiz://transactions`. CONFIRMED mismatch.
5. `raiz://dividends` -> **flaky**: first cold-load showed an "Oops!" dialog that, when dismissed, dropped to the PIN lock screen; a retry loaded the correct Dividends screen. Not a hard dead-end but unreliable.
6. Back-button inconsistency (not a registry bug but worth noting for tests): screens reached via the Home/Past/Today/Future tab surface (Home, performance/day, performance/month, history, future) **exit the app to the launcher** on back, whereas modally-pushed screens (invest, deposit, withdraw, recurring, performance, transactions, portfolio, portfolio/custom) **return to Home**.

No areas in my bucket failed to load outright; the only loading anomaly was the intermittent Dividends "Oops!".
