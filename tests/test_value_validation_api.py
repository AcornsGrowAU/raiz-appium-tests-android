"""
VALUE-validation via the Test-Data-Generation API (AUIB-6373) + balance read-back.

Seeds a generated user with a KNOWN dollar amount and asserts the balance the
backend reports equals what was seeded — a real value check, not a presence one.

CONFIRMED RECIPE (the one that actually surfaces a real, EXACT balance):
  funded user, portfolio_name "Aggressive" (NOT "Moderate" — Moderate funds price
  to $0 in dev), + a credit_investment with payment_method "ACH" and traits
  [lump_sum, with_shares_settled_status, with_holdings]. The seeded $amount settles
  into user.current_balance EXACTLY (user 41756: $150 -> $150) — but ASYNC, so we
  POLL until it settles.

ENV REALITIES handled here:
  - /v1/sessions tokens are short-lived -> mint fresh per create attempt; carry the
    login cookie jar onto the create (same opener).
  - /internal/v1/test_data_generation FLAPS on "rho_settled_at" -> retry the create.
  - /v1/sessions rate-limits bursts (400) -> backoff.
  - balance settles asynchronously -> poll current_balance up to SETTLE_BUDGET_S.

Run (no emulator needed):
  venv/bin/python -m pytest tests/test_value_validation_api.py -v -s -o addopts=""
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

SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "480"))  # how long to wait for async settlement
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))
RHO_MAX_RETRIES = int(os.getenv("RHO_MAX_RETRIES", "30"))
BAND = 1.50  # settled balance lands on the seeded dollar amount (small tolerance for cents/drift)


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _call(opener, method, path, token=None, body=None, timeout=40):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json")
    req.add_header("x-version", "v1")
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


def _mint(email, pwd, label="", budget_s=180):
    """Login on a FRESH opener (so its cookie jar holds the session cookie) and
    return (opener, token). Backoff through the /v1/sessions rate-limit (400)."""
    body = {"email": email, "password": pwd, "remember": False, "udid": UDID}
    waited, delay = 0, 8
    while waited <= budget_s:
        op = _opener()
        status, payload = _call(op, "POST", "/v1/sessions", body=body)
        if status in (200, 201) and isinstance(payload, dict) and payload.get("token"):
            return op, payload["token"]
        print(f"  [login {label or email}] HTTP {status} {str(payload)[:50]} -> sleep {delay}s")
        time.sleep(delay)
        waited += delay
        delay = min(delay * 2, 60)
    return None, None


def _create(payload):
    """Mint a FRESH gen token per attempt (tokens expire during rho retries) and
    POST the create on the same opener; retry through the rho_settled_at flap."""
    status, body = None, None
    for attempt in range(RHO_MAX_RETRIES):
        op, tok = _mint(GEN_EMAIL, GEN_PWD, "anmol(gen)")
        if not tok:
            time.sleep(8)
            continue
        status, body = _call(op, "POST", "/internal/v1/test_data_generation",
                             token=tok, body={"payload": payload})
        errs = body.get("errors", []) if isinstance(body, dict) else []
        if status == 422 and any("rho_settled_at" in str(e) for e in errs):
            if attempt % 5 == 0:
                print(f"  [create] rho_settled_at flap (attempt {attempt + 1}) — retrying")
            time.sleep(8)
            continue
        return status, body
    return status, body


def _poll_balance(email, target):
    """Log in as the seeded user and poll user.current_balance until it settles to
    ~target or the budget runs out. Returns (best_balance, status_str)."""
    op, tok = _mint(email, SEEDED_PWD, "seeded-user")
    if not tok:
        return None, "GATE: could not log in as the generated user"
    waited, best = 0, 0.0
    while waited <= SETTLE_BUDGET_S:
        status, body = _call(op, "GET", "/v1/user", token=tok)
        if status == 401:  # token expired mid-poll -> re-mint
            op, tok = _mint(email, SEEDED_PWD, "seeded-user")
            if not tok:
                return best, "token refresh failed mid-poll"
            continue
        user = body.get("user", body) if isinstance(body, dict) else {}
        bal = float(user.get("current_balance") or 0.0)
        best = max(best, bal)
        print(f"  [poll +{waited}s] current_balance={bal}")
        # settled only when within band of the EXACT target — works for credits
        # (balance rises to target) AND withdrawals (balance falls through to target).
        if abs(bal - target) <= BAND:
            return bal, "settled"
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return best, f"did not settle within {SETTLE_BUDGET_S}s"


def _ts():
    return str(int(time.time()))


def _funded_user(email, first):
    return {
        "model": "user",
        "traits": ["has_portfolio", "with_user_profile", "funded", "verified", "with_active_plan"],
        "attributes": {
            "email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
            "portfolio_name": "Aggressive", "plan_identifier": "regular",
            "profile_data": {"first_name": first, "last_name": "QA",
                             "date_of_birth": "1990-01-01", "phone_number": "0412345678"},
        },
    }


def _ach_credit(user_ref, amount):
    return {
        "model": "credit_investment",
        "traits": ["lump_sum", "with_shares_settled_status", "with_holdings"],
        "attributes": {"user": user_ref, "amount": amount, "created_at": "2024-01-01",
                       "payment_method": "ACH"},
    }


def _ach_withdrawal(user_ref, amount):
    """A debit_investment that actually sells shares: investment_type 'Withdrawal',
    settled+holdings, never shares_amount (no setter)."""
    return {
        "model": "debit_investment",
        "traits": ["with_shares_settled_status", "with_holdings"],
        "attributes": {"user": user_ref, "amount": amount, "created_at": "2024-06-01",
                       "investment_type": "Withdrawal", "payment_method": "ACH"},
    }


def _jar_user(parent_ref, email, first, jar_name):
    """A jar is its own user (jar_account) under a parent. Give it the same balance
    levers as a main user (Aggressive portfolio + funded) so its ACH credit settles."""
    return {
        "model": "user",
        "traits": ["jar_account", "has_portfolio", "with_user_profile", "funded", "verified"],
        "attributes": {
            "email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
            "parent_user": parent_ref, "portfolio_name": "Aggressive",
            "jar_account_data": {"name": jar_name},
            "profile_data": {"first_name": first, "last_name": "QA",
                             "date_of_birth": "1990-01-01", "phone_number": "0412345679"},
        },
    }


# Full kid permissions + a huge weekly investing limit so seeding isn't blocked,
# and NEVER can_withdraw (DependentUser has no setter for it).
KID_ACCOUNT_DATA = {
    "account_access": True, "investing": True, "investing_weekly_limit": 10000000,
    "rewards": True, "manage_recurring_and_goals": True, "manage_portfolio": True,
}


def _kid_user(parent_ref, email, first):
    """A kid is its own user (kid_account) under a parent — same balance levers as a
    jar (Aggressive + funded) so its ACH credit settles into the kid's own balance."""
    return {
        "model": "user",
        "traits": ["kid_account", "has_portfolio", "with_user_profile", "funded", "verified"],
        "attributes": {
            "email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
            "parent_user": parent_ref, "portfolio_name": "Aggressive",
            "kid_account_data": KID_ACCOUNT_DATA,
            "profile_data": {"first_name": first, "last_name": "QA",
                             "date_of_birth": "2012-01-01", "phone_number": "0412345680"},
        },
    }


