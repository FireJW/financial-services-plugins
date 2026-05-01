from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from news_index_runtime import (
    clean_string_list,
    isoformat_or_blank,
    load_json,
    parse_datetime,
    run_news_index,
    short_excerpt,
    slugify,
    write_json,
)


COLLECTION_KEYS = (
    "items",
    "results",
    "entries",
    "records",
    "news",
    "articles",
    "hot_topics",
    "hotspots",
    "topics",
    "trending_topics",
    "trends",
    "latest",
    "rows",
    "data",
)
RESULT_PATH_KEYS = ("trendradar_result_path", "result_path", "file", "path")
NESTED_RESULT_KEYS = ("trendradar", "trendradar_result", "source_result", "result")
TITLE_KEYS = ("title", "name", "headline", "topic", "keyword")
URL_KEYS = ("url", "link", "href", "source_url", "article_url")
TEXT_KEYS = (
    "summary",
    "description",
    "abstract",
    "content",
    "text",
    "body",
    "excerpt",
    "snippet",
    "digest",
)
PLATFORM_KEYS = ("platform", "source", "site", "feed", "feed_name", "channel", "category")
PUBLISHED_AT_KEYS = (
    "published_at",
    "publish_time",
    "pub_date",
    "pubDate",
    "created_at",
    "created",
    "time",
    "timestamp",
    "date",
    "first_seen",
)
OBSERVED_AT_KEYS = (
    "observed_at",
    "collected_at",
    "crawled_at",
    "fetched_at",
    "updated_at",
    "last_seen",
    "last_seen_at",
)
SOCIAL_PLATFORM_HINTS = {
    "bilibili",
    "douyin",
    "hackernews",
    "kuaishou",
    "reddit",
    "twitter",
    "weibo",
    "x",
    "xiaohongshu",
    "zhihu",
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def normalize_key(value: Any) -> str:
    return clean_text(value).lower().replace(" ", "_").replace("-", "_")


def first_present_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not clean_text(value):
            continue
        return value
    return None


def normalize_source_type(value: Any) -> str:
    text = clean_text(value).lower().replace(" ", "_").replace("-", "_")
    return text


def looks_like_item(value: dict[str, Any]) -> bool:
    if any(key in value for key in COLLECTION_KEYS):
        return False
    return any(first_present_value(value, keys) is not None for keys in (TITLE_KEYS, URL_KEYS, TEXT_KEYS, PLATFORM_KEYS))


def flatten_result_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for entry in value:
            items.extend(flatten_result_items(entry))
        return items
    if not isinstance(value, dict):
        return []

    nested_items: list[dict[str, Any]] = []
    for key in COLLECTION_KEYS:
        if key in value:
            nested_items.extend(flatten_result_items(value.get(key)))
    if nested_items:
        return nested_items
    if looks_like_item(value):
        return [value]
    return []


def resolve_trendradar_payload(raw_payload: dict[str, Any]) -> tuple[Any, str, str]:
    trendradar = safe_dict(raw_payload.get("trendradar"))
    if "result" in trendradar:
        return trendradar.get("result"), "inline_result", ""
    for key in RESULT_PATH_KEYS:
        path_text = clean_text(trendradar.get(key) or raw_payload.get(key))
        if path_text:
            resolved = Path(path_text).expanduser().resolve()
            return load_json(resolved), "result_path", str(resolved)
    for key in NESTED_RESULT_KEYS:
        nested = raw_payload.get(key)
        if isinstance(nested, dict) and any(collection_key in nested for collection_key in COLLECTION_KEYS):
            return nested, "inline_result", ""
    if any(key in raw_payload for key in COLLECTION_KEYS):
        return raw_payload, "inline_result", ""
    raise ValueError("TrendRadar bridge requires trendradar.result or trendradar.result_path")


def payload_metadata(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    return {
        "mcp_success": payload.get("success") if "success" in payload else "",
        "mcp_summary": clean_text(payload.get("summary") or payload.get("message")),
        "mcp_tool": clean_text(payload.get("tool") or payload.get("tool_name")),
    }


def normalize_platform(item: dict[str, Any]) -> str:
    platform = clean_text(first_present_value(item, PLATFORM_KEYS))
    if platform:
        return platform.lower()
    source_name = clean_text(item.get("source_name"))
    if source_name:
        return source_name.lower()
    return "unknown"


def infer_source_type(item: dict[str, Any], platform: str) -> str:
    explicit = normalize_source_type(item.get("source_type") or item.get("type"))
    if explicit:
        return explicit
    platform_key = platform.lower()
    if "rss" in platform_key or "news" in platform_key or "media" in platform_key:
        return "news"
    if any(hint in platform_key for hint in SOCIAL_PLATFORM_HINTS):
        return "social"
    if first_present_value(item, ("rank", "heat", "hot", "hot_score", "heat_score")) is not None:
        return "social"
    return "news"


def canonical_claim_ids(item: dict[str, Any], request: dict[str, Any]) -> list[str]:
    explicit = clean_string_list(item.get("claim_ids"))
    if explicit:
        return explicit
    return [clean_text(claim.get("claim_id")) for claim in safe_list(request.get("claims")) if isinstance(claim, dict) and clean_text(claim.get("claim_id"))]


def normalize_claim_states(item: dict[str, Any], claim_ids: list[str]) -> dict[str, str]:
    raw_states = safe_dict(item.get("claim_states") or item.get("stance_by_claim"))
    default_state = normalize_key(item.get("claim_state") or "support") or "support"
    if default_state not in {"support", "contradict", "unclear"}:
        default_state = "support"
    states: dict[str, str] = {}
    for claim_id in claim_ids:
        state = normalize_key(raw_states.get(claim_id) or default_state)
        if state not in {"support", "contradict", "unclear"}:
            state = default_state
        states[claim_id] = state
    return states


def primary_text(item: dict[str, Any]) -> str:
    title = clean_text(first_present_value(item, TITLE_KEYS))
    body = clean_text(first_present_value(item, TEXT_KEYS))
    if title and body and title not in body:
        return short_excerpt(f"{title}. {body}", limit=240)
    return short_excerpt(body or title, limit=240)


def normalize_trendradar_item(
    item: dict[str, Any],
    request: dict[str, Any],
    index: int,
) -> tuple[dict[str, Any] | None, str]:
    platform = normalize_platform(item)
    title = clean_text(first_present_value(item, TITLE_KEYS))
    url = clean_text(first_present_value(item, URL_KEYS))
    text_excerpt = primary_text(item)
    if not url and not text_excerpt:
        return None, "missing_url_and_text"

    source_type = infer_source_type(item, platform)
    claim_ids = canonical_claim_ids(item, request)
    access_mode = clean_text(item.get("access_mode") or request["source_policy"]["access_mode"]) or "local_mcp"
    published_at = parse_datetime(first_present_value(item, PUBLISHED_AT_KEYS), fallback=None)
    observed_at = parse_datetime(first_present_value(item, OBSERVED_AT_KEYS), fallback=request["analysis_time"])
    timestamp_fallback = ""
    if not published_at and request["source_policy"]["allow_observed_at_fallback"]:
        published_at = observed_at
        timestamp_fallback = "observed_at"

    metadata = {
        **request["payload_metadata"],
        "payload_source": request["payload_source"],
        "platform": platform,
        "rank": item.get("rank", ""),
        "heat": first_present_value(item, ("heat", "hot", "hot_value", "heat_score", "popularity")),
        "score": item.get("score", ""),
        "keyword": clean_text(item.get("keyword") or item.get("query")),
        "timestamp_fallback": timestamp_fallback,
    }

    candidate = {
        "source_id": clean_text(item.get("source_id") or item.get("id") or slugify(f"trendradar-{platform}-{title or url}-{index}", f"trendradar-{index:02d}")),
        "source_name": f"trendradar:{platform}",
        "source_type": source_type,
        "origin": "trendradar",
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": normalize_claim_states(item, claim_ids),
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "text_excerpt": text_excerpt,
        "channel": clean_text(item.get("channel") or request["source_policy"]["channel"]).lower() or "shadow",
        "access_mode": access_mode,
        "raw_metadata": {
            "trendradar": metadata,
            "source_item": deepcopy(item),
        },
        "discovery_reason": clean_text(item.get("discovery_reason") or f"Imported from TrendRadar {platform} signal"),
    }
    if candidate["channel"] not in {"core", "shadow", "background"}:
        candidate["channel"] = "shadow"
    if access_mode == "blocked":
        candidate["channel"] = "background"
    return candidate, ""


def dedupe_key(candidate: dict[str, Any]) -> str:
    url = clean_text(candidate.get("url")).lower()
    if url:
        return f"url:{url}"
    return f"text:{clean_text(candidate.get('source_name')).lower()}:{clean_text(candidate.get('text_excerpt')).lower()}"


def build_import_summary(
    candidates: list[dict[str, Any]],
    *,
    raw_item_count: int,
    skipped_invalid: int,
    skipped_duplicates: int,
    payload_source: str,
    result_path: str,
) -> dict[str, Any]:
    access_mode_counts = Counter(str(item.get("access_mode", "public")) for item in candidates)
    source_type_counts = Counter(str(item.get("source_type", "")) for item in candidates)
    channel_counts = Counter(str(item.get("channel", "")) for item in candidates)
    platform_counts = Counter(
        str(safe_dict(safe_dict(item.get("raw_metadata")).get("trendradar")).get("platform", "unknown"))
        for item in candidates
    )
    timestamp_fallback_count = sum(
        1
        for item in candidates
        if safe_dict(safe_dict(item.get("raw_metadata")).get("trendradar")).get("timestamp_fallback")
    )
    return {
        "payload_source": payload_source,
        "result_path": result_path,
        "raw_item_count": raw_item_count,
        "imported_candidate_count": len(candidates),
        "skipped_invalid_count": skipped_invalid,
        "skipped_duplicate_count": skipped_duplicates,
        "access_mode_counts": dict(access_mode_counts),
        "source_type_counts": dict(source_type_counts),
        "channel_counts": dict(channel_counts),
        "platform_counts": dict(platform_counts),
        "timestamp_fallback_count": timestamp_fallback_count,
        "default_channel_policy": "shadow_or_background_only",
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    summary = safe_dict(result.get("import_summary"))
    lines = [
        f"# TrendRadar Bridge Report: {request.get('topic', 'trendradar-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
        f"Payload source: {summary.get('payload_source', '') or 'unknown'}",
        f"Result path: {summary.get('result_path', '') or 'inline'}",
        f"Imported / invalid / duplicate: {summary.get('imported_candidate_count', 0)} / {summary.get('skipped_invalid_count', 0)} / {summary.get('skipped_duplicate_count', 0)}",
        f"Platforms: {summary.get('platform_counts', {})}",
        f"Source types: {summary.get('source_type_counts', {})}",
        "",
        "## Imported Candidates",
    ]
    candidates = safe_list(result.get("retrieval_request", {}).get("candidates"))
    if not candidates:
        lines.append("- None")
    for item in candidates:
        trendradar = safe_dict(safe_dict(item.get("raw_metadata")).get("trendradar"))
        lines.append(
            f"- {item.get('source_name', '')} | {item.get('source_type', '')} | {item.get('channel', '')} | "
            f"rank {trendradar.get('rank', '') or 'n/a'} | heat {trendradar.get('heat', '') or 'n/a'} | {item.get('text_excerpt', '')}"
        )
        if item.get("url"):
            lines.append(f"  URL: {item.get('url')}")

    retrieval_result = safe_dict(result.get("retrieval_result"))
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def normalize_request(raw_payload: dict[str, Any], *, preloaded_payload: Any = None, payload_source_override: str = "", result_path_override: str = "") -> dict[str, Any]:
    trendradar = safe_dict(raw_payload.get("trendradar"))
    if preloaded_payload is None:
        trendradar_payload, payload_source, result_path = resolve_trendradar_payload(raw_payload)
    else:
        trendradar_payload = preloaded_payload
        payload_source = payload_source_override or "inline_result"
        result_path = result_path_override
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    source_policy = {
        "channel": clean_text(trendradar.get("channel") or raw_payload.get("channel") or "shadow").lower(),
        "access_mode": clean_text(trendradar.get("access_mode") or raw_payload.get("access_mode") or "local_mcp"),
        "allow_observed_at_fallback": bool(trendradar.get("allow_observed_at_fallback", True)),
    }
    if source_policy["channel"] not in {"core", "shadow", "background"}:
        source_policy["channel"] = "shadow"
    return {
        "topic": clean_text(raw_payload.get("topic") or "TrendRadar bridge"),
        "analysis_time": analysis_time,
        "questions": clean_string_list(raw_payload.get("questions")),
        "use_case": clean_text(raw_payload.get("use_case") or "trendradar-bridge"),
        "source_preferences": clean_string_list(raw_payload.get("source_preferences")),
        "mode": clean_text(raw_payload.get("mode") or "generic"),
        "windows": clean_string_list(raw_payload.get("windows")),
        "claims": [item for item in safe_list(raw_payload.get("claims")) if isinstance(item, dict)],
        "market_relevance": clean_string_list(raw_payload.get("market_relevance")),
        "market_relevance_zh": clean_string_list(raw_payload.get("market_relevance_zh")),
        "expected_source_families": clean_string_list(raw_payload.get("expected_source_families")),
        "max_parallel_candidates": max(1, int(raw_payload.get("max_parallel_candidates", 1) or 1)),
        "source_policy": source_policy,
        "payload": trendradar_payload,
        "payload_source": payload_source,
        "result_path": result_path,
        "payload_metadata": payload_metadata(trendradar_payload),
    }


def prepare_trendradar_bridge(
    raw_payload: dict[str, Any],
    *,
    preloaded_payload: Any = None,
    payload_source_override: str = "",
    result_path_override: str = "",
) -> dict[str, Any]:
    request = normalize_request(
        raw_payload,
        preloaded_payload=preloaded_payload,
        payload_source_override=payload_source_override,
        result_path_override=result_path_override,
    )
    raw_items = flatten_result_items(request["payload"])
    candidates: list[dict[str, Any]] = []
    skipped_invalid = 0
    skipped_duplicates = 0
    seen: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        candidate, skip_reason = normalize_trendradar_item(item, request, index)
        if not candidate:
            skipped_invalid += 1
            continue
        key = dedupe_key(candidate)
        if key in seen:
            skipped_duplicates += 1
            continue
        seen.add(key)
        candidates.append(candidate)

    retrieval_request = {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": request["questions"],
        "use_case": request["use_case"],
        "source_preferences": request["source_preferences"],
        "mode": request["mode"],
        "windows": request["windows"],
        "claims": deepcopy(request["claims"]),
        "candidates": candidates,
        "market_relevance": request["market_relevance"],
        "market_relevance_zh": request["market_relevance_zh"],
        "expected_source_families": request["expected_source_families"],
        "max_parallel_candidates": request["max_parallel_candidates"],
    }
    result = {
        "request": {
            **{key: value for key, value in request.items() if key not in {"payload", "analysis_time"}},
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
        },
        "retrieval_request": retrieval_request,
        "import_summary": build_import_summary(
            candidates,
            raw_item_count=len(raw_items),
            skipped_invalid=skipped_invalid,
            skipped_duplicates=skipped_duplicates,
            payload_source=request["payload_source"],
            result_path=request["result_path"],
        ),
        "runner_summary": {
            "mode": "trendradar-bridge",
            "payload_source": request["payload_source"],
            "result_path": request["result_path"],
        },
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


def run_trendradar_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    result = prepare_trendradar_bridge(raw_payload)
    result["retrieval_result"] = run_news_index(result["retrieval_request"])
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_markdown_report",
    "flatten_result_items",
    "load_json",
    "normalize_request",
    "prepare_trendradar_bridge",
    "resolve_trendradar_payload",
    "run_trendradar_bridge",
    "write_json",
]
