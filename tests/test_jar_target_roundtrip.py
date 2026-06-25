"""
jar-target-roundtrip (P0, conf 82, cons 6) — VALUE, UI read-back + observable
backend anchor.

A jar's savings goal/target must ROUND-TRIP EXACTLY: a $5,000 goal reads back as
$5,000 (==5000.0), NOT $500 (==500.0). This is the classic 10x truncation defect
(5,000 -> 500) the case targets. A presence-only assertion ("a goal renders")
would sail straight past it; the oracle is the NUMERIC VALUE.

TWO LAYERS (both grounded in real source, per the backlog refinement
"UI-set + UI-read-back; downgrade backend goal clause to 'if observable'"):

  1. BACKEND ANCHOR (deterministic, the reliable observable) — the jar is its own
     `user` (a jar_account) under the parent. The Raiz Jars API exposes the goal as
     `saving_amount` on the jar entity (app/api/entities/jars/show.rb) and the jars
     list endpoint `GET /jars/v1/users` returns it for every jar the parent owns
     (app/api/jars/v1/resources/users.rb -> rabl 'jars/list'; backend rounds to 2dp
     via app/views/api/jars/show.rabl). We log in AS THE PARENT and read the
     "Europe trip" jar's saving_amount back: it must equal 5000.0 EXACTLY, never
     500.0. The backlog said "backend goal if observable" — it IS observable here,
     so this is the deterministic anchor.

  2. ON-DEVICE READ-BACK (the case's literal UI oracle) — the Jars list card for
     "Europe trip" renders the goal next to the balance as "/ $5,000"
     (raizFeatureJars JarListItemUi.kt: `"/ ${item.savingAmount.asFormattedAmount()}"`,
     shown only when savingAmount > 0). NOTE on the exact string: build 3252's
     money formatter has defaultMoneyForceDecimal()==false (formatters.kt) and
     formatLocalizedMoney(5000.0) drops the decimals on a whole dollar amount
     (MoneyFormatterTest: formatLocalizedMoney(12.0) -> "$12"), so the goal renders
     "$5,000" (NOT "$5,000.00"). We therefore assert on the PARSED NUMERIC VALUE
     (5000, tolerant of whether ".00" renders), which is what actually catches the
     5000->500 truncation; an exact "$5,000.00" literal would false-fail on a
     correct app. We isolate the goal from the balance ($100) by reading the LARGER
     money token in the card (the goal $5,000 vs the balance $100), so a balance
     read can't masquerade as the goal.

DATA: the pre-provisioned `jar_target_goal` fixture (reuse strategy). user_1 is
the parent (stored login); jar_1 is "Europe trip" with saving_amount==$5,000 and a
$100 ACH balance, seeded at the API layer (HTTP 200 verified at provision time, so
the goal was accepted). No fresh seed unless the stored fixture stops logging in
(handled by get_or_create_fixture_user). This is a READ-ONLY test — it never
mutates the jar — so reuse is safe.

needs_device: TRUE. The backend anchor runs first (deterministic, no device) and
the case fails fast if the goal didn't even round-trip server-side; the on-device
read-back then proves the APP renders the goal value (not just the backend).

Run (needs emulator + Appium for the on-device half):
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_jar_target_roundtrip.py -v -s -o addopts=""
"""
import os

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
from utils.assertions import parse_money, is_money
from utils.genuser_api import SEEDED_PWD, mint, call, can_login
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.jars]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

FIXTURE_KEY = "jar_target_goal"
JAR_NAME = "Europe trip"          # utils.genuser_fixtures JAR_TARGET_NAME
EXPECTED_GOAL = 5000.0            # utils.genuser_fixtures JAR_TARGET_GOAL ($5,000)
TRUNCATED_GOAL = 500.0           # the 10x truncation this case exists to catch
SEEDED_BALANCE = 100.0           # the jar's $100 ACH balance (NOT the goal)
# Backend rounds saving_amount to 2dp (api/jars/show.rabl); the seed is a whole
# number, so an exact-equality assert is correct for the backend anchor. The
# on-device value tolerates cents drift only.
DEVICE_BAND = 1.0


