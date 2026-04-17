#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_decision_bridge_runtime import load_json, run_tradingagents_decision_bridge, write_json


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def parse_optional_bool(value: str | None) -> bool | None:
    text = clean_text(value).lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Unsupported boolean value: {value}")


def apply_cli_overrides(request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    payload = dict(request)
    if args.enabled is not None:
        payload["enabled"] = args.enabled
    if clean_text(args.analysis_profile):
        payload["analysis_profile"] = clean_text(args.analysis_profile)
    if clean_text(args.ticker):
        payload["ticker"] = clean_text(args.ticker)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded TradingAgents decision bridge.")
    parser.add_argument("request_json", help="Path to the request JSON file.")
    parser.add_argument("--output", help="Write the JSON result to this path.")
    parser.add_argument("--markdown-output", help="Write the markdown report to this path.")
    parser.add_argument("--enabled", type=parse_optional_bool, help="Override request.enabled for this run.")
    parser.add_argument("--analysis-profile", help="Override request.analysis_profile for this run.")
    parser.add_argument("--ticker", help="Override request.ticker for this run.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request_path = Path(args.request_json).expanduser().resolve()
    request = apply_cli_overrides(load_json(request_path), args)
    result = run_tradingagents_decision_bridge(request)

    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output).expanduser().resolve()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(str(result.get("report_markdown", "")), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
