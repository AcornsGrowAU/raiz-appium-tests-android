from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, STATE_PROBE_WAIT
from pages.base_page import BasePage


class LoginPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Log in to Raiz']")
    EMAIL_FIELD = (AppiumBy.XPATH, "//android.widget.EditText[.//android.widget.TextView[@text='Email address']]")
    PASSWORD_FIELD = (AppiumBy.XPATH, "//android.widget.EditText[.//android.widget.TextView[@text='Raiz password']]")
    # The show/hide-password eye control. This is a Compose surface, so the
    # toggle is most reliably a clickable element bearing a "show"/"hide"/"password"
    # content-desc rather than a positional android.widget.Button (the only Buttons
    # on the login form are the top chrome). We match by content-desc first and
    # fall back to a clickable node inside the password field, then to the legacy
    # positional Button as a last resort. WATCH: the eye's exact content-desc was
    # not crawled — the inclusive matcher covers the common labels.
    SHOW_PASSWORD_BUTTON = (AppiumBy.XPATH,
        "//*[@clickable='true'][contains(@content-desc, 'show') or contains(@content-desc, 'Show') "
        "or contains(@content-desc, 'hide') or contains(@content-desc, 'Hide') "
        "or contains(@content-desc, 'password') or contains(@content-desc, 'Password') "
        "or contains(@content-desc, 'reveal') or contains(@content-desc, 'visibility')]")
    SHOW_PASSWORD_BUTTON_FALLBACK = (AppiumBy.XPATH, "(//android.widget.Button)[2]")
    FORGOT_PASSWORD_LINK = (AppiumBy.XPATH, "//android.widget.TextView[@text='Forgot your password?']")
    LOGIN_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Login']]")
    # Broad error matcher: the app may render the auth failure as "Invalid",
    # "incorrect", "error", "not match", "wrong" or "try again". Kept inclusive
    # because the exact server copy isn't pinned in the captured sources.
    ERROR_MESSAGE = (AppiumBy.XPATH,
        "//*[contains(@text, 'Invalid') or contains(@text, 'incorrect') "
        "or contains(@text, 'error') or contains(@text, 'not match') "
        "or contains(@text, 'wrong') or contains(@text, 'try again') "
        "or contains(@text, 'do not match') or contains(@text, \"don't match\")]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def enter_email(self, email: str):
        self.type_text(self.EMAIL_FIELD, email)

    def enter_password(self, password: str):
        self.type_text(self.PASSWORD_FIELD, password)

    def tap_login(self):
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass
        self.click_present(self.LOGIN_BUTTON)

    def tap_forgot_password(self):
        self.click(self.FORGOT_PASSWORD_LINK)

    def tap_show_password(self):
        """Toggle the show/hide-password eye control.

        Prefer the content-desc-based locator (Compose-correct); fall back to the
        legacy positional Button only if the labelled control isn't present, so a
        change in the eye's content-desc doesn't silently tap the wrong chrome
        button."""
        if self.is_present(self.SHOW_PASSWORD_BUTTON, timeout=STATE_PROBE_WAIT):
            self.click_present(self.SHOW_PASSWORD_BUTTON)
        else:
            self.click_present(self.SHOW_PASSWORD_BUTTON_FALLBACK)

    def login(self, email: str, password: str):
        self.enter_email(email)
        self.enter_password(password)
        self.tap_login()

    def get_error_message(self) -> str:
        return self.get_text(self.ERROR_MESSAGE)

    def has_error(self, timeout=DEFAULT_WAIT) -> bool:
        """True if an authentication error message is shown. Use the short
        STATE_PROBE_WAIT-style timeout from callers to avoid burning the full
        wait when no error is expected."""
        return self.is_visible(self.ERROR_MESSAGE, timeout=timeout)

    def get_password_value(self) -> str:
        """Return the current text/content-desc of the password EditText.

        Used to assert masking: when hidden, the field's `text` should not echo
        the literal password back. Falls back to content-desc, then ''.
        """
        try:
            el = self.find(self.PASSWORD_FIELD)
        except Exception:
            return ""
        return el.get_attribute("text") or el.get_attribute("content-desc") or ""
