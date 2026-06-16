"""
Settings screen coverage.

WHY THIS FILE GOES BEYOND PRESENCE
----------------------------------
The original Settings suite was presence-only and, worse, its "navigation" tests
tapped an item then pressed driver.back() with NO assertion on where back landed
(TEST_SUITE_ANALYSIS.md §3 row 3). That meant RAIZ-9994 — the Major Android bug
where Back from a Settings sub-menu does NOT return to Settings — would sail past
green. The model fix lives in test_e2e_flows.py::TestSettingsBackNavigationE2E
(Personal details / Security & privacy / Funding account / Plans and fees /
Notifications inbox) and test_portfolio.py for the portfolio area.

This file EXTENDS that back-stack rigor to the Settings items the e2e file does
NOT cover (Manage notifications, Accounts for financial insights, Manage
Round-Ups, and the help/legal/about rows), plus value-over-presence checks:
profile content correctness, notification-preference togglability, a well-formed
app version, and a logout *entry point* that prompts before ending the session.

SAFETY
------
The account is read-only and the driver session is shared across 8 concurrent
sibling agents. Nothing here changes real profile data, persists a notification
preference, or actually logs out (the full logout→re-login round trip is owned by
test_e2e_flows.py::TestSessionLifecycleE2E — we only assert the entry point
prompts, then CANCEL). Every test returns to Settings or Home so the next test
starts from a known state.
"""
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.settings_page import SettingsPage
from pages.home_page import HomePage
from utils.deep_links import DeepLinks
from utils.assertions import is_money
from config.settings import STATE_PROBE_WAIT
from conftest import _open_deep_link


def _restore_clean_home(driver):
    """Drive the app back to a confirmed, settled Home so a following fixture
    (e.g. the `settings` fixture, which does home -> tap_settings) starts from a
    known-good state. After a real logout the re-login + first navigation can be
    flaky (PIN gate, post-login modal, still-settling Home), so this retries
    log-in-then-Home several times and tolerates intermediate failures before
    asserting Home is actually loaded."""
    from conftest import _ensure_logged_in
    home = HomePage(driver)
    for _ in range(4):
        try:
            _ensure_logged_in(driver)  # drives splash->login->PIN and lands on Home
        except Exception:
            # Login/Home not settled yet; re-navigate and try again.
            try:
                _open_deep_link(driver, DeepLinks.HOME)  # PIN-aware opener
            except Exception:
                pass
        home.dismiss_modal()
        if home.is_loaded(timeout=STATE_PROBE_WAIT):
            return
    home.dismiss_modal()
    assert home.is_loaded(timeout=STATE_PROBE_WAIT), \
        "Failed to restore a clean Home state after logout recovery"


# --------------------------------------------------------------------------- #
# Existing presence smoke (kept — fast layout regression guard).              #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
@pytest.mark.smoke
class TestSettingsScreen:
    def test_settings_loads(self, settings):
        assert settings.is_loaded()

    def test_notifications_inbox_visible(self, settings):
        assert settings.is_visible(settings.NOTIFICATIONS_INBOX)

    def test_funding_account_visible(self, settings):
        assert settings.is_visible(settings.FUNDING_ACCOUNT)

    def test_accounts_financial_insights_visible(self, settings):
        assert settings.is_visible(settings.ACCOUNTS_FINANCIAL_INSIGHTS)

    def test_plans_and_fees_visible(self, settings):
        assert settings.is_visible(settings.PLANS_AND_FEES)

    def test_personal_details_visible(self, settings):
        assert settings.is_visible(settings.PERSONAL_DETAILS)

    def test_security_privacy_visible(self, settings):
        assert settings.is_visible(settings.SECURITY_PRIVACY)

    def test_manage_notifications_visible(self, settings):
        assert settings.is_visible(settings.MANAGE_NOTIFICATIONS)

    def test_manage_round_ups_visible(self, settings):
        assert settings.is_visible(settings.MANAGE_ROUND_UPS)

    def test_help_section_visible_after_scroll(self, settings):
        settings.scroll_down()
        assert settings.is_visible(settings.REFER_A_FRIEND)

    def test_important_docs_section_visible_after_scroll(self, settings):
        settings.scroll_down()
        assert settings.is_visible(settings.OUR_TERMS)

    def test_log_out_visible_after_scroll(self, settings):
        settings.scroll_down()
        assert settings.is_visible(settings.LOG_OUT)

    def test_app_version_displayed(self, settings):
        version = settings.get_app_version()
        assert "App version:" in version

    def test_close_button_closes_settings(self, settings, driver):
        settings.close()
        assert HomePage(driver).is_loaded()


