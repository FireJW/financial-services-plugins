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


class MonthEndShortlistProfilePassthroughTests(unittest.TestCase):
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
        self.assertEqual(normalized["keep_threshold"], 58.0)
        self.assertEqual(normalized["strict_top_pick_threshold"], 59.0)
        self.assertEqual(normalized["profile_settings"]["keep_threshold"], 58.0)
        self.assertEqual(normalized["profile_settings"]["strict_top_pick_threshold"], 59.0)

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
            patch.object(module_under_test, "enrich_live_result_reporting", side_effect=lambda result, *_: result),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
        ):
            result = module_under_test.run_month_end_shortlist(
                {
                    "template_name": "month_end_shortlist",
                    "target_date": "2026-04-17",
                    "analysis_time": "2026-04-16T15:25:00+08:00",
                    "filter_profile": "month_end_event_support_transition",
                }
            )

        self.assertEqual(result["request"]["filter_profile"], "month_end_event_support_transition")
        self.assertEqual(result["request"]["keep_threshold"], 58.0)
        self.assertEqual(result["request"]["strict_top_pick_threshold"], 59.0)


if __name__ == "__main__":
    unittest.main()
