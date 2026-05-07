#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import subprocess
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from news_index_runtime import (
    isoformat_or_blank,
    load_json,
    parse_datetime,
    run_news_index,
    short_excerpt,
    slugify,
    write_json,
)


COLLECTION_KEYS = (
    "items",
    "results",
    "news",
    "articles",
    "filtered_items",
    "enriched_items",
    "raw_items",
    "scored_items",
    "entries",
    "records",
    "data",
)
RESULT_PATH_KEYS = ("horizon_result_path", "result_path", "file", "path", "artifact")
NESTED_RESULT_KEYS = ("horizon", "horizon_result", "source_result", "result")
TITLE_KEYS = ("title", "headline", "name", "topic", "keyword", "question")
URL_KEYS = ("url", "link", "href", "source_url", "article_url", "final_url")
TEXT_KEYS = (
    "summary",
    "ai_summary",
    "description",
    "abstract",
    "content",
    "text",
    "body",
    "excerpt",
    "snippet",
    "digest",
    "why_relevant",
)
SOURCE_KEYS = ("source", "source_name", "site", "feed", "feed_name", "outlet", "publisher")
PLATFORM_KEYS = ("platform", "source_type", "channel", "category", "network")
PUBLISHED_AT_KEYS = (
    "published_at",
    "published_time",
    "publish_time",
    "pub_date",
    "pubDate",
    "created_at",
    "created",
    "time",
    "timestamp",
    "date",
)
OBSERVED_AT_KEYS = (
    "observed_at",
    "fetched_at",
    "collected_at",
    "crawled_at",
    "captured_at",
    "updated_at",
    "last_seen",
    "last_seen_at",
)
SCORE_KEYS = ("score", "ai_score", "importance_score", "rank_score")
HEAT_KEYS = ("heat", "hot", "hot_value", "heat_score", "hot_score", "popularity")
RANK_KEYS = ("rank", "position", "order", "index")
TAG_KEYS = ("tags", "ai_tags", "keywords", "categories")
SOCIAL_PLATFORM_HINTS = {
    "hackernews",
    "hacker_news",
    "hn",
    "reddit",
    "telegram",
    "twitter",
    "x",
    "github",
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def normalize_key(value: Any) -> str:
    return clean_text(value).lower().replace(" ", "_").replace("-", "_")


def clean_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    else:
        values = safe_list(value)
    cleaned: list[str] = []
    for item in values:
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def first_present_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not clean_text(value):
            continue
        return value
    return None


def looks_like_item(value: dict[str, Any]) -> bool:
    if any(key in value for key in COLLECTION_KEYS):
        return False
    return any(
        first_present_value(value, keys) is not None
        for keys in (TITLE_KEYS, URL_KEYS, TEXT_KEYS, SOURCE_KEYS, PLATFORM_KEYS)
    )


def flatten_result_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for entry in value:
            items.extend(flatten_result_items(entry))
        return items
    if not isinstance(value, dict):
        return []

    nested_items: list[dict[str, Any]] = []
    for key in COLLECTION_KEYS:
        if key in value:
            nested_items.extend(flatten_result_items(value.get(key)))
    if nested_items:
        return nested_items
    if looks_like_item(value):
        return [value]
    return []


def extract_first_json_value(text: str) -> Any:
    cleaned = text.lstrip("\ufeff\r\n\t ")
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        return payload
    raise ValueError("Could not locate a JSON value in Horizon command output")


def normalize_input_mode(raw_payload: dict[str, Any]) -> str:
    horizon = safe_dict(raw_payload.get("horizon"))
    requested = normalize_key(horizon.get("input_mode") or raw_payload.get("horizon_input_mode"))
    if requested in {"command", "inline_result", "inline_payload", "result_path"}:
        return "inline_result" if requested == "inline_payload" else requested
    if horizon.get("command") not in (None, "", [], {}) or raw_payload.get("horizon_command") not in (None, "", [], {}):
        return "command"
    if "result" in horizon:
        return "inline_result"
    if any(clean_text(horizon.get(key) or raw_payload.get(key)) for key in RESULT_PATH_KEYS):
        return "result_path"
    return ""


def normalize_command(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, str):
        return [clean_text(token) for token in shlex.split(value, posix=False) if clean_text(token)]
    return []


def run_horizon_command(raw_payload: dict[str, Any]) -> tuple[Any, str, str, dict[str, Any]]:
    horizon = safe_dict(raw_payload.get("horizon"))
    command = normalize_command(horizon.get("command") or raw_payload.get("horizon_command"))
    timeout_seconds = max(1, int(horizon.get("timeout_seconds") or raw_payload.get("horizon_timeout_seconds") or 30))
    workdir_text = clean_text(horizon.get("working_directory") or horizon.get("workdir") or raw_payload.get("horizon_workdir"))
    result_path_text = clean_text(horizon.get("result_path") or raw_payload.get("horizon_result_path"))
    working_directory = Path(workdir_text).expanduser().resolve() if workdir_text else None
    resolved_result_path = str(Path(result_path_text).expanduser().resolve()) if result_path_text else ""
    runner_summary = {
        "mode": "command",
        "status": "not_run",
        "reason": "",
        "command": command,
        "working_directory": str(working_directory) if working_directory else "",
        "timeout_seconds": timeout_seconds,
        "result_path": resolved_result_path,
        "exit_code": None,
        "timed_out": False,
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "payload_source": "",
        "live_execution": "opt_in_command_only",
    }
    if not command:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = "input_mode=command requires horizon.command"
        runner_summary["payload_source"] = "command_failed"
        return {}, "command_failed", resolved_result_path, runner_summary

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            cwd=str(working_directory) if working_directory else None,
        )
    except subprocess.TimeoutExpired as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = f"timeout after {timeout_seconds}s"
        runner_summary["timed_out"] = True
        runner_summary["stdout_excerpt"] = short_excerpt(clean_text(getattr(exc, "stdout", "") or ""), limit=240)
        runner_summary["stderr_excerpt"] = short_excerpt(clean_text(getattr(exc, "stderr", "") or ""), limit=240)
        runner_summary["payload_source"] = "command_failed"
        return {}, "command_failed", resolved_result_path, runner_summary
    except FileNotFoundError as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = clean_text(exc) or f"{command[0]} not installed"
        runner_summary["payload_source"] = "command_failed"
        return {}, "command_failed", resolved_result_path, runner_summary
    except OSError as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = clean_text(exc)
        runner_summary["payload_source"] = "command_failed"
        return {}, "command_failed", resolved_result_path, runner_summary

    runner_summary["exit_code"] = completed.returncode
    runner_summary["stdout_excerpt"] = short_excerpt(clean_text(completed.stdout), limit=240)
    runner_summary["stderr_excerpt"] = short_excerpt(clean_text(completed.stderr), limit=240)

    if completed.returncode != 0:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = clean_text(completed.stderr or completed.stdout or f"command exited {completed.returncode}")
        runner_summary["payload_source"] = "command_failed"
        return {}, "command_failed", resolved_result_path, runner_summary

    try:
        if resolved_result_path:
            payload = load_json(Path(resolved_result_path))
            runner_summary["status"] = "ok"
            runner_summary["payload_source"] = "command_result_path"
            return payload, "command_result_path", resolved_result_path, runner_summary
        payload = extract_first_json_value(completed.stdout)
        runner_summary["status"] = "ok"
        runner_summary["payload_source"] = "command_stdout"
        return payload, "command_stdout", "", runner_summary
    except Exception as exc:
        runner_summary["status"] = "parse_error"
        runner_summary["reason"] = clean_text(exc) or "command completed but payload could not be parsed"
        runner_summary["payload_source"] = "command_parse_error"
        return {}, "command_parse_error", resolved_result_path, runner_summary


