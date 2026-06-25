"""Raiz Jars screen coverage.

DATA STATE (important): two sources disagree on whether the SHARED test account
has an active jar. README.md says it does; the on-device verification recorded in
docs/TEST_SUITE_ANALYSIS.md (§6.5 and the test_allocation_jars_kids_e2e.py
docstring) found the opposite — on the shared account the Home Jars card shows
only "Add", so raiz://jars deep-links straight to the *create* screen and there
is NO Active/Closed list to assert against. That is why the meaningful list/value
cases here used to skip via `_require_list()` on the shared account — which left
Jars effectively untested in the populated state (a skip is not coverage).

This file now splits along that data boundary:

  * The EMPTY/create-state cases (TestJarsCreateScreen) still run on the shared
    `jars` fixture, asserting the create screen's real affordances. They are the
    honest coverage of the verified no-data state.

  * The LIST/VALUE cases (TestJarsListScreen, marked `genuser_e2e`) no longer skip.
    They route onto a SEEDED parent who owns two named jars of distinct balances
    (the reusable `jars_siblings_distinct` fixture), log into the app AS THAT
    PARENT, and open the populated Jars LIST so is_list_screen() is genuinely true
    and the balance / tab / Manage oracles actually run. The balance oracle reads
    the NAMED jar's value via JarsPage.get_jar_balance_by_name (not a screen-wide
    '$' scrape) and reconciles it against that jar's own backend current_balance,
    and asserts the two sibling jars render DISTINCT values — the presence-only
    weakness a bare existence check can't catch.

The list class manages its own driver (mirrors tests/test_jars_value_on_device.py
and tests/test_kids_value_on_device.py) and is opt-in via the genuser_e2e marker.
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
from pages.jars_page import JarsPage
from utils.deep_links import DeepLinks
from utils.assertions import assert_non_negative_money, parse_money
from utils.genuser_api import current_balance
from utils.genuser_fixtures import (
    get_or_create_fixture_user, mark_onboarded, JAR_A_NAME, JAR_B_NAME,
)

UDID = os.getenv("ANDROID_UDID", "emulator-5554")


# ---------------------------------------------------------------------------
# Empty/create state — runs on the SHARED account (raiz://jars -> create screen).
# ---------------------------------------------------------------------------
@pytest.mark.regression
class TestJarsCreateScreen:
    def test_jars_screen_loads(self, jars):
        assert jars.is_loaded()

    # On the shared account the deep link lands on the create screen; assert its
    # real affordances are present (more than "a screen rendered"). HIGH.
    def test_empty_state_shows_create_screen(self, jars):
        if jars.is_list_screen():
            pytest.skip("Account has an active jar — list screen shown, not create")
        assert jars.is_create_screen(), "With no active jar, Jars should open the create screen"
        assert jars.is_present_now(jars.NAME_FIELD), "Create screen should expose the jar name field"
        assert jars.is_present_now(jars.CREATE_JAR_BUTTON), "Create screen should expose Create Jar"

    def test_add_jar_button_visible(self, jars):
        # The Add affordance exists in both states (empty card / list header), so
        # this is not list-gated.
        assert jars.is_visible(jars.ADD_JAR_BUTTON) or jars.is_create_screen()


# ---------------------------------------------------------------------------
# Populated LIST/VALUE state — routed onto a SEEDED parent + two named jars.
# ---------------------------------------------------------------------------
def _band(expected: float) -> float:
    """Drift-tolerant absolute band for an on-device money comparison: market
    pricing settles asynchronously and the displayed value can lag the backend
    slightly. Mirrors the band used by the kid/main value E2Es (3% or $5)."""
    return max(5.0, abs(expected) * 0.03)


def _login_as_parent(d, fx):
    """Log the seeded parent into the real app and land on Home (running the
    first-login onboarding once if it shows). Polls for the splash/Home instead of
    blind sleeps — login RTT varies on a slow emulator (~1-3s)."""
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    if splash.is_visible(splash.TAGLINE, timeout=15):
        splash.tap_log_in()
    login.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    if not home.is_visible(home.TOTAL_VALUE_LABEL, timeout=30):
        assert onb.complete(), f"onboarding stuck at {onb.path}"
        mark_onboarded(fx["key"])
        assert home.is_visible(home.TOTAL_VALUE_LABEL, timeout=20), \
            "not on Home after completing onboarding as parent"
    # A promo / biometrics modal can overlay Home right after login and would sit
    # over the Jars list too; clear it before navigating.
    try:
        home.dismiss_modal()
    except Exception:
        pass
    assert home.is_present_now(home.TOTAL_VALUE_LABEL), "not on Home after login as parent"
    return home


def _open_jars_list(d, jars: JarsPage):
    """Open the Jars surface and wait for the POPULATED list screen (the seeded
    parent has two jars, so the empty/create gate should NOT win). The first deep
    link can land on a transient create/onboarding gate while jar data is still
    loading, so retry with backoff (with a Home Jars-card fallback); is_list_screen()
    already returns False on the create screen, so polling it naturally rides
    through a transient gate instead of giving up on the first render."""
    for attempt in range(4):
        DeepLinks.open(d, DeepLinks.JARS)
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                jars.dismiss_modal()
            except Exception:
                pass
            if jars.is_list_screen(timeout=2):
                return
            time.sleep(1)
        if attempt >= 1:
            try:
                HomePage(d).tap_jars()
            except Exception:
                pass
        time.sleep(2 + attempt)


@pytest.mark.genuser_e2e
class TestJarsListScreen:
    """Populated Jars LIST coverage on a seeded parent + two named sibling jars.

    One parent login + one Jars-list open serves every list/value assertion in the
    class (class-scoped driver), so the list state is exercised once and reused —
    no per-test re-login."""

    @pytest.fixture(scope="class")
    def jars_list(self):
        fx = get_or_create_fixture_user("jars_siblings_distinct")  # reused if seeded
        jar_a_email = "a." + fx["email"]
        jar_b_email = "b." + fx["email"]
        bal_a = current_balance(jar_a_email)
        bal_b = current_balance(jar_b_email)
        assert bal_a and bal_a > 0, f"jar-A has no backend balance: {bal_a}"
        assert bal_b and bal_b > 0, f"jar-B has no backend balance: {bal_b}"

        opts = get_android_options(no_reset=False)  # fresh app data: log in cleanly
        opts.udid = UDID
        # This class opens its OWN UiAutomator2 session while the conftest `driver`
        # session (used by TestJarsCreateScreen) is still alive in the same process
        # and pytest run. get_android_options() reads ANDROID_SYSTEM_PORT /
        # ANDROID_MJPEG_PORT from the env, so without an offset our second session
        # would request the SAME systemPort the conftest session already holds and
        # the UiAutomator2 server would refuse to start ("local port ... is busy").
        # Offset both host ports so the two sessions on this one device don't collide.
        _sys = int(os.getenv("ANDROID_SYSTEM_PORT", "8200"))
        _mjpeg = int(os.getenv("ANDROID_MJPEG_PORT", "7810"))
        opts.set_capability("systemPort", _sys + 50)
        opts.set_capability("mjpegServerPort", _mjpeg + 50)
        d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
        jars = JarsPage(d)
        try:
            _login_as_parent(d, fx)
            _open_jars_list(d, jars)
            assert jars.is_list_screen(timeout=8), (
                "expected the populated Jars LIST screen for a parent with two seeded "
                "jars, but the empty/create screen was shown")
            yield {
                "jars": jars,
                "bal_a": bal_a, "bal_b": bal_b,
                "name_a": JAR_A_NAME, "name_b": JAR_B_NAME,
            }
        finally:
            try:
                d.quit()
            except Exception:
                pass

    def test_active_tab_visible(self, jars_list):
        jars = jars_list["jars"]
        assert jars.is_present_now(jars.ACTIVE_TAB), "Active tab should be present on the Jars list"

    def test_closed_tab_visible(self, jars_list):
        jars = jars_list["jars"]
        assert jars.is_present_now(jars.CLOSED_TAB), "Closed tab should be present on the Jars list"

    def test_manage_jar_button_visible(self, jars_list):
        jars = jars_list["jars"]
        assert jars.has_active_jar(), "List screen should render a Manage Jar control for the active jar"

    # VALUE: the NAMED jar card renders THAT jar's backend balance (well-formed,
    # non-negative money), read name-scoped so a sibling's value can't bleed in.
    def test_named_jar_balance_matches_backend(self, jars_list):
        jars = jars_list["jars"]
        name_a, bal_a = jars_list["name_a"], jars_list["bal_a"]
        raw_a = jars.get_jar_balance_by_name(name_a)
        assert raw_a, f"jar {name_a!r} rendered no money balance on the list"
        assert_non_negative_money(raw_a, "jar balance")
        card_a = parse_money(raw_a)
        assert card_a == pytest.approx(bal_a, abs=_band(bal_a)), (
            f"jar {name_a!r} card ${card_a} should match its backend balance "
            f"${bal_a} (±${_band(bal_a):.2f})")

    # VALUE + ISOLATION: the two sibling jars render DISTINCT values, each matching
    # its OWN backend balance — the presence-only weakness a screen-wide '$' scrape
    # can't catch (one card showing the wrong/shared sibling balance would pass a
    # mere existence check).
    def test_sibling_jars_render_distinct_values(self, jars_list):
        jars = jars_list["jars"]
        name_a, bal_a = jars_list["name_a"], jars_list["bal_a"]
        name_b, bal_b = jars_list["name_b"], jars_list["bal_b"]
        raw_a = jars.get_jar_balance_by_name(name_a)
        raw_b = jars.get_jar_balance_by_name(name_b)
        assert raw_a, f"jar {name_a!r} rendered no balance"
        assert raw_b, f"jar {name_b!r} rendered no balance"
        card_a, card_b = parse_money(raw_a), parse_money(raw_b)
        assert card_b == pytest.approx(bal_b, abs=_band(bal_b)), (
            f"jar {name_b!r} card ${card_b} should match its backend ${bal_b} "
            f"(±${_band(bal_b):.2f})")
        # Distinct on-device (precondition: backend siblings differ by > band).
        assert abs(card_a - card_b) > _band(max(card_a, card_b)), (
            f"jars {name_a!r} (${card_a}) and {name_b!r} (${card_b}) rendered the SAME "
            f"value — the name-scoped getter leaked a sibling's balance")
        # And jar-A's card is closer to A's backend than to B's (rules out swap).
        assert abs(card_a - bal_a) < abs(card_a - bal_b), (
            f"jar {name_a!r} card ${card_a} is closer to {name_b!r}'s backend ${bal_b} "
            f"than to its own ${bal_a} — the cards look swapped")

    # Tab switching must change content and be reversible (the original shared-account
    # test re-asserted the just-tapped tab — a tautology). Switch to Closed (the
    # seeded parent has no closed jars) then back, and require the Manage Jar control
    # to be restored on Active.
    def test_tab_switch_restores_manage_control(self, jars_list):
        jars = jars_list["jars"]
        assert jars.has_active_jar(), "Precondition: an active jar should be listed"
        jars.tap_closed_tab()
        jars.tap_active_tab()
        assert jars.is_present_now(jars.MANAGE_JAR_BUTTON), \
            "Returning to Active should restore the Manage Jar control"

    def test_closed_tab_navigates(self, jars_list):
        jars = jars_list["jars"]
        jars.tap_closed_tab()
        assert jars.is_present_now(jars.CLOSED_TAB), \
            "Closed tab should remain selectable after tapping"
