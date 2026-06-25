import pytest
from appium.webdriver.common.appiumby import AppiumBy
from pages.home_page import HomePage
from pages.performance_page import PerformancePage
from pages.rewards_page import RewardsPage
from pages.main_portfolio_page import MainPortfolioPage
from pages.jars_page import JarsPage
from pages.kids_page import KidsPage
from utils.assertions import assert_money, assert_non_negative_money, is_money, parse_money
from utils.deep_links import DeepLinks
from conftest import _open_deep_link


@pytest.mark.smoke
@pytest.mark.regression
class TestHomeScreen:
    def test_home_screen_loads(self, home):
        assert home.is_loaded()

    def test_greeting_is_visible(self, home):
        greeting = home.get_greeting()
        assert "Hello" in greeting

    def test_total_value_is_displayed(self, home):
        value = home.get_total_value()
        assert "$" in value

    def test_add_funds_button_visible(self, home):
        assert home.is_visible(home.ADD_FUNDS_BUTTON)

    def test_withdraw_button_visible(self, home):
        assert home.is_visible(home.WITHDRAW_BUTTON)

    def test_performance_details_row_visible(self, home):
        assert home.is_visible(home.PERFORMANCE_DETAILS_ROW)

    def test_rewards_row_visible(self, home):
        assert home.is_visible(home.REWARDS_ROW)

    def test_investment_section_header_visible(self, home):
        home.reveal("Total investments value")
        assert home.is_visible(home.TOTAL_INVESTMENTS_HEADER)

    def test_main_portfolio_card_visible(self, home):
        home.reveal("Main Portfolio")
        assert home.is_visible(home.MAIN_PORTFOLIO_CARD)

    def test_jars_card_visible(self, home):
        home.reveal("Jars")
        assert home.is_visible(home.JARS_CARD)

    def test_kids_card_visible(self, home):
        home.reveal("Kids")
        assert home.is_visible(home.KIDS_CARD)

    def test_superannuation_card_visible(self, home):
        home.reveal("Superannuation")
        assert home.is_visible(home.SUPERANNUATION_CARD)


class TestHomeNavigation:
    def test_tab_past_tappable(self, home):
        home.tap_tab_past()
        assert home.is_visible(home.TAB_PAST)

    def test_tab_today_tappable(self, home):
        home.tap_tab_past()
        home.tap_tab_today()
        assert home.is_visible(home.TAB_TODAY)

    def test_tab_future_tappable(self, home):
        home.tap_tab_future()
        assert home.is_visible(home.TAB_FUTURE)

    def test_add_funds_opens_modal(self, home, driver):
        home.tap_add_funds()
        from appium.webdriver.common.appiumby import AppiumBy
        modal_title = home.is_visible((AppiumBy.XPATH, "//*[@text='Add funds']"))
        assert modal_title
        driver.back()

    def test_performance_details_navigates(self, home, driver):
        home.tap_performance_details()
        page = PerformancePage(driver)
        assert page.is_loaded()
        driver.back()

    def test_rewards_row_navigates(self, home, driver):
        home.tap_rewards()
        page = RewardsPage(driver)
        assert page.is_loaded()
        driver.back()

    def test_main_portfolio_card_navigates(self, home, driver):
        # tap_main_portfolio() does the controlled reveal (Today tab +
        # scroll_to_top + scroll_to_text) and self-recovers a recycled card; a
        # pre-emptive blind scroll_down() only risks overshooting it off-screen.
        home.tap_main_portfolio()
        page = MainPortfolioPage(driver)
        assert page.is_loaded()
        driver.back()

    def test_jars_card_navigates(self, home, driver):
        home.tap_jars()
        page = JarsPage(driver)
        assert page.is_loaded()
        driver.back()

    def test_kids_card_navigates(self, home, driver):
        home.tap_kids()
        page = KidsPage(driver)
        assert page.is_loaded()
        driver.back()


class TestHomeScrollContent:
    def test_how_you_invest_section_visible_after_scroll(self, home):
        # 'HOW YOU INVEST' sits below the account cards on the Today tab. A blind
        # fixed-distance scroll_down() can over/undershoot; reveal() does the
        # controlled Today-tab + scroll_to_top + scroll_to_text to the target.
        home.reveal("HOW YOU INVEST")
        assert home.is_visible(home.HOW_YOU_INVEST_HEADER)

    def test_milestone_widget_visible_after_scroll(self, home):
        home.reveal("Milestone")
        assert home.is_visible(home.MILESTONE_WIDGET)


