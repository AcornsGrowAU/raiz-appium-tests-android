"""Find a screen that renders the generated user's CURRENT BALANCE immediately
(the Home 'total investments value' tile lags / ignores with_balance). Reuses the
onboarded presence_funded fixture (~$643.54)."""
import os, time
os.environ.setdefault("ANDROID_UDID", "emulator-5556")
os.environ.setdefault("APPIUM_HOST", "http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from utils.genuser_fixtures import get_or_create_fixture_user
from utils.genuser_api import current_balance

fx = get_or_create_fixture_user("presence_funded")
print("fixture:", fx["email"], "API balance:", current_balance(fx["email"]))
opts = get_android_options(no_reset=False); opts.udid = "emulator-5556"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)

def money_texts():
    return [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView")
            if t.text and "$" in t.text]

try:
    time.sleep(5)
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"], fx["password"]); time.sleep(7)
    OnboardingPage(d).complete()
    assert ho.is_present_now(ho.TOTAL_VALUE_LABEL), "not on home"
    print("HOME $-texts:", money_texts())
    for action, name in ((ho.tap_withdraw, "WITHDRAW"), (ho.tap_add_funds, "ADD_FUNDS")):
        try:
            ho._open_deep_link if False else None
            action(); time.sleep(4)
            print(f"{name} $-texts:", money_texts())
            print(f"{name} headings:", [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text][:6])
            d.save_screenshot(f"/tmp/balscreen_{name}.png")
            d.back(); time.sleep(3)
            # re-open home if needed
            if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
                from utils.deep_links import DeepLinks
                DeepLinks.open(d, DeepLinks.HOME); time.sleep(3)
        except Exception as e:
            print(f"{name} error: {e}")
finally:
    try: d.quit()
    except Exception: pass
