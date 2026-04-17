#!/usr/bin/env python3
"""
Create a phase 1 info-index run-record scaffold from a single benchmark item.

A benchmark item (from the sample-pool) describes a news event, its sources,
key claims, and a credibility reference.  This script transforms that item into
the run-record shape expected by ``evaluate_info_index.py``.

Exported API used by ``init_all_run_records.py``:
    load_item(path)              -> dict
    build_run_record(item, args) -> dict
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


SCORE_MAX = {
    "source_coverage": 25,
    "claim_traceability": 20,
    "recency_discipline": 20,
    "contradiction_handling": 15,
    "signal_extraction": 10,
    "retrieval_efficiency": 10,
}

HARD_CHECK_KEYS = [
    "anchored_to_absolute_dates",
    "key_claims_traceable",
    "fact_and_inference_separated",
    "conflicting_signals_disclosed",
    "source_recency_checked",
]

SOURCE_TYPE_WEIGHTS: dict[str, int] = {
    "official": 95,
    "official_statement": 95,
    "regulator_filing": 95,
    "company_filing": 95,
    "exchange_filing": 95,
    "government_release": 90,
    "government": 90,
    "official_release": 90,
    "official_calendar": 88,
    "wire": 85,
    "major_news": 78,
    "news": 70,
    "public_ais": 60,
    "public_ship_tracker": 60,
    "company_source": 68,
    "analysis": 60,
    "research_note": 60,
    "industry_blog": 45,
    "social": 35,
    "market_rumor": 20,
    "rumor": 20,
    "unknown": 50,
}

CLAIM_STATUS_SCORES: dict[str, int] = {
    "confirmed": 90,
    "confirmed_officially": 100,
    "confirmed_directly": 95,
    "confirmed_by_reporting": 75,
    "analytical_judgment": 50,
    "inferred": 45,
    "denied": 15,
    "not_confirmed": 35,
    "unclear": 30,
    "contradicted": 10,
}


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def load_item(path: Path | str) -> dict[str, Any]:
    """Load a sample-pool item JSON file and return its contents as a dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Item file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _strength_factor(credibility_reference: dict[str, Any]) -> float:
    """Map source_strength label to a numeric factor."""
    source_strength = str(credibility_reference.get("source_strength", "medium")).strip().lower()
    return {
        "high": 0.85,
        "medium-high": 0.75,
        "medium": 0.60,
        "mixed": 0.45,
        "low": 0.30,
    }.get(source_strength, 0.60)


def _agreement_factor(credibility_reference: dict[str, Any]) -> float:
    """Map source_agreement label to a numeric factor."""
    source_agreement = str(credibility_reference.get("source_agreement", "mixed")).strip().lower()
    return {
        "aligned": 0.90,
        "mostly-aligned": 0.75,
        "mixed": 0.55,
        "conflicted": 0.35,
    }.get(source_agreement, 0.55)


def _derive_baseline_scores(
    source_pack: dict[str, Any],
    credibility_reference: dict[str, Any],
) -> dict[str, int]:
    """Derive synthetic baseline scores from the item's source pack and credibility reference."""
    sources = source_pack.get("sources", [])
    key_claims = source_pack.get("key_claims", [])

    source_count = len(sources) if isinstance(sources, list) else 0
    claim_count = len(key_claims) if isinstance(key_claims, list) else 0

    sf = _strength_factor(credibility_reference)
    af = _agreement_factor(credibility_reference)

    source_coverage = clamp(min(25, source_count * 5) * sf, 0, 25)
    claim_traceability = clamp(min(20, claim_count * 4) * af, 0, 20)
    recency_discipline = clamp(12 * sf, 0, 20)
    contradiction_handling = clamp(9 * af, 0, 15)
    signal_extraction = clamp(6 * sf, 0, 10)
    retrieval_efficiency = clamp(6 * sf, 0, 10)

    return {
        "source_coverage": int(round(source_coverage)),
        "claim_traceability": int(round(claim_traceability)),
        "recency_discipline": int(round(recency_discipline)),
        "contradiction_handling": int(round(contradiction_handling)),
        "signal_extraction": int(round(signal_extraction)),
        "retrieval_efficiency": int(round(retrieval_efficiency)),
    }


def _derive_candidate_scores(baseline_scores: dict[str, int]) -> dict[str, int]:
    """Derive synthetic candidate scores as a modest improvement over baseline."""
    candidate: dict[str, int] = {}
    for key, maximum in SCORE_MAX.items():
        base = baseline_scores.get(key, 0)
        candidate[key] = min(maximum, base + max(1, int(round(base * 0.15))))
    return candidate


