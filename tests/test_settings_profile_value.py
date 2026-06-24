"""
ON-DEVICE SETTINGS VALUE — profile identity + plan/subscription tier (TC-13, P2).

Converts the Settings area from PRESENCE to VALUE (the suite's #1 known weakness).
The existing Settings coverage asserts profile/plan SCREENS open and carry no
placeholder leakage; here we assert the rendered data is the LOGGED-IN user's REAL
values and that the plan tier is a genuine member of the known tier set.

Oracle (what proves it passes), logged in AS a generated fixture user:
  1. The personal-profile surface (raiz://profile/personal) renders the fixture's
     EXACT first name AND EXACT email address (value, not just a labelled field).
  2. The pricing-plans surface (raiz://plans) renders a plan/subscription tier that
     is NON-EMPTY and a member of the known valid set (SettingsPage.KNOWN_PLAN_TIERS)
     — never blank, 'null'/'undefined', or a '%s' placeholder. The fixture is seeded
     on the 'regular' plan, so the rendered tier is additionally asserted to be
     'Regular'.

Reuse strategy: the long-lived `presence_funded` fixture (utils.genuser_fixtures) —
an onboarded generated user with a known first name and a real Aggressive balance.
No fresh user is seeded per run.

Standalone (own driver; clears app data so login is deterministic — no PIN gate).
Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_settings_profile_value.py -v -s -o addopts=""
"""
import os
import re
import time

import pytest
from appium import webdriver as appium_webdriver

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST, STATE_PROBE_WAIT, DEFAULT_WAIT
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.settings_page import SettingsPage
from utils.deep_links import DeepLinks
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.settings]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# The first name the `presence_funded` fixture builder seeds (genuser_fixtures.py:
# with_balance_user(email, "PresFunded", ...)). If that builder's name ever
# changes, this constant must change with it — the test asserts the device renders
# exactly this value, so a drift here is a real test-data mismatch, not a flake.
FIXTURE_FIRST_NAME = "PresFunded"

# Strings that must never appear where a real value belongs (placeholder leakage).
_PLACEHOLDERS = ("null", "undefined", "%s", "%@", "{", "}", "NaN", "None", "[object")


def _wait_post_login(d, ho, timeout=30, poll=0.5):
    """Poll until the post-login transition settles on a terminal screen we can
    act on: either Home is loaded, or an onboarding screen is on-screen. Replaces
    a blind `time.sleep(7)` that under-waits on a slow emulator (1-3s RTT) and
    over-waits on a fast one. Returns 'home' or 'onboarding'; 'unknown' if neither
    appeared within the timeout (caller still asserts Home as the hard gate)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ho.is_loaded(timeout=1):
            return "home"
        # Any onboarding gate on screen (PDS/checklist/portfolio/initial-invest
        # all surface one of these affordances) means we can hand off to
        # onb.complete(); these keywords mirror the taps that complete() makes.
        src = (d.page_source or "").lower()
        if any(k in src for k in ("skip", "got it", "select as your portfolio",
                                  "i consent", "agree")):
            return "onboarding"
        time.sleep(poll)
    return "unknown"


def _login_and_home(d, fx):
    """Log into the real app as the fixture user and land on Home (running the
    first-login onboarding gauntlet only if the app isn't already on Home)."""
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
    # Wait for the login form itself rather than sleeping a fixed beat; the splash
    # can hand off slowly on a cold emulator.
    assert lo.is_loaded(timeout=20), "login form did not load"
    lo.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    state = _wait_post_login(d, ho)
    if state != "home" and not ho.is_loaded(timeout=2):
        assert onb.complete(), f"onboarding stuck: {onb.path}"
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=20), "not on Home after login"
    return ho


def _open(d, link, expect_locator, timeout=DEFAULT_WAIT):
    """Open a deep link and wait for an identifying element on the destination.

    Waits DEFAULT_WAIT (10s) by default, not the 2s STATE_PROBE_WAIT: a deep-link
    surface SWAP (e.g. profile -> plans back-to-back inside one session) can take
    several seconds to re-render on a busy emulator, and a 2s probe races it."""
    DeepLinks.open(d, link)
    page = SettingsPage(d)
    assert page.is_visible(expect_locator, timeout=timeout), \
        f"deep link {link} did not open its expected surface"
    return page


