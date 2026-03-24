#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, short_excerpt, write_json


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


def is_source_result(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output"))


def extract_runtime_result(source_result: dict[str, Any]) -> dict[str, Any]:
    runtime = safe_dict(source_result.get("retrieval_result"))
    if runtime:
        return runtime
    if safe_list(source_result.get("observations")) or safe_dict(source_result.get("verdict_output")):
        return source_result
    adapted = deepcopy(source_result)
    adapted["request"] = safe_dict(adapted.get("request")) or safe_dict(adapted.get("retrieval_request"))
    adapted["observations"] = safe_list(adapted.get("observations")) or safe_list(adapted.get("source_observations"))
    adapted["claim_ledger"] = safe_list(adapted.get("claim_ledger"))
    adapted["verdict_output"] = safe_dict(adapted.get("verdict_output"))
    return adapted


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    if is_source_result(payload):
        payload = {"source_result": payload}
    source_result = payload.get("source_result")
    source_result_path = clean_text(payload.get("source_result_path") or payload.get("source_path"))
    if source_result is None and source_result_path:
        source_result = load_json(Path(source_result_path).resolve())
    if not isinstance(source_result, dict):
        raise ValueError("article-brief requires source_result or source_result_path")

    runtime = extract_runtime_result(source_result)
    source_request = (
        safe_dict(source_result.get("request"))
        or safe_dict(source_result.get("retrieval_request"))
        or safe_dict(runtime.get("request"))
    )
    analysis_time = parse_datetime(
        payload.get("analysis_time"),
        fallback=parse_datetime(source_request.get("analysis_time")),
    )
    if analysis_time is None:
        raise ValueError("article-brief requires analysis_time in the request or source result")

    return {
        "topic": clean_text(payload.get("topic") or source_request.get("topic") or "article-topic"),
        "analysis_time": analysis_time,
        "source_result": source_result,
        "source_result_path": source_result_path,
    }


def source_name_map(observations: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for observation in observations:
        source_id = clean_text(observation.get("source_id"))
        source_name = clean_text(observation.get("source_name"))
        if source_id and source_name and source_id not in mapping:
            mapping[source_id] = source_name
    return mapping


def citation_map(observations: list[dict[str, Any]]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    by_source_id: dict[str, str] = {}
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for observation in observations:
        source_id = clean_text(observation.get("source_id"))
        url = clean_text(observation.get("url"))
        key = (source_id or clean_text(observation.get("source_name")), url)
        if key in seen:
            continue
        seen.add(key)
        citation_id = f"S{len(citations) + 1}"
        citations.append(
            {
                "citation_id": citation_id,
                "source_id": source_id,
                "source_name": clean_text(observation.get("source_name")) or "Unknown source",
                "url": url,
                "channel": clean_text(observation.get("channel")),
                "source_tier": int(observation.get("source_tier", 3) or 3),
            }
        )
        if source_id:
            by_source_id[source_id] = citation_id
    return by_source_id, citations


def build_source_summary(request: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    observations = safe_list(runtime.get("observations"))
    verdict = safe_dict(runtime.get("verdict_output"))
    return {
        "source_kind": "x_index" if safe_list(request["source_result"].get("x_posts")) or safe_dict(request["source_result"].get("evidence_pack")) else "news_index",
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "observation_count": len(observations),
        "blocked_source_count": sum(1 for item in observations if clean_text(item.get("access_mode")) == "blocked"),
        "core_source_count": sum(1 for item in observations if clean_text(item.get("channel")) == "core"),
        "shadow_source_count": sum(1 for item in observations if clean_text(item.get("channel")) == "shadow"),
        "confidence_interval": safe_list(verdict.get("confidence_interval")) or [0, 0],
        "confidence_gate": clean_text(verdict.get("confidence_gate")),
        "core_verdict": clean_text(verdict.get("core_verdict")),
        "market_relevance": clean_string_list(verdict.get("market_relevance")),
    }


def claim_text(entry: dict[str, Any]) -> str:
    return clean_text(entry.get("claim_text"))


def support_count(entry: dict[str, Any]) -> int:
    return len(clean_string_list(entry.get("supporting_sources")))


def contradiction_count(entry: dict[str, Any]) -> int:
    return len(clean_string_list(entry.get("contradicting_sources")))


def not_proven_reason(entry: dict[str, Any]) -> str:
    status = clean_text(entry.get("status")) or "unclear"
    supports = support_count(entry)
    contradictions = contradiction_count(entry)
    if status == "denied" and contradictions:
        return "Fresh contradictory evidence is present against this claim."
    if contradictions and supports:
        return "This claim has mixed evidence and cannot be upgraded yet."
    if contradictions:
        return "The current record leans against this claim rather than supporting it."
    if status == "inferred":
        return "This remains an inference rather than a directly confirmed public fact."
    if supports:
        return "There is some support, but not enough stronger-source confirmation to treat it as established."
    return "The current public evidence is still too thin or low-confidence to confirm this claim."


def build_canonical_facts(
    claim_ledger: list[dict[str, Any]],
    source_names: dict[str, str],
    citation_by_source_id: dict[str, str],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for entry in claim_ledger:
        if clean_text(entry.get("status")) != "confirmed":
            continue
        source_ids = clean_string_list(entry.get("supporting_sources"))
        citation_ids = [citation_by_source_id[source_id] for source_id in source_ids if source_id in citation_by_source_id]
        facts.append(
            {
                "claim_id": clean_text(entry.get("claim_id")),
                "claim_text": claim_text(entry),
                "source_ids": source_ids,
                "source_names": [source_names.get(source_id, source_id) for source_id in source_ids[:3]],
                "citation_ids": citation_ids,
                "support_count": len(source_ids),
                "citation_count": len(citation_ids),
                "promotion_state": clean_text(entry.get("promotion_state")) or "core",
            }
        )
    facts.sort(
        key=lambda item: (
            int(clean_text(item.get("promotion_state")) == "core"),
            int(item.get("support_count", 0) or 0),
            int(item.get("citation_count", 0) or 0),
        ),
        reverse=True,
    )
    return facts


def build_not_proven(
    claim_ledger: list[dict[str, Any]],
    source_names: dict[str, str],
    citation_by_source_id: dict[str, str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in claim_ledger:
        status = clean_text(entry.get("status"))
        if status == "confirmed":
            continue
        source_ids = clean_string_list(entry.get("supporting_sources")) + clean_string_list(entry.get("contradicting_sources"))
        deduped_source_ids = []
        for source_id in source_ids:
            if source_id and source_id not in deduped_source_ids:
                deduped_source_ids.append(source_id)
        citations = [citation_by_source_id[source_id] for source_id in deduped_source_ids if source_id in citation_by_source_id]
        results.append(
            {
                "claim_id": clean_text(entry.get("claim_id")),
                "claim_text": claim_text(entry),
                "status": status or "unclear",
                "source_ids": deduped_source_ids,
                "source_names": [source_names.get(source_id, source_id) for source_id in deduped_source_ids[:3]],
                "citation_ids": citations,
                "support_count": support_count(entry),
                "contradiction_count": contradiction_count(entry),
                "promotion_state": clean_text(entry.get("promotion_state")) or "shadow",
                "why_not_proven": not_proven_reason(entry),
            }
        )
    priority = {"denied": 0, "unclear": 1, "inferred": 2}
    results.sort(
        key=lambda item: (
            priority.get(clean_text(item.get("status")), 3),
            -int(item.get("contradiction_count", 0) or 0),
            -int(item.get("support_count", 0) or 0),
        )
    )
    return results


def latest_shadow_summary(observations: list[dict[str, Any]]) -> str:
    fresh_shadow = [
        item for item in observations if clean_text(item.get("channel")) == "shadow" and clean_text(item.get("recency_bucket")) != ">24h"
    ]
    if not fresh_shadow:
        return ""
    top = fresh_shadow[0]
    source_name = clean_text(top.get("source_name")) or "a shadow source"
    age = clean_text(top.get("age_label")) or "recently"
    return f"The live tape is still being pushed by lower-confidence recent signals such as {source_name} ({age})."


def build_trend_lines(observations: list[dict[str, Any]], claim_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    fresh_core = [item for item in observations if clean_text(item.get("channel")) == "core" and clean_text(item.get("recency_bucket")) != ">24h"]
    fresh_shadow = [item for item in observations if clean_text(item.get("channel")) == "shadow" and clean_text(item.get("recency_bucket")) != ">24h"]
    unresolved = [item for item in claim_ledger if clean_text(item.get("status")) in {"unclear", "denied", "inferred"}]
    if fresh_core:
        source_names = [clean_text(item.get("source_name")) for item in fresh_core[:3] if clean_text(item.get("source_name"))]
        trends.append(
            {
                "trend": "Fresh higher-tier evidence is present.",
                "detail": f"Recent core sources are concentrated in {', '.join(source_names) if source_names else 'the current evidence pack'}.",
                "risk": "Do not let newer shadow chatter outrun these stronger confirmations.",
            }
        )
    shadow_text = latest_shadow_summary(observations)
    if shadow_text:
        trends.append(
            {
                "trend": "The live tape is moving faster than the confirmed record.",
                "detail": shadow_text,
                "risk": "Fast chatter can reorder attention without upgrading the main verdict.",
            }
        )
    if unresolved:
        trends.append(
            {
                "trend": "Important claims remain unresolved.",
                "detail": f"{len(unresolved)} tracked claim(s) are still denied, unclear, or inference-only.",
                "risk": "A confident article angle can overrun the actual evidence boundary here.",
            }
        )
    if not trends:
        trends.append(
            {
                "trend": "The current picture is still sparse.",
                "detail": "There is not enough clean public evidence yet to support a narrow or aggressive story line.",
                "risk": "The main risk is false precision rather than missing nuance.",
            }
        )
    return trends[:3]


def build_open_questions(verdict: dict[str, Any]) -> list[str]:
    questions = clean_string_list(verdict.get("missing_confirmations")) + clean_string_list(verdict.get("next_watch_items"))
    if not questions:
        questions.append("Which stronger source family would most directly confirm or deny the live-tape claim?")
    return questions[:6]


def build_scenario_matrix(verdict: dict[str, Any], source_summary: dict[str, Any]) -> list[dict[str, Any]]:
    crisis_rows = safe_list(verdict.get("escalation_scenarios"))
    if crisis_rows:
        rows: list[dict[str, Any]] = []
        for row in crisis_rows[:3]:
            rows.append(
                {
                    "scenario": clean_text(row.get("scenario")),
                    "probability_range": clean_text(row.get("probability_range")),
                    "trigger": clean_text(row.get("trigger")),
                }
            )
        return rows

    confidence = safe_list(source_summary.get("confidence_interval")) or [0, 0]
    return [
        {
            "scenario": "Base case holds",
            "probability_range": f"{max(15, confidence[0])}-{min(95, confidence[1])}%",
            "trigger": "A fresh Tier 0 or Tier 1 confirmation supports the current core verdict.",
        },
        {
            "scenario": "Mixed picture persists",
            "probability_range": "20-60%",
            "trigger": "The live tape stays active but stronger-source confirmation remains absent.",
        },
        {
            "scenario": "Current angle weakens",
            "probability_range": "10-45%",
            "trigger": "A fresh contradiction from an official, regulator, or wire source lands against the current narrative.",
        },
    ]


def build_story_angles(
    topic: str,
    canonical_facts: list[dict[str, Any]],
    not_proven: list[dict[str, Any]],
    image_keep_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    angles: list[dict[str, Any]] = []
    lead_fact = safe_dict(canonical_facts[0]) if canonical_facts else {}
    lead_risk = safe_dict(not_proven[0]) if not_proven else {}
    if canonical_facts and not_proven:
        angles.append(
            {
                "angle": (
                    f"For {topic}, lead with '{clean_text(lead_fact.get('claim_text'))}', then explain why "
                    f"'{clean_text(lead_risk.get('claim_text'))}' is still not proven."
                ),
                "risk": "If written too aggressively, the article can smuggle in an unsupported conclusion.",
            }
        )
    elif canonical_facts:
        angles.append(
            {
                "angle": f"For {topic}, lead with the strongest confirmed development and keep the rest as conditional scenarios.",
                "risk": "Can become too flat if the piece does not explain what still matters on the live tape.",
            }
        )
    else:
        angles.append(
            {
                "angle": f"For {topic}, explain why the public record is still too thin for a hard call.",
                "risk": "Can feel unsatisfying if the piece never identifies the specific confirmation gap.",
            }
        )
    if image_keep_reasons:
        lead_image = safe_dict(image_keep_reasons[0])
        angles.append(
            {
                "angle": (
                    "Use the strongest saved visual as supporting context, and explain exactly why it is kept: "
                    f"{clean_text(lead_image.get('reason')) or 'it shows the original source context clearly'}."
                ),
                "risk": "Visuals can create a false sense of certainty if their evidentiary limits are not stated explicitly.",
            }
        )
    if not_proven:
        angles.append(
            {
                "angle": (
                    f"Stress-test the dramatic claim '{clean_text(lead_risk.get('claim_text'))}' and show why it still "
                    "fails the current evidence threshold."
                ),
                "risk": "Can become too reactive if the piece spends more time on rumor than on the stable record.",
            }
        )
    return angles[:3]


def build_image_keep_reasons(source_result: dict[str, Any], verdict: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for post in safe_list(source_result.get("x_posts")):
        if not isinstance(post, dict):
            continue
        post_url = clean_text(post.get("post_url"))
        root_path = clean_text(post.get("root_post_screenshot_path"))
        if root_path:
            items.append(
                {
                    "kind": "root_post_screenshot",
                    "source_name": clean_text(post.get("author_handle") or post.get("author_display_name") or "X post"),
                    "path": root_path,
                    "source_url": post_url,
                    "reason": clean_text(post.get("post_summary") or post.get("media_summary") or "Keeps the original post context visible."),
                }
            )
        for media in safe_list(post.get("media_items")):
            if not isinstance(media, dict):
                continue
            if clean_text(media.get("local_artifact_path")) or clean_text(media.get("source_url")):
                items.append(
                    {
                        "kind": "post_media",
                        "source_name": clean_text(post.get("author_handle") or post.get("author_display_name") or "X post"),
                        "path": clean_text(media.get("local_artifact_path")),
                        "source_url": clean_text(media.get("source_url")),
                        "reason": clean_text(media.get("ocr_summary") or media.get("ocr_text_raw") or "Contains useful visual evidence."),
                    }
                )
    for artifact in safe_list(verdict.get("source_artifacts")):
        if not isinstance(artifact, dict):
            continue
        if clean_text(artifact.get("root_post_screenshot_path")):
            items.append(
                {
                    "kind": "artifact_screenshot",
                    "source_name": clean_text(artifact.get("source_name")) or "Source artifact",
                    "path": clean_text(artifact.get("root_post_screenshot_path")),
                    "source_url": clean_text(artifact.get("url")),
                    "reason": clean_text(
                        artifact.get("media_summary")
                        or artifact.get("post_summary")
                        or artifact.get("combined_summary")
                        or "Shows the original visual evidence attached to the source."
                    ),
                }
            )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (clean_text(item.get("kind")), clean_text(item.get("path")), clean_text(item.get("source_url")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:4]


def build_voice_constraints(source_summary: dict[str, Any], not_proven: list[dict[str, Any]]) -> list[str]:
    constraints = [
        "Lead with canonical facts before any scenario or market narrative.",
        "Do not promote a single shadow signal into a settled conclusion.",
        "Keep confirmed facts, not-proven claims, and inference-only material explicitly separated.",
    ]
    if source_summary.get("blocked_source_count", 0):
        constraints.append("Do not treat blocked-page screenshots or inaccessible pages as proof by themselves.")
    if not_proven:
        constraints.append("Any strong thesis must explicitly acknowledge the highest-risk unresolved claim.")
    constraints.append("Treat image or ship-tracking evidence as the last public indication, not literal real-time truth, when relevant.")
    return constraints


def build_misread_risks(not_proven: list[dict[str, Any]], observations: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if not_proven:
        risks.append(f"The article can easily overstate the unsupported leap: {clean_text(not_proven[0].get('claim_text'))}.")
    fresh_shadow = [
        item for item in observations if clean_text(item.get("channel")) == "shadow" and clean_text(item.get("recency_bucket")) != ">24h"
    ]
    if fresh_shadow:
        risks.append("Fresh shadow-only signals can create urgency without actually upgrading the evidence quality.")
    blocked_sources = [item for item in observations if clean_text(item.get("access_mode")) == "blocked"]
    if blocked_sources:
        risks.append("Blocked sources can be mistaken for checked evidence even though they were not readable in full.")
    if not risks:
        risks.append("The main remaining risk is overconfidence rather than missing evidence.")
    return risks[:4]


def build_recommended_thesis(topic: str, canonical_facts: list[dict[str, Any]], not_proven: list[dict[str, Any]], observations: list[dict[str, Any]]) -> str:
    if canonical_facts and not_proven:
        return f"The safest evidence-backed angle on {topic} is to separate the strongest confirmed development from the more aggressive claim that is still not proven."
    if canonical_facts:
        return f"The cleanest way to write {topic} is to lead with the strongest confirmed change and keep the rest as contingent scenarios."
    fresh_shadow = [item for item in observations if clean_text(item.get("channel")) == "shadow" and clean_text(item.get("recency_bucket")) != ">24h"]
    if fresh_shadow:
        return f"For {topic}, the live tape is active but the confirmed record is still too thin for a hard call."
    return f"For {topic}, the public evidence is still too sparse for a narrow or highly confident thesis."


def build_analysis_brief_payload(request: dict[str, Any]) -> dict[str, Any]:
    runtime = extract_runtime_result(request["source_result"])
    observations = safe_list(runtime.get("observations"))
    claim_ledger = safe_list(runtime.get("claim_ledger") or request["source_result"].get("claim_ledger"))
    verdict = safe_dict(runtime.get("verdict_output") or request["source_result"].get("verdict_output"))
    source_summary = build_source_summary(request, runtime)
    source_names = source_name_map(observations)
    citation_by_source_id, citations = citation_map(observations)
    canonical_facts = build_canonical_facts(claim_ledger, source_names, citation_by_source_id)
    not_proven = build_not_proven(claim_ledger, source_names, citation_by_source_id)
    image_keep_reasons = build_image_keep_reasons(request["source_result"], verdict)
    analysis_brief = {
        "canonical_facts": canonical_facts,
        "not_proven": not_proven,
        "open_questions": build_open_questions(verdict),
        "trend_lines": build_trend_lines(observations, claim_ledger),
        "scenario_matrix": build_scenario_matrix(verdict, source_summary),
        "market_or_reader_relevance": clean_string_list(verdict.get("market_relevance")) or clean_string_list(source_summary.get("market_relevance")),
        "story_angles": build_story_angles(request["topic"], canonical_facts, not_proven, image_keep_reasons),
        "image_keep_reasons": image_keep_reasons,
        "voice_constraints": build_voice_constraints(source_summary, not_proven),
        "misread_risks": build_misread_risks(not_proven, observations),
        "recommended_thesis": build_recommended_thesis(request["topic"], canonical_facts, not_proven, observations),
        "recommended_thesis_zh": "",
    }
    return {
        "request": {
            "topic": request["topic"],
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "source_result_path": request["source_result_path"],
        },
        "source_summary": source_summary,
        "analysis_brief": analysis_brief,
        "supporting_citations": citations,
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("source_summary"))
    brief = safe_dict(result.get("analysis_brief"))
    lines = [
        f"# Article Brief: {clean_text(summary.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(summary.get('analysis_time'))}",
        f"- Source kind: {clean_text(summary.get('source_kind'))}",
        f"- Observations: {int(summary.get('observation_count', 0) or 0)}",
        f"- Blocked sources: {int(summary.get('blocked_source_count', 0) or 0)}",
        f"- Confidence: {safe_list(summary.get('confidence_interval'))}",
        "",
        "## Recommended Thesis",
        "",
        clean_text(brief.get("recommended_thesis")) or "None",
        "",
        "## Canonical Facts",
        "",
    ]
    facts = safe_list(brief.get("canonical_facts"))
    if facts:
        for item in facts:
            citation_text = ", ".join(clean_string_list(item.get("citation_ids"))) or "none"
            lines.append(f"- {clean_text(item.get('claim_text'))} [{citation_text}]")
    else:
        lines.append("- None")
    lines.extend(["", "## Not Proven", ""])
    not_proven = safe_list(brief.get("not_proven"))
    if not_proven:
        for item in not_proven:
            lines.append(
                f"- {clean_text(item.get('claim_text'))} ({clean_text(item.get('status')) or 'unclear'}) | "
                f"why: {clean_text(item.get('why_not_proven')) or 'not enough evidence yet'}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Open Questions", ""])
    for item in clean_string_list(brief.get("open_questions")):
        lines.append(f"- {item}")
    if not clean_string_list(brief.get("open_questions")):
        lines.append("- None")
    lines.extend(["", "## Scenario Matrix", ""])
    scenarios = safe_list(brief.get("scenario_matrix"))
    if scenarios:
        for item in scenarios:
            lines.append(
                f"- {clean_text(item.get('scenario'))} | {clean_text(item.get('probability_range')) or 'n/a'} | "
                f"trigger: {clean_text(item.get('trigger')) or 'n/a'}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Story Angles", ""])
    for item in safe_list(brief.get("story_angles")):
        lines.append(f"- {clean_text(item.get('angle'))} | risk: {clean_text(item.get('risk'))}")
    if not safe_list(brief.get("story_angles")):
        lines.append("- None")
    lines.extend(["", "## Image Keep Reasons", ""])
    image_reasons = safe_list(brief.get("image_keep_reasons"))
    if image_reasons:
        for item in image_reasons:
            lines.append(
                f"- {clean_text(item.get('kind')) or 'image'} | {clean_text(item.get('source_name')) or 'unknown source'} | "
                f"{clean_text(item.get('reason')) or 'no reason recorded'}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Voice Constraints", ""])
    for item in clean_string_list(brief.get("voice_constraints")):
        lines.append(f"- {item}")
    lines.extend(["", "## Misread Risks", ""])
    for item in clean_string_list(brief.get("misread_risks")):
        lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def build_analysis_brief(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    result = build_analysis_brief_payload(request)
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = ["build_analysis_brief", "load_json", "write_json"]
