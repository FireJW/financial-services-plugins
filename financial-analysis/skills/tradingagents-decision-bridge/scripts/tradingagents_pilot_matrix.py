#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_decision_bridge_runtime import load_json, run_tradingagents_decision_bridge, write_json
from tradingagents_ticker_normalization import detect_market


REPO_ROOT = SCRIPT_DIR.parents[3]
BridgeRunner = Callable[[dict[str, Any]], dict[str, Any]]


def now_utc() -> datetime:
    return datetime.now(UTC)


def isoformat_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_path(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def slugify(text: str) -> str:
    allowed = []
    for char in clean_text(text).lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {".", "_", "-"}:
            allowed.append("-" if char == "." else char)
        else:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "request"


def classify_market(ticker: str) -> str:
    try:
        return detect_market(ticker)
    except ValueError:
        return "UNKNOWN"


def summarize_item(item_id: str, request_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    memo = safe_dict(result.get("decision_memo"))
    decision = safe_dict(memo.get("decision"))
    cost_summary = safe_dict(memo.get("cost_summary"))
    requested_ticker = clean_text(memo.get("requested_ticker"))
    market = classify_market(memo.get("normalized_ticker") or requested_ticker)
    return {
        "id": item_id,
        "request_path": str(request_path),
        "requested_ticker": requested_ticker,
        "normalized_ticker": clean_text(memo.get("normalized_ticker")),
        "upstream_ticker": clean_text(memo.get("upstream_ticker")),
        "market": market,
        "status": clean_text(result.get("status")) or "unknown",
        "memo_status": clean_text(memo.get("status")) or "unknown",
        "decision_action": clean_text(decision.get("action")) or "no_opinion",
        "decision_conviction": clean_text(decision.get("conviction")) or "low",
        "tradingagents_version": clean_text(memo.get("tradingagents_version")) or "unknown",
        "observed_tokens": cost_summary.get("observed_tokens"),
        "observed_latency_ms": cost_summary.get("observed_latency_ms"),
        "warnings_count": len(safe_list(memo.get("warnings"))),
    }


def build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    us_controls = [item for item in items if item["requested_ticker"] in {"NVDA", "AAPL"}]
    local_market = [item for item in items if item["requested_ticker"] in {"601600.SS", "002837.SZ", "00700.HK"}]
    us_control_ready_count = sum(1 for item in us_controls if item["memo_status"] == "ready")
    local_market_ready_count = sum(1 for item in local_market if item["memo_status"] == "ready")
    local_market_partial_count = sum(1 for item in local_market if item["memo_status"] == "partial")
    return {
        "total_runs": len(items),
        "ready_runs": sum(1 for item in items if item["memo_status"] == "ready"),
        "partial_runs": sum(1 for item in items if item["memo_status"] == "partial"),
        "skipped_runs": sum(1 for item in items if item["memo_status"] == "skipped"),
        "error_runs": sum(1 for item in items if item["memo_status"] == "error"),
        "us_control_ready_count": us_control_ready_count,
        "local_market_ready_count": local_market_ready_count,
        "local_market_partial_count": local_market_partial_count,
        "provisional_gate_signal": (
            "go_to_analyst_review"
            if us_control_ready_count >= 1 and (local_market_ready_count >= 1 or local_market_partial_count >= 1)
            else "blocked"
        ),
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("summary"))
    lines = [
        "# TradingAgents Pilot Matrix Report",
        "",
        f"- Status: `{clean_text(result.get('status')) or 'unknown'}`",
        f"- Executed at: `{clean_text(result.get('executed_at')) or 'unknown'}`",
        f"- Output directory: `{clean_text(result.get('output_dir')) or 'unknown'}`",
        f"- Total runs: `{summary.get('total_runs', 0)}`",
        f"- Ready runs: `{summary.get('ready_runs', 0)}`",
        f"- Partial runs: `{summary.get('partial_runs', 0)}`",
        f"- Skipped runs: `{summary.get('skipped_runs', 0)}`",
        f"- Error runs: `{summary.get('error_runs', 0)}`",
        f"- U.S. controls ready: `{summary.get('us_control_ready_count', 0)}`",
        f"- Local market ready: `{summary.get('local_market_ready_count', 0)}`",
        f"- Local market partial: `{summary.get('local_market_partial_count', 0)}`",
        f"- Provisional gate signal: `{clean_text(summary.get('provisional_gate_signal')) or 'unknown'}`",
        "",
        "| ID | Ticker | Market | Result | Memo | Action | Conviction | Tokens | Latency ms |",
        "|---|---|---|---|---|---|---|---:|---:|",
    ]
    for item in safe_list(result.get("items")):
        lines.append(
            "| {id} | {ticker} | {market} | {status} | {memo} | {action} | {conviction} | {tokens} | {latency} |".format(
                id=clean_text(item.get("id")) or "unknown",
                ticker=clean_text(item.get("requested_ticker")) or "unknown",
                market=clean_text(item.get("market")) or "unknown",
                status=clean_text(item.get("status")) or "unknown",
                memo=clean_text(item.get("memo_status")) or "unknown",
                action=clean_text(item.get("decision_action")) or "no_opinion",
                conviction=clean_text(item.get("decision_conviction")) or "low",
                tokens=item.get("observed_tokens") if item.get("observed_tokens") is not None else 0,
                latency=item.get("observed_latency_ms") if item.get("observed_latency_ms") is not None else 0,
            )
        )
    if summary.get("provisional_gate_signal") == "go_to_analyst_review":
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                "- The matrix met the automated provisional gate.",
                "- Local-market `partial` rows still require analyst review before Unit 3 is unlocked.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                "- The matrix did not meet the provisional gate yet.",
                "- Keep the bridge in standalone mode until at least one U.S. control and one local-market row are usable.",
            ]
        )
    return "\n".join(lines) + "\n"


