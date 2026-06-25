# Raiz Feature-Connectivity Map

> Authoritative, source-traceable aggregation of 14 per-feature maps (built from the real Android app + Raiz backend). Downstream test-case agents read this to understand what each feature does and how features wire together for cross-feature VALUE/STATE oracles. Every claim is traceable to an app path or backend model/route cited inline.

---

## (a) Product model — one paragraph

Raiz is a micro-investing platform built around **one core investing engine**. A user holds an **active Portfolio** (a basket of funds with target allocation % that must sum to 100); money flows into it from several feeders — **lump-sum deposits**, **recurring/auto deposits**, **round-ups** (virtual spare change off linked-bank transactions), and **rewards/found-money** (partner cashback) — and each inflow materializes as an `Investment` row (STI, keyed by `investment_type`) that produces an `AllocationsOrder` and buys `Holding` fund shares. **Withdrawals** sell shares back out to the linked ACH funding source. The same Portfolio + Investment + AllocationsOrder + Holding machinery is reused for every account type: the **Main Portfolio**, each **Raiz Kid** (a `dependent` sub-User), each **Jar** (a `jar` sub-User), and **Super** (a `super_annuation` sub-User) — all hanging off one parent user whose `funding_user` resolves back to the regular account. **Portfolio-performance** is the read-out (value tile, change-in-value, graph, transaction history, statements) rendered per account. Around this sit **plans-fees** (subscription tier gating portfolios/Kids/Jars + monthly `FeeInvestment` deductions), **money/My-Finance** (Yodlee/FastLink external-account aggregation, net-worth, spend insights, savings goals), **auth-onboarding** (the universal verified-User + PIN gate in front of everything), **notifications** (inbox + push that deep-link into product screens), and **milestones-gamification** (milestones, steps, achievement badges that reward usage). The throughline for testing: **money is conserved and routed** — a single seeded inflow moves the contributing feature's totals, the active portfolio value, transaction history, net-worth, and possibly a milestone/achievement, all at once.

---

## (b) Connectivity graph (adjacency list)

Reconciled, deduplicated edges. `A <-> B` = bidirectional/mutual; `A --> B` = A feeds/depends-on/navigates-to B (arrow points to the relied-upon or fed target). Edges where the two maps agreed are merged into one line; asymmetric/contradictory claims are flagged in section (b.1).

```
core-investing (HUB)
  <-- roundups            roundup amounts become RoundUp/AutoRoundUp Investments buying portfolio shares
  <-- recurring           AutoInvestment Investments on a schedule buy portfolio shares
  <-> deposits-withdrawals lump-sum (credit) buys / withdrawal (debit) sells; shared Invest/Withdraw screen+keypad
  <-- raiz-rewards        confirmed Reward/FoundMoney -> CreditInvestment do_settle! into portfolio
  --> portfolio-performance value/return/dividends read out of holdings+fund prices (perf depends-on investing)
  <-> raiz-super          same Portfolio/Investment/AllocationsOrder w/ super types; super funded by regular acct
  <-> raiz-kids           each kid = dependent sub-User w/ own portfolio; reuses investment pipeline
  <-> raiz-jars           each jar = jar sub-User w/ own portfolio (duped from parent); reuses pipeline
  <-- plans-fees          plan tier gates accessible portfolios; FeeInvestment < Investment sells shares
  --> milestones          confirmed AllocationsOrders/balance drive milestone+achievement progression
  <-- money-myfinance     'Total in investments' net-worth row = user investing balance (finance depends-on)
  <-- auth-onboarding     verified User owns all investing data; portfolio chosen at onboarding (suitability)
  <-- notifications       default deep link raiz://home lands on main portfolio

roundups
  --> core-investing      (see above)
  <-> deposits-withdrawals same linked bank (shared bank_account_token); threshold-collect as 'deposits'
  <-> money-myfinance     SAME AggregationSubaccount/Yodlee feed (roundup:true + financial_insight:true)
  --> portfolio-performance invested round-ups become holdings + 'Round-Ups' history rows
  <-> raiz-kids           dependent-user gating on auto-roundup/PUT settings; kidsAccessDenied
  <-> raiz-jars           jar_user round-up investments; jar_user?/not_for_closed_jar? gating
  <-- raiz-rewards        automatic cashback tracking REQUIRES a linked Round-Up account (rewards depends-on)
  --> notifications       auto_round_up push pref; threshold-lower re-caches txns + async job
  --> auth-onboarding     requires linked+verified Yodlee site; enable_auto_roundups on user create
  <-- recurring           sibling auto-feeder; shared INVESTING_WEEKLY_LIMIT_TYPES + funding rails
  --> milestones          roundup_changed awards automator/collector; milestone action nudges multiply/auto

recurring
  --> core-investing      AutoInvestment CreditInvestment buys into portfolio
  --> deposits-withdrawals draws from linked funding source (ACH); NSF/unregistered blocks setup
  <-> raiz-kids           per-kid recurring via dependent_user_id (same PreferenceUpdater)
  <-> raiz-jars           per-jar recurring via jar_user_id; jars have NO savings-goal
  --> raiz-super          'Super AutoInvestment' + SuperAnnuation::Investments::Adjuster
  --> milestones          recurring_deposit_set accomplishment + steps/milestone-actions update
  <-> money-myfinance     Savings Goal reuses recurring amount+frequency to forecast reach
  --> notifications       dependent notifications + auto-investment-changed email + push
  <-> roundups            (see above)

deposits-withdrawals
  <-> core-investing      (see above)
  --> raiz-kids           Kid is a deposit/withdraw destination (dependent creator)
  --> raiz-jars           Jar is a deposit/withdraw destination (jar creator) + owner<->jar transfers
  <-> raiz-super          super_fund_debit + BPAY billing funding; amount-allowed-for-super validation
  <-- roundups            (see above)
  <-- recurring           (see above)
  <-- raiz-rewards        Reward FoundMoney credits share settlement machinery (no ACH pull)
  --> portfolio-performance settled deposits/withdrawals move balance + Buy/Sell history rows
  --> auth-onboarding     linked ACH + RDV verification is a HARD prerequisite (MissingFundingError 402)
  <-> plans-fees          fees collected from verified fee-eligible funding source; NSF gates behavior
  --> money-myfinance     deposits/withdrawals appear in txn history + net-worth
  --> notifications       link/unlink + deposit-suspension (NSF) emails/alerts

portfolio-performance
  --> core-investing      reads holdings+fund ratios; switching portfolio recalcs+rebalances (depends-on)
  <-> raiz-jars           same value tile+graph per Jar (jarId/dailyChange chip)
  <-> raiz-kids           same value tile+graph per Kid (dependentUserId chip); dependent_user statements
  <-> raiz-super          Super performance widget + super trade statement
  <-- deposits-withdrawals (see above)
  <-- roundups            invested round-ups add value + 'Round-Ups' rows
  <-- recurring           'Recurring Investment' filter/Buy rows
  <-- raiz-rewards        'Rewards'/'Promo'/'Referrals' history rows; settled credits add value
  <-- plans-fees          'Fee' history rows reduce value (AUM from avg balance)
  <-> money-myfinance     sibling tab; share per-account balances + EFV forecast + txn plumbing
  --> milestones          investment-value thresholds drive milestone celebrations
  --> auth-onboarding     all value/perf data scoped to authenticated user (graph keyed by User.find)

raiz-kids
  --> auth-onboarding     kid IS a dependent User; convert_to_full at 18 (depends-on)
  <-> core-investing      own portfolio + lump-sum invest/withdraw + dividend reinvest (kids feeds investing)
  <-> deposits-withdrawals owner<->kid transfers + lump-sum (mutual)
  --> recurring           own recurring deposit setting (delegable to child)
  --> portfolio-performance own perf/statements/dividends (PerformanceScreenArgs.Kids; kids depends-on perf)
  --> raiz-rewards        kid rewards flag -> ExternalAccountCreator; RewardsKidsAccessDenied for child
  <-- roundups            round-ups can fund kid (transfer_requests_for :deposits scoped :kids)
  <-> raiz-jars           sibling sub-account pattern; relatable_ids includes both
  --> notifications       per-kid notification prefs on DependentUser (depends-on)
  <-- plans-fees          plan Kid limitation gates opening kids; monthly_kids fee
  <-- money-myfinance     spending-analytics endpoints accept dependent_user_id
  <-- milestones          kid_money_transferred awards raiz_kids badges on parent

raiz-jars
  <-> core-investing      jar dupes parent portfolio (Custom::Duper); requires parent portfolio (depends-on)
  <-> raiz-kids           parallel sub-account type; investing_accounts = [self]+child_users+jar_users
  <-> deposits-withdrawals owner<->jar transfers + lump-sum credit/debit (mutual)
  <-> recurring           per-jar recurring (mutual; recurringv2<->jars navigation)
  <-- roundups            RoundUp credit can accumulate into a jar
  --> portfolio-performance per-jar daily-change/present-graph/gainLoss (PerformanceScreenArgs.Jars)
  <-- raiz-rewards        jar summary surfaces found-money/referral rewards
  <-- milestones          milestone nav -> nav_host_jars; jar_created awards goal_getter badges
  --> auth-onboarding     jar_user auto-created USER_TYPE_JAR copying parent verification (depends-on)
  <-- plans-fees          plan Jar limitation gates opening jars

raiz-rewards
  --> core-investing      confirmed reward -> CreditInvestment do_settle! (Rewards breakdown row)
  --> roundups            automatic tracking REQUIRES linked Round-Up account (depends-on)
  --> raiz-kids           dependent/jar NOT eligible; rewards attach to PARENT user_uuid (depends-on)
  --> raiz-super          move_super_rewards admin path (reward amounts into super)
  --> auth-onboarding     rewards scoped per user_uuid; eligibility gates on regular_suitable? (depends-on)
  <-> milestones          referral-type rewards feed drawer invite amount; rewards badges
  <-> deposits-withdrawals reward settlement shares CreditInvestment settlement machinery
  <-> money-myfinance     same AggregationSubaccount linking (rewards:true) + linked-accounts UI

raiz-super
  --> auth-onboarding     own TFN/ID/insurance-consent onboarding; DEV verify code '1111' (depends-on)
  --> core-investing      separate sub-account funded by regular acct; activity = Investment rows (depends-on)
  <-- deposits-withdrawals lump-sum + BPAY contributions; super_fund_debit (super feeds via deposits)
  <-- recurring           'Recurring contribution' -> Super AutoInvestment
  <-- raiz-rewards        'Reward contribution' into super
  <-> portfolio-performance own perf graph + dividends (PerformanceScreenArgs.Super)
  <-- money-myfinance     Find My Super (ATO SuperMatch) rolls external funds in as 'Rollover In' (super feeds finance? see b.1)
  --> notifications       raiz://raiz_super deep links route push (gated by flag)
  <-> raiz-jars           parallel sub-account funding pattern (funding_user branches)
  <-- plans-fees          super fee_user_type + super_annuation_transaction collection; plans filtered by user_type

money-myfinance
  <-> roundups            (see above)
  <-> raiz-rewards        (see above)
  --> core-investing      'Total in investments' = investing balance; goal calc uses current_balance (depends-on)
  --> raiz-super          'Total in Superannuation' = super balance (depends-on)
  --> recurring           savings-goal defaults fall back to recurring prefs (depends-on)
  <-> raiz-kids           insights endpoints accept dependent_user_id
  --> milestones          'Set up your financial insights' steps widget embedded (depends-on/navigates)
  <-> deposits-withdrawals same Transaction ledger for categorisation/forecast
  --> auth-onboarding     Yodlee FastLink linking is the onboarding gate (depends-on)

plans-fees
  --> core-investing      tier gates accessible portfolios; FeeInvestment < Investment (feeds)
  --> raiz-kids           Kid limitation; monthly_kids fee (feeds)
  --> raiz-jars           Jar limitation; re-fetch jars settings after change (feeds)
  <-> deposits-withdrawals fees collected from verified fee-eligible funding source (depends-on)
  <-- roundups            deposits count toward rebate 'deposit>=$30' condition
  <-- recurring           recurring deposits satisfy rebate; withdrawal breaks 'no_withdrawal'
  <-> raiz-super          super fees + plans filtered by user_type (shares-data)
  --> auth-onboarding     UserPlan assigned per user; PlanPicker is a sign-up step (depends-on)
  --> notifications       upgrade/downgrade fires templated email
  --> portfolio-performance fee sells reduce balance + 'Fee' history rows (feeds)

auth-onboarding (GATE)
  --> core-investing / raiz-kids / raiz-jars / raiz-super / raiz-rewards / deposits-withdrawals
      / plans-fees / notifications / money-myfinance
      verified User + PIN session is the universal precondition; sub-Users (kid/jar/super) hang off parent

notifications
  --> raiz-rewards        offer/reward notifications deep-link to offer-details (channel=notification)
  --> raiz-super          super notifications deep-link to super sign-up
  <-- money-myfinance     spending-analytics recommendations delivered as notifications (polymorphic source)
  <-- roundups            auto_round_up account-update notifications
  <-- recurring           recurring_deposit account-update notifications
  <-> raiz-kids           per-dependent notification toggles (separate dependency_users endpoint)
  --> auth-onboarding     all endpoints require auth; device push reg ties token to user.uuid
  --> core-investing      default deep link raiz://home -> main portfolio
  --> milestones          notifications deep-link to achievements; milestone completion fires push

milestones-gamification
  --> core-investing      milestone targets derived from + auto-complete against investing balance (depends-on)
  --> deposits-withdrawals deposits grow the balance driving completion (depends-on)
  <-- roundups / recurring / raiz-jars / raiz-kids / raiz-super / raiz-rewards / portfolio-performance
      cross-feature actions (roundup_changed, recurring_deposit_set, jar_created, kid_money_transferred,
      super_matched, portfolio_switched, cashback) award badges; milestone action-nudges point back out
  --> notifications       milestone completion push; achievement 'presented' lifecycle (feeds)
  --> auth-onboarding     steps = onboarding checklist; account_age badges; milestones whitelist+regular-only
  <-- money-myfinance     Steps widget embedded in My Finance (navigates-to)
```

