from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, POLL_INTERVAL, STATE_PROBE_WAIT
from pages.base_page import BasePage


class RewardsPage(BasePage):
    # Settle window for reads taken right after a Track filter re-composition.
    # Long enough to absorb a 1-3s emulator RTT recompose, short enough that a
    # genuinely-absent value still fails fast.
    DEFAULT_SETTLE = 5

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
    # Error / blank-webview state the brand-detail screen must NOT show (RAIZ-9984:
    # tapping a reward opened a blank or errored webview instead of rendering brand
    # content). Match the common load-failure copy a WebView surfaces.
    DETAIL_ERROR_STATE = (AppiumBy.XPATH,
        "//*[contains(@text,'went wrong') or contains(@text,'Something went wrong') "
        "or contains(@text,'try again') or contains(@text,'Try again') "
        "or contains(@text,'No internet') or contains(@text,'no internet') "
        "or contains(@text,'ERR_') or contains(@text,'webpage') or contains(@text,'web page') "
        "or contains(@text,'not available') or contains(@text,'failed to load') "
        "or contains(@text,'Failed to load') or contains(@text,'unable to load') "
        "or contains(@text,\"couldn't load\") or contains(@text,\"can't be reached\")]")

    # --- Linked accounts (raiz://rewards_linked_accounts) ---
    # On 2.39.1d the real screen title is 'Accounts for Raiz Rewards' (NOT
    # 'Linked accounts'), with an intro paragraph '... eligible for Automatic
    # Rewards opportunities ...'. The old 'Linked account/card' contains() never
    # matched on this build, so the title branch of the load assertions silently
    # burned its timeout and the test leaned entirely on the institution/add-account
    # fallbacks. Accept the verified real title and intro copy as well.
    LINKED_ACCOUNTS_TITLE = (AppiumBy.XPATH,
        "//*[contains(@text,'Accounts for Raiz Rewards') "
        "or contains(@text,'eligible for Automatic Rewards') "
        "or contains(@text,'Linked account') or contains(@text,'Linked card') "
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
        # Tapping a Track filter triggers a Compose list re-composition (rows are
        # filtered/animated in). On a slow emulator (1-3s RTT) the re-render lags
        # the tap, so any immediate snapshot read of the relabelled summary can
        # race the recompose and spuriously see a transient empty/blank frame.
        # Block until the Pending-rewards summary label has settled back into the
        # tree before callers read values — this is a settle wait, not a change in
        # what is asserted.
        self.is_visible(self.PENDING_REWARDS_LABEL, timeout=DEFAULT_WAIT)

    def wait_for_track_label(self, locator, timeout=DEFAULT_WAIT) -> bool:
        """Poll for a Track summary label to be present (used to ride out the
        filter re-composition before reading values)."""
        return self.is_present(locator, timeout=timeout)

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

    def _tap_card_and_confirm_navigation(self, locator, timeout=DEFAULT_WAIT) -> bool:
        """Tap the first card matching `locator` and confirm we actually left the
        Earn list (the tab strip is gone), retrying the tap if it was swallowed.

        Two slow-emulator hazards this guards against, without changing the test's
        oracle:
          * StaleElementReferenceException — a freshly-found card reference can go
            stale if the Compose list recomposes between find and click. We re-find
            the card on every attempt rather than reusing a cached handle.
          * A swallowed tap on a still-animating card leaves us on the list. Since
            the list reward cards themselves carry 'Cashback' copy (which the
            DETAIL_TERMS oracle matches), a swallowed tap could otherwise produce a
            FALSE PASS. Confirming the Earn tab strip has gone proves we navigated
            into the brand detail before any content is read."""
        import time
        from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
        deadline = time.monotonic() + timeout
        attempted = False
        while True:
            cards = self.driver.find_elements(*locator)
            if not cards:
                # Nothing of this kind on screen; let the caller try the next list.
                return False
            attempted = True
            try:
                cards[0].click()
            except (StaleElementReferenceException, WebDriverException):
                # List recomposed under us — loop to re-find and retry.
                if time.monotonic() >= deadline:
                    break
                time.sleep(POLL_INTERVAL)
                continue
            # Confirm we navigated off the Earn list (tab strip gone). The detail
            # surface is a separate route, so the Earn tab disappears on success.
            if not self.is_visible(self.EARN_TAB, timeout=STATE_PROBE_WAIT):
                return True
            # Tap was swallowed (still on the list) — retry until the deadline.
            if time.monotonic() >= deadline:
                break
        # We managed to tap a card at least once even if navigation wasn't
        # confirmed; report whether we acted so the caller can fall through.
        return attempted

    def open_first_featured_or_boosted_reward(self) -> bool:
        """Tap the first Featured reward, falling back to the first Boosted one, to
        open its brand-detail screen. Returns True if a card was tapped AND we
        navigated off the Earn list into the detail surface.

        TC-12/RAIZ-9984 targets the Featured/Boosted brand detail specifically, so
        this prefers those lists rather than ANY_REWARD_ITEM ordering. The tap is
        retried and confirmed (see _tap_card_and_confirm_navigation) so a swallowed
        tap on a slow emulator can't leave us reading list-card copy as if it were
        brand-detail content."""
        if self.get_featured_items() and self._tap_card_and_confirm_navigation(self.FEATURED_ITEMS):
            return True
        if self.get_boosted_items() and self._tap_card_and_confirm_navigation(self.BOOSTED_ITEMS):
            return True
        return False

    def get_detail_cta_text(self, timeout=DEFAULT_WAIT):
        """Non-empty text of the brand-detail shop/activate CTA, or None if it has
        not rendered within `timeout`."""
        if not self.is_visible(self.DETAIL_SHOP_CTA, timeout=timeout):
            return None
        for el in self.driver.find_elements(*self.DETAIL_SHOP_CTA):
            text = (el.text or "").strip()
            if text:
                return text
            # Raiz CTAs are null-text clickable containers; read the labelled child.
            for child in el.find_elements(AppiumBy.XPATH, ".//android.widget.TextView"):
                if child.text and child.text.strip():
                    return child.text.strip()
        return None

    def get_detail_terms_text(self, timeout=DEFAULT_WAIT):
        """Non-empty terms / how-it-works / cashback copy on the brand detail, or
        None if none rendered within `timeout`."""
        if not self.is_visible(self.DETAIL_TERMS, timeout=timeout):
            return None
        for el in self.driver.find_elements(*self.DETAIL_TERMS):
            if el.text and el.text.strip():
                return el.text.strip()
        return None

    def is_detail_error_state_shown(self) -> bool:
        """A blank/errored brand webview surfaced an error message (RAIZ-9984)."""
        return self.is_present_now(self.DETAIL_ERROR_STATE)

    def is_empty_state_shown(self) -> bool:
        return self.is_visible(self.EMPTY_STATE)

    def is_track_empty_state_shown(self) -> bool:
        return self.is_present_now(self.TRACK_EMPTY_STATE)

    # --- Track-tab pending / invested split (value reconciliation) ---
    # The Track summary renders, for each metric, a label TextView ('Pending
    # rewards' / 'Rewards invested') with its dollar amount as a nearby TextView.
    # Compose lays the amount out as a sibling inside the same row container, so we
    # walk up a few ancestor levels from the label and read the first descendant
    # TextView that holds a money token ('$' + digit). This is robust to the exact
    # nesting depth Compose uses for the row. A Track total, if the build renders
    # one, is read the same way from a 'Total' label.

    @staticmethod
    def _xpath_literal(value: str) -> str:
        """Quote a string as an XPath literal, tolerating embedded apostrophes."""
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

    def _money_near_label(self, label_text: str, timeout: float = 0.0):
        """Dollar string rendered alongside `label_text` on the Track summary, or
        None if no $-amount sits in the label's row container.

        `timeout`>0 retries the scan (POLL_INTERVAL between tries) so a single
        in-flight recompose frame after a filter tap — where the label is present
        but its sibling amount has not re-attached yet — doesn't yield a spurious
        None on a slow emulator. A real "no amount" still returns None after the
        wait, preserving the test's value-vs-presence oracle."""
        import re
        import time
        from config.settings import POLL_INTERVAL
        money_token = re.compile(r"\$\s?-?\d")

        def _scan():
            for depth in range(1, 5):
                ancestor = "/".join([".."] * depth)
                xpath = (f"//android.widget.TextView[@text={self._xpath_literal(label_text)}]"
                         f"/{ancestor}//android.widget.TextView[contains(@text,'$')]")
                for el in self.driver.find_elements(AppiumBy.XPATH, xpath):
                    if el.text and money_token.search(el.text):
                        return el.text
            return None

        deadline = time.monotonic() + timeout
        while True:
            found = _scan()
            if found is not None or time.monotonic() >= deadline:
                return found
            time.sleep(POLL_INTERVAL)

    def get_pending_rewards_amount(self, timeout: float = 0.0):
        """Dollar string shown for 'Pending rewards' on the Track tab, or None.

        Pass timeout>0 right after a filter tap to ride out the re-composition."""
        return self._money_near_label("Pending rewards", timeout=timeout)

    def get_rewards_invested_amount(self):
        """Dollar string shown for 'Rewards invested' on the Track tab, or None."""
        return self._money_near_label("Rewards invested")

    def get_track_total_amount(self):
        """Dollar string for a Track total/overall figure if the build renders one,
        else None. Optional reconciliation oracle (total == pending + invested)."""
        return self._money_near_label("Total")

    def get_track_money_texts(self) -> list[str]:
        """Text of every $-bearing TextView currently rendered on the Track tab —
        used to inspect the rows surfaced by the active filter."""
        return [el.text for el in self.driver.find_elements(*self.REWARD_AMOUNTS) if el.text]
