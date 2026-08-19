"""
PERFORMANCE ACCOUNT-ISOLATION E2E — regression guard for RAIZ-10867
(fixed in release 2.41.2).

THE BUG (RAIZ-10867): the Performance screen's data cache keyed each series only by
`(period_of_days, type)` with NO account_id. Switching the Performance view between
accounts (Main / Jar / Kid / Super) — and between time periods — served a cache HIT
for a DIFFERENT account, so the wrong account's figures were shown (e.g. an empty
jar rendered a kid's series). The fix adds the account_id to the cache key
(features/performancev2 PerformanceMainViewModel.kt `summaryResults[cacheKey to
selectedRange]` / `oneDayLoadedAccountIds`, where cacheKey = jarId | dependentUserId;
PerformanceAccountSelection.kt; raizCore GetPerformanceSummaryModel.jarId/
dependentUserId).

WHAT A RED PROVES: on-device, after viewing account A's Performance, switching to
account B (a different chip in the PerformanceAccountsCarousel) — and after changing
the time range — the headline value tile still shows A's figure instead of B's. That
is exactly the account-bleed RAIZ-10867 was about: the value surfaced for the
selected account is not that account's own. A green proves each selected account's
headline reconciles to THAT account's OWN backend balance, is DISTINCT from the
other account's, and that re-selecting A brings A's own value back (no sticky bleed
in either direction, across an account switch AND a period switch).

ORACLE (isolation; balance ONLY — see below on %-change):
  Log in AS the parent of two named jars of DISTINCT balances and open Performance
  (raiz://performance). The carousel shows Main + Jar A + Jar B; selecting a chip
  swaps the single headline tile to that account's value
  (PerformanceMainViewModel.onAccountSelected -> _balanceState = account.balance,
  where balance is the account's own currentBalance/accumulatedAmount — the same
  number the parent-session API reads). Then:
    1. Select Jar A -> settled headline == Jar A's OWN backend balance (band).
    2. Select Jar B -> settled headline == Jar B's OWN backend balance (band) AND
       is DISTINCT from A's reading (a bleed would echo A here).
    3. Change the time range while on B -> headline STILL == Jar B's balance
       (the (period, account) cache path must not re-serve A across a period switch).
    4. Re-select Jar A -> headline == Jar A's balance again (A returns; B did not
       stick).
  Reconciling each account's headline to its OWN distinct backend ground truth is the
  load-bearing check: because the two backend balances are dollars apart (far beyond
  the reconciliation band), a value that reconciles to A can NEVER reconcile to B, so
  a bleed in either direction fails at least one reconcile. An explicit distinctness
  assertion is added on top as belt-and-suspenders.

WHY BALANCE, NOT %-change: the change-in-value / % figure is derived from fund PRICE
HISTORY, and generated users carry none (memory: genuser-performance-graph-gap), so
%-change reads flat/$0 for every account and cannot distinguish A from B — asserting
it here would be vacuous. We therefore isolate on the headline VALUE (the account's
own balance), which is well-defined and distinct per account. The per-account change
text is read and LOGGED for diagnostics only.

FIXTURE (reused, per the reuse strategy — NOT re-seeded per run):
  `jars_siblings_distinct` — one parent + two NAMED jars (JAR_A_NAME / JAR_B_NAME)
  of distinct ACH-settled balances (JAR_A_BALANCE / JAR_B_BALANCE). Jars have no
  loginable identity, so each jar's ground-truth balance (accumulated_amount) is read
  through the PARENT's session (BalanceReader.jar_balance_by_name). The device logs in
  AS the parent so both jar chips appear in one carousel under one login.

Standalone (own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_performance_account_isolation.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.performance_page import PerformancePage
from utils.assertions import is_money, parse_money
from utils.deep_links import DeepLinks
from utils.genuser_api import BalanceReader, SEEDED_PWD
from utils.genuser_fixtures import (
    get_or_create_fixture_user, mark_onboarded,
    JAR_A_NAME, JAR_B_NAME, JAR_A_BALANCE, JAR_B_BALANCE,
)

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.performance, pytest.mark.jars]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")


# Reconciliation band: the headline is a market-priced accumulated_amount that can
# reprice slightly off the seeded dollars, so we band PROPORTIONALLY (max($5, 5%)) —
# the suite's "banded-for-market" convention (mirrors test_per_account_performance_tab
# RECON_PCT and the on-device jar/main value E2Es). Far tighter than the ~$2,800 gap
# between the two seeded jars, so it still catches any real account bleed.
def _band(expected):
    return max(5.0, abs(expected) * 0.05)


# A headline switch between two distinct accounts moves the value by hundreds/
# thousands of dollars; this margin only needs to clear cents-level render jitter so
# the settle poll knows the recompose to the newly-selected account has landed.
SWITCH_MARGIN = 1.00
# Distinctness floor for the A-vs-B belt-and-suspenders check (seeds are dollars
# apart by design; this only guards they are genuinely different readings).
DISTINCT_MARGIN = 5.00

SETTLE_TIMEOUT = int(os.getenv("PERF_SETTLE_TIMEOUT", "30"))


def _settled_headline(perf: PerformancePage, prev=None, timeout=SETTLE_TIMEOUT, poll=0.5):
    """Poll the per-account headline until it is well-formed money that is STABLE
    across two consecutive reads (never latch onto a transient '--'/Loading or a
    mid-recompose value). When `prev` is given, also wait until the value has moved
    away from `prev` by more than SWITCH_MARGIN — i.e. the switch to the newly
    selected account has actually taken effect — so we don't read the outgoing
    account's stale value.

    This is a WAIT condition, not the oracle: on timeout it returns the last stable
    money read even if it never moved off `prev`, so the caller's reconcile assertion
    fails LOUDLY (that stuck-on-`prev` case is exactly the RAIZ-10867 bleed). Returns
    a float, or None if no money ever rendered."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        raw = perf.read_headline_amount()
        if is_money(raw):
            val = parse_money(raw)
            if last is not None and abs(val - last) < 0.005:  # stable across 2 reads
                if prev is None or abs(val - prev) > SWITCH_MARGIN:
                    return val
            last = val
        else:
            last = None
        time.sleep(poll)
    return last


