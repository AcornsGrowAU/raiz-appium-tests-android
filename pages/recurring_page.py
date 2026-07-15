import time

from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, POLL_INTERVAL
from pages.base_page import BasePage


class RecurringPage(BasePage):
    """Recurring investments.

    raiz://recurring_investments lists the destinations you can set a recurring
    investment for (MAIN PORTFOLIO, plus prompts for Kids/Jars). Tapping the main
    portfolio row opens the per-portfolio recurring OVERVIEW/setup screen, which
    renders ONE of two CTAs depending on BACKEND account state (ground truth:
    Android-AU build 3252, features/recurringv2/overview/RecurringOverviewScreen.kt
    `if (recurring != null)` branch + strings.xml set/edit button pair):

      - empty state -> 'Set Recurring Investment'  (RecurringEmptyStateCard)
      - set state   -> 'Edit Recurring Investment' (RecurringCard)

    BOTH CTAs route to the SAME amount + Frequency + Save form (onEditRecurringClick
    -> RecurringEditScreen) — the screen where RAIZ-9909 ("Save button obstructed
    and small") lived. Because the state is backend state, it survives app-data
    resets: navigation/detection here is therefore state-agnostic.
    """
    TITLE = (AppiumBy.XPATH, "//*[@text='Recurring investments']")
    MAIN_PORTFOLIO_SECTION = (AppiumBy.XPATH, "//*[@text='MAIN PORTFOLIO']")
    # The main-portfolio row, matched by its standard portfolio type so it works
    # regardless of the (test-data) portfolio name.
    PORTFOLIO_ROW = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Conservative' or @text='Moderate' "
        "or @text='Moderately Conservative' or @text='Moderately Aggressive' or @text='Aggressive' "
        "or @text='Emerald' or @text='Plus' or @text='Standard']]")

    # Overview/setup screen (after tapping the portfolio row)
    CURRENT_BALANCE = (AppiumBy.XPATH, "//*[contains(@text,'Current balance:')]")
    SET_RECURRING_INVESTMENT = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Set Recurring Investment']]")
    EDIT_RECURRING_INVESTMENT = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Edit Recurring Investment']]")
    # State-agnostic CTA: whichever of Set/Edit the overview is showing. Both open
    # the same recurring form.
    OPEN_RECURRING_FORM_CTA = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView["
        "@text='Set Recurring Investment' or @text='Edit Recurring Investment']]")
    # "We reached the overview" (either state): the 'Current balance:' header is a
    # single unconditional Text at the top of the overview column, and either CTA
    # counts too (the balance and the card paint as one composable, but keep both
    # signals so the earliest paint confirms the row tap took).
    OVERVIEW_REACHED = (AppiumBy.XPATH,
        "//*[contains(@text,'Current balance:')] "
        "| //android.widget.TextView[@text='Set Recurring Investment' "
        "or @text='Edit Recurring Investment']")
    SET_SAVINGS_GOAL = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Set Savings Goal']]")

    # Set Recurring Investment form (RAIZ-9909).
    # NOTE: 'Recurring Investment Amount' does NOT uniquely identify the form —
    # the same string (recurring_overview_recurring_card_title) also titles the
    # overview card in BOTH states (RecurringOverviewScreen.kt passes it to
    # RecurringEmptyStateCard; RecurringCard renders it too; RecurringEditScreen.kt
    # line ~234 renders it on the form). The form's DISTINCTIVE surface is its
    # amount input: a Compose BasicTextField (RecurringEditScreen.kt line ~247)
    # that surfaces to UiAutomator2 as android.widget.EditText — the overview has
    # no text field.
    RECURRING_AMOUNT_LABEL = (AppiumBy.XPATH, "//*[@text='Recurring Investment Amount']")
    AMOUNT_FIELD = (AppiumBy.CLASS_NAME, "android.widget.EditText")
    FREQUENCY = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Frequency']]")
    SAVE_BUTTON = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Save']]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout) or self.is_visible(self.MAIN_PORTFOLIO_SECTION, timeout=2)

    def open_main_portfolio(self, timeout=25) -> bool:
        """Tap the MAIN PORTFOLIO row on the recurring list, retrying past the
        async shimmer/Loading state and re-tapping a swallowed tap.

        The list deep-link lands in a Loading (shimmer) state and resolves to
        real rows only after a network fetch; the TopBar title renders during
        the shimmer, so is_loaded() returns True before any row exists. We poll
        for the actual clickable row, tap the clickable CONTAINER (last match,
        suite convention: innermost clickable = the row itself), and confirm we
        left the list — a freshly-laid-out Compose list can swallow the first
        tap. Returns False if the overview never painted (callers assert
        is_setup_screen right after, so failures still surface)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            rows = self.driver.find_elements(*self.PORTFOLIO_ROW)
            if rows:
                try:
                    rows[-1].click()
                except Exception:  # stale/animating row — re-query and retry
                    time.sleep(POLL_INTERVAL)
                    continue
                # Confirm the tap took: the overview (loading -> paint) appears.
                if self._overview_reached(timeout=12):
                    return True
                # Swallowed tap (still on the list) — loop and re-tap.
            time.sleep(POLL_INTERVAL)
        return False

    def _overview_reached(self, timeout=12) -> bool:
        """Poll for a state-agnostic overview surface ('Current balance:' or
        either CTA) — tolerates the row tap routing through the async
        RecurringLoading screen before the overview paints."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.driver.find_elements(*self.OVERVIEW_REACHED):
                return True
            time.sleep(POLL_INTERVAL)
        return False

    def is_setup_screen(self, timeout=DEFAULT_WAIT) -> bool:
        """True when the per-portfolio overview/setup screen is on screen, in
        EITHER state ('Set' or 'Edit Recurring Investment' CTA visible).

        Keying on 'Set Recurring Investment' alone couples the check to backend
        account state: once ANY run persists a recurring for the account, the
        card flips to 'Edit Recurring Investment' forever (app-data resets do
        not clear it), and a Set-only probe returns False even though the
        navigation succeeded."""
        return self.is_visible(self.OPEN_RECURRING_FORM_CTA, timeout=timeout)

    def open_set_recurring_investment(self, timeout=DEFAULT_WAIT, attempts=4) -> bool:
        """Open the amount + Frequency + Save form via whichever CTA the
        overview is showing ('Set ...' in empty state, 'Edit ...' in set state
        — both route to the same RecurringEditScreen form). Confirms the tap
        took (the form's amount EditText painted — the label text is NOT
        distinctive, see AMOUNT_FIELD note) and re-taps a swallowed tap.
        Returns False if the form never painted (callers assert
        is_recurring_form right after, so failures still surface)."""
        for _ in range(attempts):
            deadline = time.time() + timeout
            els = self.driver.find_elements(*self.OPEN_RECURRING_FORM_CTA)
            while not els and time.time() < deadline:
                time.sleep(POLL_INTERVAL)
                els = self.driver.find_elements(*self.OPEN_RECURRING_FORM_CTA)
            if not els:
                return False
            try:
                els[-1].click()  # innermost clickable container = the CTA button
            except Exception:  # stale/animating CTA — re-query and retry
                time.sleep(POLL_INTERVAL)
                continue
            confirm_deadline = time.time() + 10
            while time.time() < confirm_deadline:
                # Confirm on the form's amount EditText — the one surface the
                # overview does NOT have ('Recurring Investment Amount' titles
                # the overview card too, so it cannot confirm the navigation).
                if self.driver.find_elements(*self.AMOUNT_FIELD):
                    return True
                time.sleep(POLL_INTERVAL)
            # Swallowed tap (form never painted) — loop and re-tap.
        return False

    def is_recurring_form(self, timeout=DEFAULT_WAIT) -> bool:
        """True only on the amount + Frequency + Save form. Requires BOTH the
        'Recurring Investment Amount' text AND the amount EditText: the text
        alone also titles the overview card (both states), so keying on it alone
        reported 'on the form' while still on the overview — misattributing any
        downstream Save-button failure to RAIZ-9909 instead of navigation."""
        deadline = time.time() + timeout
        while True:
            if (self.is_present_now(self.RECURRING_AMOUNT_LABEL)
                    and self.is_present_now(self.AMOUNT_FIELD)):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(POLL_INTERVAL)

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
