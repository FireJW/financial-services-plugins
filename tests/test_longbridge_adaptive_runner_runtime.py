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
    / "longbridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from longbridge_adaptive_runner_runtime import (
    build_safe_longbridge_runner,
    infer_adaptive_request,
    run_longbridge_adaptive_task,
)


def _daily_rows(symbol: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(70):
        close = 180.0 + index
        rows.append(
            {
                "symbol": symbol,
                "timestamp": f"2026-03-{(index % 28) + 1:02d}",
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "prev_close": close - 1,
                "volume": 1_000_000 + index * 10_000,
                "turnover": 100_000_000 + index * 1_000_000,
            }
        )
    return rows


class RecordingLongbridgeRunner:
    def __init__(self) -> None:
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
        symbol = args[-1] if args[:3] == ["quote", "--format", "json"] else (args[1] if len(args) > 1 else "")
        if command == "quote":
            return [
                {
                    "symbol": symbol,
                    "name": symbol,
                    "last": "250.00",
                    "open": "244.00",
                    "high": "252.00",
                    "low": "243.00",
                    "prev_close": "242.00",
                    "volume": "50000000",
                    "turnover": "12500000000",
                    "status": "Normal",
                }
            ]
        if command == "kline":
            return _daily_rows(args[1])
        if command == "news":
            if args[1:2] == ["detail"]:
                return {"id": args[2], "title": "AI catalyst", "content": "Full article text"}
            return [{"id": "n1", "title": "AI catalyst lifts demand", "published_at": "2026-05-06T01:00:00Z"}]
        if command == "topic":
            return [{"id": "t1", "title": "Momentum discussion", "description": "Strong inflow"}]
        if command == "filing":
            if args[1:2] == ["detail"]:
                return {"id": args[3], "title": "10-Q", "content": "Filing details"}
            return [{"id": "f1", "title": "10-Q", "publish_at": "2026-05-05T00:00:00Z"}]
        if command == "valuation":
            return {"overview": {"metrics": {"pe": {"metric": "35", "industry_median": "40"}}}}
        if command == "institution-rating":
            return {"instratings": {"recommend": "buy", "target": "280"}}
        if command == "forecast-eps":
            return {"items": [{"forecast_eps_mean": "5.20", "institution_up": 2, "institution_total": 3}]}
        if command == "consensus":
            return {"list": [{"period_text": "Q1 2026", "details": [{"key": "eps", "comp": "beat_est"}]}]}
        if command == "company":
            return {"symbol": args[1], "name": args[1], "industry": "Semiconductors", "employees": "30000"}
        if command == "industry-valuation":
            return {"industry": "Semiconductors", "pe": "35", "industry_median": "40", "percentile": "0.45"}
        if command == "shareholder":
            return [{"name": "Founder Trust", "owned": "12.5", "type": "founder"}]
        if command == "fund-holder":
            return [{"name": "AI ETF", "weight": "2.4", "shares": "1000000"}]
        if command == "corp-action":
            return []
        if command == "constituent":
            return [{"symbol": "NVDA.US", "name": "NVIDIA", "weight": "5.5"}]
        if command == "executive":
            return [{"name": "Jensen Huang", "title": "CEO"}, {"name": "Colette Kress", "title": "CFO"}]
        if command == "invest-relation":
            return {"items": [{"title": "Investor day", "published_at": "2026-05-01", "url": "https://example.test"}]}
        if command == "financial-report":
            return {"items": [{"net_income": "1200", "operating_cash_flow": "1500"}]}
        if command == "finance-calendar":
            return {"items": [{"event_date": "2026-05-07", "title": "earnings"}]}
        if command == "dividend":
            return {"items": []}
        if command == "operating":
            return {"items": [{"revenue": "10000"}]}
        if command == "insider-trades":
            return [{"symbol": args[1], "transaction_type": "BUY", "amount": "100000"}]
        if command == "short-positions":
            return [{"symbol": args[1], "short_ratio": "2.1", "days_to_cover": "1.4"}]
        if command == "investors":
            return {"items": [{"cik": "0001067983", "name": "Berkshire Hathaway", "aum": "1000000000"}]}
        if command == "market-status":
            return {"markets": [{"market": "US", "status": "open"}]}
        if command == "static":
            return {"symbol": args[1], "market": "US", "name": args[1]}
        if command == "calc-index":
            return {"symbol": args[1], "pe": "35.2", "pb": "8.1", "mktcap": "1200000000"}
        if command == "security-list":
            return {"items": [{"symbol": args[1], "eligible": True}]}
        if command == "option":
            return {"symbol": args[2], "items": [{"expiry": "2026-06-19", "strike": "300", "iv": "0.42", "oi": "1000"}]}
        if command == "warrant":
            if args[1:2] == ["quote"]:
                return {"symbol": args[2], "premium": "5.1", "effective_leverage": "3.2"}
            if args[1:2] == ["issuers"]:
                return {"items": [{"issuer_id": "1", "name": "Issuer"}]}
            return {"symbol": args[1], "items": [{"code": "12345.HK", "premium": "5.1"}]}
        if command == "brokers":
            return {"symbol": args[1], "brokers": [{"id": "1", "name": "Broker A"}]}
        if command == "broker-holding":
            if args[1:2] == ["detail"]:
                return {"symbol": args[2], "detail": [{"broker_id": "1", "shares": "1000000"}]}
            if args[1:2] == ["daily"]:
                return {"symbol": args[2], "broker_id": args[4], "change": "50000"}
            return {"symbol": args[1], "items": [{"broker_id": "1", "holding": "1000000"}]}
        if command == "ah-premium":
            if args[1:2] == ["intraday"]:
                return {"symbol": args[2], "premium": "8.2", "time": "15:59"}
            return {"symbol": args[1], "premium": "8.0"}
        if command == "participants":
            return {"items": [{"id": "1", "name": "Broker A"}]}
        if command == "trading":
            if args[1:2] == ["days"]:
                return {"trading_days": [{"date": "2026-05-06", "is_trading_day": True}]}
            return {"sessions": [{"market": "US", "status": "open"}]}
        if command == "intraday":
            return [{"time": "2026-05-06T15:59:00Z", "price": "251.00", "volume": "1000"}]
        if command == "capital":
            return {"large_order_inflow": "2000000", "large_order_outflow": "800000"}
        if command == "anomaly":
            return [{"type": "volume", "description": "abnormal volume"}]
        if command == "trade-stats":
            return {"total_volume": "2000", "dominant_price": "251.00"}
        if command == "market-temp":
            return {"market": "US", "temperature": 72}
        if command == "portfolio":
            return {"overview": {"total_asset": "100000", "total_pl": "1200"}}
        if command == "assets":
            return {"overview": {"net_assets": "100000", "buy_power": "20000"}}
        if command == "positions":
            return [{"symbol": "NVDA.US", "quantity": "10", "market_value": "2500"}]
        if command == "order":
            order_symbol = args[args.index("--symbol") + 1] if "--symbol" in args else ""
            if args[1:2] == ["executions"]:
                return [{"symbol": order_symbol, "price": "250.00", "quantity": "1"}]
            return [{"symbol": order_symbol, "side": "buy", "status": "filled"}]
        if command == "cash-flow":
            return [{"currency": "USD", "amount": "1000", "direction": "in"}]
        if command == "profit-analysis":
            return {"summary": {"realized_pl": "1200", "unrealized_pl": "800"}}
        if command == "statement":
            return [{"type": "daily", "date": "2026-05-06", "file_key": "daily-1"}]
        raise AssertionError(f"Unexpected command: {args}")


class LongbridgeAdaptiveRunnerRuntimeTests(unittest.TestCase):
    def test_cmd_wrapper_uses_repo_local_python_runtime(self) -> None:
        wrapper = SCRIPT_DIR / "run_longbridge_adaptive.cmd"

        content = wrapper.read_text(encoding="utf-8")

        self.assertIn("python-local.cmd", content)
        self.assertIn("longbridge_adaptive_runner_runtime.py", content)

    def test_infers_deep_stock_analysis_layers_from_prompt(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "[$longbridge] 查 NVDA.US 最新价、新闻催化、filing、insider、investors 和资金面",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertEqual(inferred["task_type"], "stock_analysis")
        self.assertEqual(inferred["tickers"], ["NVDA.US"])
        self.assertIn("catalyst", inferred["analysis_layers"])
        self.assertIn("financial_event", inferred["analysis_layers"])
        self.assertIn("ownership_risk", inferred["analysis_layers"])
        self.assertIn("intraday", inferred["analysis_layers"])

    def test_infers_derivative_event_risk_layer_from_prompt_aliases(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "Check NVDA.US options IV OI call put event risk",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertIn("derivative_event_risk", inferred["analysis_layers"])

    def test_infers_governance_structure_layer_from_prompt_aliases(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "Review NVDA.US governance, shareholder control and ETF fund exposure",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertIn("governance_structure", inferred["analysis_layers"])

    def test_infers_governance_structure_layer_from_chinese_prompt_aliases(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "分析 NVDA.US 治理结构、高管、投资者关系、控股结构和基金暴露",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertIn("governance_structure", inferred["analysis_layers"])

    def test_infers_account_review_plus_layer_from_review_prompt_aliases(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "复盘 NVDA.US 订单历史、成交、现金流、收益分析和日结单",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertEqual(inferred["task_type"], "review")
        self.assertIn("account_review_plus", inferred["analysis_layers"])

    def test_infers_execution_preflight_layer_from_trading_plan_prompt_aliases(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "Build NVDA.US trading plan with execution preflight, market status, trading days and overnight eligibility",
                "tickers": ["NVDA.US"],
            }
        )

        self.assertEqual(inferred["task_type"], "trading_plan")
        self.assertIn("execution_preflight", inferred["analysis_layers"])

    def test_infers_hk_microstructure_from_three_digit_hk_symbol_prompt(self) -> None:
        inferred = infer_adaptive_request(
            {
                "prompt": "给 700.HK 做港股券商持仓、AH溢价和微观结构分析",
            }
        )

        self.assertEqual(inferred["task_type"], "stock_analysis")
        self.assertEqual(inferred["tickers"], ["700.HK"])
        self.assertIn("hk_microstructure", inferred["analysis_layers"])
        self.assertNotIn("portfolio", inferred["analysis_layers"])

    def test_stock_analysis_runs_adapted_longbridge_screen(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "prompt": "查 NVDA.US 新闻、filing、insider、investors 和资金面",
                "tickers": ["NVDA.US"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertEqual(result["schema_version"], "longbridge_adaptive_runner/v1")
        self.assertEqual(result["task_type"], "stock_analysis")
        self.assertIn("longbridge-screen", result["workflow_steps"])
        self.assertIn("screen_result", result["outputs"])
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["side_effects"], "none")
        calls = [" ".join(call[:2]) for call in runner.calls]
        self.assertIn("news NVDA.US", calls)
        self.assertIn("filing NVDA.US", calls)
        self.assertIn("insider-trades NVDA.US", calls)
        self.assertIn("investors --top", calls)

    def test_trading_plan_combines_screen_and_plan_artifact(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "trading_plan",
                "prompt": "给 NVDA.US 生成交易计划，结合催化、估值和所有权风险",
                "tickers": ["NVDA.US"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertEqual(result["task_type"], "trading_plan")
        self.assertIn("longbridge-screen", result["workflow_steps"])
        self.assertIn("longbridge-trading-plan", result["workflow_steps"])
        plan = result["outputs"]["trading_plan_report"]
        self.assertEqual(plan["schema_version"], "longbridge_trading_plan/v1")
        self.assertFalse(plan["should_apply"])
        self.assertEqual(plan["side_effects"], "none")
        self.assertFalse(plan["position_sizing_guidance"]["order_allowed"])

    def test_review_builds_postclose_actuals_from_quotes_when_missing(self) -> None:
        runner = RecordingLongbridgeRunner()
        plan_report = {
            "schema_version": "longbridge_trading_plan/v1",
            "plan_date": "2026-05-06",
            "session_type": "premarket",
            "market_context": {},
            "candidates": [
                {
                    "symbol": "NVDA.US",
                    "name": "NVDA.US",
                    "levels": {"trigger_price": 248.0, "stop_loss": 240.0, "abandon_below": 238.0},
                }
            ],
        }

        result = run_longbridge_adaptive_task(
            {
                "task_type": "review",
                "prompt": "复盘 NVDA.US 交易计划",
                "plan_report": plan_report,
                "review_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertIn("longbridge quote actuals", result["workflow_steps"])
        review = result["outputs"]["postclose_review"]
        self.assertEqual(review["schema_version"], "longbridge_trading_plan_review/v1")
        self.assertEqual(review["summary"]["hit_trigger"], 1)
        self.assertFalse(review["should_apply"])
        self.assertEqual(review["side_effects"], "none")

    def test_portfolio_request_runs_only_read_only_account_snapshot(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "prompt": "查我的 portfolio、assets 和 positions，只读，不要下单",
            },
            runner=runner,
        )

        self.assertEqual(result["task_type"], "portfolio_review")
        self.assertEqual(result["outputs"]["account_snapshot"]["data_coverage"]["portfolio_available"], True)
        self.assertEqual(result["outputs"]["account_snapshot"]["data_coverage"]["assets_available"], True)
        self.assertEqual(result["outputs"]["account_snapshot"]["data_coverage"]["positions_available"], True)
        self.assertEqual(["portfolio", "--format", "json"], runner.calls[0])
        self.assertEqual(["assets", "--format", "json"], runner.calls[1])
        self.assertEqual(["positions", "--format", "json"], runner.calls[2])

    def test_portfolio_review_can_run_account_review_plus(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "portfolio_review",
                "tickers": ["NVDA.US"],
                "analysis_layers": ["account_review_plus"],
                "start": "2026-05-01",
                "end": "2026-05-06",
                "statement_limit": 3,
            },
            runner=runner,
        )

        self.assertIn("longbridge account-review-plus", result["workflow_steps"])
        review_plus = result["outputs"]["account_review_plus"]
        self.assertEqual(review_plus["order_history"][0]["symbol"], "NVDA.US")
        self.assertEqual(review_plus["order_executions"][0]["symbol"], "NVDA.US")
        self.assertTrue(review_plus["data_coverage"]["cash_flow_available"])
        self.assertTrue(review_plus["data_coverage"]["profit_analysis_available"])
        self.assertTrue(review_plus["data_coverage"]["statement_list_available"])
        self.assertEqual(
            ["order", "--history", "--start", "2026-05-01", "--end", "2026-05-06", "--symbol", "NVDA.US", "--format", "json"],
            runner.calls[3],
        )
        self.assertEqual(
            ["order", "executions", "--history", "--start", "2026-05-01", "--end", "2026-05-06", "--symbol", "NVDA.US", "--format", "json"],
            runner.calls[4],
        )
        self.assertIn(["cash-flow", "--format", "json"], runner.calls)
        self.assertIn(["profit-analysis", "--format", "json"], runner.calls)
        self.assertIn(["statement", "list", "--type", "daily", "--limit", "3", "--format", "json"], runner.calls)

    def test_review_can_run_account_review_plus_from_plan_symbols(self) -> None:
        runner = RecordingLongbridgeRunner()
        plan_report = {
            "schema_version": "longbridge_trading_plan/v1",
            "plan_date": "2026-05-06",
            "session_type": "premarket",
            "market_context": {},
            "candidates": [
                {
                    "symbol": "NVDA.US",
                    "name": "NVDA.US",
                    "levels": {"trigger_price": 248.0, "stop_loss": 240.0, "abandon_below": 238.0},
                }
            ],
        }

        result = run_longbridge_adaptive_task(
            {
                "task_type": "review",
                "analysis_layers": ["account_review_plus"],
                "plan_report": plan_report,
                "start": "2026-05-01",
                "end": "2026-05-06",
            },
            runner=runner,
        )

        self.assertIn("longbridge account-review-plus", result["workflow_steps"])
        self.assertEqual(result["outputs"]["account_review_plus"]["symbols"], ["NVDA.US"])
        self.assertIn(
            ["order", "--history", "--start", "2026-05-01", "--end", "2026-05-06", "--symbol", "NVDA.US", "--format", "json"],
            runner.calls,
        )

    def test_trading_plan_can_run_execution_preflight_for_us(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "trading_plan",
                "tickers": ["NVDA.US"],
                "analysis_layers": ["execution_preflight"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertIn("longbridge execution-preflight", result["workflow_steps"])
        preflight = result["outputs"]["preflight"]
        self.assertEqual(preflight["symbols"], ["NVDA.US"])
        self.assertTrue(preflight["data_coverage"]["static_available"])
        self.assertTrue(preflight["data_coverage"]["calc_index_available"])
        self.assertTrue(preflight["data_coverage"]["security_list_available"])
        self.assertTrue(preflight["data_coverage"]["market_status_available"])
        self.assertTrue(preflight["data_coverage"]["trading_session_available"])
        self.assertTrue(preflight["data_coverage"]["trading_days_available"])
        self.assertIn(["static", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(
            ["calc-index", "NVDA.US", "--fields", "pe,pb,dps_rate,turnover_rate,mktcap,volume_ratio,capital_flow", "--format", "json"],
            runner.calls,
        )
        self.assertIn(["security-list", "US", "--format", "json"], runner.calls)
        self.assertIn(["market-status", "--format", "json"], runner.calls)
        self.assertIn(["trading", "session", "--format", "json"], runner.calls)
        self.assertIn(["trading", "days", "US", "--start", "2026-05-06", "--end", "2026-05-06", "--format", "json"], runner.calls)

    def test_trading_plan_marks_us_only_preflight_unavailable_for_hk(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "trading_plan",
                "tickers": ["700.HK"],
                "analysis_layers": ["execution_preflight"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        preflight = result["outputs"]["preflight"]
        self.assertEqual(preflight["symbols"], ["700.HK"])
        self.assertFalse(preflight["data_coverage"]["security_list_available"])
        self.assertTrue(any(item["command"] == "security-list US" for item in preflight["unavailable"]))
        self.assertNotIn(["security-list", "US", "--format", "json"], runner.calls)

    def test_stock_analysis_runs_us_derivative_event_risk_options(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "stock_analysis",
                "tickers": ["NVDA.US"],
                "analysis_layers": ["derivative_event_risk"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertIn("longbridge derivative-event-risk", result["workflow_steps"])
        risk = result["outputs"]["derivative_event_risk"]
        self.assertEqual(risk["symbols"], ["NVDA.US"])
        self.assertTrue(risk["data_coverage"]["option_available"])
        self.assertFalse(risk["should_apply"])
        self.assertEqual(risk["side_effects"], "none")
        self.assertIn(["option", "chain", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(["option", "quote", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(["option", "volume", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(
            ["calc-index", "NVDA.US", "--fields", "iv,delta,gamma,theta,vega,oi,exp,strike,premium,effective_leverage", "--format", "json"],
            runner.calls,
        )

    def test_stock_analysis_runs_hk_derivative_event_risk_warrants(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "stock_analysis",
                "tickers": ["700.HK"],
                "analysis_layers": ["derivative_event_risk"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        risk = result["outputs"]["derivative_event_risk"]
        self.assertEqual(risk["symbols"], ["700.HK"])
        self.assertTrue(risk["data_coverage"]["warrant_available"])
        self.assertIn(["warrant", "700.HK", "--format", "json"], runner.calls)
        self.assertIn(["warrant", "quote", "700.HK", "--format", "json"], runner.calls)
        self.assertIn(["warrant", "issuers", "--format", "json"], runner.calls)
        self.assertIn(
            ["calc-index", "700.HK", "--fields", "iv,delta,gamma,theta,vega,oi,exp,strike,premium,effective_leverage", "--format", "json"],
            runner.calls,
        )
        self.assertFalse(any(call[:1] == ["option"] for call in runner.calls))

    def test_derivative_event_risk_records_unavailable_for_non_us_hk_market(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "stock_analysis",
                "tickers": ["000001.SZ"],
                "analysis_layers": ["derivative_event_risk"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        risk = result["outputs"]["derivative_event_risk"]
        self.assertFalse(risk["data_coverage"]["option_available"])
        self.assertFalse(risk["data_coverage"]["warrant_available"])
        self.assertTrue(any(item["command"] == "derivative_event_risk" for item in risk["unavailable"]))
        self.assertFalse(any(call[:1] == ["option"] for call in runner.calls))
        self.assertFalse(any(call[:1] == ["warrant"] for call in runner.calls))

    def test_trading_plan_runs_hk_microstructure_and_feeds_plan_evidence(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "trading_plan",
                "tickers": ["700.HK"],
                "analysis_layers": ["hk_microstructure"],
                "analysis_date": "2026-05-06",
                "broker_id": "1",
                "ah_premium_symbols": ["939.HK"],
            },
            runner=runner,
        )

        self.assertIn("longbridge hk-microstructure", result["workflow_steps"])
        microstructure = result["outputs"]["hk_microstructure"]
        self.assertEqual(microstructure["symbols"], ["700.HK"])
        self.assertTrue(microstructure["data_coverage"]["broker_holding_available"])
        self.assertTrue(microstructure["data_coverage"]["participants_available"])
        self.assertIn(["brokers", "700.HK", "--format", "json"], runner.calls)
        self.assertIn(["broker-holding", "700.HK", "--format", "json"], runner.calls)
        self.assertIn(["broker-holding", "detail", "700.HK", "--format", "json"], runner.calls)
        self.assertIn(["broker-holding", "daily", "700.HK", "--broker", "1", "--format", "json"], runner.calls)
        self.assertIn(["ah-premium", "939.HK", "--format", "json"], runner.calls)
        self.assertIn(["ah-premium", "intraday", "939.HK", "--format", "json"], runner.calls)
        self.assertIn(["participants", "--format", "json"], runner.calls)
        plan_evidence = result["outputs"]["trading_plan_report"]["candidates"][0]
        self.assertIn("hk_microstructure", plan_evidence)

    def test_hk_microstructure_records_coverage_gap_for_non_hk_symbols(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "stock_analysis",
                "tickers": ["NVDA.US"],
                "analysis_layers": ["hk_microstructure"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        microstructure = result["outputs"]["hk_microstructure"]
        self.assertFalse(microstructure["data_coverage"]["broker_holding_available"])
        self.assertTrue(any(item["command"] == "hk_microstructure" for item in microstructure["unavailable"]))
        self.assertFalse(any(call[:1] == ["brokers"] for call in runner.calls))
        self.assertFalse(any(call[:1] == ["broker-holding"] for call in runner.calls))
        self.assertFalse(any(call[:1] == ["ah-premium"] for call in runner.calls))
        self.assertFalse(any(call[:1] == ["participants"] for call in runner.calls))

    def test_stock_analysis_runs_governance_structure_layer_with_compact_output(self) -> None:
        runner = RecordingLongbridgeRunner()

        result = run_longbridge_adaptive_task(
            {
                "task_type": "stock_analysis",
                "tickers": ["NVDA.US"],
                "analysis_layers": ["governance_structure"],
                "theme_indexes": ["QQQ.US"],
                "analysis_date": "2026-05-06",
            },
            runner=runner,
        )

        self.assertIn("longbridge governance-structure", result["workflow_steps"])
        governance_output = result["outputs"]["governance_structure"]
        self.assertEqual(governance_output["symbols"], ["NVDA.US"])
        structure = governance_output["symbol_structures"][0]["governance_structure"]
        self.assertLessEqual(len(structure["executive_summary"]), 3)
        self.assertTrue(structure["data_coverage"]["executive_available"])
        self.assertTrue(structure["data_coverage"]["invest_relation_available"])
        self.assertIn("summary", structure)
        self.assertIn("key_flags", structure)
        self.assertIn(["executive", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(["invest-relation", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(["company", "NVDA.US", "--format", "json"], runner.calls)
        self.assertIn(["shareholder", "NVDA.US", "--sort", "owned", "--format", "json"], runner.calls)
        self.assertIn(["fund-holder", "NVDA.US", "--count", "10", "--format", "json"], runner.calls)
        self.assertIn(["constituent", "QQQ.US", "--limit", "100", "--format", "json"], runner.calls)

    def test_safe_runner_blocks_write_risk_commands(self) -> None:
        runner = build_safe_longbridge_runner(RecordingLongbridgeRunner())

        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["order", "buy", "NVDA.US", "1"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["order", "cancel", "order-id"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["order", "replace", "order-id"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["dca", "create", "NVDA.US"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["statement", "export", "--file-key", "abc", "-o", "out.pdf"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["watchlist", "add", "NVDA.US"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["alert", "remove", "alert-id"], None, 20)
        with self.assertRaisesRegex(RuntimeError, "blocked write-risk Longbridge command"):
            runner(["sharelist", "update", "list-id"], None, 20)


if __name__ == "__main__":
    unittest.main()
