export const meta = {
  name: 'build-backlog-ultracode',
  description: 'Implement the approved proposed-test-cases backlog (28 non-deferred cases) grounded in the app source + backend + connectivity map + the backlog notes. Provision fixtures up front, write one test per case (distinct files), verify (API cases off-pool, device cases on the 2 stable emulators 3x), reliability-refine, re-verify changed device tests, and report for the human gate.',
  phases: [
    { title: 'Provision', detail: 'quartermaster adds any missing fixture builders + seeds them via the gen API; returns a per-case data manifest' },
    { title: 'Implement', detail: 'one engineer per case writes the test, grounded in the backlog notes + app source + backend + connectivity map' },
    { title: 'Verify', detail: 'API/no-device cases run off-pool in parallel; on-device cases run 3x on the 2 stable emulators' },
    { title: 'Refine', detail: 'reliability engineer hardens fragile tests (no device)' },
    { title: 'Re-verify', detail: 'rerun on the pool any device test whose code changed' },
    { title: 'Report', detail: 'lead compiles verdicts for the human gate' },
  ],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const ANDROID = '/Users/joshua/Android-AU'
const BACKEND = '/Users/joshua/raiz-backend'
const CMAP = REPO + '/docs/feature-connectivity-map.md'
const BACKLOG = REPO + '/docs/proposed-test-cases.md'
const PYRUN = 'venv/bin/python -m pytest'
const branch = 'auto/extend-tests-backlog'
const EMU = [
  { udid: 'emulator-5554', appium: 'http://127.0.0.1:4723', systemPort: 8201, mjpegPort: 7811 },
  { udid: 'emulator-5556', appium: 'http://127.0.0.1:4724', systemPort: 8202, mjpegPort: 7812 },
]

const RESOURCES = `RESOURCES (use ALL — read-only except the test/fixture files you own):
- BACKLOG (authoritative per-case spec): ${BACKLOG} — find YOUR case's row by key for its oracle, data_mode, consensus/conf,
  and the verdict/notes. The notes column carries the cross-checkers' REFINEMENTS and MUST be honoured: split-scope,
  API-layer-first, use small EXACT ACH balances (not the repricing buffer), assert STATE not enforcement, spike-gate, drop
  unproven sub-clauses, skip-with-reason where data is non-seedable. A 'refine' verdict means build the refined scope.
- APP SOURCE: ${ANDROID} — real Kotlin/Compose source (build 3252). Get REAL contentDescription/testTag/text/id locators,
  deep links (raiz://...), screen/flow names, and exact strings here instead of guessing. Quote zsh grep globs (--include="*.kt").
- BACKEND: ${BACKEND} — Rails API. app/models (associations = the real feature wiring + the fields to seed/assert via the
  gen API) and config/routes.rb + app/controllers (the /v1 endpoints). Use it to ground oracles in backend ground truth.
- CONNECTIVITY MAP: ${CMAP} — feature functionality, cross-feature edges, and the value/state-oracle cheat-sheet.
CONVENTIONS: tap the CLICKABLE CONTAINER not the bare TextView (//*[@clickable='true'][.//*[@text='LABEL']], last match);
assert real VALUES/state, never presence; DEV API only (api-dev.raizinvest.com.au), never prod; reuse strategy + real-ACH
fixtures (exact, stable — small EXACT amounts for deltas, never the priced buffer); register new markers in pytest.ini;
conftest recovers PIN lockout + serializes shared-account logins; generated users have NO price history (no perf/Δ oracles);
build 3252. Be HONEST: where a case is spike-gated/non-seedable/blocked, ship a skip-with-reason (clear evidence), never a
fake or vacuous pass. One DISTINCT file per case (no cross-file edits).`

const CASES = [
  { id: 'new-kid-zero-start', priority: 'P0', data_mode: 'reuse-fixture' },
  { id: 'jar-target-roundtrip', priority: 'P0', data_mode: 'dynamic' },
  { id: 'deposit-main-routing-isolation', priority: 'P0', data_mode: 'dynamic' },
  { id: 'portfolio-style-allocation-weights', priority: 'P0', data_mode: 'reuse-fixture' },
  { id: 'main-jar-transfer-conserves', priority: 'P0', data_mode: 'dynamic' },
  { id: 'jar-goal-progress-ring', priority: 'P0', data_mode: 'reuse-fixture' },
  { id: 'kid-fund-no-cross-post', priority: 'P0', data_mode: 'dynamic' },
  { id: 'kid-initial-below5-rejected', priority: 'P0', data_mode: 'dynamic' },
  { id: 'withdraw-over-balance-rejected', priority: 'P0', data_mode: 'dynamic' },
  { id: 'tier-gating-kids-jars', priority: 'P0', data_mode: 'dynamic' },
  { id: 'jar-six-cap-enforced', priority: 'P1', data_mode: 'reuse-fixture' },
  { id: 'home-total-conservation', priority: 'P1', data_mode: 'dynamic' },
  { id: 'per-kid-portfolio-independent', priority: 'P1', data_mode: 'dynamic' },
  { id: 'jar-name-icon-persist', priority: 'P1', data_mode: 'dynamic' },
  { id: 'networth-total-investments-recon', priority: 'P1', data_mode: 'dynamic' },
  { id: 'kid-summary-rows-recon', priority: 'P1', data_mode: 'reuse-fixture' },
  { id: 'myfinance-empty-state', priority: 'P1', data_mode: 'dynamic' },
  { id: 'jar-below-min-deposit-rejected', priority: 'P1', data_mode: 'dynamic' },
  { id: 'inflow-triple-oracle', priority: 'P1', data_mode: 'dynamic' },
  { id: 'funding-source-contents', priority: 'P1', data_mode: 'dynamic' },
  { id: 'recurring-create-roundtrip', priority: 'P1', data_mode: 'dynamic' },
  { id: 'deposit-sub5-rejected', priority: 'P1', data_mode: 'dynamic' },
  { id: 'net-invested-ledger-recon', priority: 'P1', data_mode: 'dynamic' },
  { id: 'pending-vs-settled-distinction', priority: 'P1', data_mode: 'dynamic' },
  { id: 'per-jar-portfolio-independent', priority: 'P2', data_mode: 'reuse-fixture' },
  { id: 'kid-eight-cap-enforced', priority: 'P2', data_mode: 'dynamic' },
  { id: 'recurring-into-jar-no-goal', priority: 'P2', data_mode: 'dynamic' },
  { id: 'per-account-performance-tab', priority: 'P2', data_mode: 'reuse-fixture' },
]
const fileFor = (c) => `tests/test_${c.id.replace(/-/g, '_')}.py`
const PRANK = { P0: 0, P1: 1, P2: 2, P3: 3 }
const rank = (c) => (PRANK[c.priority] ?? 2)

const IMPL = { type: 'object', additionalProperties: false,
  required: ['id', 'file', 'test_name', 'needs_device', 'wrote_to_disk', 'summary'],
  properties: {
    id: { type: 'string' }, file: { type: 'string' }, test_name: { type: 'string' },
    needs_device: { type: 'boolean', description: 'true if the test drives the app on an emulator; false if pure DEV-API (value_api)' },
    blocked: { type: 'boolean', description: 'true if shipped as skip-with-reason (spike-gated / non-seedable)' },
    page_object_changes: { type: 'string' }, wrote_to_disk: { type: 'boolean' }, summary: { type: 'string' },
  } }
const VERDICT = { type: 'object', additionalProperties: false,
  required: ['id', 'verdict', 'runs'],
  properties: { id: { type: 'string' }, verdict: { type: 'string', description: 'green | flaky | red | skip-with-reason' },
    runs: { type: 'integer' }, passes: { type: 'integer' }, failure_reason: { type: 'string' }, log_tail: { type: 'string' } } }
const REFINE = { type: 'object', additionalProperties: false,
  required: ['id', 'revised'],
  properties: { id: { type: 'string' }, reliability_score: { type: 'integer' },
    issues: { type: 'array', items: { type: 'string' } }, revised: { type: 'boolean' }, summary: { type: 'string' } } }

const provisionPrompt = `You are the TEST-DATA PROVISIONER for the backlog build. Read the full backlog (${BACKLOG}) and the
existing fixtures (utils/genuser_fixtures.py + utils/genuser_api.py). Determine EVERY fixture the 28 cases need and make it
exist, using REAL ACH balances (exact, stable) per the reuse strategy. Likely NEW builders to add to genuser_fixtures.py:
a BARE kid (no balance, for new-kid-zero-start / cap tests), bare jars for jar-six-cap, a parent with 6 jars / 8 kids for
the cap tests, plan-tier users (lite/regular/plus — confirm the gen API accepts plan_identifier='lite'/'plus'; if not, say
so for tier-gating), per-style portfolio users (Aggressive/Conservative/Moderate — confirm portfolio_name accepted), and
small-exact-ACH seeded users for the conservation/recon/min-rejection cases. Existing reusable fixtures
(presence_funded, rich/kids/jars buffers, kids/jars siblings) are already real-ACH — reuse them where they fit.
${RESOURCES}
ACTIONS: add the missing builders + FIXTURES entries (idempotent, distinct keys), seed each once via get_or_create_fixture_user
/ gen_create (API only, NO device — onboarding happens lazily on first test login), and verify balances are exact. Return a
concise manifest: for each of the 28 case ids, which fixture key (or 'fresh-per-run recipe' / 'shared-account') it should
use, and flag any fixture that could NOT be seeded (e.g. lite/plus plan, a portfolio style) so those cases ship skip-with-reason.`

const implPrompt = (c, manifest) => `You are a Test Automation Engineer. Implement EXACTLY this approved backlog case by
WRITING one self-contained, deterministic pytest test to ${fileFor(c)} (your OWN file — do not touch others').
${RESOURCES}

CASE key: ${c.id}  (priority ${c.priority}, data_mode ${c.data_mode})
Read its row + notes in the backlog (${BACKLOG}) for the precise oracle + refinement — that is your spec. Use the
provisioned fixture for this case (manifest below); if the manifest flags it unseedable, ship a skip-with-reason.
PROVISION MANIFEST:\n${JSON.stringify(manifest || 'see backlog/fixtures', null, 1)}

Ground the locators/flows in the real app source (${ANDROID}, build 3252) and the oracle in the backend model/endpoints
(${BACKEND}). Prefer the API layer where the note says 'API-layer first' (no device, deterministic). DO NOT run it —
verification is separate. Set needs_device honestly (false for pure DEV-API/value_api tests). Register any new marker in
pytest.ini. Return the schema; wrote_to_disk + needs_device + blocked must reflect reality.`

const deviceVerifyPrompt = (c, em) => `Verify ONE on-device test on emulator ${em.udid} (build 3252). Run it 3 TIMES to
surface flakiness:
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} RUN_DESTRUCTIVE=1 ${PYRUN} ${c.file}::${c.test_name} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=short
Use ONLY this device. verdict green only if all 3 pass (a skip-with-reason counts as passing); flaky if mixed; red for a
real failure; distinguish infra (session crash / device drop) from a true failure in failure_reason. Capture ~20 log lines.
Return the schema (id=${c.id}).`

const apiVerifyPrompt = (c) => `Verify ONE pure DEV-API test (no emulator needed). Run it TWICE for determinism:
  ${PYRUN} ${c.file}::${c.test_name} -p no:cacheprovider -o addopts="" -q --tb=short
verdict green if both pass (skip-with-reason counts as passing), red on a real failure. Return the schema (id=${c.id}).`

const refinePrompt = (c) => `You are the Reliability Refinement Engineer. Harden ${c.file}::${c.test_name} (case ${c.id})
WITHOUT changing what it validates. ${RESOURCES}
Most recent verdict: ${JSON.stringify(c.verdict || 'n/a')}. Hunt for: blind sleeps that should be polls, presence where a
value/state oracle is feasible, brittle/absolute-index XPaths, unhandled modals/onboarding, swallowed taps (re-tap the
clickable container), and shared-account order/state coupling. Edit on disk if you find real issues (revised=true), else
revised=false. Return the schema (id=${c.id}).`

// ---- 2-emulator pool --------------------------------------------------------
async function poolVerify(items, phaseName, promptFn) {
  const todo = items.filter(Boolean)
  if (!EMU.length || !todo.length) return []
  const q = [...todo].sort((a, b) => rank(a) - rank(b))
  let k = 0
  const next = () => (k < q.length ? q[k++] : null)
  const out = []
  await parallel(EMU.map((em) => async () => {
    let c
    while ((c = next())) {
      const v = await agent(promptFn(c, em), { label: `${phaseName}:${c.id}@${em.udid}`, phase: phaseName, schema: VERDICT })
      if (v) { out.push(v); const t = todo.find((x) => x.id === v.id); if (t) { t.verdict = v; t.dirty = false } }
    }
  }))
  return out
}

// ---- PHASE 0 — Provision ----------------------------------------------------
phase('Provision')
const manifest = await agent(provisionPrompt, { label: 'provision:fixtures', phase: 'Provision' })
log('Provisioning complete; implementing 28 cases.')

// ---- PHASE 1 — Implement (parallel, write-only) -----------------------------
phase('Implement')
const built = (await parallel(CASES.map((c) => () =>
  agent(implPrompt({ ...c, file: fileFor(c) }, manifest), { label: `impl:${c.id}`, phase: 'Implement', schema: IMPL })
    .then((r) => r && ({ ...c, file: r.file || fileFor(c), test_name: r.test_name, needs_device: r.needs_device, blocked: r.blocked, impl: r, dirty: true }))
))).filter(Boolean)
const onDisk = built.filter((c) => c.impl && c.impl.wrote_to_disk)
log(`Implemented ${onDisk.length}/${CASES.length} on disk (${built.filter((c) => c.blocked).length} shipped skip-with-reason).`)

// ---- PHASE 2 — Verify (split API off-pool vs device on the 2-pool) ----------
phase('Verify')
const verifiable = onDisk.filter((c) => c.test_name && !c.blocked)
const apiCases = verifiable.filter((c) => !c.needs_device)
const deviceCases = verifiable.filter((c) => c.needs_device)
log(`Verify: ${apiCases.length} API (off-pool) + ${deviceCases.length} device (2-emulator pool, 3x).`)
const apiVerify = parallel(apiCases.map((c) => () =>
  agent(apiVerifyPrompt(c), { label: `verify-api:${c.id}`, phase: 'Verify', schema: VERDICT })
    .then((v) => { if (v) { c.verdict = v; c.dirty = false } return v })))
const devVerify = poolVerify(deviceCases, 'Verify', deviceVerifyPrompt)
await Promise.all([apiVerify, devVerify])

// ---- PHASE 3 — Refine (no device) -------------------------------------------
phase('Refine')
await parallel(verifiable.map((c) => () =>
  agent(refinePrompt(c), { label: `refine:${c.id}`, phase: 'Refine', schema: REFINE })
    .then((r) => { c.refine = r; if (r && r.revised) c.dirty = true; return r })))

// ---- PHASE 4 — Re-verify changed device tests -------------------------------
phase('Re-verify')
const dirtyDevice = deviceCases.filter((c) => c.dirty)
log(`Re-verifying ${dirtyDevice.length} device test(s) changed during refine.`)
await poolVerify(dirtyDevice, 'Re-verify', deviceVerifyPrompt)
// re-run any dirty API tests too (cheap, no device)
const dirtyApi = apiCases.filter((c) => c.dirty)
await parallel(dirtyApi.map((c) => () =>
  agent(apiVerifyPrompt(c), { label: `reverify-api:${c.id}`, phase: 'Re-verify', schema: VERDICT })
    .then((v) => { if (v) c.verdict = v; return v })))

// ---- PHASE 5 — Report -------------------------------------------------------
phase('Report')
const rows = built.map((c) => ({
  id: c.id, priority: c.priority, node: c.test_name ? `${c.file}::${c.test_name}` : c.file,
  needs_device: c.needs_device, blocked: c.blocked || false,
  verdict: (c.verdict && c.verdict.verdict) || (c.blocked ? 'skip-with-reason' : 'not-run'),
  reliability: c.refine && c.refine.reliability_score,
}))
const report = await agent(
  `You are the QA lead. Compile a human-gate report for the backlog build. Per case: id, priority, node, device/API,
verdict (green/flaky/red/skip-with-reason), reliability. Then: GREEN/AMBER/RED roll-up, which cases are safe to land now,
which need attention (flaky/red/blocked + why), and which shipped as honest skip-with-reason (spike-gated/non-seedable).
DATA:\n${JSON.stringify(rows, null, 1)}`,
  { label: 'lead:report', phase: 'Report' })

return {
  branch,
  counts: {
    cases: CASES.length, on_disk: onDisk.length,
    green: rows.filter((r) => r.verdict === 'green').length,
    skip: rows.filter((r) => r.verdict === 'skip-with-reason').length,
    flaky: rows.filter((r) => r.verdict === 'flaky').length,
    red: rows.filter((r) => r.verdict === 'red').length,
  },
  tests: rows,
  report,
}
