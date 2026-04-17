#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment-dependent optional dependency
    yaml = None

from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, run_news_index, short_excerpt, write_json
from runtime_paths import runtime_subdir


SUPPORTED_CHANNELS = ("web", "github", "youtube", "rss", "x", "wechat", "reddit", "bilibili", "douyin", "xiaohongshu", "semantic")
CHANNEL_ALIASES = {"twitter": "x", "x_twitter": "x", "web_jina": "web"}
COLLECTION_KEYS = ("findings", "items", "results", "entries", "records", "data")
DEFAULT_CHANNELS = ["github", "youtube"]
QUERYLESS_REDDIT_SUBREDDIT_LIMITS = [
    ("r/stocks", 2),
    ("r/investing", 1),
    ("r/SecurityAnalysis", 2),
    ("r/ValueInvesting", 1),
    ("r/wallstreetbets", 1),
    ("r/MachineLearning", 2),
    ("r/hardware", 2),
    ("r/geopolitics", 1),
    ("r/CredibleDefense", 1),
]
QUERYLESS_REDDIT_SEARCH_QUERIES = [
    "AI chips semiconductors",
    "OpenAI Claude Anthropic",
    "robotaxi Tesla",
    "oil shipping Hormuz",
    "jet fuel shortage Europe",
    "Netflix NFLX earnings revenue",
    "tariffs trade war supply chain",
]
QUERYLESS_REDDIT_SEARCH_SUBREDDITS = [
    "r/MachineLearning",
    "r/hardware",
    "r/stocks",
    "r/SecurityAnalysis",
    "r/CredibleDefense",
    "r/wallstreetbets",
]
QUERYLESS_REDDIT_META_TITLE_KEYWORDS = {
    "rate my portfolio",
    "daily discussion",
    "discussion and advice thread",
    "questions and discussions thread",
    "who's hiring",
    "self-promotion thread",
    "self promotion thread",
    "reminder:",
    "letters & reports",
    "letters and reports",
    "quarterly thread",
    "monthly who's hiring",
    "active conflicts & news megathread",
}
QUERYLESS_REDDIT_META_TITLE_PREFIXES = ("[d] ", "[week ")
QUERYLESS_REDDIT_STALE_MAX_AGE_DAYS = 45
QUERYLESS_REDDIT_THEMATIC_KEYWORDS = {
    "earnings",
    "eps",
    "revenue",
    "guidance",
    "market share",
    "catalyst",
    "amd",
    "ryzen",
    "x3d",
    "semiconductor",
    "semiconductors",
    "chip",
    "chips",
    "hbm",
    "gpu",
    "nvidia",
    "foundry",
    "packaging",
    "robotaxi",
    "autonomous",
    "tesla",
    "openai",
    "claude",
    "anthropic",
    "gemini",
    "model",
    "models",
    "inference",
    "cost curve",
    "ai agent",
    "agents",
    "oil",
    "hormuz",
    "jet fuel",
    "blockade",
    "supply chain",
    "tariff",
    "tariffs",
    "export control",
    "defence",
    "defense",
    "ukraine",
}
QUERYLESS_X_SEARCH_QUERIES = [
    "NVIDIA AMD TSMC chips HBM semiconductors",
    "OpenAI Anthropic Claude Gemini AI agents",
    "robotaxi autonomous driving Tesla",
    "oil shipping Hormuz jet fuel sanctions",
    "Netflix NFLX earnings revenue EPS",
    "tariffs trade war supply chain macro",
]
QUERYLESS_X_PER_QUERY_TIMEOUT_SECONDS = 8
DEFAULT_TIMEOUT_PER_CHANNEL = 30
DEFAULT_DEDUPE_WINDOW_HOURS = 6
BRAND_BY_HOST_FRAGMENT = {
    "github.com": "GitHub",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "x.com": "X",
    "twitter.com": "X",
    "reddit.com": "Reddit",
    "bilibili.com": "Bilibili",
    "xiaohongshu.com": "Xiaohongshu",
    "weixin.qq.com": "WeChat",
    "reuters.com": "Reuters",
    "apnews.com": "AP",
    "axios.com": "Axios",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "nytimes.com": "New York Times",
}


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


