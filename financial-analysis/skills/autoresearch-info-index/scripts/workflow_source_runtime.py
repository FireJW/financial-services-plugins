#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


JsonWriter = Callable[[Path, dict[str, Any]], None]
BridgePayloadBuilder = Callable[..., dict[str, Any]]
BridgePayloadMerger = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
BridgeStageSummarizer = Callable[..., dict[str, Any]]
BridgeRunner = Callable[[dict[str, Any]], dict[str, Any]]


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _write_stage_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(clean_text(payload.get("report_markdown")), encoding="utf-8-sig")


def _write_bridge_stage_outputs(
    output_dir: Path,
    stage: dict[str, Any],
    *,
    result_name: str,
    report_name: str,
    write_json: JsonWriter,
) -> dict[str, Any]:
    stage_payload = deepcopy(safe_dict(stage))
    if not stage_payload:
        return {}

    bridge_result = safe_dict(stage_payload.get("bridge_result"))
    result_path = output_dir / result_name
    report_path = output_dir / report_name
    write_json(result_path, bridge_result)
    _write_stage_report(report_path, bridge_result)
    stage_payload["result_path"] = str(result_path)
    stage_payload["report_path"] = str(report_path)
    return stage_payload


def write_source_stage_outputs(
    output_dir: Path,
    *,
    source_kind: str,
    source_payload: dict[str, Any],
    agent_reach_stage: dict[str, Any],
    opencli_stage: dict[str, Any],
    write_json: JsonWriter,
) -> dict[str, Any]:
    source_result_path = output_dir / "source-result.json"
    source_report_path = output_dir / "source-report.md"
    source_payload_copy = deepcopy(safe_dict(source_payload))
    write_json(source_result_path, source_payload_copy)
    _write_stage_report(source_report_path, source_payload_copy)
    return {
        "source_kind": clean_text(source_kind),
        "result_path": str(source_result_path),
        "report_path": str(source_report_path),
        "agent_reach_stage": _write_bridge_stage_outputs(
            output_dir,
            agent_reach_stage,
            result_name="agent-reach-bridge-result.json",
            report_name="agent-reach-bridge-report.md",
            write_json=write_json,
        ),
        "opencli_stage": _write_bridge_stage_outputs(
            output_dir,
            opencli_stage,
            result_name="opencli-bridge-result.json",
            report_name="opencli-bridge-report.md",
            write_json=write_json,
        ),
    }


def resolve_indexed_source_kind(source_payload: dict[str, Any]) -> str:
    payload = safe_dict(source_payload)
    if safe_list(payload.get("x_posts")) or safe_dict(payload.get("evidence_pack")):
        return "x_index"
    return "news_index"


