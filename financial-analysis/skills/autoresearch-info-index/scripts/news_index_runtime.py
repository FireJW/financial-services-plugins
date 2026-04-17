#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any


WINDOW_MINUTES = {
    "10m": 10,
    "1h": 60,
    "6h": 360,
    "24h": 1440,
}

PROMOTABLE_TRACKER_TYPES = {"public_ship_tracker", "public_ais"}
SUPPORT_STATES = {"support", "supported", "confirm", "confirmed", "true", "yes"}
CONTRADICT_STATES = {"contradict", "contradicted", "deny", "denied", "false", "refute"}

SOURCE_TIER_BY_TYPE = {
    "official": 0,
    "official_release": 0,
    "official_statement": 0,
    "government": 0,
    "government_release": 0,
    "wire": 1,
    "major_news": 1,
    "company_statement": 1,
    "company_filing": 1,
    "exchange_filing": 1,
    "public_ship_tracker": 2,
    "public_ais": 2,
    "specialist_outlet": 2,
    "research_note": 2,
    "analysis": 2,
    "blog": 2,
    "social": 3,
}

BASE_CHANNEL_BY_TYPE = {
    "official": "core",
    "official_release": "core",
    "official_statement": "core",
    "government": "core",
    "government_release": "core",
    "wire": "core",
    "major_news": "background",
    "company_statement": "core",
    "company_filing": "core",
    "exchange_filing": "core",
    "public_ship_tracker": "shadow",
    "public_ais": "shadow",
    "specialist_outlet": "shadow",
    "research_note": "shadow",
    "analysis": "shadow",
    "blog": "shadow",
    "social": "shadow",
}

SOURCE_RANK_BASE = {
    "official": 120,
    "official_release": 120,
    "official_statement": 120,
    "government": 120,
    "government_release": 120,
    "wire": 85,
    "major_news": 85,
    "company_statement": 90,
    "company_filing": 90,
    "exchange_filing": 90,
    "public_ship_tracker": 80,
    "public_ais": 80,
    "specialist_outlet": 40,
    "research_note": 45,
    "analysis": 45,
    "blog": 40,
    "social": 55,
}

SOURCE_FAMILY_BY_TYPE = {
    "official": "government",
    "official_release": "government",
    "official_statement": "government",
    "government": "government",
    "government_release": "government",
    "wire": "wire",
    "major_news": "major_news",
    "specialist_outlet": "major_news",
    "company_statement": "company",
    "company_filing": "company",
    "exchange_filing": "exchange",
    "public_ship_tracker": "public_ship_tracker",
    "public_ais": "public_ais",
    "research_note": "analysis",
    "analysis": "analysis",
    "blog": "blog",
    "social": "social",
}

