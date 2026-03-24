#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from news_index_runtime import isoformat_or_blank, slugify


PROFILE_REQUEST_KEYS = (
    "language_mode",
    "tone",
    "draft_mode",
    "image_strategy",
    "max_images",
    "angle",
    "angle_zh",
    "must_include",
    "must_avoid",
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def default_profile_dir() -> Path:
    return Path.cwd() / ".tmp" / "article-feedback-profiles"


def resolve_profile_dir(path_value: Any) -> Path:
    path_text = clean_text(path_value)
    return Path(path_text).expanduser() if path_text else default_profile_dir()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8-sig")


def global_profile_path(profile_dir: Path) -> Path:
    return profile_dir / "global.json"


def topic_profile_path(profile_dir: Path, topic: str) -> Path:
    return profile_dir / f"topic-{slugify(clean_text(topic), 'topic')}.json"


def load_feedback_profiles(profile_dir: Path, topic: str) -> dict[str, Any]:
    global_path = global_profile_path(profile_dir)
    topic_path = topic_profile_path(profile_dir, topic)
    global_profile = load_json_file(global_path)
    topic_profile = load_json_file(topic_path)
    applied_paths = [str(path) for path in (global_path, topic_path) if path.exists()]
    return {
        "global": global_profile,
        "topic": topic_profile,
        "applied_paths": applied_paths,
    }


def feedback_profile_status(profile_dir: Path, topic: str) -> dict[str, Any]:
    profiles = load_feedback_profiles(profile_dir, topic)
    global_path = global_profile_path(profile_dir)
    topic_path = topic_profile_path(profile_dir, topic)
    return {
        "profile_dir": str(profile_dir),
        "topic": clean_text(topic),
        "global_profile_path": str(global_path),
        "topic_profile_path": str(topic_path),
        "global_exists": global_path.exists(),
        "topic_exists": topic_path.exists(),
        "applied_paths": clean_string_list(profiles.get("applied_paths")),
    }


def merge_request_with_profiles(request: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(request)
    for profile in (safe_dict(profiles.get("global")), safe_dict(profiles.get("topic"))):
        defaults = safe_dict(profile.get("request_defaults"))
        for key in PROFILE_REQUEST_KEYS:
            if key in {"must_include", "must_avoid"}:
                merged[key] = clean_string_list(defaults.get(key)) + [item for item in clean_string_list(merged.get(key)) if item not in clean_string_list(defaults.get(key))]
                continue
            current = merged.get(key)
            if current not in (None, "", []):
                continue
            if defaults.get(key) not in (None, "", []):
                merged[key] = defaults.get(key)
    merged["applied_feedback_profiles"] = clean_string_list(profiles.get("applied_paths"))
    return merged


def normalize_profile_feedback(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    scope = clean_text(payload.get("scope")).lower()
    if scope not in {"global", "topic", "both"}:
        scope = "none"
    defaults = safe_dict(payload.get("defaults"))
    normalized_defaults: dict[str, Any] = {}
    for key in PROFILE_REQUEST_KEYS:
        if key in {"must_include", "must_avoid"}:
            cleaned = clean_string_list(defaults.get(key))
            if cleaned:
                normalized_defaults[key] = cleaned
        else:
            text = defaults.get(key)
            if text not in (None, "", []):
                normalized_defaults[key] = text
    return {
        "scope": scope,
        "defaults": normalized_defaults,
        "notes": clean_string_list(payload.get("notes")),
        "use_current_request_defaults": parse_bool(
            payload.get("use_current_request_defaults", payload.get("inherit_current_request_defaults")),
            default=False,
        ),
    }


def request_defaults_from_request(request: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for key in PROFILE_REQUEST_KEYS:
        if key in {"must_include", "must_avoid"}:
            cleaned = clean_string_list(request.get(key))
            if cleaned:
                defaults[key] = cleaned
            continue
        value = request.get(key)
        if value not in (None, "", []):
            defaults[key] = value
    return defaults


def merge_profile_payload(existing: dict[str, Any], update: dict[str, Any], *, scope: str, topic: str, analysis_time: Any) -> dict[str, Any]:
    merged = deepcopy(existing)
    merged["scope"] = scope
    merged["topic"] = clean_text(topic)
    merged["updated_at"] = isoformat_or_blank(analysis_time)
    merged["request_defaults"] = {**safe_dict(existing.get("request_defaults")), **safe_dict(update.get("defaults"))}
    merged["notes"] = clean_string_list(safe_list(existing.get("notes")) + safe_list(update.get("notes")))
    merged["revision_count"] = int(existing.get("revision_count", 0) or 0) + 1
    return merged


def save_feedback_profiles(
    profile_dir: Path,
    topic: str,
    analysis_time: Any,
    profile_feedback: dict[str, Any],
    request_defaults: dict[str, Any] | None = None,
) -> list[str]:
    update = normalize_profile_feedback(profile_feedback)
    if update.get("scope") == "none":
        return []
    merged_defaults = {}
    if update.get("use_current_request_defaults"):
        merged_defaults = request_defaults_from_request(safe_dict(request_defaults))
    for key in PROFILE_REQUEST_KEYS:
        if key in {"must_include", "must_avoid"}:
            merged = clean_string_list(merged_defaults.get(key)) + [
                item for item in clean_string_list(update["defaults"].get(key)) if item not in clean_string_list(merged_defaults.get(key))
            ]
            if merged:
                merged_defaults[key] = merged
            elif key in merged_defaults:
                del merged_defaults[key]
            continue
        if update["defaults"].get(key) not in (None, "", []):
            merged_defaults[key] = update["defaults"][key]
    update = {**update, "defaults": merged_defaults}
    written: list[str] = []
    profile_dir.mkdir(parents=True, exist_ok=True)
    targets: list[tuple[str, Path]] = []
    if update["scope"] in {"global", "both"}:
        targets.append(("global", global_profile_path(profile_dir)))
    if update["scope"] in {"topic", "both"}:
        targets.append(("topic", topic_profile_path(profile_dir, topic)))
    for scope, path in targets:
        merged = merge_profile_payload(load_json_file(path), update, scope=scope, topic=topic, analysis_time=analysis_time)
        write_json_file(path, merged)
        written.append(str(path))
    return written


__all__ = [
    "clean_string_list",
    "clean_text",
    "default_profile_dir",
    "feedback_profile_status",
    "load_feedback_profiles",
    "merge_request_with_profiles",
    "normalize_profile_feedback",
    "request_defaults_from_request",
    "resolve_profile_dir",
    "save_feedback_profiles",
]
