#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import urllib.parse
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from last30days_bridge_runtime import discover_input_batches, load_last30days_payload
from news_index_runtime import (
    isoformat_or_blank,
    load_json,
    parse_datetime,
    run_news_index,
    safe_dict,
    safe_list,
    short_excerpt,
    write_json,
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


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
    media_items: list[dict[str, Any]]
    session_used: bool = False
    session_source: str = ""
    session_status: str = ""
    session_notes: list[str] = field(default_factory=list)


def extract_meta_content(html: str, *names: str) -> str:
    for name in names:
        pattern = re.compile(
            rf"<meta[^>]+(?:property|name)\s*=\s*[\"']{re.escape(name)}[\"'][^>]+content\s*=\s*[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        )
        match = pattern.search(html)
        if match:
            return clean_text(match.group(1))
    return ""


def status_id_from_url(url: str) -> str:
    return clean_text(url).rstrip("/").rsplit("/", 1)[-1]


def author_handle_from_url(url: str) -> str:
    match = re.search(r"x\.com/([^/?#]+)/status/", clean_text(url), re.IGNORECASE)
    return clean_text(match.group(1) if match else "")


def parse_html_posted_at(html: str) -> str:
    patterns = [
        r'property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "", re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def host_for(url: str) -> str:
    try:
        return urllib.parse.urlparse(clean_text(url)).netloc.lower()
    except ValueError:
        return ""


def last30days_source(raw_request: dict[str, Any]) -> dict[str, Any]:
    for key in ("last30days_result", "last30days_payload"):
        candidate = safe_dict(raw_request.get(key))
        if candidate:
            return candidate
    path_text = clean_text(raw_request.get("last30days_result_path") or raw_request.get("last30days_output_path"))
    if path_text:
        try:
            return load_last30days_payload(path_text)
        except Exception:
            return {}
    return {}


def derive_last30days_x_inputs(raw_request: dict[str, Any]) -> dict[str, Any]:
    payload = last30days_source(raw_request)
    if not payload:
        return {}
    seed_posts: list[dict[str, Any]] = []
    manual_urls: list[str] = []
    phrase_clues: list[str] = []
    entity_clues: list[str] = []
    account_allowlist: list[str] = []

    for batch_hint, items in discover_input_batches(payload):
        hint = clean_text(batch_hint).lower()
        for item in items:
            if not isinstance(item, dict):
                continue
            url = clean_text(item.get("url") or item.get("post_url") or item.get("source_url"))
            platform = clean_text(item.get("platform") or item.get("network") or item.get("source_platform") or hint).lower()
            if "x" not in platform and "twitter" not in platform and "x.com" not in host_for(url) and "twitter.com" not in host_for(url):
                continue
            author_handle = clean_text(item.get("author_handle") or item.get("author") or item.get("username")) or author_handle_from_url(url)
            if author_handle and author_handle not in account_allowlist:
                account_allowlist.append(author_handle)
            summary = clean_text(item.get("summary") or item.get("post_summary") or item.get("why_relevant") or item.get("text_excerpt"))
            if summary and summary not in phrase_clues:
                phrase_clues.append(summary)
            for token in re.findall(r"\b\d{6}\.(?:SS|SZ|HK|US)\b", " ".join([summary, clean_text(item.get("post_text_raw")), clean_text(item.get("text"))])):
                if token not in entity_clues:
                    entity_clues.append(token)
            seed_post = {
                "post_url": url,
                "posted_at": clean_text(item.get("published_at") or item.get("posted_at") or item.get("created_at")),
                "post_text_raw": clean_text(item.get("post_text_raw") or item.get("text") or item.get("content")),
                "post_summary": clean_text(item.get("post_summary") or item.get("summary")),
                "media_summary": clean_text(item.get("media_summary") or item.get("image_summary")),
                "root_post_screenshot_path": clean_text(item.get("root_post_screenshot_path") or item.get("screenshot_path")),
                "artifact_manifest": safe_list(item.get("artifact_manifest")),
                "media_items": safe_list(item.get("media_items")),
                "author_handle": author_handle,
            }
            if seed_post["post_url"] and seed_post["post_url"] not in manual_urls:
                manual_urls.append(seed_post["post_url"])
            if seed_post["post_text_raw"] or seed_post["post_summary"] or seed_post["root_post_screenshot_path"] or seed_post["media_items"]:
                seed_posts.append(seed_post)

    return {
        "seed_posts": seed_posts,
        "manual_urls": manual_urls,
        "phrase_clues": phrase_clues[:8],
        "entity_clues": entity_clues[:8],
        "account_allowlist": account_allowlist[:8],
        "topic": clean_text(raw_request.get("topic") or payload.get("topic") or payload.get("request", {}).get("topic")),
    }


def parse_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = dict(raw_request or {})
    request.update({k: v for k, v in derive_last30days_x_inputs(request).items() if v and not request.get(k)})
    analysis_time = parse_datetime(request.get("analysis_time"))
    request["analysis_time"] = isoformat_or_blank(analysis_time)
    request["topic"] = clean_text(request.get("topic")) or "x-index-topic"
    request["keywords"] = clean_string_list(request.get("keywords"))
    request["phrase_clues"] = clean_string_list(request.get("phrase_clues"))
    request["entity_clues"] = clean_string_list(request.get("entity_clues"))
    request["account_allowlist"] = clean_string_list(request.get("account_allowlist"))
    request["manual_urls"] = clean_string_list(request.get("manual_urls"))
    request["seed_posts"] = [safe_dict(item) for item in safe_list(request.get("seed_posts")) if isinstance(item, dict)]
    raw_ocr_root_text = str(request.get("ocr_root_text") or "")
    request["ocr_root_text"] = clean_text(raw_ocr_root_text)
    request["browser_session"] = safe_dict(request.get("browser_session"))
    request["max_search_queries"] = max(1, int(request.get("max_search_queries", 12) or 12))
    request["same_author_scan_limit"] = max(1, int(request.get("same_author_scan_limit", 6) or 6))
    request["same_author_scan_window_hours"] = max(1, int(request.get("same_author_scan_window_hours", 72) or 72))
    output_dir = request.get("output_dir")
    request["output_dir"] = Path(output_dir).expanduser().resolve() if clean_text(output_dir) else Path.cwd() / ".tmp" / "x-index"

    if raw_ocr_root_text:
        for line in raw_ocr_root_text.splitlines():
            line = clean_text(line)
            if not line:
                continue
            if "Exhibit" in line and line not in request["phrase_clues"]:
                request["phrase_clues"].append(line)
            if "Exhibit " in line:
                simplified = re.sub(r"^Exhibit\s+\d+:\s*", "", line, flags=re.IGNORECASE)
                simplified = clean_text(simplified)
                if simplified and simplified not in request["phrase_clues"]:
                    request["phrase_clues"].append(simplified)
            for entity in re.findall(r"\b\d{6}\.(?:SS|SZ|HK|US)\b", line):
                if entity not in request["entity_clues"]:
                    request["entity_clues"].append(entity)
    return request


def probe_cdp_endpoint(_endpoint: str) -> tuple[bool, str]:
    return False, "not_probed"


def prepare_session_context(request: dict[str, Any]) -> dict[str, Any]:
    browser_session = safe_dict(request.get("browser_session"))
    strategy = clean_text(browser_session.get("strategy")) or "disabled"
    output_dir = Path(request["output_dir"])
    notes: list[str] = []
    context = {
        "strategy": strategy,
        "active": False,
        "status": "disabled",
        "health": "inactive",
        "cookie_file": "",
        "notes": notes,
    }
    if strategy == "cookie_file":
        source_path = Path(clean_text(browser_session.get("cookie_file"))).expanduser()
        if source_path.exists():
            target_dir = output_dir / ".session"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / source_path.name
            shutil.copy2(source_path, target_path)
            context.update(
                {
                    "active": True,
                    "status": "ready",
                    "health": "effective",
                    "cookie_file": str(target_path),
                }
            )
            notes.append("copied cookie file into the output directory")
        else:
            context.update({"status": "unavailable", "health": "degraded"})
            notes.append("cookie file is missing; provide a valid exported cookie file")
    elif strategy == "remote_debugging":
        endpoint = clean_text(browser_session.get("cdp_endpoint")) or "http://127.0.0.1:9222"
        ok, detail = probe_cdp_endpoint(endpoint)
        if ok:
            context.update({"active": True, "status": "ready", "health": "effective"})
            notes.append(f"attached to {endpoint}")
        else:
            context.update({"status": "unavailable", "health": "degraded"})
            notes.append("Open a new Edge window with remote debugging enabled if the endpoint stays unavailable.")
            if detail:
                notes.append(detail)
    return context


def build_chain_commands(url: str, _screenshot_path: Path, session_context: dict[str, Any]) -> list[list[str]]:
    commands: list[list[str]] = []
    if clean_text(session_context.get("strategy")) == "cookie_file" and session_context.get("active") and clean_text(session_context.get("cookie_file")):
        commands.append(["cookie-import", clean_text(session_context.get("cookie_file"))])
    commands.append(["goto", clean_text(url)])
    return commands


def build_search_queries(request: dict[str, Any]) -> list[dict[str, str]]:
    queries: list[str] = []
    phrases = clean_string_list(request.get("phrase_clues"))
    entities = clean_string_list(request.get("entity_clues"))
    keywords = clean_string_list(request.get("keywords"))
    allowlist = clean_string_list(request.get("account_allowlist"))

    for handle in allowlist:
        for phrase in phrases:
            queries.append(f'site:x.com/{handle}/status "{phrase}"')
        for keyword in keywords:
            for entity in entities:
                queries.append(f'site:x.com/{handle}/status "{keyword}" "{entity}"')

    for phrase in phrases:
        queries.append(f'"{phrase}"')
        for entity in entities:
            queries.append(f'"{phrase}" "{entity}"')

    if keywords:
        for keyword in keywords:
            for entity in entities:
                queries.append(f'"{keyword}" "{entity}"')

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for query in queries:
        if query in seen:
            continue
        seen.add(query)
        deduped.append({"query": query})
        if len(deduped) >= request.get("max_search_queries", 12):
            break
    return deduped


def build_same_author_scan_queries(author: dict[str, Any], request: dict[str, Any]) -> list[dict[str, str]]:
    handle = clean_text(author.get("author_handle"))
    if not handle:
        return []
    queries: list[str] = []
    for phrase in clean_string_list(request.get("phrase_clues")):
        queries.append(f'site:x.com/{handle}/status "{phrase}"')
    for entity in clean_string_list(request.get("entity_clues")):
        queries.append(f'site:x.com/{handle}/status "{entity}"')
    if request.get("phrase_clues") and request.get("entity_clues"):
        queries.append(
            f'site:x.com/{handle}/status "{clean_string_list(request.get("phrase_clues"))[0]}" "{clean_string_list(request.get("entity_clues"))[0]}"'
        )
    return [{"query": item} for item in queries[: request.get("same_author_scan_limit", 6)]]


def build_window_capture_hints(request: dict[str, Any]) -> dict[str, Any]:
    queries = build_search_queries(request)
    search_urls = [
        {
            "query": item["query"],
            "url": f"https://x.com/search?q={urllib.parse.quote(item['query'])}&src=typed_query&f=live",
        }
        for item in queries
    ]
    for handle in clean_string_list(request.get("account_allowlist")):
        for phrase in clean_string_list(request.get("phrase_clues"))[:2]:
            query = f'from:{handle} "{phrase}"'
            search_urls.append(
                {
                    "query": query,
                    "url": f"https://x.com/search?q={urllib.parse.quote(query)}&src=typed_query&f=live",
                }
            )
    return {
        "preferred": bool(search_urls or clean_string_list(request.get("manual_urls"))),
        "manual_urls": clean_string_list(request.get("manual_urls")),
        "search_urls": search_urls,
        "notes": ["Open a new Edge window for the direct X search URLs if the embedded session stays blocked."],
    }


def extract_post_text(html: str, visible_text: str, accessibility_text: str, ocr_root_text: str) -> tuple[str, str, float]:
    accessibility = clean_text(accessibility_text)
    quoted_match = re.search(r"[“\"](.*?)[”\"]\s*/\s*X$", accessibility)
    if quoted_match:
        return clean_text(quoted_match.group(1)), "accessibility_root", 0.95
    if clean_text(visible_text):
        return clean_text(visible_text), "dom", 0.98
    description = extract_meta_content(html or "", "og:description", "twitter:description")
    if description:
        return description, "dom", 0.92
    if clean_text(ocr_root_text):
        return clean_text(ocr_root_text), "ocr_fallback", 0.72
    return "", "", 0.0


def fetch_page(url: str, _screenshot_path: Path, session_context: dict[str, Any] | None = None) -> FetchArtifact:
    return FetchArtifact(
        url=url,
        final_url=url,
        html="",
        visible_text="",
        accessibility_text="",
        links_text="",
        screenshot_path="",
        error="fetch_page is not implemented in offline mode",
        media_items=[],
        session_used=bool(safe_dict(session_context).get("active")),
        session_source=clean_text(safe_dict(session_context).get("strategy")),
        session_status=clean_text(safe_dict(session_context).get("status")),
        session_notes=clean_string_list(safe_dict(session_context).get("notes")),
    )


def maybe_fetch_search_results(_query: str) -> list[str]:
    return []


def discover_search_candidates(request: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for item in build_search_queries(request):
        urls.extend(maybe_fetch_search_results(item["query"]))
    return urls


def normalize_media_items(value: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "source_url": clean_text(item.get("source_url")),
                "local_artifact_path": clean_text(item.get("local_artifact_path")),
                "ocr_text_raw": clean_text(item.get("ocr_text_raw")),
                "ocr_summary": clean_text(item.get("ocr_summary")),
                "alt_text": clean_text(item.get("alt_text")),
                "capture_method": clean_text(item.get("capture_method")),
                "ocr_source": clean_text(item.get("ocr_source")),
            }
        )
    return items


def post_artifact_manifest(post_url: str, root_post_screenshot_path: str, media_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    if root_post_screenshot_path:
        manifest.append(
            {
                "role": "root_post_screenshot",
                "path": root_post_screenshot_path,
                "source_url": post_url,
                "media_type": "image",
            }
        )
    for item in media_items:
        manifest.append(
            {
                "role": "post_media",
                "path": item.get("local_artifact_path", ""),
                "source_url": item.get("source_url", ""),
                "media_type": "image",
            }
        )
    return manifest


def normalize_x_post(raw_post: dict[str, Any], request: dict[str, Any], session_context: dict[str, Any]) -> dict[str, Any]:
    html = raw_post.get("html", "")
    text, text_source, confidence = extract_post_text(
        html,
        clean_text(raw_post.get("visible_text")),
        clean_text(raw_post.get("accessibility_text")),
        clean_text(raw_post.get("ocr_root_text")),
    )
    media_items = normalize_media_items(raw_post.get("media_items"))
    thread_posts = [safe_dict(item) for item in safe_list(raw_post.get("thread_posts")) if isinstance(item, dict)]
    thread_texts = [clean_text(item.get("post_text_raw")) for item in thread_posts if clean_text(item.get("post_text_raw"))]
    media_summary = short_excerpt(
        " ".join(
            filter(
                None,
                [
                    clean_text(media_items[0].get("ocr_summary") if media_items else ""),
                    clean_text(media_items[0].get("ocr_text_raw") if media_items else ""),
                    clean_text(media_items[0].get("alt_text") if media_items else ""),
                ],
            )
        ),
        limit=180,
    )
    post_summary = short_excerpt(" ".join(filter(None, thread_texts + [text])), limit=240)
    combined_summary = post_summary
    if text_source == "ocr_fallback" and media_summary:
        combined_summary = f"Conflict note: OCR fallback is carrying the main post text. Media details: {media_summary}"
    elif media_summary:
        combined_summary = f"{post_summary} Images: {media_summary}"

    root_post_screenshot_path = clean_text(raw_post.get("root_post_screenshot_path") or raw_post.get("screenshot_path"))
    used_browser_session = bool(raw_post.get("used_browser_session")) or bool(raw_post.get("session_source"))
    session_source = clean_text(raw_post.get("session_source")) or clean_text(session_context.get("strategy"))
    session_status = clean_text(raw_post.get("session_status")) or (clean_text(session_context.get("status")) if used_browser_session else "")
    session_notes = clean_string_list(raw_post.get("session_notes")) + clean_string_list(session_context.get("notes"))
    crawl_notes = session_notes[:]
    if clean_text(raw_post.get("error")):
        crawl_notes.append(clean_text(raw_post.get("error")))
    access_mode = "browser_session" if used_browser_session else "public"
    if clean_text(raw_post.get("error")) and not text:
        access_mode = "blocked"
    session_health = "effective" if access_mode == "browser_session" and session_status == "ready" else ("degraded" if session_status in {"failed", "unavailable"} or clean_text(raw_post.get("error")) else "inactive")

    posted_at = clean_text(raw_post.get("posted_at")) or parse_html_posted_at(str(html)) or clean_text(request.get("analysis_time"))
    post_url = clean_text(raw_post.get("post_url") or raw_post.get("url"))
    return {
        "post_url": post_url,
        "author_handle": clean_text(raw_post.get("author_handle")) or author_handle_from_url(post_url),
        "posted_at": posted_at,
        "post_text_raw": text,
        "post_text_source": text_source,
        "post_text_confidence": confidence,
        "post_summary": post_summary,
        "media_summary": media_summary,
        "combined_summary": combined_summary,
        "root_post_screenshot_path": root_post_screenshot_path,
        "thread_posts": thread_posts,
        "media_items": media_items,
        "artifact_manifest": post_artifact_manifest(post_url, root_post_screenshot_path, media_items),
        "access_mode": access_mode,
        "session_source": session_source,
        "session_status": session_status,
        "session_health": session_health,
        "crawl_notes": crawl_notes,
        "discovery_reason": clean_text(raw_post.get("discovery_reason")),
        "engagement": safe_dict(raw_post.get("engagement")),
    }


def extract_same_author_links(links_text: str, author_handle: str) -> list[str]:
    urls = re.findall(r"https://x\.com/[^/\s]+/status/\d+", links_text or "", re.IGNORECASE)
    return [item for item in urls if author_handle_from_url(item).lower() == author_handle.lower()]


def fetch_thread_posts(
    base_post: dict[str, Any],
    links_text: str,
    request: dict[str, Any],
    output_dir: Path,
    seen_urls: set[str],
) -> list[dict[str, Any]]:
    author_handle = clean_text(base_post.get("author_handle"))
    base_posted_at = parse_datetime(base_post.get("posted_at"))
    discovered_urls: list[str] = []
    for item in build_same_author_scan_queries({"author_handle": author_handle}, request):
        discovered_urls.extend(maybe_fetch_search_results(item["query"]))
    if not discovered_urls:
        discovered_urls.extend(extract_same_author_links(links_text, author_handle))

    rows: list[dict[str, Any]] = []
    for url in discovered_urls:
        if url in seen_urls or author_handle_from_url(url).lower() != author_handle.lower():
            continue
        artifact = fetch_page(url, output_dir / f"{status_id_from_url(url)}.png", session_context=safe_dict(request.get("_session_context")))
        posted_at = parse_datetime(parse_html_posted_at(artifact.html) or base_post.get("posted_at"))
        if base_posted_at and posted_at:
            delta_hours = abs((posted_at - base_posted_at).total_seconds()) / 3600.0
            if delta_hours > float(request.get("same_author_scan_window_hours", 72)):
                continue
        text, source, confidence = extract_post_text(artifact.html, artifact.visible_text, artifact.accessibility_text, "")
        rows.append(
            {
                "post_url": url,
                "posted_at": isoformat_or_blank(posted_at),
                "post_text_raw": text,
                "post_text_source": source,
                "post_text_confidence": confidence,
            }
        )
        seen_urls.add(url)
        if len(rows) >= int(request.get("same_author_scan_limit", 6)):
            break
    rows.sort(key=lambda item: item.get("posted_at", ""))
    return rows


def build_retrieval_request(request: dict[str, Any], x_posts: list[dict[str, Any]]) -> dict[str, Any]:
    claims = [safe_dict(item) for item in safe_list(request.get("claims")) if isinstance(item, dict)]
    if not claims:
        claims = [{"claim_id": "claim-x-post", "claim_text": request.get("topic", "X post evidence")}]
    claim_ids = [clean_text(item.get("claim_id")) for item in claims if clean_text(item.get("claim_id"))]
    candidates = []
    for post in x_posts:
        candidates.append(
            {
                "source_id": status_id_from_url(post.get("post_url")),
                "source_name": clean_text(post.get("author_handle")) or "X",
                "source_type": "social",
                "published_at": clean_text(post.get("posted_at")) or clean_text(request.get("analysis_time")),
                "observed_at": clean_text(request.get("analysis_time")),
                "url": clean_text(post.get("post_url")),
                "text_excerpt": short_excerpt(post.get("post_text_raw") or post.get("post_summary"), limit=240),
                "claim_ids": claim_ids,
                "claim_states": {claim_id: "support" for claim_id in claim_ids},
                "artifact_manifest": post.get("artifact_manifest", []),
                "root_post_screenshot_path": clean_text(post.get("root_post_screenshot_path")),
                "post_text_raw": clean_text(post.get("post_text_raw")),
                "post_text_source": clean_text(post.get("post_text_source")),
                "post_text_confidence": post.get("post_text_confidence", 0.0),
                "post_summary": clean_text(post.get("post_summary")),
                "media_summary": clean_text(post.get("media_summary")),
                "combined_summary": clean_text(post.get("combined_summary")),
                "thread_posts": safe_list(post.get("thread_posts")),
                "media_items": safe_list(post.get("media_items")),
                "access_mode": "public" if clean_text(post.get("access_mode")) != "blocked" else "blocked",
            }
        )
    return {
        "topic": request.get("topic", "x-index-topic"),
        "analysis_time": request.get("analysis_time"),
        "claims": claims,
        "candidates": candidates,
        "mode": "generic",
        "windows": ["10m", "1h", "24h"],
    }


def build_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# X Index Report: {clean_text(result.get('topic')) or 'x-index-topic'}",
        "",
        f"- Captured posts: {len(safe_list(result.get('x_posts')))}",
    ]
    session = safe_dict(result.get("session_bootstrap"))
    if session:
        lines.extend(
            [
                "",
                "## Session Bootstrap",
                f"- Session: {clean_text(session.get('strategy'))} | {clean_text(session.get('status'))}",
                f"- Health: {clean_text(session.get('health'))}",
            ]
        )
    reuse_summary = safe_dict(result.get("reuse_summary"))
    if reuse_summary.get("reused_posts"):
        lines.extend(["", "## Reuse", f"- Reused posts: {int(reuse_summary.get('reused_posts', 0))}"])
    return "\n".join(lines).rstrip() + "\n"


def load_recent_cached_result(request: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(request["output_dir"]).resolve()
    parent = output_dir.parent
    candidates = sorted(parent.rglob("x-index-result.json"), reverse=True)
    for path in candidates:
        if output_dir in path.parents:
            continue
        try:
            payload = load_json(path)
        except Exception:
            continue
        cached_request = safe_dict(payload.get("request"))
        if clean_text(cached_request.get("topic")) != clean_text(request.get("topic")):
            continue
        if clean_string_list(cached_request.get("phrase_clues")) != clean_string_list(request.get("phrase_clues")):
            continue
        if clean_string_list(cached_request.get("entity_clues")) != clean_string_list(request.get("entity_clues")):
            continue
        if clean_string_list(cached_request.get("account_allowlist")) != clean_string_list(request.get("account_allowlist")):
            continue
        return payload
    return {}


def persist_x_index_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "x-index-result.json", result)
    (output_dir / "x-index-report.md").write_text(result.get("report_markdown", ""), encoding="utf-8")


def run_x_index(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = parse_request(raw_request)
    session_context = prepare_session_context(request)
    request["_session_context"] = session_context
    output_dir = Path(request["output_dir"])
    serializable_request = deepcopy(request)
    serializable_request["output_dir"] = str(output_dir)
    serializable_request.pop("_session_context", None)

    if not request["seed_posts"] and not request["manual_urls"]:
        cached = load_recent_cached_result(request)
        if cached:
            x_posts = [safe_dict(item) for item in safe_list(cached.get("x_posts")) if isinstance(item, dict)]
            for item in x_posts:
                item["discovery_reason"] = clean_text(item.get("discovery_reason")) or f"reused_recent_result:{clean_text(cached.get('topic'))}"
                notes = clean_string_list(item.get("crawl_notes"))
                notes.append("reused cached x-index output")
                item["crawl_notes"] = notes
            retrieval_request = build_retrieval_request(request, x_posts)
            retrieval_result = run_news_index(retrieval_request)
            result = {
                "topic": request["topic"],
                "analysis_time": request["analysis_time"],
                "request": serializable_request,
                "x_posts": x_posts,
                "retrieval_request": retrieval_request,
                "retrieval_result": retrieval_result,
                "reuse_summary": {"reused_posts": len(x_posts)},
                "session_bootstrap": session_context,
            }
            result["report_markdown"] = build_report_markdown(result)
            persist_x_index_outputs(output_dir, result)
            return result

    x_posts: list[dict[str, Any]] = []
    if request["seed_posts"]:
        for raw_post in request["seed_posts"]:
            x_posts.append(normalize_x_post(raw_post, request, session_context))
    else:
        for manual_url in request["manual_urls"]:
            artifact = fetch_page(
                manual_url,
                output_dir / f"{status_id_from_url(manual_url)}.png",
                session_context=session_context,
            )
            x_posts.append(
                normalize_x_post(
                    {
                        "post_url": manual_url,
                        "html": artifact.html,
                        "visible_text": artifact.visible_text,
                        "accessibility_text": artifact.accessibility_text,
                        "links_text": artifact.links_text,
                        "root_post_screenshot_path": artifact.screenshot_path,
                        "media_items": artifact.media_items,
                        "session_source": artifact.session_source,
                        "session_status": artifact.session_status,
                        "session_notes": artifact.session_notes,
                        "used_browser_session": artifact.session_used,
                        "error": artifact.error,
                    },
                    request,
                    session_context,
                )
            )

    retrieval_request = build_retrieval_request(request, x_posts)
    retrieval_result = run_news_index(retrieval_request)
    result = {
        "topic": request["topic"],
        "analysis_time": request["analysis_time"],
        "request": serializable_request,
        "x_posts": x_posts,
        "retrieval_request": retrieval_request,
        "retrieval_result": retrieval_result,
        "reuse_summary": {"reused_posts": 0},
        "session_bootstrap": session_context,
    }
    if session_context.get("health") == "degraded" and any(clean_text(item.get("session_status")) == "failed" for item in x_posts):
        result["session_bootstrap"]["health"] = "degraded"
    result["report_markdown"] = build_report_markdown(result)
    persist_x_index_outputs(output_dir, result)
    return result


__all__ = [
    "FetchArtifact",
    "build_chain_commands",
    "build_same_author_scan_queries",
    "build_search_queries",
    "build_window_capture_hints",
    "discover_search_candidates",
    "extract_post_text",
    "fetch_page",
    "fetch_thread_posts",
    "load_json",
    "maybe_fetch_search_results",
    "parse_request",
    "prepare_session_context",
    "probe_cdp_endpoint",
    "run_x_index",
    "write_json",
]
