#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

from article_cleanup_runtime import cleanup_article_temp_dirs
from article_workflow_runtime import load_json, run_article_workflow, write_json
from news_index_runtime import parse_datetime, slugify


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_batch_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    items = safe_list(raw_payload.get("items"))
    if not items:
        raise ValueError("article-batch-workflow requires an items[] list")

    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None)
    if analysis_time is None:
        raise ValueError("article-batch-workflow requires analysis_time at the batch level")

    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "article-batch-workflow" / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )
    return {
        "analysis_time": analysis_time,
        "items": items,
        "default_draft_mode": clean_text(raw_payload.get("default_draft_mode") or raw_payload.get("draft_mode")),
        "default_image_strategy": clean_text(raw_payload.get("default_image_strategy") or raw_payload.get("image_strategy")),
        "default_language_mode": clean_text(raw_payload.get("default_language_mode") or raw_payload.get("language_mode")),
        "default_tone": clean_text(raw_payload.get("default_tone") or raw_payload.get("tone")),
        "default_max_images": raw_payload.get("default_max_images", raw_payload.get("max_images")),
        "default_target_length_chars": raw_payload.get("default_target_length_chars", raw_payload.get("target_length_chars")),
        "cleanup_enabled": bool(raw_payload.get("cleanup_enabled") or raw_payload.get("cleanup_days") or raw_payload.get("cleanup_root_dir")),
        "cleanup_days": int(raw_payload.get("cleanup_days", 4) or 4),
        "cleanup_root_dir": clean_text(raw_payload.get("cleanup_root_dir")),
        "stop_on_error": bool(raw_payload.get("stop_on_error", False)),
        "max_parallel_topics": max(1, int(raw_payload.get("max_parallel_topics", min(4, len(items))) or 1)),
        "output_dir": output_dir,
    }


def load_item_payload(item: dict[str, Any]) -> dict[str, Any]:
    if isinstance(item.get("payload"), dict):
        return deepcopy(item["payload"])
    request_path = clean_text(item.get("request_path") or item.get("source_result_path") or item.get("input_path"))
    if not request_path:
        raise ValueError("Each batch item needs payload or request_path/source_result_path/input_path")
    return load_json(Path(request_path).resolve())


def item_label(item: dict[str, Any], payload: dict[str, Any], index: int) -> str:
    return (
        clean_text(item.get("label"))
        or clean_text(item.get("topic"))
        or clean_text(payload.get("topic"))
        or clean_text(safe_dict(payload.get("request")).get("topic"))
        or f"item-{index:02d}"
    )


def merge_item_request(batch_request: dict[str, Any], item: dict[str, Any], payload: dict[str, Any], item_dir: Path) -> dict[str, Any]:
    merged = deepcopy(payload)
    if clean_text(item.get("topic")):
        merged["topic"] = clean_text(item.get("topic"))
    if clean_text(item.get("title_hint")):
        merged["title_hint"] = clean_text(item.get("title_hint"))
    if clean_text(item.get("title_hint_zh")):
        merged["title_hint_zh"] = clean_text(item.get("title_hint_zh"))
    if clean_text(item.get("subtitle_hint")):
        merged["subtitle_hint"] = clean_text(item.get("subtitle_hint"))
    if clean_text(item.get("subtitle_hint_zh")):
        merged["subtitle_hint_zh"] = clean_text(item.get("subtitle_hint_zh"))
    if clean_text(item.get("angle")):
        merged["angle"] = clean_text(item.get("angle"))
    if clean_text(item.get("angle_zh")):
        merged["angle_zh"] = clean_text(item.get("angle_zh"))
    if clean_text(item.get("tone")):
        merged["tone"] = clean_text(item.get("tone"))
    elif batch_request.get("default_tone"):
        merged["tone"] = batch_request["default_tone"]
    if clean_text(item.get("draft_mode")):
        merged["draft_mode"] = clean_text(item.get("draft_mode"))
    elif batch_request.get("default_draft_mode"):
        merged["draft_mode"] = batch_request["default_draft_mode"]
    if clean_text(item.get("image_strategy")):
        merged["image_strategy"] = clean_text(item.get("image_strategy"))
    elif batch_request.get("default_image_strategy"):
        merged["image_strategy"] = batch_request["default_image_strategy"]
    if clean_text(item.get("language_mode")):
        merged["language_mode"] = clean_text(item.get("language_mode"))
    elif batch_request.get("default_language_mode"):
        merged["language_mode"] = batch_request["default_language_mode"]
    if item.get("max_images") is not None:
        merged["max_images"] = item.get("max_images")
    elif batch_request.get("default_max_images") is not None:
        merged["max_images"] = batch_request.get("default_max_images")
    if item.get("target_length_chars") is not None:
        merged["target_length_chars"] = item.get("target_length_chars")
    elif batch_request.get("default_target_length_chars") is not None:
        merged["target_length_chars"] = batch_request.get("default_target_length_chars")
    if "analysis_time" not in merged:
        merged["analysis_time"] = batch_request["analysis_time"].isoformat()
    merged["output_dir"] = str(item_dir)
    return merged


