#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from article_feedback_profiles import (
    feedback_profile_status,
    normalize_profile_feedback,
    parse_bool,
    request_defaults_from_request,
    resolve_profile_dir,
    save_feedback_profiles_detailed,
)
from article_draft_flow_runtime import (
    assemble_article_package,
    build_article_preview_html,
    build_report_markdown,
    clean_string_list,
    clean_text,
    draft_metrics,
    load_json,
    localize_selected_images,
    merge_localized_image_candidates,
    safe_dict,
    safe_list,
    sanitize_draft_mode,
    write_json,
)
from article_style_learning import (
    build_revision_diff,
    build_style_learning,
    human_feedback_form_to_edit_reason_feedback,
    merge_edit_reason_feedback,
    normalize_edit_reason_feedback,
    normalize_human_feedback_form,
)
from news_index_runtime import isoformat_or_blank, parse_datetime


ARTICLE_REBUILD_KEYS = (
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
    "image_strategy",
    "draft_mode",
    "language_mode",
    "must_include",
    "must_avoid",
)


def load_draft_result(raw_payload: dict[str, Any]) -> dict[str, Any]:
    draft_result = raw_payload.get("draft_result") or raw_payload.get("article_result")
    if isinstance(draft_result, dict):
        return deepcopy(draft_result)

    draft_result_path = clean_text(
        raw_payload.get("draft_result_path") or raw_payload.get("article_result_path") or raw_payload.get("source_path")
    )
    if not draft_result_path:
        raise ValueError("article-revise requires draft_result/article_result or a matching *_path")
    return load_json(Path(draft_result_path).resolve())


def normalize_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    feedback = safe_dict(payload.get("feedback"))
    feedback_notes = clean_string_list(payload.get("feedback_notes"))
    if clean_text(feedback.get("summary")):
        feedback_notes.append(clean_text(feedback.get("summary")))
    if clean_text(payload.get("revision_note")):
        feedback_notes.append(clean_text(payload.get("revision_note")))
    drop_image_ids = clean_string_list(
        payload.get("drop_image_ids") or payload.get("drop_image_asset_ids") or feedback.get("drop_image_asset_ids")
    )
    keep_image_ids = clean_string_list(
        payload.get("pinned_image_ids") or payload.get("pin_image_ids") or feedback.get("keep_image_asset_ids")
    )
    return {
        "feedback_notes": feedback_notes,
        "drop_image_ids": drop_image_ids,
        "keep_image_ids": keep_image_ids,
        "summary": clean_text(feedback.get("summary")),
    }


def derive_persist_feedback(
    raw_persist_feedback: Any,
    edit_reason_feedback: Any,
) -> dict[str, Any]:
    explicit = normalize_profile_feedback(raw_persist_feedback)
    if explicit.get("scope") != "none":
        return explicit

    normalized_feedback = normalize_edit_reason_feedback(edit_reason_feedback)
    reusable_preferences = [
        item
        for item in safe_list(normalized_feedback.get("reusable_preferences"))
        if clean_text(item.get("key")) and normalize_profile_feedback({"scope": item.get("scope")}).get("scope") in {"topic", "global"}
    ]
    if not reusable_preferences:
        return explicit

    scopes = {
        normalize_profile_feedback({"scope": item.get("scope")}).get("scope")
        for item in reusable_preferences
        if normalize_profile_feedback({"scope": item.get("scope")}).get("scope") in {"topic", "global"}
    }
    if len(scopes) != 1:
        return explicit

    defaults: dict[str, Any] = {}
    for item in reusable_preferences:
        key = clean_text(item.get("key")).lower()
        value = item.get("value")
        if key in {"must_include", "must_avoid"}:
            existing = clean_string_list(defaults.get(key))
            additions = clean_string_list(value)
            merged = existing + [entry for entry in additions if entry not in existing]
            if merged:
                defaults[key] = merged
            continue
        if value not in (None, "", []):
            defaults[key] = value

    if not defaults:
        return explicit

    derived_notes = clean_string_list(
        safe_list(explicit.get("notes"))
        + [
            "Auto-derived from reusable preferences in the human review form.",
            clean_text(normalized_feedback.get("summary")),
        ]
        + [clean_text(item.get("why")) for item in reusable_preferences]
    )
    return normalize_profile_feedback(
        {
            "scope": next(iter(scopes)),
            "defaults": defaults,
            "notes": derived_notes,
            "use_current_request_defaults": False,
        }
    )


