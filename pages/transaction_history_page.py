import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL, STATE_PROBE_WAIT
from pages.base_page import BasePage

# dd Mon yyyy  /  dd Mon  /  Mon dd, yyyy  — the date forms Raiz history rows use.
_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+[A-Za-z]{3,9}(?:\s+\d{4})?|[A-Za-z]{3,9}\s+\d{1,2},?\s*\d{4})\b"
)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


class TransactionHistoryPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Transaction History']")
    DOWNLOAD_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[2]")
    # The 'Filter' label is a non-clickable TextView wrapped in a clickable View;
    # the old locator matched the non-clickable outer container so taps were
    # swallowed and the filter sheet never opened. Target the clickable parent.
    FILTER_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Filter']]")
    PORTFOLIO_CHIP = (AppiumBy.XPATH, "//*[@text='Portfolio']")
    PENDING_HEADER = (AppiumBy.XPATH, "//*[@text='Pending']")

    # Filter sheet (opens after tapping Filter). Verified on 2.39.1d: the sheet
    # presents 'Select an account', 'Select a transaction type', 'Select a date
    # range', 'Common Filters' and an 'Apply' button. Transaction-type options
    # (Buy/Sell/...) live behind the 'Select a transaction type' picker, not on
    # the top sheet.
    FILTER_SHEET_TITLE = (AppiumBy.XPATH,
        "//*[@text='Select a transaction type' or @text='Select an account' "
        "or @text='Select a date range' or @text='Common Filters']")
    FILTER_TXN_TYPE_PICKER = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Select a transaction type']]")
    # Verified on 2.39.1d/3223 (emulator-5556): the transaction-type picker offers
    # Lump Sum, Recurring Investment, Round-Ups, Transfers, Withdrawal, Dividend,
    # Rebalance, Fee, Rewards, Promo, Referrals — there is NO 'Buy' option. The LIST
    # rows are labelled Buy/Sell/Rebalance, so 'Buy' rows are produced by the
    # 'Lump Sum' filter (lump-sum investments render as Buy rows). The old FILTER_BUY
    # (@text='Buy') never matched anything in the picker, so the test permanently
    # skipped. FILTER_TYPE_NAME drives the locators below.
    FILTER_TYPE_NAME = "Lump Sum"
    # Row label(s) that the chosen filter type maps to in the transaction list.
    FILTER_TYPE_ROW_LABELS = ("Buy",)
    # A filter type this kind of account has none of — used to prove the filter
    # actually discriminates (yields a strictly smaller/empty result).
    FILTER_ABSENT_TYPE_NAME = "Withdrawal"

    FILTER_TYPE_OPTION = (AppiumBy.XPATH,
        f"//*[@clickable='true'][.//android.widget.TextView[@text='{FILTER_TYPE_NAME}']]")
    FILTER_ABSENT_TYPE_OPTION = (AppiumBy.XPATH,
        f"//*[@clickable='true'][.//android.widget.TextView[@text='{FILTER_ABSENT_TYPE_NAME}']]")
    FILTER_APPLY = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Apply' or @text='Done' or @text='Show results']]")
    # 'Cancel'/'Close' dismissal control on the filter sheet — used to prove the
    # list survives an opened-then-cancelled filter (RAIZ-10063: list not refreshed
    # after cancel). Some builds expose an explicit Cancel/Close label; others only
    # the chevron/back affordance, so the cancel helper falls back to system-back.
    FILTER_CANCEL = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Cancel' or @text='Close']]")
    # Empty-state shown when a filter matches no transactions (verified on this build).
    EMPTY_STATE = (AppiumBy.XPATH,
        "//android.widget.TextView[contains(@text, 'no investments') or contains(@text, 'No transactions') or contains(@text, 'no transactions')]")

    TRANSACTION_ROWS = (AppiumBy.XPATH,
        "//android.view.View[.//android.widget.TextView[@text='Buy' or @text='Sell' or @text='Rebalance']]"
    )

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def wait_for_rows(self, timeout=LONG_WAIT) -> bool:
        """Wait until the transaction list has actually RENDERED its rows (or has
        settled into its empty state), not just until the screen title appears.

        The 'Transaction History' title paints as soon as the screen mounts, but
        the rows arrive asynchronously over the network (1-3s RTT on the emulator).
        Asserting on get_transactions()/find_deposit_rows_matching() right after
        is_loaded() therefore races the fetch and intermittently sees an EMPTY
        list — the exact symptom behind the '$X found none (visible rows: [])'
        failures. Poll until at least one row is present (success) OR the empty
        state shows (a genuinely empty ledger). Returns True once rows exist."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.driver.find_elements(*self.TRANSACTION_ROWS):
                return True
            if self.is_present_now(self.EMPTY_STATE):
                return False
            time.sleep(POLL_INTERVAL)
        return bool(self.driver.find_elements(*self.TRANSACTION_ROWS))

    def get_transaction_count(self) -> int:
        return len(self.driver.find_elements(*self.TRANSACTION_ROWS))

    def tap_filter(self):
        self.click(self.FILTER_BUTTON)

    def tap_download(self):
        self.click(self.DOWNLOAD_BUTTON)

    def get_first_transaction_type(self) -> str:
        rows = self.driver.find_elements(*self.TRANSACTION_ROWS)
        if rows:
            type_el = rows[0].find_element(
                AppiumBy.XPATH, ".//android.widget.TextView[@text='Buy' or @text='Sell' or @text='Rebalance']"
            )
            return type_el.text
        return ""

    def get_transactions(self, limit: int = 10) -> list[dict]:
        """Return structured rows: [{type, amount, texts}]. Enables correctness
        assertions (every row has a type AND a dollar amount) rather than a bare
        count. Targets the class of history defects where rows render without
        their amount or fail to refresh (e.g. RAIZ-10063, RAIZ-10328)."""
        rows = self.driver.find_elements(*self.TRANSACTION_ROWS)[:limit]
        out = []
        for row in rows:
            texts = [t.text for t in row.find_elements(
                AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]")]
            tx_type = next((t for t in texts if t in ("Buy", "Sell", "Rebalance")), "")
            amount = next((t for t in texts if t.strip().startswith("$") or t.strip().startswith("-$")), "")
            date = next((d for d in (_parse_date_key(t) for t in texts) if d), None)
            date_text = next((t for t in texts if _DATE_RE.search(t)), "")
            out.append({"type": tx_type, "amount": amount,
                        "date": date, "date_text": date_text, "texts": texts})
        return out

    def get_transaction_dates(self, limit: int = 10) -> list[tuple]:
        """Parsed (year, month, day) sort keys for the first `limit` rows that
        expose a recognisable date. Used to assert newest-first ordering
        (RAIZ-10328). Rows without a parseable date are skipped."""
        return [r["date"] for r in self.get_transactions(limit=limit) if r["date"]]

    def open_filter(self) -> bool:
        """Tap Filter and report whether a filter surface actually opened."""
        self.tap_filter()
        return self.is_visible(self.FILTER_SHEET_TITLE, timeout=STATE_PROBE_WAIT)

    def open_transaction_type_picker(self) -> bool:
        """From the open filter sheet, drill into the 'Select a transaction type'
        picker where the type options (Lump Sum, Withdrawal, ...) live. Returns
        True if the configured FILTER_TYPE_NAME option becomes reachable."""
        if not self.is_present_now(self.FILTER_TXN_TYPE_PICKER):
            return False
        self.click(self.FILTER_TXN_TYPE_PICKER)
        return self.is_visible(self.FILTER_TYPE_OPTION, timeout=STATE_PROBE_WAIT)

    def apply_transaction_type_filter(self, type_option) -> bool:
        """From the list view: open the filter, drill into the transaction-type
        picker, select the given option locator, tap Apply, and wait to land back
        on the history list. Returns True if the full flow completed.

        `type_option` is one of the FILTER_*_OPTION locators on this page."""
        if not self.open_filter():
            return False
        if not self.is_present_now(type_option):
            if not self.open_transaction_type_picker():
                return False
        if not self.is_present_now(type_option):
            return False
        self.click(type_option)
        if self.is_present_now(self.FILTER_APPLY):
            self.click(self.FILTER_APPLY)
        else:
            self.go_back()  # some sheets apply on toggle + dismiss
        return self.is_loaded(timeout=STATE_PROBE_WAIT)

    def shows_empty_state(self) -> bool:
        """True if the list is showing its 'no transactions' empty state."""
        return self.is_present_now(self.EMPTY_STATE)

    def find_deposit_rows_matching(self, target_amount: float, tol: float = 0.005) -> list[dict]:
        """Return the parsed deposit/investment rows whose dollar amount equals
        `target_amount` (within `tol`). A deposit/lump-sum credit renders as a
        'Buy' row, so we accept Buy-typed rows. This is the VALUE oracle: it
        asserts a row with the exact seeded amount exists, not mere presence of
        any row. Scrolls the list so a target that sits below the fold is found."""
        deposit_types = ("Buy",)
        seen_keys = set()
        matches = []

        # The list rows arrive async after the screen mounts; give them a beat to
        # render before scanning so we don't scroll/scan an empty (not-yet-loaded)
        # list and wrongly conclude the seeded row is absent.
        self.wait_for_rows()

        def _collect():
            for r in self.get_transactions(limit=60):
                amt = parse_money(r.get("amount", ""))
                if amt is None:
                    continue
                key = (r.get("type"), r.get("amount"), r.get("date_text"))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if r.get("type") in deposit_types and abs(amt - target_amount) <= tol:
                    matches.append(r)

        _collect()
        # Scroll a few pages in case the seeded credit is below the initial fold.
        for _ in range(6):
            if matches:
                break
            before = len(seen_keys)
            self.scroll_down()
            _collect()
            if len(seen_keys) == before:
                break  # reached the end of the list; nothing new rendered
        self.scroll_to_top()
        return matches

    def cancel_filter(self) -> bool:
        """Open the filter sheet, then DISMISS it without applying (Cancel/Close,
        falling back to system-back). Returns True once back on the history list.

        Targets the RAIZ-10063 class of defect: the list must still be rendered
        (not blanked / not stuck on the sheet) after a cancelled filter."""
        if not self.open_filter():
            return False
        if self.is_present_now(self.FILTER_CANCEL):
            self.click(self.FILTER_CANCEL)
        else:
            self.go_back()
        if not self.is_loaded(timeout=DEFAULT_WAIT):
            return False
        # The list re-renders after the sheet dismisses; wait for the rows to come
        # back before the caller reads the post-cancel row count, otherwise the
        # count-preserved assertion races the re-render.
        self.wait_for_rows()
        return True


def parse_money(text: str):
    """Parse a Raiz money string ('$137.42', '-$5.00', '$1,234.56') to a float.
    Returns the absolute dollar value (sign-agnostic — deposit vs debit is read
    from the row TYPE, not the sign). None if no dollar amount is present."""
    if not text:
        return None
    m = re.search(r"-?\$\s*([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_date_key(text: str):
    """('17 May 2026' / '17 May' / 'May 17, 2026') -> (year, month, day) sort key.
    Year defaults to 0 when the row omits it (still orders within a year). None if
    no date is present."""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    token = m.group(1).lower().replace(",", "")
    parts = token.split()
    day = month = year = None
    for p in parts:
        if p.isdigit():
            if len(p) == 4:
                year = int(p)
            else:
                day = int(p)
        elif p[:3] in _MONTHS:
            month = _MONTHS[p[:3]]
    if month is None or day is None:
        return None
    return (year or 0, month, day)
