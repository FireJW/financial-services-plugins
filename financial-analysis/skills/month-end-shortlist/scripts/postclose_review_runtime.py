#!/usr/bin/env python3
"""Automated postclose review runtime.

Reads a shortlist result.json, fetches intraday bars, classifies plan outcomes,
and produces structured adjustments + markdown report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TRADINGAGENTS_SCRIPT_DIR = (
    Path(__file__).resolve().parents[2]
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(TRADINGAGENTS_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(TRADINGAGENTS_SCRIPT_DIR))


def classify_plan_outcome(*, plan_action: str, actual_return_pct: float) -> str:
    """Classify a single candidate's plan-vs-actual outcome.

    Args:
        plan_action: The midday action from the shortlist run.
            '可执行' = qualified, '继续观察' = watch/near_miss, '不执行' = blocked.
        actual_return_pct: The actual day return in percent (e.g. -1.46 for -1.46%).

    Returns one of: 'plan_correct', 'plan_too_aggressive', 'missed_opportunity',
    'plan_correct_negative'.
    """
    is_qualified = plan_action == "可执行"
    is_skip = plan_action in ("继续观察", "不执行")

    if is_qualified:
        if actual_return_pct < -1.0:
            return "plan_too_aggressive"
        return "plan_correct"

    if is_skip:
        if actual_return_pct > 2.0:
            return "missed_opportunity"
        return "plan_correct_negative"

    # Fallback for unknown actions
    return "plan_correct_negative"


def generate_adjustment(judgment: str) -> dict[str, Any]:
    """Generate a priority adjustment dict from a plan outcome judgment.

    Returns dict with keys: adjustment, priority_delta, gate_next_run.
    """
    if judgment == "plan_too_aggressive":
        return {"adjustment": "downgrade", "priority_delta": -5, "gate_next_run": True}
    if judgment == "missed_opportunity":
        return {"adjustment": "upgrade", "priority_delta": 5, "gate_next_run": False}
    return {"adjustment": "hold", "priority_delta": 0, "gate_next_run": False}


def _fetch_intraday_bars_for_review(ticker: str, trade_date: str) -> list[dict[str, Any]]:
    """Fetch intraday bars for review — delegates to month_end_shortlist_runtime's cached wrapper."""
    try:
        from month_end_shortlist_runtime import eastmoney_cached_intraday_bars_for_candidate
        return eastmoney_cached_intraday_bars_for_candidate(ticker, trade_date)
    except ImportError:
        return []


