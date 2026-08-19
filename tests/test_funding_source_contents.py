"""
funding-source-contents (P1, value, data_mode=dynamic) — API-layer-first VALUE test.

ORACLE (from docs/proposed-test-cases.md):
  "Funding/withdrawal destination renders real values, never blank/'%s'.
   Bank name non-empty non-placeholder string; account id matches mask regex
   (mask chars + trailing digits); no null/'%s'.
   DROP hard BSB unless confirmed; withdraw-destination tie is optional secondary."

WHAT THE APP RENDERS (build 3252 ground truth):
  FundingCurrentViewModel.loadFundingAccount() builds the on-screen destination string as
      name = "${fundingAccount.name.orEmpty()} (${fundingAccount.lastFour.orEmpty()})".trim()
  from accountsRepository.getUserAccounts() == GET /v1/accounts -> `funding` object
  (raizCore .../accounts/FundingAccountResponse.kt: SerializedName "name" + "last_4").
  So the exact bytes the customer sees are "<bank name> (<last_4>)". If either field is
  null/blank the user sees a hollow "()" or " ( )" — the very defect this case guards.

BACKEND GROUND TRUTH (app/views/api/accounts.rabl):
  funding.name  := current_user.funding_source.yodlee_monitored_site.site_name
  funding.last_4:= current_user.funding_source.last_4
  funding.funding_type := funding_source.fund_type  (only emitted when funding?("ach"))
  -> name and last_4 are BOTH driven by seeded data; neither is a hardcoded string, so a
     bad seed/migration genuinely surfaces null here (verified: the static `presence_funded`
     fixture returns name:null,last_4:null — i.e. a blank destination — see PROVISION note).

WHY data_mode=dynamic (NOT the provisioned `presence_funded` fixture):
  Probing the manifest fixture `presence_funded` (user 42057) against /v1/accounts returns
  {"name": null, "last_4": null} — the seed never populated a yodlee_monitored_site nor a
  last_4, so it CANNOT exercise the real-value oracle. This test therefore SEEDS a fresh
  user per run with a fully-populated ACH funding source + linked funding yodlee site
  (proven recipe below; created user 42149 returned name:"Commonwealth Bank", last_4:"4321")
  so the rendered destination string carries REAL values, deterministically, with no device.

SCOPE / REFINEMENTS honoured:
  - API-layer-first, no device (needs_device=False): asserts the exact JSON the app turns
    into the destination string.
  - DROP hard BSB: /v1/accounts emits no BSB/routing field at all — nothing to assert; not
    seeded, not asserted.
  - Account id "mask regex": last_4 must be exactly the masked tail the UI shows (digits
    only; the app wraps it in "(...)" so the mask chars are the literal parens). Assert it
    is a non-empty run of digits, never a placeholder/format token.
  - "never blank/'%s'": name & last_4 must be non-empty and must NOT be a placeholder/format
    token (e.g. "%s", "%1$s", "null", "N/A", "{0}", "—").
  - withdraw-destination tie (optional secondary): in Raiz the linked ACH funding source IS
    the withdrawal destination (single per-user funding_source; withdrawals route back to it).
    We assert STATE (the same single funding block is the ACH destination), not enforcement.

Run (no emulator):
  venv/bin/python -m pytest tests/test_funding_source_contents.py -v -s -o addopts=""
"""
import os
import re
import time

import pytest

from utils.genuser_api import SEEDED_PWD, call, gen_create, mint

pytestmark = pytest.mark.value_api

# Deterministic seed values for the funding source the test renders.
SEED_BANK_NAME = "Commonwealth Bank"
SEED_LAST_4 = "4321"

# Placeholder / format tokens that mean "the value never resolved" — the real defect.
_PLACEHOLDER_TOKENS = {"", "%s", "%1$s", "%2$s", "%d", "{0}", "{1}", "null", "nil",
                       "none", "n/a", "na", "-", "—", "--", "()", "( )"}
_FORMAT_TOKEN_RE = re.compile(r"%[0-9]*\$?[sdf@]|\{\d+\}")  # printf / java MessageFormat tokens
# The masked account tail the UI shows inside "(...)" — a non-empty run of digits.
_MASK_TAIL_RE = re.compile(r"^\d{2,}$")


