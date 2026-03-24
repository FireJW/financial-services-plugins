#!/usr/bin/env python3
"""
Evaluate all phase 1 code-fix run records in one directory.

This script is intentionally zero-dependency. It reuses the single-file
evaluation logic from evaluate_code_fix.py and applies it to every
`*-run-record.json` file in the input directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_code_fix import build_result, load_input


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "examples" / "batch-run-records"
    default_output = SCRIPT_DIR.parent / "examples" / "batch-evaluated"

    parser = argparse.ArgumentParser(
        description="Evaluate all code-fix run-record JSON files in one directory."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing *-run-record.json files. Defaults to ../examples/batch-run-records",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory to write *-evaluated.json files. Defaults to ../examples/batch-evaluated",
    )
    parser.add_argument(
        "--summary-name",
        default="evaluation-summary.json",
        help="Filename for the written summary JSON inside the output directory",
    )
    return parser.parse_args()


def iter_run_record_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("*-run-record.json"))
    if not files:
        raise ValueError(f"No *-run-record.json files found in {input_dir}")
    return files


def output_path_for(output_dir: Path, run_record_path: Path) -> Path:
    output_name = run_record_path.name.replace("-run-record.json", "-evaluated.json")
    return output_dir / output_name


def evaluate_one(run_record_path: Path, output_dir: Path) -> dict:
    payload = load_input(run_record_path)
    result = build_result(payload)

    output_path = output_path_for(output_dir, run_record_path)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return {
        "task_id": result.get("task_id", ""),
        "input_file": str(run_record_path),
        "output_file": str(output_path),
        "keep": bool(result.get("decision", {}).get("keep", False)),
        "rollback_to": result.get("decision", {}).get("rollback_to", ""),
        "candidate_total": result.get("soft_scores", {}).get("candidate_total"),
        "baseline_total": result.get("soft_scores", {}).get("baseline_total"),
        "delta": result.get("soft_scores", {}).get("delta"),
        "hard_checks_passed": bool(result.get("hard_checks", {}).get("passed", False)),
    }


def build_summary(input_dir: Path, output_dir: Path, evaluated_files: list[dict], failed_files: list[dict]) -> dict:
    keep_count = sum(1 for item in evaluated_files if item["keep"])
    rollback_count = len(evaluated_files) - keep_count

    return {
        "status": "OK" if not failed_files else "PARTIAL_ERROR",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_found": len(evaluated_files) + len(failed_files),
        "total_evaluated": len(evaluated_files),
        "total_failed": len(failed_files),
        "keep_count": keep_count,
        "rollback_count": rollback_count,
        "evaluated_files": evaluated_files,
        "failed_files": failed_files,
    }


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    try:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        run_record_files = iter_run_record_files(input_dir)

        evaluated_files: list[dict] = []
        failed_files: list[dict] = []

        for run_record_path in run_record_files:
            try:
                evaluated_files.append(evaluate_one(run_record_path, output_dir))
            except Exception as exc:
                failed_files.append(
                    {
                        "input_file": str(run_record_path),
                        "message": str(exc),
                    }
                )

        summary = build_summary(input_dir, output_dir, evaluated_files, failed_files)
        summary_path = output_dir / args.summary_name
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print(json.dumps(summary, indent=2))
        sys.exit(0 if not failed_files else 1)
    except Exception as exc:
        error = {
            "status": "ERROR",
            "message": str(exc),
        }
        print(json.dumps(error, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
