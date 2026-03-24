#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from article_feedback_profiles import (
    feedback_profile_status,
    normalize_profile_feedback,
    request_defaults_from_request,
    resolve_profile_dir,
    save_feedback_profiles,
)
from article_draft_flow_runtime import (
    assemble_article_package,
    build_article_preview_html,
    build_report_markdown,
    clean_string_list,
    clean_text,
    draft_metrics,
    load_json,
    localize_selected_images,
    safe_dict,
    safe_list,
    sanitize_draft_mode,
    write_json,
)
from news_index_runtime import isoformat_or_blank, parse_datetime


def load_draft_result(raw_payload: dict[str, Any]) -> dict[str, Any]:
    draft_result = raw_payload.get("draft_result") or raw_payload.get("article_result")
    if isinstance(draft_result, dict):
        return deepcopy(draft_result)

    draft_result_path = clean_text(
        raw_payload.get("draft_result_path") or raw_payload.get("article_result_path") or raw_payload.get("source_path")
    )
    if not draft_result_path:
        raise ValueError("article-revise requires draft_result/article_result or a matching *_path")
    return load_json(Path(draft_result_path).resolve())


def normalize_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    feedback = safe_dict(payload.get("feedback"))
    feedback_notes = clean_string_list(payload.get("feedback_notes"))
    if clean_text(feedback.get("summary")):
        feedback_notes.append(clean_text(feedback.get("summary")))
    if clean_text(payload.get("revision_note")):
        feedback_notes.append(clean_text(payload.get("revision_note")))
    drop_image_ids = clean_string_list(
        payload.get("drop_image_ids") or payload.get("drop_image_asset_ids") or feedback.get("drop_image_asset_ids")
    )
    keep_image_ids = clean_string_list(
        payload.get("pinned_image_ids") or payload.get("pin_image_ids") or feedback.get("keep_image_asset_ids")
    )
    return {
        "feedback_notes": feedback_notes,
        "drop_image_ids": drop_image_ids,
        "keep_image_ids": keep_image_ids,
        "summary": clean_text(feedback.get("summary")),
    }


