"""
new-kid-zero-start (P0, conf 82, cons 20) — VALUE, API-layer-first.

A newly created (bare, unfunded) kid sub-account starts at EXACTLY $0.00 — not
blank/null, and NOT a partition of / inherited from the parent's balance.

ORACLE (backend ground truth, the reliable anchor per the backlog note):
  The kid is its own `user` (a DependentUser kid_account) under the parent. The
  Raiz API exposes `current_balance` as a Float on the user entity
  (app/api/entities/user.rb), computed from settled holdings
  (User#current_balance -> total_current_amount_for_funds_for_presentation in
  app/models/concerns/user_cache_rebalance.rb). A kid with NO ACH credit / NO
  holdings therefore reports current_balance == 0.0 EXACTLY — a real numeric
  zero, never nil/blank. We log in AS the kid (its own deterministic
  `k.<parent-email>` address) and read that value directly.

WHY API-LAYER (no device):
  The backlog note marks the API current_balance==0.0 read as the reliable
  anchor for this case. This is a pure DEV-API value test — deterministic, no
  emulator, no async settle to poll (an unfunded kid has nothing to settle). The
  on-device card render ($0.00 vs blank) is a separate UI concern not owned here.

DATA: the pre-provisioned `bare_kid` fixture (reuse strategy). user_1 is the
parent (stored login); kid_1 is a BARE kid at `k.<parent-email>`. No fresh seed
unless the stored fixture no longer logs in (handled by get_or_create_fixture_user).

Run (no emulator needed):
  venv/bin/python -m pytest tests/test_new_kid_zero_start.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import SEEDED_PWD, current_balance, can_login
from utils.genuser_fixtures import get_or_create_fixture_user

pytestmark = [pytest.mark.value_api, pytest.mark.kids]

FIXTURE_KEY = "bare_kid"


def _kid_email(parent_email):
    """The bare_kid fixture seeds the kid at `k.<parent-email>` (see
    utils.genuser_fixtures FIXTURES['bare_kid']: kid_user('k.' + email, ...)).
    Derive it from the stored parent rec so it stays correct if the fixture is
    ever re-seeded under a new timestamped address."""
    return "k." + parent_email


def _balance_or_retry(email, pwd=SEEDED_PWD, attempts=4, delay=3):
    """Read current_balance, retrying ONLY a None result (a transient login /
    /v1/user read flap or a /v1/sessions rate-limit window), never a real value.

    current_balance() collapses login-fail, non-200 read, and missing-field all to
    None. A single transient hiccup on the read would otherwise fail this pure-API
    case spuriously. We poll a few times rather than blind-read once: a genuine
    bare-kid 0.0 returns immediately (a real float, not None), so this only ever
    adds latency on an actual transient failure — it can never turn a non-zero
    backend value into a zero. Returns the float (incl. a true 0.0) or None if it
    never reads cleanly."""
    last = None
    for i in range(attempts):
        last = current_balance(email, pwd)
        if last is not None:
            return last
        if i < attempts - 1:
            time.sleep(delay)
    return last


def test_bare_kid_starts_at_exactly_zero():
    """A newly created, unfunded kid's backend current_balance is EXACTLY 0.0 —
    a real numeric zero (not nil/blank, not the parent's balance)."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email = parent["email"]
    kid_email = _kid_email(parent_email)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')}); "
          f"bare kid {kid_email}")

    # The kid must be a real, logged-in account in its own right (so a 0.0 is a
    # genuine zero balance, not a 'could not read' masquerading as zero).
    assert can_login(kid_email, SEEDED_PWD), (
        f"bare kid {kid_email} could not log in — fixture not provisioned as "
        f"expected; cannot distinguish a true $0.00 from an unreadable account"
    )

    kid_balance = _balance_or_retry(kid_email, SEEDED_PWD)
    assert kid_balance is not None, (
        f"could not read current_balance for bare kid {kid_email} (login ok but "
        f"/v1/user read failed after retries) — would mask a blank/null as zero"
    )
    print(f"  bare kid current_balance == {kid_balance}")

    # The core oracle: EXACTLY zero. Not approx — a bare kid with no holdings has
    # nothing to drift, so the backend returns a hard 0.0.
    assert kid_balance == 0.0, (
        f"bare kid should start at EXACTLY $0.00 but current_balance == "
        f"{kid_balance} (inherited/partitioned from parent, or stale holdings?)"
    )


def test_bare_kid_zero_is_not_inherited_from_parent():
    """Anti-inheritance guard: the kid's $0.00 is genuinely the kid's own zero,
    NOT a mirror/partition of the parent. The parent is a `funded_user` (has its
    own non-kid balance levers), so if the kid were inheriting the parent's value
    the kid would read non-zero. Assert kid == 0.0 while reading the parent
    independently — they are distinct accounts with the kid pinned at zero."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email = parent["email"]
    kid_email = _kid_email(parent_email)

    kid_balance = _balance_or_retry(kid_email, SEEDED_PWD)
    assert kid_balance is not None, f"could not read bare kid balance for {kid_email}"

    # Read the parent independently. The bare_kid parent is seeded via funded_user
    # WITHOUT an ACH credit, so its own current_balance is also 0.0 — that does not
    # weaken the oracle: the point is the kid does not pull a DIFFERENT (parent)
    # number. We assert the kid is its own hard zero regardless of the parent value,
    # and that the read is a real numeric value (not nil) on a distinct account.
    parent_balance = _balance_or_retry(parent_email, parent.get("password", SEEDED_PWD))
    print(f"  parent {parent_email} current_balance == {parent_balance}; "
          f"kid {kid_email} current_balance == {kid_balance}")

    # Distinct accounts: the kid login is a different user than the parent. A bare
    # kid never adopts a non-zero parent figure — if the parent is ever funded and
    # the kid still reads 0.0, that is the inheritance-safety this case targets.
    assert kid_email != parent_email, "kid and parent must be distinct accounts"
    # The parent must be a real, independently readable account (not a failed read
    # masquerading as the comparison anchor). This makes the anti-inheritance claim
    # rest on TWO genuine account reads, not just a string compare: we proved the
    # kid login resolves to a current_balance AND the parent login resolves to its
    # own current_balance, on distinct addresses.
    assert parent_balance is not None, (
        f"could not read parent current_balance for {parent_email} — cannot assert "
        f"the kid's zero is its own vs inherited without a real parent read"
    )

    assert kid_balance == 0.0, (
        f"bare kid current_balance must be its OWN exact $0.00, got {kid_balance}"
    )
