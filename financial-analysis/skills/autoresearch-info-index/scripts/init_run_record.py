#!/usr/bin/env python3
"""
Create a phase 1 info-index run record from one sample-pool item definition.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCORE_FIELDS = [
    "source_coverage",
    "claim_traceability",
    "recency_discipline",
    "contradiction_handling",
    "signal_extraction",
    "retrieval_efficiency",
]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "sample-pool" / "items" / "news-001.json"

    parser = argparse.ArgumentParser(
        description="Create a run-record JSON scaffold from one phase 1 information-index sample."
    )
    parser.add_argument(
        "item_file",
        nargs="?",
        default=str(default_input),
        help="Path to one information-index sample JSON file",
    )
    parser.add_argument("--output", help="Optional path to save the generated run-record JSON")
    parser.add_argument("--sample-set-version", default="info-index-sample-v1", help="Sample set version")
    parser.add_argument("--baseline-version", default="baseline-v1", help="Baseline version label")
    parser.add_argument("--candidate-version", default="candidate-v2", help="Candidate version label")
    parser.add_argument("--last-stable-version", default="baseline-v1", help="Last stable version label")
    return parser.parse_args()


def load_item(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Sample item must be a JSON object")

    item_id = payload.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("Sample item must contain a non-empty item_id")

    return payload


def default_task_goal(item: dict[str, Any]) -> str:
    claim = str(item.get("claim_to_evaluate", "")).strip()
    goal = str(item.get("baseline_goal", "")).strip()
    if claim and goal:
        return f"Improve repeatable indexing of {claim}: {goal}"
    if claim:
        return f"Improve repeatable indexing of {claim}"
    return "Improve one repeatable information-index workflow"


def default_patterns(item: dict[str, Any]) -> tuple[str, str]:
    notes = item.get("notes", {})
    winner = ""
    loser = ""
    if isinstance(notes, dict):
        winner = str(notes.get("winner_pattern_hint", "")).strip()
        loser = str(notes.get("loser_pattern_hint", "")).strip()
    winner = winner or "State confirmed facts first, then unresolved points, then the credibility judgment."
    loser = loser or "Treating one unsupported headline as if it were already verified."
    return winner, loser


def normalize_source_entry(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    normalized = dict(source)
    if "type" not in normalized and "source_type" in normalized:
        normalized["type"] = normalized["source_type"]
    return normalized


def normalize_source_pack(item: dict[str, Any]) -> dict[str, Any]:
    source_pack = item.get("source_pack", {})
    if isinstance(source_pack, list):
        source_pack = {
            "event_label": item.get("title", ""),
            "sources": source_pack,
            "key_claims": item.get("key_claims", []),
        }
    if not isinstance(source_pack, dict):
        source_pack = {}

    sources = source_pack.get("sources", [])
    if not isinstance(sources, list):
        sources = []

    key_claims = source_pack.get("key_claims", item.get("key_claims", []))
    if not isinstance(key_claims, list):
        key_claims = []

    return {
        "analysis_date": item.get("analysis_date", ""),
        "event_label": source_pack.get("event_label", item.get("title", "")),
        "sources": [normalize_source_entry(source) for source in sources if isinstance(source, dict)],
        "key_claims": key_claims,
    }


def normalize_credibility_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    interval = value.get("confidence_interval_pct", [])
    if isinstance(interval, tuple):
        interval = list(interval)
    if not isinstance(interval, list):
        interval = []

    return {
        "source_strength": value.get("source_strength", ""),
        "source_agreement": value.get("source_agreement", ""),
        "confidence_interval_pct": interval,
        "expected_judgment": value.get("expected_judgment", ""),
    }


def sanitize_version(label: str, fallback: str) -> str:
    clean = re.sub(r"\s+", "-", label.strip())
    return clean or fallback


def zero_scores() -> dict[str, int]:
    return {field: 0 for field in SCORE_FIELDS}


def build_run_record(item: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    winner_pattern, loser_pattern = default_patterns(item)
    source_pack = normalize_source_pack(item)
    credibility_reference = normalize_credibility_reference(item.get("credibility_reference"))

    return {
        "task_id": item["item_id"],
        "analysis_date": item.get("analysis_date", ""),
        "sample_set_version": args.sample_set_version,
        "task_goal": default_task_goal(item),
        "baseline_version": sanitize_version(args.baseline_version, "baseline-v1"),
        "candidate_version": sanitize_version(args.candidate_version, "candidate-v2"),
        "last_stable_version": sanitize_version(args.last_stable_version, "baseline-v1"),
        "hard_checks": {
            "anchored_to_absolute_dates": False,
            "key_claims_traceable": False,
            "fact_and_inference_separated": False,
            "conflicting_signals_disclosed": False,
            "source_recency_checked": False
        },
        "baseline_scores": zero_scores(),
        "candidate_scores": zero_scores(),
        "thresholds": {
            "min_improvement": 2,
            "large_regression": 5
        },
        "history": {
            "consecutive_small_gain_rounds": 0,
            "consecutive_stale_source_rounds": 0,
            "recent_success_rate": 0.0,
            "target_success_rate": 0.8
        },
        "winner_pattern": winner_pattern,
        "loser_pattern": loser_pattern,
        "credibility_reference": credibility_reference,
        "source_pack": {
            "analysis_date": source_pack.get("analysis_date", ""),
            "event_label": source_pack.get("event_label", ""),
            "sources": source_pack.get("sources", []),
            "key_claims": source_pack.get("key_claims", [])
        },
        "source_item": {
            "item_file": item.get("_source_file", ""),
            "title": item.get("title", ""),
            "topic": item.get("topic", ""),
            "claim_to_evaluate": item.get("claim_to_evaluate", ""),
            "baseline_goal": item.get("baseline_goal", ""),
            "required_output_sections": item.get("required_output_sections", []),
            "credibility_reference": credibility_reference,
            "rollback": item.get("rollback", {})
        }
    }


def default_output_path(item_file: Path) -> Path:
    return item_file.with_name(f"{item_file.stem}-run-record.json")


def main() -> None:
    args = parse_args()
    item_file = Path(args.item_file).resolve()

    try:
        item = load_item(item_file)
        item["_source_file"] = str(item_file)
        run_record = build_run_record(item, args)
        output = json.dumps(run_record, indent=2)

        if args.output:
            output_path = Path(args.output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
        else:
            output_path = default_output_path(item_file)
            output_path.write_text(output, encoding="utf-8")

        print(output)
        sys.exit(0)
    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(error, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
