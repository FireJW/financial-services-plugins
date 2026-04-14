from __future__ import annotations

import csv
import io
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[3]

DEFAULT_SOURCE_FRAMEWORKS = [
    "Bridgewater_growth_inflation",
    "ChicagoFed_NFCI",
    "NYFed_Outlook_at_Risk",
    "NYFed_term_premium",
    "FRED_real_yield_breakeven_dollar",
]
DEFAULT_LIVE_DATA_PROVIDER = "none"
DEFAULT_LIVE_FILL_MODE = "missing_only"
DEFAULT_LOOKBACK_TRADING_DAYS = 20
DEFAULT_SEED_FILL_MODE = "fallback_on_no_data"
HTTP_TIMEOUT_SECONDS = 20
FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
TREASURY_TGA_API_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
TREASURY_REAL_YIELD_CSV_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{year_month}?_format=csv&field_tdr_date_value_month={year_month}&page=&type=daily_treasury_real_yield_curve"
TREASURY_NOMINAL_YIELD_CSV_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{year_month}?_format=csv&field_tdr_date_value_month={year_month}&page=&type=daily_treasury_yield_curve"
FED_H10_BROAD_DOLLAR_CSV_URL = "https://www.federalreserve.gov/datadownload/Output.aspx?filetype=csv&from=&label=include&lastobs=120&layout=seriescolumn&rel=H10&series=122e3bcb627e8e53f1bf72a1a09cfb81&to=&type=package"
CHICAGO_FED_NFCI_CSV_URL = "https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv"
CBOE_VIX_CSV_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
NYFED_SOFR_JSON_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/{count}.json"
NYFED_BGCR_JSON_URL = "https://markets.newyorkfed.org/api/rates/secured/bgcr/last/{count}.json"
NYFED_TGCR_JSON_URL = "https://markets.newyorkfed.org/api/rates/secured/tgcr/last/{count}.json"
NYFED_EFFR_JSON_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/{count}.json"
DEFAULT_FRED_SERIES = {
    "real_yield_10y": "DFII10",
    "dxy_broad": "DTWEXBGS",
    "breakeven_10y": "T10YIE",
    "oil_wti": "DCOILWTICO",
    "sp500": "SP500",
    "nasdaq": "NASDAQCOM",
    "financial_conditions": "ANFCI",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique_strings(values: list[Any]) -> list[str]:
    resolved: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and text not in resolved:
            resolved.append(text)
    return resolved


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_local_path(value: Any) -> Path | None:
    text = clean_text(value)
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "financial-services-plugins/macro-health-overlay",
            "Accept": "text/plain, text/csv, application/json",
        },
    )
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def parse_float(value: Any) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text or text == ".":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_iso_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def isoformat_or_blank(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def fetch_fred_series_observations(series_id: str) -> list[tuple[date, float]]:
    query = urlencode({"id": series_id})
    text = fetch_text(f"{FRED_GRAPH_CSV_URL}?{query}")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[date, float]] = []
    for row in reader:
        observation_date = parse_iso_date(row.get("DATE") or row.get("date"))
        value = parse_float(row.get(series_id) or row.get("VALUE") or row.get("value"))
        if observation_date is None or value is None:
            continue
        rows.append((observation_date, value))
    rows.sort(key=lambda item: item[0])
    return rows


def series_latest_and_lookback(rows: list[tuple[date, float]], lookback_observations: int) -> tuple[tuple[date, float] | None, tuple[date, float] | None]:
    if not rows:
        return None, None
    latest = rows[-1]
    if len(rows) > lookback_observations:
        reference = rows[-1 - lookback_observations]
    else:
        reference = rows[0]
    return latest, reference


def series_latest_and_previous_month(rows: list[tuple[date, float]]) -> tuple[tuple[date, float] | None, tuple[date, float] | None]:
    if not rows:
        return None, None
    latest = rows[-1]
    latest_month = (latest[0].year, latest[0].month)
    for row in reversed(rows[:-1]):
        if (row[0].year, row[0].month) != latest_month:
            return latest, row
    return latest, rows[0]


def fred_bp_change(series_id: str, lookback_observations: int) -> dict[str, Any]:
    rows = fetch_fred_series_observations(series_id)
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    return {
        "series_id": series_id,
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_bp": round((latest_value - reference_value) * 100.0, 2),
    }


def fred_pct_change(series_id: str, lookback_observations: int) -> dict[str, Any]:
    rows = fetch_fred_series_observations(series_id)
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    change_pct = 0.0
    if reference_value != 0:
        change_pct = (latest_value / reference_value - 1.0) * 100.0
    return {
        "series_id": series_id,
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_pct": round(change_pct, 2),
    }


def fred_abs_change(series_id: str, lookback_observations: int) -> dict[str, Any]:
    rows = fetch_fred_series_observations(series_id)
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    return {
        "series_id": series_id,
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_abs": round(latest_value - reference_value, 4),
    }


