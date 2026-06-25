export const meta = {
  name: 'remediate-p1-ultracode',
  description: 'ULTRACODE P1 remediation of the existing in-scope suite: fix each unit (presence→value, un-skip onto seeded fixtures, drop stale xfails, delete redundant, harden), then adversarially verify (5× flake runs on the pool + a skeptic assertion-quality audit), run a completeness critic, re-verify reworked units, and report for human approval.',
  phases: [
    { title: 'Provision', detail: 'quartermaster seeds + onboards the fixtures the fixes need (parent+jars, parent+kids, Plus user)' },
    { title: 'Fix', detail: 'one engineer per file-unit applies its P1 fixes (own files only)' },
    { title: 'Verify', detail: 'run each unit\'s affected tests 5× on the pool to surface flakiness' },
    { title: 'Skeptic', detail: 'adversarial audit per unit: does the fix assert a value that would catch a WRONG number, deterministically?' },
    { title: 'Critic', detail: 'completeness critic over all units + the audit: superficial or missed presence→value conversions' },
    { title: 'Re-verify', detail: 'rerun units the skeptic/critic flagged' },
    { title: 'Report', detail: 'lead compiles verdicts + reliability for human approval' },
  ],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const PYRUN = 'venv/bin/python -m pytest'
const REPEATS = 5  // ultracode flake-detection runs per device unit
const EMU = [
  { udid: 'emulator-5554', appium: 'http://127.0.0.1:4723', systemPort: 8201, mjpegPort: 7811 },
  { udid: 'emulator-5556', appium: 'http://127.0.0.1:4724', systemPort: 8202, mjpegPort: 7812 },
  { udid: 'emulator-5558', appium: 'http://127.0.0.1:4725', systemPort: 8204, mjpegPort: 7814 },
]

const SUITE = `Repo ${REPO}. Appium/UiAutomator2 + pytest, Raiz Android app (com.acornsau.android.development).
Conventions: use the Page Objects in pages/; tap a button by its CLICKABLE CONTAINER not the bare TextView
(//*[@clickable='true'][.//*[@text='LABEL']], click last); assert real VALUES/state, never mere presence; DEV API only
(api-dev.raizinvest.com.au), never prod. conftest now recovers from PIN lockout + serializes shared-account logins.
Generated users have NO price history (performance/net-invested decomposition is $0 on them — keep performance tests on
the SHARED account). Reuse strategy: test-case-specific fixtures generated once + stored; rich-buffer for money; FRESH
user per run for create-jars/kids. The genuser_e2e pattern (own driver + login + OnboardingPage.complete) is in
tests/test_main_value_on_device.py and tests/test_kids_value_on_device.py — mirror it. OUT OF SCOPE entirely: Rewards,
Super product surface (only the My-Finance super *reconciliation* arithmetic is in scope), Auth/PIN/Onboarding.`

// P1 work grouped BY FILE so no two agents edit the same file concurrently.
const UNITS = [
  { id: 'U-SETTINGS', items: ['P1-01', 'P1-02'], device: true,
    files: 'pages/settings_page.py, tests/test_navigation_coverage.py, tests/test_settings_profile_value.py',
    nodes: 'tests/test_settings_profile_value.py tests/test_navigation_coverage.py -k "fee or plan or profile or tier"',
    brief: `Make the fee/plan surfaces assert VALUES. (P1-01) Fees are checked only by an OR'd keyword locator in
test_navigation_coverage.py (lines ~181-183,405-407) — any keyword present passes, so any dollar figure stays green. Add
SettingsPage.current_monthly_fee() (read the fee value co-located with the plan/fee label) and assert the EXACT fee for
the current ('regular') tier ('$5.50'); keep only a thin nav/back presence check. (P1-02) Harden
SettingsPage.current_plan_tier() to REQUIRE the 'Current plan' marker association (return None rather than guessing any
tier-name TextView on a multi-tier screen); reconcile KNOWN_PLAN_TIERS ('Staple'/'Essential' are unverified guesses)
against what the seeded account renders. Use the presence_funded ('regular') fixture; per-tier lite/plus parametrization
is P2 — here just make the current-tier oracle real and non-guessing.` },
  { id: 'U-KIDS', items: ['P1-04', 'P1-05'], device: true,
    files: 'tests/test_kids.py (+ pages/kids_page.py if a getter is missing)',
    nodes: 'tests/test_kids.py',
    brief: `Stop the kids tests from SKIPPING and make them assert. (P1-04) Every value/list test in test_kids.py is gated
by _require_list() which skips on the shared account (raiz://raiz_kids opens the consent/welcome gate). Route them under
the kids_siblings_distinct PARENT fixture (log in as the parent, as test_kids_value_on_device.py does) so is_list_screen()
is true and the balance/tab/manage oracles actually execute. (P1-05) test_kid_names_displayed asserts only non-empty and
get_kid_names() matches any 'yr' TextView — assert the rendered names CONTAIN the exact seeded first names
('KidSibAlpha'/'KidSibBravo') and that the kid-row count == the number of seeded kids.` },
  { id: 'U-JARS', items: ['P1-03'], device: true,
    files: 'tests/test_jars.py',
    nodes: 'tests/test_jars.py',
    brief: `test_jars.py value/list tests skip via _require_list() on the shared account (raiz://jars deep-links to the
create screen). Route them onto a seeded parent+jars fixture (mirror the jars_value / two-named-jars pattern) via a parent
genuser login so is_list_screen() is true and the balance/tab/manage oracles run; use get_jar_balance_by_name(). A skip is
not coverage.` },
  { id: 'U-PORTFOLIO', items: ['P1-09', 'P1-11'], device: true,
    files: 'tests/test_portfolio.py',
    nodes: 'tests/test_portfolio.py',
    brief: `(P1-09) Delete the three TestPerformanceScreen.test_select_1d/1m/all_range tests — each taps a range then
asserts that range button is visible (a tautology RAIZ-10306 sails past); they're superseded by
TestPerformanceRangeChangesValue (change-value varies across ranges). Keep performance coverage on the SHARED account only
(genuser has no price history). (P1-11) Drop the stale @pytest.mark.xfail('requires active jars') on
test_jar_tab_*/test_portfolio_tab — the shared account now HAS jars — and make them data-adaptive (skip if no jar tab,
assert real content if present).` },
  { id: 'U-INVEST', items: ['P1-10', 'P1-12'], device: true,
    files: 'tests/test_investments.py',
    nodes: 'tests/test_investments.py',
    brief: `(P1-10) Delete TestLumpSumScreen.test_preset_10_sets_amount and test_keypad_enters_digits — they only assert
the display is "not $0.00"; redundant with TestLumpSumValueCorrectness (exact parse_money==expected). (P1-12) Remove the
stale @pytest.mark.xfail on TestRecurringInvestments.test_kids_section_visible (the account now has kids); assert the KIDS
recurring section is present, or skip-if-absent — don't mask a now-runnable assertion as expected-fail.` },
  { id: 'U-MOREE2E', items: ['P1-13', 'P1-08', 'P1-15'], device: true,
    files: 'tests/test_more_e2e_flows.py',
    nodes: 'tests/test_more_e2e_flows.py',
    brief: `(P1-13) test_net_worth_section_loads is presence-only and subsumed by test_my_finance_networth_recon — delete
it, or downgrade to a single headline well-formedness assertion. (P1-08) test_round_ups_filter_tabs_change_content is
VACUOUS: 'if not has_data: assert visible(...); return' — the shared account has no round-up activity so the
differentiation branch never runs and it can't fail. Round-up accrual is INFRA-GATED (no gen-API seed recipe). If you
cannot seed round-up accrual, convert it to an explicit xfail/skip with a precise 'no round-up data — needs accrual seed'
reason — do NOT leave a passing vacuous test. (P1-15) test_super_component_reconciles_with_super_surface only asserts
super==$0 (unfunded). Funded super is INFRA-GATED (non-seedable). Keep the $0 branch; add a non-zero branch that
reconciles My-Finance 'Total in Superannuation' against the funded super dashboard, guarded/skipped with a clear reason
until a funded-super account exists. Be honest — skip-with-reason beats a vacuous pass.` },
  { id: 'U-WITHDRAW', items: ['P1-06'], device: true,
    files: 'tests/test_withdrawal_e2e.py',
    nodes: 'tests/test_withdrawal_e2e.py -k "kids or jars"',
    brief: `_run_withdrawal asserts only the 'Withdrawal Confirmed' screen. For the kids_withdrawal_buffer /
jars_withdrawal_buffer SUB-accounts (NOT the market-noisy six-figure main), add a backend current_balance before/after
DELTA using the settle-poll pattern from test_value_validation_api / test_withdraw_available_value: read the sub-account
balance before, withdraw, poll-after, assert it dropped by ~the withdrawn amount within a band. Keep the success screen as
the flow oracle and ADD the delta as the value oracle.` },
  { id: 'U-ALLOC', items: ['P1-07'], device: true,
    files: 'tests/test_allocation_jars_kids_e2e.py',
    nodes: 'tests/test_allocation_jars_kids_e2e.py -k Plus',
    brief: `TestCustomPortfolioPlusE2E only reads the static base-100% start (BASE_100). Add an EDITING flow on a
Plus/seeded user: reallocate a holding and assert the running total stays ==100% at each step, that a save with
total!=100% is blocked, and that Bitcoin>5% / Raiz-Property>~30% are clamped/rejected before save (RAIZ-10251). This is
the interactive drift/cap defect a read-only sum check can't catch. If the Plus builder isn't reachable on the seeded
user, report that with evidence rather than forcing it.` },
  { id: 'U-API', items: ['P1-14'], device: false,
    files: 'tests/test_value_validation_api.py',
    nodes: 'tests/test_value_validation_api.py::test_jar_balance_reduced_by_withdrawal',
    brief: `test_jar_balance_reduced_by_withdrawal pytest.xfails whenever the backend gates the jar withdrawal (422), so it
can NEVER prove the reduction — effectively no coverage. Make the xfail PRECISE (strict where the gate is deterministic),
add a comment tracking the backend gate as a defect and pointing to the on-device jar-withdrawal delta (P1-06) as the
interim guard. No device — API only.` },
]

const FIX = { type: 'object', additionalProperties: false,
  required: ['unit', 'changed_files', 'summary', 'items_done'],
  properties: {
    unit: { type: 'string' }, changed_files: { type: 'array', items: { type: 'string' } },
    items_done: { type: 'array', items: { type: 'string' } },
    items_blocked: { type: 'array', items: { type: 'string' }, description: 'items that were infra-gated/not-viable, with why' },
    summary: { type: 'string' },
  } }
const VERIFY = { type: 'object', additionalProperties: false,
  required: ['unit', 'runs', 'all_passed', 'flaky'],
  properties: {
    unit: { type: 'string' }, runs: { type: 'integer' }, passes: { type: 'integer' },
    all_passed: { type: 'boolean' }, flaky: { type: 'boolean' }, failure_reason: { type: 'string' }, log_tail: { type: 'string' } } }
const SKEPTIC = { type: 'object', additionalProperties: false,
  required: ['unit', 'asserts_real_value', 'would_catch_wrong_number', 'verdict'],
  properties: {
    unit: { type: 'string' },
    asserts_real_value: { type: 'boolean', description: 'does the changed test reconcile a value/state to an authoritative oracle (vs presence/shape)?' },
    would_catch_wrong_number: { type: 'boolean', description: 'if the app rendered a WRONG dollar figure, would this test fail?' },
    superficial_or_skipping: { type: 'boolean', description: 'did the "fix" just rename presence, or still skip/return vacuously?' },
    verdict: { type: 'string', description: 'solid | superficial | rework-needed' }, issues: { type: 'array', items: { type: 'string' } } } }

const fixPrompt = (u, em) => `You are a senior Test Automation Engineer doing a P1 remediation unit. Fix ALL items in this
unit by editing ONLY your owned files, then do ONE confirming run.
${SUITE}

UNIT ${u.id} — items ${u.items.join(', ')}
Owned files (edit only these): ${u.files}
${u.brief}

${u.device ? `Confirm with ONE run on YOUR device ${em.udid}:
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} RUN_DESTRUCTIVE=1 ${PYRUN} ${u.nodes} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=short`
  : `Confirm with: ${PYRUN} ${u.nodes} -p no:cacheprovider -o addopts="" -q`}

Read the current tests + the audit reasoning first. Make the MINIMAL correct change that converts presence→value /
un-skips onto a seeded fixture / drops a stale xfail / deletes a redundant test / hardens reliability, exactly as briefed.
Where an item is genuinely infra-gated (no seed recipe, non-seedable funded super), do the honest thing — skip-with-clear-
reason or precise xfail — and list it in items_blocked; never fake a pass. Return the schema.`

