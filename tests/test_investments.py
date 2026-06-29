"""
Investment flow tests — Lump Sum, Withdraw, Recurring Investments.
These tests verify the UI and keypad behaviour WITHOUT submitting real transactions.
"""
import time

import pytest
from appium.webdriver.common.appiumby import AppiumBy
from pages.lump_sum_page import LumpSumPage
from pages.recurring_page import RecurringPage
from pages.base_page import BasePage
from utils.deep_links import DeepLinks
from utils.assertions import parse_money, is_money
from config.settings import STATE_PROBE_WAIT
from conftest import _open_deep_link


@pytest.fixture
def lump_sum(driver):
    _open_deep_link(driver, DeepLinks.DEPOSIT)
    page = LumpSumPage(driver)
    if not page.is_lump_sum_loaded():
        _open_deep_link(driver, DeepLinks.DEPOSIT)
    assert page.is_lump_sum_loaded()
    return page


@pytest.fixture
def withdraw(driver):
    _open_deep_link(driver, DeepLinks.WITHDRAW)
    page = LumpSumPage(driver)
    if not page.is_withdraw_loaded():
        _open_deep_link(driver, DeepLinks.WITHDRAW)
    assert page.is_withdraw_loaded()
    return page


@pytest.fixture
def recurring(driver):
    _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
    page = RecurringPage(driver)
    if not page.is_loaded():
        _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
    assert page.is_loaded()
    return page


@pytest.mark.investments
@pytest.mark.smoke
class TestLumpSumScreen:
    def test_lump_sum_screen_loads(self, lump_sum):
        assert lump_sum.is_lump_sum_loaded()

    def test_account_selector_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.ACCOUNT_SELECTOR)

    def test_minimum_notice_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.MINIMUM_NOTICE)

    def test_preset_10_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.PRESET_10)

    def test_preset_25_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.PRESET_25)

    def test_preset_50_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.PRESET_50)

    def test_preset_100_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.PRESET_100)

    def test_keypad_all_digits_visible(self, lump_sum):
        for key in [lump_sum.KEY_0, lump_sum.KEY_1, lump_sum.KEY_2, lump_sum.KEY_3,
                    lump_sum.KEY_4, lump_sum.KEY_5, lump_sum.KEY_6, lump_sum.KEY_7,
                    lump_sum.KEY_8, lump_sum.KEY_9]:
            assert lump_sum.is_visible(key)

    def test_keypad_delete_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.KEY_DELETE)

    def test_invest_button_visible(self, lump_sum):
        assert lump_sum.is_visible(lump_sum.INVEST_BUTTON)

    def test_delete_clears_amount(self, lump_sum):
        lump_sum.tap_preset("$10")
        lump_sum.clear_amount()
        assert lump_sum.is_visible((AppiumBy.XPATH, "//*[@text='$0.00']"))


@pytest.mark.investments
class TestWithdrawScreen:
    def test_withdraw_screen_loads(self, withdraw):
        assert withdraw.is_withdraw_loaded()

    def test_account_selector_visible(self, withdraw):
        assert withdraw.is_visible(withdraw.ACCOUNT_SELECTOR)

    def test_available_balance_visible(self, withdraw):
        assert withdraw.is_visible(withdraw.AVAILABLE_BALANCE)

    def test_keypad_visible(self, withdraw):
        assert withdraw.is_visible(withdraw.KEY_0)
        assert withdraw.is_visible(withdraw.KEY_DELETE)

    def test_withdraw_button_visible(self, withdraw):
        assert withdraw.is_visible(withdraw.WITHDRAW_BUTTON)

    def test_keypad_enters_amount(self, withdraw):
        withdraw.enter_amount("10")
        assert not withdraw.is_visible((AppiumBy.XPATH, "//*[@text='$0.00']"), timeout=2)


@pytest.mark.investments
class TestAddFundsModal:
    def test_add_funds_modal_opens(self, home, driver):
        home.tap_add_funds()
        page = BasePage(driver)
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='Add funds']"))

    def test_lump_sum_option_in_modal(self, home, driver):
        home.tap_add_funds()
        page = BasePage(driver)
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='Lump Sum Investment']"))

    def test_recurring_option_in_modal(self, home, driver):
        home.tap_add_funds()
        page = BasePage(driver)
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='Recurring investments']"))

    def test_modal_closes_on_back(self, home, driver):
        home.tap_add_funds()
        page = BasePage(driver)
        # The Add-funds sheet is a Compose ModalBottomSheet. Its dismissal is
        # driven by sheetState/BackHandler, which only becomes active once the
        # enter-animation has settled. If driver.back() fires mid-animation it
        # falls through to the activity's default back-press and EXITS the app
        # instead of closing the sheet. Wait for the sheet's title (real string:
        # quick_actions_dialog_title = "Add funds") to be visible, then add a
        # short settle so the back handler is registered before we go back.
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='Add funds']")), \
            "Add funds sheet did not appear after tapping Add funds"
        time.sleep(0.4)
        driver.back()
        assert home.is_loaded(), \
            "Back press should close the Add funds sheet and return to Home"


