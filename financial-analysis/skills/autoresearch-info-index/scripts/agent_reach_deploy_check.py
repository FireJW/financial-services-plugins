#!/usr/bin/env python3
"""
Run a local deployment check for a separate Agent Reach installation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_reach_deploy_check_runtime import load_json, run_agent_reach_deploy_check, write_json


def emit_json(payload: dict, *, stream: object = sys.stdout) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        print(json.dumps(payload, indent=2, ensure_ascii=True), file=stream)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether a separate Agent Reach deployment is present, pinned, and usable."
    )
    parser.add_argument("input", nargs="?", help="Optional path to a deploy-check request JSON file")
    parser.add_argument("--install-root", help="Override the Agent Reach install root to inspect")
    parser.add_argument("--pseudo-home", help="Override the Agent Reach pseudo-home to inspect")
    parser.add_argument("--python-binary", help="Override the expected full Python binary path")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument("--markdown-output", help="Optional path to save the markdown report")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write requested files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        payload = load_json(Path(args.input).resolve()) if args.input else {}
        if args.install_root:
            payload["install_root"] = args.install_root
        if args.pseudo_home:
            payload["pseudo_home"] = args.pseudo_home
        if args.python_binary:
            payload["python_binary"] = args.python_binary
        result = run_agent_reach_deploy_check(payload)
        if not args.quiet:
            emit_json(result)

        if args.output:
            write_json(Path(args.output).resolve(), result)
        if args.markdown_output:
            output_path = Path(args.markdown_output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
        sys.exit(0 if result.get("core_channels_ready") else 1)
    except Exception as exc:
        emit_json({"status": "ERROR", "message": str(exc)}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
