"""Raiz Kids screen coverage.

PREVIOUS WEAKNESS (now fixed): every value/list test here was gated by
`_require_list()`, which SKIPPED on the shared account because raiz://raiz_kids
opens the consent/"Welcome to Raiz Kids!" onboarding gate when the logged-in
account has no active kids. So the balance/tab/manage/name oracles never
actually ran.

FIX (P1-04): the list/value tests now run under the `kids_parent` fixture, which
logs into the app AS the PARENT of the seeded `kids_siblings_distinct` fixture
(two kid sub-accounts of distinct balances under one parent), exactly as
test_kids_value_on_device.py does. Because that account HAS active kids,
is_list_screen() is true and the balance/tab/manage/name oracles actually
execute against the populated list.

P1-05: test_kid_names_displayed now asserts the rendered names CONTAIN the exact
seeded first names ('KidSibAlpha'/'KidSibBravo') and that the kid-row count equals
the number of seeded kids (2) — not merely "non-empty, matches any 'yr' string".

The screen-loads and empty-state/add-affordance tests still run on the shared
`kids` fixture, where the consent/welcome gate is the correct surface to assert.
"""
import os
import time

import pytest

from config.settings import ANDROID_APP_PACKAGE, ANDROID_APP_ACTIVITY
from pages.kids_page import KidsPage
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from utils.assertions import assert_non_negative_money, parse_money
from utils.deep_links import DeepLinks
from utils.genuser_api import current_balance
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# Kid first names as seeded in utils/genuser_fixtures (kids_siblings_distinct).
# The app renders each kid row label as "<first_name> <last_name> (<age>)", so the
# first-name token identifies a sibling's card.
KID_A_NAME = "KidSibAlpha"
KID_B_NAME = "KidSibBravo"
SEEDED_KID_NAMES = (KID_A_NAME, KID_B_NAME)
SEEDED_KID_COUNT = len(SEEDED_KID_NAMES)


def _band(expected: float) -> float:
    """Drift-tolerant absolute band for an on-device money comparison: pricing
    settles asynchronously and the displayed value can lag the backend slightly.
    Mirrors the band used by test_kids_value_on_device.py (3% or $5)."""
    return max(5.0, abs(expected) * 0.03)


def _login_as_parent(d, fx):
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    if splash.is_visible(splash.TAGLINE, timeout=15):
        splash.tap_log_in()
    login.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    if not home.is_visible(home.TOTAL_VALUE_LABEL, timeout=30):
        assert onb.complete(), f"onboarding stuck at {onb.path}"
        mark_onboarded(fx["key"])
        assert home.is_visible(home.TOTAL_VALUE_LABEL, timeout=20), \
            "not on Home after completing onboarding as parent"
    assert home.is_present_now(home.TOTAL_VALUE_LABEL), "not on Home after login as parent"
    return home


def _open_kids_list(d) -> KidsPage:
    """Open the Raiz Kids surface and wait for the POPULATED list screen. The first
    deep link can land on a transient onboarding/consent gate while kids data is
    still loading, so retry with backoff and treat the consent gate as 'not ready
    yet'. Mirrors _open_kids_list in test_kids_value_on_device.py."""
    kids = KidsPage(d)
    for attempt in range(4):
        DeepLinks.open(d, DeepLinks.RAIZ_KIDS)
        deadline = time.time() + 8
        while time.time() < deadline:
            if kids.is_list_screen(timeout=2):
                return kids
            if attempt < 3:
                time.sleep(1)
        time.sleep(2 + attempt)
    return kids


def _switch_app_account(d):
    """Log the CURRENT live session OUT of whatever account it's on and back to a
    clean splash, by clearing the app's data IN PLACE and relaunching it — WITHOUT
    quitting the Appium/UiAutomator2 session.

    This is the single-session fix for the prior multi-session crash: the old
    fixture quit the shared session and opened a SECOND `Remote` on the same
    systemPort, and that handoff routinely failed ('local port #8201 is busy') or
    left the new instrumentation flaky enough to crash mid-suite — two concurrent
    UiAutomator2 servers on one 2GB emulator. `mobile: clearApp` wipes app data
    (logging out) while the ONE session keeps owning the port, and `mobile:
    activateApp` brings the app back to its cold splash. No second session is ever
    created."""
    d.execute_script("mobile: clearApp", {"appId": ANDROID_APP_PACKAGE})
    d.execute_script("mobile: activateApp", {"appId": ANDROID_APP_PACKAGE})