const verifyPrompt = (u, em) => `Verify the remediated unit ${u.id} on device ${em.udid} by running its tests ${REPEATS} TIMES
to surface flakiness:
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} RUN_DESTRUCTIVE=1 ${PYRUN} ${u.nodes} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=line
Run it ${REPEATS} separate times (do not use -n). all_passed=true only if EVERY run was green (skips are fine and count as
passing for flake purposes); flaky=true if results varied across runs. Capture the last ~20 lines of a representative run.
Use only this device. Return the schema.`

const skepticPrompt = (u) => `You are an ADVERSARIAL test reviewer. Your job is to PROVE the remediation of unit ${u.id} is
hollow if you can. Read the CURRENT state of: ${u.files}.
${SUITE}

The remediation was supposed to: ${u.brief}

Scrutinize every changed/added assertion. Answer honestly:
- asserts_real_value: does it reconcile a VALUE/state to an authoritative oracle (rate×spend, backend current_balance,
  exact fee, allocation sum), or is it still presence/shape ("a $ parses", "is_visible")?
- would_catch_wrong_number: if the app rendered a WRONG dollar figure / wrong state, would the test FAIL? Trace it.
- superficial_or_skipping: did the fix just rename a presence check, or does it still skip()/return vacuously on the
  shared account (the original sin)?
Default to skepticism: if you cannot convince yourself the test would catch a real defect, verdict='rework-needed' or
'superficial'. List concrete issues. Return the schema.`

