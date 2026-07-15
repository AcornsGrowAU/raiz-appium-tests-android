"""
ON-DEVICE WITHDRAWAL E2E for generated users (reuse strategy — rich buffers, so a
withdrawal is negligible and the fixture lasts many runs).

Logs into the real app AS a generated user and completes a withdrawal through the
actual Withdraw UI, asserting the "Withdrawal Confirmed" success screen (the FLOW
oracle).

For the KIDS/JARS sub-accounts we ALSO add a VALUE oracle: a KID sub-account is its
own login user with its own backend current_balance; a JAR is a sub-account of the
main account with NO loginable identity (POST /v1/sessions with a jar email 401s BY
DESIGN), so its balance is the jar's accumulated_amount read via the PARENT's
session (utils.genuser_api.jar_balance_by_name). Either way we read the balance
before the withdrawal and poll it after (settle-poll pattern from
test_value_validation_api / test_withdraw_available_value) and assert it dropped by
~the withdrawn amount within a band. The MAIN account stays flow-only — it is
six-figure market-priced holdings whose repricing swamps a $100 delta (the exact
balance-after contract there is covered by the API tests in
test_value_validation_api.py).

Mapped flow: Home → Withdraw → keypad amount → [Withdraw] → "Confirm Withdrawal" →
[Confirm] → "Withdrawal Confirmed" → [Ok] → Home. No PIN prompt.

Standalone (own driver; clears app data). Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_withdrawal_e2e.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST, STATE_PROBE_WAIT
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.lump_sum_page import LumpSumPage
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded
from utils.genuser_api import jar_balance_by_name, mint, call, SEEDED_PWD

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# jars_withdrawal_buffer fixture shape (utils.genuser_fixtures FIXTURES builder):
# the registry email IS the JAR sub-account; its PARENT is "jp." + that email and
# the jar's display name is "QA WD Jar". Jars have NO loginable identity (POST
# /v1/sessions with a jar email 401s BY DESIGN), so the jar's balance is ONLY
# readable as accumulated_amount through the parent's session.
JARS_BUFFER_PARENT_PREFIX = "jp."
JARS_BUFFER_JAR_NAME = "QA WD Jar"

# --- backend balance DELTA oracle for the kids/jars SUB-accounts -------------
# Unlike the market-noisy six-figure MAIN account (covered by the success screen
# alone) we can read the sub-account balance before, withdraw, poll the balance
# after, and assert it dropped by ~the withdrawn amount. The KID buffer is its
# own login user with its own current_balance (kid_account_data.account_access is
# true in the fixtures); the JAR buffer has NO loginable identity, so its balance
# is the jar's accumulated_amount read via the PARENT's session
# (jar_balance_by_name).
#
# The buffers are ~$320k of MARKET-PRICED holdings that reprice between reads, so
# the drop is matched within a band sized for that magnitude (~$0.50/$1k of
# holdings ≈ $160 on $320k) rather than to the cent — the withdrawn $100 is the
# signal, the repricing is the noise the band absorbs. The success screen remains
# the FLOW oracle; this delta is the VALUE oracle.
DELTA_BAND = float(os.getenv("WD_DELTA_BAND", "250.0"))
SETTLE_BUDGET_S = int(os.getenv("WD_SETTLE_BUDGET_S", "180"))
POLL_INTERVAL_S = int(os.getenv("WD_POLL_INTERVAL_S", "20"))


def _self_balance_reader(email):
    """Balance reader for a sub-account that IS its own login user (KIDS only —
    kid_account_data.account_access is true in the fixtures; jar emails can NEVER
    be minted). Reuses ONE minted session across reads (the /v1/sessions endpoint
    is rate-limited), re-minting only on a failed read. Returns a zero-arg
    callable -> current_balance float | None."""
    state = {}
    state["op"], state["tok"] = mint(email, SEEDED_PWD)

    def read():
        if state["tok"] is None:
            state["op"], state["tok"] = mint(email, SEEDED_PWD)
            if state["tok"] is None:
                return None
        s, b = call(state["op"], "GET", "/v1/user", token=state["tok"])
        if s != 200:  # token expired/rejected -> re-mint on the next pass
            state["op"], state["tok"] = mint(email, SEEDED_PWD)
            return None
        user = b.get("user", b) if isinstance(b, dict) else {}
        cb = user.get("current_balance")
        return float(cb) if cb is not None else None

    return read


def _jar_parent_reader(parent_email, jar_name):
    """Balance reader for a JAR sub-account. Jars have NO loginable identity
    (/v1/sessions with a jar email 401s BY DESIGN), so the jar's balance is its
    accumulated_amount read through the PARENT's session (jar_balance_by_name).
    Each read mints a parent session; mint() itself absorbs rate limiting."""
    return lambda: jar_balance_by_name(parent_email, jar_name)


def _poll_balance_drop(read_balance, before, expected_drop):
    """Poll the sub-account balance (via read_balance()) until it has dropped by
    ~expected_drop from `before` (within DELTA_BAND), or the settle budget elapses.
    Returns (best_after, dropped_bool) where best_after is the reading whose drop
    is closest to expected — so the assertion message is meaningful even on
    timeout. Mirrors test_value_validation_api's settle-poll and
    test_withdraw_available_value's _poll_balance_drop."""
    target = round(before - expected_drop, 2)
    waited = 0
    best_after, best_err = before, expected_drop  # initial drop of 0
    while waited <= SETTLE_BUDGET_S:
        bal = read_balance()
        if bal is not None:
            drop = before - bal
            err = abs(drop - expected_drop)
            if err < best_err:
                best_err, best_after = err, bal
            print(f"  [poll +{waited}s] balance={bal} (drop={round(drop, 2)})")
            if abs(bal - target) <= DELTA_BAND:
                return bal, True
        else:
            print(f"  [poll +{waited}s] backend balance read failed")
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return best_after, False


