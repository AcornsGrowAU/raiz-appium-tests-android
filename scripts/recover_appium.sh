#!/usr/bin/env bash
#
# Recover a wedged UiAutomator2 / Appium device state.
#
# Symptom this fixes:
#   "POST /elements cannot be proxied to UiAutomator2 server because the
#    instrumentation process is not running (probably crashed)"
#   ...repeated on every test (a UiAutomation DeadObjectException crash loop).
#
# The in-run self-healing driver (conftest._DriverProxy) recovers crashes that
# happen DURING a run. Use this script when the device is wedged so badly that a
# fresh session won't even start — it clears the crashed processes so the next
# `pytest` can establish a clean session.
#
# Usage:  ./scripts/recover_appium.sh
set -uo pipefail

ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
APP="${ANDROID_APP_PACKAGE:-com.acornsau.android.development}"

if [ ! -x "$ADB" ] && ! command -v adb >/dev/null 2>&1; then
  echo "adb not found. Set ADB=/path/to/adb or add platform-tools to PATH." >&2
  exit 1
fi
command -v adb >/dev/null 2>&1 && ADB="adb"

echo "Device:"; "$ADB" devices

echo "Force-stopping Appium + app processes…"
for pkg in io.appium.uiautomator2.server io.appium.uiautomator2.server.test io.appium.settings "$APP"; do
  "$ADB" shell am force-stop "$pkg" >/dev/null 2>&1 && echo "  stopped $pkg"
done

echo "Killing any stray instrumentation…"
"$ADB" shell "pkill -f uiautomator 2>/dev/null; pkill -f 'am instrument' 2>/dev/null" >/dev/null 2>&1 || true

echo "Remaining instrumentation/uiautomator processes (should be none):"
"$ADB" shell ps -A 2>/dev/null | grep -iE 'instrument|uiautomat' | grep -v 'io.appium.settings' || echo "  clean"

echo
echo "If it STILL won't start after this, escalate:"
echo "  1) Reinstall the server APKs (Appium auto-reinstalls):"
echo "       $ADB uninstall io.appium.uiautomator2.server"
echo "       $ADB uninstall io.appium.uiautomator2.server.test"
echo "  2) Reboot the device (clears the system-side dead UiAutomation):"
echo "       $ADB reboot"
echo
echo "Done. Re-run: pytest -m e2e"