### (b.1) Asymmetric / contradictory claims (reconciliation notes)

- **roundups <-> money-myfinance direction.** roundups map calls it `shares-data`; money-myfinance map also calls it `shares-data`. **Agree** — merged as one bidirectional shared-data edge (one `AggregationSubaccount` row can be `roundup:true` AND `financial_insight:true`).
- **raiz-super --> money-myfinance vs money-myfinance --> raiz-super.** Two *different* edges, not a contradiction: (1) super map asserts Find-My-Super uses TFN/ATO SuperMatch aggregation to roll external funds in (`feeds`, super consuming an aggregation flow); (2) finance map asserts the net-worth 'Total in Superannuation' row reads the super balance (`depends-on`). Kept as **two distinct directed relationships** between the same pair.
- **core-investing <-> portfolio-performance.** core-investing map says performance is `feeds` (investing feeds the readout); portfolio-performance map says it `depends-on` core-investing. These are the **same edge** from opposite ends — merged; canonical wording: performance depends-on / reads-out-of core-investing.
- **deposits-withdrawals <-> plans-fees.** deposits map: `shares-data` (NSF/fee-eligible funding state). plans-fees map: `depends-on` (fees collected from verified fee-eligible funding source). Merged into one edge; the dependency direction (fees depend on a funding source) is the stronger/clearer claim and is kept as primary wording, retaining both evidence pointers (`funding_source.rb:scope :fee_eligible`; `fee_investment.rb:ready_for_collecting`).
- **roundups <-> deposits-withdrawals.** roundups: `depends-on` (funded by same linked bank). deposits: `feeds` (round-ups become CreditInvestments through the same source). Same shared-funding edge from both ends — merged as mutual, both evidence pointers (`aggregation_subaccount.rb:has_one :funding_source`; `credit_investment.rb:check_threshold`).
- **recurring <-> roundups.** Both map it as `shares-data` sibling auto-feeders sharing `INVESTING_WEEKLY_LIMIT_TYPES`. Agree — merged.
- **raiz-kids / raiz-jars sub-account symmetry.** kids map (`shares-data` to jars) and jars map (`shares-data` to kids) agree; `user.rb:1062 relatable_ids` and `investing_accounts` are the shared evidence. Merged.

---

## (c) Per-feature sections

### core-investing — THE HUB
- **Purpose:** Pick a portfolio (funds + target % summing to 100); money flows in (lump-sum/round-ups/recurring/rewards) to buy shares; show value/invested/returns; periodically rebalance to target weights; switch styles (Conservative→Aggressive/Plus/Emerald/Custom); view/withdraw holdings.
- **Key screens/flows:** Main Portfolio / Invest (`main_portfolio/MainPortfolioScreen.kt` + `MainPortfolioViewModel.kt`); portfolio style selection + allocation (`raizFeaturePortfolio` `PortfolioSplashScreen.kt`, `BasePlanScreen.kt`, `PortfolioSwitcher.kt`); Custom portfolios (`CustomizationFragment.kt` + `CustomizationViewModel.kt`); Plus/Pro pie-chart + holdings (`PortfolioPlusDetailsViewModel.kt`, `HoldingsView.kt`); lump-sum/withdraw keypad (`raizFeatureOperations/deposit/DepositRegularFragment.kt`); My Finance entry (`MyFinanceScreen.kt`).
- **Backend models+endpoints:** `Portfolio` (+ `Portfolio::FundRatio` ratios sum=100), `UserPortfolio` join (+ `portfolio_switch_history`), `Allocation` (+ `Allocation::FundRatio`), `AllocationsOrder` (aasm pending→finalized→confirmed; STI buy/sell/rebalance_buy/rebalance_sell/fee/chargeback/split/aggregate), `Investment` STI (`INVESTMENT_TYPE_*` LumpSum/RoundUp/AutoRoundUp/Reward/FoundMoney/Dividend/Withdrawal/AutoInvestment/PerfectRebalance/Fee/UserTransfer), `InvestmentsRebalance`, `Holding`/`HoldingBought`/`HoldingSold`/`HoldingSplit`, `Fund`. Routes: `orders` (rebalance_buy/sell/preview/users_allocations), `funds` path 'etfs' (delete_holding), `portfolios` path 'target_allocations'; `customer_ledgers/investments_controller` order_creation_buy/sell/investments_rebalances/reward_creation (routes.rb:746-763).
- **Deep links:** `raiz://main_portfolio`, `raiz://invest`, `raiz://portfolio[/{page}|/custom|/regular]`, `raiz://finance`, `raiz://finance_v2`, `raiz://home`, `raiz://funding_account`, `raiz://recurring_investments`.
- **Appium hooks:** `text='Main portfolio'`/`text='Invest'` (TITLE/TITLE_REBRAND — TWO home layouts); `text='Add funds'`, `text='Withdraw'` (clickable parent View); `text='Performance details'` / contentDescription `'Performance details icon.'`; rows 'Round-Ups','Recurring','Transaction history','Holdings','Dividends','Past performance','Rewards','Net invested by you','Total invested to date'; style tabs 'Standard/Plus/Conservative/Moderate/Moderately Conservative/Aggressive/Moderately Aggressive/Emerald'; lump-sum: 'Lump Sum investment'/'One-Time Investment'/'Minimum of $5 Investment', '$0.00', 'Available:', chips $10/$25/$50/$100, `resource-id='keypad_dot'`/`'keypad_image_delete'`, 'Invest', success 'Nice!'/'on its way'; custom ids `R.id.btnAddFunds`,`btnSaveFunds`,`pieChartViewPortfolioPro`,`containerItemFund`,`btnPortfolioSelectMain`,`framePortfolioRegularChip`.
- **Seedable/assertable entities:** `Portfolio.identifier_key`/`active`/`user_id`(nil=general)/`position`; `FundRatio.ratio` (sum=100); `Fund.symbol`/`exchange`/`price`/`average_price`; `Investment.amount`(>0)/`investment_type`/`status`/`portfolio_id`/`funding_source_id`; `AllocationsOrder.status`+subtype; `Holding.fund_id`/`shares`/`investment_id`; `InvestmentsRebalance.rebalance_credit_id`/`debit_id`; `UserPortfolio(user_id,portfolio_id)`.
- **Connections:** the drain for roundups/recurring/rewards/deposits; shares pipeline with kids/jars/super; performance reads it; plans-fees gate portfolios + sell fees; milestones derive from balance.
- **test_implications:** Hub — assert cross-feature, not in isolation: a seeded deposit changes main value AND the contributing feature's totals. Seed via gen API: set `UserPortfolio` (style via `identifier_key`), create `Investment(amount, investment_type, portfolio_id)` → AllocationsOrder (pending→finalized→confirmed) + Holdings; allocation % in `Portfolio::FundRatio` (sum=100). Gotchas: (1) gen users have NO fund price history → performance/return/Δ oracles invalid (assert presence/structure only); (2) TWO home layouts (legacy 'Main portfolio' vs rebrand 'Invest') — page objects handle both; (3) withdrawal = sell order, not row deletion, may sit pending; (4) custom save blocked unless ratios sum to 100; (5) kids/jars reuse this exact pipeline; (6) lump-sum $5 minimum; keypad uses clickable parent Views (inner ids non-clickable).

