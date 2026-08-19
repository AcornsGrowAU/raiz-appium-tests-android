"""
hdpi-round-button-no-crash (RAIZ-10898 regression guard) — ON-DEVICE.

WHAT THIS GUARDS
----------------
RAIZ-10898 (fixed in 2.41.1 / 2.41.2): `RoundRippleButton` — the shared primary
CTA used across the app (and wrapped by `AnimatedRoundRippleButton`) — reads its
autosize min/max/granularity from dimen resources in `onSizeChanged` and hands them
straight to `TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(...)`.

On hdpi-density devices (~240dpi) the *hdpi* resource bucket overrode the
granularity to `0.5sp` (raizUi/res/values-hdpi/dimen.xml). At scale 1.5 that is
0.75px, which the pre-fix code truncated to **0px**. `TextView` rejects a
granularity (or min/max) of 0 with an IllegalArgumentException → **fatal crash**
the instant such a button is laid out. It only reproduces at hdpi because only the
hdpi bucket carried the sub-1sp value (default values/dimen.xml granularity = 1sp).

The fix removes the hdpi `0.5sp` override and coerces min/max/granularity to
`>= 1px`. This test forces the device into the hdpi bucket, drives the app onto
screens that inflate a `RoundRippleButton`, and asserts the app does NOT crash.

  * On a FIXED build (>= 2.41.1): the button inflates at hdpi, the screen renders,
    the app stays foreground -> PASS.
  * On a PRE-FIX build: the button's onSizeChanged throws, the process dies, the
    foreground drops to the launcher / a system "keeps stopping" dialog -> FAIL.

DENSITY-OVERRIDE MECHANISM
--------------------------
The crash is density-gated, so the test must put the *whole UiAutomator2 session's*
device into the hdpi bucket. It does that with `wm density 240` run through, in
order of preference:
  1. Appium's `driver.execute_script("mobile: shell", {"command": "wm", ...})` —
     available because the suite's runner starts Appium with `--relaxed-security`
     (see scripts/run_parallel.sh, scripts/run_queue.sh), which enables `adb_shell`.
  2. A direct `adb -s <udid> shell wm density 240` fallback for setups without
     relaxed security (udid resolved from the live session's capabilities / env).
If NEITHER works, OR the override cannot be confirmed at 240, the test SKIPs with a
reason (it never pretends to have tested hdpi) — RAIZ-10898 then needs a real hdpi
device / the manual repro in this module's footer.

SAFETY (global state)
---------------------
`wm density` is a global, session-wide change; the suite's `driver` is
session-scoped and shared. So the density is ALWAYS restored via `wm density reset`
in a `finally` — on pass, on assertion failure, and on any exception — and the app
is returned to Home afterwards. The conftest's autouse self-healing
(`_reauthenticate_if_needed`, the `home` fixture) recovers the following test even
if the density flip disrupted the shared session. Under `-n` (xdist) each worker
owns its own device, so the blast radius is that one device only.

NON-VACUOUS
-----------
The "no crash" assertion is only made AFTER the test has PROVEN the device is at
density 240 (it reads `wm density` back). If it cannot establish hdpi it skips, so
it can never pass at the emulator's native (non-hdpi) density where the bug is
invisible. The load-bearing screen (Invest / Main portfolio) must positively render
its button-bearing layout at hdpi, not merely keep the app in the foreground.
"""
import os
import subprocess
import time

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from config.settings import (
    ANDROID_APP_PACKAGE, DEFAULT_WAIT, LONG_WAIT, POLL_INTERVAL,
)
from utils.deep_links import DeepLinks
from pages.main_portfolio_page import MainPortfolioPage
from pages.portfolio_allocation_page import PortfolioAllocationPage

pytestmark = [pytest.mark.portfolio, pytest.mark.regression]

# hdpi bucket. Selecting 240 forces Android to resolve res/values-hdpi/*, which is
# where the crashing 0.5sp granularity lived.
HDPI_DENSITY = 240

# A native crash surfaces either as the app dropping out of the foreground (to the
# launcher) or as a system "keeps stopping" / "not responding" dialog. Apostrophes
# are avoided so the XPath string stays valid.
_CRASH_DIALOG = (
    AppiumBy.XPATH,
    "//*[contains(@text,'keeps stopping') or contains(@text,'has stopped') "
    "or contains(@text,'Close app') or contains(@text,'Open app again') "
    "or contains(@text,'not responding') or contains(@text,'Pause app')]",
)


