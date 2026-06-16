import time
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config.settings import DEFAULT_WAIT, LONG_WAIT


def wait_for(driver, locator, timeout=DEFAULT_WAIT):
    """Wait for an element to be visible and return it."""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator)
    )


def wait_for_clickable(driver, locator, timeout=DEFAULT_WAIT):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)
    )


def wait_for_text(driver, text: str, timeout=DEFAULT_WAIT):
    """Wait until any element with the given text is visible."""
    locator = (AppiumBy.XPATH, f"//*[@text='{text}']")
    return wait_for(driver, locator, timeout)


def is_element_present(driver, locator, timeout=3) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return True
    except TimeoutException:
        return False


def dismiss_modal_if_present(driver, close_bounds_x: int = 1032, close_bounds_y: int = 235, timeout=3):
    """Dismiss a promotional modal if one appears after navigation."""
    time.sleep(timeout)
    try:
        driver.tap([(close_bounds_x, close_bounds_y)])
    except Exception:
        pass


def scroll_down(driver, start_y=1500, end_y=500, duration=500):
    size = driver.get_window_size()
    width = size["width"] // 2
    driver.swipe(width, start_y, width, end_y, duration)


def scroll_up(driver, start_y=500, end_y=1500, duration=500):
    size = driver.get_window_size()
    width = size["width"] // 2
    driver.swipe(width, start_y, width, end_y, duration)


def clear_and_type(driver, element, text: str):
    """Clear an input field and type new text."""
    element.clear()
    element.send_keys(text)
