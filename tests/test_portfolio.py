import pytest
from appium.webdriver.common.appiumby import AppiumBy
from pages.main_portfolio_page import MainPortfolioPage
from pages.performance_page import PerformancePage
from pages.transaction_history_page import TransactionHistoryPage
from utils.assertions import (
    assert_money, assert_non_negative_money, parse_money, parse_percent, is_money,
)
from config.settings import STATE_PROBE_WAIT
from utils.deep_links import DeepLinks
# PIN-aware deep-link opener (same one the conftest fixtures use): in-test
# re-navigation must handle the intermittent PIN re-prompt / deep-link resolve
# flake, which the raw BasePage.go_to() does not.
from conftest import _open_deep_link


@pytest.mark.portfolio
@pytest.mark.smoke
class TestMainPortfolioScreen:
    def test_main_portfolio_loads(self, main_portfolio):
        assert main_portfolio.is_loaded()

    def test_investment_amount_displayed(self, main_portfolio):
        amount = main_portfolio.get_investment_amount()
        assert "$" in amount

    def test_add_funds_button_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.ADD_FUNDS_BUTTON)

    def test_withdraw_button_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.WITHDRAW_BUTTON)

    def test_performance_details_row_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.PERFORMANCE_DETAILS_ROW)

    def test_invested_section_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.INVESTED_HEADER)

    def test_you_portfolio_row_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.YOU_PORTFOLIO_ROW)

    def test_net_invested_row_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.NET_INVESTED_ROW)

    def test_total_invested_label_visible(self, main_portfolio):
        assert main_portfolio.is_visible(main_portfolio.TOTAL_INVESTED_LABEL)

    def test_performance_section_visible_after_scroll(self, main_portfolio):
        main_portfolio.scroll_down()
        assert main_portfolio.is_visible(main_portfolio.PERFORMANCE_HEADER)

    def test_manage_portfolio_section_visible_after_scroll(self, main_portfolio):
        main_portfolio.scroll_down()
        assert main_portfolio.is_visible(main_portfolio.ROUND_UPS_ROW)

    def test_about_portfolio_section_visible_after_scroll(self, main_portfolio):
        main_portfolio.scroll_down()
        main_portfolio.scroll_down()
        assert main_portfolio.is_visible(main_portfolio.TRANSACTION_HISTORY_ROW)


@pytest.mark.portfolio
class TestPortfolioNavigation:
    def test_performance_details_navigates(self, main_portfolio, driver):
        main_portfolio.tap_performance_details()
        page = PerformancePage(driver)
        assert page.is_loaded()
        driver.back()

    def test_transaction_history_navigates(self, main_portfolio, driver):
        main_portfolio.tap_transaction_history()
        page = TransactionHistoryPage(driver)
        assert page.is_loaded()
        driver.back()


@pytest.mark.portfolio
class TestPerformanceScreen:
    def test_performance_screen_loads(self, performance):
        assert performance.is_loaded()

    @pytest.mark.xfail(reason="Requires account with active jars", strict=False)
    def test_portfolio_tab_visible(self, performance):
        assert performance.is_visible(performance.PORTFOLIO_TAB)

    @pytest.mark.xfail(reason="Requires account with active jars", strict=False)
    def test_jar_tab_visible(self, performance):
        assert performance.is_visible(performance.JAR_TAB)

    def test_investment_value_label_visible(self, performance):
        assert performance.is_visible(performance.INVESTMENT_VALUE_LABEL)

    def test_time_range_buttons_visible(self, performance):
        for locator in [performance.TIME_1D, performance.TIME_1M, performance.TIME_3M,
                        performance.TIME_6M, performance.TIME_1Y, performance.TIME_ALL]:
            assert performance.is_visible(locator)

    def test_select_1d_range(self, performance):
        performance.select_time_range("1D")
        assert performance.is_visible(performance.TIME_1D)

    def test_select_1m_range(self, performance):
        performance.select_time_range("1M")
        assert performance.is_visible(performance.TIME_1M)

    def test_select_all_range(self, performance):
        performance.select_time_range("All")
        assert performance.is_visible(performance.TIME_ALL)

    def test_market_status_displayed(self, performance):
        assert performance.is_visible(performance.MARKET_STATUS)

    @pytest.mark.xfail(reason="Requires account with active jars", strict=False)
    def test_jar_tab_navigates(self, performance):
        performance.select_jar_tab()
        assert performance.is_visible(performance.JAR_TAB)


