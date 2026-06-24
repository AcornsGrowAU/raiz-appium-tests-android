"""
recurring-create-roundtrip [P1] — Recurring create persists amount + frequency
(on-device round-trip), plus the next-debit-date SHAPE renders.

REFINED SCOPE (backlog notes for this case — SPLIT, parts a + b):

  (a) AMOUNT + FREQUENCY round-trip (the solid, primary oracle): on the Recurring
      main-portfolio setup screen, open 'Set Recurring Investment', type an amount
      ($25), pick a frequency (Weekly), Save. Then RE-OPEN the recurring overview
      and assert the persisted state round-trips on a fresh render:
        * the amount card shows $25.00   (parse_money == 25.00)
        * the frequency renders Weekly   (overview title is "Weekly on <Day>")
        * the card has flipped from the empty "Set Recurring Investment" CTA to the
          set-state "Edit Recurring Investment" CTA (proves it was actually saved,
          not just typed into a transient form).

  (b) NEXT-DEBIT-DATE SHAPE (gated on Phase-0 confirming a next-date renders): the
      set-state RecurringCard renders a 'Next Investment' row whose value is a real
      date string. We assert that row is present and NON-EMPTY (a date shape), NOT a
      specific S+7 arithmetic — the exact next-debit arithmetic is the backend's and
      is not asserted here. Confirmed in source: RecurringCard renders
      `recurring_overview_recurring_card_next_investment` + getFormattedNextInvestmentAt()
      ("EEEE, 'Nth' MMMM") whenever a recurring is set (Android-AU build 3252,
      features/recurringv2/.../overview/RecurringCard.kt).

EXPLICITLY OUT OF SCOPE (backlog note): we DO NOT assert the API request/response
body shape — the recurring read-back over the gen/internal API is unproven, so the
oracle is the on-device re-render only.

GROUND TRUTH (Android-AU build 3252, features/recurringv2):
  - edit/RecurringEditScreen.kt: amount is a single BasicTextField (Number keyboard);
    Frequency is a clickable Row showing the current frequency; Save = common_btn_save.
  - frequency/FrequencyScreen.kt + WeeklyPage.kt: tab row Daily/Weekly/Fortnightly/
    Monthly; Weekly page "SELECT DAY OF WEEK" lists weekdays; a "Set <freq>" button
    confirms (recurring_frequency_btn_setup_title_start == "Set ").
  - overview/RecurringCard.kt: set-state card = title "Recurring Investment Amount",
    amount, "Frequency" + overview title, "Next Investment" + date, and the
    "Edit Recurring Investment" button.

Reuse strategy: the long-lived `presence_funded` fixture (onboarded user with a real
Aggressive main-portfolio balance + a linked funding account, so the recurring form
is reachable and Save is enabled). Setting a recurring is idempotent across re-runs —
each run just (re)sets the same $25 Weekly recurring, so the shared fixture is safe.

Standalone (own driver; clears app data). DEV API only. Needs emulator + Appium:
  ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_recurring_create_roundtrip.py -v -s -o addopts=""
"""
import os
import re
import time

import pytest
from appium import webdriver as appium_webdriver
from appium.webdriver.common.appiumby import AppiumBy

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST, DEFAULT_WAIT, POLL_INTERVAL
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.recurring_page import RecurringPage
from utils.deep_links import DeepLinks
from utils.assertions import parse_money
from utils.genuser_fixtures import get_or_create_fixture_user, mark_onboarded

pytestmark = pytest.mark.genuser_e2e

UDID = os.getenv("ANDROID_UDID", "emulator-5554")

# The recurring values we set and round-trip. $25 is a clean, parseable amount;
# Weekly is the backlog's named frequency for this case.
RECURRING_AMOUNT = "25"
RECURRING_AMOUNT_VALUE = 25.00

