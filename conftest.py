import os
import pytest
import _profile_hook  # noqa: F401  (no-op unless PROFILE_TESTS=1)
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options, get_ios_options
from config.settings import (
    APPIUM_HOST, PLATFORM, STATE_PROBE_WAIT, DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL,
    TEST_EMAIL, TEST_PASSWORD, TEST_PIN,
)
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.pin_page import PinPage
from pages.home_page import HomePage
from utils.deep_links import DeepLinks


# Dynamic work-queue support (pytest-xdist `-n N --dist load`): xdist holds all
# collected tests in one queue and hands the next to whichever worker just freed
# up. Each worker is its own process, so we pin it to its own device + Appium
# server + ports here (gw0->5554, gw1->5556, gw2->5558), mirroring the
# run_parallel.sh port map. `-n` must equal the device count or workers double up.
# Override the map with ANDROID_DEVICE_MAP="udid,host,sysport,mjpeg;udid,..." env.
_DEFAULT_DEVICE_MAP = [
    ("emulator-5554", "http://127.0.0.1:4723", "8201", "7811"),
    ("emulator-5556", "http://127.0.0.1:4724", "8202", "7812"),
    ("emulator-5558", "http://127.0.0.1:4725", "8204", "7814"),
]


def _device_map():
    raw = os.getenv("ANDROID_DEVICE_MAP")
    if not raw:
        return _DEFAULT_DEVICE_MAP
    out = []
    for row in raw.split(";"):
        parts = [p.strip() for p in row.split(",")]
        if len(parts) == 4:
            out.append(tuple(parts))
    return out or _DEFAULT_DEVICE_MAP


def _xdist_device():
    """Return (udid, appium_host, system_port, mjpeg_port) for this xdist worker,
    or None when not running distributed (single-device behaviour via env)."""
    worker = os.getenv("PYTEST_XDIST_WORKER")  # 'gw0','gw1',... under -n; unset otherwise
    if not worker:
        return None
    try:
        idx = int(worker.replace("gw", ""))
    except ValueError:
        idx = 0
    table = _device_map()
    return table[idx % len(table)]


def _create_driver(no_reset: bool = True):
    if PLATFORM != "android":
        return appium_webdriver.Remote(command_executor=APPIUM_HOST, options=get_ios_options(no_reset))
    dev = _xdist_device()
    if dev:
        udid, host, sysport, mjpeg = dev
        # systemPort/mjpegPort are read from env at call time inside
        # get_android_options; the udid is import-bound there, so override it on the
        # built options object.
        os.environ["ANDROID_SYSTEM_PORT"] = sysport
        os.environ["ANDROID_MJPEG_PORT"] = mjpeg
        opts = get_android_options(no_reset)
        opts.udid = udid
        return appium_webdriver.Remote(command_executor=host, options=opts)
    return appium_webdriver.Remote(command_executor=APPIUM_HOST, options=get_android_options(no_reset))


_BIOMETRICS_TITLE = (AppiumBy.XPATH,
    "//*[@text='Raiz Biometrics' or contains(@text, 'biometric') or contains(@text, 'Biometric')]")
_BIOMETRICS_NO = (AppiumBy.XPATH,
    "//android.view.View[@clickable='true'][.//android.widget.TextView[@text='No']]")


def _dismiss_biometrics(driver, timeout=STATE_PROBE_WAIT) -> bool:
    """Dismiss the 'Raiz Biometrics' enable prompt (a Yes/No dialog) by clicking No.

    This prompt can overlay the PIN page — either as we arrive (blocking the
    keypad) or right after the PIN is accepted (offering to enable biometric
    login). We never enrol biometrics in tests, so always choose No. Pass
    timeout=0 for an instant snapshot check (no polling)."""
    from pages.base_page import BasePage
    bp = BasePage(driver)
    present = (bp.is_present_now(_BIOMETRICS_TITLE) if timeout == 0
               else bp.is_visible(_BIOMETRICS_TITLE, timeout=timeout))
    if not present:
        return False
    try:
        bp.click(_BIOMETRICS_NO)
        driver._biometrics_dismissed = True
        driver._biometrics_pending = False
        return True
    except Exception:
        return False


