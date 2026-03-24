#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_library_refresh_runtime import load_json, run_benchmark_library_refresh, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh a benchmark cases library, discover candidates, and optionally rerun benchmark-index."
    )
    parser.add_argument("input", help="Path to a benchmark refresh request JSON file")
    parser.add_argument("--output", help="Optional path to save the refresh result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the refresh markdown report")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = load_json(Path(args.input).resolve())
        if not payload.get("analysis_time"):
            payload["analysis_time"] = datetime.now().astimezone().isoformat(timespec="seconds")
        result = run_benchmark_library_refresh(payload)
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
