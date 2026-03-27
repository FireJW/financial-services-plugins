#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from article_feedback_profiles import parse_bool
from article_draft_flow_runtime import clean_string_list, clean_text, load_json, safe_dict, safe_list


SECTION_ALIASES = {
    "overall goal": "overall_goal",
    "goal": "overall_goal",
    "keep": "keep",
    "what to keep": "keep",
    "change requests": "changes",
    "what to change": "changes",
    "remember next time": "remember",
    "what to remember next time": "remember",
    "one-off fact fixes": "one_off_fixes",
    "one-off fixes": "one_off_fixes",
    "one off fact fixes": "one_off_fixes",
    "one off fixes": "one_off_fixes",
    "images to keep near front": "keep_images",
    "images to keep": "keep_images",
    "images to drop": "drop_images",
    "optional full rewrite": "full_rewrite",
}

FIELD_ALIASES = {
    "change": "change",
    "why": "why",
    "area": "area",
    "reason tag": "reason_tag",
    "reason_tag": "reason_tag",
    "key": "key",
    "value": "value",
    "scope": "scope",
    "remember for": "scope",
}


def normalize_heading(value: str) -> str:
    return " ".join(clean_text(value).lower().replace("_", " ").split())


def normalize_field_name(value: str) -> str:
    return FIELD_ALIASES.get(normalize_heading(value), "")


def split_sections(markdown_text: str) -> tuple[list[str], dict[str, str]]:
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current_key = "__preamble__"
    current_lines = preamble
    in_fence = False

    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            current_lines.append(raw_line)
            continue

        if not in_fence and raw_line.startswith("## "):
            current_key = normalize_heading(raw_line[3:])
            current_lines = sections.setdefault(current_key, [])
            continue

        current_lines.append(raw_line)

    return preamble, {key: "\n".join(lines).strip() for key, lines in sections.items()}


