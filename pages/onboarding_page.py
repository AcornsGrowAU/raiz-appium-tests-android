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
            # build-3252 onboarding gate (P0-B): a "Select your Portfolio" marketing
            # SPLASH (raizFeaturePortfolio: portfolio_splash_button_select="Select your
            # Portfolio") and a sign-up plan-picker (raizFeaturePlans:
            # plans_action_bar_title_sign_up="Choose your plan", plans_button_select=
            # "Select plan") now precede the per-portfolio confirm. Match these FIRST,
            # using substrings deliberately distinct from "select as your portfolio".
            if (not acted and "select your portfolio" in src
                    and "select as your portfolio" not in src):
                acted = self._tap_text("Select your Portfolio")
            if not acted and ("choose your plan" in src or "select plan" in src):
                acted = self._tap_text("Select plan")
            if not acted and "select as your portfolio" in src:
                self._tap_text("Aggressive")
                time.sleep(1)
                acted = self._tap_text("Select as your portfolio")
            if not acted and ("initial investment" in src or "ready to start investing" in src):
                acted = self._tap_text("Skip")
            if not acted:
                # generic forward (Skip first; 'Recurring Investment' screen has a Skip;
                # NO 'Invest' — it matches the 'Raiz Invest' heading)
                acted = self._tap_text("Skip", "Continue", "Confirm", "Done", "Next",
                                       "I consent", "Agree")
            if not acted:
                # LAST-RESORT (P2-G): no known branch matched. Before giving up, if there is
                # exactly one bottom clickable Button on screen, tap it — covers a renamed
                # primary CTA. Conservative: a single Button means there's no ambiguous
                # secondary action a real branch should have handled instead.
                acted = self._tap_lone_bottom_button()
            if not acted:
                # Self-describing dead-end: record the visible heading / primary-button text
                # so the failure artifact says WHICH screen we got stuck on, not bare STUCK.
                self.path.append("STUCK: " + self._describe_screen())
                return False
            self.path.append(acted)
            time.sleep(pause)
        return home.is_present_now(home.TOTAL_VALUE_LABEL)

    def _tap_lone_bottom_button(self):
        """If exactly one clickable Button is present, tap the lowest one and return its
        label/marker; otherwise return None. Used only as a last resort in complete()."""
        try:
            btns = self.driver.find_elements(
                AppiumBy.XPATH,
                "//*[contains(@class,'Button') and @clickable='true']")
        except Exception:
            return None
        if len(btns) != 1:
            return None
        btn = btns[0]
        try:
            btn.click()
        except Exception:
            return None
        label = (btn.get_attribute("text") or btn.get_attribute("content-desc") or "").strip()
        return "lone-button:" + (label or "?")

    def _describe_screen(self):
        """Best-effort visible heading + primary-button text for a self-describing failure."""
        bits = []
        try:
            for e in self.driver.find_elements(
                    AppiumBy.XPATH,
                    "//*[@clickable='true'] | //*[contains(@class,'TextView')]"):
                t = (e.get_attribute("text") or "").strip()
                if t and t not in bits:
                    bits.append(t)
                if len(bits) >= 6:
                    break
        except Exception:
            pass
        return " | ".join(bits) if bits else "no visible text"