def _read_account(perf: PerformancePage, chip_title: str, expect_type: str, prev):
    """Select the carousel chip `chip_title`, wait for the headline to settle to the
    newly-selected account (away from `prev`), and return (value, change_text).
    Asserts the chip was found and the account TYPE header matches `expect_type`."""
    assert perf.select_account_chip(chip_title), \
        f"could not find/tap the Performance account chip {chip_title!r}"
    # Confirm the account TYPE switched (Main vs Jars vs Kids header). This does not
    # distinguish sibling jars — the VALUE does — but proves we left the prior type.
    deadline = time.time() + 10
    while time.time() < deadline and perf.current_header_type() != expect_type:
        time.sleep(0.5)
    assert perf.current_header_type() == expect_type, (
        f"after selecting {chip_title!r} the header type is "
        f"{perf.current_header_type()!r}, expected {expect_type!r}")
    val = _settled_headline(perf, prev=prev)
    change = ""
    try:
        change = perf.get_change_value()
    except Exception:
        pass
    print(f"  [{chip_title}] headline={val} change_text={change!r}")
    return val, change


# ----- login / navigation helpers (mirror the on-device value E2Es) ----------------
def _login_as_parent(d, email, pwd):
    """Log the parent into the app and land on Home, running first-login onboarding
    once if it appears. Polls for the splash/Home rather than sleeping a fixed beat
    (login RTT varies on a slow emulator)."""
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_visible(sp.TAGLINE, timeout=15):
        sp.tap_log_in()
    assert lo.is_loaded(timeout=20), "login form did not load"
    lo.login(email, pwd)
    if not ho.is_visible(ho.TOTAL_VALUE_LABEL, timeout=30):
        onb = OnboardingPage(d)
        assert onb.complete(), f"onboarding stuck at {onb.path}"
        assert ho.is_visible(ho.TOTAL_VALUE_LABEL, timeout=20), \
            "parent not on Home after completing onboarding"
    try:
        ho.dismiss_modal()
    except Exception:
        pass
    assert ho.is_present_now(ho.TOTAL_VALUE_LABEL), "parent not on Home after login"
    return ho


