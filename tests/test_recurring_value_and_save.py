"""
TC-14 [P3] — Recurring 'Current balance' == backend, and Save button well-rendered
(RAIZ-9909).

Two VALUE/layout oracles on the Recurring main-portfolio setup screen, the screen
where RAIZ-9909 ("Save button obstructed and small") lived:

  1. VALUE: the setup screen renders 'Current balance: $X' for the main portfolio.
     We parse X and assert it equals the backend current_balance the API reports for
     the SAME logged-in user (within a small reconciliation band) — not just that a
     dollar amount is present. This targets the suite's presence-vs-value weakness.

  2. LAYOUT (RAIZ-9909): after opening 'Set Recurring Investment', the Save button
     must render at a usable tap-target size. RecurringPage.is_save_button_well_rendered()
     measures the button's bounds and requires it be displayed and large enough — a
     presence check would sail straight past the "obstructed and small" defect.

Reuse strategy: the long-lived `presence_funded` fixture — an onboarded generated
user with an immediate (priced) Aggressive main-portfolio balance — so no fresh user
is seeded per run, and the main portfolio has a non-zero balance to reconcile against.

Standalone (own driver; clears app data). DEV API only. Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_recurring_value_and_save.py -v -s -o addopts=""
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
from pages.recurring_page import RecurringPage
from utils.deep_links import DeepLinks
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


def _open_recurring_main_setup(d, rec: RecurringPage):
    """Open the Recurring investments list (deep link) and tap the MAIN PORTFOLIO
    row to land on the setup screen that shows 'Current balance: $X'."""
    DeepLinks.open(d, DeepLinks.RECURRING_INVESTMENTS)
    assert rec.is_loaded(timeout=20), "Recurring investments list did not load"
    # A promo/coachmark can land over the list on a slow emulator — clear it
    # before we try to tap the portfolio row.
    rec.dismiss_modal()
    rec.open_main_portfolio()
    assert rec.is_setup_screen(timeout=20), \
        "did not reach the main-portfolio recurring setup screen"


def test_current_balance_matches_and_save_button_rendered():
    """The Recurring main-portfolio setup screen renders 'Current balance: $X' equal
    to the backend current_balance for the logged-in user (within band), and the Save
    button on the 'Set Recurring Investment' form is rendered at a usable size
    (RAIZ-9909)."""
    fx = get_or_create_fixture_user("presence_funded")

    # Backend truth for the SAME user we log in as.
    backend = current_balance(fx["email"], fx["password"])
    assert backend is not None, f"could not read backend current_balance for {fx['email']}"
    assert backend > 0, f"fixture user has a non-positive backend balance: ${backend}"

    opts = get_android_options(no_reset=False)  # fresh app data
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)
        rec = RecurringPage(d)
        _open_recurring_main_setup(d, rec)

        # --- Oracle 1: 'Current balance: $X' == backend current_balance -----------
        cb_text = rec.get_current_balance_text()
        assert cb_text is not None, "Recurring setup screen rendered no 'Current balance:' text"
        cb_value = parse_money(cb_text)
        print(f"  Recurring 'Current balance' text={cb_text!r} -> ${cb_value:.2f} | "
              f"backend current_balance=${backend:.2f}")
        assert cb_value > 0, f"'Current balance' value is non-positive: {cb_text!r}"

        # Reconciliation band: max($5, 3% of the backend value) absolute tolerance.
        # The balance is market-priced and can drift slightly from the API snapshot;
        # the band catches a real mismatch while tolerating live-pricing jitter.
        band = max(5.0, 0.03 * backend)
        delta = abs(cb_value - backend)
        assert delta <= band, (
            f"Recurring 'Current balance' ${cb_value:.2f} does not match backend "
            f"${backend:.2f}: |delta|=${delta:.2f} exceeds band ${band:.2f}"
        )
        print(f"  PASS oracle 1: balance matches backend within ${band:.2f} (|delta|=${delta:.2f})")

        # --- Oracle 2: Save button well-rendered on the recurring form (RAIZ-9909) -
        rec.open_set_recurring_investment()
        assert rec.is_recurring_form(timeout=20), \
            "did not reach the 'Set Recurring Investment' form (amount + Frequency + Save)"

        assert rec.is_save_button_well_rendered(), (
            "Save button is not rendered at a usable tap-target size — "
            f"bounds={rec.save_button_size()!r} (RAIZ-9909: 'Save button obstructed and small')"
        )
        print(f"  PASS oracle 2: Save button well-rendered, size={rec.save_button_size()!r}")
    finally:
        try:
            d.quit()
        except Exception:
            pass
