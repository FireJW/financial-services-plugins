#!/usr/bin/env python3
"""
Validate phase 1 information-index sample pool JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = [
    "item_id",
    "title",
    "topic",
    "analysis_date",
    "claim_to_evaluate",
    "baseline_goal",
    "required_output_sections",
    "source_pack",
    "credibility_reference",
    "rollback",
]

REQUIRED_SOURCE_PACK = [
    "event_label",
    "sources",
    "key_claims",
]

REQUIRED_ROLLBACK = [
    "stable_version",
    "rollback_rule",
]

VALID_SOURCE_STRENGTHS = {
    "high",
    "medium-high",
    "medium",
    "mixed",
    "low",
}

VALID_SOURCE_AGREEMENT = {
    "aligned",
    "mostly-aligned",
    "mixed",
    "conflicted",
}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "sample-pool" / "items"
    parser = argparse.ArgumentParser(
        description="Validate info-index sample pool JSON files and output a JSON summary."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing sample JSON files. Defaults to ../sample-pool/items",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save the validation summary JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write the requested file.",
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


def validate_iso_date(value: Any, field_name: str, errors: list[str]) -> None:
    if not is_nonempty_string(value):
        errors.append(f"{field_name} must be a non-empty ISO date string")
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field_name} must be in YYYY-MM-DD format")


def validate_sources(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("source_pack.sources must be a non-empty list")
        return

    for index, source in enumerate(value, start=1):
        prefix = f"source_pack.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["name", "url", "published_at", "support"]:
            if field not in source or not is_nonempty_string(source.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")
        source_type = source.get("type", source.get("source_type"))
        if not is_nonempty_string(source_type):
            errors.append(f"{prefix}.type or {prefix}.source_type must be a non-empty string")
        if "published_at" in source:
            validate_iso_date(source.get("published_at"), f"{prefix}.published_at", errors)


def validate_key_claims(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("source_pack.key_claims must be a non-empty list")
        return

    for index, claim in enumerate(value, start=1):
        prefix = f"source_pack.key_claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["claim", "status"]:
            if field not in claim or not is_nonempty_string(claim.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")


def validate_source_pack(payload: dict[str, Any], errors: list[str]) -> None:
    source_pack = payload.get("source_pack")
    if isinstance(source_pack, list):
        source_pack = {
            "event_label": payload.get("title", ""),
            "sources": source_pack,
            "key_claims": payload.get("key_claims", []),
        }
    if not isinstance(source_pack, dict):
        errors.append("source_pack must be an object or a list of source entries")
        return

    validate_required_keys(source_pack, REQUIRED_SOURCE_PACK, "source_pack.", errors)
    if "event_label" in source_pack and not is_nonempty_string(source_pack["event_label"]):
        errors.append("source_pack.event_label must be a non-empty string")
    validate_sources(source_pack.get("sources"), errors)
    validate_key_claims(source_pack.get("key_claims"), errors)


def validate_rollback(rollback: Any, errors: list[str]) -> None:
    if not isinstance(rollback, dict):
        errors.append("rollback must be an object")
        return

    validate_required_keys(rollback, REQUIRED_ROLLBACK, "rollback.", errors)
    for field in REQUIRED_ROLLBACK:
        if field in rollback and not is_nonempty_string(rollback[field]):
            errors.append(f"rollback.{field} must be a non-empty string")


def validate_credibility_reference(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("credibility_reference must be an object")
        return

    source_strength = value.get("source_strength")
    if not is_nonempty_string(source_strength):
        errors.append("credibility_reference.source_strength must be a non-empty string")
    elif str(source_strength).strip().lower() not in VALID_SOURCE_STRENGTHS:
        errors.append(
            "credibility_reference.source_strength must be one of: "
            + ", ".join(sorted(VALID_SOURCE_STRENGTHS))
        )

    source_agreement = value.get("source_agreement")
    if not is_nonempty_string(source_agreement):
        errors.append("credibility_reference.source_agreement must be a non-empty string")
    elif str(source_agreement).strip().lower() not in VALID_SOURCE_AGREEMENT:
        errors.append(
            "credibility_reference.source_agreement must be one of: "
            + ", ".join(sorted(VALID_SOURCE_AGREEMENT))
        )

    interval = value.get("confidence_interval_pct")
    if not isinstance(interval, list) or len(interval) != 2:
        errors.append("credibility_reference.confidence_interval_pct must be a two-number list")
    else:
        low, high = interval
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            errors.append("credibility_reference.confidence_interval_pct values must be numeric")
        else:
            if low < 0 or high > 100:
                errors.append("credibility_reference.confidence_interval_pct values must be between 0 and 100")
            if low > high:
                errors.append("credibility_reference.confidence_interval_pct low must be <= high")

    expected_judgment = value.get("expected_judgment")
    if not is_nonempty_string(expected_judgment):
        errors.append("credibility_reference.expected_judgment must be a non-empty string")


def validate_sample(path: Path) -> dict[str, Any]:
    errors: list[str] = []

    try:
        payload = load_json(path)
    except ValueError as exc:
        return {"file": path.name, "item_id": None, "valid": False, "errors": [str(exc)]}

    validate_required_keys(payload, REQUIRED_TOP_LEVEL, "", errors)

    for field in ["item_id", "title", "topic", "claim_to_evaluate", "baseline_goal"]:
        if field in payload and not is_nonempty_string(payload[field]):
            errors.append(f"{field} must be a non-empty string")

    if "required_output_sections" in payload and not is_nonempty_list_of_strings(payload["required_output_sections"]):
        errors.append("required_output_sections must be a non-empty list of strings")

    validate_iso_date(payload.get("analysis_date"), "analysis_date", errors)

    expected_item_id = path.stem
    item_id = payload.get("item_id")
    if is_nonempty_string(item_id) and item_id != expected_item_id:
        errors.append(f"item_id '{item_id}' does not match file name '{expected_item_id}'")

    validate_source_pack(payload, errors)
    validate_credibility_reference(payload.get("credibility_reference"), errors)
    validate_rollback(payload.get("rollback"), errors)

    return {"file": path.name, "item_id": item_id, "valid": len(errors) == 0, "errors": errors}


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
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)

    files = sorted(path for path in input_dir.glob("*.json") if path.name != "item-template.json")
    if not files:
        error = {"status": "ERROR", "message": f"No JSON files found in {input_dir}"}
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)

    results = [validate_sample(path) for path in files]
    summary = build_summary(results, input_dir)
    output = json.dumps(summary, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")

    if not args.quiet:
        print(output)
    sys.exit(0 if summary["all_valid"] else 1)


if __name__ == "__main__":
    main()
