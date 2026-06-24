"""
withdraw-over-balance-rejected [P0] — a withdrawal GREATER THAN the available
balance must not be able to leave the account in an invalid (over-drawn) state.

BACKLOG TIGHTENING (honoured here):
  "GREEN but weak: the oracle was 'over-balance rejected OR invariant held' — the OR
   made it pass trivially. TIGHTEN to a deterministic state assertion: seed a known
   small EXACT balance, attempt a withdrawal > available, and assert the SPECIFIC
   outcome on 3252. Spike whether the gate is UI or backend; assert what's real.
   Remove the trivial OR. Keep the within-balance success leg."

SPIKE RESULT (build 3252, DEV backend, live 2026-06-24 — run twice, identical):
  Seeding user + $300 ACH credit + a $500 over-balance withdrawal in ONE atomic
  gen-create returns HTTP 422 with the exact insufficient_funds signature and commits
  NOTHING:
    HTTP 422
    errors: ["withdrawal_1: The amount you have requested to withdraw plus your
              already pending withdraws exceeds your account balance. ..."]
    created: {}            # no user_1, no credit_1, no withdrawal_1
    can_login(email): False  # the over-drawing user never committed
  => On 3252 the gate is BACKEND-enforced at the DebitInvestment create layer
     (cannot_withdraw_more_than_available). It is NOT ungated. The old UNGATED/
     invariant-held leg was therefore dead code that could only ever mask a
     regression behind a vacuous pass, so it is REMOVED. This test now asserts the
     ONE real, deterministic state outcome; if a future build stops gating, this test
     goes RED (it must, so a human re-evaluates) rather than silently passing.

This is the DEV-API (value_api) layer of the case — the deterministic, no-device half.
The on-device withdrawal *journey* (within-balance, through 'Withdrawal Confirmed') is
covered by test_withdraw_available_value.py; the within-balance reduction by
test_value_validation_api.py. What was NOT covered is the NEGATIVE/rejection state:
attempting to withdraw MORE than is available.

BACKEND GROUND TRUTH (raiz-backend, the oracle):
  app/models/debit_investment.rb:17
    validate :cannot_withdraw_more_than_available, on: :create, ...
  app/models/debit_investment.rb:237-238
    def cannot_withdraw_more_than_available
      add_base_error_for("insufficient_funds") if amount > user.available_amount_to_withdraw
  app/models/concerns/user_investments.rb:652-654
    def available_amount_to_withdraw
      current_balance.round(2) - pending_withdraws.amount.round(2)
  config/locales/en.yml:107  insufficient_funds:
    "The amount you have requested to withdraw plus your already pending withdraws
     exceeds your account balance. ..."
So the backend invariant is: a settled withdrawal can never exceed
available_amount_to_withdraw, i.e. it can never drive current_balance below 0.

WHY THE STATE ORACLE IS EXPRESSED VIA ATOMICITY (not "balance unchanged" on a
committed user): a withdrawal entity can only reference a user created in the SAME
gen-create payload (@user_1). A withdrawal-only create against a pre-committed user is
rejected — referencing by email -> 422 'User expected, got "<email>" ... String', by id
-> 422 'User expected, got <id> ... Integer' (verified live 2026-06-24). So the
over-balance withdrawal MUST be exercised in the combined atomic create. Because the
create is atomic, the gated outcome IS the "over-available error + no settled
DebitInvestment + balance/available unchanged" state: NOTHING committed, so there is no
debit, and there is no over-drawn balance to read (the user does not exist).

The within-balance SUCCESS leg is kept (test_within_balance_withdrawal_succeeds): a
small EXACT withdrawal that DOES fit settles the balance to the exact net — the control
that proves the rejection leg is a real over-balance gate, not the API rejecting *all*
withdrawals.

DATA: dynamic — fresh funded users with SMALL EXACT ACH balances (NOT the six-figure
rich_withdrawal_buffer, whose market-priced holdings reprice between reads and would
make an exact over/under-balance oracle impossible). Small exact ACH credits settle to
current_balance to the cent and stay stable.

Run (no emulator needed):
  venv/bin/python -m pytest tests/test_withdraw_over_balance_rejected.py -v -s -o addopts=""
"""
import os
import time

import pytest

from utils.genuser_api import (
    gen_create, mint, call, funded_user, ach_credit, ach_withdrawal, can_login, SEEDED_PWD,
)