const criticPrompt = (rows) => `You are the completeness critic for this P1 remediation. Across all units, what did we
likely MISS or do SUPERFICIALLY? Look for: presence→value conversions that should have been made but weren't, tests still
skipping/vacuous, fixes that renamed presence without adding a real oracle, reliability hazards left in place, and any
in-scope audit P1 item not addressed. Output the highest-leverage gaps to close next.
DATA:\n${JSON.stringify(rows, null, 1)}`

const reportPrompt = (rows) => `You are the Test Automation LEAD. Compile a concise human-review report of the P1
remediation for the approver. Per unit: items done / blocked, verify verdict (passed/flaky + runs), and the skeptic's
assertion-quality verdict. Then: (1) GREEN/AMBER/RED batch status, (2) which units are safe to land, (3) which need
attention and why (flaky, superficial, infra-gated), (4) the critic's top missed/superficial items as follow-ups.
DATA:\n${JSON.stringify(rows, null, 1)}`

// ---- shared 3-emulator pool ------------------------------------------------
async function pool(items, phaseName, makeAgent) {
  const todo = items.filter(Boolean)
  if (!todo.length) return []
  if (!EMU.length) return []
  let k = 0
  const next = () => (k < todo.length ? todo[k++] : null)
  const out = []
  await parallel(EMU.map((em) => async () => {
    let it
    while ((it = next())) {
      const r = await makeAgent(it, em, phaseName)
      out.push(r)
    }
  }))
  return out
}

