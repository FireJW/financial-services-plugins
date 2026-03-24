#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, run_news_index, short_excerpt, slugify, write_json


COLLECTION_KEYS = ("findings", "items", "results", "sources", "entries", "records")
PLATFORM_KEYS = (
    "reddit",
    "x",
    "twitter",
    "bluesky",
    "truth_social",
    "truthsocial",
    "youtube",
    "tiktok",
    "instagram",
    "hacker_news",
    "hackernews",
    "hn",
    "polymarket",
    "web",
)
PLATFORM_ALIASES = {
    "twitter": "x",
    "tweet": "x",
    "tweets": "x",
    "truthsocial": "truth_social",
    "truth-social": "truth_social",
    "hackernews": "hacker_news",
    "hn": "hacker_news",
}
SOCIAL_PLATFORMS = {"x", "reddit", "bluesky", "truth_social", "youtube", "tiktok", "instagram"}
BRAND_BY_HOST_FRAGMENT = {
    "reuters.com": "Reuters",
    "apnews.com": "AP",
    "axios.com": "Axios",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "nytimes.com": "New York Times",
    "janes.com": "Janes",
    "usni.org": "USNI News",
    "defensenews.com": "Defense News",
    "polymarket.com": "Polymarket",
    "news.ycombinator.com": "Hacker News",
    "reddit.com": "Reddit",
    "x.com": "X",
    "twitter.com": "X",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "tiktok.com": "TikTok",
    "instagram.com": "Instagram",
    "bsky.app": "Bluesky",
    "truthsocial.com": "Truth Social",
}
RESULT_PATH_KEYS = ("last30days_result_path", "last30days_output_path", "result_path")
NESTED_RESULT_KEYS = ("last30days_result", "source_result", "result", "research_result")


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


def decode_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def normalize_key(value: Any) -> str:
    return clean_text(value).lower().replace(" ", "_").replace("-", "_")


def canonical_platform(value: Any) -> str:
    normalized = normalize_key(value)
    return PLATFORM_ALIASES.get(normalized, normalized)


def extract_first_json_object(text: str) -> dict[str, Any]:
    cleaned = text.lstrip("\ufeff\r\n\t ")
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Could not locate a JSON object in last30days output")


def load_last30days_payload(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    source_path = Path(clean_text(source)).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"last30days result file not found: {source_path}")
    try:
        return load_json(source_path)
    except Exception:
        return extract_first_json_object(decode_text_file(source_path))


def find_result_path(raw_payload: dict[str, Any]) -> str:
    for key in RESULT_PATH_KEYS:
        candidate = clean_text(raw_payload.get(key))
        if candidate:
            return candidate
    for key in NESTED_RESULT_KEYS:
        nested = safe_dict(raw_payload.get(key))
        for nested_key in RESULT_PATH_KEYS:
            candidate = clean_text(nested.get(nested_key))
            if candidate:
                return candidate
    return ""


