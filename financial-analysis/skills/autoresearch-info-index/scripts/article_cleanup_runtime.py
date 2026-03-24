from __future__ import annotations

import os
import stat
import subprocess
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ARTICLE_MARKER_FILES = {
    "article-draft-result.json",
    "article-revise-result.json",
    "article-revise-template.json",
    "workflow-report.md",
    "workflow-result.json",
    "batch-workflow-report.md",
    "article-draft-preview.html",
}

DEFAULT_PREFIXES = (
    "article-",
    "verify-article-",
    "live-article-run-",
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_root_dir(value: Any) -> Path:
    text = clean_text(value)
    return Path(text).expanduser().resolve() if text else (Path.cwd() / ".tmp").resolve()


def looks_like_article_temp_dir(path: Path, prefixes: tuple[str, ...]) -> bool:
    if any(path.name.startswith(prefix) for prefix in prefixes):
        return True
    for marker in ARTICLE_MARKER_FILES:
        if any(path.rglob(marker)):
            return True
    return False


def latest_mtime(path: Path) -> datetime:
    latest = path.stat().st_mtime
    for child in path.rglob("*"):
        try:
            latest = max(latest, child.stat().st_mtime)
        except OSError:
            continue
    return datetime.fromtimestamp(latest, tz=UTC)


def _handle_remove_readonly(func: Any, path: str, exc_info: Any) -> None:
    try:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        func(path)
    except OSError:
        raise exc_info[1]


def remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=False, onerror=_handle_remove_readonly)
        return
    except PermissionError:
        quoted = str(path)
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"Remove-Item -LiteralPath '{quoted}' -Recurse -Force -ErrorAction Stop",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0 and path.exists():
            raise


def normalize_cleanup_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    root_dir = normalize_root_dir(raw_payload.get("root_dir"))
    retention_days = max(0, int(raw_payload.get("retention_days", 4) or 4))
    dry_run = parse_bool(raw_payload.get("dry_run"), default=False)
    explicit_paths = [
        Path(clean_text(item)).expanduser().resolve()
        for item in safe_list(raw_payload.get("explicit_paths"))
        if clean_text(item)
    ]
    prefixes = tuple(
        clean_text(item)
        for item in safe_list(raw_payload.get("prefixes"))
        if clean_text(item)
    ) or DEFAULT_PREFIXES
    return {
        "root_dir": root_dir,
        "retention_days": retention_days,
        "dry_run": dry_run,
        "explicit_paths": explicit_paths,
        "prefixes": prefixes,
    }


def cleanup_article_temp_dirs(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_cleanup_request(raw_payload)
    root_dir = request["root_dir"]
    if not root_dir.exists():
        return {
            "root_dir": str(root_dir),
            "retention_days": request["retention_days"],
            "dry_run": request["dry_run"],
            "removed_count": 0,
            "kept_count": 0,
            "removed_paths": [],
            "kept_paths": [],
            "missing_paths": [str(root_dir)],
        }

    cutoff = datetime.now(UTC) - timedelta(days=request["retention_days"])
    removed_paths: list[str] = []
    kept_paths: list[str] = []
    missing_paths: list[str] = []
    explicit_targets = {path for path in request["explicit_paths"]}

    candidate_dirs = [path for path in root_dir.iterdir() if path.is_dir()]
    for path in sorted(candidate_dirs, key=lambda item: item.name.lower()):
        if not looks_like_article_temp_dir(path, request["prefixes"]) and path not in explicit_targets:
            continue
        modified_at = latest_mtime(path)
        should_remove = path in explicit_targets or modified_at < cutoff
        if not should_remove:
            kept_paths.append(str(path))
            continue
        if request["dry_run"]:
            removed_paths.append(str(path))
            continue
        remove_tree(path)
        removed_paths.append(str(path))

    for path in sorted(explicit_targets, key=lambda item: str(item).lower()):
        if path.exists() or path in {Path(item) for item in removed_paths}:
            continue
        missing_paths.append(str(path))

    return {
        "root_dir": str(root_dir),
        "retention_days": request["retention_days"],
        "dry_run": request["dry_run"],
        "cutoff_utc": cutoff.isoformat(),
        "removed_count": len(removed_paths),
        "kept_count": len(kept_paths),
        "removed_paths": removed_paths,
        "kept_paths": kept_paths,
        "missing_paths": missing_paths,
    }


__all__ = ["cleanup_article_temp_dirs", "normalize_cleanup_request"]
