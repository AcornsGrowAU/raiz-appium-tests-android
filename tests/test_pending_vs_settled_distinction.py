"""
Backlog case: pending-vs-settled-distinction  (P1, portfolio-performance)

Intended oracle (from docs/proposed-test-cases.md, row key
`pending-vs-settled-distinction`):
    "Pending vs settled row rendered correctly (pending flagged, not counted
     settled). Pending marker present on pending row, absent on settled."
    Refinement (notes column, verdict=refine):
    "Phase-0: prove a 'seed a credit that renders Pending' recipe (drop
     with_shares_settled_status); if unprovable -> downgrade P2 or cut
     (timing-only/flaky)."   data_mode=dynamic, consensus 1, conf 35.

VERDICT: SKIP-WITH-EVIDENCE (honest, documented gap — not a vacuous pass).

The refinement made the build conditional on a Phase-0 proof: a recipe to *seed*
a credit that renders under the app's "Pending" section. That recipe does not
exist on DEV at build 3252. Three independent, source-grounded facts establish
this, and the provision manifest (FLAG #4) recorded the same conclusion: "no
pending-seed recipe ... There is no proven recipe to seed a row that renders as
Pending on DEV (conf 35). No fixture created -> skip-with-evidence."

1) THE APP RENDERS "PENDING" PURELY FROM A NON-SETTLED CREDIT STATUS.
   app/src/main/java/com/raiz/history/HomeHistoryItem.kt (build 3252):
       val pending: Boolean
       ...
       if (current.pending) { items.add(HomeHistoryItem.Header("Pending")) }
   The home transaction history groups rows under a single `Header("Pending")`
   section whenever the item's `pending` flag is true; settled rows fall under
   their date headers instead (HomeHistoryContentState.kt: "Pending" header vs
   the "pending"/date mapping). So the marker the oracle wants to assert is a
   server-driven boolean: a credit must arrive in a NON-settled status to render
   under that header.

2) THE GEN API SEEDS EVERY ACH CREDIT AS SETTLED — NO PENDING TRAIT EXPOSED.
   utils/genuser_api.py seeds lump-sum / ACH credits with the settled trait:
       "traits": ["lump_sum", "with_shares_settled_status", "with_holdings"]   (line ~160)
       "traits": ["with_shares_settled_status", "with_holdings"]               (line ~241)
   Backend factory (raiz-backend/spec/factories/credit_investment.rb):
       trait :with_shares_settled_status do status { 'shares_settled' } end
   `shares_settled` is a terminal/settled state in the CreditInvestment state
   machine (raiz-backend/app/models/credit_investment.rb:
       waiting -> pending -> approved -> transferred -> settled -> shares_settled).
   A `shares_settled` credit has `pending == false`, so it can ONLY ever render
   under a date header, never under "Pending". The test_data_generation endpoint
   exposes the settled traits but NO trait to seed a credit left in
   `pending` / `pending_settle` / `transferred` (the only states that would flip
   the app's `pending` flag true). Dropping `with_shares_settled_status`
   (as the refinement asks) yields a credit that the generator drives to settled
   anyway / does not deterministically park in a pending state — there is no
   "seed-as-pending" trait to substitute.

3) A REAL PENDING ROW IS A TRANSIENT, TIMING-ONLY ARTIFACT — NOT SEEDABLE
   DETERMINISTICALLY. On the real rails, a credit is `pending`/`transferred`
   only during the brief window before settlement/clearing (external ACH +
   broker action). There is no DEV hook to freeze a credit in that window for a
   test to read. Asserting on it would be inherently flaky — exactly the
   "timing-only/flaky" failure mode the backlog refinement told us to cut rather
   than ship. Backlog confidence on this case is 35 (lowest tier), reflecting
   that the seed recipe was unproven from the outset.

CONCLUSION: the Phase-0 gate failed (no pending-seed recipe), so per the
refinement this case is not built as a passing test. It is shipped as an
evidence-backed skip (documented gap) rather than downgraded silently or faked.

To un-skip later, the Phase-0 blocker must clear: a DEV test_data_generation
trait (or internal endpoint) that seeds a CreditInvestment in a non-settled
status (`pending`/`pending_settle`/`transferred`) and keeps it there long enough
to read. Once such a fixture exists, the assertion is straightforward and
deterministic: the pending row renders under the `Header("Pending")` section
(app/.../HomeHistoryItem.kt) and a settled row of the same user does NOT — i.e.
the pending credit is flagged pending and is excluded from the settled grouping.

needs_device: False — the skip fires unconditionally (no driver/fixture/emulator
touched); the blocking evidence is static ground truth from the app source, the
gen-API seed traits, and the backend state machine, not a runtime observation.
"""
import pytest

_SKIP_REASON = (
    "pending-vs-settled-distinction SKIPPED (skip-with-evidence; Phase-0 gate failed). "
    "The app renders a 'Pending' history header only from a NON-settled credit status "
    "(app/.../history/HomeHistoryItem.kt: Header(\"Pending\") gated on item.pending). "
    "The gen API seeds every ACH/lump-sum credit with the settled trait "
    "with_shares_settled_status (utils/genuser_api.py -> status 'shares_settled', a "
    "terminal state in CreditInvestment's waiting->pending->...->settled->shares_settled "
    "machine), and exposes NO trait to park a credit in pending/pending_settle/transferred. "
    "A real pending row is a transient ACH/clearing-window artifact (timing-only, flaky) "
    "with no DEV seed hook. Manifest FLAG #4 + backlog conf 35: no pending-seed recipe -> "
    "no fixture -> skip-with-evidence. Un-skip only once a deterministic non-settled-credit "
    "seed exists; then assert the pending row sits under Header('Pending') and the settled "
    "row does not."
)


@pytest.mark.portfolio
@pytest.mark.value_api
@pytest.mark.skip(reason=_SKIP_REASON)
def test_pending_vs_settled_distinction():
    """Placeholder for the pending-vs-settled history-row distinction oracle.

    Unconditionally skipped with evidence (see module docstring). Do NOT convert
    to a pass until the Phase-0 blocker clears: a deterministic DEV recipe to seed
    a CreditInvestment in a non-settled status (pending/pending_settle/transferred)
    that survives long enough to read. At build 3252 every gen-API credit is
    seeded `shares_settled` (pending==false), so no row can render under the app's
    Header("Pending") section — asserting one would be fabricated/flaky."""
    raise AssertionError("unreachable — test is skip-marked with evidence")  # pragma: no cover
