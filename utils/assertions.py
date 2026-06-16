"""
Value assertions for Raiz E2E tests.

The existing suite asserts almost exclusively on *presence* ("is X visible").
Several real production defects were value/state defects that a presence check
cannot catch, e.g.:
  - RAIZ-10306  Performance widget shows incorrect change in value for 1 month
  - RAIZ-10244  Percentages shown for $0.00 on the new Performance widget
  - RAIZ-10251  Totals don't add up on custom portfolio customisation screen

These helpers parse the money/percentage strings the app renders so tests can
assert the *content* is well-formed and internally consistent, not just present.
"""
import re

# Matches $1,234.56  /  -$5.00  /  $0.00  /  $12
_MONEY_RE = re.compile(r"-?\$\s?-?[\d,]+(?:\.\d{1,2})?")
# Matches 12.3%  /  -4%  /  +0.50%
_PERCENT_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?\s?%")


def parse_money(text: str) -> float:
    """Extract the first dollar value from a string and return it as a float.

    >>> parse_money("Available: $1,234.56")
    1234.56
    >>> parse_money("-$5.00")
    -5.0
    Raises AssertionError if no money token is present so failures point at the
    real problem (the screen didn't render a value) rather than a ValueError.
    """
    assert text is not None, "Expected a money string, got None"
    match = _MONEY_RE.search(text)
    assert match, f"No dollar amount found in {text!r}"
    token = match.group(0)
    negative = token.lstrip().startswith("-") or "-$" in token or "$-" in token
    digits = token.replace("$", "").replace(",", "").replace(" ", "").replace("-", "")
    value = float(digits)
    return -value if negative else value


def parse_percent(text: str) -> float:
    """Extract the first percentage from a string as a float (sign preserved)."""
    assert text is not None, "Expected a percentage string, got None"
    match = _PERCENT_RE.search(text)
    assert match, f"No percentage found in {text!r}"
    return float(match.group(0).replace("%", "").replace(",", "").replace(" ", "").replace("+", ""))


_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(bounds: str):
    """Parse an Android element bounds string '[x1,y1][x2,y2]' into (width, height).

    Used by tap-target size checks (e.g. RAIZ-9909, where the Save button rendered
    too small). Returns None if the string is missing or malformed so callers can
    treat 'no readable bounds' distinctly from 'a real size'.

    >>> parse_bounds("[48,2010][1032,2154]")
    (984, 144)
    """
    if not bounds:
        return None
    match = _BOUNDS_RE.search(bounds)
    if not match:
        return None
    x1, y1, x2, y2 = map(int, match.groups())
    return (x2 - x1, y2 - y1)


def is_money(text: str) -> bool:
    """True if the string contains a well-formed dollar amount."""
    return bool(text) and bool(_MONEY_RE.search(text))


def assert_money(text: str, label: str = "value") -> float:
    """Assert the string is a well-formed dollar amount and return it.

    Catches the class of bug where a screen renders a malformed/empty/`$NaN`
    amount — something `is_visible(...)` will happily pass.
    """
    assert is_money(text), f"{label} is not a well-formed dollar amount: {text!r}"
    return parse_money(text)


def assert_non_negative_money(text: str, label: str = "value") -> float:
    value = assert_money(text, label)
    assert value >= 0, f"{label} should not be negative: {text!r} -> {value}"
    return value


def assert_positive_money(text: str, label: str = "value") -> float:
    value = assert_money(text, label)
    assert value > 0, f"{label} should be greater than $0.00: {text!r} -> {value}"
    return value
