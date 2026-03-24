#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from shutil import which
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
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
BLOCKED_MARKERS = [
    "something went wrong",
    "javascript 不可用",
    "javascript is disabled",
    "privacy related extensions may cause issues",
    "scriptloadfailure",
]


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


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_text(text: Any) -> str:
    return WHITESPACE_RE.sub(" ", unescape(str(text or "")).replace("\u200b", " ")).strip()


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
    haystack = f"{text}\n{html}".lower()
    return any(marker in haystack for marker in BLOCKED_MARKERS)


# Normalize the blocked markers in case this file previously picked up a garbled
# localized string during console edits on Windows.
BLOCKED_MARKERS = [
    "something went wrong",
    "javascript 不可用",
    "javascript is disabled",
    "privacy related extensions may cause issues",
    "scriptloadfailure",
]


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
        Path(raw_payload.get("output_dir", "")).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "x-index" / slugify(str(raw_payload.get("topic", "x-topic")), "x-topic") / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )
    return {
        "topic": clean_text(raw_payload.get("topic") or "x-index-topic"),
        "analysis_time": analysis_time,
        "keywords": [clean_text(item) for item in raw_payload.get("keywords", []) if clean_text(item)],
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
        "access_mode": clean_text(raw_payload.get("access_mode") or "public_first_browser_fallback"),
        "output_dir": output_dir,
        "ocr_root_text": clean_text(raw_payload.get("ocr_root_text")),
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


def fetch_page(url: str, screenshot_path: Path) -> FetchArtifact:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    parsed, error = run_chain(
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


def discover_search_candidates(request: dict[str, Any]) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    queries: list[tuple[str, str]] = []
    for keyword in request.get("keywords", []):
        queries.append((f'site:x.com/status "{keyword}"', f"keyword:{keyword}"))
        for handle in request.get("account_allowlist", []):
            queries.append((f'site:x.com/{handle}/status "{keyword}"', f"keyword:{keyword}|allowlist:@{handle}"))

    for query, reason in queries:
        try:
            for url in maybe_fetch_search_results(query):
                if len(discovered) >= request.get("max_candidates", 50):
                    break
                if any(item.get("post_url") == url for item in discovered):
                    continue
                discovered.append({"post_url": url, "discovery_reason": reason})
        except OSError as exc:
            discovered.append({"post_url": "", "discovery_reason": reason, "blocked_reason": f"search_fetch_failed: {exc}"})
        if len(discovered) >= request.get("max_candidates", 50):
            break
    return discovered


def extract_post_text(html: str, visible_text: str, accessibility_text: str, ocr_fallback: str) -> tuple[str, str, float]:
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

    merged_sources: list[dict[str, Any]] = [item for item in source_items if isinstance(item, dict)]
    for url in discovered_urls:
        if any(clean_text(item.get("source_url")) == url for item in merged_sources):
            continue
        merged_sources.append({"source_url": url})

    for index, item in enumerate(merged_sources, start=1):
        source_url = clean_text(item.get("source_url"))
        local_path = clean_text(item.get("local_artifact_path"))
        if not local_path and source_url:
            suffix = Path(urllib.parse.urlparse(source_url).path).suffix or ".bin"
            local_path = maybe_download_image(source_url, output_dir / f"{post_slug}-media-{index}{suffix}")

        ocr_text_raw = clean_text(item.get("ocr_text_raw"))
        ocr_source = clean_text(item.get("ocr_source")) or ("image" if source_url else "")
        if not ocr_text_raw and local_path:
            ocr_text_raw = maybe_run_tesseract(local_path)
            if ocr_text_raw:
                ocr_source = "image"

        ocr_summary = clean_text(item.get("ocr_summary")) or summarize_text(ocr_text_raw, limit=180)
        confidence = float(item.get("ocr_confidence", 0.0)) if clean_text(item.get("ocr_confidence")) else (0.7 if ocr_text_raw else 0.0)
        relevance = clean_text(item.get("image_relevance_to_post")) or image_relevance(post_text, ocr_text_raw or ocr_summary)
        media_item = {
            "media_type": clean_text(item.get("media_type")) or "image",
            "source_url": source_url,
            "local_artifact_path": local_path,
            "ocr_text_raw": ocr_text_raw,
            "ocr_summary": ocr_summary,
            "ocr_source": ocr_source or ("image" if ocr_text_raw else ""),
            "ocr_confidence": round(confidence, 2),
            "image_relevance_to_post": relevance,
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
    return score


def fetch_thread_posts(
    root_post: dict[str, Any],
    links_text: str,
    request: dict[str, Any],
    output_dir: Path,
    visited: set[str],
) -> list[dict[str, Any]]:
    if not request.get("include_threads"):
        return []
    same_author_links = []
    handle = root_post.get("author_handle", "")
    root_url = root_post.get("post_url", "")
    for url in LINK_RE.findall(links_text or ""):
        canonical = canonical_status_url(url)
        match = STATUS_URL_RE.search(canonical)
        if not match or match.group(1) != handle:
            continue
        if canonical == root_url or canonical in visited or canonical in same_author_links:
            continue
        same_author_links.append(canonical)

    thread_posts: list[dict[str, Any]] = []
    for index, url in enumerate(same_author_links[: request.get("max_thread_posts", 10)], start=1):
        visited.add(url)
        artifact = fetch_page(url, output_dir / f"{slugify(handle or 'thread', 'thread')}-thread-{index}.png")
        post_text_raw, source, confidence = extract_post_text(artifact.html, artifact.visible_text, artifact.accessibility_text, "")
        thread_posts.append(
            {
                "post_url": canonical_status_url(url),
                "posted_at": extract_posted_at(artifact.html, ""),
                "post_text_raw": post_text_raw,
                "post_text_source": source,
                "post_text_confidence": confidence,
                "collected_at": isoformat_or_blank(request["analysis_time"]),
            }
        )
    return thread_posts


def build_x_post_record(candidate: dict[str, Any], request: dict[str, Any], ordinal: int) -> dict[str, Any]:
    collected_at = request["analysis_time"]
    post_url = canonical_status_url(clean_text(candidate.get("post_url") or candidate.get("url")))
    post_slug = slugify(f"x-{ordinal}-{post_url}", f"x-post-{ordinal}")
    output_dir = request["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

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
        )
    else:
        artifact = fetch_page(post_url, output_dir / f"{post_slug}-root.png")

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
            {"author_handle": author_handle, "post_url": post_url},
            artifact.links_text,
            request,
            output_dir,
            visited,
        )

    media_items, media_artifacts = normalize_media_items(
        artifact.html,
        [item for item in candidate.get("media_items", []) if isinstance(item, dict)],
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
    access_mode = "blocked" if blocked else ("browser_session" if candidate.get("used_browser_session") else "public")
    crawl_notes = [
        item
        for item in [clean_text(candidate.get("crawl_notes")), clean_text(artifact.error), clean_text(candidate.get("blocked_reason"))]
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

    if len(candidates) < request.get("max_candidates", 50):
        for item in discover_search_candidates(request):
            canonical = canonical_status_url(item.get("post_url", ""))
            if not canonical:
                candidates.append(item)
                continue
            if any(existing.get("post_url") == canonical for existing in candidates):
                continue
            candidates.append({**item, "post_url": canonical})
            if len(candidates) >= request.get("max_candidates", 50):
                break
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
    lines = [
        f"# X Index Report: {request.get('topic', 'x-index-topic')}",
        "",
        f"Analysis time: {request.get('analysis_time', '')}",
        "",
        "## X Posts",
    ]
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
        if post.get("conflict_note"):
            lines.append(f"  Conflict note: {post.get('conflict_note', '')}")
    if result.get("retrieval_result", {}).get("report_markdown"):
        lines.extend(["", "## News Index Bridge", "", result["retrieval_result"]["report_markdown"]])
    return "\n".join(lines).strip() + "\n"


def run_x_index(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_request(raw_payload)
    collected_candidates = collect_candidates(request)
    x_posts = []
    blocked_candidates = []
    for index, candidate in enumerate(collected_candidates, start=1):
        if not clean_text(candidate.get("post_url")):
            blocked_candidates.append(candidate)
            continue
        post = build_x_post_record(candidate, request, index)
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
        "x_posts": kept_posts,
        "discovery_summary": {
            "attempted_candidates": len(collected_candidates),
            "kept_posts": len(kept_posts),
            "blocked_candidates": blocked_candidates,
        },
        "evidence_pack": evidence_pack,
        "retrieval_request": retrieval_request,
        "retrieval_result": retrieval_result,
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = [
    "build_markdown_report",
    "load_json",
    "run_x_index",
    "write_json",
]
