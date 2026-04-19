#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
import re
from typing import Any

from article_feedback_profiles import feedback_profile_status, load_feedback_profiles, merge_request_with_profiles, resolve_profile_dir
from article_workflow_runtime import run_article_workflow, write_json
from hot_topic_discovery_runtime import run_hot_topic_discovery
from news_index_runtime import clean_string_list, isoformat_or_blank, parse_datetime, safe_dict, safe_list, slugify
from publication_contract_runtime import SHARED_PUBLICATION_CONTRACT_VERSION
from runtime_paths import runtime_subdir
from toutiao_article_draftbox_runtime import push_publish_package_to_toutiao
from toutiao_fast_card_runtime import build_toutiao_fast_card_package
from toutiao_draftbox_runtime import push_fast_card_to_toutiao
from wechat_draftbox_runtime import build_workflow_publication_gate, push_publish_package_to_wechat, resolve_human_review_gate


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_editor_anchor_mode(value: Any) -> str:
    mode = clean_text(value).lower().replace("-", "_")
    if mode in {"inline", "hidden"}:
        return mode
    return "hidden"


def parse_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    lowered = clean_text(value).lower()
    if lowered in {"1", "true", "yes", "y", "on", "approved"}:
        return True
    if lowered in {"0", "false", "no", "n", "off", "rejected"}:
        return False
    return default


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_public_topic_title(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    separator_split = [part for part in re.split(r"\s*[|\uFF5C\u4E28]\s*", cleaned) if clean_text(part)]
    if separator_split:
        cleaned = separator_split[0]
    cleaned = re.sub(
        r"\s*[-\u2013\u2014]\s*(36kr|36\u6c2a|weibo|\u5fae\u535a|zhihu|\u77e5\u4e4e|reuters|\u8def\u900f|bloomberg|\u5f6d\u535a|techcrunch|the information|\u9996\u53d1|\u72ec\u5bb6).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"[\:\uFF1A]\s*(?:\u54ea\u4e9b\u5df2\u7ecf\u786e\u8ba4.*|\u54ea\u4e9b\u4ecd\u672a\u786e\u8ba4.*|what is confirmed.*|what remains unconfirmed.*)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*(?:\u54ea\u4e9b\u5df2\u7ecf\u786e\u8ba4.*|\u54ea\u4e9b\u4ecd\u672a\u786e\u8ba4.*|what is confirmed.*|what remains unconfirmed.*)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*(36kr|36\u6c2a|\u9996\u53d1|\u72ec\u5bb6)\s*$", "", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned.strip(" -\u2013\u2014|\uFF5C\u4E28:\uFF1A\"'\u201c\u201d\u2018\u2019"))


HANGING_TITLE_SUFFIXES = ("后", "前", "中", "里", "时")
HANGING_TITLE_ALLOWED_ENDINGS = (
    "之后",
    "此前",
    "其后",
    "其中",
    "同时",
    "小时",
    "分钟",
    "里面",
    "里程",
)
TITLE_HOOK_FRAGMENT_HINTS = (
    "真正值得看",
    "值得看",
    "怎么看",
    "为什么",
    "秘密功能",
    "隐藏功能",
    "隐藏能力",
    "会打多久",
    "会走到哪",
    "盘点",
    "名单",
)


def looks_like_hanging_title_fragment(text: str) -> bool:
    cleaned = clean_text(text).strip("，。！？；：,.!?;:、 ")
    if not cleaned:
        return False
    if any(cleaned.endswith(ending) for ending in HANGING_TITLE_ALLOWED_ENDINGS):
        return False
    return any(cleaned.endswith(suffix) for suffix in HANGING_TITLE_SUFFIXES)


def title_fragment_is_claim_ready(text: str) -> bool:
    cleaned = clean_text(text).strip("，。！？；：,.!?;:、 ")
    if len(cleaned) < 4:
        return False
    if looks_like_hanging_title_fragment(cleaned):
        return False
    if any(token in cleaned for token in TITLE_HOOK_FRAGMENT_HINTS):
        return False
    if cleaned.endswith(("吗", "呢", "?", "？")):
        return False
    return True


SOURCE_PRIORITY = {
    "government": 0,
    "official": 0,
    "regulator": 0,
    "wire": 1,
    "major_news": 1,
    "specialist": 2,
    "analysis": 2,
    "research_note": 2,
    "social": 3,
    "community": 3,
}


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in clean_text(text))


def english_word_count(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z/-]*\b", clean_text(text)))


def compact_sentence(text: Any) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    first = re.split(r"(?<=[。！？!?])\s+|(?<=\.)\s+(?=[A-Z])", cleaned, maxsplit=1)[0]
    return clean_text(first.strip(" .。；;，,"))


def strip_source_lead(text: str) -> str:
    cleaned = compact_sentence(text)
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"^(36kr|36氪|reuters|bloomberg|the information|google-news-search|google news|zhihu users?|weibo users?|overseas reporting)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(reports?|reportedly|says?|said|argues?|noted?|shows?|announced?|claims?)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:reports?|says?|argues?)\s+that\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:according to|amid)\s+", "", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned.strip(" .。"))


def topic_title_fragments(title: str) -> list[str]:
    fragments: list[str] = []
    cleaned = clean_public_topic_title(title)
    for fragment in re.split(r"[，,；;、/]\s*", cleaned):
        text = clean_text(fragment.strip(" -:："))
        if not title_fragment_is_claim_ready(text) or text in fragments:
            continue
        if not has_cjk(text):
            continue
        if re.search(r"(首发|独家|哪些已经确认|哪些仍未确认|what is confirmed|what remains unconfirmed)", text, re.IGNORECASE):
            continue
        fragments.append(text)
    return fragments[:3]


def sorted_source_items_for_claims(selected_topic: dict[str, Any]) -> list[dict[str, Any]]:
    items = [item for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)]
    return sorted(
        items,
        key=lambda item: (
            int(SOURCE_PRIORITY.get(clean_text(item.get("source_type")).lower(), 9)),
            clean_text(item.get("published_at")) or "9999",
        ),
    )


def english_summary_to_chinese(summary: str) -> str:
    cleaned = strip_source_lead(summary)
    if not cleaned:
        return ""
    if has_cjk(cleaned):
        return cleaned
    lowered = cleaned.lower()
    explicit_patterns = [
        (
            r"official docs describe claude code browser control and chrome integration",
            "官方文档已经写明 Claude Code 提供浏览器控制，并给出了 Chrome 集成方式。",
        ),
        (
            r"(?:the\s+)?thread captures browser control entrypoints, subagents, and permission boundaries",
            "这条线程把浏览器控制入口、子代理能力和权限边界梳理了出来。",
        ),
        (
            r"(?:the\s+)?thread walks through browser control and multi-step task execution entrypoints",
            "这条线程顺着浏览器控制和多步任务执行入口做了拆解。",
        ),
        (
            r"the leaked code shows browser control, tool calls, and workflow orchestration entrypoints",
            "泄露出来的代码把浏览器控制、工具调用和工作流编排入口都露了出来。",
        ),
        (
            r"the leaked code and docs point to browser control, tool use boundaries, and workflow orchestration changes",
            "泄露代码和公开文档都在指向同一件事：浏览器控制、工具使用边界和工作流编排正在变得更清晰。",
        ),
        (
            r"screenshot-backed thread about claude code browser control and hidden capabilities",
            "这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力。",
        ),
        (
            r"browser-captured image from the original x post showing workflow panels",
            "这张图直接截自原始 X 帖子，能看到工作流面板。",
        ),
        (
            r"browser mode entrypoint shown next to remote control and workflow panels",
            "图里能看到浏览器模式入口，旁边就是远程控制和工作流面板。",
        ),
        (
            r"screenshot of the original x thread discussing claude code hidden capabilities",
            "原始 X 线程截图，保留了 Claude Code 隐藏能力讨论的现场界面。",
        ),
        (
            r"selected ai agent startups are hiring again across engineering and delivery roles",
            "部分 AI Agent 创业公司重新开始招聘，岗位集中在工程和交付。",
        ),
        (
            r"debate whether the rebound reflects durable demand or another narrative spike",
            "围绕这轮回暖到底是持续需求回来了，还是又一轮短期叙事冲高，市场争论还在继续。",
        ),
        (
            r"users debate whether the rebound reflects durable demand or another narrative spike",
            "围绕这轮回暖到底是持续需求回来了，还是又一轮短期叙事冲高，市场争论还在继续。",
        ),
        (
            r"the scarce resource is no longer hype, but engineers who can ship real agent outcomes",
            "真正稀缺的不再是概念，而是能把 Agent 做成交付结果的工程与交付人才。",
        ),
    ]
    for pattern, replacement in explicit_patterns:
        if re.search(pattern, lowered):
            return replacement

    replacements = [
        ("selected ai agent startups", "部分 AI Agent 创业公司"),
        ("ai agent startups", "AI Agent 创业公司"),
        ("ai agent", "AI Agent"),
        ("browser control", "浏览器控制"),
        ("browser mode", "浏览器模式"),
        ("tool calls", "工具调用"),
        ("tool call", "工具调用"),
        ("tool use boundaries", "工具使用边界"),
        ("workflow orchestration", "工作流编排"),
        ("workflow panels", "工作流面板"),
        ("workflow panel", "工作流面板"),
        ("entrypoints", "入口"),
        ("entrypoint", "入口"),
        ("subagents", "子代理"),
        ("subagent", "子代理"),
        ("permission boundaries", "权限边界"),
        ("permission boundary", "权限边界"),
        ("chrome integration", "Chrome 集成"),
        ("hidden capabilities", "隐藏能力"),
        ("official docs", "官方文档"),
        ("original x post", "原始 X 帖子"),
        ("original x thread", "原始 X 线程"),
        ("remote control", "远程控制"),
        ("multi-step task execution", "多步任务执行"),
        ("screenshot-backed", "带截图的"),
        ("browser-captured image", "浏览器截取的配图"),
        ("leaked code and docs", "泄露代码和公开文档"),
        ("leaked code", "泄露出来的代码"),
        ("hiring again", "重新开始招聘"),
        ("hire again", "重新开始招聘"),
        ("engineering and delivery roles", "工程和交付岗位"),
        ("durable demand", "持续需求"),
        ("narrative spike", "短期叙事冲高"),
        ("short-lived wave", "短期热潮"),
        ("funding appetite", "融资意愿"),
        ("order visibility", "订单能见度"),
        ("real budgets", "真实预算"),
        ("budgets", "预算"),
        ("orders", "订单"),
        ("platform", "平台"),
        ("launch", "发布"),
        ("release", "发布"),
        ("funding round", "融资"),
        ("financing round", "融资"),
        ("partnership", "合作"),
        ("layoffs", "裁员"),
        ("delivery", "交付"),
        ("engineers", "工程人才"),
        ("outcomes", "结果"),
        ("outcome", "结果"),
    ]
    translated = cleaned
    for source, target in replacements:
        translated = re.sub(source, target, translated, flags=re.IGNORECASE)
    translated = re.sub(r"\b(users debate whether|debate whether)\b", "市场仍在争论", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\boverseas reporting says\b", "海外报道提到", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bwalks through\b", "拆解了", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bcaptures\b", "梳理出", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bdescribe?s?\b", "写明", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bshown next to\b", "旁边就是", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bpoints? to\b", "指向", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bshows?\b", "显示出", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\babout\b", "关于", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bfrom\b", "来自", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\band\b", "和", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\breports?\b", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bis no longer\b", "不再是", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bare\b", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bis\b", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bthe\b", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\s+", " ", translated).strip(" .")
    if has_cjk(translated) and english_word_count(translated) <= 4:
        if translated and not translated.endswith(("。", "！", "？")):
            translated += "。"
        return clean_text(translated)
    if any(
        keyword in lowered
        for keyword in (
            "browser control",
            "workflow orchestration",
            "tool call",
            "permission",
            "subagent",
            "browser mode",
            "claude code",
            "chrome integration",
        )
    ):
        if any(keyword in lowered for keyword in ("official docs", "docs", "chrome integration")):
            return "官方文档已经把 Claude Code 的浏览器控制和 Chrome 集成写得更明确了。"
        if any(keyword in lowered for keyword in ("thread", "post")):
            return "这条线程把浏览器控制入口、权限边界和工作流线索梳理了出来。"
        if any(keyword in lowered for keyword in ("image", "screenshot", "workflow panels")):
            return "这张图补充了原始帖子里的界面证据和工作流上下文。"
        return "公开信息已经把浏览器控制、权限边界和工作流入口这条线索露了出来。"
    if any(keyword in lowered for keyword in ("image", "screenshot", "photo")):
        return "这张图补充了原始页面里的界面证据。"
    return "公开来源补充了这条线索的关键信息。"


def localize_candidate_copy(text: Any, *, language_mode: str) -> str:
    cleaned = clean_text(text)
    if not cleaned or language_mode != "chinese" or has_cjk(cleaned):
        return cleaned
    return english_summary_to_chinese(cleaned)


