#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xhs_workflow_runtime import build_readiness_report, load_json, run_xhs_workflow, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local Xiaohongshu GPT Image workflow package.")
    parser.add_argument("input", help="Path to xhs workflow request JSON")
    parser.add_argument("--benchmark-file", help="Optional imported benchmark JSON file")
    parser.add_argument("--benchmark-source", help="Optional benchmark source label")
    parser.add_argument("--doctor", action="store_true", help="Check request readiness without generating a package")
    parser.add_argument("--run-collector", action="store_true", help="Run the configured collector before building the package")
    parser.add_argument(
        "--run-publish-preview",
        action="store_true",
        help="Run the configured fill-publish preview after package generation; never clicks publish",
    )
    parser.add_argument("--image-mode", choices=["dry_run", "openai"], help="Override image_generation.mode")
    parser.add_argument("--image-model", help="Override image_generation.model")
    parser.add_argument("--image-size", help="Override image_generation.size")
    parser.add_argument("--reference-image", action="append", default=[], help="Add a local reference image path for GPT Image edits")
    parser.add_argument("--performance-file", help="Optional XHS detail JSON to import into performance review")
    parser.add_argument("--output", help="Optional path to save summary JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON")
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict:
    payload = load_json(Path(args.input).resolve())
    if args.benchmark_file:
        payload["benchmark_file"] = args.benchmark_file
    if args.benchmark_source:
        payload["benchmark_source"] = args.benchmark_source
    if args.run_collector:
        collector = dict(payload.get("collector") or {})
        collector["auto_run"] = True
        payload["collector"] = collector
    if args.run_publish_preview:
        publish = dict(payload.get("publish") or {})
        publish["auto_run_preview"] = True
        publish["click_publish"] = False
        payload["publish"] = publish
    if args.image_mode or args.image_model or args.image_size or args.reference_image:
        image_generation = dict(payload.get("image_generation") or {})
        if args.image_mode:
            image_generation["mode"] = args.image_mode
        if args.image_model:
            image_generation["model"] = args.image_model
        if args.image_size:
            image_generation["size"] = args.image_size
        if args.reference_image:
            image_generation["reference_images"] = list(args.reference_image)
        payload["image_generation"] = image_generation
    if args.performance_file:
        payload["performance_file"] = args.performance_file
    return payload


def main() -> None:
    args = parse_args()
    try:
        payload = build_payload(args)
        result = build_readiness_report(payload) if args.doctor else run_xhs_workflow(payload)
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if not args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1 if args.doctor and result.get("status") == "blocked" else 0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
