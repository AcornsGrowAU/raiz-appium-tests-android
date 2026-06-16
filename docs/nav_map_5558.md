# Raiz AU Android — Navigation Map: Rewards / Finance / Profile / Settings / Drawer

- Device: **emulator-5554** (free/healthy emulator; these areas are app-global and identical on every logged-in device — file named `nav_map_5558.md` per the navigator task brief)
- Build: **2.39.1d (3223)**, logged in as "Jsoj Jdjd", PIN `0000`
- Package: `com.acornsau.android.development` (single activity `com.raiz.main.MainActivity`; whole app is one React/Compose surface)
- Explored: 2026-06-05, foreground Appium session, deep links + UI taps
- "Total investments value" drifts cent-by-cent between captures (live mock backend) — ignore dollar figures as identity signals.
- **Bank-link state:** the test account already has the Yodlee "Dag Site (US)" institution linked, so the rewards/finance "linked accounts" deep links show the populated Dag account picker, NOT an empty "link an account" state.

---

## 1. Deep-link areas

| Area | Deep link | Actual screen (title / first elements) | Key visible elements | Lands on expected? | Back-button landing | Links to other areas |
|------|-----------|----------------------------------------|----------------------|--------------------|---------------------|----------------------|
| Rewards | `raiz://raiz_rewards` | **Rewards — Earn tab** | Earn / Track tabs, "Featured rewards", merchant cards (Ab test merchants 2% invested, Boosted rewards, amazon 10%, Acme Inc, Commission Factory Test) | YES | Home | Earn↔Track tabs, individual reward detail |
| Rewards linked accounts | `raiz://rewards_linked_accounts` | **Automatic Rewards account picker** ("The following accounts are eligible for Automatic Rewards…") | Dag Site (US), Dag Charge Card (3600), Dag Credit Card (9806), Dag Checking (2345), Dag Fixed Term (9881), Dag Saving Plus (4197) | YES | Home | account/consent management |
| Rewards auto | `raiz://rewards_auto` | **Rewards — Earn tab (Surveys section in view)** | Earn/Track tabs, Surveys, "pure profile owner", "Answer questions, earn $$", "inbrain test 29.90% invested" | PARTIAL — lands on the standard Rewards Earn screen scrolled to the Surveys/auto section, not a distinct "auto rewards" screen | Home | Surveys, reward cards |
| Accounts: rewards | `raiz://accounts/rewards` | **Automatic Rewards account picker** (identical to `rewards_linked_accounts`) | same Dag account list | YES (duplicate of rewards_linked_accounts) | Home | account/consent management |
| Finance | `raiz://finance` | **My Finance — "Set up your financial insights"** (empty/onboarding state) | "0 of 3 completed", View all, "Link your transactional accounts", "Review your spending categories", INSIGHTS AND HABITS | YES (real destination is the empty onboarding state — no insights set up) | Home | Link transactional accounts, spending categories, View all |
| Accounts: financial insights | `raiz://accounts/financial_insights` | **Financial-insights account picker** ("Connect and give read only access to your accounts…") | Dag Site (US) + the same 5 Dag accounts/cards | YES | Home | account/consent management |
| Profile: personal | `raiz://profile/personal` | **Personal details form** | Legal First/Last Name, Email Address, Phone Number, Unit/House Number, Street Number, Address 1, Address 2 | YES | Home | (form; Personal/Financial tabs) |
| Profile: financial | `raiz://profile/financial` | **Financial profile form** | Employment, Household income, "What is your financial goal?", "Where did you hear about us?", Confirm Changes, Personal / Financial tabs | YES | Home | Personal↔Financial tabs |
| Notifications settings | `raiz://notifications_settings` | **Manage notifications** ("Use this screens to modify your push notifications…") | Email + Push columns, New Features & Tips, Market & Account Insights, Rewards, Account Updates | YES | Home | (toggles only) |
| Fees | `raiz://fees` | **Plans and fees** ("If you apply for the account fee of 0.275%…") | Funding account, Raiz Invest account, PLAN, Pricing plan, Regular | YES | Home | plan/fee account selectors |
| Offsetters | `raiz://offsetters` | **Offsetters** | Offset / Impact / Win tabs, "Your small change can create a big change…", "Become a member for just…", Learn More | YES | Home | Offset/Impact/Win tabs, Learn More |
| Blog | `raiz://blog` | **Blog/articles list** | "Dollar cost averaging…", "Market update: 2 June 2026", "What Payday Super means…", several Market update + glossary articles | YES | Home | individual article (webview) |
| Invite friends | `raiz://invite_friends` | **Invite friends** ("You can both get $5 invested for you!") | Invite code MYE3QG, "Your friends have to", Sign up steps, "Your reward" | YES | Home | share/copy code |

