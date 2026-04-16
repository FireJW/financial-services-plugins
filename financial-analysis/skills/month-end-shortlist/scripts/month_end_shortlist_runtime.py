#!/usr/bin/env python3
from __future__ import annotations

from importlib.machinery import SourcelessFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
from pathlib import Path
import sys
from typing import Any, Callable
from copy import deepcopy


PYC_PATH = (
    Path(__file__).resolve().parents[2]
    / "short-horizon-shortlist"
    / "scripts"
    / "__pycache__"
    / "month_end_shortlist_runtime.cpython-312.pyc"
)
TRADINGAGENTS_SCRIPT_DIR = (
    Path(__file__).resolve().parents[2]
    / "tradingagents-decision-bridge"
    / "scripts"
)


if str(TRADINGAGENTS_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(TRADINGAGENTS_SCRIPT_DIR))


BENCHMARK_TICKERS = {"000300.SS", "000300.SH"}


def load_compiled_module():
    if not PYC_PATH.exists():
        raise ModuleNotFoundError(f"Compiled month_end_shortlist_runtime artifact is missing: {PYC_PATH}")
    loader = SourcelessFileLoader(__name__ + "._compiled", str(PYC_PATH))
    spec = spec_from_loader(__name__ + "._compiled", loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create an import spec for {PYC_PATH}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_compiled = load_compiled_module()
__doc__ = getattr(_compiled, "__doc__", None)

for _name in dir(_compiled):
    if _name.startswith("__") and _name not in {"__all__"}:
        continue
    globals()[_name] = getattr(_compiled, _name)


BarsFetcher = Callable[[str, str, str], list[dict[str, Any]]]
AssessCandidate = Callable[..., dict[str, Any]]
NEAR_MISS_MAX_GAP = 15.0
MAX_REPORTED_TOP_PICKS = 10
MAX_REPORTED_NEAR_MISS = 5
MAX_REPORTED_BLOCKED = 5
MAX_REPORTED_WATCH_ITEMS = 3
WRAPPER_FILTER_PROFILE_OVERRIDES: dict[str, dict[str, float]] = {
    # Recovered from a validated historical artifact until the compiled runtime
    # regains native support for this documented profile.
    "month_end_event_support_transition": {
        "keep_threshold": 58.0,
        "strict_top_pick_threshold": 59.0,
    }
}


def wrap_bars_fetcher_with_benchmark_fallback(base_fetcher: BarsFetcher) -> BarsFetcher:
    def wrapped(ticker: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        try:
            return base_fetcher(ticker, start_date, end_date)
        except Exception:
            if str(ticker or "").strip().upper() in BENCHMARK_TICKERS:
                return []
            raise

    return wrapped


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    return json.loads(resolved.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Any) -> None:
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def extract_x_style_overlays_from_result(batch_payload: dict[str, Any], selected_handles: list[str] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    desired = unique_strings([clean_text(item).lstrip("@") for item in (selected_handles or [])])
    handles: list[str] = []
    overlays: list[dict[str, Any]] = []
    for item in batch_payload.get("subject_runs", []):
        if not isinstance(item, dict):
            continue
        subject = item.get("subject", {})
        overlay_pack = item.get("overlay_pack", {})
        if not isinstance(subject, dict) or not isinstance(overlay_pack, dict):
            continue
        handle = clean_text(subject.get("handle")).lstrip("@")
        if not handle:
            continue
        if desired and handle not in desired:
            continue
        if handle in handles:
            continue
        handles.append(handle)
        overlays.append(deepcopy(overlay_pack))
    return handles, overlays


def apply_wrapper_filter_profile_override(raw_payload: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    requested_profile = clean_text(raw_payload.get("filter_profile"))
    if not requested_profile:
        return normalized
    override = WRAPPER_FILTER_PROFILE_OVERRIDES.get(requested_profile)
    if not override:
        return normalized

    normalized["filter_profile"] = requested_profile
    profile_settings = dict(normalized.get("profile_settings") or {})
    for key, value in override.items():
        normalized[key] = value
        profile_settings[key] = value
    normalized["profile_settings"] = profile_settings
    return normalized


def normalize_request_with_compiled(raw_payload: dict[str, Any], compiled_normalize_request: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    normalized = apply_wrapper_filter_profile_override(
        raw_payload,
        compiled_normalize_request(raw_payload),
    )
    batch_path = clean_text(normalized.get("x_style_batch_result_path"))
    if not batch_path:
        return normalized
    path = Path(batch_path).expanduser().resolve()
    if not path.exists():
        return normalized
    try:
        batch_payload = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return normalized
    handles, overlays = extract_x_style_overlays_from_result(
        batch_payload,
        selected_handles=normalized.get("x_style_selected_handles", []),
    )
    if handles:
        normalized["x_style_selected_handles"] = handles
    if overlays:
        normalized["x_style_overlays"] = overlays
    return normalized


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_request_with_compiled(raw_payload, _compiled.normalize_request)


def build_bars_fetch_failed_candidate(candidate: dict[str, Any], error: Exception | str) -> dict[str, Any]:
    ticker = str(candidate.get("ticker", "")).strip()
    name = str(candidate.get("name", "")).strip()
    return {
        "ticker": ticker,
        "name": name,
        "code": str(candidate.get("code", "")).strip(),
        "sector": str(candidate.get("sector", "")).strip(),
        "board": str(candidate.get("board", "")).strip(),
        "price": candidate.get("price"),
        "open": candidate.get("open"),
        "high": candidate.get("high"),
        "low": candidate.get("low"),
        "pre_close": candidate.get("pre_close"),
        "day_pct": candidate.get("day_pct"),
        "pct_from_60d": candidate.get("pct_from_60d"),
        "pct_from_ytd": candidate.get("pct_from_ytd"),
        "pe_ttm": candidate.get("pe_ttm"),
        "pb": candidate.get("pb"),
        "free_float_market_cap": candidate.get("free_float_market_cap"),
        "total_market_cap": candidate.get("total_market_cap"),
        "turnover_rate_pct": candidate.get("turnover_rate_pct"),
        "day_turnover_cny": candidate.get("day_turnover_cny"),
        "day_volume_shares": candidate.get("day_volume_shares"),
        "keep": False,
        "top_pick_eligible": False,
        "hard_filter_failures": ["bars_fetch_failed"],
        "scores": {},
        "score_components": {
            "trend_template_score": 0.0,
            "rs_and_leadership_score": 0.0,
            "fundamental_acceleration_score": 0.0,
            "structured_catalyst_score": 0.0,
            "vcp_or_contraction_score": 0.0,
            "liquidity_and_participation_score": 0.0,
            "cap_multiplier": 1.0,
            "raw_total_score": 0.0,
            "adjusted_total_score": 0.0,
        },
        "price_snapshot": {},
        "trend_template": {},
        "structured_catalyst_snapshot": {},
        "fundamental_snapshot": {},
        "vcp_snapshot": {},
        "cap_snapshot": {},
        "price_paths": {},
        "backtest_summary": {},
        "trade_card": {},
        "bars_fetch_error": str(error or "").strip(),
    }


def enrich_degraded_live_result(result: dict[str, Any], failure_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not failure_candidates:
        return result

    enriched = deepcopy(result)
    filter_summary = dict(enriched.get("filter_summary") or {})
    tickers = unique_strings([item.get("ticker") for item in failure_candidates])
    filter_summary["blocked_candidate_count"] = len(tickers)
    filter_summary["bars_fetch_failed_tickers"] = tickers
    enriched["filter_summary"] = filter_summary
    enriched["blocked_candidates"] = deepcopy(failure_candidates)

    failure_by_ticker = {clean_text(item.get("ticker")): item for item in failure_candidates if clean_text(item.get("ticker"))}
    dropped = []
    for item in enriched.get("dropped", []):
        if not isinstance(item, dict):
            dropped.append(item)
            continue
        failure = failure_by_ticker.get(clean_text(item.get("ticker")))
        if not failure:
            dropped.append(item)
            continue
        merged = dict(item)
        for key in ("sector", "board", "price", "bars_fetch_error"):
            value = failure.get(key)
            if value not in (None, "", []):
                merged[key] = value
        dropped.append(merged)
    enriched["dropped"] = dropped

    report_markdown = str(enriched.get("report_markdown") or "").rstrip()
    lines = [report_markdown] if report_markdown else []
    lines.extend(["", "## Blocked Candidates", ""])
    for item in failure_candidates:
        ticker = clean_text(item.get("ticker")) or "unknown"
        name = clean_text(item.get("name")) or ticker
        reason = clean_text(item.get("bars_fetch_error")) or "bars_fetch_failed"
        lines.append(f"- `{ticker}` {name}: `{reason}`")
    enriched["report_markdown"] = "\n".join(lines).strip() + "\n"
    return enriched


def split_drop_reasons(value: Any) -> list[str]:
    reasons: list[str] = []
    for chunk in str(value or "").split(","):
        text = clean_text(chunk)
        if text:
            reasons.append(text)
    return reasons


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_candidate_snapshot_from_rows(ticker: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = dict(rows[-1]) if rows else {}
    latest_close = to_float(latest.get("close"))
    first_close = to_float(rows[0].get("close")) if rows else 0.0
    trailing_60 = rows[-60] if len(rows) >= 60 else (rows[0] if rows else {})
    ref_60 = to_float(trailing_60.get("close"))

    pct_from_60d = ((latest_close - ref_60) / ref_60 * 100.0) if ref_60 else 0.0
    pct_from_ytd = ((latest_close - first_close) / first_close * 100.0) if first_close else 0.0
    return {
        "ticker": ticker,
        "name": ticker,
        "price": latest_close,
        "open": to_float(latest.get("open")),
        "high": to_float(latest.get("high")),
        "low": to_float(latest.get("low")),
        "pre_close": to_float(latest.get("pre_close")),
        "day_pct": to_float(latest.get("pct_chg")),
        "day_turnover_cny": to_float(latest.get("amount")),
        "day_volume_shares": to_float(latest.get("vol")),
        "pct_from_60d": round(pct_from_60d, 2),
        "pct_from_ytd": round(pct_from_ytd, 2),
    }


def build_diagnostic_scorecard_entry(candidate: dict[str, Any], keep_threshold: float | int | None = None) -> dict[str, Any]:
    entry = deepcopy(candidate)
    scores = entry.get("scores") if isinstance(entry.get("scores"), dict) else {}
    score_components = entry.get("score_components") if isinstance(entry.get("score_components"), dict) else {}
    score = scores.get("adjusted_total_score")
    if score in (None, ""):
        score = score_components.get("adjusted_total_score")
    if score not in (None, ""):
        entry["score"] = float(score)
    if keep_threshold not in (None, "") and score not in (None, ""):
        entry["keep_threshold_gap"] = round(float(score) - float(keep_threshold), 2)
    entry["diagnostic_components"] = {
        "trend": score_components.get("trend_template_score"),
        "rs": score_components.get("rs_and_leadership_score"),
        "catalyst": score_components.get("structured_catalyst_score"),
        "liquidity": score_components.get("liquidity_and_participation_score"),
    }
    return entry


def build_near_miss_candidates(
    diagnostic_scorecard: list[dict[str, Any]],
    *,
    max_gap: float = NEAR_MISS_MAX_GAP,
) -> list[dict[str, Any]]:
    near_miss: list[dict[str, Any]] = []
    for item in diagnostic_scorecard:
        if not isinstance(item, dict):
            continue
        if item.get("keep"):
            continue
        if item.get("hard_filter_failures"):
            continue
        score = item.get("score")
        gap = item.get("keep_threshold_gap")
        if score in (None, "") or gap in (None, ""):
            continue
        try:
            gap_value = float(gap)
        except (TypeError, ValueError):
            continue
        if gap_value >= 0 or abs(gap_value) > float(max_gap):
            continue
        near_miss.append(deepcopy(item))
    return near_miss


def classify_midday_status(candidate: dict[str, Any], near_miss_tickers: set[str] | None = None) -> str:
    ticker = clean_text(candidate.get("ticker"))
    failures = candidate.get("hard_filter_failures")
    if isinstance(failures, list) and failures:
        return "blocked"
    if ticker and ticker in (near_miss_tickers or set()):
        return "near_miss"
    if candidate.get("keep"):
        return "qualified"
    return "watch"


def midday_action_for_status(status: str) -> str:
    normalized = clean_text(status).lower()
    if normalized == "blocked":
        return "不执行"
    if normalized == "qualified":
        return "可执行"
    return "继续观察"


def build_midday_action_summary(diagnostic_scorecard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in diagnostic_scorecard:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "ticker": clean_text(item.get("ticker")),
                "name": clean_text(item.get("name")) or clean_text(item.get("ticker")),
                "status": clean_text(item.get("midday_status")),
                "action": midday_action_for_status(clean_text(item.get("midday_status"))),
                "score": item.get("score"),
                "keep_threshold_gap": item.get("keep_threshold_gap"),
            }
        )
    return summary


def build_midday_action_summary_from_top_picks(top_picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in top_picks[:MAX_REPORTED_TOP_PICKS]:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "ticker": clean_text(item.get("ticker")),
                "name": clean_text(item.get("name")) or clean_text(item.get("ticker")),
                "status": "qualified",
                "action": "可执行",
                "score": item.get("score"),
                "keep_threshold_gap": None,
            }
        )
    return summary


def build_midday_action_summary_from_result(enriched: dict[str, Any]) -> list[dict[str, Any]]:
    top_picks = enriched.get("top_picks")
    if isinstance(top_picks, list) and top_picks:
        return build_midday_action_summary_from_top_picks(top_picks)
    diagnostic_scorecard = enriched.get("diagnostic_scorecard")
    if isinstance(diagnostic_scorecard, list) and diagnostic_scorecard:
        return build_midday_action_summary(diagnostic_scorecard)
    return []


def build_technical_factor_summary(candidate: dict[str, Any]) -> str:
    snapshot = candidate.get("price_snapshot") if isinstance(candidate.get("price_snapshot"), dict) else {}
    trend = candidate.get("trend_template") if isinstance(candidate.get("trend_template"), dict) else {}
    if snapshot:
        close = snapshot.get("close")
        ma20 = snapshot.get("ma20")
        ma50 = snapshot.get("ma50")
        ma150 = snapshot.get("ma150")
        ma200 = snapshot.get("ma200")
        rsi14 = snapshot.get("rsi14")
        rs90 = snapshot.get("rs90")
        structure = "均线结构偏弱"
        if all(value not in (None, "") for value in (close, ma20, ma50, ma150, ma200)):
            if close > ma20 > ma50 > ma150 > ma200:
                structure = "均线多头结构仍成立"
            elif close > ma20 and close > ma50:
                structure = "短中期均线仍偏强，但长周期确认一般"
        trend_state = "趋势未确认"
        if trend.get("trend_pass") is True:
            trend_state = f"趋势模板通过（{trend.get('passed_count', 0)}项）"
        rsi_text = f"RSI 处在 {rsi14} 附近，未见极端失真" if rsi14 not in (None, "") else "RSI 证据不足"
        rs_text = f"相对强度 RS90 仍有支撑（{rs90}）" if rs90 not in (None, "") else "相对强度证据不足"
        return f"{structure}，{trend_state}；{rsi_text}；{rs_text}。"
    return "技术形态证据不足，当前无法完整复核均线、动能与波动结构。"


def build_event_factor_summary(candidate: dict[str, Any]) -> str:
    structured = candidate.get("structured_catalyst_snapshot") if isinstance(candidate.get("structured_catalyst_snapshot"), dict) else {}
    events = structured.get("earnings_events") if isinstance(structured.get("earnings_events"), list) else []
    if events:
        first = events[0]
        return f"关键事件窗口内有催化，最近一项是 {clean_text(first.get('date'))} 的 {clean_text(first.get('event_type'))}。"
    scheduled = clean_text(candidate.get("scheduled_earnings_date"))
    if scheduled:
        return f"已知关键事件日期为 {scheduled}，需要围绕事件前后确认结构是否延续。"
    if structured.get("structured_catalyst_within_window") is False:
        return "当前没有落在窗口内的关键结构化事件，事件驱动支持偏弱。"
    return "关键事件证据不足。"


def build_likely_next_summary(candidate: dict[str, Any], action: str) -> str:
    if action == "可执行":
        return "如果量能和趋势继续共振，后续更可能走确认后延续，而不是简单冲高回落。"
    if action == "继续观察":
        return "更可能先进入确认/回踩二选一阶段，关键看趋势和事件是否能把分数推回执行区间。"
    failures = candidate.get("hard_filter_failures") if isinstance(candidate.get("hard_filter_failures"), list) else []
    if failures:
        return "在当前硬伤修复前，更可能继续维持观察或剔除状态。"
    return "后续方向仍不清晰，优先等待更多证据。"


def build_logic_factor_summary(candidate: dict[str, Any], action: str) -> str:
    failures = candidate.get("hard_filter_failures") if isinstance(candidate.get("hard_filter_failures"), list) else []
    score = candidate.get("score")
    gap = candidate.get("keep_threshold_gap")
    if action == "可执行":
        return f"当前结构、事件与分数共同支持执行，综合评分 {score} 已进入可执行区间。"
    if action == "继续观察":
        return f"当前没有硬伤，但综合评分 {score} 距 keep line 仍差 {gap}，更适合继续观察等待确认。"
    if failures:
        return f"当前不执行，核心原因是 {', '.join(failures)}。"
    return "当前不执行，复核证据不足以支持出手。"


def build_trade_layer_summary(candidate: dict[str, Any], action: str) -> str:
    trade_card = candidate.get("trade_card") if isinstance(candidate.get("trade_card"), dict) else {}
    price_paths = candidate.get("price_paths") if isinstance(candidate.get("price_paths"), dict) else {}
    risk_reward_ratio = candidate.get("risk_reward_ratio")
    base_upside_pct = candidate.get("base_upside_pct")
    risk_pct = candidate.get("risk_pct")

    parts: list[str] = []
    if action in {"可执行", "继续观察"}:
        if clean_text(trade_card.get("watch_action")):
            parts.append(f"观察/执行参考：{clean_text(trade_card.get('watch_action'))}")
        if clean_text(trade_card.get("invalidation")):
            parts.append(f"失效条件：{clean_text(trade_card.get('invalidation'))}")
        if isinstance(price_paths.get("base"), list) and price_paths.get("base"):
            parts.append(f"基准路径：{price_paths.get('base')}")
        if risk_reward_ratio not in (None, ""):
            parts.append(f"风险收益比 `{risk_reward_ratio}`")
        if base_upside_pct not in (None, ""):
            parts.append(f"基础上行空间 `{base_upside_pct}%`")
        if risk_pct not in (None, ""):
            parts.append(f"预估风险 `{risk_pct}%`")
    if not parts and action == "不执行":
        return "当前不进入交易层细化，先解决结构或事件上的硬伤再谈执行。"
    return "；".join(parts) if parts else "交易层证据不足。"


def build_next_watch_items(candidate: dict[str, Any], action: str) -> list[str]:
    items: list[str] = []
    trade_card = candidate.get("trade_card") if isinstance(candidate.get("trade_card"), dict) else {}
    if action == "继续观察":
        if clean_text(trade_card.get("watch_action")):
            items.append(clean_text(trade_card.get("watch_action")))
        if clean_text(trade_card.get("invalidation")):
            items.append(f"若出现 `{clean_text(trade_card.get('invalidation'))}` 则观察逻辑失效。")
        if not items:
            items.append("等待下一次趋势确认或分数修复后再评估。")
    elif action == "可执行":
        if clean_text(trade_card.get("watch_action")):
            items.append(clean_text(trade_card.get("watch_action")))
        if clean_text(trade_card.get("invalidation")):
            items.append(f"执行后重点盯住失效条件：`{clean_text(trade_card.get('invalidation'))}`。")
    else:
        items.append("除非结构和价格条件明显改善，否则不进入执行清单。")
    return items[:MAX_REPORTED_WATCH_ITEMS]


def build_decision_factor_entry(candidate: dict[str, Any], action: str) -> dict[str, Any]:
    status = clean_text(candidate.get("midday_status"))
    if not status:
        if action == "可执行":
            status = "qualified"
        elif action == "继续观察":
            status = "near_miss"
        else:
            status = "blocked"
    return {
        "ticker": clean_text(candidate.get("ticker")),
        "name": clean_text(candidate.get("name")) or clean_text(candidate.get("ticker")),
        "action": action,
        "status": status,
        "score": candidate.get("score"),
        "keep_threshold_gap": candidate.get("keep_threshold_gap"),
        "technical_summary": build_technical_factor_summary(candidate),
        "event_summary": build_event_factor_summary(candidate),
        "likely_next_summary": build_likely_next_summary(candidate, action),
        "logic_summary": build_logic_factor_summary(candidate, action),
        "trade_layer_summary": build_trade_layer_summary(candidate, action),
        "next_watch_items": build_next_watch_items(candidate, action),
    }


def build_decision_factors_from_result(enriched: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    factors = {"qualified": [], "near_miss": [], "blocked": []}
    for item in enriched.get("top_picks", []) if isinstance(enriched.get("top_picks"), list) else []:
        if isinstance(item, dict):
            factors["qualified"].append(build_decision_factor_entry(item, "可执行"))
    for item in enriched.get("near_miss_candidates", []) if isinstance(enriched.get("near_miss_candidates"), list) else []:
        if isinstance(item, dict):
            factors["near_miss"].append(build_decision_factor_entry(item, "继续观察"))
    for item in enriched.get("diagnostic_scorecard", []) if isinstance(enriched.get("diagnostic_scorecard"), list) else []:
        if not isinstance(item, dict):
            continue
        if clean_text(item.get("midday_status")) == "blocked":
            factors["blocked"].append(build_decision_factor_entry(item, "不执行"))
    factors["qualified"] = factors["qualified"][:MAX_REPORTED_TOP_PICKS]
    factors["near_miss"] = factors["near_miss"][:MAX_REPORTED_NEAR_MISS]
    factors["blocked"] = factors["blocked"][:MAX_REPORTED_BLOCKED]
    return factors


def prepare_request_with_candidate_snapshots(request: dict[str, Any], *, bars_fetcher: BarsFetcher) -> dict[str, Any]:
    prepared = deepcopy(request)
    candidate_tickers = [clean_text(item) for item in prepared.get("candidate_tickers", []) if clean_text(item)]
    if not candidate_tickers or prepared.get("universe_candidates"):
        return prepared

    history_by_ticker = dict(prepared.get("history_by_ticker") or {})
    analysis_date = parse_date(prepared.get("analysis_time")) or parse_date(prepared.get("target_date")) or now_utc().date()
    start_date = (analysis_date - timedelta(days=420)).isoformat()
    end_date = analysis_date.isoformat()

    universe_candidates: list[dict[str, Any]] = []
    for raw_ticker in candidate_tickers:
        normalized_ticker = build_manual_candidate({"ticker": raw_ticker, "name": raw_ticker}).get("ticker") or clean_text(raw_ticker).upper()
        rows = history_by_ticker.get(normalized_ticker)
        if not rows:
            try:
                rows = bars_fetcher(normalized_ticker, start_date, end_date)
            except Exception:
                rows = []
        if rows:
            history_by_ticker[normalized_ticker] = rows
            universe_candidates.append(build_candidate_snapshot_from_rows(normalized_ticker, rows))
        else:
            universe_candidates.append({"ticker": normalized_ticker, "name": normalized_ticker})

    prepared["history_by_ticker"] = history_by_ticker
    prepared["universe_candidates"] = universe_candidates
    return prepared

def enrich_live_result_reporting(
    result: dict[str, Any],
    failure_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    enriched = enrich_degraded_live_result(result, failure_candidates)
    dropped = [item for item in enriched.get("dropped", []) if isinstance(item, dict)]

    filter_summary = dict(enriched.get("filter_summary") or {})
    if dropped:
        drop_reason_counts: dict[str, int] = {}
        for item in dropped:
            for reason in split_drop_reasons(item.get("drop_reason")):
                drop_reason_counts[reason] = drop_reason_counts.get(reason, 0) + 1
        if drop_reason_counts:
            filter_summary["drop_reason_counts"] = drop_reason_counts
            enriched["filter_summary"] = filter_summary

    diagnostic_scorecard = [
        build_diagnostic_scorecard_entry(item, filter_summary.get("keep_threshold"))
        for item in (assessed_candidates or [])
        if isinstance(item, dict)
    ]
    if diagnostic_scorecard:
        near_miss_candidates = build_near_miss_candidates(diagnostic_scorecard)
        near_miss_tickers = {clean_text(item.get("ticker")) for item in near_miss_candidates}
        for item in diagnostic_scorecard:
            item["midday_status"] = classify_midday_status(item, near_miss_tickers)
        filter_summary["diagnostic_scorecard_count"] = len(diagnostic_scorecard)
        enriched["filter_summary"] = filter_summary
        enriched["diagnostic_scorecard"] = diagnostic_scorecard
        enriched["midday_action_summary"] = build_midday_action_summary(diagnostic_scorecard)
        if near_miss_candidates:
            for item in near_miss_candidates:
                item["midday_status"] = classify_midday_status(item, near_miss_tickers)
            filter_summary["near_miss_candidate_count"] = len(near_miss_candidates)
            enriched["filter_summary"] = filter_summary
            enriched["near_miss_candidates"] = near_miss_candidates

    midday_action_summary = build_midday_action_summary_from_result(enriched)
    if midday_action_summary:
        enriched["midday_action_summary"] = midday_action_summary
    decision_factors = build_decision_factors_from_result(enriched)
    if any(decision_factors.values()):
        enriched["decision_factors"] = decision_factors

    report_markdown = str(enriched.get("report_markdown") or "").rstrip()
    if "## Dropped Candidates" in report_markdown:
        lines = [report_markdown]
    else:
        lines = [report_markdown] if report_markdown else []
        if dropped:
            lines.extend(["", "## Dropped Candidates", ""])
            for item in dropped:
                ticker = clean_text(item.get("ticker")) or "unknown"
                name = clean_text(item.get("name")) or ticker
                reason = clean_text(item.get("drop_reason")) or "dropped"
                lines.append(f"- `{ticker}` {name}: `{reason}`")
    if diagnostic_scorecard and "## Diagnostic Scorecard" not in "\n".join(lines):
        lines.extend(["", "## Diagnostic Scorecard", ""])
        for item in diagnostic_scorecard:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            failures = ",".join(item.get("hard_filter_failures", [])) if isinstance(item.get("hard_filter_failures"), list) else clean_text(item.get("hard_filter_failures"))
            components = item.get("diagnostic_components") if isinstance(item.get("diagnostic_components"), dict) else {}
            component_summary = " / ".join(
                f"{label}=`{components[label]}`"
                for label in ("trend", "rs", "catalyst", "liquidity")
                if components.get(label) not in (None, "")
            )
            lines.append(
                f"- `{ticker}` {name}: status=`{item.get('midday_status')}` score=`{score}` gap=`{gap}`"
                + (f" {component_summary}" if component_summary else "")
                + f" failures=`{failures or 'none'}`"
            )
    near_miss_candidates = enriched.get("near_miss_candidates", [])
    if isinstance(near_miss_candidates, list) and near_miss_candidates and "## Near Miss Candidates" not in "\n".join(lines):
        lines.extend(["", "## Near Miss Candidates", ""])
        for item in near_miss_candidates:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            lines.append(f"- `{ticker}` {name}: status=`{item.get('midday_status')}` score=`{score}` gap=`{gap}`")
    midday_action_summary = enriched.get("midday_action_summary", [])
    if isinstance(midday_action_summary, list) and midday_action_summary and "## 午盘操作建议摘要" not in "\n".join(lines):
        lines.extend(["", "## 午盘操作建议摘要", ""])
        for item in midday_action_summary:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            action = clean_text(item.get("action")) or "继续观察"
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            lines.append(f"- `{ticker}` {name}: `{action}` score=`{score}` gap=`{gap}`")
    if any(decision_factors.values()) and "## Decision Factors" not in "\n".join(lines):
        lines.extend(["", "## Decision Factors", ""])
        section_map = [("qualified", "可执行"), ("near_miss", "继续观察"), ("blocked", "不执行")]
        for key, title in section_map:
            rows = decision_factors.get(key, [])
            if not rows:
                continue
            lines.extend(["", f"### {title}", ""])
            for item in rows:
                ticker = clean_text(item.get("ticker")) or "unknown"
                name = clean_text(item.get("name")) or ticker
                lines.append(f"- `{ticker}` {name}")
                lines.append(f"  - 动作: `{item.get('action')}`")
                if item.get("score") not in (None, ""):
                    lines.append(f"  - 分数: `{item.get('score')}`")
                if item.get("keep_threshold_gap") not in (None, ""):
                    lines.append(f"  - 与 keep line 差距: `{item.get('keep_threshold_gap')}`")
                lines.append(f"  - 技术形态: {item.get('technical_summary')}")
                lines.append(f"  - 关键事件: {item.get('event_summary')}")
                lines.append(f"  - 下一步推演: {item.get('likely_next_summary')}")
                lines.append(f"  - 判断逻辑: {item.get('logic_summary')}")
                lines.append(f"  - 交易层: {item.get('trade_layer_summary')}")
                next_watch = item.get("next_watch_items") if isinstance(item.get("next_watch_items"), list) else []
                for note in next_watch[:MAX_REPORTED_WATCH_ITEMS]:
                    lines.append(f"  - 观察点: {note}")
    enriched["report_markdown"] = "\n".join(lines).strip() + "\n"
    return enriched


def wrap_assess_candidate_with_bars_failure_fallback(
    base_assess_candidate: AssessCandidate,
    failure_log: list[dict[str, Any]] | None = None,
    assessed_log: list[dict[str, Any]] | None = None,
) -> AssessCandidate:
    def wrapped(
        candidate: dict[str, Any],
        request: dict[str, Any],
        benchmark_rows: list[dict[str, Any]],
        *,
        bars_fetcher: Any,
        html_fetcher: Any,
    ) -> dict[str, Any]:
        try:
            assessed = base_assess_candidate(
                candidate,
                request,
                benchmark_rows,
                bars_fetcher=bars_fetcher,
                html_fetcher=html_fetcher,
            )
            if assessed_log is not None:
                assessed_log.append(deepcopy(assessed))
            return assessed
        except Exception as exc:
            if "bars_fetch_failed" in str(exc):
                failed = build_bars_fetch_failed_candidate(candidate, exc)
                if failure_log is not None:
                    failure_log.append(deepcopy(failed))
                if assessed_log is not None:
                    assessed_log.append(deepcopy(failed))
                return failed
            raise

    return wrapped


default_bars_fetcher = wrap_bars_fetcher_with_benchmark_fallback(_compiled.default_bars_fetcher)


def run_month_end_shortlist(
    raw_payload: dict[str, Any],
    *,
    universe_fetcher: Any = _compiled.default_universe_fetcher,
    bars_fetcher: Any = default_bars_fetcher,
    html_fetcher: Any = _compiled.fetch_html,
) -> dict[str, Any]:
    failure_log: list[dict[str, Any]] = []
    assessed_log: list[dict[str, Any]] = []
    original_assess_candidate = _compiled.assess_candidate
    original_normalize_request = _compiled.normalize_request
    _compiled.assess_candidate = wrap_assess_candidate_with_bars_failure_fallback(
        original_assess_candidate,
        failure_log,
        assessed_log,
    )
    _compiled.normalize_request = lambda payload: normalize_request_with_compiled(payload, original_normalize_request)
    try:
        prepared_payload = prepare_request_with_candidate_snapshots(
            normalize_request_with_compiled(raw_payload, original_normalize_request),
            bars_fetcher=wrap_bars_fetcher_with_benchmark_fallback(bars_fetcher),
        )
        result = _compiled.run_month_end_shortlist(
            prepared_payload,
            universe_fetcher=universe_fetcher,
            bars_fetcher=wrap_bars_fetcher_with_benchmark_fallback(bars_fetcher),
            html_fetcher=html_fetcher,
        )
        return enrich_live_result_reporting(result, failure_log, assessed_log)
    finally:
        _compiled.assess_candidate = original_assess_candidate
        _compiled.normalize_request = original_normalize_request

if "__all__" not in globals():
    __all__ = [name for name in dir(_compiled) if not name.startswith("_")]

for _extra in (
    "BENCHMARK_TICKERS",
    "load_json",
    "write_json",
    "wrap_bars_fetcher_with_benchmark_fallback",
    "build_bars_fetch_failed_candidate",
    "enrich_degraded_live_result",
    "enrich_live_result_reporting",
    "build_diagnostic_scorecard_entry",
    "build_near_miss_candidates",
    "classify_midday_status",
    "build_midday_action_summary",
    "build_midday_action_summary_from_top_picks",
    "build_midday_action_summary_from_result",
    "build_decision_factor_entry",
    "build_decision_factors_from_result",
    "midday_action_for_status",
    "prepare_request_with_candidate_snapshots",
    "wrap_assess_candidate_with_bars_failure_fallback",
):
    if _extra not in __all__:
        __all__.append(_extra)
