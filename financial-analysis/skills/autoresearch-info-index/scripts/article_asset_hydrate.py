#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_draft_flow_runtime import (
    build_article_preview_html,
    build_report_markdown as build_draft_report_markdown,
    clean_text,
    load_json,
    localize_selected_images,
    safe_dict,
    write_json,
)
from article_workflow_runtime import build_report_markdown as build_workflow_report_markdown, summarize_asset_stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry localizing remote image assets for an existing article draft result.")
    parser.add_argument("draft_result", help="Path to article-draft-result.json or article-revise-result.json")
    parser.add_argument("--asset-output-dir", help="Optional override for local asset directory")
    parser.add_argument("--markdown-output", help="Optional override for markdown report path")
    parser.add_argument("--preview-output", help="Optional override for HTML preview path")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    draft_path = Path(args.draft_result).resolve()
    result = load_json(draft_path)
    if not isinstance(result, dict):
        raise ValueError("Draft result must be a JSON object")

    article_package = result.get("article_package")
    if not isinstance(article_package, dict):
        raise ValueError("Draft result is missing article_package")

    request = result.get("request") or {}
    if not isinstance(request, dict):
        request = {}
    default_asset_dir = draft_path.parent / "assets"
    request["asset_output_dir"] = clean_text(args.asset_output_dir) or clean_text(request.get("asset_output_dir")) or str(default_asset_dir)
    request["download_remote_images"] = True

    localization = localize_selected_images(article_package, request)
    result["article_package"] = article_package
    result["asset_localization"] = localization
    result["preview_html"] = build_article_preview_html(article_package)
    result["report_markdown"] = build_draft_report_markdown(article_package)
    write_json(draft_path, result)

    markdown_path = Path(args.markdown_output).resolve() if args.markdown_output else draft_path.with_name(draft_path.name.replace("-result.json", "-report.md"))
    preview_path = Path(args.preview_output).resolve() if args.preview_output else draft_path.with_name(draft_path.name.replace("-result.json", "-preview.html"))
    markdown_path.write_text(result.get("report_markdown", ""), encoding="utf-8-sig")
    preview_path.write_text(result.get("preview_html", ""), encoding="utf-8-sig")

    workflow_result_path = draft_path.parent / "workflow-result.json"
    if workflow_result_path.exists():
        workflow_result = load_json(workflow_result_path)
        if isinstance(workflow_result, dict):
            workflow_result["asset_stage"] = summarize_asset_stage(result, draft_path)
            workflow_result["report_markdown"] = build_workflow_report_markdown(workflow_result)
            write_json(workflow_result_path, workflow_result)
            workflow_report_path = Path(
                clean_text(safe_dict(workflow_result).get("workflow_report_path")) or (draft_path.parent / "workflow-report.md")
            ).resolve()
            workflow_report_path.write_text(workflow_result.get("report_markdown", ""), encoding="utf-8-sig")

    if not args.quiet:
        print(json.dumps({"status": "ok", "draft_result": str(draft_path), "asset_localization": localization}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
