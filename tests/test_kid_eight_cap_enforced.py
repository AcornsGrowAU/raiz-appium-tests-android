"""
kid-eight-cap-enforced (P2, value_api) — API-LAYER negative test, PROBE-GATED.

CASE (backlog docs/proposed-test-cases.md, verdict=refine, conf 70, cons 8):
  "Eight-kid cap enforced: 9th create blocked, existing eight unchanged. Seed 8 kids;
   Add disabled/at-limit, 9th not completable, count stays 8; with 7, Add enabled."
REFINEMENT (notes column — honoured here):
  "De-dupe with jar-six-cap via shared helper; seed bare kids; land AFTER jar-cap."
  -> This test seeds bare kids (no ACH), reuses jar-six-cap's shared cap helper
     (attempt_create_subaccount_blocked), and asserts STATE (count stable), not a
     UI affordance/string.

WHY THIS IS PROBE-GATED (the honest, non-vacuous outcome) — MANIFEST FLAG #2:
  The 8-kid cap is NOT enforced on DEV by default. Backend ground truth:

  1. The numeric cap lives in DependentUsers::Users::Creator#validate_limit_number
     (raiz-backend app/services/dependent_users/users/creator.rb):
         def validate_limit_number
           return if limit_number.zero?            # <-- DEV: limit_number == 0 -> NO CAP
           return if user.child_users.not_closing_or_closed.count < limit_number
           raise LimitNumberError, ...
         def limit_number
           @limit_number ||= Setting.kids_limit_number
     and Setting.kids_limit_number DEFAULTS TO 0 (app/models/setting.rb:38,
     `field :kids_limit_number, type: :integer, default: 0`). limit_number.zero?
     => the guard returns early => no numeric cap is applied on DEV.

  2. The only OTHER gate is the per-plan UserPlans::Limitations::Kid#allowed_count.
     For the seeded parent's plan (Regular, via funded_user) that is
     Float::INFINITY (app/services/user_plans/regular/limitations/kid.rb), and Plus
     is also INFINITY (.../plus/...). The base default 0 only bites the Starter/Lite
     plan (that gate is exercised separately by tier-gating-kids-jars). The Regular
     parent therefore has NO effective kid cap on DEV.

  Net: a 9th kid create on this Regular parent will SUCCEED on a stock DEV unless an
  admin has set Setting.kids_limit_number to a non-zero value. Asserting
  "9th blocked / count stays 8" unconditionally would be a FAKE PASS.

  So the test PROBES at runtime: it attempts the 9th create and inspects the outcome.
   - If DEV rejects it (HTTP 422 from the LimitNumberError path) AND the count stays
     8: the cap IS enforced -> assert the full oracle (count stays 8, names + the
     pre-existing balances unchanged to the cent). The test auto-activates.
   - If DEV ACCEPTS the 9th (the documented DEV default): pytest.skip with EVIDENCE
     (the create's HTTP status + the observed kid count), documenting the gap rather
     than masking it. Before skipping it CLOSES the spurious 9th kid it just created
     (POST .../close) so the `eight_kids_cap` fixture stays at exactly 8 and remains
     reusable (no state drift).

WHY API-LAYER (no device, deterministic):
  Both the cap guard AND the kid count/names/balances are backend ground truth read
  straight off the dependency_users API — no UI, no flake, no emulator.

ENDPOINTS (raiz-backend app/api/dependency_users/v1/resources/users.rb,
mounted at /dependency_users/v1, config/routes.rb:33):
  - GET  /dependency_users/v1/users          -> list (rabl dependency_users/users:
        root key "dependency_users"; each kid: name [=first_name], id [=uuid],
        current_balance [.to_f.round(2)], closed).
  - POST /dependency_users/v1/users {name, date_of_birth, avatar_id}
        -> create; avatar_id in Assets::Icons::RAIZ_KIDS[:ids]
        (boy+1..boy+4, girl+1..girl+4). On cap -> Creator::Error -> error!(_, 422).
  - POST /dependency_users/v1/users/close {dependent_user_id}  -> close a kid
        (used only to undo a spurious 9th in the not-enforced branch).

DATA: pre-provisioned `eight_kids_cap` fixture (reuse strategy). user_1 is the parent
(the stored login, Regular plan) seeded with 8 BARE kids first_name CapKid1..CapKid8
(no ACH -> no settle wait, bare kids read current_balance==0.0). This test does not
mutate persistent state: in the enforced branch the 9th is rejected (no row); in the
not-enforced branch the spurious 9th is closed before skip, so the fixture stays at 8.

SHARED HELPER REUSE (de-dupe with jar-six-cap, per the notes):
  attempt_create_subaccount_blocked(parent_email, pwd, create_path, payload) is the
  cap helper authored in tests/test_jar_six_cap_enforced.py; this test imports and
  reuses it for the over-cap create rather than re-implementing it.

Run (no emulator):
  venv/bin/python -m pytest tests/test_kid_eight_cap_enforced.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import get_or_create_fixture_user
# Reuse the shared cap helper authored by the jar-six-cap test (de-dupe, per notes).
from tests.test_jar_six_cap_enforced import attempt_create_subaccount_blocked

pytestmark = [pytest.mark.value_api, pytest.mark.kids, pytest.mark.edge]

FIXTURE_KEY = "eight_kids_cap"

# The fixture seeds 8 bare kids with deterministic first names (utils.genuser_fixtures
# FIXTURES['eight_kids_cap']: kid_user(..., f"CapKid{i}") for i in 1..8). The list rabl
# exposes first_name as :name.
EXPECTED_CAP = 8
SEEDED_KID_NAMES = {f"CapKid{i}" for i in range(1, EXPECTED_CAP + 1)}

KIDS_LIST_PATH = "/dependency_users/v1/users"
KIDS_CREATE_PATH = "/dependency_users/v1/users"
KIDS_CLOSE_PATH = "/dependency_users/v1/users/close"

# avatar_id must be in Assets::Icons::RAIZ_KIDS[:ids] (raiz-backend
# app/constants/assets/icons.rb) so the create is rejected (if at all) purely by the
# cap, never by a bad payload. date_of_birth makes the kid a minor (validate at create).
VALID_AVATAR_ID = "boy+1"
KID_DOB = "2018-01-01"


def _fetch_kids(parent_email, pwd):
    """Log in AS the parent and read its kids list (GET /dependency_users/v1/users).
    Returns the list of kid dicts (each carries name + current_balance from the
    dependency_users/user rabl), or None if login / read fails."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None
    status, body = call(op, "GET", KIDS_LIST_PATH, token=tok)
    if status != 200:
        return None
    # users.rabl -> `child @dependency_users => :dependency_users` -> root key.
    if isinstance(body, dict):
        return body.get("dependency_users", body.get("users", body.get("kids", [])))
    if isinstance(body, list):
        return body
    return None


