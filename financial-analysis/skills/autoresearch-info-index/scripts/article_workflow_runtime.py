#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from article_brief_runtime import build_analysis_brief, build_reddit_operator_review_manual_state
from article_cleanup_runtime import cleanup_article_temp_dirs
from article_feedback_markdown import build_feedback_markdown
from article_feedback_profiles import feedback_profile_status, resolve_profile_dir
from article_draft_flow_runtime import build_article_draft, clean_string_list, clean_text, load_json, safe_dict, safe_list, write_json
from agent_reach_bridge_runtime import run_agent_reach_bridge
from agent_reach_workflow_bridge_runtime import (
    build_agent_reach_bridge_payload,
    merge_news_payload_with_agent_reach_candidates,
    summarize_agent_reach_stage,
)
from opencli_bridge_runtime import prepare_opencli_bridge
from opencli_workflow_bridge_runtime import (
    build_opencli_bridge_payload,
    merge_news_payload_with_opencli_candidates,
    summarize_opencli_stage,
)
from article_revise_flow_runtime import build_article_revision
from news_index_runtime import isoformat_or_blank, parse_datetime, run_news_index, slugify
from runtime_paths import runtime_subdir
from workflow_publication_gate_runtime import build_workflow_publication_gate
from last30days_bridge_runtime import run_last30days_bridge
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

import random


