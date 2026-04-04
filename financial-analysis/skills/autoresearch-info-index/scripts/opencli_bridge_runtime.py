#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import subprocess
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from news_index_runtime import (
    isoformat_or_blank,
    load_json,
    parse_datetime,
    run_news_index,
    short_excerpt,
    slugify,
    write_json,
)


COLLECTION_KEYS = (
    "items",
    "results",
    "entries",
    "records",
    "captures",
    "pages",
    "documents",
    "articles",
)
NESTED_RESULT_KEYS = ("opencli_result", "source_result", "result", "data")
EXCLUDED_SITE_PROFILES = {"x", "twitter", "x-twitter", "wechat", "weixin"}
EXCLUDED_HOST_FRAGMENTS = ("x.com", "twitter.com", "weixin.qq.com", "mp.weixin.qq.com")
BRAND_BY_HOST_FRAGMENT = {
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "github.com": "GitHub",
    "youtube.com": "YouTube",
    "x.com": "X",
    "twitter.com": "X",
    "weixin.qq.com": "WeChat",
    "mp.weixin.qq.com": "WeChat",
}
DEFAULT_SOURCE_POLICIES = {
    "generic-dynamic-page": {
        "source_type": "analysis",
        "channel": "shadow",
        "access_mode": "browser_session",
        "allow_observed_at_fallback": True,
    },
    "broker-research-portal": {
        "source_type": "research_note",
        "channel": "shadow",
        "access_mode": "browser_session",
        "allow_observed_at_fallback": True,
    },
    "official-dynamic-page": {
        "source_type": "official_release",
        "channel": "shadow",
        "access_mode": "browser_session",
        "allow_observed_at_fallback": True,
    },
    "company-ir-portal": {
        "source_type": "company_statement",
        "channel": "shadow",
        "access_mode": "browser_session",
        "allow_observed_at_fallback": True,
    },
}
BLOCKED_STATUS_MARKERS = {
    "blocked",
    "login_required",
    "auth_required",
    "paywalled",
    "captcha",
    "failed",
    "error",
    "unavailable",
}
RUNNER_BLOCKED_MARKERS = ("blocked", "login", "auth", "captcha", "paywall", "session")


def now_utc() -> datetime:
    return datetime.now(UTC)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def normalize_key(value: Any) -> str:
    return clean_text(value).lower().replace(" ", "_").replace("-", "_")


def decode_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def extract_first_json_value(text: str) -> Any:
    cleaned = text.lstrip("\ufeff\r\n\t ")
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[index:])
            return payload
        except json.JSONDecodeError:
            continue
    raise ValueError("Could not find a JSON object or array in the OpenCLI output")


