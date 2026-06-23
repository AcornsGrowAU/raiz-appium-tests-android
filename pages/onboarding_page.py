import time

from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage


class OnboardingPage(BasePage):
    """Drives a freshly-logged-in GENERATED user through the first-login onboarding
    gauntlet to Home.

    A generated user (unlike the shared TEST_EMAIL account) lands in onboarding on
    first login. The gates and how we clear them:
      - PDS / advisor agreement  -> pre-accepted via the seeding recipe (pds_accepted_at);
                                    handled defensively here ("I consent") in case it shows.
      - Round-up account checklist -> Skip (funding + personal details auto-complete from
                                    the `funded` trait + with_user_profile).
      - Portfolio selection       -> the assigned portfolio is pre-selected; dismiss the
                                    "Scroll Tabs" coachmark, then "Select as your portfolio".
      - Initial investment        -> Skip (the user already has a seeded balance).
    Order-agnostic: re-evaluates the current screen each step.
    """

    def _tap_text(self, *labels):
        for lab in labels:
            for e in self.driver.find_elements(
                    AppiumBy.XPATH, f"//*[@text='{lab}'] | //*[contains(@text,'{lab}')]"):
                try:
                    e.click()
                    return lab
                except Exception:
                    pass
        return None

    def _tap_id(self, rid):
        for e in self.driver.find_elements(
                AppiumBy.XPATH, f"//*[contains(@resource-id,'{rid}')]"):
            try:
                e.click()
                return True
            except Exception:
                pass
        return False

    def complete(self, max_steps=16, pause=3.5):
        """Advance to Home. Returns True if Home was reached. self.path records the
        tap sequence (useful for debugging onboarding changes)."""
        from pages.home_page import HomePage
        home = HomePage(self.driver)
        self.path = []
        for _ in range(max_steps):
            if home.is_present_now(home.TOTAL_VALUE_LABEL):
                return True
            src = self.driver.page_source.lower()
            acted = None
            # Use `if not acted` fall-through (NOT elif): a branch may match the screen
            # but its specific control may already be gone (e.g. round-up "Skip" tapped,
            # screen still shows the checklist needing a "Continue") — we must fall
            # through to the generic taps rather than dead-end.
            if "got it" in src or "scroll tabs" in src:
                acted = self._tap_text("Got it")
            if not acted and any(s in src for s in ("follow these steps", "link a round-up",
                                                    "complete your raiz invest")):
                acted = self._tap_text("Skip")
            if not acted and "select as your portfolio" in src:
                self._tap_text("Aggressive")
                time.sleep(1)
                acted = self._tap_text("Select as your portfolio")
            if not acted and self._tap_id("btnSelectYourPortfolio"):
                acted = "btnSelectYourPortfolio"
            if not acted and ("initial investment" in src or "ready to start investing" in src):
                acted = self._tap_text("Skip")
            if not acted:
                # generic forward (Skip first; 'Recurring Investment' screen has a Skip;
                # NO 'Invest' — it matches the 'Raiz Invest' heading)
                acted = self._tap_text("Skip", "Continue", "Confirm", "Done", "Next",
                                       "I consent", "Agree")
            self.path.append(acted or "STUCK")
            if not acted:
                return False
            time.sleep(pause)
        return home.is_present_now(home.TOTAL_VALUE_LABEL)
