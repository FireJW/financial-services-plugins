#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "longbridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from longbridge_trading_plan_runtime import (
    build_postclose_review,
    build_trading_plan_markdown,
    build_trading_plan_report,
)

def _screen_result() -> dict:
    return {
        "analysis_date": "2026-05-02",
        "summary": {"winner": "000988.SZ"},
        "ranked_candidates": [
            {
                "symbol": "000988.SZ",
                "name": "HGTECH",
                "screen_score": 52.41,
                "technical_score": 32.81,
                "catalyst_score": 8.6,
                "valuation_score": 11.0,
                "workbench_score": 60.16,
                "signal": "watch_reclaim",
                "last_close": 119.53,
                "trigger_price": 125.21,
                "stop_loss": 112.56,
                "abandon_below": 112.55,
                "volume_ratio_20": 1.01,
                "tracking_plan": {
                    "suggested_watchlist_bucket": "reclaim_watch",
                    "should_apply": False,
                    "side_effects": "none",
                },
                "qualitative_evaluation": {
                    "qualitative_verdict": "constructive but needs confirmation",
                    "catalyst_summary": "Q1 profit improved.",
                    "key_risks": ["valuation/target-price conflict"],
                },
            },
            {
                "symbol": "002565.SZ",
                "name": "Shunho",
                "screen_score": 34.03,
                "technical_score": 27.43,
                "catalyst_score": 6.6,
                "valuation_score": 0.0,
                "signal": "watch_reclaim",
                "last_close": 19.02,
                "trigger_price": 23.0,
                "stop_loss": 17.33,
                "abandon_below": 17.19,
                "tracking_plan": {"suggested_watchlist_bucket": "reclaim_watch"},
                "qualitative_evaluation": {
                    "qualitative_verdict": "constructive but fragile",
                    "key_risks": ["profit/cash-flow divergence"],
                },
            },
        ],
        "missed_attention_priorities": [
            {
                "priority": "P0",
                "issue": "profit_cashflow_divergence",
                "affected_symbols": ["002565.SZ"],
                "why_it_matters": "Profit without cash-flow support is fragile.",
                "follow_up_action": "Re-read operating cash flow.",
            }
        ],
        "dry_run_action_plan": {
            "status": "dry_run",
            "should_apply": False,
            "side_effects": "none",
            "actions": [
                {
                    "operation": "watchlist.add_stocks",
                    "symbol": "000988.SZ",
                    "should_apply": False,
                    "side_effects": "none",
                }
            ],
        },
    }


def _intraday_result() -> dict:
    return {
        "intraday_monitor": {"analysis_date": "2026-05-06", "trading_allowed": True},
        "monitored_symbols": [
            {
                "symbol": "000988.SZ",
                "latest_price": 126.0,
                "plan_status": {
                    "state": "triggered",
                    "triggered": True,
                    "invalidated": False,
                    "latest_price": 126.0,
                },
                "capital_flow": {"confirms": True, "latest_net_inflow": 5000000},
                "abnormal_volume": {"exists": True, "count": 1},
                "trade_stats": {"dominant_price": 126.0, "total_volume": 3500},
            }
        ],
        "risk_flags": [],
        "should_apply": False,
        "side_effects": "none",
    }