def _open_performance(d) -> PerformancePage:
    """Open the Performance screen and wait for the account carousel to populate.
    Retries the deep link once (the chart can be slow to render), mirroring the
    conftest `performance` fixture."""
    perf = PerformancePage(d)
    for _ in range(2):
        DeepLinks.open(d, DeepLinks.PERFORMANCE)
        if perf.is_loaded(timeout=15):
            break
    assert perf.is_loaded(), "Performance screen did not load"
    try:
        perf.dismiss_modal()
    except Exception:
        pass
    assert perf.has_account_carousel(timeout=30), (
        "Performance account carousel never populated — the parent's Main + jar "
        "chips should render (PerformanceAccountsCarousel)")
    return perf


def test_performance_headline_is_isolated_per_account():
    """Switching the Performance view between two sibling jars (and changing the time
    range) always shows the SELECTED account's own value — never the other jar's —
    proving the RAIZ-10867 account-bleed is fixed."""
    fx = get_or_create_fixture_user("jars_siblings_distinct")  # reused if seeded
    parent_email = fx["email"]
    print(f"  fixture '{fx['key']}' parent={parent_email} (reused={fx.get('reused')})")

    # Backend ground truth per jar, read through the PARENT's session (jars have no
    # loginable identity). One minted session serves both reads (BalanceReader),
    # retried once on a transient None from the rate-limited sessions endpoint.
    reader = BalanceReader(parent_email, fx.get("password", SEEDED_PWD))

    def _jar_backend(name):
        bal = reader.jar_balance_by_name(name)
        if bal is None:
            time.sleep(8)
            bal = reader.jar_balance_by_name(name)
        return bal

    bal_a = _jar_backend(JAR_A_NAME)
    bal_b = _jar_backend(JAR_B_NAME)
    assert bal_a is not None, f"could not read backend balance for jar {JAR_A_NAME!r}"
    assert bal_b is not None, f"could not read backend balance for jar {JAR_B_NAME!r}"
    # Precondition: the two jars must be genuinely distinct, else a bleed is
    # undetectable and the isolation oracle is vacuous.
    assert abs(bal_a - bal_b) > (DISTINCT_MARGIN + _band(bal_a) + _band(bal_b)), (
        f"sibling jars are not distinct enough to detect a bleed: "
        f"A ${bal_a:.2f} vs B ${bal_b:.2f}")
    print(f"  backend truth: {JAR_A_NAME!r}=${bal_a:.2f} (~${JAR_A_BALANCE:,}), "
          f"{JAR_B_NAME!r}=${bal_b:.2f} (~${JAR_B_BALANCE:,})")

    chip_a = PerformancePage.jar_chip_title(JAR_A_NAME)
    chip_b = PerformancePage.jar_chip_title(JAR_B_NAME)

    opts = get_android_options(no_reset=False, secondary=True)  # fresh app data
    opts.udid = UDID
    # Disable the MJPEG broadcaster on this test-owned session (a 2nd broadcaster on
    # the 2GB emulator is the documented OOM tipping point; failure screenshots use
    # the W3C path, not MJPEG). Mirrors the other on-device genuser E2Es.
    opts.set_capability("mjpegServerPort", 0)
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_as_parent(d, parent_email, fx.get("password", SEEDED_PWD))
        if not fx.get("onboarded"):
            mark_onboarded(fx["key"])
        perf = _open_performance(d)

        # Main is preselected on open; capture its displayed value so the first
        # switch (Main -> Jar A) can wait for the headline to move off it.
        main_raw = perf.read_headline_amount()
        main_val = parse_money(main_raw) if is_money(main_raw) else None
        print(f"  Main (preselected) headline={main_raw!r}")

        # (1) Select Jar A -> reconciles to A's own backend balance.
        a_val, a_change = _read_account(perf, chip_a, "jar", prev=main_val)
        assert a_val is not None, f"Jar A ({chip_a!r}) rendered no headline value"
        assert abs(a_val - bal_a) <= _band(bal_a), (
            f"Jar A headline ${a_val:.2f} does not reconcile to its backend balance "
            f"${bal_a:.2f} (band ${_band(bal_a):.2f})")

        # (2) Select Jar B -> reconciles to B's OWN backend balance, distinct from A.
        b_val, b_change = _read_account(perf, chip_b, "jar", prev=a_val)
        assert b_val is not None, f"Jar B ({chip_b!r}) rendered no headline value"
        assert abs(b_val - bal_b) <= _band(bal_b), (
            f"Jar B headline ${b_val:.2f} does not reconcile to its backend balance "
            f"${bal_b:.2f} (band ${_band(bal_b):.2f}) — a value matching Jar A "
            f"(${bal_a:.2f}) here is the RAIZ-10867 account bleed")
        assert abs(b_val - a_val) > DISTINCT_MARGIN, (
            f"Jar B headline ${b_val:.2f} is indistinguishable from Jar A "
            f"${a_val:.2f} — the headline bled A's value across the account switch")

        # (3) Change the time range while on Jar B -> the (period, account) cache path
        # must NOT re-serve Jar A. The headline value is the account's own balance and
        # does not depend on the range, so it must STILL reconcile to Jar B.
        perf.select_time_range("1M")
        b_val_1m = _settled_headline(perf, prev=None)
        b_1m_change = ""
        try:
            b_1m_change = perf.get_change_value()
        except Exception:
            pass
        print(f"  [Jar B @1M] headline={b_val_1m} change_text={b_1m_change!r}")
        assert b_val_1m is not None, "Jar B headline vanished after the period switch"
        assert abs(b_val_1m - bal_b) <= _band(bal_b), (
            f"After switching to the 1M range, Jar B headline ${b_val_1m:.2f} no longer "
            f"reconciles to Jar B ${bal_b:.2f} (band ${_band(bal_b):.2f}) — a period "
            f"switch bled another account's data (RAIZ-10867)")

        # (4) Re-select Jar A -> A's own value returns (B did not stick either way).
        a_val_again, _ = _read_account(perf, chip_a, "jar", prev=b_val_1m)
        assert a_val_again is not None, "Jar A rendered no headline value on re-select"
        assert abs(a_val_again - bal_a) <= _band(bal_a), (
            f"On re-selecting Jar A its headline ${a_val_again:.2f} does not reconcile "
            f"to Jar A ${bal_a:.2f} (band ${_band(bal_a):.2f}) — Jar B's value stuck "
            f"after the switch (RAIZ-10867)")
        assert abs(a_val_again - b_val) > DISTINCT_MARGIN, (
            f"On re-selecting Jar A the headline ${a_val_again:.2f} still equals Jar B "
            f"${b_val:.2f} — B's value bled into A")

        print(f"  PASS: Performance headline is per-account — "
              f"A=${a_val:.2f}/re-A=${a_val_again:.2f} (backend ${bal_a:.2f}), "
              f"B=${b_val:.2f}/B@1M=${b_val_1m:.2f} (backend ${bal_b:.2f}); "
              f"distinct across an account switch AND a period switch.")
    finally:
        try:
            d.quit()
        except Exception:
            pass
