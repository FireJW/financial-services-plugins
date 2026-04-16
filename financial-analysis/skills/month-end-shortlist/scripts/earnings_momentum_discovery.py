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


SCHEDULE_ONLY_KEYWORDS = ("披露时间", "预约披露", "提前至", "将于", "定于", "预约日期")
POSITIVE_EXPECTATION_KEYWORDS = ("超预期", "大超预期", "明显超预期", "很硬", "强劲", "弹性最大", "价格可能上行", "涨价", "景气", "环比增长", "稳中有升", "放量攀升")
NEGATIVE_EXPECTATION_KEYWORDS = ("不及预期", "低于预期", "承压", "利空", "弱于预期", "低于一致预期")
METRIC_PATTERN = re.compile(r"(?:\d+(?:\.\d+)?(?:%|x|X|GW|G|T|亿|亿元|万亿|万颗|万台|倍|万亿Token)|Q\d|\d+月\d+日)")


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
        "peer_tier_1": [clean_text(item) for item in raw.get("peer_tier_1", []) if clean_text(item)],
        "peer_tier_2": [clean_text(item) for item in raw.get("peer_tier_2", []) if clean_text(item)],
        "leaders": [clean_text(item) for item in raw.get("leaders", []) if clean_text(item)],
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


def _chain_role_priority(value: str) -> tuple[int, str]:
    normalized = clean_text(value)
    priorities = {
        "upstream_material": 0,
        "midstream_manufacturing": 1,
        "downstream_brand": 2,
        "direct_pick": 3,
        "theme_basket": 4,
        "logic_support": 5,
        "quote_only": 6,
    }
    return (priorities.get(normalized, 99), normalized)


