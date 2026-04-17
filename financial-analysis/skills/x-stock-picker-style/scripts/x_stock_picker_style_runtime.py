#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import sys


AUTORESEARCH_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "autoresearch-info-index" / "scripts"
if str(AUTORESEARCH_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUTORESEARCH_SCRIPT_DIR))


STATUS_URL_RE = re.compile(r"/status/(?P<status_id>\d+)")
X_PROFILE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/(?P<handle>[A-Za-z0-9_]{1,15})(?:/status/\d+)?/?",
    re.IGNORECASE,
)
LOCAL_TZ = timezone(timedelta(hours=8))
EASTMONEY_SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
PAREN_GROUP_RE = re.compile(r"[（(](?P<body>[^()（）]{2,120})[)）]")
CORE_SINGLE_RE = re.compile(r"(?:核心股|核心标的)[：:\s#]*?(?P<name>[\u4e00-\u9fffA-Za-z]{2,12})")
NAME_WITH_CODE_RE = re.compile(r"(?P<name>[\u4e00-\u9fffA-Za-z]{2,12})\s*[（(](?:\d{6}|[A-Za-z0-9_.-]{2,16})[)）]")

EVENT_CLASSIFICATIONS = {
    "direct_pick",
    "theme_basket",
    "logic_support",
    "quote_only",
    "ignore",
}

DIRECT_CORE_PHRASES = (
    "核心股",
    "核心标的",
)

STRONG_DIRECT_PHRASES = (
    "绝对龙头",
    "弹性最大",
    "翻倍空间",
    "第一目标市值",
    "最受益",
)

LOGIC_SUPPORT_PHRASES = (
    "景气",
    "稼动率",
    "缺口",
    "供不应求",
    "涨价",
    "提价",
    "上调",
    "调价",
    "扩产",
    "投产",
    "订单",
    "中标",
    "预增",
    "高增预期",
    "bottleneck",
    "shortage",
    "utilization",
    "expansion",
    "high boom",
    "boom",
)

CATALYST_KEYWORDS = {
    "price_hike": ("涨价", "提价", "上调", "调价"),
    "capacity_expansion": ("扩产", "投产"),
    "order_flow": ("订单", "中标"),
    "earnings": ("业绩预告", "业绩快报", "预增", "一季报", "年报", "季报"),
    "shortage": ("缺口", "供不应求", "稼动率"),
}