def run_tradingagents_pilot_matrix(
    batch_request: dict[str, Any],
    *,
    bridge_runner: BridgeRunner | None = None,
) -> dict[str, Any]:
    requests = safe_list(batch_request.get("requests"))
    output_dir = resolve_path(clean_text(batch_request.get("output_dir") or ".tmp/tradingagents-pilot-matrix"))
    output_dir.mkdir(parents=True, exist_ok=True)
    results_dir = output_dir / "results"
    reports_dir = output_dir / "reports"
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    runner = bridge_runner or run_tradingagents_decision_bridge
    items: list[dict[str, Any]] = []

    for raw_item in requests:
        item = safe_dict(raw_item)
        request_path = resolve_path(clean_text(item.get("path")))
        item_id = clean_text(item.get("id")) or slugify(request_path.stem)
        request_payload = safe_dict(load_json(request_path))
        result = runner(request_payload)

        result_path = results_dir / f"{item_id}.result.json"
        report_path = reports_dir / f"{item_id}.report.md"
        write_json(result_path, result)
        report_path.write_text(str(result.get("report_markdown", "")), encoding="utf-8")

        summary_item = summarize_item(item_id, request_path, result)
        summary_item["result_path"] = str(result_path)
        summary_item["report_path"] = str(report_path)
        items.append(summary_item)

    summary = build_summary(items)
    status = "ok" if summary["provisional_gate_signal"] == "go_to_analyst_review" else "degraded"
    result = {
        "status": status,
        "executed_at": isoformat_z(now_utc()),
        "output_dir": str(output_dir),
        "items": items,
        "summary": summary,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TradingAgents pilot matrix across multiple request files.")
    parser.add_argument("input_json", help="Path to the pilot-matrix request JSON file.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--markdown-output", help="Optional markdown output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = safe_dict(load_json(resolve_path(args.input_json)))
    result = run_tradingagents_pilot_matrix(payload)
    if not args.quiet:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    if args.output:
        write_json(resolve_path(args.output), result)
    if args.markdown_output:
        output_path = resolve_path(args.markdown_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(result.get("report_markdown", "")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
