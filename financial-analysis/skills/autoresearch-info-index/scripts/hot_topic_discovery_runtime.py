#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import Any

from agent_reach_bridge_runtime import fetch_agent_reach_channels
from news_index_runtime import clean_string_list, isoformat_or_blank, parse_datetime, safe_dict, safe_list, slugify
from reddit_bridge_runtime import build_comment_operator_review, build_operator_review_priority, format_comment_operator_review


DEFAULT_DISCOVERY_SOURCES = ["weibo", "zhihu", "36kr", "google-news-world"]
LIVE_SNAPSHOT_SOURCES = ["google-news-world", "36kr"]
LIVE_SNAPSHOT_DEFAULT_LIMIT = 8
LIVE_SNAPSHOT_DEFAULT_TOP_N = 5
LIVE_SNAPSHOT_DEFAULT_MAX_PARALLEL_SOURCES = 2
LIVE_SNAPSHOT_MEDIUM_FIT_LIMIT = 2
LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE = 70
LIVE_SNAPSHOT_SOURCE_ORDER = ["36kr", "google-news-world"]
LIVE_SNAPSHOT_GOOGLE_WORLD_TIMEOUT_SECONDS = 15
LIVE_SNAPSHOT_ANALYSIS_KEYWORDS = {
    "market",
    "markets",
    "oil",
    "equities",
    "stocks",
    "guidance",
    "earnings",
    "capex",
    "rollout",
    "policy",
    "conflict",
    "supply chain",
    "order",
    "orders",
    "oil price",
    "risk asset",
    "risk assets",
    "油价",
    "风险资产",
    "订单",
}
LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS = {
    "official commentary",
    "modernization goal",
    "must be achieved",
    "总书记",
    "看图学习",
    "宣传",
    "会议精神",
}
LIVE_SNAPSHOT_EXTENSION_KEYWORDS = {
    "ai",
    "model",
    "chip",
    "chips",
    "market",
    "markets",
    "company",
    "policy",
    "robotaxi",
    "supply chain",
    "energy",
    "macro",
    "earnings",
    "capex",
    "AI",
    "鑺墖",
    "甯傚満",
    "鍏徃",
    "鏀跨瓥",
    "渚涘簲閾?",
    "鑳芥簮",
    "瀹忚",
}
LIVE_SNAPSHOT_ANALYSIS_KEYWORDS.update(
    {
        "revenue",
        "profit",
        "margin",
        "loss",
        "sales",
        "bond",
        "yield",
        "volatility",
        "ceasefire",
        "strait",
        "shipping",
        "sanction",
        "tariff",
        "negotiation",
        "钀ユ敹",
        "鍒╂鼎",
        "鍑€鍒?",
        "浜忔崯",
        "鑲″競",
        "鏀剁泭鐜?",
        "娉㈠姩鐜?",
        "鍋滅伀",
        "娴峰场",
        "鑸繍",
        "鍒惰",
        "鍏崇◣",
        "璋堝垽",
    }
)
LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS.update(
    {
        "international observation",
        "global change",
        "talks remain uncertain",
        "observation",
        "analysis says",
        "灞€鍔胯蛋鍚戞湁鍑犵鍙兘",
        "瑙傚療",
        "鑳屽悗",
        "鍙樺眬",
        "瀵嗛泦璁垮崕",
        "鐞嗘€с€佸姟瀹炲洖搴?",
    }
)
DEFAULT_TOPIC_SCORE_WEIGHTS = {
    "timeliness": 0.22,
    "debate": 0.18,
    "relevance": 0.23,
    "depth": 0.14,
    "seo": 0.13,
    "information_gap": 0.10,
}
POSITIVE_FEEDBACK_HARD_INDUSTRY_KEYWORDS = {
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
    "光刻",
    "晶圆",
    "代工",
    "芯片",
    "半导体",
    "封装",
    "产能",
    "供应链",
    "算力",
    "数据中心",
}
POSITIVE_FEEDBACK_CLEAR_ACTOR_KEYWORDS = {
    "nvidia",
    "amd",
    "intel",
    "tsmc",
    "asml",
    "tesla",
    "openai",
    "anthropic",
    "amazon",
    "microsoft",
    "meta",
    "台积电",
    "阿斯麦",
    "英伟达",
    "华为",
    "腾讯",
    "特斯拉",
    "亚马逊",
    "微软",
}
POSITIVE_FEEDBACK_CHINA_MARKET_KEYWORDS = {
    "china",
    "chinese",
    "market",
    "markets",
    "guidance",
    "earnings",
    "capex",
    "order",
    "orders",
    "supply chain",
    "trade war",
    "中国",
    "国产",
    "市场",
    "股价",
    "资本市场",
    "订单",
    "指引",
    "财报",
    "关税",
    "出口管制",
    "供应链",
}
POSITIVE_FEEDBACK_CONTRARIAN_MARKERS = (
    "不是",
    "而是",
    "最怕",
    "真正",
    "护城河",
    "胜负手",
    "关键不在",
    "关键不是",
    "not ",
    "but ",
    "real moat",
    "actually",
    "误判",
    "被低估",
    "被高估",
    "反转",
    "拐点",
    "underestimated",
    "overestimated",
    "turning point",
    "the market is wrong",
    "consensus is",
)
FRESH_CATALYST_KEYWORDS = {
    "new filing",
    "filing",
    "guidance",
    "raises",
    "cuts",
    "update",
    "updated",
    "expands",
    "expansion",
    "rollout",
    "order",
    "orders",
    "hearing",
    "probe",
    "ceasefire",
    "sanction",
    "sanctions",
    "guidance check",
}
CONTINUING_STORY_KEYWORDS = {
    "again",
    "returns",
    "return",
    "back into",
    "update",
    "filing",
    "guidance",
    "rollout",
    "hearing",
    "probe",
    "ceasefire",
    "sanction",
}
AGENT_REACH_ENV_VAR = "AGENT_REACH_PROVIDERS"
REDDIT_LISTING_ALIASES = {
    "best": "best",
    "hot": "hot",
    "new": "new",
    "rising": "rising",
    "top": "top",
    "controversial": "controversial",
}
REDDIT_WINDOW_ALIASES = {
    "hour": "hour",
    "1h": "hour",
    "24h": "day",
    "day": "day",
    "1d": "day",
    "today": "day",
    "week": "week",
    "7d": "week",
    "month": "month",
    "30d": "month",
    "year": "year",
    "365d": "year",
    "all": "all",
    "alltime": "all",
}
REDDIT_LISTING_HEAT_BONUS = {
    "rising": 1800,
    "hot": 1200,
    "top": 900,
    "new": 500,
    "best": 350,
    "controversial": 250,
}
REDDIT_LISTING_SCORE_BONUS = {
    "rising": 0.08,
    "hot": 0.06,
    "top": 0.05,
    "new": 0.03,
    "best": 0.02,
    "controversial": 0.01,
}
REDDIT_WINDOW_WEIGHT = {
    "hour": 1.00,
    "day": 0.90,
    "week": 0.75,
    "month": 0.60,
    "year": 0.50,
    "all": 0.35,
}
REDDIT_CLUSTER_TOKEN_STOPWORDS = {
    "discussion",
    "thread",
    "threads",
    "check",
    "checking",
    "latest",
    "still",
    "debates",
    "debate",
    "retail",
    "investors",
    "thoughts",
    "thought",
    "means",
    "meaning",
    "matters",
    "matter",
    "readthrough",
    "underpriced",
    "priced",
    "pricing",
    "look",
    "looks",
    "again",
    "keep",
    "keeps",
    "show",
    "showing",
    "center",
    "centers",
    "centered",
}
REDDIT_CLUSTER_SHORT_TOKENS = {"ai", "ipo", "gpu", "lng", "hbm"}
REDDIT_CLUSTER_GENERIC_QUERY_TOKENS = {
    "advanced",
    "bottleneck",
    "bottlenecks",
    "capacity",
    "chain",
    "constraint",
    "constraints",
    "packaging",
    "supplier",
    "suppliers",
    "supply",
}
DEFAULT_REDDIT_CLUSTER_ALIAS_GROUPS = (
    {"nvidia", "nvda"},
    {"tesla", "tsla"},
    {"apple", "aapl"},
    {"microsoft", "msft"},
    {"amazon", "amzn"},
    {"google", "alphabet", "googl", "goog"},
    {"tsmc", "台积电", "台積電"},
)
REDDIT_CLUSTER_ALIAS_PATH = Path(__file__).resolve().parents[1] / "references" / "reddit-cluster-aliases.json"
REDDIT_CLUSTER_ALIAS_CONFIG_KEYS = (
    "ticker_alias_groups",
    "company_alias_groups",
    "cross_language_alias_groups",
    "alias_groups",
)
DEFAULT_REDDIT_SUBREDDIT_KIND_GROUPS = {
    "broad_market": {"r/stocks", "r/investing", "r/StockMarket"},
    "deep_research": {"r/SecurityAnalysis", "r/ValueInvesting"},
    "speculative_flow": {"r/wallstreetbets", "r/options", "r/pennystocks", "r/Superstonk"},
    "event_watch": {"r/geopolitics", "r/worldnews", "r/economics", "r/CredibleDefense"},
}
REDDIT_COMMUNITY_PROFILE_PATH = Path(__file__).resolve().parents[1] / "references" / "reddit-community-profiles.json"
FINANCE_KEYWORDS = {
    "ai",
    "agent",
    "openai",
    "claude",
    "芯片",
    "半导体",
    "算力",
    "大模型",
    "模型",
    "融资",
    "上市",
    "ipo",
    "并购",
    "裁员",
    "出海",
    "消费",
    "制造",
    "新能源",
    "汽车",
    "机器人",
    "军工",
    "油",
    "油气",
    "天然气",
    "关税",
    "政策",
    "a股",
    "港股",
    "美股",
    "经济",
    "宏观",
    "基金",
    "银行",
    "证券",
    "地产",
    "黄金",
    "铜",
    "铝",
}
DEBATE_KEYWORDS = {
    "为什么",
    "争议",
    "意味着",
    "冲击",
    "暴涨",
    "暴跌",
    "裁员",
    "封杀",
    "暂停",
    "限制",
    "崩盘",
    "利空",
    "利好",
    "冲突",
    "战争",
    "谈判",
    "断供",
    "禁令",
}
SEO_STOPWORDS = {"今天", "最新", "刚刚", "回应", "热搜", "视频", "全文", "图"}
ALLOWED_LOCALITY_KEYWORDS = {
    "上海",
    "浙江",
    "杭州",
    "宁波",
    "温州",
    "嘉兴",
    "湖州",
    "绍兴",
    "金华",
    "义乌",
    "台州",
    "丽水",
    "衢州",
    "舟山",
}
BLOCKED_LOCALITY_KEYWORDS = {
    "北京",
    "天津",
    "重庆",
    "河北",
    "山西",
    "内蒙古",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "海南",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
    "深圳",
    "广州",
    "中山",
    "东莞",
    "苏州",
    "南京",
    "无锡",
    "成都",
    "武汉",
    "长沙",
    "西安",
    "郑州",
    "青岛",
    "厦门",
    "阜沙",
}
LOCAL_ADMIN_KEYWORDS = {"镇", "区", "县", "乡", "村", "街道", "开发区", "新区"}
OBITUARY_KEYWORDS = {
    "逝世",
    "去世",
    "病逝",
    "辞世",
    "离世",
    "dead",
    "death",
    "dies",
    "found dead",
    "murder-suicide",
    "obituary",
}
RUMOR_KEYWORDS = {"传闻", "爆料", "据传", "网传", "疑似", "或本周上线", "或将", "rumor"}
VERIFICATION_KEYWORDS = {"实名", "认证", "验证", "封号", "证件", "手持证件", "自拍"}
CROSS_PLATFORM_STORY_KEYWORDS = {
    "claude",
    "anthropic",
    "opus",
    "openai",
    "chatgpt",
    "gpt",
    "gemini",
    "实名",
    "认证",
    "验证",
    "封号",
    "证件",
    "账号",
    "模型",
    "上线",
    "发布",
    "传闻",
}
CROSS_PLATFORM_ENTITY_TOKENS = {
    # AI companies
    "claude",
    "anthropic",
    "openai",
    "chatgpt",
    "gpt",
    "gemini",
    "腾讯",
    "混元",
    "阿里",
    "通义",
    "字节",
    "豆包",
    "英伟达",
    "nvidia",
    # Semiconductors / chips
    "semiconductor",
    "asml",
    "tsmc",
    "amd",
    "intel",
    "qualcomm",
    "hbm",
    "gpu",
    "chip",
    # Major tickers / companies
    "netflix",
    "nflx",
    "tesla",
    "tsla",
    "nio",
    "amazon",
    "amzn",
    "apple",
    "aapl",
    "microsoft",
    "msft",
    "google",
    "meta",
    # Industry / macro
    "oil",
    "crude",
    "opec",
    "earnings",
    "robotaxi",
    "ev",
}
CROSS_PLATFORM_TOKEN_STOPWORDS = {"突发", "本周", "直接", "必须", "否则", "开始", "消息", "引入", "正式"}
INTERNATIONAL_PRIMARY_SOURCES = ["agent-reach:reddit", "agent-reach:x"]
INTERNATIONAL_FALLBACK_SOURCES = ["google-news-world", "36kr"]
GENERIC_FEATURE_KEYWORDS = {"我们和", "聊了聊", "有人转型", "有人想逃", "牛马", "人物故事", "采访"}
DIPLOMATIC_PROTOCOL_KEYWORDS = {"会见", "四访", "关系重要性", "桥梁", "共同会见", "指出", "致力搭建"}
OFFICIAL_COMMENTARY_KEYWORDS = {"自信", "胸怀", "担当", "评论员", "述评", "观察", "阐释", "彰显", "元首外交"}
EXPLICIT_OFFTOPIC_PREFIXES = {"somewhat off-topic", "off-topic:"}
GENERIC_PLATFORM_POLITICAL_NAMES = {"trump", "vance", "biden", "mayor", "governor", "pope"}
GENERIC_PLATFORM_POLITICAL_PHRASES = {
    "proudest achievements",
    "calls end of",
    "says end of",
    "administration",
}
GENERIC_PLATFORM_POLITICAL_KEEP_KEYWORDS = {
    "oil",
    "hormuz",
    "jet fuel",
    "tariff",
    "tariffs",
    "sanction",
    "sanctions",
    "supply chain",
    "market",
    "markets",
    "chip",
    "chips",
    "semiconductor",
    "semiconductors",
    "ai",
    "robotaxi",
    "defence",
    "defense",
    "procurement",
    "ukraine support loan",
}
REDDIT_META_THREAD_KEYWORDS = {
    "daily general discussion",
    "discussion and advice thread",
    "questions and discussions thread",
    "rate my portfolio",
    "megathread",
    "who's hiring",
    "self-promotion thread",
    "self promotion thread",
    "please do not submit",
    "questions and discussions thread",
    "quarterly thread",
    "monthly",
    "reminder:",
    "letters & reports",
    "letters and reports",
    "investor letters",
    "quarterly reports",
}
REDDIT_RESEARCH_SIGNAL_KEYWORDS = {
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "nvidia",
    "amd",
    "tsmc",
    "tesla",
    "robotaxi",
    "earnings",
    "revenue",
    "guidance",
    "market share",
    "catalyst",
    "semiconductor",
    "chip",
    "chips",
    "hbm",
    "oil",
    "hormuz",
    "jet fuel",
    "ukraine",
    "defense",
    "defence",
}
REDDIT_LOW_SPECIFICITY_GENERIC_TOKENS = {
    "macro",
    "market",
    "markets",
    "outlook",
    "tariff",
    "tariffs",
    "economy",
    "economic",
    "global",
    "debating",
    "investors",
    "retail",
    "today",
    "week",
    "stocks",
}
REDDIT_LOW_SPECIFICITY_PHRASES = {
    "markets are debating",
    "investors are debating",
    "macro outlook",
    "market outlook",
    "tariffs and macro",
    "global outlook",
}
SELF_PROMOTIONAL_PLATFORM_KEYWORDS = {
    "i built",
    "i made",
    "free & gives",
    "gives your agents",
    "my startup",
    "my tool",
    "launching today",
}
EXHIBITION_PROMO_KEYWORDS = {
    "广交会",
    "消博会",
    "卖货",
    "亮相",
    "展位",
    "上新",
    "首秀",
    "参展",
}


