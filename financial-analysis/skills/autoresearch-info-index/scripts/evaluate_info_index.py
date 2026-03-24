#!/usr/bin/env python3
"""
Evaluate an information-index autoresearch run record.

This script is intentionally zero-dependency. It scores one run record for a
news/message indexing workflow and returns a keep-or-rollback decision.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path


HARD_CHECKS = [
    ("anchored_to_absolute_dates", "Relative timing was not anchored to absolute dates"),
    ("key_claims_traceable", "Key claims are not traceable to specific sources"),
    ("fact_and_inference_separated", "Facts and inference are mixed together"),
    ("conflicting_signals_disclosed", "Conflicting or missing confirmations were not disclosed"),
    ("source_recency_checked", "Source recency was not checked before writing the conclusion"),
]

SCORE_MAX = {
    "source_coverage": 25,
    "claim_traceability": 20,
    "recency_discipline": 20,
    "contradiction_handling": 15,
    "signal_extraction": 10,
    "retrieval_efficiency": 10,
}

REQUIRED_FIELDS = [
    "task_id",
    "sample_set_version",
    "task_goal",
    "baseline_version",
    "candidate_version",
    "last_stable_version",
    "hard_checks",
    "baseline_scores",
    "candidate_scores",
]

SOURCE_TYPE_WEIGHTS = {
    "official": 95,
    "official_statement": 95,
    "regulator_filing": 95,
    "company_filing": 95,
    "exchange_filing": 95,
    "government_release": 90,
    "government": 90,
    "official_release": 90,
    "official_calendar": 88,
    "wire": 85,
    "major_news": 78,
    "news": 70,
    "public_ais": 60,
    "public_ship_tracker": 60,
    "company_source": 68,
    "analysis": 60,
    "research_note": 60,
    "industry_blog": 45,
    "social": 35,
    "market_rumor": 20,
    "rumor": 20,
    "unknown": 50,
}

CLAIM_STATUS_SCORES = {
    "confirmed": 90,
    "confirmed_officially": 100,
    "confirmed_directly": 95,
    "confirmed_by_reporting": 75,
    "analytical_judgment": 50,
    "inferred": 45,
    "denied": 15,
    "not_confirmed": 35,
    "unclear": 30,
    "contradicted": 10,
}

SOURCE_STRENGTH_REFERENCE_BANDS = {
    "high": (80, 100),
    "medium-high": (70, 84),
    "medium": (55, 74),
    "mixed": (40, 64),
    "low": (0, 39),
}

AGREEMENT_REFERENCE_BANDS = {
    "aligned": (85, 100),
    "mostly-aligned": (70, 89),
    "mixed": (45, 74),
    "conflicted": (0, 54),
}


def load_input(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def require_fields(payload: dict) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def validate_score_block(name: str, scores: dict) -> None:
    missing = [key for key in SCORE_MAX if key not in scores]
    if missing:
        raise ValueError(f"{name} is missing score fields: {', '.join(missing)}")

    extra = [key for key in scores if key not in SCORE_MAX]
    if extra:
        raise ValueError(f"{name} contains unsupported score fields: {', '.join(extra)}")

    for key, maximum in SCORE_MAX.items():
        value = scores[key]
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name}.{key} must be numeric")
        if value < 0 or value > maximum:
            raise ValueError(f"{name}.{key} must be between 0 and {maximum}")


def total_score(scores: dict) -> int:
    return int(round(sum(scores.values())))


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        if len(text) == 10:
            try:
                parsed = datetime.fromisoformat(text + "T00:00:00+00:00")
            except ValueError:
                return None
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_iso_date(value: object) -> date | None:
    parsed = parse_iso_datetime(value)
    return parsed.date() if parsed else None


def list_of_dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def observation_key(source: dict) -> tuple[str, str, str]:
    source_id = str(source.get("source_id", "")).strip()
    url = str(source.get("url", "")).strip()
    name = str(source.get("source_name", source.get("name", ""))).strip().lower()
    return source_id, url, name


def build_observation_lookup(retrieval_result: dict) -> dict[str, dict[str, dict]]:
    lookup = {"by_id": {}, "by_url": {}, "by_name": {}}
    for item in list_of_dicts(retrieval_result.get("observations", [])):
        source_id, url, name = observation_key(item)
        if source_id and source_id not in lookup["by_id"]:
            lookup["by_id"][source_id] = item
        if url and url not in lookup["by_url"]:
            lookup["by_url"][url] = item
        if name and name not in lookup["by_name"]:
            lookup["by_name"][name] = item
    return lookup


def resolve_source_observation(source: dict, observation_lookup: dict[str, dict[str, dict]]) -> dict | None:
    source_id, url, name = observation_key(source)
    if source_id and source_id in observation_lookup["by_id"]:
        return observation_lookup["by_id"][source_id]
    if url and url in observation_lookup["by_url"]:
        return observation_lookup["by_url"][url]
    if name and name in observation_lookup["by_name"]:
        return observation_lookup["by_name"][name]
    return None


def resolve_source_datetime(source: dict, observation_lookup: dict[str, dict[str, dict]]) -> datetime | None:
    source_published = source.get("published_at")
    source_observed = source.get("observed_at")
    has_precise_time = (
        isinstance(source_published, str)
        and "T" in source_published
        or isinstance(source_observed, str)
        and "T" in source_observed
    )
    if has_precise_time:
        return parse_iso_datetime(source_published) or parse_iso_datetime(source_observed)

    matched = resolve_source_observation(source, observation_lookup)
    if isinstance(matched, dict):
        matched_dt = parse_iso_datetime(matched.get("published_at")) or parse_iso_datetime(matched.get("observed_at"))
        if matched_dt is not None:
            return matched_dt

    return parse_iso_datetime(source_published) or parse_iso_datetime(source_observed)


def parse_confidence_interval(value: object) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None

    low, high = value
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return None

    low_value = clamp(low)
    high_value = clamp(high)
    if low_value > high_value:
        low_value, high_value = high_value, low_value
    return low_value, high_value


def build_band_alignment(score: int, expected_band: tuple[int, int] | None) -> dict | None:
    if expected_band is None:
        return None

    expected_low, expected_high = expected_band
    within_band = expected_low <= score <= expected_high

    if within_band:
        distance = 0
    elif score < expected_low:
        distance = expected_low - score
    else:
        distance = score - expected_high

    return {
        "expected_low": expected_low,
        "expected_high": expected_high,
        "actual": score,
        "within_expected_band": within_band,
        "distance_from_band": distance,
    }


def default_source_strength(source: dict) -> int:
    explicit_strength = source.get("strength_score")
    if isinstance(explicit_strength, (int, float)):
        return clamp(explicit_strength)

    strength_label = str(source.get("strength", "")).strip().lower()
    if strength_label in {"very-high", "very_high"}:
        return 95
    if strength_label == "high":
        return 85
    if strength_label == "medium":
        return 65
    if strength_label == "low":
        return 35

    source_type = str(source.get("type", source.get("source_type", ""))).strip().lower() or "unknown"
    return SOURCE_TYPE_WEIGHTS.get(source_type, SOURCE_TYPE_WEIGHTS["unknown"])


def status_score(status: object) -> int:
    status_key = str(status).strip().lower()
    return CLAIM_STATUS_SCORES.get(status_key, CLAIM_STATUS_SCORES["unclear"])


def timeliness_score(analysis_time: datetime | None, published_at: datetime | None) -> int:
    if analysis_time is None or published_at is None:
        return 50

    if published_at > analysis_time:
        return 25

    age_minutes = max(0.0, (analysis_time - published_at).total_seconds() / 60.0)
    if age_minutes <= 10:
        return 100
    if age_minutes <= 60:
        return 95
    if age_minutes <= 360:
        return 85
    if age_minutes <= 1440:
        return 70
    if age_minutes <= 4320:
        return 55
    if age_minutes <= 10080:
        return 45
    return 25


def confidence_label(score: int, width: int) -> str:
    if score >= 85 and width <= 25:
        return "high"
    if score >= 60 and width <= 40:
        return "medium"
    return "low"


def build_credibility_metrics(payload: dict, hard_checks_passed: bool) -> dict:
    source_pack = payload.get("source_pack", {})
    if not isinstance(source_pack, dict):
        source_pack = {}
    retrieval_result = payload.get("retrieval_result", {})
    if not isinstance(retrieval_result, dict):
        retrieval_result = {}
    observation_lookup = build_observation_lookup(retrieval_result)

    sources = source_pack.get("sources", [])
    if not isinstance(sources, list):
        sources = []

    key_claims = source_pack.get("key_claims", [])
    if not isinstance(key_claims, list):
        key_claims = []

    analysis_time = parse_iso_datetime(
        retrieval_result.get("request", {}).get("analysis_time")
        or source_pack.get("analysis_date")
        or payload.get("analysis_date")
        or payload.get("as_of_date")
    )

    source_strength_values: list[int] = []
    source_timeliness_values: list[int] = []
    source_type_counts: dict[str, int] = {}

    for source in sources:
        if not isinstance(source, dict):
            continue

        source_type = str(source.get("type", source.get("source_type", ""))).strip().lower() or "unknown"
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

        strength = default_source_strength(source)
        source_strength_values.append(strength)

        published_at = resolve_source_datetime(source, observation_lookup)
        source_timeliness_values.append(timeliness_score(analysis_time, published_at))

    claim_scores: list[int] = []
    status_counts: dict[str, int] = {}
    confirmed_count = 0
    contradicted_count = 0
    not_confirmed_count = 0
    judgment_count = 0

    for claim in key_claims:
        if not isinstance(claim, dict):
            continue
        status = str(claim.get("status", "unclear")).strip().lower()
        status_counts[status] = status_counts.get(status, 0) + 1
        claim_scores.append(status_score(status))
        if status in {"confirmed_officially", "confirmed_directly", "confirmed_by_reporting"}:
            confirmed_count += 1
        elif status == "contradicted":
            contradicted_count += 1
        elif status == "not_confirmed":
            not_confirmed_count += 1
        elif status == "analytical_judgment":
            judgment_count += 1

    source_strength_score = clamp(average(source_strength_values) if source_strength_values else 50)
    timeliness = clamp(average(source_timeliness_values) if source_timeliness_values else 50)
    claim_confirmation = clamp(average(claim_scores) if claim_scores else 40)

    total_claims = len(claim_scores)
    if total_claims == 0:
        agreement = 40
        uncertainty_ratio = 0.6
    else:
        contradicted_ratio = contradicted_count / total_claims
        unconfirmed_ratio = not_confirmed_count / total_claims
        judgment_ratio = judgment_count / total_claims
        agreement = clamp(100 - contradicted_ratio * 70 - unconfirmed_ratio * 30 - judgment_ratio * 10)
        uncertainty_ratio = min(1.0, unconfirmed_ratio + judgment_ratio * 0.5 + contradicted_ratio)

    source_diversity_bonus = min(5, len(source_type_counts))
    confidence_score = clamp(
        source_strength_score * 0.35
        + claim_confirmation * 0.30
        + timeliness * 0.20
        + agreement * 0.15
        + source_diversity_bonus
    )

    source_count = max(len(source_strength_values), 1)
    width = clamp(
        8 + uncertainty_ratio * 15 + max(0, 10 - min(10, int(round(math.sqrt(source_count) * 4)))),
        low=5,
        high=35,
    )
    interval_low = clamp(confidence_score - width)
    interval_high = clamp(confidence_score + width)
    evidence_label = confidence_label(confidence_score, interval_high - interval_low)

    return {
        "source_strength_score": source_strength_score,
        "claim_confirmation_score": claim_confirmation,
        "timeliness_score": timeliness,
        "agreement_score": agreement,
        "confidence_score": confidence_score,
        "confidence_interval": {
            "low": interval_low,
            "high": interval_high,
            "width": interval_high - interval_low,
        },
        "confidence_label": evidence_label,
        "display_confidence_label": evidence_label if hard_checks_passed else "blocked",
        "confidence_scope": "evidence_only",
        "confidence_gate": {
            "hard_checks_passed": hard_checks_passed,
            "usable": hard_checks_passed,
            "status": "usable" if hard_checks_passed else "blocked_by_hard_checks",
        },
        "source_count": len(source_strength_values),
        "claim_count": total_claims,
        "status_counts": status_counts,
        "source_type_counts": source_type_counts,
    }


def build_retrieval_quality_metrics(payload: dict) -> dict:
    retrieval_result = payload.get("retrieval_result", {})
    if not isinstance(retrieval_result, dict):
        retrieval_result = {}
    observations = list_of_dicts(retrieval_result.get("observations", []))
    observation_lookup = build_observation_lookup(retrieval_result)
    observations_by_id = {
        str(item.get("source_id", "")).strip(): item
        for item in observations
        if str(item.get("source_id", "")).strip()
    }
    claim_ledger = list_of_dicts(retrieval_result.get("claim_ledger", []))

    explicit = retrieval_result.get("retrieval_quality", {})
    if isinstance(explicit, dict) and explicit:
        return {
            "freshness_capture_score": clamp(explicit.get("freshness_capture_score", 0)),
            "shadow_signal_discipline_score": clamp(explicit.get("shadow_signal_discipline_score", 0)),
            "source_promotion_discipline_score": clamp(explicit.get("source_promotion_discipline_score", 0)),
            "blocked_source_handling_score": clamp(explicit.get("blocked_source_handling_score", 0)),
        }

    run_report = retrieval_result.get("retrieval_run_report", {})
    if not isinstance(run_report, dict):
        run_report = {}
    verdict_output = retrieval_result.get("verdict_output", {})
    if not isinstance(verdict_output, dict):
        verdict_output = {}

    latest_signals = verdict_output.get("latest_signals", [])
    if not isinstance(latest_signals, list):
        latest_signals = []
    analysis_time = parse_iso_datetime(
        retrieval_result.get("request", {}).get("analysis_time")
        or payload.get("analysis_date")
        or payload.get("as_of_date")
    )

    freshness_hits = 0
    for item in latest_signals[:3]:
        if not isinstance(item, dict):
            continue
        age_minutes = item.get("age_minutes")
        if not isinstance(age_minutes, (int, float)):
            matched = resolve_source_observation(item, observation_lookup)
            if analysis_time is not None and isinstance(matched, dict):
                published_at = parse_iso_datetime(matched.get("published_at")) or parse_iso_datetime(matched.get("observed_at"))
                if published_at is not None:
                    age_minutes = max(0.0, (analysis_time - published_at).total_seconds() / 60.0)
        if isinstance(age_minutes, (int, float)) and float(age_minutes) <= 60:
            freshness_hits += 1
    freshness_capture_score = clamp(40 + freshness_hits * 20)

    shadow_signal_discipline_score = 100
    source_promotion_discipline_score = 100
    for claim in claim_ledger:
        supporting_sources = [
            observations_by_id[source_id]
            for source_id in claim.get("supporting_sources", [])
            if isinstance(source_id, str) and source_id in observations_by_id
        ]
        live_support = [item for item in supporting_sources if item.get("access_mode") != "blocked"]
        if claim.get("status") == "confirmed":
            if claim.get("promotion_state") != "core":
                shadow_signal_discipline_score -= 25
            if not live_support:
                shadow_signal_discipline_score -= 20
        if claim.get("promotion_state") == "core":
            unique_live_sources = {
                item.get("source_id") or item.get("url") or item.get("source_name")
                for item in live_support
                if item.get("source_id") or item.get("url") or item.get("source_name")
            }
            has_strong_support = any(int(item.get("source_tier", 3)) <= 1 for item in live_support)
            if not has_strong_support and len(unique_live_sources) < 2:
                source_promotion_discipline_score -= 20
            if supporting_sources and not live_support:
                source_promotion_discipline_score -= 10

    blocked_sources = list_of_dicts(run_report.get("sources_blocked", []))
    blocked_observations = [item for item in observations if item.get("access_mode") == "blocked"]
    blocked_visible_keys = {observation_key(item) for item in blocked_sources}
    hidden_blocked_count = sum(1 for item in blocked_observations if observation_key(item) not in blocked_visible_keys)
    blocked_used_in_core = sum(1 for item in blocked_observations if str(item.get("channel", "")).strip().lower() == "core")
    blocked_source_handling_score = 100
    if blocked_observations and not blocked_sources:
        blocked_source_handling_score -= 40
    blocked_source_handling_score -= hidden_blocked_count * 10
    blocked_source_handling_score -= blocked_used_in_core * 25

    return {
        "freshness_capture_score": freshness_capture_score,
        "shadow_signal_discipline_score": clamp(shadow_signal_discipline_score),
        "source_promotion_discipline_score": clamp(source_promotion_discipline_score),
        "blocked_source_handling_score": clamp(blocked_source_handling_score),
    }


def build_retrieval_observability(payload: dict) -> dict:
    retrieval_result = payload.get("retrieval_result", {})
    if not isinstance(retrieval_result, dict):
        retrieval_result = {}

    observations = list_of_dicts(retrieval_result.get("observations", []))
    observation_lookup = build_observation_lookup(retrieval_result)
    run_report = retrieval_result.get("retrieval_run_report", {})
    if not isinstance(run_report, dict):
        run_report = {}

    blocked_sources: list[dict] = []
    seen_keys: set[str] = set()

    def add_blocked_source(source: dict) -> None:
        source_id, url, name = observation_key(source)
        dedupe_key = source_id or url or name
        if dedupe_key in seen_keys:
            return
        seen_keys.add(dedupe_key)
        matched = resolve_source_observation(source, observation_lookup)
        blocked_sources.append(
            {
                "source_id": source_id,
                "source_name": str(
                    source.get("source_name")
                    or source.get("name")
                    or (matched.get("source_name") if isinstance(matched, dict) else "")
                ).strip(),
                "source_type": str(
                    source.get("source_type")
                    or source.get("type")
                    or (matched.get("source_type") if isinstance(matched, dict) else "")
                ).strip(),
                "url": url or (str(matched.get("url", "")).strip() if isinstance(matched, dict) else ""),
                "channel": str(source.get("channel") or (matched.get("channel") if isinstance(matched, dict) else "")).strip(),
                "access_mode": "blocked",
            }
        )

    for item in list_of_dicts(run_report.get("sources_blocked", [])):
        add_blocked_source(item)
    for item in observations:
        if item.get("access_mode") == "blocked":
            add_blocked_source(item)

    missing_expected_source_families = (
        [str(item).strip() for item in run_report.get("missed_expected_source_families", []) if str(item).strip()]
        if isinstance(run_report.get("missed_expected_source_families"), list)
        else []
    )

    return {
        "blocked_sources": blocked_sources,
        "blocked_source_count": len(blocked_sources),
        "blocked_sources_used_in_core": sum(1 for item in blocked_sources if item.get("channel") == "core"),
        "missing_expected_source_families": missing_expected_source_families,
        "missing_expected_source_family_count": len(missing_expected_source_families),
    }


def build_benchmark_alignment(payload: dict, credibility_metrics: dict) -> dict:
    reference = payload.get("credibility_reference")
    if not isinstance(reference, dict):
        source_item = payload.get("source_item", {})
        if isinstance(source_item, dict):
            reference = source_item.get("credibility_reference")

    if not isinstance(reference, dict) or not reference:
        return {"available": False}

    expected_confidence_band = parse_confidence_interval(reference.get("confidence_interval_pct"))
    expected_source_strength = SOURCE_STRENGTH_REFERENCE_BANDS.get(
        str(reference.get("source_strength", "")).strip().lower()
    )
    expected_agreement = AGREEMENT_REFERENCE_BANDS.get(
        str(reference.get("source_agreement", "")).strip().lower()
    )

    confidence_alignment = build_band_alignment(
        credibility_metrics.get("confidence_score", 0),
        expected_confidence_band,
    )
    source_strength_alignment = build_band_alignment(
        credibility_metrics.get("source_strength_score", 0),
        expected_source_strength,
    )
    agreement_alignment = build_band_alignment(
        credibility_metrics.get("agreement_score", 0),
        expected_agreement,
    )

    checks = [
        alignment
        for alignment in [confidence_alignment, source_strength_alignment, agreement_alignment]
        if alignment is not None
    ]
    passed_checks = sum(1 for alignment in checks if alignment["within_expected_band"])

    return {
        "available": True,
        "expected": {
            "source_strength": str(reference.get("source_strength", "")).strip(),
            "source_agreement": str(reference.get("source_agreement", "")).strip(),
            "confidence_interval_pct": list(expected_confidence_band) if expected_confidence_band else [],
            "expected_judgment": str(reference.get("expected_judgment", "")).strip(),
        },
        "actual": {
            "source_strength_score": credibility_metrics.get("source_strength_score", 0),
            "agreement_score": credibility_metrics.get("agreement_score", 0),
            "confidence_score": credibility_metrics.get("confidence_score", 0),
            "confidence_interval": credibility_metrics.get("confidence_interval", {}),
            "confidence_label": credibility_metrics.get("confidence_label", ""),
            "display_confidence_label": credibility_metrics.get("display_confidence_label", ""),
        },
        "checks_available": len(checks),
        "checks_passed": passed_checks,
        "all_available_checks_passed": bool(checks) and passed_checks == len(checks),
        "confidence_alignment": confidence_alignment,
        "source_strength_alignment": source_strength_alignment,
        "agreement_alignment": agreement_alignment,
    }


def evaluate_hard_checks(hard_checks: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for key, message in HARD_CHECKS:
        if key not in hard_checks:
            failures.append(f"Missing hard check: {key}")
            continue
        if not isinstance(hard_checks[key], bool):
            failures.append(f"Hard check {key} must be true or false")
            continue
        if not hard_checks[key]:
            failures.append(message)
    return (len(failures) == 0, failures)


def evaluate_stop_signal(payload: dict, candidate_total: int, baseline_total: int) -> dict:
    history = payload.get("history", {})
    min_improvement = payload.get("thresholds", {}).get("min_improvement", 2)
    target_success_rate = history.get("target_success_rate", 0.8)
    recent_success_rate = history.get("recent_success_rate")
    small_gain_rounds = history.get("consecutive_small_gain_rounds", 0)
    stale_source_rounds = history.get("consecutive_stale_source_rounds", 0)

    delta = candidate_total - baseline_total

    if small_gain_rounds >= 3 and delta < min_improvement:
        return {"reached": True, "reason": "Three consecutive low-gain rounds reached the stop threshold"}
    if stale_source_rounds >= 2:
        return {"reached": True, "reason": "Two consecutive rounds failed on source recency discipline"}
    if recent_success_rate is not None and recent_success_rate >= target_success_rate:
        return {"reached": True, "reason": "Recent success rate reached the target threshold"}

    return {"reached": False, "reason": "No stop condition reached"}


def build_result(payload: dict) -> dict:
    require_fields(payload)
    validate_score_block("baseline_scores", payload["baseline_scores"])
    validate_score_block("candidate_scores", payload["candidate_scores"])

    hard_passed, failures = evaluate_hard_checks(payload["hard_checks"])
    baseline_total = total_score(payload["baseline_scores"])
    candidate_total = total_score(payload["candidate_scores"])
    delta = candidate_total - baseline_total

    thresholds = payload.get("thresholds", {})
    min_improvement = thresholds.get("min_improvement", 2)
    large_regression = thresholds.get("large_regression", 5)
    severe_new_issue = bool(payload.get("severe_new_issue", False))
    credibility_metrics = build_credibility_metrics(payload, hard_passed)
    retrieval_quality_metrics = build_retrieval_quality_metrics(payload)
    retrieval_observability = build_retrieval_observability(payload)
    benchmark_alignment = build_benchmark_alignment(payload, credibility_metrics)

    dimension_rows = []
    for key, maximum in SCORE_MAX.items():
        baseline_value = payload["baseline_scores"][key]
        candidate_value = payload["candidate_scores"][key]
        dimension_rows.append(
            {
                "name": key,
                "score": candidate_value,
                "weight": maximum,
                "baseline": baseline_value,
                "delta": candidate_value - baseline_value,
            }
        )

    keep = hard_passed and not severe_new_issue and delta >= min_improvement

    if not hard_passed:
        reason = "Rollback because one or more hard checks failed"
    elif severe_new_issue:
        reason = "Rollback because the candidate introduced unsupported certainty"
    elif delta < min_improvement:
        reason = f"Rollback because score improved by {delta}, below the {min_improvement}-point threshold"
    else:
        reason = f"Keep because hard checks passed and score improved by {delta}"

    concerns = []
    if delta <= -large_regression:
        concerns.append(f"Large regression detected: score dropped by {abs(delta)} points")
    if severe_new_issue:
        concerns.append("Unsupported certainty or stale-source risk was flagged in the input")
    if benchmark_alignment.get("available") and not benchmark_alignment.get("all_available_checks_passed", True):
        concerns.append("Evidence confidence does not fully match the benchmark reference bands")

    return {
        "profile": "info-index",
        "task_id": payload["task_id"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "sample_set_version": payload["sample_set_version"],
        "task_goal": payload["task_goal"],
        "baseline_version": payload["baseline_version"],
        "candidate_version": payload["candidate_version"],
        "hard_checks": {
            "passed": hard_passed,
            "failures": failures,
        },
        "soft_scores": {
            "baseline_total": baseline_total,
            "candidate_total": candidate_total,
            "total": candidate_total,
            "delta": delta,
            "dimensions": dimension_rows,
        },
        "decision": {
            "keep": keep,
            "rollback_to": "" if keep else payload["last_stable_version"],
            "reason": reason,
            "concerns": concerns,
        },
        "credibility_metrics": credibility_metrics,
        "retrieval_quality_metrics": retrieval_quality_metrics,
        "retrieval_observability": retrieval_observability,
        "benchmark_alignment": benchmark_alignment,
        "stop_signal": evaluate_stop_signal(payload, candidate_total, baseline_total),
        "notes": {
            "winner_pattern": payload.get("winner_pattern", ""),
            "loser_pattern": payload.get("loser_pattern", ""),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate an information-index autoresearch run record and return a keep-or-rollback decision."
    )
    parser.add_argument("input", help="Path to a JSON run record")
    parser.add_argument("--output", help="Optional path to save the result JSON")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout JSON output and only write the requested file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        payload = load_input(Path(args.input))
        result = build_result(payload)
        if not args.quiet:
            print(json.dumps(result, indent=2))

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        sys.exit(0 if result["decision"]["keep"] else 2)
    except Exception as exc:
        error = {
            "status": "ERROR",
            "message": str(exc),
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
