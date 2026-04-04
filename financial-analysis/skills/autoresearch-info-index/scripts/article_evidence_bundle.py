#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib import error as urllib_error

from news_index_runtime import fetch_public_page_hints, isoformat_or_blank, short_excerpt


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


def looks_like_ui_capture_noise(text: Any) -> bool:
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    if not cleaned:
        return False
    markers = (
        'link "',
        "/url:",
        "progressbar",
        "banner - main",
        "login",
        "log in",
        "sign in",
        "sign up",
        "new to x",
        "加载中",
        "登录",
        "注册",
        "抢先知道",
        "main:",
    )
    return any(marker in lowered or marker in cleaned for marker in markers)


def first_meaningful_text(*values: Any, fallback: str = "") -> str:
    noisy_fallback = clean_text(fallback)
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        if not noisy_fallback:
            noisy_fallback = text
        if not looks_like_ui_capture_noise(text):
            return text
    return noisy_fallback


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


OPERATOR_REVIEW_PRIORITY_RANK = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "none": 0,
}


def normalize_operator_review_priority_level(value: Any) -> str:
    level = clean_text(value).lower()
    return level if level in OPERATOR_REVIEW_PRIORITY_RANK else "none"


def normalize_operator_review_queue_entry(item: dict[str, Any], **fallbacks: Any) -> dict[str, Any]:
    priority_level = normalize_operator_review_priority_level(item.get("priority_level"))
    review_required = bool(item.get("review_required")) or priority_level != "none"
    if not review_required:
        return {}
    priority_score = max(0, int(item.get("priority_score", 0) or 0))
    title = clean_text(item.get("title") or fallbacks.get("title") or item.get("topic_id") or item.get("url"))
    source_name = clean_text(item.get("source_name") or fallbacks.get("source_name"))
    url = clean_text(item.get("url") or fallbacks.get("url"))
    topic_id = clean_text(item.get("topic_id") or fallbacks.get("topic_id"))
    summary = clean_text(item.get("summary") or fallbacks.get("summary"))
    recommended_action = clean_text(item.get("recommended_action") or fallbacks.get("recommended_action"))
    return {
        "title": title,
        "source_name": source_name,
        "url": url,
        "topic_id": topic_id,
        "priority_level": priority_level,
        "priority_score": priority_score,
        "summary": summary,
        "recommended_action": recommended_action,
        "review_required": review_required,
    }