def build_batch_report(result: dict[str, Any]) -> str:
    cleanup_stage = safe_dict(result.get("cleanup_stage"))
    lines = [
        f"# Article Batch Workflow",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Total items: {result.get('total_items', 0)}",
        f"- Succeeded: {result.get('succeeded_items', 0)}",
        f"- Failed: {result.get('failed_items', 0)}",
        f"- Max parallel topics: {result.get('max_parallel_topics', 1)}",
        "",
    ]
    if cleanup_stage:
        lines.extend(
            [
                "## Cleanup",
                "",
                f"- Cleanup root: {clean_text(cleanup_stage.get('root_dir')) or 'none'}",
                f"- Retention days: {cleanup_stage.get('retention_days', 0)}",
                f"- Removed this run: {cleanup_stage.get('removed_count', 0)}",
                f"- Still kept: {cleanup_stage.get('kept_count', 0)}",
                "",
            ]
        )
    lines.extend(
        [
        "## Queue",
        "",
    ]
    )
    for item in safe_list(result.get("items")):
        lines.extend(
            [
                f"### {clean_text(item.get('label'))}",
                "",
                f"- Status: {clean_text(item.get('status'))}",
                f"- Draft title: {clean_text(item.get('draft_title')) or 'n/a'}",
                f"- Draft mode: {clean_text(item.get('draft_mode')) or 'n/a'}",
                f"- Images: {item.get('image_count', 0)}",
                f"- Local images ready: {item.get('local_ready_count', 0)}",
                f"- Remote images pending: {item.get('remote_only_count', 0)}",
                f"- Citations: {item.get('citation_count', 0)}",
                f"- Workflow report: {clean_text(item.get('workflow_report_path')) or 'n/a'}",
                f"- Draft preview: {clean_text(item.get('preview_path')) or 'n/a'}",
                f"- Review template: {clean_text(item.get('revision_template_path')) or 'n/a'}",
                "",
            ]
        )
        command = clean_text(item.get("suggested_revise_command"))
        if command:
            lines.extend(["```text", command, "```", ""])
        hydrate_command = clean_text(item.get("suggested_asset_hydrate_command"))
        if hydrate_command:
            lines.extend(["```text", hydrate_command, "```", ""])
        if clean_text(item.get("error")):
            lines.append(f"- Error: {clean_text(item.get('error'))}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_batch_item(request: dict[str, Any], item: dict[str, Any], index: int) -> tuple[int, dict[str, Any]]:
    payload = load_item_payload(item)
    label = item_label(item, payload, index)
    item_dir = request["output_dir"] / f"{index:02d}-{slugify(label, f'item-{index:02d}')}"
    workflow_payload = merge_item_request(request, item, payload, item_dir)
    workflow_result = run_article_workflow(workflow_payload)
    draft_stage = safe_dict(workflow_result.get("draft_stage"))
    asset_stage = safe_dict(workflow_result.get("asset_stage"))
    review_stage = safe_dict(workflow_result.get("review_stage"))
    result_item = {
        "index": index,
        "label": label,
        "status": clean_text(workflow_result.get("status")) or "ok",
        "draft_title": clean_text(draft_stage.get("title")),
        "draft_mode": clean_text(draft_stage.get("draft_mode")),
        "image_count": int(draft_stage.get("image_count", 0) or 0),
        "local_ready_count": int(asset_stage.get("local_ready_count", 0) or 0),
        "remote_only_count": int(asset_stage.get("remote_only_count", 0) or 0),
        "citation_count": int(draft_stage.get("citation_count", 0) or 0),
        "workflow_report_path": clean_text(workflow_result.get("workflow_report_path")),
        "workflow_result_path": str(item_dir / "workflow-result.json"),
        "preview_path": clean_text(draft_stage.get("preview_path")),
        "revision_template_path": clean_text(review_stage.get("revision_template_path")),
        "review_result_path": clean_text(review_stage.get("result_path")),
        "quality_gate": clean_text(safe_dict(workflow_result.get("final_stage")).get("quality_gate")),
        "suggested_revise_command": clean_text(review_stage.get("suggested_revise_command")),
        "suggested_asset_hydrate_command": clean_text(asset_stage.get("suggested_asset_hydrate_command")),
    }
    write_json(item_dir / "workflow-result.json", workflow_result)
    return index, result_item


def run_article_batch_workflow(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_batch_request(raw_payload)
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

    items_result_by_index: dict[int, dict[str, Any]] = {}
    succeeded = 0
    failed = 0
    serial_mode = request.get("stop_on_error") or request.get("max_parallel_topics", 1) <= 1 or len(request["items"]) <= 1
    if serial_mode:
        for index, item in enumerate(request["items"], start=1):
            item = safe_dict(item)
            try:
                _, result_item = run_batch_item(request, item, index)
                items_result_by_index[index] = result_item
                succeeded += 1
            except Exception as exc:
                label = clean_text(item.get("label")) or f"item-{index:02d}"
                items_result_by_index[index] = {"index": index, "label": label, "status": "error", "error": str(exc)}
                failed += 1
                if request.get("stop_on_error"):
                    break
    else:
        with ThreadPoolExecutor(max_workers=request["max_parallel_topics"]) as executor:
            future_map = {
                executor.submit(run_batch_item, request, safe_dict(item), index): (index, safe_dict(item))
                for index, item in enumerate(request["items"], start=1)
            }
            for future in as_completed(future_map):
                index, item = future_map[future]
                try:
                    _, result_item = future.result()
                    items_result_by_index[index] = result_item
                    succeeded += 1
                except Exception as exc:
                    label = clean_text(item.get("label")) or f"item-{index:02d}"
                    items_result_by_index[index] = {"index": index, "label": label, "status": "error", "error": str(exc)}
                    failed += 1

    items_result = [items_result_by_index[index] for index in sorted(items_result_by_index)]

    result = {
        "status": "ok" if failed == 0 else "partial",
        "workflow_kind": "article_batch_workflow",
        "analysis_time": request["analysis_time"].isoformat(),
        "output_dir": str(request["output_dir"]),
        "max_parallel_topics": request.get("max_parallel_topics", 1),
        "total_items": len(request["items"]),
        "succeeded_items": succeeded,
        "failed_items": failed,
        "cleanup_stage": cleanup_stage,
        "items": items_result,
    }
    result["report_markdown"] = build_batch_report(result)
    report_path = request["output_dir"] / "batch-workflow-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["report_path"] = str(report_path)
    return result


__all__ = ["load_json", "run_article_batch_workflow", "write_json"]