// ---- PHASE 0 — Provision ----------------------------------------------------
phase('Provision')
const deviceUnits = UNITS.filter((u) => u.device)
const provisionBrief = `You are the TEST-DATA PROVISIONER. The P1 remediation needs these reusable, ONBOARDED fixtures to
exist in utils/genuser_fixtures.py + the registry so the un-skipped tests have real data. Ensure each exists (seed via
get_or_create_fixture_user / add a builder if missing) AND is driven through first-login onboarding once on YOUR emulator
(OnboardingPage.complete + mark_onboarded), since onboarding is server-side and then applies on every device:
- a parent with TWO named jars of distinct balances (for the jars list/value tests),
- a parent with TWO kids of distinct balances (kids_siblings_distinct already exists — onboard it),
- the presence_funded 'regular' user (settings/fees),
- a Plus-portfolio-capable user if one is needed for the allocation editing test (report if Plus isn't seedable).
${SUITE}
Return a short summary of which fixtures are ready (key + onboarded) and any that could not be prepared.`
const provision = await pool(
  [{ id: 'provision', brief: provisionBrief }],
  'Provision',
  (it, em) => agent(`${it.brief}\n\nUse emulator ${em.udid} (APPIUM_HOST=${em.appium}, ANDROID_SYSTEM_PORT=${em.systemPort}, ANDROID_MJPEG_PORT=${em.mjpegPort}).`,
    { label: 'provision:fixtures', phase: 'Provision' }))
