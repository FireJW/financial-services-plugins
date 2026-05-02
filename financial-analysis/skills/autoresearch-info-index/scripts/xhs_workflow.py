#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xhs_workflow_runtime import load_json, run_xhs_workflow, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local Xiaohongshu GPT Image workflow package.")
    parser.add_argument("input", help="Path to xhs workflow request JSON")
    parser.add_argument("--output", help="Optional path to save summary JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = run_xhs_workflow(load_json(Path(args.input).resolve()))
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if not args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
