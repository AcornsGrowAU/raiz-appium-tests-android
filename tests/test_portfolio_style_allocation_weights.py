"""
portfolio-style-allocation-weights (P0, core-investing) — API LAYER.

Oracle (backlog row + notes, case key `portfolio-style-allocation-weights`):
  Per-style user: the published allocation MIX differs by risk level (Aggressive vs
  Conservative are NOT the same row-set), each style's weights SUM to 100 (+-0.5), and
  the per-user portfolio LABEL persists across views. The notes explicitly say: use the
  *robust core* (differ + sum-to-100 + label-persists) with a tolerance, do NOT
  hard-code the exact published %s (the published mix can be re-tuned), and DROP
  UNPROVEN SUB-CLAUSES / skip-with-reason where the data is non-seedable.

Why API-layer-first (per the notes + manifest):
  The allocation mix is BACKEND GROUND TRUTH. A portfolio's weights live on
  Portfolio#fund_ratios (each FundRatio.ratio is a whole-number PERCENT); the user is
  wired to ONE portfolio via has_one :portfolio, through: :user_portfolio
  (User#allocation_profile_id == current_user.portfolio.uuid). So the whole oracle is
  provable deterministically off the DEV API with no emulator:

    1. mint() as the seeded style user.
    2. GET /v1/user             -> `allocation_profile_id` (the portfolio uuid the user
                                   is actually on) — the per-user LABEL link.
    3. GET /v1/portfolios/:uuid -> { portfolio: { name, ratios:[{symbol, ratio, ...}],
                                   etfs:[{symbol, percent, ...}] } } — the published mix
                                   + the portfolio's own name.

  Mix source = the `ratios[].ratio` values (FundRatio.ratio, the documented whole-number
  percent that the backend rabl exposes — verified to sum to exactly 100.0). The same
  response ALSO carries `etfs[].percent`, but those are the SAME weights expressed as a
  FRACTION (0.54, not 54.0) which sum to ~1.0, not 100 — so `_mix()` normalises: it
  reads `ratios` first and falls back to `etfs[].percent`, scaling a fractional set up
  to percent so the sum-to-100 oracle is correct regardless of which shape is present.

  Label-persists-across-views (API form): the SAME portfolio is reached from the user
  object (allocation_profile_id) AND names itself the seeded style on the portfolio
  detail — i.e. the per-user style label is stable across the two reads, not a transient
  echo of the seed payload.

Fixtures (manifest):
  portfolio_aggressive / portfolio_conservative — two standalone `regular`-plan users,
  each seeded on a distinct portfolio_name (Aggressive / Conservative). These two are the
  ROBUST CORE and are ALWAYS asserted. portfolio_moderate is an OPTIONAL third style:
  on the DEV backend the gen API does NOT wire a `user_portfolio` for the Moderate (or
  Moderately Conservative) portfolio — a fresh Moderate user comes back with
  allocation_profile_id == None — so Moderate's label/sum checks are added ONLY when it
  is actually wired and are skipped with a clear seed-gate reason otherwise. That seed
  gate does NOT block the provable Aggressive-vs-Conservative core. (Reuse strategy:
  read-only reads of a shared rig; the published mix is independent of any balance.)

Determinism / honesty:
  - Tolerances only (sum 100 +-0.5; differ = set inequality) — no exact published %s.
  - No balance is read or asserted anywhere (mix is balance-free).
  - A login/read gate on the CORE styles -> skip-with-reason (clear evidence). A missing
    Moderate portfolio wiring -> the Moderate sub-clause is skipped, the core still runs.
  - If the published mix ever genuinely fails to sum to 100 or Aggressive==Conservative,
    that is a REAL product/data defect and the test fails (the point of the oracle).

Run (no emulator):
  venv/bin/python -m pytest tests/test_portfolio_style_allocation_weights.py -v -s -o addopts=""
"""
import pytest

from utils.genuser_api import SEEDED_PWD, call, mint
from utils.genuser_fixtures import (
    STYLE_AGGRESSIVE, STYLE_CONSERVATIVE, STYLE_MODERATE,
    get_or_create_fixture_user,
)

pytestmark = pytest.mark.value_api

# Each published portfolio's weights must sum to 100%. Backend FundRatio.ratio values
# are whole-number percents; tiny rounding across a handful of ETFs is expected, so
# allow +-0.5.
SUM_TARGET = 100.0
SUM_TOL = 0.5