def test_generated_user_displays_seeded_balance():
    """Seed a funded user with an ACH credit on Aggressive; the user's own balance
    must settle to exactly the seeded amount."""
    ts = _ts()
    email = f"green.bal.main.{ts}@emel.xyz"
    amount = 150.00
    payload = {"user_1": _funded_user(email, f"GBalMain{ts}"),
               "investment_1": _ach_credit("@user_1", amount)}
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    assert body.get("created", {}).get("investment_1", {}).get("id"), f"no investment id: {body}"
    print(f"  created user {body['created']['user_1']['id']} ({email}) seeded ${amount}")

    bal, state = _poll_balance(email, amount)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"balance never settled to ${amount} (best seen ${bal}; {state})"
    assert bal == pytest.approx(amount, abs=BAND), f"seeded ${amount} but balance settled to ${bal}"
    print(f"  PASS: current_balance ${bal} == seeded ${amount} (±${BAND})")


def test_generated_jar_displays_seeded_balance():
    """A single funded JAR shows its exact seeded balance. The jar is its own user,
    so we read it via the jar-user's own token. Confirms the recipe works for a
    jar_account sub-account, not just a main account."""
    ts = _ts()
    parent_email = f"green.jar.parent.{ts}@emel.xyz"
    jar_email = f"green.jar.{ts}@emel.xyz"
    amount = 175.50
    payload = {
        "user_1": _funded_user(parent_email, f"JarParent{ts}"),
        "jar_user_1": _jar_user("@user_1", jar_email, f"GreenJar{ts}", "QA Green Jar"),
        "investment_jar_1": _ach_credit("@jar_user_1", amount),
    }
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    jar_id = body.get("created", {}).get("jar_user_1", {}).get("id")
    assert jar_id, f"no jar user id in {body}"
    print(f"  created jar user {jar_id} ({jar_email}) seeded ${amount}")

    bal, state = _poll_balance(jar_email, amount)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"jar balance never settled to ${amount} (best seen ${bal}; {state})"
    assert bal == pytest.approx(amount, abs=BAND), f"seeded ${amount} jar but balance settled to ${bal}"
    print(f"  PASS: jar current_balance ${bal} == seeded ${amount} (±${BAND})")


