#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import sys
from copy import deepcopy
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import import_module, util
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, perf_counter, sleep
from typing import Any, Callable, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
for raw_path in reversed((os.environ.get("TRADINGAGENTS_PYTHONPATH") or "").split(os.pathsep)):
    candidate = raw_path.strip()
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from tradingagents_decision_contract import (
    ACTION_VALUES,
    CONFIDENCE_VALUES,
    SOURCE_VALUE,
    STATUS_VALUES,
    contract_errors,
    validate_decision_memo,
)
from tradingagents_eastmoney_market import (
    fetch_daily_bars as fetch_eastmoney_daily_bars,
    fetch_hk_quote_snapshot,
    get_indicator as get_eastmoney_indicator,
    get_stock_data as get_eastmoney_stock_data,
)
from tradingagents_longbridge_market import (
    fetch_daily_bars as fetch_longbridge_daily_bars,
    get_indicator as get_longbridge_indicator,
    get_stock_data as get_longbridge_stock_data,
    longbridge_available,
)
from tradingagents_package_support import resolve_package_version
from tradingagents_provider_config import resolve_provider_runtime, temporary_environment_overrides
from tradingagents_sec_fundamentals import (
    get_balance_sheet as get_sec_balance_sheet,
    get_cashflow as get_sec_cashflow,
    get_fundamentals as get_sec_fundamentals,
    get_income_statement as get_sec_income_statement,
)
from tradingagents_tushare_market import (
    fetch_daily_bars as fetch_tushare_daily_bars,
    get_indicator as get_tushare_indicator,
    get_stock_data as get_tushare_stock_data,
    indicator_series as market_indicator_series,
)
from tradingagents_ticker_normalization import detect_market, normalize_ticker, ticker_to_tradingagents_format


REPO_ROOT = SCRIPT_DIR.parents[3]
BRIDGE_VERSION = "0.1.0"
DEFAULT_MODE = "optional"
DEFAULT_COST_BUDGET_TOKENS = 50000
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_VERSION_GUARD = "0.2."
DEFAULT_SELECTED_ANALYSTS = ("market", "social", "news", "fundamentals")
DEFAULT_ALPHA_VANTAGE_MIN_INTERVAL_SECONDS = 0.0
SUPPORTED_ANALYSTS = {"market", "social", "news", "fundamentals"}
ANALYSIS_PROFILE_PRESETS = {
    "full": {},
    "smart_free": {},
    "free_alpha_vantage_fundamentals": {
        "selected_analysts": ["fundamentals"],
        "deep_think_llm": "gpt-5.4-mini",
        "data_vendors": {
            "fundamental_data": "alpha_vantage",
        },
        "tool_vendors": {
            "get_fundamentals": "alpha_vantage",
            "get_balance_sheet": "alpha_vantage",
            "get_cashflow": "alpha_vantage",
            "get_income_statement": "alpha_vantage",
        },
        "max_debate_rounds": 0,
        "max_risk_discuss_rounds": 0,
        "alpha_vantage_min_interval_seconds": 1.25,
    },
    "free_sec_fundamentals": {
        "selected_analysts": ["fundamentals"],
        "deep_think_llm": "gpt-5.4-mini",
        "data_vendors": {
            "fundamental_data": "sec_companyfacts",
        },
        "tool_vendors": {
            "get_fundamentals": "sec_companyfacts",
            "get_balance_sheet": "sec_companyfacts",
            "get_cashflow": "sec_companyfacts",
            "get_income_statement": "sec_companyfacts",
        },
        "max_debate_rounds": 0,
        "max_risk_discuss_rounds": 0,
        "alpha_vantage_min_interval_seconds": 0,
    },
    "free_tushare_market": {
        "selected_analysts": ["market"],
        "deep_think_llm": "gpt-5.4-mini",
        "data_vendors": {
            "core_stock_apis": "tushare_market",
            "technical_indicators": "tushare_market",
        },
        "tool_vendors": {
            "get_stock_data": "tushare_market",
            "get_indicators": "tushare_market",
        },
        "max_debate_rounds": 0,
        "max_risk_discuss_rounds": 0,
        "alpha_vantage_min_interval_seconds": 0,
    },
    "free_eastmoney_market": {
        "selected_analysts": ["market"],
        "deep_think_llm": "gpt-5.4-mini",
        "data_vendors": {
            "core_stock_apis": "eastmoney_market",
            "technical_indicators": "eastmoney_market",
        },
        "tool_vendors": {
            "get_stock_data": "eastmoney_market",
            "get_indicators": "eastmoney_market",
        },
        "max_debate_rounds": 0,
        "max_risk_discuss_rounds": 0,
        "alpha_vantage_min_interval_seconds": 0,
    },
    "longbridge_market": {
        "selected_analysts": ["market"],
        "deep_think_llm": "gpt-5.4-mini",
        "data_vendors": {
            "core_stock_apis": "longbridge_market",
            "technical_indicators": "longbridge_market",
        },
        "tool_vendors": {
            "get_stock_data": "longbridge_market",
            "get_indicators": "longbridge_market",
        },
        "max_debate_rounds": 0,
        "max_risk_discuss_rounds": 0,
        "alpha_vantage_min_interval_seconds": 0,
    },
}
MANDATORY_WARNINGS = (
    "This is advisory output from TradingAgents (research purposes only).",
    "Do not treat this output as factual evidence or investment advice.",
)

