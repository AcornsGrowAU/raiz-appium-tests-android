"""
jar-six-cap-enforced (P1, value_api) — API-LAYER negative test.

CASE (backlog docs/proposed-test-cases.md, verdict=keep, conf 86, cons 15):
  "Six-jar cap enforced: 7th create blocked, existing six unchanged. Seed 6 jars;
   Add disabled OR 7th rejected; count stays 6, six names/balances unchanged; with
   5, Add enabled."
REFINEMENT (notes column — honoured here):
  "Assert NOT-completable + count==6 (don't hard-code the at-limit affordance/string);
   seed bare jars to skip 6x ACH settle. Build the shared 'seed N sub-accounts,
   attempt N+1, assert blocked + count stable' helper here — kid-eight-cap reuses it."

WHY API-LAYER (no device, deterministic):
  The jar cap is enforced at the backend, not just hidden in the UI. The create
  service raises before any jar is persisted:

    raiz-backend app/services/jars/base_creator.rb#validate_limit_number
      return if user.jar_users.not_closing_or_closed.count < Setting.jars_limit_number
      raise Jars::Errors::Creator::LimitNumberError(...)   # -> HTTP 422

  A parent's jar_users is `has_many through: :jars` (app/models/user.rb), so the
  count the service guards is exactly the set the jars-list endpoint returns. The
  (cap+1)th POST /jars/v1/users therefore hits validate_limit_number and is rejected
  with a 422 via detailed_error! (app/api/v1/helpers/response.rb) — no row is created.
  LimitNumberError is a Jars::Errors::Creator::Error, rescued in
  app/api/jars/v1/resources/users.rb -> detailed_error! (default status 422,
  app/api/v1/helpers/response.rb).

  CAP VALUE — read live, NOT hard-coded:
    Setting.jars_limit_number's *source default* is 6 (app/models/setting.rb:113), but
    Setting is a DB-backed config field, and the DEV backend has it configured to a
    DIFFERENT value. As of 2026-06-24 GET /jars/v1/settings on DEV returns
    limit.value == 10. The original "six-jar" premise was WRONG against the live DEV
    config: a 7th jar create SUCCEEDS because 7 < 10 — that is correct product
    behaviour, NOT a defect. (The build that filed this RED simply saw the 7th create
    succeed and assumed a 6-cap.) This test is therefore CAP-RELATIVE: it reads the
    live cap, tops the parent up to EXACTLY the cap with bare jars, attempts the
    (cap+1)th create, and asserts THAT is rejected. The cap MECHANISM is genuinely
    enforced (validate_limit_number), so a (cap+1)th create that SUCCEEDS is a real
    defect, asserted loudly here (never masked as a skip).

  Unlike the KID cap (Setting.kids_limit_number default 0 == disabled on DEV, see
  the eight-kids-cap manifest flag), the JAR cap is a positive number and is
  genuinely enforced at whatever the live Setting.jars_limit_number is.

ORACLE — assert STATE + NOT-completable, not a UI affordance/string:
  0. Read the LIVE cap (GET /jars/v1/settings -> limit.value). Top the parent up to
     EXACTLY `cap` active jars by creating bare jars via POST /jars/v1/users (the
     fixture seeds only the source-default 6; the live DEV cap is higher). Track
     every jar this test created so it can be closed afterward.
  1. Pre:  GET /jars/v1/users -> exactly `cap` active jars, with known names/balances.
  2. Act:  POST /jars/v1/users {name, icon_id} for a (cap+1)th jar.
           Assert it is NOT completable (rejected, not 200/201). We assert on the
           outcome (no creation), NOT on a specific alert string or disabled-button
           affordance, per the refinement.
  3. Post: GET /jars/v1/users -> STILL exactly `cap` active jars; the SAME names; each
           jar's accumulated_amount unchanged to the cent (the rejected create did
           not perturb the existing ones).
  4. Cleanup: close every jar this test created (top-up jars + any over-cap jar that
     slipped through) so the fixture is restored to its 6 seeded jars and stays
     re-runnable.

DATA: the pre-provisioned `six_jars_cap` fixture (reuse strategy). user_1 is the
parent (the stored login) seeded with 6 BARE jars 'QA Cap Jar 1'..'QA Cap Jar 6'
(no ACH -> no settle wait). Because the live cap (10 on DEV) exceeds the 6 seeded
jars, the test creates the remaining bare jars at runtime to reach the cap, then
closes them in a `finally` so the fixture returns to its seeded baseline of 6. As a
SAFETY NET, if the over-cap create ever DOES succeed (a real cap-not-enforced defect),
the test also closes the jar it created so the parent is restored and the fixture
stays re-runnable (a prior version left an over-cap jar behind, which broke re-runs).

ROBUSTNESS NOTES (refinement: assert STATE, don't hard-code the cap):
  * The cap value is READ from the backend (GET /jars/v1/settings -> limit.value =
    Setting.jars_limit_number) rather than hard-coded, so a backend config change
    (e.g. DEV's 10 vs the source default 6) does not silently invert the verdict. We
    fall back to the source default of 6 only if that endpoint is unreadable (logged
    loudly).
  * The PRECONDITION counts only NON-closed jars (jars/show.rabl exposes `closed` =
    jar_user.closing_or_closed?). This matches the EXACT set the cap guard counts
    (`user.jar_users.not_closing_or_closed` in jars/base_creator.rb) -- the list
    endpoint returns ALL jar_users including closing/closed ones, so counting the raw
    list (as the prior version did) could read 7 after a leftover closure and mis-
    fail the precondition. Counting active jars aligns the test oracle with the
    backend's own cap arithmetic.

SHARED HELPERS (`attempt_create_subaccount_blocked` / `seed_then_cap` semantics):
  The "read N -> attempt N+1 -> assert blocked + count/values stable" logic lives in
  this file's module-level helpers so the kid-eight-cap test can import + reuse them.

Run (no emulator):
  venv/bin/python -m pytest tests/test_jar_six_cap_enforced.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import get_or_create_fixture_user

pytestmark = [pytest.mark.value_api, pytest.mark.jars, pytest.mark.edge]

FIXTURE_KEY = "six_jars_cap"

# The fixture seeds SEEDED_JAR_COUNT bare jars named deterministically (see
# utils.genuser_fixtures FIXTURES['six_jars_cap']: jar_user(..., f"QA Cap Jar {i}")
# for i in 1..6). FALLBACK_CAP is the backend source default (Setting.jars_limit_number
# default 6, app/models/setting.rb), used ONLY if the live GET /jars/v1/settings
# cap-read fails. The live cap (10 on DEV) is preferred at runtime and the test tops
# the parent up from SEEDED_JAR_COUNT to the live cap with runtime bare jars.
FALLBACK_CAP = 6
SEEDED_JAR_COUNT = 6
SEEDED_JAR_NAMES = {f"QA Cap Jar {i}" for i in range(1, SEEDED_JAR_COUNT + 1)}
# Bare top-up jars created at runtime to reach the live cap use this prefix so they
# are easy to distinguish from the seeded set and are all closed in cleanup.
TOPUP_NAME_PREFIX = "QA Topup Jar"

# A valid jar payload for the 7th create: backend requires a name + exactly one of
# {icon_id, file}. icon_id must be in Assets::Icons::JARS[:ids]
# (raiz-backend app/constants/assets/icons.rb): home car island money gift umbrella
# cat dog. So the create is REJECTED purely by the cap, not by a bad payload.
VALID_ICON_ID = "home"

# accumulated_amount is rounded to 2dp by jars/show.rabl; bare jars read back 0.0.
# Compare exactly (no settle drift on a zero-balance jar).


def _fetch_jars(parent_email, pwd):
    """Log in AS the parent and read its jars list (GET /jars/v1/users). Returns the
    list of jar dicts (each carries name + accumulated_amount from jars/show.rabl),
    or None if login / read fails."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None
    status, body = call(op, "GET", "/jars/v1/users", token=tok)
    if status != 200:
        return None
    # list.rabl is `child @jar_users => :jar_users` -> {"jar_users": [...]}.
    if isinstance(body, dict):
        return body.get("jar_users", body.get("jars", []))
    if isinstance(body, list):
        return body
    return None


