#!/usr/bin/env python3
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

import month_end_shortlist_runtime as module_under_test


class MarketStrengthSupplementLaneTests(unittest.TestCase):
    def test_normalize_request_preserves_market_strength_candidates(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "market_strength_candidates": [
                    {
                        "ticker": "002980.SZ",
                        "name": "华盛昌",
                        "strength_reason": "near_limit_close",
                        "close_strength": "high",
                        "volume_signal": "expanding",
                        "board_context": "high_conviction_momentum",
                        "theme_guess": ["short_term_momentum"],
                        "source": "market_strength_scan",
                        "ignored": "drop-me",
                    }
                ],
            }
        )

        rows = normalized.get("market_strength_candidates")
        self.assertIsInstance(rows, list)
        self.assertEqual(rows[0]["ticker"], "002980.SZ")
        self.assertEqual(rows[0]["close_strength"], "high")
        self.assertEqual(rows[0]["source"], "market_strength_scan")
        self.assertNotIn("ignored", rows[0])

    def test_build_market_strength_discovery_candidates_converts_rows(self) -> None:
        rows = module_under_test.build_market_strength_discovery_candidates(
            [
                {
                    "ticker": "002980.SZ",
                    "name": "华盛昌",
                    "strength_reason": "near_limit_close",
                    "close_strength": "high",
                    "volume_signal": "expanding",
                    "board_context": "high_conviction_momentum",
                    "theme_guess": ["short_term_momentum"],
                    "source": "market_strength_scan",
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "002980.SZ")
        self.assertEqual(rows[0]["event_type"], "market_strength_scan")
        self.assertEqual(rows[0]["benefit_type"], "mapping")
        self.assertEqual(rows[0]["market_validation"]["relative_strength"], "strong")
        self.assertEqual(rows[0]["market_strength_source"], "market_strength_scan")

    def test_enrich_live_result_reporting_merges_market_strength_candidates_into_watch_surfaces(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {
                    "market_strength_candidates": [
                        {
                            "ticker": "002980.SZ",
                            "name": "华盛昌",
                            "strength_reason": "near_limit_close",
                            "close_strength": "high",
                            "volume_signal": "expanding",
                            "board_context": "high_conviction_momentum",
                            "theme_guess": ["short_term_momentum"],
                            "source": "market_strength_scan",
                        }
                    ]
                },
                "filter_summary": {},
                "top_picks": [],
                "dropped": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            },
            failure_candidates=[],
            assessed_candidates=[],
        )

        self.assertIn("priority_watchlist", enriched)
        tickers = [row["ticker"] for row in enriched["priority_watchlist"]]
        self.assertIn("002980.SZ", tickers)
        row = next(item for item in enriched["priority_watchlist"] if item["ticker"] == "002980.SZ")
        self.assertTrue(row.get("market_strength_supplement"))


if __name__ == "__main__":
    unittest.main()
