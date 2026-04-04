#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import tempfile
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from typing import Any, Callable

from article_workflow_runtime import load_json
from news_index_runtime import safe_dict, safe_list
from workflow_publication_gate_runtime import build_workflow_publication_gate


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


RequestFn = Callable[[str, str, bytes | None, dict[str, str], int], bytes]
DownloadFn = Callable[[str, int], bytes]
BrowserRunner = Callable[[Path, dict[str, Any], int], dict[str, Any]]
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOCAL_SECRET_FILES = [
    ".env.wechat.local",
    ".tmp/wechat-phase2-dev/.env.wechat.local",
]


def parse_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    lowered = clean_text(value).lower()
    if lowered in {"1", "true", "yes", "y", "on", "approved"}:
        return True
    if lowered in {"0", "false", "no", "n", "off", "rejected"}:
        return False
    return default


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = clean_text(key).lstrip("\ufeff")
        if not clean_key:
            continue
        clean_value = value.strip().strip('"').strip("'")
        values[clean_key] = clean_value
    return values


def iter_wechat_env_candidate_paths(payload: dict[str, Any] | None = None) -> list[Path]:
    candidate_paths: list[Path] = []
    raw_payload = payload or {}

    explicit_paths = [
        clean_text(os.environ.get("WECHAT_ENV_FILE")),
        clean_text(os.environ.get("WECHAT_ENV_PATH")),
        clean_text(raw_payload.get("wechat_env_file")),
        clean_text(raw_payload.get("wechat_env_path")),
        clean_text(raw_payload.get("env_file_path")),
    ]
    for explicit_path in explicit_paths:
        if explicit_path:
            candidate_paths.append(Path(explicit_path).expanduser().resolve())

    cwd = Path.cwd().resolve()
    candidate_paths.append((cwd / ".env.wechat.local").resolve())
    for relative_path in DEFAULT_LOCAL_SECRET_FILES:
        candidate_paths.append((REPO_ROOT / relative_path).resolve())
    return candidate_paths


def load_local_wechat_credentials(payload: dict[str, Any] | None = None) -> dict[str, str]:
    candidate_paths = iter_wechat_env_candidate_paths(payload)

    seen_paths: set[Path] = set()
    for candidate_path in candidate_paths:
        if candidate_path in seen_paths:
            continue
        seen_paths.add(candidate_path)
        if not candidate_path.exists() or not candidate_path.is_file():
            continue
        values = parse_env_file(candidate_path)
        app_id = clean_text(values.get("WECHAT_APP_ID") or values.get("WECHAT_APPID"))
        app_secret = clean_text(values.get("WECHAT_APP_SECRET") or values.get("WECHAT_APPSECRET"))
        if app_id and app_secret:
            return {"app_id": app_id, "app_secret": app_secret, "source": str(candidate_path)}
    return {}


def mask_config_value(value: Any, *, prefix: int = 2, suffix: int = 2) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if len(text) <= prefix + suffix:
        return "*" * len(text)
    return f"{text[:prefix]}{'*' * max(1, len(text) - prefix - suffix)}{text[-suffix:]}"


