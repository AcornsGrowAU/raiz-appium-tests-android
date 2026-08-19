import re

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

    # ------------------------------------------------------------------
    # Account carousel + per-account headline (RAIZ-10867 isolation).
    #
    # The Performance V2 screen renders an account carousel (LazyRow) of pill
    # chips — Main + each Jar + each Kid — above a single headline value tile
    # (PerformanceMainScreen.kt / PerformanceAccountsCarousel.kt). Each chip is a
    # clickable Compose Row wrapping a TextView whose text is the account title:
    # 'Main Portfolio', 'Jar: <name>', 'Kid: <name>' (PerformanceAccountUi.title +
    # features/performancev2 strings.xml performance_v2_account_chip_*). Selecting a
    # chip swaps the headline title AND balance to that account (VM.onAccountSelected
    # -> _balanceState = Content(account.balance), where balance is the account's OWN
    # currentBalance / accumulatedAmount). RAIZ-10867 was a graph-cache bleed across
    # accounts; the invariant this exposes is that the value shown for the selected
    # account is THAT account's own figure, never a previously-viewed account's.
    # ------------------------------------------------------------------

    # Per-account header label — distinguishes the account TYPE (not which specific
    # jar/kid; the VALUE does that). resolveHeaderTitle() in PerformanceMainViewModel.
    HEADER_MAIN = (AppiumBy.XPATH, "//*[@text='Main Portfolio investment value']")
    HEADER_JAR = (AppiumBy.XPATH, "//*[@text='Jars Account investment value']")
    HEADER_KID = (AppiumBy.XPATH, "//*[@text='Kids Account investment value']")

    # Any account chip in the carousel (used to wait for the carousel to populate —
    # accounts load async, so the screen shows a shimmer before the chips appear).
    ANY_ACCOUNT_CHIP = (AppiumBy.XPATH,
        "//android.view.View[@clickable='true']"
        "[.//android.widget.TextView[@text='Main Portfolio' "
        "or starts-with(@text,'Jar:') or starts-with(@text,'Kid:')]]")

    _BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")

    @staticmethod
    def jar_chip_title(name: str) -> str:
        """The carousel chip label for a jar named `name` ('Jar: <name>').

        NOTE: PerformanceAccountUi.formatAccountChipLabel truncates names past ~20
        chars (MAX_DISPLAY_NAME_LENGTH 25 minus the 'Jar: ' prefix) with an ellipsis.
        The reusable fixture jar names are short, so no truncation applies here; a
        longer name would need the truncated form."""
        return f"Jar: {name}"

    @staticmethod
    def kid_chip_title(name: str) -> str:
        """The carousel chip label for a kid named `name` ('Kid: <name>')."""
        return f"Kid: {name}"

    def account_chip(self, title: str):
        return (AppiumBy.XPATH,
                f"//android.view.View[@clickable='true']"
                f"[.//android.widget.TextView[@text=\"{title}\"]]")

    def has_account_carousel(self, timeout=DEFAULT_WAIT) -> bool:
        """True once the account carousel has populated (at least one chip)."""
        return self.is_present(self.ANY_ACCOUNT_CHIP, timeout=timeout)

    def current_header_type(self):
        """'main' | 'jar' | 'kid' for the account TYPE currently shown, else None."""
        if self.is_present_now(self.HEADER_JAR):
            return "jar"
        if self.is_present_now(self.HEADER_KID):
            return "kid"
        if self.is_present_now(self.HEADER_MAIN):
            return "main"
        return None

    def _swipe_carousel(self, to_left: bool = True):
        """Best-effort horizontal nudge of the account carousel to reveal a chip
        scrolled off-screen. The carousel sits just under the 'Performance' action
        bar. TODO(device): the y-fraction (0.22 of screen height) is a best-guess
        from the layout (action bar -> carousel top=16dp) and not yet confirmed on a
        device; with the 3-chip reusable fixture all chips fit and this rarely fires,
        but verify/tune the band if a longer carousel needs scrolling."""
        try:
            size = self.driver.get_window_size()
            y = int(size["height"] * 0.22)
            if to_left:
                x1, x2 = int(size["width"] * 0.8), int(size["width"] * 0.2)
            else:
                x1, x2 = int(size["width"] * 0.2), int(size["width"] * 0.8)
            self.driver.swipe(x1, y, x2, y, 400)
        except Exception:
            pass

    def select_account_chip(self, title: str, attempts: int = 4) -> bool:
        """Tap the carousel chip whose title is exactly `title`. Returns True if it
        was found and tapped. Uses a presence-based click (Compose pills near the
        viewport edge are in the tree but may not report as 'visible'), nudging the
        carousel horizontally between tries for a chip that starts off-screen."""
        loc = self.account_chip(title)
        for i in range(attempts):
            if self.is_present_now(loc):
                self.click_present(loc)
                return True
            # Alternate scroll directions so we find a chip on either side.
            self._swipe_carousel(to_left=(i % 2 == 0))
        if self.is_present_now(loc):
            self.click_present(loc)
            return True
        return False

    def _y_center(self, el):
        m = self._BOUNDS_RE.match(el.get_attribute("bounds") or "")
        if not m:
            return None
        return (int(m.group(2)) + int(m.group(4))) / 2

    def _header_label_el(self):
        for loc in (self.HEADER_MAIN, self.HEADER_JAR, self.HEADER_KID):
            els = self.driver.find_elements(*loc)
            if els:
                return els[0]
        return None

    def read_headline_amount(self) -> str:
        """The per-account headline balance text (e.g. '$4,000.00'), '' if absent.

        Anchors to the account header label and returns the nearest money TextView —
        the same geometric label->value pairing MainPortfolioPage uses. This matters
        on this screen because the allocations pager page is pre-composed
        (beyondViewportPageCount=2), so a bare 'clickable $ TextView' read could latch
        onto an off-screen allocation row instead of the headline. Falls back to the
        clickable headline $ (PerformanceMainHeader's balance Text is clickable)."""
        from utils.assertions import is_money
        money = self.driver.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$')]")
        label = self._header_label_el()
        if label is not None:
            ly = self._y_center(label)
            if ly is not None:
                best, best_d = "", None
                for e in money:
                    try:
                        t = e.text
                        if not is_money(t):
                            continue
                        y = self._y_center(e)
                    except Exception:
                        continue
                    if y is None:
                        continue
                    d = abs(y - ly)
                    if best_d is None or d < best_d:
                        best, best_d = t, d
                if best:
                    return best
        for e in self.driver.find_elements(*self.INVESTMENT_VALUE_AMOUNT):
            try:
                if e.text and is_money(e.text):
                    return e.text
            except Exception:
                continue
        return ""
