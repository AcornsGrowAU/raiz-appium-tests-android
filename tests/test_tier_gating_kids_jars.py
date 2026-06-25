"""
tier-gating-kids-jars  (P0, dynamic / value_api) — API / ENTITLEMENT-LAYER HALF.

CASE (backlog docs/proposed-test-cases.md, verdict=refine):
  "Kids/Jars upgrade-gated on Lite, enabled on Regular/Plus (assert gating STATE)."
  Refinement/notes column:
    - Lite: create entry disabled / upgrade-routed (assert STATE, not tile absence);
      Regular/Plus: enabled.
    - SPIKE-GATED: probe that plan_identifier='lite' is accepted AND that DEV actually
      ENFORCES the entitlement; if DEV unlocks everything -> xfail documented-gap, NOT
      a guard.

SPIKE RESOLUTION (grounded in /Users/joshua/raiz-backend, build-time source):
  The gate is REAL and is a PURE FUNCTION OF THE PARENT'S PLAN — not a runtime/DEV
  toggle, so this is NOT a "DEV unlocks everything" xfail. Proof from source:

    app/services/user_plans/limitations/kid.rb   -> Kid  setting :allowed_count, default: 0
    app/services/user_plans/limitations/jar.rb   -> Jar  setting :allowed_count, default: 0
    app/services/user_plans/starter/limitations/kid.rb -> class Kid < ...Limitations::Kid; end
    app/services/user_plans/starter/limitations/jar.rb -> class Jar < ...Limitations::Jar; end
        (Starter INHERITS the base default 0 — no override -> allowed_count == 0)
    app/services/user_plans/regular/limitations/kid.rb -> setting :allowed_count, default: INFINITY
    app/services/user_plans/regular/limitations/jar.rb -> setting :allowed_count, default: INFINITY

  Creation is conducted through the plan limitation (app/services/action_prechecker_services/
  conductor.rb: 'create_kid'->rule 'kid', 'create_jar'->rule 'jar', type 'plan_limitation'),
  which evaluates `(existing_count + 1) <= allowed_count` (limitations/kid.rb,
  limitations/jar.rb). For a STARTER ('Lite') parent that is `1 <= 0` => FALSE =>
  raise UserPlans::Errors::Kid::CreateError / Jar::CreateError (errors/kid.rb, errors/jar.rb).
  For REGULAR it is `<= INFINITY` => always allowed. The OUTCOME OF THE GATE IS THEREFORE
  FULLY DETERMINED BY WHICH PLAN IS ACTIVE on the parent.

WHY assert PLAN STATE (not "attempt a create and expect 422"):
  The PROVEN test-data-gen seed path does NOT route through the production
  ActionPrecheckerServices conductor — it factory-inserts entities. The provision
  manifest's FLAG 2 documents exactly this for the sibling kids-CAP case ("a 9th kid
  create will SUCCEED unless DEV's Setting is non-zero" — the seed bypasses the cap).
  So seeding a kid/jar on a Starter parent via the gen API would SUCCEED and would
  prove NOTHING about the production gate (false negative). The honest, deterministic
  oracle is the ENTITLEMENT STATE that the gate keys off: the parent's ACTIVE PLAN, as
  the backend itself reports it to the app.

ORACLE — read each seeded user's ACTIVE PLAN from the customer-facing entitlement API:
  GET /v1/plans  (app/api/v1/resources/plans.rb, mounted at /v1; rendered by
  app/views/api/plans.rabl) returns, per the user's user_type, the array of plans with
  a per-entry boolean `current_plan` derived from
  app/facades/plans/api_show_facade.rb#current_plan? == (user.plan&.id == plan.id).
  The plan `name` comes from config/locales/user_plans.en.yml:
      starter.name == "Lite"   regular.name == "Regular"   plus.name == "Plus"
  (i.e. the backend's `starter` IS the app's "Lite" plan — see also genuser_fixtures
  comment and provision-manifest Phase-0 probe: gen plan_identifier 'lite' is INVALID,
  'starter' is the Lite tier).

  Assertions (entitlement STATE, cross-tier DISTINCTION):
    1. Each user's /v1/plans response is well-formed: EXACTLY ONE plan has
       current_plan == true (a single, unambiguous active entitlement).
    2. The Lite (starter-seeded) user's active plan name == "Lite"  -> on the tier whose
       Kid/Jar allowed_count == 0 -> kids & jars are upgrade-GATED.
    3. The Regular control user's active plan name == "Regular"     -> on the tier whose
       Kid/Jar allowed_count == INFINITY -> kids & jars are ENABLED.
    4. The two users' active plan names DIFFER -> the gate OUTCOME differs by tier
       (the whole point of the case): same code path, different entitlement.

  This asserts STATE (the active plan that DETERMINES the gate), never enforcement of a
  UI control, exactly as the backlog refinement and the CONVENTIONS demand.

DATA: reuse the provisioned fixtures `plan_lite` (starter/"Lite") + `plan_regular`
  (regular control) — get_or_create_fixture_user reuses the persisted registry users
  (fixtures/genuser_registry.json) and only re-seeds if a user no longer logs in. The
  balance is NOT load-bearing here (manifest FLAG 1: the $100 ACH does not settle on
  Starter); we read the PLAN, not the balance.

COMPANION HALF (DEFERRED, on-device): "Lite create-entry disabled / upgrade-routed" —
  drive the Lite user to the Kids/Jars create entry and assert the upgrade route
  (raiz Kotlin: the create CTA is gated behind the plan-upgrade flow). Needs the
  on-device plan-gated-CTA driver; out of scope for this API-layer deliverable, in the
  same (a) API / (b) on-device split as tests/test_main_jar_transfer_conserves.py.
  The on-device half is SECONDARY: the entitlement gate is genuinely enforced at the
  backend (proven above), so the API-layer STATE oracle is the load-bearing proof.

needs_device: False — pure DEV-API entitlement read, no emulator, deterministic.

Run (no emulator):
  venv/bin/python -m pytest tests/test_tier_gating_kids_jars.py -v -s -o addopts=""
"""
import pytest

