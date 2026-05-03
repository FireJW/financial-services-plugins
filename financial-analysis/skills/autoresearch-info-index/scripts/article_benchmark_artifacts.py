#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


GENERIC_BENCHMARK_SEARCH_TERMS = {
    "ai",
    "AI",
    "analysis",
    "market",
    "reaction",
    "news",
    "business",
    "investing",
    "industry",
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "out",
    "the",
    "to",
    "with",
}

BENCHMARK_TOPIC_EXPANSIONS = [
    {
        "triggers": ["内存", "内存条", "dram", "hbm", "memory", "micron", "sk hynix", "samsung"],
        "required_terms": ["内存", "内存条", "DRAM", "HBM", "memory"],
        "query_templates": [
            '"{title}"',
            '内存 AI 涨价',
            'DRAM HBM AI memory',
            'AI server memory shortage',
            'Micron HBM AI demand',
            'SK Hynix HBM AI memory',
            'Samsung DRAM HBM AI',
        ],
    },
]


def is_generic_benchmark_search_term(value: Any) -> bool:
    text = clean_text(value)
    return not text or text in GENERIC_BENCHMARK_SEARCH_TERMS or text.lower() in GENERIC_BENCHMARK_SEARCH_TERMS


def benchmark_topic_expansion(selected_title: str, keywords: list[str]) -> dict[str, Any]:
    haystack = " ".join([selected_title, *keywords]).lower()
    for expansion in BENCHMARK_TOPIC_EXPANSIONS:
        if any(clean_text(trigger).lower() in haystack for trigger in safe_list(expansion.get("triggers"))):
            return expansion
    return {}


def build_benchmark_required_terms(selected_title: str, keywords: list[str]) -> list[str]:
    expansion = benchmark_topic_expansion(selected_title, keywords)
    terms = clean_string_list(safe_list(expansion.get("required_terms")))
    if not terms:
        terms.extend(
            term
            for term in clean_string_list([selected_title, *keywords])
            if not is_generic_benchmark_search_term(term)
        )
    return clean_string_list(terms)[:10]


def query_has_required_term(query: str, required_terms: list[str]) -> bool:
    lowered_query = clean_text(query).lower()
    return any(clean_text(term).lower() in lowered_query for term in required_terms)


def build_benchmark_enrichment_queries(selected_title: str, keywords: list[str]) -> list[str]:
    required_terms = build_benchmark_required_terms(selected_title, keywords)
    expansion = benchmark_topic_expansion(selected_title, keywords)
    raw_queries = clean_string_list(
        [
            selected_title,
            f'"{selected_title}"',
            *clean_string_list(expansion.get("query_templates")),
            f"{selected_title} analysis",
            f"{selected_title} market reaction",
        ]
    )
    anchored_queries = [
        query
        for query in raw_queries
        if query_has_required_term(query, required_terms) and not is_generic_benchmark_search_term(query)
    ]
    return clean_string_list(anchored_queries)[:8]


def score_total(topic: dict[str, Any]) -> int:
    return int(safe_dict(topic.get("score_breakdown")).get("total_score", 0) or 0)


