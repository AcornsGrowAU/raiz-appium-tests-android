"""
Fixture-user registry — the reuse strategy in code (see memory:
genuser-test-data-reuse-strategy).

A small pool of long-lived, pre-onboarded generated users keyed by PURPOSE. Tests
ask `get_or_create_fixture_user(key)`; a fresh user is generated + stored ONCE (ever),
and reused on every subsequent run as long as it still logs in. Fresh generation +
onboarding is reserved for cases that genuinely need it (request those directly via
utils.genuser_api).

  presence_funded        -> onboarded user with a real (immediate) Aggressive balance,
                            for screen-presence / value-read tests.
  rich_withdrawal_buffer -> ~$1,000,000 (100 x $10k ACH deposits). Withdrawal tests
                            draw a tiny amount ($5) each, so one user serves thousands
                            of runs without re-seeding.
"""
import json
import os
import time

from utils.genuser_api import (
    SEEDED_PWD, can_login, current_balance, gen_create,
    funded_user, ach_credit, ach_credits, kid_user, jar_user, tiered_user,
)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REGISTRY = os.path.join(_REPO, "fixtures", "genuser_registry.json")

# Distinctive (non-round) seeded ACH credit amount for the transaction-history
# ledger test. Deterministic by recipe, so it is the oracle value the on-device
# test parses for in the history list. Chosen to be unlikely to collide with the
# with_balance priced-holding Buy rows. Keep in sync with the
# `history_seeded_deposit` fixture builder below.
HISTORY_SEEDED_DEPOSIT = 137.42

# Deterministic jar card labels for the reusable `jars_siblings_distinct` fixture.
# The app renders the jar row label from the jar's name, so on-device tests scope a
# card to one jar by matching the name (JarsPage.get_jar_balance_by_name). Keep in
# sync with the `jars_siblings_distinct` builder below.
JAR_A_NAME = "QA Sib Jar Alpha"
JAR_B_NAME = "QA Sib Jar Bravo"

# Exact ACH-settled balance targets (built from real credit_investment / payment_method
# ACH, max $10k per txn — see utils.genuser_api.ach_credits). These settle to
# current_balance EXACTLY and stay stable (no market drift), which is why we use them
# instead of the with_balance trait. The withdrawal buffer at $50k absorbs ~10,000
# $5-draws before re-seeding. Sibling amounts are deliberately distinct.
PRESENCE_BALANCE = 5000
WITHDRAWAL_BUFFER = 50000
KID_A_BALANCE, KID_B_BALANCE = 4000, 1200
JAR_A_BALANCE, JAR_B_BALANCE = 4000, 1200

# --- SMALL EXACT ACH balances for the conservation / reconciliation / min-rejection
# cases. Deliberately small + non-round (NOT the repricing six-figure buffer) so the
# delta==0 / sum-conservation oracles read exact, stable current_balance values with
# no market drift. Distinct per sub-account so a sibling's delta is unambiguous.
CONSERVE_MAIN_BALANCE = 300.00   # Main seed for routing-isolation / transfer-conserve
CONSERVE_JAR_BALANCE = 80.00     # a funded jar that must NOT move
CONSERVE_KID_BALANCE = 40.00     # a funded kid that must NOT move
KID_FUND_A_BALANCE = 60.00       # kid-fund-no-cross-post: Kid-A starting balance
KID_FUND_B_BALANCE = 20.00       # kid-fund-no-cross-post: Kid-B (sibling, delta==0)
BELOW_MIN_JAR_BALANCE = 25.00    # funded jar for sub-$5 deposit-rejection (delta==0)
MYFIN_UNLINKED_BALANCE = 50.00   # funded-but-unlinked user (My Finance empty-state precondition)

