"""The REAL Raiz PLUS custom-portfolio builder, reachable only on a PLUS-plan account.

Verified live on a seeded `plan_plus` generated user (build 3252, v2.40.1d):

  raiz://portfolio/custom  -> "Welcome to PLUS" 4-screen intro carousel (Next x3 then
  "Close")  -> the builder "Your Portfolio" screen.

The builder lists each category as a clickable container (framePortfolioProContentItem)
carrying a title (tvPortfolioProItemTitle) and a weighting (tvPortfolioProItemPercentage):

    Base Portfolio (Aggressive)   100.0%     <- starts here; absorbs the remainder
    ETFs                          Add
    Stocks                        Add
    Raiz Property Fund            Add
    Bitcoin                       Add

Opening a category lands on the "Customisation" editor: a -/+ stepper (btnDec/btnInc)
around an amount field (etAmount, "0.0%"), moving 0.5% per tap, with a "Save Allocation"
CTA (btnSaveAllocation). Per-holding caps are enforced HERE: Bitcoin clamps at 5.0% and
the Raiz Property Fund at 30.0%, disabling the + control at the cap.

RAIZ-10251 reconciliation (VERIFIED on this builder, NOT present on the regular-plan
limited editor): after Saving an allocation, the builder's category-row weightings still
sum to 100% — the Base Portfolio draws DOWN by exactly what the customised holdings take
(e.g. Bitcoin 5% + Property 30% -> Base 65%). The whole-portfolio running total stays
reconciled to 100% rather than drifting. The on-screen running total IS the set of
tvPortfolioProItemPercentage rows; there is no single literal "100%" headline widget.
"""
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage

APP = "com.acornsau.android.development"


