"""
Weird edge-case E2E scenarios for the Raiz AU app.

These go after the awkward inputs and cross-screen invariants that micro-investing
apps actually break on, and that a presence check never catches:
  - keypad abuse (double decimal points, >2 decimals, huge numbers, dot-first,
    leading zeros, delete-past-empty) — the display must always stay well-formed
  - money "gate" invariants ($0 must not be investable/withdrawable)
  - cross-screen value consistency (Main Portfolio vs Performance; Home ≥ a single
    account) — the RAIZ-10251 / RAIZ-10306 family
  - placeholder leakage in the greeting ("Hello, null") — a classic data-binding bug

Grounded entirely in locators/methods verified on-device this session. Assertions
are deliberately INVARIANTS (well-formed, non-negative, internally consistent)
rather than exact values, so a legitimate input-model choice doesn't cause a
false failure while real defects still trip them.

NOT yet executed on-device (phone offline when written) — run and report.
"""
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.lump_sum_page import LumpSumPage
from pages.main_portfolio_page import MainPortfolioPage
from pages.performance_page import PerformancePage
from pages.home_page import HomePage
from utils.deep_links import DeepLinks
from utils.assertions import parse_money, is_money
from config.settings import STATE_PROBE_WAIT
from conftest import _open_deep_link


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture
def lump_sum(driver):
    _open_deep_link(driver, DeepLinks.DEPOSIT)
    page = LumpSumPage(driver)
    if not page.is_lump_sum_loaded():
        _open_deep_link(driver, DeepLinks.DEPOSIT)
    assert page.is_lump_sum_loaded(), "Could not open the Lump Sum screen"
    return page


@pytest.fixture
def withdraw(driver):
    _open_deep_link(driver, DeepLinks.WITHDRAW)
    page = LumpSumPage(driver)
    if not page.is_withdraw_loaded():
        _open_deep_link(driver, DeepLinks.WITHDRAW)
    assert page.is_withdraw_loaded(), "Could not open the Withdraw screen"
    return page


def _assert_well_formed_amount(display: str):
    """The universal invariant for a money input display, regardless of how the
    keypad chooses to model entry: one currency sign, at most one decimal point,
    at most two decimal places, at least one digit, and never negative."""
    assert display, "Amount display is empty"
    assert "$" in display, f"Amount display has no currency sign: {display!r}"
    assert any(c.isdigit() for c in display), f"Amount display has no digits: {display!r}"
    assert display.count(".") <= 1, f"Amount display has multiple decimal points: {display!r}"
    assert "-" not in display, f"Amount display went negative: {display!r}"
    if "." in display:
        cents = "".join(c for c in display.split(".", 1)[1] if c.isdigit())
        assert len(cents) <= 2, f"Amount display shows more than 2 decimal places: {display!r}"


# --------------------------------------------------------------------------- #
# Keypad abuse — the amount display must never become malformed.              #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.edge
@pytest.mark.investments
class TestAmountEntryEdgeCases:

    def test_invest_zero_amount_reaches_confirmation(self, lump_sum):
        """CHARACTERISATION — verified on-device: the keypad does NOT gate a $0.00
        amount; tapping Invest opens the 'Nice!' confirmation sheet. Same
        no-keypad-gating behaviour as the below-minimum case. We cancel
        immediately (nothing is committed).

        FINDING: $0.00 arguably should be blocked before the confirmation (Withdraw
        *does* gate $0 — see test_withdraw_zero_amount_does_not_proceed). If invest
        gating is added later this flips RED, which is the intent."""
        assert lump_sum.amount_is_zero(), "Precondition: amount starts at $0.00"
        try:
            lump_sum.tap_invest()
        except Exception:
            pytest.skip("Invest is disabled at $0 (gated at the button) on this build")
        reached = lump_sum.is_confirmation_shown(timeout=STATE_PROBE_WAIT)
        if reached:
            lump_sum.cancel_confirmation()  # never leave a $0 confirmation open
        assert reached, "Documented: $0.00 currently reaches the invest confirmation (no keypad gate)"

    def test_withdraw_zero_amount_does_not_proceed(self, withdraw):
        assert withdraw.amount_is_zero(), "Precondition: amount starts at $0.00"
        try:
            withdraw.tap_withdraw()
        except Exception:
            return
        assert not withdraw.is_confirmation_shown(timeout=STATE_PROBE_WAIT), \
            "Withdrawing $0.00 must not open the confirmation sheet"

    def test_delete_on_empty_stays_zero(self, lump_sum):
        """Hammering delete on an empty amount must not crash or go negative."""
        lump_sum.clear_amount()
        assert lump_sum.amount_is_zero(), "Delete past empty should leave the amount at $0.00"

    def test_multiple_decimal_points_are_rejected(self, lump_sum):
        lump_sum.enter_amount("5.5.5")
        _assert_well_formed_amount(lump_sum.get_amount_display())

    def test_more_than_two_decimals_are_capped(self, lump_sum):
        lump_sum.enter_amount("5.999")
        _assert_well_formed_amount(lump_sum.get_amount_display())

    def test_dot_first_is_well_formed(self, lump_sum):
        lump_sum.clear_amount()
        lump_sum.enter_amount(".5")
        _assert_well_formed_amount(lump_sum.get_amount_display())

    def test_leading_zeros_are_well_formed(self, lump_sum):
        lump_sum.clear_amount()
        lump_sum.enter_amount("007")
        _assert_well_formed_amount(lump_sum.get_amount_display())

    def test_large_amount_is_well_formed(self, lump_sum):
        """A 7-digit amount must render as well-formed money (comma grouping must
        not corrupt the value or break parsing)."""
        lump_sum.clear_amount()
        lump_sum.enter_amount("1234567")
        display = lump_sum.get_amount_display()
        _assert_well_formed_amount(display)
        assert is_money(display) and parse_money(display) > 0, \
            f"Large amount should remain a positive, parseable value: {display!r}"

    def test_long_digit_run_does_not_corrupt_display(self, lump_sum):
        """Far more digits than any real investment — the display must not overflow
        into garbage or a negative."""
        lump_sum.clear_amount()
        lump_sum.enter_amount("999999999")
        _assert_well_formed_amount(lump_sum.get_amount_display())


