export const meta = {
  name: 'extend-appium-tests',
  description: 'Implement an approved set of Appium Android test cases (write 5-wide), verify them on a shared emulator pool (priority-ordered), reliability-refine, efficiency-tune, re-verify, and report for human approval',
  whenToUse: 'Invoked by the extend-appium-tests skill AFTER the Test Case Expert list is human-approved. Not a standalone entry point.',
  phases: [
    { title: 'Provision', detail: 'quartermaster prepares each case\'s test data: seed+onboard a reusable fixture, or hand back a fresh-per-run gen-API recipe, or route to the shared account' },
    { title: 'Implement', detail: 'engineers write each approved test case (up to 5 effective in parallel; no device needed)' },
    { title: 'Verify', detail: 'run each test on the shared emulator pool, highest-priority first; 3x to surface flakes' },
    { title: 'Refine', detail: 'reliability engineer hardens fragile/flaky tests' },
    { title: 'Efficiency', detail: 'efficiency engineer cuts cost without harming reliability' },
    { title: 'Re-verify', detail: 'rerun on the pool any test whose code changed during refine/efficiency' },
    { title: 'Report', detail: 'lead compiles the verified set + reliability/efficiency notes for human approval' },
  ],
}

// ---- inputs -----------------------------------------------------------------
// args = {
//   cases:     [{ id, title, feature, priority('P0'..'P3'), intent, oracle, file, test_name }],
//   emulators: [{ udid, appium, systemPort, mjpegPort }],
//              // concurrent UiAutomator2 sessions MUST each get a distinct systemPort/
//              // mjpegPort (config/capabilities.py reads ANDROID_SYSTEM_PORT/_MJPEG_PORT)
//              // or they collide on the 8200/7810 defaults. e.g.
//              // { udid:'emulator-5554', appium:'http://127.0.0.1:4723', systemPort:8201, mjpegPort:7811 }
//   branch:    'auto/extend-tests-...',   // already checked out by the skill
//   repoRoot:  '/abs/path/to/repo',
//   pyrun:     'venv/bin/python -m pytest',
// }
const cases = (args && args.cases) || []
const emulators = (args && args.emulators) || []
const branch = (args && args.branch) || '(current branch)'
const repoRoot = (args && args.repoRoot) || '.'
const PYRUN = (args && args.pyrun) || 'venv/bin/python -m pytest'

const PRANK = { P0: 0, P1: 1, P2: 2, P3: 3 }
const rank = (c) => (PRANK[String(c.priority || 'P2').toUpperCase()] ?? 2)

if (!cases.length) { log('No approved cases passed — nothing to do.'); return { tests: [] } }
if (!emulators.length) log('WARNING: no emulators supplied — verification phases are skipped (tests are written but unproven).')
log(`Approved cases: ${cases.length} | emulators: ${emulators.map(e => e.udid).join(', ') || 'none'} | branch: ${branch}`)

// ---- conventions every engineer must honour ---------------------------------
const SUITE = `Repo: ${repoRoot} (branch ${branch}). This is an Appium/UiAutomator2 + pytest suite for the Raiz Android app
(com.acornsau.android.development, activity com.raiz.main.MainActivity). NON-NEGOTIABLE conventions:
- Use the existing Page Objects in pages/ (SplashPage, LoginPage, OnboardingPage, HomePage, PinPage, JarsPage, KidsPage, etc.).
  Add locators/methods to a page object rather than scattering raw XPaths in tests.
- To tap a BUTTON whose label sits on a child View (Raiz buttons are null-text clickable containers), tap the clickable
  container, NOT the bare TextView:  //*[@clickable='true'][.//*[@text='LABEL']]  -> click the last match.
- Reuse test data per the reuse strategy: utils/genuser_fixtures.get_or_create_fixture_user(key) + the rich-buffer pattern.
  Only generate fresh users when a scenario truly needs it (utils/genuser_api). DEV API only (api-dev.raizinvest.com.au); never prod.
- DESTRUCTIVE-TEST DATA (mandatory): MONEY/withdrawal tests REUSE one rich-buffer user (~$1M) and draw only ~$5/run.
  Tests that CREATE jars/kids (or any additive sub-account) GENERATE A FRESH user EVERY run with their OWN driver — never
  reuse a fixture and never use the shared TEST_EMAIL/conftest driver (created entities are left behind, so a reused
  account accumulates them and the count/state oracle drifts). A fresh user gives a clean 0-baseline.
- Register any new pytest marker in pytest.ini. Standalone device tests build their own driver and set opts.udid from ANDROID_UDID.
- Assert real VALUES/state where possible (not mere element presence) — that is the suite's known weakness.
- Account state drifts (the shared test account now has jars/kids/insights); do not assume an empty account.`

