import time
from collections import Counter
from appium.webdriver.common.appiumby import AppiumBy
from conftest import _open_deep_link, _DriverProxy
from utils.deep_links import DeepLinks
from pages.transaction_history_page import TransactionHistoryPage

PICKER = (AppiumBy.XPATH,
          "//*[@clickable='true'][.//android.widget.TextView[@text='Select a transaction type']]")
APPLY = (AppiumBy.XPATH,
         "//*[@clickable='true'][.//android.widget.TextView[@text='Apply']]")


def opt(text):
    return (AppiumBy.XPATH,
            f"//*[@clickable='true'][.//android.widget.TextView[@text='{text}']]")


def apply_type(d, page, type_text):
    page.tap_filter()
    time.sleep(1.5)
    if d.find_elements(*PICKER):
        d.find_element(*PICKER).click()
        time.sleep(1.5)
    d.find_element(*opt(type_text)).click()
    time.sleep(0.7)
    if d.find_elements(*APPLY):
        d.find_element(*APPLY).click()
    time.sleep(2)
    return page.get_transaction_count()


def main():
    proxy = _DriverProxy()
    proxy.start()
    d = proxy
    try:
        _open_deep_link(d, DeepLinks.TRANSACTIONS)
        page = TransactionHistoryPage(d)
        if not page.is_loaded(timeout=5):
            _open_deep_link(d, DeepLinks.TRANSACTIONS)
        assert page.is_loaded()
        print("unfiltered count:", page.get_transaction_count(),
              Counter(r["type"] for r in page.get_transactions(limit=30)))

        # Fresh navigation, then apply Withdrawal ONLY (account has none).
        _open_deep_link(d, DeepLinks.TRANSACTIONS)
        assert page.is_loaded(timeout=5)
        c = apply_type(d, page, "Withdrawal")
        print("\nAfter WITHDRAWAL-only count:", c)
        rows = page.get_transactions(limit=30)
        print(Counter(r["type"] for r in rows))
        # dump any empty-state text
        texts = [t.text for t in d.find_elements(
            AppiumBy.XPATH, "//android.widget.TextView[string-length(@text) > 0]")]
        print("screen texts:", texts[:20])
    finally:
        proxy.shutdown()


if __name__ == "__main__":
    main()