X_GENERIC_CIVIC_KEYWORDS = {
    "mayor",
    "governor",
    "pope",
    "cameroon",
    "pied",
    "terre",
    "second homes",
    "luxury second homes",
    "visits",
    "leaders' call",
    "migrant children",
    "shelter contract",
    "catholic shelter",
    "administration cancels",
    "senate rejects",
    "push to block",
    "arms to israel",
    "jesus embrace",
    "pope criticism",
    "armed citizens",
    "stop more shooters",
    "draws backlash",
}
X_CORE_TOPIC_KEYWORDS = {
    "agent",
    "chip",
    "chips",
    "semiconductor",
    "gpu",
    "robotaxi",
    "tesla",
    "nvidia",
    "openai",
    "claude",
    "anthropic",
    "apple",
    "google",
    "amazon",
    "microsoft",
    "oil",
    "gas",
    "fuel",
    "jet fuel",
    "energy",
    "hormuz",
    "shipping",
    "port",
    "ports",
    "blockade",
    "shortage",
    "iea",
    "supplier",
    "supply",
    "manufacturing",
    "tariff",
    "trade",
    "export",
    "sanction",
    "robot",
    "battery",
    "ev",
}
X_GENERIC_COMMENTARY_TITLE_PREFIXES = {
    "okay,",
    "something just shifted in how i think about",
}
X_GENERIC_COMMENTARY_PHRASES = {
    "how i think about",
    "what excites me most",
    "worth sitting with",
    "i will tell you honestly",
    "stops me in my tracks",
    "different category of tool",
    "not ai that answers",
    "ai that acts",
    "human attention",
    "for every team",
}
X_COMMENTARY_KEEP_KEYWORDS = {
    "earnings",
    "revenue",
    "guidance",
    "market share",
    "supplier",
    "supply chain",
    "chip",
    "chips",
    "semiconductor",
    "gpu",
    "robotaxi",
    "autonomous",
    "autonomy",
    "oil",
    "fuel",
    "jet fuel",
    "hormuz",
    "shipping",
    "port",
    "ports",
    "blockade",
    "shortage",
    "tariff",
    "sanction",
    "capex",
    "fab",
    "foundry",
    "memory",
    "hbm",
    "valuation",
    "stock",
    "stocks",
    "funding",
    "financing",
    "round",
    "merger",
    "acquisition",
    "ryzen",
}
X_MANIFESTO_PHRASES = {
    "the bottom line",
    "for years, tesla has dominated headlines",
    "not a single-company story",
    "growing army of robotaxi challengers",
}
GENERIC_BROAD_MARKET_QUESTION_PREFIXES = {
    "why is the market",
    "why are markets",
    "why are stocks",
}
AI_MEME_ENTERTAINMENT_PHRASES = {
    "squid game",
    "battle royale",
    "who would win",
    "ai hunger games",
    "ai gladiator",
    "prompt battle",
    "ai rap battle",
    "ai roast",
    "ai meme",
    "pure entertainment",
}
AI_MEME_ENTERTAINMENT_KEEP_KEYWORDS = {
    "earnings",
    "revenue",
    "guidance",
    "supply chain",
    "supply crunch",
    "capex",
    "fab",
    "foundry",
    "hbm",
    "valuation",
    "market share",
    "semiconductor",
    "chip",
    "gpu",
    "h200",
    "h100",
    "b200",
    "hyperscaler",
}
ENTERPRISE_AI_SYNTHESIS_PHRASES = {
    "enterprise ai flywheel",
    "flywheel is spinning",
    "flywheel effect",
    "winners keep winning",
    "the new paradigm",
    "ai adoption is accelerating",
    "doubled down on openai",
    "enterprise ai adoption",
}
ENTERPRISE_AI_SYNTHESIS_KEEP_KEYWORDS = {
    "earnings",
    "revenue",
    "guidance",
    "beat",
    "missed",
    "eps",
    "capex",
    "supply chain",
    "supply crunch",
    "fab",
    "foundry",
    "hbm",
    "semiconductor",
    "chip",
    "gpu",
    "h200",
    "h100",
    "b200",
    "hyperscaler",
    "valuation",
    "market share",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def now_utc() -> datetime:
    return datetime.now(UTC)


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def normalize_topic_score_weights(value: Any) -> dict[str, float]:
    raw_value = value
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            raw_value = {}
    raw_weights = safe_dict(raw_value)
    weights: dict[str, float] = {}
    total = 0.0
    for key, default in DEFAULT_TOPIC_SCORE_WEIGHTS.items():
        try:
            numeric = float(raw_weights.get(key, default))
        except (TypeError, ValueError):
            numeric = float(default)
        numeric = max(0.0, numeric)
        weights[key] = numeric
        total += numeric
    if total <= 0:
        return dict(DEFAULT_TOPIC_SCORE_WEIGHTS)
    return {key: round(weights[key] / total, 4) for key in DEFAULT_TOPIC_SCORE_WEIGHTS}


def candidate_match_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        [
            candidate.get("title", ""),
            candidate.get("summary", ""),
            " ".join(candidate.get("keywords", [])),
            " ".join(candidate.get("source_names", [])),
        ]
    ).lower()


