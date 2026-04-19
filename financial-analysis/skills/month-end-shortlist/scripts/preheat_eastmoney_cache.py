#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def unique_tickers(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        ticker = " ".join(str(raw or "").split()).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        ordered.append(ticker)
    return ordered


def parse_cli_tickers(raw: str) -> list[str]:
    return unique_tickers(part for part in str(raw or "").split(","))


def parse_tickers_file(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Ticker json file must contain an array of strings.")
        return unique_tickers(payload)
    return unique_tickers(text.splitlines())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preheat Eastmoney cache for selected tickers.")
    parser.add_argument("--tickers", default="", help="Comma-separated ticker list.")
    parser.add_argument("--tickers-file", default="", help="Path to txt/json ticker file.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    tickers = parse_cli_tickers(args.tickers)
    if args.tickers_file:
        tickers.extend(parse_tickers_file(Path(args.tickers_file)))
    tickers = unique_tickers(tickers)
    if not tickers:
        parser.error("Provide --tickers or --tickers-file.")
    for ticker in tickers:
        print(ticker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
