#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

from news_index_runtime import isoformat_or_blank


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_opencli_bridge_payload(request: dict[str, Any], *, default_use_case: str) -> dict[str, Any]:
    payload = safe_dict(request.get("payload"))
    opencli_config = deepcopy(safe_dict(request.get("opencli_config")))
    opencli_config.pop("enabled", None)
    opencli_config.pop("required", None)
    return {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": deepcopy(safe_list(payload.get("questions"))),
        "use_case": clean_text(payload.get("use_case")) or default_use_case,
        "source_preferences": deepcopy(safe_list(payload.get("source_preferences"))),
        "mode": clean_text(payload.get("mode")) or "generic",
        "windows": deepcopy(safe_list(payload.get("windows"))),
        "claims": deepcopy(safe_list(payload.get("claims"))),
        "market_relevance": deepcopy(safe_list(payload.get("market_relevance"))),
        "expected_source_families": deepcopy(safe_list(payload.get("expected_source_families"))),
        "opencli": opencli_config,
    }


def merge_news_payload_with_opencli_candidates(payload: dict[str, Any], bridge_result: dict[str, Any]) -> dict[str, Any]:
    merged_payload = deepcopy(payload)
    imported_candidates = [
        deepcopy(item)
        for item in safe_list(safe_dict(bridge_result.get("retrieval_request")).get("candidates"))
        if isinstance(item, dict)
    ]
    existing_candidates = [
        deepcopy(item)
        for item in safe_list(merged_payload.get("candidates") or merged_payload.get("source_candidates"))
        if isinstance(item, dict)
    ]
    merged_payload["candidates"] = existing_candidates + imported_candidates
    return merged_payload


def summarize_opencli_stage(bridge_result: dict[str, Any], *, required: bool, status: str = "ok", error: str = "") -> dict[str, Any]:
    import_summary = safe_dict(bridge_result.get("import_summary"))
    runner_summary = safe_dict(bridge_result.get("runner_summary"))
    return {
        "enabled": True,
        "required": required,
        "status": status,
        "error": clean_text(error),
        "bridge_result": bridge_result,
        "payload_source": clean_text(import_summary.get("payload_source")),
        "imported_candidate_count": int(import_summary.get("imported_candidate_count", 0) or 0),
        "runner_status": clean_text(runner_summary.get("status")),
    }


__all__ = [
    "build_opencli_bridge_payload",
    "merge_news_payload_with_opencli_candidates",
    "summarize_opencli_stage",
]
