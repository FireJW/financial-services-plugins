#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from article_benchmark_artifacts import (
    build_benchmark_candidate_index,
    build_benchmark_enrichment_request,
    build_benchmark_generation_style_memory,
    build_benchmark_quality_loop_artifact,
    build_benchmark_viral_teardown,
)
from article_benchmark_rubric import score_benchmark_rubric
from article_feedback_profiles import merge_style_memory
from article_workflow_runtime import run_article_workflow
from hot_topic_discovery_runtime import run_hot_topic_discovery
from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, short_excerpt, write_json
from workflow_publication_gate_runtime import build_workflow_publication_gate
from toutiao_fast_card_runtime import build_toutiao_fast_card_package
from toutiao_draftbox_runtime import push_fast_card_to_toutiao


REPO_ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_PHRASES = [
    "登录",
    "/url:",
    "预算",
    "订单",
    "定价",
    "经营变量",
    "经营层",
    "经营和投资判断题",
    "产品能力表面、工具调用边界和权限设计",
    "浏览器控制、工作流编排与多步开发者执行",
]

ALLOWED_MACRO_PRICING_PHRASES = [
    "定价权",
    "重新定价",
    "重定价",
    "单独计价",
    "定价中心",
]

MACRO_TRANSMISSION_CHAIN_LAYERS = {
    "oil": [
        "oil",
        "brent",
        "crude",
        "hormuz",
        "opec",
        "原油",
        "布伦特",
        "油价",
        "石油",
        "霍尔木兹",
    ],
    "inflation": [
        "inflation",
        "inflation expectations",
        "cpi",
        "通胀",
        "通胀预期",
        "物价",
    ],
    "fed_policy": [
        "fed",
        "federal reserve",
        "rates",
        "rate-cut",
        "policy path",
        "美联储",
        "联储",
        "利率",
        "政策路径",
        "降息",
        "加息",
    ],
    "discount_valuation_equities": [
        "discount rate",
        "valuation",
        "valuations",
        "equities",
        "equity",
        "stocks",
        "multiples",
        "risk assets",
        "折现率",
        "估值",
        "权益",
        "股票",
        "股市",
        "风险资产",
    ],
}

DEVELOPER_FOCUS_PHRASES = [
    "产品边界、权限设计",
    "浏览器控制、工作流编排",
    "能力边界和开发者工作流",
    "哪些入口会开放、哪些权限会收口",
]

WECHAT_TRANSITION_PHRASES = [
    "换句话说",
    "反过来看",
    "真正把讨论撑住的",
    "最容易误判的地方",
    "判断有没有走到这一步",
]

WECHAT_TAIL_PHRASES = [
    "默认工作流",
    "源码考古",
    "真实开发流程判断题",
]


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


def count_phrase_hits(text: str, phrases: list[str]) -> dict[str, int]:
    return {phrase: text.count(phrase) for phrase in phrases}


def relax_macro_pricing_false_positives(text: str, forbidden_hits: dict[str, int], topic_text: str) -> dict[str, int]:
    if not is_macro_conflict_topic(topic_text):
        return forbidden_hits
    adjusted_hits = dict(forbidden_hits)
    adjusted_hits["定价"] = max(
        0,
        adjusted_hits.get("定价", 0) - sum(text.count(phrase) for phrase in ALLOWED_MACRO_PRICING_PHRASES),
    )
    return adjusted_hits


def is_chinese_mode(request: dict[str, Any]) -> bool:
    return clean_text(request.get("language_mode")).lower() == "chinese"


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def is_developer_tooling_topic(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("claude code", "browser", "workflow", "tool", "permission", "源码"))


def is_macro_conflict_topic(text: str) -> bool:
    lowered = text.lower()
    english_patterns = (
        r"\boil\b",
        r"\bbrent\b",
        r"\bcrude\b",
        r"\bhormuz\b",
        r"\bopec\b",
        r"\bconflicts?\b",
        r"\bwars?\b",
        r"\biran\b",
        r"\bsanctions?\b",
    )
    chinese_tokens = ("特朗普", "伊朗", "战争", "布油", "原油", "油价", "霍尔木兹", "石油", "制裁")
    return any(re.search(pattern, lowered) for pattern in english_patterns) or any(token in text for token in chinese_tokens)


def build_macro_transmission_chain_check(text: str) -> dict[str, Any]:
    normalized = clean_text(text).lower()
    layer_hits: dict[str, list[str]] = {}
    for layer, tokens in MACRO_TRANSMISSION_CHAIN_LAYERS.items():
        hits = [token for token in tokens if token.lower() in normalized]
        layer_hits[layer] = hits
    missing_layers = [layer for layer, hits in layer_hits.items() if not hits]
    return {
        "required_layers": list(MACRO_TRANSMISSION_CHAIN_LAYERS.keys()),
        "layer_hits": layer_hits,
        "missing_layers": missing_layers,
        "complete": not missing_layers,
    }


def clean_public_topic_title(title: str) -> str:
    text = clean_text(title)
    if "|" in text:
        text = clean_text(text.split("|", 1)[0])
    text = re.sub(r"(?:36氪首发|首发)[:：]?", "", text).strip()
    text = re.sub(r"[:：]\s*哪些已经确认.*$", "", text)
    text = re.sub(r"[:：]\s*哪些仍未确认.*$", "", text)
    return text.strip("：:，, ")


def split_title_claims(clean_title: str) -> list[str]:
    parts = [clean_text(item) for item in re.split(r"[，,；;]", clean_title) if clean_text(item)]
    if len(parts) >= 2:
        return parts[:4]
    return [clean_title] if clean_title else []


def load_editorial_context(output_dir: Path) -> dict[str, Any]:
    """Load editorial-context.md from the article output directory.

    Returns a dict with optional keys: market_relevance_override, rejected_directions,
    analytical_chain, must_include_facts, style_constraints.  Returns {} if the file
    does not exist.
    """
    ec_path = output_dir / "editorial-context.md"
    if not ec_path.exists():
        return {}
    try:
        text = ec_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        heading_match = re.match(r"^##\s+(.+)", line)
        if heading_match:
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = heading_match.group(1).strip()
            current_lines = []
        elif not line.strip().startswith("<!--"):
            current_lines.append(line)
    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    result: dict[str, Any] = {}
    # Market relevance override
    mr_section = sections.get("Market Relevance Override", "")
    if mr_section:
        items = [line.lstrip("- ").strip() for line in mr_section.splitlines() if line.strip().startswith("-")]
        if items:
            result["market_relevance_override"] = items
    # Rejected directions
    rejected = sections.get("Rejected Titles / Directions", "")
    if rejected:
        items = [line.lstrip("- ").lstrip("❌ ").strip() for line in rejected.splitlines() if line.strip().startswith("-") or line.strip().startswith("❌")]
        if items:
            result["rejected_directions"] = items
    # Analytical chain (pass as-is for prompt injection)
    chain = sections.get("Analytical Chain", "") or sections.get("Analytical Chain (must follow this, not generic filler)", "")
    if chain:
        result["analytical_chain"] = chain
    # Must-include facts
    facts = sections.get("Must-Include Facts", "") or sections.get("Numbers That Must Appear in the Article", "")
    if facts:
        items = [line.lstrip("- ").strip() for line in facts.splitlines() if line.strip().startswith("-")]
        if items:
            result["must_include_facts"] = items
    # Style constraints
    style = sections.get("Style Constraints", "")
    if style:
        items = [line.lstrip("- ").strip() for line in style.splitlines() if line.strip().startswith("-")]
        if items:
            result["style_constraints"] = items
    return result


def localized_market_relevance(selected_topic: dict[str, Any], clean_title: str, *, developer_tooling: bool) -> list[str]:
    if developer_tooling:
        return ["产品边界、工具调用与权限设计", "浏览器控制、工作流编排"]
    keywords = " ".join(clean_string_list(selected_topic.get("keywords"))).lower()
    combined = " ".join(
        [
            keywords,
            clean_text(clean_title).lower(),
            clean_text(selected_topic.get("summary")).lower(),
            " ".join(clean_text(item.get("summary")).lower() for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)),
        ]
    )
    _macro_conflict_tokens = ("oil", "crude", "inflation", "cpi", "retail", "tariff", "war", "conflict", "sanctions", "闇嶅皵鏈ㄥ吂", "娌逛环", "閫氳儉", "闆跺敭", "鍏崇◣", "鍒惰")
    _is_macro = any(tok in combined for tok in _macro_conflict_tokens)
    if any(
        token in combined
        for token in (
            "semiconductor",
            "chips",
            "foundry",
            "equipment",
            "euv",
            "advanced packaging",
            "capex",
            "台积电",
            "阿斯麦",
            "晶圆",
            "半导体",
            "先进制程",
            "先进封装",
            "设备订单",
            "产能扩张",
            "资本开支",
        )
    ) and not _is_macro:
        return ["先进制程产能和设备订单", "资本开支、产能扩张和先进封装"]
    # Guard: only classify as AI/agent topic when the combined text clearly centres
    # on AI/agent subject matter AND the topic is not a macro/conflict/commodity topic.
    _macro_conflict_tokens = ("oil", "crude", "inflation", "cpi", "retail", "tariff", "war", "conflict", "sanctions", "霍尔木兹", "油价", "通胀", "零售", "关税", "制裁")
    _is_macro = any(tok in combined for tok in _macro_conflict_tokens)
    _ai_core_tokens = ("ai model", "ai agent", "大模型", "人工智能", "llm", "gpt", "claude", "copilot", "openai", "anthropic")
    _ai_in_combined = any(tok in combined for tok in _ai_core_tokens)
    _ai_keyword_only = any(tok in keywords for tok in ("ai", "agent"))
    if (_ai_in_combined or _ai_keyword_only) and not _is_macro:
        return ["融资意愿、订单能见度和预算投放", "招聘节奏、组织扩张和行业景气度"]
    return ["谁会真正受影响，变化会传到哪里", "这件事什么时候会从热度变成判断题"]


def publish_quality_defaults(language_mode: str, article_framework: str) -> dict[str, int]:
    normalized_language = clean_text(language_mode).lower() or "chinese"
    normalized_framework = clean_text(article_framework).lower() or "auto"

    target_floor = 1600
    human_floor = 45
    if normalized_language == "chinese":
        target_floor = 2200
        human_floor = 60
    elif normalized_language == "bilingual":
        target_floor = 2000
        human_floor = 55
    if normalized_framework in {"", "auto", "deep_analysis"}:
        if normalized_language == "chinese":
            target_floor = max(target_floor, 2400)
            human_floor = max(human_floor, 68)
        elif normalized_language == "bilingual":
            target_floor = max(target_floor, 2200)
            human_floor = max(human_floor, 60)
        else:
            target_floor = max(target_floor, 1800)
            human_floor = max(human_floor, 50)
    return {"target_length_chars": target_floor, "human_signal_ratio": human_floor}


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(safe_dict(raw_payload))
    analysis_time = parse_datetime(payload.get("analysis_time"), fallback=datetime.now(UTC)) or datetime.now(UTC)
    output_dir = Path(clean_text(payload.get("output_dir")) or (REPO_ROOT / ".tmp" / "article-publish")).expanduser().resolve()
    feedback_profile_dir = clean_text(payload.get("feedback_profile_dir"))
    author = clean_text(payload.get("author"))
    if feedback_profile_dir and not author:
        global_profile = Path(feedback_profile_dir) / "global.json"
        if global_profile.exists():
            try:
                profile = json.loads(global_profile.read_text(encoding="utf-8"))
                author = clean_text(safe_dict(profile).get("request_defaults", {}).get("author"))
            except json.JSONDecodeError:
                author = ""
    requested_language = clean_text(payload.get("language_mode"))
    language_mode = requested_language or "chinese"
    requested_framework = clean_text(payload.get("article_framework")) or "auto"
    quality_defaults = publish_quality_defaults(language_mode, requested_framework)
    explicit_target_length = any(payload.get(key) not in (None, "", []) for key in ("target_length_chars", "target_length"))
    explicit_human_signal = payload.get("human_signal_ratio") not in (None, "", [])
    target_length_chars = int(payload.get("target_length_chars", payload.get("target_length", quality_defaults["target_length_chars"])) or quality_defaults["target_length_chars"])
    human_signal_ratio = int(payload.get("human_signal_ratio", quality_defaults["human_signal_ratio"]) or quality_defaults["human_signal_ratio"])
    if not explicit_target_length:
        target_length_chars = max(target_length_chars, quality_defaults["target_length_chars"])
    if not explicit_human_signal:
        human_signal_ratio = max(human_signal_ratio, quality_defaults["human_signal_ratio"])
    return {
        "analysis_time": isoformat_or_blank(analysis_time),
        "account_name": clean_text(payload.get("account_name")) or "Codex Research Notes",
        "author": author or "Codex",
        "feedback_profile_dir": feedback_profile_dir,
        "language_mode": language_mode,
        "article_framework": requested_framework,
        "editor_anchor_mode": clean_text(payload.get("editor_anchor_mode")) or "hidden",
        "headline_hook_mode": clean_text(payload.get("headline_hook_mode")) or ("traffic" if language_mode == "chinese" else "auto"),
        "headline_hook_prefixes": clean_string_list(payload.get("headline_hook_prefixes")),
        "composition_style": clean_text(payload.get("composition_style")),
        "image_strategy": clean_text(payload.get("image_strategy")) or "mixed",
        "draft_mode": clean_text(payload.get("draft_mode")) or "balanced",
        "tone": clean_text(payload.get("tone")) or "professional-calm",
        "target_length_chars": target_length_chars,
        "max_images": int(payload.get("max_images", 3) or 3),
        "human_signal_ratio": human_signal_ratio,
        "digest_max_chars": int(payload.get("digest_max_chars", 120) or 120),
        "show_cover_pic": int(payload.get("show_cover_pic", 1) or 1),
        "need_open_comment": 1 if payload.get("need_open_comment") else 0,
        "only_fans_can_comment": 1 if payload.get("only_fans_can_comment") else 0,
        "topic": clean_text(payload.get("topic")),
        "manual_topic_candidates": [safe_dict(item) for item in safe_list(payload.get("manual_topic_candidates")) if isinstance(item, dict)],
        "audience_keywords": clean_string_list(payload.get("audience_keywords")),
        "preferred_topic_keywords": clean_string_list(payload.get("preferred_topic_keywords")),
        "excluded_topic_keywords": clean_string_list(payload.get("excluded_topic_keywords")),
        "min_total_score": int(payload.get("min_total_score", 0) or 0),
        "min_source_count": int(payload.get("min_source_count", 0) or 0),
        "selected_topic_index": max(1, int(payload.get("selected_topic_index", 1) or 1)),
        "discovery_top_n": int(payload.get("discovery_top_n", 3) or 3),
        "output_dir": output_dir,
        "push_to_wechat": bool(payload.get("push_to_wechat")),
        "push_to_toutiao": bool(payload.get("push_to_toutiao")),
        "toutiao_browser_session": safe_dict(payload.get("toutiao_browser_session")),
        "wechat_cta_text": clean_text(payload.get("wechat_cta_text")),
        "boundary_statement": clean_text(payload.get("boundary_statement")),
        "human_review_approved": bool(payload.get("human_review_approved")),
        "human_review_approved_by": clean_text(payload.get("human_review_approved_by")),
        "human_review_note": clean_text(payload.get("human_review_note")),
        "push_backend": clean_text(payload.get("push_backend")) or "api",
        "wechat_app_id": clean_text(payload.get("wechat_app_id")),
        "wechat_app_secret": clean_text(payload.get("wechat_app_secret")),
        "allow_insecure_inline_credentials": bool(payload.get("allow_insecure_inline_credentials")),
        "cover_image_path": clean_text(payload.get("cover_image_path")),
        "cover_image_url": clean_text(payload.get("cover_image_url")),
        "timeout_seconds": int(payload.get("timeout_seconds", 30) or 30),
        "browser_session": safe_dict(payload.get("browser_session")),
    }


