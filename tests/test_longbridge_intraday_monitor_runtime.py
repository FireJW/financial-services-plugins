#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
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
RUNTIME_PATH = SCRIPT_DIR / "longbridge_intraday_monitor_runtime.py"


def load_monitor_module() -> Any:
    if not RUNTIME_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("longbridge_intraday_monitor_runtime", RUNTIME_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_monitor_callable() -> Any:
    module = load_monitor_module()
    if module is None:
        return None
    return getattr(module, "run_longbridge_intraday_monitor", None)


def run_monitor(request: dict[str, Any], runner: Any) -> dict[str, Any]:
    monitor = load_monitor_callable()
    if monitor is None:
        return {}
    return monitor(request, runner=runner)


class FakeLongbridgeRunner:
    def __init__(
        self,
        *,
        closed: bool = False,
        non_trading_day: bool = False,
        capital_series: bool = False,
        fail_commands: set[str] | None = None,
    ) -> None:
        self.closed = closed
        self.non_trading_day = non_trading_day
        self.capital_series = capital_series
        self.fail_commands = fail_commands or set()
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        timeout_seconds: int = 20,
    ) -> Any:
        del env, timeout_seconds
        self.calls.append(list(args))
        command = args[0] if args else ""
        if command in self.fail_commands:
            raise RuntimeError(f"{command} unavailable")
        if args == ["market-status", "--format", "json"]:
            return {
                "markets": [
                    {
                        "market": "HK",
                        "status": "Closed" if self.closed else "Open",
                        "trade_status": "closed" if self.closed else "trading",
                    }
                ]
            }
        if args == ["trading", "session", "--format", "json"]:
            return {
                "sessions": [
                    {
                        "market": "HK",
                        "session": "intraday",
                        "begin_time": "09:30",
                        "end_time": "16:00",
                    }
                ]
            }
        if args[:3] == ["trading", "days", "HK"]:
            return {"trading_days": [] if self.non_trading_day else ["2026-05-02"], "half_trading_days": []}
        if args[:1] == ["intraday"]:
            symbol = args[1]
            latest = {"700.HK": "101.20", "9988.HK": "88.00"}.get(symbol, "10.00")
            return [
                {"timestamp": "2026-05-02 09:31:00", "price": "99.80", "volume": "1000", "turnover": "99800"},
                {"timestamp": "2026-05-02 10:30:00", "price": latest, "volume": "3500", "turnover": "354200"},
            ]
        if args[:1] == ["capital"]:
            symbol = args[1]
            if self.capital_series:
                return [
                    {"timestamp": "2026-05-02 09:30:00", "net_inflow": "-100000", "inflow": "200000", "outflow": "300000"},
                    {"timestamp": "2026-05-02 10:30:00", "net_inflow": "750000", "inflow": "1250000", "outflow": "500000"},
                ]
            return {
                "symbol": symbol,
                "net_inflow": "5000000" if symbol == "700.HK" else "-1200000",
                "large_order_inflow": "3200000",
                "large_order_outflow": "900000",
            }
        if args[:1] == ["anomaly"]:
            symbol = args[args.index("--symbol") + 1]
            if symbol == "700.HK":
                return [{"symbol": symbol, "type": "volume_spike", "description": "unusual volume"}]
            return []
        if args[:1] == ["trade-stats"]:
            return {
                "price_distribution": [
                    {"price": "101.20" if args[1] == "700.HK" else "88.00", "volume": "3500"}
                ]
            }
        raise AssertionError(f"unexpected args: {args}")


