#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tradingagents_tushare_market import (
    INDICATOR_DESCRIPTIONS,
    MIN_HISTORY_DAYS,
    format_indicator_report,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_CACHE_DIR_NAME = ".tmp/tradingagents-eastmoney-cache"
EASTMONEY_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60
HK_QUOTE_CACHE_MAX_AGE_SECONDS = 5 * 60
EASTMONEY_DEFAULT_UT = "fa5fd1943c7b386f172d6893dbfba10b"
SUPPORTED_MAINLAND_SUFFIXES = {".SZ", ".SH", ".SS"}

_RETRY_ATTEMPTS = 4
_RETRY_BACKOFF_BASE = 1.5  # seconds: 1.5, 3.0, 4.5

JsonFetcher = Callable[[dict[str, Any], int, dict[str, str] | None], dict[str, Any]]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def cache_root() -> Path:
    return (REPO_ROOT / EASTMONEY_CACHE_DIR_NAME).resolve()


def cache_path(cache_name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_text(cache_name)).strip("._")
    if not slug:
        slug = "cache"
    return cache_root() / slug


def read_cached_json(path: Path, *, max_age_seconds: int) -> Any | None:
    try:
        age_seconds = datetime.now(UTC).timestamp() - path.stat().st_mtime
    except (FileNotFoundError, OSError):
        return None
    if age_seconds > max_age_seconds:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def write_cached_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_eastmoney_symbol(ticker: str) -> str:
    normalized = clean_text(ticker).upper()
    if not normalized:
        raise ValueError("Ticker is blank.")
    if not any(normalized.endswith(suffix) for suffix in SUPPORTED_MAINLAND_SUFFIXES):
        raise ValueError(f"Eastmoney market vendor supports mainland A-share tickers only, got `{normalized}`.")
    if normalized.endswith(".SS"):
        return normalized[:-3] + ".SH"
    return normalized


def eastmoney_secid(ticker: str) -> str:
    normalized = normalize_eastmoney_symbol(ticker)
    digits, suffix = normalized.split(".", 1)
    market_code = "1" if suffix == "SH" else "0"
    return f"{market_code}.{digits}"


def normalize_eastmoney_hk_symbol(ticker: str) -> str:
    normalized = clean_text(ticker).upper()
    if not normalized:
        raise ValueError("Ticker is blank.")
    if not normalized.endswith(".HK"):
        raise ValueError(f"Eastmoney HK quote vendor supports Hong Kong tickers only, got `{normalized}`.")
    digits = normalized.split(".", 1)[0]
    if not digits.isdigit():
        raise ValueError(f"Eastmoney HK quote vendor requires numeric HK tickers, got `{normalized}`.")
    return f"{int(digits):05d}.HK"


def eastmoney_hk_secid(ticker: str) -> str:
    normalized = normalize_eastmoney_hk_symbol(ticker)
    digits = normalized.split(".", 1)[0]
    return f"116.{digits}"


def format_date_yyyymmdd(value: str) -> str:
    parsed = datetime.strptime(clean_text(value), "%Y-%m-%d")
    return parsed.strftime("%Y%m%d")