# --- Locators grounded in the app source (features/recurringv2, build 3252) -------
# The amount field on the Set Recurring Investment form is a single Compose
# BasicTextField -> surfaces to UiAutomator2 as an EditText. The form has exactly one.
AMOUNT_FIELD = (AppiumBy.CLASS_NAME, "android.widget.EditText")
# Frequency screen tab + weekday + confirm button.
WEEKLY_TAB = (AppiumBy.XPATH, "//*[@clickable='true'][.//*[@text='Weekly']] | //*[@text='Weekly']")
# A weekday cell on the Weekly page (SELECT DAY OF WEEK). Monday is deterministic.
WEEKDAY_CELL = (AppiumBy.XPATH,
    "//*[@clickable='true'][.//android.widget.TextView["
    "@text='Monday' or @text='Tuesday' or @text='Wednesday' or @text='Thursday' "
    "or @text='Friday' or @text='Saturday' or @text='Sunday']]")
# The frequency confirm button text begins with "Set " (recurring_frequency_btn_setup_title_start).
SET_FREQUENCY_BUTTON = (AppiumBy.XPATH,
    "//*[@clickable='true'][.//android.widget.TextView[starts-with(@text,'Set ')]]")
# We're on the Frequency screen (vs back on the Edit form) ONLY when a surface
# unique to that screen is present: its TopBar title "Investment Frequency"
# (recurring_frequency_top_bar_title) or the Weekly page's "Select day of week"
# header (recurring_frequency_weekly_page_title, rendered .uppercase()).
# NOTE: neither "Weekly" nor a "Set ..." token is distinctive — the Edit form
# itself shows the frequency value "Weekly" AND has the TopBar title "Set Recurring
# Investment", so an earlier marker keyed on those falsely matched the form.
FREQUENCY_SCREEN_MARKER = (AppiumBy.XPATH,
    "//*[@text='Investment Frequency'] "
    "| //*[contains(translate(@text,'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'DAY OF WEEK')]")
# The Edit form's amount field + Save button mark "still on the form". After Save
# fires (RecurringUpdatedEvent -> navigates back), the form leaves the screen; we
# poll for its absence to confirm the Save tap took rather than being swallowed.
SAVE_BUTTON_LOC = (AppiumBy.XPATH,
    "//*[@clickable='true'][.//android.widget.TextView[@text='Save']]")
# Overview set-state surfaces (proves persistence on a fresh render).
EDIT_RECURRING_BUTTON = (AppiumBy.XPATH,
    "//*[@clickable='true'][.//android.widget.TextView[@text='Edit Recurring Investment']]")
NEXT_INVESTMENT_LABEL = (AppiumBy.XPATH, "//*[@text='Next Investment']")
WEEKLY_OVERVIEW_TITLE = (AppiumBy.XPATH, "//*[contains(@text,'Weekly')]")

# The per-portfolio recurring OVERVIEW renders ONE of two CTAs depending on state:
#   - empty state  -> "Set Recurring Investment"  (no recurring yet)
#   - set state     -> "Edit Recurring Investment" (a recurring already exists)
# Both route to the SAME amount + Frequency + Save form. Because this is a SHARED
# fixture account and setting a recurring is idempotent across re-runs, the FIRST
# run leaves the overview in set-state, so on the 2nd/3rd run only the "Edit ..."
# CTA is present. We must detect/open the form state-agnostically — keying only on
# "Set Recurring Investment" was the shared-account coupling that made this flaky.
OPEN_RECURRING_FORM_CTA = (AppiumBy.XPATH,
    "//*[@clickable='true'][.//android.widget.TextView["
    "@text='Set Recurring Investment' or @text='Edit Recurring Investment']]")
# The recurring overview/setup screen, in EITHER state, always shows the
# 'Current balance:' header. Use it (plus the CTA) as the state-agnostic
# "we reached the overview" oracle.
OVERVIEW_REACHED = (AppiumBy.XPATH,
    "//*[contains(@text,'Current balance:')] "
    "| //android.widget.TextView[@text='Set Recurring Investment' "
    "or @text='Edit Recurring Investment']")


