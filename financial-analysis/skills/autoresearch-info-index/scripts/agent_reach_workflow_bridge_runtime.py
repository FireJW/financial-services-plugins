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


def build_agent_reach_bridge_payload(request: dict[str, Any], *, default_use_case: str) -> dict[str, Any]:
    payload = safe_dict(request.get("payload"))
    agent_reach_config = safe_dict(request.get("agent_reach_config"))
    bridge_payload: dict[str, Any] = {
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
    }
    for key in (
        "pseudo_home",
        "channels",
        "timeout_per_channel",
        "max_results_per_channel",
        "dedupe_window_hours",
        "dedupe_store_path",
        "rss_feeds",
        "channel_payloads",
        "channel_result_paths",
        "channel_commands",
    ):
        value = agent_reach_config.get(key)
        if value not in (None, "", [], {}):
            bridge_payload[key] = deepcopy(value)
    return bridge_payload


def merge_news_payload_with_agent_reach_candidates(payload: dict[str, Any], bridge_result: dict[str, Any]) -> dict[str, Any]:
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


def summarize_agent_reach_stage(bridge_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": True,
        "bridge_result": bridge_result,
        "channels_attempted": deepcopy(safe_list(bridge_result.get("channels_attempted"))),
        "channels_succeeded": deepcopy(safe_list(bridge_result.get("channels_succeeded"))),
        "channels_failed": deepcopy(safe_list(bridge_result.get("channels_failed"))),
        "imported_candidate_count": int(bridge_result.get("observations_imported", 0) or 0),
    }


__all__ = [
    "build_agent_reach_bridge_payload",
    "merge_news_payload_with_agent_reach_candidates",
    "summarize_agent_reach_stage",
]