def parse_json_like_payload(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise RuntimeError("Eastmoney returned an empty payload.")
    if text.endswith(");") and "(" in text:
        text = text[text.find("(") + 1 : -2].strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("Eastmoney returned a non-object payload.")
    return payload


def eastmoney_api_request(params: dict[str, Any], max_age_seconds: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    env_map = env or {}
    query = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "lmt": "10000",
        "ut": clean_text(env_map.get("EASTMONEY_UT")) or EASTMONEY_DEFAULT_UT,
        **params,
    }
    cache_name = f"kline-{json.dumps(query, ensure_ascii=True, sort_keys=True)}.json"
    path = cache_path(cache_name)
    cached = read_cached_json(path, max_age_seconds=max_age_seconds)
    if cached is not None:
        return cached

    request = Request(
        f"{clean_text(env_map.get('EASTMONEY_KLINE_URL')) or EASTMONEY_KLINE_URL}?{urlencode(query)}",
        headers={
            "User-Agent": clean_text(env_map.get("EASTMONEY_USER_AGENT"))
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
            "Referer": clean_text(env_map.get("EASTMONEY_REFERER")) or "https://quote.eastmoney.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=20) as response:
                payload = parse_json_like_payload(response.read().decode("utf-8"))
            write_cached_json(path, payload)
            return payload
        except HTTPError as exc:
            if exc.code < 500:
                raise RuntimeError(f"Eastmoney request failed with HTTP {exc.code}.") from exc
            last_error = exc
        except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < _RETRY_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF_BASE * (attempt + 1))

    raise RuntimeError(
        f"Eastmoney request failed after {_RETRY_ATTEMPTS} attempts: "
        f"{clean_text(str(last_error)) or last_error.__class__.__name__}"
    ) from last_error


def eastmoney_quote_api_request(params: dict[str, Any], max_age_seconds: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    env_map = env or {}
    query = {
        "fields": "f43,f57,f58,f116,f117,f167,f173",
        **params,
    }
    cache_name = f"quote-{json.dumps(query, ensure_ascii=True, sort_keys=True)}.json"
    path = cache_path(cache_name)
    cached = read_cached_json(path, max_age_seconds=max_age_seconds)
    if cached is not None:
        return cached

    request = Request(
        f"{clean_text(env_map.get('EASTMONEY_QUOTE_URL')) or EASTMONEY_QUOTE_URL}?{urlencode(query)}",
        headers={
            "User-Agent": clean_text(env_map.get("EASTMONEY_USER_AGENT"))
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
            "Referer": clean_text(env_map.get("EASTMONEY_REFERER")) or "https://quote.eastmoney.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=20) as response:
                payload = parse_json_like_payload(response.read().decode("utf-8"))
            write_cached_json(path, payload)
            return payload
        except HTTPError as exc:
            if exc.code < 500:
                raise RuntimeError(f"Eastmoney quote request failed with HTTP {exc.code}.") from exc
            last_error = exc
        except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < _RETRY_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF_BASE * (attempt + 1))

    raise RuntimeError(
        f"Eastmoney quote request failed after {_RETRY_ATTEMPTS} attempts: "
        f"{clean_text(str(last_error)) or last_error.__class__.__name__}"
    ) from last_error


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def normalize_trade_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10] if len(text) >= 10 else text


def parse_daily_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    symbol = clean_text(data.get("code"))
    klines = data.get("klines") or []
    rows: list[dict[str, Any]] = []
    for item in klines:
        parts = [clean_text(part) for part in str(item or "").split(",")]
        if len(parts) < 11:
            continue
        close = to_float(parts[2])
        change = to_float(parts[9])
        pre_close = close - change if not math.isnan(close) and not math.isnan(change) else float("nan")
        rows.append(
            {
                "ts_code": symbol,
                "trade_date": normalize_trade_date(parts[0]),
                "open": to_float(parts[1]),
                "high": to_float(parts[3]),
                "low": to_float(parts[4]),
                "close": close,
                "pre_close": pre_close,
                "change": change,
                "pct_chg": to_float(parts[8]),
                "vol": to_float(parts[5]),
                "amount": to_float(parts[6]),
            }
        )
    rows.sort(key=lambda item: item["trade_date"])
    return [row for row in rows if row["trade_date"]]


def fetch_hk_quote_snapshot(
    ticker: str,
    *,
    fetcher: JsonFetcher = eastmoney_quote_api_request,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    symbol = normalize_eastmoney_hk_symbol(ticker)
    payload = fetcher(
        {
            "secid": eastmoney_hk_secid(symbol),
        },
        HK_QUOTE_CACHE_MAX_AGE_SECONDS,
        env,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"No Eastmoney HK quote payload returned for `{symbol}`.")
    raw_price = data.get("f43")
    price = float(raw_price) / 1000 if raw_price not in (None, "") else float("nan")
    if math.isnan(price):
        raise RuntimeError(f"No Eastmoney HK quote price returned for `{symbol}`.")
    return {
        "symbol": symbol,
        "name": clean_text(data.get("f58")) or symbol,
        "last_price": price,
        "raw": data,
    }


def fetch_daily_bars(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    fetcher: JsonFetcher = eastmoney_api_request,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    symbol = normalize_eastmoney_symbol(ticker)
    payload = fetcher(
        {
            "secid": eastmoney_secid(symbol),
            "beg": format_date_yyyymmdd(start_date),
            "end": format_date_yyyymmdd(end_date),
        },
        EASTMONEY_CACHE_MAX_AGE_SECONDS,
        env,
    )
    rows = parse_daily_items(payload)
    if not rows:
        raise RuntimeError(f"No Eastmoney daily bars returned for `{symbol}`.")
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
    fetcher: JsonFetcher = eastmoney_api_request,
    env: dict[str, str] | None = None,
) -> str:
    rows = fetch_daily_bars(symbol, start_date, end_date, fetcher=fetcher, env=env)
    header = [
        f"# Stock data for {normalize_eastmoney_symbol(symbol)} from {start_date} to {end_date}",
        f"# Total records: {len(rows)}",
        "# Volume/Amount units follow the Eastmoney daily kline payload.",
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
    fetcher: JsonFetcher = eastmoney_api_request,
    env: dict[str, str] | None = None,
) -> str:
    normalized_indicator = clean_text(indicator).lower()
    if normalized_indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {normalized_indicator} is not supported. Please choose from: {sorted(INDICATOR_DESCRIPTIONS.keys())}"
        )
    start_date = days_before(curr_date, max(look_back_days + MIN_HISTORY_DAYS, MIN_HISTORY_DAYS))
    rows = fetch_daily_bars(symbol, start_date, curr_date, fetcher=fetcher, env=env)
    return format_indicator_report(normalize_eastmoney_symbol(symbol), normalized_indicator, curr_date, look_back_days, rows)


def classify_intraday_structure(bars_15min: list[dict]) -> str:
    """Classify a single trading day's 15min bars into an intraday structure type.

    Returns one of: 'strong_close', 'fade_from_high', 'weak_open_no_recovery', 'range_bound'.
    """
    if not bars_15min:
        return "range_bound"

    day_high = max(b["high"] for b in bars_15min)
    day_low = min(b["low"] for b in bars_15min)
    day_range = day_high - day_low
    last_close = bars_15min[-1]["close"]
    first_open = bars_15min[0]["open"]

    # VWAP = cumulative amount / cumulative volume
    total_amount = sum(b["amount"] for b in bars_15min)
    total_volume = sum(b["volume"] for b in bars_15min)
    vwap = total_amount / total_volume if total_volume > 0 else last_close

    # Avoid division by zero for flat days
    if day_range <= 0:
        return "range_bound"

    close_position = (last_close - day_low) / day_range  # 0.0 = at low, 1.0 = at high

    # --- weak_open_no_recovery ---
    first_bar = bars_15min[0]
    first_drop_pct = (first_bar["close"] - first_bar["open"]) / first_bar["open"] if first_bar["open"] > 0 else 0
    if first_drop_pct < -0.01:
        recovered = any(b["close"] >= first_open for b in bars_15min[1:])
        if not recovered:
            return "weak_open_no_recovery"

    # --- strong_close ---
    if len(bars_15min) >= 2:
        last_two = bars_15min[-2:]
        last_two_above_vwap = all(b["close"] > vwap for b in last_two)
        last_bar_green = last_two[-1]["close"] > last_two[-1]["open"]
        if last_two_above_vwap and last_bar_green and close_position >= 0.80:
            return "strong_close"

    # --- fade_from_high ---
    midpoint = len(bars_15min) // 2
    first_half = bars_15min[:midpoint] if midpoint > 0 else bars_15min[:1]
    first_half_high = max(b["high"] for b in first_half)
    if first_half_high == day_high and last_close < vwap and close_position <= 0.40:
        return "fade_from_high"

    # --- range_bound ---
    day_range_pct = day_range / day_low if day_low > 0 else 0
    if day_range_pct < 0.03 and 0.30 <= close_position <= 0.70:
        return "range_bound"

    return "range_bound"


def _parse_intraday_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse Eastmoney kline payload into intraday bar dicts with full timestamp."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    klines = data.get("klines") or []
    rows: list[dict[str, Any]] = []
    for item in klines:
        parts = [clean_text(part) for part in str(item or "").split(",")]
        if len(parts) < 7:
            continue
        rows.append(
            {
                "timestamp": clean_text(parts[0]),
                "open": to_float(parts[1]),
                "close": to_float(parts[2]),
                "high": to_float(parts[3]),
                "low": to_float(parts[4]),
                "volume": to_float(parts[5]),
                "amount": to_float(parts[6]),
            }
        )
    return rows


def fetch_intraday_bars(
    ticker: str,
    trade_date: str,
    *,
    klt: int = 104,
    fetcher: JsonFetcher | None = None,
    env: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch intraday bars (default 15min, klt=104) for a single trade_date.

    Returns list[dict] with keys: timestamp, open, close, high, low, volume, amount.
    Filters to bars whose timestamp starts with trade_date.
    Raises RuntimeError if no bars match.
    """
    if fetcher is None:
        fetcher = eastmoney_api_request
    symbol = normalize_eastmoney_symbol(ticker)
    payload = fetcher(
        {
            "secid": eastmoney_secid(symbol),
            "beg": format_date_yyyymmdd(trade_date),
            "end": format_date_yyyymmdd(trade_date),
            "klt": str(klt),
        },
        EASTMONEY_CACHE_MAX_AGE_SECONDS,
        env,
    )
    rows = _parse_intraday_items(payload)
    if not isinstance(rows, list):
        rows = []
    # Filter to requested trade_date (Eastmoney may return adjacent days)
    date_prefix = trade_date[:10]
    filtered = [r for r in rows if str(r.get("timestamp", "")).startswith(date_prefix)]
    if not filtered:
        raise RuntimeError(f"No Eastmoney intraday bars for `{symbol}` on {trade_date}.")
    return filtered
