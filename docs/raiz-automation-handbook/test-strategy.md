# Test Strategy

Why the suite is built the way it is, and how to extend it well.

## The thesis: green ≠ verified

A coverage audit (14 product areas, customer-POV + source-mapped) found the suite was
**all green but hollow**: it reliably confirmed screens *render*, but rarely that the
*numbers on them are correct*. No area scored above C+ on value-correctness; three money
surfaces (Plans/fees, Super, My Finance) sat at D because the load-bearing math was
unreachable on a single shared happy-path account. The dominant non-failure was **PASS and
SKIP standing in for coverage that was never written** — a 5%-on-$100 reward crediting
$0.50 still passed, a new kid's $0.00 start was unchecked, Super "reconciled" only by
equalling $0.

**So the strategy is: convert presence → value, and assert the invariants that matter.**

## What "good" looks like

1. **Value/state oracles, reconciled to an authoritative source.** Read the real figure
   and check it against backend `current_balance`, the published fee schedule, allocation
   × balance, or the exact seeded amount — not "a `$` parsed" or "is_visible".
2. **Cross-feature money-conservation invariants** (the biggest, least-covered, highest-
   consequence gap): Home total == Main + Σ jars + Σ kids + Super; a deposit into Main
   moves no jar/kid; funding Kid-A credits only Kid-A; a Main↔Jar transfer conserves the
   total. These catch the worst class of fintech bug (money created/lost across products).
3. **Negative / enforcement-point oracles**, asserted at COMMIT not the keypad: sub-$5
   rejected, over-balance withdrawal blocked, caps enforced (6 jars / 8 kids / Bitcoin ≤
   5% / Property ≤ 30%), tier entitlement gating, suspended/closed account blocked in UI.
4. **Per-entity independence:** per-kid / per-jar portfolio + recurring stored
   independently (changing A doesn't bleed into B).
5. **Round-trip persistence:** set-then-read-back across a restart (settings toggles, jar
   target, recurring amount+frequency), not read-after-a-presumed-state.

## Systemic weaknesses to keep fighting

Presence-over-value · almost no negative/rejection assertions · a single shared funded
happy-path account (no empty/Lite/suspended/net-new state) · state not verified round-trip
· confirmation-sheet amounts/dates never value-checked · `parse_money`/`parse_percent`
xfails on negatives (parens/trailing/unicode minus) so the oracle is blind to losses ·
reliability managed reactively (retries) instead of designed out · no cross-product
conservation discipline.

## Test-data strategy (reuse first, real-ACH always)

See `genuser-test-data-reuse-strategy` (memory) and `utils/genuser_fixtures.py`.

- **Ask first: does it need to be generated fresh?** Default to **reusing** a small pool
  of long-lived, pre-onboarded fixture users keyed by purpose (the registry). Generating
  fresh is triple-expensive (slow + flap-prone + each fresh user must be onboarded).
- **Build balances from real ACH** (`credit_investment` / `payment_method: "ACH"`): they
  settle to `current_balance` **exactly** and stay **stable** (no market drift). The old
  `with_balance` trait fabricated market-priced holdings that drift by hundreds on a six-
  figure balance — which is why delta/conservation oracles must use **small, exact ACH**
  balances, never the priced buffer. ($10k/transaction cap → split via `ach_credits`.)
- **Rich-buffer pattern** for repeated mutations: one user with a large ACH balance
  (e.g. $50k = 5×$10k), withdraw ~$5/test → thousands of runs without re-seeding.
- **Generate fresh** only for: irreversible mutations (creating jars/kids, account-state),
  onboarding-itself, or when a unique value avoids a false positive on a drifting account.
- **Destructive split:** money/withdrawal → reuse a rich buffer; create-jars/kids → fresh
  user every run (own driver, own onboarding) so counts/state start clean.
- **Two layers:** Route A = API read-back (seed via gen API, read `current_balance`/state
  with the user's own token, no emulator — fast, deterministic, best for conservation/
  recon). Route B = on-device (log in AS the generated user, drive the UI). Prefer A where
  the note says "API-layer first".

## What's NOT seedable (must use the shared account or skip-with-reason)

The gen API seeds users, balances (ACH), jars, kids, account-states — but **not**: rewards
offers, funded super, or round-up accrual. Tests needing those use the shared account
(read-only) or ship an honest `skip-with-reason` until a seed recipe exists. **Generated
users also have no price history** → performance/Δ/%-change oracles are invalid on them.

## How coverage gets extended (the pipeline)

1. **Audit / map** — `feature-connectivity-map` workflow builds `docs/feature-connectivity-
   map.md`; the coverage audit grades each feature and lists gaps.
2. **Generate** — `test-case-generation-fanout` (N agents propose → dedupe with a consensus
   count → adversarial cross-check → ranked backlog at `docs/proposed-test-cases.md`).
3. **Human gate** — a person approves the case list.
4. **Build + verify** — `extend-appium-tests` / `build-backlog-ultracode` (Provision →
   Implement → Verify on the emulator pool → Refine → Re-verify → Report).
5. **Human gate** — approve what lands; commit on a branch; nothing reaches `main`
   unreviewed.

Throughout: assert real values, ground in source, skip-with-reason honestly, and respect
the 2-emulator RAM ceiling.

## Known production bug clusters the value tests target

Wrong Δ / change-value, % shown on a $0 base, totals not reconciling, count-after-create
not refreshing, history not refreshing after a cancel, obstructed Save button, rewards
brand webview not loading. Bias new tests toward these.
