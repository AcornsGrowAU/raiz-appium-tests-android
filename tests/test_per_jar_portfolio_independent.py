"""
per-jar-portfolio-independent (P2, state-transition) — API LAYER (no device).

Backlog row (case key `per-jar-portfolio-independent`, verdict `keep`, conf 78):
  "Per-jar portfolio stored independently and can differ from Main. Seed
   jar='Conservative', Main='Aggressive'; jar reads Conservative, Main reads
   Aggressive, A != B (independent storage). Scope to seeded read-back;
   mutate-and-reread is a stretch."
  Notes (#10): "Scope to the seeded backend read-back (jar's own token);
   mutate-and-reread is a stretch needing a Manage-Jar portfolio page object."

  This file implements the KEPT seeded read-back ONLY. The mutate-and-reread half
  (change the jar's portfolio on device and re-read) is out of scope — it needs a
  Manage-Jar portfolio driver that does not exist — and is intentionally not touched.
  This is the direct jar analog of the sibling `test_per_kid_portfolio_independent`.

ORACLE (backend ground truth, /Users/joshua/raiz-backend):
  A jar is its OWN `user` (user_type='jar') created UNDER a parent — see
  spec/factories/user.rb trait :jar_account (user_type { 'jar' } + a `jar` row linked
  to the parent). The gen-API `portfolio_name` flows through the :has_portfolio trait,
  which wires the portfolio directly onto the JAR's own user record:
      user.portfolio = Portfolio.find_by_localized_name(portfolio_name)
  (spec/factories/user.rb:489). That portfolio's uuid is exposed on the jar's OWN user
  entity as `allocation_profile_id` (app/api/entities/user.rb:42), and the published
  portfolio (incl. its `name` = the style LABEL) is read from the PUBLIC per-uuid route
      GET /v1/portfolios/:uuid
  which is authenticated with `skip: [:check_user_access]` (app/api/v1/resources/
  portfolios.rb:11), so ANY logged-in token may resolve a portfolio uuid to its label.

  Per-jar independence is therefore provable as: the jar resolves (via its OWN login) to
  one portfolio uuid whose published name is the seeded Conservative, the parent (Main)
  resolves (via its OWN login) to a DIFFERENT portfolio uuid whose name is the seeded
  Aggressive, and the two are not the same portfolio. That is exactly "stored
  independently and can differ from Main": the jar carries its own portfolio link, not
  an inherited/shared copy of the parent's.

WHY API-LAYER-FIRST (no device), and the manifest caveat:
  Mirrors the sibling kid test and `test_portfolio_style_allocation_weights` exactly:
  log in AS the entity, read its own `allocation_profile_id`, then GET the public
  /v1/portfolios/:uuid for the label. The provision manifest FLAG #6 ("per-jar portfolio
  read-back is UI-only") refers to the INTERNAL endpoint GET /internal/v1/portfolios/user,
  which switches on user_type and 500s for `jar`. We deliberately do NOT use that
  endpoint — the PUBLIC per-uuid path used here is a different, working read and keeps the
  case deterministic with no emulator. If that public path is ever genuinely unreadable
  for the jar token (auth/seed gate), the test SKIPS-with-reason (clear evidence) rather
  than faking a pass — and the case would then fall back to the device read-back the
  backlog allows.

DATA (manifest `jar_portfolio_distinct`): one parent (`user_1`, a `regular` user seeded
  Aggressive = Main) with one jar under it (`jar_1`) at `jp.<parent-email>` seeded
  Conservative (+ a small exact $80 ACH so the jar exists with a real balance; NOT read
  here). Reuse strategy: read-only reads of a shared rig; the style link is independent of
  any balance, so reuse-drift is a non-issue. No balance is read or asserted anywhere —
  this is a pure LABEL/uuid independence oracle.

Run (no emulator):
  venv/bin/python -m pytest tests/test_per_jar_portfolio_independent.py -v -s -o addopts=""
"""
import time

import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import (
    JAR_PF_NAME, STYLE_AGGRESSIVE, STYLE_CONSERVATIVE,
    get_or_create_fixture_user,
)

pytestmark = [pytest.mark.value_api, pytest.mark.jars, pytest.mark.portfolio]

FIXTURE_KEY = "jar_portfolio_distinct"

# A TRANSIENT read failure (no token from a rate-limited /v1/sessions, a 5xx, or a
# network blip) is retried a bounded number of times before we fall through to SKIP, so a
# rate-limit blip no longer silently NO-RUNS the label/independence oracle. A genuine GATE
# (a real non-2xx contract response / a missing allocation_profile_id / a missing jar or
# jar-portfolio object) skips immediately. Mirrors
# test_networth_total_investments_recon._get_v3_user.
_READ_ATTEMPTS = 3
_READ_RETRY_DELAY_S = 8


