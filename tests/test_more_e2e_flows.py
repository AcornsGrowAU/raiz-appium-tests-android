"""
E2E coverage for Round-Ups, Raiz Super, My Finance, and Recurring investments.

Each flow is grounded in on-device crawling and, where possible, a real defect:
  - RAIZ-9970  Round-Ups settings UI glitch
  - RAIZ-10114 Super history rebalance-cell UI
  - RAIZ-9909  Recurring "Save" button obstructed and small (Android)

Account state (verified): Round-Ups is unlinked; Super is set up but unfunded
($0) so it opens onboarding interstitials; the portfolio is funded (~$1.5k).
SAFETY: we only tap reversible actions. We never tap "Apply for insurance",
"Consolidate my super funds", or "Save" (which would create a recurring order).
"""
import os
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.round_ups_page import RoundUpsPage
from pages.super_page import SuperPage
from pages.recurring_page import RecurringPage
from pages.home_page import HomePage
from pages.my_finance_page import MyFinancePage
from utils.deep_links import DeepLinks
from utils.assertions import assert_money, assert_positive_money, parse_money, is_money
from conftest import _open_deep_link

_RUN_DESTRUCTIVE = os.getenv("RUN_DESTRUCTIVE") == "1"


def _open(driver, link, page, attempts=3):
    """Deep-link with retry — absorbs the shared-session/PIN-gate race. The
    self-healing driver handles an outright instrumentation crash."""
    from selenium.common.exceptions import WebDriverException
    from pages.pin_page import PinPage
    from config.settings import TEST_PIN, STATE_PROBE_WAIT
    for attempt in range(attempts):
        try:
            _open_deep_link(driver, link)
            if page.is_loaded():
                return page
            # A late PIN re-auth can land us on the PIN screen after the opener's
            # probe window — clear it and re-check before retrying the deep link.
            pin = PinPage(driver)
            if pin.is_loaded(timeout=STATE_PROBE_WAIT):
                pin.enter_pin(TEST_PIN)
                if page.is_loaded():
                    return page
        except WebDriverException:
            pass
        # Reset to a clean origin before retrying — a stale/loading screen left by
        # the previous test (e.g. Super's "searching for existing funds") can stop
        # the next deep link from resolving. Re-navigating from Home clears it.
        if attempt < attempts - 1:
            try:
                _open_deep_link(driver, DeepLinks.HOME)
            except WebDriverException:
                pass
    assert page.is_loaded(), f"Could not open {link}"
    return page


@pytest.fixture
def round_ups(driver):
    return _open(driver, DeepLinks.ROUND_UPS, RoundUpsPage(driver))


@pytest.fixture
def round_ups_settings(driver):
    return _open(driver, DeepLinks.ROUND_UPS_SETTINGS, RoundUpsPage(driver))


@pytest.fixture
def round_ups_accounts(driver):
    return _open(driver, DeepLinks.ROUND_UPS_ACCOUNTS, RoundUpsPage(driver))


@pytest.fixture
def raiz_super(driver):
    return _open(driver, DeepLinks.RAIZ_SUPER, SuperPage(driver))


@pytest.fixture
def super_account_info(driver):
    return _open(driver, DeepLinks.RAIZ_SUPER_ACCOUNT_INFO, SuperPage(driver))


@pytest.fixture
def super_important_docs(driver):
    return _open(driver, DeepLinks.RAIZ_SUPER_IMPORTANT_DOCS, SuperPage(driver))


@pytest.fixture
def recurring(driver):
    return _open(driver, DeepLinks.RECURRING_INVESTMENTS, RecurringPage(driver))


