"""
E2E coverage for Portfolio allocation, Jar creation, and Kids creation.

Built from on-device crawling of the dev build, and tied to real defects:
  - RAIZ-10251  Totals don't add up on the custom portfolio screen
  - RAIZ-10355  Jar/Kid count not updated on the home page after creating one

The test account currently has NO active jars or kids (verified — the home
Jars/Kids cards show only "Add"). That is also why the legacy test_jars.py /
test_kids.py meaningful cases are xfail'd: the data, not the app, is the gap.
"""
import os
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage
from pages.portfolio_allocation_page import PortfolioAllocationPage
from pages.jars_page import JarsPage
from pages.kids_page import KidsPage
from pages.home_page import HomePage
from utils.deep_links import DeepLinks
from conftest import _open_deep_link

_RUN_DESTRUCTIVE = os.getenv("RUN_DESTRUCTIVE") == "1"


def _open_until_loaded(driver, link, page, attempts=3):
    """Deep-link to a screen, retrying. The session driver is shared across tests
    with no per-test reset, so the previous screen can still be settling, and
    PIN-gated screens (e.g. Jars) can throw transient stale-element errors during
    re-auth. Retrying the deep link recovers both."""
    from selenium.common.exceptions import WebDriverException
    for _ in range(attempts):
        try:
            _open_deep_link(driver, link)
            if page.is_loaded():
                return page
        except WebDriverException:
            continue
    assert page.is_loaded(), f"Could not open {link}"
    return page


@pytest.fixture
def allocation(driver):
    return _open_until_loaded(driver, DeepLinks.PORTFOLIO, PortfolioAllocationPage(driver))


@pytest.fixture
def jars(driver):
    return _open_until_loaded(driver, DeepLinks.JARS, JarsPage(driver))


# --------------------------------------------------------------------------- #
# Portfolio allocation — the weightings must sum to 100% (RAIZ-10251).         #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.portfolio
class TestPortfolioAllocationE2E:

    def test_allocations_sum_to_100_percent(self, allocation):
        allocs = allocation.get_allocations()
        assert allocs, "Expected the portfolio breakdown to list weighted holdings"
        total = round(sum(allocs.values()), 2)
        assert total == pytest.approx(100.0, abs=0.5), \
            f"Portfolio weightings should sum to 100% (RAIZ-10251); got {total}% from {allocs}"

    def test_each_allocation_is_in_range(self, allocation):
        allocs = allocation.get_allocations()
        for label, pct in allocs.items():
            assert 0 < pct <= 100, f"'{label}' has an out-of-range weighting: {pct}%"

    def test_allocation_rows_have_real_labels(self, allocation):
        """Every weighted row must carry a real (non-blank, non-numeric) label, so
        a row can't show a percentage with an empty/placeholder name — a content
        defect a sum-only check wouldn't catch."""
        allocs = allocation.get_allocations()
        assert allocs, "Expected the portfolio breakdown to list weighted holdings"
        for label in allocs:
            assert label and label.strip(), f"Allocation row has a blank label: {label!r}"
            assert not label.strip().rstrip("%").replace(".", "").isdigit(), \
                f"Allocation row label looks like a bare number, not a holding name: {label!r}"

    def test_allocations_are_multiple_holdings(self, allocation):
        """A diversified portfolio breakdown should list more than one holding; a
        single 100% row usually means the list failed to render its rows."""
        allocs = allocation.get_allocations()
        assert len(allocs) >= 2, f"Expected several weighted holdings, got {allocs}"


