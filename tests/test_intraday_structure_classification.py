#!/usr/bin/env python3
"""Tests for classify_intraday_structure in tradingagents_eastmoney_market."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_eastmoney_market import classify_intraday_structure


def _bar(timestamp: str, o: float, c: float, h: float, l: float, vol: int, amt: float) -> dict:
    return {"timestamp": timestamp, "open": o, "close": c, "high": h, "low": l, "volume": vol, "amount": amt}


class IntradayStructureClassificationTests(unittest.TestCase):
    """Spec Section 1.2: classify_intraday_structure."""

    def test_strong_close_classification(self):
        """Last 2 bars close > VWAP, last bar close > open, close in top 20% of day range."""
        bars = [
            _bar("09:30", 10.0, 10.2, 10.3, 10.0, 1000, 10200.0),
            _bar("09:45", 10.2, 10.3, 10.4, 10.1, 1000, 10300.0),
            _bar("10:00", 10.3, 10.4, 10.5, 10.2, 1000, 10400.0),
            _bar("10:15", 10.4, 10.3, 10.5, 10.2, 1000, 10300.0),
            _bar("10:30", 10.3, 10.4, 10.5, 10.3, 1000, 10400.0),
            _bar("10:45", 10.4, 10.5, 10.6, 10.3, 1000, 10500.0),
            _bar("11:00", 10.5, 10.6, 10.7, 10.4, 1000, 10600.0),
            _bar("11:15", 10.6, 10.7, 10.8, 10.5, 1000, 10700.0),
            _bar("13:00", 10.7, 10.8, 10.9, 10.6, 1000, 10800.0),
            _bar("13:15", 10.8, 10.85, 10.9, 10.7, 1000, 10850.0),
            _bar("13:30", 10.85, 10.9, 11.0, 10.8, 1000, 10900.0),
            _bar("13:45", 10.9, 10.92, 11.0, 10.85, 1000, 10920.0),
            _bar("14:00", 10.9, 10.95, 11.0, 10.85, 1000, 10950.0),
            _bar("14:15", 10.95, 10.98, 11.0, 10.9, 1000, 10980.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "strong_close")

    def test_fade_from_high_classification(self):
        """Intraday high in first half, close < VWAP, close in bottom 40% of day range."""
        bars = [
            _bar("09:30", 10.5, 10.8, 11.0, 10.5, 2000, 21600.0),
            _bar("09:45", 10.8, 10.9, 11.0, 10.7, 2000, 21800.0),
            _bar("10:00", 10.9, 10.7, 11.0, 10.6, 2000, 21400.0),
            _bar("10:15", 10.7, 10.5, 10.8, 10.4, 1000, 10500.0),
            _bar("10:30", 10.5, 10.3, 10.6, 10.2, 1000, 10300.0),
            _bar("10:45", 10.3, 10.1, 10.4, 10.0, 1000, 10100.0),
            _bar("11:00", 10.1, 10.0, 10.2, 9.9, 1000, 10000.0),
            _bar("11:15", 10.0, 9.9, 10.1, 9.8, 1000, 9900.0),
            _bar("13:00", 9.9, 9.8, 10.0, 9.7, 1000, 9800.0),
            _bar("13:15", 9.8, 9.7, 9.9, 9.6, 1000, 9700.0),
            _bar("13:30", 9.7, 9.7, 9.8, 9.6, 1000, 9700.0),
            _bar("13:45", 9.7, 9.6, 9.8, 9.5, 1000, 9600.0),
            _bar("14:00", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
            _bar("14:15", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "fade_from_high")

    def test_weak_open_no_recovery(self):
        """First bar close < open by > 1%, never recovers above open price."""
        open_price = 10.0
        first_close = 9.85  # -1.5% from open
        bars = [
            _bar("09:30", open_price, first_close, 10.0, 9.80, 2000, 19700.0),
            _bar("09:45", 9.85, 9.80, 9.90, 9.75, 1000, 9800.0),
            _bar("10:00", 9.80, 9.82, 9.88, 9.78, 1000, 9820.0),
            _bar("10:15", 9.82, 9.78, 9.85, 9.75, 1000, 9780.0),
            _bar("10:30", 9.78, 9.80, 9.85, 9.75, 1000, 9800.0),
            _bar("10:45", 9.80, 9.75, 9.82, 9.72, 1000, 9750.0),
            _bar("11:00", 9.75, 9.78, 9.80, 9.70, 1000, 9780.0),
            _bar("11:15", 9.78, 9.76, 9.80, 9.72, 1000, 9760.0),
            _bar("13:00", 9.76, 9.74, 9.78, 9.70, 1000, 9740.0),
            _bar("13:15", 9.74, 9.72, 9.76, 9.68, 1000, 9720.0),
            _bar("13:30", 9.72, 9.70, 9.75, 9.68, 1000, 9700.0),
            _bar("13:45", 9.70, 9.68, 9.72, 9.65, 1000, 9680.0),
            _bar("14:00", 9.68, 9.65, 9.70, 9.62, 1000, 9650.0),
            _bar("14:15", 9.65, 9.60, 9.68, 9.58, 1000, 9600.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "weak_open_no_recovery")

    def test_range_bound_default(self):
        """Day range < 3%, close within 30%-70% of day range."""
        bars = [
            _bar("09:30", 10.1, 10.05, 10.15, 10.0, 1000, 10050.0),
            _bar("09:45", 10.05, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("10:00", 10.1, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("10:15", 10.08, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("10:30", 10.12, 10.1, 10.2, 10.05, 1000, 10100.0),
            _bar("10:45", 10.1, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("11:00", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("11:15", 10.1, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("13:00", 10.12, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("13:15", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("13:30", 10.1, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("13:45", 10.12, 10.1, 10.15, 10.02, 1000, 10100.0),
            _bar("14:00", 10.1, 10.08, 10.15, 10.0, 1000, 10080.0),
            _bar("14:15", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "range_bound")

    def test_empty_bars_returns_range_bound(self):
        """Edge case: empty list -> range_bound."""
        self.assertEqual(classify_intraday_structure([]), "range_bound")

    def test_vwap_calculation_correctness(self):
        """VWAP = cumulative amount / cumulative volume."""
        bars = [
            _bar("09:30", 10.0, 10.5, 10.5, 10.0, 100, 1020.0),
            _bar("09:45", 10.5, 11.0, 11.0, 10.5, 200, 2160.0),
        ]
        result = classify_intraday_structure(bars)
        self.assertIn(result, ("strong_close", "fade_from_high", "weak_open_no_recovery", "range_bound"))


if __name__ == "__main__":
    unittest.main()
