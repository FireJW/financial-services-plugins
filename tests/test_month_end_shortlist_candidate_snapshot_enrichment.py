#!/usr/bin/env python3
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

import month_end_shortlist_runtime as module_under_test


class MonthEndShortlistCandidateSnapshotEnrichmentTests(unittest.TestCase):
    def test_prepare_request_with_candidate_snapshots_builds_richer_universe_candidates(self) -> None:
        rows = [
            {
                "trade_date": "2026-04-15",
                "open": 12.1,
                "high": 12.5,
                "low": 11.9,
                "close": 12.34,
                "pre_close": 12.0,
                "pct_chg": 2.83,
                "vol": 9876543.0,
                "amount": 123456789.0,
            }
        ]
        request = {
            "analysis_time": "2026-04-16T04:08:25+00:00",
            "candidate_tickers": ["601600.SH"],
            "history_by_ticker": {"601600.SS": rows},
        }

        prepared = module_under_test.prepare_request_with_candidate_snapshots(request, bars_fetcher=lambda *args, **kwargs: [])

        self.assertEqual(len(prepared["universe_candidates"]), 1)
        candidate = prepared["universe_candidates"][0]
        self.assertEqual(candidate["ticker"], "601600.SS")
        self.assertEqual(candidate["price"], 12.34)
        self.assertEqual(candidate["open"], 12.1)
        self.assertEqual(candidate["high"], 12.5)
        self.assertEqual(candidate["low"], 11.9)
        self.assertEqual(candidate["pre_close"], 12.0)
        self.assertEqual(candidate["day_turnover_cny"], 123456789.0)
        self.assertEqual(candidate["day_volume_shares"], 9876543.0)

    def test_prepare_request_with_candidate_snapshots_fetches_missing_history(self) -> None:
        calls: list[tuple[str, str, str]] = []
        rows = [
            {
                "trade_date": "2026-04-15",
                "open": 20.0,
                "high": 21.0,
                "low": 19.5,
                "close": 20.5,
                "pre_close": 20.0,
                "pct_chg": 2.5,
                "vol": 1000.0,
                "amount": 50000.0,
            }
        ]

        def fake_bars_fetcher(ticker: str, start_date: str, end_date: str) -> list[dict]:
            calls.append((ticker, start_date, end_date))
            return rows

        request = {
            "analysis_time": "2026-04-16T04:08:25+00:00",
            "candidate_tickers": ["002837.SZ"],
            "history_by_ticker": {},
        }

        prepared = module_under_test.prepare_request_with_candidate_snapshots(request, bars_fetcher=fake_bars_fetcher)

        self.assertEqual(len(calls), 1)
        self.assertIn("002837.SZ", calls[0][0])
        self.assertIn("002837.SZ", prepared["history_by_ticker"])
        self.assertEqual(prepared["universe_candidates"][0]["price"], 20.5)


if __name__ == "__main__":
    unittest.main()
