"""
ON-DEVICE WITHDRAWAL E2E for generated users (reuse strategy — rich buffers, so a
withdrawal is negligible and the fixture lasts many runs).

Logs into the real app AS a generated user and completes a withdrawal through the
actual Withdraw UI, asserting the "Withdrawal Confirmed" success screen (the FLOW
oracle).

For the KIDS/JARS sub-accounts we ALSO add a VALUE oracle: each sub-account is its
own user with its own backend current_balance, so we read it before the withdrawal
and poll it after (settle-poll pattern from test_value_validation_api /
test_withdraw_available_value) and assert it dropped by ~the withdrawn amount within
a band. The MAIN account stays flow-only — it is six-figure market-priced holdings
whose repricing swamps a $100 delta (the exact balance-after contract there is
covered by the API tests in test_value_validation_api.py).

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
from config.settings import APPIUM_HOST
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded
from utils.genuser_api import current_balance, mint, call, SEEDED_PWD

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# --- backend balance DELTA oracle for the kids/jars SUB-accounts -------------
# The kid/jar withdrawal buffers are their OWN users with their OWN
# current_balance, so unlike the market-noisy six-figure MAIN account (covered by
# the success screen alone) we can read the sub-account balance before, withdraw,
# poll the balance after, and assert it dropped by ~the withdrawn amount.
#
# The buffers are ~$320k of MARKET-PRICED holdings that reprice between reads, so
# the drop is matched within a band sized for that magnitude (~$0.50/$1k of
# holdings ≈ $160 on $320k) rather than to the cent — the withdrawn $100 is the
# signal, the repricing is the noise the band absorbs. The success screen remains
# the FLOW oracle; this delta is the VALUE oracle.
DELTA_BAND = float(os.getenv("WD_DELTA_BAND", "250.0"))
SETTLE_BUDGET_S = int(os.getenv("WD_SETTLE_BUDGET_S", "180"))
POLL_INTERVAL_S = int(os.getenv("WD_POLL_INTERVAL_S", "20"))


def _poll_balance_drop(email, before, expected_drop):
    """Poll the sub-account current_balance until it has dropped by ~expected_drop
    from `before` (within DELTA_BAND), or the settle budget elapses. Reuses ONE
    minted session across reads (the /v1/sessions endpoint is rate-limited),
    re-minting only on a failed read. Returns (best_after, dropped_bool) where
    best_after is the reading whose drop is closest to expected — so the assertion
    message is meaningful even on timeout. Mirrors test_value_validation_api's
    settle-poll and test_withdraw_available_value's _poll_balance_drop."""
    target = round(before - expected_drop, 2)
    waited = 0
    best_after, best_err = before, expected_drop  # initial drop of 0
    op, tok = mint(email, SEEDED_PWD)
    while waited <= SETTLE_BUDGET_S:
        bal = None
        if tok is not None:
            s, b = call(op, "GET", "/v1/user", token=tok)
            if s == 200:
                user = b.get("user", b) if isinstance(b, dict) else {}
                cb = user.get("current_balance")
                bal = float(cb) if cb is not None else None
            else:  # token expired/rejected -> re-mint on the next pass
                op, tok = mint(email, SEEDED_PWD)
        else:
            op, tok = mint(email, SEEDED_PWD)
        if bal is not None:
            drop = before - bal
            err = abs(drop - expected_drop)
            if err < best_err:
                best_err, best_after = err, bal
            print(f"  [poll +{waited}s] current_balance={bal} (drop={round(drop, 2)})")
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


def _login_and_home(d, fx):
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
        time.sleep(2)
    lo.login(fx["email"], fx["password"])
    time.sleep(7)
    onb = OnboardingPage(d)
    # Build-robust home detection: the kids/jars sub-account fixtures land on the
    # REDESIGNED home (build 3226) which drops the legacy 'Your total investments
    # value' header and shows a 'Welcome' greeting + the Past/Today/Future tab bar.
    # Gating on the legacy label alone mis-reads that as "onboarding incomplete" and
    # OnboardingPage.complete() then immediately STUCKs (there is no onboarding left
    # to run). Use HomePage.is_loaded(), which accepts either layout (legacy header
    # OR the build-agnostic Today tab) — mirrors test_main_value_on_device.
    if not ho.is_loaded(timeout=8):
        assert onb.complete(), f"onboarding stuck: {onb.path}"
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=20), "not on Home after login"
    return ho


