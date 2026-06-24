"""
Backlog case: kid-initial-below5-rejected  (P0, raiz-kids / deposits-withdrawals)

Intended oracle (from docs/proposed-test-cases.md):
    "Kid initial one-off < $5 rejected at commit; exactly $5 credits +$5.00"
    $4.99/$1 -> validation error AND no funded kid (current_balance stays 0);
    $5.00   -> kid delta == +5.00 (band).
    NOTE in backlog: "DEPENDS on a kid-creation wizard driver (shared with the
    create-a-kid P0); slips if not in scope."

VERDICT: SKIP-WITH-EVIDENCE (honest, documented gap — not a vacuous pass).

Two INDEPENDENT, source-grounded reasons block a real assertion at build 3252:

1) NO KID-CREATION WIZARD DRIVER IS IN SCOPE.
   The initial one-off deposit only exists *inside* the new-kid creation wizard
   (InvestType.InitialInvestment), reached only after the full multi-step crawl:
       consent -> Welcome -> profile create -> portfolio -> investment access
       -> agreement -> password -> PIN -> notifications -> INVEST (initial deposit).
   The suite's Kids page object (pages/kids_page.py) and the existing
   TestKidsCreationE2E (tests/test_allocation_jars_kids_e2e.py) reach ONLY the
   consent/welcome onboarding intro — they explicitly stop short:
       "Full multi-step kid creation needs a deeper crawl (consent -> Welcome ->
        Next -> permissions -> details); covered here up to the onboarding intro."
   There is no driver that reaches the InitialInvestment amount field, so the
   commit-time validation this case targets cannot be exercised. The backlog
   note pre-authorised this slip ("slips if not in scope"). The provision
   manifest assigns this case a "fresh-per-run recipe — needs kid-creation wizard
   driver; one-off kid create", confirming the driver does not yet exist.

2) THE "< $5 REJECTED" ORACLE IS NOT GROUNDED IN BUILD 3252.
   App source (/Users/joshua/Android-AU, build 3252):
     raizFeatureKids/.../investment/KidInvestViewModel.kt
       InvestmentScreenStateHolder(..., minAmount = 0.01, ...)        # NOT 5.00
       onBottomButtonClick():
         if (amount == 0.0 && investType is InitialInvestment)        # $0 == fund-later
             onInitialInvestmentNextStep()                            # skip funding, no error
         else -> open account-select dialog -> transfer(amount)       # any >= $0.01 proceeds
   So an initial one-off of $4.99 (or $1) is ACCEPTED, not rejected: the only
   special case is $0.00 (treated as "fund later", still no validation error).
   The $5 minimum the backlog refers to is a DIFFERENT field — the recurring
   WEEKLY investment-access limit:
     raizFeatureKids/.../investment_access/KidsInvestmentAccessOption.kt
        const val MIN_LIMIT = 5
     raizFeatureKids/.../investment_access/ValidateFormatterAmountRule.kt
        return amount != null && amount >= MIN_LIMIT
   That rule guards the weekly auto-invest cap, NOT the initial one-off deposit.
   Asserting "$4.99 rejected at commit" would therefore be FABRICATED against the
   real build: there is no such enforcement point to assert on.

Backend (/Users/joshua/raiz-backend): no kid-specific initial-deposit minimum
model/validation was found either; the kid transfer rides the generic securities
transfer path. Nothing grounds a $5 floor on the initial kid deposit.

To un-skip later, BOTH must change: (a) land the shared create-a-kid wizard driver
that reaches the InitialInvestment amount field, and (b) re-confirm the oracle —
if build 3252's minAmount=0.01 still holds, the correct assertion is "$0.01..$4.99
ACCEPTED, $0.00 = fund-later", i.e. the backlog's '< $5 rejected' premise should be
RETIRED, not implemented.

needs_device: False — the skip fires unconditionally (no driver/fixture touched);
the blocking evidence is static source ground truth, not a runtime observation.
"""
import pytest

# Honest, evidence-backed skip. Reasons are independent: even if a wizard driver
# existed, the build-3252 oracle is wrong (minAmount=0.01, no < $5 rejection).
_SKIP_REASON = (
    "kid-initial-below5-rejected SKIPPED (skip-with-evidence). "
    "(1) No kid-creation wizard driver is in scope: the suite reaches only the "
    "Kids consent/welcome intro, not the InitialInvestment amount field where a "
    "commit-time check would fire (backlog: 'slips if not in scope'; manifest: "
    "fixture is a not-yet-built fresh-per-run kid-create recipe). "
    "(2) The '< $5 rejected' oracle is NOT grounded in build 3252: "
    "KidInvestViewModel uses minAmount=0.01 and only special-cases $0.00 as "
    "fund-later, so $4.99/$1 are ACCEPTED, not rejected. The $5 MIN_LIMIT in "
    "KidsInvestmentAccessOption applies to the recurring WEEKLY access limit, a "
    "different field. Asserting a < $5 initial-deposit rejection would be fabricated."
)


@pytest.mark.edge
@pytest.mark.kids
@pytest.mark.skip(reason=_SKIP_REASON)
def test_kid_initial_below5_rejected():
    """Placeholder for the < $5 initial kid-deposit rejection oracle.

    Unconditionally skipped with evidence (see module docstring). Do not convert
    to a pass until BOTH blockers clear: (a) a create-a-kid wizard driver reaches
    the InitialInvestment amount field, and (b) the oracle is re-grounded — at
    build 3252 the minimum is $0.01, so the '< $5 rejected' premise is currently
    false and should be retired rather than asserted."""
    # No body: the skip marker fires at call time regardless. Leaving the assertion
    # below documents the intended (but currently ungroundable) oracle for the
    # future driver author.
    raise AssertionError("unreachable — test is skip-marked with evidence")  # pragma: no cover
