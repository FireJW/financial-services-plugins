#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from news_index_runtime import (
    isoformat_or_blank,
    load_json,
    parse_datetime,
    short_excerpt,
    slugify,
    write_json,
)


WHITESPACE_RE = re.compile(r"\s+")
ALNUM_RE = re.compile(r"[^a-z0-9]+")
CONTENT_MODES = {"mixed", "image_first", "image_only"}


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_text(value: Any) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in safe_list(values):
        text = clean_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def path_exists(path_value: Any) -> bool:
    path_text = clean_text(path_value)
    return bool(path_text) and Path(path_text).exists()


def normalize_content_mode(value: Any) -> str:
    text = clean_text(value).lower()
    return text if text in CONTENT_MODES else "mixed"


def normalize_source_kind(payload: dict[str, Any]) -> str:
    if safe_list(payload.get("x_posts")) or safe_dict(payload.get("evidence_pack")):
        return "x_index"
    if safe_list(payload.get("observations")) or safe_dict(payload.get("verdict_output")):
        return "news_index"
    retrieval_result = safe_dict(payload.get("retrieval_result"))
    if safe_list(retrieval_result.get("observations")) or safe_dict(retrieval_result.get("verdict_output")):
        return "x_index"
    raise ValueError("Expected an x-index or news-index result payload")


def retrieval_result_for(source_payload: dict[str, Any]) -> dict[str, Any]:
    source_kind = normalize_source_kind(source_payload)
    if source_kind == "x_index":
        retrieval_result = safe_dict(source_payload.get("retrieval_result"))
        if retrieval_result:
            return retrieval_result
    return source_payload


def clean_claim_texts(value: Any) -> list[str]:
    claims: list[str] = []
    for item in safe_list(value):
        text = clean_text(item.get("claim_text") if isinstance(item, dict) else item)
        if text and text not in claims:
            claims.append(text)
    return claims


def make_source_key(source_name: str, url: str) -> str:
    return ALNUM_RE.sub("-", f"{source_name}-{url}".lower()).strip("-") or "source"


def normalize_embed_target(path_value: Any, source_url: Any) -> str:
    path_text = clean_text(path_value)
    if path_text:
        return path_text.replace("\\", "/")
    return clean_text(source_url)


def load_source_payload(raw_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    inline_payload = safe_dict(raw_payload.get("source_result"))
    if inline_payload:
        return deepcopy(inline_payload), clean_text(raw_payload.get("source_result_path") or raw_payload.get("source_path"))

    source_path = clean_text(
        raw_payload.get("source_path")
        or raw_payload.get("source_result_path")
        or raw_payload.get("input_result_path")
    )
    if not source_path:
        raise ValueError("source_result or source_path is required")
    return load_json(Path(source_path).resolve()), source_path


def normalize_draft_request(raw_payload: dict[str, Any], source_payload: dict[str, Any], source_path: str) -> dict[str, Any]:
    source_kind = normalize_source_kind(source_payload)
    source_request = safe_dict(source_payload.get("request"))
    nested_request = safe_dict(retrieval_result_for(source_payload).get("request"))
    analysis_time = (
        parse_datetime(raw_payload.get("analysis_time"))
        or parse_datetime(source_request.get("analysis_time"))
        or parse_datetime(nested_request.get("analysis_time"))
        or now_utc()
    )
    topic = (
        clean_text(raw_payload.get("topic"))
        or clean_text(source_request.get("topic"))
        or clean_text(nested_request.get("topic"))
        or "article-topic"
    )
    image_strategy = clean_text(raw_payload.get("image_strategy") or "mixed")
    prefer_screenshots = bool_value(raw_payload.get("prefer_screenshots"), default=image_strategy == "screenshots_only")
    content_mode = normalize_content_mode(raw_payload.get("content_mode") or raw_payload.get("article_mode"))
    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "article-draft" / slugify(topic, "article-topic") / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )
    return {
        "topic": topic,
        "analysis_time": analysis_time,
        "source_kind": source_kind,
        "source_path": source_path,
        "title_hint": clean_text(raw_payload.get("title_hint")),
        "subtitle_hint": clean_text(raw_payload.get("subtitle_hint")),
        "angle": clean_text(raw_payload.get("angle")),
        "tone": clean_text(raw_payload.get("tone")) or "clear",
        "target_length": max(300, int(raw_payload.get("target_length", raw_payload.get("target_length_chars", 1000)))),
        "max_images": max(0, min(int(raw_payload.get("max_images", 3)), 8)),
        "content_mode": content_mode,
        "include_image_only_sources": bool_value(raw_payload.get("include_image_only_sources"), default=True),
        "require_local_images": bool_value(raw_payload.get("require_local_images"), default=False),
        "prefer_screenshots": prefer_screenshots,
        "image_strategy": "screenshots_only" if prefer_screenshots else image_strategy or "mixed",
        "focus_points": unique_strings(raw_payload.get("focus_points") or raw_payload.get("must_include")),
        "must_include": unique_strings(raw_payload.get("must_include") or raw_payload.get("focus_points")),
        "must_avoid": unique_strings(raw_payload.get("must_avoid")),
        "output_dir": output_dir,
    }


