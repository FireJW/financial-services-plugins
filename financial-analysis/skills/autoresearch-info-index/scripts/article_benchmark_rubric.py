#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any


RUBRIC_VERSION = "article_benchmark_rubric_v1"
DEFAULT_LONGFORM_THRESHOLD = 78
DEFAULT_DIMENSION_FLOOR = 50

RUBRIC_DIMENSIONS = (
    ("opening_hook", "opening hook", 15, "Open with one concrete tension, then collapse it into the real question before listing sources."),
    ("single_mainline", "single mainline", 14, "Keep one thesis running through the lede, headings, body, and watch section."),
    ("factual_restraint", "factual restraint", 14, "Separate confirmed facts from inference and keep unsettled claims visibly bounded."),
    ("second_order_analysis", "second-order analysis", 15, "Push past the headline into the underlying variable, incentive, constraint, or timing gap."),
    ("industry_market_transmission", "industry or market transmission", 15, "Show who is affected next and how the signal travels through supply, demand, costs, pricing, trust, or policy."),
    ("reader_payoff", "reader payoff", 12, "Translate the analysis into what investors, operators, companies, or practitioners can actually watch or decide."),
    ("trackable_ending", "trackable ending", 15, "End with concrete variables or nodes that can confirm, weaken, or reprice the thesis."),
)

BENCHMARK_DIMENSION_ALIASES = {
    "factual_restraint": "fact_restraint",
    "trackable_ending": "trackable_variables",
}
REFERENCE_SAMPLE_NAMES = ["nvidia-real-moat.md", "tsmc-asml-ai-infra-capex.md"]

OPENING_HOOK_TERMS = ("真正", "问题", "但", "不是", "而是", "如果", "为什么", "更值得", "real question", "what matters")
TENSION_TERMS = ("不是", "而是", "但", "可", "尴尬", "冲突", "争议", "担心", "误判", "问题在于", "tension", "but", "not")
SOURCE_DUMP_TERMS = ("来源：", "source:", "according to", "报道，报道称，", "彭博、路透、华尔街日报、")
MAINLINE_TERMS = ("真正", "核心", "关键", "变量", "主线", "不是", "而是", "判断", "分水岭", "real question", "what matters")
FACTUAL_RESTRAINT_TERMS = ("还不能", "不等于", "可能", "仍", "暂时", "边界", "风险", "如果", "会不会", "不能写死", "仍待", "尚未", "not settled", "not yet", "may", "risk")
OVERCLAIM_TERMS = ("已经证明", "必然", "一定会", "永远", "闭眼", "无风险", "确定会", "guaranteed", "inevitable", "risk-free")
SECOND_ORDER_TERMS = ("真正", "问题在于", "再往下一层", "往下拆", "背后", "意味着", "结构", "时间差", "分水岭", "泡沫结构", "护城河", "变量", "边界", "传导", "更深", "second-order", "underlying", "incentive", "constraint")
TRANSMISSION_GROUPS = {
    "supply_capacity": ("上游", "产能", "供应链", "制程", "封装", "设备", "服务器", "网络", "infrastructure", "capacity", "supply"),
    "money_orders": ("资本开支", "capex", "订单", "采购", "预算", "出货", "order", "spending", "purchase"),
    "market_pricing": ("市场", "投资者", "估值", "定价", "重估", "利润率", "股价", "market", "valuation", "pricing"),
    "cost_efficiency": ("成本", "效率", "吞吐", "延迟", "训练", "推理", "cost", "efficiency", "training", "inference"),
    "trust_governance": ("信任", "合规", "服务条款", "来源", "披露", "边界", "trust", "terms", "provenance"),
    "policy_risk": ("政策", "监管", "出口", "关税", "地缘", "利率", "policy", "regulation", "export", "tariff"),
}
READER_PAYOFF_TERMS = ("投资者", "读者", "从业者", "公司", "企业", "客户", "开发者", "市场", "谁会", "哪家", "风险", "受益", "重估", "更现实的问题", "值得盯", "真正要看", "值得注意", "观察", "决定", "应该", "investors", "operators", "companies", "customers")
READER_ACTION_TERMS = ("值得盯", "真正要看", "真正值得注意", "值得注意", "先看", "观察", "决定", "应该", "要是", "风险", "受益", "watch", "risk", "benefit")
TRACKABLE_TERMS = ("接下来", "盯", "验证", "节点", "第一", "第二", "第三", "会不会", "是否", "如果", "指引", "订单", "出货", "庭审", "政策", "数据", "变量", "watch", "checkpoint", "guidance", "orders")

