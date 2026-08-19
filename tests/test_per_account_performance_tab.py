"""
per-account-performance-tab (P2, data_mode reuse-fixture) — API-LAYER recon.

BACKLOG ORACLE (refined, row `per-account-performance-tab`):
  "Per-account Performance tab headline differs from Main + reconciles to its
  backend balance."
  Refinement (notes column — HONOURED here):
    - Reuse jars/kids sibling fixtures.
    - Jar/Kid Performance-tab headline  !=  Main  AND  == sub-account
      current_balance, within a band.
    - **Reconcile balance ONLY; assert NO graph / return / Δ** (gen users have
      NO price history — see memory genuser-performance-graph-gap; any
      graph/return/change oracle on a gen user is invalid).
    - "Un-skip the existing data-adaptive tests" — there is no prior
      per-account-performance test file in the suite (this case introduces it),
      so the refinement is satisfied by shipping this reconciliation directly
      rather than un-skipping a stub.

WHY API-LAYER (no device, deterministic):
  The Performance screen renders ONE value tile PER account via the account
  carousel (features/performancev2 `PerformanceMainScreen.kt` +
  `PerformanceAccountsCarousel.kt` / `PerformanceAccountUi.kt`
  / `PerformanceFeatureType.kt`): Regular (Main), Kids(dependentUserId),
  Jars(jarId), Super. Each `PerformanceAccountUi` exposes an
  `abstract val balance: Double` — i.e. the headline figure on each account's
  Performance tab IS that account's balance, and the carousel shows Main and
  each sub-account side by side with DISTINCT balances.
  Every Raiz Kid and Jar is its own backend sub-User (`dependent` / `jar`)
  hanging off the parent with its own holdings, but their SESSIONS differ:
  kids CAN log in (fixtures set kid_account_data.account_access), so a kid's
  headline is read as `GET /v1/user -> current_balance` from the KID's own
  session; jars have NO loginable identity (a jar-email /v1/sessions 401s by
  design), so a jar's headline balance (accumulated_amount) is read through
  the PARENT's session via `jar_balance_by_name`. Either way this reconciles
  the SAME number the device would render in that account's Performance tile,
  with no Appium/market-drift flakiness — exactly what "API-layer first" asks.

  Graph range pills (`PerformanceMainChartTabs.kt`), change-in-value and
  returns are deliberately NOT touched: gen users carry no fund price history,
  so those read 0 / flat and would be a vacuous or misleading oracle.

ORACLE this test enforces:
  For BOTH the jars fixture and the kids fixture, per parent:
    (1) Each sub-account's Performance headline (== its backend balance) is
        read live — kids from their OWN session, jars via the PARENT session.
    (2) Each sub-account headline  !=  the Main (parent) headline, beyond band
        — the per-account tab does NOT just echo Main.
    (3) The two siblings differ from EACH OTHER beyond band — the headline is
        genuinely per-account (a screen-wide scrape could not tell them apart);
        this is the load-bearing check.
    (4) Each sub-account headline == its known seeded ACH balance within band
        (reconciles to backend ground truth).
  No graph / return / Δ assertion anywhere.

FIXTURES (existing, per the provision manifest):
  `jars_siblings_distinct` — parent + two named jars (JAR_A_NAME / JAR_B_NAME,
    read by name via the parent session — jar sub-account emails cannot log in),
    seeded ACH balances JAR_A_BALANCE / JAR_B_BALANCE.
  `kids_siblings_distinct` — parent + two kids at a.<email>/b.<email>,
    seeded ACH balances KID_A_BALANCE / KID_B_BALANCE.
  Reused per the reuse strategy; nothing is mutated. No emulator.

needs_device: FALSE — pure DEV-API value test.
Run (no emulator):
  venv/bin/python -m pytest tests/test_per_account_performance_tab.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import current_balance, jar_users
from utils.genuser_fixtures import (
    get_or_create_fixture_user,
    JAR_A_NAME, JAR_B_NAME,
    JAR_A_BALANCE, JAR_B_BALANCE,
    KID_A_BALANCE, KID_B_BALANCE,
)

pytestmark = pytest.mark.value_api

# RECONCILIATION band (headline == that account's seeded backend balance).
#
# An ACH lump-sum credit here carries the `with_holdings`/`with_shares_settled_status`
# traits, so it buys real fund SHARES — and those shares REPRICE with the market over
# the fixture's lifetime (empirically: a $4,000 seed read $4,004.34 and a $1,200 seed
# read $1,201.30 days later — a clean, identical ~0.11% repricing on both, NOT a cents
# rounding error). A tiny absolute band therefore goes stale and the test grows flakier
# as the reused fixture ages. We band PROPORTIONALLY instead: ±RECON_PCT of the seed
# absorbs realistic repricing drift, with a small absolute FLOOR for cents rounding on
# small balances. This still catches every real break — a wrong account, an echo of
# Main, or a leaked credit is dollars-to-hundreds off (orders of magnitude beyond any
# plausible repricing), never within a fraction of a percent.
RECON_PCT = 0.05      # 5% — comfortably > observed repricing, << any real mis-read
RECON_FLOOR = 1.50    # absolute floor (cents rounding on small seeds)
# The "differs from Main / from sibling" separations are dollars apart by design
# (the fixtures seed deliberately distinct balances), so anything within this
# margin means the headline is NOT distinct — a real failure, not read jitter.
DISTINCT_MARGIN = 5.00


def _headline(label, read, source):
    """The per-account Performance-tab headline balance, read via `read()`:
    Main and kids from that account's OWN session (kids can log in); jars
    through the PARENT's session (jars have no loginable identity — the jar's
    accumulated_amount IS its headline balance). (Balance ONLY — no
    graph/return/Δ; gen users have no price history.)

    Retries once on a transient None (a /v1/sessions rate-limit can exhaust the
    mint budget and return no token), so a recoverable read flap does not fail
    the value oracle."""
    bal = read()
    if bal is None:
        time.sleep(8)
        bal = read()
    assert bal is not None, (
        f"{label}: could not read the Performance-tab headline balance via "
        f"{source} — session/endpoint failure")
    print(f"  {label} [{source}]: Performance headline = ${bal:.2f}")
    return bal


def _recon_band(seed):
    """Reconciliation tolerance for a seeded balance: proportional to the seed
    (absorbs share repricing) with an absolute floor (cents rounding)."""
    return max(RECON_FLOOR, RECON_PCT * seed)


def _assert_per_account_performance(kind, parent_email, a_seed, b_seed,
                                    read_a, read_b, a_src, b_src):
    """Shared body for both jars and kids: each sibling's Performance headline
    reconciles to its seeded balance, differs from Main, and differs from its
    sibling. `read_a`/`read_b` are zero-arg callables returning that sibling's
    headline balance (kids: own-session current_balance; jars: parent-session
    jar_balance_by_name), with `a_src`/`b_src` describing the read for failure
    messages. Returns (main, a, b) balances."""
    main = _headline(f"{kind}-Main(parent)",
                     lambda: current_balance(parent_email),
                     f"own session {parent_email[:30]}")
    a = _headline(f"{kind}-A", read_a, a_src)
    b = _headline(f"{kind}-B", read_b, b_src)

    # (4) reconcile each sub-account headline to its KNOWN seeded ACH balance,
    # within a repricing-aware proportional band (see _recon_band / RECON_PCT).
    a_band, b_band = _recon_band(a_seed), _recon_band(b_seed)
    assert abs(a - a_seed) <= a_band, (
        f"{kind}-A Performance headline ${a:.2f} does not reconcile to its "
        f"seeded balance ${a_seed:.2f} (band ±${a_band:.2f})")
    assert abs(b - b_seed) <= b_band, (
        f"{kind}-B Performance headline ${b:.2f} does not reconcile to its "
        f"seeded balance ${b_seed:.2f} (band ±${b_band:.2f})")

    # (2) each sub-account headline differs from Main — the per-account tab is
    # NOT just echoing the parent/Main figure.
    assert abs(a - main) > DISTINCT_MARGIN, (
        f"{kind}-A Performance headline ${a:.2f} == Main ${main:.2f} within "
        f"${DISTINCT_MARGIN} — the per-account tab must differ from Main")
    assert abs(b - main) > DISTINCT_MARGIN, (
        f"{kind}-B Performance headline ${b:.2f} == Main ${main:.2f} within "
        f"${DISTINCT_MARGIN} — the per-account tab must differ from Main")

    # (3) the load-bearing per-account check: the two siblings differ from EACH
    # OTHER, so the headline is genuinely scoped to one account (not a
    # screen-wide value read twice).
    assert abs(a - b) > DISTINCT_MARGIN, (
        f"{kind} siblings have indistinguishable Performance headlines "
        f"(A ${a:.2f} vs B ${b:.2f}) — the headline is not per-account, or the "
        f"fixture is not seeded as expected")

    return main, a, b


def test_jar_performance_tab_headline_differs_from_main_and_reconciles():
    """Each Jar's Performance-tab headline == that jar's backend balance,
    differs from Main and from its sibling. Balance ONLY (no graph/Δ/return)."""
    fx = get_or_create_fixture_user("jars_siblings_distinct")  # reused if seeded
    parent_email = fx["email"]
    print(f"  fixture '{fx['key']}' parent={parent_email} "
          f"(reused={fx.get('reused')})")

    # Jars have no loginable identity — read each NAMED jar's balance through the
    # PARENT's session. EFF-02: fetch the parent's jar list ONCE and index by name
    # (instead of two jar_balance_by_name calls, each its own parent login + jars
    # GET). The cached map re-fetches only while it holds nothing, so _headline's
    # retry still recovers a transient empty read without extra logins on success.
    _jar_bal = {}

    def _jar_map():
        if not _jar_bal:
            for j in (jar_users(parent_email) or []):
                if isinstance(j, dict) and j.get("name") is not None \
                        and j.get("accumulated_amount") is not None:
                    _jar_bal[j["name"]] = float(j["accumulated_amount"])
        return _jar_bal

    main, a, b = _assert_per_account_performance(
        "Jar", parent_email, JAR_A_BALANCE, JAR_B_BALANCE,
        read_a=lambda: _jar_map().get(JAR_A_NAME),
        read_b=lambda: _jar_map().get(JAR_B_NAME),
        a_src=f"parent-session jars read, name={JAR_A_NAME!r}",
        b_src=f"parent-session jars read, name={JAR_B_NAME!r}")

    print(f"  PASS: Jar Performance headlines A=${a:.2f} B=${b:.2f} both differ "
          f"from Main=${main:.2f} and from each other, and each reconciles to "
          f"its seeded balance (${JAR_A_BALANCE:,}/${JAR_B_BALANCE:,}).")


def test_kid_performance_tab_headline_differs_from_main_and_reconciles():
    """Each Kid's Performance-tab headline == that kid's backend balance,
    differs from Main and from its sibling. Balance ONLY (no graph/Δ/return)."""
    fx = get_or_create_fixture_user("kids_siblings_distinct")  # reused if seeded
    parent_email = fx["email"]
    print(f"  fixture '{fx['key']}' parent={parent_email} "
          f"(reused={fx.get('reused')})")

    # Kids CAN log in (kid_account_data.account_access) — read each kid's
    # headline from the kid's OWN session, unchanged.
    a_email = "a." + parent_email
    b_email = "b." + parent_email
    main, a, b = _assert_per_account_performance(
        "Kid", parent_email, KID_A_BALANCE, KID_B_BALANCE,
        read_a=lambda: current_balance(a_email),
        read_b=lambda: current_balance(b_email),
        a_src=f"kid's own session {a_email[:32]}",
        b_src=f"kid's own session {b_email[:32]}")

    print(f"  PASS: Kid Performance headlines A=${a:.2f} B=${b:.2f} both differ "
          f"from Main=${main:.2f} and from each other, and each reconciles to "
          f"its seeded balance (${KID_A_BALANCE:,}/${KID_B_BALANCE:,}).")
