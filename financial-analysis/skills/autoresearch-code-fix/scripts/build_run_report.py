#!/usr/bin/env python3
"""
Build a markdown phase 1 run report from multiple code-fix result JSON files.

This script is intentionally zero-dependency and optimized for small sample
sets. It reads one directory of result JSON files and produces a human-readable
markdown summary suitable for phase 1 review.
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
        description="Build a markdown phase 1 run report from result JSON files."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(default_input),
        help="Directory containing result JSON files. Defaults to ../examples",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save the markdown report",
    )
    parser.add_argument(
        "--owner",
        default="Codex",
        help="Owner field to include in the report",
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
        if path.name.endswith("-case.json") or path.name == "run-record-template.json":
            continue
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


def percent(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(part / total * 100)}%"


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
    prefix = "Improve repeatable handling of "
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
    hard_check_failures = sum(1 for r in results if not r["hard_checks"]["passed"])

    baseline_scores = [r["soft_scores"]["baseline_total"] for r in results]
    candidate_scores = [r["soft_scores"]["candidate_total"] for r in results]
    deltas = [r["soft_scores"]["delta"] for r in results]

    sample_sets = sorted({r.get("sample_set_version", "unknown") for r in results})
    baseline_versions = sorted({r.get("baseline_version", "unknown") for r in results})
    candidate_versions = sorted({r.get("candidate_version", "unknown") for r in results})
    goals = most_common_nonempty([r.get("task_goal", "") for r in results], limit=1)
    task_mix = [
        {
            "task_id": result.get("task_id", "unknown"),
            "summary": summarize_task_goal(result.get("task_goal", "")),
        }
        for result in results
    ]
    unique_task_summaries = sorted({item["summary"] for item in task_mix if item["summary"]})

    first_pass_baseline = sum(1 for r in results if r["soft_scores"]["baseline_total"] >= 70)
    first_pass_candidate = sum(1 for r in results if r["decision"]["keep"])
    new_critical_regressions = sum(
        1
        for r in results
        if any("severe" in concern.lower() or "critical" in concern.lower() for concern in r["decision"].get("concerns", []))
    )

    overall_result = compute_overall_result(
        keeps=keeps,
        rollbacks=rollbacks,
        avg_delta=average(deltas),
        hard_failures=hard_check_failures,
    )

    hard_failure_lines: list[str] = []
    for result in rollback_runs:
        bug_id = result.get("task_id", "unknown")
        for failure in result["hard_checks"].get("failures", []):
            hard_failure_lines.append(f"- {bug_id}: {failure}")

    dimension_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"baseline": 0.0, "candidate": 0.0, "count": 0.0})
    for result in results:
        for row in result["soft_scores"]["dimensions"]:
            stats = dimension_stats[row["name"]]
            stats["baseline"] += row["baseline"]
            stats["candidate"] += row["score"]
            stats["count"] += 1

    winning_patterns = most_common_nonempty([r.get("notes", {}).get("winner_pattern", "") for r in keep_runs])
    losing_patterns = most_common_nonempty([r.get("notes", {}).get("loser_pattern", "") for r in rollback_runs])

    generated_date = datetime.now().date().isoformat()
    if len(unique_task_summaries) <= 1:
        goal_line = goals[0] if goals else "Summarize phase 1 code-fix runs"
    else:
        goal_line = f"Batch review across {len(unique_task_summaries)} distinct code-fix tasks"

    lines: list[str] = [
        "# Phase 1 Run Report",
        f"Date: {generated_date}",
        "Profile: code-fix",
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
        f"- Hard Check Failures: {hard_check_failures}",
        f"- Avg Baseline Score: {round(average(baseline_scores), 2):g}",
        f"- Avg Candidate Score: {round(average(candidate_scores), 2):g}",
        f"- Avg Delta: {format_signed(average(deltas))}",
        "- First-Pass Success Rate:",
        f"  Baseline: {percent(first_pass_baseline, total_runs)}",
        f"  Candidate: {percent(first_pass_candidate, total_runs)}",
        "- New Critical Regressions:",
        "  Baseline: 0",
        f"  Candidate: {new_critical_regressions}",
        "",
    ]

    if len(unique_task_summaries) > 1:
        lines.extend(
            [
                "## Task Mix",
                *[f"- {item['task_id']}: {item['summary']}" for item in task_mix],
                "",
            ]
        )

    lines.extend(
        [
        "## Decision",
        f"- Overall Result: {overall_result}",
        "- Why:",
        f"  - Keep count: {keeps}, rollback count: {rollbacks}",
        f"  - Average score delta: {format_signed(average(deltas))}",
        f"  - Hard-check failures: {hard_check_failures}",
        "- Next Action:",
        ]
    )

    if overall_result == "KEEP":
        lines.extend(
            [
                "  - Continue iterating on the weakest scoring dimension only",
                "  - Preserve the current candidate as the active baseline for the next round",
            ]
        )
    elif overall_result == "ROLLBACK":
        lines.extend(
            [
                "  - Return to the last stable baseline version",
                "  - Fix hard-check discipline before attempting another iteration",
            ]
        )
    else:
        lines.extend(
            [
                "  - Keep investigating the strongest keep pattern and the most common rollback reason",
                "  - Improve one discipline only before the next batch",
            ]
        )

    lines.extend(
        [
            "",
            "## Run Table",
            "",
            "| Run ID | Bug ID | Baseline | Candidate | Delta | Hard Checks | Decision | Core Reason |",
            "|---|---|---:|---:|---:|---|---|---|",
        ]
    )

    for index, result in enumerate(results, start=1):
        run_id = f"{index:03d}"
        bug_id = result.get("task_id", "unknown")
        baseline = result["soft_scores"]["baseline_total"]
        candidate = result["soft_scores"]["candidate_total"]
        delta = format_signed(result["soft_scores"]["delta"])
        hard = "Pass" if result["hard_checks"]["passed"] else "Fail"
        decision = "Keep" if result["decision"]["keep"] else "Rollback"
        reason = result["decision"]["reason"]
        lines.append(f"| {run_id} | {bug_id} | {baseline} | {candidate} | {delta} | {hard} | {decision} | {reason} |")

    lines.extend(["", "## Hard Check Failures"])
    if hard_failure_lines:
        lines.extend(hard_failure_lines)
    else:
        lines.append("- None")

    lines.extend(["", "## Score Trends", "", "### By Dimension", "", "| Dimension | Avg Baseline | Avg Candidate | Delta | Note |", "|---|---:|---:|---:|---|"])

    for name in sorted(dimension_stats):
        stats = dimension_stats[name]
        avg_base = stats["baseline"] / stats["count"]
        avg_cand = stats["candidate"] / stats["count"]
        delta = avg_cand - avg_base
        note = "Largest improvement" if name == max(dimension_stats, key=lambda n: (dimension_stats[n]["candidate"] - dimension_stats[n]["baseline"])) else ""
        label = name.replace("_", " ").title()
        lines.append(f"| {label} | {avg_base:.2f} | {avg_cand:.2f} | {format_signed(delta)} | {note} |")

    lines.extend(["", "## Winning Patterns"])
    if winning_patterns:
        lines.extend(f"- {pattern}" for pattern in winning_patterns)
    else:
        lines.append("- None recorded yet")

    lines.extend(["", "## Losing Patterns"])
    if losing_patterns:
        lines.extend(f"- {pattern}" for pattern in losing_patterns)
    else:
        lines.append("- None recorded yet")

    weakest_dimension = None
    if dimension_stats:
        weakest_dimension = min(
            dimension_stats,
            key=lambda name: (dimension_stats[name]["candidate"] / max(dimension_stats[name]["count"], 1)),
        )

    lines.extend(["", "## Recommendation"])
    lines.append(f"- Keep using candidate? {'Yes' if overall_result != 'ROLLBACK' else 'No'}")
    if overall_result != "ROLLBACK" and weakest_dimension:
        lines.append(f"- If Yes:")
        lines.append(f"  - Next dimension to improve: {weakest_dimension.replace('_', ' ')}")
    else:
        rollback_target = rollback_runs[0]["decision"]["rollback_to"] if rollback_runs else "last stable baseline"
        lines.append("- If No:")
        lines.append(f"  - Roll back to: {rollback_target}")
        lines.append("  - Fix hard-check discipline first")

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
            "  - this report covers only the phase 1 code-fix sample pool",
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
        output_path.write_text(markdown, encoding="utf-8")

    print(markdown, end="")


if __name__ == "__main__":
    main()
