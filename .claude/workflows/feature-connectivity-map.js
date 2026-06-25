export const meta = {
  name: 'feature-connectivity-map',
  description: 'Map every Raiz product feature across BOTH the Android app source and the backend API, in parallel (one agent per feature), then aggregate into a cross-feature connectivity graph + report that downstream test-case agents consume to understand feature functionality and how features wire together.',
  phases: [
    { title: 'Map', detail: 'one agent per feature maps it across the app (UI/flows/locators) + backend (models/endpoints) and records its connections' },
    { title: 'Aggregate', detail: 'orchestrator reconciles all maps into a connectivity graph + writes the report for test agents' },
  ],
}

const ANDROID = '/Users/joshua/Android-AU'           // app source (Kotlin, Compose-heavy)
const BACKEND = '/Users/joshua/raiz-backend'         // Raiz API (Ruby on Rails)
const OUT = '/Users/joshua/Documents/Android test automation appium/raiz-appium-tests/docs/feature-connectivity-map.md'

const SRC = `Two read-only source repos are cloned locally:
- APP: ${ANDROID} — modular Kotlin, Compose-heavy. Modules under features/ (financev2, futurev2, roundups,
  recurringv2, performancev2, pricing, movement, milestone, steps, navmenu, notificationsv2, ...) and top-level
  raizFeature* (raizFeaturePortfolio, raizFeatureSignUp, raizFeatureSmsf, raizFeatureNotifications, raizFeatureStatements,
  raizFeatureAchievements, ...) + core/ (model, ui, ui-compose, ui-legacy). Appium hooks: contentDescription (primary,
  ~411 files), testTag (sparse, ~19), text, and legacy android:id (~414). Deep links look like raiz://...
- BACKEND: ${BACKEND} — Rails. app/models (data model + ActiveRecord associations = the real feature wiring),
  app/controllers + config/routes.rb (the /v1 and /internal API surface the app + the test-data-gen use).
Quote evidence as file:symbol. In zsh, QUOTE grep globs: grep -r --include="*.kt" / --include="*.rb". Read-only — never edit these repos.`

const FEATURES = [
  { key: 'core-investing', name: 'Core investing — portfolios, allocation, orders, rebalancing',
    app: 'raizFeaturePortfolio, core/model; portfolio styles, allocation %, buy/sell', be: 'allocation*, *_order*, security/fund, portfolio, valuation models' },
  { key: 'roundups', name: 'Round-Ups (virtual spare change)',
    app: 'features/roundups', be: 'roundup*, spending/monitored account, multiplier/threshold' },
  { key: 'recurring', name: 'Recurring investments',
    app: 'features/recurringv2', be: 'recurring*/scheduled investment, frequency' },
  { key: 'deposits-withdrawals', name: 'Deposits & withdrawals (funding, ACH, cutoffs)',
    app: 'features/movement; deposit/withdraw flows, funding source', be: 'credit_investment, debit_investment, billing_funding_source, bank, calendar_holiday/weekday (cutoffs)' },
  { key: 'portfolio-performance', name: 'Portfolio value, performance & transactions',
    app: 'features/performancev2, raizFeatureStatements; value tiles, perf graph, history', be: 'valuation, performance, order/transaction, statement models' },
  { key: 'raiz-kids', name: 'Raiz Kids (dependent sub-accounts)',
    app: 'kids screens (search "kid"/"Raiz Kids")', be: 'kid/dependent account, parental permission, transfer-at-18 models' },
  { key: 'raiz-jars', name: 'Raiz Jars (goal-based savings sub-accounts)',
    app: 'features/futurev2 or search "jar"/"goal"', be: 'jar/goal sub-account, target, recurring-into-jar models' },
  { key: 'raiz-rewards', name: 'Raiz Rewards (partner cashback)',
    app: 'search "reward"/"earn"/"offer"', be: 'reward/offer/cashback/brand, pending-vs-invested models' },
  { key: 'raiz-super', name: 'Raiz Super (superannuation / SMSF)',
    app: 'raizFeatureSmsf', be: 'super/smsf, contribution, rollover, insurance models' },
  { key: 'money-myfinance', name: 'Raiz Money / My Finance (aggregation, insights, net worth)',
    app: 'features/financev2', be: 'aggregation_account*, aggregation_subaccount, spending/category, net-worth models' },
  { key: 'plans-fees', name: 'Plans, fees & subscription tiers',
    app: 'features/pricing', be: 'pricing_plan/plan, bill, fee, subscription models (tiers: lite/regular/plus/sapphire)' },
  { key: 'auth-onboarding', name: 'Auth, security & onboarding (sign-up, KYC, PIN)',
    app: 'raizFeatureSignUp; login/PIN/biometric', be: 'user, authentication_token, kyc/identity, acceptance_document models' },
  { key: 'notifications', name: 'Notifications & messaging',
    app: 'features/notificationsv2', be: 'notification/message/push models' },
  { key: 'milestones-gamification', name: 'Milestones, steps & achievements',
    app: 'features/milestone, features/steps, raizFeatureAchievements', be: 'accomplishment*, milestone models' },
]

