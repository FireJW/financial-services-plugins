#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from news_index_runtime import isoformat_or_blank, short_excerpt


CONTRACT_VERSION = "article_evidence_bundle_v1"


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


def path_exists(value: Any) -> bool:
    try:
        text = clean_text(value)
        return bool(text) and Path(text).exists()
    except OSError:
        return False


def is_source_result(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output"))


def extract_runtime_result(source_result: dict[str, Any]) -> dict[str, Any]:
    runtime = safe_dict(source_result.get("retrieval_result"))
    if runtime:
        return runtime
    if safe_list(source_result.get("observations")) or safe_dict(source_result.get("verdict_output")):
        return source_result
    adapted = deepcopy(source_result)
    adapted["request"] = safe_dict(adapted.get("request")) or safe_dict(adapted.get("retrieval_request"))
    adapted["observations"] = safe_list(adapted.get("observations")) or safe_list(adapted.get("source_observations"))
    adapted["claim_ledger"] = safe_list(adapted.get("claim_ledger"))
    adapted["verdict_output"] = safe_dict(adapted.get("verdict_output"))
    return adapted


def claim_texts(value: Any) -> list[str]:
    texts: list[str] = []
    for item in safe_list(value):
        text = clean_text(item.get("claim_text") if isinstance(item, dict) else item)
        if text and text not in texts:
            texts.append(text)
    return texts


def claim_texts_with_map(value: Any, text_map: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for item in safe_list(value):
        if isinstance(item, dict):
            claim_id = clean_text(item.get("claim_id"))
            text = clean_text(text_map.get(claim_id) or item.get("claim_text"))
        else:
            text = clean_text(item)
        if text and text not in texts:
            texts.append(text)
    return texts


def normalize_latest_signals(value: Any) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        signals.append(
            {
                "source_name": clean_text(item.get("source_name")),
                "source_tier": int(item.get("source_tier", 3)),
                "channel": clean_text(item.get("channel")),
                "age": clean_text(item.get("age")),
                "text_excerpt": clean_text(item.get("text_excerpt")),
            }
        )
    return signals


def build_source_summary_and_digest(source_result: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = extract_runtime_result(source_result)
    verdict = safe_dict(runtime.get("verdict_output"))
    observations = safe_list(runtime.get("observations"))
    source_request = (
        safe_dict(source_result.get("request"))
        or safe_dict(source_result.get("retrieval_request"))
        or safe_dict(runtime.get("request"))
    )
    claim_text_zh_map = {
        clean_text(item.get("claim_id")): clean_text(item.get("claim_text_zh"))
        for item in safe_list(source_request.get("claims"))
        if isinstance(item, dict) and clean_text(item.get("claim_id")) and clean_text(item.get("claim_text_zh"))
    }
    blocked = sum(1 for item in observations if clean_text(item.get("access_mode")) == "blocked")
    core_sources = sum(1 for item in observations if clean_text(item.get("channel")) == "core")
    shadow_sources = sum(1 for item in observations if clean_text(item.get("channel")) == "shadow")
    summary = {
        "source_kind": "x_index" if safe_list(source_result.get("x_posts")) or safe_dict(source_result.get("evidence_pack")) else "news_index",
        "topic": clean_text(request.get("topic")),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "observation_count": len(observations),
        "blocked_source_count": blocked,
        "core_source_count": core_sources,
        "shadow_source_count": shadow_sources,
        "confidence_interval": verdict.get("confidence_interval", [0, 0]),
        "confidence_gate": clean_text(verdict.get("confidence_gate")),
        "core_verdict": clean_text(verdict.get("core_verdict")),
        "market_relevance": clean_string_list(verdict.get("market_relevance")),
        "market_relevance_zh": clean_string_list(source_request.get("market_relevance_zh")),
    }
    digest = {
        "core_verdict": summary["core_verdict"],
        "confirmed": claim_texts(verdict.get("confirmed")),
        "not_confirmed": claim_texts(verdict.get("not_confirmed")),
        "inference_only": claim_texts(verdict.get("inference_only")),
        "confirmed_zh": claim_texts_with_map(verdict.get("confirmed"), claim_text_zh_map),
        "not_confirmed_zh": claim_texts_with_map(verdict.get("not_confirmed"), claim_text_zh_map),
        "inference_only_zh": claim_texts_with_map(verdict.get("inference_only"), claim_text_zh_map),
        "latest_signals": normalize_latest_signals(verdict.get("latest_signals")),
        "next_watch_items": clean_string_list(verdict.get("next_watch_items")),
        "confidence_interval": summary["confidence_interval"],
        "confidence_gate": summary["confidence_gate"],
        "market_relevance": summary["market_relevance"],
        "market_relevance_zh": summary["market_relevance_zh"],
    }
    return summary, digest


def build_citations(source_result: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = extract_runtime_result(source_result)
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for observation in safe_list(runtime.get("observations")):
        if not isinstance(observation, dict):
            continue
        key = (clean_text(observation.get("source_id") or observation.get("source_name")), clean_text(observation.get("url")))
        if key in seen:
            continue
        seen.add(key)
        excerpt = clean_text(
            observation.get("combined_summary")
            or observation.get("post_summary")
            or observation.get("media_summary")
            or observation.get("post_text_raw")
            or observation.get("text_excerpt")
        )
        citations.append(
            {
                "citation_id": f"S{len(citations) + 1}",
                "source_id": clean_text(observation.get("source_id")),
                "source_name": clean_text(observation.get("source_name")) or "Unknown source",
                "url": clean_text(observation.get("url")),
                "source_tier": int(observation.get("source_tier", 3)),
                "channel": clean_text(observation.get("channel")),
                "access_mode": clean_text(observation.get("access_mode")),
                "excerpt": short_excerpt(excerpt, limit=180),
            }
        )
    return citations


def citation_by_source_id(citations: list[dict[str, Any]]) -> dict[str, str]:
    return {
        clean_text(item.get("source_id")): clean_text(item.get("citation_id"))
        for item in citations
        if clean_text(item.get("source_id")) and clean_text(item.get("citation_id"))
    }


def meaningful_image_hint(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    if cleaned.lower().strip(" .,:;!?") in {"image", "images", "photo", "photos", "picture", "pictures", "media", "graphic", "鍥惧儚", "鍥剧墖", "鐓х墖"}:
        return ""
    return cleaned


def candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("score", 0)),
        1 if path_exists(item.get("path")) else 0,
        1 if clean_text(item.get("summary") or item.get("caption")) else 0,
    )


def build_image_candidates(source_result: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        role: str,
        source_name: str,
        path: str,
        source_url: str,
        summary: str,
        access_mode: str,
        relevance: str,
        source_tier: int,
        alt_text: str = "",
        capture_method: str = "",
    ) -> None:
        clean_path = clean_text(path)
        clean_url = clean_text(source_url)
        if not clean_path and not clean_url:
            return
        key = (clean_text(role), clean_path, clean_url)
        if key in seen:
            return
        seen.add(key)

        if request.get("image_strategy") == "screenshots_only" and role != "root_post_screenshot":
            return

        score = 0
        if role == "post_media":
            score += 40
        elif role == "root_post_screenshot":
            score += 24
        score += {"high": 20, "medium": 10, "low": 2}.get(clean_text(relevance), 5)
        score += {0: 12, 1: 10, 2: 6, 3: 0}.get(int(source_tier), 0)
        if clean_text(summary):
            score += 14
        if clean_path:
            score += 12
            if path_exists(clean_path):
                score += 10
        elif clean_url:
            score += 4
        if clean_text(access_mode) == "blocked" and role == "root_post_screenshot":
            score += 12
        if request.get("image_strategy") == "prefer_images":
            score += 10 if role == "post_media" else 4
        if request.get("draft_mode") in {"image_first", "image_only"}:
            score += 10

        candidates.append(
            {
                "image_id": f"IMG-{len(candidates) + 1:02d}",
                "role": role,
                "source_name": clean_text(source_name),
                "path": clean_path,
                "source_url": clean_url,
                "summary": clean_text(summary),
                "caption": clean_text(summary),
                "access_mode": clean_text(access_mode) or "unknown",
                "relevance": clean_text(relevance) or "medium",
                "source_tier": int(source_tier),
                "alt_text": clean_text(alt_text),
                "capture_method": clean_text(capture_method),
                "score": score,
            }
        )

    for post in safe_list(source_result.get("x_posts")):
        if not isinstance(post, dict):
            continue
        source_name = f"X @{clean_text(post.get('author_handle') or post.get('author_display_name') or 'post')}"
        access_mode = clean_text(post.get("access_mode")) or "public"
        post_summary = clean_text(post.get("media_summary") or post.get("post_summary") or post.get("post_text_raw"))
        add(
            "root_post_screenshot",
            source_name,
            clean_text(post.get("root_post_screenshot_path")),
            clean_text(post.get("post_url")),
            post_summary,
            access_mode,
            "medium",
            3,
        )
        for media in safe_list(post.get("media_items")):
            if not isinstance(media, dict):
                continue
            add(
                "post_media",
                source_name,
                clean_text(media.get("local_artifact_path")),
                clean_text(media.get("source_url")),
                clean_text(media.get("ocr_summary") or media.get("ocr_text_raw") or meaningful_image_hint(media.get("alt_text"))),
                access_mode,
                clean_text(media.get("image_relevance_to_post")) or "medium",
                3,
                meaningful_image_hint(media.get("alt_text")),
                clean_text(media.get("capture_method")),
            )

    verdict = safe_dict(extract_runtime_result(source_result).get("verdict_output"))
    for item in safe_list(verdict.get("source_artifacts")):
        if not isinstance(item, dict):
            continue
        add(
            "root_post_screenshot",
            clean_text(item.get("source_name")) or "Artifact source",
            clean_text(item.get("root_post_screenshot_path")),
            clean_text(item.get("url")),
            clean_text(item.get("media_summary") or item.get("post_summary") or item.get("combined_summary") or item.get("post_text_raw")),
            clean_text(item.get("access_mode")) or "public",
            "medium",
            int(item.get("source_tier", 3)),
        )

    candidates.sort(key=candidate_sort_key, reverse=True)
    return candidates


def build_shared_evidence_bundle(source_result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    runtime = extract_runtime_result(source_result)
    source_summary, evidence_digest = build_source_summary_and_digest(source_result, request)
    citations = build_citations(source_result)
    return {
        "contract_version": CONTRACT_VERSION,
        "topic": clean_text(request.get("topic")),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "source_kind": clean_text(source_summary.get("source_kind")),
        "source_summary": source_summary,
        "evidence_digest": evidence_digest,
        "citations": citations,
        "citation_by_source_id": citation_by_source_id(citations),
        "image_candidates": build_image_candidates(source_result, request),
        "observations": deepcopy(safe_list(runtime.get("observations"))),
        "claim_ledger": deepcopy(safe_list(runtime.get("claim_ledger"))),
    }


__all__ = [
    "CONTRACT_VERSION",
    "build_citations",
    "build_image_candidates",
    "build_shared_evidence_bundle",
    "build_source_summary_and_digest",
    "citation_by_source_id",
    "clean_string_list",
    "clean_text",
    "extract_runtime_result",
    "safe_dict",
    "safe_list",
]
