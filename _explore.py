"""Standalone exploration script — drives the running Appium session to find
end-to-end flows. Each flow is isolated with try/except + home recovery so a
single failure doesn't abort the rest of the exploration.
"""
import os
import sys
import time
import traceback
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from appium.webdriver.common.appiumby import AppiumBy
from conftest import _create_driver, _ensure_logged_in, _open_deep_link
from pages.home_page import HomePage
from pages.pin_page import PinPage
from utils.deep_links import DeepLinks
from config.settings import TEST_PIN

LOG = "/tmp/raiz_explore.log"


def log(msg=""):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def dump_screen(driver, label: str):
    log(f"\n--- {label} ---")
    texts = driver.find_elements(AppiumBy.XPATH, "//android.widget.TextView[string-length(@text) > 0]")
    values = []
    for el in texts:
        try:
            t = el.text
            if t and t.strip():
                values.append(t.strip())
        except Exception:
            pass
    log("TEXTS:")
    for t in values[:50]:
        log(f"  · {t}")

    clickables = driver.find_elements(AppiumBy.XPATH, "//*[@clickable='true']")
    log(f"CLICKABLES ({len(clickables)} total):")
    seen = set()
    for el in clickables[:80]:
        try:
            cls = (el.get_attribute("className") or "").split(".")[-1]
            txt = el.get_attribute("text") or ""
            desc = el.get_attribute("contentDescription") or ""
            inner = ""
            inner_els = el.find_elements(AppiumBy.XPATH, ".//android.widget.TextView")
            if inner_els:
                inner = " | ".join(t.text for t in inner_els[:3] if t.text)
            entry = f"{cls:<14} txt={txt!r} desc={desc!r} inner={inner!r}"
            if entry not in seen:
                seen.add(entry)
                log(f"  · {entry}")
        except Exception:
            pass


def tap_text(driver, text, timeout=3):
    """Tap a clickable element whose subtree contains `text`. Returns True if tapped."""
    end = time.time() + timeout
    while time.time() < end:
        # Prefer the clickable ancestor that contains the text
        candidates = driver.find_elements(
            AppiumBy.XPATH,
            f"//*[@clickable='true'][.//android.widget.TextView[@text='{text}']]",
        )
        if not candidates:
            candidates = driver.find_elements(AppiumBy.XPATH, f"//android.widget.TextView[@text='{text}']")
        if candidates:
            candidates[0].click()
            return True
        time.sleep(0.2)
    return False


def reset_to_home(driver):
    """Force a clean home state, handling PIN re-auth if it pops up."""
    DeepLinks.open(driver, DeepLinks.HOME)
    time.sleep(0.5)
    pin = PinPage(driver)
    if pin.is_loaded(timeout=2):
        pin.enter_pin(TEST_PIN)
        time.sleep(1.5)
    # Dismiss any modal
    HomePage(driver).dismiss_modal()


@contextmanager
def flow(name):
    log(f"\n{'=' * 60}\nFLOW: {name}\n{'=' * 60}")
    try:
        yield
    except Exception as e:
        log(f"[FLOW ERROR] {type(e).__name__}: {e}")
        log(traceback.format_exc()[:800])