const MAP = { type: 'object', additionalProperties: false,
  required: ['feature', 'purpose', 'connects_to'],
  properties: {
    feature: { type: 'string' },
    purpose: { type: 'string', description: "what this feature does, in a customer's terms" },
    app_surface: { type: 'array', items: { type: 'string' }, description: 'key screens/composables/flows + the module(s) they live in' },
    backend_surface: { type: 'array', items: { type: 'string' }, description: 'key models (+ notable associations) and key endpoints/routes (file:symbol)' },
    deep_links: { type: 'array', items: { type: 'string' } },
    appium_hooks: { type: 'array', items: { type: 'string' }, description: 'real contentDescription / testTag / text / id strings a test would target' },
    data_entities: { type: 'array', items: { type: 'string' }, description: 'the core data objects/values a test could seed or assert (with backend field names)' },
    connects_to: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['feature', 'relationship'],
      properties: {
        feature: { type: 'string', description: 'the OTHER feature key it connects to' },
        relationship: { type: 'string', description: 'e.g. "round-ups fund the main portfolio", "rewards invest into Invest or Super", "kids/jars are sub-accounts under the parent user"' },
        direction: { type: 'string', description: 'feeds | depends-on | shares-data | navigates-to | mutually' },
        evidence: { type: 'string', description: 'file:symbol in app or backend that shows the link' } } } },
    test_implications: { type: 'string', description: 'what a test author must know about this feature + its connections (state to seed, cross-feature effects, gotchas)' },
  } }

const mapPrompt = (f) => `You are mapping ONE Raiz product feature across both the app and the backend, for a connectivity
report that test-case authors will rely on. Focus feature: **${f.name}** (key: ${f.key}).
${SRC}

Where to look (confirm in-source, don't assume): APP — ${f.app}. BACKEND — ${f.be}.

Produce a precise map of THIS feature:
- purpose (customer-level), app_surface (screens/flows + module), backend_surface (key models + associations + key
  endpoints/routes, as file:symbol), deep_links, appium_hooks (REAL contentDescription/testTag/text/id strings you find),
  data_entities (the values a test could seed/assert, with backend field names).
- connects_to: the most important part — how this feature WIRES to OTHER features. Look at backend model associations
  (belongs_to/has_many), shared accounts/users (e.g. sub-accounts under a parent user), money flows (what funds/feeds
  what), and app navigation/deep-links. For each connection give the other feature key, the relationship in plain words,
  a direction, and file:symbol evidence. Use the feature keys from this set: ${FEATURES.map((x) => x.key).join(', ')}.
- test_implications: what a test author must know (state to seed via the gen API, cross-feature side effects, gotchas).
Be concrete and evidence-backed. Return the schema.`

const aggPrompt = (maps) => `You are the orchestrator. You have per-feature maps of the Raiz app (built from the real
app + backend source). Aggregate them into ONE authoritative **feature-connectivity report** that downstream test-case
agents will read to understand feature functionality and how features connect.

Do this:
1. Build the CONNECTIVITY GRAPH: reconcile/dedupe edges across all maps (if A says it feeds B and B says it depends on A,
   that's ONE edge — keep the clearest wording + both evidence pointers). Note any asymmetric/contradictory claims.
2. Note COMPLETENESS gaps: connections one side asserts that the other didn't, and any feature pair that almost certainly
   connects but neither mapped (flag for follow-up).
3. WRITE the report to ${OUT} (create the docs/ dir if needed) as well-structured markdown with these sections:
   (a) one-paragraph overview of the app's product model;
   (b) an ASCII/mermaid-style connectivity diagram or adjacency list (feature -> feature: relationship);
   (c) per-feature sections: purpose, key screens/flows, backend models+endpoints, deep links, REAL Appium hooks
       (contentDescription/testTag/text/id), seedable/assertable data entities, connections, and test_implications;
   (d) a "for test authors" cheat-sheet: for each feature, the highest-value VALUE/STATE oracles its connections enable
       (e.g. money-conservation across Main<->Jar<->Kid, reward routes to the right product, round-ups fund main).
Keep it information-dense and accurate — every claim should be traceable to source.

PER-FEATURE MAPS:\n${JSON.stringify(maps, null, 1)}

Return a concise summary: the edge count, the most connected features, any completeness gaps, and confirm the file was written.`

// ---- run --------------------------------------------------------------------
log(`Mapping ${FEATURES.length} Raiz features across app + backend (parallel), then aggregating.`)

phase('Map')
const maps = (await parallel(FEATURES.map((f) => () =>
  agent(mapPrompt(f), { label: `map:${f.key}`, phase: 'Map', schema: MAP })))).filter(Boolean)
log(`Mapped ${maps.length}/${FEATURES.length} features; aggregating into the connectivity report.`)

phase('Aggregate')
const summary = await agent(aggPrompt(maps), { label: 'orchestrator:aggregate', phase: 'Aggregate' })

return {
  features: FEATURES.map((f) => f.key),
  mapped: maps.length,
  report_path: OUT,
  maps,
  summary,
}
