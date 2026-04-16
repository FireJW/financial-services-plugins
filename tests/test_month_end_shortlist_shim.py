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

import month_end_shortlist as cli_module
import month_end_shortlist_runtime as runtime_module


class MonthEndShortlistShimTests(unittest.TestCase):
    def test_runtime_exports_normalize_request(self) -> None:
        self.assertTrue(callable(getattr(runtime_module, "normalize_request", None)))

    def test_cli_exports_main(self) -> None:
        self.assertTrue(callable(getattr(cli_module, "main", None)))


if __name__ == "__main__":
    unittest.main()