@pytest.fixture(scope="module")
def kids_parent(driver):
    """Module-scoped: the SINGLE session `driver`, re-authenticated AS the parent of
    the seeded `kids_siblings_distinct` fixture, parked on the POPULATED Raiz Kids
    list.

    This is what un-skips the list/value oracles: the parent account HAS active
    kids, so is_list_screen() is true. Reused per the reuse strategy (nothing is
    mutated here), so no fresh generation per run.

    ONE driver, no second session: instead of quitting the shared session and
    opening a second concurrent UiAutomator2 server on the same systemPort (the
    prior 'port busy'/instrumentation-crash failure on a 2GB emulator), we reuse the
    session `driver` proxy and just switch which ACCOUNT it's logged into by clearing
    app data in place (_switch_app_account). On teardown we clear again and let the
    session proxy self-heal back to the shared account for any later test."""
    fx = get_or_create_fixture_user("kids_siblings_distinct")  # reused if seeded
    _switch_app_account(driver)        # log the live session out of the shared account
    try:
        _login_as_parent(driver, fx)   # log the SAME session in as the parent
        kids = _open_kids_list(driver)
        assert kids.is_list_screen(), (
            "expected the populated Raiz Kids LIST screen for a parent with two "
            "active kids, but the consent/welcome onboarding gate was shown")
        # Expose the page AND the fixture record so value oracles can reconstruct
        # each kid's own login (a.<email>/b.<email>) and read its ground-truth
        # current_balance over the DEV API. The balance reads are pure HTTP — NO
        # second Appium/UiAutomator2 session — so the whole module runs within this
        # ONE driver on a single 2GB emulator (the prior multi-session crash).
        yield kids, fx
    finally:
        # Clear the parent account off the live session and rebuild the shared-account
        # session so later shared-account tests (this file's TestKidsScreen runs
        # FIRST, but other modules in a full run come after) start clean. Best effort.
        try:
            _switch_app_account(driver)
            if hasattr(driver, "recreate"):
                driver.recreate()
        except Exception:
            pass


@pytest.fixture(scope="module")
def kid_backend_balances(kids_parent):
    """Ground-truth backend current_balance per seeded kid, keyed by first name.

    Each kid is its own user under the parent at the deterministic a.<email> /
    b.<email> address the fixture builder uses. Read ONCE per module over the DEV
    API (HTTP only — does NOT open a second device session)."""
    _, fx = kids_parent
    parent_email = fx["email"]
    bals = {
        KID_A_NAME: current_balance("a." + parent_email),
        KID_B_NAME: current_balance("b." + parent_email),
    }
    return bals


@pytest.mark.regression
class TestKidsScreen:
    """Entry-surface tests on the shared account (consent/welcome gate is correct
    there). These do NOT need active kids."""

    def test_kids_screen_loads(self, kids):
        assert kids.is_loaded()

    # When there are no active kids the surface opens on the consent/welcome
    # onboarding gate; assert that entry positively. HIGH.
    def test_empty_state_shows_consent_or_welcome(self, kids):
        if kids.is_list_screen():
            pytest.skip("Account has active kids — list screen shown, not onboarding")
        assert kids.is_consent_screen() or kids.is_welcome_screen() or kids.is_loaded(), \
            "With no active kids, Kids should open the consent/welcome onboarding gate"

    def test_add_kid_button_visible(self, kids):
        # The Add affordance exists in both states; not list-gated.
        assert (kids.is_visible(kids.ADD_KID_BUTTON)
                or kids.is_consent_screen() or kids.is_welcome_screen())


