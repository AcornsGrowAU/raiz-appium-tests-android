"""Drive a GENERATED user through the full first-login flow on the emulator and
read its balance on Home. Confirms on-device generated-user testing is viable."""
import os, time
os.environ["ANDROID_UDID"] = "emulator-5556"
os.environ["APPIUM_HOST"] = "http://127.0.0.1:4723"
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.home_page import HomePage
from pages.pin_page import PinPage

GEN_EMAIL = open("/tmp/onb_email.txt").read().strip()
GEN_PWD = "Pass1234"
PIN = "0000"

opts = get_android_options(no_reset=False)
opts.udid = "emulator-5556"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)

def texts():
    out = []
    for e in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView"):
        try:
            if e.text and e.text.strip():
                out.append(e.text.strip())
        except Exception:
            pass
    return out

def tap_text(t):
    els = d.find_elements(AppiumBy.XPATH,
        f"//*[@text='{t}'] | //*[contains(@text,'{t}')]")
    for e in els:
        try:
            e.click(); return True
        except Exception:
            pass
    return False

try:
    time.sleep(5)
    splash, login, home, pin = SplashPage(d), LoginPage(d), HomePage(d), PinPage(d)
    if splash.is_present_now(splash.TAGLINE):
        splash.tap_log_in(); time.sleep(2)
    login.login(GEN_EMAIL, GEN_PWD)
    print(f"submitted login for {GEN_EMAIL}")
    time.sleep(7)

    path = []
    for step in range(10):
        if home.is_present_now(home.TOTAL_VALUE_LABEL):
            path.append("HOME"); break
        src = d.page_source.lower()
        tx = texts()
        if "i consent" in src:
            path.append("consent"); tap_text("I consent"); time.sleep(4); continue
        if any(k in src for k in ("create a pin", "set up your pin", "choose a pin",
                                  "create your pin", "set a pin", "confirm your pin",
                                  "re-enter", "enter a pin")) or pin.is_present_now(pin.TITLE):
            path.append("pin-entry");
            try: pin.enter_pin(PIN)
            except Exception as e: print("pin enter err:", e)
            time.sleep(3); continue
        # generic "continue/next/get started/done/skip"
        tapped = False
        for b in ("Continue", "Next", "Get started", "Done", "Skip", "Maybe later", "Not now", "Confirm"):
            if tap_text(b):
                path.append(f"tap:{b}"); tapped = True; time.sleep(3); break
        if not tapped:
            path.append(f"STUCK: {tx[:8]}"); break
        d.save_screenshot(f"/tmp/flow_{step}.png")

    print("PATH:", " -> ".join(path))
    print("FINAL screen:", texts()[:18])
    if home.is_present_now(home.TOTAL_VALUE_LABEL):
        print("HOME total value:", home.get_total_value())
        for lbl in ("Main Portfolio", "Jars", "Kids"):
            try: print(f"  card {lbl}:", home.get_account_card_value(lbl))
            except Exception: pass
    d.save_screenshot("/tmp/genuser_final.png")
    print("final screenshot -> /tmp/genuser_final.png")
finally:
    try: d.quit()
    except Exception: pass
