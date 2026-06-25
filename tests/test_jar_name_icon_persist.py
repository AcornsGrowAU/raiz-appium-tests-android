"""
jar-name-icon-persist (P1, conf 74, cons 5) — state-transition, SPLIT scope, dynamic.

When a user creates a jar through the on-device wizard, the NAME they typed must
persist and render on the Jars LIST card afterwards (and the ICON they picked must
stick too). This is a real create -> read-back round-trip, not a presence probe:
the oracle is that the jar card's name TextView reads back the EXACT name we typed.

SPLIT (per the backlog refinement, verdict 'refine'):
  - MUST-HAVE  : NAME render. Create a jar named exactly NAME, drive the wizard to
                 commit, return to the Jars list, and assert the list card surfaces
                 that exact name (JarsPage.get_jar_by_name(NAME) binds a TextView
                 whose text == NAME). Grounded in the app source: each jar list row
                 renders `Text(text = item.name)` —
                 raizFeatureJars/.../list/JarListItemUi.kt:117 — so the typed name is
                 the row's own label and a name-scoped read-back is a true VALUE oracle.
  - BEST-EFFORT: ICON. The backlog gates the icon read-back on a VERIFIED
                 content-desc / locator. There is NONE: the selectable icon tiles
                 (JarIconItem in raizFeatureJars/.../customization/EmojiItem.kt) render
                 their image with `contentDescription = null` and carry no testTag, and
                 the `selected` state is only a border-COLOR change (not surfaced to the
                 accessibility tree). So per-icon identity / selected-state is NOT
                 readable via Appium on build 3252. The icon half therefore asserts the
                 refinement's fallback — "tile tapped + Create still reachable/enabled"
                 (the create flow accepted the icon selection and did not block) — rather
                 than a fake per-icon read-back. The deferred true icon-identity read-back
                 is shipped as an explicit skip-with-evidence below.

DATA STRATEGY (dynamic / fresh-per-run): creating a jar mutates account state
irreversibly and there is no proven DEV recipe to delete a committed jar, so this
test does NOT reuse a shared fixture — it generates a brand-new funded user each
run (per the provision manifest: jar-name-icon-persist = "fresh-per-run recipe"),
logs in AS it, onboards, and creates one jar. A fresh user owns 0 jars, so the
created jar is unambiguously the one under test. The orphan jar is left on the
throwaway user (documented, not cleaned — see ORPHAN note below); it is harmless
because the user is single-use.

DESTRUCTIVE + on-device: gated behind RUN_DESTRUCTIVE=1, needs an emulator + Appium.
DEV backend only — never prod.
  RUN_DESTRUCTIVE=1 ANDROID_UDID=emulator-5554 APPIUM_HOST=http://127.0.0.1:4723 \
    venv/bin/python -m pytest tests/test_jar_name_icon_persist.py -v -s -o addopts=""
"""
import os
import time

import pytest
from appium import webdriver as appium_webdriver
from selenium.common.exceptions import WebDriverException

from config.capabilities import get_android_options
from config.settings import APPIUM_HOST
from pages.splash_page import SplashPage
from pages.login_page import LoginPage
from pages.onboarding_page import OnboardingPage
from pages.home_page import HomePage
from pages.jars_page import JarsPage
from utils.deep_links import DeepLinks
from utils.genuser_api import gen_create, funded_user, SEEDED_PWD
from conftest import _open_deep_link

pytestmark = [pytest.mark.genuser_e2e, pytest.mark.jars, pytest.mark.destructive]

UDID = os.getenv("ANDROID_UDID", "emulator-5554")
_RUN_DESTRUCTIVE = os.getenv("RUN_DESTRUCTIVE") == "1"

# The name we type into the create wizard. A distinctive, exact string so the
# read-back assertion is unambiguous; matches the backlog's illustrative value.
JAR_NAME = "Europe trip"


def _fresh_user():
    """Seed a brand-new funded user for THIS run only (jar-create mutates state and
    cannot be undone, so never reuse a shared fixture). Returns {email, password}."""
    email = f"jarnameicon.{int(time.time())}@emel.xyz"
    status, body = gen_create({"user_1": funded_user(email, "JarNameIcon")})
    assert status == 200, f"failed to seed fresh jar-name-icon user: HTTP {status} {body}"
    return {"email": email, "password": SEEDED_PWD}


