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

    def accept_consent(self, timeout=2) -> bool:
        """If the Raiz Kids identity-consent gate is up, accept it (tap 'I consent'/
        Continue) to advance toward the list. A parent WHO HAS active kids still hits
        this gate on a freshly-installed/cleared app, so accepting it — the real user
        action — is what reveals the populated list. Idempotent: a no-op (returns
        False) when the consent gate isn't showing. Never raises."""
        if not self.is_consent_screen(timeout=timeout):
            return False
        try:
            self.click(self.I_CONSENT_BUTTON)
            return True
        except Exception:
            return False

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

    def _scroll_name_into_view(self, name: str) -> None:
        """Best-effort scroll the kid row whose name contains `name` into view, so
        a kid below the fold is rendered before we read its card (the list
        recycles off-screen rows). The kid label renders as 'Name LastName (<1yr)';
        scroll to the first-name token which is always on-screen text."""
        try:
            self.scroll_to_top()
        except Exception:
            pass
        try:
            self.scroll_to_text(name)
        except Exception:
            pass

    def get_kid_value_by_name(self, name: str) -> str | None:
        """Name-scoped kid balance getter.

        Return the well-formed money string rendered INSIDE the kid card/row whose
        own text contains `name`, or None if that kid's row renders no amount.
        Reading within the matched row (not the whole screen, and not a broad
        wrapper that spans every sibling) is what isolates one sibling's value from
        the other's — the suite's known presence-only weakness is that a
        screen-wide '$' scrape can't tell two kids apart.

        IMPORTANT — why we pick the TIGHTEST container, not the first match:
        XPath `find_elements` returns ancestors BEFORE descendants in document
        order. A naive `//android.view.View[@clickable='true'][.//TextView[name]]`
        therefore matches the OUTER list/card wrapper first — and that wrapper also
        contains EVERY sibling's money TextView, so `_first_money_in` would return
        the first money on screen (kid-A's) for *every* name queried. That is the
        exact failure where both kid cards report kid-A's balance. To isolate the
        row, we choose, among the containers that hold this name, the one with the
        FEWEST 'yr' name TextViews (i.e. the tightest row that wraps exactly this
        one kid — never a multi-kid wrapper), and read the money nearest the name
        within it."""
        self._scroll_name_into_view(name)
        # All View ancestors that contain this kid's name AND at least one money
        # TextView. We then narrow to the tightest single-kid row below.
        candidates = self.driver.find_elements(
            AppiumBy.XPATH,
            f"//android.view.View[.//android.widget.TextView[contains(@text, {self._xq(name)})]"
            f" and .//android.widget.TextView[contains(@text, '$')]]",
        )
        best = None  # (kid_name_count, money) — minimise kid_name_count
        for c in candidates:
            kid_name_count = self._kid_name_count_in(c)
            if kid_name_count == 0:
                continue
            money = self._money_for_name_in(c, name)
            if money is None:
                continue
            if best is None or kid_name_count < best[0]:
                best = (kid_name_count, money)
                if kid_name_count == 1:
                    # Tightest possible: a container scoped to exactly this kid.
                    return money
        return best[1] if best else None

    def _kid_name_count_in(self, container) -> int:
        """Number of kid-name TextViews ('… (<age>yr)') inside a container. A
        single-kid row has exactly 1; a multi-kid wrapper has >1. Lets us reject
        broad wrappers that would leak a sibling's value."""
        return len(container.find_elements(
            AppiumBy.XPATH, ".//android.widget.TextView[contains(@text, 'yr')]"))

    def _money_for_name_in(self, container, name: str) -> str | None:
        """The money string belonging to `name` within `container`.

        When the container wraps only this kid, any money inside is this kid's.
        When it (still) wraps more than one kid, pick the money TextView that
        directly follows this kid's name TextView in document order, so we don't
        return a sibling's amount that happens to appear first."""
        tvs = container.find_elements(
            AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]")
        seen_name = False
        for tv in tvs:
            txt = tv.text or ""
            if name in txt:
                seen_name = True
            if seen_name and is_money(txt):
                return txt
        # Name not followed by money (recycler quirk): fall back to first money.
        for tv in tvs:
            if is_money(tv.text or ""):
                return tv.text
        return None

    def _first_money_in(self, container) -> str | None:
        for tv in container.find_elements(
                AppiumBy.XPATH, ".//android.widget.TextView[string-length(@text) > 0]"):
            if is_money(tv.text):
                return tv.text
        return None

    @staticmethod
    def _xq(text: str) -> str:
        """Quote a string for an XPath literal, handling embedded apostrophes via
        concat() so kid names with quotes don't break the selector."""
        if "'" not in text:
            return f"'{text}'"
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"
