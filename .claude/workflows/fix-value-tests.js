export const meta = {
  name: 'fix-value-tests',
  description: 'Investigate, fix, and on-device-verify the 4 remaining value tests (TC-05 migrate-to-genuser, TC-06 jars-nav, TC-08 verify, TC-10 net-worth lazy-load) across a 3-emulator pool',
  phases: [{ title: 'Fix', detail: 'one agent per test: investigate on its emulator, fix, re-verify' }],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const PYRUN = 'venv/bin/python -m pytest'
const EMU = [
  { udid: 'emulator-5554', appium: 'http://127.0.0.1:4723', systemPort: 8201, mjpegPort: 7811 },
  { udid: 'emulator-5556', appium: 'http://127.0.0.1:4724', systemPort: 8202, mjpegPort: 7812 },
  { udid: 'emulator-5558', appium: 'http://127.0.0.1:4725', systemPort: 8204, mjpegPort: 7814 },
]

const SUITE = `Repo ${REPO}. Appium/UiAutomator2 + pytest, Raiz Android app
(com.acornsau.android.development). Conventions: use the Page Objects in pages/; tap a button by its CLICKABLE CONTAINER
not the bare TextView (//*[@clickable='true'][.//*[@text='LABEL']], click last); assert real VALUES/state not presence;
DEV API only (api-dev.raizinvest.com.au), never prod. Generated users have NO price history (performance/net-invested
decomposition may be empty on them). Reuse strategy: test-case-specific fixture generated ONCE + stored in the registry
(utils/genuser_fixtures); the rich-buffer pattern for money; FRESH user per run for create-jars/kids. The genuser_e2e
pattern (own driver + login + OnboardingPage.complete) is in tests/test_main_value_on_device.py and
tests/test_withdrawal_e2e.py — mirror it. Shared-account tests now have a concurrency-safe login gate in conftest.`

const TASKS = [
  { id: 'TC-08', file: 'tests/test_withdraw_available_value.py',
    node: 'tests/test_withdraw_available_value.py::test_withdraw_available_matches_backend_and_completes',
    env: 'RUN_DESTRUCTIVE=1', kind: 'verify-only',
    brief: `VERIFY ONLY (do not change the oracle). This test was just fixed to drop an unmeasurable backend balance-delta
(the ~$320k rich buffer reprices by hundreds of dollars between reads, swamping a $5 withdrawal) and keep two reliable
oracles: Available == backend current_balance, and the on-device 'Withdrawal Confirmed' success screen. RUN it and
confirm green. If it FAILS, only fix on-device flakiness (tap/timing) — do NOT re-introduce a balance-delta assertion.` },
  { id: 'TC-06', file: 'tests/test_jars_count_after_create.py',
    node: 'tests/test_jars_count_after_create.py::test_home_jars_count_increments_after_create',
    env: 'RUN_DESTRUCTIVE=1', kind: 'fix',
    brief: `It now generates a FRESH user + own driver (correct — keep that), but '_open_jars' via the JARS deep link
fails ("Could not open the Jars screen") for a freshly generated user. Find a RELIABLE way to reach the Jars create
screen for a genuser: try the Home Jars card tap, the nav drawer -> Jars, or another route — DUMP the screen on-device to
see what's actually available, don't guess. Fix _open_jars to navigate via that route. The oracle is unchanged: fresh
user owns 0 jars -> create exactly one -> Home Jars card count == before+1 and not empty. Verify the full flow on your
emulator. If the genuser genuinely cannot open Jars at all, report that clearly with evidence.` },
  { id: 'TC-10', file: 'tests/test_my_finance_networth_recon.py',
    node: 'tests/test_my_finance_networth_recon.py::test_net_worth_equals_investments_plus_super',
    env: '', kind: 'fix',
    brief: `Fails with "'My net worth' card did not finish loading its header total and component figures" — a LAZY-LOAD /
empty-state problem on the shared TEST_EMAIL account, NOT bad math. Investigate My Finance on-device: does the net-worth
card populate its header + component values? (1) Make the wait robustly POLL until the header total AND the component
figures are present (longer, poll-based, not a snapshot). (2) If the shared account legitimately has no net-worth data,
SKIP on empty-state instead of failing. (3) If values DO load, assert net_worth == sum of ALL shown component rows (net
worth may include cash/other, not just investments+super) within +/-$0.02, or net_worth >= investments+super if extra
components exist. Super is NOT seedable, so this stays on the shared account (login gate handles concurrency). Verify.` },
  { id: 'TC-05', file: 'tests/test_main_portfolio_reconciliation.py',
    node: 'tests/test_main_portfolio_reconciliation.py::test_net_invested_plus_returns_equals_value',
    env: '', kind: 'fix',
    brief: `Currently uses the shared-account 'main_portfolio' conftest fixture and FLAKED (passed clean once,
"comparison failed" once). GOAL: migrate to a DEDICATED GENERATED user for determinism (generate-once + store in the
fixture registry, reuse thereafter), own driver + login + onboard (mirror tests/test_main_value_on_device.py). BUT FIRST
verify on-device whether a generated user's Main Portfolio even RENDERS the net-invested / market-return / dividends
decomposition — generated users have no price history, so these rows may be absent/zero (same gap that killed the
performance test). If the decomposition IS present on a genuser, migrate and assert the reconciliation identity
(net-invested + returns == value, +/-band) after DUMPING the rows to confirm which identity holds. If it is NOT present
on a genuser, do NOT force it — keep TC-05 on the shared account (it passes there) and report that genuser migration
isn't viable for this oracle, with evidence.` },
]

const FIXRES = { type: 'object', additionalProperties: false,
  required: ['id', 'verdict', 'summary'],
  properties: {
    id: { type: 'string' },
    verdict: { type: 'string', description: 'pass | fail | skip | not-viable' },
    runs: { type: 'integer', description: 'on-device verification runs performed' },
    changed_files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string', description: 'what you found + did, concrete' },
    followup: { type: 'string', description: 'anything still needed / a flag for the human' },
  } }

const fixPrompt = (t, em) => `You are a senior test-automation engineer. Fix and on-device-verify ONE test.
${SUITE}

TASK ${t.id} (${t.kind}) — file ${t.file}
Device assigned to you (use ONLY this one): ${em.udid}, Appium ${em.appium}, systemPort ${em.systemPort}, mjpegPort ${em.mjpegPort}.
Run the test with EXACTLY this env so you don't collide with the other workers:
  ${t.env} ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} ${PYRUN} ${t.node} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=short

${t.brief}

Read the current test + its recent failure, investigate ON-DEVICE (dump screens / run it) before editing, make the
minimal correct fix to the test and/or its page object (own files only — do not touch other tests' files), then RE-RUN
to confirm. A genuser_e2e/standalone test builds its own driver from get_android_options() (reads your env vars). Return
the schema honestly — verdict 'not-viable'/'skip' with evidence is a valid, useful outcome; do not fake a pass.`

phase('Fix')
let n = 0
const claim = () => (n < TASKS.length ? TASKS[n++] : null)
const lanes = await parallel(EMU.map((em) => async () => {
  const out = []
  let t
  while ((t = claim())) {
    const r = await agent(fixPrompt(t, em), { label: `fix:${t.id}@${em.udid}`, phase: 'Fix', schema: FIXRES })
    out.push(r)
  }
  return out
}))

const results = lanes.flat().filter(Boolean)
return {
  fixed: results.filter((r) => r.verdict === 'pass').map((r) => r.id),
  results,
}