def resolve_horizon_payload(raw_payload: dict[str, Any]) -> tuple[Any, str, str, dict[str, Any]]:
    horizon = safe_dict(raw_payload.get("horizon"))
    input_mode = normalize_input_mode(raw_payload)
    if input_mode == "command":
        return run_horizon_command(raw_payload)
    if "result" in horizon:
        return horizon.get("result"), "inline_result", "", {}
    for key in RESULT_PATH_KEYS:
        path_text = clean_text(horizon.get(key) or raw_payload.get(key))
        if path_text:
            resolved = Path(path_text).expanduser().resolve()
            return load_json(resolved), "result_path", str(resolved), {}
    for key in NESTED_RESULT_KEYS:
        nested = raw_payload.get(key)
        if isinstance(nested, dict) and any(collection_key in nested for collection_key in COLLECTION_KEYS):
            return nested, "inline_result", "", {}
    if any(key in raw_payload for key in COLLECTION_KEYS):
        return raw_payload, "inline_result", "", {}
    raise ValueError("Horizon bridge requires horizon.result, horizon.result_path, or horizon.input_mode=command")


def payload_metadata(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    data = safe_dict(payload.get("data"))
    return {
        "mcp_ok": payload.get("ok") if "ok" in payload else payload.get("success", ""),
        "mcp_tool": clean_text(payload.get("tool") or payload.get("tool_name")),
        "mcp_stage": clean_text(payload.get("stage") or data.get("stage")),
        "run_id": clean_text(payload.get("run_id") or data.get("run_id")),
        "artifact": clean_text(payload.get("artifact") or data.get("artifact")),
        "payload_summary": clean_text(payload.get("summary") or payload.get("message")),
    }


def normalize_source_label(item: dict[str, Any]) -> str:
    source = clean_text(first_present_value(item, SOURCE_KEYS))
    if source:
        return source
    platform = clean_text(first_present_value(item, PLATFORM_KEYS))
    if platform:
        return platform
    metadata = safe_dict(item.get("metadata"))
    metadata_source = clean_text(first_present_value(metadata, SOURCE_KEYS + PLATFORM_KEYS))
    return metadata_source or "unknown"


def normalize_platform(item: dict[str, Any], source_label: str) -> str:
    platform = clean_text(first_present_value(item, PLATFORM_KEYS))
    if platform:
        return normalize_key(platform)
    source_type = normalize_key(item.get("source_type"))
    if source_type:
        return source_type
    source_key = normalize_key(source_label)
    return source_key or "unknown"


def infer_source_type(item: dict[str, Any], platform: str) -> str:
    explicit = normalize_key(item.get("news_index_source_type") or item.get("source_family"))
    if explicit:
        return explicit
    item_source_type = normalize_key(item.get("source_type") or item.get("type"))
    if item_source_type and item_source_type not in SOCIAL_PLATFORM_HINTS:
        return item_source_type
    if any(hint in platform for hint in SOCIAL_PLATFORM_HINTS):
        return "social" if platform != "github" else "community"
    if "rss" in platform or "news" in platform or "feed" in platform:
        return "major_news"
    return "major_news"


def canonical_claim_ids(item: dict[str, Any], request: dict[str, Any]) -> list[str]:
    explicit = clean_string_list(item.get("claim_ids"))
    if explicit:
        return explicit
    request_claims = [
        clean_text(claim.get("claim_id"))
        for claim in safe_list(request.get("claims"))
        if isinstance(claim, dict) and clean_text(claim.get("claim_id"))
    ]
    return request_claims if len(request_claims) == 1 else []


def normalize_claim_states(item: dict[str, Any], claim_ids: list[str]) -> dict[str, str]:
    raw_states = safe_dict(item.get("claim_states") or item.get("stance_by_claim"))
    default_state = normalize_key(item.get("claim_state") or "support") or "support"
    if default_state not in {"support", "contradict", "unclear"}:
        default_state = "support"
    states: dict[str, str] = {}
    for claim_id in claim_ids:
        state = normalize_key(raw_states.get(claim_id) or default_state)
        states[claim_id] = state if state in {"support", "contradict", "unclear"} else default_state
    return states


def primary_text(item: dict[str, Any]) -> str:
    title = clean_text(first_present_value(item, TITLE_KEYS))
    body = clean_text(first_present_value(item, TEXT_KEYS))
    if title and body and title not in body:
        return short_excerpt(f"{title}. {body}", limit=240)
    return short_excerpt(body or title, limit=240)


def normalize_access_mode(value: Any, payload_source: str) -> str:
    mode = normalize_key(value)
    if mode in {"local_mcp", "external_artifact", "blocked"}:
        return mode
    if mode in {"artifact", "file", "saved_payload"}:
        return "external_artifact"
    return "external_artifact" if payload_source == "result_path" else "local_mcp"


def normalize_horizon_item(
    item: dict[str, Any],
    request: dict[str, Any],
    index: int,
) -> tuple[dict[str, Any] | None, str]:
    source_label = normalize_source_label(item)
    platform = normalize_platform(item, source_label)
    title = clean_text(first_present_value(item, TITLE_KEYS))
    url = clean_text(first_present_value(item, URL_KEYS))
    text_excerpt = primary_text(item)
    if not url and not text_excerpt:
        return None, "missing_url_and_text"

    claim_ids = canonical_claim_ids(item, request)
    source_policy = request["source_policy"]
    access_mode = normalize_access_mode(item.get("access_mode") or source_policy["access_mode"], request["payload_source"])
    published_at = parse_datetime(first_present_value(item, PUBLISHED_AT_KEYS), fallback=None)
    observed_at = parse_datetime(first_present_value(item, OBSERVED_AT_KEYS), fallback=request["analysis_time"])
    timestamp_fallback = ""
    if not published_at and source_policy["allow_observed_at_fallback"]:
        published_at = observed_at
        timestamp_fallback = "observed_at"

    tags = clean_string_list(first_present_value(item, TAG_KEYS))
    horizon_metadata = {
        **request["payload_metadata"],
        "payload_source": request["payload_source"],
        "source": source_label,
        "platform": platform,
        "title": title,
        "score": first_present_value(item, SCORE_KEYS),
        "heat": first_present_value(item, HEAT_KEYS),
        "rank": first_present_value(item, RANK_KEYS),
        "tags": tags,
        "ai_reason": clean_text(item.get("ai_reason") or item.get("reason")),
        "timestamp_fallback": timestamp_fallback,
        "score_policy": "discovery_heat_only_not_claim_confirmation",
    }

    candidate = {
        "source_id": clean_text(item.get("source_id") or item.get("id") or slugify(f"horizon-{source_label}-{title or url}-{index}", f"horizon-{index:02d}")),
        "source_name": f"horizon:{source_label}",
        "source_type": infer_source_type(item, platform),
        "origin": "horizon",
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": normalize_claim_states(item, claim_ids),
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "text_excerpt": text_excerpt,
        "channel": clean_text(item.get("channel") or source_policy["channel"]).lower() or "shadow",
        "access_mode": access_mode,
        "tags": tags,
        "artifact_manifest": [
            {
                "role": "horizon_source_url",
                "source_url": url,
                "path": "",
                "media_type": "",
                "summary": short_excerpt(text_excerpt, limit=180),
            }
        ]
        if url
        else [],
        "raw_metadata": {
            "horizon": horizon_metadata,
            "source_item": deepcopy(item),
        },
        "discovery_reason": clean_text(item.get("discovery_reason") or f"Imported from Horizon {source_label} discovery radar"),
    }
    if candidate["channel"] not in {"core", "shadow", "background"}:
        candidate["channel"] = "shadow"
    if access_mode == "blocked":
        candidate["channel"] = "background"
    return candidate, ""


def dedupe_key(candidate: dict[str, Any]) -> str:
    url = clean_text(candidate.get("url")).lower()
    if url:
        return f"url:{url}"
    return f"text:{clean_text(candidate.get('source_name')).lower()}:{clean_text(candidate.get('text_excerpt')).lower()}"


def build_import_summary(
    candidates: list[dict[str, Any]],
    *,
    raw_item_count: int,
    skipped_invalid: int,
    skipped_duplicates: int,
    payload_source: str,
    result_path: str,
) -> dict[str, Any]:
    access_mode_counts = Counter(str(item.get("access_mode", "")) for item in candidates)
    source_type_counts = Counter(str(item.get("source_type", "")) for item in candidates)
    channel_counts = Counter(str(item.get("channel", "")) for item in candidates)
    platform_counts = Counter(
        str(safe_dict(safe_dict(item.get("raw_metadata")).get("horizon")).get("platform", "unknown"))
        for item in candidates
    )
    score_count = sum(
        1
        for item in candidates
        if safe_dict(safe_dict(item.get("raw_metadata")).get("horizon")).get("score") not in (None, "")
    )
    ranked_count = sum(
        1
        for item in candidates
        if safe_dict(safe_dict(item.get("raw_metadata")).get("horizon")).get("rank") not in (None, "")
    )
    return {
        "payload_source": payload_source,
        "result_path": result_path,
        "raw_item_count": raw_item_count,
        "imported_candidate_count": len(candidates),
        "skipped_invalid_count": skipped_invalid,
        "skipped_duplicate_count": skipped_duplicates,
        "access_mode_counts": dict(access_mode_counts),
        "source_type_counts": dict(source_type_counts),
        "channel_counts": dict(channel_counts),
        "platform_counts": dict(platform_counts),
        "score_count": score_count,
        "ranked_count": ranked_count,
        "default_channel_policy": "shadow_or_background_only",
        "score_policy": "horizon_score_is_discovery_heat_not_claim_confirmation",
    }


def build_completion_check(result: dict[str, Any]) -> dict[str, Any]:
    summary = safe_dict(result.get("import_summary"))
    retrieval_result = safe_dict(result.get("retrieval_result"))
    observations = safe_list(retrieval_result.get("observations"))
    blockers: list[str] = []
    warnings: list[str] = []
    if not summary.get("imported_candidate_count"):
        blockers.append("No Horizon items were imported as news-index candidates.")
    if not observations:
        blockers.append("No bridged retrieval_result observations were produced.")
    if summary.get("score_count"):
        warnings.append("Horizon scores are preserved only as discovery heat, not claim confirmation.")
    warnings.append("Horizon imported items remain shadow evidence until native confirmation promotes them.")
    status = "blocked" if blockers else "ready"
    return {
        "contract_version": "horizon_bridge_completion_check/v1",
        "target": "horizon-bridge",
        "status": status,
        "recommendation": "Proceed to native confirmation review." if status == "ready" else "Do not proceed until bridge output is complete.",
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "imported_candidate_count": int(summary.get("imported_candidate_count", 0) or 0),
            "observation_count": len(observations),
            "default_channel_policy": summary.get("default_channel_policy", ""),
            "score_policy": summary.get("score_policy", ""),
        },
    }