# --------------------------------------------------------------------------- #
# Round-Ups — the flagship spare-change feature (unlinked entry state).        #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.regression
class TestRoundUpsE2E:
    """Covers the CONFIGURED Round-Ups surfaces. The test account has a linked
    Round-Ups account (Yodlee sandbox "Dag Site (US)" — link flow documented in
    docs/). If a test here finds the account unlinked, it skips with a pointer to
    re-link rather than silently passing on the empty state."""

    def test_round_ups_screen_loads(self, round_ups):
        assert round_ups.is_loaded()

    def test_round_ups_dashboard_shows_auto_and_manual(self, round_ups):
        if not round_ups.is_linked():
            pytest.skip("No linked Round-Ups account — re-link 'Dag Site (US)' to cover this")
        assert round_ups.is_visible(round_ups.AUTO_ROUND_UPS), "Dashboard should show Auto Round-Ups"
        assert round_ups.is_visible(round_ups.MANUAL_ROUND_UPS), "Dashboard should show Manual Round-Ups"
        assert round_ups.is_visible(round_ups.ROUND_UPS_INVESTED), "Dashboard should show Round-Ups invested"
        # Every figure on the dashboard must be a well-formed dollar amount.
        for el in round_ups.driver.find_elements(*round_ups.MONEY_VALUES):
            assert is_money(el.text), f"Malformed money value on Round-Ups dashboard: {el.text!r}"

    def test_round_ups_dashboard_filter_tabs(self, round_ups):
        """The dashboard offers All / Invested / Available filters, and cycling
        them keeps us on the dashboard."""
        if not round_ups.is_linked():
            pytest.skip("No linked Round-Ups account — re-link 'Dag Site (US)' to cover this")
        for tab in (round_ups.TAB_ALL, round_ups.TAB_INVESTED, round_ups.TAB_AVAILABLE):
            assert round_ups.is_present_now(tab), f"Dashboard filter tab missing: {tab}"
        round_ups.click(round_ups.TAB_INVESTED)
        round_ups.click(round_ups.TAB_AVAILABLE)
        round_ups.click(round_ups.TAB_ALL)
        assert round_ups.is_visible(round_ups.ROUND_UPS_INVESTED), \
            "Dashboard should remain after cycling the filter tabs"

    def test_round_ups_settings_render_fully(self, round_ups_settings):
        """The settings screen must render the Auto toggle, ALL four minimum
        thresholds, the multiplier, and whole-dollar round-ups. Guards the
        RAIZ-9970 family of Round-Ups settings rendering defects."""
        s = round_ups_settings
        if not (s.is_visible(s.SETTINGS_TITLE, timeout=3) or s.is_present_now(s.MINIMUM_AMOUNT_HEADER)):
            pytest.skip("Round-Ups settings not available (account unlinked?)")
        assert s.is_visible(s.SETTINGS_AUTO), "Auto Round-Ups setting should be present"
        assert s.is_present_now(s.MINIMUM_AMOUNT_HEADER), "Minimum Round-Ups amount section should be present"
        for thr in (s.THRESHOLD_5, s.THRESHOLD_10, s.THRESHOLD_20, s.THRESHOLD_40):
            assert s.is_present_now(thr), f"Minimum-threshold option missing: {thr}"
        assert s.is_present_now(s.MULTIPLY), "Multiplier setting should be present"
        assert s.is_present_now(s.WHOLE_DOLLAR), "Whole-dollar round-ups setting should be present"

    def test_round_ups_invested_total_is_well_formed_money(self, round_ups):
        """The 'Round-Ups invested' headline must be a well-formed dollar amount
        (not blank / $NaN), and non-negative. Value-over-presence on the flagship
        figure (catches the class of defect a visibility check passes)."""
        if not round_ups.is_linked():
            pytest.skip("No linked Round-Ups account — re-link 'Dag Site (US)' to cover this")
        total = round_ups.get_invested_total()
        assert is_money(total), f"Round-Ups invested headline not well-formed money: {total!r}"
        assert parse_money(total) >= 0, f"Round-Ups invested total should be non-negative: {total!r}"

    def test_round_ups_filter_tabs_change_content(self, round_ups):
        """Cycling All / Invested / Available must actually change the rendered
        content (the set of money figures) WHEN there is Round-Ups data to filter.

        On-device crawl (REDESIGN v2.39.1d): the tabs are clickable containers and
        the tap is accepted (we stay on the dashboard); the selected state is not
        surfaced via a11y attributes (selected/checked stay false on all three).
        Crucially, this shared test account has NO Round-Ups activity — invested,
        auto and manual all read $0 and the list shows 'You don't have any spending
        yet.' With nothing in any bucket, a perfectly-working filter renders
        IDENTICAL content across the three tabs, so the only meaningful assertion
        (the tabs filter to DIFFERENT content) is unreachable.

        INFRA-GATED: Round-Up accrual is not seedable — there is no gen-API recipe
        to inject simulated card transactions that round up into invested/available
        buckets, and we never tap money-moving actions on the shared account. So
        rather than fall through to a vacuous empty-state pass (the prior bug: the
        differentiation branch never ran and the test could not fail), we skip with
        a precise reason whenever the account has no Round-Ups data to filter. When
        an account is seeded with real Round-Up accrual this test starts running
        its true assertion automatically — no edit required."""
        if not round_ups.is_linked():
            pytest.skip("No linked Round-Ups account — re-link 'Dag Site (US)' to cover this")
        # Decide data-presence from the headline total + empty-state BEFORE cycling
        # tabs — threshold-progress copy like '$5.00 until $5' is not filterable data.
        if not round_ups.has_round_ups_data():
            pytest.skip(
                "No Round-Up data to filter — needs accrual seed (round-up accrual "
                "is infra-gated: no gen-API recipe to inject rounded-up transactions, "
                "and money-moving taps are off-limits on the shared account). Without "
                "data the All/Invested/Available tabs render identical content, so "
                "the differentiation assertion is unreachable.")
        round_ups.click(round_ups.TAB_ALL)
        all_money = round_ups.get_money_texts()
        round_ups.click(round_ups.TAB_INVESTED)
        invested_money = round_ups.get_money_texts()
        round_ups.click(round_ups.TAB_AVAILABLE)
        available_money = round_ups.get_money_texts()
        # With real data, at least one pair of tabs must differ — else it's a no-op.
        assert not (all_money == invested_money == available_money), (
            "All/Invested/Available filters rendered identical content despite "
            f"non-zero Round-Ups data — filter appears to be a no-op "
            f"(All={all_money}, Invested={invested_money}, Available={available_money})")

    def test_round_ups_settings_multiplier_options_render(self, round_ups_settings):
        """The multiplier control must offer selectable factor options. Crawled
        on-device (REDESIGN v2.39.1d): the 'Multiply your Round-Ups' row is
        collapsed by default and shows only a label + description with NO inline
        chips; tapping its expander reveals factor RadioButtons rendered as
        '<n>X' (verified '2X' / '3X' / '5X', capital-X SUFFIX — NOT 'x1'..'x10').
        Deepens the RAIZ-9970 settings-rendering coverage beyond label presence."""
        import re
        s = round_ups_settings
        if not (s.is_visible(s.SETTINGS_TITLE, timeout=3) or s.is_present_now(s.MULTIPLY)):
            pytest.skip("Round-Ups settings not available (account unlinked?)")
        assert s.is_present_now(s.MULTIPLY), "Multiplier label should be present"
        assert s.open_multiplier_options(), \
            "Tapping the 'Multiply your Round-Ups' row should reveal the multiplier picker"
        options = s.get_multiplier_texts()
        assert options, "Expected selectable multiplier factor options after expanding the row"
        # Each option must be a real multiplier factor like '2X'/'3X'/'5X'.
        assert all(re.fullmatch(r"\d+X", o) for o in options), \
            f"Multiplier options should be '<n>X' factors, found: {options}"

    def test_round_ups_settings_links_to_linked_accounts(self, round_ups_settings):
        """The settings screen exposes the 'Linked accounts for Round-Ups' entry
        point — the management affordance that bridges settings to account admin."""
        s = round_ups_settings
        if not (s.is_visible(s.SETTINGS_TITLE, timeout=3) or s.is_present_now(s.MINIMUM_AMOUNT_HEADER)):
            pytest.skip("Round-Ups settings not available (account unlinked?)")
        s.scroll_down()
        assert s.is_present_now(s.LINKED_ACCOUNTS_ROW), \
            "Settings should expose a 'Linked accounts for Round-Ups' row"

    def test_round_ups_monitored_accounts_are_described(self, round_ups_accounts):
        """Each monitored subaccount row must carry a non-empty, descriptive label
        (account/card/deposit type) — guards against blank account rows."""
        a = round_ups_accounts
        if not a.is_visible(a.ACCOUNTS_TITLE, timeout=3):
            pytest.skip("Linked accounts screen not available (account unlinked?)")
        accounts = a.get_monitored_account_texts()
        assert accounts, "Expected at least one monitored subaccount"
        for label in accounts:
            assert label and label.strip(), f"Monitored account row has empty label: {label!r}"

    def test_round_ups_linked_accounts_listed(self, round_ups_accounts):
        """The linked institution and its monitored subaccounts must be listed,
        with Add-account and consent-management entry points."""
        a = round_ups_accounts
        if not a.is_visible(a.ACCOUNTS_TITLE, timeout=3):
            pytest.skip("Linked accounts screen not available (account unlinked?)")
        assert a.is_present_now(a.LINKED_INSTITUTION), "Linked institution (Dag Site) should be shown"
        assert len(a.get_monitored_account_texts()) > 0, "Expected at least one monitored subaccount"
        assert a.is_present_now(a.ADD_ACCOUNT), "Should offer 'Add an account'"
        assert a.is_present_now(a.MANAGE_CONSENT), "Should offer consent/data-sharing management"

    @pytest.mark.destructive
    @pytest.mark.skipif(not _RUN_DESTRUCTIVE,
                        reason="Links a bank account via the Yodlee sandbox; set RUN_DESTRUCTIVE=1")
    def test_link_round_ups_account_via_dag_sandbox(self, round_ups):
        """Reproducible re-link: connect the 'Dag Site (US)' sandbox institution
        so the configured-state tests above have data. Skips if already linked
        (unlink first to re-exercise the full flow). DEV/sandbox creds only."""
        from config.settings import CDR_TEST_USERNAME, CDR_TEST_PASSWORD, CDR_TEST_INSTITUTION
        if round_ups.is_linked():
            pytest.skip("Round-Ups account already linked — nothing to do")
        assert round_ups.link_dag_account(
            CDR_TEST_USERNAME, CDR_TEST_PASSWORD, CDR_TEST_INSTITUTION), \
            "Bank link flow did not reach completion"


