# Raiz Appium Test Suite — Android

Python + pytest + Appium test suite for the Raiz AU Android app.
Built to be iOS-ready: capabilities and page locators are structured so iOS support can be added without restructuring the project.

---

## Prerequisites

- Python 3.11+
- [Appium 2.x](https://appium.io/docs/en/2.0/) running locally
- `appium driver install uiautomator2` (Android)
- Android device connected via USB with USB debugging enabled
- Raiz dev app installed (`com.acornsau.android.development`)

## Setup

```bash
cd "raiz-appium-tests"
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your device UDID if different
```

Start Appium server (separate terminal):
```bash
appium --relaxed-security
```

## Running Tests

```bash
# Full suite
pytest

# Smoke tests only (fast, critical paths)
pytest -m smoke

# Specific test file
pytest tests/test_auth.py
pytest tests/test_navigation.py

# Specific marker
pytest -m "portfolio or investments"

# Parallel (4 workers — requires separate devices or simulators)
pytest -n 4

# View HTML report after run
open reports/report.html
```

## Project Structure

```
raiz-appium-tests/
├── conftest.py              # Driver setup, all fixtures
├── pytest.ini               # Markers, test paths, report config
├── requirements.txt
├── .env.example             # Environment variable template
│
├── config/
│   ├── capabilities.py      # Android + iOS (stub) Appium caps
│   └── settings.py          # Credentials, timeouts, env vars
│
├── pages/                   # Page Object Model
│   ├── base_page.py         # Shared helpers (find, click, scroll, deep link)
│   ├── splash_page.py       # Landing / unauthenticated screen
│   ├── login_page.py        # Email + password login form
│   ├── pin_page.py          # PIN entry (on app restart)
│   ├── home_page.py         # Main dashboard
│   ├── nav_drawer.py        # Slide-out navigation drawer
│   ├── settings_page.py     # Settings modal
│   ├── main_portfolio_page.py
│   ├── performance_page.py  # Performance chart + time range
│   ├── lump_sum_page.py     # Lump Sum + Withdraw (shared keypad)
│   ├── rewards_page.py      # Rewards Earn + Track tabs
│   ├── jars_page.py
│   ├── kids_page.py
│   ├── transaction_history_page.py
│   └── my_finance_page.py
│
├── tests/
│   ├── test_auth.py         # Login, PIN, logout, error states
│   ├── test_home.py         # Home screen content + navigation
│   ├── test_navigation.py   # Drawer + all deep links
│   ├── test_portfolio.py    # Main Portfolio, Performance, Transactions
│   ├── test_investments.py  # Lump Sum, Withdraw, Add Funds modal, Recurring
│   ├── test_rewards.py      # Rewards Earn + Track tabs
│   ├── test_settings.py     # Settings items + navigation
│   ├── test_jars.py         # Raiz Jars screen
│   ├── test_kids.py         # Raiz Kids screen
│   ├── test_e2e_flows.py    # E2E journeys w/ value+state assertions (see docs/)
│   ├── test_allocation_jars_kids_e2e.py  # Allocation 100%, Plus, Jar/Kid create
│   └── test_more_e2e_flows.py  # Round-Ups, Super, My Finance, Recurring
│
├── utils/
│   ├── deep_links.py        # All 40+ raiz:// deep link constants + open() helper
│   ├── assertions.py        # Money/percentage parsing + value assertions
│   └── helpers.py           # Wait, scroll, dismiss modal utilities
│
└── docs/
    └── TEST_SUITE_ANALYSIS.md  # Critical analysis, gap report, E2E roadmap
```

## Test Markers

| Marker | Description |
|---|---|
| `smoke` | Critical paths — run on every build |
| `regression` | Full regression suite |
| `auth` | Login, logout, PIN flows |
| `navigation` | Drawer and deep link navigation |
| `portfolio` | Main Portfolio and sub-screens |
| `investments` | Lump Sum, Withdraw, Recurring |
| `rewards` | Rewards Earn and Track tabs |
| `settings` | Settings screen |
| `e2e` | Full end-to-end journeys that assert value/state, not just presence |
| `edge` | Negative / boundary cases (below minimum, over balance) |
| `destructive` | Commits a real DEV transaction — opt-in via `RUN_DESTRUCTIVE=1` |

## Deep Links

All 40+ `raiz://` deep links are in `utils/deep_links.py`. Tests use these to navigate directly to screens rather than tapping through the UI — this makes tests faster and more resilient to UI changes in navigation flows.

```python
from utils.deep_links import DeepLinks
DeepLinks.open(driver, DeepLinks.PORTFOLIO)
```

## Test Account

```
Email:    raizjoshnew+5847266@gmail.com
Password: TestAccount123*
PIN:      0000
```

This account has:
- Main Portfolio with transaction history
- Raiz Jars (active jar)
- Raiz Kids (5 kids accounts)
- Superannuation account

## Adding iOS Support

1. Fill in `IOS_UDID`, `IOS_BUNDLE_ID`, `IOS_XCODE_ORG_ID` in `.env`
2. Run the iOS device through the same ADB-equivalent inspection (`xcrun simctl` or Appium Inspector) to capture XCUITest accessibility IDs
3. Add iOS locators to each page object as a second locator strategy:
   ```python
   # In each page object — example pattern
   if platform == "ios":
       TITLE = (AppiumBy.ACCESSIBILITY_ID, "ios_accessibility_id_here")
   else:
       TITLE = (AppiumBy.XPATH, "//android.widget.TextView[@text='...']")
   ```
4. Update `conftest.py` to select capabilities based on `PLATFORM` env var — already handled.

## Troubleshooting

### "instrumentation process is not running (probably crashed)" on every test

The UiAutomator2 instrumentation crashed mid-run (commonly a UiAutomation
`DeadObjectException` on Samsung One UI). Because the driver is session-scoped,
every subsequent test then fails with the same error.

- **During a run:** the self-healing driver (`conftest._DriverProxy`) detects the
  dead session before the next test and rebuilds it automatically — the run
  continues instead of cascading.
- **If a session won't even start** (device wedged in a crash loop):
  ```bash
  ./scripts/recover_appium.sh      # force-stops the crashed processes
  ```
  If it persists, the script prints the escalation steps (reinstall the server
  APKs, then reboot the device to clear the system-side dead UiAutomation).
