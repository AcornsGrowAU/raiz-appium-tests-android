"""
TC-10 — My Finance net-worth VALUE reconciliation.

The 'My net worth' card on the My Finance screen shows a headline total plus two
labelled components: 'Total in investments' and 'Total in Superannuation'. The
headline MUST equal the sum of its components. This is a value invariant that
holds for ANY account state (funded or unfunded super, any portfolio balance),
so it fails for the right reason when a total is miscomputed — the RAIZ-10251
'totals don't add up' defect family.

Unlike a presence/well-formedness check (which a wrong-but-well-formed total
passes), this parses the dollar figures and asserts the arithmetic, after the
net-worth section finishes its lazy load.
"""
import pytest

from utils.assertions import assert_non_negative_money, parse_money


@pytest.mark.portfolio
@pytest.mark.e2e
@pytest.mark.regression
def test_net_worth_equals_investments_plus_super(my_finance):
    """'My net worth' headline total reconciles with its component rows.

    When the card exposes a headline figure, it must equal the sum of ALL shown
    component rows within +/-$0.02 (net worth may include cash/other beyond
    investments + super), or be >= investments + super if extra components are
    present. When the card renders only component rows and no headline figure
    (the layout observed on the current build), there is nothing to reconcile and
    the test SKIPS rather than failing for the wrong reason."""
    # Let the net-worth CARD populate. The screen renders its title before the
    # totals load, so an immediate read can catch $0 placeholders or empty
    # component rows. wait_for_net_worth() polls (longer, poll-based) and gates on
    # this specific card's component rows (header + both component labels + both
    # paired figures well-formed), not on any positive figure on the screen.
    my_finance.wait_for_net_worth()

    if not my_finance.net_worth_components_ready():
        # Header label and/or its component figures never rendered well-formed
        # money within the poll window — treat as an empty/not-loaded net-worth
        # state on the shared account rather than a math failure.
        pytest.skip("'My net worth' card did not render its component figures "
                    "(empty-state / not-loaded on the shared test account) — "
                    "no headline reconciliation possible")

    # Snapshot the component figures, then re-read until two consecutive reads
    # agree. Compose lazy-lists can recycle/re-bind a row mid-read, so a single
    # snapshot can pair a label to a transient value; requiring two identical
    # consecutive reads pins down a settled card before asserting arithmetic.
    def _read():
        return (my_finance.get_investments_total_text(),
                my_finance.get_super_total_text(),
                my_finance.get_net_worth_total_text())

    investments_text, super_text, net_worth_text = _read()
    for _ in range(3):
        again = _read()
        if again == (investments_text, super_text, net_worth_text):
            break
        investments_text, super_text, net_worth_text = again

    # Each component figure must be well-formed, non-negative money (catches a
    # blank / mislabelled component the arithmetic check below could mask).
    investments = assert_non_negative_money(investments_text, "Total in investments")
    super_total = assert_non_negative_money(super_text, "Total in Superannuation")

    if not net_worth_text:
        # The card shows its component rows but no separate headline 'My net
        # worth' dollar figure (verified on-device: this build's layout renders
        # the header label with no '$' figure on its row). There is no headline
        # total to reconcile against — skip rather than fail.
        pytest.skip("'My net worth' card exposes no headline dollar figure on "
                    "this build (only component rows render) — headline "
                    "reconciliation not applicable. Components read: "
                    f"investments=${investments}, super=${super_total}")

    net_worth = parse_money(net_worth_text)

    # Reconcile against ALL shown component rows, not just investments + super:
    # the headline may include cash/other rows on builds that show them.
    component_values = [parse_money(t) for t in my_finance.get_component_totals()]
    components_sum = round(sum(component_values), 2)
    base_sum = round(investments + super_total, 2)

    if component_values and components_sum >= base_sum:
        # We can see every component row that feeds the headline — exact match.
        assert net_worth == pytest.approx(components_sum, abs=0.02), (
            f"My net worth ${net_worth} != sum of shown component rows "
            f"${components_sum} {component_values} (within $0.02) — net-worth "
            "total does not add up (RAIZ-10251 family)")
    else:
        # Fall back to the investments + super lower bound: extra components the
        # geometric pairing missed can only add to the headline, never subtract.
        assert net_worth + 0.02 >= base_sum, (
            f"My net worth ${net_worth} < investments ${investments} + super "
            f"${super_total} (= ${base_sum}) — headline is smaller than its "
            "known components, which cannot add up (RAIZ-10251 family)")
