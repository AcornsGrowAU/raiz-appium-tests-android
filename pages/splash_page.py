from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class SplashPage(BasePage):
    TAGLINE = (AppiumBy.XPATH, "//*[contains(@text, 'Smart investing')]")
    CREATE_ACCOUNT_BUTTON = (AppiumBy.XPATH, "//android.view.View[.//android.widget.TextView[@text='Create an account']]")
    LOG_IN_LINK = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text, 'Log in')]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TAGLINE, timeout=timeout)

    def tap_log_in(self):
        self.click(self.LOG_IN_LINK)

    def tap_create_account(self):
        self.click(self.CREATE_ACCOUNT_BUTTON)