def host_for(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ""


def brand_for_host(host: str) -> str:
    for fragment, brand in BRAND_BY_HOST_FRAGMENT.items():
        if fragment in host:
            return brand
    if not host:
        return ""
    return host.split(":")[0]


def is_excluded_route(url: str) -> bool:
    host = host_for(url)
    return any(fragment in host for fragment in EXCLUDED_HOST_FRAGMENTS)


def resolve_source_policy(site_profile: str, override: dict[str, Any]) -> dict[str, Any]:
    profile_key = normalize_key(site_profile) or "generic_dynamic_page"
    base = deepcopy(DEFAULT_SOURCE_POLICIES.get(profile_key.replace("_", "-")) or DEFAULT_SOURCE_POLICIES.get(profile_key) or DEFAULT_SOURCE_POLICIES["generic-dynamic-page"])
    for key, value in safe_dict(override).items():
        if value not in (None, "", [], {}):
            base[key] = deepcopy(value)
    base["site_profile"] = site_profile
    base["channel"] = clean_text(base.get("channel") or "shadow").lower() or "shadow"
    if base["channel"] not in {"core", "shadow", "background"}:
        base["channel"] = "shadow"
    base["access_mode"] = normalize_access_mode(base.get("access_mode"), blocked_reason="")
    base["source_type"] = clean_text(base.get("source_type") or "analysis").lower().replace(" ", "_").replace("-", "_")
    base["allow_observed_at_fallback"] = bool(base.get("allow_observed_at_fallback", True))
    return base


def normalize_access_mode(value: Any, *, blocked_reason: str) -> str:
    text = clean_text(value).lower().replace("-", "_")
    if blocked_reason:
        return "blocked"
    if text in {"public", "browser_session", "blocked"}:
        return text
    return "public"


def load_json_from_path(path: Path) -> Any:
    try:
        return load_json(path)
    except Exception:
        return extract_first_json_value(decode_text_file(path))


def normalize_input_mode(raw_payload: dict[str, Any]) -> str:
    opencli_block = safe_dict(raw_payload.get("opencli"))
    requested = normalize_key(opencli_block.get("input_mode") or raw_payload.get("opencli_input_mode"))
    if requested in {"inline_payload", "result_path", "command"}:
        return requested
    if opencli_block.get("result") not in (None, "", [], {}) or raw_payload.get("opencli_result") not in (None, "", [], {}):
        return "inline_payload"
    if clean_text(opencli_block.get("result_path") or raw_payload.get("opencli_result_path")):
        return "result_path"
    if opencli_block.get("command") not in (None, "", [], {}) or raw_payload.get("opencli_command") not in (None, "", [], {}):
        return "command"
    return ""


def normalize_command(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, str):
        return [clean_text(token) for token in shlex.split(value, posix=False) if clean_text(token)]
    return []


def classify_runner_failure(message: str) -> str:
    lowered = clean_text(message).lower()
    if any(marker in lowered for marker in RUNNER_BLOCKED_MARKERS):
        return "blocked_capture"
    return "failed_capture"


def run_opencli_command(raw_payload: dict[str, Any]) -> tuple[Any, str, str, dict[str, Any]]:
    opencli_block = safe_dict(raw_payload.get("opencli"))
    command = normalize_command(opencli_block.get("command") or raw_payload.get("opencli_command"))
    timeout_seconds = max(1, int(opencli_block.get("timeout_seconds") or raw_payload.get("opencli_timeout_seconds") or 30))
    workdir_text = clean_text(opencli_block.get("working_directory") or opencli_block.get("workdir") or raw_payload.get("opencli_workdir"))
    result_path_text = clean_text(opencli_block.get("result_path") or raw_payload.get("opencli_result_path"))
    artifact_root_text = clean_text(opencli_block.get("artifact_root") or raw_payload.get("opencli_artifact_root"))
    working_directory = Path(workdir_text).expanduser().resolve() if workdir_text else None
    resolved_result_path = str(Path(result_path_text).expanduser().resolve()) if result_path_text else ""
    resolved_artifact_root = str(Path(artifact_root_text).expanduser().resolve()) if artifact_root_text else ""
    runner_summary = {
        "mode": "command",
        "status": "not_run",
        "reason": "",
        "command": command,
        "working_directory": str(working_directory) if working_directory else "",
        "timeout_seconds": timeout_seconds,
        "result_path": resolved_result_path,
        "artifact_root": resolved_artifact_root,
        "exit_code": None,
        "timed_out": False,
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "payload_source": "",
    }
    if not command:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = "input_mode=command requires opencli.command"
        return {}, "", resolved_result_path, runner_summary
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            cwd=str(working_directory) if working_directory else None,
        )
    except subprocess.TimeoutExpired as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = f"timeout after {timeout_seconds}s"
        runner_summary["timed_out"] = True
        runner_summary["stdout_excerpt"] = short_excerpt(clean_text(getattr(exc, "stdout", "") or ""), limit=240)
        runner_summary["stderr_excerpt"] = short_excerpt(clean_text(getattr(exc, "stderr", "") or ""), limit=240)
        return {}, "", resolved_result_path, runner_summary
    except FileNotFoundError as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = clean_text(exc) or f"{command[0]} not installed"
        return {}, "", resolved_result_path, runner_summary
    except OSError as exc:
        runner_summary["status"] = "failed_capture"
        runner_summary["reason"] = clean_text(exc)
        return {}, "", resolved_result_path, runner_summary

    runner_summary["exit_code"] = completed.returncode
    runner_summary["stdout_excerpt"] = short_excerpt(clean_text(completed.stdout), limit=240)
    runner_summary["stderr_excerpt"] = short_excerpt(clean_text(completed.stderr), limit=240)

    if completed.returncode != 0:
        failure_reason = clean_text(completed.stderr or completed.stdout or f"command exited {completed.returncode}")
        runner_summary["status"] = classify_runner_failure(failure_reason)
        runner_summary["reason"] = failure_reason or f"command exited {completed.returncode}"
        return {}, "", resolved_result_path, runner_summary

    try:
        if resolved_result_path:
            payload = load_json_from_path(Path(resolved_result_path))
            runner_summary["status"] = "ok"
            runner_summary["payload_source"] = "command_result_path"
            return payload, "command_result_path", resolved_result_path, runner_summary
        payload = extract_first_json_value(completed.stdout)
        runner_summary["status"] = "ok"
        runner_summary["payload_source"] = "command_stdout"
        return payload, "command_stdout", "", runner_summary
    except Exception as exc:
        runner_summary["status"] = "parse_error"
        runner_summary["reason"] = clean_text(exc) or "command completed but payload could not be parsed"
        return {}, "", resolved_result_path, runner_summary