def contains_any_keyword(text: str, keywords: set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def contains_any_keyword_boundary(text: str, keywords: set[str]) -> bool:
    for keyword in keywords:
        lowered = keyword.lower()
        if re.search(r"[a-z]", lowered):
            pattern = rf"(?<![a-z0-9]){re.escape(lowered)}(?![a-z0-9])"
            if re.search(pattern, text):
                return True
            continue
        if lowered in text:
            return True
    return False


def is_allowed_locality_candidate(candidate: dict[str, Any]) -> bool:
    return contains_any_keyword(candidate_match_text(candidate), {item.lower() for item in ALLOWED_LOCALITY_KEYWORDS})


def is_locality_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    if contains_any_keyword(text, {item.lower() for item in ALLOWED_LOCALITY_KEYWORDS}):
        return False
    if contains_any_keyword(text, {item.lower() for item in BLOCKED_LOCALITY_KEYWORDS}):
        return True
    title = clean_text(candidate.get("title"))
    summary = clean_text(candidate.get("summary"))
    if any(marker in title for marker in LOCAL_ADMIN_KEYWORDS):
        return True
    if any(marker in summary for marker in LOCAL_ADMIN_KEYWORDS) and any(
        keyword.lower() in text for keyword in {item.lower() for item in BLOCKED_LOCALITY_KEYWORDS}
    ):
        return True
    return False


def is_weak_obituary_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    if not contains_any_keyword(text, {item.lower() for item in OBITUARY_KEYWORDS}):
        return False
    if int(candidate.get("source_count", 0) or 0) >= 2:
        return False
    return len(keyword_hits(text)) < 3


def is_rumor_like_candidate(candidate: dict[str, Any]) -> bool:
    title = clean_text(candidate.get("title"))
    text = candidate_match_text(candidate)
    return "?" in title or "？" in title or contains_any_keyword(text, {item.lower() for item in RUMOR_KEYWORDS})


def is_verification_like_candidate(candidate: dict[str, Any]) -> bool:
    return contains_any_keyword(candidate_match_text(candidate), {item.lower() for item in VERIFICATION_KEYWORDS})


def is_generic_feature_interview_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    return contains_any_keyword(text, {item.lower() for item in GENERIC_FEATURE_KEYWORDS})


def is_diplomatic_protocol_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    return contains_any_keyword(text, {item.lower() for item in DIPLOMATIC_PROTOCOL_KEYWORDS})


def is_official_commentary_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    title = clean_text(candidate.get("title"))
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    if re.match(r"^从.+看", title):
        return True
    return contains_any_keyword(text, {item.lower() for item in OFFICIAL_COMMENTARY_KEYWORDS})


def is_live_snapshot_low_yield_candidate(candidate: dict[str, Any]) -> bool:
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness not in {"0-6h", "6-24h"}:
        return False
    text = " ".join(
        [
            clean_text(candidate.get("title")),
            " ".join(clean_string_list(candidate.get("keywords"))),
        ]
    ).lower()
    if not contains_any_keyword(text, LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS):
        return False
    if contains_any_keyword(text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
        return False
    return True


def is_explicitly_offtopic_platform_candidate(candidate: dict[str, Any]) -> bool:
    if primary_platform_signal_count(candidate) == 0:
        return False
    title = clean_text(candidate.get("title")).lower()
    return any(title.startswith(prefix) for prefix in EXPLICIT_OFFTOPIC_PREFIXES)


def is_generic_platform_political_statement_candidate(candidate: dict[str, Any]) -> bool:
    if primary_platform_signal_count(candidate) == 0:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    title = clean_text(candidate.get("title")).lower()
    if not contains_any_keyword_boundary(title, GENERIC_PLATFORM_POLITICAL_NAMES):
        return False
    if contains_any_keyword_boundary(title, GENERIC_PLATFORM_POLITICAL_KEEP_KEYWORDS):
        return False
    return contains_any_keyword_boundary(title, GENERIC_PLATFORM_POLITICAL_PHRASES)


def is_reddit_meta_discussion_candidate(candidate: dict[str, Any]) -> bool:
    title = clean_text(candidate.get("title")).lower()
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if not all(is_primary_platform_source_item(item) and clean_text(item.get("source_name")).lower().startswith("reddit ") for item in source_items):
        return False
    if contains_any_keyword(title, REDDIT_META_THREAD_KEYWORDS):
        return True
    if "live thread" in title or " ama " in f" {title} ":
        return True
    return bool(re.match(r"^\[week\s+\d+", title))


def is_generic_reddit_research_chatter_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    if not all(is_primary_platform_source_item(item) and clean_text(item.get("source_name")).lower().startswith("reddit ") for item in source_items):
        return False
    title = clean_text(candidate.get("title")).lower()
    if "[r]" not in title and "[d]" not in title:
        return False
    return not contains_any_keyword(title, REDDIT_RESEARCH_SIGNAL_KEYWORDS)


def candidate_source_item_tags(candidate: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for item in safe_list(candidate.get("source_items")):
        if not isinstance(item, dict):
            continue
        for tag in clean_string_list(item.get("tags")):
            if tag:
                tags.add(tag)
    return tags


def candidate_reddit_subreddit_kinds(candidate: dict[str, Any]) -> set[str]:
    kinds = {
        normalize_reddit_subreddit_kind(kind)
        for kind in clean_string_list(candidate.get("reddit_subreddit_kinds"))
        if normalize_reddit_subreddit_kind(kind)
    }
    if kinds:
        return kinds
    for tag in candidate_source_item_tags(candidate):
        if tag.startswith("subreddit_kind:"):
            normalized = normalize_reddit_subreddit_kind(tag.split(":", 1)[1])
            if normalized:
                kinds.add(normalized)
    return kinds


def candidate_reddit_outbound_domains(candidate: dict[str, Any]) -> set[str]:
    domains = {clean_text(domain).lower() for domain in clean_string_list(candidate.get("reddit_outbound_domains")) if clean_text(domain)}
    if domains:
        return domains
    for tag in candidate_source_item_tags(candidate):
        if tag.startswith("outbound_domain:"):
            domain = clean_text(tag.split(":", 1)[1]).lower()
            if domain:
                domains.add(domain)
    return domains


def is_low_specificity_reddit_platform_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if not all(is_primary_platform_source_item(item) and clean_text(item.get("source_name")).lower().startswith("reddit ") for item in source_items):
        return False
    if primary_platform_signal_count(candidate) > 1 or int(candidate.get("source_count", 0) or 0) > 1:
        return False
    subreddit_kinds = candidate_reddit_subreddit_kinds(candidate)
    if not subreddit_kinds or not subreddit_kinds.issubset({"broad_market", "event_watch"}):
        return False
    if candidate_reddit_outbound_domains(candidate):
        return False
    text = clean_text(candidate.get("title")).lower()
    if contains_any_keyword(text, REDDIT_LOW_SPECIFICITY_PHRASES):
        return True
    tokens = reddit_cluster_tokens(
        {
            "title": candidate.get("title", ""),
            "summary": candidate.get("summary", ""),
        }
    )
    if cross_platform_entity_tokens(tokens):
        return False
    specific_tokens = tokens - REDDIT_CLUSTER_GENERIC_QUERY_TOKENS - REDDIT_LOW_SPECIFICITY_GENERIC_TOKENS
    return len(specific_tokens) <= 1


def is_self_promotional_platform_candidate(candidate: dict[str, Any]) -> bool:
    if primary_platform_signal_count(candidate) == 0:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    return contains_any_keyword(candidate_match_text(candidate), SELF_PROMOTIONAL_PLATFORM_KEYWORDS)


def is_exhibition_promo_candidate(candidate: dict[str, Any]) -> bool:
    if primary_platform_signal_count(candidate) > 0:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    return contains_any_keyword(candidate_match_text(candidate), EXHIBITION_PROMO_KEYWORDS)


def is_x_platform_source_item(item: dict[str, Any]) -> bool:
    source_name = clean_text(item.get("source_name")).lower()
    tags = clean_string_list(item.get("tags"))
    return source_name in {"agent-reach:x", "x"} or source_name.startswith("x @") or "provider:agent-reach:x" in tags


def is_generic_x_news_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False

    if not all(is_x_platform_source_item(item) for item in source_items):
        return False
    text = clean_text(candidate.get("title")).lower()
    if not contains_any_keyword_boundary(text, X_GENERIC_CIVIC_KEYWORDS):
        return False
    if contains_any_keyword_boundary(text, X_CORE_TOPIC_KEYWORDS):
        return False
    return True


def is_generic_x_commentary_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    if not all(is_x_platform_source_item(item) for item in source_items):
        return False
    title = clean_text(candidate.get("title")).lower()
    text = candidate_match_text(candidate)
    if not (
        any(title.startswith(prefix) for prefix in X_GENERIC_COMMENTARY_TITLE_PREFIXES)
        or contains_any_keyword(text, X_GENERIC_COMMENTARY_PHRASES)
    ):
        return False
    if contains_any_keyword(text, X_COMMENTARY_KEEP_KEYWORDS):
        return False
    return True


def is_generic_x_manifesto_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    if not all(is_x_platform_source_item(item) for item in source_items):
        return False
    title = clean_text(candidate.get("title"))
    lowered_title = title.lower()
    text = candidate_match_text(candidate)
    lowered_text = text.lower()
    if len(lowered_text) < 260:
        return False
    if "#" not in title and "$" not in title and len(title) < 100:
        return False
    if lowered_text.count(" wins") < 2 and not contains_any_keyword(lowered_text, X_MANIFESTO_PHRASES):
        return False
    return True


def is_generic_broad_market_question_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    if not all(is_primary_platform_source_item(item) and clean_text(item.get("source_name")).lower().startswith("reddit ") for item in source_items):
        return False
    subreddit_kinds = candidate_reddit_subreddit_kinds(candidate)
    if not subreddit_kinds or not subreddit_kinds.issubset({"broad_market"}):
        return False
    title = clean_text(candidate.get("title")).lower()
    if "?" not in title:
        return False
    return any(title.startswith(prefix) for prefix in GENERIC_BROAD_MARKET_QUESTION_PREFIXES)


def is_ai_meme_entertainment_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    text = candidate_match_text(candidate)
    if not contains_any_keyword(text, AI_MEME_ENTERTAINMENT_PHRASES):
        return False
    if contains_any_keyword(text, AI_MEME_ENTERTAINMENT_KEEP_KEYWORDS):
        return False
    return True


def is_enterprise_ai_synthesis_candidate(candidate: dict[str, Any]) -> bool:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return False
    if int(candidate.get("source_count", 0) or 0) > 1:
        return False
    text = candidate_match_text(candidate)
    if not contains_any_keyword(text, ENTERPRISE_AI_SYNTHESIS_PHRASES):
        return False
    if contains_any_keyword(text, ENTERPRISE_AI_SYNTHESIS_KEEP_KEYWORDS):
        return False
    return True


def is_primary_platform_source_item(item: dict[str, Any]) -> bool:
    source_name = clean_text(item.get("source_name")).lower()
    if source_name.startswith("reddit ") or source_name.startswith("x @") or source_name == "x":
        return True
    tags = clean_string_list(item.get("tags"))
    return any(tag in {"provider:agent-reach:reddit", "provider:agent-reach:x"} for tag in tags)


def primary_platform_signal_count(candidate: dict[str, Any]) -> int:
    return sum(1 for item in safe_list(candidate.get("source_items")) if isinstance(item, dict) and is_primary_platform_source_item(item))


def source_mix_summary(candidate: dict[str, Any]) -> str:
    reddit_count = 0
    x_count = 0
    fallback_count = 0
    for item in safe_list(candidate.get("source_items")):
        if not isinstance(item, dict):
            continue
        if is_primary_platform_source_item(item):
            source_name = clean_text(item.get("source_name")).lower()
            tags = clean_string_list(item.get("tags"))
            if source_name.startswith("reddit ") or "provider:agent-reach:reddit" in tags:
                reddit_count += 1
            elif source_name.startswith("x @") or source_name == "x" or "provider:agent-reach:x" in tags:
                x_count += 1
        else:
            fallback_count += 1
    parts: list[str] = []
    if reddit_count:
        parts.append(f"Reddit {reddit_count}")
    if x_count:
        parts.append(f"X {x_count}")
    if fallback_count:
        parts.append(f"Fallback {fallback_count}")
    return " + ".join(parts) if parts else "Fallback 0"


def story_family_label(candidate: dict[str, Any]) -> str:
    text = candidate_match_text(candidate)
    if "claude" in text or "anthropic" in text:
        if is_rumor_like_candidate(candidate) or is_verification_like_candidate(candidate):
            return "Claude / Anthropic release-rumor cycle"
        return "Claude / Anthropic platform change"
    if "ai" in text and "芯片" in text:
        return "国产 AI 芯片竞争"
    return clean_text(candidate.get("title"))


def recommended_story_angle(candidate: dict[str, Any]) -> str:
    text = candidate_match_text(candidate)
    if "claude" in text or "anthropic" in text:
        return "为什么模型发布时间和账号限制传闻总会反复出现，普通读者该怎么辨真假"
    if "ai" in text and "芯片" in text:
        return "国产 AI 芯片到底到了哪一步，真正值得看的竞争格局和替代空间是什么"
    return "这件事为什么值得现在关注，以及它会改变哪些判断"


def why_now_summary(candidate: dict[str, Any]) -> str:
    freshness = clean_text(candidate.get("freshness_bucket"))
    heat = clean_text(candidate.get("heat_bucket"))
    if candidate.get("fresh_catalyst_present"):
        return "这条题不是旧闻回放，而是过去 24 小时内出现了 fresh catalyst。"
    if freshness == "0-6h" and heat.startswith("near_window"):
        return "过去 6 小时内出现了近窗多源扩散，这波热度不是旧讨论残留。"
    if freshness == "6-24h":
        return "过去 24 小时内还有新的公开信号，时效性仍然足够强。"
    if freshness == ">72h":
        return "最新公开信号已经超过 72 小时，除非有新的催化剂，否则更像旧闻余波。"
    primary_count = primary_platform_signal_count(candidate)
    if primary_count and (is_rumor_like_candidate(candidate) or is_verification_like_candidate(candidate)):
        return "平台讨论在升温，而且真假混杂，适合做一次辨真假梳理。"
    if primary_count:
        return "Reddit/X 上已经形成真实讨论，这不只是单条新闻标题。"
    return "这条题目仍有一定延展空间，但更多依赖新闻兜底补充。"


def selection_reason_summary(candidate: dict[str, Any]) -> str:
    freshness = clean_text(candidate.get("freshness_bucket"))
    if candidate.get("fresh_catalyst_present"):
        return "保留这条题，不是因为旧闻本身，而是因为过去 24 小时内出现了 fresh catalyst。"
    if freshness == "0-6h":
        return "主因是这条题刚进入 6 小时内窗口，而且近窗热度来自真实扩散。"
    if freshness == "6-24h":
        return "主因是这条题仍处在 24 小时内窗口，时效和可写角度都还在。"
    if freshness == ">72h":
        return "这条题已经偏旧，只有在后续出现 fresh catalyst 时才适合保留。"
    primary_count = primary_platform_signal_count(candidate)
    if primary_count:
        return f"主因是平台侧已有 {primary_count} 条有效讨论信号，而且具备可写角度。"
    return "目前主要靠兜底新闻源支撑，适合作为备选而非首选。"


def risk_flags_for_candidate(candidate: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if int(candidate.get("source_count", 0) or 0) <= 1:
        flags.append("single_source")
    if is_rumor_like_candidate(candidate):
        flags.append("rumor_heavy")
    if primary_platform_signal_count(candidate) == 0:
        flags.append("fallback_only")
    if int(candidate.get("source_count", 0) or 0) <= 1 and primary_platform_signal_count(candidate) == 0:
        flags.append("weak_confirmation")
    return flags


def enforce_international_primary_source_floor(
    kept_topics: list[dict[str, Any]],
    filtered_out_topics: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    required_platform_topics = min(4, max(0, top_n))
    platform_topics = [topic for topic in kept_topics if primary_platform_signal_count(topic) > 0]
    fallback_topics = [topic for topic in kept_topics if primary_platform_signal_count(topic) == 0]
    if len(platform_topics) < required_platform_topics:
        for topic in fallback_topics:
            filtered_out_topics.append(
                {
                    "title": clean_text(topic.get("title")),
                    "filter_reason": "deprioritized fallback-only topic because top slots require platform-backed topics",
                    "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
                }
            )
        return platform_topics[:top_n]
    return (platform_topics + fallback_topics)[:top_n]


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword.lower() in text)


def matching_keywords(text: str, keywords: list[str]) -> list[str]:
    matches: list[str] = []
    for keyword in keywords:
        lowered = keyword.lower()
        if lowered in text and keyword not in matches:
            matches.append(keyword)
    return matches


def fetch_text(url: str, *, timeout_seconds: int = 10) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def is_google_news_rss_wrapper_url(url: Any) -> bool:
    parsed = urllib.parse.urlparse(clean_text(url))
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return host == "news.google.com" and path.startswith(("/rss/articles/", "/articles/"))


def extract_google_news_wrapper_token(url: Any) -> str:
    parsed = urllib.parse.urlparse(clean_text(url))
    return clean_text(parsed.path.rsplit("/", 1)[-1])


def decode_google_news_wrapper_token(token: str) -> str:
    if not token:
        return ""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, base64.binascii.Error):
        return ""
    field_marker = raw.find(b"\x22")
    if field_marker >= 0 and field_marker + 1 < len(raw):
        length = raw[field_marker + 1]
        payload_start = field_marker + 2
        payload_end = payload_start + length
        if payload_end <= len(raw):
            return clean_text(raw[payload_start:payload_end].decode("utf-8", errors="replace"))
    decoded_text = clean_text(raw.decode("utf-8", errors="replace"))
    match = re.search(r"https?://[^\s\x00-\x1f\"'<>]+", decoded_text)
    return clean_text(match.group(0)) if match else decoded_text


def extract_google_news_decode_params(html_text: str) -> tuple[str, str]:
    timestamp_match = re.search(r'data-n-a-ts=["\']([^"\']+)["\']', html_text)
    signature_match = re.search(r'data-n-a-sg=["\']([^"\']+)["\']', html_text)
    return (
        clean_text(timestamp_match.group(1)) if timestamp_match else "",
        clean_text(signature_match.group(1)) if signature_match else "",
    )


def extract_google_news_batch_execute_url(response_text: str) -> str:
    for chunk in response_text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk.startswith("["):
            continue
        try:
            payload = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, list):
            continue
        for entry in payload:
            if not isinstance(entry, list) or len(entry) < 3 or not isinstance(entry[2], str):
                continue
            try:
                inner = json.loads(entry[2])
            except json.JSONDecodeError:
                continue
            if not isinstance(inner, list) or len(inner) < 2 or inner[0] != "garturlres":
                continue
            candidate = clean_text(inner[1])
            if candidate.startswith(("http://", "https://")) and not is_google_news_rss_wrapper_url(candidate):
                return candidate
    return ""


def resolve_google_news_opaque_wrapper_via_simple_batch_execute(token: str, *, timeout_seconds: int = 8) -> str:
    if not token:
        return ""
    payload = (
        '[[["Fbv4je","[\\"garturlreq\\",[[\\"en-US\\",\\"US\\",[\\"FINANCE_TOP_INDICES\\",\\"WEB_TEST_1_0_0\\"],'
        'null,null,1,1,\\"US:en\\",null,1,null,null,null,null,null,0,1],'
        '\\"en-US\\",\\"US\\",1,[1,1,1],1,1,null,0,0,null,0],\\"'
        + token
        + '\\"]",null,"generic"]]]'
    )
    request = urllib.request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
        data=f"f.req={urllib.parse.quote(payload, safe='')}".encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": "https://news.google.com/",
            "Referrer": "https://news.google.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return extract_google_news_batch_execute_url(response.read().decode("utf-8", errors="replace"))
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        return ""


def extract_google_news_wrapper_page_hints(wrapper_url: str, html_text: str) -> dict[str, Any]:
    canonical_url = ""
    redirect_match = re.search(
        r"https://uberproxy-pen-redirect\.corp\.google\.com/uberproxy/pen\?url=([^\"'&<>\s]+)",
        html_text,
        re.IGNORECASE,
    )
    if redirect_match:
        canonical_url = clean_text(urllib.parse.unquote(unescape(redirect_match.group(1))))

    def extract_meta_content(*names: str) -> str:
        for name in names:
            pattern = re.compile(
                rf"<meta[^>]+(?:property|name)\s*=\s*[\"']{re.escape(name)}[\"'][^>]+content\s*=\s*[\"']([^\"']+)[\"']",
                re.IGNORECASE,
            )
            match = pattern.search(html_text)
            if match:
                return clean_text(unescape(match.group(1)))
        return ""

    image_url = extract_meta_content("og:image", "twitter:image")
    image_alt = extract_meta_content("og:image:alt", "twitter:image:alt")
    artifact_manifest: list[dict[str, Any]] = []
    if image_url:
        artifact_manifest.append(
            {
                "role": "post_media",
                "path": "",
                "source_url": image_url,
                "media_type": "image",
            }
        )
    return {
        "final_url": canonical_url or clean_text(wrapper_url),
        "title": "",
        "text_excerpt": "",
        "post_summary": "",
        "media_summary": image_alt,
        "artifact_manifest": artifact_manifest,
    }


def fetch_google_news_wrapper_page_hints(url: str, *, timeout_seconds: int = 8) -> dict[str, Any]:
    wrapper_url = clean_text(url)
    if not is_google_news_rss_wrapper_url(wrapper_url):
        return {}
    request = urllib.request.Request(
        wrapper_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            try:
                body = response.read(1_000_000)
            except TypeError:
                body = response.read()
            html_text = body.decode("utf-8", errors="replace")
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        return {}
    return extract_google_news_wrapper_page_hints(wrapper_url, html_text)


def resolve_google_news_opaque_wrapper_url(token: str, *, wrapper_url: str = "", timeout_seconds: int = 8) -> str:
    if not token:
        return ""
    simple_resolved = resolve_google_news_opaque_wrapper_via_simple_batch_execute(token, timeout_seconds=timeout_seconds)
    if simple_resolved:
        return simple_resolved
    article_url = f"https://news.google.com/articles/{token}"

    def fetch_wrapper_html(url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            try:
                body = response.read(1_000_000)
            except TypeError:
                body = response.read()
            return body.decode("utf-8", errors="replace")

    try:
        html_text = fetch_wrapper_html(article_url)
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        html_text = ""
    timestamp, signature = extract_google_news_decode_params(html_text)
    decode_page_url = article_url
    if (not timestamp or not signature) and clean_text(wrapper_url):
        try:
            html_text = fetch_wrapper_html(clean_text(wrapper_url))
        except (TimeoutError, ValueError, OSError, urllib.error.URLError):
            html_text = ""
        timestamp, signature = extract_google_news_decode_params(html_text)
        decode_page_url = clean_text(wrapper_url) or article_url
    if not timestamp or not signature:
        return ""
    payload = json.dumps(
        [
            [
                [
                    "Fbv4je",
                    (
                        "[\"garturlreq\",[[\"X\",\"X\",[\"X\",\"X\"],null,null,1,1,\"US:en\",null,1,null,null,null,null,null,0,1],"
                        "\"X\",\"X\",1,[1,1,1],1,1,null,0,0,null,0],"
                        f"\"{token}\",{timestamp},\"{signature}\"]"
                    ),
                ]
            ]
        ],
        separators=(",", ":"),
    )
    request = urllib.request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data=f"f.req={urllib.parse.quote(payload, safe='')}".encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": decode_page_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return extract_google_news_batch_execute_url(response.read().decode("utf-8", errors="replace"))
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        return ""


def resolve_google_news_rss_target_url(url: str, *, timeout_seconds: int = 8) -> str:
    wrapper_url = clean_text(url)
    if not is_google_news_rss_wrapper_url(wrapper_url):
        return wrapper_url

    parsed = urllib.parse.urlparse(wrapper_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    for key in ("url", "article", "u"):
        candidate = clean_text(query_params.get(key, [""])[0])
        if candidate.startswith(("http://", "https://")) and not is_google_news_rss_wrapper_url(candidate):
            return candidate

    token = extract_google_news_wrapper_token(wrapper_url)
    decoded_token = decode_google_news_wrapper_token(token)
    if decoded_token.startswith(("http://", "https://")) and not is_google_news_rss_wrapper_url(decoded_token):
        return decoded_token

    # Newer RSS wrappers store an opaque token that needs a signed Google decode round-trip.
    if decoded_token.startswith("AU_yq"):
        resolved = resolve_google_news_opaque_wrapper_url(token, wrapper_url=wrapper_url, timeout_seconds=timeout_seconds)
        if resolved:
            return resolved

    request = urllib.request.Request(
        wrapper_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            html_text = response.read().decode("utf-8", errors="replace")
            final_url = clean_text(response.geturl() if hasattr(response, "geturl") else "")
    except (TimeoutError, ValueError, OSError, urllib.error.URLError):
        return wrapper_url
    if final_url.startswith(("http://", "https://")) and not is_google_news_rss_wrapper_url(final_url):
        return final_url
    wrapper_hints = extract_google_news_wrapper_page_hints(wrapper_url, html_text)
    hinted_url = clean_text(wrapper_hints.get("final_url"))
    if hinted_url.startswith(("http://", "https://")) and not is_google_news_rss_wrapper_url(hinted_url):
        return hinted_url
    return wrapper_url


def parse_pub_date(value: Any, analysis_time: datetime) -> str:
    if isinstance(value, str):
        direct = parse_datetime(value, fallback=None)
        if direct:
            return isoformat_or_blank(direct)
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return isoformat_or_blank(parsed.astimezone(UTC))
        except (TypeError, ValueError, IndexError):
            pass
    return isoformat_or_blank(analysis_time)


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(text or "")).strip()


def extract_numeric_heat(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = clean_text(value)
    if not text:
        return 0
    digits = re.findall(r"\d+", text.replace(",", ""))
    return int(digits[0]) if digits else 0


def numeric_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_reddit_subreddit(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    normalized = text.lstrip("/")
    if normalized.lower().startswith("r/"):
        return f"r/{normalized[2:].lstrip('/')}"
    return f"r/{normalized}"


def normalize_reddit_user(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    normalized = text.lstrip("/")
    if normalized.lower().startswith("u/"):
        return f"u/{normalized[2:].lstrip('/')}"
    return f"u/{normalized}"


def normalize_reddit_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("/"):
        return urllib.parse.urljoin("https://www.reddit.com", text)
    return text


def is_reddit_url(value: Any) -> bool:
    host = urllib.parse.urlparse(normalize_reddit_url(value)).netloc.lower()
    return "reddit.com" in host


def normalize_reddit_listing(value: Any) -> str:
    text = clean_text(value).lower().replace(".json", "").replace(".rss", "")
    if not text:
        return ""
    text = text.rsplit("/", 1)[-1]
    return REDDIT_LISTING_ALIASES.get(text, "")


def normalize_reddit_listing_window(value: Any) -> str:
    text = clean_text(value).lower().replace("_", "").replace("-", "")
    if not text:
        return ""
    return REDDIT_WINDOW_ALIASES.get(text, "")


def reddit_listing(item: dict[str, Any]) -> str:
    for key in ("listing", "listing_type", "sort", "feed", "ranking", "reddit_listing"):
        listing = normalize_reddit_listing(item.get(key))
        if listing:
            return listing
    return ""


def reddit_listing_window(item: dict[str, Any]) -> str:
    for key in ("listing_window", "time_filter", "window", "period", "t", "reddit_listing_window"):
        window = normalize_reddit_listing_window(item.get(key))
        if window:
            return window
    return ""


def reddit_listing_weight(listing: str, window: str) -> float:
    if listing != "top":
        return 1.0
    return REDDIT_WINDOW_WEIGHT.get(window, 1.0)


def reddit_engagement_value(item: dict[str, Any]) -> float:
    score = max(0.0, numeric_value(item.get("score") or item.get("ups")))
    comments = max(0.0, numeric_value(item.get("num_comments") or item.get("comments_count")))
    crossposts = max(0.0, numeric_value(item.get("num_crossposts")))
    awards = max(0.0, numeric_value(item.get("total_awards") or item.get("total_awards_received")))
    return score + comments * 25 + crossposts * 80 + awards * 40


def reddit_age_hours(item: dict[str, Any], analysis_time: datetime) -> float:
    published = parse_datetime(
        item.get("published_at") or item.get("created_utc") or item.get("created_at") or item.get("timestamp"),
        fallback=analysis_time,
    ) or analysis_time
    return max(0.25, (analysis_time - published).total_seconds() / 3600.0)


def reddit_velocity_score(item: dict[str, Any], analysis_time: datetime) -> int:
    velocity = reddit_engagement_value(item) / reddit_age_hours(item, analysis_time)
    if velocity >= 8000:
        score = 100
    elif velocity >= 4000:
        score = 92
    elif velocity >= 2000:
        score = 82
    elif velocity >= 1000:
        score = 70
    elif velocity >= 500:
        score = 58
    elif velocity >= 250:
        score = 46
    elif velocity >= 120:
        score = 32
    else:
        score = 18
    age_hours = reddit_age_hours(item, analysis_time)
    if age_hours <= 2:
        score += 8
    elif age_hours <= 6:
        score += 4
    return clamp(score)


def reddit_velocity_bucket(score: int) -> str:
    if score >= 85:
        return "surging"
    if score >= 60:
        return "fast"
    if score >= 35:
        return "steady"
    return "slow"


def reddit_source_name(item: dict[str, Any], fallback: str) -> str:
    subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
    return f"Reddit {subreddit}".strip() if subreddit else fallback


def reddit_summary(item: dict[str, Any], title: str) -> str:
    primary = clean_text(
        item.get("summary")
        or item.get("snippet")
        or item.get("description")
        or item.get("selftext")
        or item.get("body")
        or item.get("text")
        or item.get("content")
    )
    top_comment_summary = clean_text(
        item.get("top_comment_summary")
        or item.get("comment_summary")
        or item.get("top_comment_excerpt")
    )
    if primary and top_comment_summary and top_comment_summary.lower() not in primary.lower():
        return clean_text(f"{primary} Top comments: {top_comment_summary}")[:240]
    return primary or top_comment_summary or title


def reddit_heat_score(item: dict[str, Any], analysis_time: datetime) -> int:
    listing = reddit_listing(item)
    window = reddit_listing_window(item)
    velocity = reddit_velocity_score(item, analysis_time)
    base = reddit_engagement_value(item)
    listing_bonus = REDDIT_LISTING_HEAT_BONUS.get(listing, 0) * reddit_listing_weight(listing, window)
    multiplier = reddit_signal_multiplier(item.get("subreddit_name_prefixed") or item.get("subreddit"))
    return int(round((base + listing_bonus + velocity * 45) * multiplier))


def reddit_score_float(item: dict[str, Any], analysis_time: datetime) -> float:
    score = max(0.0, numeric_value(item.get("score") or item.get("ups")))
    comments = max(0.0, numeric_value(item.get("num_comments") or item.get("comments_count")))
    crossposts = max(0.0, numeric_value(item.get("num_crossposts")))
    upvote_ratio = max(0.0, min(1.0, numeric_value(item.get("upvote_ratio"))))
    listing = reddit_listing(item)
    window = reddit_listing_window(item)
    velocity = reddit_velocity_score(item, analysis_time)
    combined = (
        0.2
        + min(0.45, score / 2000.0)
        + min(0.25, comments / 200.0)
        + min(0.10, crossposts / 10.0)
        + min(0.10, max(0.0, upvote_ratio - 0.5) / 0.5 * 0.10)
    )
    combined += min(0.14, velocity / 100.0 * 0.14)
    combined += REDDIT_LISTING_SCORE_BONUS.get(listing, 0.0) * reddit_listing_weight(listing, window)
    combined *= reddit_signal_multiplier(item.get("subreddit_name_prefixed") or item.get("subreddit"))
    return clamp_score_float(combined, default=0.5)


def normalize_discovered_item(item: dict[str, Any], analysis_time: datetime, index: int) -> dict[str, Any]:
    title = clean_text(item.get("title"))
    url = clean_text(item.get("url"))
    if not title or not url:
        raise ValueError("Discovered hot-topic item requires title and url")
    source_name = clean_text(item.get("source_name") or item.get("source") or f"source-{index:02d}")
    source_type = clean_text(item.get("source_type") or "major_news")
    summary = clean_text(item.get("summary") or item.get("snippet") or title)
    published_at = parse_pub_date(item.get("published_at"), analysis_time)
    observed_at = parse_pub_date(item.get("observed_at") or analysis_time.isoformat(), analysis_time)
    normalized = {
        "title": title,
        "summary": summary,
        "url": url,
        "source_name": source_name,
        "source_type": source_type,
        "published_at": published_at,
        "observed_at": observed_at,
        "heat_score": extract_numeric_heat(item.get("heat_score") or item.get("heat") or item.get("engagement")),
        "tags": clean_string_list(item.get("tags")),
    }
    provider = clean_text(item.get("provider"))
    if provider:
        normalized["provider"] = provider
    score_float = item.get("score_float")
    if isinstance(score_float, (int, float)):
        normalized["score_float"] = max(0.0, min(1.0, float(score_float)))
    for key in (
        "publisher_domain_hint",
        "post_summary",
        "media_summary",
        "subreddit",
        "reddit_listing",
        "reddit_listing_window",
        "reddit_author",
        "reddit_subreddit_kind",
        "outbound_domain",
        "top_comment_summary",
        "top_comment_excerpt",
        "top_comment_sort_strategy",
    ):
        value = clean_text(item.get(key))
        if value:
            normalized[key] = value
    top_comment_authors = clean_string_list(item.get("top_comment_authors"))
    if top_comment_authors:
        normalized["top_comment_authors"] = top_comment_authors
    artifact_manifest = safe_list(item.get("artifact_manifest"))
    if artifact_manifest:
        normalized["artifact_manifest"] = artifact_manifest
    comment_near_duplicate_examples = clean_string_list(item.get("comment_near_duplicate_examples"))
    if comment_near_duplicate_examples:
        normalized["comment_near_duplicate_examples"] = comment_near_duplicate_examples
    outbound_url = clean_text(item.get("outbound_url"))
    if outbound_url:
        normalized["outbound_url"] = outbound_url
    velocity_score = item.get("velocity_score")
    if isinstance(velocity_score, (int, float)):
        normalized["velocity_score"] = clamp(float(velocity_score))
    signal_multiplier = item.get("reddit_signal_multiplier")
    if isinstance(signal_multiplier, (int, float)):
        normalized["reddit_signal_multiplier"] = clamp_reddit_signal_multiplier(signal_multiplier)
    if isinstance(item.get("reddit_low_signal"), bool):
        normalized["reddit_low_signal"] = bool(item.get("reddit_low_signal"))
    top_comment_count = item.get("top_comment_count")
    if isinstance(top_comment_count, (int, float)):
        normalized["top_comment_count"] = max(0, int(top_comment_count))
    top_comment_max_score = item.get("top_comment_max_score")
    if isinstance(top_comment_max_score, (int, float)):
        normalized["top_comment_max_score"] = max(0, int(top_comment_max_score))
    comment_raw_count = item.get("comment_raw_count")
    if isinstance(comment_raw_count, (int, float)):
        normalized["comment_raw_count"] = max(0, int(comment_raw_count))
    comment_duplicate_count = item.get("comment_duplicate_count")
    if isinstance(comment_duplicate_count, (int, float)):
        normalized["comment_duplicate_count"] = max(0, int(comment_duplicate_count))
    comment_near_duplicate_count = item.get("comment_near_duplicate_count")
    if isinstance(comment_near_duplicate_count, (int, float)):
        normalized["comment_near_duplicate_count"] = max(0, int(comment_near_duplicate_count))
    comment_near_duplicate_same_author_count = item.get("comment_near_duplicate_same_author_count")
    if isinstance(comment_near_duplicate_same_author_count, (int, float)):
        normalized["comment_near_duplicate_same_author_count"] = max(0, int(comment_near_duplicate_same_author_count))
    comment_near_duplicate_cross_author_count = item.get("comment_near_duplicate_cross_author_count")
    if isinstance(comment_near_duplicate_cross_author_count, (int, float)):
        normalized["comment_near_duplicate_cross_author_count"] = max(0, int(comment_near_duplicate_cross_author_count))
    comment_near_duplicate_level_value = clean_text(item.get("comment_near_duplicate_level"))
    if comment_near_duplicate_level_value:
        normalized["comment_near_duplicate_level"] = comment_near_duplicate_level_value
    comment_near_duplicate_example_count = item.get("comment_near_duplicate_example_count")
    if isinstance(comment_near_duplicate_example_count, (int, float)):
        normalized["comment_near_duplicate_example_count"] = max(0, int(comment_near_duplicate_example_count))
    comment_declared_count = item.get("comment_declared_count")
    if isinstance(comment_declared_count, (int, float)):
        normalized["comment_declared_count"] = max(0, int(comment_declared_count))
    comment_sample_coverage_ratio = item.get("comment_sample_coverage_ratio")
    if isinstance(comment_sample_coverage_ratio, (int, float)):
        normalized["comment_sample_coverage_ratio"] = round(float(comment_sample_coverage_ratio), 4)
    if isinstance(item.get("comment_count_mismatch"), bool):
        normalized["comment_count_mismatch"] = bool(item.get("comment_count_mismatch"))
    comment_operator_review = build_comment_operator_review(normalized)
    if comment_operator_review:
        normalized["comment_operator_review"] = comment_operator_review
    operator_review_priority = build_operator_review_priority(normalized)
    if operator_review_priority:
        normalized["operator_review_priority"] = operator_review_priority
    return normalized


def normalize_title_for_cluster(title: str) -> str:
    text = clean_text(title).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def domain_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    return clean_text(parsed.netloc).lower()


def normalize_cluster_url(url: Any) -> str:
    text = clean_text(url)
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    if not parsed.netloc:
        return text.rstrip("/")
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower(), path, "", "", ""))


def keyword_hits(*texts: str) -> list[str]:
    combined = " ".join(clean_text(text).lower() for text in texts)
    hits = [keyword for keyword in FINANCE_KEYWORDS if keyword in combined]
    return sorted(hits, key=len, reverse=True)


def tokenize_title(title: str) -> list[str]:
    text = clean_text(title)
    latin = re.findall(r"[A-Za-z][A-Za-z0-9\-+]{1,20}", text)
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    tokens = []
    for token in latin + chinese_chunks:
        normalized = token.strip()
        if normalized and normalized not in tokens and normalized not in SEO_STOPWORDS:
            tokens.append(normalized)
    return tokens


def cross_platform_story_tokens(item: dict[str, Any]) -> set[str]:
    combined = " ".join(
        [
            clean_text(item.get("title")),
            clean_text(item.get("summary")),
            clean_text(item.get("text")),
            clean_text(item.get("source_name")),
        ]
    )
    lowered = combined.lower()
    tokens: set[str] = set()
    for token in tokenize_title(combined):
        normalized = token.lower()
        if normalized and normalized not in {value.lower() for value in CROSS_PLATFORM_TOKEN_STOPWORDS}:
            tokens.add(normalized)
    for keyword in CROSS_PLATFORM_STORY_KEYWORDS:
        if keyword.lower() in lowered:
            tokens.add(keyword.lower())
    return tokens


def cross_platform_entity_tokens(tokens: set[str]) -> set[str]:
    return {token for token in tokens if token in {value.lower() for value in CROSS_PLATFORM_ENTITY_TOKENS}}


def is_reddit_discovered_item(item: dict[str, Any]) -> bool:
    if normalize_reddit_subreddit(item.get("subreddit")):
        return True
    source_name = clean_text(item.get("source_name")).lower()
    if source_name.startswith("reddit "):
        return True
    return any(tag == "provider:agent-reach:reddit" or tag.startswith("subreddit:r/") for tag in clean_string_list(item.get("tags")))


def reddit_cluster_outbound_url(item: dict[str, Any]) -> str:
    outbound = normalize_cluster_url(item.get("outbound_url"))
    return outbound if outbound and not is_reddit_url(outbound) else ""


def normalize_reddit_cluster_alias_group(group: Any) -> frozenset[str]:
    aliases = {
        clean_text(alias).lower()
        for alias in safe_list(group)
        if clean_text(alias)
    }
    return frozenset(aliases) if len(aliases) >= 2 else frozenset()


def merge_reddit_cluster_alias_groups(groups: list[frozenset[str]]) -> list[frozenset[str]]:
    merged_groups: list[frozenset[str]] = []
    for group in groups:
        if len(group) < 2:
            continue

        pending = set(group)
        remaining: list[frozenset[str]] = []
        for existing in merged_groups:
            if pending.intersection(existing):
                pending.update(existing)
                continue
            remaining.append(existing)
        remaining.append(frozenset(pending))
        merged_groups = remaining

    ordered_groups: list[frozenset[str]] = []
    seen_groups: set[frozenset[str]] = set()
    for group in merged_groups:
        if group in seen_groups:
            continue
        seen_groups.add(group)
        ordered_groups.append(group)
    return ordered_groups


@lru_cache(maxsize=1)
def load_reddit_cluster_alias_groups() -> tuple[frozenset[str], ...]:
    raw_groups: list[Any] = []
    if REDDIT_CLUSTER_ALIAS_PATH.exists():
        try:
            payload = json.loads(REDDIT_CLUSTER_ALIAS_PATH.read_text(encoding="utf-8-sig"))
            config = safe_dict(payload)
            for key in REDDIT_CLUSTER_ALIAS_CONFIG_KEYS:
                raw_groups.extend(safe_list(config.get(key)))
        except (OSError, ValueError, json.JSONDecodeError):
            raw_groups = []

    normalized_groups = merge_reddit_cluster_alias_groups(
        [normalize_reddit_cluster_alias_group(group) for group in raw_groups]
    )

    if normalized_groups:
        return tuple(normalized_groups)
    return tuple(frozenset(group) for group in DEFAULT_REDDIT_CLUSTER_ALIAS_GROUPS)


def normalize_reddit_subreddit_kind(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


@lru_cache(maxsize=1)
def load_reddit_community_profile_payload() -> dict[str, Any]:
    if REDDIT_COMMUNITY_PROFILE_PATH.exists():
        try:
            return safe_dict(json.loads(REDDIT_COMMUNITY_PROFILE_PATH.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
    return {}


@lru_cache(maxsize=1)
def load_reddit_subreddit_kind_map() -> dict[str, str]:
    kind_groups: dict[str, list[Any]] = {}
    payload = load_reddit_community_profile_payload()
    for key, value in payload.items():
        if key.endswith("_subreddits") and key != "low_signal_subreddits":
            kind_groups.setdefault(normalize_reddit_subreddit_kind(key[: -len("_subreddits")]), []).extend(safe_list(value))
    for key, value in safe_dict(payload.get("subreddit_kind_groups")).items():
        kind_groups.setdefault(normalize_reddit_subreddit_kind(key), []).extend(safe_list(value))

    mapping: dict[str, str] = {}
    for kind, entries in kind_groups.items():
        if not kind:
            continue
        for entry in entries:
            subreddit = normalize_reddit_subreddit(entry).lower()
            if subreddit:
                mapping[subreddit] = kind

    if mapping:
        return mapping

    fallback: dict[str, str] = {}
    for kind, entries in DEFAULT_REDDIT_SUBREDDIT_KIND_GROUPS.items():
        normalized_kind = normalize_reddit_subreddit_kind(kind)
        for entry in entries:
            subreddit = normalize_reddit_subreddit(entry).lower()
            if subreddit and normalized_kind:
                fallback[subreddit] = normalized_kind
    return fallback


def reddit_subreddit_kind(value: Any) -> str:
    subreddit = normalize_reddit_subreddit(value).lower()
    return load_reddit_subreddit_kind_map().get(subreddit, "")


def clamp_reddit_signal_multiplier(value: Any, default: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.75, min(1.15, number))


@lru_cache(maxsize=1)
def load_reddit_kind_score_multipliers() -> dict[str, float]:
    payload = load_reddit_community_profile_payload()
    raw = safe_dict(payload.get("kind_score_multipliers"))
    mapping: dict[str, float] = {}
    for key, value in raw.items():
        kind = normalize_reddit_subreddit_kind(key)
        if kind:
            mapping[kind] = clamp_reddit_signal_multiplier(value)
    if mapping:
        return mapping
    return {
        "broad_market": 1.0,
        "deep_research": 1.06,
        "speculative_flow": 0.88,
        "event_watch": 0.96,
    }


@lru_cache(maxsize=1)
def load_reddit_subreddit_score_overrides() -> dict[str, float]:
    payload = load_reddit_community_profile_payload()
    raw = safe_dict(payload.get("subreddit_score_overrides"))
    mapping: dict[str, float] = {}
    for key, value in raw.items():
        subreddit = normalize_reddit_subreddit(key).lower()
        if subreddit:
            mapping[subreddit] = clamp_reddit_signal_multiplier(value)
    if mapping:
        return mapping
    return {"r/wallstreetbets": 0.86}


@lru_cache(maxsize=1)
def load_reddit_low_signal_subreddits() -> set[str]:
    payload = load_reddit_community_profile_payload()
    configured = {
        normalize_reddit_subreddit(value).lower()
        for value in safe_list(payload.get("low_signal_subreddits"))
        if normalize_reddit_subreddit(value)
    }
    if configured:
        return configured
    return {"r/wallstreetbets"}


def reddit_signal_multiplier(value: Any) -> float:
    subreddit = normalize_reddit_subreddit(value).lower()
    if not subreddit:
        return 1.0
    override = load_reddit_subreddit_score_overrides().get(subreddit)
    if override is not None:
        return override
    kind = reddit_subreddit_kind(subreddit)
    return load_reddit_kind_score_multipliers().get(kind, 1.0)


def reddit_is_low_signal_subreddit(value: Any) -> bool:
    subreddit = normalize_reddit_subreddit(value).lower()
    return bool(subreddit) and subreddit in load_reddit_low_signal_subreddits()


@lru_cache(maxsize=1)
def reddit_cluster_alias_map() -> dict[str, frozenset[str]]:
    mapping: dict[str, frozenset[str]] = {}
    for group in load_reddit_cluster_alias_groups():
        for alias in group:
            mapping[alias] = group
    return mapping


def expand_reddit_cluster_aliases(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        expanded.update(reddit_cluster_alias_map().get(token, {token}))
    return expanded


def is_chinese_cluster_token(token: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", token))


def reddit_cluster_tokens(item: dict[str, Any]) -> set[str]:
    tokens: list[str] = []
    for text in (item.get("title"), item.get("summary")):
        for token in tokenize_title(clean_text(text)):
            normalized = token.lower()
            if len(normalized) > 4 and normalized.endswith("ies"):
                normalized = f"{normalized[:-3]}y"
            elif len(normalized) > 4 and normalized.endswith("s") and not normalized.endswith("ss"):
                normalized = normalized[:-1]
            if normalized in REDDIT_CLUSTER_TOKEN_STOPWORDS:
                continue
            minimum_length = 2 if is_chinese_cluster_token(normalized) else 4
            if len(normalized) < minimum_length and normalized not in REDDIT_CLUSTER_SHORT_TOKENS:
                continue
            if normalized not in tokens:
                tokens.append(normalized)
    return expand_reddit_cluster_aliases(set(tokens[:12]))


def reddit_cluster_query_tokens(query: Any) -> set[str]:
    text = clean_text(query)
    if not text:
        return set()
    return reddit_cluster_tokens({"title": text, "summary": ""})


def reddit_cluster_shared_tokens(item_tokens: set[str], cluster_tokens: set[str]) -> set[str]:
    return item_tokens & cluster_tokens


def reddit_cluster_token_overlap(item_tokens: set[str], cluster_tokens: set[str]) -> bool:
    shared = reddit_cluster_shared_tokens(item_tokens, cluster_tokens)
    if len(shared) >= 3:
        return True
    return len(shared) >= 2 and any(len(token) >= 5 for token in shared)


def reddit_cluster_matches_query(shared_tokens: set[str], query_tokens: set[str]) -> bool:
    if not shared_tokens:
        return False
    if not query_tokens:
        return True
    overlaps = shared_tokens & query_tokens
    if not overlaps:
        return False
    if overlaps - REDDIT_CLUSTER_GENERIC_QUERY_TOKENS:
        return True
    return len(overlaps) >= 2


def reddit_cluster_query_overlap(tokens: set[str], query_tokens: set[str]) -> set[str]:
    if not tokens or not query_tokens:
        return set()
    return tokens & query_tokens


def reddit_cluster_query_entity_groups(query_tokens: set[str]) -> set[frozenset[str]]:
    groups: set[frozenset[str]] = set()
    alias_map = reddit_cluster_alias_map()
    for token in query_tokens:
        group = alias_map.get(token)
        if group and group & query_tokens:
            groups.add(group)
    return groups


def reddit_cluster_token_entity_groups(tokens: set[str], query_entity_groups: set[frozenset[str]]) -> set[frozenset[str]]:
    matched: set[frozenset[str]] = set()
    for group in query_entity_groups:
        if tokens & group:
            matched.add(group)
    return matched


def reddit_cluster_has_strong_query_match(tokens: set[str], query_tokens: set[str]) -> bool:
    overlaps = reddit_cluster_query_overlap(tokens, query_tokens)
    if len(overlaps) >= 2:
        return True
    return any(len(token) >= 5 for token in overlaps)


def new_item_cluster(title_key: str, item: dict[str, Any]) -> dict[str, Any]:
    story_tokens = cross_platform_story_tokens(item)
    return {
        "title_keys": {title_key} if title_key else set(),
        "reddit_outbound_urls": {reddit_cluster_outbound_url(item)} if reddit_cluster_outbound_url(item) else set(),
        "reddit_tokens": reddit_cluster_tokens(item) if is_reddit_discovered_item(item) else set(),
        "story_tokens": story_tokens,
        "entity_tokens": cross_platform_entity_tokens(story_tokens),
        "items": [item],
    }


def merge_item_into_cluster(cluster: dict[str, Any], title_key: str, item: dict[str, Any]) -> None:
    if title_key:
        cluster["title_keys"].add(title_key)
    outbound_url = reddit_cluster_outbound_url(item)
    if outbound_url:
        cluster["reddit_outbound_urls"].add(outbound_url)
    if is_reddit_discovered_item(item):
        cluster["reddit_tokens"].update(reddit_cluster_tokens(item))
    story_tokens = cross_platform_story_tokens(item)
    cluster["story_tokens"].update(story_tokens)
    cluster["entity_tokens"].update(cross_platform_entity_tokens(story_tokens))
    cluster["items"].append(item)


def cluster_discovered_items(raw_items: list[dict[str, Any]], query: Any = "") -> list[list[dict[str, Any]]]:
    clusters: list[dict[str, Any]] = []
    query_tokens = reddit_cluster_query_tokens(query)
    query_entity_groups = reddit_cluster_query_entity_groups(query_tokens)
    for item in raw_items:
        title_key = normalize_title_for_cluster(item.get("title", ""))
        item_is_reddit = is_reddit_discovered_item(item)
        item_outbound_url = reddit_cluster_outbound_url(item) if item_is_reddit else ""
        item_tokens = reddit_cluster_tokens(item) if item_is_reddit else set()
        item_entity_groups = reddit_cluster_token_entity_groups(item_tokens, query_entity_groups) if item_is_reddit else set()
        item_story_tokens = cross_platform_story_tokens(item)
        item_entity_tok = cross_platform_entity_tokens(item_story_tokens)

        matching_indexes: list[int] = []
        for index, cluster in enumerate(clusters):
            if title_key and title_key in cluster["title_keys"]:
                matching_indexes.append(index)
                continue
            # Entity-based match — for cross-platform pairs and non-Reddit-to-non-Reddit pairs.
            # Skipped when both item and cluster are Reddit-only (use Reddit-specific path instead).
            cluster_all_reddit = bool(cluster.get("reddit_tokens")) and all(is_reddit_discovered_item(ci) for ci in cluster["items"])
            skip_entity_match = item_is_reddit and cluster_all_reddit
            if not skip_entity_match:
                shared_entities = item_entity_tok & cluster.get("entity_tokens", set())
                shared_story = item_story_tokens & cluster.get("story_tokens", set())
                if shared_entities and len(shared_story) >= 2:
                    matching_indexes.append(index)
                    continue
            if not item_is_reddit:
                continue
            if item_outbound_url and item_outbound_url in cluster["reddit_outbound_urls"]:
                matching_indexes.append(index)
                continue
            if not query_tokens:
                continue
            shared_tokens = reddit_cluster_shared_tokens(item_tokens, cluster["reddit_tokens"])
            cluster_entity_groups = reddit_cluster_token_entity_groups(cluster["reddit_tokens"], query_entity_groups)
            allow_strong_query_fallback = (
                reddit_cluster_has_strong_query_match(item_tokens, query_tokens)
                and reddit_cluster_has_strong_query_match(cluster["reddit_tokens"], query_tokens)
                and (
                    len(query_entity_groups) <= 1
                    or bool(item_entity_groups & cluster_entity_groups)
                )
            )
            if (
                shared_tokens
                and reddit_cluster_token_overlap(item_tokens, cluster["reddit_tokens"])
                and (
                    reddit_cluster_matches_query(shared_tokens, query_tokens)
                    or allow_strong_query_fallback
                )
            ):
                matching_indexes.append(index)

        if not matching_indexes:
            clusters.append(new_item_cluster(title_key, item))
            continue

        primary_index = matching_indexes[0]
        primary_cluster = clusters[primary_index]
        merge_item_into_cluster(primary_cluster, title_key, item)
        for merged_index in reversed(matching_indexes[1:]):
            secondary_cluster = clusters.pop(merged_index)
            primary_cluster["title_keys"].update(secondary_cluster["title_keys"])
            primary_cluster["reddit_outbound_urls"].update(secondary_cluster["reddit_outbound_urls"])
            primary_cluster["reddit_tokens"].update(secondary_cluster["reddit_tokens"])
            primary_cluster["story_tokens"].update(secondary_cluster.get("story_tokens", set()))
            primary_cluster["entity_tokens"].update(secondary_cluster.get("entity_tokens", set()))
            primary_cluster["items"].extend(secondary_cluster["items"])

    return [cluster["items"] for cluster in clusters]


def fetch_weibo(limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    raw_text = fetch_text("https://weibo.com/ajax/side/hotSearch")
    payload = json.loads(raw_text)
    items = safe_list(safe_dict(payload.get("data")).get("realtime"))
    discovered = []
    for index, item in enumerate(items[:limit], start=1):
        title = clean_text(item.get("note") or item.get("word"))
        if not title:
            continue
        discovered.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": clean_text(item.get("label_name") or title),
                    "url": f"https://s.weibo.com/weibo?q={urllib.parse.quote(title)}",
                    "source_name": "weibo",
                    "source_type": "social",
                    "published_at": analysis_time.isoformat(),
                    "heat_score": item.get("num"),
                    "tags": [clean_text(item.get("label_name"))] if clean_text(item.get("label_name")) else [],
                },
                analysis_time,
                index,
            )
        )
    return discovered


def fetch_zhihu(limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    zhihu_cookie = os.environ.get("ZHIHU_COOKIE", "")
    zhihu_url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    if zhihu_cookie:
        req = urllib.request.Request(
            zhihu_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Cookie": zhihu_cookie,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")
    else:
        raw_text = fetch_text(zhihu_url)
    payload = json.loads(raw_text)
    items = safe_list(payload.get("data"))
    discovered = []
    for index, item in enumerate(items[:limit], start=1):
        target = safe_dict(item.get("target"))
        title = clean_text(target.get("title") or item.get("title"))
        if not title:
            continue
        question_id = clean_text(target.get("id") or item.get("id"))
        url = f"https://www.zhihu.com/question/{question_id}" if question_id else clean_text(item.get("url"))
        if not url:
            continue
        discovered.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": clean_text(item.get("excerpt") or item.get("detail_text") or title),
                    "url": url,
                    "source_name": "zhihu",
                    "source_type": "social",
                    "published_at": analysis_time.isoformat(),
                    "heat_score": item.get("detail_text"),
                },
                analysis_time,
                index,
            )
        )
    return discovered


def fetch_36kr(limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    html = fetch_text("https://36kr.com/newsflashes")
    matches = re.findall(r'href="(/p/\d+[^"]*)"[^>]*>([^<]{6,120})</a>', html)
    discovered = []
    for index, (href, title) in enumerate(matches[:limit], start=1):
        discovered.append(
            normalize_discovered_item(
                {
                    "title": strip_tags(title),
                    "summary": strip_tags(title),
                    "url": urllib.parse.urljoin("https://36kr.com", href),
                    "source_name": "36kr",
                    "source_type": "major_news",
                    "published_at": analysis_time.isoformat(),
                },
                analysis_time,
                index,
            )
        )
    return discovered


def parse_rss_items(xml_text: str, source_name: str, source_type: str, limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    discovered = []
    for index, item in enumerate(root.findall(".//item")[:limit], start=1):
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        if not title or not link:
            continue
        effective_source_name = source_name
        clean_title = title
        if source_name in {"google-news-search", "google-news-world"} and " - " in title:
            possible_title, possible_source = [clean_text(part) for part in title.rsplit(" - ", 1)]
            if possible_title and possible_source and len(possible_source) <= 40:
                clean_title = possible_title
                effective_source_name = possible_source
        summary_text = strip_tags(item.findtext("description") or clean_title)
        if source_name in {"google-news-search", "google-news-world"}:
            if summary_text == title:
                summary_text = clean_title
            elif effective_source_name and summary_text.endswith(effective_source_name):
                summary_text = clean_text(re.sub(rf"[\s\-|_:：]+{re.escape(effective_source_name)}$", "", summary_text))
        publisher_domain_hint = effective_source_name if source_name in {"google-news-search", "google-news-world"} else ""
        resolved_link = resolve_google_news_rss_target_url(link) if is_google_news_rss_wrapper_url(link) else link
        wrapper_hints = fetch_google_news_wrapper_page_hints(link) if source_name in {"google-news-search", "google-news-world"} else {}
        discovered.append(
            normalize_discovered_item(
                {
                    "title": clean_title,
                    "summary": summary_text,
                    "url": resolved_link or link,
                    "source_name": effective_source_name,
                    "publisher_domain_hint": publisher_domain_hint,
                    "post_summary": clean_text(wrapper_hints.get("post_summary")),
                    "media_summary": clean_text(wrapper_hints.get("media_summary")),
                    "artifact_manifest": safe_list(wrapper_hints.get("artifact_manifest")),
                    "source_type": source_type,
                    "published_at": item.findtext("pubDate") or analysis_time.isoformat(),
                },
                analysis_time,
                index,
            )
        )
    return discovered


def fetch_google_news_world(limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    xml_text = fetch_text("https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
    return parse_rss_items(xml_text, "google-news-world", "major_news", limit, analysis_time)


def fetch_google_news_search(query: str, limit: int, analysis_time: datetime) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    xml_text = fetch_text(url)
    return parse_rss_items(xml_text, "google-news-search", "major_news", limit, analysis_time)


def clamp_score_float(value: Any, default: float = 0.5) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return default


def clean_x_title(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = re.sub(r"^(?:@\w+\s+)+", "", text)
    text = re.sub(r"https?://\S+", "", text).strip()
    text = clean_text(text)
    if not text:
        return ""
    sentence_parts = re.split(r"(?<=[.!?！？])\s+|\n+", text)
    for part in sentence_parts:
        candidate = clean_text(part).rstrip(".!?！？")
        if candidate:
            return candidate[:120]
    return text[:120]


def normalize_agent_reach_items(source_name: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    family = source_name.split(":", 1)[1]
    query = clean_text(request.get("query") or request.get("topic"))
    if not query and family not in {"reddit", "x"}:
        raise ValueError(f"{source_name} requires query or topic")
    fetch_result = fetch_agent_reach_channels(
        {
            "topic": query,
            "analysis_time": request["analysis_time"].isoformat(),
            "channels": [family],
            "pseudo_home": request.get("agent_reach_pseudo_home"),
            "timeout_per_channel": request.get("agent_reach_timeout_per_channel", 30),
            "max_results_per_channel": request.get("agent_reach_max_results_per_channel", request.get("limit", 10)),
            "channel_payloads": safe_dict(request.get("agent_reach_channel_payloads")),
            "channel_result_paths": safe_dict(request.get("agent_reach_channel_result_paths")),
            "channel_commands": safe_dict(request.get("agent_reach_channel_commands")),
            "rss_feeds": safe_list(request.get("agent_reach_rss_feeds")),
            "dedupe_store_path": request.get("agent_reach_dedupe_store_path"),
        }
    )
    if fetch_result.get("channels_failed"):
        reason = clean_text(safe_list(fetch_result["channels_failed"])[0].get("reason"))
        raise ValueError(f"{source_name} fetch failed: {reason or 'unknown error'}")
    channel_result = safe_dict(fetch_result.get("results_by_channel", {}).get(family))
    items = [item for item in safe_list(channel_result.get("items")) if isinstance(item, dict)]
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items[: request["limit"]], start=1):
        if family == "x" and clean_text(item.get("inReplyToStatusId") or item.get("in_reply_to_status_id")):
            continue
        author = safe_dict(item.get("author"))
        x_author_handle = clean_text(
            item.get("author_handle")
            or item.get("handle")
            or item.get("username")
            or author.get("username")
        ).lstrip("@")
        title = clean_text(
            item.get("title")
            or item.get("name")
            or item.get("full_name")
            or item.get("fullName")
            or item.get("nameWithOwner")
            or item.get("headline")
            or item.get("text")
        )
        raw_url = clean_text(item.get("url") or item.get("html_url") or item.get("webpage_url") or item.get("link"))
        permalink = clean_text(item.get("permalink") or item.get("post_permalink"))
        url = clean_text(raw_url or permalink)
        outbound_url = ""
        if family == "youtube" and not url and clean_text(item.get("id")):
            url = f"https://www.youtube.com/watch?v={clean_text(item.get('id'))}"
        if family == "reddit":
            if not title:
                title = clean_text(item.get("selftext") or item.get("body") or item.get("content") or item.get("text"))[:160]
            permalink = normalize_reddit_url(permalink)
            outbound_url = clean_text(item.get("outbound_url"))
            if raw_url and not is_reddit_url(raw_url) and not outbound_url:
                outbound_url = raw_url
            url = permalink or normalize_reddit_url(raw_url)
            if not url:
                subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
                post_id = clean_text(item.get("id") or item.get("post_id"))
                if subreddit and post_id:
                    url = f"https://www.reddit.com/{subreddit}/comments/{post_id}/"
        if family == "x":
            post_id = clean_text(item.get("id") or item.get("tweet_id") or item.get("status_id"))
            if not url and post_id:
                if x_author_handle:
                    url = f"https://x.com/{x_author_handle}/status/{post_id}"
                else:
                    url = f"https://x.com/i/web/status/{post_id}"
            if title:
                title = clean_x_title(title)
        if family == "github" and title and clean_text(item.get("description")):
            title = f"{title} - {clean_text(item.get('description'))}"[:160]
        if not title or not url:
            continue
        score_float = 0.5
        heat_score = int(round(score_float * 100))
        tags: list[str] = []
        normalized_source_name = source_name
        source_type = "social" if family in {"youtube", "x", "wechat", "reddit"} else "community" if family == "github" else "major_news"
        subreddit = ""
        listing = ""
        listing_window = ""
        velocity_score = 0
        reddit_author = ""
        reddit_subreddit_kind_value = ""
        outbound_domain = ""
        reddit_signal_multiplier_value = 1.0
        reddit_low_signal = False
        if family == "github":
            score_float = clamp_score_float((item.get("stargazersCount") or item.get("stars") or 0) / 10000 if isinstance(item.get("stargazersCount") or item.get("stars"), (int, float)) else 0.5)
            heat_score = int(round(score_float * 100))
        elif family == "youtube":
            tags = ["video"]
            heat_score = int(round(score_float * 100))
        elif family == "reddit":
            normalized_source_name = reddit_source_name(item, source_name)
            subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
            listing = reddit_listing(item)
            listing_window = reddit_listing_window(item)
            velocity_score = reddit_velocity_score(item, request["analysis_time"])
            reddit_author = normalize_reddit_user(item.get("author") or item.get("username"))
            reddit_subreddit_kind_value = reddit_subreddit_kind(subreddit)
            reddit_signal_multiplier_value = reddit_signal_multiplier(subreddit)
            reddit_low_signal = reddit_is_low_signal_subreddit(subreddit)
            score_float = reddit_score_float(item, request["analysis_time"])
            heat_score = reddit_heat_score(item, request["analysis_time"]) or int(round(score_float * 100))
            tags = ["community"]
            if subreddit:
                tags.append(f"subreddit:{subreddit}")
            if reddit_subreddit_kind_value:
                tags.append(f"subreddit_kind:{reddit_subreddit_kind_value}")
            if reddit_low_signal:
                tags.append("subreddit_signal:low")
            if listing:
                tags.append(f"listing:{listing}")
            if listing_window:
                tags.append(f"listing_window:{listing_window}")
            tags.append(f"velocity:{reddit_velocity_bucket(velocity_score)}")
            outbound_domain = domain_from_url(outbound_url)
            if outbound_domain:
                tags.append(f"outbound_domain:{outbound_domain}")
        elif family == "x":
            normalized_source_name = f"X @{x_author_handle}" if x_author_handle else "X"
        elif family == "semantic":
            score_float = clamp_score_float(item.get("similarity_score"), default=0.5)
            heat_score = int(round(score_float * 100))
        normalized.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": reddit_summary(item, title) if family == "reddit" else clean_text(item.get("summary") or item.get("snippet") or item.get("description") or title),
                    "url": url,
                    "source_name": normalized_source_name,
                    "source_type": source_type,
                    "published_at": item.get("published_at") or item.get("updatedAt") or item.get("createdAt") or item.get("created_at") or item.get("created_utc") or item.get("pubDate") or request["analysis_time"].isoformat(),
                    "heat_score": heat_score,
                    "tags": tags + [f"provider:{source_name}"],
                    "provider": source_name,
                    "score_float": score_float,
                    "subreddit": subreddit if family == "reddit" else "",
                    "reddit_listing": listing if family == "reddit" else "",
                    "reddit_listing_window": listing_window if family == "reddit" else "",
                    "reddit_author": reddit_author if family == "reddit" else "",
                    "reddit_subreddit_kind": reddit_subreddit_kind_value if family == "reddit" else "",
                    "velocity_score": velocity_score if family == "reddit" else 0,
                    "outbound_url": outbound_url if family == "reddit" else "",
                    "outbound_domain": outbound_domain if family == "reddit" else "",
                    "reddit_signal_multiplier": reddit_signal_multiplier_value if family == "reddit" else 1.0,
                    "reddit_low_signal": reddit_low_signal if family == "reddit" else False,
                    "top_comment_summary": clean_text(item.get("top_comment_summary")) if family == "reddit" else "",
                    "top_comment_excerpt": clean_text(item.get("top_comment_excerpt")) if family == "reddit" else "",
                    "top_comment_sort_strategy": clean_text(item.get("top_comment_sort_strategy")) if family == "reddit" else "",
                    "top_comment_count": item.get("top_comment_count") if family == "reddit" else 0,
                    "top_comment_authors": clean_string_list(item.get("top_comment_authors")) if family == "reddit" else [],
                    "top_comment_max_score": item.get("top_comment_max_score") if family == "reddit" else 0,
                    "comment_raw_count": item.get("comment_raw_count") if family == "reddit" else 0,
                    "comment_duplicate_count": item.get("comment_duplicate_count") if family == "reddit" else 0,
                    "comment_near_duplicate_count": item.get("comment_near_duplicate_count") if family == "reddit" else 0,
                    "comment_near_duplicate_same_author_count": item.get("comment_near_duplicate_same_author_count") if family == "reddit" else 0,
                    "comment_near_duplicate_cross_author_count": item.get("comment_near_duplicate_cross_author_count") if family == "reddit" else 0,
                    "comment_near_duplicate_level": clean_text(item.get("comment_near_duplicate_level")) if family == "reddit" else "",
                    "comment_near_duplicate_examples": clean_string_list(item.get("comment_near_duplicate_examples")) if family == "reddit" else [],
                    "comment_near_duplicate_example_count": item.get("comment_near_duplicate_example_count") if family == "reddit" else 0,
                    "comment_declared_count": item.get("comment_declared_count") if family == "reddit" else 0,
                    "comment_sample_coverage_ratio": item.get("comment_sample_coverage_ratio") if family == "reddit" else 0.0,
                    "comment_count_mismatch": bool(item.get("comment_count_mismatch")) if family == "reddit" else False,
                },
                request["analysis_time"],
                index,
            )
        )
    return normalized


def fetch_source_items(source_name: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(request.get("limit", 10) or 10)
    analysis_time = request["analysis_time"]
    if source_name == "weibo":
        return fetch_weibo(limit, analysis_time)
    if source_name == "zhihu":
        return fetch_zhihu(limit, analysis_time)
    if source_name == "36kr":
        return fetch_36kr(limit, analysis_time)
    if source_name == "google-news-world":
        return fetch_google_news_world(limit, analysis_time)
    if source_name == "google-news-search":
        query = clean_text(request.get("query") or request.get("topic"))
        if not query:
            raise ValueError("google-news-search requires query or topic")
        return fetch_google_news_search(query, limit, analysis_time)
    if source_name.startswith("agent-reach:"):
        return normalize_agent_reach_items(source_name, request)
    if source_name.startswith("rss:"):
        url = source_name[4:]
        return parse_rss_items(fetch_text(url), "rss", "major_news", limit, analysis_time)
    raise ValueError(f"Unsupported discovery source: {source_name}")


def normalize_agent_reach_sources(raw_payload: dict[str, Any]) -> list[str]:
    explicit = [f"agent-reach:{normalize_channel}" for normalize_channel in [clean_text(item).lower() for item in safe_list(raw_payload.get("agent_reach_families"))] if normalize_channel]
    env_value = clean_text(os.environ.get(AGENT_REACH_ENV_VAR))
    env_sources = [f"agent-reach:{clean_text(item).lower()}" for item in env_value.split(",") if clean_text(item)]
    seen: list[str] = []
    for source in explicit + env_sources:
        if source not in seen:
            seen.append(source)
    return seen


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    discovery_profile = clean_text(raw_payload.get("discovery_profile")).lower() or "default"
    is_live_snapshot = discovery_profile == "live_snapshot"
    explicit_sources = clean_string_list(raw_payload.get("sources"))
    sources = explicit_sources or (
        list(INTERNATIONAL_PRIMARY_SOURCES + INTERNATIONAL_FALLBACK_SOURCES)
        if discovery_profile == "international_first"
        else (list(LIVE_SNAPSHOT_SOURCES) if is_live_snapshot else list(DEFAULT_DISCOVERY_SOURCES))
    )
    agent_reach_sources = normalize_agent_reach_sources(raw_payload)
    manual_topic_candidates = [
        item for item in safe_list(raw_payload.get("manual_topic_candidates") or raw_payload.get("topics")) if isinstance(item, dict)
    ]
    query = clean_text(raw_payload.get("query") or raw_payload.get("topic"))
    if query and not manual_topic_candidates and not clean_string_list(raw_payload.get("sources")):
        sources = ["google-news-search"]
    for source in agent_reach_sources:
        if source not in sources:
            sources.append(source)
    return {
        "analysis_time": analysis_time,
        "discovery_profile": discovery_profile,
        "sources": sources,
        "limit": max(
            1,
            int(raw_payload.get("limit", LIVE_SNAPSHOT_DEFAULT_LIMIT if is_live_snapshot else 10) or 10),
        ),
        "top_n": max(
            1,
            int(raw_payload.get("top_n", LIVE_SNAPSHOT_DEFAULT_TOP_N if is_live_snapshot else 5) or 5),
        ),
        "query": query,
        "audience_keywords": clean_string_list(raw_payload.get("audience_keywords")),
        "preferred_topic_keywords": clean_string_list(
            raw_payload.get("preferred_topic_keywords")
            or raw_payload.get("topic_preferences")
            or raw_payload.get("preferred_keywords")
        ),
        "excluded_topic_keywords": clean_string_list(
            raw_payload.get("excluded_topic_keywords") or raw_payload.get("exclude_keywords")
        ),
        "topic_score_weights": normalize_topic_score_weights(
            raw_payload.get("topic_score_weights") or raw_payload.get("score_weights")
        ),
        "min_total_score": max(0, int(raw_payload.get("min_total_score", 0) or 0)),
        "min_source_count": max(0, int(raw_payload.get("min_source_count", 0) or 0)),
        "manual_topic_candidates": manual_topic_candidates,
        "max_parallel_sources": max(
            1,
            int(
                raw_payload.get(
                    "max_parallel_sources",
                    LIVE_SNAPSHOT_DEFAULT_MAX_PARALLEL_SOURCES if is_live_snapshot else min(4, len(sources)),
                )
                or 1
            ),
        ),
        "agent_reach_timeout_per_channel": max(1, int(raw_payload.get("agent_reach_timeout_per_channel", 30) or 1)),
        "agent_reach_max_results_per_channel": max(1, int(raw_payload.get("agent_reach_max_results_per_channel", raw_payload.get("limit", 10)) or 1)),
        "agent_reach_pseudo_home": clean_text(raw_payload.get("agent_reach_pseudo_home")),
        "agent_reach_channel_payloads": safe_dict(raw_payload.get("agent_reach_channel_payloads")),
        "agent_reach_channel_result_paths": safe_dict(raw_payload.get("agent_reach_channel_result_paths")),
        "agent_reach_channel_commands": safe_dict(raw_payload.get("agent_reach_channel_commands")),
        "agent_reach_rss_feeds": safe_list(raw_payload.get("agent_reach_rss_feeds")),
        "agent_reach_dedupe_store_path": raw_payload.get("agent_reach_dedupe_store_path"),
    }


def age_minutes(analysis_time: datetime, published_at: str) -> float:
    published = parse_datetime(published_at, fallback=analysis_time) or analysis_time
    return max(0.0, (analysis_time - published).total_seconds() / 60.0)


def discussion_score(title: str, source_count: int) -> int:
    text = clean_text(title).lower()
    keyword_bonus = 25 if any(keyword in text for keyword in DEBATE_KEYWORDS) else 0
    punctuation_bonus = 10 if "？" in title or "?" in title or "！" in title or "!" in title else 0
    source_bonus = min(45, source_count * 15)
    return clamp(20 + keyword_bonus + punctuation_bonus + source_bonus)


def seo_score(title: str, keywords: list[str]) -> int:
    length = len(clean_text(title))
    if 10 <= length <= 28:
        length_score = 40
    elif 8 <= length <= 36:
        length_score = 30
    else:
        length_score = 18
    token_score = min(40, len(keywords) * 12)
    specificity_bonus = 15 if re.search(r"\d|AI|Agent|IPO|OpenAI|Claude", title, re.IGNORECASE) else 0
    return clamp(length_score + token_score + specificity_bonus)


def relevance_score(candidate: dict[str, Any], audience_keywords: list[str], preferred_topic_keywords: list[str]) -> int:
    combined = candidate_match_text(candidate)
    finance_hits = len(keyword_hits(combined))
    audience_hits = keyword_hit_count(combined, audience_keywords)
    preference_hits = keyword_hit_count(combined, preferred_topic_keywords)
    source_bonus = (
        8
        if int(candidate.get("source_count", 0) or 0) > 1
        and any(name in {"36kr", "google-news-world", "google-news-search"} for name in candidate.get("source_names", []))
        else 0
    )
    preference_bonus = min(24, preference_hits * 12)
    disambiguation_bonus = 10 if is_rumor_like_candidate(candidate) and contains_any_keyword(combined, {"claude", "anthropic", "openai"}) else 0
    return clamp(20 + finance_hits * 15 + audience_hits * 18 + source_bonus + preference_bonus + disambiguation_bonus)


def positive_feedback_topic_signals(candidate: dict[str, Any]) -> dict[str, bool]:
    title = clean_text(candidate.get("title"))
    text = " ".join(
        [
            candidate_match_text(candidate),
            clean_text(candidate.get("recommended_angle")),
            clean_text(candidate.get("why_now")),
        ]
    ).lower()
    return {
        "hard_industry": contains_any_keyword(text, POSITIVE_FEEDBACK_HARD_INDUSTRY_KEYWORDS),
        "clear_actor": contains_any_keyword(text, POSITIVE_FEEDBACK_CLEAR_ACTOR_KEYWORDS),
        "contrarian_frame": any(marker in title.lower() for marker in POSITIVE_FEEDBACK_CONTRARIAN_MARKERS),
        "china_or_market_relevance": contains_any_keyword(text, POSITIVE_FEEDBACK_CHINA_MARKET_KEYWORDS),
    }


def positive_feedback_topic_bonus(candidate: dict[str, Any]) -> int:
    signals = positive_feedback_topic_signals(candidate)
    bonus = 0
    if signals["hard_industry"]:
        bonus += 3
    if signals["clear_actor"]:
        bonus += 3
    if signals["contrarian_frame"]:
        bonus += 5  # raised from 3 to 5 for contrarian signal amplification
    if signals["china_or_market_relevance"]:
        bonus += 3
    return min(14, bonus)


# ---------------------------------------------------------------------------
# Information Gap & X Author Signal — Phase 3 additions
# ---------------------------------------------------------------------------

# X watchlist authors and their focus areas.
# Maintained in sync with x-stock-picker-style-subject-registry and author-discovery.md.
# source: "manual" = operator hand-picked (highest trust, used for trade-plan input)
#          "auto"   = community-recommended (monitor-only, signal enrichment)
X_WATCHLIST_AUTHORS: dict[str, dict[str, Any]] = {
    # --- Manual Curated (operator hand-picked) ---
    "twikejin": {"tier": 1, "source": "manual", "focus": ["A股", "AI基建", "光模块", "电子布"]},
    "LinQingV": {"tier": 1, "source": "manual", "focus": ["存储", "DRAM", "兆易创新", "长鑫"]},
    "tuolaji2024": {"tier": 1, "source": "manual", "focus": ["光互联", "光模块"]},
    "dmjk001": {"tier": 2, "source": "manual", "focus": ["光互联", "硅光", "800G", "1.6T"]},
    "Ariston_Macro": {"tier": 1, "source": "manual", "focus": ["宏观", "利率", "政策", "macro", "rates"]},
    "aleabitoreddit": {"tier": 2, "source": "manual", "focus": ["AI基建", "半导体", "AI infra", "semiconductor"]},
    "jukan05": {"tier": 2, "source": "manual", "focus": ["半导体供应链", "semiconductor supply"]},
    # --- Auto Discovery: Macro & Market Structure (via @LucyBuilding 2026-04-22) ---
    "morganhousel": {"tier": 3, "source": "auto", "focus": ["investment psychology", "long-term thinking"]},
    "LizAnnSonders": {"tier": 3, "source": "auto", "focus": ["macro", "liquidity", "market structure"]},
    "BittelJulien": {"tier": 3, "source": "auto", "focus": ["global macro", "asset allocation", "liquidity"]},
    "charliebilello": {"tier": 3, "source": "auto", "focus": ["historical data", "cycle comparison"]},
    "awealthofcs": {"tier": 3, "source": "auto", "focus": ["long-term investment framework"]},
    "Ritholtz": {"tier": 3, "source": "auto", "focus": ["market commentary", "macro"]},
    "LynAldenContact": {"tier": 3, "source": "auto", "focus": ["monetary", "fiscal", "energy", "credit", "macro"]},
    "biancoresearch": {"tier": 3, "source": "auto", "focus": ["rates", "bond market", "policy expectations"]},
    "josephwang": {"tier": 3, "source": "auto", "focus": ["Fed", "reserves", "USD liquidity", "plumbing"]},
    # --- Auto Discovery: Semiconductor, AI Infra & Supply Chain ---
    "dylan522p": {"tier": 3, "source": "auto", "focus": ["AI infra", "GPU", "cloud capex", "HBM", "memory"]},
    "Beth_Kindig": {"tier": 3, "source": "auto", "focus": ["tech growth", "AI main line"]},
    "BenBajarin": {"tier": 3, "source": "auto", "focus": ["industry analysis", "supply chain", "product cycles"]},
    "HedgeMind": {"tier": 3, "source": "auto", "focus": ["institutional positioning", "AI infra", "US tech"]},
    "TheValueist": {"tier": 3, "source": "auto", "focus": ["semiconductor", "value analysis"]},
    "MikeLongTerm": {"tier": 3, "source": "auto", "focus": ["semiconductor supply chain", "AI demand data"]},
    # --- Auto Discovery: Tech Business Models & Research Frameworks ---
    "stratechery": {"tier": 3, "source": "auto", "focus": ["platform", "AI business models", "industry structure"]},
    "ByrneHobart": {"tier": 3, "source": "auto", "focus": ["finance", "tech", "business model synthesis"]},
    "BrianFeroldi": {"tier": 3, "source": "auto", "focus": ["fundamentals", "earnings", "business model"]},
    "10kdiver": {"tier": 3, "source": "auto", "focus": ["probability", "valuation", "long-term returns"]},
    # --- Auto Discovery: Trading Frameworks & Market Structure ---
    "PeterLBrandt": {"tier": 3, "source": "auto", "focus": ["trading", "market structure"]},
    "alphatrends": {"tier": 3, "source": "auto", "focus": ["technical analysis", "trend framework"]},
    "bespokeinvest": {"tier": 3, "source": "auto", "focus": ["data statistics", "charts", "cross-validation"]},
}


def information_gap_score(candidate: dict[str, Any]) -> int:
    """Score the information gap: high public discussion but low depth coverage."""
    score = 20  # baseline

    source_items = safe_list(candidate.get("source_items"))
    source_count = len(source_items)

    # Check for analysis-tier sources (tier 0-2)
    has_analysis_source = any(
        int(safe_dict(s).get("source_tier", 99) or 99) <= 2
        for s in source_items
        if isinstance(s, dict)
    )

    # Multi-source discussion but no deep analysis source → high gap
    if source_count >= 3 and not has_analysis_source:
        score += 30
    elif source_count >= 2 and not has_analysis_source:
        score += 20

    # Social-heavy but low professional coverage → high gap
    social_providers = {"weibo", "zhihu", "reddit"}
    social_count = sum(
        1 for s in source_items
        if isinstance(s, dict) and clean_text(s.get("provider")) in social_providers
    )
    pro_count = source_count - social_count
    if social_count >= 2 and pro_count <= 1:
        score += 15

    # Contradicting signals in source items → public confusion → high gap
    has_contradiction = candidate.get("has_contradicting_signals", False)
    if not has_contradiction:
        # Heuristic: check if title contains contradiction markers
        title_lower = clean_text(candidate.get("title")).lower()
        has_contradiction = any(
            m in title_lower for m in ("争议", "矛盾", "但", "却", "dispute", "contradiction")
        )
    if has_contradiction:
        score += 15

    return clamp(score, 0, 100)


def x_author_signal_bonus(candidate: dict[str, Any]) -> int:
    """Bonus for topics overlapping with X watchlist authors' focus areas."""
    text = candidate_match_text(candidate).lower()
    bonus = 0
    matched_authors: list[str] = []
    for author, profile in X_WATCHLIST_AUTHORS.items():
        for focus in profile["focus"]:
            if focus.lower() in text:
                tier_bonus = 6 if profile["tier"] == 1 else 3
                bonus += tier_bonus
                matched_authors.append(author)
                break  # each author contributes at most once
    return min(bonus, 15)


def candidate_source_age_minutes(candidate: dict[str, Any], analysis_time: datetime) -> list[float]:
    ages = [
        age_minutes(analysis_time, item.get("published_at", ""))
        for item in safe_list(candidate.get("source_items"))
        if isinstance(item, dict)
    ]
    if ages:
        return ages
    return [age_minutes(analysis_time, candidate.get("latest_published_at", ""))]


def freshness_bucket(candidate: dict[str, Any], analysis_time: datetime) -> str:
    newest_age = min(candidate_source_age_minutes(candidate, analysis_time))
    if newest_age <= 360:
        return "0-6h"
    if newest_age <= 1440:
        return "6-24h"
    if newest_age <= 4320:
        return "24-72h"
    return ">72h"


def newest_source_item(candidate: dict[str, Any]) -> dict[str, Any]:
    source_items = [item for item in safe_list(candidate.get("source_items")) if isinstance(item, dict)]
    if not source_items:
        return {}
    return max(source_items, key=lambda item: clean_text(item.get("published_at")))


def is_continuing_story_candidate(candidate: dict[str, Any], analysis_time: datetime) -> bool:
    ages = candidate_source_age_minutes(candidate, analysis_time)
    if len(ages) < 2:
        return False
    newest_age = min(ages)
    oldest_age = max(ages)
    if newest_age > 1440:
        return False
    if oldest_age - newest_age < 1440:
        return False
    return contains_any_keyword(candidate_match_text(candidate), CONTINUING_STORY_KEYWORDS)


def fresh_catalyst_present(candidate: dict[str, Any], analysis_time: datetime) -> bool:
    if not is_continuing_story_candidate(candidate, analysis_time):
        return False
    latest_text = " ".join(
        [
            clean_text(newest_source_item(candidate).get("title") or candidate.get("title")),
            clean_text(newest_source_item(candidate).get("summary")),
            clean_text(candidate.get("summary")),
        ]
    ).lower()
    return contains_any_keyword(latest_text, FRESH_CATALYST_KEYWORDS)


def freshness_window_bonus(candidate: dict[str, Any], analysis_time: datetime) -> int:
    bucket = freshness_bucket(candidate, analysis_time)
    bonus = {
        "0-6h": 12,
        "6-24h": 8,
        "24-72h": 0,
        ">72h": 0,
    }.get(bucket, 0)
    if fresh_catalyst_present(candidate, analysis_time):
        bonus += 4
    return bonus


def near_window_heat_bonus(candidate: dict[str, Any], analysis_time: datetime) -> int:
    if freshness_bucket(candidate, analysis_time) not in {"0-6h", "6-24h"}:
        return 0
    bonus = 0
    source_count = int(candidate.get("source_count", 0) or 0)
    if source_count >= 2:
        bonus += min(6, (source_count - 1) * 3)
    primary_count = primary_platform_signal_count(candidate)
    if primary_count:
        bonus += min(4, primary_count * 2)
    if len(safe_list(candidate.get("domains"))) >= 2:
        bonus += 2
    return min(10, bonus)


def stale_story_penalty(candidate: dict[str, Any], analysis_time: datetime) -> int:
    bucket = freshness_bucket(candidate, analysis_time)
    weak_confirmation = int(candidate.get("source_count", 0) or 0) <= 1 and primary_platform_signal_count(candidate) == 0
    if bucket == ">72h":
        penalty = -10
        if weak_confirmation:
            penalty -= 8
        return penalty
    if bucket == "24-72h":
        return -6 if weak_confirmation else -3
    return 0


def heat_bucket(candidate: dict[str, Any], analysis_time: datetime) -> str:
    near_window_bonus = near_window_heat_bonus(candidate, analysis_time)
    bucket = freshness_bucket(candidate, analysis_time)
    if near_window_bonus >= 6:
        return "near_window_multi_source"
    if near_window_bonus > 0:
        return "near_window_single_source"
    if bucket == "24-72h":
        return "carryover"
    if bucket == ">72h":
        return "stale_residual"
    return "baseline"


def staleness_flags(candidate: dict[str, Any], analysis_time: datetime) -> list[str]:
    flags: list[str] = []
    bucket = freshness_bucket(candidate, analysis_time)
    if bucket == "24-72h":
        flags.append("older_than_24h")
    elif bucket == ">72h":
        flags.append("older_than_72h")
    if int(candidate.get("source_count", 0) or 0) <= 1 and primary_platform_signal_count(candidate) == 0:
        flags.append("weak_confirmation")
    if primary_platform_signal_count(candidate) == 0:
        flags.append("fallback_only")
    if is_continuing_story_candidate(candidate, analysis_time):
        flags.append("continuing_story")
    if fresh_catalyst_present(candidate, analysis_time):
        flags.append("fresh_catalyst")
    return flags


def freshness_reason(candidate: dict[str, Any], analysis_time: datetime) -> str:
    bucket = freshness_bucket(candidate, analysis_time)
    if fresh_catalyst_present(candidate, analysis_time):
        return "A continuing story picked up a fresh catalyst inside the current 24-hour window."
    if bucket == "0-6h":
        return "The newest public signal landed within the last 6 hours."
    if bucket == "6-24h":
        return "The newest public signal landed within the last 24 hours."
    if bucket == "24-72h":
        return "The story is still recent enough to matter, but it now sits in a carryover window."
    return "The newest public signal is older than 72 hours, so this is stale unless a new catalyst appears."


def live_snapshot_fit(candidate: dict[str, Any]) -> str:
    text = candidate_match_text(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
        return "high_fit"
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(text, LIVE_SNAPSHOT_EXTENSION_KEYWORDS):
        return "medium_fit"
    return "low_fit"


def live_snapshot_reason(candidate: dict[str, Any]) -> str:
    fit = live_snapshot_fit(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if fit == "high_fit":
        return "This is still a real-time writeable topic because the new signal already changes market or policy expectations."
    if fit == "medium_fit":
        return f"Fresh headline in the {freshness} window, but it still needs a clearer second-order read-through."
    return "Freshness alone is not enough here because the story still reads more like a narrow news flash than an analysis topic."


def live_snapshot_rank_reason(candidate: dict[str, Any]) -> str:
    fit = clean_text(candidate.get("live_snapshot_fit"))
    total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
    if fit == "high_fit":
        return "kept as high_fit"
    if fit == "medium_fit" and total >= LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE:
        return "eligible medium_fit backup"
    if fit == "medium_fit":
        return "filtered because medium_fit score below floor"
    return "filtered because low_fit"


def ordered_sources_for_request(request: dict[str, Any]) -> list[str]:
    sources = list(request["sources"])
    if request.get("discovery_profile") != "live_snapshot":
        return sources
    ordered: list[str] = []
    for preferred in LIVE_SNAPSHOT_SOURCE_ORDER:
        if preferred in sources:
            ordered.append(preferred)
    for source in sources:
        if source not in ordered:
            ordered.append(source)
    return ordered


def fetch_source_items_with_live_snapshot_budget(source_name: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    if request.get("discovery_profile") != "live_snapshot" or source_name != "google-news-world":
        return fetch_source_items(source_name, request)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_source_items, source_name, request)
        try:
            return future.result(timeout=LIVE_SNAPSHOT_GOOGLE_WORLD_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001
            future.cancel()
            raise RuntimeError(f"live snapshot source budget exceeded for {source_name}: {exc}") from exc


def enforce_live_snapshot_fit_gate(
    kept_topics: list[dict[str, Any]],
    filtered_out_topics: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    high_fit = [topic for topic in kept_topics if clean_text(topic.get("live_snapshot_fit")) == "high_fit"]
    medium_fit = [topic for topic in kept_topics if clean_text(topic.get("live_snapshot_fit")) == "medium_fit"]
    low_fit = [topic for topic in kept_topics if clean_text(topic.get("live_snapshot_fit")) == "low_fit"]
    for topic in low_fit:
        filtered_out_topics.append(
            {
                "title": clean_text(topic.get("title")),
                "filter_reason": "deprioritized low-fit live snapshot topic",
                "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
            }
        )
    return (high_fit + medium_fit[:LIVE_SNAPSHOT_MEDIUM_FIT_LIMIT])[:top_n]


def timeliness_score(candidate: dict[str, Any], analysis_time: datetime) -> int:
    newest_age = age_minutes(analysis_time, candidate.get("latest_published_at", ""))
    if newest_age <= 15:
        score = 100
    elif newest_age <= 60:
        score = 90
    elif newest_age <= 360:
        score = 75
    elif newest_age <= 1440:
        score = 60
    else:
        score = 35
    source_count = int(candidate.get("source_count", 0) or 0)
    if source_count <= 1:
        score -= 8
    if is_rumor_like_candidate(candidate):
        score -= 18 if source_count <= 1 else 10
    elif is_verification_like_candidate(candidate) and source_count <= 1:
        score -= 10
    return clamp(score)


def depth_score(candidate: dict[str, Any]) -> int:
    source_count = int(candidate.get("source_count", 0) or 0)
    diversity = len(candidate.get("domains", []))
    heat_score = int(candidate.get("max_heat_score", 0) or 0)
    base = 25 + min(40, source_count * 12) + min(20, diversity * 8)
    subreddit_count = int(candidate.get("reddit_subreddit_count", 0) or 0)
    subreddit_kind_count = len(candidate.get("reddit_subreddit_kinds", []))
    listing_count = len(candidate.get("reddit_listings", []))
    comment_sample_count = int(candidate.get("top_comment_count", 0) or 0)
    max_velocity_score = int(candidate.get("max_velocity_score", 0) or 0)
    if heat_score >= 10000:
        base += 10
    if subreddit_count > 1:
        base += min(12, (subreddit_count - 1) * 6)
    if subreddit_kind_count > 1:
        base += min(8, (subreddit_kind_count - 1) * 4)
    if listing_count > 1:
        base += min(8, (listing_count - 1) * 4)
    if comment_sample_count > 0:
        base += min(6, comment_sample_count)
    if max_velocity_score >= 85:
        base += 10
    elif max_velocity_score >= 60:
        base += 6
    elif max_velocity_score >= 35:
        base += 3
    return clamp(base)


def build_clustered_candidate(cluster_items: list[dict[str, Any]], request: dict[str, Any], index: int) -> dict[str, Any]:
    analysis_time = request["analysis_time"]
    audience_keywords = request["audience_keywords"]
    preferred_topic_keywords = request["preferred_topic_keywords"]
    weights = request["topic_score_weights"]
    sorted_items = sorted(
        cluster_items,
        key=lambda item: (
            int(item.get("heat_score", 0) or 0),
            item.get("published_at", ""),
            len(clean_text(item.get("summary"))),
        ),
        reverse=True,
    )
    canonical = sorted_items[0]
    latest_published_at = max((item.get("published_at", "") for item in sorted_items), default=isoformat_or_blank(analysis_time))
    source_names = []
    domains = []
    combined_tags = []
    reddit_subreddits = []
    reddit_subreddit_kinds = []
    reddit_listings = []
    reddit_listing_windows = []
    reddit_authors = []
    reddit_outbound_domains = []
    reddit_low_signal_subreddits = []
    top_comment_count = 0
    top_comment_authors = []
    top_comment_max_score = 0
    comment_raw_count = 0
    comment_duplicate_count = 0
    comment_near_duplicate_count = 0
    comment_near_duplicate_same_author_count = 0
    comment_near_duplicate_cross_author_count = 0
    comment_near_duplicate_examples = []
    comment_count_mismatch_count = 0
    comment_sample_coverage_ratios = []
    top_comment_summaries = []
    max_velocity_score = 0
    for item in sorted_items:
        source_name = clean_text(item.get("source_name"))
        if source_name and source_name not in source_names:
            source_names.append(source_name)
        domain = clean_text(item.get("publisher_domain_hint")) or domain_from_url(item.get("url", ""))
        if domain and domain not in domains:
            domains.append(domain)
        for tag in clean_string_list(item.get("tags")):
            if tag not in combined_tags:
                combined_tags.append(tag)
        subreddit = normalize_reddit_subreddit(item.get("subreddit"))
        if subreddit and subreddit not in reddit_subreddits:
            reddit_subreddits.append(subreddit)
        subreddit_kind = normalize_reddit_subreddit_kind(item.get("reddit_subreddit_kind"))
        if subreddit_kind and subreddit_kind not in reddit_subreddit_kinds:
            reddit_subreddit_kinds.append(subreddit_kind)
        listing = normalize_reddit_listing(item.get("reddit_listing"))
        if listing and listing not in reddit_listings:
            reddit_listings.append(listing)
        listing_window = normalize_reddit_listing_window(item.get("reddit_listing_window"))
        if listing_window and listing_window not in reddit_listing_windows:
            reddit_listing_windows.append(listing_window)
        reddit_author = normalize_reddit_user(item.get("reddit_author"))
        if reddit_author and reddit_author not in reddit_authors:
            reddit_authors.append(reddit_author)
        outbound_domain = clean_text(item.get("outbound_domain")).lower()
        if outbound_domain and outbound_domain not in reddit_outbound_domains:
            reddit_outbound_domains.append(outbound_domain)
        if item.get("reddit_low_signal") and subreddit and subreddit not in reddit_low_signal_subreddits:
            reddit_low_signal_subreddits.append(subreddit)
        top_comment_count += max(0, int(item.get("top_comment_count", 0) or 0))
        top_comment_summary = clean_text(item.get("top_comment_summary"))
        if top_comment_summary and top_comment_summary not in top_comment_summaries:
            top_comment_summaries.append(top_comment_summary)
        comment_raw_count += max(0, int(item.get("comment_raw_count", 0) or 0))
        comment_duplicate_count += max(0, int(item.get("comment_duplicate_count", 0) or 0))
        comment_near_duplicate_count += max(0, int(item.get("comment_near_duplicate_count", 0) or 0))
        comment_near_duplicate_same_author_count += max(0, int(item.get("comment_near_duplicate_same_author_count", 0) or 0))
        comment_near_duplicate_cross_author_count += max(0, int(item.get("comment_near_duplicate_cross_author_count", 0) or 0))
        for example in clean_string_list(item.get("comment_near_duplicate_examples")):
            if example not in comment_near_duplicate_examples and len(comment_near_duplicate_examples) < 4:
                comment_near_duplicate_examples.append(example)
        for comment_author in clean_string_list(item.get("top_comment_authors")):
            if comment_author not in top_comment_authors:
                top_comment_authors.append(comment_author)
        top_comment_max_score = max(top_comment_max_score, int(item.get("top_comment_max_score", 0) or 0))
        if item.get("comment_count_mismatch"):
            comment_count_mismatch_count += 1
        comment_sample_coverage_ratio = item.get("comment_sample_coverage_ratio")
        if isinstance(comment_sample_coverage_ratio, (int, float)):
            comment_sample_coverage_ratios.append(round(float(comment_sample_coverage_ratio), 4))
        max_velocity_score = max(max_velocity_score, int(item.get("velocity_score", 0) or 0))
    keywords = clean_string_list(keyword_hits(canonical.get("title", ""), canonical.get("summary", ""), " ".join(combined_tags)))
    keywords = clean_string_list(keywords + tokenize_title(canonical.get("title", "")))[:8]
    candidate = {
        "topic_id": slugify(canonical.get("title", ""), f"topic-{index:02d}"),
        "title": canonical.get("title", ""),
        "summary": canonical.get("summary", "") or canonical.get("title", ""),
        "latest_published_at": latest_published_at,
        "source_count": len(sorted_items),
        "source_names": source_names,
        "domains": domains,
        "keywords": keywords,
        "max_heat_score": max((int(item.get("heat_score", 0) or 0) for item in sorted_items), default=0),
        "reddit_subreddits": reddit_subreddits,
        "reddit_subreddit_count": len(reddit_subreddits),
        "reddit_subreddit_kinds": reddit_subreddit_kinds,
        "reddit_subreddit_kind_count": len(reddit_subreddit_kinds),
        "reddit_listings": reddit_listings,
        "reddit_listing_windows": reddit_listing_windows,
        "reddit_authors": reddit_authors,
        "reddit_author_count": len(reddit_authors),
        "reddit_outbound_domains": reddit_outbound_domains,
        "reddit_low_signal_subreddits": reddit_low_signal_subreddits,
        "reddit_low_signal_count": len(reddit_low_signal_subreddits),
        "top_comment_count": top_comment_count,
        "top_comment_summary": " | ".join(top_comment_summaries[:2]),
        "comment_raw_count": comment_raw_count,
        "comment_duplicate_count": comment_duplicate_count,
        "comment_near_duplicate_count": comment_near_duplicate_count,
        "comment_near_duplicate_same_author_count": comment_near_duplicate_same_author_count,
        "comment_near_duplicate_cross_author_count": comment_near_duplicate_cross_author_count,
        "comment_near_duplicate_level": "cross_author"
        if comment_near_duplicate_cross_author_count > 0
        else ("same_author_only" if comment_near_duplicate_same_author_count > 0 else ""),
        "comment_near_duplicate_examples": comment_near_duplicate_examples,
        "comment_near_duplicate_example_count": len(comment_near_duplicate_examples),
        "top_comment_authors": top_comment_authors,
        "top_comment_author_count": len(top_comment_authors),
        "top_comment_max_score": top_comment_max_score,
        "comment_count_mismatch_count": comment_count_mismatch_count,
        "comment_sample_coverage_ratio_max": max(comment_sample_coverage_ratios, default=0.0),
        "comment_sample_coverage_ratio_min": min(comment_sample_coverage_ratios, default=0.0) if comment_sample_coverage_ratios else 0.0,
        "max_velocity_score": max_velocity_score,
        "source_items": sorted_items,
    }
    comment_operator_review = build_comment_operator_review(candidate)
    if comment_operator_review:
        candidate["comment_operator_review"] = comment_operator_review
    operator_review_priority = build_operator_review_priority(candidate)
    if operator_review_priority:
        candidate["operator_review_priority"] = operator_review_priority
    if reddit_subreddits or reddit_listings or reddit_subreddit_kinds or reddit_outbound_domains:
        spread_parts: list[str] = []
        if reddit_subreddits:
            spread_parts.append(f"{len(reddit_subreddits)} subreddit(s)")
        if reddit_subreddit_kinds:
            spread_parts.append(f"signal {', '.join(reddit_subreddit_kinds[:3])}")
        if reddit_listings:
            spread_parts.append(f"listing {', '.join(reddit_listings[:3])}")
        if reddit_listing_windows:
            spread_parts.append(f"window {', '.join(reddit_listing_windows[:3])}")
        if reddit_outbound_domains:
            spread_parts.append(f"outbound {', '.join(reddit_outbound_domains[:2])}")
        if top_comment_count:
            spread_parts.append(f"comment sample {top_comment_count}")
        if comment_duplicate_count:
            spread_parts.append(f"deduped {comment_duplicate_count}")
        if comment_near_duplicate_count:
            if comment_near_duplicate_cross_author_count > 0:
                spread_parts.append(
                    f"near-duplicate caution {comment_near_duplicate_count} (cross-author {comment_near_duplicate_cross_author_count})"
                )
            elif comment_near_duplicate_same_author_count > 0:
                spread_parts.append(
                    f"near-duplicate caution {comment_near_duplicate_count} (same-author {comment_near_duplicate_same_author_count})"
                )
            else:
                spread_parts.append(f"near-duplicate caution {comment_near_duplicate_count}")
        if comment_count_mismatch_count:
            spread_parts.append(f"partial comments {comment_count_mismatch_count}")
        candidate["community_spread_summary"] = " / ".join(spread_parts)
    timeliness = timeliness_score(candidate, analysis_time)
    debate = discussion_score(candidate["title"], candidate["source_count"])
    relevance = relevance_score(candidate, audience_keywords, preferred_topic_keywords)
    depth = depth_score(candidate)
    seo = seo_score(candidate["title"], candidate["keywords"])
    info_gap = information_gap_score(candidate)
    freshness_window = freshness_window_bonus(candidate, analysis_time)
    near_window_heat = near_window_heat_bonus(candidate, analysis_time)
    stale_penalty = stale_story_penalty(candidate, analysis_time)
    candidate["freshness_bucket"] = freshness_bucket(candidate, analysis_time)
    candidate["freshness_reason"] = freshness_reason(candidate, analysis_time)
    candidate["heat_bucket"] = heat_bucket(candidate, analysis_time)
    candidate["staleness_flags"] = staleness_flags(candidate, analysis_time)
    candidate["is_continuing_story"] = is_continuing_story_candidate(candidate, analysis_time)
    candidate["fresh_catalyst_present"] = fresh_catalyst_present(candidate, analysis_time)
    total = clamp(
        timeliness * weights["timeliness"]
        + debate * weights["debate"]
        + relevance * weights["relevance"]
        + depth * weights["depth"]
        + seo * weights["seo"]
        + info_gap * weights.get("information_gap", 0.10)
        + freshness_window
        + near_window_heat
        + stale_penalty
    )
    if request.get("discovery_profile") == "international_first":
        primary_count = primary_platform_signal_count(candidate)
        if primary_count:
            total = clamp(total + min(18, primary_count * 7))
        else:
            total = clamp(total - 8)
            if int(candidate.get("source_count", 0) or 0) <= 1:
                total = clamp(total - 10)
    preferred_matches = matching_keywords(candidate_match_text(candidate), preferred_topic_keywords)
    # Penalize single-source social topics (e.g. zhihu) that match zero preferred/finance keywords
    if preferred_topic_keywords and not preferred_matches:
        source_names = [s.lower() for s in (candidate.get("source_names") or [])]
        finance_hits = keyword_hits(candidate_match_text(candidate))
        is_social_only = all(s in {"zhihu", "weibo"} for s in source_names) if source_names else False
        if is_social_only and not finance_hits:
            total = clamp(total - 20)
    positive_feedback_signals = positive_feedback_topic_signals(candidate)
    positive_feedback_bonus = positive_feedback_topic_bonus(candidate)
    if positive_feedback_bonus:
        total = clamp(total + positive_feedback_bonus)
    x_author_bonus = x_author_signal_bonus(candidate)
    if x_author_bonus:
        total = clamp(total + x_author_bonus)
    reasons = [
        f"新鲜度 {timeliness}",
        f"讨论空间 {debate}",
        f"受众相关性 {relevance}",
        f"延展深度 {depth}",
        f"SEO 价值 {seo}",
        f"信息差 {info_gap}",
    ]
    candidate["score_breakdown"] = {
        "timeliness": timeliness,
        "debate": debate,
        "relevance": relevance,
        "depth": depth,
        "seo": seo,
        "information_gap": info_gap,
        "freshness_window_bonus": freshness_window,
        "near_window_heat_bonus": near_window_heat,
        "stale_story_penalty": stale_penalty,
        "positive_feedback_bonus": positive_feedback_bonus,
        "x_author_signal_bonus": x_author_bonus,
        "total_score": total,
        "weights": weights,
    }
    candidate["positive_feedback_topic_signals"] = positive_feedback_signals
    if freshness_window:
        reasons.append(f"freshness window +{freshness_window}")
    if near_window_heat:
        reasons.append(f"near-window heat +{near_window_heat}")
    if stale_penalty:
        reasons.append(f"stale penalty {stale_penalty}")
    if preferred_matches:
        reasons.append(f"topic preference match {', '.join(preferred_matches[:3])}")
    if positive_feedback_bonus:
        active_positive_feedback_signals = [
            name for name, enabled in positive_feedback_signals.items() if enabled
        ]
        reasons.append(
            "positive_feedback "
            + ", ".join(active_positive_feedback_signals[:3])
            + f" (+{positive_feedback_bonus})"
        )
    if x_author_bonus:
        reasons.append(f"x_author_signal (+{x_author_bonus})")
    if candidate.get("reddit_subreddit_count", 0) > 1:
        reasons.append(f"reddit spread {candidate['reddit_subreddit_count']} subreddits")
    if candidate.get("reddit_subreddit_kind_count", 0) > 1:
        reasons.append(f"reddit community mix {', '.join(candidate['reddit_subreddit_kinds'][:2])}")
    if candidate.get("reddit_listings"):
        reasons.append(f"reddit listings {', '.join(candidate['reddit_listings'][:2])}")
    if candidate.get("max_velocity_score", 0) >= 60:
        reasons.append(f"reddit velocity {candidate['max_velocity_score']}")
    if candidate.get("reddit_low_signal_subreddits"):
        reasons.append(f"reddit low-signal caution {', '.join(candidate['reddit_low_signal_subreddits'][:2])}")
    if candidate.get("top_comment_count", 0) > 0:
        reasons.append(f"reddit comments sampled {candidate['top_comment_count']}")
    if candidate.get("comment_duplicate_count", 0) > 0:
        reasons.append(f"reddit deduped duplicate comments {candidate['comment_duplicate_count']}")
    if candidate.get("comment_near_duplicate_count", 0) > 0:
        if candidate.get("comment_near_duplicate_cross_author_count", 0) > 0:
            reasons.append(
                f"reddit near-duplicate comment caution {candidate['comment_near_duplicate_count']} (cross-author {candidate['comment_near_duplicate_cross_author_count']})"
            )
        elif candidate.get("comment_near_duplicate_same_author_count", 0) > 0:
            reasons.append(
                f"reddit near-duplicate comment caution {candidate['comment_near_duplicate_count']} (same-author {candidate['comment_near_duplicate_same_author_count']})"
            )
        else:
            reasons.append(f"reddit near-duplicate comment caution {candidate['comment_near_duplicate_count']}")
    if candidate.get("comment_count_mismatch_count", 0) > 0:
        reasons.append(f"reddit partial comment samples {candidate['comment_count_mismatch_count']}")
    operator_review_priority = safe_dict(candidate.get("operator_review_priority"))
    priority_level = clean_text(operator_review_priority.get("priority_level"))
    if priority_level and priority_level != "none":
        reasons.append(f"operator review {priority_level} priority")
    candidate["score_reasons"] = reasons
    candidate["topic_control_match"] = {
        "preferred_keyword_hits": preferred_matches,
        "excluded_keyword_hits": [],
    }
    candidate["story_family"] = story_family_label(candidate)
    candidate["recommended_angle"] = recommended_story_angle(candidate)
    candidate["why_now"] = why_now_summary(candidate)
    candidate["selection_reason"] = selection_reason_summary(candidate)
    candidate["risk_flags"] = risk_flags_for_candidate(candidate)
    candidate["source_mix"] = source_mix_summary(candidate)
    if request.get("discovery_profile") == "live_snapshot":
        candidate["live_snapshot_fit"] = live_snapshot_fit(candidate)
        candidate["live_snapshot_reason"] = live_snapshot_reason(candidate)
        candidate["live_snapshot_rank_reason"] = live_snapshot_rank_reason(candidate)
    return candidate


def normalize_manual_topic_candidate(
    candidate: dict[str, Any],
    request: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    analysis_time = request["analysis_time"]
    source_items = []
    for item_index, source in enumerate(safe_list(candidate.get("source_items")) or [candidate], start=1):
        if not isinstance(source, dict):
            continue
        title = clean_text(source.get("title") or candidate.get("title"))
        url = clean_text(source.get("url"))
        if not title or not url:
            continue
        source_items.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": clean_text(source.get("summary") or source.get("snippet") or candidate.get("summary") or title),
                    "url": url,
                    "source_name": clean_text(source.get("source_name") or source.get("source") or candidate.get("source_name") or f"manual-{index:02d}"),
                    "source_type": clean_text(source.get("source_type") or candidate.get("source_type") or "major_news"),
                    "published_at": source.get("published_at") or candidate.get("published_at") or analysis_time.isoformat(),
                    "heat_score": source.get("heat_score") or source.get("heat") or candidate.get("heat_score"),
                    "tags": safe_list(source.get("tags") or candidate.get("tags")),
                },
                analysis_time,
                item_index,
            )
        )
    if not source_items:
        raise ValueError("Manual topic candidate requires at least one valid source_items/url entry")
    return build_clustered_candidate(source_items, request, index)


def apply_topic_controls(candidate: dict[str, Any], request: dict[str, Any]) -> tuple[bool, str]:
    match_text = candidate_match_text(candidate)
    excluded_matches = matching_keywords(match_text, request["excluded_topic_keywords"])
    topic_control_match = safe_dict(candidate.get("topic_control_match"))
    topic_control_match["excluded_keyword_hits"] = excluded_matches
    candidate["topic_control_match"] = topic_control_match
    if is_locality_candidate(candidate) and not is_allowed_locality_candidate(candidate):
        return False, "filtered local topic outside shanghai/zhejiang"
    if is_weak_obituary_candidate(candidate):
        return False, "filtered weak obituary topic"
    if request.get("discovery_profile") == "international_first":
        if is_explicitly_offtopic_platform_candidate(candidate):
            return False, "filtered explicitly off-topic platform post"
        if is_generic_platform_political_statement_candidate(candidate):
            return False, "filtered generic platform political statement"
        if is_reddit_meta_discussion_candidate(candidate):
            return False, "filtered reddit meta discussion thread"
        if is_generic_reddit_research_chatter_candidate(candidate):
            return False, "filtered generic reddit research chatter"
        if is_low_specificity_reddit_platform_candidate(candidate):
            return False, "filtered low-specificity reddit platform chatter"
        if is_self_promotional_platform_candidate(candidate):
            return False, "filtered self-promotional platform post"
        if is_exhibition_promo_candidate(candidate):
            return False, "filtered exhibition promo topic"
        if is_generic_x_news_candidate(candidate):
            return False, "filtered generic x civic/social news"
        if is_generic_x_commentary_candidate(candidate):
            return False, "filtered generic x commentary thread"
        if is_generic_x_manifesto_candidate(candidate):
            return False, "filtered generic x manifesto thread"
        if is_generic_broad_market_question_candidate(candidate):
            return False, "filtered generic broad-market question thread"
        if is_ai_meme_entertainment_candidate(candidate):
            return False, "filtered ai meme/entertainment thread"
        if is_enterprise_ai_synthesis_candidate(candidate):
            return False, "filtered enterprise-ai synthesis thread"
        if is_generic_feature_interview_candidate(candidate):
            return False, "filtered generic feature/interview topic"
        if is_diplomatic_protocol_candidate(candidate):
            return False, "filtered diplomatic protocol topic"
        if is_official_commentary_candidate(candidate):
            return False, "filtered official commentary topic"
    freshness = clean_text(candidate.get("freshness_bucket"))
    stale_flags = clean_string_list(candidate.get("staleness_flags"))
    if freshness == ">72h" and not candidate.get("fresh_catalyst_present"):
        if "weak_confirmation" in stale_flags:
            return False, "filtered stale weak-confirmation topic"
        return False, "filtered stale topic without fresh catalyst"
    if freshness == "24-72h" and "weak_confirmation" in stale_flags and not candidate.get("fresh_catalyst_present"):
        return False, "filtered stale weak-confirmation topic"
    if request.get("discovery_profile") == "live_snapshot":
        fit = clean_text(candidate.get("live_snapshot_fit"))
        total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
        if fit == "low_fit":
            return False, "filtered low_fit live snapshot topic"
        if fit == "medium_fit" and total < LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE:
            return False, "filtered medium_fit live snapshot topic below floor"
        if is_live_snapshot_low_yield_candidate(candidate):
            return False, "filtered low-yield live snapshot topic"
    if excluded_matches:
        return False, f"excluded keywords: {', '.join(excluded_matches)}"
    if int(candidate.get("source_count", 0) or 0) < request["min_source_count"]:
        return False, f"source_count<{request['min_source_count']}"
    if safe_dict(candidate.get("score_breakdown")).get("total_score", 0) < request["min_total_score"]:
        return False, f"total_score<{request['min_total_score']}"
    return True, ""


def build_markdown_report(result: dict[str, Any]) -> str:
    controls = safe_dict(result.get("topic_controls"))
    lines = [
        "# Hot Topic Discovery",
        "",
        f"- Analysis time: {result.get('analysis_time', '')}",
        f"- Sources attempted: {', '.join(result.get('sources_attempted', [])) or 'manual'}",
        f"- Errors: {len(result.get('errors', []))}",
        f"- Preferred keywords: {', '.join(controls.get('preferred_topic_keywords', [])) or 'none'}",
        f"- Excluded keywords: {', '.join(controls.get('excluded_topic_keywords', [])) or 'none'}",
        (
            "- Score weights: "
            + ", ".join(
                f"{key}={int(round(float(value) * 100))}%"
                for key, value in safe_dict(controls.get("topic_score_weights")).items()
            )
        ),
        f"- Minimum total score: {controls.get('min_total_score', 0)}",
        f"- Minimum source count: {controls.get('min_source_count', 0)}",
        f"- Filtered out topics: {len(result.get('filtered_out_topics', []))}",
        "",
        "| Rank | Topic | Total | Review | Sources | Latest | Why |",
        "|---:|---|---:|---|---:|---|---|",
    ]
    for index, topic in enumerate(result.get("ranked_topics", []), start=1):
        operator_priority = safe_dict(topic.get("operator_review_priority"))
        priority_level = clean_text(operator_priority.get("priority_level")) or "none"
        lines.append(
            f"| {index} | {topic.get('title', '')} | {safe_dict(topic.get('score_breakdown')).get('total_score', 0)} | "
            f"{priority_level} | {topic.get('source_count', 0)} | {topic.get('latest_published_at', '')} | {' / '.join(topic.get('score_reasons', [])[:2])} |"
        )
    if not result.get("ranked_topics"):
        lines.append("| 1 | none | 0 | none | 0 | n/a | no discoverable topics |")
    operator_review_lines: list[str] = []
    for topic in result.get("ranked_topics", []):
        operator_priority = safe_dict(topic.get("operator_review_priority"))
        review_summary = format_comment_operator_review(safe_dict(topic.get("comment_operator_review")))
        if not review_summary:
            continue
        priority_level = clean_text(operator_priority.get("priority_level"))
        prefix = f"[{priority_level}] " if priority_level and priority_level != "none" else ""
        operator_review_lines.append(f"- {prefix}{topic.get('title', '')}: {review_summary}")
    if operator_review_lines:
        lines.extend(["", "## Reddit Operator Review", *operator_review_lines])
    if result.get("operator_review_queue"):
        lines.extend(["", "## Operator Queue"])
        for item in result["operator_review_queue"]:
            lines.append(
                f"- [{item.get('priority_level', 'none')}] {item.get('title', '')}: {item.get('summary', '') or item.get('recommended_action', '')}"
            )
    if result.get("errors"):
        lines.extend(["", "## Errors"])
        for item in result["errors"]:
            lines.append(f"- {item.get('source', '')}: {item.get('message', '')}")
    if result.get("filtered_out_topics"):
        lines.extend(["", "## Filtered Out"])
        for item in result["filtered_out_topics"]:
            lines.append(f"- {item.get('title', '')}: {item.get('filter_reason', '')}")
    if result.get("source_timings"):
        lines.extend(["", "## Source Timings"])
        for item in result["source_timings"]:
            lines.append(
                f"- {item.get('source', '')}: {item.get('status', '')} in {item.get('duration_ms', 0)} ms"
            )
    return "\n".join(lines).strip() + "\n"


def run_hot_topic_discovery(raw_payload: dict[str, Any]) -> dict[str, Any]:
    run_started = time.perf_counter()
    request = normalize_request(raw_payload)
    analysis_time = request["analysis_time"]
    errors: list[dict[str, str]] = []
    clustered_topics: list[dict[str, Any]] = []
    source_timings: list[dict[str, Any]] = []

    if request["manual_topic_candidates"]:
        for index, candidate in enumerate(request["manual_topic_candidates"], start=1):
            clustered_topics.append(normalize_manual_topic_candidate(candidate, request, index))
        source_timings.append({"source": "manual_topic_candidates", "duration_ms": 0, "status": "ok"})
    else:
        raw_items: list[dict[str, Any]] = []
        sources = request["sources"]
        max_workers = min(request["max_parallel_sources"], max(1, len(sources)))
        if max_workers > 1 and len(sources) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {}
                for source_name in sources:
                    started = time.perf_counter()
                    future = executor.submit(fetch_source_items, source_name, request)
                    future_map[future] = (source_name, started)
                for future in as_completed(future_map):
                    source_name, started = future_map[future]
                    try:
                        raw_items.extend(future.result())
                        source_timings.append(
                            {
                                "source": source_name,
                                "duration_ms": int(round((time.perf_counter() - started) * 1000)),
                                "status": "ok",
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        source_timings.append(
                            {
                                "source": source_name,
                                "duration_ms": int(round((time.perf_counter() - started) * 1000)),
                                "status": "error",
                            }
                        )
                        errors.append({"source": source_name, "message": str(exc)})
        else:
            for source_name in sources:
                started = time.perf_counter()
                try:
                    raw_items.extend(fetch_source_items(source_name, request))
                    source_timings.append(
                        {
                            "source": source_name,
                            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
                            "status": "ok",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    source_timings.append(
                        {
                            "source": source_name,
                            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
                            "status": "error",
                        }
                    )
                    errors.append({"source": source_name, "message": str(exc)})

        for index, cluster_items in enumerate(cluster_discovered_items(raw_items, request.get("query", "")), start=1):
            clustered_topics.append(build_clustered_candidate(cluster_items, request, index))

    ranked_topics = sorted(
        clustered_topics,
        key=lambda item: (
            safe_dict(item.get("score_breakdown")).get("total_score", 0),
            item.get("latest_published_at", ""),
            item.get("source_count", 0),
        ),
        reverse=True,
    )
    kept_topics: list[dict[str, Any]] = []
    filtered_out_topics: list[dict[str, Any]] = []
    for topic in ranked_topics:
        keep, reason = apply_topic_controls(topic, request)
        if keep:
            kept_topics.append(topic)
            continue
        filtered_out_topics.append(
            {
                "title": clean_text(topic.get("title")),
                "filter_reason": reason,
                "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
            }
        )
    if request.get("discovery_profile") == "international_first":
        kept_topics = enforce_international_primary_source_floor(kept_topics, filtered_out_topics, request["top_n"])
    operator_review_queue = []
    for topic in kept_topics:
        operator_priority = safe_dict(topic.get("operator_review_priority"))
        priority_level = clean_text(operator_priority.get("priority_level"))
        if not operator_priority or priority_level == "none":
            continue
        operator_review_queue.append(
            {
                "title": clean_text(topic.get("title")),
                "topic_id": clean_text(topic.get("topic_id")),
                "priority_level": priority_level,
                "priority_score": max(0, int(operator_priority.get("priority_score", 0) or 0)),
                "summary": clean_text(operator_priority.get("summary")),
                "recommended_action": clean_text(operator_priority.get("recommended_action")),
                "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
            }
        )
    operator_review_queue = sorted(
        operator_review_queue,
        key=lambda item: (
            int(item.get("priority_score", 0) or 0),
            int(item.get("total_score", 0) or 0),
            clean_text(item.get("title")),
        ),
        reverse=True,
    )
    result = {
        "status": "ok",
        "workflow_kind": "hot_topic_discovery",
        "analysis_time": isoformat_or_blank(analysis_time),
        "sources_attempted": request["sources"],
        "errors": errors,
        "source_timings": source_timings,
        "total_runtime_ms": int(round((time.perf_counter() - run_started) * 1000)),
        "ranked_topics": kept_topics[: request["top_n"]],
        "operator_review_queue": operator_review_queue[: request["top_n"]],
        "filtered_out_topics": filtered_out_topics,
        "topic_controls": {
            "preferred_topic_keywords": request["preferred_topic_keywords"],
            "excluded_topic_keywords": request["excluded_topic_keywords"],
            "topic_score_weights": request["topic_score_weights"],
            "min_total_score": request["min_total_score"],
            "min_source_count": request["min_source_count"],
        },
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = ["fetch_google_news_search", "normalize_request", "run_hot_topic_discovery"]
