#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[3]
TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_CACHE_DIR_NAME = ".tmp/tradingagents-tushare-cache"
DAILY_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60
SUPPORTED_A_MARKET_SUFFIXES = {".SZ", ".SH", ".SS", ".BJ"}
INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.",
    "close_200_sma": "200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.",
    "close_10_ema": "10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.",
    "macd": "MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.",
    "macds": "MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.",
    "macdh": "MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.",
    "rsi": "RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.",
    "boll": "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.",
    "boll_ub": "Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.",
    "boll_lb": "Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.",
    "atr": "ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.",
    "vwma": "VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.",
}
MIN_HISTORY_DAYS = 260

JsonFetcher = Callable[[str, dict[str, Any], str, int], dict[str, Any]]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def cache_root() -> Path:
    return (REPO_ROOT / TUSHARE_CACHE_DIR_NAME).resolve()


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


def tushare_token(env: dict[str, str] | None = None) -> str:
    env_map = env or {}
    token = clean_text(env_map.get("TUSHARE_TOKEN")) or clean_text(env_map.get("TUSHARE_PRO_TOKEN"))
    if not token:
        raise ValueError("TUSHARE_TOKEN is not set.")
    return token


def normalize_tushare_ts_code(ticker: str) -> str:
    normalized = clean_text(ticker).upper()
    if not normalized:
        raise ValueError("Ticker is blank.")
    if not any(normalized.endswith(suffix) for suffix in SUPPORTED_A_MARKET_SUFFIXES):
        raise ValueError(f"Tushare market vendor supports A-share/B-share tickers only, got `{normalized}`.")
    if normalized.endswith(".SS"):
        return normalized[:-3] + ".SH"
    return normalized


def format_date_yyyymmdd(value: str) -> str:
    parsed = datetime.strptime(clean_text(value), "%Y-%m-%d")
    return parsed.strftime("%Y%m%d")