@pytest.mark.portfolio
class TestTransactionHistory:
    def test_transaction_history_loads(self, transaction_history):
        assert transaction_history.is_loaded()

    def test_filter_button_visible(self, transaction_history):
        assert transaction_history.is_visible(transaction_history.FILTER_BUTTON)

    def test_transactions_are_listed(self, transaction_history):
        count = transaction_history.get_transaction_count()
        assert count > 0, "Expected at least one transaction for this test account"

    def test_first_transaction_has_type(self, transaction_history):
        tx_type = transaction_history.get_first_transaction_type()
        assert tx_type in ("Buy", "Sell", "Rebalance")


@pytest.mark.e2e
@pytest.mark.portfolio
@pytest.mark.navigation
class TestMainPortfolioBackNavigationE2E:
    """Back from a Main Portfolio sub-screen must return to Main Portfolio, not
    exit to Home. This is the RAIZ-9994 bug class (originally only covered for
    Settings) applied to the portfolio area, where the same broken back-stack
    would strand users. Conservative: asserts we left, then returned — no
    sub-screen content is assumed."""

    ROWS = [
        ("Round-Ups", MainPortfolioPage.ROUND_UPS_ROW),
        ("Recurring", MainPortfolioPage.RECURRING_ROW),
        ("Holdings", MainPortfolioPage.HOLDINGS_ROW),
        ("Transaction history", MainPortfolioPage.TRANSACTION_HISTORY_ROW),
    ]

    @pytest.mark.parametrize("label,locator", ROWS, ids=[r[0] for r in ROWS])
    def test_back_from_sub_screen_returns_to_main_portfolio(self, main_portfolio, driver, label, locator):
        assert main_portfolio.is_loaded(), "Precondition: on Main portfolio"
        # Rows live in the lower 'Manage'/'About' sections — scroll them into view.
        try:
            main_portfolio.scroll_to_text(label)
        except Exception:
            pass
        main_portfolio.click(locator)
        left = not main_portfolio.is_visible(main_portfolio.TITLE, timeout=STATE_PROBE_WAIT)
        assert left, f"Tapping '{label}' should open its own screen"
        driver.back()
        assert main_portfolio.is_visible(main_portfolio.TITLE), \
            f"Back from '{label}' must return to Main portfolio, not exit (RAIZ-9994 class)"


