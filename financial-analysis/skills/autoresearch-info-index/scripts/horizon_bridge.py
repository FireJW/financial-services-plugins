#!/usr/bin/env python3
"""
Run a one-shot Horizon saved-payload import and bridge it into news-index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from horizon_bridge_runtime import load_json, run_horizon_bridge, write_json


def emit_json(payload: dict, *, stream: object = sys.stdout) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        print(json.dumps(payload, indent=2, ensure_ascii=True), file=stream)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge a saved Horizon result payload into the recency-first news-index workflow."
    )
    parser.add_argument("input", help="Path to a Horizon bridge request JSON file")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write requested files.",
    )
    return parser.parse_args()


def companion_stem(output_path: Path) -> str:
    stem = output_path.stem
    if stem.endswith("-result"):
        stem = stem[: -len("-result")]
    if stem in {"result", "output"}:
        stem = "horizon-bridge"
    return stem or "horizon-bridge"


def companion_base_path(args: argparse.Namespace) -> Path | None:
    if args.output:
        return Path(args.output).resolve()
    if args.markdown_output:
        return Path(args.markdown_output).resolve().with_suffix(".json")
    return None


def write_companion_artifacts(result: dict, base_path: Path | None) -> None:
    if base_path is None:
        return
    base_path.parent.mkdir(parents=True, exist_ok=True)
    stem = companion_stem(base_path)
    completion_path = base_path.parent / f"{stem}-completion-check.json"
    completion_report_path = base_path.parent / f"{stem}-completion-check.md"
    operator_path = base_path.parent / f"{stem}-operator-summary.json"
    operator_report_path = base_path.parent / f"{stem}-operator-summary.md"
    result["completion_check_path"] = str(completion_path)
    result["completion_check_report_path"] = str(completion_report_path)
    result["operator_summary_path"] = str(operator_path)
    result["operator_summary_report_path"] = str(operator_report_path)
    write_json(completion_path, result.get("completion_check", {}))
    completion_report_path.write_text(result.get("completion_check_markdown", ""), encoding="utf-8")
    write_json(operator_path, result.get("operator_summary", {}))
    operator_report_path.write_text(result.get("operator_summary_markdown", ""), encoding="utf-8")


def main() -> None:
    args = parse_args()
    try:
        result = run_horizon_bridge(load_json(Path(args.input).resolve()))
        write_companion_artifacts(result, companion_base_path(args))
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
