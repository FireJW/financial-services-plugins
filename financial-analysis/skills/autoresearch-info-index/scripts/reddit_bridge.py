#!/usr/bin/env python3
"""
Run a one-shot Reddit result import and bridge it into news-index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reddit_bridge_runtime import load_json, run_reddit_bridge, write_json


def emit_json(payload: dict, *, stream: object = sys.stdout) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        print(json.dumps(payload, indent=2, ensure_ascii=True), file=stream)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge exported Reddit results into the recency-first news-index workflow."
    )
    parser.add_argument("input", nargs="?", help="Optional path to a Reddit bridge request JSON file")
    parser.add_argument("--file", help="Optional path to a Reddit result file or exported directory")
    parser.add_argument("--topic", help="Optional topic override")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write requested files.",
    )
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve()) if args.input else {}
    if args.file:
        payload["reddit_result_path"] = args.file
    if args.topic:
        payload["topic"] = args.topic
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_reddit_bridge(build_payload(args))
        if not args.quiet:
            emit_json(result)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0 if result.get("import_summary", {}).get("imported_candidate_count") else 1)
    except Exception as exc:
        emit_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
