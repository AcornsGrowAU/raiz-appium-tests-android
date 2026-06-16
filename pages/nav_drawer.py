from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage


class NavDrawer(BasePage):
    CLOSE_BUTTON = (AppiumBy.XPATH, "//android.view.View[@bounds='[924,142][1068,286]']")

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

    def has_item(self, locator, timeout=2) -> bool:
        """Scroll-safe visibility probe for a drawer item that may sit below the
        fold. Returns True once the item is on screen, scrolling the drawer first."""
        if self.is_present_now(locator):
            return True
        try:
            self.scroll_down()
        except Exception:
            pass
        return self.is_visible(locator, timeout=timeout)
