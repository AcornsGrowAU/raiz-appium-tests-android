import pytest
import _profile_hook  # noqa: F401  (no-op unless PROFILE_TESTS=1)
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options, get_ios_options
from config.settings import APPIUM_HOST, PLATFORM, STATE_PROBE_WAIT, TEST_EMAIL, TEST_PASSWORD, TEST_PIN
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.pin_page import PinPage
from pages.home_page import HomePage
from utils.deep_links import DeepLinks


def _create_driver(no_reset: bool = True):
    opts = get_android_options(no_reset) if PLATFORM == "android" else get_ios_options(no_reset)
    return appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)


def _enter_pin(pin: PinPage, driver):
    """Enter the test PIN and mark biometrics as possibly pending so the next dismiss_modal
    waits for it to render. Biometrics only appears immediately after PIN entry."""
    pin.enter_pin(TEST_PIN)
    driver._biometrics_pending = True


def _open_deep_link(driver, link: str):
    """Open a deep link, handling PIN re-authentication if the app requires it.

    Some screens (deposit, withdraw, rewards) trigger a PIN check when navigated
    to via deep link. This helper enters the PIN automatically if it appears.
    """
    DeepLinks.open(driver, link)
    pin = PinPage(driver)
    # PIN screen, if triggered, appears immediately — short probe avoids burning
    # several seconds per fixture on the common no-PIN path.
    if pin.is_loaded(timeout=STATE_PROBE_WAIT):
        _enter_pin(pin, driver)


def _ensure_logged_in(driver):
    """
    Handle whatever state the app is in on launch:
    - Splash screen → tap Log in → enter credentials
    - PIN screen → enter PIN
    - Home screen → already ready
    - Post-login modal → dismiss it
    """
    splash = SplashPage(driver)
    login = LoginPage(driver)
    pin = PinPage(driver)
    home = HomePage(driver)

    # State probes: snapshots first — whichever screen is up is already rendered.
    if pin.is_present_now(pin.TITLE):
        _enter_pin(pin, driver)
    elif splash.is_present_now(splash.TAGLINE):
        splash.tap_log_in()
        login.login(TEST_EMAIL, TEST_PASSWORD)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            _enter_pin(pin, driver)
    elif home.is_present_now(home.TOTAL_VALUE_LABEL):
        pass  # already on home

    # If we still aren't on home (unknown screen or initial render still settling), deep-link.
    if not home.is_loaded(timeout=STATE_PROBE_WAIT):
        DeepLinks.open(driver, DeepLinks.HOME)
        if pin.is_loaded(timeout=STATE_PROBE_WAIT):
            _enter_pin(pin, driver)

    home.dismiss_modal()
    assert home.is_loaded(), "Expected to be on Home screen after login"


class _DriverProxy:
    """A stand-in for the Appium driver that forwards every call to a live
    session and can transparently rebuild it.

    Why: the suite uses one session-scoped driver for speed, but the UiAutomator2
    instrumentation can crash mid-run (observed: UiAutomation DeadObjectException
    on Samsung One UI). With a plain driver, that crash cascades — every later
    test fails with "instrumentation process is not running". This proxy lets the
    autouse health check rebuild the underlying session in place, so the next
    test recovers instead of the whole run dying.
    """

    def __init__(self):
        self._d = None

    def start(self):
        self._d = _create_driver()
        _ensure_logged_in(self)
        return self

    def is_alive(self) -> bool:
        if self._d is None:
            return False
        try:
            # Probe the element pipeline specifically — that's what dies when the
            # UiAutomator2 instrumentation crashes ("POST /elements cannot be
            # proxied … instrumentation process is not running"). A non-matching
            # locator returns [] cheaply when healthy and raises when it's dead.
            # (current_package is served via ADB and would NOT detect the crash.)
            self._d.find_elements(AppiumBy.ID, "__liveness_probe__")
            return True
        except Exception:
            return False

    def recreate(self):
        try:
            if self._d is not None:
                self._d.quit()
        except Exception:
            pass
        # Drop stale per-session flags so biometrics/modal handling re-probes.
        for attr in ("_biometrics_pending", "_biometrics_dismissed"):
            self.__dict__.pop(attr, None)
        self._d = _create_driver()
        _ensure_logged_in(self)
        return self

    def shutdown(self):
        try:
            if self._d is not None:
                self._d.quit()
        except Exception:
            pass
        self._d = None

    def __getattr__(self, name):
        # Only reached for attributes the proxy itself doesn't define — i.e. the
        # real driver's API. Forward to the live session.
        d = self.__dict__.get("_d")
        if d is None:
            raise AttributeError(name)
        return getattr(d, name)


@pytest.fixture(scope="session")
def driver():
    """Session-scoped, self-healing driver — one Appium session for the run, with
    automatic recovery if the UiAutomator2 instrumentation crashes."""
    proxy = _DriverProxy()
    proxy.start()
    yield proxy
    proxy.shutdown()


@pytest.fixture(scope="function", autouse=True)
def _reauthenticate_if_needed(request):
    """Re-login before each test if a previous test left the session driver logged out."""
    if "driver" not in request.fixturenames:
        return
    d = request.getfixturevalue("driver")
    # Self-heal: if the UiAutomator2 instrumentation crashed during a previous
    # test, rebuild the session now so this test runs on a live driver instead of
    # failing with the cascading "instrumentation process is not running" error.
    if hasattr(d, "is_alive") and not d.is_alive():
        d.recreate()
        return
    splash = SplashPage(d)
    # Snapshot: if user is logged out, the login link is rendered right now.
    # Polling wouldn't make a difference here and was wasting ~1s per test.
    if splash.is_present_now(splash.TAGLINE):
        _ensure_logged_in(d)