def resolve_opencli_payload(raw_payload: dict[str, Any]) -> tuple[Any, str, str, dict[str, Any]]:
    opencli_block = safe_dict(raw_payload.get("opencli"))
    input_mode = normalize_input_mode(raw_payload)
    if input_mode == "command":
        return run_opencli_command(raw_payload)
    inline_payload = opencli_block.get("result")
    if inline_payload not in (None, "", [], {}):
        return inline_payload, "inline_payload", "", {}
    top_level_inline = raw_payload.get("opencli_result")
    if top_level_inline not in (None, "", [], {}):
        return top_level_inline, "inline_payload", "", {}

    result_path = clean_text(opencli_block.get("result_path") or raw_payload.get("opencli_result_path"))
    if result_path:
        resolved = Path(result_path).expanduser().resolve()
        return load_json_from_path(resolved), "result_path", str(resolved), {}
    raise ValueError("OpenCLI bridge requires opencli.result, opencli.result_path, or opencli.input_mode=command")


def flatten_result_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if any(clean_text(value.get(key)) for key in ("url", "page_url", "final_url", "title", "summary", "text", "content", "markdown", "body")):
            return [value]
        items: list[dict[str, Any]] = []
        for key in COLLECTION_KEYS:
            items.extend(flatten_result_items(value.get(key)))
        if not items:
            for key in NESTED_RESULT_KEYS:
                nested = value.get(key)
                if nested not in (None, "", [], {}):
                    items.extend(flatten_result_items(nested))
        return items
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for item in value:
            items.extend(flatten_result_items(item))
        return items
    return []


def canonical_claim_ids(item: dict[str, Any], request: dict[str, Any]) -> list[str]:
    claim_ids = clean_string_list(item.get("claim_ids"))
    request_claim_ids = [clean_text(claim.get("claim_id")) for claim in request["claims"] if clean_text(claim.get("claim_id"))]
    if not claim_ids and len(request_claim_ids) == 1:
        claim_ids = request_claim_ids
    return claim_ids


def normalize_claim_states(item: dict[str, Any], claim_ids: list[str]) -> dict[str, str]:
    raw_states = safe_dict(item.get("claim_states") or item.get("stance_by_claim"))
    default_state = clean_text(item.get("claim_state") or "support").lower() or "support"
    states: dict[str, str] = {}
    for claim_id in claim_ids:
        state = clean_text(raw_states.get(claim_id) or default_state).lower()
        if state in {"support", "supported", "confirm", "confirmed"}:
            states[claim_id] = "support"
        elif state in {"contradict", "contradiction", "deny", "denied"}:
            states[claim_id] = "contradict"
        elif state in {"unclear", "mixed", "unknown"}:
            states[claim_id] = "unclear"
        else:
            states[claim_id] = "support"
    return states