def restructure_angle(
    request: dict[str, Any],
    brief_result: dict[str, Any],
) -> dict[str, Any]:
    """Pick a non-default story angle from the brief and inject it into the request.

    This ensures the draft uses a different cut-in point from the source articles,
    making the final article structurally independent.
    """
    analysis_brief = safe_dict(brief_result.get("analysis_brief"))
    angles_en = safe_list(analysis_brief.get("story_angles"))
    angles_zh = safe_list(analysis_brief.get("story_angles_zh"))

    # Already has an explicit angle from the user — don't override
    if clean_text(request.get("angle")) or clean_text(request.get("angle_zh")):
        return request

    # Need at least 2 angles to pick a non-default one
    if len(angles_en) >= 2:
        # Sort by risk length (shorter risk = safer angle), skip the first (default)
        candidates = angles_en[1:]
        candidates.sort(key=lambda a: len(clean_text(a.get("risk", ""))))
        chosen = candidates[0]
        request["angle"] = clean_text(chosen.get("angle", ""))
    elif angles_en:
        request["angle"] = clean_text(angles_en[0].get("angle", ""))

    if len(angles_zh) >= 2:
        candidates_zh = angles_zh[1:]
        candidates_zh.sort(key=lambda a: len(clean_text(a.get("risk", ""))))
        chosen_zh = candidates_zh[0]
        request["angle_zh"] = clean_text(chosen_zh.get("angle", ""))
    elif angles_zh:
        request["angle_zh"] = clean_text(angles_zh[0].get("angle", ""))

    return request


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
        raise ValueError("article-workflow requires analysis_time in the request or the indexed result")

    topic = (
        clean_text(payload.get("topic"))
        or clean_text(source_request.get("topic"))
        or clean_text(retrieval_request.get("topic"))
        or clean_text(runtime_request.get("topic"))
        or "article-topic"
    )
    output_dir = (
        Path(clean_text(payload.get("output_dir"))).expanduser()
        if clean_text(payload.get("output_dir"))
        else runtime_subdir("article-workflow", slugify(topic, "article-topic"), analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    agent_reach_config = safe_dict(payload.get("agent_reach"))
    opencli_config = safe_dict(payload.get("opencli_config") or payload.get("opencli"))
    return {
        "payload_kind": payload_kind,
        "topic": topic,
        "analysis_time": analysis_time,
        "title_hint": clean_text(payload.get("title_hint")),
        "title_hint_zh": clean_text(payload.get("title_hint_zh")),
        "subtitle_hint": clean_text(payload.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(payload.get("subtitle_hint_zh")),
        "angle": clean_text(payload.get("angle")),
        "angle_zh": clean_text(payload.get("angle_zh")),
        "tone": clean_text(payload.get("tone")),
        "target_length_chars": payload.get("target_length_chars", payload.get("target_length")),
        "max_images": payload.get("max_images"),
        "human_signal_ratio": payload.get("human_signal_ratio"),
        "personal_phrase_bank": payload.get("personal_phrase_bank"),
        "image_strategy": clean_text(payload.get("image_strategy")),
        "draft_mode": clean_text(payload.get("draft_mode")),
        "article_framework": clean_text(payload.get("article_framework")),
        "headline_hook_mode": clean_text(payload.get("headline_hook_mode") or payload.get("title_hook_mode")),
        "headline_hook_prefixes": clean_string_list(
            payload.get("headline_hook_prefixes") or payload.get("title_hook_prefixes") or payload.get("title_prefixes")
        ),
        "language_mode": clean_text(payload.get("language_mode") or payload.get("output_language")),
        "feedback_profile_dir": clean_text(payload.get("feedback_profile_dir")),
        "cleanup_enabled": bool(payload.get("cleanup_enabled") or payload.get("cleanup_days") or payload.get("cleanup_root_dir")),
        "cleanup_days": int(payload.get("cleanup_days", 4) or 4),
        "cleanup_root_dir": clean_text(payload.get("cleanup_root_dir")),
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
        return run_x_index(request["payload"]), "x_index", agent_reach_stage, opencli_stage
    if payload_kind == "last30days_request":
        return run_last30days_bridge(request["payload"]), "last30days_bridge", agent_reach_stage, opencli_stage
    if payload_kind == "news_request":
        merged_payload, agent_reach_stage, opencli_stage = augment_news_payload_with_workflow_sources(
            request,
            default_agent_reach_use_case="article-workflow-agent-reach",
            default_opencli_use_case="article-workflow-opencli",
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
    raise ValueError("article-workflow could not resolve a source payload")


def build_draft_payload(request: dict[str, Any], source_result: dict[str, Any]) -> dict[str, Any]:
    draft_payload = {"source_result": source_result}
    for key in (
        "topic",
        "title_hint",
        "title_hint_zh",
        "subtitle_hint",
        "subtitle_hint_zh",
        "angle",
        "angle_zh",
        "tone",
        "target_length_chars",
        "max_images",
        "human_signal_ratio",
        "personal_phrase_bank",
        "language_mode",
        "article_framework",
        "headline_hook_mode",
        "headline_hook_prefixes",
        "feedback_profile_dir",
    ):
        if request.get(key) not in (None, ""):
            draft_payload[key] = request[key]
    if request.get("image_strategy"):
        draft_payload["image_strategy"] = request["image_strategy"]
    if request.get("draft_mode"):
        draft_payload["draft_mode"] = request["draft_mode"]
    draft_payload["asset_output_dir"] = str(request["output_dir"] / "assets")
    draft_payload["download_remote_images"] = True
    return draft_payload


def build_brief_payload(request: dict[str, Any], source_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_result": source_result,
        "source_result_path": request.get("source_result_path"),
        "topic": request.get("topic"),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
    }


def build_revision_template(draft_result: dict[str, Any]) -> dict[str, Any]:
    request = safe_dict(draft_result.get("request"))
    article_package = safe_dict(draft_result.get("article_package"))
    analysis_brief = safe_dict(draft_result.get("analysis_brief")) or safe_dict(safe_dict(draft_result.get("draft_context")).get("analysis_brief"))
    source_summary = safe_dict(draft_result.get("source_summary"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    hero_image_id = clean_text(selected_images[0].get("asset_id") or selected_images[0].get("image_id")) if selected_images else ""
    profile_status = safe_dict(request.get("feedback_profile_status")) or safe_dict(draft_result.get("feedback_profile_status"))
    if not profile_status:
        profile_status = feedback_profile_status(
            resolve_profile_dir(request.get("feedback_profile_dir")),
            clean_text(request.get("topic")) or clean_text(safe_dict(draft_result.get("source_summary")).get("topic")) or "article-topic",
        )
    unresolved_claim = clean_text(safe_dict((safe_list(analysis_brief.get("not_proven")) or [{}])[0]).get("claim_text"))
    review_focus_checks: list[str] = []
    if unresolved_claim:
        review_focus_checks.append(f"Check that the article still treats this as unresolved: {unresolved_claim}")
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        review_focus_checks.append("Check that blocked or inaccessible sources are disclosed clearly.")
    for item in clean_text_list_preview(article_package.get("writer_risk_notes"), limit=2):
        review_focus_checks.append(item)
    if selected_images:
        image_ids = [
            clean_text(item.get("asset_id") or item.get("image_id"))
            for item in selected_images[:4]
            if clean_text(item.get("asset_id") or item.get("image_id"))
        ]
        if image_ids:
            review_focus_checks.append(f"Confirm whether these image IDs should stay near the front: {', '.join(image_ids)}")
    template = {
        "feedback": {
            "summary": "",
            "tone": clean_text(request.get("tone")) or "neutral-cautious",
            "keep_image_asset_ids": [hero_image_id] if hero_image_id else [],
            "drop_image_asset_ids": [],
        },
        "language_mode": clean_text(request.get("language_mode")) or "english",
        "tone": clean_text(request.get("tone")) or "neutral-cautious",
        "draft_mode": clean_text(request.get("draft_mode")) or "balanced",
        "image_strategy": clean_text(request.get("image_strategy")) or "mixed",
        "headline_hook_mode": clean_text(request.get("headline_hook_mode")) or "auto",
        "headline_hook_prefixes": safe_list(request.get("headline_hook_prefixes")),
        "max_images": request.get("max_images", 3),
        "human_signal_ratio": request.get("human_signal_ratio", 35),
        "personal_phrase_bank": safe_list(request.get("personal_phrase_bank")),
        "must_include": safe_list(request.get("must_include")),
        "must_avoid": safe_list(request.get("must_avoid")),
        "persist_feedback": {
            "scope": "none",
            "use_current_request_defaults": True,
            "defaults": {
                "language_mode": clean_text(request.get("language_mode")) or "english",
                "tone": clean_text(request.get("tone")) or "neutral-cautious",
                "draft_mode": clean_text(request.get("draft_mode")) or "balanced",
                "image_strategy": clean_text(request.get("image_strategy")) or "mixed",
                "headline_hook_mode": clean_text(request.get("headline_hook_mode")) or "auto",
                "headline_hook_prefixes": safe_list(request.get("headline_hook_prefixes")),
                "max_images": request.get("max_images", 3),
                "human_signal_ratio": request.get("human_signal_ratio", 35),
                "personal_phrase_bank": safe_list(request.get("personal_phrase_bank")),
                "must_include": [],
                "must_avoid": [],
            },
            "notes": [],
        },
        "title_hint": "",
        "title_hint_zh": "",
        "subtitle_hint": "",
        "subtitle_hint_zh": "",
        "angle": "",
        "angle_zh": "",
        "edited_body_markdown": "",
        "edited_article_markdown": "",
        "human_feedback_form": {
            "overall_goal_in_plain_english": "",
            "what_to_keep": [],
            "what_to_change": [
                {
                    "change": "",
                    "why": "",
                }
            ],
            "what_to_remember_next_time": [
                {
                    "key": "must_include",
                    "value": "",
                    "why": "",
                }
            ],
            "one_off_fixes_not_style": [
                {
                    "change": "",
                    "why": "",
                }
            ],
            "help": {
                "how_to_use": [
                    "Fill this form if you want a simpler review path. The system will translate it into structured learning signals.",
                    "Use what_to_keep only as soft context to preserve, not as a hard lock on the rewrite.",
                    "Use what_to_change for edits you made in this draft.",
                    "Use what_to_remember_next_time only for preferences you want reused later. If you omit scope, topic is assumed.",
                    "Use one_off_fixes_not_style for fact corrections or evidence-bound fixes that should not become house style.",
                    "Optional advanced fields like area, reason_tag, remember_for, and scope can be added only when they help.",
                ],
                "reason_tags": [
                    "voice",
                    "structure",
                    "clarity",
                    "factual_caution",
                    "citation_handling",
                    "image_usage",
                    "translation",
                    "audience_fit",
                    "emphasis",
                    "other",
                ],
                "areas": [
                    "title",
                    "subtitle",
                    "lede",
                    "body",
                    "article",
                    "structure",
                    "images",
                    "claims",
                    "citations",
                    "tone",
                    "language",
                    "other",
                ],
                "remember_for_meaning": {
                    "review": "Good context for this review, but not a saved default yet.",
                    "topic": "Save this preference for this topic only.",
                    "global": "Save this preference across future drafts.",
                },
                "preference_keys": [
                    "language_mode",
                    "tone",
                    "draft_mode",
                    "image_strategy",
                    "max_images",
                    "human_signal_ratio",
                    "personal_phrase_bank",
                    "must_include",
                    "must_avoid",
                ],
            },
        },
        "edit_reason_feedback": {
            "summary": "",
            "changes": [],
            "reusable_preferences": [],
            "help": {
                "reason_tags": [
                    "voice",
                    "structure",
                    "clarity",
                    "factual_caution",
                    "citation_handling",
                    "image_usage",
                    "translation",
                    "audience_fit",
                    "emphasis",
                    "other",
                ],
                "reuse_scope_meaning": {
                    "none": "One-off edit. Keep it in history, but do not reuse it.",
                    "review": "Useful signal for review, but not yet a default.",
                    "topic": "Good default for this topic only.",
                    "global": "Good default across future drafts.",
                },
                "preference_keys": [
                    "language_mode",
                    "tone",
                    "draft_mode",
                    "image_strategy",
                    "max_images",
                    "human_signal_ratio",
                    "personal_phrase_bank",
                    "must_include",
                    "must_avoid",
                ],
            },
        },
        "review_form_quickstart": {
            "recommended_path": "Fill human_feedback_form first. Use edit_reason_feedback only if you want the lower-level structured version directly.",
            "example_overall_goal": "Make the opening clearer and more cautious.",
            "example_change": {
                "change": "Lead with confirmed facts before scenarios.",
                "why": "Readers should see what is known before what is possible.",
            },
            "example_preference": {
                "key": "must_include",
                "value": "Lead with the strongest confirmed fact before any scenario.",
                "why": "This is the framing I want for this kind of article.",
            },
            "example_one_off_fix": {
                "change": "Removed the line implying talks were already agreed.",
                "why": "That was a fact correction, not a reusable writing preference.",
            },
        },
        "review_focus_suggestions": {
            "top_unresolved_claim": unresolved_claim,
            "blocked_source_count": int(source_summary.get("blocked_source_count", 0) or 0),
            "writer_risk_notes": clean_text_list_preview(article_package.get("writer_risk_notes"), limit=4),
            "recommended_first_checks": clean_text_list_preview(review_focus_checks, limit=6),
        },
        "allow_auto_rewrite_after_manual": False,
        "feedback_profile_status": profile_status,
        "feedback_reuse_help": {
            "save_for_all_future_drafts": "Set persist_feedback.scope to global.",
            "save_for_this_topic_only": "Set persist_feedback.scope to topic.",
            "save_for_both": "Set persist_feedback.scope to both.",
        },
    }
    return template


def build_revision_form_markdown(draft_result: dict[str, Any], revision_template: dict[str, Any]) -> str:
    return build_feedback_markdown(draft_result, revision_template)


def summarize_asset_stage(draft_result: dict[str, Any], draft_result_path: Path) -> dict[str, Any]:
    article_package = safe_dict(draft_result.get("article_package"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    localization = safe_dict(draft_result.get("asset_localization") or article_package.get("asset_localization"))
    local_ready_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "local_ready")
    remote_only_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "remote_only")
    missing_count = sum(1 for item in selected_images if clean_text(item.get("status")) == "missing")
    return {
        "asset_output_dir": clean_text(localization.get("asset_output_dir")),
        "downloaded_count": int(localization.get("downloaded_count", 0) or 0),
        "failed_count": int(localization.get("failed_count", 0) or 0),
        "local_ready_count": local_ready_count,
        "remote_only_count": remote_only_count,
        "missing_count": missing_count,
        "suggested_asset_hydrate_command": (
            f"financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_article_asset_hydrate.cmd \"{draft_result_path}\""
            if remote_only_count > 0
            else ""
        ),
    }


def summarize_feedback_stage(draft_result: dict[str, Any]) -> dict[str, Any]:
    request = safe_dict(draft_result.get("request"))
    cached = safe_dict(draft_result.get("feedback_profile_status")) or safe_dict(request.get("feedback_profile_status"))
    if cached:
        return cached
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    topic = clean_text(request.get("topic")) or clean_text(safe_dict(draft_result.get("source_summary")).get("topic")) or "article-topic"
    return feedback_profile_status(profile_dir, topic)


def summarize_brief_decisions(brief_result: dict[str, Any]) -> dict[str, Any]:
    analysis_brief = safe_dict(brief_result.get("analysis_brief"))
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    story_angles = safe_list(analysis_brief.get("story_angles"))
    lead_canonical_fact = clean_text(safe_dict((canonical_facts or [{}])[0]).get("claim_text"))
    lead_not_proven = clean_text(safe_dict((not_proven or [{}])[0]).get("claim_text"))
    top_story_angle = clean_text(safe_dict((story_angles or [{}])[0]).get("angle"))
    return {
        "recommended_thesis": clean_text(analysis_brief.get("recommended_thesis")),
        "lead_canonical_fact": lead_canonical_fact,
        "lead_not_proven": lead_not_proven,
        "top_story_angle": top_story_angle,
        "voice_constraints": clean_text_list_preview(analysis_brief.get("voice_constraints"), limit=3),
        "canonical_fact_count": len(canonical_facts),
        "not_proven_count": len(not_proven),
    }


def clean_text_list_preview(value: Any, *, limit: int = 3) -> list[str]:
    return [clean_text(item) for item in safe_list(value) if clean_text(item)][: max(1, limit)]


def summarize_learning_rules_preview(value: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    preview = []
    for item in safe_list(value)[: max(1, limit)]:
        rule = safe_dict(item)
        key = clean_text(rule.get("key"))
        if not key:
            continue
        preview.append(
            {
                "key": key,
                "scope": clean_text(rule.get("scope")),
                "confidence": float(rule.get("confidence", 0) or 0),
                "rule_type": clean_text(rule.get("rule_type")),
                "reason": clean_text(rule.get("reason")),
            }
        )
    return preview


def summarize_style_learning_surface(style_learning: dict[str, Any], profile_update_decision: dict[str, Any]) -> dict[str, Any]:
    proposed_defaults = deepcopy(safe_dict(safe_dict(style_learning.get("proposed_profile_feedback")).get("defaults")))
    return {
        "decision": clean_text(profile_update_decision.get("status")),
        "reason": clean_text(profile_update_decision.get("reason")),
        "high_confidence_rule_count": len(safe_list(style_learning.get("high_confidence_rules"))),
        "medium_confidence_rule_count": len(safe_list(style_learning.get("medium_confidence_rules"))),
        "low_confidence_rule_count": len(safe_list(style_learning.get("low_confidence_rules"))),
        "explicit_change_count": int(style_learning.get("explicit_change_count", 0) or 0),
        "explicit_preference_count": int(style_learning.get("explicit_preference_count", 0) or 0),
        "used_explicit_feedback": bool(style_learning.get("used_explicit_feedback")),
        "change_summary_preview": clean_text_list_preview(style_learning.get("change_summary"), limit=4),
        "excluded_signals_preview": clean_text_list_preview(style_learning.get("excluded_signals"), limit=3),
        "high_confidence_rule_preview": summarize_learning_rules_preview(style_learning.get("high_confidence_rules"), limit=3),
        "medium_confidence_rule_preview": summarize_learning_rules_preview(style_learning.get("medium_confidence_rules"), limit=3),
        "low_confidence_rule_preview": summarize_learning_rules_preview(style_learning.get("low_confidence_rules"), limit=3),
        "proposed_default_keys": sorted(proposed_defaults.keys()),
        "proposed_defaults": proposed_defaults,
    }


def summarize_draft_decisions(draft_result: dict[str, Any]) -> dict[str, Any]:
    article_package = safe_dict(draft_result.get("article_package"))
    style_profile = safe_dict(article_package.get("style_profile_applied"))
    effective_request = safe_dict(style_profile.get("effective_request"))
    draft_claim_map = safe_list(article_package.get("draft_claim_map"))
    return {
        "title": clean_text(article_package.get("title")),
        "draft_thesis": clean_text(article_package.get("draft_thesis")),
        "top_claims": [
            {
                "claim_label": clean_text(item.get("claim_label")),
                "claim_text": clean_text(item.get("claim_text")),
                "citation_ids": clean_text_list_preview(item.get("citation_ids"), limit=4),
                "support_level": clean_text(item.get("support_level")),
            }
            for item in draft_claim_map[:4]
            if clean_text(item.get("claim_text"))
        ],
        "style_effective_request": {
            "language_mode": clean_text(effective_request.get("language_mode")),
            "draft_mode": clean_text(effective_request.get("draft_mode")),
            "image_strategy": clean_text(effective_request.get("image_strategy")),
            "tone": clean_text(effective_request.get("tone")),
            "human_signal_ratio": int(effective_request.get("human_signal_ratio", 0) or 0),
            "personal_phrase_bank": clean_text_list_preview(effective_request.get("personal_phrase_bank"), limit=4),
            "must_include": clean_text_list_preview(effective_request.get("must_include"), limit=3),
            "must_avoid": clean_text_list_preview(effective_request.get("must_avoid"), limit=3),
        },
        "writer_risk_notes": clean_text_list_preview(article_package.get("writer_risk_notes"), limit=4),
    }


def summarize_review_decisions(review_result: dict[str, Any]) -> dict[str, Any]:
    review_package = safe_dict(review_result.get("review_rewrite_package"))
    style_learning = safe_dict(review_result.get("style_learning"))
    profile_update_decision = safe_dict(review_result.get("profile_update_decision"))
    attacks = safe_list(review_package.get("attacks"))
    severity_rank = {"critical": 3, "major": 2, "minor": 1}
    highest_attack = {}
    for item in attacks:
        if severity_rank.get(clean_text(item.get("severity")), 0) > severity_rank.get(clean_text(highest_attack.get("severity")), 0):
            highest_attack = safe_dict(item)
    return {
        "quality_gate": clean_text(review_package.get("quality_gate")),
        "attack_count": len(attacks),
        "highest_attack": {
            "severity": clean_text(highest_attack.get("severity")),
            "title": clean_text(highest_attack.get("title")),
        },
        "attacks": [
            {
                "severity": clean_text(item.get("severity")),
                "title": clean_text(item.get("title")),
                "detail": clean_text(item.get("detail")),
            }
            for item in attacks[:4]
        ],
        "claims_removed_or_softened": clean_text_list_preview(review_package.get("claims_removed_or_softened"), limit=4),
        "remaining_risks": clean_text_list_preview(review_package.get("remaining_risks"), limit=4),
        "style_learning": summarize_style_learning_surface(style_learning, profile_update_decision),
    }


def build_decision_trace(brief_result: dict[str, Any], draft_result: dict[str, Any], review_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "brief": summarize_brief_decisions(brief_result),
        "draft": summarize_draft_decisions(draft_result),
        "review": summarize_review_decisions(review_result),
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    source_stage = safe_dict(result.get("source_stage"))
    agent_reach_stage = safe_dict(source_stage.get("agent_reach_stage"))
    opencli_stage = safe_dict(source_stage.get("opencli_stage"))
    brief_stage = safe_dict(result.get("brief_stage"))
    draft_stage = safe_dict(result.get("draft_stage"))
    review_stage = safe_dict(result.get("review_stage"))
    final_stage = safe_dict(result.get("final_stage"))
    asset_stage = safe_dict(result.get("asset_stage"))
    feedback_stage = safe_dict(result.get("feedback_stage"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    manual_review = safe_dict(workflow_publication_gate.get("manual_review")) or safe_dict(result.get("manual_review"))
    decision_trace = safe_dict(result.get("decision_trace"))
    brief_trace = safe_dict(decision_trace.get("brief"))
    draft_trace = safe_dict(decision_trace.get("draft"))
    review_trace = safe_dict(decision_trace.get("review"))
    lines = [
        f"# Article Workflow: {clean_text(result.get('topic'))}",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Source stage: {clean_text(source_stage.get('source_kind'))}",
        f"- Brief thesis: {clean_text(brief_stage.get('recommended_thesis')) or 'n/a'}",
        f"- Draft mode: {clean_text(draft_stage.get('draft_mode'))}",
        f"- Draft title: {clean_text(draft_stage.get('title'))}",
        f"- Rewrite mode: {clean_text(final_stage.get('rewrite_mode')) or 'n/a'}",
        f"- Pre-rewrite quality gate: {clean_text(final_stage.get('pre_rewrite_quality_gate')) or 'n/a'}",
        f"- Review quality gate: {clean_text(final_stage.get('quality_gate')) or 'n/a'}",
        f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness') or result.get('publication_readiness')) or 'ready'}",
        f"- Reddit operator review: {clean_text(manual_review.get('status')) or 'not_required'}",
        f"- Images kept: {draft_stage.get('image_count', 0)}",
        f"- Citations kept: {draft_stage.get('citation_count', 0)}",
        "",
        "## Files",
        "",
    ]
    lines.extend(build_source_stage_file_lines(source_stage, include_source_report=True, include_bridge_reports=True))
    lines.extend(
        [
        f"- Brief result: {clean_text(brief_stage.get('result_path')) or 'not written'}",
        f"- Brief report: {clean_text(brief_stage.get('report_path')) or 'not written'}",
        f"- Draft result: {clean_text(draft_stage.get('result_path')) or 'not written'}",
        f"- Draft report: {clean_text(draft_stage.get('report_path')) or 'not written'}",
        f"- Draft preview: {clean_text(draft_stage.get('preview_path')) or 'not written'}",
        f"- Review result: {clean_text(review_stage.get('result_path')) or 'not written'}",
        f"- Review report: {clean_text(review_stage.get('report_path')) or 'not written'}",
        f"- Review template: {clean_text(review_stage.get('revision_template_path')) or 'not written'}",
        f"- Review form: {clean_text(review_stage.get('revision_form_path')) or 'not written'}",
        f"- Feedback markdown: {clean_text(review_stage.get('feedback_markdown_path')) or 'not written'}",
        f"- Final article result: {clean_text(final_stage.get('result_path')) or 'not written'}",
        "",
        "## Next Step",
        "",
        (
            "Use the final article result as a draft only, then review the queued Reddit comment signals before treating community-comment context as publication-ready."
            if manual_review.get("required")
            else "Use the final article result as the current best version, then edit the feedback markdown file for the next revision pass."
        ),
        ]
    )
    lines.extend(build_agent_reach_augmentation_lines(agent_reach_stage))
    lines.extend(build_opencli_augmentation_lines(opencli_stage))
    lines.extend(
        [
            "",
            "## Why This Draft Looks This Way",
            "",
            f"- Recommended thesis: {clean_text(brief_trace.get('recommended_thesis')) or 'none'}",
            f"- Lead confirmed fact: {clean_text(brief_trace.get('lead_canonical_fact')) or 'none'}",
            f"- Main unresolved claim: {clean_text(brief_trace.get('lead_not_proven')) or 'none'}",
            f"- Chosen story angle: {clean_text(brief_trace.get('top_story_angle')) or 'none'}",
            f"- Style applied: language={clean_text(safe_dict(draft_trace.get('style_effective_request')).get('language_mode')) or 'n/a'}, draft_mode={clean_text(safe_dict(draft_trace.get('style_effective_request')).get('draft_mode')) or 'n/a'}, image_strategy={clean_text(safe_dict(draft_trace.get('style_effective_request')).get('image_strategy')) or 'n/a'}, tone={clean_text(safe_dict(draft_trace.get('style_effective_request')).get('tone')) or 'n/a'}, human_signal_ratio={int(safe_dict(draft_trace.get('style_effective_request')).get('human_signal_ratio', 0) or 0)}",
        ]
    )
    for item in clean_text_list_preview(brief_trace.get("voice_constraints"), limit=3):
        lines.append(f"- Voice constraint: {item}")
    for item in clean_text_list_preview(draft_trace.get("writer_risk_notes"), limit=3):
        lines.append(f"- Writer risk note: {item}")
    lines.extend(["", "## Reddit Operator Review", ""])
    lines.append(f"- Status: {clean_text(manual_review.get('status')) or 'not_required'}")
    lines.append(f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness') or manual_review.get('publication_readiness')) or 'ready'}")
    lines.append(f"- Required items: {int(manual_review.get('required_count', 0) or 0)}")
    lines.append(f"- High-priority items: {int(manual_review.get('high_priority_count', 0) or 0)}")
    lines.append(f"- Summary: {clean_text(manual_review.get('summary')) or 'None'}")
    lines.append(f"- Next step: {clean_text(manual_review.get('next_step')) or 'None'}")
    for item in safe_list(manual_review.get("queue")):
        label = clean_text(item.get("title") or item.get("source_name") or item.get("url")) or "queued item"
        lines.append(
            f"- Queue: [{clean_text(item.get('priority_level')) or 'unknown'}] {label} | "
            f"{clean_text(item.get('summary')) or 'operator review required'}"
        )
    if not safe_list(manual_review.get("queue")):
        lines.append("- Queue: None")
    lines.extend(["", "## Claim Support Map", ""])
    for item in safe_list(draft_trace.get("top_claims")):
        lines.append(
            f"- {clean_text(item.get('claim_label'))}: {clean_text(item.get('claim_text'))} | citations: "
            f"{', '.join(clean_text_list_preview(item.get('citation_ids'), limit=4)) or 'none'} | support: {clean_text(item.get('support_level')) or 'unknown'}"
        )
    if not safe_list(draft_trace.get("top_claims")):
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Red Team Summary",
            "",
            f"- Quality gate: {clean_text(review_trace.get('quality_gate')) or 'unknown'}",
            f"- Attack count: {review_trace.get('attack_count', 0)}",
            f"- Highest attack: {clean_text(safe_dict(review_trace.get('highest_attack')).get('severity')).upper() or 'NONE'} | {clean_text(safe_dict(review_trace.get('highest_attack')).get('title')) or 'none'}",
        ]
    )
    for item in safe_list(review_trace.get("attacks")):
        lines.append(f"- Attack: {clean_text(item.get('severity')).upper()} | {clean_text(item.get('title'))} | {clean_text(item.get('detail'))}")
    for item in clean_text_list_preview(review_trace.get("claims_removed_or_softened"), limit=4):
        lines.append(f"- Softened or removed: {item}")
    for item in clean_text_list_preview(review_trace.get("remaining_risks"), limit=4):
        lines.append(f"- Remaining risk: {item}")
    learning_trace = safe_dict(review_trace.get("style_learning"))
    lines.extend(
        [
            "",
            "## Learning Signals",
            "",
            f"- Decision: {clean_text(learning_trace.get('decision')) or 'unknown'}",
            f"- Reason: {clean_text(learning_trace.get('reason')) or 'none'}",
            f"- High-confidence reusable rules: {learning_trace.get('high_confidence_rule_count', 0)}",
            f"- Medium-confidence candidates: {learning_trace.get('medium_confidence_rule_count', 0)}",
            f"- Low-confidence observations: {learning_trace.get('low_confidence_rule_count', 0)}",
            f"- Human change reasons used: {learning_trace.get('explicit_change_count', 0)}",
            f"- Human reusable preferences used: {learning_trace.get('explicit_preference_count', 0)}",
            f"- Human feedback path used: {'yes' if learning_trace.get('used_explicit_feedback') else 'no'}",
        ]
    )
    for item in clean_text_list_preview(learning_trace.get("change_summary_preview"), limit=4):
        lines.append(f"- Learning summary: {item}")
    for item in safe_list(learning_trace.get("high_confidence_rule_preview")):
        lines.append(
            f"- High-confidence rule: {clean_text(item.get('key'))} | scope={clean_text(item.get('scope')) or 'review'} | "
            f"type={clean_text(item.get('rule_type')) or 'unknown'} | confidence={float(item.get('confidence', 0) or 0):.2f}"
        )
    for item in safe_list(learning_trace.get("medium_confidence_rule_preview")):
        lines.append(
            f"- Medium-confidence rule: {clean_text(item.get('key'))} | scope={clean_text(item.get('scope')) or 'review'} | "
            f"type={clean_text(item.get('rule_type')) or 'unknown'} | confidence={float(item.get('confidence', 0) or 0):.2f}"
        )
    for item in safe_list(learning_trace.get("low_confidence_rule_preview")):
        lines.append(
            f"- Low-confidence rule: {clean_text(item.get('key'))} | scope={clean_text(item.get('scope')) or 'review'} | "
            f"type={clean_text(item.get('rule_type')) or 'unknown'} | confidence={float(item.get('confidence', 0) or 0):.2f}"
        )
    for item in clean_text_list_preview(learning_trace.get("excluded_signals_preview"), limit=3):
        lines.append(f"- Excluded signal: {item}")
    for key, value in safe_dict(learning_trace.get("proposed_defaults")).items():
        lines.append(f"- Proposed default: {clean_text(key)} = {value}")
    cleanup_stage = safe_dict(result.get("cleanup_stage"))
    if cleanup_stage:
        lines.extend(
            [
                "",
                "## Cleanup",
                "",
                f"- Cleanup root: {clean_text(cleanup_stage.get('root_dir')) or 'none'}",
                f"- Retention days: {cleanup_stage.get('retention_days', 0)}",
                f"- Removed this run: {cleanup_stage.get('removed_count', 0)}",
                f"- Still kept: {cleanup_stage.get('kept_count', 0)}",
            ]
        )
    suggested_command = clean_text(review_stage.get("suggested_revise_command"))
    if suggested_command:
        lines.extend(["", "```text", suggested_command, "```"])
    if asset_stage:
        lines.extend(
            [
                "",
                "## Images",
                "",
                f"- Local images ready: {asset_stage.get('local_ready_count', 0)}",
                f"- Remote-only images left: {asset_stage.get('remote_only_count', 0)}",
                f"- Missing images: {asset_stage.get('missing_count', 0)}",
                f"- Download attempts this run: {asset_stage.get('downloaded_count', 0)}",
                f"- Download failures this run: {asset_stage.get('failed_count', 0)}",
                f"- Asset directory: {clean_text(asset_stage.get('asset_output_dir')) or 'not set'}",
            ]
        )
        hydrate_command = clean_text(asset_stage.get("suggested_asset_hydrate_command"))
        if hydrate_command:
            lines.extend(["", "Retry image hydration with:", "", "```text", hydrate_command, "```"])
    if feedback_stage:
        applied_paths = safe_list(feedback_stage.get("applied_paths"))
        lines.extend(
            [
                "",
                "## Feedback Reuse",
                "",
                f"- Profile directory: {clean_text(feedback_stage.get('profile_dir')) or 'none'}",
                f"- Applied profiles now: {', '.join(applied_paths) if applied_paths else 'none'}",
                f"- Global defaults file: {clean_text(feedback_stage.get('global_profile_path')) or 'none'} ({'saved' if feedback_stage.get('global_exists') else 'not saved yet'})",
                f"- Topic defaults file: {clean_text(feedback_stage.get('topic_profile_path')) or 'none'} ({'saved' if feedback_stage.get('topic_exists') else 'not saved yet'})",
                f"- Global backup snapshots: {feedback_stage.get('global_history_count', 0)}",
                f"- Topic backup snapshots: {feedback_stage.get('topic_history_count', 0)}",
                "- To save this draft style for all future drafts, set `Persist feedback scope: global` in the feedback markdown file.",
                "- To save it only for this topic, set `Persist feedback scope: topic` in the feedback markdown file.",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_article_workflow(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_workflow_request(raw_payload)
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

    source_payload, source_kind, agent_reach_stage, opencli_stage = prepare_source_payload(request)
    source_stage = write_source_stage_outputs(
        request["output_dir"],
        source_kind=source_kind,
        source_payload=source_payload,
        agent_reach_stage=agent_reach_stage,
        opencli_stage=opencli_stage,
        write_json=write_json,
    )

    brief_payload = build_brief_payload(request, source_payload)
    brief_result = build_analysis_brief(brief_payload)
    manual_review = build_reddit_operator_review_manual_state(safe_dict(brief_result.get("source_summary")))
    brief_result_path = request["output_dir"] / "analysis-brief-result.json"
    brief_report_path = request["output_dir"] / "analysis-brief-report.md"
    write_json(brief_result_path, brief_result)
    brief_report_path.write_text(brief_result.get("report_markdown", ""), encoding="utf-8-sig")

    # --- Angle restructure: pick a non-default story angle so the draft
    #     cuts in from a different direction than the source articles ---
    request = restructure_angle(request, brief_result)

    draft_payload = build_draft_payload(request, source_payload)
    draft_payload["analysis_brief"] = safe_dict(brief_result.get("analysis_brief"))
    draft_payload["analysis_brief_path"] = str(brief_result_path)
    draft_payload["evidence_bundle"] = deepcopy(safe_dict(brief_result.get("evidence_bundle")))
    draft_result = build_article_draft(draft_payload)
    draft_result_path = request["output_dir"] / "article-draft-result.json"
    draft_report_path = request["output_dir"] / "article-draft-report.md"
    draft_preview_path = request["output_dir"] / "article-draft-preview.html"
    write_json(draft_result_path, draft_result)
    draft_report_path.write_text(draft_result.get("report_markdown", ""), encoding="utf-8-sig")
    draft_preview_path.write_text(draft_result.get("preview_html", ""), encoding="utf-8-sig")

    review_result = build_article_revision(
        {
            "draft_result": draft_result,
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "feedback_profile_dir": request.get("feedback_profile_dir"),
        }
    )
    review_result_path = request["output_dir"] / "article-revise-result.json"
    review_report_path = request["output_dir"] / "article-revise-report.md"
    review_preview_path = request["output_dir"] / "article-revise-preview.html"
    final_article_result_path = request["output_dir"] / "final-article-result.json"
    write_json(review_result_path, review_result)
    review_report_path.write_text(review_result.get("report_markdown", ""), encoding="utf-8-sig")
    review_preview_path.write_text(review_result.get("preview_html", ""), encoding="utf-8-sig")
    workflow_publication_gate = build_workflow_publication_gate(
        {
            "manual_review": manual_review,
            "publication_readiness": clean_text(manual_review.get("publication_readiness")) or "ready",
        }
    )
    final_article_result = deepcopy(safe_dict(review_result.get("final_article_result")))
    final_article_result["manual_review"] = deepcopy(manual_review)
    final_article_result["publication_readiness"] = clean_text(workflow_publication_gate.get("publication_readiness")) or "ready"
    final_article_result["workflow_publication_gate"] = deepcopy(workflow_publication_gate)
    write_json(final_article_result_path, final_article_result)

    revision_template = build_revision_template(draft_result)
    revision_template_path = request["output_dir"] / "article-revise-template.json"
    revision_form_path = request["output_dir"] / "article-revise-form.md"
    feedback_markdown_path = request["output_dir"] / "ARTICLE-FEEDBACK.md"
    feedback_markdown = build_feedback_markdown(draft_result, revision_template, draft_result_path=str(draft_result_path))
    write_json(revision_template_path, revision_template)
    revision_form_path.write_text(feedback_markdown, encoding="utf-8-sig")
    feedback_markdown_path.write_text(feedback_markdown, encoding="utf-8-sig")

    article_package = safe_dict(draft_result.get("article_package"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
    citations = safe_list(article_package.get("citations"))
    asset_stage = summarize_asset_stage(review_result, review_result_path)
    feedback_stage = summarize_feedback_stage(review_result)
    decision_trace = build_decision_trace(brief_result, draft_result, review_result)
    learning_stage = safe_dict(safe_dict(decision_trace.get("review")).get("style_learning"))
    result = {
        "status": "ok",
        "workflow_kind": "article_workflow",
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
        "manual_review": manual_review,
        "workflow_publication_gate": workflow_publication_gate,
        "source_stage": source_stage,
        "brief_stage": {
            "result_path": str(brief_result_path),
            "report_path": str(brief_report_path),
            "evidence_bundle_contract": clean_text(safe_dict(brief_result.get("evidence_bundle")).get("contract_version")),
            "evidence_bundle_citation_count": len(safe_list(safe_dict(brief_result.get("evidence_bundle")).get("citations"))),
            "evidence_bundle_image_candidate_count": len(safe_list(safe_dict(brief_result.get("evidence_bundle")).get("image_candidates"))),
            "recommended_thesis": clean_text(safe_dict(brief_result.get("analysis_brief")).get("recommended_thesis")),
            "canonical_fact_count": len(safe_list(safe_dict(brief_result.get("analysis_brief")).get("canonical_facts"))),
            "not_proven_count": len(safe_list(safe_dict(brief_result.get("analysis_brief")).get("not_proven"))),
            "top_story_angle": clean_text(
                safe_dict((safe_list(safe_dict(brief_result.get("analysis_brief")).get("story_angles")) or [{}])[0]).get("angle")
            ),
        },
        "draft_stage": {
            "result_path": str(draft_result_path),
            "report_path": str(draft_report_path),
            "preview_path": str(draft_preview_path),
            "title": clean_text(article_package.get("title")),
            "draft_thesis": clean_text(article_package.get("draft_thesis")),
            "draft_mode": clean_text(article_package.get("draft_mode")),
            "style_profile_applied": deepcopy(safe_dict(article_package.get("style_profile_applied"))),
            "image_count": len(selected_images),
            "citation_count": len(citations),
        },
        "cleanup_stage": cleanup_stage,
        "asset_stage": asset_stage,
        "feedback_stage": feedback_stage,
        "learning_stage": learning_stage,
        "review_stage": {
            "result_path": str(review_result_path),
            "report_path": str(review_report_path),
            "preview_path": str(review_preview_path),
            "revision_template_path": str(revision_template_path),
            "revision_form_path": str(revision_form_path),
            "feedback_markdown_path": str(feedback_markdown_path),
            "attack_count": len(safe_list(safe_dict(review_result.get("review_rewrite_package")).get("attacks"))),
            "claims_softened_count": len(clean_text_list_preview(safe_dict(review_result.get("review_rewrite_package")).get("claims_removed_or_softened"), limit=20)),
            "learning_decision": clean_text(learning_stage.get("decision")),
            "learning_reason": clean_text(learning_stage.get("reason")),
            "learning_change_summary_preview": deepcopy(safe_list(learning_stage.get("change_summary_preview"))),
            "learning_proposed_default_keys": deepcopy(safe_list(learning_stage.get("proposed_default_keys"))),
            "suggested_revise_command": (
                f"financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_article_revise.cmd "
                f"\"{draft_result_path}\" \"{feedback_markdown_path}\" --output \"{request['output_dir'] / 'article-revise-result.json'}\" "
                f"--markdown-output \"{request['output_dir'] / 'article-revise-report.md'}\""
            ),
        },
        "final_stage": {
            "result_path": str(final_article_result_path),
            "rewrite_mode": clean_text(safe_dict(review_result.get("review_rewrite_package")).get("rewrite_mode")),
            "pre_rewrite_quality_gate": clean_text(safe_dict(review_result.get("review_rewrite_package")).get("pre_rewrite_quality_gate")),
            "quality_gate": clean_text(safe_dict(review_result.get("review_rewrite_package")).get("quality_gate")),
            "draft_thesis": clean_text(safe_dict(review_result.get("final_article_result")).get("draft_thesis")),
            "manual_review_required": bool(manual_review.get("required")),
            "manual_review_status": clean_text(manual_review.get("status")) or "not_required",
            "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
            "workflow_publication_gate": deepcopy(workflow_publication_gate),
        },
        "source_result": source_payload,
        "analysis_brief": safe_dict(brief_result.get("analysis_brief")),
        "draft_result": draft_result,
        "review_result": review_result,
        "final_article_result": final_article_result,
        "decision_trace": decision_trace,
    }
    result["report_markdown"] = build_report_markdown(result)
    workflow_report_path = request["output_dir"] / "workflow-report.md"
    workflow_report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["workflow_report_path"] = str(workflow_report_path)
    return result


__all__ = ["build_revision_template", "load_json", "run_article_workflow", "write_json"]
