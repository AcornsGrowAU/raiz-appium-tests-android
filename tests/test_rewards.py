import pytest
from appium.webdriver.common.appiumby import AppiumBy
from pages.rewards_page import RewardsPage
from utils.assertions import assert_non_negative_money, is_money
from utils.deep_links import DeepLinks


@pytest.mark.rewards
@pytest.mark.smoke
class TestRewardsEarnTab:
    def test_rewards_screen_loads(self, rewards):
        assert rewards.is_loaded()

    def test_earn_tab_visible(self, rewards):
        assert rewards.is_visible(rewards.EARN_TAB)

    def test_track_tab_visible(self, rewards):
        assert rewards.is_visible(rewards.TRACK_TAB)

    def test_header_value_visible(self, rewards):
        assert rewards.is_visible(rewards.HEADER_VALUE)

    def test_search_bar_visible(self, rewards):
        assert rewards.is_visible(rewards.SEARCH_INPUT)

    def test_featured_rewards_list_visible(self, rewards):
        assert rewards.is_visible(rewards.FEATURED_LIST)

    def test_boosted_rewards_list_visible(self, rewards):
        assert rewards.is_visible(rewards.BOOSTED_LIST)

    def test_featured_items_present(self, rewards):
        items = rewards.get_featured_items()
        assert len(items) > 0, "Expected at least one featured reward item"

    def test_boosted_items_present(self, rewards):
        items = rewards.get_boosted_items()
        assert len(items) > 0, "Expected at least one boosted reward item"

    def test_search_input_accepts_text(self, rewards):
        rewards.search("amazon")
        from appium.webdriver.common.appiumby import AppiumBy
        assert rewards.is_visible((AppiumBy.XPATH, "//android.widget.EditText[@text='amazon']"))


@pytest.mark.rewards
class TestRewardsTrackTab:
    def test_track_tab_navigates(self, rewards):
        rewards.tap_track_tab()
        assert rewards.is_visible(rewards.PENDING_REWARDS_LABEL)

    def test_pending_rewards_label_visible(self, rewards):
        rewards.tap_track_tab()
        assert rewards.is_visible(rewards.PENDING_REWARDS_LABEL)

    def test_rewards_invested_label_visible(self, rewards):
        rewards.tap_track_tab()
        assert rewards.is_visible(rewards.REWARDS_INVESTED_LABEL)

    def test_filter_tabs_visible(self, rewards):
        rewards.tap_track_tab()
        assert rewards.is_visible(rewards.FILTER_ALL)
        assert rewards.is_visible(rewards.FILTER_PENDING)
        assert rewards.is_visible(rewards.FILTER_INVESTED)

    def test_filter_all_tappable(self, rewards):
        rewards.tap_track_tab()
        rewards.filter_track_by("All")
        assert rewards.is_visible(rewards.FILTER_ALL)

    def test_filter_pending_tappable(self, rewards):
        rewards.tap_track_tab()
        rewards.filter_track_by("Pending")

    def test_filter_invested_tappable(self, rewards):
        rewards.tap_track_tab()
        rewards.filter_track_by("Invested")

    def test_earn_tab_navigates_back(self, rewards):
        rewards.tap_track_tab()
        rewards.tap_earn_tab()
        assert rewards.is_visible(rewards.FEATURED_HEADER)


def _open_rewards_link(rewards, link, ready=None):
    """PIN-aware deep-link open from within a test (mirrors conftest._open_deep_link).

    The `rewards` fixture only opens raiz://raiz_rewards; the linked-accounts and
    auto variants need their own navigation, and rewards screens can re-prompt for
    the PIN. We import PinPage lazily and reuse the page's existing driver.

    `ready` is an optional zero-arg predicate that returns True once the target
    surface has rendered. The linked-accounts/auto screens are heavy and lazy, and
    deep-link nav on this build intermittently misroutes or drops back to the PIN;
    if a readiness probe is given and the surface hasn't appeared, we re-open ONCE
    (the same one-shot retry the conftest rewards/transaction fixtures use) before
    handing back to the test's own waited assertions.
    """
    from pages.pin_page import PinPage
    from config.settings import STATE_PROBE_WAIT, TEST_PIN

    def _open_once():
        DeepLinks.open(rewards.driver, link)
        pin = PinPage(rewards.driver)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            pin.enter_pin(TEST_PIN)
            rewards.driver._biometrics_pending = True
        # Clear the biometric prompt that can follow a PIN re-entry, centrally
        # (clicks 'No'); safe no-op when none is showing.
        rewards.dismiss_modal()

    _open_once()
    if ready is not None and not ready():
        _open_once()


