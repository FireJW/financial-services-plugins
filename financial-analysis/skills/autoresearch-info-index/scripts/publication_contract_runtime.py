#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SHARED_PUBLICATION_CONTRACT_VERSION = "publish-package/v1"
REQUIRED_PUBLICATION_FIELDS = [
    "title",
    "subtitle",
    "lede",
    "sections",
    "content_markdown",
    "content_html",
    "selected_images",
    "cover_plan",
    "platform_hints",
    "style_profile_applied",
    "operator_notes",
    "draft_thesis",
    "citations",
]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_publication_contract(payload: Any) -> dict[str, Any]:
    root = safe_dict(payload)
    contract = safe_dict(root.get("publish_package")) if "publish_package" in root else {}
    if contract:
        return contract
    contract_path = clean_text(root.get("publish_package_path") or root.get("input_path"))
    if contract_path:
        loaded = json.loads(Path(contract_path).read_text(encoding="utf-8-sig"))
        loaded_root = safe_dict(loaded)
        return safe_dict(loaded_root.get("publish_package")) if "publish_package" in loaded_root else loaded_root
    return root


def validate_publication_contract(payload: Any) -> dict[str, Any]:
    contract = load_publication_contract(payload)
    missing_fields = [field for field in REQUIRED_PUBLICATION_FIELDS if field not in contract]
    return {
        "status": "ok" if not missing_fields else "error",
        "missing_fields": missing_fields,
        "contract_version": clean_text(contract.get("contract_version")),
    }


__all__ = [
    "REQUIRED_PUBLICATION_FIELDS",
    "SHARED_PUBLICATION_CONTRACT_VERSION",
    "load_publication_contract",
    "validate_publication_contract",
]
