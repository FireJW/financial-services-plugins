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


class EmergentThemePromotionTests(unittest.TestCase):
    def _strong_candidate(self, **overrides: object) -> dict[str, object]:
        base = {
            "theme_name": "optical_interconnect",
            "theme_label": "Optical Interconnect",
            "signal_strength": "high",
            "source_kind": "weekend_market_candidate",
            "priority_rank": 1,
            "source_count": 3,
            "supporting_signals": [
                {"source_kind": "x_live_index", "summary": "Weekend X discussion stayed concentrated on optics."},
                {"source_kind": "reddit", "summary": "Reddit kept confirming optics demand."},
                {"source_kind": "preferred_seed", "summary": "Preferred seeds kept the same theme tags."},
            ],
        }
        base.update(overrides)
        return module_under_test.normalize_emergent_theme_candidate(base)

    def test_normalize_emergent_theme_candidate_classifies_coarse_signals(self) -> None:
        candidate = module_under_test.normalize_emergent_theme_candidate(
            {
                "topic_name": "optical_interconnect",
                "topic_label": "Optical Interconnect",
                "signal_strength": "high",
                "source_kind": "weekend_market_candidate",
                "priority_rank": 1,
                "supporting_signals": [
                    {"source_kind": "x_live_index", "summary": "Weekend X theme cluster remained strong."},
                    {"source_kind": "reddit", "summary": "Reddit kept confirming the same optics narrative."},
                    {"source_kind": "preferred_seed", "summary": "Preferred seeds tagged the same theme."},
                ],
                "ignored": "drop-me",
            }
        )

        self.assertEqual(candidate["theme_name"], "optical_interconnect")
        self.assertEqual(candidate["theme_label"], "Optical Interconnect")
        self.assertEqual(candidate["coarse_signal_strength"], "strong")
        self.assertEqual(candidate["coarse_signal_breadth"], "broad")
        self.assertEqual(candidate["coarse_signal_consensus"], "aligned")
        self.assertNotIn("ignored", candidate)

    def test_emergent_theme_promotion_score_and_threshold_behavior(self) -> None:
        promoted = self._strong_candidate()
        thin = module_under_test.normalize_emergent_theme_candidate(
            {
                "theme_name": "satellite_chain",
                "signal_strength": "medium",
                "source_kind": "explicit_request",
                "source_count": 1,
                "supporting_signals": [
                    {"source_kind": "manual_note", "summary": "Single-source mention only."},
                ],
            }
        )

        self.assertGreaterEqual(
            module_under_test.emergent_theme_promotion_score(promoted),
            module_under_test.EMERGENT_THEME_PROMOTION_THRESHOLD,
        )
        self.assertTrue(module_under_test.should_promote_emergent_theme(promoted))
        self.assertLess(
            module_under_test.emergent_theme_promotion_score(thin),
            module_under_test.EMERGENT_THEME_PROMOTION_THRESHOLD,
        )
        self.assertFalse(module_under_test.should_promote_emergent_theme(thin))

    def test_build_emergent_theme_candidates_merges_duplicate_sources_into_one_theme(self) -> None:
        candidates = module_under_test.build_emergent_theme_candidates_from_runtime_inputs(
            {
                "emergent_theme_candidates": [
                    {
                        "theme_name": "optical_interconnect",
                        "signal_strength": "medium",
                        "source_kind": "manual_seed",
                        "supporting_signals": [
                            {"source_kind": "manual_seed", "summary": "Manual seed still points to optics."},
                        ],
                    }
                ]
            },
            weekend_market_candidate={
                "candidate_topics": [
                    {
                        "topic_name": "optical_interconnect",
                        "topic_label": "Optical Interconnect",
                        "priority_rank": 1,
                        "signal_strength": "high",
                        "why_it_matters": "Weekend discussion stayed concentrated on optics.",
                        "ranking_reason": "Preferred seeds and live X both pointed to optics.",
                        "monday_watch": "Watch optics leadership at the open.",
                        "key_sources": [
                            {
                                "source_kind": "x_live_index",
                                "source_name": "optics_live",
                                "summary": "Live X stayed focused on optics.",
                            }
                        ],
                    }
                ]
            },
            market_strength_candidates=[
                {
                    "ticker": "300394.SZ",
                    "name": "天孚通信",
                    "theme_guess": ["optical_interconnect"],
                    "close_strength": "high",
                    "strength_reason": "near_limit_close",
                    "board_context": "high_conviction_momentum",
                    "source": "market_strength_scan",
                }
            ],
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["theme_name"], "optical_interconnect")
        self.assertGreaterEqual(candidate["source_count"], 3)
        self.assertIn("manual_seed", candidate["source_kinds"])
        self.assertIn("weekend_market_candidate", candidate["source_kinds"])
        self.assertIn("market_strength_candidate", candidate["source_kinds"])
        self.assertTrue(candidate["promoted"])

    def test_merge_promoted_emergent_themes_into_active_pool_adds_only_promoted_names(self) -> None:
        promoted = self._strong_candidate()
        thin = module_under_test.normalize_emergent_theme_candidate(
            {
                "theme_name": "satellite_chain",
                "signal_strength": "medium",
                "source_kind": "explicit_request",
                "source_count": 1,
                "supporting_signals": [
                    {"source_kind": "manual_note", "summary": "Single-source note only."},
                ],
            }
        )

        active_themes = module_under_test.merge_promoted_emergent_themes_into_active_pool(
            ["commercial_space"],
            [promoted, thin],
        )

        self.assertEqual(active_themes, ["commercial_space", "optical_interconnect"])

    def test_enrich_live_result_reporting_attaches_emergent_theme_surfaces(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {
                    "strategic_base_watch_themes": ["commercial_space"],
                    "emergent_theme_candidates": [
                        {
                            "theme_name": "optical_interconnect",
                            "theme_label": "Optical Interconnect",
                            "signal_strength": "high",
                            "source_kind": "explicit_request",
                            "priority_rank": 1,
                            "source_count": 3,
                            "supporting_signals": [
                                {"source_kind": "manual_seed", "summary": "Manual seed stayed positive."},
                                {"source_kind": "reddit", "summary": "Reddit kept confirming the same theme."},
                                {"source_kind": "x_live_index", "summary": "X live evidence remained concentrated."},
                            ],
                        }
                    ],
                },
                "filter_summary": {},
                "top_picks": [],
                "dropped": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            },
            failure_candidates=[],
            assessed_candidates=[],
        )

        self.assertIn("emergent_theme_candidates", enriched)
        self.assertEqual(enriched["emergent_theme_candidates"][0]["theme_name"], "optical_interconnect")
        self.assertIn("commercial_space", enriched["promoted_active_themes"])
        self.assertIn("optical_interconnect", enriched["promoted_active_themes"])

    def test_merge_track_results_attaches_emergent_theme_surfaces(self) -> None:
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
                "strategic_base_watch_themes": ["commercial_space"],
                "emergent_theme_candidates": [
                    {
                        "theme_name": "optical_interconnect",
                        "theme_label": "Optical Interconnect",
                        "signal_strength": "high",
                        "source_kind": "explicit_request",
                        "priority_rank": 1,
                        "source_count": 3,
                        "supporting_signals": [
                            {"source_kind": "manual_seed", "summary": "Manual seed stayed positive."},
                            {"source_kind": "reddit", "summary": "Reddit kept confirming the same theme."},
                            {"source_kind": "x_live_index", "summary": "X live evidence remained concentrated."},
                        ],
                    }
                ],
            },
        )

        self.assertIn("emergent_theme_candidates", merged)
        self.assertEqual(merged["emergent_theme_candidates"][0]["theme_name"], "optical_interconnect")
        self.assertIn("optical_interconnect", merged["promoted_active_themes"])

    def test_run_month_end_shortlist_merges_promoted_emergent_themes_into_setup_pool(self) -> None:
        captured: dict[str, list[str]] = {}

        def fake_setup_builder(
            universe_rows: list[dict[str, object]],
            *,
            active_themes: list[str],
            existing_tickers: set[str],
            max_names: int,
        ) -> list[dict[str, object]]:
            captured["active_themes"] = list(active_themes)
            return []

        def fake_enrich_track_result(
            result: dict[str, object],
            failure_candidates: list[dict[str, object]],
            assessed_candidates: list[dict[str, object]] | None = None,
            *,
            track_name: str = "",
            track_config: dict[str, object] | None = None,
            direction_reference_map: list[dict[str, object]] | None = None,
            weekend_market_candidate: dict[str, object] | None = None,
            prior_review_adjustments: list[dict[str, object]] | None = None,
            geopolitics_overlay: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "filter_summary": {"track_name": track_name, "keep_threshold": track_config["keep_threshold"]},
                "top_picks": [],
                "dropped": [],
                "diagnostic_scorecard": [],
                "near_miss_candidates": [],
                "midday_action_summary": [],
                "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
                "report_markdown": "",
            }

        with (
            patch.object(module_under_test._compiled, "normalize_request", side_effect=lambda payload: dict(payload)),
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda request, **_: request),
            patch.object(
                module_under_test._compiled,
                "run_month_end_shortlist",
                return_value={
                    "status": "ok",
                    "filter_summary": {"keep_threshold": 58.0},
                    "top_picks": [],
                    "dropped": [],
                    "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
                },
            ),
            patch.object(module_under_test._compiled, "classify_board", side_effect=lambda ticker: "main_board"),
            patch.object(module_under_test, "build_market_strength_candidates_from_universe", return_value=[]),
            patch.object(module_under_test, "build_setup_launch_candidates_from_universe", side_effect=fake_setup_builder),
            patch.object(module_under_test, "enrich_track_result", side_effect=fake_enrich_track_result),
            patch.object(module_under_test, "attach_cache_baseline_metadata", side_effect=lambda merged, assessed: merged),
        ):
            result = module_under_test.run_month_end_shortlist(
                {
                    "template_name": "month_end_shortlist",
                    "target_date": "2026-04-21",
                    "emergent_theme_candidates": [
                        {
                            "theme_name": "optical_interconnect",
                            "theme_label": "Optical Interconnect",
                            "signal_strength": "high",
                            "source_kind": "explicit_request",
                            "priority_rank": 1,
                            "source_count": 3,
                            "supporting_signals": [
                                {"source_kind": "manual_seed", "summary": "Manual seed stayed positive."},
                                {"source_kind": "reddit", "summary": "Reddit kept confirming the same theme."},
                                {"source_kind": "x_live_index", "summary": "X live evidence remained concentrated."},
                            ],
                        }
                    ],
                },
                universe_fetcher=lambda request: [],
                market_strength_universe_fetcher=lambda request: [],
            )

        self.assertIn("optical_interconnect", captured["active_themes"])
        self.assertIn("optical_interconnect", result["promoted_active_themes"])

    def test_build_data_blocked_theme_confirmed_candidates_preserves_tiansci_style_miss(self) -> None:
        emergent_theme_candidates = [
            module_under_test.normalize_emergent_theme_candidate(
                {
                    "theme_name": "lithium_upstream",
                    "theme_label": "Lithium Upstream",
                    "signal_strength": "high",
                    "source_kind": "explicit_request",
                    "priority_rank": 1,
                    "source_count": 3,
                    "supporting_names": ["002709.SZ", "002466.SZ", "002407.SZ"],
                    "supporting_signals": [
                        {"source_kind": "x_live_index", "summary": "Key X users kept reinforcing lithium upstream."},
                        {"source_kind": "earnings_confirmation", "summary": "Earnings broadly confirmed lithium upstream."},
                        {"source_kind": "market_strength_candidate", "summary": "Market action aligned with lithium upstream."},
                    ],
                }
            )
        ]
        dropped = [
            {
                "ticker": "002709.SZ",
                "name": "天赐材料",
                "drop_reason": "bars_fetch_failed",
                "bars_fetch_error": "bars_fetch_failed for `002709.SZ`: Eastmoney request failed after 3 attempts",
            }
        ]

        blocked = module_under_test.build_data_blocked_theme_confirmed_candidates(
            dropped,
            emergent_theme_candidates,
        )

        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["ticker"], "002709.SZ")
        self.assertEqual(blocked[0]["theme_name"], "lithium_upstream")
        self.assertEqual(blocked[0]["status"], "data_blocked_theme_confirmed")


if __name__ == "__main__":
    unittest.main()
