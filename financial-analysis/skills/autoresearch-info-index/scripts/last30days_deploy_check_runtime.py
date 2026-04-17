#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from news_index_runtime import load_json, write_json


DEFAULT_REQUIRED_REL_PATHS = ["SKILL.md", "README.md", "scripts/last30days.py"]
DEFAULT_OPTIONAL_REL_PATHS = ["open/SKILL.md", "package.json"]
DEFAULT_BINARY_GROUPS = [["node"], ["python", "python3"]]
DEFAULT_OPTIONAL_BINARIES = ["yt-dlp"]
DEFAULT_ENV_VARS = ["OPENAI_API_KEY", "XAI_API_KEY", "SCRAPECREATORS_API_KEY", "X_SESSION_COOKIE"]


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def normalize_path(value: Any) -> Path:
    return Path(clean_text(value)).expanduser()


def normalize_string_list(value: Any, default: list[str]) -> list[str]:
    items = [clean_text(item) for item in safe_list(value) if clean_text(item)]
    return items or default


def normalize_binary_groups(value: Any) -> list[list[str]]:
    if isinstance(value, list) and not value:
        return []
    groups: list[list[str]] = []
    for item in safe_list(value):
        if isinstance(item, str):
            groups.append([clean_text(item)])
            continue
        if isinstance(item, list):
            group = [clean_text(entry) for entry in item if clean_text(entry)]
            if group:
                groups.append(group)
    return groups or [list(group) for group in DEFAULT_BINARY_GROUPS]


def preferred_user_root() -> Path:
    username = Path.home().name
    d_user_root = Path("D:/Users") / username
    return d_user_root


def default_vendor_root() -> Path:
    return preferred_user_root() / ".codex" / "vendor"


def default_install_root() -> Path:
    env_root = clean_text(os.environ.get("LAST30DAYS_SKILL_ROOT"))
    if env_root:
        return Path(env_root).expanduser()
    return default_vendor_root() / "last30days-skill"


def default_env_file_path() -> Path:
    env_path = clean_text(os.environ.get("LAST30DAYS_ENV_FILE"))
    if env_path:
        return Path(env_path).expanduser()
    return default_vendor_root() / "last30days-data" / ".env"


def default_storage_paths() -> list[str]:
    data_root = default_vendor_root() / "last30days-data"
    return [
        str(data_root),
        str(data_root / "out"),
        str(data_root / "history"),
    ]


def inspect_binary(command: str) -> dict[str, Any]:
    resolved = shutil.which(command)
    entry = {
        "command": command,
        "available": bool(resolved),
        "path": resolved or "",
        "version": "",
        "error": "",
    }
    if not resolved:
        return entry
    try:
        completed = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        version_text = clean_text(completed.stdout or completed.stderr)
        entry["version"] = version_text.splitlines()[0] if version_text else ""
    except (OSError, subprocess.SubprocessError) as exc:
        entry["error"] = clean_text(exc)
    return entry


def inspect_path(path: Path) -> dict[str, Any]:
    exists = path.exists()
    kind = "missing"
    entry_count = 0
    if exists and path.is_dir():
        kind = "directory"
        try:
            entry_count = sum(1 for _ in path.iterdir())
        except OSError:
            entry_count = 0
    elif exists:
        kind = "file"
    return {"path": str(path), "exists": exists, "kind": kind, "entry_count": entry_count}


