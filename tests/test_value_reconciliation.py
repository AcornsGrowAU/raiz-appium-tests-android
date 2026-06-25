"""
VALUE reconciliation on the Home screen — asserts the numbers ADD UP, not just
that money strings are present. Targets the RAIZ-10251 'totals don't add up on
the customisation screen' defect class. Pure device test (no test-data API).

Unlike a presence check (`balance looks like money`), these parse the dollar
figures and assert arithmetic relationships that MUST hold for any account state,
so they fail for the right reason when a total is miscomputed.
"""
import pytest

from utils.assertions import is_money


def _money(s):
    """Parse a displayed money string ('$1,578.11') to float, or None."""
    if not s:
        return None
    if not is_money(s):
        # tolerate '$0' which some cards render without decimals
        cleaned = s.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return float(s.replace("$", "").replace(",", "").strip())


# The Home screen's per-account cards. Empty cards (Jars/Kids with no balance)
# render no dollar figure and legitimately contribute 0 to the total.
CARDS = ["Main Portfolio", "Jars", "Kids", "Superannuation"]


def _read_home_values(home):
    total = _money(home.get_total_value())
    cards = {}
    for label in CARDS:
        v = _money(home.get_account_card_value(label))
        if v is not None:
            cards[label] = v
    return total, cards


@pytest.mark.portfolio
def test_home_total_equals_sum_of_account_cards(home):
    """The displayed 'Your total investments value' must equal the sum of the
    per-account card values that render a figure (RAIZ-10251: totals must add up)."""
    total, cards = _read_home_values(home)
    assert total is not None, "Home total value should be well-formed money"
    assert cards, "Expected at least one account card to render a dollar value"
    summed = round(sum(cards.values()), 2)
    assert summed == pytest.approx(total, abs=0.01), (
        f"Home total ${total} does not equal the sum of its account cards "
        f"${summed} {cards} — totals don't add up (RAIZ-10251)")


@pytest.mark.portfolio
def test_no_account_card_exceeds_the_total(home):
    """No single account card may show more than the overall total — a cheap,
    state-independent value invariant that catches a card/total mismatch."""
    total, cards = _read_home_values(home)
    assert total is not None, "Home total value should be well-formed money"
    for label, value in cards.items():
        assert value <= total + 0.01, (
            f"'{label}' card shows ${value}, more than the Home total ${total}")