def _read_live_cap(parent_email, pwd):
    """GET /jars/v1/settings -> the live Setting.jars_limit_number (limit.value).
    Returns the int cap, or None if unreadable (caller falls back to EXPECTED_CAP).
    Reading the cap from the backend keeps the oracle honest if the configured limit
    ever differs from the source default of 6, instead of hard-coding it."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None
    status, body = call(op, "GET", "/jars/v1/settings", token=tok)
    if status != 200 or not isinstance(body, dict):
        return None
    limit = body.get("limit")
    if isinstance(limit, dict) and limit.get("value") is not None:
        try:
            return int(limit["value"])
        except (TypeError, ValueError):
            return None
    return None


def _active_jars(jars):
    """The jars the backend cap actually counts: jars/show.rabl exposes `closed` =
    jar_user.closing_or_closed?, and the cap guard counts `not_closing_or_closed`.
    A jar missing the `closed` key (older payloads) is treated as active."""
    return [j for j in jars if isinstance(j, dict) and not j.get("closed", False)]


def _close_jar(parent_email, pwd, jar_user_id):
    """Best-effort cleanup: close (DELETE /jars/v1/users with jar_user_id) a jar that
    an over-cap create unexpectedly produced, so the fixture is restored to the cap
    and stays re-runnable. Returns (status, body) or (None, None) on login failure."""
    if not jar_user_id:
        return None, None
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None, None
    return call(op, "DELETE", "/jars/v1/users", token=tok,
                body={"jar_user_id": jar_user_id})


def _create_bare_jar(parent_email, pwd, name):
    """Create a single bare jar (POST /jars/v1/users {name, icon_id}) AS the parent.
    Returns (status, body). Used to top the parent up from the seeded count to the
    live cap so the (cap+1)th attempt actually exercises validate_limit_number."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None, None
    return call(op, "POST", "/jars/v1/users", token=tok,
                body={"name": name, "icon_id": VALID_ICON_ID})