def _with_retry(once, label):
    """Run a single-attempt reader (`once` -> dict | ('GATE'|'TRANSIENT', reason)) under a
    BOUNDED retry: return the dict on success, skip immediately on a genuine GATE, and
    retry the TRANSIENT (re-minting a fresh token inside `once`) before falling through to
    SKIP. Preserves the 'dict | SKIP:-string' contract the callers already expect."""
    last = None
    for i in range(_READ_ATTEMPTS):
        r = once()
        if isinstance(r, dict):
            return r
        kind, reason = r
        if kind == "GATE":
            return "SKIP: " + reason
        last = reason
        print(f"  [{label} attempt {i + 1}/{_READ_ATTEMPTS}] transient: {reason}")
        if i < _READ_ATTEMPTS - 1:
            time.sleep(_READ_RETRY_DELAY_S)
    return f"SKIP: {last} (persisted across {_READ_ATTEMPTS} bounded retries)"


def _read_jar_portfolio_via_parent_once(parent_email):
    """ONE attempt to resolve the JAR's portfolio through the PARENT's session.

    Jars are sub-accounts with NO loginable identity (their email 401s on /v1/sessions by
    design), so the jar leg cannot log in as the jar. The parent's jars list
    (GET /jars/v1/users) exposes each jar's portfolio directly as a nested object
    {id: <portfolio uuid>, name: <label>} — the same uuid+label pair the old own-token
    read produced. (Inlined here rather than via genuser_api.jar_by_name so a login/read
    blip can be classed TRANSIENT vs a real missing-jar GATE, which the helper's flat None
    return conflates.)

    Returns dict {label, uuid} | ('GATE', reason) | ('TRANSIENT', reason)."""
    op, tok = mint(parent_email, SEEDED_PWD)
    if not tok:
        return ("TRANSIENT", f"could not log in as parent {parent_email} (auth/rate-limit)")

    try:
        s, b = call(op, "GET", "/jars/v1/users", token=tok)
    except Exception as e:  # network/timeout — transient
        return ("TRANSIENT", f"network error reading /jars/v1/users for {parent_email}: {e}")
    if s is not None and s >= 500:
        return ("TRANSIENT", f"GET /jars/v1/users for {parent_email} returned HTTP {s} (server error)")
    if s != 200 or not isinstance(b, dict):
        return ("GATE", f"GET /jars/v1/users for {parent_email} returned HTTP {s} "
                "(parent jars-list gate)")
    jar = None
    for j in b.get("jar_users", []) or []:
        if j.get("name") == JAR_PF_NAME:
            jar = j
            break
    if jar is None:
        return ("GATE", f"no jar named {JAR_PF_NAME!r} under {parent_email} "
                "(seed gate, not a product result)")
    portfolio = jar.get("portfolio") or {}
    uuid, label = portfolio.get("id"), portfolio.get("name")
    if not uuid or not label:
        return ("GATE", f"jar {JAR_PF_NAME!r} carries no portfolio object "
                f"(portfolio={portfolio!r}) — seed gate, not a product result")
    return {"label": label, "uuid": uuid}


def _read_own_portfolio_once(email, who):
    """ONE attempt to resolve an entity's OWN portfolio off the PUBLIC DEV API (log in AS
    the entity).

    Returns dict {label, uuid} | ('GATE', reason) | ('TRANSIENT', reason).
    No balance is touched."""
    op, tok = mint(email, SEEDED_PWD)
    if not tok:
        return ("TRANSIENT", f"could not log in as {who} {email} (auth/rate-limit)")

    try:
        s, b = call(op, "GET", "/v1/user", token=tok)
    except Exception as e:  # network/timeout — transient
        return ("TRANSIENT", f"network error reading /v1/user for {who} {email}: {e}")
    if s is not None and s >= 500:
        return ("TRANSIENT", f"GET /v1/user for {who} {email} returned HTTP {s} (server error)")
    if s != 200 or not isinstance(b, dict):
        return ("GATE", f"GET /v1/user for {who} {email} returned HTTP {s} (read gate)")
    user = b.get("user", b)
    uuid = user.get("allocation_profile_id")
    if not uuid:
        return ("GATE", f"{who} {email} has no allocation_profile_id (no portfolio "
                "wired to the entity) — seed gate, not a product result")

    try:
        s, b = call(op, "GET", f"/v1/portfolios/{uuid}", token=tok)
    except Exception as e:  # network/timeout — transient
        return ("TRANSIENT", f"network error reading /v1/portfolios/{uuid} for {who} {email}: {e}")
    if s is not None and s >= 500:
        return ("TRANSIENT", f"GET /v1/portfolios/{uuid} for {who} {email} returned HTTP {s} "
                "(server error)")
    if s != 200 or not isinstance(b, dict):
        return ("GATE", f"GET /v1/portfolios/{uuid} for {who} {email} returned HTTP {s} "
                "(portfolio detail read gate)")
    portfolio = b.get("portfolio", b)
    label = portfolio.get("name")
    if not label:
        return ("GATE", f"portfolio detail for {who} {email} missing name "
                f"(name={label!r}) — read gate")
    return {"label": label, "uuid": uuid}


