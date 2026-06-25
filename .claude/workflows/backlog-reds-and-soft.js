export const meta = {
  name: 'backlog-reds-and-soft',
  description: 'Investigate the 2 red backlog tests (jar-six-cap suspected product defect, jar-name-icon persistence red) and harden the 2 low-reliability greens (withdraw-over-balance weak oracle, recurring-create device flake) on the 2 stable emulators (build 3252), grounded in the app source + backend.',
  phases: [{ title: 'Work', detail: '2-emulator pool: investigate/fix each item, re-verify on-device' }, { title: 'Report', detail: 'verdicts for the human gate' }],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const ANDROID = '/Users/joshua/Android-AU'
const BACKEND = '/Users/joshua/raiz-backend'
const PYRUN = 'venv/bin/python -m pytest'
const EMU = [
  { udid: 'emulator-5554', appium: 'http://127.0.0.1:4723', systemPort: 8201, mjpegPort: 7811 },
  { udid: 'emulator-5556', appium: 'http://127.0.0.1:4724', systemPort: 8202, mjpegPort: 7812 },
]
const SRC = `Ground in the real sources (read-only): app ${ANDROID} (Kotlin/Compose, build 3252; contentDescription/testTag/text/
id locators, raiz:// deep links), backend ${BACKEND} (app/models = data model + any caps/limits, config/routes.rb). conftest
recovers PIN lockout + serializes logins. Real-ACH fixtures (exact/stable). Be HONEST: a confirmed product defect → keep a
red/xfail-with-bug reproducer; a wrong test premise → skip-with-reason or correct it; never fake green. zsh: quote grep globs.`

const ITEMS = [
  { id: 'jar-six-cap-enforced', node: 'tests/test_jar_six_cap_enforced.py',
    brief: `RED — the build reported "a 7th jar was created where the 6-jar cap should reject; the six were not left
unchanged." FIRST CONFIRM THE PREMISE: is a 6-jar cap actually a PRODUCT RULE on build 3252? Search the app source
(${ANDROID}: jar create flow / limits) AND the backend (${BACKEND}/app/models for a jar/goal count cap or validation). If
NO 6-jar cap exists in the product, the test's premise is WRONG → convert to skip-with-reason (or delete) — it is NOT a
defect. If a cap DOES exist and the app let a 7th through, that's a REAL defect → keep a red/xfail-with-bug reproducer with
precise evidence (where the cap is defined vs what the app did). Either way, leave the file in a non-falsely-red state and
report which it is.` },
  { id: 'jar-name-icon-persist', node: 'tests/test_jar_name_icon_persist.py',
    brief: `RED, device — "created jar name does not read back on the list card." Disambiguate: re-run isolated 3x on your
emulator; dump the Jars list after create. Is the name genuinely absent (real persistence/render miss → keep a documented
red/xfail + flag to app team) OR is it a list-scrape race / wrong name-scoped locator (→ fix the read: wait for the list to
settle, scope the card by name, re-tap swallowed taps)? Confirm the jar IS created (backend) to separate create-failure
from read-failure. Resolve to a true verdict, not a flaky red.` },
  { id: 'withdraw-over-balance-rejected', node: 'tests/test_withdraw_over_balance_rejected.py',
    brief: `GREEN but weak (reliability ~low): the oracle is "over-balance rejected OR invariant held" — the OR makes it
pass trivially. TIGHTEN to a deterministic state assertion: seed a known small EXACT balance, attempt a withdrawal >
available, and assert the SPECIFIC outcome on 3252 — EITHER an over-available error is shown AND no settled DebitInvestment
is created AND balance+available are unchanged, OR (if the app doesn't gate at the UI) characterize that explicitly and
assert the backend invariant (no settled debit > available). Keep the within-balance success leg. Remove the trivial OR.
RUN_DESTRUCTIVE=1. Spike on-device whether the gate is UI or backend; assert what's real.` },
  { id: 'recurring-create-roundtrip', node: 'tests/test_recurring_create_roundtrip.py',
    brief: `GREEN but a device one-off (low reliability): needs determinism. Harden — poll/wait for the recurring amount +
frequency to render after Save and after re-opening (don't read a snapshot); re-tap swallowed taps on the clickable
container; settle the screen before reading. Keep the oracle (amount==set, frequency==set round-trips; next-date SHAPE only
if it renders). Re-run 3x to confirm it's now stable.` },
]

const VERDICT = { type: 'object', additionalProperties: false, required: ['id', 'verdict', 'summary'],
  properties: { id: { type: 'string' },
    verdict: { type: 'string', description: 'green | flaky | red | real-defect | skip-with-reason | not-viable' },
    is_product_defect: { type: 'boolean' }, runs: { type: 'integer' }, changed_files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' }, followup: { type: 'string' } } }

const prompt = (it, em) => `You are a senior test-automation engineer. Investigate/fix ONE backlog item on YOUR device
${em.udid} (build 3252). Run with:
  ANDROID_UDID=${em.udid} APPIUM_HOST=${em.appium} ANDROID_SYSTEM_PORT=${em.systemPort} ANDROID_MJPEG_PORT=${em.mjpegPort} RUN_DESTRUCTIVE=1 ${PYRUN} ${it.node} -p no:cacheprovider -o addopts="" -q --timeout=300 --tb=short
${SRC}

ITEM ${it.id}: ${it.brief}

Edit only this item's file (+ its page object if needed). Re-run to confirm your resolution. Return the schema — set
is_product_defect=true only with source/backend evidence; verdict honestly.`

phase('Work')
let n = 0
const claim = () => (n < ITEMS.length ? ITEMS[n++] : null)
const results = []
await parallel(EMU.map((em) => async () => {
  let it
  while ((it = claim())) {
    const r = await agent(prompt(it, em), { label: `investigate:${it.id}@${em.udid}`, phase: 'Work', schema: VERDICT })
    if (r) results.push(r)
  }
}))

phase('Report')
const report = await agent(
  `Summarize this investigation for the human gate: per item verdict, whether it's a confirmed PRODUCT DEFECT (with
evidence) vs a test-premise/flake fix, what changed, and what to file with the app team. DATA:\n${JSON.stringify(results, null, 1)}`,
  { label: 'lead:report', phase: 'Report' })

return { results, report }
