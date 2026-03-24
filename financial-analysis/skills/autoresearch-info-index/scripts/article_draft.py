#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_draft_flow_runtime import build_article_draft, load_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an article draft package from an indexed evidence result.")
    parser.add_argument("input", help="Path to a source result JSON file or article-draft request JSON")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument("--title-hint", help="Optional title override")
    parser.add_argument("--subtitle-hint", help="Optional subtitle override")
    parser.add_argument("--angle", help="Optional article angle")
    parser.add_argument("--tone", help="Optional tone")
    parser.add_argument("--target-length", type=int, help="Target article length in characters")
    parser.add_argument("--max-images", type=int, help="Maximum number of image blocks to keep")
    parser.add_argument("--image-strategy", choices=["mixed", "prefer_images", "screenshots_only"], help="Image priority mode")
    parser.add_argument("--draft-mode", choices=["balanced", "image_first", "image_only"], help="Composition mode")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve())
    if not isinstance(payload, dict):
        raise ValueError("Input file must contain a JSON object")
    if not any(key in payload for key in ("source_result", "source_result_path")) and any(
        key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output")
    ):
        payload = {"source_result": payload}
    if args.title_hint:
        payload["title_hint"] = args.title_hint
    if args.subtitle_hint:
        payload["subtitle_hint"] = args.subtitle_hint
    if args.angle:
        payload["angle"] = args.angle
    if args.tone:
        payload["tone"] = args.tone
    if args.target_length is not None:
        payload["target_length_chars"] = args.target_length
    if args.max_images is not None:
        payload["max_images"] = args.max_images
    if args.image_strategy:
        payload["image_strategy"] = args.image_strategy
    if args.draft_mode:
        payload["draft_mode"] = args.draft_mode
    return payload


def main() -> None:
    args = parse_args()
    try:
        payload = build_payload(args)
        result = build_article_draft(payload)
        if not args.quiet:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