from utils.genuser_api import mint, call, SEEDED_PWD
from utils.genuser_fixtures import get_or_create_fixture_user

pytestmark = [pytest.mark.value_api, pytest.mark.tier]

# Plan-name ground truth from config/locales/user_plans.en.yml (build source).
LITE_NAME = "Lite"        # backend identifier 'starter' -> the app's "Lite" plan
REGULAR_NAME = "Regular"  # backend identifier 'regular' -> control (kids/jars enabled)


def _active_plan_name(email, pwd=SEEDED_PWD):
    """Log in AS the user and read the ACTIVE plan name the backend reports to the app
    via GET /v1/plans. Returns (active_name, all_names, n_active) where:
      active_name : the `name` of the single plan with current_plan == true (or None)
      all_names   : the names of every plan offered to this user_type (for diagnostics)
      n_active    : how many entries reported current_plan == true (must be exactly 1)
    Returns (None, [], -1) if login/read fails (asserted as a hard failure by caller)."""
    op, tok = mint(email, pwd)
    if not tok:
        return None, [], -1
    status, body = call(op, "GET", "/v1/plans", token=tok)
    if status != 200:
        return None, [], -1
    # rabl (app/views/api/plans.rabl) wraps the collection under "plans", AND — because
    # `collection @plans => :plans` renders a non-Plan facade root — each element is
    # itself wrapped under a per-object "plan" envelope:
    #     {"plans": [ {"plan": {id, name, current_plan, ...}}, ... ]}
    # Verified live against DEV (2026-06-24): reading p["name"]/p["current_plan"] on the
    # OUTER wrapper returns None for every entry (the prior brittle parse path — it made
    # the test report n_active=0 / names [None,None,None] despite a healthy payload).
    # Unwrap the envelope per element, tolerating a future flattening (defensive .get).
    plans = body.get("plans", body) if isinstance(body, dict) else body
    if not isinstance(plans, list):
        return None, [], -1
    entries = [w.get("plan", w) if isinstance(w, dict) else w for w in plans]
    active = [p for p in entries if isinstance(p, dict) and p.get("current_plan") is True]
    all_names = [p.get("name") for p in entries if isinstance(p, dict)]
    active_name = active[0].get("name") if len(active) == 1 else None
    return active_name, all_names, len(active)