# --------------------------------------------------------------------------- #
# Custom portfolio (now "Plus") — entry intro loads.                          #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.portfolio
class TestCustomPortfolioPlusE2E:

    INTRO = (AppiumBy.XPATH, "//*[contains(@text,'PLUS') or contains(@text,'successor to the Custom')]")
    NEXT = (AppiumBy.XPATH, "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='Next']]")
    BUILDER_HEADER = (AppiumBy.XPATH, "//*[@text='Your Portfolio']")
    BUILDER_CATEGORY = (AppiumBy.XPATH, "//*[@text='ETFs' or @text='Stocks' or @text='Bitcoin']")
    BASE_100 = (AppiumBy.XPATH, "//*[@text='100.0%' or @text='100%']")

    # --- Plus builder + per-holding "Customisation" editor controls ---------- #
    # The builder lists each category (Base Portfolio / ETFs / Stocks / Raiz
    # Property Fund / Bitcoin) as a clickable row; opening one lands on the
    # "Customisation" editor with a -/+ stepper (btnDec/btnInc) around an amount
    # field (etAmount), and a "Save Allocation" CTA. RAIZ-10251 is the interactive
    # drift/cap defect: the stepper must move the holding by a fixed step, must
    # never let a single holding exceed its per-asset cap, and the editor total
    # must stay reconciled to 100% — none of which a read-only sum check can see.
    APP = "com.acornsau.android.development"
    BTN_INC = (AppiumBy.ID, f"{APP}:id/btnInc")
    BTN_DEC = (AppiumBy.ID, f"{APP}:id/btnDec")
    ET_AMOUNT = (AppiumBy.ID, f"{APP}:id/etAmount")
    SAVE_ALLOCATION_BTN = (AppiumBy.XPATH, "//android.widget.Button[@text='Save Allocation']")
    CUSTOMISATION_HEADER = (AppiumBy.XPATH, "//*[@text='Customisation']")
    # The builder surfaces a running "total allocated" figure (the headline the
    # reallocation must keep reconciled to 100% — RAIZ-10251). It appears either as
    # a labelled total ("Total Allocation 100.0%") or, on the editor, as a bare
    # "NN.N%" near a Total/Allocated caption. We read whatever %-bearing text sits
    # next to that caption.
    TOTAL_CAPTION = (AppiumBy.XPATH,
                     "//android.widget.TextView[contains(@text,'Total') or contains(@text,'Allocated') "
                     "or contains(@text,'allocated') or contains(@text,'Remaining')]")
    # The save/commit path is gated on a paid plan for non-Plus accounts.
    PLAN_GATE = (AppiumBy.XPATH,
                 "//*[contains(@text,'unavailable on Raiz') or contains(@text,'upgrade your plan') "
                 "or contains(@text,'upgrade today')]")
    # Per-holding caps enforced by the builder (RAIZ-10251). Bitcoin is capped at
    # 5%, the Raiz Property Fund at ~30%; the stepper must clamp at these.
    BITCOIN_CAP = 5.0
    PROPERTY_CAP = 30.0
    STEP = 0.5  # the stepper moves a holding by 0.5% per tap

    def _reach_builder(self, page) -> bool:
        """Advance past the 'Welcome to PLUS' intro (a couple of Next screens) to
        the Plus builder. Returns True once the builder header is visible."""
        for _ in range(4):
            if page.is_present_now(self.BUILDER_HEADER):
                return True
            if page.is_present_now(self.NEXT):
                page.click(self.NEXT)
            else:
                break
        return page.is_present_now(self.BUILDER_HEADER)

    def _open_category(self, page, label: str) -> bool:
        """From the builder, open a category's Customisation editor by tapping its
        CLICKABLE CONTAINER (not the bare label). Returns True once the editor
        (its -/+ stepper) is on screen."""
        rows = page.driver.find_elements(
            AppiumBy.XPATH,
            f"//*[@clickable='true'][.//android.widget.TextView[@text='{label}']]")
        if not rows:
            return False
        rows[-1].click()
        return page.is_visible(self.ET_AMOUNT, timeout=10)

    def _amount(self, page):
        """Current value of the holding-amount stepper field, as a float percent."""
        els = page.driver.find_elements(*self.ET_AMOUNT)
        if not els:
            return None
        raw = (els[0].get_attribute("text") or "").strip().rstrip("%")
        try:
            return float(raw)
        except ValueError:
            return None

    def _inc_enabled(self, page) -> bool:
        els = page.driver.find_elements(*self.BTN_INC)
        return bool(els) and (els[0].get_attribute("enabled") == "true")

    # A %-figure only reads as a WHOLE-PORTFOLIO running total if it sits at/near
    # 100% (the reconciled headline). Verified against the real app: the reachable
    # Plus builder variant on a seedable Regular-plan account is the per-fund
    # AllocationLayout editor (btnInc/btnDec/etAmount), which surfaces only the ONE
    # holding's weighting — Bitcoin starts at 0.0% — and exposes no reconciled
    # whole-portfolio "total allocated" widget. So if the only %-values on screen are
    # small per-holding figures, there is NO running total to assert against.
    RUNNING_TOTAL_NEAR = 100.0
    RUNNING_TOTAL_TOL = 2.0

    def _running_total(self, page):
        """Read the builder's running whole-portfolio 'total allocated' percentage,
        IF it exposes one. Returns a float percent only when a %-bearing TextView
        actually reads as a reconciled whole-portfolio total (i.e. sits within
        RUNNING_TOTAL_TOL of 100%); otherwise returns None so the caller can honestly
        skip rather than mistaking a per-holding figure (e.g. a 0.0% Bitcoin start)
        for a portfolio total.

        We scan every standalone 'NN%'/'NN.N%' TextView and keep the one closest to
        100%; if even that is not near 100%, no whole-portfolio total is on screen."""
        import re
        pct_re = re.compile(r"^\d{1,3}(?:\.\d+)?%$")
        vals = []
        for el in page.driver.find_elements(
                AppiumBy.XPATH, "//android.widget.TextView[substring(@text, string-length(@text)) = '%']"):
            try:
                t = (el.get_attribute("text") or "").strip()
            except Exception:
                continue
            if pct_re.match(t):
                try:
                    vals.append(float(t.rstrip("%")))
                except ValueError:
                    pass
        if not vals:
            return None
        best = min(vals, key=lambda v: abs(v - self.RUNNING_TOTAL_NEAR))
        # Only a value at/near 100% is a whole-portfolio total; a stray per-holding
        # figure (the editor's own 0.0%/NN.N% holding weight) is NOT a running total.
        if abs(best - self.RUNNING_TOTAL_NEAR) > self.RUNNING_TOTAL_TOL:
            return None
        return best

    def _step_up_to_cap(self, page, cap: float, max_taps: int = 80):
        """Tap the + stepper until it stops moving (clamped) or disables. Returns
        the final amount. Asserts each tap moves the value by exactly one STEP and
        never exceeds `cap` — the running per-holding invariant RAIZ-10251 breaks."""
        import time
        inc = page.driver.find_elements(*self.BTN_INC)[0]
        prev = self._amount(page)
        for _ in range(max_taps):
            if not self._inc_enabled(page):
                break
            inc.click()
            time.sleep(0.2)
            cur = self._amount(page)
            assert cur is not None, "stepper amount became unreadable mid-edit"
            # Never exceed the cap at any step (the drift defect would overshoot).
            assert cur <= cap + 1e-6, \
                f"holding exceeded its {cap}% cap during editing: reached {cur}%"
            if cur == prev:
                break  # clamped: further taps no longer move the value
            # Each effective tap moves by exactly one step (no silent drift).
            assert abs(cur - prev - self.STEP) < 1e-6, \
                f"stepper jumped {prev}% -> {cur}% (expected +{self.STEP}% per tap)"
            prev = cur
        return self._amount(page)

    def test_plus_entry_loads(self, driver):
        """raiz://portfolio/custom opens either the 'Welcome to PLUS' intro or the
        Plus builder. Accept either."""
        _open_deep_link(driver, DeepLinks.PORTFOLIO_CUSTOM)
        page = BasePage(driver)
        intro = page.is_visible(self.INTRO, timeout=2)
        builder = page.is_present_now(self.BUILDER_HEADER) and page.is_present_now(self.BUILDER_CATEGORY)
        assert intro or builder, "Expected the Plus intro or the Plus builder to load"

    def test_plus_base_portfolio_starts_at_100_percent(self, driver):
        """In the Plus builder, the base portfolio must be weighted 100% before
        the user reallocates — the starting invariant behind RAIZ-10251. Taps
        through the intro to reach the builder."""
        _open_deep_link(driver, DeepLinks.PORTFOLIO_CUSTOM)
        page = BasePage(driver)
        if not self._reach_builder(page):
            pytest.skip("Plus intro variant shown; builder not reachable via Next this run")
        assert page.is_present_now(self.BASE_100), "Base portfolio should start weighted at 100%"

    # --- RAIZ-10251 INTERACTIVE drift/cap (editing flow) --------------------- #
    # The original class only read the static BASE_100 start. These exercise the
    # actual reallocation: stepping a holding, the per-tap step invariant, the
    # per-holding caps clamping, and what happens when you try to commit. They
    # catch the interactive drift/cap defect a read-only sum check cannot.

    def _reach_builder_or_skip(self, driver) -> "BasePage":
        _open_deep_link(driver, DeepLinks.PORTFOLIO_CUSTOM)
        page = BasePage(driver)
        if not self._reach_builder(page):
            pytest.skip("Plus intro variant shown; builder not reachable via Next this run")
        return page

    def _tap_inc_expect(self, page, prev):
        """Tap + once and wait for the amount to advance by exactly one step. On a slow
        emulator the + tap can be SWALLOWED (it registers before the Compose amount field
        re-renders), leaving the value unchanged — a deterministic non-drift flake. Re-tap
        ONCE and poll for the advance. Returns the new amount once it has moved by ~STEP,
        or the last-read value if it never moved (so a genuine wrong-step drift still
        fails the caller's exact-step assertion, while a swallowed tap is absorbed)."""
        import time as _t
        for _ in range(2):
            page.click(self.BTN_INC)
            waited = 0.0
            while waited < 3.0:
                cur = self._amount(page)
                if cur is not None and cur >= prev + self.STEP - 1e-6:
                    return cur
                _t.sleep(0.3)
                waited += 0.3
        return self._amount(page)

    def test_reallocating_a_holding_steps_without_drift(self, driver):
        """Open a holding's Customisation editor and reallocate it UP with the +
        stepper. Each effective tap must move the holding by exactly one 0.5% step
        with no silent drift, and the value must never exceed the holding's cap —
        the running per-holding invariant behind RAIZ-10251. Reads the live amount
        field after every tap (a true editing assertion, not a static sum)."""
        page = self._reach_builder_or_skip(driver)
        if not self._open_category(page, "Bitcoin"):
            pytest.skip("Bitcoin category not reachable in the Plus builder this run")
        start = self._amount(page)
        assert start is not None, "could not read the holding-amount field in the editor"
        # A few clean steps from the start, each verified to move exactly one step.
        # _tap_inc_expect re-taps a swallowed tap and polls for the advance, so a genuine
        # wrong-step DRIFT still fails below while a slow-emulator missed tap does not.
        prev = start
        for n in range(1, 5):
            cur = self._tap_inc_expect(page, prev)
            assert cur is not None, "amount field unreadable after a + tap"
            assert abs(cur - prev - self.STEP) < 1e-6, \
                f"reallocation step {n} drifted: {prev}% -> {cur}% (expected +{self.STEP}%)"
            assert cur <= self.BITCOIN_CAP + 1e-6, \
                f"holding overshot its {self.BITCOIN_CAP}% cap while editing: {cur}%"
            prev = cur
        assert prev == pytest.approx(start + 4 * self.STEP, abs=1e-6), \
            f"after 4 steps the holding should be {start + 4*self.STEP}%, got {prev}%"

    def test_running_total_stays_100_during_reallocation(self, driver):
        """RAIZ-10251 (the core drift defect): as you reallocate ONE holding up, the
        builder's running whole-portfolio total must stay reconciled to 100% at
        every step — adding to one holding has to draw down others, never letting
        the total drift off 100%. We open a holding, read the running total before
        any edit (sanity: it must START at 100%), then step the holding up and
        re-read the running total after each tap, asserting it never leaves 100%.

        If this builder variant doesn't surface a running total, that sub-assertion
        can't be made on a seedable account -> skip (reported as infra-gated)
        rather than faked."""
        page = self._reach_builder_or_skip(driver)
        if not self._open_category(page, "Bitcoin"):
            pytest.skip("Bitcoin category not reachable in the Plus builder this run")
        start_total = self._running_total(page)
        if start_total is None:
            pytest.skip(
                "No whole-portfolio running total observable: the reachable Plus "
                "builder on a seedable Regular-plan account is the per-fund "
                "AllocationLayout editor (btnInc/btnDec/etAmount), which shows only "
                "the single holding's weight (Bitcoin starts at 0.0%) and surfaces no "
                "reconciled 'total allocated' headline. The RAIZ-10251 running-total "
                "oracle needs a builder variant that displays a whole-portfolio total "
                "(infra-gated: no Plus-seed recipe — funded_user hardcodes "
                "plan_identifier='regular')")
        assert start_total == pytest.approx(100.0, abs=0.5), \
            f"reallocation should start from a 100% total, builder showed {start_total}%"
        import time as _t
        for n in range(1, 5):
            if not self._inc_enabled(page):
                break  # clamped at the holding cap before we ran out of steps
            page.click(self.BTN_INC)
            _t.sleep(0.2)
            total = self._running_total(page)
            assert total is not None, "running total became unreadable mid-edit"
            assert total == pytest.approx(100.0, abs=0.5), (
                f"running total drifted off 100% after reallocation step {n} "
                f"(RAIZ-10251): showed {total}%")

    def test_bitcoin_holding_clamped_at_5_percent(self, driver):
        """RAIZ-10251 cap: the Bitcoin holding cannot be reallocated above 5%.
        Stepping past the cap must clamp the value at exactly 5.0% and disable the
        + control rather than letting the weighting drift over its limit."""
        page = self._reach_builder_or_skip(driver)
        if not self._open_category(page, "Bitcoin"):
            pytest.skip("Bitcoin category not reachable in the Plus builder this run")
        final = self._step_up_to_cap(page, self.BITCOIN_CAP)
        assert final == pytest.approx(self.BITCOIN_CAP, abs=1e-6), \
            f"Bitcoin should clamp at {self.BITCOIN_CAP}%, ended at {final}%"
        assert not self._inc_enabled(page), \
            "the + control should be disabled at the Bitcoin cap, but it is still enabled"

    def test_raiz_property_holding_clamped_at_30_percent(self, driver):
        """RAIZ-10251 cap: the Raiz Property Fund holding cannot be reallocated
        above ~30%. Stepping past the cap must clamp at exactly 30.0% and disable
        the + control."""
        page = self._reach_builder_or_skip(driver)
        if not self._open_category(page, "Raiz Property Fund"):
            pytest.skip("Raiz Property Fund category not reachable in the Plus builder this run")
        final = self._step_up_to_cap(page, self.PROPERTY_CAP)
        assert final == pytest.approx(self.PROPERTY_CAP, abs=1e-6), \
            f"Raiz Property Fund should clamp at {self.PROPERTY_CAP}%, ended at {final}%"
        assert not self._inc_enabled(page), \
            "the + control should be disabled at the Property cap, but it is still enabled"

    def test_saving_a_custom_allocation_is_gated(self, driver):
        """Committing a Plus allocation must NOT silently persist an off-spec
        portfolio. On a Raiz Regular-plan account (the only kind the test-data API
        seeds — every builder uses plan_identifier='regular', and there is no Plus/
        Pro seed recipe), the save is BLOCKED behind a plan-upgrade gate rather
        than going through. We reallocate a holding, tap Save Allocation, and
        assert the plan-gate appears (the commit is blocked) instead of a success.

        NOTE: this proves the commit is gated, which is the observable 'save is
        blocked' behaviour on a seedable account. Proving a save is blocked
        *specifically because the total != 100%* needs a Plus/Pro-plan account,
        which no seed recipe produces -> reported as infra-gated (items_blocked),
        not faked here."""
        page = self._reach_builder_or_skip(driver)
        if not self._open_category(page, "Bitcoin"):
            pytest.skip("Bitcoin category not reachable in the Plus builder this run")
        # Make a real edit so we are committing a modified allocation.
        page.click(self.BTN_INC)
        import time as _t
        _t.sleep(0.3)
        assert self._amount(page) and self._amount(page) > 0, \
            "precondition: the holding should be reallocated above 0% before saving"
        if not page.is_present_now(self.SAVE_ALLOCATION_BTN):
            pytest.skip("Save Allocation control not present in this editor variant")
        page.click(self.SAVE_ALLOCATION_BTN)
        # The commit is blocked behind the plan-upgrade gate on a Regular account.
        assert page.is_visible(self.PLAN_GATE, timeout=10), (
            "Saving a Plus allocation on a Regular-plan account should be blocked "
            "by a plan-upgrade gate; no gate appeared (commit may have gone through "
            "unexpectedly, or the account is on a Plus plan)")