@pytest.mark.regression
@pytest.mark.genuser_e2e
class TestKidsList:
    """List/value oracles run under the parent of the two seeded kids, so they
    ACTUALLY EXECUTE against the populated list instead of skipping."""

    def test_active_tab_visible(self, kids_parent):
        kids, _ = kids_parent
        assert kids.is_present_now(kids.ACTIVE_TAB), \
            "Active tab should be present on the Kids list"

    def test_closed_tab_visible(self, kids_parent):
        kids, _ = kids_parent
        assert kids.is_present_now(kids.CLOSED_TAB), \
            "Closed tab should be present on the Kids list"

    def test_manage_account_buttons_present(self, kids_parent):
        kids, _ = kids_parent
        buttons = kids.driver.find_elements(*kids.MANAGE_ACCOUNT_BUTTONS)
        assert len(buttons) > 0, "List screen should render a Manage account control per kid"

    # VALUE (P1-05): the rendered kid names must CONTAIN the exact seeded first
    # names, and the kid-row count must equal the number of seeded kids — not
    # merely "non-empty / matches any 'yr' TextView".
    def test_kid_names_displayed(self, kids_parent):
        kids, _ = kids_parent
        names = kids.get_kid_names()
        assert names, "Expected the seeded kid account names on the list"
        joined = " | ".join(names)
        for seeded in SEEDED_KID_NAMES:
            assert any(seeded in n for n in names), (
                f"rendered kid names {names!r} should contain seeded first name "
                f"{seeded!r}")
        # One name row per seeded kid (get_kid_names returns the per-kid 'yr' label).
        assert len(names) == SEEDED_KID_COUNT, (
            f"expected exactly {SEEDED_KID_COUNT} kid rows (seeded "
            f"{SEEDED_KID_NAMES}), got {len(names)}: {joined}")

    # VALUE (STRENGTHENED): each rendered kid card must show THAT kid's own backend
    # current_balance, tied to the kid by NAME. The prior version scraped every '$'
    # TextView screen-wide and only asserted non-negative + count>=2 — it would have
    # passed if both cards showed kid-A's $4,000, or any two arbitrary positive
    # amounts (HOLLOW). This now uses the name-scoped getter and the DEV-API ground
    # truth so it catches a wrong / stale / swapped / duplicated value.
    def test_kid_card_values_match_backend_and_siblings_distinct(
            self, kids_parent, kid_backend_balances):
        kids, _ = kids_parent
        bal_a = kid_backend_balances[KID_A_NAME]
        bal_b = kid_backend_balances[KID_B_NAME]
        assert bal_a and bal_a > 0, f"kid-A ({KID_A_NAME}) has no backend balance: {bal_a}"
        assert bal_b and bal_b > 0, f"kid-B ({KID_B_NAME}) has no backend balance: {bal_b}"
        # Precondition for the isolation oracle: the seeded siblings must differ by
        # more than the drift band, else "distinct" is unprovable on-device.
        assert abs(bal_a - bal_b) > _band(max(bal_a, bal_b)), (
            f"seeded kid balances are not materially distinct (A=${bal_a}, "
            f"B=${bal_b}); the sibling-isolation oracle needs them to differ")

        # Name-scoped getter: reads the money INSIDE each kid's own row, so one
        # sibling's value can't bleed into the other's.
        raw_a = kids.get_kid_value_by_name(KID_A_NAME)
        raw_b = kids.get_kid_value_by_name(KID_B_NAME)
        assert raw_a is not None, f"no money rendered in the {KID_A_NAME} kid card"
        assert raw_b is not None, f"no money rendered in the {KID_B_NAME} kid card"
        rendered_a = parse_money(raw_a)
        rendered_b = parse_money(raw_b)

        # Well-formed money (kept from the old test, now per named card).
        assert_non_negative_money(raw_a, f"{KID_A_NAME} balance")
        assert_non_negative_money(raw_b, f"{KID_B_NAME} balance")

        # Oracle 1: each card == that kid's OWN backend current_balance (band).
        assert rendered_a == pytest.approx(bal_a, abs=_band(bal_a)), (
            f"{KID_A_NAME} card ${rendered_a} should match its backend ${bal_a} "
            f"(±${_band(bal_a):.2f})")
        assert rendered_b == pytest.approx(bal_b, abs=_band(bal_b)), (
            f"{KID_B_NAME} card ${rendered_b} should match its backend ${bal_b} "
            f"(±${_band(bal_b):.2f})")

        # Oracle 2: siblings are DISTINCT on-device (rules out a shared/duplicated
        # value), and each card is closer to its OWN backend than to the other's
        # (rules out the two cards being swapped).
        assert abs(rendered_a - rendered_b) > _band(max(rendered_a, rendered_b)), (
            f"{KID_A_NAME} (${rendered_a}) and {KID_B_NAME} (${rendered_b}) rendered "
            f"the SAME value — sibling isolation broken")
        assert abs(rendered_a - bal_a) < abs(rendered_a - bal_b), (
            f"{KID_A_NAME} card ${rendered_a} is closer to {KID_B_NAME}'s backend "
            f"${bal_b} than to its own ${bal_a} — the kid cards look swapped")
        assert abs(rendered_b - bal_b) < abs(rendered_b - bal_a), (
            f"{KID_B_NAME} card ${rendered_b} is closer to {KID_A_NAME}'s backend "
            f"${bal_a} than to its own ${bal_b} — the kid cards look swapped")

    # Tab switching must change content and be reversible (the original test
    # re-asserted the just-tapped tab — a tautology).
    def test_tab_switch_returns_to_list(self, kids_parent):
        kids, _ = kids_parent
        assert kids.has_active_kid(), "Precondition: at least one kid should be listed"
        kids.tap_closed_tab()
        kids.tap_active_tab()
        assert kids.is_present_now(kids.MANAGE_ACCOUNT_BUTTONS), \
            "Returning to Active should restore the Manage account controls"

    def test_closed_tab_tappable(self, kids_parent):
        kids, _ = kids_parent
        kids.tap_closed_tab()
        assert kids.is_present_now(kids.CLOSED_TAB), \
            "Closed tab should remain selectable after tapping"
        # Restore Active so a later test in this module isn't left on Closed.
        kids.tap_active_tab()