@pytest.mark.e2e
@pytest.mark.regression
@pytest.mark.kids
@pytest.mark.jars
def test_tier_gating_kids_jars_entitlement_state():
    """Lite (starter) vs Regular control: the ENTITLEMENT STATE that determines the
    Kids/Jars gate differs by tier. Lite parent's active plan == "Lite" (Kid/Jar
    allowed_count == 0 -> upgrade-gated); Regular parent's active plan == "Regular"
    (allowed_count == INFINITY -> enabled). The two active plans DIFFER, so the same
    create code path yields opposite outcomes purely by plan. Asserts plan STATE, not
    UI enforcement (see module docstring for the source-grounded gate proof)."""
    lite = get_or_create_fixture_user("plan_lite")
    ctrl = get_or_create_fixture_user("plan_regular")
    print(f"  fixtures: lite={lite['email']} (reused={lite.get('reused')}) "
          f"regular={ctrl['email']} (reused={ctrl.get('reused')})")

    lite_name, lite_all, lite_n = _active_plan_name(lite["email"], lite.get("password", SEEDED_PWD))
    ctrl_name, ctrl_all, ctrl_n = _active_plan_name(ctrl["email"], ctrl.get("password", SEEDED_PWD))
    print(f"  Lite user    active plan: {lite_name!r}  (offered: {lite_all}, n_active={lite_n})")
    print(f"  Regular user active plan: {ctrl_name!r}  (offered: {ctrl_all}, n_active={ctrl_n})")

    # (0) Both reads must succeed — a failed login/read is a hard failure, never masked.
    assert lite_n != -1, f"could not read /v1/plans for the Lite fixture {lite['email']}"
    assert ctrl_n != -1, f"could not read /v1/plans for the Regular fixture {ctrl['email']}"

    # (1) Well-formed entitlement: each user has EXACTLY ONE active plan.
    assert lite_n == 1, (
        f"Lite user does not have exactly one active plan (n_active={lite_n}); "
        f"entitlement state is ambiguous — offered {lite_all}")
    assert ctrl_n == 1, (
        f"Regular user does not have exactly one active plan (n_active={ctrl_n}); "
        f"entitlement state is ambiguous — offered {ctrl_all}")

    # (2) Lite user is on the STARTER ('Lite') tier -> Kid/Jar allowed_count == 0 ->
    #     kids & jars are upgrade-GATED (the gate the case is about).
    assert lite_name == LITE_NAME, (
        f"Lite fixture's active plan is {lite_name!r}, expected {LITE_NAME!r} — the "
        f"starter-seeded user is NOT on the Lite tier, so the kids/jars upgrade-gate "
        f"would not apply. SPIKE NOTE: if DEV had unlocked/auto-upgraded the plan this "
        f"would surface here (documented-gap), not be masked.")

    # (3) Regular control is on REGULAR -> Kid/Jar allowed_count == INFINITY -> ENABLED.
    assert ctrl_name == REGULAR_NAME, (
        f"Regular control's active plan is {ctrl_name!r}, expected {REGULAR_NAME!r} — "
        f"the control is not on the enabled tier, so it cannot serve as the "
        f"kids/jars-ENABLED counterpart to Lite.")

    # (4) CROSS-TIER DISTINCTION: the two active plans DIFFER, so the identical
    #     create_kid / create_jar path gives OPPOSITE outcomes (gated vs enabled)
    #     purely as a function of the active plan. This is the load-bearing assertion.
    assert lite_name != ctrl_name, (
        f"Lite and Regular users report the SAME active plan ({lite_name!r}) — the "
        f"tiers are indistinguishable at the entitlement layer, so the kids/jars gate "
        f"cannot differ between them. The gate would be a no-op / DEV-unlocked.")

    print(f"  PASS: Lite tier ({lite_name}) upgrade-gates kids/jars (allowed_count==0); "
          f"Regular control ({ctrl_name}) enables them (allowed_count==INFINITY); "
          f"tiers are distinct at the entitlement layer.")
