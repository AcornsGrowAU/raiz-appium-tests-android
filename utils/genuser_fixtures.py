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
    funded_user, ach_credit, ach_credits, kid_user, jar_user,
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
}


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
