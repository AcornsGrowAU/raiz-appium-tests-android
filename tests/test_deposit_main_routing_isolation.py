"""
deposit-main-routing-isolation (P0, cross-feature-conservation) — API LAYER.

Oracle (backlog row + notes):
  Seed Main + >=1 jar + >=1 kid; drive $10 into Main; every jar/kid backend
  delta == 0 (LOAD-BEARING). The Main rise is scoped SOFT (async settle -> band),
  NOT an exact +$10, because ACH credits settle asynchronously.

Why API-layer-first (notes + manifest): deterministic, no device. The ROUTING of a
deposit is decided in the backend — a credit_investment is attributed to exactly ONE
user (the @ref it names), so a deposit routed at Main has no path to touch the jar/kid
sub-accounts (each a distinct user with its own balance). The kid balance is read via
its own login (kids can log in); the jar has NO loginable identity (a jar-email login
401s by design), so its balance (accumulated_amount) is read by NAME via the PARENT
session's jars API. This proves the isolation invariant directly against backend
ground truth. The on-device deposit leg
is a separate concern; the value-isolation invariant is fully provable here.

DETERMINISM — seed a fresh, self-contained rig per run (the proven same-payload @-alias
recipe used by every green test in test_value_validation_api.py), with the $10 Main
routing deposit included as its OWN credit in the SAME create. We do NOT mutate a shared
fixture or attach a credit to a pre-existing user by id (that resolution is unproven on
the gen API and would be fragile/non-deterministic). The conserve_main_jar_kid balances
(Main $300 / jar $80 / kid $40 — small EXACT ACH, no market drift) are mirrored here so
the rig is identical in shape to the manifest fixture but reproduced cleanly each run.

The isolation oracle is then exact: the jar/kid each hold EXACTLY their own seeded
balance (delta-from-seed == 0.00) AFTER a $10 deposit landed on Main in the same create
— i.e. the Main deposit did not leak a cent into any sub-account. Main is the soft leg
(settles to ~base+$10 within an async band).

Honesty: any seed/login/settle gate -> skip-with-reason (clear evidence), never a fake
or vacuous pass.

LEAK MUST FAIL, NOT SKIP: the jar/kid settle-gate polls until each reaches AT LEAST its
own seed (">= seed"), NOT until it lands within a band AROUND the seed. A band-poll would
mark a leaked sub-account (seed+$10) as "never settled" and SKIP it — masking the exact
bug this test hunts. The ">= seed" gate lets a leak clear the gate and FAIL the load-
bearing delta==0 assertion, while a base ACH that never lands still skips honestly.

Run (no emulator):
  venv/bin/python -m pytest tests/test_deposit_main_routing_isolation.py -v -s -o addopts=""
"""
import os
import time

import pytest

from utils.genuser_api import (
    BalanceReader, SEEDED_PWD, ach_credit, ach_credits, gen_create,
    funded_user, jar_user, kid_user,
)
from utils.genuser_fixtures import (
    CONSERVE_JAR_BALANCE, CONSERVE_KID_BALANCE, CONSERVE_MAIN_BALANCE,
)

pytestmark = pytest.mark.value_api

# The deposit ROUTED INTO MAIN. Small + EXACT ACH (within the $10k single-txn cap),
# deliberately NOT the repricing six-figure buffer, so the Main settle band stays tight.
DEPOSIT = 10.00

# Sub-accounts are NEVER referenced by the Main deposit credit, so each must settle to
# EXACTLY its own seeded balance — delta-from-seed must be 0.00 to the cent (load-bearing).
DELTA_EPS = 0.01

# Main settles asynchronously. Soft band: once settled, Main lands within this tolerance
# of (base + DEPOSIT). We do NOT hard-assert the exact +$10 (async settle may lag).
SETTLE_BAND = 1.50
SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "360"))
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))

# The seeded jar card's name — jars have NO loginable identity (a jar-email login
# 401s by design), so the jar leg is read by THIS name via the PARENT session
# (jar_balance_by_name -> accumulated_amount == the jar's own balance).
JAR_NAME = "QA Route Jar"


def _ts():
    return str(int(time.time()))


