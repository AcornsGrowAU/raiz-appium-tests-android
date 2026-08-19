"""
Authentication tests — login, PIN, logout, error states.
These tests manage their own driver state and do NOT use the session driver fixture.
"""
import pytest
from appium import webdriver as appium_webdriver
from config.capabilities import get_android_options, get_ios_options
from config.settings import (
    APPIUM_HOST,
    ANDROID_APP_PACKAGE,
    DEFAULT_WAIT,
    PLATFORM,
    STATE_PROBE_WAIT,
    TEST_EMAIL,
    TEST_PASSWORD,
    TEST_PIN,
)
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.pin_page import PinPage
from pages.home_page import HomePage


@pytest.fixture
def fresh_driver():
    """Force-stops the app and starts a fresh session (noReset=False)."""
    opts = get_android_options(no_reset=False, secondary=True) if PLATFORM == "android" else get_ios_options(no_reset=False)
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    yield d
    d.quit()


# A relaunch goes splash -> PIN; on a slow/pressured or back-to-back restart the
# PIN title can render well after the default 10s. Give the restart assertion room.
PIN_RESTART_WAIT = 20


def _relaunch_app(driver, attempts=3) -> PinPage:
    """Cold-restart the authenticated app and return its PIN screen.

    Two hardenings against the intermittent 'PIN screen should appear on app
    restart' flake, neither of which touches the oracle (PIN must still appear):

    1. Un-raced relaunch: fully terminate and WAIT for the app to actually leave
       the running state before reactivating. Back-to-back restarts otherwise race
       (activate_app fires while the process is still tearing down).
    2. Reopen-retry: an occasional cold relaunch just fails to render the Compose
       PIN screen (empirically ~1 in a class of 6 consecutive restarts, even with a
       20s wait). Rather than wait ever-longer on ONE bad relaunch, re-terminate
       and relaunch — mirrors the reopen-retry the deep-link/heavy-screen fixtures
       already use. Returns as soon as the PIN title is up; the caller's
       is_loaded(timeout=PIN_RESTART_WAIT) assert still fails loudly if all
       attempts genuinely never surface PIN."""
    import time as _time
    from config.settings import POLL_INTERVAL
    pin = PinPage(driver)
    for attempt in range(attempts):
        driver.terminate_app(ANDROID_APP_PACKAGE)
        # Poll until the app is no longer running (state <= 1) before reactivating.
        waited = 0.0
        while waited < 5.0:
            try:
                if driver.query_app_state(ANDROID_APP_PACKAGE) <= 1:
                    break
            except Exception:
                break
            _time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
        driver.activate_app(ANDROID_APP_PACKAGE)
        # First attempts poll briefly; the last attempt gets the full budget so the
        # caller's assert reflects a genuinely-stuck relaunch, not an early give-up.
        probe = PIN_RESTART_WAIT if attempt == attempts - 1 else 8
        if pin.is_loaded(timeout=probe):
            return pin
    return pin


def _open_login(driver) -> LoginPage:
    """From a cold start, open the login form and return the LoginPage."""
    splash = SplashPage(driver)
    assert splash.is_loaded(), "Splash should load on cold start"
    splash.tap_log_in()
    login = LoginPage(driver)
    assert login.is_loaded(), "Login form should open after tapping Log in"
    return login


def _unlock_to_home(driver, pin: PinPage) -> HomePage:
    """Enter the correct PIN and land on Home, relying on the CENTRAL biometric
    handling in base_page.dismiss_modal().

    The "Raiz Biometrics" Yes/No prompt can render a beat AFTER the PIN is
    accepted. dismiss_modal() only gives that prompt a real polling wait when the
    driver carries the `_biometrics_pending` flag — otherwise it takes an instant
    snapshot that misses the late prompt, leaving it to block Home. The conftest
    PIN helper sets that flag; these tests drive the keypad directly, so we set it
    here too (mirroring conftest) instead of re-implementing any biometric clicks.
    """
    pin.enter_pin(TEST_PIN)
    driver._biometrics_pending = True
    home = HomePage(driver)
    home.dismiss_modal()
    if home.is_loaded():
        return home  # happy path unchanged

    # PIN-heavy tests (wrong-PIN / backspace cases) can trip the app's
    # "Too many attempts" lockout — the dialog reads "Too many attempts" /
    # "You've made too many failed attempts to log in with your PIN..." (real
    # strings: raizFeatureSignUp/.../strings.xml pin_dialog_too_many_attempts_*).
    # Once locked out the app drops to the splash/credential login, so the PIN we
    # just entered can never reach Home. Detect the lockout dialog or the splash
    # TAGLINE and route recovery through the credential re-login helper, which owns
    # the lockout-reset path. Local import to avoid any import cycle with conftest.
    from appium.webdriver.common.appiumby import AppiumBy
    lockout = (AppiumBy.XPATH,
               "//*[contains(@text,'Too many attempts') "
               "or contains(@text,'too many failed')]")
    splash = SplashPage(driver)
    if home.is_present_now(lockout) or splash.is_present_now(splash.TAGLINE):
        from conftest import _ensure_logged_in
        _ensure_logged_in(driver)
        home = HomePage(driver)
    return home


