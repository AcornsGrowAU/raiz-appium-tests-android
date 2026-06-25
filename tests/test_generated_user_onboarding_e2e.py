"""
ON-DEVICE E2E using a REUSED fixture user (reuse strategy — see memory
genuser-test-data-reuse-strategy). Logs into the real app AS the stored
`presence_funded` fixture, completes first-login onboarding ONCE (then records it so
later runs skip the gauntlet), and asserts it's on Home AS that user with a
backend-confirmed balance. No fresh generation per run.

Standalone (manages its own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5556 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_generated_user_onboarding_e2e.py -v -s -o addopts=""
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
from utils.genuser_api import current_balance
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5556")


def _money(s):
    try:
        return float((s or "").replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def test_fixture_user_logs_in_and_home_renders_balance():
    fx = get_or_create_fixture_user("presence_funded")  # reused if already seeded
    email, pwd, key = fx["email"], fx["password"], fx["key"]
    api_balance = current_balance(email)
    print(f"  fixture '{key}' {email} (reused={fx.get('reused')}) backend balance=${api_balance}")
    assert api_balance and api_balance > 0, f"fixture has no balance: {api_balance}"

    opts = get_android_options(no_reset=False)  # fresh app data
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        time.sleep(5)
        splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
        if splash.is_present_now(splash.TAGLINE):
            splash.tap_log_in()
            time.sleep(2)
        login.login(email, pwd)
        print(f"  logged into app as fixture {email}")
        time.sleep(7)

        onb = OnboardingPage(d)
        if not home.is_present_now(home.TOTAL_VALUE_LABEL):
            assert onb.complete(), f"onboarding stuck at {onb.path}"
            mark_onboarded(key)
            print(f"  completed onboarding once: {onb.path}")
        else:
            print("  fixture already onboarded -> straight to Home")

        assert home.is_present_now(home.TOTAL_VALUE_LABEL), "should be on Home"
        greeting = home.get_greeting() if hasattr(home, "get_greeting") else ""
        print(f"  on Home as {greeting!r}")
        assert "PresFunded" in greeting.replace(" ", ""), \
            f"greeting {greeting!r} should be the fixture user (PresFunded)"

        # The "total investments value" tile (first $ on screen) lags / ignores
        # with_balance, but the Main Portfolio CARD renders the balance immediately.
        # Assert the card against the backend ground truth (drift-robust band).
        card = None
        for _ in range(4):
            card = _money(home.get_account_card_value("Main Portfolio"))
            if card and card > 0:
                break
            time.sleep(5)
            try:
                home.pull_to_refresh()
                time.sleep(3)
            except Exception:
                pass
        print(f"  Main Portfolio card=${card} | backend current_balance=${api_balance}")
        assert card and card > 0, f"Main Portfolio card should render the balance, got ${card}"
        assert card == pytest.approx(api_balance, abs=max(5.0, api_balance * 0.03)), \
            f"on-device Main Portfolio card ${card} should match backend ${api_balance}"
        print(f"  PASS: reused fixture on Home as {greeting!r}; "
              f"Main Portfolio card ${card} == backend ${api_balance}")
    finally:
        try:
            d.quit()
        except Exception:
            pass