# --------------------------------------------------------------------------- #
# Raiz Super — onboarding interstitials for an unfunded account.               #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.regression
class TestSuperE2E:
    # NOTE: Raiz Super onboarding is stateful and the test account's super is
    # unfunded, so raiz://raiz_super lands on whichever onboarding step the
    # account last reached (insurance opt-in, "Super is Ready", or the
    # consolidation/contact step). These tests assert the resilient invariants and
    # never tap actions that advance the flow ("Apply for insurance", "Not now",
    # "Consolidate", "Finish") so they don't further mutate the shared account.

    def test_super_surface_loads(self, raiz_super):
        """The Super surface loads on one of its known onboarding screens."""
        assert raiz_super.is_loaded()

    def test_insurance_opt_in_discloses_consent_when_shown(self, raiz_super):
        """If the insurance opt-in is the current step, it must carry the Death &
        TPD consent disclosure and both CTAs (a compliance requirement). If the
        account has moved past this step, skip — we don't force the flow."""
        if not raiz_super.is_insurance_interstitial():
            pytest.skip("Insurance opt-in is not the current super onboarding step")
        assert raiz_super.is_present_now(raiz_super.INSURANCE_CONSENT_TEXT), \
            "Insurance opt-in must show the Death & TPD consent disclosure"
        assert raiz_super.is_present_now(raiz_super.NOT_NOW), \
            "Insurance opt-in must offer a 'Not now' decline option"

    def test_super_account_info_screen_loads(self, super_account_info):
        """The Super account-info deep link resolves to a Super surface. On an
        unfunded account this may fall back to onboarding; the invariant is that
        the deep link does not dead-end (blank screen / wrong app area)."""
        assert super_account_info.is_account_info_loaded(), \
            "raiz://raiz_super/account_info should resolve to a Super surface"

    def test_super_account_info_shows_member_identifiers_when_present(self, super_account_info):
        """When the account-info detail renders (funded/activated account), it must
        carry at least one member identifier (USI / Member number / ABN) — these
        are regulatory fields. Skips if the unfunded account only shows onboarding."""
        s = super_account_info
        if not s.is_visible(s.ACCOUNT_INFO_TITLE, timeout=3):
            pytest.skip("Account-info detail not shown (account on onboarding step)")
        assert (s.is_present_now(s.USI_LABEL)
                or s.is_present_now(s.MEMBER_NUMBER_LABEL)
                or s.is_present_now(s.ABN_LABEL)), \
            "Account-info screen should show a member identifier (USI / Member number / ABN)"

    def test_super_important_documents_screen_loads(self, super_important_docs):
        """The important-documents deep link resolves to a Super surface (does not
        dead-end), guarding the disclosure-document entry point."""
        assert super_important_docs.is_docs_loaded(), \
            "raiz://raiz_super/important_documents should resolve to a Super surface"

    def test_super_important_documents_lists_disclosures_when_present(self, super_important_docs):
        """When the documents list renders, it must list at least one disclosure
        document (PDS / TMD / Guide / Statement) — a compliance surface. Skips if
        the unfunded account only shows onboarding instead of the docs list."""
        s = super_important_docs
        if not s.is_visible(s.DOCS_TITLE, timeout=3):
            pytest.skip("Important-documents list not shown (account on onboarding step)")
        docs = s.get_document_texts()
        assert docs, "Important-documents screen should list at least one disclosure document"