# --- Jar GOAL/target for round-trip + progress-ring math (jar.saving_amount).
# $5,000 catches the $5,000->$500 truncation bug. Progress-ring fixture seeds a
# balance that is a clean fraction of the target (150/200 == 75%).
JAR_TARGET_GOAL = 5000           # jar-target-roundtrip: set 5000, read back 5000.00
JAR_TARGET_NAME = "Europe trip"
RING_GOAL = 200                  # jar-goal-progress-ring target
RING_BALANCE = 150               # 150/200 -> exactly 75%
RING_JAR_NAME = "QA Ring Jar"

# --- Per-style portfolio users for allocation-weights (verified portfolio_name
# accepted by the gen API: Aggressive / Conservative / Moderate). Moderate prices to
# $0 in some views, so allocation/label tests must assert the LABEL + published mix,
# never a balance on Moderate.
STYLE_AGGRESSIVE = "Aggressive"
STYLE_CONSERVATIVE = "Conservative"
STYLE_MODERATE = "Moderate"

# --- Per-entity portfolio independence: kid-A Aggressive vs kid-B Moderate;
# jar Conservative vs Main Aggressive. Assert the LABEL (not balance) — Moderate $0.
KID_PF_A_NAME = "QA PF Kid Alpha"
KID_PF_B_NAME = "QA PF Kid Bravo"
JAR_PF_NAME = "QA PF Jar Conservative"

