#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
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

PLATFORM_ALIASES = {
    "wechat": "wechat",
    "wx": "wechat",
    "mp": "wechat",
    "公众号": "wechat",
    "微信公众号": "wechat",
    "toutiao": "toutiao",
    "今日头条": "toutiao",
    "头条": "toutiao",
    "头条号": "toutiao",
}

HIGH_TICKET_AUDIENCE_TOKENS = (
    "投资",
    "财经",
    "研究",
    "交易",
    "资管",
    "机构",
    "商业",
    "企业",
    "公司",
    "产业",
    "决策",
    "买方",
    "专业",
    "finance",
    "investor",
    "research",
    "institution",
    "institutional",
    "operator",
    "business",
    "market",
    "high-net-worth",
    "report",
)

METHOD_JARGON_TOKENS = (
    "模板",
    "工作流",
    "prompt",
    "矩阵",
    "分层",
    "骨架",
    "框架",
    "workflow",
)

PUBLIC_HOOK_TOKENS = (
    "影响",
    "后果",
    "谁",
    "为什么",
    "怎么办",
    "冲击",
    "突发",
    "政策",
    "坠亡",
    "市场",
    "行业",
    "公司",
    "发生了什么",
    "到底",
    "consequence",
    "affected",
    "what changed",
    "why it matters",
    "question",
)

DECISION_DENSE_TOKENS = (
    "必读",
    "复盘",
    "研判",
    "判断",
    "案例",
    "跟踪",
    "评分",
    "清单",
    "变量",
    "信号",
    "brief",
    "复核",
    "must-read",
    "review",
    "signal",
    "scenario",
    "forensic",
)

PAID_LINKAGE_HIGH_TOKENS = (
    "会员",
    "付费",
    "订阅",
    "专栏",
    "模板包",
    "报告",
    "app",
    "必读",
    "更新",
    "subscription",
    "paid",
    "membership",
    "template",
    "report",
)

PAID_LINKAGE_MEDIUM_TOKENS = (
    "等候名单",
    "领取",
    "lead magnet",
    "lite",
    "白皮书",
    "下载",
    "waitlist",
    "download",
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
    match = re.search(r"(\d+(?:\.\d+)?)\s*(亿|万|w)?\+?", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or ""
    multiplier = 1
    if unit in {"万", "w"}:
        multiplier = 10_000
    elif unit == "亿":
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
    if band == "unknown":
        if "100w" in text or "100万" in text:
            band = "100w+"
        elif "50w" in text or "50万" in text:
            band = "50w+"
        elif "10w" in text or "10万" in text:
            band = "10w+"
        elif "5w" in text or "5万" in text:
            band = "5w+"
        elif "3w" in text or "3万" in text:
            band = "3w+"
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
    if not cases:
        raise ValueError("benchmark-index library_path did not resolve any cases[]")
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
    if "template" in text.lower() or "workflow" in text.lower():
        score += 12
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
            commercial_center,
        ]
    )
    score = 35
    if contains_any(text, HIGH_TICKET_AUDIENCE_TOKENS):
        score += 28
    if "retail" in text.lower() or "散户" in text:
        score += 8
    if "泛" in text or "gossip" in text.lower() or "情绪" in text:
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
    if "none" in text.lower() or "无" == clean_text(case.get("cta_type")):
        score = min(score, 25)
    return clamp(score)


def infer_cta_strength(case: dict[str, Any]) -> int:
    manual = coerce_score(case.get("cta_strength_score"), fallback=-1)
    if manual >= 0:
        return manual
    text = " ".join(
        [
            clean_text(case.get("cta_type")),
            clean_text(case.get("paid_asset_linkage")),
        ]
    )
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
    text = " ".join(
        [
            clean_text(case.get("title")),
            clean_text(case.get("hook_type")),
        ]
    )
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
        generated.append("外层包装先写事件、后果或受影响的人，再进入方法层")
    if clean_text(case.get("affected_group")):
        generated.append(f"从“{clean_text(case.get('affected_group'))}”这个受影响群体切入")
    if normalized_case["decision_density_score"] >= 72:
        generated.append("保留高密度判断结构，而不是只做情绪性观点")
    if normalized_case["paid_linkage_score"] >= 70 or normalized_case["cta_strength_score"] >= 70:
        generated.append("让免费内容自然导向一个可重复购买的付费资产")
    if normalized_case["platform"] == "toutiao" and normalized_case["acquisition_score"] >= 70:
        generated.append("头条标题先交代公共后果，再把方法放进正文")
    if normalized_case["platform"] == "wechat" and normalized_case["commercial_fit_score"] >= 70:
        generated.append("公众号负责解释、归档和转化承接")
    return unique_keep_order(safe_list(case.get("copy_signals")) + generated)


