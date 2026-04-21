#!/usr/bin/env python3
"""Tests for postclose_review_runtime."""
from __future__ import annotations

import sys
import unittest
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

from postclose_review_runtime import classify_plan_outcome, generate_adjustment


class ClassifyPlanOutcomeTests(unittest.TestCase):
    """Spec Section 2.4: judgment classification."""

    def test_plan_too_aggressive_generates_downgrade(self):
        """华工科技 scenario: qualified + -1.46% → plan_too_aggressive."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=-1.46)
        self.assertEqual(judgment, "plan_too_aggressive")

    def test_missed_opportunity_generates_upgrade(self):
        """北方稀土 scenario: 观察 + +3.39% → missed_opportunity."""
        judgment = classify_plan_outcome(plan_action="继续观察", actual_return_pct=3.39)
        self.assertEqual(judgment, "missed_opportunity")

    def test_plan_correct_positive_return(self):
        """Qualified + positive return → plan_correct."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=2.5)
        self.assertEqual(judgment, "plan_correct")

    def test_plan_correct_minor_drawdown(self):
        """Qualified + return between -1% and 0% → plan_correct (not too_aggressive)."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=-0.5)
        self.assertEqual(judgment, "plan_correct")

    def test_plan_correct_negative(self):
        """Blocked + negative return → plan_correct_negative."""
        judgment = classify_plan_outcome(plan_action="不执行", actual_return_pct=-2.0)
        self.assertEqual(judgment, "plan_correct_negative")

    def test_observation_small_positive_not_missed(self):
        """观察 + +1.5% (< 2%) → plan_correct_negative (not missed_opportunity)."""
        judgment = classify_plan_outcome(plan_action="继续观察", actual_return_pct=1.5)
        self.assertEqual(judgment, "plan_correct_negative")


class GenerateAdjustmentTests(unittest.TestCase):
    """Spec Section 2.4: adjustment generation."""

    def test_downgrade_from_too_aggressive(self):
        adj = generate_adjustment("plan_too_aggressive")
        self.assertEqual(adj["adjustment"], "downgrade")
        self.assertEqual(adj["priority_delta"], -5)
        self.assertTrue(adj["gate_next_run"])

    def test_upgrade_from_missed_opportunity(self):
        adj = generate_adjustment("missed_opportunity")
        self.assertEqual(adj["adjustment"], "upgrade")
        self.assertEqual(adj["priority_delta"], 5)
        self.assertFalse(adj["gate_next_run"])

    def test_hold_from_plan_correct(self):
        adj = generate_adjustment("plan_correct")
        self.assertEqual(adj["adjustment"], "hold")
        self.assertEqual(adj["priority_delta"], 0)
        self.assertFalse(adj["gate_next_run"])

    def test_hold_from_plan_correct_negative(self):
        adj = generate_adjustment("plan_correct_negative")
        self.assertEqual(adj["adjustment"], "hold")
        self.assertEqual(adj["priority_delta"], 0)
        self.assertFalse(adj["gate_next_run"])


if __name__ == "__main__":
    unittest.main()
