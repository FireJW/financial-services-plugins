#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from shutil import copy2, which
from typing import Any

from news_index_runtime import (
    isoformat_or_blank,
    load_json,
    parse_datetime,
    run_news_index,
    short_excerpt,
    slugify,
    write_json,
)
from runtime_paths import runtime_subdir


SEARCH_ENDPOINT = "https://duckduckgo.com/html/?q={query}"
STATUS_URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)")
META_CONTENT_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?P<name>[^"\']+)["\'][^>]+content=["\'](?P<content>.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
TIME_RE = re.compile(r"<time[^>]+datetime=[\"'](?P<value>[^\"']+)[\"']", re.IGNORECASE)
LINK_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[^/\s]+/status/\d+")
MEDIA_URL_RE = re.compile(r"https://pbs\.twimg\.com/media/[^\"'?\s>]+", re.IGNORECASE)
TWEET_TEXT_RE = re.compile(
    r'<[^>]+data-testid=["\']tweetText["\'][^>]*>(?P<content>.*?)</[^>]+>',
    re.IGNORECASE | re.DOTALL,
)
ROOT_AREA_QUOTE_RE = re.compile(r"RootWebArea:\s.*?：“(?P<quote>.+?)”\s*/\s*X", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
GENERIC_IMAGE_HINTS = {
    "image",
    "images",
    "photo",
    "photos",
    "picture",
    "pictures",
    "media",
    "graphic",
    "图像",
    "图片",
    "照片",
}
BLOCKED_TEXT_MARKERS = [
    "something went wrong",
    "javascript 不可用",
    "javascript is disabled",
    "privacy related extensions may cause issues",
]
CLUE_LINE_HINTS = (
    "morgan stanley",
    "focus list",
    "strategy",
    "research",
    "reflation",
    "exhibit",
    "thematic",
)
TICKER_CLUE_RE = re.compile(r"\b(?:\d{6}\.(?:SS|SZ)|\d{4}\.HK|[A-Z]{2,5}\.N)\b")
DEFAULT_X_RESULT_FILENAME = "x-index-result.json"
DEFAULT_X_REPORT_FILENAME = "x-index-report.md"
DEFAULT_REUSE_SCAN_LIMIT = 24
DEFAULT_WINDOW_QUERY_LIMIT = 6
CODEX_IAB_SESSION_STRATEGIES = {"codex_iab", "codex_iab_capture", "browser_use", "browser_use_capture"}


@dataclass
class FetchArtifact:
    url: str
    final_url: str
    html: str
    visible_text: str
    accessibility_text: str
    links_text: str
    screenshot_path: str
    error: str
    media_items: list[dict[str, Any]] = field(default_factory=list)
    session_used: bool = False
    session_source: str = ""
    session_status: str = ""
    session_notes: list[str] = field(default_factory=list)


SCRIPT_DIR = Path(__file__).resolve().parent


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_text(text: Any) -> str:
    return WHITESPACE_RE.sub(" ", unescape(str(text or "")).replace("\u200b", " ")).strip()


def unique_cleaned_strings(values: list[Any], *, limit: int = 12, min_length: int = 0) -> list[str]:
    cleaned_values: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or (min_length and len(cleaned) < min_length):
            continue
        if cleaned not in cleaned_values:
            cleaned_values.append(cleaned)
        if len(cleaned_values) >= limit:
            break
    return cleaned_values


def derive_phrase_clues_from_ocr_text(text: str) -> list[str]:
    if not clean_text(text):
        return []
    raw_candidates: list[str] = []
    for line in re.split(r"[\r\n]+", str(text)):
        cleaned = clean_text(line)
        lowered = cleaned.lower()
        if not cleaned or len(cleaned) < 12 or len(cleaned) > 140:
            continue
        if any(hint in lowered for hint in CLUE_LINE_HINTS):
            raw_candidates.append(cleaned)
            if ":" in cleaned:
                suffix = clean_text(cleaned.split(":", 1)[1])
                if suffix and suffix != cleaned:
                    raw_candidates.append(suffix)
    return unique_cleaned_strings(raw_candidates, limit=10, min_length=12)


def derive_entity_clues_from_ocr_text(text: str) -> list[str]:
    if not clean_text(text):
        return []
    return unique_cleaned_strings(TICKER_CLUE_RE.findall(text), limit=12, min_length=5)


def build_x_window_queries(request: dict[str, Any]) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    seen_queries: set[str] = set()
    handles = [item.lstrip("@") for item in request.get("account_allowlist", []) if clean_text(item)]
    keywords = unique_cleaned_strings(request.get("keywords", []), limit=8, min_length=3)
    phrase_clues = unique_cleaned_strings(request.get("phrase_clues", []), limit=8, min_length=8)
    entity_clues = unique_cleaned_strings(request.get("entity_clues", []), limit=8, min_length=3)
    query_overrides = unique_cleaned_strings(request.get("query_overrides", []), limit=8, min_length=3)

    def add_query(query: str, reason: str) -> None:
        normalized_query = clean_text(query)
        if not normalized_query or normalized_query in seen_queries or len(queries) >= DEFAULT_WINDOW_QUERY_LIMIT:
            return
        seen_queries.add(normalized_query)
        queries.append({"query": normalized_query, "reason": clean_text(reason) or "window_capture"})

    for query in query_overrides:
        add_query(query, "query_override")

    for handle in handles:
        for phrase in phrase_clues[:4]:
            add_query(f'from:{handle} "{phrase}"', f"allowlist_phrase:@{handle}|phrase:{phrase}")
        for keyword in keywords[:3]:
            add_query(f'from:{handle} "{keyword}"', f"allowlist_keyword:@{handle}|keyword:{keyword}")
        for entity in entity_clues[:4]:
            add_query(f'from:{handle} "{entity}"', f"allowlist_entity:@{handle}|entity:{entity}")
        for phrase in phrase_clues[:2]:
            for entity in entity_clues[:2]:
                add_query(
                    f'from:{handle} "{phrase}" "{entity}"',
                    f"allowlist_phrase_entity:@{handle}|phrase:{phrase}|entity:{entity}",
                )

    if not queries:
        for phrase in phrase_clues[:4]:
            add_query(f'"{phrase}"', f"phrase:{phrase}")
        for keyword in keywords[:3]:
            add_query(f'"{keyword}"', f"keyword:{keyword}")
        for entity in entity_clues[:4]:
            add_query(f'"{entity}"', f"entity:{entity}")

    return queries[:DEFAULT_WINDOW_QUERY_LIMIT]


def build_window_capture_hints(request: dict[str, Any]) -> dict[str, Any]:
    manual_urls = [canonical_status_url(url) for url in request.get("manual_urls", []) if clean_text(url)]
    search_queries = build_x_window_queries(request)
    search_urls = [
        {
            "query": item["query"],
            "reason": item["reason"],
            "url": f"https://x.com/search?q={urllib.parse.quote_plus(item['query'])}&src=typed_query&f=live",
        }
        for item in search_queries
    ]
    notes = [
        "Prefer reusing the last successful x-index result or running session before bootstrapping a fresh X flow.",
        "On Windows, prefer a new Edge window in the existing signed-in profile before any interruptive relaunch.",
    ]
    return {
        "preferred": True,
        "manual_urls": manual_urls,
        "search_urls": search_urls,
        "notes": notes,
    }


def build_search_queries(request: dict[str, Any]) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    seen_queries: set[str] = set()
    max_queries = max(1, int(request.get("max_search_queries", 24)))
    handles = [item.lstrip("@") for item in request.get("account_allowlist", []) if clean_text(item)]
    keywords = unique_cleaned_strings(request.get("keywords", []), limit=10, min_length=3)
    phrase_clues = unique_cleaned_strings(request.get("phrase_clues", []), limit=10, min_length=8)
    entity_clues = unique_cleaned_strings(request.get("entity_clues", []), limit=12, min_length=3)
    query_overrides = unique_cleaned_strings(request.get("query_overrides", []), limit=12, min_length=3)

    def add_query(query: str, reason: str) -> None:
        normalized_query = clean_text(query)
        if not normalized_query or normalized_query in seen_queries or len(queries) >= max_queries:
            return
        seen_queries.add(normalized_query)
        queries.append({"query": normalized_query, "reason": clean_text(reason) or "derived"})

    for query in query_overrides:
        add_query(query, "query_override")

    for keyword in keywords:
        add_query(f'site:x.com/status "{keyword}"', f"keyword:{keyword}")
        for handle in handles:
            add_query(f'site:x.com/{handle}/status "{keyword}"', f"keyword:{keyword}|allowlist:@{handle}")

    for phrase in phrase_clues:
        add_query(f'site:x.com/status "{phrase}"', f"phrase:{phrase}")
        for handle in handles:
            add_query(f'site:x.com/{handle}/status "{phrase}"', f"phrase:{phrase}|allowlist:@{handle}")
        for entity in entity_clues[:6]:
            add_query(f'site:x.com/status "{phrase}" "{entity}"', f"phrase:{phrase}|entity:{entity}")
            for handle in handles:
                add_query(
                    f'site:x.com/{handle}/status "{phrase}" "{entity}"',
                    f"phrase:{phrase}|entity:{entity}|allowlist:@{handle}",
                )

    for keyword in keywords[:6]:
        for entity in entity_clues[:6]:
            add_query(f'site:x.com/status "{keyword}" "{entity}"', f"keyword:{keyword}|entity:{entity}")
            for handle in handles:
                add_query(
                    f'site:x.com/{handle}/status "{keyword}" "{entity}"',
                    f"keyword:{keyword}|entity:{entity}|allowlist:@{handle}",
                )

    for handle in handles:
        for entity in entity_clues[:6]:
            add_query(f'site:x.com/{handle}/status "{entity}"', f"entity:{entity}|allowlist:@{handle}")

    return queries[:max_queries]


def build_same_author_scan_queries(root_post: dict[str, Any], request: dict[str, Any]) -> list[dict[str, str]]:
    handle = clean_text(root_post.get("author_handle")).lstrip("@")
    if not handle:
        return []

    queries: list[dict[str, str]] = []
    seen_queries: set[str] = set()
    max_queries = max(1, int(request.get("same_author_scan_limit", 12)))
    keywords = unique_cleaned_strings(request.get("keywords", []), limit=8, min_length=3)
    phrase_clues = unique_cleaned_strings(request.get("phrase_clues", []), limit=8, min_length=8)
    entity_clues = unique_cleaned_strings(request.get("entity_clues", []), limit=8, min_length=3)

    def add_query(query: str, reason: str) -> None:
        normalized_query = clean_text(query)
        if not normalized_query or normalized_query in seen_queries or len(queries) >= max_queries:
            return
        seen_queries.add(normalized_query)
        queries.append({"query": normalized_query, "reason": clean_text(reason) or "same_author_scan"})

    for phrase in phrase_clues:
        add_query(f'site:x.com/{handle}/status "{phrase}"', f"same_author_phrase:@{handle}|phrase:{phrase}")
        for entity in entity_clues[:4]:
            add_query(
                f'site:x.com/{handle}/status "{phrase}" "{entity}"',
                f"same_author_phrase:@{handle}|phrase:{phrase}|entity:{entity}",
            )

    for keyword in keywords[:4]:
        add_query(f'site:x.com/{handle}/status "{keyword}"', f"same_author_keyword:@{handle}|keyword:{keyword}")
        for entity in entity_clues[:4]:
            add_query(
                f'site:x.com/{handle}/status "{keyword}" "{entity}"',
                f"same_author_keyword:@{handle}|keyword:{keyword}|entity:{entity}",
            )

    for entity in entity_clues[:6]:
        add_query(f'site:x.com/{handle}/status "{entity}"', f"same_author_entity:@{handle}|entity:{entity}")

    if not queries:
        add_query(f"site:x.com/{handle}/status", f"same_author_handle:@{handle}")
    return queries[:max_queries]


def meaningful_image_hint(text: Any) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower().strip(" .,:;!?")
    return "" if lowered in GENERIC_IMAGE_HINTS else cleaned


def canonical_status_url(url: str) -> str:
    match = STATUS_URL_RE.search(url)
    if not match:
        return clean_text(url)
    handle, status_id = match.groups()
    return f"https://x.com/{handle}/status/{status_id}"


def strip_tags(fragment: str) -> str:
    return clean_text(TAG_RE.sub(" ", fragment))


def extract_meta_contents(html: str) -> dict[str, str]:
    contents: dict[str, str] = {}
    for match in META_CONTENT_RE.finditer(html):
        name = clean_text(match.group("name")).lower()
        if name and name not in contents:
            contents[name] = clean_text(match.group("content"))
    return contents


def looks_blocked(text: str, html: str) -> bool:
    text_haystack = clean_text(text).lower()
    html_haystack = clean_text(html).lower()
    if any(marker in text_haystack for marker in BLOCKED_TEXT_MARKERS):
        return True
    if not text_haystack and any(marker in html_haystack for marker in BLOCKED_TEXT_MARKERS):
        return True
    # X includes a dormant ScriptLoadFailure node in healthy HTML, so the token
    # alone is not a failure signal.
    if "scriptloadfailure" in html_haystack and any(
        marker in text_haystack for marker in ("something went wrong", "javascript is disabled", "javascript 不可用")
    ):
        return True
    return False


def summarize_text(text: str, limit: int = 280) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned)
    summary = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{summary} {sentence}".strip()
        if len(candidate) > limit and summary:
            break
        summary = candidate
        if len(summary) >= limit:
            break
    return summary or short_excerpt(cleaned, limit=limit)


def summarize_text(text: str, limit: int = 280) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned)
    summary = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{summary} {sentence}".strip()
        if len(candidate) > limit and summary:
            break
        summary = candidate
        if len(summary) >= limit:
            break
    return summary or short_excerpt(cleaned, limit=limit)


