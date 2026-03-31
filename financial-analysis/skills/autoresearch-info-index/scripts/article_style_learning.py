#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any


STYLE_REQUEST_KEYS = ("language_mode", "tone", "draft_mode", "image_strategy", "max_images", "human_signal_ratio")
GUIDANCE_REQUEST_KEYS = ("must_include", "must_avoid", "personal_phrase_bank")
FRAMING_REQUEST_KEYS = ("title_hint", "title_hint_zh", "subtitle_hint", "subtitle_hint_zh", "angle", "angle_zh")
REQUEST_DIFF_KEYS = STYLE_REQUEST_KEYS + GUIDANCE_REQUEST_KEYS + FRAMING_REQUEST_KEYS + ("allow_auto_rewrite_after_manual",)
EDIT_REASON_TAGS = {
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
}
EDIT_REASON_AREAS = {
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
}
REUSE_SCOPES = {"none", "review", "topic", "global"}
REUSABLE_PREFERENCE_KEYS = set(STYLE_REQUEST_KEYS + GUIDANCE_REQUEST_KEYS)
GENERIC_GUIDANCE_HINTS = {
    "fact",
    "facts",
    "confirmed",
    "unconfirmed",
    "unclear",
    "source",
    "sources",
    "citation",
    "citations",
    "image",
    "images",
    "screenshot",
    "tone",
    "title",
    "subtitle",
    "lead",
    "lede",
    "headline",
    "market relevance",
    "reader relevance",
    "angle",
    "thesis",
    "avoid",
    "explicit",
    "bilingual",
    "english",
    "chinese",
    "language",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def normalize_reason_tag(value: Any) -> str:
    tag = clean_text(value).lower()
    return tag if tag in EDIT_REASON_TAGS else "other"


def normalize_reason_area(value: Any) -> str:
    area = clean_text(value).lower()
    return area if area in EDIT_REASON_AREAS else "other"


def normalize_reuse_scope(value: Any, *, default: str = "none") -> str:
    scope = clean_text(value).lower()
    return scope if scope in REUSE_SCOPES else default


def normalize_preference_value(key: str, value: Any) -> Any:
    if key in GUIDANCE_REQUEST_KEYS:
        if isinstance(value, str):
            cleaned = clean_text(value)
            return [cleaned] if cleaned else []
        return clean_string_list(value)
    if key == "max_images":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return clean_text(value)


def combine_change_and_reason(change: Any, why: Any) -> str:
    change_text = clean_text(change)
    why_text = clean_text(why)
    if change_text and why_text:
        if change_text == why_text:
            return change_text
        return f"{change_text} Why: {why_text}"
    return change_text or why_text


def normalize_edit_reason_feedback(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    changes: list[dict[str, Any]] = []
    for item in safe_list(payload.get("changes") or payload.get("change_log")):
        entry = safe_dict(item)
        change = clean_text(entry.get("change") or entry.get("instruction") or entry.get("edit") or entry.get("text"))
        why = clean_text(entry.get("why") or entry.get("reason") or entry.get("details"))
        area = normalize_reason_area(entry.get("area") or entry.get("field"))
        reuse_scope = normalize_reuse_scope(entry.get("reuse_scope") or entry.get("should_reuse"))
        if not change and not why and reuse_scope == "none":
            continue
        changes.append(
            {
                "area": area,
                "reason_tag": normalize_reason_tag(entry.get("reason_tag") or entry.get("category")),
                "change": change,
                "why": why,
                "reuse_scope": reuse_scope,
            }
        )

    reusable_preferences: list[dict[str, Any]] = []
    for item in safe_list(payload.get("reusable_preferences") or payload.get("preference_signals")):
        entry = safe_dict(item)
        key = clean_text(entry.get("key")).lower()
        if key not in REUSABLE_PREFERENCE_KEYS:
            continue
        normalized_value = normalize_preference_value(key, entry.get("value"))
        if normalized_value in ("", [], None):
            continue
        reusable_preferences.append(
            {
                "key": key,
                "value": normalized_value,
                "scope": normalize_reuse_scope(entry.get("scope") or entry.get("reuse_scope"), default="review"),
                "reason_tag": normalize_reason_tag(entry.get("reason_tag") or entry.get("category")),
                "why": clean_text(entry.get("why") or entry.get("reason") or entry.get("details")),
            }
        )

    return {
        "summary": clean_text(payload.get("summary")),
        "changes": changes,
        "reusable_preferences": reusable_preferences,
    }


def normalize_human_feedback_change(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        text = clean_text(value)
        return {
            "area": "other",
            "change": text,
            "why": "",
            "reason_tag": "other",
            "reuse_scope": "review",
        }
    payload = safe_dict(value)
    return {
        "area": normalize_reason_area(payload.get("area")),
        "change": clean_text(payload.get("change") or payload.get("instruction") or payload.get("text")),
        "why": clean_text(payload.get("why") or payload.get("reason")),
        "reason_tag": normalize_reason_tag(payload.get("reason_tag") or payload.get("category")),
        "reuse_scope": normalize_reuse_scope(payload.get("reuse_scope") or payload.get("remember_for"), default="review"),
    }


def normalize_human_feedback_preference(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    key = clean_text(payload.get("key")).lower()
    normalized_value = normalize_preference_value(key, payload.get("value"))
    return {
        "key": key,
        "value": normalized_value,
        "scope": normalize_reuse_scope(payload.get("scope") or payload.get("remember_for"), default="topic"),
        "why": clean_text(payload.get("why") or payload.get("reason")),
        "reason_tag": normalize_reason_tag(payload.get("reason_tag") or payload.get("category")),
    }


def normalize_human_feedback_form(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    what_to_keep = clean_string_list(payload.get("what_to_keep") or payload.get("keep_notes"))
    what_to_change = [
        item
        for item in (normalize_human_feedback_change(raw) for raw in safe_list(payload.get("what_to_change") or payload.get("changes")))
        if clean_text(item.get("change")) or clean_text(item.get("why"))
    ]
    reusable_preferences = [
        item
        for item in (
            normalize_human_feedback_preference(raw)
            for raw in safe_list(payload.get("what_to_remember_next_time") or payload.get("reusable_preferences"))
        )
        if clean_text(item.get("key")) in REUSABLE_PREFERENCE_KEYS and item.get("value") not in ("", [], None)
    ]
    one_off_fixes = [
        item
        for item in (normalize_human_feedback_change(raw) for raw in safe_list(payload.get("one_off_fixes_not_style") or payload.get("one_off_corrections")))
        if clean_text(item.get("change")) or clean_text(item.get("why"))
    ]
    return {
        "overall_goal_in_plain_english": clean_text(payload.get("overall_goal_in_plain_english") or payload.get("summary")),
        "what_to_keep": what_to_keep,
        "what_to_change": what_to_change,
        "what_to_remember_next_time": reusable_preferences,
        "one_off_fixes_not_style": one_off_fixes,
    }


def human_feedback_form_to_edit_reason_feedback(value: Any) -> dict[str, Any]:
    form = normalize_human_feedback_form(value)
    summary_parts = [clean_text(form.get("overall_goal_in_plain_english"))]
    if form.get("what_to_keep"):
        summary_parts.append("Keep: " + "; ".join(clean_string_list(form.get("what_to_keep"))[:3]))

    changes: list[dict[str, Any]] = []
    for item in safe_list(form.get("what_to_change")):
        change_text = clean_text(item.get("change"))
        why = clean_text(item.get("why"))
        changes.append(
            {
                "area": normalize_reason_area(item.get("area")),
                "reason_tag": normalize_reason_tag(item.get("reason_tag")),
                "change": change_text,
                "why": why,
                "reuse_scope": normalize_reuse_scope(item.get("reuse_scope"), default="review"),
            }
        )

    for item in safe_list(form.get("one_off_fixes_not_style")):
        change_text = clean_text(item.get("change"))
        why = clean_text(item.get("why"))
        changes.append(
            {
                "area": normalize_reason_area(item.get("area")),
                "reason_tag": normalize_reason_tag(item.get("reason_tag") or "factual_caution"),
                "change": change_text,
                "why": why,
                "reuse_scope": "none",
            }
        )

    reusable_preferences: list[dict[str, Any]] = []
    for item in safe_list(form.get("what_to_remember_next_time")):
        reusable_preferences.append(
            {
                "key": clean_text(item.get("key")).lower(),
                "value": normalize_preference_value(clean_text(item.get("key")).lower(), item.get("value")),
                "scope": normalize_reuse_scope(item.get("scope"), default="topic"),
                "reason_tag": normalize_reason_tag(item.get("reason_tag")),
                "why": clean_text(item.get("why")),
            }
        )

    return normalize_edit_reason_feedback(
        {
            "summary": " ".join(part for part in summary_parts if part).strip(),
            "changes": changes,
            "reusable_preferences": reusable_preferences,
        }
    )


def merge_edit_reason_feedback(*values: Any) -> dict[str, Any]:
    summaries: list[str] = []
    changes: list[dict[str, Any]] = []
    reusable_preferences: list[dict[str, Any]] = []
    seen_change_keys: set[tuple[str, str, str, str, str]] = set()
    seen_preference_keys: set[tuple[str, str, str]] = set()
    for value in values:
        payload = normalize_edit_reason_feedback(value)
        summary = clean_text(payload.get("summary"))
        if summary and summary not in summaries:
            summaries.append(summary)
        for item in safe_list(payload.get("changes")):
            key = (
                clean_text(item.get("area")),
                clean_text(item.get("reason_tag")),
                clean_text(item.get("change")),
                clean_text(item.get("why")),
                normalize_reuse_scope(item.get("reuse_scope")),
            )
            if key in seen_change_keys:
                continue
            seen_change_keys.add(key)
            changes.append(item)
        for item in safe_list(payload.get("reusable_preferences")):
            key = (
                clean_text(item.get("key")).lower(),
                repr(item.get("value")),
                normalize_reuse_scope(item.get("scope"), default="review"),
            )
            if key in seen_preference_keys:
                continue
            seen_preference_keys.add(key)
            reusable_preferences.append(item)
    return {
        "summary": " ".join(summaries).strip(),
        "changes": changes,
        "reusable_preferences": reusable_preferences,
    }


def normalize_request_value(key: str, value: Any) -> Any:
    if key in GUIDANCE_REQUEST_KEYS:
        return clean_string_list(value)
    if key == "max_images":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if key == "allow_auto_rewrite_after_manual":
        return bool(value)
    return clean_text(value)


def summarize_text_change(before: Any, after: Any) -> dict[str, Any]:
    before_text = str(before or "")
    after_text = str(after or "")
    changed = before_text != after_text
    similarity = 1.0 if not changed else SequenceMatcher(None, before_text, after_text).ratio()
    return {
        "changed": changed,
        "before_chars": len(before_text),
        "after_chars": len(after_text),
        "char_delta": len(after_text) - len(before_text),
        "before_lines": len(before_text.splitlines()) if before_text else 0,
        "after_lines": len(after_text.splitlines()) if after_text else 0,
        "line_delta": (len(after_text.splitlines()) if after_text else 0) - (len(before_text.splitlines()) if before_text else 0),
        "similarity": round(similarity, 3),
    }


def section_headings(value: Any) -> list[str]:
    headings: list[str] = []
    for item in safe_list(value):
        heading = clean_text(safe_dict(item).get("heading"))
        if heading:
            headings.append(heading)
    return headings


def image_ids(value: Any) -> list[str]:
    image_list: list[str] = []
    for item in safe_list(value):
        image_id = clean_text(safe_dict(item).get("asset_id") or safe_dict(item).get("image_id"))
        if image_id and image_id not in image_list:
            image_list.append(image_id)
    return image_list


def summarize_request_changes(previous_request: dict[str, Any], revised_request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in REQUEST_DIFF_KEYS:
        before_value = normalize_request_value(key, previous_request.get(key))
        after_value = normalize_request_value(key, revised_request.get(key))
        if before_value == after_value:
            continue
        changes[key] = {"before": deepcopy(before_value), "after": deepcopy(after_value)}
    return changes


def build_revision_diff(
    previous_result: dict[str, Any],
    revised_request: dict[str, Any],
    revised_article_package: dict[str, Any],
    revised_images: list[dict[str, Any]],
    revised_citations: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_package = safe_dict(previous_result.get("article_package"))
    previous_request = safe_dict(previous_result.get("request"))
    previous_images = safe_list(previous_package.get("selected_images")) or safe_list(previous_package.get("image_blocks"))
    previous_citations = safe_list(previous_package.get("citations")) or safe_list(safe_dict(previous_result.get("draft_context")).get("citation_candidates"))

    previous_section_headings = section_headings(previous_package.get("sections") or previous_package.get("body_sections"))
    revised_section_headings = section_headings(revised_article_package.get("sections") or revised_article_package.get("body_sections"))
    previous_image_ids = image_ids(previous_images)
    revised_image_ids = image_ids(revised_images)
    request_changes = summarize_request_changes(previous_request, revised_request)

    summary: list[str] = []
    title_before = clean_text(previous_package.get("title"))
    title_after = clean_text(revised_article_package.get("title"))
    if title_before != title_after:
        summary.append(f"Title changed from '{title_before or 'n/a'}' to '{title_after or 'n/a'}'.")
    subtitle_before = clean_text(previous_package.get("subtitle"))
    subtitle_after = clean_text(revised_article_package.get("subtitle"))
    if subtitle_before != subtitle_after:
        summary.append("Subtitle wording changed.")
    body_summary = summarize_text_change(previous_package.get("body_markdown"), revised_article_package.get("body_markdown"))
    if body_summary["changed"]:
        summary.append(
            f"Body markdown changed by {body_summary['char_delta']} chars and {body_summary['line_delta']} lines "
            f"(similarity {body_summary['similarity']})."
        )
    article_summary = summarize_text_change(previous_package.get("article_markdown"), revised_article_package.get("article_markdown"))
    if article_summary["changed"]:
        summary.append(
            f"Publishable article markdown changed by {article_summary['char_delta']} chars and {article_summary['line_delta']} lines "
            f"(similarity {article_summary['similarity']})."
        )
    if previous_section_headings != revised_section_headings:
        summary.append(
            f"Section order/count changed from {len(previous_section_headings)} to {len(revised_section_headings)} sections."
        )
    if previous_image_ids != revised_image_ids:
        summary.append(
            f"Image selection changed: kept {len([item for item in previous_image_ids if item in revised_image_ids])}, "
            f"added {len([item for item in revised_image_ids if item not in previous_image_ids])}, "
            f"removed {len([item for item in previous_image_ids if item not in revised_image_ids])}."
        )
    if request_changes:
        summary.append(f"Revision request changed {len(request_changes)} reusable controls or hints.")
    if not summary:
        summary.append("No material revision deltas were detected.")

    return {
        "summary": summary,
        "title": {"before": title_before, "after": title_after, "changed": title_before != title_after},
        "subtitle": {"before": subtitle_before, "after": subtitle_after, "changed": subtitle_before != subtitle_after},
        "body": body_summary,
        "article": article_summary,
        "sections": {
            "changed": previous_section_headings != revised_section_headings,
            "before_count": len(previous_section_headings),
            "after_count": len(revised_section_headings),
            "before_headings": previous_section_headings,
            "after_headings": revised_section_headings,
        },
        "images": {
            "changed": previous_image_ids != revised_image_ids,
            "before_ids": previous_image_ids,
            "after_ids": revised_image_ids,
            "kept_ids": [item for item in previous_image_ids if item in revised_image_ids],
            "added_ids": [item for item in revised_image_ids if item not in previous_image_ids],
            "removed_ids": [item for item in previous_image_ids if item not in revised_image_ids],
            "before_count": len(previous_image_ids),
            "after_count": len(revised_image_ids),
        },
        "citations": {
            "changed": len(previous_citations) != len(revised_citations),
            "before_count": len(previous_citations),
            "after_count": len(revised_citations),
        },
        "request_changes": request_changes,
        "manual_override": bool(revised_article_package.get("manual_body_override") or revised_article_package.get("manual_article_override")),
    }


def looks_like_generic_guidance(text: str) -> bool:
    lowered = clean_text(text).lower()
    if not lowered or len(lowered) > 120:
        return False
    if any(char.isdigit() for char in lowered):
        return False
    if "http" in lowered or "www." in lowered:
        return False
    return any(hint in lowered for hint in GENERIC_GUIDANCE_HINTS)


def make_rule(*, key: str, value: Any, confidence: float, reason: str, scope: str = "candidate", rule_type: str = "request_default") -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "key": key,
        "value": deepcopy(value),
        "confidence": round(confidence, 2),
        "scope": scope,
        "reason": clean_text(reason),
    }


def add_proposed_default(proposed_defaults: dict[str, Any], key: str, value: Any) -> None:
    if key in GUIDANCE_REQUEST_KEYS:
        existing = clean_string_list(proposed_defaults.get(key))
        additions = clean_string_list(value)
        merged = existing + [item for item in additions if item not in existing]
        if merged:
            proposed_defaults[key] = merged
        return
    proposed_defaults[key] = deepcopy(value)


def build_style_learning(
    previous_result: dict[str, Any],
    revised_request: dict[str, Any],
    revised_article_package: dict[str, Any],
    review_package: dict[str, Any],
    revision_diff: dict[str, Any],
    edit_reason_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_changes = safe_dict(revision_diff.get("request_changes"))
    explicit_feedback = normalize_edit_reason_feedback(edit_reason_feedback)
    high_confidence_rules: list[dict[str, Any]] = []
    medium_confidence_rules: list[dict[str, Any]] = []
    low_confidence_rules: list[dict[str, Any]] = []
    excluded_signals: list[str] = []
    proposed_defaults: dict[str, Any] = {}

    for item in safe_list(explicit_feedback.get("reusable_preferences")):
        key = clean_text(item.get("key"))
        value = item.get("value")
        scope = normalize_reuse_scope(item.get("scope"), default="review")
        confidence = 0.98 if scope in {"topic", "global"} else 0.85
        rule = make_rule(
            key=key,
            value=value,
            confidence=confidence,
            reason=clean_text(item.get("why")) or "Explicit reusable preference provided during human review.",
            scope=scope,
            rule_type="explicit_preference",
        )
        high_confidence_rules.append(rule)
        if scope in {"topic", "global"}:
            add_proposed_default(proposed_defaults, key, value)

    for item in safe_list(explicit_feedback.get("changes")):
        reason_tag = clean_text(item.get("reason_tag"))
        change = clean_text(item.get("change"))
        why = clean_text(item.get("why"))
        reuse_scope = normalize_reuse_scope(item.get("reuse_scope"))
        detail = combine_change_and_reason(change, why)
        fallback_detail = detail or reason_tag or "No details provided."
        change_note = f"Human change [{clean_text(item.get('area'))}/{reason_tag}]: {fallback_detail}"
        if reason_tag in {"factual_caution", "citation_handling"}:
            excluded_signals.append(f"{change_note} This was treated as evidence-bound editing, not reusable style memory.")
            continue
        if reuse_scope in {"topic", "global"}:
            medium_confidence_rules.append(
                make_rule(
                    key=f"{clean_text(item.get('area'))}_reason",
                    value=detail or reason_tag,
                    confidence=0.72,
                    reason=(
                        "Human marked this change as reusable, but no direct request-default key was provided."
                        f" {fallback_detail}"
                    ).strip(),
                    scope=reuse_scope,
                    rule_type="explicit_reason",
                )
            )
        else:
            low_confidence_rules.append(
                make_rule(
                    key=f"{clean_text(item.get('area'))}_reason",
                    value=detail or reason_tag,
                    confidence=0.45,
                    reason=(
                        "Human supplied an edit reason; stored as context rather than auto-reusable preference."
                        f" {fallback_detail}"
                    ).strip(),
                    scope=reuse_scope or "review",
                    rule_type="explicit_reason",
                )
            )

    for key in STYLE_REQUEST_KEYS:
        if key not in request_changes:
            continue
        change = safe_dict(request_changes.get(key))
        if any(clean_text(item.get("key")) == key for item in high_confidence_rules):
            continue
        rule = make_rule(
            key=key,
            value=change.get("after"),
            confidence=0.9,
            reason="Explicit reusable style control changed during the revision request.",
        )
        high_confidence_rules.append(rule)
        add_proposed_default(proposed_defaults, key, change.get("after"))

    for key in GUIDANCE_REQUEST_KEYS:
        if key not in request_changes:
            continue
        change = safe_dict(request_changes.get(key))
        before_items = clean_string_list(change.get("before"))
        after_items = clean_string_list(change.get("after"))
        reusable_items = [item for item in after_items if item not in before_items and looks_like_generic_guidance(item)]
        for item in reusable_items[:4]:
            if any(clean_text(rule.get("key")) == key and item in clean_string_list(rule.get("value")) for rule in high_confidence_rules):
                continue
            medium_confidence_rules.append(
                make_rule(
                    key=key,
                    value=item,
                    confidence=0.65,
                    reason="Explicit guidance looks generic enough to be reviewed for reuse, but it is not safe to auto-apply.",
                    rule_type="constraint_candidate",
                )
            )
        skipped_items = [item for item in after_items if item not in before_items and item not in reusable_items]
        if skipped_items:
            excluded_signals.append(f"{key} included topic-specific or ambiguous guidance, so it was kept out of reusable defaults.")

    if any(key in request_changes for key in FRAMING_REQUEST_KEYS):
        low_confidence_rules.append(
            make_rule(
                key="framing_hints",
                value=[key for key in FRAMING_REQUEST_KEYS if key in request_changes],
                confidence=0.35,
                reason="Title, subtitle, or angle hints changed, but those edits are likely topic-specific framing rather than stable style defaults.",
                rule_type="framing_observation",
            )
        )

    if safe_dict(revision_diff.get("images")).get("changed"):
        low_confidence_rules.append(
            make_rule(
                key="image_selection",
                value={
                    "added_ids": safe_dict(revision_diff.get("images")).get("added_ids", []),
                    "removed_ids": safe_dict(revision_diff.get("images")).get("removed_ids", []),
                },
                confidence=0.3,
                reason="Image choices changed during revision, but that may be event-specific rather than a durable workflow rule.",
                rule_type="image_observation",
            )
        )

    if safe_dict(revision_diff.get("body")).get("changed") or safe_dict(revision_diff.get("article")).get("changed"):
        low_confidence_rules.append(
            make_rule(
                key="manual_rewrite",
                value={
                    "body_changed": bool(safe_dict(revision_diff.get("body")).get("changed")),
                    "article_changed": bool(safe_dict(revision_diff.get("article")).get("changed")),
                },
                confidence=0.25,
                reason=(
                    "The body/article text changed materially, but the reusable preference is still unclear."
                    if explicit_feedback.get("changes") or explicit_feedback.get("reusable_preferences")
                    else "The body/article text changed materially, but the reason is ambiguous without structured edit tags, so it stays as observation only."
                ),
                rule_type="rewrite_observation",
            )
        )

    if safe_dict(revision_diff.get("citations")).get("changed"):
        excluded_signals.append("Citation count changed; evidence maintenance is not treated as reusable style memory.")

    quality_gate = clean_text(safe_dict(review_package).get("quality_gate"))
    if quality_gate == "block":
        excluded_signals.append("Final quality gate is block, so no learned defaults should be promoted from this revision.")

    for rule in high_confidence_rules:
        if clean_text(rule.get("key")) not in REUSABLE_PREFERENCE_KEYS:
            continue
        if normalize_reuse_scope(rule.get("scope"), default="topic") in {"topic", "global"}:
            add_proposed_default(proposed_defaults, clean_text(rule.get("key")), rule.get("value"))

    proposed_scope = "none"
    reusable_scopes = [
        normalize_reuse_scope(item.get("scope"), default="review")
        for item in safe_list(explicit_feedback.get("reusable_preferences"))
        if normalize_reuse_scope(item.get("scope"), default="review") in {"topic", "global"}
    ]
    if reusable_scopes:
        unique_scopes = {item for item in reusable_scopes if item in {"topic", "global"}}
        proposed_scope = reusable_scopes[0] if len(unique_scopes) == 1 else "none"

    proposed_feedback = {
        "scope": proposed_scope,
        "defaults": proposed_defaults,
        "notes": clean_string_list(revision_diff.get("summary"))
        + clean_string_list([clean_text(explicit_feedback.get("summary"))]),
        "auto_apply_safe": False,
    }
    if quality_gate == "block":
        profile_update_decision = {
            "status": "hold",
            "reason": "The revised article still failed the quality gate, so the learning output is stored for review only.",
        }
    elif proposed_defaults:
        profile_update_decision = {
            "status": "suggest_only",
            "reason": "Reusable style defaults were detected, but they are suggestions rather than automatic profile mutations.",
        }
    elif high_confidence_rules or medium_confidence_rules or low_confidence_rules:
        profile_update_decision = {
            "status": "record_only",
            "reason": "Signals were captured, but they are not strong or general enough to suggest profile defaults yet.",
        }
    else:
        profile_update_decision = {
            "status": "no_signal",
            "reason": "No reusable style signals were detected from this revision.",
        }

    change_summary = clean_string_list(revision_diff.get("summary"))
    if clean_text(explicit_feedback.get("summary")):
        change_summary.append(f"Human summary: {clean_text(explicit_feedback.get('summary'))}")
    for item in safe_list(explicit_feedback.get("changes"))[:4]:
        change_summary.append(
            f"Human change [{clean_text(item.get('area'))}/{clean_text(item.get('reason_tag'))}]: "
            f"{combine_change_and_reason(item.get('change'), item.get('why')) or 'No details provided.'}"
        )
    if not change_summary:
        change_summary = ["No reusable style signals were detected."]

    return {
        "change_summary": change_summary,
        "high_confidence_rules": high_confidence_rules,
        "medium_confidence_rules": medium_confidence_rules,
        "low_confidence_rules": low_confidence_rules,
        "excluded_signals": clean_string_list(excluded_signals),
        "proposed_profile_feedback": proposed_feedback,
        "profile_update_decision": profile_update_decision,
        "used_explicit_feedback": bool(explicit_feedback.get("summary") or explicit_feedback.get("changes") or explicit_feedback.get("reusable_preferences")),
        "explicit_change_count": len(safe_list(explicit_feedback.get("changes"))),
        "explicit_preference_count": len(safe_list(explicit_feedback.get("reusable_preferences"))),
        "explicit_feedback": explicit_feedback,
    }


__all__ = [
    "build_revision_diff",
    "build_style_learning",
    "human_feedback_form_to_edit_reason_feedback",
    "merge_edit_reason_feedback",
    "normalize_edit_reason_feedback",
    "normalize_human_feedback_form",
]
