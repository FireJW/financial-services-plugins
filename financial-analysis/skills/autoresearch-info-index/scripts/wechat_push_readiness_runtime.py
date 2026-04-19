#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

from article_publish_runtime import build_push_readiness
from news_index_runtime import write_json
from publication_contract_runtime import load_publication_contract, validate_publication_contract
from wechat_draftbox_runtime import (
    build_workflow_publication_gate,
    default_request_fn,
    fetch_access_token,
    inspect_wechat_credentials,
    resolve_wechat_credentials,
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    publish_package = load_publication_contract(payload)
    if not publish_package:
        raise ValueError("wechat push readiness audit requires publish_package or publish_package_path")
    validation = validate_publication_contract(publish_package)
    if validation["status"] != "ok":
        raise ValueError(f"Invalid publish_package: missing {validation['missing_fields']}")

    return {
        "publish_package": publish_package,
        "cover_image_path": clean_text(payload.get("cover_image_path")),
        "cover_image_url": clean_text(payload.get("cover_image_url")),
        "human_review_approved": bool(payload.get("human_review_approved")),
        "human_review_approved_by": clean_text(payload.get("human_review_approved_by") or payload.get("reviewed_by")),
        "human_review_note": clean_text(payload.get("human_review_note") or payload.get("review_note")),
        "validate_live_auth": bool(payload.get("validate_live_auth")),
        "wechat_env_file": clean_text(payload.get("wechat_env_file") or payload.get("env_file_path")),
        "wechat_app_id": clean_text(payload.get("wechat_app_id") or payload.get("app_id")),
        "wechat_app_secret": clean_text(payload.get("wechat_app_secret") or payload.get("app_secret")),
        "allow_insecure_inline_credentials": bool(payload.get("allow_insecure_inline_credentials")),
        "timeout_seconds": int(payload.get("timeout_seconds", 30) or 30),
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    push_readiness = safe_dict(result.get("push_readiness"))
    credential_check = safe_dict(result.get("credential_check"))
    live_auth = safe_dict(result.get("live_auth_check"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    workflow_manual_review = safe_dict(workflow_publication_gate.get("manual_review"))
    blockers = safe_list(result.get("blockers"))
    warnings = safe_list(result.get("warnings"))
    lines = [
        "# WeChat Push Readiness Audit",
        "",
        f"- Readiness level: {clean_text(result.get('readiness_level'))}",
        f"- Ready for real push: {'yes' if result.get('ready_for_real_push') else 'no'}",
        f"- Push readiness status: {clean_text(push_readiness.get('status')) or 'unknown'}",
        f"- Credential status: {clean_text(credential_check.get('status')) or 'unknown'}",
        f"- Credential source: {clean_text(credential_check.get('source')) or 'unknown'}",
        f"- Human review approved: {'yes' if result.get('human_review_approved') else 'no'}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {clean_text(item)}" for item in blockers)
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend(f"- {clean_text(item)}" for item in warnings)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Workflow Publication Gate",
            "",
            f"- Publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness')) or 'ready'}",
            f"- Reddit operator review: {clean_text(workflow_manual_review.get('status')) or 'not_required'}",
            f"- Required items: {int(workflow_manual_review.get('required_count', 0) or 0)}",
            f"- High-priority items: {int(workflow_manual_review.get('high_priority_count', 0) or 0)}",
            f"- Next step: {clean_text(workflow_manual_review.get('next_step')) or 'none'}",
            "",
            "## Live Auth",
            "",
            f"- Status: {clean_text(live_auth.get('status')) or 'not_run'}",
            f"- Message: {clean_text(live_auth.get('message')) or 'none'}",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def run_wechat_push_readiness_audit(
    raw_payload: dict[str, Any],
    *,
    request_fn=default_request_fn,
) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    publish_package = safe_dict(request.get("publish_package"))
    workflow_publication_gate = build_workflow_publication_gate(publish_package)
    push_readiness = build_push_readiness(
        request,
        clean_text(publish_package.get("content_html")),
        safe_dict(publish_package.get("draftbox_payload_template")),
        safe_list(publish_package.get("image_assets")),
        safe_dict(publish_package.get("cover_plan")),
    )
    credential_check = inspect_wechat_credentials(request)

    blockers: list[str] = []
    warnings: list[str] = []
    if not request["human_review_approved"]:
        blockers.append("Human review approval is still required before a real WeChat push.")
    if not push_readiness.get("ready_for_api_push"):
        blockers.append(clean_text(push_readiness.get("next_step")) or "Resolve push readiness blockers first.")
    if not credential_check.get("ready"):
        blockers.append(clean_text(credential_check.get("error_message")) or "Configure WeChat credentials before pushing.")
    elif credential_check.get("warning"):
        warnings.append("Credentials are usable, but they currently rely on an insecure inline override.")

    live_auth_check = {"status": "not_run", "message": "Live auth was not requested."}
    if request["validate_live_auth"]:
        if not credential_check.get("ready"):
            live_auth_check = {
                "status": "skipped_missing_credentials",
                "message": "Live auth was skipped because credentials are not ready.",
            }
        else:
            try:
                credentials = resolve_wechat_credentials(request)
                fetch_access_token(
                    clean_text(credentials.get("app_id")),
                    clean_text(credentials.get("app_secret")),
                    request["timeout_seconds"],
                    request_fn,
                )
                live_auth_check = {"status": "ok", "message": "Successfully fetched a live WeChat access token."}
            except Exception as exc:  # pragma: no cover - surfaced by tests through fake request_fn
                blockers.append(f"Live WeChat auth failed: {exc}")
                live_auth_check = {"status": "error", "message": clean_text(exc)}

    readiness_level = "ready"
    if blockers:
        readiness_level = "blocked"
    elif warnings:
        readiness_level = "warning"

    result = {
        "status": "ok",
        "workflow_kind": "wechat_push_readiness_audit",
        "readiness_level": readiness_level,
        "ready_for_real_push": readiness_level == "ready",
        "human_review_approved": request["human_review_approved"],
        "human_review_approved_by": request["human_review_approved_by"],
        "workflow_publication_gate": workflow_publication_gate,
        "push_readiness": push_readiness,
        "credential_check": credential_check,
        "live_auth_check": live_auth_check,
        "blockers": blockers,
        "warnings": warnings,
    }
    result["report_markdown"] = build_report_markdown(result)
    return result


__all__ = ["run_wechat_push_readiness_audit", "write_json"]