def test_profile_and_plan_tier_render_real_values():
    """Settings profile shows the fixture's exact first name + email, and the
    plan/subscription tier is a real member of the known valid set (not a
    placeholder)."""
    fx = get_or_create_fixture_user("presence_funded")
    expected_email = (fx["email"] or "").strip()
    assert expected_email and "@" in expected_email, \
        f"fixture user has no usable email: {fx!r}"

    opts = get_android_options(no_reset=False)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)

        # ---- 1) PROFILE identity: exact first name + exact email --------- #
        from appium.webdriver.common.appiumby import AppiumBy
        profile = _open(
            d, DeepLinks.PROFILE_PERSONAL,
            (AppiumBy.XPATH,
             "//*[contains(@text,'Personal') or contains(@text,'personal') "
             "or contains(@text,'Profile') or contains(@text,'Email') "
             "or contains(@text,'Name')]"),
        )
        # Personal-details field VALUES live inside EditText widgets, not plain
        # TextViews; value_texts() unions TextView + EditText (+ content-desc) so
        # the value reads below see what the user actually sees. visible_texts()
        # (TextView-only, i.e. the field labels) is kept only for the diagnostic
        # print so failures show the surrounding label set.
        # Wait for the editable fields to hydrate (they populate after labels on a
        # slow emulator) before scraping, so we don't race the value render.
        profile.wait_for_value(expected_email, timeout=DEFAULT_WAIT)
        labels = profile.visible_texts()
        texts = profile.value_texts()
        assert texts, "Personal details rendered no text at all"
        blob = " \n".join(texts)
        print(f"  profile labels: {labels!r}")
        print(f"  profile value texts: {texts!r}")

        # No placeholder leakage where real PII should be. Scan node TEXT only
        # (not @content-desc): the redesigned Compose profile emits a default
        # @content-desc of the literal 'null' on EVERY node, which is a framework
        # artifact, not leaked data — folding it in would false-flag a screen that
        # renders correct values. Genuine leakage (a field whose VALUE is 'null'/
        # '%s') still surfaces in the node text.
        for t in profile.value_texts(include_content_desc=False):
            for junk in _PLACEHOLDERS:
                assert junk not in t, f"Placeholder leakage on profile: {t!r}"

        # Exact email of the logged-in fixture user.
        assert profile.screen_shows_value(expected_email), (
            f"Personal details should render the fixture's exact email "
            f"{expected_email!r}; rendered texts: {texts!r}"
        )
        # The email must also be well-formed where it is rendered (no truncation
        # to a bare label / no '@'-less echo).
        found_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", blob)
        assert any(e.lower() == expected_email.lower() for e in found_emails), (
            f"profile email render is malformed: expected {expected_email!r}, "
            f"found {found_emails!r}"
        )

        # Exact first name of the logged-in fixture user.
        assert profile.screen_shows_value(FIXTURE_FIRST_NAME), (
            f"Personal details should render the fixture's exact first name "
            f"{FIXTURE_FIRST_NAME!r}; rendered texts: {texts!r}"
        )
        print(f"  PASS: profile shows first_name={FIXTURE_FIRST_NAME!r} "
              f"and email={expected_email!r}")

        # ---- 2) PLAN / subscription tier: real value in known set ------- #
        plans = _open(
            d, DeepLinks.PLANS,
            (AppiumBy.XPATH,
             "//*[contains(@text,'Plan') or contains(@text,'plan')]"),
        )
        tier = plans.current_plan_tier()
        print(f"  plan tier rendered: {tier!r}")
        assert tier is not None, (
            "Plans screen rendered no recognisable plan tier "
            f"(expected one of {SettingsPage.KNOWN_PLAN_TIERS}); "
            f"texts: {plans.visible_texts()!r}"
        )
        assert tier.strip(), "Plan tier rendered blank"
        for junk in _PLACEHOLDERS:
            assert junk not in tier, f"Placeholder leakage in plan tier: {tier!r}"
        assert tier in SettingsPage.KNOWN_PLAN_TIERS, (
            f"Plan tier {tier!r} is not a member of the known valid set "
            f"{SettingsPage.KNOWN_PLAN_TIERS}"
        )
        # The fixture is seeded on plan_identifier='regular' -> tier 'Regular'.
        assert tier == "Regular", (
            f"fixture is on the 'regular' plan, so the rendered tier should be "
            f"'Regular', got {tier!r}"
        )
        print(f"  PASS: plan tier {tier!r} is a real value in the known set")

        # ---- 3) MONTHLY FEE: EXACT value for the current ('regular') tier ---- #
        # P1-01: the Plans / Plans-and-fees surface renders the monthly
        # subscription fee co-located with the plan/fee copy ("from $5.50 /
        # month"). The fixture is on the 'regular' tier whose monthly fee is
        # exactly $5.50. Assert that exact value — not mere presence of a fee
        # keyword (which any dollar figure would satisfy).
        fee = plans.current_monthly_fee()
        print(f"  monthly fee rendered: {fee!r}")
        assert fee is not None, (
            "Plans-and-fees surface rendered no well-formed monthly fee figure; "
            f"texts: {plans.visible_texts()!r}"
        )
        for junk in _PLACEHOLDERS:
            assert junk not in fee, f"Placeholder leakage in monthly fee: {fee!r}"
        assert fee == "$5.50", (
            f"current ('regular') tier monthly fee should be exactly '$5.50', "
            f"got {fee!r}; texts: {plans.visible_texts()!r}"
        )
        print(f"  PASS: monthly fee {fee!r} is the exact regular-tier value")
    finally:
        try:
            d.quit()
        except Exception:
            pass