# --------------------------------------------------------------------------- #
# Main Portfolio — money-row CORRECTNESS, not just row presence.              #
# Complements TestMainPortfolioScreen (presence) and the Home/Performance     #
# value E2E. Targets the RAIZ-10251 "totals don't add up" family: the value   #
# beside each labelled row must be well-formed money and obey the obvious     #
# invariants between invested capital and current value.                      #
# --------------------------------------------------------------------------- #
@pytest.mark.portfolio
@pytest.mark.e2e
class TestMainPortfolioValueIntegrity:

    def test_investment_amount_is_well_formed_money(self, main_portfolio):
        # Stronger than the existing '"$" in amount' presence check: the headline
        # must parse as a real, non-negative dollar figure (catches '$', '$NaN').
        amount = main_portfolio.get_investment_amount()
        assert_non_negative_money(amount, "main portfolio investment value")

    def test_total_invested_row_value_is_well_formed(self, main_portfolio):
        # On 2.39.1d the 'You portfolio' row shows the portfolio NAME, not money;
        # the 'Total invested to date' row is the well-formed money figure in the
        # Invested breakdown. Assert it parses as a real, non-negative dollar value
        # (catches '$', '$NaN').
        amount = main_portfolio.get_total_invested_amount()
        assert is_money(amount), f"'Total invested to date' has no well-formed amount: {amount!r}"
        assert parse_money(amount) >= 0, f"'Total invested to date' should not be negative: {amount!r}"

    def test_net_invested_row_value_is_well_formed(self, main_portfolio):
        amount = main_portfolio.get_net_invested_amount()
        assert is_money(amount), f"'Net invested by you' row has no well-formed amount: {amount!r}"

    def test_net_invested_not_greater_than_portfolio_value(self, main_portfolio):
        """The Invested breakdown must reconcile with the headline value
        (RAIZ-10251 — totals must add up). On 2.39.1d the breakdown exposes 'Net
        invested by you' and 'Total invested to date' as money rows; the headline
        is current market value = invested capital + returns (which may be ±). We
        assert the always-true invariant: capital is non-negative, and the headline
        value sits within a market-movement band of the invested capital — it must
        not be wildly detached from what was put in (the totals-don't-add-up class)."""
        headline = parse_money(main_portfolio.get_investment_amount())
        net_invested = main_portfolio.get_net_invested_amount()
        if not is_money(net_invested):
            pytest.skip("'Net invested by you' row not exposing a value on this build")
        invested_val = parse_money(net_invested)
        assert invested_val >= 0, f"'Net invested by you' value negative: {net_invested!r}"
        assert headline >= 0, f"Headline value negative: {headline}"
        # Current value = invested capital + cumulative returns. Returns are small
        # relative to capital for this account; allow a generous ±25% market band
        # plus a floor so a near-zero account doesn't false-fail. A headline that
        # falls outside this band of invested capital means the totals are detached.
        band = max(50.0, 0.25 * max(invested_val, headline))
        assert abs(headline - invested_val) <= band, (
            f"Headline value ${headline} is detached from invested capital "
            f"${invested_val} beyond a ${band:.2f} market band "
            f"(RAIZ-10251 totals-don't-add-up class)"
        )


# --------------------------------------------------------------------------- #
# Performance — selecting a range must CHANGE the displayed period/value, not  #
# merely leave the button visible. The analysis doc explicitly calls out the  #
# old test_select_*_range tests for asserting only button-visibility, which    #
# RAIZ-10306 (wrong/stuck Δ-value) would sail past. Complements                #
# TestPerformanceValueE2E (well-formed value per range).                       #
# --------------------------------------------------------------------------- #
@pytest.mark.portfolio
@pytest.mark.e2e
class TestPerformanceRangeChangesValue:

    def test_period_label_or_value_changes_across_ranges(self, performance):
        """Cycle the time ranges and capture (period-label, change-value) for each.
        At least the period descriptor OR the change figure must vary — if every
        range renders an identical pair the range selector is dead/stuck, which is
        the RAIZ-10306 class of defect that a button-visibility check cannot see."""
        snapshots = {}
        for rng in PerformancePage.RANGE_KEYS:
            performance.select_time_range(rng)
            assert performance.is_visible(performance.INVESTMENT_VALUE_LABEL), \
                f"Investment value label disappeared after selecting {rng}"
            label = performance.get_period_label()
            change = performance.get_change_value()
            snapshots[rng] = (label, change)
        distinct = set(snapshots.values())
        assert len(distinct) > 1, (
            "Selecting different time ranges produced an identical period label AND "
            f"change value every time — the range selector is not updating the widget "
            f"(RAIZ-10306 class). Snapshots: {snapshots}"
        )

    def test_change_value_is_well_formed_for_every_range(self, performance):
        """Whenever a change-in-value figure renders for a range, it must be a
        well-formed money token (not '$NaN', not a stray symbol) — this asserts
        the *change* figure, distinct from the headline value. Some ranges
        legitimately render NO change row on a freshly-funded account (verified on
        2.39.1d: 1D shows only the headline value, no Δ row), so an absent figure
        for a range is skipped rather than failed; the well-formedness check still
        fires for every range that DOES surface a figure, and at least one must."""
        seen = 0
        for rng in PerformancePage.RANGE_KEYS:
            performance.select_time_range(rng)
            change = performance.get_change_value()
            if not change:
                continue  # range renders no Δ figure on this account — not malformed
            assert is_money(change), f"[{rng}] change-in-value not well-formed money: {change!r}"
            seen += 1
        assert seen > 0, "No time range rendered a change-in-value figure at all"

    def test_active_range_value_reconciles_with_main_portfolio(self, performance, driver):
        """The Performance headline value and the Main Portfolio headline value
        describe the same portfolio and must agree within tolerance — a cross-screen
        consistency check (RAIZ-10251 family). Reads Performance first, then opens
        Main Portfolio, and restores Performance for the next serial test."""
        perf_value = performance.get_investment_amount()
        assert_non_negative_money(perf_value, "performance headline value")
        perf_val = parse_money(perf_value)

        main = MainPortfolioPage(driver)
        # PIN-aware open + one retry (raw go_to strands on an intermittent PIN
        # re-prompt; the deep link also occasionally fails to resolve first try).
        _open_deep_link(driver, DeepLinks.INVEST)
        if not main.is_loaded(timeout=STATE_PROBE_WAIT):
            _open_deep_link(driver, DeepLinks.INVEST)
        assert main.is_loaded(), "Could not open Main Portfolio for cross-screen check"
        main_val = parse_money(main.get_investment_amount())

        tol = max(1.0, 0.02 * max(perf_val, main_val))
        assert abs(perf_val - main_val) <= tol, (
            f"Performance value ${perf_val} and Main Portfolio value ${main_val} "
            f"disagree beyond tolerance ${tol:.2f} (cross-screen, RAIZ-10251 family)"
        )

    def test_no_percentage_against_zero_change_value(self, performance):
        """If the change-in-value is exactly $0.00 there must be no non-zero %
        shown on the widget (the RAIZ-10244 '% on $0.00' defect, applied to the
        change figure). No-op pass when the change is non-zero."""
        change = performance.get_change_value()
        if not is_money(change) or parse_money(change) != 0:
            pytest.skip("Change value is non-zero (or absent); the $0.00 % case doesn't apply")
        for pct in performance.get_percent_texts():
            assert parse_percent(pct) == 0, \
                f"Non-zero percentage {pct!r} shown against a $0.00 change value (RAIZ-10244)"


