#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def is_usable_runtime_root(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".runtime-write-probe-{uuid4().hex}"
        probe.mkdir()
        probe.rmdir()
    except OSError:
        return False
    return path.is_dir()


def resolve_runtime_root(path_value: Any = None) -> Path:
    explicit = clean_text(path_value)
    if explicit:
        return Path(explicit).expanduser().resolve()

    for env_name in ("FINANCIAL_ANALYSIS_RUNTIME_ROOT", "CODEX_RUNTIME_ROOT"):
        env_value = clean_text(os.environ.get(env_name))
        if env_value:
            candidate = Path(env_value).expanduser().resolve()
            if is_usable_runtime_root(candidate):
                return candidate

    fallback = (Path.cwd() / ".tmp").resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def runtime_subdir(*parts: str) -> Path:
    path = resolve_runtime_root()
    for part in parts:
        clean_part = clean_text(part)
        if clean_part:
            path = path / clean_part
    return path


__all__ = ["is_usable_runtime_root", "resolve_runtime_root", "runtime_subdir"]
