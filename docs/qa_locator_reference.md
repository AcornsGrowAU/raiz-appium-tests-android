# Raiz AU Android — Verified Locator & Screen-State Reference

**Device:** emulator-5554 | **Build:** 2.39.1d (3223) — the LEGACY layout the suite targets
**Package:** `com.acornsau.android.development` (single activity `com.raiz.main.MainActivity`; entire app is one React/Compose surface, so `current_activity` is always `MainActivity`)
**Crawled:** 2026-06-19, one live Appium session, logged in, PIN `0000`, no_reset.
**Account state (verified live):** greeting `Hello, Jsoj`; NO active jars; NO kids; Super unfunded ($0); financial insights configured; rewards has linked CDR accounts (Dag Site US + a broken NAB link).

> **How to read this:** every screen below lists the exact on-screen `@text`, the clickable controls (text + class + bounds + resource-id), and any toggles. All text is the REAL copy captured on-device. Dollar figures drift cent-by-cent between runs (live mock backend) — never assert exact amounts; assert *well-formed money*.

---

## Cross-cutting facts (apply to most screens)

- **Compose, not native widgets.** Almost every tappable row is an `android.view.View[@clickable='true']`, NOT a `Button`. Its visible label is a *descendant* `android.widget.TextView`, so the suite's `//android.view.View[@clickable='true'][.//android.widget.TextView[@text='X']]` pattern is correct and verified.
- **`resource-id` is `null` on nearly all content.** Only Rewards exposes stable resource-ids (`RewardsEarn*`). Everywhere else, locate by `@text`. The only non-Rewards resource-ids present are the host chrome: `action_bar_root`, `android:id/content`, `drawer_layout`, `navFragment` (useless for content).
- **Header chrome buttons are the only `android.widget.Button`s on most screens:**
  - **Hamburger / back** = `(//android.widget.Button)[1]` at bounds `[0,118][147,265]` (top-left). On sub-screens this same first Button is the **back** arrow.
  - **Settings gear** (Home only) = `(//android.widget.Button)[2]` at `[954,128][1080,254]` (top-right).
  - HomePage's `HAMBURGER`/`SETTINGS_GEAR` locators are **verified correct**.
- **Every `clickable=true` View also reports `@checked='false'`** — this is why `SettingsPage.SWITCHES` (which matches `@checked` Views) returns ~15 false positives on Settings. It is NOT a real toggle list. Real toggles are ONLY on `notifications_settings` (see that section). When counting real toggles, filter by the toggle's narrow right-edge bounds, not just `@checked` presence.
- **Tabs** (`Past`/`Today`/`Future`, `Earn`/`Track`, `Personal`/`Financial`) are clickable Views at y≈129–255 (top tab strip).

---

## HOME — `raiz://home`  (lands: YES, on Home)

### Today tab (default) — verified texts
`Hello, Jsoj` · `Your total investments value` · `$1,579.53` · `2 issues that need to be solved` · `Add funds` · `Withdraw` · `Performance details` · `Rewards` · `Total investments value` · `Main Portfolio` · `$1,578.81` · `$28.81` · `Jars` · `Add` · `Kids` · `Superannuation` · `$0` · `HOW YOU INVEST` · `Milestone` · `Past` · `Today` · `Future`

### Clickables (Today)
| Label | bounds | locator note |
|-------|--------|--------------|
| Past tab | `[200,129][412,255]` | `HOME_TABS`/`TAB_PAST` OK |
| Today tab | `[434,129][646,255]` | `TAB_TODAY` OK |
| Future tab | `[668,129][880,255]` | `TAB_FUTURE` OK |
| Hamburger (Button) | `[0,118][147,265]` | `(//android.widget.Button)[1]` |
| Gear (Button) | `[954,128][1080,254]` | `(//android.widget.Button)[2]` |
| 2 issues that need to be solved | `[42,588][1038,735]` | onboarding/issues entry |
| Add funds | `[42,777][529,924]` | opens Add-funds bottom sheet |
| Withdraw | `[550,777][1038,924]` | → withdraw keypad |
| Performance details | `[42,966][1038,1113]` | → performance |
| Rewards | `[42,1116][1038,1263]` | → rewards (Home row) |
| Main Portfolio card | `[42,1444][1038,1617]` | child texts: `Main Portfolio`, `$1,578.81`, `$28.81` |
| Jars card | `[42,1620][1038,1767]` | child texts: `Jars`, `Add` → **empty state** |
| Kids card | `[42,1770][1038,1917]` | child texts: `Kids`, `Add` → **empty state** |
| Superannuation card | `[42,1920][1038,2067]` | child texts: `Superannuation`, `$0` → **unfunded** |

