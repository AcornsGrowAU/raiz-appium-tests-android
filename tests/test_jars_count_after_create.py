"""
TC-06 [P1] — Home Jars card count increments after creating a jar (RAIZ-10355).

RAIZ-10355: the Home Jars/Kids card count did not update after creating one. The
existing TestJarCreationE2E.test_create_jar_updates_home_count only asserts the
card stops showing the empty 'Add' state — it does NOT prove the COUNT advanced
by exactly one (it would pass even on a card that went from "Add" to a stale "1"
that was already wrong, or to "3" after a double-create). This test closes that
gap with the precise oracle the defect needs:

    count BEFORE  ->  create exactly ONE jar  ->  back to Home + pull-to-refresh
    ->  count == before + 1  AND  jars_card_is_empty() is False.

DATA STRATEGY (destructive create -> FRESH user every run): creating a jar mutates
account state irreversibly, so this test does NOT reuse a shared fixture or the
shared TEST_EMAIL account — it generates a brand-new user each run, logs in AS it
(own driver), and onboards. A fresh user owns 0 jars, so the baseline is a clean
`before_count == 0` and the oracle is unambiguous. (Reuse is reserved for read-only
/ money tests via the rich-buffer pattern — see memory genuser-test-data-reuse-strategy.)

DESTRUCTIVE: gated behind RUN_DESTRUCTIVE=1. DEV backend only — never prod. Needs
emulator + Appium:
  RUN_DESTRUCTIVE=1 ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_jars_count_after_create.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver
from selenium.common.exceptions import WebDriverException

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.jars_page import JarsPage
from utils.deep_links import DeepLinks
from utils.genuser_api import gen_create, funded_user, SEEDED_PWD
from conftest import _open_deep_link

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.jars, pytest.mark.destructive]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")
_RUN_DESTRUCTIVE = os.getenv("RUN_DESTRUCTIVE") == "1"


def _fresh_user():
    """Seed a brand-new funded user for THIS run only (jar-create mutates state, so
    never reuse). Returns {email, password}."""
    email = f"jarcreate.{int(time.time())}@emel.xyz"
    status, body = gen_create({"user_1": funded_user(email, "JarCreate")})
    assert status == 200, f"failed to seed fresh jar-create user: HTTP {status} {body}"
    return {"email": email, "password": SEEDED_PWD}


def _login_and_home(d, fx):
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
        time.sleep(2)
    lo.login(fx["email"], fx["password"])
    time.sleep(7)
    if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
        onb = OnboardingPage(d)
        assert onb.complete(), f"onboarding stuck: {onb.path}"
    assert ho.is_present_now(ho.TOTAL_VALUE_LABEL), "not on Home after login"
    return ho


def _open_jars(driver, attempts=3) -> JarsPage:
    """Reach the Jars create screen via the Home Jars CARD tap.

    The `raiz://jars` deep link does NOT resolve for a freshly generated user that
    owns 0 jars — verified on device (emulator-5556): firing the deep link leaves
    the app sitting on Home with the Jars card still in its empty 'Add' state, so
    the old deep-link route deterministically failed with "Could not open the Jars
    screen". Tapping the Home Jars card (its clickable container, via
    HomePage.tap_jars) DOES navigate, landing straight on the 'Customise your Jar!'
    create screen — exactly the screen this test needs to add a jar. Retry the tap
    a couple of times to ride out a tap that registers before the card scroll
    settles."""
    home = HomePage(driver)
    jars = JarsPage(driver)
    for _ in range(attempts):
        try:
            home.tap_jars()
            if jars.is_loaded():
                return jars
            # Tap landed before navigation settled / on the wrong screen — return
            # to a known Home state and try again.
            _open_deep_link(driver, DeepLinks.HOME)
            home.dismiss_modal()
        except WebDriverException:
            try:
                _open_deep_link(driver, DeepLinks.HOME)
                home.dismiss_modal()
            except WebDriverException:
                pass
            continue
    assert jars.is_loaded(), "Could not open the Jars screen via the Home Jars card"
    return jars


def _return_home(driver, attempts=6) -> HomePage:
    """Return to Home from the Jars LIST screen after the jar commits.

    Uses the system back button, NOT a `raiz://home` deep link: verified on device
    (emulator-5556) that the home deep link does NOT navigate away from the Jars
    list / jar-detail screens — it leaves the app sitting on the Jars list — whereas
    a single back press pops the Jars list straight back to Home. Press back until
    Home renders (each pop settles one screen)."""
    import time
    home = HomePage(driver)
    for _ in range(attempts):
        if home.is_loaded(timeout=1):
            return home
        try:
            driver.back()
        except WebDriverException:
            pass
        time.sleep(2)
        home.dismiss_modal()
    assert home.is_loaded(), "Expected to be back on Home after creating the jar"
    return home


@pytest.mark.skipif(
    not _RUN_DESTRUCTIVE,
    reason="Creates a real DEV jar (left on the account); opt-in via RUN_DESTRUCTIVE=1",
)
def test_home_jars_count_increments_after_create():
    """Creating exactly one jar must bump the Home Jars card count by one
    (RAIZ-10355). Fresh generated user (0 jars baseline), own driver. Asserts the
    real value (count == before + 1), not mere presence."""
    fx = _fresh_user()
    opts = get_android_options(no_reset=False)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        ho = _login_and_home(d, fx)

        # --- BEFORE: a fresh user owns no jars -> empty 'Add' state == 0. ---
        before_empty = ho.jars_card_is_empty()
        before_count = ho.jars_card_count()
        if before_count is None:
            assert before_empty, (
                "Home Jars card surfaced no count yet was not in the empty 'Add' "
                "state — cannot establish a baseline to assert the RAIZ-10355 increment"
            )
            before_count = 0

        # --- ACT: create exactly ONE jar from the Jars create screen. ---
        jars = _open_jars(d)
        assert jars.is_create_screen(), (
            "Expected the 'Customise your Jar' create screen to add a new jar"
        )
        jars.create_jar("TC06 Count Jar")
        # Wait for the create to commit on the DEV backend before judging success —
        # tapping Create Jar returns instantly, so an immediate read races the network.
        oops = jars.wait_for_create_committed()
        assert not oops, "Creating the jar raised an 'Oops!' error"

        # --- ASSERT: back on Home + pull-to-refresh, count is exactly before + 1. ---
        ho = _return_home(d)
        after_count = None
        still_empty = True
        for _ in range(4):
            ho.pull_to_refresh()
            still_empty = ho.jars_card_is_empty()
            after_count = ho.jars_card_count()
            if after_count == before_count + 1 and not still_empty:
                break

        assert not still_empty, (
            "Home Jars card still shows the empty 'Add' state after creating a jar "
            "(RAIZ-10355)"
        )
        assert after_count is not None, (
            "Home Jars card shows no count after creating a jar — the count failed to "
            "render (RAIZ-10355)"
        )
        assert after_count == before_count + 1, (
            f"Home Jars card count did not increment by one after creating a single "
            f"jar (RAIZ-10355): before={before_count}, after={after_count}"
        )
    finally:
        try:
            d.quit()
        except Exception:
            pass