# (fixture key, expected seeded style label, required?)
# Aggressive + Conservative are the provable core (always asserted). Moderate is an
# OPTIONAL third style: the DEV gen API does not wire a portfolio for it, so it is
# included only when actually present and skipped (sub-clause only) otherwise.
STYLE_AGGRESSIVE_KEY = "portfolio_aggressive"
STYLE_CONSERVATIVE_KEY = "portfolio_conservative"
STYLE_MODERATE_KEY = "portfolio_moderate"
CORE_STYLES = [
    (STYLE_AGGRESSIVE_KEY, STYLE_AGGRESSIVE),
    (STYLE_CONSERVATIVE_KEY, STYLE_CONSERVATIVE),
]


def _mix(portfolio):
    """Return {symbol: percent} normalised to WHOLE-NUMBER percents (so a mix sums to
    ~100), or None if no usable weight rows are present.

    Prefers `ratios[].ratio` (FundRatio.ratio, the documented whole percent the backend
    exposes). Falls back to `etfs[].percent`, which carries the SAME weights as a
    fraction (0.54 not 54.0); if that fallback set sums to ~1 it is scaled up to percent
    so the sum-to-100 oracle holds regardless of which API shape is present."""
    rows = portfolio.get("ratios")
    weight_key = "ratio"
    if not rows:
        rows = portfolio.get("etfs")
        weight_key = "percent"
    if not rows:
        return None

    mix = {}
    for r in rows:
        sym = r.get("symbol") or r.get("etf_name")
        w = r.get(weight_key)
        if sym is None or w is None:
            return None
        mix[str(sym)] = float(w)
    if not mix:
        return None

    total = sum(mix.values())
    # If the values came back as fractions (sum ~1), scale to whole-number percent.
    if 0.5 < total < 1.5:
        mix = {k: v * 100.0 for k, v in mix.items()}
    return {k: round(v, 4) for k, v in mix.items()}


def _read_style(fixture_key):
    """Resolve a seeded style user's ACTUAL portfolio off the DEV API.

    Returns a dict {label, mix, uuid} where:
      - label = the portfolio's own name on the detail endpoint (the persisted style),
      - mix   = {symbol: percent} (whole-number percents; see _mix),
      - uuid  = the user's allocation_profile_id (the portfolio it is wired to),
    or a string starting with 'SKIP:' describing the gate that blocked the read."""
    rec = get_or_create_fixture_user(fixture_key)
    email = rec["email"]

    op, tok = mint(email, SEEDED_PWD)
    if not tok:
        return f"SKIP: could not log in as {fixture_key} ({email}) (auth/rate-limit gate)"

    s, b = call(op, "GET", "/v1/user", token=tok)
    if s != 200 or not isinstance(b, dict):
        return f"SKIP: GET /v1/user for {fixture_key} returned HTTP {s} (read gate)"
    user = b.get("user", b)
    uuid = user.get("allocation_profile_id")
    if not uuid:
        return (f"SKIP: {fixture_key} has no allocation_profile_id (no portfolio wired "
                "to the user) — seed gate, not a product result")

    s, b = call(op, "GET", f"/v1/portfolios/{uuid}", token=tok)
    if s != 200 or not isinstance(b, dict):
        return (f"SKIP: GET /v1/portfolios/{uuid} for {fixture_key} returned HTTP {s} "
                "(portfolio detail read gate)")
    portfolio = b.get("portfolio", b)
    label = portfolio.get("name")
    mix = _mix(portfolio)
    if not label or not mix:
        return (f"SKIP: portfolio detail for {fixture_key} missing name/weights "
                f"(name={label!r}, rows={0 if not mix else len(mix)}) — read gate")
    return {"label": label, "mix": mix, "uuid": uuid}


def _sum(mix):
    return round(sum(mix.values()), 4)


def _assert_sums_to_100(r):
    total = _sum(r["mix"])
    assert abs(total - SUM_TARGET) <= SUM_TOL, (
        f"{r['label']} published allocation sums to {total}%, expected "
        f"{SUM_TARGET}% +-{SUM_TOL} — weights do not add up")