def _names(jars):
    return sorted(j.get("name") for j in jars if isinstance(j, dict))


def _balances_by_name(jars):
    """{name: accumulated_amount} for the cent-level no-perturbation assertion."""
    out = {}
    for j in jars:
        if isinstance(j, dict) and j.get("name") is not None:
            amt = j.get("accumulated_amount")
            out[j["name"]] = round(float(amt), 2) if amt is not None else None
    return out


def attempt_create_subaccount_blocked(parent_email, pwd, create_path, payload):
    """SHARED cap helper (kid-eight-cap reuses this): log in AS the parent and POST a
    sub-account create that should be REJECTED by a cap. Returns (status, body). The
    caller asserts NOT-completable (status not in 200/201) — we do NOT match a
    specific alert string, only that the create did not complete.

    Raises AssertionError on login failure so a bad token never masks a missed cap."""
    op, tok = mint(parent_email, pwd)
    assert tok, f"could not log in as parent {parent_email} to attempt the over-cap create"
    return call(op, "POST", create_path, token=tok, body=payload)


def test_over_cap_jar_blocked_and_existing_unchanged():
    """At the live jar cap, a (cap+1)th jar create is NOT completable and the existing
    jars are left exactly unchanged (count stays at the cap, same names, same balances
    to the cent). CAP-RELATIVE: reads the live cap and tops the parent up to it (the
    fixture seeds only the source-default 6, but the live DEV cap is higher).
    Asserts STATE + the rejection outcome, never a UI affordance/alert string."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)

    # Cap value: prefer the LIVE backend setting over the hard-coded source default.
    # The DEV backend's Setting.jars_limit_number is 10 (source default is 6); reading
    # it live keeps the oracle honest instead of mis-failing a 7th create as a defect.
    live_cap = _read_live_cap(parent_email, pwd)
    cap = live_cap if live_cap is not None else FALLBACK_CAP
    if live_cap is None:
        print(f"  WARN: could not read live cap (GET /jars/v1/settings); falling back "
              f"to source default {FALLBACK_CAP}")
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')}); "
          f"live cap={cap}")

    # Track jars THIS test creates (top-up + any over-cap jar that slips through) so
    # the `finally` restores the fixture to its seeded baseline of 6.
    created_ids = []
    try:
        # --- TOP-UP: bring the parent up to EXACTLY the cap with bare jars. ---
        # The fixture seeds SEEDED_JAR_COUNT (6); the live cap is higher, so create
        # the remaining bare jars so the (cap+1)th attempt actually trips the guard.
        seeded_raw = _fetch_jars(parent_email, pwd)
        assert seeded_raw is not None, (
            f"could not read jars list for parent {parent_email} (login or "
            f"GET /jars/v1/users failed) — cannot establish the baseline"
        )
        seeded = _active_jars(seeded_raw)
        assert set(_names(seeded)) >= SEEDED_JAR_NAMES, (
            f"seeded jar names missing: got {_names(seeded)}, expected to include "
            f"{sorted(SEEDED_JAR_NAMES)} — re-provision `six_jars_cap`"
        )
        assert len(seeded) <= cap, (
            f"parent already has {len(seeded)} active jars (> cap {cap}) before top-up "
            f"({_names(seeded)}) — fixture drifted, re-provision `six_jars_cap`"
        )
        need = cap - len(seeded)
        print(f"  TOP-UP: {len(seeded)} active jars seeded; creating {need} bare jars "
              f"to reach the cap of {cap}")
        for i in range(need):
            name = f"{TOPUP_NAME_PREFIX} {int(time.time())}_{i}"
            tstatus, tbody = _create_bare_jar(parent_email, pwd, name)
            assert tstatus in (200, 201), (
                f"failed to create top-up jar {name} (HTTP {tstatus} {str(tbody)[:160]}) "
                f"— cannot reach the cap to test the (cap+1)th rejection"
            )
            if isinstance(tbody, dict) and tbody.get("id"):
                created_ids.append(tbody["id"])

        # --- PRE: the parent now sits at EXACTLY the cap. ---
        before_raw = _fetch_jars(parent_email, pwd)
        assert before_raw is not None, "could not re-read jars after top-up"
        before = _active_jars(before_raw)
        assert len(before) == cap, (
            f"after top-up the parent is not at the cap: expected {cap} active jars, "
            f"got {len(before)} ({_names(before)})"
        )
        before_names = _names(before)
        before_balances = _balances_by_name(before)
        print(f"  PRE: {len(before)} active jars (at cap); balances {before_balances}")

        # --- ACT: attempt to create a (cap+1)th jar with an otherwise-valid payload. ---
        over = {"name": f"QA Over Cap Jar {int(time.time())}", "icon_id": VALID_ICON_ID}
        status, body = attempt_create_subaccount_blocked(
            parent_email, pwd, "/jars/v1/users", over)
        print(f"  ACT: over-cap jar create -> HTTP {status} {str(body)[:200]}")

        # If the create UNEXPECTEDLY succeeded, capture its id so the `finally` closes
        # it too (jars/show.rabl exposes the uuid as `id`). Idempotency safety net.
        if status in (200, 201) and isinstance(body, dict) and body.get("id"):
            created_ids.append(body["id"])

        # --- ASSERT (1): the create is NOT completable. ---
        # Backend raises LimitNumberError -> detailed_error! -> 422 (we assert the
        # OUTCOME, not the alert string). A 2xx here means the jar cap was NOT
        # enforced at the live Setting.jars_limit_number: fail loudly with evidence.
        assert status not in (200, 201), (
            f"jar cap NOT enforced: the over-cap jar create COMPLETED (HTTP {status}) "
            f"for a parent already at the cap of {cap} jars — "
            f"jars/base_creator.rb#validate_limit_number (Setting.jars_limit_number) "
            f"did not reject it. Response: {str(body)[:240]}"
        )
        assert status == 422, (
            f"over-cap jar create was rejected but with an unexpected status "
            f"(HTTP {status}); expected 422 from the cap guard (detailed_error!). "
            f"Response: {str(body)[:240]}"
        )

        # --- ASSERT (2): the existing jars are EXACTLY unchanged. ---
        after_raw = _fetch_jars(parent_email, pwd)
        assert after_raw is not None, (
            f"could not re-read jars list for parent {parent_email} after the rejected "
            f"over-cap create — cannot confirm the existing jars were left unchanged"
        )
        after = _active_jars(after_raw)
        assert len(after) == cap, (
            f"active jar count changed after a REJECTED over-cap create: was {cap}, now "
            f"{len(after)} ({_names(after)}) — the failed create must not persist a row"
        )
        after_names = _names(after)
        assert after_names == before_names, (
            f"jar names changed after the rejected create: before {before_names}, "
            f"after {after_names}"
        )
        after_balances = _balances_by_name(after)
        assert after_balances == before_balances, (
            f"existing jar balances perturbed by the rejected create: before "
            f"{before_balances}, after {after_balances} (must be unchanged to the cent)"
        )
        print(f"  PASS: over-cap create blocked (HTTP {status}); count stays {cap}, "
              f"names + balances unchanged")
    finally:
        # IDEMPOTENCY: close every jar this test created (top-up jars + any over-cap
        # jar that slipped through) so the fixture is restored to its seeded 6 and the
        # next run's baseline holds. (A prior version left jars behind, breaking re-runs.)
        for jid in created_ids:
            cstatus, cbody = _close_jar(parent_email, pwd, jid)
            print(f"  CLEANUP: closed jar id={jid} -> HTTP {cstatus} {str(cbody)[:80]}")