def month_sequence(end_date: date, count: int = 3) -> list[str]:
    months: list[str] = []
    year = end_date.year
    month = end_date.month
    for _ in range(count):
        months.append(f"{year:04d}{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return months


def parse_mmddyyyy(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        month, day, year = text.split("/")
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def fetch_treasury_curve_observations(end_date: date, curve_type: str, tenor_label: str, month_count: int = 3) -> list[tuple[date, float]]:
    rows: list[tuple[date, float]] = []
    url_template = TREASURY_REAL_YIELD_CSV_URL if curve_type == "real" else TREASURY_NOMINAL_YIELD_CSV_URL
    for year_month in month_sequence(end_date, month_count):
        text = fetch_text(url_template.format(year_month=year_month))
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            row_date = parse_mmddyyyy(row.get("Date"))
            value = parse_float(row.get(tenor_label))
            if row_date is None or value is None:
                continue
            rows.append((row_date, value))
    deduped: dict[date, float] = {}
    for row_date, value in rows:
        deduped[row_date] = value
    ordered = sorted(deduped.items(), key=lambda item: item[0])
    return ordered


def treasury_curve_bp_change(end_date: date, curve_type: str, tenor_label: str, lookback_observations: int) -> dict[str, Any]:
    rows = fetch_treasury_curve_observations(end_date, curve_type, tenor_label)
    latest, reference = series_latest_and_previous_month(rows)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    return {
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_bp": round((latest_value - reference_value) * 100.0, 2),
    }


def treasury_breakeven_bp_change(end_date: date, tenor_label: str, lookback_observations: int) -> dict[str, Any]:
    real_rows = fetch_treasury_curve_observations(end_date, "real", tenor_label)
    nominal_rows = fetch_treasury_curve_observations(end_date, "nominal", tenor_label)
    real_map = {row_date: value for row_date, value in real_rows}
    nominal_map = {row_date: value for row_date, value in nominal_rows}
    shared_dates = sorted(set(real_map).intersection(nominal_map))
    rows = [(row_date, nominal_map[row_date] - real_map[row_date]) for row_date in shared_dates]
    latest, reference = series_latest_and_previous_month(rows)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    return {
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_bp": round((latest_value - reference_value) * 100.0, 2),
    }


def fed_h10_broad_dollar_pct_change(lookback_observations: int) -> dict[str, Any]:
    text = fetch_text(FED_H10_BROAD_DOLLAR_CSV_URL)
    reader = csv.reader(io.StringIO(text))
    rows: list[tuple[date, float]] = []
    for row in reader:
        if len(row) < 2:
            continue
        row_date = parse_iso_date(row[0])
        value = parse_float(row[1])
        if row_date is None or value is None:
            continue
        rows.append((row_date, value))
    rows.sort(key=lambda item: item[0])
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    change_pct = 0.0
    if reference_value != 0:
        change_pct = (latest_value / reference_value - 1.0) * 100.0
    return {
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_pct": round(change_pct, 2),
    }


def chicago_fed_anfci_abs_change(lookback_observations: int) -> dict[str, Any]:
    text = fetch_text(CHICAGO_FED_NFCI_CSV_URL)
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[date, float]] = []
    for row in reader:
        row_date = parse_mmddyyyy(row.get("Friday_of_Week"))
        value = parse_float(row.get("ANFCI"))
        if row_date is None or value is None:
            continue
        rows.append((row_date, value))
    rows.sort(key=lambda item: item[0])
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    return {
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_abs": round(latest_value - reference_value, 4),
    }


def cboe_vix_pct_change(lookback_observations: int) -> dict[str, Any]:
    text = fetch_text(CBOE_VIX_CSV_URL)
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[date, float]] = []
    for row in reader:
        row_date = parse_mmddyyyy(row.get("DATE"))
        value = parse_float(row.get("CLOSE"))
        if row_date is None or value is None:
            continue
        rows.append((row_date, value))
    rows.sort(key=lambda item: item[0])
    latest, reference = series_latest_and_lookback(rows, lookback_observations)
    if latest is None or reference is None:
        return {}
    latest_date, latest_value = latest
    reference_date, reference_value = reference
    change_pct = 0.0
    if reference_value != 0:
        change_pct = (latest_value / reference_value - 1.0) * 100.0
    return {
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "reference_date": reference_date.isoformat(),
        "reference_value": reference_value,
        "change_pct": round(change_pct, 2),
    }


def parse_nyfed_ref_rates(url: str) -> list[dict[str, Any]]:
    payload = json.loads(fetch_text(url))
    rows = safe_list(safe_dict(payload).get("refRates"))
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = safe_dict(row)
        row_date = parse_iso_date(item.get("effectiveDate"))
        rate = parse_float(item.get("percentRate"))
        volume = parse_float(item.get("volumeInBillions"))
        if row_date is None or rate is None:
            continue
        normalized.append(
            {
                "date": row_date,
                "rate": rate,
                "volume_bil": volume,
                "type": clean_text(item.get("type")),
            }
        )
    normalized.sort(key=lambda item: item["date"])
    return normalized


