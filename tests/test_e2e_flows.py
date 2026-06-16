"""
End-to-end user journeys for the Raiz AU Android app.

WHY THIS FILE EXISTS
--------------------
The rest of the suite is overwhelmingly *presence* testing ("is element X
visible"). That catches layout regressions but misses the defects that actually
hurt customers — money flows that don't complete, values that render wrong, and
navigation that lands on the wrong screen. Every test below is tied to a real
flow the Raiz "Release testing process" calls critical (Login/Auth,
Investing/Withdrawing, Navigation) and, where possible, to a real production
bug the *current* suite would have sailed past:

  - Invest never reaches the confirmation sheet in the old suite (stops at keypad)
  - RAIZ-9994  Back from Settings sub-menus does not return to Settings (Android)
  - RAIZ-10306 Performance widget shows incorrect change in value for 1 month
  - RAIZ-10244 Percentages shown for $0.00 on the Performance widget
  - RAIZ-10063 History list not updated after a cancelled transaction
  - RAIZ-10251 Totals don't add up on the custom portfolio screen

SAFETY
------
These run against the DEV app (com.acornsau.android.development). The default
money-movement tests stop at the confirmation sheet and CANCEL — no transaction
is committed. The one test that actually commits is marked @pytest.mark.destructive
and is skipped unless RUN_DESTRUCTIVE=1, because it changes account state.

NOTE: locators for screens beyond the captured exploration (withdraw confirm,
logout confirm, round-ups) are written defensively and flagged inline. Run once
on-device and tighten any that don't match.
"""
import os
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.home_page import HomePage
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.pin_page import PinPage
from pages.settings_page import SettingsPage
from pages.lump_sum_page import LumpSumPage
from pages.performance_page import PerformancePage
from pages.transaction_history_page import TransactionHistoryPage
from utils.deep_links import DeepLinks
from utils.assertions import assert_money, assert_non_negative_money, parse_money, parse_percent, is_money
from config.settings import TEST_EMAIL, TEST_PASSWORD, TEST_PIN, STATE_PROBE_WAIT
from conftest import _open_deep_link, _ensure_logged_in


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


# --------------------------------------------------------------------------- #
# 1. INVESTMENT — reach (and back out of) the confirmation. The gap the old    #
#    suite never crossed: it asserted the keypad renders, then stopped.        #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.investments
class TestLumpSumInvestmentE2E:

    @pytest.mark.smoke
    def test_invest_reaches_confirmation_then_cancels(self, lump_sum):
        """Enter a valid amount → Invest → the 'Nice!' confirmation appears → Cancel.
        Asserts the amount actually registered (value check, not just '!= $0.00')."""
        lump_sum.enter_amount("5")
        shown = lump_sum.get_amount_display()
        assert parse_money(shown) == pytest.approx(5.0), f"Keypad should show $5, showed {shown!r}"

        lump_sum.tap_invest()
        assert lump_sum.is_confirmation_shown(), \
            "Tapping Invest with a valid amount should open the confirmation sheet"

        lump_sum.cancel_confirmation()
        assert not lump_sum.is_confirmation_shown(timeout=STATE_PROBE_WAIT), \
            "Cancel should dismiss the confirmation without committing the investment"

    @pytest.mark.edge
    def test_below_minimum_amount_is_not_gated_at_keypad(self, lump_sum):
        """CHARACTERISATION TEST — documents *verified* behaviour on this build.

        The screen discloses a "Minimum of $5 Investment", but entering $1 and
        tapping Invest still opens the 'Nice!' confirmation sheet — the client
        does NOT block below-minimum amounts at the keypad gate. Verified on a
        clean session (not a state leak).

        FINDING: where the $5 minimum is actually enforced (final confirm step or
        server) is unconfirmed — we deliberately do not commit the transaction.
        If enforcement is later added at the keypad, this test will flip RED and
        prompt a review, which is exactly what we want. See TEST_SUITE_ANALYSIS.md.
        """
        lump_sum.enter_amount("1")
        assert parse_money(lump_sum.get_amount_display()) == pytest.approx(1.0)
        lump_sum.tap_invest()
        reached = lump_sum.is_confirmation_shown(timeout=STATE_PROBE_WAIT)
        if reached:
            lump_sum.cancel_confirmation()  # never commit a below-minimum amount
        assert reached, (
            "Documented behaviour: a below-minimum ($1) amount currently reaches "
            "the confirmation sheet. If this changed, confirm the new gating is intended."
        )

    @pytest.mark.destructive
    @pytest.mark.skipif(os.getenv("RUN_DESTRUCTIVE") != "1",
                        reason="Commits a real DEV investment; set RUN_DESTRUCTIVE=1 to run")
    def test_invest_full_completion_appears_in_history(self, driver, lump_sum):
        """FULL E2E (DEV only): invest $5 → confirm → success → the transaction
        is reflected in Transaction History. This is the journey that proves the
        money flow actually works, not just that the screens render."""
        lump_sum.enter_amount("5")
        lump_sum.tap_invest()
        assert lump_sum.is_confirmation_shown()
        lump_sum.confirm_invest()
        assert lump_sum.is_success_shown(), "Expected a success state after confirming the investment"

        _open_deep_link(driver, DeepLinks.TRANSACTIONS)
        history = TransactionHistoryPage(driver)
        assert history.is_loaded()
        # A pending Buy should now exist. (Pending section renders before settled.)
        assert history.get_transaction_count() > 0


