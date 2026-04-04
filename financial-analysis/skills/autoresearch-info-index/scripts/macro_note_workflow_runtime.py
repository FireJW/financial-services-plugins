#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from agent_reach_bridge_runtime import run_agent_reach_bridge
from agent_reach_workflow_bridge_runtime import (
    build_agent_reach_bridge_payload,
    merge_news_payload_with_agent_reach_candidates,
    summarize_agent_reach_stage,
)
from article_brief_runtime import build_analysis_brief, build_reddit_operator_review_manual_state, clean_text, load_json, safe_dict, safe_list, write_json
from opencli_bridge_runtime import prepare_opencli_bridge
from opencli_workflow_bridge_runtime import (
    build_opencli_bridge_payload,
    merge_news_payload_with_opencli_candidates,
    summarize_opencli_stage,
)
from news_index_runtime import isoformat_or_blank, now_utc, parse_datetime, run_news_index, slugify
from runtime_paths import runtime_subdir
from workflow_publication_gate_runtime import build_workflow_publication_gate
from workflow_source_runtime import (
    augment_news_payload_with_workflow_sources,
    build_agent_reach_augmentation_lines,
    build_opencli_augmentation_lines,
    build_source_stage_file_lines,
    detect_payload_kind,
    resolve_agent_reach_enabled,
    resolve_indexed_source_kind,
    resolve_news_source_kind,
    resolve_opencli_enabled,
    resolve_opencli_required,
    write_source_stage_outputs,
)
from x_index_runtime import run_x_index


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
        analysis_time = now_utc()

    topic = (
        clean_text(payload.get("topic"))
        or clean_text(source_request.get("topic"))
        or clean_text(retrieval_request.get("topic"))
        or clean_text(runtime_request.get("topic"))
        or "macro-note-topic"
    )
    output_dir = (
        Path(clean_text(payload.get("output_dir"))).expanduser().resolve()
        if clean_text(payload.get("output_dir"))
        else runtime_subdir("macro-note-workflow", slugify(topic, "macro-note-topic"), analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    agent_reach_config = safe_dict(payload.get("agent_reach"))
    opencli_config = safe_dict(payload.get("opencli_config") or payload.get("opencli"))
    return {
        "payload_kind": payload_kind,
        "topic": topic,
        "analysis_time": analysis_time,
        "agent_reach_enabled": resolve_agent_reach_enabled(payload, agent_reach_config),
        "agent_reach_config": agent_reach_config,
        "opencli_enabled": resolve_opencli_enabled(payload, opencli_config),
        "opencli_required": resolve_opencli_required(payload, opencli_config),
        "opencli_config": opencli_config,
        "source_result": source_payload,
        "source_result_path": source_result_path,
        "payload": payload,
        "output_dir": output_dir,
    }
def prepare_source_payload(request: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    payload_kind = request["payload_kind"]
    source_payload = request["source_result"]
    agent_reach_stage: dict[str, Any] = {}
    opencli_stage: dict[str, Any] = {}
    if payload_kind == "x_request":
        x_payload = deepcopy(request["payload"])
        x_payload["output_dir"] = clean_text(x_payload.get("x_output_dir") or x_payload.get("source_output_dir")) or str(
            (request["output_dir"] / "source-stage").resolve()
        )
        return run_x_index(x_payload), "x_index", agent_reach_stage, opencli_stage
    if payload_kind == "news_request":
        merged_payload, agent_reach_stage, opencli_stage = augment_news_payload_with_workflow_sources(
            request,
            default_agent_reach_use_case="macro-note-workflow-agent-reach",
            default_opencli_use_case="macro-note-workflow-opencli",
            run_agent_reach_bridge=run_agent_reach_bridge,
            build_agent_reach_bridge_payload=build_agent_reach_bridge_payload,
            merge_news_payload_with_agent_reach_candidates=merge_news_payload_with_agent_reach_candidates,
            summarize_agent_reach_stage=summarize_agent_reach_stage,
            prepare_opencli_bridge=prepare_opencli_bridge,
            build_opencli_bridge_payload=build_opencli_bridge_payload,
            merge_news_payload_with_opencli_candidates=merge_news_payload_with_opencli_candidates,
            summarize_opencli_stage=summarize_opencli_stage,
        )
        return run_news_index(merged_payload), resolve_news_source_kind(agent_reach_stage=agent_reach_stage, opencli_stage=opencli_stage), agent_reach_stage, opencli_stage
    if source_payload:
        return source_payload, resolve_indexed_source_kind(source_payload), agent_reach_stage, opencli_stage
    raise ValueError("macro-note-workflow could not resolve a source payload")


def build_brief_payload(request: dict[str, Any], source_result: dict[str, Any], staged_source_result_path: str) -> dict[str, Any]:
    return {
        "source_result": source_result,
        "source_result_path": staged_source_result_path or request.get("source_result_path"),
        "topic": request.get("topic"),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
    }


def build_macro_note_result(
    request: dict[str, Any],
    source_result: dict[str, Any],
    brief_result: dict[str, Any],
    staged_source_result_path: str,
) -> dict[str, Any]:
    source_summary = safe_dict(brief_result.get("source_summary"))
    manual_review = build_reddit_operator_review_manual_state(source_summary)
    workflow_publication_gate = build_workflow_publication_gate(
        {
            "manual_review": manual_review,
            "publication_readiness": clean_text(manual_review.get("publication_readiness")) or "ready",
        }
    )
    analysis_brief = safe_dict(brief_result.get("analysis_brief"))
    macro_fields = safe_dict(analysis_brief.get("macro_note_fields"))
    policy_overlay = safe_dict(analysis_brief.get("policy_pressure_overlay"))
    citations = safe_list(brief_result.get("supporting_citations"))
    result = {
        "request": {
            "topic": request["topic"],
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "source_result_path": staged_source_result_path or request.get("source_result_path") or "",
        },
        "source_summary": source_summary,
        "analysis_brief": analysis_brief,
        "manual_review": manual_review,
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
        "workflow_publication_gate": workflow_publication_gate,
        "macro_note": {
            "one_line_judgment": safe_dict(macro_fields.get("one_line_judgment")),
            "confidence_markers": safe_dict(macro_fields.get("confidence_markers")),
            "current_state_rows": safe_list(macro_fields.get("current_state_rows")),
            "physical_vs_risk_premium": safe_list(macro_fields.get("physical_vs_risk_premium")),
            "benchmark_map": safe_dict(macro_fields.get("benchmark_map")),
            "scenario_matrix": safe_list(analysis_brief.get("scenario_matrix")),
            "bias_table": safe_list(macro_fields.get("bias_table")),
            "horizon_table": safe_list(macro_fields.get("horizon_table")),
            "what_changes_the_view": safe_dict(macro_fields.get("what_changes_the_view")),
            "policy_pressure_overlay": policy_overlay,
            "canonical_facts": safe_list(analysis_brief.get("canonical_facts")),
            "not_proven": safe_list(analysis_brief.get("not_proven")),
            "market_or_reader_relevance": safe_list(analysis_brief.get("market_or_reader_relevance")),
        },
        "supporting_citations": citations,
        "source_result": source_result,
    }
    result["report_markdown"] = build_macro_note_markdown(result)
    return result


def build_macro_note_markdown(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    macro_note = safe_dict(result.get("macro_note"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    manual_review = safe_dict(workflow_publication_gate.get("manual_review")) or safe_dict(result.get("manual_review"))
    judgment = safe_dict(macro_note.get("one_line_judgment"))
    confidence = safe_dict(macro_note.get("confidence_markers"))
    benchmark_map = safe_dict(macro_note.get("benchmark_map"))
    view_changes = safe_dict(macro_note.get("what_changes_the_view"))
    lines = [
        f"# Macro Note: {clean_text(request.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(request.get('analysis_time'))}",
        f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness') or result.get('publication_readiness')) or 'ready'}",
        f"- Reddit operator review: {clean_text(manual_review.get('status')) or 'not_required'}",
        "",
        "## One-line Judgment",
        "",
        clean_text(judgment.get("text")) or "None",
        "",
        "## Confidence",
        "",
        f"- Label: {clean_text(confidence.get('confidence_label')) or 'None'}",
        f"- Interval: {safe_list(confidence.get('confidence_interval'))}",
        f"- Gate: {clean_text(confidence.get('confidence_gate')) or 'None'}",
        f"- Evidence mode: {clean_text(confidence.get('evidence_mode')) or 'None'}",
        "",
        "## Reddit Operator Review",
        "",
        f"- Status: {clean_text(manual_review.get('status')) or 'not_required'}",
        f"- Required items: {int(manual_review.get('required_count', 0) or 0)}",
        f"- High-priority items: {int(manual_review.get('high_priority_count', 0) or 0)}",
        f"- Summary: {clean_text(manual_review.get('summary')) or 'None'}",
        f"- Next step: {clean_text(manual_review.get('next_step')) or 'None'}",
    ]
    for item in safe_list(manual_review.get("queue")):
        label = clean_text(item.get("title") or item.get("source_name") or item.get("url")) or "queued item"
        lines.append(
            f"- Queue: [{clean_text(item.get('priority_level')) or 'unknown'}] {label} | "
            f"{clean_text(item.get('summary')) or 'operator review required'}"
        )
    if not safe_list(manual_review.get("queue")):
        lines.append("- Queue: None")
    lines.extend(["", "## Current State", ""])
    for item in safe_list(macro_note.get("current_state_rows")):
        lines.append(f"- {clean_text(item.get('state'))}: {clean_text(item.get('detail'))}")
    if not safe_list(macro_note.get("current_state_rows")):
        lines.append("- None")
    lines.extend(["", "## Physical Vs Risk Premium", ""])
    for item in safe_list(macro_note.get("physical_vs_risk_premium")):
        lines.append(f"- {clean_text(item.get('bucket'))}: {clean_text(item.get('assessment'))}")
    if not safe_list(macro_note.get("physical_vs_risk_premium")):
        lines.append("- None")
    lines.extend(["", "## Benchmark Map", ""])
    lines.append(f"- Primary: {', '.join(safe_list(benchmark_map.get('primary_benchmarks'))) or 'None'}")
    lines.append(f"- Secondary: {', '.join(safe_list(benchmark_map.get('secondary_benchmarks'))) or 'None'}")
    lines.append(f"- Note: {clean_text(benchmark_map.get('benchmark_note')) or 'None'}")
    for item in safe_list(benchmark_map.get("benchmark_rows")):
        lines.append(f"- {clean_text(item.get('benchmark'))} | {clean_text(item.get('role'))} | {clean_text(item.get('why'))}")
    lines.extend(["", "## Scenario Matrix", ""])
    for item in safe_list(macro_note.get("scenario_matrix")):
        lines.append(
            f"- {clean_text(item.get('scenario'))} | {clean_text(item.get('probability_range'))} | "
            f"trigger: {clean_text(item.get('trigger'))}"
        )
    if not safe_list(macro_note.get("scenario_matrix")):
        lines.append("- None")
    lines.extend(["", "## Bias Table", ""])
    for item in safe_list(macro_note.get("bias_table")):
        lines.append(
            f"- {clean_text(item.get('label'))} ({clean_text(item.get('bias'))}) | "
            f"conditions: {', '.join(safe_list(item.get('conditions')))} | "
            f"read-through: {clean_text(item.get('market_readthrough'))}"
        )
    if not safe_list(macro_note.get("bias_table")):
        lines.append("- None")
    lines.extend(["", "## Horizon Table", ""])
    for item in safe_list(macro_note.get("horizon_table")):
        lines.append(
            f"- {clean_text(item.get('horizon'))} | base: {clean_text(item.get('base_case'))} | "
            f"upside: {clean_text(item.get('upside_case'))} | downside: {clean_text(item.get('downside_case'))}"
        )
    if not safe_list(macro_note.get("horizon_table")):
        lines.append("- None")
    policy_overlay = safe_dict(macro_note.get("policy_pressure_overlay"))
    if policy_overlay:
        lines.extend(["", "## Policy Pressure Overlay", ""])
        lines.append(f"- Name: {clean_text(policy_overlay.get('overlay_name'))}")
        lines.append(f"- Use case: {clean_text(policy_overlay.get('use_case'))}")
        for item in safe_list(policy_overlay.get("likely_components")):
            lines.append(
                f"- {clean_text(item.get('component'))} | {clean_text(item.get('pressure_direction'))} | sign: {clean_text(item.get('likely_sign_in_index'))}"
            )
    lines.extend(["", "## What Changes The View", ""])
    lines.extend([f"- Upgrade: {item}" for item in safe_list(view_changes.get("upgrades"))] or ["- Upgrade: None"])
    lines.extend([f"- Downgrade: {item}" for item in safe_list(view_changes.get("downgrades"))] or ["- Downgrade: None"])
    lines.extend(["", "## Sources", ""])
    for item in safe_list(result.get("supporting_citations"))[:8]:
        source_name = clean_text(item.get("source_name")) or "Source"
        source_url = clean_text(item.get("url"))
        lines.append(f"- [{source_name}]({source_url})" if source_url else f"- {source_name}")
    if not safe_list(result.get("supporting_citations")):
        lines.append("- None")
    return "\n".join(lines).strip() + "\n"


def build_workflow_report_markdown(result: dict[str, Any]) -> str:
    source_stage = safe_dict(result.get("source_stage"))
    agent_reach_stage = safe_dict(source_stage.get("agent_reach_stage"))
    opencli_stage = safe_dict(source_stage.get("opencli_stage"))
    macro_note_stage = safe_dict(result.get("macro_note_stage"))
    brief_stage = safe_dict(result.get("brief_stage"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    manual_review = safe_dict(workflow_publication_gate.get("manual_review")) or safe_dict(result.get("manual_review"))
    lines = [
        f"# Macro Note Workflow Report: {clean_text(result.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Source stage: {clean_text(source_stage.get('source_kind'))}",
        f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness') or result.get('publication_readiness')) or 'ready'}",
        f"- Reddit operator review: {clean_text(manual_review.get('status')) or 'not_required'}",
    ]
    lines.extend(build_source_stage_file_lines(source_stage, include_source_report=False, include_bridge_reports=False))
    lines.extend(
        [
        f"- Analysis brief: {clean_text(brief_stage.get('result_path'))}",
        f"- Macro note result: {clean_text(macro_note_stage.get('result_path'))}",
        f"- Macro note report: {clean_text(macro_note_stage.get('report_path'))}",
        f"- One-line judgment: {clean_text(macro_note_stage.get('one_line_judgment')) or 'None'}",
        ]
    )
    lines.extend(build_agent_reach_augmentation_lines(agent_reach_stage))
    lines.extend(build_opencli_augmentation_lines(opencli_stage))
    lines.extend(
        [
            "",
            "## Reddit Operator Review",
            "",
            f"- Status: {clean_text(manual_review.get('status')) or 'not_required'}",
            f"- Required items: {int(manual_review.get('required_count', 0) or 0)}",
            f"- High-priority items: {int(manual_review.get('high_priority_count', 0) or 0)}",
            f"- Summary: {clean_text(manual_review.get('summary')) or 'None'}",
            f"- Next step: {clean_text(manual_review.get('next_step')) or 'None'}",
        ]
    )
    for item in safe_list(manual_review.get("queue")):
        label = clean_text(item.get("title") or item.get("source_name") or item.get("url")) or "queued item"
        lines.append(
            f"- Queue: [{clean_text(item.get('priority_level')) or 'unknown'}] {label} | "
            f"{clean_text(item.get('summary')) or 'operator review required'}"
        )
    if not safe_list(manual_review.get("queue")):
        lines.append("- Queue: None")
    return "\n".join(lines).strip() + "\n"


def run_macro_note_workflow(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_workflow_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    source_payload, source_kind, agent_reach_stage, opencli_stage = prepare_source_payload(request)
    source_stage = write_source_stage_outputs(
        request["output_dir"],
        source_kind=source_kind,
        source_payload=source_payload,
        agent_reach_stage=agent_reach_stage,
        opencli_stage=opencli_stage,
        write_json=write_json,
    )
    staged_source_result_path = clean_text(source_stage.get("result_path"))

    brief_payload = build_brief_payload(request, source_payload, staged_source_result_path)
    brief_result = build_analysis_brief(brief_payload)
    brief_result_path = request["output_dir"] / "analysis-brief-result.json"
    brief_report_path = request["output_dir"] / "analysis-brief-report.md"
    write_json(brief_result_path, brief_result)
    brief_report_path.write_text(brief_result.get("report_markdown", ""), encoding="utf-8-sig")

    macro_note_result = build_macro_note_result(request, source_payload, brief_result, staged_source_result_path)
    macro_note_result_path = request["output_dir"] / "macro-note-result.json"
    macro_note_report_path = request["output_dir"] / "macro-note-report.md"
    write_json(macro_note_result_path, macro_note_result)
    macro_note_report_path.write_text(macro_note_result.get("report_markdown", ""), encoding="utf-8-sig")
    workflow_publication_gate = deepcopy(safe_dict(macro_note_result.get("workflow_publication_gate")))

    result = {
        "status": "ok",
        "workflow_kind": "macro_note_workflow",
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
        "manual_review": deepcopy(safe_dict(macro_note_result.get("manual_review"))),
        "workflow_publication_gate": workflow_publication_gate,
        "source_stage": source_stage,
        "brief_stage": {
            "result_path": str(brief_result_path),
            "report_path": str(brief_report_path),
            "recommended_thesis": clean_text(safe_dict(brief_result.get("analysis_brief")).get("recommended_thesis")),
        },
        "macro_note_stage": {
            "result_path": str(macro_note_result_path),
            "report_path": str(macro_note_report_path),
            "one_line_judgment": clean_text(
                safe_dict(safe_dict(macro_note_result.get("macro_note")).get("one_line_judgment")).get("text")
            ),
            "manual_review_required": bool(safe_dict(macro_note_result.get("manual_review")).get("required")),
            "manual_review_status": clean_text(safe_dict(macro_note_result.get("manual_review")).get("status")) or "not_required",
            "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
            "workflow_publication_gate": deepcopy(workflow_publication_gate),
        },
        "source_result": source_payload,
        "analysis_brief": safe_dict(brief_result.get("analysis_brief")),
        "macro_note_result": macro_note_result,
    }
    result["report_markdown"] = build_workflow_report_markdown(result)
    workflow_report_path = request["output_dir"] / "workflow-report.md"
    workflow_report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["workflow_report_path"] = str(workflow_report_path)
    return result


__all__ = ["load_json", "run_macro_note_workflow", "write_json"]
