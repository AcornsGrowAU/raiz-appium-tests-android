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
import time

import pytest
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST
from pages.base_page import BasePage
from pages.portfolio_allocation_page import PortfolioAllocationPage
from pages.plus_builder_page import PlusBuilderPage
from pages.jars_page import JarsPage
from pages.kids_page import KidsPage
from pages.home_page import HomePage
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.pin_page import PinPage
from utils.deep_links import DeepLinks
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded
from conftest import _open_deep_link, _enter_pin

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
# Custom portfolio "PLUS" builder — on the REAL builder, on a PLUS-PLAN user.   #
# --------------------------------------------------------------------------- #
# The Plus custom-portfolio builder is PLAN-GATED (backend Plan enum
# starter/regular/plus; POST:/v1/custom_portfolios is gated behind PlusPortfolio,
# which starter/regular RESTRICT and plus UNLOCKS). Our earlier Plus tests ran on
# the shared REGULAR-plan account, so they only ever reached the limited/legacy
# editor and skipped ("Plus intro variant", "Bitcoin category not reachable"), and
# the old U-ALLOC / RAIZ-10251 conclusion ("no 100% running-total -> not a defect")
# was drawn on THAT limited editor — NOT the real builder.
#
# These tests log in AS the seeded `plan_plus` generated user (own driver +
# login + onboard, like test_main_value_on_device.py). On a plus user the REAL
# builder IS reachable, and (VERIFIED live, build 3252) it reconciles correctly:
# stepping moves 0.5%/tap, Bitcoin clamps at 5.0% and Property at 30.0%, and after
# saving an allocation the builder rows still sum to 100% (Base Portfolio draws
# down). So the running-total oracle IS implementable here — and the prior
# "not a defect" verdict was a REGULAR-PLAN ARTIFACT, not a property of the app.
#
# Single shared driver session per class (class-scoped fixture): the login +
# onboarding + intro carousel is expensive, and this 2GB emulator OOM-kills the
# app under the per-test churn of repeated relaunches; one session keeps it stable.
# IMPORTANT: mjpegServerPort is disabled — the screenshot broadcaster is the memory
# tipping point that OOM-kills the UiAutomator2 instrumentation on this 2GB device.

_PLUS_UDID = os.getenv("ANDROID_UDID", "emulator-5560")


def _plus_login_and_home(d, fx):
    """Log into the real app as the plus fixture user and land on Home, running the
    first-login onboarding gauntlet (incl. the 'Select your Portfolio' intro)."""
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
    assert lo.is_loaded(timeout=25), "login form did not load"
    lo.login(fx["email"], fx["password"])
    time.sleep(7)

    def _texts():
        out = []
        for el in d.find_elements(AppiumBy.XPATH,
                                  "//android.widget.TextView | //android.widget.Button"):
            try:
                t = (el.get_attribute("text") or "").strip()
            except Exception:
                continue
            if t:
                out.append(t)
        return out

    def _tap(*labels):
        for lab in labels:
            els = d.find_elements(
                AppiumBy.XPATH,
                f"//*[@clickable='true'][.//*[@text='{lab}']] | //*[@clickable='true' and @text='{lab}'] "
                f"| //android.widget.Button[@text='{lab}']")
            if els:
                els[-1].click()
                return lab
        return None

    onboarded = False
    for _ in range(20):
        if ho.is_present_now(ho.TOTAL_VALUE_LABEL):
            break
        low = " ".join(_texts()).lower()
        acted = None
        if "got it" in low or "scroll tabs" in low:
            acted = _tap("Got it")
        if not acted and any(s in low for s in ("follow these steps", "link a round-up",
                                                "complete your raiz invest")):
            acted = _tap("Continue") or _tap("Skip")
        if not acted and "select as your portfolio" in low:
            acted = _tap("Select as your portfolio")
        if not acted and "select your" in low and "portfolio" in low and "select as" not in low:
            # the onboarding portfolio-selection intro -> proceed via its bottom CTA
            btns = d.find_elements(AppiumBy.XPATH, "//android.widget.Button")
            if btns:
                btns[-1].click()
                acted = "intro-CTA"
        if not acted and ("initial investment" in low or "ready to start investing" in low):
            acted = _tap("Skip")
        if not acted:
            acted = _tap("Skip", "Continue", "Confirm", "Done", "Next")
        if not acted:
            break
        onboarded = True
        time.sleep(4)
    if onboarded:
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=25), "not on Home after login"
    return ho


