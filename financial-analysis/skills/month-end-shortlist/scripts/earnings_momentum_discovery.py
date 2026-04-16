#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any


SOURCE_ROLE_MAP = {
    "official_filing": "official_filing_reference",
    "company_response": "company_response_reference",
    "x_summary": "summary_or_relay",
    "x_thread": "personal_thesis",
    "market_rumor": "market_rumor",
    "xueqiu_summary": "summary_or_relay",
    "community_post": "personal_thesis",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_source_role(source_type: str) -> str:
    return SOURCE_ROLE_MAP.get(clean_text(source_type), "personal_thesis")


def normalize_event_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    sources = deepcopy(raw.get("sources") or [])
    candidate = {
        "ticker": clean_text(raw.get("ticker")),
        "name": clean_text(raw.get("name")) or clean_text(raw.get("ticker")),
        "event_type": clean_text(raw.get("event_type")),
        "event_strength": clean_text(raw.get("event_strength")) or "medium",
        "chain_name": clean_text(raw.get("chain_name")),
        "chain_role": clean_text(raw.get("chain_role")) or "unknown",
        "benefit_type": clean_text(raw.get("benefit_type")) or "mapping",
        "sources": sources,
        "source_roles": [normalize_source_role(item.get("source_type")) for item in sources if isinstance(item, dict)],
        "market_validation": deepcopy(raw.get("market_validation") or {}),
    }
    return candidate


def compute_rumor_confidence_range(candidate: dict[str, Any]) -> dict[str, Any]:
    roles = set(candidate.get("source_roles") or [])
    if "official_filing_reference" in roles or "company_response_reference" in roles:
        return {"label": "high", "range": [80, 90]}
    if "market_rumor" in roles:
        return {"label": "medium", "range": [40, 65]}
    return {"label": "low", "range": [20, 40]}


def classify_market_validation(candidate: dict[str, Any]) -> dict[str, Any]:
    data = candidate.get("market_validation") if isinstance(candidate.get("market_validation"), dict) else {}
    score = 0
    if float(data.get("volume_multiple_5d") or 0) >= 1.5:
        score += 1
    if bool(data.get("breakout")):
        score += 1
    if clean_text(data.get("relative_strength")).lower() == "strong":
        score += 1
    if bool(data.get("chain_resonance")):
        score += 1

    if score >= 3:
        return {"label": "strong", "summary": "强资金先行，存在提前进场迹象。"}
    if score >= 2:
        return {"label": "medium", "summary": "中等资金先行，已有部分提前验证。"}
    return {"label": "weak", "summary": "弱资金先行，仍需更多量价确认。"}


def assign_discovery_bucket(candidate: dict[str, Any]) -> str:
    confidence = compute_rumor_confidence_range(candidate)
    validation = classify_market_validation(candidate)
    if clean_text(candidate.get("event_type")).lower() == "rumor":
        return "watch"
    if (
        clean_text(candidate.get("event_strength")).lower() == "strong"
        and validation["label"] == "strong"
        and confidence["label"] in {"medium", "high"}
    ):
        return "qualified"
    return "watch"


def build_market_validation_from_shortlist_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    trend = candidate.get("trend_template") if isinstance(candidate.get("trend_template"), dict) else {}
    price_snapshot = candidate.get("price_snapshot") if isinstance(candidate.get("price_snapshot"), dict) else {}
    rs90 = float(price_snapshot.get("rs90") or 0)
    distance_to_high = float(price_snapshot.get("distance_to_high52_pct") or 1000)
    return {
        "volume_multiple_5d": float(candidate.get("volume_ratio") or 0),
        "breakout": bool(trend.get("trend_pass")) and distance_to_high <= 25.0,
        "relative_strength": "strong" if rs90 >= 500 else "normal",
        "chain_resonance": False,
    }


def infer_event_type_from_shortlist_candidate(candidate: dict[str, Any]) -> str:
    snapshot = candidate.get("structured_catalyst_snapshot") if isinstance(candidate.get("structured_catalyst_snapshot"), dict) else {}
    previews = snapshot.get("performance_preview") if isinstance(snapshot.get("performance_preview"), list) else []
    if previews:
        report_period = clean_text((previews[0] or {}).get("report_period"))
        if report_period.endswith("-12-31"):
            return "annual_report_preview"
        return "quarterly_preview"
    company_events = snapshot.get("structured_company_events") if isinstance(snapshot.get("structured_company_events"), list) else []
    if company_events:
        return "company_event"
    return "structured_catalyst"


def build_source_items_from_shortlist_candidate(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = candidate.get("structured_catalyst_snapshot") if isinstance(candidate.get("structured_catalyst_snapshot"), dict) else {}
    rows: list[dict[str, Any]] = []
    for item in snapshot.get("performance_preview", []) if isinstance(snapshot.get("performance_preview"), list) else []:
        if not isinstance(item, dict):
            continue
        summary = clean_text(item.get("summary"))
        if summary:
            rows.append(
                {
                    "source_type": "official_filing",
                    "date": clean_text(item.get("notice_date")),
                    "summary": summary,
                }
            )
    for item in snapshot.get("structured_company_events", []) if isinstance(snapshot.get("structured_company_events"), list) else []:
        if not isinstance(item, dict):
            continue
        detail = clean_text(item.get("detail"))
        if detail:
            rows.append(
                {
                    "source_type": "official_filing",
                    "date": clean_text(item.get("date")),
                    "summary": detail,
                }
            )
    return rows


def build_auto_discovery_candidates(assessed_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in assessed_candidates:
        if not isinstance(candidate, dict):
            continue
        snapshot = candidate.get("structured_catalyst_snapshot") if isinstance(candidate.get("structured_catalyst_snapshot"), dict) else {}
        sources = build_source_items_from_shortlist_candidate(candidate)
        if not snapshot.get("structured_catalyst_within_window") and not sources:
            continue
        rows.append(
            normalize_event_candidate(
                {
                    "ticker": clean_text(candidate.get("ticker")),
                    "name": clean_text(candidate.get("name")),
                    "event_type": infer_event_type_from_shortlist_candidate(candidate),
                    "event_strength": "strong" if float((candidate.get("score_components") or {}).get("structured_catalyst_score") or 0) >= 12 else "medium",
                    "chain_name": clean_text(candidate.get("sector")),
                    "chain_role": clean_text(candidate.get("chain_role")) or "unknown",
                    "benefit_type": "direct",
                    "sources": sources,
                    "market_validation": build_market_validation_from_shortlist_candidate(candidate),
                }
            )
        )
    return rows
