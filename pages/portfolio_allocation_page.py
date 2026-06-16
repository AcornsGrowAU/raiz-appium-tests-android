import re
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class PortfolioAllocationPage(BasePage):
    """The portfolio breakdown reached via raiz://portfolio — a list of ETF/asset
    rows each with a target weighting (e.g. 'iShares Asia 50 ETF | IAA | - | 3%').

    Exists to assert the weightings actually add up to 100%, the exact failure in
    RAIZ-10251 ('totals don't add up on the custom portfolio screen'). A presence
    check can't see that; you have to read the numbers and sum them.
    """
    PORTFOLIO_TABS = (AppiumBy.XPATH,
        "//android.widget.TextView[@text='Standard' or @text='Plus' or @text='Conservative' "
        "or @text='Moderate' or @text='Moderately Conservative' or @text='Aggressive' "
        "or @text='Moderately Aggressive' or @text='Emerald']")
    # A coachmark ("Scroll Tabs … Got it") can overlay the list on first visit.
    GOT_IT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Got it']]")
    # Allocation rows: clickable cells whose subtree contains a standalone percentage.
    ALLOCATION_ROWS = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[substring(@text, string-length(@text)) = '%']]")
    _PCT_RE = re.compile(r"^\d+(?:\.\d+)?%$")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.PORTFOLIO_TABS, timeout=timeout)

    def dismiss_coachmark(self):
        if self.is_present_now(self.GOT_IT):
            self.click(self.GOT_IT)

    def _collect_visible_allocations(self, acc: dict):
        """Add every currently-rendered allocation row to acc keyed by row label
        (so scrolling doesn't double-count rows that re-appear).

        Compose lazily recomposes rows during/after a scroll, so an element handle
        can go stale between query and read. We skip any row that goes stale and
        pick it up on the next pass rather than aborting the whole collection."""
        for row in self.driver.find_elements(*self.ALLOCATION_ROWS):
            try:
                texts = [t.text.strip() for t in row.find_elements(
                    AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]")]
            except (StaleElementReferenceException, WebDriverException):
                continue
            pct = next((t for t in texts if self._PCT_RE.match(t)), None)
            if pct is None:
                continue
            label = " | ".join(t for t in texts if not self._PCT_RE.match(t)) or pct
            acc[label] = float(pct.rstrip("%"))

    def get_allocations(self) -> dict:
        """Scroll the list end-to-end and return {row_label: percent}. Bounded
        scroll so a rendering bug can't loop forever."""
        self.dismiss_coachmark()
        acc: dict = {}
        last_count = -1
        for _ in range(8):
            self._collect_visible_allocations(acc)
            if len(acc) == last_count:
                break  # nothing new appeared — we've seen the whole list
            last_count = len(acc)
            self.scroll_down()
        return acc

    def total_allocation(self) -> float:
        return round(sum(self.get_allocations().values()), 2)
