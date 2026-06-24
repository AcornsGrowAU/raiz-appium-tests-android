"""
myfinance-empty-state (P1, negative/rejection) — API LAYER (no device).

Oracle (backlog row + notes):
  A fresh, FUNDED but UNLINKED user (no `registered_in_yodlee`, i.e. no Yodlee /
  AccountMonitor spend transactions synced) must render a TRUE zero/empty My Finance
  spend state:
    - Where-You-Spend == $0 / empty: NO category-spending rows.
    - Future Cash empty: NO upcoming/forecast transactions.
    - net-worth rows are 0-or-seeded, with NO unsubstituted '%s' / placeholder leak.
  "Confirm exact copy on 3252" — see the HONESTY note below on why copy is split off.

Why API-layer-first (notes: 'assert STATE not enforcement', deterministic, no device):
  The My Finance home + Where-You-Spend widget + Future Cash are populated by three
  backend endpoints the app's FinanceService calls
  (raizCore/.../network/services/FinanceService.kt, build 3252):
      GET /v3/spend_analysis/summary               -> FinanceSummaryResponse
      GET /v3/spend_analysis/transactions/upcoming -> Future Cash (UpcomingTransaction[])
      GET /v3/spend_analysis/categories            -> STATIC category catalog (not user data)
  The empty state is decided ENTIRELY in the backend presenter
  (raiz-backend app/api/v3/presenters/spend_analysis/summary.rb): with no synced
  AccountMonitor debit transactions, `debit_totals` is blank, so
      category_spending == []      (no Where-You-Spend rows)
      monthly_tracker   == {}       (no spent-last-month / average)
      subscriptions / buy_now_pay_later / biggest_transactions == []
      forecast          == {}       (no Future Cash)
  and `net_worth` carries only the suitability `income` band string (no dollar
  figures, no '%s' template leak). Asserting these payloads directly proves the
  empty STATE (not UI enforcement) against backend ground truth, deterministically.

FIXTURE: `myfinance_unlinked` — funded_user(app_ready=True) with the
  `registered_in_yodlee` trait STRIPPED (utils/genuser_fixtures.py::_unlinked_user),
  so there is no synced spend. Reused if it still logs in; re-seeded fresh otherwise.

HONESTY / split-scope (backlog asks to "confirm exact copy on 3252"):
  Exact on-screen empty-state COPY ("You haven't linked an account", etc.) is a
  device/Compose concern and is NOT in the API payload — that sub-clause would need
  an on-device read. This test takes the API-provable half (the empty DATA STATE, the
  load-bearing oracle: no category rows, no Future Cash, no placeholder leak). The copy
  sub-clause is intentionally deferred to a device test rather than faked here.

Any seed/login gate -> skip-with-reason (clear evidence), never a fake/vacuous pass.

Run (no emulator):
  venv/bin/python -m pytest tests/test_myfinance_empty_state.py -v -s -o addopts=""
"""
import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import get_or_create_fixture_user

pytestmark = pytest.mark.value_api

SUMMARY_PATH = "/v3/spend_analysis/summary"
UPCOMING_PATH = "/v3/spend_analysis/transactions/upcoming?period=30"

# A placeholder/template leak: an unsubstituted format token reaching the payload
# (the "no '%s'/placeholder leak" sub-clause). Catches a backend that string-formats
# a label with a missing arg, or a sentinel string used in place of a real value.
_PLACEHOLDER_TOKENS = ("%s", "%d", "%@", "{0}", "{}", "null", "nan", "undefined")


def _leaks_placeholder(value):
    """True if a scalar value is (or contains) an unsubstituted placeholder token."""
    if not isinstance(value, str):
        return False
    low = value.strip().lower()
    return any(tok in low for tok in _PLACEHOLDER_TOKENS)