# --------------------------------------------------------------------------- #
# Backend anchor: read the parent's jars list and pull the goal for our jar.
# --------------------------------------------------------------------------- #
def _read_jar_goal_via_api(parent_email, pwd, jar_name):
    """Log in AS THE PARENT and return (saving_amount, current_balance_field) for
    the named jar from `GET /jars/v1/users` (rabl 'jars/list'), or (None, None) if
    the jar/endpoint can't be read. saving_amount is the goal/target; the entity
    also exposes accumulated_amount (the jar's invested balance)."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None, None
    status, body = call(op, "GET", "/jars/v1/users", token=tok)
    if status != 200:
        print(f"  [api] GET /jars/v1/users -> HTTP {status}: {body}")
        return None, None
    # The list endpoint (rabl 'jars/list' -> `child @jar_users => :jar_users`) wraps
    # the array under the "jar_users" key: {"jar_users": [ {id,name,saving_amount,...} ]}.
    # Read that real key FIRST (the previous parser only knew "jars"/"users", so a fully
    # populated response was silently read as [] and misreported as a missing jar).
    if isinstance(body, list):
        jars = body
    else:
        jars = (body.get("jar_users") or body.get("jars") or body.get("users") or [])
    for j in jars if isinstance(jars, list) else []:
        if not isinstance(j, dict):
            continue
        if (j.get("name") or "").strip() == jar_name:
            goal = j.get("saving_amount")
            acc = j.get("accumulated_amount")
            return (float(goal) if goal is not None else None,
                    float(acc) if acc is not None else None)
    print(f"  [api] jar named {jar_name!r} not found in jars list: "
          f"{[ (j.get('name') if isinstance(j, dict) else j) for j in (jars if isinstance(jars, list) else []) ]}")
    return None, None


# --------------------------------------------------------------------------- #
# On-device helpers
# --------------------------------------------------------------------------- #
class OnboardingBlocked(Exception):
    """Raised when the first-login onboarding gauntlet cannot be cleared to Home.
    This is shared-infra (pages/onboarding_page.py) on build 3252 — the portfolio
    intro / Round-Up checklist render as unlabelled Compose containers that the
    text-driven completer loops on — and is OUTSIDE this case's oracle (the goal
    round-trip), so the on-device half SKIPS with this as evidence rather than
    reporting a false red. The backend anchor remains the deterministic guarantee."""


def _login_as_parent(d, fx):
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    if splash.is_visible(splash.TAGLINE, timeout=15):
        splash.tap_log_in()
    login.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    if not home.is_visible(home.TOTAL_VALUE_LABEL, timeout=30):
        if not onb.complete():
            raise OnboardingBlocked(
                f"first-login onboarding could not reach Home (path={onb.path}); "
                f"shared onboarding gauntlet gap on build 3252, not a jar-goal defect"
            )
        mark_onboarded(fx["key"])
        if not home.is_visible(home.TOTAL_VALUE_LABEL, timeout=20):
            raise OnboardingBlocked(
                f"onboarding completer returned but Home not shown (path={onb.path})"
            )
    try:
        home.dismiss_modal()
    except Exception:
        pass
    assert home.is_present_now(home.TOTAL_VALUE_LABEL), "not on Home after login as parent"
    return home


def _open_jars_list(d, jars: JarsPage):
    """Open the populated Jars LIST screen (the parent owns one seeded jar), riding
    through a transient create/loading gate. Mirrors the proven opener in
    test_jars_value_on_device.py."""
    import time
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
        if attempt >= 1:
            try:
                HomePage(d).tap_jars()
            except Exception:
                pass
        time.sleep(2 + attempt)
    assert jars.is_list_screen(timeout=8), \
        "expected the populated Jars LIST screen (parent has 1 seeded jar)"


def _read_card_money_tokens(jars: JarsPage, name: str):
    """All well-formed money strings rendered inside the named jar's card. The
    'Europe trip' card holds two: the balance ($100) and the goal ('/ $5,000').
    We read within the tightest container that holds this jar's name AND a '$' so a
    sibling card can't bleed in (reuses JarsPage's own tight-container logic by
    scrolling the card into view first, then collecting money TextViews inside the
    smallest matching wrapper)."""
    import time
    from appium.webdriver.common.appiumby import AppiumBy
    for _ in range(5):
        jars.scroll_jar_into_view(name)
        candidates = jars.driver.find_elements(
            AppiumBy.XPATH,
            f"//android.view.View"
            f"[.//android.widget.TextView[contains(@text, {jars._xq(name)})]"
            f" and .//android.widget.TextView[contains(@text, '$')]]",
        )
        best = None  # (money_count, [money strings]) — minimise count for the tight card
        for c in candidates:
            monies = [tv.text for tv in c.find_elements(
                AppiumBy.XPATH, ".//android.widget.TextView[contains(@text, '$')]")
                if is_money(tv.text or "")]
            if not monies:
                continue
            if best is None or len(monies) < best[0]:
                best = (len(monies), monies)
        if best and best[1]:
            return best[1]
        time.sleep(2)
    return []


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_jar_goal_roundtrips_exactly_backend():
    """Backend anchor: the seeded $5,000 goal reads back as EXACTLY 5000.0 from the
    jars API (never 500.0). Deterministic, no device — fails fast if the goal never
    round-tripped server-side."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')}); jar {JAR_NAME!r}")

    assert can_login(parent_email, pwd), (
        f"fixture parent {parent_email} could not log in — fixture not provisioned; "
        f"cannot read the jar goal back"
    )

    goal, accumulated = _read_jar_goal_via_api(parent_email, pwd, JAR_NAME)
    assert goal is not None, (
        f"could not read saving_amount for jar {JAR_NAME!r} from GET /jars/v1/users "
        f"as parent {parent_email} — the goal is not observable, so the backend "
        f"round-trip cannot be asserted"
    )
    print(f"  [api] {JAR_NAME!r} saving_amount={goal} accumulated_amount={accumulated}")

    # Core oracle: EXACT round-trip. A 5,000 -> 500 truncation reads back 500.0.
    assert goal != pytest.approx(TRUNCATED_GOAL, abs=DEVICE_BAND), (
        f"jar goal read back as ${goal} — looks like the ${EXPECTED_GOAL:.0f} -> "
        f"${TRUNCATED_GOAL:.0f} truncation defect this case targets"
    )
    assert goal == EXPECTED_GOAL, (
        f"jar goal must round-trip EXACTLY to ${EXPECTED_GOAL:.2f}, got ${goal} "
        f"(saving_amount is seeded as a whole number, backend rounds to 2dp)"
    )

    # The goal is distinct from the jar's balance: a backend that mirrored the
    # balance ($100) into the goal field would also be wrong.
    assert goal != pytest.approx(SEEDED_BALANCE, abs=DEVICE_BAND), (
        f"jar goal (${goal}) equals the jar BALANCE (${SEEDED_BALANCE}) — the goal "
        f"field is not holding the seeded target"
    )