// ---- structured-output schemas ----------------------------------------------
const IMPL = { type: 'object', additionalProperties: false,
  required: ['file', 'test_name', 'wrote_to_disk', 'summary'],
  properties: {
    file: { type: 'string', description: 'repo-relative path written, e.g. tests/test_xyz.py' },
    test_name: { type: 'string', description: 'the pytest node, e.g. test_foo or Class::test_foo' },
    wrote_to_disk: { type: 'boolean' },
    page_object_changes: { type: 'string' },
    summary: { type: 'string' },
  } }
const VERDICT = { type: 'object', additionalProperties: false,
  required: ['passed', 'runs', 'passes', 'flaky'],
  properties: {
    passed: { type: 'boolean', description: 'passed on every run' },
    runs: { type: 'integer' }, passes: { type: 'integer' },
    flaky: { type: 'boolean', description: 'passed sometimes, failed others' },
    failure_reason: { type: 'string' }, log_tail: { type: 'string' },
  } }
const REFINE = { type: 'object', additionalProperties: false,
  required: ['reliability_score', 'issues', 'revised'],
  properties: {
    reliability_score: { type: 'integer', description: '0-100 confidence this test is non-flaky & deterministic' },
    issues: { type: 'array', items: { type: 'string' } },
    revised: { type: 'boolean', description: 'true if you edited the test/page-object on disk' },
    summary: { type: 'string' },
  } }
const EFF = { type: 'object', additionalProperties: false,
  required: ['changed'],
  properties: {
    changed: { type: 'boolean', description: 'true if you edited code on disk to make it more efficient' },
    savings: { type: 'string', description: 'what got cheaper (logins avoided, fixtures shared, steps merged, runtime cut)' },
    behavior_preserved: { type: 'boolean' },
    rationale: { type: 'string' },
  } }

const PROVISION = { type: 'object', additionalProperties: false,
  required: ['case_id', 'mode', 'rationale'],
  properties: {
    case_id: { type: 'string' },
    mode: { type: 'string', description: 'reuse-fixture | dynamic | shared-account' },
    fixture_key: { type: 'string', description: '(reuse) registry key the test passes to get_or_create_fixture_user()' },
    fixture_status: { type: 'string', description: '(reuse) seeded+onboarded | reused-existing | seeded-onboarding-pending' },
    onboarded: { type: 'boolean', description: '(reuse) true if driven through first-login onboarding this run' },
    api_recipe: { type: 'string', description: '(dynamic) the exact gen_create({...}) payload + a short Python snippet the engineer embeds to seed a FRESH user every run' },
    rationale: { type: 'string' },
  } }

// ---- prompt builders --------------------------------------------------------
const provisionPrompt = (c, em) => `You are the TEST-DATA PROVISIONER ("quartermaster"). Your sole job: decide and PREPARE
the test data this ONE case needs, so the engineer never has to. Apply the reuse strategy exactly.
${SUITE}

CASE ${c.id} [${c.priority}] — ${c.title}
Feature: ${c.feature}
Intent: ${c.intent}
Oracle (the value/state that proves a pass): ${c.oracle}

Pick the MODE (memory genuser-test-data-reuse-strategy is authoritative):
- "reuse-fixture" — state is SEEDABLE and reusable across runs (presence/value reads; money via the rich-buffer pattern).
  ACTIONS: pick/define a stable key in utils/genuser_fixtures.py (add a builder if none fits the exact state this oracle
  needs), seed it once via get_or_create_fixture_user(key), THEN drive emulator ${em.udid} (APPIUM_HOST=${em.appium},
  ANDROID_SYSTEM_PORT=${em.systemPort}, ANDROID_MJPEG_PORT=${em.mjpegPort}) through first-login ONBOARDING once
  (OnboardingPage.complete) and call mark_onboarded(key). Onboarding is SERVER-SIDE, so doing it once makes the fixture
  onboarded on every device — later logins skip the gauntlet. Return fixture_key + fixture_status + onboarded.
- "dynamic" — state mutates IRREVERSIBLY per run (creating jars/kids, account-state, "first investment made"). Do NOT
  pre-seed or onboard. Produce the EXACT gen_create({...}) payload AND a short Python snippet the engineer pastes so the
  TEST generates a fresh user every run (the test onboards it at runtime). Put both in api_recipe.
- "shared-account" — state is NOT seedable by the gen API (confirmed: rewards offers, super). The test uses the shared
  TEST_EMAIL account; the conftest login gate handles parallel-run contention. Return mode + why in rationale.

To run on-device use: ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} ${PYRUN} ...
Leave the registry/recipe in a state the engineer can consume directly. Return the schema. case_id MUST be "${c.id}".`

