from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, STATE_PROBE_WAIT
from pages.base_page import BasePage


class SettingsPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Settings']")
    # NOTE (shared-infra request): the close affordance is found by geometry in
    # close() rather than a hard-coded pixel-bounds locator. The old
    # CLOSE_BUTTON = @bounds='[924,117][1068,261]' was device-specific (flagged in
    # TEST_SUITE_ANALYSIS.md §3 row 4) and is intentionally not used here.

    NOTIFICATIONS_INBOX = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Notifications inbox']]")
    FUNDING_ACCOUNT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Funding account']]")
    ACCOUNTS_FINANCIAL_INSIGHTS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Accounts for financial insights']]")
    PLANS_AND_FEES = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Plans and fees']]")
    PERSONAL_DETAILS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Personal details']]")
    SECURITY_PRIVACY = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Security and privacy']]")
    MANAGE_NOTIFICATIONS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage notifications']]")
    MANAGE_ROUND_UPS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage Round-Ups']]")
    REFER_A_FRIEND = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Refer a friend']]")
    RATE_RAIZ = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Rate Raiz']]")
    HOW_TO_START = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='How to start guide']]")
    GET_SUPPORT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Get support']]")
    OUR_TERMS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Our terms']]")
    STATEMENTS_REPORTS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Statements and reports']]")
    LOG_OUT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Log out']]")
    APP_VERSION = (AppiumBy.XPATH, "//*[contains(@text, 'App version:')]")
    NOTIFICATION_BADGE = (AppiumBy.XPATH, "//android.view.View[.//android.widget.TextView[@text='Notifications inbox']]//android.widget.TextView[not(@text='Notifications inbox')]")

    # Any toggle/switch on a settings sub-screen (e.g. notification preferences).
    # The Notifications screen (REDESIGN) does NOT use android.widget.Switch — its
    # toggles render as clickable Compose android.view.View nodes that still expose
    # a boolean @checked attribute. Match both the native Switch and these custom
    # checkable toggle Views so togglability checks work on the redesigned screen.
    SWITCHES = (AppiumBy.XPATH,
        "//android.widget.Switch | "
        "//android.view.View[@clickable='true' and (@checked='true' or @checked='false')]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def close(self):
        """Tap the top-right header close (X). Its pixel bounds differ per device,
        so target the right-most clickable in the top ~20% of the screen rather
        than hardcoding coordinates; fall back to Back if none is found."""
        import re
        height = self.driver.get_window_size()["height"]
        best = None
        for el in self.driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
            if m and int(m.group(2)) < height * 0.2:
                x1 = int(m.group(1))
                if best is None or x1 > best[0]:
                    best = (x1, el)
        if best:
            best[1].click()
        else:
            self.go_back()

    def get_notification_count(self) -> str:
        return self.get_text(self.NOTIFICATION_BADGE)

    def get_app_version(self) -> str:
        self.scroll_down()
        return self.get_text(self.APP_VERSION)

    # ---- navigation helpers (scroll-safe: lower items recycle off-screen) ----
    def _tap_item(self, label: str, locator):
        """Scroll the named settings row into view (it may be below the fold) then
        tap it. Settings is a Compose lazy column, so off-screen rows aren't in the
        DOM until scrolled in."""
        if not self.is_present_now(locator):
            try:
                self.scroll_to_text(label)
            except Exception:
                pass
        self.click(locator)

    def tap_log_out(self):
        self._tap_item("Log out", self.LOG_OUT)

    def tap_personal_details(self):
        self._tap_item("Personal details", self.PERSONAL_DETAILS)

    def tap_security_privacy(self):
        self._tap_item("Security and privacy", self.SECURITY_PRIVACY)

    def tap_funding_account(self):
        self._tap_item("Funding account", self.FUNDING_ACCOUNT)

    def tap_plans_and_fees(self):
        self._tap_item("Plans and fees", self.PLANS_AND_FEES)

    def tap_notifications_inbox(self):
        self._tap_item("Notifications inbox", self.NOTIFICATIONS_INBOX)

    def tap_manage_notifications(self):
        self._tap_item("Manage notifications", self.MANAGE_NOTIFICATIONS)

    def tap_accounts_financial_insights(self):
        self._tap_item("Accounts for financial insights", self.ACCOUNTS_FINANCIAL_INSIGHTS)

    def tap_manage_round_ups(self):
        self._tap_item("Manage Round-Ups", self.MANAGE_ROUND_UPS)

    def tap_refer_a_friend(self):
        self._tap_item("Refer a friend", self.REFER_A_FRIEND)

    def tap_get_support(self):
        self._tap_item("Get support", self.GET_SUPPORT)

    def tap_our_terms(self):
        self._tap_item("Our terms", self.OUR_TERMS)

    def tap_statements_reports(self):
        self._tap_item("Statements and reports", self.STATEMENTS_REPORTS)

    # ---- toggles (notification preferences etc.) ----
    def get_switches(self):
        """All Switch widgets currently on screen."""
        return self.driver.find_elements(*self.SWITCHES)

    def switch_state(self, el) -> bool:
        """True if a Switch element is currently on/checked."""
        return (el.get_attribute("checked") or "").lower() == "true"

    # ---- logout confirmation (used WITHOUT committing the logout) ----
    LOGOUT_CONFIRM_DIALOG = (AppiumBy.XPATH,
        "//*[contains(@text,'Log out') or contains(@text,'log out') or contains(@text,'Are you sure')]")

    def logout_prompt_shown(self, timeout=STATE_PROBE_WAIT) -> bool:
        """After tapping Log out, a confirmation prompt should appear before the
        session actually ends. Detect it by a clickable 'Cancel'/'No' alongside a
        confirm affordance, or 'Are you sure' copy — without committing."""
        cancel = self._first_present(("Cancel", "No", "Not now"))
        confirm = self._first_present(("Yes", "Confirm"))
        if cancel is not None and confirm is not None:
            return True
        return self.is_visible(self.LOGOUT_CONFIRM_DIALOG, timeout=timeout)

    def _first_present(self, words):
        """Return a locator for the first of `words` that is on screen right now
        as a clickable control, else None."""
        for w in words:
            loc = (AppiumBy.XPATH,
                   f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{w}']]")
            if self.is_present_now(loc):
                return loc
            loc_btn = (AppiumBy.XPATH, f"//*[@text='{w}']")
            if self.is_present_now(loc_btn):
                return loc_btn
        return None

    def cancel_logout(self) -> bool:
        """Dismiss the logout confirmation WITHOUT logging out. Returns True if a
        dismiss affordance was found and tapped. Keeps the shared session alive for
        sibling tests. Falls back to Back if no explicit Cancel/No is present."""
        loc = self._first_present(("Cancel", "No", "Not now"))
        if loc is not None:
            self.click(loc)
            return True
        self.go_back()
        return False
