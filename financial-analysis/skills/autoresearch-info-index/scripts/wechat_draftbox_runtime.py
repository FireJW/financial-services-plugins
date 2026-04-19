#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import base64
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from publication_contract_runtime import load_publication_contract, validate_publication_contract
from workflow_publication_gate_runtime import build_workflow_publication_gate


REPO_ROOT = Path(__file__).resolve().parents[4]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


def default_request_fn(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_local_wechat_credentials(explicit_path: Any = None) -> dict[str, str]:
    env_paths = []
    request_explicit = clean_text(explicit_path)
    if request_explicit:
        env_paths.append(Path(request_explicit).expanduser())
    explicit = clean_text(os.environ.get("WECHAT_ENV_FILE"))
    if explicit:
        env_paths.append(Path(explicit).expanduser())
    env_paths.append(REPO_ROOT / ".tmp" / "wechat-phase2-dev" / ".env.wechat.local")
    env_paths.append(Path.cwd() / ".tmp" / "wechat-phase2-dev" / ".env.wechat.local")
    env_paths.append(REPO_ROOT / ".env.wechat.local")
    for path in env_paths:
        values = parse_env_file(path)
        app_id = clean_text(values.get("WECHAT_APP_ID") or values.get("WECHAT_APPID"))
        app_secret = clean_text(values.get("WECHAT_APP_SECRET") or values.get("WECHAT_APPSECRET"))
        if app_id and app_secret:
            return {"app_id": app_id, "app_secret": app_secret, "env_file": str(path)}
    return {}


def resolve_wechat_credentials(request: dict[str, Any]) -> dict[str, str]:
    local = load_local_wechat_credentials(request.get("wechat_env_file"))
    if local:
        return local
    app_id = clean_text(request.get("wechat_app_id"))
    app_secret = clean_text(request.get("wechat_app_secret"))
    if app_id or app_secret:
        if not request.get("allow_insecure_inline_credentials"):
            raise ValueError("Inline WeChat credentials are blocked by default")
        if not (app_id and app_secret):
            raise ValueError("Both wechat_app_id and wechat_app_secret are required")
        return {"app_id": app_id, "app_secret": app_secret, "env_file": ""}
    raise ValueError("No usable WeChat credentials were found")


def inspect_wechat_credentials(request: dict[str, Any]) -> dict[str, Any]:
    try:
        credentials = resolve_wechat_credentials(request)
        source = "env_file" if clean_text(credentials.get("env_file")) else "inline_override"
        warning = "inline_override" if source == "inline_override" else ""
        return {"ready": True, "status": "ready", "source": source, "warning": warning, "error_message": ""}
    except Exception as exc:
        return {"ready": False, "status": "missing", "source": "none", "warning": "", "error_message": clean_text(exc)}


def fetch_access_token(app_id: str, app_secret: str, timeout_seconds: int, request_fn=default_request_fn) -> dict[str, Any]:
    url = (
        "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential"
        f"&appid={urllib.parse.quote(app_id)}&secret={urllib.parse.quote(app_secret)}"
    )
    payload = json.loads(request_fn("GET", url, None, {}, timeout_seconds).decode("utf-8"))
    if clean_text(payload.get("access_token")):
        return payload
    raise ValueError(f"{payload.get('errcode', '')} {payload.get('errmsg', 'failed to fetch access token')}".strip())


def parse_wechat_api_payload(raw_bytes: bytes, *, required_field: str = "") -> dict[str, Any]:
    payload = json.loads(raw_bytes.decode("utf-8"))
    if clean_text(payload.get(required_field)) if required_field else False:
        return payload
    errcode = clean_text(payload.get("errcode"))
    errmsg = clean_text(payload.get("errmsg"))
    if errcode or errmsg:
        raise ValueError(f"{errcode} {errmsg}".strip())
    if required_field:
        raise ValueError(f"WeChat API response missing required field: {required_field}")
    return payload


def detect_image_mime_from_bytes(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if data.startswith(b"BM"):
        return "image/bmp", ".bmp"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return "application/octet-stream", ".bin"


def edge_binary_path() -> str:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def convert_image_to_png_for_wechat(file_path: str, *, source_url: str = "", workdir: Path | None = None) -> str:
    resolved = Path(clean_text(file_path)).expanduser()
    if not resolved.exists():
        raise ValueError(f"Local file not found: {resolved}")
    data = resolved.read_bytes()
    mime_type, _ = detect_image_mime_from_bytes(data)
    if mime_type != "image/webp":
        return str(resolved)
    edge_path = edge_binary_path()
    if not edge_path:
        raise ValueError("Microsoft Edge is required to convert unsupported image formats for WeChat upload")
    scratch_root = (workdir or Path.cwd()) / ".tmp" / "wechat-upload-convert"
    scratch_root.mkdir(parents=True, exist_ok=True)
    html_path = scratch_root / f"{resolved.stem}-{uuid.uuid4().hex}.html"
    png_path = scratch_root / f"{resolved.stem}-{uuid.uuid4().hex}.png"
    if clean_text(source_url).startswith(("http://", "https://")):
        image_src = clean_text(source_url)
    else:
        image_src = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
    html = (
        "<!doctype html><html><body style=\"margin:0;display:flex;align-items:center;justify-content:center;background:#fff;\">"
        f"<img src=\"{image_src}\" style=\"max-width:100%;height:auto;\" />"
        "</body></html>"
    )
    html_path.write_text(html, encoding="utf-8")
    command = [
        edge_path,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1200,900",
        f"--screenshot={png_path}",
        str(html_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode != 0:
        raise ValueError(clean_text(completed.stderr or completed.stdout) or "Edge screenshot conversion failed")
    if not png_path.exists():
        raise ValueError("Edge screenshot conversion did not produce a PNG output")
    return str(png_path)


def prepare_wechat_upload_file(asset: dict[str, Any], *, workdir: Path | None = None) -> tuple[Path, str, str]:
    local_path = clean_text(asset.get("local_path"))
    source_url = clean_text(asset.get("source_url"))
    converted_path = Path(convert_image_to_png_for_wechat(local_path, source_url=source_url, workdir=workdir)).expanduser()
    data = converted_path.read_bytes()
    mime_type, default_ext = detect_image_mime_from_bytes(data)
    if mime_type == "application/octet-stream":
        suffix_hint = converted_path.suffix.lower()
        suffix_map = {
            ".png": ("image/png", ".png"),
            ".jpg": ("image/jpeg", ".jpg"),
            ".jpeg": ("image/jpeg", ".jpeg"),
            ".gif": ("image/gif", ".gif"),
            ".bmp": ("image/bmp", ".bmp"),
        }
        if suffix_hint in suffix_map:
            mime_type, default_ext = suffix_map[suffix_hint]
    if mime_type not in {"image/png", "image/jpeg", "image/gif", "image/bmp"}:
        raise ValueError(f"Unsupported WeChat image format: {mime_type or 'unknown'}")
    suffix = converted_path.suffix.lower() or default_ext
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
        suffix = default_ext
    return converted_path, mime_type, suffix


def build_multipart_file_body(file_path: str, *, field_name: str = "media", source_url: str = "", workdir: Path | None = None) -> tuple[bytes, str]:
    asset = {"local_path": file_path, "source_url": source_url}
    resolved, mime_type, suffix = prepare_wechat_upload_file(asset, workdir=workdir)
    if not resolved.exists():
        raise ValueError(f"Local file not found: {resolved}")
    boundary = f"----CodexWechat{uuid.uuid4().hex}"
    stem = resolved.stem
    filename = stem + suffix
    file_bytes = resolved.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def prepare_wechat_browser_session_context(request: dict[str, Any]) -> dict[str, Any]:
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
            "home_url": clean_text(browser_session.get("home_url")) or "https://mp.weixin.qq.com/",
            "editor_url": clean_text(browser_session.get("editor_url")),
            "notes": ["Open a new Edge window with remote debugging enabled."],
        }
    return {"requested": False, "strategy": strategy, "required": False, "active": False, "status": "disabled", "notes": []}


def replace_inline_images(content_html: str, image_assets: list[dict[str, Any]], inline_urls: list[str]) -> str:
    resolved = content_html
    for asset, inline_url in zip(image_assets, inline_urls):
        token = clean_text(asset.get("upload_token"))
        render_src = clean_text(asset.get("render_src"))
        if token:
            resolved = resolved.replace(token, inline_url)
        if render_src.startswith("file://") or render_src.startswith("http://") or render_src.startswith("https://"):
            resolved = resolved.replace(render_src, inline_url)
    resolved = resolved.replace("file://", "")
    return resolved


def build_review_gate(request: dict[str, Any]) -> dict[str, Any]:
    approved = bool(request.get("human_review_approved"))
    return {
        "approved": approved,
        "status": "approved" if approved else "awaiting_human_review",
        "approved_by": clean_text(request.get("human_review_approved_by")),
        "note": clean_text(request.get("human_review_note")),
    }


def build_browser_manifest(publish_package: dict[str, Any], request: dict[str, Any], workdir: Path) -> tuple[Path, dict[str, Any]]:
    browser_dir = workdir / ".tmp" / "wechat-browser-session-push"
    browser_dir.mkdir(parents=True, exist_ok=True)
    cover_path = clean_text(request.get("cover_image_path")) or clean_text(safe_dict(publish_package.get("cover_plan")).get("selected_cover_local_path"))
    if not cover_path:
        cover_path = clean_text((safe_list(publish_package.get("image_assets")) or [{}])[0].get("local_path"))
    manifest = {
        "article": safe_dict(safe_dict(publish_package.get("draftbox_payload_template")).get("articles")) if False else {},
    }
    article = safe_dict((safe_list(safe_dict(publish_package.get("draftbox_payload_template")).get("articles")) or [{}])[0])
    manifest = {
        "article": {
            "title": clean_text(article.get("title")),
            "author": clean_text(article.get("author")),
            "content": clean_text(article.get("content")),
        },
        "cover_image_path": cover_path,
    }
    manifest_path = browser_dir / "manifest.json"
    result_path = browser_dir / "result.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return result_path, {"manifest_path": manifest_path, "result_path": result_path, "manifest": manifest}


def upload_inline_image(access_token: str, asset: dict[str, Any], timeout_seconds: int, request_fn) -> dict[str, Any]:
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={urllib.parse.quote(access_token)}"
    body, boundary = build_multipart_file_body(
        clean_text(asset.get("local_path")),
        source_url=clean_text(asset.get("source_url")),
    )
    payload = parse_wechat_api_payload(
        request_fn("POST", url, body, {"content-type": f"multipart/form-data; boundary={boundary}"}, timeout_seconds),
        required_field="url",
    )
    return {"asset_id": clean_text(asset.get("asset_id")), "inline_url": clean_text(payload.get("url"))}


def upload_cover(access_token: str, publish_package: dict[str, Any], request: dict[str, Any], timeout_seconds: int, request_fn) -> dict[str, Any]:
    cover_plan = safe_dict(publish_package.get("cover_plan"))
    cover_path = clean_text(request.get("cover_image_path")) or clean_text(cover_plan.get("selected_cover_local_path"))
    if not cover_path:
        cover_path = clean_text((safe_list(publish_package.get("image_assets")) or [{}])[0].get("local_path"))
    source_url = clean_text(cover_plan.get("selected_cover_source_url")) or clean_text((safe_list(publish_package.get("image_assets")) or [{}])[0].get("source_url"))
    body, boundary = build_multipart_file_body(cover_path, source_url=source_url)
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={urllib.parse.quote(access_token)}&type=image"
    payload = parse_wechat_api_payload(
        request_fn("POST", url, body, {"content-type": f"multipart/form-data; boundary={boundary}"}, timeout_seconds),
        required_field="media_id",
    )
    return {"media_id": clean_text(payload.get("media_id")), "url": clean_text(payload.get("url"))}


def create_draft(access_token: str, article_payload: dict[str, Any], timeout_seconds: int, request_fn) -> dict[str, Any]:
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={urllib.parse.quote(access_token)}"
    payload = parse_wechat_api_payload(
        request_fn(
            "POST",
            url,
            json.dumps({"articles": [article_payload]}, ensure_ascii=False).encode("utf-8"),
            {"content-type": "application/json"},
            timeout_seconds,
        ),
        required_field="media_id",
    )
    return {"media_id": clean_text(payload.get("media_id"))}


def push_publish_package_to_wechat(
    raw_request: dict[str, Any],
    *,
    request_fn=default_request_fn,
    browser_runner=None,
) -> dict[str, Any]:
    request = safe_dict(raw_request)
    publish_package = load_publication_contract(request)
    validation = validate_publication_contract(publish_package)
    if validation["status"] != "ok":
        raise ValueError(f"Invalid publish_package: missing {validation['missing_fields']}")
    workflow_publication_gate = build_workflow_publication_gate(publish_package)
    review_gate = build_review_gate(request)
    if not review_gate["approved"]:
        return {
            "status": "blocked_review_gate",
            "blocked_reason": "human_review_not_approved",
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "error_message": "Human review approval is required before a real WeChat push.",
        }

    push_backend = clean_text(request.get("push_backend")) or "api"
    timeout_seconds = int(request.get("timeout_seconds", 30) or 30)
    article_payload = deepcopy(safe_dict((safe_list(safe_dict(publish_package.get("draftbox_payload_template")).get("articles")) or [{}])[0]))
    image_assets = [safe_dict(item) for item in safe_list(publish_package.get("image_assets")) if isinstance(item, dict)]

    def run_browser_session() -> dict[str, Any]:
        ready_context = prepare_wechat_browser_session_context(request)
        remote_ready = [
            asset for asset in image_assets if not clean_text(asset.get("source_url") or asset.get("render_src")).startswith(("http://", "https://"))
        ]
        if remote_ready:
            return {
                "status": "blocked_browser_session",
                "blocked_reason": "browser_session_missing_remote_inline_images",
                "missing_remote_inline_asset_ids": [clean_text(item.get("asset_id")) for item in remote_ready],
                "review_gate": review_gate,
                "workflow_publication_gate": workflow_publication_gate,
            }
        result_path, browser_meta = build_browser_manifest(publish_package, request, Path.cwd())
        runner = browser_runner or (lambda manifest_path, session_context, timeout_seconds: {"status": "ok", "draft_media_id": "", "draft_url": ""})
        runner_result = runner(browser_meta["manifest_path"], ready_context, timeout_seconds)
        result_path.write_text(json.dumps(runner_result, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "status": clean_text(runner_result.get("status")) or "ok",
            "push_backend": "browser_session",
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "browser_session": {
                "manifest_path": str(browser_meta["manifest_path"]),
                "result_path": str(result_path),
            },
            "draft_result": {"media_id": clean_text(runner_result.get("draft_media_id")), "url": clean_text(runner_result.get("draft_url"))},
        }

    if push_backend == "browser_session":
        return run_browser_session()

    try:
        credentials = resolve_wechat_credentials(request)
        token_payload = fetch_access_token(credentials["app_id"], credentials["app_secret"], timeout_seconds, request_fn=request_fn)
        access_token = clean_text(token_payload.get("access_token"))
        uploaded_inline_images = [upload_inline_image(access_token, asset, timeout_seconds, request_fn) for asset in image_assets if clean_text(asset.get("local_path"))]
        resolved_html = replace_inline_images(
            clean_text(publish_package.get("content_html")),
            image_assets,
            [clean_text(item.get("inline_url")) for item in uploaded_inline_images],
        )
        uploaded_cover = upload_cover(access_token, publish_package, request, timeout_seconds, request_fn)
        article_payload["thumb_media_id"] = uploaded_cover["media_id"]
        article_payload["content"] = resolved_html
        draft_result = create_draft(access_token, article_payload, timeout_seconds, request_fn)
        return {
            "status": "ok",
            "push_backend": "api",
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "uploaded_inline_images": uploaded_inline_images,
            "uploaded_cover": uploaded_cover,
            "draft_result": draft_result,
            "resolved_content_html": resolved_html,
            "push_readiness": {"status": "ready_for_api_push"},
            "fallback_used": False,
        }
    except Exception as exc:
        if push_backend == "auto":
            browser_result = run_browser_session()
            browser_result["fallback_used"] = True
            browser_result["api_error_message"] = clean_text(exc)
            return browser_result
        raise


__all__ = [
    "REPO_ROOT",
    "build_workflow_publication_gate",
    "default_request_fn",
    "fetch_access_token",
    "inspect_wechat_credentials",
    "load_local_wechat_credentials",
    "prepare_wechat_browser_session_context",
    "push_publish_package_to_wechat",
    "resolve_wechat_credentials",
]