### roundups
- **Purpose:** Virtual spare-change — round a card transaction up to the next dollar and invest the difference. Multiply (1X/2X/3X/5X), minimum accumulation threshold, auto-invest opt-in, whole-dollar round-ups, review in Invested/Available/All history.
- **Key screens/flows:** `features/roundups` `RoundUpsFragmentV2`+`RoundUpsNavHost`; splash `RoundUpsSplashScreen.kt`; history `RoundUpsHistoryScreen.kt` (All/Invested/Available); settings `RoundUpsSettingsScreen.kt` (Auto toggle, threshold, multiplier, whole-dollar, linked accounts); legacy `raizFeatureRoundUps`; entry via NavMenu + Settings 'Manage Round-Ups'.
- **Backend:** `RoundupSetting` (AMOUNT_MULTIPLIERS=[1,2,3,5]; `perform_autoroundup`), `User#roundup_setting`/`credit_roundups`/`automatic_roundups_enabled?`, `CreditInvestment` (RoundUp/AutoRoundUp, scope :round_up/:autoround_up), `YodleeMonitoredSite` (spending/funding/linked/verified), `AggregationSubaccount` (scope :roundup/:analytics). Services `Investing::RoundupPreferences`, `Investing::RoundupManager`; facade `LiveRoundupsFacade`. Endpoints: GET/PUT `/v1/roundup_settings`, GET `/v1/investments/roundups`, POST `/v1/investments` (RoundUp/AutoRoundUp), GET `/v1/account_summary/roundups`.
- **Deep links:** `raiz://round_ups`, `raiz://round_ups/settings`, `raiz://accounts/round_ups`(→spending_account), `raiz://spending_account`, `raiz://funding_account`.
- **Appium hooks (text-only; Compose, no contentDescription/testTag):** 'Round-Ups', 'Round-Up settings' (singular), 'Round-Ups invested', 'Auto Round-Ups', 'Manual Round-Ups', 'Linked accounts for Round-Ups', 'Multiply your Round-Ups', 'Minimum Round-Ups amount', 'Round-Ups for whole dollar transactions', 'Link a Round-Ups account', 'Manage Round-Ups'; tabs 'All'/'Invested'/'Available'; multipliers RadioButtons '2X'/'3X'/'5X' (capital-X); thresholds '$5'/'$10'/'$20'/'$40'; empty states "You don't have any spending yet."; Yodlee 'Dag Site'.
- **Seedable/assertable:** `RoundupSetting.automatic_roundup_enabled_at`/`amount_multiplier`[1,2,3,5]/`automatic_lower_threshold`<`automatic_upper_threshold`/`default_amount`(0..1); `CreditInvestment` RoundUp/AutoRoundUp status (waiting/processing/invested/canceled); `User#round_up_investment_amount`→{invested,waiting}; `YodleeMonitoredSite` linked/verified state; `AggregationSubaccount.card_last4`.
- **Connections:** feeds core-investing + performance; mutual w/ deposits (shared bank); shares-data w/ My-Finance (same Yodlee feed) + kids/jars (sub-account gating); rewards depends-on it for auto-tracking; feeds notifications + milestones.
- **test_implications:** Needs a LINKED+VERIFIED Yodlee site ('Dag Site (US)'); test account HAS one → expect LINKED dashboard, not splash. Seed `RoundupSetting` via gen API (multiplier shown as '2X' capital-X RadioButtons, collapsed by default). Round-ups are CreditInvestments into the SAME portfolio as lump sums → cross-feature side effects on balance/performance/weekly limit. Shared bank w/ deposits — unlinking affects both. Gen users have no real txns → history empty, invested/waiting=0; assert config not dollars. PUT blocked for dependent users + NSF.

### recurring
- **Purpose:** Ongoing fixed-amount auto-invest on a cadence (daily/weekly/fortnightly/monthly) from the funding source. Same engine serves Main/Kids/Jars/Super; optional Savings Goal forecasts reach time.
- **Key screens/flows:** `features/recurringv2` `RecurringFragmentV2`+`RecurringNavHostV2`; LIST (Main/Kids/Jars picker, `raiz://recurring_list`); OVERVIEW (recurring card + goal card + next investment + balance); EDIT ('Set Recurring Investment'); FREQUENCY sub-pages; GOAL flow; stop/suspend dialogs; no-funding/dependent gating; legacy `raizFeatureRecurring` (`raiz://recurring_investments`).
- **Backend:** `RecurringDepositSetting` (user_uuid fk; scope :active amount>0&freq>0), `User#recurring_deposit_preferences`, scope :auto_investing + `next_auto_investment_date`. Services `RecurringDeposit::Preferences` (FREQUENCIES 1 daily/2 weekly/3 monthly/4 fortnightly), `PreferenceUpdater` (validates funding+amount limits), `Investor` (builds AutoInvestment), `PreferenceDeleter`. Endpoints: GET/PUT/DELETE `/v1/recurring_deposit_settings` (Main); `dependency_users/.../recurring_deposit_settings` (Kids, dependent_user_id); `jars/.../recurring_deposit_settings` (Jars, jar_user_id); `super_annuation/.../recurring_deposit_settings`. Driver `UserAutomaticInvestingJob`.
- **Deep links:** `raiz://recurring_list`, `raiz://recurring_investments`.
- **Appium hooks (text-based; contentDescription null, testTag unused):** 'Recurring investments', 'MAIN PORTFOLIO'/'Kids'/'Jars', 'Set Recurring Investment', 'Edit Recurring Investment', 'Recurring Investment Amount', 'Next Investment', 'Frequency', 'Daily'/'Weekly'/'Fortnightly'/'Monthly', 'Save', 'Current balance:', 'Set/Edit Savings Goal', 'Stop this recurring investment?'/'Stop'/'Keep it', 'Add a Raiz Kid now'/'Create your first Jar'.
- **Seedable/assertable:** `RecurringDepositSetting.amount`(5..10000)/`frequency`(1-4 + string identifier)/`day`(weekly/fortnightly 1-7 Sun=1; monthly -1=last)/`start_date`(future for fortnightly); `User.next_auto_investment_date`; API returns `{}` when OFF; `CreditInvestment` AutoInvestment/Super AutoInvestment; `SpendingAnalyticsGoal.target_amount/frequency/target_contribution`.
- **Connections:** feeds core-investing/super; depends-on deposits funding; shares-data kids/jars; mutual w/ My-Finance goal; feeds milestones + notifications; sibling of roundups.
- **test_implications:** PUT amount 5..10000, frequency string, day, start_date (future for fortnightly). API returns `{}` when OFF — assert populated body, not 200. day semantics differ per frequency. next_investment_at via IceCube — don't hard-assert dates on gen users. Gated: no funding/NSF → 400; amount outside threshold → error. Same-day eligible → immediate AutoInvestment (moves balance/history/milestones). Same engine for Main/Kids(dependent_user_id)/Jars(jar_user_id)/Super; Jars have NO goal. Stopping recurring removes the goal.

