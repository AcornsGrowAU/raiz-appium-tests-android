from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class PinPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Enter your PIN']")
    LOG_OUT_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Log Out']]")
    # Wrong-PIN feedback. Exact server copy not pinned in captured sources, so the
    # matcher stays inclusive (matches the common "incorrect/Wrong/try again/attempts"
    # phrasings). WATCH on first device run.
    ERROR_MESSAGE = (AppiumBy.XPATH,
        "//*[contains(@text, 'incorrect') or contains(@text, 'Incorrect') "
        "or contains(@text, 'wrong') or contains(@text, 'Wrong') "
        "or contains(@text, 'try again') or contains(@text, 'attempt') "
        "or contains(@text, 'does not match') or contains(@text, 'not match')]")

    # Target the clickable parent cell (not the inner non-clickable icon child)
    KEY_0 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='0']]")
    KEY_1 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='1']]")
    KEY_2 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='2']]")
    KEY_3 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='3']]")
    KEY_4 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='4']]")
    KEY_5 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='5']]")
    KEY_6 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='6']]")
    KEY_7 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='7']]")
    KEY_8 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='8']]")
    KEY_9 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='9']]")
    KEY_DELETE = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.view.View[@resource-id='keypad_image_delete']]")

    # The masked PIN progress dots. The login keypad pins each digit's value into
    # a non-echoing indicator rather than a visible number, so the entered digits
    # must NOT appear as readable text anywhere on screen. WATCH: resource-id
    # inferred (mirrors the lump-sum 'keypad_*' naming); the digit-leak assertion
    # below does not depend on this locator.
    PIN_DOTS = (AppiumBy.XPATH, "//android.view.View[contains(@resource-id, 'pin') or contains(@resource-id, 'dot')]")

    _KEY_MAP = {str(d): (AppiumBy.XPATH, f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{d}']]") for d in range(10)}

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def enter_pin(self, pin: str):
        # The PIN keypad is a Compose grid that can recompose between locating a
        # key and clicking it (e.g. right after the screen appears), throwing a
        # StaleElementReferenceException. Retry the individual key once so a
        # transient recomposition doesn't abort the whole login.
        from selenium.common.exceptions import StaleElementReferenceException
        for digit in pin:
            try:
                self.click(self._KEY_MAP[digit])
            except StaleElementReferenceException:
                self.click(self._KEY_MAP[digit])

    def tap_key(self, digit: str):
        """Tap a single keypad digit (stale-safe, like enter_pin)."""
        from selenium.common.exceptions import StaleElementReferenceException
        try:
            self.click(self._KEY_MAP[digit])
        except StaleElementReferenceException:
            self.click(self._KEY_MAP[digit])

    def tap_delete(self, times: int = 1):
        """Tap the backspace/delete key. Targets RAIZ-10026 (backspace crash on
        the verification/PIN entry). Delete shares the 'keypad_image_delete'
        resource-id verified on the lump-sum keypad, so this locator is HIGH."""
        from selenium.common.exceptions import StaleElementReferenceException
        for _ in range(times):
            try:
                self.click(self.KEY_DELETE)
            except StaleElementReferenceException:
                self.click(self.KEY_DELETE)

    def digit_is_visible_as_text(self, digit: str) -> bool:
        """True if the literal entered digit appears as readable on-screen text.

        A masked PIN field must NOT echo digits. We exclude the keypad keys
        themselves (each key renders its own number) by only counting a digit
        that appears MORE times than the single key that bears it.
        """
        matches = self.driver.find_elements(
            AppiumBy.XPATH, f"//android.widget.TextView[@text='{digit}']")
        # One occurrence is the keypad key. More than one means the entry echoed.
        return len(matches) > 1

    def has_error(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.ERROR_MESSAGE, timeout=timeout)

    def tap_log_out(self):
        self.click(self.LOG_OUT_BUTTON)
