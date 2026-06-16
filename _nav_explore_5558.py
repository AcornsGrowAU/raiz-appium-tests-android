"""Navigation mapper for emulator-5558. One foreground Appium session.
Uses the project's proven conftest helpers for driver/login/PIN so the PIN
keypad (clickable parent View, not the TextView) is tapped correctly.
Explores deep-link areas + full nav drawer + full Settings.
"""
import os
import sys
import time
import json
import traceback

os.environ["ANDROID_UDID"] = "emulator-5558"
os.environ["APPIUM_HOST"] = "http://127.0.0.1:4725"
os.environ["ANDROID_SYSTEM_PORT"] = "8204"
os.environ["ANDROID_MJPEG_PORT"] = "7814"

ROOT = "/Users/joshua/Documents/Android test automation appium/raiz-appium-tests"
sys.path.insert(0, ROOT)

from appium.webdriver.common.appiumby import AppiumBy
from conftest import _create_driver, _ensure_logged_in, _open_deep_link
from pages.pin_page import PinPage
from pages.home_page import HomePage
from config.settings import TEST_PIN
from utils.deep_links import DeepLinks

RESULTS = {"deep_links": [], "drawer": [], "settings": [], "notes": []}


def log(m=""):
    sys.stdout.write(str(m) + "\n")
    sys.stdout.flush()


def texts(driver, limit=40):
    out = []
    try:
        els = driver.find_elements(AppiumBy.XPATH,
            "//android.widget.TextView[string-length(@text) > 0]")
        for el in els:
            try:
                t = (el.text or "").strip()
                if t and t not in out:
                    out.append(t)
            except Exception:
                pass
    except Exception:
        pass
    return out[:limit]


def clickable_labels(driver, limit=50):
    out = []
    try:
        els = driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']")
        for el in els:
            try:
                txt = (el.get_attribute("text") or "").strip()
                desc = (el.get_attribute("contentDescription") or "").strip()
                label = txt or desc
                if not label:
                    inner = el.find_elements(AppiumBy.XPATH, ".//android.widget.TextView")
                    inner_t = [i.text for i in inner[:2] if i.text]
                    label = " | ".join(inner_t)
                label = (label or "").strip()
                if label and label not in out:
                    out.append(label)
            except Exception:
                pass
    except Exception:
        pass
    return out[:limit]


def pin_if_needed(driver, timeout=2):
    pin = PinPage(driver)
    if pin.is_loaded(timeout=timeout):
        pin.enter_pin(TEST_PIN)
        driver._biometrics_pending = True
        time.sleep(1.3)
        return True
    return False


def dismiss_modal(driver):
    try:
        HomePage(driver).dismiss_modal()
    except Exception:
        pass
    for sel in ["//*[@content-desc='Close']", "//*[@text='Not now']",
                "//*[@text='Maybe later']", "//*[@text='Skip']"]:
        els = driver.find_elements(AppiumBy.XPATH, sel)
        if els:
            try:
                els[0].click(); time.sleep(0.4)
            except Exception:
                pass


def current_pkg(driver):
    try:
        return driver.current_package
    except Exception:
        return "?"


def header_title(driver, tx):
    for rid in ["//*[contains(@resource-id,'toolbar')]//android.widget.TextView",
                "//*[contains(@resource-id,'title')]"]:
        els = driver.find_elements(AppiumBy.XPATH, rid)
        for el in els:
            t = (el.text or "").strip()
            if t:
                return t
    return tx[0] if tx else "(no text)"


def left_app(driver):
    """True if we are no longer in the Raiz app (e.g. launcher/dialer)."""
    return current_pkg(driver) != "com.acornsau.android.development"


def reset_home(driver):
    DeepLinks.open(driver, DeepLinks.HOME)
    time.sleep(1.0)
    pin_if_needed(driver, timeout=2)
    time.sleep(0.7)
    dismiss_modal(driver)


def explore_deeplink(driver, name, link):
    rec = {"area": name, "link": link}
    try:
        _open_deep_link(driver, link)   # handles PIN re-auth
        time.sleep(1.3)
        dismiss_modal(driver)
        tx = texts(driver)
        rec["package"] = current_pkg(driver)
        rec["title"] = header_title(driver, tx)
        rec["texts"] = tx[:16]
        rec["clickables"] = clickable_labels(driver, 22)
        rec["is_webview"] = bool(driver.find_elements(AppiumBy.XPATH, "//android.webkit.WebView"))
        rec["left_app"] = left_app(driver)
        try:
            driver.back(); time.sleep(1.0)
            pin_if_needed(driver, 1.5); time.sleep(0.4)
            btx = texts(driver, 10)
            rec["back_package"] = current_pkg(driver)
            rec["back_lands_on"] = header_title(driver, btx)
            rec["back_texts"] = btx[:8]
        except Exception as e:
            rec["back_lands_on"] = f"ERR {e}"
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        log(traceback.format_exc()[:400])
    RESULTS["deep_links"].append(rec)
    log(f"[deeplink] {name}: pkg={rec.get('package')} title={rec.get('title')!r} "
        f"left_app={rec.get('left_app')} back={rec.get('back_lands_on')!r} err={rec.get('error')}")
    return rec


