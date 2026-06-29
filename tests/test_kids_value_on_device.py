"""
ON-DEVICE KID-RENDER VALUE validation with SIBLING ISOLATION (TC-03, P0).

Logs into the real app AS the PARENT of two seeded kids of DISTINCT balances,
opens the Raiz Kids list, and proves the rendered kid-card values are correct
*per kid* — not merely present. This targets the suite's known presence-vs-value
weakness: a screen-wide '$' scrape cannot tell two siblings apart, so a kid card
that rendered the WRONG sibling's balance (or a stale/duplicated value) would
sail through a presence check.

Oracle (what proves it passes):
  - a name-scoped getter returns kid-A's rendered value == kid-A's BACKEND balance
    (within a drift band) and that value != kid-B's,
  - the sum of the two rendered kid-card values == the sum of the two seeded
    backend balances (within a band).

Each kid is its OWN user (own login + own current_balance) under one parent. The
`kids_siblings_distinct` fixture seeds the parent at the stored (bare) email and
the kids at deterministic `a.<email>` / `b.<email>` addresses, so we read each
kid's ground-truth balance straight from the DEV API. Reused per the reuse
strategy (rich-ish priced holdings; nothing is mutated here), so no fresh
generation per run.

Standalone (manages its own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_kids_value_on_device.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.kids_page import KidsPage
from utils.assertions import parse_money
from utils.deep_links import DeepLinks
from utils.genuser_api import current_balance
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# Kid first names as seeded in the fixture (utils/genuser_fixtures
# kids_siblings_distinct). The app renders the kid row label as
# "<first_name> <last_name> (<age>)", so matching the first-name token is enough
# to scope a card to one sibling.
KID_A_NAME = "KidSibAlpha"
KID_B_NAME = "KidSibBravo"


def _band(expected: float) -> float:
    """Drift-tolerant absolute band for an on-device money comparison: market
    pricing settles asynchronously and the displayed value can lag the backend
    slightly. Mirrors the band used by the onboarding-balance E2E (3% or $5)."""
    return max(5.0, abs(expected) * 0.03)


def _login_as_parent(d, fx):
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    # Poll the splash up to 15s (was a 10s poll preceded by a blind 5s sleep at the
    # call site): same worst-case cold-start patience, but it exits as soon as the
    # tagline renders (commonly 1-3s) instead of always burning a fixed 5s first.
    if splash.is_visible(splash.TAGLINE, timeout=15):
        splash.tap_log_in()
    login.login(fx["email"], fx["password"])
    # Explicit wait for Home instead of a blind sleep: on a slow emulator
    # (~1-3s RTT) the login round-trip varies, so poll for Home up to LONG_WAIT.
    onb = OnboardingPage(d)
    if not home.is_visible(home.TOTAL_VALUE_LABEL, timeout=30):
        assert onb.complete(), f"onboarding stuck at {onb.path}"
        mark_onboarded(fx["key"])
        assert home.is_visible(home.TOTAL_VALUE_LABEL, timeout=20), \
            "not on Home after completing onboarding as parent"
    assert home.is_present_now(home.TOTAL_VALUE_LABEL), "not on Home after login as parent"
    return home


def _open_kids_list(d) -> KidsPage:
    """Open the Raiz Kids surface and wait for the POPULATED list screen (the
    parent has active kids, so the consent/welcome onboarding gate should NOT
    appear). The first deep link can land on a transient onboarding/consent gate
    while the kids data is still loading, so retry with backoff and treat the
    consent gate as 'not ready yet' rather than a final state."""
    kids = KidsPage(d)
    for attempt in range(4):
        DeepLinks.open(d, DeepLinks.RAIZ_KIDS)
        # Poll for the populated list; is_list_screen() already returns False on
        # the consent/welcome gate, so this naturally re-tries through a transient
        # gate instead of giving up on the first render.
        deadline = time.time() + 8
        while time.time() < deadline:
            if kids.is_list_screen(timeout=2):
                return kids
            # A parent WITH active kids still hits the identity-consent gate on a
            # freshly-cleared app; ACCEPT it (tap 'I consent') to advance to the
            # populated list rather than only waiting the gate out.
            kids.accept_consent(timeout=2)
            if attempt < 3:
                time.sleep(1)
        # Bail out of the inner loop and re-fire the deep link with more settle
        # time on later attempts.
        time.sleep(2 + attempt)
    return kids


def test_kid_card_values_match_seeded_and_siblings_distinct():
    fx = get_or_create_fixture_user("kids_siblings_distinct")  # reused if already seeded
    parent_email, key = fx["email"], fx["key"]
    kid_a_email = "a." + parent_email
    kid_b_email = "b." + parent_email

    # Backend ground truth: each kid is its own user with its own current_balance.
    bal_a = current_balance(kid_a_email)
    bal_b = current_balance(kid_b_email)
    print(f"  fixture '{key}' parent={parent_email} (reused={fx.get('reused')})")
    print(f"  backend balances: kid-A({kid_a_email})=${bal_a}  kid-B({kid_b_email})=${bal_b}")
    assert bal_a and bal_a > 0, f"kid-A has no backend balance: {bal_a}"
    assert bal_b and bal_b > 0, f"kid-B has no backend balance: {bal_b}"
    # Precondition for the isolation oracle: the two kids must actually differ by
    # more than the drift band, else "distinct" is unprovable on-device.
    assert abs(bal_a - bal_b) > _band(max(bal_a, bal_b)), (
        f"seeded kid balances are not materially distinct (A=${bal_a}, B=${bal_b}); "
        f"the sibling-isolation oracle needs them to differ")

    opts = get_android_options(no_reset=False)  # fresh app data: log in cleanly as the parent
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        # No blind post-create sleep: _login_as_parent polls the splash (up to 15s)
        # and the login form's fields are found via WebDriverWait, so cold-start is
        # absorbed by those existing polls rather than an unconditional fixed wait.
        home = _login_as_parent(d, fx)
        print(f"  on Home as {home.get_greeting()!r}")

        kids = _open_kids_list(d)
        assert kids.is_list_screen(), (
            "expected the populated Raiz Kids LIST screen for a parent with two "
            "active kids, but the consent/welcome onboarding gate was shown")

        names = kids.get_kid_names()
        print(f"  rendered kid names: {names}")

        # Name-scoped getters: each reads the money INSIDE that kid's own row, so
        # one sibling's value can't bleed into the other's.
        raw_a = kids.get_kid_value_by_name(KID_A_NAME)
        raw_b = kids.get_kid_value_by_name(KID_B_NAME)
        print(f"  rendered card values: kid-A={raw_a!r}  kid-B={raw_b!r}")
        assert raw_a is not None, f"no money rendered in the {KID_A_NAME} kid card"
        assert raw_b is not None, f"no money rendered in the {KID_B_NAME} kid card"

        rendered_a = parse_money(raw_a)
        rendered_b = parse_money(raw_b)

        # Oracle 1: kid-A's rendered value matches kid-A's BACKEND balance (band).
        assert rendered_a == pytest.approx(bal_a, abs=_band(bal_a)), (
            f"kid-A card ${rendered_a} should match kid-A backend ${bal_a} "
            f"(±${_band(bal_a):.2f})")
        # And kid-B's matches kid-B's backend (band) — confirms the getter didn't
        # just return the same row twice.
        assert rendered_b == pytest.approx(bal_b, abs=_band(bal_b)), (
            f"kid-B card ${rendered_b} should match kid-B backend ${bal_b} "
            f"(±${_band(bal_b):.2f})")

        # Oracle 2: siblings are DISTINCT on-device — kid-A's value != kid-B's.
        assert abs(rendered_a - rendered_b) > _band(max(rendered_a, rendered_b)), (
            f"kid-A (${rendered_a}) and kid-B (${rendered_b}) rendered the SAME "
            f"value — sibling isolation broken (a card showed the wrong/shared balance)")
        # And kid-A's rendered value is closer to kid-A's backend than to kid-B's
        # (rules out the cards being swapped).
        assert abs(rendered_a - bal_a) < abs(rendered_a - bal_b), (
            f"kid-A card ${rendered_a} is closer to kid-B's backend ${bal_b} than to "
            f"kid-A's ${bal_a} — the two kid cards look swapped")

        # Oracle 3: sum of the two rendered kid-card values == sum of the two seeded
        # backend balances (±band on the total).
        rendered_sum = rendered_a + rendered_b
        backend_sum = bal_a + bal_b
        assert rendered_sum == pytest.approx(backend_sum, abs=_band(backend_sum)), (
            f"sum of rendered kid cards ${rendered_sum} should equal the sum of "
            f"seeded balances ${backend_sum} (±${_band(backend_sum):.2f})")

        print(f"  PASS: kid-A ${rendered_a}=={bal_a} backend, kid-B ${rendered_b}=={bal_b} "
              f"backend, distinct, sum ${rendered_sum}=={backend_sum}")
    finally:
        try:
            d.quit()
        except Exception:
            pass
