#!/usr/bin/env python3
"""Tests for board-specific threshold overrides in month-end shortlist."""
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

import month_end_shortlist_runtime as m


def _make_entry(ticker: str, score: float, keep: bool, failures: list[str] | None = None) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "score": score,
        "keep": keep,
        "keep_threshold_gap": round(score - 56.0, 2),
        "hard_filter_failures": failures or [],
        "tier_tags": [],
    }


class BoardThresholdOverrideTests(unittest.TestCase):
    """Verify that main_board candidates are held to 58 while chinext uses 56."""

    def test_main_board_demoted_below_58(self):
        """Main board candidate with score 57 should be demoted (keep=False)."""
        entries = [_make_entry("002384.SZ", 57.0, keep=True)]  # main_board
        result, thresholds = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertFalse(result[0]["keep"])
        self.assertIn("board_demoted", result[0]["tier_tags"])
        self.assertEqual(result[0]["board"], "main_board")
        self.assertEqual(result[0]["board_keep_threshold"], 58.0)
        self.assertEqual(result[0]["keep_threshold_gap"], -1.0)

    def test_main_board_kept_at_58(self):
        """Main board candidate with score 58 should stay keep=True."""
        entries = [_make_entry("000988.SZ", 58.0, keep=True)]  # main_board
        result, _ = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertTrue(result[0]["keep"])
        self.assertNotIn("board_demoted", result[0]["tier_tags"])
        self.assertEqual(result[0]["keep_threshold_gap"], 0.0)

    def test_chinext_kept_at_56(self):
        """Chinext candidate with score 56 should stay keep=True (no override)."""
        entries = [_make_entry("300857.SZ", 56.0, keep=True)]  # chinext
        result, _ = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertTrue(result[0]["keep"])
        self.assertEqual(result[0]["board"], "chinext")
        # chinext has no override, so gap stays relative to base 56.0
        self.assertEqual(result[0]["keep_threshold_gap"], 0.0)

    def test_chinext_57_stays_qualified(self):
        """Chinext candidate with score 57 should remain keep=True."""
        entries = [_make_entry("300136.SZ", 57.0, keep=True)]  # chinext
        result, _ = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertTrue(result[0]["keep"])
        self.assertEqual(result[0]["keep_threshold_gap"], 1.0)

    def test_main_board_promoted_when_score_meets_board_threshold(self):
        """Main board candidate at 58 that core marked not-keep should be promoted."""
        entries = [_make_entry("000988.SZ", 58.0, keep=False)]
        result, _ = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertTrue(result[0]["keep"])
        self.assertIn("board_promoted", result[0]["tier_tags"])

    def test_no_override_for_other_profiles(self):
        """Board overrides should not apply to broad_coverage_mode."""
        entries = [_make_entry("002384.SZ", 57.0, keep=True)]
        result, thresholds = m.apply_board_threshold_overrides(
            entries, "broad_coverage_mode", 55.0,
        )
        self.assertTrue(result[0]["keep"])
        self.assertEqual(thresholds, {})

    def test_hard_failure_prevents_promotion(self):
        """Candidate with hard failures should not be promoted even if score >= board threshold."""
        entries = [_make_entry("000988.SZ", 58.0, keep=False, failures=["trend_template_failed"])]
        result, _ = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        self.assertFalse(result[0]["keep"])

    def test_mixed_board_candidates(self):
        """Verify correct split behavior across main_board and chinext."""
        entries = [
            _make_entry("000988.SZ", 58.0, keep=True),   # main_board, stays
            _make_entry("002384.SZ", 57.0, keep=True),   # main_board, demoted
            _make_entry("300136.SZ", 57.0, keep=True),   # chinext, stays
            _make_entry("300857.SZ", 56.0, keep=True),   # chinext, stays
            _make_entry("000657.SZ", 56.0, keep=True),   # main_board, demoted
        ]
        result, thresholds = m.apply_board_threshold_overrides(
            entries, "month_end_event_support_transition", 56.0,
        )
        keeps = [(e["ticker"], e["keep"]) for e in result]
        self.assertEqual(keeps, [
            ("000988.SZ", True),   # main_board 58 >= 58
            ("002384.SZ", False),  # main_board 57 < 58
            ("300136.SZ", True),   # chinext 57 >= 56
            ("300857.SZ", True),   # chinext 56 >= 56
            ("000657.SZ", False),  # main_board 56 < 58
        ])
        self.assertEqual(thresholds["main_board"], 58.0)


