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


class MonthEndShortlistCandidateFetchFallbackTests(unittest.TestCase):
    def test_wrap_assess_candidate_converts_bars_fetch_failure_to_drop_record(self) -> None:
        wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(
            lambda candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher: (_ for _ in ()).throw(
                RuntimeError("bars_fetch_failed for `601600.SS`: boom")
            )
        )

        result = wrapped(
            {"ticker": "601600.SS", "name": "中国铝业", "board": "main_board", "sector": "有色"},
            {},
            [],
            bars_fetcher=lambda *args, **kwargs: [],
            html_fetcher=lambda *args, **kwargs: "",
        )

        self.assertFalse(result["keep"])
        self.assertIn("bars_fetch_failed", result["hard_filter_failures"])
        self.assertEqual(result["ticker"], "601600.SS")

    def test_wrap_assess_candidate_preserves_non_bars_errors(self) -> None:
        wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(
            lambda candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher: (_ for _ in ()).throw(
                RuntimeError("unexpected boom")
            )
        )

        with self.assertRaises(RuntimeError):
            wrapped(
                {"ticker": "601600.SS", "name": "中国铝业"},
                {},
                [],
                bars_fetcher=lambda *args, **kwargs: [],
                html_fetcher=lambda *args, **kwargs: "",
            )

    def test_bars_fetch_failure_record_keeps_original_error_text(self) -> None:
        wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(
            lambda candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher: (_ for _ in ()).throw(
                RuntimeError(
                    "bars_fetch_failed for `601975.SS`: Eastmoney request failed: Remote end closed connection without response"
                )
            )
        )

        result = wrapped(
            {"ticker": "601975.SS", "name": "招商南油"},
            {},
            [],
            bars_fetcher=lambda *args, **kwargs: [],
            html_fetcher=lambda *args, **kwargs: "",
        )

        self.assertIn("bars_fetch_failed", result["hard_filter_failures"])
        self.assertIn("Eastmoney request failed", result["bars_fetch_error"])

    def test_classify_eastmoney_cache_freshness_marks_same_day_as_fresh(self) -> None:
        rows = [
            {"date": "2026-04-17"},
            {"date": "2026-04-18"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "fresh_cache")
        self.assertEqual(outcome["last_bar_date"], "2026-04-18")

    def test_classify_eastmoney_cache_freshness_marks_one_day_gap_as_stale_rescue(self) -> None:
        rows = [
            {"date": "2026-04-16"},
            {"date": "2026-04-17"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "stale_one_day")
        self.assertEqual(outcome["last_bar_date"], "2026-04-17")

    def test_classify_eastmoney_cache_freshness_marks_older_gap_as_stale_blocked(self) -> None:
        rows = [
            {"date": "2026-04-15"},
            {"date": "2026-04-16"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "stale_too_old")
        self.assertEqual(outcome["last_bar_date"], "2026-04-16")

    def test_cached_bars_covering_target_date_are_accepted_as_normal_recovery(self) -> None:
        rows = [
            {"date": "2026-04-17", "close": 5.5},
            {"date": "2026-04-18", "close": 5.8},
        ]
        recovered = module_under_test.choose_eastmoney_cache_recovery_mode(rows, "2026-04-18")
        self.assertEqual(recovered["mode"], "fresh_cache")
        self.assertEqual(recovered["bars_source"], "eastmoney_cache")
        self.assertEqual(recovered["rows"][-1]["date"], "2026-04-18")

    def test_wrap_assess_candidate_recovers_from_same_day_eastmoney_cache(self) -> None:
        rows = [
            {"date": "2026-04-17", "close": 5.5},
            {"date": "2026-04-18", "close": 5.8},
        ]

        def base_assess(candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher):
            fetched_rows = bars_fetcher(candidate["ticker"], "2026-04-01", "2026-04-18")
            return {
                "ticker": candidate["ticker"],
                "name": candidate["name"],
                "keep": True,
                "hard_filter_failures": [],
                "scores": {"adjusted_total_score": 75.0},
                "score_components": {"adjusted_total_score": 75.0},
                "bars_row_count": len(fetched_rows),
            }

        wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(base_assess)

        with patch.object(module_under_test, "eastmoney_cached_bars_for_candidate", return_value=rows):
            result = wrapped(
                {"ticker": "601975.SS", "name": "招商南油"},
                {"analysis_time": "2026-04-18T15:00:00+08:00"},
                [],
                bars_fetcher=lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("bars_fetch_failed for `601975.SS`: Eastmoney request failed")
                ),
                html_fetcher=lambda *args, **kwargs: "",
            )

        self.assertTrue(result["keep"])
        self.assertEqual(result["bars_source"], "eastmoney_cache")
        self.assertEqual(result["bars_row_count"], 2)


if __name__ == "__main__":
    unittest.main()