EN_OPENING_HOOK_TERMS = ("important question", "whether", "real question", "what matters")
EN_TENSION_TERMS = ("not whether", "rather than", "instead", "but", "not")
EN_MAINLINE_TERMS = ("important question", "gating variable", "tracking map", "what readers can use")
EN_FACTUAL_RESTRAINT_TERMS = ("still does not prove", "only says", "does not prove", "risk", "may")
EN_SECOND_ORDER_TERMS = ("second-order", "underlying", "constraint", "bottleneck", "gating variable", "only matter", "converting into", "moved from", "rather than")
EN_CHAIN_TERMS = ("turning into", "converting into", "moved from", "through", "link", "travels")
EN_READER_PAYOFF_TERMS = ("investors", "operators", "companies", "customers", "tracking map", "benefit")
EN_READER_ACTION_TERMS = ("watch", "risk", "benefit", "read in that order", "should be read")
EN_TRACKABLE_TERMS = ("first", "second", "third", "whether", "backlog", "utilization", "capacity", "guidance", "orders")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clamp(value: int, floor: int = 0, ceiling: int = 100) -> int:
    return max(floor, min(ceiling, value))


def count_terms(text: str, terms: tuple[str, ...]) -> int:
    lowered = clean_text(text).lower()
    return sum(1 for term in terms if term.lower() in lowered)


def count_overclaim_hits(text: str) -> int:
    lowered = clean_text(text).lower()
    return sum(lowered.count(term.lower()) for term in OVERCLAIM_TERMS)


def section_headings(article_package: dict[str, Any]) -> list[str]:
    return [clean_text(item.get("heading")) for item in safe_list(article_package.get("sections")) if isinstance(item, dict) and clean_text(item.get("heading"))]


def section_paragraphs(article_package: dict[str, Any]) -> list[str]:
    return [clean_text(item.get("paragraph")) for item in safe_list(article_package.get("sections")) if isinstance(item, dict) and clean_text(item.get("paragraph"))]


def compose_article_text(article_package: dict[str, Any]) -> str:
    markdown = clean_text(article_package.get("content_markdown") or article_package.get("article_markdown") or article_package.get("body_markdown"))
    if markdown:
        return markdown
    parts = [clean_text(article_package.get("title")), clean_text(article_package.get("draft_thesis") or article_package.get("thesis")), clean_text(article_package.get("subtitle")), clean_text(article_package.get("lede")), *section_headings(article_package), *section_paragraphs(article_package)]
    return "\n".join(part for part in parts if part)


def opening_text(article_package: dict[str, Any], full_text: str) -> str:
    lede = clean_text(article_package.get("lede"))
    if lede:
        return lede[:420]
    for raw_line in str(full_text or "").splitlines():
        line = clean_text(raw_line.lstrip("#> "))
        if line and not line.startswith("来源") and not line.startswith("##"):
            return line[:420]
    return clean_text(full_text)[:420]


def ending_text(article_package: dict[str, Any], full_text: str) -> str:
    sections = [safe_dict(item) for item in safe_list(article_package.get("sections")) if isinstance(item, dict)]
    if sections:
        last = sections[-1]
        return " ".join([clean_text(last.get("heading")), clean_text(last.get("paragraph"))])
    return clean_text(full_text)[-900:]


def count_chinese_sentences(text: str) -> int:
    return len([item for item in re.split(r"[。！？!?.]+", str(text or "")) if clean_text(item)])


def transmission_group_hits(text: str) -> list[str]:
    lowered = clean_text(text).lower()
    return [group for group, terms in TRANSMISSION_GROUPS.items() if any(term.lower() in lowered for term in terms)]