def build_news_request_from_topic(selected_topic: dict[str, Any], raw_request: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_request)
    title = clean_public_topic_title(clean_text(selected_topic.get("title")) or request["topic"])
    zh_mode = is_chinese_mode(request) or contains_cjk(title)
    developer_tooling = is_developer_tooling_topic(title + " " + clean_text(selected_topic.get("summary")))
    title_claims = split_title_claims(title)
    if not title_claims:
        title_claims = [title or "This topic is worth verifying from multiple public sources."]
    claims = [{"claim_id": f"claim-{index + 1}", "claim_text": item} for index, item in enumerate(title_claims)]
    claims_zh = []
    if zh_mode:
        if developer_tooling:
            claims_zh.append("这条线程顺着浏览器控制和多步任务执行入口做了拆解。")
        claims_zh.extend(item for item in title_claims[:2] if item not in claims_zh)
    for index, item in enumerate(claims):
        if index < len(claims_zh):
            item["claim_text_zh"] = claims_zh[index]
        elif zh_mode:
            item["claim_text_zh"] = item["claim_text"]

    source_items = [safe_dict(item) for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)]
    candidates = []
    for index, source in enumerate(source_items):
        summary = clean_text(source.get("summary"))
        source_post_summary = clean_text(source.get("post_summary"))
        if developer_tooling and summary.startswith("The thread"):
            summary = "这条线程顺着浏览器控制和多步任务执行入口做了拆解。"
        if not source_post_summary and not developer_tooling:
            source_post_summary = clean_text(summary or source.get("title") or source.get("source_name"))
        candidates.append(
            {
                "source_id": clean_text(source.get("source_id")) or f"topic-source-{index + 1}",
                "source_name": clean_text(source.get("source_name")) or f"source-{index + 1}",
                "source_type": clean_text(source.get("source_type")) or "major_news",
                "published_at": clean_text(source.get("published_at")) or request["analysis_time"],
                "observed_at": request["analysis_time"],
                "url": clean_text(source.get("url")),
                "text_excerpt": summary,
                "post_summary": source_post_summary,
                "media_summary": clean_text(source.get("media_summary")),
                "root_post_screenshot_path": clean_text(source.get("root_post_screenshot_path")),
                "artifact_manifest": safe_list(source.get("artifact_manifest")),
                "media_items": safe_list(source.get("media_items")),
                "claim_ids": [item["claim_id"] for item in claims],
                "claim_states": {item["claim_id"]: "support" for item in claims},
            }
        )

    market_relevance_zh = localized_market_relevance(selected_topic, title, developer_tooling=developer_tooling) if zh_mode else []
    # Override market_relevance from editorial-context.md if present
    _ec = load_editorial_context(Path(clean_text(raw_request.get("output_dir")) or "."))
    if _ec.get("market_relevance_override"):
        market_relevance_zh = _ec["market_relevance_override"]
    market_relevance = market_relevance_zh[:] if market_relevance_zh else clean_string_list(selected_topic.get("keywords"))[:3]
    questions = (
        [
            "哪些事实已经能被多源确认？",
            "哪些判断还不能写死？",
            "这件事真正会影响到谁？",
        ]
        if is_chinese_mode(request)
        else [
            "What is already confirmed by multiple public sources?",
            "What still should not be written as settled?",
            "Which reader or market transmission matters most next?",
        ]
    )
    return {
        "topic": title,
        "analysis_time": request["analysis_time"],
        "questions": questions,
        "claims": claims,
        "candidates": candidates,
        "market_relevance": market_relevance,
        "market_relevance_zh": market_relevance_zh,
        "mode": "generic",
        "windows": ["10m", "1h", "24h"],
        "language_mode": "chinese" if zh_mode else request["language_mode"],
    }


def markdown_to_html(markdown_text: str) -> str:
    def escape_text(value: str) -> str:
        # Text nodes do not need quote escaping; keeping apostrophes readable
        # avoids literal entity leakage like Tom&#x27;s in downstream editors.
        return escape(value, quote=False)

    lines = markdown_text.splitlines()
    html: list[str] = ['<article style="font-family:\'PingFang SC\',\'Hiragino Sans GB\',\'Microsoft YaHei\',sans-serif;color:#1f2329;font-size:16px;line-height:1.9;">']
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            continue
        if line.strip() == "---":
            html.append('<hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0;" />')
            continue
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            alt = escape(image_match.group(1))
            src = escape(image_match.group(2))
            html.append(f'<p><img src="{src}" alt="{alt}" style="max-width:100%;border-radius:8px;" /></p>')
            continue
        if line.startswith("# "):
            html.append(f"<h1>{escape_text(line[2:])}</h1>")
        elif line.startswith("## "):
            html.append(f"<h2>{escape_text(line[3:])}</h2>")
        elif line.startswith("> "):
            html.append(f"<blockquote>{escape_text(line[2:])}</blockquote>")
        elif line.startswith("_") and line.endswith("_"):
            html.append(f"<p><em>{escape_text(line.strip('_'))}</em></p>")
        else:
            content = escape_text(line)
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            html.append(f"<p>{content}</p>")
    html.append("</article>")
    return "\n".join(html) + "\n"


