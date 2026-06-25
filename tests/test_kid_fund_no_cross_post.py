"""
kid-fund-no-cross-post (P0, data_mode dynamic) — API-LAYER half.

BACKLOG ORACLE (refined):
  Funding Kid-A credits ONLY Kid-A. Credit Kid-A +$25 -> Kid-A delta == +25.00,
  sibling Kid-B delta == 0.00 EXACTLY. The on-device parent-side lump-sum-into-Kid-A
  is a SEPARATE deferred unit; the parent-funding-debit clause is DROPPED (no oracle).
  Implement at the API layer first (no device, deterministic, no market drift).

WHY THIS IS SEEDED IN A SINGLE CREATE (not a cross-create runtime re-credit of the
persisted `kid_fund_two` fixture):
  The provision manifest assigns `kid_fund_two` (parent + Kid-A $60 / Kid-B $20, live)
  and asks to "credit Kid-A +$25 at runtime". A runtime re-credit needs the gen API to
  reference an ALREADY-EXISTING user from a NEW create payload. That is not supported —
  PROBED 2026-06-24 against DEV: a credit_investment whose `user` is the persisted Kid-A
  email (or {email:...}) is rejected 422:
      "User(#...) expected, got \"a.fixture.kid_fund_two...@emel.xyz\" which is an
       instance of String"
  The gen API only resolves @<key> references WITHIN the same create payload. So the
  faithful, deterministic way to assert the SAME oracle (a +$25 credit posts to Kid-A
  only; the sibling does not move) is to seed the whole two-kid rig in ONE create where
  Kid-A receives its base ACH balance PLUS a DISTINCT +$25.00 ACH credit, and Kid-B
  receives ONLY its own base. Then:
    - Kid-A settles to (base_A + 25.00)  -> the +$25 posted to Kid-A.
    - Kid-B settles to base_B EXACTLY    -> the credit did NOT cross-post to the sibling
                                            (Kid-B delta from its seeded base == 0.00).
  Each kid is its OWN backend User (kid_account / DependentUser) with its OWN
  current_balance from its OWN holdings (verified: persisted fixture reads Kid-A $60.04
  vs Kid-B $20.01 via separate tokens) — there is no shared sibling ledger, which is
  exactly the cross-post invariant under test.

Small EXACT ACH amounts (NOT the repricing buffer): base_A $60.00, base_B $20.00, the
funding credit $25.00. ACH lump-sum credits settle to current_balance EXACTLY and stay
stable (no market drift), so the delta is read precisely.

needs_device: FALSE — pure DEV-API value test.
Run (no emulator):
  venv/bin/python -m pytest tests/test_kid_fund_no_cross_post.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import (
    SEEDED_PWD, current_balance, gen_create,
    funded_user, kid_user, ach_credit, ach_credits,
)

pytestmark = pytest.mark.value_api

# Small EXACT ACH amounts (stable, no drift). Kid-A's funding credit is DISTINCT from
# both base balances so its arrival is unambiguous.
KID_A_BASE = 60.00
KID_B_BASE = 20.00
FUND_AMOUNT = 25.00
KID_A_EXPECTED = round(KID_A_BASE + FUND_AMOUNT, 2)   # 85.00 — base + the +$25 credit

BAND = 1.50            # ACH credits settle on the EXACT dollar amount (cents tolerance)
NO_MOVE_EPS = 0.05     # sibling "delta == 0.00 exactly": only read jitter (sub-cent) allowed
SETTLE_BUDGET_S = int(__import__("os").getenv("SETTLE_BUDGET_S", "480"))
POLL_INTERVAL_S = int(__import__("os").getenv("POLL_INTERVAL_S", "20"))


def _poll_until(email, target, budget_s=SETTLE_BUDGET_S):
    """Poll the user's OWN current_balance until it lands within BAND of target.
    Returns (best_seen, settled_bool)."""
    waited, best = 0, -1.0
    while waited <= budget_s:
        bal = current_balance(email, SEEDED_PWD)
        if bal is not None:
            best = bal if best < 0 else max(best, bal)
            print(f"  [poll {email[:22]} +{waited}s] current_balance={bal}")
            if abs(bal - target) <= BAND:
                return bal, True
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return best, False


def test_funding_kid_a_does_not_cross_post_to_sibling_kid_b():
    """+$25 credited to Kid-A posts to Kid-A ONLY: Kid-A settles to base+25, sibling
    Kid-B settles to its OWN base with delta == 0.00 (no cross-post leak)."""
    ts = str(int(time.time()))
    parent_email = f"kidfund.parent.{ts}@emel.xyz"
    kid_a_email = f"a.kidfund.{ts}@emel.xyz"
    kid_b_email = f"b.kidfund.{ts}@emel.xyz"

    # One create: parent + 2 kids. Kid-A = base + the +$25 funding credit; Kid-B = base only.
    payload = {
        "user_1": funded_user(parent_email, f"KidFundParent{ts}"),
        "kid_a": kid_user(kid_a_email, f"KidFundAlpha{ts}", "@user_1"),
        "kid_b": kid_user(kid_b_email, f"KidFundBravo{ts}", "@user_1"),
        # Kid-A base balance (split into <=$10k ACH chunks).
        **ach_credits("@kid_a", KID_A_BASE, prefix="kfa"),
        # Kid-B base balance — the sibling that must NOT move.
        **ach_credits("@kid_b", KID_B_BASE, prefix="kfb"),
        # The funding action under test: a DISTINCT +$25 credit to Kid-A ONLY.
        "fund_kid_a": ach_credit("@kid_a", FUND_AMOUNT),
    }
    status, body = gen_create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    created = body.get("created", {})
    assert created.get("kid_a", {}).get("id"), f"no Kid-A user id: {body}"
    assert created.get("kid_b", {}).get("id"), f"no Kid-B user id: {body}"
    print(f"  created Kid-A {created['kid_a']['id']} (base ${KID_A_BASE} + ${FUND_AMOUNT}), "
          f"Kid-B {created['kid_b']['id']} (base ${KID_B_BASE})")

    # Kid-A must settle to base + the +$25 credit -> the funding posted to Kid-A.
    bal_a, settled_a = _poll_until(kid_a_email, KID_A_EXPECTED)
    assert settled_a, (f"Kid-A never settled to ${KID_A_EXPECTED} (base ${KID_A_BASE} "
                       f"+ ${FUND_AMOUNT}); best seen ${bal_a}")
    assert bal_a == pytest.approx(KID_A_EXPECTED, abs=BAND), (
        f"Kid-A expected ${KID_A_EXPECTED} (= ${KID_A_BASE} + ${FUND_AMOUNT}) but read ${bal_a}")

    # Kid-B (sibling) must settle to its OWN base — the +$25 did NOT cross-post.
    bal_b, settled_b = _poll_until(kid_b_email, KID_B_BASE)
    assert settled_b, f"Kid-B never settled to its base ${KID_B_BASE}; best seen ${bal_b}"

    # Sibling delta == 0.00 EXACTLY (load-bearing assertion): Kid-B's balance equals its
    # seeded base, with only sub-cent read jitter allowed — no portion of the $25 leaked.
    sibling_delta = round(bal_b - KID_B_BASE, 2)
    assert abs(sibling_delta) <= NO_MOVE_EPS, (
        f"CROSS-POST LEAK: Kid-B moved by ${sibling_delta} (read ${bal_b}, base ${KID_B_BASE}) "
        f"when ONLY Kid-A was funded +${FUND_AMOUNT} — sibling delta must be 0.00")

    # And the +$25 is fully accounted for on Kid-A, not split across the two kids.
    kid_a_delta = round(bal_a - KID_A_BASE, 2)
    assert kid_a_delta == pytest.approx(FUND_AMOUNT, abs=BAND), (
        f"Kid-A delta ${kid_a_delta} != funded ${FUND_AMOUNT}")

    print(f"  PASS: Kid-A delta +${kid_a_delta} (== ${FUND_AMOUNT}); "
          f"Kid-B delta ${sibling_delta} (== 0.00, no cross-post)")
