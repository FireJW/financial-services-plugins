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


class MonthEndShortlistBenchmarkFallbackTests(unittest.TestCase):
    def test_returns_empty_rows_when_benchmark_fetch_fails(self) -> None:
        wrapped = module_under_test.wrap_bars_fetcher_with_benchmark_fallback(
            lambda ticker, start_date, end_date: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        self.assertEqual(wrapped("000300.SS", "2025-01-01", "2025-12-31"), [])

    def test_non_benchmark_fetch_failure_still_raises(self) -> None:
        wrapped = module_under_test.wrap_bars_fetcher_with_benchmark_fallback(
            lambda ticker, start_date, end_date: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        with self.assertRaises(RuntimeError):
            wrapped("601600.SH", "2025-01-01", "2025-12-31")


if __name__ == "__main__":
    unittest.main()
