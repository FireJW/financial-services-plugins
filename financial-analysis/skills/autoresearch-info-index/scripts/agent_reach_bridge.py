#!/usr/bin/env python3
"""
Run a one-shot Agent Reach import and bridge it into news-index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_reach_bridge_runtime import load_json, run_agent_reach_bridge, write_json


def emit_json(payload: dict, *, stream: object = sys.stdout) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        print(json.dumps(payload, indent=2, ensure_ascii=True), file=stream)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge an Agent Reach payload or live per-channel fetch into the recency-first news-index workflow."
    )
    parser.add_argument("input", nargs="?", help="Optional path to an Agent Reach bridge request JSON file")
    parser.add_argument("--file", help="Optional path to a saved Agent Reach payload to import directly")
    parser.add_argument("--topic", help="Optional live query topic")
    parser.add_argument("--channels", nargs="*", help="Optional channel override list")
    parser.add_argument("--pseudo-home", help="Optional Agent Reach pseudo-home override")
    parser.add_argument("--timeout-per-channel", type=int, help="Optional per-channel timeout in seconds")
    parser.add_argument("--max-results-per-channel", type=int, help="Optional per-channel result cap")
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
        payload["agent_reach_result_path"] = args.file
    if args.topic:
        payload["topic"] = args.topic
        payload.setdefault("query", args.topic)
    if args.channels:
        payload["channels"] = args.channels
    if args.pseudo_home:
        payload["pseudo_home"] = args.pseudo_home
    if args.timeout_per_channel is not None:
        payload["timeout_per_channel"] = args.timeout_per_channel
    if args.max_results_per_channel is not None:
        payload["max_results_per_channel"] = args.max_results_per_channel
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = run_agent_reach_bridge(build_payload(args))
        if not args.quiet:
            emit_json(result)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0 if result.get("channels_succeeded") else 1)
    except Exception as exc:
        emit_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