### deposits-withdrawals
- **Purpose:** Move real money in/out: one-off lump-sum (credit) pulled from ACH funding source, withdrawals (debit) paid back, with min-deposit threshold, verified-funding requirement, available-to-withdraw limits, 1-5 business-day settlement gated by trading-day cutoffs. Same flow targets Main/Kid/Jar; underlies Super (BPAY) + reward/round-up credits.
- **Key screens/flows:** `features/movement` LumpSum (`LumpSumScreen.kt`+VM+Fragment+NavHost), Withdraw (`WithdrawScreen.kt`+`WithdrawFragmentV2.kt`), shared `AmountInput.kt`/`QuickInvestment.kt`, account chooser `SelectInvestmentAccountDialog.kt` (`AccountType` = MainPortfolio|Kid|Jar), source chooser `InvestmentSourceDialog.kt`, NSF gate `DepositSuspensionDialogData.kt`; `MovementType` LumpSum→'credit'/Withdraw→'debit'; funding-account linking in `raizFeatureSignUp`.
- **Backend:** `CreditInvestment` (COLLECTION_TYPE 'deposits'; AASM waiting→pending→approved→transferred→settled→posted_in), `DebitInvestment` (COLLECTION_TYPE 'withdrawals'; AASM long chain; validates cannot_withdraw_more_than_available, no_withdrawals_when_unprocessed_full_withdrawal, check_random_deposit_verification, check_amount_allowed_for_super_fund), `FundingSource` (ACH/DC, status, verified, NSF, bank_account_token), `BillingFundingSource` (BPAY), `Bank`, `CalendarWeekday`/`CalendarHoliday` (cutoffs default 16:00), `credit_investments_threshold` concern. Services `Investments::Creator`→credit/debit creators; `Investments::Types` ALL={credit, debit:[debit,super_fund_debit]}. Endpoints: POST `/v1/investments` (raises MissingFundingError 402/ValidationError 422), PUT `:id/cancel`, FundingSources chargeback_relink/remove_deposits_suspension/changeable/request_change/upload/verification_status. `available_amount_to_withdraw = current_balance - pending_withdraws`.
- **Deep links:** `raiz://lump_sum` (withdraw has NONE — reach via in-app nav).
- **Appium hooks:** 'Lump Sum investment', 'Invest', 'Minimum of $5 Investment', 'Withdraw', 'Available:', 'Choose investment account', 'Raiz account'/'Funding account', 'Nice!'/'Confirm Withdrawal', 'Withdrawal Confirmed', `keypad_dot`/`keypad_image_delete`, '$0.00', chips $10/$25/$50/$100; clickable container `//View[@clickable='true'][.//TextView[@text='Invest'|'Withdraw']]`.
- **Seedable/assertable:** funding_sources fund_type/status/verified/NSF/bank_account_token; investments type/status/amount/transferred_amount/additional_info(super_fund/risk_withdrawal/intended_full_withdrawal); user current_balance/available_amount_to_withdraw/is_frozen; `Setting.investments_threshold`; billing_funding_sources BPAY member_id; calendar cutoffs.
- **Connections:** mutual w/ core-investing; feeds kids/jars destinations; mutual super; fed by roundups/recurring/rewards; feeds performance + My-Finance + notifications; depends-on auth (funding+RDV); shares-data plans-fees.
- **test_implications:** Seed linked+verified FundingSource (ACH, success, verified, no NSF) else POST → 402 + funding gate; withdrawals fail RDV. Min = `Setting.investments_threshold` ($5). Withdrawals capped at available_amount_to_withdraw. Same flow → Main/Kid/Jar (different creators) — seed sub-account first, pick destination. Type mapping load-bearing (credit/debit/super_fund_debit). Settlement async (1-5 days, trading cutoffs) — assert request acceptance + success dialog copy, not immediate 'settled'. intended_full_withdrawal blocks new withdrawals. Tap clickable parent View.

### portfolio-performance
- **Purpose:** What investments are worth + how they performed: value tile, Change-in-Value %, interactive graph (1D/1M/3M/6M/1Y/All), per-security breakdown, market open/closed, transaction history, statements/trade confirmations/tax. Reused per account: Main/Jar/Kid/Super.
- **Key screens/flows:** `features/performancev2` `PerformanceMainScreen.kt`+Header+VM, `PerformanceMainChartTabs.kt` (range pills), balance states; account carousel `PerformanceAccountsCarousel.kt`/`PerformanceAccountUi.kt`/`PerformanceFeatureType.kt` (Regular/Super/Kids(dependentUserId)/Jars(jarId)); ETF breakdown `PerformanceEtfViewerScreen.kt`; super widget; Transaction History (`raiz://history`, mirrored by `transaction_history_page.py`); Statements (`raizFeatureStatements`, tabs Confirmation/Monthly/Tax).
- **Backend:** `Holding` (AASM pending/settled/chargeback; scopes boughts/solds/from_withdrawal/from_fee), `Transaction` (amount/change/transaction_date/posted_date(nil=pending)/transaction_type/category; scopes approved/pending/can_be_rounded_up), `Portfolio`+`UserPortfolio` (efv_multipliers), `Statement` (USER_TYPES user_trade_confirmation/jar_user/super_annuation_user/dependent_user/tax). Service `PerformanceGraphBuilder::Base`+`General#graph_data/#account_balance/#summary` (Balance + Credit-Debit-Difference; `InvestmentSummaryCalculator` period_market_return/%). Endpoints: GET `performance_graph` (requested_days 1/30/91/182/365/nil=All), statement endpoints (reports_archive/trade_statement/super_trade_statement/holding_statement), ledger_history, holdings.
- **Deep links:** `raiz://performance`, `raiz://portfolio[/regular|/custom]`, `raiz://history`.
- **Appium hooks:** 'Performance', 'Main Portfolio investment value', 'Kids/Jars Account investment value', 'Main Portfolio'/'Jar: %s'/'Kid: %s'(+'(Closed)'); range pills '1D'/'1M'/'3M'/'6M'/'1Y'/'All' = NON-clickable TextView in clickable parent View (`//View[@clickable='true'][.//TextView[@text='1D']]`); 'Change in Value'; 'The market is currently open/closed.'; value `//TextView[@clickable='true' and contains(@text,'$')]`; NoContent '--'; 'Transaction History', 'Filter' (clickable parent), filter types 'Lump Sum'/'Recurring Investment'/'Round-Ups'/'Transfers'/'Withdrawal'/'Dividend'/'Rebalance'/'Fee'/'Rewards'/'Promo'/'Referrals', rows Buy/Sell/Rebalance, 'Pending', 'Apply'; 'Statements' tabs Confirmation/Monthly/Tax Reports, 'Send to email'.
- **Seedable/assertable:** account_balance (summary.last[:balance]); summary[] {date,balance,credit_debit_diff}; period_market_return/%; requested_days; Holding status/fund/type; Transaction amount/change/dates/type; Portfolio.identifier_key/efv_multipliers; Statement.statement_type.
- **Connections:** depends-on core-investing; shares-data jars/kids/super (per-account); fed by deposits/roundups/recurring/rewards/fees; sibling My-Finance; feeds milestones; depends-on auth.
- **test_implications:** Seed settled Holdings so balance>0 (NoContent='--'). KNOWN GOTCHA: gen users have no EOD price history → graph series/Δ/% INVALID; assert tile presence/format + pills selectable, NOT numbers. Range pills are non-clickable TextViews in clickable parent (target parent). Value = clickable $ TextView; change = non-clickable sibling. Same surface for Main/Jar/Kid/Super — seed/select account first (test account HAS jars/kids). History rows async — wait_for_rows. 'Buy' rows come from 'Lump Sum' filter (no 'Buy' filter). requested_days 1/30/91/182/365/nil(All).

### raiz-kids
- **Purpose:** Parent opens/funds separate investment sub-accounts for children. Each kid = real separate account legally owned by parent, optionally operated by child with graduated access + weekly limit; converts to full account at 18.
- **Key screens/flows:** `raizFeatureKids` KidsList (Active/Closed), KidsInitial, KidsAgreement, KidsProfile, KidHome (balance + invest/withdraw + summary rows), KidInvest, KidSettings (+convert/close dialogs), KidsAccess/FeatureAccess (weekly limit), per-kid Recurring/Performance/Statements/Dividends, KidsWidget; nav-drawer 'Kids' (feature-flag gated).
- **Backend:** `DependentUser` (link row: belongs_to dependent_user(::User) + user(parent); avatar_id, investing_weekly_limit, token, notifications store_accessor, converted_to_parent?), `User#child_dependent_users`/`child_users`(type_dependent)/`parent_user`. API `dependency_users/v1`: POST/PUT/GET `/users`, `/users/summary`, close, convert_to_full, reopen, resend_signup_email; POST `/investments` (Credit/DebitCreator); POST `/transfers` (target dependent|owner); per-kid portfolios/recurring/notifications/statements. Services Creator/Updater/Closer/Reopener/`FullAccountConverter` (age>=18).
- **Deep links:** `raiz://kids`, `raiz://kids/details/{details_kid_id}`.
- **Appium hooks (text=; testTag absent, only contentDescription 'Reactivate'):** 'Raiz Kids', 'Active'/'Closed', 'Manage account', 'Add a Raiz Kid now', 'Invest now'/'Withdraw now', 'Initial Investment Amount', 'Raiz Kids Balance'/'Amount Invested:'/'Market Returns:'/'Referrals:'/'Reinvested Dividends:'/'Raiz Rewards:'/'Withdrawn:', 'Raiz Kid Access', 'Update Profile', 'There are no closed kids' accounts.', contentDescription 'Reactivate'.
- **Seedable/assertable:** DependentUser investing_weekly_limit/avatar_id/token/notifications; access flags (investing, manage_recurring_and_goals, manage_portfolio, account_access, rewards); kid profile name/date_of_birth(<18 vs >=18 gating)/email/user_type='dependent'/closed_at; KidHome summary values; per-kid portfolio + recurring_deposit_setting.
- **Connections:** depends-on auth (dependent User); feeds/shares core-investing; mutual deposits (transfers); recurring; depends-on performance; feeds rewards (flag) + roundups; sibling jars; depends-on notifications; gated by plans-fees Kid limitation; My-Finance insights via dependent_user_id; milestones badges on parent.
- **test_implications:** Seed via `dependency_users/v1` as PARENT (account HAS kids — assert seeded set). Create: POST `/users` name+dob+email+ (avatar_id|file). Access via PUT `/users` dependent_user hash. Fund via POST `/investments` + `/transfers`. DOB load-bearing (>=18 enables convert_to_full). Closed-account: POST `/close` then 'Closed' tab + 'Reactivate'. Gotchas: nav entry feature-flag gated; text= XPath only; gen kids no price history (assert balance/invested, not market-returns %); scope type_dependent so jars don't leak; funds belong to parent (convert/transfer is the real flow).

