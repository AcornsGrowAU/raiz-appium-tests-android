import os
from dotenv import load_dotenv

load_dotenv()

APPIUM_HOST = os.getenv("APPIUM_HOST", "http://127.0.0.1:4723")
PLATFORM = os.getenv("PLATFORM", "android").lower()

# Test account
TEST_EMAIL = os.getenv("TEST_EMAIL", "raizjoshnew+5847266@gmail.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "TestAccount123*")
TEST_PIN = os.getenv("TEST_PIN", "0000")

# Round-Ups bank-link sandbox (Yodlee test institution "Dag Site (US)").
# Sandbox credentials only — used by the opt-in destructive link flow.
CDR_TEST_INSTITUTION = os.getenv("CDR_TEST_INSTITUTION", "Dag Site (US)")
CDR_TEST_USERNAME = os.getenv("CDR_TEST_USERNAME", "raiz_dev.site16441.1")
CDR_TEST_PASSWORD = os.getenv("CDR_TEST_PASSWORD", "site16441.1")

# Timeouts
DEFAULT_WAIT = 10
LONG_WAIT = 20
ANIMATION_WAIT = 2
# Short timeout for state-detection probes (e.g. "are we on the PIN screen?"). If
# the screen is going to appear it appears immediately; we don't want to burn the
# full DEFAULT_WAIT on the false branch.
STATE_PROBE_WAIT = 2
# Probe for transient modals (biometrics prompt, promo close). Appear instantly
# or not at all.
MODAL_PROBE_WAIT = 1
# WebDriverWait polling interval. Selenium defaults to 0.5s; 0.1s detects
# already-visible elements roughly 5x faster without meaningful CPU cost.
POLL_INTERVAL = 0.1

# Android
ANDROID_UDID = os.getenv("ANDROID_UDID", "RFCX80S23GM")
ANDROID_APP_PACKAGE = os.getenv("ANDROID_APP_PACKAGE", "com.acornsau.android.development")
ANDROID_APP_ACTIVITY = os.getenv("ANDROID_APP_ACTIVITY", "com.raiz.main.MainActivity")

# iOS (populated when ready)
IOS_UDID = os.getenv("IOS_UDID", "")
IOS_BUNDLE_ID = os.getenv("IOS_BUNDLE_ID", "com.acornsau.AcornsAU-dev")
IOS_XCODE_ORG_ID = os.getenv("IOS_XCODE_ORG_ID", "")
