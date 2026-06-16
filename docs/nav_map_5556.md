# Raiz AU Android — Navigation Map (emulator-5556)

- **Build:** 2.39.1d / 3223
- **Package:** `com.acornsau.android.development`
- **Account state:** logged in (PIN 0000); NO active jars, NO kids, UNFUNDED super.
- **Method:** single foreground Appium session (host `http://127.0.0.1:4724`, systemPort 8202). Each area opened via `mobile: deepLink`, screen captured, `driver.back()` to record back-stack landing.
- **Date:** 2026-06-05
- **Note:** every screen runs inside the single React-Native host activity `com.raiz.main.MainActivity`; "screen title" below is the in-app header text, not an Android activity.

## Deep-link areas

| Area | Deep link / path | Actual screen title | Key elements | Lands on expected screen? | Back-button landing | Links to other areas |
|------|------------------|---------------------|--------------|---------------------------|---------------------|----------------------|
| Jars | `raiz://jars` | **Customise your Jar** | Choose an icon / Upload photo, "What would you like to name this Jar?" Name field, Set recurring investments, **Create Jar** button | PARTIAL — no jars exist, so deep link lands directly on the *create-jar* form rather than a Jars list/empty-list screen | Home | Jar create flow; recurring investments |
| Raiz Kids | `raiz://raiz_kids` | **Raiz Kids** (identity-consent gate) | "By clicking 'I consent' you confirm…" consent body, PDS / Investment Guide / TMD doc references, **I consent** button | YES (onboarding gate is the real destination for an account with no kids) | Home | Privacy Policy, T&Cs, PDS/AID, Plus Portfolio Investment Guide, TMD |
| Raiz Kids 2 | `raiz://raiz_kids_2` | **Raiz Kids** (identity-consent gate) | Identical to `raiz://raiz_kids` — same consent screen | MISMATCH-ish — `raiz_kids_2` is not a distinct screen; resolves to the same consent gate as `raiz_kids` | Home | same as above |
| Raiz Super | `raiz://raiz_super` | **Raiz Invest Super** | "We were unable to search for your existing Super funds at this time…", Contact US, Email, phone 1300 75 47 48 | PARTIAL — lands on a super-fund-search *error/contact* state (unfunded account), not a clean onboarding intro | Home | Contact US (email/phone) |
| Raiz Super — Account Info | `raiz://raiz_super/account_info` | **Raiz Invest Super** (same error state) | identical to `raiz://raiz_super` | MISMATCH — sub-route does NOT open an account-info screen; falls back to the super error/contact screen | Home | Contact US |
| Raiz Super — Important Documents | `raiz://raiz_super/important_documents` | **Raiz Invest Super** (same error state) | identical to `raiz://raiz_super` | MISMATCH — sub-route does NOT open important documents; falls back to the super error/contact screen | Home | Contact US |
| Round-Ups | `raiz://round_ups` | **Round-Ups** (activity/empty) | "You don't have any spending yet.", Round-Ups invested $0, Auto Round-Ups ($5.00 until $5), Manual Round-Ups "tap to invest", tabs All / Invested / Available | YES (empty state is the real destination) | Home | Round-Up settings; Manual Round-Ups invest |
| Round-Up Settings | `raiz://round_ups/settings` | **Round-Up settings** | Linked accounts for Round-Ups, Auto Round-Ups toggle, Minimum amount threshold ($5/$10/$20/$40), Multiply your Round-Ups, whole-dollar amounts ($0.00–$1.00) | YES | Home | Linked accounts for Round-Ups (→ `accounts/round_ups`) |
| Accounts — Round-Ups | `raiz://accounts/round_ups` | **Linked accounts for Round-Ups** | Dag Site (US) cards/accounts (Charge 3600, Credit 9806, Checking 2345, Term 9881, Saving 4197), NAB "unable to connect — Log in", Add an account, Manage consent and data sharing | YES | Home | Add an account; Manage consent & data sharing; NAB re-login |
| Funding Account | `raiz://funding_account` | **Funding Account** | "This bank account funds all investments…", account (1234), Change, **Account verified**, funding-source warnings | YES | Home | Change funding account |
| Spending Account | `raiz://spending_account` | **Linked accounts for Round-Ups** | IDENTICAL to `accounts/round_ups` (Dag Site cards, NAB, Add an account…) | MISMATCH — `spending_account` resolves to the Round-Ups linked-accounts screen, NOT a distinct spending-account screen | Home | same as accounts/round_ups |
| Milestone | `raiz://milestone` | **Milestone overview** | "Up next", Edit, progress $1,564.03 / $2,000, "Fastest ways to get there": Set recurring investment, Make lump-sum deposit, Explore Raiz Rewards, Open a new Jar | YES | Home | Recurring investment, Deposit, Raiz Rewards, Jars |
| Achievements | `raiz://achievements` | **Achievements** | Grouped badge grid: Goals (Goal Setter, Quarter Closer, Goal Chaser, Goal Keeper), Round-Ups (The Automator, Collector, Accumulator), Raiz Rewards (Cashback Beginner, Bonus Builder, Insider) | YES | Home | (badges — see dead-end note) |
| Plans | `raiz://plans` | **Pricing plans** | Lite / Regular / Plus tiers, "from $5.50 / month", fee notes, feature bullets (Rewards, Kids, Jars, Plus Portfolio), **Current plan** marker, "read PDS and AID" | YES | Home | PDS / AID |