def main():
    open(LOG, "w").close()
    log(f"# explore start ts={time.time():.0f}")
    driver = _create_driver()
    try:
        _ensure_logged_in(driver)
        home = HomePage(driver)

        with flow("Add funds modal"):
            reset_to_home(driver)
            home.tap_add_funds()
            time.sleep(1)
            dump_screen(driver, "Add funds modal")

        with flow("Lump Sum Investment full path"):
            reset_to_home(driver)
            home.tap_add_funds()
            time.sleep(1)
            tap_text(driver, "Lump Sum Investment")
            time.sleep(2)
            dump_screen(driver, "Lump sum screen (empty)")
            for d in "10":
                tap_text(driver, d)
            time.sleep(0.5)
            dump_screen(driver, "Lump sum $10 entered")
            tap_text(driver, "Invest")
            time.sleep(2.5)
            dump_screen(driver, "After tapping Invest")

        with flow("Recurring Investment from modal"):
            reset_to_home(driver)
            home.tap_add_funds()
            time.sleep(1)
            tap_text(driver, "Recurring investments")
            time.sleep(2.5)
            dump_screen(driver, "Recurring investments entry")

        with flow("Withdraw full path"):
            reset_to_home(driver)
            home.tap_withdraw()
            time.sleep(1.5)
            dump_screen(driver, "Withdraw screen")
            for d in "5":
                tap_text(driver, d)
            time.sleep(0.5)
            dump_screen(driver, "Withdraw $5 entered")
            tap_text(driver, "Withdraw")
            time.sleep(2)
            dump_screen(driver, "After tapping Withdraw")

        with flow("Settings → Manage Round-Ups"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Manage Round-Ups")
            time.sleep(2)
            dump_screen(driver, "Manage Round-Ups")

        with flow("Settings → Notifications inbox"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Notifications inbox")
            time.sleep(2)
            dump_screen(driver, "Notifications inbox")

        with flow("Settings → Plans and fees"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Plans and fees")
            time.sleep(2)
            dump_screen(driver, "Plans and fees")

        with flow("Settings → Funding account"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Funding account")
            time.sleep(2)
            dump_screen(driver, "Funding account")

        with flow("Settings → Personal details"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Personal details")
            time.sleep(2)
            dump_screen(driver, "Personal details")

        with flow("Settings → Security and privacy"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            tap_text(driver, "Security and privacy")
            time.sleep(2)
            dump_screen(driver, "Security and privacy")

        with flow("Rewards → tap featured item"):
            _open_deep_link(driver, DeepLinks.REWARDS)
            time.sleep(2)
            items = driver.find_elements(
                AppiumBy.XPATH, "//*[@resource-id='RewardsEarnFeaturedItem_Root']"
            )
            if items:
                items[0].click()
                time.sleep(2)
                dump_screen(driver, "Reward detail (featured)")
            else:
                log("No featured items")

        with flow("Rewards → search"):
            _open_deep_link(driver, DeepLinks.REWARDS)
            time.sleep(2)
            search = driver.find_elements(AppiumBy.XPATH, "//android.widget.EditText")
            if search:
                search[0].click()
                time.sleep(0.5)
                search[0].send_keys("Coles")
                time.sleep(2)
                dump_screen(driver, "Rewards search 'Coles'")

        with flow("Rewards Track tab"):
            _open_deep_link(driver, DeepLinks.REWARDS)
            time.sleep(2)
            tap_text(driver, "Track")
            time.sleep(2)
            dump_screen(driver, "Rewards Track tab")
            tap_text(driver, "Pending")
            time.sleep(1)
            dump_screen(driver, "Rewards Track → Pending filter")

        with flow("Performance time-range cycling"):
            _open_deep_link(driver, DeepLinks.PERFORMANCE)
            time.sleep(2)
            dump_screen(driver, "Performance default")
            for r in ["1D", "1M", "3M", "6M", "1Y", "All"]:
                tap_text(driver, r)
                time.sleep(0.6)
            dump_screen(driver, "Performance after cycling ranges")

        with flow("Transaction history → filter"):
            _open_deep_link(driver, DeepLinks.TRANSACTIONS)
            time.sleep(2)
            dump_screen(driver, "Transaction history")
            tap_text(driver, "Filter")
            time.sleep(2)
            dump_screen(driver, "Filter modal")

        with flow("Main portfolio → Round-Ups row"):
            _open_deep_link(driver, DeepLinks.INVEST)
            time.sleep(2)
            try:
                driver.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().scrollable(true))'
                    '.scrollIntoView(new UiSelector().text("Round-Ups"))',
                )
            except Exception:
                pass
            tap_text(driver, "Round-Ups")
            time.sleep(2)
            dump_screen(driver, "Round-Ups detail")

        with flow("Main portfolio → Holdings"):
            _open_deep_link(driver, DeepLinks.INVEST)
            time.sleep(2)
            try:
                driver.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().scrollable(true))'
                    '.scrollIntoView(new UiSelector().text("Holdings"))',
                )
            except Exception:
                pass
            tap_text(driver, "Holdings")
            time.sleep(2)
            dump_screen(driver, "Holdings detail")

        with flow("Recurring investments deep link"):
            _open_deep_link(driver, DeepLinks.RECURRING_INVESTMENTS)
            time.sleep(2)
            dump_screen(driver, "Recurring investments")

        with flow("Settings → Log out (no actual logout)"):
            reset_to_home(driver)
            home.tap_settings()
            time.sleep(1)
            try:
                driver.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().scrollable(true))'
                    '.scrollIntoView(new UiSelector().text("Log out"))',
                )
            except Exception:
                pass
            tap_text(driver, "Log out")
            time.sleep(2)
            dump_screen(driver, "Log out confirmation")
            # Cancel the logout so we stay logged in
            for cancel_word in ["Cancel", "No"]:
                if tap_text(driver, cancel_word, timeout=1):
                    log(f"Cancelled via '{cancel_word}'")
                    break

        log("\n# explore complete")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
