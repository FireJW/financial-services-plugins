#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import re
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
CODE_PATTERN = re.compile(r"(?P<name>[\u4e00-\u9fffA-Za-z0-9]+)\((?P<code>\d{6})\)")
RESPONSE_CONFIRM_KEYWORDS = ("确认", "证实", "属实", "已签", "confirm", "confirmed")
RESPONSE_DENY_KEYWORDS = ("否认", "不属实", "不实", "谣言", "澄清", "denied", "false")
RESPONSE_AMBIGUOUS_KEYWORDS = ("不予置评", "以公告为准", "无法评论", "适时披露", "no comment")


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
        "chain_name": clean_text(raw.get("chain_name")) or "unknown",
        "chain_role": clean_text(raw.get("chain_role")) or "unknown",
        "benefit_type": clean_text(raw.get("benefit_type")) or "mapping",
        "sources": sources,
        "source_roles": [normalize_source_role(item.get("source_type")) for item in sources if isinstance(item, dict)],
        "market_validation": deepcopy(raw.get("market_validation") or {}),
    }
    return candidate


def compute_rumor_confidence_range(candidate: dict[str, Any]) -> dict[str, Any]:
    roles = set(candidate.get("source_roles") or [])
    state = classify_event_state(candidate)
    if state["label"] == "response_denied":
        return {"label": "low", "range": [10, 25]}
    if state["label"] in {"official_confirmed", "response_confirmed"}:
        return {"label": "high", "range": [80, 90]}
    if state["label"] == "response_ambiguous":
        return {"label": "medium_high", "range": [55, 75]}
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
    state = classify_event_state(candidate)
    if state["label"] == "response_denied":
        return "track"
    if clean_text(candidate.get("event_type")).lower() == "rumor" and state["label"] not in {"response_confirmed", "official_confirmed"}:
        return "watch"
    if (
        clean_text(candidate.get("event_strength")).lower() == "strong"
        and validation["label"] == "strong"
        and confidence["label"] in {"medium", "medium_high", "high"}
    ):
        return "qualified"
    return "watch"


def detect_response_signal(text: str) -> str:
    normalized = clean_text(text)
    if any(keyword in normalized for keyword in RESPONSE_DENY_KEYWORDS):
        return "deny"
    if any(keyword in normalized for keyword in RESPONSE_CONFIRM_KEYWORDS):
        return "confirm"
    if any(keyword in normalized for keyword in RESPONSE_AMBIGUOUS_KEYWORDS):
        return "ambiguous"
    return ""


def classify_event_state(candidate: dict[str, Any]) -> dict[str, Any]:
    sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
    has_official_filing = False
    seen_signals: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_type = clean_text(source.get("source_type"))
        if source_type == "official_filing":
            has_official_filing = True
        summary = clean_text(source.get("summary"))
        response_signal = clean_text(source.get("response_signal")) or detect_response_signal(summary)
        if response_signal:
            seen_signals.add(response_signal)

    if has_official_filing:
        return {"label": "official_confirmed"}
    if "deny" in seen_signals:
        return {"label": "response_denied"}
    if "confirm" in seen_signals:
        return {"label": "response_confirmed"}
    if "ambiguous" in seen_signals:
        return {"label": "response_ambiguous"}
    if clean_text(candidate.get("event_type")).lower() == "rumor":
        return {"label": "rumor_unconfirmed"}
    return {"label": "unconfirmed"}


def classify_trading_usability(candidate: dict[str, Any]) -> dict[str, Any]:
    state = classify_event_state(candidate)
    validation = classify_market_validation(candidate)
    if state["label"] == "response_denied":
        return {"label": "low", "summary": "交易可用性低，优先等待进一步证据或回避。"}
    if state["label"] in {"official_confirmed", "response_confirmed"} and validation["label"] == "strong":
        return {"label": "high", "summary": "交易可用性高，已具备升级为执行判断的基础。"}
    if state["label"] in {"official_confirmed", "response_confirmed"}:
        return {"label": "medium", "summary": "交易可用性中等，事件已确认但仍需进一步量价确认。"}
    if validation["label"] == "strong":
        return {"label": "medium", "summary": "交易可用性中等，可作为重点观察对象。"}
    return {"label": "low", "summary": "交易可用性偏低，更多是线索而非执行依据。"}


