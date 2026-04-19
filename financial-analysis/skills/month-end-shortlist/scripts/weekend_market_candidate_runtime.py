#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item for item in (_clean_text(value) for value in values) if item]


def _logic_level(value: int, *, high_at: int, medium_at: int = 1) -> str:
    if value >= high_at:
        return "high"
    if value >= medium_at:
        return "medium"
    return "low"


def _select_key_sources(candidate_input: dict[str, Any], top_topic: str) -> list[dict[str, str]]:
    key_sources: list[dict[str, str]] = []

    for row in candidate_input.get("x_seed_inputs", []):
        if top_topic not in row.get("tags", []):
            continue
        key_sources.append(
            {
                "source_name": _clean_text(row.get("display_name")) or _clean_text(row.get("handle")),
                "source_kind": "x_seed",
                "url": _clean_text(row.get("url")),
                "summary": f"Preferred seed concentrated on {top_topic}.",
            }
        )
        break

    for row in candidate_input.get("x_expansion_inputs", []):
        if top_topic not in row.get("theme_overlap", []):
            continue
        key_sources.append(
            {
                "source_name": _clean_text(row.get("handle")),
                "source_kind": "x_expansion",
                "url": _clean_text(row.get("url")),
                "summary": _clean_text(row.get("why_included")) or f"Expansion layer confirmed {top_topic}.",
            }
        )
        break

    for row in candidate_input.get("reddit_inputs", []):
        if top_topic not in row.get("theme_tags", []):
            continue
        key_sources.append(
            {
                "source_name": _clean_text(row.get("subreddit")),
                "source_kind": "reddit_confirmation",
                "url": _clean_text(row.get("thread_url")),
                "summary": _clean_text(row.get("thread_summary")) or f"Reddit discussion confirmed {top_topic}.",
            }
        )
        break

    return key_sources[:3]


