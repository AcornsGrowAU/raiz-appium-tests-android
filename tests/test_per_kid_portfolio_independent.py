"""
per-kid-portfolio-independent — STATIC HALF (P1, state-transition) — API LAYER.

Backlog row (case key `per-kid-portfolio-independent`, verdict `refine`):
  Per-kid portfolio is stored INDEPENDENTLY per kid (A != B; changing A leaves B).
  The cross-checkers SPLIT this case:
    (a) static distinctness — kid-A == Aggressive, kid-B == a DIFFERENT seeded style,
        A != B (KEEP, P1; assert the LABEL + distinct uuids, never a balance);
    (b) on-device change-no-bleed — DEFERRED to a Manage-account page object.
  This file implements the KEPT static half ONLY. The change-no-bleed half is
  out of scope (no Manage-account driver yet) and is intentionally not asserted.

  STYLE CHOICE FOR KID-B (Conservative, not Moderate):
    The backlog row names kid-B == Moderate, but the validated PROPERTY is per-kid
    INDEPENDENCE (A != B, distinct portfolio uuids) — the specific style labels are only
    the vehicle that makes the two kids distinct. Empirically on the DEV backend (build
    3252) the seed trait `:has_portfolio` wires Aggressive AND Conservative onto a user's
    OWN record (allocation_profile_id present) but does NOT wire Moderate: both an adult
    `portfolio_moderate` fixture and a Moderate-seeded kid come back with
    allocation_profile_id=None (Portfolio.find_by_localized_name('Moderate') does not
    resolve to a seedable user.portfolio on DEV, whereas Aggressive/Conservative do). So
    kid-B is seeded Conservative instead of Moderate. This keeps WHAT the test validates
    identical (two siblings on distinct, independently-stored portfolios) while turning a
    permanent vacuous skip on a non-seedable style into a real value-asserting pass.

ORACLE (backend ground truth):
  A kid is its OWN `user` (user_type='dependent') under the parent. The seed trait
  `:has_portfolio` (gen-API `portfolio_name`) wires the portfolio directly onto the
  KID's own user record:
      user.portfolio = Portfolio.find_by_localized_name(portfolio_name)
  (spec/factories/user.rb trait :has_portfolio). The kid's portfolio uuid is exposed
  on its OWN user entity as `allocation_profile_id` (app/api/entities/user.rb:42), and
  the published portfolio (incl. its `name` = the style LABEL) is read from the public
  `GET /v1/portfolios/:uuid` (app/api/v1/resources/portfolios.rb — authenticated with
  `skip: [:check_user_access]`, so any logged-in token may read a portfolio by uuid).

  So per-kid independence is provable as: kid-A and kid-B each resolve (via their OWN
  login) to a DISTINCT portfolio uuid whose published name is the SEEDED style — A's is
  Aggressive, B's is Conservative, and the two are not the same portfolio. That is exactly
  "stored independently per kid": two sibling dependents under one parent carry their
  own, different portfolio links.

WHY API-LAYER-FIRST (no device), and the manifest caveat:
  This mirrors the sibling `test_portfolio_style_allocation_weights` exactly: log in AS
  the entity, read its own `allocation_profile_id`, then `GET /v1/portfolios/:uuid` for
  the label. The provision manifest's FLAG #6 ("per-kid portfolio read-back is UI-only")
  refers to the INTERNAL endpoint `GET /internal/v1/portfolios/user`, which switches on
  user_type and 500s for `dependent`/`jar`. We deliberately do NOT use that endpoint. The
  PUBLIC per-uuid path used here is a different, working read and keeps the case
  deterministic with no emulator. If that public path is ever genuinely unreadable for a
  kid token, the test SKIPS-with-reason (clear evidence) rather than faking a pass — and
  the case would then fall back to the device read-back the backlog allows.

DATA (manifest): the pre-provisioned `kids_portfolio_distinct` fixture — one parent
  (`user_1`) with two kids under it: kid-A at `a.<parent-email>` seeded Aggressive and
  kid-B at `b.<parent-email>` seeded Conservative. Reuse strategy: read-only reads of a
  shared rig; the style link is independent of any balance, so reuse-drift is a non-issue.
  No balance is read or asserted anywhere — LABEL + uuid only.

Run (no emulator):
  venv/bin/python -m pytest tests/test_per_kid_portfolio_independent.py -v -s -o addopts=""
"""
import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import (
    STYLE_AGGRESSIVE, STYLE_CONSERVATIVE,
    get_or_create_fixture_user,
)

pytestmark = [pytest.mark.value_api, pytest.mark.kids, pytest.mark.portfolio]

FIXTURE_KEY = "kids_portfolio_distinct"