def build_avoid_signals(case: dict[str, Any], normalized_case: dict[str, Any]) -> list[str]:
    generated: list[str] = []
    title = clean_text(case.get("title"))
    if contains_any(title, METHOD_JARGON_TOKENS):
        generated.append("不要在外层标题里先扔方法论术语")
    if normalized_case["acquisition_score"] >= 72 and normalized_case["commercial_fit_score"] < 60:
        generated.append("不要把高流量误判成高付费意愿")
    if normalized_case["paid_linkage_score"] < 45:
        generated.append("不要只抄内容外壳，不抄它的转化承接")
    if "gossip" in clean_text(case.get("notes")).lower():
        generated.append("不要复制八卦化或强人格化包装")
    return unique_keep_order(safe_list(case.get("avoid_signals")) + generated)


def classify_case(
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
        status = "qualified" if label != "reject" else "rejected"
        return label, status

    if allow_exception and commercial_fit_score >= 70 and label in {"commercial-fit", "mixed", "watchlist"}:
        return "commercial-fit" if label == "watchlist" else label, "qualified_exception"

    return label, "rejected_threshold"


def build_review_summary(case: dict[str, Any]) -> str:
    parts = [f"{case['classification']} / {case['qualification_status']}"]
    if case["read_band"] != "unknown":
        parts.append(f"read {case['read_band']}")
    parts.append(f"acq {case['acquisition_score']}")
    parts.append(f"comm {case['commercial_fit_score']}")
    if case["qualification_status"] == "qualified_exception":
        parts.append("kept as commercial exception below read threshold")
    return "; ".join(parts)


def normalize_case(case: dict[str, Any], request: dict[str, Any], index: int) -> dict[str, Any]:
    platform = normalize_platform(case.get("platform"))
    read_meta = normalize_read_band(case.get("read_signal") or case.get("read_count") or case.get("reads"))
    threshold_rank = READ_BAND_ORDER[request["minimum_read_band"]]
    meets_threshold = read_meta["read_band_rank"] >= threshold_rank if threshold_rank > 0 else True
    publicness_score = infer_publicness(case, read_meta["read_strength_score"])
    decision_density_score = infer_decision_density(case)
    audience_fit_score = infer_audience_fit(case, request["commercial_center"])
    paid_linkage_score = infer_paid_linkage(case)
    cta_strength_score = infer_cta_strength(case)
    hook_clarity_score = infer_hook_clarity(case)
    acquisition_score = clamp(
        average([read_meta["read_strength_score"], publicness_score, hook_clarity_score]) + (5 if platform == "toutiao" else 0)
    )
    commercial_fit_score = clamp(
        average([decision_density_score, audience_fit_score, paid_linkage_score, cta_strength_score]) + (5 if platform == "wechat" else 0)
    )
    label, qualification_status = classify_case(
        acquisition_score,
        commercial_fit_score,
        meets_threshold,
        request["allow_below_threshold_commercial_exceptions"] and not request["strict_read_gate"],
    )
    published_at = parse_datetime(case.get("published_at"), fallback=None)
    normalized = {
        "index": index,
        "case_id": clean_text(case.get("case_id")) or slugify(clean_text(case.get("account_name")) or f"case-{index:02d}", f"case-{index:02d}"),
        "platform": platform,
        "account_name": clean_text(case.get("account_name")),
        "title": clean_text(case.get("title")),
        "url": clean_text(case.get("url")),
        "published_at": published_at.isoformat() if published_at else "",
        "read_signal": clean_text(case.get("read_signal") or case.get("read_count") or case.get("reads")),
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
        "classification": label,
        "qualification_status": qualification_status,
    }
    normalized["copy_signals"] = build_copy_signals(case, normalized)
    normalized["avoid_signals"] = build_avoid_signals(case, normalized)
    normalized["review_summary"] = build_review_summary(normalized)
    return normalized


def sort_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        cases,
        key=lambda case: (
            1 if case["qualification_status"] in {"qualified", "qualified_exception"} else 0,
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
        "rejected": [],
    }
    for case in cases:
        if case["classification"] == "mixed" and case["qualification_status"] in {"qualified", "qualified_exception"}:
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
        return ["没有通过筛选的案例。先补案例池，再做策略判断。"]

    implications: list[str] = []
    if any(case["qualification_status"] == "qualified_exception" for case in qualified):
        implications.append("保留“低于 10W+ 但高商业适配”的例外池，不要用流量阈值一刀切掉高价值样本。")

    toutiao_cases = [case for case in qualified if case["platform"] == "toutiao"]
    wechat_cases = [case for case in qualified if case["platform"] == "wechat"]
    if toutiao_cases and average([case["acquisition_score"] for case in toutiao_cases]) >= 70:
        implications.append("头条更适合承担公共化外壳和冷启动获客，标题先写后果、冲突或受影响的人。")
    if wechat_cases and average([case["commercial_fit_score"] for case in wechat_cases]) >= 70:
        implications.append("公众号更适合承担解释、归档和付费转化，核心付费 CTA 继续放在公众号。")

    if any(case["commercial_fit_score"] >= 75 and case["paid_linkage_score"] >= 70 for case in qualified):
        implications.append("高商业适配案例普遍在卖“重复使用的决策效率”，不是在卖更多热点或更强情绪。")

    if any(case["acquisition_score"] >= 75 and case["commercial_fit_score"] < 60 for case in qualified):
        implications.append("把高流量案例只当包装 benchmark，不要直接把它们当产品方向。")

    if any("不要在外层标题里先扔方法论术语" in case["avoid_signals"] for case in qualified):
        implications.append("顶层包装继续公共化，方法论术语放进正文、卡片结构或副标题。")

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
                f"- URL: {case['url'] or 'n/a'}",
                f"- Published at: {case['published_at'] or 'unknown'}",
                f"- Read band: {case['read_band']}",
                f"- Classification: {case['classification']} ({case['qualification_status']})",
                f"- Scores: acquisition {case['acquisition_score']} / commercial {case['commercial_fit_score']} / decision density {case['decision_density_score']}",
                f"- Copy: {'；'.join(case['copy_signals']) or 'n/a'}",
                f"- Avoid: {'；'.join(case['avoid_signals']) or 'n/a'}",
                f"- Notes: {case['notes'] or 'n/a'}",
                "",
            ]
        )
    return lines


