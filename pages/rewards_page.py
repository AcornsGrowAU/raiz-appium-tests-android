from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class RewardsPage(BasePage):
    EARN_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Earn']]")
    TRACK_TAB = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Track']]")

    HEADER_ROOT = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnHeader_Root']")
    HEADER_VALUE = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnHeader_Value']")
    # The search field is an EditText whose hint 'Search by store name' is a child
    # TextView. Once focused/typed, that hint TextView disappears, so a locator
    # gated on the hint stops matching after typing. SEARCH_INPUT (hint-gated) is
    # used only to locate the empty field; SEARCH_FIELD matches the EditText
    # regardless of its current text for typing/verification.
    SEARCH_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[.//android.widget.TextView[@text='Search by store name']]")
    SEARCH_FIELD = (AppiumBy.XPATH, "//android.widget.EditText")

    FEATURED_LIST = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnFeaturedList_Root']")
    FEATURED_ITEMS = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnFeaturedItem_Root']")
    BOOSTED_LIST = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnBoostedList_Root']")
    BOOSTED_ITEMS = (AppiumBy.XPATH, "//*[@resource-id='RewardsEarnBoostedItem_Root']")
    FEATURED_HEADER = (AppiumBy.XPATH, "//*[@text='Featured rewards']")

    # Any reward card across the Earn lists (featured + boosted). Used for
    # value/navigation assertions that don't care which list a card belongs to.
    ANY_REWARD_ITEM = (AppiumBy.XPATH,
        "//*[@resource-id='RewardsEarnFeaturedItem_Root' or @resource-id='RewardsEarnBoostedItem_Root']")
    # Cashback / reward $ amounts rendered inside the Earn lists.
    REWARD_AMOUNTS = (AppiumBy.XPATH, "//android.widget.TextView[contains(@text,'$')]")

    PENDING_REWARDS_LABEL = (AppiumBy.XPATH, "//*[@text='Pending rewards']")
    REWARDS_INVESTED_LABEL = (AppiumBy.XPATH, "//*[@text='Rewards invested']")
    FILTER_ALL = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='All']]")
    FILTER_PENDING = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Pending']]")
    FILTER_INVESTED = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Invested']]")
    EMPTY_STATE = (AppiumBy.XPATH, "//*[@text='There are no rewards at the moment']")
    # Track-tab empty/loaded content (rewards the user is tracking). The "no
    # rewards" copy is the empty case; the labels below are the loaded case.
    TRACK_EMPTY_STATE = (AppiumBy.XPATH,
        "//*[contains(@text,'no rewards') or contains(@text,'No rewards') or contains(@text,'haven')]")

    # --- Reward detail / webview (WATCH: surface not deeply crawled) ---
    # A reward detail screen typically surfaces a "Shop now" / "Earn" CTA and a
    # back affordance. Kept conservative — we assert a detail screen opens, not
    # that an external brand URL loads (RAIZ-9984 flakiness).
    DETAIL_SHOP_CTA = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[contains(@text,'Shop') "
        "or contains(@text,'shop') or contains(@text,'Earn') or contains(@text,'Activate')]]")
    DETAIL_TERMS = (AppiumBy.XPATH,
        "//*[contains(@text,'Terms') or contains(@text,'terms') or contains(@text,'How it works') "
        "or contains(@text,'Cashback')]")

    # --- Linked accounts (raiz://rewards_linked_accounts) ---
    LINKED_ACCOUNTS_TITLE = (AppiumBy.XPATH,
        "//*[contains(@text,'Linked account') or contains(@text,'Linked card') "
        "or contains(@text,'linked card')]")
    # The real affordance on 2.39.1d reads 'Add Round-Up Account' (capitalised),
    # so the case-sensitive XPath contains() must accept both cases plus the
    # 'Round-Up' wording, not just lowercase 'account'/'card'.
    ADD_ACCOUNT_AFFORDANCE = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[contains(@text,'Add') "
        "and (contains(@text,'account') or contains(@text,'Account') "
        "or contains(@text,'card') or contains(@text,'Card') "
        "or contains(@text,'Round-Up'))]] "
        "| //*[@clickable='true'][.//android.widget.TextView[contains(@text,'Link')]]")
    INSTITUTION_ROW = (AppiumBy.XPATH,
        "//*[contains(@text,'Dag Site') or contains(@text,'Bank') or contains(@text,'Card') "
        "or contains(@text,'Visa') or contains(@text,'Mastercard')]")

    # --- Auto rewards (raiz://rewards_auto) ---
    # Verified on 2.39.1d: this screen has NO 'Auto Rewards' title. It opens on the
    # rewards Earn surface with the distinctive 'Click-through' / 'Automatic' reward
    # modes, a 'Surveys'/'Shops' grouping, category chips and a 'Sort:' control.
    # Match those real markers (a 'Click-through'/'Automatic' mode toggle plus the
    # 'Sort:' control) instead of a non-existent title/Switch.
    AUTO_TITLE = (AppiumBy.XPATH,
        "//*[@text='Automatic' or @text='Click-through' or @text='Surveys' or @text='Shops']")
    AUTO_TOGGLE = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Automatic' or @text='Click-through']] "
        "| //android.widget.TextView[starts-with(@text,'Sort:')]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        # The rewards surface can render its content lazily (the Earn/Track strip
        # may settle a beat after the deep link resolves), which made the fixture's
        # is_loaded() flake intermittently. Accept any of the stable Earn signals
        # — the tab strip, the Featured header, or the header value — and give the
        # content a real (long) wait before giving up.
        if (self.is_present_now(self.EARN_TAB) or self.is_present_now(self.TRACK_TAB)
                or self.is_present_now(self.FEATURED_HEADER) or self.is_present_now(self.HEADER_VALUE)):
            return True
        from config.settings import LONG_WAIT
        return (self.is_visible(self.EARN_TAB, timeout=max(timeout, LONG_WAIT))
                or self.is_present_now(self.FEATURED_HEADER))

    def is_earn_content_loaded(self) -> bool:
        return self.is_present(self.FEATURED_LIST)

    def get_rewards_value(self) -> str:
        return self.get_text(self.HEADER_VALUE)

    def search(self, store_name: str):
        """Type into the rewards search box. The field is a (nested) EditText whose
        'Search by store name' hint disappears on focus, so we re-find the leaf
        EditText after focusing rather than relying on the hint-gated locator."""
        # Focus via the hint-labelled field while it's still empty.
        self.click_present(self.SEARCH_INPUT)
        # The leaf input is the EditText with no EditText descendant; send keys there.
        leaf = (AppiumBy.XPATH, "//android.widget.EditText[not(.//android.widget.EditText)]")
        els = self.driver.find_elements(*leaf)
        target = els[-1] if els else self.driver.find_element(*self.SEARCH_FIELD)
        target.send_keys(store_name)

    def tap_earn_tab(self):
        self.click(self.EARN_TAB)

    def tap_track_tab(self):
        self.click(self.TRACK_TAB)

    # Aliases matching the task's requested naming.
    def switch_to_earn(self):
        self.tap_earn_tab()

    def switch_to_track(self):
        self.tap_track_tab()

    def is_track_content_loaded(self) -> bool:
        """Track tab actually shows tracked-rewards content (not just the tab itself).

        The Track tab surfaces the Pending rewards / Rewards invested summary —
        content that does NOT exist on the Earn tab — so this distinguishes a real
        content switch from the anti-pattern of asserting the tab is still visible.
        """
        return (self.is_present(self.PENDING_REWARDS_LABEL, timeout=DEFAULT_WAIT)
                or self.is_present(self.REWARDS_INVESTED_LABEL, timeout=2))

    def filter_track_by(self, filter_: str):
        filters = {"All": self.FILTER_ALL, "Pending": self.FILTER_PENDING, "Invested": self.FILTER_INVESTED}
        self.click(filters[filter_])

    def get_boosted_items(self):
        return self.driver.find_elements(*self.BOOSTED_ITEMS)

    def get_featured_items(self):
        return self.driver.find_elements(*self.FEATURED_ITEMS)

    def get_rewards(self):
        """All reward cards visible across the Earn lists (featured + boosted)."""
        return self.driver.find_elements(*self.ANY_REWARD_ITEM)

    def get_reward_amount_texts(self) -> list[str]:
        """Text of every $-bearing label currently on the Earn screen."""
        return [el.text for el in self.driver.find_elements(*self.REWARD_AMOUNTS) if el.text]

    def open_first_reward(self) -> bool:
        """Tap the first reward card to open its detail screen. Returns True if a card was tapped."""
        items = self.get_rewards()
        if not items:
            return False
        items[0].click()
        return True

    def is_detail_screen_shown(self, timeout=DEFAULT_WAIT) -> bool:
        """A reward detail screen is open (CTA or terms/how-it-works content present)
        and the Earn/Track tab strip is gone — i.e. we navigated away from the list."""
        on_detail = (self.is_visible(self.DETAIL_SHOP_CTA, timeout=timeout)
                     or self.is_visible(self.DETAIL_TERMS, timeout=2))
        left_list = not self.is_present_now(self.EARN_TAB)
        return on_detail or left_list

    def is_empty_state_shown(self) -> bool:
        return self.is_visible(self.EMPTY_STATE)

    def is_track_empty_state_shown(self) -> bool:
        return self.is_present_now(self.TRACK_EMPTY_STATE)
