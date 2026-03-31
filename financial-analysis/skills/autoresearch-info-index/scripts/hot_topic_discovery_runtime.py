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
from html import unescape
from typing import Any

from agent_reach_bridge_runtime import fetch_agent_reach_channels
from news_index_runtime import clean_string_list, isoformat_or_blank, parse_datetime, safe_dict, safe_list, slugify


DEFAULT_DISCOVERY_SOURCES = ["weibo", "zhihu", "36kr", "google-news-world"]
DEFAULT_TOPIC_SCORE_WEIGHTS = {
    "timeliness": 0.25,
    "debate": 0.20,
    "relevance": 0.25,
    "depth": 0.15,
    "seo": 0.15,
}
AGENT_REACH_ENV_VAR = "AGENT_REACH_PROVIDERS"
FINANCE_KEYWORDS = {
    "ai",
    "agent",
    "openai",
    "claude",
    "芯片",
    "半导体",
    "算力",
    "云",
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
    "锂",
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
    "崩",
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
    return normalized


def normalize_title_for_cluster(title: str) -> str:
    text = clean_text(title).lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def domain_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    return clean_text(parsed.netloc).lower()


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
        url = clean_text(item.get("url") or item.get("html_url") or item.get("webpage_url") or item.get("link") or item.get("permalink"))
        if family == "youtube" and not url and clean_text(item.get("id")):
            url = f"https://www.youtube.com/watch?v={clean_text(item.get('id'))}"
        if family == "x" and title:
            title = title[:120]
        if family == "github" and title and clean_text(item.get("description")):
            title = f"{title} - {clean_text(item.get('description'))}"[:160]
        if not title or not url:
            continue
        score_float = 0.5
        tags: list[str] = []
        if family == "github":
            score_float = clamp_score_float((item.get("stargazersCount") or item.get("stars") or 0) / 10000 if isinstance(item.get("stargazersCount") or item.get("stars"), (int, float)) else 0.5)
        elif family == "youtube":
            tags = ["video"]
        elif family == "semantic":
            score_float = clamp_score_float(item.get("similarity_score"), default=0.5)
        normalized.append(
            normalize_discovered_item(
                {
                    "title": title,
                    "summary": clean_text(item.get("summary") or item.get("snippet") or item.get("description") or title),
                    "url": url,
                    "source_name": source_name,
                    "source_type": "social" if family in {"youtube", "x", "wechat"} else "community" if family == "github" else "major_news",
                    "published_at": item.get("published_at") or item.get("updatedAt") or item.get("created_at") or item.get("pubDate") or request["analysis_time"].isoformat(),
                    "heat_score": int(round(score_float * 100)),
                    "tags": tags + [f"provider:{source_name}"],
                    "provider": source_name,
                    "score_float": score_float,
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
    if heat_score >= 10000:
        base += 10
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
        "source_items": sorted_items,
    }
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
        "| Rank | Topic | Total | Sources | Latest | Why |",
        "|---:|---|---:|---:|---|---|",
    ]
    for index, topic in enumerate(result.get("ranked_topics", []), start=1):
        lines.append(
            f"| {index} | {topic.get('title', '')} | {safe_dict(topic.get('score_breakdown')).get('total_score', 0)} | "
            f"{topic.get('source_count', 0)} | {topic.get('latest_published_at', '')} | {' / '.join(topic.get('score_reasons', [])[:2])} |"
        )
    if not result.get("ranked_topics"):
        lines.append("| 1 | none | 0 | 0 | n/a | no discoverable topics |")
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

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in raw_items:
            key = normalize_title_for_cluster(item.get("title", ""))
            if not key:
                continue
            grouped.setdefault(key, []).append(item)
        for index, cluster_items in enumerate(grouped.values(), start=1):
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
    result = {
        "status": "ok",
        "workflow_kind": "hot_topic_discovery",
        "analysis_time": isoformat_or_blank(analysis_time),
        "sources_attempted": request["sources"],
        "errors": errors,
        "ranked_topics": kept_topics[: request["top_n"]],
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
