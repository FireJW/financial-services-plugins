#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import load_json
from cli_output import print_json
from wechat_push_readiness_runtime import run_wechat_push_readiness_audit, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit whether a WeChat publish package is truly ready for a real draft-box push.")
    parser.add_argument("input", help="Path to a publish-package JSON or an article-publish result JSON")
    parser.add_argument("--output", help="Optional path to save the readiness result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the readiness markdown report")
    parser.add_argument("--cover-image-path", help="Optional explicit local cover override for the audit")
    parser.add_argument("--cover-image-url", help="Optional explicit remote cover override for the audit")
    parser.add_argument("--human-review-approved", action="store_true", help="Treat the package as human-reviewed during the audit")
    parser.add_argument("--human-review-approved-by", help="Optional reviewer name recorded in the audit")
    parser.add_argument("--human-review-note", help="Optional review note recorded in the audit")
    parser.add_argument("--validate-live-auth", action="store_true", help="Fetch a real access token to verify the current WeChat credentials")
    parser.add_argument("--wechat-app-id", help="Optional unsafe inline AppID override for the audit")
    parser.add_argument("--wechat-app-secret", help="Optional unsafe inline AppSecret override for the audit")
    parser.add_argument(
        "--allow-insecure-inline-credentials",
        action="store_true",
        help="Explicitly allow inline credentials during the audit. Prefer env vars or .env.wechat.local instead.",
    )
    parser.add_argument("--timeout-seconds", type=int, help="Optional WeChat API timeout override")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    payload = load_json(Path(args.input).resolve())
    if not isinstance(payload, dict):
        raise ValueError("Input file must contain a JSON object")
    payload["_input_path"] = str(Path(args.input).resolve())
    if args.cover_image_path:
        payload["cover_image_path"] = args.cover_image_path
    if args.cover_image_url:
        payload["cover_image_url"] = args.cover_image_url
    if args.human_review_approved:
        payload["human_review_approved"] = True
    if args.human_review_approved_by:
        payload["human_review_approved_by"] = args.human_review_approved_by
    if args.human_review_note:
        payload["human_review_note"] = args.human_review_note
    if args.validate_live_auth:
        payload["validate_live_auth"] = True
    if args.wechat_app_id:
        payload["wechat_app_id"] = args.wechat_app_id
    if args.wechat_app_secret:
        payload["wechat_app_secret"] = args.wechat_app_secret
    if args.allow_insecure_inline_credentials:
        payload["allow_insecure_inline_credentials"] = True
    if args.timeout_seconds is not None:
        payload["timeout_seconds"] = args.timeout_seconds
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_wechat_push_readiness_audit(build_payload(args))
        if not args.quiet:
            print_json(result)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