# --------------------------------------------------------------------------- #
# My Finance — net worth & totals must render as real, consistent values.      #
# (Uses the conftest `my_finance` fixture.)                                    #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.regression
class TestMyFinanceE2E:

    def test_net_worth_headline_is_well_formed(self, my_finance):
        """Smoke gate for the net-worth card: the section renders AND its
        investments component reads as a well-formed dollar amount (not a blank /
        $NaN placeholder). Downgraded from the old presence-only triple-assert —
        the full per-component value coverage lives in
        test_net_worth_breakdown_components_well_formed and
        test_net_worth_values_are_well_formed; this keeps only a cheap headline
        well-formedness smoke check rather than re-asserting mere visibility."""
        my_finance.wait_for_net_worth()
        assert my_finance.is_visible(my_finance.NET_WORTH_HEADER), \
            "My Finance should render the 'My net worth' section"
        investments = my_finance.get_investments_total_text()
        assert is_money(investments), \
            f"Net-worth investments headline not well-formed money: {investments!r}"

    def test_net_worth_values_are_well_formed(self, my_finance):
        """Every net-worth figure must be a well-formed dollar amount (catches the
        blank/`$NaN` class of defect a visibility check would pass), and the
        investments total must be positive for this funded account."""
        values = my_finance.wait_for_net_worth()
        assert values, "Expected dollar figures in the net-worth section"
        for v_text in my_finance.get_money_texts():
            assert is_money(v_text), f"Malformed money value on My Finance: {v_text!r}"
        assert max(values) > 0, "Total in investments should be positive for a funded account"

    def test_finance_investments_consistent_with_home(self, driver, my_finance):
        """The investments total on My Finance should match the Home headline
        within a small tolerance (live prices drift between reads). Catches
        cross-screen value mismatches (the RAIZ-10251 family)."""
        finance_investments = max(my_finance.wait_for_net_worth())
        _open_deep_link(driver, DeepLinks.HOME)
        home = HomePage(driver)
        home.dismiss_modal()
        home_total = parse_money(home.get_total_value())
        tolerance = max(5.0, home_total * 0.02)  # 2% absorbs intraday price drift
        assert abs(finance_investments - home_total) <= tolerance, (
            f"My Finance investments ${finance_investments} and Home total "
            f"${home_total} differ by more than ${tolerance:.2f}")

    def test_financial_insights_setup_card_present(self, my_finance):
        """The 'Set up your financial insights' onboarding card renders with its
        X-of-3 progress and at least one setup action, for an account that hasn't
        linked transactional accounts yet.

        DATA-STATE: this card only exists while insights are UNCONFIGURED. The
        shared test account has since linked accounts and populated Category
        Spending / net worth, so the onboarding card no longer shows. Skip rather
        than fail when the account is already set up (the configured surface is
        covered by the net-worth / Category Spending tests)."""
        if not my_finance.is_visible(my_finance.SETUP_INSIGHTS_HEADER, timeout=4):
            pytest.skip("Account has already completed financial-insights setup — "
                        "onboarding card not shown (net worth + Category Spending populated)")
        assert my_finance.is_visible(my_finance.SETUP_INSIGHTS_HEADER), \
            "Expected the 'Set up your financial insights' card"
        assert my_finance.is_present_now(my_finance.INSIGHTS_PROGRESS), \
            "Setup card should show 'X of 3 completed' progress"
        assert (my_finance.is_present_now(my_finance.LINK_TRANSACTIONAL_ACCOUNTS)
                or my_finance.is_present_now(my_finance.REVIEW_SPENDING_CATEGORIES)), \
            "Setup card should list its setup actions"

    def test_category_spending_section_present(self, my_finance):
        """The Category Spending section renders (with its empty-state when there
        is no recent transaction data)."""
        assert my_finance.is_visible(my_finance.CATEGORY_SPENDING), \
            "My Finance should show the Category Spending section"

    def test_net_worth_breakdown_components_well_formed(self, my_finance):
        """Both labelled net-worth components — 'Total in investments' and 'Total
        in Superannuation' — must render their own well-formed dollar figures.
        The aggregate well-formed check can pass while a single component is
        blank/misattributed; this pins each component to its label."""
        my_finance.wait_for_net_worth()
        investments = my_finance.get_investments_total_text()
        super_total = my_finance.get_super_total_text()
        assert is_money(investments), \
            f"'Total in investments' figure not well-formed money: {investments!r}"
        assert is_money(super_total), \
            f"'Total in Superannuation' figure not well-formed money: {super_total!r}"
        assert parse_money(investments) >= 0, "Investments component should be non-negative"
        assert parse_money(super_total) >= 0, "Superannuation component should be non-negative"

    def test_investments_is_largest_net_worth_component(self, my_finance):
        """Invariant for this account profile (funded portfolio, unfunded super):
        the investments component is the dominant, positive net-worth figure and
        is at least as large as the superannuation component. Catches a
        component-swap / mislabelling defect that per-figure well-formedness misses."""
        my_finance.wait_for_net_worth()
        investments = parse_money(my_finance.get_investments_total_text())
        super_total = parse_money(my_finance.get_super_total_text())
        assert investments > 0, "Investments component should be positive for a funded account"
        assert investments >= super_total, (
            f"Investments (${investments}) should be >= Superannuation (${super_total}) "
            "for this funded-portfolio / unfunded-super account")

    def test_super_component_reconciles_with_super_surface(self, driver, my_finance):
        """Cross-screen invariant (RAIZ-10251 family): the Superannuation figure on
        My Finance must agree with the Raiz Super state.

        Two branches, keyed off the actual Super surface state:

        - UNFUNDED (this account today): raiz://raiz_super lands on onboarding
          interstitials (insurance opt-in / "Super is Ready" / consolidation) and
          there is no funded dashboard balance. The My Finance super total must
          read $0. This branch runs and asserts on every run for the current
          shared account.

        - FUNDED: when a funded-super account exists, the Super surface renders a
          real dashboard balance instead of onboarding. We then reconcile that
          balance against My Finance 'Total in Superannuation' within a small
          tolerance (live-price drift). INFRA-GATED today: funded super is NOT
          seedable (no gen-API recipe to fund a member's super, and we never tap
          the irreversible consolidation/contribution actions on the shared
          account), so no funded dashboard has ever been crawled. Until a funded
          account is available this branch skips with a clear reason rather than
          fake a pass. It activates automatically the moment a funded Super
          dashboard is reachable — no edit required."""
        my_finance.wait_for_net_worth()
        super_total = parse_money(my_finance.get_super_total_text())
        super_page = _open(driver, DeepLinks.RAIZ_SUPER, SuperPage(driver))

        # Funded super renders a real dashboard balance rather than an onboarding
        # interstitial. Detect onboarding first; anything else with a positive
        # super balance on My Finance is the funded-reconciliation path.
        is_onboarding = (super_page.is_insurance_interstitial()
                         or super_page.is_ready_screen(timeout=2))

        if is_onboarding:
            # Onboarding state == unfunded == $0 on My Finance.
            assert super_total == 0, (
                f"Super is unfunded (onboarding state) but My Finance shows "
                f"${super_total} in Superannuation — cross-screen mismatch")
            return

        # Not on a recognised onboarding step. If the Super surface didn't resolve
        # at all, we can't reconcile either way.
        if not super_page.is_loaded(timeout=2):
            pytest.skip("Could not confirm Super surface state (deep link did not resolve)")

        # FUNDED branch. A funded dashboard exposes a real super balance; pair the
        # largest well-formed money figure on the Super surface (the headline
        # balance) against the My Finance super total.
        from utils.assertions import is_money as _is_money
        super_money = [parse_money(el.text)
                       for el in super_page.driver.find_elements(*MyFinancePage.MONEY_VALUES)
                       if _is_money(el.text)]
        if super_total == 0 or not any(v > 0 for v in super_money):
            pytest.skip(
                "Funded-super reconciliation needs a funded-super account — "
                "INFRA-GATED: funded super is non-seedable (no gen-API recipe to "
                "fund a member's super; money-moving Super actions are off-limits "
                "on the shared account), so no funded dashboard exists to reconcile "
                f"against (My Finance super=${super_total}, Super surface "
                f"figures={super_money}).")
        super_dashboard_balance = max(super_money)
        tolerance = max(5.0, super_dashboard_balance * 0.02)  # absorb intraday drift
        assert abs(super_total - super_dashboard_balance) <= tolerance, (
            f"My Finance 'Total in Superannuation' (${super_total}) and the funded "
            f"Super dashboard balance (${super_dashboard_balance}) differ by more "
            f"than ${tolerance:.2f} — cross-screen mismatch")

    def test_category_spending_amounts_well_formed_when_present(self, my_finance):
        """When Category Spending has data (linked transactional accounts), every
        category amount must be well-formed money. With no data the section shows
        its empty-state and the test skips — it never asserts on a placeholder."""
        if not my_finance.has_category_spending_data():
            pytest.skip("No category-spending data (empty state) — nothing to validate")
        amounts = my_finance.get_category_spending_amounts()
        assert amounts, "Category Spending reported data but exposed no amounts"
        for amt in amounts:
            assert is_money(amt), f"Malformed category-spending amount: {amt!r}"