def _derive_hard_checks(source_pack: dict[str, Any]) -> dict[str, bool]:
    """Derive initial hard-check values from the item's source pack."""
    sources = source_pack.get("sources", [])
    key_claims = source_pack.get("key_claims", [])

    has_dates = all(
        isinstance(s, dict) and s.get("published_at")
        for s in (sources if isinstance(sources, list) else [])
    )
    has_traceable_claims = all(
        isinstance(c, dict) and c.get("status") and c.get("status") != "unclear"
        for c in (key_claims if isinstance(key_claims, list) else [])
    )
    has_status_variety = len({
        c.get("status")
        for c in (key_claims if isinstance(key_claims, list) else [])
        if isinstance(c, dict)
    }) > 1

    return {
        "anchored_to_absolute_dates": has_dates,
        "key_claims_traceable": has_traceable_claims,
        "fact_and_inference_separated": True,
        "conflicting_signals_disclosed": has_status_variety or len(key_claims) <= 1,
        "source_recency_checked": has_dates,
    }


def build_run_record(item: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """
    Transform a benchmark item into a run-record scaffold.

    Parameters
    ----------
    item : dict
        A sample-pool item dict with keys like ``item_id``, ``title``, ``topic``,
        ``source_pack``, ``credibility_reference``, ``rollback``, ``notes``, etc.
    args : argparse.Namespace
        CLI arguments with at least ``sample_set_version``, ``baseline_version``,
        ``candidate_version``, and ``last_stable_version``.

    Returns
    -------
    dict
        A run-record dict matching the shape expected by ``evaluate_info_index.build_result()``.
    """
    item_id = item.get("item_id", "unknown")
    title = item.get("title", "")
    topic = item.get("topic", "")
    analysis_date = item.get("analysis_date", "")
    claim_to_evaluate = item.get("claim_to_evaluate", "")

    source_pack = item.get("source_pack", {})
    if not isinstance(source_pack, dict):
        source_pack = {}

    credibility_reference = item.get("credibility_reference", {})
    if not isinstance(credibility_reference, dict):
        credibility_reference = {}

    rollback = item.get("rollback", {})
    if not isinstance(rollback, dict):
        rollback = {}

    notes = item.get("notes", {})
    if not isinstance(notes, dict):
        notes = {}

    baseline_scores = _derive_baseline_scores(source_pack, credibility_reference)
    candidate_scores = _derive_candidate_scores(baseline_scores)
    hard_checks = _derive_hard_checks(source_pack)

    sample_set_version = getattr(args, "sample_set_version", "info-index-sample-v1")
    baseline_version = getattr(args, "baseline_version", "baseline-v1")
    candidate_version = getattr(args, "candidate_version", "candidate-v2")
    last_stable_version = getattr(args, "last_stable_version", "baseline-v1")

    return {
        "task_id": item_id,
        "title": title,
        "topic": topic,
        "analysis_date": analysis_date,
        "claim_to_evaluate": claim_to_evaluate,
        "sample_set_version": sample_set_version,
        "task_goal": (
            f"Evaluate whether the info-index correctly handles: {claim_to_evaluate}"
            if claim_to_evaluate
            else f"Evaluate info-index coverage for {topic}"
        ),
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "last_stable_version": last_stable_version,
        "hard_checks": hard_checks,
        "baseline_scores": baseline_scores,
        "candidate_scores": candidate_scores,
        "thresholds": {
            "min_improvement": 2,
            "large_regression": 5,
        },
        "history": {
            "consecutive_small_gain_rounds": 0,
            "consecutive_stale_source_rounds": 0,
            "recent_success_rate": 0.0,
            "target_success_rate": 0.8,
        },
        "winner_pattern": notes.get("winner_pattern_hint", ""),
        "loser_pattern": notes.get("loser_pattern_hint", ""),
        "source_pack": source_pack,
        "credibility_reference": credibility_reference,
        "rollback": rollback,
        "source_item": {
            "item_id": item_id,
            "title": title,
            "topic": topic,
            "analysis_date": analysis_date,
            "claim_to_evaluate": claim_to_evaluate,
            "credibility_reference": credibility_reference,
        },
    }


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "sample-pool" / "items" / "news-001.json"
    parser = argparse.ArgumentParser(
        description="Create a run-record scaffold from a single benchmark item."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(default_input),
        help="Path to a sample-pool item JSON file",
    )
    parser.add_argument("--output", help="Optional path to save the run-record JSON")
    parser.add_argument("--sample-set-version", default="info-index-sample-v1")
    parser.add_argument("--baseline-version", default="baseline-v1")
    parser.add_argument("--candidate-version", default="candidate-v2")
    parser.add_argument("--last-stable-version", default="baseline-v1")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write the requested file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        item = load_item(Path(args.input).resolve())
        run_record = build_run_record(item, args)
        if not args.quiet:
            print(json.dumps(run_record, indent=2, ensure_ascii=False))
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(run_record, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        sys.exit(0)
    except Exception as exc:
        error = {"status": "ERROR", "message": str(exc)}
        print(json.dumps(error, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
