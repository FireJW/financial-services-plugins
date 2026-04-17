#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_root_dir(value: Any) -> Path:
    text = clean_text(value)
    if not text:
        raise ValueError("root_dir is required")
    return Path(text).expanduser().resolve()


def remove_tree(path: Path, *, dry_run: bool) -> bool:
    if dry_run:
        return True
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def candidate_directories(root_dir: Path, explicit_paths: list[Any]) -> list[Path]:
    explicit = []
    for item in safe_list(explicit_paths):
        text = clean_text(item)
        if text:
            explicit.append(Path(text).expanduser().resolve())
    if explicit:
        return explicit
    if not root_dir.exists():
        return []
    return [item for item in root_dir.iterdir() if item.is_dir()]


def cleanup_article_temp_dirs(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = raw_request if isinstance(raw_request, dict) else {}
    root_dir = parse_root_dir(request.get("root_dir"))
    retention_days = max(0, int(request.get("retention_days", 4) or 0))
    dry_run = bool(request.get("dry_run"))
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    removed_paths: list[str] = []
    kept_paths: list[str] = []
    missing_paths: list[str] = []

    for path in candidate_directories(root_dir, request.get("explicit_paths")):
        if not path.exists():
            missing_paths.append(str(path))
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified_at < cutoff:
            if remove_tree(path, dry_run=dry_run):
                removed_paths.append(str(path))
        else:
            kept_paths.append(str(path))

    return {
        "status": "ok",
        "root_dir": str(root_dir),
        "retention_days": retention_days,
        "dry_run": dry_run,
        "removed_count": len(removed_paths),
        "kept_count": len(kept_paths),
        "missing_count": len(missing_paths),
        "removed_paths": removed_paths,
        "kept_paths": kept_paths,
        "missing_paths": missing_paths,
    }


__all__ = ["cleanup_article_temp_dirs"]