def build_operator_summary(result: dict[str, Any]) -> dict[str, Any]:
    completion_check = safe_dict(result.get("completion_check"))
    summary = safe_dict(result.get("import_summary"))
    status = "ready" if completion_check.get("status") == "ready" else "blocked"
    return {
        "contract_version": "horizon_bridge_operator_summary/v1",
        "target": "horizon-bridge",
        "operator_status": status,
        "operator_recommendation": (
            "Use Horizon as an upstream radar only; confirm claims through news-index, completion-check, and publication gates."
            if status == "ready"
            else "Fix Horizon bridge blockers before downstream use."
        ),
        "bridge_summary": {
            "origin": "horizon",
            "payload_source": summary.get("payload_source", ""),
            "imported_candidate_count": int(summary.get("imported_candidate_count", 0) or 0),
            "channel_counts": deepcopy(summary.get("channel_counts", {})),
            "access_mode_counts": deepcopy(summary.get("access_mode_counts", {})),
            "score_policy": summary.get("score_policy", ""),
        },
        "completion_check": deepcopy(completion_check),
    }


def build_completion_check_markdown(check: dict[str, Any]) -> str:
    lines = [
        "# Horizon Bridge Completion Check",
        "",
        f"Status: {check.get('status', '')}",
        f"Recommendation: {check.get('recommendation', '')}",
        "",
        "## Blockers",
    ]
    lines.extend([f"- {item}" for item in safe_list(check.get("blockers"))] or ["- None"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in safe_list(check.get("warnings"))] or ["- None"])
    return "\n".join(lines).strip() + "\n"


