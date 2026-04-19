#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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

import preheat_eastmoney_cache as module_under_test


class EastmoneyCachePreheatParsingTests(unittest.TestCase):
    def test_parse_cli_tickers_splits_and_deduplicates(self) -> None:
        tickers = module_under_test.parse_cli_tickers("000988.SZ, 002384.SZ,000988.SZ")
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])

    def test_parse_tickers_file_reads_txt_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tickers.txt"
            path.write_text("000988.SZ\n\n002384.SZ\n", encoding="utf-8")
            tickers = module_under_test.parse_tickers_file(path)
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])

    def test_parse_tickers_file_reads_json_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tickers.json"
            path.write_text(json.dumps(["000988.SZ", "002384.SZ"]), encoding="utf-8")
            tickers = module_under_test.parse_tickers_file(path)
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])


class EastmoneyCachePreheatStatusTests(unittest.TestCase):
    def test_preheat_ticker_reports_cache_hit_when_cache_already_exists(self) -> None:
        with patch.object(module_under_test, "eastmoney_cache_already_exists", return_value=True):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "cache_hit")

    def test_preheat_ticker_reports_cache_written_when_fetch_succeeds(self) -> None:
        with patch.object(module_under_test, "eastmoney_cache_already_exists", return_value=False), patch.object(
            module_under_test, "fetch_eastmoney_daily_bars", return_value=[{"date": "2026-04-19"}]
        ):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "cache_written")
        self.assertEqual(result["ticker"], "000988.SZ")

    def test_preheat_ticker_reports_failed_when_fetch_raises(self) -> None:
        with patch.object(module_under_test, "eastmoney_cache_already_exists", return_value=False), patch.object(
            module_under_test, "fetch_eastmoney_daily_bars", side_effect=RuntimeError("boom")
        ):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "failed")
        self.assertIn("boom", result["message"])


class EastmoneyCachePreheatReportingTests(unittest.TestCase):
    def test_build_summary_counts_statuses(self) -> None:
        summary = module_under_test.build_summary(
            [
                {"ticker": "000988.SZ", "status": "cache_written", "message": ""},
                {"ticker": "002384.SZ", "status": "cache_hit", "message": ""},
                {"ticker": "300476.SZ", "status": "failed", "message": "boom"},
            ]
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["cache_written"], 1)
        self.assertEqual(summary["cache_hit"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_print_results_emits_per_ticker_rows_and_summary(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            module_under_test.print_results(
                [
                    {"ticker": "000988.SZ", "status": "cache_written", "message": ""},
                    {"ticker": "002384.SZ", "status": "cache_hit", "message": ""},
                    {"ticker": "300476.SZ", "status": "failed", "message": "boom"},
                ]
            )
        output = buffer.getvalue()
        self.assertIn("[cache_written] 000988.SZ", output)
        self.assertIn("[cache_hit] 002384.SZ", output)
        self.assertIn("[failed] 300476.SZ - boom", output)
        self.assertIn("Summary:", output)
        self.assertIn("- total: 3", output)


if __name__ == "__main__":
    unittest.main()