class LongbridgeIntradayMonitorRuntimeTests(unittest.TestCase):
    def test_cli_runner_resolver_adds_tradingagents_runtime_path(self) -> None:
        module = load_monitor_module()
        self.assertIsNotNone(module)
        bridge_dir = str(SCRIPT_DIR.parents[1] / "tradingagents-decision-bridge" / "scripts")
        original_path = list(sys.path)
        sys.modules.pop("tradingagents_longbridge_market", None)
        sys.path = [item for item in sys.path if item != bridge_dir]
        try:
            runner = module.load_longbridge_cli_runner()
        finally:
            sys.path = original_path

        self.assertTrue(callable(runner))

    def test_run_longbridge_intraday_monitor_uses_read_only_json_cli_args(self) -> None:
        runner = FakeLongbridgeRunner()

        result = run_monitor(
            {
                "tickers": ["700.HK"],
                "analysis_date": "2026-05-02",
                "market": "HK",
                "session": "all",
                "anomaly_count": 7,
                "plan_levels": {"700.HK": {"trigger_price": 100, "stop_loss": 95, "abandon_below": 90}},
            },
            runner,
        )

        self.assertIn(["market-status", "--format", "json"], runner.calls)
        self.assertIn(["trading", "session", "--format", "json"], runner.calls)
        self.assertIn(
            ["trading", "days", "HK", "--start", "2026-05-02", "--end", "2026-05-02", "--format", "json"],
            runner.calls,
        )
        self.assertIn(
            ["intraday", "700.HK", "--session", "all", "--date", "20260502", "--format", "json"],
            runner.calls,
        )
        self.assertIn(["capital", "700.HK", "--flow", "--format", "json"], runner.calls)
        self.assertIn(["anomaly", "--market", "HK", "--symbol", "700.HK", "--count", "7", "--format", "json"], runner.calls)
        self.assertIn(["trade-stats", "700.HK", "--format", "json"], runner.calls)
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["side_effects"], "none")

    def test_market_closed_or_non_trading_day_blocks_plan_status(self) -> None:
        runner = FakeLongbridgeRunner(closed=True, non_trading_day=True)

        result = run_monitor(
            {
                "tickers": ["700.HK"],
                "analysis_date": "2026-05-02",
                "market": "HK",
                "plan_levels": {"700.HK": {"trigger_price": 100, "stop_loss": 95}},
            },
            runner,
        )

        symbol = result["monitored_symbols"][0]
        self.assertFalse(result["intraday_monitor"]["trading_allowed"])
        self.assertEqual(symbol["plan_status"]["state"], "blocked")
        self.assertIn("market_closed", result["risk_flags"])
        self.assertIn("non_trading_day", result["risk_flags"])

    def test_latest_intraday_price_triggers_or_invalidates_plan_levels(self) -> None:
        runner = FakeLongbridgeRunner()

        result = run_monitor(
            {
                "tickers": ["700.HK", "9988.HK"],
                "analysis_date": "2026-05-02",
                "market": "HK",
                "plan_levels": {
                    "700.HK": {"trigger_price": 100, "stop_loss": 95, "abandon_below": 90},
                    "9988.HK": {"trigger_price": 95, "stop_loss": 89, "abandon_below": 88.5},
                },
            },
            runner,
        )

        by_symbol = {item["symbol"]: item for item in result["monitored_symbols"]}
        self.assertEqual(by_symbol["700.HK"]["plan_status"]["state"], "triggered")
        self.assertTrue(by_symbol["700.HK"]["plan_status"]["triggered"])
        self.assertTrue(by_symbol["700.HK"]["capital_flow"]["confirms"])
        self.assertTrue(by_symbol["700.HK"]["abnormal_volume"]["exists"])
        self.assertEqual(by_symbol["9988.HK"]["plan_status"]["state"], "invalidated")
        self.assertTrue(by_symbol["9988.HK"]["plan_status"]["invalidated"])

    def test_endpoint_failure_is_recorded_without_blocking_other_symbol_data(self) -> None:
        runner = FakeLongbridgeRunner(fail_commands={"capital"})

        result = run_monitor(
            {
                "tickers": ["700.HK"],
                "analysis_date": "2026-05-02",
                "market": "HK",
                "plan_levels": {"700.HK": {"trigger_price": 100, "stop_loss": 95}},
            },
            runner,
        )

        symbol = result["monitored_symbols"][0]
        self.assertTrue(symbol["data_coverage"]["intraday_available"])
        self.assertFalse(symbol["data_coverage"]["capital_available"])
        self.assertTrue(symbol["data_coverage"]["anomaly_available"])
        self.assertTrue(symbol["data_coverage"]["trade_stats_available"])
        self.assertEqual(symbol["plan_status"]["state"], "triggered")
        self.assertEqual(result["unavailable"][0]["command"], "capital")

    def test_capital_flow_series_and_trade_stats_are_normalized(self) -> None:
        runner = FakeLongbridgeRunner(capital_series=True)

        result = run_monitor(
            {
                "tickers": ["700.HK"],
                "analysis_date": "2026-05-02",
                "market": "HK",
                "plan_levels": {"700.HK": {"trigger_price": 100, "stop_loss": 95}},
            },
            runner,
        )

        symbol = result["monitored_symbols"][0]
        self.assertTrue(symbol["capital_flow"]["confirms"])
        self.assertEqual(symbol["capital_flow"]["latest_net_inflow"], 750000.0)
        self.assertEqual(symbol["capital_flow"]["cumulative_net_inflow"], 650000.0)
        self.assertEqual(symbol["trade_stats"]["dominant_price"], 101.2)
        self.assertEqual(symbol["trade_stats"]["dominant_volume"], 3500.0)
        self.assertEqual(symbol["trade_stats"]["total_volume"], 3500.0)
        self.assertEqual(len(symbol["trade_stats"]["distribution"]), 1)


if __name__ == "__main__":
    unittest.main()
