#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from article_publish_runtime import (
    build_automatic_acceptance_markdown,
    build_automatic_acceptance_result,
    build_publish_package,
    safe_dict,
    safe_list,
)
from article_workflow_runtime import load_json, write_json
from news_index_runtime import clean_string_list
from workflow_publication_gate_runtime import build_workflow_publication_gate


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_payload_dict(payload_or_path: Any, *, label: str) -> dict[str, Any]:
    if isinstance(payload_or_path, dict):
        return payload_or_path
    path_text = clean_text(payload_or_path)
    if not path_text:
        raise ValueError(f"{label} is required")
    loaded = load_json(Path(path_text).resolve())
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must resolve to a JSON object")
    return loaded


def should_preserve_manual_revised_markdown(revised_result: dict[str, Any]) -> bool:
    article_package = safe_dict(revised_result.get("article_package"))
    if bool(article_package.get("manual_article_override") or article_package.get("manual_body_override")):
        return True
    revised_request = safe_dict(revised_result.get("request"))
    has_manual_input = bool(clean_text(revised_request.get("edited_article_markdown") or revised_request.get("edited_body_markdown")))
    if has_manual_input and not bool(revised_request.get("allow_auto_rewrite_after_manual")):
        return True
    review_rewrite_package = safe_dict(revised_result.get("review_rewrite_package"))
    return clean_text(review_rewrite_package.get("rewrite_mode")) == "manual_preserved"


def derive_publish_request(base_result: dict[str, Any], revised_result: dict[str, Any]) -> dict[str, Any]:
    base_package = safe_dict(base_result.get("publish_package"))
    if not base_package:
        raise ValueError("base_publish_result must contain publish_package")
    draft_article = safe_dict(safe_list(safe_dict(base_package.get("draftbox_payload_template")).get("articles"))[:1][0] if safe_list(safe_dict(base_package.get("draftbox_payload_template")).get("articles")) else {})
    effective_request = safe_dict(safe_dict(base_package.get("style_profile_applied")).get("effective_request"))
    revised_request = safe_dict(revised_result.get("request"))
    old_digest = clean_text(base_package.get("digest"))
    return {
        "account_name": clean_text(base_package.get("account_name")),
        "author": clean_text(base_package.get("author")) or clean_text(draft_article.get("author")),
        "digest_max_chars": max(60, len(old_digest) or 120),
        "need_open_comment": int(draft_article.get("need_open_comment", 0) or 0),
        "only_fans_can_comment": int(draft_article.get("only_fans_can_comment", 0) or 0),
        "editor_anchor_mode": clean_text(base_package.get("editor_anchor_mode")) or "hidden",
        "article_framework": clean_text(base_package.get("article_framework") or effective_request.get("article_framework")) or "auto",
        "headline_hook_mode": clean_text(revised_request.get("headline_hook_mode") or effective_request.get("headline_hook_mode")),
        "headline_hook_prefixes": clean_string_list(
            revised_request.get("headline_hook_prefixes") or effective_request.get("headline_hook_prefixes")
        ),
        "draft_mode": clean_text(revised_request.get("draft_mode") or effective_request.get("draft_mode")),
        "image_strategy": clean_text(revised_request.get("image_strategy") or effective_request.get("image_strategy")),
        "language_mode": clean_text(revised_request.get("language_mode") or effective_request.get("language_mode")),
        "target_length_chars": int(revised_request.get("target_length_chars") or effective_request.get("target_length_chars") or 1600),
        "tone": clean_text(revised_request.get("tone") or effective_request.get("tone")),
        "human_signal_ratio": int(revised_request.get("human_signal_ratio") or effective_request.get("human_signal_ratio") or 35),
        "preserve_manual_revised_markdown": should_preserve_manual_revised_markdown(revised_result),
        "human_review_approved": False,
    }


