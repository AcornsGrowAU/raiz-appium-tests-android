from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage
from utils.assertions import is_money


class KidsPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Raiz Kids']")
    ACTIVE_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Active']]")
    CLOSED_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Closed']]")
    ADD_KID_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[2]")
    HELP_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[3]")
    MANAGE_ACCOUNT_BUTTONS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage account']]")

    # --- Create Kid flow (verified entry points) ---
    # raiz://raiz_kids with no active kids opens an identity-consent gate, then a
    # multi-step "Welcome to Raiz Kids!" onboarding.
    CONSENT_PROMPT = (AppiumBy.XPATH, "//*[contains(@text,'I consent')]")
    I_CONSENT_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[contains(@text,'I consent') or @text='Continue']]")
    WELCOME_TITLE = (AppiumBy.XPATH, "//*[@text='Welcome to Raiz Kids!']")
    NEXT_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Next']]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        # With no active kids, the Kids surface opens on a consent/welcome
        # onboarding screen rather than the titled list — accept any entry surface.
        return (self.is_visible(self.TITLE, timeout=timeout)
                or self.is_consent_screen(timeout=2)
                or self.is_welcome_screen(timeout=2))

    def is_consent_screen(self, timeout=2) -> bool:
        return self.is_visible(self.CONSENT_PROMPT, timeout=timeout)

    def is_welcome_screen(self, timeout=2) -> bool:
        return self.is_visible(self.WELCOME_TITLE, timeout=timeout)

    def is_entry_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        """True on any of the Kids entry surfaces: list title, consent gate, or
        the create-onboarding welcome."""
        return (self.is_visible(self.TITLE, timeout=timeout)
                or self.is_consent_screen(timeout=2)
                or self.is_welcome_screen(timeout=2))

    def is_list_screen(self, timeout=2) -> bool:
        """True on the populated Kids *list* screen (account has >=1 kid): the
        titled 'Raiz Kids' screen with Active/Closed tabs and Manage account
        controls — NOT the consent/welcome onboarding the empty state opens on.

        Drives data-adaptive tests so real-content assertions only run when kid
        accounts actually exist."""
        if self.is_consent_screen(timeout=timeout) or self.is_welcome_screen(timeout=timeout):
            return False
        return (self.is_visible(self.TITLE, timeout=timeout)
                and (self.is_present_now(self.ACTIVE_TAB)
                     or self.is_present_now(self.MANAGE_ACCOUNT_BUTTONS)))

    def has_active_kid(self) -> bool:
        """True when the list screen renders at least one kid account (a Manage
        account control is the per-kid affordance)."""
        return self.is_list_screen() and self.is_present_now(self.MANAGE_ACCOUNT_BUTTONS)

    def get_kid_balances(self) -> list[str]:
        """Every well-formed money string currently rendered on the Kids list
        screen (each kid account shows its balance)."""
        texts = [t.text for t in self.driver.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[contains(@text, '$')]")]
        return [t for t in texts if is_money(t)]

    def tap_active_tab(self):
        self.click(self.ACTIVE_TAB)

    def tap_closed_tab(self):
        self.click(self.CLOSED_TAB)

    def tap_manage_account(self, index: int = 0):
        buttons = self.driver.find_elements(*self.MANAGE_ACCOUNT_BUTTONS)
        buttons[index].click()

    def get_kid_names(self) -> list[str]:
        # Kid names appear as e.g. "Test (<1yr)" — find all such TextViews
        elements = self.driver.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[contains(@text, 'yr')]"
        )
        return [el.text for el in elements]
