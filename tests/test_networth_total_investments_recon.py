"""
networth-total-investments-recon (P1, conf 72, data_mode dynamic) — VALUE,
API-layer-first, no device, deterministic.

WHAT THE SCREEN SHOWS
  The My Finance "My net worth" card renders a 'Total in investments' figure.
  In the app source that figure is NOT a screen-local sum — it is bound to ONE
  backend field:
    features/financev2/.../main/FinanceMainScreenState.kt:46
        totalInvestments = user.investingAccountsBalance
    raizCore/.../user/UserResponse.kt:87-88
        @SerializedName("investing_accounts_balance") val investingAccountsBalance
  i.e. the card draws the API field `investing_accounts_balance` verbatim.

THE ORACLE (independent — the whole point of this case)
  Backend ground truth for that field (app/models/concerns/user_account_types.rb):
        def investing_accounts        -> [self] + child_users + jar_users
        def investing_accounts_balance-> investing_accounts.sum(&:current_balance)
  So the screen figure MUST equal Main + Σ(kids) + Σ(jars) current balances.

  To make the oracle INDEPENDENT of the screen's source (so a single wrong
  aggregate can't be "reconciled" against itself), we do NOT trust the aggregate
  field for the right-hand side. We reconstruct the sum from each sub-account's
  OWN `current_balance`, read by logging in AS that account separately (Main
  parent, the jar sub-user, the kid sub-user) — exactly how the no-cross-post
  test reads per-account ground truth. Two genuinely different code paths
  (aggregate view vs per-account holdings) must agree. This is the RAIZ-10251
  "totals don't add up" defect family.

DE-DUPE vs home-total-conservation (#4)
  #4 asserts the HOME headline conserves across a transfer. THIS case is scoped
  per the backlog note to the MY-FINANCE screen field (`investing_accounts_balance`)
  vs an independent per-account backend sum — different surface, different oracle.

WHY v3
  The field lives on Entities::V3::User (app/api/entities/v3/user.rb:57); the
  legacy /v1/user payload omits it (verified: returns null). The app reads the
  v3 user. We send x-version: v3 to read the same field the screen reads.

DATA — pre-provisioned `conserve_main_jar_kid` fixture (reuse strategy):
  Main $300.00 + 1 jar $80.00 + 1 kid $40.00, all seeded with small EXACT settled
  ACH credits (NOT the repricing buffer). Sub-accounts live at deterministic
  addresses derived from the parent: jar = cj.<parent>, kid = ck.<parent>
  (utils.genuser_fixtures FIXTURES['conserve_main_jar_kid']). Settled ACH lands on
  the exact dollar amount and stays stable (cent-level holding settlement only),
  so both the inputs and the recon are read precisely.

needs_device: FALSE — pure DEV-API value test.
Run (no emulator):
  venv/bin/python -m pytest tests/test_networth_total_investments_recon.py -v -s -o addopts=""
"""
import json
import time
import urllib.request

import pytest

from utils.genuser_api import API, SEEDED_PWD, call, current_balance, mint
from utils.genuser_fixtures import (
    CONSERVE_MAIN_BALANCE,
    CONSERVE_JAR_BALANCE,
    CONSERVE_KID_BALANCE,
    get_or_create_fixture_user,
)

pytestmark = [pytest.mark.value_api, pytest.mark.portfolio]

FIXTURE_KEY = "conserve_main_jar_kid"

# Per-account exact seeds (small EXACT ACH amounts, never the priced buffer).
SEED_MAIN = CONSERVE_MAIN_BALANCE   # 300.00
SEED_JAR = CONSERVE_JAR_BALANCE     # 80.00
SEED_KID = CONSERVE_KID_BALANCE     # 40.00
SEED_TOTAL = round(SEED_MAIN + SEED_JAR + SEED_KID, 2)  # 420.00

# Settled ACH lands on the exact dollar; only sub-dollar holding-settlement drift
# is allowed when anchoring each account to its seed.
SEED_BAND = 2.00
# The aggregate field and the independent per-account sum are the SAME numbers
# (one summed server-side, one summed by us) — they must agree to the cent.
RECON_BAND = 0.05


def _jar_email(parent_email):
    """Jar sub-account address (FIXTURES['conserve_main_jar_kid']: jar_user('cj.'+email,...))."""
    return "cj." + parent_email


def _kid_email(parent_email):
    """Kid sub-account address (FIXTURES['conserve_main_jar_kid']: kid_user('ck.'+email,...))."""
    return "ck." + parent_email


def _read_v3_user(op, token):
    """One GET of the V3 user payload (x-version: v3) — the genuser_api.call() helper
    pins x-version: v1, and the legacy v1 user omits investing_accounts_balance. The
    My Finance card reads the v3 user, so we read the same surface. Returns
    (ok, user_dict) where ok signals a clean 200 with a parseable dict body; a
    transient (HTTP error / network blip / non-dict body) returns (False, None)."""
    req = urllib.request.Request(API + "/v3/user", method="GET")
    for h, v in (("content-type", "application/json"), ("accept", "application/json"),
                 ("x-version", "v3")):
        req.add_header(h, v)
    req.add_header("Authorization", f"token {token}")
    try:
        with op.open(req, timeout=40) as r:
            raw = r.read().decode()
            body = json.loads(raw) if raw else {}
    except Exception:
        return False, None
    if not isinstance(body, dict):
        return False, None
    return True, body.get("user", body)