def derive_workflow_gate_state(base_result: dict[str, Any], raw_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    base_package = safe_dict(base_result.get("publish_package"))
    workflow_stage = safe_dict(base_result.get("workflow_stage"))
    workflow_manual_review = safe_dict(base_package.get("workflow_manual_review"))
    override_manual_review = safe_dict(raw_payload.get("workflow_manual_review"))
    if override_manual_review:
        workflow_manual_review = override_manual_review
    publication_readiness = clean_text(
        raw_payload.get("publication_readiness")
        or base_package.get("publication_readiness")
        or workflow_stage.get("publication_readiness")
        or workflow_manual_review.get("publication_readiness")
        or "ready"
    )
    return workflow_manual_review, publication_readiness


def build_reuse_report_markdown(result: dict[str, Any]) -> str:
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    workflow_manual_review = safe_dict(workflow_publication_gate.get("manual_review")) or safe_dict(result.get("workflow_manual_review"))
    automatic_acceptance = safe_dict(result.get("automatic_acceptance"))
    publish_package = safe_dict(result.get("publish_package"))
    benchmark_rubric = safe_dict(safe_dict(publish_package.get("regression_checks")).get("benchmark_rubric"))
    weakest_dimensions = ", ".join(
        clean_text(item.get("label"))
        for item in safe_list(benchmark_rubric.get("weakest_dimensions"))[:3]
        if clean_text(item.get("label"))
    )
    lines = [
        "# Article Publish Reuse",
        "",
        f"- Status: {clean_text(result.get('status')) or 'unknown'}",
        f"- Title: {clean_text(safe_dict(result.get('selected_topic')).get('title')) or 'unknown'}",
        f"- Output dir: {clean_text(result.get('output_dir')) or 'unknown'}",
        f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness') or result.get('publication_readiness')) or 'ready'}",
        f"- Workflow Reddit operator review: {clean_text(workflow_manual_review.get('status')) or 'not_required'}",
        f"- Review items: {int(workflow_manual_review.get('required_count', 0) or 0)}",
        f"- High-priority review items: {int(workflow_manual_review.get('high_priority_count', 0) or 0)}",
        f"- Next step: {clean_text(workflow_manual_review.get('next_step')) or 'none'}",
        f"- Publish package path: {clean_text(result.get('publish_package_path')) or 'unknown'}",
        f"- WeChat HTML path: {clean_text(result.get('wechat_html_path')) or 'unknown'}",
        f"- Automatic acceptance status: {clean_text(automatic_acceptance.get('status')) or 'unknown'}",
        f"- Automatic acceptance report: {clean_text(result.get('automatic_acceptance_report_path')) or 'unknown'}",
        f"- Push readiness: {clean_text(safe_dict(publish_package.get('push_readiness')).get('status')) or 'unknown'}",
    ]
    if benchmark_rubric:
        lines.extend(
            [
                "",
                "## Benchmark Rubric",
                "",
                f"- Benchmark rubric score: {int(benchmark_rubric.get('total_score', 0) or 0)} / {int(benchmark_rubric.get('threshold', 0) or 0)}",
                f"- Benchmark rubric target met: {'yes' if benchmark_rubric.get('passed') else 'no'}",
                f"- Benchmark rubric blocking ok: {'yes' if benchmark_rubric.get('blocking_passed') else 'no'}",
                f"- Benchmark weakest dimensions: {weakest_dimensions or 'none'}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_reuse_publish_result(raw_payload: dict[str, Any]) -> dict[str, Any]:
    base_result = load_payload_dict(raw_payload.get("base_publish_result") or raw_payload.get("base_publish_result_path"), label="base_publish_result")
    revised_result = load_payload_dict(raw_payload.get("revised_article_result") or raw_payload.get("revised_article_result_path"), label="revised_article_result")
    selected_topic = safe_dict(base_result.get("selected_topic"))
    if not selected_topic:
        raise ValueError("base_publish_result must contain selected_topic")

    request = {
        **derive_publish_request(base_result, revised_result),
        **safe_dict(raw_payload.get("request_overrides")),
    }
    workflow_manual_review, publication_readiness = derive_workflow_gate_state(base_result, raw_payload)
    workflow_result = {
        "review_result": {"article_package": safe_dict(revised_result.get("article_package"))},
        "draft_result": {"draft_context": safe_dict(revised_result.get("draft_context"))},
        "manual_review": workflow_manual_review,
        "publication_readiness": publication_readiness,
    }
    publish_package = build_publish_package(workflow_result, selected_topic, request)
    workflow_publication_gate = build_workflow_publication_gate(publish_package)

    output_dir_text = clean_text(raw_payload.get("output_dir"))
    if output_dir_text:
        output_dir = Path(output_dir_text).resolve()
    else:
        base_dir = Path(clean_text(raw_payload.get("base_publish_result_path"))).resolve().parent
        output_dir = (base_dir / "wechat-polished-reuse").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    publish_package_path = output_dir / "publish-package.json"
    wechat_html_path = output_dir / "wechat-draft.html"
    acceptance_path = output_dir / "publish-automatic-acceptance.json"
    acceptance_report_path = output_dir / "publish-automatic-acceptance.md"
    report_path = output_dir / "article-publish-reuse-report.md"
    result_path = output_dir / "article-publish-reuse-result.json"

    automatic_acceptance = build_automatic_acceptance_result(
        safe_dict(publish_package.get("regression_checks")),
        target=clean_text(publish_package.get("title")),
        output_dir=str(output_dir),
        regression_source="reuse_publish_package",
        extra_metadata={
            "publish_package_path": str(publish_package_path),
            "base_publish_result_path": clean_text(raw_payload.get("base_publish_result_path")),
            "revised_article_result_path": clean_text(raw_payload.get("revised_article_result_path")),
            "workflow_publication_gate": workflow_publication_gate,
        },
    )
    automatic_acceptance["report_markdown"] = build_automatic_acceptance_markdown(automatic_acceptance)

    write_json(publish_package_path, publish_package)
    wechat_html_path.write_text(publish_package.get("content_html", ""), encoding="utf-8-sig")
    write_json(acceptance_path, automatic_acceptance)
    acceptance_report_path.write_text(automatic_acceptance["report_markdown"], encoding="utf-8-sig")

    result = {
        "status": "ok",
        "selected_topic": selected_topic,
        "request": request,
        "publish_package": publish_package,
        "publish_package_path": str(publish_package_path),
        "wechat_html_path": str(wechat_html_path),
        "automatic_acceptance": automatic_acceptance,
        "automatic_acceptance_path": str(acceptance_path),
        "automatic_acceptance_report_path": str(acceptance_report_path),
        "workflow_manual_review": workflow_manual_review,
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or publication_readiness,
        "workflow_publication_gate": workflow_publication_gate,
        "base_publish_result_path": clean_text(raw_payload.get("base_publish_result_path")),
        "revised_article_result_path": clean_text(raw_payload.get("revised_article_result_path")),
        "output_dir": str(output_dir),
    }
    result["report_markdown"] = build_reuse_report_markdown(result)
    result["report_path"] = str(report_path)
    report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    write_json(result_path, result)
    result["result_path"] = str(result_path)
    return result


__all__ = ["build_reuse_publish_result", "build_reuse_report_markdown", "load_json", "write_json"]
