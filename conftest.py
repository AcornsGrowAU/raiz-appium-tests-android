import os
import pytest
import _profile_hook  # noqa: F401  (no-op unless PROFILE_TESTS=1)
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy
from config.capabilities import get_android_options, get_ios_options
from config.settings import (
    APPIUM_HOST, PLATFORM, STATE_PROBE_WAIT, DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL,
    TEST_EMAIL, TEST_PASSWORD, TEST_PIN, ANDROID_APP_PACKAGE,
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


_PIN_LOCKOUT_XPATH = ("//*[contains(@text,'Too many attempts') "
                      "or contains(@text,'too many failed')]")


def _pin_locked_out(driver) -> bool:
    """True if the app is showing the PIN-lockout dialog. Re-entering the PIN here
    would just re-trip it — _ensure_logged_in owns that recovery — so callers bail
    out of PIN entry when this is up."""
    try:
        return bool(driver.find_elements(AppiumBy.XPATH, _PIN_LOCKOUT_XPATH))
    except Exception:
        return False


def _clear_pin_gate(driver, probe_timeout=STATE_PROBE_WAIT, attempts=2) -> bool:
    """Enter the PIN if the unlock gate is up after navigation, and CONFIRM it
    cleared — re-entering once if a swallowed first keypress left us stranded.

    The old one-shot probe entered the PIN if it appeared within the window but
    never checked that the unlock took. A tap on a still-composing Compose keypad
    can be dropped, leaving the app on 'Enter your PIN' when the caller's assertion
    runs (the round_ups_settings flake). Here we verify the title disappears and
    re-enter once if it didn't. Bails out on PIN lockout so we never hammer the
    keypad into a 'Too many attempts' block. Returns True if a gate was handled.
    The common no-PIN path still costs a single STATE_PROBE_WAIT probe."""
    import time
    pin = PinPage(driver)
    if not pin.is_loaded(timeout=probe_timeout):
        return False
    for _ in range(attempts):
        if _pin_locked_out(driver):
            return True
        _enter_pin(pin, driver)
        # Confirm the gate cleared: a valid PIN drops the 'Enter your PIN' title.
        deadline = time.time() + DEFAULT_WAIT
        while time.time() < deadline:
            if not pin.is_present_now(pin.TITLE):
                return True
            time.sleep(POLL_INTERVAL * 3)
        # Still on PIN — first keypress likely swallowed; loop re-enters once.
    return True


def _ensure_raiz_foreground(driver):
    """Best-effort: reclaim the foreground for the Raiz app if something else is on
    top. A Settings row ('Get support' / 'Our terms') fires an Intent into external
    Chrome (com.android.chrome); Chrome's first-run/consent screen swallows the next
    raiz:// deep link, stranding every later serial test's home fixture at
    assert is_loaded(). If the current foreground package is something other than
    ours, kill Chrome (it's the usual culprit) and re-activate the app. Wrapped so it
    can never raise — a dead driver or a missing capability must not fail a test."""
    try:
        current = driver.current_package
        if current and current != ANDROID_APP_PACKAGE:
            try:
                driver.terminate_app("com.android.chrome")
            except Exception:
                pass
            driver.activate_app(ANDROID_APP_PACKAGE)
    except Exception:
        pass


def _open_deep_link(driver, link: str, ready=None, settle=LONG_WAIT):
    """Open a deep link, handling PIN re-authentication if the app requires it.

    Some screens (deposit, withdraw, round_ups/settings) trigger a PIN check when
    navigated to — sometimes a beat AFTER the link resolves. Two call shapes:

    - Without `ready` (most fixtures): open, then a single short PIN probe that now
      also verifies the gate cleared (re-entering a swallowed keypress). Cost on the
      common no-PIN path is unchanged — one STATE_PROBE_WAIT probe.
    - With `ready` (a predicate that returns True once the real destination is up):
      a readiness-aware settle — poll cheaply until the destination renders OR a PIN
      gate appears (which we clear), up to `settle` seconds, exiting the instant the
      destination is up. This closes the late-gate race that the fixed-window probe
      misses, without penalising routes that never gate.
    """
    import time
    # If a Settings link bounced us into external Chrome, the deep link below would
    # land on Chrome's first-run screen instead of the app. Reclaim the foreground
    # first so DeepLinks.open resolves inside Raiz.
    _ensure_raiz_foreground(driver)
    DeepLinks.open(driver, link)
    if ready is None:
        _clear_pin_gate(driver)
        return
    pin = PinPage(driver)
    deadline = time.time() + settle
    pin_entries = 0
    while time.time() < deadline:
        # A PIN gate up now takes priority — the destination can't be 'ready' behind
        # it. Clear it (verify-and-re-enter; never past lockout) and re-loop. The
        # bare _enter_pin here used to skip the gate-cleared verification that
        # _clear_pin_gate already does, so a swallowed first Compose keypress left
        # finance/raiz_kids_2 stranded on an empty PIN screen.
        if pin.is_present_now(pin.TITLE):
            if pin_entries >= 3 or _pin_locked_out(driver):
                return  # leave recovery to the caller's assert / _ensure_logged_in
            _clear_pin_gate(driver)
            pin_entries += 1
            # The keypad wait above shouldn't be charged against the destination's
            # render budget — give the loop a fresh `settle` window after a gate.
            deadline = max(deadline, time.time() + settle)
            time.sleep(POLL_INTERVAL * 3)
            continue
        if ready(driver):
            return
        time.sleep(POLL_INTERVAL * 2)


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
            # External Chrome (Settings → Get support / Our terms) can sit on top
            # after a prior test; reclaim Raiz so this HOME deep link resolves in-app
            # instead of bouncing off Chrome's first-run screen.
            _ensure_raiz_foreground(driver)
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


@pytest.fixture(scope="function", autouse=True)
def _reclaim_foreground_after_test(request):
    """After every test that uses the shared `driver`, make sure Raiz is back in the
    foreground. A test that tapped a Settings row opening external Chrome ('Get
    support' / 'Our terms') would otherwise leave Chrome on top, stranding the next
    serial test's home fixture. No-op for tests that don't use `driver` (genuser_e2e
    tests manage their own driver). Best-effort — never raises, even on a dead
    session."""
    if "driver" not in request.fixturenames:
        yield
        return
    yield
    try:
        d = request.getfixturevalue("driver")
        _ensure_raiz_foreground(d)
    except Exception:
        pass


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
        # A prior test may have left external Chrome on top (Settings → Get support /
        # Our terms); reclaim the app before the HOME deep link so it doesn't strand
        # on Chrome's first-run screen.
        _ensure_raiz_foreground(driver)
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
    # Install the live-driver tracking that screenshot-on-failure depends on.
    # Done here (before any fixture/test builds a driver) so every Appium session
    # — the shared `driver` fixture AND the genuser tests' own local drivers —
    # is captured for the failure-screenshot hook below.
    _install_driver_tracking()

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


# --- Screenshot (+ page source) on failure --------------------------------------
# Attaches a screenshot of the device at the moment of failure to BOTH the Allure
# report and the pytest-html report, and drops a PNG under reports/screenshots/ for
# CI artifact archiving. Works for the two driver patterns in this suite with no
# per-test edits:
#   - shared-account tests use the session `driver` fixture (a _DriverProxy). Its
#     underlying session is still alive when pytest_runtest_makereport fires, so we
#     capture it there from the live-driver registry.
#   - genuser_e2e tests build a local `appium_webdriver.Remote(...)` and quit() it in
#     their own `finally`, which runs BEFORE makereport. So we also snapshot inside a
#     wrapped quit() when an exception is in flight, stash it keyed by the current
#     test, and let makereport drain the stash.
# Everything here is best-effort and fully guarded — it must never turn a pass into a
# failure or mask the real error.
import threading as _threading

_LIVE_DRIVERS = []                       # Appium sessions currently alive in THIS process
_LIVE_LOCK = _threading.Lock()
_PENDING_SHOTS = {}                      # nodeid -> [(png_bytes, page_source_str), ...]
_SHOT_DIR = os.path.join(os.path.dirname(__file__), "reports", "screenshots")


def _register_driver(d):
    with _LIVE_LOCK:
        _LIVE_DRIVERS.append(d)


def _deregister_driver(d):
    with _LIVE_LOCK:
        try:
            _LIVE_DRIVERS.remove(d)
        except ValueError:
            pass


def _current_test_id():
    """Stable nodeid for the test currently executing (no ' (call)'/'(setup)' suffix)."""
    raw = os.environ.get("PYTEST_CURRENT_TEST", "")
    return raw.split(" (")[0] if raw else ""


def _grab(driver):
    """Return (png_bytes_or_None, page_source_or_None) from a live Appium session."""
    png = src = None
    try:
        png = driver.get_screenshot_as_png()
    except Exception:
        png = None
    try:
        src = driver.page_source
    except Exception:
        src = None
    return png, src


def _install_driver_tracking():
    """Wrap appium.webdriver.Remote once so every constructed session is tracked.

    Both the conftest fixture and the genuser tests construct via
    `appium_webdriver.Remote(...)` (an attribute lookup on the appium.webdriver
    module at call time), so replacing that attribute reaches all call sites."""
    try:
        from appium import webdriver as _aw
    except Exception:
        return
    if getattr(_aw, "_raiz_shot_patched", False):
        return
    _RealRemote = _aw.Remote

    class _TrackedRemote(_RealRemote):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            _register_driver(self)

        def quit(self, *a, **k):
            # If we're unwinding a failing test (its `finally: d.quit()` runs while
            # the assertion error propagates), snapshot BEFORE tearing the session
            # down — makereport fires too late, after this driver is already gone.
            try:
                import sys
                if sys.exc_info()[0] is not None:
                    nodeid = _current_test_id()
                    if nodeid:
                        png, src = _grab(self)
                        if png or src:
                            _PENDING_SHOTS.setdefault(nodeid, []).append((png, src))
            except Exception:
                pass
            _deregister_driver(self)
            return super().quit(*a, **k)

    _aw.Remote = _TrackedRemote
    _aw._raiz_shot_patched = True


def _attach_shot(item, report, png, src, idx):
    """Send one (png, src) to Allure, the pytest-html report, and disk."""
    when = getattr(report, "when", "call")
    # Allure
    if png or src:
        try:
            import allure
            if png:
                allure.attach(png, name="failure-screenshot",
                              attachment_type=allure.attachment_type.PNG)
            if src:
                allure.attach(src, name="page-source",
                              attachment_type=allure.attachment_type.XML)
        except Exception:
            pass
    # Disk (for CI artifact archiving + headless triage)
    if png:
        try:
            os.makedirs(_SHOT_DIR, exist_ok=True)
            import re
            base = re.sub(r"[^A-Za-z0-9._-]+", "_", report.nodeid)[:150]
            suffix = f"_{idx}" if idx else ""
            with open(os.path.join(_SHOT_DIR, f"{base}__{when}{suffix}.png"), "wb") as fh:
                fh.write(png)
        except Exception:
            pass
    # pytest-html (inline base64 so it survives --self-contained-html)
    if png:
        try:
            html = item.config.pluginmanager.getplugin("html")
            if html is not None:
                import base64
                b64 = base64.b64encode(png).decode("ascii")
                extras = getattr(report, "extras", [])
                extras.append(html.extras.png(b64, name="failure-screenshot"))
                report.extras = extras
        except Exception:
            pass


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On a failed setup/call phase, attach a device screenshot + page source."""
    outcome = yield
    report = outcome.get_result()
    if report.when not in ("setup", "call") or not report.failed:
        return
    try:
        # 1) Genuser pattern: driver already quit in the test's finally — drain the
        #    snapshot it stashed on the way out.
        stashed = _PENDING_SHOTS.pop(item.nodeid, [])
        for idx, (png, src) in enumerate(stashed):
            _attach_shot(item, report, png, src, idx)
        # 2) Shared-account pattern (or a leaked/never-quit driver): the session is
        #    still alive — capture the active one now. Skip if (1) already produced
        #    a shot for this test.
        if not stashed:
            with _LIVE_LOCK:
                live = list(_LIVE_DRIVERS)
            for d in reversed(live):          # newest first = the active session
                png, src = _grab(d)
                if png or src:
                    _attach_shot(item, report, png, src, 0)
                    break
    except Exception:
        pass
    finally:
        # Don't let the stash grow unbounded if a test passed after stashing
        # (e.g. a caught-and-handled exception triggered a quit mid-test).
        _PENDING_SHOTS.pop(item.nodeid, None)
