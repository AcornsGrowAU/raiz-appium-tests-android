# Agent Playbook — what Claude should do on the Raiz suite

Read this before writing or running anything. It encodes the conventions and hard-won
gotchas so an agent is productive and safe from the first action.

## Operating principles

1. **Value over presence.** The suite's documented weakness is `is_visible()`/title
   checks. Every new/changed test must reconcile a real **value or state** against an
   authoritative oracle (backend `current_balance`, the published fee schedule,
   allocation × balance, the seeded amount). Ask: *"would this test fail if the app
   showed the WRONG number?"* If not, it's not done.
2. **Ground in the real source — don't guess.** `~/Android-AU` (Kotlin/Compose) has the
   real `contentDescription`/`testTag`/`text`/`android:id` locators, deep links
   (`raiz://…`), screen names and exact strings. `~/raiz-backend` (`app/models`,
   `config/routes.rb`, `app/controllers`) has the data model + endpoints — use it to
   know what to seed and what to reconcile against. `docs/feature-connectivity-map.md`
   shows how features wire together.
3. **DEV only, never prod.** All test data goes through `api-dev.raizinvest.com.au`.
   Never POST to `api.raizinvest.com.au`. Never seed or mutate the shared test account
   without explicit human consent.
4. **Be honest about blocked work.** Where state is non-seedable (rewards offers, funded
   super, round-up accrual) or a flow is gated/architecturally absent, ship a
   `pytest.skip(...)` **with a clear evidence-backed reason** — never a fake pass, a
   vacuous `if no data: return`, or an assertion that can't fail.
5. **One concern per change; verify it.** Re-run a changed test 3× on-device to catch
   flakes before declaring green. Distinguish a real failure from an infra wedge.

## Suite conventions (match these or tests silently break)

- **Tap the clickable CONTAINER, not the bare TextView.** Raiz buttons render their label
  on a child `View`; tapping the `TextView` misses. Use
  `//*[@clickable='true'][.//*[@text='LABEL']]` and click the **last** match.
- **Page Objects** live in `pages/`. Add locators/methods there; don't scatter raw XPaths
  in tests. Heavy-screen conftest fixtures (rewards/settings/performance/main_portfolio/
  transaction_history) have a one-shot reopen-retry for RAM-pressure timeouts.
- **Markers** (register new ones in `pytest.ini`): `value_api` (DEV-API value tests, no
  device), `genuser_e2e` (on-device, logs in AS a generated user, own driver),
  `destructive` (mutates state — opt-in via `RUN_DESTRUCTIVE=1`), plus the feature markers.
- **Home detection is build-dependent** — use `HomePage.is_loaded()` (accepts legacy and
  redesigned layouts), never gate only on the legacy "total investments value" header.
- **Generated users have NO price history** → never assert performance graphs / Δ /
  %-change / net-invested decomposition on them (those read $0). Keep those on the shared
  account, or skip.

## Hard environment constraints (these WILL bite)

- **2 GB-emulator RAM ceiling.** This Mac sustains ~2–3 concurrent emulator+Appium
  sessions. A 3rd session crashes UiAutomator2 / drops the device. **Verify on 2 stable
  emulators**, not 3. Free RAM before big runs.
- **PIN lockout.** Heavy/parallel PIN entry trips the app's "Too many attempts" dialog →
  the whole suite ERRORS at login. `conftest._ensure_logged_in` now recovers (dismiss +
  email/password re-login). If you see "Expected to be on Home screen after login" on
  *every* test, it's this (or a logged-out/wrong-build device), not 352 broken tests.
- **Build → layout.** The dev APK versionName misleads. Current build is **3252 /
  v2.40.1d** (redesigned home). Crawl the device / read source; don't assume the layout.
- **`~/Documents` TCC.** The repo is under `~/Documents`; the Bash sandbox can lose
  readdir/exec access there (Python won't even start). Fix: grant Full Disk Access +
  relaunch. `cat`/Read/Edit still work when readdir is blocked.
- **Concurrent UiAutomator2** sessions need distinct `systemPort`/`mjpegPort` (env-driven)
  or they collide on 8200/7810.

## How to work (the loop)

1. **Scope from the backlog.** `docs/proposed-test-cases.md` is the ranked, cross-checked
   list — each row has the oracle + refinement notes (split-scope, API-layer-first, exact-
   ACH-not-buffer, skip-with-reason). The notes are the spec.
2. **Provision data first.** Reuse the fixture registry (`utils/genuser_fixtures.py`);
   only generate fresh when a scenario truly needs it. See the test-data strategy doc.
3. **Implement** one test per file (distinct files avoid parallel-write collisions),
   grounded in source. Prefer the **API layer** for conservation/recon oracles (no device,
   deterministic).
4. **Verify** 3× on a stable emulator (or off-device for `value_api`).
5. **Stage on a branch**, report verdicts, and **let the human approve** before landing.

## Skills & workflows (already built — use them)

Invoke via the Workflow tool (`scriptPath` — note: this harness does NOT thread the `args`
input, so embed run data in the script). Watch with `/workflows`.

- **`extend-appium-tests`** — the end-to-end pipeline: Provision → Implement (5-wide) →
  Verify (emulator pool) → Refine → Efficiency → Re-verify → Report. Human-gated at the
  case list and before landing.
- **`feature-connectivity-map`** — maps every feature across app + backend → the
  connectivity report.
- **`test-case-generation-fanout`** — N agents generate candidate cases → dedupe (consensus
  count) → adversarial cross-check → ranked backlog.
- **`build-backlog-ultracode`** — implements the approved backlog (verify split: API
  off-pool, device on the 2 stable emulators).
- **`remediate-p1-ultracode` / `p1-reverify-investigate`** — fix existing tests
  (presence→value, un-skip, drop stale xfails) + adversarial verification.

**Pattern that works:** scout/scope inline → fan out a workflow for the parallel part →
adversarially verify → human gate. Keep on-device parallelism ≤ the number of stable
emulators; route API/no-device work off the device pool.

## Don'ts

- Don't hit prod, don't commit secrets, don't seed the shared account without consent.
- Don't assert exact deltas on market-priced (`with_balance`) balances — use **real ACH**
  fixtures (exact, stable) for delta/conservation oracles.
- Don't trust raw `pytest --lf`/`lastfailed` counts (stale node ids + RAM cascades inflate
  them) — rebuild with a full run or isolate-retriage.
- Don't run 3 concurrent device sessions on 2 GB AVDs; don't leave a vacuous/skip test
  masquerading as a pass.
