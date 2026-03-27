#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from macro_note_workflow_runtime import load_json, run_macro_note_workflow, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the macro-note workflow: index if needed, build the brief, and emit a macro note."
    )
    parser.add_argument("input", help="Path to an indexed result JSON, an x-index request JSON, or a news-index request JSON")
    parser.add_argument("--output", help="Optional path to save the workflow summary JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the macro-note markdown report")
    parser.add_argument("--workflow-markdown-output", help="Optional path to save the workflow summary markdown report")
    parser.add_argument("--output-dir", help="Directory for staged workflow outputs")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve())
    if not isinstance(payload, dict):
        raise ValueError("Input file must contain a JSON object")
    if args.output_dir:
        payload["output_dir"] = args.output_dir
    return payload


def main() -> None:
    args = parse_args()
    try:
        payload = build_payload(args)
        result = run_macro_note_workflow(payload)
        if not args.quiet:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("macro_note_result", {}).get("report_markdown", ""), encoding="utf-8")
        if args.workflow_markdown_output:
            workflow_output_path = Path(args.workflow_markdown_output).resolve()
            workflow_output_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