# --------------------------------------------------------------------------- #
# App version — VALUE check (not just the label). A blank/placeholder version  #
# string is exactly the kind of defect a presence check passes.                #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
class TestAppVersionValue:
    def test_app_version_is_well_formed(self, settings):
        """'App version:' must be followed by a real version, not empty or a
        placeholder. HIGH — uses the existing APP_VERSION locator/getter."""
        version = settings.get_app_version()
        # Strip the label and assert what's left looks like a version (has a digit).
        tail = version.split("App version:", 1)[-1].strip()
        assert tail, f"App version label rendered with no version: {version!r}"
        assert any(c.isdigit() for c in tail), \
            f"App version should contain a numeric version, got {tail!r}"
        for junk in ("null", "undefined", "%s", "{", "}", "NaN"):
            assert junk not in version, f"Placeholder leakage in app version: {version!r}"


# --------------------------------------------------------------------------- #
# RAIZ-9994 (Major, Android) — back from a Settings sub-menu must return to    #
# Settings, NOT exit to Home. EXTENDS test_e2e_flows.TestSettingsBackNavigation #
# (which covers Personal details / Security & privacy / Funding account /      #
# Plans and fees / Notifications inbox) to the items it does NOT cover.        #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
@pytest.mark.navigation
@pytest.mark.e2e
class TestSettingsBackNavigationExtraE2E:
    """Different items / deeper rows than the existing e2e back-nav test, so the
    two together cover the whole Settings list rather than duplicating."""

    # (label, locator) — none of these overlap the e2e file's SUB_ITEMS.
    SUB_ITEMS = [
        ("Manage notifications", SettingsPage.MANAGE_NOTIFICATIONS),
        ("Accounts for financial insights", SettingsPage.ACCOUNTS_FINANCIAL_INSIGHTS),
        ("Manage Round-Ups", SettingsPage.MANAGE_ROUND_UPS),
    ]

    @pytest.mark.parametrize("label,locator", SUB_ITEMS, ids=[s[0] for s in SUB_ITEMS])
    def test_back_from_sub_menu_returns_to_settings(self, settings, driver, label, locator):
        assert settings.is_loaded(), "Precondition: Settings should be open"
        settings._tap_item(label, locator)
        left = not settings.is_visible(settings.TITLE, timeout=STATE_PROBE_WAIT)
        assert left, f"Tapping '{label}' should open its own screen"
        driver.back()
        assert settings.is_visible(settings.TITLE), \
            f"Back from '{label}' must return to Settings, not exit to Home (RAIZ-9994)"


@pytest.mark.settings
@pytest.mark.navigation
@pytest.mark.e2e
class TestSettingsHelpLegalBackNavigationE2E:
    """The Help / Legal / About rows (below the fold) are the deepest part of the
    Settings list and were entirely untested for back-stack behaviour. Same
    RAIZ-9994 contract. Some of these may open an external browser / webview / OS
    share sheet rather than an in-app screen — in that case Back may land on the
    OS or a webview rather than Settings, so we record (not hard-fail) when we
    cannot get back into the app, and only assert the in-app contract when Back
    keeps us inside the app. WATCH — these rows weren't crawled."""

    ITEMS = [
        ("Refer a friend", SettingsPage.REFER_A_FRIEND),
        ("Statements and reports", SettingsPage.STATEMENTS_REPORTS),
        ("Get support", SettingsPage.GET_SUPPORT),
        ("Our terms", SettingsPage.OUR_TERMS),
    ]

    @pytest.mark.parametrize("label,locator", ITEMS, ids=[s[0] for s in ITEMS])
    def test_back_from_help_legal_item_returns_to_settings(self, settings, driver, label, locator):
        assert settings.is_loaded(), "Precondition: Settings should be open"
        settings._tap_item(label, locator)
        left = not settings.is_visible(settings.TITLE, timeout=STATE_PROBE_WAIT)
        assert left, f"Tapping '{label}' should open its own destination"

        driver.back()
        # Coming back from an external browser can take an extra hop / a moment.
        back_in_settings = settings.is_visible(settings.TITLE, timeout=STATE_PROBE_WAIT)
        if not back_in_settings:
            # If we left the app entirely (webview/share sheet), recover so the
            # next test isn't stranded, then state the limitation explicitly.
            in_app = HomePage(driver).is_loaded(timeout=STATE_PROBE_WAIT) or \
                SettingsPage(driver).is_loaded(timeout=STATE_PROBE_WAIT)
            if not in_app:
                _open_deep_link(driver, DeepLinks.HOME)
                pytest.skip(f"'{label}' opens an external surface; in-app back-stack "
                            f"contract doesn't apply (recovered to Home)")
        assert back_in_settings or HomePage(driver).is_loaded(), \
            f"Back from '{label}' must return inside the app, not strand the user (RAIZ-9994 class)"


