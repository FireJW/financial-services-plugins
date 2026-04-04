#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
INFO_INDEX_SCRIPT_DIR = (
    DEFAULT_REPO_ROOT
    / "financial-analysis"
    / "skills"
    / "autoresearch-info-index"
    / "scripts"
)
if str(INFO_INDEX_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(INFO_INDEX_SCRIPT_DIR))

from news_index_runtime import (
    build_claim_evidence,
    build_claim_ledger,
    build_markdown_report,
    build_retrieval_quality,
    build_retrieval_run_report,
    build_verdict_output,
    load_json,
    merge_refresh,
    normalize_request,
    promote_observation_channels,
    rerank_observations,
    run_news_index,
    write_json,
)
try:
    from opencli_bridge_runtime import (
        build_markdown_report as build_opencli_bridge_report,
        prepare_opencli_bridge,
        resolve_opencli_payload,
    )
except ModuleNotFoundError:  # OpenCLI bridge is optional for the nightly watchlist path.
    def build_opencli_bridge_report(result: dict[str, Any]) -> str:
        return str(result.get("report_markdown", ""))

    def prepare_opencli_bridge(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ModuleNotFoundError("opencli_bridge_runtime")

    def resolve_opencli_payload(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        raise ModuleNotFoundError("opencli_bridge_runtime")
from fred_macro_chart import generate_gold_pricing_chart


SOURCE_PREFERENCES = [
    "public-first",
    "official-before-derived",
    "claim-traceability-first",
]
DEFAULT_EXECUTION_MODE = "auto"
DEFAULT_OUTPUT_LANGUAGE = "zh-CN"
OUTPUT_LANGUAGE_CHOICES = ("zh-CN", "en")
EXECUTION_MODE_CHOICES = ("auto", "refresh", "full")
BASE_WINDOWS = ["1h", "6h", "24h"]
REFRESH_WINDOWS = ["10m", "1h", "6h", "24h"]
ALIAS_SOURCE_ID = "alias-bundle"
GS_QUANT_PLUGIN_DIR = "partner-built/goldmansachs"
GS_QUANT_BRIDGE_SCRIPT = Path(GS_QUANT_PLUGIN_DIR) / "scripts" / "run-gs-quant-workflow-bridge.mjs"
GS_QUANT_COMMAND_ORDER = (
    "thesis-to-backtest",
    "basket-scenario-check",
    "gs-quant-backtesting",
)
GS_QUANT_DEFAULT_ARTIFACT_STAGE = "full"
GS_QUANT_DEFAULT_BENCHMARK = "000300.SH"
GS_QUANT_DEFAULT_STYLE_HEDGE = "512100.SS"
DRIVER_BASELINE_SOURCE_IDS = {
    "driver-keywords",
    "watch-items",
    "driver-keywords-baseline",
    "watch-items-baseline",
}
REPORT_TITLE_KEYWORDS = (
    "年度报告",
    "年度报告摘要",
    "半年度报告",
    "半年报",
    "一季报",
    "第一季度报告",
    "三季报",
    "第三季度报告",
    "季度报告",
    "业绩预告",
    "业绩快报",
)
CATALYST_TITLE_KEYWORDS = (
    "利润分配",
    "分红",
    "董事会决议",
    "股东会决议",
    "担保",
    "衍生品",
    "套期保值",
    "期货",
    "会计估计变更",
    "资产减值",
    "减值准备",
    "回购",
    "订单",
    "增资",
    "募投",
    "重大合同",
    "关联交易",
    "投资",
)
DRIVER_TITLE_KEYWORDS = (
    "利润分配",
    "担保",
    "衍生品",
    "套期保值",
    "期货",
    "会计估计变更",
    "资产减值",
    "减值准备",
    "年报",
    "季报",
    "股东会决议",
    "董事会决议",
)


@dataclass(frozen=True)
class RequestSpec:
    name: str
    topic_suffix: str
    base_use_case: str
    refresh_use_case: str

    def build_questions(self, stock: dict[str, Any]) -> list[str]:
        name = stock_name(stock)
        ticker = str(stock.get("ticker", "")).strip()
        drivers = ", ".join(unique_strings(stock.get("driver_keywords", []))[:4])
        if self.name == "company_state":
            return [
                f"What is the latest confirmed official filing, earnings update, or major announcement for {name}?",
                f"What changed most recently for {name} that could affect earnings power, valuation, or risk sentiment?",
                f"What is confirmed, not confirmed, or inference only for {name} right now?",
            ]
        if self.name == "earnings_freshness":
            return [
                f"What is the latest annual report, interim report, quarter report, or earnings preview publicly available for {name}?",
                f"What is the exact release date and session timing for the latest report tied to {name} ({ticker})?",
                f"What official materials should be linked for follow-up financial analysis on {name}?",
            ]
        return [
            f"What are the latest commodity, policy, or industry-driver changes that matter for {name}?",
            f"Do the newest {drivers or 'industry and cost'} signals help or hurt {name}?",
            f"Which driver changes are confirmed versus still only a narrative for {name}?",
        ]

    def build_market_relevance(self, stock: dict[str, Any]) -> list[str]:
        name = stock_name(stock)
        sector = str(stock.get("sector", "")).strip()
        if self.name == "company_state":
            return [
                f"{name} latest filing date",
                f"{name} earnings or policy sensitivity",
                f"{name} catalyst and sentiment state",
            ]
        if self.name == "earnings_freshness":
            return [
                f"{name} latest annual or interim report date",
                f"{name} filing freshness",
                f"{name} next reporting catalyst",
            ]
        return [
            f"{name} {sector or 'industry'} driver state",
            f"{name} cost and margin transmission",
            f"{name} policy or macro sensitivity",
        ]

    def build_claims(self, stock: dict[str, Any]) -> list[dict[str, str]]:
        name = stock_name(stock)
        if self.name == "company_state":
            return [
                {
                    "claim_id": "latest-filing-known",
                    "claim_text": f"The latest official filing or major company announcement for {name} is identified with an exact date.",
                },
                {
                    "claim_id": "material-update-exists",
                    "claim_text": f"There is at least one fresh signal that materially updates the current market view on {name}.",
                },
            ]
        if self.name == "earnings_freshness":
            return [
                {
                    "claim_id": "latest-report-identified",
                    "claim_text": f"The latest report for {name} is identified with an exact release date.",
                }
            ]
        return [
            {
                "claim_id": "driver-state-known",
                "claim_text": f"The latest key external drivers for {name} can be described with exact dates and clear pass-through logic.",
            }
        ]


REQUEST_SPECS = (
    RequestSpec(
        name="company_state",
        topic_suffix="latest company-state verification",
        base_use_case="tracked-stock-company-state",
        refresh_use_case="tracked-stock-company-state-refresh",
    ),
    RequestSpec(
        name="earnings_freshness",
        topic_suffix="latest earnings and filing freshness",
        base_use_case="tracked-stock-earnings-freshness",
        refresh_use_case="tracked-stock-earnings-freshness-refresh",
    ),
    RequestSpec(
        name="driver_state",
        topic_suffix="macro and commodity driver state",
        base_use_case="tracked-stock-driver-state",
        refresh_use_case="tracked-stock-driver-state-refresh",
    ),
)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-root", help="Override repo root for workflow files.")
    parser.add_argument("--prepare-only", action="store_true", help="Only write requests and skip index execution.")
    parser.add_argument(
        "--output-language",
        choices=OUTPUT_LANGUAGE_CHOICES,
        help="Report language for markdown outputs. Defaults to zh-CN unless overridden in refresh config.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=EXECUTION_MODE_CHOICES,
        default=DEFAULT_EXECUTION_MODE,
        help="auto uses refresh when an existing case exists, refresh forces merge-refresh, full reruns the full index even when a case already exists.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh tracked A-share watchlist cases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subparsers.add_parser("refresh-watchlist", help="Refresh every tracked stock.")
    add_common_args(refresh_parser)

    run_stock_parser = subparsers.add_parser("run-stock", help="Refresh one tracked stock by slug.")
    run_stock_parser.add_argument("--slug", required=True, help="Stock slug in tracked_stock_library.json.")
    add_common_args(run_stock_parser)
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def stock_name(stock: dict[str, Any]) -> str:
    return str(stock.get("name", "")).strip()


def normalize_output_language(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("en"):
        return "en"
    return DEFAULT_OUTPUT_LANGUAGE


def resolve_output_language(config: dict[str, Any] | None = None, override: Any = None) -> str:
    candidates = [override]
    if isinstance(config, dict):
        candidates.extend([config.get("output_language"), config.get("report_language")])
    for candidate in candidates:
        if str(candidate or "").strip():
            return normalize_output_language(candidate)
    return DEFAULT_OUTPUT_LANGUAGE


def build_translation_map(zh_cn: str, en: str) -> dict[str, str]:
    return {DEFAULT_OUTPUT_LANGUAGE: zh_cn, "en": en}


def pick_translation(translations: dict[str, str] | None, output_language: str) -> str:
    mapping = translations or {}
    language = normalize_output_language(output_language)
    return str(mapping.get(language) or mapping.get("en") or mapping.get(DEFAULT_OUTPUT_LANGUAGE) or "").strip()


def localized_text(output_language: str, *, zh_cn: str, en: str) -> str:
    return en if normalize_output_language(output_language) == "en" else zh_cn


def payload_text(payload: dict[str, Any], key: str, output_language: str | None = None) -> str:
    language = normalize_output_language(output_language or payload.get("output_language"))
    translations = payload.get(f"{key}_translations")
    if isinstance(translations, dict):
        text = pick_translation(translations, language)
        if text:
            return text
    return str(payload.get(key, "")).strip()


def unique_strings(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def ticker_digits(ticker: str) -> str:
    return "".join(ch for ch in str(ticker or "") if ch.isdigit())


def choose_repo_root(args: argparse.Namespace) -> Path:
    if getattr(args, "workspace_root", None):
        return Path(args.workspace_root).resolve()
    return DEFAULT_REPO_ROOT


def workflow_root(repo_root: Path) -> Path:
    return repo_root / ".tmp" / "stock-watch-workflow"


def workflow_paths(repo_root: Path) -> dict[str, Path]:
    root = workflow_root(repo_root)
    return {
        "root": root,
        "library": root / "tracked_stock_library.json",
        "candidate_library": root / "tracked_stock_candidates.json",
        "observations": root / "tracked_stock_observations.jsonl",
        "refresh_request": root / "tracked_stock_refresh_request.json",
        "nightly_summary": root / "nightly_refresh_summary.json",
        "nightly_summary_md": root / "nightly_refresh_summary.md",
        "compare_note": root / "nightly_compare_note.json",
        "compare_note_md": root / "nightly_compare_note.md",
        "gs_quant_root": root / "gs-quant",
        "gs_quant_summary": root / "gs_quant_summary.json",
        "gs_quant_summary_md": root / "gs_quant_summary.md",
    }


def load_refresh_config(paths: dict[str, Path]) -> dict[str, Any]:
    config_path = paths["refresh_request"]
    if config_path.exists():
        return load_json(config_path)
    return {
        "library_path": ".tmp\\stock-watch-workflow\\tracked_stock_library.json",
        "candidate_library_path": ".tmp\\stock-watch-workflow\\tracked_stock_candidates.json",
        "observations_path": ".tmp\\stock-watch-workflow\\tracked_stock_observations.jsonl",
        "refresh_existing_cases": True,
        "discover_new_cases": False,
        "auto_add_new_cases": False,
        "prefer_news_refresh": True,
        "default_execution_mode": DEFAULT_EXECUTION_MODE,
        "generate_nightly_summary": True,
        "ingest_to_backtest": False,
        "generate_gs_quant_workflows": True,
        "use_opencli": False,
        "require_opencli": False,
        "opencli": {},
        "output_language": DEFAULT_OUTPUT_LANGUAGE,
    }


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_opencli_config(config: dict[str, Any]) -> dict[str, Any]:
    for key in ("opencli", "opencli_config"):
        value = config.get(key)
        if isinstance(value, dict):
            return deepcopy(value)
    return {}


def resolve_opencli_enabled(config: dict[str, Any]) -> bool:
    if "use_opencli" in config:
        return bool(config.get("use_opencli"))
    opencli_config = resolve_opencli_config(config)
    if "enabled" in opencli_config:
        return bool(opencli_config.get("enabled"))
    return bool(opencli_config)


def resolve_opencli_required(config: dict[str, Any]) -> bool:
    if "require_opencli" in config:
        return bool(config.get("require_opencli"))
    opencli_config = resolve_opencli_config(config)
    return bool(opencli_config.get("required"))


def load_tracked_stocks(paths: dict[str, Path]) -> list[dict[str, Any]]:
    payload = load_json(paths["library"])
    stocks = payload.get("stocks")
    if not isinstance(stocks, list):
        raise ValueError(f"tracked stock library is malformed: {paths['library']}")
    return [item for item in stocks if isinstance(item, dict)]


def ensure_case_dirs(case_dir: Path) -> None:
    for relative in ("requests", "results", "reports", "history"):
        (case_dir / relative).mkdir(parents=True, exist_ok=True)


def alias_bundle(stock: dict[str, Any]) -> str:
    values = [stock_name(stock), ticker_digits(stock.get("ticker", "")), stock.get("ticker", "")]
    values.extend(stock.get("aliases", []))
    return ", ".join(unique_strings(values))


def parse_notice_timestamp(item: dict[str, Any]) -> str:
    display_time = str(item.get("display_time", "")).strip()
    if display_time:
        match = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", display_time)
        if match:
            return f"{match.group(1)}T{match.group(2)}+08:00"
    notice_date = str(item.get("notice_date", "")).strip()
    if notice_date:
        return f"{notice_date[:10]}T00:00:00+08:00"
    return ""


def parse_notice_cache(repo_root: Path, stock: dict[str, Any]) -> list[dict[str, Any]]:
    digits = ticker_digits(stock.get("ticker", ""))
    if not digits:
        return []
    notice_path = repo_root / ".tmp" / f"eastmoney_{digits}_notices.json"
    if not notice_path.exists():
        return []
    payload = load_json(notice_path)
    raw_items = payload.get("data", {}).get("list", [])
    notices: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("title_ch") or "").strip()
        if not title:
            continue
        notices.append(
            {
                "art_code": str(item.get("art_code", "")).strip(),
                "title": title,
                "notice_date": str(item.get("notice_date", "")).strip()[:10],
                "published_at": parse_notice_timestamp(item),
                "display_time": str(item.get("display_time", "")).strip(),
                "columns": [str(col.get("column_name", "")).strip() for col in item.get("columns", []) if isinstance(col, dict)],
            }
        )
    notices.sort(key=lambda item: (item.get("published_at", ""), item.get("notice_date", ""), item.get("art_code", "")), reverse=True)
    return notices


def notice_candidate(
    notice: dict[str, Any],
    *,
    claim_ids: list[str],
    source_name: str,
) -> dict[str, Any]:
    timestamp = notice.get("published_at") or ""
    date_label = notice.get("notice_date") or "unknown-date"
    title = notice.get("title", "")
    columns = " / ".join(unique_strings(notice.get("columns", [])))
    excerpt = f"{date_label}: {title}"
    if columns:
        excerpt = f"{excerpt} [{columns}]"
    art_code = str(notice.get("art_code", "")).strip().lower() or "notice"
    return {
        "source_id": f"eastmoney-{art_code}",
        "source_name": source_name,
        "source_type": "company_filing",
        "published_at": timestamp or f"{date_label}T00:00:00+08:00",
        "observed_at": timestamp or f"{date_label}T00:00:00+08:00",
        "access_mode": "public",
        "text_excerpt": excerpt,
        "claim_ids": claim_ids,
    }


def is_report_notice(title: str) -> bool:
    return any(keyword in title for keyword in REPORT_TITLE_KEYWORDS)


def is_catalyst_notice(title: str) -> bool:
    return any(keyword in title for keyword in CATALYST_TITLE_KEYWORDS)


def is_driver_notice(title: str) -> bool:
    return any(keyword in title for keyword in DRIVER_TITLE_KEYWORDS)


def build_candidates(spec: RequestSpec, stock: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    notices = parse_notice_cache(repo_root, stock)
    candidates: list[dict[str, Any]] = []
    if spec.name == "company_state":
        candidates.append(
            {
                "source_id": ALIAS_SOURCE_ID,
                "source_name": "Alias bundle",
                "source_type": "symbol_aliases",
                "text_excerpt": alias_bundle(stock),
                "claim_ids": ["latest-filing-known"],
                "raw_metadata": {
                    "baseline_only": True,
                    "baseline_group": "company_profile",
                },
            }
        )
        relevant = [notice for notice in notices if is_report_notice(notice["title"]) or is_catalyst_notice(notice["title"])]
        if not relevant:
            relevant = notices[:4]
        for notice in relevant[:6]:
            claim_ids = ["latest-filing-known"]
            if is_catalyst_notice(notice["title"]):
                claim_ids.append("material-update-exists")
            candidates.append(
                notice_candidate(
                    notice,
                    claim_ids=claim_ids,
                    source_name="Eastmoney local notice cache",
                )
            )
        return candidates

    if spec.name == "earnings_freshness":
        report_notices = [notice for notice in notices if is_report_notice(notice["title"])]
        for notice in report_notices[:4]:
            candidates.append(
                notice_candidate(
                    notice,
                    claim_ids=["latest-report-identified"],
                    source_name="Eastmoney local filing cache",
                )
            )
        return candidates

    candidates.extend(
        [
            {
                "source_id": "driver-keywords-baseline",
                "source_name": "Driver keywords baseline",
                "source_type": "analysis",
                "channel": "background",
                "text_excerpt": ", ".join(unique_strings(stock.get("driver_keywords", []))),
                "claim_ids": [],
                "raw_metadata": {
                    "baseline_only": True,
                    "baseline_group": "driver_profile",
                },
            },
            {
                "source_id": "watch-items-baseline",
                "source_name": "Watch items baseline",
                "source_type": "analysis",
                "channel": "background",
                "text_excerpt": ", ".join(unique_strings(stock.get("watch_items", []))),
                "claim_ids": [],
                "raw_metadata": {
                    "baseline_only": True,
                    "baseline_group": "driver_profile",
                },
            },
        ]
    )
    driver_notices = [notice for notice in notices if is_driver_notice(notice["title"])]
    for notice in driver_notices[:6]:
        candidates.append(
            notice_candidate(
                notice,
                claim_ids=["driver-state-known"],
                source_name="Eastmoney local catalyst cache",
            )
        )
    return candidates


def build_request(
    spec: RequestSpec,
    stock: dict[str, Any],
    *,
    repo_root: Path,
    analysis_time: datetime,
    refresh: bool,
) -> dict[str, Any]:
    name = stock_name(stock)
    ticker = str(stock.get("ticker", "")).strip()
    return {
        "topic": f"{name} ({ticker}) {spec.topic_suffix}",
        "analysis_time": isoformat(analysis_time),
        "questions": spec.build_questions(stock),
        "use_case": spec.refresh_use_case if refresh else spec.base_use_case,
        "source_preferences": SOURCE_PREFERENCES,
        "mode": "generic",
        "windows": REFRESH_WINDOWS if refresh else BASE_WINDOWS,
        "market_relevance": spec.build_market_relevance(stock),
        "claims": spec.build_claims(stock),
        "candidates": build_candidates(spec, stock, repo_root),
        "stock_metadata": {
            key: value
            for key, value in stock.items()
            if key
            in {
                "slug",
                "name",
                "ticker",
                "market",
                "exchange",
                "aliases",
                "peer_keywords",
                "driver_keywords",
                "watch_items",
                "sector",
                "status",
            }
        },
        "max_parallel_candidates": 4,
    }


def build_opencli_bridge_payload(spec: RequestSpec, request_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    opencli_config = resolve_opencli_config(config)
    opencli_config.pop("enabled", None)
    opencli_config.pop("required", None)
    use_case = clean_text(request_payload.get("use_case")) or f"tracked-stock-{spec.name}-opencli"
    if not use_case.endswith("-opencli"):
        use_case = f"{use_case}-opencli"
    return {
        "topic": clean_text(request_payload.get("topic")),
        "analysis_time": clean_text(request_payload.get("analysis_time")),
        "questions": deepcopy(safe_list(request_payload.get("questions"))),
        "use_case": use_case,
        "source_preferences": deepcopy(safe_list(request_payload.get("source_preferences"))),
        "mode": clean_text(request_payload.get("mode")) or "generic",
        "windows": deepcopy(safe_list(request_payload.get("windows"))),
        "claims": deepcopy(safe_list(request_payload.get("claims"))),
        "market_relevance": deepcopy(safe_list(request_payload.get("market_relevance"))),
        "expected_source_families": deepcopy(safe_list(request_payload.get("expected_source_families"))),
        "opencli": opencli_config,
    }


def build_opencli_capture_payload(stock: dict[str, Any], analysis_time: datetime, config: dict[str, Any]) -> dict[str, Any]:
    opencli_config = resolve_opencli_config(config)
    opencli_config.pop("enabled", None)
    opencli_config.pop("required", None)
    return {
        "topic": f"{stock_name(stock)} ({clean_text(stock.get('ticker'))}) stock-watch opencli capture",
        "analysis_time": isoformat(analysis_time),
        "use_case": "tracked-stock-opencli-capture",
        "opencli": opencli_config,
    }


def merge_request_with_opencli_candidates(request_payload: dict[str, Any], bridge_result: dict[str, Any]) -> dict[str, Any]:
    merged_payload = deepcopy(request_payload)
    imported_candidates = [
        deepcopy(item)
        for item in safe_list(safe_dict(bridge_result.get("retrieval_request")).get("candidates"))
        if isinstance(item, dict)
    ]
    existing_candidates = [
        deepcopy(item)
        for item in safe_list(merged_payload.get("candidates") or merged_payload.get("source_candidates"))
        if isinstance(item, dict)
    ]
    merged_payload["candidates"] = existing_candidates + imported_candidates
    return merged_payload


def normalize_projected_claim_state(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"support", "supported", "confirm", "confirmed"}:
        return "support"
    if text in {"contradict", "contradiction", "deny", "denied"}:
        return "contradict"
    if text in {"unclear", "mixed", "unknown"}:
        return "unclear"
    return "support"


def project_opencli_candidates_for_request(candidates: list[dict[str, Any]], request_payload: dict[str, Any]) -> list[dict[str, Any]]:
    request_claim_ids = [clean_text(item.get("claim_id")) for item in safe_list(request_payload.get("claims")) if clean_text(item.get("claim_id"))]
    projected: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        updated = deepcopy(candidate)
        existing_claim_ids = [clean_text(item) for item in safe_list(updated.get("claim_ids")) if clean_text(item)]
        if existing_claim_ids:
            updated["claim_ids"] = existing_claim_ids
            updated["claim_states"] = safe_dict(updated.get("claim_states"))
            projected.append(updated)
            continue
        if len(request_claim_ids) == 1:
            claim_id = request_claim_ids[0]
            raw_source_item = safe_dict(safe_dict(updated.get("raw_metadata")).get("source_item"))
            raw_states = safe_dict(raw_source_item.get("claim_states") or raw_source_item.get("stance_by_claim"))
            updated["claim_ids"] = [claim_id]
            updated["claim_states"] = {
                claim_id: normalize_projected_claim_state(raw_states.get(claim_id) or raw_source_item.get("claim_state") or "support")
            }
        else:
            updated["claim_ids"] = []
            updated["claim_states"] = {}
        projected.append(updated)
    return projected


def build_opencli_bridge_result_for_request(shared_bridge_result: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, Any]:
    shared_request = safe_dict(shared_bridge_result.get("request"))
    shared_retrieval_request = safe_dict(shared_bridge_result.get("retrieval_request"))
    projected_candidates = project_opencli_candidates_for_request(
        safe_list(shared_retrieval_request.get("candidates")),
        request_payload,
    )
    result = {
        "request": {
            "topic": clean_text(request_payload.get("topic")),
            "analysis_time": clean_text(request_payload.get("analysis_time")),
            "generated_at": clean_text(shared_request.get("generated_at")),
            "site_profile": clean_text(shared_request.get("site_profile")),
            "input_mode": clean_text(shared_request.get("input_mode")),
        },
        "notes": deepcopy(safe_list(shared_bridge_result.get("notes"))),
        "runner_summary": deepcopy(safe_dict(shared_bridge_result.get("runner_summary"))),
        "import_summary": deepcopy(safe_dict(shared_bridge_result.get("import_summary"))),
        "retrieval_request": {
            "topic": clean_text(request_payload.get("topic")),
            "analysis_time": clean_text(request_payload.get("analysis_time")),
            "questions": deepcopy(safe_list(request_payload.get("questions"))),
            "use_case": clean_text(request_payload.get("use_case")),
            "source_preferences": deepcopy(safe_list(request_payload.get("source_preferences"))),
            "mode": clean_text(request_payload.get("mode")),
            "windows": deepcopy(safe_list(request_payload.get("windows"))),
            "claims": deepcopy(safe_list(request_payload.get("claims"))),
            "candidates": projected_candidates,
            "market_relevance": deepcopy(safe_list(request_payload.get("market_relevance"))),
            "expected_source_families": deepcopy(safe_list(request_payload.get("expected_source_families"))),
        },
    }
    result["report_markdown"] = build_opencli_bridge_report(result)
    return result


def summarize_opencli_stage(bridge_result: dict[str, Any], *, required: bool, status: str = "ok", error: str = "") -> dict[str, Any]:
    import_summary = safe_dict(bridge_result.get("import_summary"))
    runner_summary = safe_dict(bridge_result.get("runner_summary"))
    return {
        "enabled": True,
        "required": required,
        "status": status,
        "error": clean_text(error),
        "bridge_result": bridge_result,
        "payload_source": clean_text(import_summary.get("payload_source")),
        "imported_candidate_count": int(import_summary.get("imported_candidate_count", 0) or 0),
        "runner_status": clean_text(runner_summary.get("status")),
    }


def observation_list(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    observations = result.get("observations")
    if not isinstance(observations, list):
        return []
    return [item for item in observations if isinstance(item, dict)]


def is_driver_baseline_source(observation: dict[str, Any]) -> bool:
    source_id = str(observation.get("source_id", "")).strip().lower()
    source_name = str(observation.get("source_name", "")).strip().lower()
    raw_metadata = observation.get("raw_metadata", {})
    baseline_group = ""
    if isinstance(raw_metadata, dict):
        baseline_group = str(raw_metadata.get("baseline_group", "")).strip().lower()
    return (
        source_id in DRIVER_BASELINE_SOURCE_IDS
        or source_name in {"driver keywords", "watch items", "driver keywords baseline", "watch items baseline"}
        or baseline_group == "driver_profile"
    )


def is_baseline_source(observation: dict[str, Any]) -> bool:
    source_id = str(observation.get("source_id", "")).strip().lower()
    source_type = str(observation.get("source_type", "")).strip().lower()
    source_name = str(observation.get("source_name", "")).strip().lower()
    raw_metadata = observation.get("raw_metadata", {})
    if isinstance(raw_metadata, dict) and raw_metadata.get("baseline_only"):
        return True
    if source_id == ALIAS_SOURCE_ID or source_type == "symbol_aliases" or source_name == "alias bundle":
        return True
    return is_driver_baseline_source(observation)


def external_source_ids(result: dict[str, Any] | None, *, fresh_only: bool = False) -> set[str]:
    ids: set[str] = set()
    for observation in observation_list(result):
        source_id = str(observation.get("source_id", "")).strip()
        if not source_id or is_baseline_source(observation):
            continue
        if str(observation.get("access_mode", "")).strip().lower() == "blocked":
            continue
        if fresh_only and float(observation.get("age_minutes", 0.0)) > 1440:
            continue
        ids.add(source_id)
    return ids


def baseline_source_ids(result: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    for observation in observation_list(result):
        source_id = str(observation.get("source_id", "")).strip()
        if source_id and is_baseline_source(observation):
            ids.add(source_id)
    return ids


def source_ids(result: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    for observation in observation_list(result):
        source_id = str(observation.get("source_id", "")).strip()
        if source_id:
            ids.add(source_id)
    return ids


def choose_execution_mode(requested_mode: str, config: dict[str, Any], result_path: Path) -> str:
    mode = str(requested_mode or config.get("default_execution_mode", DEFAULT_EXECUTION_MODE)).strip().lower()
    if mode not in EXECUTION_MODE_CHOICES:
        mode = DEFAULT_EXECUTION_MODE
    if mode == "refresh":
        return "news_refresh" if result_path.exists() else "news_index_bootstrap"
    if mode == "full":
        return "news_rebuild" if result_path.exists() else "news_index"
    if config.get("prefer_news_refresh", True) and result_path.exists():
        return "news_refresh"
    return "news_index"


def build_source_delta(previous_result: dict[str, Any] | None, current_result: dict[str, Any] | None) -> dict[str, Any]:
    previous_ids = source_ids(previous_result)
    current_ids = source_ids(current_result)
    previous_baseline_ids = baseline_source_ids(previous_result)
    current_baseline_ids = baseline_source_ids(current_result)
    previous_external_ids = external_source_ids(previous_result)
    current_external_ids = external_source_ids(current_result)
    new_ids = sorted(current_ids - previous_ids)
    new_baseline_ids = sorted(current_baseline_ids - previous_baseline_ids)
    new_nonbaseline_ids = sorted(set(new_ids) - set(new_baseline_ids))
    new_external_ids = sorted(current_external_ids - previous_external_ids)
    dropped_ids = sorted(previous_ids - current_ids)
    return {
        "previous_source_count": len(previous_ids),
        "current_source_count": len(current_ids),
        "previous_baseline_source_count": len(previous_baseline_ids),
        "current_baseline_source_count": len(current_baseline_ids),
        "new_source_count": len(new_ids),
        "new_source_ids": new_ids,
        "new_baseline_source_count": len(new_baseline_ids),
        "new_baseline_source_ids": new_baseline_ids,
        "new_nonbaseline_source_count": len(new_nonbaseline_ids),
        "new_nonbaseline_source_ids": new_nonbaseline_ids,
        "dropped_source_count": len(dropped_ids),
        "dropped_source_ids": dropped_ids,
        "previous_external_source_count": len(previous_external_ids),
        "current_external_source_count": len(current_external_ids),
        "new_external_source_count": len(new_external_ids),
        "new_external_source_ids": new_external_ids,
        "captured_new_sources": bool(new_ids),
        "captured_new_external_sources": bool(new_external_ids),
        "captured_only_baseline_sources": bool(new_ids) and len(new_baseline_ids) == len(new_ids),
    }


def rebuild_result_views(result: dict[str, Any]) -> dict[str, Any]:
    normalized_request = normalize_request(result.get("request", {}))
    observations = deepcopy(observation_list(result))
    evidence_index = build_claim_evidence(observations)
    observations = rerank_observations(observations, evidence_index)
    claim_ledger = build_claim_ledger(normalized_request, observations)
    promote_observation_channels(observations, claim_ledger)
    rebuilt = dict(result)
    rebuilt["request"] = {
        **normalized_request,
        "analysis_time": isoformat(normalized_request["analysis_time"]),
    }
    rebuilt["observations"] = observations
    rebuilt["claim_ledger"] = claim_ledger
    rebuilt["verdict_output"] = build_verdict_output(normalized_request, observations, claim_ledger)
    rebuilt["retrieval_run_report"] = build_retrieval_run_report(normalized_request, observations, claim_ledger)
    rebuilt["retrieval_quality"] = build_retrieval_quality(observations, claim_ledger)
    rebuilt["report_markdown"] = build_markdown_report(rebuilt)
    return rebuilt


def apply_driver_state_guardrails(result: dict[str, Any]) -> dict[str, Any]:
    observations = deepcopy(observation_list(result))
    if not observations:
        return result

    saw_baseline = False
    for observation in observations:
        if not is_driver_baseline_source(observation):
            continue
        saw_baseline = True
        source_name = str(observation.get("source_name", "")).strip()
        if source_name and "baseline" not in source_name.lower():
            observation["source_name"] = f"{source_name} baseline"
        raw_metadata = observation.get("raw_metadata", {})
        baseline_metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        baseline_metadata["baseline_only"] = True
        baseline_metadata["baseline_group"] = "driver_profile"
        observation["raw_metadata"] = baseline_metadata
        observation["claim_ids"] = []
        observation["claim_states"] = {}
        observation["channel"] = "background"

    rebuilt = dict(result)
    rebuilt["observations"] = observations
    rebuilt = rebuild_result_views(rebuilt)

    workflow_context = dict(rebuilt.get("workflow_context", {}))
    fresh_external_ids = sorted(external_source_ids(rebuilt, fresh_only=True))
    workflow_context["driver_external_source_count"] = len(external_source_ids(rebuilt))
    workflow_context["driver_fresh_external_source_count"] = len(fresh_external_ids)
    workflow_context["driver_fresh_external_source_ids"] = fresh_external_ids
    workflow_context["driver_evidence_status"] = "fresh_external_evidence" if fresh_external_ids else "baseline_only" if saw_baseline else "no_external_driver_evidence"
    rebuilt["workflow_context"] = workflow_context

    if not fresh_external_ids:
        verdict = dict(rebuilt.get("verdict_output", {}))
        verdict["core_verdict"] = "Static stock-profile driver inputs define what to watch, but this run did not capture fresh external driver evidence yet."
        next_watch_items = list(verdict.get("next_watch_items", []))
        guidance = "Wait for fresh filings, policy releases, or third-party driver checks before treating driver_state as tradeable evidence."
        if guidance not in next_watch_items:
            next_watch_items.insert(0, guidance)
        verdict["next_watch_items"] = next_watch_items
        rebuilt["verdict_output"] = verdict
        rebuilt["report_markdown"] = build_markdown_report(rebuilt)
    return rebuilt


def apply_result_guardrails(spec: RequestSpec, result: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(result)
    if spec.name == "driver_state":
        guarded = apply_driver_state_guardrails(guarded)
    workflow_context = dict(guarded.get("workflow_context", {}))
    workflow_context["external_source_count"] = len(external_source_ids(guarded))
    workflow_context["fresh_external_source_count"] = len(external_source_ids(guarded, fresh_only=True))
    guarded["workflow_context"] = workflow_context
    return guarded


def build_result_summary(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    verdict = result.get("verdict_output", {})
    confidence_interval = verdict.get("confidence_interval", [0, 0])
    if not isinstance(confidence_interval, list) or len(confidence_interval) != 2:
        confidence_interval = [0, 0]
    freshness_panel = verdict.get("freshness_panel", [])
    latest_window = next(
        (item for item in freshness_panel if isinstance(item, dict) and item.get("window") == "24h"),
        {},
    )
    workflow_context = result.get("workflow_context", {})
    return {
        "core_verdict": str(verdict.get("core_verdict", "")).strip(),
        "confidence_gate": str(verdict.get("confidence_gate", "unknown")).strip() or "unknown",
        "confidence_interval": [int(confidence_interval[0]), int(confidence_interval[1])],
        "confirmed_count": len(verdict.get("confirmed", [])) if isinstance(verdict.get("confirmed"), list) else 0,
        "not_confirmed_count": len(verdict.get("not_confirmed", [])) if isinstance(verdict.get("not_confirmed"), list) else 0,
        "inference_only_count": len(verdict.get("inference_only", [])) if isinstance(verdict.get("inference_only"), list) else 0,
        "fresh_signal_count": int(latest_window.get("count", 0) or 0),
        "fresh_core_signal_count": int(latest_window.get("core_count", 0) or 0),
        "external_source_count": int(workflow_context.get("external_source_count", 0) or 0),
        "fresh_external_source_count": int(workflow_context.get("fresh_external_source_count", 0) or 0),
        "driver_evidence_status": str(workflow_context.get("driver_evidence_status", "")).strip(),
    }


def format_mode_counts(counter_payload: dict[str, int], output_language: str = DEFAULT_OUTPUT_LANGUAGE) -> str:
    parts = [f"{mode} x{count}" for mode, count in sorted(counter_payload.items()) if count]
    return ", ".join(parts) if parts else localized_text(output_language, zh_cn="无", en="none")


def build_stock_workflow_summary(
    run_results: list[dict[str, Any]],
    execution_mode_requested: str,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    mode_counts = Counter(str(item.get("mode", "")).strip() or "unknown" for item in run_results)
    requests_with_new_sources = sum(1 for item in run_results if item.get("captured_new_sources"))
    requests_with_new_external_sources = sum(1 for item in run_results if item.get("captured_new_external_sources"))
    requests_with_only_baseline_source_changes = sum(1 for item in run_results if item.get("captured_only_baseline_sources"))
    total_new_sources = sum(int(item.get("source_delta", {}).get("new_source_count", 0) or 0) for item in run_results)
    total_new_baseline_sources = sum(
        int(item.get("source_delta", {}).get("new_baseline_source_count", 0) or 0) for item in run_results
    )
    total_new_external_sources = sum(int(item.get("source_delta", {}).get("new_external_source_count", 0) or 0) for item in run_results)
    usable_requests = [
        str(item.get("request_name", "")).strip()
        for item in run_results
        if item.get("summary", {}).get("confidence_gate") == "usable"
    ]
    strongest_request = max(
        run_results,
        key=lambda item: (
            int(item.get("summary", {}).get("confidence_interval", [0, 0])[1]),
            int(item.get("summary", {}).get("external_source_count", 0)),
        ),
        default={},
    )
    driver_item = next((item for item in run_results if item.get("request_name") == "driver_state"), {})
    if total_new_external_sources:
        one_line_translations = build_translation_map(
            f"本轮在 {requests_with_new_external_sources} 个请求里新增捕获 {total_new_external_sources} 条外部来源。",
            f"Captured {total_new_external_sources} new external source(s) across {requests_with_new_external_sources} request(s).",
        )
    elif total_new_sources and total_new_baseline_sources == total_new_sources:
        one_line_translations = build_translation_map(
            "本轮只变动了 baseline/profile 输入，没有新增捕获外部来源。",
            "Only baseline/profile inputs changed in this run; no new external source was captured.",
        )
    elif total_new_sources:
        one_line_translations = build_translation_map(
            "本轮更新了缓存上下文，但没有新增捕获外部来源。",
            "The run changed cached context, but it did not capture any new external source.",
        )
    else:
        one_line_translations = build_translation_map(
            "本轮没有新增来源，流程主要是在复核既有缓存上下文。",
            "No new source was captured in this run; the workflow mainly revalidated existing cached context.",
        )
    return {
        "output_language": language,
        "execution_mode_requested": execution_mode_requested,
        "effective_modes": dict(mode_counts),
        "request_count": len(run_results),
        "requests_with_new_sources": requests_with_new_sources,
        "requests_with_new_external_sources": requests_with_new_external_sources,
        "requests_with_only_baseline_source_changes": requests_with_only_baseline_source_changes,
        "total_new_sources": total_new_sources,
        "total_new_baseline_sources": total_new_baseline_sources,
        "total_new_external_sources": total_new_external_sources,
        "usable_requests": usable_requests,
        "strongest_request": str(strongest_request.get("request_name", "")).strip(),
        "driver_evidence_status": str(driver_item.get("summary", {}).get("driver_evidence_status", "")).strip(),
        "one_line_translations": one_line_translations,
        "one_line": pick_translation(one_line_translations, language),
    }


def build_watchlist_workflow_summary(
    updates: list[dict[str, Any]],
    execution_mode_requested: str,
    prepare_only: bool,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    stocks_with_new_external_sources = sum(
        1 for update in updates if int(update.get("workflow_summary", {}).get("total_new_external_sources", 0) or 0) > 0
    )
    stocks_with_only_baseline_source_changes = sum(
        1 for update in updates if int(update.get("workflow_summary", {}).get("total_new_sources", 0) or 0) > 0 and int(update.get("workflow_summary", {}).get("total_new_baseline_sources", 0) or 0) == int(update.get("workflow_summary", {}).get("total_new_sources", 0) or 0)
    )
    total_new_external_sources = sum(
        int(update.get("workflow_summary", {}).get("total_new_external_sources", 0) or 0) for update in updates
    )
    total_new_baseline_sources = sum(
        int(update.get("workflow_summary", {}).get("total_new_baseline_sources", 0) or 0) for update in updates
    )
    total_new_sources = sum(
        int(update.get("workflow_summary", {}).get("total_new_sources", 0) or 0) for update in updates
    )
    if prepare_only:
        one_line_translations = build_translation_map(
            "本轮为 prepare-only，只写入了请求文件，没有执行底层 index。",
            "Prepare-only mode wrote requests without executing the underlying index.",
        )
    elif total_new_external_sources:
        one_line_translations = build_translation_map(
            f"本轮在 {stocks_with_new_external_sources} 个股票案例里新增捕获 {total_new_external_sources} 条外部来源。",
            f"Captured {total_new_external_sources} new external source(s) across {stocks_with_new_external_sources} stock case(s).",
        )
    elif total_new_sources and total_new_baseline_sources == total_new_sources:
        one_line_translations = build_translation_map(
            "本轮股票池只变动了 baseline/profile 输入，没有新增捕获外部来源。",
            "Only baseline/profile inputs changed across the watchlist; this pass did not capture any new external source.",
        )
    elif total_new_sources:
        one_line_translations = build_translation_map(
            "本轮刷新更新了缓存上下文，但没有新增捕获外部来源。",
            "The refresh touched cached context, but it did not capture any new external source.",
        )
    else:
        one_line_translations = build_translation_map(
            "本轮股票池刷新没有新增来源，主要是在复核既有案例。",
            "No new source was captured across the watchlist refresh; this pass mainly revalidated existing cases.",
        )
    return {
        "output_language": language,
        "execution_mode_requested": execution_mode_requested,
        "prepare_only": prepare_only,
        "stock_count": len(updates),
        "stocks_with_new_external_sources": stocks_with_new_external_sources,
        "stocks_with_only_baseline_source_changes": stocks_with_only_baseline_source_changes,
        "total_new_sources": total_new_sources,
        "total_new_baseline_sources": total_new_baseline_sources,
        "total_new_external_sources": total_new_external_sources,
        "one_line_translations": one_line_translations,
        "one_line": pick_translation(one_line_translations, language),
    }


def compare_strength_score(update: dict[str, Any]) -> tuple[int, int, int, int]:
    run_results = update.get("run_results", [])
    total_external_sources = sum(int(item.get("summary", {}).get("external_source_count", 0) or 0) for item in run_results)
    total_fresh_external_sources = sum(int(item.get("summary", {}).get("fresh_external_source_count", 0) or 0) for item in run_results)
    total_confirmed = sum(int(item.get("summary", {}).get("confirmed_count", 0) or 0) for item in run_results)
    best_upper = max((int(item.get("summary", {}).get("confidence_interval", [0, 0])[1]) for item in run_results), default=0)
    return (total_fresh_external_sources, total_external_sources, total_confirmed, best_upper)


def build_compare_note_payload(
    updates: list[dict[str, Any]],
    refreshed_at: str,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    rows = []
    for update in updates:
        run_index = {
            str(item.get("request_name", "")).strip(): item
            for item in update.get("run_results", [])
            if isinstance(item, dict)
        }
        workflow_summary = update.get("workflow_summary", {})
        stock = update.get("stock", {})
        total_external_sources = sum(
            int(item.get("summary", {}).get("external_source_count", 0) or 0) for item in run_index.values()
        )
        total_fresh_external_sources = sum(
            int(item.get("summary", {}).get("fresh_external_source_count", 0) or 0) for item in run_index.values()
        )
        total_confirmed_claims = sum(
            int(item.get("summary", {}).get("confirmed_count", 0) or 0) for item in run_index.values()
        )
        best_confidence_upper = max(
            (int(item.get("summary", {}).get("confidence_interval", [0, 0])[1]) for item in run_index.values()),
            default=0,
        )
        rows.append(
            {
                "slug": str(stock.get("slug", "")).strip(),
                "name": str(stock.get("name", "")).strip(),
                "ticker": str(stock.get("ticker", "")).strip(),
                "company_state": run_index.get("company_state", {}).get("summary", {}),
                "earnings_freshness": run_index.get("earnings_freshness", {}).get("summary", {}),
                "driver_state": run_index.get("driver_state", {}).get("summary", {}),
                "total_new_external_sources": int(workflow_summary.get("total_new_external_sources", 0) or 0),
                "total_new_sources": int(workflow_summary.get("total_new_sources", 0) or 0),
                "total_new_baseline_sources": int(workflow_summary.get("total_new_baseline_sources", 0) or 0),
                "total_external_sources": total_external_sources,
                "total_fresh_external_sources": total_fresh_external_sources,
                "total_confirmed_claims": total_confirmed_claims,
                "best_confidence_upper": best_confidence_upper,
                "driver_evidence_status": str(run_index.get("driver_state", {}).get("summary", {}).get("driver_evidence_status", "")).strip(),
                "strongest_request": str(workflow_summary.get("strongest_request", "")).strip(),
                "strength_score": compare_strength_score(update),
            }
        )
    ranked = sorted(rows, key=lambda item: item["strength_score"], reverse=True)
    leader = ranked[0] if ranked else {}
    laggard = ranked[-1] if len(ranked) > 1 else {}
    comparison_basis_translations = build_translation_map("", "")
    one_line_translations = build_translation_map("", "")
    if leader and laggard and leader.get("slug") != laggard.get("slug"):
        if leader["strength_score"] > laggard["strength_score"]:
            basis_parts_zh: list[str] = []
            basis_parts_en: list[str] = []
            if leader.get("total_external_sources", 0) > laggard.get("total_external_sources", 0):
                basis_parts_zh.append(
                    f"外部来源深度 {leader.get('total_external_sources', 0)} 对 {laggard.get('total_external_sources', 0)}"
                )
                basis_parts_en.append(
                    f"external-source depth {leader.get('total_external_sources', 0)} vs {laggard.get('total_external_sources', 0)}"
                )
            if leader.get("best_confidence_upper", 0) > laggard.get("best_confidence_upper", 0):
                basis_parts_zh.append(
                    f"最高置信上沿 {leader.get('best_confidence_upper', 0)} 对 {laggard.get('best_confidence_upper', 0)}"
                )
                basis_parts_en.append(
                    f"best confidence ceiling {leader.get('best_confidence_upper', 0)} vs {laggard.get('best_confidence_upper', 0)}"
                )
            if leader.get("total_confirmed_claims", 0) > laggard.get("total_confirmed_claims", 0):
                basis_parts_zh.append(
                    f"已确认 claim 数 {leader.get('total_confirmed_claims', 0)} 对 {laggard.get('total_confirmed_claims', 0)}"
                )
                basis_parts_en.append(
                    f"confirmed-claim count {leader.get('total_confirmed_claims', 0)} vs {laggard.get('total_confirmed_claims', 0)}"
                )
            comparison_basis_translations = build_translation_map(
                "、".join(basis_parts_zh) if basis_parts_zh else "领先项的整体证据结构仍然没那么薄。",
                ", ".join(basis_parts_en) if basis_parts_en else "the leader still has a less thin evidence mix overall",
            )
            one_line_translations = build_translation_map(
                f"{leader.get('name', leader.get('slug', '领先项'))}当前的证据底座更厚，{laggard.get('name', laggard.get('slug', '落后项'))}仍然更偏 baseline 驱动。",
                f"{leader.get('name', leader.get('slug', 'Leader'))} currently carries the richer evidence base, while {laggard.get('name', laggard.get('slug', 'the weaker case'))} still looks more baseline-driven.",
            )
        else:
            comparison_basis_translations = build_translation_map(
                "两只标的新鲜外部证据都偏薄。",
                "both names are still thin on fresh external evidence",
            )
            one_line_translations = build_translation_map(
                "两只跟踪标的新鲜外部证据都差不多薄，目前都还没有明显脱离 baseline 观察状态。",
                "The tracked names are still similarly thin on fresh external evidence; neither case has clearly broken away from baseline watchlist status.",
            )
    else:
        comparison_basis_translations = build_translation_map(
            "本轮只有一个标的可用。",
            "only one stock was available for this pass",
        )
        one_line_translations = build_translation_map(
            "本轮只有一个跟踪标的，因此没有生成跨股票对比。",
            "Only one tracked stock was available, so no cross-stock comparison was generated.",
        )
    return {
        "output_language": language,
        "refreshed_at": refreshed_at,
        "one_line_translations": one_line_translations,
        "one_line": pick_translation(one_line_translations, language),
        "leader_slug": str(leader.get("slug", "")).strip(),
        "laggard_slug": str(laggard.get("slug", "")).strip(),
        "comparison_basis_translations": comparison_basis_translations,
        "comparison_basis": pick_translation(comparison_basis_translations, language),
        "stocks": ranked,
    }


def safe_slug_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return token or "item"


def normalize_gs_quant_ticker(ticker: str) -> str:
    normalized = str(ticker or "").strip().upper()
    if normalized.endswith(".SH"):
        return f"{normalized[:-3]}.SS"
    return normalized


def gs_quant_strategy_name(bundle_slug: str, suffix: str) -> str:
    return f"{bundle_slug}_{suffix}".replace("-", "_")


def build_gs_quant_bundle_slug(compare_payload: dict[str, Any]) -> str:
    focus_rows = compare_payload.get("stocks", [])[:2]
    slug_parts = [safe_slug_token(row.get("slug", "")) for row in focus_rows if row.get("slug")]
    return "-".join(slug_parts) if slug_parts else "watchlist-pair"


def render_gs_quant_evidence_table(compare_payload: dict[str, Any]) -> list[str]:
    lines = [
        "| Stock | Ticker | External sources | Fresh external | Best upper | Driver evidence |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in compare_payload.get("stocks", []):
        lines.append(
            f"| {row.get('name', '')} | `{row.get('ticker', '')}` | "
            f"{row.get('total_external_sources', 0)} | {row.get('total_fresh_external_sources', 0)} | "
            f"{row.get('best_confidence_upper', 0)} | {row.get('driver_evidence_status', '') or 'n/a'} |"
        )
    return lines


def render_gs_quant_thesis_workflow(compare_payload: dict[str, Any]) -> str:
    focus_rows = compare_payload.get("stocks", [])[:2]
    leader = focus_rows[0]
    laggard = focus_rows[1]
    leader_ticker = normalize_gs_quant_ticker(str(leader.get("ticker", "")).strip())
    laggard_ticker = normalize_gs_quant_ticker(str(laggard.get("ticker", "")).strip())
    as_of_date = str(compare_payload.get("refreshed_at", ""))[:10]
    bundle_slug = build_gs_quant_bundle_slug(compare_payload)
    compare_one_line = payload_text(compare_payload, "one_line", "en")
    comparison_basis = payload_text(compare_payload, "comparison_basis", "en")
    spec = {
        "mode": "thesis_to_backtest",
        "strategyName": gs_quant_strategy_name(bundle_slug, "watchlist_thesis"),
        "expression": (
            f"Long equal-weight basket of {leader.get('name', '')} and {laggard.get('name', '')} "
            f"with CSI300 benchmark-relative evaluation to test the current watchlist thesis."
        ),
        "instruments": [
            {"id": leader_ticker, "name": leader.get("name", ""), "weight": 0.5, "role": "long"},
            {"id": laggard_ticker, "name": laggard.get("name", ""), "weight": 0.5, "role": "long"},
        ],
        "benchmark": GS_QUANT_DEFAULT_BENCHMARK,
        "hedge": "benchmark_relative",
        "window": {
            "start": "2021-01-01",
            "end": as_of_date,
            "frequency": "daily",
            "rebalance": "weekly",
        },
        "triggers": [
            "Enter when the active watchlist thesis is still supported and both names remain in a weak-to-repair regime chosen by the analyst.",
            "Exit when excess return vs benchmark reaches +12% or holding period reaches 60 trading days.",
        ],
        "scenarioAxes": [
            "RSI threshold grid: 30, 35, 40",
            "Holding horizon sensitivity: 20, 40, 60 trading days",
            "Transaction cost sensitivity: 10, 20, 30 bps",
        ],
        "outputs": [
            "annualized_excess_return",
            "information_ratio",
            "max_drawdown",
            "trade_win_rate",
            "holding_period_return_distribution",
        ],
        "notes": [
            f"Derived automatically from stock_watch_workflow compare note as of {compare_payload.get('refreshed_at', '')}.",
            "This handoff pack uses the stable workflow-file bridge path, not the task-mode worker bridge.",
            "Entry trigger wording is provisional and still needs analyst confirmation against price action.",
        ],
    }
    lines = [
        "# Thesis To Backtest Workflow Pack",
        "",
        "## 1. Watchlist handoff",
        f"- As of: `{compare_payload.get('refreshed_at', '')}`",
        f"- Focus pair: `{leader.get('name', '')}` vs `{laggard.get('name', '')}`",
        f"- Compare note: {compare_one_line}",
        f"- Basis: {comparison_basis}",
        "",
        "## 2. Evidence snapshot",
        "",
        *render_gs_quant_evidence_table(compare_payload),
        "",
        "## 3. Thesis in one line",
        "",
        f"The current watchlist favors a benchmark-relative repair expression centered on `{leader.get('name', '')}` with `{laggard.get('name', '')}` as the secondary leg.",
        "",
        "## 4. Proposed expression",
        "",
        f"- Type: `basket_vs_benchmark`",
        f"- Construction: long `{leader_ticker}` 50% + `{laggard_ticker}` 50%, benchmark `{GS_QUANT_DEFAULT_BENCHMARK}`",
        "- Rationale: preserve the pair idea while stripping out a large part of broad-market beta.",
        "",
        "## 5. Historical test window",
        "",
        f"- Window: `2021-01-01` to `{as_of_date}`",
        "- Frequency: `daily`",
        "- Rebalance: `weekly`",
        "",
        "## 6. Analyst note",
        "",
        "- The watchlist flow confirms evidence freshness and cross-stock strength, but it does not by itself prove a price-based oversold condition.",
        "- Treat the trigger rules below as handoff defaults pending analyst price confirmation.",
        "",
        "## Scaffold Spec",
        "",
        "```json",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_gs_quant_basket_workflow(compare_payload: dict[str, Any]) -> str:
    focus_rows = compare_payload.get("stocks", [])[:2]
    leader = focus_rows[0]
    laggard = focus_rows[1]
    leader_ticker = normalize_gs_quant_ticker(str(leader.get("ticker", "")).strip())
    laggard_ticker = normalize_gs_quant_ticker(str(laggard.get("ticker", "")).strip())
    as_of_date = str(compare_payload.get("refreshed_at", ""))[:10]
    bundle_slug = build_gs_quant_bundle_slug(compare_payload)
    spec = {
        "mode": "basket_scenario",
        "strategyName": gs_quant_strategy_name(bundle_slug, "watchlist_basket_check"),
        "expression": "benchmark_relative",
        "instruments": [
            {"ticker": leader_ticker, "role": "long", "weight": 0.6},
            {"ticker": laggard_ticker, "role": "long", "weight": 0.4},
        ],
        "benchmark": {"ticker": "510300.SS", "hedgeType": "beta_adjusted_short"},
        "hedge": {"ticker": GS_QUANT_DEFAULT_STYLE_HEDGE, "usage": "optional_style_control"},
        "window": {"start": "2024-01-01", "end": as_of_date},
        "triggers": [
            "active_watchlist_theme",
            "market_beta_rebound_needs_control",
        ],
        "scenarioAxes": [
            "first_reaction_T0_T5",
            "follow_through_T6_T20",
            "adverse_unwind_T21_T60",
        ],
        "outputs": [
            "window_return",
            "beta_adjusted_alpha",
            "max_drawdown",
            "hit_rate",
            "turnover_proxy",
        ],
        "notes": [
            f"Derived automatically from stock_watch_workflow compare note as of {compare_payload.get('refreshed_at', '')}.",
            "Preferred expression: benchmark-relative basket.",
            "Fallback expression: pair.",
        ],
    }
    lines = [
        "# GS Quant Basket Scenario Workflow Pack",
        "",
        "## 1. Theme in one line",
        "",
        f"Compare whether `{leader.get('name', '')}` and `{laggard.get('name', '')}` should be expressed as a basket, pair, or benchmark-relative setup.",
        "",
        "## 2. Evidence snapshot",
        "",
        *render_gs_quant_evidence_table(compare_payload),
        "",
        "## 3. Candidate expressions",
        "",
        "| Expression | Construction | Why it exists |",
        "|---|---|---|",
        f"| `E1 basket` | Long `{leader_ticker}` 60% + `{laggard_ticker}` 40% | Directly express the shared watchlist theme. |",
        f"| `E2 pair` | Long `{leader_ticker}` / short `{laggard_ticker}` | Isolate the stronger-vs-weaker leg view. |",
        f"| `E3 benchmark-relative` | Long `E1`, short `510300.SS` by beta-adjusted notional | Remove broad-market beta and keep the theme exposure cleaner. |",
        "",
        "## 4. Recommendation",
        "",
        "- Preferred expression: `E3 benchmark-relative`",
        "- Fallback expression: `E2 pair`",
        f"- Optional style hedge: `{GS_QUANT_DEFAULT_STYLE_HEDGE}`",
        "",
        "## 5. Scenario windows",
        "",
        "- `T+0 to T+5`: first reaction",
        "- `T+6 to T+20`: follow-through",
        "- `T+21 to T+60`: unwind / adverse path",
        "",
        "## Scaffold Spec",
        "",
        "```json",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_gs_quant_backtesting_workflow(compare_payload: dict[str, Any]) -> str:
    focus_rows = compare_payload.get("stocks", [])[:2]
    leader = focus_rows[0]
    laggard = focus_rows[1]
    bundle_slug = build_gs_quant_bundle_slug(compare_payload)
    spec = {
        "mode": "backtesting",
        "strategyName": gs_quant_strategy_name(bundle_slug, "watchlist_pair_backtest"),
        "expression": {
            "type": "pair_with_basket_extension",
            "corePair": [leader.get("name", ""), laggard.get("name", "")],
            "thesis": "trade the stronger-vs-weaker watchlist leg and compare against a benchmark-relative basket extension",
        },
        "instruments": [
            {"symbol": leader.get("name", ""), "role": "pair_leg"},
            {"symbol": laggard.get("name", ""), "role": "pair_leg"},
        ],
        "benchmark": {"name": "CSI300", "role": "optional_basket_neutralization"},
        "hedge": {"type": "dollar_neutral_pair", "targetGross": 1.0},
        "window": {"start": "2020-01-01", "end": str(compare_payload.get("refreshed_at", ""))[:10], "frequency": "daily"},
        "triggers": [
            {
                "name": "entry_oversold_or_relative_weakness",
                "condition": "RSI14<30 for both legs OR spread_zscore<-1.5",
                "action": "open_pair_position",
            },
            {
                "name": "hold_band",
                "condition": "-0.5<=spread_zscore<=0.5 AND holding_days<=20",
                "action": "hold",
            },
            {
                "name": "exit_mean_revert_or_recovery",
                "condition": "spread_zscore>=0 OR weaker_leg_RSI14>45",
                "action": "close_position",
            },
            {
                "name": "stop_loss",
                "condition": "adverse_spread_move>=2.0_std",
                "action": "force_close",
            },
            {
                "name": "rebalance_weekly",
                "condition": "every_5_trading_days",
                "action": "rebalance_to_target_weights",
            },
        ],
        "scenarioAxes": [
            "transaction_cost_bps=[10,30,50,80]",
            "volatility_regime=[high,low]",
            "theme_follow_through=[strong,weak]",
        ],
        "outputs": [
            "performance_summary",
            "cost_sensitivity",
            "rebalance_log",
            "entry_exit_diagnostics",
            "holding_period_distribution",
            "failure_mode_flags",
        ],
        "notes": [
            f"Derived automatically from stock_watch_workflow compare note as of {compare_payload.get('refreshed_at', '')}.",
            "Trigger and cost settings are handoff defaults and should be tuned by the analyst before live backtesting.",
            "Always report gross vs net results by transaction-cost bucket.",
        ],
    }
    lines = [
        "# GS Quant Backtesting Workflow Pack",
        "",
        "## 1. Strategy in one line",
        "",
        f"Long the relatively stronger watchlist leg `{leader.get('name', '')}` and short the relatively weaker leg `{laggard.get('name', '')}`, then compare that pair against a basket extension.",
        "",
        "## 2. Evidence snapshot",
        "",
        *render_gs_quant_evidence_table(compare_payload),
        "",
        "## 3. Rule design",
        "",
        "- Entry: `RSI(14) < 30` for both legs or `spread z-score < -1.5`",
        "- Hold: `-0.5 <= z-score <= 0.5` and `holding_days <= 20`",
        "- Exit: `z-score >= 0` or weaker-leg `RSI(14) > 45`",
        "- Stop: adverse move `>= 2.0 sigma`",
        "- Rebalance: every `5` trading days",
        "- Cost ladder: `10 / 30 / 50 / 80 bps`",
        "",
        "## 4. Diagnostics",
        "",
        "- Gross vs net performance",
        "- Turnover and holding-period distribution",
        "- Entry / exit attribution",
        "- Failure-mode flags",
        "",
        "## Scaffold Spec",
        "",
        "```json",
        json.dumps(spec, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def build_gs_quant_bundle_plans(repo_root: Path, compare_payload: dict[str, Any], paths: dict[str, Path]) -> list[dict[str, Any]]:
    focus_rows = compare_payload.get("stocks", [])[:2]
    if len(focus_rows) < 2:
        return []
    bundle_slug = build_gs_quant_bundle_slug(compare_payload)
    bundle_root = paths["gs_quant_root"] / bundle_slug
    renderers = {
        "thesis-to-backtest": (
            "thesis_to_backtest",
            gs_quant_strategy_name(bundle_slug, "watchlist_thesis"),
            render_gs_quant_thesis_workflow,
        ),
        "basket-scenario-check": (
            "basket_scenario",
            gs_quant_strategy_name(bundle_slug, "watchlist_basket_check"),
            render_gs_quant_basket_workflow,
        ),
        "gs-quant-backtesting": (
            "backtesting",
            gs_quant_strategy_name(bundle_slug, "watchlist_pair_backtest"),
            render_gs_quant_backtesting_workflow,
        ),
    }
    plans: list[dict[str, Any]] = []
    bridge_script_path = repo_root / GS_QUANT_BRIDGE_SCRIPT
    for command_name in GS_QUANT_COMMAND_ORDER:
        mode, strategy_name, renderer = renderers[command_name]
        output_dir = bundle_root / command_name
        workflow_path = output_dir / "workflow.md"
        plans.append(
            {
                "command_name": command_name,
                "mode": mode,
                "strategy_name": strategy_name,
                "bundle_slug": bundle_slug,
                "output_dir": output_dir,
                "workflow_path": workflow_path,
                "manifest_path": output_dir / "bridge-manifest.json",
                "workflow_markdown": renderer(compare_payload),
                "command": [
                    "node",
                    str(bridge_script_path),
                    "--workflow-file",
                    str(workflow_path),
                    "--output-dir",
                    str(output_dir),
                    "--artifact-stage",
                    GS_QUANT_DEFAULT_ARTIFACT_STAGE,
                    "--json",
                ],
            }
        )
    return plans


def render_gs_quant_summary_markdown(summary: dict[str, Any], output_language: str | None = None) -> str:
    language = normalize_output_language(output_language or summary.get("output_language"))
    compare_one_line = payload_text(summary, "compare_one_line", language)
    comparison_basis = payload_text(summary, "comparison_basis", language)
    reason = payload_text(summary, "reason", language)
    lines = [
        localized_text(language, zh_cn="# 股票池 GS Quant 工作流摘要", en="# Watchlist GS Quant Workflow Summary"),
        "",
        f"- {localized_text(language, zh_cn='刷新时间', en='Refreshed at')}: `{summary.get('refreshed_at', '')}`",
        f"- {localized_text(language, zh_cn='状态', en='Status')}: `{summary.get('status', 'unknown')}`",
        f"- {localized_text(language, zh_cn='组合 slug', en='Bundle slug')}: `{summary.get('bundle_slug', '')}`",
        f"- {localized_text(language, zh_cn='关注股票', en='Focus stocks')}: `{', '.join(summary.get('focus_names', []))}`",
        f"- {localized_text(language, zh_cn='对比结论', en='Compare note')}: {compare_one_line}",
        f"- {localized_text(language, zh_cn='判断依据', en='Basis')}: {comparison_basis}",
        "",
        localized_text(language, zh_cn="| Bundle | Mode | Strategy | 状态 | 输出目录 |", en="| Bundle | Mode | Strategy | Status | Output dir |"),
        "|---|---|---|---|---|",
    ]
    for bundle in summary.get("bundles", []):
        lines.append(
            f"| `{bundle.get('command_name', '')}` | `{bundle.get('mode', '')}` | "
            f"`{bundle.get('strategy_name', '')}` | `{bundle.get('status', '')}` | "
            f"`{bundle.get('output_dir', '')}` |"
        )
    if reason:
        lines.extend(["", f"- {localized_text(language, zh_cn='原因', en='Reason')}: {reason}"])
    return "\n".join(lines).strip() + "\n"


def summarize_gs_quant_bridge_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    materialization = payload.get("materialization", {})
    statuses = payload.get("statuses", {})
    return {
        "inputMode": payload.get("inputMode"),
        "artifactStage": payload.get("artifactStage"),
        "mode": materialization.get("mode"),
        "strategyName": materialization.get("strategyName"),
        "statuses": {
            "workflowWritten": bool(statuses.get("workflowWritten")),
            "specWritten": bool(statuses.get("specWritten")),
            "pythonWritten": bool(statuses.get("pythonWritten")),
            "manifestWritten": bool(statuses.get("manifestWritten")),
        },
    }


def enrich_gs_quant_bridge_summary(summary: dict[str, Any], manifest_payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(summary)
    materialization = manifest_payload.get("materialization", {})
    statuses = manifest_payload.get("statuses", {})
    if not enriched.get("inputMode"):
        enriched["inputMode"] = manifest_payload.get("inputMode")
    if not enriched.get("artifactStage"):
        enriched["artifactStage"] = manifest_payload.get("artifactStage")
    if not enriched.get("mode"):
        enriched["mode"] = materialization.get("mode")
    if not enriched.get("strategyName"):
        enriched["strategyName"] = materialization.get("strategyName")
    status_summary = dict(enriched.get("statuses", {}))
    status_summary.setdefault("workflowWritten", bool(statuses.get("workflowWritten")))
    status_summary.setdefault("specWritten", bool(statuses.get("specWritten")))
    status_summary.setdefault("pythonWritten", bool(statuses.get("pythonWritten")))
    status_summary.setdefault("manifestWritten", bool(statuses.get("manifestWritten")))
    enriched["statuses"] = status_summary
    return enriched


def maybe_generate_gs_quant_workflows(
    repo_root: Path,
    paths: dict[str, Path],
    config: dict[str, Any],
    updates: list[dict[str, Any]],
    *,
    prepare_only: bool,
    output_language: str | None = None,
    command_runner: Any = None,
) -> dict[str, Any]:
    language = resolve_output_language(config, output_language)
    if not config.get("generate_gs_quant_workflows", True):
        reason_translations = build_translation_map("refresh 配置里已禁用 GS quant 后处理。", "disabled by refresh config")
        summary = {
            "output_language": language,
            "refreshed_at": isoformat(now_utc()),
            "status": "skipped",
            "reason_translations": reason_translations,
            "reason": pick_translation(reason_translations, language),
            "bundles": [],
        }
        write_json(paths["gs_quant_summary"], summary)
        write_report(paths["gs_quant_summary_md"], render_gs_quant_summary_markdown(summary))
        return summary

    compare_payload = build_compare_note_payload(updates, isoformat(now_utc()), output_language=language)
    focus_rows = compare_payload.get("stocks", [])[:2]
    bridge_script_path = repo_root / GS_QUANT_BRIDGE_SCRIPT
    if prepare_only:
        reason_translations = build_translation_map(
            "prepare-only 模式不会执行 gs-quant workflow 生成。",
            "prepare-only mode does not execute gs-quant workflow generation",
        )
        summary = {
            "output_language": language,
            "refreshed_at": compare_payload.get("refreshed_at", ""),
            "status": "skipped",
            "reason_translations": reason_translations,
            "reason": pick_translation(reason_translations, language),
            "compare_one_line_translations": compare_payload.get("one_line_translations", {}),
            "compare_one_line": payload_text(compare_payload, "one_line", language),
            "comparison_basis_translations": compare_payload.get("comparison_basis_translations", {}),
            "comparison_basis": payload_text(compare_payload, "comparison_basis", language),
            "bundles": [],
        }
        write_json(paths["gs_quant_summary"], summary)
        write_report(paths["gs_quant_summary_md"], render_gs_quant_summary_markdown(summary))
        return summary
    if not bridge_script_path.exists():
        reason_translations = build_translation_map(
            "GS quant 插件桥接脚本缺失，已跳过后处理生成。",
            "gs-quant workflow bridge is unavailable, skipping postprocess generation",
        )
        summary = {
            "output_language": language,
            "refreshed_at": compare_payload.get("refreshed_at", ""),
            "status": "skipped",
            "reason_translations": reason_translations,
            "reason": pick_translation(reason_translations, language),
            "bridge_script_path": str(bridge_script_path),
            "compare_one_line_translations": compare_payload.get("one_line_translations", {}),
            "compare_one_line": payload_text(compare_payload, "one_line", language),
            "comparison_basis_translations": compare_payload.get("comparison_basis_translations", {}),
            "comparison_basis": payload_text(compare_payload, "comparison_basis", language),
            "bundles": [],
        }
        write_json(paths["gs_quant_summary"], summary)
        write_report(paths["gs_quant_summary_md"], render_gs_quant_summary_markdown(summary))
        return summary
    if len(focus_rows) < 2:
        reason_translations = build_translation_map(
            "gs-quant 后处理至少需要两个已跟踪股票。",
            "gs-quant postprocess requires at least two tracked stocks",
        )
        summary = {
            "output_language": language,
            "refreshed_at": compare_payload.get("refreshed_at", ""),
            "status": "skipped",
            "reason_translations": reason_translations,
            "reason": pick_translation(reason_translations, language),
            "compare_one_line_translations": compare_payload.get("one_line_translations", {}),
            "compare_one_line": payload_text(compare_payload, "one_line", language),
            "comparison_basis_translations": compare_payload.get("comparison_basis_translations", {}),
            "comparison_basis": payload_text(compare_payload, "comparison_basis", language),
            "bundles": [],
        }
        write_json(paths["gs_quant_summary"], summary)
        write_report(paths["gs_quant_summary_md"], render_gs_quant_summary_markdown(summary))
        return summary

    plans = build_gs_quant_bundle_plans(repo_root, compare_payload, paths)
    runner = command_runner or subprocess.run
    bundle_results: list[dict[str, Any]] = []
    for plan in plans:
        write_report(plan["workflow_path"], plan["workflow_markdown"])
        try:
            result = runner(
                plan["command"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=repo_root,
            )
            manifest_payload = load_json(plan["manifest_path"]) if plan["manifest_path"].exists() else {}
            bridge_summary = enrich_gs_quant_bridge_summary(
                summarize_gs_quant_bridge_stdout(getattr(result, "stdout", "") or ""),
                manifest_payload,
            )
            ok = int(getattr(result, "returncode", 1)) == 0 and bool(manifest_payload)
            bundle_results.append(
                {
                    "command_name": plan["command_name"],
                    "mode": plan["mode"],
                    "strategy_name": plan["strategy_name"],
                    "status": "ready" if ok else "error",
                    "output_dir": str(plan["output_dir"]),
                    "workflow_path": str(plan["workflow_path"]),
                    "manifest_path": str(plan["manifest_path"]),
                    "bridge_summary": bridge_summary,
                    "stdout_tail": "" if ok else str(getattr(result, "stdout", "") or "")[-2000:],
                    "stderr_tail": str(getattr(result, "stderr", "") or "")[-2000:],
                    "artifacts": manifest_payload.get("artifacts", {}),
                }
            )
        except OSError as exc:
            bundle_results.append(
                {
                    "command_name": plan["command_name"],
                    "mode": plan["mode"],
                    "strategy_name": plan["strategy_name"],
                    "status": "error",
                    "output_dir": str(plan["output_dir"]),
                    "workflow_path": str(plan["workflow_path"]),
                    "manifest_path": str(plan["manifest_path"]),
                    "stdout_tail": "",
                    "stderr_tail": str(exc),
                    "artifacts": {},
                }
            )

    ready_count = sum(1 for bundle in bundle_results if bundle.get("status") == "ready")
    if ready_count == len(bundle_results):
        status = "ready"
    elif ready_count:
        status = "partial"
    else:
        status = "error"
    summary = {
        "output_language": language,
        "refreshed_at": compare_payload.get("refreshed_at", ""),
        "status": status,
        "bundle_slug": build_gs_quant_bundle_slug(compare_payload),
        "focus_slugs": [str(row.get("slug", "")).strip() for row in focus_rows],
        "focus_names": [str(row.get("name", "")).strip() for row in focus_rows],
        "compare_one_line_translations": compare_payload.get("one_line_translations", {}),
        "compare_one_line": payload_text(compare_payload, "one_line", language),
        "comparison_basis_translations": compare_payload.get("comparison_basis_translations", {}),
        "comparison_basis": payload_text(compare_payload, "comparison_basis", language),
        "bundles": bundle_results,
    }
    write_json(paths["gs_quant_summary"], summary)
    write_report(paths["gs_quant_summary_md"], render_gs_quant_summary_markdown(summary))
    return summary


def render_compare_note_markdown(payload: dict[str, Any], output_language: str | None = None) -> str:
    language = normalize_output_language(output_language or payload.get("output_language"))
    leader = next((row for row in payload.get("stocks", []) if row.get("slug") == payload.get("leader_slug")), {})
    laggard = next((row for row in payload.get("stocks", []) if row.get("slug") == payload.get("laggard_slug")), {})
    one_line = payload_text(payload, "one_line", language)
    comparison_basis = payload_text(payload, "comparison_basis", language)
    lines = [
        localized_text(language, zh_cn="# 跟踪股票对比笔记", en="# Tracked Stock Compare Note"),
        "",
        f"- {localized_text(language, zh_cn='刷新时间', en='Refreshed at')}: `{payload.get('refreshed_at', '')}`",
        f"- {localized_text(language, zh_cn='一句话判断', en='One-line judgment')}: {one_line}",
        f"- {localized_text(language, zh_cn='领先项', en='Leader')}: `{leader.get('name', leader.get('slug', 'n/a'))}`",
        f"- {localized_text(language, zh_cn='落后项', en='Laggard')}: `{laggard.get('name', laggard.get('slug', 'n/a'))}`",
        f"- {localized_text(language, zh_cn='判断依据', en='Basis')}: {comparison_basis}",
        "",
        localized_text(
            language,
            zh_cn="| 股票 | 公司状态 | 财报新鲜度 | 驱动状态 | 外部来源 | 新鲜外部来源 | 驱动证据 | 最高上沿 |",
            en="| Stock | Company state | Earnings freshness | Driver state | External sources | Fresh external | Driver evidence | Best upper |",
        ),
        "|---|---|---|---|---:|---:|---|---:|",
    ]
    for row in payload.get("stocks", []):
        company_gate = row.get("company_state", {}).get("confidence_gate", "unknown")
        earnings_gate = row.get("earnings_freshness", {}).get("confidence_gate", "unknown")
        driver_gate = row.get("driver_state", {}).get("confidence_gate", "unknown")
        driver_status = row.get("driver_state", {}).get("driver_evidence_status", "") or "n/a"
        lines.append(
            f"| {row.get('name', '')} (`{row.get('ticker', '')}`) | {company_gate} | {earnings_gate} | {driver_gate} | {row.get('total_external_sources', 0)} | {row.get('total_fresh_external_sources', 0)} | {driver_status} | {row.get('best_confidence_upper', 0)} |"
        )
    lines.extend(["", localized_text(language, zh_cn="## 个股备注", en="## Stock Notes"), ""])
    for row in payload.get("stocks", []):
        lines.extend(
            [
                f"### {row.get('name', '')} (`{row.get('ticker', '')}`)",
                localized_text(
                    language,
                    zh_cn=f"- 证据快照：{row.get('total_external_sources', 0)} 条外部来源，{row.get('total_fresh_external_sources', 0)} 条新鲜外部来源，最高置信上沿 {row.get('best_confidence_upper', 0)}",
                    en=f"- Evidence snapshot: {row.get('total_external_sources', 0)} external source(s), {row.get('total_fresh_external_sources', 0)} fresh external source(s), best upper confidence {row.get('best_confidence_upper', 0)}",
                ),
                f"- {localized_text(language, zh_cn='公司状态', en='Company state')}: {row.get('company_state', {}).get('core_verdict', '')}",
                f"- {localized_text(language, zh_cn='财报新鲜度', en='Earnings freshness')}: {row.get('earnings_freshness', {}).get('core_verdict', '')}",
                f"- {localized_text(language, zh_cn='驱动状态', en='Driver state')}: {row.get('driver_state', {}).get('core_verdict', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_stdout_tail(result: dict[str, Any]) -> str:
    report = str(result.get("report_markdown", "")).strip()
    refresh_summary = result.get("refresh_summary")
    if refresh_summary:
        report = f"{report}\n\n{json.dumps({'refresh_summary': refresh_summary}, ensure_ascii=False, indent=2)}".strip()
    return report[-4000:]


def build_run_result(
    stock: dict[str, Any],
    spec: RequestSpec,
    *,
    execution_mode_requested: str,
    mode: str,
    status: str,
    result_path: Path,
    report_path: Path,
    result: dict[str, Any] | None,
    source_delta: dict[str, Any] | None = None,
    opencli_stage: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    observed_at = ""
    stdout_tail = ""
    summary: dict[str, Any] = {}
    if result:
        observed_at = str(result.get("request", {}).get("analysis_time", "")).strip()
        stdout_tail = render_stdout_tail(result)
        summary = build_result_summary(result)
    source_delta = source_delta or {}
    return {
        "observed_at": observed_at,
        "slug": str(stock.get("slug", "")).strip(),
        "name": stock_name(stock),
        "ticker": str(stock.get("ticker", "")).strip(),
        "request_name": spec.name,
        "execution_mode_requested": execution_mode_requested,
        "mode": mode,
        "status": status,
        "result_path": str(result_path),
        "report_path": str(report_path),
        "source_delta": source_delta,
        "captured_new_sources": bool(source_delta.get("captured_new_sources")),
        "captured_new_external_sources": bool(source_delta.get("captured_new_external_sources")),
        "captured_only_baseline_sources": bool(source_delta.get("captured_only_baseline_sources")),
        "summary": summary,
        "opencli_stage": deepcopy(opencli_stage) if opencli_stage else {},
        "stdout_tail": stdout_tail,
        "stderr_tail": "",
        "error": error,
    }


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_history(case_dir: Path, spec_name: str, analysis_time: datetime, request: dict[str, Any], result: dict[str, Any]) -> None:
    timestamp = analysis_time.strftime("%Y%m%dT%H%M%SZ")
    history_dir = case_dir / "history" / spec_name
    history_dir.mkdir(parents=True, exist_ok=True)
    write_json(history_dir / f"{timestamp}.request.json", request)
    write_json(history_dir / f"{timestamp}.result.json", result)
    write_report(history_dir / f"{timestamp}.report.md", str(result.get("report_markdown", "")))


def write_latest_update(
    case_dir: Path,
    stock: dict[str, Any],
    run_results: list[dict[str, Any]],
    updated_at: str,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    workflow_summary = build_stock_workflow_summary(
        run_results,
        execution_mode_requested=str(run_results[0].get("execution_mode_requested", DEFAULT_EXECUTION_MODE)).strip() if run_results else DEFAULT_EXECUTION_MODE,
        output_language=language,
    )
    payload = {
        "updated_at": updated_at,
        "stock": {
            "slug": str(stock.get("slug", "")).strip(),
            "name": stock_name(stock),
            "ticker": str(stock.get("ticker", "")).strip(),
            "market": str(stock.get("market", "")).strip(),
        },
        "workflow_summary": workflow_summary,
        "run_results": run_results,
    }
    write_json(case_dir / "latest_update.json", payload)
    summary_lines = [
        f"- {localized_text(language, zh_cn='请求执行模式', en='Requested execution mode')}: `{workflow_summary.get('execution_mode_requested', DEFAULT_EXECUTION_MODE)}`",
        f"- {localized_text(language, zh_cn='实际执行模式', en='Effective modes')}: `{format_mode_counts(workflow_summary.get('effective_modes', {}), language)}`",
    ]
    if workflow_summary.get("driver_evidence_status"):
        summary_lines.append(
            f"- {localized_text(language, zh_cn='驱动证据状态', en='Driver evidence status')}: `{workflow_summary.get('driver_evidence_status', '')}`"
        )
    if workflow_summary.get("strongest_request"):
        summary_lines.append(
            f"- {localized_text(language, zh_cn='最强模块', en='Strongest module')}: `{workflow_summary.get('strongest_request', '')}`"
        )
    summary_lines.extend(
        [
            f"- {localized_text(language, zh_cn='本轮是否新增外部来源', en='Captured new external sources this run')}: `{localized_text(language, zh_cn='是', en='yes') if workflow_summary.get('total_new_external_sources', 0) else localized_text(language, zh_cn='否', en='no')}`",
            f"- {localized_text(language, zh_cn='新增来源', en='New sources')}: `{workflow_summary.get('total_new_sources', 0)}` total / `{workflow_summary.get('total_new_baseline_sources', 0)}` baseline / `{workflow_summary.get('total_new_external_sources', 0)}` external",
            f"- {localized_text(language, zh_cn='有新外部来源的请求', en='Requests with new external sources')}: `{workflow_summary.get('requests_with_new_external_sources', 0)}/{workflow_summary.get('request_count', 0)}`",
            f"- {localized_text(language, zh_cn='仅 baseline 变动的请求', en='Requests with baseline-only changes')}: `{workflow_summary.get('requests_with_only_baseline_source_changes', 0)}/{workflow_summary.get('request_count', 0)}`",
            f"- {localized_text(language, zh_cn='一句话摘要', en='One-line summary')}: {workflow_summary.get('one_line', '')}",
        ]
    )
    lines = [
        localized_text(language, zh_cn=f"# {stock_name(stock)} 最新更新", en=f"# {stock_name(stock)} Latest Update"),
        "",
        f"- Ticker: `{stock.get('ticker', '')}`",
        f"- Market: `{stock.get('market', '')}`",
        f"- {localized_text(language, zh_cn='更新时间', en='Updated at')}: `{updated_at}`",
        "",
        localized_text(language, zh_cn="## 流程摘要", en="## Workflow Summary"),
        "",
    ]
    lines.extend(summary_lines)
    lines.extend(["", localized_text(language, zh_cn="## 运行结果", en="## Run Results"), ""])
    for item in run_results:
        opencli_stage = safe_dict(item.get("opencli_stage"))
        lines.extend(
            [
                f"- `{item['request_name']}`: `{item['status']}` {localized_text(language, zh_cn='通过', en='via')} `{item['mode']}`",
                f"  - {localized_text(language, zh_cn='gate', en='gate')}: `{item.get('summary', {}).get('confidence_gate', 'unknown')}` / {localized_text(language, zh_cn='置信区间', en='confidence')} `{item.get('summary', {}).get('confidence_interval', [0, 0])[0]}-{item.get('summary', {}).get('confidence_interval', [0, 0])[1]}`",
                f"  - {localized_text(language, zh_cn='新增来源', en='new sources')}: `{item.get('source_delta', {}).get('new_source_count', 0)}` total / `{item.get('source_delta', {}).get('new_baseline_source_count', 0)}` baseline / `{item.get('source_delta', {}).get('new_external_source_count', 0)}` external",
                f"  - {localized_text(language, zh_cn='结果文件', en='result')}: `{item['result_path']}`",
                f"  - {localized_text(language, zh_cn='报告文件', en='report')}: `{item['report_path']}`",
            ]
        )
        if opencli_stage:
            lines.append(
                f"  - OpenCLI: `{opencli_stage.get('status', 'unknown')}` / imported `{opencli_stage.get('imported_candidate_count', 0)}` / runner `{opencli_stage.get('runner_status', '') or 'not-run'}`"
            )
            if opencli_stage.get("result_path"):
                lines.append(f"  - OpenCLI bridge result: `{opencli_stage['result_path']}`")
            if opencli_stage.get("report_path"):
                lines.append(f"  - OpenCLI bridge report: `{opencli_stage['report_path']}`")
        if item.get("error"):
            lines.append(f"  - {localized_text(language, zh_cn='错误', en='error')}: `{item['error']}`")
    write_report(case_dir / "latest_update.md", "\n".join(lines) + "\n")
    return payload


def refresh_single_stock(
    repo_root: Path,
    stock: dict[str, Any],
    *,
    paths: dict[str, Path],
    config: dict[str, Any],
    execution_mode_requested: str,
    prepare_only: bool,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any]:
    analysis_time = now_utc()
    case_dir = workflow_root(repo_root) / "cases" / str(stock.get("slug", "")).strip()
    ensure_case_dirs(case_dir)

    profile = dict(stock)
    profile["case_dir"] = str(case_dir.relative_to(repo_root))
    profile["updated_at"] = isoformat(analysis_time)
    write_json(case_dir / "profile.json", profile)

    run_results: list[dict[str, Any]] = []
    opencli_enabled = resolve_opencli_enabled(config)
    opencli_required = resolve_opencli_required(config)
    opencli_capture: dict[str, Any] = {}
    opencli_capture_error = ""
    shared_opencli_bridge_result: dict[str, Any] = {}
    if opencli_enabled:
        try:
            opencli_payload, payload_source, resolved_result_path, runner_summary = resolve_opencli_payload(
                build_opencli_capture_payload(stock, analysis_time, config)
            )
            opencli_capture = {
                "payload": deepcopy(opencli_payload),
                "payload_source": payload_source,
                "result_path": resolved_result_path,
                "runner_summary": deepcopy(safe_dict(runner_summary)),
            }
            shared_opencli_bridge_result = prepare_opencli_bridge(
                build_opencli_capture_payload(stock, analysis_time, config),
                preloaded_payload=opencli_capture.get("payload"),
                payload_source_override=clean_text(opencli_capture.get("payload_source")),
                result_path_override=clean_text(opencli_capture.get("result_path")),
                runner_summary_override=safe_dict(opencli_capture.get("runner_summary")),
            )
        except Exception as exc:
            opencli_capture_error = str(exc)
    for spec in REQUEST_SPECS:
        base_request = build_request(spec, stock, repo_root=repo_root, analysis_time=analysis_time, refresh=False)
        refresh_request = build_request(spec, stock, repo_root=repo_root, analysis_time=analysis_time, refresh=True)

        request_path = case_dir / "requests" / f"{spec.name}.request.json"
        refresh_request_path = case_dir / "requests" / f"{spec.name}.refresh.request.json"
        result_path = case_dir / "results" / f"{spec.name}.result.json"
        report_path = case_dir / "reports" / f"{spec.name}.report.md"
        opencli_result_path = case_dir / "results" / f"{spec.name}.opencli-bridge.result.json"
        opencli_report_path = case_dir / "reports" / f"{spec.name}.opencli-bridge.report.md"

        write_json(request_path, base_request)
        write_json(refresh_request_path, refresh_request)
        previous_result = load_json(result_path) if result_path.exists() else None
        effective_mode = choose_execution_mode(execution_mode_requested, config, result_path)
        opencli_stage: dict[str, Any] = {}

        if prepare_only:
            item = build_run_result(
                stock,
                spec,
                execution_mode_requested=execution_mode_requested,
                mode="prepare_only",
                status="prepared",
                result_path=result_path,
                report_path=report_path,
                result=None,
                opencli_stage=opencli_stage,
            )
            run_results.append(item)
            append_jsonl(paths["observations"], item)
            continue

        try:
            executed_request = refresh_request if effective_mode == "news_refresh" else base_request
            if opencli_enabled:
                if opencli_capture_error:
                    opencli_stage = summarize_opencli_stage({}, required=opencli_required, status="error", error=opencli_capture_error)
                    if opencli_required:
                        raise ValueError(opencli_capture_error)
                else:
                    try:
                        bridge_result = build_opencli_bridge_result_for_request(
                            shared_opencli_bridge_result,
                            build_opencli_bridge_payload(spec, executed_request, config),
                        )
                        opencli_stage = summarize_opencli_stage(bridge_result, required=opencli_required)
                        write_json(opencli_result_path, bridge_result)
                        write_report(opencli_report_path, str(bridge_result.get("report_markdown", "")))
                        opencli_stage["result_path"] = str(opencli_result_path)
                        opencli_stage["report_path"] = str(opencli_report_path)
                        executed_request = merge_request_with_opencli_candidates(executed_request, bridge_result)
                        if effective_mode == "news_refresh":
                            refresh_request = executed_request
                            write_json(refresh_request_path, refresh_request)
                        else:
                            base_request = executed_request
                            write_json(request_path, base_request)
                    except Exception as exc:
                        opencli_stage = summarize_opencli_stage({}, required=opencli_required, status="error", error=str(exc))
                        if opencli_required:
                            raise
            if effective_mode == "news_refresh":
                if previous_result is None:
                    raise ValueError(f"Cannot refresh without an existing result: {result_path}")
                result = merge_refresh(previous_result, refresh_request)
                mode = effective_mode
            else:
                result = run_news_index(base_request)
                mode = effective_mode

            result = apply_result_guardrails(spec, result)
            source_delta = build_source_delta(previous_result, result)
            workflow_context = dict(result.get("workflow_context", {}))
            workflow_context["execution_mode_requested"] = execution_mode_requested
            workflow_context["execution_mode_effective"] = mode
            workflow_context["source_delta"] = source_delta
            result["workflow_context"] = workflow_context
            write_json(result_path, result)
            write_report(report_path, str(result.get("report_markdown", "")))
            save_history(case_dir, spec.name, analysis_time, refresh_request if mode == "news_refresh" else base_request, result)

            item = build_run_result(
                stock,
                spec,
                execution_mode_requested=execution_mode_requested,
                mode=mode,
                status="ok",
                result_path=result_path,
                report_path=report_path,
                result=result,
                source_delta=source_delta,
                opencli_stage=opencli_stage,
            )
        except Exception as exc:
            item = build_run_result(
                stock,
                spec,
                execution_mode_requested=execution_mode_requested,
                mode=effective_mode,
                status="error",
                result_path=result_path,
                report_path=report_path,
                result=None,
                opencli_stage=opencli_stage,
                error=str(exc),
            )
        run_results.append(item)
        append_jsonl(paths["observations"], item)

    latest_update = write_latest_update(case_dir, stock, run_results, isoformat(now_utc()), output_language=output_language)
    maybe_ingest_observations(repo_root, config, paths["observations"])
    return latest_update


def maybe_ingest_observations(repo_root: Path, config: dict[str, Any], observations_path: Path) -> None:
    if not config.get("ingest_to_backtest"):
        return
    loader = repo_root / ".tmp" / "oliver-kell-backtest" / "scripts" / "local_index_loader.py"
    if not loader.exists():
        return
    python_bin = sys.executable or "python"
    try:
        subprocess.run(
            [python_bin, str(loader), str(observations_path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


def render_nightly_summary_markdown(payload: dict[str, Any], output_language: str | None = None) -> str:
    language = normalize_output_language(output_language or payload.get("output_language"))
    workflow_summary = payload.get("workflow_summary", {})
    gs_quant_summary = payload.get("gs_quant_postprocess", {})
    macro_chart = payload.get("macro_chart", {})
    lines = [
        localized_text(language, zh_cn="# 跟踪股票夜间摘要", en="# Tracked Stock Nightly Summary"),
        "",
        f"- {localized_text(language, zh_cn='刷新时间', en='Refreshed at')}: `{payload.get('refreshed_at', '')}`",
        f"- {localized_text(language, zh_cn='股票数量', en='Stock count')}: `{payload.get('stock_count', 0)}`",
        f"- {localized_text(language, zh_cn='请求执行模式', en='Requested execution mode')}: `{workflow_summary.get('execution_mode_requested', DEFAULT_EXECUTION_MODE)}`",
        f"- {localized_text(language, zh_cn='本轮是否新增外部来源', en='Captured new external sources in this pass')}: `{localized_text(language, zh_cn='是', en='yes') if workflow_summary.get('total_new_external_sources', 0) else localized_text(language, zh_cn='否', en='no')}`",
        f"- {localized_text(language, zh_cn='新增来源', en='New sources')}: `{workflow_summary.get('total_new_sources', 0)}` total / `{workflow_summary.get('total_new_baseline_sources', 0)}` baseline / `{workflow_summary.get('total_new_external_sources', 0)}` external",
        f"- {localized_text(language, zh_cn='一句话摘要', en='One-line summary')}: {workflow_summary.get('one_line', '')}",
        f"- {localized_text(language, zh_cn='GS quant 后处理', en='GS quant postprocess')}: `{gs_quant_summary.get('status', 'not-run')}`",
        f"- {localized_text(language, zh_cn='FRED 宏观图表', en='FRED macro chart')}: `{macro_chart.get('status', 'not-run')}`",
        "",
        localized_text(language, zh_cn="## 股票列表", en="## Stocks"),
        "",
    ]
    for update in payload.get("stocks", []):
        stock = update.get("stock", {})
        summary = update.get("workflow_summary", {})
        lines.extend(
            [
                f"- {stock.get('name', '')} (`{stock.get('ticker', '')}`): {summary.get('one_line', '')}",
                f"  - {localized_text(language, zh_cn='新增来源', en='new sources')}: `{summary.get('total_new_sources', 0)}` total / `{summary.get('total_new_baseline_sources', 0)}` baseline / `{summary.get('total_new_external_sources', 0)}` external",
            ]
        )
    compare_note_path = payload.get("compare_note_path", "")
    if compare_note_path:
        lines.extend(["", f"- {localized_text(language, zh_cn='对比笔记', en='Compare note')}: `{compare_note_path}`"])
    gs_quant_summary_path = payload.get("gs_quant_summary_path", "")
    if gs_quant_summary_path:
        lines.append(f"- {localized_text(language, zh_cn='GS quant 摘要', en='GS quant summary')}: `{gs_quant_summary_path}`")
    if macro_chart:
        lines.extend(["", localized_text(language, zh_cn="## 宏观图表", en="## Macro Chart"), ""])
        lines.append(f"- {localized_text(language, zh_cn='状态', en='Status')}: `{macro_chart.get('status', 'unknown')}`")
        if macro_chart.get("chart_path"):
            lines.append(f"- {localized_text(language, zh_cn='图表', en='Chart')}: `{macro_chart.get('chart_path', '')}`")
        if macro_chart.get("summary_path"):
            lines.append(f"- {localized_text(language, zh_cn='摘要文件', en='Summary')}: `{macro_chart.get('summary_path', '')}`")
        if macro_chart.get("actual_start_date") and macro_chart.get("actual_end_date"):
            lines.append(
                f"- {localized_text(language, zh_cn='实际日期范围', en='Actual date range')}: `{macro_chart.get('actual_start_date', '')}` to `{macro_chart.get('actual_end_date', '')}`"
            )
        if macro_chart.get("one_line"):
            lines.append(f"- {localized_text(language, zh_cn='快照', en='Snapshot')}: {macro_chart.get('one_line', '')}")
        if macro_chart.get("reason"):
            lines.append(f"- {localized_text(language, zh_cn='原因', en='Reason')}: {macro_chart.get('reason', '')}")
        if macro_chart.get("error"):
            lines.append(f"- {localized_text(language, zh_cn='错误', en='Error')}: {macro_chart.get('error', '')}")
    return "\n".join(lines).strip() + "\n"


def write_compare_note(
    paths: dict[str, Path],
    updates: list[dict[str, Any]],
    refreshed_at: str,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> dict[str, Any] | None:
    if len(updates) < 2:
        return None
    payload = build_compare_note_payload(updates, refreshed_at, output_language=output_language)
    write_json(paths["compare_note"], payload)
    write_report(paths["compare_note_md"], render_compare_note_markdown(payload))
    return payload


def write_nightly_summary(
    paths: dict[str, Path],
    updates: list[dict[str, Any]],
    prepare_only: bool,
    execution_mode_requested: str,
    gs_quant_summary: dict[str, Any] | None = None,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
) -> None:
    language = normalize_output_language(output_language)
    refreshed_at = isoformat(now_utc())
    compare_note = write_compare_note(paths, updates, refreshed_at, output_language=language)
    macro_chart_summary = (
        {
            "status": "skipped",
            "reason": "Prepare-only mode skipped FRED macro chart generation.",
            "one_line": "Prepare-only mode skipped FRED macro chart generation.",
        }
        if prepare_only
        else generate_gold_pricing_chart(paths["root"])
    )
    payload = {
        "output_language": language,
        "refreshed_at": refreshed_at,
        "stock_count": len(updates),
        "prepare_only": prepare_only,
        "workflow_summary": build_watchlist_workflow_summary(updates, execution_mode_requested, prepare_only, output_language=language),
        "compare_note_path": str(paths["compare_note_md"]) if compare_note else "",
        "gs_quant_summary_path": str(paths["gs_quant_summary_md"]) if gs_quant_summary else "",
        "gs_quant_postprocess": gs_quant_summary or {},
        "macro_chart": macro_chart_summary,
        "stocks": updates,
    }
    write_json(paths["nightly_summary"], payload)
    write_report(paths["nightly_summary_md"], render_nightly_summary_markdown(payload))


def main() -> None:
    args = parse_args()
    repo_root = choose_repo_root(args)
    paths = workflow_paths(repo_root)
    config = load_refresh_config(paths)
    output_language = resolve_output_language(config, getattr(args, "output_language", None))
    stocks = load_tracked_stocks(paths)

    if args.command == "run-stock":
        target_slug = str(args.slug).strip()
        selected = [stock for stock in stocks if str(stock.get("slug", "")).strip() == target_slug]
        if not selected:
            raise SystemExit(f"Unknown stock slug: {target_slug}")
    else:
        selected = stocks

    updates = [
        refresh_single_stock(
            repo_root,
            stock,
            paths=paths,
            config=config,
            execution_mode_requested=str(getattr(args, "execution_mode", DEFAULT_EXECUTION_MODE)).strip(),
            prepare_only=bool(getattr(args, "prepare_only", False)),
            output_language=output_language,
        )
        for stock in selected
    ]

    gs_quant_summary = maybe_generate_gs_quant_workflows(
        repo_root,
        paths,
        config,
        updates,
        prepare_only=bool(getattr(args, "prepare_only", False)),
        output_language=output_language,
    )

    if args.command == "refresh-watchlist" and config.get("generate_nightly_summary", True):
        write_nightly_summary(
            paths,
            updates,
            bool(getattr(args, "prepare_only", False)),
            str(getattr(args, "execution_mode", DEFAULT_EXECUTION_MODE)).strip(),
            gs_quant_summary,
            output_language=output_language,
        )

    print(json.dumps({"status": "ok", "stock_count": len(updates), "stocks": [item["stock"]["slug"] for item in updates]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
