from __future__ import annotations

from typing import Any


TASK_VALUES = {"intake", "match", "tailor", "track", "apply_assist"}
STATUS_VALUES = {"ready", "partial", "skipped", "error"}
DECISION_VALUES = {"go", "maybe", "skip", ""}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def contract_errors(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    task = clean_text(result.get("task"))
    if task not in TASK_VALUES:
        errors.append("task must be one of intake, match, tailor, track, apply_assist")

    status = clean_text(result.get("status"))
    if status not in STATUS_VALUES:
        errors.append("status must be one of ready, partial, skipped, error")

    if clean_text(result.get("job_id")) == "":
        errors.append("job_id is required")

    if not isinstance(result.get("job_card"), dict):
        errors.append("job_card must be a dict")

    fit_score = result.get("fit_score")
    if fit_score is not None and not isinstance(fit_score, int):
        errors.append("fit_score must be an int or null")

    decision = clean_text(result.get("decision"))
    if decision not in DECISION_VALUES:
        errors.append("decision must be go, maybe, skip, or empty")

    if not isinstance(result.get("artifacts"), dict):
        errors.append("artifacts must be a dict")

    if not isinstance(result.get("warnings"), list):
        errors.append("warnings must be a list")

    if not isinstance(result.get("human_review_items"), list):
        errors.append("human_review_items must be a list")

    if clean_text(result.get("generated_at")) == "":
        errors.append("generated_at is required")

    return errors


def validate_career_result(result: dict[str, Any]) -> bool:
    return not contract_errors(result)