- **Greeting** is `Hello, Jsoj` (comma AFTER the name). `HomePage.GREETING` (`contains(@text,'Hello')`) is correct; the name-strip helper handles the trailing comma.
- **Account cards confirm data state:** Jars=`Add`, Kids=`Add` (no children/jars), Super=`$0`. `jars_card_is_empty()` / `kids_card_is_empty()` (look for `Add`) are **verified accurate**. Prefer DATA-STATE SKIPS on these.
- Cards live under the `Total investments value` section heading. All 4 cards are in the DOM at top-of-page WITHOUT scrolling on this device (screen is tall enough). `Milestone` / `HOW YOU INVEST` sit below the fold.
- The `$28.81` on the Main Portfolio card is the gain figure (green ↑), distinct from the `$1,578.81` value — a card has TWO money TextViews. `get_account_card_value()` returns the first money string inside the card container (= `$1,578.81`).

### Past tab → "Your investing journey" (same as `raiz://history`)
Texts: `Your investing journey since 2026` · `Portfolios` · `1` · `Net invested by you` · `$1,550` · `Rewards` · `$0` · `Promos & Referrals` · `Total invested to date` · `Your returns so far` · `Market return to date:` · `3.74%` · `$29.53` · `Dividends:` · `Total returns:` · **`Transaction history`** · tabs.
Clickables: `Net invested by you | $1,550` `[42,606][1038,742]`; `Rewards | $0` `[42,745][1038,881]`; **`Transaction history` `[42,1796][1038,1943]`** (the only in-app link to the real txn list besides the deep link).

### Future tab → projection (same as `raiz://future`)
Texts: `Projected Value` · `$5,282` · age ticks `18`…`38` · `Age` · `Periodic Investment` · `$20/monthly` · `Portfolio` · `Conservative` · `View my portfolio` · tabs.
Clickables: `Age | 28` `[42,1750][1038,1877]`; `Periodic Investment | $20/monthly`; `Portfolio | Conservative`; `View my portfolio` `[42,2174][1038,2300]`.

---

## INVEST / Main Portfolio — `raiz://invest`  (lands: YES)

Header value label: **`Your main portfolio's investment value`** (legacy copy; the rebrand `Invest`/`investment account value` labels are NOT present on 3223). `$1,579.53`.

Texts: `Your main portfolio's investment value` · `$1,579.53` · `Add funds` · `Withdraw` · `Performance details` · `Invested` · `You portfolio` · `Conservative` · `Net invested by you` · `$1,550` · `Rewards` · `$0` · `Promos & Referrals` · `Total invested to date` · `Performance` · `Market return to date:` · `3.74%` · `$29.53` · `Dividends:` · `Total returns:` · `Main portfolio` (toolbar title).

Clickables: `Add funds` `[42,526][529,673]`; `Withdraw` `[550,526][1038,673]`; `Performance details` `[42,715][1038,862]`; **`You portfolio | Conservative` `[42,1043][1038,1170]`**; `Net invested by you | $1,550` `[42,1173][1038,1309]`; `Rewards | $0` `[42,1312][1038,1448]`; back Button `[0,118][147,265]`.

- **CONFIRMED TYPO in app copy:** the row reads **`You portfolio`** (missing "r"), value = the portfolio NAME `Conservative`, NOT money. `MainPortfolioPage.YOU_PORTFOLIO_ROW` matches `@text='You portfolio'` — **verified correct** (keep the typo). The test `test_you_portfolio_row_value_is_well_formed` (in lastfailed) must NOT assert money on this row — its value is `Conservative` (a name). See "Test-impacting notes".
- `MainPortfolioPage.is_loaded()` `ANY_TITLE` matches `Main portfolio` (toolbar) — verified present.
- `Dividends:`, `Total returns:`, `Promos & Referrals`, `Market return to date:` are read-only summary labels, NOT clickable rows.

