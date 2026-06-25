"""
ON-DEVICE JAR-CARD VALUE E2E (TC-02 [P0]).

The named jar card on the Jars list screen must render THAT jar's seeded balance,
and the name-scoped getter (JarsPage.get_jar_balance_by_name) must NOT bleed a
sibling jar's value. This is the on-device counterpart to the API-only
`test_sibling_jars_hold_distinct_balances` in test_value_validation_api.py — that
one proves the backend keeps sibling balances distinct; this one proves the APP
renders the right value in the right named card.

Architecture: a jar is its OWN user (jar_account) under a parent, with its own
current_balance. To see the jar *cards*, we log into the app AS THE PARENT and open
the Jars list. We seed a FRESH parent with two sibling jars of DISTINCT amounts (no
shared fixture provides two named jars under one parent, so this scenario truly needs
a fresh seed), poll each jar's backend current_balance until it settles to the EXACT
seeded amount (the proven Aggressive + ACH-credit recipe), then assert on-device:
  - get_jar_balance_by_name(JAR_A) == JAR_A backend current_balance (within band)
  - get_jar_balance_by_name(JAR_A) != get_jar_balance_by_name(JAR_B)   (no sibling leak)

Standalone (own driver; clears app data). DEV API only. Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_jars_value_on_device.py -v -s -o addopts=""
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
from pages.jars_page import JarsPage
from utils.deep_links import DeepLinks
from utils.assertions import parse_money
from utils.genuser_api import (
    SEEDED_PWD, gen_create, current_balance, funded_user, ach_credit,
)

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# Settled balance lands on the seeded dollar amount; small tolerance for cents/drift.
BAND = 1.50
# Distinct, non-round sibling amounts so an accidental positional/leaked read can't
# coincidentally match the other jar.
AMT_A = 80.10
AMT_B = 120.40
# Settlement is async on the dev backend; poll each jar's own balance until exact.
SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "480"))
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))


def _jar_user(parent_ref, email, first, jar_name):
    """A jar_account sub-account under `parent_ref`, with the same balance levers as a
    main user (Aggressive + funded) so its ACH credit settles to an EXACT amount.
    Mirrors the proven recipe in test_value_validation_api.py."""
    u = funded_user(email, first)
    u["traits"] = ["jar_account"] + u["traits"]
    u["attributes"]["parent_user"] = parent_ref
    u["attributes"]["jar_account_data"] = {"name": jar_name}
    return u


def _poll_balances(targets):
    """Poll several (sub-)accounts' own current_balance concurrently within ONE shared
    budget+cadence, until each settles within BAND of its target (then we stop
    re-querying that one) or the budget runs out. `targets` maps email -> target
    amount. Returns {email: (best_seen, settled_bool)}.

    Both jars are seeded in the same create call and settle in the same async window,
    so polling them in a shared loop — instead of running a full SETTLE_BUDGET_S loop
    per jar back-to-back — halves the worst-case wait and the login/read volume while
    keeping the exact per-jar settle criterion (BAND) unchanged."""
    state = {email: [0.0, False] for email in targets}
    waited = 0
    while waited <= SETTLE_BUDGET_S and not all(s[1] for s in state.values()):
        for email, target in targets.items():
            if state[email][1]:
                continue
            bal = current_balance(email, SEEDED_PWD)
            if bal is not None:
                state[email][0] = max(state[email][0], bal)
                print(f"  [poll {email} +{waited}s] current_balance={bal}")
                if abs(bal - target) <= BAND:
                    state[email][1] = True
        if all(s[1] for s in state.values()):
            break
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return {email: (best, settled) for email, (best, settled) in state.items()}


def _seed_parent_with_two_jars():
    """Seed a fresh parent + two sibling jars (DISTINCT amounts) and wait for both jar
    balances to settle to their exact seeded values. Returns
    (parent_email, jar_a_name, bal_a, jar_b_name, bal_b)."""
    ts = str(int(time.time()))
    parent_email = f"tc02.jarparent.{ts}@emel.xyz"
    jar_a_email = f"tc02.jara.{ts}@emel.xyz"
    jar_b_email = f"tc02.jarb.{ts}@emel.xyz"
    jar_a_name = f"TC02 Jar A {ts}"
    jar_b_name = f"TC02 Jar B {ts}"
    payload = {
        "user_1": funded_user(parent_email, f"TC02Parent{ts}"),
        "jar_a": _jar_user("@user_1", jar_a_email, f"TC02JarA{ts}", jar_a_name),
        "jar_b": _jar_user("@user_1", jar_b_email, f"TC02JarB{ts}", jar_b_name),
        "credit_a": ach_credit("@jar_a", AMT_A),
        "credit_b": ach_credit("@jar_b", AMT_B),
    }
    status, body = gen_create(payload)
    assert status == 200, f"seed failed: HTTP {status} {body}"
    created = body.get("created", {}) if isinstance(body, dict) else {}
    assert created.get("jar_a", {}).get("id") and created.get("jar_b", {}).get("id"), \
        f"sibling jars not created: {body}"
    print(f"  seeded parent {created['user_1']['id']} with jars "
          f"A {created['jar_a']['id']} (${AMT_A}, {jar_a_name!r}) and "
          f"B {created['jar_b']['id']} (${AMT_B}, {jar_b_name!r})")

    results = _poll_balances({jar_a_email: AMT_A, jar_b_email: AMT_B})
    bal_a, settled_a = results[jar_a_email]
    bal_b, settled_b = results[jar_b_email]
    if not (settled_a and settled_b):
        pytest.fail(f"jar balances never settled (A ${bal_a}/${AMT_A} settled={settled_a}; "
                    f"B ${bal_b}/${AMT_B} settled={settled_b})")
    # Sanity: the two seeded amounts must actually be distinct, else the sibling-leak
    # half of the oracle is vacuous.
    assert abs(bal_a - bal_b) > BAND, f"seeded sibling balances not distinct: A ${bal_a}, B ${bal_b}"
    return parent_email, jar_a_name, bal_a, jar_b_name, bal_b


def _login_as_parent(d, email, pwd):
    """Log the parent into the app and land on Home (clearing first-login onboarding
    once if it shows). Uses explicit waits rather than blind sleeps — login RTT
    varies on a slow emulator (~1-3s) so we poll for the splash/Home instead of
    guessing a fixed delay."""
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_visible(sp.TAGLINE, timeout=15):
        sp.tap_log_in()
    lo.login(email, pwd)
    # Poll for Home rather than sleeping a flat 7s; complete onboarding once if the
    # first-login flow appears instead of Home.
    if not ho.is_visible(ho.TOTAL_VALUE_LABEL, timeout=30):
        onb = OnboardingPage(d)
        assert onb.complete(), f"onboarding stuck at {onb.path}"
        assert ho.is_visible(ho.TOTAL_VALUE_LABEL, timeout=20), \
            "parent not on Home after completing onboarding"
    # A promo / biometrics modal can overlay Home right after login and would sit
    # over the Jars list too; clear it before navigating.
    try:
        ho.dismiss_modal()
    except Exception:
        pass
    assert ho.is_present_now(ho.TOTAL_VALUE_LABEL), "parent not on Home after login"
    return ho


def _open_jars_list(d, jars: JarsPage):
    """Open the Jars list screen and confirm it's the populated LIST screen, not the
    empty Create screen. The first deep link can land on a transient
    create/onboarding gate while jar data is still loading, so retry the deep link
    (with a Home Jars-card fallback) with backoff — is_list_screen() already returns
    False on the create screen, so polling it naturally rides through a transient
    gate instead of giving up on the first render."""
    for attempt in range(4):
        DeepLinks.open(d, DeepLinks.JARS)
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                jars.dismiss_modal()
            except Exception:
                pass
            if jars.is_list_screen(timeout=2):
                return
            time.sleep(1)
        # Fallback on later attempts: tap the Jars account card from Home.
        if attempt >= 1:
            try:
                HomePage(d).tap_jars()
            except Exception:
                pass
        time.sleep(2 + attempt)
    assert jars.is_list_screen(timeout=8), \
        "expected the populated Jars LIST screen (parent has 2 seeded jars)"


def _read_card_value(jars: JarsPage, name: str):
    """Scroll the named jar card into view and read its name-scoped balance, with a
    few retries for a slow first render."""
    for _ in range(5):
        jars.scroll_jar_into_view(name)
        raw = jars.get_jar_balance_by_name(name)
        if raw:
            return raw
        time.sleep(2)
    return None


def test_jar_card_value_matches_seeded_balance():
    """The named jar card renders THAT jar's seeded balance, and the name-scoped
    getter does not bleed a sibling jar's value (two distinct sibling jars)."""
    parent_email, jar_a, bal_a, jar_b, bal_b = _seed_parent_with_two_jars()
    print(f"  backend settled: {jar_a!r}=${bal_a}, {jar_b!r}=${bal_b}")

    opts = get_android_options(no_reset=False)  # fresh app data
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_as_parent(d, parent_email, SEEDED_PWD)
        jars = JarsPage(d)
        _open_jars_list(d, jars)

        raw_a = _read_card_value(jars, jar_a)
        raw_b = _read_card_value(jars, jar_b)
        print(f"  on-device jar cards: {jar_a!r}->{raw_a!r}, {jar_b!r}->{raw_b!r}")
        assert raw_a, f"jar A card {jar_a!r} rendered no balance"
        assert raw_b, f"jar B card {jar_b!r} rendered no balance"

        card_a = parse_money(raw_a)
        card_b = parse_money(raw_b)

        # Oracle 1: the named card == that jar's backend current_balance (within band).
        assert card_a == pytest.approx(bal_a, abs=BAND), \
            f"jar A card ${card_a} should match backend ${bal_a} for {jar_a!r}"

        # Oracle 2: the name-scoped getter does NOT return the sibling's value.
        assert card_a != pytest.approx(card_b, abs=BAND), \
            (f"name-scoped getter leaked a sibling value: {jar_a!r}->${card_a} == "
             f"{jar_b!r}->${card_b} (expected distinct ${bal_a} vs ${bal_b})")
        # And jar B's card matches ITS own backend balance, confirming the read is
        # scoped per-jar rather than both cards reading the same number.
        assert card_b == pytest.approx(bal_b, abs=BAND), \
            f"jar B card ${card_b} should match backend ${bal_b} for {jar_b!r}"

        print(f"  PASS: {jar_a!r} card ${card_a} == backend ${bal_a}; "
              f"distinct from {jar_b!r} ${card_b} (==backend ${bal_b})")
    finally:
        try:
            d.quit()
        except Exception:
            pass