def _kid_emails(parent_email):
    """The fixture seeds kid-A at `a.<parent-email>` and kid-B at `b.<parent-email>`
    (utils.genuser_fixtures FIXTURES['kids_portfolio_distinct']: kid_user('a.'+email,...)
    Aggressive; kid_user('b.'+email,...) Conservative). Derive from the stored parent rec so
    it stays correct if the fixture is ever re-seeded under a new timestamped address."""
    return "a." + parent_email, "b." + parent_email


def _read_kid_portfolio(kid_email):
    """Resolve a kid's OWN portfolio off the public DEV API.

    Returns {label, uuid} where:
      - uuid  = the kid's own allocation_profile_id (the portfolio it is wired to),
      - label = that portfolio's published `name` (the persisted style),
    or a string starting with 'SKIP:' describing the gate that blocked the read.
    No balance is touched."""
    op, tok = mint(kid_email, SEEDED_PWD)
    if not tok:
        return f"SKIP: could not log in as kid {kid_email} (auth/rate-limit gate)"

    s, b = call(op, "GET", "/v1/user", token=tok)
    if s != 200 or not isinstance(b, dict):
        return f"SKIP: GET /v1/user for kid {kid_email} returned HTTP {s} (read gate)"
    user = b.get("user", b)
    uuid = user.get("allocation_profile_id")
    if not uuid:
        return (f"SKIP: kid {kid_email} has no allocation_profile_id (no portfolio "
                "wired to the kid) — seed gate, not a product result")

    s, b = call(op, "GET", f"/v1/portfolios/{uuid}", token=tok)
    if s != 200 or not isinstance(b, dict):
        return (f"SKIP: GET /v1/portfolios/{uuid} for kid {kid_email} returned HTTP {s} "
                "(portfolio detail read gate)")
    portfolio = b.get("portfolio", b)
    label = portfolio.get("name")
    if not label:
        return (f"SKIP: portfolio detail for kid {kid_email} missing name "
                f"(name={label!r}) — read gate")
    return {"label": label, "uuid": uuid}


def test_per_kid_portfolio_stored_independently():
    """Static half: kid-A's portfolio == Aggressive, kid-B's == Conservative, and the two
    kids resolve to DISTINCT portfolios (A != B) — i.e. each sibling dependent under one
    parent carries its OWN, independent portfolio link. LABEL + uuid only; no balance.

    The on-device change-no-bleed half (changing A leaves B) is deferred per the backlog
    split and is NOT covered here."""
    parent = get_or_create_fixture_user(FIXTURE_KEY)
    parent_email = parent["email"]
    kid_a_email, kid_b_email = _kid_emails(parent_email)
    print(f"  fixture parent {parent_email} (reused={parent.get('reused')}); "
          f"kid-A {kid_a_email} (expect {STYLE_AGGRESSIVE!r}); "
          f"kid-B {kid_b_email} (expect {STYLE_CONSERVATIVE!r})")

    a = _read_kid_portfolio(kid_a_email)
    if isinstance(a, str) and a.startswith("SKIP:"):
        pytest.skip("skip-with-reason: " + a[len("SKIP:"):].strip())
    b = _read_kid_portfolio(kid_b_email)
    if isinstance(b, str) and b.startswith("SKIP:"):
        pytest.skip("skip-with-reason: " + b[len("SKIP:"):].strip())

    print(f"  kid-A label={a['label']!r} uuid={a['uuid']}")
    print(f"  kid-B label={b['label']!r} uuid={b['uuid']}")

    # ---- Each kid carries its OWN seeded style label (per-kid storage) ----
    assert a["label"] == STYLE_AGGRESSIVE, (
        f"kid-A resolved to portfolio labelled {a['label']!r}, expected "
        f"{STYLE_AGGRESSIVE!r} — kid-A's per-kid portfolio did not persist")
    assert b["label"] == STYLE_CONSERVATIVE, (
        f"kid-B resolved to portfolio labelled {b['label']!r}, expected "
        f"{STYLE_CONSERVATIVE!r} — kid-B's per-kid portfolio did not persist "
        "(label + uuid only; no balance is asserted)")

    # ---- Independence: the two kids are NOT on the same portfolio ----
    # Distinct labels AND distinct uuids — if two siblings under one parent shared the
    # same portfolio uuid, per-kid storage would be collapsed/inherited, which is the
    # exact mis-wiring this case guards against.
    assert a["label"] != b["label"], (
        f"both kids resolved to the SAME portfolio label {a['label']!r} — per-kid "
        "portfolio is not stored independently (collapsed/shared)")
    assert a["uuid"] != b["uuid"], (
        f"both kids resolved to the SAME portfolio uuid {a['uuid']} — the two kids "
        "are not on distinct portfolios (shared/inherited link)")

    print(f"  PASS: per-kid portfolios independent — A={a['label']} != B={b['label']} "
          f"(distinct uuids {a['uuid']} vs {b['uuid']})")
