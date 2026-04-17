#!/usr/bin/env python3
from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
import urllib.parse

from news_index_runtime import clean_string_list, isoformat_or_blank, load_json, parse_datetime, run_news_index, short_excerpt, write_json


COLLECTION_KEYS = ("posts", "items", "results", "entries", "records", "data")
COMMENT_COLLECTION_KEYS = ("comments", "comment_items", "replies")
RESULT_PATH_KEYS = ("reddit_result_path", "result_path", "csv_path", "posts_path")
NESTED_RESULT_KEYS = ("reddit", "reddit_result", "source_result", "result")
EXPORT_DIRECTORY_PREFIXES = ("r_", "u_")
COMMENT_AUTHOR_KEYS = ("author", "username", "user", "author_name", "comment_author")
COMMENT_SCORE_KEYS = ("score", "ups", "upvotes", "vote_score")
COMMENT_TEXT_KEYS = (
    "body",
    "text",
    "content",
    "comment",
    "selftext",
    "body_text",
    "comment_text",
    "comment_body",
    "message",
)
COMMENT_TIMESTAMP_KEYS = ("created_utc", "created_at", "timestamp", "created", "time", "date")
COMMENT_POST_ID_KEYS = ("post_id", "link_id", "linkId", "submission_id", "submissionId", "parent_id", "parentId")
COMMENT_THREAD_URL_KEYS = (
    "post_permalink",
    "thread_permalink",
    "submission_permalink",
    "link",
    "permalink",
    "post_url",
    "thread_url",
    "submission_url",
    "reddit_url",
)
COMMENT_SORT_STRATEGIES = {"score_then_recency", "recency_then_score", "hybrid"}
DEFAULT_REDDIT_SUBREDDIT_KIND_GROUPS = {
    "broad_market": {"r/stocks", "r/investing", "r/StockMarket"},
    "deep_research": {"r/SecurityAnalysis", "r/ValueInvesting"},
    "speculative_flow": {"r/wallstreetbets", "r/options", "r/pennystocks", "r/Superstonk"},
    "event_watch": {"r/geopolitics", "r/worldnews", "r/economics", "r/CredibleDefense"},
}
REDDIT_COMMUNITY_PROFILE_PATH = Path(__file__).resolve().parents[1] / "references" / "reddit-community-profiles.json"


def now_utc() -> datetime:
    return datetime.now(UTC)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def decode_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def extract_first_json_object(text: str) -> dict[str, Any]:
    cleaned = text.lstrip("\ufeff\r\n\t ")
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Could not locate a JSON object in Reddit bridge input")


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


def numeric_value(value: Any) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_present_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not clean_text(value):
            continue
        return value
    return None


