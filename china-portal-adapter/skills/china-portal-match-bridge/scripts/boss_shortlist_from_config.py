#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from china_portal_match_bridge_runtime import run_china_portal_match_bridge, write_json, write_text


DEFAULT_CONFIG_PATH = Path(r"D:\career-ops-local\config\china_portal_adapter.local.json")
DEFAULT_PROFILE_DIR = Path(r"D:\career-ops-local\profile")
DEFAULT_TRACKER_PATH = Path(r"D:\career-ops-local\applications\tracker.csv")
DEFAULT_UPSTREAM_ROOT = Path(r"D:\career-ops-upstream")
DEFAULT_OUTPUTS_ROOT = Path(r"D:\career-ops-local\outputs\china-portal-adapter")


def parse_csv_like(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_run_root(outputs_root: str | Path) -> Path:
    return Path(outputs_root).expanduser().resolve() / "boss-shortlist" / timestamp_slug()


def prepare_output_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    resolved_run_root = getattr(args, "_resolved_run_root", "")
    if resolved_run_root:
        run_root = Path(resolved_run_root)
    else:
        run_root = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_run_root(args.outputs_root)
        args._resolved_run_root = str(run_root)
    output_path = Path(args.output).expanduser().resolve() if args.output else run_root / "boss-shortlist-result.json"
    markdown_output_path = (
        Path(args.markdown_output).expanduser().resolve()
        if args.markdown_output
        else run_root / "boss-shortlist-report.md"
    )
    return run_root, output_path, markdown_output_path


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    output_dir, _, _ = prepare_output_paths(args)
    adapter_request: dict[str, Any] = {
        "task": "scan_jobs",
        "config_path": str(Path(args.config_path).expanduser().resolve()),
        "platforms": ["boss"],
        "fixture": {"enabled": False},
        "live_scan": {
            "enabled": True,
            "timeout_ms": args.timeout_ms,
            "max_jobs": args.max_jobs,
        },
    }
    keywords = parse_csv_like(args.keywords)
    cities = parse_csv_like(args.cities)
    if keywords:
        adapter_request["keywords"] = keywords
    if cities:
        adapter_request["cities"] = cities
    if args.minimum_monthly_rmb > 0:
        adapter_request["salary_filters"] = {"minimum_monthly_rmb": args.minimum_monthly_rmb}

    return {
        "adapter_request": adapter_request,
        "role_pack": args.role_pack,
        "candidate_profile_dir": str(Path(args.candidate_profile_dir).expanduser().resolve()),
        "tracker_path": str(Path(args.tracker_path).expanduser().resolve()),
        "output_dir": str(output_dir),
        "minimum_fit_score": args.minimum_fit_score,
        "top_n": args.top_n,
        "emit_tailor_queue": True,
        "tailor_execution_strategy": args.tailor_execution_strategy,
        "tailor_export_pdf": args.tailor_export_pdf,
        "upstream_root": str(Path(args.upstream_root).expanduser().resolve()),
        "language": args.language,
        "dry_run": args.dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Boss live scan and immediately produce a local shortlist + tailor queue.")
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--candidate-profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--tracker-path", default=str(DEFAULT_TRACKER_PATH))
    parser.add_argument("--upstream-root", default=str(DEFAULT_UPSTREAM_ROOT))
    parser.add_argument("--outputs-root", default=str(DEFAULT_OUTPUTS_ROOT))
    parser.add_argument("--keywords", help="Comma-separated keyword overrides.")
    parser.add_argument("--cities", help="Comma-separated city overrides.")
    parser.add_argument("--minimum-monthly-rmb", type=int, default=0)
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--max-jobs", type=int, default=20)
    parser.add_argument("--role-pack", default="ai_platform_pm")
    parser.add_argument("--minimum-fit-score", type=int, default=60)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--tailor-execution-strategy", default="hybrid")
    parser.add_argument("--tailor-export-pdf", action="store_true")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--output")
    parser.add_argument("--markdown-output")
    args = parser.parse_args()

    request = build_request(args)
    result = run_china_portal_match_bridge(request)
    _, output_path, markdown_output_path = prepare_output_paths(args)
    artifacts = result.setdefault("artifacts", {})
    artifacts["result_json"] = str(output_path)
    artifacts["report_markdown"] = str(markdown_output_path)
    write_json(output_path, result)
    write_text(markdown_output_path, result.get("report_markdown", ""))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
