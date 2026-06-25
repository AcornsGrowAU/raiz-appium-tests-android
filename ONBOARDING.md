# Raiz Android Automation — Onboarding & Knowledge Pack

Start here. This is the entry point for anyone (human or a Claude/AI agent) joining the
Raiz Android Appium test-automation effort. It explains what Raiz is, how the suite is
built, how to get running, and **what an AI agent should and shouldn't do** here.

> **No secrets in this pack.** Credentials, PINs, and device UDIDs live in `config/`
> (`.env`/`config/settings.py`) and the team password manager — never in these docs.
> Where a doc needs auth, it points to *where* the secret lives, not the value.

---

## 1. What this is

**Raiz Invest (Australia)** is a consumer micro-investing app. This repo is its
**Appium (UiAutomator2) + pytest** Android UI-automation suite. Two source repos back
the product and ground the tests:

| Repo | What | Local clone |
|------|------|-------------|
| `AcornsGrowAU/Android-AU` | the Android app (Kotlin, Compose-heavy) | `~/Android-AU` |
| `AcornsGrowAU/backend` | the Raiz API (Ruby on Rails) — data model + `/v1` endpoints | `~/raiz-backend` |

Access is via the `gh` CLI (`gh auth login`, scope `repo`). Clone shallow:
`git clone --depth 1 https://github.com/AcornsGrowAU/<repo>`. **Read these to get REAL
resource-ids / strings / fee values / portfolio names / flows — never guess.**

## 2. The one thing to understand: "green ≠ verified"

The suite was historically **green but hollow** — it confirmed screens *rendered*, rarely
that the *dollar figures* were correct (presence-over-value). The whole strategy now is to
convert presence checks into **value/state oracles that reconcile against the backend**,
and to assert the **cross-feature money-conservation invariants** that are the highest-
consequence class of fintech bug. See `docs/raiz-automation-handbook/test-strategy.md`.

## 3. Get running (the short version)

1. **Repos + access:** clone the two source repos (above); `gh auth status` should show `repo` scope.
2. **Emulators:** boot Android emulators (the rig assumes up to 3; **2 GB AVDs only sustain ~2 stable sessions** — see the RAM-ceiling note). Install the current dev APK (build **3252 / v2.40.1d**, package `com.acornsau.android.development`).
3. **Appium:** one server per device (`appium --relaxed-security -p 4723` / `4724` / `4725`); each session needs a distinct `systemPort`/`mjpegPort` (env-driven).
4. **Python:** `venv/bin/python -m pytest ...` with `ANDROID_UDID` + `APPIUM_HOST` set per device.
5. **Test data:** seeded via the **DEV test-data-gen API** (`api-dev.raizinvest.com.au`) — never prod. See the test-data strategy doc.

Full detail + every gotcha: `docs/raiz-automation-handbook/environment-and-access.md`.

## 4. What an AI agent should do here (read before acting)

The full playbook is `docs/raiz-automation-handbook/agent-playbook.md`. The essentials:

- **Ground in the real source.** Before writing a locator/oracle, grep `~/Android-AU`
  (Compose: `contentDescription` is the primary hook, `testTag` sparse) and
  `~/raiz-backend/app/models` + `config/routes.rb` for the data model + endpoints.
- **Assert values, not presence.** A test that passes when the app shows the *wrong*
  number is worthless. Reconcile against backend `current_balance` / the published
  schedule / the seeded amount.
- **DEV only. Never prod.** Never POST to `api.raizinvest.com.au`. Never seed/mutate the
  shared test account without explicit human consent.
- **Be honest about blocked work.** If state isn't seedable (rewards offers, funded
  super, round-up accrual) or a flow is gated, ship a **skip-with-reason**, never a fake
  or vacuous pass.
- **Respect the hard constraints:** the 2 GB-emulator RAM ceiling (≤2–3 sessions), the
  PIN-lockout recovery, build→layout differences, and the clickable-container tap rule.

## 5. The handbook (this folder + existing docs)

| Doc | Purpose |
|-----|---------|
| `docs/raiz-automation-handbook/agent-playbook.md` | **What Claude should do** — conventions, gotchas, do/don't, how to run the skills/workflows |
| `docs/raiz-automation-handbook/environment-and-access.md` | Repos, gh access, emulators/builds, Appium rig, the DEV gen API, infra gotchas (RAM, PIN lockout, TCC) |
| `docs/raiz-automation-handbook/test-strategy.md` | Value-over-presence philosophy, test-data reuse + real-ACH fixtures, the coverage audit |
| `docs/feature-connectivity-map.md` | How every feature wires to every other (app + backend), + a value/state-oracle cheat-sheet |
| `docs/proposed-test-cases.md` | The ranked backlog of test cases to add (consensus + cross-check confidence) |
| `docs/qa_locator_reference.md` | Verified on-device locators/strings per screen (calibrate to the current build) |

## 6. Capabilities already built (the multi-agent skills)

This repo ships `.claude/skills` + `.claude/workflows` that orchestrate the work:

- **`extend-appium-tests`** (skill) — the end-to-end pipeline: a human-gated Test-Case
  Expert, a Test-Data Provisioner ("quartermaster"), 5 engineers, reliability + efficiency
  passes, and a lead coordinating verification across a shared emulator pool.
- Supporting workflows: `feature-connectivity-map`, `test-case-generation-fanout`,
  `remediate-p1-ultracode`, `build-backlog-ultracode`, `p1-reverify-investigate`.

See `docs/raiz-automation-handbook/agent-playbook.md` §"Skills & workflows" for when/how to
use each.
