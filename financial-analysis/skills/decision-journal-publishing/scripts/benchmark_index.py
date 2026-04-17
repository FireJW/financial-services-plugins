#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_index_runtime import load_json, run_benchmark_index, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index and review WeChat / Toutiao benchmark article cases for acquisition fit and commercial fit."
    )
    parser.add_argument("input", help="Path to a benchmark-index request JSON file")
    parser.add_argument("--output", help="Optional path to save the benchmark-index result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the benchmark-index markdown report")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = load_json(Path(args.input).resolve())
        result = run_benchmark_index(payload)
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
