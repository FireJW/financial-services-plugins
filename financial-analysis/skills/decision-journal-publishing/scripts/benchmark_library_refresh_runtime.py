#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_index_runtime import normalize_platform, normalize_read_band, run_benchmark_index

AUTORESEARCH_SCRIPT_DIR = SCRIPT_DIR.parent.parent / "autoresearch-info-index" / "scripts"
if str(AUTORESEARCH_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUTORESEARCH_SCRIPT_DIR))

from news_index_runtime import load_json, parse_datetime, slugify, write_json


PARSER_VERSION = "2026-03-24.3"
TRACKING_QUERY_PREFIXES = ("utm_", "spm", "from", "source", "share_", "timestamp")
DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

TITLE_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S),
]

PUBLISHED_PATTERNS = [
    re.compile(r'article:published_time["\']?\s*content=["\']([^"\']+)["\']', re.I),
    re.compile(r'"publish(?:ed)?_?time"\s*:\s*"([^"]+)"', re.I),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I),
    re.compile(r'"published_at"\s*:\s*"([^"]+)"', re.I),
]

READ_SIGNAL_PATTERNS = [
    re.compile(r"(?:\u9605\u8bfb(?:\u91cf)?|read(?:s| count)?)[^0-9]{0,8}(\d+(?:\.\d+)?\s*(?:\u4e07|\u4ebf|w)\+?)", re.I),
    re.compile(r"(\d+(?:\.\d+)?\s*(?:\u4e07|\u4ebf|w)\+?)[^0-9]{0,8}(?:\u9605\u8bfb(?:\u91cf)?|read(?:s| count)?)", re.I),
]
HREF_PATTERN = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strip_tags(value: str) -> str:
    return SPACE_PATTERN.sub(" ", TAG_PATTERN.sub(" ", value or "")).strip()


def canonicalize_url(target: str, *, base_url: str = "") -> str:
    absolute = urllib.parse.urljoin(base_url, clean_text(target))
    parsed = urllib.parse.urlparse(absolute)
    if not parsed.scheme:
        return clean_text(target)
    filtered_query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    canonical = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urllib.parse.urlencode(filtered_query, doseq=True),
        fragment="",
    )
    rendered = canonical.geturl()
    if rendered.endswith("/") and canonical.path not in {"", "/"}:
        rendered = rendered[:-1]
    return rendered


def fetch_text(target: str) -> tuple[str, str]:
    target = clean_text(target)
    if not target:
        raise ValueError("fetch target is blank")
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme in {"http", "https", "file"}:
        request = urllib.request.Request(target, headers=DEFAULT_HTTP_HEADERS)
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return payload.decode(encoding, errors="replace"), target
    path = Path(target).expanduser().resolve()
    return path.read_text(encoding="utf-8"), path.as_uri()