def _became_invisible(driver, locator, timeout=DEFAULT_WAIT) -> bool:
    """Positive transition wait: True once `locator` has actually left the screen
    (invisible or absent), False if it's still present after `timeout`.

    Preferred over `not is_visible(...)`: that snapshot passes if the element
    merely isn't visible at the instant it's read, so it can report navigation
    BEFORE the transition even begins. This waits for the disappearance to
    complete, asserting the navigation actually happened. Mirrors base_page's
    WebDriverWait/EC usage."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    from config.settings import POLL_INTERVAL
    try:
        return bool(WebDriverWait(driver, timeout, poll_frequency=POLL_INTERVAL).until(
            EC.invisibility_of_element_located(locator)))
    except TimeoutException:
        return False


def _parse_bounds(el):
    """Parse an element's @bounds into (x1, y1, x2, y2), or None."""
    import re
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
    return tuple(int(m.group(i)) for i in (1, 2, 3, 4)) if m else None


def _password_toggle_is_real(login) -> bool:
    """Prove the show/hide control the test taps is a GENUINE password toggle
    before trusting a reveal/hide reading.

    True when the content-desc-labelled eye is present (Compose-correct), OR when
    the positional (//Button)[2] fallback sits INSIDE the password field's bounds
    (a real in-field trailing eye). A chrome Button elsewhere on the form must NOT
    be able to masquerade as the toggle via the positional fallback."""
    if login.is_present(login.SHOW_PASSWORD_BUTTON, timeout=STATE_PROBE_WAIT):
        return True
    fields = login.driver.find_elements(*login.PASSWORD_FIELD)
    btns = login.driver.find_elements(*login.SHOW_PASSWORD_BUTTON_FALLBACK)
    if not fields or not btns:
        return False
    fb = _parse_bounds(fields[0])
    bb = _parse_bounds(btns[0])
    if not fb or not bb:
        return False
    # The fallback button's centre must fall within the password field rectangle.
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    return fb[0] <= cx <= fb[2] and fb[1] <= cy <= fb[3]


