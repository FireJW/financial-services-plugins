#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from x_stock_picker_style_runtime import (
    build_batch_markdown_report,
    build_markdown_report,
    load_json,
    run_x_stock_picker_style,
    run_x_stock_picker_style_batch,
    write_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the X stock-picker style learning workflow.")
    parser.add_argument("request_json", help="Path to the request JSON file.")
    parser.add_argument("--output", help="Write the JSON result to this path.")
    parser.add_argument("--markdown-output", help="Write the markdown report to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request_path = Path(args.request_json).expanduser().resolve()
    request = load_json(request_path)
    is_batch = bool(request.get("selected_handles")) or request.get("mode") == "batch"
    result = run_x_stock_picker_style_batch(request) if is_batch else run_x_stock_picker_style(request)
    markdown = result.get("report_markdown") or (build_batch_markdown_report(result) if is_batch else build_markdown_report(result))

    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output).expanduser().resolve()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(str(markdown), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