def build_source_summary(source_payload: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    retrieval_result = retrieval_result_for(source_payload)
    verdict = safe_dict(retrieval_result.get("verdict_output"))
    observations = safe_list(retrieval_result.get("observations"))
    blocked_source_count = sum(1 for item in observations if clean_text(item.get("access_mode")) == "blocked")
    return {
        "source_kind": request.get("source_kind", "news_index"),
        "topic": request.get("topic", "article-topic"),
        "analysis_time": isoformat_or_blank(request.get("analysis_time")),
        "blocked_source_count": blocked_source_count,
        "confidence_interval": verdict.get("confidence_interval", [0, 0]),
        "confidence_gate": clean_text(verdict.get("confidence_gate")),
        "core_verdict": clean_text(verdict.get("core_verdict")),
    }


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


def build_evidence_digest(source_payload: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    retrieval_result = retrieval_result_for(source_payload)
    verdict = safe_dict(retrieval_result.get("verdict_output"))
    return {
        "core_verdict": clean_text(verdict.get("core_verdict")),
        "confirmed": clean_claim_texts(verdict.get("confirmed")),
        "not_confirmed": clean_claim_texts(verdict.get("not_confirmed")),
        "inference_only": clean_claim_texts(verdict.get("inference_only")),
        "latest_signals": normalize_latest_signals(verdict.get("latest_signals")),
        "next_watch_items": unique_strings(verdict.get("next_watch_items")),
        "confidence_interval": verdict.get("confidence_interval", [0, 0]),
        "confidence_gate": clean_text(verdict.get("confidence_gate")),
    }


def build_citations(source_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    retrieval_result = retrieval_result_for(source_payload)
    verdict = safe_dict(retrieval_result.get("verdict_output"))
    source_candidates = safe_list(verdict.get("source_artifacts")) or safe_list(retrieval_result.get("observations"))
    citations: list[dict[str, Any]] = []
    citation_ids: dict[str, str] = {}
    for index, source in enumerate(source_candidates, start=1):
        source_name = clean_text(source.get("source_name")) or f"Source {index}"
        url = clean_text(source.get("url"))
        key = make_source_key(source_name, url)
        if key in citation_ids:
            continue
        citation_id = f"S{len(citations) + 1}"
        citation_ids[key] = citation_id
        excerpt = (
            clean_text(source.get("combined_summary"))
            or clean_text(source.get("post_summary"))
            or clean_text(source.get("media_summary"))
            or clean_text(source.get("post_text_raw"))
            or clean_text(source.get("text_excerpt"))
            or url
        )
        citations.append(
            {
                "citation_id": citation_id,
                "source_name": source_name,
                "url": url,
                "published_at": clean_text(source.get("published_at") or source.get("observed_at")),
                "source_tier": int(source.get("source_tier", 3)),
                "channel": clean_text(source.get("channel")),
                "access_mode": clean_text(source.get("access_mode")) or "unknown",
                "excerpt": short_excerpt(excerpt, limit=220),
            }
        )
    return citations, citation_ids


def citation_id_for(citation_ids: dict[str, str], source_name: str, url: str) -> str:
    return citation_ids.get(make_source_key(source_name, url), "")


def add_image_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    *,
    role: str,
    source_name: str,
    image_path: str,
    source_url: str,
    summary: str,
    relevance: str,
    access_mode: str,
    source_tier: int,
    citation_id: str,
) -> None:
    path_text = clean_text(image_path)
    url_text = clean_text(source_url)
    if not path_text and not url_text:
        return
    key = (clean_text(role), path_text, url_text, clean_text(source_name))
    if key in seen:
        return
    seen.add(key)
    candidates.append(
        {
            "role": clean_text(role) or "image",
            "kind": clean_text(role) or "image",
            "image_path": path_text,
            "path": path_text,
            "source_url": url_text,
            "source_name": clean_text(source_name) or "Unknown source",
            "summary": clean_text(summary),
            "relevance": clean_text(relevance) or "medium",
            "access_mode": clean_text(access_mode) or "unknown",
            "source_tier": int(source_tier),
            "citation_id": clean_text(citation_id),
        }
    )


def build_image_candidates(source_payload: dict[str, Any], citation_ids: dict[str, str]) -> list[dict[str, Any]]:
    retrieval_result = retrieval_result_for(source_payload)
    verdict = safe_dict(retrieval_result.get("verdict_output"))
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def ingest_artifact_manifest(owner: dict[str, Any], source_name: str, source_url: str, citation_id: str, source_tier: int) -> None:
        owner_summary = (
            clean_text(owner.get("media_summary"))
            or clean_text(owner.get("post_summary"))
            or clean_text(owner.get("combined_summary"))
            or clean_text(owner.get("post_text_raw"))
        )
        for artifact in safe_list(owner.get("artifact_manifest")):
            if not isinstance(artifact, dict):
                continue
            role = clean_text(artifact.get("role")) or "artifact"
            add_image_candidate(
                candidates,
                seen,
                role=role,
                source_name=source_name,
                image_path=clean_text(artifact.get("path")),
                source_url=clean_text(artifact.get("source_url")) or source_url,
                summary=owner_summary,
                relevance="medium",
                access_mode=clean_text(owner.get("access_mode")) or "unknown",
                source_tier=source_tier,
                citation_id=citation_id,
            )

    for item in safe_list(verdict.get("source_artifacts")):
        if not isinstance(item, dict):
            continue
        source_name = clean_text(item.get("source_name")) or "Artifact source"
        source_url = clean_text(item.get("url"))
        citation_id = citation_id_for(citation_ids, source_name, source_url)
        add_image_candidate(
            candidates,
            seen,
            role="root_post_screenshot",
            source_name=source_name,
            image_path=clean_text(item.get("root_post_screenshot_path")),
            source_url=source_url,
            summary=clean_text(item.get("post_summary")) or clean_text(item.get("media_summary")) or clean_text(item.get("post_text_raw")),
            relevance="medium",
            access_mode=clean_text(item.get("access_mode")) or "unknown",
            source_tier=int(item.get("source_tier", 3)),
            citation_id=citation_id,
        )
        ingest_artifact_manifest(item, source_name, source_url, citation_id, int(item.get("source_tier", 3)))

    for item in safe_list(retrieval_result.get("observations")):
        if not isinstance(item, dict):
            continue
        source_name = clean_text(item.get("source_name")) or "Observation source"
        source_url = clean_text(item.get("url"))
        citation_id = citation_id_for(citation_ids, source_name, source_url)
        ingest_artifact_manifest(item, source_name, source_url, citation_id, int(item.get("source_tier", 3)))

    for post in safe_list(source_payload.get("x_posts")):
        if not isinstance(post, dict):
            continue
        handle = clean_text(post.get("author_handle"))
        source_name = f"X @{handle}" if handle else clean_text(post.get("author_display_name")) or "X post"
        post_url = clean_text(post.get("post_url"))
        citation_id = citation_id_for(citation_ids, source_name, post_url)
        add_image_candidate(
            candidates,
            seen,
            role="root_post_screenshot",
            source_name=source_name,
            image_path=clean_text(post.get("root_post_screenshot_path")),
            source_url=post_url,
            summary=clean_text(post.get("post_summary")) or clean_text(post.get("post_text_raw")),
            relevance="medium",
            access_mode=clean_text(post.get("access_mode")) or "unknown",
            source_tier=3,
            citation_id=citation_id,
        )
        for media_item in safe_list(post.get("media_items")):
            if not isinstance(media_item, dict):
                continue
            add_image_candidate(
                candidates,
                seen,
                role=clean_text(media_item.get("media_type")) or "post_media",
                source_name=source_name,
                image_path=clean_text(media_item.get("local_artifact_path")),
                source_url=clean_text(media_item.get("source_url")),
                summary=clean_text(media_item.get("ocr_summary")) or clean_text(media_item.get("ocr_text_raw")),
                relevance=clean_text(media_item.get("image_relevance_to_post")) or "medium",
                access_mode=clean_text(post.get("access_mode")) or "unknown",
                source_tier=3,
                citation_id=citation_id,
            )
        ingest_artifact_manifest(post, source_name, post_url, citation_id, 3)
    return candidates


def score_image_candidate(candidate: dict[str, Any], request: dict[str, Any]) -> int:
    path_text = clean_text(candidate.get("image_path") or candidate.get("path"))
    source_url = clean_text(candidate.get("source_url"))
    if request.get("require_local_images") and not path_text:
        return -999

    score = 0
    if path_text:
        score += 35 if path_exists(path_text) else 25
    elif source_url:
        score += 10

    role = clean_text(candidate.get("role") or candidate.get("kind"))
    if role in {"image", "post_media"}:
        score += 18
    elif role == "root_post_screenshot":
        score += 12
    else:
        score += 8

    score += {"high": 20, "medium": 10, "low": 2}.get(clean_text(candidate.get("relevance")), 5)
    if clean_text(candidate.get("summary")):
        score += 18
    elif not request.get("include_image_only_sources", True):
        score -= 40

    score += {0: 12, 1: 9, 2: 5, 3: 0}.get(int(candidate.get("source_tier", 3)), 0)
    access_mode = clean_text(candidate.get("access_mode"))
    if access_mode == "public":
        score += 8
    elif access_mode == "blocked" and path_text:
        score += 6
    if request.get("prefer_screenshots") and role == "root_post_screenshot":
        score += 10
    return score


def build_candidate_caption(candidate: dict[str, Any]) -> str:
    summary = clean_text(candidate.get("summary"))
    role = clean_text(candidate.get("role") or candidate.get("kind"))
    access_mode = clean_text(candidate.get("access_mode"))
    if summary:
        if access_mode == "blocked" and role == "root_post_screenshot":
            return f"{summary} This is preserved as a screenshot clue because the page text was blocked."
        return summary
    if role == "root_post_screenshot":
        return "Root post screenshot kept as a source artifact."
    return "Key supporting image."


def select_images(candidates: list[dict[str, Any]], request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        scored = deepcopy(candidate)
        scored["selection_score"] = score_image_candidate(scored, request)
        scored["caption"] = build_candidate_caption(scored)
        ranked.append(scored)
    ranked.sort(
        key=lambda item: (
            int(item.get("selection_score", -999)),
            1 if clean_text(item.get("summary")) else 0,
            1 if clean_text(item.get("image_path")) else 0,
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    for item in ranked:
        if int(item.get("selection_score", -999)) < 0:
            continue
        asset_id = clean_text(item.get("asset_id")) or f"img-{len(selected) + 1:02d}"
        image_id = clean_text(item.get("image_id")) or f"IMG-{len(selected) + 1:02d}"
        path_text = clean_text(item.get("image_path") or item.get("path"))
        source_url = clean_text(item.get("source_url"))
        selected.append(
            {
                "asset_id": asset_id,
                "image_id": image_id,
                "role": clean_text(item.get("role") or item.get("kind")) or "image",
                "kind": clean_text(item.get("kind") or item.get("role")) or "image",
                "image_path": path_text,
                "path": path_text,
                "embed_url": normalize_embed_target(path_text, source_url),
                "render_target": path_text or source_url,
                "source_url": source_url,
                "source_name": clean_text(item.get("source_name")) or "Unknown source",
                "citation_id": clean_text(item.get("citation_id")),
                "caption": clean_text(item.get("caption")),
                "summary": clean_text(item.get("summary")),
                "source_tier": int(item.get("source_tier", 3)),
                "channel": clean_text(item.get("channel")),
                "access_mode": clean_text(item.get("access_mode")) or "unknown",
                "status": "local_ready" if path_exists(path_text) else "remote_only" if source_url else "missing",
                "selection_score": int(item.get("selection_score", 0)),
                "placement_hint": "hero" if not selected else f"section-{min(len(selected) + 1, 3)}",
                "placement": "after_lede" if not selected else f"after_section_{min(len(selected) + 1, 3)}",
            }
        )
        if len(selected) >= int(request.get("max_images", 3)):
            break
    return selected, ranked


def build_draft_context(source_payload: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    citations, citation_ids = build_citations(source_payload)
    source_summary = build_source_summary(source_payload, request)
    evidence_digest = build_evidence_digest(source_payload, request)
    image_candidates = build_image_candidates(source_payload, citation_ids)
    selected_images, available_images = select_images(image_candidates, request)
    retrieval_result = retrieval_result_for(source_payload)
    verdict = safe_dict(retrieval_result.get("verdict_output"))
    return {
        "source_summary": source_summary,
        "evidence_digest": evidence_digest,
        "source_kind": source_summary.get("source_kind"),
        "topic": source_summary.get("topic"),
        "analysis_time": source_summary.get("analysis_time"),
        "core_verdict": source_summary.get("core_verdict"),
        "confirmed_claims": evidence_digest.get("confirmed", []),
        "not_confirmed_claims": evidence_digest.get("not_confirmed", []),
        "inference_only_claims": evidence_digest.get("inference_only", []),
        "latest_signals": evidence_digest.get("latest_signals", []),
        "next_watch_items": evidence_digest.get("next_watch_items", []),
        "market_relevance": unique_strings(verdict.get("market_relevance")),
        "citations": citations,
        "citation_candidates": citations,
        "selected_images": selected_images,
        "available_images": available_images,
        "image_candidates": available_images,
        "source_result_path": request.get("source_path", ""),
    }


def citation_suffix(citation_ids: list[str]) -> str:
    cleaned = [clean_text(item) for item in citation_ids if clean_text(item)]
    return f" [{', '.join(cleaned)}]" if cleaned else ""


def build_title(request: dict[str, Any], source_summary: dict[str, Any], evidence_digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    if clean_text(request.get("title_hint")):
        return clean_text(request.get("title_hint"))
    topic = clean_text(source_summary.get("topic")) or clean_text(request.get("topic")) or "Article topic"
    content_mode = request.get("content_mode", "mixed")
    if content_mode == "image_only":
        return f"{topic}: key visuals and what they show"
    if content_mode == "image_first" and selected_images:
        return f"{topic}: image-led snapshot with source boundaries"
    if evidence_digest.get("confirmed"):
        return f"{topic}: what is confirmed and what is not"
    if selected_images:
        return f"{topic}: public signals, key visuals, and open questions"
    return f"{topic}: current public evidence snapshot"


def build_subtitle(request: dict[str, Any], source_summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    if clean_text(request.get("subtitle_hint")):
        return clean_text(request.get("subtitle_hint"))
    if request.get("content_mode") == "image_only":
        return "Image-led draft package built from saved screenshots and media artifacts."
    if request.get("content_mode") == "image_first":
        return "Text stays secondary; the selected visuals carry the main evidence load."
    if source_summary.get("source_kind") == "x_index" and selected_images:
        return "Built from saved X post records, screenshots, and image summaries."
    return "Built from the current indexed result with explicit source boundaries."


def latest_signal_sentence(evidence_digest: dict[str, Any]) -> str:
    signals = safe_list(evidence_digest.get("latest_signals"))
    if not signals:
        return "Recent public signals are still sparse, so no single clue should be treated as settled fact."
    parts: list[str] = []
    for item in signals[:3]:
        parts.append(
            f"{clean_text(item.get('source_name')) or 'Unknown source'} ({clean_text(item.get('age')) or 'time unknown'}) said: "
            f"{short_excerpt(clean_text(item.get('text_excerpt')), limit=90)}"
        )
    return "Most recent signals first: " + "; ".join(parts) + "."


def build_image_lines(selected_images: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in selected_images[:3]:
        placement = "Lead image" if clean_text(item.get("placement_hint")) == "hero" else "Supporting image"
        lines.append(
            f"{placement} from {clean_text(item.get('source_name'))}: {clean_text(item.get('caption'))}"
            f"{citation_suffix([clean_text(item.get('citation_id'))])}"
        )
    return lines


def join_claims(items: list[str], fallback: str) -> str:
    return "; ".join(items[:4]) if items else fallback


def build_sections(request: dict[str, Any], draft_context: dict[str, Any]) -> list[dict[str, Any]]:
    source_summary = safe_dict(draft_context.get("source_summary"))
    evidence_digest = safe_dict(draft_context.get("evidence_digest"))
    selected_images = safe_list(draft_context.get("selected_images"))
    top_citations = [clean_text(item.get("citation_id")) for item in safe_list(draft_context.get("citations"))[:2]]
    content_mode = request.get("content_mode", "mixed")

    sections: list[dict[str, Any]] = []
    if content_mode == "image_only":
        sections.append(
            {
                "heading": "What the images show",
                "paragraph": join_claims(
                    build_image_lines(selected_images),
                    "No usable local or remote images were selected for this draft.",
                )
                + citation_suffix(top_citations),
            }
        )
        sections.append(
            {
                "heading": "How to use the visuals",
                "paragraph": (
                    "Use the first image as the anchor visual and treat later images as supporting exhibits. "
                    "Do not let a screenshot or chart make a stronger claim than its source supports."
                ),
            }
        )
        sections.append(
            {
                "heading": "Source boundaries",
                "paragraph": (
                    f"Core read: {clean_text(source_summary.get('core_verdict')) or 'The evidence remains partial.'} "
                    f"Blocked sources: {int(source_summary.get('blocked_source_count', 0))}. "
                    f"{latest_signal_sentence(evidence_digest)}"
                ),
            }
        )
    else:
        sections.append(
            {
                "heading": "Bottom line",
                "paragraph": (
                    f"As of {clean_text(source_summary.get('analysis_time'))}, the safest lead is: "
                    f"{clean_text(source_summary.get('core_verdict')) or 'public evidence is still incomplete.'}"
                    f"{citation_suffix(top_citations)}"
                ),
            }
        )
        if content_mode == "image_first":
            sections.append(
                {
                    "heading": "What the images add",
                    "paragraph": join_claims(
                        build_image_lines(selected_images),
                        "No image was strong enough to lead this draft.",
                    ),
                }
            )
        sections.append(
            {
                "heading": "Confirmed vs unconfirmed",
                "paragraph": (
                    "Confirmed: "
                    + join_claims(evidence_digest.get("confirmed", []), "nothing strong enough yet")
                    + ". Not confirmed: "
                    + join_claims(evidence_digest.get("not_confirmed", []), "no additional items")
                    + ". Inference only: "
                    + join_claims(evidence_digest.get("inference_only", []), "none listed")
                    + "."
                ),
            }
        )
        if content_mode != "image_first":
            sections.append(
                {
                    "heading": "What the images add",
                    "paragraph": join_claims(
                        build_image_lines(selected_images),
                        "No image was strong enough to add beyond the text evidence.",
                    ),
                }
            )
        sections.append({"heading": "Latest signals", "paragraph": latest_signal_sentence(evidence_digest)})
        sections.append(
            {
                "heading": "Source boundaries",
                "paragraph": (
                    f"Blocked sources: {int(source_summary.get('blocked_source_count', 0))}. "
                    "Keep shadow signals and image clues separate from confirmed fact unless stronger sources catch up."
                ),
            }
        )

    if unique_strings(request.get("must_include")):
        sections.append(
            {
                "heading": "Required focus points",
                "paragraph": "Requested focus points: " + "; ".join(unique_strings(request.get("must_include"))) + ".",
            }
        )
    if safe_list(evidence_digest.get("next_watch_items")):
        sections.append(
            {
                "heading": "What would change the view",
                "paragraph": "; ".join(safe_list(evidence_digest.get("next_watch_items"))[:4]) + ".",
            }
        )
    normalized_sections: list[dict[str, Any]] = []
    for section in sections:
        heading = clean_text(section.get("heading"))
        paragraph = clean_text(section.get("paragraph"))
        normalized_sections.append({"heading": heading, "paragraph": paragraph, "content": paragraph})
    return normalized_sections


def build_body_markdown(title: str, subtitle: str, sections: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", subtitle]
    for section in sections:
        lines.extend(["", f"## {clean_text(section.get('heading'))}", clean_text(section.get("paragraph"))])
    return "\n".join(lines).strip() + "\n"


def apply_must_avoid(text: str, must_avoid: list[str]) -> str:
    updated = text
    for phrase in must_avoid:
        updated = updated.replace(phrase, "")
    return updated


def join_sections_as_text(sections: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for section in sections:
        heading = clean_text(section.get("heading"))
        paragraph = clean_text(section.get("paragraph"))
        if heading:
            chunks.append(heading)
        if paragraph:
            chunks.append(paragraph)
    return "\n".join(chunks).strip()


def build_editor_notes(request: dict[str, Any], source_summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    if int(source_summary.get("blocked_source_count", 0)) > 0:
        notes.append("Some sources were blocked or background-only. Do not present those clues as confirmed fact.")
    if not selected_images:
        notes.append("No usable image asset was selected for this draft.")
    if request.get("content_mode") == "image_only" and not selected_images:
        notes.append("Image-only mode is weak here because there is no selected visual evidence.")
    if request.get("require_local_images") and any(item.get("status") != "local_ready" for item in selected_images):
        notes.append("At least one selected image is not saved locally.")
    return notes


def draft_metrics(body_markdown: str, images: list[dict[str, Any]], citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "char_count": len(clean_text(body_markdown).replace(" ", "")),
        "section_count": body_markdown.count("\n## "),
        "image_count": len(images),
        "citation_count": len(citations),
    }