### raiz-jars
- **Purpose:** Goal-based savings sub-accounts (named Jars w/ optional target + icon + own portfolio). Money transferred in is invested toward the goal with progress tracking. Each jar = full investing sub-account off the parent.
- **Key screens/flows:** `raizFeatureJars` `JarsFragment`/`JarsNavHost`; initial router (Create|Details(jarId)|List); list (Active/Closed, promo jar); create wizard (customise icon/name → 'Set goal amount'[Skip] → portfolio confirm); jar home (balance, JarProgress ring, history); invest/withdraw; per-jar recurring (reuses recurringv2); edit; settings (close); performance/dividends/statements; verification/funding sub-flows; widgets.
- **Backend:** `Jar` (belongs_to user + jar_user; name+saving_amount(0..10_000_000_000); additional_data:promoted bonus_10; icon_id), `User#jars`/`jar_users`(through jars)/`jar`(when self IS jar)/`parent_jar_user`; `user_account_types` jar_user?, investing_accounts=[self]+child_users+jar_users. Services `Jars::BaseCreator` (creates jar_user USER_TYPE_JAR, dupes portfolio via `Portfolios::Custom::Duper`; validates regular_suitable/adult/verified/linked_funding/portfolio/jars_limit/unique-name), `Creator`/`Promo::Creator`, credit/debit creators, `SubaccountClosureInitiator`. API `jars/v1`: Users (POST create name+icon_id, list, PUT update, DELETE close, promo), Transfers (jar_user_id, amount, target jar|owner), Investments (LumpSum credit/debit, summary, present), RecurringDepositSettings, Portfolios (set_portfolio), AllocationProfiles, Settings, Statements.
- **Deep links:** `raiz://jars` (empty → 'Customise your Jar' create form; with jars → list; Details(jarId) → jar home).
- **Appium hooks (NO testTags, contentDescription=null; on-device text only):** 'Raiz Jars', 'Active'/'Closed', 'Manage Jar', 'Customise your Jar', 'Create Jar', 'Set recurring investments', 'Set goal amount', 'Skip', 'Oops!'/'Ok', name field = EditText by class.
- **Seedable/assertable:** Jar.name(unique per parent)/saving_amount(goal)/icon_id/jar_user_id/additional_data.promoted; JarData accumulatedAmount→getProgress=accumulated/saving*100; closed/portfolioName/dailyChange; JarRecurringData; JarsSummaryResponse (invested_by_you/withdrawals/reinvested_dividends/gain_loss/total_found_money_rewarded/total_referrals_rewarded); JarTransferModel JAR/OWNER.
- **Connections:** depends-on core-investing (dupes parent portfolio, requires it); sibling kids; mutual deposits (transfers) + recurring; fed by roundups + rewards summary; feeds performance; milestone nav + badges; depends-on auth; gated by plans-fees Jar limitation.
- **test_implications:** Jar requires parent verified+adult+linked-funding+EXISTING portfolio before Creator succeeds — bare gen user can't create one. Seed >=1 jar_user via POST `/jars/v1/users` (name+icon_id, optional saving_amount); seed goal AND balance (transfers target 'jar' / LumpSum) for a non-zero ring. Gen jars no price history (assert balance/goal, not deltas). Jar inflates parent investing_accounts_balance. Closing runs SubaccountClosureInitiator (liquidates; errors if closure/withdrawal pending). `raiz://jars` empty → create form (no list). Locate by text. Name unique per parent; jars_limit_number caps creation (re-runs can hit limit).

### raiz-rewards
- **Purpose:** Partner cashback — shop with brands, earn cash rewards auto-invested into portfolio. Reward starts pending, confirms (~100 days) → settles into an investment. Online purchases auto-tracked via a linked Round-Up account.
- **Key screens/flows:** `raizFeatureRewards` `RewardsFragment`+`RewardsNavHost` (WebView-backed, `provideWebAppUrl`); main Earn/Track tabs (Track sub-tabs All/Invested/Pending); Earn carousels + 'Rewards invested' header + payment-connect prompt; offer detail → Terms/BrandStore/PureProfile survey/GiftCard; Linked Accounts; Search (sort); KidsAccessDenied; cross-surfaces (Home tile, main-portfolio Rewards row, drawer).
- **Backend:** `Reward` (belongs_to user(user_uuid) + credit_investment; AASM pending/confirmed/cancelled/closed; `confirm_reward`→do_settle!; scopes pokitpal/offer_system/referral/...), `CreditInvestment` (INVESTMENT_TYPE_REWARD, has_one reward), `UserRewards` (instore_rewards, external_rewards_eligible?), `User has_many :rewards`, `OfferSystem::UserAccount`/`UserOffers::Account`, `OfferRewardRequest`/`OfferRewardBatch`. Endpoints: admin `rewards` (offer_system/pokitpal/manual/upload/monthly_breakdown_csv), `offers` namespace, reward_creation/confirm_reward_creation/reward_investments, `move_super_rewards`.
- **Deep links:** `raiz://raiz_rewards`(+`?destination=tabAuto|category|details&offerId=|accounts|surveys`).
- **Appium hooks:** text 'Earn'/'Track', 'All'/'Invested'/'Pending', 'Rewards invested', 'Pending rewards', 'Rewards', 'Raiz Rewards', sort 'Most Popular'/'Most Cashback (%)'/'Most Cashback ($)'; **testTags** 'RewardsEarnHeader_Root'/'_Value', 'RewardsEarnFeaturedList_Root'/'_Automatic'/'_Manual', 'RewardsEarnBoostedList_Root'/'_Items', 'RewardsEarnSurveysList_Carousel', 'RewardsEarnSurveyItem_Root'; analytics 'found_raiz_rewards'. (Offer/brand content is remote WebView — brittle.)
- **Seedable/assertable:** reward.amount; aasm_state (pending→Pending tab; confirmed/settled→Invested + portfolio Rewards row); reward_type (pokitpal/offer_system/instore/online/referral/...); settled_at; credit_investment_id; additional_data{offer_id,partner_name,order_date,campaign_type,reward_tracking_source}; external_id; user_uuid; credit_investment batch_effective_date/batch_number; UserOffers::Account.
- **Connections:** feeds core-investing (settle); depends-on roundups (auto-track linked account); depends-on kids (parent-only eligibility); feeds super (move_super_rewards); depends-on auth; shares-data milestones (referral) + deposits (settlement machinery) + My-Finance (rewards:true link).
- **test_implications:** WebView-backed → prefer native hooks (tab text + testTags). Seed Reward rows: amount + aasm_state (pending vs confirmed/settled) + reward_type + additional_data. Confirming settles credit_investment (raises portfolio value — account for it). Eligibility: kids/jar NOT eligible (KidsAccessDenied); rewards attach to PARENT user_uuid — never seed on sub-account. Auto-tracking needs linked Round-Up account. Deep links jump straight to surfaces.

