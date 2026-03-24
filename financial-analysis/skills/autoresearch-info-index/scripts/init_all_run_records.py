#!/usr/bin/env python3
"""
Create phase 1 info-index run records for all sample items in one directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from init_run_record import build_run_record, load_item


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "sample-pool" / "items"
    default_output = SCRIPT_DIR.parent / "examples" / "batch-run-records"

    parser = argparse.ArgumentParser(
        description="Create run-record JSON scaffolds for all phase 1 info-index samples."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing sample JSON files. Defaults to ../sample-pool/items",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory to write generated run-record JSON files. Defaults to ../examples/batch-run-records",
    )
    parser.add_argument("--sample-set-version", default="info-index-sample-v1", help="Sample set version")
    parser.add_argument("--baseline-version", default="baseline-v1", help="Baseline version label")
    parser.add_argument("--candidate-version", default="candidate-v2", help="Candidate version label")
    parser.add_argument("--last-stable-version", default="baseline-v1", help="Last stable version label")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write generated files.",
    )
    return parser.parse_args()


def iter_item_files(input_dir: Path) -> list[Path]:
    files = sorted(path for path in input_dir.glob("*.json") if path.name != "item-template.json")
    if not files:
        raise ValueError(f"No sample item files found in {input_dir}")
    return files


def output_path_for(output_dir: Path, item_id: str) -> Path:
    return output_dir / f"{item_id}-run-record.json"


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
        item_files = iter_item_files(input_dir)

        generated: list[dict[str, str]] = []
        for item_file in item_files:
            item = load_item(item_file)
            item["_source_file"] = str(item_file)
            run_record = build_run_record(item, args)

            output_path = output_path_for(output_dir, item["item_id"])
            output_path.write_text(json.dumps(run_record, indent=2), encoding="utf-8")
            generated.append(
                {
                    "item_id": item["item_id"],
                    "source_file": str(item_file),
                    "output_file": str(output_path),
                }
            )

        if not args.quiet:
            print(json.dumps(build_summary(input_dir, output_dir, generated), indent=2))
        sys.exit(0)
    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
