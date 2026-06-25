export const meta = {
  name: 'p1-reverify-investigate',
  description: 'Re-verify the code-solid P1 units on the 2 STABLE emulators (5554/5556 only — avoid the 2GB 3rd-session crash) and investigate the 3 real findings (U-ALLOC deterministic fail, U-WITHDRAW sub-account withdraw entry, U-KIDS hollow assertions) on the CURRENT build (3252 / v2.40.1d), grounding each in the real app source + the feature-connectivity map.',
  phases: [
    { title: 'Work', detail: '2-emulator pool drains a queue: re-verify code-solid units (3x) + investigate/fix the 3 findings' },
    { title: 'Report', detail: 'lead compiles verdicts for human approval' },
  ],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const ANDROID = '/Users/joshua/Android-AU'
const CMAP = REPO + '/docs/feature-connectivity-map.md'
const PYRUN = 'venv/bin/python -m pytest'
// ONLY the 2 stable emulators (user directive — the 3rd session crashes on 2GB AVDs).
const EMU = [
  { udid: 'emulator-5554', appium: 'http://127.0.0.1:4723', systemPort: 8201, mjpegPort: 7811 },
  { udid: 'emulator-5556', appium: 'http://127.0.0.1:4724', systemPort: 8202, mjpegPort: 7812 },
]

const SRC = `Ground your work in the REAL sources (read-only): app at ${ANDROID} (Kotlin, Compose-heavy; contentDescription/
testTag/text/id locators; deep links raiz://...), and the feature-connectivity map at ${CMAP} (how features wire + the
value/state oracle cheat-sheet). conftest recovers from PIN lockout and serializes shared-account logins. Fixtures are now
real-ACH (exact, stable): presence_funded $5,000; withdrawal buffers $50,000; kids/jars siblings $4,000/$1,200 distinct.
Generated users have NO price history (no performance/net-invested decomposition). Quote grep globs in zsh (--include="*.kt").`

const ITEMS = [
  { id: 'U-JARS', kind: 'reverify', nodes: 'tests/test_jars.py',
    brief: 'Re-verify the un-skipped jars list/value tests (routed onto the jars_siblings_distinct parent fixture). First login as the parent will run onboarding once.' },
  { id: 'U-MOREE2E', kind: 'reverify', nodes: 'tests/test_more_e2e_flows.py -k "net_worth or round_ups or super"',
    brief: 'Re-verify the My-Finance/round-ups/super-recon P1 changes. P1-08 (round-ups) and P1-15 (funded super) are expected to SKIP-with-reason (non-seedable) — a skip counts as green here.' },
  { id: 'U-PORTFOLIO', kind: 'reverify', nodes: 'tests/test_portfolio.py',
    brief: 'Re-verify after deleting the range-button tautologies and dropping the stale jar-tab xfails (now data-adaptive). Skips-if-absent are fine; a wrong value must fail.' },
  { id: 'U-INVEST', kind: 'reverify', nodes: 'tests/test_investments.py',
    brief: 'Re-verify after deleting the weak lump-sum presence tests and dropping the stale kids-recurring xfail.' },
  { id: 'U-ALLOC', kind: 'investigate', nodes: 'tests/test_allocation_jars_kids_e2e.py -k Plus',
    brief: `DIAGNOSE: test_running_total_stays_100_during_reallocation FAILS deterministically (5/5). Two hypotheses: (a) a
REAL RAIZ-10251 defect — the Plus custom-portfolio running total drifts off 100% during reallocation; (b) the Plus builder
is never reachable because the test data only seeds Regular-plan users (plan_identifier='regular'). RESOLVE IT: check the
app source (${ANDROID}, raizFeaturePortfolio customization) for whether the Plus builder is plan-gated, and try seeding a
plan_identifier='plus' user via the gen API. If Plus is reachable and the total truly drifts -> it's a real defect: keep a
failing/xfail-with-bug test + document precisely. If Plus is NOT reachable on the seedable plans -> mark skip-with-reason
(needs a Plus-seeded account) rather than a deterministic red. Decide with evidence; do not leave a silent red.` },
  { id: 'U-WITHDRAW', kind: 'investigate', nodes: 'tests/test_withdrawal_e2e.py -k "kids or jars"',
    brief: `CONFIRM + RESOLVE on the CURRENT build (now 3252 / v2.40.1d — freshly installed; this is a NEW build vs the
3226 where the kids/jars on-device withdrawal was reported INFRA-GATED with NO Withdraw entry + a jars 'Oops!' login gate;
re-evaluate from scratch — the entry may have changed). Verify against the app source (${ANDROID}: search the redesigned
home + drilled-in sub-account/account screens for a withdraw entry/deep-link for sub-accounts) AND on your emulator (log in
as kids_withdrawal_buffer / jars_withdrawal_buffer, navigate, dump screens). If an entry EXISTS -> wire the test to it and
assert the real backend balance DELTA (the ACH buffers are STABLE $50k now, so the delta is exact — use a tight tolerance,
not the leftover $250 band). If there is genuinely no sub-account Withdraw entry on 3252 -> convert those two tests to
skip-with-reason citing the build + that API-level jar-withdrawal value is already covered by test_value_validation_api
(U-API), and note it for the app team.` },
  { id: 'U-KIDS', kind: 'investigate', nodes: 'tests/test_kids.py',
    brief: `STRENGTHEN + VERIFY: the skeptic judged the kids parent-session tests HOLLOW (assertions wouldn't catch a wrong
value). Strengthen them to real value/state oracles: each rendered kid-card value == that kid's backend current_balance
(kids_siblings_distinct: $4,000 / $1,200) within a tight band, names CONTAIN the exact seeded first names, and the two
siblings are distinct + not swapped. Also investigate the prior multi-session UiAutomator2 crash: ensure the test uses ONE
driver (the genuser parent login), not a second concurrent session, so it runs within a single 2GB emulator. Then verify
on your emulator.` },
]

const VERIFY = { type: 'object', additionalProperties: false,
  required: ['id', 'verdict', 'summary'],
  properties: {
    id: { type: 'string' },
    verdict: { type: 'string', description: 'green | flaky | red | skip-with-reason | real-defect | not-viable' },
    runs: { type: 'integer' }, passes: { type: 'integer' },
    changed_files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    followup: { type: 'string' },
  } }

const prompt = (it, em) => `You are a senior test-automation engineer on the 2-stable-emulator re-verify/investigation pass.
${SRC}

ITEM ${it.id} (${it.kind}) on YOUR device ${em.udid} (Appium ${em.appium}, ANDROID_SYSTEM_PORT=${em.systemPort},
ANDROID_MJPEG_PORT=${em.mjpegPort}). Run with:
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} RUN_DESTRUCTIVE=1 ${PYRUN} ${it.nodes} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=short

${it.kind === 'reverify'
  ? `RE-VERIFY ONLY (do not change the oracle unless you find a real on-device flake to harden): ${it.brief} Run it 3 times; verdict green only if all 3 pass (skip-with-reason counts as passing), flaky if mixed, red if it fails for a real (non-infra) reason. If it fails due to emulator infra (session crash / device dropped), say so and set verdict accordingly — do not fake green.`
  : `INVESTIGATE + FIX (own file only): ${it.brief} Make the minimal correct change, then re-run to confirm. Return the honest verdict (real-defect / skip-with-reason / green / not-viable) with evidence — a documented real-defect or skip-with-reason is a valid outcome; never fake a pass.`}

Use ONLY your assigned device. Return the schema.`

phase('Work')
let n = 0
const claim = () => (n < ITEMS.length ? ITEMS[n++] : null)
const results = []
await parallel(EMU.map((em) => async () => {
  let it
  while ((it = claim())) {
    const r = await agent(prompt(it, em), { label: `${it.kind}:${it.id}@${em.udid}`, phase: 'Work', schema: VERIFY })
    if (r) results.push(r)
  }
}))

phase('Report')
const report = await agent(
  `You are the test lead. Summarize this 2-emulator re-verify/investigation pass for the approver: per item verdict +
what changed + any real defect or skip-with-reason. Then give a GREEN/AMBER/RED roll-up, which items are now safe to land,
and which need human attention. DATA:\n${JSON.stringify(results, null, 1)}`,
  { label: 'lead:report', phase: 'Report' })

return {
  green: results.filter((r) => r.verdict === 'green').map((r) => r.id),
  results,
  report,
}
