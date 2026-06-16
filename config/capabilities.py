from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from config.settings import (
    ANDROID_UDID, ANDROID_APP_PACKAGE, ANDROID_APP_ACTIVITY,
    IOS_UDID, IOS_BUNDLE_ID, IOS_XCODE_ORG_ID,
)


def get_android_options(no_reset: bool = True) -> UiAutomator2Options:
    import os
    opts = UiAutomator2Options()
    opts.device_name = "Samsung Galaxy S23"
    opts.udid = ANDROID_UDID
    opts.app_package = ANDROID_APP_PACKAGE
    opts.app_activity = ANDROID_APP_ACTIVITY
    opts.no_reset = no_reset
    opts.full_reset = False
    opts.auto_grant_permissions = True
    opts.new_command_timeout = 120
    # Concurrent-device support: when running the suite against several devices in
    # parallel (one pytest process per device), each UiAutomator2 session needs a
    # distinct host systemPort/mjpegServerPort or they collide on the 8200/7810
    # defaults. Set ANDROID_SYSTEM_PORT (and optionally ANDROID_MJPEG_PORT) per
    # process. Defaults preserve single-device behaviour.
    _sysport = os.getenv("ANDROID_SYSTEM_PORT")
    if _sysport:
        opts.set_capability("systemPort", int(_sysport))
    _mjpeg = os.getenv("ANDROID_MJPEG_PORT")
    if _mjpeg:
        opts.set_capability("mjpegServerPort", int(_mjpeg))
    opts.uiautomator2_server_launch_timeout = 60000
    # --- Stability hardening ---
    # The UiAutomator2 instrumentation can crash mid-run (observed: UiAutomation
    # DeadObjectException on Samsung One UI), which kills the whole session. These
    # reduce the chance and give the server more room before timing out. Recovery
    # from an actual crash is handled by the self-healing driver in conftest.py.
    opts.set_capability("disableWindowAnimation", True)
    opts.set_capability("uiautomator2ServerReadTimeout", 90000)
    opts.set_capability("uiautomator2ServerInstallTimeout", 90000)
    opts.set_capability("ignoreHiddenApiPolicyError", True)
    opts.set_capability("forceAppLaunch", True)
    return opts


def get_ios_options(no_reset: bool = True) -> XCUITestOptions:
    opts = XCUITestOptions()
    opts.device_name = "iPhone"
    opts.udid = IOS_UDID
    opts.bundle_id = IOS_BUNDLE_ID
    opts.xcode_org_id = IOS_XCODE_ORG_ID
    opts.no_reset = no_reset
    opts.full_reset = False
    opts.new_command_timeout = 120
    return opts
