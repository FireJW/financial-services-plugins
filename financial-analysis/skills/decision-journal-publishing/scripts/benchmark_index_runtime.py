#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AUTORESEARCH_SCRIPT_DIR = SCRIPT_DIR.parent.parent / "autoresearch-info-index" / "scripts"
if str(AUTORESEARCH_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUTORESEARCH_SCRIPT_DIR))

from news_index_runtime import load_json, parse_datetime, slugify, write_json


READ_BAND_ORDER = {
    "unknown": 0,
    "3w+": 1,
    "5w+": 2,
    "10w+": 3,
    "50w+": 4,
    "100w+": 5,
}

READ_BAND_SCORE = {
    "unknown": 0,
    "3w+": 30,
    "5w+": 42,
    "10w+": 62,
    "50w+": 82,
    "100w+": 95,
}

READ_BAND_ALIASES = {
    "3w+": "3w+",
    "5w+": "5w+",
    "10w+": "10w+",
    "50w+": "50w+",
    "100w+": "100w+",
}

PLATFORM_ALIASES = {
    "wechat": "wechat",
    "wx": "wechat",
    "mp": "wechat",
    "toutiao": "toutiao",
    "headline": "toutiao",
}

HIGH_TICKET_AUDIENCE_TOKENS = (
    "invest",
    "finance",
    "research",
    "institution",
    "operator",
    "trader",
    "portfolio",
    "professional",
    "market",
    "report",
    "wealth",
    "asset management",
)

METHOD_JARGON_TOKENS = (
    "template",
    "workflow",
    "prompt",
    "matrix",
    "framework",
)

PUBLIC_HOOK_TOKENS = (
    "why it matters",
    "what changed",
    "consequence",
    "affected",
    "question",
    "shock",
    "policy",
    "conflict",
)

DECISION_DENSE_TOKENS = (
    "must-read",
    "review",
    "signal",
    "scenario",
    "brief",
    "forensic",
    "decision",
)

PAID_LINKAGE_HIGH_TOKENS = (
    "subscription",
    "membership",
    "paid",
    "template",
    "report",
)