def find_sqlite_candidates(roots: list[Path], *, limit: int = 25) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else list(root.rglob("*"))
        for path in candidates:
            suffix = path.suffix.lower()
            if suffix not in {".sqlite", ".db", ".sqlite3"}:
                continue
            text = str(path)
            if text in seen:
                continue
            seen.add(text)
            matches.append(text)
            if len(matches) >= limit:
                return matches
    return matches


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    install_root = normalize_path(raw_payload.get("install_root")) if clean_text(raw_payload.get("install_root")) else default_install_root()
    env_file_path = (
        normalize_path(raw_payload.get("env_file_path"))
        if clean_text(raw_payload.get("env_file_path"))
        else default_env_file_path()
    )
    storage_paths = [normalize_path(item) for item in normalize_string_list(raw_payload.get("storage_paths"), default_storage_paths())]
    return {
        "install_root": install_root,
        "required_rel_paths": normalize_string_list(raw_payload.get("required_rel_paths"), DEFAULT_REQUIRED_REL_PATHS),
        "optional_rel_paths": normalize_string_list(raw_payload.get("optional_rel_paths"), DEFAULT_OPTIONAL_REL_PATHS),
        "binary_groups": normalize_binary_groups(raw_payload.get("binary_groups")),
        "optional_binaries": normalize_string_list(raw_payload.get("optional_binaries"), DEFAULT_OPTIONAL_BINARIES),
        "env_file_path": env_file_path,
        "env_vars": normalize_string_list(raw_payload.get("env_vars"), DEFAULT_ENV_VARS),
        "storage_paths": storage_paths,
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Last30Days Deploy Check",
        "",
        f"Status: {result.get('status', 'unknown')}",
        f"Skill root: {result.get('skill_root', '')}",
        "",
        "## Required Files",
    ]
    for item in result.get("required_files", []):
        lines.append(f"- {item.get('relative_path', '')}: {'ok' if item.get('exists') else 'missing'}")
    lines.extend(["", "## Runtime"])
    for group in result.get("binary_status", {}).get("required_groups", []):
        line = f"- {', '.join(group.get('commands', []))}: {'ok' if group.get('satisfied') else 'missing'}"
        if group.get("resolved_command"):
            line += f" ({group.get('resolved_command')})"
        lines.append(line)
    optional = result.get("binary_status", {}).get("optional", [])
    if optional:
        lines.append("")
        lines.append("## Optional Binaries")
        for item in optional:
            lines.append(f"- {item.get('command', '')}: {'ok' if item.get('available') else 'missing'}")
    lines.extend(["", "## Env"])
    env_status = result.get("env_status", {})
    lines.append(f"- Env file: {env_status.get('env_file', {}).get('path', '')} ({'present' if env_status.get('env_file', {}).get('exists') else 'missing'})")
    for item in env_status.get("variables", []):
        lines.append(f"- {item.get('name', '')}: {'set' if item.get('is_set') else 'missing'}")
    lines.extend(["", "## Storage Paths"])
    for item in result.get("storage_paths", []):
        lines.append(f"- {item.get('path', '')}: {'present' if item.get('exists') else 'missing'} ({item.get('kind', '')})")
    lines.extend(["", "## SQLite Candidates"])
    lines.extend([f"- {path}" for path in result.get("sqlite_candidates", [])] or ["- None"])
    if result.get("notes"):
        lines.extend(["", "## Notes"])
        lines.extend([f"- {note}" for note in result.get("notes", [])])
    return "\n".join(lines).strip() + "\n"


def run_last30days_deploy_check(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    install_root = request["install_root"]

    required_files = [
        {
            "relative_path": relative_path,
            "path": str(install_root / relative_path),
            "exists": (install_root / relative_path).exists(),
        }
        for relative_path in request["required_rel_paths"]
    ]
    optional_files = [
        {
            "relative_path": relative_path,
            "path": str(install_root / relative_path),
            "exists": (install_root / relative_path).exists(),
        }
        for relative_path in request["optional_rel_paths"]
    ]

    required_groups = []
    runtime_ready = True
    for group in request["binary_groups"]:
        inspected = [inspect_binary(command) for command in group]
        satisfied = any(item.get("available") for item in inspected)
        if not satisfied:
            runtime_ready = False
        resolved = next((item for item in inspected if item.get("available")), {})
        required_groups.append(
            {
                "commands": group,
                "satisfied": satisfied,
                "resolved_command": resolved.get("command", ""),
                "resolved_path": resolved.get("path", ""),
                "version": resolved.get("version", ""),
                "alternatives": inspected,
            }
        )
    optional_binaries = [inspect_binary(command) for command in request["optional_binaries"]]

    env_file = inspect_path(request["env_file_path"])
    env_vars = [{"name": name, "is_set": bool(os.environ.get(name))} for name in request["env_vars"]]
    storage_paths = [inspect_path(path) for path in request["storage_paths"]]
    sqlite_roots = [install_root, request["env_file_path"], *request["storage_paths"]]
    sqlite_candidates = find_sqlite_candidates(sqlite_roots)

    notes: list[str] = []
    if not install_root.exists():
        status = "missing_install"
        notes.append("Install root is missing. Separate deployment has not been completed yet.")
    else:
        missing_required_files = [item["relative_path"] for item in required_files if not item["exists"]]
        if missing_required_files:
            status = "partial"
            notes.append(f"Missing required files: {', '.join(missing_required_files)}")
        elif not runtime_ready:
            status = "partial"
            notes.append("Required runtimes are incomplete. Node and a Python executable are the baseline checks.")
        else:
            status = "ready"

    if not env_file["exists"]:
        notes.append("The expected .env file is missing. Source backends that depend on credentials may still fail.")
    if not any(item["is_set"] for item in env_vars):
        notes.append("No optional API or auth environment variables are set in this process.")
    if not sqlite_candidates:
        notes.append("No SQLite watchlist/history database was found in the checked paths.")
    if any(not item.get("available") for item in optional_binaries):
        missing_optional = [item["command"] for item in optional_binaries if not item.get("available")]
        notes.append(f"Optional helpers missing: {', '.join(missing_optional)}")

    result = {
        "status": status,
        "skill_root": str(install_root),
        "required_files": required_files,
        "optional_files": optional_files,
        "binary_status": {
            "required_groups": required_groups,
            "optional": optional_binaries,
        },
        "env_status": {
            "env_file": env_file,
            "variables": env_vars,
        },
        "storage_paths": storage_paths,
        "sqlite_candidates": sqlite_candidates,
        "notes": notes,
    }
    result["report_markdown"] = build_report_markdown(result)
    return result


__all__ = [
    "build_report_markdown",
    "load_json",
    "run_last30days_deploy_check",
    "write_json",
]
