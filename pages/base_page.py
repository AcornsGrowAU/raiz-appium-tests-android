from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from config.settings import DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL, MODAL_PROBE_WAIT
from utils.deep_links import DeepLinks


class BasePage:
    # Navigation chrome present on most screens
    BACK_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[1]")
    HAMBURGER_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[1]")

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, DEFAULT_WAIT, poll_frequency=POLL_INTERVAL)
        self.long_wait = WebDriverWait(driver, LONG_WAIT, poll_frequency=POLL_INTERVAL)

    def find(self, locator):
        return self.wait.until(EC.visibility_of_element_located(locator))

    def find_clickable(self, locator):
        return self.wait.until(EC.element_to_be_clickable(locator))

    def click(self, locator):
        self.find_clickable(locator).click()

    def type_text(self, locator, text: str):
        el = self.find_clickable(locator)
        el.clear()
        el.send_keys(text)

    def get_text(self, locator) -> str:
        return self.find(locator).text

    def is_present(self, locator, timeout=DEFAULT_WAIT) -> bool:
        """Check if element is in the DOM (for Compose elements that may not register as visible)."""
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=POLL_INTERVAL).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_visible(self, locator, timeout=DEFAULT_WAIT) -> bool:
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=POLL_INTERVAL).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_present_now(self, locator) -> bool:
        """Snapshot — element either rendered right now or not. No polling.

        Use for "is X on screen?" probes where polling can't help: if the
        element isn't in the view tree on the first query, waiting won't put
        it there. Saves the full timeout on the false branch.
        """
        return bool(self.driver.find_elements(*locator))

    def scroll_down(self):
        size = self.driver.get_window_size()
        x = size["width"] // 2
        self.driver.swipe(x, 1500, x, 500, 500)

    def scroll_to_text(self, text: str):
        """Scroll within any scrollable container until an element with matching text is visible."""
        self.driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().text("{text}"))'
        )

    def scroll_to_top(self) -> bool:
        """Scroll the current scrollable container back to its first item.

        UiScrollable.scrollIntoView() (used by scroll_to_text) only searches
        FORWARD, so it fails to find a target that sits ABOVE the current scroll
        position — exactly what happens when a prior test left the page scrolled
        down. Resetting to the top first makes the subsequent forward search
        reliable. Best-effort: returns False if nothing scrollable is present."""
        try:
            self.driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiScrollable(new UiSelector().scrollable(true)).scrollToBeginning(10)',
            )
            return True
        except Exception:
            return False

    def scroll_up(self):
        size = self.driver.get_window_size()
        x = size["width"] // 2
        self.driver.swipe(x, 500, x, 1500, 500)

    def click_present(self, locator):
        """Click an element that is in the DOM but may not register as visible (Compose elements with small bounds)."""
        WebDriverWait(self.driver, DEFAULT_WAIT, poll_frequency=POLL_INTERVAL).until(
            EC.presence_of_element_located(locator)
        ).click()

    def go_back(self):
        self.driver.back()

    def go_to(self, deep_link: str):
        """Navigate directly to a screen via deep link."""
        DeepLinks.open(self.driver, deep_link)

    def dismiss_modal(self):
        """Dismiss any blocking modal (promo close or biometrics prompt). Safe to call when none is showing.

        Biometrics only appears immediately after a PIN entry and may render slightly late, so we
        give it a real polling wait only when the conftest has flagged a recent PIN entry. Outside
        that window a snapshot is enough. Once dismissed it never reappears this session, so we
        flag the driver to skip the probe entirely.
        """
        if not getattr(self.driver, "_biometrics_dismissed", False):
            biometrics_title = (AppiumBy.XPATH, "//*[@text='Raiz Biometrics']")
            if getattr(self.driver, "_biometrics_pending", False):
                found = self.is_visible(biometrics_title, timeout=MODAL_PROBE_WAIT)
                self.driver._biometrics_pending = False
            else:
                found = self.is_present_now(biometrics_title)
            if found:
                no_button = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='No']]")
                self.click(no_button)
                self.driver._biometrics_dismissed = True
                return

        close_locator = (AppiumBy.XPATH, "//android.widget.Button[contains(@bounds,'[912') or contains(@bounds,'[924')]")
        if self.is_present_now(close_locator):
            self.click(close_locator)

    @staticmethod
    def by_text(text: str):
        return (AppiumBy.XPATH, f"//*[@text='{text}']")

    @staticmethod
    def by_text_contains(text: str):
        return (AppiumBy.XPATH, f"//*[contains(@text, '{text}')]")

    @staticmethod
    def by_child_text(text: str):
        return (AppiumBy.XPATH, f"//android.view.View[.//*[@text='{text}']]")

    @staticmethod
    def by_id(resource_id: str):
        return (AppiumBy.ID, resource_id)
