from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class RoundUpsPage(BasePage):
    """Round-Ups — Raiz's flagship spare-change feature.

    The test account now has a linked Round-Ups account (Yodlee sandbox
    "Dag Site (US)"), so this object covers the *configured* surfaces:
      - Dashboard (raiz://round_ups): Auto/Manual Round-Ups + invested totals
      - Settings (raiz://round_ups/settings): Auto toggle, minimum threshold
        ($5/$10/$20/$40), multiplier, whole-dollar round-ups  ← RAIZ-9970 area
      - Linked accounts (raiz://accounts/round_ups): institution + monitored
        subaccounts, Add an account, Manage consent
    Unlinked-state locators are kept so the page still works before linking.
    """
    TITLE = (AppiumBy.XPATH, "//*[@text='Round-Ups']")

    # --- Unlinked state ---
    EXPLAINER = (AppiumBy.XPATH, "//*[contains(@text,'spare change')]")
    LINK_ACCOUNT_BUTTON = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Link a Round-Ups account']]")

    # --- Linked dashboard ---
    ROUND_UPS_INVESTED = (AppiumBy.XPATH, "//*[@text='Round-Ups invested']")
    AUTO_ROUND_UPS = (AppiumBy.XPATH, "//*[@text='Auto Round-Ups']")
    MANUAL_ROUND_UPS = (AppiumBy.XPATH, "//*[@text='Manual Round-Ups']")
    TAB_ALL = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='All']]")
    TAB_INVESTED = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Invested']]")
    TAB_AVAILABLE = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Available']]")
    MONEY_VALUES = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$')]")

    # --- Settings (raiz://round_ups/settings) ---
    SETTINGS_TITLE = (AppiumBy.XPATH, "//*[@text='Round-Up settings']")
    SETTINGS_AUTO = (AppiumBy.XPATH, "//*[@text='Auto Round-Ups']")
    MINIMUM_AMOUNT_HEADER = (AppiumBy.XPATH, "//*[@text='Minimum Round-Ups amount']")
    THRESHOLD_5 = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='$5']] | //android.widget.TextView[@text='$5']")
    THRESHOLD_10 = (AppiumBy.XPATH, "//android.widget.TextView[@text='$10']")
    THRESHOLD_20 = (AppiumBy.XPATH, "//android.widget.TextView[@text='$20']")
    THRESHOLD_40 = (AppiumBy.XPATH, "//android.widget.TextView[@text='$40']")
    MULTIPLY = (AppiumBy.XPATH, "//*[contains(@text,'Multiply your Round-Ups')]")
    WHOLE_DOLLAR = (AppiumBy.XPATH, "//*[contains(@text,'whole dollar transactions')]")
    LINKED_ACCOUNTS_ROW = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Linked accounts for Round-Ups']]")
    # Verified on-device: expanding the multiplier row reveals factor options
    # rendered as RadioButtons with text like '2X' / '3X' / '5X' (capital X
    # SUFFIX) — NOT 'x1'..'x10'. Match a digit immediately followed by X.
    MULTIPLIER_OPTIONS = (AppiumBy.XPATH,
        "//*[(@class='android.widget.RadioButton' or self::android.widget.RadioButton "
        "or self::android.widget.TextView)][string-length(@text)<=3 and substring(@text, string-length(@text))='X']")

    # --- Linked accounts (raiz://accounts/round_ups) ---
    ACCOUNTS_TITLE = (AppiumBy.XPATH, "//*[@text='Linked accounts for Round-Ups']")
    ADD_ACCOUNT = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Add an account']]")
    MANAGE_CONSENT = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Manage consent and data sharing']]")
    LINKED_INSTITUTION = (AppiumBy.XPATH, "//*[contains(@text,'Dag Site')]")
    MONITORED_ACCOUNT = (AppiumBy.XPATH,
        "//android.widget.TextView[contains(@text,'(') and (contains(@text,'Account') or contains(@text,'Card') "
        "or contains(@text,'Deposit') or contains(@text,'Saving'))]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return (self.is_visible(self.TITLE, timeout=timeout)
                or self.is_visible(self.ROUND_UPS_INVESTED, timeout=2)
                or self.is_visible(self.LINK_ACCOUNT_BUTTON, timeout=2)
                or self.is_visible(self.SETTINGS_TITLE, timeout=2)
                or self.is_visible(self.ACCOUNTS_TITLE, timeout=2))

    # The dashboard list shows this empty-state line when there is no spending yet.
    NO_SPENDING = (AppiumBy.XPATH, "//*[contains(@text,\"don't have any spending\")]")

    # state probes
    def is_linked(self) -> bool:
        return self.is_present_now(self.ROUND_UPS_INVESTED) or self.is_present_now(self.AUTO_ROUND_UPS)

    def has_round_ups_data(self) -> bool:
        """True only if the account has real, filterable Round-Ups activity: a
        positive 'Round-Ups invested' headline AND no 'don't have any spending'
        empty-state. Threshold-progress copy like '$5.00 until $5' is NOT data, so
        we key off the headline total, not any '$' on screen."""
        from utils.assertions import is_money, parse_money
        if self.is_present_now(self.NO_SPENDING):
            return False
        total = self.get_invested_total()
        return is_money(total) and parse_money(total) > 0

    def is_unlinked_state(self) -> bool:
        return self.is_present_now(self.LINK_ACCOUNT_BUTTON)

    def is_explainer_shown(self) -> bool:
        return self.is_present_now(self.EXPLAINER)

    # dashboard values
    def get_money_texts(self) -> list[str]:
        """Every well-formed dollar figure currently on the dashboard."""
        from utils.assertions import is_money
        return [el.text for el in self.driver.find_elements(*self.MONEY_VALUES) if is_money(el.text)]

    def get_invested_total(self) -> str:
        """The 'Round-Ups invested' headline figure. The amount renders as the
        sibling/nearby TextView of the 'Round-Ups invested' label; we take the
        first well-formed money value on the dashboard as the headline total."""
        from utils.assertions import is_money
        # Prefer a value adjacent to the 'Round-Ups invested' label within its card.
        card = self.driver.find_elements(
            AppiumBy.XPATH,
            "//*[.//android.widget.TextView[@text='Round-Ups invested']]"
            "//android.widget.TextView[contains(@text,'$')]")
        for el in card:
            if is_money(el.text):
                return el.text
        texts = self.get_money_texts()
        return texts[0] if texts else ""

    # accounts
    def get_monitored_account_texts(self) -> list[str]:
        return [el.text for el in self.driver.find_elements(*self.MONITORED_ACCOUNT)]

    def get_multiplier_texts(self) -> list[str]:
        return [el.text for el in self.driver.find_elements(*self.MULTIPLIER_OPTIONS)]

    def open_multiplier_options(self) -> bool:
        """Expand the multiplier picker. On the Round-Up settings screen the
        'Multiply your Round-Ups' row is collapsed by default and shows only its
        label + description; tapping the expander control on the right of that row
        reveals the factor options (verified: '2X' / '3X' / '5X' RadioButtons).

        Returns True once at least one multiplier option is rendered. Finds the
        expander geometrically — the clickable element sharing the row's vertical
        band but offset to the right of the label — which is robust to the
        flattened Compose tree (no reliable sibling/parent wrapper)."""
        import re
        if self.driver.find_elements(*self.MULTIPLIER_OPTIONS):
            return True
        labels = self.driver.find_elements(*self.MULTIPLY)
        if not labels:
            return False
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", labels[0].get_attribute("bounds") or "")
        if not m:
            return False
        label_y = (int(m.group(2)) + int(m.group(4))) / 2
        label_left = int(m.group(1))
        best = None  # (x_left, element) — rightmost clickable on the row
        for el in self.driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
            mb = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
            if not mb:
                continue
            y = (int(mb.group(2)) + int(mb.group(4))) / 2
            x_left = int(mb.group(1))
            # Same visual row as the label, and to the right of the label text.
            if abs(y - label_y) <= 90 and x_left >= label_left:
                if best is None or x_left > best[0]:
                    best = (x_left, el)
        if best is None:
            return False
        try:
            best[1].click()
        except Exception:
            return False
        return bool(self.driver.find_elements(*self.MULTIPLIER_OPTIONS))

    # --- Linking a bank account (Yodlee sandbox) ---
    # Reusable, robust encoding of the verified link flow so the test account can
    # be re-linked if its Round-Ups account ever drops. Steps confirmed on-device:
    #   Link CTA → Add an account → Next → See more (lazy; scroll to it) →
    #   search institution → select → username/password → Sign In → "Completed".
    def _tap_text(self, text, timeout=8, contains=False):
        import time
        xp = (f"//*[@clickable='true'][.//android.widget.TextView[contains(@text,'{text}')]]"
              if contains else
              f"//*[@clickable='true'][.//android.widget.TextView[@text='{text}']]")
        end = time.time() + timeout
        while time.time() < end:
            els = self.driver.find_elements(AppiumBy.XPATH, xp) or \
                  self.driver.find_elements(AppiumBy.XPATH, f"//android.widget.TextView[@text='{text}']")
            if els:
                try:
                    els[0].click(); return True
                except Exception:
                    pass
            time.sleep(0.3)
        return False

    def _wait_edittexts(self, count=1, timeout=10):
        import time
        end = time.time() + timeout
        while time.time() < end:
            e = self.driver.find_elements(AppiumBy.XPATH, "//android.widget.EditText")
            if len(e) >= count:
                return e
            time.sleep(0.3)
        return self.driver.find_elements(AppiumBy.XPATH, "//android.widget.EditText")

    def link_dag_account(self, username: str, password: str, institution: str = "Dag Site (US)", timeout=90) -> bool:
        """Drive the full bank-link flow with the Yodlee sandbox institution.
        Returns True once the connection reports completion. DEV/sandbox only."""
        import time
        self._tap_text("Link a Round-Ups account", timeout=4)
        self._tap_text("Add an account", timeout=6)
        self._tap_text("Next", timeout=6)
        # "See more" lazy-renders at the list bottom — scroll to reveal it.
        for _ in range(4):
            if self._tap_text("See more", timeout=2):
                break
            self.scroll_down()
        search = self._wait_edittexts(1, 8)
        assert search, "Institution search field not found after 'See more'"
        search[0].click(); search[0].send_keys("Dag")
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass
        assert self._tap_text(institution, timeout=8), f"Institution '{institution}' not found"
        creds = self._wait_edittexts(2, 8)
        assert len(creds) >= 2, "Bank login fields not found"
        creds[0].click(); creds[0].send_keys(username)
        creds[1].click(); creds[1].send_keys(password)
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass
        assert self._tap_text("Sign In", timeout=8, contains=True), "Sign In not tapped"
        # Wait for the connection progress to reach completion.
        end = time.time() + timeout
        while time.time() < end:
            if self.is_present_now((AppiumBy.XPATH, "//*[@text='Completed']")) or self.is_linked():
                return True
            if self.is_present_now((AppiumBy.XPATH, "//*[contains(@text,'unable to connect')]")):
                return False
            time.sleep(1)
        return False
