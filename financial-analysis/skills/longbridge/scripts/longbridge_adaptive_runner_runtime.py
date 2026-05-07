#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
TRADINGAGENTS_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "tradingagents-decision-bridge" / "scripts"

if str(TRADINGAGENTS_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(TRADINGAGENTS_SCRIPT_DIR))

from longbridge_intraday_monitor_runtime import run_longbridge_intraday_monitor
from longbridge_screen_runtime import run_longbridge_screen
from longbridge_trading_plan_runtime import (
    build_postclose_review,
    build_postclose_review_markdown,
    build_trading_plan_markdown,
    build_trading_plan_report,
)


SCHEMA_VERSION = "longbridge_adaptive_runner/v1"
CommandRunner = Callable[[list[str], dict[str, str] | None, int], Any]

READ_ONLY_ACCOUNT_COMMANDS = {"portfolio", "assets", "positions"}
TASK_ALIASES = {
    "analysis": "stock_analysis",
    "stock": "stock_analysis",
    "stock_analysis": "stock_analysis",
    "market_analysis": "stock_analysis",
    "plan": "trading_plan",
    "trade_plan": "trading_plan",
    "trading_plan": "trading_plan",
    "review": "review",
    "postclose": "review",
    "post_close": "review",
    "replay": "review",
    "portfolio": "portfolio_review",
    "portfolio_review": "portfolio_review",
    "account": "portfolio_review",
    "account_review": "portfolio_review",
}
LAYER_ORDER = [
    "catalyst",
    "valuation",
    "financial_event",
    "ownership_risk",
    "intraday",
    "portfolio",
    "theme_chain",
    "governance_structure",
    "account_health",
    "account_review_plus",
    "execution_preflight",
    "derivative_event_risk",
    "hk_microstructure",
    "quant",
    "watchlist_alert",
    "subscription_sharelist",
]
PLAN_EVIDENCE_LAYER_KEYS = (
    "account_review_plus",
    "execution_preflight",
    "derivative_event_risk",
    "hk_microstructure",
    "governance_structure",
)
WRITE_RISK_ORDER_OPERATIONS = {"buy", "sell", "submit", "cancel", "replace", "modify"}
WRITE_RISK_GENERIC_OPERATIONS = {
    "add",
    "add-stock",
    "add_stocks",
    "create",
    "delete",
    "disable",
    "enable",
    "pin",
    "remove",
    "remove-stock",
    "replace",
    "set",
    "sort",
    "unpin",
    "update",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def _symbol_match_key(symbol: Any) -> str:
    value = clean_text(symbol).upper()
    match = re.match(r"^0*(\d+)\.(US|HK|SH|SZ|SG|HAS)$", value)
    if match:
        return f"{int(match.group(1))}.{match.group(2)}"
    return value


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"), strict=False)
    return payload if isinstance(payload, dict) else {}


def _text_has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _is_broker_holding_context(prompt: str) -> bool:
    return _text_has_any(
        prompt,
        ("broker holding", "broker-holding", "brokers", "券商持仓", "经纪持仓"),
    )


def _listify(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if clean_text(value):
        return [clean_text(value)]
    return []


def _extract_tickers(prompt: str) -> list[str]:
    tickers: list[str] = []
    for match in re.finditer(r"\b([A-Z]{1,6}|\d{1,6})(?:\.(US|HK|SH|SZ|SG|HAS))\b", prompt):
        symbol = match.group(0).upper()
        if symbol not in tickers:
            tickers.append(symbol)
    return tickers


def normalize_task_type(request: dict[str, Any]) -> str:
    explicit = clean_text(request.get("task_type") or request.get("mode")).lower().replace("-", "_")
    if explicit:
        return TASK_ALIASES.get(explicit, explicit)
    prompt = clean_text(request.get("prompt") or request.get("query") or request.get("task"))
    if _text_has_any(prompt, ("复盘", "review", "postclose", "post-close", "回顾")):
        return "review"
    if _text_has_any(prompt, ("交易计划", "trading plan", "trade plan", "trigger", "止损", "入场", "仓位")):
        return "trading_plan"
    if _text_has_any(prompt, ("portfolio", "assets", "positions", "组合", "资产", "持仓")) and not _is_broker_holding_context(prompt):
        return "portfolio_review"
    return "stock_analysis"


def infer_analysis_layers(request: dict[str, Any], *, task_type: str) -> list[str]:
    explicit = _listify(request.get("analysis_layers"))
    if explicit:
        if any(item.lower() == "all" for item in explicit):
            return list(LAYER_ORDER)
        normalized = {layer.lower().replace("-", "_") for layer in explicit}
        if "preflight" in normalized:
            normalized.add("execution_preflight")
        if normalized & {"derivative", "derivatives", "option", "options", "iv", "oi", "warrant", "warrants"}:
            normalized.add("derivative_event_risk")
        if normalized & {"hk", "hk_micro", "microstructure", "broker_holding", "broker-holding", "ah_premium", "ah-premium"}:
            normalized.add("hk_microstructure")
        if normalized & {"governance", "governance_structure", "executive", "executives", "management", "invest_relation", "invest-relation", "fund_exposure", "control_structure"}:
            normalized.add("governance_structure")
        if normalized & {"subscription", "subscriptions", "sharelist", "sharelists", "subscription_sharelist", "sharelist_subscription"}:
            normalized.add("subscription_sharelist")
        return [item for item in LAYER_ORDER if item in normalized]

    prompt = clean_text(request.get("prompt") or request.get("query") or request.get("task"))
    layers: set[str] = {"catalyst", "valuation"}
    if _text_has_any(
        prompt,
        (
            "option",
            "options",
            "iv",
            "oi",
            "call",
            "put",
            "warrant",
            "warrants",
            "derivative",
            "derivatives",
            "期权",
            "隐波",
            "窝轮",
            "牛熊证",
        ),
    ):
        layers.add("derivative_event_risk")
    if _text_has_any(
        prompt,
        (
            "hk microstructure",
            "microstructure",
            "broker holding",
            "broker-holding",
            "brokers",
            "ah premium",
            "ah-premium",
            "participants",
            "港股",
            "券商持仓",
            "经纪持仓",
            "AH溢价",
        ),
    ):
        layers.add("hk_microstructure")
    if _text_has_any(
        prompt,
        (
            "governance",
            "governance structure",
            "executive",
            "management",
            "invest relation",
            "invest-relation",
            "board",
            "control",
            "ownership structure",
            "fund exposure",
            "model governance",
            "治理",
            "治理结构",
            "高管",
            "管理层",
            "投资者关系",
            "控股结构",
            "股权结构",
            "基金暴露",
        ),
    ):
        layers.add("governance_structure")
    if task_type == "trading_plan":
        layers.update({"financial_event", "ownership_risk"})
        if _text_has_any(
            prompt,
            (
                "execution preflight",
                "preflight",
                "overnight eligibility",
                "market status",
                "trading days",
                "trading session",
                "tradability",
                "可执行",
                "可执行性",
                "隔夜",
                "隔夜资格",
                "市场状态",
                "交易日",
                "交易时段",
            ),
        ):
            layers.add("execution_preflight")
    if _text_has_any(prompt, ("filing", "财报", "业绩", "earnings", "financial report", "dividend", "分红")):
        layers.add("financial_event")
    if _text_has_any(prompt, ("insider", "investors", "institutional", "short interest", "short-position", "空头", "内部人", "机构")):
        layers.add("ownership_risk")
    if _text_has_any(
        prompt,
        (
            "资金面",
            "capital flow",
            "intraday",
            "盘中",
            "短线",
            "market-temp",
            "市场温度",
            "order book",
            "depth",
            "bid ask",
            "bid-ask",
            "recent trades",
            "tick-by-tick",
            "trade-stats",
            "trade stats",
            "quote anomaly",
            "quote anomalies",
            "逐笔",
            "盘口",
            "买卖盘",
            "异动",
        ),
    ):
        layers.add("intraday")
    if _text_has_any(prompt, ("portfolio", "assets", "positions", "组合", "资产", "持仓")) and not _is_broker_holding_context(prompt):
        layers.add("portfolio")
    if task_type in {"review", "portfolio_review"} and _text_has_any(
        prompt,
        (
            "order history",
            "trade history",
            "executions",
            "fills",
            "cash-flow",
            "cash flow",
            "profit-analysis",
            "profit analysis",
            "statement list",
            "daily statement",
            "订单",
            "订单历史",
            "成交",
            "现金流",
            "收益分析",
            "盈亏分析",
            "日结单",
            "结单",
            "对账单",
        ),
    ):
        layers.add("account_review_plus")
    if _text_has_any(prompt, ("产业链", "theme", "sector", "constituent", "fund-holder", "shareholder", "板块")):
        layers.add("theme_chain")
    if _text_has_any(prompt, ("margin", "buying power", "max-qty", "statement list", "保证金", "购买力", "最大可买")):
        layers.add("account_health")
    if _text_has_any(prompt, ("quant", "rsi", "macd", "技术指标", "指标")):
        layers.add("quant")
    if _text_has_any(prompt, ("watchlist", "alert", "观察池", "提醒")):
        layers.add("watchlist_alert")
    if _text_has_any(
        prompt,
        (
            "subscription",
            "subscriptions",
            "websocket subscription",
            "sharelist",
            "share list",
            "popular sharelist",
            "community stock list",
            "实时订阅",
            "订阅",
            "共享列表",
            "社区股票列表",
            "热门社区",
        ),
    ):
        layers.add("subscription_sharelist")
    return [layer for layer in LAYER_ORDER if layer in layers]


def infer_adaptive_request(request: dict[str, Any]) -> dict[str, Any]:
    inferred = deepcopy(request)
    prompt = clean_text(inferred.get("prompt") or inferred.get("query") or inferred.get("task"))
    task_type = normalize_task_type(inferred)
    tickers = _listify(inferred.get("tickers") or inferred.get("symbols"))
    if not tickers and prompt:
        tickers = _extract_tickers(prompt)
    inferred["task_type"] = task_type
    inferred["tickers"] = tickers
    inferred["analysis_layers"] = infer_analysis_layers(inferred, task_type=task_type)
    inferred["content_count"] = max(1, min(_to_int(inferred.get("content_count"), 3), 10))
    inferred["session_type"] = clean_text(inferred.get("session_type") or inferred.get("session")) or "premarket"
    return inferred


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def command_preview(args: list[str]) -> str:
    return "longbridge " + " ".join(clean_text(arg) for arg in args)


def is_write_risk_command(args: list[str]) -> bool:
    if not args:
        return False
    command = clean_text(args[0]).lower()
    operation = clean_text(args[1]).lower().replace("_", "-") if len(args) > 1 else ""
    if command == "dca":
        return True
    if command == "order":
        return operation in WRITE_RISK_ORDER_OPERATIONS
    if command == "statement":
        return operation == "export" or "-o" in args or "--output" in args
    if command in {"watchlist", "alert", "sharelist"}:
        return operation in WRITE_RISK_GENERIC_OPERATIONS
    return False


def build_safe_longbridge_runner(runner: CommandRunner) -> CommandRunner:
    def safe_runner(args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
        if is_write_risk_command(args):
            raise RuntimeError(f"blocked write-risk Longbridge command: {command_preview(args)}")
        return runner(args, env, timeout_seconds)

    return safe_runner


def _screen_request(inferred: dict[str, Any]) -> dict[str, Any]:
    request = {
        "tickers": inferred.get("tickers") or [],
        "analysis_date": clean_text(inferred.get("analysis_date")),
        "analysis_layers": inferred.get("analysis_layers") or [],
        "content_count": inferred.get("content_count") or 3,
    }
    for key in (
        "investor_ciks",
        "investor_top",
        "short_count",
        "insider_count",
        "trade_count",
        "theme_indexes",
        "quant_start",
        "quant_end",
        "quant_period",
        "quant_scripts",
        "indicators",
        "statement_type",
        "statement_limit",
        "account_health_symbol_limit",
    ):
        if key in inferred:
            request[key] = deepcopy(inferred[key])
    return request


def _candidate_plan_levels(screen_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    levels: dict[str, dict[str, Any]] = {}
    for candidate in screen_result.get("ranked_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        symbol = clean_text(candidate.get("symbol"))
        if not symbol:
            continue
        levels[symbol] = {
            key: candidate.get(key)
            for key in ("trigger_price", "stop_loss", "abandon_below")
            if candidate.get(key) is not None
        }
    return levels


def _fetch_account_snapshot(
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    unavailable: list[dict[str, str]] = []
    outputs: dict[str, Any] = {}
    for command in ("portfolio", "assets", "positions"):
        try:
            outputs[command] = runner([command, "--format", "json"], env, 20)
        except Exception as exc:
            unavailable.append({"command": command, "reason": clean_text(exc)})
            outputs[command] = None
    return {
        **outputs,
        "data_coverage": {
            "portfolio_available": outputs["portfolio"] is not None,
            "assets_available": outputs["assets"] is not None,
            "positions_available": outputs["positions"] is not None,
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _symbols_from_plan(plan_report: dict[str, Any]) -> list[str]:
    symbols: list[str] = []
    for candidate in plan_report.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        symbol = clean_text(candidate.get("symbol"))
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _has_analysis_layer(inferred: dict[str, Any], layer: str) -> bool:
    normalized = {clean_text(item).lower().replace("-", "_") for item in inferred.get("analysis_layers") or []}
    return layer in normalized


def _symbol_targets_for_account_review(
    inferred: dict[str, Any],
    *,
    plan_report: dict[str, Any] | None = None,
    screen_result: dict[str, Any] | None = None,
) -> list[str]:
    symbols: list[str] = []
    for symbol in _listify(inferred.get("tickers") or inferred.get("symbols")):
        if symbol not in symbols:
            symbols.append(symbol)
    for symbol in _symbols_from_plan(plan_report or {}):
        if symbol not in symbols:
            symbols.append(symbol)
    if isinstance(screen_result, dict):
        for candidate in screen_result.get("ranked_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            symbol = clean_text(candidate.get("symbol"))
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols


def _date_window_for_account_review(inferred: dict[str, Any]) -> dict[str, str]:
    start = clean_text(
        inferred.get("start")
        or inferred.get("start_date")
        or inferred.get("review_start")
        or inferred.get("trade_start")
    )
    end = clean_text(
        inferred.get("end")
        or inferred.get("end_date")
        or inferred.get("review_end")
        or inferred.get("trade_end")
        or inferred.get("review_date")
        or inferred.get("analysis_date")
    )
    if start and not end:
        end = start
    if end and not start:
        start = end
    return {"start": start, "end": end}


def _with_date_window(args: list[str], window: dict[str, str]) -> list[str]:
    result = list(args)
    if clean_text(window.get("start")):
        result.extend(["--start", clean_text(window.get("start"))])
    if clean_text(window.get("end")):
        result.extend(["--end", clean_text(window.get("end"))])
    return result


def _optional_account_payload(
    args: list[str],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
    unavailable: list[dict[str, str]],
) -> Any:
    try:
        return runner(args, env, 20)
    except Exception as exc:
        unavailable.append({"command": command_preview(args), "reason": clean_text(exc)})
        return None


def _extend_list_payload(target: list[Any], payload: Any) -> None:
    if isinstance(payload, list):
        target.extend(deepcopy(payload))
    elif payload is not None:
        target.append(deepcopy(payload))


def _fetch_account_review_plus(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
    plan_report: dict[str, Any] | None = None,
    screen_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbols = _symbol_targets_for_account_review(inferred, plan_report=plan_report, screen_result=screen_result)
    window = _date_window_for_account_review(inferred)
    statement_limit = max(1, min(_to_int(inferred.get("statement_limit"), 5), 100))
    unavailable: list[dict[str, str]] = []
    order_history: list[Any] = []
    order_executions: list[Any] = []

    for symbol in symbols:
        history_args = _with_date_window(["order", "--history"], window)
        history_args.extend(["--symbol", symbol, "--format", "json"])
        _extend_list_payload(
            order_history,
            _optional_account_payload(history_args, runner=runner, env=env, unavailable=unavailable),
        )

        executions_args = _with_date_window(["order", "executions", "--history"], window)
        executions_args.extend(["--symbol", symbol, "--format", "json"])
        _extend_list_payload(
            order_executions,
            _optional_account_payload(executions_args, runner=runner, env=env, unavailable=unavailable),
        )

    cash_flow = _optional_account_payload(["cash-flow", "--format", "json"], runner=runner, env=env, unavailable=unavailable)
    profit_analysis = _optional_account_payload(["profit-analysis", "--format", "json"], runner=runner, env=env, unavailable=unavailable)
    statement_list = _optional_account_payload(
        ["statement", "list", "--type", "daily", "--limit", str(statement_limit), "--format", "json"],
        runner=runner,
        env=env,
        unavailable=unavailable,
    )

    return {
        "symbols": symbols,
        "date_window": window,
        "order_history": order_history,
        "order_executions": order_executions,
        "cash_flow": cash_flow,
        "profit_analysis": profit_analysis,
        "statement_list": statement_list,
        "data_coverage": {
            "order_history_available": bool(order_history),
            "order_executions_available": bool(order_executions),
            "cash_flow_available": cash_flow is not None,
            "profit_analysis_available": profit_analysis is not None,
            "statement_list_available": statement_list is not None,
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _items_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "sharelists", "lists", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _sharelist_ids_from_payload(payload: Any, *, limit: int) -> list[str]:
    ids: list[str] = []
    for item in _items_from_payload(payload):
        if not isinstance(item, dict):
            continue
        sharelist_id = clean_text(item.get("id") or item.get("sharelist_id") or item.get("list_id"))
        if sharelist_id and sharelist_id not in ids:
            ids.append(sharelist_id)
        if len(ids) >= limit:
            break
    return ids


def _fetch_subscription_sharelist_state(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    sharelist_count = max(1, min(_to_int(inferred.get("sharelist_count"), 20), 100))
    popular_count = max(1, min(_to_int(inferred.get("sharelist_popular_count"), 10), 100))
    detail_limit = max(0, min(_to_int(inferred.get("sharelist_detail_limit"), 0), 20))
    unavailable: list[dict[str, str]] = []

    subscriptions = _optional_account_payload(["subscriptions", "--format", "json"], runner=runner, env=env, unavailable=unavailable)
    sharelists = _optional_account_payload(
        ["sharelist", "--count", str(sharelist_count), "--format", "json"],
        runner=runner,
        env=env,
        unavailable=unavailable,
    )
    popular_sharelists = _optional_account_payload(
        ["sharelist", "popular", "--count", str(popular_count), "--format", "json"],
        runner=runner,
        env=env,
        unavailable=unavailable,
    )
    sharelist_details: list[Any] = []
    for sharelist_id in _sharelist_ids_from_payload(sharelists, limit=detail_limit):
        detail = _optional_account_payload(
            ["sharelist", "detail", sharelist_id, "--format", "json"],
            runner=runner,
            env=env,
            unavailable=unavailable,
        )
        _extend_list_payload(sharelist_details, detail)

    return {
        "sharelist_count": sharelist_count,
        "sharelist_popular_count": popular_count,
        "sharelist_detail_limit": detail_limit,
        "subscriptions": subscriptions,
        "sharelists": sharelists,
        "popular_sharelists": popular_sharelists,
        "sharelist_details": sharelist_details,
        "data_coverage": {
            "subscriptions_available": subscriptions is not None,
            "sharelists_available": sharelists is not None,
            "popular_sharelists_available": popular_sharelists is not None,
            "sharelist_details_available": bool(sharelist_details),
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _append_subscription_sharelist_state(
    result: dict[str, Any],
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> None:
    if not _has_analysis_layer(inferred, "subscription_sharelist"):
        return
    state = _fetch_subscription_sharelist_state(inferred, runner=runner, env=env)
    result["workflow_steps"].append("longbridge subscription-sharelist")
    result["outputs"]["subscription_sharelist_state"] = state
    screen_result = result["outputs"].get("screen_result")
    if isinstance(screen_result, dict):
        screen_result["subscription_sharelist_state"] = state


def _market_from_symbol(symbol: str, fallback_market: str = "") -> str:
    match = re.search(r"\.([A-Z]{2,3})$", clean_text(symbol))
    if match:
        return match.group(1).upper()
    return clean_text(fallback_market).upper()


def _market_targets_for_preflight(inferred: dict[str, Any]) -> list[str]:
    markets: list[str] = []
    fallback_market = clean_text(inferred.get("market"))
    for symbol in _listify(inferred.get("tickers") or inferred.get("symbols")):
        market = _market_from_symbol(symbol, fallback_market)
        if market and market not in markets:
            markets.append(market)
    if not markets and fallback_market:
        markets.append(fallback_market.upper())
    return markets


def _date_window_for_preflight(inferred: dict[str, Any]) -> dict[str, str]:
    start = clean_text(
        inferred.get("preflight_start")
        or inferred.get("start")
        or inferred.get("start_date")
        or inferred.get("analysis_date")
    )
    end = clean_text(
        inferred.get("preflight_end")
        or inferred.get("end")
        or inferred.get("end_date")
        or inferred.get("analysis_date")
    )
    if start and not end:
        end = start
    if end and not start:
        start = end
    return {"start": start, "end": end}


def _fetch_execution_preflight(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    symbols = _listify(inferred.get("tickers") or inferred.get("symbols"))
    markets = _market_targets_for_preflight(inferred)
    window = _date_window_for_preflight(inferred)
    unavailable: list[dict[str, str]] = []
    symbol_checks: list[dict[str, Any]] = []
    preflight_fields = "pe,pb,dps_rate,turnover_rate,mktcap,volume_ratio,capital_flow"

    for symbol in symbols:
        symbol_checks.append(
            {
                "symbol": symbol,
                "market": _market_from_symbol(symbol, clean_text(inferred.get("market"))),
                "static": _optional_account_payload(
                    ["static", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
                "calc_index": _optional_account_payload(
                    ["calc-index", symbol, "--fields", preflight_fields, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
            }
        )

    security_list = None
    if "US" in markets:
        security_list = _optional_account_payload(
            ["security-list", "US", "--format", "json"],
            runner=runner,
            env=env,
            unavailable=unavailable,
        )
    else:
        unavailable.append({"command": "security-list US", "reason": "not applicable for non-US markets"})

    market_status = _optional_account_payload(["market-status", "--format", "json"], runner=runner, env=env, unavailable=unavailable)
    trading_session = _optional_account_payload(["trading", "session", "--format", "json"], runner=runner, env=env, unavailable=unavailable)

    trading_days: dict[str, Any] = {}
    for market in markets:
        trading_days[market] = _optional_account_payload(
            _with_date_window(["trading", "days", market], window) + ["--format", "json"],
            runner=runner,
            env=env,
            unavailable=unavailable,
        )

    result = {
        "symbols": symbols,
        "markets": markets,
        "date_window": window,
        "symbol_checks": symbol_checks,
        "security_list": security_list,
        "market_status": market_status,
        "trading_session": trading_session,
        "trading_days": trading_days,
        "data_coverage": {
            "static_available": all(check.get("static") is not None for check in symbol_checks) if symbol_checks else False,
            "calc_index_available": all(check.get("calc_index") is not None for check in symbol_checks) if symbol_checks else False,
            "security_list_available": security_list is not None,
            "market_status_available": market_status is not None,
            "trading_session_available": trading_session is not None,
            "trading_days_available": bool(trading_days),
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }
    return result


def _attach_symbol_layer_to_candidates(
    screen_result: dict[str, Any],
    *,
    layer_name: str,
    records: list[dict[str, Any]],
) -> None:
    by_symbol = {
        _symbol_match_key(record.get("symbol")): record
        for record in records
        if isinstance(record, dict) and _symbol_match_key(record.get("symbol"))
    }
    for candidate in screen_result.get("ranked_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        symbol = _symbol_match_key(candidate.get("symbol"))
        if symbol not in by_symbol:
            continue
        candidate[layer_name] = deepcopy(by_symbol[symbol])
        qualitative = deepcopy(candidate.get("qualitative_evaluation") or {})
        qualitative[layer_name] = deepcopy(by_symbol[symbol])
        candidate["qualitative_evaluation"] = qualitative


def _merge_layer_evidence_into_plan(
    plan: dict[str, Any],
    *,
    screen_result: dict[str, Any],
    outputs: dict[str, Any] | None = None,
) -> None:
    source_candidates = {
        _symbol_match_key(candidate.get("symbol")): candidate
        for candidate in screen_result.get("ranked_candidates") or []
        if isinstance(candidate, dict) and _symbol_match_key(candidate.get("symbol"))
    }
    output_sources = outputs if isinstance(outputs, dict) else {}

    def merge_from_records(target: dict[str, Any], layer_name: str, records: Any) -> None:
        if not isinstance(records, list):
            return
        by_symbol = {
            _symbol_match_key(record.get("symbol")): record
            for record in records
            if isinstance(record, dict) and _symbol_match_key(record.get("symbol"))
        }
        symbol = _symbol_match_key(target.get("symbol"))
        record = by_symbol.get(symbol)
        if not record:
            return
        qualitative = target.get("qualitative_evidence")
        if not isinstance(qualitative, dict):
            qualitative = {}
            target["qualitative_evidence"] = qualitative
        qualitative[layer_name] = deepcopy(record)

    def merge_candidate(target: dict[str, Any]) -> None:
        symbol = clean_text(target.get("symbol"))
        source = source_candidates.get(symbol)
        if not source:
            return
        qualitative = target.get("qualitative_evidence")
        if not isinstance(qualitative, dict):
            qualitative = {}
            target["qualitative_evidence"] = qualitative
        for key in PLAN_EVIDENCE_LAYER_KEYS:
            value = source.get(key)
            if isinstance(value, dict):
                qualitative[key] = deepcopy(value)
        merge_from_records(target, "derivative_event_risk", (output_sources.get("derivative_event_risk") or {}).get("symbol_risks"))
        merge_from_records(target, "hk_microstructure", (output_sources.get("hk_microstructure") or {}).get("symbol_microstructure"))
        merge_from_records(target, "execution_preflight", (output_sources.get("preflight") or {}).get("symbol_checks"))

    for candidate in plan.get("candidates") or []:
        if isinstance(candidate, dict):
            merge_candidate(candidate)

    for candidate in plan.get("qualitative_evidence") or []:
        if isinstance(candidate, dict):
            symbol = _symbol_match_key(candidate.get("symbol"))
            source = source_candidates.get(symbol)
            if not source:
                continue
            qualitative = candidate.get("qualitative_evidence")
            if not isinstance(qualitative, dict):
                qualitative = {}
                candidate["qualitative_evidence"] = qualitative
            for key in PLAN_EVIDENCE_LAYER_KEYS:
                value = source.get(key)
                if isinstance(value, dict):
                    qualitative[key] = deepcopy(value)
            merge_from_records(candidate, "derivative_event_risk", (output_sources.get("derivative_event_risk") or {}).get("symbol_risks"))
            merge_from_records(candidate, "hk_microstructure", (output_sources.get("hk_microstructure") or {}).get("symbol_microstructure"))
            merge_from_records(candidate, "execution_preflight", (output_sources.get("preflight") or {}).get("symbol_checks"))


def _inject_symbol_records_into_plan(
    plan: dict[str, Any],
    *,
    layer_name: str,
    records: Any,
) -> None:
    if not isinstance(records, list):
        return
    by_symbol = {
        _symbol_match_key(record.get("symbol")): record
        for record in records
        if isinstance(record, dict) and _symbol_match_key(record.get("symbol"))
    }

    def merge_entry(entry: dict[str, Any]) -> None:
        symbol = _symbol_match_key(entry.get("symbol"))
        record = by_symbol.get(symbol)
        if not record:
            return
        entry[layer_name] = deepcopy(record)
        qualitative = deepcopy(entry.get("qualitative_evidence") or {})
        qualitative[layer_name] = deepcopy(record)
        entry["qualitative_evidence"] = qualitative

    for candidate in plan.get("candidates") or []:
        if isinstance(candidate, dict):
            merge_entry(candidate)
    for candidate in plan.get("qualitative_evidence") or []:
        if isinstance(candidate, dict):
            merge_entry(candidate)


def _collect_governance_structure(screen_result: dict[str, Any]) -> dict[str, Any]:
    symbol_structures: list[dict[str, Any]] = []
    for candidate in screen_result.get("ranked_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        symbol = clean_text(candidate.get("symbol"))
        theme_chain = candidate.get("theme_chain_analysis") if isinstance(candidate.get("theme_chain_analysis"), dict) else {}
        governance = theme_chain.get("governance_structure") if isinstance(theme_chain.get("governance_structure"), dict) else {}
        if not governance:
            continue
        symbol_structures.append(
            {
                "symbol": symbol,
                "governance_structure": deepcopy(governance),
                "theme_chain_score": theme_chain.get("theme_chain_score"),
                "data_coverage": deepcopy(governance.get("data_coverage") if isinstance(governance.get("data_coverage"), dict) else {}),
            }
        )
    return {
        "symbols": [item["symbol"] for item in symbol_structures],
        "symbol_structures": symbol_structures,
        "data_coverage": {
            "governance_structure_available": bool(symbol_structures),
            "executive_available": any((item.get("data_coverage") or {}).get("executive_available") for item in symbol_structures),
            "invest_relation_available": any((item.get("data_coverage") or {}).get("invest_relation_available") for item in symbol_structures),
        },
        "should_apply": False,
        "side_effects": "none",
    }


def _fetch_derivative_event_risk(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    symbols = _listify(inferred.get("tickers") or inferred.get("symbols"))
    derivative_fields = "iv,delta,gamma,theta,vega,oi,exp,strike,premium,effective_leverage"
    unavailable: list[dict[str, str]] = []
    symbol_risks: list[dict[str, Any]] = []

    for symbol in symbols:
        market = _market_from_symbol(symbol, clean_text(inferred.get("market")))
        record: dict[str, Any] = {
            "symbol": symbol,
            "market": market,
            "option": None,
            "warrant": None,
            "calc_index": None,
            "should_apply": False,
            "side_effects": "none",
        }
        if market == "US":
            record["option"] = {
                "chain": _optional_account_payload(
                    ["option", "chain", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
                "quote": _optional_account_payload(
                    ["option", "quote", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
                "volume": _optional_account_payload(
                    ["option", "volume", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
            }
            record["calc_index"] = _optional_account_payload(
                ["calc-index", symbol, "--fields", derivative_fields, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            )
        elif market == "HK":
            record["warrant"] = {
                "list": _optional_account_payload(
                    ["warrant", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
                "quote": _optional_account_payload(
                    ["warrant", "quote", symbol, "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
                "issuers": _optional_account_payload(
                    ["warrant", "issuers", "--format", "json"],
                    runner=runner,
                    env=env,
                    unavailable=unavailable,
                ),
            }
            record["calc_index"] = _optional_account_payload(
                ["calc-index", symbol, "--fields", derivative_fields, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            )
        else:
            unavailable.append(
                {
                    "command": "derivative_event_risk",
                    "symbol": symbol,
                    "market": market,
                    "reason": "not applicable for non-US/HK markets",
                }
            )
        symbol_risks.append(record)

    option_available = any(isinstance(record.get("option"), dict) for record in symbol_risks)
    warrant_available = any(isinstance(record.get("warrant"), dict) for record in symbol_risks)
    calc_index_available = any(record.get("calc_index") is not None for record in symbol_risks)
    return {
        "symbols": symbols,
        "symbol_risks": symbol_risks,
        "data_coverage": {
            "option_available": option_available,
            "warrant_available": warrant_available,
            "calc_index_available": calc_index_available,
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _hk_symbol_targets(inferred: dict[str, Any]) -> list[str]:
    return [
        symbol
        for symbol in _listify(inferred.get("tickers") or inferred.get("symbols"))
        if _market_from_symbol(symbol, clean_text(inferred.get("market"))) == "HK"
    ]


def _fetch_hk_microstructure(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    all_symbols = _listify(inferred.get("tickers") or inferred.get("symbols"))
    hk_symbols = _hk_symbol_targets(inferred)
    broker_id = clean_text(inferred.get("broker_id") or inferred.get("broker"))
    ah_symbols = _listify(inferred.get("ah_premium_symbols") or inferred.get("ah_symbols"))
    if not ah_symbols:
        ah_symbols = list(hk_symbols)
    unavailable: list[dict[str, str]] = []
    symbol_microstructure: list[dict[str, Any]] = []

    if not hk_symbols:
        unavailable.append(
            {
                "command": "hk_microstructure",
                "reason": "not applicable because no HK symbols were supplied",
            }
        )
        return {
            "symbols": all_symbols,
            "hk_symbols": [],
            "ah_premium_symbols": [],
            "symbol_microstructure": [],
            "ah_premium": {},
            "participants": None,
            "data_coverage": {
                "brokers_available": False,
                "broker_holding_available": False,
                "broker_holding_detail_available": False,
                "broker_holding_daily_available": False,
                "ah_premium_available": False,
                "participants_available": False,
            },
            "unavailable": unavailable,
            "should_apply": False,
            "side_effects": "none",
        }

    for symbol in hk_symbols:
        record = {
            "symbol": symbol,
            "brokers": _optional_account_payload(
                ["brokers", symbol, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            ),
            "broker_holding": _optional_account_payload(
                ["broker-holding", symbol, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            ),
            "broker_holding_detail": _optional_account_payload(
                ["broker-holding", "detail", symbol, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            ),
            "broker_holding_daily": None,
            "should_apply": False,
            "side_effects": "none",
        }
        if broker_id:
            record["broker_holding_daily"] = _optional_account_payload(
                ["broker-holding", "daily", symbol, "--broker", broker_id, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            )
        symbol_microstructure.append(record)

    ah_premium: dict[str, Any] = {}
    for symbol in ah_symbols:
        if _market_from_symbol(symbol, "HK") != "HK":
            unavailable.append({"command": "ah-premium", "symbol": symbol, "reason": "not an HK symbol"})
            continue
        ah_premium[symbol] = {
            "snapshot": _optional_account_payload(
                ["ah-premium", symbol, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            ),
            "intraday": _optional_account_payload(
                ["ah-premium", "intraday", symbol, "--format", "json"],
                runner=runner,
                env=env,
                unavailable=unavailable,
            ),
        }

    participants = _optional_account_payload(["participants", "--format", "json"], runner=runner, env=env, unavailable=unavailable)
    return {
        "symbols": all_symbols,
        "hk_symbols": hk_symbols,
        "ah_premium_symbols": ah_symbols,
        "symbol_microstructure": symbol_microstructure,
        "ah_premium": ah_premium,
        "participants": participants,
        "data_coverage": {
            "brokers_available": any(record.get("brokers") is not None for record in symbol_microstructure),
            "broker_holding_available": any(record.get("broker_holding") is not None for record in symbol_microstructure),
            "broker_holding_detail_available": any(record.get("broker_holding_detail") is not None for record in symbol_microstructure),
            "broker_holding_daily_available": any(record.get("broker_holding_daily") is not None for record in symbol_microstructure),
            "ah_premium_available": bool(ah_premium),
            "participants_available": participants is not None,
        },
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _first_quote_item(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return {}


def _fetch_quote_actuals(
    plan_report: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
    review_date: str,
) -> dict[str, Any]:
    prices: dict[str, dict[str, Any]] = {}
    unavailable: list[dict[str, str]] = []
    for symbol in _symbols_from_plan(plan_report):
        try:
            payload = runner(["quote", "--format", "json", symbol], env, 20)
        except Exception as exc:
            unavailable.append({"command": "quote", "symbol": symbol, "reason": clean_text(exc)})
            continue
        item = _first_quote_item(payload)
        prices[symbol] = {
            "symbol": symbol,
            "open": item.get("open"),
            "high": item.get("high"),
            "low": item.get("low"),
            "close": item.get("close") or item.get("last") or item.get("last_price"),
            "last": item.get("last") or item.get("last_price"),
            "volume": item.get("volume"),
            "source": "longbridge quote",
        }
    return {
        "review_date": review_date,
        "prices": prices,
        "unavailable": unavailable,
        "data_coverage": {"quote_actuals_available": len(prices)},
    }


def _run_screen(
    inferred: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    tickers = inferred.get("tickers") or []
    if not tickers:
        raise RuntimeError("Longbridge adaptive runner requires `tickers` for stock analysis or trading-plan tasks.")
    return run_longbridge_screen(_screen_request(inferred), runner=runner, env=env)


def _promote_screen_outputs(result: dict[str, Any], screen_result: dict[str, Any]) -> None:
    for key in ("account_state", "account_health", "quant_analysis"):
        if key in screen_result:
            result["outputs"][key] = deepcopy(screen_result[key])


def _collect_intraday_confirmation_state(screen_result: dict[str, Any]) -> dict[str, Any]:
    confirmations: list[dict[str, Any]] = []
    coverage_totals: dict[str, bool] = {
        "capital_available": False,
        "depth_available": False,
        "trades_available": False,
        "trade_stats_available": False,
        "anomaly_available": False,
        "market_temp_available": False,
    }
    unavailable: list[Any] = []
    for candidate in screen_result.get("ranked_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        confirmation = candidate.get("intraday_confirmation")
        if not isinstance(confirmation, dict):
            continue
        symbol = clean_text(candidate.get("symbol"))
        confirmations.append(
            {
                "symbol": symbol,
                "short_term_confirmation_score": confirmation.get("short_term_confirmation_score"),
                "intraday_confirmation": deepcopy(confirmation),
            }
        )
        coverage = confirmation.get("data_coverage") if isinstance(confirmation.get("data_coverage"), dict) else {}
        for key in coverage_totals:
            coverage_totals[key] = coverage_totals[key] or bool(coverage.get(key))
        if isinstance(confirmation.get("unavailable"), list):
            unavailable.extend(deepcopy(confirmation["unavailable"]))
    return {
        "symbols": [item["symbol"] for item in confirmations if item.get("symbol")],
        "symbol_confirmations": confirmations,
        "data_coverage": coverage_totals,
        "unavailable": unavailable,
        "should_apply": False,
        "side_effects": "none",
    }


def _append_intraday_confirmation_state(result: dict[str, Any], inferred: dict[str, Any]) -> None:
    if not _has_analysis_layer(inferred, "intraday"):
        return
    screen_result = result["outputs"].get("screen_result")
    if not isinstance(screen_result, dict):
        return
    state = _collect_intraday_confirmation_state(screen_result)
    if state["symbol_confirmations"]:
        result["outputs"]["intraday_confirmation_state"] = state


def run_longbridge_adaptive_task(
    request: dict[str, Any],
    *,
    runner: CommandRunner,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    inferred = infer_adaptive_request(request)
    safe_runner = build_safe_longbridge_runner(runner)
    task_type = clean_text(inferred.get("task_type"))
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "task_type": task_type,
        "request": deepcopy(request),
        "inferred_request": deepcopy(inferred),
        "workflow_steps": [],
        "outputs": {},
        "should_apply": False,
        "side_effects": "none",
    }

    if task_type == "portfolio_review":
        result["workflow_steps"].extend(["longbridge portfolio", "longbridge assets", "longbridge positions"])
        result["outputs"]["account_snapshot"] = _fetch_account_snapshot(runner=safe_runner, env=env)
        if _has_analysis_layer(inferred, "account_review_plus"):
            result["workflow_steps"].append("longbridge account-review-plus")
            result["outputs"]["account_review_plus"] = _fetch_account_review_plus(
                inferred,
                runner=safe_runner,
                env=env,
            )
        _append_subscription_sharelist_state(result, inferred, runner=safe_runner, env=env)
        return result

    if task_type == "review":
        plan_report = deepcopy(request.get("plan_report") if isinstance(request.get("plan_report"), dict) else {})
        if not plan_report:
            screen_result = deepcopy(request.get("screen_result") if isinstance(request.get("screen_result"), dict) else {})
            if not screen_result:
                screen_result = _run_screen(inferred, runner=safe_runner, env=env)
                result["workflow_steps"].append("longbridge-screen")
                result["outputs"]["screen_result"] = screen_result
            plan_report = build_trading_plan_report(screen_result, session_type="premarket")
            result["workflow_steps"].append("longbridge-trading-plan")
            result["outputs"]["trading_plan_report"] = plan_report
        if _has_analysis_layer(inferred, "account_review_plus"):
            result["workflow_steps"].append("longbridge account-review-plus")
            result["outputs"]["account_review_plus"] = _fetch_account_review_plus(
                inferred,
                runner=safe_runner,
                env=env,
                plan_report=plan_report,
                screen_result=result["outputs"].get("screen_result")
                if isinstance(result["outputs"].get("screen_result"), dict)
                else None,
            )
        actuals = deepcopy(request.get("actuals") if isinstance(request.get("actuals"), dict) else {})
        if not actuals:
            actuals = _fetch_quote_actuals(
                plan_report,
                runner=safe_runner,
                env=env,
                review_date=clean_text(inferred.get("review_date")) or clean_text(inferred.get("analysis_date")),
            )
            result["workflow_steps"].append("longbridge quote actuals")
        review = build_postclose_review(
            plan_report,
            actuals,
            review_date=clean_text(inferred.get("review_date")) or None,
        )
        result["workflow_steps"].append("longbridge-trading-plan review")
        result["outputs"]["postclose_review"] = review
        result["outputs"]["actuals"] = actuals
        _append_subscription_sharelist_state(result, inferred, runner=safe_runner, env=env)
        return result

    screen_result = _run_screen(inferred, runner=safe_runner, env=env)
    result["workflow_steps"].append("longbridge-screen")
    result["outputs"]["screen_result"] = screen_result
    _promote_screen_outputs(result, screen_result)
    _append_subscription_sharelist_state(result, inferred, runner=safe_runner, env=env)
    _append_intraday_confirmation_state(result, inferred)

    if _has_analysis_layer(inferred, "governance_structure"):
        governance_structure = _collect_governance_structure(screen_result)
        screen_result["governance_structure"] = governance_structure
        result["workflow_steps"].append("longbridge governance-structure")
        result["outputs"]["governance_structure"] = governance_structure

    if task_type == "trading_plan" and _has_analysis_layer(inferred, "execution_preflight"):
        preflight = _fetch_execution_preflight(inferred, runner=safe_runner, env=env)
        screen_result["execution_preflight"] = preflight
        result["workflow_steps"].append("longbridge execution-preflight")
        result["outputs"]["preflight"] = preflight

    if _has_analysis_layer(inferred, "derivative_event_risk"):
        derivative_event_risk = _fetch_derivative_event_risk(inferred, runner=safe_runner, env=env)
        screen_result["derivative_event_risk"] = derivative_event_risk
        _attach_symbol_layer_to_candidates(
            screen_result,
            layer_name="derivative_event_risk",
            records=derivative_event_risk.get("symbol_risks") or [],
        )
        result["workflow_steps"].append("longbridge derivative-event-risk")
        result["outputs"]["derivative_event_risk"] = derivative_event_risk

    if _has_analysis_layer(inferred, "hk_microstructure"):
        hk_microstructure = _fetch_hk_microstructure(inferred, runner=safe_runner, env=env)
        screen_result["hk_microstructure"] = hk_microstructure
        _attach_symbol_layer_to_candidates(
            screen_result,
            layer_name="hk_microstructure",
            records=hk_microstructure.get("symbol_microstructure") or [],
        )
        result["workflow_steps"].append("longbridge hk-microstructure")
        result["outputs"]["hk_microstructure"] = hk_microstructure

    if task_type == "trading_plan":
        session_type = clean_text(inferred.get("session_type")) or "premarket"
        intraday_monitor_result: dict[str, Any] | None = None
        if session_type == "intraday":
            intraday_request = {
                "tickers": inferred.get("tickers") or [],
                "analysis_date": clean_text(inferred.get("analysis_date")),
                "market": clean_text(inferred.get("market")),
                "session": clean_text(inferred.get("intraday_session") or "intraday"),
                "plan_levels": _candidate_plan_levels(screen_result),
            }
            intraday_monitor_result = run_longbridge_intraday_monitor(intraday_request, runner=safe_runner, env=env)
            result["workflow_steps"].append("longbridge-intraday-monitor")
            result["outputs"]["intraday_monitor_result"] = intraday_monitor_result
        plan = build_trading_plan_report(
            screen_result,
            session_type=session_type,
            intraday_monitor_result=intraday_monitor_result,
        )
        if isinstance(result["outputs"].get("derivative_event_risk"), dict):
            _inject_symbol_records_into_plan(
                plan,
                layer_name="derivative_event_risk",
                records=(result["outputs"]["derivative_event_risk"].get("symbol_risks") or []),
            )
        if isinstance(result["outputs"].get("hk_microstructure"), dict):
            _inject_symbol_records_into_plan(
                plan,
                layer_name="hk_microstructure",
                records=(result["outputs"]["hk_microstructure"].get("symbol_microstructure") or []),
            )
        if isinstance(result["outputs"].get("preflight"), dict):
            _inject_symbol_records_into_plan(
                plan,
                layer_name="execution_preflight",
                records=(result["outputs"]["preflight"].get("symbol_checks") or []),
            )
        _merge_layer_evidence_into_plan(plan, screen_result=screen_result, outputs=result["outputs"])
        result["workflow_steps"].append("longbridge-trading-plan")
        result["outputs"]["trading_plan_report"] = plan
    return result


def build_adaptive_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Longbridge Adaptive Runner",
        "",
        f"- task_type: `{clean_text(result.get('task_type'))}`",
        f"- workflow_steps: `{', '.join(result.get('workflow_steps') or [])}`",
        f"- should_apply: `{str(bool(result.get('should_apply'))).lower()}`",
        f"- side_effects: `{clean_text(result.get('side_effects'))}`",
        "",
    ]
    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    if isinstance(outputs.get("trading_plan_report"), dict):
        lines.append(build_trading_plan_markdown(outputs["trading_plan_report"]).rstrip())
        lines.append("")
    if isinstance(outputs.get("postclose_review"), dict):
        lines.append(build_postclose_review_markdown(outputs["postclose_review"]).rstrip())
        lines.append("")
    if isinstance(outputs.get("account_snapshot"), dict):
        snapshot = outputs["account_snapshot"]
        lines.extend(
            [
                "## Account Snapshot",
                "",
                f"- data_coverage: `{json.dumps(snapshot.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(snapshot.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(snapshot.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("account_review_plus"), dict):
        review_plus = outputs["account_review_plus"]
        lines.extend(
            [
                "## Account Review Plus",
                "",
                f"- symbols: `{json.dumps(review_plus.get('symbols') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(review_plus.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(review_plus.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(review_plus.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("subscription_sharelist_state"), dict):
        state = outputs["subscription_sharelist_state"]
        lines.extend(
            [
                "## Subscription And Sharelist State",
                "",
                f"- data_coverage: `{json.dumps(state.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(state.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(state.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("intraday_confirmation_state"), dict):
        state = outputs["intraday_confirmation_state"]
        lines.extend(
            [
                "## Intraday Confirmation State",
                "",
                f"- symbols: `{json.dumps(state.get('symbols') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(state.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(state.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(state.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("preflight"), dict):
        preflight = outputs["preflight"]
        lines.extend(
            [
                "## Execution Preflight",
                "",
                f"- markets: `{json.dumps(preflight.get('markets') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(preflight.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(preflight.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(preflight.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("derivative_event_risk"), dict):
        risk = outputs["derivative_event_risk"]
        lines.extend(
            [
                "## Derivative Event Risk",
                "",
                f"- symbols: `{json.dumps(risk.get('symbols') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(risk.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(risk.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(risk.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("hk_microstructure"), dict):
        hk_microstructure = outputs["hk_microstructure"]
        lines.extend(
            [
                "## HK Microstructure",
                "",
                f"- symbols: `{json.dumps(hk_microstructure.get('symbols') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(hk_microstructure.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(hk_microstructure.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(hk_microstructure.get('side_effects'))}`",
                "",
            ]
        )
    if isinstance(outputs.get("governance_structure"), dict):
        governance = outputs["governance_structure"]
        lines.extend(
            [
                "## Governance Structure",
                "",
                f"- symbols: `{json.dumps(governance.get('symbols') or [], ensure_ascii=False)}`",
                f"- data_coverage: `{json.dumps(governance.get('data_coverage') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- should_apply: `{str(bool(governance.get('should_apply'))).lower()}`",
                f"- side_effects: `{clean_text(governance.get('side_effects'))}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adaptively run read-only Longbridge workflows for analysis, plans, and reviews.")
    parser.add_argument("request_json", help="Path to adaptive request JSON.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--markdown-output", help="Optional markdown output path.")
    args = parser.parse_args(argv)

    from tradingagents_longbridge_market import run_longbridge_cli

    request = load_json(Path(args.request_json))
    result = run_longbridge_adaptive_task(request, runner=run_longbridge_cli, env=dict(os.environ))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    if args.markdown_output:
        Path(args.markdown_output).write_text(build_adaptive_markdown(result), encoding="utf-8")
    if not args.output and not args.markdown_output:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
