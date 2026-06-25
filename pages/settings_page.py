from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT, STATE_PROBE_WAIT
from pages.base_page import BasePage


class SettingsPage(BasePage):
    TITLE = (AppiumBy.XPATH, "//*[@text='Settings']")
    # NOTE (shared-infra request): the close affordance is found by geometry in
    # close() rather than a hard-coded pixel-bounds locator. The old
    # CLOSE_BUTTON = @bounds='[924,117][1068,261]' was device-specific (flagged in
    # TEST_SUITE_ANALYSIS.md §3 row 4) and is intentionally not used here.

    NOTIFICATIONS_INBOX = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Notifications inbox']]")
    FUNDING_ACCOUNT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Funding account']]")
    ACCOUNTS_FINANCIAL_INSIGHTS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Accounts for financial insights']]")
    PLANS_AND_FEES = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Plans and fees']]")
    PERSONAL_DETAILS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Personal details']]")
    SECURITY_PRIVACY = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Security and privacy']]")
    MANAGE_NOTIFICATIONS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage notifications']]")
    MANAGE_ROUND_UPS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Manage Round-Ups']]")
    REFER_A_FRIEND = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Refer a friend']]")
    RATE_RAIZ = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Rate Raiz']]")
    HOW_TO_START = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='How to start guide']]")
    GET_SUPPORT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Get support']]")
    OUR_TERMS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Our terms']]")
    STATEMENTS_REPORTS = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Statements and reports']]")
    LOG_OUT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Log out']]")
    APP_VERSION = (AppiumBy.XPATH, "//*[contains(@text, 'App version:')]")
    NOTIFICATION_BADGE = (AppiumBy.XPATH, "//android.view.View[.//android.widget.TextView[@text='Notifications inbox']]//android.widget.TextView[not(@text='Notifications inbox')]")

    # Any toggle/switch on a settings sub-screen (e.g. notification preferences).
    # The Notifications screen (REDESIGN) does NOT use android.widget.Switch — its
    # toggles render as clickable Compose android.view.View nodes that still expose
    # a boolean @checked attribute. Match both the native Switch and these custom
    # checkable toggle Views so togglability checks work on the redesigned screen.
    SWITCHES = (AppiumBy.XPATH,
        "//android.widget.Switch | "
        "//android.view.View[@clickable='true' and (@checked='true' or @checked='false')]")

    # ---- profile / plan VALUE reads (TC-13) ------------------------------- #
    # The pricing-plans screen (raiz://plans) renders the account's subscription
    # tier as one of a small fixed set, with a "Current plan" marker on the tier
    # the user is actually on (docs/nav_map_5556.md row `raiz://plans`:
    # "Lite / Regular / Plus tiers ... Current plan marker"). The Plans-and-fees /
    # fees surface echoes the same tier under a "PLAN"/"Pricing plan" label
    # (docs/nav_map_5558.md row "Plans and fees": "...PLAN, Pricing plan, Regular").
    #
    # KNOWN_PLAN_TIERS is the set of CRAWL-VERIFIED tier names. Only Lite/Regular/
    # Plus are rendered on the live Plans (5556) and Fees (5558) surfaces; those
    # are the names a real tier render can be. The previous list also carried
    # 'Sapphire'/'Staple'/'Essential' — unverified guesses that appear in NO nav
    # map and would let a stray TextView masquerade as a tier. They are removed so
    # the oracle can never match a name the product doesn't actually render.
    KNOWN_PLAN_TIERS = ("Lite", "Regular", "Plus")
    CURRENT_PLAN_MARKER = (AppiumBy.XPATH,
        "//*[@text='Current plan' or @text='Current Plan' or contains(@text,'Current plan')]")

    # The monthly subscription fee is rendered co-located with the plan/fee copy
    # on the Plans (raiz://plans: "from $5.50 / month") and Plans-and-fees
    # (raiz://fees) surfaces. The current 'regular' tier's monthly fee is $5.50.
    # A real fee read must be a well-formed dollar amount, never a label-only or a
    # '%s' placeholder.
    _FEE_DOLLAR_RE = r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})"

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.TITLE, timeout=timeout)

    def visible_texts(self) -> list:
        """Every non-empty TextView string currently rendered. Used by VALUE tests
        that assert the screen shows real data (a name/email/tier), not just that a
        labelled element exists."""
        return [el.text for el in self.driver.find_elements(AppiumBy.XPATH, "//android.widget.TextView")
                if (el.text or "").strip()]

    # Editable-field nodes that carry their VALUE in @text (and sometimes their
    # label only in @content-desc). The Personal-details surface renders the
    # user's real first name / email / phone INSIDE EditText widgets, NOT plain
    # TextViews — so a TextView-only scrape (visible_texts) sees the field LABELS
    # but never the values. Compose text fields can also expose the typed value via
    # @content-desc. value_texts() unions all three so a value read actually sees
    # what the user sees.
    _VALUE_NODES = (AppiumBy.XPATH,
        "//android.widget.EditText | //android.widget.TextView | //android.widget.AutoCompleteTextView")

    def value_texts(self, include_content_desc: bool = True) -> list:
        """Every non-empty value string currently rendered, across TextView AND
        editable input widgets (EditText/AutoCompleteTextView). With
        include_content_desc=True (default) each node's @content-desc is also
        unioned in — Personal-details values live in EditTexts (and some Compose
        fields expose the typed value only via @content-desc), so a TextView-only
        scrape can never see them: this is the read VALUE-PRESENCE asserts against.

        Set include_content_desc=False for a TEXT-only read. On the redesigned
        Compose surfaces EVERY node emits a default @content-desc of the literal
        string 'null' (a framework artifact, not data) — so a placeholder-leakage
        scan must read node TEXT only, or it would flag that 'null' artifact as PII
        leakage on a screen that actually renders correct values."""
        attrs = ("text", "content-desc") if include_content_desc else ("text",)
        out = []
        for el in self.driver.find_elements(*self._VALUE_NODES):
            for attr in attrs:
                try:
                    v = el.get_attribute(attr)
                except Exception:
                    v = None
                if v and v.strip():
                    out.append(v)
        return out

    def screen_shows_value(self, value: str) -> bool:
        """True if `value` appears (case-insensitively, trimmed) inside any rendered
        value node — TextView OR editable input (EditText). Used to assert the
        profile renders the fixture's EXACT first name / email — a value read, not a
        presence read of a label. Editable fields hold their value in @text /
        @content-desc, which a TextView-only scrape misses."""
        needle = (value or "").strip().lower()
        if not needle:
            return False
        return any(needle in (t or "").strip().lower() for t in self.value_texts())

    def wait_for_value(self, value: str, timeout=STATE_PROBE_WAIT) -> bool:
        """Poll until `value` is rendered in any value node, or timeout. The
        Personal-details EditText fields hydrate from a store/network fetch AFTER
        the static labels render, so on a slow emulator (1-3s RTT) the value can be
        absent the instant the labelled surface first appears. Explicit wait instead
        of racing a single scrape."""
        from selenium.webdriver.support.ui import WebDriverWait
        from config.settings import POLL_INTERVAL
        try:
            return WebDriverWait(self.driver, timeout, poll_frequency=POLL_INTERVAL).until(
                lambda _d: self.screen_shows_value(value)
            )
        except Exception:
            return False

    @staticmethod
    def _bounds(el):
        """Parse an element's @bounds into (x1, y1, x2, y2), or None."""
        import re
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
        return tuple(int(m.group(i)) for i in (1, 2, 3, 4)) if m else None

    def current_plan_tier(self) -> str | None:
        """Return the account's CURRENT subscription/plan tier — the tier the user
        is actually on — or None if it can't be determined with confidence.

        HARDENED (P1-02): the tier is returned ONLY via a positional association
        with the 'Current plan' marker, never by guessing a tier-name TextView.
        The pricing-plans screen lays the three tier names out as a horizontal tab
        row (crawl-verified bounds on emulator-5554: Lite x≈202-272, Regular
        x≈597-743, Plus x≈1001-1085, all at y≈395-445) and renders a single
        'Current plan' marker BELOW the selected tab (x≈499-781), horizontally
        centred under the active tier. So the current tier is the tier-tab whose
        x-span the marker's horizontal centre falls within (nearest by centre as a
        tie-break).

        The earlier shared-ancestor XPath was WRONG: every tier and the marker
        share the one scroll container, so it matched the root and returned the
        first tier in iteration order ('Lite') regardless of which tab was active.
        Likewise the old "any known tier text present" fallback would return a tier
        the user is NOT on. With no marker, or no tier-tab the marker aligns to,
        we return None rather than guess.

        Matching is constrained to KNOWN_PLAN_TIERS (crawl-verified names only);
        the caller still validates non-empty / no-placeholder."""
        markers = self.driver.find_elements(*self.CURRENT_PLAN_MARKER)
        if not markers:
            return None
        mb = self._bounds(markers[0])
        if not mb:
            return None
        marker_cx = (mb[0] + mb[2]) / 2

        # Collect on-screen tier tabs with their x-spans.
        tabs = []
        for tier in self.KNOWN_PLAN_TIERS:
            for el in self.driver.find_elements(AppiumBy.XPATH, "//*[@text='" + tier + "']"):
                b = self._bounds(el)
                if b:
                    tabs.append((tier, b[0], b[2]))
        if not tabs:
            return None
        # 1) The tab whose x-span actually contains the marker's centre.
        for tier, x1, x2 in tabs:
            if x1 <= marker_cx <= x2:
                return tier
        # 2) Else the tab whose centre is closest to the marker's centre.
        tier, _, _ = min(tabs, key=lambda t: abs((t[1] + t[2]) / 2 - marker_cx))
        return tier

    def current_monthly_fee(self) -> str | None:
        """Return the account's monthly subscription fee as a normalised dollar
        string (e.g. '$5.50'), or None if no well-formed fee figure is rendered.

        The fee is co-located with the plan/fee copy on the Plans / Plans-and-fees
        surface ("from $5.50 / month"). We read the dollar amount that sits next to
        the per-month / plan-fee copy: scan value nodes whose text contains a '$'
        amount AND a per-month marker ('month'/'/mo'/'/ month'), then fall back to
        the dollar amount adjacent to a 'PLAN'/'Pricing plan'/'plan fee' label.
        Returns the EXACT rendered amount (normalised to '$N.NN') so callers can
        assert the precise tier fee, not mere presence of a dollar sign."""
        import re
        fee_re = re.compile(self._FEE_DOLLAR_RE)

        def _norm(m: str) -> str:
            return "$" + m.lstrip("$").strip()

        # 1) A dollar amount on a node that also carries a per-month marker.
        month_markers = ("/ month", "/month", "/mo", "per month", "a month", "month")
        for t in self.value_texts():
            low = (t or "").lower()
            if any(mm in low for mm in month_markers):
                m = fee_re.search(t)
                if m:
                    return _norm(m.group(0))
        # 2) A dollar amount adjacent to a plan/fee label (same node text).
        fee_markers = ("plan", "fee", "subscription")
        for t in self.value_texts():
            low = (t or "").lower()
            if any(fm in low for fm in fee_markers):
                m = fee_re.search(t)
                if m:
                    return _norm(m.group(0))
        return None

    def close(self):
        """Tap the top-right header close (X). Its pixel bounds differ per device,
        so target the right-most clickable in the top ~20% of the screen rather
        than hardcoding coordinates; fall back to Back if none is found."""
        import re
        height = self.driver.get_window_size()["height"]
        best = None
        for el in self.driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
            if m and int(m.group(2)) < height * 0.2:
                x1 = int(m.group(1))
                if best is None or x1 > best[0]:
                    best = (x1, el)
        if best:
            best[1].click()
        else:
            self.go_back()

    def get_notification_count(self) -> str:
        return self.get_text(self.NOTIFICATION_BADGE)

    def get_app_version(self) -> str:
        self.scroll_down()
        return self.get_text(self.APP_VERSION)

    # ---- navigation helpers (scroll-safe: lower items recycle off-screen) ----
    def _tap_item(self, label: str, locator):
        """Scroll the named settings row into view (it may be below the fold) then
        tap it. Settings is a Compose lazy column, so off-screen rows aren't in the
        DOM until scrolled in."""
        if not self.is_present_now(locator):
            try:
                self.scroll_to_text(label)
            except Exception:
                pass
        self.click(locator)

    def tap_log_out(self):
        self._tap_item("Log out", self.LOG_OUT)

    def tap_personal_details(self):
        self._tap_item("Personal details", self.PERSONAL_DETAILS)

    def tap_security_privacy(self):
        self._tap_item("Security and privacy", self.SECURITY_PRIVACY)

    def tap_funding_account(self):
        self._tap_item("Funding account", self.FUNDING_ACCOUNT)

    def tap_plans_and_fees(self):
        self._tap_item("Plans and fees", self.PLANS_AND_FEES)

    def tap_notifications_inbox(self):
        self._tap_item("Notifications inbox", self.NOTIFICATIONS_INBOX)

    def tap_manage_notifications(self):
        self._tap_item("Manage notifications", self.MANAGE_NOTIFICATIONS)

    def tap_accounts_financial_insights(self):
        self._tap_item("Accounts for financial insights", self.ACCOUNTS_FINANCIAL_INSIGHTS)

    def tap_manage_round_ups(self):
        self._tap_item("Manage Round-Ups", self.MANAGE_ROUND_UPS)

    def tap_refer_a_friend(self):
        self._tap_item("Refer a friend", self.REFER_A_FRIEND)

    def tap_get_support(self):
        self._tap_item("Get support", self.GET_SUPPORT)

    def tap_our_terms(self):
        self._tap_item("Our terms", self.OUR_TERMS)

    def tap_statements_reports(self):
        self._tap_item("Statements and reports", self.STATEMENTS_REPORTS)

    # ---- toggles (notification preferences etc.) ----
    def get_switches(self):
        """All Switch widgets currently on screen."""
        return self.driver.find_elements(*self.SWITCHES)

    def get_real_toggles(self):
        """The genuine preference toggles ONLY (verified on notifications_settings).

        `SWITCHES` over-matches: on most screens EVERY clickable View reports
        `@checked='false'`, so it returns ~15 false positives that are really
        navigation rows, not toggles (qa_locator_reference.md "Cross-cutting
        facts"). The REAL toggles on the Notifications screen are custom checkable
        Views pinned to the right edge (bounds x-start ~901, narrow ~137px wide).
        Filter to those so callers tap an actual toggle, never a navigation row
        that would carry them off-screen.

        Returns native android.widget.Switch elements as-is (always genuine), plus
        right-edge checkable Views. Falls back to the raw SWITCHES list only if the
        geometric filter finds nothing (so behaviour never silently regresses)."""
        import re
        width = self.driver.get_window_size()["width"]
        real, native = [], []
        for el in self.driver.find_elements(*self.SWITCHES):
            try:
                cls = el.get_attribute("className") or ""
                if cls.endswith("Switch"):
                    native.append(el)
                    continue
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", el.get_attribute("bounds") or "")
                if not m:
                    continue
                x1, x2 = int(m.group(1)), int(m.group(3))
                # Right-aligned (starts past ~80% of width) and narrow (a toggle,
                # not a full-width row). Verified: real toggles start at x=901 on a
                # 1080-wide device (~83%), width ~137px.
                if x1 > width * 0.78 and (x2 - x1) < width * 0.30:
                    real.append(el)
            except Exception:
                continue
        if native or real:
            return native + real
        # No geometric match — return the raw list rather than hide a real toggle.
        return self.driver.find_elements(*self.SWITCHES)

    def switch_state(self, el) -> bool:
        """True if a Switch element is currently on/checked."""
        return (el.get_attribute("checked") or "").lower() == "true"

    # ---- logout confirmation (used WITHOUT committing the logout) ----
    LOGOUT_CONFIRM_DIALOG = (AppiumBy.XPATH,
        "//*[contains(@text,'Log out') or contains(@text,'log out') or contains(@text,'Are you sure')]")

    def logout_prompt_shown(self, timeout=STATE_PROBE_WAIT) -> bool:
        """After tapping Log out, a confirmation prompt should appear before the
        session actually ends. Detect it by a clickable 'Cancel'/'No' alongside a
        confirm affordance, or 'Are you sure' copy — without committing."""
        cancel = self._first_present(("Cancel", "No", "Not now"))
        confirm = self._first_present(("Yes", "Confirm"))
        if cancel is not None and confirm is not None:
            return True
        return self.is_visible(self.LOGOUT_CONFIRM_DIALOG, timeout=timeout)

    def _first_present(self, words):
        """Return a locator for the first of `words` that is on screen right now
        as a clickable control, else None."""
        for w in words:
            loc = (AppiumBy.XPATH,
                   f"//android.view.View[@clickable='true'][.//android.widget.TextView[@text='{w}']]")
            if self.is_present_now(loc):
                return loc
            loc_btn = (AppiumBy.XPATH, f"//*[@text='{w}']")
            if self.is_present_now(loc_btn):
                return loc_btn
        return None

    def cancel_logout(self) -> bool:
        """Dismiss the logout confirmation WITHOUT logging out. Returns True if a
        dismiss affordance was found and tapped. Keeps the shared session alive for
        sibling tests. Falls back to Back if no explicit Cancel/No is present."""
        loc = self._first_present(("Cancel", "No", "Not now"))
        if loc is not None:
            self.click(loc)
            return True
        self.go_back()
        return False