def _src(d) -> str:
    """Lower-cased page source, swallowing the transient WebDriverException that
    page_source can throw mid-transition (so a screen change never aborts the poll)."""
    try:
        return d.page_source.lower()
    except WebDriverException:
        return ""


def _tap_text(d, *labels) -> str | None:
    """Tap the first on-screen element matching any of the given visible labels
    (exact OR contains), returning the label that took. Mirrors the shared
    OnboardingPage helper but lives here so this test's precondition is not coupled
    to a single shared page object that does not yet handle the build-3252 layout."""
    from appium.webdriver.common.appiumby import AppiumBy
    for lab in labels:
        for e in d.find_elements(
                AppiumBy.XPATH, f"//*[@text='{lab}'] | //*[contains(@text,'{lab}')]"):
            try:
                e.click()
                return lab
            except Exception:
                pass
    return None


def _complete_onboarding(d, ho, deadline_s=140) -> bool:
    """Drive a freshly-logged-in generated user through the build-3252 onboarding
    gauntlet to Home — a POLLING re-implementation of OnboardingPage.complete().

    Why this exists (the verdict's root cause): the shared OnboardingPage.complete()
    takes ONE non-polling page_source snapshot per step and, if that single snapshot
    matches none of its branches, immediately appends 'STUCK' and returns False. On
    build 3252 the signup STEPS screen (SignUpStepsScreen.kt) only renders a 'Skip'
    button for the ROUND_UP/FUNDING steps (SignUpStepItem.skipButtonVisible); the
    remaining step's only forward control is the action button, whose label is
    'Continue' (else-branch in SignUpStepItem.actionButton). Tapping 'Continue'
    NAVIGATES into the portfolio sub-flow (SignUpStepsViewModel.onActionButtonClick
    -> navigate), which renders a 'Scroll Tabs' coachmark then 'Select as your
    portfolio' (portfolio_btn_select). Mid-transition the shared helper's lone
    snapshot caught none of those strings and dead-ended at ['Skip','Continue',
    'STUCK'] — an infra-shaped precondition failure, NOT this test's own assertion.

    This driver instead RE-READS the screen on a real deadline (so a screen that is
    still settling is retried, never instantly declared STUCK), and walks the same
    real controls the app exposes:
      - round-up / funding checklist  -> 'Skip'
      - 'Scroll Tabs' / 'Got it' coachmark -> 'Got it'
      - portfolio selection           -> 'Select as your portfolio'
      - initial-investment / steps action button -> 'Skip' then 'Continue'
    Returns True once Home (TOTAL_VALUE_LABEL) renders. Does NOT change what the
    test validates — only makes reaching the subject-under-test reliable."""
    path = []
    deadline = time.time() + deadline_s
    last_src = None
    stuck_polls = 0
    while time.time() < deadline:
        if ho.is_present_now(ho.TOTAL_VALUE_LABEL):
            return True
        src = _src(d)
        acted = None
        # Coachmark first — it overlays the portfolio screen and must be cleared
        # before the 'Select as your portfolio' button is hittable.
        if "got it" in src or "scroll tabs" in src:
            acted = _tap_text(d, "Got it")
        if not acted and any(s in src for s in (
                "follow these steps", "link a round-up", "link a funding",
                "complete your raiz invest", "link round-up account",
                "link funding account")):
            acted = _tap_text(d, "Skip")
        # Portfolio INTRO screen (build 3252): after the steps screen's 'Continue'
        # the app lands on a 'Select your Portfolio' marketing intro whose ONLY
        # forward control is a 'Select your Portfolio' button — it navigates INTO
        # the portfolio picker list. This is the step the original driver missed
        # (it only handled the picker-list 'Select as your portfolio'), so it
        # dead-ended here and the jar subject-under-test was never reached. Fire it
        # only when the picker-list confirm is NOT yet present, so we don't re-tap
        # on the list screen.
        if (not acted and "select your portfolio" in src
                and "select as your portfolio" not in src):
            acted = _tap_text(d, "Select your Portfolio")
        if not acted and "select as your portfolio" in src:
            _tap_text(d, "Aggressive")
            time.sleep(1)
            acted = _tap_text(d, "Select as your portfolio")
        if not acted and ("initial investment" in src or "ready to start investing" in src):
            acted = _tap_text(d, "Skip")
        if not acted:
            # Generic forward. 'Skip' before 'Continue' (a step that can be skipped
            # should be, to avoid entering a sub-flow); 'Continue'/'Add Personal
            # Details' advance the steps screen when no Skip exists. NO bare 'Invest'
            # (it collides with the 'Raiz Invest' heading).
            acted = _tap_text(d, "Skip", "Continue", "Add Personal Details",
                              "Confirm", "Done", "Next", "I consent", "Agree")
        if acted:
            path.append(acted)
            stuck_polls = 0
            time.sleep(3.5)
            continue
        # Nothing matched this snapshot. Unlike the shared helper, DON'T dead-end:
        # the screen may be mid-transition. Re-poll. Only give up if the screen has
        # been identical and unactionable across several polls (a true dead-end).
        if src and src == last_src:
            stuck_polls += 1
        else:
            stuck_polls = 0
        last_src = src
        if stuck_polls >= 6:
            path.append("STUCK")
            print(f"  onboarding dead-ended (stable unactionable screen): {path}")
            return ho.is_present_now(ho.TOTAL_VALUE_LABEL)
        time.sleep(2)
    print(f"  onboarding timed out after {deadline_s}s: {path}")
    return ho.is_present_now(ho.TOTAL_VALUE_LABEL)


