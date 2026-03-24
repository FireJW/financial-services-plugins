#!/usr/bin/env python3
"""
Validate phase 1 code-fix sample pool JSON files.

This script is intentionally zero-dependency. It checks that bug sample files
contain the minimum fields needed for reproduce/verify/rollback workflows and
returns a JSON summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = [
    "bug_id",
    "title",
    "priority",
    "module_boundary",
    "bug_description",
    "expected_behavior",
    "actual_behavior",
    "reproduction",
    "validation",
    "rollback",
]

REQUIRED_REPRODUCTION = [
    "steps",
    "expected_behavior",
    "actual_behavior",
]

REQUIRED_VALIDATION = [
    "primary_command",
]

REQUIRED_ROLLBACK = [
    "stable_version",
    "rollback_rule",
]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "sample-pool" / "bugs"
    parser = argparse.ArgumentParser(
        description="Validate code-fix sample pool JSON files and output a JSON summary."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing bug sample JSON files. Defaults to ../sample-pool/bugs",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save the validation summary JSON",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON value must be an object")
    return payload


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def is_nonempty_list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(is_nonempty_string(item) for item in value)


def validate_required_keys(payload: dict[str, Any], keys: list[str], prefix: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"Missing required field: {prefix}{key}")


def validate_module_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("module_boundary must be an object")
        return

    allowed = boundary.get("allowed_paths")
    forbidden = boundary.get("forbidden_paths")

    if not is_nonempty_list_of_strings(allowed):
        errors.append("module_boundary.allowed_paths must be a non-empty list of strings")
    if not is_nonempty_list_of_strings(forbidden):
        errors.append("module_boundary.forbidden_paths must be a non-empty list of strings")


def validate_reproduction(reproduction: Any, errors: list[str]) -> None:
    if not isinstance(reproduction, dict):
        errors.append("reproduction must be an object")
        return

    validate_required_keys(reproduction, REQUIRED_REPRODUCTION, "reproduction.", errors)

    if "steps" in reproduction and not is_nonempty_list_of_strings(reproduction["steps"]):
        errors.append("reproduction.steps must be a non-empty list of strings")
    if "expected_behavior" in reproduction and not is_nonempty_string(reproduction["expected_behavior"]):
        errors.append("reproduction.expected_behavior must be a non-empty string")
    if "actual_behavior" in reproduction and not is_nonempty_string(reproduction["actual_behavior"]):
        errors.append("reproduction.actual_behavior must be a non-empty string")


def validate_validation(validation: Any, errors: list[str]) -> None:
    if not isinstance(validation, dict):
        errors.append("validation must be an object")
        return

    validate_required_keys(validation, REQUIRED_VALIDATION, "validation.", errors)

    if "primary_command" in validation and not is_nonempty_string(validation["primary_command"]):
        errors.append("validation.primary_command must be a non-empty string")

    secondary = validation.get("secondary_checks", [])
    manual = validation.get("manual_checks", [])
    if secondary and not all(is_nonempty_string(item) for item in secondary):
        errors.append("validation.secondary_checks must contain only non-empty strings")
    if manual and not all(is_nonempty_string(item) for item in manual):
        errors.append("validation.manual_checks must contain only non-empty strings")


def validate_rollback(rollback: Any, errors: list[str]) -> None:
    if not isinstance(rollback, dict):
        errors.append("rollback must be an object")
        return

    validate_required_keys(rollback, REQUIRED_ROLLBACK, "rollback.", errors)

    if "stable_version" in rollback and not is_nonempty_string(rollback["stable_version"]):
        errors.append("rollback.stable_version must be a non-empty string")
    if "rollback_rule" in rollback and not is_nonempty_string(rollback["rollback_rule"]):
        errors.append("rollback.rollback_rule must be a non-empty string")


def validate_sample(path: Path) -> dict[str, Any]:
    errors: list[str] = []

    try:
        payload = load_json(path)
    except ValueError as exc:
        return {
            "file": path.name,
            "bug_id": None,
            "valid": False,
            "errors": [str(exc)],
        }

    validate_required_keys(payload, REQUIRED_TOP_LEVEL, "", errors)

    for field in ["bug_id", "title", "priority", "bug_description", "expected_behavior", "actual_behavior"]:
        if field in payload and not is_nonempty_string(payload[field]):
            errors.append(f"{field} must be a non-empty string")

    expected_bug_id = path.stem
    bug_id = payload.get("bug_id")
    if is_nonempty_string(bug_id) and bug_id != expected_bug_id:
        errors.append(f"bug_id '{bug_id}' does not match file name '{expected_bug_id}'")

    validate_module_boundary(payload.get("module_boundary"), errors)
    validate_reproduction(payload.get("reproduction"), errors)
    validate_validation(payload.get("validation"), errors)
    validate_rollback(payload.get("rollback"), errors)

    return {
        "file": path.name,
        "bug_id": bug_id,
        "valid": len(errors) == 0,
        "errors": errors,
    }


def build_summary(results: list[dict[str, Any]], input_dir: Path) -> dict[str, Any]:
    valid_count = sum(1 for item in results if item["valid"])
    invalid_count = len(results) - valid_count

    return {
        "input_dir": str(input_dir),
        "total_files": len(results),
        "valid_files": valid_count,
        "invalid_files": invalid_count,
        "all_valid": invalid_count == 0,
        "results": results,
    }


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()

    if not input_dir.exists():
        error = {"status": "ERROR", "message": f"Input directory not found: {input_dir}"}
        print(json.dumps(error, indent=2))
        sys.exit(1)

    files = sorted(
        path
        for path in input_dir.glob("*.json")
        if path.name != "bug-template.json"
    )
    if not files:
        error = {"status": "ERROR", "message": f"No JSON files found in {input_dir}"}
        print(json.dumps(error, indent=2))
        sys.exit(1)

    results = [validate_sample(path) for path in files]
    summary = build_summary(results, input_dir)
    output = json.dumps(summary, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")

    print(output)
    sys.exit(0 if summary["all_valid"] else 1)


if __name__ == "__main__":
    main()