def normalize_revision_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    article_result = load_draft_result(raw_payload)
    prior_request = safe_dict(article_result.get("request"))
    source_summary = safe_dict(article_result.get("source_summary")) or safe_dict(article_result.get("source_context"))
    feedback = normalize_feedback(raw_payload)

    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None) or parse_datetime(
        prior_request.get("analysis_time"),
        fallback=parse_datetime(source_summary.get("analysis_time")),
    )
    if analysis_time is None:
        raise ValueError("Unable to determine analysis_time for article revision")

    return {
        "analysis_time": analysis_time,
        "topic": clean_text(raw_payload.get("topic") or prior_request.get("topic") or source_summary.get("topic")),
        "title_hint": clean_text(raw_payload.get("title_hint") or raw_payload.get("title_override") or prior_request.get("title_hint")),
        "title_hint_zh": clean_text(raw_payload.get("title_hint_zh") or prior_request.get("title_hint_zh")),
        "subtitle_hint": clean_text(raw_payload.get("subtitle_hint") or raw_payload.get("subtitle_override") or prior_request.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(raw_payload.get("subtitle_hint_zh") or prior_request.get("subtitle_hint_zh")),
        "angle": clean_text(raw_payload.get("angle") or prior_request.get("angle")),
        "angle_zh": clean_text(raw_payload.get("angle_zh") or prior_request.get("angle_zh")),
        "tone": clean_text(raw_payload.get("tone") or safe_dict(raw_payload.get("feedback")).get("tone") or prior_request.get("tone") or "neutral-cautious"),
        "target_length_chars": int(
            raw_payload.get("target_length_chars", raw_payload.get("target_length", prior_request.get("target_length_chars", 1000)))
        ),
        "max_images": max(0, min(int(raw_payload.get("max_images", prior_request.get("max_images", 3))), 8)),
        "image_strategy": clean_text(raw_payload.get("image_strategy") or prior_request.get("image_strategy") or "mixed"),
        "draft_mode": sanitize_draft_mode(raw_payload.get("draft_mode") or prior_request.get("draft_mode")),
        "language_mode": clean_text(raw_payload.get("language_mode") or prior_request.get("language_mode") or "english"),
        "must_include": clean_string_list(raw_payload.get("must_include") or prior_request.get("must_include")),
        "must_avoid": clean_string_list(raw_payload.get("must_avoid") or prior_request.get("must_avoid")),
        "asset_output_dir": clean_text(raw_payload.get("asset_output_dir") or safe_dict(article_result.get("draft_context")).get("asset_output_dir")),
        "download_remote_images": True,
        "feedback_profile_dir": clean_text(raw_payload.get("feedback_profile_dir") or prior_request.get("feedback_profile_dir")),
        "persist_feedback": normalize_profile_feedback(raw_payload.get("persist_feedback")),
        "edited_body_markdown": raw_payload.get("edited_body_markdown") if isinstance(raw_payload.get("edited_body_markdown"), str) else "",
        "edited_article_markdown": raw_payload.get("edited_article_markdown") if isinstance(raw_payload.get("edited_article_markdown"), str) else "",
        "article_result": article_result,
        "feedback": feedback,
    }


def reorder_candidates(image_candidates: list[dict[str, Any]], keep_image_ids: list[str], drop_image_ids: list[str]) -> list[dict[str, Any]]:
    keep = set(clean_string_list(keep_image_ids))
    drop = set(clean_string_list(drop_image_ids))
    filtered = []
    for item in image_candidates:
        image_id = clean_text(item.get("image_id") or item.get("asset_id"))
        if image_id and image_id in drop:
            continue
        filtered.append(item)

    if not keep:
        return filtered

    by_id = {clean_text(item.get("image_id") or item.get("asset_id")): item for item in filtered}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for image_id in keep:
        if image_id in by_id:
            ordered.append(by_id[image_id])
            seen.add(image_id)
    for item in filtered:
        image_id = clean_text(item.get("image_id") or item.get("asset_id"))
        if image_id in seen:
            continue
        ordered.append(item)
    return ordered


def build_article_revision(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_revision_request(raw_payload)
    article_result = deepcopy(request["article_result"])
    source_summary = deepcopy(safe_dict(article_result.get("source_summary")) or safe_dict(article_result.get("source_context")))
    evidence_digest = deepcopy(safe_dict(article_result.get("evidence_digest")))
    draft_context = deepcopy(safe_dict(article_result.get("draft_context")))

    citations = deepcopy(safe_list(draft_context.get("citation_candidates"))) or deepcopy(
        safe_list(safe_dict(article_result.get("article_package")).get("citations"))
    )
    image_candidates = deepcopy(safe_list(draft_context.get("image_candidates")))
    if not image_candidates:
        image_candidates = deepcopy(
            safe_list(safe_dict(article_result.get("article_package")).get("selected_images"))
            or safe_list(safe_dict(article_result.get("article_package")).get("image_blocks"))
        )
    image_candidates = reorder_candidates(
        image_candidates,
        request["feedback"].get("keep_image_ids", []),
        request["feedback"].get("drop_image_ids", []),
    )

    source_summary["topic"] = clean_text(request.get("topic")) or clean_text(source_summary.get("topic"))
    source_summary["analysis_time"] = isoformat_or_blank(request["analysis_time"])

    article_package, selected_images = assemble_article_package(request, source_summary, evidence_digest, citations, image_candidates)

    manual_override = False
    manual_body_override = False
    manual_article_override = False
    if clean_text(request.get("edited_body_markdown")):
        manual_override = True
        manual_body_override = True
        article_package["body_markdown"] = request.get("edited_body_markdown").strip() + "\n"
    if clean_text(request.get("edited_article_markdown")):
        manual_override = True
        manual_article_override = True
        article_package["article_markdown"] = request.get("edited_article_markdown").strip() + "\n"
    article_package["image_blocks"] = deepcopy(selected_images)
    article_package["selected_images"] = deepcopy(selected_images)
    article_package["manual_body_override"] = manual_body_override
    article_package["manual_article_override"] = manual_article_override

    editor_notes = clean_string_list(safe_dict(article_result.get("article_package")).get("editor_notes"))
    editor_notes.extend(request["feedback"].get("feedback_notes", []))
    if manual_override:
        editor_notes.append("Manual article/body override was applied during revision.")
    article_package["editor_notes"] = clean_string_list(editor_notes)
    article_package["draft_metrics"] = draft_metrics(article_package["body_markdown"], selected_images, citations)
    article_package["char_count"] = article_package["draft_metrics"]["char_count"]
    asset_localization = localize_selected_images(article_package, request)
    selected_images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    saved_profile_paths = save_feedback_profiles(
        resolve_profile_dir(request.get("feedback_profile_dir")),
        request.get("topic"),
        request["analysis_time"],
        request.get("persist_feedback"),
        request_defaults=request_defaults_from_request(request),
    )
    article_package["feedback_profile_status"] = feedback_profile_status(
        resolve_profile_dir(request.get("feedback_profile_dir")),
        request.get("topic"),
    )
    if saved_profile_paths:
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Saved feedback profile updates: {', '.join(saved_profile_paths)}"]
        )

    result = deepcopy(article_result)
    result["request"] = {
        **(safe_dict(article_result.get("request"))),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "topic": request.get("topic"),
        "title_hint": request.get("title_hint"),
        "title_hint_zh": request.get("title_hint_zh"),
        "subtitle_hint": request.get("subtitle_hint"),
        "subtitle_hint_zh": request.get("subtitle_hint_zh"),
        "angle": request.get("angle"),
        "angle_zh": request.get("angle_zh"),
        "tone": request.get("tone"),
        "target_length_chars": request.get("target_length_chars"),
        "max_images": request.get("max_images"),
        "image_strategy": request.get("image_strategy"),
        "draft_mode": request.get("draft_mode"),
        "language_mode": request.get("language_mode"),
        "must_include": request.get("must_include"),
        "must_avoid": request.get("must_avoid"),
        "feedback_profile_dir": request.get("feedback_profile_dir"),
        "source_result": None,
    }
    result["source_summary"] = source_summary
    result["source_context"] = {
        "source_kind": source_summary.get("source_kind"),
        "topic": source_summary.get("topic"),
        "analysis_time": source_summary.get("analysis_time"),
        "source_result_path": clean_text(safe_dict(article_result.get("source_context")).get("source_result_path")),
    }
    result["draft_context"] = {
        **draft_context,
        "source_summary": source_summary,
        "evidence_digest": evidence_digest,
        "citation_candidates": citations,
        "image_candidates": image_candidates,
        "selected_images": deepcopy(selected_images),
        "asset_output_dir": request.get("asset_output_dir"),
    }
    result["article_package"] = article_package
    result["saved_feedback_profiles"] = saved_profile_paths
    result["feedback_profile_status"] = deepcopy(safe_dict(article_package.get("feedback_profile_status")))
    result["asset_localization"] = asset_localization
    result["preview_html"] = build_article_preview_html(article_package)

    revision_entry = {
        "revised_at": isoformat_or_blank(request["analysis_time"]),
        "manual_override": manual_override,
        "feedback_notes": request["feedback"].get("feedback_notes", []),
        "image_count": len(selected_images),
        "citation_count": len(citations),
        "kept_image_ids": request["feedback"].get("keep_image_ids", []),
        "dropped_image_ids": request["feedback"].get("drop_image_ids", []),
        "saved_feedback_profiles": saved_profile_paths,
    }
    result["revision_history"] = safe_list(article_result.get("revision_history")) + [revision_entry]
    result["revision_log"] = safe_list(article_result.get("revision_log")) + [revision_entry]
    result["report_markdown"] = build_report_markdown(article_package)
    return result


__all__ = ["build_article_revision", "load_json", "write_json"]