### raiz-super
- **Purpose:** In-app superannuation — separate super account alongside regular invest. Register/verify (TFN+ID), choose super portfolio, see balance/holdings, make voluntary contributions (lump-sum/recurring/reward), find & consolidate external funds (rollover), insurance opt-in/out, dividends/statements; SMSF users view fund/member details.
- **Key screens/flows:** `raizFeatureSuper` `SuperFragment`+`SuperNavHost` (~25 destinations); Super Home hub (Account Info, Find My Super, Insurance, Portfolio, Dividends, Invest a Lump Sum, Recurring/Reward contribution); onboarding (Verification/UploadPhoto/TfnGender/InsuranceConsent/RegistrationComplete); deposit; rollover/Find My Super (Consolidate/History); insurance; personal info (TFN/membership/BPAY); portfolio; performance (PerformanceScreenArgs.Super); dividends/statements/documents; rewards-into-super; SMSF viewer `raizFeatureSmsf` (Information/Member-Director, read-only); nav-drawer 'Super' (flag gated).
- **Backend:** `User has_one :super_annuation_account` (after_create when super_annuation_user; funding_user→regular_user), `SuperAnnuationAccount` (status MATCHED/NOT_MATCHED/...; balance fields super_guarantee/holdings/...), `SuperAnnuationSubaccount` (status pending/complete/failed, usi), `SuperAnnuationIncomingTransaction` ('Rollover In'→Investment), `SuperFund<Bill` (BPAY), `SuperAnnuationInsuranceCheck`, `SuperAnnuationFund` (USI directory), `Investment` scope :super_annuation (super_rollover?/super_contribution?). API `super_annuation/v1` + `smsf/v1`; customer_ledgers super_annuation show/create/retry/order_buy/sell/toggle_insurance/close/reopen/request_supermatch/super_user_verifications; subaccounts reset_rollover/request_rollover; insurance/contribution_reports.
- **Deep links:** `raiz://raiz_super/{page}?channel=`, `/home`, `/account_info`, bare (→home; →raiz://home if flag off).
- **Appium hooks (NO testTag/contentDescription — visible text only):** 'Super', 'Super Account Info', 'Find My Super', 'Insurance', 'Portfolio', 'Dividends', 'Invest a Lump Sum', 'Recurring contribution', 'Reward contribution', 'Consolidate funds'/'History', 'Rollover'/'Add manually', 'Rollover Acknowledgement', 'Opt In'/'Opt Out'/'Opted In/Out', 'Member Name'/'TFN Number'/'Fund Name'/'Fund USI'/'Biller Code:'/'Ref:', 'Fix', 'Important Documents'; SMSF tabs 'Information'/'Member/Director'.
- **Seedable/assertable:** super_annuation_accounts.status/member_number/balance decimals; subaccounts status='complete'/usi; incoming_transactions amount/transaction_type='Rollover In'/investment_id; super_funds BPAY biller; insurance_checks status+freshness; user_type=USER_TYPE_SUPER_ANNUATION; verify code DEV '1111'; Investment super flags.
- **Connections:** depends-on auth (own verification); depends-on core-investing (sub-account funded by regular, activity=Investments); fed by deposits (lump/BPAY) + recurring + rewards; shares-data performance; fed by My-Finance Find-My-Super rollover; depends-on notifications (deep links); parallel jars; fed by plans-fees (super fees).
- **test_implications:** Feature-flag gated — if off, drawer hidden + `raiz://raiz_super`→home. Need BOTH regular (funding) account w/ balance AND super sub-account; seed status='MATCHED'+member_number else not-matched states. Seed balance decimals + subaccount status='complete'+usi→fund. Contributions/rollovers/rewards = Investment rows (assert there). Find My Super: seed super_annuation_funds + expect 'Rollover In'. Insurance toggle reads freshness window. DEV verify '1111'. NO testTag/contentDescription → target text. Gen super no price history → perf/Δ invalid. SMSF viewer read-only, SMSF-type only.

### money-myfinance
- **Purpose:** Financial-aggregation + insights hub. After linking external accounts (Yodlee/FastLink CDR): 'My net worth' (investments + super), category spending, monthly tracker vs average, 30-day forecast, transaction categorisation, curated lists (biggest/subscriptions/BNPL), financial-insight steps widget, smart actions, savings goals.
- **Key screens/flows:** `features/financev2` `MyFinanceScreen.kt`+VM; MyNetWorthCard; CategorySpendingCard + 'Where You Spend'; MonthlyTrackerCard; ForecastCard + Forecast screen; CategoriseTransactionsScreen + change dialog; SmartActionsRow (ConnectMoreAccounts/ReviewRecentCategories/UpdateYourGoals); TransactionsCard; MyFinanceStepsScreen (feature/steps StepsWidget).
- **Backend:** `AggregationSubaccount` (belongs_to user + aggregation_account(YodleeMonitoredSite); scopes :roundup/:financial_insight/:rewards/:linked/:analytics=active.financial_insight; #transactions by yodlee_item_account_id), `YodleeMonitoredSite`, `SpendingAnalyticsCategoryTotal` (category/amount/count), `SpendingAnalyticsGoal` (status/frequency/target_amount/current_percent; calc uses current_balance + recurring prefs), `SpendingAnalyticsRecommendation`, `User#spend_analytics_transactions`. API `spending_analytics` (GET/PUT settings, getgoals, create/update/deletegoal, categories_averages, catch-all proxy; all accept dependent_user_id); internal spending_analytics; aggregation_limits; spending_goals.
- **Deep links:** `raiz://finance`, `raiz://finance_v2`, `raiz://spending_account`, `raiz://linked_accounts`, `raiz://fastlink_connect`, `raiz://transactions`.
- **Appium hooks (almost no contentDescription/testTag — visible text):** 'My Finance', 'INSIGHTS AND HABITS', 'My net worth', 'Total in investments', 'Total in Superannuation', 'Monthly tracker', 'Categorise Transactions', 'Forecast', 'SMART ACTIONS', 'Connect more accounts'/'Review recent categories'/'Update your goals', 'Biggest transactions last month', 'Subscriptions last month', 'BNPL debts last month', 'Set up your financial insights', 'Where You Spend', 'Choose Category', 'Transaction Categorisation' (tabs All/Uncategorised), 'Your potential spare cash in 30 days'/'Assumed Transactions', 'You have no transactions' (empty oracle).
- **Seedable/assertable:** AggregationSubaccount roundup/financial_insight/rewards/is_deleted/bank_account_token/last_synchronized_at; investingAccountsBalance→'Total in investments'; superCurrentBalance→'Total in Superannuation'; FinanceSummaryResponse monthlyTracker/forecast/categorySpending/biggestTransactions/subscriptions/buyNowPayLater; SpendingAnalyticsCategoryTotal; SpendingAnalyticsGoal; financial_insight_steps_state jsonb; Transaction yodlee_item_account_id/investment_id.
- **Connections:** shares-data roundups+rewards (same link); depends-on core-investing + super (net-worth rows) + recurring (goal defaults); shares-data kids (dependent_user_id) + deposits (Transaction ledger); depends-on/navigates milestones (steps); depends-on auth (FastLink gate).
- **test_implications:** Gated on linked external accounts: needs AggregationSubaccount financial_insight:true + last_synchronized_at + categorised transactions, else empty states + net-worth 0. 'My net worth' is CROSS-FEATURE (investments row = investing balance, super row = super balance) — seed those. Same account serves roundups/rewards/insights — isolate. Forecast/tracker computed client-side from seeded values. dependent_user_id → kid insights. Gen users lack txn history — seed explicitly.

### plans-fees
- **Purpose:** See/change subscription tier (Starter/'Lite', Regular, Plus) + review monthly fees. Plan determines fee, accessible portfolios, Kids/Jars eligibility, balance cap; tracks fee-rebate qualification (deposit + no-withdrawal monthly) + rebate history.
- **Key screens/flows:** `features/pricing` SelectPlanScreen (tier pager, Change-plan, confirm/congrats, rebate progress), PlansAndFeesScreen (fee list + 'Pricing plan' row), SelectPlanHistoryScreen (rebate history); PricingFragment maps PlansFees→PlansAndFees, Plans→SelectPlan; legacy SettingsFragment path.
- **Backend:** `Plan` (STARTER/REGULAR/PLUS enum; PLAN_HIERARCHY upgrade?/downgrade?; available_for_user_types; for_user_type scope), `UserPlan` (belongs_to user+plan; scope :active start_at<=now & end_at>=now/null; #limitations), `User has_one :active_user_plan/:plan/#current_plan/:eligible_for_rebate`, `Fee` (flat/aum; AASM new/pending/confirmed/collected; scopes monthly/monthly_kids), `FeeInvestment<Investment` (from_fee; ready_for_collecting joins verified fee-eligible FundingSource), `Bill`. Facade `Plans::ApiShowFacade` (name/details/price/available_portfolios/current_plan?). Services `UserPlans::Updater` (ends current, creates new, clears rebate, emails), limitations/{portfolio,plus_portfolio,kid,jar}, starter/limitations/balance (1500 cap), starter/rebate_conditions (deposit>=30 + no_withdrawal). Endpoints: GET `/v2/plans?sign_up=`, GET `/v1/user_plans/active`, POST `/v1/user_plans/:id`, GET rebate_conditions_history.
- **Deep links:** `raiz://plans`, `raiz://plans/{planId}`, `raiz://plans/{planId}?ref=` (host remote-config gated).
- **Appium hooks (Compose, NO testTag/contentDescription — text):** 'Plans and fees', 'Pricing plan', 'PLAN', 'Pricing plans', 'Current plan', 'Change plan', 'Confirm plan change', 'Keep current plan', 'Plan change confirmed', 'Rebate history'. (Plan names/prices server-driven from /v2/plans — text match.)
- **Seedable/assertable:** Plan.identifier (starter|regular|plus; 'lite'=marketing name for starter)/name/order_position; UserPlan.start_at/end_at (active window — seed to set tier); User.eligible_for_rebate; Fee.fee_type/amount/status/fee_collection_type(monthly|monthly_kids|super_annuation_transaction); FeeInvestment.additional_info (fee_id/fee_type/fee_user_type/funding_user_id); available_portfolios; Starter balance cap 1500; rebate MINIMUM_MONTHLY_INVESTMENT=30 [:deposit,:no_withdrawal]; Setting.lite_plan_rebate_months.
- **Connections:** feeds core-investing (portfolio gating + FeeInvestment sells); feeds kids+jars (limitations); depends-on deposits (fee collection from funding source); fed by roundups+recurring (rebate deposit condition); shares-data super (super fees + user_type filtering); depends-on auth (UserPlan + PlanPicker); feeds notifications (upgrade/downgrade email); feeds performance (fee sells reduce balance + 'Fee' rows).
- **test_implications:** Seed UserPlan active window to put user on a tier. Plan gates portfolios + Kids/Jars + balance cap (Starter 1500). Fees = FeeInvestment (Investment subclass, sells shares) collected from verified fee-eligible funding source. Rebate: deposit>=$30/mo + no withdrawal. Plan change ends old + creates new UserPlan (CustomerAction + email). Server-driven names — assert via text. (Note: source map's test_implications field was 'duplicate' — derived here from data_entities + connections.)

### auth-onboarding — THE GATE
- **Purpose:** Account creation + per-launch re-auth. Sign-up (email/password, details, address, consents), KYC (doc upload + selfie liveness + status poll), device registration + SMS OTP, create 4-digit PIN, on every open re-auth via PIN/biometric. No verified+PIN'd session → no feature.
- **Key screens/flows:** `raizFeatureSignUp` SplashIntro/SignUp/Login/Forgot+Reset/EmailVerification/VerifyDevice(SMS auto-fill)/CreatePin; app `com.raiz.pin/EnterPinScreen.kt` (10-key keypad); biometric unlock (`BiometricPromptUtils.kt`); ChangePin in settings; onboarding steps/Personal/Address/Consent; KYC upload + status poll ('Hang tight! Verifying your identity.'); PlanPicker.
- **Backend:** `User` (pin, verified, EMAIL_REGEXP, registration_steps_state jsonb, user_type), `AuthenticationToken` (polymorphic; bearer 'Authorization: token <key>'), `Device` (udid unique per user), `Otp`, `UserPassword`, `IdentityVerificationResponse` (+additional_input/biometric_input; status pending/completed), `AcceptanceDocument`/`UserAgreement`. Endpoints: POST `/v1/sessions` (udid+email+password→token), POST `/v1/sessions/authorize` (PIN; 401 maxed_out_pin_attempts/403 incorrect_pin), POST `/v1/otp/verify/sign-in`+`/authorize`, POST `/v1/user/pin`, verify_pins, reset_pin (PinRateLimiter), recover/reset/change_password, POST `/internal/v1/test_data_generation` (traits).
- **Deep links:** `raiz://home` (post-auth landing), funding_account/invest/main_portfolio/future/withdraw_v2/history/notifications_settings/milestone. NOTE: signup/login/PIN have NO raiz:// host — a deep link while locked lands on EnterPin first.
- **Appium hooks (Compose text=, no stable contentDescription/testTag):** 'Log in to Raiz', 'Login', 'Forgot your password?', 'Email address'/'Raiz password', 'Enter your PIN', 'Log Out', PIN keypad = clickable View w/ TextView '0'..'9' + `keypad_image_delete`, 'Create your Raiz account'/'Create Account', 'Add Personal Details', 'I consent', 'Hang tight! Verifying your identity.', 'Verify'/'Next'/'Skip', 'Security Question'.
- **Seedable/assertable:** User.email/password/pin(4-digit)/verified(gates check_user_access)/user_type; registration_steps_state; Device.udid; AuthenticationToken.key; Otp.otp_session_token+otp_code; IdentityVerificationResponse.status; AcceptanceDocument; gen-API traits :verified, :has_portfolio, :with_user_profile, :with_funding_source, :with_active_plan, :kid_account, :jar_account.
- **Connections:** GATE — feeds/depends-on every feature; sub-Users (kid/jar/super) hang off parent verified User.
- **test_implications:** Universal precondition; conftest walks splash→login→PIN→home, dismisses biometric enrol (always No). GOTCHA 1 PIN lockout (PinRateLimiter / 'Too many attempts') trips under heavy/parallel entry → whole suite ERRORS at login; conftest recovers via credential re-login; serialize credential logins. GOTCHA 2 login burst rate-limit IP-level on /v1/sessions — mint gen-API token ONCE + reuse. Seed: POST `/internal/v1/test_data_generation` minimum [verified, with_user_profile]; add has_portfolio/with_funding_source/with_active_plan/kid_account/jar_account. Gen users log in with @emel.xyz + Pass1234. GET /v1/user nests under 'user'. Closing parent cascades to kids/jars. Text= only locators. No deep link for signup/login/PIN.

### notifications
- **Purpose:** In-app inbox + push/SMS. Paginated pull-to-refresh list, open to read, 'More Info' deep-link into product screen, mark read individually/all, manage push categories, device push registration, per-kid notification control.
- **Key screens/flows:** `features/notificationsv2` inbox (`NotificationsInboxScreen.kt`, paginated, Read All) + legacy `raizFeatureNotifications/list`; detail (`NotificationDetailsScreen.kt`, conditional 'More Info'); settings toggles; per-item row (read/unread icon).
- **Backend:** `Notification` (STI MobileNotification|SMSNotification; status sent/draft; kind=marketing; priority; deep_link; receivers_ids), `MobileNotification` (subject<=25), `SMSNotification`, `UserNotification` (per-user delivered; scopes sent/unseen/seen/visible; sent_at/seen_at/data{title,body,deep_link_url,hidden}; DEEP_LINK_URL_DEFAULT='raiz://home'), `UserNotificationsPreference` (DEFAULT_PREFERENCES general.account_updates.{auto_round_up,account_approved,recurring_deposit,monitored_institution_response_code}, referrals.referrer_rewarded, marketing.updates), `SpendingAnalyticsRecommendation` (has_one user_notification as source). Endpoints: GET `/v1/notifications` (offset/limit/filter, last 3 months, includes source), PATCH /seen, /seen_all, POST /register_device, GET+PUT /preferences, POST /send; `dependency_users/.../notifications/:dependent_user_id` (Kids).
- **Deep links:** `raiz://home`, `raiz://offer_details?id=`, `raiz://raiz_super`, `raiz://raiz_rewards`, `raiz://notifications`.
- **Appium hooks:** **testTag** 'icon'/'arrowIcon'/'backButton'/'readAllButton'; text 'Notifications', 'Read All', 'More Info', "You don't have any notifications", "Can't load notifications", "Are you sure you want to mark all notifications as read?", "You don't have any notification settings".
- **Seedable/assertable:** UserNotification.sent_at(non-null to appear)/seen_at(null=unread)/data['title','body','deep_link_url','hidden']; unseen_count; Notification.type/priority/kind/scheduled_at; UserNotificationsPreference.preferences hash; device_uuid+device_token.
- **Connections:** navigates-to rewards/super; fed by My-Finance recommendations + roundups + recurring; shares-data kids (separate endpoint); depends-on auth; navigates core-investing (home) + milestones (achievements).
- **test_implications:** Seed UserNotification w/ sent_at set, source_type, data{title,body,deep_link_url}; seen_at null for unread/Read All. Only last-3-months + non-hidden returned; unseen_count counts those. Paginated (limit 50) — assert via paging. 'More Info' only renders when deep_link_url non-empty (seed raiz://offer_details / raiz://raiz_super / raiz://home for cross-feature nav). PATCH /seen mutates server-side — re-seed between runs. Two impls coexist. Account drift: prefs default true + account may have real notifications polluting empty-state. Kids toggles use separate dependent_user_id endpoint.

### milestones-gamification
- **Purpose:** Three engagement surfaces: (1) Milestones — auto-generated $ balance targets that auto-complete as balance grows + 'fastest ways to get there' nudges; (2) Steps — getting-started/insights checklist; (3) Achievements — collectible badges for actions+balances across the product.
- **Key screens/flows:** `features/milestone` overview (carousel + actions), edit, widget (on redesign home); `features/steps` checklist + widget (on MyFinance + redesign home); `raizFeatureAchievements` list + details dialog + widget; nav-drawer 'Achievements' (flag gated).
- **Backend:** `Milestone` (belongs_to user; .completed/.active; system_generated?/custom? via original_system_amount), `User has_one :active_milestone`, `Accomplishment::Definition` (category+identifier+rank; CATEGORY_ORDER goals/round_ups/raiz_rewards/raiz_kids/jars/raiz_super/account_age/dividends/...), `Accomplishment::Badge` (user+definition unique; .not_accomplished), `UserAccomplishments`. Services `Milestones::Conductor` (Creator→Completer auto-advance), Creator (target from investing_accounts_balance), Updater (validate_amount_above_current_balance!), `Accomplishments::Trackable#accomp_trackable` (prepended onto other features), Tracker/Scheduler/Applier, definitions/* (balance_based, action_based_events/{jar_created,recurring_deposit_set,kid_money_transferred,super_matched,roundup_changed,goal_created,portfolio_switched}), `Steps::Fetcher` (registration/account_setup/financial_insight). Endpoints: GET/PATCH `/v3/milestones`(+/current), GET/PATCH `/v1/accomplishments`(+/presented), GET/PATCH `/v3/account_setup_steps`.
- **Deep links:** `raiz://milestone` (only if redesign flag; else HOME), `raiz://achievements` (only if achievements flag; else HOME).
- **Appium hooks (contentDescription=null on all icons; visible text + ONE dynamic contentDescription):** 'Milestone overview', 'Edit', 'Fastest ways to get there:', 'Milestone', 'Your first/next milestone', 'Edit milestone', 'Customize your next milestone', 'Achievements', 'Raiz Achievements', 'View all', 'Unlock your first achievement', 'Discover', 'Set up your financial insights', 'All steps completed', 'TO DO'/'DONE', 'X of Y done/completed', 'View All'; contentDescription 'Mark <name> as done'.
- **Seedable/assertable:** Milestone.amount/original_system_amount(null=system)/completed_at(null=active)/initial; v3 entity id/title/amount/completed/initial; Accomplishment::Definition category/identifier/rank/repeatable; Accomplishment::Badge presented_at(null=unpresented→badge_count)/completed_at/count; account_setup step identifier/completed/changeable.
- **Connections:** depends-on core-investing + deposits (balance-driven); fed by roundups/recurring/jars/kids/super/rewards/performance (cross-feature actions award badges); feeds notifications; depends-on auth (steps + account_age + whitelist/regular-only); navigates My-Finance (steps widget).
- **test_implications:** (1) MILESTONES WHITELIST-GATED — `Setting.milestones_test_user_emails` + regular_user; non-whitelisted → no milestone + widget hidden. (2) milestone widget + `raiz://milestone` only when redesign flag (3226 vs 3223 legacy). (3) `raiz://achievements` gated by achievements flag. (4) Milestone amounts auto-advance on balance change; PATCH rejects amount below current balance (422). (5) Badges awarded ASYNC — seed cross-feature action then allow job processing (Scheduler/Tracker/Applier). Gen users no price history → dividend/balance badges + milestone progression may be invalid. (6) contentDescription=null → text only + 'Mark <name> as done'. Badge stays unpresented (drives badge_count) until PATCH /presented.

---

## (d) For test authors — VALUE/STATE oracle cheat-sheet

The connections above enable cross-feature oracles far stronger than single-screen presence checks. Highest-value ones, per feature:

| Feature | Connection-enabled VALUE/STATE oracle | Why it holds (evidence) |
|---|---|---|
| **core-investing** | **Money conservation across Main↔Jar↔Kid↔Super:** parent `investing_accounts_balance` = `[self]+child_users+jar_users` balances; an owner→jar/kid transfer must DECREASE one and INCREASE the other by the same amount (net parent balance unchanged for a transfer, increased for a fresh deposit). | `user_account_types.rb:investing_accounts`; transfers `target jar|owner|dependent` |
| **core-investing** | Any seeded inflow (lump-sum/round-up/recurring/reward) appears as an `Investment` row of the matching `investment_type` AND raises main-portfolio value AND adds a typed Transaction-History row — assert all three together. | `investment.rb:INVESTMENT_TYPE_*`; transaction_history filter types |
| **roundups** | **Round-ups fund main:** a settled RoundUp/AutoRoundUp `CreditInvestment` increases portfolio value + posts a 'Round-Ups' history row; `round_up_investment_amount.invested` should reconcile to the sum of settled round-up credits. On gen users (no real txns) assert CONFIG (multiplier/threshold/auto), not dollars. | `credit_investment.rb` scope :round_up; perf 'Round-Ups' filter |
| **recurring** | A same-day-eligible recurring setup creates exactly one `AutoInvestment` credit that moves balance + history; otherwise `next_investment_at` matches the day-rule shape (don't hard-assert the date). | `recurring_deposit/investor.rb`; IceCube schedule |
| **deposits-withdrawals** | **Withdrawal cap:** a withdraw request > `available_amount_to_withdraw` (= current_balance − pending_withdraws) must be rejected/insufficient_funds; a valid one yields 'Withdrawal Confirmed' but NOT immediate settled balance change (1-5 day async). | `user_investments.rb:available_amount_to_withdraw`; DebitInvestment AASM |
| **deposits-withdrawals** | **Destination routing:** seeding a deposit to a Kid vs Jar vs Main must change ONLY that account's balance (different creators) — cross-check the other accounts are unchanged. | `AccountType` + jars/dependent_users creators |
| **portfolio-performance** | **Per-account value reconciliation:** Main/Jar/Kid/Super value tiles each equal their account's `account_balance` (summary.last[:balance]); NoContent shows '--'. Δ/% INVALID on gen users — assert tile presence + pills selectable only. | `PerformanceGraphBuilder::General#account_balance`; genuser gap |
| **raiz-kids** | Kid summary rows (Amount Invested / Withdrawn / Market Returns) should reconcile invested−withdrawn against KidHome balance; rewards row non-zero only if rewards flag enabled. Funds belong to parent (convert/transfer at 18, not auto-keep). | dependency_users investments/transfers; FullAccountConverter |
| **raiz-jars** | **Goal ring oracle:** progress = accumulatedAmount / saving_amount × 100 — seed both, assert the ring; jar balance also inflates parent `investing_accounts_balance`. | `JarData.getProgress`; investing_accounts |
| **raiz-rewards** | **Reward routes to the right product:** confirming a reward calls `credit_investment.do_settle!` → portfolio 'Rewards' breakdown row + Invested tab; pending → Pending tab only. Seed pending vs confirmed to drive the two tabs. Never on a sub-account (parent user_uuid only). | `reward.rb:confirm_reward`; MainPortfolioInvested |
| **raiz-super** | Contributions/rollovers/rewards-into-super all materialize as `Investment` rows (super_annuation scope) and raise super balance → which is exactly the 'Total in Superannuation' net-worth row. 'Rollover In' incoming transactions link to an investment_id. | `investment.rb` super scopes; SuperAnnuationIncomingTransaction |
| **money-myfinance** | **Net-worth is cross-feature:** 'Total in investments' == sum of investing accounts balance; 'Total in Superannuation' == super balance — asserting these validates core-investing + super state, not aggregation data. Spend/forecast need explicitly seeded synced transactions or they collapse to empty/0. | `FinanceMainScreenState` totals; AggregationSubaccount :analytics |
| **plans-fees** | **Fees conserve into the ledger:** a monthly fee is a `FeeInvestment < Investment` (a SELL) that reduces balance + posts a 'Fee' history row; plan tier change re-gates accessible portfolios + Kids/Jars; rebate qualifies on deposit≥$30 AND no withdrawal that month. | `fee_investment.rb < Investment`; rebate_conditions |
| **auth-onboarding** | `verified=true` is the single switch that passes `check_user_access` and unlocks all features; an unverified seeded user must be blocked at the API. Closing the parent cascades to kids/jars (sub-Users). | `authentication.rb:check_user_access`; dependent destroy cascade |
| **notifications** | A seeded UserNotification with a non-empty `deep_link_url` must render 'More Info' and route to the matching product screen (offer_details→rewards, raiz_super→super, home→main); unseen_count must equal the count of sent+visible+unseen-within-3-months rows. | `user_notification.rb` data + unseen scope; details VM routing |
| **milestones-gamification** | Milestone target auto-completes when `investing_accounts_balance` crosses it (assert against LIVE balance); a cross-feature action (jar_created/recurring_deposit_set/kid_money_transferred/roundup_changed) awards its badge ASYNC after job processing. Both are whitelist/flag-gated — verify gating first. | Conductor Creator/Completer; Accomplishments::Trackable |

**Universal gotchas baked into every oracle:** (1) generated/fresh users have NO EOD price history → any performance/Δ/%/dividend/market-return number is invalid; assert balances, invested/withdrawn totals, config, and structure instead. (2) The test account already HAS kids/jars/linked-funding/insights/rewards (state drift) → 'empty account' assumptions fail; assert against the seeded set. (3) Two home layouts (3223 legacy 'Main portfolio' vs 3226 redesign 'Invest'); the redesign flag also gates milestone widget + `raiz://milestone`. (4) Most Compose screens expose only visible `text=` (contentDescription/testTag sparse — notable exceptions: Rewards `RewardsEarn*` testTags, Notifications icon/arrowIcon/backButton/readAllButton, the single milestone 'Mark <name> as done' contentDescription). (5) Range pills, Filter, Add funds/Withdraw/Invest are non-clickable TextViews inside clickable parent Views — target the `@clickable='true'` parent.

---

## Completeness gaps & follow-ups

**Asserted by one side only (one-directional in source maps — confirm the reverse before relying on it):**
- **roundups → notifications** (auto_round_up push, threshold re-cache job) is asserted by roundups but the notifications map lists roundups only as a preference category, not a delivery edge — confirm round-up events actually generate inbox rows.
- **recurring → notifications** (auto-investment-changed email + RecurringDeposit push) asserted by recurring; notifications map only names the `recurring_deposit` preference — confirm the push/inbox row.
- **plans-fees → notifications** (upgrade/downgrade email) asserted by plans-fees; notifications map does not list a plan edge — likely email-only (no inbox row); confirm.
- **deposits-withdrawals → notifications** (link/unlink + NSF suspension emails) asserted by deposits; notifications map silent — confirm whether these surface in-app.
- **milestones → notifications** (milestone-completion push) asserted by both; agree.

**Pairs that almost certainly connect but NEITHER mapped (flag for follow-up):**
- **plans-fees ↔ money-myfinance.** A 'Fee' deduction is a Transaction; My-Finance categorises Transactions and the net-worth/forecast read balances that fees reduce — yet neither map drew this edge. Likely a `feeds`/`shares-data` (fees appear in spend categorisation + reduce net-worth). Confirm.
- **plans-fees ↔ milestones-gamification.** No badge/milestone tie to plan tier was mapped, but a plan upgrade is a `CustomerAction` and other CustomerActions feed accomplishments — check whether a plan change awards any badge.
- **raiz-super ↔ milestones for Steps.** Super onboarding is a multi-step flow; Steps::Fetcher has registration/account_setup scopes — confirm whether super registration contributes step items.
- **notifications ↔ deposits-withdrawals 'account_approved'.** The `account_approved` preference is an onboarding/funding notification; mapped under auth but arguably also a deposits/funding event. Low priority.
- **money-myfinance ↔ portfolio-performance Transaction provenance.** Both consume `Transaction`, mapped as `shares-data` from the perf side and via the ledger from finance side — consistent but verify they read the SAME Transaction rows (yodlee_item_account_id vs investment_id provenance) so a categorisation change doesn't desync history.

**Structural observation:** every money-movement feature ultimately terminates at **core-investing** (the `Investment`/`Holding` ledger) and is read back through **portfolio-performance** — these two plus **auth-onboarding** (the gate) are load-bearing for almost every cross-feature oracle. A test that seeds any inflow should, by default, also assert the core-investing ledger row and the performance/history readout.
