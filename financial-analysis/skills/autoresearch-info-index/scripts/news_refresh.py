#!/usr/bin/env python3
"""
Refresh a prior news-index result with new high-recency observations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from news_index_runtime import load_json, merge_refresh, write_json


def parse_args() -> argparse.Namespace:
    default_existing = SCRIPT_DIR.parent / "examples" / "news-index-crisis-result.json"
    default_refresh = SCRIPT_DIR.parent / "examples" / "news-index-refresh-update.json"
    parser = argparse.ArgumentParser(
        description="Refresh a prior news-index result with a smaller recent-window update."
    )
    parser.add_argument(
        "existing_result",
        nargs="?",
        default=str(default_existing),
        help="Path to an existing news-index result JSON file",
    )
    parser.add_argument(
        "refresh_request",
        nargs="?",
        default=str(default_refresh),
        help="Path to a refresh retrieval_request JSON file",
    )
    parser.add_argument("--output", help="Optional path to save the refreshed result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the refreshed markdown report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write requested files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        existing = load_json(Path(args.existing_result).resolve())
        refresh_payload = load_json(Path(args.refresh_request).resolve())
        result = merge_refresh(existing, refresh_payload)
        if not args.quiet:
            print(json.dumps(result, indent=2, ensure_ascii=False))

        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0)
    except Exception as exc:
        print(
            json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
