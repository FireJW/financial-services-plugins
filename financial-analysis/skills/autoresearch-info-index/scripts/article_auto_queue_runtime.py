#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

from article_batch_workflow_runtime import run_article_batch_workflow
from article_workflow_runtime import load_json, write_json
from news_index_runtime import parse_datetime, slugify, run_news_index
from runtime_paths import runtime_subdir
from x_index_runtime import run_x_index


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def detect_payload_kind(payload: dict[str, Any]) -> str:
    if any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output")):
        return "indexed_result"
    if any(key in payload for key in ("seed_posts", "manual_urls", "account_allowlist", "include_threads", "include_images")):
        return "x_request"
    return "news_request"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    candidates = safe_list(raw_payload.get("candidates") or raw_payload.get("items"))
    if not candidates:
        raise ValueError("article-auto-queue requires candidates[]")
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None)
    if analysis_time is None:
        raise ValueError("article-auto-queue requires analysis_time")
    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else runtime_subdir("article-auto-queue", analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    top_n = int(raw_payload.get("top_n", min(3, len(candidates))))
    return {
        "analysis_time": analysis_time,
        "candidates": candidates,
        "top_n": max(1, min(top_n, len(candidates))),
        "prefer_visuals": bool(raw_payload.get("prefer_visuals", True)),
        "default_draft_mode": clean_text(raw_payload.get("default_draft_mode") or raw_payload.get("draft_mode")),
        "default_image_strategy": clean_text(raw_payload.get("default_image_strategy") or raw_payload.get("image_strategy")),
        "default_language_mode": clean_text(raw_payload.get("default_language_mode") or raw_payload.get("language_mode")),
        "default_tone": clean_text(raw_payload.get("default_tone") or raw_payload.get("tone")),
        "default_max_images": raw_payload.get("default_max_images", raw_payload.get("max_images")),
        "default_target_length_chars": raw_payload.get("default_target_length_chars", raw_payload.get("target_length_chars")),
        "max_parallel_topics": max(1, int(raw_payload.get("max_parallel_topics", min(4, top_n)) or 1)),
        "max_parallel_candidates": max(1, int(raw_payload.get("max_parallel_candidates", min(4, len(candidates))) or 1)),
        "output_dir": output_dir,
    }


def load_candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    if isinstance(candidate.get("payload"), dict):
        return deepcopy(candidate["payload"])
    request_path = clean_text(candidate.get("request_path") or candidate.get("source_result_path") or candidate.get("input_path"))
    if not request_path:
        raise ValueError("Each candidate needs payload or request_path/source_result_path/input_path")
    return load_json(Path(request_path).resolve())


def candidate_label(candidate: dict[str, Any], payload: dict[str, Any], index: int) -> str:
    return (
        clean_text(candidate.get("label"))
        or clean_text(candidate.get("topic"))
        or clean_text(payload.get("topic"))
        or clean_text(safe_dict(payload.get("request")).get("topic"))
        or f"candidate-{index:02d}"
    )


def resolve_source_payload(candidate: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    kind = detect_payload_kind(payload)
    if kind == "indexed_result":
        source_payload = payload
    elif kind == "x_request":
        source_payload = run_x_index(payload)
    else:
        source_payload = run_news_index(payload)
    source_kind = "x_index" if safe_list(source_payload.get("x_posts")) or safe_dict(source_payload.get("evidence_pack")) else "news_index"
    return source_payload, source_kind


def count_local_images(source_payload: dict[str, Any]) -> int:
    count = 0
    for post in safe_list(source_payload.get("x_posts")):
        if not isinstance(post, dict):
            continue
        root_path = clean_text(post.get("root_post_screenshot_path"))
        if root_path and Path(root_path).exists():
            count += 1
        for media in safe_list(post.get("media_items")):
            if not isinstance(media, dict):
                continue
            media_path = clean_text(media.get("local_artifact_path"))
            if media_path and Path(media_path).exists():
                count += 1
    return count


def count_remote_images(source_payload: dict[str, Any]) -> int:
    count = 0
    for post in safe_list(source_payload.get("x_posts")):
        if not isinstance(post, dict):
            continue
        if clean_text(post.get("root_post_screenshot_path")) and not Path(clean_text(post.get("root_post_screenshot_path"))).exists():
            count += 1
        for media in safe_list(post.get("media_items")):
            if not isinstance(media, dict):
                continue
            if clean_text(media.get("source_url")) and not clean_text(media.get("local_artifact_path")):
                count += 1
    return count


def blocked_count(source_payload: dict[str, Any]) -> int:
    runtime = safe_dict(source_payload.get("retrieval_result")) or source_payload
    return sum(1 for item in safe_list(runtime.get("observations")) if clean_text(item.get("access_mode")) == "blocked")


def top_signal_score(source_payload: dict[str, Any]) -> int:
    runtime = safe_dict(source_payload.get("retrieval_result")) or source_payload
    latest = safe_list(safe_dict(runtime.get("verdict_output")).get("latest_signals"))
    if not latest:
        return 0
    first = safe_dict(latest[0])
    return int(first.get("rank_score", 0) or 0)


def source_count(source_payload: dict[str, Any]) -> int:
    runtime = safe_dict(source_payload.get("retrieval_result")) or source_payload
    return len(safe_list(runtime.get("observations")))


def confidence_width(source_payload: dict[str, Any]) -> int:
    runtime = safe_dict(source_payload.get("retrieval_result")) or source_payload
    interval = safe_list(safe_dict(runtime.get("verdict_output")).get("confidence_interval"))
    if len(interval) != 2:
        return 100
    try:
        return max(0, int(interval[1]) - int(interval[0]))
    except Exception:
        return 100


def priority_metrics(source_payload: dict[str, Any], source_kind: str, prefer_visuals: bool) -> dict[str, Any]:
    local_images = count_local_images(source_payload)
    remote_images = count_remote_images(source_payload)
    blocked = blocked_count(source_payload)
    top_signal = top_signal_score(source_payload)
    sources = source_count(source_payload)
    width = confidence_width(source_payload)
    score = 0
    score += min(40, local_images * (20 if prefer_visuals else 12))
    score += min(10, remote_images * 4)
    score += min(20, sources * 3)
    score += min(20, top_signal // 4) if top_signal else 0
    score += max(0, 20 - width // 5)
    score += 8 if source_kind == "x_index" and prefer_visuals and local_images > 0 else 0
    score -= blocked * 4
    reasons: list[str] = []
    if local_images:
        reasons.append(f"{local_images} local image(s)")
    elif remote_images:
        reasons.append(f"{remote_images} remote image(s)")
    if sources:
        reasons.append(f"{sources} source observation(s)")
    if top_signal:
        reasons.append(f"top signal score {top_signal}")
    if blocked:
        reasons.append(f"{blocked} blocked source(s)")
    reasons.append(f"confidence width {width}")
    return {
        "priority_score": score,
        "local_image_count": local_images,
        "remote_image_count": remote_images,
        "blocked_source_count": blocked,
        "source_count": sources,
        "top_signal_score": top_signal,
        "confidence_width": width,
        "reason_summary": "; ".join(reasons),
    }


def choose_defaults(candidate: dict[str, Any], metrics: dict[str, Any], batch_request: dict[str, Any]) -> tuple[str, str]:
    draft_mode = clean_text(candidate.get("draft_mode"))
    image_strategy = clean_text(candidate.get("image_strategy"))
    if not draft_mode:
        if metrics["local_image_count"] > 0 and batch_request.get("prefer_visuals"):
            draft_mode = "image_only" if metrics["blocked_source_count"] > 0 and metrics["local_image_count"] == 1 else "image_first"
        else:
            draft_mode = clean_text(batch_request.get("default_draft_mode")) or "balanced"
    if not image_strategy:
        if metrics["local_image_count"] > 0 and batch_request.get("prefer_visuals"):
            image_strategy = "screenshots_only" if metrics["blocked_source_count"] > 0 else "prefer_images"
        else:
            image_strategy = clean_text(batch_request.get("default_image_strategy")) or "mixed"
    return draft_mode, image_strategy


def rank_single_candidate(request: dict[str, Any], candidate: dict[str, Any], index: int, sources_dir: Path) -> tuple[int, dict[str, Any]]:
    payload = load_candidate_payload(candidate)
    label = candidate_label(candidate, payload, index)
    source_payload, source_kind = resolve_source_payload(candidate, payload)
    metrics = priority_metrics(source_payload, source_kind, request["prefer_visuals"])
    draft_mode, image_strategy = choose_defaults(candidate, metrics, request)
    source_result_path = clean_text(candidate.get("request_path") or candidate.get("source_result_path") or candidate.get("input_path"))
    return (
        index,
        {
            "index": index,
            "label": label,
            "status": "ok",
            "source_kind": source_kind,
            "source_result_path": source_result_path,
            "draft_mode": draft_mode,
            "image_strategy": image_strategy,
            "source_payload": source_payload,
            **metrics,
        },
    )


def build_candidate_error_result(request: dict[str, Any], candidate: dict[str, Any], index: int, error: Exception) -> dict[str, Any]:
    label = clean_text(candidate.get("label") or candidate.get("topic")) or f"candidate-{index:02d}"
    draft_mode = clean_text(candidate.get("draft_mode")) or clean_text(request.get("default_draft_mode")) or "balanced"
    image_strategy = clean_text(candidate.get("image_strategy")) or clean_text(request.get("default_image_strategy")) or "mixed"
    message = clean_text(error) or error.__class__.__name__
    return {
        "index": index,
        "label": label,
        "status": "error",
        "error_message": message,
        "source_kind": "error",
        "source_result_path": "",
        "draft_mode": draft_mode,
        "image_strategy": image_strategy,
        "priority_score": -1,
        "local_image_count": 0,
        "remote_image_count": 0,
        "blocked_source_count": 0,
        "source_count": 0,
        "top_signal_score": 0,
        "confidence_width": 100,
        "reason_summary": f"Candidate failed during ranking: {message}",
    }


def build_ranked_candidates(request: dict[str, Any]) -> list[dict[str, Any]]:
    ranked_by_index: dict[int, dict[str, Any]] = {}
    candidate_by_index = {index: safe_dict(candidate) for index, candidate in enumerate(request["candidates"], start=1)}
    serial_mode = request.get("max_parallel_candidates", 1) <= 1 or len(request["candidates"]) <= 1
    if serial_mode:
        for index, candidate in candidate_by_index.items():
            try:
                _, result_item = rank_single_candidate(request, candidate, index, request["output_dir"])
            except Exception as exc:
                result_item = build_candidate_error_result(request, candidate, index, exc)
            ranked_by_index[index] = result_item
    else:
        with ThreadPoolExecutor(max_workers=request["max_parallel_candidates"]) as executor:
            future_map = {
                executor.submit(rank_single_candidate, request, candidate, index, request["output_dir"]): index
                for index, candidate in candidate_by_index.items()
            }
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    _, result_item = future.result()
                except Exception as exc:
                    result_item = build_candidate_error_result(request, candidate_by_index[index], index, exc)
                ranked_by_index[index] = result_item
    ranked = [ranked_by_index[index] for index in sorted(ranked_by_index)]
    ranked.sort(
        key=lambda item: (
            int(item.get("status") == "ok"),
            int(item.get("priority_score", 0)),
            int(item.get("local_image_count", 0)),
            int(item.get("source_count", 0)),
        ),
        reverse=True,
    )
    return ranked


def build_batch_request(request: dict[str, Any], ranked_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [item for item in ranked_candidates if item.get("status") == "ok"][: request["top_n"]]
    items = []
    for item in selected:
        items.append(
            {
                "candidate_index": item["index"],
                "label": item["label"],
                "payload": deepcopy(safe_dict(item.get("source_payload"))),
                "source_result_path": item["source_result_path"],
                "draft_mode": item["draft_mode"],
                "image_strategy": item["image_strategy"],
            }
        )
    batch_request = {
        "analysis_time": request["analysis_time"].isoformat(),
        "output_dir": str(request["output_dir"] / "batch"),
        "default_draft_mode": request.get("default_draft_mode"),
        "default_image_strategy": request.get("default_image_strategy"),
        "default_language_mode": request.get("default_language_mode"),
        "default_tone": request.get("default_tone"),
        "default_max_images": request.get("default_max_images"),
        "default_target_length_chars": request.get("default_target_length_chars"),
        "max_parallel_topics": request.get("max_parallel_topics", 1),
        "items": items,
    }
    return batch_request


def build_report(result: dict[str, Any]) -> str:
    lines = [
        "# Article Auto Queue",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Candidates scanned: {result.get('candidate_count', 0)}",
        f"- Selected for batch: {result.get('selected_count', 0)}",
        f"- Max parallel candidates: {result.get('max_parallel_candidates', 1)}",
        f"- Max parallel topics: {result.get('max_parallel_topics', 1)}",
        "",
        "## Ranking",
        "",
    ]
    for item in safe_list(result.get("ranked_candidates")):
        lines.extend(
            [
                f"### {clean_text(item.get('label'))}",
                "",
                f"- Selection: {clean_text(item.get('selection_status')) or 'n/a'}",
                f"- Priority score: {item.get('priority_score', 0)}",
                f"- Source kind: {clean_text(item.get('source_kind'))}",
                f"- Draft mode: {clean_text(item.get('draft_mode'))}",
                f"- Image strategy: {clean_text(item.get('image_strategy'))}",
                f"- Blocked sources: {item.get('blocked_source_count', 0)}",
                f"- Reason: {clean_text(item.get('reason_summary'))}",
                f"- Source result: {clean_text(item.get('source_result_path'))}",
                f"- Final quality gate: {clean_text(item.get('final_quality_gate')) or 'n/a'}",
                f"- Rewrite mode: {clean_text(item.get('final_rewrite_mode')) or 'n/a'}",
                "",
            ]
        )
    batch_report = clean_text(safe_dict(result.get("batch_result")).get("report_path"))
    if batch_report:
        lines.extend(["## Batch Queue", "", f"- Batch report: {batch_report}", ""])
    return "\n".join(lines).strip() + "\n"


def run_article_auto_queue(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)
    ranked_candidates = build_ranked_candidates(request)
    batch_request = build_batch_request(request, ranked_candidates)
    if batch_request["items"]:
        batch_result = run_article_batch_workflow(batch_request)
    else:
        batch_result = {
            "status": "skipped",
            "report_path": "",
            "items": [],
            "succeeded_items": 0,
            "failed_items": 0,
            "report_markdown": "No valid candidates were available for batch execution.\n",
        }
    selected_indexes = {
        int(item.get("candidate_index", 0) or 0)
        for item in batch_request["items"]
        if int(item.get("candidate_index", 0) or 0) > 0
    }
    batch_items_by_index = {
        int(item.get("candidate_index", 0) or 0): item
        for item in safe_list(batch_result.get("items"))
        if int(item.get("candidate_index", 0) or 0) > 0
    }
    enriched_candidates = []
    for item in ranked_candidates:
        batch_item = safe_dict(batch_items_by_index.get(int(item.get("index", 0) or 0)))
        if clean_text(item.get("status")) != "ok":
            selection_status = "error"
        elif int(item.get("index", 0) or 0) in selected_indexes:
            selection_status = "selected"
        else:
            selection_status = "skipped"
        enriched_candidates.append(
            {
                **{key: value for key, value in item.items() if key != "source_payload"},
                "selection_status": selection_status,
                "final_quality_gate": clean_text(batch_item.get("quality_gate")),
                "final_rewrite_mode": clean_text(batch_item.get("rewrite_mode")),
            }
        )
    batch_result_path = request["output_dir"] / "batch-result.json"
    write_json(batch_result_path, batch_result)
    result = {
        "status": "ok" if batch_request["items"] else "partial",
        "workflow_kind": "article_auto_queue",
        "analysis_time": request["analysis_time"].isoformat(),
        "candidate_count": len(ranked_candidates),
        "selected_count": len(batch_request["items"]),
        "max_parallel_candidates": request.get("max_parallel_candidates", 1),
        "max_parallel_topics": request.get("max_parallel_topics", 1),
        "ranked_candidates": enriched_candidates,
        "batch_request_path": str(request["output_dir"] / "batch-request.json"),
        "batch_result": {
            "status": clean_text(batch_result.get("status")),
            "report_path": clean_text(batch_result.get("report_path")),
            "result_path": str(batch_result_path),
            "succeeded_items": int(batch_result.get("succeeded_items", 0) or 0),
            "failed_items": int(batch_result.get("failed_items", 0) or 0),
        },
    }
    write_json(Path(result["batch_request_path"]), batch_request)
    result["report_markdown"] = build_report(result)
    report_path = request["output_dir"] / "auto-queue-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


__all__ = ["load_json", "run_article_auto_queue", "write_json"]