def augment_news_payload_with_workflow_sources(
    request: dict[str, Any],
    *,
    default_agent_reach_use_case: str,
    default_opencli_use_case: str,
    run_agent_reach_bridge: BridgeRunner,
    build_agent_reach_bridge_payload: BridgePayloadBuilder,
    merge_news_payload_with_agent_reach_candidates: BridgePayloadMerger,
    summarize_agent_reach_stage: BridgeStageSummarizer,
    prepare_opencli_bridge: BridgeRunner,
    build_opencli_bridge_payload: BridgePayloadBuilder,
    merge_news_payload_with_opencli_candidates: BridgePayloadMerger,
    summarize_opencli_stage: BridgeStageSummarizer,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    merged_payload = deepcopy(safe_dict(request.get("payload")))
    agent_reach_stage: dict[str, Any] = {}
    opencli_stage: dict[str, Any] = {}
    if request.get("agent_reach_enabled"):
        bridge_result = run_agent_reach_bridge(
            build_agent_reach_bridge_payload(request, default_use_case=default_agent_reach_use_case)
        )
        merged_payload = merge_news_payload_with_agent_reach_candidates(merged_payload, bridge_result)
        agent_reach_stage = summarize_agent_reach_stage(bridge_result)
    if request.get("opencli_enabled"):
        try:
            bridge_result = prepare_opencli_bridge(
                build_opencli_bridge_payload(request, default_use_case=default_opencli_use_case)
            )
            merged_payload = merge_news_payload_with_opencli_candidates(merged_payload, bridge_result)
            opencli_stage = summarize_opencli_stage(bridge_result, required=bool(request.get("opencli_required")))
        except Exception as exc:
            opencli_stage = summarize_opencli_stage(
                {},
                required=bool(request.get("opencli_required")),
                status="error",
                error=str(exc),
            )
            if request.get("opencli_required"):
                raise
    return merged_payload, agent_reach_stage, opencli_stage


def build_source_stage_file_lines(
    source_stage: dict[str, Any],
    *,
    include_source_report: bool,
    include_bridge_reports: bool,
) -> list[str]:
    source_stage_payload = safe_dict(source_stage)
    agent_reach_stage = safe_dict(source_stage_payload.get("agent_reach_stage"))
    opencli_stage = safe_dict(source_stage_payload.get("opencli_stage"))
    lines = [f"- Source result: {clean_text(source_stage_payload.get('result_path')) or 'not written'}"]
    if include_source_report:
        lines.append(f"- Source report: {clean_text(source_stage_payload.get('report_path')) or 'not written'}")
    lines.append(f"- Agent Reach bridge result: {clean_text(agent_reach_stage.get('result_path')) or 'not used'}")
    if include_bridge_reports:
        lines.append(f"- Agent Reach bridge report: {clean_text(agent_reach_stage.get('report_path')) or 'not used'}")
    lines.append(f"- OpenCLI bridge result: {clean_text(opencli_stage.get('result_path')) or 'not used'}")
    if include_bridge_reports:
        lines.append(f"- OpenCLI bridge report: {clean_text(opencli_stage.get('report_path')) or 'not used'}")
    return lines


def build_agent_reach_augmentation_lines(agent_reach_stage: dict[str, Any]) -> list[str]:
    stage = safe_dict(agent_reach_stage)
    if not stage:
        return []

    lines = [
        "",
        "## Agent Reach Augmentation",
        "",
        f"- Channels attempted: {', '.join(safe_list(stage.get('channels_attempted'))) or 'none'}",
        f"- Channels succeeded: {', '.join(safe_list(stage.get('channels_succeeded'))) or 'none'}",
        f"- Imported shadow candidates: {int(stage.get('imported_candidate_count', 0) or 0)}",
    ]
    for item in safe_list(stage.get("channels_failed")):
        failure = safe_dict(item)
        lines.append(f"- Channel failure: {clean_text(failure.get('channel'))} | {clean_text(failure.get('reason'))}")
    return lines


def build_opencli_augmentation_lines(opencli_stage: dict[str, Any]) -> list[str]:
    stage = safe_dict(opencli_stage)
    if not stage:
        return []

    lines = [
        "",
        "## OpenCLI Augmentation",
        "",
        f"- Status: {clean_text(stage.get('status')) or 'unknown'}",
        f"- Required: {'yes' if stage.get('required') else 'no'}",
        f"- Payload source: {clean_text(stage.get('payload_source')) or 'none'}",
        f"- Runner status: {clean_text(stage.get('runner_status')) or 'none'}",
        f"- Imported shadow candidates: {int(stage.get('imported_candidate_count', 0) or 0)}",
    ]
    if clean_text(stage.get("error")):
        lines.append(f"- Error: {clean_text(stage.get('error'))}")
    return lines


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


def resolve_agent_reach_enabled(payload: dict[str, Any], agent_reach_config: dict[str, Any]) -> bool:
    if "use_agent_reach" in payload:
        return bool(payload.get("use_agent_reach"))
    if "enabled" in agent_reach_config:
        return bool(agent_reach_config.get("enabled"))
    return bool(agent_reach_config)


def resolve_opencli_enabled(payload: dict[str, Any], opencli_config: dict[str, Any]) -> bool:
    if "use_opencli" in payload:
        return bool(payload.get("use_opencli"))
    if "enabled" in opencli_config:
        return bool(opencli_config.get("enabled"))
    return bool(opencli_config)


def resolve_opencli_required(payload: dict[str, Any], opencli_config: dict[str, Any]) -> bool:
    if "require_opencli" in payload:
        return bool(payload.get("require_opencli"))
    return bool(opencli_config.get("required"))


def resolve_news_source_kind(*, agent_reach_stage: dict[str, Any], opencli_stage: dict[str, Any]) -> str:
    if agent_reach_stage and opencli_stage:
        return "news_index_agent_reach_opencli"
    if agent_reach_stage:
        return "news_index_agent_reach"
    if opencli_stage:
        return "news_index_opencli"
    return "news_index"


__all__ = [
    "augment_news_payload_with_workflow_sources",
    "build_agent_reach_augmentation_lines",
    "build_opencli_augmentation_lines",
    "build_source_stage_file_lines",
    "clean_text",
    "detect_payload_kind",
    "resolve_agent_reach_enabled",
    "resolve_indexed_source_kind",
    "resolve_opencli_enabled",
    "resolve_opencli_required",
    "resolve_news_source_kind",
    "safe_dict",
    "safe_list",
    "write_source_stage_outputs",
]