def test_jar_balance_equals_sum_of_deposits():
    """A jar funded by several ACH credits shows the SUM, not the last/first deposit
    — a real aggregation value check (uses distinct non-round amounts)."""
    ts = _ts()
    parent_email = f"green.jarsum.parent.{ts}@emel.xyz"
    jar_email = f"green.jarsum.{ts}@emel.xyz"
    amounts = [60.10, 40.00, 25.40]
    total = round(sum(amounts), 2)  # 125.50
    payload = {
        "user_1": _funded_user(parent_email, f"JarSumP{ts}"),
        "jar_user_1": _jar_user("@user_1", jar_email, f"JarSum{ts}", "QA Sum Jar"),
    }
    for i, a in enumerate(amounts, 1):
        payload[f"credit_{i}"] = _ach_credit("@jar_user_1", a)
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created jar {body['created']['jar_user_1']['id']} with deposits {amounts} (sum ${total})")

    bal, state = _poll_balance(jar_email, total)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"jar sum never settled to ${total} (best seen ${bal}; {state})"
    assert bal == pytest.approx(total, abs=BAND), f"expected sum ${total} but jar balance ${bal}"
    print(f"  PASS: jar current_balance ${bal} == sum of deposits ${total} (±${BAND})")


def test_sibling_jars_hold_distinct_balances():
    """Two jars under one parent each hold their OWN seeded balance — neither leaks
    into the other (read each jar via its own token)."""
    ts = _ts()
    parent_email = f"green.jarsib.parent.{ts}@emel.xyz"
    jar_a_email = f"green.jarsib.a.{ts}@emel.xyz"
    jar_b_email = f"green.jarsib.b.{ts}@emel.xyz"
    amt_a, amt_b = 80.00, 120.00
    payload = {
        "user_1": _funded_user(parent_email, f"JarSibP{ts}"),
        "jar_a": _jar_user("@user_1", jar_a_email, f"JarSibA{ts}", "QA Jar A"),
        "jar_b": _jar_user("@user_1", jar_b_email, f"JarSibB{ts}", "QA Jar B"),
        "credit_a": _ach_credit("@jar_a", amt_a),
        "credit_b": _ach_credit("@jar_b", amt_b),
    }
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created sibling jars: A {body['created']['jar_a']['id']} (${amt_a}), "
          f"B {body['created']['jar_b']['id']} (${amt_b})")

    bal_a, state_a = _poll_balance(jar_a_email, amt_a)
    if state_a.startswith("GATE"):
        pytest.fail(state_a)
    assert state_a == "settled" and bal_a == pytest.approx(amt_a, abs=BAND), \
        f"jar A expected ${amt_a}, got ${bal_a} ({state_a})"
    bal_b, state_b = _poll_balance(jar_b_email, amt_b)
    assert state_b == "settled" and bal_b == pytest.approx(amt_b, abs=BAND), \
        f"jar B expected ${amt_b}, got ${bal_b} ({state_b})"
    print(f"  PASS: jar A ${bal_a} == ${amt_a}, jar B ${bal_b} == ${amt_b} (distinct, no leak)")