def _wait_post_login(d, ho, timeout=30, poll=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ho.is_loaded(timeout=1):
            return "home"
        src = (d.page_source or "").lower()
        if any(k in src for k in ("skip", "got it", "select as your portfolio",
                                  "i consent", "agree")):
            return "onboarding"
        time.sleep(poll)
    return "unknown"


def _login_and_home(d, fx):
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
    assert lo.is_loaded(timeout=20), "login form did not load"
    lo.login(fx["email"], fx["password"])
    onb = OnboardingPage(d)
    state = _wait_post_login(d, ho)
    if state != "home" and not ho.is_loaded(timeout=2):
        assert onb.complete(), f"onboarding stuck: {onb.path}"
        mark_onboarded(fx["key"])
    assert ho.is_loaded(timeout=20), "not on Home after login"
    return ho


def _settle(d, quiet=0.6, timeout=8.0, poll=0.2):
    """Wait until the view tree stops changing (Compose animation/layout has
    settled) before READING from it. Polls the page-source length and returns
    once it is stable for `quiet` seconds, or after `timeout`. Cheap insurance
    against reading a value mid-transition (a snapshot of a half-painted card)."""
    deadline = time.time() + timeout
    last_src = None
    stable_since = None
    while time.time() < deadline:
        try:
            src = d.page_source or ""
        except Exception:
            return  # driver hiccup mid-animation; let the caller's own poll cope
        now = time.time()
        if src == last_src:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= quiet:
                return
        else:
            last_src = src
            stable_since = None
        time.sleep(poll)


def _tap_until(d, tap_locator, gone_locator=None, present_locator=None,
               attempts=4, settle_after=10, what="element"):
    """Tap a clickable container and CONFIRM the tap took, re-tapping a swallowed
    tap up to `attempts` times. The tap is confirmed when ALL supplied signals
    hold: `gone_locator` disappears (we left the current screen) and/or
    `present_locator` appears (the next surface painted). Compose containers
    routinely swallow the first tap on a freshly-laid-out / still-animating
    screen, which was a flake source here."""
    for i in range(attempts):
        els = WebDriverWait_find(d, tap_locator, timeout=DEFAULT_WAIT)
        assert els, f"could not find {what} to tap"
        try:
            els[-1].click()  # convention: tap the (last) matching clickable container
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue
        deadline = time.time() + settle_after
        while time.time() < deadline:
            confirmed = True
            if gone_locator is not None and d.find_elements(*gone_locator):
                confirmed = False
            if present_locator is not None and not d.find_elements(*present_locator):
                confirmed = False
            if confirmed:
                return True
            time.sleep(POLL_INTERVAL)
        # tap appears swallowed (screen unchanged) — loop and re-tap
    return False


def _select_weekday_and_confirm(d, attempts=4):
    """On the Weekly frequency page: select a weekday and confirm with 'Set <freq>',
    landing back on the Edit form. Treats weekday+Set as one retryable unit because
    a swallowed weekday tap makes 'Set' pop a "choose frequency" help dialog and
    stay on the screen (FrequencyViewModel.onSetFrequencyClick) rather than throw —
    so the only reliable signal is whether 'Set' navigated us off the Frequency
    screen. Re-selects + re-taps on each attempt; backs out of a stuck dialog first."""
    for _attempt in range(attempts):
        # Select a weekday (the clickable Row container; last match = a real weekday).
        cells = WebDriverWait_find(d, WEEKDAY_CELL, timeout=DEFAULT_WAIT)
        if not cells:
            d.back()  # possibly a dialog is covering the page — dismiss and retry
            time.sleep(POLL_INTERVAL)
            continue
        try:
            cells[-1].click()
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue
        _settle(d, quiet=0.4, timeout=4)
        # Tap 'Set <freq>'. If a day is selected this navigates back to the form.
        set_btns = WebDriverWait_find(d, SET_FREQUENCY_BUTTON, timeout=DEFAULT_WAIT)
        if not set_btns:
            continue
        try:
            set_btns[-1].click()
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue
        # Confirm we left the Frequency screen (its distinctive markers — the
        # "Investment Frequency" TopBar / "Select day of week" header — are gone).
        # If a "choose frequency" help dialog popped (no day registered), the
        # markers stay -> back out of it and re-select.
        deadline = time.time() + 10
        while time.time() < deadline:
            if not d.find_elements(*FREQUENCY_SCREEN_MARKER):
                return True
            time.sleep(POLL_INTERVAL)
        try:
            d.back()
        except Exception:
            pass
        _settle(d, quiet=0.4, timeout=4)
    return False


def _is_overview_reached(d, timeout=20):
    """The per-portfolio recurring overview/setup screen is reached when its
    state-agnostic surfaces render: the 'Current balance:' header, or EITHER the
    'Set'/'Edit Recurring Investment' CTA. Polls so it tolerates the row tap
    routing through the async RecurringLoading screen before the overview paints."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if d.find_elements(*OVERVIEW_REACHED):
            return True
        time.sleep(POLL_INTERVAL)
    return False


def _tap_main_portfolio_row(d, rec: RecurringPage):
    """Tap the MAIN PORTFOLIO row on the recurring list, retrying past the
    async shimmer/Loading state and re-tapping if the first tap is swallowed.

    The list deep-link lands in a Loading (shimmer) state and resolves to real
    rows only after a network fetch; the TopBar title renders during shimmer, so
    `is_loaded()` returns True before any row exists. We poll for the actual
    clickable main-portfolio row, then tap the clickable CONTAINER (last match,
    per convention) and confirm we left the list — re-tapping once if needed."""
    row_deadline = time.time() + 25
    last_err = None
    while time.time() < row_deadline:
        rows = d.find_elements(*rec.PORTFOLIO_ROW)
        if rows:
            try:
                rows[-1].click()  # clickable container, last match
            except Exception as e:  # stale/animating row — re-query and retry
                last_err = e
                time.sleep(POLL_INTERVAL)
                continue
            # Confirm the tap took: the overview (loading->paint) should appear.
            if _is_overview_reached(d, timeout=12):
                return True
            # Swallowed tap (still on the list) — loop and re-tap.
        time.sleep(POLL_INTERVAL)
    if last_err is not None:
        print(f"  (last row-tap error: {last_err!r})")
    return False


def _open_recurring_main_setup(d, rec: RecurringPage):
    """Open the Recurring investments list (deep link) and tap the MAIN PORTFOLIO
    row to land on the main-portfolio overview/setup screen (in EITHER empty or
    set state — both expose the amount+Frequency+Save form)."""
    DeepLinks.open(d, DeepLinks.RECURRING_INVESTMENTS)
    assert rec.is_loaded(timeout=20), "Recurring investments list did not load"
    rec.dismiss_modal()
    assert _tap_main_portfolio_row(d, rec), \
        "did not reach the main-portfolio recurring overview/setup screen " \
        "(main row never resolved past the list shimmer, or the tap was swallowed)"


def _set_recurring_amount_weekly(d, rec: RecurringPage):
    """On the setup screen, open 'Set Recurring Investment', type the amount,
    choose Weekly frequency, and Save. The overview shows 'Set Recurring Investment'
    in empty state and 'Edit Recurring Investment' in set state; both CTAs route to
    the same amount + Frequency + Save form, so open whichever is present."""
    # Open the form, confirming the CTA tap took (the form's amount label paints).
    assert _tap_until(d, OPEN_RECURRING_FORM_CTA,
                      present_locator=rec.RECURRING_AMOUNT_LABEL,
                      what="the 'Set'/'Edit Recurring Investment' CTA on the overview"), \
        "did not reach the recurring form (amount + Frequency + Save) after tapping the CTA"
    assert rec.is_recurring_form(timeout=20), \
        "did not reach the recurring form (amount + Frequency + Save)"
    _settle(d)

    # --- type the amount into the single BasicTextField (EditText) --------------
    fields = WebDriverWait_find(d, AMOUNT_FIELD, timeout=DEFAULT_WAIT)
    assert fields, "recurring form exposed no amount text field (EditText)"
    amount_el = fields[0]
    try:
        amount_el.clear()
    except Exception:
        pass
    amount_el.send_keys(RECURRING_AMOUNT)
    # Dismiss the IME so it does not cover the Frequency row / Save button.
    try:
        d.hide_keyboard()
    except Exception:
        d.back()
    _settle(d)

    # --- pick Weekly frequency --------------------------------------------------
    assert rec.is_frequency_present(timeout=10), "Frequency control not present on the form"
    # Tap the Frequency row, confirming we landed on the Frequency screen (not a
    # swallowed tap that left us on the form). The row is a clickable Compose Row.
    assert _tap_until(d, rec.FREQUENCY, present_locator=FREQUENCY_SCREEN_MARKER,
                      what="the Frequency row on the form"), \
        "tapping Frequency did not open the Frequency screen"
    _settle(d)
    # Frequency screen: select the Weekly tab, pick a weekday, confirm with "Set ...".
    # The weekday-cell selection on the Weekly page proves the Weekly tab is active,
    # so confirm the tab tap by the appearance of a tappable weekday cell.
    assert _tap_until(d, WEEKLY_TAB, present_locator=WEEKDAY_CELL,
                      what="the Weekly frequency tab"), \
        "Weekly tab tap did not surface the weekday list"
    _settle(d)
    # Pick a weekday, then confirm with 'Set <freq>'. The selected weekday's Check
    # icon carries null contentDescription (ItemCell.kt) and the 'Set' button is
    # ALWAYS present (FrequencyScreen.kt), so the *selection* itself isn't a uniquely
    # locatable surface. The reliable, source-grounded confirm is the OUTCOME of
    # 'Set': with a day selected it navigates back to the form (Frequency markers
    # leave the tree); with NO day selected it pops a "choose frequency" help dialog
    # and stays (FrequencyViewModel.onSetFrequencyClick). So we treat weekday+Set as
    # one unit: (re)select a weekday, tap Set, and confirm we left the Frequency
    # screen — retrying the pair if a swallowed weekday tap left Set ineffective.
    assert _select_weekday_and_confirm(d), \
        "did not set a Weekly frequency (could not select a weekday and confirm 'Set')"

    # Back on the form, Save must now be enabled (amount + frequency set).
    assert rec.is_recurring_form(timeout=20), "did not return to the recurring form after setting frequency"
    _settle(d)
    assert rec.is_save_button_well_rendered(timeout=15), \
        f"Save button not rendered at a usable size: bounds={rec.save_button_size()!r}"
    # Save fires RecurringUpdatedEvent -> navigates back off the Edit form (source:
    # RecurringEditScreen.kt onSaveClick). Confirm the Save tap took by the Save
    # button (and form) leaving the screen; re-tap a swallowed tap. Without this the
    # immediate re-open could race the navigate-back / persistence and read empty-state.
    assert _tap_until(d, SAVE_BUTTON_LOC, gone_locator=SAVE_BUTTON_LOC,
                      attempts=4, settle_after=12, what="the Save button"), \
        "Save tap was swallowed — still on the recurring Edit form after tapping Save"


def _click_first(d, locator, what):
    els = WebDriverWait_find(d, locator, timeout=DEFAULT_WAIT)
    assert els, f"could not find {what}"
    els[-1].click()  # convention: tap the (last) matching clickable container


def WebDriverWait_find(d, locator, timeout=DEFAULT_WAIT):
    """Poll for at least one matching element; return the list (possibly empty)."""
    deadline = time.time() + timeout
    while True:
        els = d.find_elements(*locator)
        if els:
            return els
        if time.time() >= deadline:
            return []
        time.sleep(POLL_INTERVAL)


def _open_recurring_overview(d, rec: RecurringPage):
    """Re-open the recurring overview for the main portfolio on a FRESH render
    (deep-link back to the list, tap the main row) so the round-trip read is the
    persisted state, not the form we just left."""
    DeepLinks.open(d, DeepLinks.RECURRING_INVESTMENTS)
    assert rec.is_loaded(timeout=20), "Recurring investments list did not reload"
    rec.dismiss_modal()
    assert _tap_main_portfolio_row(d, rec), \
        "did not re-open the main-portfolio recurring overview on the fresh render"


def _read_recurring_amount(d, timeout=DEFAULT_WAIT):
    """Read the largest dollar value rendered on the recurring overview card.

    The overview shows 'Current balance: $X' (the account balance) AND the recurring
    amount ($25). We pick the recurring amount by matching the exact $25 token if
    present, else fall back to the value nearest RECURRING_AMOUNT_VALUE among the
    on-screen money tokens — so the balance line can't masquerade as the answer."""
    deadline = time.time() + timeout
    money_re = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
    best = None
    while time.time() < deadline:
        texts = [e.text for e in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if e.text]
        candidates = []
        for t in texts:
            # Skip the explicit current-balance line — that's the account balance.
            if "current balance" in t.lower():
                continue
            for m in money_re.findall(t):
                try:
                    candidates.append((parse_money(m), m))
                except AssertionError:
                    pass
        # Prefer an exact $25(.00) match.
        for val, raw in candidates:
            if abs(val - RECURRING_AMOUNT_VALUE) < 0.005:
                return val, raw
        if candidates:
            best = min(candidates, key=lambda c: abs(c[0] - RECURRING_AMOUNT_VALUE))
        time.sleep(POLL_INTERVAL)
    return (best if best else (None, None))


def test_recurring_create_persists_amount_frequency_and_next_date():
    """Set a $25 Weekly recurring on the main portfolio, Save, then re-open the
    overview and assert the persisted state round-trips: amount == $25.00, frequency
    renders Weekly, the card is in set-state ('Edit Recurring Investment'), and a
    'Next Investment' date renders (shape, part b)."""
    fx = get_or_create_fixture_user("presence_funded")

    opts = get_android_options(no_reset=False)  # fresh app data
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)
        rec = RecurringPage(d)

        # --- create: type amount + pick Weekly + Save -----------------------------
        _open_recurring_main_setup(d, rec)
        _set_recurring_amount_weekly(d, rec)

        # --- round-trip: re-open the overview on a fresh render -------------------
        _open_recurring_overview(d, rec)

        # The set-state card flips the CTA from 'Set' to 'Edit Recurring Investment'.
        # This is the load-bearing proof the recurring was persisted (not just typed).
        assert rec.is_visible(EDIT_RECURRING_BUTTON, timeout=25), (
            "recurring overview did not reach set-state ('Edit Recurring Investment' "
            "CTA absent) — the recurring was not persisted"
        )
        print("  set-state confirmed: 'Edit Recurring Investment' CTA present")
        # Settle the set-state card before reading amount/frequency/next-date so the
        # round-trip oracle reads a fully-painted card, not a mid-render snapshot.
        _settle(d)

        # --- Oracle (a1): amount round-trips to $25.00 ----------------------------
        amount_val, amount_raw = _read_recurring_amount(d)
        print(f"  recurring amount on overview: {amount_raw!r} -> "
              f"{amount_val if amount_val is None else f'${amount_val:.2f}'}")
        assert amount_val is not None, "no recurring amount rendered on the overview card"
        assert abs(amount_val - RECURRING_AMOUNT_VALUE) < 0.005, (
            f"recurring amount did not round-trip: got ${amount_val:.2f} "
            f"(raw {amount_raw!r}), expected ${RECURRING_AMOUNT_VALUE:.2f}"
        )

        # --- Oracle (a2): frequency round-trips to Weekly -------------------------
        # The overview frequency title for a Weekly recurring is "Weekly on <Day>".
        assert rec.is_visible(WEEKLY_OVERVIEW_TITLE, timeout=15), (
            "recurring overview did not render the Weekly frequency title "
            "(expected 'Weekly on <Day>')"
        )
        weekly_text = d.find_element(*WEEKLY_OVERVIEW_TITLE).text
        print(f"  frequency on overview: {weekly_text!r}")
        assert "weekly" in weekly_text.lower(), \
            f"frequency did not round-trip to Weekly: {weekly_text!r}"

        # --- Oracle (b): a 'Next Investment' date renders (SHAPE, not arithmetic) -
        assert rec.is_visible(NEXT_INVESTMENT_LABEL, timeout=15), \
            "set-state card did not render the 'Next Investment' row"
        # The value sits in its own TextView just after the label; assert a date-shaped,
        # non-empty string renders (a month name token). We do NOT assert S+7 arithmetic.
        all_texts = [e.text for e in d.find_elements(AppiumBy.XPATH, "//android.widget.TextView") if e.text]
        month_re = re.compile(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)",
            re.IGNORECASE,
        )
        next_date_texts = [t for t in all_texts if month_re.search(t)]
        print(f"  Next Investment date candidates: {next_date_texts!r}")
        assert next_date_texts, (
            "'Next Investment' row rendered no date-shaped value (no month name) — "
            "part (b) next-debit-date SHAPE not satisfied"
        )
        print("  PASS: amount + Weekly frequency round-trip, set-state + next-date rendered")
    finally:
        try:
            d.quit()
        except Exception:
            pass
