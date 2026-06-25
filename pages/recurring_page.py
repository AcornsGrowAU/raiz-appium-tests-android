import time

from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, POLL_INTERVAL
from pages.base_page import BasePage


class RecurringPage(BasePage):
    """Recurring investments.

    raiz://recurring_investments lists the destinations you can set a recurring
    investment for (MAIN PORTFOLIO, plus prompts for Kids/Jars). Tapping the main
    portfolio row opens a setup screen ("Set Recurring Investment" / "Set Savings
    Goal"); "Set Recurring Investment" then opens the amount + Frequency + Save
    form — the screen where RAIZ-9909 ("Save button obstructed and small") lived.
    """
    TITLE = (AppiumBy.XPATH, "//*[@text='Recurring investments']")
    MAIN_PORTFOLIO_SECTION = (AppiumBy.XPATH, "//*[@text='MAIN PORTFOLIO']")
    # The main-portfolio row, matched by its standard portfolio type so it works
    # regardless of the (test-data) portfolio name.
    PORTFOLIO_ROW = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Conservative' or @text='Moderate' "
        "or @text='Moderately Conservative' or @text='Moderately Aggressive' or @text='Aggressive' "
        "or @text='Emerald' or @text='Plus' or @text='Standard']]")

    # Setup screen (after tapping the portfolio row)
    CURRENT_BALANCE = (AppiumBy.XPATH, "//*[contains(@text,'Current balance:')]")
    SET_RECURRING_INVESTMENT = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Set Recurring Investment']]")
    SET_SAVINGS_GOAL = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Set Savings Goal']]")

    # Set Recurring Investment form (RAIZ-9909)
    RECURRING_AMOUNT_LABEL = (AppiumBy.XPATH, "//*[@text='Recurring Investment Amount']")
    FREQUENCY = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Frequency']]")
    SAVE_BUTTON = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Save']]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout) or self.is_visible(self.MAIN_PORTFOLIO_SECTION, timeout=2)

    def open_main_portfolio(self):
        self.click(self.PORTFOLIO_ROW)

    def is_setup_screen(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.SET_RECURRING_INVESTMENT, timeout=timeout)

    def open_set_recurring_investment(self):
        self.click(self.SET_RECURRING_INVESTMENT)

    def is_recurring_form(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.RECURRING_AMOUNT_LABEL, timeout=timeout)

    def is_savings_goal_offered(self, timeout=DEFAULT_WAIT) -> bool:
        """The setup screen offers both 'Set Recurring Investment' and 'Set
        Savings Goal'. Confirms the second path is present alongside the first."""
        return self.is_visible(self.SET_SAVINGS_GOAL, timeout=timeout)

    def is_frequency_present(self, timeout=DEFAULT_WAIT) -> bool:
        """The recurring form must expose a Frequency control (Daily/Weekly/etc.).
        Presence-checked here; the value check lives in is_current_balance_well_formed."""
        return self.is_visible(self.FREQUENCY, timeout=timeout)

    def get_current_balance_text(self, timeout=DEFAULT_WAIT) -> str:
        """Return the raw 'Current balance: $X' text from the setup screen.

        The balance is market-priced and loaded asynchronously, so on a slow
        emulator the row can render first as a placeholder (e.g. '$0.00' or a
        blank '$') and update to the real value a beat later. We poll until the
        rendered text carries a *positive* dollar value (or the timeout lapses,
        in which case we hand back whatever is on screen so the caller's value
        assertion fails against reality rather than against a loading frame)."""
        from utils.assertions import parse_money
        deadline = time.time() + timeout
        last = self.get_text(self.CURRENT_BALANCE)  # waits for the row to exist
        while time.time() < deadline:
            try:
                if parse_money(last) > 0:
                    return last
            except AssertionError:
                pass  # no money token yet (placeholder) — keep polling
            time.sleep(POLL_INTERVAL)
            if not self.is_present_now(self.CURRENT_BALANCE):
                break
            last = self.driver.find_elements(*self.CURRENT_BALANCE)[0].text
        return last

    def save_button_size(self):
        """(width, height) in px of the Save button, or None if absent/hidden.
        On an empty form the button is correctly *disabled*, so we check that it
        renders at a usable size rather than that it's clickable."""
        from utils.assertions import parse_bounds
        els = self.driver.find_elements(*self.SAVE_BUTTON)
        if not els or not els[0].is_displayed():
            return None
        return parse_bounds(els[0].get_attribute("bounds"))

    def is_save_button_well_rendered(self, min_w=200, min_h=40, timeout=DEFAULT_WAIT) -> bool:
        """Save must be displayed at a usable tap-target size — guards RAIZ-9909
        ('Save button obstructed and small'). Does not require it to be enabled
        (it's disabled until an amount/frequency are entered).

        The form settles/animates into place after it opens, so a single bounds
        read can catch the button mid-layout at a transient zero/small size. We
        poll until it measures at a usable size (returning early on success);
        only a button that stays small for the whole window is a real defect."""
        deadline = time.time() + timeout
        while True:
            size = self.save_button_size()
            if size is not None and size[0] >= min_w and size[1] >= min_h:
                return True
            if time.time() >= deadline:
                return False
            time.sleep(POLL_INTERVAL)
