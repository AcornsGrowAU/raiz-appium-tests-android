"""TC-12 [P2] — Rewards brand-detail webview renders content (RAIZ-9984).

Tapping a Featured or Boosted reward must open a brand-detail surface that
actually RENDERS content — a non-empty shop CTA and/or terms copy — within a
generous timeout, and must NOT show a blank/errored webview state. This is a
value-over-presence check: we assert on the real rendered CTA/terms text and
explicitly fail on any web-load error message, rather than merely asserting an
element exists.
"""
import pytest

from config.settings import LONG_WAIT
from pages.rewards_page import RewardsPage


@pytest.mark.rewards
class TestRewardsBrandDetailWebview:
    def test_brand_detail_webview_renders_content(self, rewards: RewardsPage):
        # Precondition: the Earn surface has reward cards to open. Account state
        # drifts, but the shared account reliably carries Featured/Boosted offers;
        # skip (don't fail) if a transient empty Earn list leaves nothing to tap.
        if not rewards.get_rewards():
            pytest.skip("No Featured/Boosted reward cards on the Earn tab to open")

        assert rewards.open_first_featured_or_boosted_reward(), \
            "No Featured or Boosted reward card was available to open"

        # The brand detail/webview is a heavy partner surface — give it a generous
        # wait to render its shop CTA and/or terms content.
        cta_text = rewards.get_detail_cta_text(timeout=LONG_WAIT)
        terms_text = rewards.get_detail_terms_text(timeout=LONG_WAIT) if cta_text is None else None

        rendered = cta_text or terms_text
        assert rendered, (
            "Brand-detail webview rendered no shop CTA and no terms/how-it-works "
            "content within the timeout (blank/empty webview — RAIZ-9984)"
        )
        # Value, not just presence: the rendered marker carries real, non-blank text.
        assert rendered.strip(), f"Brand-detail content rendered but was blank: {rendered!r}"

        # And the detail must NOT be an error/blank webview state.
        assert not rewards.is_detail_error_state_shown(), (
            "Brand-detail webview surfaced an error/load-failure state instead of "
            "rendering brand content (RAIZ-9984)"
        )
