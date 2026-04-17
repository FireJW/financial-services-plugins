#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable


REPORT_DIR_NAME = "automation-cleanup"
BATCH_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
DEFAULT_FIXED_SESSION_IDS = ("019d15d9-a364-78c1-b513-1ff666cd3df1",)
DEFAULT_TMP_DIR_NAMES = {
    "cc-recovered-main",
    "claude-code-secret-features",
    "macro-note-workflow",
}
DEFAULT_TMP_DIR_PREFIXES = (
    "debug-",
    "snapshot-",
    "test-",
    "tmp-",
)
DEFAULT_TMP_DIR_SUFFIXES = (
    "-debug",
    "-snapshot",
    "-tests",
)


@dataclass(frozen=True)
class CleanupConfig:
    repo_root: Path
    codex_home: Path
    dry_run: bool = False
    session_days: int = 60
    stock_history_days: int = 30
    gs_quant_days: int = 14
    tmp_dir_days: int = 14
    quarantine_days: int = 7
    today: date | None = None
    fixed_session_ids: tuple[str, ...] = DEFAULT_FIXED_SESSION_IDS

    @property
    def tmp_root(self) -> Path:
        return self.repo_root / ".tmp"

    @property
    def stock_watch_root(self) -> Path:
        return self.tmp_root / "stock-watch-workflow"

    @property
    def sessions_root(self) -> Path:
        return self.codex_home / "sessions"

    @property
    def sessions_quarantine_root(self) -> Path:
        return self.codex_home / "quarantine" / REPORT_DIR_NAME

    @property
    def tmp_quarantine_root(self) -> Path:
        return self.tmp_root / REPORT_DIR_NAME / "quarantine"

    @property
    def report_root(self) -> Path:
        return self.tmp_root / REPORT_DIR_NAME

    def run_date(self) -> date:
        return self.today or date.today()


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def normalize_path(value: str | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser().resolve()


def path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def latest_mtime(path: Path) -> datetime:
    try:
        latest = path.stat().st_mtime
    except OSError:
        latest = 0
    if path.is_dir():
        for child in path.rglob("*"):
            try:
                latest = max(latest, child.stat().st_mtime)
            except OSError:
                continue
    return datetime.fromtimestamp(latest, tz=UTC)


def batch_dir_timestamp(path: Path) -> datetime:
    try:
        return datetime.strptime(path.name, BATCH_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return latest_mtime(path)


def looks_like_safe_tmp_dir(path: Path) -> bool:
    name = path.name.lower()
    if name in DEFAULT_TMP_DIR_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in DEFAULT_TMP_DIR_PREFIXES):
        return True
    return any(name.endswith(suffix) for suffix in DEFAULT_TMP_DIR_SUFFIXES)


def format_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def preview_paths(paths: list[str], limit: int = 10) -> list[str]:
    if len(paths) <= limit:
        return paths
    preview = list(paths[:limit])
    preview.append(f"... and {len(paths) - limit} more")
    return preview


def sorted_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda item: str(item).lower())


def collect_session_candidates(config: CleanupConfig) -> list[Path]:
    root = config.sessions_root
    if not root.exists():
        return []
    candidates: list[Path] = []
    for path in root.rglob("*.jsonl"):
        if any(session_id in path.name for session_id in config.fixed_session_ids):
            continue
        candidates.append(path)
    return sorted_paths(candidates)


def collect_stock_history_candidates(config: CleanupConfig) -> list[Path]:
    history_glob = config.stock_watch_root.glob("cases/*/history/**/*")
    return sorted_paths(path for path in history_glob if path.is_file())


def collect_gs_quant_candidates(config: CleanupConfig) -> list[Path]:
    root = config.stock_watch_root / "gs-quant"
    if not root.exists():
        return []
    return sorted_paths(path for path in root.iterdir() if path.is_dir())


def collect_generic_tmp_dir_candidates(config: CleanupConfig) -> list[Path]:
    root = config.tmp_root
    if not root.exists():
        return []
    candidates: list[Path] = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        if path.name in {"automation-cleanup", "stock-watch-workflow"}:
            continue
        if looks_like_safe_tmp_dir(path):
            candidates.append(path)
    return sorted_paths(candidates)