# --------------------------------------------------------------------------- #
# Recurring investments — reach the setup form and prove Save is tappable.     #
# Directly guards RAIZ-9909 ("Save button obstructed and small").              #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.investments
class TestRecurringInvestmentsE2E:

    def test_recurring_list_loads(self, recurring):
        assert recurring.is_loaded()
        assert recurring.is_visible(recurring.MAIN_PORTFOLIO_SECTION)

    def test_open_main_portfolio_recurring_setup(self, recurring):
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen(), "Tapping the portfolio row should open the recurring setup"
        balance = recurring.get_text(recurring.CURRENT_BALANCE)
        assert is_money(balance), f"Setup screen should show a real current balance, got {balance!r}"

    def test_setup_offers_recurring_and_savings_goal(self, recurring):
        """The portfolio setup screen offers BOTH a recurring investment and a
        savings goal (both verified on-device)."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen()
        assert recurring.is_present_now(recurring.SET_RECURRING_INVESTMENT), \
            "Setup screen should offer 'Set Recurring Investment'"
        assert recurring.is_present_now(recurring.SET_SAVINGS_GOAL), \
            "Setup screen should offer 'Set Savings Goal'"

    def test_recurring_save_button_is_actionable(self, recurring):
        """Open the Set Recurring Investment form and assert the Save button is
        present AND clickable — the exact regression in RAIZ-9909. We do NOT tap
        Save (that would create a recurring order)."""
        recurring.open_main_portfolio()
        assert recurring.is_setup_screen()
        recurring.open_set_recurring_investment()
        assert recurring.is_recurring_form(), "Set Recurring Investment form should open"
        assert recurring.is_visible(recurring.FREQUENCY), "Frequency selector should be present"
        assert recurring.is_save_button_well_rendered(), \
            "Save button must render at a usable size, not obstructed/small (RAIZ-9909)"