def _event_type_priority(value: str) -> tuple[int, str]:
    normalized = clean_text(value)
    priorities = {
        "annual_report_preview": 0,
        "quarterly_preview": 1,
        "earnings": 2,
        "company_event": 3,
        "structured_catalyst": 4,
        "x_logic_signal": 5,
        "rumor": 6,
    }
    return (priorities.get(normalized, 99), normalized)


def _state_priority(value: str) -> int:
    return {
        "response_denied": 0,
        "official_confirmed": 1,
        "response_confirmed": 2,
        "response_ambiguous": 3,
        "rumor_unconfirmed": 4,
        "unconfirmed": 5,
    }.get(clean_text(value), 99)


def build_event_cards(discovery_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in discovery_rows:
        if not isinstance(row, dict):
            continue
        ticker = clean_text(row.get("ticker")) or clean_text(row.get("name"))
        if not ticker:
            continue
        grouped.setdefault(ticker, []).append(row)

    cards: list[dict[str, Any]] = []
    for ticker, rows in grouped.items():
        base = deepcopy(rows[0])
        all_sources: list[dict[str, Any]] = []
        all_roles: list[str] = []
        all_accounts: list[str] = []
        event_types: list[str] = []
        chain_names: list[str] = []
        chain_roles: list[str] = []
        benefit_types: list[str] = []
        merged_validation = {"volume_multiple_5d": 0.0, "breakout": False, "relative_strength": "", "chain_resonance": False}

        for row in rows:
            event_types.append(clean_text(row.get("event_type")))
            chain_names.append(clean_text(row.get("chain_name")))
            chain_roles.append(clean_text(row.get("chain_role")))
            benefit_types.append(clean_text(row.get("benefit_type")))
            for source in row.get("sources", []) if isinstance(row.get("sources"), list) else []:
                if not isinstance(source, dict):
                    continue
                all_sources.append(deepcopy(source))
                role = normalize_source_role(clean_text(source.get("source_type")))
                if role:
                    all_roles.append(role)
                account = clean_text(source.get("account"))
                if account:
                    all_accounts.append(account)
            validation = row.get("market_validation") if isinstance(row.get("market_validation"), dict) else {}
            merged_validation["volume_multiple_5d"] = max(float(merged_validation.get("volume_multiple_5d") or 0), float(validation.get("volume_multiple_5d") or 0))
            merged_validation["breakout"] = bool(merged_validation.get("breakout")) or bool(validation.get("breakout"))
            merged_validation["chain_resonance"] = bool(merged_validation.get("chain_resonance")) or bool(validation.get("chain_resonance"))
            if clean_text(validation.get("relative_strength")).lower() == "strong":
                merged_validation["relative_strength"] = "strong"

        merged_candidate = normalize_event_candidate(
            {
                "ticker": ticker,
                "name": clean_text(base.get("name")),
                "event_type": sorted([item for item in event_types if item], key=_event_type_priority)[0] if any(event_types) else clean_text(base.get("event_type")),
                "event_strength": "strong" if any(clean_text(row.get("event_strength")).lower() == "strong" for row in rows) else clean_text(base.get("event_strength")) or "medium",
                "chain_name": next((item for item in chain_names if item and item != "unknown"), "unknown"),
                "chain_role": next((item for item in chain_roles if item and item != "unknown"), "unknown"),
                "benefit_type": next((item for item in benefit_types if item and item != "mapping"), clean_text(base.get("benefit_type")) or "mapping"),
                "sources": all_sources,
                "market_validation": merged_validation,
            }
        )
        event_state = classify_event_state(merged_candidate)
        rumor_confidence = compute_rumor_confidence_range(merged_candidate)
        market_validation_summary = classify_market_validation(merged_candidate)
        trading_usability = classify_trading_usability(merged_candidate)
        discovery_bucket = assign_discovery_bucket(merged_candidate)
        card = {
            **merged_candidate,
            "event_types": sorted({item for item in event_types if item}, key=_event_type_priority),
            "primary_event_type": clean_text(merged_candidate.get("event_type")),
            "source_roles": sorted(set(all_roles)),
            "source_accounts": sorted(set(all_accounts)),
            "source_count": len(all_sources),
            "event_state": event_state,
            "rumor_confidence_range": rumor_confidence,
            "market_validation_summary": market_validation_summary,
            "trading_usability": trading_usability,
            "discovery_bucket": discovery_bucket,
        }
        cards.append(card)

    cards.sort(key=lambda item: (_state_priority(item.get("event_state", {}).get("label")), -len(item.get("sources", [])), clean_text(item.get("ticker"))))
    return cards


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


def build_x_style_discovery_candidates(
    batch_payload: dict[str, Any],
    *,
    selected_handles: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    desired_handles = {clean_text(item).lstrip("@") for item in (selected_handles or []) if clean_text(item)}
    if isinstance(batch_payload.get("subject_runs"), list):
        subject_runs = batch_payload.get("subject_runs", [])
    elif isinstance(batch_payload.get("recommendation_ledger"), list):
        subject_runs = [batch_payload]
    else:
        subject_runs = []
    for subject_run in subject_runs:
        if not isinstance(subject_run, dict):
            continue
        subject = subject_run.get("subject") if isinstance(subject_run.get("subject"), dict) else {}
        handle = clean_text(subject.get("handle")).lstrip("@")
        if desired_handles and handle not in desired_handles:
            continue

        name_to_ticker: dict[str, str] = {}
        for event in subject_run.get("recommendation_ledger", []) if isinstance(subject_run.get("recommendation_ledger"), list) else []:
            if not isinstance(event, dict):
                continue
            for scored in event.get("scored_names", []) if isinstance(event.get("scored_names"), list) else []:
                if not isinstance(scored, dict):
                    continue
                name = clean_text(scored.get("name"))
                ticker = clean_text(scored.get("ticker"))
                if name and ticker and name not in name_to_ticker:
                    name_to_ticker[name] = ticker

        source_board_by_status: dict[str, dict[str, Any]] = {}
        for item in subject_run.get("source_board", []) if isinstance(subject_run.get("source_board"), list) else []:
            if not isinstance(item, dict):
                continue
            status_url = clean_text(item.get("status_url"))
            status_id = clean_text(item.get("status_id"))
            if status_url:
                source_board_by_status[status_url] = item
            if status_id:
                source_board_by_status[status_id] = item

        for event in subject_run.get("recommendation_ledger", []) if isinstance(subject_run.get("recommendation_ledger"), list) else []:
            if not isinstance(event, dict):
                continue
            classification = clean_text(event.get("classification"))
            if classification not in {"direct_pick", "theme_basket", "logic_support", "quote_only"}:
                continue

            raw_names = event.get("names", []) if isinstance(event.get("names"), list) else []
            if not raw_names:
                raw_names = event.get("suggested_basket_core_candidates", []) if isinstance(event.get("suggested_basket_core_candidates"), list) else []
            if not raw_names:
                raw_names = event.get("suggested_basket_candidates", []) if isinstance(event.get("suggested_basket_candidates"), list) else []

            for raw_name in raw_names:
                name = clean_text(raw_name)
                if not name:
                    continue
                ticker = name_to_ticker.get(name, "")
                if not ticker:
                    source_item = source_board_by_status.get(clean_text(event.get("status_url"))) or source_board_by_status.get(clean_text(event.get("status_id")))
                    source_text = ""
                    if isinstance(source_item, dict):
                        source_text = clean_text(source_item.get("direct_text")) or clean_text(source_item.get("quoted_text"))
                    for match in CODE_PATTERN.finditer(source_text):
                        if clean_text(match.group("name")) == name:
                            code = clean_text(match.group("code"))
                            if code.startswith(("6", "9")):
                                ticker = f"{code}.SS"
                            else:
                                ticker = f"{code}.SZ"
                            break
                rows.append(
                    normalize_event_candidate(
                        {
                            "ticker": ticker,
                            "name": name,
                            "event_type": clean_text(event.get("catalyst_type")) or "x_logic_signal",
                            "event_strength": "strong" if "strong" in clean_text(event.get("strength")).lower() else "medium",
                            "chain_name": clean_text(event.get("sector_or_chain") or event.get("suggested_basket_sector")),
                            "chain_role": classification,
                            "benefit_type": "direct" if classification == "direct_pick" else "mapping",
                            "sources": [
                                {
                                    "source_type": "x_summary",
                                    "account": handle,
                                    "summary": clean_text(event.get("thesis_excerpt")),
                                    "status_url": clean_text(event.get("status_url")),
                                }
                            ],
                            "market_validation": {},
                        }
                    )
                )
    return rows
