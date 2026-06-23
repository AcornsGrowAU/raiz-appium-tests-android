from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL
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

    # --- Post-"Create Jar" wizard steps (verified on device emulator-5556) ---
    # Tapping "Create Jar" on the customise screen does NOT commit the jar; it
    # advances a multi-step wizard:
    #   1. "Set goal amount" — a numeric keypad with a "Skip" affordance;
    #   2. portfolio selection — risk-profile chips + ETF allocation list, already
    #      defaulted, confirmed by the single full-width primary Button at the
    #      bottom of the screen.
    # Only after the portfolio confirm does the jar commit and the app land on the
    # Jars LIST screen ("Raiz Jars" + Active/Closed + a Manage Jar control).
    SET_GOAL_TITLE = (AppiumBy.XPATH, "//*[@text='Set goal amount']")
    SKIP_GOAL_BUTTON = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Skip']]")
    # The portfolio step's only full-width primary Button (no text node of its own).
    PORTFOLIO_CONFIRM_BUTTON = (AppiumBy.XPATH, "//android.widget.Button")

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

    def skip_goal_step(self, timeout=DEFAULT_WAIT) -> bool:
        """Step 2 of the create wizard. After 'Create Jar' the app shows a
        'Set goal amount' keypad; creating a jar with no goal is the minimal path,
        so tap 'Skip'. Returns True if the goal step was present and skipped."""
        if not self.is_visible(self.SET_GOAL_TITLE, timeout=timeout):
            return False
        self.click(self.SKIP_GOAL_BUTTON)
        return True

    def confirm_portfolio_step(self, timeout=DEFAULT_WAIT) -> bool:
        """Step 3 of the create wizard. The portfolio screen (risk-profile chips +
        ETF allocation list) comes pre-defaulted, so committing the jar is a single
        tap of the screen's only full-width primary Button at the bottom. Returns
        True if that confirm Button was found and tapped.

        Pick the BOTTOM-MOST wide Button: the portfolio step has exactly one such
        Button, but guard against a stray top-bar ImageButton by choosing the
        lowest, widest candidate."""
        import re
        buttons = self.driver.find_elements(*self.PORTFOLIO_CONFIRM_BUTTON)
        best = None  # (element, y_top)
        for b in buttons:
            try:
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", b.get_attribute("bounds")))
            except Exception:
                continue
            if (x2 - x1) > 600 and (best is None or y1 > best[1]):
                best = (b, y1)
        if best is None:
            return False
        best[0].click()
        return True

    def wait_for_create_committed(self, timeout=LONG_WAIT) -> bool:
        """Drive the post-'Create Jar' wizard to completion and block until the jar
        actually commits, instead of racing the network.

        VERIFIED ON DEVICE: tapping 'Create Jar' does NOT commit a jar — it advances
        a multi-step wizard (Set goal amount -> portfolio selection) and only the
        final portfolio confirm commits and lands on the Jars LIST. The old logic
        ('create screen dismissed => committed') was wrong: the create screen
        dismisses straight to the goal step while no jar yet exists, so the caller
        read the Home count before the jar was created.

        This now actively completes the wizard:
          - Skip the 'Set goal amount' step;
          - confirm the defaulted portfolio (the bottom full-width Button);
        then polls until EITHER the Jars list screen renders (commit succeeded) or
        an 'Oops!' dialog appears (failure). Returns True if an 'Oops!' is showing
        (so the caller can assert no-error meaningfully), False once the jar has
        committed onto the Jars list. Idempotent per step: re-taps Skip/confirm only
        while that step is still on screen, so a slow round-trip just polls."""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_oops_shown():
                return True
            # Committed: the Jars LIST screen (with at least one jar) is showing.
            if self.has_active_jar():
                return False
            # Advance whichever wizard step is currently on screen.
            if self.is_visible(self.SET_GOAL_TITLE, timeout=0):
                self.skip_goal_step(timeout=0)
            elif self.is_present_now(self.PORTFOLIO_CONFIRM_BUTTON) and not self.is_create_screen(timeout=0):
                self.confirm_portfolio_step(timeout=0)
            time.sleep(POLL_INTERVAL)
        # Timed out — report whatever the Oops state is so the caller's assertion
        # reflects reality.
        return self.is_oops_shown()

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

    def scroll_jar_into_view(self, name: str) -> bool:
        """Bring the named jar's card on-screen before reading it. The Jars list is a
        scrollable column, so a second/third jar can recycle out of the view tree
        until scrolled to its OWN name. Best-effort: resets to the top first (the
        UiScrollable search is forward-only) then scrolls to the jar name.

        Matches the name with `contains` (not exact) because a long jar name can
        render TRUNCATED/ellipsized on the card — an exact-text probe would then
        report the card as absent even though it is on screen. Returns True once a
        TextView containing the name is present."""
        name_loc = (AppiumBy.XPATH,
                    f"//android.widget.TextView[contains(@text, {self._xq(name)})]")
        if self.is_present_now(name_loc):
            return True
        self.scroll_to_top()
        try:
            self.scroll_to_text(name)
        except Exception:
            pass
        return self.is_present_now(name_loc)

    def get_jar_balance_by_name(self, name: str) -> str | None:
        """Name-scoped jar balance getter.

        Return the well-formed money string rendered INSIDE the jar card/row whose
        own text contains `name`, or None if that jar's row renders no amount.
        Reading within the matched row (not the whole screen, and not a broad
        wrapper that spans every sibling) is what isolates one jar's value from a
        sibling's — the suite's known presence-only weakness is that a screen-wide
        '$' scrape can't tell two jars apart.

        Mirrors the proven KidsPage.get_kid_value_by_name approach after the earlier
        clickable-container version returned None on device:
          - Search `//android.view.View` (NOT `[@clickable='true']`): the jar's name
            and balance can sit inside a NON-clickable card wrapper, so restricting
            to a clickable ancestor found no money TextView at all -> None for every
            jar despite the backend balance being settled.
          - Match the name with `contains` (not exact `@text=`): long jar names can
            render truncated on the card, so an exact match never bound the row.
          - Pick the TIGHTEST container: XPath `find_elements` returns ancestors
            BEFORE descendants, so a naive match binds the OUTER list wrapper that
            holds EVERY sibling's money and leaks jar-A's value for every name. Among
            containers that hold this name AND a '$', choose the one with the FEWEST
            money TextViews (the single-jar row has exactly one), then read the money
            that FOLLOWS this jar's name in document order."""
        self.scroll_jar_into_view(name)
        candidates = self.driver.find_elements(
            AppiumBy.XPATH,
            f"//android.view.View"
            f"[.//android.widget.TextView[contains(@text, {self._xq(name)})]"
            f" and .//android.widget.TextView[contains(@text, '$')]]",
        )
        best = None  # (money_count, money) — minimise money_count to get the tight row
        for c in candidates:
            money_count = self._money_count_in(c)
            if money_count == 0:
                continue
            money = self._money_for_name_in(c, name)
            if money is None:
                continue
            if best is None or money_count < best[0]:
                best = (money_count, money)
                if money_count == 1:
                    # Tightest possible: a container scoped to exactly this jar.
                    return money
        return best[1] if best else None

    def _money_count_in(self, container) -> int:
        """Number of well-formed money TextViews inside a container. A single-jar
        row has exactly 1; a multi-jar wrapper has >1. Lets us reject broad
        wrappers that would leak a sibling jar's amount."""
        return len([tv for tv in container.find_elements(
            AppiumBy.XPATH, ".//android.widget.TextView[contains(@text, '$')]")
            if is_money(tv.text or "")])

    def _money_for_name_in(self, container, name: str) -> str | None:
        """The money string belonging to `name` within `container`.

        When the container wraps only this jar, any money inside is this jar's.
        When it (still) wraps more than one jar, pick the money TextView that
        FOLLOWS this jar's name TextView in document order, so we don't return a
        sibling's amount that happens to appear first."""
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

    @staticmethod
    def _xq(text: str) -> str:
        """Quote a string for an XPath literal, handling embedded apostrophes via
        concat() so jar names with quotes don't break the selector."""
        if "'" not in text:
            return f"'{text}'"
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"