class LongbridgeTradingPlanRuntimeTests(unittest.TestCase):
    def test_build_trading_plan_report_emits_required_closed_loop_schema(self) -> None:
        report = build_trading_plan_report(_screen_result(), session_type="premarket")

        self.assertEqual(report["schema_version"], "longbridge_trading_plan/v1")
        self.assertEqual(report["plan_date"], "2026-05-02")
        self.assertEqual(report["session_type"], "premarket")
        for field in (
            "market_context",
            "candidates",
            "trigger_plan",
            "invalidation_plan",
            "position_sizing_guidance",
            "qualitative_evidence",
            "risk_flags",
            "missed_attention_priorities",
            "dry_run_action_plan",
            "review_checklist",
        ):
            self.assertIn(field, report)
        self.assertFalse(report["should_apply"])
        self.assertEqual(report["side_effects"], "none")
        self.assertEqual(report["candidates"][0]["levels"]["trigger_price"], 125.21)
        self.assertEqual(report["trigger_plan"][0]["upgrade_conditions"][0], "price_at_or_above_trigger")
        self.assertIn("capital_flow_confirms", report["review_checklist"])
        self.assertFalse(report["dry_run_action_plan"]["should_apply"])
        self.assertEqual(report["dry_run_action_plan"]["side_effects"], "none")

    def test_intraday_report_merges_read_only_monitor_status(self) -> None:
        report = build_trading_plan_report(
            _screen_result(),
            session_type="intraday",
            intraday_monitor_result=_intraday_result(),
        )

        candidate = report["candidates"][0]
        self.assertEqual(report["session_type"], "intraday")
        self.assertEqual(candidate["intraday_confirmation"]["plan_status"]["state"], "triggered")
        self.assertTrue(candidate["intraday_confirmation"]["capital_flow_confirms"])
        self.assertIn("000988.SZ", report["market_context"]["intraday_symbols"])
        self.assertFalse(report["should_apply"])
        self.assertEqual(report["side_effects"], "none")

    def test_postclose_review_compares_trigger_stop_abandon_with_actual_prices(self) -> None:
        plan = build_trading_plan_report(_screen_result(), session_type="premarket")
        review = build_postclose_review(
            plan,
            {
                "review_date": "2026-05-06",
                "prices": {
                    "000988.SZ": {"open": 121.0, "high": 126.2, "low": 118.0, "close": 125.8, "volume_ratio_20": 1.4},
                    "002565.SZ": {"open": 19.1, "high": 23.2, "low": 17.0, "close": 17.4, "volume_ratio_20": 1.7},
                },
            },
        )

        by_symbol = {item["symbol"]: item for item in review["candidates_reviewed"]}
        self.assertEqual(review["session_type"], "postclose")
        self.assertTrue(by_symbol["000988.SZ"]["hit_trigger"])
        self.assertEqual(by_symbol["000988.SZ"]["review_status"], "hit_trigger")
        self.assertTrue(by_symbol["002565.SZ"]["stopped"])
        self.assertTrue(by_symbol["002565.SZ"]["invalidated"])
        self.assertEqual(by_symbol["002565.SZ"]["review_status"], "stopped")
        self.assertEqual(review["summary"]["hit_trigger"], 1)
        self.assertEqual(review["summary"]["stopped"], 1)
        self.assertFalse(review["should_apply"])
        self.assertEqual(review["side_effects"], "none")
        self.assertIn("downgrade", by_symbol["002565.SZ"]["next_session_adjustment"])

    def test_postclose_review_marks_failed_trigger_and_still_valid(self) -> None:
        plan = build_trading_plan_report(_screen_result(), session_type="premarket")
        review = build_postclose_review(
            plan,
            {
                "review_date": "2026-05-06",
                "prices": [
                    {"symbol": "000988.SZ", "high": 126.0, "low": 116.0, "close": 124.0},
                    {"symbol": "002565.SZ", "high": 22.0, "low": 18.5, "close": 19.5},
                ],
            },
        )

        by_symbol = {item["symbol"]: item for item in review["candidates_reviewed"]}
        self.assertTrue(by_symbol["000988.SZ"]["failed_trigger"])
        self.assertEqual(by_symbol["000988.SZ"]["review_status"], "failed_trigger")
        self.assertTrue(by_symbol["002565.SZ"]["still_valid"])
        self.assertEqual(by_symbol["002565.SZ"]["review_status"], "still_valid")

    def test_markdown_report_contains_standard_sections_and_side_effect_boundary(self) -> None:
        report = build_trading_plan_report(_screen_result(), session_type="premarket")
        markdown = build_trading_plan_markdown(report)

        self.assertIn("# Longbridge Trading Plan", markdown)
        self.assertIn("## Trigger Plan", markdown)
        self.assertIn("## Invalidation Plan", markdown)
        self.assertIn("## Dry-run Action Plan", markdown)
        self.assertIn("should_apply: `false`", markdown)
        self.assertIn("side_effects: `none`", markdown)


if __name__ == "__main__":
    unittest.main()