if __name__ == "__main__":
    unittest.main()


class SplitUniverseByBoardTests(unittest.TestCase):
    """Verify split_universe_by_board correctly partitions candidates."""

    def _make_candidate(self, ticker: str, name: str = "") -> dict:
        return {"ticker": ticker, "name": name or ticker}

    def test_basic_split(self):
        """Main board and chinext candidates go to their respective tracks."""
        payload = {
            "universe_candidates": [
                self._make_candidate("000988.SZ"),  # main_board
                self._make_candidate("300857.SZ"),  # chinext
                self._make_candidate("002384.SZ"),  # main_board
                self._make_candidate("300136.SZ"),  # chinext
            ],
        }
        tracks, out_of_scope = m.split_universe_by_board(payload)
        main_tickers = [c["ticker"] for c in tracks["main_board"]["universe_candidates"]]
        chinext_tickers = [c["ticker"] for c in tracks["chinext"]["universe_candidates"]]
        self.assertEqual(sorted(main_tickers), ["000988.SZ", "002384.SZ"])
        self.assertEqual(sorted(chinext_tickers), ["300136.SZ", "300857.SZ"])
        self.assertEqual(out_of_scope, [])

    def test_star_board_dropped(self):
        """Star board candidates should be in out_of_scope."""
        payload = {
            "universe_candidates": [
                self._make_candidate("688525.SS"),  # star
                self._make_candidate("000988.SZ"),  # main_board
            ],
        }
        tracks, out_of_scope = m.split_universe_by_board(payload)
        self.assertEqual(len(out_of_scope), 1)
        self.assertEqual(out_of_scope[0]["ticker"], "688525.SS")
        self.assertEqual(out_of_scope[0]["drop_reason"], "outside_track_scope")
        self.assertEqual(len(tracks["main_board"]["universe_candidates"]), 1)

    def test_track_thresholds_applied(self):
        """Each track payload should have its own keep_threshold."""
        payload = {
            "universe_candidates": [
                self._make_candidate("000988.SZ"),
                self._make_candidate("300857.SZ"),
            ],
        }
        tracks, _ = m.split_universe_by_board(payload)
        self.assertEqual(tracks["main_board"]["keep_threshold"], 58.0)
        self.assertEqual(tracks["main_board"]["strict_top_pick_threshold"], 59.0)
        self.assertEqual(tracks["chinext"]["keep_threshold"], 56.0)
        self.assertEqual(tracks["chinext"]["strict_top_pick_threshold"], 58.0)

    def test_empty_universe(self):
        """Empty universe should produce empty tracks."""
        payload = {"universe_candidates": []}
        tracks, out_of_scope = m.split_universe_by_board(payload)
        self.assertEqual(len(tracks["main_board"]["universe_candidates"]), 0)
        self.assertEqual(len(tracks["chinext"]["universe_candidates"]), 0)
        self.assertEqual(out_of_scope, [])

    def test_history_filtered_per_track(self):
        """history_by_ticker should be filtered to only the track's tickers."""
        payload = {
            "universe_candidates": [
                self._make_candidate("000988.SZ"),
                self._make_candidate("300857.SZ"),
            ],
            "history_by_ticker": {
                "000988.SZ": [{"close": 10}],
                "300857.SZ": [{"close": 20}],
            },
        }
        tracks, _ = m.split_universe_by_board(payload)
        self.assertIn("000988.SZ", tracks["main_board"]["history_by_ticker"])
        self.assertNotIn("300857.SZ", tracks["main_board"]["history_by_ticker"])
        self.assertIn("300857.SZ", tracks["chinext"]["history_by_ticker"])
        self.assertNotIn("000988.SZ", tracks["chinext"]["history_by_ticker"])

    def test_split_universe_by_board_ignores_market_strength_candidates(self):
        payload = {
            "universe_candidates": [
                self._make_candidate("000988.SZ", "华工科技"),
                self._make_candidate("300857.SZ", "协创数据"),
            ],
            "market_strength_candidates": [
                {"ticker": "603268.SS", "name": "松发股份"}
            ],
        }
        tracks, out_of_scope = m.split_universe_by_board(payload)
        self.assertEqual(
            sorted(c["ticker"] for c in tracks["main_board"]["universe_candidates"]),
            ["000988.SZ"],
        )
        self.assertEqual(
            sorted(c["ticker"] for c in tracks["chinext"]["universe_candidates"]),
            ["300857.SZ"],
        )
        self.assertEqual(out_of_scope, [])


