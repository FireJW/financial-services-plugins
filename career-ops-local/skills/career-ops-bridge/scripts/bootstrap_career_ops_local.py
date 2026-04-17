#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_ROOT = SCRIPT_DIR.parent / "templates" / "private-local"
DEFAULT_ROOT = Path(r"D:\career-ops-local")
DEFAULT_UPSTREAM_ROOT = Path(r"D:\career-ops-upstream")

TEMPLATE_MAP = {
    "profile/master_resume.template.md": "profile/master_resume.md",
    "profile/brag_bank.template.md": "profile/brag_bank.md",
    "profile/stories_bank.template.yml": "profile/stories_bank.yml",
    "profile/constraints.template.yml": "profile/constraints.yml",
    "roles/ai_platform_pm.template.yml": "roles/ai_platform_pm.yml",
    "roles/general_pm.template.yml": "roles/general_pm.yml",
    "roles/product_strategy_ops.template.yml": "roles/product_strategy_ops.yml",
    "config/portals.template.yml": "config/portals.yml",
    "config/career_ops.local.template.json": "config/career_ops.local.json",
    "applications/tracker.template.csv": "applications/tracker.csv",
}


def now_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write_text(path: Path, payload: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def tool_snapshot() -> dict[str, Any]:
    return {
        "node": shutil.which("node") or "",
        "npx": shutil.which("npx") or "",
        "claude": shutil.which("claude") or "",
        "git": shutil.which("git") or "",
    }


def copy_templates(root: Path, force: bool, dry_run: bool) -> list[str]:
    created: list[str] = []
    for template_rel, target_rel in TEMPLATE_MAP.items():
        source = TEMPLATES_ROOT / template_rel
        target = root / target_rel
        if target.exists() and not force:
            continue
        created.append(str(target))
        write_text(target, source.read_text(encoding="utf-8"), dry_run)
    return created


def maybe_clone_upstream(upstream_root: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    created: list[str] = []
    warnings: list[str] = []
    git_path = shutil.which("git")
    if upstream_root.exists():
        return created, warnings
    if not git_path:
        warnings.append("Git was not found on PATH, so the upstream checkout was not cloned.")
        return created, warnings
    if dry_run:
        created.append(str(upstream_root))
        return created, warnings
    subprocess.run([git_path, "clone", "https://github.com/santifer/career-ops.git", str(upstream_root)], check=True)
    created.append(str(upstream_root))
    return created, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the private career-ops-local workspace.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--upstream-root", default=str(DEFAULT_UPSTREAM_ROOT))
    parser.add_argument("--clone-upstream", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    upstream_root = Path(args.upstream_root).expanduser().resolve()
    created: list[str] = []
    warnings: list[str] = []

    for rel in ["profile", "roles", "jobs/inbox", "jobs/normalized", "applications/packs", "outputs", "config"]:
        path = root / rel
        created.append(str(path))
        ensure_dir(path, args.dry_run)
    created.extend(copy_templates(root, args.force, args.dry_run))

    if not args.clone_upstream:
        created.append(str(upstream_root))
        ensure_dir(upstream_root, args.dry_run)
        placeholder = upstream_root / "README.local.txt"
        if not placeholder.exists() or args.force:
            write_text(
                placeholder,
                "Clone or place the external career-ops checkout here when you want optional upstream augmentation.\n",
                args.dry_run,
            )
            created.append(str(placeholder))
    else:
        clone_created, clone_warnings = maybe_clone_upstream(upstream_root, args.dry_run)
        created.extend(clone_created)
        warnings.extend(clone_warnings)

    result = {
        "status": "ready",
        "root": str(root),
        "upstream_root": str(upstream_root),
        "created": created,
        "warnings": warnings,
        "tools": tool_snapshot(),
        "generated_at": now_z(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