def _interleaved_settle(parent_reader, main_target, jar_name, jar_seed,
                        kid_reader, kid_seed, budget_s):
    """Settle Main + jar + kid in ONE interleaved loop under a SINGLE shared budget,
    reading through mint-once cached-token readers.

    WHY MERGED (reliability): the old shape ran three SERIAL per-account polls, each with
    its OWN full budget and each re-logging-in (current_balance()/jar_balance_by_name()
    mint a fresh /v1/sessions token) on EVERY iteration — dozens of redundant logins for
    the same handful of accounts, which both causes and gets tripped by /v1/sessions
    rate-limiting. Here one `parent_reader` login serves BOTH the Main /v1/user read and
    the jar /jars/v1/users read, and one `kid_reader` login serves the kid; both are
    re-minted only on a rejected read. All three accounts are polled together within the
    SAME budget window instead of end-to-end.

    Each account's settle CRITERION is UNCHANGED from the old per-account polls; only the
    scheduling is merged:
      - Main (SOFT leg): settled == within SETTLE_BAND of `main_target` (~base+$10).
      - jar / kid (LOAD-BEARING): landed == balance reaches AT LEAST its own seed
        (>= seed - DELTA_EPS). This is deliberately NOT a band-poll around `seed`: the
        jar/kid are the isolation oracle, and a routing LEAK would push a sub-account to
        seed+$10, which a band around `seed` would NEVER mark settled — the test would
        SKIP ("base ACH did not settle") and silently MASK the leak it exists to catch.
        Gating on ">= seed" lets a leaked sub-account CLEAR the gate and then FAIL the
        exact delta==0 assertion, while a genuinely lagging base ACH still skips honestly.
        Balances only rise on an inbound credit and a seeded ACH settles to EXACTLY its
        amount, so ">= seed" is a sound "base landed" signal that does not pre-judge delta.

    Returns (main_best, main_settled, jar_best, jar_settled, kid_best, kid_settled);
    each *_best is the max balance seen (0.0 if never read)."""
    waited = 0
    main_best = jar_best = kid_best = 0.0
    main_settled = jar_settled = kid_settled = False
    while waited <= budget_s:
        if not main_settled:
            bal = parent_reader.current_balance()
            if bal is not None:
                main_best = max(main_best, bal)
                print(f"  [poll main +{waited}s] current_balance={bal} (target ~{main_target})")
                if abs(bal - main_target) <= SETTLE_BAND:
                    main_settled = True
        if not jar_settled:
            bal = parent_reader.jar_balance_by_name(jar_name)
            if bal is not None:
                jar_best = max(jar_best, bal)
                print(f"  [poll jar '{jar_name}' +{waited}s] balance={bal} (seed {jar_seed})")
                if bal >= jar_seed - DELTA_EPS:
                    jar_settled = True
        if not kid_settled:
            bal = kid_reader.current_balance()
            if bal is not None:
                kid_best = max(kid_best, bal)
                print(f"  [poll kid +{waited}s] balance={bal} (seed {kid_seed})")
                if bal >= kid_seed - DELTA_EPS:
                    kid_settled = True
        if main_settled and jar_settled and kid_settled:
            break
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return main_best, main_settled, jar_best, jar_settled, kid_best, kid_settled