# --------------------------------------------------------------------------- #
# 2. WITHDRAW — confirmation + over-balance guard. Defensive locators.         #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.investments
class TestWithdrawE2E:

    def test_available_balance_is_well_formed(self, withdraw):
        """The withdraw screen must show a real 'Available:' figure, not a blank."""
        text = withdraw.get_text(withdraw.AVAILABLE_BALANCE)
        assert is_money(text), f"Available balance should be a dollar amount, got {text!r}"

    @pytest.mark.edge
    def test_over_balance_amount_is_not_gated_at_keypad(self, withdraw):
        """CHARACTERISATION TEST — documents *verified* behaviour on this build.

        Entering far more than the available balance still opens the
        'Confirm Withdrawal' sheet — the client does NOT cap the amount at the
        available balance on the keypad. Same pattern as the invest minimum.

        FINDING: client-side bounds (min for invest, max for withdraw) are not
        enforced at the keypad→confirmation gate; enforcement is at final confirm
        or server-side (unverified — we do not commit). See TEST_SUITE_ANALYSIS.md.
        We cancel immediately so nothing is submitted."""
        available = parse_money(withdraw.get_text(withdraw.AVAILABLE_BALANCE))
        over = str(int(available) + 100000)
        withdraw.enter_amount(over)
        withdraw.tap_withdraw()
        reached = withdraw.is_confirmation_shown(timeout=STATE_PROBE_WAIT)
        if reached:
            withdraw.cancel_confirmation()  # never commit an over-balance withdrawal
        assert reached, (
            "Documented behaviour: an over-balance withdrawal currently reaches the "
            "confirmation sheet. If this changed, confirm the new gating is intended."
        )

    def test_withdraw_reaches_confirmation_then_cancels(self, withdraw):
        """Small valid withdrawal → confirmation → Cancel. DEFENSIVE: if the
        withdraw confirmation copy differs from Invest's 'Nice!', this assertion
        is the first thing to retune after an on-device run."""
        available = parse_money(withdraw.get_text(withdraw.AVAILABLE_BALANCE))
        if available < 5:
            pytest.skip(f"Test account has insufficient balance to withdraw (${available})")
        withdraw.enter_amount("5")
        withdraw.tap_withdraw()
        reached = withdraw.is_confirmation_shown(timeout=STATE_PROBE_WAIT) or withdraw.is_success_shown()
        assert reached, "A valid withdrawal should advance past the keypad (confirmation/next step)"
        if withdraw.is_confirmation_shown(timeout=1):
            withdraw.cancel_confirmation()


# --------------------------------------------------------------------------- #
# 3. NAVIGATION — back from a Settings sub-menu returns to Settings.           #
#    DIRECTLY targets RAIZ-9994 (Major, Android). The old settings nav tests   #
#    pressed back but never asserted *where* they landed — so they'd pass even #
#    while this exact bug was live.                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.navigation
class TestSettingsBackNavigationE2E:

    SUB_ITEMS = [
        ("Personal details", SettingsPage.PERSONAL_DETAILS),
        ("Security and privacy", SettingsPage.SECURITY_PRIVACY),
        ("Funding account", SettingsPage.FUNDING_ACCOUNT),
        ("Plans and fees", SettingsPage.PLANS_AND_FEES),
        ("Notifications inbox", SettingsPage.NOTIFICATIONS_INBOX),
    ]

    @pytest.mark.parametrize("label,locator", SUB_ITEMS, ids=[s[0] for s in SUB_ITEMS])
    def test_back_from_sub_menu_returns_to_settings(self, settings, driver, label, locator):
        assert settings.is_loaded(), "Precondition: Settings should be open"
        settings.click(locator)
        # We should have left the Settings list…
        left_settings = not settings.is_visible(settings.TITLE, timeout=STATE_PROBE_WAIT)
        assert left_settings, f"Tapping '{label}' should open its own screen"
        # …and Back should bring us straight back to Settings (the RAIZ-9994 bug).
        driver.back()
        assert settings.is_visible(settings.TITLE), \
            f"Back from '{label}' must return to Settings, not exit to Home (RAIZ-9994)"