def normalize_artifact_manifest(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw_entries: list[Any] = []
    for key in ("artifact_manifest", "artifacts", "files", "downloads", "attachments"):
        value = item.get(key)
        if isinstance(value, list):
            raw_entries.extend(value)
    for key, role in (
        ("screenshot_path", "page_screenshot"),
        ("pdf_path", "exported_pdf"),
        ("download_path", "download"),
        ("html_path", "saved_html"),
    ):
        value = clean_text(item.get(key))
        if value:
            raw_entries.append({"path": value, "role": role})

    manifest: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(raw_entries, start=1):
        if isinstance(entry, dict):
            path = clean_text(entry.get("path") or entry.get("local_path") or entry.get("file_path") or entry.get("artifact_path"))
            source_url = clean_text(entry.get("source_url") or entry.get("url") or entry.get("download_url"))
            media_type = clean_text(entry.get("media_type") or entry.get("mime_type") or entry.get("content_type"))
            role = clean_text(entry.get("role") or entry.get("kind") or entry.get("name") or f"artifact_{index}")
        else:
            path = clean_text(entry)
            source_url = ""
            media_type = ""
            role = f"artifact_{index}"
        if not path and not source_url:
            continue
        dedupe_key = (path, source_url, role)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        manifest.append(
            {
                "role": role,
                "path": path,
                "source_url": source_url,
                "media_type": media_type,
            }
        )
    return manifest


def merge_artifact_manifests(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for artifact in [*safe_list(existing), *safe_list(incoming)]:
        if not isinstance(artifact, dict):
            continue
        key = (
            clean_text(artifact.get("role")),
            clean_text(artifact.get("path")),
            clean_text(artifact.get("source_url")),
        )
        if key == ("", "", ""):
            continue
        seen[key] = artifact
    return list(seen.values())


def candidate_quality(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        0 if clean_text(candidate.get("access_mode")) != "blocked" else 1,
        0 if clean_text(candidate.get("published_at")) else 1,
        -len(clean_text(candidate.get("text_excerpt"))),
        -len(safe_list(candidate.get("artifact_manifest"))),
    )


def merge_duplicate_candidates(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    preferred, secondary = (existing, incoming)
    if candidate_quality(incoming) < candidate_quality(existing):
        preferred, secondary = incoming, existing

    merged = deepcopy(preferred)
    merged_claim_ids = clean_string_list([*safe_list(preferred.get("claim_ids")), *safe_list(secondary.get("claim_ids"))])
    merged["claim_ids"] = merged_claim_ids
    merged_claim_states = deepcopy(safe_dict(preferred.get("claim_states")))
    for claim_id, claim_state in safe_dict(secondary.get("claim_states")).items():
        if claim_id and claim_state and claim_id not in merged_claim_states:
            merged_claim_states[claim_id] = claim_state
    merged["claim_states"] = merged_claim_states
    merged["entity_ids"] = clean_string_list([*safe_list(preferred.get("entity_ids")), *safe_list(secondary.get("entity_ids"))])
    merged["vessel_ids"] = clean_string_list([*safe_list(preferred.get("vessel_ids")), *safe_list(secondary.get("vessel_ids"))])
    merged["artifact_manifest"] = merge_artifact_manifests(
        safe_list(preferred.get("artifact_manifest")),
        safe_list(secondary.get("artifact_manifest")),
    )
    if len(clean_text(secondary.get("text_excerpt"))) > len(clean_text(merged.get("text_excerpt"))):
        merged["text_excerpt"] = secondary.get("text_excerpt", "")
    if clean_text(secondary.get("published_at")) and not clean_text(merged.get("published_at")):
        merged["published_at"] = secondary.get("published_at", "")
    if clean_text(secondary.get("observed_at")) and not clean_text(merged.get("observed_at")):
        merged["observed_at"] = secondary.get("observed_at", "")
    if clean_text(secondary.get("discovery_reason")) and not clean_text(merged.get("discovery_reason")):
        merged["discovery_reason"] = secondary.get("discovery_reason", "")
    if clean_text(secondary.get("access_mode")) == "blocked" and clean_text(merged.get("access_mode")) != "blocked":
        raw_metadata = safe_dict(merged.get("raw_metadata"))
        opencli_metadata = safe_dict(raw_metadata.get("opencli"))
        secondary_opencli = safe_dict(safe_dict(secondary.get("raw_metadata")).get("opencli"))
        if secondary_opencli.get("blocked_reason") and not opencli_metadata.get("blocked_reason"):
            opencli_metadata["blocked_reason"] = secondary_opencli.get("blocked_reason")
            raw_metadata["opencli"] = opencli_metadata
            merged["raw_metadata"] = raw_metadata
    return merged


def dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped_duplicates = 0
    for candidate in candidates:
        key = (
            clean_text(candidate.get("url")) or clean_text(candidate.get("source_name")),
            clean_text(candidate.get("published_at")) or clean_text(candidate.get("observed_at")),
            "|".join(sorted(clean_string_list(candidate.get("claim_ids")))),
        )
        if key not in kept:
            kept[key] = candidate
            continue
        kept[key] = merge_duplicate_candidates(kept[key], candidate)
        skipped_duplicates += 1
    return list(kept.values()), skipped_duplicates


def primary_text(item: dict[str, Any], url: str, source_name: str, blocked_reason: str) -> str:
    for key in (
        "text_excerpt",
        "summary",
        "combined_summary",
        "page_summary",
        "text",
        "content",
        "body",
        "markdown",
        "extracted_text",
        "visible_text",
    ):
        text = clean_text(item.get(key))
        if text:
            return short_excerpt(text, limit=240)
    if blocked_reason:
        return short_excerpt(f"OpenCLI could not capture full page content: {blocked_reason}", limit=240)
    if not url:
        return ""
    host = brand_for_host(host_for(url))
    fallback = source_name or host or "OpenCLI captured page"
    return short_excerpt(f"{fallback} captured via OpenCLI.", limit=240)


def normalize_opencli_item(item: dict[str, Any], request: dict[str, Any], index: int) -> tuple[dict[str, Any] | None, str]:
    source_policy = request["source_policy"]
    url = clean_text(item.get("url") or item.get("page_url") or item.get("final_url") or item.get("source_url") or item.get("href") or item.get("link"))
    if url and is_excluded_route(url):
        return None, "excluded_route"

    status_key = normalize_key(item.get("status") or item.get("capture_status"))
    blocked_reason = clean_text(item.get("blocked_reason") or item.get("error") or item.get("failure_reason"))
    if status_key in BLOCKED_STATUS_MARKERS and not blocked_reason:
        blocked_reason = status_key

    title = clean_text(item.get("source_name") or item.get("name") or item.get("title"))
    source_name = title or brand_for_host(host_for(url)) or request["site_profile"] or f"opencli-source-{index:02d}"
    source_type = clean_text(item.get("source_type") or item.get("type") or source_policy["source_type"]).lower().replace(" ", "_").replace("-", "_")
    claim_ids = canonical_claim_ids(item, request)
    access_mode = normalize_access_mode(item.get("access_mode") or source_policy["access_mode"], blocked_reason=blocked_reason)

    published_at = parse_datetime(
        item.get("published_at") or item.get("post_time") or item.get("release_date") or item.get("date"),
        fallback=None,
    )
    observed_at = parse_datetime(
        item.get("observed_at") or item.get("captured_at") or item.get("collected_at") or item.get("updated_at"),
        fallback=request["analysis_time"],
    )
    timestamp_fallback = ""
    if not published_at and source_policy["allow_observed_at_fallback"]:
        published_at = observed_at
        timestamp_fallback = "observed_at"

    text_excerpt = primary_text(item, url, source_name, blocked_reason)
    if not url and not text_excerpt:
        return None, "missing_url_and_text"

    candidate = {
        "source_id": clean_text(item.get("source_id") or item.get("id") or slugify(f"{request['site_profile']}-{source_name}-{index}", f"opencli-{index:02d}")),
        "source_name": source_name,
        "source_type": source_type or "analysis",
        "origin": "opencli",
        "published_at": isoformat_or_blank(published_at),
        "observed_at": isoformat_or_blank(observed_at),
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": normalize_claim_states(item, claim_ids),
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "vessel_ids": clean_string_list(item.get("vessel_ids")),
        "text_excerpt": text_excerpt,
        "channel": clean_text(item.get("channel") or source_policy["channel"]).lower() or "shadow",
        "access_mode": access_mode,
        "artifact_manifest": normalize_artifact_manifest(item),
        "raw_metadata": {
            "opencli": {
                "site_profile": request["site_profile"],
                "payload_source": request["payload_source"],
                "blocked_reason": blocked_reason,
                "timestamp_fallback": timestamp_fallback,
                "source_policy": {
                    "source_type": source_policy["source_type"],
                    "channel": source_policy["channel"],
                    "access_mode": source_policy["access_mode"],
                    "allow_observed_at_fallback": source_policy["allow_observed_at_fallback"],
                },
            },
            "source_item": deepcopy(item),
        },
        "discovery_reason": clean_text(item.get("discovery_reason") or f"Imported from OpenCLI {request['site_profile']} capture"),
    }
    if access_mode == "blocked":
        candidate["channel"] = "background"
    if candidate["channel"] not in {"core", "shadow", "background"}:
        candidate["channel"] = "shadow"
    return candidate, ""


def build_import_summary(
    candidates: list[dict[str, Any]],
    *,
    raw_item_count: int,
    skipped_invalid: int,
    skipped_excluded: int,
    skipped_duplicates: int,
    payload_source: str,
    result_path: str,
) -> dict[str, Any]:
    access_mode_counts = Counter(str(item.get("access_mode", "public")) for item in candidates)
    source_type_counts = Counter(str(item.get("source_type", "")) for item in candidates)
    channel_counts = Counter(str(item.get("channel", "")) for item in candidates)
    artifacts = sum(len(safe_list(item.get("artifact_manifest"))) for item in candidates)
    timestamp_fallback_count = sum(
        1
        for item in candidates
        if safe_dict(safe_dict(item.get("raw_metadata")).get("opencli")).get("timestamp_fallback")
    )
    return {
        "payload_source": payload_source,
        "result_path": result_path,
        "raw_item_count": raw_item_count,
        "imported_candidate_count": len(candidates),
        "skipped_invalid_count": skipped_invalid,
        "skipped_excluded_count": skipped_excluded,
        "skipped_duplicate_count": skipped_duplicates,
        "access_mode_counts": dict(access_mode_counts),
        "source_type_counts": dict(source_type_counts),
        "channel_counts": dict(channel_counts),
        "artifact_count": artifacts,
        "timestamp_fallback_count": timestamp_fallback_count,
        "default_channel_policy": "shadow_or_background_only",
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    request = safe_dict(result.get("request"))
    summary = safe_dict(result.get("import_summary"))
    runner_summary = safe_dict(result.get("runner_summary"))
    lines = [
        f"# OpenCLI Bridge Report: {request.get('topic', 'opencli-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
        f"Site profile: {request.get('site_profile', '') or 'generic-dynamic-page'}",
        f"Input mode: {request.get('input_mode', '') or 'auto'}",
        f"Payload source: {summary.get('payload_source', '') or 'unknown'}",
        f"Imported / invalid / excluded / duplicate: {summary.get('imported_candidate_count', 0)} / {summary.get('skipped_invalid_count', 0)} / {summary.get('skipped_excluded_count', 0)} / {summary.get('skipped_duplicate_count', 0)}",
        f"Access modes: {summary.get('access_mode_counts', {})}",
        f"Source types: {summary.get('source_type_counts', {})}",
        f"Artifact count: {summary.get('artifact_count', 0)}",
        "",
        "## Notes",
    ]
    lines.extend(result.get("notes", []) or ["- None"])
    if runner_summary:
        lines.extend(
            [
                "",
                "## Runner",
                "",
                f"- Status: {runner_summary.get('status', '') or 'not_run'}",
                f"- Reason: {runner_summary.get('reason', '') or 'None'}",
                f"- Exit code: {runner_summary.get('exit_code', '')}",
                f"- Timeout seconds: {runner_summary.get('timeout_seconds', '')}",
                f"- Result path: {runner_summary.get('result_path', '') or 'None'}",
                f"- Artifact root: {runner_summary.get('artifact_root', '') or 'None'}",
            ]
        )
    retrieval_result = safe_dict(result.get("retrieval_result"))
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def normalize_request(
    raw_payload: dict[str, Any],
    *,
    preloaded_payload: Any = None,
    payload_source_override: str = "",
    result_path_override: str = "",
    runner_summary_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    opencli_block = safe_dict(raw_payload.get("opencli"))
    analysis_time = parse_datetime(raw_payload.get("analysis_time") or opencli_block.get("analysis_time"), fallback=now_utc()) or now_utc()
    generated_at = now_utc()
    site_profile = clean_text(opencli_block.get("site_profile") or raw_payload.get("site_profile") or "generic-dynamic-page")
    if normalize_key(site_profile) in {normalize_key(item) for item in EXCLUDED_SITE_PROFILES}:
        raise ValueError("OpenCLI bridge does not support X or WeChat routes; use the native x-index or WeChat workflows instead")
    source_policy = resolve_source_policy(site_profile, safe_dict(opencli_block.get("source_policy") or raw_payload.get("source_policy")))
    if preloaded_payload is None:
        opencli_payload, payload_source, result_path, runner_summary = resolve_opencli_payload(raw_payload)
    else:
        opencli_payload = deepcopy(preloaded_payload)
        payload_source = clean_text(payload_source_override) or "inline_payload"
        result_path = clean_text(result_path_override)
        runner_summary = deepcopy(safe_dict(runner_summary_override))
    return {
        "topic": clean_text(raw_payload.get("topic") or f"OpenCLI bridge ({site_profile})"),
        "analysis_time": analysis_time,
        "generated_at": generated_at,
        "input_mode": normalize_input_mode(raw_payload) or "auto",
        "questions": deepcopy(safe_list(raw_payload.get("questions"))),
        "use_case": clean_text(raw_payload.get("use_case") or "opencli-bridge"),
        "source_preferences": deepcopy(safe_list(raw_payload.get("source_preferences"))),
        "mode": clean_text(raw_payload.get("mode") or "generic"),
        "windows": deepcopy(safe_list(raw_payload.get("windows"))),
        "claims": deepcopy(safe_list(raw_payload.get("claims"))),
        "market_relevance": deepcopy(safe_list(raw_payload.get("market_relevance"))),
        "expected_source_families": deepcopy(safe_list(raw_payload.get("expected_source_families"))),
        "site_profile": site_profile,
        "source_policy": source_policy,
        "opencli_payload": opencli_payload,
        "payload_source": payload_source,
        "result_path": result_path,
        "runner_summary": runner_summary,
    }


def prepare_opencli_bridge(
    raw_payload: dict[str, Any],
    *,
    preloaded_payload: Any = None,
    payload_source_override: str = "",
    result_path_override: str = "",
    runner_summary_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = normalize_request(
        raw_payload,
        preloaded_payload=preloaded_payload,
        payload_source_override=payload_source_override,
        result_path_override=result_path_override,
        runner_summary_override=runner_summary_override,
    )
    raw_items = flatten_result_items(request["opencli_payload"])
    candidates: list[dict[str, Any]] = []
    skipped_invalid = 0
    skipped_excluded = 0
    skipped_duplicates = 0
    notes: list[str] = []

    for index, item in enumerate(raw_items, start=1):
        candidate, skip_reason = normalize_opencli_item(item, request, index)
        if candidate:
            candidates.append(candidate)
            continue
        if skip_reason == "excluded_route":
            skipped_excluded += 1
        else:
            skipped_invalid += 1

    candidates, skipped_duplicates = dedupe_candidates(candidates)

    if request["payload_source"] == "result_path" and request["result_path"]:
        notes.append(f"- Loaded OpenCLI payload from `{request['result_path']}`")
    if request["payload_source"] == "command_result_path" and request["result_path"]:
        notes.append(f"- OpenCLI runner wrote a result file at `{request['result_path']}`")
    runner_summary = safe_dict(request.get("runner_summary"))
    if runner_summary:
        runner_status = clean_text(runner_summary.get("status"))
        if runner_status == "ok":
            notes.append("- OpenCLI runner completed successfully before import.")
        elif runner_status:
            reason = clean_text(runner_summary.get("reason"))
            notes.append(f"- OpenCLI runner status: {runner_status}" + (f" ({reason})" if reason else ""))
    if skipped_excluded:
        notes.append("- Some imported items were rejected because they matched native X/WeChat routes.")
    if skipped_duplicates:
        notes.append(f"- Collapsed {skipped_duplicates} duplicate OpenCLI item(s) before running news-index.")
    if not candidates:
        notes.append("- No importable OpenCLI candidate remained after normalization.")

    retrieval_request = {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": request["questions"],
        "use_case": request["use_case"],
        "source_preferences": request["source_preferences"],
        "mode": request["mode"],
        "windows": request["windows"],
        "claims": deepcopy(request["claims"]),
        "candidates": candidates,
        "market_relevance": request["market_relevance"],
        "expected_source_families": request["expected_source_families"],
    }
    result = {
        "request": {
            "topic": request["topic"],
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "generated_at": isoformat_or_blank(request["generated_at"]),
            "site_profile": request["site_profile"],
            "input_mode": request["input_mode"],
        },
        "notes": notes,
        "runner_summary": runner_summary,
        "import_summary": build_import_summary(
            candidates,
            raw_item_count=len(raw_items),
            skipped_invalid=skipped_invalid,
            skipped_excluded=skipped_excluded,
            skipped_duplicates=skipped_duplicates,
            payload_source=request["payload_source"],
            result_path=request["result_path"],
        ),
        "retrieval_request": retrieval_request,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


def run_opencli_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    result = prepare_opencli_bridge(raw_payload)
    retrieval_result = run_news_index(result["retrieval_request"])
    result["retrieval_result"] = retrieval_result
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_markdown_report",
    "load_json",
    "normalize_request",
    "prepare_opencli_bridge",
    "resolve_opencli_payload",
    "run_opencli_bridge",
    "write_json",
]