# --------------------------------------------------------------------------- #
# Value correctness — the headline total is the single most important number   #
# on the screen yet the legacy suite only checked it contained a '$'. These    #
# assert it is well-formed, signed sensibly, and stable. (Gap class: value-over #
# -presence; complements the cross-screen invariant in test_edge_cases_e2e.)    #
# --------------------------------------------------------------------------- #
@pytest.mark.regression
@pytest.mark.edge
class TestHomeTotalValueCorrectness:
    def test_total_value_is_well_formed_money(self, home):
        """RAIZ-10244-class: a '$NaN'/'$'/'$--' headline passes is_visible but is a
        real defect. Assert the headline parses as a dollar amount."""
        assert_money(home.get_total_value(), "Home total value")

    def test_total_value_is_non_negative(self, home):
        """The aggregate portfolio value across all accounts cannot be negative;
        a negative here signals a sign/aggregation bug."""
        assert_non_negative_money(home.get_total_value(), "Home total value")

    def test_total_value_stable_within_session(self, home):
        """The headline should not jump between reads with no user action (live
        price drift aside) — catches a flickering/uninitialised value binding."""
        first = parse_money(home.get_total_value())
        second = parse_money(home.get_total_value())
        tol = max(5.0, first * 0.05)
        assert abs(first - second) <= tol, (
            f"Home total changed between reads with no action: ${first} -> ${second}")


# --------------------------------------------------------------------------- #
# Greeting — personalisation + no placeholder leakage. Complements (does not    #
# duplicate) TestHomeGreetingEdgeCases: that asserts a name exists & no token   #
# leak; here we check the greeting word itself and that it has no stray brace/   #
# format-specifier characters that the lowercase token scan would miss.         #
# --------------------------------------------------------------------------- #
@pytest.mark.regression
@pytest.mark.edge
class TestHomeGreetingContent:
    def test_greeting_starts_with_hello(self, home):
        greeting = home.get_greeting()
        assert greeting.strip().startswith("Hello"), f"Unexpected greeting form: {greeting!r}"

    def test_greeting_name_is_alphabetic_not_money_or_id(self, home):
        """A personalised name should be a name, not a leaked numeric id or a
        money string (data-binding pointed at the wrong field)."""
        name = home.get_greeting_name()
        assert name, "Greeting is not personalised"
        assert not is_money(name), f"Greeting name looks like a money value: {name!r}"
        assert any(c.isalpha() for c in name), f"Greeting name has no letters: {name!r}"

    def test_greeting_has_no_format_specifier_chars(self, home):
        """Catches raw format leakage the lowercase token scan can miss, e.g.
        'Hello %1$s,' or 'Hello {0},'."""
        greeting = home.get_greeting()
        for bad in ("%1$", "%d", "%@", "{0}", "{1}", "{{", "}}"):
            assert bad not in greeting, f"Greeting leaks a format specifier ({bad!r}): {greeting!r}"


# --------------------------------------------------------------------------- #
# Account cards — each card should render well-formed money OR a sensible CTA   #
# (the test account has no active jars/kids, so those legitimately show 'Add'). #
# Gap class: presence-only card checks would pass on a '$NaN' or blank card.    #
# --------------------------------------------------------------------------- #
@pytest.mark.regression
@pytest.mark.edge
class TestHomeAccountCardValues:
    def test_main_portfolio_card_value_well_formed(self, home):
        """Main Portfolio is funded on the test account, so it must show money."""
        value = home.get_account_card_value("Main Portfolio")
        assert value is not None, "Main Portfolio card shows no dollar amount"
        assert_non_negative_money(value, "Main Portfolio card")

    def test_superannuation_card_value_well_formed(self, home):
        value = home.get_account_card_value("Superannuation")
        assert value is not None, "Superannuation card shows no dollar amount"
        assert_non_negative_money(value, "Superannuation card")

    def test_jars_card_money_or_add_cta(self, home):
        """Empty Jars card legitimately shows an 'Add' CTA; a funded one shows
        money. Anything else (blank/'$NaN') is the defect we want to catch."""
        value = home.get_account_card_value("Jars")
        texts = home.account_card_texts("Jars")
        assert (value is not None and is_money(value)) or "Add" in texts, (
            f"Jars card shows neither well-formed money nor an Add CTA: {texts!r}")

    def test_kids_card_money_or_add_cta(self, home):
        value = home.get_account_card_value("Kids")
        texts = home.account_card_texts("Kids")
        assert (value is not None and is_money(value)) or "Add" in texts, (
            f"Kids card shows neither well-formed money nor an Add CTA: {texts!r}")

    def test_funded_card_values_do_not_exceed_home_total(self, home):
        """Cross-account invariant: no single funded account card can exceed the
        Home aggregate total (within live-price drift). Catches a card bound to
        the wrong/total field."""
        total = parse_money(home.get_total_value())
        for label in ("Main Portfolio", "Superannuation"):
            value = home.get_account_card_value(label)
            if value is None:
                continue
            v = parse_money(value)
            tol = max(5.0, total * 0.02)
            assert v <= total + tol, (
                f"{label} card (${v}) exceeds Home total (${total})")


