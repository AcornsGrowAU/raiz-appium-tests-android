"""Map the full residual onboarding flow (portfolio select -> investment -> home),
driving a pds_accepted generated user and dumping each screen so we can script it."""
import os, time
os.environ["ANDROID_UDID"] = "emulator-5556"
os.environ["APPIUM_HOST"] = "http://127.0.0.1:4723"
from appium import webdriver as awd
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.home_page import HomePage

EMAIL = open("/tmp/onb_email.txt").read().strip()
PWD = "Pass1234"
opts = get_android_options(no_reset=False); opts.udid = "emulator-5556"
d = awd.Remote(command_executor="http://127.0.0.1:4723", options=opts)

def clickables():
    out = []
    for e in d.find_elements(AppiumBy.XPATH, "//*[@clickable='true']"):
        try:
            t = (e.text or "").strip() or (e.get_attribute("content-desc") or "").strip()
            cls = (e.get_attribute("class") or "").split(".")[-1]
            rid = (e.get_attribute("resource-id") or "").split("/")[-1]
            out.append((t, cls, rid, e))
        except Exception:
            pass
    return out

def heading():
    return [t.text for t in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if t.text][:4]

def tap(e):
    try: e.click(); return True
    except Exception: return False

def tap_text(*opts):
    for o in opts:
        for e in d.find_elements(AppiumBy.XPATH, f"//*[@text='{o}'] | //*[contains(@text,'{o}')]"):
            if tap(e): return o
    return None

try:
    time.sleep(5)
    splash, login, home = SplashPage(d), LoginPage(d), HomePage(d)
    if splash.is_present_now(splash.TAGLINE):
        splash.tap_log_in(); time.sleep(2)
    login.login(EMAIL, PWD); print("logged in", EMAIL); time.sleep(7)
    for step in range(14):
        if home.is_present_now(home.TOTAL_VALUE_LABEL):
            print(f"[{step}] HOME reached"); break
        src = d.page_source.lower()
        cl = clickables()
        ids = [c[2] for c in cl if c[2]]
        print(f"[{step}] heading={heading()} | clickable ids={ids[:8]} | texts={[c[0] for c in cl if c[0]][:8]}")
        d.save_screenshot(f"/tmp/onb_{step}.png")
        acted = None
        # dismiss coachmark/popups first (they overlay and block taps)
        if "got it" in src or "scroll tabs" in src:
            acted = tap_text("Got it")
        # account checklist (round-up/funding/personal) -> Skip the round-up step
        if not acted and any(s in src for s in ("complete your raiz invest", "link a round-up", "follow these steps")):
            acted = tap_text("Skip")
        # portfolio DETAIL screen -> ensure the assigned portfolio is selected, then confirm
        if not acted and "select as your portfolio" in src:
            tap_text("Aggressive"); time.sleep(1)
            acted = tap_text("Select as your portfolio")
        # portfolio INTRO -> open the picker
        if not acted and any("btnselectyourportfolio" in (c[2] or '').lower() for c in cl):
            for c in cl:
                if "btnselectyourportfolio" in (c[2] or '').lower():
                    acted = "btnSelectYourPortfolio" if tap(c[3]) else None; break
        # initial-investment prompt -> SKIP (the user already has a seeded balance)
        if not acted and ("initial investment" in src or "ready to start investing" in src):
            acted = tap_text("Skip")
        # generic forward (Skip BEFORE Next; no 'Invest' — matches the 'Raiz Invest' heading)
        if not acted:
            acted = tap_text("Skip", "Confirm", "Continue", "Done", "Save", "Got it",
                             "Agree", "I agree", "I consent", "Maybe later", "Not now")
        if not acted:
            print(f"[{step}] NO ACTION — stuck. clickables:")
            for c in cl: print("     ", c[1], repr(c[0]), c[2])
            break
        print(f"[{step}] -> tapped {acted}")
        time.sleep(4)
    print("FINAL heading:", heading())
    if home.is_present_now(home.TOTAL_VALUE_LABEL):
        print("HOME total:", home.get_total_value())
    d.save_screenshot("/tmp/onb_final.png")
finally:
    try: d.quit()
    except Exception: pass
