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
from article_publish_runtime import run_article_publish


def normalize_article_framework_arg(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover a hot topic or use a provided topic, run the article workflow, and export a WeChat-ready draft package."
    )
    parser.add_argument("input", nargs="?", help="Optional request JSON path")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument("--topic", help="Optional explicit topic override")
    parser.add_argument("--sources", nargs="*", help="Optional discovery source override list")
    parser.add_argument("--discovery-limit", type=int, help="Optional per-source discovery item limit")
    parser.add_argument("--discovery-top-n", type=int, help="Optional ranked topic count to keep")
    parser.add_argument("--selected-topic-index", type=int, help="Optional 1-based ranked topic index to publish")
    parser.add_argument("--audience-keywords", nargs="*", help="Optional audience keyword overrides")
    parser.add_argument("--preferred-topic-keywords", nargs="*", help="Optional topic preference keywords")
    parser.add_argument("--excluded-topic-keywords", nargs="*", help="Optional topic exclusion keywords")
    parser.add_argument("--min-total-score", type=int, help="Optional minimum topic score to keep")
    parser.add_argument("--min-source-count", type=int, help="Optional minimum source count to keep")
    parser.add_argument("--output-dir", help="Optional output directory for staged files")
    parser.add_argument("--title-hint", help="Optional title hint passed into article workflow")
    parser.add_argument("--subtitle-hint", help="Optional subtitle hint passed into article workflow")
    parser.add_argument("--angle", help="Optional article angle override")
    parser.add_argument("--tone", help="Optional tone override")
    parser.add_argument("--target-length-chars", type=int, help="Optional article target length in Chinese characters")
    parser.add_argument("--draft-mode", choices=["balanced", "image_first", "image_only"], help="Draft mode")
    parser.add_argument(
        "--article-framework",
        type=normalize_article_framework_arg,
        choices=["auto", "hot_comment", "deep_analysis", "tutorial", "story", "list", "opinion"],
        help="Optional public article framework override",
    )
    parser.add_argument(
        "--editor-anchor-mode",
        choices=["hidden", "inline"],
        help="Whether editor anchors should stay review-only or render inline in HTML",
    )
    parser.add_argument(
        "--headline-hook-mode",
        choices=["auto", "neutral", "traffic", "aggressive"],
        help="Optional Chinese headline hook strategy for higher-click public titles",
    )
    parser.add_argument(
        "--headline-hook-prefixes",
        nargs="*",
        help="Optional explicit headline hook prefixes, used before the generated Chinese title",
    )
    parser.add_argument("--image-strategy", choices=["mixed", "prefer_images", "screenshots_only"], help="Image strategy")
    parser.add_argument("--max-images", type=int, help="Max images to keep")
    parser.add_argument("--feedback-profile-dir", help="Optional feedback profile directory override")
    parser.add_argument("--account-name", help="Optional public account name for the publish package")
    parser.add_argument("--author", help="Optional author name for the publish package")
    parser.add_argument("--digest-max-chars", type=int, help="Optional digest max length")
    parser.add_argument("--show-cover-pic", type=int, choices=[0, 1], help="Whether WeChat should display the cover pic")
    parser.add_argument("--need-open-comment", action="store_true", help="Enable comments on the pushed draft")
    parser.add_argument("--only-fans-can-comment", action="store_true", help="Restrict comments to followers")
    parser.add_argument("--push-to-wechat", action="store_true", help="Upload images and create a real WeChat draft if credentials are available")
    parser.add_argument("--push-to-channel", action="store_true", help="Push the shared publish_package to the adapter selected by --publish-channel")
    parser.add_argument("--publish-channel", choices=["wechat", "toutiao"], help="Choose which platform adapter should consume the shared publish_package")
    parser.add_argument("--human-review-approved", action="store_true", help="Mark the article as human-reviewed so a real WeChat push is allowed")
    parser.add_argument("--human-review-approved-by", help="Optional reviewer name recorded for the push gate")
    parser.add_argument("--human-review-note", help="Optional review note recorded for the push gate")
    parser.add_argument("--push-backend", choices=["api", "browser_session", "auto"], help="Choose API push, browser-session push, or auto fallback")
    parser.add_argument("--browser-session-strategy", choices=["remote_debugging"], help="Browser-session strategy for WeChat fallback")
    parser.add_argument("--browser-debug-endpoint", help="Remote debugging endpoint, e.g. http://127.0.0.1:9222")
    parser.add_argument("--browser-wait-ms", type=int, help="Browser-session settle wait in milliseconds")
    parser.add_argument("--browser-home-url", help="Optional browser-session home URL override")
    parser.add_argument("--browser-editor-url", help="Optional browser-session editor URL override")
    parser.add_argument("--browser-session-required", action="store_true", help="Mark browser-session fallback as required")
    parser.add_argument("--wechat-app-id", help="Optional WeChat app id override")
    parser.add_argument("--wechat-app-secret", help="Optional WeChat app secret override")
    parser.add_argument("--cover-image-path", help="Optional local cover image override")
    parser.add_argument("--cover-image-url", help="Optional remote cover image override")
    parser.add_argument("--timeout-seconds", type=int, help="Optional WeChat API timeout override")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload: dict = {}
    if args.input:
        payload = load_json(Path(args.input).resolve())
        if not isinstance(payload, dict):
            raise ValueError("Input file must contain a JSON object")
    if args.topic:
        payload["topic"] = args.topic
    if args.sources is not None:
        payload["sources"] = args.sources
    if args.discovery_limit is not None:
        payload["discovery_limit"] = args.discovery_limit
    if args.discovery_top_n is not None:
        payload["discovery_top_n"] = args.discovery_top_n
    if args.selected_topic_index is not None:
        payload["selected_topic_index"] = args.selected_topic_index
    if args.audience_keywords is not None:
        payload["audience_keywords"] = args.audience_keywords
    if args.preferred_topic_keywords is not None:
        payload["preferred_topic_keywords"] = args.preferred_topic_keywords
    if args.excluded_topic_keywords is not None:
        payload["excluded_topic_keywords"] = args.excluded_topic_keywords
    if args.min_total_score is not None:
        payload["min_total_score"] = args.min_total_score
    if args.min_source_count is not None:
        payload["min_source_count"] = args.min_source_count
    if args.output_dir:
        payload["output_dir"] = args.output_dir
    if args.title_hint:
        payload["title_hint"] = args.title_hint
    if args.subtitle_hint:
        payload["subtitle_hint"] = args.subtitle_hint
    if args.angle:
        payload["angle"] = args.angle
    if args.tone:
        payload["tone"] = args.tone
    if args.target_length_chars is not None:
        payload["target_length_chars"] = args.target_length_chars
    if args.draft_mode:
        payload["draft_mode"] = args.draft_mode
    if args.article_framework:
        payload["article_framework"] = args.article_framework
    if args.editor_anchor_mode:
        payload["editor_anchor_mode"] = args.editor_anchor_mode
    if args.headline_hook_mode:
        payload["headline_hook_mode"] = args.headline_hook_mode
    if args.headline_hook_prefixes is not None:
        payload["headline_hook_prefixes"] = args.headline_hook_prefixes
    if args.image_strategy:
        payload["image_strategy"] = args.image_strategy
    if args.max_images is not None:
        payload["max_images"] = args.max_images
    if args.feedback_profile_dir:
        payload["feedback_profile_dir"] = args.feedback_profile_dir
    if args.account_name:
        payload["account_name"] = args.account_name
    if args.author:
        payload["author"] = args.author
    if args.digest_max_chars is not None:
        payload["digest_max_chars"] = args.digest_max_chars
    if args.show_cover_pic is not None:
        payload["show_cover_pic"] = args.show_cover_pic
    if args.need_open_comment:
        payload["need_open_comment"] = True
    if args.only_fans_can_comment:
        payload["only_fans_can_comment"] = True
    if args.push_to_wechat:
        payload["push_to_wechat"] = True
    if args.push_to_channel:
        payload["push_to_channel"] = True
    if args.publish_channel:
        payload["publish_channel"] = args.publish_channel
    if args.human_review_approved:
        payload["human_review_approved"] = True
    if args.human_review_approved_by:
        payload["human_review_approved_by"] = args.human_review_approved_by
    if args.human_review_note:
        payload["human_review_note"] = args.human_review_note
    if args.push_backend:
        payload["push_backend"] = args.push_backend
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
    if args.wechat_app_id:
        payload["wechat_app_id"] = args.wechat_app_id
    if args.wechat_app_secret:
        payload["wechat_app_secret"] = args.wechat_app_secret
    if args.cover_image_path:
        payload["cover_image_path"] = args.cover_image_path
    if args.cover_image_url:
        payload["cover_image_url"] = args.cover_image_url
    if args.timeout_seconds is not None:
        payload["timeout_seconds"] = args.timeout_seconds
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_article_publish(build_payload(args))
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