def test_plan_and_fees_render_exact_fee():
    """The pricing-plans surface (raiz://plans) renders the EXACT monthly fee for
    the current ('regular') tier — '$5.50' — co-located with the plan/fee copy
    ('from $5.50 / month').

    P1-01: the navigation-coverage suite formerly proved this surface only with an
    OR'd fee-keyword presence check (incl. '0.275%'), so ANY dollar figure (or
    none) stayed green. This is the VALUE oracle for the fee: it reads the actual
    rendered amount via SettingsPage.current_monthly_fee() and asserts the precise
    regular-tier figure.

    NOTE (crawl-verified on emulator-5554): the monthly DOLLAR fee lives on the
    Pricing-plans screen (raiz://plans: 'from $5.50 / month'); the Plans-and-fees
    screen (raiz://fees) renders only the percentage fee ('0.275% p.a.') and the
    plan label ('Regular'), NOT a monthly dollar figure — so the dollar-fee VALUE
    is read from raiz://plans. Uses the long-lived `presence_funded` fixture
    (seeded on the 'regular' plan); no fresh user per run."""
    fx = get_or_create_fixture_user("presence_funded")

    opts = get_android_options(no_reset=False)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)

        from appium.webdriver.common.appiumby import AppiumBy
        plans = _open(
            d, DeepLinks.PLANS,
            (AppiumBy.XPATH,
             "//*[contains(@text,'Pricing plan') or contains(@text,'Current plan') "
             "or contains(@text,'plan') or contains(@text,'Plan')]"),
        )
        # Let the fee value hydrate (it can populate after the static labels).
        plans.wait_for_value("$5.50", timeout=DEFAULT_WAIT)
        fee = plans.current_monthly_fee()
        print(f"  plans-screen monthly fee rendered: {fee!r}")
        assert fee is not None, (
            "Pricing-plans rendered no well-formed monthly fee figure; "
            f"texts: {plans.visible_texts()!r}"
        )
        for junk in _PLACEHOLDERS:
            assert junk not in fee, f"Placeholder leakage in monthly fee: {fee!r}"
        assert fee == "$5.50", (
            f"current ('regular') tier monthly fee should be exactly '$5.50', "
            f"got {fee!r}; texts: {plans.visible_texts()!r}"
        )
        print(f"  PASS: Pricing-plans shows exact regular-tier fee {fee!r}")
    finally:
        try:
            d.quit()
        except Exception:
            pass
