#!/usr/bin/env python3
"""
Create phase 1 code-fix run records for all bug samples in one directory.

This script is intentionally zero-dependency. It reuses the single-file
run-record scaffold logic from init_run_record.py and applies it to every
`bug-*.json` sample in the input directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from init_run_record import build_run_record, load_bug


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "sample-pool" / "bugs"
    default_output = script_dir.parent / "examples"

    parser = argparse.ArgumentParser(
        description="Create run-record JSON scaffolds for all phase 1 bug samples."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing bug sample JSON files. Defaults to ../sample-pool/bugs",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory to write generated run-record JSON files. Defaults to ../examples",
    )
    parser.add_argument(
        "--sample-set-version",
        default="code-fix-sample-v1",
        help="Sample set version to write into every run record",
    )
    parser.add_argument(
        "--baseline-version",
        default="baseline-v1",
        help="Baseline version label",
    )
    parser.add_argument(
        "--candidate-version",
        default="candidate-v2",
        help="Candidate version label",
    )
    parser.add_argument(
        "--last-stable-version",
        default="baseline-v1",
        help="Last stable version label for rollback",
    )
    return parser.parse_args()


def iter_bug_files(input_dir: Path) -> list[Path]:
    files = sorted(
        path for path in input_dir.glob("bug-*.json") if path.name != "bug-template.json"
    )
    if not files:
        raise ValueError(f"No bug sample files found in {input_dir}")
    return files


def output_path_for(output_dir: Path, bug_id: str) -> Path:
    return output_dir / f"{bug_id}-run-record.json"


def build_summary(input_dir: Path, output_dir: Path, generated: list[dict[str, str]]) -> dict:
    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_generated": len(generated),
        "generated_files": generated,
    }


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    try:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        bug_files = iter_bug_files(input_dir)

        generated: list[dict[str, str]] = []
        for bug_file in bug_files:
            bug = load_bug(bug_file)
            bug["_source_file"] = str(bug_file)
            run_record = build_run_record(bug, args)

            output_path = output_path_for(output_dir, bug["bug_id"])
            output_path.write_text(json.dumps(run_record, indent=2), encoding="utf-8")
            generated.append(
                {
                    "bug_id": bug["bug_id"],
                    "source_file": str(bug_file),
                    "output_file": str(output_path),
                }
            )

        summary = build_summary(input_dir, output_dir, generated)
        print(json.dumps(summary, indent=2))
        sys.exit(0)
    except Exception as exc:
        error = {
            "status": "ERROR",
            "message": str(exc),
        }
        print(json.dumps(error, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
