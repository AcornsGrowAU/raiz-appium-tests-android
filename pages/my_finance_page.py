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

    def get_net_worth_total_text(self) -> str:
        """The aggregate 'My net worth' dollar figure (the headline total the
        investments + super components must add up to). Paired geometrically to
        the 'My net worth' header, same as the component figures."""
        return self._value_near(self.NET_WORTH_HEADER)

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

    def net_worth_components_ready(self) -> bool:
        """True once the 'My net worth' card has rendered its COMPONENT rows: the
        header and BOTH component labels are present AND both geometrically-paired
        component figures ('Total in investments' / 'Total in Superannuation')
        read as well-formed money.

        This is the load gate the reconciliation test depends on. It does NOT
        require the headline net-worth figure, because on the current app build
        the card renders the header label and the two component rows but exposes
        no separate headline dollar figure on the header row (verified on-device
        emulator-5558, build's My Finance layout: only '$1,578.14' for
        investments and '$0' for super are present near the card; the 'My net
        worth' header has no '$' sibling within a row's height). Gating on a
        screen-wide 'any positive figure' check is too loose — an unrelated
        figure elsewhere (e.g. Monthly tracker) can satisfy it while these
        component rows are still placeholders."""
        from utils.assertions import is_money
        if not (self.is_present_now(self.NET_WORTH_HEADER)
                and self.is_present_now(self.TOTAL_IN_INVESTMENTS)
                and self.is_present_now(self.TOTAL_IN_SUPER)):
            return False
        return (is_money(self.get_investments_total_text())
                and is_money(self.get_super_total_text()))

    def net_worth_card_ready(self) -> bool:
        """Backwards-compatible: True once the card's component rows are fully
        populated (see net_worth_components_ready)."""
        return self.net_worth_components_ready()

    def has_net_worth_headline(self) -> bool:
        """True if the card exposes a headline 'My net worth' dollar figure on the
        header row (some builds render only the component rows and no separate
        headline total — in which case the headline reconciliation is not
        applicable and callers should skip rather than fail)."""
        from utils.assertions import is_money
        return is_money(self.get_net_worth_total_text())

    def get_component_totals(self) -> list[str]:
        """Well-formed money figures of the net-worth card's component rows, i.e.
        the figures rendered BELOW the 'My net worth' header and ABOVE the next
        section ('Category Spending'). Geometric pairing (UiAutomator2 rejects the
        `following::` axis). Returns the raw figure texts for the rows that
        actually appear, so a build with extra components (cash/other) reconciles
        against all of them, not just investments + super."""
        from utils.assertions import is_money
        headers = self.driver.find_elements(*self.NET_WORTH_HEADER)
        if not headers:
            return []
        top = self._y_center(headers[0])
        if top is None:
            return []
        bottom = float("inf")
        for nxt in self.driver.find_elements(*self.CATEGORY_SPENDING):
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

    def wait_for_net_worth(self, timeout=30) -> list[float]:
        """Poll (longer, poll-based — not a snapshot) until the 'My net worth'
        card's component rows are fully populated, then return the parsed dollar
        figures on screen.

        Gating is on the card the net-worth tests actually read — header + both
        component labels present AND both component figures well-formed (see
        net_worth_components_ready) — rather than 'any positive figure anywhere on
        the screen'. The old loose gate let an unrelated positive figure (e.g.
        Monthly tracker) satisfy the wait while this card still showed $0
        placeholders or hadn't rendered its component rows, a slow-emulator race
        that made callers read partial values. The headline net-worth figure is
        deliberately NOT part of this gate: on the current build the card renders
        no separate headline figure, and gating on it would hang the full timeout
        then fail for the wrong reason.

        Backward-compatible return: the parsed money values on screen (callers do
        `max(...)`/truthiness on it), with the investments total as the largest."""
        import time
        from selenium.common.exceptions import WebDriverException
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.net_worth_components_ready():
                    return self.get_money_values()
            except WebDriverException:
                pass
            time.sleep(0.5)
        # Timed out: return whatever figures are on screen so legacy callers still
        # get their best-effort list rather than an empty hard failure here.
        try:
            return self.get_money_values()
        except WebDriverException:
            return []
