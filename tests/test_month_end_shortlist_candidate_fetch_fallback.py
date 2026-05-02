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
import tradingagents_decision_bridge_runtime as bridge_runtime


class MonthEndShortlistCandidateFetchFallbackTests(unittest.TestCase):
    def test_infer_execution_state_defaults_plain_candidates_to_live(self) -> None:
        state = module_under_test.infer_execution_state(
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "hard_filter_failures": [],
            }
        )
        self.assertEqual(state, "live")

    def test_last_cached_trade_date_from_row_sets_picks_latest_available_date(self) -> None:
        row_sets = [
            [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
            [{"date": "2026-04-16"}, {"date": "2026-04-18"}],
            [],
        ]
        self.assertEqual(
            module_under_test.last_cached_trade_date_from_row_sets(row_sets),
            "2026-04-18",
        )

    def test_resolve_cache_baseline_metadata_reports_baseline_only_when_cache_lags_target(self) -> None:
        metadata = module_under_test.resolve_cache_baseline_metadata(
            "2026-04-20",
            [
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
                [{"date": "2026-04-18"}],
            ],
        )
        self.assertEqual(metadata["baseline_trade_date"], "2026-04-18")
        self.assertTrue(metadata["cache_baseline_only"])

    def test_resolve_cache_baseline_metadata_stays_empty_when_target_is_covered(self) -> None:
        metadata = module_under_test.resolve_cache_baseline_metadata(
            "2026-04-18",
            [
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
            ],
        )
        self.assertEqual(metadata["baseline_trade_date"], "")
        self.assertFalse(metadata["cache_baseline_only"])

    def test_attach_cache_baseline_metadata_uses_recent_cached_rows(self) -> None:
        result = {"request": {"analysis_time": "2026-04-20T10:00:00+08:00"}}
        candidates = [
            {"ticker": "000988.SZ"},
            {"ticker": "002384.SZ"},
        ]
        with patch.object(
            module_under_test,
            "eastmoney_cached_bars_for_candidate",
            side_effect=[
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
                [{"date": "2026-04-18"}],
            ],
        ):
            enriched = module_under_test.attach_cache_baseline_metadata(result, candidates)
        self.assertEqual(enriched["filter_summary"]["cache_baseline_trade_date"], "2026-04-18")
        self.assertTrue(enriched["filter_summary"]["cache_baseline_only"])
        self.assertEqual(enriched["filter_summary"]["live_supplement_status"], "unavailable")

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

    def test_bars_fetch_failure_record_is_marked_as_blocked_execution_state(self) -> None:
        failed = module_under_test.build_bars_fetch_failed_candidate(
            {"ticker": "601975.SS", "name": "招商南油"},
            RuntimeError("bars_fetch_failed for `601975.SS`: Eastmoney request failed"),
        )
        self.assertEqual(failed["execution_state"], "blocked")

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

    def test_classify_eastmoney_cache_freshness_treats_friday_cache_for_monday_as_stale_rescue(self) -> None:
        rows = [
            {"date": "2026-04-23"},
            {"date": "2026-04-24"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-27")
        self.assertEqual(outcome["mode"], "stale_one_day")
        self.assertEqual(outcome["last_bar_date"], "2026-04-24")

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

    def test_choose_cache_recovery_mode_treats_friday_cache_for_monday_as_stale_rescue(self) -> None:
        rows = [
            {"date": "2026-04-23", "close": 5.5},
            {"date": "2026-04-24", "close": 5.8},
        ]
        recovered = module_under_test.choose_eastmoney_cache_recovery_mode(rows, "2026-04-27")
        self.assertEqual(recovered["mode"], "stale_one_day")
        self.assertEqual(recovered["last_bar_date"], "2026-04-24")

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
        self.assertEqual(result["execution_state"], "fresh_cache")

    def test_local_market_snapshot_accepts_longbridge_profile(self) -> None:
        with patch.object(bridge_runtime, "smart_free_profile_name", return_value="longbridge_market"):
            with patch.object(
                bridge_runtime,
                "summarize_local_market_snapshot",
                return_value={
                    "latest_close": 284.9,
                    "latest_pct_chg": 4.99,
                    "sma20": 270.0,
                    "sma50": 255.0,
                    "rsi14": 62.0,
                    "volume_ratio": 1.35,
                },
            ):
                snapshot = module_under_test.local_market_snapshot_for_candidate("AAPL.US", "2026-05-01")

        self.assertEqual(snapshot["profile_name"], "longbridge_market")
        self.assertEqual(snapshot["close"], 284.9)


if __name__ == "__main__":
    unittest.main()
