#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import write_json
from article_publish_regression_check_runtime import run_publish_regression_check
from cli_output import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a publish workflow output directory against the article regression checks."
    )
    parser.add_argument("target", help="Publish output directory, publish-package.json, or article-publish-result.json")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = run_publish_regression_check({"target": args.target})
        if not args.quiet:
            print_json(result)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0 if result.get("accepted") else 1)
    except Exception as exc:
        print_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