def parse_preamble_settings(lines: list[str]) -> dict[str, str]:
    settings: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(">") or line.startswith("```"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        settings[normalize_heading(key)] = value.strip()
    return settings


def meaningful_lines(section_text: str) -> list[str]:
    return [
        line.strip()
        for line in section_text.splitlines()
        if line.strip() and not line.lstrip().startswith(">") and not line.lstrip().startswith("<!--")
    ]


def parse_plain_text(section_text: str) -> str:
    lines: list[str] = []
    for line in meaningful_lines(section_text):
        if line.startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def parse_simple_bullets(section_text: str) -> list[str]:
    items: list[str] = []
    for line in meaningful_lines(section_text):
        if line.startswith(("```", "## ", "### ")):
            continue
        if line.startswith(("- ", "* ")):
            text = clean_text(line[2:])
            if text and text not in items:
                items.append(text)
    return items


def parse_structured_bullet_blocks(section_text: str) -> list[dict[str, str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in meaningful_lines(section_text):
        if line.startswith("```"):
            continue
        if line.startswith(("- ", "* ")):
            if current:
                blocks.append(current)
            current = [line[2:].strip()]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)

    parsed: list[dict[str, str]] = []
    for block in blocks:
        item: dict[str, str] = {}
        last_key = ""
        for index, line in enumerate(block):
            text = line.strip()
            if not text:
                continue
            if ":" in text:
                field_name, value = text.split(":", 1)
                normalized = normalize_field_name(field_name)
                if normalized:
                    item[normalized] = value.strip()
                    last_key = normalized
                    continue
            if index == 0 and "change" not in item:
                item["change"] = text
                last_key = "change"
                continue
            if index == 0 and "value" not in item and "key" in item:
                item["value"] = text
                last_key = "value"
                continue
            if last_key:
                item[last_key] = clean_text(f"{item.get(last_key, '')} {text}")
        if item:
            parsed.append(item)
    return parsed


def extract_fenced_block(section_text: str) -> str:
    in_fence = False
    captured: list[str] = []
    saw_fence = False
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if in_fence:
                break
            in_fence = True
            saw_fence = True
            continue
        if in_fence:
            captured.append(raw_line)
    if not saw_fence:
        return ""
    return "\n".join(captured).strip()


def load_feedback_markdown(path: Path, *, template_path: Path | None = None) -> dict[str, Any]:
    resolved_path = path.resolve()
    resolved_template = template_path.resolve() if template_path else resolved_path.with_name("article-revise-template.json")
    base_template: dict[str, Any] = {}
    if resolved_template.exists():
        loaded = load_json(resolved_template)
        if isinstance(loaded, dict):
            base_template = loaded
    return parse_feedback_markdown(resolved_path.read_text(encoding="utf-8-sig"), base_template=base_template)


def parse_feedback_markdown(markdown_text: str, *, base_template: Any = None) -> dict[str, Any]:
    payload = deepcopy(safe_dict(base_template))
    preamble_lines, sections = split_sections(markdown_text)
    settings = parse_preamble_settings(preamble_lines)

    feedback = safe_dict(payload.get("feedback"))
    feedback["keep_image_asset_ids"] = parse_simple_bullets(
        sections.get("images to keep near front") or sections.get("images to keep") or ""
    )
    feedback["drop_image_asset_ids"] = parse_simple_bullets(sections.get("images to drop") or "")
    payload["feedback"] = feedback

    persist_feedback = safe_dict(payload.get("persist_feedback"))
    persist_feedback["scope"] = clean_text(
        settings.get("persist feedback scope") or settings.get("persist feedback") or persist_feedback.get("scope") or "none"
    ).lower() or "none"
    payload["persist_feedback"] = persist_feedback

    payload["allow_auto_rewrite_after_manual"] = parse_bool(
        settings.get("auto rewrite after manual"),
        default=bool(payload.get("allow_auto_rewrite_after_manual")),
    )

    overall_goal = parse_plain_text(sections.get("overall goal") or sections.get("goal") or "")
    keep_notes = parse_simple_bullets(sections.get("keep") or sections.get("what to keep") or "")

    change_requests = []
    for item in parse_structured_bullet_blocks(sections.get("change requests") or sections.get("what to change") or ""):
        if clean_text(item.get("change")) or clean_text(item.get("why")):
            change_requests.append(
                {
                    "change": clean_text(item.get("change")),
                    "why": clean_text(item.get("why")),
                    "area": clean_text(item.get("area")),
                    "reason_tag": clean_text(item.get("reason_tag")),
                }
            )

    remember_next_time = []
    for item in parse_structured_bullet_blocks(sections.get("remember next time") or sections.get("what to remember next time") or ""):
        key = clean_text(item.get("key")).lower()
        value = clean_text(item.get("value"))
        if key and value:
            remember_next_time.append(
                {
                    "key": key,
                    "value": value,
                    "why": clean_text(item.get("why")),
                    "scope": clean_text(item.get("scope")).lower() or "topic",
                    "reason_tag": clean_text(item.get("reason_tag")),
                }
            )

    one_off_fixes = []
    for item in parse_structured_bullet_blocks(sections.get("one-off fact fixes") or sections.get("one-off fixes") or ""):
        if clean_text(item.get("change")) or clean_text(item.get("why")):
            one_off_fixes.append(
                {
                    "change": clean_text(item.get("change")),
                    "why": clean_text(item.get("why")),
                    "area": clean_text(item.get("area")),
                    "reason_tag": clean_text(item.get("reason_tag")) or "factual_caution",
                }
            )

    payload["human_feedback_form"] = {
        "overall_goal_in_plain_english": overall_goal,
        "what_to_keep": keep_notes,
        "what_to_change": change_requests,
        "what_to_remember_next_time": remember_next_time,
        "one_off_fixes_not_style": one_off_fixes,
    }

    manual_rewrite = extract_fenced_block(sections.get("optional full rewrite") or "")
    if manual_rewrite:
        payload["edited_body_markdown"] = manual_rewrite
        payload["edited_article_markdown"] = manual_rewrite

    return payload


def build_feedback_markdown(
    draft_result: dict[str, Any],
    revision_template: dict[str, Any],
    *,
    draft_result_path: str = "",
) -> str:
    article_package = safe_dict(draft_result.get("article_package"))
    request = safe_dict(draft_result.get("request"))
    review_focus = safe_dict(revision_template.get("review_focus_suggestions"))
    feedback = safe_dict(revision_template.get("feedback"))
    persist_feedback = safe_dict(revision_template.get("persist_feedback"))
    selected_images = safe_list(article_package.get("selected_images")) or safe_list(article_package.get("image_blocks"))

    lines = [
        "# Article Feedback",
        "",
        "> Edit this file, save it, then run the revise command again with this markdown file as the second argument.",
        "",
        f"Draft result path: {draft_result_path or 'fill in if needed'}",
        f"Persist feedback scope: {clean_text(persist_feedback.get('scope')) or 'none'}",
        f"Auto rewrite after manual: {'true' if revision_template.get('allow_auto_rewrite_after_manual') else 'false'}",
        "",
        "## Current Draft Snapshot",
        "",
        f"- Title: {clean_text(article_package.get('title')) or 'n/a'}",
        f"- Thesis: {clean_text(article_package.get('draft_thesis')) or 'n/a'}",
        f"- Tone: {clean_text(request.get('tone')) or 'n/a'}",
        f"- Images attached: {len(selected_images)}",
        "",
        "## Overall Goal",
        "",
        "> One short sentence about what you want improved.",
        "",
        "## Keep",
        "",
        "> Add one `- ...` bullet per point you want preserved.",
        "",
        "## Change Requests",
        "",
        "> Format each request like this:",
        "> - Change: ...",
        ">   Why: ...",
        ">   Area: body",
        ">   Reason Tag: clarity",
        "",
        "## Remember Next Time",
        "",
        "> Only include stable preferences you want reused later.",
        "> - Key: must_include",
        ">   Value: ...",
        ">   Why: ...",
        ">   Scope: topic",
        "",
        "## One-Off Fact Fixes",
        "",
        "> Use this for fact or evidence fixes that should not become a default preference.",
        "> - Change: ...",
        ">   Why: ...",
        ">   Area: claims",
        "",
        "## Images To Keep Near Front",
        "",
        "> Copy image IDs from the list below if needed.",
    ]
    for image_id in clean_string_list(feedback.get("keep_image_asset_ids")):
        lines.append(f"- {image_id}")
    lines.extend(["", "## Images To Drop", "", "> Copy image IDs from the list below if needed."])
    for image_id in clean_string_list(feedback.get("drop_image_asset_ids")):
        lines.append(f"- {image_id}")
    suggested_checks = clean_string_list(review_focus.get("recommended_first_checks"))
    if suggested_checks:
        lines.extend(["", "## Suggested Review Focus", ""])
        for item in suggested_checks:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Optional Full Rewrite",
            "",
            "> Paste a full rewritten article below only if you rewrote it yourself.",
            "```md",
            "",
            "```",
        ]
    )
    if selected_images:
        lines.extend(["", "## Available Image IDs", ""])
        for item in selected_images:
            image_id = clean_text(item.get("asset_id") or item.get("image_id"))
            label = clean_text(item.get("headline") or item.get("caption") or item.get("credit") or item.get("source_name"))
            if image_id:
                lines.append(f"- {image_id}: {label or 'image'}")
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "build_feedback_markdown",
    "load_feedback_markdown",
    "parse_feedback_markdown",
]