def tushare_api_request(
    api_name: str,
    params: dict[str, Any],
    fields: str,
    max_age_seconds: int,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env_map = env or {}
    body = {
        "api_name": api_name,
        "token": tushare_token(env_map),
        "params": params,
        "fields": fields,
    }
    cache_name = f"{api_name}-{json.dumps(params, ensure_ascii=True, sort_keys=True)}.json"
    path = cache_path(cache_name)
    cached = read_cached_json(path, max_age_seconds=max_age_seconds)
    if cached is not None:
        return cached

    request = Request(
        clean_text(env_map.get("TUSHARE_API_URL")) or TUSHARE_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Tushare request failed with HTTP {exc.code} for api `{api_name}`") from exc
    except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Tushare request failed for api `{api_name}`: {clean_text(str(exc)) or exc.__class__.__name__}") from exc

    code = payload.get("code")
    if code not in {0, None}:
        message = clean_text(payload.get("msg")) or f"code={code}"
        raise RuntimeError(f"Tushare api `{api_name}` failed: {message}")

    write_cached_json(path, payload)
    return payload


def parse_daily_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    fields = list(data.get("fields") or [])
    items = list(data.get("items") or [])
    rows: list[dict[str, Any]] = []
    for item in items:
        row = {str(field): item[index] if index < len(item) else None for index, field in enumerate(fields)}
        rows.append(
            {
                "ts_code": clean_text(row.get("ts_code")),
                "trade_date": normalize_trade_date(row.get("trade_date")),
                "open": to_float(row.get("open")),
                "high": to_float(row.get("high")),
                "low": to_float(row.get("low")),
                "close": to_float(row.get("close")),
                "pre_close": to_float(row.get("pre_close")),
                "change": to_float(row.get("change")),
                "pct_chg": to_float(row.get("pct_chg")),
                "vol": to_float(row.get("vol")),
                "amount": to_float(row.get("amount")),
            }
        )
    rows.sort(key=lambda item: item["trade_date"])
    return [row for row in rows if row["trade_date"]]


def normalize_trade_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def fetch_daily_bars(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    fetcher: JsonFetcher = tushare_api_request,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    ts_code = normalize_tushare_ts_code(ticker)
    payload = fetcher(
        "daily",
        {
            "ts_code": ts_code,
            "start_date": format_date_yyyymmdd(start_date),
            "end_date": format_date_yyyymmdd(end_date),
        },
        "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        DAILY_CACHE_MAX_AGE_SECONDS,
        env=env,
    )
    rows = parse_daily_items(payload)
    if not rows:
        raise RuntimeError(f"No Tushare daily bars returned for `{ts_code}`.")
    return rows


def days_before(date_text: str, days: int) -> str:
    parsed = datetime.strptime(clean_text(date_text), "%Y-%m-%d")
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def format_numeric(value: float, digits: int = 4) -> str:
    if math.isnan(value):
        return "N/A"
    return f"{value:.{digits}f}"


def ema(values: list[float], period: int) -> list[float]:
    results: list[float] = []
    multiplier = 2 / (period + 1)
    prev = float("nan")
    for index, value in enumerate(values):
        if math.isnan(value):
            results.append(float("nan"))
            continue
        if index == 0 or math.isnan(prev):
            prev = value
        else:
            prev = (value - prev) * multiplier + prev
        results.append(prev)
    return results


def sma(values: list[float], period: int) -> list[float]:
    results: list[float] = []
    window_sum = 0.0
    window: list[float] = []
    for value in values:
        window.append(value)
        if not math.isnan(value):
            window_sum += value
        if len(window) > period:
            removed = window.pop(0)
            if not math.isnan(removed):
                window_sum -= removed
        if len(window) < period or any(math.isnan(item) for item in window):
            results.append(float("nan"))
        else:
            results.append(window_sum / period)
    return results


def rolling_std(values: list[float], period: int) -> list[float]:
    means = sma(values, period)
    results: list[float] = []
    window: list[float] = []
    for index, value in enumerate(values):
        window.append(value)
        if len(window) > period:
            window.pop(0)
        if len(window) < period or any(math.isnan(item) for item in window):
            results.append(float("nan"))
            continue
        mean = means[index]
        variance = sum((item - mean) ** 2 for item in window) / period
        results.append(math.sqrt(variance))
    return results


def compute_rsi(values: list[float], period: int = 14) -> list[float]:
    results = [float("nan")] * len(values)
    if len(values) <= period:
        return results
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for index in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        rs = float("inf") if avg_loss == 0 else avg_gain / avg_loss
        results[index + 1] = 100 - (100 / (1 + rs))
    return results


def compute_macd(values: list[float]) -> tuple[list[float], list[float], list[float]]:
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    macd_line = [
        float("nan") if math.isnan(a) or math.isnan(b) else a - b
        for a, b in zip(ema12, ema26)
    ]
    signal_line = ema([0.0 if math.isnan(value) else value for value in macd_line], 9)
    histogram = [
        float("nan") if math.isnan(macd_value) else macd_value - signal_value
        for macd_value, signal_value in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, histogram


def compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    true_ranges: list[float] = []
    for index, high in enumerate(highs):
        low = lows[index]
        prev_close = closes[index - 1] if index > 0 else closes[index]
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    results = [float("nan")] * len(true_ranges)
    if len(true_ranges) < period:
        return results
    atr_value = sum(true_ranges[:period]) / period
    results[period - 1] = atr_value
    for index in range(period, len(true_ranges)):
        atr_value = ((atr_value * (period - 1)) + true_ranges[index]) / period
        results[index] = atr_value
    return results


def compute_vwma(closes: list[float], volumes: list[float], period: int = 20) -> list[float]:
    results: list[float] = []
    close_window: list[float] = []
    volume_window: list[float] = []
    for close, volume in zip(closes, volumes):
        close_window.append(close)
        volume_window.append(volume)
        if len(close_window) > period:
            close_window.pop(0)
            volume_window.pop(0)
        if len(close_window) < period or any(math.isnan(item) for item in close_window) or any(math.isnan(item) for item in volume_window):
            results.append(float("nan"))
            continue
        denominator = sum(volume_window)
        if denominator == 0:
            results.append(float("nan"))
            continue
        results.append(sum(c * v for c, v in zip(close_window, volume_window)) / denominator)
    return results


def indicator_series(rows: list[dict[str, Any]], indicator: str) -> list[float]:
    closes = [row["close"] for row in rows]
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]
    volumes = [row["vol"] for row in rows]
    if indicator == "close_50_sma":
        return sma(closes, 50)
    if indicator == "close_200_sma":
        return sma(closes, 200)
    if indicator == "close_10_ema":
        return ema(closes, 10)
    if indicator == "rsi":
        return compute_rsi(closes, 14)
    if indicator == "boll":
        return sma(closes, 20)
    if indicator == "boll_ub":
        middle = sma(closes, 20)
        std_values = rolling_std(closes, 20)
        return [float("nan") if math.isnan(m) or math.isnan(s) else m + 2 * s for m, s in zip(middle, std_values)]
    if indicator == "boll_lb":
        middle = sma(closes, 20)
        std_values = rolling_std(closes, 20)
        return [float("nan") if math.isnan(m) or math.isnan(s) else m - 2 * s for m, s in zip(middle, std_values)]
    if indicator == "atr":
        return compute_atr(highs, lows, closes, 14)
    if indicator == "vwma":
        return compute_vwma(closes, volumes, 20)
    macd_line, signal_line, histogram = compute_macd(closes)
    if indicator == "macd":
        return macd_line
    if indicator == "macds":
        return signal_line
    if indicator == "macdh":
        return histogram
    raise ValueError(
        f"Indicator {indicator} is not supported. Please choose from: {sorted(INDICATOR_DESCRIPTIONS.keys())}"
    )


def format_indicator_report(symbol: str, indicator: str, curr_date: str, look_back_days: int, rows: list[dict[str, Any]]) -> str:
    before = days_before(curr_date, look_back_days)
    series = indicator_series(rows, indicator)
    lines = []
    for row, value in zip(rows, series):
        trade_date = row["trade_date"]
        if trade_date < before or trade_date > curr_date:
            continue
        lines.append(f"{trade_date}: {format_numeric(value)}")
    description = INDICATOR_DESCRIPTIONS.get(indicator, "No description available.")
    return (
        f"## {indicator} values from {before} to {curr_date}:\n\n"
        + ("\n".join(lines) if lines else "No data available for the specified range.")
        + "\n\n"
        + description
    )


def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    fetcher: JsonFetcher = tushare_api_request,
    env: dict[str, str] | None = None,
) -> str:
    rows = fetch_daily_bars(symbol, start_date, end_date, fetcher=fetcher, env=env)
    header = [
        f"# Stock data for {normalize_tushare_ts_code(symbol)} from {start_date} to {end_date}",
        f"# Total records: {len(rows)}",
        "# Volume unit: hands; amount unit: thousand CNY",
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
    fetcher: JsonFetcher = tushare_api_request,
    env: dict[str, str] | None = None,
) -> str:
    normalized_indicator = clean_text(indicator).lower()
    if normalized_indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {normalized_indicator} is not supported. Please choose from: {sorted(INDICATOR_DESCRIPTIONS.keys())}"
        )
    start_date = days_before(curr_date, max(look_back_days + MIN_HISTORY_DAYS, MIN_HISTORY_DAYS))
    rows = fetch_daily_bars(symbol, start_date, curr_date, fetcher=fetcher, env=env)
    return format_indicator_report(normalize_tushare_ts_code(symbol), normalized_indicator, curr_date, look_back_days, rows)


# ---------------------------------------------------------------------------
# Universe candidates via Tushare daily_basic API
# ---------------------------------------------------------------------------

UNIVERSE_CACHE_MAX_AGE_SECONDS = 30 * 60  # 30 minutes, same as Eastmoney


def _parse_daily_basic_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse Tushare ``daily_basic`` response into a flat list of dicts."""
    data = payload.get("data") or {}
    fields = list(data.get("fields") or [])
    items = list(data.get("items") or [])
    rows: list[dict[str, Any]] = []
    for item in items:
        row = {str(field): item[idx] if idx < len(item) else None for idx, field in enumerate(fields)}
        rows.append(row)
    return rows


def _ts_code_to_ticker(ts_code: str) -> str:
    """Convert Tushare ts_code (e.g. ``000001.SZ``) to canonical ticker."""
    normalized = clean_text(ts_code).upper()
    if normalized.endswith(".SH"):
        return normalized[:-3] + ".SS"
    return normalized


def _board_name_from_code(code: str) -> str:
    """Infer board name from the numeric prefix of a stock code."""
    if code.startswith(("300", "301")):
        return "chinext"
    if code.startswith("688"):
        return "star"
    if code.startswith(("000", "001", "002", "600", "601", "603", "605")):
        return "main"
    if code.startswith(("8", "4")):
        return "bse"
    return "unknown"


def fetch_universe_candidates(
    trade_date: str,
    limit: int = 80,
    *,
    fetcher: JsonFetcher = tushare_api_request,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch top A-share stocks by turnover via Tushare ``daily_basic``.

    Returns a list of candidate dicts compatible with the month-end shortlist
    universe format (keys: code, ticker, name, sector, price, day_pct,
    turnover_amount, total_market_cap, free_float_market_cap, board, source).

    The function fetches ``daily_basic`` for the given *trade_date*, sorts by
    ``amount`` (turnover in thousand CNY) descending, and returns the top
    *limit* entries.  Results are cached for 30 minutes.
    """
    cache_name = f"tushare-universe-{clean_text(trade_date)}-{limit}.json"
    path = cache_path(cache_name)
    cached = read_cached_json(path, max_age_seconds=UNIVERSE_CACHE_MAX_AGE_SECONDS)
    if cached is not None:
        return cached  # type: ignore[return-value]

    formatted_date = format_date_yyyymmdd(trade_date)
    payload = fetcher(
        "daily_basic",
        {"trade_date": formatted_date},
        "ts_code,trade_date,close,pct_chg,turnover_rate,volume_ratio,total_mv,circ_mv",
        DAILY_CACHE_MAX_AGE_SECONDS,
        env=env,
    )
    raw_rows = _parse_daily_basic_items(payload)

    # Also fetch daily bars for the same date to get turnover amount
    daily_payload = fetcher(
        "daily",
        {"trade_date": formatted_date},
        "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        DAILY_CACHE_MAX_AGE_SECONDS,
        env=env,
    )
    daily_rows = _parse_daily_basic_items(daily_payload)
    amount_map: dict[str, float] = {}
    for row in daily_rows:
        ts_code = clean_text(row.get("ts_code"))
        # Tushare amount is in thousand CNY; convert to CNY
        amt = to_float(row.get("amount")) * 1000.0
        if ts_code and not math.isnan(amt):
            amount_map[ts_code] = amt

    # Build candidate list
    candidates: list[dict[str, Any]] = []
    for row in raw_rows:
        ts_code = clean_text(row.get("ts_code"))
        if not ts_code:
            continue
        # Only A-share main exchanges
        if not any(ts_code.endswith(suffix) for suffix in (".SZ", ".SH")):
            continue
        code = ts_code.split(".")[0]
        ticker = _ts_code_to_ticker(ts_code)
        close_price = to_float(row.get("close"))
        pct_chg = to_float(row.get("pct_chg"))
        # total_mv and circ_mv are in 万元 (10k CNY); convert to CNY
        total_mv = to_float(row.get("total_mv")) * 1e4
        circ_mv = to_float(row.get("circ_mv")) * 1e4
        amount = amount_map.get(ts_code, 0.0)
        if math.isnan(close_price) or close_price <= 0:
            continue
        candidates.append({
            "code": code,
            "ticker": ticker,
            "name": code,  # Tushare daily_basic doesn't return name; use code as placeholder
            "sector": "",
            "price": round(close_price, 2),
            "day_pct": round(pct_chg, 2) if not math.isnan(pct_chg) else 0.0,
            "turnover_amount": round(amount, 2),
            "total_market_cap": round(total_mv, 2) if not math.isnan(total_mv) else 0.0,
            "free_float_market_cap": round(circ_mv, 2) if not math.isnan(circ_mv) else 0.0,
            "board": _board_name_from_code(code),
            "source": "tushare_daily_basic",
        })

    # Sort by turnover amount descending, take top N
    candidates.sort(key=lambda c: c["turnover_amount"], reverse=True)
    result = candidates[:limit]
    write_cached_json(path, result)
    return result