---

## PERFORMANCE — `raiz://performance`  (lands: YES)

Texts: `Main Portfolio investment value` · `$1,579.53` · `Change in value (All)` · `+$29.53 +3.74%` · `Total invested:` · `$1,550.00` · `Total returns:` · `$29.53` · `1D` `1M` `3M` `6M` `1Y` `All` · `The market is currently open.` · `Date: 18 June 2026` · `Performance` (title).

Clickables: headline value `$1,579.53` is itself a **clickable `android.widget.TextView`** `[0,359][1080,506]`; range tabs `1D`[74,2013] `1M`[233] `3M`[392] `6M`[551] `1Y`[710] `All`[869] (all y `2013–2123`); two tiny chart-point Views near `[461..627,2125..2252]`; back Button.

- `PerformancePage` locators verified: `TITLE='Performance'`, range-tab `TIME_*`, `MARKET_STATUS` (`contains 'market is currently'`) → real copy is `The market is currently open.` ✓. `CHANGE_IN_VALUE` (`contains 'Change in value'`) ✓.
- `INVESTMENT_VALUE_LABEL='Main Portfolio investment value'` ✓.
- NOTE: `Total invested:` label here, but the page object's `MARKET_RETURN_LABEL='Market return to date:'` is on the **Invest** screen, not Performance. Performance shows `Total invested:` / `Total returns:` only.

---

## TRANSACTIONS — `raiz://transactions`  (lands: YES, "Transaction History")

Title: `Transaction History`. Texts: `Filter` · `Buy` · `$500` · `Main Portfolio` · `07 May 2026` · `$400` · `$150` · `08 May 2026`.
Clickables: `Filter` `[0,328][226,454]`; 4 transaction rows `Buy | $<amt> | Main Portfolio` (`$500`, `$400`, `$500`, `$150`); back Button; a second top-right Button `[954,128][1080,254]`.

- Sparse text count (9) is **normal** — only ~4 rows of mock data exist. NOT a load failure. `TransactionHistoryPage.is_loaded` should key off `Transaction History` title or `Filter`.
- Deep link sometimes needs the conftest retry (already in the `transaction_history` fixture).

---

## NOTIFICATION SETTINGS — `raiz://notifications_settings`  (lands: YES, "Notifications")

Title: `Notifications`. Body: `Use this screens to modify your push notifications from Raiz.` (sic — typo "screens" is in the app).
Section/row labels (NO inline values): `Email` · `New Features & Tips` · `Market & Account Insights` · `Rewards` · `Account Updates` · `Push`.

### THE REAL TOGGLES (only place in the suite with genuine toggles)
8 toggles, all custom `android.view.View[@clickable='true']` with `@checked='true'` (all currently ON), right-aligned:
| # | bounds | checked |
|---|--------|---------|
| 1 | `[901,534][1038,660]` | true |
| 2 | `[901,676][1038,802]` | true |
| 3 | `[901,818][1038,944]` | true |
| 4 | `[901,960][1038,1086]` | true |
| 5 | `[901,1298][1038,1424]` | true |
| 6 | `[901,1440][1038,1566]` | true |
| 7 | `[901,1582][1038,1708]` | true |
| 8 | `[901,1724][1038,1850]` | true |

- **There is NO `android.widget.Switch`.** Toggles are checkable `View`s. `SettingsPage.SWITCHES` (`Switch | View[@checked]`) DOES match these — but it ALSO matches every clickable row elsewhere (all report `@checked='false'`). On THIS screen the toggles are distinguishable by their narrow right-edge bounds (x start = 901) and `@checked='true'`.
- The toggle label is a **sibling** TextView, NOT a child of the toggle View (the toggle View has empty text). To pair a label with its toggle, match by row Y-band, not parent/child.
- **Compose `@checked` updates a beat late after a tap** — poll the attribute, don't read once (relevant if any test flips a toggle).
- Note the split: rows 1–4 are under one heading band, 5–8 under another (`Email` group vs `Push` group), with a gap `1086→1298`.