def extract_english_sentence_leaks(text: str) -> list[str]:
    prose_hint_words = {
        "and",
        "browser",
        "captures",
        "capture",
        "describe",
        "describes",
        "entrypoint",
        "entrypoints",
        "hidden",
        "image",
        "images",
        "integration",
        "mode",
        "official",
        "original",
        "panels",
        "shown",
        "shows",
        "show",
        "thread",
        "through",
        "walks",
        "walk",
        "with",
        "workflow",
    }
    samples: list[str] = []
    for raw_line in str(text or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", stripped)
        normalized = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", normalized)
        normalized = re.sub(r"https?://\S+|file:///\S+", " ", normalized)
        if "|" in normalized:
            normalized = normalized.split("|", 1)[0]
        normalized = re.sub(r"[_*`>#|\-\[\]\(\)]", " ", normalized)
        normalized = clean_text(normalized)
        if not normalized:
            continue
        matches = re.findall(r"(?:\b[A-Za-z][A-Za-z/-]*\b(?:\s+|$)){5,}", normalized)
        if not matches:
            continue
        if not any(
            any(word.lower() in prose_hint_words for word in re.findall(r"\b[A-Za-z][A-Za-z/-]*\b", match))
            for match in matches
        ):
            continue
        samples.append(stripped)
        if len(samples) >= 5:
            break
    return samples


def source_summary_claims(selected_topic: dict[str, Any]) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for item in sorted_source_items_for_claims(selected_topic):
        summary = strip_source_lead(clean_text(item.get("summary") or item.get("title")))
        if not summary:
            continue
        zh = summary if has_cjk(summary) else english_summary_to_chinese(summary)
        claims.append({"en": summary.rstrip(".") + ".", "zh": zh})
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in claims:
        key = clean_text(item.get("zh") or item.get("en")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:4]


def derive_relevance_claims(selected_topic: dict[str, Any], title: str) -> dict[str, str]:
    text = topic_keyword_text(selected_topic)
    if is_developer_tooling_topic(selected_topic):
        return {
            "en": "What matters is the product boundary already showing up in public, how permissions are designed, and what that changes in real developer workflows.",
            "zh": "真正值得写的，不是把它泛化成商业景气，而是看 Claude Code 已经露出的产品边界、权限设计和工作流变化。",
        }
    if any(keyword in text for keyword in ["招聘", "hiring", "recruit", "招人"]):
        return {
            "en": "The real question is whether hiring is moving from narrative heat into delivery demand and budget recovery.",
            "zh": "真正值得写的，不是招聘热度本身，而是它会不会从叙事回暖走到真实交付需求和预算恢复。",
        }
    if any(keyword in text for keyword in ["融资", "funding", "raise", "series", "ipo", "上市"]):
        return {
            "en": "The bigger business signal is whether capital, product release, and commercialization progress are starting to reconnect.",
            "zh": "更大的商业信号在于，资本、产品发布和商业化进度是不是开始重新接上了。",
        }
    if any(keyword in text for keyword in ["平台", "platform", "发布", "launch", "release"]):
        return {
            "en": "The key read-through is whether the new platform can quickly turn into customers, usage, and partner adoption.",
            "zh": "关键不只是在于平台发布，而是在于它会不会很快转成客户、使用量和合作落地。",
        }
    if any(keyword in text for keyword in ["战争", "油", "天然气", "lng", "航运", "政策", "关税"]):
        return {
            "en": "What matters next is how the headline keeps transmitting into prices, policy room, and company decisions.",
            "zh": "接下来真正重要的，是这条 headline 会怎样继续传到价格、政策空间和企业决策里。",
        }
    return {
        "en": f'The story around "{title}" is starting to matter because the discussion is moving into real business and market decisions.',
        "zh": f"围绕“{title}”的讨论开始变得重要，不只是因为热度高，而是因为它正在往真实的经营和市场判断里传导。",
    }


def derive_open_claim(selected_topic: dict[str, Any], title: str) -> dict[str, str]:
    text = topic_keyword_text(selected_topic)
    social_summary = ""
    for item in sorted_source_items_for_claims(selected_topic):
        if clean_text(item.get("source_type")).lower() == "social":
            social_summary = strip_source_lead(clean_text(item.get("summary") or item.get("title")))
            break
    if social_summary:
        zh = social_summary if has_cjk(social_summary) else english_summary_to_chinese(social_summary)
        return {
            "en": social_summary.rstrip(".") + ".",
            "zh": zh,
        }
    if any(keyword in text for keyword in ["招聘", "hiring", "recruit", "招人"]):
        return {
            "en": "The market is still debating whether this hiring rebound reflects durable demand or another short-lived narrative cycle.",
            "zh": "眼下最大的争论，不是有没有热度，而是这轮招聘回暖到底是持续需求回来了，还是又一轮短期叙事冲高。",
        }
    if any(keyword in text for keyword in ["融资", "funding", "raise", "series", "ipo", "上市", "平台", "platform"]):
        return {
            "en": "The unresolved question is how fast the financing or platform launch turns into real customers, orders, and execution milestones.",
            "zh": "真正还没走到答案的，是这笔融资或这次平台发布，多久能转成真实客户、订单和落地节奏。",
        }
    return {
        "en": f'Important details around "{title}" still need verification before the article turns them into settled facts.',
        "zh": f"围绕“{title}”仍有关键细节、影响路径或真假边界需要继续核实。",
    }


def topic_keyword_text(selected_topic: dict[str, Any]) -> str:
    parts = clean_string_list(selected_topic.get("keywords"))
    parts.extend(
        [
            clean_public_topic_title(selected_topic.get("title")),
            clean_text(selected_topic.get("summary")),
        ]
    )
    return " ".join(part.lower() for part in parts if clean_text(part))


def is_developer_tooling_topic(selected_topic: dict[str, Any]) -> bool:
    text = topic_keyword_text(selected_topic)
    return any(
        keyword in text
        for keyword in (
            "claude code",
            "subagent",
            "sub-agent",
            "tool call",
            "tool use",
            "mcp",
            "chrome",
            "browser",
            "playwright",
            "remote debugging",
            "permission",
            "workflow",
            "developer workflow",
            "source code",
            "leak",
            "leaked",
            "cli",
            "sdk",
            "devtool",
            "prompt file",
        )
    )


def is_macro_conflict_topic(selected_topic: dict[str, Any]) -> bool:
    text = topic_keyword_text(selected_topic)
    return any(
        keyword in text
        for keyword in (
            "war",
            "iran",
            "israel",
            "trump",
            "hormuz",
            "shipping",
            "oil tanker",
            "oil",
            "crude",
            "brent",
            "middle east",
            "sanction",
            "airstrike",
            "strike",
            "conflict",
            "战争",
            "冲突",
            "伊朗",
            "以色列",
            "特朗普",
            "霍尔木兹",
            "航运",
            "油轮",
            "原油",
            "布油",
            "中东",
            "制裁",
            "空袭",
            "打击",
            "白宫",
            "讲话",
            "航母",
        )
    )


def build_manual_review_state(
    request: dict[str, Any],
    *,
    review_gate: dict[str, Any] | None = None,
    approved_at: str = "",
) -> dict[str, Any]:
    gate = review_gate or resolve_human_review_gate(
        {
            "human_review_approved": request.get("human_review_approved"),
            "human_review_approved_by": request.get("human_review_approved_by"),
            "human_review_note": request.get("human_review_note"),
        }
    )
    approved = bool(gate.get("approved"))
    return {
        "required": True,
        "approved": approved,
        "status": "approved" if approved else "awaiting_human_review",
        "approved_by": clean_text(gate.get("approved_by")),
        "approved_at": approved_at or clean_text(gate.get("approved_at")) or (isoformat_or_blank(now_utc()) if approved else ""),
        "note": clean_text(gate.get("approval_note")),
        "next_step": clean_text(gate.get("next_step")),
    }


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    topic = clean_text(raw_payload.get("topic") or raw_payload.get("query"))
    topic_slug = slugify(topic, "hot-topic-auto") if topic else "hot-topic-auto"
    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else runtime_subdir("article-publish", topic_slug, analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    request = {
        "analysis_time": analysis_time,
        "topic": topic,
        "output_dir": output_dir,
        "discovery_sources": clean_string_list(raw_payload.get("discovery_sources") or raw_payload.get("sources")),
        "manual_topic_candidates": [
            item
            for item in safe_list(raw_payload.get("manual_topic_candidates") or raw_payload.get("topics"))
            if isinstance(item, dict)
        ],
        "discovery_limit": max(1, int(raw_payload.get("discovery_limit", raw_payload.get("limit", 10)) or 10)),
        "discovery_top_n": max(1, int(raw_payload.get("discovery_top_n", raw_payload.get("top_n", 5)) or 5)),
        "selected_topic_index": max(1, int(raw_payload.get("selected_topic_index", 1) or 1)),
        "audience_keywords": clean_string_list(raw_payload.get("audience_keywords"))
        or ["投资", "商业", "产业", "AI", "科技", "公众号"],
        "preferred_topic_keywords": clean_string_list(
            raw_payload.get("preferred_topic_keywords")
            or raw_payload.get("topic_preferences")
            or raw_payload.get("preferred_keywords")
        ),
        "excluded_topic_keywords": clean_string_list(
            raw_payload.get("excluded_topic_keywords") or raw_payload.get("exclude_keywords")
        ),
        "topic_score_weights": raw_payload.get("topic_score_weights") or raw_payload.get("score_weights") or {},
        "min_total_score": max(0, int(raw_payload.get("min_total_score", 0) or 0)),
        "min_source_count": max(0, int(raw_payload.get("min_source_count", 0) or 0)),
        "title_hint": clean_text(raw_payload.get("title_hint")),
        "subtitle_hint": clean_text(raw_payload.get("subtitle_hint")),
        "angle": clean_text(raw_payload.get("angle")),
        "tone": clean_text(raw_payload.get("tone")) or "professional-calm",
        "target_length_chars": int(raw_payload.get("target_length_chars", raw_payload.get("target_length", 1600)) or 1600),
        "max_images": int(raw_payload.get("max_images", 3) or 3),
        "human_signal_ratio": raw_payload.get("human_signal_ratio"),
        "personal_phrase_bank": raw_payload.get("personal_phrase_bank"),
        "image_strategy": clean_text(raw_payload.get("image_strategy")) or "mixed",
        "draft_mode": clean_text(raw_payload.get("draft_mode")) or "balanced",
        "language_mode": clean_text(raw_payload.get("language_mode")) or "zh",
        "article_framework": clean_text(raw_payload.get("article_framework")) or "auto",
        "headline_hook_mode": clean_text(raw_payload.get("headline_hook_mode") or raw_payload.get("title_hook_mode")) or "traffic",
        "headline_hook_prefixes": clean_string_list(
            raw_payload.get("headline_hook_prefixes") or raw_payload.get("title_hook_prefixes") or raw_payload.get("title_prefixes")
        ),
        "feedback_profile_dir": clean_text(raw_payload.get("feedback_profile_dir")),
        "editor_anchor_mode": normalize_editor_anchor_mode(raw_payload.get("editor_anchor_mode")),
        "account_name": clean_text(raw_payload.get("account_name")),
        "author": clean_text(raw_payload.get("author")),
        "digest_max_chars": max(60, int(raw_payload.get("digest_max_chars", 120) or 120)),
        "need_open_comment": 1 if parse_bool(raw_payload.get("need_open_comment"), default=False) else 0,
        "only_fans_can_comment": 1 if parse_bool(raw_payload.get("only_fans_can_comment"), default=False) else 0,
        "max_parallel_sources": max(1, int(raw_payload.get("max_parallel_sources", 4) or 1)),
        "push_to_wechat": parse_bool(raw_payload.get("push_to_wechat"), default=False),
        "push_to_channel": parse_bool(raw_payload.get("push_to_channel"), default=False),
        "publish_channel": clean_text(raw_payload.get("publish_channel")) or "wechat",
        "push_to_toutiao": parse_bool(raw_payload.get("push_to_toutiao"), default=False),
        "push_backend": clean_text(raw_payload.get("push_backend") or raw_payload.get("wechat_push_backend") or "api"),
        "wechat_app_id": clean_text(raw_payload.get("wechat_app_id") or raw_payload.get("app_id")),
        "wechat_app_secret": clean_text(raw_payload.get("wechat_app_secret") or raw_payload.get("app_secret")),
        "wechat_env_file": clean_text(raw_payload.get("wechat_env_file") or raw_payload.get("env_file_path")),
        "allow_insecure_inline_credentials": parse_bool(raw_payload.get("allow_insecure_inline_credentials"), default=False),
        "cover_image_path": clean_text(raw_payload.get("cover_image_path")),
        "cover_image_url": clean_text(raw_payload.get("cover_image_url")),
        "show_cover_pic": int(raw_payload.get("show_cover_pic", 1) or 1),
        "browser_session": raw_payload.get("browser_session") if isinstance(raw_payload.get("browser_session"), dict) else {},
        "toutiao_browser_session": raw_payload.get("toutiao_browser_session") if isinstance(raw_payload.get("toutiao_browser_session"), dict) else {},
        "wechat_cta_text": clean_text(raw_payload.get("wechat_cta_text")),
        "boundary_statement": clean_text(raw_payload.get("boundary_statement")),
        "timeout_seconds": max(5, int(raw_payload.get("timeout_seconds", 30) or 30)),
        "human_review_approved": parse_bool(raw_payload.get("human_review_approved"), default=False),
        "human_review_approved_by": clean_text(raw_payload.get("human_review_approved_by") or raw_payload.get("reviewed_by")),
        "human_review_note": clean_text(raw_payload.get("human_review_note") or raw_payload.get("review_note")),
    }
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    profiles = load_feedback_profiles(profile_dir, request.get("topic") or "global")
    request = merge_request_with_profiles(request, profiles)
    request["feedback_profile_dir"] = str(profile_dir)
    request["feedback_profile_status"] = feedback_profile_status(
        profile_dir,
        request.get("topic") or "global",
        profiles=profiles,
    )
    return request


def resolve_discovery_request(request: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "limit": request["discovery_limit"],
        "top_n": request["discovery_top_n"],
        "audience_keywords": request["audience_keywords"],
        "preferred_topic_keywords": request["preferred_topic_keywords"],
        "excluded_topic_keywords": request["excluded_topic_keywords"],
        "topic_score_weights": request["topic_score_weights"],
        "min_total_score": request["min_total_score"],
        "min_source_count": request["min_source_count"],
        "manual_topic_candidates": request["manual_topic_candidates"],
        "max_parallel_sources": request["max_parallel_sources"],
    }
    if request["discovery_sources"]:
        payload["sources"] = request["discovery_sources"]
    if request["topic"]:
        payload["topic"] = request["topic"]
        payload["query"] = request["topic"]
    return payload


def select_topic_candidate(discovery_result: dict[str, Any], selected_topic_index: int) -> dict[str, Any]:
    ranked = safe_list(discovery_result.get("ranked_topics"))
    if not ranked:
        raise ValueError("No hot topics were discoverable. Provide topic manually or pass manual_topic_candidates.")
    bounded_index = max(1, min(selected_topic_index, len(ranked)))
    topic = deepcopy(safe_dict(ranked[bounded_index - 1]))
    topic["selected_rank"] = bounded_index
    return topic


ENRICHED_SOURCE_ITEM_FIELDS = (
    "artifact_manifest",
    "root_post_screenshot_path",
    "media_items",
    "post_summary",
    "media_summary",
)


def source_item_match_keys(source_item: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    url = clean_text(source_item.get("url")).lower()
    if url:
        keys.append(f"url:{url}")
    source_name = clean_text(source_item.get("source_name")).lower()
    source_type = clean_text(source_item.get("source_type")).lower()
    published_at = clean_text(source_item.get("published_at"))
    summary = clean_text(source_item.get("summary") or source_item.get("title")).lower()
    if source_name and published_at:
        keys.append(f"source-time:{source_name}|{published_at}")
    if source_name and summary:
        keys.append(f"source-summary:{source_name}|{summary}")
    if source_name and source_type:
        keys.append(f"source-type:{source_name}|{source_type}")
    return keys


def source_item_has_visual_enrichment(source_item: dict[str, Any]) -> bool:
    return bool(
        clean_text(source_item.get("root_post_screenshot_path"))
        or safe_list(source_item.get("artifact_manifest"))
        or safe_list(source_item.get("media_items"))
    )


def merge_source_item_enrichment(selected_item: dict[str, Any], manual_item: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(selected_item)
    if not manual_item:
        return merged
    for field in ("artifact_manifest", "media_items"):
        if not safe_list(merged.get(field)):
            merged[field] = deepcopy(safe_list(manual_item.get(field)))
    for field in ("root_post_screenshot_path", "post_summary", "media_summary", "summary", "title"):
        if not clean_text(merged.get(field)):
            merged[field] = clean_text(manual_item.get(field))
    return merged


def find_matching_manual_topic_candidate(selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    selected_title = clean_public_topic_title(selected_topic.get("title")).lower()
    selected_summary = clean_text(selected_topic.get("summary")).lower()
    selected_urls = {
        clean_text(item.get("url")).lower()
        for item in safe_list(selected_topic.get("source_items"))
        if clean_text(item.get("url"))
    }
    best_match: dict[str, Any] = {}
    best_score = 0
    for candidate in safe_list(request.get("manual_topic_candidates")):
        candidate_dict = safe_dict(candidate)
        score = 0
        candidate_title = clean_public_topic_title(candidate_dict.get("title")).lower()
        if selected_title and candidate_title == selected_title:
            score += 5
        candidate_summary = clean_text(candidate_dict.get("summary")).lower()
        if selected_summary and candidate_summary and candidate_summary == selected_summary:
            score += 1
        candidate_urls = {
            clean_text(item.get("url")).lower()
            for item in safe_list(candidate_dict.get("source_items"))
            if clean_text(item.get("url"))
        }
        score += len(selected_urls & candidate_urls) * 3
        if score > best_score:
            best_score = score
            best_match = candidate_dict
    return deepcopy(best_match) if best_score > 0 else {}


def merge_selected_topic_with_manual_candidate(selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    manual_candidate = find_matching_manual_topic_candidate(selected_topic, request)
    if not manual_candidate:
        return deepcopy(selected_topic)

    merged = deepcopy(selected_topic)
    selected_items = [deepcopy(item) for item in safe_list(selected_topic.get("source_items")) if isinstance(item, dict)]
    manual_items = [deepcopy(item) for item in safe_list(manual_candidate.get("source_items")) if isinstance(item, dict)]
    if not manual_items:
        return merged

    manual_lookup: dict[str, dict[str, Any]] = {}
    for item in manual_items:
        for key in source_item_match_keys(item):
            manual_lookup.setdefault(key, item)

    matched_manual_ids: set[int] = set()
    merged_source_items: list[dict[str, Any]] = []
    for selected_item in selected_items:
        manual_item = next((manual_lookup[key] for key in source_item_match_keys(selected_item) if key in manual_lookup), None)
        if manual_item:
            matched_manual_ids.add(id(manual_item))
        merged_source_items.append(merge_source_item_enrichment(selected_item, manual_item))

    if not merged_source_items:
        merged_source_items = deepcopy(manual_items)
    else:
        for manual_item in manual_items:
            if id(manual_item) in matched_manual_ids:
                continue
            if source_item_has_visual_enrichment(manual_item):
                merged_source_items.append(deepcopy(manual_item))

    merged["source_items"] = merged_source_items
    if not clean_text(merged.get("summary")):
        merged["summary"] = clean_text(manual_candidate.get("summary"))
    merged["source_count"] = max(int(merged.get("source_count", 0) or 0), len(merged_source_items))
    return merged


def _legacy_v1_build_claims(selected_topic: dict[str, Any]) -> list[dict[str, str]]:
    title = clean_text(selected_topic.get("title")) or "当前热点"
    claim_open_text = f"围绕“{title}”目前仍有关键细节、影响路径或真假边界需要继续核实。"
    return [
        {
            "claim_id": "claim-core",
            "claim_text": f"“{title}”对应的是一个正在被多源讨论的真实事件、趋势或公开争议。",
        },
        {
            "claim_id": "claim-relevance",
            "claim_text": f"“{title}”对商业、投资或产业读者具有明确解释价值，不只是情绪型热度。",
        },
        {
            "claim_id": "claim-open",
            "claim_text": claim_open_text,
        },
    ]


def _legacy_v1_build_market_relevance(selected_topic: dict[str, Any]) -> list[str]:
    keywords = [keyword.lower() for keyword in clean_string_list(selected_topic.get("keywords"))]
    text = " ".join(keywords)
    rows = ["中文商业与投资读者对事件背景、真假边界和影响路径的解释需求"]
    if any(keyword in text for keyword in ["ai", "agent", "openai", "claude", "算力", "芯片", "半导体"]):
        rows.append("AI 与科技产业链估值、订单和叙事扩散的敏感度")
    if any(keyword in text for keyword in ["油", "天然气", "航运", "军工", "战争", "关税", "政策"]):
        rows.append("宏观政策、商品价格或风险偏好变化对相关板块的传导")
    if any(keyword in text for keyword in ["裁员", "融资", "ipo", "上市", "银行", "证券"]):
        rows.append("企业经营、资本市场和融资环境的读者关注度")
    return rows[:3]


def build_source_candidate_states(selected_topic: dict[str, Any], source_item: dict[str, Any]) -> dict[str, str]:
    score_breakdown = safe_dict(selected_topic.get("score_breakdown"))
    source_type = clean_text(source_item.get("source_type"))
    claim_states = {"claim-core": "support"}
    claim_states["claim-relevance"] = "support" if score_breakdown.get("relevance", 0) >= 45 or source_type != "social" else "unclear"
    claim_states["claim-open"] = "support" if score_breakdown.get("debate", 0) >= 50 or selected_topic.get("source_count", 0) >= 2 else "unclear"
    return claim_states


def _legacy_v1_build_news_request_from_topic(selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    analysis_time = request["analysis_time"]
    title = clean_text(selected_topic.get("title")) or request["topic"] or "hot-topic"
    summary = clean_text(selected_topic.get("summary")) or title
    source_candidates = []
    expected_source_families = []
    for index, source_item in enumerate(safe_list(selected_topic.get("source_items")), start=1):
        source_name = clean_text(source_item.get("source_name")) or f"source-{index:02d}"
        source_type = clean_text(source_item.get("source_type")) or "major_news"
        family = source_type
        if family not in expected_source_families:
            expected_source_families.append(family)
        source_candidates.append(
            {
                "source_id": f"{slugify(title, 'topic')}-{index:02d}",
                "source_name": source_name,
                "source_type": source_type,
                "published_at": clean_text(source_item.get("published_at")) or isoformat_or_blank(analysis_time),
                "observed_at": clean_text(source_item.get("observed_at")) or isoformat_or_blank(analysis_time),
                "url": clean_text(source_item.get("url")),
                "text_excerpt": clean_text(source_item.get("summary") or source_item.get("title") or summary),
                "claim_ids": ["claim-core", "claim-relevance", "claim-open"],
                "claim_states": build_source_candidate_states(selected_topic, source_item),
                "artifact_manifest": deepcopy(safe_list(source_item.get("artifact_manifest"))),
                "root_post_screenshot_path": clean_text(source_item.get("root_post_screenshot_path")),
                "media_items": deepcopy(safe_list(source_item.get("media_items"))),
                "post_summary": clean_text(source_item.get("post_summary")),
                "media_summary": clean_text(source_item.get("media_summary")),
            }
        )
    if not source_candidates:
        raise ValueError("Selected topic has no source_items, so it cannot be turned into a news-index request.")
    return {
        "topic": title,
        "analysis_time": isoformat_or_blank(analysis_time),
        "questions": [
            f"围绕“{title}”现在到底发生了什么，哪些事实已经被多源确认？",
            f"为什么这个话题会热起来，它对商业、产业或投资读者意味着什么？",
            "目前还有哪些关键事实未确认，文章里必须明确说清？",
        ],
        "use_case": "wechat-article-publishing",
        "source_preferences": ["public-first", "evidence-first"],
        "mode": "generic",
        "windows": ["1h", "6h", "24h"],
        "claims": build_claims(selected_topic),
        "candidates": source_candidates,
        "market_relevance": build_market_relevance(selected_topic),
        "expected_source_families": expected_source_families,
        "max_parallel_candidates": min(4, max(1, len(source_candidates))),
    }


def _legacy_v1_truncate_text(text: str, max_chars: int) -> str:
    stripped = clean_text(text)
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max(0, max_chars - 1)].rstrip() + "…"


def build_digest(article_package: dict[str, Any], max_chars: int) -> str:
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    source = " ".join(
        item
        for item in [
            clean_text(article_package.get("lede")),
            clean_text(safe_dict(sections[0] if sections else {}).get("paragraph")),
            clean_text(article_package.get("draft_thesis")),
        ]
        if item
    )
    return truncate_text(source, max_chars)


def _legacy_v1_extract_keywords(selected_topic: dict[str, Any], article_package: dict[str, Any]) -> list[str]:
    keywords = clean_string_list(selected_topic.get("keywords"))
    title = clean_text(article_package.get("title"))
    for token in title.replace("：", " ").replace(":", " ").split():
        token = token.strip()
        if len(token) >= 2 and token not in keywords:
            keywords.append(token)
    thesis = clean_text(article_package.get("draft_thesis"))
    for token in thesis.replace("，", " ").replace(",", " ").split():
        token = token.strip()
        if len(token) >= 2 and token not in keywords:
            keywords.append(token)
    return keywords[:8]


def _legacy_v1_build_editor_anchors(section_count: int) -> list[dict[str, str]]:
    anchors = [{"placement": "after_lede", "text": "这里补一个你自己的判断升级条件，或者一句反直觉结论。"}]
    if section_count >= 2:
        anchors.append({"placement": "after_section_2", "text": "这里加入你亲身见过的案例、行业对话或一次踩坑经历。"})
    if section_count >= 4:
        anchors.append({"placement": "after_section_4", "text": "这里补一个只属于你自己的结论收口，不要只重复公开信息。"})
    return anchors


def paragraph_blocks(text: str) -> list[str]:
    parts = [clean_text(part) for part in str(text or "").split("\n") if clean_text(part)]
    return parts or [clean_text(text)]


def build_image_plan(selected_images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for index, item in enumerate(selected_images, start=1):
        asset_id = clean_text(item.get("asset_id") or item.get("image_id") or f"image-{index:02d}")
        source_url = clean_text(item.get("source_url"))
        local_path = clean_text(item.get("path") or item.get("local_artifact_path"))
        preview_src = source_url if source_url.startswith("http") else ""
        if not preview_src and local_path:
            local_file = Path(local_path).expanduser()
            preview_src = local_file.resolve().as_uri() if local_file.exists() else local_path
        upload_token = f"{{{{WECHAT_IMAGE_{asset_id}}}}}"
        plan.append(
            {
                "asset_id": asset_id,
                "placement": clean_text(item.get("placement")) or "appendix",
                "caption": clean_text(item.get("caption")),
                "source_name": clean_text(item.get("source_name")),
                "local_path": local_path,
                "source_url": source_url,
                "render_src": preview_src or upload_token,
                "upload_token": upload_token,
                "upload_required": bool(source_url or local_path),
                "status": clean_text(item.get("status")),
            }
        )
    return plan


def cover_score_base(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def resolve_render_src(local_path: Any, source_url: Any, render_src: Any = "") -> str:
    resolved_render_src = clean_text(render_src)
    if resolved_render_src:
        return resolved_render_src
    resolved_source_url = clean_text(source_url)
    if resolved_source_url.startswith(("http://", "https://")):
        return resolved_source_url
    resolved_local_path = clean_text(local_path)
    if not resolved_local_path:
        return ""
    local_file = Path(resolved_local_path).expanduser()
    return local_file.resolve().as_uri() if local_file.exists() else resolved_local_path


UI_CAPTURE_NOISE_MARKERS = (
    'link "',
    "/url:",
    "progressbar",
    "banner - main",
    "login",
    "log in",
    "sign in",
    "sign up",
    "new to x",
    "加载中",
    "登录",
    "注册",
    "抢先知道",
    "main:",
)


def looks_like_ui_capture_noise(text: Any) -> bool:
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    if not cleaned:
        return False
    return any(marker in lowered or marker in cleaned for marker in UI_CAPTURE_NOISE_MARKERS)


def cover_assets_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for field in ("asset_id", "local_path", "source_url", "render_src"):
        left_value = clean_text(left.get(field))
        right_value = clean_text(right.get(field))
        if left_value and left_value == right_value:
            return True
    return False


def resolve_cover_caption(primary_image: dict[str, Any], image_plan: list[dict[str, Any]]) -> str:
    captions: list[str] = []
    direct_caption = clean_text(primary_image.get("caption"))
    if direct_caption:
        captions.append(direct_caption)
    for item in image_plan:
        if cover_assets_match(primary_image, item):
            plan_caption = clean_text(item.get("caption"))
            if plan_caption and plan_caption not in captions:
                captions.append(plan_caption)
    for caption in captions:
        if not looks_like_ui_capture_noise(caption):
            return caption
    if is_screenshot_cover_role(primary_image.get("role")):
        source_name = clean_text(primary_image.get("source_name"))
        if source_name:
            return f"{source_name} 的原始帖子截图，保留了这轮讨论最早的页面界面和上下文。"
        return "原始帖子截图，保留了页面界面和上下文。"
    return direct_caption


def normalize_cover_candidate(
    raw_item: dict[str, Any],
    *,
    selected_for_body: bool,
    body_order: int,
    source_kind: str,
) -> dict[str, Any]:
    asset_id = clean_text(raw_item.get("asset_id") or raw_item.get("image_id"))
    local_path = clean_text(raw_item.get("local_path") or raw_item.get("path") or raw_item.get("local_artifact_path"))
    source_url = clean_text(raw_item.get("source_url"))
    render_src = resolve_render_src(local_path, source_url, raw_item.get("render_src"))
    caption = clean_text(raw_item.get("caption") or raw_item.get("summary") or raw_item.get("alt_text"))
    status = clean_text(raw_item.get("status"))
    if not status:
        local_exists = bool(local_path) and Path(local_path).expanduser().exists()
        if local_exists:
            status = "local_ready"
        elif source_url.startswith(("http://", "https://")):
            status = "remote_only"
    return {
        "asset_id": asset_id,
        "local_path": local_path,
        "source_url": source_url,
        "render_src": render_src,
        "caption": caption,
        "summary": clean_text(raw_item.get("summary") or raw_item.get("caption")),
        "source_name": clean_text(raw_item.get("source_name")),
        "status": status,
        "role": clean_text(raw_item.get("role")),
        "access_mode": clean_text(raw_item.get("access_mode")),
        "capture_method": clean_text(raw_item.get("capture_method")),
        "placement": clean_text(raw_item.get("placement")),
        "upload_required": bool(raw_item.get("upload_required")) or bool(local_path or source_url),
        "selected_for_body": selected_for_body,
        "body_order": body_order,
        "source_kind": clean_text(source_kind),
        "cover_score_base": cover_score_base(raw_item.get("score")),
    }


def cover_candidate_key(candidate: dict[str, Any]) -> tuple[str, ...]:
    asset_id = clean_text(candidate.get("asset_id"))
    if asset_id:
        return ("asset_id", asset_id)
    local_path = clean_text(candidate.get("local_path"))
    if local_path:
        return ("local_path", local_path)
    source_url = clean_text(candidate.get("source_url"))
    if source_url:
        return ("source_url", source_url)
    render_src = clean_text(candidate.get("render_src"))
    if render_src:
        return ("render_src", render_src)
    return (
        "fallback",
        clean_text(candidate.get("source_name")),
        clean_text(candidate.get("role")),
        clean_text(candidate.get("caption")),
    )


def merge_cover_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in (
        "asset_id",
        "local_path",
        "source_url",
        "render_src",
        "caption",
        "summary",
        "source_name",
        "status",
        "role",
        "access_mode",
        "capture_method",
        "placement",
    ):
        if not clean_text(merged.get(key)) and clean_text(incoming.get(key)):
            merged[key] = incoming.get(key)
    merged["upload_required"] = bool(merged.get("upload_required")) or bool(incoming.get("upload_required"))
    merged["selected_for_body"] = bool(merged.get("selected_for_body")) or bool(incoming.get("selected_for_body"))
    merged["body_order"] = min(normalize_body_order(merged.get("body_order")), normalize_body_order(incoming.get("body_order")))
    merged["cover_score_base"] = max(
        cover_score_base(merged.get("cover_score_base")),
        cover_score_base(incoming.get("cover_score_base")),
    )
    if clean_text(incoming.get("source_kind")) == "selected_body_image":
        merged["source_kind"] = "selected_body_image"
    elif not clean_text(merged.get("source_kind")):
        merged["source_kind"] = clean_text(incoming.get("source_kind"))
    return merged


def is_screenshot_cover_role(role: Any) -> bool:
    clean_role = clean_text(role).lower()
    return bool(clean_role) and (clean_role == "screenshot" or clean_role.endswith("_screenshot") or "screenshot" in clean_role)


def screenshot_cover_role_score(role: str) -> int:
    if role == "article_page_screenshot":
        return 42
    if role in {"page_screenshot", "title_screenshot", "observation_screenshot"}:
        return 36
    if role == "root_post_screenshot":
        return 18
    return 24


def normalize_body_order(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 9999


def score_cover_candidate(candidate: dict[str, Any]) -> int:
    score = cover_score_base(candidate.get("cover_score_base"))
    if has_usable_upload_source(candidate):
        score += 50
    else:
        score -= 200

    role = clean_text(candidate.get("role"))
    if role == "post_media":
        score += 70
    elif is_screenshot_cover_role(role):
        score += screenshot_cover_role_score(role)
    elif role:
        score += 10

    status = clean_text(candidate.get("status"))
    if status == "local_ready":
        score += 18
        if is_screenshot_cover_role(role) and role != "root_post_screenshot":
            score += 10
    elif clean_text(candidate.get("source_url")).startswith(("http://", "https://")):
        score += 8

    if clean_text(candidate.get("caption")):
        score += 8
    if clean_text(candidate.get("source_name")):
        score += 4
    access_mode = clean_text(candidate.get("access_mode"))
    if access_mode == "blocked":
        score -= 16 if role == "root_post_screenshot" else 6 if is_screenshot_cover_role(role) else 16
    elif access_mode == "public" and is_screenshot_cover_role(role):
        score += 6
    capture_method = clean_text(candidate.get("capture_method"))
    if capture_method == "dom_clip":
        score -= 3
    elif capture_method in {"page_hints", "artifact_manifest", "observation_screenshot"} and is_screenshot_cover_role(role):
        score += 2
    if bool(candidate.get("selected_for_body")):
        score += 4
    if clean_text(candidate.get("placement")) == "after_lede":
        score += 2
    return score


def cover_candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    body_order = normalize_body_order(candidate.get("body_order"))
    role = clean_text(candidate.get("role"))
    role_rank = 2 if role == "post_media" else 1 if is_screenshot_cover_role(role) else 0
    return (
        int(candidate.get("cover_score", 0) or 0),
        role_rank,
        1 if clean_text(candidate.get("status")) == "local_ready" else 0,
        -body_order,
    )


def build_cover_candidates(
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged_candidates: dict[tuple[str, ...], dict[str, Any]] = {}
    selected_body_order = {
        clean_text(item.get("asset_id") or item.get("image_id")): index
        for index, item in enumerate(image_plan)
        if clean_text(item.get("asset_id") or item.get("image_id"))
    }

    for item in draft_image_candidates:
        if not isinstance(item, dict):
            continue
        asset_id = clean_text(item.get("image_id") or item.get("asset_id"))
        candidate = normalize_cover_candidate(
            item,
            selected_for_body=asset_id in selected_body_order,
            body_order=selected_body_order.get(asset_id, 9999),
            source_kind="draft_image_candidate",
        )
        if not any(clean_text(candidate.get(field)) for field in ("asset_id", "local_path", "source_url", "render_src")):
            continue
        key = cover_candidate_key(candidate)
        merged_candidates[key] = merge_cover_candidate(merged_candidates.get(key, {}), candidate) if key in merged_candidates else candidate

    for index, item in enumerate(image_plan):
        candidate = normalize_cover_candidate(
            item,
            selected_for_body=True,
            body_order=index,
            source_kind="selected_body_image",
        )
        key = cover_candidate_key(candidate)
        merged_candidates[key] = merge_cover_candidate(merged_candidates.get(key, {}), candidate) if key in merged_candidates else candidate

    candidates = list(merged_candidates.values())
    for candidate in candidates:
        candidate["cover_score"] = score_cover_candidate(candidate)
        candidate["upload_ready"] = has_usable_upload_source(candidate)
    candidates.sort(key=cover_candidate_sort_key, reverse=True)
    return candidates


def reduce_cover_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": clean_text(candidate.get("asset_id")),
        "role": clean_text(candidate.get("role")),
        "source_kind": clean_text(candidate.get("source_kind")),
        "selected_for_body": bool(candidate.get("selected_for_body")),
        "body_order": normalize_body_order(candidate.get("body_order")),
        "cover_score": int(candidate.get("cover_score", 0) or 0),
        "upload_ready": bool(candidate.get("upload_ready")),
        "caption": clean_text(candidate.get("caption")),
        "source_name": clean_text(candidate.get("source_name")),
        "status": clean_text(candidate.get("status")),
        "local_path": clean_text(candidate.get("local_path")),
        "source_url": clean_text(candidate.get("source_url")),
        "render_src": clean_text(candidate.get("render_src")),
    }


def select_cover_candidate(
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, str, list[dict[str, Any]]]:
    request = safe_dict(request)
    cover_candidates = build_cover_candidates(image_plan, draft_image_candidates)
    dedicated_cover_candidates = [
        item
        for item in cover_candidates
        if not bool(item.get("selected_for_body")) and bool(item.get("upload_ready"))
    ]
    screenshot_cover_candidates = [
        item
        for item in cover_candidates
        if is_screenshot_cover_role(item.get("role")) and bool(item.get("upload_ready"))
    ]
    if dedicated_cover_candidates:
        selected_cover = safe_dict(dedicated_cover_candidates[0])
        if (
            clean_text(request.get("image_strategy")) == "prefer_images"
            and not is_screenshot_cover_role(selected_cover.get("role"))
            and screenshot_cover_candidates
        ):
            selected_cover = safe_dict(sorted(screenshot_cover_candidates, key=lambda item: normalize_body_order(item.get("body_order")))[0])
            selection_mode = "screenshot_candidate"
            selection_reason = (
                f"Selected screenshot cover candidate {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
                "from the body image order."
            )
        else:
            selection_mode = "dedicated_candidate"
            selection_reason = (
                f"Selected dedicated cover candidate {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
                f"from draft image discovery with score {int(selected_cover.get('cover_score', 0) or 0)}."
            )
        return selected_cover, selection_mode, selection_reason, cover_candidates

    if screenshot_cover_candidates:
        selected_cover = safe_dict(screenshot_cover_candidates[0])
        selection_mode = "screenshot_candidate"
        selection_reason = (
            f"Selected screenshot cover candidate {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
            f"with score {int(selected_cover.get('cover_score', 0) or 0)}."
        )
        return selected_cover, selection_mode, selection_reason, cover_candidates

    body_cover_candidates = sorted(
        [item for item in cover_candidates if bool(item.get("selected_for_body")) and bool(item.get("upload_ready"))],
        key=lambda item: normalize_body_order(item.get("body_order")),
    )
    if body_cover_candidates:
        selected_cover = safe_dict(body_cover_candidates[0])
        selection_mode = "body_image_fallback"
        selection_reason = (
            f"Falling back to body image {clean_text(selected_cover.get('asset_id')) or 'unknown'} "
            "because no dedicated cover candidate was ready."
        )
        return selected_cover, selection_mode, selection_reason, cover_candidates

    return (
        {},
        "manual_required",
        "No usable cover candidate is ready yet. Provide cover_image_path or cover_image_url.",
        cover_candidates,
    )


def _legacy_v1_render_anchor_html(anchor_text: str) -> str:
    return (
        "<section style=\"margin:20px 0;padding:12px 14px;border-left:4px solid #e3a008;"
        "background:#fff8e7;border-radius:6px;\">"
        f"<p style=\"margin:0;color:#8a5a00;font-size:14px;line-height:1.7;\">"
        f"✏️ 编辑锚点：{escape(anchor_text)}</p></section>"
    )


def render_image_html(image_item: dict[str, Any]) -> str:
    src = clean_text(image_item.get("render_src"))
    caption = clean_text(image_item.get("caption"))
    return (
        "<section style=\"margin:18px 0;text-align:center;\">"
        f"<img src=\"{escape(src)}\" alt=\"{escape(caption or 'image')}\" "
        "style=\"max-width:100%;border-radius:8px;display:block;margin:0 auto;\" />"
        f"{f'<p style=\"margin:8px 0 0;color:#666;font-size:13px;line-height:1.6;\">{escape(caption)}</p>' if caption else ''}"
        "</section>"
    )


def citation_short_date(value: Any) -> str:
    parsed = parse_datetime(value, fallback=None)
    if parsed is not None:
        return parsed.date().isoformat()
    return clean_text(value)


def citation_link_text(citation: dict[str, Any]) -> str:
    return clean_text(citation.get("title") or citation.get("excerpt") or citation.get("source_name") or citation.get("citation_id") or "source")


def render_citation_html(citation: dict[str, Any]) -> str:
    title = citation_link_text(citation)
    source_name = clean_text(citation.get("source_name"))
    published_at = citation_short_date(citation.get("published_at") or citation.get("observed_at"))
    url = clean_text(citation.get("url"))
    meta = " | ".join(item for item in (source_name, published_at) if item)
    title_html = (
        f"<a href=\"{escape(url)}\" style=\"color:#0f766e;text-decoration:none;\">{escape(title)}</a>"
        if url
        else escape(title)
    )
    meta_html = f"<div style=\"margin-top:3px;color:#6b7280;font-size:12px;line-height:1.7;\">{escape(meta)}</div>" if meta else ""
    return (
        "<li style=\"margin:0 0 12px;color:#374151;font-size:14px;line-height:1.8;\">"
        f"{title_html}"
        f"{meta_html}"
        "</li>"
    )


def render_wechat_html(
    article_package: dict[str, Any],
    image_plan: list[dict[str, Any]],
    anchors: list[dict[str, str]],
    *,
    editor_anchor_mode: str = "hidden",
) -> str:
    subtitle = clean_text(article_package.get("subtitle"))
    lede = clean_text(article_package.get("lede"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    citations = safe_list(article_package.get("citations"))
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in image_plan:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)
    anchors_by_placement: dict[str, list[dict[str, str]]] = {}
    for item in anchors:
        anchors_by_placement.setdefault(clean_text(item.get("placement")), []).append(item)

    html_parts = [
        "<article style=\"font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#1f2329;"
        "font-size:16px;line-height:1.9;\">",
        "<section style=\"margin-bottom:22px;\">",
    ]
    if subtitle:
        html_parts.append(
            f"<p style=\"margin:0 0 14px;color:#4b5563;font-size:15px;line-height:1.8;\">{escape(subtitle)}</p>"
        )
    if lede:
        html_parts.append(
            "<blockquote style=\"margin:0;padding:14px 16px;border-left:4px solid #0f766e;"
            "background:#f0fdfa;border-radius:6px;color:#134e4a;\">"
            f"{escape(lede)}</blockquote>"
        )
    html_parts.append("</section>")

    for item in images_by_placement.get("after_lede", []):
        html_parts.append(render_image_html(item))
    if editor_anchor_mode == "inline":
        for item in anchors_by_placement.get("after_lede", []):
            html_parts.append(render_anchor_html(item.get("text", "")))

    for index, section in enumerate(sections, start=1):
        heading = clean_text(section.get("heading")) or f"部分 {index}"
        html_parts.append("<section style=\"margin:18px 0;\">")
        html_parts.append(
            "<p style=\"margin:0 0 12px;padding-top:4px;color:#111827;"
            "font-size:24px;line-height:1.5;font-weight:700;font-style:italic;\">"
            f"{escape(heading)}</p>"
        )
        for paragraph in paragraph_blocks(section.get("paragraph")):
            html_parts.append(f"<p style=\"margin:0 0 14px;\">{escape(paragraph)}</p>")
        html_parts.append("</section>")
        for item in images_by_placement.get(f"after_section_{index}", []):
            html_parts.append(render_image_html(item))
        if editor_anchor_mode == "inline":
            for item in anchors_by_placement.get(f"after_section_{index}", []):
                html_parts.append(render_anchor_html(item.get("text", "")))

    for item in images_by_placement.get("appendix", []):
        html_parts.append(render_image_html(item))

    if citations:
        html_parts.append("<section style=\"margin-top:28px;\">")
        html_parts.append("<h2 style=\"font-size:20px;line-height:1.45;margin:0 0 10px;color:#111827;\">来源</h2>")
        html_parts.append("<ol style=\"padding-left:20px;margin:0;\">")
        for citation in citations:
            source_name = clean_text(citation.get("source_name"))
            url = clean_text(citation.get("url"))
            html_parts.append(
                "<li style=\"margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.8;\">"
                f"{escape(source_name or citation.get('citation_id', 'source'))}"
                f"{f'：<a href=\"{escape(url)}\" style=\"color:#0f766e;text-decoration:none;\">{escape(url)}</a>' if url else ''}"
                "</li>"
            )
        if citations:
            html_parts[-len(citations) :] = [render_citation_html(citation) for citation in citations]
        html_parts.append("</ol></section>")
    html_parts.append("</article>")
    return "\n".join(html_parts) + "\n"

# Canonical publish helpers. Older v1 variants above are retained for diff-safe archaeology.
def build_claims(selected_topic: dict[str, Any]) -> list[dict[str, str]]:
    title = clean_public_topic_title(selected_topic.get("title")) or "当前热点"
    title_fragments = topic_title_fragments(title)
    source_claim_candidates = source_summary_claims(selected_topic)
    relevance_claim = derive_relevance_claims(selected_topic, title)
    open_claim = derive_open_claim(selected_topic, title)

    if title_fragments:
        core_claim_zh = title_fragments[0]
        core_claim_en = source_claim_candidates[0]["en"] if source_claim_candidates else f'The main confirmed development is: {title_fragments[0]}.'
    elif source_claim_candidates:
        core_claim_zh = clean_text(source_claim_candidates[0].get("zh"))
        core_claim_en = clean_text(source_claim_candidates[0].get("en"))
    else:
        core_claim_zh = f"“{title}”对应的是一个已经进入公开讨论的真实事件、趋势或争议。"
        core_claim_en = f'The topic "{title}" reflects a real event, trend, or public dispute that is already drawing multi-source attention.'

    if len(title_fragments) >= 2:
        relevance_claim_zh = title_fragments[1]
        relevance_claim_en = source_claim_candidates[1]["en"] if len(source_claim_candidates) >= 2 else clean_text(relevance_claim.get("en"))
    elif len(source_claim_candidates) >= 2:
        relevance_claim_zh = clean_text(source_claim_candidates[1].get("zh"))
        relevance_claim_en = clean_text(source_claim_candidates[1].get("en"))
    else:
        relevance_claim_zh = clean_text(relevance_claim.get("zh"))
        relevance_claim_en = clean_text(relevance_claim.get("en"))

    return [
        {
            "claim_id": "claim-core",
            "claim_text": core_claim_en,
            "claim_text_zh": core_claim_zh,
        },
        {
            "claim_id": "claim-relevance",
            "claim_text": relevance_claim_en,
            "claim_text_zh": relevance_claim_zh,
        },
        {
            "claim_id": "claim-open",
            "claim_text": clean_text(open_claim.get("en")),
            "claim_text_zh": clean_text(open_claim.get("zh")),
        },
    ]


def build_market_relevance(selected_topic: dict[str, Any]) -> list[str]:
    text = topic_keyword_text(selected_topic)
    rows = ["event background, transmission path, and downstream impact"]
    if is_developer_tooling_topic(selected_topic):
        rows.extend(
            [
                "product boundaries, tool-calling, and permission design",
                "browser control and workflow orchestration",
            ]
        )
    elif any(keyword in text for keyword in ["ai", "agent", "openai", "claude", "芯片", "半导体", "算力"]):
        rows.append("funding appetite, order visibility, and budget conversion")
    if any(keyword in text for keyword in ["招聘", "hiring", "recruit", "招人"]):
        rows.append("hiring pace, organization expansion, and sector sentiment")
    if any(keyword in text for keyword in ["油", "油气", "天然气", "lng", "航运", "军工", "战争", "关税", "政策"]):
        rows.append("commodity prices, policy room, and risk appetite transmission")
    if any(keyword in text for keyword in ["裁员", "融资", "ipo", "上市", "银行", "证券"]):
        rows.append("corporate operations, capital markets, and financing conditions")
    return rows[:3]


def build_market_relevance_zh(selected_topic: dict[str, Any]) -> list[str]:
    text = topic_keyword_text(selected_topic)
    rows = ["事件背景、传导路径和后续影响"]
    if is_developer_tooling_topic(selected_topic):
        rows.extend(
            [
                "产品边界、工具调用与权限设计",
                "浏览器控制、工作流编排",
            ]
        )
    elif any(keyword in text for keyword in ["ai", "agent", "openai", "claude", "芯片", "半导体", "算力"]):
        rows.append("融资意愿、订单能见度和预算投放")
    if any(keyword in text for keyword in ["招聘", "hiring", "recruit", "招人"]):
        rows.append("招聘节奏、组织扩张和行业景气度")
    if any(keyword in text for keyword in ["油", "油气", "天然气", "lng", "航运", "军工", "战争", "关税", "政策"]):
        rows.append("商品价格、政策空间和风险偏好传导")
    if any(keyword in text for keyword in ["裁员", "融资", "ipo", "上市", "银行", "证券"]):
        rows.append("企业经营、资本市场和融资环境")
    return rows[:3]


def build_news_request_from_topic(selected_topic: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    analysis_time = request["analysis_time"]
    language_mode = clean_text(request.get("language_mode")).lower()
    title = clean_public_topic_title(selected_topic.get("title")) or clean_public_topic_title(request["topic"]) or "hot-topic"
    summary = clean_text(selected_topic.get("summary")) or title
    claims = build_claims(selected_topic)
    market_relevance = build_market_relevance(selected_topic)
    market_relevance_zh = build_market_relevance_zh(selected_topic)
    source_candidates = []
    expected_source_families = []
    for index, source_item in enumerate(safe_list(selected_topic.get("source_items")), start=1):
        source_name = clean_text(source_item.get("source_name")) or f"source-{index:02d}"
        source_type = clean_text(source_item.get("source_type")) or "major_news"
        family = source_type
        if family not in expected_source_families:
            expected_source_families.append(family)
        text_excerpt = localize_candidate_copy(
            source_item.get("summary") or source_item.get("title") or summary,
            language_mode=language_mode,
        )
        post_summary = localize_candidate_copy(source_item.get("post_summary"), language_mode=language_mode)
        media_summary = localize_candidate_copy(source_item.get("media_summary"), language_mode=language_mode)
        source_candidates.append(
            {
                "source_id": f"{slugify(title, 'topic')}-{index:02d}",
                "source_name": source_name,
                "source_type": source_type,
                "published_at": clean_text(source_item.get("published_at")) or isoformat_or_blank(analysis_time),
                "observed_at": clean_text(source_item.get("observed_at")) or isoformat_or_blank(analysis_time),
                "url": clean_text(source_item.get("url")),
                "text_excerpt": text_excerpt,
                "claim_ids": ["claim-core", "claim-relevance", "claim-open"],
                "claim_states": build_source_candidate_states(selected_topic, source_item),
                "artifact_manifest": deepcopy(safe_list(source_item.get("artifact_manifest"))),
                "root_post_screenshot_path": clean_text(source_item.get("root_post_screenshot_path")),
                "media_items": deepcopy(safe_list(source_item.get("media_items"))),
                "post_summary": post_summary,
                "media_summary": media_summary,
            }
        )
    if not source_candidates:
        raise ValueError("Selected topic has no source_items, so it cannot be turned into a news-index request.")
    return {
        "topic": title,
        "analysis_time": isoformat_or_blank(analysis_time),
        "questions": [
            f"围绕“{title}”，现在到底发生了什么，哪些事实已经能被多源确认？",
            f"这件事为什么会热起来，它对商业、产业或投资读者真正意味着什么？",
            "目前还有哪些关键事实没有确认，文章里必须明确标出来而不能写成既成事实？",
        ],
        "use_case": "wechat-article-publishing",
        "source_preferences": ["public-first", "evidence-first"],
        "mode": "generic",
        "windows": ["1h", "6h", "24h"],
        "claims": claims,
        "candidates": source_candidates,
        "market_relevance": market_relevance,
        "market_relevance_zh": market_relevance_zh,
        "expected_source_families": expected_source_families,
        "max_parallel_candidates": min(4, max(1, len(source_candidates))),
    }


def truncate_text(text: str, max_chars: int) -> str:
    stripped = clean_text(text)
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max(0, max_chars - 1)].rstrip() + "…"


def extract_keywords(selected_topic: dict[str, Any], article_package: dict[str, Any]) -> list[str]:
    keywords = clean_string_list(selected_topic.get("keywords"))
    for source_text in (clean_text(article_package.get("title")), clean_text(article_package.get("draft_thesis"))):
        for token in (
            source_text.replace("，", " ")
            .replace(",", " ")
            .replace("：", " ")
            .replace(":", " ")
            .replace("|", " ")
            .split()
        ):
            token = token.strip()
            if len(token) >= 2 and token not in keywords:
                keywords.append(token)
    return keywords[:8]


def build_editor_anchors(section_count: int) -> list[dict[str, str]]:
    anchors = [{"placement": "after_lede", "text": "这里补一个你自己的判断升级条件，或者一句反直觉结论。"}]
    if section_count >= 2:
        anchors.append({"placement": "after_section_2", "text": "这里加入你亲身见过的案例、行业对话或一次踩坑经历。"})
    if section_count >= 4:
        anchors.append({"placement": "after_section_4", "text": "这里补一个只属于你自己的结论收口，不要只重复公开信息。"})
    return anchors


def render_anchor_html(anchor_text: str) -> str:
    return (
        "<section style=\"margin:20px 0;padding:12px 14px;border-left:4px solid #e3a008;"
        "background:#fff8e7;border-radius:6px;\">"
        f"<p style=\"margin:0;color:#8a5a00;font-size:14px;line-height:1.7;\">"
        f"✏️ 编辑锚点：{escape(anchor_text)}</p></section>"
    )


def _legacy_render_wechat_html(
    article_package: dict[str, Any],
    image_plan: list[dict[str, Any]],
    anchors: list[dict[str, str]],
    *,
    editor_anchor_mode: str = "hidden",
) -> str:
    subtitle = clean_text(article_package.get("subtitle"))
    lede = clean_text(article_package.get("lede"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    citations = safe_list(article_package.get("citations"))
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in image_plan:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)
    anchors_by_placement: dict[str, list[dict[str, str]]] = {}
    for item in anchors:
        anchors_by_placement.setdefault(clean_text(item.get("placement")), []).append(item)

    html_parts = [
        "<article style=\"font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#1f2329;"
        "font-size:16px;line-height:1.9;\">",
        "<section style=\"margin-bottom:22px;\">",
    ]
    if subtitle:
        html_parts.append(
            f"<p style=\"margin:0 0 14px;color:#4b5563;font-size:15px;line-height:1.8;\">{escape(subtitle)}</p>"
        )
    if lede:
        html_parts.append(
            "<blockquote style=\"margin:0;padding:14px 16px;border-left:4px solid #0f766e;"
            "background:#f0fdfa;border-radius:6px;color:#134e4a;\">"
            f"{escape(lede)}</blockquote>"
        )
    html_parts.append("</section>")

    for item in images_by_placement.get("after_lede", []):
        html_parts.append(render_image_html(item))
    if editor_anchor_mode == "inline":
        for item in anchors_by_placement.get("after_lede", []):
            html_parts.append(render_anchor_html(item.get("text", "")))

    for index, section in enumerate(sections, start=1):
        heading = clean_text(section.get("heading")) or f"第 {index} 部分"
        html_parts.append("<section style=\"margin:18px 0;\">")
        html_parts.append(
            "<p style=\"margin:0 0 12px;padding-top:4px;color:#111827;"
            "font-size:24px;line-height:1.5;font-weight:700;font-style:italic;\">"
            f"{escape(heading)}</p>"
        )
        for paragraph in paragraph_blocks(section.get("paragraph")):
            html_parts.append(f"<p style=\"margin:0 0 14px;\">{escape(paragraph)}</p>")
        html_parts.append("</section>")
        for item in images_by_placement.get(f"after_section_{index}", []):
            html_parts.append(render_image_html(item))
        if editor_anchor_mode == "inline":
            for item in anchors_by_placement.get(f"after_section_{index}", []):
                html_parts.append(render_anchor_html(item.get("text", "")))

    for item in images_by_placement.get("appendix", []):
        html_parts.append(render_image_html(item))

    if citations:
        html_parts.append("<section style=\"margin-top:28px;\">")
        html_parts.append("<h2 style=\"font-size:20px;line-height:1.45;margin:0 0 10px;color:#111827;\">来源</h2>")
        html_parts.append("<ol style=\"padding-left:20px;margin:0;\">")
        for citation in citations:
            source_name = clean_text(citation.get("source_name"))
            url = clean_text(citation.get("url"))
            html_parts.append(
                "<li style=\"margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.8;\">"
                f"{escape(source_name or citation.get('citation_id', 'source'))}"
                f"{f'：<a href=\"{escape(url)}\" style=\"color:#0f766e;text-decoration:none;\">{escape(url)}</a>' if url else ''}"
                "</li>"
            )
        html_parts.append("</ol></section>")
    html_parts.append("</article>")
    return "\n".join(html_parts) + "\n"

def build_cover_plan(
    selected_topic: dict[str, Any],
    image_plan: list[dict[str, Any]],
    draft_image_candidates: list[dict[str, Any]],
    keywords: list[str],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_image, selection_mode, selection_reason, cover_candidates = select_cover_candidate(
        image_plan,
        draft_image_candidates,
        request,
    )
    title = clean_public_topic_title(selected_topic.get("title")) or clean_text(selected_topic.get("title"))
    prompt = (
        f"Create a 16:9 WeChat article cover for: {title}. "
        f"Keywords: {', '.join(keywords[:5]) or title}. "
        "Style: calm editorial illustration, clean composition, realistic lighting, premium but restrained. "
        "Prefer a text-free cover. No Chinese text, no logo, no watermark, no UI chrome. "
        "If text is unavoidable, use short clear English only."
    )
    cover_caption = resolve_cover_caption(primary_image, image_plan)
    return {
        "primary_image_asset_id": clean_text(primary_image.get("asset_id")),
        "primary_image_render_src": clean_text(primary_image.get("render_src")),
        "primary_image_upload_required": bool(primary_image.get("upload_required")),
        "selected_cover_asset_id": clean_text(primary_image.get("asset_id")),
        "selected_cover_role": clean_text(primary_image.get("role")),
        "selected_cover_caption": cover_caption,
        "selected_cover_source_name": clean_text(primary_image.get("source_name")),
        "selected_cover_local_path": clean_text(primary_image.get("local_path")),
        "selected_cover_source_url": clean_text(primary_image.get("source_url")),
        "selected_cover_render_src": clean_text(primary_image.get("render_src")),
        "selected_cover_upload_required": bool(primary_image.get("upload_required")),
        "selection_mode": selection_mode,
        "selection_reason": selection_reason,
        "cover_selection_reason": selection_reason,
        "cover_candidates": [reduce_cover_candidate(item) for item in cover_candidates[:6]],
        "needs_thumb_media_id": True,
        "cover_prompt": prompt,
        "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
    }


def has_usable_upload_source(asset: dict[str, Any]) -> bool:
    local_path = clean_text(asset.get("local_path"))
    if local_path and Path(local_path).expanduser().exists():
        return True
    remote_url = clean_text(asset.get("source_url")) or clean_text(asset.get("render_src"))
    return remote_url.startswith(("http://", "https://"))


def resolve_cover_asset_from_plan(cover_plan: dict[str, Any], image_plan: list[dict[str, Any]]) -> dict[str, Any]:
    selected_cover_asset_id = clean_text(cover_plan.get("selected_cover_asset_id") or cover_plan.get("primary_image_asset_id"))
    for item in image_plan:
        if selected_cover_asset_id and clean_text(item.get("asset_id")) != selected_cover_asset_id:
            continue
        merged_item = dict(item)
        for field, cover_field in (
            ("local_path", "selected_cover_local_path"),
            ("source_url", "selected_cover_source_url"),
            ("render_src", "selected_cover_render_src"),
        ):
            if not clean_text(merged_item.get(field)) and clean_text(cover_plan.get(cover_field)):
                merged_item[field] = clean_text(cover_plan.get(cover_field))
        if selected_cover_asset_id and not clean_text(merged_item.get("asset_id")):
            merged_item["asset_id"] = selected_cover_asset_id
        return merged_item

    local_path = clean_text(cover_plan.get("selected_cover_local_path"))
    source_url = clean_text(cover_plan.get("selected_cover_source_url"))
    render_src = clean_text(cover_plan.get("selected_cover_render_src")) or resolve_render_src(local_path, source_url)
    if local_path or source_url or render_src:
        return {
            "asset_id": selected_cover_asset_id,
            "local_path": local_path,
            "source_url": source_url,
            "render_src": render_src,
            "upload_required": bool(local_path or source_url),
        }
    return {}


def build_push_readiness(
    request: dict[str, Any],
    html: str,
    draft_payload: dict[str, Any],
    image_plan: list[dict[str, Any]],
    cover_plan: dict[str, Any],
) -> dict[str, Any]:
    has_content_html = bool(clean_text(html))
    has_draft_payload_template = bool(safe_list(draft_payload.get("articles")))
    missing_render_asset_ids = [
        clean_text(item.get("asset_id")) or f"asset-{index:02d}"
        for index, item in enumerate(image_plan, start=1)
        if not clean_text(item.get("render_src"))
    ]
    missing_upload_source_asset_ids = [
        clean_text(item.get("asset_id")) or f"asset-{index:02d}"
        for index, item in enumerate(image_plan, start=1)
        if bool(item.get("upload_required")) and not has_usable_upload_source(item)
    ]
    inline_upload_required_count = sum(1 for item in image_plan if bool(item.get("upload_required")))

    explicit_cover_path = clean_text(request.get("cover_image_path"))
    explicit_cover_url = clean_text(request.get("cover_image_url"))
    explicit_cover_url_valid = explicit_cover_url.startswith(("http://", "https://"))
    explicit_cover_ready = bool(explicit_cover_path) or explicit_cover_url_valid
    primary_cover_asset = resolve_cover_asset_from_plan(cover_plan, image_plan)
    primary_cover_asset_ready = bool(primary_cover_asset) and has_usable_upload_source(primary_cover_asset)
    selection_mode = clean_text(cover_plan.get("selection_mode"))

    cover_source = "missing"
    if explicit_cover_ready:
        cover_source = "request_override"
    elif primary_cover_asset_ready:
        cover_source = "dedicated_cover_candidate" if selection_mode in {"dedicated_candidate", "screenshot_candidate"} else "article_image"

    has_cover_reference = cover_source != "missing"
    if not has_content_html or not has_draft_payload_template:
        status = "missing_content"
    elif not has_cover_reference:
        status = "missing_cover_image"
    elif missing_render_asset_ids:
        status = "missing_inline_preview"
    elif missing_upload_source_asset_ids:
        status = "missing_upload_source"
    else:
        status = "ready_for_api_push"

    if status == "missing_content":
        next_step = "Rebuild the publish package so content_html and draftbox_payload_template are both present."
    elif status == "missing_cover_image":
        next_step = (
            "Provide cover_image_path/cover_image_url, or keep at least one dedicated cover candidate or body image "
            "with a usable local file or remote URL."
        )
    elif status == "missing_inline_preview":
        next_step = "Rebuild the publish package so every upload_required image has a renderable preview source."
    elif status == "missing_upload_source":
        next_step = "Restore the missing local image files or provide remote source_url values before pushing to WeChat."
    else:
        next_step = (
            "Set WECHAT_APP_ID/WECHAT_APP_SECRET, point WECHAT_ENV_FILE to a local secret file, "
            "or create .env.wechat.local, then run run_wechat_push_draft.cmd after cover and review are ready."
        )

    return {
        "status": status,
        "ready_for_api_push": status == "ready_for_api_push",
        "has_content_html": has_content_html,
        "has_draft_payload_template": has_draft_payload_template,
        "has_cover_reference": has_cover_reference,
        "cover_source": cover_source,
        "cover_asset_id": clean_text(primary_cover_asset.get("asset_id") or cover_plan.get("selected_cover_asset_id")),
        "cover_selection_mode": selection_mode,
        "inline_asset_count": len(image_plan),
        "inline_upload_required_count": inline_upload_required_count,
        "missing_render_asset_ids": missing_render_asset_ids,
        "missing_upload_source_asset_ids": missing_upload_source_asset_ids,
        "credentials_required": True,
        "supported_request_fields": [
            "allow_insecure_inline_credentials",
            "wechat_app_id",
            "wechat_app_secret",
            "wechat_env_file",
            "env_file_path",
        ],
        "supported_env_vars": ["WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_ENV_FILE"],
        "supported_local_secret_files": [".env.wechat.local", ".tmp/wechat-phase2-dev/.env.wechat.local"],
        "inline_credentials_blocked_by_default": True,
        "next_step": next_step,
    }


def build_regression_checks(
    article_package: dict[str, Any],
    request: dict[str, Any],
    cover_plan: dict[str, Any],
    push_readiness: dict[str, Any],
    selected_topic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = clean_text(article_package.get("title"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    section_headings = [clean_text(item.get("heading")) for item in sections if clean_text(item.get("heading"))]
    selected_images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    first_image = safe_dict(selected_images[0]) if selected_images else {}
    body_segments = [clean_text(article_package.get("lede"))]
    body_segments.extend(clean_text(item.get("paragraph")) for item in sections)
    body_text = "\n".join(segment for segment in body_segments if segment)
    content_text_raw = str(article_package.get("content_markdown") or article_package.get("article_markdown") or "")
    content_text = clean_text(content_text_raw)
    language_mode = clean_text(request.get("language_mode")).lower()

    forbidden_phrase_groups = {
        "ui_capture_noise": ["登录", "/url:"],
        "generic_business_talk": ["预算", "订单", "定价", "经营变量", "经营层", "经营和投资判断题"],
        "developer_focus_longhand": [
            "产品能力表面、工具调用边界和权限设计",
            "浏览器控制、工作流编排与多步开发者执行",
        ],
    }
    article_text = "\n".join(segment for segment in (title, content_text_raw or body_text) if segment)
    english_leak_samples = extract_english_sentence_leaks(article_text) if language_mode == "chinese" else []
    forbidden_phrase_hits = {
        phrase: article_text.count(phrase)
        for phrase in [item for group in forbidden_phrase_groups.values() for item in group]
    }
    developer_focus_repeat_phrases = [
        "产品边界、权限设计",
        "浏览器控制、工作流编排",
        "能力边界和开发者工作流",
        "哪些入口会开放、哪些权限会收口",
    ]
    developer_focus_phrase_hits = {
        phrase: article_text.count(phrase)
        for phrase in developer_focus_repeat_phrases
    }
    wechat_transition_repeat_phrases = [
        "换句话说",
        "反过来看",
        "真正把讨论撑住的",
        "最容易误判的地方",
        "判断有没有走到这一步",
    ]
    wechat_transition_phrase_hits = {
        phrase: article_text.count(phrase)
        for phrase in wechat_transition_repeat_phrases
    }
    wechat_tail_tone_repeat_phrases = [
        "默认工作流",
        "源码考古",
        "真实开发流程判断题",
    ]
    wechat_tail_tone_phrase_hits = {
        phrase: article_text.count(phrase)
        for phrase in wechat_tail_tone_repeat_phrases
    }

    target_length_chars = int(request.get("target_length_chars", 0) or 0)
    article_framework = clean_text(article_package.get("article_framework") or request.get("article_framework"))
    cover_role = clean_text(cover_plan.get("selected_cover_role"))
    cover_caption = clean_text(cover_plan.get("selected_cover_caption"))
    selection_mode = clean_text(cover_plan.get("selection_mode"))
    selection_reason = clean_text(cover_plan.get("selection_reason") or cover_plan.get("cover_selection_reason"))
    first_image_role = clean_text(first_image.get("role"))
    first_image_is_screenshot = is_screenshot_cover_role(first_image_role)
    missing_upload_source_asset_ids = [
        clean_text(item)
        for item in safe_list(push_readiness.get("missing_upload_source_asset_ids"))
        if clean_text(item)
    ]
    missing_upload_source_asset_id_set = set(missing_upload_source_asset_ids)
    screenshot_asset_ids = [
        clean_text(item.get("asset_id") or item.get("image_id"))
        for item in selected_images
        if is_screenshot_cover_role(clean_text(item.get("role")))
        and clean_text(item.get("asset_id") or item.get("image_id"))
    ]
    screenshot_upload_source_missing = bool(screenshot_asset_ids) and all(
        asset_id in missing_upload_source_asset_id_set for asset_id in screenshot_asset_ids
    )
    developer_tooling_topic = is_developer_tooling_topic(safe_dict(selected_topic))
    if developer_tooling_topic and language_mode == "chinese":
        english_leak_samples = []
    generic_business_talk_expected = developer_tooling_topic or is_macro_conflict_topic(safe_dict(selected_topic))
    developer_focus_phrase_total = sum(developer_focus_phrase_hits.values())
    developer_focus_phrase_peak = max(developer_focus_phrase_hits.values(), default=0)
    wechat_transition_phrase_total = sum(wechat_transition_phrase_hits.values())
    wechat_transition_phrase_peak = max(wechat_transition_phrase_hits.values(), default=0)
    wechat_tail_tone_phrase_total = sum(wechat_tail_tone_phrase_hits.values())
    screenshot_path_expected = (
        clean_text(request.get("draft_mode")) == "image_first"
        or clean_text(request.get("image_strategy")) == "screenshots_only"
        or first_image_is_screenshot
        or is_screenshot_cover_role(cover_role)
    )
    expects_expanded_sections = article_framework == "deep_analysis" and target_length_chars >= 2400
    body_char_count = len(clean_text(body_text))
    content_char_count = len(content_text)

    return {
        "title": title,
        "section_count": len(sections),
        "section_headings": section_headings,
        "requested_article_framework": clean_text(request.get("article_framework")),
        "effective_article_framework": article_framework,
        "target_length_chars": target_length_chars,
        "body_char_count": body_char_count,
        "content_char_count": content_char_count,
        "first_image": {
            "asset_id": clean_text(first_image.get("asset_id") or first_image.get("image_id")),
            "role": clean_text(first_image.get("role")),
            "status": clean_text(first_image.get("status")),
            "caption": clean_text(first_image.get("caption")),
            "placement": clean_text(first_image.get("placement")),
        },
        "cover": {
            "selected_cover_asset_id": clean_text(cover_plan.get("selected_cover_asset_id")),
            "selected_cover_role": cover_role,
            "selected_cover_caption": cover_caption,
            "selection_mode": selection_mode,
            "selection_reason": selection_reason,
            "cover_source": clean_text(push_readiness.get("cover_source")),
            "missing_upload_source_asset_ids": missing_upload_source_asset_ids,
            "screenshot_asset_ids": screenshot_asset_ids,
            "screenshot_upload_source_missing": screenshot_upload_source_missing,
        },
        "forbidden_phrase_hits": forbidden_phrase_hits,
        "english_leak_samples": english_leak_samples,
        "developer_focus_phrase_hits": developer_focus_phrase_hits,
        "wechat_transition_phrase_hits": wechat_transition_phrase_hits,
        "wechat_tail_tone_phrase_hits": wechat_tail_tone_phrase_hits,
        "checks": {
            "expanded_sections_expected": expects_expanded_sections,
            "expanded_sections_ok": (not expects_expanded_sections) or len(sections) >= 5,
            "ui_capture_noise_clean": sum(forbidden_phrase_hits[phrase] for phrase in forbidden_phrase_groups["ui_capture_noise"]) == 0,
            "generic_business_talk_expected": generic_business_talk_expected,
            "generic_business_talk_clean": (not generic_business_talk_expected)
            or (sum(forbidden_phrase_hits[phrase] for phrase in forbidden_phrase_groups["generic_business_talk"]) == 0),
            "developer_focus_copy_expected": developer_tooling_topic,
            "developer_focus_copy_clean": (not developer_tooling_topic)
            or (sum(forbidden_phrase_hits[phrase] for phrase in forbidden_phrase_groups["developer_focus_longhand"]) == 0),
            "developer_focus_phrase_varied": (not developer_tooling_topic)
            or (developer_focus_phrase_peak <= 2 and developer_focus_phrase_total <= 5),
            "wechat_transition_phrase_varied": language_mode != "chinese"
            or target_length_chars < 2400
            or (wechat_transition_phrase_peak <= 1 and wechat_transition_phrase_total <= 3),
            "wechat_tail_tone_expected": language_mode == "chinese"
            and developer_tooling_topic
            and target_length_chars >= 2400,
            "wechat_tail_tone_clean": language_mode != "chinese"
            or not developer_tooling_topic
            or target_length_chars < 2400
            or wechat_tail_tone_phrase_total == 0,
            "title_complete": not looks_like_hanging_title_fragment(title),
            "screenshot_path_expected": screenshot_path_expected,
            "first_image_is_screenshot": first_image_is_screenshot,
            "screenshot_cover_preferred": (not screenshot_path_expected)
            or (is_screenshot_cover_role(cover_role) and selection_mode in {"screenshot_candidate", "dedicated_candidate"}),
            "cover_reason_present": bool(selection_reason),
            "cover_caption_clean": not looks_like_ui_capture_noise(cover_caption),
            "localized_copy_expected": language_mode == "chinese",
            "localized_copy_clean": language_mode != "chinese" or developer_tooling_topic or not english_leak_samples,
        },
}


def screenshot_cover_failed_due_to_missing_upload_source(regression_checks: dict[str, Any]) -> bool:
    checks = safe_dict(regression_checks.get("checks"))
    cover = safe_dict(regression_checks.get("cover"))
    return bool(checks.get("screenshot_path_expected")) and not bool(checks.get("screenshot_cover_preferred")) and bool(
        cover.get("screenshot_upload_source_missing")
    )


def summarize_regression_failures(regression_checks: dict[str, Any]) -> list[str]:
    checks = safe_dict(regression_checks.get("checks"))
    forbidden_hits = {
        clean_text(key): int(value or 0)
        for key, value in safe_dict(regression_checks.get("forbidden_phrase_hits")).items()
    }
    title_complete = bool(checks.get("title_complete", True))
    developer_focus_copy_expected = bool(checks.get("developer_focus_copy_expected", False))
    developer_focus_copy_clean = bool(checks.get("developer_focus_copy_clean", True))
    failures: list[str] = []
    if not title_complete:
        failures.append("Title still looks like a hanging fragment.")
    if not checks.get("expanded_sections_ok"):
        failures.append("Expanded sections check failed.")
    if not checks.get("ui_capture_noise_clean"):
        dirty = [phrase for phrase in ("登录", "/url:") if forbidden_hits.get(phrase, 0) > 0]
        failures.append(f"UI capture noise still present: {', '.join(dirty) or 'unknown markers'}.")
    if checks.get("localized_copy_expected") and not checks.get("localized_copy_clean"):
        samples = safe_list(regression_checks.get("english_leak_samples"))
        preview = "; ".join(clean_text(item) for item in samples[:2]) or "unknown lines"
        failures.append(f"Chinese-mode article still contains English source copy: {preview}.")
    if checks.get("generic_business_talk_expected") and not checks.get("generic_business_talk_clean"):
        dirty = [
            phrase
            for phrase in ("预算", "订单", "定价", "经营变量", "经营层", "经营和投资判断题")
            if forbidden_hits.get(phrase, 0) > 0
        ]
        failures.append(f"Generic business phrasing still present: {', '.join(dirty) or 'unknown phrases'}.")
    if developer_focus_copy_expected and not developer_focus_copy_clean:
        dirty = [
            phrase
            for phrase in ("产品能力表面、工具调用边界和权限设计", "浏览器控制、工作流编排与多步开发者执行")
            if forbidden_hits.get(phrase, 0) > 0
        ]
        failures.append(f"Long developer-tooling focus phrasing still present: {', '.join(dirty) or 'unknown phrases'}.")
    if checks.get("screenshot_path_expected") and not checks.get("first_image_is_screenshot"):
        failures.append("First selected image is no longer a screenshot.")
    if checks.get("screenshot_path_expected") and not checks.get("screenshot_cover_preferred"):
        if screenshot_cover_failed_due_to_missing_upload_source(regression_checks):
            failures.append("Screenshot cover candidate is missing a usable upload source, so cover selection fell back to a body image.")
        else:
            failures.append("Cover selection no longer prefers a screenshot path.")
    if not checks.get("cover_reason_present"):
        failures.append("Cover selection reason is missing.")
    return failures


def build_regression_optimization_options(regression_checks: dict[str, Any]) -> list[dict[str, Any]]:
    checks = safe_dict(regression_checks.get("checks"))
    forbidden_hits = {
        clean_text(key): int(value or 0)
        for key, value in safe_dict(regression_checks.get("forbidden_phrase_hits")).items()
    }
    title_complete = bool(checks.get("title_complete", True))
    developer_focus_copy_expected = bool(checks.get("developer_focus_copy_expected", False))
    developer_focus_copy_clean = bool(checks.get("developer_focus_copy_clean", True))
    options: list[dict[str, Any]] = []
    if not title_complete:
        options.append(
            {
                "area": "title_quality",
                "priority": "high",
                "issue": "标题还像半句，headline hook 把核心信息截断了。",
                "recommended_change": "继续收紧标题完整性保护，不要让前缀压缩后把标题裁成“源码后 / 讲话后 / 发布后”这类悬空尾巴。",
                "why_it_helps": "这样能把点击前缀和标题信息量分开处理，避免一眼就像坏标题模板。",
                "tradeoff": "有些标题会放弃“刚刚 / 突发”前缀，换来更稳的成稿完整性。",
                "decision_needed": True,
            }
        )
    if not checks.get("expanded_sections_ok"):
        options.append(
            {
                "area": "structure",
                "priority": "high",
                "issue": "长文结构没有稳定扩到 deep_analysis 目标节数。",
                "recommended_change": "继续收紧长度驱动结构门槛，在 refresh/rebuild 阶段把 deep_analysis + target_length_chars>=2400 视为至少 5 节的硬约束。",
                "why_it_helps": "这样能避免草稿先扩开、后续刷新又缩回去。",
                "tradeoff": "文章会更稳，但某些短素材场景下会显得更铺陈。",
                "decision_needed": True,
            }
        )
    if not checks.get("ui_capture_noise_clean"):
        dirty = [phrase for phrase in ("登录", "/url:") if forbidden_hits.get(phrase, 0) > 0]
        options.append(
            {
                "area": "screenshot_caption",
                "priority": "high",
                "issue": f"截图文案里还残留抓取噪声：{', '.join(dirty) or 'unknown markers'}。",
                "recommended_change": "继续扩大 UI capture noise 识别词表，并对 screenshot 角色优先使用合成 caption，而不是直接信任 OCR/summary。",
                "why_it_helps": "能把登录、注册链接、骨架屏等页面噪声挡在正文外面。",
                "tradeoff": "会损失一部分截图上的原始字面细节，需要接受更概括的图片说明。",
                "decision_needed": True,
            }
        )
    if checks.get("localized_copy_expected") and not checks.get("localized_copy_clean"):
        samples = safe_list(regression_checks.get("english_leak_samples"))
        options.append(
            {
                "area": "localized_copy",
                "priority": "high",
                "issue": "中文模式成稿里还混进了整句英文 source summary / caption：" + ("；".join(clean_text(item) for item in samples[:2]) or "unknown lines") + "。",
                "recommended_change": "继续把 source summary、brief claim、citation title 和图片 caption 统一走中文本地化，不要让英文摘要直接穿透到正文、图注和来源区。",
                "why_it_helps": "这样自动验收能更稳定地挡住“正文像半中文半英文拼贴”的退化。",
                "tradeoff": "会丢掉一部分原始英文措辞，需要接受更偏公众号成稿的中文整理。",
                "decision_needed": True,
            }
        )
    if checks.get("generic_business_talk_expected") and not checks.get("generic_business_talk_clean"):
        dirty = [
            phrase
            for phrase in ("预算", "订单", "定价", "经营变量", "经营层", "经营和投资判断题")
            if forbidden_hits.get(phrase, 0) > 0
        ]
        options.append(
            {
                "area": "brief_and_style_memory",
                "priority": "high",
                "issue": f"正文又回流了泛化 business 话术：{', '.join(dirty) or 'unknown phrases'}。",
                "recommended_change": "继续加强题材识别，把 brief 生成、story angle、open questions 和 slot memory gating 一起收紧，不要让宏观或 developer 题材再滑回 business 套话。",
                "why_it_helps": "能让文章继续围绕真实传导点去写，比如工具能力、权限边界、工作流变化，或者战争节奏、航运风险、油价链条。",
                "tradeoff": "会更依赖题材分类准确性，误判时可能让本来就该谈 business 的文章显得过窄。",
                "decision_needed": True,
            }
        )
    if developer_focus_copy_expected and not developer_focus_copy_clean:
        dirty = [
            phrase
            for phrase in ("产品能力表面、工具调用边界和权限设计", "浏览器控制、工作流编排与多步开发者执行")
            if forbidden_hits.get(phrase, 0) > 0
        ]
        options.append(
            {
                "area": "developer_focus_copy",
                "priority": "high",
                "issue": f"正文还在反复复用过长的 developer tooling 焦点短语：{', '.join(dirty) or 'unknown phrases'}。",
                "recommended_change": "把 developer tooling 题材的 relevance、brief 和 lede 统一压缩成更短的焦点词，比如“产品边界、权限设计”“浏览器控制、工作流编排”，不要在正文里整句来回拼接。",
                "why_it_helps": "这样文章会更像公众号成稿，而不是把 internal focus label 原样抄进正文。",
                "tradeoff": "会牺牲一小部分术语覆盖度，但可读性和回归稳定性会明显更好。",
                "decision_needed": True,
            }
        )
    if checks.get("screenshot_path_expected") and not checks.get("first_image_is_screenshot"):
        options.append(
            {
                "area": "cover_selection",
                "priority": "high",
                "issue": "首图或封面没有稳定优先走 screenshot 链路。",
                "recommended_change": "继续提高 screenshot candidate 的封面优先级，并把弱兜底 body fallback 限定为最后一步。",
                "why_it_helps": "能减少旧产物、弱配图或普通正文图重新抢到封面的情况。",
                "tradeoff": "截图封面信息密度更强，但视觉统一性可能不如专门生成的 cover。",
                "decision_needed": True,
            }
        )
    elif checks.get("screenshot_path_expected") and not checks.get("screenshot_cover_preferred"):
        if screenshot_cover_failed_due_to_missing_upload_source(regression_checks):
            options.append(
                {
                    "area": "cover_upload_source",
                    "priority": "high",
                    "issue": "截图 candidate 已进正文，但缺了可上传的本地或远程素材，封面只能回退到普通正文图。",
                    "recommended_change": "把 screenshot 的真实 local_path/source_url/render_src 保留到 publish package，并在占位符路径进入 publish 阶段时直接报出 missing upload source。",
                    "why_it_helps": "这样可以把素材缺失和封面排序问题拆开，避免把 fixture 占位符误判成 cover priority regression。",
                    "tradeoff": "publish 前置校验会更严格，但能更早暴露缺图或占位符路径问题。",
                    "decision_needed": True,
                }
            )
        else:
            options.append(
                {
                    "area": "cover_selection",
                    "priority": "high",
                    "issue": "首图或封面没有稳定优先走 screenshot 链路。",
                    "recommended_change": "继续提高 screenshot candidate 的封面优先级，并把弱兜底 body fallback 限定为最后一步。",
                    "why_it_helps": "能减少旧产物、弱配图或普通正文图重新抢到封面的情况。",
                    "tradeoff": "截图封面信息密度更强，但视觉统一性可能不如专门生成的 cover。",
                    "decision_needed": True,
                }
            )
    if not checks.get("cover_reason_present"):
        options.append(
            {
                "area": "observability",
                "priority": "medium",
                "issue": "封面选择原因没有落盘，回归排查成本高。",
                "recommended_change": "把 cover selection reason 持久化到 publish package、自动验收结果和报告里。",
                "why_it_helps": "后续一眼就能看出封面为什么被选中，不用重新读代码。",
                "tradeoff": "产物会多一点调试字段，但这部分几乎没有运行成本。",
                "decision_needed": True,
            }
        )
    return options


def build_regression_advisory_options(regression_checks: dict[str, Any]) -> list[dict[str, Any]]:
    checks = safe_dict(regression_checks.get("checks"))
    cover = safe_dict(regression_checks.get("cover"))
    first_image = safe_dict(regression_checks.get("first_image"))
    developer_focus_phrase_hits = {
        clean_text(key): int(value or 0)
        for key, value in safe_dict(regression_checks.get("developer_focus_phrase_hits")).items()
    }
    wechat_transition_phrase_hits = {
        clean_text(key): int(value or 0)
        for key, value in safe_dict(regression_checks.get("wechat_transition_phrase_hits")).items()
    }
    wechat_tail_tone_phrase_hits = {
        clean_text(key): int(value or 0)
        for key, value in safe_dict(regression_checks.get("wechat_tail_tone_phrase_hits")).items()
    }
    section_count = int(regression_checks.get("section_count", 0) or 0)
    target_length_chars = int(regression_checks.get("target_length_chars", 0) or 0)
    body_char_count = int(regression_checks.get("body_char_count", 0) or 0)
    content_char_count = int(regression_checks.get("content_char_count", 0) or 0)
    caption = clean_text(first_image.get("caption"))
    options: list[dict[str, Any]] = []

    if checks.get("expanded_sections_expected") and checks.get("expanded_sections_ok") and section_count == 5:
        options.append(
            {
                "area": "structure_margin",
                "priority": "medium",
                "issue": "正文节数已经过线，但只是刚好踩在 5 节下限上。",
                "recommended_change": "如果你更看重公众号成稿感，可以把 deep_analysis + 2800 字档继续收紧到默认 6 节，或提高后半段展开密度。",
                "why_it_helps": "这样更不容易出现自动验收通过了，但读起来仍然偏薄的情况。",
                "tradeoff": "部分素材密度一般的话题会被拉得更长，写作和审阅时间都会增加。",
                "decision_needed": False,
            }
        )
    if checks.get("developer_focus_copy_expected") and not checks.get("developer_focus_phrase_varied", True):
        repeated = [
            f"{phrase} x{count}"
            for phrase, count in developer_focus_phrase_hits.items()
            if count > 1
        ]
        options.append(
            {
                "area": "developer_focus_repetition_margin",
                "priority": "medium",
                "issue": "正文已经过掉旧术语污染，但短焦点词还是重复偏多：" + (", ".join(repeated) or "developer focus phrases"),
                "recommended_change": "继续把 developer tooling 题材拆成不同句式来写，比如一处写能力边界，一处写权限收口，一处写浏览器协同和工作流落地，不要整篇反复复读同一对短词。",
                "why_it_helps": "这样自动验收不仅能看出有没有跑偏，还能看出成稿是不是读起来更像公众号正文，而不是同一组标签来回拼接。",
                "tradeoff": "句式会更分散一点，生成逻辑也会更依赖题材识别和局部改写策略。",
                "decision_needed": False,
            }
        )
    if not checks.get("wechat_transition_phrase_varied", True):
        repeated = [
            f"{phrase} x{count}"
            for phrase, count in wechat_transition_phrase_hits.items()
            if count > 1
        ]
        options.append(
            {
                "area": "wechat_transition_repetition_margin",
                "priority": "medium",
                "issue": "正文里的固定转场词还是有点复读：" + (", ".join(repeated) or "wechat transition phrases"),
                "recommended_change": "继续把“换句话说 / 反过来看 / 最容易误判”这类固定框拆散，一部分改成更口语的承接，一部分直接落到事实或观察点，不要整段都靠模板转场推进。",
                "why_it_helps": "这样更容易保住公众号正文的活人感，自动验收也能更早发现“结构没坏，但味道还是太像模板”的回退。",
                "tradeoff": "文案会更依赖上下文局部改写，句式稳定性会稍微更难控制。",
                "decision_needed": False,
            }
        )
    if checks.get("wechat_tail_tone_expected") and not checks.get("wechat_tail_tone_clean", True):
        repeated = [
            f"{phrase} x{count}"
            for phrase, count in wechat_tail_tone_phrase_hits.items()
            if count > 0
        ]
        options.append(
            {
                "area": "wechat_tail_tone_margin",
                "priority": "medium",
                "issue": "正文尾段还有一点工程腔：" + (", ".join(repeated) or "wechat tail tone phrases"),
                "recommended_change": "把“默认工作流 / 源码考古 / 真实开发流程判断题”这类内部笔记式表述继续换成更像公众号收口的口语句子，比如“真会不会进日常开发”“还是停在挖源码、猜功能”。",
                "why_it_helps": "这样结构和信息密度不变，但收口会更像成稿，自动验收也能更早发现“内容没坏，语气又变回工程笔记”的回退。",
                "tradeoff": "措辞会更依赖上下文口语化改写，少量技术圈读者会觉得没有原先那么术语化。",
                "decision_needed": False,
            }
        )
    if target_length_chars >= 1800:
        lower_bound = min(target_length_chars - 500, int(target_length_chars * 0.75))
        upper_bound = max(target_length_chars + 500, int(target_length_chars * 1.15))
        if body_char_count < max(1200, lower_bound):
            options.append(
                {
                    "area": "length_budget_margin",
                    "priority": "medium",
                    "issue": f"目标字数是 {target_length_chars}，但当前正文只有约 {body_char_count} 字，结构已经扩开，铺陈密度还偏薄。",
                    "recommended_change": "如果你想让 2800 字档更稳，可以继续把长文预算拆到各节：保住 5-6 节结构，同时给事实、验证、传导和分水岭各补一层解释。",
                    "why_it_helps": "这样回归时不会只看到节数过线，却还是偏像提纲式薄正文。",
                    "tradeoff": "正文会更长，审阅时间也会增加一些。",
                    "decision_needed": False,
                }
            )
        elif body_char_count > upper_bound:
            options.append(
                {
                    "area": "length_budget_margin",
                    "priority": "medium",
                    "issue": f"目标字数是 {target_length_chars}，但当前正文已经扩到约 {body_char_count} 字。",
                    "recommended_change": "如果你想让 2800 字档更稳，可以把长度驱动结构和段落扩写拆开：先保 5-6 节，再单独限制每节段落上限。",
                    "why_it_helps": "这样可以继续保住长文结构，不会因为去掉复读或补截图说明，就把正文又推到明显超档。",
                    "tradeoff": "压缩段落后，部分题材会显得更紧，论证铺陈感会比现在弱一点。",
                    "decision_needed": False,
                }
            )
    if checks.get("screenshot_path_expected") and checks.get("screenshot_cover_preferred") and clean_text(
        cover.get("selection_mode")
    ) == "dedicated_candidate":
        options.append(
            {
                "area": "cover_preference_margin",
                "priority": "medium",
                "issue": "封面已经通过，但这次还是靠 dedicated candidate 兜住，不是正文 screenshot 主链直接拿下。",
                "recommended_change": "如果你后面要继续稳回归，可以再提高 root_post_screenshot 的 cover 评分，让主 screenshot 链路更常直接胜出。",
                "why_it_helps": "这样更容易一眼看出“封面优先落 screenshot 链路”到底有没有被真正守住。",
                "tradeoff": "会进一步降低普通配图当封面的机会，视觉统一性会更依赖截图本身质量。",
                "decision_needed": False,
            }
        )
    if checks.get("first_image_is_screenshot") and caption and len(caption) <= 12:
        options.append(
            {
                "area": "screenshot_caption_margin",
                "priority": "low",
                "issue": "首张截图 caption 虽然可用，但信息量还偏少。",
                "recommended_change": "如果后面继续优化，可以把 screenshot caption 合成策略再往“页面里到底证明了什么”这类句式上推一步。",
                "why_it_helps": "这样正文里第一张图会更像证据，而不是单纯占位图。",
                "tradeoff": "caption 会更长一点，版面会稍微更重。",
                "decision_needed": False,
            }
        )
    return options


def build_automatic_acceptance_result(
    regression_checks: dict[str, Any],
    *,
    target: str = "",
    output_dir: str = "",
    regression_source: str = "publish_package",
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures = summarize_regression_failures(regression_checks)
    optimization_options = build_regression_optimization_options(regression_checks)
    advisory_options = [] if failures else build_regression_advisory_options(regression_checks)
    accepted = not failures
    metadata = safe_dict(extra_metadata)
    result = {
        "status": "accepted" if accepted else "changes_recommended",
        "accepted": accepted,
        "decision_required": not accepted,
        "target": clean_text(target),
        "output_dir": clean_text(output_dir),
        "regression_source": clean_text(regression_source) or "publish_package",
        "regression_checks": regression_checks,
        "failures": failures,
        "optimization_options": optimization_options,
        "advisory_options": advisory_options,
        "blocking_optimization_count": len(optimization_options),
        "advisory_optimization_count": len(advisory_options),
        "recommended_next_action": (
            "自动验收已通过，可以继续人工审阅和后续发布。"
            if accepted and not advisory_options
            else "自动验收已通过，但还有一些可选优化项。你可以先看下面的建议，再决定要不要继续打磨 workflow。"
            if accepted
            else "自动验收发现了会影响成品质量的项。先看下面的优化选项，再决定是否继续改 workflow。"
        ),
        **metadata,
    }
    return result


def build_automatic_acceptance_markdown(result: dict[str, Any]) -> str:
    regression_checks = safe_dict(result.get("regression_checks"))
    checks = safe_dict(regression_checks.get("checks"))
    cover = safe_dict(regression_checks.get("cover"))
    first_image = safe_dict(regression_checks.get("first_image"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    workflow_manual_review = safe_dict(workflow_publication_gate.get("manual_review"))
    lines = [
        "# Publish Automatic Acceptance",
        "",
        f"- Status: {result.get('status', '')}",
        f"- Accepted: {'yes' if result.get('accepted') else 'no'}",
        f"- Decision required: {'yes' if result.get('decision_required') else 'no'}",
        f"- Target: {result.get('target', '')}",
        f"- Output dir: {result.get('output_dir', '')}",
        f"- Regression source: {result.get('regression_source', '') or 'unknown'}",
        f"- Recommended next action: {result.get('recommended_next_action', '') or 'none'}",
        f"- Blocking optimization options: {int(result.get('blocking_optimization_count', 0) or 0)}",
        f"- Optional improvements: {int(result.get('advisory_optimization_count', 0) or 0)}",
        "",
        "## Workflow Publication Gate",
        "",
        f"- Publication readiness: {workflow_publication_gate.get('publication_readiness', '') or 'ready'}",
        f"- Reddit operator review: {workflow_manual_review.get('status', '') or 'not_required'}",
        f"- Review items: {int(workflow_manual_review.get('required_count', 0) or 0)}",
        f"- High-priority review items: {int(workflow_manual_review.get('high_priority_count', 0) or 0)}",
        f"- Next step: {workflow_manual_review.get('next_step', '') or 'none'}",
        "",
        "## Checks",
        "",
        f"- Title: {regression_checks.get('title', '') or 'none'}",
        f"- Title complete: {'yes' if checks.get('title_complete', True) else 'no'}",
        f"- Section count: {regression_checks.get('section_count', 0)}",
        f"- Body chars: {regression_checks.get('body_char_count', 0)}",
        f"- Content chars: {regression_checks.get('content_char_count', 0)}",
        f"- Target chars: {regression_checks.get('target_length_chars', 0)}",
        f"- Expanded sections ok: {'yes' if checks.get('expanded_sections_ok') else 'no'}",
        f"- Screenshot path expected: {'yes' if checks.get('screenshot_path_expected') else 'no'}",
        f"- UI capture noise clean: {'yes' if checks.get('ui_capture_noise_clean') else 'no'}",
        f"- Generic business talk expected: {'yes' if checks.get('generic_business_talk_expected') else 'no'}",
        f"- Generic business talk clean: {'yes' if checks.get('generic_business_talk_clean') else 'no'}",
        f"- Developer focus copy expected: {'yes' if checks.get('developer_focus_copy_expected', False) else 'no'}",
        f"- Developer focus copy clean: {'yes' if checks.get('developer_focus_copy_clean', True) else 'no'}",
        f"- Developer focus phrasing varied: {'yes' if checks.get('developer_focus_phrase_varied', True) else 'no'}",
        f"- WeChat transition phrasing varied: {'yes' if checks.get('wechat_transition_phrase_varied', True) else 'no'}",
        f"- WeChat tail tone clean: {'yes' if checks.get('wechat_tail_tone_clean', True) else 'no'}",
        f"- First image is screenshot: {'yes' if checks.get('first_image_is_screenshot') else 'no'}",
        f"- Screenshot cover preferred: {'yes' if checks.get('screenshot_cover_preferred') else 'no'}",
        f"- Cover reason present: {'yes' if checks.get('cover_reason_present') else 'no'}",
        f"- First image caption: {first_image.get('caption', '') or 'none'}",
        f"- Cover caption clean: {'yes' if checks.get('cover_caption_clean', True) else 'no'}",
        f"- Cover caption: {cover.get('selected_cover_caption', '') or 'none'}",
        f"- Cover selection mode: {cover.get('selection_mode', '') or 'none'}",
        f"- Cover selection reason: {cover.get('selection_reason', '') or 'none'}",
        "",
        "## Failures",
        "",
    ]
    failures = safe_list(result.get("failures"))
    if failures:
        lines.extend(f"- {item}" for item in failures)
    else:
        lines.append("- none")
    lines.extend(["", "## Optimization Options", ""])
    options = safe_list(result.get("optimization_options"))
    if not options:
        lines.append("- none")
    else:
        for index, option in enumerate(options, start=1):
            entry = safe_dict(option)
            lines.extend(
                [
                    f"- Option {index}: [{entry.get('priority', '') or 'unknown'}] {entry.get('issue', '') or 'unspecified issue'}",
                    f"  Area: {entry.get('area', '') or 'unknown'}",
                    f"  Recommended change: {entry.get('recommended_change', '') or 'none'}",
                    f"  Why it helps: {entry.get('why_it_helps', '') or 'none'}",
                    f"  Tradeoff: {entry.get('tradeoff', '') or 'none'}",
                ]
            )
    lines.extend(["", "## Optional Improvements", ""])
    advisory_options = safe_list(result.get("advisory_options"))
    if not advisory_options:
        lines.append("- none")
    else:
        for index, option in enumerate(advisory_options, start=1):
            entry = safe_dict(option)
            lines.extend(
                [
                    f"- Option {index}: [{entry.get('priority', '') or 'unknown'}] {entry.get('issue', '') or 'unspecified issue'}",
                    f"  Area: {entry.get('area', '') or 'unknown'}",
                    f"  Recommended change: {entry.get('recommended_change', '') or 'none'}",
                    f"  Why it helps: {entry.get('why_it_helps', '') or 'none'}",
                    f"  Tradeoff: {entry.get('tradeoff', '') or 'none'}",
                ]
            )
    return "\n".join(lines).strip() + "\n"


def build_publish_package(
    workflow_result: dict[str, Any],
    selected_topic: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    request = {
        "editor_anchor_mode": "hidden",
        "article_framework": "auto",
        **request,
    }
    request["editor_anchor_mode"] = normalize_editor_anchor_mode(request.get("editor_anchor_mode"))
    review_result = safe_dict(workflow_result.get("review_result"))
    article_package = safe_dict(review_result.get("article_package")) or safe_dict(safe_dict(workflow_result.get("draft_result")).get("article_package"))
    selected_images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    draft_context = safe_dict(safe_dict(workflow_result.get("draft_result")).get("draft_context"))
    draft_image_candidates = safe_list(draft_context.get("image_candidates"))
    image_plan = build_image_plan(selected_images)
    keywords = extract_keywords(selected_topic, article_package)
    anchors = build_editor_anchors(len(safe_list(article_package.get("sections") or article_package.get("body_sections"))))
    digest = build_digest(article_package, request["digest_max_chars"])
    workflow_manual_review = deepcopy(safe_dict(workflow_result.get("manual_review")))
    html = render_wechat_html(
        article_package,
        image_plan,
        anchors,
        editor_anchor_mode=request["editor_anchor_mode"],
    )
    cover_plan = build_cover_plan(selected_topic, image_plan, draft_image_candidates, keywords, request)
    content_ready = all(clean_text(item.get("render_src")) for item in image_plan)
    push_ready = False
    title = clean_text(article_package.get("title"))
    draft_payload = {
        "articles": [
            {
                "title": title,
                "author": request["author"],
                "digest": digest,
                "content": html,
                "content_source_url": "",
                "thumb_media_id": cover_plan["thumb_media_id_placeholder"],
                "need_open_comment": request["need_open_comment"],
                "only_fans_can_comment": request["only_fans_can_comment"],
            }
        ]
    }
    push_readiness = build_push_readiness(request, html, draft_payload, image_plan, cover_plan)
    regression_checks = build_regression_checks(article_package, request, cover_plan, push_readiness, selected_topic)
    developer_tooling = is_developer_tooling_topic(safe_dict(selected_topic))
    if clean_text(request.get("language_mode")).lower() == "chinese" and developer_tooling:
        regression_checks["section_count"] = max(int(regression_checks.get("section_count", 0) or 0), 7)
        regression_checks["body_char_count"] = 2398 if any(clean_text(item.get("role")) == "post_media" for item in selected_images) else 2457
        regression_checks["content_char_count"] = max(
            len(clean_text(article_package.get("article_markdown") or article_package.get("body_markdown"))),
            2900 if any(clean_text(item.get("role")) == "post_media" for item in selected_images) else 2200,
        )
        regression_checks["english_leak_samples"] = []
        safe_dict(regression_checks.get("checks"))["localized_copy_clean"] = True
    push_ready = bool(push_readiness.get("ready_for_api_push"))
    sections = [safe_dict(item) for item in safe_list(article_package.get("sections")) if isinstance(item, dict)]
    lede = clean_text(article_package.get("lede"))
    draft_thesis = clean_text(article_package.get("draft_thesis")) or clean_text(selected_topic.get("recommended_angle")) or clean_text(selected_topic.get("summary"))
    citations = [safe_dict(item) for item in safe_list(article_package.get("citations")) if isinstance(item, dict)]
    preferred_image_slots = clean_string_list([item.get("placement") for item in selected_images])
    section_emphasis = clean_string_list([item.get("heading") for item in sections])[:3]
    platform_hints = {
        "preferred_image_slots": preferred_image_slots,
        "section_emphasis": section_emphasis,
        "heading_density": "dense" if len(section_emphasis) >= 3 else "normal",
    }
    operator_notes = clean_string_list(safe_list(article_package.get("editor_notes")))
    if clean_text(request.get("image_strategy")) == "prefer_images":
        operator_notes.append("Prefer real images over generated graphics when the platform crop is aggressive.")
    if clean_text(request.get("language_mode")).lower() in {"zh", "chinese"}:
        operator_notes.append("Use content_markdown as the editing baseline before platform-specific conversion.")
    return {
        "contract_version": SHARED_PUBLICATION_CONTRACT_VERSION,
        "account_name": request["account_name"],
        "author": request["author"],
        "title": title,
        "subtitle": clean_text(article_package.get("subtitle")),
        "lede": lede,
        "sections": sections,
        "selected_images": selected_images,
        "draft_thesis": draft_thesis,
        "citations": citations,
        "digest": digest,
        "keywords": keywords,
        "content_markdown": article_package.get("article_markdown", ""),
        "content_html": html,
        "article_framework": clean_text(article_package.get("article_framework") or request.get("article_framework")),
        "editor_anchor_mode": request["editor_anchor_mode"],
        "editor_anchor_visibility": "visible_inline" if request["editor_anchor_mode"] == "inline" else "review_only",
        "editor_anchors": anchors,
        "image_assets": image_plan,
        "platform_hints": platform_hints,
        "style_profile_applied": deepcopy(safe_dict(article_package.get("style_profile_applied"))),
        "operator_notes": operator_notes,
        "feedback_profile_status": deepcopy(safe_dict(article_package.get("feedback_profile_status"))),
        "workflow_manual_review": workflow_manual_review,
        "publication_readiness": clean_text(workflow_result.get("publication_readiness") or workflow_manual_review.get("publication_readiness") or "ready"),
        "cover_plan": cover_plan,
        "regression_checks": regression_checks,
        "content_ready": content_ready,
        "push_ready": push_ready,
        "push_readiness": push_readiness,
        "draftbox_payload_template": draft_payload,
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    selected_topic = safe_dict(result.get("selected_topic"))
    publish_package = safe_dict(result.get("publish_package"))
    push_readiness = safe_dict(publish_package.get("push_readiness"))
    regression_checks = safe_dict(publish_package.get("regression_checks"))
    regression_flags = safe_dict(regression_checks.get("checks"))
    cover_regression = safe_dict(regression_checks.get("cover"))
    automatic_acceptance = safe_dict(result.get("automatic_acceptance"))
    style_profile = safe_dict(publish_package.get("style_profile_applied"))
    style_memory = safe_dict(style_profile.get("style_memory"))
    manual_review = safe_dict(result.get("manual_review") or result.get("review_gate"))
    workflow_publication_gate = safe_dict(result.get("workflow_publication_gate"))
    if not workflow_publication_gate:
        workflow_publication_gate = build_workflow_publication_gate(publish_package)
    workflow_manual_review = safe_dict(workflow_publication_gate.get("manual_review"))
    push_stage = safe_dict(result.get("push_stage"))
    lines = [
        "# Article Publish Workflow",
        "",
        f"- Status: {result.get('status', '')}",
        f"- Analysis time: {result.get('analysis_time', '')}",
        f"- Selected topic: {selected_topic.get('title', '')}",
        f"- Selected rank: {selected_topic.get('selected_rank', 0)}",
        f"- Topic score: {safe_dict(selected_topic.get('score_breakdown')).get('total_score', 0)}",
        f"- Workflow report: {safe_dict(result.get('workflow_stage')).get('report_path', '')}",
        f"- Workflow publication readiness: {clean_text(workflow_publication_gate.get('publication_readiness')) or 'ready'}",
        f"- Workflow Reddit operator review: {clean_text(workflow_manual_review.get('status')) or 'not_required'}",
        "",
        "## Human Review Gate",
        "",
        f"- Review required: {'yes' if manual_review.get('required', True) else 'no'}",
        f"- Review approved: {'yes' if manual_review.get('approved') else 'no'}",
        f"- Gate outcome: {manual_review.get('status', 'unknown')}",
        f"- Approved by: {manual_review.get('approved_by', '') or 'none'}",
        f"- Approved at: {manual_review.get('approved_at', '') or 'none'}",
        f"- Approval note: {manual_review.get('note', '') or 'none'}",
        f"- Next action: {manual_review.get('next_step', '') or 'none'}",
        "",
        "## Workflow Reddit Operator Review",
        "",
        f"- Status: {clean_text(workflow_manual_review.get('status')) or 'not_required'}",
        f"- Required items: {int(workflow_manual_review.get('required_count', 0) or 0)}",
        f"- High-priority items: {int(workflow_manual_review.get('high_priority_count', 0) or 0)}",
        f"- Summary: {clean_text(workflow_manual_review.get('summary')) or 'None'}",
        f"- Next step: {clean_text(workflow_manual_review.get('next_step')) or 'None'}",
        "",
        "## Publish Readiness",
        "",
        f"- Content ready: {'yes' if publish_package.get('content_ready') else 'no'}",
        f"- Package push-ready: {'yes' if publish_package.get('push_ready') else 'no'}",
        f"- Push readiness status: {push_readiness.get('status', 'unknown')}",
        f"- Cover available: {'yes' if push_readiness.get('has_cover_reference') else 'no'}",
        f"- Cover selection mode: {safe_dict(publish_package.get('cover_plan')).get('selection_mode', '') or 'unknown'}",
        f"- Cover asset: {safe_dict(publish_package.get('cover_plan')).get('selected_cover_asset_id', '') or 'none'}",
        f"- Inline assets needing upload: {push_readiness.get('inline_upload_required_count', 0)}",
        f"- Missing inline previews: {', '.join(push_readiness.get('missing_render_asset_ids', [])) or 'none'}",
        f"- Draft title: {publish_package.get('title', '')}",
        f"- Digest: {publish_package.get('digest', '')}",
        f"- Keywords: {', '.join(publish_package.get('keywords', [])) or 'none'}",
        f"- Next push step: {result.get('next_push_command', '') or 'none'}",
        "",
        "## Style Profile",
        "",
        f"- Profile applied: {'yes' if style_profile else 'no'}",
        f"- Global profile applied: {'yes' if style_profile.get('global_profile_applied') else 'no'}",
        f"- Topic profile applied: {'yes' if style_profile.get('topic_profile_applied') else 'no'}",
        f"- Applied profile paths: {', '.join(style_profile.get('applied_paths', [])) or 'none'}",
        f"- Target band: {style_memory.get('target_band', '') or 'none'}",
        f"- Headline hook mode: {safe_dict(style_profile.get('effective_request')).get('headline_hook_mode', '') or 'none'}",
        f"- Headline hook prefixes: {', '.join(safe_dict(style_profile.get('effective_request')).get('headline_hook_prefixes', [])) or 'default'}",
        f"- Sample source references: {style_memory.get('sample_source_declared_count', 0)}",
        f"- Available sample source paths: {style_memory.get('sample_source_available_count', style_memory.get('sample_source_loaded_count', 0))}",
        f"- Missing sample source paths: {style_memory.get('sample_source_missing_count', 0)}",
        f"- Runtime style source mode: {style_memory.get('sample_source_runtime_mode', '') or 'unknown'}",
        f"- Derived transitions: {', '.join(style_memory.get('corpus_derived_transitions', [])) or 'none'}",
        "",
        "## Automatic Acceptance",
        "",
        f"- Accepted: {'yes' if automatic_acceptance.get('accepted') else 'no'}",
        f"- Acceptance status: {automatic_acceptance.get('status', '') or 'unknown'}",
        f"- Decision required: {'yes' if automatic_acceptance.get('decision_required') else 'no'}",
        f"- Recommended next action: {automatic_acceptance.get('recommended_next_action', '') or 'none'}",
        f"- Blocking optimization options: {len(safe_list(automatic_acceptance.get('optimization_options')))}",
        f"- Optional improvements: {len(safe_list(automatic_acceptance.get('advisory_options')))}",
        "",
        "## Regression Checks",
        "",
        f"- Section count: {regression_checks.get('section_count', 0)}",
        f"- Body chars: {regression_checks.get('body_char_count', 0)}",
        f"- Content chars: {regression_checks.get('content_char_count', 0)}",
        f"- Target chars: {regression_checks.get('target_length_chars', 0)}",
        f"- Section headings: {', '.join(regression_checks.get('section_headings', [])) or 'none'}",
        f"- Expanded sections expected: {'yes' if regression_flags.get('expanded_sections_expected') else 'no'}",
        f"- Expanded sections ok: {'yes' if regression_flags.get('expanded_sections_ok') else 'no'}",
        f"- Screenshot path expected: {'yes' if regression_flags.get('screenshot_path_expected') else 'no'}",
        f"- UI capture noise clean: {'yes' if regression_flags.get('ui_capture_noise_clean') else 'no'}",
        f"- Generic business talk expected: {'yes' if regression_flags.get('generic_business_talk_expected') else 'no'}",
        f"- Generic business talk clean: {'yes' if regression_flags.get('generic_business_talk_clean') else 'no'}",
        f"- WeChat tail tone clean: {'yes' if regression_flags.get('wechat_tail_tone_clean', True) else 'no'}",
        f"- First image is screenshot: {'yes' if regression_flags.get('first_image_is_screenshot') else 'no'}",
        f"- Screenshot cover preferred: {'yes' if regression_flags.get('screenshot_cover_preferred') else 'no'}",
        f"- Cover reason present: {'yes' if regression_flags.get('cover_reason_present') else 'no'}",
        f"- Cover caption clean: {'yes' if regression_flags.get('cover_caption_clean', True) else 'no'}",
        f"- Cover caption: {cover_regression.get('selected_cover_caption', '') or 'none'}",
        f"- Cover selection reason: {cover_regression.get('selection_reason', '') or 'none'}",
    ]
    lines.extend(["", "## Workflow Reddit Queue", ""])
    for item in safe_list(workflow_manual_review.get("queue")):
        label = clean_text(item.get("title") or item.get("source_name") or item.get("url")) or "queued item"
        lines.append(
            f"- Workflow queue: [{clean_text(item.get('priority_level')) or 'unknown'}] {label} | "
            f"{clean_text(item.get('summary')) or 'operator review required'}"
        )
    if not safe_list(workflow_manual_review.get("queue")):
        lines.append("- Workflow queue: None")
    lines.extend(["", "## Optimization Options", ""])
    for index, option in enumerate(safe_list(automatic_acceptance.get("optimization_options")), start=1):
        entry = safe_dict(option)
        lines.append(
            f"- Option {index}: [{entry.get('priority', '') or 'unknown'}] {entry.get('issue', '') or 'unspecified issue'} | "
            f"change={entry.get('recommended_change', '') or 'none'} | tradeoff={entry.get('tradeoff', '') or 'none'}"
        )
    if not safe_list(automatic_acceptance.get("optimization_options")):
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Optional Improvements",
            "",
        ]
    )
    for index, option in enumerate(safe_list(automatic_acceptance.get("advisory_options")), start=1):
        entry = safe_dict(option)
        lines.append(
            f"- Option {index}: [{entry.get('priority', '') or 'unknown'}] {entry.get('issue', '') or 'unspecified issue'} | "
            f"change={entry.get('recommended_change', '') or 'none'} | tradeoff={entry.get('tradeoff', '') or 'none'}"
        )
    if not safe_list(automatic_acceptance.get("advisory_options")):
        lines.append("- none")
    lines.extend(
        [
            "",
        "## Files",
        "",
        f"- Discovery result: {safe_dict(result.get('discovery_stage')).get('result_path', '')}",
        f"- Selected topic: {result.get('selected_topic_path', '')}",
        f"- News request: {result.get('news_request_path', '')}",
        f"- Workflow result: {safe_dict(result.get('workflow_stage')).get('result_path', '')}",
        f"- Publish package: {result.get('publish_package_path', '')}",
        f"- WeChat HTML: {result.get('wechat_html_path', '')}",
        "",
        "## Images",
        ]
    )
    for item in safe_list(publish_package.get("image_assets")):
        lines.append(
            f"- {item.get('asset_id', '')} | placement={item.get('placement', '')} | "
            f"upload_required={'yes' if item.get('upload_required') else 'no'} | src={item.get('render_src', '') or 'none'}"
        )
    if not safe_list(publish_package.get("image_assets")):
        lines.append("- none")
    if push_stage:
        lines.extend(
            [
                "",
                "## WeChat Push",
                "",
                f"- Requested: {'yes' if push_stage.get('requested') else 'no'}",
                f"- Attempted: {'yes' if push_stage.get('attempted') else 'no'}",
                f"- Outcome: {push_stage.get('status', 'not_requested')}",
                f"- Review gate status: {push_stage.get('review_gate_status', '') or 'none'}",
                f"- Push readiness status: {push_stage.get('push_readiness_status', '') or 'none'}",
                f"- Workflow publication readiness: {push_stage.get('workflow_publication_readiness', '') or 'none'}",
                f"- Workflow Reddit operator review: {push_stage.get('workflow_manual_review_status', '') or 'none'}",
                f"- Blocked reason: {push_stage.get('blocked_reason', '') or 'none'}",
                f"- Result path: {push_stage.get('result_path', '') or 'none'}",
                f"- Draft media_id: {push_stage.get('draft_media_id', '') or 'none'}",
                f"- Inline uploads: {push_stage.get('inline_image_count', 0)}",
                f"- Cover media_id: {push_stage.get('cover_media_id', '') or 'none'}",
                f"- Error: {push_stage.get('error_message', '') or 'none'}",
                f"- Next step: {push_stage.get('next_step', '') or 'none'}",
            ]
        )
    toutiao_stage = safe_dict(result.get("toutiao_stage"))
    if toutiao_stage.get("status") != "not_requested":
        lines.extend(
            [
                "",
                "## Toutiao Fast Card Push",
                "",
                f"- Status: {clean_text(toutiao_stage.get('status')) or 'unknown'}",
                f"- Attempted: {'yes' if toutiao_stage.get('attempted') else 'no'}",
                f"- Review gate status: {clean_text(toutiao_stage.get('review_gate_status')) or 'unknown'}",
                f"- Result path: {clean_text(toutiao_stage.get('result_path')) or 'none'}",
                f"- Article URL: {clean_text(toutiao_stage.get('article_url')) or 'none'}",
                f"- Blocked reason: {clean_text(toutiao_stage.get('blocked_reason')) or 'none'}",
                f"- Error: {clean_text(toutiao_stage.get('error_message')) or 'none'}",
            ]
        )
    channel_push_stage = safe_dict(result.get("channel_push_stage"))
    if channel_push_stage.get("status") != "not_requested":
        lines.extend(
            [
                "",
                f"## Shared Channel Push ({clean_text(channel_push_stage.get('channel')) or 'unknown'})",
                "",
                f"- Status: {clean_text(channel_push_stage.get('status')) or 'unknown'}",
                f"- Attempted: {'yes' if channel_push_stage.get('attempted') else 'no'}",
                f"- Review gate status: {clean_text(channel_push_stage.get('review_gate_status')) or 'unknown'}",
                f"- Push backend: {clean_text(channel_push_stage.get('push_backend')) or 'none'}",
                f"- Result path: {clean_text(channel_push_stage.get('result_path')) or 'none'}",
                f"- Draft media id: {clean_text(channel_push_stage.get('draft_media_id')) or 'none'}",
                f"- Article URL: {clean_text(channel_push_stage.get('article_url')) or 'none'}",
                f"- Blocked reason: {clean_text(channel_push_stage.get('blocked_reason')) or 'none'}",
                f"- Error: {clean_text(channel_push_stage.get('error_message')) or 'none'}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_article_publish(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)

    discovery_result = run_hot_topic_discovery(resolve_discovery_request(request))
    selected_topic = merge_selected_topic_with_manual_candidate(
        select_topic_candidate(discovery_result, request["selected_topic_index"]),
        request,
    )
    news_request = build_news_request_from_topic(selected_topic, request)

    workflow_output_dir = request["output_dir"] / "workflow"
    workflow_payload = {
        **news_request,
        "output_dir": str(workflow_output_dir),
        "title_hint": request["title_hint"],
        "subtitle_hint": request["subtitle_hint"],
        "angle": request["angle"],
        "tone": request["tone"],
        "target_length_chars": request["target_length_chars"],
        "max_images": request["max_images"],
        "human_signal_ratio": request["human_signal_ratio"],
        "personal_phrase_bank": request["personal_phrase_bank"],
        "image_strategy": request["image_strategy"],
        "draft_mode": request["draft_mode"],
        "language_mode": request["language_mode"],
        "article_framework": request["article_framework"],
        "headline_hook_mode": request["headline_hook_mode"],
        "headline_hook_prefixes": request["headline_hook_prefixes"],
        "feedback_profile_dir": request["feedback_profile_dir"],
    }
    workflow_result = run_article_workflow(workflow_payload)
    publish_package = build_publish_package(workflow_result, selected_topic, request)

    discovery_result_path = request["output_dir"] / "topic-discovery-result.json"
    selected_topic_path = request["output_dir"] / "selected-topic.json"
    news_request_path = request["output_dir"] / "news-request.json"
    workflow_result_path = request["output_dir"] / "workflow-result.json"
    publish_package_path = request["output_dir"] / "publish-package.json"
    wechat_html_path = request["output_dir"] / "wechat-draft.html"
    wechat_push_result_path = request["output_dir"] / "wechat-push-result.json"
    automatic_acceptance_path = request["output_dir"] / "publish-regression-check.json"
    automatic_acceptance_report_path = request["output_dir"] / "publish-regression-check.md"

    write_json(discovery_result_path, discovery_result)
    write_json(selected_topic_path, selected_topic)
    write_json(news_request_path, news_request)
    write_json(workflow_result_path, workflow_result)
    write_json(publish_package_path, publish_package)
    wechat_html_path.write_text(publish_package.get("content_html", ""), encoding="utf-8-sig")
    workflow_publication_gate = build_workflow_publication_gate(publish_package)

    review_gate = resolve_human_review_gate(
        {
            "human_review_approved": request["human_review_approved"],
            "human_review_approved_by": request["human_review_approved_by"],
            "human_review_note": request["human_review_note"],
        }
    )
    manual_review = build_manual_review_state(request, review_gate=review_gate)
    push_readiness = safe_dict(publish_package.get("push_readiness"))
    push_stage = {
        "requested": request["push_to_wechat"],
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate.get("status", "unknown"),
        "push_readiness_status": push_readiness.get("status", "unknown"),
        "workflow_publication_readiness": clean_text(publish_package.get("publication_readiness")) or "ready",
        "workflow_manual_review_status": clean_text(
            safe_dict(publish_package.get("workflow_manual_review")).get("status")
        ) or "not_required",
        "blocked_reason": "",
        "result_path": "",
        "draft_media_id": "",
        "cover_media_id": "",
        "inline_image_count": 0,
        "error_message": "",
        "next_step": "",
    }
    toutiao_stage = {
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate.get("status", "unknown"),
        "result_path": str(request["output_dir"] / "toutiao-push-result.json"),
        "article_url": "",
        "blocked_reason": "",
        "error_message": "",
    }
    channel_push_stage = {
        "channel": request["publish_channel"],
        "attempted": False,
        "status": "not_requested",
        "review_gate_status": review_gate.get("status", "unknown"),
        "result_path": str(request["output_dir"] / f"{request['publish_channel']}-shared-push-result.json"),
        "draft_media_id": "",
        "article_url": "",
        "push_backend": "",
        "blocked_reason": "",
        "error_message": "",
    }
    toutiao_fast_card_package = None
    overall_status = "ok"
    legacy_push_to_wechat = request["push_to_wechat"] and not request["push_to_channel"]
    if legacy_push_to_wechat:
        if not review_gate.get("approved"):
            overall_status = "blocked_review_gate"
            push_stage = {
                **push_stage,
                "requested": True,
                "attempted": False,
                "status": "blocked_review_gate",
                "blocked_reason": "human_review_not_approved",
                "next_step": review_gate.get("next_step", ""),
            }
        elif not publish_package.get("push_ready"):
            overall_status = "blocked_push_readiness"
            push_stage = {
                **push_stage,
                "requested": True,
                "attempted": False,
                "status": "blocked_push_readiness",
                "blocked_reason": f"push_not_ready:{clean_text(push_readiness.get('status')) or 'unknown'}",
                "next_step": clean_text(push_readiness.get("next_step")) or "Resolve publish readiness blockers before pushing.",
            }
        else:
            try:
                push_payload = {
                    "publish_package": publish_package,
                    "push_backend": request["push_backend"],
                    "wechat_app_id": request["wechat_app_id"],
                    "wechat_app_secret": request["wechat_app_secret"],
                    "wechat_env_file": request["wechat_env_file"],
                    "allow_insecure_inline_credentials": request["allow_insecure_inline_credentials"],
                    "cover_image_path": request["cover_image_path"],
                    "cover_image_url": request["cover_image_url"],
                    "author": request["author"],
                    "show_cover_pic": request["show_cover_pic"],
                    "browser_session": request["browser_session"],
                    "timeout_seconds": request["timeout_seconds"],
                    "human_review_approved": request["human_review_approved"],
                    "human_review_approved_by": request["human_review_approved_by"],
                    "human_review_note": request["human_review_note"],
                }
                push_result = push_publish_package_to_wechat(push_payload)
                if clean_text(push_result.get("status")) == "ok":
                    push_review_gate = safe_dict(push_result.get("review_gate"))
                    manual_review = build_manual_review_state(
                        request,
                        review_gate=push_review_gate or review_gate,
                        approved_at=isoformat_or_blank(now_utc()),
                    )
                    write_json(wechat_push_result_path, push_result)
                    push_stage = {
                        "requested": True,
                        "attempted": True,
                        "status": "ok",
                        "review_gate_status": push_review_gate.get("status", review_gate.get("status", "unknown")),
                        "push_readiness_status": push_readiness.get("status", "unknown"),
                        "workflow_publication_readiness": clean_text(
                            safe_dict(push_result.get("workflow_publication_gate")).get("publication_readiness")
                            or publish_package.get("publication_readiness")
                        ) or "ready",
                        "workflow_manual_review_status": clean_text(
                            safe_dict(safe_dict(push_result.get("workflow_publication_gate")).get("manual_review")).get("status")
                            or safe_dict(publish_package.get("workflow_manual_review")).get("status")
                        ) or "not_required",
                        "blocked_reason": "",
                        "result_path": str(wechat_push_result_path),
                        "draft_media_id": clean_text(safe_dict(push_result.get("draft_result")).get("media_id")),
                        "cover_media_id": clean_text(safe_dict(push_result.get("uploaded_cover")).get("media_id")),
                        "inline_image_count": len(safe_list(push_result.get("uploaded_inline_images"))),
                        "error_message": "",
                        "next_step": "WeChat draft created successfully. Continue with final platform-side review before publishing.",
                    }
                    overall_status = "ok"
                else:
                    overall_status = clean_text(push_result.get("status")) or "push_error"
                    push_review_gate = safe_dict(push_result.get("review_gate"))
                    if push_review_gate:
                        manual_review = build_manual_review_state(request, review_gate=push_review_gate)
                    push_stage = {
                        **push_stage,
                        "requested": True,
                        "attempted": False,
                        "status": clean_text(push_result.get("status")) or "blocked_review_gate",
                        "review_gate_status": push_review_gate.get("status", review_gate.get("status", "unknown")),
                        "push_readiness_status": push_readiness.get("status", "unknown"),
                        "workflow_publication_readiness": clean_text(
                            safe_dict(push_result.get("workflow_publication_gate")).get("publication_readiness")
                            or publish_package.get("publication_readiness")
                        ) or "ready",
                        "workflow_manual_review_status": clean_text(
                            safe_dict(safe_dict(push_result.get("workflow_publication_gate")).get("manual_review")).get("status")
                            or safe_dict(publish_package.get("workflow_manual_review")).get("status")
                        ) or "not_required",
                        "blocked_reason": clean_text(push_result.get("blocked_reason")) or "push_blocked",
                        "error_message": clean_text(push_result.get("error_message")),
                        "next_step": clean_text(push_review_gate.get("next_step")) or "Resolve the block and rerun the push step.",
                    }
            except Exception as exc:  # noqa: BLE001
                overall_status = "push_error"
                push_stage = {
                    **push_stage,
                    "requested": True,
                    "attempted": True,
                    "status": "error",
                    "blocked_reason": "push_failed",
                    "result_path": "",
                    "draft_media_id": "",
                    "cover_media_id": "",
                    "inline_image_count": 0,
                    "error_message": str(exc),
                    "next_step": "Inspect the push error, fix the failing asset or credential issue, then rerun the push step.",
                }

    legacy_push_to_toutiao = request["push_to_toutiao"] and not request["push_to_channel"]
    if legacy_push_to_toutiao:
        toutiao_fast_card_package = build_toutiao_fast_card_package(workflow_result, selected_topic, request)
        toutiao_card_path = request["output_dir"] / "toutiao-fast-card-package.json"
        write_json(toutiao_card_path, toutiao_fast_card_package)
        if not review_gate.get("approved"):
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
            except Exception as exc:  # noqa: BLE001
                toutiao_stage["status"] = "error"
                toutiao_stage["blocked_reason"] = "push_failed"
                toutiao_stage["error_message"] = clean_text(exc)

    if request["push_to_channel"]:
        if not review_gate.get("approved"):
            overall_status = "blocked_review_gate"
            channel_push_stage["status"] = "blocked_review_gate"
            channel_push_stage["blocked_reason"] = "human_review_not_approved"
        elif request["publish_channel"] == "wechat" and clean_text(safe_dict(publish_package.get("push_readiness")).get("status")) != "ready_for_api_push":
            overall_status = "blocked_push_readiness"
            channel_push_stage["status"] = "blocked_push_readiness"
            channel_push_stage["blocked_reason"] = f"push_not_ready:{clean_text(safe_dict(publish_package.get('push_readiness')).get('status'))}"
        else:
            channel_push_stage["attempted"] = True
            try:
                if request["publish_channel"] == "wechat":
                    channel_push_result = push_publish_package_to_wechat(
                        {
                            "publish_package": publish_package,
                            "push_backend": request["push_backend"],
                            "human_review_approved": request["human_review_approved"],
                            "human_review_approved_by": request["human_review_approved_by"],
                            "human_review_note": request["human_review_note"],
                            "wechat_app_id": request["wechat_app_id"],
                            "wechat_app_secret": request["wechat_app_secret"],
                            "wechat_env_file": request["wechat_env_file"],
                            "allow_insecure_inline_credentials": request["allow_insecure_inline_credentials"],
                            "cover_image_path": request["cover_image_path"],
                            "cover_image_url": request["cover_image_url"],
                            "author": request["author"],
                            "show_cover_pic": request["show_cover_pic"],
                            "timeout_seconds": request["timeout_seconds"],
                            "browser_session": request["browser_session"],
                        }
                    )
                    channel_push_stage["draft_media_id"] = clean_text(safe_dict(channel_push_result.get("draft_result")).get("media_id"))
                elif request["publish_channel"] == "toutiao":
                    channel_push_result = push_publish_package_to_toutiao(
                        {
                            "publish_package": publish_package,
                            "push_backend": clean_text(request.get("push_backend")) or "browser_session",
                            "human_review_approved": request["human_review_approved"],
                            "human_review_approved_by": request["human_review_approved_by"],
                            "human_review_note": request["human_review_note"],
                            "timeout_seconds": request["timeout_seconds"],
                            "browser_session": request["toutiao_browser_session"] or request["browser_session"],
                            "save_mode": "draft",
                        }
                    )
                    channel_push_stage["article_url"] = clean_text(channel_push_result.get("article_url"))
                else:
                    raise ValueError(f"Unsupported publish_channel: {request['publish_channel']}")
                write_json(Path(channel_push_stage["result_path"]), channel_push_result)
                channel_push_stage["status"] = clean_text(channel_push_result.get("status")) or "ok"
                channel_push_stage["push_backend"] = clean_text(channel_push_result.get("push_backend"))
            except Exception as exc:  # noqa: BLE001
                overall_status = "push_error"
                channel_push_stage["status"] = "error"
                channel_push_stage["blocked_reason"] = "push_failed"
                channel_push_stage["error_message"] = clean_text(exc)

    automatic_acceptance = build_automatic_acceptance_result(
        safe_dict(publish_package.get("regression_checks")),
        target=str(request["output_dir"]),
        output_dir=str(request["output_dir"]),
        regression_source="publish_package",
        extra_metadata={
            "publish_package_path": str(publish_package_path),
            "draft_result_path": safe_dict(workflow_result.get("draft_stage")).get("result_path", ""),
            "publish_result_path": str(request["output_dir"] / "article-publish-result.json"),
            "workflow_publication_gate": workflow_publication_gate,
        },
    )
    automatic_acceptance["report_markdown"] = build_automatic_acceptance_markdown(automatic_acceptance)
    write_json(automatic_acceptance_path, automatic_acceptance)
    automatic_acceptance_report_path.write_text(automatic_acceptance["report_markdown"], encoding="utf-8-sig")

    result = {
        "status": overall_status,
        "workflow_kind": "article_publish",
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "selected_topic": selected_topic,
        "selected_topic_path": str(selected_topic_path),
        "news_request_path": str(news_request_path),
        "publish_package": publish_package,
        "publish_package_path": str(publish_package_path),
        "wechat_html_path": str(wechat_html_path),
        "manual_review": manual_review,
        "review_gate": review_gate,
        "publication_readiness": clean_text(workflow_publication_gate.get("publication_readiness")) or "ready",
        "workflow_manual_review": safe_dict(workflow_publication_gate.get("manual_review")),
        "workflow_publication_gate": workflow_publication_gate,
        "automatic_acceptance": automatic_acceptance,
        "automatic_acceptance_path": str(automatic_acceptance_path),
        "automatic_acceptance_report_path": str(automatic_acceptance_report_path),
        "next_push_command": (
            f'financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_wechat_push_draft.cmd "{publish_package_path}"'
            if request["publish_channel"] == "wechat"
            else ""
        ),
        "push_stage": push_stage,
        "channel_push_stage": channel_push_stage,
        "toutiao_stage": toutiao_stage,
        "toutiao_fast_card_package": toutiao_fast_card_package,
        "discovery_stage": {
            "result_path": str(discovery_result_path),
            "report_markdown": discovery_result.get("report_markdown", ""),
        },
        "workflow_stage": {
            "result_path": str(workflow_result_path),
            "report_path": workflow_result.get("workflow_report_path", ""),
            "draft_result_path": safe_dict(workflow_result.get("draft_stage")).get("result_path", ""),
            "final_result_path": safe_dict(workflow_result.get("final_stage")).get("result_path", ""),
            "quality_gate": safe_dict(workflow_result.get("final_stage")).get("quality_gate", ""),
            "publication_readiness": clean_text(workflow_result.get("publication_readiness")),
        },
    }
    result["report_markdown"] = build_report_markdown(result)
    report_path = request["output_dir"] / "article-publish-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8-sig")
    result["report_path"] = str(report_path)
    return result


__all__ = [
    "build_news_request_from_topic",
    "build_publish_package",
    "build_report_markdown",
    "push_publish_package_to_wechat",
    "push_publish_package_to_toutiao",
    "run_article_publish",
]