PAID_LINKAGE_MEDIUM_TOKENS = (
    "waitlist",
    "lead magnet",
    "download",
    "lite",
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = clean_text(item)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def normalize_platform(value: Any) -> str:
    text = clean_text(value).lower()
    return PLATFORM_ALIASES.get(text, text or "unknown")


def normalize_status(value: Any) -> str:
    text = clean_text(value).lower()
    return text or "reviewed"


def normalize_status_list(value: Any, *, default: list[str] | None = None) -> list[str]:
    defaults = default or ["reviewed"]
    raw_items = safe_list(value)
    if not raw_items:
        raw_items = defaults
    statuses = unique_keep_order([normalize_status(item) for item in raw_items if clean_text(item)])
    return statuses or defaults


def contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def coerce_score(value: Any, *, fallback: int = 0) -> int:
    if isinstance(value, (int, float)):
        return clamp(float(value))
    text = clean_text(value).lower()
    if not text:
        return fallback
    if text in {"high", "strong", "yes"}:
        return 85
    if text in {"medium", "mid"}:
        return 60
    if text in {"low", "weak", "no"}:
        return 30
    match = re.search(r"(\d+)", text)
    return clamp(float(match.group(1))) if match else fallback


def parse_read_count(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    text = clean_text(value).lower().replace(",", "")
    if not text:
        return None
    if text in READ_BAND_ALIASES:
        band = READ_BAND_ALIASES[text]
        if band == "3w+":
            return 30_000
        if band == "5w+":
            return 50_000
        if band == "10w+":
            return 100_000
        if band == "50w+":
            return 500_000
        if band == "100w+":
            return 1_000_000
    match = re.search(r"(\d+(?:\.\d+)?)\s*([a-z\u4e07\u4ebf]+)?\+?", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or ""
    multiplier = 1
    if unit in {"w", "\u4e07"}:
        multiplier = 10_000
    elif unit == "\u4ebf":
        multiplier = 100_000_000
    return int(amount * multiplier)


def band_for_read_count(count: int | None) -> str:
    if count is None:
        return "unknown"
    if count >= 1_000_000:
        return "100w+"
    if count >= 500_000:
        return "50w+"
    if count >= 100_000:
        return "10w+"
    if count >= 50_000:
        return "5w+"
    if count >= 30_000:
        return "3w+"
    return "unknown"


def normalize_read_band(value: Any) -> dict[str, Any]:
    count = parse_read_count(value)
    band = band_for_read_count(count)
    text = clean_text(value).lower()
    if band == "unknown" and text in READ_BAND_ALIASES:
        band = READ_BAND_ALIASES[text]
    return {
        "read_count_estimate": count,
        "read_band": band,
        "read_band_rank": READ_BAND_ORDER.get(band, 0),
        "read_strength_score": READ_BAND_SCORE.get(band, 0),
    }


def load_case_library(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    payload = load_json(path)
    cases = safe_list(payload.get("cases") or payload.get("items"))
    return {
        "path": str(path),
        "name": clean_text(payload.get("library_name") or path.stem),
        "version": clean_text(payload.get("version")),
        "default_request": safe_dict(payload.get("default_request")),
        "cases": cases,
    }


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    library_path = clean_text(raw_payload.get("library_path"))
    library: dict[str, Any] = {}
    cases = safe_list(raw_payload.get("cases") or raw_payload.get("items"))
    if not cases and library_path:
        library = load_case_library(library_path)
        cases = safe_list(library.get("cases"))
    if not cases:
        raise ValueError("benchmark-index requires cases[] or library_path")

    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None)
    if analysis_time is None:
        raise ValueError("benchmark-index requires analysis_time")

    defaults = safe_dict(library.get("default_request"))
    minimum_read_band = clean_text(raw_payload.get("minimum_read_band") or defaults.get("minimum_read_band") or "5w+").lower()
    if minimum_read_band not in READ_BAND_ORDER:
        raise ValueError("minimum_read_band must be one of unknown, 3w+, 5w+, 10w+, 50w+, 100w+")

    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "benchmark-index" / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )

    return {
        "analysis_time": analysis_time,
        "goal": clean_text(raw_payload.get("goal") or defaults.get("goal")),
        "commercial_center": clean_text(
            raw_payload.get("commercial_center")
            or raw_payload.get("target_audience")
            or defaults.get("commercial_center")
            or defaults.get("target_audience")
        ),
        "minimum_read_band": minimum_read_band,
        "strict_read_gate": bool(raw_payload.get("strict_read_gate", defaults.get("strict_read_gate", False))),
        "allow_below_threshold_commercial_exceptions": bool(
            raw_payload.get(
                "allow_below_threshold_commercial_exceptions",
                defaults.get("allow_below_threshold_commercial_exceptions", True),
            )
        ),
        "allow_unreviewed_qualification": bool(
            raw_payload.get("allow_unreviewed_qualification", defaults.get("allow_unreviewed_qualification", False))
        ),
        "include_curation_statuses": normalize_status_list(
            raw_payload.get("include_curation_statuses") or defaults.get("include_curation_statuses"),
            default=["reviewed"],
        ),
        "prefer_machine_read_signal": bool(
            raw_payload.get("prefer_machine_read_signal", defaults.get("prefer_machine_read_signal", True))
        ),
        "platforms": [
            normalize_platform(item)
            for item in safe_list(raw_payload.get("platforms") or defaults.get("platforms"))
            if clean_text(item)
        ],
        "cases": cases,
        "library": library,
        "output_dir": output_dir,
    }


def infer_publicness(case: dict[str, Any], read_strength_score: int) -> int:
    manual = coerce_score(case.get("publicness_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join(
        [
            clean_text(case.get("title")),
            clean_text(case.get("hook_type")),
            clean_text(case.get("topic_type")),
            clean_text(case.get("affected_group")),
        ]
    )
    score = 35 + read_strength_score * 0.4
    if contains_any(text, PUBLIC_HOOK_TOKENS):
        score += 18
    if contains_any(text, METHOD_JARGON_TOKENS):
        score -= 18
    if clean_text(case.get("affected_group")):
        score += 8
    return clamp(score)


def infer_decision_density(case: dict[str, Any]) -> int:
    manual = coerce_score(case.get("decision_density_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join(
        [
            clean_text(case.get("title")),
            clean_text(case.get("topic_type")),
            clean_text(case.get("account_positioning")),
            clean_text(case.get("notes")),
        ]
    )
    score = 40
    if contains_any(text, DECISION_DENSE_TOKENS):
        score += 22
    if contains_any(text, HIGH_TICKET_AUDIENCE_TOKENS):
        score += 14
    if contains_any(text, METHOD_JARGON_TOKENS):
        score += 10
    if "gossip" in text.lower():
        score -= 18
    return clamp(score)


def infer_audience_fit(case: dict[str, Any], commercial_center: str) -> int:
    manual = coerce_score(case.get("audience_fit_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join(
        [
            clean_text(case.get("account_positioning")),
            clean_text(case.get("topic_type")),
            clean_text(case.get("notes")),
            clean_text(commercial_center),
        ]
    )
    score = 35
    if contains_any(text, HIGH_TICKET_AUDIENCE_TOKENS):
        score += 28
    if "retail" in text.lower():
        score += 8
    if "gossip" in text.lower():
        score -= 15
    return clamp(score)


def infer_paid_linkage(case: dict[str, Any]) -> int:
    manual = coerce_score(case.get("paid_linkage_score") or case.get("paid_asset_linkage"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join(
        [
            clean_text(case.get("cta_type")),
            clean_text(case.get("paid_asset_linkage")),
            clean_text(case.get("notes")),
        ]
    )
    score = 20
    if contains_any(text, PAID_LINKAGE_HIGH_TOKENS):
        score += 55
    elif contains_any(text, PAID_LINKAGE_MEDIUM_TOKENS):
        score += 30
    if "none" in text.lower():
        score = min(score, 25)
    return clamp(score)


def infer_cta_strength(case: dict[str, Any]) -> int:
    manual = coerce_score(case.get("cta_strength_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join([clean_text(case.get("cta_type")), clean_text(case.get("paid_asset_linkage"))])
    if contains_any(text, PAID_LINKAGE_HIGH_TOKENS):
        return 82
    if contains_any(text, PAID_LINKAGE_MEDIUM_TOKENS):
        return 58
    if not text or "none" in text.lower():
        return 25
    return 45


def infer_hook_clarity(case: dict[str, Any]) -> int:
    manual = coerce_score(case.get("hook_clarity_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join([clean_text(case.get("title")), clean_text(case.get("hook_type"))])
    score = 42
    if contains_any(text, PUBLIC_HOOK_TOKENS):
        score += 24
    if clean_text(case.get("affected_group")):
        score += 8
    if contains_any(text, METHOD_JARGON_TOKENS):
        score -= 20
    return clamp(score)


def build_copy_signals(case: dict[str, Any], normalized_case: dict[str, Any]) -> list[str]:
    generated: list[str] = []
    if normalized_case["publicness_score"] >= 75:
        generated.append("Lead the wrapper with the consequence or affected group before method.")
    if clean_text(case.get("affected_group")):
        generated.append(f"Anchor the opening around '{clean_text(case.get('affected_group'))}'.")
    if normalized_case["decision_density_score"] >= 72:
        generated.append("Keep the high-density judgment structure instead of generic commentary.")
    if normalized_case["paid_linkage_score"] >= 70 or normalized_case["cta_strength_score"] >= 70:
        generated.append("Point the free post toward a reusable paid asset, not just a follow CTA.")
    if normalized_case["platform"] == "toutiao" and normalized_case["acquisition_score"] >= 70:
        generated.append("On Toutiao, lead the headline with consequence, conflict, or who gets hit.")
    if normalized_case["platform"] == "wechat" and normalized_case["commercial_fit_score"] >= 70:
        generated.append("On WeChat, use the post as the trust, archive, and conversion layer.")
    return unique_keep_order(safe_list(case.get("copy_signals")) + generated)


def build_avoid_signals(case: dict[str, Any], normalized_case: dict[str, Any]) -> list[str]:
    generated: list[str] = []
    title = clean_text(case.get("title"))
    if contains_any(title, METHOD_JARGON_TOKENS):
        generated.append("Do not lead the external headline with method jargon.")
    if normalized_case["acquisition_score"] >= 72 and normalized_case["commercial_fit_score"] < 60:
        generated.append("Do not confuse high traffic with high willingness to pay.")
    if normalized_case["paid_linkage_score"] < 45:
        generated.append("Do not copy only the outer wrapper while missing the conversion asset.")
    if "gossip" in clean_text(case.get("notes")).lower():
        generated.append("Do not copy gossip framing or personality-heavy packaging.")
    return unique_keep_order(safe_list(case.get("avoid_signals")) + generated)


def classify_reviewed_case(
    acquisition_score: int,
    commercial_fit_score: int,
    meets_threshold: bool,
    allow_exception: bool,
) -> tuple[str, str]:
    if acquisition_score >= 70 and commercial_fit_score >= 70:
        label = "mixed"
    elif acquisition_score >= 70:
        label = "acquisition"
    elif commercial_fit_score >= 70:
        label = "commercial-fit"
    elif acquisition_score >= 60 or commercial_fit_score >= 60:
        label = "watchlist"
    else:
        label = "reject"

    if meets_threshold:
        return (label, "qualified") if label != "reject" else (label, "rejected")

    if allow_exception and commercial_fit_score >= 70 and label in {"commercial-fit", "mixed", "watchlist"}:
        return ("commercial-fit" if label == "watchlist" else label, "qualified_exception")

    return label, "rejected_threshold"


def build_review_summary(case: dict[str, Any]) -> str:
    if case["qualification_status"] == "unreviewed_candidate":
        suggestion = clean_text(case.get("suggested_classification")) or "candidate"
        return (
            f"candidate / unreviewed; suggested {suggestion}; "
            f"read {case['read_band']}; acq {case['acquisition_score']}; comm {case['commercial_fit_score']}"
        )
    parts = [f"{case['classification']} / {case['qualification_status']}"]
    if case["read_band"] != "unknown":
        parts.append(f"read {case['read_band']}")
    parts.append(f"acq {case['acquisition_score']}")
    parts.append(f"comm {case['commercial_fit_score']}")
    if case["qualification_status"] == "qualified_exception":
        parts.append("kept as a below-threshold commercial exception")
    return "; ".join(parts)


def resolve_machine_state(case: dict[str, Any]) -> dict[str, Any]:
    return safe_dict(case.get("machine_state"))


def is_human_locked(case: dict[str, Any], field_name: str) -> bool:
    locks = safe_dict(case.get("human_locks"))
    return bool(locks.get(field_name, False))


def resolve_title(case: dict[str, Any]) -> tuple[str, str]:
    curated = clean_text(case.get("title"))
    if curated:
        return curated, "curated.title"
    if is_human_locked(case, "title"):
        return "", ""
    machine_title = clean_text(resolve_machine_state(case).get("current_title"))
    if machine_title:
        return machine_title, "machine_state.current_title"
    return "", ""


def resolve_published_at(case: dict[str, Any]) -> tuple[str, str]:
    curated = clean_text(case.get("published_at"))
    if curated:
        return curated, "curated.published_at"
    if is_human_locked(case, "published_at"):
        return "", ""
    machine_published = clean_text(resolve_machine_state(case).get("current_published_at"))
    if machine_published:
        return machine_published, "machine_state.current_published_at"
    return "", ""


def resolve_read_signal(case: dict[str, Any], request: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    machine = resolve_machine_state(case)
    machine_signal = clean_text(machine.get("current_read_signal"))
    curated_signal = clean_text(case.get("read_signal") or case.get("read_count") or case.get("reads"))
    if is_human_locked(case, "read_signal"):
        if curated_signal:
            return curated_signal, normalize_read_band(curated_signal), "curated.read_signal"
        return "", normalize_read_band(""), ""
    if request["prefer_machine_read_signal"] and machine_signal:
        return machine_signal, normalize_read_band(machine_signal), "machine_state.current_read_signal"
    if curated_signal:
        return curated_signal, normalize_read_band(curated_signal), "curated.read_signal"
    machine_count = machine.get("current_read_count_estimate")
    if machine_count not in {"", None}:
        return clean_text(machine_count), normalize_read_band(machine_count), "machine_state.current_read_count_estimate"
    return "", normalize_read_band(""), ""


def normalize_case(case: dict[str, Any], request: dict[str, Any], index: int) -> dict[str, Any]:
    platform = normalize_platform(case.get("platform"))
    curation_status = normalize_status(case.get("curation_status"))
    title, title_source = resolve_title(case)
    published_at_value, published_at_source = resolve_published_at(case)
    read_signal, read_meta, read_source = resolve_read_signal(case, request)

    threshold_rank = READ_BAND_ORDER[request["minimum_read_band"]]
    meets_threshold = read_meta["read_band_rank"] >= threshold_rank if threshold_rank > 0 else True

    working_case = dict(case)
    working_case["title"] = title
    working_case["published_at"] = published_at_value
    working_case["read_signal"] = read_signal

    publicness_score = infer_publicness(working_case, read_meta["read_strength_score"])
    decision_density_score = infer_decision_density(working_case)
    audience_fit_score = infer_audience_fit(working_case, request["commercial_center"])
    paid_linkage_score = infer_paid_linkage(working_case)
    cta_strength_score = infer_cta_strength(working_case)
    hook_clarity_score = infer_hook_clarity(working_case)

    acquisition_score = clamp(
        average([read_meta["read_strength_score"], publicness_score, hook_clarity_score]) + (5 if platform == "toutiao" else 0)
    )
    commercial_fit_score = clamp(
        average([decision_density_score, audience_fit_score, paid_linkage_score, cta_strength_score]) + (5 if platform == "wechat" else 0)
    )

    suggested_classification, suggested_qualification_status = classify_reviewed_case(
        acquisition_score,
        commercial_fit_score,
        meets_threshold,
        request["allow_below_threshold_commercial_exceptions"] and not request["strict_read_gate"],
    )

    if curation_status != "reviewed" and not request["allow_unreviewed_qualification"]:
        classification = "candidate" if curation_status == "candidate" else curation_status
        qualification_status = "unreviewed_candidate" if curation_status == "candidate" else f"unreviewed_{curation_status}"
    else:
        classification = suggested_classification
        qualification_status = suggested_qualification_status

    published_at = parse_datetime(published_at_value, fallback=None)
    normalized = {
        "index": index,
        "case_id": clean_text(case.get("case_id")) or slugify(clean_text(case.get("account_name")) or f"case-{index:02d}", f"case-{index:02d}"),
        "platform": platform,
        "curation_status": curation_status,
        "account_name": clean_text(case.get("account_name")),
        "title": title,
        "url": clean_text(case.get("url")),
        "canonical_url": clean_text(case.get("canonical_url") or case.get("url")),
        "published_at": published_at.isoformat() if published_at else "",
        "published_at_source": published_at_source,
        "read_signal": read_signal,
        "read_signal_source": read_source,
        "read_count_estimate": read_meta["read_count_estimate"],
        "read_band": read_meta["read_band"],
        "read_band_rank": read_meta["read_band_rank"],
        "meets_threshold": meets_threshold,
        "account_positioning": clean_text(case.get("account_positioning")),
        "topic_type": clean_text(case.get("topic_type")),
        "hook_type": clean_text(case.get("hook_type")),
        "affected_group": clean_text(case.get("affected_group")),
        "cta_type": clean_text(case.get("cta_type")),
        "notes": clean_text(case.get("notes")),
        "publicness_score": publicness_score,
        "decision_density_score": decision_density_score,
        "audience_fit_score": audience_fit_score,
        "paid_linkage_score": paid_linkage_score,
        "cta_strength_score": cta_strength_score,
        "hook_clarity_score": hook_clarity_score,
        "acquisition_score": acquisition_score,
        "commercial_fit_score": commercial_fit_score,
        "classification": classification,
        "qualification_status": qualification_status,
        "suggested_classification": suggested_classification if classification != suggested_classification else "",
        "suggested_qualification_status": (
            suggested_qualification_status if qualification_status != suggested_qualification_status else ""
        ),
        "value_sources": {
            "title": title_source,
            "published_at": published_at_source,
            "read_signal": read_source,
        },
    }
    normalized["copy_signals"] = build_copy_signals(working_case, normalized)
    normalized["avoid_signals"] = build_avoid_signals(working_case, normalized)
    normalized["review_summary"] = build_review_summary(normalized)
    return normalized


def sort_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        cases,
        key=lambda case: (
            1 if case["qualification_status"] in {"qualified", "qualified_exception"} else 0,
            1 if case["qualification_status"] == "unreviewed_candidate" else 0,
            max(case["acquisition_score"], case["commercial_fit_score"]),
            case["read_band_rank"],
        ),
        reverse=True,
    )


def pool_cases(cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pools = {
        "acquisition": [],
        "commercial_fit": [],
        "mixed": [],
        "watchlist": [],
        "candidates": [],
        "rejected": [],
    }
    for case in cases:
        if case["qualification_status"] == "unreviewed_candidate":
            pools["candidates"].append(case)
        elif case["classification"] == "mixed" and case["qualification_status"] in {"qualified", "qualified_exception"}:
            pools["mixed"].append(case)
        elif case["classification"] == "acquisition" and case["qualification_status"] in {"qualified", "qualified_exception"}:
            pools["acquisition"].append(case)
        elif case["classification"] == "commercial-fit" and case["qualification_status"] in {"qualified", "qualified_exception"}:
            pools["commercial_fit"].append(case)
        elif case["classification"] == "watchlist" and case["qualification_status"] in {"qualified", "qualified_exception"}:
            pools["watchlist"].append(case)
        else:
            pools["rejected"].append(case)
    for key in pools:
        pools[key] = sort_cases(pools[key])
    return pools


def build_strategy_implications(cases: list[dict[str, Any]]) -> list[str]:
    qualified = [case for case in cases if case["qualification_status"] in {"qualified", "qualified_exception"}]
    if not qualified:
        return ["No reviewed benchmark cases passed the current qualification gates."]

    implications: list[str] = []
    if any(case["qualification_status"] == "qualified_exception" for case in qualified):
        implications.append("Keep below-threshold commercial exceptions, but track them separately from true read-threshold wins.")

    toutiao_cases = [case for case in qualified if case["platform"] == "toutiao"]
    wechat_cases = [case for case in qualified if case["platform"] == "wechat"]
    if toutiao_cases and average([case["acquisition_score"] for case in toutiao_cases]) >= 70:
        implications.append("Toutiao is still the best cold-start wrapper for consequence-led packaging and angle testing.")
    if wechat_cases and average([case["commercial_fit_score"] for case in wechat_cases]) >= 70:
        implications.append("WeChat remains the best trust, archive, and paid-conversion layer for this account shape.")
    if any(case["commercial_fit_score"] >= 75 and case["paid_linkage_score"] >= 70 for case in qualified):
        implications.append("The best commercial cases sell repeated decision efficiency, not more hot takes.")
    if any(case["acquisition_score"] >= 75 and case["commercial_fit_score"] < 60 for case in qualified):
        implications.append("Treat traffic-heavy cases as packaging benchmarks, not product-direction benchmarks.")
    return unique_keep_order(implications)


def build_report_section(title: str, cases: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not cases:
        lines.extend(["- none", ""])
        return lines
    for case in cases:
        label = f"{case['account_name']} | {case['title']}".strip(" |")
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Platform: {case['platform']}",
                f"- Curation status: {case['curation_status']}",
                f"- URL: {case['url'] or 'n/a'}",
                f"- Published at: {case['published_at'] or 'unknown'}",
                f"- Read band: {case['read_band']}",
                f"- Classification: {case['classification']} ({case['qualification_status']})",
                f"- Scores: acquisition {case['acquisition_score']} / commercial {case['commercial_fit_score']} / decision density {case['decision_density_score']}",
                f"- Copy: {'; '.join(case['copy_signals']) or 'n/a'}",
                f"- Avoid: {'; '.join(case['avoid_signals']) or 'n/a'}",
                f"- Notes: {case['notes'] or 'n/a'}",
                "",
            ]
        )
    return lines


def build_queue_item(case: dict[str, Any], request: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = normalize_case(case, request, index)
    return {
        "case_id": normalized["case_id"],
        "platform": normalized["platform"],
        "account_name": normalized["account_name"],
        "title": normalized["title"],
        "url": normalized["url"],
        "canonical_url": normalized["canonical_url"],
        "curation_status": normalized["curation_status"],
        "published_at": normalized["published_at"],
        "read_band": normalized["read_band"],
        "read_signal": normalized["read_signal"],
        "review_summary": normalized["review_summary"],
    }


def build_candidate_queue_section(cases: list[dict[str, Any]]) -> list[str]:
    lines = ["## Candidate Queue (Excluded From Reviewed Benchmark Counts)", ""]
    if not cases:
        lines.extend(["- none", ""])
        return lines
    for case in cases:
        label = f"{case['account_name']} | {case['title']}".strip(" |")
        lines.append(f"- {label} | {case['platform']} | {case['read_band']} | {case['review_summary']} | {case['url'] or 'n/a'}")
    lines.append("")
    return lines


def build_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("summary"))
    pools = safe_dict(result.get("pools"))
    library = safe_dict(result.get("case_library"))
    review_scope = safe_dict(result.get("review_scope"))
    lines = [
        "# Benchmark Index Report",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Goal: {clean_text(result.get('goal')) or 'benchmark review'}",
        f"- Commercial center: {clean_text(result.get('commercial_center')) or 'n/a'}",
        f"- Minimum read band: {clean_text(result.get('minimum_read_band'))}",
        f"- Case library: {clean_text(library.get('name')) or 'direct cases'}",
        f"- Included curation statuses: {', '.join(safe_list(review_scope.get('include_curation_statuses'))) or 'reviewed'}",
        f"- Cases loaded: {summary.get('loaded_cases', 0)}",
        f"- Cases considered: {summary.get('considered_cases', 0)}",
        f"- Reviewed cases considered: {summary.get('reviewed_cases_considered', 0)}",
        f"- Threshold-qualified reviewed cases: {summary.get('threshold_qualified_cases', 0)}",
        f"- Exception-qualified reviewed cases: {summary.get('exception_qualified_cases', 0)}",
        f"- Candidate cases considered: {summary.get('candidate_cases_considered', 0)}",
        f"- Candidate queue excluded: {summary.get('candidate_queue_excluded', 0)}",
        "",
        "## Strategy Implications",
        "",
    ]
    for item in safe_list(result.get("strategy_implications")):
        lines.append(f"- {clean_text(item)}")
    lines.append("")
    if safe_dict(review_scope.get("excluded_status_counts")):
        lines.extend(["## Excluded Status Counts", ""])
        for status, count in safe_dict(review_scope.get("excluded_status_counts")).items():
            lines.append(f"- {status}: {count}")
        lines.append("")
    lines.extend(build_report_section("Mixed Benchmarks", safe_list(pools.get("mixed"))))
    lines.extend(build_report_section("Acquisition Benchmarks", safe_list(pools.get("acquisition"))))
    lines.extend(build_report_section("Commercial-Fit Benchmarks", safe_list(pools.get("commercial_fit"))))
    lines.extend(build_report_section("Watchlist", safe_list(pools.get("watchlist"))))
    lines.extend(build_report_section("Candidate / Unreviewed Cases", safe_list(pools.get("candidates"))))
    lines.extend(build_report_section("Rejected Cases", safe_list(pools.get("rejected"))))
    lines.extend(build_candidate_queue_section(safe_list(result.get("candidate_queue"))))
    return "\n".join(lines).strip() + "\n"


def filter_cases_for_request(request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    platforms = set(request["platforms"])
    include_statuses = set(request["include_curation_statuses"])
    loaded_cases: list[dict[str, Any]] = []
    considered_cases: list[dict[str, Any]] = []
    excluded_status_counts: Counter[str] = Counter()

    for raw_case in request["cases"]:
        case = safe_dict(raw_case)
        platform = normalize_platform(case.get("platform"))
        if platforms and platform not in platforms:
            continue
        loaded_cases.append(case)
        status = normalize_status(case.get("curation_status"))
        if status in include_statuses:
            considered_cases.append(case)
        else:
            excluded_status_counts[status] += 1

    return loaded_cases, considered_cases, dict(excluded_status_counts)


def run_benchmark_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    loaded_cases, considered_cases, excluded_status_counts = filter_cases_for_request(request)
    normalized_cases = [normalize_case(case, request, index + 1) for index, case in enumerate(considered_cases)]
    normalized_cases = sort_cases(normalized_cases)
    pools = pool_cases(normalized_cases)
    included_statuses = set(request["include_curation_statuses"])
    candidate_queue = [
        build_queue_item(case, request, index + 1)
        for index, case in enumerate(loaded_cases)
        if normalize_status(case.get("curation_status")) == "candidate" and "candidate" not in included_statuses
    ]

    result = {
        "status": "ok",
        "workflow_kind": "benchmark_index",
        "analysis_time": request["analysis_time"].isoformat(),
        "goal": request["goal"],
        "commercial_center": request["commercial_center"],
        "minimum_read_band": request["minimum_read_band"],
        "strict_read_gate": request["strict_read_gate"],
        "allow_below_threshold_commercial_exceptions": request["allow_below_threshold_commercial_exceptions"],
        "allow_unreviewed_qualification": request["allow_unreviewed_qualification"],
        "case_library": {
            "path": clean_text(safe_dict(request.get("library")).get("path")),
            "name": clean_text(safe_dict(request.get("library")).get("name")),
            "version": clean_text(safe_dict(request.get("library")).get("version")),
        },
        "review_scope": {
            "include_curation_statuses": request["include_curation_statuses"],
            "platforms": request["platforms"],
            "excluded_status_counts": excluded_status_counts,
        },
        "summary": {
            "loaded_cases": len(loaded_cases),
            "considered_cases": len(normalized_cases),
            "reviewed_cases_considered": sum(1 for case in normalized_cases if case["curation_status"] == "reviewed"),
            "threshold_qualified_cases": sum(1 for case in normalized_cases if case["qualification_status"] == "qualified"),
            "exception_qualified_cases": sum(1 for case in normalized_cases if case["qualification_status"] == "qualified_exception"),
            "candidate_cases_considered": sum(1 for case in normalized_cases if case["qualification_status"] == "unreviewed_candidate"),
            "candidate_queue_excluded": len(candidate_queue),
            "mixed_cases": len(pools["mixed"]),
            "acquisition_cases": len(pools["acquisition"]),
            "commercial_fit_cases": len(pools["commercial_fit"]),
            "watchlist_cases": len(pools["watchlist"]),
            "candidate_cases": len(pools["candidates"]),
            "rejected_cases": len(pools["rejected"]),
        },
        "cases": normalized_cases,
        "pools": pools,
        "candidate_queue": candidate_queue,
    }
    result["strategy_implications"] = build_strategy_implications(normalized_cases)
    result["report_markdown"] = build_report(result)
    report_path = request["output_dir"] / "benchmark-index-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8")
    result["report_path"] = str(report_path)

    request_path = request["output_dir"] / "benchmark-index-request.normalized.json"
    write_json(
        request_path,
        {
            "analysis_time": request["analysis_time"].isoformat(),
            "goal": request["goal"],
            "commercial_center": request["commercial_center"],
            "minimum_read_band": request["minimum_read_band"],
            "strict_read_gate": request["strict_read_gate"],
            "allow_below_threshold_commercial_exceptions": request["allow_below_threshold_commercial_exceptions"],
            "allow_unreviewed_qualification": request["allow_unreviewed_qualification"],
            "include_curation_statuses": request["include_curation_statuses"],
            "case_library_path": clean_text(safe_dict(request.get("library")).get("path")),
            "case_library_name": clean_text(safe_dict(request.get("library")).get("name")),
            "case_library_version": clean_text(safe_dict(request.get("library")).get("version")),
            "platforms": request["platforms"],
            "loaded_case_count": len(loaded_cases),
            "considered_case_count": len(normalized_cases),
        },
    )
    result["normalized_request_path"] = str(request_path)
    return result


__all__ = ["load_json", "normalize_platform", "run_benchmark_index", "write_json"]

