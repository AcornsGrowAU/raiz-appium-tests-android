from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class PerformancePage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Performance']")
    PORTFOLIO_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Main Portfolio']]")
    JAR_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[contains(@text,'Jar:')]]")
    INVESTMENT_VALUE_LABEL = (AppiumBy.XPATH, "//*[@text='Main Portfolio investment value']")
    INVESTMENT_VALUE_AMOUNT = (AppiumBy.XPATH, "//android.widget.TextView[@clickable='true' and contains(@text,'$')]")

    # The range pills wrap each label in a NON-clickable outer View and a
    # clickable inner View. The old locators matched the outer (non-clickable)
    # container, so taps never registered and the widget stayed on its default
    # range — which made the range-change test look like a stuck-widget defect.
    # Target the @clickable='true' parent so the tap actually selects the range.
    TIME_1D = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='1D']]")
    TIME_1M = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='1M']]")
    TIME_3M = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='3M']]")
    TIME_6M = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='6M']]")
    TIME_1Y = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='1Y']]")
    TIME_ALL = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='All']]")

    CHANGE_IN_VALUE = (AppiumBy.XPATH, "//*[contains(@text,'Change in value')]")
    MARKET_STATUS = (AppiumBy.XPATH, "//*[contains(@text,'market is currently')]")
    # Any rendered percentage token on the widget (used for the $0.00 / Δ checks).
    PERCENT_ANY = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'%')]")

    # Map a range key to the human period word the widget shows beside the
    # change-in-value (e.g. "Change in value (1 month)"). WATCH: exact copy not
    # verified on-device — read via get_change_in_value_text() which is robust to
    # the surrounding wording.
    RANGE_KEYS = ["1D", "1M", "3M", "6M", "1Y", "All"]

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def range_locator(self, range_: str):
        return {
            "1D": self.TIME_1D, "1M": self.TIME_1M,
            "3M": self.TIME_3M, "6M": self.TIME_6M,
            "1Y": self.TIME_1Y, "All": self.TIME_ALL,
        }[range_]

    def select_time_range(self, range_: str):
        ranges = {
            "1D": self.TIME_1D, "1M": self.TIME_1M,
            "3M": self.TIME_3M, "6M": self.TIME_6M,
            "1Y": self.TIME_1Y, "All": self.TIME_ALL,
        }
        self.click(ranges[range_])

    def select_portfolio_tab(self):
        self.click(self.PORTFOLIO_TAB)

    def select_jar_tab(self):
        self.click(self.JAR_TAB)

    def get_investment_amount(self) -> str:
        return self.get_text(self.INVESTMENT_VALUE_AMOUNT)

    def get_market_status(self) -> str:
        return self.get_text(self.MARKET_STATUS)

    def get_change_in_value_text(self) -> str:
        """Full text of the 'Change in value' row/label, including any period
        word the widget renders (e.g. '1 month', '3 months', 'all time'). Empty
        string if not present so callers can treat absence distinctly."""
        els = self.driver.find_elements(*self.CHANGE_IN_VALUE)
        return els[0].text if els else ""

    def get_period_label(self) -> str:
        """The period descriptor currently shown beside the change-in-value.
        Derived from the change-in-value row so it tracks the selected range
        without relying on a separate, unverified locator."""
        return self.get_change_in_value_text()

    def get_change_value(self) -> str:
        """The change-in-value figure rendered beside the 'Change in value (...)'
        label, e.g. '+$13.52 +1.73%'.

        Verified on 2.39.1d: the widget renders the period label ('Change in
        value (1M)') and the change figure ('+$13.52 +1.73%') as adjacent sibling
        TextViews under a shared container, distinct from the headline account
        value ('Main Portfolio investment value' / '$1,563.65'). We locate the
        first $-bearing TextView that is NOT the headline value (the headline is
        clickable; the change figure is not) so we read the Δ, not the balance."""
        # The change figure sits next to the period label and carries a sign
        # (+/-) — match a money token that is not the clickable headline amount.
        change_els = self.driver.find_elements(
            AppiumBy.XPATH,
            "//android.widget.TextView[contains(@text,'$') and not(@clickable='true') "
            "and (contains(@text,'%') or starts-with(@text,'+') or starts-with(@text,'-'))]")
        for e in change_els:
            if e.text and "$" in e.text:
                return e.text
        # Fallback: first non-headline money token on the widget.
        money_els = self.driver.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$') and not(@clickable='true')]")
        texts = [e.text for e in money_els if e.text and "$" in e.text]
        return texts[0] if texts else ""

    def get_percent_texts(self) -> list[str]:
        """All percentage tokens currently rendered on the widget."""
        return [e.text for e in self.driver.find_elements(*self.PERCENT_ANY) if e.text]
