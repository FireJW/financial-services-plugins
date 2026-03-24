#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


TIER_WEIGHTS = {0: 100, 1: 80, 2: 60, 3: 35}
STALE_PENALTY = 25
DEFAULT_WINDOWS = ["10m", "1h", "6h", "24h"]
CRISIS_EXPECTED_SOURCE_FAMILIES = [
    "government",
    "wire",
    "major_news",
    "public_ais",
    "public_ship_tracker",
    "social",
]

TIER_BY_SOURCE_TYPE = {
    "official": 0,
    "official_statement": 0,
    "official_release": 0,
    "government": 0,
    "government_release": 0,
    "government_ministry": 0,
    "regulator": 0,
    "regulator_filing": 0,
    "company_filing": 0,
    "exchange_filing": 0,
    "company_statement": 0,
    "wire": 1,
    "major_news": 1,
    "major_press": 1,
    "major_media": 1,
    "specialist": 2,
    "specialist_outlet": 2,
    "analysis": 2,
    "research_note": 2,
    "public_ais": 2,
    "public_ship_tracker": 2,
    "ship_tracker": 2,
    "ais": 2,
    "blog": 3,
    "community": 3,
    "market_rumor": 3,
    "rumor": 3,
    "social": 3,
}

RECENCY_WINDOWS = [
    ("10m", 10, 40),
    ("1h", 60, 30),
    ("6h", 360, 20),
    ("24h", 1440, 10),
]


@dataclass
class ClaimEvidence:
    supports: list[dict[str, Any]]
    contradicts: list[dict[str, Any]]


def now_utc() -> datetime:
    return datetime.now(UTC)


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_datetime(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return fallback

    text = value.strip()
    if not text:
        return fallback
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text}T00:00:00+00:00")
        except ValueError:
            return fallback

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def isoformat_or_blank(value: datetime | None) -> str:
    return value.astimezone(UTC).isoformat() if value else ""


def normalize_source_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return text or "unknown"


def source_tier_for(source_type: str) -> int:
    return TIER_BY_SOURCE_TYPE.get(
        source_type,
        2 if "ais" in source_type else 3 if "social" in source_type else 1 if "news" in source_type else 2,
    )


def source_family_for(source_type: str) -> str:
    if source_type.startswith("government") or source_type.startswith("official"):
        return "government"
    if source_type.startswith("regulator") or source_type.endswith("filing"):
        return "government"
    if source_type in {"wire", "major_news", "major_press", "major_media"}:
        return source_type if source_type != "major_press" and source_type != "major_media" else "major_news"
    if source_type in {"public_ais", "ais"}:
        return "public_ais"
    if source_type in {"public_ship_tracker", "ship_tracker"}:
        return "public_ship_tracker"
    if source_type in {"social", "market_rumor", "rumor", "community"}:
        return "social"
    return source_type


def recency_bucket(age_minutes: float) -> str:
    if age_minutes <= 10:
        return "0-10m"
    if age_minutes <= 60:
        return "10-60m"
    if age_minutes <= 360:
        return "1-6h"
    if age_minutes <= 1440:
        return "6-24h"
    return ">24h"


def recency_boost(age_minutes: float) -> int:
    if age_minutes <= 10:
        return 40
    if age_minutes <= 60:
        return 30
    if age_minutes <= 360:
        return 20
    if age_minutes <= 1440:
        return 10
    return 0


def staleness_penalty(age_minutes: float) -> int:
    return STALE_PENALTY if age_minutes > 1440 else 0