def normalize_weekend_market_candidate_input(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    def normalize_seed(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        handle = _clean_text(row.get("handle"))
        if not handle:
            return None
        return {
            "handle": handle,
            "url": _clean_text(row.get("url")),
            "display_name": _clean_text(row.get("display_name")),
            "tags": _clean_list(row.get("tags")),
            "theme_aliases": deepcopy(row.get("theme_aliases")) if isinstance(row.get("theme_aliases"), dict) else {},
            "candidate_names": _clean_list(row.get("candidate_names")),
            "x_index_result_path": _clean_text(row.get("x_index_result_path")),
            "quality_hint": _clean_text(row.get("quality_hint")),
        }

    def normalize_expansion(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        handle = _clean_text(row.get("handle"))
        if not handle:
            return None
        return {
            "handle": handle,
            "url": _clean_text(row.get("url")),
            "why_included": _clean_text(row.get("why_included")),
            "theme_overlap": _clean_list(row.get("theme_overlap")),
            "candidate_names": _clean_list(row.get("candidate_names")),
            "quality_hint": _clean_text(row.get("quality_hint")),
            "x_index_result_path": _clean_text(row.get("x_index_result_path")),
        }

    def normalize_reddit(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        subreddit = _clean_text(row.get("subreddit"))
        summary = _clean_text(row.get("thread_summary"))
        if not subreddit and not summary:
            return None
        return {
            "subreddit": subreddit,
            "thread_url": _clean_text(row.get("thread_url")),
            "thread_summary": summary,
            "direction_hint": _clean_text(row.get("direction_hint")),
            "theme_tags": _clean_list(row.get("theme_tags")),
            "quality_hint": _clean_text(row.get("quality_hint")),
        }

    normalized = {
        "x_seed_inputs": [item for item in (normalize_seed(row) for row in raw.get("x_seed_inputs", [])) if item],
        "x_expansion_inputs": [item for item in (normalize_expansion(row) for row in raw.get("x_expansion_inputs", [])) if item],
        "reddit_inputs": [item for item in (normalize_reddit(row) for row in raw.get("reddit_inputs", [])) if item],
    }
    return normalized if any(normalized.values()) else None


def build_weekend_market_candidate(candidate_input: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(candidate_input, dict):
        return (
            {
                "candidate_topics": [],
                "beneficiary_chains": [],
                "headwind_chains": [],
                "priority_watch_directions": [],
                "signal_strength": "low",
                "evidence_summary": ["No usable weekend market candidate input was provided."],
                "x_seed_alignment": "none",
                "reddit_confirmation": "none",
                "status": "insufficient_signal",
            },
            [],
        )

    topic_counter: Counter[str] = Counter()
    reference_candidates: dict[str, list[str]] = {}

    for row in candidate_input.get("x_seed_inputs", []):
        for topic in row.get("tags", []):
            topic_counter[topic] += 3
            reference_candidates.setdefault(topic, []).extend(row.get("candidate_names", []))

    for row in candidate_input.get("x_expansion_inputs", []):
        for topic in row.get("theme_overlap", []):
            topic_counter[topic] += 1
            reference_candidates.setdefault(topic, []).extend(row.get("candidate_names", []))

    for row in candidate_input.get("reddit_inputs", []):
        for topic in row.get("theme_tags", []):
            topic_counter[topic] += 1

    if not topic_counter:
        return (
            {
                "candidate_topics": [],
                "beneficiary_chains": [],
                "headwind_chains": [],
                "priority_watch_directions": [],
                "signal_strength": "low",
                "evidence_summary": ["Weekend inputs did not converge on a usable A-share topic."],
                "x_seed_alignment": "low",
                "reddit_confirmation": "mixed",
                "status": "insufficient_signal",
            },
            [],
        )

    top_topic, top_score = topic_counter.most_common(1)[0]
    seed_count = sum(1 for row in candidate_input.get("x_seed_inputs", []) if top_topic in row.get("tags", []))
    expansion_count = sum(1 for row in candidate_input.get("x_expansion_inputs", []) if top_topic in row.get("theme_overlap", []))
    reddit_count = sum(1 for row in candidate_input.get("reddit_inputs", []) if top_topic in row.get("theme_tags", []))
    deduped_names = list(dict.fromkeys(name for name in reference_candidates.get(top_topic, []) if name))
    leaders = deduped_names[:2]
    high_beta_names = deduped_names[2:4]
    ranking_logic = {
        "seed_alignment": _logic_level(seed_count, high_at=2),
        "expansion_confirmation": _logic_level(expansion_count, high_at=1),
        "reddit_confirmation": _logic_level(reddit_count, high_at=1),
        "noise_or_disagreement": "low",
    }
    ranking_reason = (
        f"Preferred X seeds and confirmation layers aligned most clearly on {top_topic}, "
        "so it ranks first for Monday watch."
    )
    key_sources = _select_key_sources(candidate_input, top_topic)

    candidate = {
        "candidate_topics": [
            {
                "topic_name": top_topic,
                "topic_label": top_topic,
                "priority_rank": 1,
                "signal_strength": "high" if top_score >= 6 else "medium",
                "why_it_matters": "Preferred X seeds converged on the same weekend topic and expansion inputs reinforced it.",
                "monday_watch": f"Watch whether {top_topic} continues to lead on Monday open.",
                "ranking_logic": ranking_logic,
                "ranking_reason": ranking_reason,
                "key_sources": key_sources,
            }
        ],
        "beneficiary_chains": [top_topic],
        "headwind_chains": [],
        "priority_watch_directions": [top_topic],
        "signal_strength": "high" if top_score >= 6 else "medium",
        "evidence_summary": [
            "Preferred X seeds aligned on the same weekend direction.",
            "Reddit acted as confirmation instead of driving topic selection.",
        ],
        "x_seed_alignment": "high" if top_score >= 6 else "medium",
        "reddit_confirmation": "confirming",
        "status": "candidate_only",
    }
    direction_reference_map = [
        {
            "direction_key": top_topic,
            "direction_label": top_topic,
            "leaders": [{"ticker": "", "name": name} for name in leaders],
            "high_beta_names": [{"ticker": "", "name": name} for name in high_beta_names],
            "mapping_note": "Direction reference only. Not a formal execution layer.",
        }
    ]
    return candidate, direction_reference_map


__all__ = [
    "build_weekend_market_candidate",
    "normalize_weekend_market_candidate_input",
]
