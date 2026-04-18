#!/usr/bin/env python3
from __future__ import annotations

from importlib.machinery import SourcelessFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable
from copy import deepcopy
from earnings_momentum_discovery import (
    TRADING_PROFILE_BUCKETS,
    assign_discovery_bucket,
    build_auto_discovery_candidates,
    build_chain_path_summary,
    build_event_cards,
    build_trading_profile_judgment,
    build_trading_profile_playbook,
    build_trading_profile_usage,
    build_x_style_discovery_candidates,
    classify_trading_profile,
    classify_event_state,
    classify_market_validation,
    classify_trading_usability,
    compute_rumor_confidence_range,
    normalize_event_candidate,
)


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
X_STYLE_SCRIPT_DIR = (
    Path(__file__).resolve().parents[2]
    / "x-stock-picker-style"
    / "scripts"
)


for _script_dir in (TRADINGAGENTS_SCRIPT_DIR, X_STYLE_SCRIPT_DIR):
    if str(_script_dir) not in sys.path:
        sys.path.insert(0, str(_script_dir))


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
NEAR_MISS_MAX_GAP = 20.0
MAX_REPORTED_TOP_PICKS = 10
MAX_REPORTED_NEAR_MISS = 5
MAX_REPORTED_BLOCKED = 5
MAX_REPORTED_WATCH_ITEMS = 3

# --- Screening Coverage Optimization constants ---
NEAR_MISS_FLOOR_GAP = 25.0        # used by floor policy supplementation
TIER_CAPS = {"T1": 10, "T2": 5, "T3": 8, "T4": 5}
TOTAL_RENDERED_CAP = 12            # final merged display budget across all tiers
MIN_COVERAGE_TARGET = 10
TWO_ROUND_THRESHOLD = 3            # top_picks < this triggers Round 2
CATALYST_WAIVER_SCORE_GAP = 10.0   # keep_threshold - this = waiver floor

# Hard failures that permanently exclude from all tiers
HARD_EXCLUSION_FAILURES = frozenset({
    "bars_fetch_failed",
    "price_below_floor",
    "volume_below_floor",
    "suspended",
    "st_or_risk_warning",
})
WRAPPER_FILTER_PROFILE_OVERRIDES: dict[str, dict[str, float]] = {
    # Recovered from a validated historical artifact until the compiled runtime
    # regains native support for this documented profile.
    "month_end_event_support_transition": {
        "keep_threshold": 56.0,
        "strict_top_pick_threshold": 58.0,
    },
    "broad_coverage_mode": {
        "keep_threshold": 55.0,
        "strict_top_pick_threshold": 57.0,
    },
}

# Board-specific threshold adjustments (legacy single-pool mode).
# Retained for backward compatibility; multi-track mode uses TRACK_CONFIGS.
BOARD_THRESHOLD_OVERRIDES: dict[str, dict[str, float]] = {
    "main_board": {
        "keep_threshold": 58.0,
        "strict_top_pick_threshold": 59.0,
    },
}

# Multi-track board-separated pipeline configuration.
# Each key is a track name; board_values lists the return values of
# _compiled.classify_board(ticker) that belong to this track.
# Candidates whose board is not covered by any track are dropped with
# "outside_track_scope".  To add a new track (e.g. star / 科创板),
# simply add an entry here.
TRACK_CONFIGS: dict[str, dict[str, Any]] = {
    "main_board": {
        "label": "主板",
        "board_values": ("main_board",),
        "keep_threshold": 58.0,
        "strict_top_pick_threshold": 59.0,
        "tier_caps": {"T1": 10, "T2": 5, "T3": 8, "T4": 5},
        "min_coverage_target": 10,
        "two_round_threshold": 3,
    },
    "chinext": {
        "label": "创业板",
        "board_values": ("chinext",),
        "keep_threshold": 56.0,
        "strict_top_pick_threshold": 58.0,
        "tier_caps": {"T1": 10, "T2": 5, "T3": 8, "T4": 5},
        "min_coverage_target": 10,
        "two_round_threshold": 3,
    },
}

GEOPOLITICS_REGIME_LABELS = frozenset({
    "escalation",
    "de_escalation",
    "whipsaw",
})

GEOPOLITICS_BENEFICIARY_CHAINS = frozenset({
    "oil_shipping",
    "energy",
    "gold",
    "defense",
})

GEOPOLITICS_HEADWIND_CHAINS = frozenset({
    "cost_sensitive_chemicals",
    "airlines",
    "export_chain",
    "high_beta_growth",
})

GEOPOLITICS_CANDIDATE_DIRECTIONS = frozenset({
    "escalation",
    "de_escalation",
    "whipsaw",
})