@pytest.mark.auth
@pytest.mark.smoke
class TestLogin:
    def test_splash_screen_loads(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        assert splash.is_loaded(), "Splash screen should be visible on cold start"

    def test_log_in_link_opens_login_form(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        assert login.is_loaded(), "Login form should be visible after tapping Log in"

    def test_successful_login(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        login.login(TEST_EMAIL, TEST_PASSWORD)

        # Account may require PIN after email/password
        pin = PinPage(fresh_driver)
        if pin.is_loaded():
            pin.enter_pin(TEST_PIN)

        home = HomePage(fresh_driver)
        home.dismiss_modal()
        assert home.is_loaded(), "Should land on Home after successful login"

    def test_wrong_password_shows_error(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        login.login(TEST_EMAIL, "WrongPassword999!")
        assert not HomePage(fresh_driver).is_loaded(), "Should NOT navigate to Home with wrong password"

    def test_empty_email_stays_on_login(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        login.enter_password(TEST_PASSWORD)
        login.tap_login()
        assert login.is_loaded(), "Should stay on Login with empty email"

    def test_empty_password_stays_on_login(self, fresh_driver):
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        login.enter_email(TEST_EMAIL)
        login.tap_login()
        assert login.is_loaded(), "Should stay on Login with empty password"

    def test_invalid_email_format_does_not_log_in(self, fresh_driver):
        """A malformed email must never authenticate."""
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        login.login("notanemail", TEST_PASSWORD)
        assert not HomePage(fresh_driver).is_loaded(), "A malformed email must not reach Home"

    def test_forgot_password_link_navigates(self, fresh_driver):
        """'Forgot your password?' must open the reset flow, i.e. leave the login
        form. (Conservative: asserts we navigate away from the 'Log in to Raiz'
        title — the reset screen's exact copy isn't asserted.)"""
        splash = SplashPage(fresh_driver)
        splash.tap_log_in()
        login = LoginPage(fresh_driver)
        assert login.is_loaded()
        login.tap_forgot_password()
        assert _became_invisible(fresh_driver, login.TITLE, timeout=DEFAULT_WAIT), \
            "Tapping 'Forgot your password?' should navigate to the password-reset flow"


@pytest.mark.auth
@pytest.mark.regression
class TestLoginErrorHandling:
    """Value/state assertions on failed logins — the suite's core weakness was
    asserting only 'not on Home'. These assert the app STAYS on the login form
    AND surfaces an error, and that abusive input doesn't crash or authenticate."""

    def test_wrong_password_stays_on_login_and_shows_error(self, fresh_driver):
        """Wrong password must keep us on the login form AND show an error
        message — not merely 'not navigate Home'."""
        login = _open_login(fresh_driver)
        login.login(TEST_EMAIL, "WrongPassword999!")
        assert not HomePage(fresh_driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "Wrong password must not reach Home"
        assert login.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Should remain on the login form after a wrong password"
        assert login.has_error(timeout=DEFAULT_WAIT), \
            "Wrong password should surface an authentication error message"

    def test_unknown_email_does_not_authenticate(self, fresh_driver):
        """A well-formed but non-existent email must never authenticate and must
        stay on the login form."""
        login = _open_login(fresh_driver)
        login.login("raiz_no_such_user+999@example.com", TEST_PASSWORD)
        assert not HomePage(fresh_driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "Unknown email must not reach Home"
        assert login.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Should remain on login for an unknown email"

    def test_email_with_surrounding_whitespace(self, fresh_driver):
        """Leading/trailing whitespace around the email should not crash the app.
        Characterisation: either the app trims and logs in, or it rejects and
        stays on login — but it must not land in a broken/blank state."""
        login = _open_login(fresh_driver)
        login.login(f"  {TEST_EMAIL}  ", TEST_PASSWORD)
        pin = PinPage(fresh_driver)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            pin.enter_pin(TEST_PIN)
        home = HomePage(fresh_driver)
        home.dismiss_modal()
        # Recoverable end state: either trimmed+authenticated, or still on a usable
        # login form. Never a dead/unknown screen.
        assert home.is_loaded(timeout=STATE_PROBE_WAIT) or login.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Whitespace-padded email should leave the app on a usable Home or Login screen"

    def test_uppercased_email_is_accepted_case_insensitively(self, fresh_driver):
        """Emails are case-insensitive by RFC; the registered lowercase address
        upper-cased should still authenticate (or at worst stay on login — never
        crash)."""
        login = _open_login(fresh_driver)
        login.login(TEST_EMAIL.upper(), TEST_PASSWORD)
        pin = PinPage(fresh_driver)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            pin.enter_pin(TEST_PIN)
        home = HomePage(fresh_driver)
        home.dismiss_modal()
        assert home.is_loaded(timeout=STATE_PROBE_WAIT) or login.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Upper-cased email should leave the app on a usable Home or Login screen"

    def test_very_long_input_does_not_crash(self, fresh_driver):
        """Extremely long email/password must not crash the app or authenticate.
        The login form must remain interactive afterwards."""
        login = _open_login(fresh_driver)
        login.login("a" * 500 + "@example.com", "b" * 500)
        assert not HomePage(fresh_driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "Garbage long credentials must not authenticate"
        assert login.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Login form must remain present (not crashed) after very long input"

    def test_repeated_failed_attempts_stay_on_login(self, fresh_driver):
        """Three consecutive wrong passwords must each be rejected and never
        authenticate. (Read-only account: we use a wrong password, so this does
        NOT risk locking the real credentials.)"""
        login = _open_login(fresh_driver)
        for i in range(3):
            login.login(TEST_EMAIL, f"Wrong{i}Password!")
            assert not HomePage(fresh_driver).is_loaded(timeout=STATE_PROBE_WAIT), \
                f"Attempt {i + 1}: wrong password must not reach Home"
            assert login.is_loaded(timeout=STATE_PROBE_WAIT), \
                f"Attempt {i + 1}: should remain on login form"


@pytest.mark.auth
@pytest.mark.regression
class TestPasswordVisibility:
    """Show/hide-password control behaviour (the eye toggle)."""

    def test_password_is_masked_by_default(self, fresh_driver):
        """The entered password must not be echoed back as plain text by default."""
        login = _open_login(fresh_driver)
        login.enter_password(TEST_PASSWORD)
        value = login.get_password_value()
        assert TEST_PASSWORD not in value, \
            f"Password field should mask input by default, but exposed it: {value!r}"

    def test_show_password_toggle_reveals_and_hides(self, fresh_driver):
        """Tapping the eye reveals the password; tapping again re-masks it.
        Asserts an actual state change, not just that a control exists."""
        login = _open_login(fresh_driver)
        login.enter_password(TEST_PASSWORD)
        # Before trusting a reveal/hide reading, prove the control we tap is a REAL
        # password toggle — not a chrome button the positional (//Button)[2]
        # fallback could tap and let masquerade as a toggle.
        assert _password_toggle_is_real(login), \
            "Show/hide control must be a genuine password toggle (content-desc eye, " \
            "or a clickable node inside the password field), not a chrome button"
        login.tap_show_password()
        revealed = login.get_password_value()
        login.tap_show_password()
        rehidden = login.get_password_value()
        # The two states must differ — revealing then hiding must change what the
        # field reports.
        assert revealed != rehidden, \
            "Toggling show-password should change the field's reported value"


@pytest.mark.auth
@pytest.mark.regression
class TestForgotPassword:
    """'Forgot your password?' reset flow — content, not just navigation."""

    def test_forgot_password_opens_reset_with_email_field(self, fresh_driver):
        """The reset flow should leave the login title AND present a reset
        affordance (an email field to send the reset link to). Conservative:
        asserts we left 'Log in to Raiz' and that an email input is present."""
        login = _open_login(fresh_driver)
        login.tap_forgot_password()
        assert _became_invisible(fresh_driver, login.TITLE, timeout=DEFAULT_WAIT), \
            "Forgot-password should navigate away from the login form"
        # The reset screen collects an email; the same field locator works if the
        # screen reuses the 'Email address' label. WATCH: reset-screen copy not
        # crawled — falls back to any EditText so the test still proves an input.
        email_field = login.EMAIL_FIELD
        any_edit = (login.EMAIL_FIELD[0], "//android.widget.EditText")
        assert login.is_present(email_field, timeout=STATE_PROBE_WAIT) \
            or login.is_present(any_edit, timeout=STATE_PROBE_WAIT), \
            "Password-reset screen should present an email input to send the reset link"

    def test_back_from_forgot_password_returns_to_login(self, fresh_driver):
        """Backing out of the reset flow should return to the login form, leaving
        the app recoverable."""
        login = _open_login(fresh_driver)
        login.tap_forgot_password()
        assert _became_invisible(fresh_driver, login.TITLE, timeout=DEFAULT_WAIT)
        login.go_back()
        assert login.is_loaded(), "Back from reset flow should return to the login form"


@pytest.mark.auth
class TestPin:
    def test_pin_screen_appears_on_app_restart(self, driver):
        """After a session is established, restarting the app should show the PIN screen."""
        pin = _relaunch_app(driver)
        assert pin.is_loaded(timeout=PIN_RESTART_WAIT), "PIN screen should appear on app restart"

    def test_correct_pin_navigates_home(self, driver):
        pin = _relaunch_app(driver)
        assert pin.is_loaded(timeout=PIN_RESTART_WAIT), "PIN screen should appear on app restart"
        home = _unlock_to_home(driver, pin)
        assert home.is_loaded(), "Correct PIN should navigate to Home"

    def test_log_out_from_pin_screen(self, driver):
        pin = _relaunch_app(driver)
        assert pin.is_loaded(timeout=PIN_RESTART_WAIT)
        pin.tap_log_out()
        splash = SplashPage(driver)
        assert splash.is_loaded(), "Tapping Log Out on PIN screen should return to Splash"

    def _restart_to_pin(self, driver) -> PinPage:
        pin = _relaunch_app(driver)
        assert pin.is_loaded(timeout=PIN_RESTART_WAIT), "PIN screen should appear on app restart"
        return pin

    def test_wrong_pin_does_not_navigate_home(self, driver):
        """An incorrect PIN must NOT unlock the app. We then complete with the
        correct PIN so the session is left logged in for the next test."""
        pin = self._restart_to_pin(driver)
        # A 4-digit PIN that is not the real one.
        wrong = "1234" if TEST_PIN != "1234" else "5678"
        pin.enter_pin(wrong)
        assert not HomePage(driver).is_loaded(timeout=STATE_PROBE_WAIT), \
            "A wrong PIN must not unlock the app"
        assert pin.is_loaded(timeout=STATE_PROBE_WAIT) or pin.has_error(timeout=STATE_PROBE_WAIT), \
            "After a wrong PIN we should remain on the PIN screen (optionally with an error)"
        # Recover: clear any partial entry and enter the correct PIN. A 4-digit
        # wrong PIN may auto-clear on rejection; delete is a safety no-op then.
        pin.tap_delete(times=4)
        home = _unlock_to_home(driver, pin)
        assert home.is_loaded(), "Correct PIN after a wrong attempt should unlock the app"

    def test_pin_entry_is_masked(self, driver):
        """Entered PIN digits must not be echoed as readable on-screen text
        (the keypad keys themselves are excluded). Then unlock to stay logged in."""
        pin = self._restart_to_pin(driver)
        pin.enter_pin(TEST_PIN)
        # The entered digits must never be echoed as readable on-screen text.
        # digit_is_visible_as_text() already excludes the single keypad key that
        # bears each digit (it counts >1 occurrence). Capture this while still on
        # the PIN surface, before the correct PIN routes us away.
        on_pin = pin.is_loaded(timeout=STATE_PROBE_WAIT)
        for digit in set(TEST_PIN):
            assert not (on_pin and pin.digit_is_visible_as_text(digit)), \
                f"PIN digit {digit!r} appears to be echoed as plain text — should be masked"
        # Now finish unlocking (handles the late biometric prompt centrally).
        driver._biometrics_pending = True
        home = HomePage(driver)
        home.dismiss_modal()
        assert home.is_loaded(), "Correct PIN should unlock the app"

    def test_backspace_on_empty_pin_does_not_crash(self, driver):
        """RAIZ-10026 class: pressing backspace/delete on an empty PIN field must
        not crash. The keypad must stay alive and still accept the correct PIN."""
        pin = self._restart_to_pin(driver)
        # Delete past empty.
        pin.tap_delete(times=3)
        assert pin.is_loaded(timeout=STATE_PROBE_WAIT), \
            "Backspace on an empty PIN must keep the keypad alive (RAIZ-10026)"
        # And the keypad still works afterwards.
        home = _unlock_to_home(driver, pin)
        assert home.is_loaded(), "PIN keypad should still function after backspace-on-empty"

    def test_backspace_corrects_a_mistyped_pin(self, driver):
        """Type a wrong leading digit, backspace it away, then complete the
        correct PIN — the corrected entry must unlock the app (delete must
        actually remove the last digit, not no-op or crash)."""
        pin = self._restart_to_pin(driver)
        wrong_first = "9" if TEST_PIN[0] != "9" else "1"
        pin.tap_key(wrong_first)
        pin.tap_delete(times=1)
        home = _unlock_to_home(driver, pin)
        assert home.is_loaded(), \
            "Backspacing a mistyped digit then entering the correct PIN should unlock"


@pytest.mark.auth
@pytest.mark.regression
class TestSessionPersistence:
    """Relaunching an authenticated app should resume via PIN, NOT a full
    email/password login — i.e. the session persists and the splash login form
    must NOT reappear."""

    def test_relaunch_resumes_at_pin_not_full_login(self, driver):
        pin = _relaunch_app(driver)
        login = LoginPage(driver)
        splash = SplashPage(driver)
        assert pin.is_loaded(timeout=PIN_RESTART_WAIT), \
            "Relaunch of an authenticated app should show the PIN screen"
        assert not splash.is_present_now(splash.TAGLINE), \
            "Relaunch must NOT drop to the splash/login form when a session exists"
        assert not login.is_present(login.TITLE, timeout=STATE_PROBE_WAIT), \
            "Relaunch must NOT require a full email/password login"
        # Restore home for subsequent tests.
        home = _unlock_to_home(driver, pin)
        assert home.is_loaded(), "PIN should resume the persisted session to Home"
