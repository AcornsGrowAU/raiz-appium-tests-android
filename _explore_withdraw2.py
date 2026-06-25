"""Map the FULL main Withdraw flow to completion (amount -> Withdraw -> confirm/PIN/
success), on the rich_withdrawal_buffer (absorbs any amount). Dumps each step."""
import os, time
os.environ.setdefault("ANDROID_UDID", "emulator-5554"); os.environ.setdefault("APPIUM_HOST", "http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.pin_page import PinPage
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded
from utils.genuser_api import current_balance

fx = get_or_create_fixture_user("rich_withdrawal_buffer")
print("fixture:", fx["email"], "onboarded:", fx.get("onboarded"), "API balance:", current_balance(fx["email"]))
opts = get_android_options(no_reset=False); opts.udid = "emulator-5554"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)

def texts():
    return [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text and t.text.strip()]

def tap_text(*o):
    for x in o:
        for e in d.find_elements(AppiumBy.XPATH, f"//*[@text='{x}']"):
            try: e.click(); return x
            except Exception: pass
    return None

try:
    time.sleep(5)
    sp, lo, ho, pin = SplashPage(d), LoginPage(d), HomePage(d), PinPage(d)
    if sp.is_present_now(sp.TAGLINE): sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"], fx["password"]); time.sleep(7)
    onb = OnboardingPage(d)
    if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
        ok = onb.complete();
        if ok: mark_onboarded(fx["key"])
        print("onboard:", onb.path)
    print("Main Portfolio card BEFORE:", ho.get_account_card_value("Main Portfolio"))
    ho.tap_withdraw(); time.sleep(4)
    print("WITHDRAW open:", texts()[:12])
    for k in ("1", "0", "0"): tap_text(k); time.sleep(0.5)   # $100
    print("after $100:", [t for t in texts() if "$" in t])
    d.save_screenshot("/tmp/wd2_amount.png")
    # tap the Withdraw confirm button (there are two 'Withdraw' texts: title + button; click the lower one)
    btns = d.find_elements(AppiumBy.XPATH, "//*[@text='Withdraw']")
    print(f"'Withdraw' elements: {len(btns)}")
    if btns:
        try: btns[-1].click()
        except Exception as e: print("confirm tap err:", e)
    time.sleep(4)
    # post-confirm: map up to 6 steps (PIN / confirm dialog / success)
    for step in range(6):
        tx = texts(); src = d.page_source.lower()
        print(f"[post {step}] {tx[:10]}")
        d.save_screenshot(f"/tmp/wd2_post{step}.png")
        if ho.is_present_now(ho.TOTAL_VALUE_LABEL): print("  -> back on HOME"); break
        if pin.is_present_now(pin.TITLE) or "enter your pin" in src or "enter pin" in src:
            print("  -> PIN screen; entering 0000");
            try: pin.enter_pin("0000")
            except Exception as e: print("   pin err:", e)
            time.sleep(3); continue
        a = tap_text("Confirm", "Withdraw", "Done", "Continue", "Ok", "Got it")
        print(f"  -> tapped {a}"); time.sleep(3)
        if not a: break
    print("FINAL:", texts()[:12])
    print("Main Portfolio card AFTER:", ho.get_account_card_value("Main Portfolio") if ho.is_present_now(ho.TOTAL_VALUE_LABEL) else "(not home)")
finally:
    try: d.quit()
    except Exception: pass
