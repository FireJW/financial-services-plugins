#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import load_json, write_json
from cli_output import print_json
from wechat_draftbox_runtime import push_publish_package_to_wechat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push a publish-package into the WeChat Official Account draft box.")
    parser.add_argument("input", help="Path to a publish-package result JSON or a request JSON containing publish_package_path")
    parser.add_argument("--output", help="Optional path to save the push result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save a small markdown summary")
    parser.add_argument("--cover-image-path", help="Optional explicit local cover image override")
    parser.add_argument("--cover-image-url", help="Optional explicit remote cover image override")
    parser.add_argument("--author", help="Optional author override for the pushed draft")
    parser.add_argument("--show-cover-pic", type=int, choices=[0, 1], help="Whether WeChat should display the cover pic")
    parser.add_argument("--human-review-approved", action="store_true", help="Mark the article as human-reviewed so a real WeChat push is allowed")
    parser.add_argument("--human-review-approved-by", help="Optional reviewer name recorded for the push gate")
    parser.add_argument("--human-review-note", help="Optional review note recorded for the push gate")
    parser.add_argument("--wechat-app-id", help="Optional WeChat app id override")
    parser.add_argument("--wechat-app-secret", help="Optional WeChat app secret override")
    parser.add_argument("--timeout-seconds", type=int, help="Optional WeChat API timeout override")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve())
    if not isinstance(payload, dict):
        raise ValueError("Input file must contain a JSON object")
    if "publish_package" not in payload and "contract_version" in payload:
        payload = {"publish_package": payload}
    if args.cover_image_path:
        payload["cover_image_path"] = args.cover_image_path
    if args.cover_image_url:
        payload["cover_image_url"] = args.cover_image_url
    if args.author:
        payload["author"] = args.author
    if args.show_cover_pic is not None:
        payload["show_cover_pic"] = args.show_cover_pic
    if args.human_review_approved:
        payload["human_review_approved"] = True
    if args.human_review_approved_by:
        payload["human_review_approved_by"] = args.human_review_approved_by
    if args.human_review_note:
        payload["human_review_note"] = args.human_review_note
    if args.wechat_app_id:
        payload["wechat_app_id"] = args.wechat_app_id
    if args.wechat_app_secret:
        payload["wechat_app_secret"] = args.wechat_app_secret
    if args.timeout_seconds is not None:
        payload["timeout_seconds"] = args.timeout_seconds
    return payload


def build_markdown(result: dict) -> str:
    lines = [
        "# WeChat Draft Push",
        "",
        f"- Status: {result.get('status', '')}",
        f"- Draft media_id: {result.get('draft_result', {}).get('media_id', '')}",
        f"- Inline images uploaded: {len(result.get('uploaded_inline_images', []))}",
        f"- Cover media_id: {result.get('uploaded_cover', {}).get('media_id', '')}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    try:
        result = push_publish_package_to_wechat(build_payload(args))
        if not args.quiet:
            print_json(result)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(build_markdown(result), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
