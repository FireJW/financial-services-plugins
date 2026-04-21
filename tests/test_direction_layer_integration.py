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


if __name__ == "__main__":
    unittest.main()
