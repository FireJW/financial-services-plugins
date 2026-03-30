#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import write_json
from cli_output import print_json
from wechat_live_setup_runtime import run_wechat_live_setup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create safe local WeChat live-push scaffold files from tracked templates.")
    parser.add_argument("--request-template-path", help="Optional tracked request template override")
    parser.add_argument("--env-template-path", help="Optional tracked env template override")
    parser.add_argument("--request-output-path", help="Optional local request output path")
    parser.add_argument("--env-output-path", help="Optional local env output path")
    parser.add_argument("--topic", help="Optional topic override written into the local request file")
    parser.add_argument("--account-name", help="Optional account_name override")
    parser.add_argument("--author", help="Optional author override")
    parser.add_argument("--reviewer-name", help="Optional reviewer name override")
    parser.add_argument("--cover-image-url", help="Optional cover image URL override")
    parser.add_argument("--human-review-note", help="Optional human review note override")
    parser.add_argument("--force", action="store_true", help="Overwrite existing local files instead of keeping them")
    parser.add_argument("--output", help="Optional path to save the setup result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the setup markdown report")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    payload: dict[str, object] = {
        "force": args.force,
    }
    for key in (
        "request_template_path",
        "env_template_path",
        "request_output_path",
        "env_output_path",
        "topic",
        "account_name",
        "author",
        "reviewer_name",
        "cover_image_url",
        "human_review_note",
    ):
        value = getattr(args, key)
        if value:
            payload[key] = value
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_wechat_live_setup(build_payload(args))
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
