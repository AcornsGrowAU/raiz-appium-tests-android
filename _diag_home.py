import os, time
os.environ.setdefault("ANDROID_UDID","emulator-5556"); os.environ.setdefault("APPIUM_HOST","http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.home_page import HomePage
from pages.onboarding_page import OnboardingPage
from utils.genuser_fixtures import get_or_create_fixture_user
fx=get_or_create_fixture_user("presence_funded")
opts=get_android_options(no_reset=False); opts.udid="emulator-5556"
d=awd.Remote("http://127.0.0.1:4723",options=opts)
def texts(): return [t.text for t in d.find_elements(AppiumBy.XPATH,"//android.widget.TextView") if t.text and t.text.strip()]
try:
    time.sleep(5); sp,lo,ho=SplashPage(d),LoginPage(d),HomePage(d)
    if sp.is_present_now(sp.TAGLINE): sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"],fx["password"]); time.sleep(8)
    print("POST-LOGIN texts:", texts()[:18])
    print("TOTAL_VALUE_LABEL present:", ho.is_present_now(ho.TOTAL_VALUE_LABEL))
    if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
        onb=OnboardingPage(d); onb.complete(); print("onboard path:", getattr(onb,'path',None))
    try: ho.dismiss_modal(); time.sleep(2); print("dismissed modal")
    except Exception as e: print("dismiss err:", e)
    print("AFTER-DISMISS texts:", texts()[:18])
    print("Main Portfolio card:", ho.get_account_card_value("Main Portfolio"))
    print("WITHDRAW_BUTTON present:", bool(d.find_elements(*ho.WITHDRAW_BUTTON)))
    d.save_screenshot("/tmp/diag_home.png")
finally:
    try: d.quit()
    except: pass
