#!/usr/bin/env python3
"""
Evaluate a code-fix autoresearch run record.

This script is intentionally small and explicit. It scores a single run record,
checks hard gates, and returns a keep-or-rollback decision for phase 1 of the
autoresearch loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


HARD_CHECKS = [
    ("issue_reproduced_before", "Issue was not reproducible before the fix"),
    ("fix_verified_after", "Fix was not verified after the change"),
    ("no_new_critical_failures", "New critical failure was introduced"),
    ("scope_controlled", "Change scope exceeded the allowed boundary"),
    ("root_cause_aligned", "Fix does not match the stated root cause"),
]

SCORE_MAX = {
    "root_cause_quality": 25,
    "fix_minimality": 20,
    "verification_completeness": 20,
    "regression_risk_control": 15,
    "debugging_efficiency": 10,
    "reuse_value": 10,
}

REQUIRED_FIELDS = [
    "task_id",
    "sample_set_version",
    "task_goal",
    "baseline_version",
    "candidate_version",
    "last_stable_version",
    "hard_checks",
    "baseline_scores",
    "candidate_scores",
]


def load_input(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def require_fields(payload: dict) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def validate_score_block(name: str, scores: dict) -> None:
    missing = [key for key in SCORE_MAX if key not in scores]
    if missing:
        raise ValueError(f"{name} is missing score fields: {', '.join(missing)}")

    extra = [key for key in scores if key not in SCORE_MAX]
    if extra:
        raise ValueError(f"{name} contains unsupported score fields: {', '.join(extra)}")

    for key, maximum in SCORE_MAX.items():
        value = scores[key]
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name}.{key} must be numeric")
        if value < 0 or value > maximum:
            raise ValueError(f"{name}.{key} must be between 0 and {maximum}")


def total_score(scores: dict) -> int:
    return int(round(sum(scores.values())))


def evaluate_hard_checks(hard_checks: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []

    for key, message in HARD_CHECKS:
        if key not in hard_checks:
            failures.append(f"Missing hard check: {key}")
            continue
        if not isinstance(hard_checks[key], bool):
            failures.append(f"Hard check {key} must be true or false")
            continue
        if not hard_checks[key]:
            failures.append(message)

    return (len(failures) == 0, failures)


def evaluate_stop_signal(payload: dict, candidate_total: int, baseline_total: int) -> dict:
    history = payload.get("history", {})
    min_improvement = payload.get("thresholds", {}).get("min_improvement", 2)
    target_success_rate = history.get("target_success_rate", 0.8)
    recent_success_rate = history.get("recent_success_rate")
    small_gain_rounds = history.get("consecutive_small_gain_rounds", 0)
    non_verifying_rounds = history.get("consecutive_non_verifying_rounds", 0)

    delta = candidate_total - baseline_total

    if small_gain_rounds >= 3 and delta < min_improvement:
        return {"reached": True, "reason": "Three consecutive low-gain rounds reached the stop threshold"}
    if non_verifying_rounds >= 2:
        return {"reached": True, "reason": "Two consecutive rounds failed to improve verification quality"}
    if recent_success_rate is not None and recent_success_rate >= target_success_rate:
        return {"reached": True, "reason": "Recent success rate reached the target threshold"}

    return {"reached": False, "reason": "No stop condition reached"}


def build_result(payload: dict) -> dict:
    require_fields(payload)
    validate_score_block("baseline_scores", payload["baseline_scores"])
    validate_score_block("candidate_scores", payload["candidate_scores"])

    hard_passed, failures = evaluate_hard_checks(payload["hard_checks"])

    baseline_total = total_score(payload["baseline_scores"])
    candidate_total = total_score(payload["candidate_scores"])
    delta = candidate_total - baseline_total

    thresholds = payload.get("thresholds", {})
    min_improvement = thresholds.get("min_improvement", 2)
    large_regression = thresholds.get("large_regression", 5)
    severe_new_issue = bool(payload.get("severe_new_issue", False))

    dimension_rows = []
    for key, maximum in SCORE_MAX.items():
        baseline_value = payload["baseline_scores"][key]
        candidate_value = payload["candidate_scores"][key]
        dimension_rows.append(
            {
                "name": key,
                "score": candidate_value,
                "weight": maximum,
                "baseline": baseline_value,
                "delta": candidate_value - baseline_value,
            }
        )

    keep = hard_passed and not severe_new_issue and delta >= min_improvement

    if not hard_passed:
        reason = "Rollback because one or more hard checks failed"
    elif severe_new_issue:
        reason = "Rollback because a new severe issue was introduced"
    elif delta < min_improvement:
        reason = f"Rollback because score improved by {delta}, below the {min_improvement}-point threshold"
    else:
        reason = f"Keep because hard checks passed and score improved by {delta}"

    concerns = []
    if delta <= -large_regression:
        concerns.append(f"Large regression detected: score dropped by {abs(delta)} points")
    if severe_new_issue:
        concerns.append("A severe new issue was flagged in the input")

    return {
        "profile": "code-fix",
        "task_id": payload["task_id"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "sample_set_version": payload["sample_set_version"],
        "task_goal": payload["task_goal"],
        "baseline_version": payload["baseline_version"],
        "candidate_version": payload["candidate_version"],
        "hard_checks": {
            "passed": hard_passed,
            "failures": failures,
        },
        "soft_scores": {
            "baseline_total": baseline_total,
            "candidate_total": candidate_total,
            "total": candidate_total,
            "delta": delta,
            "dimensions": dimension_rows,
        },
        "decision": {
            "keep": keep,
            "rollback_to": "" if keep else payload["last_stable_version"],
            "reason": reason,
            "concerns": concerns,
        },
        "stop_signal": evaluate_stop_signal(payload, candidate_total, baseline_total),
        "notes": {
            "winner_pattern": payload.get("winner_pattern", ""),
            "loser_pattern": payload.get("loser_pattern", ""),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a code-fix autoresearch run record and return a keep-or-rollback decision."
    )
    parser.add_argument("input", help="Path to a JSON run record")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        payload = load_input(Path(args.input))
        result = build_result(payload)
        print(json.dumps(result, indent=2))

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        sys.exit(0 if result["decision"]["keep"] else 2)
    except Exception as exc:  # pragma: no cover - command-line safety path
        error = {
            "status": "ERROR",
            "message": str(exc),
        }
        print(json.dumps(error, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
