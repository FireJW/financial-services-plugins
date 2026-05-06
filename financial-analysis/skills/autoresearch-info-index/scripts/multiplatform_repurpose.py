#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from cli_output import print_json
from multiplatform_repurpose_runtime import build_multiplatform_repurpose, load_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repurpose one source Markdown article into platform-native content packages."
    )
    parser.add_argument("input", help="Path to a multiplatform repurpose request JSON")
    parser.add_argument("--out", "--output-dir", dest="output_dir", help="Optional output directory override")
    parser.add_argument("--output", help="Optional path to save the final manifest JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request_path = Path(args.input).resolve()
    payload = load_json(request_path)
    if args.output_dir:
        payload["output_dir"] = str(Path(args.output_dir).resolve())
    result = build_multiplatform_repurpose(payload, base_dir=request_path.parent)
    if args.output:
        write_json(Path(args.output).resolve(), result)
    if not args.quiet:
        print_json(result)


if __name__ == "__main__":
    main()