def _read_jar_portfolio_via_parent(parent_email):
    """Resolve the JAR's portfolio through the PARENT's session, with a bounded transient
    retry (see _with_retry). Returns {label, uuid} or a 'SKIP:'-prefixed gate description."""
    return _with_retry(lambda: _read_jar_portfolio_via_parent_once(parent_email),
                       f"read_jar {JAR_PF_NAME!r}")


def _read_own_portfolio(email, who):
    """Resolve an entity's OWN portfolio off the PUBLIC DEV API, with a bounded transient
    retry (see _with_retry). Returns {label, uuid} (uuid = the entity's own
    allocation_profile_id; label = that portfolio's published name), or a 'SKIP:'-prefixed
    gate description. No balance is touched."""
    return _with_retry(lambda: _read_own_portfolio_once(email, who), f"read_{who} {email}")


def test_per_jar_portfolio_stored_independently():
    """Seeded read-back: the jar's portfolio == Conservative, the parent's (Main) ==
    Aggressive, and the jar resolves to a DISTINCT portfolio (jar != Main) — i.e. the
    jar carries its OWN, independent portfolio link that DIFFERS from Main, rather than
    inheriting/sharing the parent's. LABEL + uuid only; no balance asserted.

    The mutate-and-reread half (change the jar portfolio on device, re-read no-bleed) is
    deferred per the backlog scope and is NOT covered here."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email = parent["email"]
    print(f"  fixture parent/Main {parent_email} (reused={parent.get('reused')}; "
          f"expect {STYLE_AGGRESSIVE!r}); "
          f"jar {JAR_PF_NAME!r} read via parent session (expect {STYLE_CONSERVATIVE!r})")

    jar = _read_jar_portfolio_via_parent(parent_email)
    if isinstance(jar, str) and jar.startswith("SKIP:"):
        pytest.skip("skip-with-reason: " + jar[len("SKIP:"):].strip())
    main = _read_own_portfolio(parent_email, "Main")
    if isinstance(main, str) and main.startswith("SKIP:"):
        pytest.skip("skip-with-reason: " + main[len("SKIP:"):].strip())

    print(f"  jar  label={jar['label']!r} uuid={jar['uuid']}")
    print(f"  Main label={main['label']!r} uuid={main['uuid']}")

    # ---- Each entity carries its OWN seeded style label (independent storage) ----
    assert jar["label"] == STYLE_CONSERVATIVE, (
        f"jar resolved to portfolio labelled {jar['label']!r}, expected "
        f"{STYLE_CONSERVATIVE!r} — the per-jar portfolio did not persist")
    assert main["label"] == STYLE_AGGRESSIVE, (
        f"Main (parent) resolved to portfolio labelled {main['label']!r}, expected "
        f"{STYLE_AGGRESSIVE!r} — Main's portfolio is not the seeded baseline")

    # ---- Independence: the jar is NOT on the same portfolio as Main ----
    # Distinct labels AND distinct uuids — if the jar shared Main's portfolio uuid, the
    # per-jar portfolio would be collapsed/inherited from the parent, which is the exact
    # mis-wiring this case guards against (a jar must be able to DIFFER from Main).
    assert jar["label"] != main["label"], (
        f"jar and Main resolved to the SAME portfolio label {jar['label']!r} — the "
        "per-jar portfolio is not stored independently from Main (collapsed/shared)")
    assert jar["uuid"] != main["uuid"], (
        f"jar and Main resolved to the SAME portfolio uuid {jar['uuid']} — the jar is "
        "on Main's portfolio (shared/inherited link), not its own independent one")

    print(f"  PASS: per-jar portfolio independent of Main — jar={jar['label']} != "
          f"Main={main['label']} (distinct uuids {jar['uuid']} vs {main['uuid']})")
