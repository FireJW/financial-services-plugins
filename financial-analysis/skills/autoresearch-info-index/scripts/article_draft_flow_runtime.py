#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
import re
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from article_brief_runtime import build_analysis_brief
from article_evidence_bundle import CONTRACT_VERSION as EVIDENCE_BUNDLE_CONTRACT_VERSION, build_shared_evidence_bundle
from article_feedback_profiles import feedback_profile_status, load_feedback_profiles, merge_request_with_profiles, resolve_profile_dir
from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, short_excerpt, write_json


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def meaningful_image_hint(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    if cleaned.lower().strip(" .,:;!?") in {"image", "images", "photo", "photos", "picture", "pictures", "media", "graphic", "图像", "图片", "照片"}:
        return ""
    return cleaned


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


def path_exists(path_value: Any) -> bool:
    path_text = clean_text(path_value)
    return bool(path_text) and Path(path_text).exists()


def normalize_local_path(path_value: Any) -> str:
    path_text = clean_text(path_value)
    return path_text.replace("\\", "/") if path_text else ""


def is_source_result(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output"))


def sanitize_draft_mode(value: Any) -> str:
    mode = clean_text(value).lower()
    if mode in {"image-first", "image_first"}:
        return "image_first"
    if mode in {"image-only", "image_only"}:
        return "image_only"
    return "balanced"


def sanitize_language_mode(value: Any) -> str:
    mode = clean_text(value).lower()
    if mode in {"bilingual", "zh-en", "zh_en", "cn-en", "cn_en"}:
        return "bilingual"
    if mode in {"chinese", "zh", "cn"}:
        return "chinese"
    return "english"


def sanitize_article_framework(value: Any) -> str:
    framework = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    if framework in {"hot_comment", "deep_analysis", "tutorial", "story", "list", "opinion"}:
        return framework
    return "auto"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    if is_source_result(payload):
        payload = {"source_result": payload}
    source_result = payload.get("source_result")
    source_result_path = clean_text(payload.get("source_result_path") or payload.get("source_path") or payload.get("input_result_path"))
    if source_result is None and source_result_path:
        source_result = load_json(Path(source_result_path).resolve())
    if not isinstance(source_result, dict):
        raise ValueError("article-draft requires source_result or source_result_path")
    analysis_brief = safe_dict(payload.get("analysis_brief"))
    analysis_brief_path = clean_text(payload.get("analysis_brief_path"))
    if not analysis_brief and analysis_brief_path:
        loaded_brief = load_json(Path(analysis_brief_path).resolve())
        analysis_brief = safe_dict(loaded_brief.get("analysis_brief")) or loaded_brief
    evidence_bundle = safe_dict(payload.get("evidence_bundle"))

    source_request = (
        safe_dict(source_result.get("request"))
        or safe_dict(source_result.get("retrieval_request"))
        or safe_dict(safe_dict(source_result.get("retrieval_result")).get("request"))
    )
    analysis_time = parse_datetime(payload.get("analysis_time"), fallback=None) or parse_datetime(
        source_request.get("analysis_time"),
        fallback=now_utc(),
    ) or now_utc()

    request = {
        "topic": clean_text(payload.get("topic") or source_request.get("topic") or "article-topic"),
        "analysis_time": analysis_time,
        "title_hint": clean_text(payload.get("title_hint")),
        "title_hint_zh": clean_text(payload.get("title_hint_zh")),
        "subtitle_hint": clean_text(payload.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(payload.get("subtitle_hint_zh")),
        "angle": clean_text(payload.get("angle")),
        "angle_zh": clean_text(payload.get("angle_zh")),
        "tone": clean_text(payload.get("tone")),
        "target_length_chars": int(payload.get("target_length_chars", payload.get("target_length", 1000))),
        "max_images": payload.get("max_images"),
        "image_strategy": clean_text(payload.get("image_strategy")),
        "draft_mode": clean_text(payload.get("draft_mode") or payload.get("composition_mode")),
        "language_mode": clean_text(payload.get("language_mode") or payload.get("output_language")),
        "article_framework": clean_text(payload.get("article_framework")),
        "must_include": clean_string_list(payload.get("must_include") or payload.get("focus_points")),
        "must_avoid": clean_string_list(payload.get("must_avoid")),
        "asset_output_dir": clean_text(payload.get("asset_output_dir")),
        "download_remote_images": str(payload.get("download_remote_images", "")).strip().lower() not in {"0", "false", "no", "off"},
        "feedback_profile_dir": clean_text(payload.get("feedback_profile_dir")),
        "source_result": source_result,
        "source_result_path": source_result_path,
        "analysis_brief": analysis_brief,
        "analysis_brief_path": analysis_brief_path,
        "evidence_bundle": evidence_bundle,
    }
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    profiles = load_feedback_profiles(profile_dir, request.get("topic", "article-topic"))
    request = merge_request_with_profiles(request, profiles)
    request["tone"] = clean_text(request.get("tone") or "neutral-cautious")
    request["max_images"] = max(0, min(int(request.get("max_images", 3) or 3), 8))
    request["image_strategy"] = clean_text(request.get("image_strategy") or "mixed")
    request["draft_mode"] = sanitize_draft_mode(request.get("draft_mode"))
    request["language_mode"] = sanitize_language_mode(request.get("language_mode"))
    request["article_framework"] = sanitize_article_framework(request.get("article_framework"))
    request["feedback_profile_dir"] = str(profile_dir)
    request["feedback_profile_status"] = feedback_profile_status(
        profile_dir,
        request.get("topic", "article-topic"),
        profiles=profiles,
    )
    return request


def ensure_evidence_bundle(request: dict[str, Any]) -> dict[str, Any]:
    bundle = safe_dict(request.get("evidence_bundle"))
    if clean_text(bundle.get("contract_version")) != EVIDENCE_BUNDLE_CONTRACT_VERSION:
        bundle = {}
    required_keys = {"source_summary", "evidence_digest", "citations", "image_candidates"}
    if not required_keys.issubset(bundle.keys()):
        bundle = build_shared_evidence_bundle(request["source_result"], request)
    return deepcopy(bundle)

def extract_runtime_result(source_result: dict[str, Any]) -> dict[str, Any]:
    runtime = safe_dict(source_result.get("retrieval_result"))
    if runtime:
        return runtime
    if safe_list(source_result.get("observations")) or safe_dict(source_result.get("verdict_output")):
        return source_result
    adapted = deepcopy(source_result)
    adapted["request"] = safe_dict(adapted.get("request")) or safe_dict(adapted.get("retrieval_request"))
    adapted["observations"] = safe_list(adapted.get("observations")) or safe_list(adapted.get("source_observations"))
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


def build_source_summary(source_result: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
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
    summary = {
        "source_kind": "x_index" if safe_list(source_result.get("x_posts")) or safe_dict(source_result.get("evidence_pack")) else "news_index",
        "topic": clean_text(request.get("topic")),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "blocked_source_count": blocked,
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


def candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("score", 0)),
        1 if path_exists(item.get("path")) else 0,
        1 if clean_text(item.get("summary") or item.get("caption")) else 0,
    )


def normalize_image_reference(path: Any, source_url: Any) -> tuple[str, str]:
    clean_path = clean_text(path)
    clean_url = clean_text(source_url)
    if clean_path.startswith(("http://", "https://", "file://")) and not clean_url:
        return "", clean_path
    return clean_path, clean_url


def image_candidate_key(role: Any, path: Any, source_url: Any) -> tuple[str, str, str]:
    clean_role = clean_text(role)
    clean_path, clean_url = normalize_image_reference(path, source_url)
    if clean_path:
        return clean_role, "path", clean_path
    return clean_role, "url", clean_url


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
        clean_path, clean_url = normalize_image_reference(path, source_url)
        if not clean_path and not clean_url:
            return
        key = image_candidate_key(role, clean_path, clean_url)
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
        root_post_screenshot_path = clean_text(post.get("root_post_screenshot_path"))
        if root_post_screenshot_path:
            add(
                "root_post_screenshot",
                source_name,
                root_post_screenshot_path,
                "",
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
        root_post_screenshot_path = clean_text(item.get("root_post_screenshot_path"))
        if root_post_screenshot_path:
            add(
                "root_post_screenshot",
                clean_text(item.get("source_name")) or "Artifact source",
                root_post_screenshot_path,
                "",
                clean_text(item.get("media_summary") or item.get("post_summary") or item.get("combined_summary") or item.get("post_text_raw")),
                clean_text(item.get("access_mode")) or "public",
                "medium",
                int(item.get("source_tier", 3)),
            )
        for artifact in safe_list(item.get("artifact_manifest")):
            if not isinstance(artifact, dict):
                continue
            artifact_role = clean_text(artifact.get("role")) or "post_media"
            add(
                "post_media" if artifact_role == "post_media" else artifact_role,
                clean_text(item.get("source_name")) or "Artifact source",
                clean_text(artifact.get("path")),
                clean_text(artifact.get("source_url")),
                clean_text(artifact.get("summary") or item.get("media_summary") or item.get("post_summary") or item.get("combined_summary")),
                clean_text(item.get("access_mode")) or "public",
                "high" if artifact_role == "post_media" else "medium",
                int(item.get("source_tier", 3)),
                clean_text(artifact.get("summary")),
                "artifact_manifest",
            )

    candidates.sort(key=candidate_sort_key, reverse=True)
    return candidates


def build_selected_images(image_candidates: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in image_candidates[: request.get("max_images", 3)]:
        path_text = clean_text(item.get("path"))
        source_url = clean_text(item.get("source_url"))
        access_mode = clean_text(item.get("access_mode"))
        summary = clean_text(item.get("summary") or item.get("caption"))
        alt_text = clean_text(item.get("alt_text"))
        capture_method = clean_text(item.get("capture_method"))
        if summary:
            caption = summary
        elif alt_text:
            caption = alt_text
        elif item.get("role") == "root_post_screenshot" and access_mode == "blocked":
            caption = "Root post screenshot from a blocked page. Keep it as visual evidence only."
        elif item.get("role") == "post_media" and capture_method == "dom_clip":
            caption = "Browser-captured image from the original X post."
        elif item.get("role") == "root_post_screenshot":
            caption = "Root post screenshot."
        else:
            caption = "Key source image."
        render_target = normalize_local_path(path_text) or source_url
        status = "local_ready" if path_exists(path_text) else "remote_only" if source_url else "missing"
        placement = {0: "after_lede", 1: "after_section_2", 2: "after_section_3"}.get(len(selected), "appendix")
        selected.append(
            {
                **item,
                "asset_id": clean_text(item.get("image_id")),
                "render_target": render_target,
                "embed_target": render_target,
                "caption": caption,
                "status": status,
                "placement": placement,
                "embed_markdown": f"![{clean_text(item.get('image_id'))}]({render_target})" if render_target else "",
            }
        )
    return selected


def image_candidate_match_keys(item: dict[str, Any]) -> list[tuple[str, ...]]:
    keys: list[tuple[str, ...]] = []
    image_id = clean_text(item.get("image_id") or item.get("asset_id"))
    if image_id:
        keys.append(("id", image_id))
    role = clean_text(item.get("role"))
    source_url = clean_text(item.get("source_url") or item.get("localized_from"))
    source_name = clean_text(item.get("source_name"))
    if role or source_url or source_name:
        keys.append(("source", role, source_url, source_name))
    path_text = clean_text(item.get("path") or item.get("render_target") or item.get("embed_target"))
    if role and path_text:
        keys.append(("path", role, path_text))
    return keys


def merge_localized_image_candidates(
    image_candidates: list[dict[str, Any]],
    localized_images: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    localized_lookup: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in localized_images:
        local_path = clean_text(item.get("path") or item.get("render_target") or item.get("embed_target"))
        if not local_path or not path_exists(local_path):
            continue
        localized_item = deepcopy(item)
        localized_item["path"] = local_path
        for key in image_candidate_match_keys(localized_item):
            localized_lookup[key] = localized_item

    if not localized_lookup:
        return deepcopy(image_candidates)

    merged_candidates: list[dict[str, Any]] = []
    for item in image_candidates:
        merged = deepcopy(item)
        match = next((localized_lookup[key] for key in image_candidate_match_keys(merged) if key in localized_lookup), None)
        if not match:
            merged_candidates.append(merged)
            continue

        merged["path"] = clean_text(match.get("path"))
        merged["status"] = "local_ready"
        localized_from = clean_text(match.get("localized_from"))
        if localized_from:
            merged["localized_from"] = localized_from
            if not clean_text(merged.get("source_url")):
                merged["source_url"] = localized_from
        for field in ("summary", "caption", "alt_text", "capture_method", "access_mode", "relevance"):
            if not clean_text(merged.get(field)) and clean_text(match.get(field)):
                merged[field] = clean_text(match.get(field))
        if merged.get("source_tier") in (None, "") and match.get("source_tier") not in (None, ""):
            merged["source_tier"] = int(match.get("source_tier"))
        merged_candidates.append(merged)
    return merged_candidates


def strip_source_branding(text: Any) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    separator_split = [part for part in re.split(r"\s*[|\uFF5C\u4E28]\s*", cleaned) if clean_text(part)]
    if separator_split:
        cleaned = separator_split[0]
    cleaned = re.sub(
        r"\s*[-\u2013\u2014]\s*(36kr|36\u6c2a|weibo|\u5fae\u535a|zhihu|\u77e5\u4e4e|reuters|\u8def\u900f|bloomberg|\u5f6d\u535a|techcrunch|the information|\u9996\u53d1|\u72ec\u5bb6).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*(36kr|36\u6c2a|\u9996\u53d1|\u72ec\u5bb6)\s*$", "", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned.strip(" -\u2013\u2014|\uFF5C\u4E28:\uFF1A\"'\u201c\u201d\u2018\u2019"))


def public_topic_text(request: dict[str, Any], fallback: str = "Developing Story") -> str:
    return strip_source_branding(request.get("topic")) or fallback


def resolve_article_framework(request: dict[str, Any], source_summary: dict[str, Any] | None = None) -> str:
    explicit = sanitize_article_framework(request.get("article_framework"))
    if explicit != "auto":
        return explicit
    topic = public_topic_text(request).lower()
    if any(token in topic for token in ("how to", "guide", "tutorial", "\u6559\u7a0b", "\u6307\u5357", "\u65b9\u6cd5", "\u6b65\u9aa4")):
        return "tutorial"
    if any(token in topic for token in ("list", "tools", "tool", "\u76d8\u70b9", "\u6e05\u5355", "\u699c\u5355")):
        return "list"
    if any(token in topic for token in ("founder", "interview", "\u4eba\u7269", "\u521b\u59cb\u4eba", "\u8bbf\u8c08", "story")):
        return "story"
    if any(token in topic for token in ("opinion", "\u5410\u69fd", "\u4e89\u8bae", "should", "\u503c\u4e0d\u503c")):
        return "opinion"
    if any(token in topic for token in ("\u878d\u8d44", "policy", "regulation", "industry", "trend", "platform", "\u5e73\u53f0", "\u53d1\u5e03", "launch")):
        return "deep_analysis"
    if source_summary and int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        return "hot_comment"
    return "hot_comment"


''' Disabled legacy public-writer block kept only for forensic recovery.
The active implementation lives in the safe redefinitions below.

def build_title(request: dict[str, Any], digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    del digest, selected_images
    language_mode = request.get("language_mode", "english")
    title_hint = clean_text(request.get("title_hint"))
    title_hint_zh = clean_text(request.get("title_hint_zh"))
    if title_hint or title_hint_zh:
        return bilingual_heading(title_hint_zh, title_hint, language_mode)
    topic = public_topic_text(request)
    if topic:
        if language_mode == "bilingual":
            return topic
        return bilingual_heading(topic, topic, language_mode)
    framework = resolve_article_framework(request)
    fallback_titles = {
        "hot_comment": ("这件事真正值得看的是什么", "What really matters in this story"),
        "deep_analysis": ("这件事为什么值得关注", "Why this story matters now"),
        "tutorial": ("三步看懂这件事", "How to break this down in three steps"),
        "story": ("这件事的关键转折", "The turning point in this story"),
        "list": ("这件事最值得看的三个点", "Three angles worth watching here"),
        "opinion": ("别只看热度，要看真正的变化", "Ignore the noise and look at the real shift"),
    }
    title_zh, title_en = fallback_titles.get(framework, fallback_titles["hot_comment"])
    return bilingual_heading(title_zh, title_en, language_mode)


def build_subtitle(request: dict[str, Any], summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    subtitle_hint = clean_text(request.get("subtitle_hint"))
    subtitle_hint_zh = clean_text(request.get("subtitle_hint_zh"))
    if subtitle_hint or subtitle_hint_zh:
        return bilingual_text(subtitle_hint_zh, subtitle_hint, language_mode)
    if request.get("draft_mode") == "image_only":
        return bilingual_text(
            "先看图里能确认什么，再决定这件事该怎么写。",
            "Start with what the images can genuinely support, then decide how far the story should go.",
            language_mode,
        )
    framework = resolve_article_framework(request, summary)
    if framework == "tutorial":
        return bilingual_text(
            "把问题拆开讲清楚，比堆观点更重要。",
            "Clarity matters more than volume here, so the draft breaks the problem into practical steps.",
            language_mode,
        )
    if framework == "story":
        return bilingual_text(
            "真正值得写的，不只是事件本身，而是它走到这一步的关键转折。",
            "The value is not just the event itself, but the turning point that pushed it into focus.",
            language_mode,
        )
    if framework == "list":
        return bilingual_text(
            "别急着下结论，先把最关键的几个观察点摆出来。",
            "Before jumping to a verdict, put the few highest-signal observations on the table.",
            language_mode,
        )
    if summary.get("source_kind") == "x_index" and selected_images:
        return bilingual_text(
            "热度会骗人，真正有用的是能落回公开信息和一手素材的那部分。",
            "Heat can be misleading. What matters is the part of the story that still lands on public evidence and first-hand material.",
            language_mode,
        )
    return bilingual_text(
        "先把发生了什么说清楚，再看这件事为什么会继续发酵。",
        "Start with what changed, then look at why the discussion is still gaining heat.",
        language_mode,
    )


def citation_ids_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> list[str]:
    citation_ids: list[str] = []
    source_id_set = set(clean_string_list(source_ids))
    for citation in citations:
        citation_source_id = clean_text(citation.get("source_id"))
        citation_id = clean_text(citation.get("citation_id"))
        if citation_source_id in source_id_set and citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
    return citation_ids


def refs_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> str:
    refs = [f"[{citation_id}]" for citation_id in citation_ids_for_source_ids(citations, source_ids)]
    return "".join(refs)


def top_citation_ids(citations: list[dict[str, Any]], limit: int = 2) -> list[str]:
    citation_ids: list[str] = []
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        if citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
        if len(citation_ids) >= max(1, limit):
            break
    return citation_ids


def preferred_citation_ids(
    citations: list[dict[str, Any]],
    source_ids: list[str] | None = None,
    *,
    limit: int = 2,
) -> list[str]:
    matched = citation_ids_for_source_ids(citations, clean_string_list(source_ids))
    if matched:
        return matched[: max(1, limit)]
    ranked = [
        item
        for item in citations
        if clean_text(item.get("access_mode")) != "blocked" and int(item.get("source_tier", 3)) <= 1
    ]
    if not ranked:
        ranked = [item for item in citations if clean_text(item.get("access_mode")) != "blocked"]
    return top_citation_ids(ranked or citations, limit=limit)


def citation_channels_for_ids(citations: list[dict[str, Any]], citation_ids: list[str]) -> list[str]:
    channels: list[str] = []
    wanted = set(clean_string_list(citation_ids))
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        channel = clean_text(citation.get("channel"))
        if citation_id in wanted and channel and channel not in channels:
            channels.append(channel)
    return channels


def join_with_semicolons(items: list[str], empty_text: str) -> str:
    clean_items = [clean_text(item) for item in items if clean_text(item)]
    return "; ".join(clean_items) if clean_items else empty_text


def strip_terminal_punctuation(text: str) -> str:
    return clean_text(text).rstrip(" .;:")


def lowercase_first(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    return cleaned[:1].lower() + cleaned[1:]


def join_with_commas(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def bilingual_heading(zh: str, en: str, mode: str) -> str:
    zh_text = clean_text(zh)
    en_text = clean_text(en)
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text} | {en_text}"
        return zh_text or en_text
    return en_text or zh_text


def bilingual_text(zh: str, en: str, mode: str) -> str:
    zh_text = str(zh or "").replace("\u200b", " ").strip()
    en_text = str(en or "").replace("\u200b", " ").strip()
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text}\n\n{en_text}"
        return zh_text or en_text
    return en_text or zh_text


def signal_sentence(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "There are not enough fresh public signals yet to upgrade any single hint into a firm conclusion."
    parts = []
    for item in signals[:3]:
        source_name = clean_text(item.get("source_name")) or "Unknown source"
        age = clean_text(item.get("age")) or "unknown age"
        excerpt = short_excerpt(clean_text(item.get("text_excerpt")), limit=100) or "new signal"
        parts.append(f"{source_name} ({age}) said: {excerpt}")
    return "Latest signals first: " + "; ".join(parts) + "."


def image_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is attached to this draft yet."
    parts = []
    for item in images[:3]:
        source_name = clean_text(item.get("source_name")) or "Unnamed source"
        caption = short_excerpt(clean_text(item.get("caption")), limit=100) or "no machine-readable image summary"
        parts.append(f"{source_name}: {caption}")
    return "Key images kept for the article: " + "; ".join(parts) + "."


def visual_evidence_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is available, so this version cannot be image-first in practice."
    parts = []
    for item in images[:3]:
        role = clean_text(item.get("role")).replace("_", " ")
        status = clean_text(item.get("status")) or "unknown"
        caption = short_excerpt(clean_text(item.get("caption")), limit=110) or "no machine-readable summary"
        parts.append(f"{role}: {caption} [{status}]")
    return "Visual evidence layer: " + "; ".join(parts) + "."


def apply_must_avoid(text: str, must_avoid: list[str]) -> str:
    updated = text
    for phrase in must_avoid:
        updated = updated.replace(phrase, "")
    return updated


def derive_analysis_brief_from_digest(
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_source_ids = clean_string_list([citation.get("source_id") for citation in citations[:2]])
    canonical_facts = [
        {
            "claim_id": f"derived-confirmed-{index + 1}",
            "claim_text": text,
            "source_ids": primary_source_ids if index == 0 else [],
            "promotion_state": "core",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("confirmed"))[:4])
    ]
    not_proven = [
        {
            "claim_id": f"derived-not-proven-{index + 1}",
            "claim_text": text,
            "source_ids": [],
            "status": "unclear",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("not_confirmed"))[:4])
    ]
    latest_signal_summary = signal_sentence(normalize_latest_signals(evidence_digest.get("latest_signals")))
    story_angles = [
        {
            "angle": "Lead with the confirmed public record before discussing faster-moving signals.",
            "risk": "Do not turn social or single-source updates into settled fact.",
        }
    ]
    if images:
        story_angles.append(
            {
                "angle": "Use saved images as supporting context, not as proof beyond what they visibly show.",
                "risk": "Treat visuals as the last public indication, not ground truth.",
            }
        )
    open_questions = clean_string_list(evidence_digest.get("next_watch_items"))[:4]
    voice_constraints = [
        "Keep facts, inference, and visual hints clearly separated.",
        "Do not write past the strongest confirmed evidence.",
    ]
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        voice_constraints.append("Some sources were blocked, so the draft should not imply the search was complete.")
    if clean_text(source_summary.get("confidence_gate")) == "shadow-heavy":
        voice_constraints.append("Shadow-only signals can raise attention, but they cannot carry the main conclusion alone.")
    misread_risks = []
    if not canonical_facts:
        misread_risks.append("The package does not yet have a strong confirmed fact to anchor the draft.")
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        misread_risks.append("Blocked or missing sources could hide confirming or contradicting evidence.")
    if images:
        misread_risks.append("Readers may overread the images if the captions are written too strongly.")
    recommended_thesis = (
        clean_text(source_summary.get("core_verdict"))
        or (clean_string_list(evidence_digest.get("confirmed")) or ["Current evidence remains incomplete."])[0]
    )
    return {
        "canonical_facts": canonical_facts,
        "not_proven": not_proven,
        "open_questions": open_questions,
        "trend_lines": [
            {
                "trend": "Latest signals",
                "detail": latest_signal_summary,
            }
        ],
        "scenario_matrix": [],
        "market_or_reader_relevance": clean_string_list(evidence_digest.get("market_relevance")),
        "story_angles": story_angles,
        "image_keep_reasons": [
            {
                "image_id": clean_text(item.get("image_id") or item.get("asset_id")),
                "reason": clean_text(item.get("caption")) or "Retained as visual context for the draft.",
            }
            for item in images[:3]
        ],
        "voice_constraints": voice_constraints,
        "recommended_thesis": recommended_thesis,
        "misread_risks": misread_risks,
    }


def brief_items_text(items: list[dict[str, Any]], fallback: str, *, field: str = "claim_text") -> str:
    texts = [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))]
    return join_with_semicolons(texts, fallback)


def item_texts(items: list[dict[str, Any]], *, field: str = "claim_text", limit: int = 3) -> list[str]:
    return [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))][:limit]


def framework_headings(framework: str) -> list[tuple[str, str]]:
    heading_map = {
        "hot_comment": [
            ("事情先说清楚", "What Changed"),
            ("热度为什么还在涨", "Why The Story Is Spreading"),
            ("为什么这事值得关注", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "deep_analysis": [
            ("先看变化本身", "What Changed"),
            ("深层原因", "The Deeper Driver"),
            ("影响会传到哪里", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "tutorial": [
            ("核心问题", "The Core Problem"),
            ("先看判断方法", "How To Read It"),
            ("三个实操动作", "Three Practical Moves"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "story": [
            ("关键转折", "The Turning Point"),
            ("事情是怎么走到这里的", "How The Story Reached Here"),
            ("这件事说明了什么", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "list": [
            ("第一个信号", "First Signal"),
            ("第二个信号", "Second Signal"),
            ("第三个信号", "Third Signal"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "opinion": [
            ("事情先说清楚", "What Changed"),
            ("噪音从哪来", "Where The Noise Starts"),
            ("我的判断", "The View"),
            ("接下来盯什么", "What To Watch Next"),
        ],
    }
    return heading_map.get(framework, heading_map["hot_comment"])


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    lead_fact = item_texts(canonical_facts, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    if lead_fact:
        zh = (
            f"{lead_fact[0]}。真正让这件事值得继续盯下去的，不只是热度，而是"
            f"{strip_terminal_punctuation(market_relevance[0]) if market_relevance else '它开始影响后面的判断和动作'}。"
        )
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(zh, en, language_mode)
    zh = f"{topic}正在从一个单点话题，慢慢变成一件需要继续追踪的事。先把已经发生的变化说清楚，再看影响会传到哪里。"
    en = f"{topic} is moving from a single headline into a story that still needs tracking. Start with the real change, then follow where the impact goes next."
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    open_questions = clean_string_list(analysis_brief.get("open_questions"))
    fact_texts = item_texts(canonical_facts, limit=3)
    not_proven_texts = item_texts(not_proven, limit=2)
    trend_texts = item_texts(trend_lines, field="detail", limit=2) or item_texts(trend_lines, field="trend", limit=2)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")

    fact_paragraph = bilingual_text(
        "先把台面上最硬的几条信息放在一起：" + join_with_semicolons(fact_texts, f"{topic}还需要更多公开信息来补全。") + "。这意味着它已经不是一句话就能带过去的热搜。",
        "Start with the hardest public facts on the table: "
        + join_with_semicolons(fact_texts, f"{topic} still needs more public detail before the picture is complete.")
        + ". At this point, the story is already bigger than a one-line trend item.",
        language_mode,
    )
    spread_paragraph = bilingual_text(
        "这件事会继续发酵，通常不是因为标题更吓人，而是因为" + join_with_semicolons(trend_texts, "讨论开始从情绪转向影响路径") + "。一旦讨论开始落到产业、预算或执行层面，它就不只是流量题了。",
        "The discussion keeps spreading not because the headline sounds louder, but because "
        + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to transmission")
        + ". Once a topic starts touching industry positioning, budgets, or execution, it stops being pure traffic.",
        language_mode,
    )
    impact_paragraph = bilingual_text(
        "真正值得盯的不是表面热度，而是它会传到谁、改变谁的判断。现在最直接的观察对象是"
        + join_with_commas(market_relevance[:3], "后续决策、行业情绪和资源分配")
        + "。这才是它从话题变成变量的地方。",
        "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
        + join_with_commas(market_relevance[:3], "follow-on decisions, industry positioning, and resource allocation")
        + ". That is where a topic stops being noise and becomes a variable.",
        language_mode,
    )
    watch_paragraph = bilingual_text(
        "接下来最该盯的不是情绪，而是这些变量："
        + join_with_semicolons(open_questions[:3], "新的公开确认、后续动作，以及市场会不会继续加码")
        + "。如果这些点落地，叙事会升级；如果迟迟落不了地，热度就可能跑在事实前面。",
        "The next useful checkpoints are "
        + join_with_semicolons(open_questions[:3], "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
        + ". If those land, the story upgrades quickly; if they do not, the heat may outrun the substance.",
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "这里最容易被说过头的地方是：" + join_with_semicolons(not_proven_texts, "不要把还在发酵的推演，当成已经落地的事实") + "。写到这里，克制本身就是质量。",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: " + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "先只说图像层真正能支撑的部分：" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections


'''

# Safe redefinitions: keep late-bound public writer logic in ASCII / unicode-escape form
# so publishable copy does not depend on terminal encoding.
def build_title(request: dict[str, Any], digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    del digest, selected_images
    language_mode = request.get("language_mode", "english")
    title_hint = clean_text(request.get("title_hint"))
    title_hint_zh = clean_text(request.get("title_hint_zh"))
    if title_hint or title_hint_zh:
        return bilingual_heading(title_hint_zh, title_hint, language_mode)
    topic = public_topic_text(request)
    if topic:
        if language_mode == "bilingual":
            return topic
        return bilingual_heading(topic, topic, language_mode)
    fallback_titles = {
        "hot_comment": ("\u8fd9\u4ef6\u4e8b\u771f\u6b63\u503c\u5f97\u770b\u7684\u662f\u4ec0\u4e48", "What really matters in this story"),
        "deep_analysis": ("\u8fd9\u4ef6\u4e8b\u4e3a\u4ec0\u4e48\u503c\u5f97\u5173\u6ce8", "Why this story matters now"),
        "tutorial": ("\u4e09\u6b65\u770b\u61c2\u8fd9\u4ef6\u4e8b", "How to break this down in three steps"),
        "story": ("\u8fd9\u4ef6\u4e8b\u7684\u5173\u952e\u8f6c\u6298", "The turning point in this story"),
        "list": ("\u8fd9\u4ef6\u4e8b\u6700\u503c\u5f97\u770b\u7684\u4e09\u4e2a\u70b9", "Three angles worth watching here"),
        "opinion": ("\u522b\u53ea\u770b\u70ed\u5ea6\uff0c\u8981\u770b\u771f\u6b63\u7684\u53d8\u5316", "Ignore the noise and look at the real shift"),
    }
    title_zh, title_en = fallback_titles.get(resolve_article_framework(request), fallback_titles["hot_comment"])
    return bilingual_heading(title_zh, title_en, language_mode)


def build_subtitle(request: dict[str, Any], summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    subtitle_hint = clean_text(request.get("subtitle_hint"))
    subtitle_hint_zh = clean_text(request.get("subtitle_hint_zh"))
    if subtitle_hint or subtitle_hint_zh:
        return bilingual_text(subtitle_hint_zh, subtitle_hint, language_mode)
    if request.get("draft_mode") == "image_only":
        return bilingual_text(
            "\u5148\u770b\u56fe\u91cc\u80fd\u786e\u8ba4\u4ec0\u4e48\uff0c\u518d\u51b3\u5b9a\u8fd9\u4ef6\u4e8b\u8be5\u600e\u4e48\u5199\u3002",
            "Start with what the images can genuinely support, then decide how far the story should go.",
            language_mode,
        )
    framework = resolve_article_framework(request, summary)
    if framework == "tutorial":
        return bilingual_text(
            "\u628a\u95ee\u9898\u62c6\u5f00\u8bb2\u6e05\u695a\uff0c\u6bd4\u5806\u89c2\u70b9\u66f4\u91cd\u8981\u3002",
            "Clarity matters more than volume here, so the draft breaks the problem into practical steps.",
            language_mode,
        )
    if framework == "story":
        return bilingual_text(
            "\u771f\u6b63\u503c\u5f97\u5199\u7684\uff0c\u4e0d\u53ea\u662f\u4e8b\u4ef6\u672c\u8eab\uff0c\u800c\u662f\u5b83\u8d70\u5230\u8fd9\u4e00\u6b65\u7684\u5173\u952e\u8f6c\u6298\u3002",
            "The value is not just the event itself, but the turning point that pushed it into focus.",
            language_mode,
        )
    if framework == "list":
        return bilingual_text(
            "\u522b\u6025\u7740\u4e0b\u7ed3\u8bba\uff0c\u5148\u628a\u6700\u5173\u952e\u7684\u51e0\u4e2a\u89c2\u5bdf\u70b9\u6446\u51fa\u6765\u3002",
            "Before jumping to a verdict, put the few highest-signal observations on the table.",
            language_mode,
        )
    if summary.get("source_kind") == "x_index" and selected_images:
        return bilingual_text(
            "\u70ed\u5ea6\u4f1a\u9a97\u4eba\uff0c\u771f\u6b63\u6709\u7528\u7684\u662f\u80fd\u843d\u56de\u516c\u5f00\u4fe1\u606f\u548c\u4e00\u624b\u7d20\u6750\u7684\u90a3\u90e8\u5206\u3002",
            "Heat can be misleading. What matters is the part of the story that still lands on public evidence and first-hand material.",
            language_mode,
        )
    return bilingual_text(
        "\u5148\u628a\u53d1\u751f\u4e86\u4ec0\u4e48\u8bf4\u6e05\u695a\uff0c\u518d\u770b\u8fd9\u4ef6\u4e8b\u4e3a\u4ec0\u4e48\u4f1a\u7ee7\u7eed\u53d1\u9175\u3002",
        "Start with what changed, then look at why the discussion is still gaining heat.",
        language_mode,
    )


def framework_headings(framework: str) -> list[tuple[str, str]]:
    heading_map = {
        "hot_comment": [
            ("\u4e8b\u60c5\u5148\u8bf4\u6e05\u695a", "What Changed"),
            ("\u70ed\u5ea6\u4e3a\u4ec0\u4e48\u8fd8\u5728\u6da8", "Why The Story Is Spreading"),
            ("\u4e3a\u4ec0\u4e48\u8fd9\u4e8b\u503c\u5f97\u5173\u6ce8", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "deep_analysis": [
            ("\u5148\u770b\u53d8\u5316\u672c\u8eab", "What Changed"),
            ("\u6df1\u5c42\u539f\u56e0", "The Deeper Driver"),
            ("\u5f71\u54cd\u4f1a\u4f20\u5230\u54ea\u91cc", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "tutorial": [
            ("\u6838\u5fc3\u95ee\u9898", "The Core Problem"),
            ("\u5148\u770b\u5224\u65ad\u65b9\u6cd5", "How To Read It"),
            ("\u4e09\u4e2a\u5b9e\u64cd\u52a8\u4f5c", "Three Practical Moves"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "story": [
            ("\u5173\u952e\u8f6c\u6298", "The Turning Point"),
            ("\u4e8b\u60c5\u662f\u600e\u4e48\u8d70\u5230\u8fd9\u91cc\u7684", "How The Story Reached Here"),
            ("\u8fd9\u4ef6\u4e8b\u8bf4\u660e\u4e86\u4ec0\u4e48", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "list": [
            ("\u7b2c\u4e00\u4e2a\u4fe1\u53f7", "First Signal"),
            ("\u7b2c\u4e8c\u4e2a\u4fe1\u53f7", "Second Signal"),
            ("\u7b2c\u4e09\u4e2a\u4fe1\u53f7", "Third Signal"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "opinion": [
            ("\u4e8b\u60c5\u5148\u8bf4\u6e05\u695a", "What Changed"),
            ("\u566a\u97f3\u4ece\u54ea\u6765", "Where The Noise Starts"),
            ("\u6211\u7684\u5224\u65ad", "The View"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
    }
    return heading_map.get(framework, heading_map["hot_comment"])


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    lead_fact = item_texts(canonical_facts, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    if lead_fact:
        zh_relevance = strip_terminal_punctuation(market_relevance[0]) if market_relevance else "\u5b83\u5f00\u59cb\u5f71\u54cd\u540e\u9762\u7684\u5224\u65ad\u548c\u52a8\u4f5c"
        zh = f"{lead_fact[0]}\u3002\u771f\u6b63\u8ba9\u8fd9\u4ef6\u4e8b\u503c\u5f97\u7ee7\u7eed\u76ef\u4e0b\u53bb\u7684\uff0c\u4e0d\u53ea\u662f\u70ed\u5ea6\uff0c\u800c\u662f{zh_relevance}\u3002"
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(zh, en, language_mode)
    zh = f"{topic}\u6b63\u5728\u4ece\u4e00\u4e2a\u5355\u70b9\u8bdd\u9898\uff0c\u6162\u6162\u53d8\u6210\u4e00\u4ef6\u9700\u8981\u7ee7\u7eed\u8ffd\u8e2a\u7684\u4e8b\u3002\u5148\u628a\u5df2\u7ecf\u53d1\u751f\u7684\u53d8\u5316\u8bf4\u6e05\u695a\uff0c\u518d\u770b\u5f71\u54cd\u4f1a\u4f20\u5230\u54ea\u91cc\u3002"
    en = f"{topic} is moving from a single headline into a story that still needs tracking. Start with the real change, then follow where the impact goes next."
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    open_questions = clean_string_list(analysis_brief.get("open_questions"))
    fact_texts = item_texts(canonical_facts, limit=3)
    not_proven_texts = item_texts(not_proven, limit=2)
    trend_texts = item_texts(trend_lines, field="detail", limit=2) or item_texts(trend_lines, field="trend", limit=2)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")

    fact_paragraph = bilingual_text(
        "\u5148\u628a\u53f0\u9762\u4e0a\u6700\u786c\u7684\u51e0\u6761\u4fe1\u606f\u653e\u5728\u4e00\u8d77\uff1a"
        + join_with_semicolons(fact_texts, f"{topic}\u8fd8\u9700\u8981\u66f4\u591a\u516c\u5f00\u4fe1\u606f\u6765\u8865\u5168\u3002")
        + "\u3002\u8fd9\u8bf4\u660e\u5b83\u5df2\u7ecf\u4e0d\u662f\u4e00\u53e5\u8bdd\u5c31\u80fd\u5e26\u8fc7\u53bb\u7684\u70ed\u641c\u3002",
        "Start with the hardest public facts on the table: "
        + join_with_semicolons(fact_texts, f"{topic} still needs more public detail before the picture is complete.")
        + ". At this point, the story is already bigger than a one-line trend item.",
        language_mode,
    )
    spread_paragraph = bilingual_text(
        "\u8fd9\u4ef6\u4e8b\u4f1a\u7ee7\u7eed\u53d1\u9175\uff0c\u4e0d\u662f\u56e0\u4e3a\u6807\u9898\u66f4\u5413\u4eba\uff0c\u800c\u662f\u56e0\u4e3a"
        + join_with_semicolons(trend_texts, "\u8ba8\u8bba\u5f00\u59cb\u4ece\u60c5\u7eea\u8f6c\u5411\u5f71\u54cd\u8def\u5f84")
        + "\u3002\u4e00\u65e6\u8ba8\u8bba\u5f00\u59cb\u843d\u5230\u4ea7\u4e1a\u3001\u9884\u7b97\u6216\u6267\u884c\u5c42\u9762\uff0c\u5b83\u5c31\u4e0d\u53ea\u662f\u6d41\u91cf\u9898\u4e86\u3002",
        "The discussion keeps spreading not because the headline sounds louder, but because "
        + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to transmission")
        + ". Once a topic starts touching industry positioning, budgets, or execution, it stops being pure traffic.",
        language_mode,
    )
    impact_paragraph = bilingual_text(
        "\u771f\u6b63\u503c\u5f97\u76ef\u7684\u4e0d\u662f\u8868\u9762\u70ed\u5ea6\uff0c\u800c\u662f\u5b83\u4f1a\u4f20\u5230\u8c01\u3001\u6539\u53d8\u8c01\u7684\u5224\u65ad\u3002\u73b0\u5728\u6700\u76f4\u63a5\u7684\u89c2\u5bdf\u5bf9\u8c61\u662f"
        + join_with_commas(market_relevance[:3], "\u540e\u7eed\u51b3\u7b56\u3001\u884c\u4e1a\u60c5\u7eea\u548c\u8d44\u6e90\u5206\u914d")
        + "\u3002\u8fd9\u624d\u662f\u5b83\u4ece\u8bdd\u9898\u53d8\u6210\u53d8\u91cf\u7684\u5730\u65b9\u3002",
        "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
        + join_with_commas(market_relevance[:3], "follow-on decisions, industry positioning, and resource allocation")
        + ". That is where a topic stops being noise and becomes a variable.",
        language_mode,
    )
    watch_paragraph = bilingual_text(
        "\u63a5\u4e0b\u6765\u6700\u8be5\u76ef\u7684\u4e0d\u662f\u60c5\u7eea\uff0c\u800c\u662f\u8fd9\u4e9b\u53d8\u91cf\uff1a"
        + join_with_semicolons(open_questions[:3], "\u65b0\u7684\u516c\u5f00\u786e\u8ba4\u3001\u540e\u7eed\u52a8\u4f5c\uff0c\u4ee5\u53ca\u5e02\u573a\u4f1a\u4e0d\u4f1a\u7ee7\u7eed\u52a0\u7801")
        + "\u3002\u5982\u679c\u8fd9\u4e9b\u70b9\u843d\u5730\uff0c\u53d9\u4e8b\u4f1a\u5347\u7ea7\uff1b\u5982\u679c\u8fdf\u8fdf\u843d\u4e0d\u4e86\u5730\uff0c\u70ed\u5ea6\u5c31\u53ef\u80fd\u8dd1\u5728\u4e8b\u5b9e\u524d\u9762\u3002",
        "The next useful checkpoints are "
        + join_with_semicolons(open_questions[:3], "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
        + ". If those land, the story upgrades quickly; if they do not, the heat may outrun the substance.",
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "\u8fd9\u91cc\u6700\u5bb9\u6613\u88ab\u8bf4\u8fc7\u5934\u7684\u5730\u65b9\u662f\uff1a"
        + join_with_semicolons(not_proven_texts, "\u4e0d\u8981\u628a\u8fd8\u5728\u53d1\u9175\u7684\u63a8\u6f14\uff0c\u5f53\u6210\u5df2\u7ecf\u843d\u5730\u7684\u4e8b\u5b9e")
        + "\u3002\u5199\u5230\u8fd9\u91cc\uff0c\u514b\u5236\u672c\u8eab\u5c31\u662f\u8d28\u91cf\u3002",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "\u56fe\u50cf\u7d20\u6750\u80fd\u5e2e\u4f60\u628a\u73b0\u573a\u611f\u8865\u56de\u6765\uff0c\u4f46\u5b83\u66f4\u9002\u5408\u505a\u8865\u5145\uff0c\u4e0d\u9002\u5408\u66ff\u4ee3\u5224\u65ad\u3002\u5f53\u524d\u503c\u5f97\u4fdd\u7559\u7684\u89c6\u89c9\u7ebf\u7d22\u662f\uff1a"
        + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
        + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("\u56fe\u91cc\u80fd\u786e\u8ba4\u4ec0\u4e48", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "\u5148\u53ea\u8bf4\u56fe\u50cf\u5c42\u771f\u6b63\u80fd\u652f\u6491\u7684\u90e8\u5206\uff1a" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("\u56fe\u91cc\u4e0d\u80fd\u66ff\u4ee3\u4ec0\u4e48", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("\u56fe\u91cc\u80fd\u8865\u4ec0\u4e48", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections

def build_sections(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    effective_brief = safe_dict(analysis_brief) or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        images,
    )
    return build_sections_from_brief(request, source_summary, citations, images, effective_brief)


def build_draft_claim_map(citations: list[dict[str, Any]], analysis_brief: dict[str, Any]) -> list[dict[str, Any]]:
    claim_map: list[dict[str, Any]] = []
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    recommended_thesis = clean_text(analysis_brief.get("recommended_thesis"))
    thesis_sources = clean_string_list(safe_dict(canonical_facts[0]).get("source_ids")) if canonical_facts else []
    thesis_citation_ids = preferred_citation_ids(citations, thesis_sources)
    if recommended_thesis:
        claim_map.append(
            {
                "claim_label": "thesis",
                "claim_text": recommended_thesis,
                "source_ids": thesis_sources,
                "citation_ids": thesis_citation_ids,
                "citation_channels": citation_channels_for_ids(citations, thesis_citation_ids),
                "support_level": "core" if thesis_sources else "derived" if thesis_citation_ids else "shadow-heavy",
            }
        )
    for item in canonical_facts[:3]:
        source_ids = clean_string_list(item.get("source_ids"))
        citation_ids = preferred_citation_ids(citations, source_ids)
        claim_map.append(
            {
                "claim_label": clean_text(item.get("claim_id")) or "canonical_fact",
                "claim_text": clean_text(item.get("claim_text")),
                "source_ids": source_ids,
                "citation_ids": citation_ids,
                "citation_channels": citation_channels_for_ids(citations, citation_ids),
                "support_level": clean_text(item.get("promotion_state")) or "core",
            }
        )
    for item in safe_list(analysis_brief.get("not_proven"))[:2]:
        source_ids = clean_string_list(item.get("source_ids"))
        citation_ids = preferred_citation_ids(citations, source_ids)
        claim_map.append(
            {
                "claim_label": clean_text(item.get("claim_id")) or "not_proven",
                "claim_text": clean_text(item.get("claim_text")),
                "source_ids": source_ids,
                "citation_ids": citation_ids,
                "citation_channels": citation_channels_for_ids(citations, citation_ids),
                "support_level": clean_text(item.get("status")) or "unclear",
            }
        )
    return [item for item in claim_map if clean_text(item.get("claim_text"))]


def build_style_profile_applied(request: dict[str, Any]) -> dict[str, Any]:
    profile_status = safe_dict(request.get("feedback_profile_status"))
    applied_paths = clean_string_list(request.get("applied_feedback_profiles")) or clean_string_list(profile_status.get("applied_paths"))
    constraints = {
        "must_include": clean_string_list(request.get("must_include")),
        "must_avoid": clean_string_list(request.get("must_avoid")),
    }
    return {
        "applied_paths": applied_paths,
        "global_profile_applied": bool(profile_status.get("global_exists")),
        "topic_profile_applied": bool(profile_status.get("topic_exists")),
        "constraints": constraints,
        "effective_request": {
            "language_mode": clean_text(request.get("language_mode")),
            "draft_mode": clean_text(request.get("draft_mode")),
            "image_strategy": clean_text(request.get("image_strategy")),
            "tone": clean_text(request.get("tone")),
            "target_length_chars": int(request.get("target_length_chars", 0) or 0),
            "max_images": int(request.get("max_images", 0) or 0),
            "must_include": constraints["must_include"],
            "must_avoid": constraints["must_avoid"],
        },
    }


def build_writer_risk_notes(analysis_brief: dict[str, Any], source_summary: dict[str, Any]) -> list[str]:
    notes = clean_string_list(analysis_brief.get("misread_risks"))
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        notes.append("Some sources were blocked, so the writer must avoid treating the package as fully checked.")
    if not notes:
        notes.append("The main remaining writer risk is sounding more certain than the evidence allows.")
    return notes[:5]

def build_body_markdown(title: str, subtitle: str, sections: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", subtitle]
    for section in sections:
        lines.extend(["", f"## {section.get('heading', '')}", section.get("paragraph", "")])
    return "\n".join(lines).strip() + "\n"


def build_article_markdown(
    title: str,
    subtitle: str,
    lede: str,
    sections: list[dict[str, Any]],
    images: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> str:
    lines = [f"# {title}", "", subtitle, "", f"> {lede}", ""]
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in images:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)

    def emit_images(placement: str) -> None:
        for item in images_by_placement.get(placement, []):
            if clean_text(item.get("embed_markdown")):
                lines.append(item["embed_markdown"])
                caption = clean_text(item.get("caption"))
                if caption:
                    lines.append(f"_{caption}_")
                    lines.append("")

    emit_images("after_lede")
    for index, section in enumerate(sections, start=1):
        lines.append(f"## {section.get('heading', '')}")
        lines.append(section.get("paragraph", ""))
        lines.append("")
        emit_images(f"after_section_{index}")
    emit_images("appendix")

    lines.extend(["## Sources", ""])
    for item in citations:
        lines.append(
            f"- {item.get('citation_id', '')} | {item.get('source_name', '')} | "
            f"{item.get('url', '') or 'no url'}"
        )
    if not citations:
        lines.append("- None")
    return "\n".join(lines).strip() + "\n"


def body_refresh_signature(images: list[dict[str, Any]], draft_mode: str) -> list[tuple[str, str, str, str]]:
    signature: list[tuple[str, str, str, str]] = []
    include_status = draft_mode in {"image_first", "image_only"}
    for item in images[:3]:
        signature.append(
            (
                clean_text(item.get("source_name")),
                clean_text(item.get("caption")),
                clean_text(item.get("role")),
                clean_text(item.get("status")) if include_status else "",
            )
        )
    return signature


def should_rebuild_body_for_image_refresh(
    article_package: dict[str, Any],
    previous_images: list[dict[str, Any]],
    next_images: list[dict[str, Any]],
) -> bool:
    if article_package.get("manual_body_override"):
        return False
    render_context = safe_dict(article_package.get("render_context"))
    if not render_context:
        return False
    if not safe_list(article_package.get("sections") or article_package.get("body_sections")):
        return True
    request_context = safe_dict(render_context.get("request"))
    draft_mode = clean_text(request_context.get("draft_mode"))
    return body_refresh_signature(previous_images, draft_mode) != body_refresh_signature(next_images, draft_mode)


def refresh_article_package(
    article_package: dict[str, Any],
    must_avoid: list[str] | None = None,
    *,
    rebuild_body: bool = True,
) -> dict[str, Any]:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    citations = safe_list(article_package.get("citations"))
    render_context = safe_dict(article_package.get("render_context"))
    request_context = safe_dict(render_context.get("request"))
    section_must_avoid = clean_string_list(must_avoid if must_avoid is not None else request_context.get("must_avoid"))
    should_refresh_body = rebuild_body or not safe_list(article_package.get("sections") or article_package.get("body_sections"))
    if render_context and not article_package.get("manual_body_override") and should_refresh_body:
        sections = build_sections(
            request_context,
            safe_dict(render_context.get("source_summary")),
            safe_dict(render_context.get("evidence_digest")),
            citations,
            images,
            safe_dict(render_context.get("analysis_brief")),
        )
        article_package["sections"] = deepcopy(sections)
        article_package["body_sections"] = deepcopy(sections)
        article_package["lede"] = build_public_lede(
            request_context,
            safe_dict(render_context.get("source_summary")),
            safe_dict(render_context.get("analysis_brief")),
        )
        article_package["body_markdown"] = apply_must_avoid(
            build_body_markdown(title, subtitle, sections),
            section_must_avoid,
        )
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    lede = clean_text(article_package.get("lede"))
    article_package["image_blocks"] = deepcopy(images)
    article_package["selected_images"] = deepcopy(images)
    if not article_package.get("manual_article_override"):
        article_package["article_markdown"] = apply_must_avoid(
            build_article_markdown(title, subtitle, lede, sections, images, citations),
            section_must_avoid,
        )
    request_context = safe_dict(render_context.get("request"))
    source_summary = safe_dict(render_context.get("source_summary"))
    article_package["article_framework"] = resolve_article_framework(request_context, source_summary)
    article_package["public_topic"] = public_topic_text(request_context, clean_text(source_summary.get("topic")) or "article-topic")
    article_package["publishability_checks"] = build_publishability_checks(title, subtitle, lede, sections)
    article_package["draft_metrics"] = draft_metrics(article_package.get("body_markdown", ""), images, citations)
    article_package["char_count"] = article_package["draft_metrics"]["char_count"]
    article_package["verification"] = {
        "has_visual_evidence": bool(images),
        "has_local_image": any(clean_text(item.get("status")) == "local_ready" for item in images),
        "blocked_images_labeled": all(
            clean_text(item.get("access_mode")) != "blocked" or "blocked" in clean_text(item.get("caption")).lower()
            for item in images
        ),
    }
    return article_package


def is_remote_target(value: Any) -> bool:
    text = clean_text(value)
    return text.startswith(("http://", "https://", "file://"))


def safe_asset_filename(index: int, source_name: str, remote_url: str) -> str:
    parsed = urllib_parse.urlparse(clean_text(remote_url))
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".img"
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in clean_text(source_name)).strip("-") or "asset"
    return f"{index:02d}-{slug[:48]}{suffix}"


def fetch_remote_asset(remote_url: str, destination: Path) -> bool:
    try:
        if clean_text(remote_url).startswith("file://"):
            parsed = urllib_parse.urlparse(remote_url)
            source_path = Path(urllib_request.url2pathname(parsed.path))
            if not source_path.exists():
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source_path.read_bytes())
            return True
        request = urllib_request.Request(remote_url, headers={"User-Agent": "Codex-ArticleWorkflow/1.0"})
        with urllib_request.urlopen(request, timeout=20) as response:
            data = response.read()
        if not data:
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return True
    except (TimeoutError, OSError, urllib_error.URLError, ValueError):
        return False


def localize_selected_images(article_package: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    selected_images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    asset_output_dir = clean_text(request.get("asset_output_dir"))
    if not selected_images or not asset_output_dir or not request.get("download_remote_images", True):
        localization = {
            "asset_output_dir": asset_output_dir,
            "downloaded_count": 0,
            "failed_count": 0,
            "downloaded_assets": [],
            "failed_assets": [],
        }
        article_package["asset_localization"] = localization
        refresh_article_package(article_package, request.get("must_avoid", []), rebuild_body=False)
        return localization

    previous_images = deepcopy(selected_images)
    asset_dir = Path(asset_output_dir)
    downloaded_assets: list[str] = []
    failed_assets: list[str] = []
    for index, item in enumerate(selected_images, start=1):
        current_path = clean_text(item.get("path"))
        if current_path and path_exists(current_path):
            continue
        remote_url = ""
        for candidate in (
            item.get("path"),
            item.get("render_target"),
            item.get("embed_target"),
            item.get("source_url"),
        ):
            if is_remote_target(candidate):
                remote_url = clean_text(candidate)
                break
        if not remote_url:
            continue
        destination = asset_dir / safe_asset_filename(index, item.get("source_name", ""), remote_url)
        if fetch_remote_asset(remote_url, destination):
            local_path = str(destination.resolve())
            item["path"] = local_path
            item["render_target"] = local_path
            item["embed_target"] = normalize_local_path(local_path)
            item["status"] = "local_ready"
            item["localized_from"] = remote_url
            item["embed_markdown"] = f"![{clean_text(item.get('image_id'))}]({normalize_local_path(local_path)})"
            downloaded_assets.append(local_path)
        else:
            failed_assets.append(remote_url)
    article_package["image_blocks"] = deepcopy(selected_images)
    article_package["selected_images"] = deepcopy(selected_images)
    article_package["asset_localization"] = {
        "asset_output_dir": str(asset_dir),
        "downloaded_count": len(downloaded_assets),
        "failed_count": len(failed_assets),
        "downloaded_assets": downloaded_assets,
        "failed_assets": failed_assets,
    }
    refresh_article_package(
        article_package,
        request.get("must_avoid", []),
        rebuild_body=should_rebuild_body_for_image_refresh(article_package, previous_images, selected_images),
    )
    return article_package["asset_localization"]


def preview_src(render_target: str) -> str:
    target = clean_text(render_target)
    if not target:
        return ""
    if target.startswith(("http://", "https://", "file://")):
        return target
    path = Path(target)
    try:
        if path.exists():
            return path.resolve().as_uri()
    except OSError:
        return target
    return target


def paragraph_blocks(text: str) -> list[str]:
    blocks = [clean_text(block) for block in str(text or "").split("\n\n")]
    return [block for block in blocks if block]


def build_article_preview_html(article_package: dict[str, Any]) -> str:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    lede = clean_text(article_package.get("lede"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    citations = safe_list(article_package.get("citations"))
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in images:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)

    def render_images(placement: str) -> str:
        chunks: list[str] = []
        for item in images_by_placement.get(placement, []):
            src = preview_src(item.get("render_target") or item.get("embed_target") or item.get("path") or item.get("source_url"))
            if not src:
                continue
            caption = clean_text(item.get("caption"))
            source_name = clean_text(item.get("source_name"))
            status = clean_text(item.get("status"))
            meta = " | ".join([part for part in [source_name, status] if part])
            chunks.append(
                "<figure>"
                f"<img src=\"{escape(src)}\" alt=\"{escape(caption or source_name or 'image')}\" />"
                f"<figcaption>{escape(caption)}{' | ' + escape(meta) if meta else ''}</figcaption>"
                "</figure>"
            )
        return "".join(chunks)

    section_html: list[str] = []
    for index, section in enumerate(sections, start=1):
        paragraphs = "".join(f"<p>{escape(block)}</p>" for block in paragraph_blocks(section.get("paragraph", "")))
        section_html.append(f"<section><h2>{escape(clean_text(section.get('heading')))}</h2>{paragraphs}{render_images(f'after_section_{index}')}</section>")

    citations_html = "".join(
        f"<li><strong>{escape(clean_text(item.get('citation_id')))}</strong> {escape(clean_text(item.get('source_name')))}"
        f" <a href=\"{escape(clean_text(item.get('url')))}\">{escape(clean_text(item.get('url')))}</a></li>"
        for item in citations
        if clean_text(item.get("source_name")) or clean_text(item.get("url"))
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\" />"
        f"<title>{escape(title or 'Article Preview')}</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.7;color:#1d1d1f;background:#faf8f2;}"
        "h1,h2{line-height:1.25;} .subtitle{color:#555;margin-bottom:24px;} blockquote{border-left:4px solid #c8b27d;padding:8px 16px;background:#fffaf0;margin:20px 0;}"
        "figure{margin:24px 0;} img{max-width:100%;height:auto;border-radius:10px;border:1px solid #ddd;} figcaption{font-size:14px;color:#555;margin-top:8px;}"
        "section{margin:28px 0;} a{color:#0b57d0;word-break:break-all;}"
        "</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        f"<div class=\"subtitle\">{escape(subtitle)}</div>"
        f"<blockquote>{escape(lede)}</blockquote>"
        f"{render_images('after_lede')}"
        f"{''.join(section_html)}"
        f"{render_images('appendix')}"
        "<section><h2>Sources</h2><ol>"
        f"{citations_html or '<li>None</li>'}"
        "</ol></section></body></html>"
    )


def draft_metrics(body_markdown: str, images: list[dict[str, Any]], citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "char_count": len(clean_text(body_markdown).replace(" ", "")),
        "section_count": body_markdown.count("\n## "),
        "image_count": len(images),
        "citation_count": len(citations),
    }


PUBLISHABILITY_BANNED_PHRASES = [
    "best writer-safe thesis",
    "built from the current indexed result",
    "what is confirmed and what still is not",
    "confirmed and not confirmed",
    "story angles",
    "images and screenshots",
    "boundaries and open questions",
    "this version is image-first",
    "\u5f53\u524d\u6700\u7a33\u59a5\u7684\u5199\u6cd5",
    "\u8fd9\u7248\u5185\u5bb9\u57fa\u4e8e\u5f53\u524d\u7d22\u5f15\u7ed3\u679c\u751f\u6210",
    "\u54ea\u4e9b\u5df2\u7ecf\u786e\u8ba4",
    "\u54ea\u4e9b\u4ecd\u672a\u786e\u8ba4",
    "\u53ef\u5199\u89d2\u5ea6",
    "\u8fb9\u754c\u4e0e\u5f85\u786e\u8ba4\u70b9",
]


def build_publishability_checks(
    title: str,
    subtitle: str,
    lede: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    fields = {
        "title": clean_text(title),
        "subtitle": clean_text(subtitle),
        "lede": clean_text(lede),
    }
    for index, section in enumerate(sections, start=1):
        fields[f"section_{index}_heading"] = clean_text(section.get("heading"))
        fields[f"section_{index}_paragraph"] = clean_text(section.get("paragraph"))
    for field_name, value in fields.items():
        lowered = value.lower()
        for phrase in PUBLISHABILITY_BANNED_PHRASES:
            if phrase.lower() in lowered:
                matches.append({"field": field_name, "phrase": phrase})
        if field_name == "title" and re.search(
            r"(36kr|36\u6c2a|\u9996\u53d1|\u72ec\u5bb6)",
            lowered,
        ):
            if not any(
                item.get("field") == "title" and item.get("phrase") == "source_brand_leakage"
                for item in matches
            ):
                matches.append({"field": field_name, "phrase": "source_brand_leakage"})
        if field_name == "title" and re.search(r"(36kr|36氪|首发|独家)", lowered):
            matches.append({"field": field_name, "phrase": "source_brand_leakage"})
    deduped_matches: list[dict[str, str]] = []
    seen_match_keys: set[tuple[str, str]] = set()
    for item in matches:
        key = (clean_text(item.get("field")), clean_text(item.get("phrase")))
        if key in seen_match_keys:
            continue
        seen_match_keys.add(key)
        deduped_matches.append(item)
    matches = deduped_matches
    return {
        "passed": not matches,
        "match_count": len(matches),
        "matches": matches,
    }


def build_report_markdown(article_package: dict[str, Any]) -> str:
    lines = [article_package.get("article_markdown", "").rstrip(), "", "## Image Assets"]
    for item in safe_list(article_package.get("selected_images") or article_package.get("image_blocks")):
        lines.append(f"- {item.get('asset_id') or item.get('image_id', '')} | {item.get('source_name', '')} | {item.get('status', '')}")
        lines.append(f"  Caption: {item.get('caption', '')}")
        lines.append(f"  Path: {item.get('path', '') or 'none'}")
        lines.append(f"  Source URL: {item.get('source_url', '') or 'none'}")
    if not safe_list(article_package.get("selected_images") or article_package.get("image_blocks")):
        lines.append("- None")
    lines.extend(["", "## Citations"])
    for item in safe_list(article_package.get("citations")):
        lines.append(f"- {item.get('citation_id', '')} | {item.get('source_name', '')} | {item.get('channel', '')}")
        lines.append(f"  URL: {item.get('url', '') or 'none'}")
        lines.append(f"  Excerpt: {item.get('excerpt', '') or 'none'}")
    if not safe_list(article_package.get("citations")):
        lines.append("- None")
    lines.extend(["", "## Draft Thesis", clean_text(article_package.get("draft_thesis")) or "None"])
    lines.extend(["", "## Draft Claim Map"])
    for item in safe_list(article_package.get("draft_claim_map")):
        lines.append(
            f"- {clean_text(item.get('claim_label'))}: {clean_text(item.get('claim_text'))} | "
            f"citations: {', '.join(clean_string_list(item.get('citation_ids'))) or 'none'} | "
            f"support: {clean_text(item.get('support_level')) or 'unknown'}"
        )
    if not safe_list(article_package.get("draft_claim_map")):
        lines.append("- None")
    lines.extend(["", "## Writer Risk Notes"])
    for item in clean_string_list(article_package.get("writer_risk_notes")):
        lines.append(f"- {item}")
    if not clean_string_list(article_package.get("writer_risk_notes")):
        lines.append("- None")
    publishability_checks = safe_dict(article_package.get("publishability_checks"))
    if publishability_checks:
        lines.extend(
            [
                "",
                "## Publishability Checks",
                f"- Passed: {'yes' if publishability_checks.get('passed') else 'no'}",
                f"- Match count: {int(publishability_checks.get('match_count', 0) or 0)}",
            ]
        )
        for item in safe_list(publishability_checks.get("matches")):
            lines.append(f"- {clean_text(item.get('field'))}: {clean_text(item.get('phrase'))}")
    localization = safe_dict(article_package.get("asset_localization"))
    if localization:
        lines.extend(
            [
                "",
                "## Asset Localization",
                f"- Asset directory: {clean_text(localization.get('asset_output_dir')) or 'none'}",
                f"- Downloaded: {int(localization.get('downloaded_count', 0) or 0)}",
                f"- Failed: {int(localization.get('failed_count', 0) or 0)}",
            ]
        )
    profile_status = safe_dict(article_package.get("feedback_profile_status"))
    if profile_status:
        applied_paths = clean_string_list(profile_status.get("applied_paths"))
        lines.extend(
            [
                "",
                "## Feedback Profiles",
                f"- Profile directory: {clean_text(profile_status.get('profile_dir')) or 'none'}",
                f"- Applied now: {', '.join(applied_paths) if applied_paths else 'none'}",
                f"- Global defaults: {'saved' if profile_status.get('global_exists') else 'not saved yet'} | {clean_text(profile_status.get('global_profile_path')) or 'none'}",
                f"- Topic defaults: {'saved' if profile_status.get('topic_exists') else 'not saved yet'} | {clean_text(profile_status.get('topic_profile_path')) or 'none'}",
            ]
        )
    for note in safe_list(article_package.get("editor_notes")):
        lines.append(f"- {note}")
    return "\n".join(lines).strip() + "\n"


def assemble_article_package(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    image_candidates: list[dict[str, Any]],
    analysis_brief: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected_images = build_selected_images(image_candidates, request)
    title = build_title(request, evidence_digest, selected_images)
    subtitle = build_subtitle(request, source_summary, selected_images)
    effective_analysis_brief = safe_dict(analysis_brief) or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        selected_images,
    )
    sections = build_sections(request, source_summary, evidence_digest, citations, selected_images, effective_analysis_brief)
    body_markdown = apply_must_avoid(build_body_markdown(title, subtitle, sections), request.get("must_avoid", []))
    lede = build_public_lede(request, source_summary, effective_analysis_brief)
    article_markdown = apply_must_avoid(
        build_article_markdown(title, subtitle, lede, sections, selected_images, citations),
        request.get("must_avoid", []),
    )
    draft_thesis = clean_text(effective_analysis_brief.get("recommended_thesis")) or clean_text(source_summary.get("core_verdict"))
    draft_claim_map = build_draft_claim_map(citations, effective_analysis_brief) if effective_analysis_brief else []
    style_profile_applied = build_style_profile_applied(request)
    writer_risk_notes = build_writer_risk_notes(effective_analysis_brief, source_summary) if effective_analysis_brief else []
    article_framework = resolve_article_framework(request, source_summary)
    publishability_checks = build_publishability_checks(title, subtitle, lede, sections)

    editor_notes = []
    if int(source_summary.get("blocked_source_count", 0)) > 0:
        editor_notes.append("Some sources were blocked or background-only. Do not turn them into confirmed facts in the article.")
    if not selected_images:
        editor_notes.append("No reusable image asset is attached yet. If this must be visual, capture or save the images first.")
    if request.get("draft_mode") == "image_only":
        editor_notes.append("This draft was generated in image-only mode. Text is intentionally minimal and should not overstate what the images prove.")
    if not publishability_checks.get("passed"):
        editor_notes.append("Publishability checks flagged operator-style language. Review the title and section copy before publishing.")

    package = {
        "title": title,
        "subtitle": subtitle,
        "lede": lede,
        "sections": sections,
        "body_sections": sections,
        "body_markdown": body_markdown,
        "article_markdown": article_markdown,
        "image_blocks": deepcopy(selected_images),
        "selected_images": deepcopy(selected_images),
        "citations": citations,
        "editor_notes": editor_notes,
        "draft_mode": request.get("draft_mode"),
        "language_mode": request.get("language_mode"),
        "article_framework": article_framework,
        "public_topic": public_topic_text(request, clean_text(source_summary.get("topic")) or "article-topic"),
        "draft_thesis": draft_thesis,
        "draft_claim_map": draft_claim_map,
        "publishability_checks": publishability_checks,
        "style_profile_applied": style_profile_applied,
        "writer_risk_notes": writer_risk_notes,
        "feedback_profile_status": deepcopy(safe_dict(request.get("feedback_profile_status"))),
        "render_context": {
            "request": {
                "topic": clean_text(request.get("topic")),
                "analysis_time": isoformat_or_blank(request.get("analysis_time")),
                "angle": clean_text(request.get("angle")),
                "angle_zh": clean_text(request.get("angle_zh")),
                "must_include": clean_string_list(request.get("must_include")),
                "must_avoid": clean_string_list(request.get("must_avoid")),
                "draft_mode": clean_text(request.get("draft_mode")),
                "language_mode": clean_text(request.get("language_mode")),
                "article_framework": clean_text(request.get("article_framework")),
            },
            "source_summary": deepcopy(source_summary),
            "evidence_digest": deepcopy(evidence_digest),
            "analysis_brief": deepcopy(effective_analysis_brief),
        },
    }
    refresh_article_package(package, request.get("must_avoid", []))
    return package, selected_images


def build_article_draft(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    evidence_bundle = ensure_evidence_bundle(request)
    request["evidence_bundle"] = evidence_bundle
    source_summary = safe_dict(evidence_bundle.get("source_summary"))
    evidence_digest = safe_dict(evidence_bundle.get("evidence_digest"))
    citations = deepcopy(safe_list(evidence_bundle.get("citations")))
    image_candidates = deepcopy(safe_list(evidence_bundle.get("image_candidates")))
    analysis_brief = safe_dict(request.get("analysis_brief"))
    if not analysis_brief:
        analysis_brief_result = build_analysis_brief(
            {
                "source_result": request["source_result"],
                "source_result_path": request.get("source_result_path"),
                "topic": request.get("topic"),
                "analysis_time": isoformat_or_blank(request["analysis_time"]),
            }
        )
        analysis_brief = safe_dict(analysis_brief_result.get("analysis_brief"))
    analysis_brief = analysis_brief or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        image_candidates,
    )
    request["analysis_brief"] = analysis_brief
    article_package, selected_images = assemble_article_package(
        request,
        source_summary,
        evidence_digest,
        citations,
        image_candidates,
        analysis_brief,
    )
    if clean_string_list(request.get("applied_feedback_profiles")):
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Applied feedback profiles: {', '.join(clean_string_list(request.get('applied_feedback_profiles')))}"]
        )
    asset_localization = localize_selected_images(article_package, request)
    selected_images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    image_candidates = merge_localized_image_candidates(image_candidates, selected_images)
    evidence_bundle["image_candidates"] = deepcopy(image_candidates)

    result = {
        "request": {
            **request,
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "source_result": None,
            "evidence_bundle": {
                "contract_version": clean_text(evidence_bundle.get("contract_version")),
                "citation_count": len(citations),
                "image_candidate_count": len(image_candidates),
            },
        },
        "source_summary": source_summary,
        "source_context": {
            "source_kind": source_summary.get("source_kind"),
            "topic": source_summary.get("topic"),
            "analysis_time": source_summary.get("analysis_time"),
            "source_result_path": request.get("source_result_path", ""),
        },
        "evidence_digest": evidence_digest,
        "evidence_bundle": evidence_bundle,
        "analysis_brief": analysis_brief,
        "draft_context": {
            "source_summary": source_summary,
            "evidence_digest": evidence_digest,
            "analysis_brief": analysis_brief,
            "citation_candidates": citations,
            "image_candidates": image_candidates,
            "selected_images": deepcopy(selected_images),
            "evidence_bundle": evidence_bundle,
            "source_result_path": request.get("source_result_path", ""),
            "applied_feedback_profiles": clean_string_list(request.get("applied_feedback_profiles")),
            "asset_output_dir": clean_text(request.get("asset_output_dir")),
        },
        "article_package": article_package,
        "asset_localization": asset_localization,
        "preview_html": build_article_preview_html(article_package),
        "revision_history": [],
        "revision_log": [],
    }
    result["report_markdown"] = build_report_markdown(article_package)
    return result


__all__ = [
    "apply_must_avoid",
    "assemble_article_package",
    "build_article_draft",
    "build_article_markdown",
    "build_body_markdown",
    "build_citations",
    "build_image_candidates",
    "build_report_markdown",
    "build_sections",
    "build_selected_images",
    "build_source_summary",
    "build_subtitle",
    "build_title",
    "clean_string_list",
    "clean_text",
    "draft_metrics",
    "load_json",
    "merge_localized_image_candidates",
    "normalize_latest_signals",
    "normalize_request",
    "path_exists",
    "safe_dict",
    "safe_list",
    "write_json",
]


