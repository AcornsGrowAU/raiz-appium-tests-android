from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class HomePage(BasePage):
    HAMBURGER = (AppiumBy.XPATH, "(//android.widget.Button)[1]")
    SETTINGS_GEAR = (AppiumBy.XPATH, "(//android.widget.Button)[2]")

    TAB_PAST = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Past']]")
    TAB_TODAY = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Today']]")
    TAB_FUTURE = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Future']]")

    # Greeting renders as "Hello <Name>," — the comma follows the name, so the old
    # 'Hello,' locator never matched. Match on "Hello".
    GREETING = (AppiumBy.XPATH, "//*[contains(@text, 'Hello')]")
    TOTAL_VALUE_LABEL = (AppiumBy.XPATH, "//*[@text='Your total investments value']")
    TOTAL_VALUE_AMOUNT = (AppiumBy.XPATH, "(//android.widget.TextView[contains(@text, '$')])[1]")

    ADD_FUNDS_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Add funds']]")
    WITHDRAW_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Withdraw']]")
    PERFORMANCE_DETAILS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Performance details']]")
    REWARDS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Rewards']]")

    TOTAL_INVESTMENTS_HEADER = (AppiumBy.XPATH, "//*[@text='Total investments value']")
    MAIN_PORTFOLIO_CARD = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Main Portfolio']]")
    JARS_CARD = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Jars']]")
    KIDS_CARD = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Kids']]")
    SUPERANNUATION_CARD = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Superannuation']]")

    HOW_YOU_INVEST_HEADER = (AppiumBy.XPATH, "//*[@text='HOW YOU INVEST']")
    MILESTONE_WIDGET = (AppiumBy.XPATH, "//*[@text='Milestone']")
    LAST_MONTH_WIDGET = (AppiumBy.XPATH, "//*[@text='Last month at a glance']")

    # Build-robust home signal: the Past/Today/Future tab bar is present on the home
    # dashboard across app builds (including the redesigned build that drops the
    # legacy 'Your total investments value' header and uses a 'Welcome' greeting).
    HOME_TABS = (AppiumBy.XPATH, "//android.widget.TextView[@text='Today']")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        # Prefer the legacy header when present; otherwise fall back to the
        # build-agnostic Past/Today/Future tab bar so session startup and the
        # deep-link fixtures aren't gated on a single (build-specific) label.
        if self.is_present_now(self.TOTAL_VALUE_LABEL):
            return True
        return self.is_present(self.HOME_TABS, timeout=timeout)

    def get_greeting(self) -> str:
        return self.get_text(self.GREETING)

    def get_greeting_name(self) -> str:
        """The personalised portion of the greeting. Greeting renders 'Hello <Name>,'
        so strip the leading 'Hello' and surrounding punctuation/whitespace."""
        greeting = self.get_greeting()
        if "Hello" in greeting:
            return greeting.replace("Hello", "", 1).strip(" ,!.")
        return greeting.strip(" ,!.")

    def get_total_value(self) -> str:
        return self.get_text(self.TOTAL_VALUE_AMOUNT)

    def _scroll_portfolio_cards_into_view(self, label: str = "Main Portfolio"):
        """Bring a specific investment account card on-screen. The cards sit under
        the 'Total investments value' section (only present on the Today tab) and
        are stacked vertically (Main Portfolio, Jars, Kids, Superannuation), so the
        lower cards (Kids/Superannuation) recycle out of the view tree until we
        scroll to their OWN label — scrolling only to 'Main Portfolio' leaves them
        absent from the DOM."""
        import time
        if self.is_present_now(self.TAB_TODAY):
            try:
                self.tap_tab_today()
                time.sleep(0.4)
            except Exception:
                pass
        # Reset to the top first: scroll_to_text searches forward only, so if a
        # prior test left Home scrolled past the cards it would never find them.
        self.scroll_to_top()
        try:
            self.scroll_to_text(label)
        except Exception:
            pass

    def reveal(self, label: str = "Main Portfolio"):
        """Public helper for tests: ensure the Today tab is active and scroll the
        named account card / section header (e.g. 'Main Portfolio', 'Total
        investments value') into view before asserting its visibility."""
        self._scroll_portfolio_cards_into_view(label)

    def get_account_card_value(self, label: str) -> str | None:
        """Return the first money-looking text inside the account card identified
        by `label` (e.g. 'Main Portfolio', 'Superannuation'), or None if the card
        renders no dollar amount (e.g. an empty Jars/Kids card showing only 'Add').

        Cards live in their own clickable container; we read the TextViews within
        that container rather than the whole screen so we don't pick up the Home
        headline total by accident."""
        from utils.assertions import is_money
        card_locator = (AppiumBy.XPATH,
            f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{label}']]")
        self._scroll_portfolio_cards_into_view(label)
        cards = self.driver.find_elements(*card_locator)
        if not cards:
            return None
        for tv in cards[0].find_elements(
                AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]"):
            if is_money(tv.text):
                return tv.text
        return None

    def account_card_texts(self, label: str) -> list[str]:
        """All non-empty TextView strings inside the named account card."""
        return self._card_texts((AppiumBy.XPATH,
            f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{label}']]"),
            scroll_label=label)

    def pull_to_refresh(self):
        """Swipe down from near the top to trigger the pull-to-refresh gesture,
        then wait for the Home headline to settle back in."""
        import time
        size = self.driver.get_window_size()
        x = size["width"] // 2
        # Start high (just under the header chrome) and drag well down so the
        # refresh control engages, then release.
        self.driver.swipe(x, int(size["height"] * 0.30), x, int(size["height"] * 0.80), 800)
        time.sleep(1.0)

    def tap_tab_past(self):
        self.click(self.TAB_PAST)

    def tap_tab_today(self):
        self.click(self.TAB_TODAY)

    def tap_tab_future(self):
        self.click(self.TAB_FUTURE)

    def tap_add_funds(self):
        self.click(self.ADD_FUNDS_BUTTON)

    def tap_withdraw(self):
        self.click(self.WITHDRAW_BUTTON)

    def tap_performance_details(self):
        self.click(self.PERFORMANCE_DETAILS_ROW)

    def tap_rewards(self):
        self.click(self.REWARDS_ROW)

    # Scroll the target card into view by its own label, then tap it. The previous
    # approach always scrolled to "Superannuation", which on taller screens pushed
    # the Main Portfolio/Jars cards back off-screen and made the tap miss.
    def _tap_card(self, label: str, locator):
        """Scroll a portfolio card into view and tap it, confirming we actually
        left Home. On a slow device the first tap can register before the scroll
        settles and not navigate; retry once if we're still on Home with the card
        present (don't retry blindly — that would tap the wrong screen)."""
        import time
        # Portfolio cards only exist on the "Today" tab; a previous test may have
        # left Home on Past/Future (which show a different view with no cards), so
        # select Today first.
        if self.is_present_now(self.TAB_TODAY):
            try:
                self.tap_tab_today()
                time.sleep(0.5)
            except Exception:
                pass
        # scroll_to_text only searches forward; reset to the top so a card left
        # above the current scroll position (by a prior test) is still found.
        self.scroll_to_top()
        self.scroll_to_text(label)
        self.click(locator)
        time.sleep(1.2)
        if self.is_present_now(self.TOTAL_VALUE_LABEL) and self.is_present_now(locator):
            self.scroll_to_text(label)
            self.click(locator)

    def tap_main_portfolio(self):
        self._tap_card("Main Portfolio", self.MAIN_PORTFOLIO_CARD)

    def tap_jars(self):
        self._tap_card("Jars", self.JARS_CARD)

    def tap_kids(self):
        self._tap_card("Kids", self.KIDS_CARD)

    def tap_superannuation(self):
        self._tap_card("Superannuation", self.SUPERANNUATION_CARD)

    def tap_hamburger(self):
        self.click(self.HAMBURGER)

    def tap_settings(self):
        self.click(self.SETTINGS_GEAR)

    # --- Portfolio-card state (for RAIZ-10355: counts must update after create) ---
    def _card_texts(self, card_locator, scroll_label: str = "Main Portfolio") -> list[str]:
        self._scroll_portfolio_cards_into_view(scroll_label)
        cards = self.driver.find_elements(*card_locator)
        if not cards:
            return []
        return [t.text for t in cards[0].find_elements(
            AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]")]

    def jars_card_is_empty(self) -> bool:
        """True when the Jars card shows only the 'Add' affordance (no jars yet)."""
        return "Add" in self._card_texts(self.JARS_CARD, scroll_label="Jars")

    def kids_card_is_empty(self) -> bool:
        return "Add" in self._card_texts(self.KIDS_CARD, scroll_label="Kids")
