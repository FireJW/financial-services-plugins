#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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
DEFAULT_TOPIC_SCORE_WEIGHTS = {
    "timeliness": 0.25,
    "debate": 0.20,
    "relevance": 0.25,
    "depth": 0.15,
    "seo": 0.15,
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
    return {
        "title_keys": {title_key} if title_key else set(),
        "reddit_outbound_urls": {reddit_cluster_outbound_url(item)} if reddit_cluster_outbound_url(item) else set(),
        "reddit_tokens": reddit_cluster_tokens(item) if is_reddit_discovered_item(item) else set(),
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

        matching_indexes: list[int] = []
        for index, cluster in enumerate(clusters):
            if title_key and title_key in cluster["title_keys"]:
                matching_indexes.append(index)
                continue
            if not item_is_reddit:
                continue
            if item_outbound_url and item_outbound_url in cluster["reddit_outbound_urls"]:
                matching_indexes.append(index)
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
    raw_text = fetch_text("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total")
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
        discovered.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": strip_tags(item.findtext("description") or title),
                    "url": link,
                    "source_name": source_name,
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


def normalize_agent_reach_items(source_name: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    family = source_name.split(":", 1)[1]
    query = clean_text(request.get("query") or request.get("topic"))
    if not query:
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
        if family == "x" and title:
            title = title[:120]
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
                    "published_at": item.get("published_at") or item.get("updatedAt") or item.get("created_at") or item.get("created_utc") or item.get("pubDate") or request["analysis_time"].isoformat(),
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
    sources = clean_string_list(raw_payload.get("sources")) or list(DEFAULT_DISCOVERY_SOURCES)
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
        "sources": sources,
        "limit": max(1, int(raw_payload.get("limit", 10) or 10)),
        "top_n": max(1, int(raw_payload.get("top_n", 5) or 5)),
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
        "max_parallel_sources": max(1, int(raw_payload.get("max_parallel_sources", min(4, len(sources))) or 1)),
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
    source_bonus = 15 if any(name in {"36kr", "google-news-world", "google-news-search"} for name in candidate.get("source_names", [])) else 0
    preference_bonus = min(24, preference_hits * 12)
    return clamp(20 + finance_hits * 15 + audience_hits * 18 + source_bonus + preference_bonus)


def timeliness_score(candidate: dict[str, Any], analysis_time: datetime) -> int:
    newest_age = age_minutes(analysis_time, candidate.get("latest_published_at", ""))
    if newest_age <= 15:
        return 100
    if newest_age <= 60:
        return 90
    if newest_age <= 360:
        return 75
    if newest_age <= 1440:
        return 60
    return 35


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
        domain = domain_from_url(item.get("url", ""))
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
    total = clamp(
        timeliness * weights["timeliness"]
        + debate * weights["debate"]
        + relevance * weights["relevance"]
        + depth * weights["depth"]
        + seo * weights["seo"]
    )
    preferred_matches = matching_keywords(candidate_match_text(candidate), preferred_topic_keywords)
    reasons = [
        f"新鲜度 {timeliness}",
        f"讨论空间 {debate}",
        f"受众相关性 {relevance}",
        f"延展深度 {depth}",
        f"SEO 价值 {seo}",
    ]
    candidate["score_breakdown"] = {
        "timeliness": timeliness,
        "debate": debate,
        "relevance": relevance,
        "depth": depth,
        "seo": seo,
        "total_score": total,
        "weights": weights,
    }
    if preferred_matches:
        reasons.append(f"topic preference match {', '.join(preferred_matches[:3])}")
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
    return "\n".join(lines).strip() + "\n"


def run_hot_topic_discovery(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    analysis_time = request["analysis_time"]
    errors: list[dict[str, str]] = []
    clustered_topics: list[dict[str, Any]] = []

    if request["manual_topic_candidates"]:
        for index, candidate in enumerate(request["manual_topic_candidates"], start=1):
            clustered_topics.append(normalize_manual_topic_candidate(candidate, request, index))
    else:
        raw_items: list[dict[str, Any]] = []
        sources = request["sources"]
        max_workers = min(request["max_parallel_sources"], max(1, len(sources)))
        if max_workers > 1 and len(sources) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(fetch_source_items, source_name, request): source_name for source_name in sources}
                for future in as_completed(future_map):
                    source_name = future_map[future]
                    try:
                        raw_items.extend(future.result())
                    except Exception as exc:  # noqa: BLE001
                        errors.append({"source": source_name, "message": str(exc)})
        else:
            for source_name in sources:
                try:
                    raw_items.extend(fetch_source_items(source_name, request))
                except Exception as exc:  # noqa: BLE001
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
