#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_reuse_runtime import build_reuse_publish_result, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reuse a prior publish run and a revised article result to rebuild a WeChat publish package.")
    parser.add_argument("base_publish_result", help="Path to an existing article-publish-result.json")
    parser.add_argument("revised_article_result", help="Path to an article-revise result JSON")
    parser.add_argument("--output-dir", help="Optional directory for the rebuilt publish package")
    parser.add_argument("--output", help="Optional path to save the reuse result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the automatic acceptance markdown")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = {
        "base_publish_result_path": str(Path(args.base_publish_result).resolve()),
        "revised_article_result_path": str(Path(args.revised_article_result).resolve()),
    }
    if args.output_dir:
        payload["output_dir"] = str(Path(args.output_dir).resolve())
    return payload


def main() -> None:
    args = parse_args()
    try:
        result = build_reuse_publish_result(build_payload(args))
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
        print(json.dumps({"status": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