def move_to_quarantine(
    *,
    rule_name: str,
    candidates: list[Path],
    retention_days: int,
    preserve_base: Path,
    quarantine_root: Path,
    batch_id: str,
    dry_run: bool,
) -> dict[str, object]:
    cutoff = now_utc() - timedelta(days=retention_days)
    moved_paths: list[str] = []
    kept_paths: list[str] = []
    skipped: list[dict[str, str]] = []
    prune_targets: list[tuple[Path, Path]] = []
    moved_bytes = 0

    for path in candidates:
        modified_at = latest_mtime(path)
        if modified_at >= cutoff:
            kept_paths.append(str(path))
            continue

        try:
            relative_path = path.resolve().relative_to(preserve_base.resolve())
        except ValueError:
            skipped.append({"path": str(path), "reason": "path is outside the configured preserve base"})
            continue

        source_size = path_size_bytes(path)
        path_is_file = path.is_file()
        moved_bytes += source_size
        moved_paths.append(str(path))
        if dry_run:
            continue

        destination = quarantine_root / batch_id / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(path), str(destination))
        except Exception as exc:  # pragma: no cover - defensive skip path
            skipped.append({"path": str(path), "reason": f"move failed: {exc}"})
            moved_paths.pop()
            moved_bytes -= source_size
            continue

        if path_is_file:
            if "sessions" in path.parts:
                prune_targets.append((path.parent, preserve_base / "sessions"))
            elif "history" in path.parts:
                history_index = path.parts.index("history")
                history_root = Path(*path.parts[: history_index + 1])
                prune_targets.append((path.parent, history_root))

    if not dry_run:
        for current, stop_at in prune_targets:
            prune_empty_dirs(current, stop_at)

    return {
        "rule_name": rule_name,
        "retention_days": retention_days,
        "cutoff_utc": isoformat(cutoff),
        "candidate_count": len(candidates),
        "eligible_count": len(moved_paths) + len(skipped),
        "moved_count": len(moved_paths),
        "kept_count": len(kept_paths),
        "skipped_count": len(skipped),
        "moved_bytes": moved_bytes,
        "moved_paths": moved_paths,
        "kept_paths_preview": preview_paths(kept_paths),
        "skipped": skipped,
        "quarantine_root": str(quarantine_root),
        "batch_id": batch_id,
    }


def prune_empty_dirs(start_dir: Path, stop_at: Path) -> None:
    current = start_dir
    stop_at_resolved = stop_at.resolve()
    while current.exists():
        try:
            current_resolved = current.resolve()
        except OSError:
            break
        if current_resolved == stop_at_resolved:
            break
        try:
            if any(current.iterdir()):
                break
            current.rmdir()
        except OSError:
            break
        current = current.parent


def run_quarantine_stage(config: CleanupConfig, *, batch_id: str) -> dict[str, object]:
    rules = [
        move_to_quarantine(
            rule_name="codex_sessions",
            candidates=collect_session_candidates(config),
            retention_days=config.session_days,
            preserve_base=config.codex_home,
            quarantine_root=config.sessions_quarantine_root,
            batch_id=batch_id,
            dry_run=config.dry_run,
        ),
        move_to_quarantine(
            rule_name="stock_watch_history",
            candidates=collect_stock_history_candidates(config),
            retention_days=config.stock_history_days,
            preserve_base=config.tmp_root,
            quarantine_root=config.tmp_quarantine_root,
            batch_id=batch_id,
            dry_run=config.dry_run,
        ),
        move_to_quarantine(
            rule_name="stock_watch_gs_quant",
            candidates=collect_gs_quant_candidates(config),
            retention_days=config.gs_quant_days,
            preserve_base=config.tmp_root,
            quarantine_root=config.tmp_quarantine_root,
            batch_id=batch_id,
            dry_run=config.dry_run,
        ),
        move_to_quarantine(
            rule_name="generic_tmp_dirs",
            candidates=collect_generic_tmp_dir_candidates(config),
            retention_days=config.tmp_dir_days,
            preserve_base=config.tmp_root,
            quarantine_root=config.tmp_quarantine_root,
            batch_id=batch_id,
            dry_run=config.dry_run,
        ),
    ]
    return {
        "triggered": True,
        "batch_id": batch_id,
        "rules": rules,
        "moved_count": sum(int(rule["moved_count"]) for rule in rules),
        "moved_bytes": sum(int(rule["moved_bytes"]) for rule in rules),
        "skipped_count": sum(int(rule["skipped_count"]) for rule in rules),
    }