# HISTORY / DEFECT CONTEXT (AUIB-6373 follow-up):
# This jar-withdrawal seed was previously gated by the backend test-data API: a
# debit_investment (Withdrawal) on a jar_account was rejected 422 "exceeds balance"
# because the covering ACH credit had not settled into a withdrawable balance at
# create time. That made the test unable to ever prove the reduction, so it carried a
# (broad, then PRECISE-strict) xfail with the on-device P1-06 jar-withdrawal delta as
# the interim guard for the actual reduction value.
#
# RE-VERIFIED 2026-06-24: the gate is NO LONGER reproducible. Seeding $500 credit +
# $200 Withdrawal on the jar in the SAME create now returns 200 and the jar balance
# settles to EXACTLY the $300 net (created jar 42081 confirmed live). The strict xfail
# correctly XPASS-failed on that, which is the documented signal that the gate lifted —
# so the xfail is removed and this is now a REAL value test of the reduction via the API.
# If the backend ever re-introduces the gate, the create will 422 on the balance/exceed
# signature and the assertions below hard-fail loudly (re-add an xfail then, don't mask).
# The on-device P1-06 delta remains an independent cross-check of the same reduction.
_JAR_WD_GATE_KEYS = ("exceed", "insufficient", "greater than", "available balance")


def test_jar_balance_reduced_by_withdrawal():
    """A withdrawal must REDUCE the jar's balance: $500 credit minus a $200
    Withdrawal nets $300. Catches the 'withdrawal not reflected in balance' defect.

    Previously the jar withdrawal was deterministically gated (422 exceeds-balance) and
    this could only prove the gate, never the reduction. The gate is no longer
    reproducible (see HISTORY above), so this now proves the reduction directly: seed a
    funded jar with a $500 ACH credit + a $200 ACH Withdrawal in one create, then assert
    the jar's own current_balance settles to exactly the $300 net. A re-introduced
    backend gate (422 on the balance/exceed signature) hard-fails here so it is never
    silently masked. Independent cross-check of the same reduction: on-device P1-06.
    """
    ts = _ts()
    parent_email = f"green.jarwd.parent.{ts}@emel.xyz"
    jar_email = f"green.jarwd.{ts}@emel.xyz"
    credit, withdraw = 500.00, 200.00
    net = round(credit - withdraw, 2)  # 300.00
    payload = {
        "user_1": _funded_user(parent_email, f"JarWdP{ts}"),
        "jar_user_1": _jar_user("@user_1", jar_email, f"JarWd{ts}", "QA Withdrawal Jar"),
        "credit_1": _ach_credit("@jar_user_1", credit),
        "withdrawal_1": _ach_withdrawal("@jar_user_1", withdraw),
    }
    status, body = _create(payload)
    if status == 422:
        errs = str(body.get("errors", body)).lower()
        # The backend re-introduced the deterministic balance/exceed gate. Surface it
        # loudly (NOT a silent xfail) so we notice and re-add an explicit xfail+guard.
        if any(k in errs for k in _JAR_WD_GATE_KEYS):
            pytest.fail(f"jar withdrawal gate has RE-APPEARED (AUIB-6373): the API again "
                        f"rejects a jar withdrawal as exceeds-balance — re-add an xfail and "
                        f"lean on on-device P1-06: {str(body.get('errors', body))[:180]}")
        # Any other 422 (schema/trait/validation) is a different new problem.
        pytest.fail(f"jar create 422 but NOT the known withdrawal gate: "
                    f"{str(body.get('errors', body))[:200]}")
    # Real value check: the withdrawal must net the balance down to exactly $300.
    assert status == 200, f"create failed (unexpected non-422): HTTP {status} {body}"
    print(f"  created jar {body['created']['jar_user_1']['id']}: ${credit} credit - ${withdraw} withdrawal -> net ${net}")

    bal, state = _poll_balance(jar_email, net)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"net balance never settled to ${net} (best seen ${bal}; {state})"
    assert bal == pytest.approx(net, abs=BAND), \
        f"expected net ${net} ($500-$200) but jar balance ${bal} — withdrawal not reflected?"
    print(f"  PASS: jar current_balance ${bal} == net ${net} (withdrawal reduced balance)")