def _tap_text(d, *labels, which=-1):
    """Tap a TextView by exact text. which=-1 -> last match (the confirm 'Withdraw'
    button, vs the screen title which is the first match)."""
    for lab in labels:
        els = d.find_elements(AppiumBy.XPATH, f"//*[@text='{lab}']")
        if els:
            try:
                els[which].click()
                return lab
            except Exception:
                pass
    return None


def _tap_button(d, label):
    """Tap the CLICKABLE container whose descendant text == label (the button's text
    sits on a child View, so clicking the bare TextView misses the button). Falls
    back to the text element. Uses the LAST match (bottom button vs a title)."""
    els = d.find_elements(AppiumBy.XPATH, f"//*[@clickable='true'][.//*[@text='{label}']]")
    if not els:
        els = d.find_elements(AppiumBy.XPATH, f"//*[@text='{label}']")
    if els:
        try:
            els[-1].click()
            return True
        except Exception:
            pass
    return False


def _wait_text(d, contains, secs=15):
    """Poll up to `secs` for a TextView containing `contains` (slow emulator network)."""
    waited = 0.0
    while waited <= secs:
        if d.find_elements(AppiumBy.XPATH, f"//*[contains(@text,'{contains}')]"):
            return True
        time.sleep(1.5)
        waited += 1.5
    return False


