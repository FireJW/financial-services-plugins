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


class SetupLaunchSupplementLaneTests(unittest.TestCase):
    def test_normalize_request_preserves_setup_launch_candidates_and_strategic_themes(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "strategic_base_watch_themes": [
                    "commercial_space",
                    "controlled_fusion",
                    "commercial_space",
                    "",
                ],
                "setup_launch_candidates": [
                    {
                        "ticker": "603698.SS",
                        "name": "航天工程",
                        "theme_guess": ["commercial_space"],
                        "setup_reasons": ["reclaimed_ma20_ma50"],
                        "ignored": "drop-me",
                    }
                ],
            }
        )

        self.assertEqual(
            normalized["strategic_base_watch_themes"],
            ["commercial_space", "controlled_fusion"],
        )
        self.assertEqual(normalized["setup_launch_candidates"][0]["ticker"], "603698.SS")
        self.assertEqual(
            normalized["setup_launch_candidates"][0]["source"],
            "setup_launch_scan",
        )
        self.assertNotIn("ignored", normalized["setup_launch_candidates"][0])

    def test_resolve_setup_launch_theme_pool_unions_weekend_topics_and_strategic_themes(self) -> None:
        themes = module_under_test.resolve_setup_launch_theme_pool(
            {
                "strategic_base_watch_themes": [
                    "commercial_space",
                    "controlled_fusion",
                    "humanoid_robotics",
                ]
            },
            {
                "candidate_topics": [
                    {"topic_name": "commercial_space"},
                    {"topic_name": "oil_shipping"},
                ]
            },
        )

        self.assertEqual(
            themes,
            ["commercial_space", "oil_shipping", "controlled_fusion", "humanoid_robotics"],
        )

    def test_build_setup_launch_candidates_from_universe_generates_theme_aware_setup_rows(self) -> None:
        rows = module_under_test.build_setup_launch_candidates_from_universe(
            [
                {
                    "ticker": "603698.SS",
                    "name": "航天工程",
                    "sector": "商业航天",
                    "price": 12.0,
                    "high": 12.3,
                    "low": 11.4,
                    "pre_close": 11.55,
                    "day_pct": 3.9,
                    "day_turnover_cny": 320_000_000.0,
                    "turnover_rate_pct": 2.8,
                    "pct_from_60d": 18.0,
                    "pct_from_ytd": 9.5,
                    "price_snapshot": {"close": 12.0, "ma20": 11.3, "ma50": 10.9, "rs90": 82.0},
                    "theme_guess": ["commercial_space"],
                },
                {
                    "ticker": "000001.SZ",
                    "name": "底部漂移样本",
                    "sector": "商业航天",
                    "price": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "pre_close": 9.95,
                    "day_pct": 0.5,
                    "day_turnover_cny": 60_000_000.0,
                    "turnover_rate_pct": 0.2,
                    "pct_from_60d": 1.0,
                    "pct_from_ytd": -5.0,
                    "price_snapshot": {"close": 10.0, "ma20": 10.2, "ma50": 10.6, "rs90": 48.0},
                    "theme_guess": ["commercial_space"],
                },
                {
                    "ticker": "000002.SZ",
                    "name": "强势延伸样本",
                    "sector": "商业航天",
                    "price": 35.0,
                    "high": 35.4,
                    "low": 31.0,
                    "pre_close": 31.5,
                    "day_pct": 9.8,
                    "day_turnover_cny": 910_000_000.0,
                    "turnover_rate_pct": 8.0,
                    "pct_from_60d": 66.0,
                    "pct_from_ytd": 42.0,
                    "price_snapshot": {"close": 35.0, "ma20": 31.0, "ma50": 28.0, "rs90": 115.0},
                    "theme_guess": ["commercial_space"],
                },
            ],
            active_themes=["commercial_space", "controlled_fusion"],
            existing_tickers=set(),
            max_names=5,
        )

        self.assertEqual([item["ticker"] for item in rows], ["603698.SS"])
        self.assertEqual(rows[0]["source"], "setup_launch_scan")
        self.assertEqual(rows[0]["theme_guess"], ["commercial_space"])
        self.assertIn("structure_repair_visible", rows[0]["setup_reasons"])
        self.assertEqual(rows[0]["distance_from_bottom_state"], "off_bottom_not_extended")

    def test_build_setup_launch_candidates_from_universe_requires_active_theme_match(self) -> None:
        rows = module_under_test.build_setup_launch_candidates_from_universe(
            [
                {
                    "ticker": "603698.SS",
                    "name": "航天工程",
                    "sector": "商业航天",
                    "price": 12.0,
                    "high": 12.3,
                    "low": 11.4,
                    "pre_close": 11.55,
                    "day_pct": 3.9,
                    "day_turnover_cny": 320_000_000.0,
                    "turnover_rate_pct": 2.8,
                    "pct_from_60d": 18.0,
                    "pct_from_ytd": 9.5,
                    "price_snapshot": {"close": 12.0, "ma20": 11.3, "ma50": 10.9, "rs90": 82.0},
                    "theme_guess": ["commercial_space"],
                }
            ],
            active_themes=["controlled_fusion"],
            existing_tickers=set(),
            max_names=5,
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
