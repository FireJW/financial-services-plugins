#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xhs_workflow_runtime import build_readiness_report, load_json, run_xhs_workflow, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local Xiaohongshu GPT Image workflow package.")
    parser.add_argument("input", help="Path to xhs workflow request JSON")
    parser.add_argument("--benchmark-file", help="Optional imported benchmark JSON file")
    parser.add_argument("--benchmark-source", help="Optional benchmark source label")
    parser.add_argument("--doctor", action="store_true", help="Check request readiness without generating a package")
    parser.add_argument("--run-collector", action="store_true", help="Run the configured collector before building the package")
    parser.add_argument("--output", help="Optional path to save summary JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve())
    if args.benchmark_file:
        payload["benchmark_file"] = args.benchmark_file
    if args.benchmark_source:
        payload["benchmark_source"] = args.benchmark_source
    if args.run_collector:
        collector = dict(payload.get("collector") or {})
        collector["auto_run"] = True
        payload["collector"] = collector
    return payload


def main() -> None:
    args = parse_args()
    try:
        payload = build_payload(args)
        result = build_readiness_report(payload) if args.doctor else run_xhs_workflow(payload)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if not args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1 if args.doctor and result.get("status") == "blocked" else 0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