def detect_conflict(post_text: str, media_text: str) -> str:
    post_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", post_text))
    media_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", media_text))
    if post_numbers and media_numbers and not (post_numbers & media_numbers):
        return "Image details include numbers not present in the main post text. Verify before treating them as the same claim."
    return ""


def image_relevance(post_text: str, media_text: str) -> str:
    if not media_text:
        return "low"
    post_tokens = {token for token in re.findall(r"[A-Za-z0-9]{3,}", post_text.lower())}
    media_tokens = {token for token in re.findall(r"[A-Za-z0-9]{3,}", media_text.lower())}
    overlap = len(post_tokens & media_tokens)
    if overlap >= 3:
        return "high"
    if overlap >= 1:
        return "medium"
    return "low"


def parse_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    output_dir = (
        Path(raw_payload.get("output_dir", "")).expanduser().resolve()
        if clean_text(raw_payload.get("output_dir"))
        else runtime_subdir("x-index", slugify(str(raw_payload.get("topic", "x-topic")), "x-topic"), analysis_time.strftime("%Y%m%dT%H%M%SZ"))
    )
    browser_session_raw = raw_payload.get("browser_session") if isinstance(raw_payload.get("browser_session"), dict) else {}
    browser_session_strategy = clean_text(
        browser_session_raw.get("strategy")
        or raw_payload.get("browser_session_strategy")
        or ("cookie_file" if clean_text(browser_session_raw.get("cookie_file") or raw_payload.get("session_cookie_file")) else "")
        or ("remote_debugging" if clean_text(browser_session_raw.get("cdp_endpoint") or raw_payload.get("browser_debug_endpoint")) else "")
    )
    raw_ocr_root_text = str(raw_payload.get("ocr_root_text") or "")
    ocr_root_text = clean_text(raw_ocr_root_text)
    phrase_clues = unique_cleaned_strings(
        [
            *[item for item in raw_payload.get("phrase_clues", []) if clean_text(item)],
            *derive_phrase_clues_from_ocr_text(raw_ocr_root_text),
        ],
        limit=10,
        min_length=8,
    )
    entity_clues = unique_cleaned_strings(
        [
            *[item for item in raw_payload.get("entity_clues", []) if clean_text(item)],
            *derive_entity_clues_from_ocr_text(raw_ocr_root_text),
        ],
        limit=12,
        min_length=3,
    )
    return {
        "topic": clean_text(raw_payload.get("topic") or "x-index-topic"),
        "analysis_time": analysis_time,
        "keywords": [clean_text(item) for item in raw_payload.get("keywords", []) if clean_text(item)],
        "phrase_clues": phrase_clues,
        "entity_clues": entity_clues,
        "query_overrides": [clean_text(item) for item in raw_payload.get("query_overrides", []) if clean_text(item)],
        "account_allowlist": [clean_text(item).lstrip("@") for item in raw_payload.get("account_allowlist", []) if clean_text(item)],
        "manual_urls": [clean_text(item) for item in raw_payload.get("manual_urls", []) if clean_text(item)],
        "seed_posts": [item for item in raw_payload.get("seed_posts", []) if isinstance(item, dict)],
        "claims": [item for item in raw_payload.get("claims", []) if isinstance(item, dict)],
        "market_relevance": [clean_text(item) for item in raw_payload.get("market_relevance", []) if clean_text(item)],
        "include_threads": bool(raw_payload.get("include_threads", True)),
        "include_images": bool(raw_payload.get("include_images", True)),
        "lookback": clean_text(raw_payload.get("lookback") or "24h"),
        "max_candidates": int(raw_payload.get("max_candidates", 50)),
        "max_kept_posts": int(raw_payload.get("max_kept_posts", 10)),
        "max_thread_posts": int(raw_payload.get("max_thread_posts", 10)),
        "max_search_queries": int(raw_payload.get("max_search_queries", 24)),
        "same_author_scan_window_hours": max(1, int(raw_payload.get("same_author_scan_window_hours", 48))),
        "same_author_scan_limit": max(1, int(raw_payload.get("same_author_scan_limit", 12))),
        "access_mode": clean_text(raw_payload.get("access_mode") or "public_first_browser_fallback"),
        "output_dir": output_dir,
        "ocr_root_text": ocr_root_text,
        "reuse_recent_runs": bool(raw_payload.get("reuse_recent_runs", True)),
        "reuse_recent_hours": max(1, int(raw_payload.get("reuse_recent_hours", 168))),
        "reuse_max_seed_posts": max(1, int(raw_payload.get("reuse_max_seed_posts", 6))),
        "browser_session": {
            "strategy": browser_session_strategy,
            "cookie_file": clean_text(browser_session_raw.get("cookie_file") or raw_payload.get("session_cookie_file")),
            "cdp_endpoint": clean_text(browser_session_raw.get("cdp_endpoint") or raw_payload.get("browser_debug_endpoint") or "http://127.0.0.1:9222"),
            "required": bool(browser_session_raw.get("required", raw_payload.get("browser_session_required", False))),
            "browser_name": clean_text(browser_session_raw.get("browser_name") or raw_payload.get("browser_name") or "edge"),
            "wait_ms": int(browser_session_raw.get("wait_ms", raw_payload.get("browser_wait_ms", 8000))),
        },
    }


