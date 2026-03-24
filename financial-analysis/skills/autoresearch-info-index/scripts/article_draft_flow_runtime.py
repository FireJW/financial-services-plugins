#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from article_feedback_profiles import feedback_profile_status, load_feedback_profiles, merge_request_with_profiles, resolve_profile_dir
from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, short_excerpt, write_json


def now_utc() -> datetime:
    return datetime.now(UTC)


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
        "must_include": clean_string_list(payload.get("must_include") or payload.get("focus_points")),
        "must_avoid": clean_string_list(payload.get("must_avoid")),
        "asset_output_dir": clean_text(payload.get("asset_output_dir")),
        "download_remote_images": str(payload.get("download_remote_images", "")).strip().lower() not in {"0", "false", "no", "off"},
        "feedback_profile_dir": clean_text(payload.get("feedback_profile_dir")),
        "source_result": source_result,
        "source_result_path": source_result_path,
    }
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    profiles = load_feedback_profiles(profile_dir, request.get("topic", "article-topic"))
    request = merge_request_with_profiles(request, profiles)
    request["tone"] = clean_text(request.get("tone") or "neutral-cautious")
    request["max_images"] = max(0, min(int(request.get("max_images", 3) or 3), 8))
    request["image_strategy"] = clean_text(request.get("image_strategy") or "mixed")
    request["draft_mode"] = sanitize_draft_mode(request.get("draft_mode"))
    request["language_mode"] = sanitize_language_mode(request.get("language_mode"))
    request["feedback_profile_dir"] = str(profile_dir)
    request["feedback_profile_status"] = feedback_profile_status(profile_dir, request.get("topic", "article-topic"))
    return request

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