def resolve_credential_state(payload: dict[str, Any]) -> dict[str, Any]:
    env_app_id = clean_text(os.environ.get("WECHAT_APP_ID") or os.environ.get("WECHAT_APPID"))
    env_app_secret = clean_text(os.environ.get("WECHAT_APP_SECRET") or os.environ.get("WECHAT_APPSECRET"))
    if env_app_id and env_app_secret:
        return {
            "ready": True,
            "warning": False,
            "status": "ready",
            "source": "environment",
            "source_path": "",
            "app_id": env_app_id,
            "app_secret": env_app_secret,
            "masked_app_id": mask_config_value(env_app_id, prefix=4, suffix=4),
            "error_message": "",
            "next_step": "Credentials are available from environment variables.",
        }

    file_credentials = load_local_wechat_credentials(payload)
    if file_credentials:
        app_id = clean_text(file_credentials.get("app_id"))
        app_secret = clean_text(file_credentials.get("app_secret"))
        return {
            "ready": True,
            "warning": False,
            "status": "ready",
            "source": "env_file",
            "source_path": clean_text(file_credentials.get("source")),
            "app_id": app_id,
            "app_secret": app_secret,
            "masked_app_id": mask_config_value(app_id, prefix=4, suffix=4),
            "error_message": "",
            "next_step": "Credentials are available from the local env file.",
        }

    inline_app_id = clean_text(payload.get("wechat_app_id") or payload.get("app_id"))
    inline_app_secret = clean_text(payload.get("wechat_app_secret") or payload.get("app_secret"))
    allow_inline = parse_bool(payload.get("allow_insecure_inline_credentials"), default=False)
    if inline_app_id or inline_app_secret:
        if not allow_inline:
            error_message = (
                "Inline WeChat credentials are blocked by default. Set WECHAT_APP_ID/WECHAT_APP_SECRET "
                "in the environment, point WECHAT_ENV_FILE to a local secret file, or create .env.wechat.local. "
                "Only use allow_insecure_inline_credentials=true "
                "for isolated one-off runs you will never commit."
            )
            return {
                "ready": False,
                "warning": False,
                "status": "blocked_inline_credentials",
                "source": "inline",
                "source_path": "",
                "app_id": inline_app_id,
                "app_secret": inline_app_secret,
                "masked_app_id": mask_config_value(inline_app_id, prefix=4, suffix=4),
                "error_message": error_message,
                "next_step": "Move the credentials into WECHAT_APP_ID/WECHAT_APP_SECRET, WECHAT_ENV_FILE, or .env.wechat.local.",
            }
        if not inline_app_id or not inline_app_secret:
            return {
                "ready": False,
                "warning": False,
                "status": "incomplete_inline_credentials",
                "source": "inline",
                "source_path": "",
                "app_id": inline_app_id,
                "app_secret": inline_app_secret,
                "masked_app_id": mask_config_value(inline_app_id, prefix=4, suffix=4),
                "error_message": "Inline WeChat credentials are incomplete. Both app_id and app_secret are required.",
                "next_step": "Provide both WECHAT_APP_ID and WECHAT_APP_SECRET, or remove the partial inline override.",
            }
        return {
            "ready": True,
            "warning": True,
            "status": "warning_insecure_inline",
            "source": "inline",
            "source_path": "",
            "app_id": inline_app_id,
            "app_secret": inline_app_secret,
            "masked_app_id": mask_config_value(inline_app_id, prefix=4, suffix=4),
            "error_message": "",
            "next_step": "Inline credentials are usable, but move them into env vars or .env.wechat.local before normal operation.",
        }

    return {
        "ready": False,
        "warning": False,
        "status": "missing_credentials",
        "source": "none",
        "source_path": "",
        "app_id": "",
        "app_secret": "",
        "masked_app_id": "",
        "error_message": (
            "Missing WeChat credentials. Set WECHAT_APP_ID/WECHAT_APP_SECRET in the environment, "
            "point WECHAT_ENV_FILE to a local secret file, or create .env.wechat.local."
        ),
        "next_step": "Set WECHAT_APP_ID/WECHAT_APP_SECRET, WECHAT_ENV_FILE, or create an untracked .env.wechat.local file.",
    }


def inspect_wechat_credentials(payload: dict[str, Any]) -> dict[str, Any]:
    state = resolve_credential_state(payload)
    return {
        "ready": state["ready"],
        "warning": state["warning"],
        "status": state["status"],
        "source": state["source"],
        "source_path": state["source_path"],
        "masked_app_id": state["masked_app_id"],
        "app_secret_configured": bool(state.get("app_secret")),
        "inline_credentials_blocked_by_default": True,
        "error_message": state["error_message"],
        "next_step": state["next_step"],
    }


