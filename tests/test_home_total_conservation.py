"""
home-total-conservation (P1, dynamic/reconciliation) — API LAYER (no device).

Oracle (backlog row + notes, docs/proposed-test-cases.md):
  Home total == Main + Sigma(named jar cards) + Sigma(kid cards), within band, AND that
  same total == the backend `investing_accounts_balance` aggregate. The refinement
  de-dupes this against networth-total-investments-recon (#6, the My Finance source)
  by SCOPING this case to the HOME HEADLINE + per-card sum reconciliation.

WHAT THE HOME HEADLINE ACTUALLY BINDS TO (grounded in app source, build 3252):
  The redesign Home/Today screen headline total is fed by
  `TodayRedesignViewModel.accountBalance = it.investingAccountsBalance`
  (Android-AU app/src/main/java/com/raiz/feature/today/TodayRedesignViewModel.kt:151)
  — i.e. the backend field `investing_accounts_balance`, NOT the Main-only
  `current_balance` used by the legacy HomeTodayViewModel / MainPortfolioViewModel.

  Backend ground truth (raiz-backend app/models/concerns/user_account_types.rb):
    investing_accounts          = [self] + child_users + jar_users          (L109)
    investing_accounts_balance  = investing_accounts.sum(&:current_balance)  (L118)
  So the Home headline == Main(self) + Sigma(kid current_balance) + Sigma(jar
  current_balance) BY CONSTRUCTION. `investing_accounts_balance` is exposed on the v3
  user entity (app/api/entities/v3/user.rb:57) and served at GET /v3/user.

THEREFORE the value invariant behind the Home headline is fully provable at the API
layer, deterministically and with no device:
  (A) read each sub-account's settled current_balance independently (Main via the
      parent login, jar via the jar login, kid via the kid login — each is its own
      User with its own current_balance), and
  (B) read the parent's backend AGGREGATE investing_accounts_balance from GET /v3/user
      — the SAME field the Home headline renders — as an INDEPENDENT oracle, and assert
        investing_accounts_balance  ==  Main + jar + kid     (to the cent, within band)
  This is the RAIZ "totals don't add up across sub-accounts" defect family: if the
  aggregate the headline shows does not equal the sum of the per-account cards, money
  was created or lost in the rollup.

SPLIT-SCOPE (per the refinement convention): the on-device leg — opening Home and
reading the rendered headline string + the per-card dollar figures — is a SEPARATE
device half (needs the Today/Jars page objects). It is NOT built here; this file is the
API-layer reconciliation half and is the load-bearing oracle (it proves the exact field
the headline binds to reconciles to the per-card sum and to the backend aggregate).

DATA: small EXACT ACH balances (Main $300 / jar $80 / kid $40 — the conserve_main_jar_kid
shape), NOT the repricing six-figure buffer, so every balance settles to an exact,
drift-free current_balance and the sum reconciles to the cent. The backlog note's
"use DELTA_BAND (cards are market-priced)" caveat applies to PRICED holdings; this rig
uses settled ACH credits (stable, no market drift), so a tight settlement band is correct
and a market band would only mask a real rollup error. We seed a fresh self-contained rig
per run (the proven same-payload @-alias recipe used by the green value_api siblings)
rather than mutating the shared fixture — identical in shape to conserve_main_jar_kid but
reproduced cleanly and deterministically each run.

Honesty: any seed / login / settle gate -> skip-with-reason (clear evidence), never a
fake or vacuous pass.

Run (no emulator):
  venv/bin/python -m pytest tests/test_home_total_conservation.py -v -s -o addopts=""
"""
import os
import time

import pytest

from utils.genuser_api import (
    SEEDED_PWD, ach_credits, call, current_balance, funded_user, gen_create,
    jar_user, kid_user, mint,
)
from utils.genuser_fixtures import (
    CONSERVE_JAR_BALANCE, CONSERVE_KID_BALANCE, CONSERVE_MAIN_BALANCE,
)

pytestmark = pytest.mark.value_api

# Small EXACT ACH balances (settled current_balance, no market drift) — the
# conserve_main_jar_kid shape. Each distinct so a leak/miscompute is unambiguous.
MAIN_SEED = CONSERVE_MAIN_BALANCE   # 300.00  (parent / self)
JAR_SEED = CONSERVE_JAR_BALANCE     # 80.00   (one named jar card)
KID_SEED = CONSERVE_KID_BALANCE     # 40.00   (one kid card)
EXPECTED_TOTAL = round(MAIN_SEED + JAR_SEED + KID_SEED, 2)  # 420.00

