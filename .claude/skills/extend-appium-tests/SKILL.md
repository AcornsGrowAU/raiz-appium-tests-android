---
name: extend-appium-tests
description: Create, expand, and improve front-end tests for the Raiz Appium Android suite via a coordinated multi-agent run. A Test Case Expert proposes a prioritized, human-approved test-case list (gating everything else); then 5 engineers implement, a reliability engineer and an efficiency engineer refine, and a lead coordinates verification across a shared 3-emulator pool — staging everything on a branch for a final human approval before it lands. Use when the user wants to grow or harden the Appium test coverage.
---

# Extend Appium Tests — multi-agent orchestrator

Grows and hardens the front-end Appium/pytest suite. Two stages: an **interactive,
human-gated planning stage** you run from the main loop, then a **deterministic
implementation+verification Workflow** (`.claude/workflows/extend-appium-tests.js`).

## Role → mechanism mapping (read this first)

The user describes a team of agents. Here is how each maps to something that actually
runs, given that **sub-agents cannot negotiate in real time** and **on-device work is
serial per emulator** (one Appium session each):

| Requested role | How it is realized |
|---|---|
| **Test Case Expert** (gates everything) | An `Explore`/`general-purpose` agent you run in **this** loop. Its list is shown to the user and iterated until approved. No workflow starts before approval. |
| **Test Data Provisioner** ("quartermaster") | The workflow's `Provision` phase — one agent per case decides the data mode and prepares it: seed + emulator-onboard a **reusable** fixture (stored in the registry), hand back a fresh-per-run **gen-API recipe** for **dynamic** state, or route to the **shared account** when the state isn't seedable (rewards/super). Engineers consume its per-case data contract instead of each re-deciding. |
| **Test Automation Engineers ×5** | The workflow's `Implement` phase — up to 5 effective in parallel. Writing code needs no device. |
| **Test Automation Lead** (owns 3 emulators, prioritizes) | The workflow itself: a **priority-sorted queue feeding a 3-slot emulator pool** (one worker per emulator). Highest-priority unverified case claims the next free device — that *is* the lead allocating by priority. |
| **Reliability Refinement Engineer ×1** | The `Refine` phase. |
| **Efficiency Engineer ×1** | The `Efficiency` phase. |

Anything changed by refine/efficiency is **re-verified on the pool** before it counts
as green. Nothing reaches the live suite until the user approves — work is staged on a
branch.

## Hard constraints (do not violate)

- **On-device parallelism = number of emulators (≤3).** Never run two Appium sessions
  against one emulator/Appium endpoint at once.
- **DEV API only** (`api-dev.raizinvest.com.au`). Never hit production. Never seed the
  shared TEST_EMAIL account without explicit user consent.
- **Bash needs `~/Documents` access.** The repo is under `~/Documents` (TCC-protected);
  if Bash readdir/exec is blocked there, the user must grant Full Disk Access and
  relaunch (see memory `macos-documents-tcc-bash-block`). Verify before Stage B.
- Follow the suite conventions and the **reuse strategy** (memory
  `genuser-test-data-reuse-strategy`, `raiz-ondevice-withdrawal-e2e`,
  `raiz-appium-suite`). Assert real **values**, not mere presence.

---

## Stage A — Test Case Expert (interactive gate)

1. **Brief the expert.** Spawn one agent (subagent_type `Explore` for read-heavy
   scans, or `general-purpose` if it must drive the app) with this charter:
   - Read the suite: `tests/`, `pages/`, `conftest.py`, `pytest.ini` markers, and the
     coverage map (`~/Downloads/raiz-test-coverage-map.html` if present).
   - Read relevant memory: `raiz-appium-suite`, `raiz-jira-bug-clusters`,
     `raiz-account-state-drift`, `raiz-ondevice-withdrawal-e2e`,
     `raiz-scenario-test-initiative`.
   - **Explore the live app via ADB/Appium, read-only**: `adb devices`, launch the app,
     dump current screens (`uiautomator dump` or an Appium page_source helper), and
     enumerate features/flows that exist on-device but are thin or absent in the suite.
     Do **not** mutate account data.
   - Output a **prioritized candidate list**, each row:
     `{ id, title, feature, priority(P0..P3), intent, oracle, file, test_name, rationale }`
     where `oracle` is the concrete value/state that proves a pass, `file`/`test_name`
     are the target location, and **each engineer owns a distinct file** (no two cases
     target the same file, to avoid parallel-write conflicts).
   - Bias toward **real validations** (values, balances, reconciliation, state
     transitions) over presence checks, and toward the known bug clusters.

