export const meta = {
  name: 'test-case-generation-fanout',
  description: '20 agents independently generate candidate test cases to ADD (grounded in the feature-connectivity map + the coverage audit + existing-suite coverage), then the candidates are deduped with a consensus count, adversarially cross-checked against the existing suite for realness/feasibility/novelty, and synthesized into one ranked backlog written to docs/proposed-test-cases.md.',
  phases: [
    { title: 'Generate', detail: '20 agents each produce a prioritized candidate test-case list from the same inputs' },
    { title: 'Dedupe', detail: 'merge all candidates into a canonical set with a consensus count (how many of the 20 surfaced each)' },
    { title: 'CrossCheck', detail: 'adversarial reviewers validate slices of the canonical set: real? feasible? already covered? sound oracle?' },
    { title: 'Synthesize', detail: 'rank + write the final backlog (consensus x cross-check confidence) to docs/proposed-test-cases.md' },
  ],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'
const CMAP = REPO + '/docs/feature-connectivity-map.md'
const AUDIT = '/private/tmp/claude-501/-Users-joshua-Documents-Android-test-automation-appium-raiz-appium-tests/9ab8acad-d14b-4867-98b6-04913d55fa16/scratchpad/research_slim.json'
const ANDROID = '/Users/joshua/Android-AU'
const OUT = REPO + '/docs/proposed-test-cases.md'
const GEN_COUNT = 20
const CHECK_SLICES = 8

const INPUTS = `Ground EVERY proposal in these (read-only):
- FEATURE-CONNECTIVITY MAP: ${CMAP} — feature functionality, the cross-feature edges, and the "for test authors"
  value/state-oracle cheat-sheet. The highest-value cases come from CONNECTIONS (e.g. money conservation across
  Main<->Jar<->Kid, round-ups fund main, reward routes to the right product).
- COVERAGE AUDIT: ${AUDIT} (JSON) — per-feature grade + missing[] (with oracles) + value_vs_presence + critique
  (cross_cutting weaknesses + missed_areas). This is the prior gap analysis.
- EXISTING SUITE: ${REPO}/tests + ${REPO}/pages — SCAN it so you do NOT propose cases already covered; prefer
  presence->value upgrades and genuinely missing flows. Existing value tests live in test_*value*, test_value_validation_api.
- REAL APP SOURCE (optional, for real flows/locators/feasibility): ${ANDROID} (Kotlin, Compose-heavy).
The app is build 3252. Test-data: real-ACH fixtures (exact/stable balances), gen API seeds users/balances/jars/kids/account-
states but NOT rewards-offers or funded-super (those need the shared account). Generated users have no price history.
DEFERRED (still in scope to LIST, but flag deferred='yes'): Rewards, Super product surface, Auth/Security/Onboarding —
the user will give additional context before those are built; include them in the backlog but mark them deferred.`

const GEN = { type: 'object', additionalProperties: false, required: ['cases'],
  properties: { cases: { type: 'array', items: { type: 'object', additionalProperties: false,
    required: ['feature', 'title', 'type', 'priority', 'oracle'],
    properties: {
      feature: { type: 'string' },
      title: { type: 'string' },
      type: { type: 'string', description: 'value | state-transition | reconciliation | negative/rejection | cross-feature-conservation | flow | reliability' },
      priority: { type: 'string', description: 'P0..P3' },
      oracle: { type: 'string', description: 'the concrete value/state that proves a pass' },
      data_mode: { type: 'string', description: 'reuse-fixture | dynamic | shared-account' },
      connection_basis: { type: 'string', description: 'which connectivity edge or audit gap this comes from' },
      deferred: { type: 'string', description: 'yes if rewards/super/auth (await user context), else no' },
    } } } } }

const DEDUP = { type: 'object', additionalProperties: false, required: ['cases'],
  properties: { cases: { type: 'array', items: { type: 'object', additionalProperties: false,
    required: ['key', 'feature', 'title', 'type', 'priority', 'oracle', 'consensus_count'],
    properties: {
      key: { type: 'string', description: 'short stable slug' },
      feature: { type: 'string' }, title: { type: 'string' }, type: { type: 'string' },
      priority: { type: 'string' }, oracle: { type: 'string' }, data_mode: { type: 'string' },
      deferred: { type: 'string' },
      consensus_count: { type: 'integer', description: 'how many of the 20 agents independently proposed this (1..20)' },
    } } } } }

const REVIEW = { type: 'object', additionalProperties: false, required: ['reviews'],
  properties: { reviews: { type: 'array', items: { type: 'object', additionalProperties: false,
    required: ['key', 'verdict', 'confidence'],
    properties: {
      key: { type: 'string' },
      verdict: { type: 'string', description: 'keep | cut | refine' },
      already_covered: { type: 'string', description: 'no, or the existing test node that already covers it' },
      feasible: { type: 'string', description: 'yes/no + how (seedable? device-reachable on 3252?)' },
      oracle_ok: { type: 'boolean', description: 'is the oracle a real value/state check that would catch a wrong number?' },
      confidence: { type: 'integer', description: '0-100 this is a real, valuable, novel, implementable case' },
      notes: { type: 'string' },
    } } } } }

const genPrompt = (i) => `You are Test-Case Generator #${i + 1} of ${GEN_COUNT}. Independently produce a PRIORITIZED list of
test cases that SHOULD BE ADDED to the Raiz Appium suite. Work from first principles using the inputs — do not coordinate
with other generators (your list will be cross-checked against theirs).
${INPUTS}

Produce 12-20 candidate cases. Bias HARD toward: real VALUE/STATE oracles over presence; cross-feature CONNECTIONS from the
map (the money-conservation and routing invariants are the highest-value, least-covered class); negative/rejection cases
(minimums, caps, over-balance, account-state blocks); and the audit's documented gaps. For each: feature, a precise title,
type, priority, a concrete oracle (the value/state that proves a pass), data_mode, the connection_basis (which map edge or
audit gap it derives from), and deferred (yes for rewards/super/auth). Do NOT propose cases the existing suite already
covers — scan tests/ first. Return the schema.`

const dedupPrompt = (lists) => `You are the de-duplication aggregator. ${GEN_COUNT} generators independently proposed test
cases (below). Merge them into ONE canonical, de-duplicated set. Two proposals are the SAME case if they assert the same
value/state on the same feature even if worded differently — merge them, keep the clearest title + strongest oracle, and
set consensus_count = how many generators surfaced it (a strong signal of importance). Assign each a short stable key.
Preserve deferred flags. Do not drop unique-but-valid cases (consensus_count 1 is fine). Return the schema.
CANDIDATE LISTS (one per generator):\n${JSON.stringify(lists, null, 1)}`

const checkPrompt = (slice, idx) => `You are adversarial Cross-Checker #${idx + 1}. Validate each candidate test case below
against reality — be skeptical, your job is to catch weak/duplicate/infeasible proposals before they reach the backlog.
${INPUTS}

For EACH case: (1) already_covered — search ${REPO}/tests; if an existing test already asserts this, say which node.
(2) feasible — can it be implemented on build 3252 with our tooling (gen-API seedable? device-reachable? not blocked like
the kids/jars on-device withdraw)? (3) oracle_ok — is the oracle a REAL value/state check that would fail on a wrong
number, or is it secretly presence? (4) verdict keep/cut/refine + confidence 0-100 + notes (for refine, say how).
You MAY do a quick read-only spot-check on emulator-5560 (build 3252) via 'adb -s emulator-5560 shell uiautomator dump'
ONLY if essential to judge feasibility — it's shared, so don't navigate/drive it, just read the current screen if needed.
CASES:\n${JSON.stringify(slice, null, 1)}\nReturn the schema (one review per case key).`

// ---- Generate (20 in parallel) ----------------------------------------------
phase('Generate')
const lists = (await parallel(Array.from({ length: GEN_COUNT }, (_, i) => () =>
  agent(genPrompt(i), { label: `gen#${i + 1}`, phase: 'Generate', schema: GEN }))))
  .filter(Boolean).map((r) => r.cases || [])
const totalCandidates = lists.reduce((n, l) => n + l.length, 0)
log(`Generated ${totalCandidates} raw candidates across ${lists.length}/${GEN_COUNT} generators.`)

// ---- Dedupe -----------------------------------------------------------------
phase('Dedupe')
const deduped = await agent(dedupPrompt(lists), { label: 'dedupe-aggregator', phase: 'Dedupe', schema: DEDUP })
const canon = (deduped && deduped.cases) || []
log(`De-duplicated to ${canon.length} canonical cases (consensus range ${Math.min(...canon.map((c) => c.consensus_count || 1))}-${Math.max(...canon.map((c) => c.consensus_count || 1))}).`)

// ---- CrossCheck (reviewers over slices) -------------------------------------
phase('CrossCheck')
const size = Math.ceil(canon.length / CHECK_SLICES) || 1
const slices = []
for (let i = 0; i < canon.length; i += size) slices.push(canon.slice(i, i + size))
const reviewsNested = (await parallel(slices.map((sl, idx) => () =>
  agent(checkPrompt(sl, idx), { label: `crosscheck#${idx + 1}`, phase: 'CrossCheck', schema: REVIEW }))))
  .filter(Boolean).map((r) => r.reviews || [])
const reviewByKey = {}
reviewsNested.flat().forEach((rv) => { reviewByKey[rv.key] = rv })
const merged = canon.map((c) => ({ ...c, review: reviewByKey[c.key] || null }))
const kept = merged.filter((c) => !c.review || c.review.verdict !== 'cut')
log(`Cross-check: ${merged.length - kept.length} cut, ${kept.length} kept/refined.`)

// ---- Synthesize (write the backlog) -----------------------------------------
phase('Synthesize')
const synthPrompt = `You are the QA lead. Write the final, ranked test-case backlog to ${OUT} (create docs/ if needed) as
clear markdown. Use the cross-checked cases below. RANK by (a) cross-check verdict (drop 'cut'), (b) confidence, (c)
consensus_count, (d) priority. Structure: (1) a 2-3 line summary (how many proposed, kept, cut, top themes); (2) a table of
the KEPT cases — key | feature | priority | type | title | oracle | data_mode | consensus | confidence | deferred; group
non-deferred first, then a clearly-marked DEFERRED (rewards/super/auth — await user context) section; (3) a short
"highest-value first" shortlist of the top ~12 to build next (the cross-feature conservation / value oracles). Also note
any case the cross-checkers flagged 'refine' with the refinement needed. Keep it dense and implementation-ready (this feeds
the extend-appium-tests skill). After writing, return a concise summary (counts + the top 12 keys + confirm file written).
CROSS-CHECKED CASES:\n${JSON.stringify(merged, null, 1)}`
const summary = await agent(synthPrompt, { label: 'synthesize-backlog', phase: 'Synthesize' })

return {
  generators: lists.length,
  raw_candidates: totalCandidates,
  canonical: canon.length,
  kept: kept.length,
  cut: merged.length - kept.length,
  backlog_path: OUT,
  summary,
}
