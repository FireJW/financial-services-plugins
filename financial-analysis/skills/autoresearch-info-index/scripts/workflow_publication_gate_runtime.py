#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_queue(value: Any) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        queue.append(
            {
                "title": clean_text(item.get("title")),
                "summary": clean_text(item.get("summary")),
                "priority_level": clean_text(item.get("priority_level")).lower() or "none",
                "priority_score": int(item.get("priority_score", 0) or 0),
                "recommended_action": clean_text(item.get("recommended_action")),
            }
        )
    return queue


def build_workflow_publication_gate(publish_package: dict[str, Any]) -> dict[str, Any]:
    package = publish_package if isinstance(publish_package, dict) else {}
    manual_review = safe_dict(package.get("workflow_manual_review") or package.get("manual_review"))
    queue = normalize_queue(manual_review.get("queue") or manual_review.get("items") or package.get("operator_review_queue"))

    required = bool(manual_review.get("required")) or bool(queue)
    high_priority_count = sum(
        1
        for item in queue
        if item.get("priority_level") == "high" or int(item.get("priority_score", 0) or 0) >= 80
    )
    required_count = int(manual_review.get("required_count", len(queue)) or 0)
    status = clean_text(manual_review.get("status"))
    if not status:
        status = "awaiting_reddit_operator_review" if required else "not_required"

    publication_readiness = clean_text(
        package.get("publication_readiness") or manual_review.get("publication_readiness")
    )
    if not publication_readiness:
        publication_readiness = "blocked_by_reddit_operator_review" if required else "ready"

    next_step = clean_text(manual_review.get("next_step"))
    if not next_step:
        next_step = (
            "Review the queued Reddit operator items before publishing."
            if required
            else "No Reddit comment operator review action is required."
        )

    summary = clean_text(manual_review.get("summary"))
    if not summary:
        summary = (
            f"{required_count} Reddit operator review item(s) require attention."
            if required
            else "No Reddit comment operator review items were detected."
        )

    return {
        "publication_readiness": publication_readiness,
        "manual_review": {
            "required": required,
            "status": status,
            "required_count": required_count,
            "high_priority_count": high_priority_count,
            "summary": summary,
            "next_step": next_step,
            "queue": queue,
            "publication_readiness": publication_readiness,
        },
    }


__all__ = ["build_workflow_publication_gate"]
