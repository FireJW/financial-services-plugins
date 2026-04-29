#!/usr/bin/env python3
from __future__ import annotations

import shutil
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
COMPILED_ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "short-horizon-shortlist"
    / "scripts"
    / "__pycache__"
    / "month_end_shortlist_runtime.cpython-312.pyc"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO_ROOT = (
    REPO_ROOT.parents[2] / REPO_ROOT.parent.name
    if REPO_ROOT.parent.parent.name == ".worktrees"
    else REPO_ROOT
)
SOURCE_ARTIFACT = (
    SOURCE_REPO_ROOT
    / "financial-analysis"
    / "skills"
    / "short-horizon-shortlist"
    / "scripts"
    / "__pycache__"
    / "month_end_shortlist_runtime.cpython-312.pyc"
)

if not COMPILED_ARTIFACT.exists() and SOURCE_ARTIFACT.exists():
    COMPILED_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_ARTIFACT, COMPILED_ARTIFACT)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as module_under_test


class MonthEndShortlistProfilePassthroughTests(unittest.TestCase):
    def test_normalize_request_preserves_weekend_market_candidate_input(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "weekend_market_candidate_input": {
                    "x_seed_inputs": [
                        {
                            "handle": "tuolaji2024",
                            "tags": ["optical_interconnect"],
                            "candidate_names": ["中际旭创", "新易盛"],
                            "ignored": "drop-me",
                        }
                    ],
                    "x_expansion_inputs": [
                        {
                            "handle": "aleabitoreddit",
                            "theme_overlap": ["optical_interconnect"],
                        }
                    ],
                    "reddit_inputs": [
                        {
                            "subreddit": "stocks",
                            "thread_summary": "Optics still strong",
                        }
                    ],
                    "x_live_index_results": [
                        {
                            "x_posts": [
                                {
                                    "post_url": "https://x.com/live/status/1",
                                    "author_handle": "live_seed",
                                    "combined_summary": "商业航天和卫星互联网升温。",
                                }
                            ]
                        }
                    ],
                    "x_live_index_result_paths": [
                        "D:\\Users\\rickylu\\dev\\financial-services-plugins-clean\\.tmp\\weekend-market-candidate-actual\\result.x-index.weekend-mix.live.json"
                    ],
                },
            }
        )

        self.assertIn("weekend_market_candidate_input", normalized)
        candidate_input = normalized["weekend_market_candidate_input"]
        self.assertEqual(candidate_input["x_seed_inputs"][0]["handle"], "tuolaji2024")
        self.assertNotIn("ignored", candidate_input["x_seed_inputs"][0])
        self.assertEqual(candidate_input["x_expansion_inputs"][0]["handle"], "aleabitoreddit")
        self.assertEqual(candidate_input["reddit_inputs"][0]["subreddit"], "stocks")
        self.assertEqual(candidate_input["x_live_index_results"][0]["x_posts"][0]["author_handle"], "live_seed")
        self.assertEqual(
            candidate_input["x_live_index_result_paths"][0],
            "D:\\Users\\rickylu\\dev\\financial-services-plugins-clean\\.tmp\\weekend-market-candidate-actual\\result.x-index.weekend-mix.live.json",
        )

    def test_normalize_request_preserves_cleaned_geopolitics_candidate_input(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_candidate_input": {
                    "news_signals": [
                        {
                            "source": "ap",
                            "headline": "Shipping disruption fears rise",
                            "summary": "Hormuz disruption risk repriced.",
                            "direction_hint": "escalation",
                            "timestamp": "2026-04-18T09:30:00+08:00",
                        }
                    ],
                    "x_signals": [
                        {
                            "account": "MacroDesk",
                            "url": "https://x.com/example/status/1",
                            "summary": "Energy traders lean toward renewed supply fear.",
                            "direction_hint": "escalation",
                            "timestamp": "2026-04-18T09:40:00+08:00",
                        }
                    ],
                    "market_signals": {
                        "oil": "up",
                        "gold": "up",
                        "shipping": "up",
                        "risk_style": "risk_off",
                        "usd_rates": "tightening",
                        "airlines": "down",
                        "industrials": "down",
                    },
                    "ignored_field": "drop-me",
                },
            }
        )

        self.assertIn("macro_geopolitics_candidate_input", normalized)
        candidate_input = normalized["macro_geopolitics_candidate_input"]
        self.assertEqual(candidate_input["news_signals"][0]["direction_hint"], "escalation")
        self.assertEqual(candidate_input["x_signals"][0]["account"], "MacroDesk")
        self.assertEqual(candidate_input["market_signals"]["oil"], "up")
        self.assertNotIn("ignored_field", candidate_input)

    def test_candidate_input_does_not_auto_create_formal_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_candidate_input": {
                    "news_signals": [
                        {
                            "headline": "Talks resume",
                            "summary": "Transit may normalize.",
                            "direction_hint": "de_escalation",
                        }
                    ],
                    "market_signals": {
                        "oil": "down",
                        "gold": "down",
                    },
                },
            }
        )

        self.assertIn("macro_geopolitics_candidate_input", normalized)
        self.assertNotIn("macro_geopolitics_overlay", normalized)

    def test_normalize_request_preserves_emergent_theme_candidates(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "emergent_theme_candidates": [
                    {
                        "theme_name": "optical_interconnect",
                        "theme_label": "Optical Interconnect",
                        "signal_strength": "high",
                        "source_kind": "manual_seed",
                        "priority_rank": 1,
                        "supporting_signals": [
                            {"source_kind": "manual_seed", "summary": "Manual seed stayed focused on optics."},
                            {"source_kind": "reddit", "summary": "Reddit kept confirming the optics chain."},
                        ],
                        "ignored": "drop-me",
                    }
                ],
            }
        )

        self.assertIn("emergent_theme_candidates", normalized)
        candidate = normalized["emergent_theme_candidates"][0]
        self.assertEqual(candidate["theme_name"], "optical_interconnect")
        self.assertEqual(candidate["theme_label"], "Optical Interconnect")
        self.assertEqual(candidate["source_kind"], "manual_seed")
        self.assertEqual(candidate["priority_rank"], 1)
        self.assertEqual(candidate["supporting_signals"][1]["source_kind"], "reddit")
        self.assertNotIn("ignored", candidate)

    def test_enrich_live_result_reporting_attaches_weekend_candidate_and_reference_map(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {
                    "weekend_market_candidate_input": {
                        "x_seed_inputs": [
                            {
                                "handle": "seed_one",
                                "tags": ["optical_interconnect"],
                                "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                            }
                        ]
                    }
                },
                "filter_summary": {},
                "top_picks": [],
                "dropped": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            },
            failure_candidates=[],
            assessed_candidates=[],
        )

        self.assertIn("weekend_market_candidate", enriched)
        self.assertIn("direction_reference_map", enriched)
        self.assertIn(
            enriched["direction_reference_map"][0]["mapping_note"],
            (
                "Direction reference only. Not a formal execution layer.",
                "Tickers resolved at build time.",
            ),
        )

    def test_merge_track_results_attaches_weekend_candidate_and_reference_map(self) -> None:
        merged = module_under_test.merge_track_results(
            track_results={
                "main_board": {
                    "filter_summary": {"track_name": "main_board"},
                    "top_picks": [],
                    "dropped": [],
                    "diagnostic_scorecard": [],
                    "near_miss_candidates": [],
                    "midday_action_summary": [],
                    "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
                    "report_markdown": "",
                }
            },
            track_configs={"main_board": {"label": "主板"}},
            base_request={
                "weekend_market_candidate_input": {
                    "x_seed_inputs": [
                        {
                            "handle": "seed_one",
                            "tags": ["optical_interconnect"],
                            "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                        }
                    ]
                }
            },
        )

        self.assertIn("weekend_market_candidate", merged)
        self.assertIn("direction_reference_map", merged)
        self.assertIn(
            merged["direction_reference_map"][0]["mapping_note"],
            (
                "Direction reference only. Not a formal execution layer.",
                "Tickers resolved at build time.",
            ),
        )

    def test_merge_track_results_attaches_market_strength_supplement_rows(self) -> None:
        merged = module_under_test.merge_track_results(
            track_results={
                "main_board": {
                    "filter_summary": {"track_name": "main_board"},
                    "top_picks": [],
                    "dropped": [],
                    "diagnostic_scorecard": [],
                    "near_miss_candidates": [],
                    "midday_action_summary": [],
                    "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
                    "report_markdown": "",
                }
            },
            track_configs={"main_board": {"label": "主板"}},
            base_request={
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
        )

        self.assertIn("priority_watchlist", merged)
        tickers = [row["ticker"] for row in merged["priority_watchlist"]]
        self.assertIn("002980.SZ", tickers)
        row = next(item for item in merged["priority_watchlist"] if item["ticker"] == "002980.SZ")
        self.assertTrue(row.get("market_strength_supplement"))

    def test_merge_track_results_attaches_setup_launch_candidates(self) -> None:
        merged = module_under_test.merge_track_results(
            track_results={
                "main_board": {
                    "filter_summary": {"track_name": "main_board"},
                    "top_picks": [],
                    "dropped": [],
                    "diagnostic_scorecard": [],
                    "near_miss_candidates": [],
                    "midday_action_summary": [],
                    "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
                    "report_markdown": "",
                }
            },
            track_configs={"main_board": {"label": "main_board"}},
            setup_launch_candidates=[
                {
                    "ticker": "603698.SS",
                    "name": "航天工程",
                    "theme_guess": ["commercial_space"],
                    "setup_reasons": ["structure_repair_visible"],
                    "structure_repair": "high",
                    "volume_return": "medium",
                    "rs_improvement": "medium",
                    "distance_from_bottom_state": "off_bottom_not_extended",
                    "source": "setup_launch_scan",
                }
            ],
            base_request={},
        )

        self.assertIn("setup_launch_candidates", merged)
        self.assertEqual(merged["setup_launch_candidates"][0]["ticker"], "603698.SS")

    def test_normalize_request_preserves_cleaned_geopolitics_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_overlay": {
                    "regime_label": "escalation",
                    "confidence": "medium",
                    "headline_risk": "high",
                    "beneficiary_chains": ["oil_shipping", "gold", "unknown_chain"],
                    "headwind_chains": ["airlines", "high_beta_growth", "mystery"],
                    "notes": "Hormuz disruption risk repriced.",
                    "extra_field": "drop-me",
                },
            }
        )

        self.assertIn("macro_geopolitics_overlay", normalized)
        overlay = normalized["macro_geopolitics_overlay"]
        self.assertEqual(overlay["regime_label"], "escalation")
        self.assertEqual(overlay["beneficiary_chains"], ["oil_shipping", "gold"])
        self.assertEqual(overlay["headwind_chains"], ["airlines", "high_beta_growth"])
        self.assertEqual(overlay["notes"], "Hormuz disruption risk repriced.")
        self.assertNotIn("extra_field", overlay)

    def test_normalize_request_drops_invalid_geopolitics_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_overlay": {
                    "regime_label": "headline_noise",
                    "beneficiary_chains": ["oil_shipping"],
                    "headwind_chains": ["airlines"],
                },
            }
        )

        self.assertNotIn("macro_geopolitics_overlay", normalized)

    def test_normalize_request_preserves_event_support_transition_profile(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-17",
                "analysis_time": "2026-04-16T15:25:00+08:00",
                "filter_profile": "month_end_event_support_transition",
            }
        )

        self.assertEqual(normalized["filter_profile"], "month_end_event_support_transition")
        self.assertEqual(normalized["keep_threshold"], 56.0)
        self.assertEqual(normalized["strict_top_pick_threshold"], 58.0)
        self.assertEqual(normalized["profile_settings"]["keep_threshold"], 56.0)
        self.assertEqual(normalized["profile_settings"]["strict_top_pick_threshold"], 58.0)

    def test_run_month_end_shortlist_preserves_profile_inside_compiled_runtime(self) -> None:
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            captured["compiled_internal_request"] = module_under_test._compiled.normalize_request(payload)
            return {
                "status": "ok",
                "request": captured["compiled_internal_request"],
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
            patch.object(
                module_under_test,
                "merge_track_results",
                side_effect=lambda *args, base_request=None, **kwargs: {
                    "status": "ok",
                    "request": base_request or {},
                    "filter_summary": {},
                    "dropped": [],
                    "top_picks": [],
                    "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
                },
            ),
            patch.object(module_under_test, "attach_cache_baseline_metadata", side_effect=lambda merged, _: merged),
        ):
            result = module_under_test.run_month_end_shortlist(
                {
                    "template_name": "month_end_shortlist",
                    "target_date": "2026-04-17",
                    "analysis_time": "2026-04-16T15:25:00+08:00",
                    "filter_profile": "month_end_event_support_transition",
                },
                universe_fetcher=lambda request: [],
                market_strength_universe_fetcher=lambda request: [],
            )

        self.assertEqual(result["request"]["filter_profile"], "month_end_event_support_transition")
        self.assertEqual(result["request"]["keep_threshold"], 56.0)
        self.assertEqual(result["request"]["strict_top_pick_threshold"], 58.0)

    def test_run_month_end_shortlist_auto_generates_market_strength_candidates_from_universe(self) -> None:
        universe_rows = [
            {
                "ticker": "603268.SS",
                "name": "松发股份",
                "day_pct": 9.6,
                "price": 21.9,
                "high": 22.0,
                "low": 20.2,
                "pre_close": 20.0,
                "day_turnover_cny": 880000000.0,
                "turnover_rate_pct": 11.2,
            }
        ]
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            return {
                "status": "ok",
                "request": payload,
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        def fake_merge_track_results(track_results, track_configs, **kwargs):
            captured["market_strength_candidates"] = kwargs.get("market_strength_candidates")
            return {
                "top_picks": [],
                "dropped": [],
                "filter_summary": {},
                "priority_watchlist": [
                    {
                        "ticker": "603268.SS",
                        "name": "松发股份",
                        "market_strength_supplement": True,
                    }
                ],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
            patch.object(module_under_test, "merge_track_results", side_effect=fake_merge_track_results),
        ):
            result = module_under_test.run_month_end_shortlist(
                {"template_name": "month_end_shortlist", "target_date": "2026-04-21"},
                universe_fetcher=lambda _: universe_rows,
            )

        self.assertIn("603268.SS", [row["ticker"] for row in result.get("priority_watchlist", [])])
        generated = captured["market_strength_candidates"]
        self.assertTrue(any(row["ticker"] == "603268.SS" for row in generated))

    def test_run_month_end_shortlist_auto_generates_setup_launch_candidates_from_universe(self) -> None:
        universe_rows = [
            {
                "ticker": "603698.SS",
                "name": "航天工程",
                "sector": "商业航天",
                "price": 12.0,
                "high": 12.3,
                "low": 11.4,
                "pre_close": 11.55,
                "day_pct": 3.9,
                "day_turnover_cny": 320000000.0,
                "turnover_rate_pct": 2.8,
                "pct_from_60d": 18.0,
                "pct_from_ytd": 9.5,
                "price_snapshot": {"close": 12.0, "ma20": 11.3, "ma50": 10.9, "rs90": 82.0},
                "theme_guess": ["commercial_space"],
            }
        ]
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            return {
                "status": "ok",
                "request": payload,
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        def fake_merge_track_results(track_results, track_configs, **kwargs):
            captured["setup_launch_candidates"] = kwargs.get("setup_launch_candidates")
            return {
                "top_picks": [],
                "dropped": [],
                "filter_summary": {},
                "priority_watchlist": [],
                "setup_launch_candidates": kwargs.get("setup_launch_candidates", []),
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
            patch.object(module_under_test, "merge_track_results", side_effect=fake_merge_track_results),
        ):
            result = module_under_test.run_month_end_shortlist(
                {
                    "template_name": "month_end_shortlist",
                    "target_date": "2026-04-21",
                    "weekend_market_candidate_input": {
                        "x_seed_inputs": [
                            {
                                "handle": "seed_one",
                                "tags": ["commercial_space"],
                                "candidate_names": ["航天工程"],
                            }
                        ]
                    },
                },
                universe_fetcher=lambda _: universe_rows,
            )

        self.assertIn("setup_launch_candidates", result)
        generated = captured["setup_launch_candidates"]
        self.assertTrue(any(row["ticker"] == "603698.SS" for row in generated))

    def test_run_month_end_shortlist_prefers_dedicated_market_strength_universe_fetcher(self) -> None:
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            return {
                "status": "ok",
                "request": payload,
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        def fake_merge_track_results(track_results, track_configs, **kwargs):
            captured["market_strength_candidates"] = kwargs.get("market_strength_candidates")
            return {
                "top_picks": [],
                "dropped": [],
                "filter_summary": {},
                "priority_watchlist": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
            patch.object(module_under_test, "merge_track_results", side_effect=fake_merge_track_results),
        ):
            module_under_test.run_month_end_shortlist(
                {"template_name": "month_end_shortlist", "target_date": "2026-04-21"},
                universe_fetcher=lambda _: [
                    {
                        "ticker": "000988.SZ",
                        "name": "华工科技",
                        "day_pct": 2.1,
                        "price": 44.0,
                        "high": 44.5,
                        "low": 43.0,
                        "pre_close": 43.1,
                        "day_turnover_cny": 1500000000.0,
                        "turnover_rate_pct": 3.2,
                    }
                ],
                market_strength_universe_fetcher=lambda _: [
                    {
                        "ticker": "603268.SS",
                        "name": "松发股份",
                        "day_pct": 9.6,
                        "price": 21.9,
                        "high": 22.0,
                        "low": 20.2,
                        "pre_close": 20.0,
                        "day_turnover_cny": 880000000.0,
                        "turnover_rate_pct": 11.2,
                    }
                ],
            )

        generated = captured["market_strength_candidates"]
        self.assertTrue(any(row["ticker"] == "603268.SS" for row in generated))
        self.assertFalse(any(row["ticker"] == "000988.SZ" for row in generated))

    def test_run_month_end_shortlist_tolerates_market_strength_universe_fetch_failure(self) -> None:
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            return {
                "status": "ok",
                "request": payload,
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        def fake_merge_track_results(track_results, track_configs, **kwargs):
            captured["market_strength_candidates"] = kwargs.get("market_strength_candidates")
            return {
                "top_picks": [],
                "dropped": [],
                "filter_summary": {},
                "priority_watchlist": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
            patch.object(module_under_test, "merge_track_results", side_effect=fake_merge_track_results),
        ):
            result = module_under_test.run_month_end_shortlist(
                {"template_name": "month_end_shortlist", "target_date": "2026-04-21"},
                universe_fetcher=lambda _: [],
                market_strength_universe_fetcher=lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
            )

        self.assertEqual(result["priority_watchlist"], [])
        self.assertEqual(captured["market_strength_candidates"], [])


if __name__ == "__main__":
    unittest.main()
