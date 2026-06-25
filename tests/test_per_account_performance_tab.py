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
  Every Raiz Kid and Jar is its own backend User (a `dependent` / `jar`
  sub-User hanging off the parent) with its own holdings + login, so its
  Performance headline is fed by its OWN `current_balance`. Reading
  `GET /v1/user -> current_balance` from each entity's session reconciles the
  SAME number the device would render in that account's Performance tile,
  with no Appium/market-drift flakiness — exactly what "API-layer first" asks.

  Graph range pills (`PerformanceMainChartTabs.kt`), change-in-value and
  returns are deliberately NOT touched: gen users carry no fund price history,
  so those read 0 / flat and would be a vacuous or misleading oracle.

ORACLE this test enforces:
  For BOTH the jars fixture and the kids fixture, per parent:
    (1) Each sub-account's Performance headline (== its backend current_balance)
        is read live from that sub-account's OWN session.
    (2) Each sub-account headline  !=  the Main (parent) headline, beyond band
        — the per-account tab does NOT just echo Main.
    (3) The two siblings differ from EACH OTHER beyond band — the headline is
        genuinely per-account (a screen-wide scrape could not tell them apart);
        this is the load-bearing check.
    (4) Each sub-account headline == its known seeded ACH balance within band
        (reconciles to backend ground truth).
  No graph / return / Δ assertion anywhere.

FIXTURES (existing, per the provision manifest):
  `jars_siblings_distinct` — parent + two named jars at a.<email>/b.<email>,
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

from utils.genuser_api import current_balance
from utils.genuser_fixtures import (
    get_or_create_fixture_user,
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


def _headline(label, email):
    """The per-account Performance-tab headline == that account's backend
    current_balance, read from the account's OWN session. (Balance ONLY — no
    graph/return/Δ; gen users have no price history.)

    Retries once on a transient None (a /v1/sessions rate-limit can exhaust the
    mint budget and return no token), so a recoverable login flap does not fail
    the value oracle."""
    bal = current_balance(email)
    if bal is None:
        time.sleep(8)
        bal = current_balance(email)
    assert bal is not None, (
        f"{label}: could not read current_balance (the Performance-tab headline "
        f"source) for {email} — login/endpoint failure")
    print(f"  {label} {email[:30]}: Performance headline = ${bal:.2f}")
    return bal


def _recon_band(seed):
    """Reconciliation tolerance for a seeded balance: proportional to the seed
    (absorbs share repricing) with an absolute floor (cents rounding)."""
    return max(RECON_FLOOR, RECON_PCT * seed)


def _assert_per_account_performance(kind, parent_email,
                                    a_seed, b_seed):
    """Shared body for both jars and kids: each sibling's Performance headline
    reconciles to its seeded balance, differs from Main, and differs from its
    sibling. Returns (main, a, b) balances."""
    a_email = "a." + parent_email
    b_email = "b." + parent_email

    main = _headline(f"{kind}-Main(parent)", parent_email)
    a = _headline(f"{kind}-A", a_email)
    b = _headline(f"{kind}-B", b_email)

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

    main, a, b = _assert_per_account_performance(
        "Jar", parent_email, JAR_A_BALANCE, JAR_B_BALANCE)

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

    main, a, b = _assert_per_account_performance(
        "Kid", parent_email, KID_A_BALANCE, KID_B_BALANCE)

    print(f"  PASS: Kid Performance headlines A=${a:.2f} B=${b:.2f} both differ "
          f"from Main=${main:.2f} and from each other, and each reconciles to "
          f"its seeded balance (${KID_A_BALANCE:,}/${KID_B_BALANCE:,}).")