def open_drawer(driver):
    reset_home(driver)
    try:
        HomePage(driver).tap_hamburger()
        time.sleep(1.3)
        return True
    except Exception as e:
        log(f"  drawer open err: {e}")
        return False


def tap_label(driver, label):
    for sel in [
        f"//*[@clickable='true'][.//android.widget.TextView[@text={json.dumps(label)}]]",
        f"//android.widget.TextView[@text={json.dumps(label)}]",
        f"//*[@content-desc={json.dumps(label)}]",
        f"//*[@clickable='true'][@text={json.dumps(label)}]",
    ]:
        els = driver.find_elements(AppiumBy.XPATH, sel)
        if els:
            try:
                els[0].click()
                return True
            except Exception:
                pass
    return False


def main():
    log("=== nav explore 5558 v2 start ===")
    driver = _create_driver()
    try:
        _ensure_logged_in(driver)
        reset_home(driver)
        log("home pkg=%s texts=%s" % (current_pkg(driver), ", ".join(texts(driver, 8))))

        # ---------- DEEP LINKS ----------
        areas = [
            ("Raiz Rewards", "raiz://raiz_rewards"),
            ("Rewards Linked Accounts", "raiz://rewards_linked_accounts"),
            ("Rewards Auto", "raiz://rewards_auto"),
            ("Accounts/Rewards", "raiz://accounts/rewards"),
            ("Finance", "raiz://finance"),
            ("Accounts/Financial Insights", "raiz://accounts/financial_insights"),
            ("Profile/Personal", "raiz://profile/personal"),
            ("Profile/Financial", "raiz://profile/financial"),
            ("Notifications Settings", "raiz://notifications_settings"),
            ("Fees", "raiz://fees"),
            ("Offsetters", "raiz://offsetters"),
            ("Blog", "raiz://blog"),
            ("Invite Friends", "raiz://invite_friends"),
        ]
        for name, link in areas:
            try:
                explore_deeplink(driver, name, link)
            except Exception as e:
                log(f"[deeplink fatal] {name}: {e}")
            reset_home(driver)

        # ---------- REWARDS Earn/Track + detail ----------
        try:
            _open_deep_link(driver, "raiz://raiz_rewards")
            time.sleep(1.5); dismiss_modal(driver)
            earn_tx = texts(driver, 25)
            switched = tap_label(driver, "Track")
            time.sleep(1.5)
            track_tx = texts(driver, 25)
            detail_tx = []; opened = False
            _open_deep_link(driver, "raiz://raiz_rewards"); time.sleep(1.3); dismiss_modal(driver)
            items = driver.find_elements(AppiumBy.XPATH,
                "//*[contains(@resource-id,'RewardsEarnFeaturedItem')] | //*[contains(@resource-id,'FeaturedItem')]")
            if items:
                try:
                    items[0].click(); time.sleep(1.8)
                    detail_tx = texts(driver, 20)
                    opened = detail_tx != earn_tx
                except Exception:
                    pass
            RESULTS["notes"].append({
                "rewards_earn_texts": earn_tx[:18],
                "track_switched": switched,
                "rewards_track_texts": track_tx[:18],
                "reward_detail_opened": opened,
                "reward_detail_texts": detail_tx[:18],
                "reward_detail_webview": bool(driver.find_elements(AppiumBy.XPATH, "//android.webkit.WebView")),
            })
            log(f"[rewards] track_switched={switched} detail_opened={opened}")
        except Exception as e:
            log(f"[rewards tabs] err {e}")

        # ---------- NAV DRAWER ----------
        log("=== DRAWER ===")
        if open_drawer(driver):
            drawer_items = clickable_labels(driver, 60)
            drawer_texts = texts(driver, 60)
            RESULTS["notes"].append({"drawer_raw_texts": drawer_texts, "drawer_clickables": drawer_items})
            log("drawer raw texts: " + " || ".join(drawer_texts))
            skip = {"", "Close", "Open navigation drawer"}
            items = [d for d in drawer_items if d not in skip]
            for label in items:
                rec = {"item": label}
                try:
                    if not open_drawer(driver):
                        rec["error"] = "could not reopen drawer"
                        RESULTS["drawer"].append(rec); continue
                    if any(w in label.lower() for w in ("log out", "logout", "sign out")):
                        rec["destination"] = "(SKIPPED - logout, not tapped)"
                        RESULTS["drawer"].append(rec)
                        log(f"[drawer] {label}: SKIPPED logout"); continue
                    if not tap_label(driver, label):
                        rec["error"] = "could not tap"
                        RESULTS["drawer"].append(rec)
                        log(f"[drawer] {label}: could not tap"); continue
                    time.sleep(1.3)
                    rec["pin_prompted"] = pin_if_needed(driver, 2)
                    time.sleep(0.5); dismiss_modal(driver)
                    dtx = texts(driver, 14)
                    rec["package"] = current_pkg(driver)
                    rec["left_app"] = left_app(driver)
                    rec["destination_title"] = header_title(driver, dtx)
                    rec["destination_texts"] = dtx[:12]
                    rec["is_webview"] = bool(driver.find_elements(AppiumBy.XPATH, "//android.webkit.WebView"))
                    try:
                        driver.back(); time.sleep(1.0)
                        pin_if_needed(driver, 1.5); time.sleep(0.4)
                        rec["back_lands_on"] = header_title(driver, texts(driver, 8))
                    except Exception as e:
                        rec["back_lands_on"] = f"ERR {e}"
                except Exception as e:
                    rec["error"] = f"{type(e).__name__}: {e}"
                RESULTS["drawer"].append(rec)
                log(f"[drawer] {label}: dest={rec.get('destination_title')!r} pkg={rec.get('package')} "
                    f"left_app={rec.get('left_app')} back={rec.get('back_lands_on')!r} err={rec.get('error')}")
                reset_home(driver)
        else:
            log("!! could not open drawer")
            RESULTS["notes"].append({"drawer_error": "could not open drawer"})

        # ---------- SETTINGS ----------
        log("=== SETTINGS ===")
        def open_settings():
            if open_drawer(driver):
                for lbl in ["My Settings", "Settings", "My settings"]:
                    if tap_label(driver, lbl):
                        time.sleep(1.3)
                        pin_if_needed(driver, 1.5)
                        return True
            # gear fallback
            reset_home(driver)
            try:
                HomePage(driver).tap_settings(); time.sleep(1.3)
                pin_if_needed(driver, 1.5)
                return True
            except Exception:
                return False

        if open_settings():
            dismiss_modal(driver)
            # scroll-collect all settings rows
            settings_items = clickable_labels(driver, 60)
            settings_texts = texts(driver, 60)
            RESULTS["notes"].append({"settings_raw_texts": settings_texts, "settings_clickables": settings_items})
            log("settings raw texts: " + " || ".join(settings_texts))
            skip = {"", "Close"}
            items = [s for s in settings_items if s not in skip]
            for label in items:
                rec = {"row": label}
                try:
                    if not open_settings():
                        rec["error"] = "could not reopen settings"
                        RESULTS["settings"].append(rec); continue
                    dismiss_modal(driver)
                    if any(w in label.lower() for w in ("log out", "logout", "sign out")):
                        rec["destination"] = "(SKIPPED - logout, not tapped)"
                        RESULTS["settings"].append(rec)
                        log(f"[settings] {label}: SKIPPED logout"); continue
                    try:
                        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiScrollable(new UiSelector().scrollable(true))'
                            f'.scrollIntoView(new UiSelector().text({json.dumps(label)}))')
                    except Exception:
                        pass
                    if not tap_label(driver, label):
                        rec["error"] = "could not tap"
                        RESULTS["settings"].append(rec)
                        log(f"[settings] {label}: could not tap"); continue
                    time.sleep(1.3)
                    rec["pin_prompted"] = pin_if_needed(driver, 2)
                    time.sleep(0.5); dismiss_modal(driver)
                    dtx = texts(driver, 14)
                    rec["package"] = current_pkg(driver)
                    rec["left_app"] = left_app(driver)
                    rec["destination_title"] = header_title(driver, dtx)
                    rec["destination_texts"] = dtx[:12]
                    rec["is_webview"] = bool(driver.find_elements(AppiumBy.XPATH, "//android.webkit.WebView"))
                    try:
                        driver.back(); time.sleep(1.0)
                        pin_if_needed(driver, 1.5); time.sleep(0.4)
                        rec["back_lands_on"] = header_title(driver, texts(driver, 8))
                    except Exception as e:
                        rec["back_lands_on"] = f"ERR {e}"
                except Exception as e:
                    rec["error"] = f"{type(e).__name__}: {e}"
                RESULTS["settings"].append(rec)
                log(f"[settings] {label}: dest={rec.get('destination_title')!r} pkg={rec.get('package')} "
                    f"left_app={rec.get('left_app')} back={rec.get('back_lands_on')!r} err={rec.get('error')}")
                reset_home(driver)
        else:
            log("!! could not open settings")
            RESULTS["notes"].append({"settings_error": "could not open settings"})

    finally:
        with open("/tmp/nav_5558_results.json", "w") as f:
            json.dump(RESULTS, f, indent=2, default=str)
        log("=== results written /tmp/nav_5558_results.json ===")
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