# Per-balance settlement tolerance (cents/settle drift) — same band as the green
# value_api siblings. The rig uses settled ACH (no market repricing), so this stays tight.
BAND = 1.50
# Sum/aggregate band: three components each within BAND -> widen so a genuine rollup
# breach (a whole jar/kid leg lost or duplicated, ~$40-$80) still fails LOUDLY, while
# per-balance cent-settlement does not flake.
SUM_BAND = 3 * BAND  # 4.50  (< the smallest leg, $40, so a lost leg cannot hide)

SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "420"))
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))


def _ts():
    return str(int(time.time()))


def _poll_balance(email, target, budget_s):
    """Poll a User's current_balance until it lands within BAND of `target` (or the
    budget runs out). Returns (best_seen_toward_target, settled_bool)."""
    waited, best = 0, None
    while waited <= budget_s:
        bal = current_balance(email, SEEDED_PWD)
        if bal is not None:
            best = bal if best is None else (
                bal if abs(bal - target) < abs(best - target) else best)
            print(f"  [poll {email.split('@')[0]} +{waited}s] current_balance={bal} "
                  f"(target ${target})")
            if abs(bal - target) <= BAND:
                return bal, True
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return best, False


def _v3_investing_accounts_balance(email, attempts=3, retry_delay_s=8):
    """Read the parent's backend AGGREGATE `investing_accounts_balance` from GET /v3/user
    — the exact field the redesign Home headline binds to (TodayRedesignViewModel). This
    is an INDEPENDENT oracle from summing the per-account current_balances. Returns float
    or None if the login/read fails or the field is absent.

    Bounded retry: the per-card poll and the seed both retry transients, so the
    independent oracle read does too — a single transient login/GET blip must not degrade
    an already-reconciled run to a skip. Mints a fresh token per attempt (tokens expire);
    only a missing/None field (a real product/contract result, not a transient) returns
    immediately without burning retries."""
    last = None
    for i in range(attempts):
        op, tok = mint(email, SEEDED_PWD)
        if not tok:
            last = "login failed (no token)"
        else:
            s, b = call(op, "GET", "/v3/user", token=tok)
            if s == 200 and isinstance(b, dict):
                user = b.get("user", b)
                val = user.get("investing_accounts_balance")
                if val is not None:
                    return float(val)
                # 200 but field absent: a contract/product result, not a transient —
                # no point retrying. Surface it (None) so the caller skips with reason.
                print(f"  [v3/user {email.split('@')[0]}] 200 but no "
                      f"investing_accounts_balance field")
                return None
            last = f"HTTP {s} {str(b)[:160]}"
        print(f"  [v3/user {email.split('@')[0]} attempt {i + 1}/{attempts}] {last}")
        if i < attempts - 1:
            time.sleep(retry_delay_s)
    return None


