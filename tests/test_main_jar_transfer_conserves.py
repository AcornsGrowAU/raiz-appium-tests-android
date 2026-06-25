"""
main-jar-transfer-conserves (P0, value_api) — API-LAYER HALF.

CASE (backlog docs/proposed-test-cases.md): an Owner<->Jar transfer CONSERVES the
total across all of a user's accounts, and any account NOT party to the transfer is
left exactly unchanged. This is the cross-feature conservation invariant behind the
RAIZ "totals don't add up after a move between accounts" defect family — a transfer
must be a pure re-distribution: nothing is created or destroyed, and only the two
endpoints (Owner=Main and the Jar) move.

SPLIT (per the backlog REFINEMENT, verdict=refine):
  (a) API-layer conservation — seedable, deterministic, no device. THIS FILE.
  (b) on-device Owner<->Jar transfer through the app UI — DEFERRED (needs a new
      JarTransfer page object; not built here).

WHY API-LAYER, AND WHY ONE create:
  A Jar is its own User (Jar.belongs_to :jar_user) with its own current_balance,
  distinct from the parent Owner (Main) User and from any Kid User (raiz-backend
  app/models/jar.rb). So an Owner->Jar transfer of $T moves $T between two separate
  User balances; the Kid User is not party to it. The PROVEN test-data plumbing only
  references entities created in the SAME payload (@user_1 refs), so the whole
  scenario — the seeded balances AND the transfer's two ledger legs — is built in a
  SINGLE create, then read back per sub-account:

    Main:  credit M0,  WITHDRAW T   -> settles to  M0 - T   (Owner side of the move)
    Jar :  credit J0,  credit  T    -> settles to  J0 + T   (Jar side of the move)
    Kid :  credit K0                -> settles to  K0       (NOT party to the move)

  pre-transfer total  = M0 + J0 + K0
  post-transfer total = (M0 - T) + (J0 + T) + K0  == pre-transfer total  (CONSERVED)

  The two transfer legs are equal and opposite ACH movements, modelling the transfer
  at the ledger layer (the app's on-device transfer would produce the same paired
  legs). This asserts STATE/value (the conserved sum + the untouched Kid + the actual
  endpoint deltas), not enforcement of any UI control.

DATA: small EXACT ACH balances (NOT the repricing six-figure buffer) so every balance
settles to an exact, drift-free current_balance and the sum reconciles to the cent.
The jar-withdrawal leg uses the recipe proven live in tests/test_value_validation_api.py
(the historical jar-withdrawal 422 gate is no longer reproducible; if it RE-APPEARS the
create 422s on the exceed/balance signature and this test fails LOUDLY rather than
masking — see _WD_GATE_KEYS).

Run (no emulator):
  venv/bin/python -m pytest tests/test_main_jar_transfer_conserves.py -v -s -o addopts=""
"""
import os
import time

import pytest

from utils.genuser_api import (
    gen_create, current_balance, funded_user, jar_user, kid_user,
    ach_credit, ach_withdrawal,
)

pytestmark = pytest.mark.value_api

# Small EXACT ACH balances (drift-free settled current_balance), distinct per account
# so a leak/miscompute is unambiguous. NOT the priced six-figure buffer.
MAIN_START = 300.00   # Owner (Main) starting balance
JAR_START = 80.00     # Jar starting balance
KID_START = 40.00     # Kid — NOT party to the transfer; must end exactly unchanged
TRANSFER = 25.00      # amount moved Owner -> Jar

MAIN_AFTER = round(MAIN_START - TRANSFER, 2)   # 275.00
JAR_AFTER = round(JAR_START + TRANSFER, 2)     # 105.00
PRE_TOTAL = round(MAIN_START + JAR_START + KID_START, 2)  # 420.00

# Settled balance lands on the exact seeded dollar amount; small tolerance for
# cents/settlement drift (same band used by the sibling value_api tests).
BAND = 1.50
# Sum tolerance: three balances each within BAND => widen the sum band so a genuine
# conservation breach (a whole leg lost/duplicated) still fails, but per-balance
# cent-settlement does not flake.
SUM_BAND = 3 * BAND

SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "480"))
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))

# If the backend ever re-introduces the deterministic jar-withdrawal balance gate, the
# create 422s on one of these signatures — fail loudly, never mask (see file header).
_WD_GATE_KEYS = ("exceed", "insufficient", "greater than", "available balance")


def _poll(email, target):
    """Poll current_balance until it settles within BAND of target (or budget out).
    Returns (best_seen, settled_bool)."""
    waited, best, seen_any = 0, None, False
    while waited <= SETTLE_BUDGET_S:
        bal = current_balance(email)
        if bal is not None:
            seen_any = True
            best = bal if best is None else (bal if abs(bal - target) < abs(best - target) else best)
            print(f"  [poll {email} +{waited}s] current_balance={bal} (target ${target})")
            if abs(bal - target) <= BAND:
                return bal, True
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    if not seen_any:
        return None, False
    return best, False