def score_opening_hook(article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    opening = opening_text(article_package, full_text)
    score = 0
    score += 20 if 80 <= len(opening) <= 420 else (10 if 40 <= len(opening) else 0)
    hook_hits = count_terms(opening, OPENING_HOOK_TERMS) + count_terms(opening, EN_OPENING_HOOK_TERMS)
    tension_hits = count_terms(opening, TENSION_TERMS) + count_terms(opening, EN_TENSION_TERMS)
    source_dump_hits = count_terms(opening[:180], SOURCE_DUMP_TERMS)
    score += min(25, hook_hits * 8)
    score += min(25, tension_hits * 8)
    score += 15 if re.search(r"[A-Za-z]{2,}|[\u4e00-\u9fff]{2,}", opening) else 0
    score += 15 if source_dump_hits == 0 else 0
    return clamp(score), {"opening_chars": len(opening), "hook_hits": hook_hits, "tension_hits": tension_hits, "source_dump_hits": source_dump_hits}


def score_single_mainline(article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    title = clean_text(article_package.get("title"))
    thesis = clean_text(article_package.get("draft_thesis") or article_package.get("thesis"))
    headings = section_headings(article_package)
    mainline_text = " ".join([thesis, " ".join(headings), full_text[:900]])
    mainline_hits = count_terms(mainline_text, MAINLINE_TERMS) + count_terms(mainline_text, EN_MAINLINE_TERMS)
    score = (22 if title else 0) + (25 if thesis else 10 if mainline_hits >= 2 else 0)
    score += 18 if 4 <= len(headings) <= 7 else 8 if len(headings) >= 3 else 0
    score += min(20, mainline_hits * 4)
    score += 15 if len(set(headings)) == len(headings) and headings else 0
    return clamp(score), {"title_present": bool(title), "thesis_present": bool(thesis), "section_count": len(headings), "mainline_term_hits": mainline_hits}


def score_factual_restraint(article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    restraint_hits = count_terms(full_text, FACTUAL_RESTRAINT_TERMS) + count_terms(full_text, EN_FACTUAL_RESTRAINT_TERMS)
    citations = safe_list(article_package.get("citations"))
    not_proven = safe_list(article_package.get("not_proven"))
    overclaim_hits = count_overclaim_hits(full_text)
    score = 20 + min(30, restraint_hits * 5) + (20 if citations else 0) + (15 if not_proven else 0)
    score += 15 if overclaim_hits == 0 else -min(30, overclaim_hits * 10)
    return clamp(score), {"restraint_hits": restraint_hits, "citation_count": len(citations), "not_proven_count": len(not_proven), "overclaim_hits": overclaim_hits}


def score_second_order_analysis(_article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    hits = count_terms(full_text, SECOND_ORDER_TERMS) + count_terms(full_text, EN_SECOND_ORDER_TERMS)
    contrast_hits = len(re.findall(r"不是[^。；;]{0,80}(?:而是|只是|但)", full_text))
    sentence_count = count_chinese_sentences(full_text)
    return clamp(15 + min(40, hits * 5) + min(25, contrast_hits * 8) + (20 if sentence_count >= 16 else 8 if sentence_count >= 8 else 0)), {"second_order_term_hits": hits, "contrast_hits": contrast_hits, "sentence_count": sentence_count}


def score_industry_market_transmission(_article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    group_hits = transmission_group_hits(full_text)
    chain_hits = count_terms(full_text, ("传导", "往下", "顺着", "落到", "影响到", "read-through", "flow through"))
    chain_hits += count_terms(full_text, EN_CHAIN_TERMS)
    return clamp(10 + min(60, len(group_hits) * 12) + min(30, chain_hits * 6)), {"transmission_groups": group_hits, "chain_hits": chain_hits}


def score_reader_payoff(_article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    payoff_hits = count_terms(full_text, READER_PAYOFF_TERMS) + count_terms(full_text, EN_READER_PAYOFF_TERMS)
    action_hits = count_terms(full_text, READER_ACTION_TERMS) + count_terms(full_text, EN_READER_ACTION_TERMS)
    return clamp(15 + min(50, payoff_hits * 5) + min(35, action_hits * 7)), {"payoff_hits": payoff_hits, "action_hits": action_hits}


def score_trackable_ending(article_package: dict[str, Any], full_text: str) -> tuple[int, dict[str, Any]]:
    ending = ending_text(article_package, full_text)
    headings = section_headings(article_package)
    trackable_hits = count_terms(ending, TRACKABLE_TERMS)
    enumerated_hits = sum(ending.count(item) for item in ("第一", "第二", "第三", "1.", "2.", "3."))
    watch_heading = any(any(term in heading for term in ("接下来", "结尾", "观察", "盯")) for heading in headings[-2:])
    score = 10 + (25 if watch_heading else 0) + min(35, trackable_hits * 4) + min(20, enumerated_hits * 7) + (10 if "如果" in ending or "if" in ending.lower() else 0)
    trackable_hits += count_terms(ending, EN_TRACKABLE_TERMS)
    enumerated_hits += sum(ending.lower().count(item) for item in ("first", "second", "third"))
    watch_heading = watch_heading or any(any(term in heading.lower() for term in ("watch", "next", "checkpoint")) for heading in headings[-2:])
    score = 10 + (25 if watch_heading else 0) + min(35, trackable_hits * 4) + min(20, enumerated_hits * 7) + (10 if "if" in ending.lower() else 0)
    return clamp(score), {"ending_chars": len(ending), "trackable_hits": trackable_hits, "enumerated_hits": enumerated_hits, "watch_heading": watch_heading}


SCORERS = {
    "opening_hook": score_opening_hook,
    "single_mainline": score_single_mainline,
    "factual_restraint": score_factual_restraint,
    "second_order_analysis": score_second_order_analysis,
    "industry_market_transmission": score_industry_market_transmission,
    "reader_payoff": score_reader_payoff,
    "trackable_ending": score_trackable_ending,
}


def score_benchmark_rubric(article_package: dict[str, Any], request: dict[str, Any] | None = None, *, threshold: int = DEFAULT_LONGFORM_THRESHOLD, dimension_floor: int = DEFAULT_DIMENSION_FLOOR) -> dict[str, Any]:
    package = safe_dict(article_package)
    request_payload = safe_dict(request)
    full_text = compose_article_text(package)
    dimension_scores: dict[str, dict[str, Any]] = {}
    scorecard: list[dict[str, Any]] = []
    weighted_total = 0.0
    total_weight = 0
    for key, label, weight, recommendation in RUBRIC_DIMENSIONS:
        score, signals = SCORERS[key](package, full_text)
        total_weight += weight
        weighted_total += score * weight
        dimension_scores[key] = {"label": label, "score": score, "weight": weight, "signals": signals, "recommendation": recommendation}
        scorecard.append(
            {
                "dimension": BENCHMARK_DIMENSION_ALIASES.get(key, key),
                "source_key": key,
                "label": label,
                "score": score,
                "score_10": round(score / 10, 1),
                "weight": weight,
                "recommendation": recommendation,
                "signals": signals,
            }
        )
    total_score = int(round(weighted_total / max(1, total_weight)))
    weakest = sorted(
        ({"key": key, "label": value["label"], "score": value["score"], "recommendation": value["recommendation"]} for key, value in dimension_scores.items()),
        key=lambda item: (item["score"], item["key"]),
    )[:3]
    low_dimensions = [item for item in weakest if int(item["score"]) < dimension_floor]
    target_length = int(request_payload.get("target_length_chars", 0) or 0)
    expected = target_length >= 1800 or clean_text(request_payload.get("language_mode")) == "chinese"
    passed = (not expected) or (total_score >= threshold and not low_dimensions)
    weakest_three = [
        {
            "dimension": BENCHMARK_DIMENSION_ALIASES.get(item["key"], item["key"]),
            "source_key": item["key"],
            "label": item["label"],
            "score": item["score"],
            "score_10": round(int(item["score"]) / 10, 1),
            "recommendation": item["recommendation"],
        }
        for item in weakest
    ]
    return {
        "contract_version": RUBRIC_VERSION,
        "policy": "derived_rules_only_no_raw_benchmark_text",
        "reference_samples": REFERENCE_SAMPLE_NAMES,
        "expected": expected,
        "threshold": threshold,
        "dimension_floor": dimension_floor,
        "total_score": total_score,
        "average_score": round(total_score / 10, 1),
        "passed": passed,
        "passes_floor": passed,
        "scorecard": scorecard,
        "weakest_three": weakest_three,
        "weakest_dimensions": weakest,
        "dimensions": dimension_scores,
        "source_rules": [
            "opening hook",
            "single mainline",
            "factual restraint",
            "second-order analysis",
            "industry or market transmission",
            "reader payoff",
            "trackable ending variables",
        ],
    }


__all__ = [
    "DEFAULT_DIMENSION_FLOOR",
    "DEFAULT_LONGFORM_THRESHOLD",
    "RUBRIC_DIMENSIONS",
    "RUBRIC_VERSION",
    "score_benchmark_rubric",
]