@pytest.mark.rewards
class TestRewardsTabContentSwitch:
    """The tabs must switch CONTENT, not just remain visible (the anti-pattern the
    analysis doc calls out: asserting the tapped tab is still shown)."""

    def test_track_shows_tracked_content_not_just_tab(self, rewards):
        # Earn content (featured list) present first.
        assert rewards.is_earn_content_loaded(), "Earn list should be present before switching"
        rewards.switch_to_track()
        # Track exposes Pending/Invested summary that does NOT exist on Earn.
        assert rewards.is_track_content_loaded(), "Track tab did not switch to tracked-rewards content"

    def test_track_does_not_show_earn_featured_list(self, rewards):
        rewards.switch_to_track()
        assert rewards.is_track_content_loaded()
        # The Earn featured list root should be gone once Track content is shown.
        assert not rewards.is_present_now(rewards.FEATURED_LIST), \
            "Earn featured list still present on Track tab — content did not switch"

    def test_earn_shows_featured_list_after_returning_from_track(self, rewards):
        rewards.switch_to_track()
        assert rewards.is_track_content_loaded()
        rewards.switch_to_earn()
        assert rewards.is_earn_content_loaded(), "Earn featured list did not return after switching back"


@pytest.mark.rewards
class TestRewardsEarnValues:
    """Value-over-presence: the Earn lists carry real entries and any reward $
    amounts are well-formed money (utils/assertions), not just present."""

    def test_rewards_list_has_real_entries(self, rewards):
        items = rewards.get_rewards()
        assert len(items) > 0, "Expected at least one reward card across the Earn lists"

    def test_header_value_is_well_formed_money(self, rewards):
        value = rewards.get_rewards_value()
        # Header reward balance must be a well-formed, non-negative dollar amount.
        assert_non_negative_money(value, "rewards header value")

    def test_reward_amounts_are_well_formed_money(self, rewards):
        import re
        # Only treat a token as a monetary amount if a digit follows a '$' (e.g.
        # '$5', '$1,234.56'). Decorative copy like 'Answer questions, earn $$'
        # uses '$' as a symbol, not an amount, and must be ignored — it is NOT a
        # malformed money value. The real money check below is unchanged: any token
        # that DOES denote a dollar amount must parse as well-formed money.
        money_token = re.compile(r"\$\s?\d")
        amounts = [t for t in rewards.get_reward_amount_texts() if money_token.search(t)]
        if not amounts:
            pytest.skip("No $-denominated reward amounts rendered on this screen")
        for text in amounts:
            assert is_money(text), f"Malformed reward amount rendered: {text!r}"


@pytest.mark.rewards
class TestRewardsTrackValues:
    def test_pending_and_invested_amounts_well_formed(self, rewards):
        rewards.switch_to_track()
        assert rewards.is_track_content_loaded()
        # Pending/Invested summary money must be well-formed and non-negative.
        amounts = [el.text for el in rewards.driver.find_elements(*rewards.REWARD_AMOUNTS)
                   if el.text and "$" in el.text]
        if not amounts:
            pytest.skip("No $-denominated tracked-reward amounts rendered")
        for text in amounts:
            assert_non_negative_money(text, "tracked reward amount")

    def test_track_state_is_empty_or_loaded(self, rewards):
        """Robustness: the Track tab resolves to a definite state — either the
        Pending/Invested summary (loaded) or an explicit empty-state message —
        never a blank screen."""
        rewards.switch_to_track()
        loaded = rewards.is_track_content_loaded()
        empty = rewards.is_track_empty_state_shown()
        assert loaded or empty, "Track tab showed neither tracked content nor an empty state"