def first_match(patterns: list[re.Pattern[str]], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return strip_tags(match.group(1))
    return ""


def extract_read_signal(html: str) -> str:
    for pattern in READ_SIGNAL_PATTERNS:
        match = pattern.search(html)
        if match:
            return clean_text(match.group(1))
    return ""


def detect_metadata(html: str) -> dict[str, Any]:
    raw_read_signal = extract_read_signal(html)
    read_meta = normalize_read_band(raw_read_signal)
    return {
        "detected_title": first_match(TITLE_PATTERNS, html),
        "detected_published_at": first_match(PUBLISHED_PATTERNS, html),
        "detected_read_signal": raw_read_signal,
        "detected_read_count_estimate": read_meta["read_count_estimate"],
        "detected_read_band": read_meta["read_band"],
    }


def default_machine_state() -> dict[str, Any]:
    return {
        "last_checked_at": "",
        "last_fetch_status": "never",
        "last_fetch_target": "",
        "last_observation_at": "",
        "current_observation_id": "",
        "current_read_signal": "",
        "current_read_count_estimate": None,
        "current_published_at": "",
        "current_title": "",
        "change_flags": [],
    }


def default_discovery_state(method: str = "manual") -> dict[str, Any]:
    return {
        "discovered_at": "",
        "source_id": "",
        "source_url": "",
        "discovery_method": method,
    }


def default_human_locks() -> dict[str, bool]:
    return {
        "title": True,
        "published_at": True,
        "read_signal": True,
        "notes": True,
    }


def normalize_case_record(case: dict[str, Any], *, default_status: str) -> dict[str, Any]:
    normalized = deepcopy(case)
    normalized["platform"] = normalize_platform(normalized.get("platform"))
    normalized["case_id"] = clean_text(normalized.get("case_id")) or slugify(
        f"{clean_text(normalized.get('account_name'))}-{clean_text(normalized.get('title'))}",
        "case",
    )
    normalized["canonical_url"] = canonicalize_url(
        clean_text(normalized.get("canonical_url") or normalized.get("url"))
    )
    normalized["curation_status"] = clean_text(normalized.get("curation_status") or default_status).lower()
    normalized["machine_state"] = {**default_machine_state(), **safe_dict(normalized.get("machine_state"))}
    normalized["discovery_state"] = {
        **default_discovery_state(
            clean_text(safe_dict(normalized.get("discovery_state")).get("discovery_method")) or "manual"
        ),
        **safe_dict(normalized.get("discovery_state")),
    }
    normalized["human_locks"] = {**default_human_locks(), **safe_dict(normalized.get("human_locks"))}
    return normalized


def load_case_collection(path: Path, *, default_name: str, default_status: str, include_statuses: list[str]) -> dict[str, Any]:
    if path.exists():
        payload = load_json(path)
    else:
        payload = {
            "library_name": default_name,
            "version": PARSER_VERSION,
            "updated_at": "",
            "last_machine_refresh_at": "",
            "default_request": {
                "minimum_read_band": "5w+",
                "strict_read_gate": False,
                "allow_below_threshold_commercial_exceptions": True,
                "platforms": ["wechat", "toutiao"],
                "include_curation_statuses": include_statuses,
            },
            "cases": [],
        }
    payload["cases"] = [normalize_case_record(safe_dict(item), default_status=default_status) for item in safe_list(payload.get("cases"))]
    return payload


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")


def load_seeds(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "library_name": "decision-journal-benchmark-refresh-seeds",
            "version": PARSER_VERSION,
            "default_request": {},
            "sources": [],
        }
    payload = load_json(path)
    payload["default_request"] = safe_dict(payload.get("default_request"))
    payload["sources"] = [safe_dict(item) for item in safe_list(payload.get("sources") or payload.get("discovery_sources"))]
    return payload


def case_fingerprint(case: dict[str, Any]) -> str:
    parts = [
        normalize_platform(case.get("platform")),
        clean_text(case.get("account_name")).lower(),
        clean_text(case.get("title")).lower(),
    ]
    return "|".join(parts)


def build_candidate_case_id(*, source_id: str, title: str, canonical_url: str) -> str:
    normalized_source_id = slugify(clean_text(source_id), "candidate")
    normalized_title = slugify(clean_text(title), "")
    base = "-".join(part for part in (normalized_source_id, normalized_title) if part).strip("-") or normalized_source_id
    digest_seed = clean_text(canonical_url) or f"{clean_text(source_id)}|{clean_text(title)}"
    digest = hashlib.sha1(digest_seed.encode("utf-8")).hexdigest()[:10]
    return f"{base[:64].rstrip('-')}-{digest}"


def candidate_case_id_needs_repair(case_id: str) -> bool:
    normalized = clean_text(case_id).lower()
    if not normalized:
        return True
    if normalized in {"candidate", "candidate-case", "case"}:
        return True
    if len(normalized) < 4:
        return True
    if re.fullmatch(r"[0-9-]+", normalized):
        return True
    return False


def repair_candidate_case_ids(cases: list[dict[str, Any]]) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    for case in cases:
        case_id = clean_text(case.get("case_id")).lower()
        if case_id:
            counts[case_id] = counts.get(case_id, 0) + 1

    seen: set[str] = set()
    repairs: list[dict[str, str]] = []
    for case in cases:
        current_case_id = clean_text(case.get("case_id"))
        discovery_state = safe_dict(case.get("discovery_state"))
        replacement = build_candidate_case_id(
            source_id=clean_text(discovery_state.get("source_id")) or clean_text(case.get("account_name")) or "candidate",
            title=clean_text(case.get("title")),
            canonical_url=clean_text(case.get("canonical_url") or case.get("url")),
        )
        should_repair = candidate_case_id_needs_repair(current_case_id) or counts.get(current_case_id.lower(), 0) > 1
        candidate_case_id = replacement if should_repair else current_case_id
        lowered = candidate_case_id.lower()
        if lowered in seen:
            suffix_seed = clean_text(case.get("canonical_url") or case.get("url")) or case_fingerprint(case)
            suffix = hashlib.sha1(suffix_seed.encode("utf-8")).hexdigest()[:6]
            candidate_case_id = f"{candidate_case_id}-{suffix}"
            lowered = candidate_case_id.lower()
        seen.add(lowered)
        if current_case_id != candidate_case_id:
            repairs.append(
                {
                    "from_case_id": current_case_id,
                    "to_case_id": candidate_case_id,
                    "canonical_url": clean_text(case.get("canonical_url") or case.get("url")),
                }
            )
            case["case_id"] = candidate_case_id
    return repairs


def repair_candidate_human_locks(cases: list[dict[str, Any]]) -> int:
    repairs = 0
    for case in cases:
        locks = {**default_human_locks(), **safe_dict(case.get("human_locks"))}
        if locks.get("read_signal", True):
            locks["read_signal"] = False
            case["human_locks"] = locks
            repairs += 1
    return repairs


def build_case_indexes(*collections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_case_id: dict[str, dict[str, Any]] = {}
    by_canonical_url: dict[str, dict[str, Any]] = {}
    by_fingerprint: dict[str, dict[str, Any]] = {}
    for collection in collections:
        for case in collection:
            case_id = clean_text(case.get("case_id"))
            canonical_url = clean_text(case.get("canonical_url"))
            fingerprint = case_fingerprint(case)
            if case_id:
                by_case_id[case_id] = case
            if canonical_url:
                by_canonical_url[canonical_url] = case
            if fingerprint:
                by_fingerprint[fingerprint] = case
    return {
        "by_case_id": by_case_id,
        "by_canonical_url": by_canonical_url,
        "by_fingerprint": by_fingerprint,
    }


def build_observation_id(*parts: str) -> str:
    joined = "|".join(clean_text(part) for part in parts if clean_text(part))
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]
    return f"obs-{digest}"


def build_observation(
    *,
    analysis_time: str,
    fetch_target: str,
    case_id: str = "",
    canonical_url: str = "",
    source_id: str = "",
    source_url: str = "",
    fetch_status: str,
    metadata: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    meta = metadata or {}
    return {
        "observation_id": build_observation_id(analysis_time, case_id or canonical_url or source_id, fetch_target),
        "observed_at": analysis_time,
        "case_id": case_id,
        "canonical_url": canonical_url,
        "source_id": source_id,
        "source_url": source_url,
        "fetch_target": fetch_target,
        "fetch_status": fetch_status,
        "detected_title": clean_text(meta.get("detected_title")),
        "detected_published_at": clean_text(meta.get("detected_published_at")),
        "detected_read_signal": clean_text(meta.get("detected_read_signal")),
        "detected_read_count_estimate": meta.get("detected_read_count_estimate"),
        "detected_read_band": clean_text(meta.get("detected_read_band")),
        "parser_version": PARSER_VERSION,
        "errors": [clean_text(item) for item in (errors or []) if clean_text(item)],
    }


def apply_observation_to_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    machine_state = {**default_machine_state(), **safe_dict(case.get("machine_state"))}
    locks = {**default_human_locks(), **safe_dict(case.get("human_locks"))}
    change_flags: list[str] = []
    for machine_key, observation_key in (
        ("current_title", "detected_title"),
        ("current_published_at", "detected_published_at"),
        ("current_read_signal", "detected_read_signal"),
        ("current_read_count_estimate", "detected_read_count_estimate"),
    ):
        new_value = observation.get(observation_key)
        if new_value in {"", None}:
            continue
        old_value = machine_state.get(machine_key)
        if old_value != new_value:
            change_flags.append(machine_key)
            machine_state[machine_key] = new_value

    if (
        clean_text(case.get("curation_status")) == "candidate"
        and clean_text(observation.get("fetch_status")) == "ok"
        and not locks.get("read_signal", True)
    ):
        detected_signal = clean_text(observation.get("detected_read_signal"))
        detected_count = observation.get("detected_read_count_estimate") if detected_signal else None
        if machine_state.get("current_read_signal") != detected_signal:
            change_flags.append("current_read_signal")
        if machine_state.get("current_read_count_estimate") != detected_count:
            change_flags.append("current_read_count_estimate")
        machine_state["current_read_signal"] = detected_signal
        machine_state["current_read_count_estimate"] = detected_count
        case["read_signal"] = detected_signal

    machine_state["last_checked_at"] = clean_text(observation.get("observed_at"))
    machine_state["last_fetch_status"] = clean_text(observation.get("fetch_status"))
    machine_state["last_fetch_target"] = clean_text(observation.get("fetch_target"))
    machine_state["last_observation_at"] = clean_text(observation.get("observed_at"))
    machine_state["current_observation_id"] = clean_text(observation.get("observation_id"))
    machine_state["change_flags"] = list(dict.fromkeys(change_flags))
    case["machine_state"] = machine_state
    return case


def should_include_candidate(candidate: dict[str, Any], source: dict[str, Any]) -> bool:
    url = clean_text(candidate.get("url"))
    title = clean_text(candidate.get("title"))
    include_url_patterns = safe_list(source.get("include_url_patterns"))
    exclude_url_patterns = safe_list(source.get("exclude_url_patterns"))
    include_title_keywords = [clean_text(item).lower() for item in safe_list(source.get("include_title_keywords")) if clean_text(item)]
    exclude_title_keywords = [clean_text(item).lower() for item in safe_list(source.get("exclude_title_keywords")) if clean_text(item)]

    if include_url_patterns and not any(re.search(pattern, url, re.I) for pattern in include_url_patterns):
        return False
    if exclude_url_patterns and any(re.search(pattern, url, re.I) for pattern in exclude_url_patterns):
        return False

    lowered_title = title.lower()
    if include_title_keywords and not any(keyword in lowered_title for keyword in include_title_keywords):
        return False
    if exclude_title_keywords and any(keyword in lowered_title for keyword in exclude_title_keywords):
        return False
    return True


def extract_links(html: str, base_url: str, source: dict[str, Any], seen_urls: set[str], limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for href, anchor_text in HREF_PATTERN.findall(html):
        absolute = canonicalize_url(href, base_url=base_url)
        title = strip_tags(anchor_text)
        if not title or not absolute or absolute in seen_urls:
            continue
        candidate = {"url": absolute, "title": title}
        if not should_include_candidate(candidate, source):
            continue
        seen_urls.add(absolute)
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def fetch_json_payload(target: str) -> tuple[dict[str, Any], str]:
    text, resolved_target = fetch_text(target)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("JSON seed payload must be an object")
    return payload, resolved_target


def build_sina_newmedia_feed_url(source: dict[str, Any], page: int) -> str:
    explicit_feed_url = clean_text(source.get("feed_url"))
    if explicit_feed_url:
        parsed = urllib.parse.urlparse(explicit_feed_url)
        if parsed.scheme in {"", "file"}:
            return explicit_feed_url
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        query.setdefault("source", "js")
        return parsed._replace(query=urllib.parse.urlencode(query, doseq=True)).geturl()
    muid = clean_text(source.get("muid"))
    if not muid:
        raise ValueError("sina_newmedia_json seed requires muid or feed_url")
    return f"https://k.sina.cn/aj/newmedia/list?source=js&muid={urllib.parse.quote(muid)}&page={page}"


def extract_sina_newmedia_candidates(
    source: dict[str, Any],
    seen_urls: set[str],
    limit: int,
) -> tuple[list[dict[str, Any]], str]:
    pages = max(1, int(source.get("seed_pages") or 1))
    candidates: list[dict[str, Any]] = []
    resolved_seed_url = build_sina_newmedia_feed_url(source, 1)
    for page in range(1, pages + 1):
        feed_url = build_sina_newmedia_feed_url(source, page)
        payload, resolved_seed_url = fetch_json_payload(feed_url)
        for item in safe_list(payload.get("data")):
            record = safe_dict(item)
            absolute = canonicalize_url(clean_text(record.get("link") or record.get("url")))
            title = clean_text(record.get("longTitle") or record.get("title"))
            if not title or not absolute or absolute in seen_urls:
                continue
            candidate = {"url": absolute, "title": title}
            if not should_include_candidate(candidate, source):
                continue
            seen_urls.add(absolute)
            candidates.append(candidate)
            if len(candidates) >= limit:
                return candidates, resolved_seed_url
    return candidates, resolved_seed_url


def is_within_recency_window(published_at: str, max_age_days: int, analysis_time: str) -> bool:
    if not max_age_days:
        return True
    published = parse_datetime(published_at, fallback=None)
    observed = parse_datetime(analysis_time, fallback=None)
    if published is None or observed is None:
        return True
    return (observed - published).days <= max_age_days


def build_candidate_case(
    *,
    source: dict[str, Any],
    link_candidate: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    defaults = safe_dict(source.get("candidate_defaults") or source.get("case_defaults"))
    title = clean_text(observation.get("detected_title")) or clean_text(link_candidate.get("title"))
    canonical_url = canonicalize_url(clean_text(link_candidate.get("url")))
    source_id = clean_text(source.get("source_id")) or clean_text(source.get("account_name")) or "candidate"
    case = normalize_case_record(
        {
            "case_id": build_candidate_case_id(
                source_id=source_id,
                title=title,
                canonical_url=canonical_url,
            ),
            "platform": normalize_platform(source.get("platform")),
            "account_name": clean_text(source.get("account_name")),
            "title": title,
            "url": canonical_url,
            "canonical_url": canonical_url,
            "fetch_url": canonical_url,
            "published_at": clean_text(observation.get("detected_published_at")),
            "read_signal": clean_text(observation.get("detected_read_signal")),
            "account_positioning": clean_text(defaults.get("account_positioning")),
            "topic_type": clean_text(defaults.get("topic_type")),
            "hook_type": clean_text(defaults.get("hook_type")),
            "affected_group": clean_text(defaults.get("affected_group")),
            "cta_type": clean_text(defaults.get("cta_type")),
            "paid_asset_linkage": clean_text(defaults.get("paid_asset_linkage")),
            "notes": clean_text(defaults.get("notes") or "Auto-discovered candidate. Review before benchmark qualification."),
            "curation_status": "candidate",
            "discovery_state": {
                "discovered_at": clean_text(observation.get("observed_at")),
                "source_id": clean_text(source.get("source_id")),
                "source_url": clean_text(source.get("seed_url") or source.get("fetch_url") or source.get("url")),
                "discovery_method": "auto",
            },
            "human_locks": {
                "title": True,
                "published_at": True,
                "read_signal": False,
                "notes": True,
            },
        },
        default_status="candidate",
    )
    return apply_observation_to_case(case, observation)


def pick_fetch_target(case: dict[str, Any], *, allow_reference_url_fallback: bool) -> str:
    explicit = clean_text(case.get("fetch_url"))
    if explicit:
        return explicit
    if allow_reference_url_fallback:
        return clean_text(case.get("canonical_url") or case.get("url"))
    return ""


def refresh_case(
    case: dict[str, Any],
    *,
    analysis_time: str,
    observations_path: Path,
    allow_reference_url_fallback: bool,
) -> dict[str, Any]:
    fetch_target = pick_fetch_target(case, allow_reference_url_fallback=allow_reference_url_fallback)
    if not fetch_target:
        observation = build_observation(
            analysis_time=analysis_time,
            fetch_target="",
            case_id=clean_text(case.get("case_id")),
            canonical_url=clean_text(case.get("canonical_url")),
            fetch_status="skipped",
            errors=["No fetch_url configured for this case."],
        )
        append_jsonl(observations_path, observation)
        apply_observation_to_case(case, observation)
        return observation

    try:
        html, resolved_target = fetch_text(fetch_target)
        metadata = detect_metadata(html)
        observation = build_observation(
            analysis_time=analysis_time,
            fetch_target=resolved_target,
            case_id=clean_text(case.get("case_id")),
            canonical_url=clean_text(case.get("canonical_url")),
            fetch_status="ok",
            metadata=metadata,
        )
    except Exception as exc:
        observation = build_observation(
            analysis_time=analysis_time,
            fetch_target=fetch_target,
            case_id=clean_text(case.get("case_id")),
            canonical_url=clean_text(case.get("canonical_url")),
            fetch_status="error",
            errors=[str(exc)],
        )
    append_jsonl(observations_path, observation)
    apply_observation_to_case(case, observation)
    return observation


def find_existing_case(indexes: dict[str, dict[str, Any]], *, canonical_url: str, fingerprint: str) -> dict[str, Any] | None:
    if canonical_url and canonical_url in indexes["by_canonical_url"]:
        return indexes["by_canonical_url"][canonical_url]
    if fingerprint and fingerprint in indexes["by_fingerprint"]:
        return indexes["by_fingerprint"][fingerprint]
    return None


def normalize_refresh_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    library_path = Path(clean_text(raw_payload.get("library_path"))).expanduser()
    if not clean_text(raw_payload.get("library_path")):
        raise ValueError("benchmark-refresh requires library_path")

    analysis_time = parse_datetime(raw_payload.get("analysis_time"), fallback=None)
    if analysis_time is None:
        raise ValueError("benchmark-refresh requires analysis_time")

    resolved_library_path = library_path.resolve()
    cases_dir = resolved_library_path.parent
    output_dir = (
        Path(clean_text(raw_payload.get("output_dir"))).expanduser()
        if clean_text(raw_payload.get("output_dir"))
        else Path.cwd() / ".tmp" / "benchmark-refresh" / analysis_time.strftime("%Y%m%dT%H%M%SZ")
    )

    candidate_library_path = (
        Path(clean_text(raw_payload.get("candidate_library_path"))).expanduser()
        if clean_text(raw_payload.get("candidate_library_path"))
        else cases_dir / "benchmark-case-candidates.json"
    )
    seeds_path = (
        Path(clean_text(raw_payload.get("seeds_path"))).expanduser()
        if clean_text(raw_payload.get("seeds_path"))
        else cases_dir / "benchmark-refresh-seeds.json"
    )
    observations_path = (
        Path(clean_text(raw_payload.get("observations_path"))).expanduser()
        if clean_text(raw_payload.get("observations_path"))
        else cases_dir / "benchmark-case-observations.jsonl"
    )

    return {
        "analysis_time": analysis_time,
        "library_path": resolved_library_path,
        "candidate_library_path": candidate_library_path.resolve() if candidate_library_path.exists() else candidate_library_path,
        "seeds_path": seeds_path.resolve() if seeds_path.exists() else seeds_path,
        "observations_path": observations_path.resolve() if observations_path.exists() else observations_path,
        "output_dir": output_dir,
        "refresh_existing_cases": bool(raw_payload.get("refresh_existing_cases", True)),
        "discover_new_cases": bool(raw_payload.get("discover_new_cases", True)),
        "auto_add_new_cases": bool(raw_payload.get("auto_add_new_cases", True)),
        "allow_reference_url_fallback": bool(raw_payload.get("allow_reference_url_fallback", False)),
        "run_benchmark_index_after_refresh": bool(raw_payload.get("run_benchmark_index_after_refresh", True)),
        "max_candidates_per_source": int(raw_payload.get("max_candidates_per_source", 10) or 10),
        "benchmark_index_request": safe_dict(raw_payload.get("benchmark_index_request")),
    }


def discover_candidates(
    *,
    seeds: list[dict[str, Any]],
    reviewed_cases: list[dict[str, Any]],
    candidate_cases: list[dict[str, Any]],
    analysis_time: str,
    observations_path: Path,
    max_candidates_per_source: int,
    auto_add_new_cases: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    discovered_candidates: list[dict[str, Any]] = []
    matched_existing: list[dict[str, Any]] = []
    source_runs: list[dict[str, Any]] = []
    indexes = build_case_indexes(reviewed_cases, candidate_cases)
    seen_urls = set(indexes["by_canonical_url"].keys())

    for source in seeds:
        if source.get("enabled", True) is False:
            continue
        source_id = clean_text(source.get("source_id")) or slugify(clean_text(source.get("account_name")), "seed")
        seed_url = clean_text(source.get("seed_url") or source.get("fetch_url") or source.get("url"))
        source_run = {
            "source_id": source_id,
            "seed_url": seed_url,
            "status": "ok",
            "links_considered": 0,
            "candidates_added": 0,
            "matched_existing": 0,
            "skipped_old": 0,
            "errors": [],
        }
        if not seed_url:
            source_run["status"] = "error"
            source_run["errors"].append("Missing seed_url.")
            source_runs.append(source_run)
            continue

        try:
            if clean_text(source.get("seed_mode")).lower() == "sina_newmedia_json":
                link_candidates, resolved_seed_url = extract_sina_newmedia_candidates(
                    source,
                    seen_urls,
                    int(source.get("max_candidates") or max_candidates_per_source),
                )
            else:
                seed_html, resolved_seed_url = fetch_text(seed_url)
                link_candidates = extract_links(
                    seed_html,
                    resolved_seed_url,
                    source,
                    seen_urls,
                    int(source.get("max_candidates") or max_candidates_per_source),
                )
        except Exception as exc:
            source_run["status"] = "error"
            source_run["errors"].append(str(exc))
            source_runs.append(source_run)
            continue

        source_run["links_considered"] = len(link_candidates)
        for link_candidate in link_candidates:
            canonical_url = canonicalize_url(clean_text(link_candidate.get("url")))
            try:
                article_html, resolved_article_url = fetch_text(canonical_url)
                metadata = detect_metadata(article_html)
                observation = build_observation(
                    analysis_time=analysis_time,
                    fetch_target=resolved_article_url,
                    canonical_url=canonical_url,
                    source_id=source_id,
                    source_url=resolved_seed_url,
                    fetch_status="ok",
                    metadata=metadata,
                )
            except Exception as exc:
                observation = build_observation(
                    analysis_time=analysis_time,
                    fetch_target=canonical_url,
                    canonical_url=canonical_url,
                    source_id=source_id,
                    source_url=resolved_seed_url,
                    fetch_status="error",
                    errors=[str(exc)],
                )
            append_jsonl(observations_path, observation)
            if clean_text(observation.get("fetch_status")) != "ok":
                if clean_text(observation.get("fetch_status")) == "error":
                    source_run["status"] = "partial"
                continue

            if not is_within_recency_window(
                clean_text(observation.get("detected_published_at")),
                int(source.get("max_age_days") or 0),
                analysis_time,
            ):
                source_run["skipped_old"] += 1
                continue

            fingerprint = case_fingerprint(
                {
                    "platform": normalize_platform(source.get("platform")),
                    "account_name": clean_text(source.get("account_name")),
                    "title": clean_text(observation.get("detected_title") or link_candidate.get("title")),
                }
            )
            existing = find_existing_case(indexes, canonical_url=canonical_url, fingerprint=fingerprint)
            if existing is not None:
                apply_observation_to_case(existing, observation)
                matched_existing.append(
                    {
                        "source_id": source_id,
                        "case_id": clean_text(existing.get("case_id")),
                        "canonical_url": canonical_url,
                        "fetch_status": clean_text(observation.get("fetch_status")),
                    }
                )
                source_run["matched_existing"] += 1
                continue

            candidate = build_candidate_case(source=source, link_candidate=link_candidate, observation=observation)
            discovered_candidates.append(candidate)
            if auto_add_new_cases:
                candidate_cases.append(candidate)
                indexes = build_case_indexes(reviewed_cases, candidate_cases)
            source_run["candidates_added"] += 1

        source_runs.append(source_run)

    return discovered_candidates, matched_existing, source_runs


def build_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("summary"))
    lines = [
        "# Benchmark Library Refresh",
        "",
        f"- Analysis time: {clean_text(result.get('analysis_time'))}",
        f"- Reviewed library path: {clean_text(safe_dict(result.get('libraries')).get('reviewed_library_path'))}",
        f"- Candidate inbox path: {clean_text(safe_dict(result.get('libraries')).get('candidate_library_path'))}",
        f"- Observations path: {clean_text(result.get('observations_path'))}",
        f"- Reviewed cases refreshed: {summary.get('reviewed_cases_refreshed', 0)}",
        f"- Candidate cases refreshed: {summary.get('candidate_cases_refreshed', 0)}",
        f"- Candidates discovered: {summary.get('candidates_discovered', 0)}",
        f"- Existing cases matched from seeds: {summary.get('matched_existing_cases', 0)}",
        f"- Source failures: {summary.get('source_failures', 0)}",
        "",
        "## Source Runs",
        "",
    ]
    source_runs = safe_list(result.get("source_runs"))
    if not source_runs:
        lines.append("- none")
    else:
        for item in source_runs:
            errors = "; ".join(safe_list(item.get("errors"))) or "n/a"
            lines.append(
                f"- {clean_text(item.get('source_id'))}: {clean_text(item.get('status'))}; "
                f"links {item.get('links_considered', 0)}; added {item.get('candidates_added', 0)}; "
                f"matched {item.get('matched_existing', 0)}; skipped_old {item.get('skipped_old', 0)}; errors {errors}"
            )
    lines.extend(["", "## Newly Discovered Candidates", ""])
    discovered = safe_list(result.get("discovered_candidates"))
    if not discovered:
        lines.append("- none")
    else:
        for item in discovered:
            lines.append(
                f"- {clean_text(item.get('account_name'))} | {clean_text(item.get('title'))} | "
                f"{clean_text(item.get('canonical_url') or item.get('url'))}"
            )
    benchmark_index_result = safe_dict(result.get("benchmark_index_result"))
    if benchmark_index_result:
        benchmark_summary = safe_dict(benchmark_index_result.get("summary"))
        lines.extend(
            [
                "",
                "## Reviewed Benchmark Snapshot",
                "",
                f"- Threshold-qualified reviewed cases: {benchmark_summary.get('threshold_qualified_cases', 0)}",
                f"- Exception-qualified reviewed cases: {benchmark_summary.get('exception_qualified_cases', 0)}",
                f"- Report: {clean_text(benchmark_index_result.get('report_path'))}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_benchmark_library_refresh(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_refresh_request(raw_payload)
    request["output_dir"].mkdir(parents=True, exist_ok=True)
    analysis_time_iso = request["analysis_time"].isoformat()

    reviewed_library = load_case_collection(
        request["library_path"],
        default_name="decision-journal-benchmark-cases",
        default_status="reviewed",
        include_statuses=["reviewed"],
    )
    candidate_library = load_case_collection(
        request["candidate_library_path"],
        default_name="decision-journal-benchmark-candidates",
        default_status="candidate",
        include_statuses=["candidate"],
    )
    seeds_payload = load_seeds(request["seeds_path"])
    seed_defaults = safe_dict(seeds_payload.get("default_request"))

    reviewed_cases = safe_list(reviewed_library.get("cases"))
    candidate_cases = safe_list(candidate_library.get("cases"))
    candidate_case_id_repairs = repair_candidate_case_ids(candidate_cases)
    candidate_human_lock_repairs = repair_candidate_human_locks(candidate_cases)
    reviewed_case_refreshes: list[dict[str, Any]] = []
    candidate_case_refreshes: list[dict[str, Any]] = []

    if request["refresh_existing_cases"]:
        for case in reviewed_cases:
            observation = refresh_case(
                case,
                analysis_time=analysis_time_iso,
                observations_path=request["observations_path"],
                allow_reference_url_fallback=request["allow_reference_url_fallback"],
            )
            reviewed_case_refreshes.append(
                {
                    "case_id": clean_text(case.get("case_id")),
                    "fetch_status": clean_text(observation.get("fetch_status")),
                    "errors": safe_list(observation.get("errors")),
                }
            )
        for case in candidate_cases:
            observation = refresh_case(
                case,
                analysis_time=analysis_time_iso,
                observations_path=request["observations_path"],
                allow_reference_url_fallback=request["allow_reference_url_fallback"],
            )
            candidate_case_refreshes.append(
                {
                    "case_id": clean_text(case.get("case_id")),
                    "fetch_status": clean_text(observation.get("fetch_status")),
                    "errors": safe_list(observation.get("errors")),
                }
            )

    discovered_candidates: list[dict[str, Any]] = []
    matched_existing: list[dict[str, Any]] = []
    source_runs: list[dict[str, Any]] = []
    if request["discover_new_cases"]:
        discovered_candidates, matched_existing, source_runs = discover_candidates(
            seeds=safe_list(seeds_payload.get("sources")),
            reviewed_cases=reviewed_cases,
            candidate_cases=candidate_cases,
            analysis_time=analysis_time_iso,
            observations_path=request["observations_path"],
            max_candidates_per_source=int(seed_defaults.get("max_candidates_per_source") or request["max_candidates_per_source"]),
            auto_add_new_cases=request["auto_add_new_cases"],
        )

    reviewed_library["cases"] = reviewed_cases
    reviewed_library["last_machine_refresh_at"] = analysis_time_iso
    reviewed_library["candidate_library_path"] = request["candidate_library_path"].name
    reviewed_library["observation_log_path"] = request["observations_path"].name
    reviewed_library["refresh_seed_path"] = request["seeds_path"].name
    reviewed_library["machine_refresh_summary"] = {
        "reviewed_cases_refreshed": len(reviewed_case_refreshes),
        "matched_existing_cases": len(matched_existing),
    }

    candidate_library["cases"] = candidate_cases
    candidate_library["last_machine_refresh_at"] = analysis_time_iso
    candidate_library["observation_log_path"] = request["observations_path"].name
    candidate_library["refresh_seed_path"] = request["seeds_path"].name
    candidate_library["machine_refresh_summary"] = {
        "candidate_cases_refreshed": len(candidate_case_refreshes),
        "candidates_discovered": len(discovered_candidates),
        "candidate_case_id_repairs": len(candidate_case_id_repairs),
        "candidate_human_lock_repairs": len(candidate_human_lock_repairs),
    }

    write_json(request["library_path"], reviewed_library)
    write_json(request["candidate_library_path"], candidate_library)

    benchmark_index_result: dict[str, Any] = {}
    if request["run_benchmark_index_after_refresh"]:
        benchmark_index_request = {
            **safe_dict(seed_defaults.get("benchmark_index_request")),
            **safe_dict(request.get("benchmark_index_request")),
            "analysis_time": analysis_time_iso,
            "library_path": str(request["library_path"]),
        }
        if "include_statuses" in benchmark_index_request and "include_curation_statuses" not in benchmark_index_request:
            benchmark_index_request["include_curation_statuses"] = benchmark_index_request.pop("include_statuses")
        benchmark_index_result = run_benchmark_index(benchmark_index_request)
        benchmark_result_path = request["output_dir"] / "benchmark-index-after-refresh.json"
        write_json(benchmark_result_path, benchmark_index_result)
        benchmark_index_result["result_path"] = str(benchmark_result_path)

    result = {
        "status": "ok",
        "workflow_kind": "benchmark_library_refresh",
        "analysis_time": analysis_time_iso,
        "libraries": {
            "reviewed_library_path": str(request["library_path"]),
            "candidate_library_path": str(request["candidate_library_path"]),
            "seeds_path": str(request["seeds_path"]),
        },
        "observations_path": str(request["observations_path"]),
        "reviewed_case_refreshes": reviewed_case_refreshes,
        "candidate_case_refreshes": candidate_case_refreshes,
        "candidate_case_id_repairs": candidate_case_id_repairs,
        "candidate_human_lock_repairs": candidate_human_lock_repairs,
        "discovered_candidates": discovered_candidates,
        "matched_existing_cases": matched_existing,
        "source_runs": source_runs,
        "summary": {
            "reviewed_cases_refreshed": len(reviewed_case_refreshes),
            "candidate_cases_refreshed": len(candidate_case_refreshes),
            "candidates_discovered": len(discovered_candidates),
            "matched_existing_cases": len(matched_existing),
            "source_failures": sum(1 for item in source_runs if clean_text(item.get("status")) == "error"),
            "candidate_case_id_repairs": len(candidate_case_id_repairs),
            "candidate_human_lock_repairs": len(candidate_human_lock_repairs),
        },
        "benchmark_index_result": benchmark_index_result,
    }
    result["report_markdown"] = build_report(result)
    report_path = request["output_dir"] / "benchmark-library-refresh-report.md"
    report_path.write_text(result["report_markdown"], encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


__all__ = ["load_json", "run_benchmark_library_refresh", "write_json"]
