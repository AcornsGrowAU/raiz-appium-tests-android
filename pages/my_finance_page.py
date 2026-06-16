import re
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class MyFinancePage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='My Finance']")
    NET_WORTH_HEADER = (AppiumBy.XPATH, "//*[@text='My net worth']")
    TOTAL_IN_INVESTMENTS = (AppiumBy.XPATH, "//*[@text='Total in investments']")
    TOTAL_IN_SUPER = (AppiumBy.XPATH, "//*[@text='Total in Superannuation']")
    CATEGORY_SPENDING = (AppiumBy.XPATH, "//*[@text='Category Spending']")
    NO_TRANSACTIONS = (AppiumBy.XPATH, "//*[@text='No processed transactions for last 3 months']")
    SEE_MORE_BUTTON = (AppiumBy.XPATH, "//android.view.View[.//android.widget.TextView[@text='See More']]")
    MONTHLY_TRACKER = (AppiumBy.XPATH, "//*[@text='Monthly tracker']")
    # Financial-insights onboarding card (verified on-device: "Set up your
    # financial insights", "0 of 3 completed", "View all", and the two setup rows).
    SETUP_INSIGHTS_HEADER = (AppiumBy.XPATH, "//*[contains(@text,'Set up your financial insights')]")
    INSIGHTS_PROGRESS = (AppiumBy.XPATH, "//*[contains(@text,'of 3 completed')]")
    LINK_TRANSACTIONAL_ACCOUNTS = (AppiumBy.XPATH, "//*[contains(@text,'Link your transactional accounts')]")
    REVIEW_SPENDING_CATEGORIES = (AppiumBy.XPATH, "//*[contains(@text,'Review your spending categories')]")
    MONEY_VALUES = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$')]")
    NET_WORTH_TOTAL = (AppiumBy.XPATH, "//*[@text='My net worth']")
    # Every TextView carrying a '$' figure (used for geometric row-pairing).
    _MONEY_TEXTVIEWS = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$')]")
    _BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    @staticmethod
    def _y_center(el):
        """Vertical centre of an element from its @bounds, or None if unparsable."""
        m = MyFinancePage._BOUNDS_RE.match(el.get_attribute("bounds") or "")
        if not m:
            return None
        return (int(m.group(2)) + int(m.group(4))) / 2

    def _value_near(self, label_locator):
        """Return the well-formed money figure that sits on the same visual ROW as
        the given label.

        The net-worth card flattens label + value into sibling TextViews with no
        per-row wrapper element (the smallest common ancestor is the whole card),
        and the UiAutomator2 XPath engine rejects the `following::` axis
        (ClassCastException in FollowingAxis). So we pair geometrically: find the
        label's vertical centre and return the money TextView whose own vertical
        centre is closest to it (same row)."""
        from utils.assertions import is_money
        labels = self.driver.find_elements(*label_locator)
        if not labels:
            return ""
        try:
            label_y = self._y_center(labels[0])
        except (StaleElementReferenceException, WebDriverException):
            return ""
        if label_y is None:
            return ""
        best_text, best_dist = "", None
        for el in self.driver.find_elements(*self._MONEY_TEXTVIEWS):
            try:
                txt = el.text
                if not is_money(txt):
                    continue
                y = self._y_center(el)
            except (StaleElementReferenceException, WebDriverException):
                continue
            if y is None:
                continue
            dist = abs(y - label_y)
            if best_dist is None or dist < best_dist:
                best_text, best_dist = txt, dist
        # Only accept a value on the same row (tolerance ~ one row height).
        if best_dist is not None and best_dist <= 80:
            return best_text
        return ""

    def get_investments_total_text(self) -> str:
        """Dollar figure shown under 'Total in investments'."""
        return self._value_near(self.TOTAL_IN_INVESTMENTS)

    def get_super_total_text(self) -> str:
        """Dollar figure shown under 'Total in Superannuation' ($0 when unfunded)."""
        return self._value_near(self.TOTAL_IN_SUPER)

    def get_category_spending_amounts(self) -> list[str]:
        """Well-formed money figures that belong to the Category Spending section,
        i.e. those rendered BELOW the 'Category Spending' header and ABOVE the next
        section ('Monthly tracker'). Pair-by-geometry rather than the `following::`
        axis (which UiAutomator2's XPath engine rejects)."""
        from utils.assertions import is_money
        headers = self.driver.find_elements(*self.CATEGORY_SPENDING)
        if not headers:
            return []
        top = self._y_center(headers[0])
        if top is None:
            return []
        # Lower bound: the next section header, if present, else the screen bottom.
        bottom = float("inf")
        for nxt in self.driver.find_elements(*self.MONTHLY_TRACKER):
            y = self._y_center(nxt)
            if y is not None and y > top:
                bottom = min(bottom, y)
        amounts = []
        for el in self.driver.find_elements(*self._MONEY_TEXTVIEWS):
            try:
                txt = el.text
                if not is_money(txt):
                    continue
                y = self._y_center(el)
            except (StaleElementReferenceException, WebDriverException):
                continue
            if y is not None and top < y < bottom:
                amounts.append(txt)
        return amounts

    def has_category_spending_data(self) -> bool:
        """True if the Category Spending section has real rows (not the empty state)."""
        return (not self.is_present_now(self.NO_TRANSACTIONS)
                and bool(self.get_category_spending_amounts()))

    def tap_see_more(self):
        self.click(self.SEE_MORE_BUTTON)

    def get_money_texts(self) -> list[str]:
        """Raw text of every dollar figure on screen (e.g. net-worth totals)."""
        from utils.assertions import is_money
        return [el.text for el in self.driver.find_elements(*self.MONEY_VALUES) if is_money(el.text)]

    def get_money_values(self) -> list[float]:
        """Parsed dollar figures on screen. The investments total is the largest;
        Superannuation is $0 on an unfunded account."""
        from utils.assertions import parse_money
        return [parse_money(t) for t in self.get_money_texts()]

    def wait_for_net_worth(self, timeout=12) -> list[float]:
        """Poll until the net-worth figures populate (investments goes positive).
        The screen renders its title before the totals load, so an immediate read
        can catch $0 placeholders. Returns the parsed values once a positive one
        appears, or the last read on timeout."""
        import time
        from selenium.common.exceptions import WebDriverException
        end = time.time() + timeout
        values: list[float] = []
        while time.time() < end:
            try:
                values = self.get_money_values()
            except WebDriverException:
                values = []
            if values and max(values) > 0:
                return values
            time.sleep(0.5)
        return values