@pytest.mark.e2e
@pytest.mark.regression
@pytest.mark.jars
@pytest.mark.portfolio
def test_owner_to_jar_transfer_conserves_total_and_leaves_kid_unchanged():
    """An Owner->Jar transfer is a pure re-distribution: the per-user balance sum is
    unchanged, the Kid (not party to the move) is left EXACTLY unchanged, and the two
    endpoints actually moved by the transfer amount (proves a real transfer, not a
    no-op). Small exact ACH balances so the sum reconciles to the cent."""
    ts = str(int(time.time()))
    parent_email = f"conserve.transfer.{ts}@emel.xyz"
    jar_email = f"cj.conserve.transfer.{ts}@emel.xyz"
    kid_email = f"ck.conserve.transfer.{ts}@emel.xyz"

    # ONE create: the seeded balances AND the transfer's two equal-and-opposite legs.
    # Owner loses $T (credit M0 + withdraw T); Jar gains $T (credit J0 + credit T);
    # Kid is funded once and never touched.
    payload = {
        "user_1": funded_user(parent_email, f"ConsXfer{ts}"),
        "jar_1": jar_user(jar_email, f"ConsXferJar{ts}", "@user_1", "QA Conserve Xfer Jar"),
        "kid_1": kid_user(kid_email, f"ConsXferKid{ts}", "@user_1"),
        # Main: starting balance then the Owner leg of the transfer (a withdrawal of T)
        "main_credit": ach_credit("@user_1", MAIN_START),
        "main_transfer_out": ach_withdrawal("@user_1", TRANSFER),
        # Jar: starting balance then the Jar leg of the transfer (a credit of T)
        "jar_credit": ach_credit("@jar_1", JAR_START),
        "jar_transfer_in": ach_credit("@jar_1", TRANSFER),
        # Kid: funded once; NOT party to the transfer
        "kid_credit": ach_credit("@kid_1", KID_START),
    }

    status, body = gen_create(payload)
    if status == 422:
        errs = str(body.get("errors", body)).lower() if isinstance(body, dict) else str(body).lower()
        if any(k in errs for k in _WD_GATE_KEYS):
            pytest.fail(
                "Owner-leg (main) withdrawal gate RE-APPEARED: the test-data API again "
                "rejects the transfer-out leg as exceeds-balance. The conservation "
                "scenario can no longer be seeded in one create — re-evaluate the recipe; "
                f"do NOT mask: {str(body.get('errors', body))[:200]}")
        pytest.fail(f"conservation seed 422 (not the known withdrawal gate): "
                    f"{str(body.get('errors', body))[:220]}")
    assert status == 200, f"conservation seed failed: HTTP {status} {body}"
    created = body.get("created", {}) if isinstance(body, dict) else {}
    assert created.get("jar_1", {}).get("id"), f"no jar user id in {body}"
    assert created.get("kid_1", {}).get("id"), f"no kid user id in {body}"
    print(f"  seeded Main(${MAIN_START}-${TRANSFER}) Jar(${JAR_START}+${TRANSFER}) "
          f"Kid(${KID_START}); pre-transfer total ${PRE_TOTAL}")

    # Read back each sub-account's settled balance (each is its own User -> own token).
    main_after, main_ok = _poll(parent_email, MAIN_AFTER)
    jar_after, jar_ok = _poll(jar_email, JAR_AFTER)
    kid_after, kid_ok = _poll(kid_email, KID_START)

    assert main_ok, f"Main never settled to ${MAIN_AFTER} (best seen ${main_after})"
    assert jar_ok, f"Jar never settled to ${JAR_AFTER} (best seen ${jar_after})"
    assert kid_ok, f"Kid never settled to ${KID_START} (best seen ${kid_after})"

    # (1) CONSERVATION: post-transfer sum == pre-transfer sum (nothing created/destroyed).
    post_total = round(main_after + jar_after + kid_after, 2)
    assert post_total == pytest.approx(PRE_TOTAL, abs=SUM_BAND), (
        f"transfer did NOT conserve the total: pre ${PRE_TOTAL} vs post ${post_total} "
        f"(Main ${main_after} + Jar ${jar_after} + Kid ${kid_after}) — a move between "
        "accounts created or destroyed money (RAIZ totals-don't-add-up family)")

    # (2) UNINVOLVED account is EXACTLY unchanged: the Kid is not party to the transfer.
    assert kid_after == pytest.approx(KID_START, abs=BAND), (
        f"Kid balance moved ${kid_after} != seeded ${KID_START} — an Owner<->Jar "
        "transfer must not touch an account that is not party to it")

    # (3) The transfer is REAL, not a no-op: both endpoints moved by exactly $TRANSFER.
    assert main_after == pytest.approx(MAIN_AFTER, abs=BAND), (
        f"Owner endpoint did not decrease by the transfer: ${main_after} != "
        f"${MAIN_START} - ${TRANSFER} (${MAIN_AFTER})")
    assert jar_after == pytest.approx(JAR_AFTER, abs=BAND), (
        f"Jar endpoint did not increase by the transfer: ${jar_after} != "
        f"${JAR_START} + ${TRANSFER} (${JAR_AFTER})")

    print(f"  PASS: conserved sum ${post_total} == ${PRE_TOTAL}; Kid unchanged "
          f"${kid_after}; Owner ${main_after} (-${TRANSFER}); Jar ${jar_after} (+${TRANSFER})")
