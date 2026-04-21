#!/usr/bin/env python3
"""Tests for intraday_confirmation_gate and review_based_priority_boost."""
from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as runtime


class IntradayConfirmationGateTests(unittest.TestCase):
    """Spec Section 3.1: intraday_confirmation_gate."""

    def _base_candidate(self, **overrides):
        """A candidate that would be 'qualified' under current logic."""
        base = {
            "ticker": "000988",
            "name": "华工科技",
            "keep": True,
            "score": 58.0,
            "keep_threshold_gap": 2.0,
            "midday_status": "qualified",
            "midday_action": "可执行",
            "structured_catalyst_score": 15.0,
            "execution_state": "live",
            "hard_filter_failures": [],
            "tier_tags": [],
        }
        base.update(overrides)
        return base

    def test_marginal_candidate_triggers_confirmation_gate(self):
        """Gap <= 2 → pending_confirmation."""
        cand = self._base_candidate(keep_threshold_gap=1.5)
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")

    def test_strong_candidate_bypasses_gate(self):
        """High gap, strong catalyst, live data → stays qualified."""
        cand = self._base_candidate(
            keep_threshold_gap=10.0,
            structured_catalyst_score=20.0,
            execution_state="live",
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "可执行")
        self.assertEqual(result["midday_status"], "qualified")

    def test_weak_catalyst_triggers_gate(self):
        """Absent catalyst on qualified candidate → gate triggered."""
        cand = self._base_candidate(
            keep_threshold_gap=5.0,
            structured_catalyst_score=0.0,
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")

    def test_stale_cache_execution_state_triggers_gate(self):
        """execution_state stale_cache on qualified → gate triggered."""
        cand = self._base_candidate(
            keep_threshold_gap=5.0,
            execution_state="stale_cache",
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")


class ReviewBasedPriorityBoostTests(unittest.TestCase):
    """Spec Section 3.2: review_based_priority_boost."""

    def _base_candidate(self, ticker="002185", score=53.0):
        return {
            "ticker": ticker,
            "name": "华天科技" if ticker == "002185" else "华工科技",
            "score": score,
            "keep": False,
            "keep_threshold_gap": -2.0,
            "tier_tags": [],
            "midday_status": "near_miss",
            "midday_action": "继续观察",
        }

    def test_review_upgrade_boosts_priority(self):
        """Upgrade adjustment → score +5, tier tag 'review_upgraded'."""
        candidates = [self._base_candidate("002185", 53.0)]
        adjustments = [
            {"ticker": "002185", "adjustment": "upgrade", "priority_delta": 5, "gate_next_run": False},
        ]
        result = runtime.review_based_priority_boost(candidates, adjustments)
        boosted = result[0]
        self.assertEqual(boosted["score"], 58.0)
        self.assertIn("review_upgraded", boosted["tier_tags"])
        self.assertFalse(boosted.get("review_force_gate", False))

    def test_review_downgrade_reduces_priority_and_forces_gate(self):
        """Downgrade adjustment → score -5, tier tag 'review_downgraded', force gate."""
        candidates = [self._base_candidate("000988", 58.0)]
        adjustments = [
            {"ticker": "000988", "adjustment": "downgrade", "priority_delta": -5, "gate_next_run": True},
        ]
        result = runtime.review_based_priority_boost(candidates, adjustments)
        downgraded = result[0]
        self.assertEqual(downgraded["score"], 53.0)
        self.assertIn("review_downgraded", downgraded["tier_tags"])
        self.assertTrue(downgraded.get("review_force_gate", False))


class DecisionFlowCardLabelTests(unittest.TestCase):
    """Spec Section 3.4: decision flow card label updates."""

    def _make_factor(self, **overrides):
        """Minimal decision factor dict for build_decision_flow_card."""
        base = {
            "ticker": "000988",
            "name": "华工科技",
            "action": "可执行",
            "score": 58.0,
            "keep_threshold_gap": 2.0,
            "midday_status": "qualified",
            "bars_source": "eastmoney_live",
            "execution_state": "live",
            "tier_tags": [],
            "hard_filter_failures": [],
            "logic_summary": "趋势模板通过",
            "technical_summary": "均线多头结构",
            "event_summary": "事件验证通过",
        }
        base.update(overrides)
        return base

    def test_decision_flow_card_shows_pending_confirmation_labels(self):
        """pending_confirmation → card has 盘中确认, 分时确认."""
        factor = self._make_factor(
            midday_status="pending_confirmation",
            action="待确认",
        )
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=55.0, event_card=None, chain_entry=None,
        )
        reminder = card.get("operation_reminder", "")
        self.assertIn("盘中确认", reminder)
        self.assertIn("分时确认", reminder)

    def test_decision_flow_card_shows_review_boost_labels(self):
        """review_upgraded tag → card has 复盘加分."""
        factor = self._make_factor(
            tier_tags=["review_upgraded"],
            score=58.0,
        )
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=55.0, event_card=None, chain_entry=None,
        )
        reminder = card.get("operation_reminder", "")
        self.assertIn("复盘加分", reminder)


if __name__ == "__main__":
    unittest.main()