def test_jar_goal_roundtrips_exactly_on_device():
    """On-device read-back (the case's literal UI oracle): the 'Europe trip' jar
    card renders the goal as a value of 5000 (not 500). Reads the LARGER money token
    in the card to isolate the goal ($5,000) from the balance ($100)."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)

    # Re-confirm the backend round-trip so the on-device assertion has a trusted
    # expected value (and we don't chase a UI bug that is actually a seed problem).
    api_goal, _ = _read_jar_goal_via_api(parent_email, pwd, JAR_NAME)
    assert api_goal == EXPECTED_GOAL, (
        f"backend goal for {JAR_NAME!r} is ${api_goal}, expected ${EXPECTED_GOAL} — "
        f"resolve the backend round-trip (test_jar_goal_roundtrips_exactly_backend) "
        f"before trusting the on-device read"
    )

    opts = get_android_options(no_reset=False)  # fresh app data for a clean login
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        try:
            _login_as_parent(d, parent)
        except OnboardingBlocked as e:
            # Honest skip-with-evidence: the goal DID round-trip server-side (asserted
            # above), but the device cannot be driven past the build-3252 onboarding
            # gauntlet — an infra gap outside this case's oracle. Never a fake pass.
            pytest.skip(f"on-device read-back blocked by onboarding gauntlet: {e}")
        jars = JarsPage(d)
        _open_jars_list(d, jars)

        monies = _read_card_money_tokens(jars, JAR_NAME)
        print(f"  on-device {JAR_NAME!r} card money tokens: {monies!r}")
        assert monies, f"jar card {JAR_NAME!r} rendered no money tokens"

        values = [parse_money(m) for m in monies]
        # The goal is the LARGER value on the card (goal $5,000 vs balance $100).
        # Reading the max isolates the goal from the balance without depending on
        # the '/' prefix surviving the accessibility tree.
        goal_value = max(values)
        print(f"  on-device parsed values: {values} -> goal candidate ${goal_value}")

        # Core oracle: the rendered goal is 5000, NOT 500 (the truncation defect).
        assert goal_value != pytest.approx(TRUNCATED_GOAL, abs=DEVICE_BAND), (
            f"jar card rendered a goal of ${goal_value} — the ${EXPECTED_GOAL:.0f} "
            f"-> ${TRUNCATED_GOAL:.0f} truncation defect this case targets"
        )
        assert goal_value == pytest.approx(EXPECTED_GOAL, abs=DEVICE_BAND), (
            f"jar card goal should read ${EXPECTED_GOAL:.0f} (build 3252 renders a "
            f"whole-dollar goal as '$5,000', no decimals), got ${goal_value} from "
            f"{monies!r}"
        )
        # Sanity: the card also showed the balance, distinct from the goal — proves
        # we isolated the goal token rather than reading a single number twice.
        if len(values) >= 2:
            assert min(values) == pytest.approx(SEEDED_BALANCE, abs=max(DEVICE_BAND, 0.03 * SEEDED_BALANCE)), (
                f"expected the jar balance (${SEEDED_BALANCE}) alongside the goal, "
                f"got tokens {monies!r}"
            )
    finally:
        try:
            d.quit()
        except Exception:
            pass