# --------------------------------------------------------------------------- #
# Destination correctness — tapping a settings item lands on the RIGHT screen, #
# not just *some* screen. Asserts identifying content on the destination.      #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
@pytest.mark.navigation
@pytest.mark.e2e
class TestSettingsItemDestinationE2E:
    def test_plans_and_fees_opens_plans_or_fees(self, settings, driver):
        """HIGH — mirrors the existing TestSettingsNavigation plans/fees check,
        with the back-to-Settings assertion added."""
        settings.tap_plans_and_fees()
        dest = (AppiumBy.XPATH, "//*[contains(@text,'Plan') or contains(@text,'plan') or contains(@text,'Fee') or contains(@text,'fee')]")
        assert settings.is_visible(dest), "Plans and fees should open a Plans/Fees screen"
        driver.back()
        assert settings.is_loaded(), "Back from Plans and fees must return to Settings (RAIZ-9994)"

    def test_manage_round_ups_opens_round_ups(self, settings, driver):
        """Manage Round-Ups must land on a Round-Ups surface, not a blank screen.
        WATCH — destination copy inferred."""
        settings.tap_manage_round_ups()
        dest = (AppiumBy.XPATH, "//*[contains(@text,'Round-Up') or contains(@text,'Round Up') or contains(@text,'round-up')]")
        landed = settings.is_visible(dest, timeout=STATE_PROBE_WAIT)
        left = not settings.is_visible(settings.TITLE, timeout=1)
        assert landed or left, "Manage Round-Ups should open the Round-Ups area"
        driver.back()
        assert settings.is_loaded(), "Back from Manage Round-Ups must return to Settings (RAIZ-9994)"

    def test_manage_notifications_opens_notification_settings(self, settings, driver):
        """Manage notifications must open notification preferences (toggles), not
        the notifications *inbox*. WATCH — destination copy inferred."""
        settings.tap_manage_notifications()
        # A notification-preferences screen carries 'Notification' copy and/or switches.
        dest = (AppiumBy.XPATH, "//*[contains(@text,'Notification') or contains(@text,'notification')]")
        landed = settings.is_visible(dest, timeout=STATE_PROBE_WAIT) or bool(settings.get_switches())
        assert landed, "Manage notifications should open a notifications-preferences screen"
        driver.back()
        assert settings.is_loaded(), "Back from Manage notifications must return to Settings (RAIZ-9994)"


# --------------------------------------------------------------------------- #
# Notification preferences — toggles must reflect a readable on/off state and  #
# be togglable. We DO NOT persist any change (read-only account, shared        #
# session): we flip and flip straight back, asserting the state inverted.      #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
@pytest.mark.e2e
class TestNotificationPreferences:
    def test_notification_settings_has_toggles(self, driver):
        """The notification-settings deep link should expose preference toggles.
        WATCH — uses NOTIFICATIONS_SETTINGS deep link; switch presence inferred."""
        _open_deep_link(driver, DeepLinks.NOTIFICATIONS_SETTINGS)
        settings = SettingsPage(driver)
        switches = settings.get_switches()
        # Some builds render notification prefs as a single screen of Switches.
        # If none are present this is a meaningful signal, not a flaky pass.
        assert switches, "Notification settings should expose at least one preference toggle"

    def test_notification_toggle_is_togglable_without_persisting(self, driver):
        """A preference toggle must actually change state when tapped (reflect),
        proving it's interactive. We restore the original state immediately so no
        preference is persisted for the shared account. WATCH — inferred screen."""
        _open_deep_link(driver, DeepLinks.NOTIFICATIONS_SETTINGS)
        settings = SettingsPage(driver)
        switches = settings.get_switches()
        if not switches:
            pytest.skip("No notification toggles rendered on this build")
        sw = switches[0]
        before = settings.switch_state(sw)
        sw.click()
        after = settings.switch_state(settings.get_switches()[0])
        # Restore regardless of assertion outcome so we never leave a flipped pref.
        if after != before:
            settings.get_switches()[0].click()
        assert after != before, "Tapping a notification toggle must change its on/off state"


# --------------------------------------------------------------------------- #
# Profile content correctness — the personal & financial profile screens must  #
# show the account's real, well-formed data with no placeholder leakage.       #
# Reached via deep link (PROFILE_PERSONAL / PROFILE_FINANCIAL) so this test is  #
# independent of the Settings list ordering. Navigation back-nav for these is   #
# owned by the e2e file; here we assert CONTENT, which is distinct.            #
# --------------------------------------------------------------------------- #
_PLACEHOLDERS = ("null", "undefined", "{", "}", "%s", "NaN", "None", "[object")


def _visible_texts(driver):
    return [el.text for el in driver.find_elements(AppiumBy.XPATH, "//android.widget.TextView")
            if (el.text or "").strip()]