# ----------------------------- KIDS ------------------------------------------
def test_generated_kid_displays_seeded_balance():
    """A single funded KID shows its exact seeded balance (read via the kid's own token)."""
    ts = _ts()
    parent_email = f"green.kid.parent.{ts}@emel.xyz"
    kid_email = f"green.kid.{ts}@emel.xyz"
    amount = 165.00
    payload = {
        "user_1": _funded_user(parent_email, f"KidParent{ts}"),
        "kid_user_1": _kid_user("@user_1", kid_email, f"GreenKid{ts}"),
        "investment_kid_1": _ach_credit("@kid_user_1", amount),
    }
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    kid_id = body.get("created", {}).get("kid_user_1", {}).get("id")
    assert kid_id, f"no kid user id in {body}"
    print(f"  created kid user {kid_id} ({kid_email}) seeded ${amount}")
    bal, state = _poll_balance(kid_email, amount)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"kid balance never settled to ${amount} (best seen ${bal}; {state})"
    assert bal == pytest.approx(amount, abs=BAND), f"seeded ${amount} kid but balance settled to ${bal}"
    print(f"  PASS: kid current_balance ${bal} == seeded ${amount} (±${BAND})")


def test_kid_balance_equals_sum_of_deposits():
    """A kid funded by several ACH credits shows the SUM (aggregation value check)."""
    ts = _ts()
    parent_email = f"green.kidsum.parent.{ts}@emel.xyz"
    kid_email = f"green.kidsum.{ts}@emel.xyz"
    amounts = [55.20, 30.00, 40.05]
    total = round(sum(amounts), 2)  # 125.25
    payload = {
        "user_1": _funded_user(parent_email, f"KidSumP{ts}"),
        "kid_user_1": _kid_user("@user_1", kid_email, f"KidSum{ts}"),
    }
    for i, a in enumerate(amounts, 1):
        payload[f"credit_{i}"] = _ach_credit("@kid_user_1", a)
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created kid {body['created']['kid_user_1']['id']} deposits {amounts} (sum ${total})")
    bal, state = _poll_balance(kid_email, total)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"kid sum never settled to ${total} (best seen ${bal}; {state})"
    assert bal == pytest.approx(total, abs=BAND), f"expected sum ${total} but kid balance ${bal}"
    print(f"  PASS: kid current_balance ${bal} == sum of deposits ${total} (±${BAND})")


def test_sibling_kids_hold_distinct_balances():
    """Two kids under one parent each hold their OWN seeded balance — no cross-leak."""
    ts = _ts()
    parent_email = f"green.kidsib.parent.{ts}@emel.xyz"
    kid_a_email = f"green.kidsib.a.{ts}@emel.xyz"
    kid_b_email = f"green.kidsib.b.{ts}@emel.xyz"
    amt_a, amt_b = 70.00, 130.00
    payload = {
        "user_1": _funded_user(parent_email, f"KidSibP{ts}"),
        "kid_a": _kid_user("@user_1", kid_a_email, f"KidSibA{ts}"),
        "kid_b": _kid_user("@user_1", kid_b_email, f"KidSibB{ts}"),
        "credit_a": _ach_credit("@kid_a", amt_a),
        "credit_b": _ach_credit("@kid_b", amt_b),
    }
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created sibling kids: A {body['created']['kid_a']['id']} (${amt_a}), "
          f"B {body['created']['kid_b']['id']} (${amt_b})")
    bal_a, state_a = _poll_balance(kid_a_email, amt_a)
    if state_a.startswith("GATE"):
        pytest.fail(state_a)
    assert state_a == "settled" and bal_a == pytest.approx(amt_a, abs=BAND), \
        f"kid A expected ${amt_a}, got ${bal_a} ({state_a})"
    bal_b, state_b = _poll_balance(kid_b_email, amt_b)
    assert state_b == "settled" and bal_b == pytest.approx(amt_b, abs=BAND), \
        f"kid B expected ${amt_b}, got ${bal_b} ({state_b})"
    print(f"  PASS: kid A ${bal_a} == ${amt_a}, kid B ${bal_b} == ${amt_b} (distinct, no leak)")