def build_operator_summary_markdown(summary: dict[str, Any]) -> str:
    bridge = safe_dict(summary.get("bridge_summary"))
    lines = [
        "# Horizon Bridge Operator Summary",
        "",
        f"Status: {summary.get('operator_status', '')}",
        f"Recommendation: {summary.get('operator_recommendation', '')}",
        "",
        "## Bridge Summary",
        f"- Origin: {bridge.get('origin', '')}",
        f"- Payload source: {bridge.get('payload_source', '')}",
        f"- Imported candidates: {bridge.get('imported_candidate_count', 0)}",
        f"- Channels: {json.dumps(bridge.get('channel_counts', {}), ensure_ascii=False)}",
        f"- Access modes: {json.dumps(bridge.get('access_mode_counts', {}), ensure_ascii=False)}",
        f"- Score policy: {bridge.get('score_policy', '')}",
    ]
    return "\n".join(lines).strip() + "\n"


def attach_companion_checks(result: dict[str, Any]) -> dict[str, Any]:
    result["completion_check"] = build_completion_check(result)
    result["operator_summary"] = build_operator_summary(result)
    result["completion_check_markdown"] = build_completion_check_markdown(result["completion_check"])
    result["operator_summary_markdown"] = build_operator_summary_markdown(result["operator_summary"])
    return result


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    summary = safe_dict(result.get("import_summary"))
    lines = [
        f"# Horizon Bridge Report: {request.get('topic', 'horizon-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
        f"Payload source: {summary.get('payload_source', '') or 'unknown'}",
        f"Result path: {summary.get('result_path', '') or 'inline'}",
        f"Imported / invalid / duplicate: {summary.get('imported_candidate_count', 0)} / {summary.get('skipped_invalid_count', 0)} / {summary.get('skipped_duplicate_count', 0)}",
        f"Access modes: {summary.get('access_mode_counts', {})}",
        f"Platforms: {summary.get('platform_counts', {})}",
        f"Score policy: {summary.get('score_policy', '')}",
        "",
        "## Imported Candidates",
    ]
    candidates = safe_list(safe_dict(result.get("retrieval_request")).get("candidates"))
    if not candidates:
        lines.append("- None")
    for item in candidates:
        horizon = safe_dict(safe_dict(item.get("raw_metadata")).get("horizon"))
        lines.append(
            f"- {item.get('source_name', '')} | {item.get('source_type', '')} | {item.get('channel', '')} | "
            f"rank {horizon.get('rank', '') or 'n/a'} | score {horizon.get('score', '') or 'n/a'} | {item.get('text_excerpt', '')}"
        )
        if item.get("url"):
            lines.append(f"  URL: {item.get('url')}")

    retrieval_result = safe_dict(result.get("retrieval_result"))
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    horizon = safe_dict(raw_payload.get("horizon"))
    horizon_payload, payload_source, result_path, runner_summary = resolve_horizon_payload(raw_payload)
    analysis_time = parse_datetime(raw_payload.get("analysis_time") or horizon.get("analysis_time"), fallback=now_utc()) or now_utc()
    source_policy = {
        "channel": clean_text(horizon.get("channel") or raw_payload.get("channel") or "shadow").lower(),
        "access_mode": normalize_access_mode(horizon.get("access_mode") or raw_payload.get("access_mode"), payload_source),
        "allow_observed_at_fallback": bool(horizon.get("allow_observed_at_fallback", True)),
    }
    if source_policy["channel"] not in {"core", "shadow", "background"}:
        source_policy["channel"] = "shadow"
    return {
        "topic": clean_text(raw_payload.get("topic") or "Horizon bridge"),
        "analysis_time": analysis_time,
        "questions": clean_string_list(raw_payload.get("questions")),
        "use_case": clean_text(raw_payload.get("use_case") or "horizon-bridge"),
        "source_preferences": clean_string_list(raw_payload.get("source_preferences")),
        "mode": clean_text(raw_payload.get("mode") or "generic"),
        "windows": clean_string_list(raw_payload.get("windows")),
        "claims": [item for item in safe_list(raw_payload.get("claims")) if isinstance(item, dict)],
        "market_relevance": clean_string_list(raw_payload.get("market_relevance")),
        "market_relevance_zh": clean_string_list(raw_payload.get("market_relevance_zh")),
        "expected_source_families": clean_string_list(raw_payload.get("expected_source_families")),
        "max_parallel_candidates": max(1, int(raw_payload.get("max_parallel_candidates", 1) or 1)),
        "source_policy": source_policy,
        "payload": horizon_payload,
        "payload_source": payload_source,
        "result_path": result_path,
        "payload_metadata": payload_metadata(horizon_payload),
        "input_mode": normalize_input_mode(raw_payload) or "auto",
        "runner_summary": runner_summary,
    }