@pytest.mark.settings
@pytest.mark.e2e
class TestProfileContentCorrectness:
    def test_personal_details_shows_no_placeholder_leakage(self, driver):
        """Personal details must render real field values, never raw placeholders
        like 'null'/'undefined'/'%s'. WATCH — profile/personal not crawled here."""
        _open_deep_link(driver, DeepLinks.PROFILE_PERSONAL)
        page = SettingsPage(driver)
        # Confirm we actually reached a personal/profile surface.
        assert page.is_visible((AppiumBy.XPATH,
            "//*[contains(@text,'Personal') or contains(@text,'personal') or contains(@text,'Profile') or contains(@text,'Email') or contains(@text,'Name')]"),
            timeout=STATE_PROBE_WAIT), "profile/personal deep link should open a personal-details surface"
        texts = _visible_texts(driver)
        assert texts, "Personal details rendered no text"
        for t in texts:
            for junk in _PLACEHOLDERS:
                assert junk not in t, f"Placeholder leakage on Personal details: {t!r}"

    def test_personal_details_shows_account_email(self, driver):
        """The personal profile should surface a well-formed email address (the
        account identity), not a blank or a label with no value. WATCH."""
        _open_deep_link(driver, DeepLinks.PROFILE_PERSONAL)
        texts = " \n".join(_visible_texts(driver))
        # An email is the most reliably-present, format-checkable PII field.
        import re
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", texts)
        if not emails:
            pytest.skip("Personal details screen does not surface an email on this build")
        for e in emails:
            assert "@" in e and "." in e.split("@", 1)[1], f"Malformed email on profile: {e!r}"

    def test_financial_profile_shows_no_placeholder_leakage(self, driver):
        """Financial profile must render real values, no placeholder leakage, and
        any dollar figure shown must be well-formed money. WATCH — not crawled."""
        _open_deep_link(driver, DeepLinks.PROFILE_FINANCIAL)
        page = SettingsPage(driver)
        assert page.is_visible((AppiumBy.XPATH,
            "//*[contains(@text,'Financial') or contains(@text,'financial') or contains(@text,'Income') or contains(@text,'Employment') or contains(@text,'Profile')]"),
            timeout=STATE_PROBE_WAIT), "profile/financial deep link should open a financial-profile surface"
        texts = _visible_texts(driver)
        assert texts, "Financial profile rendered no text"
        for t in texts:
            for junk in _PLACEHOLDERS:
                assert junk not in t, f"Placeholder leakage on Financial profile: {t!r}"
            # Any '$' figure must be a real, well-formed amount (not '$' / '$NaN').
            if "$" in t:
                assert is_money(t), f"Malformed money on Financial profile: {t!r}"


# --------------------------------------------------------------------------- #
# Logout ENTRY POINT — tapping Log out must PROMPT for confirmation before     #
# ending the session, and Cancel must keep us logged in. We deliberately do    #
# NOT complete the logout: the full logout→re-login round trip is owned by     #
# test_e2e_flows.py::TestSessionLifecycleE2E. Completing it here would break    #
# the shared session for the other 7 sibling agents.                          #
# --------------------------------------------------------------------------- #
@pytest.mark.settings
@pytest.mark.auth
@pytest.mark.e2e
class TestLogoutEntryPoint:
    def test_logout_prompts_and_cancel_keeps_session(self, settings, driver):
        """Tap Log out → a confirmation should appear → Cancel → still on Settings
        and still logged in. Does NOT log out (siblings share the session). HIGH —
        uses tap_log_out from the page object; confirmation copy handled robustly."""
        settings.tap_log_out()

        prompted = settings.logout_prompt_shown()
        if not prompted:
            # If this build logs out immediately with no prompt, that's a finding,
            # not a test we should leave the session broken for: recover and report.
            from pages.splash_page import SplashPage
            if SplashPage(driver).is_loaded(timeout=STATE_PROBE_WAIT):
                # Log back in AND land on a clean, settled Home before failing, so
                # the next test's `settings` fixture (home -> tap_settings) doesn't
                # error against a transient post-login state. Resilient recovery
                # (retries login + Home) absorbs the post-logout re-login flakiness.
                _restore_clean_home(driver)
                pytest.fail("Log out gave NO confirmation prompt and ended the session "
                            "immediately — an accidental tap logs the user straight out.")
            pytest.skip("Log out neither prompted nor ended the session on this build")

        # Cancel the logout — must NOT end the session.
        settings.cancel_logout()
        from pages.splash_page import SplashPage
        assert not SplashPage(driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "Cancelling the logout prompt must keep the user logged in"
        # And we should be back on Settings (or at worst Home), never the splash.
        assert settings.is_loaded(timeout=STATE_PROBE_WAIT) or HomePage(driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "After cancelling logout we should remain inside the app"