def source_interaction_metrics(topic: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    return {
        "heat_score": int(source.get("heat_score") or source.get("heat") or topic.get("max_heat_score") or 0),
        "velocity_score": int(source.get("velocity_score") or topic.get("max_velocity_score") or 0),
        "reddit_score": int(source.get("score") or source.get("ups") or 0),
        "comment_count": int(source.get("comments") or source.get("num_comments") or topic.get("top_comment_count") or 0),
        "source_count": int(topic.get("source_count", 0) or 0),
        "total_score": score_total(topic),
    }


def benchmark_interaction_level(metrics: dict[str, Any]) -> str:
    heat = int(metrics.get("heat_score", 0) or 0)
    velocity = int(metrics.get("velocity_score", 0) or 0)
    reddit_score = int(metrics.get("reddit_score", 0) or 0)
    comment_count = int(metrics.get("comment_count", 0) or 0)
    if comment_count >= 50 or reddit_score >= 100 or heat >= 80 or velocity >= 70:
        return "high"
    if comment_count >= 10 or reddit_score >= 25 or heat >= 50 or velocity >= 40:
        return "medium"
    return "thin"


def benchmark_fit(topic: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    interaction_level = benchmark_interaction_level(metrics)
    flags: list[str] = []
    if interaction_level == "thin":
        flags.append("needs_higher_interaction_reference")
    if int(topic.get("source_count", 0) or 0) < 2:
        flags.append("single_source_reference")
    if int(metrics.get("total_score", 0) or 0) < 60:
        flags.append("low_topic_heat")
    return {
        "interaction_level": interaction_level,
        "reference_role": "benchmark_candidate" if interaction_level in {"high", "medium"} else "discovery_lead_only",
        "flags": flags,
    }


def build_discovery_quality(contents: list[dict[str, Any]]) -> dict[str, Any]:
    levels = [clean_text(safe_dict(item.get("benchmark_fit")).get("interaction_level")) for item in contents]
    high_count = sum(1 for level in levels if level == "high")
    medium_count = sum(1 for level in levels if level == "medium")
    thin_count = sum(1 for level in levels if level == "thin")
    flags: list[str] = []
    if high_count == 0:
        flags.append("no_high_interaction_reference")
    if thin_count and thin_count == len(levels):
        flags.append("all_references_thin")
    return {
        "content_count": len(contents),
        "high_interaction_reference_count": high_count,
        "medium_interaction_reference_count": medium_count,
        "thin_reference_count": thin_count,
        "needs_interaction_enrichment": high_count == 0,
        "flags": flags,
    }


def build_benchmark_enrichment_request(candidate_index: dict[str, Any], selected_topic: dict[str, Any]) -> dict[str, Any]:
    discovery_quality = safe_dict(candidate_index.get("discovery_quality"))
    selected_title = clean_text(selected_topic.get("title")) or clean_text(safe_dict(safe_list(candidate_index.get("topics"))[0] if safe_list(candidate_index.get("topics")) else {}).get("title"))
    raw_keywords = clean_string_list(selected_topic.get("keywords"))[:8]
    required_terms = build_benchmark_required_terms(selected_title, raw_keywords)
    keywords = required_terms[:8]
    topic_titles = clean_string_list([topic.get("title") for topic in safe_list(candidate_index.get("topics")) if isinstance(topic, dict)])[:5]
    query_overrides = build_benchmark_enrichment_queries(selected_title, raw_keywords)
    relevance_filter = {
        "required_any_terms": required_terms,
        "generic_terms": sorted(GENERIC_BENCHMARK_SEARCH_TERMS),
        "reject_if_only_generic_keyword_hit": True,
        "min_required_term_hits": 1,
    }
    return {
        "contract_version": "benchmark_enrichment_request_v1",
        "policy": "structure_only_no_source_text_copy",
        "workflow_kind": "benchmark_enrichment_request",
        "needed": bool(discovery_quality.get("needs_interaction_enrichment")),
        "reason_flags": clean_string_list(discovery_quality.get("flags")),
        "source_priority_order": ["x_index", "opencli_bridge", "browser_session_search", "google-news-search"],
        "topic": selected_title,
        "candidate_titles": topic_titles,
        "acceptance_criteria": {
            "minimum_high_interaction_references": 2,
            "minimum_medium_or_high_references": 3,
            "required_fields": ["url", "title", "source", "published_at", "interaction_metrics", "topic", "viral_point", "adaptation_reason"],
        },
        "x_index_request": {
            "topic": selected_title,
            "keywords": keywords,
            "query_overrides": query_overrides,
            "relevance_filter": relevance_filter,
            "lookback": "7d",
            "max_candidates": 50,
            "max_kept_posts": 10,
            "browser_session": {
                "strategy": "remote_debugging",
                "cdp_endpoint": "http://127.0.0.1:9222",
                "required": False,
            },
        },
        "opencli_request": {
            "topic": selected_title,
            "use_case": "benchmark-enrichment",
            "queries": query_overrides,
            "relevance_filter": relevance_filter,
            "candidate_contract": "benchmark_candidate_index_v1",
        },
        "browser_search_request": {
            "topic": selected_title,
            "queries": query_overrides,
            "relevance_filter": relevance_filter,
            "purpose": "find high-interaction structural references without copying source text",
        },
    }


def viral_point(topic: dict[str, Any]) -> str:
    return (
        clean_text(topic.get("why_now"))
        or clean_text(topic.get("selection_reason"))
        or "High-heat topic with source confirmation and a visible interpretation gap."
    )


def adaptation_reason(topic: dict[str, Any]) -> str:
    return (
        clean_text(topic.get("recommended_angle"))
        or clean_text(topic.get("source_mix"))
        or "Use as a structure reference for hook, evidence order, and follow-up variables."
    )


BENCHMARK_GENERATION_MUST_LAND = [
    "Translate the analysis into a concrete reader payoff.",
    "Show the affected actors and the transmission path.",
    "End with two or three trackable variables.",
]

BENCHMARK_GENERATION_AVOID_PATTERNS = [
    "Do not end on a vague recap without variables to watch.",
    "Do not describe transmission without naming who is affected next.",
]

BENCHMARK_GENERATION_SLOT_GUIDANCE = {
    "lede": ["Start from the visible conflict, then name the practical variable readers should care about."],
    "impact": ["Name the affected actor first, then explain how the signal travels through pricing, demand, costs, trust, or policy."],
    "watch": ["Close with two or three variables that can confirm, weaken, or reprice the thesis."],
}

RUBRIC_DIMENSION_FEEDBACK = {
    "opening_hook": {
        "must_land": "Open with a clear conflict before explaining the background.",
        "slot": "lede",
        "guidance": "Make the first paragraph name the tension and the variable at stake.",
    },
    "single_mainline": {
        "must_land": "Keep one main question running through the article.",
        "slot": "facts",
        "guidance": "Use each evidence block to answer the same central question.",
    },
    "factual_restraint": {
        "must_land": "Separate confirmed facts from inference.",
        "slot": "facts",
        "guidance": "State what is confirmed before adding interpretation.",
    },
    "second_order_analysis": {
        "must_land": "Explain the second-order variable under the headline.",
        "slot": "impact",
        "guidance": "Move from what happened to what variable changes next.",
    },
    "industry_market_transmission": {
        "must_land": "Show the affected actors and the transmission path.",
        "slot": "impact",
        "guidance": "Name who is affected next and how the signal travels through supply, demand, pricing, cost, trust, or policy.",
    },
    "reader_payoff": {
        "must_land": "Translate the analysis into a concrete reader payoff.",
        "slot": "impact",
        "guidance": "Make clear what investors, operators, companies, or practitioners can watch or decide differently.",
    },
    "trackable_ending": {
        "must_land": "End with two or three trackable variables.",
        "slot": "watch",
        "guidance": "Close on variables that can confirm, weaken, or reprice the thesis.",
    },
}


def build_benchmark_generation_style_memory(viral_teardown: dict[str, Any]) -> dict[str, Any]:
    style_memory = safe_dict(viral_teardown.get("style_memory"))
    slot_guidance = {
        slot: clean_string_list(items)
        for slot, items in safe_dict(style_memory.get("slot_guidance")).items()
        if clean_string_list(items)
    }
    return {
        "must_land": clean_string_list(style_memory.get("must_land")),
        "avoid_patterns": clean_string_list(style_memory.get("avoid_patterns")),
        "slot_guidance": slot_guidance,
    }


def build_quality_feedback_controls(weakest_dimensions: list[dict[str, Any]]) -> dict[str, Any]:
    focus_keys: list[str] = []
    must_land: list[str] = []
    slot_guidance: dict[str, list[str]] = {}
    for dimension in weakest_dimensions:
        key = clean_text(dimension.get("key"))
        if not key:
            continue
        focus_keys.append(key)
        feedback = safe_dict(RUBRIC_DIMENSION_FEEDBACK.get(key))
        if not feedback:
            recommendation = clean_text(dimension.get("recommendation"))
            if recommendation:
                must_land.append(recommendation)
            continue
        must = clean_text(feedback.get("must_land"))
        if must:
            must_land.append(must)
        slot = clean_text(feedback.get("slot"))
        guidance = clean_text(feedback.get("guidance"))
        if slot and guidance:
            slot_guidance.setdefault(slot, [])
            if guidance not in slot_guidance[slot]:
                slot_guidance[slot].append(guidance)
    return {
        "style_memory_delta": {
            "target_band": "benchmark_quality_feedback",
            "must_land": clean_string_list(must_land),
            "avoid_patterns": clean_string_list(BENCHMARK_GENERATION_AVOID_PATTERNS),
            "slot_guidance": slot_guidance,
        },
        "prompt_controls": {
            "revision_mode": "benchmark_quality_loop",
            "apply_to_next_generation": True,
            "rubric_focus": focus_keys,
        },
    }


def build_benchmark_candidate_index(discovery_result: dict[str, Any], *, selected_title: str = "") -> dict[str, Any]:
    topics: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    for rank, topic_value in enumerate(safe_list(discovery_result.get("ranked_topics")), start=1):
        topic = safe_dict(topic_value)
        title = clean_text(topic.get("title"))
        source_items = [safe_dict(item) for item in safe_list(topic.get("source_items")) if isinstance(item, dict)]
        topics.append(
            {
                "rank": rank,
                "title": title,
                "topic": title,
                "score": score_total(topic),
                "heat_score": int(safe_dict(topic.get("score_breakdown")).get("heat", 0) or 0),
                "source_confirmation_score": int(safe_dict(topic.get("score_breakdown")).get("source_confirmation", 0) or 0),
                "source_count": int(topic.get("source_count", 0) or 0),
                "viral_point": viral_point(topic),
                "adaptation_reason": adaptation_reason(topic),
                "selected": clean_text(selected_title) == title,
            }
        )
        for source_index, source in enumerate(source_items or [topic], start=1):
            url = clean_text(source.get("url") or topic.get("url"))
            if not url:
                continue
            source_title = clean_text(source.get("title") or title)
            interaction_metrics = source_interaction_metrics(topic, source)
            contents.append(
                {
                    "content_id": f"B{rank:02d}-{source_index:02d}",
                    "topic_rank": rank,
                    "url": url,
                    "title": source_title,
                    "source": clean_text(source.get("source_name") or source.get("source") or "unknown"),
                    "author": clean_text(source.get("author") or source.get("reddit_author")),
                    "published_at": clean_text(source.get("published_at") or topic.get("latest_published_at")),
                    "interaction_metrics": interaction_metrics,
                    "benchmark_fit": benchmark_fit(topic, interaction_metrics),
                    "topic": title,
                    "viral_point": viral_point(topic),
                    "adaptation_reason": adaptation_reason(topic),
                    "source_type": clean_text(source.get("source_type")),
                }
            )
    return {
        "contract_version": "benchmark_candidate_index_v1",
        "policy": "structure_only_no_source_text_copy",
        "workflow_kind": "benchmark_candidate_index",
        "analysis_time": clean_text(discovery_result.get("analysis_time")),
        "source_priority": "repo_native_hot_topic_discovery",
        "discovery_quality": build_discovery_quality(contents),
        "topics": topics,
        "contents": contents,
    }


def evidence_order_from_topic(topic: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, source in enumerate([safe_dict(item) for item in safe_list(topic.get("source_items")) if isinstance(item, dict)], start=1):
        rows.append(
            {
                "position": index,
                "source": clean_text(source.get("source_name") or source.get("source") or "unknown"),
                "source_type": clean_text(source.get("source_type")),
                "evidence_role": (
                    "primary confirmation"
                    if index == 1
                    else ("debate or social proof" if clean_text(source.get("source_type")) == "social" else "secondary corroboration")
                ),
            }
        )
    return rows


def build_benchmark_viral_teardown(selected_topic: dict[str, Any], candidate_index: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(selected_topic.get("title"))
    watch_items = [
        "whether the core source confirmation strengthens",
        "whether the high-heat discussion converts into a second hard signal",
        "whether market or industry read-through becomes measurable",
    ]
    return {
        "contract_version": "benchmark_viral_teardown_v1",
        "policy": "structure_only_no_source_text_copy",
        "workflow_kind": "benchmark_viral_teardown",
        "topic": title,
        "title_hook": "Reframe the visible headline as a business or market judgment question.",
        "opening_conflict": clean_text(selected_topic.get("why_now")) or "Open from the tension between heat and confirmation.",
        "mainline": clean_text(selected_topic.get("recommended_angle")) or "Keep one question moving from confirmed fact to downstream consequence.",
        "evidence_order": evidence_order_from_topic(selected_topic),
        "paragraph_rhythm": [
            "short hook",
            "confirmed fact boundary",
            "second-order explanation",
            "transmission chain",
            "watchable variables",
        ],
        "second_order_judgment": "Explain what variable changes underneath the headline, not just that the topic is hot.",
        "ending_watch_items": watch_items,
        "style_memory": {
            "target_band": "benchmark_structure_commentary",
            "must_land": list(BENCHMARK_GENERATION_MUST_LAND),
            "avoid_patterns": list(BENCHMARK_GENERATION_AVOID_PATTERNS),
            "slot_guidance": {
                **BENCHMARK_GENERATION_SLOT_GUIDANCE,
            },
            "source_index_contract": clean_text(candidate_index.get("contract_version")),
        },
        "prompt_controls": {
            "article_framework": "deep_analysis",
            "draft_mode": "balanced",
            "rubric_focus": [
                "opening_hook",
                "single_mainline",
                "factual_restraint",
                "second_order_analysis",
                "industry_market_transmission",
                "reader_payoff",
                "trackable_ending",
            ],
        },
    }


def build_benchmark_quality_loop_artifact(
    *,
    news_request_path: Path,
    article_draft_path: str,
    publish_package_path: Path,
    benchmark_rubric: dict[str, Any],
    automatic_acceptance: dict[str, Any],
) -> dict[str, Any]:
    weakest = [safe_dict(item) for item in safe_list(benchmark_rubric.get("weakest_dimensions"))[:3]]
    suggestions = [
        clean_text(item.get("recommendation"))
        for item in weakest
        if clean_text(item.get("recommendation"))
    ]
    if not suggestions:
        suggestions = ["Keep the next generation pass anchored to the benchmark rubric and inspect the weakest three dimensions."]
    feedback_controls = build_quality_feedback_controls(weakest)
    return {
        "contract_version": "benchmark_quality_loop_v1",
        "policy": "structure_only_no_source_text_copy",
        "workflow_kind": "benchmark_quality_loop",
        "generation_request_path": str(news_request_path),
        "article_draft_path": clean_text(article_draft_path),
        "publish_package_path": str(publish_package_path),
        "rubric_score": int(benchmark_rubric.get("total_score", 0) or 0),
        "rubric_threshold": int(benchmark_rubric.get("threshold", 0) or 0),
        "rubric_passed": bool(benchmark_rubric.get("passed")),
        "weakest_dimensions": weakest,
        "improvement_suggestions": suggestions,
        "style_memory_delta": feedback_controls["style_memory_delta"],
        "prompt_controls": feedback_controls["prompt_controls"],
        "automatic_acceptance_status": clean_text(automatic_acceptance.get("status")),
    }


__all__ = [
    "build_benchmark_candidate_index",
    "build_benchmark_enrichment_request",
    "build_benchmark_generation_style_memory",
    "build_benchmark_quality_loop_artifact",
    "build_benchmark_viral_teardown",
]