def collect_reddit_operator_review_queue(source_result: dict[str, Any], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(item: dict[str, Any], **fallbacks: Any) -> None:
        normalized = normalize_operator_review_queue_entry(item, **fallbacks)
        if not normalized:
            return
        key = (
            clean_text(normalized.get("title")),
            clean_text(normalized.get("source_name")),
            clean_text(normalized.get("url")),
            clean_text(normalized.get("topic_id")),
        )
        if key in seen:
            return
        seen.add(key)
        queue.append(normalized)

    for entry in safe_list(source_result.get("operator_review_queue")) + safe_list(runtime.get("operator_review_queue")):
        if isinstance(entry, dict):
            add(entry)

    for topic in safe_list(source_result.get("ranked_topics")) + safe_list(runtime.get("ranked_topics")):
        if not isinstance(topic, dict):
            continue
        operator_priority = safe_dict(topic.get("operator_review_priority"))
        operator_review = safe_dict(topic.get("comment_operator_review"))
        add(
            operator_priority,
            title=clean_text(topic.get("title")),
            topic_id=clean_text(topic.get("topic_id")),
            summary=clean_text(operator_priority.get("summary") or operator_review.get("summary")),
            recommended_action=clean_text(operator_priority.get("recommended_action")),
        )

    for observation in safe_list(runtime.get("observations")):
        if not isinstance(observation, dict):
            continue
        raw_metadata = safe_dict(observation.get("raw_metadata"))
        operator_priority = safe_dict(raw_metadata.get("operator_review_priority"))
        operator_review = safe_dict(raw_metadata.get("comment_operator_review"))
        add(
            operator_priority,
            source_name=clean_text(observation.get("source_name")),
            url=clean_text(observation.get("url")),
            summary=clean_text(operator_priority.get("summary") or operator_review.get("summary")),
            recommended_action=clean_text(operator_priority.get("recommended_action")),
        )

    queue.sort(
        key=lambda item: (
            OPERATOR_REVIEW_PRIORITY_RANK.get(clean_text(item.get("priority_level")), 0),
            int(item.get("priority_score", 0) or 0),
            clean_text(item.get("title") or item.get("source_name") or item.get("url")),
        ),
        reverse=True,
    )
    return queue


def summarize_reddit_operator_review(source_result: dict[str, Any]) -> dict[str, Any]:
    runtime = extract_runtime_result(source_result)
    queue = collect_reddit_operator_review_queue(source_result, runtime)
    import_summary = safe_dict(source_result.get("import_summary")) or safe_dict(runtime.get("import_summary"))
    required_count = max(
        len(queue),
        int(import_summary.get("operator_review_required_count", 0) or 0),
    )
    high_priority_count = max(
        sum(1 for item in queue if clean_text(item.get("priority_level")) == "high"),
        int(import_summary.get("operator_review_high_priority_count", 0) or 0),
    )
    top_entry = safe_dict((queue or [{}])[0])
    required = required_count > 0
    priority_level = clean_text(top_entry.get("priority_level")) or ("high" if high_priority_count else "none")
    priority_score = int(top_entry.get("priority_score", 0) or 0)
    recommended_action = clean_text(top_entry.get("recommended_action"))
    if not recommended_action and required:
        recommended_action = (
            "Review the queued Reddit comment signals before promotion or publication, and keep them shadow-only unless stronger sources confirm the claim."
        )
    if not recommended_action:
        recommended_action = "No Reddit comment operator review action is required."
    if required:
        summary = (
            f"Reddit comment operator review is required for {required_count} item(s); "
            f"highest priority is {priority_level or 'unknown'}."
        )
    else:
        summary = "No Reddit comment operator review items were detected."
    gate = {
        "required": required,
        "status": "awaiting_reddit_operator_review" if required else "clear",
        "publication_readiness": "blocked_by_reddit_operator_review" if required else "ready",
        "priority_level": priority_level or "none",
        "priority_score": priority_score,
        "required_count": required_count,
        "high_priority_count": high_priority_count,
        "queue_size": len(queue),
        "summary": summary,
        "recommended_action": recommended_action,
        "next_step": recommended_action,
        "queue": deepcopy(queue[:5]),
        "shadow_signal_policy": "Reddit comments stay in shadow/community context and cannot confirm claims by themselves.",
    }
    return {
        "operator_review_required_count": required_count,
        "operator_review_high_priority_count": high_priority_count,
        "operator_review_queue": queue,
        "reddit_comment_review_gate": gate,
    }


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
    summary.update(summarize_reddit_operator_review(source_result))
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
        page_hints = resolve_observation_page_hints(observation)
        source_name = clean_text(observation.get("source_name")) or "Unknown source"
        excerpt = first_meaningful_text(
            observation.get("combined_summary")
            or observation.get("post_summary"),
            observation.get("media_summary"),
            observation.get("text_excerpt"),
            page_hints.get("text_excerpt"),
            observation.get("post_text_raw"),
            fallback=source_name,
        )
        title = first_meaningful_text(
            observation.get("post_summary")
            or observation.get("combined_summary"),
            observation.get("media_summary"),
            page_hints.get("post_summary"),
            observation.get("text_excerpt"),
            observation.get("post_text_raw"),
            fallback=source_name,
        )
        citations.append(
            {
                "citation_id": f"S{len(citations) + 1}",
                "source_id": clean_text(observation.get("source_id")),
                "source_name": source_name,
                "url": clean_text(observation.get("url")),
                "source_tier": int(observation.get("source_tier", 3)),
                "channel": clean_text(observation.get("channel")),
                "access_mode": clean_text(observation.get("access_mode")),
                "title": short_excerpt(title, limit=180),
                "published_at": clean_text(observation.get("published_at")),
                "observed_at": clean_text(observation.get("observed_at")),
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


def is_screenshot_role(role: Any) -> bool:
    clean_role = clean_text(role).lower()
    return bool(clean_role) and (clean_role == "screenshot" or clean_role.endswith("_screenshot") or "screenshot" in clean_role)


def screenshot_role_score(role: str) -> int:
    if role == "article_page_screenshot":
        return 30
    if role in {"page_screenshot", "title_screenshot", "observation_screenshot"}:
        return 28
    if role == "root_post_screenshot":
        return 24
    return 26


def resolve_observation_page_hints(observation: dict[str, Any]) -> dict[str, Any]:
    cached = safe_dict(observation.get("public_page_hints") or observation.get("page_hints"))
    if cached:
        return cached
    url = clean_text(observation.get("url"))
    access_mode = clean_text(observation.get("access_mode"))
    if access_mode == "blocked" or not url.startswith(("http://", "https://")):
        return {}
    try:
        return safe_dict(fetch_public_page_hints(url))
    except (TimeoutError, OSError, ValueError, urllib_error.URLError):
        return {}


def observation_visual_summary(observation: dict[str, Any], page_hints: dict[str, Any]) -> str:
    return clean_text(
        observation.get("media_summary")
        or observation.get("post_summary")
        or observation.get("combined_summary")
        or observation.get("text_excerpt")
        or observation.get("post_text_raw")
        or page_hints.get("media_summary")
        or page_hints.get("post_summary")
        or page_hints.get("text_excerpt")
    )


def post_screenshot_summary(record: dict[str, Any], page_hints: dict[str, Any] | None = None) -> str:
    hints = page_hints or {}
    return clean_text(
        record.get("post_summary")
        or record.get("post_text_raw")
        or record.get("combined_summary")
        or record.get("text_excerpt")
        or record.get("media_summary")
        or hints.get("post_summary")
        or hints.get("text_excerpt")
        or hints.get("media_summary")
    )


def post_media_summary(media: dict[str, Any], owner: dict[str, Any] | None = None) -> str:
    fallback = owner or {}
    summary = clean_text(
        media.get("ocr_summary")
        or media.get("ocr_text_raw")
        or media.get("summary")
        or media.get("caption")
        or meaningful_image_hint(media.get("alt_text"))
    )
    if summary:
        return summary
    if clean_text(media.get("capture_method")) == "dom_clip":
        return ""
    return clean_text(fallback.get("media_summary"))


def observation_artifact_manifest(observation: dict[str, Any], page_hints: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    direct_manifest = safe_list(observation.get("artifact_manifest"))
    if direct_manifest:
        return direct_manifest, "artifact_manifest"
    hinted_manifest = safe_list(page_hints.get("artifact_manifest"))
    if hinted_manifest:
        return hinted_manifest, "page_hints"
    return [], ""


def resolve_artifact_role(artifact: dict[str, Any], *, access_mode: str = "") -> str:
    explicit_role = clean_text(artifact.get("role"))
    if explicit_role:
        return explicit_role
    if clean_text(artifact.get("kind")).lower() == "screenshot":
        return "article_page_screenshot" if clean_text(access_mode) == "blocked" else "observation_screenshot"
    return "post_media"


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
        preferred_caption: str = "",
    ) -> None:
        clean_path, clean_url = normalize_image_reference(path, source_url)
        if not clean_path and not clean_url:
            return
        key = image_candidate_key(role, clean_path, clean_url)
        if key in seen:
            return
        seen.add(key)

        if request.get("image_strategy") == "screenshots_only" and not is_screenshot_role(role):
            return

        score = 0
        if role == "post_media":
            score += 40
        elif is_screenshot_role(role):
            score += screenshot_role_score(role)
        if role == "root_post_screenshot":
            score += 18
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
        elif clean_text(access_mode) == "public" and is_screenshot_role(role):
            score += 10
        if request.get("image_strategy") == "prefer_images":
            if role == "post_media":
                score += 10
            elif is_screenshot_role(role):
                score += 6
            else:
                score += 4
        if request.get("draft_mode") in {"image_first", "image_only"}:
            score += 10
            if role == "root_post_screenshot":
                score += 8
        if request.get("image_strategy") == "screenshots_only" and role == "root_post_screenshot":
            score += 8

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
                "preferred_caption": clean_text(preferred_caption),
                "score": score,
            }
        )

    for post in safe_list(source_result.get("x_posts")):
        if not isinstance(post, dict):
            continue
        source_name = f"X @{clean_text(post.get('author_handle') or post.get('author_display_name') or 'post')}"
        access_mode = clean_text(post.get("access_mode")) or "public"
        post_summary = post_screenshot_summary(post)
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
                post_media_summary(media, post),
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
                post_screenshot_summary(item),
                clean_text(item.get("access_mode")) or "public",
                "medium",
                int(item.get("source_tier", 3)),
            )
        for media in safe_list(item.get("media_items")):
            if not isinstance(media, dict):
                continue
            add(
                "post_media",
                clean_text(item.get("source_name")) or "Artifact source",
                clean_text(media.get("local_artifact_path")),
                clean_text(media.get("source_url")),
                post_media_summary(media, item),
                clean_text(item.get("access_mode")) or "public",
                clean_text(media.get("image_relevance_to_post")) or "high",
                int(item.get("source_tier", 3)),
                meaningful_image_hint(media.get("alt_text")),
                clean_text(media.get("capture_method")),
            )
        for artifact in safe_list(item.get("artifact_manifest")):
            if not isinstance(artifact, dict):
                continue
            artifact_role = resolve_artifact_role(artifact, access_mode=clean_text(item.get("access_mode")) or "public")
            artifact_caption = clean_text(artifact.get("caption") or artifact.get("summary"))
            add(
                artifact_role,
                clean_text(item.get("source_name")) or "Artifact source",
                clean_text(artifact.get("path")),
                clean_text(artifact.get("source_url")),
                artifact_caption or clean_text(item.get("media_summary") or item.get("post_summary") or item.get("combined_summary")),
                clean_text(item.get("access_mode")) or "public",
                "high" if artifact_role == "post_media" else "medium",
                int(item.get("source_tier", 3)),
                meaningful_image_hint(artifact_caption),
                "artifact_manifest",
                artifact_caption,
            )

    runtime = extract_runtime_result(source_result)
    for observation in safe_list(runtime.get("observations")):
        if not isinstance(observation, dict):
            continue
        source_name = clean_text(observation.get("source_name")) or "Observation source"
        access_mode = clean_text(observation.get("access_mode")) or "public"
        source_tier = int(observation.get("source_tier", 3))
        page_hints = resolve_observation_page_hints(observation)
        summary = observation_visual_summary(observation, page_hints)
        root_summary = post_screenshot_summary(observation, page_hints)

        root_post_screenshot_path = clean_text(observation.get("root_post_screenshot_path"))
        if root_post_screenshot_path:
            add(
                "root_post_screenshot",
                source_name,
                root_post_screenshot_path,
                "",
                root_summary,
                access_mode,
                "medium",
                source_tier,
                "",
                "observation_screenshot",
            )
        for media in safe_list(observation.get("media_items")):
            if not isinstance(media, dict):
                continue
            add(
                "post_media",
                source_name,
                clean_text(media.get("local_artifact_path")),
                clean_text(media.get("source_url")),
                post_media_summary(media, observation),
                access_mode,
                clean_text(media.get("image_relevance_to_post")) or "high",
                source_tier,
                meaningful_image_hint(media.get("alt_text")),
                clean_text(media.get("capture_method")),
            )

        artifact_manifest, capture_method = observation_artifact_manifest(observation, page_hints)
        for artifact in artifact_manifest:
            if not isinstance(artifact, dict):
                continue
            artifact_role = resolve_artifact_role(artifact, access_mode=access_mode)
            artifact_caption = clean_text(artifact.get("caption") or artifact.get("summary"))
            artifact_summary = artifact_caption or summary
            add(
                artifact_role,
                source_name,
                clean_text(artifact.get("path")),
                clean_text(artifact.get("source_url")),
                artifact_summary,
                access_mode,
                "high" if artifact_role == "post_media" else "medium",
                source_tier,
                meaningful_image_hint(artifact_caption),
                capture_method,
                artifact_caption,
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
    "collect_reddit_operator_review_queue",
    "citation_by_source_id",
    "clean_string_list",
    "clean_text",
    "extract_runtime_result",
    "safe_dict",
    "safe_list",
    "summarize_reddit_operator_review",
]
