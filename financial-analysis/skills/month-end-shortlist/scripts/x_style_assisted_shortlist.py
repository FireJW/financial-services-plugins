#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from month_end_shortlist_runtime import build_markdown_report, load_json, normalize_request, run_month_end_shortlist, write_json


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def normalize_handle_list(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: list[str] = []
    for value in values:
        for chunk in str(value or "").split(","):
            handle = clean_text(chunk).lstrip("@")
            if handle and handle not in seen:
                seen.append(handle)
    return seen


def build_x_style_assisted_request(
    base_request: dict[str, Any],
    *,
    x_style_batch_result_path: str,
    selected_handles: list[str] | tuple[str, ...] | None = None,
    analysis_time: str = "",
) -> dict[str, Any]:
    request = dict(base_request)
    request["x_style_batch_result_path"] = clean_text(x_style_batch_result_path)
    normalized_handles = normalize_handle_list(list(selected_handles or []))
    if normalized_handles:
        request["x_style_selected_handles"] = normalized_handles
    if clean_text(analysis_time):
        request["analysis_time"] = clean_text(analysis_time)
    return request


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run month_end_shortlist with X-style overlays.")
    parser.add_argument("base_request_json", help="Base month-end shortlist request JSON.")
    parser.add_argument("--x-style-batch-result", required=True, help="Path to the X-style batch result JSON.")
    parser.add_argument("--handles", nargs="*", default=[], help="Optional X handles to keep.")
    parser.add_argument("--analysis-time", default="", help="Optional analysis_time override.")
    parser.add_argument("--request-output", help="Write resolved request JSON to this path.")
    parser.add_argument("--request-output-only", action="store_true", help="Only write the resolved request and exit.")
    parser.add_argument("--output", help="Write shortlist result JSON to this path.")
    parser.add_argument("--markdown-output", help="Write shortlist report markdown to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request = build_x_style_assisted_request(
        load_json(Path(args.base_request_json)),
        x_style_batch_result_path=args.x_style_batch_result,
        selected_handles=args.handles,
        analysis_time=args.analysis_time,
    )
    if args.request_output:
        write_json(args.request_output, request)
    if args.request_output_only:
        return 0

    result = run_month_end_shortlist(request)
    if args.output:
        write_json(args.output, result)
    if args.markdown_output:
        Path(args.markdown_output).expanduser().resolve().write_text(build_markdown_report(result), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