def _login_and_home(d, fx):
    sp, lo, ho = SplashPage(d), LoginPage(d), HomePage(d)
    if sp.is_present_now(sp.TAGLINE):
        sp.tap_log_in()
        time.sleep(2)
    lo.login(fx["email"], fx["password"])
    time.sleep(7)
    if not ho.is_present_now(ho.TOTAL_VALUE_LABEL):
        # Try the shared helper first (unchanged behaviour where it works), then
        # fall through to the polling build-3252 driver if it dead-ends — the shared
        # OnboardingPage.complete() stops at the steps-screen 'Continue' on 3252.
        onb = OnboardingPage(d)
        if not onb.complete():
            assert _complete_onboarding(d, ho), (
                f"onboarding stuck (shared helper path={onb.path}); polling driver "
                f"also could not reach Home"
            )
    assert ho.is_present_now(ho.TOTAL_VALUE_LABEL), "not on Home after login"
    return ho


def _open_jars(driver, attempts=3) -> JarsPage:
    """Reach the Jars create screen via the Home Jars CARD tap.

    The `raiz://jars` deep link does NOT resolve for a freshly generated user that
    owns 0 jars (verified on device for the sibling jar-create test): firing it
    leaves the app on Home with the Jars card still in its empty 'Add' state.
    Tapping the Home Jars card (HomePage.tap_jars) DOES navigate, landing on the
    'Customise your Jar!' create screen — the screen this test needs. Retry to ride
    out a tap that registers before the card scroll settles."""
    home = HomePage(driver)
    jars = JarsPage(driver)
    for _ in range(attempts):
        try:
            home.tap_jars()
            if jars.is_loaded():
                return jars
            _open_deep_link(driver, DeepLinks.HOME)
            home.dismiss_modal()
        except WebDriverException:
            try:
                _open_deep_link(driver, DeepLinks.HOME)
                home.dismiss_modal()
            except WebDriverException:
                pass
            continue
    assert jars.is_loaded(), "Could not open the Jars screen via the Home Jars card"
    return jars


