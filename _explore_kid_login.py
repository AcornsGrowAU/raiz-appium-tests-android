import os, time
os.environ.setdefault("ANDROID_UDID","emulator-5554"); os.environ.setdefault("APPIUM_HOST","http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.home_page import HomePage
from utils.genuser_fixtures import get_or_create_fixture_user

fx = get_or_create_fixture_user("kids_withdrawal_buffer")
print("KID fixture:", fx["email"])
opts = get_android_options(no_reset=False); opts.udid="emulator-5554"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)
def texts():
    return [t.text for t in d.find_elements(AppiumBy.XPATH,"//android.widget.TextView") if t.text and t.text.strip()]
def clk():
    out=[]
    for e in d.find_elements(AppiumBy.XPATH,"//*[@clickable='true']"):
        try:
            lab=(e.text or "").strip() or (e.get_attribute("content-desc") or "").strip()
            if lab: out.append(lab)
        except Exception: pass
    return out
try:
    time.sleep(5)
    sp,lo,ho=SplashPage(d),LoginPage(d),HomePage(d)
    if sp.is_present_now(sp.TAGLINE): sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"], fx["password"]); time.sleep(8)
    for step in range(6):
        print(f"\n[step {step}] on_home={ho.is_present_now(ho.TOTAL_VALUE_LABEL)}")
        print("  texts:", texts()[:16])
        print("  clickables:", clk()[:16])
        d.save_screenshot(f"/tmp/kid_{step}.png")
        if ho.is_present_now(ho.TOTAL_VALUE_LABEL):
            print("  -> reached HOME"); break
        time.sleep(4)
finally:
    try: d.quit()
    except Exception: pass