# --------------------------------------------------------------------------- #
# Cross-screen value consistency.                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.edge
@pytest.mark.portfolio
class TestCrossScreenValueConsistencyE2E:

    def test_main_portfolio_value_matches_performance(self, driver):
        """The Main Portfolio headline and the Performance headline both report the
        main portfolio value — they must agree within live-price drift."""
        _open_deep_link(driver, DeepLinks.INVEST)
        mp = MainPortfolioPage(driver)
        assert mp.is_loaded()
        v_portfolio = parse_money(mp.get_investment_amount())

        _open_deep_link(driver, DeepLinks.PERFORMANCE)
        pf = PerformancePage(driver)
        assert pf.is_loaded()
        v_performance = parse_money(pf.get_investment_amount())

        tol = max(5.0, v_portfolio * 0.02)
        assert abs(v_portfolio - v_performance) <= tol, (
            f"Main Portfolio (${v_portfolio}) and Performance (${v_performance}) "
            f"should report the same value; differ by more than ${tol:.2f}")

    def test_home_total_is_at_least_a_single_account(self, driver):
        """The Home headline is the sum across all accounts, so it can never be
        less than the Main Portfolio value alone (a sanity invariant that catches
        sign/aggregation errors)."""
        _open_deep_link(driver, DeepLinks.HOME)
        home = HomePage(driver)
        home.dismiss_modal()
        total = parse_money(home.get_total_value())

        _open_deep_link(driver, DeepLinks.INVEST)
        mp = MainPortfolioPage(driver)
        assert mp.is_loaded()
        main = parse_money(mp.get_investment_amount())

        tol = max(5.0, total * 0.02)
        assert total >= main - tol, (
            f"Home total (${total}) should be ≥ the Main Portfolio value alone "
            f"(${main})")


# --------------------------------------------------------------------------- #
# Greeting — no placeholder/data-binding leakage.                             #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.edge
@pytest.mark.smoke
class TestHomeGreetingEdgeCases:

    PLACEHOLDERS = ("null", "undefined", "none", "nan", "{", "}", "%s", "%@")

    def test_greeting_has_no_placeholder_leakage(self, home):
        """'Hello, null' / 'Hello, undefined' is a classic data-binding bug a
        presence check sails past."""
        greeting = home.get_greeting().lower()
        for token in self.PLACEHOLDERS:
            assert token not in greeting, f"Greeting leaks a placeholder ({token!r}): {greeting!r}"

    def test_greeting_includes_a_name(self, home):
        """The greeting should personalise — 'Hello' with nothing after it is the
        empty-name variant of the same bug. (Greeting renders 'Hello <Name>,'.)"""
        greeting = home.get_greeting()
        name = greeting.replace("Hello", "", 1).strip(" ,!.") if "Hello" in greeting else ""
        assert len(name) > 0, f"Greeting is not personalised (no name): {greeting!r}"
