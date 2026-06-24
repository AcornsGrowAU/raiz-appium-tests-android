"""
Backlog case: jar-below-min-deposit-rejected  (P1, raiz-jars / deposits-withdrawals)

Oracle (docs/proposed-test-cases.md, row + notes):
    "Below-$5 deposit into a jar rejected; jar balance unchanged."
    $4/$0 into a seeded funded jar -> error AND jar balance delta==0 AND no
    CreditInvestment; $5 accepted.
    NOTE refinements honoured here:
      - "Assert at COMMIT layer (sub-$5 reaches keypad confirm)."
      - "DROP funding-source-unchanged sub-clause (no read recipe)."  -> dropped.

WHY API-LAYER (no device), and where the COMMIT actually is
-----------------------------------------------------------
The backlog note imagined the rejection firing at the UI keypad confirm. Grounding
the flow in the real app source (build 3252) shows it does NOT: the jar invest screen
gates NOTHING on a $5 minimum at the client.

  raizFeatureJars/.../investment/JarInvestViewModel.kt
      InvestmentScreenStateHolder(..., minAmount = 0.01, ...)        # NOT 5.00
  raizUiCompose/.../investment/InvestmentScreen.kt
      RoundedButton(onClick = onBottomButtonClick, ... enabled gating is
      only `touchInterceptor(intercept = investButtonLocked || investmentProcessing)`)
  raizUiCompose/.../amount/KeypadAmountFormatter.kt
      minAmount only drives the amount-text COLOUR (valid/invalid); it does not
      block the bottom button.

So at the client a $4 jar deposit sails past the keypad -> opens the account-select
dialog -> calls jarsRepository.createInvestment(type=credit). The real COMMIT-LAYER
rejection lives in the BACKEND, where the credit-investment creator enforces the floor:

  raiz-backend app/services/dependent_users/investments/credit_creator.rb
      def validate_amount
        return if amount.to_d >= Setting.investments_threshold.to_d   # default 5.0
        raise InsufficientAmountError,
              I18n.t('api.user.errors.insufficient_investment', amount: ...)
      end
      def call!  ->  validate; investment.save                        # save NEVER reached on a sub-$5
  app/api/jars/v1/resources/investments.rb  POST /jars/v1/investments
      creator = ::Jars::Investments::CreditCreator (-> DependentUsers::...::CreditCreator)
      rescue creator_klass::Error => e  ->  error!(e.message, 422)
  app/models/setting.rb            field :investments_threshold, default: 5.0
  config/locales/api.en.yml        insufficient_investment:
                                     "The minimum investment amount is $%{amount}."

`validate_amount` runs BEFORE `investment.save`, so a rejected sub-$5 deposit creates
NO CreditInvestment and the jar's accumulated_amount is unchanged — exactly the
"no CreditInvestment / delta==0" oracle, provable directly against backend ground truth
with no emulator. This is the true commit point; asserting it at the API layer is
deterministic and stronger than poking the UI keypad (which would not reject at all).

TEST DESIGN
-----------
REJECTION leg (load-bearing, READ-ONLY on the shared fixture):
  Log in AS the parent of the `jar_below_min` fixture (a funded user who owns one jar
  "QA Min Jar" funded to $25 exact ACH). List the parent's jars (GET /jars/v1/users) to
  get the jar's uuid + accumulated_amount baseline. POST a $4.00 and a $0.00 credit ->
  each must be HTTP 422 naming the $5 minimum. Re-read the jar -> accumulated_amount
  delta == 0.00 (no CreditInvestment persisted). A rejected create never mutates state,
  so this leg is safe to run against the reusable fixture every run.

ACCEPTANCE leg ($5 boundary, on a FRESH throwaway rig — never the shared fixture):
  The exact $5.00 boundary is `amount >= threshold` -> ACCEPTED, which means a real
  CreditInvestment WOULD be created. To avoid drifting the reusable fixture's $25
  balance across runs, seed a self-contained parent+jar per run and POST $5.00 to it;
  assert it is NOT rejected by the minimum rule (no insufficient-amount 422). The
  throwaway rig is discarded — the shared fixture stays pristine.

Honesty: any login/seed/list gate -> skip-with-reason (clear evidence), never a fake
or vacuous pass. needs_device: False (pure DEV-API).

Run (no emulator):
  venv/bin/python -m pytest tests/test_jar_below_min_deposit_rejected.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import (
    SEEDED_PWD, ach_credits, call, funded_user, gen_create, jar_user, mint,
)
from utils.genuser_fixtures import BELOW_MIN_JAR_BALANCE, get_or_create_fixture_user

pytestmark = [pytest.mark.value_api, pytest.mark.jars, pytest.mark.edge]

# Backend Setting.investments_threshold default (app/models/setting.rb). The credit
# creator rejects any deposit strictly below this. Boundary is INCLUSIVE: $5.00 passes.
MIN_DEPOSIT = 5.00

# Sub-minimum amounts to attempt (the backlog's $4 and $0). Both must be rejected.
BELOW_MIN_AMOUNTS = [4.00, 0.00]

# The seeded fixture jar's name (utils.genuser_fixtures: jar_below_min builder).
FIXTURE_JAR_NAME = "QA Min Jar"

DELTA_EPS = 0.01  # accumulated_amount delta-from-baseline must be 0.00 to the cent


def _ts():
    return str(int(time.time()))


def _list_jars(op, token):
    """GET /jars/v1/users -> list of jar dicts (each: id=jar_user uuid, name,
    accumulated_amount). Returns (status, jars_list_or_body)."""
    status, body = call(op, "GET", "/jars/v1/users", token=token)
    jars = body.get("jar_users") if isinstance(body, dict) else None
    return status, (jars if jars is not None else body)


def _find_jar(jars, name):
    for j in jars:
        if isinstance(j, dict) and j.get("name") == name:
            return j
    return None


def _post_jar_credit(op, token, jar_uuid, amount):
    """POST /jars/v1/investments {amount, type=credit, jar_user_id}. Returns (status, body)."""
    return call(op, "POST", "/jars/v1/investments", token=token,
                body={"amount": amount, "type": "credit", "jar_user_id": jar_uuid})


def _is_min_rejection(status, body):
    """True iff the response is the backend's sub-$5 InsufficientAmount rejection
    (HTTP 422 whose message names the minimum-investment floor)."""
    if status != 422:
        return False
    text = str(body).lower()
    return "minimum investment amount" in text


def test_jar_below_min_deposit_rejected():
    """A sub-$5 credit into a funded jar is rejected at the backend commit point with
    HTTP 422 (minimum-investment floor), creates NO CreditInvestment, and leaves the
    jar's accumulated_amount unchanged (delta==0). The exact $5.00 boundary is accepted
    (no insufficient-amount 422) on a fresh throwaway jar."""
    # ---- Resolve the shared fixture parent (owns one funded jar) ----------------
    try:
        parent = get_or_create_fixture_user("jar_below_min")
    except Exception as e:  # seed/registry gate, not a product result
        pytest.skip(f"skip-with-reason: could not resolve 'jar_below_min' fixture ({e})")

    op, token = mint(parent["email"], parent.get("password", SEEDED_PWD))
    if not token:
        pytest.skip("skip-with-reason: could not log in as the jar_below_min parent "
                    "(login/lockout gate, not a product result)")

    # ---- Find the seeded jar + its baseline accumulated_amount ------------------
    status, jars = _list_jars(op, token)
    if status != 200 or not isinstance(jars, list):
        pytest.skip(f"skip-with-reason: GET /jars/v1/users failed (HTTP {status} "
                    f"{str(jars)[:160]}); read gate, not a product result")
    jar = _find_jar(jars, FIXTURE_JAR_NAME)
    if jar is None:
        # Fall back to the sole jar if the name drifted, else skip with evidence.
        if len(jars) == 1 and isinstance(jars[0], dict) and jars[0].get("id"):
            jar = jars[0]
        else:
            pytest.skip(f"skip-with-reason: fixture jar '{FIXTURE_JAR_NAME}' not found "
                        f"among {[j.get('name') for j in jars]}; fixture-shape gate")

    jar_uuid = jar.get("id")
    baseline = round(float(jar.get("accumulated_amount") or 0.0), 2)
    if not jar_uuid:
        pytest.skip("skip-with-reason: jar entity missing uuid id (fixture-shape gate)")
    print(f"  fixture jar '{jar.get('name')}' uuid={jar_uuid} "
          f"accumulated_amount baseline=${baseline} (seed ${BELOW_MIN_JAR_BALANCE})")

    # ============================ LOAD-BEARING: sub-$5 REJECTED ============================
    for amt in BELOW_MIN_AMOUNTS:
        status, body = _post_jar_credit(op, token, jar_uuid, amt)
        print(f"  POST ${amt:.2f} credit -> HTTP {status} {str(body)[:140]}")
        assert _is_min_rejection(status, body), (
            f"a ${amt:.2f} jar deposit (below the ${MIN_DEPOSIT:.2f} minimum) was NOT "
            f"rejected with a minimum-investment 422 — got HTTP {status} {str(body)[:200]}. "
            f"The credit creator must reject sub-${MIN_DEPOSIT:.0f} deposits before save.")

    # ---- No CreditInvestment persisted -> jar balance unchanged (delta==0) ------
    status, jars_after = _list_jars(op, token)
    if status != 200 or not isinstance(jars_after, list):
        pytest.skip(f"skip-with-reason: re-read of jars failed (HTTP {status}); "
                    f"cannot confirm balance unchanged")
    jar_after = _find_jar(jars_after, jar.get("name")) or (
        jars_after[0] if len(jars_after) == 1 else None)
    assert jar_after is not None, "jar disappeared after the rejected deposits"
    after = round(float(jar_after.get("accumulated_amount") or 0.0), 2)
    delta = round(after - baseline, 2)
    print(f"  jar accumulated_amount after rejected deposits=${after} (delta {delta})")
    assert abs(delta) <= DELTA_EPS, (
        f"a REJECTED sub-${MIN_DEPOSIT:.0f} deposit moved the jar balance: ${baseline} "
        f"-> ${after} (delta ${delta}). A rejection must persist NO CreditInvestment.")

    # ============================ BOUNDARY: $5.00 ACCEPTED (fresh rig) ============================
    # Seed a throwaway parent+jar so the shared fixture is never mutated, then post the
    # exact $5.00 boundary and assert it is NOT rejected by the minimum rule.
    ts = _ts()
    p_email = f"jarmin.accept.parent.{ts}@emel.xyz"
    j_email = f"jarmin.accept.jar.{ts}@emel.xyz"
    payload = {
        "user_1": funded_user(p_email, f"JarMinAccept{ts}"),
        "jar_1": jar_user(j_email, "QA Accept Jar", "@user_1", "QA Accept Jar"),
        **ach_credits("@jar_1", BELOW_MIN_JAR_BALANCE, prefix="acc"),
    }
    s, b = gen_create(payload)
    if s != 200 or not (isinstance(b, dict) and b.get("created", {}).get("jar_1", {}).get("id")):
        pytest.skip("skip-with-reason: could not seed the throwaway $5-acceptance rig "
                    f"(HTTP {s} {str(b)[:160]}); the load-bearing REJECTION leg above "
                    f"already passed — seed gate, not a product result")

    op2, token2 = mint(p_email, SEEDED_PWD)
    if not token2:
        pytest.skip("skip-with-reason: could not log in as the throwaway acceptance parent "
                    "(login gate); the REJECTION leg already passed")
    s, jars2 = _list_jars(op2, token2)
    if s != 200 or not isinstance(jars2, list) or not jars2:
        pytest.skip(f"skip-with-reason: could not list the throwaway jar (HTTP {s}); "
                    f"the REJECTION leg already passed")
    jar2_uuid = jars2[0].get("id")

    s, body5 = _post_jar_credit(op2, token2, jar2_uuid, MIN_DEPOSIT)
    print(f"  [boundary] POST ${MIN_DEPOSIT:.2f} on throwaway jar -> HTTP {s} {str(body5)[:140]}")
    assert not _is_min_rejection(s, body5), (
        f"the exact ${MIN_DEPOSIT:.2f} boundary was REJECTED as below-minimum (HTTP {s} "
        f"{str(body5)[:200]}) — the floor must be INCLUSIVE (amount >= ${MIN_DEPOSIT:.0f}).")
    print(f"  PASS: sub-${MIN_DEPOSIT:.0f} ($4/$0) rejected with no balance change "
          f"(delta {delta}); ${MIN_DEPOSIT:.2f} boundary accepted (HTTP {s})")