# --- device shell plumbing ---------------------------------------------------

def _adb_udid(driver):
    caps = getattr(driver, "capabilities", None) or {}
    return (caps.get("deviceUDID") or caps.get("udid")
            or os.getenv("ANDROID_UDID"))


def _wm(driver, wm_args):
    """Run `wm <wm_args...>` on the device. Returns (ok: bool, stdout: str).

    Prefers Appium's `mobile: shell` (enabled by the runner's
    `appium --relaxed-security`); falls back to a direct `adb -s <udid> shell`.
    Never raises — callers decide whether an inability to run it is a SKIP."""
    # 1) In-session via Appium (no udid needed; honours relaxed-security).
    try:
        out = driver.execute_script(
            "mobile: shell", {"command": "wm", "args": list(wm_args)}
        )
        if isinstance(out, dict):
            out = out.get("stdout", "") or ""
        return True, (out or "")
    except Exception:
        pass
    # 2) Direct adb fallback for non-relaxed-security setups.
    udid = _adb_udid(driver)
    if not udid:
        return False, ""
    adb = os.getenv("ADB", "adb")
    try:
        res = subprocess.run(
            [adb, "-s", udid, "shell", "wm", *wm_args],
            capture_output=True, text=True, timeout=25,
        )
        if res.returncode == 0:
            return True, (res.stdout or "")
        return False, (res.stderr or "")
    except Exception:
        return False, ""


# --- crash oracle ------------------------------------------------------------

def _crashed(driver) -> bool:
    """True if the Raiz app is no longer foreground OR a system crash/ANR dialog
    is up — i.e. the RAIZ-10898 fatal crash has fired."""
    try:
        if driver.current_package != ANDROID_APP_PACKAGE:
            return True
    except Exception:
        # A dead session can't answer; treat as inconclusive-not-crashed here and
        # let the render/ survival waits below decide.
        return False
    try:
        if driver.find_elements(*_CRASH_DIALOG):
            return True
    except Exception:
        pass
    return False


def _await_render(driver, page, timeout) -> str:
    """Poll until `page` renders its button-bearing layout, a crash is detected, or
    we time out. Returns 'loaded' | 'crashed' | 'timeout'."""
    end = time.time() + timeout
    while time.time() < end:
        if _crashed(driver):
            return "crashed"
        try:
            if page.is_loaded(timeout=0):
                return "loaded"
        except Exception:
            pass
        time.sleep(POLL_INTERVAL * 3)
    return "crashed" if _crashed(driver) else "timeout"


def _survives_for(driver, seconds) -> bool:
    """Watch the app for `seconds` after a navigation and confirm it does not crash
    while the screen (and its RoundRippleButton) inflates."""
    end = time.time() + seconds
    while time.time() < end:
        if _crashed(driver):
            return False
        time.sleep(POLL_INTERVAL * 3)
    return not _crashed(driver)


def _dismiss_crash_dialog(driver):
    """Best-effort: clear a system crash/ANR dialog so it can't strand later tests."""
    try:
        for el in driver.find_elements(*_CRASH_DIALOG):
            try:
                el.click()
                return
            except Exception:
                continue
    except Exception:
        pass


# --- the test ----------------------------------------------------------------