def _get_v3_user(parent_email, pwd, attempts=3, retry_delay_s=8):
    """Read the v3 user (the screen's source surface) with a BOUNDED retry that
    distinguishes a transient (login rate-limit / network blip / HTTP error) from a
    real result. Mints a FRESH token per attempt because session tokens can expire or
    be rejected in the rate-limit window — exactly how the sibling home-total-recon
    reader (test_home_total_conservation._v3_investing_accounts_balance) protects the
    same /v3/user read. A single transient must not degrade an already-reconcilable
    run to a hard failure. A clean 200 (even with a missing field) is a contract
    result, not a transient, so it returns immediately without burning retries.
    Returns the user dict, or None if every attempt failed transiently."""
    last = None
    for i in range(attempts):
        op, tok = mint(parent_email, pwd)
        if not tok:
            last = "login failed (no token)"
        else:
            ok, user = _read_v3_user(op, tok)
            if ok:
                return user           # clean 200; field-presence checked by caller
            last = "transient /v3/user read failure"
        print(f"  [v3/user {parent_email.split('@')[0]} attempt {i + 1}/{attempts}] {last}")
        if i < attempts - 1:
            time.sleep(retry_delay_s)
    return None


def test_my_finance_total_investments_reconciles_with_independent_backend_sum():
    """The My-Finance 'Total in investments' value (`investing_accounts_balance`)
    equals the INDEPENDENT sum of Main + jar + kid own balances.

    Two genuinely separate code paths must agree:
      A) the aggregate the screen renders  (v3 user.investing_accounts_balance)
      B) Σ of each sub-account's own current_balance, read account-by-account.
    A wrong aggregate cannot be reconciled against itself because B never reads
    the aggregate field.
    """
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)
    jar_email, kid_email = _jar_email(parent_email), _kid_email(parent_email)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')})")
    print(f"  jar {jar_email}  kid {kid_email}")

    # ---- B) Independent per-account oracle: each account's OWN current_balance,
    #         read by logging in AS that account (no aggregate field involved). ----
    bal_main = current_balance(parent_email, pwd)
    bal_jar = current_balance(jar_email, SEEDED_PWD)
    bal_kid = current_balance(kid_email, SEEDED_PWD)
    print(f"  per-account balances: main={bal_main} jar={bal_jar} kid={bal_kid}")

    assert None not in (bal_main, bal_jar, bal_kid), (
        f"could not read every sub-account balance independently "
        f"(main={bal_main}, jar={bal_jar}, kid={bal_kid}) — fixture login/read "
        f"failed; cannot build the independent oracle")

    # Anchor each input to its EXACT seed: a 420 total is only a meaningful oracle
    # if it is built from the seeded $300/$80/$40, not from drifted/garbled parts.
    assert bal_main == pytest.approx(SEED_MAIN, abs=SEED_BAND), (
        f"Main balance ${bal_main} drifted from its seed ${SEED_MAIN}")
    assert bal_jar == pytest.approx(SEED_JAR, abs=SEED_BAND), (
        f"jar balance ${bal_jar} drifted from its seed ${SEED_JAR}")
    assert bal_kid == pytest.approx(SEED_KID, abs=SEED_BAND), (
        f"kid balance ${bal_kid} drifted from its seed ${SEED_KID}")

    independent_sum = round(bal_main + bal_jar + bal_kid, 2)
    print(f"  independent sum (Main+jar+kid) = ${independent_sum}")

    # ---- A) The screen's source of truth: the v3 user's investing_accounts_balance,
    #         the exact field FinanceMainScreenState.totalInvestments binds to. ----
    user = _get_v3_user(parent_email, pwd)
    assert user is not None, (
        f"GET /v3/user failed after bounded retries for parent {parent_email} — "
        "cannot read the screen's source field (transient login/read failure)")

    screen_value = user.get("investing_accounts_balance")
    assert screen_value is not None, (
        "investing_accounts_balance missing on the v3 user — the My-Finance "
        "'Total in investments' card would render a null/blank total")
    screen_value = round(float(screen_value), 2)
    print(f"  My-Finance 'Total in investments' (investing_accounts_balance) = ${screen_value}")

    # Sanity: the aggregate must itself be near the seeded grand total (catches a
    # field that is well-formed money but reads some unrelated balance).
    assert screen_value == pytest.approx(SEED_TOTAL, abs=3 * SEED_BAND), (
        f"'Total in investments' ${screen_value} is nowhere near the seeded "
        f"grand total ${SEED_TOTAL} (Main+jar+kid) — wrong source field")

    # ---- The reconciliation: screen aggregate == independent per-account sum. ----
    # Both are summing the same three current balances; they must match to the
    # cent. A mismatch here is the 'totals don't add up' defect (RAIZ-10251):
    # the My-Finance figure would disagree with what each account actually holds.
    assert screen_value == pytest.approx(independent_sum, abs=RECON_BAND), (
        f"RECONCILIATION FAILED: My-Finance 'Total in investments' "
        f"${screen_value} != independent Σ(Main ${bal_main} + jar ${bal_jar} + "
        f"kid ${bal_kid}) = ${independent_sum} (within ${RECON_BAND}). The screen "
        f"aggregate disagrees with the per-account ground truth — totals don't "
        f"add up (RAIZ-10251 family).")

    print(f"  PASS: 'Total in investments' ${screen_value} == independent "
          f"Σ ${independent_sum} (Main+jar+kid), reconciled within ${RECON_BAND}")