---

## REWARDS — `raiz://raiz_rewards`  (lands: YES, Earn tab) — has stable resource-ids

Tabs: `Earn` `[305,129][529,255]`, `Track` `[551,129][775,255]`; a notification-count `0` View `[828,129][954,255]`; a top-right Button `[954,129]`.
Search field: `Search by store name` — `android.widget.EditText` `[74,446][1006,572]` (hint disappears on focus → use `RewardsPage.SEARCH_FIELD`).

Content texts: `Featured rewards` · `Ab test merchants` · `2% invested (was 1)` · `Boosted rewards` · `amazon` `10%` · `Acme Inc` `1%\n(was 10)` · `Commission Factory Test` `4%` · `Neat test` `Up to 3%` · `inbrain test` `29.90%` · `pure profile owner` `Answer questions, earn $$` · `Wall to Wall` `8%` · `Automatic rewards` · `Connect your Round-up accounts to start earning cashback…` · `Rewards invested` `$0`.

### Stable resource-ids (use these — verified present)
`RewardsEarnHeader_Root`, `RewardsEarnHeader_Value`, `RewardsEarnHeader_Loading`, `RewardsEarnFeaturedList_Root`, `RewardsEarnFeaturedList_Automatic`, `RewardsEarnFeaturedItem_Root`, `RewardsEarnBoostedList_Root`, `RewardsEarnBoostedList_Items`, `RewardsEarnBoostedItem_Root`.
- `RewardsPage` locators (`FEATURED_LIST`, `BOOSTED_ITEMS`, `ANY_REWARD_ITEM`, `HEADER_VALUE`, `FEATURED_HEADER='Featured rewards'`) are **all verified present**.
- Reward cards: 1 featured item (`amazon | 10% invested`) + 7 boosted items. `get_rewards()` returns 8.
- Rewards is heavy/lazy — content settles a beat after the tab strip. `is_loaded` accepting `EARN_TAB`/`FEATURED_HEADER`/`HEADER_VALUE` is correct. Keep the conftest one-shot retry.

### Track tab
`RewardsPage.PENDING_REWARDS_LABEL='Pending rewards'` / `REWARDS_INVESTED_LABEL='Rewards invested'` — `Rewards invested` IS present (also on Earn footer). To prove a real Earn→Track switch, prefer `Pending rewards` (Track-only). `Rewards invested` alone is ambiguous (appears on both).

---

## REWARDS — LINKED ACCOUNTS — `raiz://rewards_linked_accounts`  (lands: YES, "Accounts for Raiz Rewards")

Title: `Accounts for Raiz Rewards`. Intro: `The following accounts are eligible for Automatic Rewards opportunities… Manage your consent to give read only access…`.
Institution + accounts (CDR linked — confirms account state):
- `Dag Site (US)` with selectable accounts (each has a checkable View toggle at x≈928): `Dag Charge Card (3600)`, `Dag Credit Card (9806)`, `Dag Checking Account (2345)`, `Dag Fixed Term Deposit (9881)`, `Dag Saving Plus (4197)`.
- `NAB` — `We were unable to connect to this account. Please re-login to fix it.` + a **`Log in`** button `[796,1778][1038,1904]` (broken link, by design in this account).
- `Add Round-Up Account` `[42,2037][1038,2163]` (capitalised, with "Round-Up").
- `Manage consent and data sharing` `[42,2174][1038,2300]`.

- `RewardsPage.ADD_ACCOUNT_AFFORDANCE` matches `Add Round-Up Account` (verified). `INSTITUTION_ROW` matches `Dag Site`/`NAB`/`Card` (verified). `LINKED_ACCOUNTS_TITLE` (`contains 'Linked account/card'`) — **does NOT match** the real title `Accounts for Raiz Rewards`. If a test gates on `LINKED_ACCOUNTS_TITLE`, broaden it to also accept `contains(@text,'Accounts for Raiz Rewards')` or `contains(@text,'eligible for Automatic Rewards')`.

