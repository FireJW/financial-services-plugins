from __future__ import annotations

from typing import Any


TASK_VALUES = {"platform_probe", "scan_jobs"}
STATUS_VALUES = {"ready", "partial", "skipped", "error"}
PLATFORM_VALUES = {"boss", "liepin", "job51", "zhilian"}
APPLY_SUPPORT_VALUES = {"manual_only", "manual_confirm", "disabled"}
RISK_VALUES = {"low", "medium", "high"}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def contract_errors(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    task = clean_text(result.get("task"))
    if task not in TASK_VALUES:
        errors.append("task must be platform_probe or scan_jobs")

    if clean_text(result.get("source")) != "china-portal-adapter":
        errors.append("source must equal china-portal-adapter")

    status = clean_text(result.get("scan_status"))
    if status not in STATUS_VALUES:
        errors.append("scan_status must be one of ready, partial, skipped, error")

    session_status = safe_dict(result.get("session_status"))
    if clean_text(session_status.get("mode")) == "":
        errors.append("session_status.mode is required")

    platform_status = safe_dict(result.get("platform_status"))
    for platform, payload in platform_status.items():
        if clean_text(platform) not in PLATFORM_VALUES:
            errors.append(f"unsupported platform in platform_status: {platform}")
        row = safe_dict(payload)
        if clean_text(row.get("discovery")) not in STATUS_VALUES:
            errors.append(f"platform_status.{platform}.discovery must be a valid status")
        if clean_text(row.get("apply_support")) not in APPLY_SUPPORT_VALUES:
            errors.append(f"platform_status.{platform}.apply_support must be manual_only, manual_confirm, or disabled")
        if clean_text(row.get("risk_level")) not in RISK_VALUES:
            errors.append(f"platform_status.{platform}.risk_level must be low, medium, or high")

    jobs = safe_list(result.get("jobs"))
    for index, job in enumerate(jobs):
        row = safe_dict(job)
        job_card = safe_dict(row.get("job_card"))
        if clean_text(job_card.get("job_id")) == "":
            errors.append(f"jobs[{index}].job_card.job_id is required")
        if clean_text(job_card.get("role_title")) == "":
            errors.append(f"jobs[{index}].job_card.role_title is required")
        if clean_text(job_card.get("company")) == "":
            errors.append(f"jobs[{index}].job_card.company is required")
        apply_support = safe_dict(row.get("apply_support"))
        if clean_text(apply_support.get("mode")) not in APPLY_SUPPORT_VALUES:
            errors.append(f"jobs[{index}].apply_support.mode must be manual_only, manual_confirm, or disabled")
        platform_meta = safe_dict(row.get("platform_meta"))
        if clean_text(platform_meta.get("platform")) not in PLATFORM_VALUES:
            errors.append(f"jobs[{index}].platform_meta.platform must be one of the supported platforms")

    if not isinstance(result.get("warnings"), list):
        errors.append("warnings must be a list")

    if clean_text(result.get("generated_at")) == "":
        errors.append("generated_at is required")

    return errors


def validate_adapter_result(result: dict[str, Any]) -> bool:
    return not contract_errors(result)