def series_latest_and_lookback_dict(rows: list[dict[str, Any]], lookback_observations: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not rows:
        return None, None
    latest = rows[-1]
    reference = rows[-1 - lookback_observations] if len(rows) > lookback_observations else rows[0]
    return latest, reference


def nyfed_liquidity_proxy(lookback_observations: int) -> dict[str, Any]:
    count = max(lookback_observations + 5, 25)
    sofr_rows = parse_nyfed_ref_rates(NYFED_SOFR_JSON_URL.format(count=count))
    bgcr_rows = parse_nyfed_ref_rates(NYFED_BGCR_JSON_URL.format(count=count))
    tgcr_rows = parse_nyfed_ref_rates(NYFED_TGCR_JSON_URL.format(count=count))
    effr_rows = parse_nyfed_ref_rates(NYFED_EFFR_JSON_URL.format(count=count))

    sofr_latest, sofr_reference = series_latest_and_lookback_dict(sofr_rows, lookback_observations)
    bgcr_latest, _ = series_latest_and_lookback_dict(bgcr_rows, lookback_observations)
    tgcr_latest, _ = series_latest_and_lookback_dict(tgcr_rows, lookback_observations)
    effr_latest, _ = series_latest_and_lookback_dict(effr_rows, lookback_observations)
    if sofr_latest is None or sofr_reference is None or effr_latest is None:
        return {}

    latest_rate = parse_float(sofr_latest.get("rate"))
    reference_rate = parse_float(sofr_reference.get("rate"))
    latest_volume = parse_float(sofr_latest.get("volume_bil"))
    reference_volume = parse_float(sofr_reference.get("volume_bil"))
    effr_rate = parse_float(effr_latest.get("rate"))
    bgcr_rate = parse_float(safe_dict(bgcr_latest).get("rate"))
    tgcr_rate = parse_float(safe_dict(tgcr_latest).get("rate"))
    if latest_rate is None or reference_rate is None or effr_rate is None:
        return {}

    volume_change_pct = None
    if latest_volume is not None and reference_volume not in (None, 0):
        volume_change_pct = round((latest_volume / reference_volume - 1.0) * 100.0, 2)

    return {
        "latest_date": safe_dict(sofr_latest).get("date").isoformat(),
        "sofr_latest": latest_rate,
        "sofr_change_bp": round((latest_rate - reference_rate) * 100.0, 2),
        "sofr_effr_spread_bp": round((latest_rate - effr_rate) * 100.0, 2),
        "sofr_bgcr_spread_bp": round((latest_rate - bgcr_rate) * 100.0, 2) if bgcr_rate is not None else None,
        "sofr_tgcr_spread_bp": round((latest_rate - tgcr_rate) * 100.0, 2) if tgcr_rate is not None else None,
        "sofr_volume_bil": latest_volume,
        "sofr_volume_change_pct": volume_change_pct,
    }


def fetch_treasury_tga_snapshot(lookback_observations: int) -> dict[str, Any]:
    query = urlencode(
        {
            "fields": "record_date,account_type,close_today_bal",
            "sort": "-record_date",
            "page[size]": max(lookback_observations * 12, 365),
            "format": "json",
        }
    )
    payload = json.loads(fetch_text(f"{TREASURY_TGA_API_URL}?{query}"))
    rows = safe_list(safe_dict(payload).get("data"))
    parsed_rows: list[tuple[date, float, str]] = []
    for row in rows:
        item = safe_dict(row)
        account_type = clean_text(item.get("account_type"))
        lowered = account_type.lower()
        if "opening balance" in lowered or "deposit" in lowered or "withdrawal" in lowered:
            continue
        if "general account" not in lowered and "treasury general account" not in lowered and "tga" not in lowered:
            continue
        record_date = parse_iso_date(item.get("record_date"))
        balance = parse_float(item.get("close_today_bal"))
        if record_date is None or balance is None:
            continue
        parsed_rows.append((record_date, balance, account_type))
    parsed_rows.sort(key=lambda item: item[0])
    if not parsed_rows:
        raise ValueError("treasury_tga_no_non_null_closing_balance")
    latest = parsed_rows[-1]
    reference = parsed_rows[-1 - lookback_observations] if len(parsed_rows) > lookback_observations else parsed_rows[0]
    return {
        "latest_date": latest[0].isoformat(),
        "latest_value_mil": latest[1],
        "reference_date": reference[0].isoformat(),
        "reference_value_mil": reference[1],
        "change_bil": round((latest[1] - reference[1]) / 1000.0, 2),
        "account_type": latest[2],
    }


def merge_live_fill(base: dict[str, Any], incoming: dict[str, Any], fill_mode: str) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if value is None:
            continue
        if fill_mode == "override" or key not in merged or merged.get(key) in (None, "", []):
            merged[key] = value
    return merged


def load_seed_snapshot(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = load_json(path)
    snapshot = safe_dict(payload.get("signal_snapshot"))
    if snapshot:
        return snapshot
    return safe_dict(payload)


def build_seed_payload(request: dict[str, Any], live_fetch_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of": clean_text(request.get("as_of")),
        "analysis_time": clean_text(request.get("analysis_time")),
        "live_data_provider": clean_text(request.get("live_data_provider")),
        "signal_snapshot": deepcopy(safe_dict(request.get("signal_snapshot"))),
        "live_fetch_summary": deepcopy(live_fetch_summary),
    }


def fetch_live_signal_snapshot(raw_request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = clean_text(raw_request.get("live_data_provider")).lower() or DEFAULT_LIVE_DATA_PROVIDER
    if provider in {"", "none"}:
        return {}, {"provider": "none", "status": "skipped", "fetched": [], "warnings": []}
    if provider not in {"fred_public", "public_macro_mix", "treasury_fed_public"}:
        return {}, {
            "provider": provider,
            "status": "unsupported",
            "fetched": [],
            "warnings": [f"unsupported_provider:{provider}"],
        }

    lookback = int(raw_request.get("lookback_trading_days", DEFAULT_LOOKBACK_TRADING_DAYS) or DEFAULT_LOOKBACK_TRADING_DAYS)
    fred_series = {**DEFAULT_FRED_SERIES, **safe_dict(raw_request.get("fred_series"))}
    as_of = parse_iso_date(raw_request.get("as_of")) or parse_iso_date(raw_request.get("analysis_time")) or datetime.now(UTC).date()
    snapshot: dict[str, Any] = {}
    fetched: list[str] = []
    warnings: list[str] = []

    def try_fetch(label: str, fn: Any) -> dict[str, Any]:
        try:
            payload = fn()
            if payload:
                fetched.append(label)
            return payload
        except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch
            warnings.append(f"{label}:{clean_text(exc)}")
            return {}

    if provider in {"public_macro_mix", "treasury_fed_public"}:
        real_yield = try_fetch("real_yield_10y", lambda: treasury_curve_bp_change(as_of, "real", "10 YR", lookback))
    else:
        real_yield = try_fetch("real_yield_10y", lambda: fred_bp_change(clean_text(fred_series.get("real_yield_10y")), lookback))
    if real_yield:
        snapshot["real_yield_10y_change_bp_20d"] = real_yield.get("change_bp")
        snapshot["real_yield_10y_latest"] = real_yield.get("latest_value")

    if provider in {"public_macro_mix", "treasury_fed_public"}:
        dxy = try_fetch("dxy_broad", lambda: fed_h10_broad_dollar_pct_change(lookback))
    else:
        dxy = try_fetch("dxy_broad", lambda: fred_pct_change(clean_text(fred_series.get("dxy_broad")), lookback))
    if dxy:
        snapshot["dxy_change_pct_20d"] = dxy.get("change_pct")
        snapshot["dxy_latest"] = dxy.get("latest_value")

    if provider in {"public_macro_mix", "treasury_fed_public"}:
        nominal_yield = try_fetch("nominal_yield_10y", lambda: treasury_curve_bp_change(as_of, "nominal", "10 Yr", lookback))
        breakeven: dict[str, Any] = {}
        if nominal_yield and real_yield:
            latest_nominal = parse_float(nominal_yield.get("latest_value"))
            latest_real = parse_float(real_yield.get("latest_value"))
            nominal_change = parse_float(nominal_yield.get("change_bp"))
            real_change = parse_float(real_yield.get("change_bp"))
            if latest_nominal is not None and latest_real is not None and nominal_change is not None and real_change is not None:
                breakeven = {
                    "latest_value": round(latest_nominal - latest_real, 4),
                    "change_bp": round(nominal_change - real_change, 2),
                }
    else:
        breakeven = try_fetch("breakeven_10y", lambda: fred_bp_change(clean_text(fred_series.get("breakeven_10y")), lookback))
    if breakeven:
        snapshot["breakeven_10y_change_bp_20d"] = breakeven.get("change_bp")
        snapshot["breakeven_10y_latest"] = breakeven.get("latest_value")

    oil = try_fetch("oil_wti", lambda: fred_pct_change(clean_text(fred_series.get("oil_wti")), lookback)) if provider == "fred_public" else {}
    if oil:
        snapshot["brent_change_pct_20d"] = oil.get("change_pct")
        snapshot["oil_latest"] = oil.get("latest_value")

    spx = try_fetch("sp500", lambda: fred_pct_change(clean_text(fred_series.get("sp500")), lookback)) if provider == "fred_public" else {}
    if spx:
        snapshot["spx_change_pct_20d"] = spx.get("change_pct")
        snapshot["spx_latest"] = spx.get("latest_value")

    qqq = try_fetch("nasdaq", lambda: fred_pct_change(clean_text(fred_series.get("nasdaq")), lookback)) if provider == "fred_public" else {}
    if qqq:
        snapshot["qqq_change_pct_20d"] = qqq.get("change_pct")
        snapshot["qqq_latest"] = qqq.get("latest_value")

    if provider in {"public_macro_mix", "treasury_fed_public"}:
        financial_conditions = try_fetch("financial_conditions", lambda: chicago_fed_anfci_abs_change(max(1, lookback // 5)))
    else:
        financial_conditions = try_fetch("financial_conditions", lambda: fred_abs_change(clean_text(fred_series.get("financial_conditions")), 20))
    if financial_conditions:
        snapshot["financial_conditions_change_4w"] = financial_conditions.get("change_abs")
        snapshot["financial_conditions_latest"] = financial_conditions.get("latest_value")

    if provider in {"public_macro_mix", "treasury_fed_public"}:
        vix = try_fetch("vix", lambda: cboe_vix_pct_change(lookback))
        if vix:
            snapshot["vix_change_pct_20d"] = vix.get("change_pct")
            snapshot["vix_latest"] = vix.get("latest_value")
        liquidity_proxy = try_fetch("liquidity_proxy", lambda: nyfed_liquidity_proxy(lookback))
        if liquidity_proxy:
            snapshot["sofr_change_bp_20d"] = liquidity_proxy.get("sofr_change_bp")
            snapshot["sofr_effr_spread_bp"] = liquidity_proxy.get("sofr_effr_spread_bp")
            snapshot["sofr_bgcr_spread_bp"] = liquidity_proxy.get("sofr_bgcr_spread_bp")
            snapshot["sofr_tgcr_spread_bp"] = liquidity_proxy.get("sofr_tgcr_spread_bp")
            snapshot["sofr_volume_bil"] = liquidity_proxy.get("sofr_volume_bil")
            snapshot["sofr_volume_change_pct"] = liquidity_proxy.get("sofr_volume_change_pct")

    if bool(raw_request.get("treasury_tga_enabled", True)):
        treasury_tga = try_fetch("treasury_tga", lambda: fetch_treasury_tga_snapshot(lookback))
        if treasury_tga:
            snapshot["liquidity_drain_usd_bil_20d"] = treasury_tga.get("change_bil")
            snapshot["treasury_tga_latest_bil"] = round(float(treasury_tga.get("latest_value_mil") or 0.0) / 1000.0, 2)

    return snapshot, {
        "provider": provider,
        "status": "ok" if fetched else "no_data",
        "fetched": fetched,
        "warnings": warnings,
    }


def resolve_signal_state(raw: Any, numeric: Any, *, thresholds: tuple[float, float], labels: tuple[str, str, str], aliases: dict[str, str] | None = None) -> str:
    text = clean_text(raw).lower()
    normalized_aliases = aliases or {}
    if text in normalized_aliases:
        return normalized_aliases[text]
    if text in labels:
        return text
    try:
        value = float(numeric)
    except (TypeError, ValueError):
        return ""
    low, high = thresholds
    negative_label, neutral_label, positive_label = labels
    if value <= low:
        return negative_label
    if value >= high:
        return positive_label
    return neutral_label


def resolve_equity_confirmation_state(raw: Any, spx_change: Any, qqq_change: Any, vix_change: Any = None) -> str:
    text = clean_text(raw).lower()
    aliases = {
        "confirming": "confirming",
        "confirmed": "confirming",
        "mixed": "mixed",
        "failing": "failing",
        "failed": "failing",
    }
    if text in aliases:
        return aliases[text]
    try:
        spx = float(spx_change)
        qqq = float(qqq_change)
    except (TypeError, ValueError):
        try:
            vix = float(vix_change)
        except (TypeError, ValueError):
            return ""
        if vix <= -5.0:
            return "confirming"
        if vix >= 5.0:
            return "failing"
        return "mixed"
    if spx >= 1.0 and qqq >= 1.0:
        return "confirming"
    if spx <= -1.0 and qqq <= -1.0:
        return "failing"
    return "mixed"


def resolve_growth_state(raw: Any, pmi_level: Any, pmi_change: Any) -> str:
    text = clean_text(raw).lower()
    aliases = {
        "resilient": "resilient",
        "improving": "improving",
        "stable": "stable",
        "softening": "softening",
        "breaking": "breaking",
    }
    if text in aliases:
        return aliases[text]
    try:
        level = float(pmi_level)
        change = float(pmi_change)
    except (TypeError, ValueError):
        return ""
    if level < 50.0 and change < 0:
        return "breaking"
    if change >= 1.0:
        return "improving"
    if change <= -1.0:
        return "softening"
    if level >= 50.0:
        return "stable"
    return "softening"


def resolve_inflation_state(raw: Any, inflation_change_bp: Any) -> str:
    text = clean_text(raw).lower()
    aliases = {
        "easing": "easing",
        "stable": "stable",
        "sticky": "sticky",
        "reaccelerating": "reaccelerating",
    }
    if text in aliases:
        return aliases[text]
    try:
        value = float(inflation_change_bp)
    except (TypeError, ValueError):
        return ""
    if value <= -10.0:
        return "easing"
    if value >= 10.0:
        return "reaccelerating"
    return "stable"


def resolve_financial_conditions_state(raw: Any, latest_level: Any, change_abs: Any) -> str:
    text = clean_text(raw).lower()
    aliases = {
        "easing": "easing",
        "neutral": "neutral",
        "tightening": "tightening",
    }
    if text in aliases:
        return aliases[text]
    try:
        latest = float(latest_level)
        change = float(change_abs)
    except (TypeError, ValueError):
        return ""
    if latest <= -0.25 and change < 0.10:
        return "neutral"
    if latest <= -0.50 and change <= 0:
        return "easing"
    if change >= 0.10 or latest >= 0.0:
        return "tightening"
    return "neutral"


def resolve_liquidity_state(
    raw: Any,
    tga_change_bil: Any,
    sofr_effr_spread_bp: Any,
    sofr_bgcr_spread_bp: Any,
    sofr_volume_change_pct: Any,
) -> str:
    text = clean_text(raw).lower()
    aliases = {
        "easing": "easing",
        "neutral": "neutral",
        "draining": "draining",
        "stressed": "stressed",
    }
    if text in aliases:
        return aliases[text]

    try:
        tga_change = float(tga_change_bil)
    except (TypeError, ValueError):
        tga_change = None
    try:
        sofr_effr = float(sofr_effr_spread_bp)
    except (TypeError, ValueError):
        sofr_effr = None
    try:
        sofr_bgcr = float(sofr_bgcr_spread_bp)
    except (TypeError, ValueError):
        sofr_bgcr = None
    try:
        volume_change = float(sofr_volume_change_pct)
    except (TypeError, ValueError):
        volume_change = None

    if (
        (sofr_effr is not None and sofr_effr >= 8.0)
        or (sofr_bgcr is not None and sofr_bgcr >= 6.0)
        or (volume_change is not None and volume_change <= -20.0)
    ):
        if (
            (sofr_effr is not None and sofr_effr >= 12.0)
            or (sofr_bgcr is not None and sofr_bgcr >= 10.0)
            or (volume_change is not None and volume_change <= -30.0)
        ):
            return "stressed"
        return "draining"

    if tga_change is not None:
        if tga_change >= 100.0:
            return "draining"
        if tga_change <= -100.0:
            return "easing"

    if (
        (sofr_effr is not None and sofr_effr <= 3.0)
        and (sofr_bgcr is None or sofr_bgcr <= 3.0)
        and (volume_change is None or volume_change >= -10.0)
    ):
        return "neutral"
    if (
        (sofr_effr is not None and abs(sofr_effr) <= 10.0)
        and (sofr_bgcr is None or abs(sofr_bgcr) <= 10.0)
        and (volume_change is None or volume_change >= -15.0)
    ):
        return "neutral"
    return ""


def describe_state(state: str, mapping: dict[str, str], fallback: str = "n/a") -> str:
    return mapping.get(clean_text(state).lower(), fallback)


def normalize_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    live_snapshot, live_fetch_summary = fetch_live_signal_snapshot(raw_request)
    analysis_time = isoformat_or_blank(raw_request.get("analysis_time"))
    analysis_date = parse_iso_date(raw_request.get("as_of")) or parse_iso_date(analysis_time) or datetime.now(UTC).date()
    signal_states = safe_dict(raw_request.get("signal_states"))
    signal_snapshot = safe_dict(raw_request.get("signal_snapshot"))
    fill_mode = clean_text(raw_request.get("live_fill_mode")).lower() or DEFAULT_LIVE_FILL_MODE
    signal_snapshot = merge_live_fill(signal_snapshot, live_snapshot, fill_mode)
    seed_snapshot_path = resolve_local_path(raw_request.get("seed_snapshot_path"))
    seed_fill_mode = clean_text(raw_request.get("seed_fill_mode")).lower() or DEFAULT_SEED_FILL_MODE
    seed_snapshot = load_seed_snapshot(seed_snapshot_path)
    used_seed = False
    if seed_snapshot:
        if seed_fill_mode == "override":
            signal_snapshot = merge_live_fill(signal_snapshot, seed_snapshot, "override")
            used_seed = True
        elif seed_fill_mode == "missing_only":
            signal_snapshot = merge_live_fill(signal_snapshot, seed_snapshot, "missing_only")
            used_seed = True
        elif seed_fill_mode == "fallback_on_no_data" and clean_text(live_fetch_summary.get("status")) in {"skipped", "no_data", "unsupported"}:
            signal_snapshot = merge_live_fill(signal_snapshot, seed_snapshot, "missing_only")
            used_seed = True
    signal_notes = safe_dict(raw_request.get("signal_notes"))

    normalized_states = {
        "real_yield": resolve_signal_state(
            signal_states.get("real_yield"),
            signal_snapshot.get("real_yield_10y_change_bp_20d"),
            thresholds=(-5.0, 5.0),
            labels=("easing", "stable", "tightening"),
        ),
        "dxy": resolve_signal_state(
            signal_states.get("dxy"),
            signal_snapshot.get("dxy_change_pct_20d"),
            thresholds=(-0.75, 0.75),
            labels=("easing", "stable", "tightening"),
        ),
        "breakeven": resolve_signal_state(
            signal_states.get("breakeven"),
            signal_snapshot.get("breakeven_10y_change_bp_20d"),
            thresholds=(-10.0, 10.0),
            labels=("easing", "stable", "reaccelerating"),
        ),
        "financial_conditions": resolve_signal_state(
            signal_states.get("financial_conditions"),
            signal_snapshot.get("financial_conditions_change_4w"),
            thresholds=(-0.05, 0.05),
            labels=("easing", "neutral", "tightening"),
        ),
        "liquidity": resolve_signal_state(
            signal_states.get("liquidity"),
            signal_snapshot.get("liquidity_drain_usd_bil_20d"),
            thresholds=(-100.0, 100.0),
            labels=("easing", "neutral", "draining"),
            aliases={"stressed": "stressed"},
        ),
        "oil": resolve_signal_state(
            signal_states.get("oil"),
            signal_snapshot.get("brent_change_pct_20d"),
            thresholds=(3.0, 8.0),
            labels=("contained", "firm", "inflationary_spike"),
        ),
        "term_premium": resolve_signal_state(
            signal_states.get("term_premium"),
            signal_snapshot.get("term_premium_10y_change_bp_20d"),
            thresholds=(-10.0, 10.0),
            labels=("easing", "elevated", "rising"),
        ),
        "equity_confirmation": resolve_equity_confirmation_state(
            signal_states.get("equity_confirmation"),
            signal_snapshot.get("spx_change_pct_20d"),
            signal_snapshot.get("qqq_change_pct_20d"),
            signal_snapshot.get("vix_change_pct_20d"),
        ),
        "growth": resolve_growth_state(
            signal_states.get("growth"),
            signal_snapshot.get("pmi_level"),
            signal_snapshot.get("pmi_change"),
        ),
        "inflation": resolve_inflation_state(
            signal_states.get("inflation"),
            signal_snapshot.get("core_inflation_3m_ann_change_bp_20d"),
        ),
    }
    normalized_states["financial_conditions"] = resolve_financial_conditions_state(
        signal_states.get("financial_conditions"),
        signal_snapshot.get("financial_conditions_latest"),
        signal_snapshot.get("financial_conditions_change_4w"),
    ) or normalized_states.get("financial_conditions", "")
    normalized_states["liquidity"] = resolve_liquidity_state(
        signal_states.get("liquidity"),
        signal_snapshot.get("liquidity_drain_usd_bil_20d"),
        signal_snapshot.get("sofr_effr_spread_bp"),
        signal_snapshot.get("sofr_bgcr_spread_bp"),
        signal_snapshot.get("sofr_volume_change_pct"),
    ) or normalized_states.get("liquidity", "")
    return {
        "analysis_time": analysis_time,
        "as_of": analysis_date.isoformat(),
        "live_data_provider": clean_text(raw_request.get("live_data_provider")) or DEFAULT_LIVE_DATA_PROVIDER,
        "live_fill_mode": fill_mode,
        "lookback_trading_days": int(raw_request.get("lookback_trading_days", DEFAULT_LOOKBACK_TRADING_DAYS) or DEFAULT_LOOKBACK_TRADING_DAYS),
        "integration_mode": clean_text(raw_request.get("integration_mode")) or "advisory_only",
        "seed_snapshot_path": str(seed_snapshot_path) if seed_snapshot_path is not None else "",
        "seed_fill_mode": seed_fill_mode,
        "write_live_seed_cache": bool(raw_request.get("write_live_seed_cache", False)),
        "signal_states": normalized_states,
        "signal_snapshot": deepcopy(signal_snapshot),
        "signal_notes": {key: clean_text(value) for key, value in signal_notes.items() if clean_text(value)},
        "source_frameworks": unique_strings(safe_list(raw_request.get("source_frameworks"))) or list(DEFAULT_SOURCE_FRAMEWORKS),
        "evidence": unique_strings(safe_list(raw_request.get("evidence"))),
        "shortlist_request_path": clean_text(raw_request.get("shortlist_request_path")),
        "live_fetch_summary": live_fetch_summary,
        "seed_summary": {
            "path": str(seed_snapshot_path) if seed_snapshot_path is not None else "",
            "loaded": bool(seed_snapshot),
            "used": used_seed,
            "fill_mode": seed_fill_mode,
        },
    }


def build_scorecard(states: dict[str, str]) -> dict[str, float]:
    primary = 0.0
    primary += {"easing": 1.2, "stable": 0.4, "tightening": -1.2}.get(states.get("real_yield", ""), 0.0)
    primary += {"easing": 1.0, "stable": 0.3, "tightening": -1.0}.get(states.get("dxy", ""), 0.0)

    confirmation = 0.0
    confirmation += {"easing": 0.8, "neutral": 0.0, "tightening": -0.8}.get(states.get("financial_conditions", ""), 0.0)
    confirmation += {"easing": 0.8, "neutral": 0.0, "draining": -0.8, "stressed": -1.4}.get(states.get("liquidity", ""), 0.0)
    confirmation += {"confirming": 0.8, "mixed": 0.0, "failing": -0.8}.get(states.get("equity_confirmation", ""), 0.0)

    controls = 0.0
    controls += {"easing": 0.2, "stable": 0.0, "reaccelerating": -0.5}.get(states.get("breakeven", ""), 0.0)
    controls += {"contained": 0.0, "firm": -0.2, "inflationary_spike": -0.6}.get(states.get("oil", ""), 0.0)
    controls += {"easing": 0.2, "elevated": -0.2, "rising": -0.5}.get(states.get("term_premium", ""), 0.0)

    total = round(primary + confirmation + controls, 2)
    return {
        "primary_trigger_score": round(primary, 2),
        "confirmation_score": round(confirmation, 2),
        "control_score": round(controls, 2),
        "total_score": total,
    }


def classify_growth_inflation_regime(states: dict[str, str]) -> str:
    growth = states.get("growth", "")
    inflation = states.get("inflation", "")
    if growth in {"resilient", "improving", "stable"} and inflation in {"easing", "stable"}:
        return "soft_landing_or_disinflation"
    if growth in {"resilient", "stable"} and inflation in {"sticky", "reaccelerating"}:
        return "reflation_without_break"
    if growth == "softening" and inflation in {"sticky", "reaccelerating"}:
        return "early_stagflation_risk"
    if growth == "breaking" and inflation in {"easing", "stable"}:
        return "growth_scare_disinflation"
    if growth == "breaking" and inflation in {"sticky", "reaccelerating"}:
        return "stagflation_or_policy_stress"
    return "mixed_transition"


def classify_health_label(states: dict[str, str], scorecard: dict[str, float]) -> tuple[str, str, str]:
    primary = scorecard["primary_trigger_score"]
    total = scorecard["total_score"]
    liquidity = states.get("liquidity", "")
    financial_conditions = states.get("financial_conditions", "")
    equity = states.get("equity_confirmation", "")
    term_premium = states.get("term_premium", "")

    if primary <= -1.5 and (liquidity in {"draining", "stressed"} or financial_conditions == "tightening" or equity == "failing"):
        return "adverse_risk_window", "defensive", "closing_or_hostile"
    if total >= 2.5 and primary >= 1.0 and equity == "confirming" and liquidity != "stressed":
        posture = "constructive_risk_on" if term_premium != "rising" else "selective_risk_on"
        return "favorable_risk_window", posture, "open"
    if total >= 1.0 and primary >= 0.5:
        return "tentative_favorable_risk_window", "selective_risk_on", "open_but_confirmation_needed"
    if total <= -1.0:
        posture = "defensive" if liquidity == "stressed" or equity == "failing" else "selective_defensive"
        return "adverse_risk_window", posture, "closing_or_hostile"
    return "mixed_or_neutral_window", "neutral_selective", "mixed_window"


def confidence_label(states: dict[str, str], scorecard: dict[str, float]) -> str:
    populated = sum(1 for value in states.values() if clean_text(value))
    label = "low"
    if populated >= 8:
        label = "high"
    elif populated >= 5:
        label = "medium"
    primary = scorecard["primary_trigger_score"]
    confirmation = scorecard["confirmation_score"]
    if primary > 0.8 and confirmation < -0.4 and label == "high":
        return "medium"
    if primary < -0.8 and confirmation > 0.4 and label == "high":
        return "medium"
    return label


def signal_text(name: str, state: str, request: dict[str, Any]) -> str:
    override = clean_text(safe_dict(request.get("signal_notes")).get(f"{name}_signal"))
    if override:
        return override
    tables = {
        "real_yield": {
            "easing": "10Y real yield stable to down after prior tightening",
            "stable": "10Y real yield no longer worsening materially",
            "tightening": "10Y real yield still rising and keeping valuation pressure alive",
        },
        "dxy": {
            "easing": "broad dollar rollover / sideways after prior squeeze",
            "stable": "broad dollar not worsening, but not clearly easing either",
            "tightening": "broad dollar still squeezing global liquidity",
        },
        "breakeven": {
            "easing": "breakevens easing; inflation expectations are not worsening",
            "stable": "breakevens stable; no clear inflation de-anchoring",
            "reaccelerating": "breakevens reaccelerating; inflation expectations are becoming a headwind again",
        },
        "financial_conditions": {
            "easing": "financial conditions easing; broad stress is not propagating",
            "neutral": "not fully easy, but stress is not broadening",
            "tightening": "financial conditions tightening across more than one channel",
        },
        "liquidity": {
            "easing": "liquidity backdrop supportive; drain pressure is easing",
            "neutral": "watch TGA / tax / funding pressure, but no acute squeeze",
            "draining": "liquidity is draining and can cap risk-asset follow-through",
            "stressed": "liquidity stress is active and can break tactical rebounds quickly",
        },
        "oil": {
            "contained": "oil is not forcing a new stagflation call",
            "firm": "oil is firm enough to stay on watch, but not yet a decisive macro break",
            "inflationary_spike": "oil is turning into a fresh inflation / policy headwind",
        },
        "term_premium": {
            "easing": "term premium is easing and helping duration-sensitive risk assets",
            "elevated": "term premium stays elevated and remains a valuation headwind",
            "rising": "term premium is rising and tightening broad discount-rate conditions",
        },
        "equity_confirmation": {
            "confirming": "equities are confirming the easing impulse instead of failing every bounce",
            "mixed": "equities are tradable, but confirmation is incomplete",
            "failing": "equities are failing to confirm the macro impulse",
        },
    }
    return describe_state(state, tables.get(name, {}))


def shortlist_guidance(health_label: str, risk_posture: str, window_state: str) -> dict[str, Any]:
    if risk_posture in {"constructive_risk_on", "selective_risk_on"}:
        favored_styles = ["growth_beta", "leaders_with_hard_catalysts"]
        penalized_styles = ["late_defensive_chasing"] if risk_posture == "constructive_risk_on" else []
        sizing = "probe_then_add_on_confirmation" if window_state == "open_but_confirmation_needed" else "normal_selective_risk"
    elif risk_posture in {"defensive", "selective_defensive"}:
        favored_styles = ["defensive", "policy_backed_capex", "cashflow_resilience"]
        penalized_styles = ["growth_beta_without_hard_catalyst"]
        sizing = "smaller_size_and_faster_invalidation"
    else:
        favored_styles = ["mixed", "idiosyncratic_catalyst"]
        penalized_styles = []
        sizing = "selective_and_case_by_case"
    return {
        "risk_posture": risk_posture,
        "window_state": window_state,
        "favored_styles": favored_styles,
        "penalized_styles": penalized_styles,
        "sizing_guidance": sizing,
    }


def build_macro_health_overlay(normalized_request: dict[str, Any]) -> dict[str, Any]:
    states = safe_dict(normalized_request.get("signal_states"))
    scorecard = build_scorecard(states)
    growth_inflation = classify_growth_inflation_regime(states)
    health_label, risk_posture, window_state = classify_health_label(states, scorecard)
    confidence = confidence_label(states, scorecard)
    # data_coverage_ratio: fraction of the 10 canonical signal slots that
    # have a non-empty state.  Lets downstream consumers know how much of
    # the overlay is actually data-backed vs defaulted.
    canonical_signal_keys = (
        "real_yield", "dxy", "breakeven", "financial_conditions",
        "liquidity", "oil", "term_premium", "equity_confirmation",
        "growth", "inflation",
    )
    populated_count = sum(1 for k in canonical_signal_keys if clean_text(states.get(k)))
    data_coverage_ratio = round(populated_count / len(canonical_signal_keys), 2)
    return {
        "as_of": clean_text(normalized_request.get("as_of")),
        "health_label": health_label,
        "risk_posture": risk_posture,
        "window_state": window_state,
        "growth_inflation_regime": growth_inflation,
        "data_coverage_ratio": data_coverage_ratio,
        "real_yield_signal": signal_text("real_yield", clean_text(states.get("real_yield")), normalized_request),
        "dxy_signal": signal_text("dxy", clean_text(states.get("dxy")), normalized_request),
        "breakeven_signal": signal_text("breakeven", clean_text(states.get("breakeven")), normalized_request),
        "financial_conditions_signal": signal_text("financial_conditions", clean_text(states.get("financial_conditions")), normalized_request),
        "liquidity_signal": signal_text("liquidity", clean_text(states.get("liquidity")), normalized_request),
        "oil_signal": signal_text("oil", clean_text(states.get("oil")), normalized_request),
        "term_premium_signal": signal_text("term_premium", clean_text(states.get("term_premium")), normalized_request),
        "equity_confirmation": signal_text("equity_confirmation", clean_text(states.get("equity_confirmation")), normalized_request),
        "confidence": confidence,
        "integration_mode": clean_text(normalized_request.get("integration_mode")) or "advisory_only",
        "source_frameworks": unique_strings(safe_list(normalized_request.get("source_frameworks"))),
        "takeaway": build_takeaway(health_label, risk_posture, window_state),
        "evidence": unique_strings(safe_list(normalized_request.get("evidence"))),
    }


def build_takeaway(health_label: str, risk_posture: str, window_state: str) -> str:
    if health_label == "favorable_risk_window":
        if window_state == "open":
            return "Risk assets have a cleaner tradable window, but stock-level setup quality still matters more than macro optimism."
        return "The macro backdrop is constructive, but follow-through still needs confirmation from liquidity and equity breadth."
    if health_label == "tentative_favorable_risk_window":
        return "Risk assets are tradable, but this still looks like a selective window rather than a broad all-clear."
    if health_label == "adverse_risk_window":
        return "Macro conditions argue for smaller sizing, faster invalidation, and more respect for defensive or policy-backed sectors."
    return "The macro backdrop is mixed, so downstream screening should stay selective and rely on hard catalysts."


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    overlay = safe_dict(result.get("macro_health_overlay"))
    scorecard = safe_dict(result.get("scorecard"))
    guidance = safe_dict(result.get("shortlist_guidance"))
    live_fetch_summary = safe_dict(request.get("live_fetch_summary"))
    seed_summary = safe_dict(result.get("seed_summary"))
    lines = [
        "# Macro Health Overlay",
        "",
        f"- As of: `{clean_text(overlay.get('as_of')) or clean_text(request.get('as_of'))}`",
        f"- Live data provider: `{clean_text(request.get('live_data_provider')) or 'none'}`",
        f"- Integration mode: `{clean_text(overlay.get('integration_mode')) or 'advisory_only'}`",
        "",
        f"**One-line judgment**: `{clean_text(overlay.get('health_label'))}` with risk posture `{clean_text(overlay.get('risk_posture'))}` and window state `{clean_text(overlay.get('window_state'))}`.",
    ]
    if clean_text(live_fetch_summary.get("provider")) not in {"", "none"}:
        lines.extend(
            [
                "",
                "## Live Fetch",
                "",
                f"- provider: `{clean_text(live_fetch_summary.get('provider'))}`",
                f"- status: `{clean_text(live_fetch_summary.get('status')) or 'n/a'}`",
                f"- fetched: `{', '.join(safe_list(live_fetch_summary.get('fetched'))) or 'none'}`",
            ]
        )
        warnings = [clean_text(item) for item in safe_list(live_fetch_summary.get("warnings")) if clean_text(item)]
        if warnings:
            lines.append(f"- warnings: `{'; '.join(warnings)}`")
    if clean_text(seed_summary.get("path")) or seed_summary.get("loaded") or seed_summary.get("written"):
        lines.extend(
            [
                "",
                "## Seed Cache",
                "",
                f"- path: `{clean_text(seed_summary.get('path')) or 'n/a'}`",
                f"- loaded: `{bool(seed_summary.get('loaded'))}`",
                f"- used: `{bool(seed_summary.get('used'))}`",
                f"- written: `{bool(seed_summary.get('written'))}`",
                f"- fill mode: `{clean_text(seed_summary.get('fill_mode')) or 'n/a'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Signal Board",
            "",
            "| Signal | Reading |",
            "|---|---|",
            f"| Growth / inflation regime | `{clean_text(overlay.get('growth_inflation_regime'))}` |",
            f"| 10Y real yield | `{clean_text(overlay.get('real_yield_signal'))}` |",
            f"| Dollar | `{clean_text(overlay.get('dxy_signal'))}` |",
            f"| Breakevens | `{clean_text(overlay.get('breakeven_signal'))}` |",
            f"| Financial conditions | `{clean_text(overlay.get('financial_conditions_signal'))}` |",
            f"| Liquidity | `{clean_text(overlay.get('liquidity_signal'))}` |",
            f"| Oil | `{clean_text(overlay.get('oil_signal'))}` |",
            f"| Term premium | `{clean_text(overlay.get('term_premium_signal'))}` |",
            f"| Equity confirmation | `{clean_text(overlay.get('equity_confirmation'))}` |",
            f"| Confidence | `{clean_text(overlay.get('confidence'))}` |",
            "",
            "## Scorecard",
            "",
            "| Bucket | Score |",
            "|---|---|",
            f"| Primary trigger cluster | `{scorecard.get('primary_trigger_score')}` |",
            f"| Confirmation cluster | `{scorecard.get('confirmation_score')}` |",
            f"| False-positive controls | `{scorecard.get('control_score')}` |",
            f"| Total | `{scorecard.get('total_score')}` |",
            "",
            "## Shortlist Guidance",
            "",
            f"- favored styles: `{', '.join(safe_list(guidance.get('favored_styles'))) or 'n/a'}`",
            f"- penalized styles: `{', '.join(safe_list(guidance.get('penalized_styles'))) or 'none'}`",
            f"- sizing guidance: `{clean_text(guidance.get('sizing_guidance')) or 'n/a'}`",
            f"- takeaway: `{clean_text(overlay.get('takeaway')) or 'n/a'}`",
        ]
    )
    evidence = safe_list(overlay.get("evidence"))
    if evidence:
        lines.extend(["", "## Evidence"])
        for bullet in evidence:
            lines.append(f"- {clean_text(bullet)}")
    if isinstance(result.get("resolved_shortlist_request"), dict):
        lines.extend(
            [
                "",
                "## Resolved Shortlist Request",
                "",
                "- `macro_health_overlay` has been merged into the supplied shortlist request.",
            ]
        )
    return "\n".join(lines) + "\n"


def resolve_request_path(value: Any) -> Path | None:
    text = clean_text(value)
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def build_macro_health_overlay_result(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_request)
    overlay = build_macro_health_overlay(request)
    scorecard = build_scorecard(safe_dict(request.get("signal_states")))
    guidance = shortlist_guidance(clean_text(overlay.get("health_label")), clean_text(overlay.get("risk_posture")), clean_text(overlay.get("window_state")))
    live_fetch_summary = deepcopy(safe_dict(request.get("live_fetch_summary")))
    seed_summary = deepcopy(safe_dict(request.get("seed_summary")))

    seed_snapshot_path = resolve_local_path(request.get("seed_snapshot_path"))
    if bool(request.get("write_live_seed_cache")) and seed_snapshot_path is not None and clean_text(live_fetch_summary.get("status")) == "ok":
        write_json(seed_snapshot_path, build_seed_payload(request, live_fetch_summary))
        seed_summary["written"] = True
        seed_summary["path"] = str(seed_snapshot_path)
    else:
        seed_summary["written"] = False

    resolved_shortlist_request: dict[str, Any] | None = None
    shortlist_request_path = resolve_request_path(request.get("shortlist_request_path"))
    if shortlist_request_path is not None and shortlist_request_path.exists():
        resolved_shortlist_request = load_json(shortlist_request_path)
        if isinstance(resolved_shortlist_request, dict):
            resolved_shortlist_request = deepcopy(resolved_shortlist_request)
            resolved_shortlist_request["macro_health_overlay"] = deepcopy(overlay)

    result = {
        "request": request,
        "macro_health_overlay": overlay,
        "scorecard": scorecard,
        "shortlist_guidance": guidance,
        "live_fetch_summary": live_fetch_summary,
        "seed_summary": seed_summary,
    }
    if resolved_shortlist_request is not None:
        result["resolved_shortlist_request"] = resolved_shortlist_request
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_macro_health_overlay",
    "build_macro_health_overlay_result",
    "build_scorecard",
    "load_json",
    "normalize_request",
    "write_json",
]
