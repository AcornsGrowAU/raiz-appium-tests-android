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
  field for the right-hand side. We reconstruct the sum from each account's OWN
  balance, read separately: Main and the kid by logging in AS that account (kids
  have account_access), and the jar via the PARENT session's jars API
  (`accumulated_amount` == the jar's own balance) — jars are sub-accounts of the
  main account with NO loginable identity (a jar-email /v1/sessions 401s by
  design). None of these per-account reads touches the aggregate field. Two
  genuinely different code paths (aggregate view vs per-account holdings) must
  agree. This is the RAIZ-10251 "totals don't add up" defect family.

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
  ACH credits (NOT the repricing buffer). The kid lives at a deterministic
  loginable address derived from the parent (kid = ck.<parent>); the jar is
  addressed by its NAME ('QA Conserve Jar') through the parent session
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

from utils.genuser_api import (
    API, SEEDED_PWD, call, mint,
)
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

# Settled ACH lands on the exact dollar, but the holdings are MARKET-PRICED and
# the reused fixture lives for weeks — unit prices drift the balances a few
# percent off the seeds (measured 2.25% on 2026-07-13 across all fixtures). The
# seed anchor is only an anti-garbage gate (a $0 / truncated / wrong-account read
# is >>8% off); the real oracle below is drift-immune because the independent sum
# and the displayed aggregate move together. Band: 8% of each seed, $2 floor.
def _seed_band(seed):
    return max(2.00, seed * 0.08)
# The aggregate field and the independent per-account sum are the SAME numbers
# (one summed server-side, one summed by us) — they must agree to the cent.
RECON_BAND = 0.05


# Jar card name (FIXTURES['conserve_main_jar_kid']: jar_user('cj.'+email, ...,
# "QA Conserve Jar")). Jars have NO loginable identity — the jar is read by this
# name through the PARENT session (jar_balance_by_name), never by minting a token
# for its derived cj.<parent> address.
CONSERVE_JAR_NAME = "QA Conserve Jar"


def _kid_email(parent_email):
    """Kid sub-account address (FIXTURES['conserve_main_jar_kid']: kid_user('ck.'+email,...))."""
    return "ck." + parent_email


class _BalanceReader:
    """EFF-02: reuse ONE minted /v1/sessions token per account across its balance
    reads (the sessions endpoint is rate-limited; current_balance() +
    jar_balance_by_name() would each mint a SEPARATE login for the SAME parent). The
    parent reader serves both the Main /v1/user balance AND the parent-session jars
    read; a second reader serves the kid's own login. Re-mints only when a cached
    token is rejected (401), mirroring the withdrawal value tests' _BalanceReader.
    Every read returns a float or None on failure — the oracle values are unchanged.
    (The v3-user read keeps its own fresh-mint-per-attempt retry, mirroring the
    home-total-conservation reader.)"""

    def __init__(self, email, pwd=SEEDED_PWD):
        self.email, self.pwd = email, pwd
        self._op = self._tok = None

    def _ensure(self):
        if self._tok is None:
            self._op, self._tok = mint(self.email, self.pwd)
        return self._tok is not None

    def _get(self, path):
        for _ in range(2):  # one retry: re-mint if the cached token was rejected
            if not self._ensure():
                self._op = self._tok = None
                return None, None
            s, b = call(self._op, "GET", path, token=self._tok)
            if s != 401:
                return s, b
            self._op = self._tok = None
        return None, None

    def current_balance(self):
        """The account's own current_balance (GET /v1/user), or None on failure."""
        s, b = self._get("/v1/user")
        if s != 200:
            return None
        user = b.get("user", b) if isinstance(b, dict) else {}
        cb = user.get("current_balance")
        return float(cb) if cb is not None else None

    def jar_balance(self, name):
        """The named jar's accumulated_amount read via THIS (parent) session, or None.
        Jars have no loginable identity — the parent's jars list carries the jar's own
        balance."""
        s, b = self._get("/jars/v1/users")
        if s != 200 or not isinstance(b, dict):
            return None
        for j in b.get("jar_users", []):
            if isinstance(j, dict) and j.get("name") == name:
                amt = j.get("accumulated_amount")
                return float(amt) if amt is not None else None
        return None


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
      B) Σ of each account's own balance, read account-by-account (Main/kid via
         their own logins, the jar via the parent session's jars API —
         accumulated_amount — since jars have no loginable identity).
    A wrong aggregate cannot be reconciled against itself because B never reads
    the aggregate field.
    """
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)
    kid_email = _kid_email(parent_email)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')})")
    print(f"  jar '{CONSERVE_JAR_NAME}' (parent-session read)  kid {kid_email}")

    # ---- B) Independent per-account oracle: each account's OWN balance. Main and
    #         the kid are read by logging in AS that account; the jar (no loginable
    #         identity) is read through the PARENT session's jars API — its own
    #         accumulated_amount, NOT the aggregate field. ----
    # EFF-02: one parent token reused for BOTH the Main balance and the jar read
    # (was two separate parent logins); the kid keeps its own login (different
    # account). None on failure preserves the existing 'could not read' assertion.
    parent_reader = _BalanceReader(parent_email, pwd)
    bal_main = parent_reader.current_balance()
    bal_jar = parent_reader.jar_balance(CONSERVE_JAR_NAME)
    bal_kid = _BalanceReader(kid_email, SEEDED_PWD).current_balance()
    print(f"  per-account balances: main={bal_main} jar={bal_jar} kid={bal_kid}")

    assert None not in (bal_main, bal_jar, bal_kid), (
        f"could not read every per-account balance independently "
        f"(main={bal_main}, jar={bal_jar} via parent-session jars API "
        f"['{CONSERVE_JAR_NAME}'], kid={bal_kid}) — fixture login/read failed; "
        f"cannot build the independent oracle")

    # Anchor each input to its EXACT seed: a 420 total is only a meaningful oracle
    # if it is built from the seeded $300/$80/$40, not from drifted/garbled parts.
    assert bal_main == pytest.approx(SEED_MAIN, abs=_seed_band(SEED_MAIN)), (
        f"Main balance ${bal_main} is not at the seeded ~${SEED_MAIN} level "
        f"(±${_seed_band(SEED_MAIN):.2f}) — garbage/truncated read, not market drift")
    assert bal_jar == pytest.approx(SEED_JAR, abs=_seed_band(SEED_JAR)), (
        f"jar balance ${bal_jar} is not at the seeded ~${SEED_JAR} level "
        f"(±${_seed_band(SEED_JAR):.2f}) — garbage/truncated read, not market drift")
    assert bal_kid == pytest.approx(SEED_KID, abs=_seed_band(SEED_KID)), (
        f"kid balance ${bal_kid} is not at the seeded ~${SEED_KID} level "
        f"(±${_seed_band(SEED_KID):.2f}) — garbage/truncated read, not market drift")

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
    assert screen_value == pytest.approx(SEED_TOTAL, abs=_seed_band(SEED_TOTAL)), (
        f"'Total in investments' ${screen_value} is nowhere near the seeded "
        f"grand total ${SEED_TOTAL} (Main+jar+kid, ±${_seed_band(SEED_TOTAL):.2f}) "
        "— wrong source field")

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