---

## REWARDS — AUTO — `raiz://rewards_auto`  (lands: YES; opens on the Earn surface, NOT a titled "Auto" screen)

Texts: `Earn` · `Track` · `0` · `Surveys` · `pure profile owner` `Answer questions, earn $$` · `inbrain test` `29.90% invested` · `Shops` · **`Click-through`** · **`Automatic`** (mode toggle pair) · category chips `All` `Favourites` `Gift Cards` `Food & Drink` `Indoor Play & Activities` · **`Sort: ` `Most Popular`** · shop cards `Inactive`/`Cimet Owner`, `Inactive`/`CJ test`/`$5 invested` · `Rewards invested` `$0` · `Search by store name`.

Clickables of note: `Click-through` `[53,1226][529,1352]` + `Automatic` `[551,1226][1027,1352]` (mode toggle); `Sort:  | Most Popular` `[0,1465][432,1591]`; shop cards each contain an `android.widget.CheckBox`.
New resource-ids: `RewardsEarnSurveysList_Root`, `RewardsEarnSurveysList_Carousel`, **`RewardsEarnSurveyItem_Root`** (survey cards; distinct from Featured/Boosted item ids).

- `RewardsPage.AUTO_TITLE` (`Automatic`/`Click-through`/`Surveys`/`Shops`) — **all four present, verified**. `AUTO_TOGGLE` (`Click-through`/`Automatic` View or `Sort:` TextView) — verified present.

---

## JARS — `raiz://jars`  (lands: "Customise your Jar" CREATE screen — NO active jars)

Because the account has NO jars, the deep link opens **straight into the create flow**, not a jar LIST.
Title: `Customise your Jar`. Texts: `Customise your Jar! Let's start by choosing an icon.` · `OR` · `Upload photo` · `What would you like to name this Jar?` · `Name` · `Set recurring investments` · `Create Jar`.
Clickables: 5 icon tiles (`[42,798]`…`[1038,798]`, 217px wide each); `Upload photo` `[42,1142][1038,1268]`; `Name` `android.widget.EditText` `[0,1438][1080,1612]`; `Set recurring investments` toggle row `[0,1985][1080,2111]`; **`Create Jar` `[42,2153][1038,2279]`**; back + close Buttons (close at `[943,129][1069,255]`).

- `JarsPage` create-flow locators (`ICON_TILES`, `NAME_FIELD`, `CREATE_JAR_BUTTON`, `Set recurring investments`) align with this. **`Create Jar` is a real, destructive commit — never auto-tap it.**
- If a `JarsPage.is_loaded` keys off a LIST title (`Jars`/`Active`/`Closed`), it will FAIL here — the empty state IS the create screen. Accept `Customise your Jar` / `Create Jar` as a valid loaded state, OR data-state-skip list assertions.

---

## RAIZ KIDS — `raiz://raiz_kids`  (lands: CONSENT GATE — NO kids)

Because there are NO kids, the deep link opens the **identity-consent gate**, NOT the "Welcome to Raiz Kids!" onboarding and NOT a list.
Title: `Raiz Kids`. Texts: `By clicking "I consent" you confirm:` + a long compliance paragraph (mentions Privacy Policy, Terms & Conditions, Product Disclosure Statement, Plus Portfolio Investment Guide, Target Market Determination, Disclaimer) + **`I consent`**.
Clickables: **`I consent` `[42,2174][1038,2300]`**; back Button `[0,118][147,265]`; close Button `[943,129][1069,255]`.