def prepare_horizon_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    raw_items = flatten_result_items(request["payload"])
    candidates: list[dict[str, Any]] = []
    skipped_invalid = 0
    skipped_duplicates = 0
    seen: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        candidate, _skip_reason = normalize_horizon_item(item, request, index)
        if not candidate:
            skipped_invalid += 1
            continue
        key = dedupe_key(candidate)
        if key in seen:
            skipped_duplicates += 1
            continue
        seen.add(key)
        candidates.append(candidate)

    retrieval_request = {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": request["questions"],
        "use_case": request["use_case"],
        "source_preferences": request["source_preferences"],
        "mode": request["mode"],
        "windows": request["windows"],
        "claims": deepcopy(request["claims"]),
        "candidates": candidates,
        "market_relevance": request["market_relevance"],
        "market_relevance_zh": request["market_relevance_zh"],
        "expected_source_families": request["expected_source_families"],
        "max_parallel_candidates": request["max_parallel_candidates"],
    }
    result = {
        "status": "ok" if candidates else "failed",
        "workflow_kind": "horizon_bridge",
        "request": {
            **{key: value for key, value in request.items() if key not in {"payload", "analysis_time"}},
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
        },
        "retrieval_request": retrieval_request,
        "import_summary": build_import_summary(
            candidates,
            raw_item_count=len(raw_items),
            skipped_invalid=skipped_invalid,
            skipped_duplicates=skipped_duplicates,
            payload_source=request["payload_source"],
            result_path=request["result_path"],
        ),
        "runner_summary": request["runner_summary"]
        or {
            "mode": "horizon-bridge",
            "payload_source": request["payload_source"],
            "result_path": request["result_path"],
            "live_execution": "saved_payload_only",
        },
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


def run_horizon_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    result = prepare_horizon_bridge(raw_payload)
    result["retrieval_result"] = run_news_index(result["retrieval_request"])
    attach_companion_checks(result)
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "attach_companion_checks",
    "build_completion_check",
    "build_markdown_report",
    "build_operator_summary",
    "flatten_result_items",
    "load_json",
    "normalize_request",
    "prepare_horizon_bridge",
    "resolve_horizon_payload",
    "run_horizon_bridge",
    "write_json",
]