def build_image_candidates(source_result: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(role: str, source_name: str, path: str, source_url: str, summary: str, access_mode: str, relevance: str, source_tier: int) -> None:
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
                clean_text(media.get("ocr_summary") or media.get("ocr_text_raw")),
                access_mode,
                clean_text(media.get("image_relevance_to_post")) or "medium",
                3,
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


def build_selected_images(image_candidates: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in image_candidates[: request.get("max_images", 3)]:
        path_text = clean_text(item.get("path"))
        source_url = clean_text(item.get("source_url"))
        access_mode = clean_text(item.get("access_mode"))
        summary = clean_text(item.get("summary") or item.get("caption"))
        if summary:
            caption = summary
        elif item.get("role") == "root_post_screenshot" and access_mode == "blocked":
            caption = "Root post screenshot from a blocked page. Keep it as visual evidence only."
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


def build_title(request: dict[str, Any], digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    title_hint = clean_text(request.get("title_hint"))
    title_hint_zh = clean_text(request.get("title_hint_zh"))
    if title_hint or title_hint_zh:
        return bilingual_heading(title_hint_zh, title_hint, language_mode)
    topic = clean_text(request.get("topic")) or "Developing Story"
    if request.get("draft_mode") == "image_only":
        return bilingual_heading(f"{topic}：图片现在显示了什么", f"{topic}: what the images show right now", language_mode)
    if digest.get("confirmed"):
        return bilingual_heading(f"{topic}：哪些已经确认，哪些仍未确认", f"{topic}: what is confirmed and what still is not", language_mode)
    if selected_images:
        return bilingual_heading(f"{topic}：最新信号与值得保留的关键图片", f"{topic}: latest signals and the key images worth keeping", language_mode)
    return bilingual_heading(f"{topic}：最新公开信息快照", f"{topic}: latest public information snapshot", language_mode)


def build_subtitle(request: dict[str, Any], summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    subtitle_hint = clean_text(request.get("subtitle_hint"))
    subtitle_hint_zh = clean_text(request.get("subtitle_hint_zh"))
    if subtitle_hint or subtitle_hint_zh:
        return bilingual_text(subtitle_hint_zh, subtitle_hint, language_mode)
    if request.get("draft_mode") == "image_only":
        return bilingual_text(
            "这版内容以图片为先，只保留解释图片所需的最低限度文字。",
            "This version is image-first. It keeps the visual evidence and only adds the minimum text needed to explain what the images appear to show.",
            language_mode,
        )
    if summary.get("source_kind") == "x_index" and selected_images:
        return bilingual_text(
            "这版内容基于已保存的 X 证据、截图和图片摘要，图片会一并保留下来以便后续复用。",
            "Built from saved X evidence, screenshots, and image summaries, with images preserved for reuse.",
            language_mode,
        )
    return bilingual_text(
        "这版内容基于当前索引结果生成，会把已确认事实、未解问题和图片证据分开处理。",
        "Built from the current indexed result, keeping confirmed facts, open questions, and visual evidence separate.",
        language_mode,
    )


def apply_must_avoid(text: str, must_avoid: list[str]) -> str:
    updated = text
    for phrase in must_avoid:
        updated = updated.replace(phrase, "")
    return updated


def join_with_semicolons(items: list[str], empty_text: str) -> str:
    clean_items = [clean_text(item) for item in items if clean_text(item)]
    return "; ".join(clean_items) if clean_items else empty_text


def strip_terminal_punctuation(text: str) -> str:
    return clean_text(text).rstrip(" .;:")


def sentence_case_list(items: list[str]) -> list[str]:
    return [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]


def lowercase_first(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    return cleaned[:1].lower() + cleaned[1:]


def citation_refs(citations: list[dict[str, Any]], start: int = 0, count: int = 2) -> str:
    refs = [f"[{item.get('citation_id', '')}]" for item in citations[start : start + count] if clean_text(item.get("citation_id"))]
    return "".join(refs)


def join_with_commas(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def claim_sentence(items: list[str], empty_text: str) -> str:
    clean_items = sentence_case_list(items)
    return join_with_semicolons(clean_items, empty_text)


def latest_source_names(signals: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for item in signals[:3]:
        name = clean_text(item.get("source_name"))
        if name and name not in names:
            names.append(name)
    return join_with_commas(names, "recent public reporting")


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


def image_sentence_zh(images: list[dict[str, Any]]) -> str:
    if not images:
        return "当前这版草稿还没有可直接复用的图片资产。"
    parts = []
    for item in images[:3]:
        source_name = clean_text(item.get("source_name")) or "未命名来源"
        caption = short_excerpt(clean_text(item.get("caption")), limit=80) or "暂无机器摘要"
        parts.append(f"{source_name}：{caption}")
    return "当前保留下来的图片包括：" + "；".join(parts) + "。"


def visual_evidence_sentence_zh(images: list[dict[str, Any]]) -> str:
    if not images:
        return "目前没有可直接复用的图片资产，因此这版内容实际上还不能算真正的图文优先稿。"
    parts = []
    for item in images[:3]:
        role = clean_text(item.get("role")).replace("_", " ")
        status = clean_text(item.get("status")) or "unknown"
        caption = short_excerpt(clean_text(item.get("caption")), limit=90) or "暂无机器摘要"
        parts.append(f"{role}：{caption} [{status}]")
    return "图片证据层显示：" + "；".join(parts) + "。"


def build_sections(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    draft_mode = request.get("draft_mode", "balanced")
    language_mode = request.get("language_mode", "english")
    topic = source_summary.get("topic", request.get("topic"))
    analysis_time = source_summary.get("analysis_time", "")
    lead_refs = citation_refs(citations, 0, 2)
    support_refs = citation_refs(citations, 2, 2) or lead_refs
    background_refs = citation_refs(citations, 4, 2) or support_refs or lead_refs
    confirmed_items = sentence_case_list(evidence_digest.get("confirmed", []))
    not_confirmed_items = sentence_case_list(evidence_digest.get("not_confirmed", []))
    inference_items = sentence_case_list(evidence_digest.get("inference_only", []))
    confirmed_items_zh = sentence_case_list(evidence_digest.get("confirmed_zh", []))
    not_confirmed_items_zh = sentence_case_list(evidence_digest.get("not_confirmed_zh", []))
    inference_items_zh = sentence_case_list(evidence_digest.get("inference_only_zh", []))
    market_relevance = clean_string_list(evidence_digest.get("market_relevance"))
    market_relevance_zh = clean_string_list(evidence_digest.get("market_relevance_zh"))
    signals = normalize_latest_signals(evidence_digest.get("latest_signals"))
    lead_confirmed = confirmed_items[0] if confirmed_items else ""
    lead_not_confirmed = not_confirmed_items[0] if not_confirmed_items else ""
    lead_confirmed_zh = confirmed_items_zh[0] if confirmed_items_zh else lead_confirmed
    lead_not_confirmed_zh = not_confirmed_items_zh[0] if not_confirmed_items_zh else lead_not_confirmed

    opening_parts = []
    if lead_confirmed:
        opening_parts.append(
            f"As of {analysis_time}, the strongest public read on '{topic}' is that {lowercase_first(lead_confirmed)}.{lead_refs}"
        )
    else:
        opening_parts.append(
            f"As of {analysis_time}, the public record around '{topic}' is still incomplete and does not support a single high-conviction call.{lead_refs}"
        )
    if lead_not_confirmed:
        opening_parts.append(
            f"The same record still does not confirm a stronger leap: {lowercase_first(lead_not_confirmed)}.{support_refs}"
        )
    if signals:
        opening_parts.append(
            f"The freshest movement in the story is coming from {latest_source_names(signals)}, which keeps the situation active but not settled."
        )
    if request.get("angle"):
        opening_parts.append(f"This draft is written with a specific lens: {strip_terminal_punctuation(request.get('angle'))}.")
    if request.get("must_include"):
        opening_parts.append(
            f"Priority points to keep in view are {join_with_commas(request.get('must_include', [])[:3], 'none')}."
        )
    opening = " ".join(opening_parts)
    opening_zh_parts = []
    if lead_confirmed_zh:
        opening_zh_parts.append(
            f"截至 {analysis_time}，围绕“{topic}”目前最稳妥的公开判断是：{strip_terminal_punctuation(lead_confirmed_zh)}。{lead_refs}"
        )
    else:
        opening_zh_parts.append(
            f"截至 {analysis_time}，关于“{topic}”的公开信息仍然不完整，还不足以支撑单一且高把握度的判断。{lead_refs}"
        )
    if lead_not_confirmed_zh:
        opening_zh_parts.append(
            f"但同一批公开材料仍然不足以证明更强的说法：{strip_terminal_punctuation(lead_not_confirmed_zh)}。{support_refs}"
        )
    if signals:
        opening_zh_parts.append(
            f"最近一轮增量信息主要来自 {latest_source_names(signals)}，这说明局势仍在推进，但远没有尘埃落定。"
        )
    if request.get("angle_zh"):
        opening_zh_parts.append(f"这篇稿子的中文角度是：{strip_terminal_punctuation(request.get('angle_zh'))}。")
    elif request.get("angle"):
        opening_zh_parts.append(f"这篇稿子的写作重点是：{strip_terminal_punctuation(request.get('angle'))}。")
    if request.get("must_include"):
        opening_zh_parts.append(f"需要优先保留的点包括：{join_with_commas(request.get('must_include')[:3], '无')}。")
    opening_zh = "".join(opening_zh_parts)

    confirmed_text = claim_sentence(
        evidence_digest.get("confirmed", [])[:4],
        "No high-confidence public confirmation is available yet.",
    )
    confirmed_text_zh = claim_sentence(
        evidence_digest.get("confirmed_zh", [])[:4],
        "目前还没有高置信度的公开确认。",
    )
    not_confirmed_text = claim_sentence(
        evidence_digest.get("not_confirmed", [])[:4],
        "No additional unconfirmed items were separately listed.",
    )
    not_confirmed_text_zh = claim_sentence(
        evidence_digest.get("not_confirmed_zh", [])[:4],
        "目前没有额外需要单独标出的未证实事项。",
    )
    inference_text = claim_sentence(
        evidence_digest.get("inference_only", [])[:3],
        "No inference-only items were separately listed.",
    )
    inference_text_zh = claim_sentence(
        evidence_digest.get("inference_only_zh", [])[:3],
        "目前没有需要单独列出的纯推断项。",
    )
    interval = evidence_digest.get("confidence_interval", [0, 0])
    next_watch = join_with_semicolons(
        evidence_digest.get("next_watch_items", [])[:3],
        "wait for stronger sources to confirm or contradict the current picture",
    )
    confidence_text = f"This is still a {interval[0]}-{interval[1]} confidence call, which means the read is usable but far from locked."
    blocked_text = (
        f" There are {source_summary.get('blocked_source_count', 0)} blocked sources in the package, so any stronger conclusion would need cleaner confirmation."
        if int(source_summary.get("blocked_source_count", 0)) > 0
        else ""
    )
    boundary = f"{confidence_text}{blocked_text} The main things to watch next are: {next_watch}."
    boundary_zh = (
        f"这仍然只是一个 {interval[0]}-{interval[1]} 的把握区间，说明当前判断可以使用，但远远谈不上锁定。"
        f"{' 当前包里还有被阻挡的来源，因此如果要得出更强结论，还需要更干净的确认。' if int(source_summary.get('blocked_source_count', 0)) > 0 else ''}"
        f"下一步最值得盯住的是：{next_watch}。"
    )

    confirmed_paragraph = (
        f"The clearest point supported by current public reporting is {confirmed_text}.{lead_refs} "
        f"What the same reporting does not establish is {not_confirmed_text}.{support_refs} "
        f"If the story moves beyond that line, the evidence base will need to improve first."
    )
    confirmed_paragraph_zh = (
        f"当前公开报道最能支持的判断是：{confirmed_text_zh}。{lead_refs}"
        f"但同一批报道并不能证明的是：{not_confirmed_text_zh}。{support_refs}"
        f"如果后续叙事要再往前走，证据质量必须先提升。"
    )
    latest_paragraph = (
        f"The most recent reporting is clustered in {latest_source_names(signals)}. "
        f"{signal_sentence(signals)} "
        f"Taken together, those signals reinforce the base case without proving the more aggressive claims.{support_refs}"
        if signals
        else signal_sentence(signals)
    )
    latest_paragraph_zh = (
        f"最近的公开报道主要集中在 {latest_source_names(signals)}。"
        f"{'这些来源共同强化了当前的基础判断，但还不足以证明更激进的说法。' if signals else ''}"
    )
    why_matter_paragraph = (
        f"This matters most for {join_with_commas(market_relevance, 'headline-sensitive markets')}. "
        "Even before the facts fully settle, changes in the tone of talks, force posture, or shipping risk can move expectations quickly."
    )
    why_matter_paragraph_zh = (
        f"这件事最直接影响的是 {join_with_commas(market_relevance_zh or market_relevance, '对消息面敏感的市场')}。"
        "即便事实还没有完全落定，只要和谈语气、军事姿态或航运风险出现变化，市场预期就可能快速重估。"
    )

    if draft_mode == "image_only":
        return [
            {
                "heading": bilingual_heading("核心判断", "Bottom Line", language_mode),
                "paragraph": bilingual_text(opening_zh, opening, language_mode),
            },
            {
                "heading": bilingual_heading("图片显示了什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(visual_evidence_sentence_zh(images), visual_evidence_sentence(images), language_mode),
            },
            {
                "heading": bilingual_heading("图片不能证明什么", "What The Images Do Not Prove", language_mode),
                "paragraph": bilingual_text(
                    f"仅靠图片层本身，并不能证明：{not_confirmed_text_zh}。纯推断项仍然包括：{inference_text_zh}。",
                    f"The visual layer does not by itself prove {not_confirmed_text}. Inference-only items remain {inference_text}.",
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("边界条件", "Boundaries", language_mode),
                "paragraph": bilingual_text(boundary_zh, boundary, language_mode),
            },
        ]

    sections = [
        {
            "heading": bilingual_heading("核心判断", "Bottom Line", language_mode),
            "paragraph": bilingual_text(opening_zh, opening, language_mode),
        },
        {
            "heading": bilingual_heading("已确认与未确认", "Confirmed And Not Confirmed", language_mode),
            "paragraph": bilingual_text(confirmed_paragraph_zh, confirmed_paragraph, language_mode),
        },
        {
            "heading": bilingual_heading("最新增量信息", "Latest Signals", language_mode),
            "paragraph": bilingual_text(latest_paragraph_zh, latest_paragraph, language_mode),
        },
        {
            "heading": bilingual_heading("为什么这件事重要", "Why This Matters", language_mode),
            "paragraph": bilingual_text(why_matter_paragraph_zh, why_matter_paragraph, language_mode),
        },
        {
            "heading": bilingual_heading("图片与截图", "Images And Screenshots", language_mode),
            "paragraph": bilingual_text(image_sentence_zh(images), image_sentence(images), language_mode),
        },
        {
            "heading": bilingual_heading("边界条件", "Boundaries", language_mode),
            "paragraph": bilingual_text(
                f"{boundary_zh} {'当前包里没有明显的纯推断项。' if not inference_items_zh else '仍处在推断层的内容包括：' + inference_text_zh + '。'}",
                f"{boundary} {'There are no major inference-only items in the current package.' if not inference_items else 'Inference-only items still in the background are ' + inference_text + '.'}",
                language_mode,
            ),
        },
    ]
    if draft_mode == "image_first":
        sections.insert(
            1,
            {
                "heading": bilingual_heading("视觉证据", "Visual Evidence", language_mode),
                "paragraph": bilingual_text(visual_evidence_sentence_zh(images), visual_evidence_sentence(images), language_mode),
            },
        )
    return sections


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
                caption_bits = [clean_text(item.get("caption"))]
                if clean_text(item.get("source_name")):
                    caption_bits.append(f"Source: {clean_text(item.get('source_name'))}")
                if clean_text(item.get("status")):
                    caption_bits.append(f"Status: {clean_text(item.get('status'))}")
                lines.append(f"_{' | '.join(bit for bit in caption_bits if bit)}_")
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


def refresh_article_package(article_package: dict[str, Any], must_avoid: list[str] | None = None) -> dict[str, Any]:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    citations = safe_list(article_package.get("citations"))
    render_context = safe_dict(article_package.get("render_context"))
    request_context = safe_dict(render_context.get("request"))
    section_must_avoid = clean_string_list(must_avoid if must_avoid is not None else request_context.get("must_avoid"))
    if render_context and not article_package.get("manual_body_override"):
        sections = build_sections(
            request_context,
            safe_dict(render_context.get("source_summary")),
            safe_dict(render_context.get("evidence_digest")),
            citations,
            images,
        )
        article_package["sections"] = deepcopy(sections)
        article_package["body_sections"] = deepcopy(sections)
        article_package["lede"] = sections[0]["paragraph"] if sections else ""
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
        refresh_article_package(article_package, request.get("must_avoid", []))
        return localization

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
    refresh_article_package(article_package, request.get("must_avoid", []))
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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected_images = build_selected_images(image_candidates, request)
    title = build_title(request, evidence_digest, selected_images)
    subtitle = build_subtitle(request, source_summary, selected_images)
    sections = build_sections(request, source_summary, evidence_digest, citations, selected_images)
    body_markdown = apply_must_avoid(build_body_markdown(title, subtitle, sections), request.get("must_avoid", []))
    lede = sections[0]["paragraph"] if sections else ""
    article_markdown = apply_must_avoid(
        build_article_markdown(title, subtitle, lede, sections, selected_images, citations),
        request.get("must_avoid", []),
    )

    editor_notes = []
    if int(source_summary.get("blocked_source_count", 0)) > 0:
        editor_notes.append("Some sources were blocked or background-only. Do not turn them into confirmed facts in the article.")
    if not selected_images:
        editor_notes.append("No reusable image asset is attached yet. If this must be visual, capture or save the images first.")
    if request.get("draft_mode") == "image_only":
        editor_notes.append("This draft was generated in image-only mode. Text is intentionally minimal and should not overstate what the images prove.")

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
            },
            "source_summary": deepcopy(source_summary),
            "evidence_digest": deepcopy(evidence_digest),
        },
    }
    refresh_article_package(package, request.get("must_avoid", []))
    return package, selected_images


def build_article_draft(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    source_summary, evidence_digest = build_source_summary(request["source_result"], request)
    citations = build_citations(request["source_result"])
    image_candidates = build_image_candidates(request["source_result"], request)
    article_package, selected_images = assemble_article_package(request, source_summary, evidence_digest, citations, image_candidates)
    if clean_string_list(request.get("applied_feedback_profiles")):
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Applied feedback profiles: {', '.join(clean_string_list(request.get('applied_feedback_profiles')))}"]
        )
    asset_localization = localize_selected_images(article_package, request)
    selected_images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))

    result = {
        "request": {**request, "analysis_time": isoformat_or_blank(request["analysis_time"]), "source_result": None},
        "source_summary": source_summary,
        "source_context": {
            "source_kind": source_summary.get("source_kind"),
            "topic": source_summary.get("topic"),
            "analysis_time": source_summary.get("analysis_time"),
            "source_result_path": request.get("source_result_path", ""),
        },
        "evidence_digest": evidence_digest,
        "draft_context": {
            "source_summary": source_summary,
            "evidence_digest": evidence_digest,
            "citation_candidates": citations,
            "image_candidates": image_candidates,
            "selected_images": deepcopy(selected_images),
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
    "normalize_latest_signals",
    "normalize_request",
    "path_exists",
    "safe_dict",
    "safe_list",
    "write_json",
]