def _scroll_to_top(driver) -> bool:
    """Scroll the current scrollable container to its first item. Returns True on success."""
    try:
        driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiScrollable(new UiSelector().scrollable(true)).scrollToBeginning(10)',
        )
        return True
    except Exception:
        return False


@pytest.fixture(scope="function")
def home(driver):
    """Return a fresh HomePage. Fast path skips deep-link + PIN re-auth when we're already there."""
    page = HomePage(driver)

    # Fast path: home title in DOM right now (possibly scrolled off-screen but still on the home route)
    if page.is_present_now(page.TOTAL_VALUE_LABEL):
        if not page.is_loaded(timeout=0.5):
            _scroll_to_top(driver)  # restore top so subsequent tests see top-of-page elements
        page.dismiss_modal()
        return page

    # Compose lazy columns recycle off-screen items, so the title may be gone from DOM even if
    # we're still on home. Try scrolling whatever container is up — if home was underneath, the
    # title re-renders.
    if _scroll_to_top(driver) and page.is_present_now(page.TOTAL_VALUE_LABEL):
        page.dismiss_modal()
        return page

    # Not on home at all — either logged out or on another screen. Recover.
    splash = SplashPage(driver)
    if splash.is_present_now(splash.TAGLINE):
        _ensure_logged_in(driver)
    else:
        _open_deep_link(driver, DeepLinks.HOME)
    page.dismiss_modal()
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def nav_drawer(driver, home):
    from pages.nav_drawer import NavDrawer
    home.tap_hamburger()
    drawer = NavDrawer(driver)
    assert drawer.is_open()
    return drawer


@pytest.fixture(scope="function")
def settings(driver, home):
    from pages.settings_page import SettingsPage
    home.tap_settings()
    page = SettingsPage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def main_portfolio(driver):
    from pages.main_portfolio_page import MainPortfolioPage
    _open_deep_link(driver, DeepLinks.INVEST)
    page = MainPortfolioPage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def performance(driver):
    from pages.performance_page import PerformancePage
    _open_deep_link(driver, DeepLinks.PERFORMANCE)
    page = PerformancePage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def rewards(driver):
    from pages.rewards_page import RewardsPage
    _open_deep_link(driver, DeepLinks.REWARDS)
    page = RewardsPage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def jars(driver):
    from pages.jars_page import JarsPage
    _open_deep_link(driver, DeepLinks.JARS)
    page = JarsPage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def kids(driver):
    from pages.kids_page import KidsPage
    _open_deep_link(driver, DeepLinks.RAIZ_KIDS)
    page = KidsPage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def my_finance(driver):
    from pages.my_finance_page import MyFinancePage
    # Use the PIN-aware opener (like every sibling fixture) — the raw DeepLinks.open
    # here would fail whenever the app intermittently re-prompts for the PIN on
    # navigation, which is exactly what errored the My Finance tests on the emulator.
    _open_deep_link(driver, DeepLinks.FINANCE)
    page = MyFinancePage(driver)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def transaction_history(driver):
    from pages.transaction_history_page import TransactionHistoryPage
    _open_deep_link(driver, DeepLinks.TRANSACTIONS)
    page = TransactionHistoryPage(driver)
    # raiz://transactions intermittently fails to resolve on the first deep link
    # (observed as spurious FAIL/ERROR in serial runs). Retry once like the
    # lump_sum/recurring fixtures do, before asserting.
    if not page.is_loaded(timeout=STATE_PROBE_WAIT):
        _open_deep_link(driver, DeepLinks.TRANSACTIONS)
    assert page.is_loaded()
    return page


# --- Allure reporting integration (no-ops cleanly if allure-pytest is absent) ---
_FEATURE_MARKERS = {
    "auth", "navigation", "portfolio", "investments",
    "rewards", "settings", "e2e", "edge", "unit",
}


def pytest_collection_modifyitems(config, items):
    """Label each test in Allure's Behaviors view by its feature marker, derived
    from the existing pytest markers so no per-test edits are needed."""
    try:
        import allure
    except Exception:
        return
    for item in items:
        names = {m.name for m in item.iter_markers()}
        for feat in (names & _FEATURE_MARKERS):
            item.add_marker(allure.feature(feat))
        if "smoke" in names:
            item.add_marker(allure.label("tag", "smoke"))
        if "destructive" in names:
            item.add_marker(allure.label("tag", "destructive"))


def pytest_configure(config):
    """Write environment.properties into the allure results dir so the report's
    Environment widget shows the build/device/host. Best-effort and safe when
    allure is off or the dir isn't set."""
    results = getattr(config.option, "allure_report_dir", None)
    if not results:
        return
    try:
        import os
        os.makedirs(results, exist_ok=True)
        from config.settings import PLATFORM, ANDROID_UDID, ANDROID_APP_PACKAGE, APPIUM_HOST
        props = (
            f"Platform={PLATFORM}\n"
            f"Device={ANDROID_UDID}\n"
            f"AppPackage={ANDROID_APP_PACKAGE}\n"
            f"AppiumHost={APPIUM_HOST}\n"
        )
        with open(os.path.join(results, "environment.properties"), "w") as fh:
            fh.write(props)
    except Exception:
        pass