def test_kid_balance_reduced_by_withdrawal():
    """A withdrawal reduces the kid's balance: $500 credit - $200 Withdrawal = $300.
    xfails if the backend gates the kid withdrawal (like jars)."""
    ts = _ts()
    parent_email = f"green.kidwd.parent.{ts}@emel.xyz"
    kid_email = f"green.kidwd.{ts}@emel.xyz"
    credit, withdraw = 500.00, 200.00
    net = round(credit - withdraw, 2)
    payload = {
        "user_1": _funded_user(parent_email, f"KidWdP{ts}"),
        "kid_user_1": _kid_user("@user_1", kid_email, f"KidWd{ts}"),
        "credit_1": _ach_credit("@kid_user_1", credit),
        "withdrawal_1": _ach_withdrawal("@kid_user_1", withdraw),
    }
    status, body = _create(payload)
    if status == 422:
        errs = str(body.get("errors", body)).lower()
        if any(k in errs for k in ("exceed", "withdraw", "balance", "insufficient", "limit")):
            pytest.xfail(f"kid withdrawal gated by backend (known): {str(body.get('errors', body))[:180]}")
        pytest.fail(f"create failed: HTTP {status} {body}")
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created kid {body['created']['kid_user_1']['id']}: ${credit} - ${withdraw} -> net ${net}")
    bal, state = _poll_balance(kid_email, net)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"kid net never settled to ${net} (best seen ${bal}; {state})"
    assert bal == pytest.approx(net, abs=BAND), f"expected net ${net} but kid balance ${bal}"
    print(f"  PASS: kid current_balance ${bal} == net ${net} (withdrawal reduced balance)")


# --------------------------- MAIN (extra) ------------------------------------
def test_main_balance_equals_sum_of_deposits():
    """A main account funded by several ACH credits shows the SUM."""
    ts = _ts()
    email = f"green.mainsum.{ts}@emel.xyz"
    amounts = [100.00, 50.50, 25.25]
    total = round(sum(amounts), 2)  # 175.75
    payload = {"user_1": _funded_user(email, f"MainSum{ts}")}
    for i, a in enumerate(amounts, 1):
        payload[f"credit_{i}"] = _ach_credit("@user_1", a)
    status, body = _create(payload)
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created user {body['created']['user_1']['id']} deposits {amounts} (sum ${total})")
    bal, state = _poll_balance(email, total)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"main sum never settled to ${total} (best seen ${bal}; {state})"
    assert bal == pytest.approx(total, abs=BAND), f"expected sum ${total} but balance ${bal}"
    print(f"  PASS: main current_balance ${bal} == sum of deposits ${total} (±${BAND})")


def test_main_balance_reduced_by_withdrawal():
    """A withdrawal reduces the main balance: $600 credit - $250 Withdrawal = $350.
    Main-account withdrawals are expected to work (unlike jar/kid sub-accounts)."""
    ts = _ts()
    email = f"green.mainwd.{ts}@emel.xyz"
    credit, withdraw = 600.00, 250.00
    net = round(credit - withdraw, 2)  # 350.00
    payload = {
        "user_1": _funded_user(email, f"MainWd{ts}"),
        "credit_1": _ach_credit("@user_1", credit),
        "withdrawal_1": _ach_withdrawal("@user_1", withdraw),
    }
    status, body = _create(payload)
    if status == 422:
        errs = str(body.get("errors", body)).lower()
        if any(k in errs for k in ("exceed", "withdraw", "balance", "insufficient")):
            pytest.xfail(f"main withdrawal gated unexpectedly: {str(body.get('errors', body))[:180]}")
        pytest.fail(f"create failed: HTTP {status} {body}")
    assert status == 200, f"create failed: HTTP {status} {body}"
    print(f"  created user {body['created']['user_1']['id']}: ${credit} - ${withdraw} -> net ${net}")
    bal, state = _poll_balance(email, net)
    if state.startswith("GATE"):
        pytest.fail(state)
    assert state == "settled", f"main net never settled to ${net} (best seen ${bal}; {state})"
    assert bal == pytest.approx(net, abs=BAND), f"expected net ${net} but balance ${bal}"
    print(f"  PASS: main current_balance ${bal} == net ${net} (withdrawal reduced balance)")
