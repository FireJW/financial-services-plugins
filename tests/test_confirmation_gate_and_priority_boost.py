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


if __name__ == "__main__":
    unittest.main()