def _ts():
    # PID-qualified timestamp: avoid same-second email collisions when the suite
    # runs across the parallel multi-emulator rig / reruns (each worker is a
    # distinct process). Mirrors test_auth_account_states_api.py:106.
    return f"{int(time.time())}.{os.getpid()}"


def _funded_user(email, first):
    return {
        "model": "user",
        "traits": ["has_portfolio", "with_user_profile", "funded", "verified", "with_active_plan"],
        "attributes": {
            "email": email, "password": SEEDED_PWD, "skip_sending_welcome_email": True,
            "portfolio_name": "Aggressive", "plan_identifier": "regular",
            "profile_data": {"first_name": first, "last_name": "QA",
                             "date_of_birth": "1990-01-01", "phone_number": "0412345678"},
        },
    }


def _is_placeholder(value):
    """True when a string is empty / a known sentinel / a printf|MessageFormat token —
    i.e. a value the UI would render as a hollow or garbage destination."""
    if value is None:
        return True
    s = str(value).strip()
    if s.lower() in _PLACEHOLDER_TOKENS:
        return True
    if _FORMAT_TOKEN_RE.search(s):
        return True
    return False


def _seed_user_with_funding(name=SEED_BANK_NAME, last_4=SEED_LAST_4):
    """Seed a fresh funded user whose ACH funding source carries a real bank name + last_4.

    Mirrors the rabl wiring: funding.name == funding_source.yodlee_monitored_site.site_name
    and funding.last_4 == funding_source.last_4. So we create a funding_source with the
    last_4 set AND a yodlee_monitored_site (for_funding) linked to that funding_source by
    reference (the model reads YodleeMonitoredSite where funding_source_id == fs.id).
    Returns (email, created_body).
    """
    ts = _ts()
    email = f"fund.contents.{ts}@emel.xyz"
    payload = {
        "user_1": _funded_user(email, f"FundContents{ts}"),
        "fs_1": {
            "model": "funding_source",
            "traits": ["admin_linked", "with_bank"],
            "attributes": {"user": "@user_1", "fund_type": "ACH",
                           "last_4": last_4, "status": "success"},
        },
        "yms_1": {
            "model": "yodlee_monitored_site",
            "traits": ["for_funding"],
            "attributes": {"user": "@user_1", "funding_source": "@fs_1", "site_name": name},
        },
    }
    status, body = gen_create(payload)
    assert status == 200, f"funding-source seed failed: HTTP {status} {body}"
    assert body.get("created", {}).get("fs_1", {}).get("id"), f"no funding_source id: {body}"
    assert body.get("created", {}).get("yms_1", {}).get("id"), f"no yodlee site id: {body}"
    return email, body


def _get_funding(email):
    """Log in as the seeded user and return the GET /v1/accounts `funding` object — the
    exact JSON the app turns into the destination string. Returns (funding_dict, full)."""
    op, tok = mint(email, SEEDED_PWD)
    assert tok, f"GATE: could not log in as seeded user {email}"
    status, body = call(op, "GET", "/v1/accounts", token=tok)
    assert status == 200, f"/v1/accounts HTTP {status}: {body}"
    funding = body.get("funding") if isinstance(body, dict) else None
    return funding, body