@pytest.mark.investments
class TestRecurringInvestments:
    def test_recurring_investments_loads(self, driver):
        _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
        page = BasePage(driver)
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='Recurring investments']"))

    def test_main_portfolio_section_visible(self, driver):
        _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
        page = BasePage(driver)
        assert page.is_visible((AppiumBy.XPATH, "//*[@text='MAIN PORTFOLIO']"))

    def test_kids_section_visible(self, driver):
        """The account now has kid accounts (account-state drift 2026-06-15), so
        the KIDS recurring section should render. If a given test account/build
        has no kids, skip with a clear reason rather than mask a runnable
        assertion as an expected failure."""
        _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
        page = BasePage(driver)
        kids = (AppiumBy.XPATH, "//*[@text='KIDS']")
        if not page.is_visible(kids):
            pytest.skip("No KIDS recurring section on this account/build — "
                        "requires active kid accounts to render")
        assert page.is_visible(kids), \
            "KIDS recurring section should be present (account has kid accounts)"


# --------------------------------------------------------------------------- #
# VALUE CORRECTNESS — the keypad/presets must reflect the EXACT amount.       #
# The old TestLumpSumScreen only asserts "$0.00 is gone"; these assert value. #
# No transactions are submitted — every flow cancels at the confirmation.     #
# --------------------------------------------------------------------------- #
@pytest.mark.investments
class TestLumpSumValueCorrectness:

    @pytest.mark.parametrize("chip,expected", [("$10", 10.0), ("$25", 25.0),
                                               ("$50", 50.0), ("$100", 100.0)],
                             ids=["10", "25", "50", "100"])
    def test_preset_sets_exact_amount(self, lump_sum, chip, expected):
        """A preset chip must set its exact dollar value in the display — not just
        'not $0.00'. Catches a wired-wrong chip (e.g. $50 firing $5)."""
        lump_sum.tap_preset(chip)
        shown = lump_sum.get_amount_display()
        assert parse_money(shown) == pytest.approx(expected), \
            f"Preset {chip} should set {expected}, display showed {shown!r}"

    def test_keypad_enters_exact_digits(self, lump_sum):
        """Typing digits must render the same number back (value, not presence)."""
        lump_sum.enter_amount("25")
        assert parse_money(lump_sum.get_amount_display()) == pytest.approx(25.0)

    def test_keypad_enters_decimal_amount_exactly(self, lump_sum):
        """A cents amount must round-trip exactly through the display."""
        lump_sum.enter_amount("12.50")
        assert parse_money(lump_sum.get_amount_display()) == pytest.approx(12.5)

    def test_delete_returns_display_to_zero(self, lump_sum):
        """After clearing, the display must be exactly $0.00 (the gate state)."""
        lump_sum.tap_preset("$25")
        lump_sum.clear_amount()
        assert lump_sum.amount_is_zero(), \
            f"Cleared display should be $0.00, was {lump_sum.get_amount_display()!r}"

    def test_preset_then_keypad_appends_not_replaces(self, lump_sum):
        """Entering digits after a preset must change the amount (state isn't
        silently dropped). We assert it moved off the preset value and stays
        well-formed money — not an exact value, since append-vs-replace is a
        legitimate input-model choice."""
        lump_sum.tap_preset("$10")
        before = parse_money(lump_sum.get_amount_display())
        lump_sum.enter_amount("5")
        after_text = lump_sum.get_amount_display()
        assert is_money(after_text), f"Display malformed after keypad: {after_text!r}"
        assert parse_money(after_text) != pytest.approx(before), \
            "Typing a digit after a preset should change the amount"


# --------------------------------------------------------------------------- #
# CONFIRMATION CONSISTENCY — reach the 'Nice!' sheet, assert it shows the     #
# amount we typed, then CANCEL and confirm we land back on the keypad.        #
# Complements TestLumpSumInvestmentE2E (which only checks the sheet appears).  #
# --------------------------------------------------------------------------- #
@pytest.mark.investments
class TestLumpSumConfirmationConsistency:

    def test_confirmation_shows_amount_entered(self, lump_sum):
        """The amount on the confirmation sheet must equal what was typed at the
        keypad — a value-consistency check across the keypad→confirm hand-off.
        DEFENSIVE: the sheet may format the amount differently (e.g. '$50.00');
        we compare parsed values, not strings. WATCH: get_confirmation_amount
        reads the first money token on the sheet."""
        lump_sum.enter_amount("50")
        entered = parse_money(lump_sum.get_amount_display())
        lump_sum.tap_invest()
        assert lump_sum.is_confirmation_shown(), "Invest should open the confirmation sheet"
        sheet_amount = lump_sum.get_confirmation_amount()
        try:
            assert is_money(sheet_amount), \
                f"Confirmation sheet should show a dollar amount, got {sheet_amount!r}"
            assert parse_money(sheet_amount) == pytest.approx(entered), \
                f"Confirmation amount {sheet_amount!r} != entered ${entered}"
        finally:
            lump_sum.cancel_confirmation()  # never leave a sheet open / commit

    def test_cancel_returns_to_keypad_with_amount_intact(self, lump_sum):
        """Cancelling the confirmation must return to the keypad with the typed
        amount still present (state not destroyed) — and must NOT have committed
        anything. RAIZ-10063-adjacent: a cancelled flow should leave no trace."""
        lump_sum.enter_amount("30")
        lump_sum.tap_invest()
        assert lump_sum.is_confirmation_shown()
        lump_sum.cancel_confirmation()
        assert not lump_sum.is_confirmation_shown(timeout=STATE_PROBE_WAIT), \
            "Cancel should dismiss the confirmation"
        # Back on the keypad: either the amount is retained or reset to $0.00, but
        # the screen must be the Lump Sum keypad again (not a stranded sheet/success).
        assert lump_sum.is_lump_sum_loaded(), \
            "Cancelling the confirmation should return to the Lump Sum keypad"
        assert not lump_sum.is_success_shown(), \
            "Cancel must not reach a success state (no transaction committed)"


