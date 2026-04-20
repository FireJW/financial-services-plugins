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
        self.assertIn("reclaimed_ma20_ma50", rows[0]["setup_reasons"])
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

    def test_classify_structure_repair_prefers_sustained_repair_over_one_day_reclaim(self) -> None:
        weak = {
            "price": 10.2,
            "day_pct": 1.2,
            "pct_from_60d": 9.0,
            "price_snapshot": {"close": 10.2, "ma20": 10.0, "ma50": 10.8},
        }
        strong = {
            "price": 12.0,
            "day_pct": 3.2,
            "pct_from_60d": 18.0,
            "price_snapshot": {
                "close": 12.0,
                "ma20": 11.3,
                "ma50": 10.9,
                "ma20_prev": 11.0,
                "recent_low_trend": "higher_lows",
            },
        }

        self.assertEqual(module_under_test.classify_structure_repair(weak), "medium")
        self.assertEqual(module_under_test.classify_structure_repair(strong), "high")

    def test_classify_volume_return_prefers_reaccumulation_over_single_day_spike(self) -> None:
        spike = {
            "day_turnover_cny": 620_000_000.0,
            "turnover_rate_pct": 4.5,
            "price_snapshot": {
                "volume_ratio": 1.0,
                "recent_turnover_avg": 160_000_000.0,
                "base_turnover_avg": 150_000_000.0,
            },
        }
        reaccumulation = {
            "day_turnover_cny": 300_000_000.0,
            "turnover_rate_pct": 2.6,
            "price_snapshot": {
                "volume_ratio": 1.3,
                "recent_turnover_avg": 280_000_000.0,
                "base_turnover_avg": 120_000_000.0,
            },
        }

        self.assertEqual(module_under_test.classify_volume_return(spike), "medium")
        self.assertEqual(module_under_test.classify_volume_return(reaccumulation), "high")

    def test_classify_rs_improvement_prefers_improving_rs_over_flat_rs(self) -> None:
        flat = {
            "pct_from_ytd": 8.0,
            "day_pct": 1.0,
            "price_snapshot": {"rs90": 78.0, "rs90_prev": 79.0},
        }
        improving = {
            "pct_from_ytd": 8.0,
            "day_pct": 1.0,
            "price_snapshot": {"rs90": 78.0, "rs90_prev": 68.0},
        }

        self.assertEqual(module_under_test.classify_rs_improvement(flat), "low")
        self.assertEqual(module_under_test.classify_rs_improvement(improving), "medium")

    def test_classify_distance_from_bottom_state_emits_four_stage_labels(self) -> None:
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 2.0}),
            "still_bottoming",
        )
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 16.0}),
            "off_bottom_not_extended",
        )
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 42.0}),
            "early_extension",
        )
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 66.0}),
            "too_extended",
        )

    def test_theme_weights_can_change_setup_score_without_changing_contract(self) -> None:
        row = {
            "ticker": "603698.SS",
            "name": "航天工程",
            "pct_from_60d": 18.0,
            "pct_from_ytd": 9.5,
            "day_pct": 3.9,
            "day_turnover_cny": 320_000_000.0,
            "turnover_rate_pct": 2.8,
            "price_snapshot": {
                "close": 12.0,
                "ma20": 11.3,
                "ma50": 10.9,
                "ma20_prev": 11.0,
                "recent_low_trend": "higher_lows",
                "recent_turnover_avg": 280_000_000.0,
                "base_turnover_avg": 120_000_000.0,
                "rs90": 82.0,
                "rs90_prev": 70.0,
            },
        }

        default_score = module_under_test.setup_launch_score(row)
        weighted_score = module_under_test.setup_launch_score(row, theme_name="semiconductor_equipment")

        self.assertNotEqual(default_score, weighted_score)
        self.assertIsInstance(weighted_score, float)

    def test_classify_structure_repair_does_not_treat_one_day_rebound_as_high(self) -> None:
        level = module_under_test.classify_structure_repair(
            {
                "price": 10.2,
                "day_pct": 1.1,
                "pct_from_60d": 4.0,
                "price_snapshot": {
                    "close": 10.2,
                    "ma20": 10.0,
                    "ma50": 10.6,
                    "ma20_prev_5": 10.15,
                    "recent_lows": [9.4, 9.2, 9.1],
                },
            }
        )

        self.assertNotEqual(level, "high")

    def test_classify_volume_return_prefers_recent_vs_base_reacceleration(self) -> None:
        level = module_under_test.classify_volume_return(
            {
                "day_turnover_cny": 220_000_000.0,
                "turnover_rate_pct": 1.2,
                "price_snapshot": {
                    "recent_turnover_window": [220_000_000.0, 240_000_000.0, 230_000_000.0],
                    "base_turnover_window": [90_000_000.0, 100_000_000.0, 95_000_000.0, 92_000_000.0],
                },
            }
        )

        self.assertIn(level, {"medium", "high"})

    def test_classify_rs_improvement_accepts_moderate_absolute_rs_with_positive_trend(self) -> None:
        level = module_under_test.classify_rs_improvement(
            {
                "day_pct": 2.2,
                "pct_from_ytd": 4.0,
                "price_snapshot": {
                    "rs90": 68.0,
                    "rs90_prev_5": 55.0,
                },
            }
        )

        self.assertIn(level, {"medium", "high"})

    def test_classify_distance_from_bottom_state_distinguishes_early_extension(self) -> None:
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 18.0}),
            "off_bottom_not_extended",
        )
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 42.0}),
            "early_extension",
        )
        self.assertEqual(
            module_under_test.classify_distance_from_bottom_state({"pct_from_60d": 66.0}),
            "too_extended",
        )

    def test_setup_launch_score_penalizes_early_extension_vs_off_bottom(self) -> None:
        off_bottom = module_under_test.setup_launch_score(
            {
                "day_pct": 3.0,
                "pct_from_60d": 18.0,
                "pct_from_ytd": 8.0,
                "day_turnover_cny": 260_000_000.0,
                "turnover_rate_pct": 2.5,
                "price_snapshot": {
                    "close": 12.0,
                    "ma20": 11.2,
                    "ma50": 10.8,
                    "ma20_prev_5": 10.9,
                    "recent_lows": [10.6, 10.8, 11.0],
                    "recent_turnover_window": [220_000_000.0, 260_000_000.0, 250_000_000.0],
                    "base_turnover_window": [100_000_000.0, 110_000_000.0, 95_000_000.0],
                    "rs90": 76.0,
                    "rs90_prev_5": 61.0,
                },
            }
        )
        early_extension = module_under_test.setup_launch_score(
            {
                "day_pct": 3.0,
                "pct_from_60d": 42.0,
                "pct_from_ytd": 20.0,
                "day_turnover_cny": 260_000_000.0,
                "turnover_rate_pct": 2.5,
                "price_snapshot": {
                    "close": 12.0,
                    "ma20": 11.2,
                    "ma50": 10.8,
                    "ma20_prev_5": 10.9,
                    "recent_lows": [10.6, 10.8, 11.0],
                    "recent_turnover_window": [220_000_000.0, 260_000_000.0, 250_000_000.0],
                    "base_turnover_window": [100_000_000.0, 110_000_000.0, 95_000_000.0],
                    "rs90": 76.0,
                    "rs90_prev_5": 61.0,
                },
            }
        )

        self.assertGreater(off_bottom, early_extension)

    def test_theme_weights_nudge_score_without_breaking_contract(self) -> None:
        rows = module_under_test.build_setup_launch_candidates_from_universe(
            [
                {
                    "ticker": "688000.SS",
                    "name": "聚变样本",
                    "sector": "可控核聚变",
                    "price": 22.0,
                    "high": 22.4,
                    "low": 21.1,
                    "pre_close": 21.3,
                    "day_pct": 3.3,
                    "day_turnover_cny": 260_000_000.0,
                    "turnover_rate_pct": 2.4,
                    "pct_from_60d": 19.0,
                    "pct_from_ytd": 7.0,
                    "price_snapshot": {
                        "close": 22.0,
                        "ma20": 21.2,
                        "ma50": 20.5,
                        "ma20_prev_5": 20.9,
                        "recent_lows": [20.6, 20.8, 21.0],
                        "recent_turnover_window": [230_000_000.0, 260_000_000.0, 250_000_000.0],
                        "base_turnover_window": [110_000_000.0, 120_000_000.0, 105_000_000.0],
                        "rs90": 74.0,
                        "rs90_prev_5": 59.0,
                    },
                    "theme_guess": ["controlled_fusion"],
                }
            ],
            active_themes=["controlled_fusion"],
            existing_tickers=set(),
            max_names=5,
        )

        self.assertEqual(rows[0]["source"], "setup_launch_scan")
        self.assertEqual(rows[0]["theme_guess"], ["controlled_fusion"])


if __name__ == "__main__":
    unittest.main()
