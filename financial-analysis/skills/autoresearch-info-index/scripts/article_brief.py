#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_brief_runtime import build_analysis_brief, load_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an analysis brief from an indexed evidence result.")
    parser.add_argument("input", help="Path to a source result JSON file or article-brief request JSON")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
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
    return payload


def main() -> None:
    args = parse_args()
    try:
        payload = build_payload(args)
        result = build_analysis_brief(payload)
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