- `KidsPage.CONSENT_PROMPT` (`contains(@text,'I consent')`) matches the body text → `is_consent_screen()` returns True → `is_loaded()` passes. **Verified.**
- The `WELCOME_TITLE='Welcome to Raiz Kids!'` is NOT shown at this step (it's behind the consent tap). Tests must not gate on Welcome before consenting.
- Tapping `I consent` advances the real onboarding — only do so in opt-in/destructive tests.

---

## RAIZ SUPER — `raiz://raiz_super`  (lands: "Contact US" / fund-search-failed surface — Super UNFUNDED)

**IMPORTANT:** On this account the deep link does NOT open the insurance interstitial nor "Super is Ready". It opens a **Contact-US help surface**:
Title: `Raiz Invest Super`. Texts: `Contact US` · `We were unable to search for your existing Super funds at this time. Don't worry, we are here to help.` · `Email` · `1300 75 47 48`.
Clickables: back Button; `Email` `android.widget.TextView` `[126,1419][540,1545]`; `1300 75 47 48` `[540,1419][954,1545]`.

- `SuperPage.is_loaded()` via `ANY_SUPER_SURFACE` matches BOTH `Raiz Invest Super` AND `contains(@text,'existing Super funds')` → **passes here. Verified.**
- **Test-impacting (see lastfailed):** `test_super_insurance_interstitial_shown` and `test_not_now_advances_to_super_ready` expect the **insurance interstitial** (`Apply for insurance` / `Not now`) and the **"Super is Ready"** screen. Neither is reachable from this deep link in this data state — the app routes unfunded-with-no-found-funds users to the Contact-US surface instead. `is_insurance_interstitial()` (needs `APPLY_INSURANCE` + `NOT_NOW`) is correctly False here. These two tests should **DATA-STATE SKIP** when `is_insurance_interstitial()`/`is_ready_screen()` are False, not hard-assert. (Super onboarding is stateful and route-dependent.)

---

## MY FINANCE — `raiz://finance`  (lands: YES, "My Finance")

Toolbar title: `My Finance`. Section banner: `INSIGHTS AND HABITS`.
Texts: `My net worth` · `Total in investments` · `$1,578.81` · `Total in Superannuation` · `$0` · `Category Spending` · `No processed transactions for last 3 months` · `See More` · `Monthly tracker` · `Spent last month` · `Average monthly spend` · `0%` · `Over average`.
Clickables: `See More` `[84,1572][996,1698]`; back Button. (Only 2 clickables — most content is read-only summary.)

- `MyFinancePage` locators verified: `TITLE='My Finance'` ✓, `NET_WORTH_HEADER='My net worth'` ✓, `TOTAL_IN_INVESTMENTS` ✓ (`$1,578.81`), `TOTAL_IN_SUPER` ✓ (`$0`), `CATEGORY_SPENDING` ✓, `NO_TRANSACTIONS='No processed transactions for last 3 months'` ✓ (exact match), `SEE_MORE_BUTTON` ✓, `MONTHLY_TRACKER='Monthly tracker'` ✓.
- Financial insights ARE configured (no "Set up your financial insights" prompt shown) → the `SETUP_INSIGHTS_HEADER`/`INSIGHTS_PROGRESS` setup locators will be ABSENT. Category Spending currently shows the empty `No processed transactions…` state → `has_category_spending_data()` returns False; data-state-skip spending-amount assertions.

---

## PROFILE — PERSONAL — `raiz://profile/personal`  (lands: YES)

Tabs: `Personal` `[158,129][529,255]` / `Financial` `[551,129][922,255]`.
Editable fields (each value is the displayed text, label below it): `Jsoj`/`Legal First Name` · `Jdjd`/`Legal Last Name` · `raizjoshnew+5847266@gmail.com`/`Email Address` · `0446 646 464`/`Phone Number` · (blank)/`Unit/House Number` · `1`/`Street Number` · `Hardie Street`/`Address 1` · (blank)/`Address 2` · `Neutral Bay`/`Suburb` · `NSW`/`State` · `2089`/`Postcode` · `Provided`/`TFN` · **`Confirm Changes`** button `[42,2153][1038,2279]`.
Field controls are `android.widget.EditText`; `State` is a dropdown View `NSW | State` `[0,1921][538,2095]`.

- Confirms the greeting name `Jsoj` (first name) and account email match `TEST_EMAIL`. `Confirm Changes` commits edits — read-only tests must not tap it.

## PROFILE — FINANCIAL — `raiz://profile/financial`  (lands: YES)

Texts: `Employment` · `Household income` · `What is your financial goal?` · `Where did you hear about us?` · `Confirm Changes`.
Each is a dropdown: a `View` row wrapping an `android.widget.EditText` (e.g. `Employment` `[0,328][1080,502]`). `Confirm Changes` `[42,2153][1038,2279]`. Values are blank/placeholder in this capture (the EditText text equals the label) → these are unselected dropdowns; do not assert specific values.

---

## SETTINGS  (open via the gear `(//android.widget.Button)[2]`; lands "Settings")

Full row list (top→bottom, grouped):
- **ACCOUNT:** `Notifications inbox` (badge `6`) · `Funding account` · `Accounts for financial insights` · `Plans and fees`
- **PREFERENCES:** `Personal details` · `Security and privacy` · `Manage notifications` · `Manage Round-Ups`
- **HELP & FEEDBACK:** `Refer a friend` · `Rate Raiz` · `How to start guide` · `Get support`
- **IMPORTANT DOCUMENTS:** `Our terms` · `Statements and reports`
- `Dev Settings` · `Log out`
- Footer: **`App version: 2.39.1d (3223)`** (confirms build)

- All `SettingsPage` row locators verified present with exact text. `NOTIFICATION_BADGE` → `Notifications inbox` shows `6`.
- **Close (X)** button at `[944,150][1070,276]` (top-right). `SettingsPage.close()` finds the right-most clickable in the top 20% by geometry — **verified robust** (no hardcoded pixels).
- `Dev Settings` row is present → `test_dev_settings_row_present` should pass; add `Dev Settings` locator if needed.
- Lazy column: lower rows (`Statements and reports`, `Dev Settings`, `Log out`, version) require a scroll to enter the DOM — confirmed (they appear only in the scrolled capture). `_tap_item` scroll-to-text is correct.

---

## EXTERNAL vs IN-APP — verified by tapping + reading `current_package`

| Action | Lands in | `current_package` after tap | Implication for tests |
|--------|----------|-----------------------------|------------------------|
| Settings → **Get support** | **EXTERNAL Chrome** | **`com.android.chrome`** | Leaves the app entirely. Do NOT look for in-app elements after tapping. Assert by `current_package == 'com.android.chrome'` (or `!= app pkg`), then `driver.back()` to return. A waited in-app `is_visible` will time out → ERROR. |
| Settings → **Our terms** | **IN-APP WebView** | **`com.acornsau.android.development`** (stays) | Slow in-app WebView. Loads a Terms hub page. Success signal: resource-id `__next` appears (React web root), and webview texts like `Terms & Conditions \| Raiz Invest`, `Privacy Policy`, `Product Disclosure Statement`, `Last updated: 14 May 2026`, `Sign Up`. Give it a LONG wait (it renders ~2–3 s after tap). Toolbar title `Our terms`. |

**Our terms** webview content (in-app, verified): heading `Terms & Conditions | Raiz Invest`; links `Terms & Conditions`, `Privacy Policy`, `Product Disclosure Statement`, `Super Product Disclosure Statement`, `Target Market Determination`, `Super Target Market Determination`, `Disclosures`, `Important Documents`, `Chatbot`, `Direct Debit Request Service Agreement`, `Website Terms of Use`; `Sign Up` CTA. Unique signal vs native screens: `resource-id='__next'` + `content-desc='Raiz Invest logo'` / `'menu button'`.

---

## NAV DRAWER (hamburger `(//android.widget.Button)[1]`)

Items (grouped), all clickable Views — verified text + bounds:
- `Home` `[0,352][1080,479]`
- **SAVE & EARN:** `Rewards` `[0,587]` · `Surveys` `[0,714]`
- **INVESTMENT ACCOUNTS:** `Main portfolio` `[0,949]` · `Jars` `[0,1076]` · `Kids` `[0,1203]` · `Super` `[0,1330]`
- **INVESTMENT PREFERENCES:** `Round-Ups` `[0,1565]` · `Recurring investments` `[0,1692]` · `Lump Sum investments` `[0,1819]`
- **DO MORE WITH RAIZ:** `My Finance` `[0,2054]` · `My Achievements` `[0,2181]` · `Offsetters` `[0,2308]`

- All `NavDrawer.NAV_*` and `SECTION_*` locators verified (exact text incl. `Main portfolio` lowercase-p, `Super` not "Superannuation", `Kids` not "Raiz Kids").
- **STALE LOCATOR (genuine anti-pattern):** `NavDrawer.CLOSE_BUTTON = //android.view.View[@bounds='[924,142][1068,286]']` — the real close affordance is at **`[944,172][1070,298]`** on this device. The hardcoded pixel-bounds locator will NOT match and is device-specific. Reported in shared-infra (NavDrawer is a page object, not shared infra, but flagging the pattern). Replace with a geometry-based right-most-top-clickable lookup like `SettingsPage.close()`, or `(//android.widget.Button)[1]`/Back to dismiss.

---

## Deep links that MISROUTE (confirmed previously, unchanged on 3223 — for navigation_coverage tests)
- `raiz://performance/day` and `raiz://performance/month` → land on **Home**, not a day/month perf screen.
- `raiz://portfolio` → lands on the **allocation breakdown** (ETF % list), not a portfolio overview.
- `raiz://history` → lands on the **investing-journey summary** (= Home Past tab), not a txn list. Real txn list = its `Transaction history` link or `raiz://transactions`.
- `raiz://dividends` → flaky cold-load (transient "Oops!" → can drop to PIN); retry loads it.
- **Back-button:** screens on the Home/Past/Today/Future surface (home, future, history, performance/day|month) **exit to launcher** on Back; modally-pushed screens (invest, deposit, withdraw, performance, transactions, portfolio, etc.) **return to Home**. Relevant to `TestDeepLinkBackStack` expectations.

---

## Quick locator-health summary for fixer agents

**Verified ACCURATE (use as-is):** all HomePage chrome/tab/card locators; MainPortfolioPage `ANY_TITLE`/`YOU_PORTFOLIO_ROW`(keep typo); PerformancePage tabs/labels; RewardsPage `RewardsEarn*` ids + tab/header/featured; RewardsPage `AUTO_*`, `ADD_ACCOUNT_AFFORDANCE`, `INSTITUTION_ROW`; SettingsPage all rows + geometry `close()`; MyFinancePage all; KidsPage `CONSENT_PROMPT`; SuperPage `ANY_SUPER_SURFACE`; NavDrawer NAV_*/SECTION_*; PinPage/biometrics handling.

**Needs attention (genuine):**
1. `NavDrawer.CLOSE_BUTTON` hardcoded bounds `[924,142][1068,286]` are wrong (real `[944,172][1070,298]`) and device-specific → make geometric.
2. `RewardsPage.LINKED_ACCOUNTS_TITLE` doesn't match real title `Accounts for Raiz Rewards` → broaden.
3. Super tests `test_super_insurance_interstitial_shown` / `test_not_now_advances_to_super_ready` expect an interstitial that this account's deep link doesn't reach (lands on Contact-US) → convert to data-state skips.
4. `MainPortfolio test_you_portfolio_row_value_is_well_formed` — the `You portfolio` row value is the portfolio NAME (`Conservative`), not money → assert it's a non-empty name, not `is_money`.
5. Sparse screens (transactions=9, jars/kids/super onboarding) are correct content, not load failures — don't tighten `is_loaded` to demand list-screen markers that the empty/onboarding state lacks.
6. `notifications_settings` has the ONLY real toggles (8, custom `View[@checked]`, x≥901); elsewhere `@checked='false'` on every clickable row is noise — don't count it as a toggle.

## Screens NOT reached / not attempted this pass
- None failed. All 23 target captures succeeded (0 errors, 0 crashes) in one clean session.
- Not crawled (out of scope this pass): `raiz://deposit`/`withdraw` keypads (well-documented in nav_map_5554.md), `raiz://recurring_investments`, `raiz://offsetters`, `raiz://achievements`, `raiz://round_ups`, sub-screens of settings rows beyond Get support/Our terms. Refer to `docs/nav_map_5554.md` for those.