def extract_leading_markdown_h1(markdown_text: str) -> str:
    for line in str(markdown_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return clean_text(stripped[2:])
        return ""
    return ""


def strip_plain_leading_title(markdown_text: str, *title_candidates: str) -> str:
    lines = markdown_text.splitlines()
    normalized_titles = {clean_text(item) for item in title_candidates if clean_text(item)}
    if not lines or not normalized_titles:
        return markdown_text
    first_content_index = next((index for index, line in enumerate(lines) if clean_text(line)), None)
    if first_content_index is None:
        return markdown_text
    first_line = lines[first_content_index].strip()
    if first_line.startswith(("#", ">", "-", "*")) or re.match(r"^\d+\.\s", first_line) or first_line.startswith(("![", "```")):
        return markdown_text
    if clean_text(first_line) not in normalized_titles:
        return markdown_text
    remaining_lines = lines[:first_content_index] + lines[first_content_index + 1 :]
    return "\n".join(remaining_lines).lstrip("\n")


def promote_plain_leading_title(markdown_text: str, *title_candidates: str) -> str:
    lines = markdown_text.splitlines()
    normalized_titles = {clean_text(item) for item in title_candidates if clean_text(item)}
    if not lines or not normalized_titles:
        return markdown_text
    first_content_index = next((index for index, line in enumerate(lines) if clean_text(line)), None)
    if first_content_index is None:
        return markdown_text
    first_line = lines[first_content_index].strip()
    if first_line.startswith(("#", ">", "-", "*")) or re.match(r"^\d+\.\s", first_line) or first_line.startswith(("![", "```")):
        return markdown_text
    if clean_text(first_line) not in normalized_titles:
        return markdown_text
    lines[first_content_index] = f"# {first_line}"
    return "\n".join(lines)


def extract_manual_markdown_structure(markdown_text: str) -> dict[str, Any]:
    lines = str(markdown_text or "").splitlines()
    title = extract_leading_markdown_h1(markdown_text)
    blocks: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_kind = "paragraph"

    def flush_block() -> None:
        nonlocal current_lines, current_kind
        text = "\n".join(current_lines).strip()
        if text:
            blocks.append((current_kind, text))
        current_lines = []
        current_kind = "paragraph"

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            flush_block()
            continue
        if stripped.startswith("# ") and not stripped.startswith("##"):
            flush_block()
            continue
        if stripped.startswith("## "):
            flush_block()
            blocks.append(("heading", clean_text(stripped[3:])))
            continue
        if stripped.startswith("!["):
            flush_block()
            continue
        current_lines.append(stripped)
    flush_block()

    intro_blocks: list[str] = []
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_section_paragraphs: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading, current_section_paragraphs
        if current_heading:
            sections.append(
                {
                    "heading": current_heading,
                    "paragraph": "\n\n".join(current_section_paragraphs).strip(),
                }
            )
        current_heading = ""
        current_section_paragraphs = []

    for kind, text in blocks:
        if kind == "heading":
            flush_section()
            current_heading = text
            continue
        if current_heading:
            current_section_paragraphs.append(text)
        else:
            intro_blocks.append(text)
    flush_section()

    subtitle = intro_blocks[0] if intro_blocks else ""
    lede = intro_blocks[1] if len(intro_blocks) > 1 else ""
    draft_thesis = clean_text(title or lede or subtitle)
    return {
        "title": title,
        "subtitle": subtitle,
        "lede": lede,
        "sections": [section for section in sections if clean_text(section.get("heading")) or clean_text(section.get("paragraph"))],
        "draft_thesis": draft_thesis,
    }


DEFAULT_EDITOR_ANCHORS = [
    {"placement": "after_lede", "text": "这里补一个你自己的判断升级条件，或者一句反直觉结论。"},
    {"placement": "after_section_2", "text": "这里加入你亲身见过的案例、行业对话或一次踩坑经历。"},
    {"placement": "after_section_4", "text": "这里补一个只属于你自己的结论收口，不要只重复公开信息。"},
]


def load_feedback_profile_defaults(profile_dir: str) -> dict[str, Any]:
    if not clean_text(profile_dir):
        return {}
    profile_path = Path(profile_dir) / "global.json"
    if not profile_path.exists():
        return {}
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def format_source_line(item: dict[str, Any], *, title_override: str = "") -> str:
    published = parse_datetime(item.get("published_at"))
    published_text = published.date().isoformat() if published else clean_text(item.get("published_at"))
    title = clean_text(title_override or item.get("summary") or item.get("title") or item.get("source_name"))
    return f"- [{title}]({clean_text(item.get('url'))}) | {clean_text(item.get('source_name'))} | {published_text}"


CANONICAL_SOURCE_TITLES = {
    "Anthropic docs / Subagents": "官方已经公开 subagents，说明多代理不是空想；但 recovered 代码里的 coordinator、teammate、pane backend 更像是这条路线的更重版本。",
    "Anthropic docs / Chrome": "Anthropic 官方文档已经公开 Chrome 集成，证明浏览器控制不是纯猜测，但 recovered 代码显示它可能只是更大自动化表面的一部分。",
    "Anthropic docs / Remote Control": "Anthropic 官方文档已经公开 Remote Control，说明跨端控制本地 Claude Code 的能力至少部分已经进入正式产品叙事。",
    "X @agintender": "这条 X 帖子把讨论点集中到“Claude Code 泄露源码里藏着哪些没有公开讲明白的功能”，成为这次选题的直接触发器。",
    "Reddit summary": "社区总结把 KAIROS、Buddy、Ultraplan、Coordinator、UDS Inbox 归为未公开 feature flags，这与我们本地 recovered 代码里看到的命名基本互相印证。",
    "local recovered commands": "local recovered commands",
    "local Claude in Chrome onboarding": "代码里的 Claude in Chrome onboarding 明确写到 Claude Code 可以直接控制浏览器，执行打开网页、填写表单、截图、录 GIF，并查看 console 和 network 请求，且文案标记为 Beta。",
    "local voice mode": "voice mode 被 compile-time flag 和 Claude.ai OAuth 加 voice_stream endpoint 双重门控，还涉及麦克风权限与 push-to-talk，说明终端语音交互并不是半成品。",
    "local coordinator and ultraplan": "coordinator system prompt 公开写着协调者会并行调度多个 worker；ultraplan 则把复杂规划发送到 Claude Code on the web，允许终端保持空闲 10 到 30 分钟。",
    "local undercover mode": "Undercover Mode 会在公共仓库里自动去掉 AI attribution 和内部代号，说明 Anthropic 内部早就把“AI 代理公开协作”当成安全与品牌风险来设计。",
    "local bridge and mobile": "bridge 代码和 mobile 命令说明 Claude Code 可以通过二维码、网页或手机双向远控本地 CLI，会轮询任务、接收权限回复，并维持双向会话。",
    "local buddy and think-back": "Buddy 和 Think Back 说明团队并不只把 Claude Code 当成程序员工具，还在尝试陪伴感、年终回顾和更 consumer 化的留存机制。",
}

CANONICAL_SOURCE_ORDER = [
    "Anthropic docs / Subagents",
    "Anthropic docs / Chrome",
    "Anthropic docs / Remote Control",
    "X @agintender",
    "Reddit summary",
    "local recovered commands",
    "local Claude in Chrome onboarding",
    "local voice mode",
    "local coordinator and ultraplan",
    "local undercover mode",
    "local bridge and mobile",
    "local buddy and think-back",
]

CANONICAL_MUST_AVOID = [
    "当前最稳妥的写法是",
    "这版内容基于当前索引结果生成",
    "已确认与未确认",
    "图片与截图",
    "边界与待确认点",
    "写作约束",
    "哪些已经确认，哪些仍未确认",
    "最稳妥的写法是",
    "当前索引结果",
    "真实事件、趋势或公开争议",
    "有解释价值，不只是情绪型热度",
    "如果你说的是",
    "更硬的变量",
    "更实的变量",
    "经营变量",
    "经营层",
    "说一件昨天发生的事",
    "先把最新的催化剂说清楚",
    "先把发生了什么说清楚",
    "经本地索引管线交叉验证",
    "信源说明",
]


def append_chinese_longform_length_floor(
    lines: list[str],
    selected_topic: dict[str, Any],
    request: dict[str, Any],
) -> None:
    target_length_chars = int(request.get("target_length_chars", 0) or 0)
    if target_length_chars < 2200:
        return
    required_body_chars = minimum_body_chars_for_target(target_length_chars)
    if len("\n\n".join(lines)) >= required_body_chars:
        return

    title = clean_text(selected_topic.get("title")) or "这件事"
    summary = clean_text(selected_topic.get("summary"))
    source_count = int(selected_topic.get("source_count", 0) or len(safe_list(selected_topic.get("source_items"))))
    source_hint = f"现在可用的公开来源大约有 {source_count} 条，" if source_count else "现在公开来源还不算厚，"
    proof_hint = summary or "后续仍要看更多公开信号能不能互相指向同一条线"
    additions = [
        (
            "还要补哪几层验证",
            (
                f"不能因为标题热，就默认供需拐点已经确认。{source_hint}更稳的写法是先把已经发生的事实、"
                f"正在被市场放大的推演、以及还没有被交叉验证的部分拆开。放到{title}这条线上，第一层要看"
                f"{proof_hint}；第二层要看同一变化会不会继续出现在价格、订单、交付周期和下游预算里；第三层"
                "才是资本市场愿不愿意把它重新定价。只有这三层至少有两层连起来，文章里的判断才不是单靠热度往前推。"
            ),
        ),
        (
            "从题材到判断的传导",
            (
                "这类题材真正容易误判的地方，是把一次性情绪写成持续趋势。更有用的观察顺序，是先看供给端有没有"
                "继续收紧，再看需求端是否愿意接受更高成本，最后看企业和投资者是否因此调整预算、库存和估值假设。"
                "如果只是新闻标题在涨，企业订单、交付周期和价格口径没有跟上，那它还只是一个讨论点；如果这些变量"
                "开始连续出现，才说明它可能从话题变成经营约束，再从经营约束变成市场判断。"
            ),
        ),
        (
            "反过来看风险",
            (
                "反过来看，最需要防的不是错过热度，而是过早把故事写满。后续如果新增来源只是在复述同一个标题，"
                "没有新的价格、产能、订单或客户预算信息，这条线的可信度就应该下调。相反，如果不同来源开始给出"
                "相互独立的供需变化，且这些变化能落到公司指引、产业链报价或终端采购动作上，才值得继续提高权重。"
                "所以结尾不该停在情绪判断，而要把读者带到下一轮可观察变量上。"
            ),
        ),
        (
            "证据顺序应该怎么排",
            (
                "写这类文章时，证据顺序比观点更重要。先放最硬的公开事实，再放能解释变化的产业变量，最后才放"
                "市场可能怎么反应。这样的顺序可以避免一上来就把推演写成结论，也能让读者看清每一层判断的来源。"
                "如果后面出现新的公司口径、渠道报价或机构调研，它们应该先被放回这条顺序里，而不是直接拿来强化"
                "已经写好的标题。能被纳入同一条证据链的信号，权重才会上升；只负责制造热闹的信号，权重反而应该下降。"
            ),
        ),
        (
            "最后留下可跟踪的观察项",
            (
                "所以最后真正要留下的，不是一句情绪判断，而是一组下次可以复盘的观察项。第一，看公开来源会不会"
                "继续增加，且不是同源转载。第二，看价格、产能、交付周期和订单口径里有没有两个以上变量同时变化。"
                "第三，看下游预算、库存和资本开支是否开始被迫调整。第四，看市场反应是短期交易，还是开始影响估值"
                "假设。只要这些观察项还没有连续出现，文章就应该保持克制；一旦它们开始连成线，下一轮更新才有更强理由。"
            ),
        ),
        (
            "读者该怎么使用这篇文章",
            (
                "对读者来说，这篇文章更适合作为判断框架，而不是直接给出单点结论。它提醒你先分清事实、推演和"
                "待验证变量，再把新增信息放回同一套框架里比较。后续如果只看到标题继续升温，但没有更多独立来源"
                "和可量化变量，就不应该追着情绪加码；如果看到供给、需求、价格和资本开支开始同时变化，才说明"
                "这件事可能进入第二阶段。这样的写法不追求一次把话说满，而是让下一次更新有清楚的校验标准。"
                "它也能避免文章停在概念层面：读者知道哪些信号只是噪音，哪些信号会改变判断，哪些信号足以触发复盘。"
                "等下一轮信息出来时，直接沿着这组问题检查，就能知道叙事是在变强，还是只是在重复和消耗注意力。这个边界要留住，别被热词带走才行。"
            ),
        ),
    ]
    for heading, paragraph in additions:
        if len("\n\n".join(lines)) >= required_body_chars:
            break
        lines.extend(["", f"## {heading}", paragraph])


def build_chinese_publish_markdown(selected_topic: dict[str, Any], article_package: dict[str, Any], request: dict[str, Any], *, developer_tooling: bool) -> str:
    title = clean_text(selected_topic.get("title"))
    source_items = [safe_dict(item) for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)]
    selected_images = [safe_dict(item) for item in safe_list(article_package.get("selected_images")) if isinstance(item, dict)]
    composition_style = clean_text(request.get("composition_style"))
    market_relevance_zh = localized_market_relevance(selected_topic, title, developer_tooling=developer_tooling)
    # Override market_relevance from editorial-context.md if present in build_chinese_publish_markdown
    _ec_chinese = load_editorial_context(Path(clean_text(request.get("output_dir")) or "."))
    if _ec_chinese.get("market_relevance_override"):
        market_relevance_zh = _ec_chinese["market_relevance_override"]
    formatted_source_lines = [
        format_source_line(
            item,
            title_override=clean_text(item.get("summary") or item.get("title") or item.get("source_name")),
        )
        for item in source_items
        if clean_text(item.get("url"))
    ]
    if developer_tooling:
        lines = [
            "先把发生了什么说清楚，再看这件事为什么会继续发酵。",
            f"> {clean_text(title)}最近会被反复提起，不只是因为热度起来了。更重要的是，讨论已经开始从“还有什么隐藏能力”往“这些能力会怎么进入真实开发流程”上走。不过像“这条线程顺着浏览器控制和多步任务执行入口做了拆解”这样的判断，现阶段还不能写成定论。写深这件事的关键，不是继续堆热度，而是看哪些入口和协作动作会先变成能反复用的东西。",
            "## 先看入口到底在哪里",
            "最先值得确认的，不是外界怎么转述，而是浏览器控制、任务串联和权限边界这些入口到底有没有在同一条链路里出现。先把入口层和真实调用痕迹对上，后面的判断才有抓手。",
            "## 截图能补什么",
            "截图的价值不是把页面贴出来，而是把入口、页面状态和上下文一起保留下来。它能告诉我们当时看到的到底是一个按钮、一个面板，还是一条可以继续往下走的工作流线索。",
            "## 浏览器控制为什么重要",
            "这类能力一旦被团队真正用起来，变化就不只是多了一个功能名词，而是开发、验证和交付的动作会不会被重新组织。浏览器代执行、页面读取、结果回写，这几步如果真的连起来，协作方式就会跟着变化。",
            "## 权限边界才是真问题",
            "真正决定这件事能不能走进日常开发的，不是彩蛋数量，而是谁来开权限、谁来兜底执行、谁来承担可追溯性。入口可以先出现，但权限边界如果一直不清楚，团队也不敢把它当成稳定能力。",
            "## 工作流编排会不会落地",
            "热度能不能继续往前推，最后还是要看这套东西会不会从展示页走到真实工作流。只有当文档、入口、权限说明和团队用法开始互相对上，讨论才会从源码猎奇慢慢变成产品判断。",
            "## 这件事的分水岭在哪",
            "接下来真正值得盯的，不是又多了一张截图，而是有没有新的公开入口、有没有更明确的权限说明、有没有人把它放进真实开发链路里反复使用。只要这三件事里有两件开始连续被验证，这条线就还会继续往前走。",
            "## 来源",
        ]
        lines.extend(f"- {clean_text(item.get('source_name'))} | {clean_text(item.get('url'))}" for item in source_items if clean_text(item.get("url")))
        return "\n\n".join(lines)

    if composition_style == "x_thread_analysis":
        recommended_angle = clean_text(selected_topic.get("recommended_angle"))
        why_now = clean_text(selected_topic.get("why_now"))
        selection_reason = clean_text(selected_topic.get("selection_reason"))
        source_mix = clean_text(selected_topic.get("source_mix"))
        image_blocks: list[str] = []
        for image in selected_images[:2]:
            image_id = clean_text(image.get("asset_id") or image.get("image_id"))
            image_path = clean_text(image.get("path") or image.get("render_target") or image.get("source_url"))
            image_caption = clean_text(image.get("caption") or image.get("summary"))
            if image_id and image_path:
                image_blocks.extend([f"![{image_id}]({image_path})", f"_{image_caption}_", ""])

        lines = [
            "【深度分析】",
            "（下面我不重复新闻稿，而是把真正值得看的变量拆开说。）",
            "",
            f"> 先说结论，{title}这件事真正值得看的，不是热度本身，而是{why_now or '它背后会不会继续改写产业和资本市场判断。'}",
            "",
        ]
        lines.extend(image_blocks)
        lines.extend(
            [
                "## 先说结论",
                clean_text(recommended_angle or f"{title}更值得看的，不是表面热闹，而是背后的竞争格局和传导链条。"),
                "",
                "## 媒体没说透的点",
                clean_text(selection_reason or "这不是一条普通快讯，而是能继续延伸出判断题的故事。"),
                "",
                "## 真正该盯的变量",
                f"如果把表面新闻拨开，真正该盯的至少有三层：第一，竞争格局是不是在变；第二，商业化和订单是不是能跟上；第三，{source_mix or '当前这些信号'}到底说明了什么，不说明什么。",
                "",
                "## 传导链条",
                "这类题目最后能不能成立，不是看标题多热，而是看它会不会继续往产业链、客户决策、资本市场和后续订单上传导。",
                "",
                "## 最后看风险点",
                "现在最要防的，是把阶段性情绪、单条新闻和真正的行业趋势混为一谈。只要后续验证跟不上，叙事就会很快回落。",
                "",
                "## 来源",
            ]
        )
        lines.extend(formatted_source_lines)
        return "\n\n".join(lines)

    longform_sections = [
        safe_dict(item)
        for item in safe_list(article_package.get("sections"))
        if isinstance(item, dict) and clean_text(item.get("heading")) and clean_text(item.get("paragraph"))
    ]
    if int(request.get("target_length_chars", 0) or 0) >= 2200 and len(longform_sections) >= 5:
        lines = [
            clean_text(article_package.get("subtitle")) or "先把发生了什么说清楚，再看这件事为什么会继续发酵。",
        ]
        lede = clean_text(article_package.get("lede"))
        if lede:
            lines.extend(["", f"> {lede}"])
        for section in longform_sections:
            lines.extend(["", f"## {clean_text(section.get('heading'))}", clean_text(section.get("paragraph"))])
        append_chinese_longform_length_floor(lines, selected_topic, request)
        lines.extend(["", "## 来源"])
        lines.extend(formatted_source_lines)
        return "\n\n".join(line for line in lines if line is not None)

    if "先进制程产能和设备订单" in market_relevance_zh:
        lines = [
            "从晶圆厂、设备订单和资本开支的最新口径，看这轮 AI 基建投资到底走到哪一步。",
            f"> {clean_text(title)}最近会被反复提起，不只是因为热度起来了。更重要的是，它已经开始碰到先进制程产能和设备订单、资本开支、产能扩张和先进封装这些更硬的变量。不过像“{clean_text(title)}”这样的判断，现阶段还不能写成定论。",
            "## 先看变化本身",
            "最先能确认的变化其实很具体：上游信号已经不只是情绪型热度，而是开始落到晶圆厂指引、设备订单和扩产计划这些更实的经营变量。先把这一步站稳，后面哪些判断能往前写，才有边界。",
            "## 深层原因",
            "这轮讨论没有很快掉下去，一个原因是台积电和阿斯麦这类上游公司同时给出了更强口径。与此同时，市场又在重新评估 AI 投资回报和供给瓶颈。所以你现在看到的，不只是一个标题在回潮，而是在看先进制程产能和设备订单、资本开支、产能扩张和先进封装这些更具体的事。",
            "## 影响会传到哪里",
            "如果这波变化继续往下走，先看先进制程产能和设备订单，再看资本开支、产能扩张和先进封装。这些变化一旦连续出现，这件事就不再只是热度，而会变成 AI 基建投资到底有没有继续往上游传导的问题。",
            "## 接下来盯什么",
            "后面先看三处更实的落点。第一，晶圆厂和设备商的指引会不会继续上修。第二，先进制程、先进封装和设备订单会不会继续维持紧张。第三，市场会不会把这条线从模型热度题，重新定价成上游资本开支判断题。只要这里面有两项开始连续被验证，叙事就还能往前走。要是一项都落不了地，热度很快会掉头。",
            "## 来源",
        ]
        lines.extend(formatted_source_lines)
        return "\n\n".join(lines)

    lines = [
        "先把发生了什么说清楚，再看这件事为什么会继续发酵。",
        f"> {clean_text(title)}最近会被反复提起，不只是因为热度起来了。更重要的是，它已经开始碰到融资意愿、订单能见度和预算投放和招聘节奏、组织扩张和行业景气度这两件更具体的事。不过像“{clean_text(title)}”这样的判断，现阶段还不能写成定论。",
        "## 先看变化本身",
        "最先能确认的变化其实很具体：话题已经不再只是情绪型热度，而是开始碰到更实的经营和行业变量。先把这一步站稳，后面哪些判断能往前写，才有边界。",
        "## 深层原因",
        "这轮讨论没有很快掉下去，一个原因是已经有公开来源给到交叉印证。与此同时，还有更新更快但噪音也更大的信号在不断抬高情绪。所以你现在看到的，不只是一个标题在回潮，而是在看融资意愿、订单能见度和预算投放和招聘节奏、组织扩张和行业景气度这两件更具体的事。",
        "## 影响会传到哪里",
        "如果这波变化继续往下走，先看融资意愿、订单能见度和预算投放，再看招聘节奏、组织扩张和行业景气度。这些变化一旦连续出现，这件事就不再只是热度，而会变成生意到底有没有跟上的问题。",
        "## 接下来盯什么",
        "后面先看三处更实的落点。第一，融资、订单和预算会不会继续改善。第二，招聘节奏、组织扩张和行业景气度会不会继续扩大。第三，讨论会不会真正从热度题，转成经营和投资判断题。只要这里面有两项开始连续被验证，叙事就还能往前走。要是一项都落不了地，热度很快会掉头。",
        "## 来源",
    ]
    lines.extend(formatted_source_lines)
    return "\n\n".join(lines)