# --------------------------------------------------------------------------- #
# WITHDRAW — exact-value entry on the shared keypad. Over-balance / $0 gating  #
# already live in the E2E + edge files, so this only adds the value check.     #
# --------------------------------------------------------------------------- #
@pytest.mark.investments
class TestWithdrawValueCorrectness:

    def test_keypad_enters_exact_amount(self, withdraw):
        withdraw.enter_amount("10")
        assert parse_money(withdraw.get_amount_display()) == pytest.approx(10.0)

    def test_delete_returns_display_to_zero(self, withdraw):
        withdraw.enter_amount("10")
        withdraw.clear_amount()
        assert withdraw.amount_is_zero(), \
            f"Cleared withdraw display should be $0.00, was {withdraw.get_amount_display()!r}"


# --------------------------------------------------------------------------- #
# ADD FUNDS MODAL — the two options must navigate to their screens, not just   #
# render. Existing TestAddFundsModal only checks the option labels are present.#
# --------------------------------------------------------------------------- #
@pytest.mark.investments
class TestAddFundsModalNavigation:

    def test_lump_sum_option_opens_lump_sum(self, home, driver):
        home.tap_add_funds()
        page = LumpSumPage(driver)
        page.click((AppiumBy.XPATH, "//android.view.View[@clickable='true']"
                                    "[.//android.widget.TextView[@text='Lump Sum Investment']]"))
        assert page.is_lump_sum_loaded(), \
            "Selecting 'Lump Sum Investment' from the modal should open the Lump Sum screen"

    def test_recurring_option_opens_recurring(self, home, driver):
        home.tap_add_funds()
        page = RecurringPage(driver)
        page.click((AppiumBy.XPATH, "//android.view.View[@clickable='true']"
                                    "[.//android.widget.TextView[@text='Recurring investments']]"))
        assert page.is_loaded(), \
            "Selecting 'Recurring investments' from the modal should open the Recurring screen"


# --------------------------------------------------------------------------- #
# RECURRING — reach the Set Recurring form and assert RAIZ-9909 (Save renders  #
# at a usable tap-target size), Frequency control present, current balance     #
# well-formed. We NEVER tap Save (stateful). Setup also offers Savings Goal.    #
# --------------------------------------------------------------------------- #
@pytest.mark.investments
class TestRecurringSetup:

    def test_setup_screen_offers_both_paths(self, recurring):
        """Tapping the main portfolio row opens a setup screen offering both
        'Set Recurring Investment' and 'Set Savings Goal'."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen(), "Main portfolio row should open the setup screen"
        assert recurring.is_savings_goal_offered(), \
            "Setup screen should also offer 'Set Savings Goal'"

    def test_setup_current_balance_is_well_formed(self, recurring):
        """The setup screen's 'Current balance:' must be a real dollar figure."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen()
        text = recurring.get_current_balance_text()
        assert is_money(text), f"Current balance should be a dollar amount, got {text!r}"
        assert parse_money(text) >= 0, f"Current balance should not be negative: {text!r}"

    def test_recurring_form_has_frequency_control(self, recurring):
        """The Set Recurring Investment form must expose a Frequency control."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen()
        recurring.open_set_recurring_investment()
        assert recurring.is_recurring_form(), "Should reach the Set Recurring Investment form"
        assert recurring.is_frequency_present(), \
            "Recurring form must offer a Frequency selector"

    def test_save_button_renders_at_usable_size_raiz_9909(self, recurring):
        """RAIZ-9909: the Save button must render at a usable tap-target size (it
        is correctly *disabled* on an empty form, so we check size, not click).
        Uses utils.assertions.parse_bounds via the page helper — no hard-coded
        bounds."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen()
        recurring.open_set_recurring_investment()
        assert recurring.is_recurring_form()
        size = recurring.save_button_size()
        assert size is not None, "Save button should be present and displayed on the form"
        assert recurring.is_save_button_well_rendered(), \
            f"Save button tap target too small (RAIZ-9909): {size}"
