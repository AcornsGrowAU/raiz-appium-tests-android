"""
recurring-into-jar-no-goal (P2, conf 58, cons 1) — STATE invariant, API-layer +
app-source first (no device).

BACKLOG SPLIT (this file builds part A only; part B is deferred per the backlog
notes):
  (A, KEEP P2)  Jars have NO Savings-Goal control on the recurring screen, whereas
                the Main (Regular) account DOES. The backlog calls this the "cheap
                inversion of is_savings_goal_offered".
  (B, DEFER)    set+read-back a recurring INTO a jar and assert cadence/label (NOT
                exact date). Not built here.

ORACLE — grounded in the REAL app source, build 3252
(Android-AU/features/recurringv2):

  The Savings-Goal control's visibility on the recurring Overview screen is a
  CLIENT-SIDE derived property, `RecurringFeatureTypeV2.goalEnabled`
  (RecurringFeatureTypeV2.kt:29-34):

      val goalEnabled: Boolean
          get() = when (this) {
              is Regular   -> true      // Main account -> goal control offered
              is Dependent -> true      // Kids         -> goal control offered
              is Jar       -> false     // Jar          -> NO goal control
          }

  and the Overview view-model consumes it DIRECTLY as the gate
  (RecurringOverviewViewModel.kt:56):

      val goalVisible = screenArgs.featureType.goalEnabled

  So "a recurring into a jar shows no Savings-Goal control, but the Main account
  does" is EXACTLY the truth table above. There is NO backend / DEV-API field that
  exposes this (the backend `saving_goal_active` in analytic_payload.rb is an
  analytics flag for whether a USER has a goal, not the per-account control-offered
  gate). The Savings-Goal *control offered on the recurring screen* lives only in
  the client. Therefore the deterministic, honest oracle for part A is the SOURCE
  invariant itself — parsed from the real app — NOT a network read.

WHY THIS LAYER (no device): the case asks us to assert STATE/invariant, not drive
a flow (the backlog refinement: part B — the on-device set+read-back — is
deferred). The control-visibility rule is a pure compile-time property of the app;
the most direct, flake-free, deterministic oracle is to assert that property
against the real source. We additionally ANCHOR the invariant to a genuinely
seeded jar account over the DEV API (the `jars_siblings_distinct` fixture owns real
jar sub-accounts) so the test is provably about a real jar context — not a vacuous
assertion. The anchor is best-effort/skip-with-reason; the source invariant is the
load-bearing oracle and stands on its own.

DATA: reuse the pre-provisioned `jars_siblings_distinct` fixture (manifest: "jars
have NO Savings-Goal control"). user_1 is the parent (stored login) owning two real
jar sub-accounts (QA Sib Jar Alpha / Bravo). READ-ONLY — never mutated, so reuse is
safe.

needs_device: FALSE. Pure app-source parse + DEV-API read; no emulator/Appium.

Run:
  venv/bin/python -m pytest tests/test_recurring_into_jar_no_goal.py \
    -m value_api -v -s -o addopts=""
"""
import os
import re

import pytest

from utils.genuser_api import SEEDED_PWD, mint, call, can_login
from utils.genuser_fixtures import get_or_create_fixture_user, JAR_A_NAME, JAR_B_NAME

pytestmark = [pytest.mark.value_api, pytest.mark.unit, pytest.mark.investments]

FIXTURE_KEY = "jars_siblings_distinct"

# Real app source (build 3252). Both paths are load-bearing for the oracle.
_APP_SRC = os.getenv("RAIZ_APP_SRC", "/Users/joshua/Android-AU")
_FEATURE_TYPE = os.path.join(
    _APP_SRC,
    "features/recurringv2/src/main/java/com/raiz/feature/recurringv2/"
    "RecurringFeatureTypeV2.kt",
)
_OVERVIEW_VM = os.path.join(
    _APP_SRC,
    "features/recurringv2/src/main/java/com/raiz/feature/recurringv2/overview/"
    "RecurringOverviewViewModel.kt",
)


# --------------------------------------------------------------------------- #
# Source-parse helper
# --------------------------------------------------------------------------- #
def _read_goal_enabled_truth_table(src: str):
    """Parse the `goalEnabled` getter body and return {branch_label: bool} for each
    `is <Type> -> <true|false>` arm. Tolerant of whitespace/formatting. branch_label
    is the receiver type ('Regular' / 'Dependent' / 'Jar')."""
    # Isolate the goalEnabled getter block.
    m = re.search(r"val\s+goalEnabled\s*:\s*Boolean\s*get\(\)\s*=\s*when\s*\(this\)\s*\{(.*?)\}",
                  src, re.DOTALL)
    assert m, "could not locate the `goalEnabled` when(this) block in RecurringFeatureTypeV2.kt"
    body = m.group(1)
    table = {}
    for arm in re.finditer(r"is\s+([A-Za-z0-9_.]+)\s*->\s*(true|false)\b", body):
        # Receiver may be 'Regular' or a nested 'Regular.Main'; key on the top-level type.
        top = arm.group(1).split(".")[0]
        table[top] = (arm.group(2) == "true")
    return table