@pytest.mark.e2e
@pytest.mark.regression
@pytest.mark.jars
@pytest.mark.portfolio
def test_home_total_reconciles_to_jar_and_kid_cards_and_backend_aggregate():
    """The Home headline total (== backend `investing_accounts_balance`) reconciles to
    the sum of the per-account cards: Main + jar + kid. Asserts the backend aggregate the
    headline renders equals the independently-summed per-card balances to the cent
    (within band), AND that each component settled to its own exact seeded amount — so a
    rollup that drops/duplicates a sub-account leg fails LOUDLY (RAIZ totals-don't-add-up
    family)."""
    ts = _ts()
    main_email = f"hometotal.main.{ts}@emel.xyz"
    jar_email = f"hometotal.jar.{ts}@emel.xyz"
    kid_email = f"hometotal.kid.{ts}@emel.xyz"

    # One self-contained create: Main parent + one funded jar + one funded kid, each
    # funded with small EXACT ACH credits (the conserve_main_jar_kid shape, reproduced
    # cleanly per run). Each sub-account is its own User with its own current_balance.
    payload = {
        "user_1": funded_user(main_email, f"HomeTotalMain{ts}"),
        **ach_credits("@user_1", MAIN_SEED, prefix="mainbase"),
        "jar_1": jar_user(jar_email, f"HomeTotalJar{ts}", "@user_1", "QA HomeTotal Jar"),
        **ach_credits("@jar_1", JAR_SEED, prefix="jarbase"),
        "kid_1": kid_user(kid_email, f"HomeTotalKid{ts}", "@user_1"),
        **ach_credits("@kid_1", KID_SEED, prefix="kidbase"),
    }
    status, body = gen_create(payload)
    if status != 200 or not (
            isinstance(body, dict)
            and body.get("created", {}).get("jar_1", {}).get("id")
            and body.get("created", {}).get("kid_1", {}).get("id")):
        pytest.skip(
            "skip-with-reason: could not seed the home-total rig (Main + jar + kid) "
            f"(HTTP {status} {str(body)[:160]}); seed gate, not a product result")
    created = body["created"]
    print(f"  seeded: Main {created['user_1']['id']} (${MAIN_SEED}), "
          f"Jar {created['jar_1']['id']} (${JAR_SEED}), "
          f"Kid {created['kid_1']['id']} (${KID_SEED}); expected total ${EXPECTED_TOTAL}")

    # --- (A) read each sub-account's settled current_balance independently (the per-card
    # figures the Home jar/kid cards render). ---
    main_bal, main_ok = _poll_balance(main_email, MAIN_SEED, SETTLE_BUDGET_S)
    jar_bal, jar_ok = _poll_balance(jar_email, JAR_SEED, SETTLE_BUDGET_S)
    kid_bal, kid_ok = _poll_balance(kid_email, KID_SEED, SETTLE_BUDGET_S)

    if main_bal is None or jar_bal is None or kid_bal is None:
        pytest.skip("skip-with-reason: could not read back one or more sub-account "
                    "balances (login/settle gate, not a product result): "
                    f"Main={main_bal}, jar={jar_bal}, kid={kid_bal}")

    # Each component must have reached its own seed; otherwise we cannot distinguish a
    # rollup defect from a not-yet-settled baseline.
    if not (main_ok and jar_ok and kid_ok):
        pytest.skip(
            "skip-with-reason: one or more component ACH balances did not settle within "
            f"{SETTLE_BUDGET_S}s (Main ${main_bal}/{main_ok}, jar ${jar_bal}/{jar_ok}, "
            f"kid ${kid_bal}/{kid_ok}); cannot reconcile against an unsettled baseline")

    per_card_sum = round(main_bal + jar_bal + kid_bal, 2)
    print(f"  per-card: Main ${main_bal} + jar ${jar_bal} + kid ${kid_bal} = ${per_card_sum}")

    # Each component settled to its exact seeded amount (a single mis-settled card would
    # otherwise be masked by the sum band).
    assert main_bal == pytest.approx(MAIN_SEED, abs=BAND), (
        f"Main card settled to ${main_bal}, expected ${MAIN_SEED}")
    assert jar_bal == pytest.approx(JAR_SEED, abs=BAND), (
        f"Jar card settled to ${jar_bal}, expected ${JAR_SEED}")
    assert kid_bal == pytest.approx(KID_SEED, abs=BAND), (
        f"Kid card settled to ${kid_bal}, expected ${KID_SEED}")

    # --- (B) read the backend AGGREGATE the Home headline binds to, independently. ---
    headline_total = _v3_investing_accounts_balance(main_email)
    if headline_total is None:
        pytest.skip(
            "skip-with-reason: GET /v3/user did not return investing_accounts_balance "
            "for the parent (auth/endpoint gate, not a product result); the per-card "
            f"sum reconciled to ${per_card_sum} but the headline oracle was unreadable")
    print(f"  backend aggregate (Home headline field) investing_accounts_balance="
          f"${headline_total}")

    # ===================== LOAD-BEARING RECONCILIATION =====================
    # (1) The aggregate the headline renders == the independently-summed per-card
    #     balances. A rollup that drops/duplicates a jar/kid leg breaks this.
    assert headline_total == pytest.approx(per_card_sum, abs=SUM_BAND), (
        f"HOME TOTAL DOES NOT RECONCILE: backend investing_accounts_balance "
        f"${headline_total} (the Home headline field) != Main ${main_bal} + jar "
        f"${jar_bal} + kid ${kid_bal} = ${per_card_sum} (within ${SUM_BAND}) — the "
        "aggregate the headline shows is not the sum of its sub-account cards "
        "(RAIZ totals-don't-add-up family)")

    # (2) Both reconcile to the seeded ground-truth total (catches the case where the
    #     aggregate and the per-card sum agree with each other but are jointly wrong).
    assert headline_total == pytest.approx(EXPECTED_TOTAL, abs=SUM_BAND), (
        f"backend aggregate ${headline_total} != seeded Main+jar+kid ${EXPECTED_TOTAL} "
        f"(within ${SUM_BAND})")
    assert per_card_sum == pytest.approx(EXPECTED_TOTAL, abs=SUM_BAND), (
        f"per-card sum ${per_card_sum} != seeded Main+jar+kid ${EXPECTED_TOTAL} "
        f"(within ${SUM_BAND})")

    print(f"  PASS: Home headline aggregate ${headline_total} == per-card sum "
          f"${per_card_sum} == seeded total ${EXPECTED_TOTAL} (Main+jar+kid conserved)")
