#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
from pathlib import Path
from typing import Any

from publication_contract_runtime import load_publication_contract, validate_publication_contract


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strip_leading_h1(markdown: str, title: str) -> str:
    text = str(markdown or "").replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines:
        return text
    first = clean_text(lines[0])
    if first.startswith("# "):
        heading = clean_text(first[2:])
        if not title or heading == clean_text(title):
            lines = lines[1:]
            while lines and not clean_text(lines[0]):
                lines = lines[1:]
    return "\n".join(lines).strip()


def image_src_for_toutiao(item: dict[str, Any]) -> str:
    source_url = clean_text(item.get("source_url"))
    if source_url.startswith(("http://", "https://", "data:")):
        return source_url
    local_path = clean_text(item.get("path") or item.get("local_path"))
    if not local_path:
        return ""
    path_obj = Path(local_path).expanduser()
    if not path_obj.exists():
        return ""
    mime_type = mimetypes.guess_type(path_obj.name)[0] or "image/png"
    data = base64.b64encode(path_obj.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def build_review_gate(request: dict[str, Any]) -> dict[str, Any]:
    approved = bool(request.get("human_review_approved"))
    return {
        "approved": approved,
        "status": "approved" if approved else "awaiting_human_review",
        "approved_by": clean_text(request.get("human_review_approved_by")),
        "note": clean_text(request.get("human_review_note")),
    }


def prepare_toutiao_browser_session_context(request: dict[str, Any]) -> dict[str, Any]:
    browser_session = safe_dict(request.get("browser_session"))
    strategy = clean_text(browser_session.get("strategy")) or "disabled"
    if strategy == "remote_debugging":
        return {
            "requested": True,
            "strategy": "remote_debugging",
            "required": bool(browser_session.get("required")),
            "active": False,
            "status": "unavailable",
            "source": "remote_debugging",
            "cdp_endpoint": clean_text(browser_session.get("cdp_endpoint")) or "http://127.0.0.1:9222",
            "browser_name": "edge",
            "wait_ms": int(browser_session.get("wait_ms", 8000) or 8000),
            "home_url": clean_text(browser_session.get("home_url")) or "https://mp.toutiao.com/",
            "editor_url": clean_text(browser_session.get("editor_url")),
            "notes": ["Open a new Edge window with remote debugging enabled."],
        }
    return {"requested": False, "strategy": strategy, "required": False, "active": False, "status": "disabled", "notes": []}


def build_toutiao_article_browser_manifest(
    publish_package: dict[str, Any],
    request: dict[str, Any],
    workdir: Path,
) -> tuple[Path, dict[str, Any]]:
    browser_dir = workdir / ".tmp" / "toutiao-article-browser-session-push"
    browser_dir.mkdir(parents=True, exist_ok=True)
    title = clean_text(publish_package.get("title"))
    body_markdown = strip_leading_h1(str(publish_package.get("content_markdown") or ""), title)
    selected_images = [safe_dict(item) for item in safe_list(publish_package.get("selected_images")) if isinstance(item, dict)]
    inline_images = []
    for item in selected_images:
        inline_src = image_src_for_toutiao(item)
        if not inline_src:
            continue
        inline_images.append(
            {
                "asset_id": clean_text(item.get("asset_id") or item.get("image_id")),
                "placement": clean_text(item.get("placement")) or "after_lede",
                "caption": clean_text(item.get("caption")),
                "src": inline_src,
            }
        )
    cover_plan = safe_dict(publish_package.get("cover_plan"))
    cover_image_path = clean_text(cover_plan.get("selected_cover_local_path"))
    manifest = {
        "title": title,
        "subtitle": clean_text(publish_package.get("subtitle")),
        "body_markdown": body_markdown,
        "selected_images": selected_images,
        "inline_images": inline_images,
        "cover_plan": cover_plan,
        "cover_image_path": cover_image_path,
        "platform_hints": safe_dict(publish_package.get("platform_hints")),
        "operator_notes": [clean_text(item) for item in safe_list(publish_package.get("operator_notes")) if clean_text(item)],
        "save_mode": clean_text(request.get("save_mode")) or "draft",
    }
    manifest_path = browser_dir / "manifest.json"
    result_path = browser_dir / "result.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return result_path, {"manifest_path": manifest_path, "result_path": result_path, "manifest": manifest}


def run_toutiao_article_browser_session(manifest_path: Path, session_context: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    script_path = Path(__file__).resolve().with_name("toutiao_article_browser_session_push.js")
    command = [
        "node",
        str(script_path),
        "--manifest",
        str(manifest_path),
        "--endpoint",
        clean_text(session_context.get("cdp_endpoint")) or "http://127.0.0.1:9222",
        "--wait-ms",
        str(int(session_context.get("wait_ms", timeout_seconds * 1000) or timeout_seconds * 1000)),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=max(timeout_seconds, 30))
    raw_output = clean_text(completed.stdout) or clean_text(completed.stderr)
    if completed.returncode != 0:
        raise ValueError(raw_output or "Toutiao browser-session push failed")
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(raw_output or f"Invalid Toutiao browser-session response: {exc}") from exc


def push_publish_package_to_toutiao(
    raw_request: dict[str, Any],
    *,
    browser_runner=None,
) -> dict[str, Any]:
    request = safe_dict(raw_request)
    publish_package = load_publication_contract(request)
    validation = validate_publication_contract(publish_package)
    if validation["status"] != "ok":
        raise ValueError(f"Invalid publish_package: missing {validation['missing_fields']}")

    review_gate = build_review_gate(request)
    if not review_gate["approved"]:
        return {
            "status": "blocked_review_gate",
            "blocked_reason": "human_review_not_approved",
            "push_backend": "browser_session",
            "review_gate": review_gate,
            "error_message": "Human review approval is required before a real Toutiao push.",
        }

    push_backend = clean_text(request.get("push_backend")) or "browser_session"
    timeout_seconds = int(request.get("timeout_seconds", 30) or 30)

    if push_backend in {"browser_session", "auto"}:
        session_context = prepare_toutiao_browser_session_context(request)
        result_path, browser_meta = build_toutiao_article_browser_manifest(publish_package, request, Path.cwd())
        runner = browser_runner or run_toutiao_article_browser_session
        runner_result = runner(browser_meta["manifest_path"], session_context, timeout_seconds)
        result_path.write_text(json.dumps(runner_result, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "status": clean_text(runner_result.get("status")) or "ok",
            "push_backend": "browser_session",
            "review_gate": review_gate,
            "browser_session": {
                "manifest_path": str(browser_meta["manifest_path"]),
                "result_path": str(result_path),
            },
            "article_url": clean_text(runner_result.get("article_url")),
            "title": clean_text(publish_package.get("title")),
        }

    return {
        "status": "error",
        "push_backend": push_backend,
        "review_gate": review_gate,
        "error_message": f"Push backend '{push_backend}' is not yet supported for Toutiao long-form. Use 'browser_session' or 'auto'.",
    }


__all__ = ["push_publish_package_to_toutiao", "prepare_toutiao_browser_session_context", "run_toutiao_article_browser_session"]
