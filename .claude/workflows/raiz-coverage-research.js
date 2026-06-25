export const meta = {
  name: 'raiz-coverage-research',
  description: 'Research Raiz features from a customer POV, map them against the Appium test suite, identify missing/thin coverage + improvements, and synthesize structured findings for an artifact',
  phases: [
    { title: 'Research', detail: 'per-feature customer-POV research of Raiz (web)' },
    { title: 'Map', detail: 'map what the existing Appium suite covers per feature (read code)' },
    { title: 'Gaps', detail: 'cross-reference research vs coverage -> missing & improvable, prioritized' },
    { title: 'Critique', detail: 'completeness critic: what whole areas did we miss' },
    { title: 'Synthesize', detail: 'compile an executive summary + prioritized roadmap' },
  ],
}

const REPO = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests'

// Raiz Invest (Australia) consumer feature areas. key = stable id; hint = where to look.
const FEATURES = [
  { key: 'core-investing', name: 'Core investing — round-ups, recurring, lump sum, portfolios',
    hint: 'Round-Ups (auto + manual), recurring (daily/weekly/monthly), lump sum, portfolio styles (Conservative→Aggressive, Emerald/socially-responsible, Sapphire with Bitcoin, Plus Portfolios, custom allocation), rebalancing.' },
  { key: 'raiz-kids', name: 'Raiz Kids', hint: 'Kids investment sub-accounts: create, fund, gift, parental controls/permissions, transfer to child at 18, multiple kids.' },
  { key: 'raiz-jars', name: 'Raiz Jars', hint: 'Goal-based savings jars: create, name/icon, target amount, recurring into a jar, withdraw from jar, close jar.' },
  { key: 'raiz-rewards', name: 'Raiz Rewards', hint: 'Cashback rewards from partner brands: browse Earn, link cards, pending vs invested, Track tab, in-store vs online, brand detail webview.' },
  { key: 'raiz-super', name: 'Raiz Super (superannuation)', hint: 'Super fund: balance, contributions, consolidation/rollover, investment options, insurance, fees.' },
  { key: 'money-myfinance', name: 'Raiz Money / My Finance', hint: 'Account aggregation, net worth, spending insights, linked bank accounts, the Money/MyFinance dashboard.' },
  { key: 'plans-fees', name: 'Plans, fees & subscription tiers', hint: 'Subscription tiers (e.g. Essentials/Plus/etc.), monthly fees, fee thresholds, what each plan unlocks.' },
  { key: 'deposits-withdrawals', name: 'Deposits & withdrawals', hint: 'One-off deposit, withdrawal to bank, processing times, minimums, withdrawal confirmation flow, ACH/PayID/funding source.' },
  { key: 'auth-security-onboarding', name: 'Auth, security & onboarding', hint: 'Sign-up/KYC onboarding, login, OTP/2FA, PIN, biometric, password reset, advisor (PDS) agreement, account states (active/suspended/closed).' },
  { key: 'portfolio-performance', name: 'Portfolio value, performance & transactions', hint: 'Home value tiles, Main Portfolio detail (net invested, market return, dividends), performance graph/ranges, transaction history, statements.' },
]

const RESEARCH = { type: 'object', additionalProperties: false,
  required: ['feature', 'summary', 'customer_flows', 'pain_points', 'qa_should_validate'],
  properties: {
    feature: { type: 'string' },
    summary: { type: 'string', description: "what this feature is, in a customer's words" },
    customer_flows: { type: 'array', items: { type: 'string' }, description: 'concrete things a real customer does, start to finish' },
    pain_points: { type: 'array', items: { type: 'string' }, description: 'common confusions, edge cases, complaints customers hit' },
    qa_should_validate: { type: 'array', items: { type: 'string' }, description: 'the value/state assertions a QA suite SHOULD make for this feature' },
    sources: { type: 'array', items: { type: 'string' } },
  } }
const COVERAGE = { type: 'object', additionalProperties: false,
  required: ['feature', 'tested_flows', 'value_vs_presence', 'files', 'thin_or_missing'],
  properties: {
    feature: { type: 'string' },
    tested_flows: { type: 'array', items: { type: 'string' } },
    value_vs_presence: { type: 'string', description: 'do the tests assert real values/state, or mostly element presence? evidence.' },
    files: { type: 'array', items: { type: 'string' } },
    markers: { type: 'array', items: { type: 'string' } },
    thin_or_missing: { type: 'array', items: { type: 'string' } },
  } }
const GAPS = { type: 'object', additionalProperties: false,
  required: ['feature', 'coverage_grade', 'missing', 'improvements'],
  properties: {
    feature: { type: 'string' },
    coverage_grade: { type: 'string', description: 'A–F: how well the suite covers this feature for a customer' },
    missing: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['title', 'priority', 'why', 'oracle'],
      properties: { title: { type: 'string' }, priority: { type: 'string', description: 'P0–P3' },
        why: { type: 'string', description: 'customer/business impact' },
        oracle: { type: 'string', description: 'the concrete value/state that would prove a pass' },
        seedable: { type: 'string', description: 'can the DEV gen API seed this state? yes/no/unknown + note' } } } },
    improvements: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['title', 'what'], properties: { title: { type: 'string' }, what: { type: 'string' } } } },
  } }
