#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from article_publish_runtime import (
    build_automatic_acceptance_markdown,
    build_automatic_acceptance_result,
    build_regression_checks,
    clean_text,
    safe_dict,
)
from wechat_draftbox_runtime import build_workflow_publication_gate


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def resolve_artifact_path(raw_value: Any, base_dir: Path) -> Path | None:
    path_text = clean_text(raw_value)
    if not path_text:
        return None
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def resolve_publish_artifacts(target: Any) -> dict[str, str]:
    target_path = Path(clean_text(target)).expanduser()
    if not clean_text(target):
        raise ValueError("publish regression check requires a target output directory or JSON artifact path")

    if target_path.is_dir():
        output_dir = target_path.resolve()
        publish_package_path = output_dir / "publish-package.json"
        draft_result_path = output_dir / "workflow" / "article-draft-result.json"
        publish_result_path = output_dir / "article-publish-result.json"
        return {
            "output_dir": str(output_dir),
            "publish_package_path": str(publish_package_path),
            "draft_result_path": str(draft_result_path),
            "publish_result_path": str(publish_result_path),
        }

    resolved_target = target_path.resolve()
    if resolved_target.name == "publish-package.json":
        output_dir = resolved_target.parent
        return {
            "output_dir": str(output_dir),
            "publish_package_path": str(resolved_target),
            "draft_result_path": str(output_dir / "workflow" / "article-draft-result.json"),
            "publish_result_path": str(output_dir / "article-publish-result.json"),
        }

    result_payload = load_json_file(resolved_target)
    output_dir = resolved_target.parent
    publish_package_path = resolve_artifact_path(result_payload.get("publish_package_path"), output_dir) or (output_dir / "publish-package.json")
    draft_result_path = resolve_artifact_path(safe_dict(result_payload.get("workflow_stage")).get("draft_result_path"), output_dir)
    if draft_result_path is None:
        draft_result_path = output_dir / "workflow" / "article-draft-result.json"
    return {
        "output_dir": str(output_dir),
        "publish_package_path": str(publish_package_path),
        "draft_result_path": str(draft_result_path),
        "publish_result_path": str(resolved_target),
    }


def run_publish_regression_check(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = deepcopy(safe_dict(raw_payload))
    artifacts = resolve_publish_artifacts(request.get("target") or request.get("input") or request.get("output_dir"))
    publish_package_path = Path(artifacts["publish_package_path"])
    draft_result_path = Path(artifacts["draft_result_path"])
    publish_package = load_json_file(publish_package_path)
    if not publish_package:
        raise ValueError(f"publish regression check could not load publish package: {publish_package_path}")
    workflow_publication_gate = build_workflow_publication_gate(publish_package)

    regression_checks = safe_dict(publish_package.get("regression_checks"))
    regression_source = "publish_package"
    if not regression_checks:
        draft_result = load_json_file(draft_result_path)
        article_package = safe_dict(draft_result.get("article_package"))
        draft_request = safe_dict(draft_result.get("request"))
        if not article_package or not draft_request:
            raise ValueError(
                "publish regression check requires publish_package.regression_checks or a workflow/article-draft-result.json fallback"
            )
        regression_checks = build_regression_checks(
            article_package,
            draft_request,
            safe_dict(publish_package.get("cover_plan")),
            safe_dict(publish_package.get("push_readiness")),
        )
        regression_source = "workflow_draft_fallback"

    result = build_automatic_acceptance_result(
        regression_checks,
        target=clean_text(request.get("target") or request.get("input") or request.get("output_dir")),
        output_dir=artifacts["output_dir"],
        regression_source=regression_source,
        extra_metadata={
            "publish_package_path": artifacts["publish_package_path"],
            "draft_result_path": artifacts["draft_result_path"],
            "publish_result_path": artifacts["publish_result_path"],
            "workflow_publication_gate": workflow_publication_gate,
        },
    )
    result["report_markdown"] = build_automatic_acceptance_markdown(result)
    return result


__all__ = ["resolve_publish_artifacts", "run_publish_regression_check"]