class PlusBuilderPage(BasePage):
    # --- intro carousel -------------------------------------------------------
    WELCOME = (AppiumBy.XPATH, "//*[contains(@text,'Welcome to PLUS')]")
    NEXT = (AppiumBy.XPATH,
            "//*[@clickable='true'][.//*[@text='Next']] | //*[@clickable='true' and @text='Next'] "
            "| //android.widget.Button[@text='Next']")
    CLOSE = (AppiumBy.XPATH,
             "//*[@clickable='true'][.//*[@text='Close']] | //*[@clickable='true' and @text='Close'] "
             "| //android.widget.Button[@text='Close']")

    # --- builder "Your Portfolio" screen --------------------------------------
    BUILDER_HEADER = (AppiumBy.ID, f"{APP}:id/tvPortfolioProCustomize")
    ITEM_TITLE = (AppiumBy.ID, f"{APP}:id/tvPortfolioProItemTitle")
    ITEM_PERCENT = (AppiumBy.ID, f"{APP}:id/tvPortfolioProItemPercentage")

    # --- per-category "Customisation" editor ----------------------------------
    BTN_INC = (AppiumBy.ID, f"{APP}:id/btnInc")
    BTN_DEC = (AppiumBy.ID, f"{APP}:id/btnDec")
    ET_AMOUNT = (AppiumBy.ID, f"{APP}:id/etAmount")
    # The save CTA. The visible Button[text='Save Allocation'] is NOT the touch
    # target (tapping it is swallowed); the btnSaveAllocation FrameLayout that wraps
    # it IS the working target (verified on device). Tap that node by id.
    SAVE_ALLOCATION = (AppiumBy.ID, f"{APP}:id/btnSaveAllocation")
    CUSTOMISATION_HEADER = (AppiumBy.XPATH, "//*[@text='Customisation']")

    # per-holding caps enforced by the builder (RAIZ-10251), and the stepper step
    BITCOIN_CAP = 5.0
    PROPERTY_CAP = 30.0
    STEP = 0.5

    _PCT_RE = re.compile(r"^\d{1,3}(?:\.\d+)?%$")

    # ---- intro / readiness ---------------------------------------------------
    def dismiss_intro(self, attempts: int = 12) -> bool:
        """Advance through the 'Welcome to PLUS' carousel (Next x3 then Close) onto
        the builder. Returns True once the builder header is on screen. Idempotent:
        if the builder is already showing it returns immediately."""
        for _ in range(attempts):
            if self.is_present_now(self.BUILDER_HEADER):
                return True
            if self.is_present_now(self.CLOSE):
                self._tap_first(self.CLOSE)
            elif self.is_present_now(self.NEXT):
                self._tap_first(self.NEXT)
            else:
                time.sleep(1.5)
            time.sleep(2.5)
        return self.is_present_now(self.BUILDER_HEADER)

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.BUILDER_HEADER, timeout=timeout)

    def wait_rows_loaded(self, timeout: float = 15.0) -> bool:
        """Wait until the builder's category RecyclerView has fully populated (all 5
        rows readable). The header can paint before the rows do, so callers that read
        weightings should gate on this rather than just the header."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.category_weightings()) >= self._EXPECTED_ROWS:
                return True
            time.sleep(0.5)
        return len(self.category_weightings()) >= self._EXPECTED_ROWS

    def _tap_first(self, locator):
        els = self.driver.find_elements(*locator)
        if els:
            els[-1].click()
            return True
        return False

    # ---- builder row weightings (the reconciled running total) ---------------
    # Each builder row is a container holding a title (tvPortfolioProItemTitle) and a
    # weighting (tvPortfolioProItemPercentage); reading them PER ROW (not by zipping
    # two flat lists) keeps title<->percent aligned when some rows read 'Add' (0%).
    _ROW = (AppiumBy.ID, f"{APP}:id/framePortfolioProContentItem")

    def category_weightings(self) -> dict:
        """{category_title: percent} for every builder row that currently shows a
        percentage. Rows still reading 'Add' (un-customised, 0 contribution) map to
        0.0 so the dict is complete. Read per-row and stale-safe."""
        out = {}
        for row in self.driver.find_elements(*self._ROW):
            try:
                title_els = row.find_elements(AppiumBy.ID, f"{APP}:id/tvPortfolioProItemTitle")
                pct_els = row.find_elements(AppiumBy.ID, f"{APP}:id/tvPortfolioProItemPercentage")
                if not title_els or not pct_els:
                    continue
                title = (title_els[0].get_attribute("text") or "").strip()
                pct = (pct_els[0].get_attribute("text") or "").strip()
            except (StaleElementReferenceException, WebDriverException):
                continue
            if not title:
                continue
            if self._PCT_RE.match(pct):
                out[title] = float(pct.rstrip("%"))
            else:
                out[title] = 0.0  # 'Add' (un-customised) contributes 0%
        return out

    # the full Plus builder always lists exactly these 5 category rows
    _EXPECTED_ROWS = 5

    def running_total(self):
        """The reconciled whole-portfolio total = sum of ALL builder rows (treating
        un-customised 'Add' rows as 0%). The builder RecyclerView populates (and, just
        after a save, re-populates) incrementally, so a single read can under-count;
        we poll until all 5 category rows are present AND the total reads the same
        twice in a row (stable), up to ~15s. Returns None only if the rows never fully
        render. On the real builder this stays at 100% (RAIZ-10251)."""
        last = None
        deadline = time.time() + 15
        while time.time() < deadline:
            w = self.category_weightings()
            if len(w) >= self._EXPECTED_ROWS:
                total = round(sum(w.values()), 2)
                if last is not None and abs(total - last) < 1e-6:
                    return total   # stable read across two polls with all rows present
                last = total
            time.sleep(0.6)
        # fall back to the last full-row reading if we got one, else None
        return last

    # ---- open a category editor ----------------------------------------------
    def open_category(self, label: str) -> bool:
        """Open a category's Customisation editor by tapping its CLICKABLE CONTAINER
        (not the bare label). Returns True once the editor's amount field is shown.

        Polls for the row first: the builder's category RecyclerView can populate a
        beat after the header renders, so a single immediate query can miss the row."""
        xpath = f"//*[@clickable='true'][.//android.widget.TextView[@text='{label}']]"
        rows = []
        deadline = time.time() + 10
        while time.time() < deadline:
            rows = self.driver.find_elements(AppiumBy.XPATH, xpath)
            if rows:
                break
            time.sleep(0.5)
        if not rows:
            return False
        rows[-1].click()
        return self.is_visible(self.ET_AMOUNT, timeout=10)

    # ---- editor stepper ------------------------------------------------------
    def amount(self):
        """Current holding-amount stepper value as a float percent (stale-safe)."""
        for _ in range(3):
            els = self.driver.find_elements(*self.ET_AMOUNT)
            if not els:
                return None
            try:
                return float((els[0].get_attribute("text") or "").strip().rstrip("%"))
            except (ValueError, StaleElementReferenceException, WebDriverException):
                time.sleep(0.2)
        return None

    def inc_enabled(self) -> bool:
        for _ in range(3):
            els = self.driver.find_elements(*self.BTN_INC)
            if not els:
                return False
            try:
                return els[0].get_attribute("enabled") == "true"
            except (StaleElementReferenceException, WebDriverException):
                time.sleep(0.2)
        return False

    def tap_inc(self):
        els = self.driver.find_elements(*self.BTN_INC)
        if els:
            els[-1].click()

    def dec_enabled(self) -> bool:
        for _ in range(3):
            els = self.driver.find_elements(*self.BTN_DEC)
            if not els:
                return False
            try:
                return els[0].get_attribute("enabled") == "true"
            except (StaleElementReferenceException, WebDriverException):
                time.sleep(0.2)
        return False

    def tap_dec(self):
        els = self.driver.find_elements(*self.BTN_DEC)
        if els:
            els[-1].click()

    def reset_to_zero(self, max_taps: int = 80):
        """Step the open holding DOWN to its 0.0% floor (btnDec disables at 0), so a
        step-up test has a clean, known starting point regardless of any previously
        saved weight. Returns the final amount (expected 0.0)."""
        prev = self.amount()
        for _ in range(max_taps):
            if not self.dec_enabled():
                break
            self.tap_dec()
            time.sleep(0.2)
            cur = self.amount()
            if cur is None or cur == prev:
                break
            prev = cur
        return self.amount()

    def tap_inc_expect(self, prev):
        """Tap + once and wait for the amount to advance by one STEP. On a slow
        emulator a tap can be SWALLOWED before the field re-renders; re-tap once and
        poll. Returns the advanced amount, or the last-read value if it never moved
        (so a genuine wrong-step drift still fails the caller's exact-step check)."""
        for _ in range(2):
            self.tap_inc()
            waited = 0.0
            while waited < 3.0:
                cur = self.amount()
                if cur is not None and cur >= prev + self.STEP - 1e-6:
                    return cur
                time.sleep(0.3)
                waited += 0.3
        return self.amount()

    def step_up_to_cap(self, cap: float, max_taps: int = 80):
        """Tap + until clamped/disabled. Asserts each effective tap moves by exactly
        one STEP and the value never exceeds `cap`. Returns the final amount."""
        prev = self.amount()
        for _ in range(max_taps):
            if not self.inc_enabled():
                break
            self.tap_inc()
            time.sleep(0.2)
            cur = self.amount()
            assert cur is not None, "stepper amount became unreadable mid-edit"
            assert cur <= cap + 1e-6, \
                f"holding exceeded its {cap}% cap during editing: reached {cur}%"
            if cur == prev:
                break  # clamped
            assert abs(cur - prev - self.STEP) < 1e-6, \
                f"stepper jumped {prev}% -> {cur}% (expected +{self.STEP}% per tap)"
            prev = cur
        return self.amount()

    def save_enabled(self, wait: float = 0.0) -> bool:
        """True when 'Save Allocation' is actionable. The button is DISABLED until the
        editor's value differs from the last SAVED allocation (isPortfolioChanged) —
        so re-selecting the already-saved value leaves it greyed out. The enabled
        state can lag a stepper tap by a beat, so `wait` polls up to that many seconds
        for it to flip true. Reads the inner Button's enabled state."""
        deadline = time.time() + max(0.0, wait)
        while True:
            els = self.driver.find_elements(
                AppiumBy.XPATH, "//android.widget.Button[@text='Save Allocation']")
            if not els:
                els = self.driver.find_elements(*self.SAVE_ALLOCATION)
            try:
                if els and els[0].get_attribute("enabled") == "true":
                    return True
            except (StaleElementReferenceException, WebDriverException):
                pass
            if time.time() >= deadline:
                return False
            time.sleep(0.3)

    # A transient backend hiccup on save surfaces an "Oops! Sorry, something went
    # wrong." dialog with an Ok button (not a portfolio defect — a flaky DEV API).
    OOPS = (AppiumBy.XPATH, "//*[contains(@text,'something went wrong') or @text='Oops!']")
    OOPS_OK = (AppiumBy.XPATH,
               "//*[@clickable='true'][.//*[@text='Ok' or @text='OK']] "
               "| //android.widget.Button[@text='Ok' or @text='OK']")

    def _dismiss_oops(self) -> bool:
        """If a transient 'Oops' save-error dialog is up, dismiss it. Returns True if
        one was present (so the caller knows the save did NOT commit and can retry)."""
        if self.is_present_now(self.OOPS):
            self._tap_first(self.OOPS_OK)
            time.sleep(1.5)
            return True
        return False

    def save_allocation(self) -> bool:
        """Tap 'Save Allocation' and wait to land back on the builder. The save fires
        a backend rebalance, so the return to the builder can lag several seconds; we
        re-tap if a tap is swallowed and poll patiently for the header. A transient
        'Oops' DEV-API error is dismissed and the save retried. Returns True once the
        builder header reappears (the save committed)."""
        for _ in range(4):
            if self.is_present_now(self.BUILDER_HEADER):
                return True
            if self._dismiss_oops():
                continue  # the save errored transiently; the Save button is back, retry
            tapped = self._tap_first(self.SAVE_ALLOCATION)
            if not tapped:
                time.sleep(1.5)
                continue
            # poll for the builder header (save -> backend rebalance -> builder)
            deadline = time.time() + 20
            while time.time() < deadline:
                if self.is_present_now(self.OOPS):
                    break  # transient error -> outer loop dismisses + retries
                if self.is_present_now(self.BUILDER_HEADER):
                    return True
                if not self.is_present_now(self.SAVE_ALLOCATION):
                    time.sleep(1)
                else:
                    break  # tap swallowed -> re-tap
                time.sleep(1)
        return self.is_present_now(self.BUILDER_HEADER)