# key -> (builder(email) -> {ref: entity, ...}, human description)
# ALL balances are built from REAL ACH credit_investments (payment_method ACH) so they
# settle to current_balance EXACTLY and stay stable (no market drift) — the accurate,
# production-faithful money-in flow. (Previously these used the `with_balance` trait,
# which fabricated market-priced holdings that drifted; that's been retired here.)
FIXTURES = {
    "presence_funded": (
        lambda email: {"user_1": funded_user(email, "PresFunded"),
                       **ach_credits("@user_1", PRESENCE_BALANCE)},
        f"onboarded user with an exact ${PRESENCE_BALANCE:,} ACH-settled balance (presence/value reads)",
    ),
    "rich_withdrawal_buffer": (
        # Real ACH credits ($10k max/txn -> 5 x $10k = $50k). Each withdrawal test draws
        # ~$5, so ~10,000 runs before re-seeding; balance is exact + stable (no drift).
        lambda email: {"user_1": funded_user(email, "RichBuffer"),
                       **ach_credits("@user_1", WITHDRAWAL_BUFFER)},
        f"${WITHDRAWAL_BUFFER:,} ACH-settled buffer for withdrawal tests (draw $5 each; exact + stable)",
    ),
    # Sub-account buffers. A kid/jar is its OWN user (own login + own current_balance)
    # under a parent — on-device we log in AS the sub-account. user_1 is the sub-account
    # (its id/email is stored); its balance is real ACH credits referencing @user_1.
    "kids_withdrawal_buffer": (
        lambda email: {
            "parent": funded_user("kp." + email, "KidBufParent"),
            "user_1": kid_user(email, "KidBuffer", "@parent"),
            **ach_credits("@user_1", WITHDRAWAL_BUFFER, prefix="kidbuf"),
        },
        f"${WITHDRAWAL_BUFFER:,} ACH-settled kid sub-account buffer for kid-withdrawal tests",
    ),
    "jars_withdrawal_buffer": (
        lambda email: {
            "parent": funded_user("jp." + email, "JarBufParent"),
            "user_1": jar_user(email, "JarBuffer", "@parent", "QA WD Jar"),
            **ach_credits("@user_1", WITHDRAWAL_BUFFER, prefix="jarbuf"),
        },
        f"${WITHDRAWAL_BUFFER:,} ACH-settled jar sub-account buffer for jar-withdrawal tests",
    ),
    # One known ACH credit of HISTORY_SEEDED_DEPOSIT — the deposit renders as a 'Buy' row
    # in Transaction History whose parsed amount == the seeded value (TC-11 ledger oracle),
    # and current_balance == the deposit exactly. user_1 is the login user.
    "history_seeded_deposit": (
        lambda email: {
            "user_1": funded_user(email, "HistDeposit"),
            "deposit_1": ach_credit("@user_1", HISTORY_SEEDED_DEPOSIT),
        },
        f"user with one known ${HISTORY_SEEDED_DEPOSIT} ACH credit for transaction-history ledger test",
    ),
    # Two kid sub-accounts of DISTINCT ACH-settled balances under ONE parent (TC-03):
    # log in AS the parent, open Kids, assert each rendered kid-card value == that kid's
    # own backend balance and the siblings differ. user_1 (parent) is the stored login
    # user; the kids get deterministic a.<email>/b.<email> addresses so the test can
    # reconstruct each kid's login to read its ground-truth balance.
    "kids_siblings_distinct": (
        lambda email: {
            "user_1": funded_user(email, "KidSibParent"),
            "kid_a": kid_user("a." + email, "KidSibAlpha", "@user_1"),
            **ach_credits("@kid_a", KID_A_BALANCE, prefix="kida"),
            "kid_b": kid_user("b." + email, "KidSibBravo", "@user_1"),
            **ach_credits("@kid_b", KID_B_BALANCE, prefix="kidb"),
        },
        f"two kid sub-accounts of distinct ACH-settled balances (${KID_A_BALANCE:,}/${KID_B_BALANCE:,}) under one parent",
    ),
    # Two NAMED jar sub-accounts of DISTINCT ACH-settled balances under ONE parent: log in
    # AS the parent, open Jars, assert each name-scoped jar-card value
    # (JarsPage.get_jar_balance_by_name) == that jar's backend balance and siblings differ.
    # JAR_A_NAME / JAR_B_NAME are the card labels.
    "jars_siblings_distinct": (
        lambda email: {
            "user_1": funded_user(email, "JarSibParent"),
            "jar_a": jar_user("a." + email, "JarSibAlpha", "@user_1", JAR_A_NAME),
            **ach_credits("@jar_a", JAR_A_BALANCE, prefix="jara"),
            "jar_b": jar_user("b." + email, "JarSibBravo", "@user_1", JAR_B_NAME),
            **ach_credits("@jar_b", JAR_B_BALANCE, prefix="jarb"),
        },
        f"two named jar sub-accounts of distinct ACH-settled balances (${JAR_A_BALANCE:,}/${JAR_B_BALANCE:,}) under one parent",
    ),

    # ===================================================================
    # NEW (backlog batch) — bare sub-accounts, caps, conservation, goals,
    # per-entity portfolio, tier-gating. All balances are REAL exact ACH.
    # ===================================================================

    # BARE kid: a kid sub-account with NO ACH credit at all -> backend current_balance
    # == 0.0 exactly. For new-kid-zero-start ($0.00, not blank/null/inherited). user_1
    # is the PARENT (stored login); the kid gets a deterministic k.<email> address so
    # the test can log in AS the kid to read its ground-truth 0.0 balance.
    "bare_kid": (
        lambda email: {
            "user_1": funded_user(email, "BareKidParent"),
            "kid_1": kid_user("k." + email, "BareKid", "@user_1"),
        },
        "parent with ONE bare (unfunded) kid -> kid current_balance == 0.0 exactly",
    ),

    # SIX jars at the cap (Setting.jars_limit_number default == 6). Bare jars (no ACH)
    # to skip 6x settle. For jar-six-cap-enforced: count stays 6, 7th blocked. The
    # parent (user_1) is the login user; jars are named QA Cap Jar 1..6 deterministically.
    "six_jars_cap": (
        lambda email: {
            "user_1": funded_user(email, "SixJarParent"),
            **{f"jar_{i}": jar_user(f"j{i}." + email, f"CapJar{i}", "@user_1",
                                    f"QA Cap Jar {i}") for i in range(1, 7)},
        },
        "parent at the 6-jar cap (6 bare jars) for the six-jar-cap-enforced negative test",
    ),

    # EIGHT kids. NOTE on enforcement (see manifest flag): there is NO 8-kid hard cap on
    # DEV by default — Setting.kids_limit_number default == 0 (disabled) and Regular/Plus
    # plans set Kid.allowed_count == Float::INFINITY. This fixture exists so the test can
    # seed the state, but the 9th create will SUCCEED unless the DEV Setting is non-zero.
    # The kid-eight-cap test must assert STATE/characterize, or ship skip-with-evidence.
    "eight_kids_cap": (
        lambda email: {
            "user_1": funded_user(email, "EightKidParent"),
            **{f"kid_{i}": kid_user(f"k{i}." + email, f"CapKid{i}", "@user_1")
               for i in range(1, 9)},
        },
        "parent with 8 bare kids for the eight-kid-cap test (cap NOT enforced on DEV by default)",
    ),

    # CONSERVATION rig: Main + 1 funded jar + 1 funded kid, small EXACT ACH balances.
    # For deposit-main-routing-isolation, main-jar-transfer-conserves (API half),
    # home-total-conservation, networth-total-investments-recon. Each sub-account has a
    # deterministic address so the test can read every account's ground-truth balance
    # and assert delta==0 on the ones that must not move.
    "conserve_main_jar_kid": (
        lambda email: {
            "user_1": funded_user(email, "ConserveMain"),
            **ach_credits("@user_1", CONSERVE_MAIN_BALANCE, prefix="main"),
            "jar_1": jar_user("cj." + email, "ConserveJar", "@user_1", "QA Conserve Jar"),
            **ach_credits("@jar_1", CONSERVE_JAR_BALANCE, prefix="cjar"),
            "kid_1": kid_user("ck." + email, "ConserveKid", "@user_1"),
            **ach_credits("@kid_1", CONSERVE_KID_BALANCE, prefix="ckid"),
        },
        f"Main ${CONSERVE_MAIN_BALANCE} + jar ${CONSERVE_JAR_BALANCE} + kid ${CONSERVE_KID_BALANCE} "
        "(small exact ACH) for conservation/reconciliation tests",
    ),

    # KID-FUND-NO-CROSS-POST rig: two kids under one parent, small exact ACH. The test
    # credits Kid-A +$25 via the gen API at runtime, then asserts Kid-A delta==+25 and
    # Kid-B delta==0.00 exactly. Kids get a.<email>/b.<email> addresses.
    "kid_fund_two": (
        lambda email: {
            "user_1": funded_user(email, "KidFundParent"),
            "kid_a": kid_user("a." + email, "KidFundAlpha", "@user_1"),
            **ach_credits("@kid_a", KID_FUND_A_BALANCE, prefix="kfa"),
            "kid_b": kid_user("b." + email, "KidFundBravo", "@user_1"),
            **ach_credits("@kid_b", KID_FUND_B_BALANCE, prefix="kfb"),
        },
        f"two kids (${KID_FUND_A_BALANCE}/${KID_FUND_B_BALANCE} exact ACH) for fund-Kid-A-only no-cross-post",
    ),

    # JAR GOAL/target round-trip: one jar with saving_amount == $5,000 and a small ACH
    # balance, named 'Europe trip'. For jar-target-roundtrip (reads back $5,000.00).
    "jar_target_goal": (
        lambda email: {
            "user_1": funded_user(email, "JarTargetParent"),
            "jar_1": jar_user("jt." + email, "JarTarget", "@user_1", JAR_TARGET_NAME,
                              saving_amount=JAR_TARGET_GOAL),
            **ach_credits("@jar_1", 100.00, prefix="jt"),
        },
        f"jar '{JAR_TARGET_NAME}' with goal ${JAR_TARGET_GOAL:,} for target round-trip",
    ),

    # JAR PROGRESS-RING: goal $200, balance $150 -> exactly 75%. For jar-goal-progress-ring.
    "jar_progress_ring": (
        lambda email: {
            "user_1": funded_user(email, "JarRingParent"),
            "jar_1": jar_user("jr." + email, "JarRing", "@user_1", RING_JAR_NAME,
                              saving_amount=RING_GOAL),
            **ach_credits("@jar_1", RING_BALANCE, prefix="jr"),
        },
        f"jar '{RING_JAR_NAME}' goal ${RING_GOAL} balance ${RING_BALANCE} (==75%) for progress-ring math",
    ),

    # PER-STYLE portfolio users (allocation-weights). Verified portfolio_name accepted:
    # Aggressive / Conservative / Moderate. Each is a standalone funded user; the test
    # reads the allocation mix per style and asserts they differ + each sums 100%.
    # Assert the LABEL + published mix, never a balance (Moderate prices to $0).
    "portfolio_aggressive": (
        lambda email: {"user_1": tiered_user(email, "PfAggr", "regular", STYLE_AGGRESSIVE),
                       **ach_credits("@user_1", 100.00, prefix="pa")},
        f"funded user on the {STYLE_AGGRESSIVE} portfolio (allocation-weights / per-style)",
    ),
    "portfolio_conservative": (
        lambda email: {"user_1": tiered_user(email, "PfConsv", "regular", STYLE_CONSERVATIVE),
                       **ach_credits("@user_1", 100.00, prefix="pc")},
        f"funded user on the {STYLE_CONSERVATIVE} portfolio (allocation-weights / per-style)",
    ),
    "portfolio_moderate": (
        lambda email: {"user_1": tiered_user(email, "PfMod", "regular", STYLE_MODERATE)},
        f"funded user on the {STYLE_MODERATE} portfolio (label only — Moderate prices to $0)",
    ),

    # PER-KID portfolio independence (static half): kid-A Aggressive vs kid-B Conservative
    # under one parent; assert LABEL distinctness A!=B (LABEL only, no balance).
    # NB: kid-B uses Conservative, NOT Moderate. Empirically (DEV, build 3252) the seed
    # trait `:has_portfolio` wires Aggressive AND Conservative onto a user's own record
    # (allocation_profile_id present) but does NOT wire Moderate — both an adult
    # `portfolio_moderate` fixture and a Moderate kid come back with
    # allocation_profile_id=None (Portfolio.find_by_localized_name('Moderate') does not
    # resolve to a seedable user.portfolio on DEV). The case's real oracle is per-kid
    # INDEPENDENCE (A != B, distinct uuids) — the specific styles are only the vehicle, so
    # kid-B is grounded on the reliably-seedable Conservative style instead of the
    # non-seedable Moderate. This keeps the validated property identical while turning a
    # permanent vacuous skip into a real value-asserting pass.
    "kids_portfolio_distinct": (
        lambda email: {
            "user_1": funded_user(email, "KidPfParent"),
            "kid_a": kid_user("a." + email, "KidPfAlpha", "@user_1",
                              portfolio_name=STYLE_AGGRESSIVE),
            "kid_b": kid_user("b." + email, "KidPfBravo", "@user_1",
                              portfolio_name=STYLE_CONSERVATIVE),
        },
        f"two kids on distinct portfolios ({STYLE_AGGRESSIVE} vs {STYLE_CONSERVATIVE}) for per-kid independence",
    ),

    # PER-JAR portfolio independence: jar on Conservative under a Main on Aggressive.
    # Assert jar reads Conservative, Main reads Aggressive, A!=B (independent storage).
    "jar_portfolio_distinct": (
        lambda email: {
            "user_1": tiered_user(email, "JarPfParent", "regular", STYLE_AGGRESSIVE),
            "jar_1": jar_user("jp." + email, "JarPfConsv", "@user_1", JAR_PF_NAME,
                              portfolio_name=STYLE_CONSERVATIVE),
            **ach_credits("@jar_1", 80.00, prefix="jp"),
        },
        f"jar '{JAR_PF_NAME}' on {STYLE_CONSERVATIVE} vs Main on {STYLE_AGGRESSIVE} (per-jar independence)",
    ),

    # FUNDED jar for below-$5 deposit rejection: small exact ACH balance; the test
    # attempts a $4/$0 deposit and asserts the jar balance delta==0.
    "jar_below_min": (
        lambda email: {
            "user_1": funded_user(email, "JarMinParent"),
            "jar_1": jar_user("jm." + email, "JarMin", "@user_1", "QA Min Jar"),
            **ach_credits("@jar_1", BELOW_MIN_JAR_BALANCE, prefix="jm"),
        },
        f"funded jar (${BELOW_MIN_JAR_BALANCE} exact ACH) for the below-$5 deposit-rejection test",
    ),

    # INFLOW triple-oracle: one user with a known exact ACH lump-sum credit. The test
    # ties a typed History 'Buy' row + the value tile (== current_balance) + the backend
    # Investment type. Uses a small distinctive amount.
    #
    # IMPORTANT: this credit carries the `transfer_initiator` trait IN ADDITION to the
    # usual lump_sum / with_shares_settled_status / with_holdings. The mobile History feed
    # (/v2/investments -> build_investments_query -> the
    # `transfer_initiators_or_debits_including_rebalances` scope) only returns a
    # CreditInvestment row when `transferred_by_id == id AND transferred_amount IS NOT NULL`.
    # The model backfills that via `after_create :set_transferred_by`, but that callback
    # ONLY fires when `status == "transferred"` (CreditInvestment.rb:74-77). A credit seeded
    # straight to `shares_settled` (as the gen API does) therefore has a NULL
    # transferred_by_id and is FILTERED OUT of the feed -- verified empirically: balance
    # settles to the seeded amount but /v2/investments returns 0 rows (even with status=all).
    # The `transfer_initiator` factory trait backfills transferred_by_id=id /
    # transferred_amount=amount after create, so the row surfaces as a settled 'Buy' of the
    # exact amount (verified on DEV: amount=212.5, type/title='Buy', pending=False,
    # grouped_status='invested', and current_balance lands on EXACTLY 212.5 -- no drift).
    # This is the seedable shape for the History-row leg; it does NOT change what the test
    # validates, only makes the (already-correct) credit visible in the feed the test reads.
    "inflow_seeded": (
        lambda email: {
            "user_1": funded_user(email, "InflowSeed"),
            "deposit_1": {
                "model": "credit_investment",
                "traits": ["lump_sum", "with_shares_settled_status", "with_holdings",
                           "transfer_initiator"],
                "attributes": {"user": "@user_1", "amount": 212.50,
                               "created_at": "2024-01-01", "payment_method": "ACH"},
            },
        },
        "user with one known $212.50 ACH lump-sum (transfer_initiator -> surfaces as a "
        "settled 'Buy' History row) for the inflow triple-oracle",
    ),

    # TIER-GATING (spike-gated). Starter == the app's "Lite" plan (gen plan_identifier
    # 'starter'; 'lite' is NOT a valid identifier). Backend ENFORCES: Starter parents
    # are blocked from creating kids (Kid.allowed_count default 0 -> StarterCreateError);
    # Regular/Plus allow them (allowed_count INFINITY). Jars gating lives in the
    # UserPlans::*::Limitations::Jar classes. Starter only permits Conservative/
    # Moderately Conservative/Moderate portfolios. Each tier user is funded with $100
    # exact ACH so the on-device tests reach Home. Pair the Lite user with a Regular
    # control in the same run (tier-gating-kids-jars asserts gating STATE).
    "plan_lite": (
        lambda email: {"user_1": tiered_user(email, "PlanLite", "starter", STYLE_MODERATE),
                       **ach_credits("@user_1", 100.00, prefix="pll")},
        "STARTER ('Lite') plan user on Moderate (kids/jars upgrade-gated at API + UI)",
    ),
    "plan_regular": (
        lambda email: {"user_1": tiered_user(email, "PlanRegular", "regular", STYLE_AGGRESSIVE),
                       **ach_credits("@user_1", 100.00, prefix="plr")},
        "REGULAR plan user (kids/jars enabled) — control for tier-gating",
    ),
    "plan_plus": (
        lambda email: {"user_1": tiered_user(email, "PlanPlus", "plus", STYLE_AGGRESSIVE),
                       **ach_credits("@user_1", 100.00, prefix="plp")},
        "PLUS plan user (kids/jars enabled; custom builder) — control for tier-gating",
    ),

    # MY FINANCE empty state: a funded user WITHOUT the registered_in_yodlee trait, so
    # there is no synced spend -> Where-You-Spend == $0/empty. funded_user adds
    # registered_in_yodlee by default in app_ready mode, so build it explicitly without it.
    # Small EXACT ACH balance so the user is genuinely FUNDED (matching the backlog
    # oracle "FUNDED but UNLINKED") — this makes the empty My Finance result NON-vacuous:
    # it isolates the no-Yodlee SPEND state from "empty/shell account". Investment balance
    # never creates AccountMonitor spend transactions, so Where-You-Spend/Future Cash stay
    # empty regardless of the deposit. Small + exact (not the priced buffer) so the funded
    # precondition reads a stable current_balance.
    "myfinance_unlinked": (
        lambda email: {"user_1": _unlinked_user(email, "MyFinUnlinked"),
                       **ach_credits("@user_1", MYFIN_UNLINKED_BALANCE, prefix="mfu")},
        f"FUNDED (${MYFIN_UNLINKED_BALANCE} exact ACH) user NOT registered_in_yodlee "
        "-> true empty My Finance spend state",
    ),
}