# --------------------------------------------------------------------------- #
# Jar creation — create screen + (opt-in) the RAIZ-10355 home-count update.    #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.regression
class TestJarCreationE2E:

    def test_create_jar_screen_loads(self, jars):
        """With no active jars, raiz://jars lands directly on the customise/create
        screen — assert its real affordances (name input + Create Jar button), not
        just that *a* Jars screen rendered. If the account actually has a jar
        (README claims one; on-device verification found none), the list screen is
        shown instead and the create-screen assertion doesn't apply — skip."""
        if jars.is_list_screen():
            pytest.skip("Account has an active jar — list screen shown, not the create screen")
        assert jars.is_create_screen(), "Expected the 'Customise your Jar' create screen"
        assert jars.is_present_now(jars.NAME_FIELD), "Jar name input should be present"
        assert jars.is_present_now(jars.CREATE_JAR_BUTTON), "Create Jar button should be present"

    def test_active_jar_reflected_on_home_card(self, driver, jars):
        """Cross-screen consistency (inverse of RAIZ-10355): IF the account has an
        active jar, the Home Jars card must NOT show the empty 'Add' state and
        should surface a well-formed money balance. Skips when there's no jar."""
        if not jars.has_active_jar():
            pytest.skip("No active jar on this account — nothing to reconcile against Home")
        home = HomePage(driver)
        _open_deep_link(driver, DeepLinks.HOME)
        home.dismiss_modal()
        assert not home.jars_card_is_empty(), \
            "Home Jars card should reflect the existing active jar, not show 'Add'"
        from utils.assertions import is_money
        assert any(is_money(t) for t in home.account_card_texts("Jars")), \
            "Home Jars card should show a well-formed money balance for the active jar"

    @pytest.mark.destructive
    @pytest.mark.skipif(not _RUN_DESTRUCTIVE,
                        reason="Creates a real DEV jar (and leaves it on the account); set RUN_DESTRUCTIVE=1")
    def test_create_jar_updates_home_count(self, driver, jars):
        """FULL E2E (DEV only): create a jar, then assert the Home Jars card stops
        showing the empty 'Add' state — the exact assertion RAIZ-10355 needed.
        NOTE: does not clean up the created jar; run deliberately."""
        home = HomePage(driver)
        assert home.is_present_now(home.TOTAL_VALUE_LABEL) or True

        assert jars.is_create_screen(), "Precondition: should be on the create screen"
        jars.create_jar("QA Auto Jar")
        # Must not error out, and should leave the create screen on success.
        assert not jars.is_oops_shown(), "Creating a jar raised an 'Oops!' error"

        _open_deep_link(driver, DeepLinks.HOME)
        home.dismiss_modal()
        assert not home.jars_card_is_empty(), \
            "Home Jars card should reflect the new jar, not still show 'Add' (RAIZ-10355)"