def normalize_comment_sort_strategy(value: Any) -> str:
    text = clean_text(value).lower().replace("-", "_")
    aliases = {
        "": "score_then_recency",
        "score": "score_then_recency",
        "top": "score_then_recency",
        "best": "score_then_recency",
        "ranked": "score_then_recency",
        "recent": "recency_then_score",
        "recency": "recency_then_score",
        "new": "recency_then_score",
        "latest": "recency_then_score",
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in COMMENT_SORT_STRATEGIES else "score_then_recency"


def comment_dedup_key(comment: dict[str, Any]) -> str:
    excerpt = clean_text(comment.get("excerpt")).lower()
    if not excerpt:
        return ""
    author = normalize_reddit_user(comment.get("author")).lower()
    if author:
        return f"{author}|{excerpt}"
    return excerpt


def normalize_comment_similarity_text(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    return " ".join(re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text).split())


def comment_is_near_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_exact = clean_text(left.get("excerpt")).lower()
    right_exact = clean_text(right.get("excerpt")).lower()
    if not left_exact or not right_exact:
        return False
    left_author = normalize_reddit_user(left.get("author")).lower()
    right_author = normalize_reddit_user(right.get("author")).lower()
    if left_exact == right_exact:
        return left_author != right_author or not left_author or not right_author

    left_text = normalize_comment_similarity_text(left_exact)
    right_text = normalize_comment_similarity_text(right_exact)
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    if min(len(left_text), len(right_text)) < 24:
        return False
    length_ratio = min(len(left_text), len(right_text)) / max(len(left_text), len(right_text))
    if length_ratio < 0.72:
        return False
    left_tokens = {token for token in left_text.split() if token}
    right_tokens = {token for token in right_text.split() if token}
    if not left_tokens or not right_tokens:
        return False
    token_overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    if token_overlap < 0.75:
        return False
    threshold = 0.86 if left_author and left_author == right_author else 0.93
    return difflib.SequenceMatcher(a=left_text, b=right_text).ratio() >= threshold


def near_duplicate_relation(left: dict[str, Any], right: dict[str, Any]) -> str:
    if not comment_is_near_duplicate(left, right):
        return ""
    left_author = normalize_reddit_user(left.get("author")).lower()
    right_author = normalize_reddit_user(right.get("author")).lower()
    if left_author and right_author and left_author == right_author:
        return "same_author"
    return "cross_author"


def near_duplicate_level(same_author_count: int, cross_author_count: int) -> str:
    if cross_author_count > 0:
        return "cross_author"
    if same_author_count > 0:
        return "same_author_only"
    return ""


def build_near_duplicate_example(anchor: dict[str, Any], comment: dict[str, Any], relation: str) -> str:
    anchor_author = normalize_reddit_user(anchor.get("author")) or "unknown"
    comment_author = normalize_reddit_user(comment.get("author")) or "unknown"
    anchor_excerpt = short_excerpt(clean_text(anchor.get("excerpt")), limit=72)
    comment_excerpt = short_excerpt(clean_text(comment.get("excerpt")), limit=72)
    return f"{relation}:{anchor_author} -> {comment_author} | {anchor_excerpt} || {comment_excerpt}"


def count_near_duplicate_comments(comments: list[dict[str, Any]]) -> dict[str, int | str]:
    anchors: list[dict[str, Any]] = []
    near_duplicate_count = 0
    same_author_count = 0
    cross_author_count = 0
    examples: list[str] = []
    for comment in comments:
        matched_relation = ""
        for anchor in anchors:
            matched_relation = near_duplicate_relation(comment, anchor)
            if matched_relation:
                near_duplicate_count += 1
                if matched_relation == "same_author":
                    same_author_count += 1
                else:
                    cross_author_count += 1
                example = build_near_duplicate_example(anchor, comment, matched_relation)
                if example and example not in examples and len(examples) < 3:
                    examples.append(example)
                break
        if matched_relation:
            continue
        anchors.append(comment)
    return {
        "count": near_duplicate_count,
        "same_author_count": same_author_count,
        "cross_author_count": cross_author_count,
        "level": near_duplicate_level(same_author_count, cross_author_count),
        "examples": examples,
    }


def is_reddit_url(value: str) -> bool:
    normalized = normalize_reddit_url(value)
    if not normalized:
        return False
    parsed = urllib.parse.urlparse(normalized)
    return "reddit.com" in parsed.netloc.lower()


def subreddit_from_permalink(value: Any) -> str:
    parsed = urllib.parse.urlparse(normalize_reddit_url(value))
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 2 and segments[0].lower() == "r":
        return normalize_reddit_subreddit(segments[1])
    return ""


def export_target_info(path: Path) -> tuple[str, str]:
    name = clean_text(path.name)
    if name.startswith("r_"):
        return "subreddit", name[2:]
    if name.startswith("u_"):
        return "user", name[2:]
    return "", name


def clean_tag_fragment(value: Any) -> str:
    return "-".join(clean_text(value).replace("/", " ").split()).lower()


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
    for kind, values in kind_groups.items():
        if not kind:
            continue
        for value in values:
            subreddit = normalize_reddit_subreddit(value).lower()
            if subreddit:
                mapping[subreddit] = kind

    if mapping:
        return mapping

    fallback: dict[str, str] = {}
    for kind, values in DEFAULT_REDDIT_SUBREDDIT_KIND_GROUPS.items():
        normalized_kind = normalize_reddit_subreddit_kind(kind)
        for value in values:
            subreddit = normalize_reddit_subreddit(value).lower()
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


def normalize_reddit_listing(value: Any) -> str:
    text = clean_text(value).lower().replace(".json", "").replace(".rss", "")
    if not text:
        return ""
    text = text.rsplit("/", 1)[-1]
    if text in {"best", "hot", "new", "rising", "top", "controversial"}:
        return text
    return ""


def normalize_reddit_listing_window(value: Any) -> str:
    text = clean_text(value).lower().replace("_", "").replace("-", "")
    if text in {"hour", "day", "week", "month", "year", "all"}:
        return text
    return ""


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


def outbound_domain_for(item: dict[str, Any]) -> str:
    outbound_url = normalize_reddit_url(item.get("outbound_url") or item.get("url"))
    if not outbound_url or is_reddit_url(outbound_url):
        return ""
    return clean_text(urllib.parse.urlparse(outbound_url).netloc).lower()


def build_export_selector_hints(raw_payload: dict[str, Any]) -> list[str]:
    selectors: list[str] = []

    def append_selector(value: Any, *, kind: str = "") -> None:
        text = clean_text(value)
        if not text:
            return
        normalized = text.lstrip("/")
        lowered = normalized.lower()
        candidates: list[str] = []
        if lowered.startswith("r/"):
            candidates.append(f"r_{normalized[2:].lstrip('/')}")
        elif lowered.startswith("u/"):
            candidates.append(f"u_{normalized[2:].lstrip('/')}")
        elif lowered.startswith("r_") or lowered.startswith("u_"):
            candidates.append(normalized)
        elif kind == "subreddit":
            candidates.append(f"r_{normalized}")
        elif kind == "user":
            candidates.append(f"u_{normalized}")
        else:
            candidates.extend([f"r_{normalized}", f"u_{normalized}", normalized])

        for candidate in candidates:
            if candidate and candidate not in selectors:
                selectors.append(candidate)

    append_selector(raw_payload.get("export_target"))
    append_selector(raw_payload.get("reddit_target"))
    append_selector(raw_payload.get("target"))
    append_selector(raw_payload.get("subreddit"), kind="subreddit")
    append_selector(raw_payload.get("subreddit_name_prefixed"), kind="subreddit")
    append_selector(raw_payload.get("user"), kind="user")
    append_selector(raw_payload.get("username"), kind="user")
    append_selector(raw_payload.get("author"), kind="user")
    return selectors


def discover_export_directories(path: Path) -> list[Path]:
    search_roots: list[Path] = []
    data_root = path / "data"
    if data_root.is_dir():
        search_roots.append(data_root)
    search_roots.append(path)

    discovered: list[Path] = []
    for root in search_roots:
        try:
            children = sorted(root.iterdir(), key=lambda child: child.name.lower())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if not child.name.startswith(EXPORT_DIRECTORY_PREFIXES):
                continue
            if (child / "posts.csv").exists():
                discovered.append(child)
    return discovered


def select_export_posts_path(path: Path, selectors: list[str]) -> tuple[Path, str]:
    export_directories = discover_export_directories(path)
    if not export_directories:
        raise FileNotFoundError(f"Reddit bridge could not find exported posts.csv under {path}")

    if selectors:
        normalized_selectors = {selector.lower() for selector in selectors}
        for directory in export_directories:
            if directory.name.lower() in normalized_selectors:
                return directory / "posts.csv", "csv_export_root"

    if len(export_directories) == 1:
        return export_directories[0] / "posts.csv", "csv_export_root"

    available = ", ".join(directory.name for directory in export_directories[:8])
    raise ValueError(
        "Reddit bridge found multiple export targets under "
        f"{path}. Set subreddit/user/export_target to choose one. Available: {available}"
    )


def enrich_csv_row(row: dict[str, Any], path: Path) -> dict[str, Any]:
    item = {key: value for key, value in row.items()}
    export_kind, export_name = export_target_info(path.parent)
    permalink = normalize_reddit_url(item.get("permalink") or item.get("post_permalink"))
    subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit")) or subreddit_from_permalink(permalink)
    if not subreddit and export_kind == "subreddit" and export_name:
        subreddit = normalize_reddit_subreddit(export_name)
    if subreddit and not clean_text(item.get("subreddit")):
        item["subreddit"] = subreddit

    if export_kind == "user" and export_name:
        item.setdefault("export_user", export_name)
        item.setdefault("bridge_export_user", export_name)

    outbound_url = normalize_reddit_url(item.get("url"))
    if permalink and outbound_url and outbound_url != permalink:
        item.setdefault("outbound_url", outbound_url)

    item["bridge_export_kind"] = export_kind or "unknown"
    item["bridge_export_name"] = export_name
    item["bridge_export_target"] = path.parent.name
    item["bridge_posts_path"] = str(path)
    return item


def build_reddit_url(item: dict[str, Any]) -> str:
    permalink = normalize_reddit_url(item.get("permalink") or item.get("post_permalink") or item.get("link"))
    if permalink:
        return permalink

    url = normalize_reddit_url(item.get("reddit_url") or item.get("thread_url") or item.get("url") or item.get("post_url"))
    if is_reddit_url(url):
        return url

    subreddit = (
        normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        or subreddit_from_permalink(item.get("permalink") or item.get("post_permalink"))
    )
    post_id = clean_text(item.get("id") or item.get("post_id"))
    if subreddit and post_id:
        return f"https://www.reddit.com/{subreddit}/comments/{post_id}/"
    return url


def source_name_for(item: dict[str, Any]) -> str:
    subreddit = (
        normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        or subreddit_from_permalink(item.get("permalink") or item.get("post_permalink"))
    )
    if subreddit:
        return f"Reddit {subreddit}".strip()
    author = author_label_for(item)
    return f"Reddit {author}".strip() if author else "Reddit"


def author_label_for(item: dict[str, Any]) -> str:
    return normalize_reddit_user(item.get("author") or item.get("username") or item.get("export_user") or item.get("bridge_export_user"))


def post_summary_for(item: dict[str, Any]) -> str:
    return clean_text(item.get("title") or item.get("headline") or item.get("name"))


def text_excerpt_for(item: dict[str, Any]) -> str:
    return short_excerpt(
        item.get("summary")
        or item.get("snippet")
        or item.get("description")
        or item.get("selftext")
        or item.get("top_comment_summary")
        or item.get("comment_summary")
        or item.get("top_comment_excerpt")
        or item.get("body")
        or item.get("text")
        or post_summary_for(item),
        limit=240,
    )


def normalize_reddit_post_id(value: Any) -> str:
    text = clean_text(value).lower()
    if text.startswith("t3_"):
        return text[3:]
    return text


def canonical_reddit_thread_url(value: Any) -> str:
    parsed = urllib.parse.urlparse(normalize_reddit_url(value))
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 4 and segments[0].lower() == "r" and segments[2].lower() == "comments":
        subreddit = normalize_reddit_subreddit(segments[1])
        post_id = normalize_reddit_post_id(segments[3])
        if subreddit and post_id:
            return f"https://www.reddit.com/{subreddit}/comments/{post_id}/"
    return ""


def comment_text_for(item: dict[str, Any]) -> str:
    return short_excerpt(first_present_value(item, COMMENT_TEXT_KEYS) or "", limit=160)


def normalize_comment_payload(item: dict[str, Any]) -> dict[str, Any]:
    created_value = first_present_value(item, COMMENT_TIMESTAMP_KEYS)
    score_value = first_present_value(item, COMMENT_SCORE_KEYS)
    return {
        "author": normalize_reddit_user(first_present_value(item, COMMENT_AUTHOR_KEYS)),
        "score": int(round(numeric_value(score_value) or 0)),
        "excerpt": comment_text_for(item),
        "created_at": isoformat_or_blank(
            parse_datetime(
                created_value,
                fallback=now_utc(),
            )
        ),
    }


def comment_match_keys(item: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for raw_post_id in (clean_text(item.get(key)).lower() for key in COMMENT_POST_ID_KEYS):
        if not raw_post_id or raw_post_id.startswith("t1_"):
            continue
        post_id = normalize_reddit_post_id(raw_post_id)
        if post_id:
            keys.add(f"id:{post_id}")
    for value in (item.get(key) for key in COMMENT_THREAD_URL_KEYS):
        thread_url = canonical_reddit_thread_url(value)
        if thread_url:
            keys.add(f"url:{thread_url}")
            parsed = urllib.parse.urlparse(thread_url)
            segments = [segment for segment in parsed.path.split("/") if segment]
            if len(segments) >= 4:
                post_id = normalize_reddit_post_id(segments[3])
                if post_id:
                    keys.add(f"id:{post_id}")
    return keys


def post_match_keys(item: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    post_id = normalize_reddit_post_id(item.get("id") or item.get("post_id") or item.get("link_id"))
    if post_id:
        keys.add(f"id:{post_id}")
    for value in (
        item.get("permalink"),
        item.get("post_permalink"),
        item.get("reddit_url"),
        item.get("thread_url"),
        item.get("submission_url"),
        build_reddit_url(item),
    ):
        thread_url = canonical_reddit_thread_url(value)
        if thread_url:
            keys.add(f"url:{thread_url}")
    return keys


def build_comment_snapshot(comments: list[dict[str, Any]], comment_sort_strategy: str = "score_then_recency") -> dict[str, Any]:
    strategy = normalize_comment_sort_strategy(comment_sort_strategy)
    raw_candidates = [comment for comment in comments if clean_text(comment.get("excerpt"))]
    deduped_candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    duplicate_count = 0
    for comment in raw_candidates:
        dedup_key = comment_dedup_key(comment)
        if dedup_key and dedup_key in seen_keys:
            duplicate_count += 1
            continue
        if dedup_key:
            seen_keys.add(dedup_key)
        deduped_candidates.append(comment)
    ranked_candidates = deduped_candidates
    if not ranked_candidates:
        return {}
    latest_created_at = max(
        (parse_datetime(comment.get("created_at"), fallback=now_utc()) or now_utc() for comment in ranked_candidates),
        default=now_utc(),
    )
    max_score = max((int(comment.get("score", 0) or 0) for comment in ranked_candidates), default=0)

    def sort_key(comment: dict[str, Any]) -> tuple[Any, ...]:
        score = int(comment.get("score", 0) or 0)
        created_at = parse_datetime(comment.get("created_at"), fallback=latest_created_at) or latest_created_at
        excerpt_length = len(clean_text(comment.get("excerpt")))
        if strategy == "recency_then_score":
            return (created_at, score, excerpt_length)
        if strategy == "hybrid":
            hours_behind = max(0.0, (latest_created_at - created_at).total_seconds() / 3600.0)
            recency_norm = 1.0 / (1.0 + hours_behind / 12.0)
            score_norm = score / max(1, max_score)
            hybrid_rank = round(score_norm * 0.72 + recency_norm * 0.28, 6)
            return (hybrid_rank, score, created_at, excerpt_length)
        return (score, created_at, excerpt_length)

    ranked = sorted(ranked_candidates, key=sort_key, reverse=True)
    if not ranked:
        return {}
    near_duplicate = count_near_duplicate_comments(ranked)
    excerpts = [clean_text(comment.get("excerpt")) for comment in ranked if clean_text(comment.get("excerpt"))]
    authors: list[str] = []
    for comment in ranked:
        author = clean_text(comment.get("author"))
        if author and author not in authors:
            authors.append(author)
    return {
        "top_comment_count": len(ranked),
        "comment_raw_count": len(raw_candidates),
        "comment_duplicate_count": duplicate_count,
        "comment_near_duplicate_count": int(near_duplicate["count"] or 0),
        "comment_near_duplicate_same_author_count": int(near_duplicate["same_author_count"] or 0),
        "comment_near_duplicate_cross_author_count": int(near_duplicate["cross_author_count"] or 0),
        "comment_near_duplicate_level": clean_text(near_duplicate.get("level")),
        "comment_near_duplicate_examples": clean_string_list(near_duplicate.get("examples")),
        "comment_near_duplicate_example_count": len(clean_string_list(near_duplicate.get("examples"))),
        "top_comment_excerpt": excerpts[0],
        "top_comment_summary": " | ".join(excerpts[:2]),
        "top_comment_authors": authors[:3],
        "top_comment_max_score": int(ranked[0].get("score", 0) or 0),
        "top_comment_sort_strategy": strategy,
    }


def build_comment_lookup(comments: list[dict[str, Any]], comment_sort_strategy: str = "score_then_recency") -> dict[str, dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in comments:
        keys = comment_match_keys(item)
        normalized = normalize_comment_payload(item)
        if not keys or not normalized.get("excerpt"):
            continue
        matching_groups = [group for group in groups if group["keys"].intersection(keys)]
        if not matching_groups:
            groups.append({"keys": set(keys), "comments": [normalized]})
            continue

        primary = matching_groups[0]
        primary["keys"].update(keys)
        primary["comments"].append(normalized)
        for secondary in matching_groups[1:]:
            primary["keys"].update(secondary["keys"])
            primary["comments"].extend(secondary["comments"])
            groups.remove(secondary)

    lookup: dict[str, dict[str, Any]] = {}
    for group in groups:
        snapshot = build_comment_snapshot(group["comments"], comment_sort_strategy=comment_sort_strategy)
        if not snapshot:
            continue
        for key in group["keys"]:
            lookup[key] = snapshot
    return lookup


def apply_comment_lookup_to_items(
    items: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    comment_sort_strategy: str = "score_then_recency",
) -> list[dict[str, Any]]:
    if not items or not comments:
        return items
    comment_lookup = build_comment_lookup(comments, comment_sort_strategy=comment_sort_strategy)
    if not comment_lookup:
        return items

    enriched_items: list[dict[str, Any]] = []
    for item in items:
        enriched = dict(item)
        for key in post_match_keys(item):
            snapshot = comment_lookup.get(key)
            if not snapshot:
                continue
            for field, value in snapshot.items():
                enriched.setdefault(field, deepcopy(value))
            declared_comment_count = numeric_value(
                first_present_value(item, ("num_comments", "comment_count", "comments_count", "total_comments"))
            )
            sampled_comment_count = int(enriched.get("top_comment_count", 0) or 0)
            if declared_comment_count is not None:
                normalized_declared_count = max(0, int(round(declared_comment_count)))
                enriched.setdefault("comment_declared_count", normalized_declared_count)
                if normalized_declared_count > 0:
                    enriched.setdefault(
                        "comment_sample_coverage_ratio",
                        round(sampled_comment_count / normalized_declared_count, 4),
                    )
                    enriched.setdefault("comment_count_mismatch", sampled_comment_count != normalized_declared_count)
                    enriched.setdefault(
                        "comment_sample_status",
                        "partial" if sampled_comment_count < normalized_declared_count else "oversampled",
                    )
                    if sampled_comment_count == normalized_declared_count:
                        enriched["comment_sample_status"] = "matched"
            break
        enriched_items.append(enriched)
    return enriched_items


def comment_sample_coverage_bounds(item: dict[str, Any]) -> tuple[float | None, float | None]:
    coverage_ratio = item.get("comment_sample_coverage_ratio")
    if isinstance(coverage_ratio, (int, float)):
        normalized = round(float(coverage_ratio), 4)
        return normalized, normalized
    minimum = item.get("comment_sample_coverage_ratio_min")
    maximum = item.get("comment_sample_coverage_ratio_max")
    min_value = round(float(minimum), 4) if isinstance(minimum, (int, float)) else None
    max_value = round(float(maximum), 4) if isinstance(maximum, (int, float)) else None
    if min_value is None and max_value is None:
        return None, None
    if min_value is None:
        min_value = max_value
    if max_value is None:
        max_value = min_value
    return min_value, max_value


def format_comment_coverage_label(minimum: float | None, maximum: float | None) -> str:
    if minimum is None and maximum is None:
        return ""
    if minimum is not None and maximum is not None and abs(minimum - maximum) <= 0.00005:
        return f"{minimum:.4f} coverage"
    minimum_label = f"{minimum:.4f}" if minimum is not None else "n/a"
    maximum_label = f"{maximum:.4f}" if maximum is not None else "n/a"
    return f"{minimum_label}-{maximum_label} coverage"


def build_comment_operator_review(item: dict[str, Any]) -> dict[str, Any]:
    top_comment_count = max(0, int(item.get("top_comment_count", 0) or 0))
    top_comment_authors = clean_string_list(item.get("top_comment_authors"))
    top_comment_max_score = max(0, int(item.get("top_comment_max_score", 0) or 0))
    top_comment_summary = clean_text(item.get("top_comment_summary") or item.get("top_comment_excerpt"))
    comment_duplicate_count = max(0, int(item.get("comment_duplicate_count", 0) or 0))
    comment_near_duplicate_count = max(0, int(item.get("comment_near_duplicate_count", 0) or 0))
    comment_near_duplicate_same_author_count = max(0, int(item.get("comment_near_duplicate_same_author_count", 0) or 0))
    comment_near_duplicate_cross_author_count = max(0, int(item.get("comment_near_duplicate_cross_author_count", 0) or 0))
    comment_near_duplicate_examples = clean_string_list(item.get("comment_near_duplicate_examples"))
    declared_comment_count = max(0, int(item.get("comment_declared_count", 0) or 0))
    comment_count_mismatch = bool(item.get("comment_count_mismatch"))
    comment_count_mismatch_count = max(0, int(item.get("comment_count_mismatch_count", 0) or 0))
    comment_sample_status = clean_text(item.get("comment_sample_status"))
    near_duplicate_level_value = clean_text(item.get("comment_near_duplicate_level"))
    coverage_min, coverage_max = comment_sample_coverage_bounds(item)

    has_partial_sample = comment_sample_status == "partial" or comment_count_mismatch or comment_count_mismatch_count > 0
    if not comment_sample_status:
        if has_partial_sample:
            comment_sample_status = "partial"
        elif declared_comment_count > 0 and top_comment_count > declared_comment_count:
            comment_sample_status = "oversampled"
        elif declared_comment_count > 0 and top_comment_count == declared_comment_count and top_comment_count > 0:
            comment_sample_status = "matched"

    meaningful = any(
        (
            top_comment_count,
            declared_comment_count,
            bool(top_comment_authors),
            bool(top_comment_summary),
            comment_duplicate_count,
            comment_near_duplicate_count,
            has_partial_sample,
            comment_count_mismatch_count,
            coverage_min is not None or coverage_max is not None,
        )
    )
    if not meaningful:
        return {}

    cautions: list[str] = []
    review_notes: list[str] = []
    sample_parts: list[str] = []
    if top_comment_count > 0:
        if declared_comment_count > 0:
            sample_parts.append(f"sampled {top_comment_count}/{declared_comment_count} comments")
        else:
            sample_parts.append(f"sampled {top_comment_count} comments")
    coverage_label = format_comment_coverage_label(coverage_min, coverage_max)
    if coverage_label:
        sample_parts.append(coverage_label)
    if top_comment_max_score > 0:
        sample_parts.append(f"max score {top_comment_max_score}")
    if sample_parts:
        review_notes.append(", ".join(sample_parts))
    if top_comment_authors:
        review_notes.append(f"top comment authors: {', '.join(top_comment_authors[:3])}")
    if top_comment_summary:
        review_notes.append(f"top comment context: {short_excerpt(top_comment_summary, limit=120)}")

    if has_partial_sample:
        if comment_count_mismatch_count > 0 and declared_comment_count <= 0:
            cautions.append(f"partial comment samples across {comment_count_mismatch_count} source(s)")
        elif declared_comment_count > 0 and top_comment_count > 0:
            cautions.append(f"partial comment sample: {top_comment_count}/{declared_comment_count}")
        else:
            cautions.append("partial comment sample")
    elif comment_sample_status == "oversampled":
        if declared_comment_count > 0 and top_comment_count > 0:
            cautions.append(f"comment sample exceeds declared count: {top_comment_count}/{declared_comment_count}")
        else:
            cautions.append("comment sample exceeds declared count")

    if comment_duplicate_count > 0:
        cautions.append(f"exact duplicate comments deduped: {comment_duplicate_count}")
    if comment_near_duplicate_count > 0:
        near_duplicate_label = f"near-duplicate comments flagged: {comment_near_duplicate_count}"
        if comment_near_duplicate_cross_author_count > 0:
            near_duplicate_label += f" (cross-author {comment_near_duplicate_cross_author_count})"
        elif comment_near_duplicate_same_author_count > 0:
            near_duplicate_label += f" (same-author {comment_near_duplicate_same_author_count})"
        cautions.append(near_duplicate_label)

    for caution in cautions:
        if caution not in review_notes:
            review_notes.append(caution)

    summary_parts: list[str] = []
    if sample_parts:
        summary_parts.append(", ".join(sample_parts))
    if top_comment_summary:
        summary_parts.append(f"top context: {short_excerpt(top_comment_summary, limit=96)}")
    if cautions:
        summary_parts.append("cautions: " + "; ".join(cautions))

    operator_review = {
        "review_required": bool(cautions),
        "has_partial_sample": has_partial_sample,
        "has_exact_duplicates": comment_duplicate_count > 0,
        "has_near_duplicates": comment_near_duplicate_count > 0,
        "comment_sample_status": comment_sample_status,
        "top_comment_count": top_comment_count,
        "top_comment_summary": top_comment_summary,
        "top_comment_authors": top_comment_authors,
        "top_comment_max_score": top_comment_max_score,
        "comment_duplicate_count": comment_duplicate_count,
        "comment_near_duplicate_count": comment_near_duplicate_count,
        "comment_near_duplicate_same_author_count": comment_near_duplicate_same_author_count,
        "comment_near_duplicate_cross_author_count": comment_near_duplicate_cross_author_count,
        "near_duplicate_level": near_duplicate_level_value,
        "comment_near_duplicate_examples": comment_near_duplicate_examples,
        "comment_near_duplicate_example_count": len(comment_near_duplicate_examples),
        "caution_count": len(cautions),
        "cautions": cautions,
        "review_notes": review_notes,
        "summary": " | ".join(summary_parts[:3]),
    }
    if declared_comment_count > 0:
        operator_review["comment_declared_count"] = declared_comment_count
    if coverage_min is not None and coverage_max is not None and abs(coverage_min - coverage_max) <= 0.00005:
        operator_review["comment_sample_coverage_ratio"] = coverage_min
    else:
        if coverage_min is not None:
            operator_review["comment_sample_coverage_ratio_min"] = coverage_min
        if coverage_max is not None:
            operator_review["comment_sample_coverage_ratio_max"] = coverage_max
    if comment_count_mismatch:
        operator_review["comment_count_mismatch"] = True
    if comment_count_mismatch_count > 0:
        operator_review["comment_count_mismatch_count"] = comment_count_mismatch_count
    return operator_review


def format_comment_operator_review(review: dict[str, Any]) -> str:
    summary = clean_text(safe_dict(review).get("summary"))
    if summary:
        return summary
    notes = clean_string_list(safe_dict(review).get("review_notes"))
    return " | ".join(notes[:3])


def build_operator_review_priority(item: dict[str, Any]) -> dict[str, Any]:
    review = safe_dict(item.get("comment_operator_review")) or build_comment_operator_review(item)
    low_signal = bool(item.get("reddit_low_signal")) or clean_text(item.get("subreddit_signal_level")) == "low"
    if not review and not low_signal:
        return {}

    score = 0
    reasons: list[str] = []
    if review.get("has_partial_sample"):
        score += 2
        reasons.append("partial_comment_sample")
    mismatch_source_count = max(0, int(review.get("comment_count_mismatch_count", 0) or 0))
    if mismatch_source_count > 1:
        score += 1
        reasons.append("multi_source_partial_sample")
    if review.get("has_exact_duplicates"):
        score += 1
        reasons.append("exact_duplicate_comments")
    if review.get("has_near_duplicates"):
        score += 2
        near_duplicate_level_value = clean_text(review.get("near_duplicate_level"))
        if near_duplicate_level_value == "cross_author":
            score += 2
            reasons.append("cross_author_near_duplicates")
        elif near_duplicate_level_value == "same_author_only":
            score += 1
            reasons.append("same_author_near_duplicates")
        else:
            reasons.append("near_duplicate_comments")
    coverage_min, coverage_max = comment_sample_coverage_bounds(review)
    thin_coverage_value = coverage_min if coverage_min is not None else coverage_max
    if isinstance(thin_coverage_value, float):
        if thin_coverage_value < 0.01:
            score += 2
            reasons.append("very_thin_comment_sample")
        elif thin_coverage_value < 0.05:
            score += 1
            reasons.append("thin_comment_sample")
    if low_signal:
        score += 1
        reasons.append("low_signal_subreddit")

    priority_level = "none"
    recommended_action = ""
    if score >= 6:
        priority_level = "high"
        recommended_action = "manual_review_before_promotion"
    elif score >= 3:
        priority_level = "medium"
        recommended_action = "review_before_relying_on_comment_context"
    elif score > 0:
        priority_level = "low"
        recommended_action = "monitor_comment_context"

    review_required = priority_level in {"medium", "high"} or bool(review.get("review_required"))
    summary_parts: list[str] = []
    if priority_level != "none":
        summary_parts.append(f"{priority_level} priority")
    if reasons:
        summary_parts.append(", ".join(reasons[:4]))
    caution_preview = clean_string_list(review.get("cautions"))
    if caution_preview:
        summary_parts.append("; ".join(caution_preview[:2]))
    return {
        "review_required": review_required,
        "priority_level": priority_level,
        "priority_score": score,
        "reasons": reasons,
        "recommended_action": recommended_action,
        "summary": " | ".join(summary_parts),
    }


def build_source_id(url: str, published_at: str, index: int) -> str:
    basis = f"{url}|{published_at}|{index}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def normalize_claim_states(item: dict[str, Any], claim_ids: list[str]) -> dict[str, str]:
    raw_states = safe_dict(item.get("claim_states"))
    single_state = clean_text(item.get("claim_state") or "support") or "support"
    return {claim_id: clean_text(raw_states.get(claim_id) or single_state) or "support" for claim_id in claim_ids}


def load_jsonish_payload(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except Exception:
        return extract_first_json_object(decode_text_file(path))


def load_csv_posts(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [enrich_csv_row({key: value for key, value in row.items()}, path) for row in reader]


def load_csv_comments(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: value for key, value in row.items()} for row in reader]


def discover_payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if post_summary_for(payload) or build_reddit_url(payload):
        return [payload]
    return []


def discover_payload_comments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        comments: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            for key in COMMENT_COLLECTION_KEYS:
                value = item.get(key)
                if isinstance(value, list):
                    comments.extend(comment for comment in value if isinstance(comment, dict))
        return comments
    if not isinstance(payload, dict):
        return []
    for key in COMMENT_COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    nested_items = discover_payload_items(payload)
    if nested_items:
        return discover_payload_comments(nested_items)
    return []


def resolve_items(raw_payload: dict[str, Any], comment_sort_strategy: str) -> tuple[list[dict[str, Any]], str, str, list[dict[str, Any]]]:
    selectors = build_export_selector_hints(raw_payload)
    for key in RESULT_PATH_KEYS:
        candidate = clean_text(raw_payload.get(key))
        if not candidate:
            continue
        source_path = Path(candidate).expanduser()
        if source_path.is_dir():
            posts_path = source_path / "posts.csv"
            if posts_path.exists():
                comments = load_csv_comments(source_path / "comments.csv")
                return (
                    apply_comment_lookup_to_items(load_csv_posts(posts_path), comments, comment_sort_strategy),
                    "csv_directory",
                    str(posts_path),
                    comments,
                )
            selected_posts_path, payload_source = select_export_posts_path(source_path, selectors)
            comments = load_csv_comments(selected_posts_path.parent / "comments.csv")
            return (
                apply_comment_lookup_to_items(load_csv_posts(selected_posts_path), comments, comment_sort_strategy),
                payload_source,
                str(selected_posts_path),
                comments,
            )
        if source_path.suffix.lower() == ".csv":
            comments = load_csv_comments(source_path.parent / "comments.csv")
            return (
                apply_comment_lookup_to_items(load_csv_posts(source_path), comments, comment_sort_strategy),
                "csv_file",
                str(source_path),
                comments,
            )
        payload = load_jsonish_payload(source_path)
        comments = discover_payload_comments(payload)
        return (
            apply_comment_lookup_to_items(discover_payload_items(payload), comments, comment_sort_strategy),
            "result_path",
            str(source_path),
            comments,
        )

    for key in NESTED_RESULT_KEYS:
        nested = raw_payload.get(key)
        items = discover_payload_items(nested)
        if items:
            comments = discover_payload_comments(safe_dict(nested))
            return apply_comment_lookup_to_items(items, comments, comment_sort_strategy), key, "", comments

    items = discover_payload_items(raw_payload)
    if items:
        comments = discover_payload_comments(raw_payload)
        return apply_comment_lookup_to_items(items, comments, comment_sort_strategy), "inline_payload", "", comments
    return [], "empty", "", []


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    comment_sort_strategy = normalize_comment_sort_strategy(
        raw_payload.get("comment_sort_strategy") or raw_payload.get("comment_sort") or raw_payload.get("comment_rank_strategy")
    )
    items, payload_source, source_path, comments = resolve_items(raw_payload, comment_sort_strategy)
    return {
        "topic": clean_text(raw_payload.get("topic") or "reddit-bridge-topic"),
        "analysis_time": analysis_time,
        "questions": clean_string_list(raw_payload.get("questions")),
        "use_case": clean_text(raw_payload.get("use_case") or "reddit-bridge"),
        "source_preferences": clean_string_list(raw_payload.get("source_preferences")) or ["social", "major_news", "official"],
        "mode": clean_text(raw_payload.get("mode") or "generic"),
        "windows": clean_string_list(raw_payload.get("windows")),
        "claims": [item for item in safe_list(raw_payload.get("claims")) if isinstance(item, dict)],
        "market_relevance": clean_string_list(raw_payload.get("market_relevance")),
        "expected_source_families": clean_string_list(raw_payload.get("expected_source_families")),
        "items": items,
        "comment_items": comments,
        "comment_sort_strategy": comment_sort_strategy,
        "payload_source": payload_source,
        "source_path": source_path,
    }


def reddit_bridge_tags(item: dict[str, Any]) -> list[str]:
    tags = ["provider:reddit_bridge", "community"]
    subreddit = (
        normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        or subreddit_from_permalink(item.get("permalink") or item.get("post_permalink"))
    )
    author = author_label_for(item)
    post_type = clean_text(item.get("post_type"))
    flair = clean_text(item.get("flair") or item.get("link_flair_text"))
    listing = reddit_listing(item)
    listing_window = reddit_listing_window(item)
    subreddit_kind = reddit_subreddit_kind(subreddit)
    signal_multiplier = reddit_signal_multiplier(subreddit)
    low_signal = reddit_is_low_signal_subreddit(subreddit)
    outbound_domain = outbound_domain_for(item)
    export_target = clean_text(item.get("bridge_export_target"))
    export_kind = clean_text(item.get("bridge_export_kind"))
    comment_sample_status = clean_text(item.get("comment_sample_status"))
    top_comment_sort_strategy = normalize_comment_sort_strategy(item.get("top_comment_sort_strategy"))
    comment_duplicate_count = max(0, int(item.get("comment_duplicate_count", 0) or 0))
    comment_near_duplicate_count = max(0, int(item.get("comment_near_duplicate_count", 0) or 0))
    comment_near_duplicate_level_value = clean_text(item.get("comment_near_duplicate_level"))

    for tag in (
        f"subreddit:{subreddit}" if subreddit else "",
        f"author:{author}" if author else "",
        f"subreddit_kind:{clean_tag_fragment(subreddit_kind)}" if subreddit_kind else "",
        "subreddit_signal:low" if low_signal else "",
        f"post_type:{clean_tag_fragment(post_type)}" if post_type else "",
        f"flair:{clean_tag_fragment(flair)}" if flair else "",
        f"listing:{clean_tag_fragment(listing)}" if listing else "",
        f"listing_window:{clean_tag_fragment(listing_window)}" if listing_window else "",
        f"signal_weight:{signal_multiplier:.2f}" if signal_multiplier != 1.0 else "",
        f"outbound_domain:{outbound_domain}" if outbound_domain else "",
        f"comment_sample:{clean_tag_fragment(comment_sample_status)}" if comment_sample_status and comment_sample_status != "matched" else "",
        "comment_deduped" if comment_duplicate_count > 0 else "",
        "comment_near_duplicate" if comment_near_duplicate_count > 0 else "",
        f"comment_near_duplicate:{clean_tag_fragment(comment_near_duplicate_level_value)}"
        if comment_near_duplicate_count > 0 and comment_near_duplicate_level_value
        else "",
        f"comment_sort:{clean_tag_fragment(top_comment_sort_strategy)}" if top_comment_sort_strategy and top_comment_sort_strategy != "score_then_recency" else "",
        f"export_target:{export_target}" if export_target else "",
        f"export_kind:{export_kind}" if export_kind else "",
    ):
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def discovery_reason_for(item: dict[str, Any]) -> str:
    source_name = source_name_for(item)
    parts = [f"Imported Reddit discussion from {source_name}"]
    score = numeric_value(item.get("score"))
    comments = numeric_value(item.get("num_comments"))
    awards = numeric_value(item.get("total_awards"))
    flair = clean_text(item.get("flair") or item.get("link_flair_text"))
    post_type = clean_text(item.get("post_type"))
    listing = reddit_listing(item)
    listing_window = reddit_listing_window(item)
    top_comment_count = int(item.get("top_comment_count", 0) or 0)
    declared_comment_count = max(
        0,
        int(
            round(
                numeric_value(
                    item.get("comment_declared_count")
                    or item.get("num_comments")
                    or item.get("comment_count")
                    or item.get("comments_count")
                    or item.get("total_comments")
                )
                or 0
            )
        ),
    )
    comment_duplicate_count = max(0, int(item.get("comment_duplicate_count", 0) or 0))
    comment_near_duplicate_count = max(0, int(item.get("comment_near_duplicate_count", 0) or 0))
    comment_near_duplicate_same_author_count = max(0, int(item.get("comment_near_duplicate_same_author_count", 0) or 0))
    comment_near_duplicate_cross_author_count = max(0, int(item.get("comment_near_duplicate_cross_author_count", 0) or 0))
    outbound_url = normalize_reddit_url(item.get("outbound_url") or item.get("url"))

    metrics: list[str] = []
    if score is not None:
        metrics.append(f"score {int(score) if score.is_integer() else round(score, 2)}")
    if comments is not None:
        metrics.append(f"{int(comments) if comments.is_integer() else round(comments, 2)} comments")
    if awards is not None and awards > 0:
        metrics.append(f"{int(awards) if awards.is_integer() else round(awards, 2)} awards")
    if flair:
        metrics.append(f"flair {flair}")
    if post_type:
        metrics.append(f"type {post_type}")
    if listing:
        listing_label = listing if not listing_window else f"{listing}/{listing_window}"
        metrics.append(f"listing {listing_label}")
    if top_comment_count > 0:
        if declared_comment_count > 0 and top_comment_count != declared_comment_count:
            metrics.append(f"{top_comment_count}/{declared_comment_count} comments sampled")
        else:
            metrics.append(f"{top_comment_count} top comments sampled")
    if comment_duplicate_count > 0:
        metrics.append(f"deduped {comment_duplicate_count} duplicate comments")
    if comment_near_duplicate_count > 0:
        near_duplicate_label = f"flagged {comment_near_duplicate_count} near-duplicate comments"
        if comment_near_duplicate_cross_author_count > 0:
            near_duplicate_label += f" (cross-author {comment_near_duplicate_cross_author_count})"
        elif comment_near_duplicate_same_author_count > 0:
            near_duplicate_label += f" (same-author {comment_near_duplicate_same_author_count})"
        metrics.append(near_duplicate_label)
    if metrics:
        parts.append("(" + ", ".join(metrics) + ")")

    if outbound_url and not is_reddit_url(outbound_url):
        host = urllib.parse.urlparse(outbound_url).netloc.lower()
        if host:
            parts.append(f"linking to {host}")
    return " ".join(parts)


def normalize_candidate(item: dict[str, Any], request: dict[str, Any], index: int) -> dict[str, Any] | None:
    title = post_summary_for(item)
    url = build_reddit_url(item)
    if not title or not url:
        return None

    published_at = parse_datetime(
        item.get("published_at") or item.get("created_utc") or item.get("created_at") or item.get("timestamp"),
        fallback=request["analysis_time"],
    )
    observed_at = parse_datetime(
        item.get("observed_at") or item.get("scraped_at") or item.get("captured_at"),
        fallback=request["analysis_time"],
    )
    claim_ids = clean_string_list(item.get("claim_ids"))
    request_claim_ids = [clean_text(claim.get("claim_id")) for claim in request["claims"] if clean_text(claim.get("claim_id"))]
    if not claim_ids and len(request_claim_ids) == 1:
        claim_ids = request_claim_ids

    published_text = isoformat_or_blank(published_at)
    observed_text = isoformat_or_blank(observed_at)
    subreddit = (
        normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        or subreddit_from_permalink(item.get("permalink") or item.get("post_permalink"))
    )
    excerpt = text_excerpt_for(item)
    raw_metadata = deepcopy(item)
    raw_metadata.setdefault("bridge_tags", reddit_bridge_tags(item))
    raw_metadata.setdefault("reddit_thread_url", url)
    if normalize_reddit_url(item.get("outbound_url") or item.get("url")) and normalize_reddit_url(item.get("outbound_url") or item.get("url")) != url:
        raw_metadata.setdefault("reddit_outbound_url", normalize_reddit_url(item.get("outbound_url") or item.get("url")))
    if subreddit:
        raw_metadata.setdefault("subreddit_normalized", subreddit)
    author = author_label_for(item)
    if author:
        raw_metadata.setdefault("author_normalized", author)
    subreddit_kind = reddit_subreddit_kind(subreddit)
    if subreddit_kind:
        raw_metadata.setdefault("subreddit_kind", subreddit_kind)
    signal_multiplier = reddit_signal_multiplier(subreddit)
    raw_metadata.setdefault("subreddit_signal_multiplier", signal_multiplier)
    if reddit_is_low_signal_subreddit(subreddit):
        raw_metadata.setdefault("subreddit_signal_level", "low")
    listing = reddit_listing(item)
    if listing:
        raw_metadata.setdefault("reddit_listing_normalized", listing)
    listing_window = reddit_listing_window(item)
    if listing_window:
        raw_metadata.setdefault("reddit_listing_window_normalized", listing_window)
    outbound_domain = outbound_domain_for(item)
    if outbound_domain:
        raw_metadata.setdefault("reddit_outbound_domain", outbound_domain)
    if int(item.get("top_comment_count", 0) or 0) > 0:
        raw_metadata.setdefault("top_comment_count", int(item.get("top_comment_count", 0) or 0))
    if clean_text(item.get("top_comment_summary")):
        raw_metadata.setdefault("top_comment_summary", clean_text(item.get("top_comment_summary")))
    if clean_text(item.get("top_comment_excerpt")):
        raw_metadata.setdefault("top_comment_excerpt", clean_text(item.get("top_comment_excerpt")))
    if safe_list(item.get("top_comment_authors")):
        raw_metadata.setdefault("top_comment_authors", clean_string_list(item.get("top_comment_authors")))
    if int(item.get("top_comment_max_score", 0) or 0) > 0:
        raw_metadata.setdefault("top_comment_max_score", int(item.get("top_comment_max_score", 0) or 0))
    if clean_text(item.get("top_comment_sort_strategy")):
        raw_metadata.setdefault("top_comment_sort_strategy", normalize_comment_sort_strategy(item.get("top_comment_sort_strategy")))
    if int(item.get("comment_raw_count", 0) or 0) > 0:
        raw_metadata.setdefault("comment_raw_count", int(item.get("comment_raw_count", 0) or 0))
    if int(item.get("comment_duplicate_count", 0) or 0) > 0:
        raw_metadata.setdefault("comment_duplicate_count", int(item.get("comment_duplicate_count", 0) or 0))
    if int(item.get("comment_near_duplicate_count", 0) or 0) > 0:
        raw_metadata.setdefault("comment_near_duplicate_count", int(item.get("comment_near_duplicate_count", 0) or 0))
    if safe_list(item.get("comment_near_duplicate_examples")):
        raw_metadata.setdefault("comment_near_duplicate_examples", clean_string_list(item.get("comment_near_duplicate_examples")))
        raw_metadata.setdefault(
            "comment_near_duplicate_example_count",
            len(clean_string_list(item.get("comment_near_duplicate_examples"))),
        )
    if int(item.get("comment_near_duplicate_same_author_count", 0) or 0) > 0:
        raw_metadata.setdefault(
            "comment_near_duplicate_same_author_count",
            int(item.get("comment_near_duplicate_same_author_count", 0) or 0),
        )
    if int(item.get("comment_near_duplicate_cross_author_count", 0) or 0) > 0:
        raw_metadata.setdefault(
            "comment_near_duplicate_cross_author_count",
            int(item.get("comment_near_duplicate_cross_author_count", 0) or 0),
        )
    if clean_text(item.get("comment_near_duplicate_level")):
        raw_metadata.setdefault("comment_near_duplicate_level", clean_text(item.get("comment_near_duplicate_level")))
    if int(item.get("comment_declared_count", 0) or 0) > 0:
        raw_metadata.setdefault("comment_declared_count", int(item.get("comment_declared_count", 0) or 0))
    if isinstance(item.get("comment_sample_coverage_ratio"), (int, float)):
        raw_metadata.setdefault("comment_sample_coverage_ratio", round(float(item.get("comment_sample_coverage_ratio")), 4))
    if isinstance(item.get("comment_count_mismatch"), bool):
        raw_metadata.setdefault("comment_count_mismatch", bool(item.get("comment_count_mismatch")))
    if clean_text(item.get("comment_sample_status")):
        raw_metadata.setdefault("comment_sample_status", clean_text(item.get("comment_sample_status")))
    comment_operator_review = build_comment_operator_review(raw_metadata)
    if comment_operator_review:
        raw_metadata["comment_operator_review"] = comment_operator_review
    operator_review_priority = build_operator_review_priority(raw_metadata)
    if operator_review_priority:
        raw_metadata["operator_review_priority"] = operator_review_priority
    return {
        "source_id": build_source_id(url, published_text, index),
        "source_name": source_name_for(item),
        "source_type": "social",
        "origin": "reddit_bridge",
        "published_at": published_text,
        "observed_at": observed_text,
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": normalize_claim_states(item, claim_ids),
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "vessel_ids": clean_string_list(item.get("vessel_ids")),
        "text_excerpt": excerpt,
        "channel": "shadow",
        "access_mode": clean_text(item.get("access_mode") or "public") or "public",
        "raw_metadata": raw_metadata,
        "tags": reddit_bridge_tags(item),
        "post_summary": title,
        "media_summary": "",
        "discovery_reason": clean_text(item.get("discovery_reason") or discovery_reason_for(item)),
    }


def import_to_news_index(request: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_request = {
        "topic": request["topic"],
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": request["questions"],
        "use_case": request["use_case"],
        "source_preferences": request["source_preferences"],
        "mode": request["mode"],
        "windows": request["windows"],
        "claims": deepcopy(request["claims"]),
        "candidates": candidates,
        "market_relevance": request["market_relevance"],
        "expected_source_families": request["expected_source_families"],
    }
    return {"retrieval_request": retrieval_request, "retrieval_result": run_news_index(retrieval_request)}


def build_markdown_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("import_summary"))
    lines = [
        f"# Reddit Bridge Report: {result.get('topic', 'reddit-bridge-topic')}",
        "",
        f"Fetched at: {result.get('fetched_at', '')}",
        f"Payload source: {summary.get('payload_source', '') or 'unknown'}",
        f"Source path: {summary.get('source_path', '') or 'None'}",
        f"Imported / invalid: {summary.get('imported_candidate_count', 0)} / {summary.get('skipped_invalid_count', 0)}",
        f"Comment sort: {summary.get('comment_sort_strategy', 'score_then_recency')}",
        f"Comment samples: {summary.get('comment_sample_count', 0)}",
        f"Posts with comment context: {summary.get('posts_with_comment_context', 0)}",
        f"Partial comment samples: {summary.get('comment_count_mismatch_count', 0)}",
        f"Deduped comment duplicates: {summary.get('comment_duplicate_count_total', 0)}",
        f"Near-duplicate comment cautions: {summary.get('comment_near_duplicate_count_total', 0)}",
        f"Near-duplicate same-author cautions: {summary.get('comment_near_duplicate_same_author_count_total', 0)}",
        f"Near-duplicate cross-author cautions: {summary.get('comment_near_duplicate_cross_author_count_total', 0)}",
        f"Near-duplicate trace examples: {summary.get('comment_near_duplicate_example_count_total', 0)}",
    ]
    retrieval_result = safe_dict(result.get("retrieval_result"))
    operator_review_lines: list[str] = []
    for candidate in safe_list(retrieval_result.get("observations"))[:5]:
        raw_metadata = safe_dict(candidate.get("raw_metadata"))
        operator_review = safe_dict(raw_metadata.get("comment_operator_review"))
        operator_priority = safe_dict(raw_metadata.get("operator_review_priority"))
        review_summary = format_comment_operator_review(operator_review)
        if not review_summary:
            continue
        label = clean_text(candidate.get("source_name") or candidate.get("post_summary") or candidate.get("url"))
        priority_label = clean_text(operator_priority.get("priority_level"))
        prefix = f"[{priority_label}] " if priority_label and priority_label != "none" else ""
        operator_review_lines.append(f"- {prefix}{label}: {review_summary}")
    if operator_review_lines:
        lines.extend(["", "## Operator Review", *operator_review_lines])
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def run_reddit_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    candidates: list[dict[str, Any]] = []
    skipped_invalid = 0
    for index, item in enumerate(request["items"], start=1):
        candidate = normalize_candidate(item, request, index)
        if candidate is None:
            skipped_invalid += 1
            continue
        candidates.append(candidate)

    imported = import_to_news_index(request, candidates)
    posts_with_comment_context = sum(
        1
        for candidate in candidates
        if int(safe_dict(candidate.get("raw_metadata")).get("top_comment_count", 0) or 0) > 0
    )
    comment_count_mismatch_count = sum(
        1
        for candidate in candidates
        if bool(safe_dict(candidate.get("raw_metadata")).get("comment_count_mismatch"))
    )
    comment_duplicate_count_total = sum(
        int(safe_dict(candidate.get("raw_metadata")).get("comment_duplicate_count", 0) or 0)
        for candidate in candidates
    )
    comment_near_duplicate_count_total = sum(
        int(safe_dict(candidate.get("raw_metadata")).get("comment_near_duplicate_count", 0) or 0)
        for candidate in candidates
    )
    comment_near_duplicate_same_author_count_total = sum(
        int(safe_dict(candidate.get("raw_metadata")).get("comment_near_duplicate_same_author_count", 0) or 0)
        for candidate in candidates
    )
    comment_near_duplicate_cross_author_count_total = sum(
        int(safe_dict(candidate.get("raw_metadata")).get("comment_near_duplicate_cross_author_count", 0) or 0)
        for candidate in candidates
    )
    comment_near_duplicate_example_count_total = sum(
        len(clean_string_list(safe_dict(candidate.get("raw_metadata")).get("comment_near_duplicate_examples")))
        for candidate in candidates
    )
    operator_review_required_count = sum(
        1
        for candidate in candidates
        if safe_dict(safe_dict(candidate.get("raw_metadata")).get("operator_review_priority")).get("review_required")
    )
    operator_review_high_priority_count = sum(
        1
        for candidate in candidates
        if safe_dict(safe_dict(candidate.get("raw_metadata")).get("operator_review_priority")).get("priority_level") == "high"
    )
    operator_review_queue = []
    for candidate in candidates:
        raw_metadata = safe_dict(candidate.get("raw_metadata"))
        operator_priority = safe_dict(raw_metadata.get("operator_review_priority"))
        if not operator_priority:
            continue
        priority_level = clean_text(operator_priority.get("priority_level"))
        if priority_level == "none":
            continue
        operator_review_queue.append(
            {
                "source_name": clean_text(candidate.get("source_name")),
                "url": clean_text(candidate.get("url")),
                "priority_level": priority_level,
                "priority_score": max(0, int(operator_priority.get("priority_score", 0) or 0)),
                "summary": clean_text(operator_priority.get("summary")),
                "recommended_action": clean_text(operator_priority.get("recommended_action")),
            }
        )
    operator_review_queue = sorted(
        operator_review_queue,
        key=lambda item: (
            int(item.get("priority_score", 0) or 0),
            clean_text(item.get("priority_level")),
            clean_text(item.get("source_name")),
        ),
        reverse=True,
    )
    result = {
        "status": "ok" if candidates else "failed",
        "workflow_kind": "reddit_bridge",
        "topic": request["topic"],
        "fetched_at": isoformat_or_blank(request["analysis_time"]),
        "import_summary": {
            "payload_source": request["payload_source"],
            "source_path": request["source_path"],
            "imported_candidate_count": len(candidates),
            "skipped_invalid_count": skipped_invalid,
            "comment_sort_strategy": request["comment_sort_strategy"],
            "comment_sample_count": len(request["comment_items"]),
            "posts_with_comment_context": posts_with_comment_context,
            "comment_count_mismatch_count": comment_count_mismatch_count,
            "comment_duplicate_count_total": comment_duplicate_count_total,
            "comment_near_duplicate_count_total": comment_near_duplicate_count_total,
            "comment_near_duplicate_same_author_count_total": comment_near_duplicate_same_author_count_total,
            "comment_near_duplicate_cross_author_count_total": comment_near_duplicate_cross_author_count_total,
            "comment_near_duplicate_example_count_total": comment_near_duplicate_example_count_total,
            "operator_review_required_count": operator_review_required_count,
            "operator_review_high_priority_count": operator_review_high_priority_count,
        },
        "operator_review_queue": operator_review_queue,
        **imported,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_comment_operator_review",
    "build_markdown_report",
    "build_operator_review_priority",
    "format_comment_operator_review",
    "run_reddit_bridge",
    "write_json",
    "load_json",
]