**Back-button behavior:** every deep-link area in this bucket returns to **Home** on Back (consistent — none exit to launcher). Verified by the recurring "Hello, Jsoj / Your total investments value" back landing.

---

## 2. Nav drawer (top-left hamburger = `(//android.widget.Button)[1]`)

Open path: deep-link `raiz://home` → tap the first header Button (index 1). The drawer reliably opens on button index 1.

**IMPORTANT:** "My Settings" is **NOT** in the nav drawer. Settings is reached via the **gear icon** (`(//android.widget.Button)[2]`) on the Home header — see §3.

### Full drawer contents (section headers + items, in order)
- **(top)** Home
- **SAVE & EARN** *(section header)*
  - Rewards
  - Surveys
- **INVESTMENT ACCOUNTS** *(section header)*
  - Main portfolio
  - Jars
  - Kids
  - Super
- **INVESTMENT PREFERENCES** *(section header)*
  - Round-Ups
  - Recurring investments
  - Lump Sum investments
- **DO MORE WITH RAIZ** *(section header)*
  - My Finance
  - My Achievements
  - Offsetters

### Per-item destinations (tap → title / key elements → back landing)

| Drawer item | Destination title | Key elements | Back landing |
|-------------|-------------------|--------------|--------------|
| Home | Home ("Hello, Jsoj") | total value, account-setup checklist, Add funds | **Exits to launcher** (Home back = launcher) |
| Rewards | Rewards — Earn | Earn/Track, Featured rewards, merchant cards | Home |
| Surveys | Rewards — Earn (Surveys in view) | Surveys, "pure profile owner", "inbrain test 29.90% invested" | Home |
| Main portfolio | "Your main portfolio's investment value" | Add funds, Withdraw, Performance details, Invested, Conservative | **Drawer** (reopens drawer) |
| Jars | "Customise your Jar! Let's start by choosing an icon." | Upload photo, name field, Set recurring investments, Create Jar | Drawer |
| Kids | Raiz Kids consent ("By clicking 'I consent'…") | consent copy, important docs list, **I consent** | Drawer |
| Super | "Raiz Invest Super" | Contact US, "unable to search for your existing Super funds…", Email, 1300 75 47 48 | Home |
| Round-Ups | "Round-Ups invested" | Linked accounts for Round-Ups, Auto Round-Ups, Minimum Round-Ups amount $5/$10 | Drawer |
| Recurring investments | "MAIN PORTFOLIO" | Jsoj Jdjd / Conservative / $0, Raiz Kids, Raiz Jars | Drawer |
| Lump Sum investments | "Invest" (keypad) | number pad 1-9 | Drawer |
| My Finance | "Set up your financial insights" (empty state) | 0 of 3 completed, Link transactional accounts, INSIGHTS AND HABITS | Drawer |
| My Achievements | "Goals" | Goal Setter, Quarter Closer, Goal Chaser, Round-Ups, The Automator, Collector | Drawer |
| Offsetters | "Offsetters" | Offset/Impact/Win, "big change for our planet", Learn More | Drawer |

