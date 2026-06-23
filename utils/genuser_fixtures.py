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
    funded_user, with_balance_user, ach_credit,
    kid_with_balance_user, jar_with_balance_user,
)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REGISTRY = os.path.join(_REPO, "fixtures", "genuser_registry.json")

# Distinctive (non-round) seeded ACH credit amount for the transaction-history
# ledger test. Deterministic by recipe, so it is the oracle value the on-device
# test parses for in the history list. Chosen to be unlikely to collide with the
# with_balance priced-holding Buy rows. Keep in sync with the
# `history_seeded_deposit` fixture builder below.
HISTORY_SEEDED_DEPOSIT = 137.42

# key -> (builder(email) -> {ref: entity, ...}, human description)
FIXTURES = {
    "presence_funded": (
        lambda email: {"user_1": with_balance_user(email, "PresFunded", bought_shares=1)},
        "onboarded user with an immediate Aggressive balance (presence/value reads)",
    ),
    "rich_withdrawal_buffer": (
        # NB: credit_investment `count` makes the gen API 500 (any size) — so we use the
        # `with_balance` trait (one entity, immediate priced Aggressive holdings) to reach
        # ~$320k. In Raiz a withdrawal sells shares, so holdings ARE the withdrawal source.
        # ~$320k / $5 per test -> ~64,000 runs before re-seeding.
        lambda email: {"user_1": with_balance_user(email, "RichBuffer", bought_shares=500)},
        "~$320,000 holdings buffer for withdrawal tests (draw $5 each)",
    ),
    # Sub-account buffers. A kid/jar is its OWN user (own login + own current_balance)
    # under a parent — so on-device we log in AS the sub-account and use the same
    # Withdraw flow. user_1 is the sub-account (its id/email is what gets stored).
    "kids_withdrawal_buffer": (
        lambda email: {
            "parent": funded_user("kp." + email, "KidBufParent"),
            "user_1": kid_with_balance_user(email, "KidBuffer", "@parent", bought_shares=500),
        },
        "~$320,000 kid sub-account buffer for kid-withdrawal tests",
    ),
    "jars_withdrawal_buffer": (
        lambda email: {
            "parent": funded_user("jp." + email, "JarBufParent"),
            "user_1": jar_with_balance_user(email, "JarBuffer", "@parent", "QA WD Jar", bought_shares=500),
        },
        "~$320,000 jar sub-account buffer for jar-withdrawal tests",
    ),
    # Two kid sub-accounts of DISTINCT balances under ONE parent. Used by the
    # on-device kid-render value test (TC-03): we log in AS the parent, open the
    # Kids list, and assert each rendered kid-card value matches that kid's own
    # backend balance (band) and that the siblings are distinct. The two kids get
    # different bought_shares so their priced holdings differ materially. Each
    # kid is its OWN user (own login + own current_balance); both kid emails are
    # stored alongside the parent so the test can read each ground-truth balance.
    # The PARENT is the login user (stored at the bare `email`); the two kids get
    # deterministic `a.<email>` / `b.<email>` addresses so the test reconstructs
    # each kid's login from the stored parent email to read its backend balance.
    # `user_1` is the parent so get_or_create_fixture_user stores the parent id and
    # its reuse-login probe checks the parent (the account the device logs in as).
    # A user carrying ONE known ACH credit of HISTORY_SEEDED_DEPOSIT, on top of a
    # small with_balance holding so the account is non-empty/onboardable. The ACH
    # credit (lump_sum credit_investment) renders as a 'Buy' row in Transaction
    # History whose parsed amount == the seeded dollar value — that exact row is
    # the oracle for the ledger-correctness test (TC-11). user_1 is the login user.
    "history_seeded_deposit": (
        lambda email: {
            "user_1": with_balance_user(email, "HistDeposit", bought_shares=1),
            "deposit_1": ach_credit("@user_1", HISTORY_SEEDED_DEPOSIT),
        },
        f"user with one known ${HISTORY_SEEDED_DEPOSIT} ACH credit for transaction-history ledger test",
    ),
    "kids_siblings_distinct": (
        lambda email: {
            "user_1": funded_user(email, "KidSibParent"),
            "kid_a": kid_with_balance_user("a." + email, "KidSibAlpha", "@user_1", bought_shares=400),
            "kid_b": kid_with_balance_user("b." + email, "KidSibBravo", "@user_1", bought_shares=120),
        },
        "two kid sub-accounts of distinct balances under one parent (on-device kid render value test)",
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
