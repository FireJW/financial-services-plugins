#!/usr/bin/env python3
"""
Create a phase 1 code-fix run record from one sample-pool bug definition.

This script is intentionally zero-dependency. It converts a bug sample into a
run-record JSON scaffold that is directly compatible with evaluate_code_fix.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCORE_FIELDS = [
    "root_cause_quality",
    "fix_minimality",
    "verification_completeness",
    "regression_risk_control",
    "debugging_efficiency",
    "reuse_value",
]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "sample-pool" / "bugs" / "bug-001.json"

    parser = argparse.ArgumentParser(
        description="Create a run-record JSON scaffold from one phase 1 bug sample."
    )
    parser.add_argument(
        "bug_file",
        nargs="?",
        default=str(default_input),
        help="Path to one bug sample JSON file",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save the generated run-record JSON",
    )
    parser.add_argument(
        "--sample-set-version",
        default="code-fix-sample-v1",
        help="Sample set version to write into the run record",
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


def load_bug(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Bug sample must be a JSON object")

    bug_id = payload.get("bug_id")
    if not isinstance(bug_id, str) or not bug_id.strip():
        raise ValueError("Bug sample must contain a non-empty bug_id")

    return payload


def default_task_goal(bug: dict[str, Any]) -> str:
    title = str(bug.get("title", "")).strip()
    description = str(bug.get("bug_description", "")).strip()
    if title and description:
        return f"Improve repeatable handling of {title.lower()}: {description}"
    if title:
        return f"Improve repeatable handling of {title.lower()}"
    return "Improve one repeatable code-fix workflow"


def default_patterns(bug: dict[str, Any]) -> tuple[str, str]:
    notes = bug.get("notes", {})
    root_cause_hint = ""
    risk_hint = ""
    if isinstance(notes, dict):
        root_cause_hint = str(notes.get("root_cause_hint", "")).strip()
        risk_hint = str(notes.get("risk_hint", "")).strip()

    winner = root_cause_hint or "State the true trigger clearly before changing code"
    loser = risk_hint or "Broad or weakly verified fixes should lose to narrower verified fixes"
    return winner, loser


def sanitize_version(label: str, fallback: str) -> str:
    clean = re.sub(r"\s+", "-", label.strip())
    return clean or fallback


def zero_scores() -> dict[str, int]:
    return {field: 0 for field in SCORE_FIELDS}


def build_run_record(bug: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    winner_pattern, loser_pattern = default_patterns(bug)

    return {
        "task_id": bug["bug_id"],
        "sample_set_version": args.sample_set_version,
        "task_goal": default_task_goal(bug),
        "baseline_version": sanitize_version(args.baseline_version, "baseline-v1"),
        "candidate_version": sanitize_version(args.candidate_version, "candidate-v2"),
        "last_stable_version": sanitize_version(args.last_stable_version, "baseline-v1"),
        "hard_checks": {
            "issue_reproduced_before": False,
            "fix_verified_after": False,
            "no_new_critical_failures": False,
            "scope_controlled": False,
            "root_cause_aligned": False,
        },
        "baseline_scores": zero_scores(),
        "candidate_scores": zero_scores(),
        "thresholds": {
            "min_improvement": 2,
            "large_regression": 5,
        },
        "history": {
            "consecutive_small_gain_rounds": 0,
            "consecutive_non_verifying_rounds": 0,
            "recent_success_rate": 0.0,
            "target_success_rate": 0.8,
        },
        "winner_pattern": winner_pattern,
        "loser_pattern": loser_pattern,
        "source_bug": {
            "bug_file": bug.get("_source_file", ""),
            "title": bug.get("title", ""),
            "priority": bug.get("priority", ""),
            "module_boundary": bug.get("module_boundary", {}),
            "reproduction": bug.get("reproduction", {}),
            "validation": bug.get("validation", {}),
            "rollback": bug.get("rollback", {}),
            "scope_notes": bug.get("scope_notes", ""),
            "tags": bug.get("tags", []),
        },
    }


def default_output_path(bug_file: Path) -> Path:
    return bug_file.with_name(f"{bug_file.stem}-run-record.json")


def main() -> None:
    args = parse_args()
    bug_file = Path(args.bug_file).resolve()

    try:
        bug = load_bug(bug_file)
        bug["_source_file"] = str(bug_file)
        run_record = build_run_record(bug, args)
        output = json.dumps(run_record, indent=2)

        if args.output:
            output_path = Path(args.output).resolve()
            output_path.write_text(output, encoding="utf-8")
        else:
            output_path = default_output_path(bug_file)
            output_path.write_text(output, encoding="utf-8")

        print(output)
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
