#!/usr/bin/env python3
"""Automated postclose review runtime.

Reads a shortlist result.json, fetches intraday bars, classifies plan outcomes,
and produces structured adjustments + markdown report.
"""
from __future__ import annotations

from typing import Any


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