const CRITIQUE = { type: 'object', additionalProperties: false,
  required: ['missed_areas', 'cross_cutting', 'top_priorities'],
  properties: {
    missed_areas: { type: 'array', items: { type: 'string' }, description: 'whole features/flows neither research nor mapping covered' },
    cross_cutting: { type: 'array', items: { type: 'string' }, description: 'suite-wide weaknesses (e.g. presence-over-value, flake, no negative cases)' },
    top_priorities: { type: 'array', items: { type: 'string' }, description: 'the highest-impact gaps to close first, across all features' },
  } }

const researchPrompt = (f) => `You are a product analyst researching **Raiz Invest (Australia)** — the consumer micro-investing app — from a CUSTOMER's point of view. Focus area: ${f.name}.
${f.hint}

Use web search/fetch (Raiz's official site raiz.com.au, their Help Centre/support docs, app-store listings, recent reviews, reputable AU fintech write-ups). Understand how a real customer EXPERIENCES this feature: what they set up, what they see, what trips them up. Be concrete and current; note your sources. Do NOT speculate about internals — describe the customer-facing product. Return the schema. qa_should_validate must list the VALUE/state checks (not presence) a good test suite would make for this feature.`

const mapPrompt = (f) => `You are a test-automation auditor. Map what the EXISTING Appium/pytest suite at ${REPO} covers for: ${f.name}.
${f.hint}

Read the relevant tests/ and pages/ (use Grep to find files for this feature, then read the pertinent tests + page objects). Also skim conftest.py and pytest.ini markers. Determine: which customer flows are tested, whether assertions check REAL VALUES/state or just element presence (give evidence — quote an assert or two), the files/markers involved, and what's thin or missing. Be precise and grounded in the actual code — do not invent tests that aren't there. Return the schema.`

const gapPrompt = (f, research, coverage) => `You are a senior QA strategist. For Raiz feature **${f.name}**, cross-reference the customer-POV research against the suite's actual coverage and produce a prioritized gap + improvement list.

CUSTOMER RESEARCH:\n${JSON.stringify(research || {}, null, 1)}

CURRENT SUITE COVERAGE:\n${JSON.stringify(coverage || {}, null, 1)}

Identify what a customer relies on that is UNTESTED or only presence-tested, and what existing tests could be IMPROVED (value oracles, negative cases, reliability). For each missing item give a checkable value/state oracle and judge whether the DEV test-data-gen API could seed the needed state (the gen API can seed users/balances/jars/kids/ACH credits/account-states, but has NO recipe for rewards offers or super — those need the shared account). Grade the feature's coverage A–F. Be honest and specific; prioritize by customer/business impact. Return the schema.`

const critiquePrompt = (gaps) => `You are a completeness critic for a Raiz test-coverage analysis. Here are the per-feature gap findings:
${JSON.stringify(gaps.filter(Boolean).map((g) => ({ feature: g.feature, grade: g.coverage_grade, missing: (g.missing || []).map((m) => m.title) })), null, 1)}

What WHOLE areas or flows did this analysis likely miss entirely (think: error/negative paths, accessibility, localisation/currency, notifications, deep links, session/logout, multi-account interactions, edge balances, regulatory/PDS, performance under load)? What suite-WIDE weaknesses recur? What are the top cross-feature priorities to fix first? Return the schema.`

const synthPrompt = (gaps, critique) => `You are the QA lead. Write a crisp executive synthesis of this Raiz coverage analysis for an artifact the team will read.
PER-FEATURE GAPS:\n${JSON.stringify(gaps.filter(Boolean), null, 1)}
CRITIQUE:\n${JSON.stringify(critique || {}, null, 1)}

Produce: (1) a 3-4 sentence executive summary of the suite's coverage health for a customer; (2) the single biggest systemic weakness; (3) a prioritized "next 10 tests to build" list (feature, title, priority, one-line oracle) drawn from the highest-impact gaps; (4) 3-5 reliability/architecture recommendations. Be concrete and prioritized.`

// ---- run --------------------------------------------------------------------
log(`Researching ${FEATURES.length} Raiz feature areas (customer POV) + mapping suite coverage`)

phase('Research')
const research = await parallel(FEATURES.map((f) => () =>
  agent(researchPrompt(f), { label: `research:${f.key}`, phase: 'Research', schema: RESEARCH })))

phase('Map')
const coverage = await parallel(FEATURES.map((f) => () =>
  agent(mapPrompt(f), { label: `map:${f.key}`, phase: 'Map', schema: COVERAGE })))

phase('Gaps')
const gaps = await parallel(FEATURES.map((f, i) => () =>
  agent(gapPrompt(f, research[i], coverage[i]), { label: `gaps:${f.key}`, phase: 'Gaps', schema: GAPS })))

phase('Critique')
const critique = await agent(critiquePrompt(gaps), { label: 'completeness-critic', phase: 'Critique', schema: CRITIQUE })

phase('Synthesize')
const synthesis = await agent(synthPrompt(gaps, critique), { label: 'qa-lead-synthesis', phase: 'Synthesize' })

return {
  features: FEATURES.map((f) => f.key),
  research: research.filter(Boolean),
  coverage: coverage.filter(Boolean),
  gaps: gaps.filter(Boolean),
  critique,
  synthesis,
}
