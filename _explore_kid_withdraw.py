import os, time
os.environ.setdefault("ANDROID_UDID","emulator-5554"); os.environ.setdefault("APPIUM_HOST","http://127.0.0.1:4723")
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from utils.genuser_fixtures import get_or_create_fixture_user

fx = get_or_create_fixture_user("kids_withdrawal_buffer")
print("KID fixture:", fx["email"])
opts = get_android_options(no_reset=False); opts.udid="emulator-5554"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)
W,H = d.get_window_size()["width"], d.get_window_size()["height"]
def dump(tag):
    print(f"\n===== {tag} =====")
    print("TEXTS:", [t.text for t in d.find_elements(AppiumBy.XPATH,"//android.widget.TextView") if t.text and t.text.strip()][:24])
    out=[]
    for e in d.find_elements(AppiumBy.XPATH,"//*[@clickable='true']"):
        try:
            lab=(e.text or "").strip() or (e.get_attribute("content-desc") or "").strip()
            rid=(e.get_attribute("resource-id") or "").split("/")[-1]
            out.append(f"{lab or rid or '?'}")
        except Exception: pass
    print("CLICKABLE:", out[:30])
    src=d.page_source.lower()
    print("has 'withdraw':", "withdraw" in src, "| has 'manage':", "manage" in src)
def scroll_down():
    d.swipe(W//2, int(H*0.75), W//2, int(H*0.30), 600); time.sleep(1.5)
def tap_text(*o):
    for x in o:
        for e in d.find_elements(AppiumBy.XPATH,f"//*[@text='{x}']"):
            try: e.click(); return x
            except Exception: pass
    return None
try:
    time.sleep(5)
    sp,lo=SplashPage(d),LoginPage(d)
    if sp.is_present_now(sp.TAGLINE): sp.tap_log_in(); time.sleep(2)
    lo.login(fx["email"], fx["password"]); time.sleep(8)
    dump("KID HOME (top)")
    scroll_down(); dump("KID HOME (scrolled 1)")
    scroll_down(); dump("KID HOME (scrolled 2)")
    # back to top, try the nav drawer (hamburger top-left)
    d.swipe(W//2, int(H*0.30), W//2, int(H*0.80), 600); time.sleep(1)
    try:
        d.find_element(AppiumBy.ACCESSIBILITY_ID,"Open navigation drawer").click(); time.sleep(2); dump("NAV DRAWER")
        d.back(); time.sleep(1)
    except Exception as e:
        print("no nav drawer accid:", e)
        # try tapping top-left coordinate (hamburger)
        d.tap([(40, 90)]); time.sleep(2); dump("AFTER top-left tap")
        d.back(); time.sleep(1)
    # tap the Invest card / text
    if tap_text("Invest"):
        time.sleep(3); dump("AFTER tap Invest")
finally:
    try: d.quit()
    except Exception: pass
