from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage


class NavDrawer(BasePage):
    # NOTE: the old CLOSE_BUTTON pinned hard-coded pixel bounds
    # (@bounds='[924,142][1068,286]') that do not match this device (the real
    # close affordance is at [944,172][1070,298]) and are device-specific — a
    # genuine flaky-locator anti-pattern. We no longer locate the X by fixed
    # bounds; close() dismisses via the proven Back path with a geometric
    # top-right-clickable fallback (mirrors SettingsPage.close()).

    NAV_HOME = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Home']]")
    NAV_REWARDS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Rewards']]")
    NAV_SURVEYS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Surveys']]")

    NAV_MAIN_PORTFOLIO = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Main portfolio']]")
    NAV_JARS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Jars']]")
    NAV_KIDS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Kids']]")
    NAV_SUPER = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Super']]")

    NAV_ROUND_UPS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Round-Ups']]")
    NAV_RECURRING = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Recurring investments']]")
    NAV_LUMP_SUM = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Lump Sum investments']]")

    NAV_MY_FINANCE = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='My Finance']]")
    NAV_MY_ACHIEVEMENTS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='My Achievements']]")
    NAV_OFFSETTERS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Offsetters']]")

    SECTION_SAVE_EARN = (AppiumBy.XPATH, "//*[@text='SAVE & EARN']")
    SECTION_INVESTMENT_ACCOUNTS = (AppiumBy.XPATH, "//*[@text='INVESTMENT ACCOUNTS']")
    SECTION_INVESTMENT_PREFS = (AppiumBy.XPATH, "//*[@text='INVESTMENT PREFERENCES']")
    SECTION_DO_MORE = (AppiumBy.XPATH, "//*[@text='DO MORE WITH RAIZ']")

    def is_open(self) -> bool:
        return self.is_visible(self.NAV_HOME)

    def close(self):
        """Dismiss the drawer back to Home. Back reliably closes the drawer on
        this build (and is what the open/close robustness tests depend on); if a
        single Back doesn't take (slow render), fall back to tapping the
        top-right close affordance found by geometry — never hard-coded pixels."""
        if not self.is_present_now(self.NAV_HOME):
            return
        self.go_back()
        # Confirm the drawer actually closed. Allow the close animation a brief
        # settle; only escalate to the geometric X if the drawer genuinely
        # persists (a swallowed Back), so we never fire a spurious extra tap on a
        # drawer that is already on its way out.
        import time
        deadline = time.time() + 2
        while time.time() < deadline:
            if not self.is_present_now(self.NAV_HOME):
                return
            time.sleep(0.2)
        if self.is_present_now(self.NAV_HOME):
            self._tap_close_affordance()

    def _tap_close_affordance(self):
        """Tap the right-most clickable in the top ~20% of the screen (the close
        X), located by geometry so it stays correct across devices. Falls back to
        Back if nothing is found."""
        import re
        try:
            height = self.driver.get_window_size()["height"]
        except Exception:
            self.go_back()
            return
        best = None
        for el in self.driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
            if m and int(m.group(2)) < height * 0.2:
                x1 = int(m.group(1))
                if best is None or x1 > best[0]:
                    best = (x1, el)
        if best:
            try:
                best[1].click()
                return
            except Exception:
                pass
        self.go_back()

    def go_home(self):
        self.click(self.NAV_HOME)

    def go_rewards(self):
        self.click(self.NAV_REWARDS)

    def go_main_portfolio(self):
        self.click(self.NAV_MAIN_PORTFOLIO)

    def go_jars(self):
        self.click(self.NAV_JARS)

    def go_kids(self):
        self.click(self.NAV_KIDS)

    def go_super(self):
        self.scroll_to_text("Super")
        self.click(self.NAV_SUPER)

    def go_round_ups(self):
        self.scroll_to_text("Round-Ups")
        self.click(self.NAV_ROUND_UPS)

    def go_recurring(self):
        self.scroll_to_text("Recurring investments")
        self.click(self.NAV_RECURRING)

    def go_lump_sum(self):
        self.scroll_to_text("Lump Sum investments")
        self.click(self.NAV_LUMP_SUM)

    def go_my_finance(self):
        self.scroll_to_text("My Finance")
        self.click(self.NAV_MY_FINANCE)

    def go_my_achievements(self):
        self.scroll_to_text("My Achievements")
        self.click(self.NAV_MY_ACHIEVEMENTS)

    def go_offsetters(self):
        self.scroll_to_text("Offsetters")
        self.click(self.NAV_OFFSETTERS)

    def go_surveys(self):
        self.scroll_to_text("Surveys")
        self.click(self.NAV_SURVEYS)

    def has_item(self, locator, timeout=2, text: str | None = None) -> bool:
        """Scroll-safe visibility probe for a drawer item that may sit below the
        fold. Returns True once the item is on screen.

        Prefer a CONTROLLED scroll-to-text (derived from the locator's @text, or
        passed explicitly) over a blind scroll_down() that can overshoot the
        short drawer and recycle the target back out of the DOM."""
        if self.is_present_now(locator):
            return True
        target = text or self._text_from_locator(locator)
        scrolled = False
        if target:
            try:
                self.scroll_to_text(target)
                scrolled = True
            except Exception:
                scrolled = False
        if not scrolled:
            try:
                self.scroll_down()
            except Exception:
                pass
        return self.is_visible(locator, timeout=timeout)

    @staticmethod
    def _text_from_locator(locator) -> str | None:
        """Best-effort extraction of the literal @text='...' from an XPath locator
        so has_item() can scroll_to_text it. Returns None if not derivable."""
        import re
        try:
            _by, expr = locator
        except Exception:
            return None
        m = re.search(r"@text=['\"]([^'\"]+)['\"]", expr or "")
        return m.group(1) if m else None