def slugify(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or fallback


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def clean_artifact_manifest(value: Any) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        source_url = str(item.get("source_url", "")).strip()
        role = str(item.get("role", "")).strip()
        media_type = str(item.get("media_type", "")).strip()
        if not any([path, source_url, role, media_type]):
            continue
        cleaned.append(
            {
                "role": role,
                "path": path,
                "source_url": source_url,
                "media_type": media_type,
            }
        )
    return cleaned


def short_excerpt(text: Any, limit: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def age_minutes_since(analysis_time: datetime, published_at: datetime | None, observed_at: datetime | None) -> float:
    anchor = published_at or observed_at or analysis_time
    return max(0.0, (analysis_time - anchor).total_seconds() / 60.0)


def minutes_label(minutes: float) -> str:
    if minutes < 60:
        return f"{int(round(minutes))}m"
    if minutes < 1440:
        return f"{round(minutes / 60.0, 1):g}h"
    return f"{round(minutes / 1440.0, 1):g}d"


def normalize_claim_state(value: Any) -> str:
    state = str(value or "").strip().lower()
    aliases = {
        "supporting": "support",
        "supported": "support",
        "confirm": "support",
        "confirmed": "support",
        "deny": "contradict",
        "denied": "contradict",
        "refute": "contradict",
        "refuted": "contradict",
        "uncertain": "unclear",
    }
    return aliases.get(state, state or "support")


def fetch_public_excerpt(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-NewsIndex/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(4096)
    return short_excerpt(raw.decode("utf-8", errors="ignore"), limit=240), "public"


def access_rank(access_mode: str) -> int:
    return {"public": 3, "browser_session": 2, "blocked": 1}.get(access_mode, 0)


def claim_text_map_from_request(request: dict[str, Any]) -> dict[str, str]:
    claim_map: dict[str, str] = {}
    for claim in safe_list(request.get("claims")):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id", "")).strip()
        if claim_id:
            claim_map[claim_id] = str(claim.get("claim_text", "")).strip()
    return claim_map


def upgrade_legacy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "candidates" in payload or "source_candidates" in payload:
        return payload

    source_pack = safe_dict(payload.get("source_pack"))
    if not source_pack:
        return payload

    analysis_time = (
        payload.get("analysis_time")
        or source_pack.get("analysis_date")
        or payload.get("analysis_date")
        or ""
    )
    claims = []
    for index, claim in enumerate(safe_list(source_pack.get("key_claims")), start=1):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or f"claim-{index:02d}")
        claims.append(
            {
                "claim_id": claim_id,
                "claim_text": str(claim.get("claim") or claim.get("claim_text") or "").strip(),
                "expected_status": str(claim.get("status", "")).strip(),
            }
        )

    candidates = []
    for index, source in enumerate(safe_list(source_pack.get("sources")), start=1):
        if not isinstance(source, dict):
            continue
        candidates.append(
            {
                "source_id": str(source.get("source_id") or f"legacy-source-{index:02d}"),
                "source_name": source.get("name", ""),
                "source_type": source.get("type") or source.get("source_type") or "major_news",
                "published_at": source.get("published_at") or analysis_time,
                "observed_at": source.get("observed_at") or source.get("published_at") or analysis_time,
                "url": source.get("url", ""),
                "text_excerpt": source.get("support", ""),
                "claim_ids": [claim["claim_id"] for claim in claims],
                "channel": "shadow",
                "access_mode": source.get("access_mode") or "public",
            }
        )

    return {
        "topic": payload.get("topic")
        or source_pack.get("event_label")
        or payload.get("title")
        or payload.get("task_goal")
        or "news-index-topic",
        "analysis_time": analysis_time,
        "questions": payload.get("questions") or [payload.get("claim_to_evaluate") or payload.get("task_goal") or ""],
        "use_case": payload.get("use_case") or "legacy-run-record-upgrade",
        "source_preferences": payload.get("source_preferences") or [],
        "mode": payload.get("mode") or "generic",
        "windows": payload.get("windows") or DEFAULT_WINDOWS,
        "claims": claims,
        "candidates": candidates,
        "market_relevance": payload.get("market_relevance") or [],
        "expected_source_families": payload.get("expected_source_families") or [],
    }


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = upgrade_legacy_payload(raw_payload)
    analysis_time = parse_datetime(payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    mode = "crisis" if str(payload.get("mode", "")).strip().lower() == "crisis" else "generic"
    expected_source_families = clean_string_list(payload.get("expected_source_families"))
    if mode == "crisis":
        for family in CRISIS_EXPECTED_SOURCE_FAMILIES:
            if family not in expected_source_families:
                expected_source_families.append(family)

    return {
        "topic": str(payload.get("topic", "")).strip() or "news-index-topic",
        "analysis_time": analysis_time,
        "questions": clean_string_list(payload.get("questions")),
        "use_case": str(payload.get("use_case", "")).strip() or "news-index",
        "source_preferences": clean_string_list(payload.get("source_preferences")),
        "mode": mode,
        "windows": clean_string_list(payload.get("windows")) or list(DEFAULT_WINDOWS),
        "claims": [item for item in safe_list(payload.get("claims")) if isinstance(item, dict)],
        "candidates": [
            item
            for item in safe_list(payload.get("candidates") or payload.get("source_candidates"))
            if isinstance(item, dict)
        ],
        "market_relevance": clean_string_list(payload.get("market_relevance")),
        "expected_source_families": expected_source_families,
        "crisis_defaults": safe_dict(payload.get("crisis_defaults")),
    }


def normalize_candidate(
    candidate: dict[str, Any],
    analysis_time: datetime,
    claim_texts: dict[str, str],
    index: int,
) -> dict[str, Any]:
    source_name = str(candidate.get("source_name") or candidate.get("name") or f"source-{index:02d}").strip()
    source_type = normalize_source_type(candidate.get("source_type") or candidate.get("type"))
    source_id = str(candidate.get("source_id") or slugify(source_name, f"source-{index:02d}")).strip()
    published_at = parse_datetime(candidate.get("published_at"), fallback=analysis_time)
    observed_at = parse_datetime(candidate.get("observed_at"), fallback=published_at or analysis_time)
    access_mode = str(candidate.get("access_mode", "public")).strip() or "public"
    text_excerpt = short_excerpt(
        candidate.get("text_excerpt") or candidate.get("summary") or candidate.get("support") or ""
    )

    if access_mode != "blocked" and not text_excerpt and str(candidate.get("url", "")).strip():
        try:
            text_excerpt, access_mode = fetch_public_excerpt(str(candidate.get("url")).strip())
        except (TimeoutError, OSError, urllib.error.URLError):
            access_mode = "blocked"

    claim_ids = clean_string_list(candidate.get("claim_ids"))
    raw_states = safe_dict(candidate.get("claim_states") or candidate.get("stance_by_claim"))
    claim_states = {
        claim_id: normalize_claim_state(raw_states.get(claim_id) or candidate.get("claim_state") or "support")
        for claim_id in claim_ids
    }

    age = age_minutes_since(analysis_time, published_at, observed_at)
    source_tier = source_tier_for(source_type)
    channel = str(candidate.get("channel", "")).strip().lower()
    if channel not in {"core", "shadow", "background"}:
        channel = "core" if source_tier <= 1 else "shadow"
    if access_mode == "blocked":
        channel = "background"
    if age > 1440:
        channel = "background"

    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_type": source_type,
        "source_tier": source_tier,
        "channel": channel,
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": str(candidate.get("url", "")).strip(),
        "claim_ids": claim_ids,
        "entity_ids": clean_string_list(candidate.get("entity_ids")),
        "vessel_ids": clean_string_list(candidate.get("vessel_ids")),
        "text_excerpt": text_excerpt,
        "position_hint": deepcopy(candidate.get("position_hint")),
        "geo_hint": deepcopy(candidate.get("geo_hint")),
        "access_mode": access_mode,
        "rank_score": 0,
        "recency_bucket": recency_bucket(age),
        "age_minutes": round(age, 2),
        "age_label": minutes_label(age),
        "claim_states": claim_states,
        "claim_texts": {claim_id: claim_texts.get(claim_id, "") for claim_id in claim_ids},
        "artifact_manifest": clean_artifact_manifest(candidate.get("artifact_manifest")),
        "x_post_record": deepcopy(candidate.get("x_post_record")) if isinstance(candidate.get("x_post_record"), dict) else {},
        "post_text_raw": str(candidate.get("post_text_raw", "")).strip(),
        "post_text_source": str(candidate.get("post_text_source", "")).strip(),
        "post_text_confidence": candidate.get("post_text_confidence", 0.0),
        "root_post_screenshot_path": str(candidate.get("root_post_screenshot_path", "")).strip(),
        "thread_posts": deepcopy(candidate.get("thread_posts")) if isinstance(candidate.get("thread_posts"), list) else [],
        "media_items": deepcopy(candidate.get("media_items")) if isinstance(candidate.get("media_items"), list) else [],
        "post_summary": str(candidate.get("post_summary", "")).strip(),
        "media_summary": str(candidate.get("media_summary", "")).strip(),
        "combined_summary": str(candidate.get("combined_summary", "")).strip(),
        "discovery_reason": str(candidate.get("discovery_reason", "")).strip(),
        "crawl_notes": deepcopy(candidate.get("crawl_notes")) if isinstance(candidate.get("crawl_notes"), list) else [],
    }


def dedupe_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for observation in observations:
        key = (
            observation.get("url", "") or observation.get("source_name", ""),
            observation.get("published_at", ""),
            "|".join(sorted(observation.get("claim_ids", []))),
            observation.get("text_excerpt", ""),
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = observation
            continue

        existing["claim_ids"] = sorted(set(existing["claim_ids"]) | set(observation["claim_ids"]))
        existing["entity_ids"] = sorted(set(existing["entity_ids"]) | set(observation["entity_ids"]))
        existing["vessel_ids"] = sorted(set(existing["vessel_ids"]) | set(observation["vessel_ids"]))
        existing["claim_states"].update(observation.get("claim_states", {}))
        existing["claim_texts"].update(observation.get("claim_texts", {}))
        if access_rank(observation.get("access_mode", "")) > access_rank(existing.get("access_mode", "")):
            existing["access_mode"] = observation.get("access_mode", "")
        if len(observation.get("text_excerpt", "")) > len(existing.get("text_excerpt", "")):
            existing["text_excerpt"] = observation.get("text_excerpt", "")
        if len(observation.get("post_text_raw", "")) > len(existing.get("post_text_raw", "")):
            existing["post_text_raw"] = observation.get("post_text_raw", "")
            existing["post_text_source"] = observation.get("post_text_source", "")
            existing["post_text_confidence"] = observation.get("post_text_confidence", 0.0)
        if len(observation.get("post_summary", "")) > len(existing.get("post_summary", "")):
            existing["post_summary"] = observation.get("post_summary", "")
        if len(observation.get("media_summary", "")) > len(existing.get("media_summary", "")):
            existing["media_summary"] = observation.get("media_summary", "")
        if len(observation.get("combined_summary", "")) > len(existing.get("combined_summary", "")):
            existing["combined_summary"] = observation.get("combined_summary", "")
        if observation.get("root_post_screenshot_path") and not existing.get("root_post_screenshot_path"):
            existing["root_post_screenshot_path"] = observation.get("root_post_screenshot_path", "")
        if observation.get("thread_posts") and not existing.get("thread_posts"):
            existing["thread_posts"] = deepcopy(observation.get("thread_posts", []))
        if observation.get("media_items") and not existing.get("media_items"):
            existing["media_items"] = deepcopy(observation.get("media_items", []))
        if observation.get("x_post_record") and not existing.get("x_post_record"):
            existing["x_post_record"] = deepcopy(observation.get("x_post_record", {}))
        if observation.get("artifact_manifest"):
            merged_artifacts = {
                (item.get("role", ""), item.get("path", ""), item.get("source_url", "")): item
                for item in existing.get("artifact_manifest", [])
            }
            for artifact in observation.get("artifact_manifest", []):
                key = (artifact.get("role", ""), artifact.get("path", ""), artifact.get("source_url", ""))
                merged_artifacts[key] = artifact
            existing["artifact_manifest"] = list(merged_artifacts.values())
        if observation.get("crawl_notes"):
            existing["crawl_notes"] = clean_string_list(existing.get("crawl_notes", []) + observation.get("crawl_notes", []))
    return list(merged.values())


def build_claim_index(request: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, str]:
    claim_map = claim_text_map_from_request(request)
    for observation in observations:
        for claim_id, claim_text in observation.get("claim_texts", {}).items():
            if claim_id not in claim_map and claim_text:
                claim_map[claim_id] = claim_text
    return claim_map


def build_claim_evidence(observations: list[dict[str, Any]]) -> dict[str, ClaimEvidence]:
    claim_index: dict[str, ClaimEvidence] = {}
    for observation in observations:
        if observation.get("access_mode") == "blocked":
            continue
        for claim_id in observation.get("claim_ids", []):
            evidence = claim_index.setdefault(claim_id, ClaimEvidence(supports=[], contradicts=[]))
            state = normalize_claim_state(observation.get("claim_states", {}).get(claim_id))
            if state == "contradict":
                evidence.contradicts.append(observation)
            else:
                evidence.supports.append(observation)
    return claim_index


def corroboration_boost_for(observation: dict[str, Any], evidence_index: dict[str, ClaimEvidence]) -> int:
    corroborators: dict[str, dict[str, Any]] = {}
    source_id = observation.get("source_id")
    for claim_id in observation.get("claim_ids", []):
        evidence = evidence_index.get(claim_id)
        if not evidence:
            continue
        for other in evidence.supports:
            if other.get("source_id") == source_id:
                continue
            corroborators[other.get("source_id", "")] = other
    corroborators.pop("", None)
    if not corroborators:
        return 0
    if len(corroborators) >= 2 and len({item.get("source_tier", 3) for item in corroborators.values()}) >= 2:
        return 25
    return 15


def contradiction_penalty_for(observation: dict[str, Any], evidence_index: dict[str, ClaimEvidence]) -> int:
    penalties: list[int] = []
    source_tier = observation.get("source_tier", 3)
    for claim_id in observation.get("claim_ids", []):
        evidence = evidence_index.get(claim_id)
        if not evidence:
            continue
        for other in evidence.contradicts:
            other_age = float(other.get("age_minutes", 0.0))
            other_tier = other.get("source_tier", 3)
            if other_age > 1440:
                penalties.append(10)
            elif other_tier <= 1 and other_tier < source_tier:
                penalties.append(35)
            elif other_tier == source_tier:
                penalties.append(20)
            else:
                penalties.append(15)
    return max(penalties, default=0)


def fallback_channel(observation: dict[str, Any]) -> str:
    if observation.get("access_mode") == "blocked":
        return "background"
    if float(observation.get("age_minutes", 0.0)) > 1440:
        return "background"
    if observation.get("source_tier", 3) <= 1:
        return "core"
    return "shadow"


def rerank_observations(
    observations: list[dict[str, Any]],
    evidence_index: dict[str, ClaimEvidence],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for observation in observations:
        age = float(observation.get("age_minutes", 0.0))
        score = (
            TIER_WEIGHTS.get(observation.get("source_tier", 3), 35)
            + recency_boost(age)
            + corroboration_boost_for(observation, evidence_index)
            - contradiction_penalty_for(observation, evidence_index)
            - staleness_penalty(age)
        )
        if observation.get("access_mode") == "blocked":
            score -= 25
        observation["rank_score"] = score
        if not observation.get("channel"):
            observation["channel"] = fallback_channel(observation)
        ranked.append(observation)
    ranked.sort(key=lambda item: (item.get("rank_score", 0), -float(item.get("age_minutes", 0.0))), reverse=True)
    return ranked


def promoted_to_core(supports: list[dict[str, Any]]) -> bool:
    fresh_supports = [
        item
        for item in supports
        if float(item.get("age_minutes", 0.0)) <= 1440 and item.get("access_mode") != "blocked"
    ]
    if not fresh_supports:
        return False
    if any(item.get("source_tier", 3) <= 1 for item in fresh_supports):
        return True
    tier_two_sources = {item.get("source_id") for item in fresh_supports if item.get("source_tier", 3) == 2}
    return len(tier_two_sources) >= 2


def claim_status_for(supports: list[dict[str, Any]], contradicts: list[dict[str, Any]]) -> tuple[str, str]:
    strongest_support = min((item.get("source_tier", 3) for item in supports), default=None)
    strongest_contradiction = min((item.get("source_tier", 3) for item in contradicts), default=None)
    if strongest_contradiction is not None and strongest_support is None:
        return "denied", "core"
    if strongest_support is None and strongest_contradiction is None:
        return "inferred", "background"
    if strongest_support is not None and strongest_contradiction is not None:
        if strongest_contradiction < strongest_support:
            return "denied", "shadow"
        return "unclear", "shadow"
    promotion_state = (
        "core"
        if promoted_to_core(supports)
        else "background"
        if all(float(item.get("age_minutes", 0.0)) > 1440 for item in supports)
        else "shadow"
    )
    return ("confirmed", "core") if promotion_state == "core" else ("unclear", promotion_state)


def build_claim_ledger(request: dict[str, Any], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_map = build_claim_index(request, observations)
    evidence_index = build_claim_evidence(observations)
    ledger: list[dict[str, Any]] = []
    for claim_id in sorted(set(claim_map) | set(evidence_index)):
        evidence = evidence_index.get(claim_id, ClaimEvidence(supports=[], contradicts=[]))
        status, promotion_state = claim_status_for(evidence.supports, evidence.contradicts)
        timestamps = [
            parse_datetime(item.get("published_at"))
            for item in evidence.supports + evidence.contradicts
            if item.get("published_at")
        ]
        last_updated = max(timestamps) if timestamps else request["analysis_time"]
        ledger.append(
            {
                "claim_id": claim_id,
                "claim_text": claim_map.get(claim_id, ""),
                "status": status,
                "supporting_sources": [item.get("source_id", "") for item in evidence.supports],
                "contradicting_sources": [item.get("source_id", "") for item in evidence.contradicts],
                "last_updated_at": isoformat_or_blank(last_updated),
                "promotion_state": promotion_state,
            }
        )
    return ledger


def promote_observation_channels(observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> None:
    core_claims = {item["claim_id"] for item in claim_ledger if item.get("promotion_state") == "core"}
    for observation in observations:
        if observation.get("access_mode") == "blocked":
            observation["channel"] = "background"
        elif float(observation.get("age_minutes", 0.0)) > 1440:
            observation["channel"] = "background"
        elif observation.get("source_tier", 3) == 2 and core_claims.intersection(observation.get("claim_ids", [])):
            observation["channel"] = "core"
        elif observation.get("source_tier", 3) == 3:
            observation["channel"] = "shadow"


def build_latest_signals(observations: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "source_name": item.get("source_name", ""),
            "source_type": item.get("source_type", ""),
            "source_tier": item.get("source_tier", 3),
            "channel": item.get("channel", ""),
            "age": item.get("age_label", ""),
            "recency_bucket": item.get("recency_bucket", ""),
            "rank_score": item.get("rank_score", 0),
            "access_mode": item.get("access_mode", ""),
            "url": item.get("url", ""),
            "text_excerpt": item.get("text_excerpt", ""),
        }
        for item in observations[:limit]
    ]


def build_freshness_panel(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    panel = []
    for window_name, ceiling, _ in RECENCY_WINDOWS:
        matches = [item for item in observations if float(item.get("age_minutes", 0.0)) <= ceiling]
        panel.append(
            {
                "window": window_name,
                "count": len(matches),
                "core_count": sum(1 for item in matches if item.get("channel") == "core"),
                "shadow_count": sum(1 for item in matches if item.get("channel") == "shadow"),
                "blocked_count": sum(1 for item in matches if item.get("access_mode") == "blocked"),
            }
        )
    return panel


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


def build_source_layer_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "by_channel": dict(Counter(item.get("channel", "unknown") for item in observations)),
        "by_tier": dict(Counter(str(item.get("source_tier", 3)) for item in observations)),
        "by_access_mode": dict(Counter(item.get("access_mode", "unknown") for item in observations)),
    }


def build_source_artifacts(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for observation in observations:
        if not any(
            [
                observation.get("post_text_raw"),
                observation.get("media_summary"),
                observation.get("root_post_screenshot_path"),
                observation.get("artifact_manifest"),
            ]
        ):
            continue
        artifacts.append(
            {
                "source_name": observation.get("source_name", ""),
                "source_tier": observation.get("source_tier", 3),
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


def build_confidence(claim_ledger: list[dict[str, Any]], observations: list[dict[str, Any]]) -> tuple[list[int], str]:
    confirmed = sum(1 for item in claim_ledger if item.get("status") == "confirmed")
    denied = sum(1 for item in claim_ledger if item.get("status") == "denied")
    unclear = sum(1 for item in claim_ledger if item.get("status") == "unclear")
    core_sources = [item for item in observations if item.get("channel") == "core" and item.get("access_mode") != "blocked"]
    shadow_sources = [item for item in observations if item.get("channel") == "shadow"]
    blocked_sources = [item for item in observations if item.get("access_mode") == "blocked"]
    avg_core_rank = average([item.get("rank_score", 0) for item in core_sources])
    center = clamp(35 + confirmed * 15 + min(len(core_sources), 4) * 7 + avg_core_rank / 8 - denied * 12 - unclear * 8 - len(blocked_sources) * 3)
    width = clamp(10 + unclear * 4 + len(shadow_sources) * 2 + max(0, 2 - len(core_sources)) * 5, low=8, high=45)
    return [clamp(center - width), clamp(center + width)], "usable" if core_sources else "shadow-heavy"


def build_retrieval_quality(observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> dict[str, int]:
    top_hits = observations[:5]
    top_recent = sum(1 for item in top_hits if item.get("recency_bucket") in {"0-10m", "10-60m", "1-6h"})
    improper_shadow_core = sum(1 for item in observations if item.get("channel") == "core" and item.get("source_tier", 3) == 3)
    improper_promotion = sum(1 for item in claim_ledger if item.get("promotion_state") == "core" and not item.get("supporting_sources"))
    return {
        "freshness_capture_score": clamp(50 + top_recent * 10),
        "shadow_signal_discipline_score": clamp(100 - improper_shadow_core * 35),
        "source_promotion_discipline_score": clamp(100 - improper_promotion * 40),
        "blocked_source_handling_score": 100,
    }


def build_crisis_sections(request: dict[str, Any], observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    if request.get("mode") != "crisis":
        return {}

    negotiation_items = []
    for observation in observations:
        text = (observation.get("text_excerpt", "") + " " + " ".join(observation.get("claim_texts", {}).values())).lower()
        if any(keyword in text for keyword in ["talk", "negot", "ceasefire", "meeting", "mediat", "call"]):
            negotiation_items.append(
                {
                    "timestamp": observation.get("published_at") or observation.get("observed_at"),
                    "source_name": observation.get("source_name", ""),
                    "channel": observation.get("channel", ""),
                    "text_excerpt": observation.get("text_excerpt", ""),
                }
            )

    vessel_rows = []
    for observation in observations:
        if not observation.get("vessel_ids") and not observation.get("position_hint"):
            continue
        hint = observation.get("position_hint")
        hint_dict = hint if isinstance(hint, dict) else {"last_public_location": str(hint or "").strip()}
        eta_low = hint_dict.get("eta_hours_low")
        eta_high = hint_dict.get("eta_hours_high")
        if isinstance(eta_low, (int, float)) and isinstance(eta_high, (int, float)):
            eta_range = f"{round(float(eta_low), 1):g}-{round(float(eta_high), 1):g}h"
        else:
            eta_range = str(hint_dict.get("eta_range") or "unknown")
        vessel_rows.append(
            {
                "vessel_ids": observation.get("vessel_ids", []),
                "last_public_location": hint_dict.get("last_public_location") or hint_dict.get("location") or observation.get("geo_hint") or "unknown",
                "timestamp": observation.get("published_at") or observation.get("observed_at"),
                "eta_range": eta_range,
                "source_name": observation.get("source_name", ""),
            }
        )

    confirmed = sum(1 for item in claim_ledger if item.get("status") == "confirmed")
    denied = sum(1 for item in claim_ledger if item.get("status") == "denied")
    unclear = sum(1 for item in claim_ledger if item.get("status") == "unclear")
    deescalation = clamp(50 + confirmed * 6 - denied * 5 - unclear * 3, low=10, high=80)
    escalation = clamp(25 + denied * 8 + len(vessel_rows) * 4 - confirmed * 4, low=10, high=75)
    standoff = clamp(100 - max(deescalation, escalation), low=15, high=70)
    return {
        "negotiation_status_timeline": sorted(negotiation_items, key=lambda item: item.get("timestamp", ""), reverse=True),
        "vessel_movement_table": vessel_rows,
        "escalation_scenarios": [
            {
                "scenario": "Managed de-escalation",
                "probability_range": f"{max(5, deescalation - 10)}-{min(95, deescalation + 10)}%",
                "trigger": "Fresh official or wire confirmation of continued talks or restraint steps",
            },
            {
                "scenario": "Extended standoff",
                "probability_range": f"{max(5, standoff - 10)}-{min(95, standoff + 10)}%",
                "trigger": "Mixed negotiation signals with no decisive military or diplomatic break",
            },
            {
                "scenario": "Renewed escalation",
                "probability_range": f"{max(5, escalation - 10)}-{min(95, escalation + 10)}%",
                "trigger": "Fresh denial plus force-positioning signals or a failed mediation channel",
            },
        ],
    }


def build_verdict_output(request: dict[str, Any], observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    interval, gate = build_confidence(claim_ledger, observations)
    confirmed = [item for item in claim_ledger if item.get("status") == "confirmed"]
    not_confirmed = [item for item in claim_ledger if item.get("status") in {"denied", "unclear"}]
    inference_only = [item for item in claim_ledger if item.get("status") == "inferred"]
    live_tape = [item for item in observations if item.get("channel") == "shadow" and float(item.get("age_minutes", 0.0)) <= 1440]
    background = [item for item in observations if item.get("channel") == "background"]
    if confirmed:
        judgment = f"{len(confirmed)} core claim(s) have fresh support; current read is evidence-backed but still watch the conflict panel."
    elif live_tape:
        judgment = "The live tape is moving faster than the confirmed record; treat current headlines as directional, not settled."
    else:
        judgment = "Current evidence is thin or stale; there is no strong confirmed read yet."

    verdict = {
        "core_verdict": judgment,
        "live_tape": [
            {
                "source_name": item.get("source_name", ""),
                "age": item.get("age_label", ""),
                "source_tier": item.get("source_tier", 3),
                "text_excerpt": item.get("text_excerpt", ""),
            }
            for item in live_tape[:8]
        ],
        "confidence_interval": interval,
        "confidence_gate": gate,
        "latest_signals": build_latest_signals(observations),
        "confirmed": confirmed,
        "not_confirmed": not_confirmed,
        "inference_only": inference_only,
        "conflict_matrix": build_conflict_matrix(claim_ledger),
        "missing_confirmations": [item.get("claim_text", "") for item in not_confirmed if item.get("claim_text")],
        "market_relevance": request.get("market_relevance", []),
        "next_watch_items": [
            "Look for a fresh Tier 0 or Tier 1 confirmation before upgrading any shadow-only claim.",
            "Treat ship-tracking as last public indication, not live military truth.",
            "Watch for blocked or missing source families before calling the picture complete.",
        ],
        "freshness_panel": build_freshness_panel(observations),
        "source_layer_summary": build_source_layer_summary(observations),
        "source_artifacts": build_source_artifacts(observations),
        "background_only": [
            {
                "source_name": item.get("source_name", ""),
                "age": item.get("age_label", ""),
                "text_excerpt": item.get("text_excerpt", ""),
            }
            for item in background[:5]
        ],
    }
    verdict.update(build_crisis_sections(request, observations, claim_ledger))
    return verdict


def build_retrieval_run_report(request: dict[str, Any], observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [
        {
            "source_id": item.get("source_id", ""),
            "source_name": item.get("source_name", ""),
            "source_type": item.get("source_type", ""),
            "access_mode": item.get("access_mode", ""),
        }
        for item in observations
    ]
    observed_families = {source_family_for(item.get("source_type", "")) for item in observations}
    return {
        "fetch_order": [item.get("source_id", "") for item in observations],
        "sources_attempted": attempted,
        "sources_blocked": [item for item in attempted if item.get("access_mode") == "blocked"],
        "top_recent_hits": build_latest_signals(observations, limit=5),
        "shadow_to_core_promotions": [item.get("claim_id", "") for item in claim_ledger if item.get("promotion_state") == "core"],
        "missed_expected_source_families": [
            item for item in request.get("expected_source_families", []) if source_family_for(item) not in observed_families
        ],
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    request = result.get("request", {})
    verdict = result.get("verdict_output", {})
    interval = verdict.get("confidence_interval", [0, 0])
    lines = [
        f"# News Index Report: {request.get('topic', 'topic')}",
        "",
        f"One-line judgment ({request.get('analysis_time', '')}, confidence {interval[0]}-{interval[1]}, gate {verdict.get('confidence_gate', 'unknown')}): {verdict.get('core_verdict', '')}",
        "",
        "## Confirmed",
    ]
    lines.extend([f"- {item.get('claim_text', '')}" for item in verdict.get("confirmed", [])] or ["- None"])
    lines.extend(["", "## Not Confirmed"])
    lines.extend([f"- {item.get('claim_text', '')} ({item.get('status', '')})" for item in verdict.get("not_confirmed", [])] or ["- None"])
    lines.extend(["", "## Inference Only"])
    lines.extend([f"- {item.get('claim_text', '')}" for item in verdict.get("inference_only", [])] or ["- None"])

    lines.extend(["", "## Latest Signals First", "", "| Source | Tier | Channel | Age | Rank | Note |", "|---|---:|---|---|---:|---|"])
    for item in verdict.get("latest_signals", []):
        lines.append(
            f"| {item.get('source_name', '')} | {item.get('source_tier', 3)} | {item.get('channel', '')} | "
            f"{item.get('age', '')} | {item.get('rank_score', 0)} | {item.get('text_excerpt', '')} |"
        )

    lines.extend(["", "## Conflict Matrix", "", "| Claim | Status | Supports | Contradictions | Promotion |", "|---|---|---:|---:|---|"])
    for item in verdict.get("conflict_matrix", []):
        lines.append(
            f"| {item.get('claim_id', '')} | {item.get('status', '')} | {item.get('support_count', 0)} | "
            f"{item.get('contradiction_count', 0)} | {item.get('promotion_state', '')} |"
        )

    lines.extend(["", "## Freshness Panel"])
    for item in verdict.get("freshness_panel", []):
        lines.append(
            f"- {item.get('window', '')}: total {item.get('count', 0)}, core {item.get('core_count', 0)}, "
            f"shadow {item.get('shadow_count', 0)}, blocked {item.get('blocked_count', 0)}"
        )

    lines.extend(["", "## Source Layer Summary"])
    summary = verdict.get("source_layer_summary", {})
    lines.append(f"- By channel: {json.dumps(summary.get('by_channel', {}), ensure_ascii=False)}")
    lines.append(f"- By tier: {json.dumps(summary.get('by_tier', {}), ensure_ascii=False)}")
    lines.append(f"- By access mode: {json.dumps(summary.get('by_access_mode', {}), ensure_ascii=False)}")

    source_artifacts = verdict.get("source_artifacts", [])
    if source_artifacts:
        lines.extend(["", "## Source Artifacts"])
        for item in source_artifacts:
            lines.append(
                f"- {item.get('source_name', '')} | tier {item.get('source_tier', 3)} | {item.get('channel', '')} | {item.get('access_mode', '')}"
            )
            lines.append(f"  URL: {item.get('url', '') or 'none'}")
            lines.append(f"  Main post text: {item.get('post_text_raw', '') or 'none'}")
            lines.append(f"  Image summary: {item.get('media_summary', '') or 'none'}")
            lines.append(f"  Screenshot: {item.get('root_post_screenshot_path', '') or 'none'}")

    lines.extend(["", "## Live Tape"])
    lines.extend([f"- [{item.get('source_name', '')}] tier {item.get('source_tier', 3)}, {item.get('age', '')}: {item.get('text_excerpt', '')}" for item in verdict.get("live_tape", [])] or ["- None"])

    if request.get("mode") == "crisis":
        lines.extend(["", "## Negotiation Status Timeline"])
        lines.extend([f"- {item.get('timestamp', '')}: {item.get('source_name', '')} ({item.get('channel', '')}) - {item.get('text_excerpt', '')}" for item in verdict.get("negotiation_status_timeline", [])] or ["- None"])
        lines.extend(["", "## Vessel Movement Table", "", "| Vessel | Last Public Indication | Timestamp | ETA Range | Source |", "|---|---|---|---|---|"])
        vessel_rows = verdict.get("vessel_movement_table", [])
        if vessel_rows:
            for row in vessel_rows:
                lines.append(
                    f"| {', '.join(row.get('vessel_ids', [])) or 'unknown'} | {row.get('last_public_location', '')} | "
                    f"{row.get('timestamp', '')} | {row.get('eta_range', '')} | {row.get('source_name', '')} |"
                )
        else:
            lines.append("| None | None | None | None | None |")
        lines.extend(["", "## Escalation Scenarios"])
        for row in verdict.get("escalation_scenarios", []):
            lines.append(f"- {row.get('scenario', '')}: {row.get('probability_range', '')}; trigger: {row.get('trigger', '')}")

    lines.extend(["", "## What Would Change My View"])
    lines.extend([f"- {item}" for item in verdict.get("next_watch_items", [])] or ["- None"])
    return "\n".join(lines) + "\n"


def run_news_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    claim_texts = claim_text_map_from_request(request)
    observations = [
        normalize_candidate(candidate, request["analysis_time"], claim_texts, index)
        for index, candidate in enumerate(request.get("candidates", []), start=1)
    ]
    observations = dedupe_observations(observations)
    evidence_index = build_claim_evidence(observations)
    observations = rerank_observations(observations, evidence_index)
    claim_ledger = build_claim_ledger(request, observations)
    promote_observation_channels(observations, claim_ledger)
    observations = rerank_observations(observations, build_claim_evidence(observations))
    result = {
        "request": {**request, "analysis_time": isoformat_or_blank(request["analysis_time"])},
        "observations": observations,
        "claim_ledger": claim_ledger,
    }
    result["verdict_output"] = build_verdict_output(request, observations, claim_ledger)
    result["retrieval_run_report"] = build_retrieval_run_report(request, observations, claim_ledger)
    result["retrieval_quality"] = build_retrieval_quality(observations, claim_ledger)
    result["report_markdown"] = build_markdown_report(result)
    return result


def merge_refresh(existing_result: dict[str, Any], refresh_payload: dict[str, Any]) -> dict[str, Any]:
    existing = deepcopy(existing_result)
    base_request = normalize_request(existing.get("request", {}))
    refresh_request = normalize_request(refresh_payload)
    refresh_topic = str(refresh_payload.get("topic", "")).strip()
    refresh_mode = str(refresh_payload.get("mode", "")).strip().lower()
    fresh_cutoff = refresh_request["analysis_time"] - timedelta(hours=24)
    carried_candidates = []
    for observation in safe_list(existing.get("observations")):
        published_at = parse_datetime(observation.get("published_at"), fallback=refresh_request["analysis_time"])
        if published_at and published_at >= fresh_cutoff:
            carried_candidates.append(
                {
                    "source_id": observation.get("source_id", ""),
                    "source_name": observation.get("source_name", ""),
                    "source_type": observation.get("source_type", ""),
                    "published_at": observation.get("published_at", ""),
                    "observed_at": observation.get("observed_at", ""),
                    "url": observation.get("url", ""),
                    "claim_ids": observation.get("claim_ids", []),
                    "entity_ids": observation.get("entity_ids", []),
                    "vessel_ids": observation.get("vessel_ids", []),
                    "text_excerpt": observation.get("text_excerpt", ""),
                    "position_hint": observation.get("position_hint"),
                    "geo_hint": observation.get("geo_hint"),
                    "access_mode": observation.get("access_mode", "public"),
                    "claim_states": observation.get("claim_states", {}),
                }
            )

    combined_request = {
        **base_request,
        "analysis_time": refresh_request["analysis_time"],
        "topic": refresh_topic or base_request.get("topic"),
        "questions": refresh_request.get("questions") or base_request.get("questions"),
        "claims": refresh_request.get("claims") or base_request.get("claims"),
        "market_relevance": refresh_request.get("market_relevance") or base_request.get("market_relevance"),
        "expected_source_families": refresh_request.get("expected_source_families") or base_request.get("expected_source_families"),
        "mode": "crisis" if refresh_mode == "crisis" else base_request.get("mode"),
        "candidates": carried_candidates + refresh_request.get("candidates", []),
    }

    refreshed = run_news_index(combined_request)
    previous_ids = {item.get("source_id", "") for item in safe_list(existing.get("observations")) if item.get("source_id")}
    refreshed["refresh_summary"] = {
        "new_source_ids": [item.get("source_id", "") for item in refreshed.get("observations", []) if item.get("source_id", "") not in previous_ids],
        "previous_analysis_time": existing.get("request", {}).get("analysis_time", ""),
        "refresh_analysis_time": refreshed.get("request", {}).get("analysis_time", ""),
    }
    return refreshed


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