def test_portfolio_style_allocation_weights():
    """Per-style published allocation differs by risk level, each sums to 100 (+-0.5),
    and each user's portfolio LABEL persists (resolves to the seeded style across the
    user object and the portfolio detail). API-layer, deterministic, no device.

    Aggressive + Conservative are the provable core and are always asserted. Moderate is
    asserted ONLY if its portfolio is wired on DEV; otherwise just that sub-clause is
    skipped (the core still runs)."""
    # ---- CORE: Aggressive + Conservative (required; a read gate here skips the test) ----
    core = {}
    for key, expected_label in CORE_STYLES:
        r = _read_style(key)
        if isinstance(r, str) and r.startswith("SKIP:"):
            pytest.skip("skip-with-reason: " + r[len("SKIP:"):].strip())
        core[key] = (r, expected_label)
        print(f"  {key}: label={r['label']!r} expected={expected_label!r} "
              f"sum={_sum(r['mix'])} rows={len(r['mix'])} mix={r['mix']}")

    aggr, aggr_label = core[STYLE_AGGRESSIVE_KEY]
    consv, consv_label = core[STYLE_CONSERVATIVE_KEY]

    # ============================ LABEL PERSISTS (across views) ============================
    # The portfolio the user is wired to (allocation_profile_id) names itself the SEEDED
    # style on the detail endpoint — the per-user style label is stable across the two
    # reads, not a one-shot echo of the seed payload.
    assert aggr["label"] == aggr_label, (
        f"Aggressive user resolved to portfolio labelled {aggr['label']!r}, "
        f"expected {aggr_label!r} — per-user style label did not persist")
    assert consv["label"] == consv_label, (
        f"Conservative user resolved to portfolio labelled {consv['label']!r}, "
        f"expected {consv_label!r} — per-user style label did not persist")

    # ============================ EACH SUMS TO 100 (+-0.5) ============================
    _assert_sums_to_100(aggr)
    _assert_sums_to_100(consv)

    # ============================ ROW-SETS DIFFER BY RISK LEVEL ============================
    # Aggressive vs Conservative must NOT be the same allocation. We compare the full
    # {symbol: percent} maps (not exact published numbers vs a hard-coded table): if a
    # high-risk and a low-risk style produced identical weights, that is a real
    # mis-wiring of the published mix.
    assert aggr["mix"] != consv["mix"], (
        f"Aggressive and Conservative resolved to the SAME allocation mix {aggr['mix']} — "
        "distinct risk levels must publish different weights")

    # Sanity that we are not comparing the same portfolio twice (distinct uuids).
    assert aggr["uuid"] != consv["uuid"], (
        "Aggressive and Conservative resolved to the SAME portfolio uuid "
        f"{aggr['uuid']} — the two style users are not on distinct portfolios")

    # ===================== OPTIONAL THIRD STYLE: Moderate (sub-clause only) =====================
    # Moderate is asserted only when its portfolio is actually wired on the DEV backend.
    # The gen API currently does NOT wire a user_portfolio for Moderate (seed gate, not a
    # product result), so a missing wiring is reported but does NOT fail the core oracle.
    mod = _read_style(STYLE_MODERATE_KEY)
    if isinstance(mod, str) and mod.startswith("SKIP:"):
        print(f"  portfolio_moderate: sub-clause skipped — {mod[len('SKIP:'):].strip()}")
        mod_note = "Moderate skipped (seed gate)"
    else:
        print(f"  portfolio_moderate: label={mod['label']!r} expected={STYLE_MODERATE!r} "
              f"sum={_sum(mod['mix'])} rows={len(mod['mix'])} mix={mod['mix']}")
        # Label persists for Moderate too (label-only; no balance is asserted).
        assert mod["label"] == STYLE_MODERATE, (
            f"Moderate user resolved to portfolio labelled {mod['label']!r}, "
            f"expected {STYLE_MODERATE!r} — per-user style label did not persist "
            "(Moderate is label-only; no balance is asserted)")
        _assert_sums_to_100(mod)
        # Moderate must also be a distinct mix from the two extremes.
        assert mod["mix"] != aggr["mix"] and mod["mix"] != consv["mix"], (
            "Moderate resolved to the SAME mix as Aggressive or Conservative — "
            "distinct risk levels must publish different weights")
        mod_note = f"Moderate sum={_sum(mod['mix'])}"

    print(f"  PASS: labels persist ({aggr_label}/{consv_label}); each core mix sums ~100 "
          f"(A={_sum(aggr['mix'])} C={_sum(consv['mix'])}); Aggressive != Conservative "
          f"({len(aggr['mix'])} vs {len(consv['mix'])} rows); {mod_note}")