def coerce_yaml_scalar(value: str) -> Any:
    text = clean_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def load_yaml_mapping(text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            loaded = yaml.safe_load(text) or {}
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            return loaded
    result: dict[str, Any] = {}
    current_list_key = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            if current_list_key and stripped.startswith("- "):
                existing = result.get(current_list_key)
                if isinstance(existing, list):
                    existing.append(coerce_yaml_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            current_list_key = ""
            continue
        key, value = stripped.split(":", 1)
        normalized_key = clean_text(key)
        normalized_value = value.strip()
        if not normalized_key:
            current_list_key = ""
            continue
        if not normalized_value:
            result[normalized_key] = []
            current_list_key = normalized_key
            continue
        result[normalized_key] = coerce_yaml_scalar(normalized_value)
        current_list_key = ""
    return result


def preferred_user_root() -> Path:
    return Path("D:/Users") / Path.home().name


def default_vendor_root() -> Path:
    return preferred_user_root() / ".codex" / "vendor"


def default_agent_reach_home() -> Path:
    return default_vendor_root() / "agent-reach-home"


def load_agent_reach_config(home_root: Path | None = None) -> dict[str, Any]:
    root = home_root or default_agent_reach_home()
    config_path = root / ".agent-reach" / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        return load_yaml_mapping(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_env_assignments(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = clean_text(key)
        if not normalized_key:
            continue
        values[normalized_key] = value.strip().strip('"').strip("'")
    return values


def first_credential_value(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean_text(mapping.get(key))
        if value:
            return value
    return ""


def resolve_twitter_credentials(config: dict[str, Any], pseudo_home: Path) -> dict[str, str]:
    auth_token = first_credential_value(config, "twitter_auth_token", "x_auth_token", "auth_token")
    ct0 = first_credential_value(config, "twitter_ct0", "x_ct0", "ct0")
    if auth_token and ct0:
        return {"auth_token": auth_token, "ct0": ct0, "source": "config"}
    bird_env_path = pseudo_home / ".config" / "bird" / "credentials.env"
    if bird_env_path.exists():
        try:
            bird_env_values = parse_env_assignments(bird_env_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            bird_env_values = {}
        auth_token = first_credential_value(bird_env_values, "AUTH_TOKEN", "TWITTER_AUTH_TOKEN")
        ct0 = first_credential_value(bird_env_values, "CT0", "TWITTER_CT0")
        if auth_token and ct0:
            return {"auth_token": auth_token, "ct0": ct0, "source": "bird_env"}
    auth_token = first_credential_value(os.environ, "AUTH_TOKEN", "TWITTER_AUTH_TOKEN")
    ct0 = first_credential_value(os.environ, "CT0", "TWITTER_CT0")
    if auth_token and ct0:
        return {"auth_token": auth_token, "ct0": ct0, "source": "process_env"}
    return {"auth_token": "", "ct0": "", "source": ""}


def has_twitter_credentials(config: dict[str, Any], pseudo_home: Path) -> bool:
    credentials = resolve_twitter_credentials(config, pseudo_home)
    return bool(credentials["auth_token"] and credentials["ct0"])


def default_live_channels(
    *,
    pseudo_home: Path,
    agent_reach_config: dict[str, Any],
    rss_feeds: list[str],
    has_channel_overrides: bool,
) -> list[str]:
    if has_channel_overrides:
        return list(DEFAULT_CHANNELS)
    channels = list(DEFAULT_CHANNELS)
    if rss_feeds:
        channels.append("rss")
    if has_twitter_credentials(agent_reach_config, pseudo_home):
        channels.append("x")
    return channels


def preferred_binary_path(name: str) -> str:
    candidates: dict[str, list[Path]] = {
        "yt-dlp": [default_vendor_root() / "yt-dlp" / "yt-dlp.exe", Path("yt-dlp")],
        "gh": [default_vendor_root() / "gh" / "bin" / "gh.exe", Path("gh")],
        "bird": [default_vendor_root() / "bird" / "bird.cmd", Path("bird")],
    }
    for candidate in candidates.get(name, [Path(name)]):
        if candidate.is_absolute() and candidate.exists():
            return str(candidate)
        resolved = shutil.which(str(candidate))
        if resolved:
            return resolved
    return name


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_channel_name(value: Any) -> str:
    normalized = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    normalized = CHANNEL_ALIASES.get(normalized, normalized)
    return normalized if normalized in SUPPORTED_CHANNELS else ""


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
    raise ValueError("Could not locate a JSON object in Agent Reach output")


def load_payload_source(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    source_path = Path(clean_text(source)).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Agent Reach result file not found: {source_path}")
    try:
        return load_json(source_path)
    except Exception:
        return extract_first_json_object(decode_text_file(source_path))


def host_for(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""


def brand_for_host(host: str) -> str:
    for fragment, brand in BRAND_BY_HOST_FRAGMENT.items():
        if fragment in host:
            return brand
    return host.replace("www.", "") if host else ""


def normalize_reddit_subreddit(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    normalized = text.lstrip("/")
    if normalized.lower().startswith("r/"):
        return f"r/{normalized[2:].lstrip('/')}"
    return f"r/{normalized}"


def normalize_reddit_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("/"):
        return urllib.parse.urljoin("https://www.reddit.com", text)
    return text


def state_store_path(path_value: Any = None) -> Path:
    if clean_text(path_value):
        return Path(clean_text(path_value)).expanduser().resolve()
    return runtime_subdir("agent-reach", "bridge-dedupe-store.json")


def load_dedupe_store(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = load_json(path)
    except Exception:
        return {}
    entries = safe_dict(payload.get("entries"))
    return {
        url: {
            "fetched_at": clean_text(safe_dict(metadata).get("fetched_at")),
            "channel": clean_text(safe_dict(metadata).get("channel")),
            "origin": clean_text(safe_dict(metadata).get("origin") or "agent_reach"),
        }
        for url, metadata in entries.items()
        if clean_text(url)
    }


def save_dedupe_store(path: Path, entries: dict[str, dict[str, str]]) -> None:
    cutoff = now_utc() - timedelta(days=7)
    kept: dict[str, dict[str, str]] = {}
    for url, metadata in entries.items():
        fetched_at = parse_datetime(metadata.get("fetched_at"), fallback=None)
        if fetched_at and fetched_at >= cutoff:
            kept[url] = metadata
    write_json(path, {"entries": kept})


def parse_relative_timestamp(text: str, fetched_at: datetime) -> datetime | None:
    normalized = clean_text(text).lower()
    if normalized in {"yesterday", "yesterday afternoon", "yesterday evening"}:
        return fetched_at - timedelta(days=1)
    if normalized == "today":
        return fetched_at
    units = {
        "minute": "minutes",
        "minutes": "minutes",
        "min": "minutes",
        "mins": "minutes",
        "hour": "hours",
        "hours": "hours",
        "hr": "hours",
        "hrs": "hours",
        "day": "days",
        "days": "days",
        "week": "weeks",
        "weeks": "weeks",
    }
    match = re.search(r"(?P<count>\d+)\s*(?P<unit>[a-z]+)\s+ago", normalized)
    if not match:
        return None
    unit = units.get(match.group("unit"))
    if not unit:
        return None
    return fetched_at - timedelta(**{unit: int(match.group("count"))})


def normalize_timestamp(value: Any, fetched_at: datetime) -> tuple[str | None, bool]:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000.0
        return isoformat_or_blank(datetime.fromtimestamp(timestamp, tz=UTC)), False
    text = clean_text(value)
    if not text:
        return None, False
    if text.isdigit() and len(text) == 8:
        parsed = parse_datetime(f"{text[:4]}-{text[4:6]}-{text[6:8]}", fallback=None)
        return (isoformat_or_blank(parsed), False) if parsed else (None, True)
    parsed = parse_datetime(text, fallback=None)
    if parsed:
        return isoformat_or_blank(parsed), False
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return isoformat_or_blank(parsed.astimezone(UTC)), False
    except (TypeError, ValueError, IndexError):
        pass
    relative = parse_relative_timestamp(text, fetched_at)
    if relative:
        return isoformat_or_blank(relative), False
    return None, True


def build_source_id(url: str, published_at: str | None, channel: str, index: int) -> str:
    basis = f"{url}|{published_at or ''}|{channel}|{index}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def infer_source_type(channel: str, url: str, item: dict[str, Any]) -> str:
    explicit = clean_text(item.get("source_type") or item.get("type")).lower().replace("-", "_").replace(" ", "_")
    if explicit:
        return explicit
    if channel == "github":
        return "community"
    if channel in {"x", "wechat", "reddit", "bilibili", "douyin", "xiaohongshu", "youtube"}:
        return "social"
    host = host_for(url)
    if any(fragment in host for fragment in ("reuters.com", "apnews.com")):
        return "wire"
    if any(fragment in host for fragment in ("axios.com", "bloomberg.com", "wsj.com", "ft.com", "nytimes.com")):
        return "major_news"
    return "major_news" if channel in {"web", "rss", "semantic"} else "blog"


def build_source_name(channel: str, url: str, item: dict[str, Any]) -> str:
    explicit = clean_text(item.get("source_name") or item.get("source") or item.get("site_name") or item.get("outlet"))
    if explicit:
        return explicit
    if channel == "github":
        owner_dict = safe_dict(item.get("owner"))
        owner = clean_text(owner_dict.get("login") or item.get("owner"))
        return f"GitHub @{owner}" if owner else "GitHub"
    if channel == "youtube":
        author = clean_text(item.get("channel_name") or item.get("uploader") or item.get("channel"))
        return f"YouTube {author}".strip() or "YouTube"
    if channel == "reddit":
        subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        return f"Reddit {subreddit}".strip() if subreddit else "Reddit"
    if channel == "x":
        author_dict = safe_dict(item.get("author"))
        author = clean_text(
            item.get("author_handle")
            or item.get("handle")
            or item.get("username")
            or author_dict.get("username")
            or author_dict.get("screen_name")
        )
        return f"X @{author.lstrip('@')}" if author else "X"
    return brand_for_host(host_for(url)) or channel


def primary_title(channel: str, item: dict[str, Any]) -> str:
    title = clean_text(item.get("title") or item.get("name") or item.get("headline"))
    if title:
        return title
    if channel == "x":
        return clean_text(item.get("text") or item.get("content"))[:120]
    if channel == "reddit":
        subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        body = clean_text(item.get("selftext") or item.get("body") or item.get("text") or item.get("content"))
        if body:
            prefix = f"{subreddit}: " if subreddit else ""
            return f"{prefix}{body}"[:160]
    if channel == "github":
        repo_name = clean_text(item.get("full_name") or item.get("fullName") or item.get("nameWithOwner"))
        description = clean_text(item.get("description"))
        return " - ".join(part for part in (repo_name, description) if part)[:160]
    return ""


def primary_url(channel: str, item: dict[str, Any]) -> str:
    url = clean_text(item.get("url") or item.get("html_url") or item.get("htmlUrl") or item.get("webpage_url") or item.get("permalink") or item.get("link") or item.get("post_url"))
    if url:
        return normalize_reddit_url(url) if channel == "reddit" else url
    if channel == "x":
        author_dict = safe_dict(item.get("author"))
        author = clean_text(
            item.get("author_handle")
            or item.get("handle")
            or item.get("username")
            or author_dict.get("username")
            or author_dict.get("screen_name")
        ).lstrip("@")
        status_id = clean_text(item.get("id") or item.get("status_id"))
        if status_id and author:
            return f"https://x.com/{author}/status/{status_id}"
        if status_id:
            return f"https://x.com/i/web/status/{status_id}"
    if channel == "youtube":
        video_id = clean_text(item.get("id"))
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    if channel == "reddit":
        subreddit = normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit"))
        post_id = clean_text(item.get("id") or item.get("post_id"))
        if subreddit and post_id:
            return f"https://www.reddit.com/{subreddit}/comments/{post_id}/"
    return ""


def primary_summary(item: dict[str, Any], title: str) -> str:
    return short_excerpt(
        item.get("summary")
        or item.get("snippet")
        or item.get("description")
        or item.get("selftext")
        or item.get("body")
        or item.get("text")
        or item.get("content")
        or title,
        limit=500,
    )


def parse_jsonish_output(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return extract_first_json_object(stripped)


def parse_rss_xml_text(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        items.append(
            {
                "title": clean_text(item.findtext("title")),
                "url": clean_text(item.findtext("link")),
                "description": clean_text(unescape(item.findtext("description") or "")),
                "published_at": clean_text(item.findtext("pubDate")),
            }
        )
    return [item for item in items if item.get("title") and item.get("url")]


def subreddit_from_reddit_permalink(url: str) -> str:
    parsed = urllib.parse.urlparse(normalize_reddit_url(url))
    match = re.search(r"/r/([^/]+)/comments/", parsed.path)
    if not match:
        return ""
    return normalize_reddit_subreddit(f"r/{match.group(1)}")


def parse_reddit_atom_feed(xml_text: str, *, listing: str, listing_window: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    records: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", namespace):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=namespace))
        link_element = entry.find("atom:link", namespace)
        url = clean_text(link_element.get("href") if link_element is not None else "")
        content = clean_text(entry.findtext("atom:content", default="", namespaces=namespace))
        updated = clean_text(entry.findtext("atom:updated", default="", namespaces=namespace))
        subreddit = subreddit_from_reddit_permalink(url)
        records.append(
            {
                "title": title,
                "permalink": normalize_reddit_url(url),
                "subreddit_name_prefixed": subreddit,
                "selftext": content,
                "published_at": updated,
                "listing": listing,
                "listing_window": listing_window,
            }
        )
    return [item for item in records if item.get("title") and item.get("permalink")]


def is_queryless_reddit_meta_title(title: Any) -> bool:
    text = clean_text(title).lower()
    if not text:
        return False
    if text.startswith(QUERYLESS_REDDIT_META_TITLE_PREFIXES):
        return True
    return any(keyword in text for keyword in QUERYLESS_REDDIT_META_TITLE_KEYWORDS)


def is_queryless_reddit_stale_record(item: dict[str, Any], analysis_time: datetime) -> bool:
    normalized_timestamp, _ = normalize_timestamp(
        item.get("published_at") or item.get("updated") or item.get("created_utc"),
        analysis_time,
    )
    if not normalized_timestamp:
        return False
    published_at = parse_datetime(normalized_timestamp, fallback=None)
    if not published_at:
        return False
    return analysis_time - published_at > timedelta(days=QUERYLESS_REDDIT_STALE_MAX_AGE_DAYS)


def should_skip_queryless_reddit_record(item: dict[str, Any], analysis_time: datetime) -> bool:
    return (
        is_queryless_reddit_meta_title(item.get("title"))
        or is_queryless_reddit_stale_record(item, analysis_time)
        or not is_queryless_reddit_thematic_record(item)
    )


def is_queryless_reddit_thematic_record(item: dict[str, Any]) -> bool:
    title = clean_text(item.get("title")).lower()
    for keyword in QUERYLESS_REDDIT_THEMATIC_KEYWORDS:
        lowered = keyword.lower()
        if re.search(r"[a-z0-9]", lowered):
            pattern = rf"(?<![a-z0-9]){re.escape(lowered)}(?![a-z0-9])"
            if re.search(pattern, title):
                return True
            continue
        if lowered in title:
            return True
    return False


def flatten_channel_payload(channel: str, payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        nested = safe_dict(payload.get("results_by_channel") or payload.get("channels"))
        nested_payload = safe_dict(nested.get(channel))
        if nested_payload:
            return flatten_channel_payload(channel, nested_payload)
        for key in ("entries", "items", "results", "tweets", "data", "posts"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
        if primary_title(channel, payload) or primary_url(channel, payload):
            return [payload]
    return []


def normalize_channel_records(channel: str, payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, str):
        stripped = payload.strip()
        if channel == "rss" and stripped.startswith("<"):
            return parse_rss_xml_text(stripped)
        payload = parse_jsonish_output(stripped)
    return flatten_channel_payload(channel, payload)


def rss_default_records(query: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = [item.lower() for item in clean_text(query).split() if item]
    records: list[dict[str, Any]] = []
    for feed in clean_string_list(request.get("rss_feeds")):
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"curl.exe -L \"{feed}\""],
            capture_output=True,
            text=True,
            timeout=request["timeout_per_channel"],
            check=False,
        )
        if completed.returncode != 0:
            continue
        for item in parse_rss_xml_text(completed.stdout):
            haystack = f"{item.get('title', '')} {item.get('description', '')}".lower()
            if keywords and not any(keyword in haystack for keyword in keywords):
                continue
            records.append(item)
    return records[: request["max_results_per_channel"]]


def reddit_default_records(query: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    limit = request["max_results_per_channel"]
    analysis_time = request.get("analysis_time")
    if not isinstance(analysis_time, datetime):
        analysis_time = now_utc()
    if not clean_text(query):
        records: list[dict[str, Any]] = []
        seen_permalinks: set[str] = set()
        per_query_limit = max(1, min(3, limit))
        for default_query in QUERYLESS_REDDIT_SEARCH_QUERIES:
            encoded_query = urllib.parse.quote_plus(default_query)
            for subreddit in QUERYLESS_REDDIT_SEARCH_SUBREDDITS:
                search_url = f"https://www.reddit.com/{subreddit}/search.json?q={encoded_query}&restrict_sr=on&sort=top&t=day&limit={per_query_limit}"
                http_request = urllib.request.Request(search_url, headers={"User-Agent": "Codex-AgentReachBridge/1.0"})
                try:
                    with urllib.request.urlopen(http_request, timeout=request["timeout_per_channel"]) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
                    continue
                children = safe_list(safe_dict(safe_dict(payload).get("data")).get("children"))
                for child in children:
                    item = safe_dict(child).get("data") if isinstance(child, dict) else {}
                    item = safe_dict(item)
                    if not item:
                        continue
                    permalink = normalize_reddit_url(item.get("permalink"))
                    if not permalink or permalink in seen_permalinks:
                        continue
                    record = {
                        "title": clean_text(item.get("title")),
                        "permalink": permalink,
                        "subreddit_name_prefixed": normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit") or subreddit),
                        "selftext": clean_text(item.get("selftext") or item.get("body") or item.get("text")),
                        "score": item.get("score"),
                        "num_comments": item.get("num_comments"),
                        "created_utc": item.get("created_utc"),
                        "listing": "top",
                        "listing_window": "day",
                    }
                    if should_skip_queryless_reddit_record(record, analysis_time):
                        continue
                    seen_permalinks.add(permalink)
                    records.append(record)
                    if len(records) >= max(limit, 8):
                        return records[: max(limit, 8)]
        for subreddit, take_count in QUERYLESS_REDDIT_SUBREDDIT_LIMITS:
            rss_request = urllib.request.Request(
                f"https://www.reddit.com/{subreddit}/hot.rss",
                headers={"User-Agent": "Codex-AgentReachBridge/1.0"},
            )
            try:
                kept_count = 0
                with urllib.request.urlopen(rss_request, timeout=request["timeout_per_channel"]) as response:
                    for item in parse_reddit_atom_feed(
                        response.read().decode("utf-8"),
                        listing="hot",
                        listing_window="day",
                    ):
                        permalink = normalize_reddit_url(item.get("permalink"))
                        if not permalink or permalink in seen_permalinks:
                            continue
                        if should_skip_queryless_reddit_record(item, analysis_time):
                            continue
                        seen_permalinks.add(permalink)
                        records.append(item)
                        kept_count += 1
                        if kept_count >= take_count:
                            break
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ET.ParseError):
                continue
            if len(records) >= max(limit, 8):
                break
        return records[: max(limit, 8)]

    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=top&t=day&limit={limit}"
    http_request = urllib.request.Request(url, headers={"User-Agent": "Codex-AgentReachBridge/1.0"})
    with urllib.request.urlopen(http_request, timeout=request["timeout_per_channel"]) as response:
        payload = json.loads(response.read().decode("utf-8"))
    records: list[dict[str, Any]] = []
    children = safe_list(safe_dict(safe_dict(payload).get("data")).get("children"))
    for child in children:
        item = safe_dict(child).get("data") if isinstance(child, dict) else {}
        item = safe_dict(item)
        if not item:
            continue
        records.append(
            {
                "title": clean_text(item.get("title")),
                "permalink": normalize_reddit_url(item.get("permalink")),
                "subreddit_name_prefixed": normalize_reddit_subreddit(item.get("subreddit_name_prefixed") or item.get("subreddit")),
                "selftext": clean_text(item.get("selftext") or item.get("body") or item.get("text")),
                "score": item.get("score"),
                "num_comments": item.get("num_comments"),
                "created_utc": item.get("created_utc"),
                "listing": "top",
                "listing_window": "day",
            }
        )
    return [item for item in records if item.get("title") and item.get("permalink")]


def x_queryless_records(request: dict[str, Any], extra_env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    limit = request["max_results_per_channel"]
    per_query_limit = max(1, min(3, limit))
    per_query_timeout = max(6, min(QUERYLESS_X_PER_QUERY_TIMEOUT_SECONDS, int(request["timeout_per_channel"])))
    aggregated: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query in QUERYLESS_X_SEARCH_QUERIES:
        command = [preferred_binary_path("bird"), "search", query, "--json", "-n", str(per_query_limit)]
        try:
            payload = run_channel_subprocess(command, per_query_timeout, extra_env)
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue
        for item in normalize_channel_records("x", payload):
            if clean_text(item.get("inReplyToStatusId") or item.get("in_reply_to_status_id")):
                continue
            url = clean_text(item.get("url"))
            dedupe_key = url or clean_text(item.get("text"))
            if not dedupe_key or dedupe_key in seen_urls:
                continue
            seen_urls.add(dedupe_key)
            aggregated.append(item)
            if len(aggregated) >= max(limit, 8):
                return aggregated[: max(limit, 8)]
    return aggregated[: max(limit, 8)]


def github_default_records(query: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=updated&order=desc&per_page={request['max_results_per_channel']}"
    http_request = urllib.request.Request(url, headers={"User-Agent": "Codex-AgentReachBridge/1.0"})
    with urllib.request.urlopen(http_request, timeout=request["timeout_per_channel"]) as response:
        payload = json.loads(response.read().decode("utf-8"))
    records: list[dict[str, Any]] = []
    for item in safe_list(safe_dict(payload).get("items")):
        if not isinstance(item, dict):
            continue
        owner = safe_dict(item.get("owner"))
        records.append(
            {
                "full_name": clean_text(item.get("full_name") or item.get("name")),
                "description": clean_text(item.get("description")),
                "url": clean_text(item.get("html_url")),
                "updatedAt": clean_text(item.get("updated_at")),
                "stargazersCount": item.get("stargazers_count"),
                "owner": {"login": clean_text(owner.get("login"))},
            }
        )
    return [item for item in records if item.get("full_name") and item.get("url")]


def default_live_command(channel: str, request: dict[str, Any]) -> list[str] | None:
    query = request["topic"]
    limit = request["max_results_per_channel"]
    if channel == "youtube":
        command = [preferred_binary_path("yt-dlp")]
        youtube_cookies_from = clean_text(request.get("agent_reach_config", {}).get("youtube_cookies_from"))
        if youtube_cookies_from:
            command.extend(["--cookies-from-browser", youtube_cookies_from])
        command.extend(["--flat-playlist", "--dump-single-json", f"ytsearch{limit}:{query}"])
        return command
    if channel == "x":
        command = [preferred_binary_path("bird")]
        if query:
            command.extend(["search", query, "--json", "-n", str(limit)])
        else:
            command.extend(
                [
                    "news",
                    "--json",
                    "-n",
                    str(limit),
                    "--ai-only",
                    "--news-only",
                    "--with-tweets",
                    "--tweets-per-item",
                    "3",
                ]
            )
        return command
    return None


def substitute_tokens(command: Any, *, channel: str, query: str, limit: int) -> list[str]:
    mapping = {"channel": channel, "query": query, "limit": str(limit)}
    if isinstance(command, list):
        return [clean_text(str(token).format(**mapping)) for token in command if clean_text(str(token).format(**mapping))]
    if isinstance(command, str):
        return [clean_text(token.format(**mapping)) for token in shlex.split(command, posix=False) if clean_text(token.format(**mapping))]
    return []


def run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> Any:
    run_kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout_seconds,
        "check": False,
    }
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
        run_kwargs["env"] = env
    completed = subprocess.run(command, **run_kwargs)
    if completed.returncode != 0:
        raise RuntimeError(clean_text(completed.stderr or completed.stdout) or f"command exited {completed.returncode}")
    return parse_jsonish_output(completed.stdout)


def channel_fetch_worker(channel: str, request: dict[str, Any]) -> dict[str, Any]:
    fetched_at = now_utc()
    if channel in request["channel_payloads"]:
        items = normalize_channel_records(channel, request["channel_payloads"][channel])
        return {"channel": channel, "status": "ok", "reason": "", "items": items[: request["max_results_per_channel"]], "fetched_at": fetched_at}
    if channel in request["channel_result_paths"]:
        payload = load_payload_source(request["channel_result_paths"][channel])
        items = normalize_channel_records(channel, payload)
        return {"channel": channel, "status": "ok", "reason": "", "items": items[: request["max_results_per_channel"]], "fetched_at": fetched_at}
    if channel == "github":
        try:
            return {
                "channel": channel,
                "status": "ok",
                "reason": "",
                "items": github_default_records(request["topic"], request),
                "fetched_at": fetched_at,
            }
        except urllib.error.HTTPError as exc:
            return {"channel": channel, "status": "failed", "reason": f"http_{exc.code}", "items": [], "fetched_at": fetched_at}
        except urllib.error.URLError as exc:
            return {"channel": channel, "status": "failed", "reason": clean_text(exc.reason or exc), "items": [], "fetched_at": fetched_at}
        except OSError as exc:
            return {"channel": channel, "status": "failed", "reason": clean_text(exc), "items": [], "fetched_at": fetched_at}
    if channel == "reddit":
        try:
            return {
                "channel": channel,
                "status": "ok",
                "reason": "",
                "items": reddit_default_records(request["topic"], request),
                "fetched_at": fetched_at,
            }
        except urllib.error.HTTPError as exc:
            return {"channel": channel, "status": "failed", "reason": f"http_{exc.code}", "items": [], "fetched_at": fetched_at}
        except urllib.error.URLError as exc:
            return {"channel": channel, "status": "failed", "reason": clean_text(exc.reason or exc), "items": [], "fetched_at": fetched_at}
        except OSError as exc:
            return {"channel": channel, "status": "failed", "reason": clean_text(exc), "items": [], "fetched_at": fetched_at}
    if channel == "rss" and request.get("rss_feeds"):
        return {"channel": channel, "status": "ok", "reason": "", "items": rss_default_records(request["topic"], request), "fetched_at": fetched_at}
    if channel == "x" and not has_twitter_credentials(request.get("agent_reach_config", {}), request["pseudo_home"]):
        return {"channel": channel, "status": "failed", "reason": "missing_credentials", "items": [], "fetched_at": fetched_at}
    subprocess_env: dict[str, str] | None = None
    if channel == "x":
        credentials = resolve_twitter_credentials(request.get("agent_reach_config", {}), request["pseudo_home"])
        if credentials["auth_token"] and credentials["ct0"]:
            subprocess_env = {"AUTH_TOKEN": credentials["auth_token"], "CT0": credentials["ct0"]}
        if not clean_text(request["topic"]):
            try:
                items = x_queryless_records(request, subprocess_env)
            except subprocess.TimeoutExpired:
                return {"channel": channel, "status": "failed", "reason": f"timeout after {request['timeout_per_channel']}s", "items": [], "fetched_at": fetched_at}
            except Exception as exc:  # noqa: BLE001
                return {"channel": channel, "status": "failed", "reason": clean_text(exc), "items": [], "fetched_at": fetched_at}
            if not items:
                return {"channel": channel, "status": "failed", "reason": "no queryless x results", "items": [], "fetched_at": fetched_at}
            return {"channel": channel, "status": "ok", "reason": "", "items": items[: request["max_results_per_channel"]], "fetched_at": fetched_at}
    command = substitute_tokens(request["channel_commands"].get(channel), channel=channel, query=request["topic"], limit=request["max_results_per_channel"]) or default_live_command(channel, request)
    if not command:
        return {"channel": channel, "status": "failed", "reason": "live fetch not configured for this channel", "items": [], "fetched_at": fetched_at}
    executable = shutil.which(command[0]) or command[0]
    if not Path(executable).exists() and not shutil.which(command[0]):
        return {"channel": channel, "status": "failed", "reason": f"{command[0]} not installed", "items": [], "fetched_at": fetched_at}
    try:
        if subprocess_env:
            payload = run_channel_subprocess(command, request["timeout_per_channel"], subprocess_env)
        else:
            payload = run_channel_subprocess(command, request["timeout_per_channel"])
    except subprocess.TimeoutExpired:
        return {"channel": channel, "status": "failed", "reason": f"timeout after {request['timeout_per_channel']}s", "items": [], "fetched_at": fetched_at}
    except Exception as exc:  # noqa: BLE001
        return {"channel": channel, "status": "failed", "reason": clean_text(exc), "items": [], "fetched_at": fetched_at}
    return {"channel": channel, "status": "ok", "reason": "", "items": normalize_channel_records(channel, payload)[: request["max_results_per_channel"]], "fetched_at": fetched_at}


def collect_channel_payloads(payload: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, Any] = {}
    for channel in SUPPORTED_CHANNELS:
        if channel in payload:
            grouped[channel] = payload[channel]
    nested = safe_dict(payload.get("results_by_channel") or payload.get("channels"))
    for key, value in nested.items():
        channel = normalize_channel_name(key)
        if channel and channel not in grouped:
            grouped[channel] = value
    if grouped:
        return grouped
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for key in COLLECTION_KEYS:
        for item in safe_list(payload.get(key)):
            if not isinstance(item, dict):
                continue
            channel = normalize_channel_name(item.get("agent_reach_channel") or item.get("channel") or item.get("platform"))
            if channel:
                by_channel.setdefault(channel, []).append(item)
    return by_channel


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    result_path = clean_text(raw_payload.get("agent_reach_result_path") or raw_payload.get("result_path") or raw_payload.get("file"))
    loaded_payload = load_payload_source(result_path) if result_path else {}
    payload = loaded_payload or safe_dict(raw_payload.get("agent_reach_result")) or raw_payload
    pseudo_home_value = clean_text(raw_payload.get("pseudo_home") or payload.get("pseudo_home"))
    pseudo_home = Path(pseudo_home_value).expanduser().resolve() if pseudo_home_value else default_agent_reach_home()
    agent_reach_config = load_agent_reach_config(pseudo_home)
    rss_feeds = clean_string_list(raw_payload.get("rss_feeds") or payload.get("rss_feeds"))
    channel_payloads = {normalize_channel_name(key): value for key, value in safe_dict(raw_payload.get("channel_payloads")).items() if normalize_channel_name(key)}
    channel_result_paths = {normalize_channel_name(key): value for key, value in safe_dict(raw_payload.get("channel_result_paths")).items() if normalize_channel_name(key)}
    channel_commands = {normalize_channel_name(key): value for key, value in safe_dict(raw_payload.get("channel_commands")).items() if normalize_channel_name(key)}
    explicit_channels = clean_string_list(raw_payload.get("channels") or payload.get("channels"))
    normalized_channels = [normalize_channel_name(name) for name in explicit_channels if normalize_channel_name(name)]
    if not normalized_channels:
        normalized_channels = default_live_channels(
            pseudo_home=pseudo_home,
            agent_reach_config=agent_reach_config,
            rss_feeds=rss_feeds,
            has_channel_overrides=bool(channel_payloads or channel_result_paths or channel_commands),
        )
    analysis_time = parse_datetime(raw_payload.get("analysis_time") or payload.get("analysis_time"), fallback=now_utc()) or now_utc()
    return {
        "topic": clean_text(raw_payload.get("topic") or payload.get("topic") or payload.get("query") or payload.get("subject")),
        "analysis_time": analysis_time,
        "questions": clean_string_list(raw_payload.get("questions") or payload.get("questions")),
        "use_case": clean_text(raw_payload.get("use_case") or payload.get("use_case")) or "agent-reach-bridge",
        "source_preferences": clean_string_list(raw_payload.get("source_preferences") or payload.get("source_preferences")) or ["social", "major_news", "official"],
        "mode": "crisis" if clean_text(raw_payload.get("mode") or payload.get("mode")).lower() == "crisis" else "generic",
        "windows": clean_string_list(raw_payload.get("windows") or payload.get("windows")) or ["10m", "1h", "6h", "24h"],
        "claims": [item for item in safe_list(raw_payload.get("claims") or payload.get("claims")) if isinstance(item, dict)],
        "market_relevance": clean_string_list(raw_payload.get("market_relevance") or payload.get("market_relevance")),
        "expected_source_families": clean_string_list(raw_payload.get("expected_source_families") or payload.get("expected_source_families")),
        "channels": normalized_channels,
        "timeout_per_channel": max(1, int(raw_payload.get("timeout_per_channel", payload.get("timeout_per_channel", DEFAULT_TIMEOUT_PER_CHANNEL)) or 1)),
        "max_results_per_channel": max(1, int(raw_payload.get("max_results_per_channel", payload.get("max_results_per_channel", 20)) or 1)),
        "dedupe_window_hours": max(1, int(raw_payload.get("dedupe_window_hours", payload.get("dedupe_window_hours", DEFAULT_DEDUPE_WINDOW_HOURS)) or 1)),
        "dedupe_store_path": state_store_path(raw_payload.get("dedupe_store_path") or payload.get("dedupe_store_path")),
        "pseudo_home": pseudo_home,
        "rss_feeds": rss_feeds,
        "channel_payloads": channel_payloads,
        "channel_result_paths": channel_result_paths,
        "channel_commands": channel_commands,
        "agent_reach_config": agent_reach_config,
        "payload": payload,
    }


def fetch_agent_reach_channels(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    grouped_payload = collect_channel_payloads(safe_dict(request["payload"]))
    if grouped_payload:
        results_by_channel = {
            channel: {"channel": channel, "status": "ok", "reason": "", "items": normalize_channel_records(channel, payload), "fetched_at": request["analysis_time"]}
            for channel, payload in grouped_payload.items()
            if channel in request["channels"] or not request["channels"]
        }
        succeeded = [channel for channel in request["channels"] if results_by_channel.get(channel, {}).get("status") == "ok"]
        return {
            "topic": request["topic"],
            "fetched_at": isoformat_or_blank(request["analysis_time"]),
            "channels_attempted": request["channels"],
            "channels_succeeded": succeeded,
            "channels_failed": [],
            "results_by_channel": results_by_channel,
            "request": request,
        }
    results_by_channel: dict[str, dict[str, Any]] = {}
    failed: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(max(1, len(request["channels"])), 4)) as executor:
        future_map = {executor.submit(channel_fetch_worker, channel, request): channel for channel in request["channels"]}
        for future in as_completed(future_map):
            channel = future_map[future]
            result = future.result()
            results_by_channel[channel] = result
            if result["status"] != "ok":
                failed.append({"channel": channel, "reason": result["reason"]})
    succeeded = [channel for channel in request["channels"] if results_by_channel.get(channel, {}).get("status") == "ok"]
    return {
        "topic": request["topic"],
        "fetched_at": isoformat_or_blank(now_utc()),
        "channels_attempted": request["channels"],
        "channels_succeeded": succeeded,
        "channels_failed": failed,
        "results_by_channel": results_by_channel,
        "request": request,
    }


def normalize_claim_ids(item: dict[str, Any], request: dict[str, Any]) -> list[str]:
    claim_ids = clean_string_list(item.get("claim_ids"))
    request_claim_ids = [clean_text(claim.get("claim_id")) for claim in request["claims"] if clean_text(claim.get("claim_id"))]
    if not claim_ids and len(request_claim_ids) == 1:
        claim_ids = request_claim_ids
    return claim_ids


def normalize_candidate_record(item: dict[str, Any], channel: str, request: dict[str, Any], fetched_at: datetime, index: int) -> dict[str, Any] | None:
    title = primary_title(channel, item)
    url = primary_url(channel, item)
    if not title or not url:
        return None
    published_at, timestamp_unparseable = normalize_timestamp(
        item.get("published_at")
        or item.get("posted_at")
        or item.get("created_at")
        or item.get("createdAt")
        or item.get("updatedAt")
        or item.get("upload_date")
        or item.get("pubDate")
        or item.get("timestamp"),
        fetched_at,
    )
    claim_ids = normalize_claim_ids(item, request)
    raw_states = safe_dict(item.get("claim_states"))
    return {
        "source_id": build_source_id(url, published_at, channel, index),
        "source_name": build_source_name(channel, url, item),
        "source_type": infer_source_type(channel, url, item),
        "origin": "agent_reach",
        "agent_reach_channel": channel,
        "published_at": published_at or "",
        "observed_at": isoformat_or_blank(fetched_at),
        "url": url,
        "claim_ids": claim_ids,
        "claim_states": {claim_id: clean_text(raw_states.get(claim_id) or item.get("claim_state") or "support") or "support" for claim_id in claim_ids},
        "entity_ids": clean_string_list(item.get("entity_ids")),
        "vessel_ids": clean_string_list(item.get("vessel_ids")),
        "text_excerpt": short_excerpt(primary_summary(item, title), limit=240),
        "channel": "shadow",
        "access_mode": clean_text(item.get("access_mode") or "public") or "public",
        "raw_metadata": {**deepcopy(item), **({"timestamp_unparseable": True} if timestamp_unparseable else {})},
        "discovery_reason": clean_text(item.get("discovery_reason") or f"Imported from Agent Reach {channel} discovery"),
    }


def dedupe_candidate(candidate: dict[str, Any], dedupe_entries: dict[str, dict[str, str]], *, dedupe_window: timedelta, seen_urls: set[str]) -> bool:
    url = clean_text(candidate.get("url"))
    if not url:
        return True
    if url in seen_urls:
        return True
    existing = safe_dict(dedupe_entries.get(url))
    fetched_at = parse_datetime(existing.get("fetched_at"), fallback=None)
    observed_at = parse_datetime(candidate.get("observed_at"), fallback=None)
    return bool(fetched_at and observed_at and existing.get("origin", "agent_reach") == "agent_reach" and observed_at - fetched_at <= dedupe_window)


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
    lines = [
        f"# Agent Reach Bridge Report: {result.get('topic', 'agent-reach-topic')}",
        "",
        f"Fetched at: {result.get('fetched_at', '')}",
        f"Channels attempted: {', '.join(result.get('channels_attempted', [])) or 'none'}",
        f"Channels succeeded: {', '.join(result.get('channels_succeeded', [])) or 'none'}",
        f"Observations fetched/imported/skipped: {result.get('observations_fetched', 0)} / {result.get('observations_imported', 0)} / {result.get('observations_skipped_duplicate', 0)}",
        "",
        "## Channel Failures",
    ]
    lines.extend([f"- {item.get('channel', '')}: {item.get('reason', '')}" for item in result.get('channels_failed', [])] or ["- None"])
    retrieval_result = safe_dict(result.get("retrieval_result"))
    if retrieval_result.get("report_markdown"):
        lines.extend(["", "## Bridged News Index", "", retrieval_result.get("report_markdown", "")])
    return "\n".join(lines).strip() + "\n"


def run_agent_reach_bridge(raw_payload: dict[str, Any]) -> dict[str, Any]:
    fetch_result = fetch_agent_reach_channels(raw_payload)
    request = fetch_result["request"]
    dedupe_entries = load_dedupe_store(request["dedupe_store_path"])
    dedupe_window = timedelta(hours=request["dedupe_window_hours"])
    seen_urls: set[str] = set()
    candidates: list[dict[str, Any]] = []
    failed_normalizations = 0
    skipped_duplicates = 0
    raw_item_count = 0
    channel_counts: dict[str, int] = {}
    for channel in request["channels"]:
        channel_result = safe_dict(fetch_result["results_by_channel"].get(channel))
        if channel_result.get("status") != "ok":
            continue
        items = [item for item in safe_list(channel_result.get("items")) if isinstance(item, dict)]
        raw_item_count += len(items)
        channel_counts[channel] = len(items)
        fetched_at = parse_datetime(channel_result.get("fetched_at"), fallback=request["analysis_time"]) or request["analysis_time"]
        for index, item in enumerate(items, start=1):
            try:
                candidate = normalize_candidate_record(item, channel, request, fetched_at, index)
            except Exception:
                failed_normalizations += 1
                continue
            if not candidate:
                failed_normalizations += 1
                continue
            if dedupe_candidate(candidate, dedupe_entries, dedupe_window=dedupe_window, seen_urls=seen_urls):
                skipped_duplicates += 1
                continue
            seen_urls.add(candidate["url"])
            dedupe_entries[candidate["url"]] = {"fetched_at": candidate["observed_at"], "channel": channel, "origin": "agent_reach"}
            candidates.append(candidate)
    save_dedupe_store(request["dedupe_store_path"], dedupe_entries)
    import_stage = import_to_news_index(request, candidates)
    result = {
        "status": "ok" if fetch_result["channels_succeeded"] else "failed",
        "topic": request["topic"],
        "fetched_at": fetch_result["fetched_at"],
        "channels_attempted": fetch_result["channels_attempted"],
        "channels_succeeded": fetch_result["channels_succeeded"],
        "channels_failed": fetch_result["channels_failed"],
        "observations_fetched": raw_item_count,
        "observations_imported": len(candidates),
        "observations_skipped_duplicate": skipped_duplicates,
        "import_summary": {
            "raw_item_count": raw_item_count,
            "imported_candidate_count": len(candidates),
            "skipped_duplicate_count": skipped_duplicates,
            "failed_normalization_count": failed_normalizations,
            "channel_counts": channel_counts,
            "default_channel_policy": "shadow_or_background_only",
            "dedupe_store_path": str(request["dedupe_store_path"]),
        },
        "retrieval_request": import_stage["retrieval_request"],
        "retrieval_result": import_stage["retrieval_result"],
    }
    result["report_markdown"] = build_markdown_report(result)
    return result


__all__ = ["build_markdown_report", "fetch_agent_reach_channels", "load_json", "normalize_request", "run_agent_reach_bridge", "write_json"]