PackageProbe = Callable[[], tuple[bool, str]]
UpstreamRunner = Callable[[dict[str, Any]], Any]


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_path(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def normalize_mode(value: Any) -> str:
    return "required" if clean_text(value).lower() == "required" else DEFAULT_MODE


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def to_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = clean_text(value)
        return [text] if text else []
    normalized: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def normalize_string_mapping(value: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, raw_value in safe_dict(value).items():
        key_text = clean_text(key)
        value_text = clean_text(raw_value)
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized


def normalize_selected_analysts(value: Any) -> list[str]:
    selected: list[str] = []
    candidates = []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    else:
        candidates = safe_list(value)
    for item in candidates:
        analyst = clean_text(item).lower()
        if analyst in SUPPORTED_ANALYSTS and analyst not in selected:
            selected.append(analyst)
    return selected


def normalize_confidence(value: Any, default: str = "low") -> str:
    text = clean_text(value).lower()
    return text if text in CONFIDENCE_VALUES else default


def normalize_action(value: Any, default: str = "no_opinion") -> str:
    text = clean_text(value).lower()
    return text if text in ACTION_VALUES else default


def dedupe_warnings(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        text = clean_text(item)
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def format_exception_message(exc: BaseException) -> str:
    messages: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen and len(messages) < 4:
        seen.add(id(current))
        text = clean_text(str(current))
        class_name = current.__class__.__name__
        if text:
            messages.append(f"{class_name}: {text}")
        else:
            messages.append(class_name)
        next_exc = current.__cause__ if current.__cause__ is not None else current.__context__
        current = next_exc if isinstance(next_exc, BaseException) else None
    if not messages:
        return "Unexpected bridge error."
    rendered = " <- ".join(messages)
    if len(rendered) > 600:
        return f"{rendered[:597]}..."
    return rendered


def normalize_analysis_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return isoformat_z(now_utc())
    if len(text) == 10:
        return f"{text}T00:00:00Z"
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return isoformat_z(parsed)


def pick_value(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def resolve_analysis_profile_name(raw_request: dict[str, Any], config: dict[str, Any]) -> str:
    profile = clean_text(pick_value(raw_request.get("analysis_profile"), config.get("analysis_profile"))).lower()
    return profile or "full"


def resolve_request_config(raw_request: dict[str, Any]) -> dict[str, Any]:
    config = safe_dict(raw_request.get("config"))
    online_tools = raw_request.get("online_tools") if "online_tools" in raw_request else config.get("online_tools")
    online_tools_dict = safe_dict(online_tools)
    analysis_profile = resolve_analysis_profile_name(raw_request, config)
    profile_preset = safe_dict(ANALYSIS_PROFILE_PRESETS.get(analysis_profile))
    explicit_selected_analysts = normalize_selected_analysts(
        pick_value(raw_request.get("selected_analysts"), config.get("selected_analysts"))
    )
    selected_analysts = explicit_selected_analysts or normalize_selected_analysts(profile_preset.get("selected_analysts"))
    if not selected_analysts:
        selected_analysts = list(DEFAULT_SELECTED_ANALYSTS)
    explicit_data_vendors = normalize_string_mapping(
        pick_value(raw_request.get("data_vendors"), config.get("data_vendors"), online_tools_dict.get("data_vendors"))
    )
    explicit_tool_vendors = normalize_string_mapping(
        pick_value(raw_request.get("tool_vendors"), config.get("tool_vendors"), online_tools_dict.get("tool_vendors"))
    )
    data_vendors = {**normalize_string_mapping(profile_preset.get("data_vendors")), **explicit_data_vendors}
    tool_vendors = {**normalize_string_mapping(profile_preset.get("tool_vendors")), **explicit_tool_vendors}
    alpha_vantage_min_interval_seconds = to_float(
        pick_value(
            raw_request.get("alpha_vantage_min_interval_seconds"),
            config.get("alpha_vantage_min_interval_seconds"),
            profile_preset.get("alpha_vantage_min_interval_seconds"),
        ),
        DEFAULT_ALPHA_VANTAGE_MIN_INTERVAL_SECONDS,
    )
    env = os.environ
    return {
        "enabled": to_bool(
            pick_value(raw_request.get("enabled"), config.get("enabled"), env.get("TRADINGAGENTS_ENABLED")),
            False,
        ),
        "mode": normalize_mode(pick_value(raw_request.get("mode"), config.get("mode"))),
        "cost_budget_tokens": to_int(
            pick_value(
                raw_request.get("cost_budget_tokens"),
                config.get("cost_budget_tokens"),
                env.get("TRADINGAGENTS_COST_BUDGET_TOKENS"),
            ),
            DEFAULT_COST_BUDGET_TOKENS,
        ),
        "timeout_seconds": to_int(
            pick_value(
                raw_request.get("timeout_seconds"),
                config.get("timeout_seconds"),
                env.get("TRADINGAGENTS_TIMEOUT_SECONDS"),
            ),
            DEFAULT_TIMEOUT_SECONDS,
        ),
        "version_guard": clean_text(
            pick_value(
                raw_request.get("version_guard"),
                config.get("version_guard"),
                env.get("TRADINGAGENTS_VERSION_GUARD"),
            )
        )
        or DEFAULT_VERSION_GUARD,
        "backend_url": clean_text(
            pick_value(
                raw_request.get("backend_url"),
                config.get("backend_url"),
                env.get("TRADINGAGENTS_BACKEND_URL"),
            )
        ),
        "min_evidence_count": to_int(pick_value(raw_request.get("min_evidence_count"), config.get("min_evidence_count")), 0),
        "min_catalyst_count": to_int(pick_value(raw_request.get("min_catalyst_count"), config.get("min_catalyst_count")), 0),
        "llm_provider": clean_text(pick_value(raw_request.get("llm_provider"), config.get("llm_provider"))),
        "deep_think_llm": clean_text(
            pick_value(raw_request.get("deep_think_llm"), config.get("deep_think_llm"), profile_preset.get("deep_think_llm"))
        ),
        "quick_think_llm": clean_text(
            pick_value(raw_request.get("quick_think_llm"), config.get("quick_think_llm"), profile_preset.get("quick_think_llm"))
        ),
        "online_tools": online_tools,
        "analysis_profile": analysis_profile,
        "selected_analysts": selected_analysts,
        "data_vendors": data_vendors,
        "tool_vendors": tool_vendors,
        "auto_profile_fallback": to_bool(
            pick_value(raw_request.get("auto_profile_fallback"), config.get("auto_profile_fallback"), env.get("TRADINGAGENTS_AUTO_PROFILE_FALLBACK")),
            True,
        ),
        "prefer_cached_recovery": to_bool(
            pick_value(
                raw_request.get("prefer_cached_recovery"),
                config.get("prefer_cached_recovery"),
                env.get("TRADINGAGENTS_PREFER_CACHED_RECOVERY"),
            ),
            True,
        ),
        "alpha_vantage_min_interval_seconds": max(alpha_vantage_min_interval_seconds, 0.0),
        "max_debate_rounds": to_int(
            pick_value(raw_request.get("max_debate_rounds"), config.get("max_debate_rounds"), profile_preset.get("max_debate_rounds")),
            1,
        ),
        "max_risk_discuss_rounds": to_int(
            pick_value(
                raw_request.get("max_risk_discuss_rounds"),
                config.get("max_risk_discuss_rounds"),
                profile_preset.get("max_risk_discuss_rounds"),
            ),
            1,
        ),
        "debug": to_bool(pick_value(raw_request.get("debug"), config.get("debug")), False),
    }


def build_decision_memo_base(
    *,
    status: str,
    requested_ticker: str,
    normalized_ticker: str,
    upstream_ticker: str,
    analysis_date: str,
    tradingagents_version: str,
    evidence_count: int,
    catalyst_count: int,
    thesis_id: str,
    market_context_available: bool,
    cost_budget_tokens: int,
    timeout_seconds: int,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "layer": "decision_advisory",
        "source": SOURCE_VALUE,
        "version": BRIDGE_VERSION,
        "tradingagents_version": clean_text(tradingagents_version) or "unknown",
        "requested_ticker": requested_ticker,
        "normalized_ticker": normalized_ticker,
        "upstream_ticker": upstream_ticker,
        "analysis_date": analysis_date,
        "status": status if status in STATUS_VALUES else "error",
        "input_summary": {
            "thesis_id": thesis_id,
            "evidence_count": evidence_count,
            "catalyst_count": catalyst_count,
            "market_context_available": market_context_available,
        },
        "bull_case": {"key_arguments": [], "confidence": "low", "supporting_evidence_refs": []},
        "bear_case": {"key_arguments": [], "confidence": "low", "supporting_evidence_refs": []},
        "risk_assessment": {"key_risks": [], "portfolio_impact": "", "liquidity_concern": False},
        "decision": {
            "action": "no_opinion",
            "conviction": "low",
            "rationale": "No advisory decision is available.",
        },
        "key_disagreements": [],
        "invalidation_triggers": [],
        "pair_basket_ideas": [],
        "cost_summary": {
            "requested_budget_tokens": cost_budget_tokens,
            "observed_tokens": None,
            "timeout_seconds": timeout_seconds,
            "observed_latency_ms": None,
        },
        "warnings": dedupe_warnings([*MANDATORY_WARNINGS, *(warnings or [])]),
    }


def normalize_case_payload(value: Any) -> dict[str, Any]:
    case = safe_dict(value)
    return {
        "key_arguments": normalize_string_list(case.get("key_arguments") or case.get("arguments") or case.get("points")),
        "confidence": normalize_confidence(case.get("confidence")),
        "supporting_evidence_refs": normalize_string_list(
            case.get("supporting_evidence_refs") or case.get("evidence_refs") or case.get("supporting_claims")
        ),
    }


def normalize_risk_payload(value: Any) -> dict[str, Any]:
    risk = safe_dict(value)
    return {
        "key_risks": normalize_string_list(risk.get("key_risks") or risk.get("risks")),
        "portfolio_impact": clean_text(risk.get("portfolio_impact") or risk.get("summary")),
        "liquidity_concern": to_bool(risk.get("liquidity_concern"), False),
    }


def normalize_decision_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"action": normalize_action(value), "conviction": "low", "rationale": clean_text(value)}
    decision = safe_dict(value)
    return {
        "action": normalize_action(decision.get("action")),
        "conviction": normalize_confidence(decision.get("conviction") or decision.get("confidence")),
        "rationale": clean_text(decision.get("rationale") or decision.get("summary") or decision.get("reason")),
    }


def infer_action_from_text(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return "no_opinion"
    if "underweight" in text or re.search(r"\bsell\b", text):
        return "sell"
    if "overweight" in text or re.search(r"\bbuy\b", text):
        return "buy"
    if re.search(r"\bhold\b", text):
        return "hold"
    return "no_opinion"


def split_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if clean_text(line)]


def strip_markdown_emphasis(text: str) -> str:
    return clean_text(str(text or "").replace("**", "").replace("__", "").replace("`", ""))


def strip_role_history_label(text: str) -> str:
    cleaned = strip_markdown_emphasis(text)
    for prefix in (
        "Bull Analyst:",
        "Bear Analyst:",
        "Aggressive Analyst:",
        "Conservative Analyst:",
        "Neutral Analyst:",
    ):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = clean_text(cleaned[len(prefix) :])
            break
    return cleaned


def strip_final_transaction_prefix(text: str) -> str:
    cleaned_lines = [
        line
        for line in split_non_empty_lines(text)
        if not clean_text(line).upper().startswith("FINAL TRANSACTION PROPOSAL:")
    ]
    return "\n".join(cleaned_lines).strip()


def heading_matches(line: str, candidates: tuple[str, ...]) -> bool:
    normalized = strip_markdown_emphasis(line).lower()
    return any(candidate in normalized for candidate in candidates)


def normalize_report_bullet(line: str) -> str:
    text = clean_text(line)
    while text[:1] in {"-", "*"}:
        text = clean_text(text[1:])
    if text and text[0].isdigit():
        marker_end = 1
        while marker_end < len(text) and text[marker_end].isdigit():
            marker_end += 1
        if marker_end < len(text) and text[marker_end] in {".", ")"}:
            text = clean_text(text[marker_end + 1 :])
    return strip_markdown_emphasis(text)


def extract_report_items(report: str, section_markers: tuple[str, ...], *, max_items: int = 4) -> list[str]:
    lines = split_non_empty_lines(strip_final_transaction_prefix(report))
    if not lines:
        return []
    matched: list[str] = []
    active = False
    for line in lines:
        if line.startswith("#"):
            active = heading_matches(line, section_markers)
            continue
        if not active:
            continue
        normalized = normalize_report_bullet(line)
        if not normalized:
            continue
        if normalized.lower().startswith("trading implication"):
            continue
        if normalized not in matched:
            matched.append(normalized)
        if len(matched) >= max_items:
            break
    return matched


def extract_exec_summary(report: str, *, max_sentences: int = 3) -> str:
    text = strip_final_transaction_prefix(report)
    if not text:
        return ""
    plain_text = strip_markdown_emphasis(text)
    lowered_plain = plain_text.lower()
    summary_marker = "executive summary"
    summary_start = lowered_plain.find(summary_marker)
    if summary_start != -1:
        summary_block = plain_text[summary_start + len(summary_marker) :]
        if summary_block.lstrip().startswith(":"):
            summary_block = summary_block.lstrip()[1:]
        lowered_block = summary_block.lower()
        cut_positions = [
            index
            for index in (
                lowered_block.find("3. investment thesis"),
                lowered_block.find("investment thesis"),
            )
            if index != -1
        ]
        if cut_positions:
            summary_block = summary_block[: min(cut_positions)]
        numbered_summary = clean_text(summary_block)
        if numbered_summary:
            sentences = [segment.strip() for segment in numbered_summary.split(". ") if clean_text(segment)]
            summary = ". ".join(sentences[:max_sentences]).strip() if sentences else numbered_summary
            if summary and not summary.endswith("."):
                summary += "."
            return summary
    inline_match = re.search(
        r"Executive Summary\s*:?\s*(.+?)(?:\n\s*\d+\.\s|\n\s*#+\s|Investment Thesis\s*:|$)",
        plain_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if inline_match:
        inline_summary = clean_text(strip_markdown_emphasis(inline_match.group(1)))
        if inline_summary:
            sentences = [segment.strip() for segment in inline_summary.split(". ") if clean_text(segment)]
            summary = ". ".join(sentences[:max_sentences]).strip() if sentences else inline_summary
            if summary and not summary.endswith("."):
                summary += "."
            return summary
    lines = split_non_empty_lines(text)
    capture = False
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if capture and current:
                paragraphs.append(" ".join(current))
                current = []
            capture = "executive summary" in strip_markdown_emphasis(line).lower()
            continue
        if capture:
            if line.startswith("|"):
                continue
            current.append(strip_markdown_emphasis(line))
    if capture and current:
        paragraphs.append(" ".join(current))
    text_block = clean_text(" ".join(paragraphs)) if paragraphs else clean_text(strip_markdown_emphasis(lines[0]))
    if not text_block:
        return ""
    sentences = [segment.strip() for segment in text_block.split(". ") if clean_text(segment)]
    if not sentences:
        return text_block
    summary = ". ".join(sentences[:max_sentences]).strip()
    if summary and not summary.endswith("."):
        summary += "."
    return summary


def apply_report_fallbacks(memo: dict[str, Any], state: dict[str, Any]) -> None:
    fundamentals_report = str(state.get("fundamentals_report") or "")
    market_report = str(state.get("market_report") or "")
    sentiment_report = str(state.get("sentiment_report") or "")
    news_report = str(state.get("news_report") or "")
    investment_plan = str(state.get("investment_plan") or "")
    final_trade_decision = str(state.get("final_trade_decision") or "")
    bull_history = str(safe_dict(state.get("investment_debate_state")).get("bull_history") or "")
    bear_history = str(safe_dict(state.get("investment_debate_state")).get("bear_history") or "")
    bull_history_summary = strip_role_history_label(bull_history)
    bear_history_summary = strip_role_history_label(bear_history)

    bull_case = safe_dict(memo.get("bull_case"))
    bear_case = safe_dict(memo.get("bear_case"))
    risk_assessment = safe_dict(memo.get("risk_assessment"))
    decision = safe_dict(memo.get("decision"))

    if not safe_list(bull_case.get("key_arguments")):
        candidates = (
            extract_report_items(fundamentals_report, ("key fundamental strengths", "what stands out"), max_items=4)
            or extract_report_items(market_report, ("key points", "trend", "what stands out"), max_items=4)
        )
        if not candidates and bull_history_summary:
            candidates = [bull_history_summary[:240]]
        if candidates:
            memo["bull_case"] = {
                **bull_case,
                "key_arguments": candidates[:4],
                "confidence": bull_case.get("confidence") or "low",
                "supporting_evidence_refs": safe_list(bull_case.get("supporting_evidence_refs")),
            }

    if not safe_list(bear_case.get("key_arguments")) and bear_history_summary:
        memo["bear_case"] = {
            **bear_case,
            "key_arguments": [bear_history_summary[:240]],
            "confidence": bear_case.get("confidence") or "low",
            "supporting_evidence_refs": safe_list(bear_case.get("supporting_evidence_refs")),
        }

    if not safe_list(risk_assessment.get("key_risks")):
        risk_items = (
            extract_report_items(fundamentals_report, ("key risks", "watch items"), max_items=5)
            or extract_report_items(market_report, ("key risks", "risk"), max_items=5)
            or extract_report_items(news_report, ("risks",), max_items=5)
        )
        if risk_items:
            memo["risk_assessment"] = {
                **risk_assessment,
                "key_risks": risk_items[:5],
                "portfolio_impact": clean_text(risk_assessment.get("portfolio_impact")),
                "liquidity_concern": to_bool(risk_assessment.get("liquidity_concern"), False),
            }

    if clean_text(decision.get("rationale")) in {"", "BUY", "SELL", "HOLD", "NO_OPINION"}:
        rationale = (
            extract_exec_summary(final_trade_decision)
            or extract_exec_summary(investment_plan)
            or extract_exec_summary(fundamentals_report)
            or extract_exec_summary(market_report)
            or extract_exec_summary(sentiment_report)
        )
        if rationale:
            memo["decision"] = {
                **decision,
                "rationale": rationale,
            }

    if not clean_text(safe_dict(memo.get("risk_assessment")).get("portfolio_impact")):
        portfolio_impact = extract_exec_summary(investment_plan, max_sentences=2) or extract_exec_summary(final_trade_decision, max_sentences=2)
        if portfolio_impact:
            memo["risk_assessment"] = {
                **safe_dict(memo.get("risk_assessment")),
                "portfolio_impact": portfolio_impact,
                "liquidity_concern": to_bool(safe_dict(memo.get("risk_assessment")).get("liquidity_concern"), False),
            }


def derive_memo_status(memo: dict[str, Any]) -> str:
    bull_count = len(safe_list(safe_dict(memo.get("bull_case")).get("key_arguments")))
    bear_count = len(safe_list(safe_dict(memo.get("bear_case")).get("key_arguments")))
    risk_count = len(safe_list(safe_dict(memo.get("risk_assessment")).get("key_risks")))
    rationale = clean_text(safe_dict(memo.get("decision")).get("rationale"))
    action = clean_text(safe_dict(memo.get("decision")).get("action"))

    if bull_count and bear_count and action in ACTION_VALUES - {"no_opinion"} and rationale:
        return "ready"
    if bull_count or bear_count or risk_count or rationale:
        return "partial"
    return "error"


def apply_cost_checks(memo: dict[str, Any], observed_tokens: Any) -> None:
    if isinstance(observed_tokens, int):
        memo["cost_summary"]["observed_tokens"] = observed_tokens
        budget = memo["cost_summary"]["requested_budget_tokens"]
        if observed_tokens > budget:
            memo["warnings"] = dedupe_warnings(
                [*safe_list(memo.get("warnings")), f"Observed token usage exceeded the configured budget ({observed_tokens} > {budget})."]
            )
            if memo.get("status") == "ready":
                memo["status"] = "partial"
    else:
        memo["warnings"] = dedupe_warnings(
            [*safe_list(memo.get("warnings")), "Observed token usage was not available from the upstream run."]
        )


def apply_latency_measurement(memo: dict[str, Any], started_at: float | None) -> None:
    if started_at is None:
        return
    memo["cost_summary"]["observed_latency_ms"] = max(int((perf_counter() - started_at) * 1000), 0)


def adapt_upstream_payload(payload: Any, *, memo: dict[str, Any]) -> dict[str, Any]:
    data = safe_dict(payload)
    state = safe_dict(data.get("state"))

    memo["tradingagents_version"] = clean_text(data.get("tradingagents_version") or memo.get("tradingagents_version")) or "unknown"
    memo["analysis_date"] = normalize_analysis_date(data.get("analysis_date") or memo.get("analysis_date"))
    memo["bull_case"] = normalize_case_payload(data.get("bull_case") or state.get("bull_case") or state.get("bull"))
    memo["bear_case"] = normalize_case_payload(data.get("bear_case") or state.get("bear_case") or state.get("bear"))
    memo["risk_assessment"] = normalize_risk_payload(
        data.get("risk_assessment") or state.get("risk_assessment") or state.get("risk")
    )
    memo["decision"] = normalize_decision_payload(data.get("decision") or state.get("decision"))
    memo["key_disagreements"] = normalize_string_list(data.get("key_disagreements") or state.get("key_disagreements"))
    memo["invalidation_triggers"] = normalize_string_list(
        data.get("invalidation_triggers") or state.get("invalidation_triggers")
    )
    memo["pair_basket_ideas"] = normalize_string_list(data.get("pair_basket_ideas") or state.get("pair_basket_ideas"))
    memo["warnings"] = dedupe_warnings([*safe_list(memo.get("warnings")), *normalize_string_list(data.get("warnings"))])
    apply_report_fallbacks(memo, state)

    observed_tokens = None
    token_usage = safe_dict(data.get("token_usage"))
    if isinstance(data.get("cost_tokens_used"), int):
        observed_tokens = data.get("cost_tokens_used")
    elif isinstance(token_usage.get("total_tokens"), int):
        observed_tokens = token_usage.get("total_tokens")
    apply_cost_checks(memo, observed_tokens)

    if detect_market(memo["normalized_ticker"]) != "US":
        memo["warnings"] = dedupe_warnings(
            [*safe_list(memo.get("warnings")), "Local-market ticker support remains pilot-scoped and should be analyst-reviewed carefully."]
        )

    memo["status"] = derive_memo_status(memo)
    return memo


def state_log_directory(upstream_ticker: str) -> Path:
    return (REPO_ROOT / "results" / clean_text(upstream_ticker) / "TradingAgentsStrategy_logs").resolve()


def state_log_path(upstream_ticker: str, analysis_date: str) -> Path:
    trade_date = clean_text(analysis_date)[:10] or clean_text(analysis_date)
    return (state_log_directory(upstream_ticker) / f"full_states_log_{trade_date}.json").resolve()


def extract_state_log_trade_date(path: Path) -> str:
    match = re.search(r"full_states_log_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    return match.group(1) if match else ""


def state_has_recoverable_content(state: dict[str, Any]) -> bool:
    direct_fields = (
        state.get("fundamentals_report"),
        state.get("market_report"),
        state.get("sentiment_report"),
        state.get("news_report"),
        state.get("investment_plan"),
        state.get("final_trade_decision"),
        state.get("trader_investment_decision"),
    )
    if any(clean_text(value) for value in direct_fields):
        return True

    investment_debate_state = safe_dict(state.get("investment_debate_state"))
    risk_debate_state = safe_dict(state.get("risk_debate_state"))
    history_fields = (
        strip_role_history_label(investment_debate_state.get("bull_history")),
        strip_role_history_label(investment_debate_state.get("bear_history")),
        strip_role_history_label(risk_debate_state.get("aggressive_history")),
        strip_role_history_label(risk_debate_state.get("conservative_history")),
        strip_role_history_label(risk_debate_state.get("neutral_history")),
    )
    return any(clean_text(value) for value in history_fields)


def state_log_candidates(upstream_ticker: str, analysis_date: str) -> list[Path]:
    requested_path = state_log_path(upstream_ticker, analysis_date)
    requested_trade_date = clean_text(analysis_date)[:10] or clean_text(analysis_date)
    candidates: list[Path] = []
    seen: set[str] = set()

    if requested_path.exists():
        candidates.append(requested_path)
        seen.add(str(requested_path))

    log_dir = state_log_directory(upstream_ticker)
    if not log_dir.exists():
        return candidates

    for path in sorted(log_dir.glob("full_states_log_*.json"), reverse=True):
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        trade_date = extract_state_log_trade_date(path)
        if requested_trade_date and trade_date and trade_date > requested_trade_date:
            continue
        candidates.append(path.resolve())
        seen.add(resolved)
    return candidates


def recover_logged_payload(*, upstream_ticker: str, analysis_date: str, tradingagents_version: str) -> dict[str, Any] | None:
    requested_trade_date = clean_text(analysis_date)[:10] or clean_text(analysis_date)
    for path in state_log_candidates(upstream_ticker, analysis_date):
        try:
            state = safe_dict(load_json(path))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not state or not state_has_recoverable_content(state):
            continue
        final_trade_decision = str(state.get("final_trade_decision") or "")
        investment_plan = str(state.get("investment_plan") or "")
        trade_date = extract_state_log_trade_date(path) or requested_trade_date or clean_text(analysis_date)
        return {
            "analysis_date": normalize_analysis_date(trade_date),
            "tradingagents_version": tradingagents_version,
            "state": state,
            "decision": {
                "action": infer_action_from_text(final_trade_decision or investment_plan),
                "conviction": "low",
                "rationale": clean_text(infer_action_from_text(final_trade_decision or investment_plan)).upper() or "RECOVERED",
            },
            "warnings": [
                f"Recovered advisory content from `{path.name}` after the live bridge path failed or timed out.",
            ],
            "recovery_info": {
                "path": str(path),
                "same_day": bool(trade_date == requested_trade_date),
            },
        }
    return None


def fallback_profile_name(config: dict[str, Any], normalized_ticker: str) -> str:
    if not to_bool(config.get("auto_profile_fallback"), True):
        return ""
    if clean_text(config.get("analysis_profile")) not in {"", "full"}:
        return ""
    if normalize_selected_analysts(config.get("selected_analysts")) != list(DEFAULT_SELECTED_ANALYSTS):
        return ""
    if normalize_string_mapping(config.get("data_vendors")) or normalize_string_mapping(config.get("tool_vendors")):
        return ""
    if longbridge_available(env=os.environ):
        return "longbridge_market"
    market = detect_market(normalized_ticker)
    if market == "US":
        return "free_sec_fundamentals"
    if market in {"CN_SH", "CN_SZ"}:
        if clean_text(os.environ.get("TUSHARE_TOKEN")) or clean_text(os.environ.get("TUSHARE_PRO_TOKEN")):
            return "free_tushare_market"
        return "free_eastmoney_market"
    return ""


def smart_free_profile_name(normalized_ticker: str) -> str:
    if longbridge_available(env=os.environ):
        return "longbridge_market"
    market = detect_market(normalized_ticker)
    if market == "US":
        return "free_sec_fundamentals"
    if market in {"CN_SH", "CN_SZ"}:
        if clean_text(os.environ.get("TUSHARE_TOKEN")) or clean_text(os.environ.get("TUSHARE_PRO_TOKEN")):
            return "free_tushare_market"
        return "free_eastmoney_market"
    return ""


def build_profile_config(base_config: dict[str, Any], profile_name: str) -> dict[str, Any]:
    preset = safe_dict(ANALYSIS_PROFILE_PRESETS.get(profile_name))
    if not preset:
        return dict(base_config)
    fallback_config = dict(base_config)
    fallback_config["analysis_profile"] = profile_name
    fallback_config["selected_analysts"] = normalize_selected_analysts(preset.get("selected_analysts")) or fallback_config.get("selected_analysts")
    fallback_config["data_vendors"] = normalize_string_mapping(preset.get("data_vendors"))
    fallback_config["tool_vendors"] = normalize_string_mapping(preset.get("tool_vendors"))
    fallback_config["deep_think_llm"] = clean_text(preset.get("deep_think_llm")) or clean_text(fallback_config.get("deep_think_llm"))
    fallback_config["quick_think_llm"] = clean_text(preset.get("quick_think_llm")) or clean_text(fallback_config.get("quick_think_llm"))
    fallback_config["max_debate_rounds"] = to_int(preset.get("max_debate_rounds"), to_int(fallback_config.get("max_debate_rounds"), 1))
    fallback_config["max_risk_discuss_rounds"] = to_int(
        preset.get("max_risk_discuss_rounds"),
        to_int(fallback_config.get("max_risk_discuss_rounds"), 1),
    )
    fallback_config["alpha_vantage_min_interval_seconds"] = to_float(
        preset.get("alpha_vantage_min_interval_seconds"),
        to_float(fallback_config.get("alpha_vantage_min_interval_seconds"), 0.0),
    )
    fallback_config["auto_profile_fallback"] = False
    return fallback_config


def days_before(date_text: str, days: int) -> str:
    parsed = datetime.strptime(clean_text(date_text), "%Y-%m-%d")
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def latest_finite(series: list[float]) -> float:
    for value in reversed(series):
        if isinstance(value, (int, float)) and not math.isnan(float(value)):
            return float(value)
    return float("nan")


def format_snapshot_number(value: float, digits: int = 2) -> str:
    if math.isnan(value):
        return "N/A"
    return f"{value:.{digits}f}"


def market_snapshot_profile_name(config: dict[str, Any], normalized_ticker: str) -> str:
    profile_name = clean_text(config.get("analysis_profile"))
    if profile_name in {"free_eastmoney_market", "free_tushare_market", "longbridge_market"}:
        return profile_name
    candidate = fallback_profile_name(config, normalized_ticker)
    if candidate in {"free_eastmoney_market", "free_tushare_market", "longbridge_market"}:
        return candidate
    return ""


def us_fundamentals_snapshot_profile_name(config: dict[str, Any], normalized_ticker: str) -> str:
    if detect_market(normalized_ticker) != "US":
        return ""
    profile_name = clean_text(config.get("analysis_profile"))
    if profile_name == "free_sec_fundamentals":
        return profile_name
    candidate = fallback_profile_name(config, normalized_ticker)
    if candidate == "free_sec_fundamentals":
        return candidate
    return ""


def summarize_local_us_fundamentals_snapshot(
    *,
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
) -> dict[str, Any] | None:
    trade_date = clean_text(analysis_date)[:10] or clean_text(analysis_date)
    if not trade_date:
        return None
    fundamentals_report = get_sec_fundamentals(normalized_ticker, curr_date=trade_date)
    if not clean_text(fundamentals_report):
        return None
    rationale = (
        f"SEC fundamentals-only fallback for {normalized_ticker} as of {trade_date}. "
        "Treat this as a bounded fundamental snapshot until provider-backed debate and richer synthesis can run."
    )
    return {
        "analysis_date": analysis_date,
        "state": {
            "fundamentals_report": fundamentals_report,
            "investment_plan": "",
            "final_trade_decision": "",
        },
        "decision": {
            "action": "no_opinion",
            "conviction": "low",
            "rationale": rationale,
        },
        "warnings": [
            f"Recovered a bounded U.S. fundamentals snapshot through `free_sec_fundamentals` after the primary TradingAgents path failed: {failure_message}",
            "This fallback is fundamentals-only and should not be treated as a substitute for full provider-backed debate, news, and market synthesis.",
        ],
    }


def try_local_us_fundamentals_snapshot_fallback(
    *,
    config: dict[str, Any],
    memo: dict[str, Any],
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
    run_started_at: float | None,
    mode: str,
) -> dict[str, Any] | None:
    if mode == "required":
        return None
    profile_name = us_fundamentals_snapshot_profile_name(config, normalized_ticker)
    if not profile_name:
        return None
    profile_config = build_profile_config(config, profile_name) if clean_text(config.get("analysis_profile")) != profile_name else dict(config)
    try:
        payload = summarize_local_us_fundamentals_snapshot(
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=failure_message,
        )
    except Exception:
        return None
    if payload is None:
        return None
    adapted = adapt_upstream_payload(payload, memo=deepcopy(memo))
    adapted["warnings"] = dedupe_warnings(
        [
            *safe_list(adapted.get("warnings")),
            f"Analysis profile `{profile_name}` is active with analysts: {', '.join(normalize_selected_analysts(profile_config.get('selected_analysts')))}.",
            f"U.S. fundamentals snapshot fallback activated after primary profile failure: {failure_message}",
        ]
    )
    apply_latency_measurement(adapted, run_started_at)
    result = {"status": "degraded" if adapted["status"] != "ready" else "ok", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result


def hk_quote_snapshot_supported(normalized_ticker: str) -> bool:
    return detect_market(normalized_ticker) == "HK"


def summarize_local_hk_quote_snapshot(
    *,
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
) -> dict[str, Any] | None:
    trade_date = clean_text(analysis_date)[:10] or clean_text(analysis_date)
    if not trade_date:
        return None
    snapshot = fetch_hk_quote_snapshot(normalized_ticker, env=os.environ)
    price = snapshot.get("last_price")
    name = clean_text(snapshot.get("name")) or normalized_ticker
    if not isinstance(price, (int, float)):
        return None
    rationale = (
        f"HK quote-only fallback for {normalized_ticker} ({name}) as of {trade_date}: last public quote {price:.3f}. "
        "Treat this as a bounded quote snapshot until provider-backed debate, history, and fundamentals can run."
    )
    return {
        "analysis_date": analysis_date,
        "bull_case": {
            "key_arguments": [
                "A public Hong Kong quote snapshot was still recoverable through Eastmoney, so the bridge can preserve bounded price context even when the provider-backed path fails."
            ],
            "confidence": "low",
            "supporting_evidence_refs": [],
        },
        "bear_case": {
            "key_arguments": [],
            "confidence": "low",
            "supporting_evidence_refs": [],
        },
        "risk_assessment": {
            "key_risks": [
                f"Provider-backed TradingAgents path failed before a full memo was produced: {failure_message}",
                "This HK fallback is quote-only and excludes trend history, debate, news synthesis, and fundamentals detail.",
            ],
            "portfolio_impact": "Treat this as a low-confidence Hong Kong quote snapshot only. Require a later rerun with provider-backed analysis before using it for sizing, basket construction, or backtest handoff.",
            "liquidity_concern": False,
        },
        "decision": {
            "action": "no_opinion",
            "conviction": "low",
            "rationale": rationale,
        },
        "warnings": [
            "Recovered a bounded Hong Kong quote snapshot through `eastmoney_hk_quote` after the primary TradingAgents path failed.",
            "This fallback is quote-only and should not be treated as a substitute for full provider-backed analysis.",
        ],
    }


def try_local_hk_quote_snapshot_fallback(
    *,
    memo: dict[str, Any],
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
    run_started_at: float | None,
    mode: str,
) -> dict[str, Any] | None:
    if mode == "required" or not hk_quote_snapshot_supported(normalized_ticker):
        return None
    try:
        payload = summarize_local_hk_quote_snapshot(
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=failure_message,
        )
    except Exception:
        return None
    if payload is None:
        return None
    adapted = adapt_upstream_payload(payload, memo=memo)
    adapted["warnings"] = dedupe_warnings(
        [
            *safe_list(adapted.get("warnings")),
            f"HK quote snapshot fallback activated after primary profile failure: {failure_message}",
        ]
    )
    apply_latency_measurement(adapted, run_started_at)
    result = {"status": "degraded" if adapted["status"] != "ready" else "ok", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result


def market_snapshot_rows(profile_name: str, normalized_ticker: str, trade_date: str) -> list[dict[str, Any]]:
    start_date = days_before(trade_date, 400)
    if profile_name == "free_eastmoney_market":
        return fetch_eastmoney_daily_bars(normalized_ticker, start_date, trade_date, env=os.environ)
    if profile_name == "free_tushare_market":
        return fetch_tushare_daily_bars(normalized_ticker, start_date, trade_date, env=os.environ)
    if profile_name == "longbridge_market":
        return fetch_longbridge_daily_bars(normalized_ticker, start_date, trade_date, env=os.environ)
    raise ValueError(f"Profile `{profile_name}` does not support local market snapshot fallback.")


def summarize_local_market_snapshot(
    *,
    profile_name: str,
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
) -> dict[str, Any] | None:
    trade_date = clean_text(analysis_date)[:10]
    if not trade_date:
        return None
    rows = market_snapshot_rows(profile_name, normalized_ticker, trade_date)
    if len(rows) < 20:
        return None

    latest_row = rows[-1]
    latest_close = float(latest_row.get("close") or float("nan"))
    latest_change = float(latest_row.get("change") or float("nan"))
    latest_pct_chg = float(latest_row.get("pct_chg") or float("nan"))
    latest_volume = float(latest_row.get("vol") or float("nan"))
    sma20 = latest_finite(market_indicator_series(rows, "boll"))
    sma50 = latest_finite(market_indicator_series(rows, "close_50_sma"))
    rsi14 = latest_finite(market_indicator_series(rows, "rsi"))
    recent_volumes = [float(row.get("vol") or float("nan")) for row in rows[-20:]]
    valid_recent_volumes = [value for value in recent_volumes if not math.isnan(value)]
    avg20_volume = sum(valid_recent_volumes) / len(valid_recent_volumes) if valid_recent_volumes else float("nan")
    volume_ratio = (
        latest_volume / avg20_volume
        if valid_recent_volumes and not math.isnan(avg20_volume) and avg20_volume != 0 and not math.isnan(latest_volume)
        else float("nan")
    )

    bull_points: list[str] = []
    bear_points: list[str] = []
    risk_points: list[str] = [
        f"Provider-backed TradingAgents path failed, so this fallback used `{profile_name}` market data only: {failure_message}",
        "This snapshot excludes provider-backed debate, news synthesis, and fundamentals review.",
    ]

    if not math.isnan(latest_close) and not math.isnan(sma20):
        if latest_close >= sma20:
            bull_points.append(
                f"{trade_date} close {format_snapshot_number(latest_close)} is above the 20-day average {format_snapshot_number(sma20)}, which keeps short-term price support intact."
            )
        else:
            bear_points.append(
                f"{trade_date} close {format_snapshot_number(latest_close)} is below the 20-day average {format_snapshot_number(sma20)}, which points to short-term weakness."
            )
            risk_points.append(
                f"Price is still below the 20-day average {format_snapshot_number(sma20)}, so rebound confirmation is not in place yet."
            )

    if not math.isnan(latest_close) and not math.isnan(sma50):
        if latest_close >= sma50:
            bull_points.append(
                f"Latest close remains above the 50-day average {format_snapshot_number(sma50)}, so the medium-term trend has not broken."
            )
        else:
            bear_points.append(
                f"Latest close is below the 50-day average {format_snapshot_number(sma50)}, which means the medium-term trend is still under pressure."
            )
            risk_points.append(
                f"Price remains below the 50-day average {format_snapshot_number(sma50)}, so medium-term trend repair is incomplete."
            )

    if not math.isnan(rsi14):
        if rsi14 <= 35:
            bull_points.append(
                f"14-day RSI is {format_snapshot_number(rsi14, 1)}, close to oversold territory, so a technical rebound remains possible."
            )
        elif rsi14 >= 70:
            bear_points.append(
                f"14-day RSI is {format_snapshot_number(rsi14, 1)}, already in an overbought zone and exposed to mean-reversion risk."
            )
            risk_points.append(
                f"RSI at {format_snapshot_number(rsi14, 1)} is elevated, so chasing strength without confirmation would be risky."
            )

    if not math.isnan(volume_ratio):
        if volume_ratio >= 1.3:
            bull_points.append(
                f"Latest volume ran at {format_snapshot_number(volume_ratio, 2)}x the 20-day average, showing the move still has participation."
            )
        elif volume_ratio <= 0.7:
            risk_points.append(
                f"Latest volume was only {format_snapshot_number(volume_ratio, 2)}x the 20-day average, so the move lacks strong participation."
            )

    if not bull_points:
        bull_points.append(
            f"Local market data was still recoverable through `{profile_name}`, so the bridge can preserve a bounded market snapshot even when the provider path is unavailable."
        )

    rationale = (
        f"Market-only fallback snapshot for {normalized_ticker}: close {format_snapshot_number(latest_close)} on {trade_date}, "
        f"day change {format_snapshot_number(latest_change)} ({format_snapshot_number(latest_pct_chg)}%), "
        f"20-day average {format_snapshot_number(sma20)}, 50-day average {format_snapshot_number(sma50)}, "
        f"RSI {format_snapshot_number(rsi14, 1)}. Keep this at watchlist-grade confidence until provider-backed news/fundamentals analysis can run."
    )
    portfolio_impact = (
        "Treat this as a low-confidence market snapshot only. Require a later rerun with provider-backed debate plus fundamentals/news before turning it into a trading expression, basket, or backtest handoff."
    )
    return {
        "analysis_date": analysis_date,
        "bull_case": {
            "key_arguments": bull_points[:4],
            "confidence": "low",
            "supporting_evidence_refs": [],
        },
        "bear_case": {
            "key_arguments": bear_points[:3],
            "confidence": "low",
            "supporting_evidence_refs": [],
        },
        "risk_assessment": {
            "key_risks": dedupe_warnings(risk_points)[:5],
            "portfolio_impact": portfolio_impact,
            "liquidity_concern": False,
        },
        "decision": {
            "action": "no_opinion",
            "conviction": "low",
            "rationale": rationale,
        },
        "warnings": [
            f"Recovered a bounded local market snapshot through `{profile_name}` after the primary TradingAgents path failed.",
            "This fallback is market-data-only and should not be treated as a substitute for full provider-backed analysis.",
        ],
    }


def try_local_market_snapshot_fallback(
    *,
    config: dict[str, Any],
    memo: dict[str, Any],
    normalized_ticker: str,
    analysis_date: str,
    failure_message: str,
    run_started_at: float | None,
    mode: str,
) -> dict[str, Any] | None:
    if mode == "required":
        return None
    profile_name = market_snapshot_profile_name(config, normalized_ticker)
    if not profile_name:
        return None
    snapshot_config = build_profile_config(config, profile_name) if clean_text(config.get("analysis_profile")) != profile_name else dict(config)
    try:
        payload = summarize_local_market_snapshot(
            profile_name=profile_name,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=failure_message,
        )
    except Exception:
        return None
    if payload is None:
        return None
    adapted = adapt_upstream_payload(payload, memo=memo)
    adapted["warnings"] = dedupe_warnings(
        [
            *safe_list(adapted.get("warnings")),
            f"Analysis profile `{profile_name}` is active with analysts: {', '.join(normalize_selected_analysts(snapshot_config.get('selected_analysts')))}.",
            f"Local market snapshot fallback activated after primary profile failure: {failure_message}",
        ]
    )
    apply_latency_measurement(adapted, run_started_at)
    result = {"status": "degraded" if adapted["status"] != "ready" else "ok", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result


def fallback_timeout_seconds(base_timeout_seconds: int) -> int:
    if base_timeout_seconds <= 0:
        return 45
    return max(15, min(60, base_timeout_seconds // 2 or 1))


def should_prefer_cached_recovery(config: dict[str, Any]) -> bool:
    if not to_bool(config.get("prefer_cached_recovery"), True):
        return False
    profile_name = clean_text(config.get("analysis_profile"))
    selected_analysts = normalize_selected_analysts(config.get("selected_analysts"))
    data_vendors = normalize_string_mapping(config.get("data_vendors"))
    tool_vendors = normalize_string_mapping(config.get("tool_vendors"))

    if profile_name in {"", "full"}:
        return selected_analysts == list(DEFAULT_SELECTED_ANALYSTS) and not data_vendors and not tool_vendors

    preset = safe_dict(ANALYSIS_PROFILE_PRESETS.get(profile_name))
    if not preset:
        return False
    return (
        selected_analysts == normalize_selected_analysts(preset.get("selected_analysts"))
        and data_vendors == normalize_string_mapping(preset.get("data_vendors"))
        and tool_vendors == normalize_string_mapping(preset.get("tool_vendors"))
    )


def build_recovered_result(
    *,
    recovered_payload: dict[str, Any],
    memo: dict[str, Any],
    run_started_at: float | None,
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    adapted = adapt_upstream_payload(recovered_payload, memo=memo)
    if extra_warnings:
        adapted["warnings"] = dedupe_warnings([*safe_list(adapted.get("warnings")), *extra_warnings])
    apply_latency_measurement(adapted, run_started_at)
    result = {"status": "degraded" if adapted["status"] != "ready" else "ok", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result


def build_markdown_report(result: dict[str, Any]) -> str:
    memo = safe_dict(result.get("decision_memo"))
    decision = safe_dict(memo.get("decision"))
    bull_case = safe_dict(memo.get("bull_case"))
    risk_assessment = safe_dict(memo.get("risk_assessment"))
    lines = [
        "# TradingAgents Decision Memo",
        "",
        "This output is advisory only. It is not factual evidence verification.",
        "",
        f"- Status: `{clean_text(result.get('status')) or 'unknown'}`",
        f"- Memo status: `{clean_text(memo.get('status')) or 'unknown'}`",
        f"- Requested ticker: `{clean_text(memo.get('requested_ticker')) or 'n/a'}`",
        f"- Normalized ticker: `{clean_text(memo.get('normalized_ticker')) or 'n/a'}`",
        f"- Upstream ticker: `{clean_text(memo.get('upstream_ticker')) or 'n/a'}`",
        f"- Decision: `{clean_text(decision.get('action')) or 'no_opinion'}` / `{clean_text(decision.get('conviction')) or 'low'}`",
    ]
    rationale = clean_text(decision.get("rationale"))
    if rationale:
        lines.append(f"- Rationale: {rationale}")
    bull_points = normalize_string_list(bull_case.get("key_arguments"))
    if bull_points:
        lines.extend(["", "## Key Bull Points", ""])
        lines.extend([f"- {item}" for item in bull_points[:4]])
    risk_points = normalize_string_list(risk_assessment.get("key_risks"))
    if risk_points:
        lines.extend(["", "## Key Risks", ""])
        lines.extend([f"- {item}" for item in risk_points[:5]])
    portfolio_impact = clean_text(risk_assessment.get("portfolio_impact"))
    if portfolio_impact:
        lines.extend(["", "## Portfolio Impact", "", portfolio_impact])
    warnings = normalize_string_list(memo.get("warnings"))
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend([f"- {item}" for item in warnings])
    return "\n".join(lines) + "\n"


def load_fixture_payload(raw_request: dict[str, Any]) -> dict[str, Any]:
    fixture = safe_dict(raw_request.get("fixture"))
    root = resolve_path(clean_text(fixture.get("root") or "tests/fixtures/tradingagents-decision-bridge"))
    response_name = clean_text(fixture.get("response"))
    if not response_name:
        raise ValueError("Fixture mode requires fixture.response.")
    return safe_dict(load_json(root / response_name))


def default_package_probe() -> tuple[bool, str]:
    spec = util.find_spec("tradingagents")
    if spec is None:
        return False, ""
    return True, resolve_package_version("tradingagents", spec=spec)


@contextmanager
def temporary_sec_vendor_registration(required: bool) -> Iterator[None]:
    if not required:
        yield
        return

    try:
        interface_module = import_module("tradingagents.dataflows.interface")
    except Exception:
        yield
        return

    vendor_name = "sec_companyfacts"
    method_overrides = {
        "get_fundamentals": get_sec_fundamentals,
        "get_balance_sheet": get_sec_balance_sheet,
        "get_cashflow": get_sec_cashflow,
        "get_income_statement": get_sec_income_statement,
    }
    original_vendor_list = list(safe_list(getattr(interface_module, "VENDOR_LIST", [])))
    original_method_maps = {
        method: dict(safe_dict(safe_dict(getattr(interface_module, "VENDOR_METHODS", {})).get(method)))
        for method in method_overrides
    }

    try:
        vendor_list = list(original_vendor_list)
        if vendor_name not in vendor_list:
            vendor_list.append(vendor_name)
        interface_module.VENDOR_LIST = vendor_list

        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, implementation in method_overrides.items():
            patched = dict(original_method_maps[method_name])
            patched[vendor_name] = implementation
            vendor_methods[method_name] = patched
        interface_module.VENDOR_METHODS = vendor_methods
        yield
    finally:
        interface_module.VENDOR_LIST = original_vendor_list
        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, original_mapping in original_method_maps.items():
            vendor_methods[method_name] = original_mapping
        interface_module.VENDOR_METHODS = vendor_methods


@contextmanager
def temporary_tushare_vendor_registration(required: bool) -> Iterator[None]:
    if not required:
        yield
        return

    try:
        interface_module = import_module("tradingagents.dataflows.interface")
    except Exception:
        yield
        return

    vendor_name = "tushare_market"
    method_overrides = {
        "get_stock_data": get_tushare_stock_data,
        "get_indicators": get_tushare_indicator,
    }
    original_vendor_list = list(safe_list(getattr(interface_module, "VENDOR_LIST", [])))
    original_method_maps = {
        method: dict(safe_dict(safe_dict(getattr(interface_module, "VENDOR_METHODS", {})).get(method)))
        for method in method_overrides
    }

    try:
        vendor_list = list(original_vendor_list)
        if vendor_name not in vendor_list:
            vendor_list.append(vendor_name)
        interface_module.VENDOR_LIST = vendor_list

        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, implementation in method_overrides.items():
            patched = dict(original_method_maps[method_name])
            patched[vendor_name] = implementation
            vendor_methods[method_name] = patched
        interface_module.VENDOR_METHODS = vendor_methods
        yield
    finally:
        interface_module.VENDOR_LIST = original_vendor_list
        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, original_mapping in original_method_maps.items():
            vendor_methods[method_name] = original_mapping
        interface_module.VENDOR_METHODS = vendor_methods


@contextmanager
def temporary_eastmoney_vendor_registration(required: bool) -> Iterator[None]:
    if not required:
        yield
        return

    try:
        interface_module = import_module("tradingagents.dataflows.interface")
    except Exception:
        yield
        return

    vendor_name = "eastmoney_market"
    method_overrides = {
        "get_stock_data": get_eastmoney_stock_data,
        "get_indicators": get_eastmoney_indicator,
    }
    original_vendor_list = list(safe_list(getattr(interface_module, "VENDOR_LIST", [])))
    original_method_maps = {
        method: dict(safe_dict(safe_dict(getattr(interface_module, "VENDOR_METHODS", {})).get(method)))
        for method in method_overrides
    }

    try:
        vendor_list = list(original_vendor_list)
        if vendor_name not in vendor_list:
            vendor_list.append(vendor_name)
        interface_module.VENDOR_LIST = vendor_list

        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, implementation in method_overrides.items():
            patched = dict(original_method_maps[method_name])
            patched[vendor_name] = implementation
            vendor_methods[method_name] = patched
        interface_module.VENDOR_METHODS = vendor_methods
        yield
    finally:
        interface_module.VENDOR_LIST = original_vendor_list
        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, original_mapping in original_method_maps.items():
            vendor_methods[method_name] = original_mapping
        interface_module.VENDOR_METHODS = vendor_methods


@contextmanager
def temporary_longbridge_vendor_registration(required: bool) -> Iterator[None]:
    if not required:
        yield
        return

    try:
        interface_module = import_module("tradingagents.dataflows.interface")
    except Exception:
        yield
        return

    vendor_name = "longbridge_market"
    method_overrides = {
        "get_stock_data": get_longbridge_stock_data,
        "get_indicators": get_longbridge_indicator,
    }
    original_vendor_list = list(safe_list(getattr(interface_module, "VENDOR_LIST", [])))
    original_method_maps = {
        method: dict(safe_dict(safe_dict(getattr(interface_module, "VENDOR_METHODS", {})).get(method)))
        for method in method_overrides
    }

    try:
        vendor_list = list(original_vendor_list)
        if vendor_name not in vendor_list:
            vendor_list.append(vendor_name)
        interface_module.VENDOR_LIST = vendor_list

        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, implementation in method_overrides.items():
            patched = dict(original_method_maps[method_name])
            patched[vendor_name] = implementation
            vendor_methods[method_name] = patched
        interface_module.VENDOR_METHODS = vendor_methods
        yield
    finally:
        interface_module.VENDOR_LIST = original_vendor_list
        vendor_methods = safe_dict(getattr(interface_module, "VENDOR_METHODS", {}))
        for method_name, original_mapping in original_method_maps.items():
            vendor_methods[method_name] = original_mapping
        interface_module.VENDOR_METHODS = vendor_methods


@contextmanager
def temporary_alpha_vantage_throttle(min_interval_seconds: float) -> Iterator[None]:
    if min_interval_seconds <= 0:
        yield
        return

    module_names = (
        "tradingagents.dataflows.alpha_vantage_common",
        "tradingagents.dataflows.alpha_vantage_stock",
        "tradingagents.dataflows.alpha_vantage_indicator",
        "tradingagents.dataflows.alpha_vantage_fundamentals",
        "tradingagents.dataflows.alpha_vantage_news",
    )
    try:
        common_module = import_module(module_names[0])
    except Exception:
        yield
        return

    original = getattr(common_module, "_make_api_request", None)
    if not callable(original):
        yield
        return

    lock = Lock()
    state = {"last_called_at": 0.0}

    def throttled_make_api_request(function_name: str, params: dict[str, Any]) -> Any:
        with lock:
            elapsed = monotonic() - state["last_called_at"]
            remaining = min_interval_seconds - elapsed
            if remaining > 0:
                sleep(remaining)
            result = original(function_name, params)
            state["last_called_at"] = monotonic()
            return result

    patched_modules: list[tuple[Any, Any]] = []
    try:
        for module_name in module_names:
            try:
                module = import_module(module_name)
            except Exception:
                continue
            current = getattr(module, "_make_api_request", None)
            if callable(current):
                patched_modules.append((module, current))
                setattr(module, "_make_api_request", throttled_make_api_request)
        yield
    finally:
        for module, original_value in reversed(patched_modules):
            setattr(module, "_make_api_request", original_value)


def default_upstream_runner(context: dict[str, Any]) -> dict[str, Any]:
    bridge_config = safe_dict(context.get("bridge_config"))
    selected_provider = clean_text(bridge_config.get("llm_provider")) or "auto"
    provider_resolution = resolve_provider_runtime(
        env=os.environ,
        selected_provider=selected_provider,
        backend_url=bridge_config.get("backend_url"),
    )
    resolved_provider = clean_text(provider_resolution.get("selected_provider")) or "openai"
    required_env_var = clean_text(provider_resolution.get("credential_env_var"))
    if required_env_var and not bool(provider_resolution.get("credential_present")):
        raise RuntimeError(
            f"{required_env_var} is missing for llm_provider `{resolved_provider}`."
        )

    with temporary_environment_overrides(safe_dict(provider_resolution.get("env_overrides"))):
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = resolved_provider
        if clean_text(bridge_config.get("deep_think_llm")):
            config["deep_think_llm"] = bridge_config["deep_think_llm"]
        if clean_text(bridge_config.get("quick_think_llm")):
            config["quick_think_llm"] = bridge_config["quick_think_llm"]
        data_vendors = normalize_string_mapping(bridge_config.get("data_vendors"))
        if data_vendors:
            config["data_vendors"] = {**safe_dict(config.get("data_vendors")), **data_vendors}
        tool_vendors = normalize_string_mapping(bridge_config.get("tool_vendors"))
        if tool_vendors:
            config["tool_vendors"] = {**safe_dict(config.get("tool_vendors")), **tool_vendors}
        selected_analysts = normalize_selected_analysts(bridge_config.get("selected_analysts")) or list(DEFAULT_SELECTED_ANALYSTS)
        resolved_backend_url = clean_text(provider_resolution.get("backend_url"))
        provider_name = clean_text(config.get("llm_provider")).lower() or "openai"
        if resolved_backend_url:
            config["backend_url"] = resolved_backend_url
        elif provider_name in {"anthropic", "google"}:
            config["backend_url"] = None
        config["max_debate_rounds"] = to_int(bridge_config.get("max_debate_rounds"), 1)
        config["max_risk_discuss_rounds"] = to_int(bridge_config.get("max_risk_discuss_rounds"), 1)
        if bridge_config.get("online_tools") is not None:
            config["online_tools"] = bridge_config.get("online_tools")

        needs_sec_vendor = "sec_companyfacts" in set(data_vendors.values()) or "sec_companyfacts" in set(tool_vendors.values())
        needs_tushare_vendor = "tushare_market" in set(data_vendors.values()) or "tushare_market" in set(tool_vendors.values())
        needs_eastmoney_vendor = "eastmoney_market" in set(data_vendors.values()) or "eastmoney_market" in set(
            tool_vendors.values()
        )
        needs_longbridge_vendor = "longbridge_market" in set(data_vendors.values()) or "longbridge_market" in set(
            tool_vendors.values()
        )
        with temporary_sec_vendor_registration(needs_sec_vendor):
            with temporary_tushare_vendor_registration(needs_tushare_vendor):
                with temporary_eastmoney_vendor_registration(needs_eastmoney_vendor):
                    with temporary_longbridge_vendor_registration(needs_longbridge_vendor):
                        graph = TradingAgentsGraph(
                            selected_analysts=selected_analysts,
                            debug=to_bool(bridge_config.get("debug"), False),
                            config=config,
                        )
                        analysis_date = clean_text(context.get("analysis_date"))[:10]
                        with temporary_alpha_vantage_throttle(to_float(bridge_config.get("alpha_vantage_min_interval_seconds"), 0.0)):
                            try:
                                raw_result = graph.propagate(clean_text(context.get("upstream_ticker")), analysis_date)
                            except Exception as exc:
                                backend_label = resolved_backend_url or "provider default backend"
                                raise RuntimeError(
                                    f"TradingAgents propagate failed for provider `{resolved_provider}` via `{backend_label}`: {format_exception_message(exc)}"
                                ) from exc

        if isinstance(raw_result, tuple):
            state = raw_result[0] if len(raw_result) > 0 else {}
            decision = raw_result[1] if len(raw_result) > 1 else {}
        else:
            state = {}
            decision = raw_result

    return {"analysis_date": context.get("analysis_date"), "state": state, "decision": decision}


def invoke_with_timeout(runner: UpstreamRunner, context: dict[str, Any], timeout_seconds: int) -> Any:
    state: dict[str, Any] = {"result": None, "exception": None}
    completed = Event()

    def target() -> None:
        try:
            state["result"] = runner(context)
        except Exception as exc:  # pragma: no cover
            state["exception"] = exc
        finally:
            completed.set()

    worker = Thread(target=target, name="tradingagents-bridge-runner", daemon=True)
    worker.start()
    if not completed.wait(timeout=max(timeout_seconds, 1)):
        raise FuturesTimeoutError()
    if state["exception"] is not None:
        raise state["exception"]
    return state["result"]


def try_profile_fallback(
    *,
    runner: UpstreamRunner,
    config: dict[str, Any],
    memo: dict[str, Any],
    requested_ticker: str,
    normalized_ticker: str,
    upstream_ticker: str,
    analysis_date: str,
    thesis: dict[str, Any],
    evidence: list[Any],
    catalysts: list[Any],
    market_context: dict[str, Any],
    failure_message: str,
    run_started_at: float | None,
) -> dict[str, Any] | None:
    profile_name = fallback_profile_name(config, normalized_ticker)
    if not profile_name:
        return None

    fallback_config = build_profile_config(config, profile_name)
    try:
        payload = invoke_with_timeout(
            runner,
            {
                "requested_ticker": requested_ticker,
                "normalized_ticker": normalized_ticker,
                "upstream_ticker": upstream_ticker,
                "analysis_date": analysis_date,
                "thesis": thesis,
                "evidence": evidence,
                "catalysts": catalysts,
                "market_context": market_context,
                "bridge_config": fallback_config,
            },
            fallback_timeout_seconds(to_int(config.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS)),
        )
    except Exception:
        return None

    adapted = adapt_upstream_payload(payload, memo=memo)
    adapted["warnings"] = dedupe_warnings(
        [
            *safe_list(adapted.get("warnings")),
            f"Analysis profile `{profile_name}` is active with analysts: {', '.join(normalize_selected_analysts(fallback_config.get('selected_analysts')))}.",
            f"Automatic fallback profile `{profile_name}` activated after primary profile failure: {failure_message}",
        ]
    )
    if clean_text(adapted.get("status")) == "error":
        return None
    if not validate_decision_memo(adapted):
        return None
    apply_latency_measurement(adapted, run_started_at)
    result = {"status": "degraded" if adapted["status"] != "ready" else "ok", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result


def error_result(memo: dict[str, Any], *, mode: str, message: str) -> dict[str, Any]:
    memo["status"] = "error"
    memo["decision"]["rationale"] = clean_text(message) or memo["decision"]["rationale"]
    memo["warnings"] = dedupe_warnings([*safe_list(memo.get("warnings")), clean_text(message)])
    result = {"status": "error" if mode == "required" else "degraded", "decision_memo": memo}
    result["report_markdown"] = build_markdown_report(result)
    return result


def run_tradingagents_decision_bridge(
    raw_request: dict[str, Any],
    *,
    upstream_runner: UpstreamRunner | None = None,
    package_probe: PackageProbe | None = None,
) -> dict[str, Any]:
    request = safe_dict(raw_request)
    config = resolve_request_config(request)
    mode = config["mode"]
    requested_ticker = clean_text(request.get("ticker") or request.get("requested_ticker"))
    analysis_date = normalize_analysis_date(request.get("analysis_date"))
    thesis = safe_dict(request.get("thesis"))
    evidence = safe_list(request.get("evidence"))
    catalysts = safe_list(request.get("catalysts"))
    market_context = safe_dict(request.get("market_context"))

    try:
        normalized_ticker = normalize_ticker(requested_ticker)
        upstream_ticker = ticker_to_tradingagents_format(normalized_ticker)
    except ValueError as exc:
        memo = build_decision_memo_base(
            status="error",
            requested_ticker=requested_ticker,
            normalized_ticker=clean_text(requested_ticker),
            upstream_ticker=clean_text(requested_ticker),
            analysis_date=analysis_date,
            tradingagents_version="unknown",
            evidence_count=len(evidence),
            catalyst_count=len(catalysts),
            thesis_id=clean_text(thesis.get("thesis_id") or thesis.get("id")),
            market_context_available=bool(market_context),
            cost_budget_tokens=config["cost_budget_tokens"],
            timeout_seconds=config["timeout_seconds"],
            warnings=[str(exc)],
        )
        return error_result(memo, mode=mode, message=str(exc))

    if clean_text(config.get("analysis_profile")) == "smart_free":
        resolved_profile = smart_free_profile_name(normalized_ticker)
        if resolved_profile:
            config = build_profile_config(config, resolved_profile)
        else:
            memo = build_decision_memo_base(
                status="error",
                requested_ticker=requested_ticker,
                normalized_ticker=normalized_ticker,
                upstream_ticker=upstream_ticker,
                analysis_date=analysis_date,
                tradingagents_version=config["version_guard"],
                evidence_count=len(evidence),
                catalyst_count=len(catalysts),
                thesis_id=clean_text(thesis.get("thesis_id") or thesis.get("id")),
                market_context_available=bool(market_context),
                cost_budget_tokens=config["cost_budget_tokens"],
                timeout_seconds=config["timeout_seconds"],
                warnings=[
                    "smart_free profile could not resolve a market-specific free profile for this ticker/environment.",
                ],
            )
            return error_result(
                memo,
                mode=mode,
                message="smart_free profile could not resolve a market-specific free profile for this ticker/environment.",
            )

    memo = build_decision_memo_base(
        status="skipped",
        requested_ticker=requested_ticker,
        normalized_ticker=normalized_ticker,
        upstream_ticker=upstream_ticker,
        analysis_date=analysis_date,
        tradingagents_version=config["version_guard"],
        evidence_count=len(evidence),
        catalyst_count=len(catalysts),
        thesis_id=clean_text(thesis.get("thesis_id") or thesis.get("id")),
        market_context_available=bool(market_context),
        cost_budget_tokens=config["cost_budget_tokens"],
        timeout_seconds=config["timeout_seconds"],
        warnings=[],
    )
    if clean_text(config.get("analysis_profile")) not in {"", "full"}:
        memo["warnings"] = dedupe_warnings(
            [
                *safe_list(memo.get("warnings")),
                f"Analysis profile `{clean_text(config.get('analysis_profile'))}` is active with analysts: {', '.join(normalize_selected_analysts(config.get('selected_analysts')))}.",
            ]
        )

    if not config["enabled"]:
        memo["warnings"] = dedupe_warnings([*safe_list(memo.get("warnings")), "TradingAgents bridge is disabled by configuration."])
        result = {"status": "skipped", "decision_memo": memo}
        result["report_markdown"] = build_markdown_report(result)
        return result

    if len(evidence) < config["min_evidence_count"] or len(catalysts) < config["min_catalyst_count"]:
        memo["warnings"] = dedupe_warnings(
            [
                *safe_list(memo.get("warnings")),
                "TradingAgents bridge skipped because the request did not meet the configured evidence or catalyst thresholds.",
            ]
        )
        result = {"status": "skipped", "decision_memo": memo}
        result["report_markdown"] = build_markdown_report(result)
        return result

    fixture = safe_dict(request.get("fixture"))
    run_started_at: float | None = None
    try:
        run_started_at = perf_counter()
        if to_bool(fixture.get("enabled"), False):
            payload = load_fixture_payload(request)
        else:
            if should_prefer_cached_recovery(config):
                recovered_payload = recover_logged_payload(
                    upstream_ticker=upstream_ticker,
                    analysis_date=analysis_date,
                    tradingagents_version=memo["tradingagents_version"],
                )
                if recovered_payload is not None:
                    recovery_info = safe_dict(recovered_payload.get("recovery_info"))
                    recovery_path = clean_text(Path(clean_text(recovery_info.get("path"))).name if clean_text(recovery_info.get("path")) else "")
                    same_day = to_bool(recovery_info.get("same_day"), False)
                    return build_recovered_result(
                        recovered_payload=recovered_payload,
                        memo=memo,
                        run_started_at=run_started_at,
                        extra_warnings=[
                            (
                                "Preemptively reused same-day TradingAgents state log instead of re-running the full profile."
                                if same_day
                                else f"Preemptively reused recent TradingAgents state log `{recovery_path or 'unknown'}` instead of re-running the full profile."
                            ),
                        ],
                    )
            probe = package_probe or default_package_probe
            available, detected_version = probe()
            if not available:
                us_fundamentals_result = try_local_us_fundamentals_snapshot_fallback(
                    config=config,
                    memo=memo,
                    normalized_ticker=normalized_ticker,
                    analysis_date=analysis_date,
                    failure_message="TradingAgents package is not available in the current environment.",
                    run_started_at=run_started_at,
                    mode=mode,
                )
                if us_fundamentals_result is not None:
                    return us_fundamentals_result
                local_market_result = try_local_market_snapshot_fallback(
                    config=config,
                    memo=memo,
                    normalized_ticker=normalized_ticker,
                    analysis_date=analysis_date,
                    failure_message="TradingAgents package is not available in the current environment.",
                    run_started_at=run_started_at,
                    mode=mode,
                )
                if local_market_result is not None:
                    return local_market_result
                apply_latency_measurement(memo, run_started_at)
                return error_result(memo, mode=mode, message="TradingAgents package is not available in the current environment.")
            if clean_text(config["version_guard"]) and not detected_version:
                apply_latency_measurement(memo, run_started_at)
                return error_result(
                    memo,
                    mode=mode,
                    message=(
                        "TradingAgents version could not be determined, so the configured "
                        f"version guard `{config['version_guard']}` cannot be enforced."
                    ),
                )
            if clean_text(config["version_guard"]) and detected_version and not detected_version.startswith(clean_text(config["version_guard"])):
                apply_latency_measurement(memo, run_started_at)
                return error_result(
                    memo,
                    mode=mode,
                    message=f"TradingAgents version guard failed: detected `{detected_version}` but expected `{config['version_guard']}`.",
                )
            memo["tradingagents_version"] = detected_version or memo["tradingagents_version"]
            runner = upstream_runner or default_upstream_runner
            payload = invoke_with_timeout(
                runner,
                {
                    "requested_ticker": requested_ticker,
                    "normalized_ticker": normalized_ticker,
                    "upstream_ticker": upstream_ticker,
                    "analysis_date": analysis_date,
                    "thesis": thesis,
                    "evidence": evidence,
                    "catalysts": catalysts,
                    "market_context": market_context,
                    "bridge_config": config,
                },
                config["timeout_seconds"],
            )
    except FuturesTimeoutError:
        fallback_result = try_profile_fallback(
            runner=runner,
            config=config,
            memo=memo,
            requested_ticker=requested_ticker,
            normalized_ticker=normalized_ticker,
            upstream_ticker=upstream_ticker,
            analysis_date=analysis_date,
            thesis=thesis,
            evidence=evidence,
            catalysts=catalysts,
            market_context=market_context,
            failure_message="TradingAgents propagate() timed out.",
            run_started_at=run_started_at,
        )
        if fallback_result is not None:
            return fallback_result
        us_fundamentals_result = try_local_us_fundamentals_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents propagate() timed out.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if us_fundamentals_result is not None:
            return us_fundamentals_result
        hk_quote_result = try_local_hk_quote_snapshot_fallback(
            memo=deepcopy(memo),
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents propagate() timed out.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if hk_quote_result is not None:
            return hk_quote_result
        local_market_result = try_local_market_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents propagate() timed out.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if local_market_result is not None:
            return local_market_result
        recovered_payload = recover_logged_payload(
            upstream_ticker=upstream_ticker,
            analysis_date=analysis_date,
            tradingagents_version=memo["tradingagents_version"],
        )
        if recovered_payload is not None:
            return build_recovered_result(
                recovered_payload=recovered_payload,
                memo=memo,
                run_started_at=run_started_at,
            )
        apply_latency_measurement(memo, run_started_at)
        return error_result(memo, mode=mode, message="TradingAgents propagate() timed out.")
    except ModuleNotFoundError:
        us_fundamentals_result = try_local_us_fundamentals_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents package import failed during execution.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if us_fundamentals_result is not None:
            return us_fundamentals_result
        hk_quote_result = try_local_hk_quote_snapshot_fallback(
            memo=deepcopy(memo),
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents package import failed during execution.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if hk_quote_result is not None:
            return hk_quote_result
        local_market_result = try_local_market_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="TradingAgents package import failed during execution.",
            run_started_at=run_started_at,
            mode=mode,
        )
        if local_market_result is not None:
            return local_market_result
        apply_latency_measurement(memo, run_started_at)
        return error_result(memo, mode=mode, message="TradingAgents package import failed during execution.")
    except Exception as exc:  # pragma: no cover
        error_message = format_exception_message(exc)
        fallback_result = try_profile_fallback(
            runner=runner,
            config=config,
            memo=memo,
            requested_ticker=requested_ticker,
            normalized_ticker=normalized_ticker,
            upstream_ticker=upstream_ticker,
            analysis_date=analysis_date,
            thesis=thesis,
            evidence=evidence,
            catalysts=catalysts,
            market_context=market_context,
            failure_message=error_message,
            run_started_at=run_started_at,
        )
        if fallback_result is not None:
            return fallback_result
        us_fundamentals_result = try_local_us_fundamentals_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=error_message,
            run_started_at=run_started_at,
            mode=mode,
        )
        if us_fundamentals_result is not None:
            return us_fundamentals_result
        hk_quote_result = try_local_hk_quote_snapshot_fallback(
            memo=deepcopy(memo),
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=error_message,
            run_started_at=run_started_at,
            mode=mode,
        )
        if hk_quote_result is not None:
            return hk_quote_result
        local_market_result = try_local_market_snapshot_fallback(
            config=config,
            memo=memo,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message=error_message,
            run_started_at=run_started_at,
            mode=mode,
        )
        if local_market_result is not None:
            return local_market_result
        recovered_payload = recover_logged_payload(
            upstream_ticker=upstream_ticker,
            analysis_date=analysis_date,
            tradingagents_version=memo["tradingagents_version"],
        )
        if recovered_payload is not None:
            return build_recovered_result(
                recovered_payload=recovered_payload,
                memo=memo,
                run_started_at=run_started_at,
                extra_warnings=[
                    error_message,
                ],
            )
        apply_latency_measurement(memo, run_started_at)
        return error_result(memo, mode=mode, message=error_message)

    adapted = adapt_upstream_payload(payload, memo=deepcopy(memo))
    apply_latency_measurement(adapted, run_started_at)
    if not validate_decision_memo(adapted):
        errors = "; ".join(contract_errors(adapted))
        if not to_bool(fixture.get("enabled"), False):
            recovered_payload = recover_logged_payload(
                upstream_ticker=upstream_ticker,
                analysis_date=analysis_date,
                tradingagents_version=adapted.get("tradingagents_version") or memo["tradingagents_version"],
            )
            if recovered_payload is not None:
                return build_recovered_result(
                    recovered_payload=recovered_payload,
                    memo=deepcopy(memo),
                    run_started_at=run_started_at,
                    extra_warnings=[
                        f"Primary provider-backed output failed decision_memo contract validation: {errors}",
                    ],
                )
            us_fundamentals_result = try_local_us_fundamentals_snapshot_fallback(
                config=config,
                memo=deepcopy(memo),
                normalized_ticker=normalized_ticker,
                analysis_date=analysis_date,
                failure_message=f"decision_memo contract validation failed: {errors}",
                run_started_at=run_started_at,
                mode=mode,
            )
            if us_fundamentals_result is not None:
                return us_fundamentals_result
            hk_quote_result = try_local_hk_quote_snapshot_fallback(
                memo=deepcopy(memo),
                normalized_ticker=normalized_ticker,
                analysis_date=analysis_date,
                failure_message=f"decision_memo contract validation failed: {errors}",
                run_started_at=run_started_at,
                mode=mode,
            )
            if hk_quote_result is not None:
                return hk_quote_result
            local_market_result = try_local_market_snapshot_fallback(
                config=config,
                memo=deepcopy(memo),
                normalized_ticker=normalized_ticker,
                analysis_date=analysis_date,
                failure_message=f"decision_memo contract validation failed: {errors}",
                run_started_at=run_started_at,
                mode=mode,
            )
            if local_market_result is not None:
                return local_market_result
        return error_result(memo=adapted, mode=mode, message=f"decision_memo contract validation failed: {errors}")

    result = {"status": "ok" if adapted["status"] == "ready" else "degraded", "decision_memo": adapted}
    result["report_markdown"] = build_markdown_report(result)
    return result
