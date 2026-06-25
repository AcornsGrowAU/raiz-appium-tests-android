"""
Shared Test-Data-Generation API helpers (AUIB-6373) — the proven plumbing for
seeding generated users and reading their state. No emulator.

Auth: POST /v1/sessions {email,password,udid} -> token; then `Authorization: token <tok>`.
The create endpoint flaps on `rho_settled_at` (transient) -> retried here.
See memory: raiz-dev-api-auth, genuser-test-data-reuse-strategy.
"""
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request

API = os.getenv("RAIZ_API", "https://api-dev.raizinvest.com.au")
UDID = "2204bb70-d6f7-4ccd-ad49-94d9b420feaa"
GEN_EMAIL = os.getenv("GEN_EMAIL", "anmol@raizinvest.com.au")
GEN_PWD = os.getenv("GEN_PWD", "TestDemo123")
SEEDED_PWD = "Pass1234"
RHO_MAX_RETRIES = int(os.getenv("RHO_MAX_RETRIES", "30"))


def opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(op, method, path, token=None, body=None, timeout=40):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    for h, v in (("content-type", "application/json"), ("accept", "application/json"), ("x-version", "v1")):
        req.add_header(h, v)
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with op.open(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def mint(email, pwd, budget_s=180):
    """Login -> (opener, token). Backoff through the /v1/sessions rate-limit (400)."""
    body = {"email": email, "password": pwd, "remember": False, "udid": UDID}
    waited, delay = 0, 8
    while True:
        op = opener()
        status, payload = call(op, "POST", "/v1/sessions", body=body)
        tok = payload.get("token") if isinstance(payload, dict) else None
        if status in (200, 201) and tok:
            return op, tok
        if status != 400 or waited > budget_s:   # 400 == transient rate-limit; else real failure
            return op, None
        time.sleep(delay)
        waited += delay
        delay = min(delay * 2, 60)


def gen_create(payload):
    """POST /internal/v1/test_data_generation with {payload}. Mints a fresh gen token
    per attempt (tokens expire) and retries the transient rho_settled_at flap.
    Returns (status, body)."""
    status, body = None, None
    for _ in range(RHO_MAX_RETRIES):
        op, tok = mint(GEN_EMAIL, GEN_PWD)
        if not tok:
            time.sleep(8)
            continue
        status, body = call(op, "POST", "/internal/v1/test_data_generation",
                            token=tok, body={"payload": payload})
        errs = body.get("errors", []) if isinstance(body, dict) else []
        if status == 422 and any("rho_settled_at" in str(e) for e in errs):
            time.sleep(8)
            continue
        # Transient auth flap: the gen token can expire / be rejected in the window
        # between mint and this POST ("Login required."). Re-mint a fresh token and
        # retry rather than failing the seed on a recoverable 401/403.
        if status in (401, 403):
            time.sleep(8)
            continue
        return status, body
    return status, body


def current_balance(email, pwd=SEEDED_PWD):
    """current_balance the backend reports for a user (None if login/read fails)."""
    op, tok = mint(email, pwd)
    if not tok:
        return None
    s, b = call(op, "GET", "/v1/user", token=tok)
    if s != 200:
        return None
    user = b.get("user", b) if isinstance(b, dict) else {}
    cb = user.get("current_balance")
    return float(cb) if cb is not None else None


def can_login(email, pwd=SEEDED_PWD):
    _, tok = mint(email, pwd, budget_s=60)
    return bool(tok)


# ---- recipe builders -------------------------------------------------------
def _profile(first, dob="1990-01-01", phone="0412345678"):
    return {"first_name": first, "last_name": "QA", "date_of_birth": dob, "phone_number": phone}


def funded_user(email, first, app_ready=True):
    """A funded user on Aggressive. app_ready adds the traits/attrs that pre-clear
    onboarding gates (pds_accepted_at -> advisor agreement; funding source; etc.)."""
    traits = ["has_portfolio", "with_user_profile", "funded", "verified", "with_active_plan"]
    attrs = {"email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
             "portfolio_name": "Aggressive", "plan_identifier": "regular", "profile_data": _profile(first)}
    if app_ready:
        traits += ["with_billing_funding_source", "registered_in_yodlee"]
        attrs.update({"created_at": "2024-01-01", "pds_accepted_at": "2024-01-01"})
    return {"model": "user", "traits": traits, "attributes": attrs}


def with_balance_user(email, first, bought_shares=1, price_difference=5, app_ready=True):
    """User whose `with_balance` trait creates priced Aggressive holdings that render
    IMMEDIATELY (no slow cash->invested settle). ~bought_shares x Aggressive unit price."""
    u = funded_user(email, first, app_ready=app_ready)
    u["traits"].append("with_balance")
    u["attributes"].update({"bought_shares": bought_shares, "price_difference": price_difference})
    return u


KID_ACCOUNT_DATA = {
    "account_access": True, "investing": True, "investing_weekly_limit": 10000000,
    "rewards": True, "manage_recurring_and_goals": True, "manage_portfolio": True,
}


def kid_with_balance_user(email, first, parent_ref, bought_shares=500, price_difference=5):
    """A kid sub-account (its own user) with immediate priced holdings via with_balance."""
    u = with_balance_user(email, first, bought_shares=bought_shares, price_difference=price_difference)
    u["traits"] = ["kid_account"] + u["traits"]
    u["attributes"]["parent_user"] = parent_ref
    u["attributes"]["kid_account_data"] = KID_ACCOUNT_DATA
    return u


def jar_with_balance_user(email, first, parent_ref, jar_name, bought_shares=500, price_difference=5):
    """A jar sub-account (its own user) with immediate priced holdings via with_balance."""
    u = with_balance_user(email, first, bought_shares=bought_shares, price_difference=price_difference)
    u["traits"] = ["jar_account"] + u["traits"]
    u["attributes"]["parent_user"] = parent_ref
    u["attributes"]["jar_account_data"] = {"name": jar_name}
    return u


def ach_credit(user_ref, amount, count=None, created_at="2024-01-01"):
    e = {"model": "credit_investment",
         "traits": ["lump_sum", "with_shares_settled_status", "with_holdings"],
         "attributes": {"user": user_ref, "amount": amount, "created_at": created_at,
                        "payment_method": "ACH"}}
    if count:
        e["count"] = count
    return e


ACH_TXN_CAP = 10000  # backend caps a single ACH transfer at $10,000 (verified: 422 above)


def ach_credits(user_ref, total, prefix="credit", cap=ACH_TXN_CAP, created_at="2024-01-01"):
    """Build a REAL balance from ACH credit_investments (payment_method ACH), splitting
    `total` into <=cap chunks (the backend rejects a single ACH transfer over $10k).

    This is the ACCURATE way to seed a balance: unlike the `with_balance` trait (a
    fabricated, market-priced holding whose value DRIFTS), these are real ACH lump-sum
    investments that settle to current_balance == total EXACTLY and stay stable
    (verified: credits summing $25,000 -> current_balance $25,000.00, unchanged over 40s).

    Returns a dict {prefix_1: <credit>, ...} to splice into a gen payload via **. Use a
    UNIQUE prefix per user so sibling sub-accounts' credit keys don't collide."""
    amounts, remaining = [], round(float(total), 2)
    while remaining > 0.005:
        amt = min(cap, remaining)
        amounts.append(round(amt, 2))
        remaining = round(remaining - amt, 2)
    return {f"{prefix}_{i + 1}": ach_credit(user_ref, a, created_at=created_at)
            for i, a in enumerate(amounts)}


def kid_user(email, first, parent_ref, portfolio_name=None):
    """A kid sub-account (its own user) under a parent with NO pre-seeded balance —
    fund it with REAL ACH credits via `**ach_credits('@<ref>', total, prefix=...)`.
    Pass portfolio_name (e.g. 'Aggressive'/'Moderate'/'Conservative') to store a
    per-kid portfolio independent of the parent (verified accepted by the gen API)."""
    u = funded_user(email, first)
    u["traits"] = ["kid_account"] + u["traits"]
    u["attributes"]["parent_user"] = parent_ref
    u["attributes"]["kid_account_data"] = KID_ACCOUNT_DATA
    if portfolio_name:
        u["attributes"]["portfolio_name"] = portfolio_name
    return u


def jar_user(email, first, parent_ref, jar_name, portfolio_name=None, saving_amount=None,
             icon_id=None):
    """A jar sub-account (its own user) under a parent with NO pre-seeded balance —
    fund it with REAL ACH credits via `**ach_credits('@<ref>', total, prefix=...)`.

    - portfolio_name: store a per-jar portfolio independent of Main (verified accepted).
    - saving_amount: the jar's savings GOAL/target (jar.saving_amount; exposed on the
      jar detail). Used by jar-target-roundtrip / jar-goal-progress-ring.
    - icon_id: jar tile icon (e.g. 'home')."""
    u = funded_user(email, first)
    u["traits"] = ["jar_account"] + u["traits"]
    u["attributes"]["parent_user"] = parent_ref
    jdata = {"name": jar_name}
    if saving_amount is not None:
        jdata["saving_amount"] = saving_amount
    if icon_id is not None:
        jdata["icon_id"] = icon_id
    u["attributes"]["jar_account_data"] = jdata
    if portfolio_name:
        u["attributes"]["portfolio_name"] = portfolio_name
    return u


def tiered_user(email, first, plan_identifier="regular", portfolio_name="Aggressive"):
    """A funded user on a specific PLAN TIER. plan_identifier is the backend Plan enum
    value: 'starter' (the app's "Lite" plan), 'regular', or 'plus'. NOTE: 'lite' is
    NOT a valid identifier (gen API 422 'Trait not registered: lite') — use 'starter'.
    Starter only permits Conservative/Moderately Conservative/Moderate portfolios."""
    u = funded_user(email, first)
    u["attributes"]["plan_identifier"] = plan_identifier
    u["attributes"]["portfolio_name"] = portfolio_name
    return u


def ach_withdrawal(user_ref, amount, created_at="2024-06-01"):
    return {"model": "debit_investment",
            "traits": ["with_shares_settled_status", "with_holdings"],
            "attributes": {"user": user_ref, "amount": amount, "created_at": created_at,
                           "investment_type": "Withdrawal", "payment_method": "ACH"}}