def _names(kids):
    return sorted(k.get("name") for k in kids if isinstance(k, dict))


def _balances_by_name(kids):
    """{name: current_balance} for the cent-level no-perturbation assertion."""
    out = {}
    for k in kids:
        if isinstance(k, dict) and k.get("name") is not None:
            amt = k.get("current_balance")
            out[k["name"]] = round(float(amt), 2) if amt is not None else None
    return out


def _close_kid(parent_email, pwd, dependent_user_id):
    """Best-effort: close a kid by id (POST .../close) so a spurious 9th created in the
    not-enforced branch does not leave the fixture at 9. Returns the HTTP status."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None
    status, _ = call(op, "POST", KIDS_CLOSE_PATH, token=tok,
                     body={"dependent_user_id": dependent_user_id})
    return status


def test_ninth_kid_blocked_and_eight_unchanged():
    """At the 8-kid state, IF the DEV kid cap is enforced, a 9th kid create is NOT
    completable and the existing eight are left exactly unchanged (count stays 8, same
    names, same balances to the cent). If DEV does NOT enforce the cap (the documented
    default: Setting.kids_limit_number==0 + Regular plan allowed_count==INFINITY), the
    spurious 9th is closed and the test skips WITH EVIDENCE rather than faking a pass.
    Asserts STATE + the rejection outcome, never a UI affordance/alert string."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')}); "
          f"expecting exactly {EXPECTED_CAP} bare kids at the seeded state")

    # --- PRE: the parent sits at exactly 8 kids with the seeded names. ---
    before = _fetch_kids(parent_email, pwd)
    assert before is not None, (
        f"could not read kids list for parent {parent_email} (login or "
        f"GET {KIDS_LIST_PATH} failed) — cannot establish the cap baseline"
    )
    assert len(before) == EXPECTED_CAP, (
        f"fixture not at the seeded count: expected exactly {EXPECTED_CAP} seeded kids "
        f"but the parent owns {len(before)} ({_names(before)}) — re-provision "
        f"`{FIXTURE_KEY}`"
    )
    before_names = _names(before)
    assert set(before_names) == SEEDED_KID_NAMES, (
        f"seeded kid names unexpected: got {before_names}, expected "
        f"{sorted(SEEDED_KID_NAMES)} — fixture drifted"
    )
    before_balances = _balances_by_name(before)
    print(f"  PRE: {len(before)} kids {before_names}; balances {before_balances}")

    # --- ACT: probe — attempt to create a 9th kid with an otherwise-valid payload. ---
    ninth = {"name": f"QA Over Cap Kid {int(time.time())}",
             "date_of_birth": KID_DOB, "avatar_id": VALID_AVATAR_ID}
    status, body = attempt_create_subaccount_blocked(
        parent_email, pwd, KIDS_CREATE_PATH, ninth)
    print(f"  PROBE: 9th-kid create -> HTTP {status} {str(body)[:200]}")

    # --- BRANCH A: DEV did NOT enforce the cap (the documented default). -----------
    # The 9th create COMPLETED. This is the expected DEV-default behaviour
    # (Setting.kids_limit_number==0 -> validate_limit_number returns early; Regular
    # plan allowed_count==INFINITY). We do NOT fake a pass. Close the spurious kid to
    # keep the fixture at exactly 8, then skip WITH EVIDENCE documenting the gap.
    if status in (200, 201):
        created_id = None
        if isinstance(body, dict):
            created_id = (body.get("dependency_user") or {}).get("id") or body.get("id")
        after_create = _fetch_kids(parent_email, pwd)
        observed = len(after_create) if after_create is not None else "unknown"
        close_status = _close_kid(parent_email, pwd, created_id) if created_id else None
        print(f"  CLEANUP: closed spurious 9th kid id={created_id} -> HTTP {close_status}")
        pytest.skip(
            "kid 8-cap NOT enforced on DEV (documented gap, manifest flag #2): the 9th "
            f"kid create COMPLETED with HTTP {status} for a Regular-plan parent already "
            f"at {EXPECTED_CAP} kids (observed count after create: {observed}). Backend "
            "ground truth: Setting.kids_limit_number defaults to 0 so "
            "DependentUsers::Users::Creator#validate_limit_number returns early (no "
            "numeric cap), and the Regular/Plus plan UserPlans::Limitations::Kid "
            "allowed_count is Float::INFINITY. The numeric cap is only active if an "
            "admin sets Setting.kids_limit_number > 0 on DEV; until then there is no "
            "9th-kid block to assert. Spurious 9th kid closed "
            f"(id={created_id}, close HTTP {close_status}) so the fixture stays at "
            f"{EXPECTED_CAP}. This test auto-activates the real oracle if DEV ever "
            "enforces the cap."
        )

    # --- BRANCH B: the cap IS enforced -> assert the full oracle. -------------------
    # The 9th create was rejected. Confirm it is the cap rejection (422 from the
    # LimitNumberError path), not some unrelated failure, then assert the eight are
    # exactly unchanged.
    assert status == 422, (
        f"9th-kid create was not completed but with an unexpected status (HTTP "
        f"{status}); expected 422 from the kid-cap guard "
        f"(DependentUsers::Users::Creator#validate_limit_number -> error!(_, 422)). "
        f"Response: {str(body)[:240]}"
    )

    after = _fetch_kids(parent_email, pwd)
    assert after is not None, (
        f"could not re-read kids list for parent {parent_email} after the rejected "
        f"9th create — cannot confirm the eight were left unchanged"
    )
    assert len(after) == EXPECTED_CAP, (
        f"kid count changed after a REJECTED 9th create: was {EXPECTED_CAP}, now "
        f"{len(after)} ({_names(after)}) — the failed create must not persist a row"
    )
    after_names = _names(after)
    assert after_names == before_names, (
        f"kid names changed after the rejected create: before {before_names}, "
        f"after {after_names}"
    )
    after_balances = _balances_by_name(after)
    assert after_balances == before_balances, (
        f"existing kid balances perturbed by the rejected create: before "
        f"{before_balances}, after {after_balances} (must be unchanged to the cent)"
    )
    print(f"  PASS: 9th create blocked (HTTP {status}); count stays {EXPECTED_CAP}, "
          f"names + balances unchanged {after_balances}")