## UI-only flows observed (no actions completed)

| Flow | Entry | What was observed | Notes |
|------|-------|-------------------|-------|
| Jars create flow | `raiz://jars` → tap **Create Jar** with empty name | Validation modal **"Oops!" / Ok** appears (name required). No jar created. | The "Customise your Jar" form IS the create flow: icon picker / Upload photo, Name field, Set recurring investments, Create Jar. Single-screen form, not a wizard. SAFE — no jar created. |
| Kids identity-consent gate | `raiz://raiz_kids` → inspected **I consent** | Consent screen is the gate to Kids onboarding. "I consent" is the only forward control; no "Get started"/"Continue" buttons present pre-consent. Did NOT consent. | Onboarding past consent not reachable without consenting (intentionally not done). |
| Super onboarding | `raiz://raiz_super` | No onboarding wizard for this account — lands on "unable to search for your Super funds" error/contact screen. No Get started/Continue/Join buttons. | For an unfunded account the super entry is effectively a dead-end contact screen (see mismatches). |
| Round-Up settings controls | `raiz://round_ups/settings` → tapped **Multiply your Round-Ups** | Single scrollable settings screen; thresholds ($5/$10/$20/$40), multiplier section, and whole-dollar amounts ($0.00–$1.00) are all inline. Tapping the multiplier section did NOT change the visible control set (not a collapse/expand that swaps screens). | Controls are inline selectors on one screen. |
| Achievements detail | `raiz://achievements` → tapped badge **"Goal Setter"** | No detail screen opened — view stays on the Achievements grid. | Badges are not individually tappable for this no-progress account (see dead-ends). |

## Discovered areas (sub-areas surfaced on-screen)

- **Linked accounts for Round-Ups** (`raiz://accounts/round_ups`) — reached from Round-Up Settings, and is also where `raiz://spending_account` lands.
  - Sub-actions: **Add an account**, **Manage consent and data sharing**, **NAB re-login** ("Log in").
- **Round-Up settings** — reached from the Round-Ups empty screen and from the Linked-accounts header.
- **Change funding account** — from Funding Account → "Change".
- **Milestone "Fastest ways to get there"** cross-links: Set recurring investment, Make a lump-sum deposit, **Explore Raiz Rewards**, **Open a new Jar**.
- **Manual Round-Ups → "tap to invest"** on the Round-Ups screen.
- **Contact US** (email + phone 1300 75 47 48) — from the Raiz Super screen.
- Legal/document links repeated across Kids consent and Plans: **Privacy Policy, Terms & Conditions, PDS/AID, Plus Portfolio Investment Guide, Target Market Determination**.

## Mismatches / dead-ends / failures

1. **`raiz://spending_account` is a mismatch** — it does NOT open a distinct "Spending Account" screen; it lands on the **Linked accounts for Round-Ups** screen (byte-identical to `raiz://accounts/round_ups`). No separate spending-account destination exists in this build.
2. **`raiz://raiz_super/account_info` mismatch** — sub-route does not open an account-info view; falls back to the base **Raiz Invest Super** error/contact screen.
3. **`raiz://raiz_super/important_documents` mismatch** — sub-route does not open important documents; falls back to the same Raiz Super error/contact screen.
4. **`raiz://raiz_super` (base) — effective dead-end for unfunded account** — instead of an onboarding/intro it shows "We were unable to search for your existing Super funds at this time" with only a Contact US email/phone. No forward path in-app.
5. **`raiz://raiz_kids_2` duplicates `raiz://raiz_kids`** — both resolve to the same identity-consent gate; `raiz_kids_2` is not a distinct screen.
6. **Achievements badges are dead-ends (no-progress account)** — tapping a badge (e.g. "Goal Setter") opens no detail screen; the grid is display-only here.
7. **`raiz://jars` skips a Jars list** — with no jars, the deep link drops straight into the **Customise your Jar** create form rather than an empty Jars list/landing. Minor UX note rather than a hard failure.
8. **Back button is uniform** — every area (deep-linked and UI) returns to **Home** on `driver.back()`; there is no intermediate back-stack from deep links.

## Coverage summary

- Deep-link areas mapped: **14 / 14**
- UI-only flows observed: **5 / 5** (none completed; no jar/kid created, no money moved, no logout)
- Mismatches/dead-ends flagged: **8** (3 hard route mismatches: spending_account, super/account_info, super/important_documents; plus super error dead-end, raiz_kids_2 duplicate, achievements badge dead-end, jars-skips-list, uniform back)
- Discovered sub-areas: **7** clusters
