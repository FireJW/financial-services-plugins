#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TEMPLATE = REPO_ROOT / "china-portal-adapter" / "skills" / "china-portal-adapter" / "templates" / "china_portal_adapter.local.template.json"
DEFAULT_TARGET = Path(r"D:\career-ops-local\config\china_portal_adapter.local.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def deep_merge_defaults(current: Any, template: Any) -> Any:
    if isinstance(current, dict) and isinstance(template, dict):
        merged = {key: deep_merge_defaults(current.get(key), value) for key, value in template.items()}
        for key, value in current.items():
            if key not in merged:
                merged[key] = value
        return merged
    if current in ("", [], {}) and template not in ("", [], {}):
        return template
    if current is None:
        return template
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge the repo template into the local China portal adapter config.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    template_path = Path(args.template).expanduser().resolve()
    target_path = Path(args.target).expanduser().resolve()

    template = load_json(template_path)
    current = {}
    if target_path.exists():
        current = load_json(target_path)
    merged = deep_merge_defaults(current, template)
    write_json(target_path, merged, args.dry_run)
    print(
        json.dumps(
            {
                "status": "ready",
                "template": str(template_path),
                "target": str(target_path),
                "dry_run": bool(args.dry_run),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
