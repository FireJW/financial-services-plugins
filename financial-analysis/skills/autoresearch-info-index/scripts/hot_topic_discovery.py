#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import load_json, write_json
from hot_topic_discovery_runtime import run_hot_topic_discovery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and rank hot topics from live feeds or manual candidates.")
    parser.add_argument("input", nargs="?", help="Optional JSON request path")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument("--topic", help="Optional explicit topic query")
    parser.add_argument("--sources", nargs="*", help="Optional source override list")
    parser.add_argument("--limit", type=int, help="Optional per-source item limit")
    parser.add_argument("--top-n", type=int, help="Optional ranked topic count to keep")
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
        payload.setdefault("query", args.topic)
    if args.sources:
        payload["sources"] = args.sources
    if args.limit is not None:
        payload["limit"] = args.limit
    if args.top_n is not None:
        payload["top_n"] = args.top_n
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_hot_topic_discovery(build_payload(args))
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
