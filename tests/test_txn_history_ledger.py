"""
ON-DEVICE Transaction-History LEDGER correctness E2E (TC-11, P2).

Reuse strategy: a stored fixture user (`history_seeded_deposit`) carries ONE known
ACH credit of utils.genuser_fixtures.HISTORY_SEEDED_DEPOSIT dollars (seeded once,
reused thereafter). The test logs into the real app AS that user, opens Transaction
History, and asserts two things that go beyond mere element presence:

  1. LEDGER CORRECTNESS — at least one history row's PARSED dollar amount equals the
     seeded deposit value AND its type is a deposit/investment (a lump-sum ACH credit
     renders as a 'Buy' row). This is the VALUE oracle, not a bare row count.
  2. SURVIVES FILTER-CANCEL (RAIZ-10063 class) — opening the Filter sheet and then
     CANCELLING it (no Apply) must leave the list intact: the same seeded row is still
     present and the total visible row count is unchanged.

Standalone (manages its own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_txn_history_ledger.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST, DEFAULT_WAIT, STATE_PROBE_WAIT
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.pin_page import PinPage
from pages.transaction_history_page import TransactionHistoryPage
from utils.deep_links import DeepLinks
from utils.genuser_api import current_balance
from utils.genuser_fixtures import (
    HISTORY_SEEDED_DEPOSIT,
    get_or_create_fixture_user,
    mark_onboarded,
)

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.portfolio]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")


def _wait_post_login(d, home, timeout=30, poll=0.5):
    """Poll until the post-login transition settles on a terminal screen we can
    act on: either Home is loaded, or an onboarding screen is on-screen. Replaces
    the blind sleeps that under-wait on a slow emulator (1-3s RTT) and over-wait
    on a fast one. Returns 'home' or 'onboarding'; 'unknown' if neither appeared
    within the timeout (the caller still asserts Home as the hard gate)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if home.is_loaded(timeout=1):
            return "home"
        # Any onboarding gate on screen (PDS/checklist/portfolio/initial-invest
        # all surface one of these affordances) means we can hand off to
        # onb.complete(); these keywords mirror the taps that complete() makes.
        src = (d.page_source or "").lower()
        if any(k in src for k in ("skip", "got it", "select as your portfolio",
                                  "i consent", "agree")):
            return "onboarding"
        time.sleep(poll)
    return "unknown"


def _login_and_home(d, fx):
    """Log into the app as the fixture user and land on Home (running first-login
    onboarding once if this fixture hasn't been onboarded yet).

    Uses condition-based waits (login form, then a post-login settle poll) instead
    of fixed sleeps: identical behaviour, but it stops as soon as each transition
    actually completes and only waits the full budget when the emulator is slow."""
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    if splash.is_present_now(splash.TAGLINE):
        splash.tap_log_in()
    # Wait for the login form itself rather than sleeping a fixed beat; the splash
    # can hand off slowly on a cold emulator.
    assert login.is_loaded(timeout=20), "login form did not load"
    login.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    state = _wait_post_login(d, home)
    if state != "home" and not home.is_loaded(timeout=2):
        assert onb.complete(), f"onboarding stuck at {getattr(onb, 'path', None)}"
        mark_onboarded(fx["key"])
    assert home.is_loaded(timeout=20), "not on Home after login"
    return home


def _open_history(d):
    """Deep-link to Transaction History, entering the PIN if the app prompts.

    The deep link can land on a PIN re-prompt OR be dropped entirely while the
    app is still settling after login, so we retry the navigation a few times and
    rely on explicit waits (not fixed sleeps) for each transient surface. Once the
    screen mounts we additionally wait for the LIST ROWS to render, because the
    title paints before the network-loaded rows arrive — returning early here is
    what made the seeded-deposit assertion intermittently see an empty list."""
    from config.settings import TEST_PIN
    history = TransactionHistoryPage(d)
    pin = PinPage(d)
    for attempt in range(3):
        DeepLinks.open(d, DeepLinks.TRANSACTIONS)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            pin.enter_pin(TEST_PIN)
        if history.is_loaded(timeout=DEFAULT_WAIT):
            history.wait_for_rows()
            return history
    assert history.is_loaded(), "Transaction History did not open"
    history.wait_for_rows()
    return history


def test_history_contains_seeded_deposit_and_survives_cancel():
    fx = get_or_create_fixture_user("history_seeded_deposit")  # reused if already seeded
    # Sanity-check the seed landed on the backend (the credit lifts the balance).
    api_balance = current_balance(fx["email"])
    print(f"  fixture '{fx['key']}' {fx['email']} (reused={fx.get('reused')}) "
          f"backend balance=${api_balance} | seeded deposit=${HISTORY_SEEDED_DEPOSIT}")
    assert api_balance and api_balance > 0, f"fixture has no balance: {api_balance}"

    opts = get_android_options(no_reset=False)  # fresh app data
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)
        history = _open_history(d)

        # (1) LEDGER CORRECTNESS: a deposit/investment row exists whose parsed
        # amount equals the seeded dollar value.
        matches = history.find_deposit_rows_matching(HISTORY_SEEDED_DEPOSIT)
        print(f"  deposit rows matching ${HISTORY_SEEDED_DEPOSIT}: "
              f"{[(m['type'], m['amount']) for m in matches]}")
        assert matches, (
            f"expected a deposit/investment row of ${HISTORY_SEEDED_DEPOSIT} in "
            f"Transaction History, found none "
            f"(visible rows: {[(r['type'], r['amount']) for r in history.get_transactions(limit=30)]})"
        )
        matched_row = matches[0]
        assert matched_row["type"] in ("Buy",), \
            f"seeded credit should render as a deposit/investment (Buy) row, got {matched_row['type']!r}"

        # Baseline visible-row count BEFORE touching the filter.
        count_before = history.get_transaction_count()
        assert count_before >= 1, "expected at least one transaction row before filtering"
        print(f"  visible rows before filter-cancel: {count_before}")

        # (2) SURVIVES FILTER-CANCEL (RAIZ-10063): open the filter sheet, cancel it
        # (no Apply), and confirm the list is intact — same seeded row still present
        # and the visible row count unchanged.
        assert history.cancel_filter(), "did not return to the history list after cancelling the filter"

        count_after = history.get_transaction_count()
        print(f"  visible rows after filter-cancel: {count_after}")
        assert count_after == count_before, (
            f"row count changed after cancelling the filter "
            f"({count_before} -> {count_after}); list was not preserved (RAIZ-10063 class)"
        )

        still_there = history.find_deposit_rows_matching(HISTORY_SEEDED_DEPOSIT)
        assert still_there, (
            f"seeded ${HISTORY_SEEDED_DEPOSIT} deposit row disappeared after cancelling "
            f"the filter — the list was not refreshed/restored (RAIZ-10063 class)"
        )
        print(f"  PASS: seeded ${HISTORY_SEEDED_DEPOSIT} deposit present and survived "
              f"filter-cancel (rows {count_before} == {count_after})")
    finally:
        try:
            d.quit()
        except Exception:
            pass
