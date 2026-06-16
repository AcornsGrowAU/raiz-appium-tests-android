"""
Unit tests for utils/assertions.py — the money/percentage parsers that every
value-based E2E assertion depends on.

These are PURE-FUNCTION tests: no device, no Appium, no driver fixture. They run
anywhere (including CI without a phone) and lock the parsing behaviour so a
regression in the helpers can't silently weaken every value check in the suite.
"""
import pytest

from utils.assertions import (
    parse_money, parse_percent, is_money, parse_bounds,
    assert_money, assert_non_negative_money, assert_positive_money,
)


@pytest.mark.unit
class TestParseMoney:
    @pytest.mark.parametrize("text,expected", [
        ("$0.00", 0.0),
        ("$12", 12.0),
        ("$1,234.56", 1234.56),
        ("$1,564.85", 1564.85),
        ("$1,234,567.89", 1234567.89),
        ("Available: $1,234.56", 1234.56),
        ("Your total investments value $1,564.24", 1564.24),
        ("$ 100", 100.0),          # space after the sign
        ("$1,234.5", 1234.5),      # single decimal place
    ])
    def test_positive_values(self, text, expected):
        assert parse_money(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text,expected", [
        ("-$5.00", -5.0),
        ("$-5.00", -5.0),
        ("-$1,234.56", -1234.56),
    ])
    def test_negative_values(self, text, expected):
        assert parse_money(text) == pytest.approx(expected)

    def test_picks_first_amount_when_several(self):
        assert parse_money("$10 then $20") == pytest.approx(10.0)

    @pytest.mark.parametrize("bad", [None, "", "no money here", "12.3%", "$"])
    def test_raises_when_no_amount(self, bad):
        with pytest.raises(AssertionError):
            parse_money(bad)


@pytest.mark.unit
class TestParsePercent:
    @pytest.mark.parametrize("text,expected", [
        ("12.3%", 12.3),
        ("5%", 5.0),
        ("-4%", -4.0),
        ("+0.50%", 0.5),
        ("Change: 12.3%", 12.3),
        ("100 %", 100.0),         # space before %
        ("1,234.5%", 1234.5),
    ])
    def test_values(self, text, expected):
        assert parse_percent(text) == pytest.approx(expected)

    @pytest.mark.parametrize("bad", [None, "", "no percent", "$5.00"])
    def test_raises_when_no_percent(self, bad):
        with pytest.raises(AssertionError):
            parse_percent(bad)


@pytest.mark.unit
class TestIsMoney:
    @pytest.mark.parametrize("text", ["$0.00", "$5", "$1,234.56", "-$5.00", "Available: $10"])
    def test_true_for_money(self, text):
        assert is_money(text) is True

    @pytest.mark.parametrize("text", [None, "", "abc", "5 dollars", "4.5%", "$"])
    def test_false_for_non_money(self, text):
        assert is_money(text) is False


@pytest.mark.unit
class TestAssertHelpers:
    def test_assert_money_returns_value(self):
        assert assert_money("$42.50") == pytest.approx(42.5)

    def test_assert_money_rejects_garbage(self):
        with pytest.raises(AssertionError):
            assert_money("not a price")

    def test_non_negative_accepts_zero(self):
        assert assert_non_negative_money("$0.00") == pytest.approx(0.0)

    def test_non_negative_rejects_negative(self):
        with pytest.raises(AssertionError):
            assert_non_negative_money("-$1.00")

    def test_positive_rejects_zero(self):
        with pytest.raises(AssertionError):
            assert_positive_money("$0.00")

    def test_positive_accepts_positive(self):
        assert assert_positive_money("$0.01") == pytest.approx(0.01)


# A documented parser gap: the test asserts the CORRECT value and is marked xfail
# because the current parser gets it wrong. If the parser is hardened, the test
# x-passes and flags that the gap is closed (strict=False keeps the suite green).
def _gap(reason):
    return pytest.mark.xfail(reason=reason, strict=False)