def _benefit_type_priority(value: str) -> tuple[int, str]:
    normalized = clean_text(value)
    priorities = {
        "direct": 0,
        "mapping": 1,
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


def compute_event_priority_score(candidate: dict[str, Any]) -> int:
    state = classify_event_state(candidate)
    usability = classify_trading_usability(candidate)
    validation = classify_market_validation(candidate)
    source_roles = set(candidate.get("source_roles") or [])
    score = 0
    if state["label"] == "official_confirmed":
        score += 40
    elif state["label"] == "response_confirmed":
        score += 30
    elif state["label"] == "response_ambiguous":
        score += 20
    elif state["label"] == "rumor_unconfirmed":
        score += 10
    if usability["label"] == "high":
        score += 25
    elif usability["label"] == "medium":
        score += 15
    if validation["label"] == "strong":
        score += 20
    elif validation["label"] == "medium":
        score += 10
    if "official_filing_reference" in source_roles:
        score += 10
    if "summary_or_relay" in source_roles or "personal_thesis" in source_roles:
        score += 5
    return score


def build_evidence_mix(sources: list[dict[str, Any]]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_type = clean_text(source.get("source_type")) or "unknown"
        mix[source_type] = mix.get(source_type, 0) + 1
    return mix


def collect_source_urls(sources: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("status_url", "url", "source_url"):
            url = clean_text(source.get(key))
            if url and url not in urls:
                urls.append(url)
    return urls


def build_key_evidence(sources: list[dict[str, Any]], *, limit: int = 4) -> list[str]:
    bullets: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_type = clean_text(source.get("source_type")) or "unknown"
        account = clean_text(source.get("account"))
        date = clean_text(source.get("date") or source.get("published_at"))[:10]
        text = clean_text(source.get("evidence_excerpt")) or clean_text(source.get("summary")) or clean_text(source.get("quoted_text"))
        if not text:
            continue
        if len(text) > 120:
            text = text[:117].rstrip() + "..."
        prefix = [source_type]
        if account:
            prefix.append(account)
        if date:
            prefix.append(date)
        bullet = f"[{' | '.join(prefix)}] {text}"
        if bullet in seen:
            continue
        seen.add(bullet)
        bullets.append(bullet)
        if len(bullets) >= limit:
            break
    return bullets


def build_market_signal_summary(candidate: dict[str, Any]) -> str:
    data = candidate.get("market_validation") if isinstance(candidate.get("market_validation"), dict) else {}
    volume_multiple = float(data.get("volume_multiple_5d") or 0.0)
    breakout = "yes" if bool(data.get("breakout")) else "no"
    relative_strength = clean_text(data.get("relative_strength")) or "unknown"
    chain_resonance = "yes" if bool(data.get("chain_resonance")) else "no"
    return (
        f"volume_5d={volume_multiple:.1f}x; breakout={breakout}; "
        f"rs={relative_strength}; chain_resonance={chain_resonance}"
    )


def build_chain_path_summary(candidate: dict[str, Any]) -> str:
    return (
        f"{clean_text(candidate.get('chain_name')) or 'unknown'} / "
        f"{clean_text(candidate.get('chain_role')) or 'unknown'} / "
        f"{clean_text(candidate.get('benefit_type')) or 'mapping'}"
    )


def extract_headline_metrics(sources: list[dict[str, Any]], *, limit: int = 6) -> list[str]:
    metrics: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = clean_text(source.get("summary")) or clean_text(source.get("evidence_excerpt")) or clean_text(source.get("quoted_text"))
        if not text:
            continue
        for match in METRIC_PATTERN.finditer(text):
            snippet = clean_text(match.group(0))
            if snippet and snippet not in seen:
                seen.add(snippet)
                metrics.append(snippet)
            if len(metrics) >= limit:
                return metrics
    return metrics


def classify_event_phase(candidate: dict[str, Any]) -> str:
    sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
    joined = " ".join(clean_text(item.get("summary")) for item in sources if isinstance(item, dict))
    if clean_text(candidate.get("event_type")).lower() == "rumor":
        return "传闻博弈"
    if any(keyword in joined for keyword in SCHEDULE_ONLY_KEYWORDS):
        return "预期交易"
    if any(item.get("source_type") == "official_filing" for item in sources if isinstance(item, dict)):
        if clean_text(candidate.get("event_type")).lower() in {"quarterly_preview", "annual_report_preview", "earnings"}:
            return "官方预告"
        return "正式结果"
    return "预期交易"


def classify_expectation_verdict(candidate: dict[str, Any]) -> str:
    sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
    joined = " ".join(clean_text(item.get("summary")) for item in sources if isinstance(item, dict))
    phase = classify_event_phase(candidate)
    if any(keyword in joined for keyword in NEGATIVE_EXPECTATION_KEYWORDS):
        return "不及预期"
    if any(keyword in joined for keyword in POSITIVE_EXPECTATION_KEYWORDS):
        if phase == "预期交易":
            return "市场押注超预期"
        return "超预期"
    if phase == "预期交易":
        return "暂无一致预期"
    return "符合预期"


def build_community_reaction_summary(candidate: dict[str, Any]) -> str:
    sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
    named_accounts = sorted(
        {
            clean_text(item.get("account"))
            for item in sources
            if isinstance(item, dict) and clean_text(item.get("account"))
        }
    )
    account_summary = ", ".join(named_accounts) if named_accounts else "无明确账号"
    verdict = classify_expectation_verdict(candidate)
    validation = classify_market_validation(candidate)["label"]
    return f"{account_summary}；当前社区判断偏 `{verdict}`，量价验证 `{validation}`。"


def classify_community_conviction(candidate: dict[str, Any]) -> str:
    accounts = sorted(
        {
            clean_text(item.get("account"))
            for item in candidate.get("sources", [])
            if isinstance(item, dict) and clean_text(item.get("account"))
        }
    )
    validation = classify_market_validation(candidate)["label"]
    if len(accounts) >= 3 and validation == "strong":
        return "high"
    if len(accounts) >= 2:
        return "medium"
    return "low"


def build_expectation_basis_summary(candidate: dict[str, Any]) -> str:
    text = " ".join(
        clean_text(item.get("summary")) or clean_text(item.get("evidence_excerpt"))
        for item in candidate.get("sources", [])
        if isinstance(item, dict)
    )
    drivers: list[str] = []
    if any(term in text for term in ("800G", "1.6T", "放量攀升", "环比增长")):
        drivers.append("800G/1.6T放量")
    if any(term in text for term in ("毛利率", "硅光", "高端占比", "良率", "稳中有升")):
        drivers.append("毛利率改善")
    if any(term in text for term in ("EML", "缺货", "紧缺", "锁定产能", "涨价")):
        drivers.append("EML紧缺")
    if any(term in text for term in ("9.4GW", "120万亿", "算力租赁", "需求", "上行")):
        drivers.append("需求扩张")
    return "；".join(drivers) if drivers else "暂无清晰预期驱动"


def build_expectation_risk_summary(candidate: dict[str, Any]) -> str:
    verdict = classify_expectation_verdict(candidate)
    if verdict == "市场押注超预期":
        return "若财报兑现弱于这些线索，或者环比/毛利率改善不持续，预期可能快速回吐。"
    if verdict == "暂无一致预期":
        return "当前更偏主题跟踪，若缺少后续数据或新增催化，热度容易下降。"
    if verdict == "不及预期":
        return "若后续没有更强催化或公司修正指引，股价可能继续消化负反馈。"
    return "关注预期兑现节奏与资金是否继续强化主线。"


def build_why_now_summary(candidate: dict[str, Any]) -> str:
    state = classify_event_state(candidate)
    validation = classify_market_validation(candidate)
    accounts = [clean_text(item.get("account")) for item in candidate.get("sources", []) if isinstance(item, dict) and clean_text(item.get("account"))]
    account_text = ", ".join(sorted(set(accounts))) if accounts else "no_named_accounts"
    return (
        f"{state['label']} + {validation['label']} validation"
        f" + accounts[{account_text}]"
    )


def build_event_cards(discovery_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_ticker_by_name: dict[str, str] = {}
    for row in discovery_rows:
        if not isinstance(row, dict):
            continue
        name = clean_text(row.get("name"))
        ticker = clean_text(row.get("ticker"))
        if name and ticker:
            preferred_ticker_by_name.setdefault(name, ticker)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in discovery_rows:
        if not isinstance(row, dict):
            continue
        name = clean_text(row.get("name"))
        ticker = clean_text(row.get("ticker")) or preferred_ticker_by_name.get(name) or name
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
        peer_tier_1: list[str] = []
        peer_tier_2: list[str] = []
        leaders: list[str] = []
        merged_validation = {"volume_multiple_5d": 0.0, "breakout": False, "relative_strength": "", "chain_resonance": False}

        for row in rows:
            event_types.append(clean_text(row.get("event_type")))
            chain_names.append(clean_text(row.get("chain_name")))
            chain_roles.append(clean_text(row.get("chain_role")))
            benefit_types.append(clean_text(row.get("benefit_type")))
            peer_tier_1.extend([clean_text(item) for item in row.get("peer_tier_1", []) if clean_text(item)])
            peer_tier_2.extend([clean_text(item) for item in row.get("peer_tier_2", []) if clean_text(item)])
            leaders.extend([clean_text(item) for item in row.get("leaders", []) if clean_text(item)])
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
                "chain_role": sorted([item for item in chain_roles if item and item != "unknown"], key=_chain_role_priority)[0] if any(item and item != "unknown" for item in chain_roles) else "unknown",
                "benefit_type": sorted([item for item in benefit_types if item], key=_benefit_type_priority)[0] if any(item for item in benefit_types) else (clean_text(base.get("benefit_type")) or "mapping"),
                "sources": all_sources,
                "market_validation": merged_validation,
                "peer_tier_1": sorted({item for item in peer_tier_1 if item}),
                "peer_tier_2": sorted({item for item in peer_tier_2 if item}),
                "leaders": sorted({item for item in leaders if item}),
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
            "evidence_mix": build_evidence_mix(all_sources),
            "source_urls": collect_source_urls(all_sources),
            "key_evidence": build_key_evidence(all_sources),
            "market_signal_summary": build_market_signal_summary(merged_candidate),
            "chain_path_summary": build_chain_path_summary(merged_candidate),
            "event_phase": classify_event_phase(merged_candidate),
            "expectation_verdict": classify_expectation_verdict(merged_candidate),
            "headline_metrics": extract_headline_metrics(all_sources),
            "community_reaction_summary": build_community_reaction_summary(merged_candidate),
            "community_conviction": classify_community_conviction(merged_candidate),
            "expectation_basis_summary": build_expectation_basis_summary(merged_candidate),
            "expectation_risk_summary": build_expectation_risk_summary(merged_candidate),
            "peer_tier_1": sorted({item for item in merged_candidate.get("peer_tier_1", []) if item}),
            "peer_tier_2": sorted({item for item in merged_candidate.get("peer_tier_2", []) if item}),
            "leaders": sorted({item for item in merged_candidate.get("leaders", []) if item}),
            "event_state": event_state,
            "rumor_confidence_range": rumor_confidence,
            "market_validation_summary": market_validation_summary,
            "trading_usability": trading_usability,
            "discovery_bucket": discovery_bucket,
            "priority_score": compute_event_priority_score(merged_candidate),
            "why_now": build_why_now_summary(merged_candidate),
        }
        cards.append(card)

    cards.sort(key=lambda item: (-int(item.get("priority_score") or 0), _state_priority(item.get("event_state", {}).get("label")), clean_text(item.get("ticker"))))
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

            source_item = source_board_by_status.get(clean_text(event.get("status_url"))) or source_board_by_status.get(clean_text(event.get("status_id")))
            source_text = ""
            published_at = ""
            source_kind = ""
            if isinstance(source_item, dict):
                source_text = clean_text(source_item.get("direct_text")) or clean_text(source_item.get("quoted_text"))
                published_at = clean_text(source_item.get("published_at"))
                source_kind = clean_text(source_item.get("source_kind"))

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
                            "peer_tier_1": [clean_text(item) for item in event.get("suggested_basket_core_candidates", []) if clean_text(item)],
                            "peer_tier_2": [
                                clean_text(item)
                                for item in event.get("suggested_basket_candidates", [])
                                if clean_text(item) and clean_text(item) not in {clean_text(core) for core in event.get("suggested_basket_core_candidates", []) if clean_text(core)}
                            ],
                            "leaders": [name] if classification == "direct_pick" else [clean_text(item) for item in event.get("suggested_basket_core_candidates", []) if clean_text(item)],
                            "sources": [
                                {
                                    "source_type": "x_summary",
                                    "account": handle,
                                    "summary": clean_text(event.get("thesis_excerpt")) or source_text,
                                    "evidence_excerpt": source_text or clean_text(event.get("thesis_excerpt")),
                                    "status_url": clean_text(event.get("status_url")),
                                    "published_at": published_at,
                                    "source_kind": source_kind,
                                }
                            ],
                            "market_validation": {},
                        }
                    )
                )
    return rows
