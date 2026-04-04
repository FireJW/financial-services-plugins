#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_workflow_publication_gate(payload: dict[str, Any]) -> dict[str, Any]:
    manual_review = safe_dict(payload.get("workflow_manual_review") or payload.get("manual_review"))
    return {
        "publication_readiness": clean_text(
            payload.get("publication_readiness") or manual_review.get("publication_readiness") or "ready"
        ),
        "manual_review": manual_review,
    }


__all__ = ["build_workflow_publication_gate"]
