#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from article_workflow_runtime import load_json
from news_index_runtime import safe_dict, safe_list


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


RequestFn = Callable[[str, str, bytes | None, dict[str, str], int], bytes]
DownloadFn = Callable[[str, int], bytes]
REPO_ROOT = Path(__file__).resolve().parents[4]


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


def load_local_wechat_credentials() -> dict[str, str]:
    candidate_paths: list[Path] = []
    explicit_path = clean_text(os.environ.get("WECHAT_ENV_FILE"))
    if explicit_path:
        candidate_paths.append(Path(explicit_path).expanduser().resolve())
    candidate_paths.append((Path.cwd() / ".env.wechat.local").resolve())
    candidate_paths.append((REPO_ROOT / ".env.wechat.local").resolve())

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

    file_credentials = load_local_wechat_credentials()
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
                "in the environment or create .env.wechat.local. Only use allow_insecure_inline_credentials=true "
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
                "next_step": "Move the credentials into WECHAT_APP_ID/WECHAT_APP_SECRET or .env.wechat.local.",
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
        "error_message": "Missing WeChat credentials. Set WECHAT_APP_ID/WECHAT_APP_SECRET in the environment or create .env.wechat.local.",
        "next_step": "Set WECHAT_APP_ID/WECHAT_APP_SECRET or create an untracked .env.wechat.local file.",
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


def push_publish_package_to_wechat(
    raw_payload: dict[str, Any],
    *,
    request_fn: RequestFn | None = None,
    download_fn: DownloadFn | None = None,
) -> dict[str, Any]:
    request_fn = request_fn or default_request_fn
    download_fn = download_fn or default_download_fn
    timeout_seconds = max(5, int(raw_payload.get("timeout_seconds", 30) or 30))
    review_gate = resolve_human_review_gate(raw_payload)
    if not review_gate["approved"]:
        return {
            "status": "blocked_review_gate",
            "workflow_kind": "wechat_draft_push",
            "review_gate": review_gate,
            "blocked_reason": "human_review_not_approved",
            "resolved_content_html": clean_text(safe_dict(raw_payload.get("publish_package")).get("content_html")),
            "uploaded_inline_images": [],
            "uploaded_cover": {},
            "draft_result": {},
            "articles_payload": {},
            "error_message": "Human review approval is required before pushing to WeChat. Set human_review_approved=true after review.",
        }
    publish_package = resolve_publish_package(raw_payload)
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
        "review_gate": review_gate,
        "resolved_content_html": resolved_content_html,
        "uploaded_inline_images": uploaded_assets,
        "uploaded_cover": cover_upload,
        "draft_result": {
            "media_id": clean_text(draft_result.get("media_id")),
        },
        "articles_payload": articles_payload,
    }


__all__ = ["inspect_wechat_credentials", "push_publish_package_to_wechat", "resolve_wechat_credentials"]