def list_quarantine_batches(config: CleanupConfig) -> list[Path]:
    roots = [config.sessions_quarantine_root, config.tmp_quarantine_root]
    batches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_dir():
                batches.append(path)
    return sorted_paths(batches)


def run_purge_stage(config: CleanupConfig, *, force: bool) -> dict[str, object]:
    cutoff = now_utc() - timedelta(days=config.quarantine_days)
    deleted_paths: list[str] = []
    kept_paths: list[str] = []
    skipped: list[dict[str, str]] = []
    deleted_bytes = 0
    candidates = list_quarantine_batches(config)

    for batch_dir in candidates:
        batch_time = batch_dir_timestamp(batch_dir)
        if batch_time >= cutoff:
            kept_paths.append(str(batch_dir))
            continue

        deleted_bytes += path_size_bytes(batch_dir)
        deleted_paths.append(str(batch_dir))
        if config.dry_run:
            continue

        try:
            shutil.rmtree(batch_dir)
        except Exception as exc:  # pragma: no cover - defensive skip path
            skipped.append({"path": str(batch_dir), "reason": f"purge failed: {exc}"})
            deleted_paths.pop()
            deleted_bytes -= path_size_bytes(batch_dir)
            continue

    return {
        "triggered": True,
        "reason": "force purge" if force else f"weekly purge check for quarantine batches older than {config.quarantine_days} day(s)",
        "quarantine_days": config.quarantine_days,
        "cutoff_utc": isoformat(cutoff),
        "candidate_batch_count": len(candidates),
        "deleted_batch_count": len(deleted_paths),
        "deleted_bytes": deleted_bytes,
        "deleted_paths": deleted_paths,
        "kept_paths_preview": preview_paths(kept_paths),
        "skipped": skipped,
    }


def build_summary(
    *,
    mode: str,
    config: CleanupConfig,
    batch_id: str,
    quarantine_stage: dict[str, object] | None,
    purge_stage: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "generated_at": isoformat(now_utc()),
        "mode": mode,
        "dry_run": config.dry_run,
        "repo_root": str(config.repo_root),
        "codex_home": str(config.codex_home),
        "batch_id": batch_id,
        "fixed_session_ids": list(config.fixed_session_ids),
        "quarantine_stage": quarantine_stage or {"triggered": False},
        "purge_stage": purge_stage or {"triggered": False},
    }


def render_summary_markdown(summary: dict[str, object]) -> str:
    quarantine_stage = summary.get("quarantine_stage", {}) or {}
    purge_stage = summary.get("purge_stage", {}) or {}
    lines = [
        "# Safe Automation Cleanup",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Mode: `{summary.get('mode', '')}`",
        f"- Dry run: `{summary.get('dry_run', False)}`",
        f"- Batch id: `{summary.get('batch_id', '')}`",
        "",
        "## Quarantine",
        "",
        f"- Triggered: `{quarantine_stage.get('triggered', False)}`",
    ]
    if quarantine_stage.get("triggered"):
        lines.extend(
            [
                f"- Moved items: `{quarantine_stage.get('moved_count', 0)}`",
                f"- Moved bytes: `{format_bytes(int(quarantine_stage.get('moved_bytes', 0) or 0))}`",
                f"- Skipped items: `{quarantine_stage.get('skipped_count', 0)}`",
                "",
            ]
        )
        for rule in quarantine_stage.get("rules", []):
            rule_payload = rule or {}
            lines.extend(
                [
                    f"### {rule_payload.get('rule_name', 'rule')}",
                    "",
                    f"- Retention days: `{rule_payload.get('retention_days', 0)}`",
                    f"- Candidate count: `{rule_payload.get('candidate_count', 0)}`",
                    f"- Eligible count: `{rule_payload.get('eligible_count', 0)}`",
                    f"- Moved count: `{rule_payload.get('moved_count', 0)}`",
                    f"- Moved bytes: `{format_bytes(int(rule_payload.get('moved_bytes', 0) or 0))}`",
                    f"- Quarantine root: `{rule_payload.get('quarantine_root', '')}`",
                ]
            )
            moved_paths = preview_paths(list(rule_payload.get("moved_paths", []) or []))
            if moved_paths:
                lines.append("- Moved paths:")
                lines.extend(f"  - `{path}`" for path in moved_paths)
            skipped = list(rule_payload.get("skipped", []) or [])
            if skipped:
                lines.append("- Skipped:")
                for item in skipped[:10]:
                    lines.append(f"  - `{item.get('path', '')}`: {item.get('reason', '')}")
            lines.append("")

    lines.extend(
        [
            "## Purge",
            "",
            f"- Triggered: `{purge_stage.get('triggered', False)}`",
            f"- Reason: {purge_stage.get('reason', '')}",
        ]
    )
    if purge_stage.get("triggered"):
        lines.extend(
            [
                f"- Deleted batches: `{purge_stage.get('deleted_batch_count', 0)}`",
                f"- Deleted bytes: `{format_bytes(int(purge_stage.get('deleted_bytes', 0) or 0))}`",
            ]
        )
        deleted_paths = preview_paths(list(purge_stage.get("deleted_paths", []) or []))
        if deleted_paths:
            lines.append("- Deleted paths:")
            lines.extend(f"  - `{path}`" for path in deleted_paths)
        skipped = list(purge_stage.get("skipped", []) or [])
        if skipped:
            lines.append("- Skipped:")
            for item in skipped[:10]:
                lines.append(f"  - `{item.get('path', '')}`: {item.get('reason', '')}")
    return "\n".join(lines).strip() + "\n"