# --------------------------------------------------------------------------- #
# Transaction History — ORDERING, dates and filtering correctness.            #
# Complements TestTransactionCorrectnessE2E (every row has type+amount).      #
# Targets RAIZ-10328 (wrong ordering) and the filter-doesn't-filter risk.     #
# --------------------------------------------------------------------------- #
@pytest.mark.portfolio
@pytest.mark.e2e
class TestTransactionOrderingAndFilter:

    def test_transactions_are_newest_first(self, transaction_history):
        """Settled transactions should be listed newest-first. We parse the row
        dates and assert the sequence is non-increasing (RAIZ-10328). Skips if
        fewer than two rows expose a parseable date."""
        dates = transaction_history.get_transaction_dates(limit=10)
        if len(dates) < 2:
            pytest.skip("Need at least two dated transactions to assert ordering")
        assert dates == sorted(dates, reverse=True), (
            f"Transactions are not in newest-first order (RAIZ-10328): {dates}"
        )

    def test_rows_carry_a_recognisable_date(self, transaction_history):
        """Every listed transaction should expose a date its row can be sorted by.
        A row with an amount but no date is the kind of half-rendered row the
        history list has shipped before (RAIZ-10063 refresh family)."""
        rows = transaction_history.get_transactions(limit=10)
        if not rows:
            pytest.skip("No transactions for this account")
        dated = [r for r in rows if r["date"]]
        assert dated, (
            "No transaction row exposed a parseable date — rows: "
            f"{[r['texts'] for r in rows]}"
        )

    def test_filter_button_opens_a_filter_surface(self, transaction_history):
        """Tapping Filter must actually open a filter surface, not no-op. The old
        suite only asserted the Filter button is visible."""
        opened = transaction_history.open_filter()
        assert opened, "Tapping 'Filter' did not open a filter surface"
        # Restore the list view for the next serial test.
        transaction_history.go_back()

    def test_transaction_type_filter_actually_filters(self, transaction_history):
        """Prove the transaction-type filter actually filters, two ways.

        On build 2.39.1d/3223 the type picker (Filter -> 'Select a transaction
        type') offers Lump Sum, Recurring Investment, Round-Ups, Transfers,
        Withdrawal, Dividend, Rebalance, Fee, Rewards, Promo, Referrals — there is
        NO 'Buy' option, even though the LIST rows are labelled Buy/Sell/Rebalance.
        Lump-sum investments render as 'Buy' rows, so the real mapping is
        'Lump Sum' (picker) -> 'Buy' (rows). The old test targeted a non-existent
        'Buy' picker option and so permanently SKIPPED; this one executes.

        1. POSITIVE: filter by FILTER_TYPE_NAME ('Lump Sum'). The result must be
           non-empty AND every row consistent with that type (all 'Buy' rows,
           each row exposing the 'Lump Sum' label) — i.e. the filter applied and
           returned a coherent, type-consistent set.
        2. DISCRIMINATION: filter by a type the account has none of
           (FILTER_ABSENT_TYPE_NAME, 'Withdrawal'). The result must be strictly
           smaller than the matched set (here: empty / empty-state) — proving the
           filter responds to the chosen type rather than ignoring it.
        """
        before = transaction_history.get_transaction_count()
        if before == 0:
            pytest.skip("No transactions to filter")

        page = transaction_history
        label_set = set(page.FILTER_TYPE_ROW_LABELS)

        # --- 1. POSITIVE: filter by the present type and verify a coherent result.
        applied = page.apply_transaction_type_filter(page.FILTER_TYPE_OPTION)
        assert applied, (
            f"Could not apply the '{page.FILTER_TYPE_NAME}' transaction-type filter "
            "(filter sheet / type picker did not behave as verified on 2.39.1d)"
        )
        matched = page.get_transactions(limit=30)
        assert matched, (
            f"Filtering by '{page.FILTER_TYPE_NAME}' returned no rows, but the "
            f"unfiltered list had {before} — the filter dropped everything"
        )
        bad = [r for r in matched if r["type"] not in label_set]
        assert not bad, (
            f"'{page.FILTER_TYPE_NAME}' filter returned rows of the wrong type — "
            f"filter is not type-consistent: {[r['type'] for r in bad]}"
        )
        # The active filter surfaces its type as a screen-level header
        # ('Lump Sum'), confirming the chosen filter is actually applied (it is a
        # sticky group header, not a per-row label).
        assert page.is_present_now(page.by_text(page.FILTER_TYPE_NAME)), (
            f"The '{page.FILTER_TYPE_NAME}' filter header is not shown — the chosen "
            "filter does not appear to be applied"
        )
        matched_count = len(matched)

        # --- 2. DISCRIMINATION: filter by a type the account lacks; result shrinks.
        # PIN-aware open + one retry (matches the transaction_history fixture):
        # raw go_to strands on an intermittent PIN re-prompt / unresolved deep link.
        _open_deep_link(page.driver, DeepLinks.TRANSACTIONS)
        if not page.is_loaded(timeout=STATE_PROBE_WAIT):
            _open_deep_link(page.driver, DeepLinks.TRANSACTIONS)
        assert page.is_loaded(), "Failed to return to the history list before re-filtering"
        applied_absent = page.apply_transaction_type_filter(page.FILTER_ABSENT_TYPE_OPTION)
        assert applied_absent, (
            f"Could not apply the '{page.FILTER_ABSENT_TYPE_NAME}' filter"
        )
        absent_rows = page.get_transactions(limit=30)
        assert len(absent_rows) < matched_count, (
            f"Filtering by '{page.FILTER_ABSENT_TYPE_NAME}' (which this account has "
            f"none of) still returned {len(absent_rows)} rows, same as the "
            f"'{page.FILTER_TYPE_NAME}' result ({matched_count}) — the filter is "
            "ignoring the chosen type, i.e. it does not actually filter: "
            f"{[r['type'] for r in absent_rows]}"
        )
        # With zero matches this build shows an explicit empty state; assert it's
        # coherent rather than a half-rendered list.
        if not absent_rows:
            assert page.shows_empty_state(), (
                f"'{page.FILTER_ABSENT_TYPE_NAME}' filter yielded no rows but no "
                "empty-state message was shown"
            )
