"""
Route A (API) auth-CONTRACT tests using generated users — coverage the single
shared UI account can never provide. No emulator, no shared-account writes.

Characterised live (2026-06-22) against /v1/sessions + GET /v1/user:
  - closed / suspended / declined accounts ALL authenticate (201 + token) — account
    state does NOT gate the session endpoint.
  - Only the CLOSED state is reflected in GET /v1/user (closed_at set); suspended /
    declined are not distinguishable there (would need a gated action / admin surface).
  - wrong-password and unknown-email return an IDENTICAL 401 (no user enumeration).

FINDING for the auth team: closed/suspended/declined users receive a valid session
token. If the product intends those states to be blocked at login, that's a gap; if
the block is post-login (app shows a reactivate/closed screen), these tests pin the
current contract so a regression is caught.

Run:  venv/bin/python -m pytest tests/test_auth_states_api.py -v -s -o addopts=""
"""
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.value_api

API = "https://api-dev.raizinvest.com.au"
UDID = "2204bb70-d6f7-4ccd-ad49-94d9b420feaa"
GEN_EMAIL = os.getenv("GEN_EMAIL", "anmol@raizinvest.com.au")
GEN_PWD = os.getenv("GEN_PWD", "TestDemo123")
SEEDED_PWD = "Pass1234"
RHO_MAX_RETRIES = int(os.getenv("RHO_MAX_RETRIES", "30"))


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _call(opener, method, path, token=None, body=None, timeout=40):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    for h, v in (("content-type", "application/json"), ("accept", "application/json"), ("x-version", "v1")):
        req.add_header(h, v)
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def _mint(email, pwd, budget_s=180):
    """Login -> (opener, token, status, body). Backoff through the rate-limit 400."""
    body = {"email": email, "password": pwd, "remember": False, "udid": UDID}
    waited, delay = 0, 8
    while True:
        op = _opener()
        status, payload = _call(op, "POST", "/v1/sessions", body=body)
        tok = payload.get("token") if isinstance(payload, dict) else None
        if status in (200, 201) and tok:
            return op, tok, status, payload
        # 400 == transient rate-limit; anything else (401 etc.) is a real answer
        if status != 400 or waited > budget_s:
            return op, None, status, payload
        time.sleep(delay)
        waited += delay
        delay = min(delay * 2, 60)


def _gen(payload):
    """Mint a fresh gen token per attempt; retry the rho_settled_at flap."""
    status, body = None, None
    for _ in range(RHO_MAX_RETRIES):
        op, tok, _, _ = _mint(GEN_EMAIL, GEN_PWD)
        if not tok:
            time.sleep(8)
            continue
        status, body = _call(op, "POST", "/internal/v1/test_data_generation",
                             token=tok, body={"payload": payload})
        errs = body.get("errors", []) if isinstance(body, dict) else []
        if status == 422 and any("rho_settled_at" in str(e) for e in errs):
            time.sleep(8)
            continue
        return status, body
    return status, body


def _user(traits, email, first, extra=None):
    attrs = {"email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
             "profile_data": {"first_name": first, "last_name": "QA",
                              "date_of_birth": "1990-01-01", "phone_number": "0412345678"}}
    if extra:
        attrs.update(extra)
    return {"model": "user", "traits": traits, "attributes": attrs}


def _closed_at(email):
    """Log in as the user and return closed_at from GET /v1/user (None if absent)."""
    op, tok, status, _ = _mint(email, SEEDED_PWD)
    assert tok, f"could not log in as {email}: HTTP {status}"
    s, body = _call(op, "GET", "/v1/user", token=tok)
    assert s == 200, f"GET /v1/user -> {s}"
    return (body.get("user", {}) if isinstance(body, dict) else {}).get("closed_at"), status


def _ts():
    return str(int(time.time()))


def test_closed_account_authenticates_and_reflects_closed_at():
    """A CLOSED account (a state the shared UI account can never reach) still
    authenticates, and the closed state is reflected in GET /v1/user.closed_at —
    while an otherwise-identical active account has closed_at == null."""
    ts = _ts()
    good_email = f"st.good.{ts}@emel.xyz"
    closed_email = f"st.closed.{ts}@emel.xyz"
    payload = {
        "good": _user(["with_user_profile", "verified"], good_email, "StGood"),
        "closed": _user(["closed", "with_user_profile", "verified"], closed_email, "StClosed",
                        extra={"closed_at": "2024-02-01"}),
    }
    status, body = _gen(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"

    good_closed_at, good_login = _closed_at(good_email)
    closed_closed_at, closed_login = _closed_at(closed_email)
    print(f"  good: login {good_login}, closed_at={good_closed_at!r}")
    print(f"  closed: login {closed_login}, closed_at={closed_closed_at!r}")
    # Pinned contract: both authenticate; only the closed account carries closed_at.
    assert good_login in (200, 201) and closed_login in (200, 201), "both states authenticate"
    assert good_closed_at is None, f"active account should have closed_at null, got {good_closed_at!r}"
    assert closed_closed_at, f"closed account should expose closed_at, got {closed_closed_at!r}"
    print("  PASS: closed state reachable and reflected (closed_at) vs active (null)")


def test_login_does_not_enumerate_users():
    """Security contract: a wrong password and an unknown email return the SAME 401
    body — the API must not reveal whether an email exists."""
    ts = _ts()
    good_email = f"st.enum.{ts}@emel.xyz"
    status, body = _gen({"good": _user(["with_user_profile", "verified"], good_email, "StEnum")})
    assert status == 200, f"create failed: HTTP {status} {body}"

    _, _, wrong_status, wrong_body = _mint(good_email, "WrongPass999", budget_s=60)
    _, _, unk_status, unk_body = _mint(f"nobody.{ts}@emel.xyz", "WrongPass999", budget_s=60)
    print(f"  wrong-password : {wrong_status} {wrong_body}")
    print(f"  unknown-email  : {unk_status} {unk_body}")
    assert wrong_status == 401 and unk_status == 401, "both must be 401"
    assert wrong_body == unk_body, "wrong-password and unknown-email must be indistinguishable (no enumeration)"
    print("  PASS: wrong-password and unknown-email are indistinguishable (no user enumeration)")
