#!/usr/bin/env python3
"""
Compatibility layer for the recency-first news index runtime.
"""

from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from typing import Any

from news_index_runtime import (
    build_markdown_report as _build_markdown_report,
    load_json,
    merge_refresh,
    run_news_index as _run_news_index,
    write_json,
)
from news_index_to_run_record import build_run_record


def read_json(path: str | Path) -> dict[str, Any]:
    return load_json(Path(path))


def _adapt_result(result: dict[str, Any], *, refresh: bool = False) -> dict[str, Any]:
    adapted = deepcopy(result)
    adapted["_runtime_result"] = deepcopy(result)
    adapted["retrieval_request"] = adapted.get("request", {})
    adapted["source_observations"] = adapted.get("observations", [])
    verdict = deepcopy(adapted.get("verdict_output", {}))
    verdict["confirmed"] = [item.get("claim_text", "") for item in verdict.get("confirmed", []) if item.get("claim_text")]
    verdict["not_confirmed"] = [item.get("claim_text", "") for item in verdict.get("not_confirmed", []) if item.get("claim_text")]
    verdict["inference_only"] = [item.get("claim_text", "") for item in verdict.get("inference_only", []) if item.get("claim_text")]
    adapted["verdict_output"] = verdict
    if adapted.get("request", {}).get("mode") == "crisis":
        adapted["crisis_mode"] = True
    if refresh:
        adapted["refresh_context"] = {"mode": "refresh", **adapted.get("refresh_summary", {})}
    return adapted


def run_news_index(payload: dict[str, Any]) -> dict[str, Any]:
    return _adapt_result(_run_news_index(payload))


def refresh_news_index(existing_result: dict[str, Any], refresh_payload: dict[str, Any]) -> dict[str, Any]:
    base = existing_result
    if "request" not in base and "retrieval_request" in base:
        base = deepcopy(base)
        base["request"] = base.get("retrieval_request", {})
        base["observations"] = base.get("source_observations", [])
    return _adapt_result(merge_refresh(base, refresh_payload), refresh=True)


def result_to_run_record(result: dict[str, Any]) -> dict[str, Any]:
    base = result
    if "request" not in base and "retrieval_request" in base:
        base = deepcopy(base)
        base["request"] = base.get("retrieval_request", {})
        base["observations"] = base.get("source_observations", [])
    args = Namespace(
        task_id=None,
        sample_set_version="info-index-news-index-v1",
        baseline_version="baseline-v1",
        candidate_version="candidate-news-index-v1",
        last_stable_version="baseline-v1",
        baseline_factor=0.6,
    )
    return build_run_record(base, args)


def build_markdown_report(result: dict[str, Any]) -> str:
    base = result.get("_runtime_result") if isinstance(result, dict) else None
    if isinstance(base, dict):
        return _build_markdown_report(base)
    return _build_markdown_report(result)


__all__ = [
    "build_markdown_report",
    "read_json",
    "refresh_news_index",
    "result_to_run_record",
    "run_news_index",
    "write_json",
]
