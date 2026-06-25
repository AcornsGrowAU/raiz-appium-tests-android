# Environment & Access

Everything needed to get the Raiz Appium suite running, plus the infra gotchas that
dominate this setup. **Secrets are not here** — they live in `config/.env` /
`config/settings.py` and the team password manager.

## Source repos (read-only grounding)

| Repo | Stack | Use it for | Clone |
|------|-------|------------|-------|
| `AcornsGrowAU/Android-AU` | Kotlin, Compose-heavy | real `contentDescription`/`testTag`/`text`/`android:id`, deep links, screen/flow names, exact strings | `git clone --depth 1 …/Android-AU ~/Android-AU` |
| `AcornsGrowAU/backend` | Ruby on Rails | data model (`app/models` associations), endpoints (`config/routes.rb`, `app/controllers`) — what to seed + reconcile against | `git clone --depth 1 …/backend ~/raiz-backend` |

Access: `gh` CLI (`brew install gh` → `gh auth login`, HTTPS, scope `repo`). Both repos
are **private**. Default branches: app `raiz_master`, backend `master`. In zsh, **quote
grep globs**: `grep -r --include="*.kt"` (unquoted `*.kt` → "no matches found").

## The app build

- Current dev APK: **build 3252 / v2.40.1d**, package `com.acornsau.android.development`,
  launch activity `com.raiz.main.MainActivity`. SSL-pinning-free dev builds (good for
  Appium). APKs are named `raiz_development_release_WITHOUT_SSL_PINNING__…__v<ver>_<build>.apk`.
- The suite targets by **package + activity** (`config/settings.py:ANDROID_APP_PACKAGE/
  _ACTIVITY`), not an APK path — so swapping builds is just `adb install -r <apk>` (`-r`
  preserves data + login). The versionName misleads; the home **layout** changed across
  builds (legacy "Hello/Main Portfolio/total investments value" vs redesigned
  "Welcome/Invest/Rewards/Super"). Always crawl the device or read source — don't assume.

## Emulators & the parallel rig

- One **Appium server per device** on its own port; each session needs a distinct
  `systemPort`/`mjpegPort` (env-driven, `config/capabilities.py` reads
  `ANDROID_SYSTEM_PORT`/`ANDROID_MJPEG_PORT`). Mapping used:
  `5554/4723/8201/7811`, `5556/4724/8202/7812`, `5558(or 5560)/4725/8204/7814`.
- Start a server: `nohup appium --relaxed-security -p 4724 &`.
- Per-device setup: log in once (email/password → PIN), disable autofill so the "Save
  password?" dialog doesn't block: `adb -s <udid> shell settings put secure autofill_service null`.
- `scripts/run_parallel.sh` shards the suite across devices (one pytest process each, its
  own ports, `caffeinate` to keep the Mac awake) and merges Allure results.

### ⚠️ The RAM ceiling (the single biggest infra constraint)

This Mac sustains **~2–3 concurrent emulator + Appium + test sessions**. A 3rd session on
2 GB AVDs reliably crashes UiAutomator2 instrumentation / drops the device. Symptoms:
whole-file `is_loaded()==False` error cascades, "instrumentation process is not running",
a shard dropping its device mid-run. **Verify on 2 stable emulators**; bring a 3rd online
only after one finishes; free host RAM (close Chrome/Slack/Android-Studio) before big runs.
3-way `pytest-xdist` was tried and is WORSE here (controller overhead). Always
isolate-retriage a parallel-run failure before believing it.

### PIN lockout (auto-recovered)

Heavy/parallel PIN entry trips the app's **"Too many attempts… use your email address and
password"** lockout → every test ERRORS at `conftest._ensure_logged_in`
("Expected to be on Home screen after login"). `conftest` now detects + dismisses the
dialog and forces a credential re-login (which resets the counter). If you see a uniform
all-tests-error-at-login signal, it's this (or a logged-out / wrong-build device), not
hundreds of real failures — reproduce the login flow first.

### macOS `~/Documents` TCC

The repo lives under `~/Documents` (TCC-protected). The Bash sandbox can lose readdir/exec
there mid-session (Python won't start; `ls` → "Operation not permitted") while `cat`/the
Read/Edit tools still work. Fix: System Settings → Privacy & Security → Full Disk Access →
enable the terminal/Claude app, then **relaunch** (the grant only applies to newly
launched processes).

## Test-data generation (DEV API)

- **DEV only:** `https://api-dev.raizinvest.com.au`. Auth: `POST /v1/sessions {email,
  password,udid}` → token; then `Authorization: token <tok>`. The generation creds (a user
  with the securities/test-data role) and the seeded-user password live in `config`/the
  password manager + `utils/genuser_api.py` env (`GEN_EMAIL`/`GEN_PWD`/`SEEDED_PWD`).
- Endpoint: `POST /internal/v1/test_data_generation` with `{payload: {<ref>: <entity>}}`.
  Entities reference each other by `@ref`. Helpers in `utils/genuser_api.py`
  (`gen_create`, `funded_user`, `ach_credit`, `ach_credits`, `kid_user`, `jar_user`,
  `current_balance`, `mint`).
- **Quirks:** the create endpoint flaps on a transient `rho_settled_at` 422 → retried
  automatically; `/v1/sessions` rate-limits bursts (400) → mint once + backoff; a single
  ACH transfer is **capped at $10,000** (split larger balances via `ach_credits`); the
  `count` attribute 500s — use explicit entities.
- **Build balances from real ACH** (`credit_investment`, `payment_method: "ACH"`): they
  settle to `current_balance` **exactly** and stay stable. Avoid the old `with_balance`
  trait (fabricated market-priced holdings that drift). See the test-strategy doc.

## Running tests

```
# one device
ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
  venv/bin/python -m pytest tests/test_x.py -o addopts="" -q

# on-device generated-user / destructive tests
RUN_DESTRUCTIVE=1 ANDROID_UDID=… APPIUM_HOST=… ANDROID_SYSTEM_PORT=8201 ANDROID_MJPEG_PORT=7811 \
  venv/bin/python -m pytest tests/test_y.py::test_z -p no:cacheprovider

# parallel shards
TIMEOUT=120 ./scripts/run_parallel.sh
```

`value_api` tests need no device. Allure: `allure serve reports/allure-results`.