@pytest.mark.rewards
class TestRewardsDetailNavigation:
    """WATCH: the reward detail/webview surface is not deeply crawled. Conservative
    — assert a detail screen opens and back returns to the list; do NOT assert an
    external brand URL loads (RAIZ-9984 Petbarn URL, RAIZ-10061 PDF are flaky)."""

    def test_opening_reward_navigates_to_detail(self, rewards):
        assert rewards.open_first_reward(), "No reward card available to open"
        assert rewards.is_detail_screen_shown(), "Tapping a reward did not open a detail screen"

    def test_detail_back_returns_to_rewards_list(self, rewards):
        assert rewards.open_first_reward(), "No reward card available to open"
        assert rewards.is_detail_screen_shown(), "Detail screen did not open"
        rewards.go_back()
        # Back should land on the Earn list (tab strip + featured list visible again).
        assert rewards.is_visible(rewards.EARN_TAB), "Back did not return to the rewards Earn screen"


@pytest.mark.rewards
class TestRewardsLinkedAccounts:
    """Linked-accounts screen shows institutions and/or an add-account affordance."""

    def _linked_accounts_ready(self, rewards):
        # The CDR-linked institutions and the add-account affordance lazy-load, so
        # this probe (used for the one-shot reopen retry) waits rather than snapshots.
        return (rewards.is_present_now(rewards.LINKED_ACCOUNTS_TITLE)
                or rewards.is_visible(rewards.INSTITUTION_ROW, timeout=4)
                or rewards.is_present_now(rewards.ADD_ACCOUNT_AFFORDANCE))

    def test_linked_accounts_screen_loads(self, rewards):
        _open_rewards_link(rewards, DeepLinks.REWARDS_LINKED_ACCOUNTS,
                           ready=lambda: self._linked_accounts_ready(rewards))
        # Either the screen title, a linked institution, or an add affordance proves
        # we reached a real linked-accounts surface (not a blank/error screen).
        shown = (rewards.is_visible(rewards.LINKED_ACCOUNTS_TITLE, timeout=4)
                 or rewards.is_visible(rewards.INSTITUTION_ROW, timeout=2)
                 or rewards.is_visible(rewards.ADD_ACCOUNT_AFFORDANCE, timeout=2))
        assert shown, "Linked-accounts screen showed no title, institution, or add-account affordance"

    def test_linked_accounts_offers_institution_or_add_affordance(self, rewards):
        _open_rewards_link(rewards, DeepLinks.REWARDS_LINKED_ACCOUNTS,
                           ready=lambda: self._linked_accounts_ready(rewards))
        # Linked institutions (Dag Site CDR accounts) are fetched async, so
        # snapshot-checking right after navigation misses them — wait for them.
        has_institution = rewards.is_visible(rewards.INSTITUTION_ROW, timeout=6)
        has_add = rewards.is_visible(rewards.ADD_ACCOUNT_AFFORDANCE, timeout=4)
        assert has_institution or has_add, \
            "Linked-accounts screen offered neither a linked institution nor a way to add one"


@pytest.mark.rewards
class TestRewardsAuto:
    """Auto rewards screen (raiz://rewards_auto)."""

    def test_auto_rewards_screen_loads(self, rewards):
        # The auto-rewards surface is the heavy Earn screen (Click-through/Automatic
        # modes, Surveys/Shops, category chips) and renders lazily — wait for the
        # marker as the readiness signal so the one-shot reopen can recover a slow
        # or misrouted first navigation.
        _open_rewards_link(rewards, DeepLinks.REWARDS_AUTO,
                           ready=lambda: rewards.is_visible(rewards.AUTO_TITLE, timeout=6))
        # Auto-rewards surfaces an Auto-mode marker and/or a toggle control.
        shown = (rewards.is_visible(rewards.AUTO_TITLE, timeout=4)
                 or rewards.is_present_now(rewards.AUTO_TOGGLE))
        assert shown, "Auto rewards screen showed neither an Auto title nor a toggle control"
