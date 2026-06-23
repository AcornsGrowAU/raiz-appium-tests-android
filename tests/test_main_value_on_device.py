"""
ON-DEVICE VALUE RECONCILIATION — Main Portfolio card vs backend balance (TC-01, P0).

This targets the suite's #1 known weakness: presence-vs-value. The bulk of the suite
asserts an element is *visible*; here we assert the Main Portfolio card on Home renders
the EXACT backend balance the API reports for the same logged-in user.

Oracle:
  HomePage.get_account_card_value('Main Portfolio') parsed to float
    == genuser_api.current_balance(user) within abs band max($5, 3% of value);
  both values > 0.
We assert the CARD (under 'Total investments value'), NOT the lagging
'Your total investments value' headline tile.

Reuse strategy: the long-lived `presence_funded` fixture — an onboarded generated user
with an immediate (priced) Aggressive balance — so no fresh user is seeded per run.

Standalone (own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_main_value_on_device.py -v -s -o addopts=""
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
from utils.assertions import parse_money
from utils.genuser_api import current_balance
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")


def _wait_post_login(d, ho, timeout=30, poll=0.5):
    """Poll until the post-login transition settles on a terminal screen we can
    act on: either Home is loaded, or an onboarding screen is on-screen. Replaces
    a blind `time.sleep(7)` that under-waits on a slow emulator (1-3s RTT) and
    over-waits on a fast one. Returns 'home' or 'onboarding'; 'unknown' if neither
    appeared within the timeout (caller still asserts Home as the hard gate)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ho.is_loaded(timeout=1):
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
    """Log into the real app as the fixture user and land on Home (running the
    first-login onboarding gauntlet only if the app isn't already on Home)."""
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
    # Wait for the login form itself rather than sleeping a fixed beat; the splash
    # can hand off slowly on a cold emulator.
    assert lo.is_loaded(timeout=20), "login form did not load"
    lo.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    state = _wait_post_login(d, ho)
    if state != "home" and not ho.is_loaded(timeout=2):
        assert onb.complete(), f"onboarding stuck: {onb.path}"
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=20), "not on Home after login"
    return ho


def test_main_portfolio_card_matches_backend_balance():
    """The Main Portfolio account card on Home renders the exact backend
    current_balance for the logged-in generated user (value, not just presence)."""
    fx = get_or_create_fixture_user("presence_funded")

    # Backend truth for the SAME user we log in as.
    backend = current_balance(fx["email"], fx["password"])
    assert backend is not None, f"could not read backend current_balance for {fx['email']}"
    assert backend > 0, f"fixture user has a non-positive backend balance: ${backend}"

    opts = get_android_options(no_reset=False)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        ho = _login_and_home(d, fx)

        # Read the CARD value (under 'Total investments value'), not the headline tile.
        # The card label can paint a beat before its priced dollar amount lands on a
        # slow emulator, so poll a few times before concluding the value is absent —
        # this hardens against a transient None without changing the assertion.
        card_text = None
        for _ in range(6):
            card_text = ho.get_account_card_value("Main Portfolio")
            if card_text is not None:
                break
            time.sleep(1.0)
        assert card_text is not None, (
            "Main Portfolio card rendered no dollar amount "
            "(card missing or showing no value)"
        )
        card_value = parse_money(card_text)
        print(f"  Main Portfolio card={card_text!r} -> ${card_value:.2f} | "
              f"backend current_balance=${backend:.2f}")

        assert card_value > 0, f"Main Portfolio card value is non-positive: {card_text!r}"

        # Reconciliation band: max($5, 3% of the backend value) absolute tolerance.
        # The card is market-priced and can drift slightly from the API snapshot;
        # the band catches a real mismatch while tolerating live-pricing jitter.
        band = max(5.0, 0.03 * backend)
        delta = abs(card_value - backend)
        assert delta <= band, (
            f"Main Portfolio card ${card_value:.2f} does not match backend "
            f"${backend:.2f}: |delta|=${delta:.2f} exceeds band ${band:.2f}"
        )
        print(f"  PASS: card matches backend within ${band:.2f} (|delta|=${delta:.2f})")
    finally:
        try:
            d.quit()
        except Exception:
            pass