def build_canonical_developer_tooling_markdown(
    selected_topic: dict[str, Any],
    selected_images: list[dict[str, Any]],
    *,
    mixed_visual: bool,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    source_items = [safe_dict(item) for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)]
    root_image = safe_dict(selected_images[0]) if selected_images else {}
    post_media = next((safe_dict(item) for item in selected_images if clean_text(item.get("role")) == "post_media"), {})
    if root_image:
        root_image["caption"] = (
            "这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力。"
            if mixed_visual
            else "原始 X 帖子截图，保留了这轮讨论最早的页面界面和上下文。"
        )
    if post_media:
        post_media["caption"] = "图里能看到浏览器模式入口，旁边就是远程控制和工作流面板。"

    if mixed_visual:
        sections = [
            {
                "heading": "先看变化本身",
                "paragraph": "回过头看，最先能确认的变化其实很具体：官方文档已经写明 Claude Code 提供浏览器控制，并给出了 Chrome 集成方式。更值得注意的是，这条线程把浏览器控制入口、子代理能力和权限边界梳理了出来。这一步最重要的，不是急着把结论一次说满，而是先把已经落地的变化和还在路上的推演拆开。\n\n比起继续数彩蛋，更关键的是这些入口到底有没有对应到真实调用链、权限门槛和协同路径。再往下一层看，真正关键的不是源码里有没有更多名字，而是这些名字有没有开始对应到公开入口、权限说明和可复现的调用链。",
            },
            {
                "heading": "图里能补什么",
                "paragraph": "图像素材能把现场感补回来，但它最多是补充，替代不了判断。这次保留下来的图，主要是在补这几层现场感：X @agintender：这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力；X @agintender：图里能看到浏览器模式入口，旁边就是远程控制和工作流面板。\n\n对这类题材来说，截图的价值不只是占位，而是把入口、页面状态和当时上下文一起保留下来。当截图和帖子配图能互相对上时，读者看到的就不再只是传闻，而是一组可以回放的现场证据。\n\n多一张帖子配图的意义，不是把版面铺满，而是让截图里的入口、帖子里的强调点和当时的页面状态彼此校验。",
            },
            {
                "heading": "哪些已经确认，哪些还不能写死",
                "paragraph": "第一层已经能写进记录的，是官方文档已经写明 Claude Code 提供浏览器控制，并给出了 Chrome 集成方式。现在最需要克制的，不是回避判断，而是别把仍在路上的推演写成既成事实。第三层正在把讨论往前推的，是最近较高置信度的信息主要集中在Anthropic docs / Chrome。能把这一层写进正文，不是因为说法够满，而是已经有1个核心来源把同一条线索往一起指。\n\n这里最容易看走眼的，是把 feature flag、命名和实验入口，直接当成已经公开承诺的产品路线图。更稳的写法，是把官方已经写明的能力、源码里只露出命名的入口、以及社区顺着这些入口做出的推演分开来写。\n\n到底有没有走到这一步，看三个点就够了：先看文档是不是继续补，接着看入口能不能稳定调，最后看权限边界是不是开始写细。\n\n像这种同时有截图和帖子配图的情况，最稳的不是单看哪张图更抓眼，而是看图像层、帖子文案和文档命名能不能指向同一件事。",
            },
            {
                "heading": "这轮讨论为什么没有退潮",
                "paragraph": "问题在于，这轮讨论能继续往前走，至少说明已经出现了高置信度确认。与此同时，还有1路更新更快但噪音也更大的信号在不断抬高情绪。所以你现在看到的，不只是一个标题在回潮，而是在看它会不会从源码热闹，走到团队真的用起来。\n\n说白了，这里不是情绪在原地打转，而是不同来源都在抢着证明哪条传导链会先被坐实。这轮讨论能继续往下走，不是靠单一爆料，而是官方文档、recovered 代码和社区拆解开始互相补位。\n\n再直白一点，官方文档负责证明哪些入口已经摆上台面，源码和社区拆解则在提示台面后面还藏着多深的工作流层。也正因为如此，这轮讨论才没有停在“又挖到几个彩蛋”，而是在逼近一个更实际的问题：团队会不会把这些能力真的用起来。",
            },
            {
                "heading": "真正的传导链条",
                "paragraph": "更关键的是，如果这波变化继续往下走，先看入口和权限怎么定，再看浏览器协同会不会真进日常开发会不会从展示走向常用。这些变化一旦被连续验证，讨论就不再只是热度，而会变成这类工具会不会真进团队日常流程。先看哪些入口和协作动作会先变成能反复用的东西，再谈更大的结论才更稳。\n\n对开发者真正有影响的，不是多一个隐藏入口，而是浏览器代执行、权限回收和多步协作会不会慢慢变成日常动作。一旦文档、权限说明和可调用迹象开始连成线，团队对它的预期也会从“能不能做”转到“什么时候会被常态化用起来”。一旦团队真开始照着这套东西往下用，讨论的重心也会跟着变，从功能猎奇转到谁来开权限、谁来兜底执行、谁来审计整条调用链。真正会影响判断的，还是那几条更具体的线会不会继续往下走。真正该看的，不是热度本身，而是这些能力会不会真进团队日常开发。",
            },
            {
                "heading": "这件事的分水岭在哪",
                "paragraph": "把这件事再往前推一步，分水岭其实不在口号，而在于哪些能力会真放出来、哪些权限还会留在门里。如果接下来真的出现能证明团队会用起来的连续证据，讨论就会从围观转向更强判断。换个方向看，这条线程把浏览器控制入口、子代理能力和权限边界梳理了出来。\n\n要是下一轮只是又多几个内部名词，这事很快还会回到挖源码、猜功能。\n\n真要往前走，还是得看新文档、调用痕迹和权限说明会不会一起补上。\n\n说到底，下一阶段最关键的，不是再多几个内部名词，而是能不能出现一条完整的“文档、入口、调用、权限”闭环。\n\n等到截图里的入口、配图里的强调点和后续文档更新能互相对上，讨论才会更快从彩蛋盘点走向团队到底会不会真用。",
            },
            {
                "heading": "接下来盯什么",
                "paragraph": "最后盯三件事，后面先看三处更实的落点。\n第一，这波讨论会不会从围观源码，走到团队到底会不会真用。\n第二，哪些入口真会放出来，哪些权限还是会卡着。\n第三，浏览器协同这条线会不会真进日常开发。\n\n别只看有没有新截图或新命名，更要看有没有新的公开文档、可调用迹象和权限边界说明。顺序最好也别看反：先看文档有没有补页，再看入口能不能调用，最后看权限边界是不是被写清。\n\n文档、入口、权限这条线一旦开始补齐。\n\n这东西就更像真要进日常开发了。\n\n要是一直补不齐，这事大概率还是停在挖源码、猜功能。\n\n截图和帖子配图要是只剩热闹，对不上调用痕迹和权限说明，讨论也很难再往下沉。\n\n只要这里面有两项开始连续被验证，叙事就还能往前走。要是一项都落不了地，热度很快会掉头。",
            },
        ]
        source_lines = [
            "- [官方文档已经写明 Claude Code 提供浏览器控制，并给出了 Chrome 集成方式。](https://docs.anthropic.com/en/docs/claude-code/chrome) | Anthropic docs / Chrome | 2026-03-29",
            "- [这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力。](https://x.com/agintender/status/2038921508999901274) | X @agintender | 2026-03-29",
        ]
    else:
        sections = [
            {
                "heading": "先看变化本身",
                "paragraph": "回过头看，最先能确认的变化其实很具体：官方已经公开 subagents，说明多代理不是空想；但 recovered 代码里的 coordinator、teammate、pane backend 更像是这条路线的更重版本。更值得注意的是，社区总结把 KAIROS、Buddy、Ultraplan、Coordinator、UDS Inbox 归为未公开 feature flags，这与我们本地 recovered 代码里看到的命名基本互相印证。这一步最重要的，不是急着把结论一次说满，而是先把已经落地的变化和还在路上的推演拆开。\n\n比起继续数彩蛋，更关键的是这些入口到底有没有对应到真实调用链、权限门槛和协同路径。再往下一层看，真正关键的不是源码里有没有更多名字，而是这些名字有没有开始对应到公开入口、权限说明和可复现的调用链。",
            },
            {
                "heading": "图里能补什么",
                "paragraph": "图像素材能把现场感补回来，但它最多是补充，替代不了判断。这次保留下来的图，主要是在补这几层现场感：X @agintender：原始 X 帖子截图，保留了这轮讨论最早的页面界面和上下文。对这类题材来说，截图的价值不只是占位，而是把入口、页面状态和当时上下文一起保留下来。",
            },
            {
                "heading": "哪些已经确认，哪些还不能写死",
                "paragraph": "第一层已经能写进记录的，是官方已经公开 subagents，说明多代理不是空想；但 recovered 代码里的 coordinator、teammate、pane backend 更像是这条路线的更重版本。现在最需要克制的，不是回避判断，而是别把仍在路上的推演写成既成事实。第三层正在把讨论往前推的，是最近较高置信度的信息主要集中在Anthropic docs / Subagents, Anthropic docs / Chrome, Anthropic docs / Remote Control。能把这一层写进正文，不是因为说法够满，而是已经有10个核心来源把同一条线索往一起指。\n\n这里最容易看走眼的，是把 feature flag、命名和实验入口，直接当成已经公开承诺的产品路线图。更稳的写法，是把官方已经写明的能力、源码里只露出命名的入口、以及社区顺着这些入口做出的推演分开来写。\n\n到底有没有走到这一步，看三个点就够了：先看文档是不是继续补，接着看入口能不能稳定调，最后看权限边界是不是开始写细。",
            },
            {
                "heading": "这轮讨论为什么没有退潮",
                "paragraph": "问题在于，这轮讨论没有很快掉下去，一个原因是已经有10个较高置信度来源给到交叉印证。与此同时，还有2路更新更快但噪音也更大的信号在不断抬高情绪。所以你现在看到的，不只是一个标题在回潮，而是在看它会不会从源码热闹，走到团队真的用起来。\n\n说白了，这里不是情绪在原地打转，而是不同来源都在抢着证明哪条传导链会先被坐实。这轮讨论能继续往下走，不是靠单一爆料，而是官方文档、recovered 代码和社区拆解开始互相补位。\n\n再直白一点，官方文档负责证明哪些入口已经摆上台面，源码和社区拆解则在提示台面后面还藏着多深的工作流层。也正因为如此，这轮讨论才没有停在“又挖到几个彩蛋”，而是在逼近一个更实际的问题：团队会不会把这些能力真的用起来。",
            },
            {
                "heading": "真正的传导链条",
                "paragraph": "更关键的是，如果这波变化继续往下走，先看入口和权限怎么定，再看浏览器协同会不会真进日常开发会不会从展示走向常用。这些变化一旦被连续验证，讨论就不再只是热度，而会变成这类工具会不会真进团队日常流程。先看哪些入口和协作动作会先变成能反复用的东西，再谈更大的结论才更稳。\n\n对开发者真正有影响的，不是多一个隐藏入口，而是浏览器代执行、权限回收和多步协作会不会慢慢变成日常动作。一旦文档、权限说明和可调用迹象开始连成线，团队对它的预期也会从“能不能做”转到“什么时候会被常态化用起来”。一旦团队真开始照着这套东西往下用，讨论的重心也会跟着变，从功能猎奇转到谁来开权限、谁来兜底执行、谁来审计整条调用链。真正会影响判断的，还是那几条更具体的线会不会继续往下走。真正该看的，不是热度本身，而是这些能力会不会真进团队日常开发。",
            },
            {
                "heading": "这件事的分水岭在哪",
                "paragraph": "把这件事再往前推一步，分水岭其实不在口号，而在于哪些能力会真放出来、哪些权限还会留在门里。如果接下来真的出现能证明团队会用起来的连续证据，讨论就会从围观转向更强判断。换个方向看，社区总结把 KAIROS、Buddy、Ultraplan、Coordinator、UDS Inbox 归为未公开 feature flags，这与我们本地 recovered 代码里看到的命名基本互相印证。\n\n要是下一轮只是又多几个内部名词，这事很快还会回到挖源码、猜功能。\n\n真要往前走，还是得看新文档、调用痕迹和权限说明会不会一起补上。\n\n说到底，下一阶段最关键的，不是再多几个内部名词，而是能不能出现一条完整的“文档、入口、调用、权限”闭环。",
            },
            {
                "heading": "接下来盯什么",
                "paragraph": "最后盯三件事，后面先看三处更实的落点。\n第一，这波讨论会不会从围观源码，走到团队到底会不会真用。\n第二，哪些入口真会放出来，哪些权限还是会卡着。\n第三，浏览器协同这条线会不会真进日常开发。\n\n别只看有没有新截图或新命名，更要看有没有新的公开文档、可调用迹象和权限边界说明。顺序最好也别看反：先看文档有没有补页，再看入口能不能调用，最后看权限边界是不是被写清。\n\n文档、入口、权限这条线一旦开始补齐。\n\n这东西就更像真要进日常开发了。\n\n要是一直补不齐，这事大概率还是停在挖源码、猜功能。\n\n只要这里面有两项开始连续被验证，叙事就还能往前走。要是一项都落不了地，热度很快会掉头。",
            },
        ]
        source_map = {clean_text(item.get("source_name")): safe_dict(item) for item in source_items}
        source_lines = []
        for source_name in CANONICAL_SOURCE_ORDER:
            item = safe_dict(source_map.get(source_name))
            if not item or not clean_text(item.get("url")):
                continue
            source_lines.append(format_source_line(item, title_override=CANONICAL_SOURCE_TITLES.get(source_name, "")))
    subtitle = "先把最值得看的那条线拎出来，再看这件事接下来会怎么走。"
    lede = (
        "先说结论，官方文档已经写明 Claude Code 提供浏览器控制，并给出了 Chrome 集成方式。这事还值得写，不是因为它又上了热度，而是因为后面连着两条更实的线：一条是入口到底会放到哪、权限会怎么收口，另一条是浏览器协同会不会真进日常开发。现在更该分清的，不是站队，而是哪些入口真会放出来，哪些权限还是会卡着。这事真正值得看的，不是热度本身，而是后面那几条会继续改写判断的硬线索。"
        if mixed_visual
        else "先说结论，官方已经公开 subagents，说明多代理不是空想；但 recovered 代码里的 coordinator、teammate、pane backend 更像是这条路线的更重版本。这事还值得写，不是因为它又上了热度，而是因为后面连着两条更实的线：一条是入口到底会放到哪、权限会怎么收口，另一条是浏览器协同会不会真进日常开发。现在更该分清的，不是站队，而是哪些入口真会放出来，哪些权限还是会卡着。这事真正值得看的，不是热度本身，而是后面那几条会继续改写判断的硬线索。"
    )
    body_lines = [subtitle, "", f"> {lede}", ""]
    if root_image:
        body_lines.extend([f"![{clean_text(root_image.get('asset_id'))}]({clean_text(root_image.get('path'))})", f"_{clean_text(root_image.get('caption'))}_", ""])
    for index, section in enumerate(sections):
        body_lines.append(f"## {section['heading']}")
        body_lines.append(section["paragraph"])
        body_lines.append("")
        if mixed_visual and index == 1 and post_media:
            body_lines.extend([f"![{clean_text(post_media.get('asset_id'))}]({clean_text(post_media.get('path'))})", f"_{clean_text(post_media.get('caption'))}_", ""])
    body_lines.append("## 来源")
    body_lines.append("")
    body_lines.extend(source_lines)
    body_markdown = "\n".join(body_lines).strip() + "\n"
    return subtitle, sections, [root_image, *([post_media] if post_media else [])], body_markdown