class MergeTrackResultsTests(unittest.TestCase):
    """Verify merge_track_results combines per-track results correctly."""

    def _make_track_result(self, track_name: str, top_picks: list[dict], dropped: list[dict] | None = None) -> dict:
        return {
            "top_picks": top_picks,
            "dropped": dropped or [],
            "diagnostic_scorecard": [],
            "near_miss_candidates": [],
            "midday_action_summary": [],
            "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
            "filter_summary": {
                "universe_count": len(top_picks) + len(dropped or []),
                "kept_count": len(top_picks),
                "top_pick_count": len(top_picks),
            },
            "_track_name": track_name,
        }

    def test_top_picks_combined(self):
        """Top picks from all tracks should be combined."""
        results = {
            "main_board": self._make_track_result("main_board", [{"ticker": "000988.SZ"}]),
            "chinext": self._make_track_result("chinext", [{"ticker": "300857.SZ"}]),
        }
        merged = m.merge_track_results(results, m.TRACK_CONFIGS)
        tickers = [p["ticker"] for p in merged["top_picks"]]
        self.assertIn("000988.SZ", tickers)
        self.assertIn("300857.SZ", tickers)

    def test_out_of_scope_in_dropped(self):
        """Out-of-scope candidates should appear in merged dropped."""
        results = {
            "main_board": self._make_track_result("main_board", []),
            "chinext": self._make_track_result("chinext", []),
        }
        out_of_scope = [{"ticker": "688525.SS", "name": "688525.SS", "board": "star", "drop_reason": "outside_track_scope"}]
        merged = m.merge_track_results(results, m.TRACK_CONFIGS, out_of_scope_dropped=out_of_scope)
        dropped_tickers = [d["ticker"] for d in merged["dropped"]]
        self.assertIn("688525.SS", dropped_tickers)

    def test_per_track_summary_in_filter_summary(self):
        """filter_summary should contain per_track breakdown."""
        results = {
            "main_board": self._make_track_result("main_board", [{"ticker": "000988.SZ"}]),
            "chinext": self._make_track_result("chinext", []),
        }
        merged = m.merge_track_results(results, m.TRACK_CONFIGS)
        per_track = merged["filter_summary"]["per_track"]
        self.assertIn("main_board", per_track)
        self.assertIn("chinext", per_track)
        self.assertEqual(per_track["main_board"]["label"], "主板")
        self.assertEqual(per_track["chinext"]["label"], "创业板")

    def test_per_track_summary_counts_use_actual_track_result_contents(self):
        """Per-track summary should reflect actual lists even when filter_summary omits counts."""
        results = {
            "main_board": {
                "top_picks": [{"ticker": "000988.SZ"}],
                "dropped": [{"ticker": "600519.SS"}],
                "diagnostic_scorecard": [{"ticker": "000988.SZ"}],
                "near_miss_candidates": [{"ticker": "002384.SZ"}],
                "midday_action_summary": [],
                "tier_output": {"T1": [{"ticker": "000988.SZ"}], "T2": [], "T3": [{"ticker": "002384.SZ"}], "T4": []},
                "filter_summary": {
                    "kept_count": 1,
                    "keep_threshold": 58.0,
                },
                "_track_name": "main_board",
            },
            "chinext": {
                "top_picks": [{"ticker": "300857.SZ"}, {"ticker": "300620.SZ"}],
                "dropped": [{"ticker": "300476.SZ"}],
                "diagnostic_scorecard": [{"ticker": "300857.SZ"}, {"ticker": "300620.SZ"}],
                "near_miss_candidates": [{"ticker": "300308.SZ"}],
                "midday_action_summary": [],
                "tier_output": {"T1": [{"ticker": "300857.SZ"}, {"ticker": "300620.SZ"}], "T2": [], "T3": [{"ticker": "300308.SZ"}], "T4": []},
                "filter_summary": {
                    "kept_count": 2,
                    "keep_threshold": 56.0,
                },
                "_track_name": "chinext",
            },
        }
        merged = m.merge_track_results(results, m.TRACK_CONFIGS)
        per_track = merged["filter_summary"]["per_track"]
        self.assertEqual(per_track["main_board"]["top_pick_count"], 1)
        self.assertEqual(per_track["chinext"]["top_pick_count"], 2)
        self.assertEqual(per_track["main_board"]["universe_count"], 2)
        self.assertEqual(per_track["chinext"]["universe_count"], 3)
        self.assertEqual(merged["filter_summary"]["top_pick_count"], 3)
        self.assertEqual(merged["filter_summary"]["universe_count"], 5)

    def test_report_markdown_has_track_sections(self):
        """Report markdown should have separate sections for each track."""
        results = {
            "main_board": self._make_track_result("main_board", [{"ticker": "000988.SZ", "name": "华工科技"}]),
            "chinext": self._make_track_result("chinext", [{"ticker": "300857.SZ", "name": "协创数据"}]),
        }
        merged = m.merge_track_results(results, m.TRACK_CONFIGS)
        md = merged["report_markdown"]
        self.assertIn("## 主板 (main_board)", md)
        self.assertIn("## 创业板 (chinext)", md)

    def test_merge_track_results_applies_total_rendered_cap_to_merged_tiers(self):
        """Merged tier_output should be globally capped without dropping T1 first."""
        original_cap = m.TOTAL_RENDERED_CAP
        m.TOTAL_RENDERED_CAP = 3
        try:
            results = {
                "main_board": {
                    **self._make_track_result("main_board", [{"ticker": "000988.SZ"}]),
                    "tier_output": {
                        "T1": [{"ticker": "000988.SZ", "score": 58.0, "track_name": "main_board"}],
                        "T2": [],
                        "T3": [
                            {"ticker": "002384.SZ", "score": 57.0, "track_name": "main_board"},
                            {"ticker": "002463.SZ", "score": 56.0, "track_name": "main_board"},
                        ],
                        "T4": [],
                    },
                },
                "chinext": {
                    **self._make_track_result("chinext", [{"ticker": "300857.SZ"}]),
                    "tier_output": {
                        "T1": [{"ticker": "300857.SZ", "score": 56.0, "track_name": "chinext"}],
                        "T2": [],
                        "T3": [
                            {"ticker": "300308.SZ", "score": 55.0, "track_name": "chinext"},
                            {"ticker": "300394.SZ", "score": 54.0, "track_name": "chinext"},
                        ],
                        "T4": [],
                    },
                },
            }
            merged = m.merge_track_results(results, m.TRACK_CONFIGS)
        finally:
            m.TOTAL_RENDERED_CAP = original_cap

        merged_t1 = [row["ticker"] for row in merged["tier_output"]["T1"]]
        merged_t3 = [row["ticker"] for row in merged["tier_output"]["T3"]]
        total = sum(len(v) for v in merged["tier_output"].values())

        self.assertEqual(total, 3)
        self.assertEqual(merged_t1, ["000988.SZ", "300857.SZ"])
        self.assertEqual(merged_t3, ["002384.SZ"])


if __name__ == "__main__":
    unittest.main()