2. **Present the list to the user. Iterate.** Show it as a compact table. Invite
   add/remove/re-scope/re-prioritize. **Do not proceed** until the user explicitly
   approves the set. This gate is mandatory.

## Stage B — set up the shared emulator pool

Only after approval:

1. Confirm Bash has repo access: `ls "<repo>/venv/bin" >/dev/null 2>&1 && echo ok`.
   If blocked, stop and ask the user to grant Full Disk Access + relaunch.
2. **Detect emulators**: `adb devices` → take up to 3 booted `emulator-*` / device ids.
   If zero, stop and tell the user to boot at least one (RAM ceiling ~3 sessions per
   memory `raiz-multidevice-and-builds`).
3. **Map each device to an Appium endpoint** (one server per device for true
   parallelism). Reuse the existing rig if present — read `scripts/run_parallel.sh` for
   the port convention (typically 4723/4725/4727). Start any missing servers and health
   check `GET /status`. Build `emulators = [{udid, appium}, ...]`.
4. **Stage on a branch**: create `auto/extend-tests-<short-desc>` off the current branch
   so nothing lands on the main branch until approved.

## Stage C — run the implementation workflow

Invoke the saved workflow with the approved cases + pool. This is an explicit,
user-initiated multi-agent run, so calling `Workflow` here is authorized:

```
Workflow({
  name: 'extend-appium-tests',
  args: {
    cases: <approved list from Stage A>,
    emulators: [{udid, appium}, ...],   // from Stage B
    branch: 'auto/extend-tests-...',
    repoRoot: '<abs repo path>',
    pyrun: 'venv/bin/python -m pytest',
  },
})
```

The workflow runs **Provision(pool) → Implement → Verify(pool) → Refine → Efficiency →
Re-verify(pool) → Report** and returns `{ branch, counts, report, tests, provisioning }`.
The **Provision** phase (the Test Data Provisioner) runs first so reusable fixtures are
seeded + onboarded before Implement, and each engineer is handed a ready data contract
(reuse-fixture key / dynamic gen-API recipe / shared-account). Watch progress with
`/workflows`. (If you need to iterate on the workflow script, edit
`.claude/workflows/extend-appium-tests.js` and re-invoke.)

NOTE — this harness does not thread the `args` input into a workflow's `args` global.
Pass run data by EMBEDDING it in a copy of the script (a `const EMBED = {...}` block the
inputs fall back to) and invoke by `scriptPath`, rather than relying on `args`.

## Stage D — final human gate, then land

1. Relay the lead's `report` + `counts` to the user: per-test verdict, reliability
   score, efficiency notes, and the GREEN/AMBER/RED batch status. Call out anything
   flaky/failed and why.
2. **Get explicit approval** for which tests to keep. The code is already on the branch.
3. On approval: keep the approved tests, revert the rest, ensure new markers are in
   `pytest.ini`, and hand the branch back (or open a PR / merge) per the user's wish.
   Then update memory (`raiz-appium-suite` / `raiz-ondevice-withdrawal-e2e`) with the
   new coverage.

## Scaling notes

- Tune fan-out to scope: a handful of cases → small run; "comprehensively expand
  coverage" → larger Stage-A list, and consider 3 verify-runs already built in for flake
  detection.
- If only 1–2 emulators are up, the pool simply runs narrower — the priority queue still
  serves the most important cases first.
- Re-running the whole skill later reuses the same workflow; the expensive part
  (verification) is always bounded by the emulator count.
