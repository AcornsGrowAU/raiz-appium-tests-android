from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class MainPortfolioPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Main portfolio']")
    # The rebranded build titles this screen 'Invest' and labels the headline value
    # 'Your investment account value' (legacy: 'Main portfolio' / 'Your main
    # portfolio's investment value'). is_loaded() accepts either so the portfolio
    # fixtures aren't gated on build-specific copy.
    TITLE_REBRAND = (AppiumBy.XPATH, "//*[@text='Invest']")
    INVESTMENT_VALUE_HEADER = (AppiumBy.XPATH, "//*[contains(@text, 'investment account value') or contains(@text, \"main portfolio's investment value\")]")
    INVESTMENT_VALUE = (AppiumBy.XPATH, "//*[contains(@text, \"Your main portfolio's investment value\")]")
    INVESTMENT_AMOUNT = (AppiumBy.XPATH, "(//android.widget.TextView[contains(@text, '$')])[1]")

    ADD_FUNDS_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Add funds']]")
    WITHDRAW_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Withdraw']]")
    PERFORMANCE_DETAILS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Performance details']]")

    INVESTED_HEADER = (AppiumBy.XPATH, "//*[@text='Invested']")
    YOU_PORTFOLIO_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='You portfolio']]")
    NET_INVESTED_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Net invested by you']]")
    REWARDS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Rewards']]")
    TOTAL_INVESTED_LABEL = (AppiumBy.XPATH, "//*[@text='Total invested to date']")

    PERFORMANCE_HEADER = (AppiumBy.XPATH, "//*[@text='Performance']")
    MARKET_RETURN_LABEL = (AppiumBy.XPATH, "//*[@text='Market return to date:']")
    DIVIDENDS_LABEL = (AppiumBy.XPATH, "//*[@text='Dividends:']")
    TOTAL_RETURNS_LABEL = (AppiumBy.XPATH, "//*[@text='Total returns:']")

    ROUND_UPS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Round-Ups']]")
    RECURRING_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Recurring']]")
    TRANSACTION_HISTORY_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Transaction history']]")
    HOLDINGS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Holdings']]")
    DIVIDENDS_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Dividends']]")
    PAST_PERFORMANCE_ROW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Past performance']]")

    # Any one of these markers proves the portfolio screen loaded, across builds:
    # legacy 'Main portfolio' title, the rebrand 'Invest' title, or the headline
    # investment-value label. Combined into one locator so is_loaded() can POLL
    # for whichever this build renders — the previous code only waited on the
    # rebrand title (absent on 2.39.1d), so a slow deep-link navigation raced and
    # failed even though 'Main portfolio' was about to appear.
    ANY_TITLE = (AppiumBy.XPATH,
        "//*[@text='Main portfolio' or @text='Invest' "
        "or contains(@text,'investment account value') "
        "or contains(@text,\"main portfolio's investment value\")]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        if self.is_present_now(self.TITLE) or self.is_present_now(self.INVESTMENT_VALUE_HEADER):
            return True
        return self.is_present(self.ANY_TITLE, timeout=timeout)

    def get_investment_amount(self) -> str:
        return self.get_text(self.INVESTMENT_AMOUNT)

    def _row_amount(self, label: str) -> str:
        """Return the first dollar amount rendered inside the clickable row that
        carries `label`. Targets the 'amount belongs to the right label' class of
        defect (RAIZ-10251 totals) instead of grabbing a stray '$' anywhere.

        WATCH: assumes the row's value TextView is a descendant of the same
        clickable container as its label — true for the captured layout, not yet
        re-verified on-device for every row."""
        row_xpath = (
            f"//android.view.View[@clickable='true']"
            f"[.//android.widget.TextView[@text='{label}']]"
            f"//android.widget.TextView[contains(@text,'$')]"
        )
        els = self.driver.find_elements(AppiumBy.XPATH, row_xpath)
        return els[0].text if els else ""

    def get_you_portfolio_amount(self) -> str:
        """NOTE (2.39.1d redesign): the 'You portfolio' row's value is the
        portfolio NAME (e.g. 'Conservative'), not a dollar figure, so this row no
        longer exposes money. Retained for callers that still probe it; returns ''
        on this build. Use get_total_invested_amount()/get_net_invested_amount()
        for the money breakdown."""
        self.scroll_to_text("You portfolio")
        return self._row_amount("You portfolio")

    def get_net_invested_amount(self) -> str:
        self.scroll_to_text("Net invested by you")
        return self._row_amount("Net invested by you")

    def get_total_invested_amount(self) -> str:
        """'Total invested to date' value. The label and its $ value are rendered
        as adjacent TextViews in document order (not as parent/child or siblings
        under a shared node, and the XPath2 `following::` axis errors on this
        Compose tree), so we walk the ordered TextView list and return the first
        money token that appears AFTER the label."""
        self.scroll_to_text("Total invested to date")
        tvs = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
        texts = [t.text for t in tvs if t.text]
        try:
            idx = texts.index("Total invested to date")
        except ValueError:
            return ""
        for t in texts[idx + 1:]:
            if "$" in t:
                return t
        return ""

    def tap_add_funds(self):
        self.click(self.ADD_FUNDS_BUTTON)

    def tap_withdraw(self):
        self.click(self.WITHDRAW_BUTTON)

    def tap_performance_details(self):
        self.click(self.PERFORMANCE_DETAILS_ROW)

    # These rows live in the lower 'Manage'/'About' sections. A single swipe was
    # unreliable across screen sizes (failed on the emulator); scroll the row into
    # view by its label instead.
    def tap_transaction_history(self):
        self.scroll_to_text("Transaction history")
        self.click(self.TRANSACTION_HISTORY_ROW)

    def tap_holdings(self):
        self.scroll_to_text("Holdings")
        self.click(self.HOLDINGS_ROW)

    def tap_round_ups(self):
        self.scroll_to_text("Round-Ups")
        self.click(self.ROUND_UPS_ROW)

    def tap_recurring(self):
        self.scroll_to_text("Recurring")
        self.click(self.RECURRING_ROW)