const implPrompt = (c, contract) => `You are a Test Automation Engineer. Implement EXACTLY this approved test case by WRITING it to disk.
${SUITE}

CASE ${c.id} [${c.priority}] — ${c.title}
Feature: ${c.feature}
Intent: ${c.intent}
Oracle (what proves it passes): ${c.oracle}
Target file: ${c.file}   Target test name: ${c.test_name}

TEST DATA — provisioned for you by the quartermaster; use EXACTLY this, do not re-decide it:
${JSON.stringify(contract || { note: 'no contract provided — choose data per the reuse strategy yourself' }, null, 1)}
  • mode reuse-fixture  -> call get_or_create_fixture_user("<fixture_key>"); it's already seeded + onboarded.
  • mode dynamic        -> paste the api_recipe so the test seeds a FRESH user each run, then onboards it at runtime.
  • mode shared-account -> use the shared-account conftest fixture; do not generate a user.

Read the existing suite + the target file + the page objects you need first. Then write a single, self-contained,
deterministic pytest test (and any small page-object additions). DO NOT run it — verification happens separately.
Do not touch other engineers' files. When done, return the schema. wrote_to_disk MUST reflect reality.`

const verifyPrompt = (c, em) => `You are verifying ONE test on a dedicated emulator. Device: ${em.udid}  Appium: ${em.appium}
Working dir: ${repoRoot} (branch ${branch}).

Run ONLY this test, THREE times, to surface flakiness (the env vars pin this device + a
distinct UiAutomator2 systemPort/mjpegPort so you never collide with the other workers):
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} ${PYRUN} ${c.file}::${c.test_name} -p no:cacheprovider -o addopts="" -q

Use this exact emulator/Appium endpoint (do not touch other emulators — they belong to other workers). If the device is
mid-onboarding or dirty, that is part of the test's job to handle; report what you saw. Capture the last ~25 lines of
output. Return the schema: passed=true only if all 3 runs passed; flaky=true if results were mixed.`

const refinePrompt = (c) => `You are the Test Automation RELIABILITY Refinement Engineer. Harden this test against flakiness
WITHOUT changing what it validates.
${SUITE}

Test: ${c.file}::${c.test_name}  (${c.title})
Most recent verdict: ${JSON.stringify(c.verdict || 'not run')}

Read the test on disk. Hunt for: hardcoded sleeps that should be explicit waits, presence-only assertions that should be
value assertions, order/state dependence, brittle XPaths, unhandled onboarding/coachmarks, races on slow emulators
(~1-3s RTT), and bare TextView taps that should hit the clickable container. If you find real issues, EDIT the test/page
object on disk to fix them (set revised=true). If it's already solid, set revised=false. Return the schema.`

const effPrompt = (c) => `You are the Test Automation EFFICIENCY Engineer. Make this test cheaper to run WITHOUT reducing
reliability or coverage.
${SUITE}

Test: ${c.file}::${c.test_name}  (${c.title})

Look for: redundant logins/onboarding that a shared fixture or session-scope could remove, fresh user generation that the
reuse/rich-buffer strategy makes unnecessary, duplicated setup across sibling tests, oversized waits, and cases that could
share a driver. Only EDIT on disk when you are confident behaviour is preserved (set changed=true, behavior_preserved=true).
If a speedup is plausible but risky, DON'T apply it — describe it in rationale instead. Return the schema.`

const reportPrompt = (rows) => `You are the Test Automation LEAD. Compile a concise human-review report for the approver.
For each test give: id, title, priority, file::test, final verdict (pass/flaky/fail + runs), reliability score, and any
efficiency change applied or proposed. Then: (1) a one-line GREEN/AMBER/RED status for the whole batch, (2) which tests are
safe to land, (3) which need human attention and why, (4) any cross-cutting reliability or efficiency recommendation.
DATA:\n${JSON.stringify(rows, null, 1)}`

// ---- shared 3-slot emulator pool (the "lead" allocating by priority) --------
// Each emulator is one worker; workers drain a single priority-sorted queue, so
// the highest-priority unverified cases always claim the next free device.
async function poolVerify(items, phaseName) {
  const todo = items.filter(Boolean)
  if (!emulators.length || !todo.length) return
  const q = [...todo].sort((a, b) => rank(a) - rank(b))
  let k = 0
  const next = () => (k < q.length ? q[k++] : null)   // synchronous claim — no await between read+increment, so race-free
  await parallel(emulators.map((em) => async () => {
    let c
    while ((c = next())) {
      const v = await agent(verifyPrompt(c, em), { label: `${phaseName}:${c.id}@${em.udid}`, phase: phaseName, schema: VERDICT })
      c.verdict = v
      c.dirty = false
    }
  }))
}