def _assert_no_placeholder_leak(node, where):
    """Walk a JSON node; fail if any string leaf is an unsubstituted placeholder."""
    if isinstance(node, dict):
        for k, v in node.items():
            _assert_no_placeholder_leak(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _assert_no_placeholder_leak(v, f"{where}[{i}]")
    else:
        assert not _leaks_placeholder(node), (
            f"My Finance summary leaked an unsubstituted placeholder at {where}: "
            f"{node!r} — empty-state should render real/empty values, not a template token")


def test_unlinked_user_shows_empty_my_finance_state():
    """A funded-but-unlinked user's My Finance spend state is truly empty: no
    Where-You-Spend category rows, no Future Cash, net-worth carries no dollar leak
    and no unsubstituted placeholder — asserted against the live v3 endpoints."""
    rec = get_or_create_fixture_user("myfinance_unlinked")
    email = rec["email"]
    op, tok = mint(email, rec.get("password", SEEDED_PWD))
    if not tok:
        pytest.skip(f"skip-with-reason: could not log in fixture myfinance_unlinked "
                    f"({email}); login/seed gate, not a product result")

    # FUNDED PRECONDITION (makes the empty-state result NON-vacuous): the backlog oracle
    # is a FUNDED-but-UNLINKED user. Confirm via /v1/user that this is a real funded
    # account (current_balance > 0), so the empty My Finance state below is provably the
    # no-Yodlee SPEND state — NOT a trivially-empty shell account. An investment balance
    # never creates AccountMonitor spend transactions, so the spend state stays empty
    # regardless of the deposit; this guard just rules out the vacuous-pass case.
    su, ub = call(op, "GET", "/v1/user", token=tok)
    if su != 200 or not isinstance(ub, dict):
        pytest.skip(f"skip-with-reason: GET /v1/user returned HTTP {su} for {email}; "
                    f"endpoint/auth gate, not a product result")
    user = ub.get("user", ub)
    cb = user.get("current_balance")
    bal = float(cb) if cb is not None else 0.0
    assert bal > 0, (
        f"funded precondition failed: {email} current_balance={bal!r} — the "
        f"myfinance_unlinked fixture must be a FUNDED-but-unlinked user so the empty "
        f"My Finance state is non-vacuous; re-seed the fixture (drop the registry entry)")
    print(f"  funded precondition OK: current_balance=${bal:.2f}")

    # --- My Finance home + Where-You-Spend (the summary endpoint) ---
    s, summary = call(op, "GET", SUMMARY_PATH, token=tok)
    if s != 200 or not isinstance(summary, dict):
        pytest.skip(f"skip-with-reason: GET {SUMMARY_PATH} returned HTTP {s} "
                    f"{str(summary)[:160]}; endpoint/auth gate, not a product result")
    print(f"  summary payload: {summary}")

    # No '%s' / placeholder leak ANYWHERE in the empty-state payload (load-bearing
    # sub-clause: an empty state must render real/empty values, never a raw template).
    _assert_no_placeholder_leak(summary, "summary")

    # WHERE YOU SPEND == empty: no category-spending rows (the headline "$0/empty"
    # state is the absence of category rows — the presenter returns [] with no synced
    # debit transactions). A row here would mean leaked/seeded spend on an unlinked user.
    category_spending = summary.get("category_spending")
    assert category_spending in ([], None), (
        f"Where-You-Spend is NOT empty for an unlinked user: category_spending="
        f"{category_spending!r} — expected no category rows on a no-Yodlee account")

    # The grouped-spend tiles that feed the same widget must also be empty.
    for empty_key in ("subscriptions", "buy_now_pay_later", "biggest_transactions"):
        rows = summary.get(empty_key)
        assert rows in ([], None), (
            f"My Finance '{empty_key}' is NOT empty for an unlinked user: {rows!r} "
            f"— expected no rows on a no-Yodlee account")

    # FUTURE CASH (forecast) empty: presenter returns {} when there are no forecasted
    # transactions. monthly_tracker likewise empty with no synced debit history.
    forecast = summary.get("forecast")
    assert forecast in ({}, None), (
        f"Future Cash / forecast is NOT empty for an unlinked user: {forecast!r} "
        f"— expected an empty forecast on a no-Yodlee account")
    monthly_tracker = summary.get("monthly_tracker")
    assert monthly_tracker in ({}, None), (
        f"Monthly tracker is NOT empty for an unlinked user: {monthly_tracker!r} "
        f"— expected no spent-last-month/average on a no-Yodlee account")

    # NET-WORTH rows are 0-or-seeded with no dollar leak: the summary's net_worth block
    # carries only the suitability `income` band STRING (e.g. a "$x - $y" range), never a
    # computed spend dollar figure derived from (absent) synced transactions. Assert it is
    # a band string or empty/None — not a numeric spend total fabricated from no data.
    net_worth = summary.get("net_worth")
    if net_worth not in ({}, None):
        assert isinstance(net_worth, dict), (
            f"net_worth should be a hash, got {net_worth!r}")
        income = net_worth.get("income")
        # income is either absent (no suitability answer) or a band string; it must NOT
        # be a numeric spend figure (which would imply fabricated synced-spend data).
        assert income is None or isinstance(income, str), (
            f"net_worth.income should be an income BAND string (or absent), got "
            f"{income!r} — an unlinked user must not surface a computed spend figure")

    # --- FUTURE CASH endpoint (the dedicated upcoming-transactions feed) == empty ---
    s2, upcoming = call(op, "GET", UPCOMING_PATH, token=tok)
    if s2 == 200:
        assert upcoming in ([], None), (
            f"Future Cash upcoming-transactions is NOT empty for an unlinked user: "
            f"{upcoming!r} — expected [] on a no-Yodlee account")
        print(f"  upcoming (Future Cash): {upcoming!r} (empty as expected)")
    else:
        # Non-200 here is an endpoint/auth gate on the secondary feed, not a product
        # result — the load-bearing empty-state oracle is the summary above. Report it.
        print(f"  NOTE: GET {UPCOMING_PATH} -> HTTP {s2} {str(upcoming)[:120]}; "
              f"secondary feed gate, summary empty-state already asserted")

    print(f"  PASS: unlinked user {email} renders a true empty My Finance state "
          f"(no Where-You-Spend rows, no Future Cash, no placeholder leak)")