# --------------------------------------------------------------------------- #
# DEV-API anchor: confirm the fixture owns REAL jar sub-accounts.
# --------------------------------------------------------------------------- #
def _read_parent_jar_names(parent_email, pwd):
    """Log in AS THE PARENT and return the list of jar names from GET /jars/v1/users
    (the jars list endpoint), or None if it can't be read (so the caller can
    skip-with-reason rather than fake a pass)."""
    op, tok = mint(parent_email, pwd)
    if not tok:
        return None
    status, body = call(op, "GET", "/jars/v1/users", token=tok)
    if status != 200:
        print(f"  [api] GET /jars/v1/users -> HTTP {status}: {body}")
        return None
    # Real DEV response shape (app/views/api/jars/list.rabl -> jars/show): the list is
    # wrapped under the `jar_users` key, and each jar's display name is the top-level
    # `name` field (node(:name) { |u| u.jar.name }). Read `jar_users` first; keep the
    # other keys only as defensive fallbacks for older/aliased shapes.
    jars = body if isinstance(body, list) else (
        body.get("jar_users") or body.get("jars") or body.get("users") or []
    )
    if not isinstance(jars, list):
        return None
    return [(j.get("name") or "").strip() for j in jars if isinstance(j, dict)]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_jar_recurring_has_no_savings_goal_control_source_invariant():
    """LOAD-BEARING ORACLE (deterministic, no device, no network): the recurring
    Savings-Goal control is offered for the Main (Regular) account and Kids
    (Dependent) but NOT for a Jar. This is exactly RecurringFeatureTypeV2.goalEnabled
    (Jar -> false; Regular/Dependent -> true), the inversion the backlog targets."""
    assert os.path.isfile(_FEATURE_TYPE), (
        f"app source not found at {_FEATURE_TYPE} — set RAIZ_APP_SRC to the Android-AU "
        f"checkout (build 3252) so the source invariant can be asserted"
    )
    with open(_FEATURE_TYPE, encoding="utf-8") as f:
        src = f.read()

    table = _read_goal_enabled_truth_table(src)
    print(f"  goalEnabled truth table parsed from source: {table}")

    # Core oracle: a Jar recurring does NOT offer the Savings-Goal control.
    assert "Jar" in table, (
        "goalEnabled has no `is Jar ->` arm — the jar branch the case asserts is "
        "missing/renamed; re-ground against the current source"
    )
    assert table["Jar"] is False, (
        f"goalEnabled for a Jar is {table['Jar']} — the case asserts a jar recurring "
        f"offers NO Savings-Goal control (expected false)"
    )

    # Inversion half: the Main (Regular) account DOES offer it (so this is a real
    # per-account distinction, not 'goal never shown anywhere').
    assert table.get("Regular") is True, (
        f"goalEnabled for Regular (Main) is {table.get('Regular')} — the inversion "
        f"requires Main to OFFER the goal control (expected true); without it the "
        f"jar-has-no-goal assertion is vacuous"
    )
    # Kids also offer it — documents the full truth table; load-bearing distinction
    # is Jar(false) vs Regular(true).
    assert table.get("Dependent") is True, (
        f"goalEnabled for Dependent (Kids) is {table.get('Dependent')} — expected true"
    )


def test_overview_viewmodel_gates_goal_control_on_goal_enabled():
    """The source flag is the ACTUAL control-visibility gate: the recurring Overview
    view-model derives `goalVisible` directly from `featureType.goalEnabled`. Without
    this wiring the truth table above would not govern what the screen renders, so
    asserting it keeps the oracle honest (the flag is not dead code)."""
    assert os.path.isfile(_OVERVIEW_VM), (
        f"app source not found at {_OVERVIEW_VM} — set RAIZ_APP_SRC to the Android-AU "
        f"checkout (build 3252)"
    )
    with open(_OVERVIEW_VM, encoding="utf-8") as f:
        vm = f.read()
    assert re.search(r"\bgoalVisible\b\s*=\s*[^\n]*\.goalEnabled\b", vm), (
        "RecurringOverviewViewModel no longer wires `goalVisible = ...goalEnabled` — "
        "the Savings-Goal control may be gated by a different flag now; re-ground the "
        "oracle against the current source"
    )


def test_fixture_owns_real_jar_accounts_anchor():
    """ANCHOR (best-effort, DEV API): the `jars_siblings_distinct` fixture parent owns
    REAL jar sub-accounts, so the source invariant above is about a genuine jar
    context (not a vacuous abstract assertion). Skip-with-reason — never fake a pass —
    if the fixture isn't reachable; the source invariant is the load-bearing oracle
    and does not depend on this read."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email, pwd = parent["email"], parent.get("password", SEEDED_PWD)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')})")

    if not can_login(parent_email, pwd):
        pytest.skip(
            f"fixture parent {parent_email} could not log in to DEV — jar-context "
            f"anchor unverifiable this run; source invariant "
            f"(test_jar_recurring_has_no_savings_goal_control_source_invariant) still "
            f"holds independently"
        )

    names = _read_parent_jar_names(parent_email, pwd)
    if names is None:
        pytest.skip(
            "could not read GET /jars/v1/users for the fixture parent — jar-context "
            "anchor unverifiable this run (source invariant stands on its own)"
        )

    print(f"  [api] parent jar names: {names!r}")
    # The fixture seeds two named jars; confirm at least one real jar exists so the
    # invariant is anchored to a genuine jar account.
    assert names, (
        f"fixture parent {parent_email} owns NO jars — the jars_siblings_distinct "
        f"fixture should own two; re-provision before trusting the jar-context anchor"
    )
    assert (JAR_A_NAME in names) or (JAR_B_NAME in names), (
        f"neither seeded jar ({JAR_A_NAME!r}/{JAR_B_NAME!r}) found among the parent's "
        f"jars {names!r} — fixture drift; the seeded jar context is not present"
    )
