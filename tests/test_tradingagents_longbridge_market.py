#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_longbridge_market import (
    fetch_daily_bars,
    fetch_quote_snapshot,
    get_stock_data,
    normalize_longbridge_symbol,
)


def fake_runner(args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
    del env, timeout_seconds
    if args[:2] == ["kline", "AAPL.US"]:
        return [
            {
                "close": "281.50",
                "high": "284.00",
                "low": "279.25",
                "open": "280.00",
                "timestamp": "2026-04-29 00:00:00",
                "turnover": "123456.78",
                "volume": 1000,
            },
            {
                "close": "284.90",
                "high": "287.21",
                "low": "278.37",
                "open": "279.00",
                "timestamp": "2026-04-30 00:00:00",
                "turnover": "456789.01",
                "volume": 2000,
            },
        ]
    if args[:3] == ["quote", "--format", "json"]:
        return [
            {
                "high": "287.210",
                "last": "284.900",
                "low": "278.370",
                "open": "279.000",
                "prev_close": "271.350",
                "status": "Normal",
                "symbol": "AAPL.US",
                "turnover": "12161395802.307",
                "volume": 42959352,
            }
        ]
    raise AssertionError(f"unexpected args: {args}")


class TradingAgentsLongbridgeMarketTests(unittest.TestCase):
    def test_normalize_longbridge_symbol_matches_cli_format(self) -> None:
        self.assertEqual(normalize_longbridge_symbol("AAPL"), "AAPL.US")
        self.assertEqual(normalize_longbridge_symbol("700.HK"), "00700.HK")
        self.assertEqual(normalize_longbridge_symbol("601600.SS"), "601600.SH")
        self.assertEqual(normalize_longbridge_symbol("002837.SZ"), "002837.SZ")

    def test_fetch_quote_snapshot_parses_cli_quote_json(self) -> None:
        snapshot = fetch_quote_snapshot("AAPL", runner=fake_runner)

        self.assertEqual(snapshot["symbol"], "AAPL.US")
        self.assertEqual(snapshot["last_price"], 284.9)
        self.assertEqual(snapshot["prev_close"], 271.35)
        self.assertEqual(snapshot["volume"], 42959352)
        self.assertEqual(snapshot["source"], "longbridge_cli")

    def test_fetch_daily_bars_parses_cli_history_rows(self) -> None:
        rows = fetch_daily_bars(
            "AAPL",
            "2026-04-29",
            "2026-04-30",
            runner=fake_runner,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["trade_date"], "2026-04-30")
        self.assertEqual(rows[-1]["close"], 284.9)
        self.assertEqual(rows[-1]["vol"], 2000.0)
        self.assertEqual(rows[-1]["amount"], 456789.01)

    def test_get_stock_data_renders_tradingagents_csv(self) -> None:
        report = get_stock_data(
            "AAPL",
            "2026-04-29",
            "2026-04-30",
            runner=fake_runner,
        )

        self.assertIn("# Stock data for AAPL.US", report)
        self.assertIn("Date,Open,High,Low,Close,PreClose,Change,PctChg,Volume,Amount", report)
        self.assertIn("2026-04-30,279.0000,287.2100,278.3700,284.9000", report)


if __name__ == "__main__":
    unittest.main()