**Back-button quirk:** drawer items pushed as nested screens (Main portfolio, Jars, Kids, Round-Ups, Recurring, Lump Sum, My Finance, My Achievements, Offsetters) return to the **open drawer** on Back, while top-level surfaces (Rewards, Surveys, Super) return to **Home**, and Home itself exits to the launcher.

---

## 3. Settings (Home gear icon = `(//android.widget.Button)[2]` → "Settings")

Open path: deep-link `raiz://home` → tap the second header Button (gear, index 2). Title = "Settings".

### Full settings contents (section headers + rows, in order)
- **ACCOUNT** *(header)*
  - Notifications inbox *(badge "6")*
  - Funding account
  - Accounts for financial insights
  - Plans and fees
- **PREFERENCES** *(header)*
  - Personal details
  - Security and privacy
  - Manage notifications
  - Manage Round-Ups
- **HELP & FEEDBACK** *(header)*
  - Refer a friend
  - Rate Raiz
  - How to start guide
  - Get support
- **IMPORTANT DOCUMENTS** *(header)*
  - Our terms
  - Statements and reports
  - **Dev Settings** *(dev-build only)*
- Log out
- "Last log in from Google - emu64a, on June 05…" (info text)
- App version: 2.39.1d (3223)

### Per-row destinations

