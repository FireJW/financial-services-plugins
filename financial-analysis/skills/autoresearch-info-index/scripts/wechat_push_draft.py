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
from news_index_runtime import write_json
from wechat_draftbox_runtime import push_publish_package_to_wechat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push a WeChat publish package into the official account draft box.")
    parser.add_argument("input", help="Path to a publish-package JSON or a push-request JSON")
    parser.add_argument("--output", help="Optional path to save the push result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save a short push markdown report")
    parser.add_argument("--push-backend", choices=["api", "browser_session", "auto"], help="Choose API push, browser-session push, or auto fallback")
    parser.add_argument("--wechat-env-file", help="Optional path to a local .env.wechat.local file")
    parser.add_argument("--wechat-app-id", help="Optional unsafe inline AppID override")
    parser.add_argument("--wechat-app-secret", help="Optional unsafe inline AppSecret override")
    parser.add_argument("--allow-insecure-inline-credentials", action="store_true", help="Explicitly allow inline credentials")
    parser.add_argument("--human-review-approved", action="store_true", help="Mark the package as human-reviewed for real push")
    parser.add_argument("--human-review-approved-by", help="Optional reviewer name recorded in the push gate")
    parser.add_argument("--human-review-note", help="Optional review note recorded in the push gate")
    parser.add_argument("--browser-session-strategy", choices=["remote_debugging"], help="Browser-session strategy")
    parser.add_argument("--browser-debug-endpoint", help="Remote debugging endpoint, e.g. http://127.0.0.1:9222")
    parser.add_argument("--browser-wait-ms", type=int, help="Browser-session settle wait in milliseconds")
    parser.add_argument("--browser-home-url", help="Optional browser-session home URL override")
    parser.add_argument("--browser-editor-url", help="Optional browser-session editor URL override")
    parser.add_argument("--browser-session-required", action="store_true", help="Mark browser-session fallback as required")
    parser.add_argument("--timeout-seconds", type=int, help="Optional WeChat API timeout override")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    input_path = Path(args.input).resolve()
    payload = load_json(input_path)
    if not isinstance(payload, dict):
        raise ValueError("Input file must contain a JSON object")
    if "publish_package" not in payload:
        payload = {"publish_package": payload, "_input_path": str(input_path)}
    else:
        payload["_input_path"] = str(input_path)
    if args.push_backend:
        payload["push_backend"] = args.push_backend
    if args.wechat_env_file:
        payload["wechat_env_file"] = args.wechat_env_file
    if args.wechat_app_id:
        payload["wechat_app_id"] = args.wechat_app_id
    if args.wechat_app_secret:
        payload["wechat_app_secret"] = args.wechat_app_secret
    if args.allow_insecure_inline_credentials:
        payload["allow_insecure_inline_credentials"] = True
    if args.human_review_approved:
        payload["human_review_approved"] = True
    if args.human_review_approved_by:
        payload["human_review_approved_by"] = args.human_review_approved_by
    if args.human_review_note:
        payload["human_review_note"] = args.human_review_note
    browser_session = payload.get("browser_session") if isinstance(payload.get("browser_session"), dict) else {}
    if args.browser_session_strategy:
        browser_session["strategy"] = args.browser_session_strategy
    if args.browser_debug_endpoint:
        browser_session["cdp_endpoint"] = args.browser_debug_endpoint
    if args.browser_wait_ms is not None:
        browser_session["wait_ms"] = args.browser_wait_ms
    if args.browser_home_url:
        browser_session["home_url"] = args.browser_home_url
    if args.browser_editor_url:
        browser_session["editor_url"] = args.browser_editor_url
    if args.browser_session_required:
        browser_session["required"] = True
    if browser_session:
        payload["browser_session"] = browser_session
    if args.timeout_seconds is not None:
        payload["timeout_seconds"] = args.timeout_seconds
    return payload


def build_report_markdown(result: dict[str, object]) -> str:
    lines = [
        "# WeChat Draft Push",
        "",
        f"- Status: {result.get('status', '') or 'unknown'}",
        f"- Push backend: {result.get('push_backend', '') or 'unknown'}",
    ]
    draft_result = result.get("draft_result") if isinstance(result.get("draft_result"), dict) else {}
    uploaded_cover = result.get("uploaded_cover") if isinstance(result.get("uploaded_cover"), dict) else {}
    review_gate = result.get("review_gate") if isinstance(result.get("review_gate"), dict) else {}
    if draft_result:
        lines.append(f"- Draft media id: {draft_result.get('media_id', '') or 'none'}")
    if uploaded_cover:
        lines.append(f"- Cover media id: {uploaded_cover.get('media_id', '') or 'none'}")
    lines.append(f"- Review gate: {review_gate.get('status', '') or 'unknown'}")
    return "\n".join(lines).strip() + "\n"


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
            output_path.write_text(build_report_markdown(result), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