def normalize_revision_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    article_result = load_draft_result(raw_payload)
    prior_request = safe_dict(article_result.get("request"))
    source_summary = safe_dict(article_result.get("source_summary")) or safe_dict(article_result.get("source_context"))
    feedback = normalize_feedback(raw_payload)
    explicit_edit_reason_feedback = normalize_edit_reason_feedback(raw_payload.get("edit_reason_feedback"))
    human_feedback_form = normalize_human_feedback_form(raw_payload.get("human_feedback_form"))
    merged_edit_reason_feedback = merge_edit_reason_feedback(
        explicit_edit_reason_feedback,
        human_feedback_form_to_edit_reason_feedback(human_feedback_form),
    )
    persist_feedback = derive_persist_feedback(raw_payload.get("persist_feedback"), merged_edit_reason_feedback)

    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None) or parse_datetime(
        prior_request.get("analysis_time"),
        fallback=parse_datetime(source_summary.get("analysis_time")),
    )
    if analysis_time is None:
        raise ValueError("Unable to determine analysis_time for article revision")

    return {
        "analysis_time": analysis_time,
        "topic": clean_text(raw_payload.get("topic") or prior_request.get("topic") or source_summary.get("topic")),
        "title_hint": clean_text(raw_payload.get("title_hint") or raw_payload.get("title_override") or prior_request.get("title_hint")),
        "title_hint_zh": clean_text(raw_payload.get("title_hint_zh") or prior_request.get("title_hint_zh")),
        "subtitle_hint": clean_text(raw_payload.get("subtitle_hint") or raw_payload.get("subtitle_override") or prior_request.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(raw_payload.get("subtitle_hint_zh") or prior_request.get("subtitle_hint_zh")),
        "angle": clean_text(raw_payload.get("angle") or prior_request.get("angle")),
        "angle_zh": clean_text(raw_payload.get("angle_zh") or prior_request.get("angle_zh")),
        "tone": clean_text(
            raw_payload.get("tone") or safe_dict(raw_payload.get("feedback")).get("tone") or prior_request.get("tone") or "neutral-cautious"
        ),
        "target_length_chars": int(
            raw_payload.get("target_length_chars", raw_payload.get("target_length", prior_request.get("target_length_chars", 1000)))
        ),
        "max_images": max(0, min(int(raw_payload.get("max_images", prior_request.get("max_images", 3))), 8)),
        "image_strategy": clean_text(raw_payload.get("image_strategy") or prior_request.get("image_strategy") or "mixed"),
        "draft_mode": sanitize_draft_mode(raw_payload.get("draft_mode") or prior_request.get("draft_mode")),
        "language_mode": clean_text(raw_payload.get("language_mode") or prior_request.get("language_mode") or "english"),
        "must_include": clean_string_list(raw_payload.get("must_include") or prior_request.get("must_include")),
        "must_avoid": clean_string_list(raw_payload.get("must_avoid") or prior_request.get("must_avoid")),
        "asset_output_dir": clean_text(raw_payload.get("asset_output_dir") or safe_dict(article_result.get("draft_context")).get("asset_output_dir")),
        "download_remote_images": True,
        "feedback_profile_dir": clean_text(raw_payload.get("feedback_profile_dir") or prior_request.get("feedback_profile_dir")),
        "persist_feedback": persist_feedback,
        "edited_body_markdown": raw_payload.get("edited_body_markdown") if isinstance(raw_payload.get("edited_body_markdown"), str) else "",
        "edited_article_markdown": raw_payload.get("edited_article_markdown") if isinstance(raw_payload.get("edited_article_markdown"), str) else "",
        "edit_reason_feedback": merged_edit_reason_feedback,
        "human_feedback_form": human_feedback_form,
        "allow_auto_rewrite_after_manual": parse_bool(raw_payload.get("allow_auto_rewrite_after_manual"), default=False),
        "article_result": article_result,
        "feedback": feedback,
    }


def reorder_candidates(image_candidates: list[dict[str, Any]], keep_image_ids: list[str], drop_image_ids: list[str]) -> list[dict[str, Any]]:
    keep = set(clean_string_list(keep_image_ids))
    drop = set(clean_string_list(drop_image_ids))
    filtered = []
    for item in image_candidates:
        image_id = clean_text(item.get("image_id") or item.get("asset_id"))
        if image_id and image_id in drop:
            continue
        filtered.append(item)

    if not keep:
        return filtered

    by_id = {clean_text(item.get("image_id") or item.get("asset_id")): item for item in filtered}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for image_id in keep:
        if image_id in by_id:
            ordered.append(by_id[image_id])
            seen.add(image_id)
    for item in filtered:
        image_id = clean_text(item.get("image_id") or item.get("asset_id"))
        if image_id in seen:
            continue
        ordered.append(item)
    return ordered


def preserve_localized_image_assets(
    image_candidates: list[dict[str, Any]],
    *cached_image_sets: Any,
) -> list[dict[str, Any]]:
    cached_images: list[dict[str, Any]] = []
    for image_set in cached_image_sets:
        cached_images.extend(item for item in safe_list(image_set) if isinstance(item, dict))
    return merge_localized_image_candidates(image_candidates, cached_images)


def normalize_rebuild_value(key: str, value: Any) -> Any:
    if key in {"must_include", "must_avoid"}:
        return clean_string_list(value)
    if key in {"target_length_chars", "max_images"}:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
    return clean_text(value)


def request_needs_package_rebuild(request: dict[str, Any], prior_request: dict[str, Any]) -> bool:
    for key in ARTICLE_REBUILD_KEYS:
        if normalize_rebuild_value(key, request.get(key)) != normalize_rebuild_value(key, prior_request.get(key)):
            return True
    if clean_string_list(safe_dict(request.get("feedback")).get("keep_image_ids")):
        return True
    if clean_string_list(safe_dict(request.get("feedback")).get("drop_image_ids")):
        return True
    return False


def article_text(article_package: dict[str, Any]) -> str:
    return "\n".join(
        [
            clean_text(article_package.get("title")),
            clean_text(article_package.get("subtitle")),
            clean_text(article_package.get("lede")),
            clean_text(article_package.get("body_markdown")),
            clean_text(article_package.get("article_markdown")),
        ]
    ).lower()


def has_boundary_language(text: str) -> bool:
    markers = [
        "not proven",
        "not confirmed",
        "unclear",
        "inference",
        "last public indication",
        "still does not confirm",
        "not enough to confirm",
        "does not prove",
        "未证实",
        "未确认",
        "不明确",
        "推断",
        "最后公开迹象",
        "仍不足以确认",
        "不能证明",
    ]
    lowered = text.lower()
    return any(marker in lowered or marker in text for marker in markers)


def collect_non_core_promoted_claims(article_package: dict[str, Any], citation_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    flagged: list[dict[str, Any]] = []
    for item in safe_list(article_package.get("draft_claim_map")):
        claim_text = clean_text(item.get("claim_text"))
        if not claim_text:
            continue
        claim_label = clean_text(item.get("claim_label")) or "claim"
        if claim_label == "thesis":
            continue
        support_level = clean_text(item.get("support_level"))
        if support_level not in {"core", "derived"}:
            continue
        citation_ids = clean_string_list(item.get("citation_ids"))
        supporting_citations = [citation_by_id[citation_id] for citation_id in citation_ids if citation_id in citation_by_id]
        if not supporting_citations:
            continue
        if any(clean_text(citation.get("channel")) == "core" for citation in supporting_citations):
            continue
        flagged.append(
            {
                "claim_label": claim_label,
                "claim_text": claim_text,
                "citation_count": len(supporting_citations),
                "source_count": len(
                    {
                        clean_text(citation.get("source_id") or citation.get("source_name") or citation.get("citation_id"))
                        for citation in supporting_citations
                        if clean_text(citation.get("source_id") or citation.get("source_name") or citation.get("citation_id"))
                    }
                ),
            }
        )
    return flagged


def build_red_team_review(
    article_package: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    text = article_text(article_package)
    citation_by_id = {clean_text(item.get("citation_id")): item for item in citations if clean_text(item.get("citation_id"))}
    attacks: list[dict[str, Any]] = []
    softened: list[str] = []

    thesis_entry = {}
    for item in safe_list(article_package.get("draft_claim_map")):
        if clean_text(item.get("claim_label")) == "thesis":
            thesis_entry = item
            break
    thesis_citations = [
        citation_by_id[citation_id]
        for citation_id in clean_string_list(safe_dict(thesis_entry).get("citation_ids"))
        if citation_id in citation_by_id
    ]
    thesis_shadow_heavy = clean_text(safe_dict(thesis_entry).get("support_level")) == "shadow-heavy"
    thesis_shadow_only = thesis_citations and not any(clean_text(item.get("channel")) == "core" for item in thesis_citations)
    thesis_single_shadow = thesis_shadow_only and len({clean_text(item.get("citation_id")) for item in thesis_citations}) == 1
    thesis_unacceptable = thesis_single_shadow or (thesis_shadow_heavy and len(thesis_citations) <= 1)
    if thesis_unacceptable:
        attacks.append(
            {
                "attack_id": "shadow-single-source-thesis",
                "severity": "critical",
                "title": "The main thesis is hanging on a single shadow source.",
                "detail": "A single lower-confidence source cannot carry the article's lead conclusion by itself.",
            }
        )
        softened.append(clean_text(safe_dict(thesis_entry).get("claim_text")))

    uncited_promoted_claims = []
    for item in safe_list(article_package.get("draft_claim_map")):
        claim_text = clean_text(item.get("claim_text"))
        if not claim_text:
            continue
        support_level = clean_text(item.get("support_level"))
        citation_ids = clean_string_list(item.get("citation_ids"))
        if support_level in {"core", "derived"} and not citation_ids:
            uncited_promoted_claims.append(
                {
                    "claim_label": clean_text(item.get("claim_label")) or "claim",
                    "claim_text": claim_text,
                    "support_level": support_level,
                }
            )
    if uncited_promoted_claims:
        uncited_thesis = any(item.get("claim_label") == "thesis" for item in uncited_promoted_claims)
        attacks.append(
            {
                "attack_id": "uncited-promoted-claims",
                "severity": "critical" if uncited_thesis else "major",
                "title": "One or more promoted draft claims lost their citation backing.",
                "detail": (
                    f"{len(uncited_promoted_claims)} promoted claim(s) appear in the draft claim map without any citation IDs. "
                    "A promoted claim should not survive as a main article judgment unless it is traceable."
                ),
            }
        )
        softened.extend(item.get("claim_text", "") for item in uncited_promoted_claims)

    non_core_promoted_claims = collect_non_core_promoted_claims(article_package, citation_by_id)
    if non_core_promoted_claims:
        attacks.append(
            {
                "attack_id": "non-core-promoted-claims",
                "severity": "major",
                "title": "Some promoted claims still rely only on non-core evidence.",
                "detail": (
                    f"{len(non_core_promoted_claims)} promoted claim(s) are backed only by shadow/background citations. "
                    "Those claims should be softened or moved out of the confirmed-facts lane."
                ),
            }
        )
        softened.extend(item.get("claim_text", "") for item in non_core_promoted_claims)

    not_proven = safe_list(analysis_brief.get("not_proven"))
    if not_proven and not has_boundary_language(text):
        attacks.append(
            {
                "attack_id": "missing-boundary-language",
                "severity": "major",
                "title": "The draft does not clearly separate confirmed facts from unsupported leaps.",
                "detail": "At least one unresolved claim exists, but the article text is not explicit enough about that boundary.",
            }
        )
        softened.extend(clean_text(item.get("claim_text")) for item in not_proven[:2])

    location_overreach_markers = [
        "actual position",
        "confirmed position",
        "live position",
        "already in position",
        "arrived on station",
        "deployed there now",
        "at the target area",
        "已经到位",
        "已部署到位",
        "实时位置",
    ]
    blocked_or_shadow_images = [
        item
        for item in images
        if clean_text(item.get("access_mode")) == "blocked"
        or clean_text(item.get("status")) != "local_ready"
        or int(item.get("source_tier", 3) or 3) >= 2
    ]
    if blocked_or_shadow_images and any(marker in text for marker in location_overreach_markers):
        attacks.append(
            {
                "attack_id": "visual-overreach",
                "severity": "critical",
                "title": "The draft overstates what the visual evidence can prove.",
                "detail": "The current image layer can support only a last-public-indication framing, not a claim of exact live position.",
            }
        )

    if (
        int(source_summary.get("blocked_source_count", 0) or 0) > 0
        and "blocked" not in text
        and "inaccessible" not in text
        and "无法访问" not in text
        and "不可访问" not in text
    ):
        attacks.append(
            {
                "attack_id": "blocked-sources-hidden",
                "severity": "major",
                "title": "Blocked sources exist, but the draft does not surface that limitation clearly enough.",
                "detail": "Readers should be told where the package still has inaccessible evidence.",
            }
        )

    remaining_risks = clean_string_list(analysis_brief.get("misread_risks"))
    if thesis_unacceptable or any(item.get("severity") == "critical" for item in attacks):
        quality_gate = "block"
    elif attacks:
        quality_gate = "revise"
    else:
        quality_gate = "pass"

    return {
        "attacks": attacks,
        "claims_removed_or_softened": clean_string_list(softened),
        "remaining_risks": remaining_risks[:4],
        "quality_gate": quality_gate,
    }


def rewrite_request_after_attack(request: dict[str, Any], analysis_brief: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    rewritten = deepcopy(request)
    existing_include = clean_string_list(rewritten.get("must_include"))
    existing_avoid = clean_string_list(rewritten.get("must_avoid"))
    voice_constraints = clean_string_list(analysis_brief.get("voice_constraints"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    attack_ids = {clean_text(item.get("attack_id")) for item in safe_list(review.get("attacks"))}

    include_updates = [
        "state the strongest confirmed fact before any scenario",
        "name the main unsupported leap explicitly",
    ]
    if not_proven:
        include_updates.append(f"treat this as not proven unless upgraded: {clean_text(not_proven[0].get('claim_text'))}")
    if voice_constraints:
        include_updates.extend(voice_constraints[:2])
    if "non-core-promoted-claims" in attack_ids:
        include_updates.append("keep non-core signals out of the confirmed-facts lane unless stronger sourcing appears")
    if "blocked-sources-hidden" in attack_ids:
        include_updates.append("say clearly when important sources were blocked or inaccessible")
    rewritten["must_include"] = clean_string_list(existing_include + include_updates)
    rewritten["must_avoid"] = clean_string_list(existing_avoid + ["actual position", "confirmed position", "live position"])
    rewritten["tone"] = clean_text(rewritten.get("tone") or "neutral-cautious") or "neutral-cautious"
    if safe_list(analysis_brief.get("story_angles")):
        rewritten["angle"] = clean_text(safe_dict(safe_list(analysis_brief.get("story_angles"))[0]).get("angle")) or rewritten.get("angle")
    rewritten["red_team_applied"] = True
    rewritten["red_team_quality_gate"] = clean_text(review.get("quality_gate"))
    return rewritten


def build_review_report_markdown(article_package: dict[str, Any], review_package: dict[str, Any]) -> str:
    lines = [build_report_markdown(article_package).rstrip(), "", "## Red Team Review", ""]
    lines.append(f"- Rewrite mode: {clean_text(review_package.get('rewrite_mode')) or 'auto_rewrite'}")
    lines.append(f"- Base package mode: {clean_text(review_package.get('base_package_mode')) or 'unknown'}")
    lines.append(
        f"- Pre-rewrite quality gate: {clean_text(review_package.get('pre_rewrite_quality_gate')) or clean_text(review_package.get('quality_gate')) or 'unknown'}"
    )
    lines.append(f"- Final quality gate: {clean_text(review_package.get('quality_gate')) or 'unknown'}")
    if clean_text(review_package.get("rewrite_decision_reason")):
        lines.append(f"- Rewrite decision: {clean_text(review_package.get('rewrite_decision_reason'))}")
    lines.append("")
    pre_attacks = safe_list(review_package.get("pre_rewrite_attacks"))
    if pre_attacks:
        lines.append("### Pre-Rewrite Attacks")
        for item in pre_attacks:
            lines.append(
                f"- {clean_text(item.get('severity')).upper()}: {clean_text(item.get('title'))} | {clean_text(item.get('detail'))}"
            )
        lines.append("")
    lines.append("### Attacks")
    attacks = safe_list(review_package.get("attacks"))
    if attacks:
        for item in attacks:
            lines.append(
                f"- {clean_text(item.get('severity')).upper()}: {clean_text(item.get('title'))} | {clean_text(item.get('detail'))}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "### Claims Removed Or Softened"])
    softened = clean_string_list(review_package.get("claims_removed_or_softened"))
    if softened:
        for item in softened:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.extend(["", "### Remaining Risks"])
    for item in clean_string_list(review_package.get("remaining_risks")):
        lines.append(f"- {item}")
    if not clean_string_list(review_package.get("remaining_risks")):
        lines.append("- None")
    style_learning = safe_dict(review_package.get("style_learning"))
    profile_update_decision = safe_dict(review_package.get("profile_update_decision"))
    lines.extend(["", "## Style Learning", ""])
    lines.append(
        f"- Decision: {clean_text(profile_update_decision.get('status')) or 'unknown'} | "
        f"{clean_text(profile_update_decision.get('reason')) or 'No learning decision recorded.'}"
    )
    for item in clean_string_list(style_learning.get("change_summary")):
        lines.append(f"- Change summary: {item}")
    high_rules = safe_list(style_learning.get("high_confidence_rules"))
    medium_rules = safe_list(style_learning.get("medium_confidence_rules"))
    low_rules = safe_list(style_learning.get("low_confidence_rules"))
    lines.append(f"- High-confidence reusable rules: {len(high_rules)}")
    lines.append(f"- Medium-confidence candidates: {len(medium_rules)}")
    lines.append(f"- Low-confidence observations: {len(low_rules)}")
    lines.append(f"- Human change reasons used: {int(style_learning.get('explicit_change_count', 0) or 0)}")
    lines.append(f"- Human reusable preferences used: {int(style_learning.get('explicit_preference_count', 0) or 0)}")
    human_feedback_form = safe_dict(review_package.get("human_feedback_form"))
    if human_feedback_form:
        lines.append(
            f"- Human-friendly form entries: "
            f"change_requests={len(safe_list(human_feedback_form.get('what_to_change')))}, "
            f"remember_next_time={len(safe_list(human_feedback_form.get('what_to_remember_next_time')))}, "
            f"one_off_fixes={len(safe_list(human_feedback_form.get('one_off_fixes_not_style')))}"
        )
    proposed_defaults = safe_dict(safe_dict(style_learning.get("proposed_profile_feedback")).get("defaults"))
    if proposed_defaults:
        for key, value in proposed_defaults.items():
            lines.append(f"- Proposed default: {clean_text(key)} = {value}")
    for item in clean_string_list(style_learning.get("excluded_signals")):
        lines.append(f"- Excluded from reuse: {item}")
    return "\n".join(lines).strip() + "\n"


def resolve_revision_evidence_bundle(article_result: dict[str, Any], draft_context: dict[str, Any]) -> dict[str, Any]:
    bundle = safe_dict(article_result.get("evidence_bundle")) or safe_dict(draft_context.get("evidence_bundle"))
    if clean_text(bundle.get("contract_version")):
        return deepcopy(bundle)
    return {}


def matching_cached_feedback_profile_status(request: dict[str, Any], *candidates: Any) -> dict[str, Any]:
    profile_dir = str(resolve_profile_dir(request.get("feedback_profile_dir")))
    topic = clean_text(request.get("topic"))
    for candidate in candidates:
        status = safe_dict(candidate)
        if (
            clean_text(status.get("profile_dir")) == profile_dir
            and clean_text(status.get("topic")) == topic
        ):
            return deepcopy(status)
    return {}


def build_article_revision(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_revision_request(raw_payload)
    article_result = deepcopy(request["article_result"])
    prior_request = safe_dict(article_result.get("request"))
    draft_context = deepcopy(safe_dict(article_result.get("draft_context")))
    revision_evidence_bundle = resolve_revision_evidence_bundle(article_result, draft_context)
    source_summary = deepcopy(
        safe_dict(revision_evidence_bundle.get("source_summary"))
        or safe_dict(article_result.get("source_summary"))
        or safe_dict(article_result.get("source_context"))
    )
    evidence_digest = deepcopy(
        safe_dict(revision_evidence_bundle.get("evidence_digest"))
        or safe_dict(article_result.get("evidence_digest"))
    )
    analysis_brief = deepcopy(
        safe_dict(article_result.get("analysis_brief"))
        or safe_dict(draft_context.get("analysis_brief"))
        or safe_dict(safe_dict(safe_dict(article_result.get("article_package")).get("render_context")).get("analysis_brief"))
    )

    citations = deepcopy(safe_list(revision_evidence_bundle.get("citations"))) or deepcopy(safe_list(draft_context.get("citation_candidates"))) or deepcopy(
        safe_list(safe_dict(article_result.get("article_package")).get("citations"))
    )
    image_candidates = deepcopy(safe_list(revision_evidence_bundle.get("image_candidates"))) or deepcopy(
        safe_list(draft_context.get("image_candidates"))
    )
    if not image_candidates:
        image_candidates = deepcopy(
            safe_list(safe_dict(article_result.get("article_package")).get("selected_images"))
            or safe_list(safe_dict(article_result.get("article_package")).get("image_blocks"))
        )
    image_candidates = preserve_localized_image_assets(
        image_candidates,
        safe_list(safe_dict(article_result.get("article_package")).get("selected_images"))
        or safe_list(safe_dict(article_result.get("article_package")).get("image_blocks")),
        draft_context.get("selected_images"),
    )
    image_candidates = reorder_candidates(
        image_candidates,
        request["feedback"].get("keep_image_ids", []),
        request["feedback"].get("drop_image_ids", []),
    )

    source_summary["topic"] = clean_text(request.get("topic")) or clean_text(source_summary.get("topic"))
    source_summary["analysis_time"] = isoformat_or_blank(request["analysis_time"])

    reuse_existing_package = not request_needs_package_rebuild(request, prior_request) and bool(safe_dict(article_result.get("article_package")))
    if reuse_existing_package:
        article_package = deepcopy(safe_dict(article_result.get("article_package")))
        selected_images = deepcopy(
            safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))
        )
        article_package["feedback_profile_status"] = deepcopy(
            safe_dict(request.get("feedback_profile_status")) or safe_dict(article_package.get("feedback_profile_status"))
        )
    else:
        article_package, selected_images = assemble_article_package(
            request,
            source_summary,
            evidence_digest,
            citations,
            image_candidates,
            analysis_brief,
        )
    base_package_mode = "reused_draft_package" if reuse_existing_package else "reassembled"

    manual_override = False
    manual_body_override = False
    manual_article_override = False
    if clean_text(request.get("edited_body_markdown")):
        manual_override = True
        manual_body_override = True
        article_package["body_markdown"] = request.get("edited_body_markdown").strip() + "\n"
    if clean_text(request.get("edited_article_markdown")):
        manual_override = True
        manual_article_override = True
        article_package["article_markdown"] = request.get("edited_article_markdown").strip() + "\n"
    article_package["image_blocks"] = deepcopy(selected_images)
    article_package["selected_images"] = deepcopy(selected_images)
    article_package["manual_body_override"] = manual_body_override
    article_package["manual_article_override"] = manual_article_override

    editor_notes = clean_string_list(safe_dict(article_result.get("article_package")).get("editor_notes"))
    editor_notes.extend(request["feedback"].get("feedback_notes", []))
    if manual_override:
        editor_notes.append("Manual article/body override was applied during revision.")
    article_package["editor_notes"] = clean_string_list(editor_notes)
    article_package["draft_metrics"] = draft_metrics(article_package["body_markdown"], selected_images, citations)
    article_package["char_count"] = article_package["draft_metrics"]["char_count"]

    pre_rewrite_review = build_red_team_review(article_package, analysis_brief, source_summary, citations, selected_images)
    allow_auto_rewrite_after_manual = bool(request.get("allow_auto_rewrite_after_manual"))
    preserve_manual_override = manual_override and not allow_auto_rewrite_after_manual
    if preserve_manual_override:
        review_rewrite_package = {
            **pre_rewrite_review,
            "rewrite_mode": "manual_preserved",
            "base_package_mode": base_package_mode,
            "rewrite_decision_reason": "Manual override was preserved because auto rewrite after manual edits was not enabled.",
            "pre_rewrite_quality_gate": clean_text(pre_rewrite_review.get("quality_gate")),
            "pre_rewrite_attacks": deepcopy(safe_list(pre_rewrite_review.get("attacks"))),
            "pre_rewrite_remaining_risks": deepcopy(clean_string_list(pre_rewrite_review.get("remaining_risks"))),
            "quality_gate": clean_text(pre_rewrite_review.get("quality_gate")),
            "attacks": deepcopy(safe_list(pre_rewrite_review.get("attacks"))),
            "remaining_risks": deepcopy(clean_string_list(pre_rewrite_review.get("remaining_risks"))),
            "claims_removed_or_softened": clean_string_list(pre_rewrite_review.get("claims_removed_or_softened")),
        }
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [
                "Manual override preserved; auto-rewrite skipped.",
                f"Red-team quality gate on manual draft: {clean_text(review_rewrite_package.get('quality_gate')) or 'unknown'}.",
            ]
        )
        review_rewrite_package["final_draft"] = {
            "title": clean_text(article_package.get("title")),
            "draft_thesis": clean_text(article_package.get("draft_thesis")),
            "body_markdown": article_package.get("body_markdown", ""),
            "article_markdown": article_package.get("article_markdown", ""),
        }
    elif not manual_override and not safe_list(pre_rewrite_review.get("attacks")) and clean_text(pre_rewrite_review.get("quality_gate")) == "pass":
        review_rewrite_package = {
            **pre_rewrite_review,
            "rewrite_mode": "no_rewrite_needed",
            "base_package_mode": base_package_mode,
            "rewrite_decision_reason": "Red-team review passed without attacks, so the current package was kept as the final draft.",
            "pre_rewrite_quality_gate": clean_text(pre_rewrite_review.get("quality_gate")),
            "pre_rewrite_attacks": [],
            "pre_rewrite_remaining_risks": deepcopy(clean_string_list(pre_rewrite_review.get("remaining_risks"))),
            "quality_gate": clean_text(pre_rewrite_review.get("quality_gate")),
            "attacks": [],
            "remaining_risks": deepcopy(clean_string_list(pre_rewrite_review.get("remaining_risks"))),
            "claims_removed_or_softened": clean_string_list(pre_rewrite_review.get("claims_removed_or_softened")),
        }
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [
                "Red-team review passed without requiring an auto-rewrite; kept the current draft package.",
                f"Red-team quality gate: {clean_text(review_rewrite_package.get('quality_gate')) or 'unknown'}.",
            ]
        )
        review_rewrite_package["final_draft"] = {
            "title": clean_text(article_package.get("title")),
            "draft_thesis": clean_text(article_package.get("draft_thesis")),
            "body_markdown": article_package.get("body_markdown", ""),
            "article_markdown": article_package.get("article_markdown", ""),
        }
    else:
        rewrite_request = rewrite_request_after_attack(request, analysis_brief, pre_rewrite_review)
        rewritten_package, rewritten_images = assemble_article_package(
            rewrite_request,
            source_summary,
            evidence_digest,
            citations,
            image_candidates,
            analysis_brief,
        )
        final_review = build_red_team_review(rewritten_package, analysis_brief, source_summary, citations, rewritten_images)
        review_rewrite_package = {
            **pre_rewrite_review,
            "rewrite_mode": "manual_opt_in_auto_rewrite" if manual_override else "auto_rewrite",
            "base_package_mode": base_package_mode,
            "rewrite_decision_reason": (
                "Manual override requested auto rewrite after review."
                if manual_override
                else "Red-team review found issues that required a safer regenerated draft."
            ),
            "pre_rewrite_quality_gate": clean_text(pre_rewrite_review.get("quality_gate")),
            "pre_rewrite_attacks": deepcopy(safe_list(pre_rewrite_review.get("attacks"))),
            "pre_rewrite_remaining_risks": deepcopy(clean_string_list(pre_rewrite_review.get("remaining_risks"))),
            "quality_gate": clean_text(final_review.get("quality_gate")),
            "attacks": deepcopy(safe_list(final_review.get("attacks"))),
            "remaining_risks": deepcopy(clean_string_list(final_review.get("remaining_risks"))),
            "claims_removed_or_softened": clean_string_list(
                clean_string_list(pre_rewrite_review.get("claims_removed_or_softened"))
                + clean_string_list(final_review.get("claims_removed_or_softened"))
            ),
        }
        rewritten_package["manual_body_override"] = manual_body_override
        rewritten_package["manual_article_override"] = manual_article_override
        rewritten_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [
                (
                    "Manual override was reviewed and then auto-rewritten because allow_auto_rewrite_after_manual was enabled."
                    if manual_override
                    else ""
                ),
                f"Red-team pre-rewrite quality gate: {clean_text(review_rewrite_package.get('pre_rewrite_quality_gate')) or 'unknown'}.",
                f"Red-team final quality gate: {clean_text(review_rewrite_package.get('quality_gate')) or 'unknown'}.",
            ]
        )
        review_rewrite_package["final_draft"] = {
            "title": clean_text(rewritten_package.get("title")),
            "draft_thesis": clean_text(rewritten_package.get("draft_thesis")),
            "body_markdown": rewritten_package.get("body_markdown", ""),
            "article_markdown": rewritten_package.get("article_markdown", ""),
        }
        article_package = rewritten_package
        selected_images = rewritten_images
    asset_localization = localize_selected_images(article_package, request)
    selected_images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    image_candidates = preserve_localized_image_assets(image_candidates, selected_images)
    revision_diff = build_revision_diff(article_result, request, article_package, selected_images, citations)
    style_learning = build_style_learning(
        article_result,
        request,
        article_package,
        review_rewrite_package,
        revision_diff,
        request.get("edit_reason_feedback"),
    )
    profile_update_decision = safe_dict(style_learning.get("profile_update_decision"))
    review_rewrite_package["style_learning"] = deepcopy(style_learning)
    review_rewrite_package["profile_update_decision"] = deepcopy(profile_update_decision)
    review_rewrite_package["human_feedback_form"] = deepcopy(safe_dict(request.get("human_feedback_form")))

    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    save_result = save_feedback_profiles_detailed(
        profile_dir,
        request.get("topic"),
        request["analysis_time"],
        request.get("persist_feedback"),
        request_defaults=request_defaults_from_request(request),
    )
    saved_profile_paths = clean_string_list(save_result.get("saved_paths"))
    profile_backup_paths = clean_string_list(save_result.get("backup_paths"))
    cached_feedback_status = matching_cached_feedback_profile_status(
        request,
        article_result.get("feedback_profile_status"),
        safe_dict(safe_dict(article_result.get("article_package")).get("feedback_profile_status")),
        draft_context.get("feedback_profile_status"),
    )
    if saved_profile_paths or profile_backup_paths or not cached_feedback_status:
        article_package["feedback_profile_status"] = feedback_profile_status(
            profile_dir,
            request.get("topic"),
        )
    else:
        article_package["feedback_profile_status"] = cached_feedback_status
    if saved_profile_paths:
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Saved feedback profile updates: {', '.join(saved_profile_paths)}"]
        )
    if profile_backup_paths:
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Backed up previous feedback profiles: {', '.join(profile_backup_paths)}"]
        )

    result = deepcopy(article_result)
    result["request"] = {
        **(safe_dict(article_result.get("request"))),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "topic": request.get("topic"),
        "title_hint": request.get("title_hint"),
        "title_hint_zh": request.get("title_hint_zh"),
        "subtitle_hint": request.get("subtitle_hint"),
        "subtitle_hint_zh": request.get("subtitle_hint_zh"),
        "angle": request.get("angle"),
        "angle_zh": request.get("angle_zh"),
        "tone": request.get("tone"),
        "target_length_chars": request.get("target_length_chars"),
        "max_images": request.get("max_images"),
        "image_strategy": request.get("image_strategy"),
        "draft_mode": request.get("draft_mode"),
        "language_mode": request.get("language_mode"),
        "must_include": request.get("must_include"),
        "must_avoid": request.get("must_avoid"),
        "allow_auto_rewrite_after_manual": allow_auto_rewrite_after_manual,
        "feedback_profile_dir": request.get("feedback_profile_dir"),
        "persist_feedback": deepcopy(request.get("persist_feedback")),
        "edit_reason_feedback": request.get("edit_reason_feedback"),
        "human_feedback_form": request.get("human_feedback_form"),
        "source_result": None,
    }
    result["source_summary"] = source_summary
    result["source_context"] = {
        "source_kind": source_summary.get("source_kind"),
        "topic": source_summary.get("topic"),
        "analysis_time": source_summary.get("analysis_time"),
        "source_result_path": clean_text(safe_dict(article_result.get("source_context")).get("source_result_path")),
    }
    if revision_evidence_bundle:
        revision_evidence_bundle["topic"] = clean_text(request.get("topic")) or clean_text(revision_evidence_bundle.get("topic"))
        revision_evidence_bundle["analysis_time"] = isoformat_or_blank(request["analysis_time"])
        revision_evidence_bundle["source_summary"] = deepcopy(source_summary)
        revision_evidence_bundle["evidence_digest"] = deepcopy(evidence_digest)
        revision_evidence_bundle["citations"] = deepcopy(citations)
        revision_evidence_bundle["image_candidates"] = deepcopy(image_candidates)
    result["draft_context"] = {
        **draft_context,
        "source_summary": source_summary,
        "evidence_digest": evidence_digest,
        "analysis_brief": analysis_brief,
        "citation_candidates": citations,
        "image_candidates": image_candidates,
        "selected_images": deepcopy(selected_images),
        "evidence_bundle": revision_evidence_bundle,
        "asset_output_dir": request.get("asset_output_dir"),
    }
    result["evidence_bundle"] = revision_evidence_bundle
    result["analysis_brief"] = analysis_brief
    result["article_package"] = article_package
    result["review_rewrite_package"] = review_rewrite_package
    result["final_article_result"] = {
        "title": clean_text(article_package.get("title")),
        "draft_thesis": clean_text(article_package.get("draft_thesis")),
        "body_markdown": article_package.get("body_markdown", ""),
        "article_markdown": article_package.get("article_markdown", ""),
        "quality_gate": clean_text(review_rewrite_package.get("quality_gate")),
    }
    result["revision_diff"] = revision_diff
    result["style_learning"] = style_learning
    result["profile_update_decision"] = profile_update_decision
    result["human_feedback_form"] = deepcopy(safe_dict(request.get("human_feedback_form")))
    result["saved_feedback_profiles"] = saved_profile_paths
    result["profile_backup_paths"] = profile_backup_paths
    result["feedback_profile_status"] = deepcopy(safe_dict(article_package.get("feedback_profile_status")))
    result["asset_localization"] = asset_localization
    result["preview_html"] = build_article_preview_html(article_package)

    revision_entry = {
        "revised_at": isoformat_or_blank(request["analysis_time"]),
        "manual_override": manual_override,
        "allow_auto_rewrite_after_manual": allow_auto_rewrite_after_manual,
        "rewrite_mode": clean_text(review_rewrite_package.get("rewrite_mode")),
        "feedback_notes": request["feedback"].get("feedback_notes", []),
        "image_count": len(selected_images),
        "citation_count": len(citations),
        "kept_image_ids": request["feedback"].get("keep_image_ids", []),
        "dropped_image_ids": request["feedback"].get("drop_image_ids", []),
        "quality_gate": clean_text(review_rewrite_package.get("quality_gate")),
        "saved_feedback_profiles": saved_profile_paths,
        "profile_backup_paths": profile_backup_paths,
        "edit_reason_feedback": request.get("edit_reason_feedback"),
        "human_feedback_form": request.get("human_feedback_form"),
        "base_package_mode": base_package_mode,
        "revision_diff": revision_diff,
        "style_learning_summary": {
            "high_confidence_rule_count": len(safe_list(style_learning.get("high_confidence_rules"))),
            "medium_confidence_rule_count": len(safe_list(style_learning.get("medium_confidence_rules"))),
            "low_confidence_rule_count": len(safe_list(style_learning.get("low_confidence_rules"))),
            "decision": clean_text(profile_update_decision.get("status")),
            "explicit_change_count": int(style_learning.get("explicit_change_count", 0) or 0),
            "explicit_preference_count": int(style_learning.get("explicit_preference_count", 0) or 0),
        },
    }
    result["revision_history"] = safe_list(article_result.get("revision_history")) + [revision_entry]
    result["revision_log"] = safe_list(article_result.get("revision_log")) + [revision_entry]
    result["report_markdown"] = build_review_report_markdown(article_package, review_rewrite_package)
    return result


__all__ = ["build_article_revision", "load_json", "write_json"]