RECENCY_BONUS_BY_BUCKET = {
    "0-10m": 35,
    "10-60m": 5,
    "1-6h": 0,
    "6-24h": -2,
    ">24h": -5,
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must decode to a JSON object")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_datetime(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return fallback
    else:
        text = clean_text(value)
        if not text:
            return fallback
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                try:
                    parsed = datetime.fromisoformat(text + "T00:00:00+00:00")
                except ValueError:
                    return fallback
            else:
                try:
                    parsed = parsedate_to_datetime(text)
                except (TypeError, ValueError, IndexError):
                    return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def isoformat_or_blank(value: datetime | None) -> str:
    return value.astimezone(UTC).isoformat() if isinstance(value, datetime) else ""


def slugify(value: Any, fallback: str = "item") -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def short_excerpt(value: Any, limit: int = 180) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    clipped = text[: limit + 1]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    clipped = clipped.rstrip(".,;:!?，。；：、")
    return clipped + "..."


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def source_type_tier(source_type: str) -> int:
    return SOURCE_TIER_BY_TYPE.get(source_type, 3)


def source_type_channel(source_type: str) -> str:
    return BASE_CHANNEL_BY_TYPE.get(source_type, "shadow")


def source_type_family(source_type: str) -> str:
    return SOURCE_FAMILY_BY_TYPE.get(source_type, "other")


def age_minutes(analysis_time: datetime, published_at: datetime | None, observed_at: datetime | None) -> float:
    anchor = published_at or observed_at or analysis_time
    return max(0.0, (analysis_time - anchor).total_seconds() / 60.0)


def age_bucket(minutes: float) -> str:
    if minutes <= 10:
        return "0-10m"
    if minutes <= 60:
        return "10-60m"
    if minutes <= 360:
        return "1-6h"
    if minutes <= 1440:
        return "6-24h"
    return ">24h"


def format_age_label(minutes: float) -> str:
    if minutes < 60:
        return f"{int(round(minutes))}m"
    if minutes < 1440:
        hours = minutes / 60.0
        return f"{hours:.1f}h" if hours < 10 else f"{int(round(hours))}h"
    return f"{minutes / 1440.0:.1f}d"


def source_rank_score(source_type: str, recency_bucket: str) -> int:
    base = SOURCE_RANK_BASE.get(source_type, 45)
    return base + RECENCY_BONUS_BY_BUCKET.get(recency_bucket, 0)


def normalize_artifact_manifest(value: Any, *, default_role: str = "") -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        role = clean_text(item.get("role") or item.get("kind") or default_role)
        path = clean_text(item.get("path") or item.get("local_artifact_path"))
        source_url = clean_text(item.get("source_url") or item.get("url"))
        media_type = clean_text(item.get("media_type"))
        caption = clean_text(item.get("caption"))
        normalized = {
            "role": role,
            "path": path,
            "source_url": source_url,
            "media_type": media_type,
        }
        if caption:
            normalized["caption"] = caption
        artifacts.append(normalized)
    return artifacts


def strip_html_tags(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", html))


def extract_meta_content(html: str, *names: str) -> str:
    for name in names:
        pattern = re.compile(
            rf"<meta[^>]+(?:property|name)\s*=\s*[\"']{re.escape(name)}[\"'][^>]+content\s*=\s*[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        )
        match = pattern.search(html)
        if match:
            return clean_text(unescape(match.group(1)))
    return ""


def fetch_public_page_hints(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        try:
            body = response.read(1_000_000)
        except TypeError:
            # Some test doubles only expose read() without a size parameter.
            body = response.read()
        html = body.decode("utf-8", errors="ignore")
        final_url = clean_text(response.geturl() if hasattr(response, "geturl") else url) or url

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = extract_meta_content(html, "og:title", "twitter:title") or clean_text(title_match.group(1) if title_match else "")
    description = extract_meta_content(html, "og:description", "description", "twitter:description")
    paragraph_match = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
    body_text = clean_text(strip_html_tags(paragraph_match.group(1) if paragraph_match else html))
    text_excerpt = short_excerpt(description or body_text or title, limit=240)
    image_url = extract_meta_content(html, "og:image", "twitter:image")
    image_alt = extract_meta_content(html, "og:image:alt", "twitter:image:alt")
    artifact_manifest: list[dict[str, Any]] = []
    if image_url:
        artifact_manifest.append(
            {
                "role": "post_media",
                "path": "",
                "source_url": urllib.parse.urljoin(final_url, image_url),
                "media_type": "image",
            }
        )
    return {
        "final_url": final_url,
        "title": title,
        "text_excerpt": text_excerpt,
        "post_summary": short_excerpt(description or title or body_text, limit=180),
        "media_summary": clean_text(image_alt),
        "artifact_manifest": artifact_manifest,
    }


def build_page_hints(candidate: dict[str, Any]) -> dict[str, Any]:
    cached = safe_dict(candidate.get("public_page_hints") or candidate.get("page_hints"))
    if cached:
        return cached
    url = clean_text(candidate.get("url"))
    if clean_text(candidate.get("access_mode")) == "blocked" or not url.startswith(("http://", "https://")):
        return {}
    needs_hints = not safe_list(candidate.get("artifact_manifest")) or not clean_text(candidate.get("media_summary"))
    if not needs_hints:
        return {}
    try:
        return safe_dict(fetch_public_page_hints(url))
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        return {}


def normalize_claim_state(value: Any) -> str:
    state = clean_text(value).lower()
    if state in SUPPORT_STATES:
        return "support"
    if state in CONTRADICT_STATES:
        return "contradict"
    return state


def build_claim_text_map(request: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in safe_list(request.get("claims")):
        if not isinstance(item, dict):
            continue
        claim_id = clean_text(item.get("claim_id"))
        claim_text = clean_text(item.get("claim_text"))
        if claim_id and claim_text:
            mapping[claim_id] = claim_text
    return mapping


def normalize_observation(candidate: dict[str, Any], claim_text_map: dict[str, str], analysis_time: datetime) -> dict[str, Any]:
    source_type = clean_text(candidate.get("source_type")).lower() or "analysis"
    published_at = parse_datetime(candidate.get("published_at"), fallback=None)
    observed_at = parse_datetime(candidate.get("observed_at"), fallback=published_at)
    access_mode = clean_text(candidate.get("access_mode")) or "public"
    candidate_channel = clean_text(candidate.get("channel")).lower()
    if candidate_channel not in {"core", "shadow", "background"}:
        candidate_channel = source_type_channel(source_type)
    page_hints = build_page_hints(candidate)

    artifact_manifest = normalize_artifact_manifest(candidate.get("artifact_manifest")) or normalize_artifact_manifest(
        page_hints.get("artifact_manifest")
    )
    root_post_screenshot_path = clean_text(candidate.get("root_post_screenshot_path"))
    if not root_post_screenshot_path:
        for item in artifact_manifest:
            role = clean_text(item.get("role")).lower()
            path = clean_text(item.get("path"))
            if path and "screenshot" in role:
                root_post_screenshot_path = path
                break

    text_excerpt = clean_text(candidate.get("text_excerpt"))
    if not text_excerpt and access_mode != "blocked":
        text_excerpt = clean_text(page_hints.get("text_excerpt"))

    claim_states = {
        claim_id: normalize_claim_state(state)
        for claim_id, state in safe_dict(candidate.get("claim_states")).items()
        if clean_text(claim_id)
    }
    claim_ids = clean_string_list(candidate.get("claim_ids") or list(claim_states))
    observation_age = age_minutes(analysis_time, published_at, observed_at)
    observation_bucket = age_bucket(observation_age)

    return {
        "source_id": clean_text(candidate.get("source_id")) or slugify(candidate.get("url"), "source"),
        "source_name": clean_text(candidate.get("source_name")) or "Unknown Source",
        "source_type": source_type,
        "source_tier": source_type_tier(source_type),
        "origin": clean_text(candidate.get("origin")),
        "_base_channel": source_type_channel(source_type),
        "channel": candidate_channel,
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": clean_text(candidate.get("url")),
        "claim_ids": claim_ids,
        "entity_ids": clean_string_list(candidate.get("entity_ids")),
        "vessel_ids": clean_string_list(candidate.get("vessel_ids")),
        "text_excerpt": text_excerpt,
        "position_hint": safe_dict(candidate.get("position_hint")) or None,
        "geo_hint": safe_dict(candidate.get("geo_hint")) or None,
        "access_mode": access_mode,
        "rank_score": source_rank_score(source_type, observation_bucket),
        "recency_bucket": observation_bucket,
        "age_minutes": round(observation_age, 1),
        "age_label": format_age_label(observation_age),
        "claim_states": claim_states,
        "claim_texts": {claim_id: clean_text(claim_text_map.get(claim_id)) for claim_id in claim_ids if claim_id in claim_text_map},
        "artifact_manifest": artifact_manifest,
        "x_post_record": safe_dict(candidate.get("x_post_record")),
        "post_text_raw": clean_text(candidate.get("post_text_raw")),
        "post_text_source": clean_text(candidate.get("post_text_source")),
        "post_text_confidence": float(candidate.get("post_text_confidence") or 0.0),
        "root_post_screenshot_path": root_post_screenshot_path,
        "thread_posts": safe_list(candidate.get("thread_posts")),
        "media_items": safe_list(candidate.get("media_items")),
        "raw_metadata": deepcopy(safe_dict(candidate.get("raw_metadata"))),
        "agent_reach_channel": clean_text(candidate.get("agent_reach_channel")),
        "post_summary": clean_text(candidate.get("post_summary") or page_hints.get("post_summary")),
        "media_summary": clean_text(candidate.get("media_summary") or page_hints.get("media_summary")),
        "combined_summary": clean_text(candidate.get("combined_summary")),
        "discovery_reason": clean_text(candidate.get("discovery_reason")),
        "crawl_notes": clean_string_list(candidate.get("crawl_notes")),
        "public_page_hints": page_hints,
    }


def promoted_tracker_source_ids(observations: list[dict[str, Any]]) -> set[str]:
    support_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        for claim_id in observation.get("claim_ids", []):
            if observation.get("claim_states", {}).get(claim_id) == "support":
                support_by_claim[claim_id].append(observation)

    promoted: set[str] = set()
    for support_sources in support_by_claim.values():
        core_support = [item for item in support_sources if item.get("_base_channel") == "core"]
        tracker_support = [
            item
            for item in support_sources
            if item.get("source_type") in PROMOTABLE_TRACKER_TYPES and item.get("access_mode") != "blocked"
        ]
        if core_support and len({item["source_id"] for item in tracker_support}) >= 2:
            promoted.update(item["source_id"] for item in tracker_support)
    return promoted


def apply_channel_promotions(observations: list[dict[str, Any]]) -> None:
    promoted_sources = promoted_tracker_source_ids(observations)
    for observation in observations:
        if observation["source_id"] in promoted_sources and observation["source_type"] in PROMOTABLE_TRACKER_TYPES:
            observation["channel"] = "core"


def observation_sort_key(observation: dict[str, Any]) -> tuple[int, float, str]:
    return (
        int(observation.get("rank_score", 0)),
        -float(observation.get("age_minutes", 0.0)),
        clean_text(observation.get("source_name")).lower(),
    )


def build_claim_ledger(observations: list[dict[str, Any]], claim_text_map: dict[str, str]) -> list[dict[str, Any]]:
    support_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contradict_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for observation in observations:
        for claim_id in observation.get("claim_ids", []):
            state = observation.get("claim_states", {}).get(claim_id)
            if state == "support":
                support_map[claim_id].append(observation)
            elif state == "contradict":
                contradict_map[claim_id].append(observation)

    ledger: list[dict[str, Any]] = []
    for claim_id, claim_text in claim_text_map.items():
        supporting = support_map.get(claim_id, [])
        contradicting = contradict_map.get(claim_id, [])
        support_core = sum(1 for item in supporting if item.get("channel") == "core")
        contradict_core = sum(1 for item in contradicting if item.get("channel") == "core")

        if contradicting and not supporting:
            status = "denied"
        elif supporting and contradicting:
            if contradict_core >= support_core and contradict_core > 0:
                status = "denied"
            elif support_core > contradict_core:
                status = "confirmed"
            elif len(contradicting) >= len(supporting):
                status = "denied"
            else:
                status = "unclear"
        elif supporting:
            status = "confirmed" if support_core > 0 else "unclear"
        else:
            status = "inferred"

        timestamps = [
            parse_datetime(item.get("published_at"), fallback=None) or parse_datetime(item.get("observed_at"), fallback=None)
            for item in supporting + contradicting
        ]
        valid_timestamps = [item for item in timestamps if isinstance(item, datetime)]
        ledger.append(
            {
                "claim_id": claim_id,
                "claim_text": claim_text,
                "status": status,
                "supporting_sources": [item["source_id"] for item in supporting],
                "contradicting_sources": [item["source_id"] for item in contradicting],
                "last_updated_at": isoformat_or_blank(max(valid_timestamps)) if valid_timestamps else "",
                "promotion_state": "core" if support_core > 0 else "shadow",
            }
        )

    ledger.sort(key=lambda item: item["claim_id"])
    return ledger


def build_claim_sections(claim_ledger: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    confirmed = [item for item in claim_ledger if item.get("status") == "confirmed"]
    not_confirmed = [item for item in claim_ledger if item.get("status") in {"denied", "unclear", "not_confirmed"}]
    inference_only = [item for item in claim_ledger if item.get("status") == "inferred"]
    return confirmed, not_confirmed, inference_only


def build_freshness_panel(observations: list[dict[str, Any]], windows: list[str]) -> list[dict[str, Any]]:
    panel: list[dict[str, Any]] = []
    for window in windows:
        threshold = WINDOW_MINUTES.get(window)
        if threshold is None:
            continue
        bucket_items = [item for item in observations if float(item.get("age_minutes", threshold + 1)) <= threshold]
        panel.append(
            {
                "window": window,
                "count": len(bucket_items),
                "core_count": sum(1 for item in bucket_items if item.get("channel") == "core" and item.get("access_mode") != "blocked"),
                "shadow_count": sum(1 for item in bucket_items if item.get("channel") == "shadow" and item.get("access_mode") != "blocked"),
                "blocked_count": sum(1 for item in bucket_items if item.get("access_mode") == "blocked"),
            }
        )
    return panel


def build_source_layer_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_channel = Counter(item.get("channel", "") for item in observations)
    by_tier = Counter(str(item.get("source_tier", "")) for item in observations)
    by_access_mode = Counter(item.get("access_mode", "") for item in observations)
    return {
        "by_channel": dict(by_channel),
        "by_tier": dict(by_tier),
        "by_access_mode": dict(by_access_mode),
    }


def build_source_artifacts(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for observation in observations:
        if not (
            observation.get("artifact_manifest")
            or observation.get("root_post_screenshot_path")
            or observation.get("media_summary")
            or observation.get("post_text_raw")
        ):
            continue
        artifacts.append(
            {
                "source_name": observation.get("source_name", ""),
                "source_tier": observation.get("source_tier", 3),
                "origin": observation.get("origin", ""),
                "channel": observation.get("channel", ""),
                "access_mode": observation.get("access_mode", ""),
                "url": observation.get("url", ""),
                "post_text_raw": observation.get("post_text_raw", ""),
                "post_text_source": observation.get("post_text_source", ""),
                "post_text_confidence": observation.get("post_text_confidence", 0.0),
                "post_summary": observation.get("post_summary", ""),
                "media_summary": observation.get("media_summary", ""),
                "combined_summary": observation.get("combined_summary", ""),
                "root_post_screenshot_path": observation.get("root_post_screenshot_path", ""),
                "artifact_manifest": observation.get("artifact_manifest", []),
            }
        )
    return artifacts


def build_negotiation_status_timeline(observations: list[dict[str, Any]], claim_text_map: dict[str, str]) -> list[dict[str, Any]]:
    relevant_claim_ids = {
        claim_id
        for claim_id, claim_text in claim_text_map.items()
        if any(token in claim_id for token in ("deal", "negotiation")) or any(token in claim_text.lower() for token in ("deal", "settlement", "ceasefire", "contact"))
    }
    rows: list[dict[str, Any]] = []
    for observation in observations:
        if not any(claim_id in relevant_claim_ids for claim_id in observation.get("claim_ids", [])):
            continue
        timestamp = clean_text(observation.get("published_at") or observation.get("observed_at"))
        if not timestamp:
            continue
        rows.append(
            {
                "timestamp": timestamp,
                "source_name": observation.get("source_name", ""),
                "channel": observation.get("channel", ""),
                "text_excerpt": observation.get("text_excerpt", ""),
            }
        )
    rows.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return rows[:5]


def build_vessel_movement_table(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for observation in observations:
        position_hint = safe_dict(observation.get("position_hint"))
        vessel_ids = clean_string_list(observation.get("vessel_ids"))
        if not position_hint or not vessel_ids:
            continue
        key = ("|".join(vessel_ids), clean_text(position_hint.get("last_public_location")))
        if key in seen:
            continue
        seen.add(key)
        eta_low = safe_int(position_hint.get("eta_hours_low"))
        eta_high = safe_int(position_hint.get("eta_hours_high"))
        table.append(
            {
                "vessel_ids": vessel_ids,
                "last_public_location": clean_text(position_hint.get("last_public_location")),
                "timestamp": clean_text(observation.get("published_at") or observation.get("observed_at")),
                "eta_range": f"{eta_low}-{eta_high}h" if eta_low and eta_high else "",
                "source_name": observation.get("source_name", ""),
            }
        )
    return table


def build_conflict_matrix(claim_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": item.get("claim_id", ""),
            "status": item.get("status", ""),
            "support_count": len(item.get("supporting_sources", [])),
            "contradiction_count": len(item.get("contradicting_sources", [])),
            "promotion_state": item.get("promotion_state", ""),
        }
        for item in claim_ledger
    ]


def build_background_only(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for observation in observations:
        if observation.get("channel") != "background":
            continue
        rows.append(
            {
                "source_name": observation.get("source_name", ""),
                "age": observation.get("age_label", ""),
                "text_excerpt": observation.get("text_excerpt", ""),
            }
        )
    return rows


def build_live_tape(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in observations:
        if observation.get("channel") != "shadow" or float(observation.get("age_minutes", 61.0)) > 60.0:
            continue
        rows.append(
            {
                "source_name": observation.get("source_name", ""),
                "age": observation.get("age_label", ""),
                "source_tier": observation.get("source_tier", 3),
                "text_excerpt": observation.get("text_excerpt", ""),
            }
        )
    return rows[:3]


def build_missing_confirmations(claim_ledger: list[dict[str, Any]]) -> list[str]:
    return [item.get("claim_text", "") for item in claim_ledger if item.get("status") != "confirmed" and item.get("claim_text")]


def build_retrieval_quality(
    observations: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
) -> dict[str, int]:
    freshness_capture_score = 100 if any(float(item.get("age_minutes", 99.0)) <= 10.0 for item in observations) else 70
    shadow_signal_discipline_score = 100
    blocked_source_handling_score = 100
    if any(item.get("access_mode") == "blocked" and item.get("channel") == "core" for item in observations):
        blocked_source_handling_score = 75
    if any(item.get("status") == "confirmed" and item.get("promotion_state") != "core" for item in claim_ledger):
        shadow_signal_discipline_score = 70
    return {
        "freshness_capture_score": freshness_capture_score,
        "shadow_signal_discipline_score": shadow_signal_discipline_score,
        "source_promotion_discipline_score": 100,
        "blocked_source_handling_score": blocked_source_handling_score,
    }


def build_expected_source_families(request: dict[str, Any], observations: list[dict[str, Any]]) -> list[str]:
    families = clean_string_list(request.get("expected_source_families"))
    if any(item.get("source_type") in PROMOTABLE_TRACKER_TYPES for item in observations) and "public_ais" not in families:
        families.append("public_ais")
    return families


def build_missed_expected_source_families(expected_families: list[str], observations: list[dict[str, Any]]) -> list[str]:
    seen = {source_type_family(clean_text(item.get("source_type"))) for item in observations}
    return [item for item in expected_families if item not in seen]


def build_retrieval_run_report(
    request: dict[str, Any],
    observations: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_families = build_expected_source_families(request, observations)
    top_recent_hits = [
        {
            "source_name": item.get("source_name", ""),
            "source_type": item.get("source_type", ""),
            "source_tier": item.get("source_tier", 3),
            "origin": item.get("origin", ""),
            "channel": item.get("channel", ""),
            "age": item.get("age_label", ""),
            "recency_bucket": item.get("recency_bucket", ""),
            "rank_score": item.get("rank_score", 0),
            "access_mode": item.get("access_mode", ""),
            "url": item.get("url", ""),
            "text_excerpt": item.get("text_excerpt", ""),
        }
        for item in observations[:5]
    ]
    blocked_sources = [
        {
            "source_id": item.get("source_id", ""),
            "source_name": item.get("source_name", ""),
            "source_type": item.get("source_type", ""),
            "origin": item.get("origin", ""),
            "access_mode": "blocked",
        }
        for item in observations
        if item.get("access_mode") == "blocked"
    ]
    report = {
        "fetch_order": [item.get("source_id", "") for item in observations],
        "sources_attempted": [
            {
                "source_id": item.get("source_id", ""),
                "source_name": item.get("source_name", ""),
                "source_type": item.get("source_type", ""),
                "origin": item.get("origin", ""),
                "access_mode": item.get("access_mode", ""),
            }
            for item in observations
        ],
        "sources_blocked": blocked_sources,
        "top_recent_hits": top_recent_hits,
        "shadow_to_core_promotions": [item.get("claim_id", "") for item in claim_ledger if item.get("status") == "confirmed"],
        "missed_expected_source_families": build_missed_expected_source_families(expected_families, observations),
    }
    if clean_text(request.get("preset")) == "energy-war":
        report["benchmark_watchlist"] = clean_string_list(request.get("benchmark_watchlist"))
    return report


def build_core_verdict(confirmed: list[dict[str, Any]], missing_confirmations: list[str]) -> str:
    if confirmed and missing_confirmations:
        return f"{len(confirmed)} core claim(s) have fresh support; current read is evidence-backed but still watch the conflict panel."
    if confirmed:
        return f"{len(confirmed)} core claim(s) are now cleanly supported by the public record."
    return "The live tape is active, but the confirmed public record is still too thin for a hard call."


def build_confidence_interval(confirmed: list[dict[str, Any]], missing_confirmations: list[str], blocked_count: int) -> list[int]:
    if confirmed and missing_confirmations:
        return [32, 80]
    if confirmed and not missing_confirmations:
        return [55, 90]
    if blocked_count:
        return [20, 60]
    return [25, 65]


def build_next_watch_items(missing_expected_source_families: list[str]) -> list[str]:
    items = [
        "Look for a fresh Tier 0 or Tier 1 confirmation before upgrading any shadow-only claim.",
        "Treat ship-tracking as last public indication, not live military truth.",
    ]
    if missing_expected_source_families:
        items.append("Watch for blocked or missing source families before calling the picture complete.")
    else:
        items.append("Keep the live tape separate from the confirmed record as new updates arrive.")
    return items


def build_escalation_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "Managed de-escalation",
            "probability_range": "35-55%",
            "trigger": "Fresh official or wire confirmation of continued talks or restraint steps",
        },
        {
            "scenario": "Extended standoff",
            "probability_range": "45-65%",
            "trigger": "Mixed negotiation signals with no decisive military or diplomatic break",
        },
        {
            "scenario": "Renewed escalation",
            "probability_range": "23-43%",
            "trigger": "Fresh denial plus force-positioning signals or a failed mediation channel",
        },
    ]


def build_energy_war_preset(request: dict[str, Any]) -> dict[str, Any]:
    watchlist = clean_string_list(request.get("benchmark_watchlist")) or ["Brent", "TTF Gas", "LNG", "VLCC", "Defense"]
    request["benchmark_watchlist"] = watchlist
    return {
        "benchmark_watchlist": watchlist,
        "operator_note": "Track energy, shipping, and defense transmission before widening the story.",
    }


def build_verdict_output(
    request: dict[str, Any],
    observations: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
    retrieval_run_report: dict[str, Any],
) -> dict[str, Any]:
    confirmed, not_confirmed, inference_only = build_claim_sections(claim_ledger)
    missing_confirmations = build_missing_confirmations(claim_ledger)
    verdict = {
        "core_verdict": build_core_verdict(confirmed, missing_confirmations),
        "live_tape": build_live_tape(observations),
        "confidence_interval": build_confidence_interval(
            confirmed,
            missing_confirmations,
            len(retrieval_run_report.get("sources_blocked", [])),
        ),
        "confidence_gate": "usable" if confirmed or observations else "thin",
        "latest_signals": [
            {
                "source_name": item.get("source_name", ""),
                "source_type": item.get("source_type", ""),
                "source_tier": item.get("source_tier", 3),
                "origin": item.get("origin", ""),
                "channel": item.get("channel", ""),
                "age": item.get("age_label", ""),
                "recency_bucket": item.get("recency_bucket", ""),
                "rank_score": item.get("rank_score", 0),
                "access_mode": item.get("access_mode", ""),
                "url": item.get("url", ""),
                "text_excerpt": item.get("text_excerpt", ""),
            }
            for item in observations
        ],
        "confirmed": confirmed,
        "not_confirmed": not_confirmed,
        "inference_only": inference_only,
        "conflict_matrix": build_conflict_matrix(claim_ledger),
        "missing_confirmations": missing_confirmations,
        "market_relevance": clean_string_list(request.get("market_relevance")),
        "next_watch_items": build_next_watch_items(retrieval_run_report.get("missed_expected_source_families", [])),
        "freshness_panel": build_freshness_panel(observations, clean_string_list(request.get("windows")) or list(WINDOW_MINUTES)),
        "source_layer_summary": build_source_layer_summary(observations),
        "source_artifacts": build_source_artifacts(observations),
        "background_only": build_background_only(observations),
        "negotiation_status_timeline": build_negotiation_status_timeline(observations, build_claim_text_map(request)),
        "vessel_movement_table": build_vessel_movement_table(observations),
        "escalation_scenarios": build_escalation_scenarios(),
    }
    if clean_text(request.get("preset")) == "energy-war":
        verdict["energy_war_preset"] = build_energy_war_preset(request)
    return verdict


def render_claim_lines(items: list[dict[str, Any]], *, include_status: bool = False) -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        text = clean_text(item.get("claim_text"))
        if not text:
            continue
        status = clean_text(item.get("status"))
        if include_status and status:
            lines.append(f"- {text} ({status})")
        else:
            lines.append(f"- {text}")
    return lines or ["- None"]


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    verdict = safe_dict(result.get("verdict_output"))
    topic = clean_text(request.get("topic")) or "news-index-topic"
    analysis_time = clean_text(request.get("analysis_time"))
    confidence = verdict.get("confidence_interval") or [0, 0]
    report_lines = [
        f"# News Index Report: {topic}",
        "",
        (
            "One-line judgment "
            f"({analysis_time}, confidence {confidence[0]}-{confidence[1]}, gate {clean_text(verdict.get('confidence_gate')) or 'unknown'}): "
            f"{clean_text(verdict.get('core_verdict'))}"
        ),
        "",
        "## Confirmed",
        *render_claim_lines(safe_list(verdict.get("confirmed"))),
        "",
        "## Not Confirmed",
        *render_claim_lines(safe_list(verdict.get("not_confirmed")), include_status=True),
        "",
        "## Inference Only",
        *render_claim_lines(safe_list(verdict.get("inference_only"))),
        "",
        "## Latest Signals First",
        "",
        "| Source | Tier | Channel | Age | Rank | Note |",
        "|---|---:|---|---|---:|---|",
    ]

    for item in safe_list(verdict.get("latest_signals")):
        report_lines.append(
            f"| {clean_text(item.get('source_name'))} | {safe_int(item.get('source_tier'), 3)} | "
            f"{clean_text(item.get('channel'))} | {clean_text(item.get('age'))} | "
            f"{safe_int(item.get('rank_score'))} | {clean_text(item.get('text_excerpt'))} |"
        )

    report_lines.extend(["", "## Conflict Matrix", "", "| Claim | Status | Supports | Contradictions | Promotion |", "|---|---|---:|---:|---|"])
    for item in safe_list(verdict.get("conflict_matrix")):
        report_lines.append(
            f"| {clean_text(item.get('claim_id'))} | {clean_text(item.get('status'))} | "
            f"{safe_int(item.get('support_count'))} | {safe_int(item.get('contradiction_count'))} | "
            f"{clean_text(item.get('promotion_state'))} |"
        )

    report_lines.extend(["", "## Freshness Panel"])
    for item in safe_list(verdict.get("freshness_panel")):
        report_lines.append(
            f"- {clean_text(item.get('window'))}: total {safe_int(item.get('count'))}, core {safe_int(item.get('core_count'))}, "
            f"shadow {safe_int(item.get('shadow_count'))}, blocked {safe_int(item.get('blocked_count'))}"
        )

    report_lines.extend(
        [
            "",
            "## Source Layer Summary",
            f"- By channel: {json.dumps(safe_dict(safe_dict(verdict.get('source_layer_summary')).get('by_channel')), ensure_ascii=False)}",
            f"- By tier: {json.dumps(safe_dict(safe_dict(verdict.get('source_layer_summary')).get('by_tier')), ensure_ascii=False)}",
            f"- By access mode: {json.dumps(safe_dict(safe_dict(verdict.get('source_layer_summary')).get('by_access_mode')), ensure_ascii=False)}",
            "",
            "## Source Artifacts",
        ]
    )
    artifacts = safe_list(verdict.get("source_artifacts"))
    if not artifacts:
        report_lines.append("- None")
    else:
        for item in artifacts:
            report_lines.append(
                f"- {clean_text(item.get('source_name'))} | tier {safe_int(item.get('source_tier'), 3)} | "
                f"{clean_text(item.get('channel'))} | {clean_text(item.get('access_mode'))}"
            )
            report_lines.append(f"  URL: {clean_text(item.get('url'))}")
            report_lines.append(f"  Main post text: {clean_text(item.get('post_text_raw')) or 'none'}")
            report_lines.append(f"  Image summary: {clean_text(item.get('media_summary')) or 'none'}")
            report_lines.append(f"  Screenshot: {clean_text(item.get('root_post_screenshot_path')) or 'none'}")

    report_lines.extend(["", "## Live Tape"])
    live_tape = safe_list(verdict.get("live_tape"))
    if not live_tape:
        report_lines.append("- None")
    else:
        for item in live_tape:
            report_lines.append(
                f"- [{clean_text(item.get('source_name'))}] tier {safe_int(item.get('source_tier'), 3)}, "
                f"{clean_text(item.get('age'))}: {clean_text(item.get('text_excerpt'))}"
            )

    report_lines.extend(["", "## Negotiation Status Timeline"])
    timeline = safe_list(verdict.get("negotiation_status_timeline"))
    if not timeline:
        report_lines.append("- None")
    else:
        for item in timeline:
            report_lines.append(
                f"- {clean_text(item.get('timestamp'))}: {clean_text(item.get('source_name'))} "
                f"({clean_text(item.get('channel'))}) - {clean_text(item.get('text_excerpt'))}"
            )

    report_lines.extend(["", "## Vessel Movement Table", "", "| Vessel | Last Public Indication | Timestamp | ETA Range | Source |", "|---|---|---|---|---|"])
    vessel_rows = safe_list(verdict.get("vessel_movement_table"))
    if not vessel_rows:
        report_lines.append("| None | none | none | none | none |")
    else:
        for item in vessel_rows:
            report_lines.append(
                f"| {' / '.join(clean_string_list(item.get('vessel_ids')))} | {clean_text(item.get('last_public_location'))} | "
                f"{clean_text(item.get('timestamp'))} | {clean_text(item.get('eta_range'))} | {clean_text(item.get('source_name'))} |"
            )

    report_lines.extend(["", "## Escalation Scenarios"])
    for item in safe_list(verdict.get("escalation_scenarios")):
        report_lines.append(
            f"- {clean_text(item.get('scenario'))}: {clean_text(item.get('probability_range'))}; "
            f"trigger: {clean_text(item.get('trigger'))}"
        )

    if clean_text(request.get("preset")) == "energy-war":
        report_lines.extend(["", "## Energy-War Preset"])
        report_lines.append(f"- Benchmark watchlist: {', '.join(clean_string_list(request.get('benchmark_watchlist')))}")
        report_lines.append("- Keep crude, LNG, shipping, and defense transmission in the watchboard.")

    report_lines.extend(["", "## What Would Change My View"])
    for item in clean_string_list(verdict.get("next_watch_items")):
        report_lines.append(f"- {item}")

    return "\n".join(report_lines).rstrip() + "\n"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = deepcopy(raw_payload)
    analysis_time = parse_datetime(request.get("analysis_time"), fallback=now_utc()) or now_utc()
    request["analysis_time"] = isoformat_or_blank(analysis_time)
    request["questions"] = clean_string_list(request.get("questions"))
    request["source_preferences"] = clean_string_list(request.get("source_preferences"))
    request["windows"] = clean_string_list(request.get("windows")) or list(WINDOW_MINUTES)
    request["market_relevance"] = clean_string_list(request.get("market_relevance"))
    request["expected_source_families"] = clean_string_list(request.get("expected_source_families"))
    request["claims"] = [safe_dict(item) for item in safe_list(request.get("claims")) if isinstance(item, dict)]
    request["candidates"] = [safe_dict(item) for item in safe_list(request.get("candidates")) if isinstance(item, dict)]
    request["mode"] = clean_text(request.get("mode")) or "generic"
    if request["mode"] == "crisis":
        request["crisis_defaults"] = safe_dict(request.get("crisis_defaults"))
        request["max_parallel_candidates"] = safe_int(request.get("max_parallel_candidates"), 4)
    if clean_text(request.get("preset")) == "energy-war":
        build_energy_war_preset(request)
    return request


def run_news_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    analysis_time = parse_datetime(request.get("analysis_time"), fallback=now_utc()) or now_utc()
    claim_text_map = build_claim_text_map(request)
    observations = [normalize_observation(candidate, claim_text_map, analysis_time) for candidate in safe_list(request.get("candidates"))]
    apply_channel_promotions(observations)
    observations.sort(key=observation_sort_key, reverse=True)
    claim_ledger = build_claim_ledger(observations, claim_text_map)
    retrieval_run_report = build_retrieval_run_report(request, observations, claim_ledger)
    verdict_output = build_verdict_output(request, observations, claim_ledger, retrieval_run_report)
    retrieval_quality = build_retrieval_quality(observations, claim_ledger)

    result = {
        "status": "ok",
        "request": request,
        "retrieval_request": deepcopy(request),
        "observations": observations,
        "source_observations": observations,
        "claim_ledger": claim_ledger,
        "verdict_output": verdict_output,
        "retrieval_run_report": retrieval_run_report,
        "retrieval_quality": retrieval_quality,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        source_id = clean_text(item.get("source_id"))
        url = clean_text(item.get("url"))
        key = (source_id, url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def merge_refresh(existing_result: dict[str, Any], refresh_payload: dict[str, Any]) -> dict[str, Any]:
    base_request = safe_dict(existing_result.get("request")) or safe_dict(existing_result.get("retrieval_request"))
    merged_request = deepcopy(base_request)
    merged_request["analysis_time"] = clean_text(refresh_payload.get("analysis_time")) or clean_text(base_request.get("analysis_time"))
    merged_request["candidates"] = dedupe_candidates(
        [safe_dict(item) for item in safe_list(base_request.get("candidates"))]
        + [safe_dict(item) for item in safe_list(refresh_payload.get("candidates"))]
    )
    result = run_news_index(merged_request)
    result["refresh_summary"] = {
        "mode": "refresh",
        "analysis_time": clean_text(merged_request.get("analysis_time")),
        "added_source_ids": [
            clean_text(item.get("source_id"))
            for item in safe_list(refresh_payload.get("candidates"))
            if isinstance(item, dict) and clean_text(item.get("source_id"))
        ],
    }
    return result


__all__ = [
    "build_markdown_report",
    "clean_string_list",
    "fetch_public_page_hints",
    "isoformat_or_blank",
    "load_json",
    "merge_refresh",
    "now_utc",
    "parse_datetime",
    "run_news_index",
    "safe_dict",
    "safe_list",
    "short_excerpt",
    "slugify",
    "write_json",
]