def test_funding_source_renders_real_bank_name_and_masked_account():
    """The funding destination the app renders ("<name> (<last_4>)") must carry REAL
    values: a non-empty non-placeholder bank name and a digit-mask account tail — never
    null/blank/'%s'. Seeds a fresh ACH funding source per run (dynamic) because the static
    funded fixture returns null name+last_4 (a blank destination, the defect under test)."""
    email, created = _seed_user_with_funding()
    print(f"  seeded user {created['created']['user_1']['id']} ({email}) "
          f"fs={created['created']['fs_1']['id']} yms={created['created']['yms_1']['id']}")

    funding, full = _get_funding(email)
    assert funding is not None, (
        f"/v1/accounts returned no `funding` block (funding?('ach') false) — "
        f"the app would route to 'connect funding' and show no destination. full={full}")
    print(f"  funding block: {funding}")

    # --- the app only emits the funding block for ACH; confirm the type wiring ---
    assert funding.get("funding_type") == "ACH", \
        f"funding_type must be ACH (the seeded ACH source), got {funding.get('funding_type')!r}"

    # --- bank NAME: non-empty, non-placeholder, no format token ---
    name = funding.get("name")
    assert not _is_placeholder(name), (
        f"funding.name renders as a blank/placeholder destination ({name!r}) — "
        f"the customer would see a hollow bank name. This is the defect under test.")
    assert name.strip() == SEED_BANK_NAME, \
        f"funding.name should echo the seeded bank name {SEED_BANK_NAME!r}, got {name!r}"

    # --- ACCOUNT id MASK: the tail the UI shows inside '(...)' — non-empty digits, no token ---
    last_4 = funding.get("last_4")
    assert not _is_placeholder(last_4), (
        f"funding.last_4 renders as a blank/placeholder ({last_4!r}) — the customer "
        f"would see '()' with no account mask. This is the defect under test.")
    assert _MASK_TAIL_RE.match(str(last_4).strip()), (
        f"funding.last_4 {last_4!r} is not a digit-mask tail (mask chars + trailing digits) "
        f"— the app wraps it as '(...)' so it must be a clean numeric tail.")
    assert str(last_4).strip() == SEED_LAST_4, \
        f"funding.last_4 should echo the seeded tail {SEED_LAST_4!r}, got {last_4!r}"

    # --- reconstruct the EXACT on-screen destination string the app builds ---
    rendered = f"{(name or '').strip()} ({(str(last_4) or '').strip()})".strip()
    expected = f"{SEED_BANK_NAME} ({SEED_LAST_4})"
    assert rendered == expected, f"rendered destination {rendered!r} != expected {expected!r}"
    assert "%s" not in rendered and not _FORMAT_TOKEN_RE.search(rendered) and "()" not in rendered.replace(f"({SEED_LAST_4})", ""), \
        f"destination string {rendered!r} contains a placeholder/hollow segment"
    print(f"  PASS: destination renders real values -> {rendered!r}")


def test_funding_block_is_single_ach_withdraw_destination():
    """OPTIONAL SECONDARY (withdraw-destination tie, STATE not enforcement): the linked
    ACH funding source is also the withdrawal destination in Raiz. Assert STATE — there is
    exactly one funding block, it is ACH, and it carries the same real name+mask the deposit
    destination renders — so the withdrawal destination is not a separate/blank string."""
    email, created = _seed_user_with_funding()
    print(f"  seeded user {created['created']['user_1']['id']} ({email})")

    funding, full = _get_funding(email)
    assert funding is not None, f"no funding block to act as withdraw destination: {full}"

    # /v1/accounts exposes a SINGLE `funding` object (UserAccountsResponse.fundingAccount is
    # a single nullable object, not a list) — i.e. deposits AND withdrawals share one ACH
    # destination. Assert it is that single ACH block with the same rendered contents.
    assert isinstance(full.get("funding"), dict), \
        f"expected a single funding object (one ACH destination), got {type(full.get('funding'))}"
    assert funding.get("funding_type") == "ACH", \
        f"the single funding/withdraw destination must be ACH, got {funding.get('funding_type')!r}"
    assert not _is_placeholder(funding.get("name")), \
        f"withdraw destination bank name is blank/placeholder ({funding.get('name')!r})"
    assert not _is_placeholder(funding.get("last_4")), \
        f"withdraw destination account mask is blank/placeholder ({funding.get('last_4')!r})"
    assert funding.get("name").strip() == SEED_BANK_NAME and str(funding.get("last_4")).strip() == SEED_LAST_4, (
        f"withdraw destination contents drift from the seeded funding source: "
        f"{funding.get('name')!r}/{funding.get('last_4')!r}")
    print(f"  PASS: single ACH destination doubles as the withdraw destination -> "
          f"{funding.get('name')} ({funding.get('last_4')})")
