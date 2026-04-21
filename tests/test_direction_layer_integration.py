#!/usr/bin/env python3
"""Tests for direction layer execution integration."""
from __future__ import annotations

import sys
import unittest
from copy import deepcopy
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


class ResolveDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.2: build-time ticker resolution."""

    def _make_direction_map(self):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "", "name": "中际旭创"},
                    {"ticker": "", "name": "新易盛"},
                ],
                "high_beta_names": [
                    {"ticker": "", "name": "天孚通信"},
                ],
                "mapping_note": "Direction reference only. Not a formal execution layer.",
            }
        ]

    def test_resolve_direction_tickers_fills_known_names(self):
        """Mock resolver returns tickers for known names, verify tickers are filled."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()
        mock_results = {"中际旭创": "300308", "新易盛": "300502", "天孚通信": "300394"}

        def mock_resolver(name: str) -> str | None:
            return mock_results.get(name)

        resolved = resolve_direction_tickers(direction_map, resolver=mock_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "300308")
        self.assertEqual(entry["leaders"][1]["ticker"], "300502")
        self.assertEqual(entry["high_beta_names"][0]["ticker"], "300394")
        self.assertIn("Tickers resolved", entry["mapping_note"])

    def test_resolve_direction_tickers_keeps_empty_on_failure(self):
        """Resolver returns None → ticker stays empty string."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()

        def failing_resolver(name: str) -> str | None:
            return None

        resolved = resolve_direction_tickers(direction_map, resolver=failing_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "")
        self.assertEqual(entry["leaders"][1]["ticker"], "")


class CrossCheckDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.3: execution-time cross-check against universe."""

    def test_cross_check_direction_tickers_against_universe(self):
        """Names matched against universe by name, in_universe flag set correctly."""
        import month_end_shortlist_runtime as runtime

        direction_map = [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "300308", "name": "中际旭创"},
                    {"ticker": "", "name": "未知公司"},
                ],
                "high_beta_names": [
                    {"ticker": "300394", "name": "天孚通信"},
                ],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]
        universe = [
            {"ticker": "300308", "name": "中际旭创", "f12": "300308", "f14": "中际旭创"},
            {"ticker": "300394", "name": "天孚通信", "f12": "300394", "f14": "天孚通信"},
            {"ticker": "002236", "name": "大华股份", "f12": "002236", "f14": "大华股份"},
        ]

        enriched = runtime.cross_check_direction_tickers(direction_map, universe)
        entry = enriched[0]
        # 300308 is in universe
        self.assertTrue(entry["leaders"][0]["in_universe"])
        # 未知公司 has no ticker and no name match
        self.assertFalse(entry["leaders"][1]["in_universe"])
        # 300394 is in universe
        self.assertTrue(entry["high_beta_names"][0]["in_universe"])


class DirectionAlignmentBoostTests(unittest.TestCase):
    """Spec Section 2: two-tier direction alignment scoring."""

    def _make_weekend_candidate(self, signal_strength="high", status="candidate_only"):
        return {
            "candidate_topics": [{"topic_name": "optical_interconnect", "topic_label": "光通信 / 光模块"}],
            "signal_strength": signal_strength,
            "status": status,
        }

    def _make_direction_map(self, leader_ticker="300308", hb_ticker="300394"):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": leader_ticker, "name": "中际旭创", "in_universe": True}],
                "high_beta_names": [{"ticker": hb_ticker, "name": "天孚通信", "in_universe": True}],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]

    def _make_candidate(self, ticker="300308", score=50.0, matched_themes=None):
        return {
            "ticker": ticker,
            "name": "中际旭创",
            "score": score,
            "adjusted_total_score": score,
            "matched_themes": matched_themes or [],
            "tier_tags": [],
        }

    def test_theme_alignment_boost_high_signal(self):
        """Theme match + high signal → +3."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 0)

    def test_theme_alignment_boost_medium_signal(self):
        """Theme match + medium signal → +1."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("medium"),
        )
        self.assertEqual(result[0]["direction_boost"]["theme_delta"], 1)

    def test_reference_map_leader_boost(self):
        """Leader ticker match → +6."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["direction_role"], "leader")

    def test_reference_map_high_beta_boost(self):
        """High-beta ticker match → +4."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300394", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 4)
        self.assertEqual(boost["direction_role"], "high_beta")

    def test_leader_and_theme_boost_stack(self):
        """Both match → +3 + +6 = +9."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0, matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["total_delta"], 9)
        self.assertEqual(result[0]["adjusted_total_score"], 59.0)

    def test_no_boost_when_insufficient_signal(self):
        """Direction status insufficient → candidates unchanged."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        wmc = self._make_weekend_candidate(status="insufficient_signal")
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), wmc,
        )
        self.assertNotIn("direction_boost", result[0])
        self.assertEqual(result[0]["adjusted_total_score"], 50.0)

    def test_no_boost_when_no_direction(self):
        """weekend_market_candidate is None → no-op."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        result = runtime.direction_alignment_boost([cand], [], None)
        self.assertNotIn("direction_boost", result[0])


if __name__ == "__main__":
    unittest.main()