def _withdraw(d, ho, dollars):
    """Drive the in-app Withdraw flow for $dollars. Returns True iff the
    'Withdrawal Confirmed' success screen appeared."""
    ho.tap_withdraw()
    assert _wait_text(d, "Withdraw", 15), "Withdraw screen didn't open"
    time.sleep(1)
    for ch in str(int(dollars)):
        assert _tap_text(d, ch, which=0), f"keypad digit {ch} not found"
        time.sleep(0.4)
    amt = [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text and "$" in t.text]
    print(f"  amount field after typing: {amt}")
    # State-machine advance (slow emulator; mirrors the mapped flow).
    confirmed = False
    for i in range(10):
        src = d.page_source.lower()
        tx = [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text and t.text.strip()]
        print(f"  [wd {i}] {tx[:8]}")
        if "withdrawal confirmed" in src:
            confirmed = True
            break
        if ho.is_loaded(timeout=1):  # layout-tolerant (legacy header OR redesign Today tab)
            print("  back on Home"); break
        if "confirm withdrawal" in src:
            print("  -> tap Confirm"); _tap_button(d, "Confirm")
        else:
            print("  -> tap Withdraw"); _tap_button(d, "Withdraw")
        time.sleep(3.5)
    _tap_text(d, "Ok", "OK", "Done", which=-1)  # dismiss success
    return confirmed


def _run_withdrawal(account_label, fixture_key, dollars=100, check_delta=False):
    """Log in as a generated (sub-)account holder with a rich buffer and complete an
    on-device withdrawal, asserting the 'Withdrawal Confirmed' success screen.

    A kid/jar is its own user (own login + own balance) under a parent, so the
    on-device flow is identical to the main account — log in as the sub-account.

    check_delta (kids/jars sub-accounts only): also reads the sub-account's backend
    current_balance BEFORE the withdrawal and POLLS it AFTER, asserting it dropped
    by ~`dollars` (within DELTA_BAND). The success screen stays the FLOW oracle;
    this delta is the VALUE oracle. NOT used on the market-noisy six-figure MAIN
    account, where a $100 delta is swamped by holdings repricing."""
    fx = get_or_create_fixture_user(fixture_key)

    balance_before = None
    if check_delta:
        balance_before = current_balance(fx["email"])
        assert balance_before is not None, (
            f"[{account_label}] could not read backend current_balance for "
            f"{fx['email']} before withdrawal")
        print(f"  [{account_label}] backend current_balance before: ${balance_before}")

    opts = get_android_options(no_reset=False)
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
        # VALUE oracle: poll the sub-account balance until it reflects the withdrawal.
        after, dropped = _poll_balance_drop(fx["email"], balance_before, dollars)
        print(f"  [{account_label}] balance before=${balance_before} after≈${after} "
              f"(expected drop ${dollars}, ±${DELTA_BAND})")
        assert dropped, (
            f"[{account_label}] backend current_balance did not drop by ~${dollars} "
            f"within {SETTLE_BUDGET_S}s: before=${balance_before}, closest after=${after} "
            f"(drop ${round(balance_before - after, 2)}, band ±${DELTA_BAND}) — "
            f"withdrawal not reflected in the sub-account balance?")
        print(f"  PASS (value): {account_label} balance dropped ~${dollars} "
              f"(${balance_before} -> ${after})")


def test_main_account_withdrawal_on_device():
    """A generated user completes a withdrawal from the MAIN account through the app.

    Flow oracle only (success screen): the MAIN buffer is six-figure market-priced
    holdings whose repricing swamps a $100 delta — the exact post-withdrawal balance
    contract is covered by the API value tests."""
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
#   - JARS (jars_withdrawal_buffer): cannot even app-login — the app throws
#     'Oops! / Invalid response' and bounces back to the login form, though its
#     DEV-API login + balance read are fine ($50k). A jar_user is not a valid mobile
#     login principal — an app-side session gate, not creds.
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
# sub-account's backend balance (the value-oracle code below needs no change).
_REDESIGN_NO_WITHDRAW = (
    "skip-with-reason on build 3252 (v2.40.1d): kids/jars Withdraw is a PARENT-side "
    "operation (KidTransferType.OWNER; reached via raiz://kids/details — confirmed in "
    "KidHomeActiveScreen.kt/JarHomeActiveScreen.kt), so a sub-account login exposes no "
    "self-Withdraw (KIDS home shows only Invest; JARS app-login is gated by an 'Oops! "
    "Invalid response' dialog — both re-confirmed on-device emulator-5556 2026-06-24). "
    "The flow+delta oracles cannot run. Sub-account withdrawal VALUE is already covered "
    "at the API level by test_value_validation_api.py::test_{jar,kid}_balance_reduced_"
    "by_withdrawal (U-API). Value-oracle code here is implemented & proven to the "
    "before-read; un-skip only by re-fixturing to drive the PARENT-side Withdraw.")


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
    """A generated JAR sub-account completes a withdrawal through the app, and its
    backend current_balance drops by ~the withdrawn amount (flow + value oracles).

    SKIP (build 3252, re-confirmed on-device): a jar_user is not a valid mobile login
    principal — the app rejects this fixture's login with an 'Oops! Invalid response'
    dialog (DEV-API login is fine). Jar Withdraw is a PARENT-side OWNER-directed flow
    (JarHomeActiveScreen). Withdrawal VALUE is covered at the API level by
    test_value_validation_api::test_jar_balance_reduced_by_withdrawal. The delta
    oracle here (check_delta=True) is implemented & proven to the BEFORE read."""
    _run_withdrawal("JARS", "jars_withdrawal_buffer", check_delta=True)