def _unlinked_user(email, first):
    """A funded, onboarded user with NO Yodlee link (no synced spend) for the
    My Finance empty-state test. funded_user(app_ready=True) adds registered_in_yodlee;
    strip it so Where-You-Spend reads a true zero/empty state."""
    u = funded_user(email, first, app_ready=True)
    if "registered_in_yodlee" in u["traits"]:
        u["traits"].remove("registered_in_yodlee")
    return u


def _load():
    if os.path.exists(_REGISTRY):
        with open(_REGISTRY) as fh:
            return json.load(fh)
    return {}


def _save(reg):
    os.makedirs(os.path.dirname(_REGISTRY), exist_ok=True)
    with open(_REGISTRY, "w") as fh:
        json.dump(reg, fh, indent=2)


def get_or_create_fixture_user(key):
    """Return the stored fixture user for `key` (reused if it still logs in), else
    seed a fresh one, store it, and return it. Returns a dict with at least
    email/password/user_id/onboarded."""
    if key not in FIXTURES:
        raise KeyError(f"unknown fixture '{key}'; known: {list(FIXTURES)}")
    reg = _load()
    rec = reg.get(key)
    if rec and can_login(rec["email"], rec.get("password", SEEDED_PWD)):
        rec["reused"] = True
        return rec

    builder, _ = FIXTURES[key]
    email = f"fixture.{key}.{int(time.time())}@emel.xyz"
    status, body = gen_create(builder(email))
    if status != 200:
        raise RuntimeError(f"failed to seed fixture '{key}': HTTP {status} {body}")
    rec = {
        "key": key, "email": email, "password": SEEDED_PWD,
        "user_id": body.get("created", {}).get("user_1", {}).get("id"),
        "created_at": int(time.time()), "onboarded": False, "reused": False,
    }
    reg[key] = rec
    _save(reg)
    return rec


def mark_onboarded(key):
    """Record that this fixture has been driven through first-login onboarding once
    (so on-device tests can skip the gauntlet on later runs)."""
    reg = _load()
    if key in reg:
        reg[key]["onboarded"] = True
        _save(reg)


if __name__ == "__main__":
    # Seed/verify the canonical fixtures and print the registry state.
    for k in FIXTURES:
        t0 = time.time()
        u = get_or_create_fixture_user(k)
        bal = current_balance(u["email"])
        print(f"{k}: {'REUSED' if u.get('reused') else 'CREATED'} {u['email']} "
              f"id={u.get('user_id')} balance=${bal} onboarded={u['onboarded']} "
              f"({time.time() - t0:.1f}s)")