# --------------------------------------------------------------------------- #
# Entry-point navigation + back-stack (RAIZ-9994 class: back must return Home). #
# The legacy nav tests press back() but never assert where it lands; these do.  #
# --------------------------------------------------------------------------- #
@pytest.mark.regression
@pytest.mark.navigation
class TestHomeEntryPointsBackStack:
    def test_hamburger_opens_drawer_and_back_returns_home(self, home, driver):
        from pages.nav_drawer import NavDrawer
        home.tap_hamburger()
        drawer = NavDrawer(driver)
        assert drawer.is_open(), "Nav drawer did not open from the hamburger"
        driver.back()
        assert home.is_loaded(), "Back from the nav drawer did not return to Home"

    def test_settings_opens_and_back_returns_home(self, home, driver):
        from pages.settings_page import SettingsPage
        home.tap_settings()
        page = SettingsPage(driver)
        assert page.is_loaded(), "Settings did not open from the gear"
        driver.back()
        assert home.is_loaded(), "Back from Settings did not return to Home (RAIZ-9994 class)"

    def test_add_funds_modal_back_returns_home(self, home, driver):
        home.tap_add_funds()
        assert home.is_visible((AppiumBy.XPATH, "//*[@text='Add funds']")), "Add funds modal did not open"
        driver.back()
        assert home.is_loaded(), "Back from Add funds did not return to Home"

    def test_performance_details_back_returns_home(self, home, driver):
        home.tap_performance_details()
        page = PerformancePage(driver)
        assert page.is_loaded()
        driver.back()
        assert home.is_loaded(), "Back from Performance did not return to Home (RAIZ-9994 class)"

    def test_main_portfolio_card_back_returns_home(self, home, driver):
        home.tap_main_portfolio()
        page = MainPortfolioPage(driver)
        assert page.is_loaded()
        driver.back()
        assert home.is_loaded(), "Back from Main Portfolio did not return to Home (RAIZ-9994 class)"


# --------------------------------------------------------------------------- #
# Resilience — refresh, modal dismissal, deep-link re-entry. Gap class: screen  #
# integrity after gestures/navigation that have historically left a broken view.#
# --------------------------------------------------------------------------- #
@pytest.mark.regression
class TestHomeResilience:
    def test_pull_to_refresh_keeps_home_intact(self, home):
        """Pull-to-refresh should re-render, not blank, the Home headline, and the
        value must remain well-formed money afterwards."""
        before = parse_money(home.get_total_value())
        home.pull_to_refresh()
        assert home.is_loaded(), "Home headline missing after pull-to-refresh"
        after_text = home.get_total_value()
        assert_money(after_text, "Home total after refresh")
        tol = max(5.0, before * 0.05)
        assert abs(parse_money(after_text) - before) <= tol, (
            f"Home total changed materially after a plain refresh: ${before} -> {after_text}")

    def test_dismiss_modal_is_idempotent(self, home):
        """Dismissing a (possibly absent) promo/biometrics modal must never break
        the screen — calling it twice should leave Home loaded both times."""
        home.dismiss_modal()
        assert home.is_loaded()
        home.dismiss_modal()
        assert home.is_loaded()

    def test_home_loads_after_deep_link_from_another_screen(self, driver):
        """Navigate away to Performance, then deep-link back to Home and confirm
        the full screen (headline + total) rehydrates."""
        _open_deep_link(driver, DeepLinks.PERFORMANCE)
        _open_deep_link(driver, DeepLinks.HOME)
        home = HomePage(driver)
        home.dismiss_modal()
        assert home.is_loaded(), "Home did not load after deep-link re-entry"
        assert_money(home.get_total_value(), "Home total after deep-link re-entry")

    def test_today_tab_restores_account_cards(self, home):
        """After visiting the Future tab (a projection view with no cards), the
        Today tab must bring the account cards back — order-independence guard for
        the rest of the suite that relies on cards being present."""
        home.tap_tab_future()
        assert home.is_visible(home.TAB_FUTURE)
        home.tap_tab_today()
        home.reveal("Main Portfolio")
        assert home.is_visible(home.MAIN_PORTFOLIO_CARD), "Today tab did not restore the account cards"
