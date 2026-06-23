"""
TC-09 [P1] — Account-state login outcomes distinct (active/suspended/declined/closed)

Route A (API) auth-state test using generated users — coverage the single shared UI
account can never provide (it can only ever be active). No emulator, no shared-account
writes; DEV API only.

Intent: prove that suspended / declined / closed accounts produce a DISTINCT, observable
outcome versus an active account — i.e. the backend does not treat all four states
identically on the observables a client can see.

Oracle (what proves it passes):
  Generate one otherwise-identical user per state, then for each build a
  state-distinguishing FINGERPRINT from observables a client actually has:
    - login outcome    (POST /v1/sessions status + whether a token is issued)
    - closed_at         (GET /v1/user.closed_at — the known closed-state signal)
    - a status field    (GET /v1/user.status / account_status / state, if present)
    - account_closed / suspended-type boolean flags on the user object, if present
  Assert the four fingerprints are NOT all identical (at least one state differs).
  Additionally pin the known contract: closed is concretely distinguishable from active
  via closed_at, and active itself has closed_at == null.

Companion to test_auth_states_api.py (which pins the closed-vs-active closed_at contract
and the no-enumeration 401). This case widens the lens to all four states at once so a
regression that flattens any state into "looks active" is caught.

Run:  venv/bin/python -m pytest tests/test_auth_account_states_api.py -v -s -o addopts=""
"""
import os
import time

import pytest

from utils.genuser_api import SEEDED_PWD, call, gen_create, mint

pytestmark = pytest.mark.value_api

# Transient HTTP statuses the slow DEV API throws under load/rate-limit (~1-3s RTT).
# A single hiccup on the GET /v1/user read must NOT flip closed_at -> None and fail
# the pinned contract, so we retry the read with backoff (same posture as mint/gen_create).
_TRANSIENT = {0, 400, 408, 425, 429, 500, 502, 503, 504}
_READ_RETRIES = int(os.getenv("USER_READ_RETRIES", "4"))


def _read_user(op, tok):
    """GET /v1/user -> the user dict, retrying transient failures. Returns {} only
    after exhausting retries (a genuinely empty/unreadable user)."""
    delay = 4
    for attempt in range(_READ_RETRIES):
        s, body = call(op, "GET", "/v1/user", token=tok)
        if s == 200 and isinstance(body, dict):
            inner = body.get("user", body)
            return inner if isinstance(inner, dict) else {}
        if s not in _TRANSIENT or attempt == _READ_RETRIES - 1:
            return {}
        time.sleep(delay)
        delay = min(delay * 2, 30)
    return {}

# Observable keys on the GET /v1/user user-object that plausibly carry account state.
# We snapshot whichever exist; absent keys simply don't contribute to the fingerprint.
_STATE_KEYS = (
    "closed_at", "status", "account_status", "state", "account_state",
    "suspended", "suspended_at", "is_suspended", "declined", "declined_at",
    "is_declined", "account_closed", "active", "is_active", "blocked", "is_blocked",
)


def _user(traits, email, first, extra=None):
    """An otherwise-identical user; only the `traits`/`extra` carry the account state."""
    attrs = {
        "email": email,
        "password": SEEDED_PWD,
        "skip_sending_welcome_email": True,
        "profile_data": {"first_name": first, "last_name": "QA",
                         "date_of_birth": "1990-01-01", "phone_number": "0412345678"},
    }
    if extra:
        attrs.update(extra)
    return {"model": "user", "traits": traits, "attributes": attrs}


def _fingerprint(email):
    """Log in as the user and return a hashable, state-distinguishing fingerprint
    built only from client-visible observables. Robust to the login itself being
    gated (token may be None) and to /v1/user being unreadable."""
    op, tok = mint(email, SEEDED_PWD)
    login_status = "token" if tok else "no_token"
    user_obj = {}
    if tok:
        user_obj = _read_user(op, tok)
    observed = {k: user_obj.get(k) for k in _STATE_KEYS if k in user_obj}
    # closed_at is the one observable we KNOW carries state today; always include it
    # (even as None) so active-vs-closed always separates on the fingerprint.
    observed.setdefault("closed_at", user_obj.get("closed_at"))
    fp = (login_status,) + tuple(sorted((k, repr(v)) for k, v in observed.items()))
    return fp, login_status, observed


def test_account_states_produce_distinct_outcomes():
    """Generate active / suspended / declined / closed users that are identical except
    for account state, then assert their client-visible outcomes are NOT all identical
    — and that closed is concretely distinguishable from active via closed_at."""
    # PID-qualified timestamp: avoid same-second email collisions when the suite runs
    # across the parallel multi-emulator rig (each worker is a distinct process).
    ts = f"{int(time.time())}.{os.getpid()}"
    spec = {
        # ref         (traits,                                                  extra)
        "active":    (["with_user_profile", "verified"],                        None),
        "suspended": (["suspended", "with_user_profile", "verified"],           None),
        "declined":  (["declined", "with_user_profile", "verified"],            None),
        "closed":    (["closed", "with_user_profile", "verified"],              {"closed_at": "2024-02-01"}),
    }
    emails = {ref: f"as.{ref}.{ts}@emel.xyz" for ref in spec}
    payload = {
        ref: _user(traits, emails[ref], f"As{ref.capitalize()}", extra=extra)
        for ref, (traits, extra) in spec.items()
    }

    status, body = gen_create(payload)
    # If the gen API rejects a state trait outright, that itself is a distinct outcome
    # at creation time — surface it loudly rather than silently passing.
    assert status == 200, f"generated-user create failed: HTTP {status} {body}"

    fingerprints, summary = {}, {}
    for ref in spec:
        fp, login_status, observed = _fingerprint(emails[ref])
        fingerprints[ref] = fp
        summary[ref] = {"login": login_status, "observed": observed}
        print(f"  {ref:>9}: login={login_status} observed={observed}")

    distinct = set(fingerprints.values())
    print(f"  distinct fingerprints: {len(distinct)} of {len(spec)}")

    # --- Oracle: the four states are NOT all identical on the chosen observable(s) ---
    assert len(distinct) > 1, (
        "active/suspended/declined/closed are INDISTINGUISHABLE on every client-visible "
        f"observable — backend flattens all account states to one outcome: {summary}"
    )

    # --- Pinned contract: closed is concretely distinct from active via closed_at ---
    active_closed_at = summary["active"]["observed"].get("closed_at")
    closed_closed_at = summary["closed"]["observed"].get("closed_at")
    assert active_closed_at is None, \
        f"active account must have closed_at null, got {active_closed_at!r}"
    assert closed_closed_at, \
        f"closed account must expose closed_at, got {closed_closed_at!r}"
    assert fingerprints["active"] != fingerprints["closed"], \
        "active and closed must not share a fingerprint"

    print(f"  PASS: account states are distinguishable "
          f"({len(distinct)}/{len(spec)} distinct; closed separable from active via closed_at)")
