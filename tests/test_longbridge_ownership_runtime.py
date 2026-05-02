#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "longbridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from longbridge_ownership_runtime import load_json as load_ownership_json
from longbridge_ownership_runtime import main as ownership_main
from longbridge_ownership_runtime import run_longbridge_ownership_analysis


class RecordingOwnershipRunner:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None, int]] = []
        self.failures = failures or set()

    def __call__(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        timeout_seconds: int = 20,
    ) -> Any:
        self.calls.append((list(args), env, timeout_seconds))
        command = args[0] if args else ""
        if command in self.failures:
            raise RuntimeError(f"{command} blocked for this account")
        if command == "insider-trades":
            return {
                "items": [
                    {
                        "symbol": args[1],
                        "insider": "Example CFO",
                        "transaction_type": "SELL",
                        "shares": "15000",
                        "price": "212.40",
                        "transaction_date": "2026-04-28",
                    }
                ]
            }
        if command == "short-positions":
            return {
                "items": [
                    {
                        "symbol": args[1],
                        "short_ratio": "18.6",
                        "days_to_cover": "7.4",
                        "settlement_date": "2026-04-15",
                    }
                ]
            }
        if command == "investors":
            if len(args) > 1 and args[1].isdigit():
                return {
                    "cik": args[1],
                    "holdings": [
                        {
                            "symbol": "TSLA.US",
                            "name": "Tesla",
                            "value": "125000000",
                            "shares": "400000",
                            "weight": "3.2",
                        }
                    ],
                }
            return {
                "items": [
                    {
                        "cik": "0001067983",
                        "manager": "Berkshire Hathaway",
                        "aum": "347000000000",
                    }
                ]
            }
        raise AssertionError(f"unexpected args: {args}")


class LongbridgeOwnershipRuntimeTests(unittest.TestCase):
    def test_load_json_accepts_control_character_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_bytes(b'{"tickers":["TSLA.US"],"note":"raw \x01 control"}')
            payload = load_ownership_json(path)

        self.assertEqual(payload["note"], "raw \x01 control")

    def test_cli_help_is_available_without_running_longbridge(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            ownership_main(["--help"])

        self.assertEqual(raised.exception.code, 0)

    def test_run_ownership_analysis_fetches_us_layers_with_limits_and_read_only_shape(self) -> None:
        runner = RecordingOwnershipRunner()

        result = run_longbridge_ownership_analysis(
            {
                "tickers": ["TSLA.US"],
                "insider_count": 7,
                "short_count": 9,
                "investor_ciks": ["0001067983"],
                "investor_top": 3,
            },
            runner=runner,
            env={"LONGBRIDGE_LANGUAGE": "en"},
        )

        call_args = [call[0] for call in runner.calls]
        self.assertIn(["insider-trades", "TSLA.US", "--count", "7", "--format", "json"], call_args)
        self.assertIn(["short-positions", "TSLA.US", "--count", "9", "--format", "json"], call_args)
        self.assertIn(["investors", "--top", "3", "--format", "json"], call_args)
        self.assertIn(["investors", "0001067983", "--top", "3", "--format", "json"], call_args)
        self.assertTrue(all(call[1] == {"LONGBRIDGE_LANGUAGE": "en"} for call in runner.calls))
        self.assertTrue(all(call[2] == 20 for call in runner.calls))
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["side_effects"], "none")
        self.assertIn("TSLA.US", result["ownership_risk_analysis"])
        self.assertIn("insider_sell_activity", {item["flag"] for item in result["risk_flags"]})
        self.assertIn("high_short_interest", {item["flag"] for item in result["risk_flags"]})
        self.assertTrue(result["data_coverage"]["insider_trades"]["TSLA.US"])
        self.assertTrue(result["data_coverage"]["short_positions"]["TSLA.US"])
        self.assertTrue(result["data_coverage"]["institutional_investors"]["ranking"])
        self.assertTrue(result["data_coverage"]["institutional_investors"]["0001067983"])

    def test_run_ownership_analysis_records_unavailable_when_optional_command_fails(self) -> None:
        runner = RecordingOwnershipRunner(failures={"short-positions"})

        result = run_longbridge_ownership_analysis(
            {
                "tickers": ["TSLA.US"],
                "insider_count": 2,
                "short_count": 4,
            },
            runner=runner,
        )

        self.assertIn(["short-positions", "TSLA.US", "--count", "4", "--format", "json"], [call[0] for call in runner.calls])
        self.assertFalse(result["data_coverage"]["short_positions"]["TSLA.US"])
        self.assertEqual(result["short_positions"]["TSLA.US"], [])
        self.assertTrue(
            any(
                item["command"] == "short-positions"
                and item["symbol"] == "TSLA.US"
                and "blocked" in item["reason"]
                for item in result["unavailable"]
            )
        )
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["side_effects"], "none")

    def test_run_ownership_analysis_skips_non_us_symbols_for_us_only_endpoints(self) -> None:
        runner = RecordingOwnershipRunner()

        result = run_longbridge_ownership_analysis(
            {
                "tickers": ["TSLA.US", "700.HK", "600519.SH"],
                "insider_count": 5,
                "short_count": 5,
                "investor_top": 2,
            },
            runner=runner,
        )

        call_args = [call[0] for call in runner.calls]
        self.assertIn(["insider-trades", "TSLA.US", "--count", "5", "--format", "json"], call_args)
        self.assertIn(["short-positions", "TSLA.US", "--count", "5", "--format", "json"], call_args)
        self.assertNotIn(["insider-trades", "700.HK", "--count", "5", "--format", "json"], call_args)
        self.assertNotIn(["short-positions", "600519.SH", "--count", "5", "--format", "json"], call_args)
        self.assertIn(["investors", "--top", "2", "--format", "json"], call_args)
        self.assertFalse(result["data_coverage"]["insider_trades"]["700.HK"])
        self.assertFalse(result["data_coverage"]["short_positions"]["600519.SH"])
        self.assertTrue(
            any(item["symbol"] == "700.HK" and item["command"] == "insider-trades" for item in result["unavailable"])
        )
        self.assertTrue(
            any(item["symbol"] == "600519.SH" and item["command"] == "short-positions" for item in result["unavailable"])
        )


if __name__ == "__main__":
    unittest.main()