def _extract_actionable_candidates(result_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract candidates that have a midday_action from the result."""
    candidates = []
    for source_key in ("top_picks", "near_miss_candidates"):
        for item in result_json.get(source_key, []) or []:
            if not isinstance(item, dict):
                continue
            action = (item.get("midday_action") or "").strip()
            if action:
                candidates.append(item)
    return candidates


def _compute_return_pct(candidate: dict[str, Any]) -> float | None:
    """Compute actual day return from close and prev_close."""
    try:
        close = float(candidate["close"])
        prev_close = float(candidate["prev_close"])
        if prev_close <= 0:
            return None
        return round((close - prev_close) / prev_close * 100, 2)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def run_postclose_review(
    result_json: dict[str, Any],
    trade_date: str,
    plan_md: str | None = None,
) -> dict[str, Any]:
    """Run the full postclose review pipeline.

    Args:
        result_json: Parsed shortlist result.json dict.
        trade_date: The date being reviewed (YYYY-MM-DD).
        plan_md: Optional morning plan markdown (unused in v1, reserved).

    Returns:
        Review output dict with candidates_reviewed, summary, prior_review_adjustments.
    """
    actionable = _extract_actionable_candidates(result_json)
    candidates_reviewed: list[dict[str, Any]] = []
    summary = {"total_reviewed": 0, "correct": 0, "too_aggressive": 0, "missed": 0, "correct_negative": 0}

    for cand in actionable:
        ticker = (cand.get("ticker") or "").strip()
        name = (cand.get("name") or "").strip() or ticker
        plan_action = (cand.get("midday_action") or "").strip()
        actual_return = _compute_return_pct(cand)
        if actual_return is None:
            continue

        # Intraday bars — best-effort
        intraday_structure = "unavailable"
        try:
            bars = _fetch_intraday_bars_for_review(ticker, trade_date)
            if bars:
                from tradingagents_eastmoney_market import classify_intraday_structure
                intraday_structure = classify_intraday_structure(bars)
        except Exception:
            pass

        judgment = classify_plan_outcome(plan_action=plan_action, actual_return_pct=actual_return)
        adj = generate_adjustment(judgment)

        candidates_reviewed.append({
            "ticker": ticker,
            "name": name,
            "plan_action": plan_action,
            "actual_return_pct": actual_return,
            "intraday_structure": intraday_structure,
            "judgment": judgment,
            **adj,
        })

        summary["total_reviewed"] += 1
        if judgment == "plan_correct":
            summary["correct"] += 1
        elif judgment == "plan_too_aggressive":
            summary["too_aggressive"] += 1
        elif judgment == "missed_opportunity":
            summary["missed"] += 1
        elif judgment == "plan_correct_negative":
            summary["correct_negative"] += 1

    prior_review_adjustments = [
        {"ticker": c["ticker"], "adjustment": c["adjustment"],
         "priority_delta": c["priority_delta"], "gate_next_run": c["gate_next_run"]}
        for c in candidates_reviewed if c["adjustment"] != "hold"
    ]

    return {
        "trade_date": trade_date,
        "candidates_reviewed": candidates_reviewed,
        "summary": summary,
        "prior_review_adjustments": prior_review_adjustments,
    }


def build_review_markdown(review: dict[str, Any]) -> str:
    """Render the review output as a markdown report."""
    lines: list[str] = []
    trade_date = review.get("trade_date", "unknown")
    lines.append(f"# 盘后复盘报告 — {trade_date}")
    lines.append("")

    # Section: 操作建议摘要
    lines.append("## 操作建议摘要")
    lines.append("")
    lines.append("| 代码 | 名称 | 计划操作 | 实际涨跌% | 分时结构 | 判定 | 调整 |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in review.get("candidates_reviewed", []):
        lines.append(
            f"| {c['ticker']} | {c['name']} | {c['plan_action']} | "
            f"{c['actual_return_pct']:+.2f}% | {c['intraday_structure']} | "
            f"{c['judgment']} | {c['adjustment']} |"
        )
    lines.append("")

    # Section: summary
    s = review.get("summary", {})
    lines.append("## 复盘统计")
    lines.append("")
    lines.append(f"- 总复盘: {s.get('total_reviewed', 0)}")
    lines.append(f"- 计划正确: {s.get('correct', 0)}")
    lines.append(f"- 过于激进: {s.get('too_aggressive', 0)}")
    lines.append(f"- 错过机会: {s.get('missed', 0)}")
    lines.append(f"- 正确回避: {s.get('correct_negative', 0)}")
    lines.append("")

    # Section: 次日观察点
    lines.append("## 次日观察点")
    lines.append("")
    adjustments = review.get("prior_review_adjustments", [])
    if adjustments:
        for adj in adjustments:
            action = "加分 +5" if adj["adjustment"] == "upgrade" else "减分 -5 + 强制确认"
            lines.append(f"- {adj['ticker']}: {action}")
    else:
        lines.append("- 无需调整")
    lines.append("")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run postclose review on a shortlist result.")
    parser.add_argument("--result", required=True, help="Path to result.json from shortlist run.")
    parser.add_argument("--date", required=True, help="Trade date being reviewed (YYYY-MM-DD).")
    parser.add_argument("--plan", default=None, help="Optional path to morning trading plan markdown.")
    parser.add_argument("--output", default=None, help="Write review JSON to this path.")
    parser.add_argument("--markdown-output", default=None, help="Write review markdown to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result_path = Path(args.result).expanduser().resolve()
    result_json = json.loads(result_path.read_text(encoding="utf-8"))
    plan_md = None
    if args.plan:
        plan_md = Path(args.plan).expanduser().resolve().read_text(encoding="utf-8")

    review = run_postclose_review(result_json, args.date, plan_md)

    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        md_out = Path(args.markdown_output).expanduser().resolve()
        md_out.write_text(build_review_markdown(review), encoding="utf-8")
    if not args.output:
        sys.stdout.write(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
