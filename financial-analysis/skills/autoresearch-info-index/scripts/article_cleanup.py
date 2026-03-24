#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_cleanup_runtime import cleanup_article_temp_dirs
from article_draft_flow_runtime import write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up stale or explicitly selected article workflow temp directories.")
    parser.add_argument("--root-dir", help="Root temp directory to scan. Defaults to .tmp in the current workspace.")
    parser.add_argument("--retention-days", type=int, default=4, help="Delete article temp directories older than this many days.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting it.")
    parser.add_argument(
        "--explicit-path",
        action="append",
        default=[],
        help="Delete this specific directory regardless of age. Can be supplied multiple times.",
    )
    parser.add_argument("--output", help="Optional path to save the cleanup result JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = cleanup_article_temp_dirs(
        {
            "root_dir": args.root_dir,
            "retention_days": args.retention_days,
            "dry_run": args.dry_run,
            "explicit_paths": args.explicit_path,
        }
    )
    if not args.quiet:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.output:
        write_json(Path(args.output).resolve(), result)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