// ---- PHASE 0 — Provision test data (quartermaster) --------------------------
// One agent per case decides the data MODE and prepares it: seed+onboard a reusable
// fixture (uses an emulator), hand back a fresh-per-run gen-API recipe, or route to
// the shared account. Runs on the pool BEFORE Implement so reusable fixtures are
// already onboarded by the time Verify logs in (no onboarding gauntlet mid-verify).
phase('Provision')
const contracts = {}
if (emulators.length) {
  const pq = [...cases].sort((a, b) => rank(a) - rank(b))
  let pk = 0
  const nextP = () => (pk < pq.length ? pq[pk++] : null)
  await parallel(emulators.map((em) => async () => {
    let c
    while ((c = nextP())) {
      const p = await agent(provisionPrompt(c, em), { label: `provision:${c.id}@${em.udid}`, phase: 'Provision', schema: PROVISION })
      if (p) contracts[c.id] = p
    }
  }))
} else {
  // No emulators: still produce contracts (dynamic/shared decisions + recipes); a
  // reuse fixture simply can't be pre-onboarded here and will onboard on first run.
  const ph = await parallel(cases.map((c) => () =>
    agent(provisionPrompt(c, { udid: '(none)', appium: '(none)', systemPort: 0, mjpegPort: 0 }),
      { label: `provision:${c.id}`, phase: 'Provision', schema: PROVISION })))
  ph.filter(Boolean).forEach((p) => { contracts[p.case_id] = p })
}
log(`Provisioned data for ${Object.keys(contracts).length}/${cases.length} cases ` +
  `(${Object.values(contracts).filter((p) => p.mode === 'reuse-fixture').length} reuse, ` +
  `${Object.values(contracts).filter((p) => p.mode === 'dynamic').length} dynamic, ` +
  `${Object.values(contracts).filter((p) => p.mode === 'shared-account').length} shared).`)

// ---- PHASE 1 — Implement (write-only, up to 5 effective in parallel) --------
phase('Implement')
const built = (await parallel(cases.map((c) => () =>
  agent(implPrompt(c, contracts[c.id]), { label: `impl:${c.id}`, phase: 'Implement', schema: IMPL })
    .then((r) => r && ({ ...c, impl: r, contract: contracts[c.id], dirty: true }))
))).filter(Boolean)
log(`Implemented ${built.length}/${cases.length} cases (${built.filter((c) => c.impl.wrote_to_disk).length} confirmed on disk).`)

// ---- PHASE 2 — Verify on the shared pool ------------------------------------
phase('Verify')
await poolVerify(built, 'Verify')
const greenAfterImpl = built.filter((c) => c.verdict && c.verdict.passed).length
log(`Initial verify: ${greenAfterImpl}/${built.length} green${emulators.length ? '' : ' (skipped — no emulators)'}.`)

// ---- PHASE 3 — Reliability refinement (no device) ---------------------------
phase('Refine')
const refined = (await parallel(built.map((c) => () =>
  agent(refinePrompt(c), { label: `refine:${c.id}`, phase: 'Refine', schema: REFINE })
    .then((r) => { c.refine = r; if (r && r.revised) c.dirty = true; return c })
))).filter(Boolean)

// ---- PHASE 4 — Efficiency tuning (no device) --------------------------------
phase('Efficiency')
await parallel(refined.map((c) => () =>
  agent(effPrompt(c), { label: `eff:${c.id}`, phase: 'Efficiency', schema: EFF })
    .then((e) => { c.efficiency = e; if (e && e.changed) c.dirty = true; return c })
))

// ---- PHASE 5 — Re-verify only what changed ----------------------------------
phase('Re-verify')
const dirty = refined.filter((c) => c.dirty)
log(`Re-verifying ${dirty.length} test(s) whose code changed during refine/efficiency.`)
await poolVerify(dirty, 'Re-verify')

// ---- PHASE 6 — Lead synthesis -----------------------------------------------
phase('Report')
const rows = refined.map((c) => ({
  id: c.id, title: c.title, priority: c.priority, node: `${c.impl.file}::${c.impl.test_name}`,
  data_mode: c.contract && c.contract.mode, fixture_key: c.contract && c.contract.fixture_key,
  verdict: c.verdict || 'not-run', reliability_score: c.refine && c.refine.reliability_score,
  reliability_issues: (c.refine && c.refine.issues) || [],
  efficiency: c.efficiency && (c.efficiency.changed ? `applied: ${c.efficiency.savings}` : (c.efficiency.rationale || 'none')),
}))
const report = await agent(reportPrompt(rows), { label: 'lead:report', phase: 'Report' })

return {
  branch,
  emulators: emulators.map((e) => e.udid),
  counts: {
    cases: cases.length, implemented: built.length,
    green: refined.filter((c) => c.verdict && c.verdict.passed).length,
    flaky: refined.filter((c) => c.verdict && c.verdict.flaky).length,
    failed: refined.filter((c) => c.verdict && !c.verdict.passed && !c.verdict.flaky).length,
  },
  report,
  tests: rows,
  provisioning: contracts,
}
