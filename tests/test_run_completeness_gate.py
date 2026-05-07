#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


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


class RunCompletenessGateTests(unittest.TestCase):
    def test_build_run_completeness_summary_marks_missing_x_and_weekend_as_degraded(self) -> None:
        summary = module_under_test.build_run_completeness_summary(
            request_obj={},
            weekend_market_candidate={"status": "insufficient_signal", "candidate_topics": []},
            filter_summary={},
        )

        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(summary["x_index_status"], "missing")
        self.assertEqual(summary["weekend_status"], "missing")
        self.assertEqual(summary["shortlist_status"], "degraded")
        self.assertIn("missing_x_index_results", summary["reasons"])

    def test_build_run_completeness_summary_marks_full_when_all_stages_are_present(self) -> None:
        summary = module_under_test.build_run_completeness_summary(
            request_obj={
                "weekend_market_candidate_input": {
                    "x_live_index_results": [
                        {
                            "x_posts": [
                                {"post_url": "https://x.com/a/status/1", "post_text_raw": "optical interconnect"}
                            ]
                        }
                    ]
                }
            },
            weekend_market_candidate={
                "status": "candidate_only",
                "candidate_topics": [{"topic_name": "optical_interconnect"}],
            },
            filter_summary={"live_supplement_status": "updated", "cache_baseline_only": False, "blocked_candidate_count": 0},
        )

        self.assertEqual(summary["status"], "full")
        self.assertEqual(summary["x_index_status"], "complete")
        self.assertEqual(summary["weekend_status"], "complete")
        self.assertEqual(summary["shortlist_status"], "complete")
        self.assertEqual(summary["reasons"], [])

    def test_build_run_completeness_summary_marks_explicit_zero_post_x_result_as_partial_not_missing(self) -> None:
        summary = module_under_test.build_run_completeness_summary(
            request_obj={
                "weekend_market_candidate_input": {
                    "x_live_index_results": [
                        {
                            "source_result_path": ".tmp/plan/result.x-index.json",
                            "run_completeness": {"status": "full", "x_posts_captured": 0},
                            "x_posts": [],
                        }
                    ]
                }
            },
            weekend_market_candidate={"status": "insufficient_signal", "candidate_topics": []},
            filter_summary={},
        )

        self.assertEqual(summary["x_index_status"], "partial")
        self.assertIn("partial_x_index_results", summary["reasons"])
        self.assertNotIn("missing_x_index_results", summary["reasons"])

    def test_build_run_completeness_summary_counts_x_posts_from_result_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.x-index.json"
            result_path.write_text(
                json.dumps(
                    {
                        "x_posts": [
                            {"post_url": "https://x.com/live/status/1", "post_text_raw": "AI 光模块继续发酵"}
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = module_under_test.build_run_completeness_summary(
                request_obj={
                    "weekend_market_candidate_input": {
                        "x_live_index_result_paths": [str(result_path)]
                    }
                },
                weekend_market_candidate={
                    "status": "candidate_only",
                    "candidate_topics": [{"topic_name": "optical_interconnect"}],
                },
                filter_summary={
                    "live_supplement_status": "updated",
                    "cache_baseline_only": False,
                    "blocked_candidate_count": 0,
                },
            )

        self.assertEqual(summary["x_index_status"], "complete")
        self.assertEqual(summary["status"], "full")

    def test_enrich_live_result_reporting_prepends_completeness_lines(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {},
                "filter_summary": {"cache_baseline_only": True, "live_supplement_status": "unavailable", "blocked_candidate_count": 3},
                "report_markdown": "# Month-End Shortlist Report: 2026-05-01\n",
                "dropped": [],
                "top_picks": [],
            },
            failure_candidates=[],
            assessed_candidates=[],
        )

        self.assertIn("run_completeness", enriched)
        self.assertEqual(enriched["run_completeness"]["status"], "degraded")
        self.assertIn("Run completeness: `degraded`", enriched["report_markdown"])
        self.assertIn("This is a degraded repo-native run", enriched["report_markdown"])

    def test_merge_track_results_prepends_completeness_lines(self) -> None:
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
            track_configs={"main_board": {"label": "涓绘澘"}},
            base_request={},
        )

        self.assertIn("run_completeness", merged)
        self.assertEqual(merged["run_completeness"]["status"], "degraded")
        self.assertIn("Run completeness: `degraded`", merged["report_markdown"])


if __name__ == "__main__":
    unittest.main()
