"""Map the in-app MAIN-account Withdraw flow (amount input model, confirm control,
post-withdraw balance behaviour) using the rich_withdrawal_buffer fixture (~$321k)."""
import os, time
os.environ.setdefault("ANDROID_UDID", "emulator-5554")
os.environ.setdefault("APPIUM_HOST", "http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded
from utils.genuser_api import current_balance

fx = get_or_create_fixture_user("presence_funded")
print("fixture:", fx["email"], "onboarded:", fx.get("onboarded"), "API balance:", current_balance(fx["email"]))
opts = get_android_options(no_reset=False); opts.udid = "emulator-5554"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)

def texts():
    return [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text and t.text.strip()]

def clickables():
    out = []
    for e in d.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
        try:
            lab = (e.text or "").strip() or (e.get_attribute("content-desc") or "").strip()
            rid = (e.get_attribute("resource-id") or "").split("/")[-1]
            out.append(f"{lab or rid}")
        except Exception:
            pass
    return out

def tap_text(*opts):
    for o in opts:
        for e in d.find_elements(AppiumBy.XPATH, f"//*[@text='{o}']"):
            try:
                e.click(); return o
            except Exception:
                pass
    return None

try:
    time.sleep(5)
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"], fx["password"]); time.sleep(7)
    onb = OnboardingPage(d)
    if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
        onb.complete(); mark_onboarded(fx["key"]); print("onboarded:", onb.path)
    print("HOME Main Portfolio card:", ho.get_account_card_value("Main Portfolio"))
    ho.tap_withdraw(); time.sleep(4)
    print("\nWITHDRAW screen texts:", texts()[:14])
    print("WITHDRAW clickables:", clickables()[:20])
    d.save_screenshot("/tmp/wd_0.png")
    # enter an amount via the keypad — try '5' then '0' '0' to see the input model
    for k in ("5", "0", "0"):
        tap_text(k); time.sleep(0.6)
    print("\nafter typing 5,0,0 -> texts:", texts()[:14])
    d.save_screenshot("/tmp/wd_1.png")
    # look for a confirm/forward control
    print("forward buttons present:", [b for b in ("Withdraw", "Confirm", "Next", "Continue", "Review", "Submit") if d.find_elements(AppiumBy.XPATH, f"//*[@text='{b}']")])
finally:
    try: d.quit()
    except Exception: pass
