#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from article_cleanup_runtime import cleanup_article_temp_dirs
from article_feedback_profiles import feedback_profile_status, resolve_profile_dir
from article_draft_flow_runtime import build_article_draft, clean_text, load_json, safe_dict, safe_list, write_json
from news_index_runtime import isoformat_or_blank, parse_datetime, run_news_index, slugify
from x_index_runtime import run_x_index


def detect_payload_kind(payload: dict[str, Any]) -> str:
    if any(key in payload for key in ("source_result", "source_result_path")):
        return "indexed_result"
    if any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output")):
        return "indexed_result"
    if any(
        key in payload
        for key in ("seed_posts", "manual_urls", "account_allowlist", "include_threads", "include_images", "max_thread_posts")
    ):
        return "x_request"
    return "news_request"


def normalize_workflow_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    payload_kind = detect_payload_kind(payload)
    source_payload = safe_dict(payload.get("source_result")) if payload_kind == "indexed_result" else {}
    source_result_path = clean_text(payload.get("source_result_path") or payload.get("source_path"))
    if not source_payload and payload_kind == "indexed_result" and source_result_path:
        source_payload = load_json(Path(source_result_path).resolve())

    if payload_kind == "indexed_result" and not source_payload:
        source_payload = deepcopy(payload)

    source_request = safe_dict(source_payload.get("request")) if source_payload else {}
    retrieval_request = safe_dict(source_payload.get("retrieval_request")) if source_payload else {}
    runtime_request = safe_dict(safe_dict(source_payload.get("retrieval_result")).get("request")) if source_payload else {}
    analysis_time = (
        parse_datetime(payload.get("analysis_time"), fallback=None)
        or parse_datetime(source_request.get("analysis_time"), fallback=None)
        or parse_datetime(retrieval_request.get("analysis_time"), fallback=None)
        or parse_datetime(runtime_request.get("analysis_time"), fallback=None)
    )
    if analysis_time is None:
        raise ValueError("article-workflow requires analysis_time in the request or the indexed result")

    topic = (
        clean_text(payload.get("topic"))
        or clean_text(source_request.get("topic"))
        or clean_text(retrieval_request.get("topic"))
        or clean_text(runtime_request.get("topic"))
        or "article-topic"
    )
    output_dir = (
        Path(clean_text(payload.get("output_dir"))).expanduser()
        if clean_text(payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "article-workflow" / slugify(topic, "article-topic") / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )
    return {
        "payload_kind": payload_kind,
        "topic": topic,
        "analysis_time": analysis_time,
        "title_hint": clean_text(payload.get("title_hint")),
        "title_hint_zh": clean_text(payload.get("title_hint_zh")),
        "subtitle_hint": clean_text(payload.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(payload.get("subtitle_hint_zh")),
        "angle": clean_text(payload.get("angle")),
        "angle_zh": clean_text(payload.get("angle_zh")),
        "tone": clean_text(payload.get("tone")),
        "target_length_chars": payload.get("target_length_chars", payload.get("target_length")),
        "max_images": payload.get("max_images"),
        "image_strategy": clean_text(payload.get("image_strategy")),
        "draft_mode": clean_text(payload.get("draft_mode")),
        "language_mode": clean_text(payload.get("language_mode") or payload.get("output_language")),
        "feedback_profile_dir": clean_text(payload.get("feedback_profile_dir")),
        "cleanup_enabled": bool(payload.get("cleanup_enabled") or payload.get("cleanup_days") or payload.get("cleanup_root_dir")),
        "cleanup_days": int(payload.get("cleanup_days", 4) or 4),
        "cleanup_root_dir": clean_text(payload.get("cleanup_root_dir")),
        "source_result": source_payload,
        "source_result_path": source_result_path,
        "payload": payload,
        "output_dir": output_dir,
    }


def build_draft_payload(request: dict[str, Any], source_result: dict[str, Any]) -> dict[str, Any]:
    draft_payload = {"source_result": source_result}
    for key in (
        "topic",
        "title_hint",
        "title_hint_zh",
        "subtitle_hint",
        "subtitle_hint_zh",
        "angle",
        "angle_zh",
        "tone",
        "target_length_chars",
        "max_images",
        "language_mode",
        "feedback_profile_dir",
    ):
        if request.get(key) not in (None, ""):
            draft_payload[key] = request[key]
    if request.get("image_strategy"):
        draft_payload["image_strategy"] = request["image_strategy"]
    if request.get("draft_mode"):
        draft_payload["draft_mode"] = request["draft_mode"]
    draft_payload["asset_output_dir"] = str(request["output_dir"] / "assets")
    draft_payload["download_remote_images"] = True
    return draft_payload


def build_revision_template(draft_result: dict[str, Any]) -> dict[str, Any]:
    request = safe_dict(draft_result.get("request"))
    article_package = safe_dict(draft_result.get("article_package"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    hero_image_id = clean_text(selected_images[0].get("asset_id") or selected_images[0].get("image_id")) if selected_images else ""
    profile_status = feedback_profile_status(
        resolve_profile_dir(request.get("feedback_profile_dir")),
        clean_text(request.get("topic")) or clean_text(safe_dict(draft_result.get("source_summary")).get("topic")) or "article-topic",
    )
    template = {
        "feedback": {
            "summary": "",
            "tone": clean_text(request.get("tone")) or "neutral-cautious",
            "keep_image_asset_ids": [hero_image_id] if hero_image_id else [],
            "drop_image_asset_ids": [],
        },
        "language_mode": clean_text(request.get("language_mode")) or "english",
        "tone": clean_text(request.get("tone")) or "neutral-cautious",
        "draft_mode": clean_text(request.get("draft_mode")) or "balanced",
        "image_strategy": clean_text(request.get("image_strategy")) or "mixed",
        "max_images": request.get("max_images", 3),
        "must_include": safe_list(request.get("must_include")),
        "must_avoid": safe_list(request.get("must_avoid")),
        "persist_feedback": {
            "scope": "none",
            "use_current_request_defaults": True,
            "defaults": {
                "language_mode": clean_text(request.get("language_mode")) or "english",
                "tone": clean_text(request.get("tone")) or "neutral-cautious",
                "draft_mode": clean_text(request.get("draft_mode")) or "balanced",
                "image_strategy": clean_text(request.get("image_strategy")) or "mixed",
                "max_images": request.get("max_images", 3),
                "must_include": [],
                "must_avoid": [],
            },
            "notes": [],
        },
        "title_hint": "",
        "title_hint_zh": "",
        "subtitle_hint": "",
        "subtitle_hint_zh": "",
        "angle": "",
        "angle_zh": "",
        "edited_body_markdown": "",
        "feedback_profile_status": profile_status,
        "feedback_reuse_help": {
            "save_for_all_future_drafts": "Set persist_feedback.scope to global.",
            "save_for_this_topic_only": "Set persist_feedback.scope to topic.",
            "save_for_both": "Set persist_feedback.scope to both.",
        },
    }
    return template


def summarize_asset_stage(draft_result: dict[str, Any], draft_result_path: Path) -> dict[str, Any]:
    article_package = safe_dict(draft_result.get("article_package"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    localization = safe_dict(draft_result.get("asset_localization") or article_package.get("asset_localization"))
    local_ready_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "local_ready")
    remote_only_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "remote_only")
    missing_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "missing")
    return {
        "asset_output_dir": clean_text(localization.get("asset_output_dir")),
        "downloaded_count": int(localization.get("downloaded_count", 0) or 0),
        "failed_count": int(localization.get("failed_count", 0) or 0),
        "local_ready_count": local_ready_count,
        "remote_only_count": remote_only_count,
        "missing_count": missing_count,
        "suggested_asset_hydrate_command": (
            f"financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_article_asset_hydrate.cmd \"{draft_result_path}\""
            if remote_only_count > 0
            else ""
        ),
    }


def summarize_feedback_stage(draft_result: dict[str, Any]) -> dict[str, Any]:
    request = safe_dict(draft_result.get("request"))
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    topic = clean_text(request.get("topic")) or clean_text(safe_dict(draft_result.get("source_summary")).get("topic")) or "article-topic"
    return feedback_profile_status(profile_dir, topic)


def build_report_markdown(result: dict[str, Any]) -> str:
    source_stage = safe_dict(result.get("source_stage"))
    draft_stage = safe_dict(result.get("draft_stage"))
    review_stage = safe_dict(result.get("review_stage"))
    asset_stage = safe_dict(result.get("asset_stage"))
    feedback_stage = safe_dict(result.get("feedback_stage"))
    lines = [
        f"# Article Workflow: {clean_text(result.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Source stage: {clean_text(source_stage.get('source_kind'))}",
        f"- Draft mode: {clean_text(draft_stage.get('draft_mode'))}",
        f"- Draft title: {clean_text(draft_stage.get('title'))}",
        f"- Images kept: {draft_stage.get('image_count', 0)}",
        f"- Citations kept: {draft_stage.get('citation_count', 0)}",
        "",
        "## Files",
        "",
        f"- Source result: {clean_text(source_stage.get('result_path')) or 'not written'}",
        f"- Source report: {clean_text(source_stage.get('report_path')) or 'not written'}",
        f"- Draft result: {clean_text(draft_stage.get('result_path')) or 'not written'}",
        f"- Draft report: {clean_text(draft_stage.get('report_path')) or 'not written'}",
        f"- Draft preview: {clean_text(draft_stage.get('preview_path')) or 'not written'}",
        f"- Review template: {clean_text(review_stage.get('revision_template_path')) or 'not written'}",
        "",
        "## Next Step",
        "",
        "Use the draft result plus the review template to run one revision pass without re-indexing the same material.",
    ]
    cleanup_stage = safe_dict(result.get("cleanup_stage"))
    if cleanup_stage:
        lines.extend(
            [
                "",
                "## Cleanup",
                "",
                f"- Cleanup root: {clean_text(cleanup_stage.get('root_dir')) or 'none'}",
                f"- Retention days: {cleanup_stage.get('retention_days', 0)}",
                f"- Removed this run: {cleanup_stage.get('removed_count', 0)}",
                f"- Still kept: {cleanup_stage.get('kept_count', 0)}",
            ]
        )
    suggested_command = clean_text(review_stage.get("suggested_revise_command"))
    if suggested_command:
        lines.extend(["", "```text", suggested_command, "```"])
    if asset_stage:
        lines.extend(
            [
                "",
                "## Images",
                "",
                f"- Local images ready: {asset_stage.get('local_ready_count', 0)}",
                f"- Remote-only images left: {asset_stage.get('remote_only_count', 0)}",
                f"- Missing images: {asset_stage.get('missing_count', 0)}",
                f"- Download attempts this run: {asset_stage.get('downloaded_count', 0)}",
                f"- Download failures this run: {asset_stage.get('failed_count', 0)}",
                f"- Asset directory: {clean_text(asset_stage.get('asset_output_dir')) or 'not set'}",
            ]
        )
        hydrate_command = clean_text(asset_stage.get("suggested_asset_hydrate_command"))
        if hydrate_command:
            lines.extend(["", "Retry image hydration with:", "", "```text", hydrate_command, "```"])
    if feedback_stage:
        applied_paths = safe_list(feedback_stage.get("applied_paths"))
        lines.extend(
            [
                "",
                "## Feedback Reuse",
                "",
                f"- Profile directory: {clean_text(feedback_stage.get('profile_dir')) or 'none'}",
                f"- Applied profiles now: {', '.join(applied_paths) if applied_paths else 'none'}",
                f"- Global defaults file: {clean_text(feedback_stage.get('global_profile_path')) or 'none'} ({'saved' if feedback_stage.get('global_exists') else 'not saved yet'})",
                f"- Topic defaults file: {clean_text(feedback_stage.get('topic_profile_path')) or 'none'} ({'saved' if feedback_stage.get('topic_exists') else 'not saved yet'})",
                "- To save this draft style for all future drafts, set persist_feedback.scope to global in the review template.",
                "- To save it only for this topic, set persist_feedback.scope to topic in the review template.",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_article_workflow(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_workflow_request(raw_payload)
    cleanup_stage = {}
    if request.get("cleanup_enabled"):
        cleanup_root = clean_text(request.get("cleanup_root_dir")) or str(request["output_dir"].parent)
        cleanup_stage = cleanup_article_temp_dirs(
            {
                "root_dir": cleanup_root,
                "retention_days": request.get("cleanup_days", 4),
            }
        )
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    payload_kind = request["payload_kind"]
    source_payload = request["source_result"]
    if payload_kind == "x_request":
        source_payload = run_x_index(request["payload"])
    elif payload_kind == "news_request":
        source_payload = run_news_index(request["payload"])
    elif not source_payload:
        raise ValueError("article-workflow could not resolve a source payload")

    source_kind = "x_index" if safe_list(source_payload.get("x_posts")) or safe_dict(source_payload.get("evidence_pack")) else "news_index"
    source_result_path = request["output_dir"] / "source-result.json"
    source_report_path = request["output_dir"] / "source-report.md"
    write_json(source_result_path, source_payload)
    source_report_path.write_text(source_payload.get("report_markdown", ""), encoding="utf-8-sig")

    draft_payload = build_draft_payload(request, source_payload)
    draft_result = build_article_draft(draft_payload)
    draft_result_path = request["output_dir"] / "article-draft-result.json"
    draft_report_path = request["output_dir"] / "article-draft-report.md"
    draft_preview_path = request["output_dir"] / "article-draft-preview.html"
    write_json(draft_result_path, draft_result)
    draft_report_path.write_text(draft_result.get("report_markdown", ""), encoding="utf-8-sig")
    draft_preview_path.write_text(draft_result.get("preview_html", ""), encoding="utf-8-sig")

    revision_template = build_revision_template(draft_result)
    revision_template_path = request["output_dir"] / "article-revise-template.json"
    write_json(revision_template_path, revision_template)

    article_package = safe_dict(draft_result.get("article_package"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    citations = safe_list(article_package.get("citations"))
    asset_stage = summarize_asset_stage(draft_result, draft_result_path)
    feedback_stage = summarize_feedback_stage(draft_result)
    result = {
        "status": "ok",
        "workflow_kind": "article_workflow",
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "source_stage": {
            "source_kind": source_kind,
            "result_path": str(source_result_path),
            "report_path": str(source_report_path),
        },
        "draft_stage": {
            "result_path": str(draft_result_path),
            "report_path": str(draft_report_path),
            "preview_path": str(draft_preview_path),
            "title": clean_text(article_package.get("title")),
            "draft_mode": clean_text(article_package.get("draft_mode")),
            "image_count": len(selected_images),
            "citation_count": len(citations),
        },
        "cleanup_stage": cleanup_stage,
        "asset_stage": asset_stage,
        "feedback_stage": feedback_stage,
        "review_stage": {
            "revision_template_path": str(revision_template_path),
            "suggested_revise_command": (
                f"financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_article_revise.cmd "
                f"\"{draft_result_path}\" \"{revision_template_path}\" --output \"{request['output_dir'] / 'article-revise-result.json'}\" "
                f"--markdown-output \"{request['output_dir'] / 'article-revise-report.md'}\""
            ),
        },
    }
    result["report_markdown"] = build_report_markdown(result)
    workflow_report_path = request["output_dir"] / "workflow-report.md"
    workflow_report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["workflow_report_path"] = str(workflow_report_path)
    return result


__all__ = ["build_revision_template", "load_json", "run_article_workflow", "write_json"]
