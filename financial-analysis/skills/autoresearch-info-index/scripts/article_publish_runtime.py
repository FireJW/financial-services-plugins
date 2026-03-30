#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from article_workflow_runtime import run_article_workflow, write_json
from hot_topic_discovery_runtime import run_hot_topic_discovery
from news_index_runtime import clean_string_list, isoformat_or_blank, parse_datetime, safe_dict, safe_list, slugify
from runtime_paths import runtime_subdir
from wechat_draftbox_runtime import push_publish_package_to_wechat, resolve_human_review_gate


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_editor_anchor_mode(value: Any) -> str:
    mode = clean_text(value).lower().replace("-", "_")
    if mode in {"inline", "hidden"}:
        return mode
    return "hidden"


def parse_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    lowered = clean_text(value).lower()
    if lowered in {"1", "true", "yes", "y", "on", "approved"}:
        return True
    if lowered in {"0", "false", "no", "n", "off", "rejected"}:
        return False
    return default


def now_utc() -> datetime:
    return datetime.now(UTC)


def build_manual_review_state(
    request: dict[str, Any],
    *,
    review_gate: dict[str, Any] | None = None,
    approved_at: str = "",
) -> dict[str, Any]:
    gate = review_gate or resolve_human_review_gate(
        {
            "human_review_approved": request.get("human_review_approved"),
            "human_review_approved_by": request.get("human_review_approved_by"),
            "human_review_note": request.get("human_review_note"),
        }
    )
    approved = bool(gate.get("approved"))
    return {
        "required": True,
        "approved": approved,
        "status": "approved" if approved else "awaiting_human_review",
        "approved_by": clean_text(gate.get("approved_by")),
        "approved_at": approved_at or clean_text(gate.get("approved_at")) or (isoformat_or_blank(now_utc()) if approved else ""),
        "note": clean_text(gate.get("approval_note")),
        "next_step": clean_text(gate.get("next_step")),
    }


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    topic = clean_text(raw_payload.get("topic") or raw_payload.get("query"))
    topic_slug = slugify(topic, "hot-topic-auto") if topic else "hot-topic-auto"
    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else runtime_subdir("article-publish", topic_slug, analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    return {
        "analysis_time": analysis_time,
        "topic": topic,
        "output_dir": output_dir,
        "discovery_sources": clean_string_list(raw_payload.get("discovery_sources") or raw_payload.get("sources")),
        "manual_topic_candidates": [
            item
            for item in safe_list(raw_payload.get("manual_topic_candidates") or raw_payload.get("topics"))
            if isinstance(item, dict)
        ],
        "discovery_limit": max(1, int(raw_payload.get("discovery_limit", raw_payload.get("limit", 10)) or 10)),
        "discovery_top_n": max(1, int(raw_payload.get("discovery_top_n", raw_payload.get("top_n", 5)) or 5)),
        "selected_topic_index": max(1, int(raw_payload.get("selected_topic_index", 1) or 1)),
        "audience_keywords": clean_string_list(raw_payload.get("audience_keywords"))
        or ["投资", "商业", "产业", "AI", "科技", "公众号"],
        "preferred_topic_keywords": clean_string_list(
            raw_payload.get("preferred_topic_keywords")
            or raw_payload.get("topic_preferences")
            or raw_payload.get("preferred_keywords")
        ),
        "excluded_topic_keywords": clean_string_list(
            raw_payload.get("excluded_topic_keywords") or raw_payload.get("exclude_keywords")
        ),
        "topic_score_weights": raw_payload.get("topic_score_weights") or raw_payload.get("score_weights") or {},
        "min_total_score": max(0, int(raw_payload.get("min_total_score", 0) or 0)),
        "min_source_count": max(0, int(raw_payload.get("min_source_count", 0) or 0)),
        "title_hint": clean_text(raw_payload.get("title_hint")),
        "subtitle_hint": clean_text(raw_payload.get("subtitle_hint")),
        "angle": clean_text(raw_payload.get("angle")),
        "tone": clean_text(raw_payload.get("tone")) or "professional-calm",
        "target_length_chars": int(raw_payload.get("target_length_chars", raw_payload.get("target_length", 1600)) or 1600),
        "max_images": int(raw_payload.get("max_images", 3) or 3),
        "image_strategy": clean_text(raw_payload.get("image_strategy")) or "mixed",
        "draft_mode": clean_text(raw_payload.get("draft_mode")) or "balanced",
        "language_mode": clean_text(raw_payload.get("language_mode")) or "zh",
        "article_framework": clean_text(raw_payload.get("article_framework")) or "auto",
        "editor_anchor_mode": normalize_editor_anchor_mode(raw_payload.get("editor_anchor_mode")),
        "account_name": clean_text(raw_payload.get("account_name")),
        "author": clean_text(raw_payload.get("author")),
        "digest_max_chars": max(60, int(raw_payload.get("digest_max_chars", 120) or 120)),
        "need_open_comment": 1 if parse_bool(raw_payload.get("need_open_comment"), default=False) else 0,
        "only_fans_can_comment": 1 if parse_bool(raw_payload.get("only_fans_can_comment"), default=False) else 0,
        "max_parallel_sources": max(1, int(raw_payload.get("max_parallel_sources", 4) or 1)),
        "push_to_wechat": parse_bool(raw_payload.get("push_to_wechat"), default=False),
        "wechat_app_id": clean_text(raw_payload.get("wechat_app_id") or raw_payload.get("app_id")),
        "wechat_app_secret": clean_text(raw_payload.get("wechat_app_secret") or raw_payload.get("app_secret")),
        "allow_insecure_inline_credentials": parse_bool(raw_payload.get("allow_insecure_inline_credentials"), default=False),
        "cover_image_path": clean_text(raw_payload.get("cover_image_path")),
        "cover_image_url": clean_text(raw_payload.get("cover_image_url")),
        "show_cover_pic": int(raw_payload.get("show_cover_pic", 1) or 1),
        "timeout_seconds": max(5, int(raw_payload.get("timeout_seconds", 30) or 30)),
        "human_review_approved": parse_bool(raw_payload.get("human_review_approved"), default=False),
        "human_review_approved_by": clean_text(raw_payload.get("human_review_approved_by") or raw_payload.get("reviewed_by")),
        "human_review_note": clean_text(raw_payload.get("human_review_note") or raw_payload.get("review_note")),
    }


def resolve_discovery_request(request: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "limit": request["discovery_limit"],
        "top_n": request["discovery_top_n"],
        "audience_keywords": request["audience_keywords"],
        "preferred_topic_keywords": request["preferred_topic_keywords"],
        "excluded_topic_keywords": request["excluded_topic_keywords"],
        "topic_score_weights": request["topic_score_weights"],
        "min_total_score": request["min_total_score"],
        "min_source_count": request["min_source_count"],
        "manual_topic_candidates": request["manual_topic_candidates"],
        "max_parallel_sources": request["max_parallel_sources"],
    }
    if request["discovery_sources"]:
        payload["sources"] = request["discovery_sources"]
    if request["topic"]:
        payload["topic"] = request["topic"]
        payload["query"] = request["topic"]
    return payload


def select_topic_candidate(discovery_result: dict[str, Any], selected_topic_index: int) -> dict[str, Any]:
    ranked = safe_list(discovery_result.get("ranked_topics"))
    if not ranked:
        raise ValueError("No hot topics were discoverable. Provide topic manually or pass manual_topic_candidates.")
    bounded_index = max(1, min(selected_topic_index, len(ranked)))
    topic = deepcopy(safe_dict(ranked[bounded_index - 1]))
    topic["selected_rank"] = bounded_index
    return topic


def build_claims(selected_topic: dict[str, Any]) -> list[dict[str, str]]:
    title = clean_text(selected_topic.get("title")) or "当前热点"
    claim_open_text = f"围绕“{title}”目前仍有关键细节、影响路径或真假边界需要继续核实。"
    return [
        {
            "claim_id": "claim-core",
            "claim_text": f"“{title}”对应的是一个正在被多源讨论的真实事件、趋势或公开争议。",
        },
        {
            "claim_id": "claim-relevance",
            "claim_text": f"“{title}”对商业、投资或产业读者具有明确解释价值，不只是情绪型热度。",
        },
        {
            "claim_id": "claim-open",
            "claim_text": claim_open_text,
        },
    ]


def build_market_relevance(selected_topic: dict[str, Any]) -> list[str]:
    keywords = [keyword.lower() for keyword in clean_string_list(selected_topic.get("keywords"))]
    text = " ".join(keywords)
    rows = ["中文商业与投资读者对事件背景、真假边界和影响路径的解释需求"]
    if any(keyword in text for keyword in ["ai", "agent", "openai", "claude", "算力", "芯片", "半导体"]):
        rows.append("AI 与科技产业链估值、订单和叙事扩散的敏感度")
    if any(keyword in text for keyword in ["油", "天然气", "航运", "军工", "战争", "关税", "政策"]):
        rows.append("宏观政策、商品价格或风险偏好变化对相关板块的传导")
    if any(keyword in text for keyword in ["裁员", "融资", "ipo", "上市", "银行", "证券"]):
        rows.append("企业经营、资本市场和融资环境的读者关注度")
    return rows[:3]


def build_source_candidate_states(selected_topic: dict[str, Any], source_item: dict[str, Any]) -> dict[str, str]:
    score_breakdown = safe_dict(selected_topic.get("score_breakdown"))
    source_type = clean_text(source_item.get("source_type"))
    claim_states = {"claim-core": "support"}
    claim_states["claim-relevance"] = "support" if score_breakdown.get("relevance", 0) >= 45 or source_type != "social" else "unclear"
    claim_states["claim-open"] = "support" if score_breakdown.get("debate", 0) >= 50 or selected_topic.get("source_count", 0) >= 2 else "unclear"
    return claim_states


def build_news_request_from_topic(selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    analysis_time = request["analysis_time"]
    title = clean_text(selected_topic.get("title")) or request["topic"] or "hot-topic"
    summary = clean_text(selected_topic.get("summary")) or title
    source_candidates = []
    expected_source_families = []
    for index, source_item in enumerate(safe_list(selected_topic.get("source_items")), start=1):
        source_name = clean_text(source_item.get("source_name")) or f"source-{index:02d}"
        source_type = clean_text(source_item.get("source_type")) or "major_news"
        family = source_type
        if family not in expected_source_families:
            expected_source_families.append(family)
        source_candidates.append(
            {
                "source_id": f"{slugify(title, 'topic')}-{index:02d}",
                "source_name": source_name,
                "source_type": source_type,
                "published_at": clean_text(source_item.get("published_at")) or isoformat_or_blank(analysis_time),
                "observed_at": clean_text(source_item.get("observed_at")) or isoformat_or_blank(analysis_time),
                "url": clean_text(source_item.get("url")),
                "text_excerpt": clean_text(source_item.get("summary") or source_item.get("title") or summary),
                "claim_ids": ["claim-core", "claim-relevance", "claim-open"],
                "claim_states": build_source_candidate_states(selected_topic, source_item),
                "artifact_manifest": deepcopy(safe_list(source_item.get("artifact_manifest"))),
                "root_post_screenshot_path": clean_text(source_item.get("root_post_screenshot_path")),
                "media_items": deepcopy(safe_list(source_item.get("media_items"))),
                "post_summary": clean_text(source_item.get("post_summary")),
                "media_summary": clean_text(source_item.get("media_summary")),
            }
        )
    if not source_candidates:
        raise ValueError("Selected topic has no source_items, so it cannot be turned into a news-index request.")
    return {
        "topic": title,
        "analysis_time": isoformat_or_blank(analysis_time),
        "questions": [
            f"围绕“{title}”现在到底发生了什么，哪些事实已经被多源确认？",
            f"为什么这个话题会热起来，它对商业、产业或投资读者意味着什么？",
            "目前还有哪些关键事实未确认，文章里必须明确说清？",
        ],
        "use_case": "wechat-article-publishing",
        "source_preferences": ["public-first", "evidence-first"],
        "mode": "generic",
        "windows": ["1h", "6h", "24h"],
        "claims": build_claims(selected_topic),
        "candidates": source_candidates,
        "market_relevance": build_market_relevance(selected_topic),
        "expected_source_families": expected_source_families,
        "max_parallel_candidates": min(4, max(1, len(source_candidates))),
    }


def truncate_text(text: str, max_chars: int) -> str:
    stripped = clean_text(text)
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max(0, max_chars - 1)].rstrip() + "…"


def build_digest(article_package: dict[str, Any], max_chars: int) -> str:
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    source = " ".join(
        item
        for item in [
            clean_text(article_package.get("lede")),
            clean_text(safe_dict(sections[0] if sections else {}).get("paragraph")),
            clean_text(article_package.get("draft_thesis")),
        ]
        if item
    )
    return truncate_text(source, max_chars)


def extract_keywords(selected_topic: dict[str, Any], article_package: dict[str, Any]) -> list[str]:
    keywords = clean_string_list(selected_topic.get("keywords"))
    title = clean_text(article_package.get("title"))
    for token in title.replace("：", " ").replace(":", " ").split():
        token = token.strip()
        if len(token) >= 2 and token not in keywords:
            keywords.append(token)
    thesis = clean_text(article_package.get("draft_thesis"))
    for token in thesis.replace("，", " ").replace(",", " ").split():
        token = token.strip()
        if len(token) >= 2 and token not in keywords:
            keywords.append(token)
    return keywords[:8]


def build_editor_anchors(section_count: int) -> list[dict[str, str]]:
    anchors = [{"placement": "after_lede", "text": "这里补一个你自己的判断升级条件，或者一句反直觉结论。"}]
    if section_count >= 2:
        anchors.append({"placement": "after_section_2", "text": "这里加入你亲身见过的案例、行业对话或一次踩坑经历。"})
    if section_count >= 4:
        anchors.append({"placement": "after_section_4", "text": "这里补一个只属于你自己的结论收口，不要只重复公开信息。"})
    return anchors


def paragraph_blocks(text: str) -> list[str]:
    parts = [clean_text(part) for part in str(text or "").split("\n") if clean_text(part)]
    return parts or [clean_text(text)]


def build_image_plan(selected_images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for index, item in enumerate(selected_images, start=1):
        asset_id = clean_text(item.get("asset_id") or item.get("image_id") or f"image-{index:02d}")
        source_url = clean_text(item.get("source_url"))
        local_path = clean_text(item.get("path") or item.get("local_artifact_path"))
        preview_src = source_url if source_url.startswith("http") else ""
        if not preview_src and local_path:
            local_file = Path(local_path).expanduser()
            preview_src = local_file.resolve().as_uri() if local_file.exists() else local_path
        upload_token = f"{{{{WECHAT_IMAGE_{asset_id}}}}}"
        plan.append(
            {
                "asset_id": asset_id,
                "placement": clean_text(item.get("placement")) or "appendix",
                "caption": clean_text(item.get("caption")),
                "source_name": clean_text(item.get("source_name")),
                "local_path": local_path,
                "source_url": source_url,
                "render_src": preview_src or upload_token,
                "upload_token": upload_token,
                "upload_required": bool(source_url or local_path),
                "status": clean_text(item.get("status")),
            }
        )
    return plan


def cover_score_base(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def resolve_render_src(local_path: Any, source_url: Any, render_src: Any = "") -> str:
    resolved_render_src = clean_text(render_src)
    if resolved_render_src:
        return resolved_render_src
    resolved_source_url = clean_text(source_url)
    if resolved_source_url.startswith(("http://", "https://")):
        return resolved_source_url
    resolved_local_path = clean_text(local_path)
    if not resolved_local_path:
        return ""
    local_file = Path(resolved_local_path).expanduser()
    return local_file.resolve().as_uri() if local_file.exists() else resolved_local_path


def normalize_cover_candidate(
    raw_item: dict[str, Any],
    *,
    selected_for_body: bool,
    body_order: int,
    source_kind: str,
) -> dict[str, Any]:
    asset_id = clean_text(raw_item.get("asset_id") or raw_item.get("image_id"))
    local_path = clean_text(raw_item.get("local_path") or raw_item.get("path") or raw_item.get("local_artifact_path"))
    source_url = clean_text(raw_item.get("source_url"))
    render_src = resolve_render_src(local_path, source_url, raw_item.get("render_src"))
    caption = clean_text(raw_item.get("caption") or raw_item.get("summary") or raw_item.get("alt_text"))
    status = clean_text(raw_item.get("status"))
    if not status:
        local_exists = bool(local_path) and Path(local_path).expanduser().exists()
        if local_exists:
            status = "local_ready"
        elif source_url.startswith(("http://", "https://")):
            status = "remote_only"
    return {
        "asset_id": asset_id,
        "local_path": local_path,
        "source_url": source_url,
        "render_src": render_src,
        "caption": caption,
        "summary": clean_text(raw_item.get("summary") or raw_item.get("caption")),
        "source_name": clean_text(raw_item.get("source_name")),
        "status": status,
        "role": clean_text(raw_item.get("role")),
        "access_mode": clean_text(raw_item.get("access_mode")),
        "capture_method": clean_text(raw_item.get("capture_method")),
        "placement": clean_text(raw_item.get("placement")),
        "upload_required": bool(raw_item.get("upload_required")) or bool(local_path or source_url),
        "selected_for_body": selected_for_body,
        "body_order": body_order,
        "source_kind": clean_text(source_kind),
        "cover_score_base": cover_score_base(raw_item.get("score")),
    }


def cover_candidate_key(candidate: dict[str, Any]) -> tuple[str, ...]:
    asset_id = clean_text(candidate.get("asset_id"))
    if asset_id:
        return ("asset_id", asset_id)
    local_path = clean_text(candidate.get("local_path"))
    if local_path:
        return ("local_path", local_path)
    source_url = clean_text(candidate.get("source_url"))
    if source_url:
        return ("source_url", source_url)
    render_src = clean_text(candidate.get("render_src"))
    if render_src:
        return ("render_src", render_src)
    return (
        "fallback",
        clean_text(candidate.get("source_name")),
        clean_text(candidate.get("role")),
        clean_text(candidate.get("caption")),
    )


def merge_cover_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in (
        "asset_id",
        "local_path",
        "source_url",
        "render_src",
        "caption",
        "summary",
        "source_name",
        "status",
        "role",
        "access_mode",
        "capture_method",
        "placement",
    ):
        if not clean_text(merged.get(key)) and clean_text(incoming.get(key)):
            merged[key] = incoming.get(key)
    merged["upload_required"] = bool(merged.get("upload_required")) or bool(incoming.get("upload_required"))
    merged["selected_for_body"] = bool(merged.get("selected_for_body")) or bool(incoming.get("selected_for_body"))
    merged["body_order"] = min(int(merged.get("body_order", 9999) or 9999), int(incoming.get("body_order", 9999) or 9999))
    merged["cover_score_base"] = max(
        cover_score_base(merged.get("cover_score_base")),
        cover_score_base(incoming.get("cover_score_base")),
    )
    if clean_text(incoming.get("source_kind")) == "selected_body_image":
        merged["source_kind"] = "selected_body_image"
    elif not clean_text(merged.get("source_kind")):
        merged["source_kind"] = clean_text(incoming.get("source_kind"))
    return merged


def score_cover_candidate(candidate: dict[str, Any]) -> int:
    score = cover_score_base(candidate.get("cover_score_base"))
    if has_usable_upload_source(candidate):
        score += 50
    else:
        score -= 200

    role = clean_text(candidate.get("role"))
    if role == "post_media":
        score += 70
    elif role == "root_post_screenshot":
        score -= 12
    elif role:
        score += 10

    status = clean_text(candidate.get("status"))
    if status == "local_ready":
        score += 18
    elif clean_text(candidate.get("source_url")).startswith(("http://", "https://")):
        score += 8

    if clean_text(candidate.get("caption")):
        score += 8
    if clean_text(candidate.get("source_name")):
        score += 4
    if clean_text(candidate.get("access_mode")) == "blocked":
        score -= 16
    if clean_text(candidate.get("capture_method")) == "dom_clip":
        score -= 3
    if bool(candidate.get("selected_for_body")):
        score += 4
    if clean_text(candidate.get("placement")) == "after_lede":
        score += 2
    return score


def cover_candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    body_order = int(candidate.get("body_order", 9999) or 9999)
    return (
        int(candidate.get("cover_score", 0) or 0),
        1 if clean_text(candidate.get("role")) == "post_media" else 0,
        1 if clean_text(candidate.get("status")) == "local_ready" else 0,
        -body_order,
    )


def build_cover_candidates(
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged_candidates: dict[tuple[str, ...], dict[str, Any]] = {}
    selected_body_order = {
        clean_text(item.get("asset_id")): index
        for index, item in enumerate(image_plan)
        if clean_text(item.get("asset_id"))
    }

    for item in draft_image_candidates:
        if not isinstance(item, dict):
            continue
        asset_id = clean_text(item.get("image_id") or item.get("asset_id"))
        candidate = normalize_cover_candidate(
            item,
            selected_for_body=asset_id in selected_body_order,
            body_order=selected_body_order.get(asset_id, 9999),
            source_kind="draft_image_candidate",
        )
        if not any(clean_text(candidate.get(field)) for field in ("asset_id", "local_path", "source_url", "render_src")):
            continue
        key = cover_candidate_key(candidate)
        merged_candidates[key] = merge_cover_candidate(merged_candidates.get(key, {}), candidate) if key in merged_candidates else candidate

    for index, item in enumerate(image_plan):
        candidate = normalize_cover_candidate(
            item,
            selected_for_body=True,
            body_order=index,
            source_kind="selected_body_image",
        )
        key = cover_candidate_key(candidate)
        merged_candidates[key] = merge_cover_candidate(merged_candidates.get(key, {}), candidate) if key in merged_candidates else candidate

    candidates = list(merged_candidates.values())
    for candidate in candidates:
        candidate["cover_score"] = score_cover_candidate(candidate)
        candidate["upload_ready"] = has_usable_upload_source(candidate)
    candidates.sort(key=cover_candidate_sort_key, reverse=True)
    return candidates


def reduce_cover_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": clean_text(candidate.get("asset_id")),
        "role": clean_text(candidate.get("role")),
        "source_kind": clean_text(candidate.get("source_kind")),
        "selected_for_body": bool(candidate.get("selected_for_body")),
        "body_order": int(candidate.get("body_order", 9999) or 9999),
        "cover_score": int(candidate.get("cover_score", 0) or 0),
        "upload_ready": bool(candidate.get("upload_ready")),
        "caption": clean_text(candidate.get("caption")),
        "source_name": clean_text(candidate.get("source_name")),
        "status": clean_text(candidate.get("status")),
        "local_path": clean_text(candidate.get("local_path")),
        "source_url": clean_text(candidate.get("source_url")),
        "render_src": clean_text(candidate.get("render_src")),
    }


def select_cover_candidate(
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, str, list[dict[str, Any]]]:
    cover_candidates = build_cover_candidates(image_plan, draft_image_candidates)
    dedicated_cover_candidates = [
        item
        for item in cover_candidates
        if not bool(item.get("selected_for_body")) and bool(item.get("upload_ready"))
    ]
    if dedicated_cover_candidates:
        selected_cover = safe_dict(dedicated_cover_candidates[0])
        selection_mode = "dedicated_candidate"
        selection_reason = (
            f"Selected dedicated cover candidate {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
            f"from draft image discovery with score {int(selected_cover.get('cover_score', 0) or 0)}."
        )
        return selected_cover, selection_mode, selection_reason, cover_candidates

    body_cover_candidates = sorted(
        [item for item in cover_candidates if bool(item.get("selected_for_body")) and bool(item.get("upload_ready"))],
        key=lambda item: int(item.get("body_order", 9999) or 9999),
    )
    if body_cover_candidates:
        selected_cover = safe_dict(body_cover_candidates[0])
        selection_mode = "body_image_fallback"
        selection_reason = (
            f"Falling back to body image {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
            "because no dedicated cover candidate was ready."
        )
        return selected_cover, selection_mode, selection_reason, cover_candidates

    return (
        {},
        "manual_required",
        "No usable cover candidate is ready yet. Provide cover_image_path or cover_image_url.",
        cover_candidates,
    )


def render_anchor_html(anchor_text: str) -> str:
    return (
        "<section style=\"margin:20px 0;padding:12px 14px;border-left:4px solid #e3a008;"
        "background:#fff8e7;border-radius:6px;\">"
        f"<p style=\"margin:0;color:#8a5a00;font-size:14px;line-height:1.7;\">"
        f"✏️ 编辑锚点：{escape(anchor_text)}</p></section>"
    )


def render_image_html(image_item: dict[str, Any]) -> str:
    src = clean_text(image_item.get("render_src"))
    caption = clean_text(image_item.get("caption"))
    return (
        "<section style=\"margin:18px 0;text-align:center;\">"
        f"<img src=\"{escape(src)}\" alt=\"{escape(caption or 'image')}\" "
        "style=\"max-width:100%;border-radius:8px;display:block;margin:0 auto;\" />"
        f"{f'<p style=\"margin:8px 0 0;color:#666;font-size:13px;line-height:1.6;\">{escape(caption)}</p>' if caption else ''}"
        "</section>"
    )


def render_wechat_html(
    article_package: dict[str, Any],
    image_plan: list[dict[str, Any]],
    anchors: list[dict[str, str]],
    *,
    editor_anchor_mode: str = "hidden",
) -> str:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    lede = clean_text(article_package.get("lede"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    citations = safe_list(article_package.get("citations"))
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in image_plan:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)
    anchors_by_placement: dict[str, list[dict[str, str]]] = {}
    for item in anchors:
        anchors_by_placement.setdefault(clean_text(item.get("placement")), []).append(item)

    html_parts = [
        "<article style=\"font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#1f2329;"
        "font-size:16px;line-height:1.9;\">",
        "<section style=\"margin-bottom:22px;\">",
        f"<h1 style=\"font-size:28px;line-height:1.35;margin:0 0 12px;color:#111827;\">{escape(title)}</h1>",
    ]
    if subtitle:
        html_parts.append(
            f"<p style=\"margin:0 0 14px;color:#4b5563;font-size:15px;line-height:1.8;\">{escape(subtitle)}</p>"
        )
    if lede:
        html_parts.append(
            "<blockquote style=\"margin:0;padding:14px 16px;border-left:4px solid #0f766e;"
            "background:#f0fdfa;border-radius:6px;color:#134e4a;\">"
            f"{escape(lede)}</blockquote>"
        )
    html_parts.append("</section>")

    for item in images_by_placement.get("after_lede", []):
        html_parts.append(render_image_html(item))
    if editor_anchor_mode == "inline":
        for item in anchors_by_placement.get("after_lede", []):
            html_parts.append(render_anchor_html(item.get("text", "")))

    for index, section in enumerate(sections, start=1):
        heading = clean_text(section.get("heading")) or f"部分 {index}"
        html_parts.append("<section style=\"margin:18px 0;\">")
        html_parts.append(
            f"<h2 style=\"font-size:22px;line-height:1.45;margin:0 0 10px;color:#111827;\">{escape(heading)}</h2>"
        )
        for paragraph in paragraph_blocks(section.get("paragraph")):
            html_parts.append(f"<p style=\"margin:0 0 14px;\">{escape(paragraph)}</p>")
        html_parts.append("</section>")
        for item in images_by_placement.get(f"after_section_{index}", []):
            html_parts.append(render_image_html(item))
        if editor_anchor_mode == "inline":
            for item in anchors_by_placement.get(f"after_section_{index}", []):
                html_parts.append(render_anchor_html(item.get("text", "")))

    for item in images_by_placement.get("appendix", []):
        html_parts.append(render_image_html(item))

    if citations:
        html_parts.append("<section style=\"margin-top:28px;\">")
        html_parts.append("<h2 style=\"font-size:20px;line-height:1.45;margin:0 0 10px;color:#111827;\">来源</h2>")
        html_parts.append("<ol style=\"padding-left:20px;margin:0;\">")
        for citation in citations:
            source_name = clean_text(citation.get("source_name"))
            url = clean_text(citation.get("url"))
            html_parts.append(
                "<li style=\"margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.8;\">"
                f"{escape(source_name or citation.get('citation_id', 'source'))}"
                f"{f'：<a href=\"{escape(url)}\" style=\"color:#0f766e;text-decoration:none;\">{escape(url)}</a>' if url else ''}"
                "</li>"
            )
        html_parts.append("</ol></section>")
    html_parts.append("</article>")
    return "\n".join(html_parts) + "\n"


def build_cover_plan(
    selected_topic: dict[str, Any],
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
    keywords: list[str],
) -> dict[str, Any]:
    primary_image, selection_mode, selection_reason, cover_candidates = select_cover_candidate(
        image_plan,
        draft_image_candidates,
    )
    title = clean_text(selected_topic.get("title"))
    prompt = (
        f"Create a 16:9 WeChat article cover for: {title}. "
        f"Keywords: {', '.join(keywords[:5]) or title}. "
        "Style: calm editorial illustration, clean composition, realistic lighting, premium but restrained. "
        "Prefer a text-free cover. No Chinese text, no logo, no watermark, no UI chrome. "
        "If text is unavoidable, use short clear English only."
    )
    return {
        "primary_image_asset_id": clean_text(primary_image.get("asset_id")),
        "primary_image_render_src": clean_text(primary_image.get("render_src")),
        "primary_image_upload_required": bool(primary_image.get("upload_required")),
        "selected_cover_asset_id": clean_text(primary_image.get("asset_id")),
        "selected_cover_role": clean_text(primary_image.get("role")),
        "selected_cover_caption": clean_text(primary_image.get("caption")),
        "selected_cover_source_name": clean_text(primary_image.get("source_name")),
        "selected_cover_local_path": clean_text(primary_image.get("local_path")),
        "selected_cover_source_url": clean_text(primary_image.get("source_url")),
        "selected_cover_render_src": clean_text(primary_image.get("render_src")),
        "selected_cover_upload_required": bool(primary_image.get("upload_required")),
        "selection_mode": selection_mode,
        "cover_selection_reason": selection_reason,
        "cover_candidates": [reduce_cover_candidate(item) for item in cover_candidates[:6]],
        "needs_thumb_media_id": True,
        "cover_prompt": prompt,
        "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
    }


def has_usable_upload_source(asset: dict[str, Any]) -> bool:
    local_path = clean_text(asset.get("local_path"))
    if local_path and Path(local_path).expanduser().exists():
        return True
    remote_url = clean_text(asset.get("source_url")) or clean_text(asset.get("render_src"))
    return remote_url.startswith(("http://", "https://"))


def resolve_cover_asset_from_plan(cover_plan: dict[str, Any], image_plan: list[dict[str, Any]]) -> dict[str, Any]:
    selected_cover_asset_id = clean_text(cover_plan.get("selected_cover_asset_id") or cover_plan.get("primary_image_asset_id"))
    for item in image_plan:
        if selected_cover_asset_id and clean_text(item.get("asset_id")) != selected_cover_asset_id:
            continue
        merged_item = dict(item)
        for field, cover_field in (
            ("local_path", "selected_cover_local_path"),
            ("source_url", "selected_cover_source_url"),
            ("render_src", "selected_cover_render_src"),
        ):
            if not clean_text(merged_item.get(field)) and clean_text(cover_plan.get(cover_field)):
                merged_item[field] = clean_text(cover_plan.get(cover_field))
        if selected_cover_asset_id and not clean_text(merged_item.get("asset_id")):
            merged_item["asset_id"] = selected_cover_asset_id
        return merged_item

    local_path = clean_text(cover_plan.get("selected_cover_local_path"))
    source_url = clean_text(cover_plan.get("selected_cover_source_url"))
    render_src = clean_text(cover_plan.get("selected_cover_render_src")) or resolve_render_src(local_path, source_url)
    if local_path or source_url or render_src:
        return {
            "asset_id": selected_cover_asset_id,
            "local_path": local_path,
            "source_url": source_url,
            "render_src": render_src,
            "upload_required": bool(local_path or source_url),
        }
    return {}


def build_push_readiness(
    request: dict[str, Any],
    html: str,
    draft_payload: dict[str, Any],
    image_plan: list[dict[str, Any]],
    cover_plan: dict[str, Any],
) -> dict[str, Any]:
    has_content_html = bool(clean_text(html))
    has_draft_payload_template = bool(safe_list(draft_payload.get("articles")))
    missing_render_asset_ids = [
        clean_text(item.get("asset_id")) or f"asset-{index:02d}"
        for index, item in enumerate(image_plan, start=1)
        if not clean_text(item.get("render_src"))
    ]
    missing_upload_source_asset_ids = [
        clean_text(item.get("asset_id")) or f"asset-{index:02d}"
        for index, item in enumerate(image_plan, start=1)
        if bool(item.get("upload_required")) and not has_usable_upload_source(item)
    ]
    inline_upload_required_count = sum(1 for item in image_plan if bool(item.get("upload_required")))

    explicit_cover_path = clean_text(request.get("cover_image_path"))
    explicit_cover_url = clean_text(request.get("cover_image_url"))
    explicit_cover_path_exists = Path(explicit_cover_path).expanduser().exists() if explicit_cover_path else False
    explicit_cover_url_valid = explicit_cover_url.startswith(("http://", "https://"))
    explicit_cover_ready = explicit_cover_path_exists or explicit_cover_url_valid
    primary_cover_asset = resolve_cover_asset_from_plan(cover_plan, image_plan)
    primary_cover_asset_ready = bool(primary_cover_asset) and has_usable_upload_source(primary_cover_asset)
    selection_mode = clean_text(cover_plan.get("selection_mode"))

    cover_source = "missing"
    if explicit_cover_ready:
        cover_source = "request_override"
    elif primary_cover_asset_ready:
        cover_source = "dedicated_cover_candidate" if selection_mode == "dedicated_candidate" else "article_image"

    has_cover_reference = cover_source != "missing"
    if not has_content_html or not has_draft_payload_template:
        status = "missing_content"
    elif not has_cover_reference:
        status = "missing_cover_image"
    elif missing_render_asset_ids:
        status = "missing_inline_preview"
    elif missing_upload_source_asset_ids:
        status = "missing_upload_source"
    else:
        status = "ready_for_api_push"

    if status == "missing_content":
        next_step = "Rebuild the publish package so content_html and draftbox_payload_template are both present."
    elif status == "missing_cover_image":
        next_step = (
            "Provide cover_image_path/cover_image_url, or keep at least one dedicated cover candidate or body image "
            "with a usable local file or remote URL."
        )
    elif status == "missing_inline_preview":
        next_step = "Rebuild the publish package so every upload_required image has a renderable preview source."
    elif status == "missing_upload_source":
        next_step = "Restore the missing local image files or provide remote source_url values before pushing to WeChat."
    else:
        next_step = "Set WECHAT_APP_ID/WECHAT_APP_SECRET or create .env.wechat.local, then run run_wechat_push_draft.cmd after cover and review are ready."

    return {
        "status": status,
        "ready_for_api_push": status == "ready_for_api_push",
        "has_content_html": has_content_html,
        "has_draft_payload_template": has_draft_payload_template,
        "has_cover_reference": has_cover_reference,
        "cover_source": cover_source,
        "cover_asset_id": clean_text(primary_cover_asset.get("asset_id") or cover_plan.get("selected_cover_asset_id")),
        "cover_selection_mode": selection_mode,
        "inline_asset_count": len(image_plan),
        "inline_upload_required_count": inline_upload_required_count,
        "missing_render_asset_ids": missing_render_asset_ids,
        "missing_upload_source_asset_ids": missing_upload_source_asset_ids,
        "credentials_required": True,
        "supported_request_fields": ["allow_insecure_inline_credentials", "wechat_app_id", "wechat_app_secret"],
        "supported_env_vars": ["WECHAT_APP_ID", "WECHAT_APP_SECRET"],
        "supported_local_secret_files": [".env.wechat.local"],
        "inline_credentials_blocked_by_default": True,
        "next_step": next_step,
    }


def build_publish_package(
    workflow_result: dict[str, Any],
    selected_topic: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    request = {
        "editor_anchor_mode": "hidden",
        "article_framework": "auto",
        **request,
    }
    request["editor_anchor_mode"] = normalize_editor_anchor_mode(request.get("editor_anchor_mode"))
    review_result = safe_dict(workflow_result.get("review_result"))
    article_package = safe_dict(review_result.get("article_package")) or safe_dict(safe_dict(workflow_result.get("draft_result")).get("article_package"))
    selected_images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    draft_context = safe_dict(safe_dict(workflow_result.get("draft_result")).get("draft_context"))
    draft_image_candidates = safe_list(draft_context.get("image_candidates"))
    image_plan = build_image_plan(selected_images)
    keywords = extract_keywords(selected_topic, article_package)
    anchors = build_editor_anchors(len(safe_list(article_package.get("sections") or article_package.get("body_sections"))))
    digest = build_digest(article_package, request["digest_max_chars"])
    html = render_wechat_html(
        article_package,
        image_plan,
        anchors,
        editor_anchor_mode=request["editor_anchor_mode"],
    )
    cover_plan = build_cover_plan(selected_topic, image_plan, draft_image_candidates, keywords)
    content_ready = all(clean_text(item.get("render_src")) for item in image_plan)
    push_ready = False
    title = clean_text(article_package.get("title"))
    draft_payload = {
        "articles": [
            {
                "title": title,
                "author": request["author"],
                "digest": digest,
                "content": html,
                "content_source_url": "",
                "thumb_media_id": cover_plan["thumb_media_id_placeholder"],
                "need_open_comment": request["need_open_comment"],
                "only_fans_can_comment": request["only_fans_can_comment"],
            }
        ]
    }
    push_readiness = build_push_readiness(request, html, draft_payload, image_plan, cover_plan)
    push_ready = bool(push_readiness.get("ready_for_api_push"))
    return {
        "contract_version": "wechat-draft-package/v1",
        "account_name": request["account_name"],
        "author": request["author"],
        "title": title,
        "subtitle": clean_text(article_package.get("subtitle")),
        "digest": digest,
        "keywords": keywords,
        "content_markdown": article_package.get("article_markdown", ""),
        "content_html": html,
        "article_framework": clean_text(article_package.get("article_framework") or request.get("article_framework")),
        "editor_anchor_mode": request["editor_anchor_mode"],
        "editor_anchor_visibility": "visible_inline" if request["editor_anchor_mode"] == "inline" else "review_only",
        "editor_anchors": anchors,
        "image_assets": image_plan,
        "cover_plan": cover_plan,
        "content_ready": content_ready,
        "push_ready": push_ready,
        "push_readiness": push_readiness,
        "draftbox_payload_template": draft_payload,
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    selected_topic = safe_dict(result.get("selected_topic"))
    publish_package = safe_dict(result.get("publish_package"))
    push_readiness = safe_dict(publish_package.get("push_readiness"))
    manual_review = safe_dict(result.get("manual_review") or result.get("review_gate"))
    push_stage = safe_dict(result.get("push_stage"))
    lines = [
        "# Article Publish Workflow",
        "",
        f"- Status: {result.get('status', '')}",
        f"- Analysis time: {result.get('analysis_time', '')}",
        f"- Selected topic: {selected_topic.get('title', '')}",
        f"- Selected rank: {selected_topic.get('selected_rank', 0)}",
        f"- Topic score: {safe_dict(selected_topic.get('score_breakdown')).get('total_score', 0)}",
        f"- Workflow report: {safe_dict(result.get('workflow_stage')).get('report_path', '')}",
        "",
        "## Human Review Gate",
        "",
        f"- Review required: {'yes' if manual_review.get('required', True) else 'no'}",
        f"- Review approved: {'yes' if manual_review.get('approved') else 'no'}",
        f"- Gate outcome: {manual_review.get('status', 'unknown')}",
        f"- Approved by: {manual_review.get('approved_by', '') or 'none'}",
        f"- Approved at: {manual_review.get('approved_at', '') or 'none'}",
        f"- Approval note: {manual_review.get('note', '') or 'none'}",
        f"- Next action: {manual_review.get('next_step', '') or 'none'}",
        "",
        "## Publish Readiness",
        "",
        f"- Content ready: {'yes' if publish_package.get('content_ready') else 'no'}",
        f"- Package push-ready: {'yes' if publish_package.get('push_ready') else 'no'}",
        f"- Push readiness status: {push_readiness.get('status', 'unknown')}",
        f"- Cover available: {'yes' if push_readiness.get('has_cover_reference') else 'no'}",
        f"- Cover selection mode: {safe_dict(publish_package.get('cover_plan')).get('selection_mode', '') or 'unknown'}",
        f"- Cover asset: {safe_dict(publish_package.get('cover_plan')).get('selected_cover_asset_id', '') or 'none'}",
        f"- Inline assets needing upload: {push_readiness.get('inline_upload_required_count', 0)}",
        f"- Missing inline previews: {', '.join(push_readiness.get('missing_render_asset_ids', [])) or 'none'}",
        f"- Draft title: {publish_package.get('title', '')}",
        f"- Digest: {publish_package.get('digest', '')}",
        f"- Keywords: {', '.join(publish_package.get('keywords', [])) or 'none'}",
        f"- Next push step: {result.get('next_push_command', '') or 'none'}",
        "",
        "## Files",
        "",
        f"- Discovery result: {safe_dict(result.get('discovery_stage')).get('result_path', '')}",
        f"- Selected topic: {result.get('selected_topic_path', '')}",
        f"- News request: {result.get('news_request_path', '')}",
        f"- Workflow result: {safe_dict(result.get('workflow_stage')).get('result_path', '')}",
        f"- Publish package: {result.get('publish_package_path', '')}",
        f"- WeChat HTML: {result.get('wechat_html_path', '')}",
        "",
        "## Images",
    ]
    for item in safe_list(publish_package.get("image_assets")):
        lines.append(
            f"- {item.get('asset_id', '')} | placement={item.get('placement', '')} | "
            f"upload_required={'yes' if item.get('upload_required') else 'no'} | src={item.get('render_src', '') or 'none'}"
        )
    if not safe_list(publish_package.get("image_assets")):
        lines.append("- none")
    if push_stage:
        lines.extend(
            [
                "",
                "## WeChat Push",
                "",
                f"- Requested: {'yes' if push_stage.get('requested') else 'no'}",
                f"- Attempted: {'yes' if push_stage.get('attempted') else 'no'}",
                f"- Outcome: {push_stage.get('status', 'not_requested')}",
                f"- Review gate status: {push_stage.get('review_gate_status', '') or 'none'}",
                f"- Push readiness status: {push_stage.get('push_readiness_status', '') or 'none'}",
                f"- Blocked reason: {push_stage.get('blocked_reason', '') or 'none'}",
                f"- Result path: {push_stage.get('result_path', '') or 'none'}",
                f"- Draft media_id: {push_stage.get('draft_media_id', '') or 'none'}",
                f"- Inline uploads: {push_stage.get('inline_image_count', 0)}",
                f"- Cover media_id: {push_stage.get('cover_media_id', '') or 'none'}",
                f"- Error: {push_stage.get('error_message', '') or 'none'}",
                f"- Next step: {push_stage.get('next_step', '') or 'none'}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_article_publish(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    discovery_result = run_hot_topic_discovery(resolve_discovery_request(request))
    selected_topic = select_topic_candidate(discovery_result, request["selected_topic_index"])
    news_request = build_news_request_from_topic(selected_topic, request)

    workflow_output_dir = request["output_dir"] / "workflow"
    workflow_payload = {
        **news_request,
        "output_dir": str(workflow_output_dir),
        "title_hint": request["title_hint"],
        "subtitle_hint": request["subtitle_hint"],
        "angle": request["angle"],
        "tone": request["tone"],
        "target_length_chars": request["target_length_chars"],
        "max_images": request["max_images"],
        "image_strategy": request["image_strategy"],
        "draft_mode": request["draft_mode"],
        "language_mode": request["language_mode"],
        "article_framework": request["article_framework"],
    }
    workflow_result = run_article_workflow(workflow_payload)
    publish_package = build_publish_package(workflow_result, selected_topic, request)

    discovery_result_path = request["output_dir"] / "topic-discovery-result.json"
    selected_topic_path = request["output_dir"] / "selected-topic.json"
    news_request_path = request["output_dir"] / "news-request.json"
    workflow_result_path = request["output_dir"] / "workflow-result.json"
    publish_package_path = request["output_dir"] / "publish-package.json"
    wechat_html_path = request["output_dir"] / "wechat-draft.html"
    wechat_push_result_path = request["output_dir"] / "wechat-push-result.json"

    write_json(discovery_result_path, discovery_result)
    write_json(selected_topic_path, selected_topic)
    write_json(news_request_path, news_request)
    write_json(workflow_result_path, workflow_result)
    write_json(publish_package_path, publish_package)
    wechat_html_path.write_text(publish_package.get("content_html", ""), encoding="utf-8-sig")

    review_gate = resolve_human_review_gate(
        {
            "human_review_approved": request["human_review_approved"],
            "human_review_approved_by": request["human_review_approved_by"],
            "human_review_note": request["human_review_note"],
        }
    )
    manual_review = build_manual_review_state(request, review_gate=review_gate)
    push_readiness = safe_dict(publish_package.get("push_readiness"))
    push_stage = {
        "requested": request["push_to_wechat"],
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate.get("status", "unknown"),
        "push_readiness_status": push_readiness.get("status", "unknown"),
        "blocked_reason": "",
        "result_path": "",
        "draft_media_id": "",
        "cover_media_id": "",
        "inline_image_count": 0,
        "error_message": "",
        "next_step": "",
    }
    overall_status = "ok"
    if request["push_to_wechat"]:
        if not review_gate.get("approved"):
            overall_status = "blocked_review_gate"
            push_stage = {
                **push_stage,
                "requested": True,
                "attempted": False,
                "status": "blocked_review_gate",
                "blocked_reason": "human_review_not_approved",
                "next_step": review_gate.get("next_step", ""),
            }
        elif not publish_package.get("push_ready"):
            overall_status = "blocked_push_readiness"
            push_stage = {
                **push_stage,
                "requested": True,
                "attempted": False,
                "status": "blocked_push_readiness",
                "blocked_reason": f"push_not_ready:{clean_text(push_readiness.get('status')) or 'unknown'}",
                "next_step": clean_text(push_readiness.get("next_step")) or "Resolve publish readiness blockers before pushing.",
            }
        else:
            try:
                push_payload = {
                    "publish_package": publish_package,
                    "wechat_app_id": request["wechat_app_id"],
                    "wechat_app_secret": request["wechat_app_secret"],
                    "allow_insecure_inline_credentials": request["allow_insecure_inline_credentials"],
                    "cover_image_path": request["cover_image_path"],
                    "cover_image_url": request["cover_image_url"],
                    "author": request["author"],
                    "show_cover_pic": request["show_cover_pic"],
                    "timeout_seconds": request["timeout_seconds"],
                    "human_review_approved": request["human_review_approved"],
                    "human_review_approved_by": request["human_review_approved_by"],
                    "human_review_note": request["human_review_note"],
                }
                push_result = push_publish_package_to_wechat(push_payload)
                if clean_text(push_result.get("status")) == "ok":
                    push_review_gate = safe_dict(push_result.get("review_gate"))
                    manual_review = build_manual_review_state(
                        request,
                        review_gate=push_review_gate or review_gate,
                        approved_at=isoformat_or_blank(now_utc()),
                    )
                    write_json(wechat_push_result_path, push_result)
                    push_stage = {
                        "requested": True,
                        "attempted": True,
                        "status": "ok",
                        "review_gate_status": push_review_gate.get("status", review_gate.get("status", "unknown")),
                        "push_readiness_status": push_readiness.get("status", "unknown"),
                        "blocked_reason": "",
                        "result_path": str(wechat_push_result_path),
                        "draft_media_id": clean_text(safe_dict(push_result.get("draft_result")).get("media_id")),
                        "cover_media_id": clean_text(safe_dict(push_result.get("uploaded_cover")).get("media_id")),
                        "inline_image_count": len(safe_list(push_result.get("uploaded_inline_images"))),
                        "error_message": "",
                        "next_step": "WeChat draft created successfully. Continue with final platform-side review before publishing.",
                    }
                    overall_status = "ok"
                else:
                    overall_status = clean_text(push_result.get("status")) or "push_error"
                    push_review_gate = safe_dict(push_result.get("review_gate"))
                    if push_review_gate:
                        manual_review = build_manual_review_state(request, review_gate=push_review_gate)
                    push_stage = {
                        **push_stage,
                        "requested": True,
                        "attempted": False,
                        "status": clean_text(push_result.get("status")) or "blocked_review_gate",
                        "review_gate_status": push_review_gate.get("status", review_gate.get("status", "unknown")),
                        "push_readiness_status": push_readiness.get("status", "unknown"),
                        "blocked_reason": clean_text(push_result.get("blocked_reason")) or "push_blocked",
                        "error_message": clean_text(push_result.get("error_message")),
                        "next_step": clean_text(push_review_gate.get("next_step")) or "Resolve the block and rerun the push step.",
                    }
            except Exception as exc:  # noqa: BLE001
                overall_status = "push_error"
                push_stage = {
                    **push_stage,
                    "requested": True,
                    "attempted": True,
                    "status": "error",
                    "blocked_reason": "push_failed",
                    "result_path": "",
                    "draft_media_id": "",
                    "cover_media_id": "",
                    "inline_image_count": 0,
                    "error_message": str(exc),
                    "next_step": "Inspect the push error, fix the failing asset or credential issue, then rerun the push step.",
                }

    result = {
        "status": overall_status,
        "workflow_kind": "article_publish",
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "selected_topic": selected_topic,
        "selected_topic_path": str(selected_topic_path),
        "news_request_path": str(news_request_path),
        "publish_package": publish_package,
        "publish_package_path": str(publish_package_path),
        "wechat_html_path": str(wechat_html_path),
        "manual_review": manual_review,
        "review_gate": review_gate,
        "next_push_command": (
            f'financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_wechat_push_draft.cmd "{publish_package_path}"'
        ),
        "push_stage": push_stage,
        "discovery_stage": {
            "result_path": str(discovery_result_path),
            "report_markdown": discovery_result.get("report_markdown", ""),
        },
        "workflow_stage": {
            "result_path": str(workflow_result_path),
            "report_path": workflow_result.get("workflow_report_path", ""),
            "draft_result_path": safe_dict(workflow_result.get("draft_stage")).get("result_path", ""),
            "final_result_path": safe_dict(workflow_result.get("final_stage")).get("result_path", ""),
            "quality_gate": safe_dict(workflow_result.get("final_stage")).get("quality_gate", ""),
        },
    }
    result["report_markdown"] = build_report_markdown(result)
    report_path = request["output_dir"] / "article-publish-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["report_path"] = str(report_path)
    return result


__all__ = ["build_news_request_from_topic", "build_publish_package", "run_article_publish"]
