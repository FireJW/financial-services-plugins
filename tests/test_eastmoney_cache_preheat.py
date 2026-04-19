#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