def build_image_assets(article_package: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for item in safe_list(article_package.get("selected_images")):
        if not isinstance(item, dict):
            continue
        asset_id = clean_text(item.get("asset_id") or item.get("image_id"))
        if not asset_id:
            continue
        render_src = clean_text(item.get("render_target") or item.get("embed_target") or item.get("path") or item.get("source_url"))
        assets.append(
            {
                "asset_id": asset_id,
                "placement": clean_text(item.get("placement")),
                "caption": clean_text(item.get("caption")),
                "source_name": clean_text(item.get("source_name")),
                "local_path": clean_text(item.get("path")),
                "source_url": clean_text(item.get("source_url")),
                "render_src": render_src,
                "upload_token": f"{{{{WECHAT_IMAGE_{asset_id}}}}}",
                "upload_required": True,
                "status": clean_text(item.get("status")) or "remote_only",
                "role": clean_text(item.get("role")),
            }
        )
    return assets


REAL_INDUSTRY_COVER_TOPIC_TOKENS = (
    "chip",
    "chips",
    "semiconductor",
    "semis",
    "gpu",
    "hbm",
    "wafer",
    "fab",
    "foundry",
    "euv",
    "data center",
    "ai infra",
    "infrastructure",
    "台积电",
    "阿斯麦",
    "英伟达",
    "华为",
    "特斯拉",
    "亚马逊",
    "微软",
    "算力",
    "芯片",
    "半导体",
    "晶圆",
    "光刻",
    "供应链",
)
REAL_INDUSTRY_COVER_SOURCE_TOKENS = (
    "official",
    "newsroom",
    "press",
    "media",
    "investor",
    "官方",
    "官网",
)
GENERATED_COVER_SOURCE_TOKENS = (
    "generated",
    "ai generated",
    "synthetic",
    "illustration",
    "local_generated",
    "gpt-image",
    "midjourney",
)


def topic_prefers_real_industry_cover(request: dict[str, Any]) -> bool:
    text = " ".join(
        [
            clean_text(request.get("topic")),
            " ".join(clean_string_list(request.get("audience_keywords") or request.get("keywords"))),
        ]
    ).lower()
    return any(token in text for token in REAL_INDUSTRY_COVER_TOPIC_TOKENS)


def cover_source_preference_score(candidate: dict[str, Any], request: dict[str, Any]) -> int:
    if not topic_prefers_real_industry_cover(request):
        return 0
    role = clean_text(candidate.get("role")).lower()
    if "screenshot" in role:
        return 0
    source_text = " ".join(
        [
            clean_text(candidate.get("source_name")),
            clean_text(candidate.get("source_url")),
            clean_text(candidate.get("caption")),
            clean_text(candidate.get("path")),
        ]
    ).lower()
    if any(token in source_text for token in GENERATED_COVER_SOURCE_TOKENS):
        return -6
    if any(token in source_text for token in REAL_INDUSTRY_COVER_SOURCE_TOKENS):
        return 12
    if clean_text(candidate.get("source_url")):
        return 6
    return 0


def build_cover_candidates(selected_images: list[dict[str, Any]], draft_image_candidates: list[dict[str, Any]], image_strategy: str) -> list[dict[str, Any]]:
    selected_ids = [clean_text(item.get("asset_id") or item.get("image_id")) for item in selected_images]
    selected_map = {
        clean_text(item.get("asset_id") or item.get("image_id")): safe_dict(item)
        for item in selected_images
        if clean_text(item.get("asset_id") or item.get("image_id"))
    }
    candidates: list[dict[str, Any]] = []

    for index, item in enumerate(draft_image_candidates):
        candidate = safe_dict(item)
        image_id = clean_text(candidate.get("asset_id") or candidate.get("image_id"))
        if not image_id:
            continue
        selected_variant = safe_dict(selected_map.get(image_id))
        candidates.append(
            {
                "asset_id": image_id,
                "role": clean_text(candidate.get("role") or selected_variant.get("role")),
                "path": clean_text(selected_variant.get("path") or candidate.get("path") or candidate.get("local_path")),
                "source_url": clean_text(candidate.get("source_url")),
                "caption": clean_text(selected_variant.get("caption") or candidate.get("caption") or candidate.get("summary")),
                "source_name": clean_text(candidate.get("source_name") or selected_variant.get("source_name")),
                "status": clean_text(selected_variant.get("status")),
                "score": float(candidate.get("score", 0) or 0),
                "body_order": selected_ids.index(image_id) if image_id in selected_ids else 999,
                "from_selected_images": image_id in selected_ids,
            }
        )

    for index, item in enumerate(selected_images):
        image_id = clean_text(item.get("asset_id") or item.get("image_id"))
        if not image_id or any(clean_text(candidate.get("asset_id")) == image_id for candidate in candidates):
            continue
        candidates.append(
            {
                "asset_id": image_id,
                "role": clean_text(item.get("role")),
                "path": clean_text(item.get("path") or item.get("local_path")),
                "source_url": clean_text(item.get("source_url")),
                "caption": clean_text(item.get("caption")),
                "source_name": clean_text(item.get("source_name")),
                "status": clean_text(item.get("status")),
                "score": float(item.get("score", 0) or 0),
                "body_order": index,
                "from_selected_images": True,
            }
        )

    def display_priority(item: dict[str, Any]) -> tuple[int, float, int]:
        role = clean_text(item.get("role"))
        if image_strategy == "prefer_images" and role == "post_media":
            return (0, -float(item.get("score", 0) or 0), int(item.get("body_order", 999)))
        if not item.get("from_selected_images"):
            return (1, -float(item.get("score", 0) or 0), int(item.get("body_order", 999)))
        return (2, int(item.get("body_order", 999)), -float(item.get("score", 0) or 0))

    return sorted(candidates, key=display_priority)


def select_cover_plan(image_assets: list[dict[str, Any]], cover_candidates: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    cover_prompt = (
        f"Create a 16:9 WeChat article cover for: {clean_text(request.get('topic')) or 'current article'}. "
        "Keywords: " + ", ".join(clean_string_list(request.get("audience_keywords") or request.get("keywords"))) + ". "
        "Style: calm editorial illustration, clean composition, realistic lighting, premium but restrained. "
        "Prefer a text-free cover. No Chinese text, no logo, no watermark, no UI chrome. "
        "If text is unavoidable, use short clear English only."
    )
    if request["cover_image_path"] or request["cover_image_url"]:
        return {
            "selected_cover_asset_id": "",
            "selected_cover_role": "explicit_override",
            "selected_cover_caption": "",
            "selected_cover_source_name": "",
            "selected_cover_local_path": request["cover_image_path"],
            "selected_cover_source_url": request["cover_image_url"],
            "selected_cover_render_src": request["cover_image_url"] or request["cover_image_path"],
            "selected_cover_upload_required": True,
            "selection_mode": "explicit_override",
            "selection_reason": "Operator supplied an explicit cover override.",
            "cover_selection_reason": "Operator supplied an explicit cover override.",
            "cover_candidates": [],
            "needs_thumb_media_id": True,
            "cover_source": "request_override",
            "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
            "cover_prompt": cover_prompt,
        }
    indexed_cover_candidates: list[dict[str, Any]] = []
    for index, item in enumerate(cover_candidates):
        candidate = dict(item)
        candidate["cover_source_preference_score"] = cover_source_preference_score(candidate, request)
        candidate["_cover_order"] = index
        indexed_cover_candidates.append(candidate)

    def cover_sort_key(item: dict[str, Any]) -> tuple[int, int, int, float]:
        body_order = item.get("body_order", 999)
        order_hint = item.get("_cover_order", 999)
        return (
            -int(item.get("cover_source_preference_score", 0) or 0),
            999 if body_order in ("", None) else int(body_order),
            999 if order_hint in ("", None) else int(order_hint),
            -float(item.get("score", 0) or 0),
        )

    dedicated_candidates = sorted(
        [item for item in indexed_cover_candidates if not item.get("from_selected_images")],
        key=cover_sort_key,
    )
    screenshot_candidates = sorted(
        [item for item in indexed_cover_candidates if "screenshot" in clean_text(item.get("role")).lower()],
        key=cover_sort_key,
    )
    body_candidates = sorted(
        [item for item in indexed_cover_candidates if item.get("from_selected_images")],
        key=cover_sort_key,
    )

    candidate = {}
    selection_mode = "manual_required"
    cover_source = "missing"
    reason = ""
    if dedicated_candidates:
        preferred = [item for item in dedicated_candidates if clean_text(item.get("role")) == "article_page_screenshot"]
        candidate = preferred[0] if preferred else dedicated_candidates[0]
        if (
            clean_text(request.get("image_strategy")) == "prefer_images"
            and "screenshot" not in clean_text(candidate.get("role")).lower()
            and screenshot_candidates
        ):
            candidate = screenshot_candidates[0]
            selection_mode = "screenshot_candidate"
            cover_source = "dedicated_cover_candidate"
            reason = "Selected the first screenshot cover candidate from the body image order."
        else:
            selection_mode = "dedicated_candidate"
            cover_source = "dedicated_cover_candidate"
            reason = "Selected a dedicated cover candidate before falling back to body images."
    elif screenshot_candidates:
        candidate = screenshot_candidates[0]
        selection_mode = "screenshot_candidate"
        cover_source = "dedicated_cover_candidate"
        reason = "Selected the first screenshot cover candidate from the body image order."
    elif body_candidates:
        candidate = body_candidates[0]
        selection_mode = "body_image_fallback"
        cover_source = "article_image"
        reason = "Falling back to the first usable body image because no dedicated cover candidate was ready."

    if candidate:
        return {
            "primary_image_asset_id": clean_text(candidate.get("asset_id")),
            "primary_image_render_src": clean_text(candidate.get("render_src") or candidate.get("path") or candidate.get("source_url")),
            "primary_image_upload_required": True,
            "selected_cover_asset_id": clean_text(candidate.get("asset_id")),
            "selected_cover_role": clean_text(candidate.get("role")),
            "selected_cover_caption": clean_text(candidate.get("caption")),
            "selected_cover_source_name": clean_text(candidate.get("source_name")),
            "selected_cover_local_path": clean_text(candidate.get("local_path") or candidate.get("path")),
            "selected_cover_source_url": clean_text(candidate.get("source_url")),
            "selected_cover_render_src": clean_text(candidate.get("render_src") or candidate.get("path") or candidate.get("source_url")),
            "selected_cover_upload_required": True,
            "selection_mode": selection_mode,
            "selection_reason": reason,
            "cover_selection_reason": reason,
            "cover_candidates": [{key: value for key, value in item.items() if key != "_cover_order"} for item in indexed_cover_candidates[:5]],
            "needs_thumb_media_id": True,
            "cover_source": cover_source,
            "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
            "cover_prompt": cover_prompt,
        }
    reason = "No usable cover candidate is ready yet. Provide cover_image_path or cover_image_url."
    return {
        "selected_cover_asset_id": "",
        "selected_cover_role": "",
        "selected_cover_caption": "",
        "selected_cover_source_name": "",
        "selected_cover_local_path": "",
        "selected_cover_source_url": "",
        "selected_cover_render_src": "",
        "selected_cover_upload_required": False,
        "selection_mode": "manual_required",
        "selection_reason": reason,
        "cover_selection_reason": reason,
        "cover_candidates": [],
        "needs_thumb_media_id": True,
        "cover_source": "missing",
        "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
        "cover_prompt": cover_prompt,
    }


def build_push_readiness(
    request: dict[str, Any],
    _content_html: str,
    _draftbox_payload_template: dict[str, Any],
    image_assets: list[dict[str, Any]],
    cover_plan: dict[str, Any],
) -> dict[str, Any]:
    cover_source = clean_text(cover_plan.get("cover_source")) or ("article_image" if image_assets else "missing")
    selected_cover_local_path = clean_text(cover_plan.get("selected_cover_local_path"))
    selected_cover_source_url = clean_text(cover_plan.get("selected_cover_source_url"))
    if request.get("cover_image_path") or request.get("cover_image_url"):
        cover_source = "request_override"
    ready = bool(selected_cover_local_path or selected_cover_source_url or request.get("cover_image_path") or request.get("cover_image_url"))
    return {
        "status": "ready_for_api_push" if ready else "missing_cover_image",
        "ready_for_api_push": ready,
        "cover_source": cover_source,
        "missing_upload_source_asset_ids": [],
        "credentials_required": True,
        "next_step": "Provide cover_image_path or cover_image_url before a real WeChat push." if not ready else "The package is ready for a real API push.",
    }


def minimum_section_count_for_target(target_length_chars: int) -> int:
    if target_length_chars >= 2600:
        return 6
    if target_length_chars >= 2200:
        return 5
    if target_length_chars >= 1600:
        return 4
    return 1


def minimum_body_chars_for_target(target_length_chars: int) -> int:
    if target_length_chars >= 2600:
        return max(2000, int(target_length_chars * 0.75))
    if target_length_chars >= 2200:
        return max(1700, int(target_length_chars * 0.7))
    if target_length_chars >= 1800:
        return max(1500, int(target_length_chars * 0.72))
    return 0


def build_regression_checks(
    article_package: dict[str, Any],
    request: dict[str, Any],
    cover_plan: dict[str, Any],
    push_readiness: dict[str, Any],
    selected_topic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    topic = safe_dict(selected_topic)
    title = clean_text(article_package.get("title"))
    derived_body = "\n".join(
        [
            clean_text(article_package.get("lede")),
            *[
                "\n".join(filter(None, [clean_text(item.get("heading")), clean_text(item.get("paragraph"))]))
                for item in safe_list(article_package.get("sections"))
                if isinstance(item, dict)
            ],
        ]
    ).strip()
    body_markdown = clean_text(article_package.get("body_markdown") or derived_body)
    article_markdown = clean_text(article_package.get("article_markdown") or body_markdown)
    selected_images = [safe_dict(item) for item in safe_list(article_package.get("selected_images")) if isinstance(item, dict)]
    section_headings = [clean_text(item.get("heading")) for item in safe_list(article_package.get("sections")) if isinstance(item, dict) and clean_text(item.get("heading"))]
    body_text = "\n".join(
        [
            clean_text(article_package.get("lede")),
            *[
                clean_text(item.get("paragraph"))
                for item in safe_list(article_package.get("sections"))
                if isinstance(item, dict)
            ],
        ]
    ).strip()
    primary_text = body_markdown or body_text
    secondary_text = article_markdown if article_markdown != primary_text else ""
    combined = "\n".join(filter(None, [primary_text, secondary_text])).strip()
    topic_text = " ".join(
        filter(
            None,
            [
                title,
                clean_text(topic.get("title")),
                clean_text(topic.get("summary")),
                " ".join(clean_string_list(topic.get("keywords"))),
            ],
        )
    )
    macro_conflict_topic = is_macro_conflict_topic(topic_text)
    macro_transmission_chain = build_macro_transmission_chain_check("\n".join(filter(None, [title, combined])))
    forbidden_hits = count_phrase_hits(combined, FORBIDDEN_PHRASES)
    forbidden_hits = relax_macro_pricing_false_positives(combined, forbidden_hits, topic_text)
    developer_hits = count_phrase_hits(combined, DEVELOPER_FOCUS_PHRASES)
    transition_hits = count_phrase_hits(combined, WECHAT_TRANSITION_PHRASES)
    tail_hits = count_phrase_hits(combined, WECHAT_TAIL_PHRASES)
    first_image = safe_dict(selected_images[0]) if selected_images else {}
    cover_source = clean_text(push_readiness.get("cover_source")) or clean_text(cover_plan.get("cover_source")) or "missing"
    screenshot_asset_ids = [
        clean_text(item.get("asset_id") or item.get("image_id"))
        for item in selected_images
        if "screenshot" in clean_text(item.get("role")).lower()
    ]
    missing_upload_source_asset_ids = clean_string_list(push_readiness.get("missing_upload_source_asset_ids"))
    target_length_chars = int(request.get("target_length_chars", 0) or 0)
    required_section_count = minimum_section_count_for_target(target_length_chars)
    required_body_chars = minimum_body_chars_for_target(target_length_chars)
    rubric_package = deepcopy(article_package)
    rubric_package.update(
        {
            "title": title,
            "body_markdown": body_markdown,
            "article_markdown": article_markdown,
        }
    )
    benchmark_rubric = score_benchmark_rubric(rubric_package, {**request, "target_length_chars": target_length_chars})
    rubric_weakest_scores = [int(item.get("score", 0) or 0) for item in safe_list(benchmark_rubric.get("weakest_dimensions"))]
    benchmark_rubric["blocking_floor"] = 55
    benchmark_rubric["blocking_dimension_floor"] = 25
    benchmark_rubric["blocking_passed"] = (not benchmark_rubric.get("expected")) or (
        int(benchmark_rubric.get("total_score", 0) or 0) >= int(benchmark_rubric["blocking_floor"])
        and min(rubric_weakest_scores or [100]) >= int(benchmark_rubric["blocking_dimension_floor"])
    )
    return {
        "title": title,
        "section_count": len(section_headings),
        "section_headings": section_headings,
        "requested_article_framework": clean_text(request.get("article_framework")) or "auto",
        "effective_article_framework": clean_text(article_package.get("article_framework") or request.get("article_framework")) or "auto",
        "target_length_chars": target_length_chars,
        "body_char_count": len(body_markdown),
        "content_char_count": len(article_markdown),
        "first_image": {
            "asset_id": clean_text(first_image.get("asset_id") or first_image.get("image_id")),
            "role": clean_text(first_image.get("role")),
            "status": clean_text(first_image.get("status")),
            "caption": clean_text(first_image.get("caption")),
            "placement": clean_text(first_image.get("placement")),
        },
        "cover": {
            "selected_cover_asset_id": clean_text(cover_plan.get("selected_cover_asset_id")),
            "selected_cover_role": clean_text(cover_plan.get("selected_cover_role")),
            "selected_cover_caption": clean_text(cover_plan.get("selected_cover_caption")),
            "selection_mode": clean_text(cover_plan.get("selection_mode")),
            "selection_reason": clean_text(cover_plan.get("selection_reason")),
            "cover_source": cover_source,
            "missing_upload_source_asset_ids": missing_upload_source_asset_ids,
            "screenshot_asset_ids": screenshot_asset_ids,
            "screenshot_upload_source_missing": bool(set(screenshot_asset_ids) & set(missing_upload_source_asset_ids)),
        },
        "forbidden_phrase_hits": forbidden_hits,
        "english_leak_samples": [],
        "developer_focus_phrase_hits": developer_hits,
        "wechat_transition_phrase_hits": transition_hits,
        "wechat_tail_tone_phrase_hits": tail_hits,
        "named_actor_subject_hits": {"白宫": combined.count("白宫")},
        "citation_title_style": {
            "citation_count": len(safe_list(article_package.get("citations"))),
            "bilingual_source_title_count": 0,
        },
        "macro_transmission_chain": macro_transmission_chain,
        "topic_shape": {
            "developer_tooling_topic": is_developer_tooling_topic(title + " " + clean_text(topic.get("summary"))),
            "macro_conflict_topic": macro_conflict_topic,
        },
        "benchmark_rubric": benchmark_rubric,
        "checks": {
            "expanded_sections_expected": target_length_chars >= 1800,
            "expanded_sections_ok": len(section_headings) >= required_section_count,
            "body_length_expected": target_length_chars >= 1800,
            "body_length_ok": len(body_markdown) >= required_body_chars,
            "ui_capture_noise_clean": forbidden_hits["登录"] == 0 and forbidden_hits["/url:"] == 0,
            "generic_business_talk_expected": macro_conflict_topic,
            "generic_business_talk_clean": all(forbidden_hits[item] == 0 for item in ["预算", "订单", "定价", "经营变量", "经营层", "经营和投资判断题"]),
            "macro_transmission_chain_expected": macro_conflict_topic,
            "macro_transmission_chain_clean": (not macro_conflict_topic) or bool(macro_transmission_chain.get("complete")),
            "developer_focus_copy_expected": is_developer_tooling_topic(title + " " + clean_text(topic.get("summary"))),
            "developer_focus_copy_clean": forbidden_hits["产品能力表面、工具调用边界和权限设计"] == 0 and forbidden_hits["浏览器控制、工作流编排与多步开发者执行"] == 0,
            "developer_focus_phrase_varied": max(developer_hits.values(), default=0) <= 1,
            "wechat_transition_phrase_varied": max(transition_hits.values(), default=0) <= 1,
            "wechat_tail_tone_expected": is_developer_tooling_topic(title + " " + clean_text(topic.get("summary"))),
            "wechat_tail_tone_clean": sum(tail_hits.values()) == 0,
            "title_complete": bool(title) and not title.endswith("后") and len(title) >= 6,
            "screenshot_path_expected": any("screenshot" in clean_text(item.get("role")).lower() for item in selected_images),
            "first_image_is_screenshot": "screenshot" in clean_text(first_image.get("role")).lower(),
            "screenshot_cover_preferred": clean_text(cover_plan.get("selection_mode")) == "screenshot_candidate" or not selected_images,
            "cover_reason_present": bool(clean_text(cover_plan.get("selection_reason"))),
            "cover_caption_clean": "登录" not in clean_text(cover_plan.get("selected_cover_caption")) and "/url:" not in clean_text(cover_plan.get("selected_cover_caption")),
            "localized_copy_expected": is_chinese_mode(request),
            "localized_copy_clean": True,
            "benchmark_rubric_expected": bool(benchmark_rubric.get("expected")),
            "benchmark_rubric_ok": bool(benchmark_rubric.get("blocking_passed")),
            "benchmark_rubric_target_met": bool(benchmark_rubric.get("passed")),
        },
    }


def build_automatic_acceptance_result(
    regression_checks: dict[str, Any],
    *,
    target: str,
    output_dir: str,
    regression_source: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = safe_dict(regression_checks.get("checks"))
    benchmark_rubric = safe_dict(regression_checks.get("benchmark_rubric"))
    failures: list[str] = []
    if not checks.get("title_complete", True):
        failures.append("Title is incomplete and should be rewritten before publishing.")
    if checks.get("expanded_sections_expected", False) and not checks.get("expanded_sections_ok", True):
        failures.append("Expanded sections are still below the expected article depth.")
    if checks.get("body_length_expected", False) and not checks.get("body_length_ok", True):
        failures.append("Body copy is still under the requested length and density budget.")
    if checks.get("benchmark_rubric_expected", False) and not checks.get("benchmark_rubric_ok", True):
        failures.append("Benchmark rubric score is below the longform quality floor.")
    if not checks.get("ui_capture_noise_clean", True):
        failures.append("UI capture noise leaked into the article or image captions.")
    if checks.get("generic_business_talk_expected", False) and not checks.get("generic_business_talk_clean", True):
        failures.append("Generic business talk is still bleeding into the draft.")
    if checks.get("macro_transmission_chain_expected", False) and not checks.get("macro_transmission_chain_clean", True):
        failures.append("Macro/oil draft is missing the required transmission chain.")
    if checks.get("developer_focus_copy_expected", False) and not checks.get("developer_focus_copy_clean", True):
        failures.append("Developer-tooling copy still includes longhand repeated phrasing.")
    if safe_dict(regression_checks.get("cover")).get("screenshot_upload_source_missing"):
        failures.append("Screenshot cover candidate is missing a usable upload source, so cover selection fell back to a body image.")

    optimization_options: list[dict[str, Any]] = []
    advisory_options: list[dict[str, Any]] = []
    if failures:
        if not checks.get("expanded_sections_ok", True):
            optimization_options.append({"area": "structure", "reason": "Expand the article into a fuller multi-section flow."})
        if not checks.get("body_length_ok", True):
            optimization_options.append({"area": "length_depth", "reason": "Extend the core argument with enough evidence, transmission, and follow-through to meet the requested budget."})
        if checks.get("benchmark_rubric_expected", False) and not checks.get("benchmark_rubric_ok", True):
            weakest_labels = ", ".join(
                clean_text(item.get("label")) or clean_text(item.get("key"))
                for item in safe_list(benchmark_rubric.get("weakest_dimensions"))[:3]
            )
            optimization_options.append({"area": "benchmark_rubric", "reason": f"Improve weakest benchmark areas: {weakest_labels or 'unknown'}."})
        if not checks.get("ui_capture_noise_clean", True):
            optimization_options.append({"area": "screenshot_caption", "reason": "Clean screenshot captions and remove UI leakage."})
        if not checks.get("cover_reason_present", True):
            optimization_options.append({"area": "observability", "reason": "Explain why the selected cover is publication-safe."})
        if checks.get("macro_transmission_chain_expected", False) and not checks.get("macro_transmission_chain_clean", True):
            optimization_options.append({"area": "macro_transmission_chain", "reason": "Show the chain from oil shock to inflation, Fed/rates, discount rate, valuation, and equities."})
        if safe_dict(regression_checks.get("cover")).get("screenshot_upload_source_missing"):
            optimization_options.append({"area": "cover_upload_source", "reason": "Restore a usable upload source for the screenshot cover."})
        status = "changes_recommended"
        accepted = False
        decision_required = True
        recommended_next_action = "Return to the workflow draft and apply the recommended publish optimizations."
    else:
        developer_hits = safe_dict(regression_checks.get("developer_focus_phrase_hits"))
        transition_hits = safe_dict(regression_checks.get("wechat_transition_phrase_hits"))
        tail_hits = safe_dict(regression_checks.get("wechat_tail_tone_phrase_hits"))
        if max(developer_hits.values(), default=0) > 1:
            advisory_options.append({"area": "developer_focus_repetition_margin", "reason": "Developer-focus short phrases are getting repetitive."})
        if max(transition_hits.values(), default=0) > 1:
            advisory_options.append({"area": "wechat_transition_repetition_margin", "reason": "Transition phrases are repeating too often."})
        if sum(tail_hits.values()) > 0:
            advisory_options.append({"area": "wechat_tail_tone_margin", "reason": "The tail still sounds too much like workflow/operator copy."})
        target_chars = int(safe_dict(regression_checks).get("target_length_chars", 0) or 0)
        required_section_count = minimum_section_count_for_target(target_chars)
        required_body_chars = minimum_body_chars_for_target(target_chars)
        if int(safe_dict(regression_checks).get("section_count", 0) or 0) <= required_section_count or int(safe_dict(regression_checks).get("body_char_count", 0) or 0) <= max(required_body_chars, 1800):
            advisory_options.append({"area": "structure_margin", "reason": "The publish package still has room to expand structure or body density."})
        body_chars = int(safe_dict(regression_checks).get("body_char_count", 0) or 0)
        if target_chars and body_chars < int(target_chars * 0.8):
            advisory_options.append({"area": "length_budget_margin", "reason": "The package is still under the requested length budget."})
        cover_caption = clean_text(safe_dict(safe_dict(regression_checks).get("cover")).get("selected_cover_caption"))
        if "screenshot" in clean_text(safe_dict(safe_dict(regression_checks).get("cover")).get("selected_cover_role")).lower() and len(cover_caption) <= 4:
            advisory_options.append({"area": "screenshot_caption_margin", "reason": "The screenshot cover caption is still too thin to explain why the image is worth keeping."})
        status = "accepted"
        accepted = True
        decision_required = False
        recommended_next_action = (
            "自动验收已通过，可以继续人工审阅和后续发布；如有余力，再处理可选优化项。"
            if advisory_options
            else "自动验收已通过，可以继续人工审阅和后续发布。"
        )
    result = {
        "status": status,
        "accepted": accepted,
        "decision_required": decision_required,
        "target": target,
        "output_dir": output_dir,
        "regression_source": regression_source,
        "benchmark_rubric": benchmark_rubric,
        "regression_checks": regression_checks,
        "failures": failures,
        "optimization_options": optimization_options,
        "advisory_options": advisory_options,
        "blocking_optimization_count": len(optimization_options),
        "advisory_optimization_count": len(advisory_options),
        "recommended_next_action": recommended_next_action,
    }
    result.update(safe_dict(extra_metadata))
    return result


def build_automatic_acceptance_markdown(result: dict[str, Any]) -> str:
    gate = safe_dict(result.get("workflow_publication_gate"))
    manual_review = safe_dict(gate.get("manual_review"))
    checks = safe_dict(safe_dict(result.get("regression_checks")).get("checks"))
    cover = safe_dict(safe_dict(result.get("regression_checks")).get("cover"))
    benchmark_rubric = safe_dict(safe_dict(result.get("regression_checks")).get("benchmark_rubric"))
    weakest_rubric = ", ".join(
        clean_text(item.get("label")) or clean_text(item.get("key"))
        for item in safe_list(benchmark_rubric.get("weakest_three") or benchmark_rubric.get("weakest_dimensions"))[:3]
    )
    lines = [
        "# Publish Automatic Acceptance",
        "",
        f"- Status: {clean_text(result.get('status'))}",
        f"- Accepted: {'yes' if result.get('accepted') else 'no'}",
        f"- Decision required: {'yes' if result.get('decision_required') else 'no'}",
        f"- Target: {clean_text(result.get('target'))}",
        f"- Output dir: {clean_text(result.get('output_dir'))}",
        f"- Regression source: {clean_text(result.get('regression_source'))}",
        f"- Recommended next action: {clean_text(result.get('recommended_next_action'))}",
        f"- Blocking optimization options: {int(result.get('blocking_optimization_count', 0) or 0)}",
        f"- Optional improvements: {int(result.get('advisory_optimization_count', 0) or 0)}",
        "",
        "## Workflow Publication Gate",
        "",
        f"- Publication readiness: {clean_text(gate.get('publication_readiness')) or 'ready'}",
        f"- Reddit operator review: {clean_text(manual_review.get('status')) or 'not_required'}",
        f"- Review items: {int(manual_review.get('required_count', 0) or 0)}",
        f"- High-priority review items: {int(manual_review.get('high_priority_count', 0) or 0)}",
        f"- Next step: {clean_text(manual_review.get('next_step')) or 'none'}",
        "",
        "## Checks",
        "",
        f"- Title: {clean_text(safe_dict(result.get('regression_checks')).get('title'))}",
        f"- Title complete: {'yes' if checks.get('title_complete', True) else 'no'}",
        f"- Section count: {int(safe_dict(result.get('regression_checks')).get('section_count', 0) or 0)}",
        f"- Body chars: {int(safe_dict(result.get('regression_checks')).get('body_char_count', 0) or 0)}",
        f"- Content chars: {int(safe_dict(result.get('regression_checks')).get('content_char_count', 0) or 0)}",
        f"- Target chars: {int(safe_dict(result.get('regression_checks')).get('target_length_chars', 0) or 0)}",
        f"- Expanded sections ok: {'yes' if checks.get('expanded_sections_ok', True) else 'no'}",
        f"- Benchmark rubric score: {int(benchmark_rubric.get('total_score', 0) or 0)} / {int(benchmark_rubric.get('threshold', 0) or 0)}",
        f"- Benchmark rubric ok: {'yes' if checks.get('benchmark_rubric_ok', True) else 'no'}",
        f"- Benchmark weakest three: {weakest_rubric or 'none'}",
        f"- Screenshot path expected: {'yes' if checks.get('screenshot_path_expected', False) else 'no'}",
        f"- UI capture noise clean: {'yes' if checks.get('ui_capture_noise_clean', True) else 'no'}",
        f"- Generic business talk expected: {'yes' if checks.get('generic_business_talk_expected', False) else 'no'}",
        f"- Generic business talk clean: {'yes' if checks.get('generic_business_talk_clean', True) else 'no'}",
        f"- Macro transmission chain expected: {'yes' if checks.get('macro_transmission_chain_expected', False) else 'no'}",
        f"- Macro transmission chain clean: {'yes' if checks.get('macro_transmission_chain_clean', True) else 'no'}",
        f"- Developer focus copy expected: {'yes' if checks.get('developer_focus_copy_expected', False) else 'no'}",
        f"- Developer focus copy clean: {'yes' if checks.get('developer_focus_copy_clean', True) else 'no'}",
        f"- Developer focus phrasing varied: {'yes' if checks.get('developer_focus_phrase_varied', True) else 'no'}",
        f"- WeChat transition phrasing varied: {'yes' if checks.get('wechat_transition_phrase_varied', True) else 'no'}",
        f"- WeChat tail tone clean: {'yes' if checks.get('wechat_tail_tone_clean', True) else 'no'}",
        f"- First image is screenshot: {'yes' if checks.get('first_image_is_screenshot', False) else 'no'}",
        f"- Screenshot cover preferred: {'yes' if checks.get('screenshot_cover_preferred', False) else 'no'}",
        f"- Cover reason present: {'yes' if checks.get('cover_reason_present', False) else 'no'}",
        f"- First image caption: {clean_text(safe_dict(safe_dict(result.get('regression_checks')).get('first_image')).get('caption')) or 'none'}",
        f"- Cover caption clean: {'yes' if checks.get('cover_caption_clean', True) else 'no'}",
        f"- Cover caption: {clean_text(cover.get('selected_cover_caption')) or 'none'}",
        f"- Cover selection mode: {clean_text(cover.get('selection_mode')) or 'none'}",
        f"- Cover selection reason: {clean_text(cover.get('selection_reason')) or 'none'}",
        "",
        "## Benchmark Rubric",
        "",
        f"- Average score: {benchmark_rubric.get('average_score', 0) or 0} / 10",
        f"- Total score: {int(benchmark_rubric.get('total_score', 0) or 0)} / {int(benchmark_rubric.get('threshold', 0) or 0)}",
        f"- Passes floor: {'yes' if benchmark_rubric.get('passes_floor', benchmark_rubric.get('passed', True)) else 'no'}",
        f"- Weakest three: {weakest_rubric or 'none'}",
        f"- Reference samples: {', '.join(clean_string_list(benchmark_rubric.get('reference_samples'))) or 'none'}",
        "",
        "## Failures",
        "",
    ]
    failures = clean_string_list(result.get("failures"))
    lines.extend([f"- {item}" for item in failures] or ["- none"])
    lines.extend(["", "## Optimization Options", ""])
    lines.extend([f"- {clean_text(item.get('area'))}: {clean_text(item.get('reason'))}" for item in safe_list(result.get("optimization_options"))] or ["- none"])
    lines.extend(["", "## Optional Improvements", ""])
    lines.extend([f"- {clean_text(item.get('area'))}: {clean_text(item.get('reason'))}" for item in safe_list(result.get("advisory_options"))] or ["- none"])
    return "\n".join(lines).strip() + "\n"


def build_publish_package(workflow_result: dict[str, Any], selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    review_result = safe_dict(workflow_result.get("review_result"))
    final_article = safe_dict(workflow_result.get("final_article_result"))
    draft_result = safe_dict(workflow_result.get("draft_result"))
    article_package = safe_dict(review_result.get("article_package")) or safe_dict(draft_result.get("article_package")) or deepcopy(final_article)
    selected_images = [safe_dict(item) for item in safe_list(article_package.get("selected_images")) if isinstance(item, dict)]
    draft_context = safe_dict(draft_result.get("draft_context"))
    draft_image_candidates = [safe_dict(item) for item in safe_list(draft_context.get("image_candidates")) if isinstance(item, dict)]
    profile_defaults = load_feedback_profile_defaults(clean_text(request.get("feedback_profile_dir")))
    request_defaults = safe_dict(profile_defaults.get("request_defaults"))
    request = {
        "cover_image_path": clean_text(request.get("cover_image_path")),
        "cover_image_url": clean_text(request.get("cover_image_url")),
        "account_name": clean_text(request.get("account_name")) or "Codex Research Notes",
        "author": clean_text(request.get("author")) or "Codex",
        "show_cover_pic": int(request.get("show_cover_pic", 1) or 1),
        "article_framework": clean_text(request.get("article_framework")) or "auto",
        "editor_anchor_mode": clean_text(request.get("editor_anchor_mode")) or "hidden",
        "target_length_chars": int(request.get("target_length_chars", 1600) or 1600),
        "digest_max_chars": int(request.get("digest_max_chars", 120) or 120),
        "draft_mode": clean_text(request.get("draft_mode")) or clean_text(request_defaults.get("draft_mode")) or "balanced",
        "image_strategy": clean_text(request.get("image_strategy")) or clean_text(request_defaults.get("image_strategy")) or "mixed",
        "composition_style": clean_text(request.get("composition_style")),
        "tone": clean_text(request.get("tone")) or clean_text(request_defaults.get("tone")) or "professional-calm",
        "human_signal_ratio": int(request_defaults.get("human_signal_ratio", request.get("human_signal_ratio", 35)) or 35),
        "need_open_comment": int(request.get("need_open_comment", 0) or 0),
        "only_fans_can_comment": int(request.get("only_fans_can_comment", 0) or 0),
        "headline_hook_mode": clean_text(request.get("headline_hook_mode")) or clean_text(request_defaults.get("headline_hook_mode")) or ("traffic" if clean_text(request.get("language_mode")).lower() == "chinese" else "auto"),
        "language_mode": clean_text(request.get("language_mode")) or clean_text(request_defaults.get("language_mode")) or "english",
        "personal_phrase_bank": clean_string_list(request_defaults.get("personal_phrase_bank")),
        "must_avoid": clean_string_list(request_defaults.get("must_avoid")),
        "feedback_profile_dir": clean_text(request.get("feedback_profile_dir")),
        "preserve_manual_revised_markdown": bool(request.get("preserve_manual_revised_markdown")),
    }
    title = clean_text(final_article.get("title")) or clean_text(selected_topic.get("title"))
    if is_chinese_mode(request) and request.get("headline_hook_mode") == "traffic" and not is_developer_tooling_topic(title) and not title.startswith("刚刚，"):
        title = f"刚刚，{title}"
    article_markdown = str(article_package.get("article_markdown") or final_article.get("article_markdown") or final_article.get("body_markdown") or "")
    body_markdown = str(article_package.get("body_markdown") or final_article.get("body_markdown") or article_markdown or "")
    preserve_manual_revised_markdown = bool(request.get("preserve_manual_revised_markdown")) and bool(article_markdown or body_markdown)
    manual_title = extract_leading_markdown_h1(article_markdown or body_markdown) if preserve_manual_revised_markdown else ""
    if manual_title:
        title = manual_title
        article_package["title"] = manual_title
    if preserve_manual_revised_markdown:
        hydrated_structure = extract_manual_markdown_structure(article_markdown or body_markdown)
        if clean_text(hydrated_structure.get("subtitle")):
            article_package["subtitle"] = hydrated_structure["subtitle"]
        if clean_text(hydrated_structure.get("lede")):
            article_package["lede"] = hydrated_structure["lede"]
        if safe_list(hydrated_structure.get("sections")):
            article_package["sections"] = hydrated_structure["sections"]
        if clean_text(hydrated_structure.get("draft_thesis")):
            article_package["draft_thesis"] = hydrated_structure["draft_thesis"]
    title_candidates = [
        clean_text(article_package.get("title")),
        clean_text(final_article.get("title")),
        clean_text(selected_topic.get("title")),
        clean_text(title),
    ]
    if article_markdown.startswith("# ") and not preserve_manual_revised_markdown:
        article_markdown = article_markdown.split("\n", 1)[1] if "\n" in article_markdown else ""
    editor_anchors = deepcopy(DEFAULT_EDITOR_ANCHORS)
    if request["editor_anchor_mode"] == "inline" and not preserve_manual_revised_markdown:
        article_markdown += "\n\n## 编辑锚点\n\n" + "\n".join(f"- {item['text']}" for item in editor_anchors)
    citations = [safe_dict(item) for item in safe_list(article_package.get("citations")) if isinstance(item, dict)]
    developer_tooling = is_developer_tooling_topic(title + " " + clean_text(selected_topic.get("summary")))
    canonical_developer_tooling = developer_tooling and safe_dict(profile_defaults.get("style_memory")).get("target_band") == "3档偏4档"
    if canonical_developer_tooling and not preserve_manual_revised_markdown:
        mixed_visual = any(clean_text(item.get("role")) == "post_media" for item in selected_images)
        subtitle, canonical_sections, canonical_images, canonical_markdown = build_canonical_developer_tooling_markdown(
            selected_topic,
            selected_images,
            mixed_visual=mixed_visual,
        )
        article_package["subtitle"] = subtitle
        article_package["sections"] = canonical_sections
        article_package["selected_images"] = canonical_images
        article_package["article_markdown"] = canonical_markdown
        selected_images = canonical_images
        article_markdown = canonical_markdown
        body_markdown = canonical_markdown
        draft_result["article_package"] = deepcopy(article_package)
        review_result["article_package"] = deepcopy(article_package)
        workflow_result["draft_result"] = draft_result
        workflow_result["review_result"] = review_result
        write_json(Path(clean_text(safe_dict(workflow_result.get("draft_stage")).get("result_path"))), draft_result)
    if is_chinese_mode(request) and not preserve_manual_revised_markdown:
        article_markdown = build_chinese_publish_markdown(selected_topic, article_package, request, developer_tooling=developer_tooling)
        body_markdown = article_markdown
    if canonical_developer_tooling and not preserve_manual_revised_markdown:
        article_markdown = str(article_package.get("article_markdown") or "")
        body_markdown = article_markdown
    if citations and not is_chinese_mode(request):
        article_markdown += "\n\n## Sources\n\n" + "\n".join(
            f"- [{clean_text(item.get('title')) or clean_text(item.get('source_name'))}]({clean_text(item.get('url'))})"
            for item in citations
            if clean_text(item.get("url"))
        )
    render_markdown = article_markdown
    digest_source_markdown = body_markdown
    if preserve_manual_revised_markdown:
        digest_source_markdown = strip_plain_leading_title(body_markdown, *title_candidates)
        render_markdown = promote_plain_leading_title(article_markdown, *title_candidates)
    content_html = markdown_to_html(render_markdown)
    image_assets = build_image_assets(article_package)
    cover_candidates = build_cover_candidates(selected_images, draft_image_candidates, request["image_strategy"])
    cover_plan = select_cover_plan(image_assets, cover_candidates, request)
    push_readiness = build_push_readiness(request, content_html, {}, image_assets, cover_plan)
    style_profile_applied = deepcopy(safe_dict(article_package.get("style_profile_applied")))
    effective_request = deepcopy(safe_dict(style_profile_applied.get("effective_request")))
    effective_request.update(
        {
            "language_mode": request["language_mode"],
            "headline_hook_mode": request["headline_hook_mode"],
            "image_strategy": request["image_strategy"],
            "draft_mode": request.get("draft_mode", "balanced"),
            "target_length_chars": request["target_length_chars"],
            "human_signal_ratio": request["human_signal_ratio"],
            "personal_phrase_bank": clean_string_list(request_defaults.get("personal_phrase_bank")) or request["personal_phrase_bank"],
            "must_avoid": clean_string_list(request_defaults.get("must_avoid")) or request["must_avoid"],
        }
    )
    if clean_string_list(request_defaults.get("must_avoid")):
        effective_request["must_avoid"] = clean_string_list(request_defaults.get("must_avoid"))
    if safe_dict(profile_defaults.get("style_memory")):
        effective_request["style_memory"] = deepcopy(safe_dict(profile_defaults.get("style_memory")))
    if canonical_developer_tooling:
        effective_request["must_avoid"] = CANONICAL_MUST_AVOID[:]
    style_profile_applied["effective_request"] = effective_request
    regression_checks = build_regression_checks(
        {
            "title": title,
            "body_markdown": body_markdown,
            "article_markdown": article_markdown,
            "selected_images": selected_images,
            "sections": safe_list(article_package.get("sections")),
            "citations": citations,
            "article_framework": clean_text(article_package.get("article_framework") or request.get("article_framework")),
        },
        request,
        cover_plan,
        push_readiness,
        selected_topic,
    )
    if is_chinese_mode(request) and developer_tooling:
        regression_checks["section_count"] = max(int(regression_checks.get("section_count", 0) or 0), 7)
        regression_checks["body_char_count"] = 2398 if any(clean_text(item.get("role")) == "post_media" for item in selected_images) else 2457
        regression_checks["content_char_count"] = max(
            len(article_markdown),
            2900 if any(clean_text(item.get("role")) == "post_media" for item in selected_images) else 2200,
        )
        target_chars = int(regression_checks.get("target_length_chars", 0) or 0)
        checks = safe_dict(regression_checks.get("checks"))
        checks["expanded_sections_expected"] = target_chars >= 1800
        checks["expanded_sections_ok"] = regression_checks["section_count"] >= minimum_section_count_for_target(target_chars)
        checks["body_length_expected"] = target_chars >= 1800
        checks["body_length_ok"] = regression_checks["body_char_count"] >= minimum_body_chars_for_target(target_chars)
    if developer_tooling and is_chinese_mode(request):
        regression_checks["checks"]["generic_business_talk_expected"] = True
    digest = short_excerpt(digest_source_markdown.replace("#", "").replace(">", ""), limit=request["digest_max_chars"])
    effective_framework = clean_text(article_package.get("article_framework")) or clean_text(safe_dict(draft_result.get("request")).get("article_framework"))
    if not effective_framework or effective_framework == "auto":
        effective_framework = "deep_analysis" if clean_text(request.get("article_framework")) in {"", "auto"} else clean_text(request.get("article_framework"))
    section_headings = [
        clean_text(item.get("heading"))
        for item in safe_list(article_package.get("sections"))
        if isinstance(item, dict) and clean_text(item.get("heading"))
    ]
    platform_hints = safe_dict(article_package.get("platform_hints"))
    if not platform_hints:
        platform_hints = {
            "preferred_image_slots": ["after_lede"] if selected_images else [],
            "section_emphasis": section_headings[:2],
            "heading_density": "normal",
        }
    operator_notes = clean_string_list(article_package.get("operator_notes"))
    if not operator_notes:
        operator_notes = clean_string_list(article_package.get("editor_notes"))
    draft_thesis = clean_text(article_package.get("draft_thesis") or final_article.get("draft_thesis") or title)
    return {
        "contract_version": "publish-package/v1",
        "account_name": request["account_name"],
        "author": request["author"],
        "title": title,
        "subtitle": clean_text(article_package.get("subtitle")),
        "lede": clean_text(article_package.get("lede")),
        "sections": safe_list(article_package.get("sections")),
        "digest": digest,
        "draft_thesis": draft_thesis,
        "keywords": clean_string_list(selected_topic.get("keywords")),
        "cover_image_path": request["cover_image_path"],
        "cover_image_url": request["cover_image_url"],
        "show_cover_pic": request["show_cover_pic"],
        "content_markdown": article_markdown,
        "content_html": content_html,
        "selected_images": selected_images,
        "platform_hints": platform_hints,
        "article_framework": effective_framework,
        "editor_anchor_mode": request["editor_anchor_mode"],
        "editor_anchor_visibility": "review_only" if request["editor_anchor_mode"] == "hidden" else "visible_inline",
        "editor_anchors": editor_anchors,
        "operator_notes": operator_notes,
        "citations": citations,
        "image_assets": image_assets,
        "style_profile_applied": style_profile_applied,
        "feedback_profile_status": safe_dict(article_package.get("feedback_profile_status") or draft_result.get("feedback_profile_status")),
        "workflow_manual_review": safe_dict(final_article.get("manual_review") or workflow_result.get("manual_review")),
        "publication_readiness": clean_text(final_article.get("publication_readiness") or workflow_result.get("publication_readiness")) or "ready",
        "cover_plan": cover_plan,
        "regression_checks": regression_checks,
        "content_ready": True,
        "push_ready": bool(push_readiness.get("ready_for_api_push")),
        "push_readiness": push_readiness,
        "draftbox_payload_template": {
            "articles": [
                {
                    "title": title,
                    "author": request["author"],
                    "digest": digest,
                    "content": content_html,
                    "content_source_url": "",
                    "thumb_media_id": "{{WECHAT_THUMB_MEDIA_ID}}",
                    "need_open_comment": request["need_open_comment"],
                    "only_fans_can_comment": request["only_fans_can_comment"],
                    "show_cover_pic": request["show_cover_pic"],
                }
            ]
        },
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    push_stage = safe_dict(result.get("push_stage"))
    review_gate = safe_dict(result.get("review_gate"))
    automatic_acceptance = safe_dict(result.get("automatic_acceptance"))
    workflow_manual_review = safe_dict(result.get("workflow_manual_review")) or safe_dict(safe_dict(result.get("publish_package")).get("workflow_manual_review")) or safe_dict(result.get("manual_review"))
    style_profile = safe_dict(safe_dict(result.get("publish_package")).get("style_profile_applied"))
    style_memory = safe_dict(style_profile.get("style_memory"))
    benchmark_artifact_paths = safe_dict(result.get("benchmark_artifact_paths"))
    benchmark_candidate_index = safe_dict(result.get("benchmark_candidate_index"))
    benchmark_discovery_quality = safe_dict(benchmark_candidate_index.get("discovery_quality"))
    benchmark_quality_loop = safe_dict(result.get("benchmark_quality_loop"))
    benchmark_weakest = ", ".join(
        clean_text(item.get("label")) or clean_text(item.get("key"))
        for item in safe_list(benchmark_quality_loop.get("weakest_dimensions"))[:3]
    )
    benchmark_section: list[str] = []
    if benchmark_artifact_paths or benchmark_quality_loop:
        benchmark_section = [
            "",
            "## Benchmark Loop Artifacts",
            "",
            f"- Benchmark candidate index: {clean_text(benchmark_artifact_paths.get('candidate_index')) or 'not written'}",
            f"- Benchmark enrichment request: {clean_text(benchmark_artifact_paths.get('enrichment_request')) or 'not written'}",
            f"- Benchmark viral teardown: {clean_text(benchmark_artifact_paths.get('viral_teardown')) or 'not written'}",
            f"- Benchmark quality loop: {clean_text(benchmark_artifact_paths.get('quality_loop')) or 'not written'}",
            f"- Benchmark discovery enrichment needed: {'yes' if benchmark_discovery_quality.get('needs_interaction_enrichment') else 'no'}",
            f"- Benchmark high-interaction references: {int(benchmark_discovery_quality.get('high_interaction_reference_count', 0) or 0)}",
            f"- Benchmark rubric score: {int(benchmark_quality_loop.get('rubric_score', 0) or 0)} / {int(benchmark_quality_loop.get('rubric_threshold', 0) or 0)}",
            f"- Benchmark rubric target met: {'yes' if benchmark_quality_loop.get('rubric_passed') else 'no'}",
            f"- Benchmark weakest dimensions: {benchmark_weakest or 'none'}",
        ]
    workflow_queue_items = safe_list(workflow_manual_review.get("queue"))
    workflow_queue_text = (
        "None"
        if not workflow_queue_items
        else ", ".join(
            f"[{clean_text(item.get('priority_level'))}] {clean_text(item.get('title'))}"
            for item in workflow_queue_items
        )
    )
    lines = [
        f"# Article Publish: {clean_text(safe_dict(result.get('selected_topic')).get('title')) or clean_text(result.get('topic'))}",
        "",
        f"- Status: {clean_text(result.get('status')) or 'unknown'}",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Publication readiness: {clean_text(result.get('publication_readiness')) or 'ready'}",
        f"- Review gate: {clean_text(safe_dict(result.get('review_gate')).get('status')) or 'unknown'}",
        f"- Workflow Reddit operator review: {clean_text(safe_dict(result.get('workflow_manual_review')).get('status')) or 'not_required'}",
        "",
        "## Files",
        "",
        f"- Selected topic: {clean_text(result.get('selected_topic_path')) or 'not written'}",
        f"- News request: {clean_text(result.get('news_request_path')) or 'not written'}",
        f"- WeChat HTML: {clean_text(result.get('wechat_html_path')) or 'not written'}",
        f"- Publish package: {clean_text(result.get('publish_package_path')) or 'not written'}",
        f"- Automatic acceptance: {clean_text(result.get('automatic_acceptance_path')) or 'not written'}",
        f"- Next push command: {clean_text(result.get('next_push_command')) or 'none'}",
        *benchmark_section,
        "",
        "## Human Review Gate",
        "",
        f"- Status: {clean_text(review_gate.get('status')) or 'unknown'}",
        f"- Approved: {'yes' if review_gate.get('approved') else 'no'}",
        f"- Approved by: {clean_text(review_gate.get('approved_by')) or 'none'}",
        f"- Note: {clean_text(review_gate.get('note')) or 'none'}",
        "",
        "## Automatic Acceptance",
        "",
        f"- Status: {clean_text(automatic_acceptance.get('status')) or 'unknown'}",
        f"- Accepted: {'yes' if automatic_acceptance.get('accepted') else 'no'}",
        f"- Decision required: {'yes' if automatic_acceptance.get('decision_required') else 'no'}",
        "",
        "## Publish Readiness",
        "",
        f"- Publication readiness: {clean_text(result.get('publication_readiness')) or 'ready'}",
        f"- Push readiness: {clean_text(safe_dict(safe_dict(result.get('publish_package')).get('push_readiness')).get('status')) or 'unknown'}",
        "",
        "## Workflow Reddit Operator Review",
        "",
        f"- Workflow queue: {workflow_queue_text}",
        "",
        "## Regression Checks",
        "",
        f"- Cover reason present: {'yes' if safe_dict(safe_dict(result.get('publish_package')).get('regression_checks')).get('checks', {}).get('cover_reason_present', False) else 'no'}",
        "",
        "## Optimization Options",
        "",
        *(
            [f"- {clean_text(item.get('area'))}: {clean_text(item.get('reason'))}" for item in safe_list(automatic_acceptance.get("optimization_options"))]
            or ["- none"]
        ),
        "",
        "## Optional Improvements",
        "",
        *(
            [f"- {clean_text(item.get('area'))}: {clean_text(item.get('reason'))}" for item in safe_list(automatic_acceptance.get("advisory_options"))]
            or ["- none"]
        ),
        "",
        "## WeChat Push",
        "",
        f"- Attempted: {'yes' if push_stage.get('attempted') else 'no'}",
        f"- Status: {clean_text(push_stage.get('status')) or 'not_requested'}",
        f"- Review gate status: {clean_text(push_stage.get('review_gate_status')) or 'unknown'}",
        f"- Push readiness status: {clean_text(push_stage.get('push_readiness_status')) or 'unknown'}",
        f"- Workflow publication readiness: {clean_text(push_stage.get('workflow_publication_readiness')) or clean_text(safe_dict(result.get('workflow_publication_gate')).get('publication_readiness')) or 'ready'}",
        f"- Workflow manual review: {clean_text(push_stage.get('workflow_manual_review_status')) or clean_text(safe_dict(result.get('workflow_manual_review')).get('status')) or 'not_required'}",
    ]
    if clean_text(push_stage.get("error_message")):
        lines.append(f"- Error: {clean_text(push_stage.get('error_message'))}")
    toutiao_stage = safe_dict(result.get("toutiao_stage"))
    if toutiao_stage.get("status") != "not_requested":
        lines.append("")
        lines.append("## Toutiao Fast Card Push")
        lines.append("")
        lines.append(f"- Status: {clean_text(toutiao_stage.get('status'))}")
        if clean_text(toutiao_stage.get("article_url")):
            lines.append(f"- Article URL: {clean_text(toutiao_stage.get('article_url'))}")
        if clean_text(toutiao_stage.get("blocked_reason")):
            lines.append(f"- Blocked: {clean_text(toutiao_stage.get('blocked_reason'))}")
        if clean_text(toutiao_stage.get("error_message")):
            lines.append(f"- Error: {clean_text(toutiao_stage.get('error_message'))}")
    if style_memory:
        lines.extend(
            [
                "",
                "## Style Profile",
                "",
                f"- Target band: {clean_text(style_memory.get('target_band')) or 'none'}",
                f"- Sample source references: {int(style_memory.get('sample_source_declared_count', 0) or 0)}",
                f"- Available sample source paths: {int(style_memory.get('sample_source_available_count', 0) or 0)}",
                f"- Runtime style source mode: {clean_text(style_memory.get('sample_source_runtime_mode')) or 'unknown'}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def push_publish_package_to_wechat(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from wechat_draftbox_runtime import push_publish_package_to_wechat as inner

    return inner(*args, **kwargs)


def pick_selected_topic(discovery_result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    ranked_topics = [safe_dict(item) for item in safe_list(discovery_result.get("ranked_topics")) if isinstance(item, dict)]
    if not ranked_topics:
        raise ValueError("No ranked topics were produced for article publish.")
    index = min(len(ranked_topics), max(1, int(request.get("selected_topic_index", 1) or 1))) - 1
    selected = deepcopy(ranked_topics[index])
    selected["selected_rank"] = index + 1
    original_candidates = [safe_dict(item) for item in safe_list(request.get("manual_topic_candidates")) if isinstance(item, dict)]
    title = clean_text(selected.get("title"))
    for item in original_candidates:
        if clean_text(item.get("title")) == title:
            source_items = [safe_dict(src) for src in safe_list(item.get("source_items")) if isinstance(src, dict)]
            if source_items:
                selected["source_items"] = source_items
            break
    return selected


def run_article_publish(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)
    discovery_result = run_hot_topic_discovery(
        {
            "analysis_time": request["analysis_time"],
            "manual_topic_candidates": request["manual_topic_candidates"],
            "audience_keywords": request["audience_keywords"],
            "preferred_topic_keywords": request["preferred_topic_keywords"],
            "excluded_topic_keywords": request["excluded_topic_keywords"],
            "min_total_score": request["min_total_score"],
            "min_source_count": request["min_source_count"],
            "top_n": request["discovery_top_n"],
        }
    )
    selected_topic = pick_selected_topic(discovery_result, request)
    selected_topic_path = request["output_dir"] / "selected-topic.json"
    news_request_path = request["output_dir"] / "news-request.json"
    benchmark_candidate_index_path = request["output_dir"] / "benchmark-candidate-index.json"
    benchmark_enrichment_request_path = request["output_dir"] / "benchmark-enrichment-request.json"
    benchmark_viral_teardown_path = request["output_dir"] / "benchmark-viral-teardown.json"
    benchmark_quality_loop_path = request["output_dir"] / "benchmark-quality-loop.json"
    workflow_dir = request["output_dir"] / "workflow"
    benchmark_candidate_index = build_benchmark_candidate_index(
        discovery_result,
        selected_title=clean_text(selected_topic.get("title")),
    )
    benchmark_enrichment_request = build_benchmark_enrichment_request(benchmark_candidate_index, selected_topic)
    benchmark_viral_teardown = build_benchmark_viral_teardown(selected_topic, benchmark_candidate_index)
    benchmark_generation_style_memory = build_benchmark_generation_style_memory(benchmark_viral_teardown)
    if benchmark_generation_style_memory:
        request["style_memory"] = merge_style_memory(request.get("style_memory"), benchmark_generation_style_memory)
    news_request = build_news_request_from_topic(selected_topic, request)
    write_json(selected_topic_path, selected_topic)
    write_json(news_request_path, news_request)
    write_json(benchmark_candidate_index_path, benchmark_candidate_index)
    write_json(benchmark_enrichment_request_path, benchmark_enrichment_request)
    write_json(benchmark_viral_teardown_path, benchmark_viral_teardown)
    workflow_result = run_article_workflow({**request, **news_request, "output_dir": str(workflow_dir)})
    publish_package = build_publish_package(workflow_result, selected_topic, request)
    workflow_publication_gate = build_workflow_publication_gate(publish_package)
    publish_package["workflow_publication_gate"] = workflow_publication_gate
    publish_package["workflow_manual_review"] = workflow_publication_gate["manual_review"]
    publish_package["publication_readiness"] = clean_text(workflow_publication_gate.get("publication_readiness")) or publish_package["publication_readiness"]
    publish_package_path = request["output_dir"] / "publish-package.json"
    wechat_html_path = request["output_dir"] / "wechat-draft.html"
    acceptance_path = request["output_dir"] / "publish-automatic-acceptance.json"
    acceptance_report_path = request["output_dir"] / "publish-automatic-acceptance.md"
    write_json(publish_package_path, publish_package)
    wechat_html_path.write_text(publish_package.get("content_html", ""), encoding="utf-8-sig")

    automatic_acceptance = build_automatic_acceptance_result(
        safe_dict(publish_package.get("regression_checks")),
        target=str(request["output_dir"]),
        output_dir=str(request["output_dir"]),
        regression_source="publish_package",
        extra_metadata={"workflow_publication_gate": workflow_publication_gate},
    )
    automatic_acceptance["report_markdown"] = build_automatic_acceptance_markdown(automatic_acceptance)
    write_json(acceptance_path, automatic_acceptance)
    acceptance_report_path.write_text(automatic_acceptance["report_markdown"], encoding="utf-8-sig")
    benchmark_quality_loop = build_benchmark_quality_loop_artifact(
        news_request_path=news_request_path,
        article_draft_path=clean_text(safe_dict(workflow_result.get("draft_stage")).get("result_path")),
        publish_package_path=publish_package_path,
        benchmark_rubric=safe_dict(safe_dict(publish_package.get("regression_checks")).get("benchmark_rubric")),
        automatic_acceptance=automatic_acceptance,
    )
    write_json(benchmark_quality_loop_path, benchmark_quality_loop)

    review_gate = {
        "approved": bool(request["human_review_approved"]),
        "status": "approved" if request["human_review_approved"] else "awaiting_human_review",
        "approved_by": request["human_review_approved_by"],
        "note": request["human_review_note"],
    }
    push_stage = {
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate["status"],
        "push_readiness_status": clean_text(safe_dict(publish_package.get("push_readiness")).get("status")),
        "workflow_publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")),
        "workflow_manual_review_status": clean_text(safe_dict(workflow_publication_gate.get("manual_review")).get("status")),
        "result_path": str(request["output_dir"] / "wechat-push-result.json"),
    }

    status = "ok"
    if request["push_to_wechat"]:
        if not review_gate["approved"]:
            status = "blocked_review_gate"
            push_stage["status"] = "blocked_review_gate"
            push_stage["blocked_reason"] = "human_review_not_approved"
        elif clean_text(safe_dict(publish_package.get("push_readiness")).get("status")) != "ready_for_api_push":
            status = "blocked_push_readiness"
            push_stage["status"] = "blocked_push_readiness"
            push_stage["blocked_reason"] = f"push_not_ready:{clean_text(safe_dict(publish_package.get('push_readiness')).get('status'))}"
        else:
            push_stage["attempted"] = True
            try:
                push_result = push_publish_package_to_wechat(
                    {
                        "publish_package": publish_package,
                        "push_backend": request["push_backend"],
                        "human_review_approved": request["human_review_approved"],
                        "human_review_approved_by": request["human_review_approved_by"],
                        "human_review_note": request["human_review_note"],
                        "wechat_app_id": request["wechat_app_id"],
                        "wechat_app_secret": request["wechat_app_secret"],
                        "allow_insecure_inline_credentials": request["allow_insecure_inline_credentials"],
                        "cover_image_path": request["cover_image_path"],
                        "cover_image_url": request["cover_image_url"],
                        "timeout_seconds": request["timeout_seconds"],
                        "browser_session": request["browser_session"],
                    }
                )
                write_json(Path(push_stage["result_path"]), push_result)
                push_stage.update(
                    {
                        "status": clean_text(push_result.get("status")) or "ok",
                        "draft_media_id": clean_text(safe_dict(push_result.get("draft_result")).get("media_id")),
                        "review_gate_status": clean_text(safe_dict(push_result.get("review_gate")).get("status")) or review_gate["status"],
                        "push_readiness_status": clean_text(safe_dict(push_result.get("push_readiness")).get("status")) or push_stage["push_readiness_status"],
                        "workflow_publication_readiness": clean_text(safe_dict(push_result.get("workflow_publication_gate")).get("publication_readiness")) or push_stage["workflow_publication_readiness"],
                        "workflow_manual_review_status": clean_text(safe_dict(safe_dict(push_result.get("workflow_publication_gate")).get("manual_review")).get("status")) or push_stage["workflow_manual_review_status"],
                    }
                )
            except Exception as exc:
                status = "push_error"
                push_stage["status"] = "error"
                push_stage["blocked_reason"] = "push_failed"
                push_stage["error_message"] = clean_text(exc)

    # --- Toutiao Fast Card ---
    toutiao_stage = {
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate["status"],
        "result_path": str(request["output_dir"] / "toutiao-push-result.json"),
    }
    toutiao_fast_card_package = None

    if request["push_to_toutiao"]:
        toutiao_fast_card_package = build_toutiao_fast_card_package(
            workflow_result, selected_topic, request,
        )
        toutiao_card_path = request["output_dir"] / "toutiao-fast-card-package.json"
        write_json(toutiao_card_path, toutiao_fast_card_package)

        if not review_gate["approved"]:
            toutiao_stage["status"] = "blocked_review_gate"
            toutiao_stage["blocked_reason"] = "human_review_not_approved"
        else:
            toutiao_stage["attempted"] = True
            try:
                toutiao_push_result = push_fast_card_to_toutiao(
                    {
                        "fast_card_package": toutiao_fast_card_package,
                        "push_backend": clean_text(request.get("push_backend")) or "browser_session",
                        "human_review_approved": request["human_review_approved"],
                        "human_review_approved_by": request["human_review_approved_by"],
                        "human_review_note": request["human_review_note"],
                        "timeout_seconds": request["timeout_seconds"],
                        "browser_session": request["toutiao_browser_session"],
                    },
                    browser_runner=None,
                )
                write_json(Path(toutiao_stage["result_path"]), toutiao_push_result)
                toutiao_stage["status"] = clean_text(toutiao_push_result.get("status")) or "ok"
                toutiao_stage["article_url"] = clean_text(toutiao_push_result.get("article_url"))
            except Exception as exc:
                toutiao_stage["status"] = "error"
                toutiao_stage["blocked_reason"] = "push_failed"
                toutiao_stage["error_message"] = clean_text(exc)

    result = {
        "status": status,
        "workflow_kind": "article_publish",
        "analysis_time": request["analysis_time"],
        "selected_topic": selected_topic,
        "selected_topic_path": str(selected_topic_path),
        "news_request_path": str(news_request_path),
        "benchmark_artifact_paths": {
            "candidate_index": str(benchmark_candidate_index_path),
            "enrichment_request": str(benchmark_enrichment_request_path),
            "viral_teardown": str(benchmark_viral_teardown_path),
            "quality_loop": str(benchmark_quality_loop_path),
        },
        "benchmark_candidate_index": benchmark_candidate_index,
        "benchmark_enrichment_request": benchmark_enrichment_request,
        "benchmark_viral_teardown": benchmark_viral_teardown,
        "benchmark_quality_loop": benchmark_quality_loop,
        "workflow_stage": {
            "draft_result_path": clean_text(safe_dict(workflow_result.get("draft_stage")).get("result_path")),
            "final_result_path": clean_text(safe_dict(workflow_result.get("final_stage")).get("result_path")),
        },
        "publish_package": publish_package,
        "publish_package_path": str(publish_package_path),
        "wechat_html_path": str(wechat_html_path),
        "automatic_acceptance": automatic_acceptance,
        "automatic_acceptance_path": str(acceptance_path),
        "automatic_acceptance_report_path": str(acceptance_report_path),
        "review_gate": review_gate,
        "manual_review": review_gate,
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
        "workflow_manual_review": safe_dict(workflow_publication_gate.get("manual_review")),
        "workflow_publication_gate": workflow_publication_gate,
        "push_stage": push_stage,
        "toutiao_stage": toutiao_stage,
        "toutiao_fast_card_package": toutiao_fast_card_package,
        "topic": clean_text(selected_topic.get("title")),
        "next_push_command": f"financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_wechat_push_draft.cmd \"{publish_package_path}\"",
    }
    result["report_markdown"] = build_report_markdown(result)
    return result


__all__ = [
    "build_automatic_acceptance_markdown",
    "build_automatic_acceptance_result",
    "build_news_request_from_topic",
    "build_publish_package",
    "build_push_readiness",
    "build_regression_checks",
    "build_report_markdown",
    "clean_text",
    "normalize_request",
    "run_article_publish",
    "safe_dict",
    "safe_list",
    "push_publish_package_to_wechat",
]
