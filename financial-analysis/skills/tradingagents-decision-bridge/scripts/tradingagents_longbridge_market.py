#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from tradingagents_ticker_normalization import normalize_ticker
from tradingagents_tushare_market import (
    INDICATOR_DESCRIPTIONS,
    MIN_HISTORY_DAYS,
    format_indicator_report,
)


LONGBRIDGE_CACHE_MAX_AGE_SECONDS = 5 * 60
DEFAULT_TIMEOUT_SECONDS = 30

CommandRunner = Callable[[list[str], dict[str, str] | None, int], Any]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def normalize_longbridge_symbol(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".SS"):
        return normalized[:-3] + ".SH"
    if "." not in normalized:
        return f"{normalized}.US"
    return normalized


def longbridge_cli_path(env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    configured = clean_text(env_map.get("LONGBRIDGE_CLI"))
    if configured:
        return configured
    discovered = shutil.which("longbridge")
    if discovered:
        return discovered
    local_appdata = clean_text(env_map.get("LOCALAPPDATA"))
    if local_appdata:
        candidate = Path(local_appdata) / "Programs" / "longbridge" / "longbridge.exe"
        if candidate.exists():
            return str(candidate)
    return "longbridge"


def run_longbridge_cli(
    args: list[str],
    env: dict[str, str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    env_map = dict(os.environ)
    if env:
        env_map.update(env)
    executable = longbridge_cli_path(env_map)
    completed = subprocess.run(
        [executable, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        env=env_map,
    )
    if completed.returncode != 0:
        message = clean_text(completed.stderr) or clean_text(completed.stdout) or f"exit {completed.returncode}"
        raise RuntimeError(f"Longbridge CLI failed: {message}")
    output = clean_text(completed.stdout)
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Longbridge CLI returned non-JSON output: {output[:200]}") from exc


def auth_status(
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = runner(["auth", "status", "--format", "json"], env, DEFAULT_TIMEOUT_SECONDS)
    return payload if isinstance(payload, dict) else {}


def longbridge_available(
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> bool:
    try:
        payload = auth_status(runner=runner, env=env)
    except Exception:
        return False
    return clean_text((payload.get("token") or {}).get("status")) == "valid"


def normalize_trade_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    return text[:10]


def parse_quote_item(item: dict[str, Any]) -> dict[str, Any]:
    symbol = normalize_longbridge_symbol(clean_text(item.get("symbol")))
    last_price = to_float(item.get("last"))
    if math.isnan(last_price):
        raise RuntimeError(f"No Longbridge quote price returned for `{symbol}`.")
    return {
        "symbol": symbol,
        "name": clean_text(item.get("name")) or symbol,
        "last_price": last_price,
        "open": to_float(item.get("open")),
        "high": to_float(item.get("high")),
        "low": to_float(item.get("low")),
        "prev_close": to_float(item.get("prev_close")),
        "volume": int(to_float(item.get("volume"))) if not math.isnan(to_float(item.get("volume"))) else 0,
        "turnover": to_float(item.get("turnover")),
        "status": clean_text(item.get("status")),
        "source": "longbridge_cli",
        "raw": item,
    }


def fetch_quote_snapshot(
    ticker: str,
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    symbol = normalize_longbridge_symbol(ticker)
    payload = runner(["quote", "--format", "json", symbol], env, DEFAULT_TIMEOUT_SECONDS)
    rows = payload if isinstance(payload, list) else []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError(f"No Longbridge quote payload returned for `{symbol}`.")
    return parse_quote_item(rows[0])


def parse_daily_kline_items(symbol: str, payload: Any) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    parsed: list[dict[str, Any]] = []
    previous_close = float("nan")
    for item in rows:
        if not isinstance(item, dict):
            continue
        close = to_float(item.get("close"))
        pre_close = to_float(item.get("prev_close"))
        if math.isnan(pre_close):
            pre_close = previous_close
        change = close - pre_close if not math.isnan(close) and not math.isnan(pre_close) else float("nan")
        pct_chg = (change / pre_close) * 100 if not math.isnan(change) and pre_close else float("nan")
        parsed.append(
            {
                "ts_code": symbol,
                "trade_date": normalize_trade_date(item.get("timestamp") or item.get("time") or item.get("date")),
                "open": to_float(item.get("open")),
                "high": to_float(item.get("high")),
                "low": to_float(item.get("low")),
                "close": close,
                "pre_close": pre_close,
                "change": change,
                "pct_chg": pct_chg,
                "vol": to_float(item.get("volume")),
                "amount": to_float(item.get("turnover")),
            }
        )
        if not math.isnan(close):
            previous_close = close
    parsed.sort(key=lambda row: row["trade_date"])
    return [row for row in parsed if row["trade_date"]]


def _count_for_date_range(start_date: str, end_date: str) -> int:
    try:
        start = datetime.strptime(clean_text(start_date)[:10], "%Y-%m-%d")
        end = datetime.strptime(clean_text(end_date)[:10], "%Y-%m-%d")
    except ValueError:
        return 120
    days = max((end - start).days + 1, 20)
    return min(max(days + 10, 60), 400)


def fetch_daily_bars(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    symbol = normalize_longbridge_symbol(ticker)
    payload = runner(
        [
            "kline",
            symbol,
            "--period",
            "day",
            "--count",
            str(_count_for_date_range(start_date, end_date)),
            "--format",
            "json",
        ],
        env,
        DEFAULT_TIMEOUT_SECONDS,
    )
    rows = parse_daily_kline_items(symbol, payload)
    rows = [row for row in rows if start_date[:10] <= row["trade_date"] <= end_date[:10]]
    if not rows:
        raise RuntimeError(f"No Longbridge daily bars returned for `{symbol}`.")
    return rows


def days_before(date_text: str, days: int) -> str:
    parsed = datetime.strptime(clean_text(date_text), "%Y-%m-%d")
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def format_numeric(value: float, digits: int = 4) -> str:
    if math.isnan(value):
        return "N/A"
    return f"{value:.{digits}f}"


def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> str:
    normalized = normalize_longbridge_symbol(symbol)
    rows = fetch_daily_bars(normalized, start_date, end_date, runner=runner, env=env)
    header = [
        f"# Stock data for {normalized} from {start_date} to {end_date}",
        f"# Total records: {len(rows)}",
        "# Source: Longbridge CLI kline history.",
        "",
        "Date,Open,High,Low,Close,PreClose,Change,PctChg,Volume,Amount",
    ]
    csv_lines = [
        ",".join(
            [
                row["trade_date"],
                format_numeric(row["open"]),
                format_numeric(row["high"]),
                format_numeric(row["low"]),
                format_numeric(row["close"]),
                format_numeric(row["pre_close"]),
                format_numeric(row["change"]),
                format_numeric(row["pct_chg"]),
                format_numeric(row["vol"]),
                format_numeric(row["amount"]),
            ]
        )
        for row in rows
    ]
    return "\n".join([*header, *csv_lines]) + "\n"


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    *,
    runner: CommandRunner = run_longbridge_cli,
    env: dict[str, str] | None = None,
) -> str:
    normalized_indicator = clean_text(indicator).lower()
    if normalized_indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {normalized_indicator} is not supported. Please choose from: {sorted(INDICATOR_DESCRIPTIONS.keys())}"
        )
    normalized = normalize_longbridge_symbol(symbol)
    start_date = days_before(curr_date, max(look_back_days + MIN_HISTORY_DAYS, MIN_HISTORY_DAYS))
    rows = fetch_daily_bars(normalized, start_date, curr_date, runner=runner, env=env)
    return format_indicator_report(normalized, normalized_indicator, curr_date, look_back_days, rows)
