#!/usr/bin/env python3
"""
Run a one-shot OpenCLI import and bridge it into news-index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from opencli_bridge_runtime import load_json, run_opencli_bridge, write_json


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "examples" / "opencli-bridge-request.template.json"
    parser = argparse.ArgumentParser(
        description="Bridge an OpenCLI-style capture result into the recency-first news-index workflow."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(default_input),
        help="Path to an OpenCLI bridge request JSON file",
    )
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write requested files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = load_json(Path(args.input).resolve())
        result = run_opencli_bridge(payload)
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
        print(
            json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
