"""TC-07 [P1] — Rewards Track tab pending/invested split reconciles.

Value-over-presence test for the Rewards > Track summary. The existing rewards
tests assert the Pending/Invested *labels* are visible; this asserts the real
NUMBERS reconcile:

  * 'Pending rewards' and 'Rewards invested' each parse as non-negative money.
  * If the build renders a Track total, total == pending + invested (+/- $0.01).
  * The 'Pending' filter is honoured — it surfaces a pending-consistent view
    (the Pending figure stays non-negative and the screen does not regress to an
    invested-only state), never a blank/garbage screen.

Targets the class of defect a presence check cannot catch (e.g. a split that
does not add up, or a filter that silently shows the wrong subset).
"""
import pytest

from utils.assertions import assert_non_negative_money, parse_money


@pytest.mark.rewards
class TestRewardsTrackPendingInvestedSplit:
    def test_track_pending_invested_split_reconciles(self, rewards):
        # Switch to the Track tab and require real tracked-reward content (not just
        # the tab still being visible). If the account currently tracks no rewards,
        # the summary numbers don't exist to reconcile — skip rather than fail.
        rewards.switch_to_track()
        if not rewards.is_track_content_loaded():
            if rewards.is_track_empty_state_shown():
                pytest.skip("Track tab is in its empty state — no pending/invested split to reconcile")
            pytest.fail("Track tab showed neither tracked content nor an empty state")

        pending_text = rewards.get_pending_rewards_amount()
        invested_text = rewards.get_rewards_invested_amount()

        # Both metrics must render an actual dollar amount alongside their label.
        # A missing amount next to a present label is itself a defect (the bug a
        # presence-only test misses), so fail rather than skip when the label is
        # shown but its value is absent.
        assert rewards.is_present_now(rewards.PENDING_REWARDS_LABEL), \
            "'Pending rewards' label not present on Track tab"
        assert rewards.is_present_now(rewards.REWARDS_INVESTED_LABEL), \
            "'Rewards invested' label not present on Track tab"
        assert pending_text is not None, \
            "'Pending rewards' label shown but no dollar amount rendered beside it"
        assert invested_text is not None, \
            "'Rewards invested' label shown but no dollar amount rendered beside it"

        # Each figure is well-formed, non-negative money.
        pending = assert_non_negative_money(pending_text, "Pending rewards")
        invested = assert_non_negative_money(invested_text, "Rewards invested")

        # Optional oracle: if the build surfaces a Track total, it must equal the
        # sum of the two parts within rounding tolerance.
        total_text = rewards.get_track_total_amount()
        if total_text is not None:
            total = parse_money(total_text)
            assert abs(total - (pending + invested)) <= 0.01, (
                f"Track total does not reconcile: total={total_text!r} ({total}) "
                f"!= pending {pending_text!r} ({pending}) + invested {invested_text!r} ({invested})"
            )

        # Pending filter must be honoured: applying it yields a pending-consistent
        # view. After filtering, the Pending figure is still readable and
        # non-negative, and the screen has NOT regressed to an invested-only state
        # (the Pending rewards label remains present).
        rewards.filter_track_by("Pending")
        # filter_track_by already blocks until the Pending-rewards label has
        # re-settled after the recompose; assert against a polling wait (not a
        # bare snapshot) so a still-animating frame on a slow emulator can't read
        # as a regression to an invested-only view.
        assert rewards.wait_for_track_label(rewards.PENDING_REWARDS_LABEL), \
            "Pending filter did not yield a pending-consistent view ('Pending rewards' gone)"

        # Read the filtered amount with a settle window: the label re-attaches
        # before its sibling money node during the recompose, so a 0-timeout scan
        # could momentarily miss the value even though the screen is fine.
        pending_after = rewards.get_pending_rewards_amount(timeout=rewards.DEFAULT_SETTLE)
        assert pending_after is not None, \
            "Pending filter applied but no Pending rewards amount rendered"
        pending_after_val = assert_non_negative_money(pending_after, "Pending rewards (filtered)")

        # The pending total is a property of the account, not the active filter, so
        # it must not change when we narrow the list to pending rows.
        assert abs(pending_after_val - pending) <= 0.01, (
            f"Pending rewards figure changed when the Pending filter was applied: "
            f"{pending_text!r} -> {pending_after!r}"
        )

        # Every $-amount surfaced under the Pending filter must still be well-formed
        # money (no '$NaN'/blank rows leaking into the filtered view).
        for text in rewards.get_track_money_texts():
            if "$" in text:
                assert_non_negative_money(text, "Pending-filtered Track row")
