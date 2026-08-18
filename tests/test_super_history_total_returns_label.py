"""RAIZ-10889 (release 2.41.2) — Raiz Super history "Total Returns" rename.

In Raiz Super -> History -> History Details, the summary row previously labelled
"Market Returns" is renamed to "Total Returns", and the info dialog opened by that
row's info icon has its title updated to "Total Returns". The underlying value
(gains.total.netReturnAmount) is unchanged.

Grounded in the app source (~/Android-AU):
  raizFeatureSuper/.../history/summary/SuperHistorySummary.kt   — the returns row
  raizFeatureSuper/.../history/SuperHistoryScreen.kt            — hosts the summary
  raizFeatureSuper/.../history/SuperHistoryViewModel.kt         — onMarketClick dialog
  raizFeatureSuper/.../home/SuperHomeHistory.kt                 — "History Details" entry
  raizFeatureSuper/src/main/res/values/strings.xml
      raiz_super_history_market_returns  -> "Total Returns"
      card_dialog_title_market_returns   -> "Total Returns"

Navigation: raiz://raiz_super  ->  (funded Super Home dashboard)  ->  tap
"History Details"  ->  SuperHistoryScreen, whose top summary carries the row.
There is NO dedicated super-history deep link (DeepLink registry maps only the
base `raiz_super`; the /account_info and /important_documents subpaths exist but
not /history), so the button tap is the only route.

Account state: the shared test account's Super is set up but UNFUNDED, so
raiz://raiz_super opens onboarding interstitials and the History summary is not
reachable — those runs skip with a clear reason. When Super history IS present,
the label is asserted for real: a build still showing "Market Returns" fails.
"""
import pytest
from selenium.common.exceptions import WebDriverException

from pages.super_page import SuperPage
from pages.pin_page import PinPage
from utils.deep_links import DeepLinks
from config.settings import TEST_PIN, STATE_PROBE_WAIT, DEFAULT_WAIT
from conftest import _open_deep_link

_SKIP_REASON = (
    "No funded Super with History on this account — raiz://raiz_super opens "
    "onboarding, so the History summary (and its Market/Total Returns row) is "
    "not reachable. Seed a funded super with investment history to cover this."
)


def _open_super(driver, attempts=3) -> SuperPage:
    """Deep-link to the Super surface with retry — mirrors the `_open` helper in
    tests/test_more_e2e_flows.py (absorbs the shared-session / PIN-gate race; the
    self-healing driver handles an outright instrumentation crash)."""
    page = SuperPage(driver)
    for attempt in range(attempts):
        try:
            _open_deep_link(driver, DeepLinks.RAIZ_SUPER)
            if page.is_loaded():
                return page
            pin = PinPage(driver)
            if pin.is_loaded(timeout=STATE_PROBE_WAIT):
                pin.enter_pin(TEST_PIN)
                if page.is_loaded():
                    return page
        except WebDriverException:
            pass
        if attempt < attempts - 1:
            try:
                _open_deep_link(driver, DeepLinks.HOME)
            except WebDriverException:
                pass
    assert page.is_loaded(), "Could not open raiz://raiz_super"
    return page


@pytest.fixture
def super_history(driver):
    """A SuperPage already advanced to the History summary when reachable.

    Returns the page regardless; the tests call open_history_summary() and skip
    when the funded History surface is not present, so absence is handled with a
    clear reason rather than a false pass."""
    return _open_super(driver)


@pytest.mark.e2e
@pytest.mark.regression
class TestSuperHistoryTotalReturnsLabel:
    """RAIZ-10889: the Super history returns row/dialog reads 'Total Returns'."""

    def test_returns_row_labelled_total_returns(self, super_history):
        """The summary returns row must read 'Total Returns' and NOT the retired
        'Market Returns'. Gated on a stable, unchanged sibling row so it can only
        assert when the History summary is really on screen (never vacuously);
        a build still labelling the row 'Market Returns' fails here."""
        if not super_history.open_history_summary():
            pytest.skip(_SKIP_REASON)

        # History summary IS present — assert the RAIZ-10889 rename for real.
        assert super_history.is_present(super_history.TOTAL_RETURNS_LABEL, timeout=DEFAULT_WAIT), (
            "RAIZ-10889: the Super history returns row should be labelled "
            "'Total Returns' (was 'Market Returns') in 2.41.2"
        )
        assert not super_history.is_present_now(super_history.MARKET_RETURNS_LABEL), (
            "RAIZ-10889: the retired 'Market Returns' label must no longer appear "
            "on the Super history summary"
        )

    def test_returns_info_dialog_title_is_total_returns(self, super_history):
        """If reachable, tapping the returns row opens its info dialog whose title
        reads 'Total Returns' (not 'Market Returns'). The distinctive help copy
        proves the dialog actually opened, so this is not a vacuous re-read of the
        row label behind it."""
        if not super_history.open_history_summary():
            pytest.skip(_SKIP_REASON)
        if not super_history.is_present_now(super_history.TOTAL_RETURNS_LABEL):
            pytest.skip("Returns row not on the History summary (unexpected layout) "
                        "— covered by test_returns_row_labelled_total_returns")

        if not super_history.open_returns_info_dialog():
            pytest.skip("Could not open the returns info dialog on this device/layout")

        # Dialog is open (help copy present). Its title must be the new label and
        # the old one must be gone anywhere on screen (title + row alike).
        assert super_history.is_present_now(super_history.TOTAL_RETURNS_LABEL), (
            "RAIZ-10889: the returns info dialog title should read 'Total Returns'"
        )
        assert not super_history.is_present_now(super_history.MARKET_RETURNS_LABEL), (
            "RAIZ-10889: the returns info dialog must not show the retired "
            "'Market Returns' title"
        )