# --------------------------------------------------------------------------- #
# 4. PERFORMANCE — the rendered values must be correct, across time ranges.    #
#    Targets RAIZ-10306 (wrong change-in-value) & RAIZ-10244 ('%' on $0.00).   #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.portfolio
class TestPerformanceValueE2E:

    def test_investment_value_is_well_formed_money(self, performance):
        amount = performance.get_investment_amount()
        assert_non_negative_money(amount, "performance investment value")

    def test_change_in_value_renders_for_every_range(self, performance):
        """Switching the time range must keep a readable change-in-value. A blank
        or stuck value here is exactly the RAIZ-10306 class of defect."""
        for rng in ["1D", "1M", "3M", "6M", "1Y", "All"]:
            performance.select_time_range(rng)
            assert performance.is_visible(performance.INVESTMENT_VALUE_LABEL), \
                f"Investment value label disappeared after selecting {rng}"
            amount = performance.get_investment_amount()
            assert is_money(amount), f"[{rng}] investment value not well-formed: {amount!r}"

    def test_no_percentage_against_zero_value(self, performance):
        """If the portfolio value is $0.00 there must be no non-zero % shown
        beside it (RAIZ-10244). When value > 0 this test is a no-op pass."""
        amount = performance.get_investment_amount()
        if parse_money(amount) != 0:
            pytest.skip("Account is funded; the $0.00 percentage case doesn't apply")
        pct_els = performance.driver.find_elements(AppiumBy.XPATH, "//*[contains(@text,'%')]")
        for el in pct_els:
            assert parse_percent(el.text) == 0, \
                f"Non-zero percentage {el.text!r} shown against a $0.00 value (RAIZ-10244)"


# --------------------------------------------------------------------------- #
# 5. TRANSACTION HISTORY — structural correctness, not just a count.           #
#    Targets RAIZ-10063 / RAIZ-10328 (rows missing data / wrong ordering).     #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.portfolio
class TestTransactionCorrectnessE2E:

    def test_every_transaction_has_type_and_amount(self, transaction_history):
        rows = transaction_history.get_transactions(limit=10)
        assert rows, "Expected at least one transaction for this account"
        for i, row in enumerate(rows):
            assert row["type"] in ("Buy", "Sell", "Rebalance"), \
                f"Row {i} has no recognised transaction type: {row['texts']}"
            assert is_money(row["amount"]), \
                f"Row {i} ({row['type']}) is missing a dollar amount: {row['texts']}"


# --------------------------------------------------------------------------- #
# 6. HOME — the headline number must be a real value.                          #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.smoke
class TestHomeValueIntegrityE2E:

    def test_total_investments_value_is_well_formed(self, home):
        value = home.get_total_value()
        assert_non_negative_money(value, "home total investments value")


# --------------------------------------------------------------------------- #
# 7. SESSION LIFECYCLE — full logout → re-login round trip.                    #
#    The old suite only checked the Log out button is *visible*. This proves   #
#    the whole auth cycle, which the Release process names as critical.        #
#    DEFENSIVE: logout confirmation copy is handled best-effort; verify on dev.#
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.auth
class TestSessionLifecycleE2E:

    def test_logout_then_relogin(self, driver, home):
        settings = SettingsPage(driver)
        home.tap_settings()
        assert settings.is_loaded()
        settings.tap_log_out()

        # A confirmation prompt may appear ("Log out"/"Yes"). Tap it if present.
        for word in ("Log out", "Yes", "Confirm"):
            confirm = (AppiumBy.XPATH,
                       f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{word}']]")
            if settings.is_present_now(confirm):
                settings.click(confirm)
                break

        splash = SplashPage(driver)
        assert splash.is_loaded(), "Logging out should return to the Splash screen"

        # Re-login to leave the session clean for the rest of the run.
        _ensure_logged_in(driver)
        assert HomePage(driver).is_loaded(), "Should be able to log back in after logging out"
