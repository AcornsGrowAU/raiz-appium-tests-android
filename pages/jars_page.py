from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage
from utils.assertions import is_money


class JarsPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Raiz Jars']")
    CREATE_JAR_TITLE = (AppiumBy.XPATH, "//*[@text='Create Jar']")
    # Real text is "Customise your Jar! Let's start by choosing an icon." — match
    # on the prefix (the old exact-match never matched the create screen).
    CUSTOMISE_JAR_TITLE = (AppiumBy.XPATH, "//*[contains(@text,'Customise your Jar')]")
    ACTIVE_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Active']]")
    CLOSED_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Closed']]")
    # NOTE: index-based; only valid on the Jars *list* screen. On the create
    # screen it points at the wrong control (observed to trigger an "Oops!" error).
    ADD_JAR_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[2]")
    HELP_BUTTON = (AppiumBy.XPATH, "(//android.widget.Button)[3]")
    MANAGE_JAR_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage Jar']]")

    # --- Create Jar flow (verified: raiz://jars with no active jars lands here) ---
    ICON_PROMPT = (AppiumBy.XPATH, "//*[contains(@text,'choosing an icon')]")
    NAME_FIELD = (AppiumBy.XPATH, "//android.widget.EditText")
    CREATE_JAR_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Create Jar']]")
    SET_RECURRING_ROW = (AppiumBy.XPATH, "//*[@text='Set recurring investments']")
    # Selectable icon tiles on the customise screen (best-effort — verify on device).
    ICON_TILES = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][not(.//android.widget.TextView)]")
    OOPS_TITLE = (AppiumBy.XPATH, "//*[@text='Oops!']")
    OOPS_OK = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Ok']]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        alt_timeout = min(timeout, 2)
        return (self.is_visible(self.TITLE, timeout=timeout)
                or self.is_visible(self.CREATE_JAR_TITLE, timeout=alt_timeout)
                or self.is_visible(self.CUSTOMISE_JAR_TITLE, timeout=alt_timeout))

    def is_create_screen(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.CUSTOMISE_JAR_TITLE, timeout=timeout) or (
            self.is_present_now(self.NAME_FIELD) and self.is_present_now(self.CREATE_JAR_BUTTON))

    def is_list_screen(self, timeout=2) -> bool:
        """True on the Jars *list* screen (account has >=1 jar): the titled screen
        with Active/Closed tabs and a Manage Jar control, NOT the create screen.

        Distinguishes the populated state from the empty state, which deep-links
        straight to 'Customise your Jar'. Used to drive data-adaptive tests that
        assert real content only when a jar exists."""
        if self.is_create_screen(timeout=timeout):
            return False
        return (self.is_visible(self.TITLE, timeout=timeout)
                and (self.is_present_now(self.ACTIVE_TAB)
                     or self.is_present_now(self.MANAGE_JAR_BUTTON)))

    def has_active_jar(self) -> bool:
        """True when the list screen renders at least one jar (a Manage Jar control
        is the per-jar affordance)."""
        return self.is_list_screen() and self.is_present_now(self.MANAGE_JAR_BUTTON)

    def get_jar_balances(self) -> list[str]:
        """Every well-formed money string currently rendered on the Jars list
        screen (each active jar shows its balance). Used to assert balances are
        well-formed money, not just present."""
        texts = [t.text for t in self.driver.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[contains(@text, '$')]")]
        return [t for t in texts if is_money(t)]

    def select_first_icon(self):
        """Pick an icon if the screen requires one before Create Jar is enabled.
        Best-effort: taps the first icon tile if any are present."""
        tiles = self.driver.find_elements(*self.ICON_TILES)
        if tiles:
            tiles[0].click()

    def enter_jar_name(self, name: str):
        self.type_text(self.NAME_FIELD, name)
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass

    def tap_create_jar(self):
        self.click(self.CREATE_JAR_BUTTON)

    def create_jar(self, name: str, pick_icon: bool = True):
        """Full create from the customise screen. DEV-only / opt-in — commits a jar."""
        if pick_icon:
            self.select_first_icon()
        self.enter_jar_name(name)
        self.tap_create_jar()

    def is_oops_shown(self) -> bool:
        return self.is_present_now(self.OOPS_TITLE)

    def dismiss_oops(self):
        if self.is_oops_shown():
            self.click(self.OOPS_OK)

    def tap_active_tab(self):
        self.click(self.ACTIVE_TAB)

    def tap_closed_tab(self):
        self.click(self.CLOSED_TAB)

    def tap_manage_jar(self):
        self.click(self.MANAGE_JAR_BUTTON)

    def get_jar_by_name(self, name: str):
        return self.find((AppiumBy.XPATH, f"//android.widget.TextView[@text='{name}']"))