pytestmark = [pytest.mark.value_api, pytest.mark.edge]

# SMALL EXACT ACH balances (cents-exact, stable — deliberately NOT the priced buffer).
SEED_BALANCE = 300.00      # exact settled balance both legs start from
WITHIN_WITHDRAW = 120.00   # success leg: fits within balance -> nets to 180.00
WITHIN_NET = round(SEED_BALANCE - WITHIN_WITHDRAW, 2)
OVER_WITHDRAW = 500.00     # rejection leg: > SEED_BALANCE (and > available)

BAND = 1.50  # cents/rounding tolerance on an exact ACH-settled balance
SETTLE_BUDGET_S = int(os.getenv("SETTLE_BUDGET_S", "300"))
POLL_INTERVAL_S = int(os.getenv("POLL_INTERVAL_S", "20"))

# 422 signature of the backend's cannot_withdraw_more_than_available gate. Grounded in
# the EXACT insufficient_funds string (en.yml:107) the spike returned, not a loose
# substring set: the phrase "exceeds your account balance" is unique to this validation,
# so it cannot be satisfied by an unrelated withdrawal error (e.g. funding/RDV/frozen).
_GATE_PHRASE = "exceeds your account balance"


def _ts():
    return str(int(time.time()))


class _BalanceReader:
    """Reads backend current_balance reusing ONE minted session across poll reads
    (the /v1/sessions endpoint is rate-limited; re-minting per read would trip it).
    Re-mints only when a cached token is rejected. Returns float or None."""

    def __init__(self, email, pwd=SEEDED_PWD):
        self.email, self.pwd = email, pwd
        self._op = self._tok = None

    def _ensure(self):
        if self._tok is None:
            self._op, self._tok = mint(self.email, self.pwd)
        return self._tok is not None

    def read(self):
        for _ in range(2):
            if not self._ensure():
                self._op = self._tok = None
                return None
            s, b = call(self._op, "GET", "/v1/user", token=self._tok)
            if s == 200:
                user = b.get("user", b) if isinstance(b, dict) else {}
                cb = user.get("current_balance")
                return float(cb) if cb is not None else None
            self._op = self._tok = None
        return None


def _poll_until_stable(email, target, reader=None):
    """Poll current_balance until it lands within BAND of `target`, or the budget
    elapses. Returns (best_balance, settled_bool). best_balance is the reading
    closest to target so failure messages are meaningful."""
    reader = reader or _BalanceReader(email)
    waited = 0
    best, best_err = None, None
    while waited <= SETTLE_BUDGET_S:
        bal = reader.read()
        if bal is not None:
            err = abs(bal - target)
            if best_err is None or err < best_err:
                best, best_err = bal, err
            print(f"  [poll +{waited}s] current_balance={bal} (target {target})")
            if err <= BAND:
                return bal, True
        else:
            print(f"  [poll +{waited}s] backend balance read failed")
        time.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    return best, False


def test_within_balance_withdrawal_succeeds():
    """CONTROL / success leg: a withdrawal that FITS within the available balance
    settles the balance down to the exact net. Proves the rejection leg below is a
    real over-balance gate, not the API rejecting every withdrawal.

    $300 credit - $120 withdrawal -> current_balance settles to exactly $180.

    The user, the credit, and the within-balance withdrawal are seeded in a SINGLE
    gen_create so @user_1 resolves for the withdrawal entity (the proven recipe used by
    test_value_validation_api.test_main_balance_reduced_by_withdrawal and
    test_net_invested_ledger_recon). Two separate creates that each re-submit
    funded_user(same_email) hit the unique-email constraint (422) and the withdrawal
    entity never runs — so this leg builds the whole ledger in one payload.
    """
    email = f"wob.within.{_ts()}@emel.xyz"
    status, body = gen_create({
        "user_1": funded_user(email, "WobWithin"),
        "credit_1": ach_credit("@user_1", SEED_BALANCE),
        "withdrawal_1": ach_withdrawal("@user_1", WITHIN_WITHDRAW),
    })
    # The user + credit + within-balance withdrawal must all create cleanly: the
    # within-balance withdrawal must NOT be gated.
    assert status == 200, f"within-balance seed+withdrawal create failed: HTTP {status} {body}"
    assert body.get("created", {}).get("user_1", {}).get("id"), f"no user id: {body}"
    print(f"  created user + ${SEED_BALANCE} credit + ${WITHIN_WITHDRAW} withdrawal "
          f"(expect net ${WITHIN_NET})")

    bal, settled = _poll_until_stable(email, WITHIN_NET)
    assert settled, f"net never settled to ${WITHIN_NET} (best ${bal})"
    assert bal == pytest.approx(WITHIN_NET, abs=BAND), (
        f"expected net ${WITHIN_NET} (${SEED_BALANCE}-${WITHIN_WITHDRAW}) but balance ${bal}")
    print(f"  PASS: within-balance withdrawal settled to exact net ${bal}")


