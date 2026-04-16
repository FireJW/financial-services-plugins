#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as module_under_test


class MonthEndShortlistDiscoveryMergeTests(unittest.TestCase):
    def test_enrich_live_result_reporting_injects_discovery_qualified_and_watch_buckets(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "top_picks": [],
            "dropped": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "optical",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            },
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "chain_name": "chip_design",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [{"source_type": "market_rumor", "summary": "市场传闻"}],
                "market_validation": {"volume_multiple_5d": 2.4, "breakout": True, "relative_strength": "strong"},
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates)

        self.assertEqual(enriched["discovery_lane_summary"]["qualified_count"], 1)
        self.assertEqual(enriched["discovery_lane_summary"]["watch_count"], 1)
        self.assertEqual(enriched["directly_actionable"][0]["ticker"], "000988.SZ")
        self.assertEqual(enriched["priority_watchlist"][0]["ticker"], "688521.SS")

    def test_run_month_end_shortlist_passes_request_discovery_candidates_into_enrichment(self) -> None:
        payload = {
            "template_name": "month_end_shortlist",
            "target_date": "2026-04-17",
            "event_discovery_candidates": [
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                    "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
                }
            ],
        }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda request, **_: request),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", return_value={
                "status": "ok",
                "filter_summary": {"keep_threshold": 58.0},
                "top_picks": [],
                "dropped": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
            }),
        ):
            enriched = module_under_test.run_month_end_shortlist(payload)

        self.assertIn("discovery_lane_summary", enriched)
        self.assertEqual(enriched["directly_actionable"][0]["ticker"], "000988.SZ")


if __name__ == "__main__":
    unittest.main()
