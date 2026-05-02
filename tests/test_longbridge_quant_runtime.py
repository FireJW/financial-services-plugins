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

from longbridge_quant_runtime import load_json as load_quant_json
from longbridge_quant_runtime import main as quant_main
from longbridge_quant_runtime import run_longbridge_quant_analysis


class RecordingQuantRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None, int]] = []

    def __call__(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        timeout_seconds: int = 20,
    ) -> Any:
        self.calls.append((list(args), env, timeout_seconds))
        script = args[args.index("--script") + 1]
        symbol = args[2]
        if "FAIL_ME" in script:
            raise RuntimeError("server rejected script")
        if "Bearish" in script:
            return {
                "symbol": symbol,
                "series": {"pressure": [0.4, -0.2, -1.3]},
                "plots": [{"name": "bearish_pressure", "values": [0.4, -0.2, -1.3]}],
            }
        return {
            "symbol": symbol,
            "series": {"momentum": [-0.1, 0.3, 1.2]},
            "plots": [{"name": "momentum", "values": [-0.1, 0.3, 1.2]}],
            "values": {"alignment": 1.0},
        }


class LongbridgeQuantRuntimeTest(unittest.TestCase):
    def test_load_json_accepts_control_character_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_bytes(b'{"tickers":["700.HK"],"note":"raw \x01 control","start":"2024-01-01","end":"2024-06-30"}')
            payload = load_quant_json(path)

        self.assertEqual(payload["note"], "raw \x01 control")

    def test_cli_help_is_available_without_running_longbridge(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            quant_main(["--help"])

        self.assertEqual(raised.exception.code, 0)

    def test_custom_script_calls_quant_run_with_input_and_json_format(self) -> None:
        runner = RecordingQuantRunner()
        script = "indicator('Momentum')\nplot(close - close[5])"

        result = run_longbridge_quant_analysis(
            {
                "tickers": ["700.HK"],
                "period": "1h",
                "start": "2024-01-01",
                "end": "2024-06-30",
                "quant_scripts": [{"name": "custom_momentum", "script": script, "input": [14, 2.0]}],
            },
            runner=runner,
            env={"LONGPORT_REGION": "HK"},
        )

        self.assertEqual(
            runner.calls[0],
            (
                [
                    "quant",
                    "run",
                    "700.HK",
                    "--period",
                    "1h",
                    "--start",
                    "2024-01-01",
                    "--end",
                    "2024-06-30",
                    "--script",
                    script,
                    "--input",
                    "[14,2.0]",
                    "--format",
                    "json",
                ],
                {"LONGPORT_REGION": "HK"},
                30,
            ),
        )
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["side_effects"], "none")
        self.assertEqual(result["quant_analysis"]["700.HK"]["custom_momentum"]["alignment"], "bullish")
        self.assertEqual(result["signal_alignment"]["overall"], "bullish")
        self.assertIn("custom_momentum", result["indicators"]["700.HK"])

    def test_default_scripts_are_used_when_request_omits_scripts(self) -> None:
        runner = RecordingQuantRunner()

        result = run_longbridge_quant_analysis(
            {"tickers": ["TSLA.US"], "start": "2024-01-01", "end": "2024-12-31"},
            runner=runner,
        )

        self.assertGreaterEqual(len(runner.calls), 2)
        self.assertTrue(all(call[0][:3] == ["quant", "run", "TSLA.US"] for call in runner.calls))
        self.assertTrue(all("--script" in call[0] for call in runner.calls))
        self.assertIn("trend_momentum", result["quant_analysis"]["TSLA.US"])
        self.assertIn("rsi_bias", result["quant_analysis"]["TSLA.US"])
        self.assertEqual(result["data_coverage"]["successful_runs"], len(runner.calls))

    def test_bearish_series_normalizes_to_bearish_alignment(self) -> None:
        runner = RecordingQuantRunner()

        result = run_longbridge_quant_analysis(
            {
                "tickers": ["AAPL.US"],
                "start": "2024-01-01",
                "end": "2024-12-31",
                "indicators": [{"name": "bearish_pressure", "script": "indicator('Bearish')\nplot(-1)"}],
            },
            runner=runner,
        )

        self.assertEqual(result["quant_analysis"]["AAPL.US"]["bearish_pressure"]["alignment"], "bearish")
        self.assertEqual(result["signal_alignment"]["overall"], "bearish")

    def test_unavailable_records_failed_symbol_script_and_continues(self) -> None:
        runner = RecordingQuantRunner()

        result = run_longbridge_quant_analysis(
            {
                "tickers": ["600111.SH"],
                "start": "2024-01-01",
                "end": "2024-12-31",
                "quant_scripts": [
                    {"name": "ok_momentum", "script": "indicator('OK')\nplot(1)"},
                    {"name": "bad_script", "script": "indicator('FAIL_ME')\nplot(close)"},
                ],
            },
            runner=runner,
        )

        self.assertEqual(len(runner.calls), 2)
        self.assertIn("ok_momentum", result["quant_analysis"]["600111.SH"])
        self.assertNotIn("bad_script", result["quant_analysis"]["600111.SH"])
        self.assertEqual(result["unavailable"][0]["symbol"], "600111.SH")
        self.assertEqual(result["unavailable"][0]["script_name"], "bad_script")
        self.assertIn("server rejected script", result["unavailable"][0]["reason"])
        self.assertEqual(result["data_coverage"]["failed_runs"], 1)
        self.assertEqual(result["signal_alignment"]["by_symbol"]["600111.SH"]["overall"], "bullish")


if __name__ == "__main__":
    unittest.main()