@pytest.mark.skipif(
    not _RUN_DESTRUCTIVE,
    reason="Creates a real DEV jar (left on a throwaway user); opt-in via RUN_DESTRUCTIVE=1",
)
def test_created_jar_name_persists_on_list_card():
    """MUST-HAVE half: a jar created with NAME renders that EXACT name back on the
    Jars list card.

    Fresh generated user (0 jars baseline), own driver. The oracle is a real
    name-scoped read-back (get_jar_by_name(NAME) binds a TextView whose text ==
    NAME), not mere presence of 'a jar' — the suite's known weakness. ICON is
    handled best-effort inline (tile tapped + Create reachable) because no verified
    icon read-back locator exists on build 3252 (icon tiles carry
    contentDescription = null); the true icon-identity read-back is the explicit
    skip below."""
    fx = _fresh_user()
    opts = get_android_options(no_reset=False)
    opts.udid = UDID
    d = appium_webdriver.Remote(command_executor=APPIUM_HOST, options=opts)
    try:
        _login_and_home(d, fx)

        # --- ACT: open the create screen and build exactly ONE jar named JAR_NAME. ---
        jars = _open_jars(d)
        assert jars.is_create_screen(), (
            "Expected the 'Customise your Jar' create screen to add a new jar"
        )

        # ICON (best-effort, per the SPLIT refinement): tap the first icon tile and
        # assert the create flow still progresses — i.e. the icon selection was
        # accepted and the Create Jar control remains reachable/enabled afterwards.
        # We do NOT assert WHICH icon is selected: the tiles expose no
        # contentDescription/testTag and the selected state is only a border colour,
        # so a per-icon read-back is not observable via Appium on this build.
        jars.select_first_icon()
        icon_step_ok = jars.is_present_now(jars.CREATE_JAR_BUTTON)
        print(f"  icon best-effort: tile tapped, Create-Jar still reachable = {icon_step_ok}")
        assert icon_step_ok, (
            "After tapping an icon tile the 'Create Jar' control was no longer "
            "reachable — the icon selection appears to have blocked the create flow"
        )

        # NAME: type the exact name and commit the jar through the post-Create wizard
        # (Set goal -> Skip -> portfolio confirm), blocking until it actually commits.
        jars.enter_jar_name(JAR_NAME)
        jars.tap_create_jar()
        oops = jars.wait_for_create_committed()
        assert not oops, "Creating the jar raised an 'Oops!' error"

        # --- ASSERT (must-have): the committed jar's NAME persists on the list card. ---
        # wait_for_create_committed lands on the Jars LIST screen on success. Bring
        # the new jar's row on-screen, then read back its name TextView by exact text.
        assert jars.is_list_screen(), (
            "Expected the Jars LIST screen after committing the jar so the new "
            "jar's card can be read back"
        )
        on_screen = jars.scroll_jar_into_view(JAR_NAME)
        assert on_screen, (
            f"Created jar '{JAR_NAME}' did not appear on the Jars list after "
            f"creation — its name failed to persist/render"
        )

        # Exact-text read-back: bind the card's name TextView and assert its text is
        # EXACTLY the name we typed (catches truncation / wrong-jar / blank-name bugs).
        name_el = jars.get_jar_by_name(JAR_NAME)
        assert name_el is not None, (
            f"could not bind the jar list card for '{JAR_NAME}'"
        )
        rendered = (name_el.text or "").strip()
        print(f"  list card name read back == {rendered!r} (typed {JAR_NAME!r})")
        assert rendered == JAR_NAME, (
            f"created jar name did not persist EXACTLY on the list card: typed "
            f"{JAR_NAME!r}, list card rendered {rendered!r}"
        )

        # ORPHAN: the jar is left on this single-use throwaway user. There is no
        # proven DEV recipe to delete a committed jar (the internal per-jar endpoint
        # 500s for jar user_types — see provision manifest), so cleanup is the user
        # being throwaway, not an API delete. Documented honestly, not silently.
        print(f"  ORPHAN: jar '{JAR_NAME}' left on throwaway user {fx['email']} "
              f"(no DEV jar-delete recipe; user is single-use)")
    finally:
        try:
            d.quit()
        except Exception:
            pass


@pytest.mark.skip(reason=(
    "SPLIT per backlog (jar-name-icon-persist): the true ICON-IDENTITY read-back "
    "(assert the SPECIFIC icon the user picked persists on the jar card) is "
    "deferred — it has no verified locator on build 3252. The selectable icon "
    "tiles (JarIconItem, raizFeatureJars/.../customization/EmojiItem.kt) render "
    "their image with contentDescription = null and carry no testTag, and the "
    "'selected' state is only a border-COLOUR change that is not surfaced to the "
    "accessibility tree — so neither the chosen icon nor its selected state is "
    "readable via Appium. The list-card jar avatar (JarAvatarUi.kt) is likewise "
    "contentDescription = null. The backlog gates the icon assertion on a verified "
    "content-desc/locator; until the app tags the icon tiles + the card avatar, "
    "the icon half ships as best-effort (tile tapped + Create reachable, asserted "
    "in the must-have test) and this exact read-back stays an evidenced skip — "
    "never a fake pass."
))
def test_created_jar_icon_identity_persists_on_list_card():
    """Deferred: assert the EXACT icon picked in the wizard persists on the jar
    list card. Needs the app to expose a stable content-desc/testTag on the icon
    tiles AND the card avatar (both contentDescription = null on build 3252)."""
    pass