def host_for(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ""


def brand_for_host(host: str) -> str:
    for fragment, brand in BRAND_BY_HOST_FRAGMENT.items():
        if fragment in host:
            return brand
    if host.endswith(".gov"):
        return "Government"
    if host.endswith(".mil"):
        return "US Military"
    return host.replace("www.", "") if host else ""


def title_platform(platform: str) -> str:
    labels = {
        "x": "X",
        "reddit": "Reddit",
        "bluesky": "Bluesky",
        "truth_social": "Truth Social",
        "youtube": "YouTube",
        "tiktok": "TikTok",
        "instagram": "Instagram",
        "hacker_news": "Hacker News",
        "polymarket": "Polymarket",
        "web": "Web",
    }
    return labels.get(platform, platform.replace("_", " ").title())


def iter_named_batches(value: Any, key_hint: str) -> list[tuple[str, list[dict[str, Any]]]]:
    batches: list[tuple[str, list[dict[str, Any]]]] = []
    if isinstance(value, list):
        batch = [item for item in value if isinstance(item, dict)]
        if batch:
            batches.append((key_hint, batch))
        return batches
    if not isinstance(value, dict):
        return batches

    for nested_key in COLLECTION_KEYS:
        batch = [item for item in safe_list(value.get(nested_key)) if isinstance(item, dict)]
        if batch:
            batches.append((key_hint, batch))
    return batches


def discover_input_batches(payload: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    batches: list[tuple[str, list[dict[str, Any]]]] = []
    for key in COLLECTION_KEYS:
        batches.extend(iter_named_batches(payload.get(key), key))
    for key in PLATFORM_KEYS:
        batches.extend(iter_named_batches(payload.get(key), canonical_platform(key)))
    for container_key in ("sources_by_platform", "platform_results", "by_platform"):
        for key, value in safe_dict(payload.get(container_key)).items():
            batches.extend(iter_named_batches(value, canonical_platform(key)))
    return batches


def guess_platform(item: dict[str, Any], batch_hint: str) -> str:
    for key in ("platform", "network", "source_platform", "channel"):
        platform = canonical_platform(item.get(key))
        if platform:
            return platform

    hinted_platform = canonical_platform(batch_hint)
    if hinted_platform in {
        "reddit",
        "x",
        "bluesky",
        "truth_social",
        "youtube",
        "tiktok",
        "instagram",
        "hacker_news",
        "polymarket",
    }:
        return hinted_platform

    host = host_for(clean_text(item.get("url") or item.get("post_url") or item.get("source_url")))
    if "x.com" in host or "twitter.com" in host:
        return "x"
    if "reddit.com" in host:
        return "reddit"
    if "bsky.app" in host:
        return "bluesky"
    if "truthsocial.com" in host:
        return "truth_social"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    if "instagram.com" in host:
        return "instagram"
    if "news.ycombinator.com" in host:
        return "hacker_news"
    if "polymarket.com" in host:
        return "polymarket"
    return hinted_platform or "web"


def infer_source_type(item: dict[str, Any], platform: str, url: str) -> str:
    explicit = normalize_key(item.get("source_type") or item.get("type"))
    if explicit and explicit not in PLATFORM_KEYS:
        return explicit

    if platform in SOCIAL_PLATFORMS:
        return "social"
    if platform == "hacker_news":
        return "community"
    if platform == "polymarket":
        return "market_rumor"

    host = host_for(url)
    if host.endswith(".gov") or host.endswith(".mil"):
        return "government_release"
    if any(fragment in host for fragment in ("reuters.com", "apnews.com")):
        return "wire"
    if any(fragment in host for fragment in ("axios.com", "bloomberg.com", "wsj.com", "ft.com", "nytimes.com")):
        return "major_news"
    if any(fragment in host for fragment in ("janes.com", "usni.org", "defensenews.com")):
        return "specialist_outlet"
    return "blog"


def build_source_name(item: dict[str, Any], platform: str, url: str, source_type: str) -> str:
    explicit = clean_text(item.get("source_name") or item.get("source") or item.get("outlet") or item.get("site_name"))
    if explicit:
        return explicit

    author_handle = clean_text(item.get("author_handle") or item.get("handle") or item.get("username"))
    author_name = clean_text(item.get("author_display_name") or item.get("author") or item.get("channel_name"))
    if platform in SOCIAL_PLATFORMS and (author_handle or author_name):
        label = title_platform(platform)
        if author_handle:
            return f"{label} @{author_handle.lstrip('@')}"
        return f"{label} {author_name}"

    host = host_for(url)
    brand = brand_for_host(host)
    if brand:
        return brand

    if source_type == "government_release":
        return "Government release"
    return title_platform(platform or "web")


def guess_media_type(path_or_url: str) -> str:
    target = clean_text(path_or_url)
    suffix = Path(target).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return f"image/{suffix[1:]}" if suffix != ".svg" else "image/svg+xml"
    if suffix in {".mp4", ".webm", ".mov"}:
        return f"video/{suffix[1:]}"
    return ""


def append_artifact(manifest: list[dict[str, Any]], role: str, path: str, source_url: str, media_type: str) -> None:
    normalized = {
        "role": clean_text(role),
        "path": clean_text(path),
        "source_url": clean_text(source_url),
        "media_type": clean_text(media_type),
    }
    if not any(normalized.values()):
        return
    key = (normalized["role"], normalized["path"], normalized["source_url"])
    if any((item.get("role", ""), item.get("path", ""), item.get("source_url", "")) == key for item in manifest):
        return
    manifest.append(normalized)


def normalize_media_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for media in safe_list(item.get("media_items")):
        if not isinstance(media, dict):
            continue
        source_url = clean_text(media.get("source_url") or media.get("url") or media.get("image_url"))
        local_artifact_path = clean_text(media.get("local_artifact_path") or media.get("path") or media.get("image_path"))
        entry = {
            "source_url": source_url,
            "local_artifact_path": local_artifact_path,
            "ocr_text_raw": clean_text(media.get("ocr_text_raw")),
            "ocr_summary": clean_text(media.get("ocr_summary") or media.get("summary")),
            "ocr_source": clean_text(media.get("ocr_source") or "image"),
            "ocr_confidence": media.get("ocr_confidence", 0.0),
            "image_relevance_to_post": clean_text(media.get("image_relevance_to_post") or media.get("relevance")),
        }
        if any(clean_text(value) for key, value in entry.items() if key != "ocr_confidence") or entry["ocr_confidence"]:
            normalized.append(entry)
    return normalized


def build_artifact_manifest(item: dict[str, Any], url: str, media_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    manifest: list[dict[str, Any]] = []
    for artifact in safe_list(item.get("artifact_manifest")):
        if not isinstance(artifact, dict):
            continue
        append_artifact(
            manifest,
            clean_text(artifact.get("role")),
            clean_text(artifact.get("path")),
            clean_text(artifact.get("source_url")),
            clean_text(artifact.get("media_type")),
        )

    root_post_screenshot_path = clean_text(item.get("root_post_screenshot_path") or item.get("screenshot_path"))
    if root_post_screenshot_path:
        append_artifact(manifest, "root_post_screenshot", root_post_screenshot_path, url, guess_media_type(root_post_screenshot_path))

    for index, media in enumerate(media_items, start=1):
        append_artifact(
            manifest,
            f"attached_media_{index}",
            clean_text(media.get("local_artifact_path")),
            clean_text(media.get("source_url")),
            guess_media_type(clean_text(media.get("local_artifact_path")) or clean_text(media.get("source_url"))),
        )

    if clean_text(item.get("image_path")) or clean_text(item.get("image_url")):
        append_artifact(
            manifest,
            "attached_media_primary",
            clean_text(item.get("image_path")),
            clean_text(item.get("image_url")),
            guess_media_type(clean_text(item.get("image_path")) or clean_text(item.get("image_url"))),
        )
    return manifest, root_post_screenshot_path


def summarize_text_layers(item: dict[str, Any]) -> tuple[str, str, str]:
    post_summary = clean_text(item.get("post_summary") or item.get("summary"))
    media_summary = clean_text(item.get("media_summary") or item.get("image_summary") or item.get("ocr_summary"))
    combined_summary = clean_text(item.get("combined_summary"))
    if not combined_summary:
        if post_summary and media_summary:
            combined_summary = f"{post_summary} Image notes: {media_summary}"
        else:
            combined_summary = post_summary or media_summary
    return post_summary, media_summary, combined_summary


def fallback_text_excerpt(item: dict[str, Any], combined_summary: str, post_summary: str) -> str:
    return short_excerpt(
        combined_summary
        or post_summary
        or clean_text(item.get("text_excerpt"))
        or clean_text(item.get("excerpt"))
        or clean_text(item.get("snippet"))
        or clean_text(item.get("why_relevant"))
        or clean_text(item.get("question"))
        or clean_text(item.get("price_movement"))
        or clean_text(item.get("post_text_raw"))
        or clean_text(item.get("text"))
        or clean_text(item.get("content"))
        or clean_text(item.get("body"))
        or clean_text(item.get("title")),
        limit=240,
    )


def normalize_claim_states(item: dict[str, Any], claim_ids: list[str]) -> dict[str, Any]:
    raw_states = safe_dict(item.get("claim_states") or item.get("stance_by_claim"))
    single_state = clean_text(item.get("claim_state"))
    if not raw_states and single_state and claim_ids:
        return {claim_id: single_state for claim_id in claim_ids}
    return {claim_id: raw_states.get(claim_id, "support") for claim_id in claim_ids if raw_states.get(claim_id)}


def normalize_candidate(item: dict[str, Any], batch_hint: str, request: dict[str, Any], index: int) -> dict[str, Any] | None:
    url = clean_text(item.get("url") or item.get("post_url") or item.get("source_url") or item.get("hn_url"))
    platform = guess_platform(item, batch_hint)
    source_type = infer_source_type(item, platform, url)
    source_name = build_source_name(item, platform, url, source_type)
    source_id_seed = clean_text(item.get("source_id") or item.get("id") or item.get("post_id") or item.get("status_id"))
    source_id = source_id_seed or slugify(f"{platform}-{source_name}-{index}", f"last30days-{index:02d}")
    published_at = parse_datetime(
        item.get("published_at") or item.get("posted_at") or item.get("created_at") or item.get("timestamp") or item.get("date"),
        fallback=request["analysis_time"],
    )
    observed_at = parse_datetime(
        item.get("observed_at") or item.get("collected_at") or item.get("scraped_at"),
        fallback=request["generated_at"] or request["analysis_time"],
    )
    claim_ids = clean_string_list(item.get("claim_ids"))
    request_claim_ids = [clean_text(claim.get("claim_id")) for claim in request["claims"] if clean_text(claim.get("claim_id"))]
    if not claim_ids and len(request_claim_ids) == 1:
        claim_ids = request_claim_ids
    media_items = normalize_media_items(item)
    artifact_manifest, root_post_screenshot_path = build_artifact_manifest(item, url, media_items)
    post_summary, media_summary, combined_summary = summarize_text_layers(item)
    post_text_raw = clean_text(item.get("post_text_raw") or item.get("raw_text"))
    post_text_source = clean_text(item.get("post_text_source") or ("imported" if post_text_raw else ""))
    text_excerpt = fallback_text_excerpt(item, combined_summary, post_summary)
    access_mode = normalize_key(item.get("access_mode") or ("blocked" if item.get("blocked") else "public")) or "public"
    if access_mode not in {"public", "browser_session", "blocked"}:
        access_mode = "public"
    why_relevant = clean_text(item.get("why_relevant"))
    question = clean_text(item.get("question"))
    discovery_reason = clean_text(item.get("discovery_reason") or why_relevant or f"Imported from last30days {title_platform(platform)} discovery")
    candidate = {
        "source_id": source_id,
        "source_name": source_name or f"last30days-source-{index:02d}",
        "platform": platform,
        "source_type": source_type,
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": normalize_claim_states(item, claim_ids),
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "vessel_ids": clean_string_list(item.get("vessel_ids")),
        "text_excerpt": text_excerpt,
        "position_hint": deepcopy(item.get("position_hint")),
        "geo_hint": deepcopy(item.get("geo_hint")),
        "channel": "shadow",
        "access_mode": access_mode,
        "artifact_manifest": artifact_manifest,
        "post_text_raw": post_text_raw,
        "post_text_source": post_text_source,
        "post_text_confidence": item.get("post_text_confidence", 0.0),
        "root_post_screenshot_path": root_post_screenshot_path,
        "thread_posts": deepcopy(item.get("thread_posts")) if isinstance(item.get("thread_posts"), list) else [],
        "media_items": media_items,
        "post_summary": post_summary,
        "media_summary": media_summary,
        "combined_summary": combined_summary,
        "discovery_reason": discovery_reason,
        "question": question,
        "why_relevant": why_relevant,
        "origin": "last30days",
        "crawl_notes": deepcopy(item.get("crawl_notes")) if isinstance(item.get("crawl_notes"), list) else [],
    }
    if not any([candidate["source_name"], candidate["url"], candidate["text_excerpt"], candidate["post_text_raw"]]):
        return None
    return candidate


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            clean_text(candidate.get("url")) or clean_text(candidate.get("source_name")),
            clean_text(candidate.get("published_at")),
            "|".join(sorted(clean_string_list(candidate.get("claim_ids")))),
            clean_text(candidate.get("text_excerpt")),
        )
        if key not in kept:
            kept[key] = candidate
            continue
        existing = kept[key]
        if len(clean_text(candidate.get("combined_summary"))) > len(clean_text(existing.get("combined_summary"))):
            existing["combined_summary"] = candidate.get("combined_summary", "")
        if clean_text(candidate.get("root_post_screenshot_path")) and not clean_text(existing.get("root_post_screenshot_path")):
            existing["root_post_screenshot_path"] = candidate.get("root_post_screenshot_path", "")
        if candidate.get("artifact_manifest"):
            seen = {
                (item.get("role", ""), item.get("path", ""), item.get("source_url", "")): item
                for item in safe_list(existing.get("artifact_manifest"))
            }
            for artifact in safe_list(candidate.get("artifact_manifest")):
                key = (artifact.get("role", ""), artifact.get("path", ""), artifact.get("source_url", ""))
                seen[key] = artifact
            existing["artifact_manifest"] = list(seen.values())
        if candidate.get("media_items") and not existing.get("media_items"):
            existing["media_items"] = deepcopy(candidate.get("media_items", []))
        if candidate.get("thread_posts") and not existing.get("thread_posts"):
            existing["thread_posts"] = deepcopy(candidate.get("thread_posts", []))
    return list(kept.values())


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    nested_payload = {}
    for key in NESTED_RESULT_KEYS:
        nested_payload = safe_dict(raw_payload.get(key))
        if nested_payload:
            break
    result_path = find_result_path(raw_payload)
    loaded_payload = load_last30days_payload(result_path) if result_path else {}
    payload = loaded_payload or nested_payload or raw_payload
    analysis_time = parse_datetime(
        raw_payload.get("analysis_time") or payload.get("analysis_time") or payload.get("generated_at"),
        fallback=now_utc(),
    ) or now_utc()
    generated_at = parse_datetime(payload.get("generated_at"), fallback=analysis_time)
    topic = clean_text(raw_payload.get("topic") or payload.get("topic") or payload.get("query") or payload.get("subject")) or "last30days-topic"
    return {
        "topic": topic,
        "analysis_time": analysis_time,
        "generated_at": generated_at,
        "questions": clean_string_list(raw_payload.get("questions") or payload.get("questions")),
        "use_case": clean_text(raw_payload.get("use_case") or payload.get("use_case")) or "last30days-bridge",
        "source_preferences": clean_string_list(raw_payload.get("source_preferences") or payload.get("source_preferences")) or ["social", "major_news", "official"],
        "mode": "crisis" if clean_text(raw_payload.get("mode") or payload.get("mode")).lower() == "crisis" else "generic",
        "windows": clean_string_list(raw_payload.get("windows") or payload.get("windows")) or ["10m", "1h", "6h", "24h"],
        "claims": [item for item in safe_list(raw_payload.get("claims") or payload.get("claims")) if isinstance(item, dict)],
        "market_relevance": clean_string_list(raw_payload.get("market_relevance") or payload.get("market_relevance")),
        "expected_source_families": clean_string_list(raw_payload.get("expected_source_families") or payload.get("expected_source_families")),
        "max_imported_items": max(1, int(raw_payload.get("max_imported_items", payload.get("max_imported_items", 50)) or 1)),
        "result_path": result_path,
        "payload": payload,
    }


def build_import_summary(candidates: list[dict[str, Any]], total_raw_items: int, batch_labels: list[str]) -> dict[str, Any]:
    platform_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    blocked_count = 0
    with_claims = 0
    with_artifacts = 0

    for item in candidates:
        host = host_for(clean_text(item.get("url")))
        platform = guess_platform(item, brand_for_host(host) or "web")
        platform_counts[platform or "web"] += 1
        source_type_counts[clean_text(item.get("source_type")) or "unknown"] += 1
        if clean_text(item.get("access_mode")) == "blocked":
            blocked_count += 1
        if safe_list(item.get("claim_ids")):
            with_claims += 1
        if clean_text(item.get("root_post_screenshot_path")) or safe_list(item.get("artifact_manifest")):
            with_artifacts += 1

    return {
        "raw_item_count": total_raw_items,
        "imported_candidate_count": len(candidates),
        "batch_labels": batch_labels,
        "platform_counts": dict(platform_counts),
        "source_type_counts": dict(source_type_counts),
        "blocked_count": blocked_count,
        "with_claim_links": with_claims,
        "with_artifacts": with_artifacts,
        "default_channel_policy": "shadow_or_background_only",
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    summary = safe_dict(result.get("import_summary"))
    retrieval_result = safe_dict(result.get("retrieval_result"))
    lines = [
        f"# Last30Days Bridge Report: {request.get('topic', 'last30days-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
        f"Imported findings: {summary.get('imported_candidate_count', 0)} of {summary.get('raw_item_count', 0)} raw item(s)",
        f"Default channel policy: {summary.get('default_channel_policy', 'shadow_or_background_only')}",
        "",
        "## Import Summary",
        f"- Batch labels: {json.dumps(summary.get('batch_labels', []), ensure_ascii=False)}",
        f"- Platform counts: {json.dumps(summary.get('platform_counts', {}), ensure_ascii=False)}",
        f"- Source type counts: {json.dumps(summary.get('source_type_counts', {}), ensure_ascii=False)}",
        f"- Blocked imports: {summary.get('blocked_count', 0)}",
        f"- Claim-linked imports: {summary.get('with_claim_links', 0)}",
        f"- Imports with artifacts: {summary.get('with_artifacts', 0)}",
    ]
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def run_last30days_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    batches = discover_input_batches(request["payload"])
    raw_items = sum(len(batch) for _, batch in batches)
    candidates: list[dict[str, Any]] = []
    for batch_hint, items in batches:
        for item in items:
            candidate = normalize_candidate(item, batch_hint, request, len(candidates) + 1)
            if candidate:
                candidates.append(candidate)
    candidates = dedupe_candidates(candidates)[: request["max_imported_items"]]

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
        "expected_source_families": request["expected_source_families"],
    }
    retrieval_result = run_news_index(retrieval_request)
    result = {
        "request": {
            "topic": request["topic"],
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "generated_at": isoformat_or_blank(request["generated_at"]),
            "questions": request["questions"],
            "use_case": request["use_case"],
            "mode": request["mode"],
            "windows": request["windows"],
            "max_imported_items": request["max_imported_items"],
            "result_path": request["result_path"],
        },
        "import_summary": build_import_summary(candidates, raw_items, [label for label, _ in batches]),
        "retrieval_request": retrieval_request,
        "retrieval_result": retrieval_result,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_markdown_report",
    "decode_text_file",
    "extract_first_json_object",
    "load_json",
    "load_last30days_payload",
    "run_last30days_bridge",
    "write_json",
]