| Settings row | Destination title | Key elements | Back landing |
|--------------|-------------------|--------------|--------------|
| Notifications inbox | dated notification feed ("08.05.2026") | Raiz Investment items, "Your $500.00 has been invested…", "You've reached $1,500 🎉" | Settings |
| Funding account | "This bank account funds all investments…" | (1234), Change, Account verified, funding rules | Settings |
| Accounts for financial insights | "Connect and give read only access…" | Dag Site (US) + 5 Dag accounts/cards | Settings |
| Plans and fees | "If you apply for the account fee of 0.275%…" | Funding account, Raiz Invest account, PLAN, Pricing plan, Regular | Settings |
| Personal details | "Legal First Name" | Legal First/Last Name, Email, Phone, address fields | Settings |
| Security and privacy | "Change Password" | Change PIN, Use biometrics, **Close account** | Settings |
| Manage notifications | "Use this screens to modify your push notifications…" | Email/Push toggles: New Features & Tips, Market & Account Insights, Rewards, Account Updates | Settings |
| Manage Round-Ups | "Round-Ups invested" | Linked accounts for Round-Ups, Auto Round-Ups, Minimum Round-Ups amount $5/$10 | Settings |
| Refer a friend | "Invite friends." | Invite code MYE3QG, friend steps, Your reward | Settings |
| Rate Raiz | "How would you rate Raiz?" modal | 1–5 scale, **Not Now** | dismisses to its own state (modal) |
| How to start guide | "What can I invest in?" (FAQ) | funding vs Round-Ups, investing strategies, fees, choosing a portfolio | Settings |
| Get support | "Need a hand?" | Raiz Invest / Super / Contact Us tabs, 1300 75 47 48, Get Started Here, View Our App Guide | self (sub-tabs); see dead-end note |
| Our terms | "Last updated: 14 May 2026" | Terms & Conditions, Privacy Policy, PDS, Super PDS, TMD, Disclosures | Settings |
| Statements and reports | dated statements ("May 8th") | 2026, "Send CSV of all trades to date", Select, Account Value | Settings |
| Dev Settings | "Dev settings" | Copy Firebase Instance ID, Clear Preference Storage, Clear Data Store, 3223 / 2.39.1d | Settings |
| **Log out** | ⚠️ **logs out immediately — NO confirmation dialog** (see Mismatches #2) | lands on splash: "Smart investing made simple", Create an account, Already have an account? Log in | — |

---

## 4. Rewards Earn / Track tabs + first reward detail

| View | How | Content |
|------|-----|---------|
| **Earn tab** (default) | `raiz://raiz_rewards` | "Featured rewards" + merchant cards: Ab test merchants (2% invested, was 1), Boosted rewards, amazon (10%), Acme Inc (1%, was 10), Commission Factory Test, Neat test |
| **Track tab** | tap "Track" | "There are no rewards at the moment", Pending rewards $0, Rewards invested, sub-filters All / Pending / Invested — **empty rewards-activity state** (account has no rewards yet) |
| **First reward detail** (observe only — NOT redeemed) | tap first reward card on Earn | Title "Neat test", "Up to 3% invested", "neat", "How does it work?", "About the brand", Featured, **Shop online here**, "Terms & Conditions" — in-app detail screen (Shop online here would launch a webview; not followed) |

---

## 5. Discovered areas / cross-links
- **Rewards ↔ Surveys**: both `raiz://raiz_rewards` and `raiz://rewards_auto` plus drawer "Surveys" all land on the single Rewards Earn surface (Surveys is a section within it, not a separate screen).
- **Three deep links → the same Dag account picker**: `raiz://rewards_linked_accounts`, `raiz://accounts/rewards`, and `raiz://accounts/financial_insights` (and Settings → "Accounts for financial insights") all reach a near-identical Yodlee/Dag account-consent picker. The rewards variants and the financial-insights variant differ only in the intro sentence.
- **Manage notifications** is reachable via BOTH Settings → "Manage notifications" AND `raiz://notifications_settings` (same screen).
- **Refer a friend** (Settings) == **Invite friends** (`raiz://invite_friends`) == drawer has none — same invite screen, code MYE3QG.
- **Plans and fees** (Settings) == `raiz://fees` — same screen.
- **My Finance** (drawer) == `raiz://finance` — same "Set up your financial insights" empty onboarding.
- **Manage Round-Ups** (Settings) == drawer "Round-Ups" == "Round-Ups invested" screen.
- **Security and privacy** exposes **Close account** and Change PIN/Password — destructive surfaces (not entered).
- **Dev Settings** row exists only on this dev build (Clear Preference Storage / Clear Data Store — destructive; not tapped).
- **Get support** offers "Get Started Here" and "View Our App Guide" links (external/help surfaces).

---

## 6. Mismatches / dead-ends / flags
1. **`raiz://rewards_auto` is not a distinct screen** — it lands on the standard Rewards **Earn** tab (scrolled to the Surveys/auto-rewards section), same as `raiz://raiz_rewards`. Minor mismatch: no dedicated "auto rewards" screen.
2. **⚠️ Settings → "Log out" commits the logout immediately with NO confirmation dialog.** Tapping it dropped straight to the logged-out splash ("Smart investing made simple / Create an account / Already have an account? Log in"). There was no "Are you sure / Cancel" prompt to cancel against. This contradicts `settings_page.py`'s `logout_prompt_shown()` / `cancel_logout()` assumption that a confirmation appears. **This logged the test device out**; it was re-logged-in afterward (see note below). **Test impact:** any test that taps Log out expecting a cancellable dialog will instead fully log out the shared session.
3. **`raiz://accounts/rewards` duplicates `raiz://rewards_linked_accounts`** (identical account-picker screen) — redundant, not a bug but worth noting.
4. **`Rate Raiz`** opens a modal rather than a full screen; back/"Not Now" returns to the modal's prior state, not cleanly to Settings.
5. No hard load failures or "Oops!" dialogs in this bucket on this run. PIN re-auth was never triggered by any deep link in this bucket (unlike deposit/withdraw on the 5554 baseline map).

### Device-state note
The Log-out finding (#2) logged emulator-5554 out. The device was **restored to logged-in / Home state** after exploration by re-running the splash → Login (`Login` button, note: label is "Login" not "Log in") → Home flow via the project page objects. Home confirmed loaded ("Hello, Jsoj", total value). No PIN re-entry was required on this re-login. **Device left healthy and logged in.**
