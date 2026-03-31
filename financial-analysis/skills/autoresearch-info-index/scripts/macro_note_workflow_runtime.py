#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from agent_reach_bridge_runtime import run_agent_reach_bridge
from article_brief_runtime import build_analysis_brief, clean_text, load_json, safe_dict, safe_list, write_json
from news_index_runtime import isoformat_or_blank, now_utc, parse_datetime, run_news_index, slugify
from runtime_paths import runtime_subdir
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
    return {
        "payload_kind": payload_kind,
        "topic": topic,
        "analysis_time": analysis_time,
        "agent_reach_enabled": bool(payload.get("use_agent_reach") or agent_reach_config.get("enabled") or agent_reach_config),
        "agent_reach_config": agent_reach_config,
        "source_result": source_payload,
        "source_result_path": source_result_path,
        "payload": payload,
        "output_dir": output_dir,
    }


def build_agent_reach_bridge_payload(request: dict[str, Any]) -> dict[str, Any]:
    payload = safe_dict(request.get("payload"))
    agent_reach_config = safe_dict(request.get("agent_reach_config"))
    bridge_payload: dict[str, Any] = {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": deepcopy(safe_list(payload.get("questions"))),
        "use_case": clean_text(payload.get("use_case")) or "macro-note-workflow-agent-reach",
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


def prepare_source_payload(request: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]]:
    payload_kind = request["payload_kind"]
    source_payload = request["source_result"]
    agent_reach_stage: dict[str, Any] = {}
    if payload_kind == "x_request":
        x_payload = deepcopy(request["payload"])
        x_payload["output_dir"] = clean_text(x_payload.get("x_output_dir") or x_payload.get("source_output_dir")) or str(
            (request["output_dir"] / "source-stage").resolve()
        )
        return run_x_index(x_payload), "x_index", agent_reach_stage
    if payload_kind == "news_request":
        if request.get("agent_reach_enabled"):
            bridge_result = run_agent_reach_bridge(build_agent_reach_bridge_payload(request))
            source_payload = run_news_index(merge_news_payload_with_agent_reach_candidates(request["payload"], bridge_result))
            agent_reach_stage = {
                "enabled": True,
                "bridge_result": bridge_result,
                "channels_attempted": deepcopy(bridge_result.get("channels_attempted", [])),
                "channels_succeeded": deepcopy(bridge_result.get("channels_succeeded", [])),
                "channels_failed": deepcopy(bridge_result.get("channels_failed", [])),
                "imported_candidate_count": int(bridge_result.get("observations_imported", 0) or 0),
            }
            return source_payload, "news_index_agent_reach", agent_reach_stage
        return run_news_index(request["payload"]), "news_index", agent_reach_stage
    if source_payload:
        source_kind = "x_index" if safe_list(source_payload.get("x_posts")) or safe_dict(source_payload.get("evidence_pack")) else "news_index"
        return source_payload, source_kind, agent_reach_stage
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
    judgment = safe_dict(macro_note.get("one_line_judgment"))
    confidence = safe_dict(macro_note.get("confidence_markers"))
    benchmark_map = safe_dict(macro_note.get("benchmark_map"))
    view_changes = safe_dict(macro_note.get("what_changes_the_view"))
    lines = [
        f"# Macro Note: {clean_text(request.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(request.get('analysis_time'))}",
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
        "## Current State",
        "",
    ]
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
    macro_note_stage = safe_dict(result.get("macro_note_stage"))
    brief_stage = safe_dict(result.get("brief_stage"))
    lines = [
        f"# Macro Note Workflow Report: {clean_text(result.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Source stage: {clean_text(source_stage.get('source_kind'))}",
        f"- Source result: {clean_text(source_stage.get('result_path'))}",
        f"- Agent Reach bridge result: {clean_text(agent_reach_stage.get('result_path')) or 'not used'}",
        f"- Analysis brief: {clean_text(brief_stage.get('result_path'))}",
        f"- Macro note result: {clean_text(macro_note_stage.get('result_path'))}",
        f"- Macro note report: {clean_text(macro_note_stage.get('report_path'))}",
        f"- One-line judgment: {clean_text(macro_note_stage.get('one_line_judgment')) or 'None'}",
    ]
    if agent_reach_stage:
        lines.extend(
            [
                "",
                "## Agent Reach Augmentation",
                "",
                f"- Channels attempted: {', '.join(safe_list(agent_reach_stage.get('channels_attempted'))) or 'none'}",
                f"- Channels succeeded: {', '.join(safe_list(agent_reach_stage.get('channels_succeeded'))) or 'none'}",
                f"- Imported shadow candidates: {int(agent_reach_stage.get('imported_candidate_count', 0) or 0)}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_macro_note_workflow(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_workflow_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    source_payload, source_kind, agent_reach_stage = prepare_source_payload(request)
    source_result_path = request["output_dir"] / "source-result.json"
    source_report_path = request["output_dir"] / "source-report.md"
    write_json(source_result_path, source_payload)
    source_report_path.write_text(source_payload.get("report_markdown", ""), encoding="utf-8-sig")
    staged_source_result_path = str(source_result_path)
    if agent_reach_stage:
        agent_reach_result_path = request["output_dir"] / "agent-reach-bridge-result.json"
        agent_reach_report_path = request["output_dir"] / "agent-reach-bridge-report.md"
        write_json(agent_reach_result_path, safe_dict(agent_reach_stage.get("bridge_result")))
        agent_reach_report_path.write_text(safe_dict(agent_reach_stage.get("bridge_result")).get("report_markdown", ""), encoding="utf-8-sig")
        agent_reach_stage["result_path"] = str(agent_reach_result_path)
        agent_reach_stage["report_path"] = str(agent_reach_report_path)

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

    result = {
        "status": "ok",
        "workflow_kind": "macro_note_workflow",
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "source_stage": {
            "source_kind": source_kind,
            "result_path": str(source_result_path),
            "report_path": str(source_report_path),
            "agent_reach_stage": agent_reach_stage,
        },
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