def write_summary_files(
    summary: dict[str, object],
    *,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, str]:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_summary_markdown(summary), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def run_cleanup(
    *,
    mode: str,
    config: CleanupConfig,
    force_purge: bool = False,
) -> dict[str, object]:
    batch_id = now_utc().strftime(BATCH_TIMESTAMP_FORMAT)
    quarantine_stage: dict[str, object] | None = None
    purge_stage: dict[str, object] | None = None

    if mode in {"run", "quarantine"}:
        quarantine_stage = run_quarantine_stage(config, batch_id=batch_id)
    if mode in {"run", "purge-quarantine"}:
        purge_stage = run_purge_stage(config, force=force_purge)

    return build_summary(
        mode=mode,
        config=config,
        batch_id=batch_id,
        quarantine_stage=quarantine_stage,
        purge_stage=purge_stage,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely quarantine and purge old automation artifacts.")
    parser.add_argument("mode", choices=("run", "quarantine", "purge-quarantine"))
    parser.add_argument("--repo-root", help="Override repo root. Defaults to the parent of this script.")
    parser.add_argument("--codex-home", help="Override CODEX_HOME. Defaults to $CODEX_HOME or ~/.codex.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would move or purge without changing files.")
    parser.add_argument("--force-purge", action="store_true", help="Run purge even outside the monthly purge window.")
    parser.add_argument("--today", help="Override the local run date in YYYY-MM-DD format.")
    parser.add_argument("--session-days", type=int, default=60)
    parser.add_argument("--stock-history-days", type=int, default=30)
    parser.add_argument("--gs-quant-days", type=int, default=14)
    parser.add_argument("--tmp-dir-days", type=int, default=14)
    parser.add_argument("--quarantine-days", type=int, default=7)
    parser.add_argument("--output-json", help="Optional JSON summary path.")
    parser.add_argument("--output-markdown", help="Optional Markdown summary path.")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> CleanupConfig:
    repo_root = normalize_path(args.repo_root) or Path(__file__).resolve().parents[1]
    codex_home = normalize_path(args.codex_home) or normalize_path(os.environ.get("CODEX_HOME")) or normalize_path(str(Path.home() / ".codex"))
    if codex_home is None:
        raise ValueError("Could not resolve CODEX_HOME")
    today_value = date.fromisoformat(args.today) if args.today else None
    return CleanupConfig(
        repo_root=repo_root,
        codex_home=codex_home,
        dry_run=bool(args.dry_run),
        session_days=max(1, int(args.session_days)),
        stock_history_days=max(1, int(args.stock_history_days)),
        gs_quant_days=max(1, int(args.gs_quant_days)),
        tmp_dir_days=max(1, int(args.tmp_dir_days)),
        quarantine_days=max(1, int(args.quarantine_days)),
        today=today_value,
    )


def main() -> None:
    args = parse_args()
    config = build_config(args)
    summary = run_cleanup(mode=args.mode, config=config, force_purge=bool(args.force_purge))
    output_json = normalize_path(args.output_json) or (config.report_root / "latest_cleanup_summary.json")
    output_markdown = normalize_path(args.output_markdown) or (config.report_root / "latest_cleanup_summary.md")
    summary["summary_paths"] = write_summary_files(summary, json_path=output_json, markdown_path=output_markdown)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