def _enter_pin(pin: PinPage, driver):
    """Enter the test PIN, handling the biometric-login prompt that can appear on
    the PIN page. The prompt can overlay the keypad on arrival, or pop up right
    after the PIN is accepted — in either case we click No (never enrol)."""
    _dismiss_biometrics(driver, timeout=0)  # clear an overlay before typing
    pin.enter_pin(TEST_PIN)
    driver._biometrics_pending = True
    _dismiss_biometrics(driver)             # prompt usually appears AFTER the PIN


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


_SHARED_LOGIN_LOCK = "/tmp/raiz_shared_account_login.lock"


class _login_gate:
    """Cross-process lock that serializes CREDENTIAL logins to the single shared
    test account across parallel device processes.

    Running the suite across N emulators means N processes can hit the splash→login
    path at the same moment, all fresh-authenticating the ONE shared account
    simultaneously. That burst races on the backend and leaves some devices stuck on
    a loading/error screen that never resolves to Home (the deterministic
    `_ensure_logged_in` is_loaded failure seen when 3 devices start logged-out at
    once). Holding this lock through one device's login — until the app settles onto
    PIN or Home — lets each device establish its session in turn.

    Cheap in steady state: with no_reset the session persists, so a device that is
    already logged in (PIN/Home path) never enters this gate. Only the first
    logged-out burst pays the serialization cost. Unix-only (fcntl); the suite runs
    on macOS. Best-effort — if locking is unavailable the login still proceeds."""

    def __enter__(self):
        self._fd = None
        try:
            import fcntl
            self._fd = os.open(_SHARED_LOGIN_LOCK, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except Exception:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
                self._fd = None
        return self

    def __exit__(self, *exc):
        if self._fd is None:
            return
        try:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            try:
                os.close(self._fd)
            except Exception:
                pass


def _ensure_logged_in(driver):
    """
    Drive the app to the Home screen from whatever state it launched into:
    - Splash screen → tap Log in → enter credentials
    - PIN screen → enter PIN
    - Home screen → already ready
    - Post-login modal → dismiss it

    Robust against a cold launch: the app spends the first beat on a branded
    loading screen that is NEITHER splash, PIN, nor Home, and each transition
    (splash→login, login→PIN, PIN→home, deep-link→PIN) can take longer than a
    single STATE_PROBE_WAIT on a slow emulator (~1-3s RTT). A one-shot linear
    sequence therefore races and lands "nowhere", which is exactly the
    deterministic conftest:154 failure. Instead we loop: on each pass we resolve
    whichever screen is currently up and re-check Home, retrying the HOME
    deep-link until we either reach Home or hit an overall deadline. This is
    purely login-path hardening — it changes nothing the tests assert."""
    import time

    splash = SplashPage(driver)
    login = LoginPage(driver)
    pin = PinPage(driver)
    home = HomePage(driver)

    deadline = time.time() + LONG_WAIT * 3  # generous overall budget for a cold start
    deep_linked = False
    pin_locked = False  # set when the app blocks PIN after too many attempts

    while time.time() < deadline:
        # Already there? Poll briefly so a still-settling Home render counts.
        if home.is_loaded(timeout=STATE_PROBE_WAIT):
            break

        # PIN lockout: after too many PIN attempts the app blocks the PIN and demands
        # an email+password re-login ("You've made too many failed attempts to log in
        # with your PIN..."). Re-entering the PIN here would just re-trip the lockout,
        # so dismiss the dialog and force the credential path below — a successful
        # credential login resets the attempt counter. A PIN-heavy parallel suite hits
        # this routinely, so handling it is what keeps the suite reliably green.
        if driver.find_elements(
            AppiumBy.XPATH,
            "//*[contains(@text,'Too many attempts') or contains(@text,'too many failed')]",
        ):
            pin_locked = True
            for _ok in driver.find_elements(AppiumBy.XPATH, "//*[@text='Ok' or @text='OK']"):
                try:
                    _ok.click()
                    break
                except Exception:
                    pass
            time.sleep(POLL_INTERVAL)
            continue

        # PIN can overlay at any point (initial launch, post-login, post-deep-link).
        # Skip while locked out — entering the PIN would re-trip the lockout.
        if pin.is_present_now(pin.TITLE) and not pin_locked:
            _enter_pin(pin, driver)
            continue

        # Logged out: walk the splash → login → (PIN) path.
        if splash.is_present_now(splash.TAGLINE):
            splash.tap_log_in()
            if login.is_loaded(timeout=DEFAULT_WAIT):
                # Serialize the credential login + its resolution across devices so
                # parallel logged-out starts don't stampede the one shared account.
                with _login_gate():
                    login.login(TEST_EMAIL, TEST_PASSWORD)
                    # Hold the gate until login resolves to PIN or Home, so this
                    # device's session is established before the next one logs in.
                    pin.is_loaded(timeout=DEFAULT_WAIT)
            else:
                pin.is_loaded(timeout=DEFAULT_WAIT)
            pin_locked = False  # credentials submitted -> PIN lockout reset
            continue

        # Login form already up (e.g. splash auto-advanced past the tagline).
        if login.is_present_now(login.TITLE):
            with _login_gate():
                login.login(TEST_EMAIL, TEST_PASSWORD)
                pin.is_loaded(timeout=DEFAULT_WAIT)
            pin_locked = False  # credentials submitted -> PIN lockout reset
            continue

        # Unknown / still-loading screen. Try the HOME deep-link once, then keep
        # looping so a PIN prompt it triggers (or a slow render) is handled above.
        if not deep_linked:
            DeepLinks.open(driver, DeepLinks.HOME)
            deep_linked = True
            pin.is_loaded(timeout=STATE_PROBE_WAIT)
            continue

        # Deep-link already attempted and we're still not anywhere we recognise:
        # give the app a moment to finish whatever it's doing, then re-probe.
        time.sleep(POLL_INTERVAL * 5)

    home.dismiss_modal()
    # Final settle wait before the hard assert: a freshly dismissed modal can leave
    # Home recomposing for a beat. Re-check with a real poll, not a snapshot.
    assert home.is_loaded(timeout=DEFAULT_WAIT), "Expected to be on Home screen after login"


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
    # Retry once if the settings sheet didn't render (slow under memory pressure):
    # return to a known Home, then re-open the gear before asserting.
    if not page.is_loaded(timeout=STATE_PROBE_WAIT):
        _open_deep_link(driver, DeepLinks.HOME)
        home.dismiss_modal()
        home.tap_settings()
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def main_portfolio(driver):
    from pages.main_portfolio_page import MainPortfolioPage
    _open_deep_link(driver, DeepLinks.INVEST)
    page = MainPortfolioPage(driver)
    # One-shot reopen-retry (like rewards/settings/transaction_history): a single
    # slow render under memory pressure shouldn't error the whole portfolio file.
    if not page.is_loaded(timeout=STATE_PROBE_WAIT):
        _open_deep_link(driver, DeepLinks.INVEST)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def performance(driver):
    from pages.performance_page import PerformancePage
    _open_deep_link(driver, DeepLinks.PERFORMANCE)
    page = PerformancePage(driver)
    # One-shot reopen-retry (the performance chart can be slow to render under
    # memory pressure); matches the rewards/settings/transaction_history fixtures.
    if not page.is_loaded(timeout=STATE_PROBE_WAIT):
        _open_deep_link(driver, DeepLinks.PERFORMANCE)
    assert page.is_loaded()
    return page


@pytest.fixture(scope="function")
def rewards(driver):
    from pages.rewards_page import RewardsPage
    _open_deep_link(driver, DeepLinks.REWARDS)
    page = RewardsPage(driver)
    # Rewards is a heavy partner-offers screen that can be slow to render under
    # memory pressure; retry once (like the transaction_history fixture) before
    # asserting, so a single slow load doesn't error the whole rewards file.
    if not page.is_loaded(timeout=STATE_PROBE_WAIT):
        _open_deep_link(driver, DeepLinks.REWARDS)
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