@pytest.mark.unit
class TestWeirdMoneyFormats:
    """Weird-but-real money strings a finance UI can emit. Locks the ones the
    parser handles and documents the ones it doesn't."""

    @pytest.mark.parametrize("text,expected", [
        ("$007", 7.0),                        # leading zeros
        ("$1234567.89", 1234567.89),          # no thousands separators
        ("$1,2,3,4", 1234.0),                 # malformed commas tolerated
        ("$ 5", 5.0),                         # space after the sign
        ("$5.", 5.0),                         # trailing dot, no cents
        ("  $5.00  ", 5.0),                   # surrounding whitespace
        ("$1,234.5", 1234.5),                 # single decimal place
        ("Total: $0.00 today", 0.0),          # embedded in a sentence
        ("$12,345,678.90", 12345678.90),      # millions
        ("$10 / $20", 10.0),                  # first of several amounts
        ("$0", 0.0),                          # bare zero
        ("$100.5", 100.5),
    ])
    def test_unusual_but_parseable(self, text, expected):
        assert parse_money(text) == pytest.approx(expected)

    def test_three_decimals_truncate_to_cents(self):
        """A 3-dp string is read to cents — locks current behaviour so a future
        change to rounding is noticed."""
        assert parse_money("$5.999") == pytest.approx(5.99)

    def test_amount_after_newline(self):
        assert parse_money("Available:\n$50.00") == pytest.approx(50.0)

    def test_negative_zero_is_zero(self):
        assert parse_money("-$0.00") == pytest.approx(0.0)

    @pytest.mark.parametrize("text,expected", [
        pytest.param("($5.00)", -5.0, marks=_gap("accounting-parentheses negatives not handled")),
        pytest.param("$5.00-", -5.0, marks=_gap("trailing-minus negatives not handled")),
        pytest.param("−$5.00", -5.0, marks=_gap("unicode minus U+2212 not handled")),
        pytest.param("$.50", 0.5, marks=_gap("amounts with no leading zero not parsed")),
    ])
    def test_known_gaps(self, text, expected):
        assert parse_money(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["$5.999", "($5.00)", "Available: $10", "-$5.00"])
    def test_is_money_true(self, text):
        assert is_money(text) is True

    @pytest.mark.parametrize("text", ["$.50", "FREE", "0.00", "$"])
    def test_is_money_false(self, text):
        assert is_money(text) is False


@pytest.mark.unit
class TestWeirdPercentFormats:
    @pytest.mark.parametrize("text,expected", [
        ("0%", 0.0),
        ("100%", 100.0),
        ("+50%", 50.0),
        ("-12.5%", -12.5),
        ("1,000%", 1000.0),
        ("12.34%", 12.34),
        ("Change 5%", 5.0),
        ("5 %", 5.0),               # space before %
        ("+0.50%", 0.5),
        ("-4%", -4.0),
        ("0.00%", 0.0),
    ])
    def test_unusual_but_parseable(self, text, expected):
        assert parse_percent(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text,expected", [
        pytest.param("−5%", -5.0, marks=_gap("unicode minus not handled in percent")),
        pytest.param(".5%", 0.5, marks=_gap("percent with no leading zero misparsed as 5%")),
    ])
    def test_known_gaps(self, text, expected):
        assert parse_percent(text) == pytest.approx(expected)


@pytest.mark.unit
class TestParseBounds:
    """The Android-bounds parser behind tap-target size checks (RAIZ-9909)."""

    @pytest.mark.parametrize("bounds,expected", [
        ("[48,2010][1032,2154]", (984, 144)),     # the real Save button
        ("[0,0][100,50]", (100, 50)),
        ("[0,0][0,0]", (0, 0)),                    # zero-size (hidden/collapsed)
        ("bounds=[1,2][3,4]", (2, 2)),             # embedded in surrounding text
        ("[10,10][5,5]", (-5, -5)),                # inverted → negative (caller rejects)
    ])
    def test_parses_dimensions(self, bounds, expected):
        assert parse_bounds(bounds) == expected

    @pytest.mark.parametrize("bad", [None, "", "garbage", "[1,2]", "1,2,3,4"])
    def test_returns_none_for_malformed(self, bad):
        assert parse_bounds(bad) is None
