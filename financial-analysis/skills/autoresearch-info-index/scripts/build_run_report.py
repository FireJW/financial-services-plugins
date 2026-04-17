#!/usr/bin/env python3
"""
Build a markdown phase 1 run report from multiple info-index result JSON files.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "examples"

    parser = argparse.ArgumentParser(
        description="Build a markdown phase 1 run report from info-index result JSON files."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing result JSON files. Defaults to ../examples",
    )
    parser.add_argument("--output", help="Optional path to save the markdown report")
    parser.add_argument("--owner", default="Codex", help="Owner field to include in the report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout markdown output and only write the requested file.",
    )
    return parser.parse_args()


def load_results(input_dir: Path) -> list[dict[str, Any]]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    candidate_paths = sorted(input_dir.glob("*-evaluated.json"))
    if not candidate_paths:
        candidate_paths = sorted(input_dir.glob("*.json"))

    results: list[dict[str, Any]] = []
    for path in candidate_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if "decision" not in payload or "soft_scores" not in payload:
            continue
        results.append(payload)

    if not results:
        raise ValueError(f"No result JSON files found in {input_dir}")
    return results


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def format_signed(value: float) -> str:
    rounded = round(value, 2)
    if rounded > 0:
        return f"+{rounded:g}"
    return f"{rounded:g}"


def most_common_nonempty(values: list[str], limit: int = 3) -> list[str]:
    counter = Counter(value.strip() for value in values if value and value.strip())
    return [item for item, _ in counter.most_common(limit)]


def summarize_task_goal(goal: str) -> str:
    text = goal.strip()
    prefix = "Improve repeatable indexing of "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if ": " in text:
        text = text.split(": ", 1)[0]
    return text or "Unnamed task"


def compute_overall_result(keeps: int, rollbacks: int, avg_delta: float, hard_failures: int) -> str:
    if keeps > 0 and rollbacks == 0 and avg_delta > 0 and hard_failures == 0:
        return "KEEP"
    if keeps == 0:
        return "ROLLBACK"
    return "MIXED"


def build_markdown(results: list[dict[str, Any]], owner: str) -> str:
    total_runs = len(results)
    keep_runs = [r for r in results if r["decision"]["keep"]]
    rollback_runs = [r for r in results if not r["decision"]["keep"]]
    keeps = len(keep_runs)
    rollbacks = len(rollback_runs)
    hard_check_failure_runs = sum(1 for r in results if not r["hard_checks"]["passed"])
    hard_check_failure_messages = sum(len(r["hard_checks"].get("failures", [])) for r in results)

    baseline_scores = [r["soft_scores"]["baseline_total"] for r in results]
    candidate_scores = [r["soft_scores"]["candidate_total"] for r in results]
    deltas = [r["soft_scores"]["delta"] for r in results]

    credibility_blocks = [r.get("credibility_metrics", {}) for r in results]
    source_strengths = [block.get("source_strength_score", 0) for block in credibility_blocks]
    confirmation_scores = [block.get("claim_confirmation_score", 0) for block in credibility_blocks]
    timeliness_scores = [block.get("timeliness_score", 0) for block in credibility_blocks]
    agreement_scores = [block.get("agreement_score", 0) for block in credibility_blocks]
    confidence_scores = [block.get("confidence_score", 0) for block in credibility_blocks]
    interval_lows = [block.get("confidence_interval", {}).get("low", 0) for block in credibility_blocks]
    interval_highs = [block.get("confidence_interval", {}).get("high", 0) for block in credibility_blocks]
    interval_widths = [block.get("confidence_interval", {}).get("width", 0) for block in credibility_blocks]
    confidence_labels = Counter(block.get("display_confidence_label", block.get("confidence_label", "unknown")) for block in credibility_blocks)
    confidence_gates = Counter(block.get("confidence_gate", {}).get("status", "unknown") for block in credibility_blocks)
    retrieval_quality_blocks = [r.get("retrieval_quality_metrics", {}) for r in results]
    freshness_capture_scores = [block.get("freshness_capture_score") for block in retrieval_quality_blocks if isinstance(block.get("freshness_capture_score"), (int, float))]
    shadow_signal_scores = [block.get("shadow_signal_discipline_score") for block in retrieval_quality_blocks if isinstance(block.get("shadow_signal_discipline_score"), (int, float))]
    source_promotion_scores = [block.get("source_promotion_discipline_score") for block in retrieval_quality_blocks if isinstance(block.get("source_promotion_discipline_score"), (int, float))]
    blocked_handling_scores = [block.get("blocked_source_handling_score") for block in retrieval_quality_blocks if isinstance(block.get("blocked_source_handling_score"), (int, float))]
    observability_blocks = [r.get("retrieval_observability", {}) for r in results]
    blocked_source_counts = [block.get("blocked_source_count", 0) for block in observability_blocks if isinstance(block.get("blocked_source_count", 0), (int, float))]
    missing_family_counts = [block.get("missing_expected_source_family_count", 0) for block in observability_blocks if isinstance(block.get("missing_expected_source_family_count", 0), (int, float))]
    blocked_source_name_lists = [
        item.get("source_name", "")
        for block in observability_blocks
        for item in block.get("blocked_sources", [])
        if isinstance(item, dict)
    ]
    missing_family_lists = [
        family
        for block in observability_blocks
        for family in block.get("missing_expected_source_families", [])
        if isinstance(family, str) and family.strip()
    ]
    alignment_blocks = [
        block
        for block in (r.get("benchmark_alignment", {}) for r in results)
        if isinstance(block, dict) and block.get("available")
    ]
    alignment_confidence_hits = sum(
        1
        for block in alignment_blocks
        if isinstance(block.get("confidence_alignment"), dict)
        and block["confidence_alignment"].get("within_expected_band")
    )
    alignment_full_hits = sum(1 for block in alignment_blocks if block.get("all_available_checks_passed"))

    sample_sets = sorted({r.get("sample_set_version", "unknown") for r in results})
    baseline_versions = sorted({r.get("baseline_version", "unknown") for r in results})
    candidate_versions = sorted({r.get("candidate_version", "unknown") for r in results})
    task_mix = [
        {"task_id": result.get("task_id", "unknown"), "summary": summarize_task_goal(result.get("task_goal", ""))}
        for result in results
    ]
    unique_task_summaries = sorted({item["summary"] for item in task_mix if item["summary"]})
    goal_line = (
        f"Batch review across {len(unique_task_summaries)} distinct information-index tasks"
        if len(unique_task_summaries) > 1
        else (task_mix[0]["summary"] if task_mix else "Summarize phase 1 info-index runs")
    )

    hard_failure_lines: list[str] = []
    for result in rollback_runs:
        task_id = result.get("task_id", "unknown")
        for failure in result["hard_checks"].get("failures", []):
            hard_failure_lines.append(f"- {task_id}: {failure}")

    dimension_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"baseline": 0.0, "candidate": 0.0, "count": 0.0})
    for result in results:
        for row in result["soft_scores"]["dimensions"]:
            stats = dimension_stats[row["name"]]
            stats["baseline"] += row["baseline"]
            stats["candidate"] += row["score"]
            stats["count"] += 1

    winning_patterns = most_common_nonempty([r.get("notes", {}).get("winner_pattern", "") for r in keep_runs])
    losing_patterns = most_common_nonempty([r.get("notes", {}).get("loser_pattern", "") for r in rollback_runs])

    overall_result = compute_overall_result(keeps, rollbacks, average(deltas), hard_check_failure_runs)
    generated_date = datetime.now().date().isoformat()

    lines: list[str] = [
        "# Phase 1 Run Report",
        f"Date: {generated_date}",
        "Profile: info-index",
        f"Sample Set: {', '.join(sample_sets)}",
        f"Baseline Version: {', '.join(baseline_versions)}",
        f"Candidate Version: {', '.join(candidate_versions)}",
        f"Owner: {owner}",
        f"Goal: {goal_line}",
        "",
        "## Summary",
        f"- Total Runs: {total_runs}",
        f"- Keep: {keeps}",
        f"- Rollback: {rollbacks}",
        f"- Runs With Hard Check Failures: {hard_check_failure_runs}",
        f"- Hard Check Failure Messages: {hard_check_failure_messages}",
        f"- Avg Baseline Score: {round(average(baseline_scores), 2):g}",
        f"- Avg Candidate Score: {round(average(candidate_scores), 2):g}",
        f"- Avg Delta: {format_signed(average(deltas))}",
        f"- Avg Evidence Confidence Score: {round(average(confidence_scores), 2):g}",
        f"- Avg Source Strength: {round(average(source_strengths), 2):g}",
        f"- Avg Agreement Score: {round(average(agreement_scores), 2):g}",
        f"- Avg Evidence Band: {round(average(interval_lows), 2):g}-{round(average(interval_highs), 2):g}",
        f"- Avg Evidence Band Width: {round(average(interval_widths), 2):g}",
        f"- Confidence Labels: usable-high={confidence_labels.get('high', 0)}, usable-medium={confidence_labels.get('medium', 0)}, usable-low={confidence_labels.get('low', 0)}, blocked={confidence_labels.get('blocked', 0)}",
        f"- Confidence Gates: usable={confidence_gates.get('usable', 0)}, blocked={confidence_gates.get('blocked_by_hard_checks', 0)}",
        f"- Avg Freshness Capture Score: {round(average(freshness_capture_scores), 2):g}",
        f"- Avg Shadow Signal Discipline: {round(average(shadow_signal_scores), 2):g}",
        f"- Avg Promotion Discipline: {round(average(source_promotion_scores), 2):g}",
        f"- Avg Blocked Source Handling: {round(average(blocked_handling_scores), 2):g}",
        f"- Runs With Blocked Sources: {sum(1 for count in blocked_source_counts if count and count > 0)}",
        f"- Runs With Missing Expected Source Families: {sum(1 for count in missing_family_counts if count and count > 0)}",
        "",
    ]

    if alignment_blocks:
        lines.extend(
            [
                f"- Benchmark Confidence Band Hits: {alignment_confidence_hits}/{len(alignment_blocks)}",
                f"- Full Benchmark Alignment Hits: {alignment_full_hits}/{len(alignment_blocks)}",
                "",
            ]
        )

    if len(unique_task_summaries) > 1:
        lines.extend(["## Task Mix", *[f"- {item['task_id']}: {item['summary']}" for item in task_mix], ""])

    lines.extend(
        [
            "## Decision",
            f"- Overall Result: {overall_result}",
            "- Why:",
            f"  - Keep count: {keeps}, rollback count: {rollbacks}",
            f"  - Average score delta: {format_signed(average(deltas))}",
            f"  - Runs with hard-check failures: {hard_check_failure_runs}",
            f"  - Average evidence confidence score: {round(average(confidence_scores), 2):g}",
            "- Next Action:",
        ]
    )

    if overall_result == "KEEP":
        lines.extend(
            [
                "  - Keep the current candidate and improve only the weakest scoring dimension next",
                "  - Use the confidence snapshot to compare message quality across the next sample batch",
            ]
        )
    elif overall_result == "ROLLBACK":
        lines.extend(
            [
                "  - Return to the last stable baseline version",
                "  - Fix hard-check discipline before trusting the evidence-confidence metrics",
            ]
        )
    else:
        lines.extend(
            [
                "  - Keep investigating the strongest keep pattern and the most common rollback reason",
                "  - Improve one indexing discipline only before the next batch",
            ]
        )

    lines.extend(
        [
            "",
            "## Run Table",
            "",
            "| Run ID | Item ID | Candidate | Delta | Evidence | Band | Gate | Decision | Core Reason |",
            "|---|---|---:|---:|---:|---|---|---|---|",
        ]
    )

    for index, result in enumerate(results, start=1):
        metrics = result.get("credibility_metrics", {})
        interval = metrics.get("confidence_interval", {})
        band = f"{interval.get('low', 0)}-{interval.get('high', 0)}"
        gate = metrics.get("confidence_gate", {}).get("status", "unknown")
        lines.append(
            f"| {index:03d} | {result.get('task_id', 'unknown')} | "
            f"{result['soft_scores']['candidate_total']} | {format_signed(result['soft_scores']['delta'])} | "
            f"{metrics.get('confidence_score', 0)} | {band} | "
            f"{gate} | "
            f"{'Keep' if result['decision']['keep'] else 'Rollback'} | {result['decision']['reason']} |"
        )

    lines.extend(["", "## Hard Check Failures"])
    lines.extend(hard_failure_lines if hard_failure_lines else ["- None"])

    lines.extend(
        [
            "",
            "## Evidence Snapshot",
            "",
            "| Metric | Average |",
            "|---|---:|",
            f"| Source Strength | {average(source_strengths):.2f} |",
            f"| Claim Confirmation | {average(confirmation_scores):.2f} |",
            f"| Timeliness | {average(timeliness_scores):.2f} |",
            f"| Agreement | {average(agreement_scores):.2f} |",
            f"| Evidence Confidence Score | {average(confidence_scores):.2f} |",
            f"| Evidence Band Width | {average(interval_widths):.2f} |",
            f"| Freshness Capture Score | {average(freshness_capture_scores):.2f} |",
            f"| Shadow Signal Discipline | {average(shadow_signal_scores):.2f} |",
            f"| Promotion Discipline | {average(source_promotion_scores):.2f} |",
            f"| Blocked Source Handling | {average(blocked_handling_scores):.2f} |",
        ]
    )

    lines.extend(["", "## Retrieval Gaps"])
    common_blocked_sources = most_common_nonempty(blocked_source_name_lists, limit=5)
    common_missing_families = most_common_nonempty(missing_family_lists, limit=5)
    lines.extend(
        [
            f"- Common blocked sources: {', '.join(common_blocked_sources) if common_blocked_sources else 'None'}",
            f"- Common missing expected source families: {', '.join(common_missing_families) if common_missing_families else 'None'}",
            "",
            "| Item ID | Blocked Sources | Missing Expected Source Families |",
            "|---|---|---|",
        ]
    )
    for result in results:
        observability = result.get("retrieval_observability", {})
        blocked_sources = ", ".join(
            item.get("source_name", "")
            for item in observability.get("blocked_sources", [])
            if isinstance(item, dict) and item.get("source_name")
        ) or "None"
        missing_families = ", ".join(observability.get("missing_expected_source_families", [])) or "None"
        lines.append(f"| {result.get('task_id', 'unknown')} | {blocked_sources} | {missing_families} |")

    lines.extend(["", "## Benchmark Alignment"])
    if alignment_blocks:
        lines.extend(
            [
                "",
                "| Item ID | Target Band | Actual Score | In Band | Checks Passed | Expected Judgment |",
                "|---|---|---:|---|---:|---|",
            ]
        )
        for result in results:
            alignment = result.get("benchmark_alignment", {})
            if not isinstance(alignment, dict) or not alignment.get("available"):
                continue
            expected = alignment.get("expected", {})
            confidence_alignment = alignment.get("confidence_alignment", {}) or {}
            target_band = expected.get("confidence_interval_pct", [])
            band_label = (
                f"{target_band[0]}-{target_band[1]}"
                if isinstance(target_band, list) and len(target_band) == 2
                else "n/a"
            )
            lines.append(
                f"| {result.get('task_id', 'unknown')} | {band_label} | "
                f"{alignment.get('actual', {}).get('confidence_score', 0)} | "
                f"{'Yes' if confidence_alignment.get('within_expected_band') else 'No'} | "
                f"{alignment.get('checks_passed', 0)}/{alignment.get('checks_available', 0)} | "
                f"{expected.get('expected_judgment', '')} |"
            )
    else:
        lines.extend(["- Not available in these result files"])

    lines.extend(
        [
            "",
            "## Score Trends",
            "",
            "### By Dimension",
            "",
            "| Dimension | Avg Baseline | Avg Candidate | Delta | Note |",
            "|---|---:|---:|---:|---|",
        ]
    )

    best_dimension = None
    if dimension_stats:
        dimension_deltas = {
            name: (stats["candidate"] - stats["baseline"]) / max(stats["count"], 1)
            for name, stats in dimension_stats.items()
        }
        max_delta = max(dimension_deltas.values())
        if max_delta > 0 and len({round(delta, 6) for delta in dimension_deltas.values()}) > 1:
            best_dimension = max(dimension_deltas, key=dimension_deltas.get)

    for name in sorted(dimension_stats):
        stats = dimension_stats[name]
        avg_base = stats["baseline"] / stats["count"]
        avg_cand = stats["candidate"] / stats["count"]
        delta = avg_cand - avg_base
        note = "Largest improvement" if name == best_dimension else ""
        label = name.replace("_", " ").title()
        lines.append(f"| {label} | {avg_base:.2f} | {avg_cand:.2f} | {format_signed(delta)} | {note} |")

    lines.extend(["", "## Winning Patterns"])
    lines.extend([f"- {pattern}" for pattern in winning_patterns] if winning_patterns else ["- None recorded yet"])

    lines.extend(["", "## Losing Patterns"])
    lines.extend([f"- {pattern}" for pattern in losing_patterns] if losing_patterns else ["- None recorded yet"])

    lines.extend(["", "## Recommendation"])
    lines.append(f"- Keep using candidate? {'Yes' if overall_result != 'ROLLBACK' else 'No'}")
    if overall_result != "ROLLBACK":
        weakest_dimension = (
            min(
                dimension_stats,
                key=lambda name: (dimension_stats[name]["candidate"] / max(dimension_stats[name]["count"], 1)),
            )
            if dimension_stats
            else None
        )
        if weakest_dimension:
            lines.append("- If Yes:")
            lines.append(f"  - Next dimension to improve: {weakest_dimension.replace('_', ' ')}")
            lines.append("  - Keep comparing benchmark confidence bands, not only total scores")
    else:
        rollback_target = rollback_runs[0]["decision"]["rollback_to"] if rollback_runs else "last stable baseline"
        lines.append("- If No:")
        lines.append(f"  - Roll back to: {rollback_target}")
        lines.append("  - Fix hard-check discipline first, then recalibrate against the benchmark bands")

    lines.extend(
        [
            "",
            "## Appendix",
            "- Thresholds:",
            "  - Min Improvement: 2",
            "  - Large Regression: 5",
            "- Stop Rule:",
            "  - pause after 3 rounds with less than 2-point gain",
            "- Notes:",
            "  - this report summarizes whichever evaluated phase 1 result files were passed into the report builder",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    results = load_results(input_dir)
    markdown = build_markdown(results, owner=args.owner)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

    if not args.quiet:
        print(markdown, end="")


if __name__ == "__main__":
    main()
