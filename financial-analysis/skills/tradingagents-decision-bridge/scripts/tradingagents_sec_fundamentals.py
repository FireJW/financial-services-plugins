#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[3]
SEC_BASE_URL = "https://data.sec.gov"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_TICKERS_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
SEC_COMPANY_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
SEC_CACHE_DIR_NAME = ".tmp/tradingagents-sec-cache"
DEFAULT_SEC_USER_AGENT = "financial-services-plugins/0.1 (local operator use; contact not configured)"
NUMERIC_FACT_LIMIT = 6
RECENT_FILINGS_LIMIT = 5

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
QUARTERLY_FORMS = {"10-Q", "10-Q/A"}

INCOME_STATEMENT_METRICS = (
    ("Revenue", (("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"), ("us-gaap", "Revenues")), ("USD",)),
    ("Gross Profit", (("us-gaap", "GrossProfit"),), ("USD",)),
    ("Operating Income", (("us-gaap", "OperatingIncomeLoss"),), ("USD",)),
    ("Net Income", (("us-gaap", "NetIncomeLoss"),), ("USD",)),
    ("Diluted EPS", (("us-gaap", "EarningsPerShareDiluted"),), ("USD/shares", "USD-per-shares")),
)

BALANCE_SHEET_METRICS = (
    ("Cash & Equivalents", (("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),), ("USD",)),
    ("Current Assets", (("us-gaap", "AssetsCurrent"),), ("USD",)),
    ("Total Assets", (("us-gaap", "Assets"),), ("USD",)),
    ("Current Liabilities", (("us-gaap", "LiabilitiesCurrent"),), ("USD",)),
    ("Total Liabilities", (("us-gaap", "Liabilities"),), ("USD",)),
    (
        "Long-Term Debt",
        (
            ("us-gaap", "LongTermDebtNoncurrent"),
            ("us-gaap", "LongTermDebtAndCapitalLeaseObligations"),
        ),
        ("USD",),
    ),
    ("Stockholders' Equity", (("us-gaap", "StockholdersEquity"),), ("USD",)),
)

CASH_FLOW_METRICS = (
    ("Operating Cash Flow", (("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),), ("USD",)),
    (
        "Capital Expenditures",
        (
            ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
            ("us-gaap", "CapitalExpendituresIncurredButNotYetPaid"),
        ),
        ("USD",),
    ),
    ("Investing Cash Flow", (("us-gaap", "NetCashProvidedByUsedInInvestingActivities"),), ("USD",)),
    ("Financing Cash Flow", (("us-gaap", "NetCashProvidedByUsedInFinancingActivities"),), ("USD",)),
    ("Share-Based Compensation", (("us-gaap", "ShareBasedCompensation"),), ("USD",)),
)

OVERVIEW_METRICS = (
    ("Latest Revenue", INCOME_STATEMENT_METRICS[0][1], ("USD",)),
    ("Latest Net Income", INCOME_STATEMENT_METRICS[3][1], ("USD",)),
    ("Latest Diluted EPS", INCOME_STATEMENT_METRICS[4][1], ("USD/shares", "USD-per-shares")),
    ("Latest Cash & Equivalents", BALANCE_SHEET_METRICS[0][1], ("USD",)),
    ("Latest Total Assets", BALANCE_SHEET_METRICS[2][1], ("USD",)),
    ("Latest Total Liabilities", BALANCE_SHEET_METRICS[4][1], ("USD",)),
    ("Latest Stockholders' Equity", BALANCE_SHEET_METRICS[6][1], ("USD",)),
    ("Latest Operating Cash Flow", CASH_FLOW_METRICS[0][1], ("USD",)),
)

JsonFetcher = Callable[[str, str, int], Any]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def ascii_header_text(value: Any) -> str:
    return clean_text(value).encode("ascii", "ignore").decode("ascii").strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_date(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    candidates = [text, text.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            if len(candidate) == 10:
                return datetime.fromisoformat(candidate).replace(tzinfo=UTC)
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def cache_root() -> Path:
    return (REPO_ROOT / SEC_CACHE_DIR_NAME).resolve()


def cache_path(cache_name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_text(cache_name)).strip("._")
    if not slug:
        slug = "cache"
    return cache_root() / slug


def read_cached_json(path: Path, *, max_age_seconds: int) -> Any | None:
    try:
        age_seconds = datetime.now(UTC).timestamp() - path.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError:
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


def sec_user_agent(env: dict[str, str] | None = None) -> str:
    env_map = env or dict(os.environ)
    explicit = ascii_header_text(env_map.get("TRADINGAGENTS_SEC_USER_AGENT")) or ascii_header_text(env_map.get("SEC_API_USER_AGENT"))
    if explicit:
        return explicit
    git_name = ascii_header_text(git_config_value("user.name"))
    git_email = ascii_header_text(git_config_value("user.email"))
    if git_name and git_email:
        return f"financial-services-plugins/0.1 ({git_name}; {git_email})"
    if git_email:
        return f"financial-services-plugins/0.1 (contact: {git_email})"
    return DEFAULT_SEC_USER_AGENT


def git_config_value(key: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "config", key],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return clean_text(completed.stdout)


def fetch_sec_json(url: str, cache_name: str, max_age_seconds: int, *, env: dict[str, str] | None = None) -> Any:
    path = cache_path(cache_name)
    cached = read_cached_json(path, max_age_seconds=max_age_seconds)
    if cached is not None:
        return cached

    headers = {
        "User-Agent": sec_user_agent(env),
        "Accept": "application/json",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if path.exists():
            stale = read_cached_json(path, max_age_seconds=10 * 365 * 24 * 60 * 60)
            if stale is not None:
                return stale
        raise RuntimeError(f"SEC request failed with HTTP {exc.code} for {url}") from exc
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        if path.exists():
            stale = read_cached_json(path, max_age_seconds=10 * 365 * 24 * 60 * 60)
            if stale is not None:
                return stale
        raise RuntimeError(f"SEC request failed for {url}: {clean_text(str(exc)) or exc.__class__.__name__}") from exc

    write_cached_json(path, payload)
    return payload


def normalize_sec_ticker(ticker: str) -> str:
    normalized = clean_text(ticker).upper()
    if not normalized:
        raise ValueError("Ticker is blank.")
    if "." in normalized:
        raise ValueError(f"SEC fundamentals vendor supports U.S. tickers only, got `{normalized}`.")
    return normalized


def load_company_ticker_index(*, fetcher: JsonFetcher = fetch_sec_json) -> dict[str, dict[str, Any]]:
    payload = fetcher(SEC_TICKERS_URL, "company_tickers.json", SEC_TICKERS_CACHE_MAX_AGE_SECONDS)
    records = safe_list(payload) if isinstance(payload, list) else list(safe_dict(payload).values())
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        item = safe_dict(record)
        ticker = clean_text(item.get("ticker")).upper()
        cik = item.get("cik_str")
        title = clean_text(item.get("title"))
        if not ticker or cik in {None, ""}:
            continue
        index[ticker] = {
            "ticker": ticker,
            "title": title or ticker,
            "cik": str(cik).zfill(10),
        }
    return index


def resolve_company_record(ticker: str, *, fetcher: JsonFetcher = fetch_sec_json) -> dict[str, Any]:
    normalized_ticker = normalize_sec_ticker(ticker)
    index = load_company_ticker_index(fetcher=fetcher)
    record = safe_dict(index.get(normalized_ticker))
    if not record:
        raise ValueError(f"SEC ticker index does not contain `{normalized_ticker}`.")
    return record


def load_companyfacts(record: dict[str, Any], *, fetcher: JsonFetcher = fetch_sec_json) -> dict[str, Any]:
    cik = clean_text(record.get("cik"))
    if not cik:
        raise ValueError("SEC company record is missing CIK.")
    url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
    cache_name = f"companyfacts-{cik}.json"
    return safe_dict(fetcher(url, cache_name, SEC_COMPANY_CACHE_MAX_AGE_SECONDS))


def load_submissions(record: dict[str, Any], *, fetcher: JsonFetcher = fetch_sec_json) -> dict[str, Any]:
    cik = clean_text(record.get("cik"))
    if not cik:
        raise ValueError("SEC company record is missing CIK.")
    url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
    cache_name = f"submissions-{cik}.json"
    return safe_dict(fetcher(url, cache_name, SEC_COMPANY_CACHE_MAX_AGE_SECONDS))


def facts_bucket(companyfacts: dict[str, Any], taxonomy: str) -> dict[str, Any]:
    return safe_dict(safe_dict(companyfacts.get("facts")).get(taxonomy))


def choose_unit_entries(fact: dict[str, Any], preferred_units: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]]:
    units = safe_dict(fact.get("units"))
    for unit_name in preferred_units:
        entries = safe_list(units.get(unit_name))
        if entries:
            return unit_name, [safe_dict(item) for item in entries]
    for unit_name, entries in units.items():
        normalized_entries = [safe_dict(item) for item in safe_list(entries)]
        if normalized_entries:
            return clean_text(unit_name), normalized_entries
    return "", []


def entry_is_allowed(entry: dict[str, Any], *, freq: str | None, curr_date: str | None) -> bool:
    filed = parse_date(entry.get("filed"))
    ended = parse_date(entry.get("end"))
    cutoff = parse_date(curr_date)
    if cutoff is not None:
        if filed is not None and filed > cutoff:
            return False
        if ended is not None and ended > cutoff:
            return False

    if freq == "annual":
        fp = clean_text(entry.get("fp")).upper()
        form = clean_text(entry.get("form")).upper()
        if fp and fp != "FY":
            return False
        if form and form not in ANNUAL_FORMS:
            return False
    elif freq == "quarterly":
        fp = clean_text(entry.get("fp")).upper()
        form = clean_text(entry.get("form")).upper()
        if fp:
            if fp not in {"Q1", "Q2", "Q3", "Q4"}:
                return False
        elif form and form not in QUARTERLY_FORMS:
            return False
    return True


def normalize_entry(entry: dict[str, Any], *, unit: str) -> dict[str, Any]:
    return {
        "end": clean_text(entry.get("end")),
        "filed": clean_text(entry.get("filed")),
        "fy": clean_text(entry.get("fy")),
        "fp": clean_text(entry.get("fp")).upper(),
        "form": clean_text(entry.get("form")).upper(),
        "frame": clean_text(entry.get("frame")),
        "val": entry.get("val"),
        "unit": unit,
    }


def choose_metric_series(
    companyfacts: dict[str, Any],
    aliases: tuple[tuple[str, str], ...],
    *,
    preferred_units: tuple[str, ...],
    freq: str | None,
    curr_date: str | None,
) -> list[dict[str, Any]]:
    for taxonomy, concept in aliases:
        bucket = facts_bucket(companyfacts, taxonomy)
        fact = safe_dict(bucket.get(concept))
        if not fact:
            continue
        unit, entries = choose_unit_entries(fact, preferred_units)
        if not entries:
            continue
        normalized = [
            normalize_entry(item, unit=unit)
            for item in entries
            if entry_is_allowed(safe_dict(item), freq=freq, curr_date=curr_date)
        ]
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in normalized:
            key = (item["end"], item["fp"], item["form"])
            current = deduped.get(key)
            if current is None or clean_text(item.get("filed")) > clean_text(current.get("filed")):
                deduped[key] = item
        ordered = sorted(
            deduped.values(),
            key=lambda item: (clean_text(item.get("end")), clean_text(item.get("filed"))),
            reverse=True,
        )
        if ordered:
            return ordered[:NUMERIC_FACT_LIMIT]
    return []


def format_numeric_value(value: Any, unit: str) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return clean_text(value) or "n/a"
    magnitude = abs(float(value))
    if unit in {"USD/shares", "USD-per-shares"}:
        return f"{float(value):,.2f}"
    if unit == "shares":
        if magnitude >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B shares"
        if magnitude >= 1_000_000:
            return f"{value / 1_000_000:.2f}M shares"
        return f"{int(value):,}"
    if unit == "USD":
        if magnitude >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        if magnitude >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        if magnitude >= 1_000:
            return f"${value / 1_000:.2f}K"
        return f"${value:,.0f}"
    return f"{value:,.2f}" if isinstance(value, float) and not value.is_integer() else f"{value:,.0f}"


def period_label(entry: dict[str, Any]) -> str:
    end = clean_text(entry.get("end")) or "unknown"
    fp = clean_text(entry.get("fp")) or clean_text(entry.get("form")) or "period"
    return f"{end} ({fp})"


def build_statement_rows(
    companyfacts: dict[str, Any],
    metrics: tuple[tuple[str, tuple[tuple[str, str], ...], tuple[str, ...]], ...],
    *,
    freq: str,
    curr_date: str | None,
) -> list[tuple[str, list[str]]]:
    period_map: dict[str, dict[str, str]] = {}
    for label, aliases, preferred_units in metrics:
        series = choose_metric_series(companyfacts, aliases, preferred_units=preferred_units, freq=freq, curr_date=curr_date)
        for entry in series:
            key = period_label(entry)
            period_map.setdefault(key, {})
            period_map[key][label] = format_numeric_value(entry.get("val"), clean_text(entry.get("unit")))

    ordered_periods = list(period_map.keys())[:NUMERIC_FACT_LIMIT]
    rows: list[tuple[str, list[str]]] = []
    for period in ordered_periods:
        rows.append((period, [period_map[period].get(label, "n/a") for label, _, _ in metrics]))
    return rows


def markdown_table(headers: list[str], rows: list[tuple[str, list[str]]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for period, values in rows:
        lines.append("| " + " | ".join([period, *values]) + " |")
    return "\n".join(lines)


def recent_filings_text(submissions: dict[str, Any]) -> str:
    recent = safe_dict(safe_dict(submissions.get("filings")).get("recent"))
    forms = safe_list(recent.get("form"))
    filing_dates = safe_list(recent.get("filingDate"))
    accession_numbers = safe_list(recent.get("accessionNumber"))
    primary_docs = safe_list(recent.get("primaryDocument"))
    lines: list[str] = []
    for index, form in enumerate(forms[:RECENT_FILINGS_LIMIT]):
        filing_date = clean_text(filing_dates[index]) if index < len(filing_dates) else "unknown"
        accession = clean_text(accession_numbers[index]) if index < len(accession_numbers) else ""
        primary_doc = clean_text(primary_docs[index]) if index < len(primary_docs) else ""
        detail = " / ".join(item for item in [accession, primary_doc] if item)
        if detail:
            lines.append(f"- {filing_date}: {clean_text(form)} ({detail})")
        else:
            lines.append(f"- {filing_date}: {clean_text(form)}")
    return "\n".join(lines) if lines else "- No recent filings available."


def latest_metric_snapshot(companyfacts: dict[str, Any], curr_date: str | None) -> list[str]:
    lines: list[str] = []
    for label, aliases, preferred_units in OVERVIEW_METRICS:
        series = choose_metric_series(companyfacts, aliases, preferred_units=preferred_units, freq=None, curr_date=curr_date)
        if not series:
            continue
        latest = series[0]
        lines.append(f"- {label}: {format_numeric_value(latest.get('val'), clean_text(latest.get('unit')))} as of {period_label(latest)}")
    return lines


def company_header(record: dict[str, Any], companyfacts: dict[str, Any]) -> str:
    title = clean_text(companyfacts.get("entityName")) or clean_text(record.get("title")) or clean_text(record.get("ticker"))
    ticker = clean_text(record.get("ticker"))
    cik = clean_text(record.get("cik"))
    return f"{title} ({ticker}) | CIK {cik}"


def get_fundamentals(ticker: str, curr_date: str = None, *, fetcher: JsonFetcher = fetch_sec_json) -> str:
    record = resolve_company_record(ticker, fetcher=fetcher)
    companyfacts = load_companyfacts(record, fetcher=fetcher)
    submissions = load_submissions(record, fetcher=fetcher)
    header = company_header(record, companyfacts)
    snapshot_lines = latest_metric_snapshot(companyfacts, curr_date)
    lines = [
        f"# Company Fundamentals for {clean_text(record.get('ticker'))}",
        "",
        header,
        "",
        "## Snapshot",
        "",
        *(snapshot_lines or ["- No snapshot metrics available."]),
        "",
        "## Recent Filings",
        "",
        recent_filings_text(submissions),
    ]
    return "\n".join(lines) + "\n"


def statement_report(
    ticker: str,
    *,
    title: str,
    metrics: tuple[tuple[str, tuple[tuple[str, str], ...], tuple[str, ...]], ...],
    freq: str,
    curr_date: str | None,
    fetcher: JsonFetcher = fetch_sec_json,
) -> str:
    record = resolve_company_record(ticker, fetcher=fetcher)
    companyfacts = load_companyfacts(record, fetcher=fetcher)
    rows = build_statement_rows(companyfacts, metrics, freq=freq, curr_date=curr_date)
    headers = ["Period", *[label for label, _, _ in metrics]]
    lines = [
        f"# {title} for {clean_text(record.get('ticker'))}",
        "",
        company_header(record, companyfacts),
        "",
        f"Frequency: {clean_text(freq) or 'n/a'}",
        "",
    ]
    if rows:
        lines.append(markdown_table(headers, rows))
    else:
        lines.append("No statement rows available for the requested frequency/date cutoff.")
    return "\n".join(lines) + "\n"


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None, *, fetcher: JsonFetcher = fetch_sec_json) -> str:
    return statement_report(
        ticker,
        title="Balance Sheet",
        metrics=BALANCE_SHEET_METRICS,
        freq=clean_text(freq).lower() or "quarterly",
        curr_date=curr_date,
        fetcher=fetcher,
    )


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None, *, fetcher: JsonFetcher = fetch_sec_json) -> str:
    return statement_report(
        ticker,
        title="Cash Flow Statement",
        metrics=CASH_FLOW_METRICS,
        freq=clean_text(freq).lower() or "quarterly",
        curr_date=curr_date,
        fetcher=fetcher,
    )


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None, *, fetcher: JsonFetcher = fetch_sec_json) -> str:
    return statement_report(
        ticker,
        title="Income Statement",
        metrics=INCOME_STATEMENT_METRICS,
        freq=clean_text(freq).lower() or "quarterly",
        curr_date=curr_date,
        fetcher=fetcher,
    )