def default_request_fn(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def default_download_fn(url: str, timeout_seconds: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def parse_json_response(raw_bytes: bytes, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{context} returned non-JSON content") from exc
    errcode = payload.get("errcode")
    if errcode not in (None, 0, "0"):
        errmsg = clean_text(payload.get("errmsg")) or "unknown WeChat error"
        raise ValueError(f"{context} failed: errcode={errcode} errmsg={errmsg}")
    return payload


def encode_multipart_formdata(
    *,
    fields: dict[str, str] | None = None,
    file_field: str,
    filename: str,
    content_bytes: bytes,
    content_type: str | None = None,
) -> tuple[bytes, str]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    lines: list[bytes] = []
    for key, value in (fields or {}).items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        lines.append(str(value).encode("utf-8"))
        lines.append(b"\r\n")
    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    lines.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    lines.append(content_bytes)
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


def sanitize_filename(filename: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in clean_text(filename))
    return cleaned or fallback


def resolve_wechat_credentials(payload: dict[str, Any]) -> dict[str, str]:
    state = resolve_credential_state(payload)
    if not state["ready"]:
        raise ValueError(state["error_message"])
    return {
        "app_id": clean_text(state.get("app_id")),
        "app_secret": clean_text(state.get("app_secret")),
        "source": clean_text(state.get("source")),
        "source_path": clean_text(state.get("source_path")),
    }


def resolve_human_review_gate(payload: dict[str, Any]) -> dict[str, Any]:
    approved = parse_bool(payload.get("human_review_approved"), default=False)
    approved_by = clean_text(payload.get("human_review_approved_by") or payload.get("reviewed_by"))
    approval_note = clean_text(payload.get("human_review_note") or payload.get("review_note"))
    status = "approved" if approved else "awaiting_human_review"
    return {
        "required": True,
        "approved": approved,
        "status": status,
        "approved_by": approved_by,
        "approved_at": datetime.now(UTC).isoformat() if approved else "",
        "approval_note": approval_note,
        "next_step": (
            "Review the generated draft package and re-run with human_review_approved=true once the article is ready to push."
            if not approved
            else "Human review gate is satisfied."
        ),
    }


def resolve_push_backend(payload: dict[str, Any]) -> str:
    backend = clean_text(payload.get("push_backend") or payload.get("wechat_push_backend") or "api").lower()
    if backend in {"api", "browser_session", "auto"}:
        return backend
    return "api"


def normalize_browser_session_request(payload: dict[str, Any]) -> dict[str, Any]:
    browser_session_raw = payload.get("browser_session") if isinstance(payload.get("browser_session"), dict) else {}
    inferred_strategy = ""
    if clean_text(browser_session_raw.get("cdp_endpoint") or payload.get("browser_debug_endpoint")):
        inferred_strategy = "remote_debugging"
    return {
        "strategy": clean_text(
            browser_session_raw.get("strategy")
            or payload.get("browser_session_strategy")
            or inferred_strategy
        ),
        "required": parse_bool(browser_session_raw.get("required", payload.get("browser_session_required")), default=False),
        "cdp_endpoint": clean_text(browser_session_raw.get("cdp_endpoint") or payload.get("browser_debug_endpoint") or "http://127.0.0.1:9222"),
        "browser_name": clean_text(browser_session_raw.get("browser_name") or payload.get("browser_name") or "edge"),
        "wait_ms": max(1000, parse_int(browser_session_raw.get("wait_ms", payload.get("browser_wait_ms")), 8000)),
        "home_url": clean_text(browser_session_raw.get("home_url") or payload.get("browser_home_url") or "https://mp.weixin.qq.com/"),
        "editor_url": clean_text(browser_session_raw.get("editor_url") or payload.get("browser_editor_url")),
    }


def resolve_node_command() -> str | None:
    candidates = [
        clean_text(os.environ.get("NODE_EXE")),
        "D:\\nodejs\\node.exe",
        "C:\\Program Files\\nodejs\\node.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return which("node")


def resolve_wechat_browser_push_script() -> Path | None:
    candidate = SCRIPT_DIR / "wechat_browser_session_push.js"
    return candidate if candidate.exists() else None


def probe_cdp_endpoint(endpoint: str) -> tuple[bool, str]:
    normalized_endpoint = clean_text(endpoint).rstrip("/")
    if not normalized_endpoint:
        return False, "browser_session.cdp_endpoint was not provided"
    version_url = f"{normalized_endpoint}/json/version"
    try:
        request = urllib.request.Request(version_url, headers={"User-Agent": "Codex-WeChatPush/1.0"})
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore") or "{}")
        browser_name = clean_text(payload.get("Browser"))
        return True, browser_name or version_url
    except Exception as exc:  # pragma: no cover - exact transport failure varies by host
        return False, clean_text(exc) or "endpoint probe failed"


def prepare_wechat_browser_session_context(payload: dict[str, Any]) -> dict[str, Any]:
    session_request = normalize_browser_session_request(payload)
    strategy = clean_text(session_request.get("strategy"))
    context = {
        "requested": bool(strategy),
        "strategy": strategy,
        "required": bool(session_request.get("required")),
        "active": False,
        "status": "disabled" if not strategy else "unavailable",
        "source": "",
        "cdp_endpoint": clean_text(session_request.get("cdp_endpoint")),
        "browser_name": clean_text(session_request.get("browser_name")),
        "wait_ms": int(session_request.get("wait_ms", 8000) or 8000),
        "home_url": clean_text(session_request.get("home_url")),
        "editor_url": clean_text(session_request.get("editor_url")),
        "notes": [],
    }
    if not strategy:
        return context
    if strategy != "remote_debugging":
        context["notes"] = [f"unsupported browser session strategy: {strategy}"]
        return context

    node_cmd = resolve_node_command()
    script_path = resolve_wechat_browser_push_script()
    endpoint = clean_text(session_request.get("cdp_endpoint"))
    notes: list[str] = []
    endpoint_reachable = False
    if not node_cmd:
        notes.append("node runtime not found for browser-session helper")
    if not script_path:
        notes.append("wechat_browser_session_push.js helper is missing")
    if not endpoint:
        notes.append("browser_session.cdp_endpoint was not provided")
    if node_cmd and script_path and endpoint:
        endpoint_reachable, endpoint_detail = probe_cdp_endpoint(endpoint)
        if not endpoint_reachable:
            notes.append(f"remote debugging endpoint is not reachable: {endpoint_detail}")
            notes.append("Launch a signed-in Edge/Chrome window with remote debugging before using the browser fallback.")

    context.update(
        {
            "active": bool(node_cmd and script_path and endpoint and endpoint_reachable),
            "status": "ready" if node_cmd and script_path and endpoint and endpoint_reachable else "unavailable",
            "source": "remote_debugging",
            "notes": notes or [f"will attach to {endpoint}"],
        }
    )
    return context


def choose_browser_remote_image_url(asset: dict[str, Any]) -> str:
    for candidate in [
        clean_text(asset.get("source_url")),
        clean_text(asset.get("render_src")),
    ]:
        if candidate.startswith(("http://", "https://", "data:image/")):
            return candidate
    return ""


def rewrite_content_images_for_browser_session(
    content_html: str,
    image_assets: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    resolved = content_html
    unresolved_asset_ids: list[str] = []
    for index, asset in enumerate(image_assets, start=1):
        asset_id = clean_text(asset.get("asset_id")) or f"asset-{index:02d}"
        remote_url = choose_browser_remote_image_url(asset)
        local_path = clean_text(asset.get("local_path"))
        local_uri = ""
        if local_path:
            try:
                local_uri = Path(local_path).expanduser().resolve().as_uri()
            except OSError:
                local_uri = ""
        references = [
            clean_text(asset.get("render_src")),
            clean_text(asset.get("upload_token")),
            clean_text(asset.get("source_url")),
            local_path,
            local_uri,
        ]
        if remote_url:
            for candidate in references:
                if candidate:
                    resolved = resolved.replace(candidate, remote_url)
            continue
        if any(candidate and candidate in content_html for candidate in references):
            unresolved_asset_ids.append(asset_id)
    return resolved, unresolved_asset_ids


def resolve_browser_session_output_dir(payload: dict[str, Any]) -> Path:
    explicit = clean_text(payload.get("browser_session_output_dir"))
    if explicit:
        return Path(explicit).expanduser().resolve()
    publish_package_path = clean_text(payload.get("publish_package_path"))
    if publish_package_path:
        return (Path(publish_package_path).expanduser().resolve().parent / "browser-session-push").resolve()
    output_dir = clean_text(payload.get("output_dir"))
    if output_dir:
        return (Path(output_dir).expanduser().resolve() / "browser-session-push").resolve()
    return (REPO_ROOT / ".tmp" / "wechat-browser-session-push").resolve()


def default_browser_session_push_runner(
    manifest_path: Path,
    session_context: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    node_cmd = resolve_node_command()
    script_path = resolve_wechat_browser_push_script()
    if not node_cmd or not script_path:
        raise ValueError("browser-session helper prerequisites are missing")

    command = [
        node_cmd,
        str(script_path),
        "--manifest",
        str(manifest_path),
        "--endpoint",
        clean_text(session_context.get("cdp_endpoint")),
        "--wait-ms",
        str(max(1000, parse_int(session_context.get("wait_ms"), 8000))),
    ]
    process = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
        timeout=max(30, timeout_seconds * 4),
    )
    stdout_text = clean_text(process.stdout)
    stderr_text = clean_text(process.stderr)
    if process.returncode != 0:
        raise ValueError(stderr_text or stdout_text or "browser-session helper failed")
    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("browser-session helper returned non-JSON content") from exc
    if clean_text(payload.get("status")) not in {"ok", "saved"}:
        message = clean_text(payload.get("message")) or stderr_text or stdout_text or "browser-session push failed"
        raise ValueError(message)
    return payload


def fetch_access_token(app_id: str, app_secret: str, timeout_seconds: int, request_fn: RequestFn) -> str:
    url = (
        "https://api.weixin.qq.com/cgi-bin/token?"
        f"grant_type=client_credential&appid={urllib.parse.quote(app_id)}&secret={urllib.parse.quote(app_secret)}"
    )
    payload = parse_json_response(request_fn("GET", url, None, {}, timeout_seconds), "fetch access_token")
    access_token = clean_text(payload.get("access_token"))
    if not access_token:
        raise ValueError("fetch access_token succeeded but access_token was empty")
    return access_token


def resolve_binary_from_reference(
    *,
    local_path: str,
    remote_url: str,
    fallback_name: str,
    timeout_seconds: int,
    download_fn: DownloadFn,
) -> tuple[bytes, str]:
    if local_path:
        file_path = Path(local_path).expanduser().resolve()
        if not file_path.exists():
            raise ValueError(f"Local image path does not exist: {file_path}")
        return file_path.read_bytes(), sanitize_filename(file_path.name, fallback_name)
    if remote_url.startswith("http://") or remote_url.startswith("https://"):
        try:
            raw_bytes = download_fn(remote_url, timeout_seconds)
        except urllib.error.URLError as exc:
            raise ValueError(f"Failed to download remote image: {remote_url}") from exc
        suffix = Path(urllib.parse.urlparse(remote_url).path).suffix or ".bin"
        return raw_bytes, sanitize_filename(fallback_name + suffix, fallback_name)
    raise ValueError("No usable local_path or remote_url was available for image upload")


def upload_inline_image(access_token: str, image_bytes: bytes, filename: str, timeout_seconds: int, request_fn: RequestFn) -> str:
    body, content_type = encode_multipart_formdata(file_field="media", filename=filename, content_bytes=image_bytes)
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={urllib.parse.quote(access_token)}"
    payload = parse_json_response(
        request_fn("POST", url, body, {"Content-Type": content_type}, timeout_seconds),
        "upload inline image",
    )
    image_url = clean_text(payload.get("url"))
    if not image_url:
        raise ValueError("upload inline image succeeded but returned no url")
    return image_url


def upload_cover_material(access_token: str, image_bytes: bytes, filename: str, timeout_seconds: int, request_fn: RequestFn) -> dict[str, str]:
    body, content_type = encode_multipart_formdata(file_field="media", filename=filename, content_bytes=image_bytes)
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={urllib.parse.quote(access_token)}&type=image"
    payload = parse_json_response(
        request_fn("POST", url, body, {"Content-Type": content_type}, timeout_seconds),
        "upload cover material",
    )
    media_id = clean_text(payload.get("media_id"))
    if not media_id:
        raise ValueError("upload cover material succeeded but returned no media_id")
    return {"media_id": media_id, "url": clean_text(payload.get("url"))}


def replace_content_images(content_html: str, image_assets: list[dict[str, Any]], uploaded_urls: dict[str, str]) -> str:
    resolved = content_html
    for asset in image_assets:
        asset_id = clean_text(asset.get("asset_id"))
        upload_url = clean_text(uploaded_urls.get(asset_id))
        if not asset_id or not upload_url:
            continue
        for candidate in [clean_text(asset.get("render_src")), clean_text(asset.get("upload_token")), clean_text(asset.get("source_url"))]:
            if candidate:
                resolved = resolved.replace(candidate, upload_url)
    return resolved


def build_articles_payload(template: dict[str, Any], content_html: str, thumb_media_id: str, author: str, show_cover_pic: int) -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    for item in safe_list(template.get("articles")):
        article = {
            "title": clean_text(item.get("title")),
            "author": clean_text(item.get("author")) or author,
            "digest": clean_text(item.get("digest")),
            "content": content_html,
            "content_source_url": clean_text(item.get("content_source_url")),
            "thumb_media_id": thumb_media_id,
            "need_open_comment": int(item.get("need_open_comment", 0) or 0),
            "only_fans_can_comment": int(item.get("only_fans_can_comment", 0) or 0),
            "show_cover_pic": int(item.get("show_cover_pic", show_cover_pic) or show_cover_pic),
        }
        articles.append(article)
    if not articles:
        raise ValueError("draftbox payload template has no articles")
    return {"articles": articles}


def create_draft(access_token: str, articles_payload: dict[str, Any], timeout_seconds: int, request_fn: RequestFn) -> dict[str, Any]:
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={urllib.parse.quote(access_token)}"
    body = json.dumps(articles_payload, ensure_ascii=False).encode("utf-8")
    payload = parse_json_response(
        request_fn("POST", url, body, {"Content-Type": "application/json; charset=utf-8"}, timeout_seconds),
        "create draft",
    )
    media_id = clean_text(payload.get("media_id"))
    if not media_id:
        raise ValueError("create draft succeeded but returned no media_id")
    return payload


def resolve_publish_package(payload: dict[str, Any]) -> dict[str, Any]:
    publish_package = safe_dict(payload.get("publish_package"))
    publish_package_path = clean_text(payload.get("publish_package_path"))
    if not publish_package and publish_package_path:
        publish_package = safe_dict(load_json(Path(publish_package_path).resolve()))
    if not publish_package:
        raise ValueError("wechat draft push requires publish_package or publish_package_path")
    return publish_package


def choose_cover_reference(payload: dict[str, Any], publish_package: dict[str, Any]) -> dict[str, str]:
    explicit_local = clean_text(payload.get("cover_image_path"))
    explicit_remote = clean_text(payload.get("cover_image_url"))
    if explicit_local or explicit_remote:
        return {"local_path": explicit_local, "remote_url": explicit_remote, "filename": "cover-image"}
    cover_plan = safe_dict(publish_package.get("cover_plan"))
    asset_id = clean_text(cover_plan.get("selected_cover_asset_id") or cover_plan.get("primary_image_asset_id"))
    selected_cover_local = clean_text(cover_plan.get("selected_cover_local_path"))
    selected_cover_remote = clean_text(cover_plan.get("selected_cover_source_url")) or clean_text(cover_plan.get("selected_cover_render_src"))
    if selected_cover_local or selected_cover_remote:
        return {
            "local_path": selected_cover_local,
            "remote_url": selected_cover_remote,
            "filename": asset_id or "cover-image",
        }
    for asset in safe_list(publish_package.get("image_assets")):
        if clean_text(asset.get("asset_id")) == asset_id or not asset_id:
            return {
                "local_path": clean_text(asset.get("local_path")),
                "remote_url": clean_text(asset.get("source_url")) or clean_text(asset.get("render_src")),
                "filename": clean_text(asset.get("asset_id")) or "cover-image",
            }
    raise ValueError("No cover image is available. Provide cover_image_path/cover_image_url or keep at least one article image.")


def push_publish_package_to_wechat_api(
    raw_payload: dict[str, Any],
    *,
    request_fn: RequestFn | None = None,
    download_fn: DownloadFn | None = None,
) -> dict[str, Any]:
    request_fn = request_fn or default_request_fn
    download_fn = download_fn or default_download_fn
    timeout_seconds = max(5, int(raw_payload.get("timeout_seconds", 30) or 30))
    review_gate = resolve_human_review_gate(raw_payload)
    workflow_publication_gate = build_workflow_publication_gate(safe_dict(raw_payload.get("publish_package")))
    if not review_gate["approved"]:
        return {
            "status": "blocked_review_gate",
            "workflow_kind": "wechat_draft_push",
            "push_backend": "api",
            "fallback_used": False,
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "blocked_reason": "human_review_not_approved",
            "resolved_content_html": clean_text(safe_dict(raw_payload.get("publish_package")).get("content_html")),
            "uploaded_inline_images": [],
            "uploaded_cover": {},
            "draft_result": {},
            "articles_payload": {},
            "error_message": "Human review approval is required before pushing to WeChat. Set human_review_approved=true after review.",
        }
    publish_package = resolve_publish_package(raw_payload)
    workflow_publication_gate = build_workflow_publication_gate(publish_package)
    credentials = resolve_wechat_credentials(raw_payload)
    access_token = fetch_access_token(credentials["app_id"], credentials["app_secret"], timeout_seconds, request_fn)

    image_assets = deepcopy_assets = [dict(item) for item in safe_list(publish_package.get("image_assets"))]
    uploaded_urls: dict[str, str] = {}
    uploaded_assets: list[dict[str, str]] = []
    for asset in image_assets:
        local_path = clean_text(asset.get("local_path"))
        remote_url = clean_text(asset.get("source_url")) or clean_text(asset.get("render_src"))
        if not local_path and not remote_url:
            continue
        asset_id = clean_text(asset.get("asset_id")) or f"asset-{len(uploaded_assets)+1:02d}"
        binary, filename = resolve_binary_from_reference(
            local_path=local_path,
            remote_url=remote_url,
            fallback_name=asset_id,
            timeout_seconds=timeout_seconds,
            download_fn=download_fn,
        )
        wechat_url = upload_inline_image(access_token, binary, filename, timeout_seconds, request_fn)
        uploaded_urls[asset_id] = wechat_url
        uploaded_assets.append({"asset_id": asset_id, "inline_url": wechat_url, "filename": filename})

    resolved_content_html = replace_content_images(clean_text(publish_package.get("content_html")), image_assets, uploaded_urls)

    cover_reference = choose_cover_reference(raw_payload, publish_package)
    cover_bytes, cover_filename = resolve_binary_from_reference(
        local_path=cover_reference["local_path"],
        remote_url=cover_reference["remote_url"],
        fallback_name=clean_text(cover_reference["filename"]) or "cover-image",
        timeout_seconds=timeout_seconds,
        download_fn=download_fn,
    )
    cover_upload = upload_cover_material(access_token, cover_bytes, cover_filename, timeout_seconds, request_fn)

    articles_payload = build_articles_payload(
        safe_dict(publish_package.get("draftbox_payload_template")),
        resolved_content_html,
        cover_upload["media_id"],
        clean_text(raw_payload.get("author")) or clean_text(publish_package.get("author")),
        int(raw_payload.get("show_cover_pic", 1) or 1),
    )
    draft_result = create_draft(access_token, articles_payload, timeout_seconds, request_fn)

    return {
        "status": "ok",
        "workflow_kind": "wechat_draft_push",
        "push_backend": "api",
        "fallback_used": False,
        "review_gate": review_gate,
        "workflow_publication_gate": workflow_publication_gate,
        "resolved_content_html": resolved_content_html,
        "uploaded_inline_images": uploaded_assets,
        "uploaded_cover": cover_upload,
        "draft_result": {
            "media_id": clean_text(draft_result.get("media_id")),
        },
        "articles_payload": articles_payload,
    }

def push_publish_package_via_browser_session(
    raw_payload: dict[str, Any],
    *,
    browser_runner: BrowserRunner | None = None,
    download_fn: DownloadFn | None = None,
) -> dict[str, Any]:
    browser_runner = browser_runner or default_browser_session_push_runner
    download_fn = download_fn or default_download_fn
    timeout_seconds = max(5, int(raw_payload.get("timeout_seconds", 30) or 30))
    review_gate = resolve_human_review_gate(raw_payload)
    workflow_publication_gate = build_workflow_publication_gate(safe_dict(raw_payload.get("publish_package")))
    if not review_gate["approved"]:
        return {
            "status": "blocked_review_gate",
            "workflow_kind": "wechat_draft_push",
            "push_backend": "browser_session",
            "fallback_used": False,
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "blocked_reason": "human_review_not_approved",
            "resolved_content_html": clean_text(safe_dict(raw_payload.get("publish_package")).get("content_html")),
            "uploaded_inline_images": [],
            "uploaded_cover": {},
            "draft_result": {},
            "articles_payload": {},
            "browser_session": prepare_wechat_browser_session_context(raw_payload),
            "error_message": "Human review approval is required before pushing to WeChat. Set human_review_approved=true after review.",
        }

    publish_package = resolve_publish_package(raw_payload)
    workflow_publication_gate = build_workflow_publication_gate(publish_package)
    session_context = prepare_wechat_browser_session_context(raw_payload)
    if not session_context.get("active"):
        next_step = "Launch a signed-in browser with remote debugging, then rerun with push_backend=browser_session or push_backend=auto."
        return {
            "status": "blocked_browser_session",
            "workflow_kind": "wechat_draft_push",
            "push_backend": "browser_session",
            "fallback_used": False,
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "blocked_reason": "browser_session_unavailable",
            "resolved_content_html": clean_text(publish_package.get("content_html")),
            "uploaded_inline_images": [],
            "uploaded_cover": {},
            "draft_result": {},
            "articles_payload": {},
            "browser_session": session_context,
            "error_message": next_step,
            "next_step": next_step,
        }

    image_assets = [dict(item) for item in safe_list(publish_package.get("image_assets"))]
    browser_content_html, unresolved_asset_ids = rewrite_content_images_for_browser_session(
        clean_text(publish_package.get("content_html")),
        image_assets,
    )
    if unresolved_asset_ids:
        return {
            "status": "blocked_browser_session",
            "workflow_kind": "wechat_draft_push",
            "push_backend": "browser_session",
            "fallback_used": False,
            "review_gate": review_gate,
            "workflow_publication_gate": workflow_publication_gate,
            "blocked_reason": "browser_session_missing_remote_inline_images",
            "resolved_content_html": browser_content_html,
            "uploaded_inline_images": [],
            "uploaded_cover": {},
            "draft_result": {},
            "articles_payload": {},
            "browser_session": session_context,
            "missing_remote_inline_asset_ids": unresolved_asset_ids,
            "error_message": (
                "Browser-session fallback currently requires every inline image in content_html to already have an "
                "HTTP(S) source so the editor can import it without the API upload path."
            ),
            "next_step": (
                "Reuse a publish package whose content_html already references remote image URLs, or extend the "
                "browser-session path to drive inline image uploads."
            ),
        }

    cover_reference = choose_cover_reference(raw_payload, publish_package)
    output_dir = resolve_browser_session_output_dir(raw_payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    content_html_path = output_dir / "browser-session-content.html"
    content_html_path.write_text(browser_content_html, encoding="utf-8")

    cover_bytes, cover_filename = resolve_binary_from_reference(
        local_path=cover_reference["local_path"],
        remote_url=cover_reference["remote_url"],
        fallback_name=clean_text(cover_reference["filename"]) or "cover-image",
        timeout_seconds=timeout_seconds,
        download_fn=download_fn,
    )
    cover_file_path = output_dir / sanitize_filename(cover_filename, "cover-image")
    cover_file_path.write_bytes(cover_bytes)

    articles_payload = build_articles_payload(
        safe_dict(publish_package.get("draftbox_payload_template")),
        browser_content_html,
        clean_text(raw_payload.get("browser_thumb_media_id")) or "{{BROWSER_SESSION_THUMB_MEDIA_ID}}",
        clean_text(raw_payload.get("author")) or clean_text(publish_package.get("author")),
        int(raw_payload.get("show_cover_pic", 1) or 1),
    )
    primary_article = safe_dict(safe_list(articles_payload.get("articles"))[:1][0] if safe_list(articles_payload.get("articles")) else {})

    browser_session_request = normalize_browser_session_request(raw_payload)
    manifest = {
        "workflow_kind": "wechat_browser_session_push",
        "created_at": datetime.now(UTC).isoformat(),
        "cover_image_path": str(cover_file_path),
        "content_html_path": str(content_html_path),
        "article": {
            "title": clean_text(primary_article.get("title")),
            "author": clean_text(primary_article.get("author")),
            "digest": clean_text(primary_article.get("digest")),
            "content_html": browser_content_html,
            "show_cover_pic": int(primary_article.get("show_cover_pic", 1) or 1),
        },
        "browser_session": {
            "strategy": clean_text(session_context.get("strategy")),
            "cdp_endpoint": clean_text(session_context.get("cdp_endpoint")),
            "wait_ms": int(session_context.get("wait_ms", 8000) or 8000),
            "home_url": clean_text(browser_session_request.get("home_url")),
            "editor_url": clean_text(browser_session_request.get("editor_url")),
        },
    }
    manifest_path = output_dir / "browser-session-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    browser_result = browser_runner(manifest_path, session_context, timeout_seconds)
    browser_result_path = output_dir / "browser-session-result.json"
    browser_result_path.write_text(json.dumps(browser_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "workflow_kind": "wechat_draft_push",
        "push_backend": "browser_session",
        "fallback_used": False,
        "review_gate": review_gate,
        "workflow_publication_gate": workflow_publication_gate,
        "resolved_content_html": browser_content_html,
        "uploaded_inline_images": [],
        "uploaded_cover": {
            "media_id": clean_text(browser_result.get("cover_media_id")),
            "url": clean_text(browser_result.get("cover_url")),
            "local_path": str(cover_file_path),
        },
        "draft_result": {
            "media_id": clean_text(browser_result.get("draft_media_id")),
            "draft_url": clean_text(browser_result.get("draft_url")),
        },
        "articles_payload": articles_payload,
        "browser_session": {
            **session_context,
            "manifest_path": str(manifest_path),
            "content_html_path": str(content_html_path),
            "result_path": str(browser_result_path),
        },
    }


def push_publish_package_to_wechat(
    raw_payload: dict[str, Any],
    *,
    request_fn: RequestFn | None = None,
    download_fn: DownloadFn | None = None,
    browser_runner: BrowserRunner | None = None,
) -> dict[str, Any]:
    backend = resolve_push_backend(raw_payload)
    if backend == "browser_session":
        return push_publish_package_via_browser_session(
            raw_payload,
            browser_runner=browser_runner,
            download_fn=download_fn,
        )
    if backend == "auto":
        try:
            return push_publish_package_to_wechat_api(
                raw_payload,
                request_fn=request_fn,
                download_fn=download_fn,
            )
        except Exception as exc:
            if not normalize_browser_session_request(raw_payload).get("strategy"):
                raise
            browser_result = push_publish_package_via_browser_session(
                raw_payload,
                browser_runner=browser_runner,
                download_fn=download_fn,
            )
            browser_result["fallback_used"] = True
            browser_result["api_error_message"] = clean_text(exc)
            return browser_result
    return push_publish_package_to_wechat_api(
        raw_payload,
        request_fn=request_fn,
        download_fn=download_fn,
    )


__all__ = [
    "build_workflow_publication_gate",
    "inspect_wechat_credentials",
    "prepare_wechat_browser_session_context",
    "push_publish_package_to_wechat",
    "push_publish_package_to_wechat_api",
    "push_publish_package_via_browser_session",
    "resolve_wechat_credentials",
]