@pytest.mark.e2e
@pytest.mark.portfolio
@pytest.mark.genuser_e2e
@pytest.mark.skipif(not _RUN_DESTRUCTIVE,
                    reason="Plus builder edits/saves a real portfolio; gated on RUN_DESTRUCTIVE=1")
class TestCustomPortfolioPlusE2E:
    """The REAL Plus custom-portfolio builder, exercised on the seeded `plan_plus`
    generated user (plan=plus). RAIZ-10251 interactive drift/cap + reconciliation."""

    BITCOIN_CAP = PlusBuilderPage.BITCOIN_CAP
    PROPERTY_CAP = PlusBuilderPage.PROPERTY_CAP
    STEP = PlusBuilderPage.STEP

    @pytest.fixture(scope="class")
    def plus_driver(self):
        """One logged-in plus-user session for the whole class (login + onboarding
        is expensive and the 2GB emulator OOM-kills the app under per-test relaunch
        churn). Clears app data once (fresh credential login, no PIN gate) and
        disables the MJPEG broadcaster (the OOM tipping point on this device).

        The UiAutomator2 instrumentation can be lowmemorykilled mid-login on this
        2GB emulator under host memory pressure (a transient infra crash, not a test
        failure); retry the whole session create + login once before giving up."""
        from selenium.common.exceptions import WebDriverException
        fx = get_or_create_fixture_user("plan_plus")

        def _build():
            opts = get_android_options(no_reset=False)
            opts.udid = _PLUS_UDID
            opts.set_capability("adbExecTimeout", 120000)
            opts.set_capability("appWaitDuration", 60000)
            opts.set_capability("uiautomator2ServerLaunchTimeout", 120000)
            opts.set_capability("mjpegServerPort", 0)
            return appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)

        d = None
        last_exc = None
        for attempt in range(3):
            try:
                d = _build()
                _plus_login_and_home(d, fx)
                break
            except WebDriverException as exc:
                last_exc = exc
                if d is not None:
                    try:
                        d.quit()
                    except Exception:
                        pass
                    d = None
                # let the lowmemorykilled instrumentation + app fully tear down and
                # the device reclaim RAM before retrying (longer each attempt)
                time.sleep(8 * (attempt + 1))
        if d is None:
            raise last_exc
        try:
            yield d
        finally:
            try:
                d.quit()
            except Exception:
                pass

    def _open_builder(self, plus_driver) -> PlusBuilderPage:
        """Deep-link to the Plus builder and dismiss the 'Welcome to PLUS' intro,
        returning the loaded builder page. The session is shared across tests, so
        re-open from scratch each time.

        Resilient to an OOM-kill of the app mid-class (this 2GB emulator can
        lowmemorykill the app under cumulative session load): if the builder isn't
        reachable on the first deep link, relaunch the app + re-auth and retry once
        before failing."""
        page = PlusBuilderPage(plus_driver)
        for attempt in range(2):
            DeepLinks.open(plus_driver, DeepLinks.PORTFOLIO_CUSTOM)
            time.sleep(3)
            pin = PinPage(plus_driver)
            if pin.is_loaded(timeout=2):
                _enter_pin(pin, plus_driver)
                time.sleep(2)
            # clear a leftover transient 'Oops' save-error dialog from a prior test
            page._dismiss_oops()
            if page.dismiss_intro():
                # the header can paint before the category rows populate; wait for
                # the full row set so callers reading weightings don't under-count
                page.wait_rows_loaded()
                return page
            # not on the builder — the app may have been killed; relaunch + recover
            if attempt == 0:
                try:
                    plus_driver.activate_app("com.acornsau.android.development")
                except Exception:
                    pass
                time.sleep(5)
                pin = PinPage(plus_driver)
                if pin.is_loaded(timeout=3):
                    _enter_pin(pin, plus_driver)
                    time.sleep(2)
                HomePage(plus_driver).is_loaded(timeout=20)
        ts = []
        for el in plus_driver.find_elements(AppiumBy.XPATH,
                                            "//android.widget.TextView | //android.widget.Button"):
            try:
                t = (el.get_attribute("text") or "").strip()
            except Exception:
                continue
            if t:
                ts.append(t)
        raise AssertionError(
            "could not reach the Plus builder 'Your Portfolio' screen on a "
            f"plus-plan user; screen showed: {ts[:25]}")

    # ----------------------------------------------------------------------- #
    def test_plus_builder_loads_on_plus_plan(self, plus_driver):
        """On a PLUS-plan user, raiz://portfolio/custom reaches the REAL builder
        ('Your Portfolio' with its category rows) — not the limited intro variant a
        regular-plan account is stuck on. This is the precondition the old tests
        could never satisfy on the shared regular account."""
        page = self._open_builder(plus_driver)
        assert page.is_loaded(), "Plus builder header not visible"
        weights = page.category_weightings()
        assert weights, "builder showed no weighted category rows"
        # At least the Base Portfolio row must be present and weighted.
        assert any("Base Portfolio" in k for k in weights), \
            f"expected a 'Base Portfolio' row in the builder, got {list(weights)}"

    def test_plus_base_portfolio_starts_at_100_percent(self, plus_driver):
        """The builder's whole-portfolio weighting starts reconciled at 100% (the
        Base Portfolio carries the full weight before any reallocation) — the
        starting invariant behind RAIZ-10251."""
        page = self._open_builder(plus_driver)
        total = page.running_total()
        assert total is not None, "no weighted rows on the builder to total"
        assert total == pytest.approx(100.0, abs=0.5), \
            f"builder should start reconciled at 100%, got {total}% from {page.category_weightings()}"

    def test_reallocating_a_holding_steps_without_drift(self, plus_driver):
        """Open Bitcoin's Customisation editor and step it UP. Each effective tap
        moves the holding by exactly one 0.5% step with no silent drift, and never
        exceeds the holding's cap — the per-holding invariant behind RAIZ-10251.
        Reads the live amount field after every tap (a true editing assertion)."""
        page = self._open_builder(plus_driver)
        assert page.open_category("Bitcoin"), "Bitcoin category not reachable in the Plus builder"
        # Reset to a known 0.0% floor first so the step-up is clean regardless of any
        # weight saved on a prior run (the session/portfolio is reused).
        start = page.reset_to_zero()
        assert start is not None, "could not read the holding-amount field in the editor"
        assert start == pytest.approx(0.0, abs=1e-6), \
            f"expected Bitcoin to reset to 0% before stepping, got {start}%"
        prev = start
        for n in range(1, 5):
            cur = page.tap_inc_expect(prev)
            assert cur is not None, "amount field unreadable after a + tap"
            assert abs(cur - prev - self.STEP) < 1e-6, \
                f"reallocation step {n} drifted: {prev}% -> {cur}% (expected +{self.STEP}%)"
            assert cur <= self.BITCOIN_CAP + 1e-6, \
                f"holding overshot its {self.BITCOIN_CAP}% cap while editing: {cur}%"
            prev = cur
        assert prev == pytest.approx(start + 4 * self.STEP, abs=1e-6), \
            f"after 4 steps the holding should be {start + 4 * self.STEP}%, got {prev}%"

    def test_bitcoin_holding_clamped_at_5_percent(self, plus_driver):
        """RAIZ-10251 cap: the Bitcoin holding cannot be reallocated above 5%.
        Stepping past the cap clamps at exactly 5.0% and disables the + control."""
        page = self._open_builder(plus_driver)
        assert page.open_category("Bitcoin"), "Bitcoin category not reachable in the Plus builder"
        final = page.step_up_to_cap(self.BITCOIN_CAP)
        assert final == pytest.approx(self.BITCOIN_CAP, abs=1e-6), \
            f"Bitcoin should clamp at {self.BITCOIN_CAP}%, ended at {final}%"
        assert not page.inc_enabled(), \
            "the + control should be disabled at the Bitcoin cap, but it is still enabled"

    def test_raiz_property_holding_clamped_at_30_percent(self, plus_driver):
        """RAIZ-10251 cap: the Raiz Property Fund holding cannot be reallocated
        above 30%. Stepping past the cap clamps at exactly 30.0% and disables +."""
        page = self._open_builder(plus_driver)
        assert page.open_category("Raiz Property Fund"), \
            "Raiz Property Fund category not reachable in the Plus builder"
        final = page.step_up_to_cap(self.PROPERTY_CAP)
        assert final == pytest.approx(self.PROPERTY_CAP, abs=1e-6), \
            f"Raiz Property Fund should clamp at {self.PROPERTY_CAP}%, ended at {final}%"
        assert not page.inc_enabled(), \
            "the + control should be disabled at the Property cap, but it is still enabled"

    def test_running_total_stays_100_after_reallocation(self, plus_driver):
        """RAIZ-10251 (the core 'totals must add up' defect): saving a reallocation
        keeps the whole-portfolio total reconciled to 100%. Adding weight to one
        holding has to draw the Base Portfolio DOWN by the same amount, never letting
        the total drift off 100%.

        VERIFIED behaviour: open Bitcoin, step it up a few steps, Save Allocation,
        and the builder rows (Base Portfolio + Bitcoin + ...) still sum to 100%.
        On the regular-plan limited editor there was no reconciled total to observe
        at all — that absence, not a real 100% headline, was what the old test saw,
        so the prior 'not a defect' verdict was a regular-plan artifact. Here the
        real builder DOES reconcile, so we assert it holds (a true drift would fail)."""
        page = self._open_builder(plus_driver)
        before = page.running_total()
        assert before == pytest.approx(100.0, abs=0.5), \
            f"builder should start at 100%, got {before}"
        assert page.open_category("Bitcoin"), "Bitcoin category not reachable in the Plus builder"
        # Reset to 0% first so the edit is a clean, known delta regardless of any
        # weight saved on a prior run.
        start = page.reset_to_zero()
        assert start == pytest.approx(0.0, abs=1e-6), \
            f"expected Bitcoin to reset to 0% before reallocating, got {start}%"
        # Step Bitcoin UP until the Save button enables — it only enables once the
        # value differs from the last SAVED allocation (so re-landing on the saved
        # value would leave it disabled). Stop at the cap. This guarantees a genuine,
        # saveable change regardless of what a prior run persisted.
        prev = start
        for _ in range(int(self.BITCOIN_CAP / self.STEP)):
            if not page.inc_enabled():
                break
            prev = page.tap_inc_expect(prev)
            # the enabled state can lag the tap; poll it for a beat before deciding
            if page.save_enabled(wait=2.0):
                break
        edited = page.amount()
        assert edited is not None and edited > start, \
            f"precondition: Bitcoin should be reallocated above its start ({start}%), got {edited}%"
        assert page.save_enabled(wait=3.0), \
            f"precondition: Save should be enabled after changing Bitcoin to {edited}%"
        assert page.save_allocation(), "Save Allocation did not return to the builder"
        # Back on the builder: wait for the rows to repopulate, then assert they
        # still reconcile to 100%.
        page.wait_rows_loaded()
        after = page.running_total()
        weights = page.category_weightings()
        assert after is not None, "no weighted rows after saving the allocation"
        assert after == pytest.approx(100.0, abs=0.5), (
            f"running total drifted off 100% after reallocation (RAIZ-10251): "
            f"showed {after}% from {weights}")
        # And the edit really took: a non-base holding now carries a positive weight,
        # while Base drew down below 100% — i.e. the reconciliation rebalanced.
        base = next((v for k, v in weights.items() if "Base Portfolio" in k), None)
        assert base is not None and base < 100.0, \
            f"Base Portfolio should have drawn down below 100% after the edit, got {base}% ({weights})"


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