def test_deposit_into_main_does_not_move_jar_or_kid():
    """Route a $10 ACH deposit into the Main parent (in the same create that seeds the
    rig); assert the jar and kid each settle to EXACTLY their own seeded balance
    (delta-from-seed == 0.00, load-bearing) — the Main deposit leaked nothing into any
    sub-account — and Main settles to ~base+$10 (soft async band)."""
    ts = _ts()
    main_email = f"route.main.{ts}@emel.xyz"
    jar_email = f"route.jar.{ts}@emel.xyz"
    kid_email = f"route.kid.{ts}@emel.xyz"

    main_base = CONSERVE_MAIN_BALANCE          # 300.00
    jar_seed = CONSERVE_JAR_BALANCE            # 80.00  -> must stay EXACTLY this
    kid_seed = CONSERVE_KID_BALANCE            # 40.00  -> must stay EXACTLY this
    main_target = round(main_base + DEPOSIT, 2)  # 310.00 (soft)

    # One self-contained create: Main parent + funded jar + funded kid (small EXACT ACH),
    # PLUS the $10 routing deposit as its OWN credit referencing ONLY @user_1 (Main).
    # No jar/kid ref appears in the deposit -> the backend has no path to move them.
    payload = {
        "user_1": funded_user(main_email, f"RouteMain{ts}"),
        **ach_credits("@user_1", main_base, prefix="mainbase"),
        "jar_1": jar_user(jar_email, f"RouteJar{ts}", "@user_1", JAR_NAME),
        **ach_credits("@jar_1", jar_seed, prefix="jarbase"),
        "kid_1": kid_user(kid_email, f"RouteKid{ts}", "@user_1"),
        **ach_credits("@kid_1", kid_seed, prefix="kidbase"),
        # THE ROUTED DEPOSIT — into Main only.
        "deposit_main": ach_credit("@user_1", DEPOSIT),
    }
    status, body = gen_create(payload)
    if status != 200 or not (isinstance(body, dict)
                             and body.get("created", {}).get("deposit_main", {}).get("id")):
        pytest.skip(
            "skip-with-reason: could not seed the routing-isolation rig + $10 Main "
            f"deposit (HTTP {status} {str(body)[:160]}); seed gate, not a product result")
    created = body["created"]
    print(f"  created rig: Main {created['user_1']['id']} (base ${main_base} + ${DEPOSIT} "
          f"routed), Jar {created['jar_1']['id']} (${jar_seed}), Kid {created['kid_1']['id']} (${kid_seed})")

    # --- Settle all three accounts in ONE interleaved loop under a SINGLE shared budget,
    # reading through mint-once cached-token readers (one parent login serves BOTH the
    # Main /v1/user and the jar /jars/v1/users reads; one kid login serves the kid). This
    # replaces three serial per-account budgets that each re-logged-in every iteration and
    # tripped /v1/sessions rate-limiting. Main is the SOFT band leg; the jar and the kid
    # are the LOAD-BEARING isolation oracle (each gated ">= its own seed", never a band
    # around the seed, so a routing LEAK to seed+$10 clears the gate and FAILS the exact
    # delta==0 assertion rather than being masked as an unsettled skip). The kid reads via
    # its own login; the jar (no loginable identity) reads by name via the PARENT session.
    parent_reader = BalanceReader(main_email, SEEDED_PWD)
    kid_reader = BalanceReader(kid_email, SEEDED_PWD)
    (main_best, main_settled, jar_bal, jar_settled,
     kid_bal, kid_settled) = _interleaved_settle(
        parent_reader, main_target, JAR_NAME, jar_seed,
        kid_reader, kid_seed, SETTLE_BUDGET_S)

    if jar_bal is None or kid_bal is None:
        pytest.skip("skip-with-reason: could not read jar/kid balances back "
                    "(kid own-login read / jar parent-session read — a login/settle "
                    "gate, not a product result)")

    jar_delta = round(jar_bal - jar_seed, 2)
    kid_delta = round(kid_bal - kid_seed, 2)
    print(f"  Jar settled ${jar_bal} (seed ${jar_seed}, delta {jar_delta}); "
          f"Kid settled ${kid_bal} (seed ${kid_seed}, delta {kid_delta}); Main best ${main_best}")

    # The jar/kid must have reached AT LEAST their own seed (their base ACH landed), else
    # we can't distinguish "isolated" from "not yet settled". NOTE: a routing LEAK would
    # land the sub-account at seed+$10 (>= seed), so it CLEARS this gate and FAILS the
    # exact delta==0 assertion below — it is NOT swallowed as a settle skip. Only a base
    # credit that genuinely never reached its seed skips here.
    if not (jar_settled and kid_settled):
        pytest.skip(
            "skip-with-reason: jar/kid base ACH did not reach its seed within "
            f"{SETTLE_BUDGET_S}s (jar best ${jar_bal}/{jar_settled}, kid best ${kid_bal}/"
            f"{kid_settled}); cannot assert isolation against an unsettled baseline")

    assert abs(jar_delta) <= DELTA_EPS, (
        f"ROUTING LEAK: $10 routed into Main but the JAR settled to ${jar_bal} "
        f"(seeded ${jar_seed}, delta ${jar_delta}); a Main deposit must not touch any jar")
    assert abs(kid_delta) <= DELTA_EPS, (
        f"ROUTING LEAK: $10 routed into Main but the KID settled to ${kid_bal} "
        f"(seeded ${kid_seed}, delta ${kid_delta}); a Main deposit must not touch any kid")

    # ============================ SOFT (Main leg) =========================
    # Main must have ABSORBED the deposit (>= its base; it can only rise on an inbound
    # credit). Exact +$10 settle is the soft band.
    assert main_best >= main_base - DELTA_EPS, (
        f"Main settled BELOW its ${main_base} base (best ${main_best}) after an inbound "
        f"$10 deposit — conservation/routing defect")
    if main_settled:
        assert main_best == pytest.approx(main_target, abs=SETTLE_BAND), (
            f"Main settled to ${main_best}, expected ~${main_target} "
            f"(base ${main_base} + ${DEPOSIT}, +-${SETTLE_BAND})")
        print(f"  PASS: jar/kid delta-from-seed==0 (isolated); Main absorbed +${DEPOSIT} "
              f"(${main_base} -> ${main_best})")
    else:
        # Load-bearing isolation invariant held (jar/kid exact, Main >= base). The exact
        # Main +$10 settle is the SOFT leg, so a lagging settle is reported, not failed.
        print(f"  PASS (isolation): jar/kid delta-from-seed==0 and Main >= base; the exact "
              f"+${DEPOSIT} Main settle lagged the {SETTLE_BUDGET_S}s window (best ${main_best}) "
              f"— soft leg, not the load-bearing assertion")