log(`Provision: ${provision.length ? 'fixture prep attempted' : 'skipped'}`)

// ---- PHASE 1 — Fix (pool, grouped by file) ---------------------------------
phase('Fix')
const fixed = await pool(UNITS, 'Fix', (u, em) =>
  agent(fixPrompt(u, em), { label: `fix:${u.id}`, phase: 'Fix', schema: FIX }).then((r) => ({ unit: u, fix: r })))
log(`Fixed ${fixed.length}/${UNITS.length} units.`)

// ---- PHASE 2 — Verify 5x on the pool (device units only) -------------------
phase('Verify')
const verifyResults = await pool(deviceUnits, 'Verify', (u, em) =>
  agent(verifyPrompt(u, em), { label: `verify:${u.id}`, phase: 'Verify', schema: VERIFY }))
const verifyByUnit = {}
verifyResults.filter(Boolean).forEach((v) => { verifyByUnit[v.unit] = v })

// ---- PHASE 3 — Adversarial skeptic (no device, parallel) -------------------
phase('Skeptic')
const skepticResults = (await parallel(UNITS.map((u) => () =>
  agent(skepticPrompt(u), { label: `skeptic:${u.id}`, phase: 'Skeptic', schema: SKEPTIC })))).filter(Boolean)
const skepticByUnit = {}
skepticResults.forEach((s) => { skepticByUnit[s.unit] = s })

// ---- PHASE 4 — Completeness critic -----------------------------------------
phase('Critic')
const rowsForCritic = UNITS.map((u) => ({
  unit: u.id, items: u.items,
  fix: (fixed.find((f) => f.unit.id === u.id) || {}).fix,
  verify: verifyByUnit[u.id] || (u.device ? 'not-run' : 'n/a (no device)'),
  skeptic: skepticByUnit[u.id],
}))
const critic = await agent(criticPrompt(rowsForCritic), { label: 'completeness-critic', phase: 'Critic' })

// ---- PHASE 5 — Re-verify units the skeptic flagged superficial -------------
phase('Re-verify')
const needsRework = deviceUnits.filter((u) => {
  const s = skepticByUnit[u.id]
  return s && (s.verdict === 'rework-needed' || s.superficial_or_skipping || !s.would_catch_wrong_number)
})
log(`Skeptic flagged ${needsRework.length} unit(s) as superficial/rework — noting for the human (no auto-rework loop).`)

// ---- PHASE 6 — Lead report --------------------------------------------------
phase('Report')
const report = await agent(reportPrompt(rowsForCritic), { label: 'lead:report', phase: 'Report' })

return {
  units: UNITS.map((u) => u.id),
  fixed: fixed.map((f) => ({ unit: f.unit.id, items_done: f.fix && f.fix.items_done, items_blocked: f.fix && f.fix.items_blocked, changed: f.fix && f.fix.changed_files })),
  verify: verifyByUnit,
  skeptic: skepticByUnit,
  flagged_superficial: needsRework.map((u) => u.id),
  critic,
  report,
}
