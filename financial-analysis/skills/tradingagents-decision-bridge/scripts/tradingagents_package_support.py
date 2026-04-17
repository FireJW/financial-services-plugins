#!/usr/bin/env python3
from __future__ import annotations

from importlib import import_module, metadata
from pathlib import Path
import re
from typing import Any, Callable


VersionLookup = Callable[[str], str]
VERSION_PATTERNS = (
    re.compile(r"__version__\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]"),
)
PROBE_IMPORT_MODULES = (
    "tradingagents",
    "tradingagents.default_config",
    "tradingagents.graph.trading_graph",
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def package_origin(spec: Any) -> str:
    origin = clean_text(getattr(spec, "origin", ""))
    if origin and origin != "namespace":
        return origin
    for location in getattr(spec, "submodule_search_locations", []) or []:
        text = clean_text(location)
        if text:
            return text
    return ""


def extract_version_from_init(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return ""
    for pattern in VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1))
    return ""


def resolve_package_version(
    package_name: str,
    *,
    spec: Any = None,
    version_lookup: VersionLookup | None = None,
) -> str:
    if version_lookup is not None:
        try:
            version = clean_text(version_lookup(package_name))
        except Exception:
            version = ""
        if version:
            return version

    try:
        version = clean_text(metadata.version(package_name))
    except Exception:
        version = ""
    if version:
        return version

    candidate_paths: list[Path] = []
    origin = clean_text(getattr(spec, "origin", ""))
    if origin and origin != "namespace":
        candidate_paths.append(Path(origin))
    for location in getattr(spec, "submodule_search_locations", []) or []:
        text = clean_text(location)
        if text:
            candidate_paths.append(Path(text) / "__init__.py")

    for path in candidate_paths:
        version = extract_version_from_init(path)
        if version:
            return version

    try:
        module = import_module(package_name)
    except Exception:
        return ""
    return clean_text(getattr(module, "__version__", ""))


def probe_runtime_imports() -> tuple[bool, str]:
    for module_name in PROBE_IMPORT_MODULES:
        try:
            import_module(module_name)
        except Exception as exc:
            message = clean_text(str(exc))
            if message:
                return False, f"{exc.__class__.__name__}: {message}"
            return False, f"{exc.__class__.__name__}: failed to import {module_name}"
    return True, ""