def resolve_browse_command() -> str | None:
    env_value = clean_text(os.environ.get("GSTACK_BROWSE_CMD"))
    candidates = [
        env_value,
        "D:\\Users\\rickylu\\.codex\\skills\\gstack\\browse\\dist\\browse.cmd",
        "C:\\Users\\rickylu\\.codex\\skills\\gstack\\browse\\dist\\browse.cmd",
        str(Path.home() / ".codex" / "skills" / "gstack" / "browse" / "dist" / "browse.cmd"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return which("browse.cmd")


def resolve_node_command() -> str | None:
    candidates = [
        clean_text(os.environ.get("NODE_EXE")),
        "D:\\nodejs\\node.exe",
        "C:\\Program Files\\nodejs\\node.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return which("node")


def resolve_cdp_fetch_script() -> Path | None:
    candidate = SCRIPT_DIR / "browser_session_fetch.js"
    return candidate if candidate.exists() else None


def probe_cdp_endpoint(endpoint: str) -> tuple[bool, str]:
    normalized_endpoint = clean_text(endpoint).rstrip("/")
    if not normalized_endpoint:
        return False, "browser_session.cdp_endpoint was not provided"
    version_url = f"{normalized_endpoint}/json/version"
    try:
        request = urllib.request.Request(version_url, headers={"User-Agent": "Codex-XIndex/1.0"})
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore") or "{}")
        browser_name = clean_text(payload.get("Browser"))
        return True, browser_name or version_url
    except Exception as exc:  # pragma: no cover - exact transport failure varies by host
        return False, clean_text(exc) or "endpoint probe failed"


def unique_notes(values: list[str]) -> list[str]:
    notes: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    return notes


def normalize_browser_session_strategy(value: Any) -> str:
    strategy = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    if strategy in CODEX_IAB_SESSION_STRATEGIES:
        return "codex_iab"
    return strategy


def prepare_session_context(request: dict[str, Any]) -> dict[str, Any]:
    session_request = request.get("browser_session", {})
    strategy = normalize_browser_session_strategy(session_request.get("strategy"))
    context = {
        "requested": bool(strategy),
        "strategy": strategy,
        "required": bool(session_request.get("required")),
        "active": False,
        "status": "disabled" if not strategy else "unavailable",
        "source": "",
        "cookie_file": "",
        "cdp_endpoint": "",
        "wait_ms": int(session_request.get("wait_ms", 8000)),
        "notes": [],
    }
    if not strategy:
        return context

    if strategy == "codex_iab":
        context.update(
            {
                "active": False,
                "status": "operator_capture_required",
                "source": "codex_iab",
                "notes": [
                    "Codex IAB Browser Use runs inside the active Codex session and cannot be launched from this Python runtime.",
                    "Capture the page with Browser Use, then import that artifact through opencli-index with input_mode=codex_iab.",
                ],
            }
        )
        return context

    if strategy == "cookie_file":
        raw_path = clean_text(session_request.get("cookie_file"))
        if not raw_path:
            context["notes"] = ["browser_session.cookie_file was not provided"]
            return context
        cookie_path = Path(raw_path).expanduser()
        if not cookie_path.exists():
            context["notes"] = [f"cookie file not found: {cookie_path}"]
            return context
        safe_cookie_path = request["output_dir"] / "browser-session-cookies.json"
        safe_cookie_path.parent.mkdir(parents=True, exist_ok=True)
        if cookie_path.resolve() != safe_cookie_path.resolve():
            copy2(cookie_path, safe_cookie_path)
        context.update(
            {
                "active": True,
                "status": "ready",
                "source": "cookie_file",
                "cookie_file": str(safe_cookie_path),
                "notes": [f"using cookie file copy at {safe_cookie_path}"],
            }
        )
        return context

    if strategy == "remote_debugging":
        node_cmd = resolve_node_command()
        script_path = resolve_cdp_fetch_script()
        endpoint = clean_text(session_request.get("cdp_endpoint") or "http://127.0.0.1:9222")
        notes: list[str] = []
        endpoint_reachable = False
        if not node_cmd:
            notes.append("node runtime not found for remote debugging helper")
        if not script_path:
            notes.append("browser_session_fetch.js helper is missing")
        if not endpoint:
            notes.append("browser_session.cdp_endpoint was not provided")
        if node_cmd and script_path and endpoint:
            endpoint_reachable, endpoint_detail = probe_cdp_endpoint(endpoint)
            if not endpoint_reachable:
                notes.append(f"remote debugging endpoint is not reachable: {endpoint_detail}")
                notes.append(
                    "Prefer a new Edge window in the existing signed-in profile before any interruptive close-and-relaunch step."
                )
        context.update(
            {
                "active": bool(node_cmd and script_path and endpoint and endpoint_reachable),
                "status": "ready" if node_cmd and script_path and endpoint and endpoint_reachable else "unavailable",
                "source": "remote_debugging",
                "cdp_endpoint": endpoint,
                "notes": notes or [f"will attach to {endpoint}"],
            }
        )
        return context

    context["notes"] = [f"unsupported browser session strategy: {strategy}"]
    return context


def parse_chain_output(output: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"^\[(?P<cmd>[^\]]+)\]\s?(?P<body>.*?)(?=^\[[^\]]+\]\s|\Z)", output, re.MULTILINE | re.DOTALL)
    )
    parsed: dict[str, str] = {}
    for match in matches:
        parsed[match.group("cmd").strip().lower()] = match.group("body").strip()
    return parsed


def run_chain(commands: list[list[str]]) -> tuple[dict[str, str], str]:
    browse_cmd = resolve_browse_command()
    if not browse_cmd:
        return {}, "browse command not found"

    process = subprocess.run(
        ["cmd.exe", "/c", browse_cmd, "chain"],
        input=json.dumps(commands),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
        timeout=180,
    )
    output = (process.stdout or "") + ("\n" + process.stderr if process.stderr else "")
    parsed = parse_chain_output(output)
    if process.returncode != 0 and "goto" not in parsed:
        return parsed, clean_text(output)
    return parsed, ""


def build_chain_commands(url: str, screenshot_path: Path, session_context: dict[str, Any] | None = None) -> list[list[str]]:
    commands: list[list[str]] = []
    if session_context and session_context.get("strategy") == "cookie_file" and session_context.get("active"):
        commands.append(["cookie-import", str(session_context.get("cookie_file", ""))])
    commands.extend(
        [
            ["goto", url],
            ["url"],
            ["text"],
            ["accessibility"],
            ["links"],
            ["html"],
            ["screenshot", "--viewport", str(screenshot_path)],
        ]
    )
    return commands


def fetch_page_via_remote_debugging(url: str, screenshot_path: Path, session_context: dict[str, Any]) -> FetchArtifact:
    node_cmd = resolve_node_command()
    script_path = resolve_cdp_fetch_script()
    if not node_cmd or not script_path:
        return FetchArtifact(
            url=url,
            final_url=url,
            html="",
            visible_text="",
            accessibility_text="",
            links_text="",
            screenshot_path="",
            error="remote debugging helper is unavailable",
            media_items=[],
            session_used=False,
            session_source="remote_debugging",
            session_status="unavailable",
            session_notes=unique_notes(session_context.get("notes", [])),
        )

    process = subprocess.run(
        [
            node_cmd,
            str(script_path),
            "--endpoint",
            str(session_context.get("cdp_endpoint", "")),
            "--url",
            url,
            "--screenshot",
            str(screenshot_path),
            "--wait-ms",
            str(session_context.get("wait_ms", 8000)),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=180,
    )
    stdout = clean_text(process.stdout)
    stderr = clean_text(process.stderr)
    if process.returncode != 0:
        return FetchArtifact(
            url=url,
            final_url=url,
            html="",
            visible_text="",
            accessibility_text="",
            links_text="",
            screenshot_path="",
            error=stderr or stdout or "remote debugging fetch failed",
            media_items=[],
            session_used=False,
            session_source="remote_debugging",
            session_status="failed",
            session_notes=unique_notes([*session_context.get("notes", []), stderr or stdout]),
        )
    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return FetchArtifact(
            url=url,
            final_url=url,
            html="",
            visible_text="",
            accessibility_text="",
            links_text="",
            screenshot_path="",
            error=stdout or "remote debugging helper returned invalid JSON",
            media_items=[],
            session_used=False,
            session_source="remote_debugging",
            session_status="failed",
            session_notes=unique_notes([*session_context.get("notes", []), stdout]),
        )

    return FetchArtifact(
        url=url,
        final_url=clean_text(payload.get("final_url")) or url,
        html=str(payload.get("html", "")),
        visible_text=str(payload.get("visible_text", "")),
        accessibility_text=str(payload.get("accessibility_text", "")),
        links_text=str(payload.get("links_text", "")),
        screenshot_path=clean_text(payload.get("screenshot_path")),
        error=clean_text(payload.get("error")),
        media_items=deepcopy(payload.get("media_items", [])) if isinstance(payload.get("media_items"), list) else [],
        session_used=True,
        session_source="remote_debugging",
        session_status="ready",
        session_notes=unique_notes([*session_context.get("notes", []), clean_text(payload.get("session_note"))]),
    )


def fetch_page(url: str, screenshot_path: Path, session_context: dict[str, Any] | None = None) -> FetchArtifact:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    if session_context and session_context.get("strategy") == "remote_debugging" and session_context.get("active"):
        remote_artifact = fetch_page_via_remote_debugging(url, screenshot_path, session_context)
        if not remote_artifact.error or session_context.get("required"):
            return remote_artifact
        fallback_artifact = fetch_page(url, screenshot_path, None)
        fallback_artifact.error = clean_text(f"remote debugging failed; fell back to public browse: {remote_artifact.error}")
        fallback_artifact.session_notes = unique_notes([*remote_artifact.session_notes, fallback_artifact.error])
        fallback_artifact.session_source = "remote_debugging"
        fallback_artifact.session_status = "fallback_public"
        return fallback_artifact

    parsed, error = run_chain(build_chain_commands(url, screenshot_path, session_context))
    goto_output = clean_text(parsed.get("goto", ""))
    if not error and "error" in goto_output.lower():
        error = goto_output
    return FetchArtifact(
        url=url,
        final_url=clean_text(parsed.get("url")) or url,
        html=parsed.get("html", ""),
        visible_text=parsed.get("text", ""),
        accessibility_text=parsed.get("accessibility", ""),
        links_text=parsed.get("links", ""),
        screenshot_path=str(screenshot_path) if screenshot_path.exists() else "",
        error=error,
        media_items=[],
        session_used=bool(session_context and session_context.get("strategy") == "cookie_file" and session_context.get("active")),
        session_source=clean_text(session_context.get("source")) if session_context else "",
        session_status=clean_text(session_context.get("status")) if session_context else "",
        session_notes=unique_notes(
            [
                *(session_context.get("notes", []) if session_context else []),
                clean_text(parsed.get("cookie-import", "")),
            ]
        ),
    )


def maybe_fetch_search_results(query: str) -> list[str]:
    request = urllib.request.Request(
        SEARCH_ENDPOINT.format(query=urllib.parse.quote_plus(query)),
        headers={"User-Agent": "Codex-XIndex/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8", errors="ignore")
    urls = []
    for url in LINK_RE.findall(html):
        normalized = canonical_status_url(url)
        if normalized and normalized not in urls:
            urls.append(normalized)
    return urls


def extract_status_urls_from_blob(*parts: str) -> list[str]:
    urls: list[str] = []
    for part in parts:
        haystack = clean_text(part)
        if not haystack:
            continue
        for handle, status_id in STATUS_URL_RE.findall(haystack):
            normalized = canonical_status_url(f"https://x.com/{handle}/status/{status_id}")
            if normalized and normalized not in urls:
                urls.append(normalized)
    return urls


def maybe_fetch_x_search_results(search_url: str, session_context: dict[str, Any], screenshot_path: Path) -> list[str]:
    artifact = fetch_page(search_url, screenshot_path, session_context)
    if clean_text(artifact.error):
        return []
    return extract_status_urls_from_blob(artifact.final_url, artifact.links_text, artifact.html)


def discover_search_candidates(request: dict[str, Any], session_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    search_urls = build_window_capture_hints(request).get("search_urls", []) if session_context and session_context.get("strategy") == "remote_debugging" and session_context.get("active") else []

    for index, item in enumerate(search_urls, start=1):
        search_url = clean_text(item.get("url")) if isinstance(item, dict) else ""
        query = clean_text(item.get("query")) if isinstance(item, dict) else ""
        reason = clean_text(item.get("reason")) if isinstance(item, dict) else "x_live_search"
        if not search_url:
            continue
        screenshot_path = request["output_dir"] / f"x-search-{index}.png"
        try:
            for url in maybe_fetch_x_search_results(search_url, session_context, screenshot_path):
                if len(discovered) >= request.get("max_candidates", 50):
                    break
                if any(item.get("post_url") == url for item in discovered):
                    continue
                discovered.append(
                    {
                        "post_url": url,
                        "discovery_reason": f"x_live_search:{reason}",
                        "search_query": query,
                        "search_url": search_url,
                        "session_source": clean_text(session_context.get("source")),
                    }
                )
        except OSError as exc:
            discovered.append(
                {
                    "post_url": "",
                    "discovery_reason": f"x_live_search:{reason}",
                    "search_query": query,
                    "search_url": search_url,
                    "blocked_reason": f"x_live_search_failed: {exc}",
                }
            )
        if len(discovered) >= request.get("max_candidates", 50):
            break

    for query_spec in build_search_queries(request):
        query = query_spec.get("query", "")
        reason = query_spec.get("reason", "")
        try:
            for url in maybe_fetch_search_results(query):
                if len(discovered) >= request.get("max_candidates", 50):
                    break
                if any(item.get("post_url") == url for item in discovered):
                    continue
                discovered.append({"post_url": url, "discovery_reason": reason, "search_query": query})
        except OSError as exc:
            discovered.append(
                {
                    "post_url": "",
                    "discovery_reason": reason,
                    "search_query": query,
                    "blocked_reason": f"search_fetch_failed: {exc}",
                }
            )
        if len(discovered) >= request.get("max_candidates", 50):
            break
    return discovered


def candidate_reuse_roots(request: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for candidate in [request.get("output_dir", Path.cwd()).parent, runtime_subdir("x-index")]:
        path = Path(candidate).resolve()
        if path.exists() and path not in roots:
            roots.append(path)
    return roots


def cached_post_is_reusable(post: dict[str, Any]) -> bool:
    if not clean_text(post.get("post_url")):
        return False
    if clean_text(post.get("access_mode")) == "blocked" and not any(
        [
            clean_text(post.get("post_text_raw")),
            clean_text(post.get("root_post_screenshot_path")),
            isinstance(post.get("media_items"), list) and post.get("media_items"),
        ]
    ):
        return False
    return bool(
        clean_text(post.get("post_text_raw"))
        or clean_text(post.get("root_post_screenshot_path"))
        or (isinstance(post.get("media_items"), list) and post.get("media_items"))
    )


def score_cached_result_match(result_payload: dict[str, Any], request: dict[str, Any]) -> int:
    result_request = result_payload.get("request", {}) if isinstance(result_payload.get("request"), dict) else {}
    current_topic = clean_text(request.get("topic")).lower()
    previous_topic = clean_text(result_request.get("topic")).lower()
    score = 0
    if current_topic and previous_topic:
        if current_topic == previous_topic:
            score += 12
        elif current_topic in previous_topic or previous_topic in current_topic:
            score += 6

    author_handles = {
        clean_text(post.get("author_handle")).lstrip("@").lower()
        for post in result_payload.get("x_posts", [])
        if isinstance(post, dict) and clean_text(post.get("author_handle"))
    }
    allowlist = {clean_text(item).lstrip("@").lower() for item in request.get("account_allowlist", []) if clean_text(item)}
    score += min(12, 6 * len(author_handles & allowlist))

    haystack_parts: list[str] = []
    for post in result_payload.get("x_posts", []):
        if not isinstance(post, dict):
            continue
        haystack_parts.extend(
            [
                clean_text(post.get("post_text_raw")),
                clean_text(post.get("post_summary")),
                clean_text(post.get("media_summary")),
                clean_text(post.get("combined_summary")),
            ]
        )
    flattened_haystack = " ".join(part for part in haystack_parts if part).lower()
    phrase_hits = sum(1 for clue in request.get("phrase_clues", []) if clean_text(clue).lower() in flattened_haystack)
    entity_hits = sum(1 for clue in request.get("entity_clues", []) if clean_text(clue).lower() in flattened_haystack)
    keyword_hits = sum(1 for clue in request.get("keywords", []) if clean_text(clue).lower() in flattened_haystack)
    score += min(12, phrase_hits * 4)
    score += min(10, entity_hits * 3)
    score += min(6, keyword_hits * 2)
    return score


def discover_reusable_candidates(request: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "enabled": bool(request.get("reuse_recent_runs", True)),
        "matched_results": 0,
        "reused_posts": 0,
        "result_paths": [],
        "notes": [],
        "candidates": [],
    }
    if not summary["enabled"]:
        summary["notes"].append("recent x-index reuse is disabled for this run")
        return summary

    cutoff = request["analysis_time"] - timedelta(hours=max(1, int(request.get("reuse_recent_hours", 168))))
    result_candidates: list[dict[str, Any]] = []
    for root in candidate_reuse_roots(request):
        for path in root.rglob(DEFAULT_X_RESULT_FILENAME):
            if path.parent.resolve() == request["output_dir"].resolve():
                continue
            try:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified_at < cutoff:
                continue
            result_candidates.append({"path": path.resolve(), "modified_at": modified_at})

    if not result_candidates:
        summary["notes"].append("no recent x-index result files were available for reuse")
        return summary

    deduped_result_candidates: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for item in sorted(result_candidates, key=lambda candidate: candidate["modified_at"], reverse=True):
        path = item["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        deduped_result_candidates.append(item)
        if len(deduped_result_candidates) >= DEFAULT_REUSE_SCAN_LIMIT:
            break

    matched_results: list[dict[str, Any]] = []
    for item in deduped_result_candidates:
        path = item["path"]
        try:
            payload = load_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        score = score_cached_result_match(payload, request)
        if score <= 0:
            continue
        reusable_posts = [
            deepcopy(post)
            for post in payload.get("x_posts", [])
            if isinstance(post, dict) and cached_post_is_reusable(post)
        ]
        if not reusable_posts:
            continue
        matched_results.append(
            {
                "path": str(path),
                "score": score,
                "modified_at": item["modified_at"],
                "posts": reusable_posts,
            }
        )

    if not matched_results:
        summary["notes"].append("recent x-index results were found, but none matched the current topic/clues strongly enough")
        return summary

    matched_results.sort(key=lambda item: (item["score"], item["modified_at"]), reverse=True)
    seen_post_urls: set[str] = set()
    for match in matched_results:
        summary["result_paths"].append(match["path"])
        for post in match["posts"]:
            canonical = canonical_status_url(clean_text(post.get("post_url")))
            if not canonical or canonical in seen_post_urls:
                continue
            seen_post_urls.add(canonical)
            summary["candidates"].append(
                {
                    "post_url": canonical,
                    "discovery_reason": f"reused_recent_result:{Path(match['path']).name}",
                    "cached_x_post": deepcopy(post),
                    "reuse_source_path": match["path"],
                    "reuse_match_score": match["score"],
                }
            )
            if len(summary["candidates"]) >= request.get("reuse_max_seed_posts", 6):
                break
        if len(summary["candidates"]) >= request.get("reuse_max_seed_posts", 6):
            break

    summary["matched_results"] = len(matched_results)
    summary["reused_posts"] = len(summary["candidates"])
    if summary["reused_posts"]:
        summary["notes"].append(f"reused {summary['reused_posts']} cached post(s) from prior x-index output")
    return summary


def within_same_author_time_window(candidate_posted_at: str, root_posted_at: str, request: dict[str, Any]) -> bool:
    root_time = parse_datetime(root_posted_at)
    if not root_time:
        return True
    candidate_time = parse_datetime(candidate_posted_at)
    if not candidate_time:
        return False
    window = timedelta(hours=max(1, int(request.get("same_author_scan_window_hours", 48))))
    return abs(candidate_time - root_time) <= window


def discover_same_author_candidates(
    root_post: dict[str, Any],
    request: dict[str, Any],
    visited: set[str],
) -> list[dict[str, Any]]:
    handle = clean_text(root_post.get("author_handle")).lstrip("@")
    if not handle:
        return []

    discovered: list[dict[str, Any]] = []
    limit = max(1, int(request.get("same_author_scan_limit", 12)))
    for query_spec in build_same_author_scan_queries(root_post, request):
        query = query_spec.get("query", "")
        reason = query_spec.get("reason", "")
        try:
            for url in maybe_fetch_search_results(query):
                canonical = canonical_status_url(url)
                match = STATUS_URL_RE.search(canonical)
                if not canonical or not match or match.group(1) != handle:
                    continue
                if canonical == clean_text(root_post.get("post_url")) or canonical in visited:
                    continue
                if any(item.get("post_url") == canonical for item in discovered):
                    continue
                discovered.append(
                    {
                        "post_url": canonical,
                        "discovery_reason": reason,
                        "search_query": query,
                    }
                )
                if len(discovered) >= limit:
                    return discovered
        except OSError as exc:
            discovered.append(
                {
                    "post_url": "",
                    "discovery_reason": reason,
                    "search_query": query,
                    "blocked_reason": f"same_author_scan_failed: {exc}",
                }
            )
    return discovered


def extract_post_text(html: str, visible_text: str, accessibility_text: str, ocr_fallback: str) -> tuple[str, str, float]:
    accessibility_quote_match = ROOT_AREA_QUOTE_RE.search(accessibility_text or "")
    accessibility_quote = clean_text(accessibility_quote_match.group("quote")) if accessibility_quote_match else ""
    if accessibility_quote.startswith("@") and not looks_blocked(accessibility_quote, html):
        return accessibility_quote, "accessibility_root", 0.93

    meta = extract_meta_contents(html)
    for key in ("og:description", "twitter:description", "description"):
        value = clean_text(meta.get(key))
        if value and not looks_blocked(value, ""):
            return value, "dom", 0.95

    match = TWEET_TEXT_RE.search(html)
    if match:
        value = strip_tags(match.group("content"))
        if value:
            return value, "dom", 0.9

    visible = clean_text(visible_text)
    if visible and not looks_blocked(visible, html):
        return visible, "accessibility", 0.7

    accessibility = clean_text(accessibility_text)
    if accessibility and not looks_blocked(accessibility, html):
        return accessibility, "accessibility", 0.6

    if ocr_fallback:
        return clean_text(ocr_fallback), "ocr_fallback", 0.45

    return "", "unavailable", 0.0


def extract_posted_at(html: str, fallback: str = "") -> str:
    meta = extract_meta_contents(html)
    for key in ("article:published_time", "og:article:published_time", "parsely-pub-date"):
        if meta.get(key):
            parsed = parse_datetime(meta[key])
            return isoformat_or_blank(parsed)
    match = TIME_RE.search(html)
    if match:
        parsed = parse_datetime(match.group("value"))
        return isoformat_or_blank(parsed)
    return fallback


def extract_author_handle(url: str, html: str) -> str:
    match = STATUS_URL_RE.search(url)
    if match:
        return match.group(1)
    meta = extract_meta_contents(html)
    title = clean_text(meta.get("og:title"))
    match = re.match(r"@?([A-Za-z0-9_]+)\s+on\s+X", title, re.IGNORECASE)
    return match.group(1) if match else ""


def extract_display_name(html: str, fallback: str) -> str:
    meta = extract_meta_contents(html)
    title = clean_text(meta.get("og:title"))
    if " on X" in title:
        return title.split(" on X", 1)[0].lstrip("@").strip()
    return fallback


def extract_media_urls(html: str) -> list[str]:
    urls: list[str] = []
    for url in MEDIA_URL_RE.findall(html):
        normalized = clean_text(url)
        if normalized and normalized not in urls:
            urls.append(normalized)
    meta = extract_meta_contents(html)
    og_image = clean_text(meta.get("og:image"))
    if og_image and og_image not in urls:
        urls.append(og_image)
    return urls


def maybe_download_image(url: str, output_path: Path) -> str:
    if not url:
        return ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Codex-XIndex/1.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return str(output_path)
    except OSError:
        return ""


def ocr_available() -> bool:
    return which("tesseract") is not None


def maybe_run_tesseract(image_path: str) -> str:
    if not image_path or not ocr_available():
        return ""
    try:
        process = subprocess.run(
            ["tesseract", image_path, "stdout"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
        )
        return clean_text(process.stdout)
    except OSError:
        return ""


def normalize_thread_post(post: dict[str, Any], collected_at: datetime) -> dict[str, Any]:
    raw = clean_text(post.get("post_text_raw") or post.get("text"))
    source = clean_text(post.get("post_text_source")) or ("dom" if raw else "unavailable")
    posted_at = parse_datetime(post.get("posted_at"))
    return {
        "post_url": canonical_status_url(clean_text(post.get("post_url"))),
        "posted_at": isoformat_or_blank(posted_at),
        "post_text_raw": raw,
        "post_text_source": source,
        "post_text_confidence": float(post.get("post_text_confidence", 0.7 if raw else 0.0)),
        "collected_at": isoformat_or_blank(collected_at),
    }


def normalize_engagement(payload: dict[str, Any]) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for key in ("views", "likes", "reposts", "replies"):
        value = payload.get(key)
        if isinstance(value, bool):
            result[key] = None
        elif isinstance(value, (int, float)):
            result[key] = int(value)
        elif clean_text(value):
            digits = re.sub(r"[^\d]", "", str(value))
            result[key] = int(digits) if digits else None
        else:
            result[key] = None
    return result


def canonical_media_source_url(url: str) -> str:
    source_url = clean_text(url)
    if not source_url:
        return ""
    parsed = urllib.parse.urlparse(source_url)
    host = (parsed.netloc or "").lower()
    path = clean_text(parsed.path)
    if host == "pbs.twimg.com" and path.startswith("/media/"):
        return f"https://{host}{path}"
    return source_url


def merge_media_source_items(source_items: list[dict[str, Any]], discovered_urls: list[str]) -> list[dict[str, Any]]:
    merged_by_key: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []

    def merged_text(current: Any, incoming: Any) -> str:
        current_text = clean_text(current)
        incoming_text = clean_text(incoming)
        if len(incoming_text) > len(current_text):
            return incoming_text
        return current_text

    def absorb(item: dict[str, Any]) -> None:
        source_url = clean_text(item.get("source_url"))
        local_path = clean_text(item.get("local_artifact_path"))
        key = canonical_media_source_url(source_url) or local_path
        if not key:
            return
        if key not in merged_by_key:
            merged_by_key[key] = {}
            ordered_keys.append(key)
        target = merged_by_key[key]
        if source_url and len(source_url) >= len(clean_text(target.get("source_url"))):
            target["source_url"] = source_url
        if local_path:
            target["local_artifact_path"] = local_path
        for field in ("media_type", "ocr_source", "image_relevance_to_post", "alt_text", "capture_method"):
            incoming_value = clean_text(item.get(field))
            if incoming_value and not clean_text(target.get(field)):
                target[field] = incoming_value
        for field in ("ocr_text_raw", "ocr_summary"):
            merged_value = merged_text(target.get(field), item.get(field))
            if merged_value:
                target[field] = merged_value
        for field in ("ocr_confidence", "display_width", "display_height", "natural_width", "natural_height", "x", "y"):
            incoming_value = item.get(field)
            if incoming_value not in ("", None):
                try:
                    if float(incoming_value) >= float(target.get(field, 0) or 0):
                        target[field] = incoming_value
                except (TypeError, ValueError):
                    if field not in target:
                        target[field] = incoming_value

    for item in source_items:
        if isinstance(item, dict):
            absorb(item)
    for url in discovered_urls:
        absorb({"source_url": url})
    return [merged_by_key[key] for key in ordered_keys]


def normalize_media_items(
    html: str,
    source_items: list[dict[str, Any]],
    output_dir: Path,
    post_slug: str,
    post_text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    media_items: list[dict[str, Any]] = []
    artifact_manifest: list[dict[str, Any]] = []
    discovered_urls = extract_media_urls(html)
    merged_sources = merge_media_source_items(source_items, discovered_urls)

    for index, item in enumerate(merged_sources, start=1):
        source_url = clean_text(item.get("source_url"))
        local_path = clean_text(item.get("local_artifact_path"))
        if not local_path and source_url:
            suffix = Path(urllib.parse.urlparse(source_url).path).suffix or ".bin"
            local_path = maybe_download_image(source_url, output_dir / f"{post_slug}-media-{index}{suffix}")

        ocr_text_raw = clean_text(item.get("ocr_text_raw"))
        ocr_source = clean_text(item.get("ocr_source"))
        if not ocr_text_raw and local_path:
            ocr_text_raw = maybe_run_tesseract(local_path)
            if ocr_text_raw and not ocr_source:
                ocr_source = "image"
        elif ocr_text_raw and not ocr_source:
            ocr_source = "image" if source_url else ""

        alt_text = meaningful_image_hint(item.get("alt_text"))
        ocr_summary = clean_text(item.get("ocr_summary")) or summarize_text(ocr_text_raw, limit=180) or summarize_text(alt_text, limit=180)
        confidence = float(item.get("ocr_confidence", 0.0)) if clean_text(item.get("ocr_confidence")) else (0.7 if ocr_text_raw else 0.0)
        relevance = clean_text(item.get("image_relevance_to_post")) or image_relevance(post_text, " ".join(part for part in (ocr_text_raw, ocr_summary, alt_text) if part))
        media_item = {
            "media_type": clean_text(item.get("media_type")) or "image",
            "source_url": source_url,
            "local_artifact_path": local_path,
            "ocr_text_raw": ocr_text_raw,
            "ocr_summary": ocr_summary,
            "ocr_source": ocr_source or ("image" if ocr_text_raw else ""),
            "ocr_confidence": round(confidence, 2),
            "image_relevance_to_post": relevance,
            "alt_text": alt_text,
            "capture_method": clean_text(item.get("capture_method")),
            "ocr_status": "done" if ocr_text_raw else "unavailable",
        }
        media_items.append(media_item)
        if local_path:
            artifact_manifest.append(
                {
                    "role": "post_media",
                    "path": local_path,
                    "source_url": source_url,
                    "media_type": media_item["media_type"],
                }
            )
    return media_items, artifact_manifest


def score_post(post: dict[str, Any], request: dict[str, Any]) -> int:
    score = 0
    posted_at = parse_datetime(post.get("posted_at")) or parse_datetime(post.get("collected_at")) or request["analysis_time"]
    age_minutes = max(0.0, (request["analysis_time"] - posted_at).total_seconds() / 60.0)
    if age_minutes <= 60:
        score += 30
    elif age_minutes <= 360:
        score += 20
    elif age_minutes <= 1440:
        score += 10

    views = post.get("engagement", {}).get("views")
    if views is not None:
        if views > 1_000_000:
            score += 25
        elif views > 250_000:
            score += 15
        elif views > 50_000:
            score += 8

    likes = post.get("engagement", {}).get("likes") or 0
    reposts = post.get("engagement", {}).get("reposts") or 0
    replies = post.get("engagement", {}).get("replies") or 0
    engagement_score = likes + 2 * reposts + replies
    if engagement_score > 20_000:
        score += 20
    elif engagement_score > 5_000:
        score += 12
    elif engagement_score > 1_000:
        score += 6

    if post.get("author_handle") in request.get("account_allowlist", []):
        score += 20
    haystack = " ".join(
        [
            post.get("post_text_raw", ""),
            post.get("post_summary", ""),
            post.get("media_summary", ""),
            post.get("combined_summary", ""),
            post.get("discovery_reason", ""),
        ]
    ).lower()
    phrase_hits = sum(1 for clue in request.get("phrase_clues", []) if clean_text(clue).lower() in haystack)
    entity_hits = sum(1 for clue in request.get("entity_clues", []) if clean_text(clue).lower() in haystack)
    score += min(24, phrase_hits * 12)
    score += min(18, entity_hits * 6)
    return score


def fetch_thread_posts(
    root_post: dict[str, Any],
    links_text: str,
    request: dict[str, Any],
    output_dir: Path,
    visited: set[str],
    session_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not request.get("include_threads"):
        return []
    same_author_links: list[str] = []
    handle = clean_text(root_post.get("author_handle")).lstrip("@")
    root_url = canonical_status_url(clean_text(root_post.get("post_url")))
    root_posted_at = clean_text(root_post.get("posted_at"))
    max_thread_posts = max(1, int(request.get("max_thread_posts", 10)))
    collected_at = isoformat_or_blank(request["analysis_time"])
    thread_posts: list[dict[str, Any]] = []
    seen_thread_urls: set[str] = set()

    def append_thread_post(url: str, artifact: FetchArtifact, fallback_posted_at: str = "") -> None:
        canonical = canonical_status_url(url)
        candidate_handle = extract_author_handle(canonical, artifact.html)
        if handle and candidate_handle and candidate_handle != handle:
            return
        posted_at = extract_posted_at(artifact.html, fallback_posted_at)
        if not within_same_author_time_window(posted_at, root_posted_at, request):
            return
        post_text_raw, source, confidence = extract_post_text(artifact.html, artifact.visible_text, artifact.accessibility_text, "")
        if canonical in seen_thread_urls:
            return
        seen_thread_urls.add(canonical)
        thread_posts.append(
            {
                "post_url": canonical,
                "posted_at": posted_at,
                "post_text_raw": post_text_raw,
                "post_text_source": source,
                "post_text_confidence": confidence,
                "collected_at": collected_at,
            }
        )

    scan_candidates = discover_same_author_candidates(root_post, request, visited)
    for index, candidate in enumerate(scan_candidates, start=1):
        url = canonical_status_url(candidate.get("post_url", ""))
        if not url or len(thread_posts) >= max_thread_posts:
            continue
        visited.add(url)
        artifact = fetch_page(
            url,
            output_dir / f"{slugify(handle or 'thread', 'thread')}-scan-thread-{index}.png",
            session_context,
        )
        append_thread_post(url, artifact, clean_text(candidate.get("posted_at")))

    if not thread_posts:
        for url in LINK_RE.findall(links_text or ""):
            canonical = canonical_status_url(url)
            match = STATUS_URL_RE.search(canonical)
            if not match or match.group(1) != handle:
                continue
            if canonical == root_url or canonical in visited or canonical in same_author_links:
                continue
            same_author_links.append(canonical)

        for index, url in enumerate(same_author_links[:max_thread_posts], start=1):
            if len(thread_posts) >= max_thread_posts:
                break
            visited.add(url)
            artifact = fetch_page(url, output_dir / f"{slugify(handle or 'thread', 'thread')}-thread-{index}.png", session_context)
            append_thread_post(url, artifact)

    thread_posts.sort(
        key=lambda item: (
            parse_datetime(item.get("posted_at")) or request["analysis_time"],
            item.get("post_url", ""),
        )
    )
    return thread_posts[:max_thread_posts]


def build_x_post_record(
    candidate: dict[str, Any],
    request: dict[str, Any],
    ordinal: int,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collected_at = request["analysis_time"]
    post_url = canonical_status_url(clean_text(candidate.get("post_url") or candidate.get("url")))
    post_slug = slugify(f"x-{ordinal}-{post_url}", f"x-post-{ordinal}")
    output_dir = request["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    cached_post = candidate.get("cached_x_post") if isinstance(candidate.get("cached_x_post"), dict) else None

    if cached_post:
        artifact_manifest = deepcopy(cached_post.get("artifact_manifest", [])) if isinstance(cached_post.get("artifact_manifest"), list) else []
        return {
            "post_url": canonical_status_url(clean_text(cached_post.get("post_url")) or post_url),
            "author_handle": clean_text(cached_post.get("author_handle")),
            "author_display_name": clean_text(cached_post.get("author_display_name")),
            "posted_at": isoformat_or_blank(parse_datetime(cached_post.get("posted_at"))),
            "collected_at": isoformat_or_blank(collected_at),
            "post_text_raw": clean_text(cached_post.get("post_text_raw")),
            "post_text_source": clean_text(cached_post.get("post_text_source")) or "cached_x_index_result",
            "post_text_extracted_at": isoformat_or_blank(collected_at),
            "post_text_confidence": round(float(cached_post.get("post_text_confidence", 0.75)), 2),
            "thread_posts": [
                normalize_thread_post(item, collected_at)
                for item in cached_post.get("thread_posts", [])
                if isinstance(item, dict)
            ][: request.get("max_thread_posts", 10)],
            "thread_incomplete": bool(cached_post.get("thread_incomplete")),
            "engagement": normalize_engagement(cached_post.get("engagement", {})),
            "root_post_screenshot_path": clean_text(cached_post.get("root_post_screenshot_path")),
            "media_items": deepcopy(cached_post.get("media_items", [])) if isinstance(cached_post.get("media_items"), list) else [],
            "post_summary": clean_text(cached_post.get("post_summary")),
            "media_summary": clean_text(cached_post.get("media_summary")),
            "combined_summary": clean_text(cached_post.get("combined_summary")),
            "conflict_note": clean_text(cached_post.get("conflict_note")),
            "discovery_reason": clean_text(candidate.get("discovery_reason")) or clean_text(cached_post.get("discovery_reason")) or "reused_x_index_result",
            "access_mode": clean_text(cached_post.get("access_mode")) or "public",
            "crawl_notes": unique_notes(
                [
                    *(cached_post.get("crawl_notes", []) if isinstance(cached_post.get("crawl_notes"), list) else []),
                    f"reused cached x-index output from {clean_text(candidate.get('reuse_source_path'))}",
                ]
            ),
            "session_source": clean_text(cached_post.get("session_source")),
            "session_status": clean_text(cached_post.get("session_status")) or "cached_reuse",
            "session_health": clean_text(cached_post.get("session_health")) or "effective",
            "session_notes": unique_notes(
                [
                    *(cached_post.get("session_notes", []) if isinstance(cached_post.get("session_notes"), list) else []),
                    f"reused from {clean_text(candidate.get('reuse_source_path'))}",
                ]
            ),
            "artifact_manifest": artifact_manifest,
        }

    if clean_text(candidate.get("html")) or clean_text(candidate.get("visible_text")):
        artifact = FetchArtifact(
            url=post_url,
            final_url=post_url,
            html=str(candidate.get("html", "")),
            visible_text=str(candidate.get("visible_text", "")),
            accessibility_text=str(candidate.get("accessibility_text", "")),
            links_text=str(candidate.get("links_text", "")),
            screenshot_path=clean_text(candidate.get("root_post_screenshot_path")),
            error="",
            media_items=deepcopy(candidate.get("media_items", [])) if isinstance(candidate.get("media_items"), list) else [],
            session_used=bool(candidate.get("used_browser_session")),
            session_source=clean_text(candidate.get("session_source")),
            session_status=clean_text(candidate.get("session_status")),
            session_notes=unique_notes(candidate.get("session_notes", []) if isinstance(candidate.get("session_notes"), list) else [clean_text(candidate.get("session_note"))]),
        )
    else:
        artifact = fetch_page(post_url, output_dir / f"{post_slug}-root.png", session_context)

    author_handle = clean_text(candidate.get("author_handle")) or extract_author_handle(post_url, artifact.html)
    posted_at = isoformat_or_blank(parse_datetime(candidate.get("posted_at")) or parse_datetime(extract_posted_at(artifact.html, "")))
    post_text_raw, post_text_source, post_text_confidence = extract_post_text(
        artifact.html,
        clean_text(candidate.get("visible_text")) or artifact.visible_text,
        clean_text(candidate.get("accessibility_text")) or artifact.accessibility_text,
        clean_text(candidate.get("ocr_root_text")) or request.get("ocr_root_text", ""),
    )

    thread_posts = [
        normalize_thread_post(item, collected_at)
        for item in candidate.get("thread_posts", [])
        if isinstance(item, dict)
    ]
    if not thread_posts:
        visited = {post_url}
        thread_posts = fetch_thread_posts(
            {"author_handle": author_handle, "post_url": post_url, "posted_at": posted_at},
            artifact.links_text,
            request,
            output_dir,
            visited,
            session_context,
        )

    media_items, media_artifacts = normalize_media_items(
        artifact.html,
        [
            *(item for item in artifact.media_items if isinstance(item, dict)),
            *(item for item in candidate.get("media_items", []) if isinstance(item, dict)),
        ],
        output_dir,
        post_slug,
        post_text_raw,
    )
    artifact_manifest = list(media_artifacts)
    if artifact.screenshot_path:
        artifact_manifest.insert(
            0,
            {
                "role": "root_post_screenshot",
                "path": artifact.screenshot_path,
                "source_url": post_url,
                "media_type": "screenshot",
            },
        )

    post_summary = summarize_text(" ".join([post_text_raw] + [item.get("post_text_raw", "") for item in thread_posts]), limit=320)
    media_summary = summarize_text(" ".join(item.get("ocr_summary", "") for item in media_items if item.get("ocr_summary")), limit=220)
    conflict_note = detect_conflict(post_text_raw, " ".join(item.get("ocr_text_raw", "") or item.get("ocr_summary", "") for item in media_items))
    combined_summary_parts = []
    if post_summary:
        combined_summary_parts.append(f"Post: {post_summary}")
    if media_summary:
        combined_summary_parts.append(f"Images: {media_summary}")
    if conflict_note:
        combined_summary_parts.append(f"Conflict note: {conflict_note}")

    blocked = looks_blocked(artifact.visible_text, artifact.html) and not post_text_raw
    session_used = bool(candidate.get("used_browser_session")) or artifact.session_used
    access_mode = "blocked" if blocked else ("browser_session" if session_used else "public")
    session_requested = session_used or bool(session_context and session_context.get("requested")) or bool(candidate.get("session_source"))
    session_status = clean_text(candidate.get("session_status")) or artifact.session_status
    session_health = ""
    if session_requested:
        if access_mode == "browser_session" and any([post_text_raw, thread_posts, media_items, artifact.screenshot_path]):
            session_health = "effective"
        elif session_status in {"failed", "fallback_public", "unavailable"} or blocked:
            session_health = "degraded"
        else:
            session_health = "attached"
    crawl_notes = [
        item
        for item in [
            clean_text(candidate.get("crawl_notes")),
            clean_text(artifact.error),
            clean_text(candidate.get("blocked_reason")),
            *artifact.session_notes,
        ]
        if item
    ]
    if blocked and not crawl_notes:
        crawl_notes.append("page appeared blocked or degraded during browser extraction")

    return {
        "post_url": post_url,
        "author_handle": author_handle,
        "author_display_name": clean_text(candidate.get("author_display_name")) or extract_display_name(artifact.html, author_handle),
        "posted_at": posted_at,
        "collected_at": isoformat_or_blank(collected_at),
        "post_text_raw": post_text_raw,
        "post_text_source": post_text_source,
        "post_text_extracted_at": isoformat_or_blank(collected_at),
        "post_text_confidence": round(post_text_confidence, 2),
        "thread_posts": thread_posts[: request.get("max_thread_posts", 10)],
        "thread_incomplete": len(thread_posts) >= request.get("max_thread_posts", 10),
        "engagement": normalize_engagement(candidate.get("engagement", {})),
        "root_post_screenshot_path": artifact.screenshot_path,
        "media_items": media_items,
        "post_summary": post_summary,
        "media_summary": media_summary,
        "combined_summary": " ".join(combined_summary_parts).strip(),
        "conflict_note": conflict_note,
        "discovery_reason": clean_text(candidate.get("discovery_reason")) or "manual_url",
        "access_mode": access_mode,
        "crawl_notes": crawl_notes,
        "session_source": clean_text(candidate.get("session_source")) or artifact.session_source,
        "session_status": session_status,
        "session_health": session_health,
        "session_notes": unique_notes(
            [
                *(candidate.get("session_notes", []) if isinstance(candidate.get("session_notes"), list) else []),
                *artifact.session_notes,
            ]
        ),
        "artifact_manifest": artifact_manifest,
    }


def collect_candidates(request: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for post in request.get("seed_posts", []):
        candidate = deepcopy(post)
        candidate["post_url"] = canonical_status_url(clean_text(candidate.get("post_url") or candidate.get("url")))
        candidates.append(candidate)

    for url in request.get("manual_urls", []):
        canonical = canonical_status_url(url)
        if canonical and not any(item.get("post_url") == canonical for item in candidates):
            candidates.append({"post_url": canonical, "discovery_reason": "manual_url"})

    reuse_summary = discover_reusable_candidates(request)
    for candidate in reuse_summary.get("candidates", []):
        canonical = canonical_status_url(candidate.get("post_url", ""))
        if canonical and not any(item.get("post_url") == canonical for item in candidates):
            candidates.append({**candidate, "post_url": canonical})

    if len(candidates) < request.get("max_candidates", 50):
        for item in discover_search_candidates(request, request.get("_session_context")):
            canonical = canonical_status_url(item.get("post_url", ""))
            if not canonical:
                candidates.append(item)
                continue
            if any(existing.get("post_url") == canonical for existing in candidates):
                continue
            candidates.append({**item, "post_url": canonical})
            if len(candidates) >= request.get("max_candidates", 50):
                break
    request["_reuse_summary"] = reuse_summary
    return candidates[: request.get("max_candidates", 50)]


def build_claim_candidates(x_posts: list[dict[str, Any]]) -> list[str]:
    claims: list[str] = []
    for post in x_posts:
        for value in (post.get("post_summary", ""), post.get("media_summary", "")):
            cleaned = clean_text(value)
            if cleaned and cleaned not in claims:
                claims.append(cleaned)
    return claims[:10]


def build_best_images(x_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] = []
    for post in x_posts:
        for item in post.get("media_items", []):
            if not item.get("local_artifact_path") and not item.get("source_url"):
                continue
            best.append(
                {
                    "post_url": post.get("post_url", ""),
                    "image_path": item.get("local_artifact_path", ""),
                    "source_url": item.get("source_url", ""),
                    "summary": item.get("ocr_summary", ""),
                    "relevance": item.get("image_relevance_to_post", ""),
                }
            )
    best.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item.get("relevance", ""), 3))
    return best[:8]


def build_retrieval_request(request: dict[str, Any], x_posts: list[dict[str, Any]]) -> dict[str, Any]:
    claims = deepcopy(request.get("claims", []))
    claim_ids = [clean_text(item.get("claim_id")) for item in claims if clean_text(item.get("claim_id"))]
    candidates = []
    for index, post in enumerate(x_posts, start=1):
        status_match = STATUS_URL_RE.search(post.get("post_url", ""))
        status_id = status_match.group(2) if status_match else str(index)
        source_name = f"X @{post.get('author_handle')}" if post.get("author_handle") else f"X post {index}"
        candidates.append(
            {
                "source_id": f"x-{status_id}",
                "source_name": source_name,
                "source_type": "social",
                "published_at": post.get("posted_at") or post.get("collected_at"),
                "observed_at": post.get("collected_at"),
                "url": post.get("post_url", ""),
                "claim_ids": claim_ids,
                "text_excerpt": short_excerpt(post.get("combined_summary") or post.get("post_text_raw"), limit=240),
                "channel": "shadow",
                "access_mode": post.get("access_mode", "public"),
                "artifact_manifest": deepcopy(post.get("artifact_manifest", [])),
                "x_post_record": deepcopy(post),
                "post_text_raw": post.get("post_text_raw", ""),
                "post_text_source": post.get("post_text_source", ""),
                "post_text_confidence": post.get("post_text_confidence", 0.0),
                "root_post_screenshot_path": post.get("root_post_screenshot_path", ""),
                "thread_posts": deepcopy(post.get("thread_posts", [])),
                "media_items": deepcopy(post.get("media_items", [])),
                "post_summary": post.get("post_summary", ""),
                "media_summary": post.get("media_summary", ""),
                "combined_summary": post.get("combined_summary", ""),
                "discovery_reason": post.get("discovery_reason", ""),
                "crawl_notes": deepcopy(post.get("crawl_notes", [])),
                "session_source": post.get("session_source", ""),
                "session_status": post.get("session_status", ""),
                "session_health": post.get("session_health", ""),
                "session_notes": deepcopy(post.get("session_notes", [])),
            }
        )

    return {
        "topic": request.get("topic", "x-index-topic"),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "questions": [f"What do current X posts say about {request.get('topic', 'this topic')}?"],
        "use_case": "x-post-index",
        "source_preferences": ["social", "major_news", "official"],
        "mode": "crisis" if request.get("market_relevance") else "generic",
        "windows": ["10m", "1h", "6h", "24h"],
        "claims": claims,
        "candidates": candidates,
        "market_relevance": request.get("market_relevance", []),
        "expected_source_families": ["social"],
    }


def build_markdown_report(result: dict[str, Any]) -> str:
    request = result.get("request", {})
    x_posts = result.get("x_posts", [])
    session_bootstrap = result.get("session_bootstrap", {})
    reuse_summary = result.get("reuse_summary", {})
    window_capture_hints = result.get("window_capture_hints", {})
    lines = [
        f"# X Index Report: {request.get('topic', 'x-index-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
    ]
    if session_bootstrap:
        lines.extend(
            [
                "",
                "## Session Bootstrap",
                f"- Strategy: {session_bootstrap.get('strategy', '') or 'disabled'}",
                f"- Status: {session_bootstrap.get('status', '') or 'disabled'}",
            ]
        )
        if session_bootstrap.get("source"):
            lines.append(f"- Source: {session_bootstrap.get('source', '')}")
        if session_bootstrap.get("cdp_endpoint"):
            lines.append(f"- Endpoint: {session_bootstrap.get('cdp_endpoint', '')}")
        if session_bootstrap.get("cookie_file"):
            lines.append(f"- Cookie file: {session_bootstrap.get('cookie_file', '')}")
        for note in session_bootstrap.get("notes", []):
            lines.append(f"- Note: {note}")
    if reuse_summary:
        lines.extend(
            [
                "",
                "## Reuse Summary",
                f"- Enabled: {bool(reuse_summary.get('enabled'))}",
                f"- Matched results: {reuse_summary.get('matched_results', 0)}",
                f"- Reused posts: {reuse_summary.get('reused_posts', 0)}",
            ]
        )
        for path in reuse_summary.get("result_paths", []):
            lines.append(f"- Reused result: {path}")
        for note in reuse_summary.get("notes", []):
            lines.append(f"- Note: {note}")
    if window_capture_hints:
        lines.extend(["", "## Window-First Capture Hints"])
        for note in window_capture_hints.get("notes", []):
            lines.append(f"- Note: {note}")
        for url in window_capture_hints.get("manual_urls", []):
            lines.append(f"- Direct URL: {url}")
        for item in window_capture_hints.get("search_urls", []):
            lines.append(f"- Search URL: {item.get('url', '')} | Query: {item.get('query', '')}")
    lines.extend(
        [
        "",
        "## X Posts",
        ]
    )
    if not x_posts:
        lines.append("- None")
    for post in x_posts:
        lines.extend(
            [
                f"- @{post.get('author_handle', 'unknown')} | {post.get('post_url', '')}",
                f"  Posted: {post.get('posted_at', '') or 'unknown'} | Access: {post.get('access_mode', '')}",
                f"  Text source: {post.get('post_text_source', '')} | Confidence: {post.get('post_text_confidence', 0)}",
                f"  Main post text: {post.get('post_text_raw', '') or 'unavailable'}",
                f"  Media summary: {post.get('media_summary', '') or 'none'}",
                f"  Screenshot: {post.get('root_post_screenshot_path', '') or 'none'}",
            ]
        )
        if post.get("session_source") or post.get("session_status"):
            lines.append(
                f"  Session: {post.get('session_source', '') or 'none'} | {post.get('session_status', '') or 'unknown'}"
            )
        if post.get("session_health"):
            lines.append(f"  Session health: {post.get('session_health', '')}")
        if post.get("conflict_note"):
            lines.append(f"  Conflict note: {post.get('conflict_note', '')}")
    if result.get("retrieval_result", {}).get("report_markdown"):
        lines.extend(["", "## News Index Bridge", "", result["retrieval_result"]["report_markdown"]])
    return "\n".join(lines).strip() + "\n"


def persist_x_index_outputs(result: dict[str, Any]) -> dict[str, str]:
    output_dir = Path(result.get("request", {}).get("output_dir", "")).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / DEFAULT_X_RESULT_FILENAME
    report_path = output_dir / DEFAULT_X_REPORT_FILENAME
    write_json(result_path, result)
    report_path.write_text(result.get("report_markdown", ""), encoding="utf-8")
    return {"result_json": str(result_path), "report_markdown": str(report_path)}


def run_x_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_request(raw_payload)
    session_context = prepare_session_context(request)
    request["_session_context"] = session_context
    collected_candidates = collect_candidates(request)
    reuse_summary = deepcopy(request.pop("_reuse_summary", {}))
    request.pop("_session_context", None)
    x_posts = []
    blocked_candidates = []
    for index, candidate in enumerate(collected_candidates, start=1):
        if not clean_text(candidate.get("post_url")):
            blocked_candidates.append(candidate)
            continue
        post = build_x_post_record(candidate, request, index, session_context)
        post["social_rank"] = score_post(post, request)
        x_posts.append(post)

    x_posts.sort(key=lambda item: item.get("social_rank", 0), reverse=True)
    kept_posts = x_posts[: request.get("max_kept_posts", 10)]
    retrieval_request = build_retrieval_request(request, kept_posts)
    retrieval_result = run_news_index(retrieval_request)
    evidence_pack = {
        "x_posts": kept_posts,
        "artifact_manifest": [artifact for post in kept_posts for artifact in post.get("artifact_manifest", [])],
        "claim_candidates": build_claim_candidates(kept_posts),
        "best_images": build_best_images(kept_posts),
    }
    result = {
        "request": {
            **request,
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "output_dir": str(request["output_dir"]),
        },
        "session_bootstrap": {
            "strategy": session_context.get("strategy", ""),
            "status": session_context.get("status", ""),
            "source": session_context.get("source", ""),
            "cookie_file": session_context.get("cookie_file", ""),
            "cdp_endpoint": session_context.get("cdp_endpoint", ""),
            "required": bool(session_context.get("required")),
            "notes": deepcopy(session_context.get("notes", [])),
        },
        "x_posts": kept_posts,
        "discovery_summary": {
            "attempted_candidates": len(collected_candidates),
            "kept_posts": len(kept_posts),
            "search_queries": build_search_queries(request),
            "blocked_candidates": blocked_candidates,
        },
        "reuse_summary": {
            key: deepcopy(value)
            for key, value in reuse_summary.items()
            if key != "candidates"
        },
        "window_capture_hints": build_window_capture_hints(request),
        "evidence_pack": evidence_pack,
        "retrieval_request": retrieval_request,
        "retrieval_result": retrieval_result,
    }
    if session_context.get("requested"):
        health_values = [clean_text(item.get("session_health")) for item in kept_posts if clean_text(item.get("session_health"))]
        result["session_bootstrap"]["health"] = (
            "effective"
            if "effective" in health_values
            else ("degraded" if "degraded" in health_values else ("attached" if health_values else "unverified"))
        )
    result["report_markdown"] = build_markdown_report(result)
    result["workflow_artifacts"] = persist_x_index_outputs(result)
    return result


__all__ = [
    "build_markdown_report",
    "build_window_capture_hints",
    "build_search_queries",
    "build_chain_commands",
    "load_json",
    "probe_cdp_endpoint",
    "prepare_session_context",
    "run_x_index",
    "write_json",
]
