#!/usr/bin/env python3
"""
Bridge a news-index retrieval result into the existing info-index run-record shape.
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

from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, write_json


SCORE_MAX = {
    "source_coverage": 25,
    "claim_traceability": 20,
    "recency_discipline": 20,
    "contradiction_handling": 15,
    "signal_extraction": 10,
    "retrieval_efficiency": 10,
}


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_DIR.parent / "examples" / "news-index-crisis-result.json"
    parser = argparse.ArgumentParser(
        description="Convert a news-index result JSON into an info-index run-record scaffold."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(default_input),
        help="Path to a news-index result JSON file",
    )
    parser.add_argument("--output", help="Optional path to save the run-record JSON")
    parser.add_argument("--task-id", help="Optional task id override")
    parser.add_argument("--sample-set-version", default="info-index-news-index-v1")
    parser.add_argument("--baseline-version", default="baseline-v1")
    parser.add_argument("--candidate-version", default="candidate-news-index-v1")
    parser.add_argument("--last-stable-version", default="baseline-v1")
    parser.add_argument("--baseline-factor", type=float, default=0.6)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write the requested file.",
    )
    return parser.parse_args()


def clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def derive_candidate_scores(result: dict[str, Any]) -> dict[str, int]:
    observations = result.get("observations", [])
    claim_ledger = result.get("claim_ledger", [])
    verdict = result.get("verdict_output", {})
    quality = result.get("retrieval_quality", {})

    core_sources = [item for item in observations if item.get("channel") == "core" and item.get("access_mode") != "blocked"]
    shadow_sources = [item for item in observations if item.get("channel") == "shadow"]
    traceable_claims = sum(
        1
        for item in claim_ledger
        if item.get("supporting_sources") or item.get("contradicting_sources")
    )
    total_claims = max(len(claim_ledger), 1)
    conflict_matrix = verdict.get("conflict_matrix", [])

    return {
        "source_coverage": clamp(min(25.0, len(core_sources) * 5 + len(shadow_sources) * 1.5), 0, 25),
        "claim_traceability": clamp((traceable_claims / total_claims) * 20, 0, 20),
        "recency_discipline": clamp((quality.get("freshness_capture_score", 0) / 100.0) * 20, 0, 20),
        "contradiction_handling": clamp(min(15.0, len(conflict_matrix) * 3 + len(verdict.get("missing_confirmations", [])) * 1.5), 0, 15),
        "signal_extraction": clamp(10.0 if verdict.get("core_verdict") and verdict.get("latest_signals") else 5.0, 0, 10),
        "retrieval_efficiency": clamp(
            (quality.get("blocked_source_handling_score", 0) / 100.0) * 5
            + (quality.get("source_promotion_discipline_score", 0) / 100.0) * 5,
            0,
            10,
        ),
    }


def derive_baseline_scores(candidate_scores: dict[str, int], factor: float) -> dict[str, int]:
    baseline_scores: dict[str, int] = {}
    for key, maximum in SCORE_MAX.items():
        baseline_scores[key] = clamp(candidate_scores[key] * factor, 0, maximum)
    return baseline_scores


def build_hard_checks(result: dict[str, Any]) -> dict[str, bool]:
    request = result.get("request", {})
    observations = result.get("observations", [])
    verdict = result.get("verdict_output", {})
    claim_ledger = result.get("claim_ledger", [])

    all_absolute = bool(request.get("analysis_time")) and all(
        observation.get("published_at") or observation.get("observed_at")
        for observation in observations
    )
    traceable = all(
        item.get("supporting_sources") or item.get("contradicting_sources") or item.get("status") == "inferred"
        for item in claim_ledger
    )
    separated = bool(verdict.get("confirmed")) or bool(verdict.get("not_confirmed")) or bool(verdict.get("inference_only"))
    recency_checked = bool(verdict.get("freshness_panel"))
    conflicts_disclosed = bool(verdict.get("conflict_matrix"))

    return {
        "anchored_to_absolute_dates": all_absolute,
        "key_claims_traceable": traceable,
        "fact_and_inference_separated": separated,
        "conflicting_signals_disclosed": conflicts_disclosed,
        "source_recency_checked": recency_checked,
    }


def build_source_pack(result: dict[str, Any]) -> dict[str, Any]:
    request = result.get("request", {})
    observations = result.get("observations", [])
    claim_ledger = result.get("claim_ledger", [])
    analysis_dt = parse_datetime(request.get("analysis_time"))
    sources: list[dict[str, Any]] = []
    for item in observations:
        published_at = parse_datetime(item.get("published_at"))
        observed_at = parse_datetime(item.get("observed_at"))
        anchor = published_at or observed_at
        sources.append(
            {
                "source_id": item.get("source_id", ""),
                "name": item.get("source_name", ""),
                "type": item.get("source_type", ""),
                "origin": item.get("origin", ""),
                "url": item.get("url", ""),
                "published_at": isoformat_or_blank(anchor),
                "observed_at": isoformat_or_blank(observed_at),
                "published_date": anchor.date().isoformat() if anchor else "",
                "support": item.get("text_excerpt", ""),
                "channel": item.get("channel", ""),
                "source_tier": item.get("source_tier", 3),
                "access_mode": item.get("access_mode", ""),
                "artifact_manifest": item.get("artifact_manifest", []),
                "post_text_raw": item.get("post_text_raw", ""),
                "media_summary": item.get("media_summary", ""),
                "root_post_screenshot_path": item.get("root_post_screenshot_path", ""),
            }
        )
    return {
        "analysis_date": analysis_dt.date().isoformat() if analysis_dt else "",
        "event_label": request.get("topic", ""),
        "sources": sources,
        "key_claims": [
            {
                "claim": item.get("claim_text", ""),
                "status": item.get("status", ""),
                "promotion_state": item.get("promotion_state", ""),
            }
            for item in claim_ledger
        ],
    }


def build_run_record(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    request = result.get("request", {})
    candidate_scores = derive_candidate_scores(result)
    baseline_scores = derive_baseline_scores(candidate_scores, args.baseline_factor)
    topic = request.get("topic", "news-index-topic")
    task_id = args.task_id or topic.lower().replace(" ", "-")

    return {
        "task_id": task_id,
        "analysis_date": (parse_datetime(request.get("analysis_time")) or parse_datetime("")).date().isoformat()
        if parse_datetime(request.get("analysis_time"))
        else "",
        "sample_set_version": args.sample_set_version,
        "task_goal": f"Improve repeatable indexing of {topic}",
        "baseline_version": args.baseline_version,
        "candidate_version": args.candidate_version,
        "last_stable_version": args.last_stable_version,
        "hard_checks": build_hard_checks(result),
        "baseline_scores": baseline_scores,
        "candidate_scores": candidate_scores,
        "thresholds": {"min_improvement": 2, "large_regression": 5},
        "history": {
            "consecutive_small_gain_rounds": 0,
            "consecutive_stale_source_rounds": 0,
            "recent_success_rate": 0.0,
            "target_success_rate": 0.8,
        },
        "winner_pattern": "Recency-first ranking with a separate live tape and explicit conflict disclosure.",
        "loser_pattern": "Letting shadow signals raise core confidence without stronger confirmation.",
        "source_pack": build_source_pack(result),
        "retrieval_result": result,
        "source_item": {
            "topic": topic,
            "questions": request.get("questions", []),
            "mode": request.get("mode", "generic"),
            "market_relevance": request.get("market_relevance", []),
        },
    }


def main() -> None:
    args = parse_args()
    try:
        payload = load_json(Path(args.input).resolve())
        result = build_run_record(payload, args)
        if not args.quiet:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.output:
            write_json(Path(args.output).resolve(), result)
        sys.exit(0)
    except Exception as exc:
        print(
            json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
