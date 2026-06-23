from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage
from config.settings import STATE_PROBE_WAIT, DEFAULT_WAIT, LONG_WAIT


class LumpSumPage(BasePage):
    """Covers both the Lump Sum Investment and Withdraw screens — both share the same numpad."""

    # Verified on 2.39.1d (raiz://deposit): the screen shows a top-bar 'Invest'
    # title, a 'Lump Sum investment' section label, presets and the
    # 'Minimum of $5 Investment' notice. Accept the section label or the minimum
    # notice (deposit-specific) so loading isn't gated on a single copy string.
    LUMP_SUM_TITLE = (AppiumBy.XPATH,
        "//*[@text='Lump Sum investment' or @text='One-Time Investment' "
        "or @text='Minimum of $5 Investment']")
    WITHDRAW_TITLE = (AppiumBy.XPATH, "//*[@text='Withdraw']")

    ACCOUNT_SELECTOR = (AppiumBy.XPATH, "//android.view.View[.//android.widget.TextView[contains(@text,'year') or contains(@text,'Bonus') or contains(@text,'Portfolio')]]")
    AMOUNT_DISPLAY = (AppiumBy.XPATH, "//*[@text='$0.00']")
    AVAILABLE_BALANCE = (AppiumBy.XPATH, "//*[contains(@text,'Available:')]")
    MINIMUM_NOTICE = (AppiumBy.XPATH, "//*[@text='Minimum of $5 Investment']")

    # Preset chips wrap their label in a NON-clickable outer View plus a clickable
    # inner View. The old locators matched the outer container, so a tap could be
    # swallowed and the amount never set (leaving a stale display value). Target
    # the @clickable='true' parent so the preset actually applies.
    PRESET_10 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='$10']]")
    PRESET_25 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='$25']]")
    PRESET_50 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='$50']]")
    PRESET_100 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='$100']]")

    # Target the clickable parent cell (the inner resource-id view is non-clickable)
    KEY_0 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='0']]")
    KEY_1 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='1']]")
    KEY_2 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='2']]")
    KEY_3 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='3']]")
    KEY_4 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='4']]")
    KEY_5 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='5']]")
    KEY_6 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='6']]")
    KEY_7 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='7']]")
    KEY_8 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='8']]")
    KEY_9 = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='9']]")
    KEY_DOT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.view.View[@resource-id='keypad_dot']]")
    KEY_DELETE = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.view.View[@resource-id='keypad_image_delete']]")

    INVEST_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Invest']]")
    WITHDRAW_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Withdraw']]")

    # --- Confirmation dialog (appears after tapping Invest/Withdraw on the keypad) ---
    # Verified on-device (Samsung S23, dev build):
    #   Invest   → sheet titled "Nice!"            with actions Cancel / Invest
    #   Withdraw → sheet titled "Confirm Withdrawal" with actions Cancel / Confirm
    # This is the gate the old suite never crossed; it stopped at the keypad.
    CONFIRM_TITLE = (AppiumBy.XPATH, "//*[@text='Nice!' or @text='Confirm Withdrawal']")
    INVEST_CONFIRM_TITLE = (AppiumBy.XPATH, "//*[@text='Nice!']")
    WITHDRAW_CONFIRM_TITLE = (AppiumBy.XPATH, "//*[@text='Confirm Withdrawal']")
    CONFIRM_CANCEL_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Cancel']]")
    CONFIRM_PROCEED_INVEST = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Invest']]")
    CONFIRM_PROCEED_WITHDRAW = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Confirm']]")
    # Post-confirmation success markers (DEFENSIVE — verify exact copy on device;
    # success screens are only reached when actually committing, which we avoid
    # outside the opt-in destructive test).
    SUCCESS_MARKERS = (AppiumBy.XPATH, "//*[contains(@text,'on its way') or contains(@text,'successful') or contains(@text,'Success') or contains(@text,'received') or contains(@text,'processing') or contains(@text,'Done')]")
    # The withdrawal success screen specifically renders the copy 'Withdrawal
    # Confirmed' (verified by the on-device withdrawal e2e). This is the oracle the
    # destructive withdrawal flow asserts it reached.
    WITHDRAWAL_CONFIRMED = (AppiumBy.XPATH, "//*[contains(@text,'Withdrawal Confirmed')]")
    # The success screen's dismiss affordance ('Ok'/'OK'/'Done') sits on a clickable
    # container; tap the last match (bottom button, not a title).
    SUCCESS_DISMISS = (AppiumBy.XPATH,
        "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Ok' or @text='OK' or @text='Done']]")

    # The large amount display. Verified on 2.39.1d: the headline amount is the
    # only $-TextView that is NOT inside a clickable container — the preset chips
    # ($10/$25/$50/$100) sit inside clickable Views and the 'Minimum of $5' notice
    # is text. The previous locator excluded the preset *values* by text, which
    # silently broke when the typed/selected amount equalled a preset (e.g. typing
    # 25 left only the unrelated '$2' visible -> '$2' was read). Excluding by
    # clickable-ancestor is value-independent and robust.
    CURRENT_AMOUNT = (AppiumBy.XPATH,
        "//android.widget.TextView[starts-with(@text,'$') and not(contains(@text,'Minimum'))]"
        "[not(ancestor::*[@clickable='true'])]")

    _KEY_MAP = {str(d): (AppiumBy.XPATH, f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{d}']]") for d in range(10)}
    _KEY_MAP["."] = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.view.View[@resource-id='keypad_dot']]")

    def is_lump_sum_loaded(self) -> bool:
        return self.is_visible(self.LUMP_SUM_TITLE)

    def is_withdraw_loaded(self) -> bool:
        return self.is_visible(self.WITHDRAW_TITLE)

    def enter_amount(self, amount: str):
        """Type an amount using the keypad. Pass e.g. '10', '25.50'."""
        for char in amount:
            self.click(self._KEY_MAP[char])

    def clear_amount(self):
        for _ in range(10):
            self.click(self.KEY_DELETE)

    def tap_preset(self, amount: str):
        presets = {"$10": self.PRESET_10, "$25": self.PRESET_25, "$50": self.PRESET_50, "$100": self.PRESET_100}
        self.click(presets[amount])

    def tap_invest(self):
        self.click(self.INVEST_BUTTON)

    def tap_withdraw(self):
        self.click(self.WITHDRAW_BUTTON)

    def get_amount_display(self, timeout=STATE_PROBE_WAIT) -> str:
        """Return the amount currently shown in the large display (e.g. '$10', '$0.00').

        The headline is a Compose TextView that updates a BEAT LATE after a keypad
        tap. A bare is_present_now() snapshot can fire before the new value renders
        into the view tree and fall through to the '$0.00' AMOUNT_DISPLAY branch,
        reading a stale zero (a value-mismatch flake right after enter_amount()).
        So give CURRENT_AMOUNT a short WAITED probe; only fall back to the zero
        marker if the display genuinely hasn't moved off $0.00."""
        if self.is_visible(self.CURRENT_AMOUNT, timeout=timeout):
            return self.driver.find_element(*self.CURRENT_AMOUNT).text
        return self.get_text(self.AMOUNT_DISPLAY)

    def amount_is_zero(self, timeout=STATE_PROBE_WAIT) -> bool:
        """True once the display has settled back to $0.00. The Compose headline
        updates a beat late after clear_amount()/delete, so wait briefly rather
        than reading an instant snapshot that can fire mid-update."""
        return self.is_visible(self.AMOUNT_DISPLAY, timeout=timeout)

    def get_available_balance(self) -> str:
        """Return the 'Available: $X' text once the dollar figure has loaded.

        The row text renders as the bare label 'Available:' first and the live
        balance fills in a BEAT LATE from the backend on this heavy screen. A
        single get_text() can therefore read 'Available:' with no money yet and
        make a well-formed-money assertion fail spuriously. Poll the same element
        until its text actually carries a money token (or the wait elapses, in
        which case we return whatever is there so the caller's assertion reports
        the real rendered string)."""
        from utils.assertions import is_money
        from selenium.webdriver.support.ui import WebDriverWait
        from config.settings import POLL_INTERVAL

        def _money_text(_):
            els = self.driver.find_elements(*self.AVAILABLE_BALANCE)
            if els and is_money(els[0].text):
                return els[0].text
            return False

        try:
            return WebDriverWait(self.driver, DEFAULT_WAIT, poll_frequency=POLL_INTERVAL).until(_money_text)
        except Exception:
            return self.get_text(self.AVAILABLE_BALANCE)

    # --- Confirmation dialog handling ---
    def is_confirmation_shown(self, timeout=None) -> bool:
        """True once the 'Nice!' confirmation sheet is up after tapping Invest/Withdraw."""
        return self.is_visible(self.CONFIRM_TITLE, timeout=timeout) if timeout else self.is_visible(self.CONFIRM_TITLE)

    def cancel_confirmation(self):
        """Back out of the confirmation without moving any money. Safe for smoke runs."""
        self.click(self.CONFIRM_CANCEL_BUTTON)

    def confirm_invest(self):
        """Commit the investment. ONLY safe against the DEV environment (no real money)."""
        self.click(self.CONFIRM_PROCEED_INVEST)

    def confirm_withdraw(self):
        """Commit the withdrawal. ONLY safe against the DEV environment (no real money)."""
        self.click(self.CONFIRM_PROCEED_WITHDRAW)

    def is_success_shown(self) -> bool:
        return self.is_visible(self.SUCCESS_MARKERS)

    def is_withdrawal_confirmed(self, timeout=LONG_WAIT) -> bool:
        """True once the 'Withdrawal Confirmed' success screen is up. The withdrawal
        commits against the backend and settles a beat late on a slow emulator, so
        give it the long wait rather than an instant snapshot."""
        return self.is_present(self.WITHDRAWAL_CONFIRMED, timeout=timeout)

    def dismiss_success(self):
        """Tap the success screen's Ok/Done affordance to return to Home. Best-effort
        — safe to call even if the screen already dismissed itself."""
        try:
            els = self.driver.find_elements(*self.SUCCESS_DISMISS)
            if els:
                els[-1].click()
        except Exception:
            pass

    def get_confirmation_amount(self) -> str:
        """Read the dollar amount rendered on the open confirmation sheet.

        Used to assert the amount carried over from the keypad EXACTLY matches
        what the confirmation step shows (a consistency check the old suite never
        made). Returns the first money token on screen while the sheet is up.
        Preconditions: a confirmation sheet ('Nice!'/'Confirm Withdrawal') is
        already shown.

        Verified on 2.39.1d: the amount is rendered in the sheet BODY, not a bare
        TextView — e.g. a ScrollView whose text is 'Are you sure you want to invest
        $50?'. We therefore scan all elements (any class) carrying a $ token, not
        just TextViews, and return the first well-formed money value. parse_money
        extracts the figure from the surrounding sentence."""
        from utils.assertions import is_money
        els = self.driver.find_elements(
            AppiumBy.XPATH,
            "//*[contains(@text,'$') and not(contains(@text,'Minimum'))]")
        for el in els:
            txt = el.text
            if is_money(txt) and txt not in ("$10", "$25", "$50", "$100"):
                return txt
        return ""
