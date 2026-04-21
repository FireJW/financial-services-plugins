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


from unittest.mock import patch, MagicMock


def _bar(timestamp, o, c, h, l, vol, amt):
    return {"timestamp": timestamp, "open": o, "close": c, "high": h, "low": l, "volume": vol, "amount": amt}


def _fade_bars():
    """Bars that classify as fade_from_high."""
    return [
        _bar("09:30", 10.5, 10.8, 11.0, 10.5, 2000, 21600.0),
        _bar("09:45", 10.8, 10.9, 11.0, 10.7, 2000, 21800.0),
        _bar("10:00", 10.9, 10.7, 11.0, 10.6, 2000, 21400.0),
        _bar("10:15", 10.7, 10.5, 10.8, 10.4, 1000, 10500.0),
        _bar("10:30", 10.5, 10.3, 10.6, 10.2, 1000, 10300.0),
        _bar("10:45", 10.3, 10.1, 10.4, 10.0, 1000, 10100.0),
        _bar("11:00", 10.1, 10.0, 10.2, 9.9, 1000, 10000.0),
        _bar("11:15", 10.0, 9.9, 10.1, 9.8, 1000, 9900.0),
        _bar("13:00", 9.9, 9.8, 10.0, 9.7, 1000, 9800.0),
        _bar("13:15", 9.8, 9.7, 9.9, 9.6, 1000, 9700.0),
        _bar("13:30", 9.7, 9.7, 9.8, 9.6, 1000, 9700.0),
        _bar("13:45", 9.7, 9.6, 9.8, 9.5, 1000, 9600.0),
        _bar("14:00", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
        _bar("14:15", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
    ]


class RunPostcloseReviewTests(unittest.TestCase):
    """Spec Section 2.4-2.5: full orchestrator."""

    def _make_result(self, candidates):
        return {
            "top_picks": candidates,
            "near_miss_candidates": [],
            "filter_summary": {"keep_threshold": 55.0},
        }

    @patch("postclose_review_runtime._fetch_intraday_bars_for_review")
    def test_full_review_produces_correct_structure(self, mock_bars):
        from postclose_review_runtime import run_postclose_review
        mock_bars.return_value = _fade_bars()
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        self.assertEqual(review["trade_date"], "2026-04-20")
        self.assertEqual(len(review["candidates_reviewed"]), 1)
        cand = review["candidates_reviewed"][0]
        self.assertEqual(cand["ticker"], "000988")
        self.assertEqual(cand["judgment"], "plan_too_aggressive")
        self.assertEqual(cand["adjustment"], "downgrade")
        self.assertEqual(cand["intraday_structure"], "fade_from_high")
        self.assertEqual(review["summary"]["too_aggressive"], 1)
        self.assertTrue(len(review["prior_review_adjustments"]) >= 0)

    @patch("postclose_review_runtime._fetch_intraday_bars_for_review")
    def test_intraday_fetch_failure_still_produces_judgment(self, mock_bars):
        from postclose_review_runtime import run_postclose_review
        mock_bars.return_value = []  # fetch failure → empty
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        cand = review["candidates_reviewed"][0]
        self.assertEqual(cand["intraday_structure"], "unavailable")
        self.assertEqual(cand["judgment"], "plan_too_aggressive")

    def test_empty_result_produces_empty_review(self):
        from postclose_review_runtime import run_postclose_review
        result_json = self._make_result([])
        review = run_postclose_review(result_json, "2026-04-20")
        self.assertEqual(review["summary"]["total_reviewed"], 0)
        self.assertEqual(review["candidates_reviewed"], [])

    @patch("postclose_review_runtime._fetch_intraday_bars_for_review")
    def test_markdown_report_matches_template_structure(self, mock_bars):
        from postclose_review_runtime import run_postclose_review, build_review_markdown
        mock_bars.return_value = _fade_bars()
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        md = build_review_markdown(review)
        self.assertIn("操作建议摘要", md)
        self.assertIn("000988", md)
        self.assertIn("华工科技", md)
        self.assertIn("次日观察点", md)


if __name__ == "__main__":
    unittest.main()