FINANCE_CONTEXT_HINTS = (
    "股票",
    "股价",
    "买入",
    "核心股",
    "核心标的",
    "业绩",
    "净利",
    "订单",
    "中标",
    "扩产",
    "投产",
    "涨价",
    "提价",
    "估值",
    "弹性",
    "景气",
    "供需",
    "产业链",
    "电子布",
    "覆铜板",
    "洁净室",
    "油运",
    "光纤",
    "光缆",
    "PCB",
    "风电",
    "医药",
    "减肥药",
    "创新药",
    "资源",
    "矿",
    "price",
    "stock",
    "shares",
    "ticker",
    "earnings",
    "margin",
    "valuation",
    "order",
    "orders",
    "capacity",
    "shortage",
    "price hike",
    "theme",
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def normalize_x_handle(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("@"):
        text = text[1:]
    if re.fullmatch(r"[A-Za-z0-9_]{1,15}", text):
        return text.lower()
    match = X_PROFILE_URL_RE.search(text)
    if match:
        return clean_text(match.group("handle")).lower()
    return ""


def normalize_subject_tags(value: Any) -> list[str]:
    return clean_string_list(value)


def normalize_subject_record(value: Any) -> dict[str, Any]:
    item = safe_dict(value)
    handle = normalize_x_handle(item.get("handle") or item.get("url"))
    if not handle:
        return {}
    return {
        "handle": handle,
        "display_name": clean_text(item.get("display_name")) or handle,
        "url": clean_text(item.get("url")),
        "notes": clean_text(item.get("notes")),
        "tags": normalize_subject_tags(item.get("tags")),
        "candidate_names": clean_string_list(item.get("candidate_names")),
        "theme_aliases": normalize_theme_aliases(item.get("theme_aliases")),
        "logic_basket_rules": normalize_logic_basket_rules(item.get("logic_basket_rules")),
    }


def subject_registry_map(payload: Any) -> dict[str, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("subjects"), list):
        records = [safe_dict(item) for item in safe_list(payload.get("subjects"))]
    elif isinstance(payload, list):
        records = [safe_dict(item) for item in safe_list(payload)]
    elif isinstance(payload, dict):
        records = [safe_dict(payload)]
    registry: dict[str, dict[str, Any]] = {}
    for record in records:
        normalized = normalize_subject_record(record)
        handle = clean_text(normalized.get("handle"))
        if handle:
            registry[handle] = normalized
    return registry


def normalize_theme_aliases(value: Any) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    if not isinstance(value, dict):
        return aliases
    for key, raw_aliases in value.items():
        normalized_key = clean_text(key)
        normalized_aliases = clean_string_list(raw_aliases)
        if normalized_key and normalized_aliases:
            aliases[normalized_key] = normalized_aliases
    return aliases


def normalize_logic_basket_rules(value: Any) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        basket_name = clean_text(item.get("basket_name") or item.get("rule_name"))
        candidate_names = clean_string_list(item.get("candidate_names"))
        core_candidate_names = clean_string_list(item.get("core_candidate_names"))
        match_any = clean_string_list(item.get("match_any"))
        match_all = clean_string_list(item.get("match_all"))
        if not basket_name or not candidate_names or (not match_any and not match_all):
            continue
        rules.append(
            {
                "rule_name": clean_text(item.get("rule_name")) or basket_name,
                "basket_name": basket_name,
                "sector_or_chain": clean_text(item.get("sector_or_chain") or item.get("sector") or basket_name),
                "candidate_names": candidate_names,
                "core_candidate_names": unique_strings(core_candidate_names) if core_candidate_names else unique_strings(candidate_names),
                "match_any": match_any,
                "match_all": match_all,
                "note": clean_text(item.get("note")),
            }
        )
    return rules


def parse_iso_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def normalize_resolution_map(value: Any) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    if not isinstance(value, dict):
        return mapping
    for name, payload in value.items():
        normalized_name = clean_text(name)
        item = safe_dict(payload)
        ticker = clean_text(item.get("ticker"))
        if not normalized_name or not ticker:
            continue
        mapping[normalized_name] = {
            "ticker": ticker.upper(),
            "code": clean_text(item.get("code")) or ticker.split(".", 1)[0],
            "resolved_name": clean_text(item.get("resolved_name")) or normalized_name,
            "board": clean_text(item.get("board")) or "",
        }
    return mapping


def normalize_history_map(value: Any) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(value, dict):
        return mapping
    for ticker, rows in value.items():
        normalized_ticker = clean_text(ticker).upper()
        normalized_rows: list[dict[str, Any]] = []
        for row in safe_list(rows):
            if not isinstance(row, dict):
                continue
            trade_date = clean_text(row.get("trade_date") or row.get("date"))
            if not trade_date:
                continue
            normalized_rows.append(
                {
                    "trade_date": trade_date[:10],
                    "open": float(row.get("open") or 0.0),
                    "high": float(row.get("high") or 0.0),
                    "low": float(row.get("low") or 0.0),
                    "close": float(row.get("close") or 0.0),
                }
            )
        if normalized_ticker and normalized_rows:
            mapping[normalized_ticker] = normalized_rows
    return mapping


def fetch_json(url: str, *, referer: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
            "Accept": "application/json,text/plain,*/*",
        },
        method="GET",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def board_from_code(code: str) -> str:
    if code.startswith("688"):
        return "STAR"
    if code.startswith(("300", "301")):
        return "ChiNext"
    if code.startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
        return "Main"
    return "Other"


def quote_id_to_ticker(quote_id: str, code: str) -> str:
    cleaned = clean_text(quote_id)
    if cleaned.startswith("1."):
        return f"{code}.SS"
    return f"{code}.SZ"


def resolve_name_live(stock_name: str) -> dict[str, Any]:
    payload = fetch_json(
        EASTMONEY_SUGGEST_URL
        + "?"
        + urlencode({"input": stock_name, "type": "14", "token": "D43BF722C8E33BDC906FB84D85E326E8"}),
        referer="https://quote.eastmoney.com/",
    )
    data = safe_list(safe_dict(safe_dict(payload).get("QuotationCodeTable")).get("Data"))
    normalized_target = clean_text(stock_name)
    candidates: list[dict[str, Any]] = []
    for item in data:
        code = clean_text(item.get("Code") or item.get("UnifiedCode"))
        name = clean_text(item.get("Name"))
        if not code or not name or not re.fullmatch(r"\d{6}", code):
            continue
        candidates.append(
            {
                "ticker": quote_id_to_ticker(clean_text(item.get("QuoteID")), code),
                "code": code,
                "resolved_name": name,
                "board": board_from_code(code),
            }
        )
    if not candidates:
        raise KeyError(f"Could not resolve stock name `{stock_name}`.")
    for candidate in candidates:
        if clean_text(candidate.get("resolved_name")) == normalized_target:
            return candidate
    return candidates[0]


def resolve_name_for_request(stock_name: str, request: dict[str, Any], cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    normalized_name = clean_text(stock_name)
    if normalized_name in cache:
        return cache[normalized_name]
    explicit = safe_dict(request.get("ticker_resolution_by_name")).get(normalized_name)
    if explicit:
        cache[normalized_name] = safe_dict(explicit)
        return cache[normalized_name]
    if not request.get("enable_live_resolution"):
        return None
    try:
        resolved = resolve_name_live(normalized_name)
    except Exception:
        return None
    cache[normalized_name] = resolved
    return resolved


def tencent_symbol(ticker: str) -> str:
    normalized = clean_text(ticker).upper().replace(".SH", ".SS")
    digits, suffix = normalized.split(".", 1)
    return ("sh" if suffix == "SS" else "sz") + digits


def fetch_tencent_history_rows(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    symbol = tencent_symbol(ticker)
    payload = fetch_json(
        TENCENT_KLINE_URL + "?" + urlencode({"param": f"{symbol},day,{start_date},{end_date},400,qfq"}),
        referer="https://gu.qq.com/",
    )
    data = safe_dict(safe_dict(payload.get("data")).get(symbol))
    raw_rows = safe_list(data.get("qfqday")) or safe_list(data.get("day"))
    rows: list[dict[str, Any]] = []
    for item in raw_rows:
        if not isinstance(item, list) or len(item) < 5:
            continue
        rows.append(
            {
                "trade_date": clean_text(item[0])[:10],
                "open": float(item[1]),
                "close": float(item[2]),
                "high": float(item[3]),
                "low": float(item[4]),
            }
        )
    return rows


def history_rows_for_ticker(ticker: str, request: dict[str, Any], start_date: str, end_date: str) -> tuple[list[dict[str, Any]], str]:
    normalized_ticker = clean_text(ticker).upper().replace(".SH", ".SS")
    history_by_ticker = safe_dict(request.get("history_by_ticker"))
    if safe_list(history_by_ticker.get(normalized_ticker)):
        return safe_list(history_by_ticker.get(normalized_ticker)), "fixture"
    if request.get("enable_live_history"):
        rows = fetch_tencent_history_rows(normalized_ticker, start_date, end_date)
        if rows:
            return rows, "tencent_qfq"
    return [], ""


def choose_entry_index(rows: list[dict[str, Any]], published_at: str) -> int:
    published_dt = parse_datetime(published_at)
    if published_dt is None:
        raise ValueError("Published datetime is missing.")
    local_dt = published_dt.astimezone(LOCAL_TZ)
    local_date = local_dt.date()
    after_close = local_dt.time() > time(15, 0)
    for index, row in enumerate(rows):
        trade_date = parse_iso_date(row.get("trade_date"))
        if trade_date is None:
            continue
        if trade_date < local_date:
            continue
        if trade_date == local_date and after_close:
            continue
        return index
    raise ValueError("No entry bar found after published datetime.")


def compute_return_pct(entry_close: float, latest_close: float) -> float:
    if not entry_close:
        return 0.0
    return (latest_close / entry_close - 1.0) * 100.0


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def isoformat_or_blank(value: datetime | None) -> str:
    return value.astimezone(UTC).isoformat() if value else ""


def short_excerpt(value: Any, limit: int = 180) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_path(value: Any) -> Path | None:
    text = clean_text(value)
    if not text:
        return None
    return Path(text).expanduser().resolve()


def run_x_index_request(payload: dict[str, Any]) -> dict[str, Any]:
    from x_index_runtime import run_x_index  # lazy import to keep this workflow fixture-friendly

    return run_x_index(payload)


def status_id_from_url(url: str) -> str:
    match = STATUS_URL_RE.search(clean_text(url))
    return match.group("status_id") if match else ""


def normalize_thread_posts(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        text_raw = clean_text(item.get("post_text_raw"))
        summary_fallback = clean_text(item.get("post_summary")) or clean_text(item.get("combined_summary"))
        text = text_raw or summary_fallback
        text_kind = "raw_post_text" if text_raw else "summary_fallback" if summary_fallback else "missing"
        normalized.append(
            {
                "status_url": clean_text(item.get("post_url") or item.get("status_url")),
                "status_id": status_id_from_url(clean_text(item.get("post_url") or item.get("status_url"))),
                "published_at": isoformat_or_blank(parse_datetime(item.get("posted_at") or item.get("published_at"))),
                "text": text,
                "text_kind": text_kind,
            }
        )
    return normalized


def clean_artifact_manifest(value: Any) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        role = clean_text(item.get("role"))
        path = clean_text(item.get("path"))
        source_url = clean_text(item.get("source_url"))
        media_type = clean_text(item.get("media_type"))
        if not any([role, path, source_url, media_type]):
            continue
        cleaned.append(
            {
                "role": role,
                "path": path,
                "source_url": source_url,
                "media_type": media_type,
                "summary": short_excerpt(item.get("summary")),
            }
        )
    return cleaned


def normalize_x_index_post(post: dict[str, Any]) -> dict[str, Any]:
    status_url = clean_text(post.get("post_url") or post.get("status_url"))
    direct_text_raw = clean_text(post.get("post_text_raw"))
    direct_text_fallback = clean_text(post.get("post_summary")) or clean_text(post.get("combined_summary"))
    direct_text = direct_text_raw or direct_text_fallback
    direct_text_kind = "raw_post_text" if direct_text_raw else "summary_fallback" if direct_text_fallback else "missing"
    same_author_context = normalize_thread_posts(post.get("thread_posts"))
    operator_review_reasons: list[str] = []
    if not status_id_from_url(status_url):
        operator_review_reasons.append("missing_status_id")
    if direct_text_kind != "raw_post_text":
        operator_review_reasons.append("missing_raw_post_text")
    if not direct_text:
        operator_review_reasons.append("missing_direct_text")

    return {
        "source_kind": "x_index_result",
        "source_id": f"x-{status_id_from_url(status_url) or 'unknown'}",
        "status_id": status_id_from_url(status_url),
        "status_url": status_url,
        "author_handle": clean_text(post.get("author_handle")),
        "author_display_name": clean_text(post.get("author_display_name")),
        "published_at": isoformat_or_blank(parse_datetime(post.get("posted_at") or post.get("published_at"))),
        "collected_at": isoformat_or_blank(parse_datetime(post.get("collected_at"))),
        "direct_text": direct_text,
        "direct_text_kind": direct_text_kind,
        "quoted_text": "",
        "same_author_context": same_author_context,
        "post_summary": clean_text(post.get("post_summary")),
        "media_summary": clean_text(post.get("media_summary")),
        "combined_summary": clean_text(post.get("combined_summary")),
        "extraction_method": f"x_index:{clean_text(post.get('post_text_source') or post.get('access_mode') or 'unknown')}",
        "access_mode": clean_text(post.get("access_mode")),
        "session_source": clean_text(post.get("session_source")),
        "session_status": clean_text(post.get("session_status")),
        "session_health": clean_text(post.get("session_health")),
        "artifact_manifest": clean_artifact_manifest(post.get("artifact_manifest")),
        "needs_operator_review": bool(operator_review_reasons),
        "operator_review_reasons": operator_review_reasons,
    }


def normalize_timeline_article(article: dict[str, Any], page_meta: dict[str, Any]) -> dict[str, Any]:
    status_url = clean_text(article.get("status_url"))
    direct_text_raw = clean_text(article.get("text"))
    raw_fallback = clean_text(article.get("raw_text"))
    direct_text = direct_text_raw or raw_fallback
    direct_text_kind = "timeline_text" if direct_text_raw else "timeline_raw_fallback" if raw_fallback else "missing"
    operator_review_reasons: list[str] = []
    if not status_id_from_url(status_url):
        operator_review_reasons.append("missing_status_id")
    if not direct_text:
        operator_review_reasons.append("missing_direct_text")

    return {
        "source_kind": "timeline_scan",
        "source_id": f"x-{status_id_from_url(status_url) or 'unknown'}",
        "status_id": status_id_from_url(status_url),
        "status_url": status_url,
        "author_handle": clean_text(article.get("author_handle")),
        "author_display_name": clean_text(article.get("author_display_name")) or clean_text(page_meta.get("handle")),
        "published_at": isoformat_or_blank(parse_datetime(article.get("datetime"))),
        "collected_at": isoformat_or_blank(parse_datetime(page_meta.get("scanned_at"))),
        "direct_text": direct_text,
        "direct_text_kind": direct_text_kind,
        "quoted_text": clean_text(article.get("quoted_text")),
        "same_author_context": [],
        "post_summary": "",
        "media_summary": "",
        "combined_summary": "",
        "extraction_method": f"timeline_scan:{clean_text(page_meta.get('page') or 'unknown')}",
        "access_mode": "browser_session",
        "session_source": "remote_debugging",
        "session_status": "captured",
        "session_health": "unknown",
        "artifact_manifest": [],
        "needs_operator_review": bool(operator_review_reasons),
        "operator_review_reasons": operator_review_reasons,
    }


def normalize_existing_source_board_item(item: dict[str, Any]) -> dict[str, Any]:
    status_url = clean_text(item.get("status_url"))
    return {
        "source_kind": clean_text(item.get("source_kind") or "source_board"),
        "source_id": clean_text(item.get("source_id") or f"x-{status_id_from_url(status_url) or 'unknown'}"),
        "status_id": clean_text(item.get("status_id") or status_id_from_url(status_url)),
        "status_url": status_url,
        "author_handle": clean_text(item.get("author_handle")),
        "author_display_name": clean_text(item.get("author_display_name")),
        "published_at": clean_text(item.get("published_at")),
        "collected_at": clean_text(item.get("collected_at")),
        "direct_text": clean_text(item.get("direct_text")),
        "direct_text_kind": clean_text(item.get("direct_text_kind") or "unknown"),
        "quoted_text": clean_text(item.get("quoted_text")),
        "same_author_context": deepcopy(safe_list(item.get("same_author_context"))),
        "post_summary": clean_text(item.get("post_summary")),
        "media_summary": clean_text(item.get("media_summary")),
        "combined_summary": clean_text(item.get("combined_summary")),
        "extraction_method": clean_text(item.get("extraction_method")),
        "access_mode": clean_text(item.get("access_mode")),
        "session_source": clean_text(item.get("session_source")),
        "session_status": clean_text(item.get("session_status")),
        "session_health": clean_text(item.get("session_health")),
        "artifact_manifest": clean_artifact_manifest(item.get("artifact_manifest")),
        "needs_operator_review": bool(item.get("needs_operator_review")),
        "operator_review_reasons": clean_string_list(item.get("operator_review_reasons")),
    }


def item_richness_score(item: dict[str, Any]) -> tuple[int, int, int]:
    text_kind = clean_text(item.get("direct_text_kind"))
    direct_score = 3 if text_kind in {"raw_post_text", "timeline_text"} else 2 if clean_text(item.get("direct_text")) else 0
    context_score = len(safe_list(item.get("same_author_context")))
    extra_score = len(clean_text(item.get("quoted_text"))) + len(clean_text(item.get("combined_summary"))) + len(safe_list(item.get("artifact_manifest"))) * 10
    return (direct_score, context_score, extra_score)


def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            parse_datetime(item.get("published_at")) or datetime.min.replace(tzinfo=UTC),
            item_richness_score(item),
        ),
        reverse=True,
    )


def dedupe_source_board(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in sort_items(items):
        key = clean_text(item.get("status_id")) or clean_text(item.get("status_url")) or clean_text(item.get("source_id"))
        if not key:
            continue
        if key not in kept:
            kept[key] = item
            order.append(key)
            continue
        if item_richness_score(item) > item_richness_score(kept[key]):
            kept[key] = item
    return [kept[key] for key in order]


def build_source_items_from_payload(payload: dict[str, Any], payload_kind: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if safe_list(payload.get("x_posts")):
        for post in safe_list(payload.get("x_posts")):
            if isinstance(post, dict):
                items.append(normalize_x_index_post(post))
        return items
    if payload_kind in {"x_index_request", "x_index_result"} and (
        "x_posts" in payload or payload.get("workflow_kind") == "x_index"
    ):
        return []
    if safe_list(payload.get("source_board")):
        for item in safe_list(payload.get("source_board")):
            if isinstance(item, dict):
                items.append(normalize_existing_source_board_item(item))
        return items
    if safe_list(payload.get("pages")):
        scanned_at = clean_text(payload.get("scanned_at"))
        for page in safe_list(payload.get("pages")):
            if not isinstance(page, dict):
                continue
            page_meta = {
                "page": clean_text(page.get("page")),
                "handle": clean_text(page.get("handle")),
                "scanned_at": scanned_at,
            }
            for article in safe_list(page.get("articles")):
                if isinstance(article, dict):
                    items.append(normalize_timeline_article(article, page_meta))
        return items
    raise ValueError(f"Unsupported source payload shape for `{payload_kind}`.")


def normalize_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    subject_raw = safe_dict(raw_request.get("subject"))
    subject_registry_path = normalize_path(raw_request.get("subject_registry_path"))
    subject_registry_payload: Any = deepcopy(raw_request.get("subject_registry")) if raw_request.get("subject_registry") is not None else None
    if subject_registry_payload is None and subject_registry_path is not None:
        subject_registry_payload = load_json(subject_registry_path)
    registry = subject_registry_map(subject_registry_payload) if subject_registry_payload is not None else {}

    subject_url = clean_text(subject_raw.get("url") or raw_request.get("subject_url") or raw_request.get("url"))
    handle = normalize_x_handle(subject_raw.get("handle") or raw_request.get("handle") or subject_url)
    if not handle:
        raise ValueError("Request must include `subject.handle`, `handle`, `subject.url`, `subject_url`, or another handle-like X profile reference.")

    registry_subject = safe_dict(registry.get(handle))
    display_name = clean_text(
        subject_raw.get("display_name")
        or raw_request.get("display_name")
        or registry_subject.get("display_name")
        or handle
    )
    merged_tags = unique_strings(
        normalize_subject_tags(registry_subject.get("tags"))
        + normalize_subject_tags(subject_raw.get("tags"))
        + normalize_subject_tags(raw_request.get("subject_tags"))
    )
    subject_notes = clean_text(subject_raw.get("notes") or raw_request.get("subject_notes") or registry_subject.get("notes"))
    normalized_subject_url = clean_text(subject_url or registry_subject.get("url"))

    payload_specs: list[dict[str, Any]] = []
    x_index_request_path = normalize_path(raw_request.get("x_index_request_path"))
    if x_index_request_path is not None:
        payload_specs.append({"kind": "x_index_request", "path": x_index_request_path})
    x_index_result_path = normalize_path(raw_request.get("x_index_result_path"))
    if x_index_result_path is not None:
        payload_specs.append({"kind": "x_index_result", "path": x_index_result_path})
    timeline_scan_path = normalize_path(raw_request.get("timeline_scan_path"))
    if timeline_scan_path is not None:
        payload_specs.append({"kind": "timeline_scan", "path": timeline_scan_path})
    if isinstance(raw_request.get("x_index_request"), dict):
        payload_specs.append({"kind": "x_index_request", "payload": deepcopy(raw_request["x_index_request"])})
    if isinstance(raw_request.get("x_index_result"), dict):
        payload_specs.append({"kind": "x_index_result", "payload": deepcopy(raw_request["x_index_result"])})
    if isinstance(raw_request.get("timeline_scan"), dict):
        payload_specs.append({"kind": "timeline_scan", "payload": deepcopy(raw_request["timeline_scan"])})
    if isinstance(raw_request.get("source_board_seed"), dict):
        payload_specs.append({"kind": "source_board_seed", "payload": deepcopy(raw_request["source_board_seed"])})

    if not payload_specs:
        raise ValueError(
            "Request must include one of `x_index_request_path`, `x_index_result_path`, `timeline_scan_path`, inline `x_index_request`, inline `x_index_result`, inline `timeline_scan`, or `source_board_seed`."
        )

    analysis_time = parse_datetime(raw_request.get("analysis_time")) or now_utc()
    analysis_date = parse_iso_date(raw_request.get("analysis_date")) or analysis_time.astimezone(LOCAL_TZ).date()
    source_start_date = parse_iso_date(raw_request.get("source_start_date"))
    merged_candidate_names = unique_strings(
        clean_string_list(registry_subject.get("candidate_names"))
        + clean_string_list(raw_request.get("candidate_names"))
    )
    merged_theme_aliases = merge_theme_alias_maps(
        safe_dict(registry_subject.get("theme_aliases")),
        safe_dict(raw_request.get("theme_aliases")),
    )
    merged_logic_basket_rules = merge_logic_basket_rules(
        registry_subject.get("logic_basket_rules"),
        raw_request.get("logic_basket_rules"),
    )
    return {
        "analysis_time": analysis_time,
        "analysis_date": analysis_date.isoformat(),
        "source_start_date": source_start_date.isoformat() if source_start_date else "",
        "max_source_items": max(1, int(raw_request.get("max_source_items") or raw_request.get("limit") or 80)),
        "require_matching_handle": bool(raw_request.get("require_matching_handle", True)),
        "candidate_names": merged_candidate_names,
        "theme_aliases": merged_theme_aliases,
        "logic_basket_rules": merged_logic_basket_rules,
        "ticker_resolution_by_name": normalize_resolution_map(raw_request.get("ticker_resolution_by_name")),
        "history_by_ticker": normalize_history_map(raw_request.get("history_by_ticker")),
        "score_mode": clean_text(raw_request.get("score_mode") or "off"),
        "enable_live_resolution": bool(raw_request.get("enable_live_resolution", False)),
        "enable_live_history": bool(raw_request.get("enable_live_history", False)),
        "subject": {
            "platform": clean_text(subject_raw.get("platform") or raw_request.get("platform") or "x").lower() or "x",
            "handle": handle.lower(),
            "display_name": display_name or handle.lower(),
            "url": normalized_subject_url,
            "notes": subject_notes,
            "tags": merged_tags,
        },
        "payload_specs": payload_specs,
    }


def source_summary(source_board: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_sources": len(source_board),
        "operator_review_count": sum(1 for item in source_board if item.get("needs_operator_review")),
        "same_author_context_count": sum(1 for item in source_board if safe_list(item.get("same_author_context"))),
        "quoted_text_count": sum(1 for item in source_board if clean_text(item.get("quoted_text"))),
        "source_kinds": sorted({clean_text(item.get("source_kind")) for item in source_board if clean_text(item.get("source_kind"))}),
    }


def token_looks_like_stock_name(token: str) -> bool:
    text = clean_text(token).strip("•-:：")
    if not text or len(text) < 2 or len(text) > 12:
        return False
    if any(marker in text for marker in ("核心股", "核心标的", "绝对龙头", "弹性最大", "景气", "高增", "链", "出海", "国产")):
        return False
    if text.isdigit():
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def extract_parenthetical_names(text: str) -> list[str]:
    names: list[str] = []
    for match in PAREN_GROUP_RE.finditer(text):
        body = clean_text(match.group("body"))
        if not body:
            continue
        for raw_token in re.split(r"[、,，/／|｜\s]+", body):
            token = clean_text(raw_token)
            if token_looks_like_stock_name(token):
                names.append(token)
    return unique_strings(names)


def extract_stock_names(text: str, candidate_names: list[str]) -> list[str]:
    normalized_candidates = unique_strings(candidate_names)
    names: list[str] = []
    for candidate in sorted(normalized_candidates, key=len, reverse=True):
        if candidate and candidate in text:
            names.append(candidate)
    if normalized_candidates:
        return unique_strings(names)
    for match in NAME_WITH_CODE_RE.finditer(text):
        names.append(match.group("name"))
    for match in CORE_SINGLE_RE.finditer(text):
        names.append(match.group("name"))
    names.extend(extract_parenthetical_names(text))
    return unique_strings([name for name in names if token_looks_like_stock_name(name) or name in normalized_candidates])


def classify_strength(text: str, classification: str) -> str:
    has_core = any(phrase in text for phrase in DIRECT_CORE_PHRASES)
    has_strong = any(phrase in text for phrase in STRONG_DIRECT_PHRASES)
    if classification == "direct_pick":
        if has_strong:
            return "strong_direct"
        if has_core:
            return "strict_core"
        return "named_positive"
    if classification == "theme_basket":
        if has_strong or has_core:
            return "theme_basket_high_conviction"
        return "theme_basket"
    if classification == "logic_support":
        return "logic_support"
    if classification == "quote_only":
        return "quote_only"
    return "ignore"


def infer_catalyst_type(text: str) -> str:
    for catalyst_type, keywords in CATALYST_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return catalyst_type
    return ""


def infer_sector_or_chain(text: str, theme_aliases: dict[str, list[str]]) -> str:
    for theme_name, aliases in theme_aliases.items():
        if any(alias in text for alias in aliases):
            return theme_name
    built_in_aliases = {
        "electronic_cloth": ["电子布", "电子纱", "覆铜板", "CCL", "织布机"],
        "pcb_equipment": ["PCB设备", "PCB"],
        "optical_interconnect": ["光模块", "光互联", "光通信", "光芯片", "EML", "DFB", "CPO", "OCS", "DCI", "硅光子", "光器件", "SiPhIA", "LUMENTUM"],
        "advanced_pcb_flexible": ["FOLP", "FCCL", "PI膜", "TPI树脂", "柔性PCB", "电路板"],
        "satellite_chain": ["卫星", "SpaceX", "航天级"],
        "cleanroom": ["洁净室", "洁净"],
        "oil_shipping": ["油运", "航运"],
        "fiber_cable": ["光纤光缆", "海缆", "光缆"],
        "chemicals": ["树脂", "聚酯", "烯烃链", "甲醇", "尿素", "溴素"],
        "pharma": ["减肥药", "创新药"],
        "wind_power": ["风电", "轴承"],
        "cloud_ai": ["OpenClaw", "云计算", "算力"],
    }
    for theme_name, aliases in built_in_aliases.items():
        if any(alias in text for alias in aliases):
            return theme_name
    return ""


def infer_holding_horizon(classification: str, catalyst_type: str) -> str:
    if catalyst_type == "earnings":
        return "days_to_earnings_window"
    if catalyst_type in {"price_hike", "shortage", "order_flow", "capacity_expansion"}:
        return "swing_1_4w"
    if classification == "theme_basket":
        return "swing_1_4w"
    if classification == "direct_pick":
        return "swing_1_3w"
    if classification == "logic_support":
        return "watch_only"
    return ""


def has_finance_context(text: str, candidate_names: list[str], theme_aliases: dict[str, list[str]]) -> bool:
    normalized_text = clean_text(text)
    if not normalized_text:
        return False
    if any(candidate and candidate in normalized_text for candidate in candidate_names):
        return True
    if any(hint in normalized_text for hint in FINANCE_CONTEXT_HINTS):
        return True
    if infer_catalyst_type(normalized_text):
        return True
    if infer_sector_or_chain(normalized_text, theme_aliases):
        return True
    if any(phrase in normalized_text for phrase in LOGIC_SUPPORT_PHRASES):
        return True
    return False


def infer_logic_basket_hint(text: str, request: dict[str, Any]) -> dict[str, Any]:
    normalized_text = clean_text(text)
    if not normalized_text:
        return {}
    min_match_score = safe_dict(request).get("min_logic_basket_match_score")
    if min_match_score is None:
        min_match_score = 3
    else:
        min_match_score = int(min_match_score)
    best_rule: dict[str, Any] = {}
    best_score = -1
    best_terms: list[str] = []
    for rule in safe_list(request.get("logic_basket_rules")):
        item = safe_dict(rule)
        match_any = clean_string_list(item.get("match_any"))
        match_all = clean_string_list(item.get("match_all"))
        any_hits = [term for term in match_any if term in normalized_text]
        all_hits = [term for term in match_all if term in normalized_text]
        if match_all and len(all_hits) != len(match_all):
            continue
        if match_any and not any_hits:
            continue
        score = len(all_hits) * 3 + len(any_hits)
        if score > best_score:
            best_rule = item
            best_score = score
            best_terms = unique_strings(all_hits + any_hits)
    if not best_rule:
        return {}
    # Require a minimum match score to prevent single generic keyword
    # matches (e.g. "AI") from triggering an entire advisory basket.
    if best_score < min_match_score:
        return {}
    return {
        "basket_name": clean_text(best_rule.get("basket_name")),
        "sector_or_chain": clean_text(best_rule.get("sector_or_chain")),
        "candidate_names": clean_string_list(best_rule.get("candidate_names")),
        "core_candidate_names": clean_string_list(best_rule.get("core_candidate_names")),
        "note": clean_text(best_rule.get("note")),
        "matched_terms": best_terms,
        "match_score": best_score,
        "confidence": "advisory",
    }


def classify_source_item(item: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    text = clean_text(item.get("direct_text"))
    quoted_text = clean_text(item.get("quoted_text"))
    candidate_names = clean_string_list(request.get("candidate_names"))
    theme_aliases = safe_dict(request.get("theme_aliases"))
    names = extract_stock_names(text, candidate_names)
    quoted_names = extract_stock_names(quoted_text, candidate_names)
    operator_review_reasons = clean_string_list(item.get("operator_review_reasons"))
    support_hit = any(phrase in text for phrase in LOGIC_SUPPORT_PHRASES)
    catalyst_type = infer_catalyst_type(text)
    text_has_finance_context = has_finance_context(text, candidate_names, theme_aliases)
    quoted_has_finance_context = has_finance_context(quoted_text, candidate_names, theme_aliases)

    classification = "ignore"
    if not text and quoted_text and (quoted_names or quoted_has_finance_context):
        classification = "quote_only"
    elif names and text_has_finance_context:
        classification = "theme_basket" if len(names) > 1 else "direct_pick"
    elif text_has_finance_context and (support_hit or catalyst_type or infer_sector_or_chain(text, theme_aliases) or quoted_text):
        classification = "logic_support"

    if classification == "logic_support" and not names:
        operator_review_reasons.append("no_extracted_stock_names")
    if classification == "quote_only":
        operator_review_reasons.append("quote_only_not_counted_as_new_pick")
    logic_basket_hint = infer_logic_basket_hint(text or quoted_text, request) if classification in {"logic_support", "quote_only"} and not names else {}
    if logic_basket_hint:
        operator_review_reasons.append("advisory_logic_basket_hint")

    return {
        "event_id": f"rec-{clean_text(item.get('status_id')) or clean_text(item.get('source_id')) or 'unknown'}",
        "status_id": clean_text(item.get("status_id")),
        "status_url": clean_text(item.get("status_url")),
        "published_at": clean_text(item.get("published_at")),
        "classification": classification,
        "strength": classify_strength(text, classification),
        "names": names,
        "resolved_tickers": [],
        "sector_or_chain": infer_sector_or_chain(text, theme_aliases),
        "thesis_excerpt": short_excerpt(text or quoted_text, limit=220),
        "catalyst_type": catalyst_type,
        "holding_horizon_guess": infer_holding_horizon(classification, catalyst_type),
        "ambiguity_flags": operator_review_reasons,
        "operator_notes": "",
        "needs_operator_review": bool(operator_review_reasons),
        "suggested_basket_name": clean_text(logic_basket_hint.get("basket_name")),
        "suggested_basket_sector": clean_text(logic_basket_hint.get("sector_or_chain")),
        "suggested_basket_candidates": clean_string_list(logic_basket_hint.get("candidate_names")),
        "suggested_basket_core_candidates": clean_string_list(logic_basket_hint.get("core_candidate_names")),
        "suggested_basket_note": clean_text(logic_basket_hint.get("note")),
        "suggested_basket_matched_terms": clean_string_list(logic_basket_hint.get("matched_terms")),
        "suggested_basket_confidence": clean_text(logic_basket_hint.get("confidence")),
    }


def build_recommendation_ledger(source_board: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for item in source_board:
        event = classify_source_item(item, request)
        if clean_text(event.get("classification")) == "ignore":
            continue
        ledger.append(event)
    return ledger


def recommendation_summary(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    by_classification: dict[str, int] = {}
    by_strength: dict[str, int] = {}
    for event in ledger:
        classification = clean_text(event.get("classification"))
        strength = clean_text(event.get("strength"))
        if classification:
            by_classification[classification] = by_classification.get(classification, 0) + 1
        if strength:
            by_strength[strength] = by_strength.get(strength, 0) + 1
    return {
        "total_events": len(ledger),
        "operator_review_count": sum(1 for event in ledger if event.get("needs_operator_review")),
        "by_classification": by_classification,
        "by_strength": by_strength,
    }


def score_event(event: dict[str, Any], request: dict[str, Any], resolution_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if clean_text(request.get("score_mode")) == "off":
        return event
    names = clean_string_list(event.get("names"))
    if not names:
        return event
    start_date = min(parse_iso_date(clean_text(event.get("published_at"))) or parse_iso_date(request.get("analysis_date")) or date.today(), parse_iso_date(request.get("analysis_date")) or date.today())
    start_date_text = (start_date - timedelta(days=10)).isoformat()
    end_date_text = clean_text(request.get("analysis_date"))
    scored_names: list[dict[str, Any]] = []
    ambiguity_flags = clean_string_list(event.get("ambiguity_flags"))
    resolved_tickers: list[str] = []
    history_source_mix: dict[str, int] = {}

    for name in names:
        resolved = resolve_name_for_request(name, request, resolution_cache)
        if resolved is None:
            ambiguity_flags.append(f"unresolved_ticker:{name}")
            continue
        ticker = clean_text(resolved.get("ticker")).upper().replace(".SH", ".SS")
        rows, history_source = history_rows_for_ticker(ticker, request, start_date_text, end_date_text)
        if not rows:
            ambiguity_flags.append(f"missing_history:{ticker}")
            continue
        try:
            entry_index = choose_entry_index(rows, clean_text(event.get("published_at")))
        except Exception:
            ambiguity_flags.append(f"missing_entry_bar:{ticker}")
            continue
        entry_row = rows[entry_index]
        latest_row = rows[-1]
        held_trade_days = len(rows) - entry_index
        entry_close = float(entry_row.get("close") or 0.0)
        latest_close = float(latest_row.get("close") or 0.0)
        too_early = held_trade_days <= 1
        resolved_tickers.append(ticker)
        if history_source:
            history_source_mix[history_source] = history_source_mix.get(history_source, 0) + 1
        scored_names.append(
            {
                "name": name,
                "ticker": ticker,
                "resolved_name": clean_text(resolved.get("resolved_name")) or name,
                "board": clean_text(resolved.get("board")),
                "entry_trade_date": clean_text(entry_row.get("trade_date")),
                "entry_close": entry_close,
                "latest_trade_date": clean_text(latest_row.get("trade_date")),
                "latest_close": latest_close,
                "held_trade_days": held_trade_days,
                "return_pct": compute_return_pct(entry_close, latest_close),
                "too_early_to_score": too_early,
                "history_source": history_source,
            }
        )

    scoreable = [item for item in scored_names if not item.get("too_early_to_score")]
    avg_return = sum(float(item.get("return_pct") or 0.0) for item in scoreable) / len(scoreable) if scoreable else 0.0
    win_rate = sum(1 for item in scoreable if float(item.get("return_pct") or 0.0) > 0) / len(scoreable) * 100.0 if scoreable else 0.0
    updated = deepcopy(event)
    updated["resolved_tickers"] = resolved_tickers
    updated["scored_names"] = scored_names
    updated["ambiguity_flags"] = unique_strings(ambiguity_flags)
    updated["needs_operator_review"] = bool(updated["ambiguity_flags"])
    updated["score_summary"] = {
        "name_count": len(scored_names),
        "scoreable_name_count": len(scoreable),
        "too_early_count": sum(1 for item in scored_names if item.get("too_early_to_score")),
        "avg_return": avg_return,
        "win_rate": win_rate,
        "history_source_mix": history_source_mix,
    }
    return updated


def score_recommendation_ledger(ledger: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    if clean_text(request.get("score_mode")) == "off":
        return ledger
    resolution_cache: dict[str, dict[str, Any]] = {}
    return [score_event(event, request, resolution_cache) for event in ledger]


def summarize_score_bucket(items: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(item.get("return_pct") or 0.0) for item in items if not item.get("too_early_to_score")]
    if not returns:
        return {"count": 0, "win_rate": 0.0, "avg_return": 0.0}
    return {
        "count": len(returns),
        "win_rate": sum(1 for value in returns if value > 0) / len(returns) * 100.0,
        "avg_return": sum(returns) / len(returns),
    }


def score_summary_from_ledger(ledger: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    if clean_text(request.get("score_mode")) == "off":
        return {}
    score_rows: list[dict[str, Any]] = []
    by_classification: dict[str, list[dict[str, Any]]] = {}
    by_sector: dict[str, list[dict[str, Any]]] = {}
    by_catalyst: dict[str, list[dict[str, Any]]] = {}
    history_source_mix: dict[str, int] = {}
    for event in ledger:
        classification = clean_text(event.get("classification"))
        sector = clean_text(event.get("sector_or_chain"))
        catalyst = clean_text(event.get("catalyst_type"))
        for item in safe_list(event.get("scored_names")):
            scored = dict(item)
            scored["classification"] = classification
            scored["sector_or_chain"] = sector
            scored["catalyst_type"] = catalyst
            score_rows.append(scored)
            if not scored.get("too_early_to_score"):
                by_classification.setdefault(classification, []).append(scored)
                if sector:
                    by_sector.setdefault(sector, []).append(scored)
                if catalyst:
                    by_catalyst.setdefault(catalyst, []).append(scored)
            history_source = clean_text(scored.get("history_source"))
            if history_source:
                history_source_mix[history_source] = history_source_mix.get(history_source, 0) + 1
    scoreable = [item for item in score_rows if not item.get("too_early_to_score")]
    return {
        "score_mode": clean_text(request.get("score_mode")),
        "analysis_date": clean_text(request.get("analysis_date")),
        "scored_name_count": len(score_rows),
        "scoreable_name_count": len(scoreable),
        "too_early_count": sum(1 for item in score_rows if item.get("too_early_to_score")),
        "overall": summarize_score_bucket(score_rows),
        "by_classification": {key: summarize_score_bucket(items) for key, items in by_classification.items() if key},
        "by_sector": {key: summarize_score_bucket(items) for key, items in by_sector.items() if key},
        "by_catalyst_type": {key: summarize_score_bucket(items) for key, items in by_catalyst.items() if key},
        "history_source_mix": history_source_mix,
    }


def collect_event_support_map(
    ledger: list[dict[str, Any]],
    value_getter: Any,
    *,
    allow_empty: bool = False,
) -> dict[str, list[str]]:
    support_map: dict[str, list[str]] = {}
    for event in ledger:
        raw_values = value_getter(event)
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        event_id = clean_text(event.get("event_id"))
        for value in values:
            key = clean_text(value)
            if not key and not allow_empty:
                continue
            support_map.setdefault(key, [])
            if event_id and event_id not in support_map[key]:
                support_map[key].append(event_id)
    return support_map


def ranked_pattern_entries(
    support_map: dict[str, list[str]],
    *,
    min_count: int = 1,
    limit: int = 5,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for value, event_ids in support_map.items():
        if not value or len(event_ids) < min_count:
            continue
        entries.append(
            {
                "value": value,
                "count": len(event_ids),
                "event_ids": event_ids[:8],
            }
        )
    entries.sort(key=lambda item: (-int(item.get("count") or 0), clean_text(item.get("value"))))
    return entries[:limit]


def build_advisory_basket_entries(mapped_logic_events: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in mapped_logic_events:
        basket_name = clean_text(event.get("suggested_basket_name"))
        if not basket_name:
            continue
        bucket = grouped.setdefault(
            basket_name,
            {
                "value": basket_name,
                "count": 0,
                "event_ids": [],
                "candidate_names": [],
                "core_candidate_names": [],
                "sector_or_chain": clean_text(event.get("suggested_basket_sector")),
            },
        )
        bucket["count"] += 1
        event_id = clean_text(event.get("event_id"))
        if event_id and event_id not in bucket["event_ids"]:
            bucket["event_ids"].append(event_id)
        bucket["candidate_names"] = unique_strings(bucket["candidate_names"] + clean_string_list(event.get("suggested_basket_candidates")))
        bucket["core_candidate_names"] = unique_strings(bucket["core_candidate_names"] + clean_string_list(event.get("suggested_basket_core_candidates")))
        if not clean_text(bucket.get("sector_or_chain")):
            bucket["sector_or_chain"] = clean_text(event.get("suggested_basket_sector"))
    entries = list(grouped.values())
    entries.sort(key=lambda item: (-int(item.get("count") or 0), clean_text(item.get("value"))))
    return entries[:limit]


def build_named_pick_entries(events: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    return ranked_pattern_entries(
        collect_event_support_map(events, lambda event: clean_string_list(event.get("names"))),
        min_count=1,
        limit=limit,
    )


def build_language_clues(ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clue_map = {
        "core_pick_language": [phrase for phrase in DIRECT_CORE_PHRASES if phrase],
        "high_conviction_language": [phrase for phrase in STRONG_DIRECT_PHRASES if phrase],
        "shortage_language": ["缺口", "供不应求", "bottleneck", "shortage", "utilization"],
        "price_hike_language": ["涨价", "提价", "price hike"],
        "capacity_language": ["扩产", "投产", "expansion"],
        "order_language": ["订单", "中标", "order", "orders"],
        "earnings_language": ["业绩预告", "业绩快报", "预增", "earnings", "Q1", "year report"],
    }
    support_map: dict[str, list[str]] = {}
    for event in ledger:
        text = clean_text(event.get("thesis_excerpt"))
        event_id = clean_text(event.get("event_id"))
        for clue_name, phrases in clue_map.items():
            if any(phrase and phrase in text for phrase in phrases):
                support_map.setdefault(clue_name, [])
                if event_id and event_id not in support_map[clue_name]:
                    support_map[clue_name].append(event_id)
    return ranked_pattern_entries(support_map, min_count=1, limit=6)


def build_pattern_claims(
    entries: list[dict[str, Any]],
    *,
    pattern_type: str,
    min_confirmed_count: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    confirmed: list[dict[str, Any]] = []
    likely: list[dict[str, Any]] = []
    for entry in entries:
        claim = {
            "pattern_type": pattern_type,
            "value": clean_text(entry.get("value")),
            "count": int(entry.get("count") or 0),
            "event_ids": clean_string_list(entry.get("event_ids")),
        }
        if claim["count"] >= min_confirmed_count:
            confirmed.append(claim)
        else:
            likely.append(claim)
    return confirmed, likely


def actionability_level(event_count: int, actionable_event_count: int) -> str:
    if event_count <= 0 or actionable_event_count <= 0:
        return "none"
    ratio = actionable_event_count / max(1, event_count)
    if ratio >= 0.5:
        return "high"
    if ratio >= 0.25:
        return "medium"
    return "low"


def method_posture(event_count: int, actionable_event_count: int, setup_entries: list[dict[str, Any]]) -> str:
    if actionable_event_count <= 0:
        return "commentary_only"
    ratio = actionable_event_count / max(1, event_count)
    top_setup = clean_text(safe_dict((setup_entries or [{}])[0]).get("value"))
    if ratio < 0.25 or top_setup == "logic_support":
        return "chain_first_commentator"
    if ratio < 0.5:
        return "hybrid_chain_then_pick"
    return "selection_first"


def setup_style_label(value: str) -> str:
    labels = {
        "theme_basket": "basket-first",
        "direct_pick": "single-stock-conviction",
        "logic_support": "chain-first",
        "quote_only": "quote-context-heavy",
    }
    return labels.get(clean_text(value), clean_text(value) or "mixed")


def build_one_line_style(
    method_posture: str,
    setup_entries: list[dict[str, Any]],
    sector_entries: list[dict[str, Any]],
    catalyst_entries: list[dict[str, Any]],
    dominant_horizon: str,
) -> str:
    posture_labels = {
        "selection_first": setup_style_label(clean_text(setup_entries[0]["value"])) if setup_entries else "selection-first",
        "hybrid_chain_then_pick": "hybrid-chain-then-pick",
        "chain_first_commentator": "chain-first-commentator",
        "commentary_only": "commentary-only",
    }
    setup = posture_labels.get(method_posture, setup_style_label(clean_text(setup_entries[0]["value"])) if setup_entries else "mixed")
    sector = clean_text(sector_entries[0]["value"]) if sector_entries else "multi-sector"
    catalyst = clean_text(catalyst_entries[0]["value"]) if catalyst_entries else "logic-led"
    horizon = dominant_horizon or "unclear_horizon"
    return f"{setup} picker leaning toward {sector} themes, usually framed through {catalyst} catalysts and {horizon} timing."


def build_style_card(ledger: list[dict[str, Any]], summary: dict[str, Any], score_summary: dict[str, Any]) -> dict[str, Any]:
    if not ledger:
        return {}

    actionable_ledger = [
        event
        for event in ledger
        if clean_text(event.get("classification")) in {"direct_pick", "theme_basket"}
    ]
    primary_ledger = actionable_ledger if len(actionable_ledger) >= 2 else [event for event in ledger if clean_text(event.get("classification")) != "quote_only"] or ledger

    setup_entries = ranked_pattern_entries(
        collect_event_support_map(
            primary_ledger,
            lambda event: clean_text(event.get("classification")),
        ),
        min_count=1,
        limit=4,
    )
    sector_entries = ranked_pattern_entries(
        collect_event_support_map(primary_ledger, lambda event: clean_text(event.get("sector_or_chain"))),
        min_count=1,
        limit=5,
    )
    catalyst_entries = ranked_pattern_entries(
        collect_event_support_map(primary_ledger, lambda event: clean_text(event.get("catalyst_type"))),
        min_count=1,
        limit=5,
    )
    horizon_entries = ranked_pattern_entries(
        collect_event_support_map(primary_ledger, lambda event: clean_text(event.get("holding_horizon_guess"))),
        min_count=1,
        limit=5,
    )
    language_clues = build_language_clues(primary_ledger or ledger)

    confirmed_patterns: list[dict[str, Any]] = []
    likely_patterns: list[dict[str, Any]] = []
    for pattern_type, entries in (
        ("setup_type", setup_entries),
        ("sector", sector_entries),
        ("catalyst", catalyst_entries),
    ):
        confirmed, likely = build_pattern_claims(entries, pattern_type=pattern_type)
        confirmed_patterns.extend(confirmed)
        likely_patterns.extend(likely)

    quote_only_ids = [clean_text(event.get("event_id")) for event in ledger if clean_text(event.get("classification")) == "quote_only"]
    operator_review_ids = [clean_text(event.get("event_id")) for event in ledger if event.get("needs_operator_review")]
    logic_without_names_ids = [
        clean_text(event.get("event_id"))
        for event in ledger
        if clean_text(event.get("classification")) == "logic_support" and not clean_string_list(event.get("names"))
    ]
    mapped_logic_events = [
        event
        for event in ledger
        if clean_text(event.get("classification")) == "logic_support" and clean_text(event.get("suggested_basket_name"))
    ]
    basket_hint_entries = build_advisory_basket_entries(mapped_logic_events, limit=5)
    named_pick_entries = build_named_pick_entries(actionable_ledger or primary_ledger, limit=8)
    inference_only_patterns: list[dict[str, Any]] = []
    if quote_only_ids:
        inference_only_patterns.append(
            {
                "pattern_type": "caution",
                "value": "quote_only_material_exists",
                "count": len(quote_only_ids),
                "event_ids": unique_strings(quote_only_ids),
            }
        )
    if logic_without_names_ids:
        inference_only_patterns.append(
            {
                "pattern_type": "caution",
                "value": "logic_notes_without_named_stocks",
                "count": len(logic_without_names_ids),
                "event_ids": unique_strings(logic_without_names_ids),
            }
        )
    if operator_review_ids:
        inference_only_patterns.append(
            {
                "pattern_type": "caution",
                "value": "operator_review_still_required",
                "count": len(operator_review_ids),
                "event_ids": unique_strings(operator_review_ids),
            }
        )

    dominant_horizon = clean_text(horizon_entries[0]["value"]) if horizon_entries else ""
    scoreable_name_count = int(safe_dict(score_summary).get("scoreable_name_count") or 0)
    event_count = int(summary.get("total_events") or 0)
    actionable_event_count = len(actionable_ledger)
    current_actionability_level = actionability_level(event_count, actionable_event_count)
    current_method_posture = method_posture(event_count, actionable_event_count, setup_entries)
    where_the_edge_seems_real: list[str] = []
    if setup_entries:
        where_the_edge_seems_real.append(
            f"Pattern density is strongest in `{clean_text(setup_entries[0]['value'])}` style setups."
        )
    if named_pick_entries:
        where_the_edge_seems_real.append(
            f"Repeated explicit names currently cluster around `{clean_text(named_pick_entries[0]['value'])}`."
        )
    if sector_entries:
        where_the_edge_seems_real.append(
            f"Sector concentration currently clusters around `{clean_text(sector_entries[0]['value'])}`."
        )
    if catalyst_entries:
        where_the_edge_seems_real.append(
            f"Most recurring catalysts are described through `{clean_text(catalyst_entries[0]['value'])}` signals."
        )
    if not where_the_edge_seems_real:
        where_the_edge_seems_real.append("Current sample is still too thin to isolate a durable edge.")
    if basket_hint_entries:
        where_the_edge_seems_real.append(
            f"Chain commentary repeatedly maps into advisory basket `{clean_text(basket_hint_entries[0]['value'])}`."
        )
    if scoreable_name_count > 0:
        best_setup = sorted(
            safe_dict(score_summary.get("by_classification")).items(),
            key=lambda item: (-float(safe_dict(item[1]).get("avg_return") or 0.0), -int(safe_dict(item[1]).get("count") or 0)),
        )
        if best_setup:
            where_the_edge_seems_real.append(
                f"Post-score calibration currently looks strongest in `{clean_text(best_setup[0][0])}` setups."
            )
        best_sector = sorted(
            safe_dict(score_summary.get("by_sector")).items(),
            key=lambda item: (-float(safe_dict(item[1]).get("avg_return") or 0.0), -int(safe_dict(item[1]).get("count") or 0)),
        )
        if best_sector:
            where_the_edge_seems_real.append(
                f"Post-score calibration currently clusters best in `{clean_text(best_sector[0][0])}` themes."
            )

    where_the_edge_breaks: list[str] = []
    if quote_only_ids:
        where_the_edge_breaks.append("Some posts rely on quoted or inherited context and should not be promoted into fresh picks.")
    if operator_review_ids:
        where_the_edge_breaks.append("A meaningful share of events still requires operator review because the stock names or intent remain implied.")
    if not any(clean_text(event.get("classification")) == "direct_pick" for event in ledger):
        where_the_edge_breaks.append("Single-stock conviction is not yet proven from the current sample.")
    if current_actionability_level in {"low", "none"}:
        where_the_edge_breaks.append("Actionable named picks are still sparse relative to the amount of logic commentary.")
    if scoreable_name_count > 0:
        weak_setup = sorted(
            safe_dict(score_summary.get("by_classification")).items(),
            key=lambda item: (float(safe_dict(item[1]).get("avg_return") or 0.0), int(safe_dict(item[1]).get("count") or 0)),
        )
        if weak_setup:
            where_the_edge_breaks.append(
                f"Post-score calibration is weakest in `{clean_text(weak_setup[0][0])}` setups so far."
            )

    aversion_patterns: list[dict[str, Any]] = []
    if quote_only_ids:
        aversion_patterns.append(
            {
                "value": "quote_only_as_new_pick",
                "count": len(quote_only_ids),
                "event_ids": unique_strings(quote_only_ids),
            }
        )
    if logic_without_names_ids:
        aversion_patterns.append(
            {
                "value": "unnamed_logic_posts",
                "count": len(logic_without_names_ids),
                "event_ids": unique_strings(logic_without_names_ids),
            }
        )

    return {
        "evidence_stage": "score_calibrated" if scoreable_name_count > 0 else "pre_score_pattern_only",
        "method_posture": current_method_posture,
        "actionability_level": current_actionability_level,
        "one_line_style": build_one_line_style(current_method_posture, setup_entries, sector_entries, catalyst_entries, dominant_horizon),
        "confirmed_patterns": confirmed_patterns,
        "likely_patterns": likely_patterns,
        "inference_only_patterns": inference_only_patterns,
        "preferred_setup_types": setup_entries,
        "preferred_catalysts": catalyst_entries,
        "preferred_sectors": sector_entries,
        "named_pick_hints": named_pick_entries,
        "aversion_patterns": aversion_patterns,
        "timing_model": {
            "dominant_horizon": dominant_horizon,
            "distribution": horizon_entries,
        },
        "advisory_basket_hints": basket_hint_entries,
        "language_clues": language_clues,
        "where_the_edge_seems_real": where_the_edge_seems_real,
        "where_the_edge_breaks": where_the_edge_breaks,
        "sample_summary": {
            "event_count": event_count,
            "actionable_event_count": actionable_event_count,
            "mapped_logic_basket_count": len(mapped_logic_events),
            "operator_review_count": int(summary.get("operator_review_count") or 0),
            "scoreable_name_count": scoreable_name_count,
        },
        "post_score_summary": safe_dict(score_summary.get("overall")) if scoreable_name_count > 0 else {},
    }


def build_overlay_pack(style_card: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    if not style_card:
        return {}
    theme_biases = [
        {
            "theme": clean_text(item.get("value")),
            "weight": int(item.get("count") or 0),
            "event_ids": clean_string_list(item.get("event_ids")),
        }
        for item in safe_list(style_card.get("preferred_sectors"))
        if clean_text(item.get("value"))
    ][:4]
    catalyst_biases = [
        {
            "catalyst_type": clean_text(item.get("value")),
            "weight": int(item.get("count") or 0),
            "event_ids": clean_string_list(item.get("event_ids")),
        }
        for item in safe_list(style_card.get("preferred_catalysts"))
        if clean_text(item.get("value"))
    ][:4]
    setup_biases = [
        {
            "setup_type": clean_text(item.get("value")),
            "weight": int(item.get("count") or 0),
            "event_ids": clean_string_list(item.get("event_ids")),
        }
        for item in safe_list(style_card.get("preferred_setup_types"))
        if clean_text(item.get("value"))
    ][:4]
    language_trigger_phrases = [clean_text(item.get("value")) for item in safe_list(style_card.get("language_clues")) if clean_text(item.get("value"))][:6]
    advisory_basket_hints = [
        {
            "basket_name": clean_text(item.get("value")),
            "weight": int(item.get("count") or 0),
            "event_ids": clean_string_list(item.get("event_ids")),
            "candidate_names": clean_string_list(item.get("candidate_names")),
            "core_candidate_names": clean_string_list(item.get("core_candidate_names")),
            "sector_or_chain": clean_text(item.get("sector_or_chain")),
        }
        for item in safe_list(style_card.get("advisory_basket_hints"))
        if clean_text(item.get("value"))
    ][:4]
    named_pick_hints = [
        {
            "candidate_name": clean_text(item.get("value")),
            "weight": int(item.get("count") or 0),
            "event_ids": clean_string_list(item.get("event_ids")),
        }
        for item in safe_list(style_card.get("named_pick_hints"))
        if clean_text(item.get("value"))
    ][:8]
    notes_for_month_end_shortlist = [
        clean_text(style_card.get("one_line_style")),
        *clean_string_list(style_card.get("where_the_edge_seems_real")),
        *clean_string_list(style_card.get("where_the_edge_breaks")),
    ]
    return {
        "overlay_name": f"x_style_{clean_text(subject.get('handle')) or 'subject'}",
        "advisory_only": True,
        "evidence_stage": clean_text(style_card.get("evidence_stage")),
        "theme_biases": theme_biases,
        "catalyst_preference_bonus": catalyst_biases,
        "setup_biases": setup_biases,
        "advisory_basket_hints": advisory_basket_hints,
        "named_pick_hints": named_pick_hints,
        "language_trigger_phrases": language_trigger_phrases,
        "notes_for_month_end_shortlist": unique_strings(notes_for_month_end_shortlist),
        "subject_tags": clean_string_list(subject.get("tags")),
    }


def merge_request_layers(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = deepcopy(merged.get(key))
            nested.update(deepcopy(value))
            merged[key] = nested
        else:
            merged[key] = deepcopy(value)
    return merged


def merge_theme_alias_maps(*maps: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for payload in maps:
        for key, values in normalize_theme_aliases(payload).items():
            merged[key] = unique_strings(merged.get(key, []) + clean_string_list(values))
    return merged


def merge_logic_basket_rules(*rule_sets: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_rule_names: set[str] = set()
    for payload in rule_sets:
        for rule in normalize_logic_basket_rules(payload):
            rule_name = clean_text(rule.get("rule_name"))
            if rule_name and rule_name in seen_rule_names:
                continue
            if rule_name:
                seen_rule_names.add(rule_name)
            merged.append(rule)
    return merged


def build_batch_child_request(
    subject_record: dict[str, Any],
    shared_request: dict[str, Any],
    subject_override: dict[str, Any],
) -> dict[str, Any]:
    child = merge_request_layers(shared_request, subject_override)
    child["subject_url"] = clean_text(subject_record.get("url")) or child.get("subject_url") or f"https://x.com/{clean_text(subject_record.get('handle'))}"
    child["subject"] = merge_request_layers(
        {
            "platform": "x",
            "handle": clean_text(subject_record.get("handle")),
            "display_name": clean_text(subject_record.get("display_name")),
            "url": clean_text(subject_record.get("url")),
            "notes": clean_text(subject_record.get("notes")),
            "tags": clean_string_list(subject_record.get("tags")),
        },
        safe_dict(child.get("subject")),
    )
    child["candidate_names"] = unique_strings(
        clean_string_list(subject_record.get("candidate_names"))
        + clean_string_list(child.get("candidate_names"))
    )
    child["theme_aliases"] = merge_theme_alias_maps(
        safe_dict(subject_record.get("theme_aliases")),
        safe_dict(child.get("theme_aliases")),
    )
    child["logic_basket_rules"] = merge_logic_basket_rules(
        subject_record.get("logic_basket_rules"),
        child.get("logic_basket_rules"),
    )
    x_index_template = safe_dict(child.pop("x_index_request_template", {}))
    if x_index_template and not any(key in child for key in ("x_index_request", "x_index_request_path", "x_index_result", "x_index_result_path", "timeline_scan", "timeline_scan_path", "source_board_seed")):
        x_request = deepcopy(x_index_template)
        x_request.setdefault("topic", f"{clean_text(subject_record.get('handle'))} stock picker style study")
        handle = clean_text(subject_record.get("handle"))
        account_allowlist = unique_strings(clean_string_list(x_request.get("account_allowlist")) + ([handle] if handle else []))
        if account_allowlist:
            x_request["account_allowlist"] = account_allowlist
        manual_urls = clean_string_list(x_request.get("manual_urls"))
        subject_url = clean_text(subject_record.get("url"))
        if subject_url and STATUS_URL_RE.search(subject_url):
            manual_urls = unique_strings(manual_urls + [subject_url])
        x_request["manual_urls"] = manual_urls
        child["x_index_request"] = x_request
    return child


def subject_comparison_record(result: dict[str, Any]) -> dict[str, Any]:
    subject = safe_dict(result.get("subject"))
    style_card = safe_dict(result.get("style_card"))
    score_summary = safe_dict(result.get("score_summary"))
    preferred_setup = clean_text(safe_dict((safe_list(style_card.get("preferred_setup_types")) or [{}])[0]).get("value"))
    preferred_sector = clean_text(safe_dict((safe_list(style_card.get("preferred_sectors")) or [{}])[0]).get("value"))
    preferred_catalyst = clean_text(safe_dict((safe_list(style_card.get("preferred_catalysts")) or [{}])[0]).get("value"))
    dominant_horizon = clean_text(safe_dict(style_card.get("timing_model")).get("dominant_horizon"))
    return {
        "handle": clean_text(subject.get("handle")),
        "display_name": clean_text(subject.get("display_name")),
        "url": clean_text(subject.get("url")),
        "tags": clean_string_list(subject.get("tags")),
        "evidence_stage": clean_text(style_card.get("evidence_stage")),
        "event_count": int(safe_dict(style_card.get("sample_summary")).get("event_count") or 0),
        "actionable_event_count": int(safe_dict(style_card.get("sample_summary")).get("actionable_event_count") or 0),
        "mapped_logic_basket_count": int(safe_dict(style_card.get("sample_summary")).get("mapped_logic_basket_count") or 0),
        "actionability_level": clean_text(style_card.get("actionability_level")),
        "method_posture": clean_text(style_card.get("method_posture")),
        "scoreable_name_count": int(safe_dict(style_card.get("sample_summary")).get("scoreable_name_count") or 0),
        "preferred_setup": preferred_setup,
        "preferred_sector": preferred_sector,
        "preferred_catalyst": preferred_catalyst,
        "dominant_horizon": dominant_horizon,
        "avg_return": float(safe_dict(score_summary.get("overall")).get("avg_return") or 0.0) if score_summary else 0.0,
        "one_line_style": clean_text(style_card.get("one_line_style")),
    }


def build_batch_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# X Stock Picker Style Batch Report",
        "",
        f"- Analysis time: `{clean_text(result.get('analysis_time'))}`",
        f"- Subject count: `{len(safe_list(result.get('subject_runs')))} `",
        "",
        "## Comparison",
        "",
        "| Handle | Evidence stage | Method posture | Actionability | Events | Actionable | Basket hints | Scoreable names | Preferred setup | Preferred sector | Preferred catalyst | Dominant horizon | Avg return |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | ---: |",
    ]
    for item in safe_list(result.get("comparison_summary")):
        lines.append(
            "| "
            + " | ".join(
                [
                    clean_text(item.get("handle")),
                    clean_text(item.get("evidence_stage")),
                    clean_text(item.get("method_posture")),
                    clean_text(item.get("actionability_level")),
                    str(int(item.get("event_count") or 0)),
                    str(int(item.get("actionable_event_count") or 0)),
                    str(int(item.get("mapped_logic_basket_count") or 0)),
                    str(int(item.get("scoreable_name_count") or 0)),
                    clean_text(item.get("preferred_setup")),
                    clean_text(item.get("preferred_sector")),
                    clean_text(item.get("preferred_catalyst")),
                    clean_text(item.get("dominant_horizon")),
                    f"{float(item.get('avg_return') or 0.0):+.2f}%",
                ]
            )
            + " |"
        )
    lines.append("")
    for subject_run in safe_list(result.get("subject_runs")):
        lines.append(f"## @{clean_text(safe_dict(subject_run.get('subject')).get('handle'))}")
        lines.append("")
        report_markdown = str(subject_run.get("report_markdown") or "").strip()
        if report_markdown:
            lines.append(report_markdown)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_markdown_report(result: dict[str, Any]) -> str:
    subject = safe_dict(result.get("subject"))
    summary = safe_dict(result.get("source_summary"))
    recommendation = safe_dict(result.get("recommendation_summary"))
    score_summary = safe_dict(result.get("score_summary"))
    style_card = safe_dict(result.get("style_card"))
    overlay_pack = safe_dict(result.get("overlay_pack"))
    lines = [
        f"# X Stock Picker Style Report: @{subject.get('handle', '')}",
        "",
        f"- Workflow stage: `{result.get('workflow_stage', '')}`",
        f"- Analysis time: `{result.get('analysis_time', '')}`",
        f"- Subject URL: `{clean_text(subject.get('url'))}`" if clean_text(subject.get("url")) else "- Subject URL: ``",
        f"- Source count: `{summary.get('total_sources', 0)}`",
        f"- Operator-review count: `{summary.get('operator_review_count', 0)}`",
        f"- Recommendation events: `{recommendation.get('total_events', 0)}`",
        f"- Scoreable names: `{score_summary.get('scoreable_name_count', 0)}`" if score_summary else "- Scoreable names: `0`",
        "",
        "## Source Board",
        "",
    ]
    if clean_text(subject.get("notes")):
        lines.insert(6, f"- Subject notes: {clean_text(subject.get('notes'))}")
    if clean_string_list(subject.get("tags")):
        lines.insert(7 if clean_text(subject.get('notes')) else 6, f"- Subject tags: {', '.join(clean_string_list(subject.get('tags')))}")
    for item in safe_list(result.get("source_board")):
        title = clean_text(item.get("status_url")) or clean_text(item.get("source_id"))
        lines.append(f"### {title}")
        lines.append(f"- Published at: `{clean_text(item.get('published_at'))}`")
        lines.append(f"- Extraction method: `{clean_text(item.get('extraction_method'))}`")
        lines.append(f"- Direct text kind: `{clean_text(item.get('direct_text_kind'))}`")
        if clean_text(item.get("quoted_text")):
            lines.append(f"- Quoted text: {short_excerpt(item.get('quoted_text'), limit=160)}")
        if clean_text(item.get("direct_text")):
            lines.append(f"- Direct text: {short_excerpt(item.get('direct_text'), limit=220)}")
        if item.get("needs_operator_review"):
            lines.append(f"- Operator review: {', '.join(clean_string_list(item.get('operator_review_reasons')))}")
        lines.append("")
    lines.extend(
        [
            "## Recommendation Ledger",
            "",
        ]
    )
    for event in safe_list(result.get("recommendation_ledger")):
        lines.append(f"### {clean_text(event.get('status_url')) or clean_text(event.get('event_id'))}")
        lines.append(f"- Classification: `{clean_text(event.get('classification'))}`")
        lines.append(f"- Strength: `{clean_text(event.get('strength'))}`")
        if clean_string_list(event.get("names")):
            lines.append(f"- Names: {', '.join(clean_string_list(event.get('names')))}")
        if clean_text(event.get("sector_or_chain")):
            lines.append(f"- Sector or chain: `{clean_text(event.get('sector_or_chain'))}`")
        if clean_text(event.get("catalyst_type")):
            lines.append(f"- Catalyst type: `{clean_text(event.get('catalyst_type'))}`")
        if clean_text(event.get("holding_horizon_guess")):
            lines.append(f"- Holding horizon guess: `{clean_text(event.get('holding_horizon_guess'))}`")
        if clean_text(event.get("thesis_excerpt")):
            lines.append(f"- Thesis excerpt: {clean_text(event.get('thesis_excerpt'))}")
        if event.get("needs_operator_review"):
            lines.append(f"- Operator review: {', '.join(clean_string_list(event.get('ambiguity_flags')))}")
        lines.append("")
    lines.extend(
        [
            "## Style Card",
            "",
        ]
    )
    if style_card:
        lines.append(f"- Evidence stage: `{clean_text(style_card.get('evidence_stage'))}`")
        if clean_text(style_card.get("method_posture")):
            lines.append(f"- Method posture: `{clean_text(style_card.get('method_posture'))}`")
        if clean_text(style_card.get("actionability_level")):
            lines.append(f"- Actionability level: `{clean_text(style_card.get('actionability_level'))}`")
        lines.append(f"- One-line style: {clean_text(style_card.get('one_line_style'))}")
        timing_model = safe_dict(style_card.get("timing_model"))
        if clean_text(timing_model.get("dominant_horizon")):
            lines.append(f"- Dominant horizon: `{clean_text(timing_model.get('dominant_horizon'))}`")
        post_score_summary = safe_dict(style_card.get("post_score_summary"))
        if post_score_summary:
            lines.append(
                f"- Post-score summary: count `{int(post_score_summary.get('count') or 0)}`, "
                f"win rate `{float(post_score_summary.get('win_rate') or 0.0):.1f}%`, "
                f"avg return `{float(post_score_summary.get('avg_return') or 0.0):+.2f}%`"
            )
        preferred_setups = safe_list(style_card.get("preferred_setup_types"))
        if preferred_setups:
            lines.append(
                "- Preferred setup types: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in preferred_setups)
            )
        preferred_sectors = safe_list(style_card.get("preferred_sectors"))
        if preferred_sectors:
            lines.append(
                "- Preferred sectors: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in preferred_sectors)
            )
        preferred_catalysts = safe_list(style_card.get("preferred_catalysts"))
        if preferred_catalysts:
            lines.append(
                "- Preferred catalysts: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in preferred_catalysts)
            )
        named_pick_hints = safe_list(style_card.get("named_pick_hints"))
        if named_pick_hints:
            lines.append(
                "- Named pick hints: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in named_pick_hints)
            )
        advisory_basket_hints = safe_list(style_card.get("advisory_basket_hints"))
        if advisory_basket_hints:
            lines.append(
                "- Advisory basket hints: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in advisory_basket_hints)
            )
        language_clues = safe_list(style_card.get("language_clues"))
        if language_clues:
            lines.append(
                "- Language clues: "
                + ", ".join(f"{clean_text(item.get('value'))} ({int(item.get('count') or 0)})" for item in language_clues)
            )
        for bullet in clean_string_list(style_card.get("where_the_edge_seems_real")):
            lines.append(f"- Edge seems real: {bullet}")
        for bullet in clean_string_list(style_card.get("where_the_edge_breaks")):
            lines.append(f"- Edge breaks: {bullet}")
    else:
        lines.append("- Style card not available yet.")
    lines.append("")
    lines.extend(
        [
            "## Overlay Pack",
            "",
        ]
    )
    if overlay_pack:
        lines.append(f"- Overlay name: `{clean_text(overlay_pack.get('overlay_name'))}`")
        lines.append(f"- Advisory only: `{str(bool(overlay_pack.get('advisory_only'))).lower()}`")
        if safe_list(overlay_pack.get("theme_biases")):
            lines.append(
                "- Theme biases: "
                + ", ".join(
                    f"{clean_text(item.get('theme'))} ({int(item.get('weight') or 0)})"
                    for item in safe_list(overlay_pack.get("theme_biases"))
                )
            )
        if safe_list(overlay_pack.get("setup_biases")):
            lines.append(
                "- Setup biases: "
                + ", ".join(
                    f"{clean_text(item.get('setup_type'))} ({int(item.get('weight') or 0)})"
                    for item in safe_list(overlay_pack.get("setup_biases"))
                )
            )
        if safe_list(overlay_pack.get("named_pick_hints")):
            lines.append(
                "- Named pick hints: "
                + ", ".join(
                    f"{clean_text(item.get('candidate_name'))} ({int(item.get('weight') or 0)})"
                    for item in safe_list(overlay_pack.get("named_pick_hints"))
                )
            )
        if safe_list(overlay_pack.get("advisory_basket_hints")):
            lines.append(
                "- Advisory basket hints: "
                + ", ".join(
                    f"{clean_text(item.get('basket_name'))} ({int(item.get('weight') or 0)})"
                    for item in safe_list(overlay_pack.get("advisory_basket_hints"))
                )
            )
        if clean_string_list(overlay_pack.get("language_trigger_phrases")):
            lines.append(
                "- Language trigger phrases: " + ", ".join(clean_string_list(overlay_pack.get("language_trigger_phrases")))
            )
    else:
        lines.append("- Overlay pack not available yet.")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def normalize_batch_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    subject_registry_path = normalize_path(raw_request.get("subject_registry_path"))
    registry_payload: Any = deepcopy(raw_request.get("subject_registry")) if raw_request.get("subject_registry") is not None else None
    if registry_payload is None and subject_registry_path is not None:
        registry_payload = load_json(subject_registry_path)
    registry = subject_registry_map(registry_payload)
    if not registry:
        raise ValueError("Batch mode requires `subject_registry` or `subject_registry_path` with at least one subject.")
    selected_handles = [handle for handle in [normalize_x_handle(item) for item in safe_list(raw_request.get("selected_handles"))] if handle]
    if not selected_handles:
        selected_handles = sorted(registry.keys())
    shared_request = safe_dict(raw_request.get("shared_request"))
    subject_overrides = safe_dict(raw_request.get("subject_overrides_by_handle"))
    analysis_time = parse_datetime(raw_request.get("analysis_time")) or now_utc()
    analysis_date = parse_iso_date(raw_request.get("analysis_date")) or analysis_time.astimezone(LOCAL_TZ).date()
    return {
        "analysis_time": analysis_time,
        "analysis_date": analysis_date.isoformat(),
        "registry": registry,
        "selected_handles": selected_handles,
        "shared_request": shared_request,
        "subject_overrides_by_handle": subject_overrides,
    }


def run_x_stock_picker_style_batch(raw_request: dict[str, Any]) -> dict[str, Any]:
    batch_request = normalize_batch_request(raw_request)
    subject_runs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for handle in batch_request["selected_handles"]:
        subject_record = safe_dict(batch_request["registry"].get(handle))
        if not subject_record:
            warnings.append(f"missing_subject:{handle}")
            continue
        child_request = build_batch_child_request(
            subject_record,
            batch_request["shared_request"],
            safe_dict(batch_request["subject_overrides_by_handle"].get(handle)),
        )
        try:
            subject_runs.append(run_x_stock_picker_style(child_request))
        except Exception as exc:
            warnings.append(f"subject_failed:{handle}:{clean_text(str(exc))}")
    comparison_summary = [subject_comparison_record(item) for item in subject_runs]
    result = {
        "workflow_kind": "x_stock_picker_style_batch",
        "workflow_stage": "batch_compare",
        "analysis_time": isoformat_or_blank(batch_request["analysis_time"]),
        "analysis_date": clean_text(batch_request.get("analysis_date")),
        "selected_handles": batch_request["selected_handles"],
        "subject_runs": subject_runs,
        "comparison_summary": comparison_summary,
        "warnings": warnings,
    }
    result["report_markdown"] = build_batch_markdown_report(result)
    return result


def run_x_stock_picker_style(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_request)
    subject = safe_dict(request.get("subject"))
    warnings: list[str] = []
    source_items: list[dict[str, Any]] = []

    for payload_spec in safe_list(request.get("payload_specs")):
        payload = payload_spec.get("payload")
        if payload is None and payload_spec.get("path") is not None:
            payload = load_json(payload_spec["path"])
        if clean_text(payload_spec.get("kind")) == "x_index_request":
            try:
                payload = run_x_index_request(safe_dict(payload))
            except Exception as exc:
                warnings.append(f"x_index_request_failed: {clean_text(str(exc))}")
                continue
        try:
            source_items.extend(build_source_items_from_payload(safe_dict(payload), clean_text(payload_spec.get("kind"))))
        except ValueError as exc:
            warnings.append(clean_text(str(exc)))

    if request.get("require_matching_handle", True):
        source_items = [
            item
            for item in source_items
            if clean_text(item.get("author_handle")).lower() == clean_text(subject.get("handle")).lower()
        ]
    source_start_date = parse_iso_date(request.get("source_start_date"))
    if source_start_date is not None:
        source_items = [
            item
            for item in source_items
            if (parse_iso_date(item.get("published_at")) or date.min) >= source_start_date
        ]

    source_board = dedupe_source_board(source_items)
    source_board = source_board[: request["max_source_items"]]
    recommendation_ledger = build_recommendation_ledger(source_board, request)
    recommendation_ledger = score_recommendation_ledger(recommendation_ledger, request)
    recommendation_meta = recommendation_summary(recommendation_ledger)
    score_summary = score_summary_from_ledger(recommendation_ledger, request)
    style_card = build_style_card(recommendation_ledger, recommendation_meta, score_summary)
    overlay_pack = build_overlay_pack(style_card, subject)
    workflow_stage = "style_card" if style_card else "recommendation_ledger" if recommendation_ledger else "source_board"

    result = {
        "workflow_kind": "x_stock_picker_style_learning",
        "workflow_stage": workflow_stage,
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "subject": deepcopy(subject),
        "source_board": source_board,
        "source_summary": source_summary(source_board),
        "recommendation_ledger": recommendation_ledger,
        "recommendation_summary": recommendation_meta,
        "score_summary": score_summary,
        "style_card": style_card,
        "overlay_pack": overlay_pack,
        "warnings": warnings,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_markdown_report",
    "build_overlay_pack",
    "build_recommendation_ledger",
    "build_style_card",
    "build_source_items_from_payload",
    "classify_source_item",
    "dedupe_source_board",
    "load_json",
    "normalize_request",
    "recommendation_summary",
    "run_x_stock_picker_style",
    "write_json",
]
