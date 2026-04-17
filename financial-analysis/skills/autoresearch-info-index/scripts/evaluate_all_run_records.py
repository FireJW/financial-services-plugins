#!/usr/bin/env python3
"""
Evaluate all run-record JSON files in a directory.

For each ``*-run-record.json`` (or any ``.json``) in the input directory, this
script calls ``evaluate_info_index.build_result()`` and writes the evaluated
output to the ``--output-dir`` directory.

CLI usage (matches ``run_evaluate_all_run_records.cmd``)::

    python evaluate_all_run_records.py <input_dir> --output-dir <dir> [--quiet]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_info_index import build_result, load_input


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "examples" / "batch-run-records"
    default_output = SCRIPT_DIR.parent / "examples" / "batch-evaluated"

    parser = argparse.ArgumentParser(
        description="Evaluate all run-record JSON files in a directory."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing run-record JSON files. Defaults to ../examples/batch-run-records",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory to write evaluated JSON files. Defaults to ../examples/batch-evaluated",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write generated files.",
    )
    return parser.parse_args()


def iter_run_record_files(input_dir: Path) -> list[Path]:
    """Return sorted list of JSON files in *input_dir*, excluding templates."""
    files = sorted(
        path
        for path in input_dir.glob("*.json")
        if path.name != "item-template.json"
    )
    if not files:
        raise ValueError(f"No run-record JSON files found in {input_dir}")
    return files


def output_path_for(output_dir: Path, source_name: str) -> Path:
    """Derive the evaluated output filename from the source filename."""
    stem = source_name
    if stem.endswith("-run-record"):
        stem = stem[: -len("-run-record")]
    return output_dir / f"{stem}-evaluated.json"


def evaluate_one(run_record_path: Path) -> dict[str, Any]:
    """Load and evaluate a single run-record file."""
    payload = load_input(run_record_path)
    return build_result(payload)


def build_summary(
    input_dir: Path,
    output_dir: Path,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a summary dict of the batch evaluation."""
    keep_count = sum(1 for r in results if r.get("keep"))
    rollback_count = sum(1 for r in results if not r.get("keep"))

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_evaluated": len(results),
        "keep_count": keep_count,
        "rollback_count": rollback_count,
        "evaluated_files": results,
    }


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    has_rollback = False

    try:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        run_record_files = iter_run_record_files(input_dir)

        summary_entries: list[dict[str, Any]] = []
        for run_record_path in run_record_files:
            try:
                result = evaluate_one(run_record_path)
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "source_file": str(run_record_path),
                    "message": str(exc),
                }

            out_path = output_path_for(output_dir, run_record_path.stem)
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            decision = result.get("decision", {})
            keep = decision.get("keep", False) if isinstance(decision, dict) else False
            if not keep:
                has_rollback = True

            summary_entries.append(
                {
                    "source_file": str(run_record_path),
                    "output_file": str(out_path),
                    "task_id": result.get("task_id", ""),
                    "keep": keep,
                    "reason": decision.get("reason", "") if isinstance(decision, dict) else "",
                }
            )

        if not args.quiet:
            print(
                json.dumps(
                    build_summary(input_dir, output_dir, summary_entries),
                    indent=2,
                    ensure_ascii=False,
                )
            )

        # Exit 0 = all keep, exit 2 = at least one rollback (matches evaluate_info_index convention)
        sys.exit(2 if has_rollback else 0)

    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(error, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
