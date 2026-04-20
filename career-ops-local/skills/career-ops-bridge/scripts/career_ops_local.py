#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


run_career_ops_local: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local-first career ops bridge.")
    parser.add_argument("request", help="Path to the request JSON file.")
    parser.add_argument("--output", help="Optional result JSON output path.")
    parser.add_argument("--markdown-output", help="Optional Markdown report output path.")
    return parser.parse_args(argv)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def resolve_runtime() -> Callable[[dict[str, Any]], dict[str, Any]]:
    if run_career_ops_local is not None:
        return run_career_ops_local

    try:
        from career_ops_local_runtime import run_career_ops_local as runtime_func
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "career_ops_local_runtime is missing. Restore the runtime source before executing this CLI."
        ) from exc

    globals()["run_career_ops_local"] = runtime_func
    return runtime_func


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    request_path = Path(args.request).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    result = resolve_runtime()(request)

    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
    if args.markdown_output:
        write_text(
            Path(args.markdown_output).expanduser().resolve(),
            str(result.get("report_markdown", "")),
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
