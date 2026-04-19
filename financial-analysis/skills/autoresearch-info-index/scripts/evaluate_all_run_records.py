#!/usr/bin/env python3
"""
Evaluate all phase 1 info-index run records in one directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_info_index import build_result, load_input


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "examples" / "batch-run-records"
    default_output = SCRIPT_DIR.parent / "examples" / "batch-evaluated"

    parser = argparse.ArgumentParser(
        description="Evaluate all info-index run-record JSON files in one directory."
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
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write generated files.",
    )
    return parser.parse_args()


def iter_run_record_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("*-run-record.json"))
    if not files:
        raise ValueError(f"No *-run-record.json files found in {input_dir}")
    return files


def output_path_for(output_dir: Path, run_record_path: Path) -> Path:
    return output_dir / run_record_path.name.replace("-run-record.json", "-evaluated.json")


def evaluate_one(run_record_path: Path, output_dir: Path) -> dict:
    payload = load_input(run_record_path)
    result = build_result(payload)

    output_path = output_path_for(output_dir, run_record_path)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    metrics = result.get("credibility_metrics", {})
    retrieval_quality = result.get("retrieval_quality_metrics", {})
    observability = result.get("retrieval_observability", {})
    alignment = result.get("benchmark_alignment", {})
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
        "confidence_score": metrics.get("confidence_score"),
        "source_strength_score": metrics.get("source_strength_score"),
        "agreement_score": metrics.get("agreement_score"),
        "confidence_label": metrics.get("confidence_label"),
        "display_confidence_label": metrics.get("display_confidence_label"),
        "confidence_gate": metrics.get("confidence_gate", {}).get("status"),
        "freshness_capture_score": retrieval_quality.get("freshness_capture_score"),
        "shadow_signal_discipline_score": retrieval_quality.get("shadow_signal_discipline_score"),
        "source_promotion_discipline_score": retrieval_quality.get("source_promotion_discipline_score"),
        "blocked_source_handling_score": retrieval_quality.get("blocked_source_handling_score"),
        "blocked_source_count": observability.get("blocked_source_count"),
        "missing_expected_source_families": observability.get("missing_expected_source_families", []),
        "benchmark_checks_passed": alignment.get("checks_passed"),
        "benchmark_checks_available": alignment.get("checks_available"),
        "benchmark_fully_aligned": alignment.get("all_available_checks_passed"),
    }


def build_summary(input_dir: Path, output_dir: Path, evaluated_files: list[dict], failed_files: list[dict]) -> dict:
    keep_count = sum(1 for item in evaluated_files if item["keep"])
    rollback_count = len(evaluated_files) - keep_count
    freshness_scores = [item["freshness_capture_score"] for item in evaluated_files if isinstance(item.get("freshness_capture_score"), (int, float))]
    shadow_scores = [item["shadow_signal_discipline_score"] for item in evaluated_files if isinstance(item.get("shadow_signal_discipline_score"), (int, float))]
    promotion_scores = [item["source_promotion_discipline_score"] for item in evaluated_files if isinstance(item.get("source_promotion_discipline_score"), (int, float))]
    blocked_scores = [item["blocked_source_handling_score"] for item in evaluated_files if isinstance(item.get("blocked_source_handling_score"), (int, float))]
    blocked_counts = [item["blocked_source_count"] for item in evaluated_files if isinstance(item.get("blocked_source_count"), (int, float))]
    missing_family_runs = sum(1 for item in evaluated_files if item.get("missing_expected_source_families"))
    missing_families = sorted(
        {
            family
            for item in evaluated_files
            for family in item.get("missing_expected_source_families", [])
            if isinstance(family, str) and family.strip()
        }
    )
    return {
        "status": "OK" if not failed_files else "PARTIAL_ERROR",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_found": len(evaluated_files) + len(failed_files),
        "total_evaluated": len(evaluated_files),
        "total_failed": len(failed_files),
        "keep_count": keep_count,
        "rollback_count": rollback_count,
        "retrieval_quality_summary": {
            "avg_freshness_capture_score": round(sum(freshness_scores) / len(freshness_scores), 2) if freshness_scores else None,
            "avg_shadow_signal_discipline_score": round(sum(shadow_scores) / len(shadow_scores), 2) if shadow_scores else None,
            "avg_source_promotion_discipline_score": round(sum(promotion_scores) / len(promotion_scores), 2) if promotion_scores else None,
            "avg_blocked_source_handling_score": round(sum(blocked_scores) / len(blocked_scores), 2) if blocked_scores else None,
        },
        "retrieval_gap_summary": {
            "runs_with_blocked_sources": sum(1 for count in blocked_counts if count and count > 0),
            "avg_blocked_source_count": round(sum(blocked_counts) / len(blocked_counts), 2) if blocked_counts else None,
            "runs_with_missing_expected_source_families": missing_family_runs,
            "missing_expected_source_families_seen": missing_families,
        },
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
                failed_files.append({"input_file": str(run_record_path), "message": str(exc)})

        summary = build_summary(input_dir, output_dir, evaluated_files, failed_files)
        summary_path = output_dir / args.summary_name
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        if not args.quiet:
            print(json.dumps(summary, indent=2))
        sys.exit(0 if not failed_files else 1)
    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
