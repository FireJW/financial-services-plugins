#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from china_portal_match_bridge_runtime import run_china_portal_match_bridge, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the China portal shortlist bridge.")
    parser.add_argument("request", help="Path to the request JSON file.")
    parser.add_argument("--output", help="Optional result JSON output path.")
    parser.add_argument("--markdown-output", help="Optional Markdown report output path.")
    args = parser.parse_args()

    request_path = Path(args.request).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    result = run_china_portal_match_bridge(request)
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
    if args.markdown_output:
        write_text(Path(args.markdown_output).expanduser().resolve(), result.get("report_markdown", ""))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