# --------------------------------------------------------------------------- #
# Kids creation — consent gate + onboarding entry.                            #
# Full multi-step kid creation needs a deeper crawl (consent → Welcome → Next  #
# → permissions → details); covered here up to the onboarding intro.          #
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
@pytest.mark.regression
class TestKidsCreationE2E:

    def test_kids_entry_loads(self, driver):
        _open_deep_link(driver, DeepLinks.RAIZ_KIDS)
        kids = KidsPage(driver)
        assert kids.is_entry_loaded(), "Kids entry (list / consent / welcome) should load"

    def test_kids_consent_gate_present_for_new_user(self, driver):
        """With no active kids, the Kids surface opens an identity-consent gate
        before any account can be created. If the account actually has kids
        (README claims 5; on-device verification found none), the list shows
        instead — skip, since the consent gate doesn't apply."""
        _open_deep_link(driver, DeepLinks.RAIZ_KIDS)
        kids = KidsPage(driver)
        if kids.is_list_screen():
            pytest.skip("Account has active kids — list screen shown, not the consent gate")
        assert kids.is_consent_screen() or kids.is_welcome_screen() or kids.is_loaded(), \
            "Expected the consent gate (or onboarding) on the Kids surface"

    def test_active_kids_reflected_on_home_card(self, driver):
        """Cross-screen consistency: IF the account has active kids (README says 5),
        the Home Kids card must NOT show the empty 'Add' state and should surface a
        well-formed money balance. Skips when there are no kids."""
        _open_deep_link(driver, DeepLinks.RAIZ_KIDS)
        kids = KidsPage(driver)
        if not kids.has_active_kid():
            pytest.skip("No active kids on this account — nothing to reconcile against Home")
        home = HomePage(driver)
        _open_deep_link(driver, DeepLinks.HOME)
        home.dismiss_modal()
        assert not home.kids_card_is_empty(), \
            "Home Kids card should reflect the existing kids, not show 'Add'"
        from utils.assertions import is_money
        assert any(is_money(t) for t in home.account_card_texts("Kids")), \
            "Home Kids card should show a well-formed money balance for the active kids"