def test_over_balance_withdrawal_rejected():
    """REJECTION leg — DETERMINISTIC state assertion (the trivial OR is removed).

    On build 3252 the over-balance gate is BACKEND-enforced at the DebitInvestment
    create layer (spiked live, twice, identical — see module docstring). This test
    asserts that ONE real outcome with NO fallback branch: a $500 withdrawal against a
    $300 balance, submitted with the user + credit in a SINGLE atomic gen_create, MUST
    be rejected, and the atomic create MUST commit nothing.

    State oracle (all four, hard-asserted — no OR):
      1. HTTP 422 (rejected, not accepted).
      2. The over-available error is shown — the exact insufficient_funds signature
         "exceeds your account balance" (en.yml:107 /
         debit_investment.rb:cannot_withdraw_more_than_available). NOT a loose match.
      3. NO settled DebitInvestment: `created` contains no withdrawal_1.
      4. Balance + available unchanged: the create is atomic, so the over-drawing user
         was not committed at all — it cannot log in, hence no balance exists that the
         debit could have reduced. (A separate withdrawal-only create against a
         pre-committed user is impossible on this API — see module docstring.)

    If a future build stops gating (200, or a 422 without the over-available signature),
    this test goes RED. That is intended: a missing balance gate is a P0 product defect,
    and the OLD test masked exactly that behind a vacuous "invariant held" pass.

    $300 credit, $500 withdrawal (> balance, so > available_amount_to_withdraw).
    """
    email = f"wob.over.{_ts()}@emel.xyz"
    status, body = gen_create({
        "user_1": funded_user(email, "WobOver"),
        "credit_1": ach_credit("@user_1", SEED_BALANCE),
        "withdrawal_1": ach_withdrawal("@user_1", OVER_WITHDRAW),
    })
    errs = str(body.get("errors", body)).lower() if isinstance(body, dict) else str(body).lower()
    created = body.get("created", {}) if isinstance(body, dict) else {}
    print(f"  over-balance combined create -> HTTP {status}; errs={errs[:220]}")

    # 1. REJECTED, not accepted. A 200 here would mean the balance gate is gone — a P0
    #    product defect, and exactly what the old OR masked. Fail loudly.
    assert status == 422, (
        f"over-balance withdrawal (${OVER_WITHDRAW} on ${SEED_BALANCE}) was NOT rejected: "
        f"HTTP {status} {str(body)[:300]} — the backend balance gate "
        f"(cannot_withdraw_more_than_available) did not fire; possible P0 regression")

    # 2. ...with the SPECIFIC over-available signature, not just any 422.
    assert _GATE_PHRASE in errs, (
        f"over-balance withdrawal was rejected (422) but NOT with the over-available "
        f"signature '{_GATE_PHRASE}' (en.yml:107). Got: {errs[:300]} — the rejection is a "
        f"different failure, not the balance gate under test")

    # 3. No settled DebitInvestment landed.
    assert "withdrawal_1" not in created, (
        f"over-balance withdrawal was gated (422) yet a withdrawal_1 entity still appears "
        f"in `created` — a leaked DebitInvestment: {body}")

    # 4. Balance + available unchanged: the atomic create committed nothing, so the
    #    over-drawing user does not exist and cannot log in (no balance to over-draw).
    assert not created, (
        f"over-balance create was gated but `created` is non-empty {list(created)} — the "
        f"create was NOT atomic; a partial ledger committed and must be re-evaluated")
    assert not can_login(email), (
        f"over-balance withdrawal was gated (good) but the user {email} was committed "
        f"anyway — the atomic create leaked a partial ledger; verify no debit landed")

    print(f"  PASS (REJECTED, deterministic): over-balance withdrawal gated with the "
          f"over-available signature; atomic create committed nothing (empty `created`, "
          f"user cannot log in). Gate is BACKEND-enforced on build 3252.")
