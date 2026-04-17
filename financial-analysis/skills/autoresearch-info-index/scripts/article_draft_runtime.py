#!/usr/bin/env python3
from __future__ import annotations

from article_draft_flow_runtime import (
    apply_must_avoid,
    assemble_article_package,
    build_article_draft,
    build_article_markdown,
    build_body_markdown,
    build_citations,
    build_image_candidates,
    build_report_markdown,
    build_sections,
    build_selected_images,
    build_source_summary,
    build_subtitle,
    build_title,
    clean_string_list,
    clean_text,
    draft_metrics,
    load_json,
    normalize_latest_signals,
    normalize_request,
    path_exists,
    safe_dict,
    safe_list,
    write_json,
)


def run_article_draft(raw_payload):
    return build_article_draft(raw_payload)


__all__ = [
    "apply_must_avoid",
    "assemble_article_package",
    "build_article_draft",
    "build_article_markdown",
    "build_body_markdown",
    "build_citations",
    "build_image_candidates",
    "build_report_markdown",
    "build_sections",
    "build_selected_images",
    "build_source_summary",
    "build_subtitle",
    "build_title",
    "clean_string_list",
    "clean_text",
    "draft_metrics",
    "load_json",
    "normalize_latest_signals",
    "normalize_request",
    "path_exists",
    "run_article_draft",
    "safe_dict",
    "safe_list",
    "write_json",
]