def build_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("summary"))
    pools = safe_dict(result.get("pools"))
    library = safe_dict(result.get("case_library"))
    lines = [
        "# Benchmark Index Report",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Goal: {clean_text(result.get('goal')) or 'benchmark review'}",
        f"- Commercial center: {clean_text(result.get('commercial_center')) or 'n/a'}",
        f"- Minimum read band: {clean_text(result.get('minimum_read_band'))}",
        f"- Case library: {clean_text(library.get('name')) or 'direct cases'}",
        f"- Cases scanned: {summary.get('scanned_cases', 0)}",
        f"- Qualified cases: {summary.get('qualified_cases', 0)}",
        f"- Threshold exceptions kept: {summary.get('qualified_exceptions', 0)}",
        "",
        "## Strategy Implications",
        "",
    ]
    for item in safe_list(result.get("strategy_implications")):
        lines.append(f"- {clean_text(item)}")
    lines.append("")
    lines.extend(build_report_section("Mixed Benchmarks", safe_list(pools.get("mixed"))))
    lines.extend(build_report_section("Acquisition Benchmarks", safe_list(pools.get("acquisition"))))
    lines.extend(build_report_section("Commercial-Fit Benchmarks", safe_list(pools.get("commercial_fit"))))
    lines.extend(build_report_section("Watchlist", safe_list(pools.get("watchlist"))))
    lines.extend(build_report_section("Rejected Cases", safe_list(pools.get("rejected"))))
    return "\n".join(lines).strip() + "\n"


def run_benchmark_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)
    normalized_cases = [normalize_case(safe_dict(case), request, index + 1) for index, case in enumerate(request["cases"])]
    normalized_cases = sort_cases(normalized_cases)
    pools = pool_cases(normalized_cases)
    result = {
        "status": "ok",
        "workflow_kind": "benchmark_index",
        "analysis_time": request["analysis_time"].isoformat(),
        "goal": request["goal"],
        "commercial_center": request["commercial_center"],
        "minimum_read_band": request["minimum_read_band"],
        "strict_read_gate": request["strict_read_gate"],
        "allow_below_threshold_commercial_exceptions": request["allow_below_threshold_commercial_exceptions"],
        "case_library": {
            "path": clean_text(safe_dict(request.get("library")).get("path")),
            "name": clean_text(safe_dict(request.get("library")).get("name")),
            "version": clean_text(safe_dict(request.get("library")).get("version")),
        },
        "summary": {
            "scanned_cases": len(normalized_cases),
            "qualified_cases": sum(
                1 for case in normalized_cases if case["qualification_status"] in {"qualified", "qualified_exception"}
            ),
            "qualified_exceptions": sum(1 for case in normalized_cases if case["qualification_status"] == "qualified_exception"),
            "mixed_cases": len(pools["mixed"]),
            "acquisition_cases": len(pools["acquisition"]),
            "commercial_fit_cases": len(pools["commercial_fit"]),
            "watchlist_cases": len(pools["watchlist"]),
            "rejected_cases": len(pools["rejected"]),
        },
        "cases": normalized_cases,
        "pools": pools,
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
            "case_library_path": clean_text(safe_dict(request.get("library")).get("path")),
            "case_library_name": clean_text(safe_dict(request.get("library")).get("name")),
            "case_library_version": clean_text(safe_dict(request.get("library")).get("version")),
            "platforms": request["platforms"],
            "case_count": len(request["cases"]),
        },
    )
    result["normalized_request_path"] = str(request_path)
    return result


__all__ = ["load_json", "run_benchmark_index", "write_json"]