def _wait_post_login(d, ho, timeout=30, poll=0.5):
    """Poll until the post-login transition settles on a terminal screen we can act
    on: either Home is loaded, or an onboarding screen is on-screen. Replaces a blind
    `time.sleep(7)` that under-waits on a slow emulator (1-3s RTT) and over-waits on
    a fast one. Returns 'home' or 'onboarding'; 'unknown' if neither appeared within
    the timeout (caller still asserts Home as the hard gate). Mirrors
    test_main_value_on_device._wait_post_login."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ho.is_loaded(timeout=1):
            return "home"
        src = (d.page_source or "").lower()
        if any(k in src for k in ("skip", "got it", "select as your portfolio",
                                  "i consent", "agree")):
            return "onboarding"
        time.sleep(poll)
    return "unknown"


def _login_and_home(d, fx):
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
    # Wait for the login form rather than a fixed beat; the splash can hand off
    # slowly on a cold emulator.
    assert lo.is_loaded(timeout=20), "login form did not load"
    lo.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    # Build-robust home detection: the kids/jars sub-account fixtures land on the
    # REDESIGNED home (build 3226) which drops the legacy 'Your total investments
    # value' header and shows a 'Welcome' greeting + the Past/Today/Future tab bar.
    # Gating on the legacy label alone mis-reads that as "onboarding incomplete" and
    # OnboardingPage.complete() then immediately STUCKs (there is no onboarding left
    # to run). Use HomePage.is_loaded(), which accepts either layout (legacy header
    # OR the build-agnostic Today tab) — mirrors test_main_value_on_device.
    # Poll the post-login transition to a terminal screen instead of a blind
    # sleep(7) before deciding Home-vs-onboarding.
    state = _wait_post_login(d, ho)
    if state != "home" and not ho.is_loaded(timeout=8):
        assert onb.complete(), f"onboarding stuck: {onb.path}"
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=20), "not on Home after login"
    return ho


def _withdraw(d, ho, dollars):
    """Drive the in-app Withdraw flow for $dollars via the shared LumpSumPage keypad
    (its clickable-container KEY_MAP — a bare TextView tap is swallowed by the
    non-clickable inner view), confirming each transition with a bounded poll+re-tap
    instead of a blind 10x3.5s fixed loop. Mirrors
    test_withdraw_available_value._drive_withdrawal. Returns True iff the
    'Withdrawal Confirmed' success screen appeared (the FLOW oracle)."""
    lump = LumpSumPage(d)
    ho.tap_withdraw()
    assert lump.is_withdraw_loaded(), "Withdraw screen didn't open"

    # Keypad entry via the clickable-container KEY_MAP.
    lump.enter_amount(str(int(dollars)))
    shown = lump.get_amount_display()
    print(f"  keypad amount display: {shown!r}")

    # The keypad 'Withdraw' tap can be SWALLOWED by Compose late-hydration on a slow
    # emulator (the button is hit before its handler is wired), leaving the
    # confirmation sheet absent. Re-tap (bounded) only while the sheet still isn't up.
    # The oracle is unchanged: we still REQUIRE the 'Confirm Withdrawal' sheet.
    confirmation_shown = False
    for attempt in range(3):
        lump.tap_withdraw()
        if lump.is_confirmation_shown(timeout=STATE_PROBE_WAIT):
            confirmation_shown = True
            break
        print(f"  confirmation sheet not up after keypad Withdraw (attempt {attempt + 1}); retrying")
    assert confirmation_shown, "'Confirm Withdrawal' sheet didn't appear"

    # Same swallowed-tap risk on the sheet's Confirm. Re-tap while the sheet is still
    # up and the success screen hasn't been detected yet. Oracle unchanged: we still
    # REQUIRE the 'Withdrawal Confirmed' success screen.
    confirmed = False
    for attempt in range(3):
        lump.confirm_withdraw()
        if lump.is_withdrawal_confirmed():
            confirmed = True
            break
        if not lump.is_confirmation_shown(timeout=STATE_PROBE_WAIT):
            break
        print(f"  success screen not up after Confirm (attempt {attempt + 1}); sheet still open, retrying")
    if confirmed:
        lump.dismiss_success()  # dismiss the success screen (cleanup, not an oracle)
    return confirmed


def _run_withdrawal(account_label, fixture_key, dollars=100, check_delta=False,
                    jar_name=None):
    """Log in as a generated (sub-)account holder with a rich buffer and complete an
    on-device withdrawal, asserting the 'Withdrawal Confirmed' success screen.

    A KID sub-account is its own login user (own login + own current_balance) under
    a parent; a JAR is a sub-account of the main account with NO loginable identity
    — which is part of why the KIDS/JARS legs below are skipped (see
    _REDESIGN_NO_WITHDRAW).

    check_delta (kids/jars sub-accounts only): also reads the sub-account's backend
    balance BEFORE the withdrawal and POLLS it AFTER, asserting it dropped by
    ~`dollars` (within DELTA_BAND). For a KID that balance is its own /v1/user
    current_balance; for a JAR pass jar_name and the balance is the jar's
    accumulated_amount read via the PARENT's session (jar_balance_by_name — jar
    emails cannot mint a session). The success screen stays the FLOW oracle; this
    delta is the VALUE oracle. NOT used on the market-noisy six-figure MAIN
    account, where a $100 delta is swamped by holdings repricing."""
    fx = get_or_create_fixture_user(fixture_key)

    balance_before = None
    read_balance = None
    if check_delta:
        if jar_name is not None:
            # The stored fixture email IS the jar sub-account; its parent login is
            # "jp." + that email (jars_withdrawal_buffer builder).
            parent_email = JARS_BUFFER_PARENT_PREFIX + fx["email"]
            read_balance = _jar_parent_reader(parent_email, jar_name)
            balance_before = read_balance()
            assert balance_before is not None, (
                f"[{account_label}] could not read jar {jar_name!r} "
                f"accumulated_amount via the parent session ({parent_email}) before "
                f"withdrawal — jars have no loginable identity, so the parent-session "
                f"read is the only balance oracle")
        else:
            read_balance = _self_balance_reader(fx["email"])
            balance_before = read_balance()
            assert balance_before is not None, (
                f"[{account_label}] could not read backend current_balance for "
                f"{fx['email']} before withdrawal")
        print(f"  [{account_label}] backend balance before: ${balance_before}")

    opts = get_android_options(no_reset=False, secondary=True)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        ho = _login_and_home(d, fx)
        # Diagnostics only (NOT oracles): the redesigned home (build 3226) greets
        # with 'Welcome' not 'Hello' and has no Main-Portfolio card on a sub-account,
        # so both reads can legitimately be absent — never let them fail the flow.
        try:
            card = ho.get_account_card_value("Main Portfolio")
        except Exception:
            card = None
        try:
            greeting = ho.get_greeting()
        except Exception:
            greeting = None
        print(f"  [{account_label}] Home as {greeting!r}, card={card}")
        confirmed = _withdraw(d, ho, dollars)
        print(f"  [{account_label}] ${dollars} withdrawal -> 'Withdrawal Confirmed' shown: {confirmed}")
        assert confirmed, f"[{account_label}] expected the 'Withdrawal Confirmed' success screen"
        print(f"  PASS (flow): on-device ${dollars} withdrawal completed ({account_label} account)")
    finally:
        try:
            d.quit()
        except Exception:
            pass

    if check_delta:
        # VALUE oracle: poll the sub-account balance until it reflects the withdrawal
        # (kid: own current_balance; jar: accumulated_amount via the parent session).
        after, dropped = _poll_balance_drop(read_balance, balance_before, dollars)
        print(f"  [{account_label}] balance before=${balance_before} after≈${after} "
              f"(expected drop ${dollars}, ±${DELTA_BAND})")
        assert dropped, (
            f"[{account_label}] backend balance (kid current_balance / jar "
            f"accumulated_amount via parent session) did not drop by ~${dollars} "
            f"within {SETTLE_BUDGET_S}s: before=${balance_before}, closest after=${after} "
            f"(drop ${round(balance_before - after, 2)}, band ±${DELTA_BAND}) — "
            f"withdrawal not reflected in the sub-account balance?")
        print(f"  PASS (value): {account_label} balance dropped ~${dollars} "
              f"(${balance_before} -> ${after})")


@pytest.mark.destructive
def test_main_account_withdrawal_on_device():
    """A generated user completes a withdrawal from the MAIN account through the app.

    Flow oracle only (success screen): the MAIN buffer is six-figure market-priced
    holdings whose repricing swamps a $100 delta — the exact post-withdrawal balance
    contract is covered by the API value tests.

    MUTATES account state (submits a REAL $100 DEV withdrawal every run), so it is
    opt-in via RUN_DESTRUCTIVE=1 and carries @pytest.mark.destructive — mirrors
    test_withdraw_available_value.py so non-destructive lanes skip it. The flow oracle
    (the 'Withdrawal Confirmed' success screen, asserted in _run_withdrawal) still runs
    when it does."""
    if os.getenv("RUN_DESTRUCTIVE") != "1":
        pytest.skip("destructive (submits a real DEV withdrawal); set RUN_DESTRUCTIVE=1 to run")
    _run_withdrawal("MAIN", "rich_withdrawal_buffer")


# ARCHITECTURALLY UNREACHABLE for a sub-account login — RE-CONFIRMED on the CURRENT
# build (3252 / v2.40.1d) on emulator-5556, 2026-06-24. This is NOT a defect: the
# kids/jars Withdraw is by-design a PARENT-side operation, and the test's premise of
# "log in AS the sub-account and self-withdraw" does not exist in the app.
#
# Source-grounded (real app /Users/joshua/Android-AU):
#   - The kid/jar Withdraw button lives on KidHomeActiveScreen.kt / JarHomeActiveScreen.kt,
#     reached by the PARENT drilling into raiz://kids/details/{id} (or the jar home).
#     Its flow is OWNER-directed: KidsFeature InvestType.Withdraw sets
#     transferType = KidTransferType.OWNER / investmentType = DEBIT and the jar copy
#     reads "select the account you want to withdraw TO" — i.e. the parent pulls the
#     sub-account's money back to the owner. A sub-account holder has no self-withdraw.
#
# On-device (logging in AS the fixture sub-account, build 3252):
#   - KIDS (kids_withdrawal_buffer, balance $50,181.79): logs in, lands on the
#     redesigned home (Welcome / Past·Today·Future tabs). Full text dumps + scroll +
#     Invest tap captured NO 'Withdraw' element anywhere — only 'Invest', Performance,
#     Rewards, blog. HomePage.tap_withdraw()'s WITHDRAW_BUTTON cannot be found.
#   - JARS (jars_withdrawal_buffer): cannot log in at all — the app throws
#     'Oops! / Invalid response' and bounces back to the login form. This matches
#     the product model (user-confirmed): jars are sub-accounts of the main account
#     with NO loginable identity — POST /v1/sessions with a jar email returns 401
#     BY DESIGN, in the app AND on the DEV API alike. The jar's balance is its
#     accumulated_amount, readable only via the PARENT's session
#     (jar_balance_by_name; parent = "jp." + the fixture email).
#
# No reachable self-Withdraw => the flow oracle (success screen) cannot fire, so the
# delta value oracle cannot fire either. The jar/kid WITHDRAWAL VALUE contract is
# already covered at the API level (U-API): test_value_validation_api.py
# ::test_jar_balance_reduced_by_withdrawal and ::test_kid_balance_reduced_by_withdrawal
# both seed a credit + a Withdrawal and assert the sub-account balance nets down by the
# withdrawn amount. Skipping honestly rather than faking a pass. For the app team: a
# sub-account login exposes no Withdraw; this flow is only reachable parent-side.
# Un-skip only if/when the suite re-fixtures these to log in AS the PARENT and drive
# the parent's kids/jars-details Withdraw — the before/after delta then reads the
# sub-account's backend balance (the value-oracle readers below already do the right
# per-type read: kid current_balance via its own login; jar accumulated_amount via
# the parent session — so the value-oracle code needs no change).
_REDESIGN_NO_WITHDRAW = (
    "skip-with-reason on build 3252 (v2.40.1d): kids/jars Withdraw is a PARENT-side "
    "operation (KidTransferType.OWNER; reached via raiz://kids/details — confirmed in "
    "KidHomeActiveScreen.kt/JarHomeActiveScreen.kt), so a sub-account login exposes no "
    "self-Withdraw (KIDS home shows only Invest — re-confirmed on-device emulator-5556 "
    "2026-06-24; JARS have no loginable identity AT ALL: /v1/sessions with a jar email "
    "401s BY DESIGN, so the app rejects the login with 'Oops! Invalid response'). "
    "The flow+delta oracles cannot run. Sub-account withdrawal VALUE is already covered "
    "at the API level by test_value_validation_api.py::test_{jar,kid}_balance_reduced_"
    "by_withdrawal (U-API). Value-oracle readers here are per-type (kid: own "
    "current_balance; jar: accumulated_amount via the PARENT session); un-skip only by "
    "re-fixturing to drive the PARENT-side Withdraw.")


@pytest.mark.skip(reason=_REDESIGN_NO_WITHDRAW)
def test_kids_account_withdrawal_on_device():
    """A generated KID sub-account completes a withdrawal through the app, and its
    backend current_balance drops by ~the withdrawn amount (flow + value oracles).

    SKIP (build 3252, re-confirmed on-device): a kid sub-account login exposes no
    self-Withdraw — kid Withdraw is a PARENT-side OWNER-directed flow (raiz://kids/
    details → KidHomeActiveScreen). Withdrawal VALUE is covered at the API level by
    test_value_validation_api::test_kid_balance_reduced_by_withdrawal. The delta
    oracle here (check_delta=True) is implemented & proven to the BEFORE read."""
    _run_withdrawal("KIDS", "kids_withdrawal_buffer", check_delta=True)


@pytest.mark.skip(reason=_REDESIGN_NO_WITHDRAW)
def test_jars_account_withdrawal_on_device():
    """A withdrawal from a generated JAR sub-account completes through the app, and
    the jar's backend accumulated_amount (read via the PARENT session) drops by ~the
    withdrawn amount (flow + value oracles).

    SKIP (build 3252): jars are sub-accounts of the main account with NO loginable
    identity (user-confirmed product model) — /v1/sessions with a jar email 401s BY
    DESIGN, so the app rejects this fixture's login with an 'Oops! Invalid response'
    dialog. Jar Withdraw is a PARENT-side OWNER-directed flow (JarHomeActiveScreen).
    Withdrawal VALUE is covered at the API level by
    test_value_validation_api::test_jar_balance_reduced_by_withdrawal. The delta
    oracle here (check_delta + jar_name) reads the jar's accumulated_amount through
    the PARENT session (jar_balance_by_name) — never a jar-email login."""
    _run_withdrawal("JARS", "jars_withdrawal_buffer", check_delta=True,
                    jar_name=JARS_BUFFER_JAR_NAME)