def test_hdpi_round_button_no_crash(driver):
    # Establish hdpi. If we cannot even issue the override, this ticket needs a real
    # hdpi device / the manual repro below — skip honestly rather than fake a pass.
    set_ok, _ = _wm(driver, ["density", str(HDPI_DENSITY)])
    if not set_ok:
        pytest.skip(
            "skip-with-reason: cannot override display density — `mobile: shell` is "
            "disabled (start Appium with --relaxed-security) and adb is unreachable. "
            "RAIZ-10898 is density-gated (hdpi/240dpi) and needs a real hdpi device "
            "or the manual repro documented in this module."
        )

    try:
        # Confirm the override actually took. Without this the 'no crash' assertion
        # could pass vacuously at the emulator's native (non-hdpi) density, where the
        # bug is invisible. `wm density` prints e.g. "Physical density: 420\n
        # Override density: 240". If we can't confirm 240, skip (env problem, not a
        # product signal).
        got_ok, dump = _wm(driver, ["density"])
        if not (got_ok and str(HDPI_DENSITY) in (dump or "")):
            pytest.skip(
                "skip-with-reason: could not confirm the hdpi (240) density override "
                f"took effect. `wm density` reported: {dump!r}. Not testing at hdpi "
                "-> would be a vacuous pass."
            )

        # Give the running app a beat to absorb the configuration change (activities
        # recreate + re-resolve resources into the hdpi bucket).
        time.sleep(1.0)

        # (1) LOAD-BEARING screen: Invest / Main portfolio. fragment_portfolio.xml
        # inflates an AnimatedRoundRippleButton (which wraps RoundRippleButton), so
        # this deep link forces a fresh inflation of the crashing button at hdpi.
        # Require a POSITIVE render — the button-bearing screen must actually appear
        # at 240dpi without the app dying.
        DeepLinks.open(driver, DeepLinks.INVEST)
        status = _await_render(driver, MainPortfolioPage(driver), LONG_WAIT)
        if status == "timeout":
            # One reopen-retry, matching the main_portfolio fixture's own tolerance
            # for a slow deep-link render under memory pressure.
            DeepLinks.open(driver, DeepLinks.INVEST)
            status = _await_render(driver, MainPortfolioPage(driver), LONG_WAIT)
        assert status != "crashed", (
            "RAIZ-10898 regression: the app CRASHED rendering a RoundRippleButton on "
            "the Invest / Main portfolio screen at hdpi (240dpi) — the autosize "
            "granularity resolved to 0px again."
        )
        assert status == "loaded", (
            "The Invest / Main portfolio screen never rendered at hdpi within "
            f"{LONG_WAIT}s (no crash detected, but the button-bearing screen must "
            "inflate to actually exercise the RAIZ-10898 fix)."
        )

        # (2) Portfolio allocation (raiz://portfolio) — the plus/pro fragments also
        # inflate an AnimatedRoundRippleButton. Survival-only oracle: this screen can
        # be plan-gated on some accounts, so we assert the app does not crash while it
        # settles rather than requiring a specific render.
        DeepLinks.open(driver, DeepLinks.PORTFOLIO)
        assert _survives_for(driver, DEFAULT_WAIT), (
            "RAIZ-10898 regression: the app CRASHED after navigating to the Portfolio "
            "allocation screen (raiz://portfolio) at hdpi (240dpi)."
        )

        # (3) Custom portfolio (raiz://portfolio/custom) — pro funds / plus RPF
        # fragments render an AnimatedRoundRippleButton too. Survival-only oracle
        # (also plan-gated).
        DeepLinks.open(driver, DeepLinks.PORTFOLIO_CUSTOM)
        assert _survives_for(driver, DEFAULT_WAIT), (
            "RAIZ-10898 regression: the app CRASHED after navigating to the custom "
            "portfolio screen (raiz://portfolio/custom) at hdpi (240dpi)."
        )

    finally:
        # ALWAYS restore global density, whatever happened above, then leave the app
        # on a known Home so the next test in the shared session starts clean.
        _wm(driver, ["density", "reset"])
        _dismiss_crash_dialog(driver)
        try:
            DeepLinks.open(driver, DeepLinks.HOME)
        except Exception:
            pass


# =============================================================================
# MANUAL REPRO (use when the density override is unavailable and the test skips)
# -----------------------------------------------------------------------------
# 1. Install the build under test on a device/emulator in the hdpi bucket:
#        adb -s <udid> shell wm density 240
#    (confirm: `adb -s <udid> shell wm density` shows "Override density: 240")
# 2. Log in, then open each of these (they inflate a RoundRippleButton):
#        adb -s <udid> shell am start -a android.intent.action.VIEW -d raiz://invest
#        adb -s <udid> shell am start -a android.intent.action.VIEW -d raiz://portfolio
#        adb -s <udid> shell am start -a android.intent.action.VIEW -d raiz://portfolio/custom
#    A default confirmation dialog (dialog_default.xml -> btnCancel/btnConfirm) is
#    another trigger if a portfolio screen is not reachable on the account.
# 3. EXPECTED (fixed build 2.41.1+): every screen renders, app stays foreground, no
#    "keeps stopping" dialog. PRE-FIX: the app crashes the moment the button lays out.
# 4. ALWAYS restore: `adb -s <udid> shell wm density reset`.
# =============================================================================