GEOPOLITICS_MARKET_SIGNAL_VALUES: dict[str, frozenset[str]] = {
    "oil": frozenset({"up", "down", "flat"}),
    "gold": frozenset({"up", "down", "flat"}),
    "shipping": frozenset({"up", "down", "flat"}),
    "risk_style": frozenset({"risk_on", "risk_off", "mixed"}),
    "usd_rates": frozenset({"tightening", "loosening", "mixed"}),
    "airlines": frozenset({"up", "down", "flat"}),
    "industrials": frozenset({"up", "down", "flat"}),
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


def normalize_macro_geopolitics_overlay(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    regime_label = clean_text(raw.get("regime_label"))
    if regime_label not in GEOPOLITICS_REGIME_LABELS:
        return None

    overlay: dict[str, Any] = {"regime_label": regime_label}
    confidence = clean_text(raw.get("confidence"))
    if confidence:
        overlay["confidence"] = confidence
    headline_risk = clean_text(raw.get("headline_risk"))
    if headline_risk:
        overlay["headline_risk"] = headline_risk

    beneficiary_chains = [
        item for item in unique_strings(raw.get("beneficiary_chains") or [])
        if item in GEOPOLITICS_BENEFICIARY_CHAINS
    ]
    if beneficiary_chains:
        overlay["beneficiary_chains"] = beneficiary_chains

    headwind_chains = [
        item for item in unique_strings(raw.get("headwind_chains") or [])
        if item in GEOPOLITICS_HEADWIND_CHAINS
    ]
    if headwind_chains:
        overlay["headwind_chains"] = headwind_chains

    notes = clean_text(raw.get("notes"))
    if notes:
        overlay["notes"] = notes
    return overlay


def normalize_candidate_signal_row(raw: Any, source_type: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    row: dict[str, Any] = {}
    if source_type == "news":
        source = clean_text(raw.get("source"))
        headline = clean_text(raw.get("headline"))
        if source:
            row["source"] = source
        if headline:
            row["headline"] = headline
    elif source_type == "x":
        account = clean_text(raw.get("account"))
        url = clean_text(raw.get("url"))
        if account:
            row["account"] = account
        if url:
            row["url"] = url

    summary = clean_text(raw.get("summary"))
    if summary:
        row["summary"] = summary

    direction_hint = clean_text(raw.get("direction_hint"))
    if direction_hint in GEOPOLITICS_CANDIDATE_DIRECTIONS:
        row["direction_hint"] = direction_hint

    timestamp = clean_text(raw.get("timestamp"))
    if timestamp:
        row["timestamp"] = timestamp

    return row or None


def normalize_macro_geopolitics_candidate_input(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    normalized: dict[str, Any] = {}

    news_rows = [
        item
        for item in (
            normalize_candidate_signal_row(candidate, "news")
            for candidate in (raw.get("news_signals") or [])
        )
        if item
    ]
    if news_rows:
        normalized["news_signals"] = news_rows

    x_rows = [
        item
        for item in (
            normalize_candidate_signal_row(candidate, "x")
            for candidate in (raw.get("x_signals") or [])
        )
        if item
    ]
    if x_rows:
        normalized["x_signals"] = x_rows

    market_raw = raw.get("market_signals")
    if isinstance(market_raw, dict):
        market_signals: dict[str, str] = {}
        for key, allowed_values in GEOPOLITICS_MARKET_SIGNAL_VALUES.items():
            value = clean_text(market_raw.get(key))
            if value in allowed_values:
                market_signals[key] = value
        if market_signals:
            normalized["market_signals"] = market_signals

    return normalized or None


def synthesize_geopolitics_evidence_block(candidate_input: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(candidate_input, dict):
        return {"news_evidence": [], "x_evidence": [], "market_evidence": []}

    def make_row(
        source_type: str,
        signal_family: str,
        direction: str,
        strength: str,
        summary: str,
    ) -> dict[str, Any]:
        return {
            "source_type": source_type,
            "signal_family": signal_family,
            "direction": direction,
            "strength": strength,
            "summary": summary,
        }

    news_rows: list[dict[str, Any]] = []
    for row in candidate_input.get("news_signals", []):
        if not isinstance(row, dict):
            continue
        direction = clean_text(row.get("direction_hint"))
        if direction in GEOPOLITICS_CANDIDATE_DIRECTIONS:
            news_rows.append(
                make_row(
                    "news",
                    "headline_flow",
                    direction,
                    "medium",
                    clean_text(row.get("summary") or row.get("headline") or "news signal"),
                )
            )

    x_rows: list[dict[str, Any]] = []
    for row in candidate_input.get("x_signals", []):
        if not isinstance(row, dict):
            continue
        direction = clean_text(row.get("direction_hint"))
        if direction in GEOPOLITICS_CANDIDATE_DIRECTIONS:
            x_rows.append(
                make_row(
                    "x",
                    "x_discussion",
                    direction,
                    "medium",
                    clean_text(row.get("summary") or "x signal"),
                )
            )

    market_rows: list[dict[str, Any]] = []
    market = candidate_input.get("market_signals")
    if isinstance(market, dict):
        if market.get("oil") == "up":
            market_rows.append(make_row("market", "oil", "escalation", "medium", "Oil is confirming upside risk."))
        if market.get("oil") == "down":
            market_rows.append(make_row("market", "oil", "de_escalation", "medium", "Oil is unwinding risk premium."))
        if market.get("gold") == "up":
            market_rows.append(make_row("market", "gold", "escalation", "medium", "Gold is confirming safety demand."))
        if market.get("gold") == "down":
            market_rows.append(make_row("market", "gold", "de_escalation", "low", "Gold is easing with lower safety demand."))
        if market.get("shipping") == "up":
            market_rows.append(make_row("market", "shipping", "escalation", "medium", "Shipping tape is repricing disruption risk."))
        if market.get("shipping") == "down":
            market_rows.append(make_row("market", "shipping", "de_escalation", "low", "Shipping tape is easing disruption risk."))
        if market.get("risk_style") == "risk_off":
            market_rows.append(make_row("market", "risk_style", "escalation", "medium", "Risk style is defensive."))
        if market.get("risk_style") == "risk_on":
            market_rows.append(make_row("market", "risk_style", "de_escalation", "medium", "Risk style is improving."))
        if market.get("risk_style") == "mixed":
            market_rows.append(make_row("market", "risk_style", "whipsaw", "low", "Risk style is mixed."))        
        if market.get("usd_rates") == "tightening":
            market_rows.append(make_row("market", "usd_rates", "escalation", "low", "USD/rates backdrop is tighter."))
        if market.get("usd_rates") == "loosening":
            market_rows.append(make_row("market", "usd_rates", "de_escalation", "low", "USD/rates backdrop is easing."))
        if market.get("airlines") == "down":
            market_rows.append(make_row("market", "airlines", "escalation", "medium", "Airlines are lagging."))
        if market.get("airlines") == "up":
            market_rows.append(make_row("market", "airlines", "de_escalation", "low", "Airlines are recovering."))
        if market.get("industrials") == "down":
            market_rows.append(make_row("market", "industrials", "escalation", "low", "Industrials are under pressure."))
        if market.get("industrials") == "up":
            market_rows.append(make_row("market", "industrials", "de_escalation", "low", "Industrials are stabilizing."))

    return {
        "news_evidence": news_rows,
        "x_evidence": x_rows,
        "market_evidence": market_rows,
    }


def build_macro_geopolitics_candidate(candidate_input: dict[str, Any] | None) -> dict[str, Any]:
    evidence = synthesize_geopolitics_evidence_block(candidate_input)
    all_rows = evidence["news_evidence"] + evidence["x_evidence"] + evidence["market_evidence"]
    if not all_rows:
        return {
            "candidate_regime": "insufficient_signal",
            "confidence": "low",
            "signal_alignment": "none",
            "status": "insufficient_signal",
            "evidence_summary": ["No usable geopolitical candidate signals were provided."],
            "evidence_block": evidence,
        }

    score = {"escalation": 0, "de_escalation": 0, "whipsaw": 0}
    source_directions: dict[str, dict[str, int]] = {}
    weights = {"low": 1, "medium": 2, "high": 3}
    for row in all_rows:
        direction = row.get("direction")
        if direction not in score:
            continue
        weight = weights.get(clean_text(row.get("strength")), 1)
        score[direction] += weight
        source_type = clean_text(row.get("source_type"))
        source_directions.setdefault(source_type, {})
        source_directions[source_type][direction] = source_directions[source_type].get(direction, 0) + weight

    top_by_source: dict[str, str] = {}
    for source_type, direction_scores in source_directions.items():
        if not direction_scores:
            continue
        top_direction = max(direction_scores.items(), key=lambda kv: kv[1])[0]
        top_by_source[source_type] = top_direction

    aligned_pairs = []
    for pair in ("news+x", "news+market", "x+market"):
        left, right = pair.split("+")
        if left in top_by_source and right in top_by_source and top_by_source[left] == top_by_source[right]:
            aligned_pairs.append(pair)

    ordered_scores = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    top_regime, top_score = ordered_scores[0]
    second_score = ordered_scores[1][1] if len(ordered_scores) > 1 else 0
    has_full_alignment = {"news", "x", "market"}.issubset(top_by_source) and len({top_by_source["news"], top_by_source["x"], top_by_source["market"]}) == 1

    if not aligned_pairs or top_score - second_score < 2:
        return {
            "candidate_regime": "insufficient_signal",
            "confidence": "low",
            "signal_alignment": "mixed",
            "status": "insufficient_signal",
            "evidence_summary": [clean_text(row.get("summary")) for row in all_rows[:3] if clean_text(row.get("summary"))],
            "evidence_block": evidence,
        }

    candidate_regime = top_regime
    confidence = "high" if top_score >= 6 else "medium"
    signal_alignment = "news+x+market" if has_full_alignment else aligned_pairs[0]
    return {
        "candidate_regime": candidate_regime,
        "confidence": confidence,
        "signal_alignment": signal_alignment,
        "status": "candidate_only",
        "evidence_summary": [clean_text(row.get("summary")) for row in all_rows[:3] if clean_text(row.get("summary"))],
        "beneficiary_bias": (
            ["oil_shipping", "energy", "gold", "defense"]
            if candidate_regime == "escalation"
            else ["airlines", "export_chain", "high_beta_growth"]
            if candidate_regime == "de_escalation"
            else []
        ),
        "headwind_bias": (
            ["airlines", "cost_sensitive_chemicals", "export_chain", "high_beta_growth"]
            if candidate_regime == "escalation"
            else ["oil_shipping", "energy", "gold", "defense"]
            if candidate_regime == "de_escalation"
            else []
        ),
        "evidence_block": evidence,
    }


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

    # In multi-track mode, per-track payloads carry track-specific thresholds
    # that must override the profile-level defaults applied above.
    track_name = raw_payload.get("_track_name")
    if track_name:
        track_cfg = raw_payload.get("_track_config") or TRACK_CONFIGS.get(track_name, {})
        for key in ("keep_threshold", "strict_top_pick_threshold"):
            if key in track_cfg:
                normalized[key] = track_cfg[key]
                profile_settings[key] = track_cfg[key]
        normalized["profile_settings"] = profile_settings

    return normalized


def build_x_discovery_context(raw_request: dict[str, Any]) -> dict[str, Any]:
    subject_registry = raw_request.get("subject_registry") if isinstance(raw_request.get("subject_registry"), dict) else {}
    subjects = subject_registry.get("subjects") if isinstance(subject_registry.get("subjects"), list) else []
    chain_map_by_name: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        for rule in subject.get("logic_basket_rules", []) if isinstance(subject.get("logic_basket_rules"), list) else []:
            if not isinstance(rule, dict):
                continue
            chain_name = clean_text(rule.get("sector_or_chain") or rule.get("basket_name"))
            if not chain_name:
                continue
            leaders = unique_strings(rule.get("core_candidate_names") or rule.get("candidate_names") or [])
            tier_1 = unique_strings(rule.get("core_candidate_names") or rule.get("candidate_names") or [])
            all_candidates = unique_strings(rule.get("candidate_names") or [])
            tier_2 = [item for item in all_candidates if item not in tier_1]
            existing = chain_map_by_name.setdefault(
                chain_name,
                {"chain_name": chain_name, "leaders": [], "tier_1": [], "tier_2": [], "all_candidates": []},
            )
            existing["leaders"] = unique_strings(existing["leaders"] + leaders)
            existing["tier_1"] = unique_strings(existing["tier_1"] + tier_1)
            existing["tier_2"] = unique_strings(existing["tier_2"] + tier_2)
            existing["all_candidates"] = unique_strings(existing["all_candidates"] + all_candidates)
    return {"chain_map": list(chain_map_by_name.values())}


def normalize_request_with_compiled(raw_payload: dict[str, Any], compiled_normalize_request: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    normalized = apply_wrapper_filter_profile_override(
        raw_payload,
        compiled_normalize_request(raw_payload),
    )
    geopolitics_overlay = normalize_macro_geopolitics_overlay(raw_payload.get("macro_geopolitics_overlay"))
    if geopolitics_overlay:
        normalized["macro_geopolitics_overlay"] = geopolitics_overlay
    else:
        normalized.pop("macro_geopolitics_overlay", None)
    geopolitics_candidate_input = normalize_macro_geopolitics_candidate_input(
        raw_payload.get("macro_geopolitics_candidate_input")
    )
    if geopolitics_candidate_input:
        normalized["macro_geopolitics_candidate_input"] = geopolitics_candidate_input
    else:
        normalized.pop("macro_geopolitics_candidate_input", None)
    batch_path = clean_text(normalized.get("x_style_batch_result_path"))
    if batch_path:
        path = Path(batch_path).expanduser().resolve()
        if path.exists():
            try:
                batch_payload = load_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                batch_payload = {}
            if batch_payload:
                handles, overlays = extract_x_style_overlays_from_result(
                    batch_payload,
                    selected_handles=normalized.get("x_style_selected_handles", []),
                )
                if handles:
                    normalized["x_style_selected_handles"] = handles
                if overlays:
                    normalized["x_style_overlays"] = overlays
                x_discovery_candidates = build_x_style_discovery_candidates(
                    batch_payload,
                    selected_handles=normalized.get("x_style_selected_handles", []),
                )
                if x_discovery_candidates:
                    existing = normalized.get("event_discovery_candidates")
                    existing_rows = existing if isinstance(existing, list) else []
                    normalized["event_discovery_candidates"] = existing_rows + x_discovery_candidates

    x_discovery_request = raw_payload.get("x_discovery_request")
    x_discovery_request_path = raw_payload.get("x_discovery_request_path")
    if not isinstance(x_discovery_request, dict) and clean_text(x_discovery_request_path):
        try:
            x_discovery_request = load_json(clean_text(x_discovery_request_path))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            x_discovery_request = None
    if isinstance(x_discovery_request, dict):
        try:
            from x_stock_picker_style_runtime import run_x_stock_picker_style, run_x_stock_picker_style_batch
        except ModuleNotFoundError:
            x_result = {}
        else:
            is_batch_request = bool(
                isinstance(x_discovery_request.get("subject_registry"), dict)
                or clean_text(x_discovery_request.get("subject_registry_path"))
                or isinstance(x_discovery_request.get("subject_overrides_by_handle"), dict)
                or isinstance(x_discovery_request.get("shared_request"), dict)
                or isinstance(x_discovery_request.get("selected_handles"), list)
            )
            if is_batch_request:
                x_result = run_x_stock_picker_style_batch(deepcopy(x_discovery_request))
                x_discovery_context = build_x_discovery_context(x_discovery_request)
                if x_discovery_context.get("chain_map"):
                    normalized["x_discovery_context"] = x_discovery_context
            else:
                x_result = run_x_stock_picker_style(deepcopy(x_discovery_request))
        x_request_candidates = build_x_style_discovery_candidates(x_result)
        if x_request_candidates:
            existing = normalized.get("event_discovery_candidates")
            existing_rows = existing if isinstance(existing, list) else []
            normalized["event_discovery_candidates"] = existing_rows + x_request_candidates
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


def apply_board_threshold_overrides(
    scorecard: list[dict[str, Any]],
    profile: str,
    base_keep_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Re-evaluate keep / gap per candidate using board-specific thresholds.

    The compiled runtime runs with the *lowest* keep_threshold so no candidate
    is prematurely discarded.  This function tightens the gate for boards that
    have a higher threshold (e.g. main_board 58 vs chinext 56).

    Returns (updated_scorecard, effective_thresholds_by_board).
    Only active for ``month_end_event_support_transition`` profile.
    """
    if profile != "month_end_event_support_transition" or not BOARD_THRESHOLD_OVERRIDES:
        return scorecard, {}

    effective: dict[str, float] = {}
    for entry in scorecard:
        ticker = str(entry.get("ticker") or "")
        board = _compiled.classify_board(ticker)
        override = BOARD_THRESHOLD_OVERRIDES.get(board)
        board_keep = override["keep_threshold"] if override else base_keep_threshold
        effective[board] = board_keep

        score = entry.get("score")
        if score is None:
            continue

        old_gap = entry.get("keep_threshold_gap")
        new_gap = round(float(score) - board_keep, 2)
        entry["keep_threshold_gap"] = new_gap
        entry["board"] = board
        entry["board_keep_threshold"] = board_keep

        # Demote: core said keep but score < board threshold
        if entry.get("keep") and score < board_keep:
            entry["keep"] = False
            entry["tier_tags"] = entry.get("tier_tags", []) + ["board_demoted"]

        # Promote: core said not-keep but score >= board threshold and no hard failures
        hard_failures = set(entry.get("hard_filter_failures") or [])
        if (
            not entry.get("keep")
            and score >= board_keep
            and not hard_failures - {"score_below_keep_threshold"}
        ):
            entry["keep"] = True
            entry["tier_tags"] = entry.get("tier_tags", []) + ["board_promoted"]

    return scorecard, effective


def split_universe_by_board(
    prepared_payload: dict[str, Any],
    track_configs: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Split a prepared request into per-track payloads by board classification.

    Returns ``(track_payloads, out_of_scope)`` where *track_payloads* maps
    track name to a deep-copied request whose ``universe_candidates`` and
    ``candidate_tickers`` contain only candidates belonging to that track, and
    *out_of_scope* is a list of candidate dicts that did not match any track
    (e.g. star-board tickers).

    Each track payload also has ``keep_threshold`` and
    ``strict_top_pick_threshold`` overridden from the track config.
    """
    configs = track_configs or TRACK_CONFIGS
    # Build a reverse lookup: board_value -> track_name
    board_to_track: dict[str, str] = {}
    for track_name, cfg in configs.items():
        for bv in cfg.get("board_values", ()):
            board_to_track[bv] = track_name

    universe = prepared_payload.get("universe_candidates") or []
    candidate_tickers = [clean_text(t) for t in prepared_payload.get("candidate_tickers", []) if clean_text(t)]
    history_by_ticker = prepared_payload.get("history_by_ticker") or {}

    # Classify each candidate
    track_candidates: dict[str, list[dict[str, Any]]] = {name: [] for name in configs}
    track_tickers: dict[str, list[str]] = {name: [] for name in configs}
    out_of_scope: list[dict[str, Any]] = []

    for candidate in universe:
        ticker = clean_text(candidate.get("ticker"))
        if not ticker:
            continue
        board = _compiled.classify_board(ticker)
        track_name = board_to_track.get(board)
        if track_name:
            track_candidates[track_name].append(candidate)
        else:
            out_of_scope.append({
                "ticker": ticker,
                "name": clean_text(candidate.get("name")) or ticker,
                "board": board,
                "drop_reason": "outside_track_scope",
            })

    # Also split candidate_tickers (for requests that use tickers instead of universe)
    for ticker in candidate_tickers:
        board = _compiled.classify_board(ticker)
        track_name = board_to_track.get(board)
        if track_name:
            track_tickers[track_name].append(ticker)

    # Build per-track payloads
    track_payloads: dict[str, dict[str, Any]] = {}
    for track_name, cfg in configs.items():
        payload = deepcopy(prepared_payload)
        payload["universe_candidates"] = track_candidates[track_name]
        if candidate_tickers:
            payload["candidate_tickers"] = track_tickers[track_name]
        # Filter history_by_ticker to only this track's tickers
        track_ticker_set = {clean_text(c.get("ticker")) for c in track_candidates[track_name]}
        if history_by_ticker:
            payload["history_by_ticker"] = {
                k: v for k, v in history_by_ticker.items() if k in track_ticker_set
            }
        # Apply track-specific thresholds
        payload["keep_threshold"] = cfg["keep_threshold"]
        payload["strict_top_pick_threshold"] = cfg["strict_top_pick_threshold"]
        # Tag the track
        payload["_track_name"] = track_name
        payload["_track_config"] = cfg
        track_payloads[track_name] = payload

    return track_payloads, out_of_scope


def compute_independent_source_count(candidate: dict[str, Any]) -> int:
    """Count independent information sources for T2 admission."""
    sources: set[tuple[str, str]] = set()
    for x in candidate.get("x_style_inputs", []):
        if x.get("source_account"):
            sources.add(("x", x["source_account"]))
    for ev in candidate.get("event_cards", []):
        src_type = ev.get("source_type", "")
        if src_type == "filing":
            sources.add(("filing", ev.get("source_id", "filing")))
        elif src_type == "company_event":
            sources.add(("company_event", ev.get("source_id", "company_event")))
    for d in candidate.get("discovery_candidates", []):
        sources.add(("discovery", d.get("ticker", "unknown")))
    return len(sources)


def classify_geopolitics_chain_bias(chain_name: str, overlay: dict[str, Any] | None) -> str:
    if not isinstance(overlay, dict):
        return ""
    chain = clean_text(chain_name)
    if not chain:
        return ""
    if chain in set(overlay.get("beneficiary_chains") or []):
        return "beneficiary"
    if chain in set(overlay.get("headwind_chains") or []):
        return "headwind"
    return ""


def compute_geopolitics_bias(candidate: dict[str, Any], overlay: dict[str, Any] | None) -> float:
    if not isinstance(overlay, dict):
        return 0.0
    regime = clean_text(overlay.get("regime_label"))
    if regime not in GEOPOLITICS_REGIME_LABELS:
        return 0.0
    chain_name = clean_text(candidate.get("chain_name") or candidate.get("sector_or_chain"))
    bias_kind = classify_geopolitics_chain_bias(chain_name, overlay)
    if not bias_kind:
        return 0.0
    magnitude_map = {
        "escalation": 1.5,
        "de_escalation": 1.5,
        "whipsaw": 0.5,
    }
    magnitude = magnitude_map.get(regime, 0.0)
    if regime == "escalation":
        return magnitude if bias_kind == "beneficiary" else -magnitude
    if regime == "de_escalation":
        return -magnitude if bias_kind == "beneficiary" else magnitude
    if regime == "whipsaw":
        return magnitude if bias_kind == "beneficiary" else -magnitude
    return 0.0


def sort_candidates_with_geopolitics_bias(
    candidates: list[dict[str, Any]],
    overlay: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        bias = compute_geopolitics_bias(item, overlay)
        enriched = item
        enriched["macro_geopolitics_bias"] = bias
        enriched["macro_geopolitics_bias_label"] = classify_geopolitics_chain_bias(
            clean_text(item.get("chain_name") or item.get("sector_or_chain")),
            overlay,
        )
        ordered.append(enriched)
    ordered.sort(
        key=lambda x: (x.get("adjusted_total_score", 0) + x.get("macro_geopolitics_bias", 0.0)),
        reverse=True,
    )
    return ordered


def should_promote_near_miss_to_event_driven(candidate: dict[str, Any]) -> bool:
    """Check if a near-miss candidate qualifies for T2 promotion."""
    if candidate.get("structured_catalyst_score", 0) >= 10:
        return True
    if candidate.get("discovery_bucket") == "qualified":
        return True
    if compute_independent_source_count(candidate) >= 2:
        return True
    return False


def assign_tiers(
    top_picks: list[dict[str, Any]],
    near_miss_candidates: list[dict[str, Any]],
    discovery_results: dict[str, list[dict[str, Any]]],
    all_assessed: list[dict[str, Any]],
    keep_threshold: float,
    *,
    geopolitics_overlay: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Assign candidates to T1/T2/T3/T4 tiers.

    Returns dict with keys "T1", "T2", "T3", "T4", each a list of
    candidate dicts with added "wrapper_tier" and "tier_tags" fields.
    """
    assigned_tickers: set[str] = set()
    tiers: dict[str, list[dict[str, Any]]] = {"T1": [], "T2": [], "T3": [], "T4": []}

    # --- T1: top_picks from compiled core ---
    for c in sorted(
        top_picks,
        key=lambda x: x.get("adjusted_total_score", 0),
        reverse=True,
    )[:TIER_CAPS["T1"]]:
        c["wrapper_tier"] = "T1"
        c["tier_tags"] = c.get("tier_tags", [])
        tiers["T1"].append(c)
        assigned_tickers.add(c.get("ticker"))

    # --- T2 Path A: promoted near-miss ---
    ordered_near_miss = sort_candidates_with_geopolitics_bias(near_miss_candidates, geopolitics_overlay)
    ordered_watch = sort_candidates_with_geopolitics_bias(discovery_results.get("watch", []), geopolitics_overlay)
    ordered_track = sort_candidates_with_geopolitics_bias(discovery_results.get("track", []), geopolitics_overlay)

    for c in ordered_near_miss:
        if c.get("ticker") in assigned_tickers:
            continue
        if should_promote_near_miss_to_event_driven(c):
            c["wrapper_tier"] = "T2"
            c["tier_tags"] = c.get("tier_tags", []) + ["near_miss_promoted"]
            tiers["T2"].append(c)
            assigned_tickers.add(c.get("ticker"))
            if len(tiers["T2"]) >= TIER_CAPS["T2"]:
                break

    # --- T2 Path B: discovery qualified ---
    for c in discovery_results.get("qualified", []):
        if c.get("ticker") in assigned_tickers:
            continue
        if len(tiers["T2"]) >= TIER_CAPS["T2"]:
            break
        c["wrapper_tier"] = "T2"
        c["tier_tags"] = c.get("tier_tags", []) + ["discovery_qualified"]
        tiers["T2"].append(c)
        assigned_tickers.add(c.get("ticker"))

    # --- T3: remaining near-miss + discovery watch ---
    for c in ordered_near_miss:
        if c.get("ticker") in assigned_tickers:
            continue
        if len(tiers["T3"]) >= TIER_CAPS["T3"]:
            break
        c["wrapper_tier"] = "T3"
        c["tier_tags"] = c.get("tier_tags", [])
        tiers["T3"].append(c)
        assigned_tickers.add(c.get("ticker"))

    for c in ordered_watch:
        if c.get("ticker") in assigned_tickers:
            continue
        if len(tiers["T3"]) >= TIER_CAPS["T3"]:
            break
        c["wrapper_tier"] = "T3"
        c["tier_tags"] = c.get("tier_tags", []) + ["discovery_watch"]
        tiers["T3"].append(c)
        assigned_tickers.add(c.get("ticker"))

    # --- T4: discovery track + chain/sympathy ---
    for c in ordered_track:
        if c.get("ticker") in assigned_tickers:
            continue
        if len(tiers["T4"]) >= TIER_CAPS["T4"]:
            break
        c["wrapper_tier"] = "T4"
        c["tier_tags"] = c.get("tier_tags", []) + ["discovery_track"]
        tiers["T4"].append(c)
        assigned_tickers.add(c.get("ticker"))

    return tiers


def apply_catalyst_waiver(
    all_assessed: list[dict[str, Any]],
    profile: str,
    keep_threshold: float,
) -> list[dict[str, Any]]:
    """
    Wrapper-only reclassification for catalyst-only failures.

    Does NOT modify the core's keep field. Instead, returns candidates
    eligible for T3 via catalyst waiver. These should be merged into
    near_miss before calling assign_tiers.
    """
    WAIVER_PROFILES = {
        "month_end_event_support_transition",
        "broad_coverage_mode",
    }
    if profile not in WAIVER_PROFILES:
        return []

    waiver_candidates: list[dict[str, Any]] = []
    score_floor = keep_threshold - CATALYST_WAIVER_SCORE_GAP

    for c in all_assessed:
        # Skip if core said keep=True (already a top_pick)
        if c.get("keep"):
            continue
        failures = c.get("hard_filter_failures", [])
        # Must have exactly one failure and it must be catalyst
        if (
            len(failures) == 1
            and failures[0] == "no_structured_catalyst_within_window"
            and c.get("adjusted_total_score", 0) >= score_floor
        ):
            # Check not in hard exclusion list (defensive)
            if not HARD_EXCLUSION_FAILURES.intersection(failures):
                c["tier_tags"] = c.get("tier_tags", []) + ["catalyst_waived"]
                waiver_candidates.append(c)

    return waiver_candidates


def evaluate_with_coverage_fallback(
    candidates: list[dict[str, Any]],
    bars_data: dict[str, Any],
    profile: str,
    assess_fn: Callable,
) -> tuple[list[dict[str, Any]], str, str]:
    """
    Two-round evaluation. If Round 1 produces < TWO_ROUND_THRESHOLD
    top_picks and profile is not already broad_coverage_mode,
    re-evaluate all candidates with broad_coverage_mode.

    Returns: (all_assessed, profile_used, round_info)
    """
    # Round 1
    all_assessed: list[dict[str, Any]] = []
    for c in candidates:
        result = assess_fn(c, bars_data, profile)
        all_assessed.append(result)

    top_picks = [c for c in all_assessed if c.get("keep")]

    if len(top_picks) >= TWO_ROUND_THRESHOLD or profile == "broad_coverage_mode":
        return all_assessed, profile, "round_1"

    # Round 2: re-evaluate everything with broad_coverage_mode
    all_assessed_r2: list[dict[str, Any]] = []
    for c in candidates:
        result = assess_fn(c, bars_data, "broad_coverage_mode")
        all_assessed_r2.append(result)

    return all_assessed_r2, "broad_coverage_mode", "round_2"


def apply_floor_policy(
    tiers: dict[str, list[dict[str, Any]]],
    all_assessed: list[dict[str, Any]],
    discovery_results: dict[str, list[dict[str, Any]]],
    keep_threshold: float,
) -> dict[str, list[dict[str, Any]]]:
    """
    If total names < MIN_COVERAGE_TARGET, supplement from:
    1. Expanded near-miss (gap=NEAR_MISS_FLOOR_GAP)
    2. Relaxed discovery watch/track
    3. Score-sorted remaining candidates

    Never includes HARD_EXCLUSION_FAILURES candidates.
    Tags all supplemented names with [coverage_fill].
    """
    total = sum(len(v) for v in tiers.values())
    if total >= MIN_COVERAGE_TARGET:
        return tiers

    assigned_tickers: set[str] = set()
    for tier_list in tiers.values():
        for c in tier_list:
            assigned_tickers.add(c.get("ticker"))

    def is_excluded(c: dict[str, Any]) -> bool:
        failures = set(c.get("hard_filter_failures", []))
        return bool(HARD_EXCLUSION_FAILURES.intersection(failures))

    # Priority 1: expanded near-miss (gap=NEAR_MISS_FLOOR_GAP)
    for c in all_assessed:
        if total >= MIN_COVERAGE_TARGET:
            break
        if c.get("ticker") in assigned_tickers or is_excluded(c):
            continue
        score = c.get("adjusted_total_score", 0)
        gap = keep_threshold - score
        if 0 < gap <= NEAR_MISS_FLOOR_GAP:
            c["wrapper_tier"] = "T3"
            c["tier_tags"] = c.get("tier_tags", []) + ["coverage_fill"]
            tiers["T3"].append(c)
            assigned_tickers.add(c.get("ticker"))
            total += 1

    # Priority 2: relaxed discovery watch/track
    for c in discovery_results.get("watch", []) + discovery_results.get("track", []):
        if total >= MIN_COVERAGE_TARGET:
            break
        if c.get("ticker") in assigned_tickers or is_excluded(c):
            continue
        c["wrapper_tier"] = "T3"
        c["tier_tags"] = c.get("tier_tags", []) + ["coverage_fill"]
        tiers["T3"].append(c)
        assigned_tickers.add(c.get("ticker"))
        total += 1

    # Priority 3: score-sorted remaining
    remaining = [
        c for c in all_assessed
        if c.get("ticker") not in assigned_tickers and not is_excluded(c)
    ]
    remaining.sort(key=lambda x: x.get("adjusted_total_score", 0), reverse=True)
    for c in remaining:
        if total >= MIN_COVERAGE_TARGET:
            break
        c["wrapper_tier"] = "T3"
        c["tier_tags"] = c.get("tier_tags", []) + ["coverage_fill"]
        tiers["T3"].append(c)
        assigned_tickers.add(c.get("ticker"))
        total += 1

    return tiers


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


def build_discovery_lane_summary(discovery_rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"qualified_count": 0, "watch_count": 0, "track_count": 0}
    for item in discovery_rows:
        bucket = clean_text(item.get("discovery_bucket"))
        if bucket == "qualified":
            summary["qualified_count"] += 1
        elif bucket == "watch":
            summary["watch_count"] += 1
        else:
            summary["track_count"] += 1
    return summary


def build_discovery_candidates(raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        item = normalize_event_candidate(raw)
        item["rumor_confidence_range"] = compute_rumor_confidence_range(item)
        item["event_state"] = classify_event_state(item)
        item["market_validation_summary"] = classify_market_validation(item)
        item["trading_usability"] = classify_trading_usability(item)
        item["discovery_bucket"] = assign_discovery_bucket(item)
        rows.append(item)
    return rows


def merge_discovery_candidate_inputs(
    manual_candidates: list[dict[str, Any]],
    auto_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [candidate for candidate in (manual_candidates + auto_candidates) if isinstance(candidate, dict)]


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
        "hard_filter_failures": deepcopy(candidate.get("hard_filter_failures", [])),
    }


def build_decision_factors_from_result(enriched: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    factors = {"qualified": [], "near_miss": [], "blocked": []}
    for item in enriched.get("top_picks", []) if isinstance(enriched.get("top_picks"), list) else []:
        if isinstance(item, dict):
            factors["qualified"].append(build_decision_factor_entry(item, "可执行"))
    near_miss_candidates = (
        enriched.get("near_miss_candidates", [])
        if isinstance(enriched.get("near_miss_candidates"), list)
        else []
    )
    diagnostic_scorecard = (
        enriched.get("diagnostic_scorecard", [])
        if isinstance(enriched.get("diagnostic_scorecard"), list)
        else []
    )
    candidate_lookup: dict[str, dict[str, Any]] = {}
    for item in near_miss_candidates + diagnostic_scorecard:
        if not isinstance(item, dict):
            continue
        ticker = clean_text(item.get("ticker"))
        if ticker and ticker not in candidate_lookup:
            candidate_lookup[ticker] = deepcopy(item)

    near_miss_source: list[dict[str, Any]] = []
    seen_near_miss: set[str] = set()
    tier_output = enriched.get("tier_output", {}) if isinstance(enriched.get("tier_output"), dict) else {}
    rendered_t3 = tier_output.get("T3", []) if isinstance(tier_output.get("T3"), list) else []
    if rendered_t3:
        for row in rendered_t3:
            if not isinstance(row, dict):
                continue
            ticker = clean_text(row.get("ticker"))
            if not ticker or ticker in seen_near_miss:
                continue
            base = deepcopy(candidate_lookup.get(ticker) or row)
            base.setdefault("ticker", ticker)
            if row.get("name") not in (None, ""):
                base["name"] = row.get("name")
            if row.get("score") not in (None, "") and base.get("score") in (None, ""):
                base["score"] = row.get("score")
            if row.get("track_name") not in (None, ""):
                base["track_name"] = row.get("track_name")
            if isinstance(row.get("tier_tags"), list):
                merged_tags = list(base.get("tier_tags", []))
                for tag in row.get("tier_tags", []):
                    if tag not in merged_tags:
                        merged_tags.append(tag)
                base["tier_tags"] = merged_tags
            base["midday_status"] = "near_miss"
            near_miss_source.append(base)
            seen_near_miss.add(ticker)
    else:
        for item in near_miss_candidates:
            if not isinstance(item, dict):
                continue
            ticker = clean_text(item.get("ticker"))
            if ticker and ticker in seen_near_miss:
                continue
            near_miss_source.append(item)
            if ticker:
                seen_near_miss.add(ticker)

    for item in near_miss_source:
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


def build_upgrade_trigger(card: dict[str, Any], keep_threshold: float | int | None) -> str:
    action = clean_text(card.get("action"))
    score = card.get("score")
    technical_summary = clean_text(card.get("technical_summary"))
    event_summary = clean_text(card.get("event_summary"))
    driver = "技术与事件验证继续强化"
    if "均线多头结构" in technical_summary or "趋势模板通过" in technical_summary:
        driver = "趋势结构和量价验证继续保持"
    elif event_summary and "证据不足" not in event_summary:
        driver = "关键事件催化继续强化"
    if action == "继续观察" and score not in (None, "") and keep_threshold not in (None, ""):
        return f"若评分从 {score} 修复至 {keep_threshold}+，且{driver}，可升级到执行层。"
    if action == "不执行" and card.get("keep_threshold_gap") not in (None, ""):
        return "若当前硬伤消失，且分数重新回到 keep line 之上，才重新进入观察名单。"
    return "若技术、事件和资金验证继续改善，可考虑上调优先级。"


def build_downgrade_trigger(card: dict[str, Any]) -> str:
    action = clean_text(card.get("action"))
    failures = card.get("hard_filter_failures") if isinstance(card.get("hard_filter_failures"), list) else []
    if failures:
        return f"若 `{', '.join(failures)}` 继续存在或再次出现，维持当前降级结论。"
    technical_summary = clean_text(card.get("technical_summary"))
    if "均线多头结构" in technical_summary or "短中期均线仍偏强" in technical_summary:
        return "若价格重新跌回关键均线下方或趋势模板转弱，应立即降级。"
    if action == "可执行":
        return "若技术承接转弱、事件验证回落或链条共振消失，应从执行层降回观察。"
    if action == "继续观察":
        return "若技术结构转弱、事件兑现不及预期或链条共振消失，应降级为不执行。"
    return "若当前硬伤继续恶化，维持不执行。"


def build_event_risk_trigger(card: dict[str, Any]) -> str:
    key_evidence = card.get("key_evidence") if isinstance(card.get("key_evidence"), list) else []
    for item in key_evidence:
        text = clean_text(item)
        if not text:
            continue
        matches = re.findall(r"(\d{3,})\s*万元", text)
        if matches:
            return f"若实际净利润低于预告下限 {matches[0]} 万元，应警惕事件预期落空。"
    event_risk = clean_text(card.get("expectation_risk_summary"))
    if event_risk:
        return event_risk
    event_summary = clean_text(card.get("event_summary"))
    if "证据不足" in event_summary:
        return "若关键事件仍未进入窗口或验证继续缺失，不进入执行判断。"
    return ""


def build_geopolitics_bias_summary(chain_name: str, overlay: dict[str, Any] | None) -> str:
    regime = clean_text((overlay or {}).get("regime_label"))
    if regime not in GEOPOLITICS_REGIME_LABELS:
        return ""
    bias_kind = classify_geopolitics_chain_bias(chain_name, overlay)
    if not bias_kind:
        return ""
    if regime == "escalation":
        return "链条偏置：地缘升级下的受益链条" if bias_kind == "beneficiary" else "链条偏置：地缘升级下的承压链条"
    if regime == "de_escalation":
        return "链条偏置：地缘缓和下的受益链条" if bias_kind == "beneficiary" else "链条偏置：地缘缓和下的承压链条"
    return "链条偏置：whipsaw 阶段优先看确认，不看情绪先手"


def build_geopolitics_execution_constraint(action: str, overlay: dict[str, Any] | None) -> str:
    regime = clean_text((overlay or {}).get("regime_label"))
    if regime == "escalation":
        return "执行约束：轻仓，不追高，隔夜谨慎"
    if regime == "de_escalation":
        return "执行约束：优先跟随确认后的风险偏好修复，不把地缘缓和单独当成追价理由"
    if regime == "whipsaw":
        return "执行约束：headline reversal risk 高，优先等确认，不做激进隔夜博弈"
    return ""


def build_decision_flow_card(
    factor: dict[str, Any],
    *,
    keep_threshold: float | None,
    event_card: dict[str, Any] | None,
    chain_entry: dict[str, Any] | None,
    geopolitics_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = deepcopy(factor)
    event_context = event_card if isinstance(event_card, dict) else {}
    chain_context = chain_entry if isinstance(chain_entry, dict) else {}
    action = clean_text(card.get("action"))
    ticker = clean_text(card.get("ticker")) or "unknown"
    score = card.get("score")
    gap = card.get("keep_threshold_gap")
    chain_name = clean_text(event_context.get("chain_name")) or clean_text(chain_context.get("chain_name")) or "unknown"
    chain_role = clean_text(event_context.get("chain_role")) or "unknown"
    fallback_bucket = {"可执行": "稳健核心", "继续观察": "继续观察", "不执行": "不执行"}.get(action, "继续观察")
    trading_profile_bucket = clean_text(event_context.get("trading_profile_bucket")) or fallback_bucket
    logic_summary = clean_text(card.get("logic_summary")) or clean_text(event_context.get("trading_profile_judgment")) or f"当前动作 {action}"
    conclusion = logic_summary.rstrip("。")
    if score not in (None, "") and keep_threshold not in (None, "") and gap not in (None, ""):
        conclusion = f"{conclusion}。评分 {score}，执行门槛 {keep_threshold}，差距 {gap}。"
    elif score not in (None, "") and gap not in (None, ""):
        conclusion = f"{conclusion}。评分 {score}，差距 {gap}。"
    technical_summary = clean_text(card.get("technical_summary")) or "技术形态证据不足。"
    event_summary = clean_text(card.get("event_summary")) or clean_text(event_context.get("expectation_basis_summary")) or "事件证据不足。"
    community_conviction = clean_text(event_context.get("community_conviction")) or "unknown"
    validation_label = clean_text((event_context.get("market_validation_summary") or {}).get("label")) or "unknown"
    event_bits = [event_summary, f"社区一致性: {community_conviction}", f"量价验证: {validation_label}"]
    chain_summary = "；".join(
        bit
        for bit in [
            f"链条: {chain_name}" if chain_name else "",
            f"角色: {chain_role}" if chain_role and chain_role != 'unknown' else "",
            f"交易属性: {trading_profile_bucket}" if trading_profile_bucket else "",
            clean_text(chain_context.get("chain_playbook")) or clean_text(event_context.get("chain_path_summary")) or "",
            build_geopolitics_bias_summary(chain_name, geopolitics_overlay),
        ]
        if bit
    ) or "链条共振证据不足。"
    operation_parts = [
        clean_text(event_context.get("trading_profile_usage")) or clean_text(card.get("trade_layer_summary")) or "先等更多确认。",
    ]
    geopolitics_constraint = build_geopolitics_execution_constraint(action, geopolitics_overlay)
    if geopolitics_constraint:
        operation_parts.append(geopolitics_constraint)
    next_watch_items = card.get("next_watch_items") if isinstance(card.get("next_watch_items"), list) else []
    if next_watch_items:
        operation_parts.append(clean_text(next_watch_items[0]))
    flow_card = {
        "ticker": ticker,
        "name": clean_text(card.get("name")) or ticker,
        "action": action,
        "status": clean_text(card.get("status")) or clean_text(card.get("midday_status")),
        "score": score,
        "keep_threshold": keep_threshold,
        "gap": gap,
        "keep_threshold_gap": gap,
        "chain_name": chain_name,
        "chain_role": chain_role,
        "trading_profile_bucket": trading_profile_bucket,
        "trigger_overrides": None,
        "conclusion": conclusion,
        "watch_points": {
            "technical": technical_summary,
            "event": "；".join(event_bits),
            "chain": chain_summary,
        },
        "triggers": {
            "upgrade": build_upgrade_trigger(card, keep_threshold),
            "downgrade": build_downgrade_trigger(card),
        },
        "operation_reminder": " ".join(part for part in operation_parts if part),
    }
    event_risk = build_event_risk_trigger({**event_context, **card})
    if event_risk:
        flow_card["triggers"]["event_risk"] = event_risk
    return flow_card


def build_decision_flow(enriched: dict[str, Any]) -> list[dict[str, Any]]:
    decision_factors = enriched.get("decision_factors")
    if not isinstance(decision_factors, dict):
        decision_factors = build_decision_factors_from_result(enriched)
    keep_threshold = None
    filter_summary = enriched.get("filter_summary")
    if isinstance(filter_summary, dict) and filter_summary.get("keep_threshold") not in (None, ""):
        keep_threshold = float(filter_summary.get("keep_threshold"))

    event_card_map = {
        clean_text(item.get("ticker")): item
        for item in enriched.get("event_cards", [])
        if isinstance(item, dict) and clean_text(item.get("ticker"))
    }
    chain_entry_map = {
        clean_text(item.get("chain_name")): item
        for item in enriched.get("chain_map_entries", [])
        if isinstance(item, dict) and clean_text(item.get("chain_name"))
    }
    request_obj = enriched.get("request")
    geopolitics_overlay = (
        request_obj.get("macro_geopolitics_overlay")
        if isinstance(request_obj, dict) and isinstance(request_obj.get("macro_geopolitics_overlay"), dict)
        else None
    )
    ordered: list[dict[str, Any]] = []
    section_order = ("qualified", "near_miss", "blocked")
    for key in section_order:
        rows = decision_factors.get(key, [])
        if not isinstance(rows, list):
            continue
        sorted_rows = sorted(
            [item for item in rows if isinstance(item, dict)],
            key=lambda item: float(item.get("score") or 0.0),
            reverse=(key == "near_miss"),
        )
        for item in sorted_rows:
            event_card = event_card_map.get(clean_text(item.get("ticker")))
            chain_entry = None
            if isinstance(event_card, dict):
                chain_entry = chain_entry_map.get(clean_text(event_card.get("chain_name")))
            ordered.append(
                build_decision_flow_card(
                    item,
                    keep_threshold=keep_threshold,
                    event_card=event_card,
                    chain_entry=chain_entry,
                    geopolitics_overlay=geopolitics_overlay,
                )
            )
    return ordered


def build_geopolitics_candidate_summary_lines(
    candidate: dict[str, Any] | None,
    overlay: dict[str, Any] | None = None,
) -> list[str]:
    if not isinstance(candidate, dict):
        return []

    regime = clean_text(candidate.get("candidate_regime")) or "insufficient_signal"
    confidence = clean_text(candidate.get("confidence")) or "low"
    signal_alignment = clean_text(candidate.get("signal_alignment")) or "mixed"
    status = clean_text(candidate.get("status")) or "candidate_only"
    status_text = {
        "candidate_only": "候选判断，尚未写入正式 overlay",
        "accepted_as_overlay": "候选已被采纳为正式 overlay",
        "conflicts_with_overlay": "候选与正式 overlay 不一致",
        "insufficient_signal": "当前多源信号不足以形成稳定候选",
    }.get(status, "候选判断，尚未写入正式 overlay")

    lines = [
        f"- 地缘候选判断：`{regime}`（{confidence}）",
        f"- 信号对齐：{signal_alignment}",
        f"- 状态：{status_text}",
    ]
    overlay_regime = clean_text((overlay or {}).get("regime_label"))
    if overlay_regime:
        lines.append(f"- 正式 overlay：`{overlay_regime}`")
    return lines


def build_decision_flow_markdown(
    decision_flow: list[dict[str, Any]],
    geopolitics_overlay: dict[str, Any] | None = None,
    geopolitics_candidate: dict[str, Any] | None = None,
) -> list[str]:
    lines = ["", "## 决策流", ""]
    regime = clean_text((geopolitics_overlay or {}).get("regime_label"))
    if regime in GEOPOLITICS_REGIME_LABELS:
        lines.append(f"- 地缘 regime: `{regime}`")
        confidence = clean_text((geopolitics_overlay or {}).get("confidence"))
        headline_risk = clean_text((geopolitics_overlay or {}).get("headline_risk"))
        meta_bits: list[str] = []
        if confidence:
            meta_bits.append(f"confidence=`{confidence}`")
        if headline_risk:
            meta_bits.append(f"headline_risk=`{headline_risk}`")
        if meta_bits:
            lines.append(f"- {' | '.join(meta_bits)}")
        lines.append("")
    candidate_lines = build_geopolitics_candidate_summary_lines(
        geopolitics_candidate,
        geopolitics_overlay,
    )
    if candidate_lines:
        lines.extend(candidate_lines)
        lines.append("")
    for item in decision_flow:
        lines.append(
            f"### {item.get('ticker')} | {item.get('action')} | {item.get('score')}分 | {item.get('trading_profile_bucket')}"
        )
        lines.append("")
        lines.append(f"- 结论：{item.get('conclusion')}")
        lines.append("- 盘中观察点：")
        watch_points = item.get("watch_points") if isinstance(item.get("watch_points"), dict) else {}
        lines.append(f"  - 技术：{watch_points.get('technical', '技术形态证据不足。')}")
        lines.append(f"  - 事件：{watch_points.get('event', '事件证据不足。')}")
        lines.append(f"  - 链条：{watch_points.get('chain', '链条共振证据不足。')}")
        lines.append("- 触发条件：")
        triggers = item.get("triggers") if isinstance(item.get("triggers"), dict) else {}
        lines.append(f"  - ↑ upgrade：{triggers.get('upgrade', '等待更多确认。')}")
        lines.append(f"  - ↓ downgrade：{triggers.get('downgrade', '若验证转弱则降级。')}")
        if clean_text(triggers.get("event_risk")):
            lines.append(f"  - ⚡ event risk：{triggers.get('event_risk')}")
        lines.append(f"- 操作提醒：{item.get('operation_reminder')}")
        lines.append("")
    return lines


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


def enrich_event_cards_with_chain_context(event_cards: list[dict[str, Any]], discovery_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(discovery_context, dict):
        return event_cards
    chain_map = discovery_context.get("chain_map") if isinstance(discovery_context.get("chain_map"), list) else []
    if not chain_map:
        return event_cards
    chain_lookup = {
        clean_text(item.get("chain_name")): item
        for item in chain_map
        if isinstance(item, dict) and clean_text(item.get("chain_name"))
    }
    membership_lookup: dict[str, str] = {}
    for item in chain_map:
        if not isinstance(item, dict):
            continue
        chain_name = clean_text(item.get("chain_name"))
        for name in unique_strings(
            list(item.get("all_candidates") or [])
            + list(item.get("leaders") or [])
            + list(item.get("tier_1") or [])
            + list(item.get("tier_2") or [])
        ):
            membership_lookup.setdefault(name, chain_name)
    enriched_cards: list[dict[str, Any]] = []
    for card in event_cards:
        if not isinstance(card, dict):
            continue
        enriched_card = deepcopy(card)
        current_chain_name = clean_text(card.get("chain_name"))
        card_name = clean_text(card.get("name")) or clean_text(card.get("ticker"))
        current_context = chain_lookup.get(current_chain_name)
        if isinstance(current_context, dict):
            current_known_names = unique_strings(
                list(current_context.get("all_candidates") or [])
                + list(current_context.get("leaders") or [])
                + list(current_context.get("tier_1") or [])
                + list(current_context.get("tier_2") or [])
            )
        else:
            current_known_names = []
        if card_name and card_name not in current_known_names:
            fallback_chain_name = membership_lookup.get(card_name)
            if fallback_chain_name:
                enriched_card["chain_name"] = fallback_chain_name
                current_chain_name = fallback_chain_name
        context = chain_lookup.get(current_chain_name)
        if isinstance(context, dict):
            enriched_card["leaders"] = unique_strings(list(enriched_card.get("leaders", [])) + list(context.get("leaders", [])))
            enriched_card["peer_tier_1"] = unique_strings(list(enriched_card.get("peer_tier_1", [])) + list(context.get("tier_1", [])))
            enriched_card["peer_tier_2"] = unique_strings(list(enriched_card.get("peer_tier_2", [])) + list(context.get("tier_2", [])))
            enriched_card["chain_path_summary"] = build_chain_path_summary(enriched_card)
            trading_profile = classify_trading_profile(enriched_card)
            enriched_card["trading_profile_bucket"] = trading_profile["bucket"]
            enriched_card["trading_profile_subtype"] = trading_profile["subtype"]
            enriched_card["trading_profile_reason"] = trading_profile["reason"]
            enriched_card["trading_profile_playbook"] = build_trading_profile_playbook(enriched_card)
            enriched_card["trading_profile_judgment"] = build_trading_profile_judgment(enriched_card)
            enriched_card["trading_profile_usage"] = build_trading_profile_usage(enriched_card)
        enriched_cards.append(enriched_card)
    return enriched_cards


def build_chain_map_entries(event_cards: list[dict[str, Any]], discovery_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = discovery_context.get("chain_map") if isinstance(discovery_context, dict) and isinstance(discovery_context.get("chain_map"), list) else []

    chain_has_strong_validation: dict[str, bool] = {}
    for card in (event_cards if isinstance(event_cards, list) else []):
        if not isinstance(card, dict):
            continue
        chain_name = clean_text(card.get("chain_name"))
        if not chain_name:
            continue
        validation_label = clean_text((card.get("market_validation_summary") or {}).get("label"))
        if validation_label == "strong":
            chain_has_strong_validation[chain_name] = True

    grouped: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        chain_name = clean_text(item.get("chain_name"))
        if not chain_name:
            continue
        leaders = unique_strings(item.get("leaders") or [])
        tier_1 = unique_strings(item.get("tier_1") or [])
        tier_2 = unique_strings(item.get("tier_2") or [])
        has_strong = chain_has_strong_validation.get(chain_name, False)
        high_beta_candidates = [name for name in tier_1 if name not in leaders]
        if has_strong:
            high_beta = high_beta_candidates
            catchup = tier_2
        else:
            high_beta = []
            catchup = unique_strings(high_beta_candidates + tier_2)
        profiles = {
            "稳健核心": leaders,
            "高弹性": high_beta,
            "补涨候选": catchup,
            "预期差最大": [],
            "兑现风险最高": [],
        }
        grouped[chain_name] = {
            "chain_name": chain_name,
            "profiles": profiles,
            "chain_playbook": build_chain_map_playbook(profiles),
            "anchors": [],
        }
    for card in event_cards:
        if not isinstance(card, dict):
            continue
        chain_name = clean_text(card.get("chain_name"))
        if not chain_name:
            continue
        row = grouped.setdefault(
            chain_name,
            {"chain_name": chain_name, "profiles": {bucket: [] for bucket in TRADING_PROFILE_BUCKETS}, "anchors": []},
        )
        anchor_name = clean_text(card.get("name")) or clean_text(card.get("ticker"))
        if anchor_name and anchor_name not in row["anchors"]:
            row["anchors"].append(anchor_name)
        bucket = clean_text(card.get("trading_profile_bucket"))
        profiles = row.setdefault("profiles", {bucket_name: [] for bucket_name in TRADING_PROFILE_BUCKETS})
        for profile_names in profiles.values():
            if anchor_name in profile_names:
                profile_names[:] = [name for name in profile_names if name != anchor_name]
        if anchor_name and bucket in profiles:
            profiles[bucket] = unique_strings(list(profiles[bucket]) + [anchor_name])
        row["chain_playbook"] = build_chain_map_playbook(profiles)
    return list(grouped.values())


def build_chain_map_playbook(profiles: dict[str, list[str]] | None) -> str:
    profile_map = profiles if isinstance(profiles, dict) else {}
    core = profile_map.get("稳健核心") if isinstance(profile_map.get("稳健核心"), list) else []
    elastic = profile_map.get("高弹性") if isinstance(profile_map.get("高弹性"), list) else []
    catchup = profile_map.get("补涨候选") if isinstance(profile_map.get("补涨候选"), list) else []
    expectation_gap = profile_map.get("预期差最大") if isinstance(profile_map.get("预期差最大"), list) else []
    realized_risk = profile_map.get("兑现风险最高") if isinstance(profile_map.get("兑现风险最高"), list) else []

    if realized_risk and core:
        return "链条打法: 核心票已经进入兑现窗口，先防 sell-the-fact，再看后排轮动。"
    if realized_risk:
        return "链条打法: 当前先防兑现风险，不适合把这条链当作新开仓主攻方向。"
    if core and elastic:
        return "链条打法: 先看核心承载，再择机做高弹性进攻。"
    if core and catchup:
        return "链条打法: 先盯核心承载，再等轮动补涨。"
    if elastic:
        return "链条打法: 当前更适合按高弹性方向进攻，重点看加速与回踩二选一。"
    if catchup:
        return "链条打法: 当前更适合按轮动补涨处理，关注主线继续扩散而不是孤立抢跑。"
    if core:
        return "链条打法: 当前以核心承载为主，优先等回踩确认而不是情绪化追高。"
    if expectation_gap:
        return "链条打法: 当前更适合先观察预期定价，等市场把预期交易得更清楚。"
    return "链条打法: 当前缺少清晰主攻方向，先观察链内强弱分化。"


def apply_rendered_caps(
    tiers: dict[str, list[dict[str, Any]]],
    tier_caps: dict[str, int] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """
    Enforce per-tier caps. Overflow candidates get [tier_cap_overflow] tag
    and are removed from rendered tiers but kept in diagnostic scorecard.

    Returns: (capped_tiers, overflow_list)
    """
    caps = tier_caps or TIER_CAPS
    overflow: list[dict[str, Any]] = []
    capped: dict[str, list[dict[str, Any]]] = {}
    for tier_name, candidates in tiers.items():
        cap = caps.get(tier_name, 10)
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.get("adjusted_total_score", 0),
            reverse=True,
        )
        capped[tier_name] = sorted_candidates[:cap]
        for c in sorted_candidates[cap:]:
            c["tier_tags"] = c.get("tier_tags", []) + ["tier_cap_overflow"]
            overflow.append(c)
    return capped, overflow


def apply_total_rendered_cap(
    tiers: dict[str, list[dict[str, Any]]],
    *,
    total_cap: int | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Apply a final merged-tier display budget across T1/T2/T3/T4.

    Preserves tier priority by consuming the budget in T1 -> T2 -> T3 -> T4
    order, while sorting candidates within each tier by score descending.
    """
    budget = TOTAL_RENDERED_CAP if total_cap is None else int(total_cap)
    remaining = max(budget, 0)
    capped: dict[str, list[dict[str, Any]]] = {}
    overflow: list[dict[str, Any]] = []
    for tier_name in ("T1", "T2", "T3", "T4"):
        candidates = sorted(
            list(tiers.get(tier_name, [])),
            key=lambda x: x.get("score", x.get("adjusted_total_score", 0)),
            reverse=True,
        )
        if remaining <= 0:
            capped[tier_name] = []
            for c in candidates:
                c["tier_tags"] = c.get("tier_tags", []) + ["total_rendered_cap_overflow"]
                overflow.append(c)
            continue
        kept = candidates[:remaining]
        capped[tier_name] = kept
        for c in candidates[remaining:]:
            c["tier_tags"] = c.get("tier_tags", []) + ["total_rendered_cap_overflow"]
            overflow.append(c)
        remaining -= len(kept)
    return capped, overflow


def enrich_live_result_reporting(
    result: dict[str, Any],
    failure_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]] | None = None,
    discovery_candidates: list[dict[str, Any]] | None = None,
    discovery_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = enrich_degraded_live_result(result, failure_candidates)
    request_obj = enriched.get("request") if isinstance(enriched.get("request"), dict) else {}
    geopolitics_candidate_input = (
        request_obj.get("macro_geopolitics_candidate_input")
        if isinstance(request_obj.get("macro_geopolitics_candidate_input"), dict)
        else None
    )
    enriched["macro_geopolitics_candidate"] = build_macro_geopolitics_candidate(
        geopolitics_candidate_input
    )
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
        # Apply board-specific threshold overrides before near-miss / tier logic
        active_profile = clean_text(
            filter_summary.get("profile")
            or filter_summary.get("filter_profile")
            or request_obj.get("filter_profile")
        )
        geopolitics_overlay = request_obj.get("macro_geopolitics_overlay")
        base_keep = float(filter_summary.get("keep_threshold", 60.0))
        diagnostic_scorecard, board_thresholds = apply_board_threshold_overrides(
            diagnostic_scorecard, active_profile, base_keep,
        )
        if board_thresholds:
            filter_summary["board_thresholds"] = board_thresholds
            enriched["filter_summary"] = filter_summary

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

    auto_discovery_candidates = build_auto_discovery_candidates(assessed_candidates or [])
    discovery_rows = build_discovery_candidates(
        merge_discovery_candidate_inputs(list(discovery_candidates or []), auto_discovery_candidates)
    )
    if discovery_rows:
        event_cards = enrich_event_cards_with_chain_context(build_event_cards(discovery_rows), discovery_context)
        enriched["event_cards"] = event_cards
        enriched["discovery_lane_summary"] = build_discovery_lane_summary(event_cards)
        enriched["chain_map_entries"] = build_chain_map_entries(event_cards, discovery_context)
        enriched["directly_actionable"] = [row for row in event_cards if row.get("discovery_bucket") == "qualified"][:MAX_REPORTED_TOP_PICKS]
        enriched["priority_watchlist"] = [row for row in event_cards if row.get("discovery_bucket") == "watch"][:MAX_REPORTED_NEAR_MISS]
        enriched["chain_tracking"] = [row for row in event_cards if row.get("discovery_bucket") not in {"qualified", "watch"}][:MAX_REPORTED_BLOCKED]

    midday_action_summary = build_midday_action_summary_from_result(enriched)
    if midday_action_summary:
        enriched["midday_action_summary"] = midday_action_summary
    decision_factors = build_decision_factors_from_result(enriched)
    decision_flow: list[dict[str, Any]] = []
    if any(decision_factors.values()):
        enriched["decision_factors"] = decision_factors
        decision_flow = build_decision_flow(enriched)
        enriched["decision_flow"] = decision_flow

    # --- Tier output integration ---
    if diagnostic_scorecard:
        keep_threshold = filter_summary.get("keep_threshold", 60.0)
        top_picks = [item for item in diagnostic_scorecard if item.get("keep")]
        near_miss_candidates_for_tiers = enriched.get("near_miss_candidates", [])
        discovery_results = {
            "qualified": enriched.get("directly_actionable", []),
            "watch": enriched.get("priority_watchlist", []),
            "track": enriched.get("chain_tracking", []),
        }
        tiers = assign_tiers(
            top_picks, near_miss_candidates_for_tiers,
            discovery_results, diagnostic_scorecard, keep_threshold,
            geopolitics_overlay=geopolitics_overlay if isinstance(geopolitics_overlay, dict) else None,
        )
        capped_tiers, overflow = apply_rendered_caps(tiers)
        enriched["tier_output"] = {
            tier_name: [
                {
                    "ticker": clean_text(c.get("ticker")),
                    "name": clean_text(c.get("name")),
                    "score": c.get("score") or c.get("adjusted_total_score"),
                    "wrapper_tier": c.get("wrapper_tier"),
                    "tier_tags": c.get("tier_tags", []),
                }
                for c in candidates
            ]
            for tier_name, candidates in capped_tiers.items()
        }
        enriched["tier_metadata"] = {
            "total_rendered": sum(len(v) for v in capped_tiers.values()),
            "overflow_count": len(overflow),
            "floor_policy_applied": any(
                "coverage_fill" in c.get("tier_tags", [])
                for tier in capped_tiers.values() for c in tier
            ),
            "profile_used": str(filter_summary.get("profile", "default")),
        }

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

    # --- T2 事件驱动 section ---
    tier_output = enriched.get("tier_output", {})
    t2_candidates = tier_output.get("T2", [])
    if t2_candidates and "## T2 事件驱动" not in "\n".join(lines):
        lines.extend(["", "## T2 事件驱动", ""])
        lines.append("| 标的 | 分数 | 事件信号 | 来源 |")
        lines.append("|---|---|---|---|")
        for item in t2_candidates:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            score = item.get("score", "")
            tags = ", ".join(item.get("tier_tags", []))
            lines.append(f"| `{ticker}` {name} | {score} | {tags} | T2 |")

    directly_actionable = enriched.get("directly_actionable", [])
    if isinstance(directly_actionable, list) and directly_actionable and "## 直接可执行" not in "\n".join(lines):
        lines.extend(["", "## 直接可执行", ""])
        for item in directly_actionable:
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            lines.append(f"  - 事件: `{item.get('event_type')}`")
            lines.append(f"  - 事件状态: `{item.get('event_state', {}).get('label')}`")
            lines.append(f"  - 链条: `{item.get('chain_name')}` / `{item.get('chain_role')}`")
            lines.append(f"  - 市场验证: {item.get('market_validation_summary', {}).get('summary')}")
            lines.append(f"  - 交易可用性: {item.get('trading_usability', {}).get('summary')}")

    priority_watchlist = enriched.get("priority_watchlist", [])
    if isinstance(priority_watchlist, list) and priority_watchlist and "## 重点观察" not in "\n".join(lines):
        lines.extend(["", "## 重点观察", ""])
        for item in priority_watchlist:
            confidence = item.get("rumor_confidence_range", {})
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            lines.append(f"  - 事件: `{item.get('event_type')}`")
            lines.append(f"  - 事件状态: `{item.get('event_state', {}).get('label')}`")
            lines.append(f"  - 可信度区间: `{confidence.get('label')}` `{confidence.get('range')}`")
            lines.append(f"  - 链条: `{item.get('chain_name')}` / `{item.get('chain_role')}`")
            lines.append(f"  - 交易可用性: {item.get('trading_usability', {}).get('summary')}")

    chain_tracking = enriched.get("chain_tracking", [])
    if isinstance(chain_tracking, list) and chain_tracking and "## 链条跟踪" not in "\n".join(lines):
        lines.extend(["", "## 链条跟踪", ""])
        for item in chain_tracking:
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}: `{item.get('chain_name')}` / `{item.get('chain_role')}`")
            lines.append(f"  - 事件状态: `{item.get('event_state', {}).get('label')}`")
            lines.append(f"  - 交易可用性: {item.get('trading_usability', {}).get('summary')}")

    event_cards = enriched.get("event_cards", [])
    if decision_flow and "## 决策流" not in "\n".join(lines):
        geopolitics_overlay = request_obj.get("macro_geopolitics_overlay") if isinstance(request_obj.get("macro_geopolitics_overlay"), dict) else None
        geopolitics_candidate = enriched.get("macro_geopolitics_candidate") if isinstance(enriched.get("macro_geopolitics_candidate"), dict) else None
        lines.extend(build_decision_flow_markdown(decision_flow, geopolitics_overlay, geopolitics_candidate))
    if isinstance(event_cards, list) and event_cards and "## Event Cards" not in "\n".join(lines):
        lines.extend(["", "## Event Cards", ""])
        for item in event_cards:
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            lines.append(f"  - 阶段: `{item.get('event_phase')}`")
            lines.append(f"  - 预期判断: `{item.get('expectation_verdict')}`")
            lines.append(f"  - {item.get('trading_profile_judgment')}")
            lines.append(f"  - {item.get('trading_profile_usage')}")
            metrics = item.get("headline_metrics") if isinstance(item.get("headline_metrics"), list) else []
            if metrics:
                lines.append(f"  - 关键数据: `{', '.join(metrics[:4])}`")
            lines.append(f"  - 社区反应: {item.get('community_reaction_summary')}")
            lines.append(f"  - 社区一致性: `{item.get('community_conviction')}`")
            lines.append(f"  - 预期驱动: {item.get('expectation_basis_summary')}")
            lines.append(f"  - 兑现风险: {item.get('expectation_risk_summary')}")
            lines.append(f"  - primary_event_type: `{item.get('primary_event_type')}`")
            lines.append(f"  - priority_score: `{item.get('priority_score')}`")
            lines.append(f"  - why_now: `{item.get('why_now')}`")
            lines.append(f"  - chain_path_summary: `{item.get('chain_path_summary')}`")
            lines.append(f"  - market_signal_summary: `{item.get('market_signal_summary')}`")
            lines.append(f"  - source_count: `{item.get('source_count')}`")
            lines.append(f"  - source_accounts: `{', '.join(item.get('source_accounts', [])) or 'none'}`")
            lines.append(f"  - source_urls: `{', '.join(item.get('source_urls', [])) or 'none'}`")
            lines.append(f"  - evidence_mix: `{json.dumps(item.get('evidence_mix', {}), ensure_ascii=False, sort_keys=True)}`")
            lines.append(f"  - event_state: `{item.get('event_state', {}).get('label')}`")
            lines.append(f"  - trading_usability: `{item.get('trading_usability', {}).get('label')}`")
            key_evidence = item.get("key_evidence") if isinstance(item.get("key_evidence"), list) else []
            if key_evidence:
                lines.append("  - key_evidence:")
                for bullet in key_evidence[:MAX_REPORTED_WATCH_ITEMS]:
                    lines.append(f"    - {bullet}")
    enriched["report_markdown"] = "\n".join(lines).strip() + "\n"
    return enriched


# ---------------------------------------------------------------------------
# Multi-track pipeline helpers
# ---------------------------------------------------------------------------

def enrich_track_result(
    result: dict[str, Any],
    failure_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]] | None = None,
    *,
    track_name: str = "",
    track_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich a single track's compiled-runtime result.

    Similar to ``enrich_live_result_reporting`` but uses the track's own
    keep_threshold and tier_caps instead of applying board overrides.
    Discovery / event-card enrichment is intentionally omitted here; it
    is handled once in ``merge_track_results`` across all tracks.
    """
    cfg = track_config or {}
    enriched = enrich_degraded_live_result(result, failure_candidates)
    dropped = [item for item in enriched.get("dropped", []) if isinstance(item, dict)]

    filter_summary = dict(enriched.get("filter_summary") or {})
    keep_threshold = float(cfg.get("keep_threshold") or filter_summary.get("keep_threshold", 60.0))
    # Override filter_summary thresholds with track config
    filter_summary["keep_threshold"] = keep_threshold
    filter_summary["strict_top_pick_threshold"] = float(
        cfg.get("strict_top_pick_threshold") or filter_summary.get("strict_top_pick_threshold", 62.0)
    )
    if track_name:
        filter_summary["track_name"] = track_name
        filter_summary["track_label"] = cfg.get("label", track_name)

    if dropped:
        drop_reason_counts: dict[str, int] = {}
        for item in dropped:
            for reason in split_drop_reasons(item.get("drop_reason")):
                drop_reason_counts[reason] = drop_reason_counts.get(reason, 0) + 1
        if drop_reason_counts:
            filter_summary["drop_reason_counts"] = drop_reason_counts
    enriched["filter_summary"] = filter_summary

    diagnostic_scorecard = [
        build_diagnostic_scorecard_entry(item, keep_threshold)
        for item in (assessed_candidates or [])
        if isinstance(item, dict)
    ]
    if diagnostic_scorecard:
        active_profile = clean_text(
            filter_summary.get("profile")
            or filter_summary.get("filter_profile")
            or (enriched.get("request") or {}).get("filter_profile")
        )
        geopolitics_overlay = (enriched.get("request") or {}).get("macro_geopolitics_overlay")
        # No board overrides needed — each track already has the correct threshold
        near_miss_candidates = build_near_miss_candidates(diagnostic_scorecard)
        waiver_candidates = apply_catalyst_waiver(
            diagnostic_scorecard, active_profile, keep_threshold,
        )
        if waiver_candidates:
            near_miss_by_ticker = {
                clean_text(item.get("ticker")): item for item in near_miss_candidates
            }
            for item in waiver_candidates:
                ticker = clean_text(item.get("ticker"))
                if not ticker or ticker in near_miss_by_ticker:
                    continue
                near_miss_candidates.append(item)
                near_miss_by_ticker[ticker] = item
        near_miss_tickers = {clean_text(item.get("ticker")) for item in near_miss_candidates}
        for item in diagnostic_scorecard:
            item["midday_status"] = classify_midday_status(item, near_miss_tickers)
            item["track_name"] = track_name
        filter_summary["diagnostic_scorecard_count"] = len(diagnostic_scorecard)
        enriched["filter_summary"] = filter_summary
        enriched["diagnostic_scorecard"] = diagnostic_scorecard
        enriched["midday_action_summary"] = build_midday_action_summary(diagnostic_scorecard)
        if near_miss_candidates:
            for item in near_miss_candidates:
                item["midday_status"] = classify_midday_status(item, near_miss_tickers)
                item["track_name"] = track_name
            filter_summary["near_miss_candidate_count"] = len(near_miss_candidates)
            enriched["filter_summary"] = filter_summary
            enriched["near_miss_candidates"] = near_miss_candidates

        # Tier assignment with track-specific caps
        top_picks = [item for item in diagnostic_scorecard if item.get("keep")]
        enriched["top_picks"] = top_picks
        filter_summary["universe_count"] = len(diagnostic_scorecard) + len(dropped)
        filter_summary["kept_count"] = len(top_picks)
        filter_summary["top_pick_count"] = len(top_picks)
        enriched["filter_summary"] = filter_summary
        near_miss_for_tiers = enriched.get("near_miss_candidates", [])
        # Discovery results are empty at track level — merged later
        discovery_results: dict[str, list[dict[str, Any]]] = {"qualified": [], "watch": [], "track": []}
        tiers = assign_tiers(
            top_picks, near_miss_for_tiers,
            discovery_results, diagnostic_scorecard, keep_threshold,
            geopolitics_overlay=geopolitics_overlay if isinstance(geopolitics_overlay, dict) else None,
        )
        tiers = apply_floor_policy(
            tiers,
            diagnostic_scorecard,
            discovery_results,
            keep_threshold,
        )
        track_tier_caps = cfg.get("tier_caps", TIER_CAPS)
        capped_tiers, overflow = apply_rendered_caps(tiers, tier_caps=track_tier_caps)
        enriched["tier_output"] = {
            tier_name: [
                {
                    "ticker": clean_text(c.get("ticker")),
                    "name": clean_text(c.get("name")),
                    "score": c.get("score") or c.get("adjusted_total_score"),
                    "wrapper_tier": c.get("wrapper_tier"),
                    "tier_tags": c.get("tier_tags", []),
                    "track_name": track_name,
                }
                for c in candidates
            ]
            for tier_name, candidates in capped_tiers.items()
        }
        enriched["tier_metadata"] = {
            "total_rendered": sum(len(v) for v in capped_tiers.values()),
            "overflow_count": len(overflow),
            "floor_policy_applied": any(
                "coverage_fill" in c.get("tier_tags", [])
                for tier in capped_tiers.values() for c in tier
            ),
            "track_name": track_name,
        }

    enriched["_track_name"] = track_name
    enriched["_track_config"] = cfg
    return enriched


def _build_track_report_section(
    track_name: str,
    track_config: dict[str, Any],
    enriched: dict[str, Any],
) -> list[str]:
    """Build markdown lines for a single track's section in the report."""
    label = track_config.get("label", track_name)
    lines: list[str] = [f"## {label} ({track_name})"]

    top_picks = enriched.get("top_picks", [])
    if isinstance(top_picks, list) and top_picks:
        lines.extend(["", "### Top Picks", ""])
        for item in top_picks:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            lines.append(f"- `{ticker}` {name}")
    else:
        lines.extend(["", "### Top Picks", "", "- None"])

    dropped = [item for item in enriched.get("dropped", []) if isinstance(item, dict)]
    if dropped:
        lines.extend(["", "### Dropped Candidates", ""])
        for item in dropped:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            reason = clean_text(item.get("drop_reason")) or "dropped"
            lines.append(f"- `{ticker}` {name}: `{reason}`")

    diagnostic_scorecard = enriched.get("diagnostic_scorecard", [])
    if diagnostic_scorecard:
        lines.extend(["", "### Diagnostic Scorecard", ""])
        for item in diagnostic_scorecard:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            failures = ",".join(item.get("hard_filter_failures", [])) if isinstance(item.get("hard_filter_failures"), list) else clean_text(item.get("hard_filter_failures"))
            components = item.get("diagnostic_components") if isinstance(item.get("diagnostic_components"), dict) else {}
            component_summary = " / ".join(
                f"{lbl}=`{components[lbl]}`"
                for lbl in ("trend", "rs", "catalyst", "liquidity")
                if components.get(lbl) not in (None, "")
            )
            lines.append(
                f"- `{ticker}` {name}: status=`{item.get('midday_status')}` score=`{score}` gap=`{gap}`"
                + (f" {component_summary}" if component_summary else "")
                + f" failures=`{failures or 'none'}`"
            )

    near_miss_candidates = enriched.get("near_miss_candidates", [])
    if isinstance(near_miss_candidates, list) and near_miss_candidates:
        lines.extend(["", "### Near Miss Candidates", ""])
        for item in near_miss_candidates:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            lines.append(f"- `{ticker}` {name}: status=`{item.get('midday_status')}` score=`{score}` gap=`{gap}`")

    midday_action_summary = enriched.get("midday_action_summary", [])
    if isinstance(midday_action_summary, list) and midday_action_summary:
        lines.extend(["", "### 午盘操作建议摘要", ""])
        for item in midday_action_summary:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            action = clean_text(item.get("action")) or "继续观察"
            score = item.get("score")
            gap = item.get("keep_threshold_gap")
            lines.append(f"- `{ticker}` {name}: `{action}` score=`{score}` gap=`{gap}`")

    return lines


def merge_track_results(
    track_results: dict[str, dict[str, Any]],
    track_configs: dict[str, dict[str, Any]],
    *,
    discovery_candidates: list[dict[str, Any]] | None = None,
    discovery_context: dict[str, Any] | None = None,
    all_assessed: list[dict[str, Any]] | None = None,
    out_of_scope_dropped: list[dict[str, Any]] | None = None,
    base_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge per-track enriched results into a single output dict.

    Produces a unified result with:
    - ``track_results``: the per-track enriched dicts (keyed by track name)
    - ``filter_summary``: merged summary with per-track breakdowns
    - ``diagnostic_scorecard``: combined from all tracks
    - ``dropped``: combined from all tracks + out-of-scope
    - ``top_picks``: combined from all tracks
    - ``report_markdown``: per-track sections + shared discovery section
    - Discovery / event-card enrichment applied once across all tracks
    """
    merged: dict[str, Any] = {}
    merged["track_results"] = track_results
    merged["request"] = base_request or {}
    request_obj = merged["request"] if isinstance(merged.get("request"), dict) else {}
    geopolitics_candidate_input = (
        request_obj.get("macro_geopolitics_candidate_input")
        if isinstance(request_obj.get("macro_geopolitics_candidate_input"), dict)
        else None
    )
    merged["macro_geopolitics_candidate"] = build_macro_geopolitics_candidate(
        geopolitics_candidate_input
    )

    # Combine top_picks, dropped, diagnostic_scorecard, near_miss, midday_action
    all_top_picks: list[dict[str, Any]] = []
    all_dropped: list[dict[str, Any]] = list(out_of_scope_dropped or [])
    all_diagnostic_scorecard: list[dict[str, Any]] = []
    all_near_miss: list[dict[str, Any]] = []
    all_midday_action: list[dict[str, Any]] = []
    combined_tier_output: dict[str, list[dict[str, Any]]] = {"T1": [], "T2": [], "T3": [], "T4": []}

    per_track_summary: dict[str, dict[str, Any]] = {}
    total_universe = 0
    total_kept = 0

    for track_name, enriched in track_results.items():
        cfg = track_configs.get(track_name, {})
        fs = enriched.get("filter_summary", {})
        track_top_picks = enriched.get("top_picks", []) if isinstance(enriched.get("top_picks"), list) else []
        track_dropped = enriched.get("dropped", []) if isinstance(enriched.get("dropped"), list) else []
        track_diagnostic = enriched.get("diagnostic_scorecard", []) if isinstance(enriched.get("diagnostic_scorecard"), list) else []
        universe_count = fs.get("universe_count")
        if universe_count in (None, ""):
            universe_count = len(track_diagnostic) + len(track_dropped)
        top_pick_count = fs.get("top_pick_count")
        if top_pick_count in (None, ""):
            top_pick_count = len(track_top_picks)
        kept_count = fs.get("kept_count")
        if kept_count in (None, ""):
            kept_count = len(track_top_picks)
        per_track_summary[track_name] = {
            "label": cfg.get("label", track_name),
            "keep_threshold": fs.get("keep_threshold"),
            "strict_top_pick_threshold": fs.get("strict_top_pick_threshold"),
            "universe_count": universe_count,
            "kept_count": kept_count,
            "top_pick_count": top_pick_count,
            "diagnostic_scorecard_count": fs.get("diagnostic_scorecard_count", 0),
            "near_miss_candidate_count": fs.get("near_miss_candidate_count", 0),
        }
        total_universe += int(universe_count or 0)
        total_kept += int(kept_count or 0)

        all_top_picks.extend(track_top_picks)
        all_dropped.extend(track_dropped)
        all_diagnostic_scorecard.extend(track_diagnostic)
        all_near_miss.extend(enriched.get("near_miss_candidates", []))
        all_midday_action.extend(enriched.get("midday_action_summary", []))

        tier_output = enriched.get("tier_output", {})
        for tier_name in combined_tier_output:
            combined_tier_output[tier_name].extend(tier_output.get(tier_name, []))

    merged["top_picks"] = all_top_picks
    merged["dropped"] = all_dropped
    merged["diagnostic_scorecard"] = all_diagnostic_scorecard
    merged["near_miss_candidates"] = all_near_miss
    merged["midday_action_summary"] = all_midday_action
    combined_tier_output, merged_overflow = apply_total_rendered_cap(combined_tier_output)
    merged["tier_output"] = combined_tier_output
    merged["filter_summary"] = {
        "universe_count": total_universe,
        "kept_count": total_kept,
        "top_pick_count": len(all_top_picks),
        "per_track": per_track_summary,
        "total_rendered_cap": TOTAL_RENDERED_CAP,
        "merged_overflow_count": len(merged_overflow),
    }

    # --- Discovery / event-card enrichment (shared across tracks) ---
    all_assessed_combined = list(all_assessed or [])
    auto_discovery_candidates = build_auto_discovery_candidates(all_assessed_combined)
    discovery_rows = build_discovery_candidates(
        merge_discovery_candidate_inputs(list(discovery_candidates or []), auto_discovery_candidates)
    )
    if discovery_rows:
        event_cards = enrich_event_cards_with_chain_context(build_event_cards(discovery_rows), discovery_context)
        merged["event_cards"] = event_cards
        merged["discovery_lane_summary"] = build_discovery_lane_summary(event_cards)
        merged["chain_map_entries"] = build_chain_map_entries(event_cards, discovery_context)
        merged["directly_actionable"] = [row for row in event_cards if row.get("discovery_bucket") == "qualified"][:MAX_REPORTED_TOP_PICKS]
        merged["priority_watchlist"] = [row for row in event_cards if row.get("discovery_bucket") == "watch"][:MAX_REPORTED_NEAR_MISS]
        merged["chain_tracking"] = [row for row in event_cards if row.get("discovery_bucket") not in {"qualified", "watch"}][:MAX_REPORTED_BLOCKED]

    # Decision factors & flow (across all tracks)
    decision_factors = build_decision_factors_from_result(merged)
    decision_flow: list[dict[str, Any]] = []
    if any(decision_factors.values()):
        merged["decision_factors"] = decision_factors
        decision_flow = build_decision_flow(merged)
        merged["decision_flow"] = decision_flow

    # --- Report markdown ---
    request_obj = base_request or {}
    target_date = clean_text(request_obj.get("target_date") or request_obj.get("analysis_time") or "")
    profile = clean_text(request_obj.get("filter_profile") or "")
    header_lines = [
        f"# Month-End Shortlist Report: {target_date}",
        "",
        f"- Template: `{clean_text(request_obj.get('template_name') or 'month_end_shortlist')}`",
        f"- Filter profile: `{profile}`",
        f"- Total universe: `{total_universe}`",
        f"- Total kept: `{total_kept}`",
    ]
    for track_name, summary in per_track_summary.items():
        header_lines.append(f"- {summary['label']}: universe=`{summary['universe_count']}` kept=`{summary['kept_count']}` keep_threshold=`{summary['keep_threshold']}`")

    report_lines = header_lines

    # Per-track sections
    for track_name in track_configs:
        enriched = track_results.get(track_name)
        if not enriched:
            continue
        cfg = track_configs[track_name]
        report_lines.append("")
        report_lines.extend(_build_track_report_section(track_name, cfg, enriched))

    # Out-of-scope dropped
    if out_of_scope_dropped:
        report_lines.extend(["", "## Out-of-Scope Dropped", ""])
        for item in out_of_scope_dropped:
            ticker = clean_text(item.get("ticker")) or "unknown"
            name = clean_text(item.get("name")) or ticker
            reason = clean_text(item.get("drop_reason")) or "outside_track_scope"
            report_lines.append(f"- `{ticker}` {name}: `{reason}`")

    # Shared discovery sections
    directly_actionable = merged.get("directly_actionable", [])
    if isinstance(directly_actionable, list) and directly_actionable:
        report_lines.extend(["", "## 直接可执行", ""])
        for item in directly_actionable:
            report_lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            report_lines.append(f"  - 事件: `{item.get('event_type')}`")
            report_lines.append(f"  - 事件状态: `{item.get('event_state', {}).get('label')}`")
            report_lines.append(f"  - 链条: `{item.get('chain_name')}` / `{item.get('chain_role')}`")

    priority_watchlist = merged.get("priority_watchlist", [])
    if isinstance(priority_watchlist, list) and priority_watchlist:
        report_lines.extend(["", "## 重点观察", ""])
        for item in priority_watchlist:
            confidence = item.get("rumor_confidence_range", {})
            report_lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            report_lines.append(f"  - 事件: `{item.get('event_type')}`")
            report_lines.append(f"  - 事件状态: `{item.get('event_state', {}).get('label')}`")
            report_lines.append(f"  - 可信度区间: `{confidence.get('label')}` `{confidence.get('range')}`")

    chain_tracking = merged.get("chain_tracking", [])
    if isinstance(chain_tracking, list) and chain_tracking:
        report_lines.extend(["", "## 链条跟踪", ""])
        for item in chain_tracking:
            report_lines.append(f"- `{item.get('ticker')}` {item.get('name')}: `{item.get('chain_name')}` / `{item.get('chain_role')}`")

    if decision_flow:
        geopolitics_overlay = request_obj.get("macro_geopolitics_overlay") if isinstance(request_obj.get("macro_geopolitics_overlay"), dict) else None
        geopolitics_candidate = merged.get("macro_geopolitics_candidate") if isinstance(merged.get("macro_geopolitics_candidate"), dict) else None
        report_lines.extend(build_decision_flow_markdown(decision_flow, geopolitics_overlay, geopolitics_candidate))

    event_cards = merged.get("event_cards", [])
    if isinstance(event_cards, list) and event_cards:
        report_lines.extend(["", "## Event Cards", ""])
        for item in event_cards:
            report_lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            report_lines.append(f"  - 阶段: `{item.get('event_phase')}`")
            report_lines.append(f"  - 预期判断: `{item.get('expectation_verdict')}`")
            report_lines.append(f"  - {item.get('trading_profile_judgment')}")
            report_lines.append(f"  - {item.get('trading_profile_usage')}")
            metrics = item.get("headline_metrics") if isinstance(item.get("headline_metrics"), list) else []
            if metrics:
                report_lines.append(f"  - 关键数据: `{', '.join(metrics[:4])}`")
            report_lines.append(f"  - primary_event_type: `{item.get('primary_event_type')}`")
            report_lines.append(f"  - event_state: `{item.get('event_state', {}).get('label')}`")
            report_lines.append(f"  - trading_usability: `{item.get('trading_usability', {}).get('label')}`")

    merged["report_markdown"] = "\n".join(report_lines).strip() + "\n"
    return merged


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
    """Multi-track month-end shortlist pipeline.

    1. Normalize and prepare the request (shared).
    2. Split the universe by board into independent tracks.
    3. Run the compiled core + per-track enrichment for each track.
    4. Merge track results with shared discovery/event enrichment.
    """
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
        safe_bars = wrap_bars_fetcher_with_benchmark_fallback(bars_fetcher)
        prepared_payload = prepare_request_with_candidate_snapshots(
            normalize_request_with_compiled(raw_payload, original_normalize_request),
            bars_fetcher=safe_bars,
        )
        discovery_candidates = deepcopy(prepared_payload.get("event_discovery_candidates") or [])
        discovery_context = deepcopy(prepared_payload.get("x_discovery_context") or {})

        # --- Fetch full universe once, then split by board ---
        full_universe = universe_fetcher(prepared_payload)
        board_to_track: dict[str, str] = {}
        for tn, cfg in TRACK_CONFIGS.items():
            for bv in cfg.get("board_values", ()):
                board_to_track[bv] = tn

        track_universes: dict[str, list[dict[str, Any]]] = {tn: [] for tn in TRACK_CONFIGS}
        out_of_scope: list[dict[str, Any]] = []
        for candidate in full_universe:
            ticker = str(candidate.get("ticker") or candidate.get("f12") or "").strip()
            board = _compiled.classify_board(ticker)
            tn = board_to_track.get(board)
            if tn:
                track_universes[tn].append(candidate)
            else:
                out_of_scope.append({
                    "ticker": ticker,
                    "name": str(candidate.get("name") or candidate.get("f14") or ticker),
                    "board": board,
                    "drop_reason": "outside_track_scope",
                })

        # --- Run each track independently ---
        track_results: dict[str, dict[str, Any]] = {}
        all_assessed: list[dict[str, Any]] = []
        for track_name, track_cfg in TRACK_CONFIGS.items():
            track_universe = track_universes[track_name]
            # Build a frozen universe_fetcher that returns only this track's candidates
            def make_track_fetcher(candidates: list[dict[str, Any]]):
                def fetcher(request: dict[str, Any]) -> list[dict[str, Any]]:
                    return candidates
                return fetcher

            # Build per-track payload with track-specific thresholds
            track_payload = deepcopy(prepared_payload)
            track_payload["keep_threshold"] = track_cfg["keep_threshold"]
            track_payload["strict_top_pick_threshold"] = track_cfg["strict_top_pick_threshold"]
            profile_settings = dict(track_payload.get("profile_settings") or {})
            profile_settings["keep_threshold"] = track_cfg["keep_threshold"]
            profile_settings["strict_top_pick_threshold"] = track_cfg["strict_top_pick_threshold"]
            track_payload["profile_settings"] = profile_settings
            # Tag so monkey-patched normalize_request applies track-specific thresholds
            track_payload["_track_name"] = track_name
            track_payload["_track_config"] = track_cfg

            # Each track gets its own failure/assessed logs
            track_failure_log: list[dict[str, Any]] = []
            track_assessed_log: list[dict[str, Any]] = []
            _compiled.assess_candidate = wrap_assess_candidate_with_bars_failure_fallback(
                original_assess_candidate,
                track_failure_log,
                track_assessed_log,
            )
            result = _compiled.run_month_end_shortlist(
                track_payload,
                universe_fetcher=make_track_fetcher(track_universe),
                bars_fetcher=safe_bars,
                html_fetcher=html_fetcher,
            )
            enriched = enrich_track_result(
                result,
                track_failure_log,
                track_assessed_log,
                track_name=track_name,
                track_config=track_cfg,
            )
            track_results[track_name] = enriched
            all_assessed.extend(track_assessed_log)

        return merge_track_results(
            track_results,
            TRACK_CONFIGS,
            discovery_candidates=discovery_candidates,
            discovery_context=discovery_context,
            all_assessed=all_assessed,
            out_of_scope_dropped=out_of_scope,
            base_request=prepared_payload,
        )
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
    "apply_board_threshold_overrides",
    "BOARD_THRESHOLD_OVERRIDES",
    "build_near_miss_candidates",
    "classify_midday_status",
    "build_midday_action_summary",
    "build_midday_action_summary_from_top_picks",
    "build_midday_action_summary_from_result",
    "build_decision_factor_entry",
    "build_decision_factors_from_result",
    "build_upgrade_trigger",
    "build_downgrade_trigger",
    "build_event_risk_trigger",
    "build_decision_flow_card",
    "build_decision_flow",
    "build_decision_flow_markdown",
    "midday_action_for_status",
    "prepare_request_with_candidate_snapshots",
    "wrap_assess_candidate_with_bars_failure_fallback",
    "TRACK_CONFIGS",
    "split_universe_by_board",
    "enrich_track_result",
    "merge_track_results",
):
    if _extra not in __all__:
        __all__.append(_extra)
