#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from pathlib import Path
import re
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from article_brief_runtime import build_analysis_brief
from article_evidence_bundle import (
    CONTRACT_VERSION as EVIDENCE_BUNDLE_CONTRACT_VERSION,
    build_citations as shared_build_citations,
    build_image_candidates as shared_build_image_candidates,
    build_shared_evidence_bundle,
)
from article_feedback_profiles import feedback_profile_status, load_feedback_profiles, merge_request_with_profiles, resolve_profile_dir
from news_index_runtime import isoformat_or_blank, load_json, parse_datetime, short_excerpt, write_json


def now_utc() -> datetime:
    return datetime.now(UTC)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def meaningful_image_hint(value: Any) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    if cleaned.lower().strip(" .,:;!?") in {"image", "images", "photo", "photos", "picture", "pictures", "media", "graphic", "图像", "图片", "照片"}:
        return ""
    return cleaned


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in items:
            items.append(text)
    return items


def path_exists(path_value: Any) -> bool:
    path_text = clean_text(path_value)
    return bool(path_text) and Path(path_text).exists()


def normalize_local_path(path_value: Any) -> str:
    path_text = clean_text(path_value)
    return path_text.replace("\\", "/") if path_text else ""


def is_source_result(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("x_posts", "evidence_pack", "retrieval_result", "observations", "verdict_output"))


def sanitize_draft_mode(value: Any) -> str:
    mode = clean_text(value).lower()
    if mode in {"image-first", "image_first"}:
        return "image_first"
    if mode in {"image-only", "image_only"}:
        return "image_only"
    return "balanced"


def sanitize_language_mode(value: Any) -> str:
    mode = clean_text(value).lower()
    if mode in {"bilingual", "zh-en", "zh_en", "cn-en", "cn_en"}:
        return "bilingual"
    if mode in {"chinese", "zh", "cn"}:
        return "chinese"
    return "english"


def sanitize_article_framework(value: Any) -> str:
    framework = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    if framework in {"hot_comment", "deep_analysis", "tutorial", "story", "list", "opinion"}:
        return framework
    return "auto"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    if is_source_result(payload):
        payload = {"source_result": payload}
    source_result = payload.get("source_result")
    source_result_path = clean_text(payload.get("source_result_path") or payload.get("source_path") or payload.get("input_result_path"))
    if source_result is None and source_result_path:
        source_result = load_json(Path(source_result_path).resolve())
    if not isinstance(source_result, dict):
        raise ValueError("article-draft requires source_result or source_result_path")
    analysis_brief = safe_dict(payload.get("analysis_brief"))
    analysis_brief_path = clean_text(payload.get("analysis_brief_path"))
    if not analysis_brief and analysis_brief_path:
        loaded_brief = load_json(Path(analysis_brief_path).resolve())
        analysis_brief = safe_dict(loaded_brief.get("analysis_brief")) or loaded_brief
    evidence_bundle = safe_dict(payload.get("evidence_bundle"))

    source_request = (
        safe_dict(source_result.get("request"))
        or safe_dict(source_result.get("retrieval_request"))
        or safe_dict(safe_dict(source_result.get("retrieval_result")).get("request"))
    )
    analysis_time = parse_datetime(payload.get("analysis_time"), fallback=None) or parse_datetime(
        source_request.get("analysis_time"),
        fallback=now_utc(),
    ) or now_utc()

    request = {
        "topic": clean_text(payload.get("topic") or source_request.get("topic") or "article-topic"),
        "analysis_time": analysis_time,
        "title_hint": clean_text(payload.get("title_hint")),
        "title_hint_zh": clean_text(payload.get("title_hint_zh")),
        "subtitle_hint": clean_text(payload.get("subtitle_hint")),
        "subtitle_hint_zh": clean_text(payload.get("subtitle_hint_zh")),
        "angle": clean_text(payload.get("angle")),
        "angle_zh": clean_text(payload.get("angle_zh")),
        "tone": clean_text(payload.get("tone")),
        "target_length_chars": int(payload.get("target_length_chars", payload.get("target_length", 1000))),
        "max_images": payload.get("max_images"),
        "human_signal_ratio": payload.get("human_signal_ratio"),
        "humanization_level": clean_text(payload.get("humanization_level")),
        "personal_phrase_bank": payload.get("personal_phrase_bank") or payload.get("signature_phrases"),
        "style_memory": safe_dict(payload.get("style_memory")),
        "image_strategy": clean_text(payload.get("image_strategy")),
        "draft_mode": clean_text(payload.get("draft_mode") or payload.get("composition_mode")),
        "language_mode": clean_text(payload.get("language_mode") or payload.get("output_language")),
        "article_framework": clean_text(payload.get("article_framework")),
        "headline_hook_mode": clean_text(payload.get("headline_hook_mode") or payload.get("title_hook_mode")),
        "headline_hook_prefixes": clean_string_list(
            payload.get("headline_hook_prefixes") or payload.get("title_hook_prefixes") or payload.get("title_prefixes")
        ),
        "must_include": clean_string_list(payload.get("must_include") or payload.get("focus_points")),
        "must_avoid": clean_string_list(payload.get("must_avoid")),
        "asset_output_dir": clean_text(payload.get("asset_output_dir")),
        "download_remote_images": str(payload.get("download_remote_images", "")).strip().lower() not in {"0", "false", "no", "off"},
        "feedback_profile_dir": clean_text(payload.get("feedback_profile_dir")),
        "source_result": source_result,
        "source_result_path": source_result_path,
        "analysis_brief": analysis_brief,
        "analysis_brief_path": analysis_brief_path,
        "evidence_bundle": evidence_bundle,
    }
    profile_dir = resolve_profile_dir(request.get("feedback_profile_dir"))
    profiles = load_feedback_profiles(profile_dir, request.get("topic", "article-topic"))
    request = merge_request_with_profiles(request, profiles)
    request["tone"] = clean_text(request.get("tone") or "neutral-cautious")
    request["max_images"] = max(0, min(int(request.get("max_images", 3) or 3), 8))
    request["human_signal_ratio"] = normalize_human_signal_ratio(
        request.get("human_signal_ratio"),
        fallback=human_signal_ratio_from_level(request.get("humanization_level")),
    )
    request["humanization_level"] = human_signal_level(int(request.get("human_signal_ratio", 35) or 35))
    request["personal_phrase_bank"] = normalize_phrase_bank(request.get("personal_phrase_bank"))
    request["image_strategy"] = clean_text(request.get("image_strategy") or "mixed")
    request["draft_mode"] = sanitize_draft_mode(request.get("draft_mode"))
    request["language_mode"] = sanitize_language_mode(request.get("language_mode"))
    request["article_framework"] = sanitize_article_framework(request.get("article_framework"))
    request["headline_hook_mode"] = normalize_headline_hook_mode(request.get("headline_hook_mode"))
    request["headline_hook_prefixes"] = clean_string_list(request.get("headline_hook_prefixes"))
    request["feedback_profile_dir"] = str(profile_dir)
    request["feedback_profile_status"] = feedback_profile_status(
        profile_dir,
        request.get("topic", "article-topic"),
        profiles=profiles,
    )
    return request


def ensure_evidence_bundle(request: dict[str, Any]) -> dict[str, Any]:
    bundle = safe_dict(request.get("evidence_bundle"))
    if clean_text(bundle.get("contract_version")) != EVIDENCE_BUNDLE_CONTRACT_VERSION:
        bundle = {}
    required_keys = {"source_summary", "evidence_digest", "citations", "image_candidates"}
    if not required_keys.issubset(bundle.keys()):
        bundle = build_shared_evidence_bundle(request["source_result"], request)
    return deepcopy(bundle)

def extract_runtime_result(source_result: dict[str, Any]) -> dict[str, Any]:
    runtime = safe_dict(source_result.get("retrieval_result"))
    if runtime:
        return runtime
    if safe_list(source_result.get("observations")) or safe_dict(source_result.get("verdict_output")):
        return source_result
    adapted = deepcopy(source_result)
    adapted["request"] = safe_dict(adapted.get("request")) or safe_dict(adapted.get("retrieval_request"))
    adapted["observations"] = safe_list(adapted.get("observations")) or safe_list(adapted.get("source_observations"))
    return adapted


def claim_texts(value: Any) -> list[str]:
    texts: list[str] = []
    for item in safe_list(value):
        text = clean_text(item.get("claim_text") if isinstance(item, dict) else item)
        if text and text not in texts:
            texts.append(text)
    return texts


def claim_texts_with_map(value: Any, text_map: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for item in safe_list(value):
        if isinstance(item, dict):
            claim_id = clean_text(item.get("claim_id"))
            text = clean_text(text_map.get(claim_id) or item.get("claim_text"))
        else:
            text = clean_text(item)
        if text and text not in texts:
            texts.append(text)
    return texts


def normalize_latest_signals(value: Any) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        signals.append(
            {
                "source_name": clean_text(item.get("source_name")),
                "source_tier": int(item.get("source_tier", 3)),
                "channel": clean_text(item.get("channel")),
                "age": clean_text(item.get("age")),
                "text_excerpt": clean_text(item.get("text_excerpt")),
            }
        )
    return signals


def build_source_summary(source_result: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = extract_runtime_result(source_result)
    verdict = safe_dict(runtime.get("verdict_output"))
    observations = safe_list(runtime.get("observations"))
    source_request = (
        safe_dict(source_result.get("request"))
        or safe_dict(source_result.get("retrieval_request"))
        or safe_dict(runtime.get("request"))
    )
    claim_text_zh_map = {
        clean_text(item.get("claim_id")): clean_text(item.get("claim_text_zh"))
        for item in safe_list(source_request.get("claims"))
        if isinstance(item, dict) and clean_text(item.get("claim_id")) and clean_text(item.get("claim_text_zh"))
    }
    blocked = sum(1 for item in observations if clean_text(item.get("access_mode")) == "blocked")
    summary = {
        "source_kind": "x_index" if safe_list(source_result.get("x_posts")) or safe_dict(source_result.get("evidence_pack")) else "news_index",
        "topic": clean_text(request.get("topic")),
        "analysis_time": isoformat_or_blank(request["analysis_time"]),
        "blocked_source_count": blocked,
        "confidence_interval": verdict.get("confidence_interval", [0, 0]),
        "confidence_gate": clean_text(verdict.get("confidence_gate")),
        "core_verdict": clean_text(verdict.get("core_verdict")),
        "market_relevance": clean_string_list(verdict.get("market_relevance")),
        "market_relevance_zh": clean_string_list(source_request.get("market_relevance_zh")),
    }
    digest = {
        "core_verdict": summary["core_verdict"],
        "confirmed": claim_texts(verdict.get("confirmed")),
        "not_confirmed": claim_texts(verdict.get("not_confirmed")),
        "inference_only": claim_texts(verdict.get("inference_only")),
        "confirmed_zh": claim_texts_with_map(verdict.get("confirmed"), claim_text_zh_map),
        "not_confirmed_zh": claim_texts_with_map(verdict.get("not_confirmed"), claim_text_zh_map),
        "inference_only_zh": claim_texts_with_map(verdict.get("inference_only"), claim_text_zh_map),
        "latest_signals": normalize_latest_signals(verdict.get("latest_signals")),
        "next_watch_items": clean_string_list(verdict.get("next_watch_items")),
        "confidence_interval": summary["confidence_interval"],
        "confidence_gate": summary["confidence_gate"],
        "market_relevance": summary["market_relevance"],
        "market_relevance_zh": summary["market_relevance_zh"],
    }
    return summary, digest


def build_citations(source_result: dict[str, Any]) -> list[dict[str, Any]]:
    return shared_build_citations(source_result)


def candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("score", 0)),
        1 if path_exists(item.get("path")) else 0,
        1 if clean_text(item.get("summary") or item.get("caption")) else 0,
    )


def normalize_image_reference(path: Any, source_url: Any) -> tuple[str, str]:
    clean_path = clean_text(path)
    clean_url = clean_text(source_url)
    if clean_path.startswith(("http://", "https://", "file://")) and not clean_url:
        return "", clean_path
    return clean_path, clean_url


def image_candidate_key(role: Any, path: Any, source_url: Any) -> tuple[str, str, str]:
    clean_role = clean_text(role)
    clean_path, clean_url = normalize_image_reference(path, source_url)
    if clean_path:
        return clean_role, "path", clean_path
    return clean_role, "url", clean_url


def is_screenshot_role(role: Any) -> bool:
    clean_role = clean_text(role).lower()
    return bool(clean_role) and (clean_role == "screenshot" or clean_role.endswith("_screenshot") or "screenshot" in clean_role)


def build_image_candidates(source_result: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    return shared_build_image_candidates(source_result, request)


def build_selected_images(image_candidates: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in image_candidates[: request.get("max_images", 3)]:
        path_text = clean_text(item.get("path"))
        source_url = clean_text(item.get("source_url"))
        access_mode = clean_text(item.get("access_mode"))
        summary = clean_text(item.get("summary") or item.get("caption"))
        alt_text = clean_text(item.get("alt_text"))
        capture_method = clean_text(item.get("capture_method"))
        if summary:
            caption = summary
        elif alt_text:
            caption = alt_text
        elif is_screenshot_role(item.get("role")) and access_mode == "blocked":
            caption = "Source screenshot from a blocked page. Keep it as visual evidence only."
        elif item.get("role") == "post_media" and capture_method == "dom_clip":
            caption = "Browser-captured image from the original X post."
        elif is_screenshot_role(item.get("role")):
            caption = "Source page screenshot."
        else:
            caption = "Key source image."
        render_target = normalize_local_path(path_text) or source_url
        status = "local_ready" if path_exists(path_text) else "remote_only" if source_url else "missing"
        placement = {0: "after_lede", 1: "after_section_2", 2: "after_section_3"}.get(len(selected), "appendix")
        selected.append(
            {
                **item,
                "asset_id": clean_text(item.get("image_id")),
                "render_target": render_target,
                "embed_target": render_target,
                "caption": caption,
                "status": status,
                "placement": placement,
                "embed_markdown": f"![{clean_text(item.get('image_id'))}]({render_target})" if render_target else "",
            }
        )
    return selected


def image_candidate_match_keys(item: dict[str, Any]) -> list[tuple[str, ...]]:
    keys: list[tuple[str, ...]] = []
    image_id = clean_text(item.get("image_id") or item.get("asset_id"))
    if image_id:
        keys.append(("id", image_id))
    role = clean_text(item.get("role"))
    source_url = clean_text(item.get("source_url") or item.get("localized_from"))
    source_name = clean_text(item.get("source_name"))
    if role or source_url or source_name:
        keys.append(("source", role, source_url, source_name))
    path_text = clean_text(item.get("path") or item.get("render_target") or item.get("embed_target"))
    if role and path_text:
        keys.append(("path", role, path_text))
    return keys


def merge_localized_image_candidates(
    image_candidates: list[dict[str, Any]],
    localized_images: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    localized_lookup: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in localized_images:
        local_path = clean_text(item.get("path") or item.get("render_target") or item.get("embed_target"))
        if not local_path or not path_exists(local_path):
            continue
        localized_item = deepcopy(item)
        localized_item["path"] = local_path
        for key in image_candidate_match_keys(localized_item):
            localized_lookup[key] = localized_item

    if not localized_lookup:
        return deepcopy(image_candidates)

    merged_candidates: list[dict[str, Any]] = []
    for item in image_candidates:
        merged = deepcopy(item)
        match = next((localized_lookup[key] for key in image_candidate_match_keys(merged) if key in localized_lookup), None)
        if not match:
            merged_candidates.append(merged)
            continue

        merged["path"] = clean_text(match.get("path"))
        merged["status"] = "local_ready"
        localized_from = clean_text(match.get("localized_from"))
        if localized_from:
            merged["localized_from"] = localized_from
            if not clean_text(merged.get("source_url")):
                merged["source_url"] = localized_from
        for field in ("summary", "caption", "alt_text", "capture_method", "access_mode", "relevance"):
            if not clean_text(merged.get(field)) and clean_text(match.get(field)):
                merged[field] = clean_text(match.get(field))
        if merged.get("source_tier") in (None, "") and match.get("source_tier") not in (None, ""):
            merged["source_tier"] = int(match.get("source_tier"))
        merged_candidates.append(merged)
    return merged_candidates


def strip_source_branding(text: Any) -> str:
    cleaned = clean_text(text)
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


def public_topic_text(request: dict[str, Any], fallback: str = "Developing Story") -> str:
    return strip_source_branding(request.get("topic")) or fallback


def human_signal_ratio_from_level(value: Any) -> int:
    mapping = {
        "low": 25,
        "light": 25,
        "medium": 50,
        "balanced": 50,
        "high": 75,
        "heavy": 75,
        "max": 90,
        "maximum": 90,
    }
    return mapping.get(clean_text(value).lower().replace("-", "_"), 35)


def normalize_human_signal_ratio(value: Any, *, fallback: int = 35) -> int:
    if value in (None, "", []):
        return max(0, min(int(fallback or 35), 100))
    try:
        numeric = float(str(value).strip().rstrip("%"))
    except ValueError:
        numeric = float(human_signal_ratio_from_level(value))
    if 0 < numeric <= 1:
        numeric *= 100
    return max(0, min(int(round(numeric)), 100))


def human_signal_level(value: int) -> str:
    if value >= 80:
        return "high"
    if value >= 55:
        return "medium"
    return "low"


def normalize_phrase_bank(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[\n\r,，;；|｜]+", value)
    else:
        raw_items = safe_list(value)
    cleaned: list[str] = []
    for item in raw_items:
        text = clean_text(item)
        if not text or text in cleaned:
            continue
        if "http://" in text or "https://" in text:
            continue
        cleaned.append(text)
    return cleaned[:12]


DEFAULT_VOICE_PREFIXES = {
    "chinese": {
        "lede": "先说结论",
        "facts": "先把关键点摆出来",
        "spread": "麻烦在于",
        "impact": "更关键的是",
        "watch": "最后盯三件事",
    },
    "english": {
        "lede": "Put simply",
        "facts": "Start with the core point",
        "spread": "The problem is",
        "impact": "More importantly",
        "watch": "Three things matter next",
    },
}


def voice_mode_for_request(request: dict[str, Any]) -> str:
    return "chinese" if clean_text(request.get("language_mode")) == "chinese" else "english"


def short_voice_phrases(request: dict[str, Any]) -> list[str]:
    mode = voice_mode_for_request(request)
    phrases = []
    for item in normalize_phrase_bank(request.get("personal_phrase_bank")):
        if mode == "chinese" and has_cjk(item) and len(item) <= 12:
            phrases.append(item)
        elif mode != "chinese" and len(item.split()) <= 5:
            phrases.append(item)
    return phrases


def pick_voice_prefix(request: dict[str, Any], slot: str) -> str:
    ratio = int(request.get("human_signal_ratio", 35) or 35)
    if ratio < 55:
        return ""
    mode = voice_mode_for_request(request)
    personal_phrases = short_voice_phrases(request)
    slot_order = {"lede": 0, "facts": 1, "spread": 2, "impact": 3, "watch": 4}
    if personal_phrases:
        return personal_phrases[min(slot_order.get(slot, 0), len(personal_phrases) - 1)]
    return DEFAULT_VOICE_PREFIXES[mode].get(slot, "")


def prepend_voice_prefix(prefix: str, text: str, *, mode: str) -> str:
    sentence = clean_text(text)
    tag = clean_text(prefix)
    if not tag or not sentence:
        return sentence
    if sentence.startswith(tag):
        return sentence
    if mode == "chinese":
        if sentence.startswith(("先", "更", "最后", "别")):
            return sentence
        return f"{tag}，{sentence}"
    return f"{tag}, {lowercase_first(sentence)}"


def chinese_market_focus(text: str) -> str:
    cleaned = strip_terminal_punctuation(clean_text(text))
    if not cleaned:
        return ""
    if any(token in cleaned for token in ("能源", "油", "气", "霍尔木兹", "LNG", "天然气")):
        return "能源安全和输入性通胀压力"
    if any(token in cleaned for token in ("航运", "保险", "供应链", "商船", "油轮")):
        return "航运、保险和供应链成本"
    if any(token in cleaned for token in ("外交", "中东布局", "撤离", "撤侨", "公民", "表态")):
        return "外交回旋空间和中东布局"
    if any(token in cleaned for token in ("炼化", "化工", "制造业", "利润")):
        return "炼化、化工和制造业利润"
    return cleaned


def chinese_watch_item(text: str) -> str:
    cleaned = chinese_market_focus(text)
    if not cleaned:
        return ""
    if "能源安全" in cleaned:
        return "霍尔木兹、油气价格和输入性通胀这条线会不会继续往上推"
    if "航运、保险和供应链成本" in cleaned:
        return "航运、保险和供应链成本会不会继续抬升"
    if "外交回旋空间和中东布局" in cleaned:
        return "中方后续表态、撤离安排和地区外交动作会不会出现新变化"
    if "炼化、化工和制造业利润" in cleaned:
        return "成本压力会不会继续往中下游利润表里传"
    return f"{cleaned}会不会继续扩大"


def preliminary_watch_items(
    market_relevance: list[str],
    not_proven_texts: list[str],
    *,
    mode: str,
) -> list[str]:
    items: list[str] = []
    if mode == "chinese":
        for item in market_relevance:
            watch_item = chinese_watch_item(item)
            if watch_item and watch_item not in items:
                items.append(watch_item)
        if not items and not_proven_texts:
            items.append(f"围绕“{not_proven_texts[0]}”的市场想象会不会继续跑在事实前面")
        return items[:3]
    for item in market_relevance[:3]:
        cleaned = strip_terminal_punctuation(item)
        if cleaned:
            items.append(f"whether {lowercase_first(cleaned)} keeps spreading into actual decisions")
    if not items and not_proven_texts:
        items.append(f"whether the market keeps leaning too hard on the unresolved claim: {not_proven_texts[0]}")
    return items[:3]


def normalize_phrase_bank(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[\n\r,，；;、]+", value)
    else:
        raw_items = safe_list(value)
    cleaned: list[str] = []
    for item in raw_items:
        text = clean_text(item)
        if not text or text in cleaned:
            continue
        if "http://" in text or "https://" in text:
            continue
        cleaned.append(text)
    return cleaned[:12]


DEFAULT_VOICE_PREFIXES = {
    "chinese": {
        "lede": "先说结论",
        "facts": "先把关键点摆出来",
        "spread": "麻烦在于",
        "impact": "更关键的是",
        "watch": "最后盯三件事",
    },
    "english": {
        "lede": "Put simply",
        "facts": "Start with the core point",
        "spread": "The problem is",
        "impact": "More importantly",
        "watch": "Three things matter next",
    },
}


def prepend_voice_prefix(prefix: str, text: str, *, mode: str) -> str:
    sentence = clean_text(text)
    tag = clean_text(prefix)
    if not tag or not sentence:
        return sentence
    if sentence.startswith(tag):
        return sentence
    if mode == "chinese":
        if sentence.startswith(("先", "更", "最后", "别")):
            return sentence
        return f"{tag}，{sentence}"
    return f"{tag}, {lowercase_first(sentence)}"


def chinese_market_focus(text: str) -> str:
    cleaned = strip_terminal_punctuation(clean_text(text))
    if not cleaned:
        return ""
    if any(token in cleaned for token in ("能源", "油", "气", "霍尔木兹", "LNG", "天然气")):
        return "能源安全和输入性通胀压力"
    if any(token in cleaned for token in ("航运", "保险", "供应链", "商船", "油轮")):
        return "航运、保险和供应链成本"
    if any(token in cleaned for token in ("外交", "中东布局", "撤离", "撤侨", "公民", "表态")):
        return "外交回旋空间和中东布局"
    if any(token in cleaned for token in ("炼化", "化工", "制造业", "利润")):
        return "炼化、化工和制造业利润"
    return cleaned


def chinese_watch_item(text: str) -> str:
    cleaned = chinese_market_focus(text)
    if not cleaned:
        return ""
    if "能源安全" in cleaned:
        return "霍尔木兹、油气价格和输入性通胀这条线会不会继续往上推"
    if "航运、保险和供应链成本" in cleaned:
        return "航运、保险和供应链成本会不会继续抬升"
    if "外交回旋空间和中东布局" in cleaned:
        return "中方后续表态、撤离安排和地区外交动作会不会出现新变化"
    if "炼化、化工和制造业利润" in cleaned:
        return "成本压力会不会继续往中下游利润表里传"
    return f"{cleaned}会不会继续扩大"


def preliminary_watch_items(
    market_relevance: list[str],
    not_proven_texts: list[str],
    *,
    mode: str,
) -> list[str]:
    items: list[str] = []
    if mode == "chinese":
        for item in market_relevance:
            watch_item = chinese_watch_item(item)
            if watch_item and watch_item not in items:
                items.append(watch_item)
        if not items and not_proven_texts:
            items.append(f"围绕“{not_proven_texts[0]}”的市场想象会不会继续跑在事实前面")
        return items[:3]
    for item in market_relevance[:3]:
        cleaned = strip_terminal_punctuation(item)
        if cleaned:
            items.append(f"whether {lowercase_first(cleaned)} keeps spreading into actual decisions")
    if not items and not_proven_texts:
        items.append(f"whether the market keeps leaning too hard on the unresolved claim: {not_proven_texts[0]}")
    return items[:3]


def resolve_article_framework(request: dict[str, Any], source_summary: dict[str, Any] | None = None) -> str:
    explicit = sanitize_article_framework(request.get("article_framework"))
    if explicit != "auto":
        return explicit
    topic = public_topic_text(request).lower()
    if any(token in topic for token in ("how to", "guide", "tutorial", "\u6559\u7a0b", "\u6307\u5357", "\u65b9\u6cd5", "\u6b65\u9aa4")):
        return "tutorial"
    if any(token in topic for token in ("list", "tools", "tool", "\u76d8\u70b9", "\u6e05\u5355", "\u699c\u5355")):
        return "list"
    if any(token in topic for token in ("founder", "interview", "\u4eba\u7269", "\u521b\u59cb\u4eba", "\u8bbf\u8c08", "profile", "origin story", "founder story")):
        return "story"
    if any(token in topic for token in ("opinion", "\u5410\u69fd", "\u4e89\u8bae", "should", "\u503c\u4e0d\u503c")):
        return "opinion"
    if any(
        token in topic
        for token in (
            "\u878d\u8d44",
            "policy",
            "regulation",
            "industry",
            "trend",
            "platform",
            "\u5e73\u53f0",
            "\u53d1\u5e03",
            "launch",
            "hiring",
            "recruit",
            "employment",
            "business story",
            "strategy",
        )
    ):
        return "deep_analysis"
    if source_summary and int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        return "hot_comment"
    return "hot_comment"


''' Disabled legacy public-writer block kept only for forensic recovery.
The active implementation lives in the safe redefinitions below.

def build_title(request: dict[str, Any], digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    del digest, selected_images
    language_mode = request.get("language_mode", "english")
    title_hint = clean_text(request.get("title_hint"))
    title_hint_zh = clean_text(request.get("title_hint_zh"))
    if title_hint or title_hint_zh:
        return bilingual_heading(title_hint_zh, title_hint, language_mode)
    topic = public_topic_text(request)
    if topic:
        if language_mode == "bilingual":
            return topic
        return bilingual_heading(topic, topic, language_mode)
    framework = resolve_article_framework(request)
    fallback_titles = {
        "hot_comment": ("这件事真正值得看的是什么", "What really matters in this story"),
        "deep_analysis": ("这件事为什么值得关注", "Why this story matters now"),
        "tutorial": ("三步看懂这件事", "How to break this down in three steps"),
        "story": ("这件事的关键转折", "The turning point in this story"),
        "list": ("这件事最值得看的三个点", "Three angles worth watching here"),
        "opinion": ("别只看热度，要看真正的变化", "Ignore the noise and look at the real shift"),
    }
    title_zh, title_en = fallback_titles.get(framework, fallback_titles["hot_comment"])
    return bilingual_heading(title_zh, title_en, language_mode)


def build_subtitle(request: dict[str, Any], summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    subtitle_hint = clean_text(request.get("subtitle_hint"))
    subtitle_hint_zh = clean_text(request.get("subtitle_hint_zh"))
    if subtitle_hint or subtitle_hint_zh:
        return bilingual_text(subtitle_hint_zh, subtitle_hint, language_mode)
    if request.get("draft_mode") == "image_only":
        return bilingual_text(
            "先看图里能确认什么，再决定这件事该怎么写。",
            "Start with what the images can genuinely support, then decide how far the story should go.",
            language_mode,
        )
    framework = resolve_article_framework(request, summary)
    if framework == "tutorial":
        return bilingual_text(
            "把问题拆开讲清楚，比堆观点更重要。",
            "Clarity matters more than volume here, so the draft breaks the problem into practical steps.",
            language_mode,
        )
    if framework == "story":
        return bilingual_text(
            "真正值得写的，不只是事件本身，而是它走到这一步的关键转折。",
            "The value is not just the event itself, but the turning point that pushed it into focus.",
            language_mode,
        )
    if framework == "list":
        return bilingual_text(
            "别急着下结论，先把最关键的几个观察点摆出来。",
            "Before jumping to a verdict, put the few highest-signal observations on the table.",
            language_mode,
        )
    if summary.get("source_kind") == "x_index" and selected_images:
        return bilingual_text(
            "热度会骗人，真正有用的是能落回公开信息和一手素材的那部分。",
            "Heat can be misleading. What matters is the part of the story that still lands on public evidence and first-hand material.",
            language_mode,
        )
    return bilingual_text(
        "先把发生了什么说清楚，再看这件事为什么会继续发酵。",
        "Start with what changed, then look at why the discussion is still gaining heat.",
        language_mode,
    )


def citation_ids_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> list[str]:
    citation_ids: list[str] = []
    source_id_set = set(clean_string_list(source_ids))
    for citation in citations:
        citation_source_id = clean_text(citation.get("source_id"))
        citation_id = clean_text(citation.get("citation_id"))
        if citation_source_id in source_id_set and citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
    return citation_ids


def refs_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> str:
    refs = [f"[{citation_id}]" for citation_id in citation_ids_for_source_ids(citations, source_ids)]
    return "".join(refs)


def top_citation_ids(citations: list[dict[str, Any]], limit: int = 2) -> list[str]:
    citation_ids: list[str] = []
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        if citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
        if len(citation_ids) >= max(1, limit):
            break
    return citation_ids


def preferred_citation_ids(
    citations: list[dict[str, Any]],
    source_ids: list[str] | None = None,
    *,
    limit: int = 2,
) -> list[str]:
    matched = citation_ids_for_source_ids(citations, clean_string_list(source_ids))
    if matched:
        return matched[: max(1, limit)]
    ranked = [
        item
        for item in citations
        if clean_text(item.get("access_mode")) != "blocked" and int(item.get("source_tier", 3)) <= 1
    ]
    if not ranked:
        ranked = [item for item in citations if clean_text(item.get("access_mode")) != "blocked"]
    return top_citation_ids(ranked or citations, limit=limit)


def citation_channels_for_ids(citations: list[dict[str, Any]], citation_ids: list[str]) -> list[str]:
    channels: list[str] = []
    wanted = set(clean_string_list(citation_ids))
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        channel = clean_text(citation.get("channel"))
        if citation_id in wanted and channel and channel not in channels:
            channels.append(channel)
    return channels


def join_with_semicolons(items: list[str], empty_text: str) -> str:
    clean_items = [clean_text(item) for item in items if clean_text(item)]
    return "; ".join(clean_items) if clean_items else empty_text


def strip_terminal_punctuation(text: str) -> str:
    return clean_text(text).rstrip(" .;:")


def lowercase_first(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    return cleaned[:1].lower() + cleaned[1:]


def join_with_commas(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def bilingual_heading(zh: str, en: str, mode: str) -> str:
    zh_text = clean_text(zh)
    en_text = clean_text(en)
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text} | {en_text}"
        return zh_text or en_text
    return en_text or zh_text


def bilingual_text(zh: str, en: str, mode: str) -> str:
    zh_text = str(zh or "").replace("\u200b", " ").strip()
    en_text = str(en or "").replace("\u200b", " ").strip()
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text}\n\n{en_text}"
        return zh_text or en_text
    return en_text or zh_text


def signal_sentence(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "There are not enough fresh public signals yet to upgrade any single hint into a firm conclusion."
    parts = []
    for item in signals[:3]:
        source_name = clean_text(item.get("source_name")) or "Unknown source"
        age = clean_text(item.get("age")) or "unknown age"
        excerpt = short_excerpt(clean_text(item.get("text_excerpt")), limit=100) or "new signal"
        parts.append(f"{source_name} ({age}) said: {excerpt}")
    return "Latest signals first: " + "; ".join(parts) + "."


def image_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is attached to this draft yet."
    parts = []
    for item in images[:3]:
        source_name = clean_text(item.get("source_name")) or "Unnamed source"
        caption = short_excerpt(clean_text(item.get("caption")), limit=100) or "no machine-readable image summary"
        parts.append(f"{source_name}: {caption}")
    return "Key images kept for the article: " + "; ".join(parts) + "."


def visual_evidence_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is available, so this version cannot be image-first in practice."
    parts = []
    for item in images[:3]:
        role = clean_text(item.get("role")).replace("_", " ")
        status = clean_text(item.get("status")) or "unknown"
        caption = short_excerpt(clean_text(item.get("caption")), limit=110) or "no machine-readable summary"
        parts.append(f"{role}: {caption} [{status}]")
    return "Visual evidence layer: " + "; ".join(parts) + "."


def apply_must_avoid(text: str, must_avoid: list[str]) -> str:
    updated = text
    for phrase in must_avoid:
        updated = updated.replace(phrase, "")
    return updated


def derive_analysis_brief_from_digest(
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_source_ids = clean_string_list([citation.get("source_id") for citation in citations[:2]])
    canonical_facts = [
        {
            "claim_id": f"derived-confirmed-{index + 1}",
            "claim_text": text,
            "source_ids": primary_source_ids if index == 0 else [],
            "promotion_state": "core",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("confirmed"))[:4])
    ]
    not_proven = [
        {
            "claim_id": f"derived-not-proven-{index + 1}",
            "claim_text": text,
            "source_ids": [],
            "status": "unclear",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("not_confirmed"))[:4])
    ]
    latest_signal_summary = signal_sentence(normalize_latest_signals(evidence_digest.get("latest_signals")))
    story_angles = [
        {
            "angle": "Lead with the confirmed public record before discussing faster-moving signals.",
            "risk": "Do not turn social or single-source updates into settled fact.",
        }
    ]
    if images:
        story_angles.append(
            {
                "angle": "Use saved images as supporting context, not as proof beyond what they visibly show.",
                "risk": "Treat visuals as the last public indication, not ground truth.",
            }
        )
    open_questions = clean_string_list(evidence_digest.get("next_watch_items"))[:4]
    voice_constraints = [
        "Keep facts, inference, and visual hints clearly separated.",
        "Do not write past the strongest confirmed evidence.",
    ]
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        voice_constraints.append("Some sources were blocked, so the draft should not imply the search was complete.")
    if clean_text(source_summary.get("confidence_gate")) == "shadow-heavy":
        voice_constraints.append("Shadow-only signals can raise attention, but they cannot carry the main conclusion alone.")
    misread_risks = []
    if not canonical_facts:
        misread_risks.append("The package does not yet have a strong confirmed fact to anchor the draft.")
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        misread_risks.append("Blocked or missing sources could hide confirming or contradicting evidence.")
    if images:
        misread_risks.append("Readers may overread the images if the captions are written too strongly.")
    recommended_thesis = (
        clean_text(source_summary.get("core_verdict"))
        or (clean_string_list(evidence_digest.get("confirmed")) or ["Current evidence remains incomplete."])[0]
    )
    return {
        "canonical_facts": canonical_facts,
        "not_proven": not_proven,
        "open_questions": open_questions,
        "trend_lines": [
            {
                "trend": "Latest signals",
                "detail": latest_signal_summary,
            }
        ],
        "scenario_matrix": [],
        "market_or_reader_relevance": clean_string_list(evidence_digest.get("market_relevance")),
        "story_angles": story_angles,
        "image_keep_reasons": [
            {
                "image_id": clean_text(item.get("image_id") or item.get("asset_id")),
                "reason": clean_text(item.get("caption")) or "Retained as visual context for the draft.",
            }
            for item in images[:3]
        ],
        "voice_constraints": voice_constraints,
        "recommended_thesis": recommended_thesis,
        "misread_risks": misread_risks,
    }


def brief_items_text(items: list[dict[str, Any]], fallback: str, *, field: str = "claim_text") -> str:
    texts = [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))]
    return join_with_semicolons(texts, fallback)


def item_texts(items: list[dict[str, Any]], *, field: str = "claim_text", limit: int = 3) -> list[str]:
    return [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))][:limit]


def framework_headings(framework: str) -> list[tuple[str, str]]:
    heading_map = {
        "hot_comment": [
            ("事情先说清楚", "What Changed"),
            ("热度为什么还在涨", "Why The Story Is Spreading"),
            ("为什么这事值得关注", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "deep_analysis": [
            ("先看变化本身", "What Changed"),
            ("深层原因", "The Deeper Driver"),
            ("影响会传到哪里", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "tutorial": [
            ("核心问题", "The Core Problem"),
            ("先看判断方法", "How To Read It"),
            ("三个实操动作", "Three Practical Moves"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "story": [
            ("关键转折", "The Turning Point"),
            ("事情是怎么走到这里的", "How The Story Reached Here"),
            ("这件事说明了什么", "Why This Matters"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "list": [
            ("第一个信号", "First Signal"),
            ("第二个信号", "Second Signal"),
            ("第三个信号", "Third Signal"),
            ("接下来盯什么", "What To Watch Next"),
        ],
        "opinion": [
            ("事情先说清楚", "What Changed"),
            ("噪音从哪来", "Where The Noise Starts"),
            ("我的判断", "The View"),
            ("接下来盯什么", "What To Watch Next"),
        ],
    }
    return heading_map.get(framework, heading_map["hot_comment"])


LEGACY_HEADLINE_HOOK_URGENT_TOKENS = (
    "泄露",
    "曝光",
    "突发",
    "重磅",
    "官宣",
    "发布",
    "起诉",
    "停火",
    "空袭",
    "回应",
    "裁员",
    "并购",
)


def legacy_headline_hook_prefixes(request: dict[str, Any], *, mode: str) -> list[str]:
    custom_prefixes = clean_string_list(request.get("headline_hook_prefixes"))
    if custom_prefixes:
        return custom_prefixes
    if mode == "aggressive":
        return ["突发！", "重磅！", "刚刚，"]
    if mode == "traffic":
        return ["刚刚，", "突发！", "最新，"]
    return []


def legacy_title_has_headline_hook(title: Any) -> bool:
    cleaned = clean_text(title)
    if not cleaned:
        return False
    for prefix in ("突发！", "刚刚，", "刚刚", "最新，", "最新：", "重磅！"):
        if cleaned.startswith(prefix):
            return True
    return False


def legacy_resolve_headline_hook_mode(request: dict[str, Any], source_summary: dict[str, Any]) -> str:
    del source_summary
    configured_mode = normalize_headline_hook_mode(request.get("headline_hook_mode"))
    if configured_mode != "auto":
        return configured_mode
    return "neutral"


def legacy_choose_headline_hook_prefix(title: str, request: dict[str, Any], source_summary: dict[str, Any], *, mode: str) -> str:
    prefixes = legacy_headline_hook_prefixes(request, mode=mode)
    if not prefixes:
        return ""
    if mode == "aggressive":
        return prefixes[0]
    urgency_seed = " ".join(
        clean_text(item)
        for item in (title, clean_text(source_summary.get("topic")), public_topic_text(request, clean_text(source_summary.get("topic")) or ""))
        if clean_text(item)
    )
    if any(token in urgency_seed for token in LEGACY_HEADLINE_HOOK_URGENT_TOKENS):
        return next((prefix for prefix in prefixes if "！" in prefix), prefixes[0])
    return prefixes[0]


def legacy_apply_headline_hook(title: str, request: dict[str, Any], source_summary: dict[str, Any]) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return title
    compact_title = compact_chinese_title(title, limit=30) or title
    if legacy_title_has_headline_hook(compact_title):
        return compact_title
    hook_mode = legacy_resolve_headline_hook_mode(request, source_summary)
    if hook_mode == "neutral":
        return compact_title
    prefix = legacy_choose_headline_hook_prefix(compact_title, request, source_summary, mode=hook_mode)
    if not prefix:
        return compact_title
    hooked_title = compact_chinese_title(compact_title, limit=max(12, 30 - len(prefix))) or compact_title
    return f"{prefix}{hooked_title}"


def legacy_style_memory_summary(request: dict[str, Any]) -> dict[str, Any]:
    memory = request_style_memory(request)
    if not memory:
        return {}
    all_sample_sources = deepcopy(safe_list(memory.get("sample_sources")))
    sample_sources = all_sample_sources[:5]
    sample_source_declared_count = len(all_sample_sources)
    sample_source_path_count = sum(1 for item in all_sample_sources if clean_text(safe_dict(item).get("path")))
    sample_source_loaded_count = sum(1 for item in all_sample_sources if path_exists(safe_dict(item).get("path")))
    slot_lines: dict[str, list[str]] = {}
    slot_guidance: dict[str, list[str]] = {}
    for slot in ("title", "subtitle", "lede", "facts", "spread", "impact", "watch"):
        lines = style_memory_slot_lines(request, slot)
        guidance = style_memory_slot_guidance(request, slot)
        if lines:
            slot_lines[slot] = lines[:2]
        if guidance:
            slot_guidance[slot] = guidance[:2]
    summary = {
        "target_band": clean_text(memory.get("target_band")),
        "voice_summary": clean_text(memory.get("voice_summary")),
        "preferred_transitions": clean_string_list(memory.get("preferred_transitions")),
        "must_land": clean_string_list(memory.get("must_land")),
        "avoid_patterns": clean_string_list(memory.get("avoid_patterns")),
        "corpus_notes": clean_string_list(memory.get("corpus_notes"))[:3],
        "slot_lines": slot_lines,
        "slot_guidance": slot_guidance,
        "sample_sources": sample_sources,
        "sample_source_declared_count": sample_source_declared_count,
        "sample_source_available_count": sample_source_loaded_count,
        "sample_source_loaded_count": sample_source_loaded_count,
        "sample_source_missing_count": max(0, sample_source_path_count - sample_source_loaded_count),
        "sample_source_runtime_mode": "curated_profile_only",
        "raw_sample_text_loaded": False,
        "corpus_derived_transitions": clean_string_list(memory.get("preferred_transitions"))[:3],
    }
    return {key: value for key, value in summary.items() if value not in ("", [], {}, None)}


def legacy_finalize_article_title(
    title: str,
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return title
    explicit_hint = clean_text(request.get("title_hint_zh")) or clean_text(request.get("title_hint"))
    if explicit_hint:
        return compact_chinese_title(explicit_hint, limit=30) or title
    custom_titles = style_memory_slot_lines(request, "title")
    if custom_titles:
        base_title = compact_chinese_title(custom_titles[0], limit=30) or title
        return legacy_apply_headline_hook(base_title, request, source_summary)
    public_topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "")
    if has_cjk(public_topic):
        base_title = compact_chinese_title(public_topic, limit=30) or title
        return legacy_apply_headline_hook(base_title, request, source_summary)
    derived = derive_chinese_title(request, analysis_brief, source_summary)
    return legacy_apply_headline_hook(derived or title, request, source_summary)


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    lead_fact = item_texts(canonical_facts, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    if lead_fact:
        zh = (
            f"{lead_fact[0]}。真正让这件事值得继续盯下去的，不只是热度，而是"
            f"{strip_terminal_punctuation(market_relevance[0]) if market_relevance else '它开始影响后面的判断和动作'}。"
        )
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(zh, en, language_mode)
    zh = f"{topic}正在从一个单点话题，慢慢变成一件需要继续追踪的事。先把已经发生的变化说清楚，再看影响会传到哪里。"
    en = f"{topic} is moving from a single headline into a story that still needs tracking. Start with the real change, then follow where the impact goes next."
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    open_questions = clean_string_list(analysis_brief.get("open_questions"))
    fact_texts = item_texts(canonical_facts, limit=3)
    not_proven_texts = item_texts(not_proven, limit=2)
    trend_texts = item_texts(trend_lines, field="detail", limit=2) or item_texts(trend_lines, field="trend", limit=2)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")

    fact_paragraph = bilingual_text(
        "先把台面上最硬的几条信息放在一起：" + join_with_semicolons(fact_texts, f"{topic}还需要更多公开信息来补全。") + "。这意味着它已经不是一句话就能带过去的热搜。",
        "Start with the hardest public facts on the table: "
        + join_with_semicolons(fact_texts, f"{topic} still needs more public detail before the picture is complete.")
        + ". At this point, the story is already bigger than a one-line trend item.",
        language_mode,
    )
    spread_paragraph = bilingual_text(
        "这件事会继续发酵，通常不是因为标题更吓人，而是因为" + join_with_semicolons(trend_texts, "讨论开始从情绪转向影响路径") + "。一旦讨论开始落到产业、预算或执行层面，它就不只是流量题了。",
        "The discussion keeps spreading not because the headline sounds louder, but because "
        + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to transmission")
        + ". Once a topic starts touching industry positioning, budgets, or execution, it stops being pure traffic.",
        language_mode,
    )
    impact_paragraph = bilingual_text(
        "真正值得盯的不是表面热度，而是它会传到谁、改变谁的判断。现在最直接的观察对象是"
        + join_with_commas(market_relevance[:3], "后续决策、行业情绪和资源分配")
        + "。这才是它从话题变成变量的地方。",
        "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
        + join_with_commas(market_relevance[:3], "follow-on decisions, industry positioning, and resource allocation")
        + ". That is where a topic stops being noise and becomes a variable.",
        language_mode,
    )
    watch_paragraph = bilingual_text(
        "接下来最该盯的不是情绪，而是这些变量："
        + join_with_semicolons(open_questions[:3], "新的公开确认、后续动作，以及市场会不会继续加码")
        + "。如果这些点落地，叙事会升级；如果迟迟落不了地，热度就可能跑在事实前面。",
        "The next useful checkpoints are "
        + join_with_semicolons(open_questions[:3], "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
        + ". If those land, the story upgrades quickly; if they do not, the heat may outrun the substance.",
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "这里最容易被说过头的地方是：" + join_with_semicolons(not_proven_texts, "不要把还在发酵的推演，当成已经落地的事实") + "。写到这里，克制本身就是质量。",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: " + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "先只说图像层真正能支撑的部分：" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections


'''

# Safe redefinitions: keep late-bound public writer logic in ASCII / unicode-escape form
# so publishable copy does not depend on terminal encoding.
def citation_ids_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> list[str]:
    citation_ids: list[str] = []
    source_id_set = set(clean_string_list(source_ids))
    for citation in citations:
        citation_source_id = clean_text(citation.get("source_id"))
        citation_id = clean_text(citation.get("citation_id"))
        if citation_source_id in source_id_set and citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
    return citation_ids


def refs_for_source_ids(citations: list[dict[str, Any]], source_ids: list[str]) -> str:
    refs = [f"[{citation_id}]" for citation_id in citation_ids_for_source_ids(citations, source_ids)]
    return "".join(refs)


def top_citation_ids(citations: list[dict[str, Any]], limit: int = 2) -> list[str]:
    citation_ids: list[str] = []
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        if citation_id and citation_id not in citation_ids:
            citation_ids.append(citation_id)
        if len(citation_ids) >= max(1, limit):
            break
    return citation_ids


def preferred_citation_ids(
    citations: list[dict[str, Any]],
    source_ids: list[str] | None = None,
    *,
    limit: int = 2,
) -> list[str]:
    matched = citation_ids_for_source_ids(citations, clean_string_list(source_ids))
    if matched:
        return matched[: max(1, limit)]
    ranked = [
        item
        for item in citations
        if clean_text(item.get("access_mode")) != "blocked" and int(item.get("source_tier", 3)) <= 1
    ]
    if not ranked:
        ranked = [item for item in citations if clean_text(item.get("access_mode")) != "blocked"]
    return top_citation_ids(ranked or citations, limit=limit)


def citation_channels_for_ids(citations: list[dict[str, Any]], citation_ids: list[str]) -> list[str]:
    channels: list[str] = []
    wanted = set(clean_string_list(citation_ids))
    for citation in citations:
        citation_id = clean_text(citation.get("citation_id"))
        channel = clean_text(citation.get("channel"))
        if citation_id in wanted and channel and channel not in channels:
            channels.append(channel)
    return channels


def join_with_semicolons(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    separator = "；" if any(has_cjk(item) for item in clean_items) or has_cjk(empty_text) else "; "
    return separator.join(clean_items)


def strip_terminal_punctuation(text: str) -> str:
    return clean_text(text).rstrip(" .;:。；，、!?！？")


def lowercase_first(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    return cleaned[:1].lower() + cleaned[1:]


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", clean_text(text)))


def localized_brief_text(text: str, mode: str) -> str:
    cleaned = clean_text(text)
    if mode != "chinese" or not cleaned:
        return cleaned
    tracked_claims = re.fullmatch(r"(\d+)\s+tracked claim\(s\) are still denied, unclear, or inference-only\.?", cleaned)
    if tracked_claims:
        return f"目前仍有{tracked_claims.group(1)}条关键判断处在未证实、被否认或仅能推演的状态"
    recent_core = re.fullmatch(r"Recent core sources are concentrated in (.+?)\.?", cleaned)
    if recent_core:
        return f"最近较高置信度的信息主要集中在{recent_core.group(1)}"
    replacements = {
        "The live tape is still being pushed by lower-confidence recent signals.": "眼下的舆论节奏，仍在被低置信度的新信号继续推着走。",
        "The current picture is still sparse.": "眼下公开信息仍然偏少，不能把结论写得太满。",
        "There is not enough clean public evidence yet to support a narrow or aggressive story line.": "目前还没有足够干净、足够公开的证据，支撑一个过窄或过猛的结论。",
    }
    return replacements.get(cleaned, cleaned)


def join_with_commas(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    if any(has_cjk(item) for item in clean_items) or has_cjk(empty_text):
        if len(clean_items) == 1:
            return clean_items[0]
        if len(clean_items) == 2:
            return f"{clean_items[0]}和{clean_items[1]}"
        return f"{'、'.join(clean_items[:-1])}和{clean_items[-1]}"
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def bilingual_heading(zh: str, en: str, mode: str) -> str:
    zh_text = clean_text(zh)
    en_text = clean_text(en)
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text} | {en_text}"
        return zh_text or en_text
    return en_text or zh_text


def bilingual_text(zh: str, en: str, mode: str) -> str:
    zh_text = str(zh or "").replace("\u200b", " ").strip()
    en_text = str(en or "").replace("\u200b", " ").strip()
    if mode == "chinese":
        return zh_text or en_text
    if mode == "bilingual":
        if zh_text and en_text:
            return f"{zh_text}\n\n{en_text}"
        return zh_text or en_text
    return en_text or zh_text


def signal_sentence(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "There are not enough fresh public signals yet to upgrade any single hint into a firm conclusion."
    parts = []
    for item in signals[:3]:
        source_name = clean_text(item.get("source_name")) or "Unknown source"
        age = clean_text(item.get("age")) or "unknown age"
        excerpt = short_excerpt(clean_text(item.get("text_excerpt")), limit=100) or "new signal"
        parts.append(f"{source_name} ({age}) said: {excerpt}")
    return "Latest signals first: " + "; ".join(parts) + "."


def image_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is attached to this draft yet."
    parts = []
    for item in images[:3]:
        source_name = clean_text(item.get("source_name")) or "Unnamed source"
        caption = short_excerpt(clean_text(item.get("caption")), limit=100) or "no machine-readable image summary"
        parts.append(f"{source_name}: {caption}")
    return "Key images kept for the article: " + "; ".join(parts) + "."


def visual_evidence_sentence(images: list[dict[str, Any]]) -> str:
    if not images:
        return "No reusable image asset is available, so this version cannot be image-first in practice."
    parts = []
    for item in images[:3]:
        role = clean_text(item.get("role")).replace("_", " ")
        status = clean_text(item.get("status")) or "unknown"
        caption = short_excerpt(clean_text(item.get("caption")), limit=110) or "no machine-readable summary"
        parts.append(f"{role}: {caption} [{status}]")
    return "Visual evidence layer: " + "; ".join(parts) + "."


def apply_must_avoid(text: str, must_avoid: list[str]) -> str:
    updated = text
    for phrase in must_avoid:
        updated = updated.replace(phrase, "")
    return updated


def derive_analysis_brief_from_digest(
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_source_ids = clean_string_list([citation.get("source_id") for citation in citations[:2]])
    canonical_facts = [
        {
            "claim_id": f"derived-confirmed-{index + 1}",
            "claim_text": text,
            "source_ids": primary_source_ids if index == 0 else [],
            "promotion_state": "core",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("confirmed"))[:4])
    ]
    not_proven = [
        {
            "claim_id": f"derived-not-proven-{index + 1}",
            "claim_text": text,
            "source_ids": [],
            "status": "unclear",
        }
        for index, text in enumerate(clean_string_list(evidence_digest.get("not_confirmed"))[:4])
    ]
    latest_signal_summary = signal_sentence(normalize_latest_signals(evidence_digest.get("latest_signals")))
    story_angles = [
        {
            "angle": "Lead with the confirmed public record before discussing faster-moving signals.",
            "risk": "Do not turn social or single-source updates into settled fact.",
        }
    ]
    if images:
        story_angles.append(
            {
                "angle": "Use saved images as supporting context, not as proof beyond what they visibly show.",
                "risk": "Treat visuals as the last public indication, not ground truth.",
            }
        )
    open_questions = clean_string_list(evidence_digest.get("next_watch_items"))[:4]
    voice_constraints = [
        "Keep facts, inference, and visual hints clearly separated.",
        "Do not write past the strongest confirmed evidence.",
    ]
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        voice_constraints.append("Some sources were blocked, so the draft should not imply the search was complete.")
    if clean_text(source_summary.get("confidence_gate")) == "shadow-heavy":
        voice_constraints.append("Shadow-only signals can raise attention, but they cannot carry the main conclusion alone.")
    misread_risks = []
    if not canonical_facts:
        misread_risks.append("The package does not yet have a strong confirmed fact to anchor the draft.")
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        misread_risks.append("Blocked or missing sources could hide confirming or contradicting evidence.")
    if images:
        misread_risks.append("Readers may overread the images if the captions are written too strongly.")
    recommended_thesis = (
        clean_text(source_summary.get("core_verdict"))
        or (clean_string_list(evidence_digest.get("confirmed")) or ["Current evidence remains incomplete."])[0]
    )
    return {
        "canonical_facts": canonical_facts,
        "not_proven": not_proven,
        "open_questions": open_questions,
        "trend_lines": [
            {
                "trend": "Latest signals",
                "detail": latest_signal_summary,
            }
        ],
        "scenario_matrix": [],
        "market_or_reader_relevance": clean_string_list(evidence_digest.get("market_relevance")),
        "story_angles": story_angles,
        "image_keep_reasons": [
            {
                "image_id": clean_text(item.get("image_id") or item.get("asset_id")),
                "reason": clean_text(item.get("caption")) or "Retained as visual context for the draft.",
            }
            for item in images[:3]
        ],
        "voice_constraints": voice_constraints,
        "recommended_thesis": recommended_thesis,
        "misread_risks": misread_risks,
    }


def brief_items_text(items: list[dict[str, Any]], fallback: str, *, field: str = "claim_text") -> str:
    texts = [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))]
    return join_with_semicolons(texts, fallback)


def item_texts(items: list[dict[str, Any]], *, field: str = "claim_text", limit: int = 3) -> list[str]:
    return [strip_terminal_punctuation(item.get(field, "")) for item in items if strip_terminal_punctuation(item.get(field, ""))][:limit]


def build_title(request: dict[str, Any], digest: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    del digest, selected_images
    language_mode = request.get("language_mode", "english")
    title_hint = clean_text(request.get("title_hint"))
    title_hint_zh = clean_text(request.get("title_hint_zh"))
    if title_hint or title_hint_zh:
        return bilingual_heading(title_hint_zh, title_hint, language_mode)
    topic = public_topic_text(request)
    if topic:
        if language_mode == "bilingual":
            return topic
        return bilingual_heading(topic, topic, language_mode)
    custom_titles = style_memory_slot_lines(request, "title")
    if custom_titles:
        return bilingual_heading(custom_titles[0], custom_titles[0], language_mode)
    fallback_titles = {
        "hot_comment": ("\u8fd9\u4ef6\u4e8b\u771f\u6b63\u503c\u5f97\u770b\u7684\u662f\u4ec0\u4e48", "What really matters in this story"),
        "deep_analysis": ("\u8fd9\u4ef6\u4e8b\u4e3a\u4ec0\u4e48\u503c\u5f97\u5173\u6ce8", "Why this story matters now"),
        "tutorial": ("\u4e09\u6b65\u770b\u61c2\u8fd9\u4ef6\u4e8b", "How to break this down in three steps"),
        "story": ("\u8fd9\u4ef6\u4e8b\u7684\u5173\u952e\u8f6c\u6298", "The turning point in this story"),
        "list": ("\u8fd9\u4ef6\u4e8b\u6700\u503c\u5f97\u770b\u7684\u4e09\u4e2a\u70b9", "Three angles worth watching here"),
        "opinion": ("\u522b\u53ea\u770b\u70ed\u5ea6\uff0c\u8981\u770b\u771f\u6b63\u7684\u53d8\u5316", "Ignore the noise and look at the real shift"),
    }
    title_zh, title_en = fallback_titles.get(resolve_article_framework(request), fallback_titles["hot_comment"])
    return bilingual_heading(title_zh, title_en, language_mode)


def build_subtitle(request: dict[str, Any], summary: dict[str, Any], selected_images: list[dict[str, Any]]) -> str:
    language_mode = request.get("language_mode", "english")
    subtitle_hint = clean_text(request.get("subtitle_hint"))
    subtitle_hint_zh = clean_text(request.get("subtitle_hint_zh"))
    if subtitle_hint or subtitle_hint_zh:
        return bilingual_text(subtitle_hint_zh, subtitle_hint, language_mode)
    custom_subtitles = style_memory_slot_lines(request, "subtitle")
    if custom_subtitles:
        return bilingual_text(custom_subtitles[0], custom_subtitles[0], language_mode)
    if request.get("draft_mode") == "image_only":
        return bilingual_text(
            "\u5148\u770b\u56fe\u91cc\u80fd\u786e\u8ba4\u4ec0\u4e48\uff0c\u518d\u51b3\u5b9a\u8fd9\u4ef6\u4e8b\u8be5\u600e\u4e48\u5199\u3002",
            "Start with what the images can genuinely support, then decide how far the story should go.",
            language_mode,
        )
    framework = resolve_article_framework(request, summary)
    if framework == "tutorial":
        return bilingual_text(
            "\u628a\u95ee\u9898\u62c6\u5f00\u8bb2\u6e05\u695a\uff0c\u6bd4\u5806\u89c2\u70b9\u66f4\u91cd\u8981\u3002",
            "Clarity matters more than volume here, so the draft breaks the problem into practical steps.",
            language_mode,
        )
    if framework == "story":
        return bilingual_text(
            "\u771f\u6b63\u503c\u5f97\u5199\u7684\uff0c\u4e0d\u53ea\u662f\u4e8b\u4ef6\u672c\u8eab\uff0c\u800c\u662f\u5b83\u8d70\u5230\u8fd9\u4e00\u6b65\u7684\u5173\u952e\u8f6c\u6298\u3002",
            "The value is not just the event itself, but the turning point that pushed it into focus.",
            language_mode,
        )
    if framework == "list":
        return bilingual_text(
            "\u522b\u6025\u7740\u4e0b\u7ed3\u8bba\uff0c\u5148\u628a\u6700\u5173\u952e\u7684\u51e0\u4e2a\u89c2\u5bdf\u70b9\u6446\u51fa\u6765\u3002",
            "Before jumping to a verdict, put the few highest-signal observations on the table.",
            language_mode,
        )
    if summary.get("source_kind") == "x_index" and selected_images:
        return bilingual_text(
            "\u70ed\u5ea6\u4f1a\u9a97\u4eba\uff0c\u771f\u6b63\u6709\u7528\u7684\u662f\u80fd\u843d\u56de\u516c\u5f00\u4fe1\u606f\u548c\u4e00\u624b\u7d20\u6750\u7684\u90a3\u90e8\u5206\u3002",
            "Heat can be misleading. What matters is the part of the story that still lands on public evidence and first-hand material.",
            language_mode,
        )
    return bilingual_text(
        "\u5148\u628a\u53d1\u751f\u4e86\u4ec0\u4e48\u8bf4\u6e05\u695a\uff0c\u518d\u770b\u8fd9\u4ef6\u4e8b\u4e3a\u4ec0\u4e48\u4f1a\u7ee7\u7eed\u53d1\u9175\u3002",
        "Start with what changed, then look at why the discussion is still gaining heat.",
        language_mode,
    )


def framework_headings(framework: str) -> list[tuple[str, str]]:
    heading_map = {
        "hot_comment": [
            ("\u4e8b\u60c5\u5148\u8bf4\u6e05\u695a", "What Changed"),
            ("\u70ed\u5ea6\u4e3a\u4ec0\u4e48\u8fd8\u5728\u6da8", "Why The Story Is Spreading"),
            ("\u4e3a\u4ec0\u4e48\u8fd9\u4e8b\u503c\u5f97\u5173\u6ce8", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "deep_analysis": [
            ("\u5148\u770b\u53d8\u5316\u672c\u8eab", "What Changed"),
            ("\u6df1\u5c42\u539f\u56e0", "The Deeper Driver"),
            ("\u5f71\u54cd\u4f1a\u4f20\u5230\u54ea\u91cc", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "tutorial": [
            ("\u6838\u5fc3\u95ee\u9898", "The Core Problem"),
            ("\u5148\u770b\u5224\u65ad\u65b9\u6cd5", "How To Read It"),
            ("\u4e09\u4e2a\u5b9e\u64cd\u52a8\u4f5c", "Three Practical Moves"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "story": [
            ("\u5173\u952e\u8f6c\u6298", "The Turning Point"),
            ("\u4e8b\u60c5\u662f\u600e\u4e48\u8d70\u5230\u8fd9\u91cc\u7684", "How The Story Reached Here"),
            ("\u8fd9\u4ef6\u4e8b\u8bf4\u660e\u4e86\u4ec0\u4e48", "Why This Matters"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "list": [
            ("\u7b2c\u4e00\u4e2a\u4fe1\u53f7", "First Signal"),
            ("\u7b2c\u4e8c\u4e2a\u4fe1\u53f7", "Second Signal"),
            ("\u7b2c\u4e09\u4e2a\u4fe1\u53f7", "Third Signal"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
        "opinion": [
            ("\u4e8b\u60c5\u5148\u8bf4\u6e05\u695a", "What Changed"),
            ("\u566a\u97f3\u4ece\u54ea\u6765", "Where The Noise Starts"),
            ("\u6211\u7684\u5224\u65ad", "The View"),
            ("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next"),
        ],
    }
    return heading_map.get(framework, heading_map["hot_comment"])


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    lead_fact = item_texts(canonical_facts, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    voice_prefix = pick_voice_prefix(request, "lede")
    longform_mode = requested_target_length_chars(request) >= 1800
    longform_mode = requested_target_length_chars(request) >= 1800
    longform_mode = requested_target_length_chars(request) >= 1800
    if lead_fact:
        zh_relevance = strip_terminal_punctuation(market_relevance[0]) if market_relevance else "\u5b83\u5f00\u59cb\u5f71\u54cd\u540e\u9762\u7684\u5224\u65ad\u548c\u52a8\u4f5c"
        zh = f"{lead_fact[0]}\u3002\u771f\u6b63\u503c\u5f97\u5f80\u4e0b\u5199\u7684\uff0c\u4e0d\u53ea\u662f\u70ed\u5ea6\uff0c\u800c\u662f{zh_relevance}\u8fd9\u6761\u7ebf\u4f1a\u600e\u4e48\u7ee7\u7eed\u4f20\u5bfc\u3002"
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(prepend_voice_prefix(voice_prefix, zh, mode="chinese"), prepend_voice_prefix(voice_prefix, en, mode="english"), language_mode)
    boundary_claim = localized_brief_text(item_texts(not_proven, limit=1)[0], language_mode) if item_texts(not_proven, limit=1) else ""
    chinese_focus = [chinese_market_focus(item) for item in market_relevance[:3] if chinese_market_focus(item)]
    if language_mode == "chinese" and boundary_claim and chinese_focus:
        zh = (
            f"\u5148\u522b\u628a\u201c{boundary_claim}\u201d\u5f53\u6210\u5df2\u7ecf\u843d\u5730\u7684\u7ed3\u8bba\u3002"
            f"\u771f\u6b63\u538b\u5230\u684c\u9762\u4e0a\u7684\uff0c\u662f{join_with_commas(chinese_focus, '\u80fd\u6e90\u3001\u6210\u672c\u548c\u5916\u90e8\u73af\u5883')}\u8fd9\u51e0\u6761\u4f20\u5bfc\u94fe\u3002"
        )
        en = (
            f"Do not treat '{boundary_claim}' as a settled outcome yet. "
            f"What actually matters for {topic} is the transmission into {join_with_commas(market_relevance[:3], 'costs, policy room, and real-world decision pressure')}."
        )
        return bilingual_text(prepend_voice_prefix(voice_prefix, zh, mode="chinese"), prepend_voice_prefix(voice_prefix, en, mode="english"), language_mode)
    zh = (
        f"\u56f4\u7ed5{topic}\uff0c\u73b0\u5728\u66f4\u503c\u5f97\u5148\u770b\u7684\uff0c\u662f"
        f"{join_with_commas(chinese_focus[:3], '\u51e0\u6761\u5df2\u7ecf\u5f00\u59cb\u53d1\u751f\u4f20\u5bfc\u7684\u5f71\u54cd\u8def\u5f84')}\u3002"
        "\u56e0\u4e3a\u771f\u6b63\u4f1a\u538b\u5230\u53f0\u9762\u4e0a\u7684\uff0c\u4ece\u6765\u4e0d\u662f\u53e3\u53f7\u672c\u8eab\uff0c\u800c\u662f\u8fd9\u4e9b\u53d8\u91cf\u600e\u4e48\u4e00\u5c42\u5c42\u5f80\u91cc\u8d70\u3002"
    )
    en = (
        f"For {topic}, the most useful starting point is "
        f"{join_with_commas(market_relevance[:3], 'the small set of transmission paths already on the table')}. "
        "The real question is not the slogan around the story, but how those variables move through decisions next."
    )
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance_raw = [localized_brief_text(item, language_mode) for item in clean_string_list(analysis_brief.get("market_or_reader_relevance"))]
    market_relevance = [chinese_market_focus(item) if language_mode == "chinese" else item for item in market_relevance_raw]
    open_questions = [localized_brief_text(item, language_mode) for item in clean_string_list(analysis_brief.get("open_questions"))]
    fact_texts = [localized_brief_text(item, language_mode) for item in item_texts(canonical_facts, limit=3)]
    not_proven_texts = [localized_brief_text(item, language_mode) for item in item_texts(not_proven, limit=2)]
    trend_texts = [
        localized_brief_text(item, language_mode)
        for item in (item_texts(trend_lines, field="detail", limit=2) or item_texts(trend_lines, field="trend", limit=2))
    ]
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")
    watch_items = preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode) if not fact_texts else open_questions[:3]

    if fact_texts:
        fact_zh = (
            "\u53f0\u9762\u4e0a\u5148\u80fd\u7ad9\u4f4f\u7684\uff0c\u4e0d\u5916\u4e4e\u8fd9\u51e0\u6761\uff1a"
            + join_with_semicolons(fact_texts, f"{topic}\u8fd8\u5728\u53d1\u5c55\u4e2d")
            + "\u3002\u5148\u628a\u8fd9\u4e9b\u6293\u7a33\uff0c\u518d\u5f80\u4e0b\u8c08\u66f4\u5927\u7684\u5224\u65ad\u3002"
        )
        fact_en = (
            "Start with the points that can already stand on the record: "
            + join_with_semicolons(fact_texts, f"{topic} is still developing")
            + ". Hold those steady first, then widen the frame."
        )
    else:
        boundary = not_proven_texts[0] if not_proven_texts else ""
        fact_zh = (
            f"\u5148\u522b\u628a\u201c{boundary}\u201d\u5f53\u6210\u5df2\u7ecf\u843d\u5730\u7684\u7ed3\u8bba\u3002"
            if boundary
            else "\u5148\u522b\u6025\u7740\u5f80\u6700\u5927\u7684\u8bdd\u4e0a\u9760\u3002"
        )
        fact_zh += (
            "\u773c\u4e0b\u66f4\u80fd\u843d\u5230\u7eb8\u9762\u4e0a\u7684\uff0c\u662f"
            + join_with_commas(market_relevance[:3], "\u51e0\u6761\u5df2\u7ecf\u5f00\u59cb\u53d1\u751f\u4f20\u5bfc\u7684\u5f71\u54cd\u8def\u5f84")
            + "\u8fd9\u51e0\u6761\u4f20\u5bfc\u7ebf\u3002"
        )
        fact_en = (
            f"Do not treat '{boundary}' as settled yet. " if boundary else "Do not rush straight to the biggest conclusion yet. "
        ) + (
            "The part that is easier to write cleanly right now is "
            + join_with_commas(market_relevance[:3], "the transmission paths already moving into view")
            + "."
        )
    fact_paragraph = bilingual_text(
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_zh, mode="chinese"),
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_en, mode="english"),
        language_mode,
    )
    spread_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "\u8fd9\u4ef6\u4e8b\u8fd8\u4f1a\u7ee7\u7eed\u53d1\u9175\uff0c\u4e0d\u53ea\u662f\u56e0\u4e3a\u70ed\u5ea6\u6ca1\u9000\uff0c\u800c\u662f\u56e0\u4e3a"
            + join_with_semicolons(trend_texts, "\u8ba8\u8bba\u5f00\u59cb\u4ece\u60c5\u7eea\u8f6c\u5411\u771f\u5b9e\u7684\u5f71\u54cd\u8def\u5f84")
            + "\u3002\u4e00\u65e6\u8ba8\u8bba\u843d\u5230\u6210\u672c\u3001\u884c\u4e1a\u6216\u6267\u884c\u5c42\u9762\uff0c\u5b83\u5c31\u4e0d\u53ea\u662f\u6d41\u91cf\u9898\u4e86\u3002",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "The discussion keeps moving not because the headline sounds louder, but because "
            + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to actual transmission")
            + ". Once the topic starts hitting costs, industry positioning, or execution, it stops being pure traffic.",
            mode="english",
        ),
        language_mode,
    )
    impact_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "\u771f\u6b63\u503c\u5f97\u76ef\u7684\uff0c\u4e0d\u662f\u8868\u9762\u70ed\u5ea6\uff0c\u800c\u662f\u5b83\u4f1a\u4f20\u5230\u8c01\u3001\u6539\u53d8\u8c01\u7684\u5224\u65ad\u3002\u73b0\u5728\u6700\u76f4\u63a5\u7684\u89c2\u5bdf\u5bf9\u8c61\u662f"
            + join_with_commas(market_relevance_raw[:3], "\u540e\u7eed\u51b3\u7b56\u3001\u884c\u4e1a\u60c5\u7eea\u548c\u8d44\u6e90\u5206\u914d")
            + "\u3002\u8fd9\u624d\u662f\u5b83\u4ece\u8bdd\u9898\u53d8\u6210\u53d8\u91cf\u7684\u5730\u65b9\u3002",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
            + join_with_commas(market_relevance_raw[:3], "follow-on decisions, industry positioning, and resource allocation")
            + ". That is where a topic stops being noise and becomes a variable.",
            mode="english",
        ),
        language_mode,
    )
    watch_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "\u63a5\u4e0b\u6765\u522b\u76ef\u60c5\u7eea\uff0c\u76ef\u8fd9\u51e0\u4ef6\u4e8b\uff1a"
            + join_with_semicolons(watch_items, "\u65b0\u7684\u516c\u5f00\u786e\u8ba4\u3001\u540e\u7eed\u52a8\u4f5c\uff0c\u4ee5\u53ca\u5e02\u573a\u4f1a\u4e0d\u4f1a\u7ee7\u7eed\u52a0\u7801")
            + "\u3002\u8fd9\u4e9b\u70b9\u8c01\u5148\u88ab\u9a8c\u8bc1\uff0c\u8c01\u5c31\u4f1a\u628a\u53d9\u4e8b\u5f80\u524d\u63a8\u4e00\u6b65\u3002",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "The next useful checkpoints are "
            + join_with_semicolons(watch_items, "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
            + ". Whichever of those gets verified first will move the story forward.",
            mode="english",
        ),
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "\u8fd9\u91cc\u6700\u5bb9\u6613\u88ab\u8bf4\u8fc7\u5934\u7684\u5730\u65b9\u662f\uff1a"
        + join_with_semicolons(not_proven_texts, "\u4e0d\u8981\u628a\u8fd8\u5728\u53d1\u9175\u7684\u63a8\u6f14\uff0c\u5f53\u6210\u5df2\u7ecf\u843d\u5730\u7684\u4e8b\u5b9e")
        + "\u3002\u5199\u5230\u8fd9\u91cc\uff0c\u514b\u5236\u672c\u8eab\u5c31\u662f\u8d28\u91cf\u3002",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "\u56fe\u50cf\u7d20\u6750\u80fd\u5e2e\u4f60\u628a\u73b0\u573a\u611f\u8865\u56de\u6765\uff0c\u4f46\u5b83\u66f4\u9002\u5408\u505a\u8865\u5145\uff0c\u4e0d\u9002\u5408\u66ff\u4ee3\u5224\u65ad\u3002\u5f53\u524d\u503c\u5f97\u4fdd\u7559\u7684\u89c6\u89c9\u7ebf\u7d22\u662f\uff1a"
        + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
        + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("\u56fe\u91cc\u80fd\u786e\u8ba4\u4ec0\u4e48", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "\u5148\u53ea\u8bf4\u56fe\u50cf\u5c42\u771f\u6b63\u80fd\u652f\u6491\u7684\u90e8\u5206\uff1a" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("\u56fe\u91cc\u4e0d\u80fd\u66ff\u4ee3\u4ec0\u4e48", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("\u63a5\u4e0b\u6765\u76ef\u4ec0\u4e48", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("\u56fe\u91cc\u80fd\u8865\u4ec0\u4e48", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections

def signal_sentence_zh(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "暂时还没有足够新的公开信号，去把任何单条线索升级成硬结论。"
    parts = []
    for item in signals[:3]:
        source_name = clean_text(item.get("source_name")) or "未知来源"
        age = clean_text(item.get("age")) or "时间未知"
        excerpt = short_excerpt(clean_text(item.get("text_excerpt")), limit=80) or "出现了新的公开线索"
        parts.append(f"{source_name}（{age}）提到：{excerpt}")
    return "最新一轮公开信号主要集中在：" + "；".join(parts) + "。"


def preferred_brief_item_text(
    item: dict[str, Any],
    *,
    mode: str,
    field: str = "claim_text",
    zh_field: str = "claim_text_zh",
) -> str:
    if mode == "chinese":
        return strip_terminal_punctuation(item.get(zh_field) or item.get(field, ""))
    return strip_terminal_punctuation(item.get(field) or item.get(zh_field, ""))


def preferred_brief_texts(
    items: list[dict[str, Any]],
    *,
    mode: str,
    field: str = "claim_text",
    zh_field: str = "claim_text_zh",
    limit: int = 3,
) -> list[str]:
    texts = [
        preferred_brief_item_text(item, mode=mode, field=field, zh_field=zh_field)
        for item in items
        if preferred_brief_item_text(item, mode=mode, field=field, zh_field=zh_field)
    ]
    return texts[:limit]


def derive_analysis_brief_from_digest(
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_source_ids = clean_string_list([citation.get("source_id") for citation in citations[:2]])
    confirmed = clean_string_list(evidence_digest.get("confirmed"))
    confirmed_zh = clean_string_list(evidence_digest.get("confirmed_zh")) or confirmed
    not_confirmed = clean_string_list(evidence_digest.get("not_confirmed"))
    not_confirmed_zh = clean_string_list(evidence_digest.get("not_confirmed_zh")) or not_confirmed
    market_relevance = clean_string_list(evidence_digest.get("market_relevance"))
    market_relevance_zh = clean_string_list(evidence_digest.get("market_relevance_zh")) or market_relevance
    latest_signals = normalize_latest_signals(evidence_digest.get("latest_signals"))

    canonical_facts = []
    for index, text in enumerate(confirmed[:4]):
        canonical_facts.append(
            {
                "claim_id": f"derived-confirmed-{index + 1}",
                "claim_text": text,
                "claim_text_zh": confirmed_zh[index] if index < len(confirmed_zh) else text,
                "source_ids": primary_source_ids if index == 0 else [],
                "promotion_state": "core",
            }
        )

    not_proven = []
    for index, text in enumerate(not_confirmed[:4]):
        not_proven.append(
            {
                "claim_id": f"derived-not-proven-{index + 1}",
                "claim_text": text,
                "claim_text_zh": not_confirmed_zh[index] if index < len(not_confirmed_zh) else text,
                "source_ids": [],
                "status": "unclear",
            }
        )

    open_questions = clean_string_list(evidence_digest.get("next_watch_items"))[:4]
    open_questions_zh = [chinese_watch_item(item) for item in market_relevance_zh if chinese_watch_item(item)][:4]
    if not open_questions_zh and not_confirmed_zh:
        open_questions_zh = [f"围绕“{not_confirmed_zh[0]}”的市场想象会不会继续跑在事实前面"]

    voice_constraints = [
        "Keep facts, inference, and visual hints clearly separated.",
        "Do not write past the strongest confirmed evidence.",
    ]
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        voice_constraints.append("Some sources were blocked, so the draft should not imply the search was complete.")
    if clean_text(source_summary.get("confidence_gate")) == "shadow-heavy":
        voice_constraints.append("Shadow-only signals can raise attention, but they cannot carry the main conclusion alone.")

    misread_risks = []
    if not canonical_facts:
        misread_risks.append("The package does not yet have a strong confirmed fact to anchor the draft.")
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        misread_risks.append("Blocked or missing sources could hide confirming or contradicting evidence.")
    if images:
        misread_risks.append("Readers may overread the images if the captions are written too strongly.")

    recommended_thesis = clean_text(source_summary.get("core_verdict")) or (confirmed or ["Current evidence remains incomplete."])[0]
    recommended_thesis_zh = (confirmed_zh or market_relevance_zh or ["目前公开证据还不够完整。"])[0]

    story_angles = [
        {
            "angle": "Lead with the confirmed public record before discussing faster-moving signals.",
            "angle_zh": "先把已经站住的公开记录摆出来，再谈跑得更快的新信号。",
            "risk": "Do not turn social or single-source updates into settled fact.",
            "risk_zh": "不要把社交媒体或单一来源更新直接写成既成事实。",
        }
    ]
    if images:
        story_angles.append(
            {
                "angle": "Use saved images as supporting context, not as proof beyond what they visibly show.",
                "angle_zh": "图片只能做辅助语境，不能替代它本来没有证明的东西。",
                "risk": "Treat visuals as the last public indication, not ground truth.",
                "risk_zh": "视觉材料最多是最后一层公开迹象，不是现场真相本身。",
            }
        )

    return {
        "canonical_facts": canonical_facts,
        "not_proven": not_proven,
        "open_questions": open_questions,
        "open_questions_zh": open_questions_zh,
        "trend_lines": [
            {
                "trend": "Latest signals",
                "trend_zh": "最新信号",
                "detail": signal_sentence(latest_signals),
                "detail_zh": signal_sentence_zh(latest_signals),
            }
        ],
        "scenario_matrix": [],
        "market_or_reader_relevance": market_relevance,
        "market_or_reader_relevance_zh": market_relevance_zh,
        "story_angles": story_angles,
        "image_keep_reasons": [
            {
                "image_id": clean_text(item.get("image_id") or item.get("asset_id")),
                "reason": clean_text(item.get("caption")) or "Retained as visual context for the draft.",
            }
            for item in images[:3]
        ],
        "voice_constraints": voice_constraints,
        "recommended_thesis": recommended_thesis,
        "recommended_thesis_zh": recommended_thesis_zh,
        "misread_risks": misread_risks,
    }


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    not_proven = safe_list(analysis_brief.get("not_proven"))
    lead_fact = preferred_brief_texts(canonical_facts, mode=language_mode, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    voice_prefix = pick_voice_prefix(request, "lede")
    if lead_fact:
        zh_relevance = strip_terminal_punctuation(market_relevance[0]) if market_relevance else "它开始影响后面的判断和动作"
        zh = f"{lead_fact[0]}。真正值得往下写的，不只是热度，而是{zh_relevance}这条线会怎么继续传导。"
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, zh, mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    boundary_claims = preferred_brief_texts(not_proven, mode=language_mode, limit=1)
    boundary_claim = boundary_claims[0] if boundary_claims else ""
    chinese_focus = [chinese_market_focus(item) for item in market_relevance[:3] if chinese_market_focus(item)]
    if language_mode == "chinese" and boundary_claim and chinese_focus:
        zh = (
            f"先别把“{boundary_claim}”当成已经落地的结论。"
            f"真正压到桌面上的，是{join_with_commas(chinese_focus, '能源、成本和外部环境')}这几条传导链。"
        )
        en = (
            f"Do not treat '{boundary_claim}' as a settled outcome yet. "
            f"What actually matters for {topic} is the transmission into {join_with_commas(market_relevance[:3], 'costs, policy room, and real-world decision pressure')}."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, zh, mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    zh = (
        f"围绕{topic}，现在更值得先看的，是"
        f"{join_with_commas(chinese_focus[:3], '几条已经开始发生传导的影响路径')}。"
        "因为真正会压到台面上的，从来不是口号本身，而是这些变量怎么一层层往里走。"
    )
    en = (
        f"For {topic}, the most useful starting point is "
        f"{join_with_commas(market_relevance[:3], 'the small set of transmission paths already on the table')}. "
        "The real question is not the slogan around the story, but how those variables move through decisions next."
    )
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance_raw = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    market_relevance = [chinese_market_focus(item) if language_mode == "chinese" else item for item in market_relevance_raw]
    open_questions = (
        (clean_string_list(analysis_brief.get("open_questions_zh")) or clean_string_list(analysis_brief.get("open_questions")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("open_questions")) or clean_string_list(analysis_brief.get("open_questions_zh")))
    )
    fact_texts = preferred_brief_texts(canonical_facts, mode=language_mode, limit=3)
    not_proven_texts = preferred_brief_texts(not_proven, mode=language_mode, limit=2)
    trend_texts = []
    for item in trend_lines:
        text = localized_brief_text(
            preferred_brief_item_text(item, mode=language_mode, field="detail", zh_field="detail_zh"),
            language_mode,
        )
        if text:
            trend_texts.append(text)
        if len(trend_texts) >= 2:
            break
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")
    if language_mode == "chinese" and not fact_texts:
        watch_items = preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)
    else:
        watch_items = open_questions[:3] or preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)

    if fact_texts:
        fact_zh = (
            "台面上先能站住的，不外乎这几条："
            + join_with_semicolons(fact_texts, f"{topic}还在发展中")
            + "。先把这些抓稳，再往下谈更大的判断。"
        )
        fact_en = (
            "Start with the points that can already stand on the record: "
            + join_with_semicolons(fact_texts, f"{topic} is still developing")
            + ". Hold those steady first, then widen the frame."
        )
    else:
        boundary = not_proven_texts[0] if not_proven_texts else ""
        fact_zh = f"先别把“{boundary}”当成已经落地的结论。" if boundary else "先别急着往最大的结论上靠。"
        fact_zh += "眼下更能落到纸面上的，是" + join_with_commas(market_relevance[:3], "几条已经开始发生传导的影响路径") + "这几条传导线。"
        fact_en = (
            f"Do not treat '{boundary}' as settled yet. " if boundary else "Do not rush straight to the biggest conclusion yet. "
        ) + ("The part that is easier to write cleanly right now is " + join_with_commas(market_relevance[:3], "the transmission paths already moving into view") + ".")

    fact_paragraph = bilingual_text(
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_zh, mode="chinese"),
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_en, mode="english"),
        language_mode,
    )
    spread_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "这件事还会继续发酵，不只是因为热度没退，而是因为"
            + join_with_semicolons(trend_texts, "讨论开始从情绪转向真实的影响路径")
            + "。一旦讨论落到成本、行业或执行层面，它就不只是流量题了。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "The discussion keeps moving not because the headline sounds louder, but because "
            + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to actual transmission")
            + ". Once the topic starts hitting costs, industry positioning, or execution, it stops being pure traffic.",
            mode="english",
        ),
        language_mode,
    )
    impact_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "真正值得盯的，不是表面热度，而是它会传到谁、改变谁的判断。现在最直接的观察对象是"
            + join_with_commas(market_relevance_raw[:3], "后续决策、行业情绪和资源分配")
            + "。这才是它从话题变成变量的地方。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
            + join_with_commas(market_relevance_raw[:3], "follow-on decisions, industry positioning, and resource allocation")
            + ". That is where a topic stops being noise and becomes a variable.",
            mode="english",
        ),
        language_mode,
    )
    watch_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "接下来别盯情绪，盯这几件事：" + join_with_semicolons(watch_items, "新的公开确认、后续动作，以及市场会不会继续加码") + "。这些点谁先被验证，谁就会把叙事往前推一步。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "The next useful checkpoints are "
            + join_with_semicolons(watch_items, "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
            + ". Whichever of those gets verified first will move the story forward.",
            mode="english",
        ),
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "这里最容易被说过头的地方是："
        + join_with_semicolons(not_proven_texts, "不要把还在发酵的推演，当成已经落地的事实")
        + "。写到这里，克制本身就是质量。",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
        + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "先只说图像层真正能支撑的部分：" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections


def build_sections(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    effective_brief = safe_dict(analysis_brief) or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        images,
    )
    return build_sections_from_brief(request, source_summary, citations, images, effective_brief)


def build_draft_claim_map(citations: list[dict[str, Any]], analysis_brief: dict[str, Any]) -> list[dict[str, Any]]:
    claim_map: list[dict[str, Any]] = []
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    recommended_thesis = clean_text(analysis_brief.get("recommended_thesis"))
    thesis_sources = clean_string_list(safe_dict(canonical_facts[0]).get("source_ids")) if canonical_facts else []
    thesis_citation_ids = preferred_citation_ids(citations, thesis_sources)
    if recommended_thesis:
        claim_map.append(
            {
                "claim_label": "thesis",
                "claim_text": recommended_thesis,
                "source_ids": thesis_sources,
                "citation_ids": thesis_citation_ids,
                "citation_channels": citation_channels_for_ids(citations, thesis_citation_ids),
                "support_level": "core" if thesis_sources else "derived" if thesis_citation_ids else "shadow-heavy",
            }
        )
    for item in canonical_facts[:3]:
        source_ids = clean_string_list(item.get("source_ids"))
        citation_ids = preferred_citation_ids(citations, source_ids)
        claim_map.append(
            {
                "claim_label": clean_text(item.get("claim_id")) or "canonical_fact",
                "claim_text": clean_text(item.get("claim_text")),
                "source_ids": source_ids,
                "citation_ids": citation_ids,
                "citation_channels": citation_channels_for_ids(citations, citation_ids),
                "support_level": clean_text(item.get("promotion_state")) or "core",
            }
        )
    for item in safe_list(analysis_brief.get("not_proven"))[:2]:
        source_ids = clean_string_list(item.get("source_ids"))
        citation_ids = preferred_citation_ids(citations, source_ids)
        claim_map.append(
            {
                "claim_label": clean_text(item.get("claim_id")) or "not_proven",
                "claim_text": clean_text(item.get("claim_text")),
                "source_ids": source_ids,
                "citation_ids": citation_ids,
                "citation_channels": citation_channels_for_ids(citations, citation_ids),
                "support_level": clean_text(item.get("status")) or "unclear",
            }
        )
    return [item for item in claim_map if clean_text(item.get("claim_text"))]


def build_style_profile_applied(request: dict[str, Any]) -> dict[str, Any]:
    profile_status = safe_dict(request.get("feedback_profile_status"))
    applied_paths = clean_string_list(request.get("applied_feedback_profiles")) or clean_string_list(profile_status.get("applied_paths"))
    constraints = {
        "must_include": clean_string_list(request.get("must_include")),
        "must_avoid": clean_string_list(request.get("must_avoid")),
        "personal_phrase_bank": clean_string_list(request.get("personal_phrase_bank")),
    }
    memory_summary = style_memory_summary(request)
    return {
        "applied_paths": applied_paths,
        "global_profile_applied": bool(profile_status.get("global_exists")),
        "topic_profile_applied": bool(profile_status.get("topic_exists")),
        "constraints": constraints,
        "style_memory": memory_summary,
        "effective_request": {
            "language_mode": clean_text(request.get("language_mode")),
            "draft_mode": clean_text(request.get("draft_mode")),
            "image_strategy": clean_text(request.get("image_strategy")),
            "tone": clean_text(request.get("tone")),
            "target_length_chars": int(request.get("target_length_chars", 0) or 0),
            "max_images": int(request.get("max_images", 0) or 0),
            "human_signal_ratio": int(request.get("human_signal_ratio", 0) or 0),
            "humanization_level": clean_text(request.get("humanization_level")),
            "headline_hook_mode": normalize_headline_hook_mode(request.get("headline_hook_mode")),
            "headline_hook_prefixes": clean_string_list(request.get("headline_hook_prefixes")),
            "personal_phrase_bank": constraints["personal_phrase_bank"],
            "must_include": constraints["must_include"],
            "must_avoid": constraints["must_avoid"],
            "style_memory": memory_summary,
        },
    }


def build_writer_risk_notes(analysis_brief: dict[str, Any], source_summary: dict[str, Any]) -> list[str]:
    notes = clean_string_list(analysis_brief.get("misread_risks"))
    if int(source_summary.get("blocked_source_count", 0) or 0) > 0:
        notes.append("Some sources were blocked, so the writer must avoid treating the package as fully checked.")
    if not notes:
        notes.append("The main remaining writer risk is sounding more certain than the evidence allows.")
    return notes[:5]

def build_body_markdown(title: str, subtitle: str, sections: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", subtitle]
    for section in sections:
        lines.extend(["", f"## {section.get('heading', '')}", section.get("paragraph", "")])
    return "\n".join(lines).strip() + "\n"


def build_article_markdown(
    title: str,
    subtitle: str,
    lede: str,
    sections: list[dict[str, Any]],
    images: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    language_mode: str = "english",
) -> str:
    del title
    lines: list[str] = []
    if clean_text(subtitle):
        lines.extend([subtitle, ""])
    if clean_text(lede):
        lines.extend([f"> {lede}", ""])
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in images:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)

    def emit_images(placement: str) -> None:
        for item in images_by_placement.get(placement, []):
            if clean_text(item.get("embed_markdown")):
                lines.append(item["embed_markdown"])
                caption = clean_text(item.get("caption"))
                if caption:
                    lines.append(f"_{caption}_")
                    lines.append("")

    emit_images("after_lede")
    for index, section in enumerate(sections, start=1):
        lines.append(f"## {section.get('heading', '')}")
        lines.append(section.get("paragraph", ""))
        lines.append("")
        emit_images(f"after_section_{index}")
    emit_images("appendix")

    source_heading = "来源" if clean_text(language_mode) == "chinese" else "Sources"
    lines.extend([f"## {source_heading}", ""])
    for item in citations:
        lines.append(
            f"- {item.get('citation_id', '')} | {item.get('source_name', '')} | "
            f"{item.get('url', '') or 'no url'}"
        )
    if citations:
        lines[-len(citations) :] = [render_citation_markdown(item) for item in citations]
    if not citations:
        lines.append("- None")
    return "\n".join(lines).strip() + "\n"


def citation_short_date(value: Any) -> str:
    parsed = parse_datetime(value, fallback=None)
    if parsed is not None:
        return parsed.date().isoformat()
    return clean_text(value)


def render_citation_markdown(citation: dict[str, Any]) -> str:
    title = clean_text(citation.get("title") or citation.get("excerpt") or citation.get("source_name") or citation.get("citation_id"))
    source_name = clean_text(citation.get("source_name"))
    published_at = citation_short_date(citation.get("published_at") or citation.get("observed_at"))
    url = clean_text(citation.get("url"))
    meta = " | ".join(item for item in (source_name, published_at) if item)
    line = f"- [{title}]({url})" if url else f"- {title}"
    if meta:
        line += f" | {meta}"
    return line


def append_source_limit_note(article_markdown: str, source_summary: dict[str, Any], language_mode: str = "english") -> str:
    blocked_source_count = int(source_summary.get("blocked_source_count", 0) or 0)
    if blocked_source_count <= 0:
        return article_markdown
    if "inaccessible" in article_markdown.lower() or "blocked" in article_markdown.lower():
        return article_markdown
    if clean_text(language_mode) == "chinese":
        note = "- 注：索引时仍有部分相关来源不可访问，因此公开信息面可能还不完整。\n"
        marker = "## 来源\n\n"
    else:
        note = "- Note: Some relevant sources were inaccessible at indexing time, so the public record may still be incomplete.\n"
        marker = "## Sources\n\n"
    if marker in article_markdown:
        return article_markdown.replace(marker, marker + note, 1)
    return article_markdown.rstrip() + f"\n\n{marker}" + note


def body_refresh_signature(images: list[dict[str, Any]], draft_mode: str) -> list[tuple[str, str, str, str]]:
    signature: list[tuple[str, str, str, str]] = []
    include_status = draft_mode == "image_only"
    for item in images[:3]:
        signature.append(
            (
                clean_text(item.get("source_name")),
                clean_text(item.get("caption")),
                clean_text(item.get("role")),
                clean_text(item.get("status")) if include_status else "",
            )
        )
    return signature


def should_rebuild_body_for_image_refresh(
    article_package: dict[str, Any],
    previous_images: list[dict[str, Any]],
    next_images: list[dict[str, Any]],
) -> bool:
    if article_package.get("manual_body_override"):
        return False
    render_context = safe_dict(article_package.get("render_context"))
    if not render_context:
        return False
    if not safe_list(article_package.get("sections") or article_package.get("body_sections")):
        return True
    request_context = safe_dict(render_context.get("request"))
    draft_mode = clean_text(request_context.get("draft_mode"))
    return body_refresh_signature(previous_images, draft_mode) != body_refresh_signature(next_images, draft_mode)


def refresh_article_package(
    article_package: dict[str, Any],
    must_avoid: list[str] | None = None,
    *,
    rebuild_body: bool = True,
) -> dict[str, Any]:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    citations = safe_list(article_package.get("citations"))
    render_context = safe_dict(article_package.get("render_context"))
    request_context = safe_dict(render_context.get("request"))
    section_must_avoid = clean_string_list(must_avoid if must_avoid is not None else request_context.get("must_avoid"))
    should_refresh_body = rebuild_body or not safe_list(article_package.get("sections") or article_package.get("body_sections"))
    if render_context and not article_package.get("manual_body_override") and should_refresh_body:
        sections = build_sections(
            request_context,
            safe_dict(render_context.get("source_summary")),
            safe_dict(render_context.get("evidence_digest")),
            citations,
            images,
            safe_dict(render_context.get("analysis_brief")),
        )
        article_package["sections"] = deepcopy(sections)
        article_package["body_sections"] = deepcopy(sections)
        article_package["lede"] = build_public_lede(
            request_context,
            safe_dict(render_context.get("source_summary")),
            safe_dict(render_context.get("analysis_brief")),
        )
        article_package["body_markdown"] = apply_must_avoid(
            build_body_markdown(title, subtitle, sections),
            section_must_avoid,
        )
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    lede = clean_text(article_package.get("lede"))
    article_package["image_blocks"] = deepcopy(images)
    article_package["selected_images"] = deepcopy(images)
    if not article_package.get("manual_article_override"):
        article_package["article_markdown"] = apply_must_avoid(
            build_article_markdown(
                title,
                subtitle,
                lede,
                sections,
                images,
                citations,
                clean_text(request_context.get("language_mode")),
            ),
            section_must_avoid,
        )
        article_package["article_markdown"] = append_source_limit_note(
            article_package["article_markdown"],
            safe_dict(render_context.get("source_summary")),
            clean_text(request_context.get("language_mode")),
        )
    request_context = safe_dict(render_context.get("request"))
    source_summary = safe_dict(render_context.get("source_summary"))
    article_package["article_framework"] = resolve_article_framework(request_context, source_summary)
    article_package["public_topic"] = public_topic_text(request_context, clean_text(source_summary.get("topic")) or "article-topic")
    article_package["publishability_checks"] = build_publishability_checks(title, subtitle, lede, sections)
    article_package["draft_metrics"] = draft_metrics(article_package.get("body_markdown", ""), images, citations)
    article_package["char_count"] = article_package["draft_metrics"]["char_count"]
    article_package["verification"] = {
        "has_visual_evidence": bool(images),
        "has_local_image": any(clean_text(item.get("status")) == "local_ready" for item in images),
        "blocked_images_labeled": all(
            clean_text(item.get("access_mode")) != "blocked" or "blocked" in clean_text(item.get("caption")).lower()
            for item in images
        ),
    }
    return article_package


def is_remote_target(value: Any) -> bool:
    text = clean_text(value)
    return text.startswith(("http://", "https://", "file://"))


def safe_asset_filename(index: int, source_name: str, remote_url: str) -> str:
    parsed = urllib_parse.urlparse(clean_text(remote_url))
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".img"
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in clean_text(source_name)).strip("-") or "asset"
    return f"{index:02d}-{slug[:48]}{suffix}"


def fetch_remote_asset(remote_url: str, destination: Path) -> bool:
    try:
        if clean_text(remote_url).startswith("file://"):
            parsed = urllib_parse.urlparse(remote_url)
            source_path = Path(urllib_request.url2pathname(parsed.path))
            if not source_path.exists():
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source_path.read_bytes())
            return True
        request = urllib_request.Request(remote_url, headers={"User-Agent": "Codex-ArticleWorkflow/1.0"})
        with urllib_request.urlopen(request, timeout=20) as response:
            data = response.read()
        if not data:
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return True
    except (TimeoutError, OSError, urllib_error.URLError, ValueError):
        return False


def localize_selected_images(article_package: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    selected_images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    asset_output_dir = clean_text(request.get("asset_output_dir"))
    if not selected_images or not asset_output_dir or not request.get("download_remote_images", True):
        localization = {
            "asset_output_dir": asset_output_dir,
            "downloaded_count": 0,
            "failed_count": 0,
            "downloaded_assets": [],
            "failed_assets": [],
        }
        article_package["asset_localization"] = localization
        refresh_article_package(article_package, request.get("must_avoid", []), rebuild_body=False)
        return localization

    previous_images = deepcopy(selected_images)
    asset_dir = Path(asset_output_dir)
    downloaded_assets: list[str] = []
    failed_assets: list[str] = []
    for index, item in enumerate(selected_images, start=1):
        current_path = clean_text(item.get("path"))
        if current_path and path_exists(current_path):
            continue
        remote_url = ""
        for candidate in (
            item.get("path"),
            item.get("render_target"),
            item.get("embed_target"),
            item.get("source_url"),
        ):
            if is_remote_target(candidate):
                remote_url = clean_text(candidate)
                break
        if not remote_url:
            continue
        destination = asset_dir / safe_asset_filename(index, item.get("source_name", ""), remote_url)
        if fetch_remote_asset(remote_url, destination):
            local_path = str(destination.resolve())
            item["path"] = local_path
            item["render_target"] = local_path
            item["embed_target"] = normalize_local_path(local_path)
            item["status"] = "local_ready"
            item["localized_from"] = remote_url
            item["embed_markdown"] = f"![{clean_text(item.get('image_id'))}]({normalize_local_path(local_path)})"
            downloaded_assets.append(local_path)
        else:
            failed_assets.append(remote_url)
    article_package["image_blocks"] = deepcopy(selected_images)
    article_package["selected_images"] = deepcopy(selected_images)
    article_package["asset_localization"] = {
        "asset_output_dir": str(asset_dir),
        "downloaded_count": len(downloaded_assets),
        "failed_count": len(failed_assets),
        "downloaded_assets": downloaded_assets,
        "failed_assets": failed_assets,
    }
    refresh_article_package(
        article_package,
        request.get("must_avoid", []),
        rebuild_body=should_rebuild_body_for_image_refresh(article_package, previous_images, selected_images),
    )
    return article_package["asset_localization"]


def preview_src(render_target: str) -> str:
    target = clean_text(render_target)
    if not target:
        return ""
    if target.startswith(("http://", "https://", "file://")):
        return target
    path = Path(target)
    try:
        if path.exists():
            return path.resolve().as_uri()
    except OSError:
        return target
    return target


def paragraph_blocks(text: str) -> list[str]:
    blocks = [clean_text(block) for block in str(text or "").split("\n\n")]
    return [block for block in blocks if block]


def build_article_preview_html(article_package: dict[str, Any]) -> str:
    title = clean_text(article_package.get("title"))
    subtitle = clean_text(article_package.get("subtitle"))
    lede = clean_text(article_package.get("lede"))
    language_mode = clean_text(article_package.get("language_mode"))
    sections = safe_list(article_package.get("sections") or article_package.get("body_sections"))
    images = safe_list(article_package.get("selected_images") or article_package.get("image_blocks"))
    citations = safe_list(article_package.get("citations"))
    images_by_placement: dict[str, list[dict[str, Any]]] = {}
    for item in images:
        images_by_placement.setdefault(clean_text(item.get("placement")) or "appendix", []).append(item)

    def render_images(placement: str) -> str:
        chunks: list[str] = []
        for item in images_by_placement.get(placement, []):
            src = preview_src(item.get("render_target") or item.get("embed_target") or item.get("path") or item.get("source_url"))
            if not src:
                continue
            caption = clean_text(item.get("caption"))
            source_name = clean_text(item.get("source_name"))
            status = clean_text(item.get("status"))
            meta = " | ".join([part for part in [source_name, status] if part])
            chunks.append(
                "<figure>"
                f"<img src=\"{escape(src)}\" alt=\"{escape(caption or source_name or 'image')}\" />"
                f"<figcaption>{escape(caption)}{' | ' + escape(meta) if meta else ''}</figcaption>"
                "</figure>"
            )
        return "".join(chunks)

    section_html: list[str] = []
    for index, section in enumerate(sections, start=1):
        paragraphs = "".join(f"<p>{escape(block)}</p>" for block in paragraph_blocks(section.get("paragraph", "")))
        section_html.append(f"<section><h2>{escape(clean_text(section.get('heading')))}</h2>{paragraphs}{render_images(f'after_section_{index}')}</section>")

    citations_html = "".join(
        f"<li><strong>{escape(clean_text(item.get('citation_id')))}</strong> {escape(clean_text(item.get('source_name')))}"
        f" <a href=\"{escape(clean_text(item.get('url')))}\">{escape(clean_text(item.get('url')))}</a></li>"
        for item in citations
        if clean_text(item.get("source_name")) or clean_text(item.get("url"))
    )
    source_heading = "来源" if language_mode == "chinese" else "Sources"
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\" />"
        f"<title>{escape(title or 'Article Preview')}</title>"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.7;color:#1d1d1f;background:#faf8f2;}"
        "h1,h2{line-height:1.25;} .subtitle{color:#555;margin-bottom:24px;} blockquote{border-left:4px solid #c8b27d;padding:8px 16px;background:#fffaf0;margin:20px 0;}"
        "figure{margin:24px 0;} img{max-width:100%;height:auto;border-radius:10px;border:1px solid #ddd;} figcaption{font-size:14px;color:#555;margin-top:8px;}"
        "section{margin:28px 0;} a{color:#0b57d0;word-break:break-all;}"
        "</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        f"<div class=\"subtitle\">{escape(subtitle)}</div>"
        f"<blockquote>{escape(lede)}</blockquote>"
        f"{render_images('after_lede')}"
        f"{''.join(section_html)}"
        f"{render_images('appendix')}"
        f"<section><h2>{escape(source_heading)}</h2><ol>"
        f"{citations_html or '<li>None</li>'}"
        "</ol></section></body></html>"
    )


def draft_metrics(body_markdown: str, images: list[dict[str, Any]], citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "char_count": len(clean_text(body_markdown).replace(" ", "")),
        "section_count": body_markdown.count("\n## "),
        "image_count": len(images),
        "citation_count": len(citations),
    }


PUBLISHABILITY_BANNED_PHRASES = [
    "best writer-safe thesis",
    "built from the current indexed result",
    "what is confirmed and what still is not",
    "confirmed and not confirmed",
    "story angles",
    "images and screenshots",
    "boundaries and open questions",
    "this version is image-first",
    "\u5f53\u524d\u6700\u7a33\u59a5\u7684\u5199\u6cd5",
    "\u8fd9\u7248\u5185\u5bb9\u57fa\u4e8e\u5f53\u524d\u7d22\u5f15\u7ed3\u679c\u751f\u6210",
    "\u54ea\u4e9b\u5df2\u7ecf\u786e\u8ba4",
    "\u54ea\u4e9b\u4ecd\u672a\u786e\u8ba4",
    "\u53ef\u5199\u89d2\u5ea6",
    "\u8fb9\u754c\u4e0e\u5f85\u786e\u8ba4\u70b9",
]


def build_publishability_checks(
    title: str,
    subtitle: str,
    lede: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    fields = {
        "title": clean_text(title),
        "subtitle": clean_text(subtitle),
        "lede": clean_text(lede),
    }
    for index, section in enumerate(sections, start=1):
        fields[f"section_{index}_heading"] = clean_text(section.get("heading"))
        fields[f"section_{index}_paragraph"] = clean_text(section.get("paragraph"))
    for field_name, value in fields.items():
        lowered = value.lower()
        for phrase in PUBLISHABILITY_BANNED_PHRASES:
            if phrase.lower() in lowered:
                matches.append({"field": field_name, "phrase": phrase})
        if field_name == "title" and re.search(
            r"(36kr|36\u6c2a|\u9996\u53d1|\u72ec\u5bb6)",
            lowered,
        ):
            if not any(
                item.get("field") == "title" and item.get("phrase") == "source_brand_leakage"
                for item in matches
            ):
                matches.append({"field": field_name, "phrase": "source_brand_leakage"})
        if field_name == "title" and re.search(r"(36kr|36氪|首发|独家)", lowered):
            matches.append({"field": field_name, "phrase": "source_brand_leakage"})
    deduped_matches: list[dict[str, str]] = []
    seen_match_keys: set[tuple[str, str]] = set()
    for item in matches:
        key = (clean_text(item.get("field")), clean_text(item.get("phrase")))
        if key in seen_match_keys:
            continue
        seen_match_keys.add(key)
        deduped_matches.append(item)
    matches = deduped_matches
    return {
        "passed": not matches,
        "match_count": len(matches),
        "matches": matches,
    }


def build_report_markdown(article_package: dict[str, Any]) -> str:
    lines = [article_package.get("article_markdown", "").rstrip(), "", "## Image Assets"]
    for item in safe_list(article_package.get("selected_images") or article_package.get("image_blocks")):
        lines.append(f"- {item.get('asset_id') or item.get('image_id', '')} | {item.get('source_name', '')} | {item.get('status', '')}")
        lines.append(f"  Status: {item.get('status', '') or 'unknown'}")
        lines.append(f"  Caption: {item.get('caption', '')}")
        lines.append(f"  Path: {item.get('path', '') or 'none'}")
        lines.append(f"  Source URL: {item.get('source_url', '') or 'none'}")
    if not safe_list(article_package.get("selected_images") or article_package.get("image_blocks")):
        lines.append("- None")
    lines.extend(["", "## Citations"])
    for item in safe_list(article_package.get("citations")):
        lines.append(f"- {item.get('citation_id', '')} | {item.get('source_name', '')} | {item.get('channel', '')}")
        lines.append(f"  URL: {item.get('url', '') or 'none'}")
        lines.append(f"  Excerpt: {item.get('excerpt', '') or 'none'}")
    if not safe_list(article_package.get("citations")):
        lines.append("- None")
    lines.extend(["", "## Draft Thesis", clean_text(article_package.get("draft_thesis")) or "None"])
    lines.extend(["", "## Draft Claim Map"])
    for item in safe_list(article_package.get("draft_claim_map")):
        lines.append(
            f"- {clean_text(item.get('claim_label'))}: {clean_text(item.get('claim_text'))} | "
            f"citations: {', '.join(clean_string_list(item.get('citation_ids'))) or 'none'} | "
            f"support: {clean_text(item.get('support_level')) or 'unknown'}"
        )
    if not safe_list(article_package.get("draft_claim_map")):
        lines.append("- None")
    lines.extend(["", "## Writer Risk Notes"])
    for item in clean_string_list(article_package.get("writer_risk_notes")):
        lines.append(f"- {item}")
    if not clean_string_list(article_package.get("writer_risk_notes")):
        lines.append("- None")
    publishability_checks = safe_dict(article_package.get("publishability_checks"))
    if publishability_checks:
        lines.extend(
            [
                "",
                "## Publishability Checks",
                f"- Passed: {'yes' if publishability_checks.get('passed') else 'no'}",
                f"- Match count: {int(publishability_checks.get('match_count', 0) or 0)}",
            ]
        )
        for item in safe_list(publishability_checks.get("matches")):
            lines.append(f"- {clean_text(item.get('field'))}: {clean_text(item.get('phrase'))}")
    localization = safe_dict(article_package.get("asset_localization"))
    if localization:
        lines.extend(
            [
                "",
                "## Asset Localization",
                f"- Asset directory: {clean_text(localization.get('asset_output_dir')) or 'none'}",
                f"- Downloaded: {int(localization.get('downloaded_count', 0) or 0)}",
                f"- Failed: {int(localization.get('failed_count', 0) or 0)}",
            ]
        )
    profile_status = safe_dict(article_package.get("feedback_profile_status"))
    if profile_status:
        applied_paths = clean_string_list(profile_status.get("applied_paths"))
        lines.extend(
            [
                "",
                "## Feedback Profiles",
                f"- Profile directory: {clean_text(profile_status.get('profile_dir')) or 'none'}",
                f"- Applied now: {', '.join(applied_paths) if applied_paths else 'none'}",
                f"- Global defaults: {'saved' if profile_status.get('global_exists') else 'not saved yet'} | {clean_text(profile_status.get('global_profile_path')) or 'none'}",
                f"- Topic defaults: {'saved' if profile_status.get('topic_exists') else 'not saved yet'} | {clean_text(profile_status.get('topic_profile_path')) or 'none'}",
            ]
        )
    for note in safe_list(article_package.get("editor_notes")):
        lines.append(f"- {note}")
    return "\n".join(lines).strip() + "\n"


def assemble_article_package(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    evidence_digest: dict[str, Any],
    citations: list[dict[str, Any]],
    image_candidates: list[dict[str, Any]],
    analysis_brief: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected_images = build_selected_images(image_candidates, request)
    effective_analysis_brief = safe_dict(analysis_brief) or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        selected_images,
    )
    title = finalize_article_title(build_title(request, evidence_digest, selected_images), request, effective_analysis_brief, source_summary)
    subtitle = build_subtitle(request, source_summary, selected_images)
    sections = build_sections(request, source_summary, evidence_digest, citations, selected_images, effective_analysis_brief)
    body_markdown = apply_must_avoid(build_body_markdown(title, subtitle, sections), request.get("must_avoid", []))
    lede = build_public_lede(request, source_summary, effective_analysis_brief)
    article_markdown = apply_must_avoid(
        build_article_markdown(
            title,
            subtitle,
            lede,
            sections,
            selected_images,
            citations,
            clean_text(request.get("language_mode")),
        ),
        request.get("must_avoid", []),
    )
    article_markdown = append_source_limit_note(article_markdown, source_summary, clean_text(request.get("language_mode")))
    if clean_text(request.get("language_mode")) == "chinese":
        draft_thesis = clean_text(effective_analysis_brief.get("recommended_thesis_zh")) or clean_text(
            effective_analysis_brief.get("recommended_thesis")
        ) or clean_text(source_summary.get("core_verdict"))
    else:
        draft_thesis = clean_text(effective_analysis_brief.get("recommended_thesis")) or clean_text(source_summary.get("core_verdict"))
    draft_claim_map = build_draft_claim_map(citations, effective_analysis_brief) if effective_analysis_brief else []
    style_profile_applied = build_style_profile_applied(request)
    writer_risk_notes = build_writer_risk_notes(effective_analysis_brief, source_summary) if effective_analysis_brief else []
    article_framework = resolve_article_framework(request, source_summary)
    publishability_checks = build_publishability_checks(title, subtitle, lede, sections)

    editor_notes = []
    if int(source_summary.get("blocked_source_count", 0)) > 0:
        editor_notes.append("Some sources were blocked or background-only. Do not turn them into confirmed facts in the article.")
    if not selected_images:
        editor_notes.append("No reusable image asset is attached yet. If this must be visual, capture or save the images first.")
    if request.get("draft_mode") == "image_only":
        editor_notes.append("This draft was generated in image-only mode. Text is intentionally minimal and should not overstate what the images prove.")
    if not publishability_checks.get("passed"):
        editor_notes.append("Publishability checks flagged operator-style language. Review the title and section copy before publishing.")

    package = {
        "title": title,
        "subtitle": subtitle,
        "lede": lede,
        "sections": sections,
        "body_sections": sections,
        "body_markdown": body_markdown,
        "article_markdown": article_markdown,
        "image_blocks": deepcopy(selected_images),
        "selected_images": deepcopy(selected_images),
        "citations": citations,
        "editor_notes": editor_notes,
        "draft_mode": request.get("draft_mode"),
        "language_mode": request.get("language_mode"),
        "article_framework": article_framework,
        "public_topic": public_topic_text(request, clean_text(source_summary.get("topic")) or "article-topic"),
        "draft_thesis": draft_thesis,
        "draft_claim_map": draft_claim_map,
        "publishability_checks": publishability_checks,
        "style_profile_applied": style_profile_applied,
        "writer_risk_notes": writer_risk_notes,
        "feedback_profile_status": deepcopy(safe_dict(request.get("feedback_profile_status"))),
        "render_context": {
            "request": {
                "topic": clean_text(request.get("topic")),
                "analysis_time": isoformat_or_blank(request.get("analysis_time")),
                "angle": clean_text(request.get("angle")),
                "angle_zh": clean_text(request.get("angle_zh")),
                "must_include": clean_string_list(request.get("must_include")),
                "must_avoid": clean_string_list(request.get("must_avoid")),
                "human_signal_ratio": int(request.get("human_signal_ratio", 0) or 0),
                "personal_phrase_bank": clean_string_list(request.get("personal_phrase_bank")),
                "style_memory": style_memory_summary(request),
                "draft_mode": clean_text(request.get("draft_mode")),
                "language_mode": clean_text(request.get("language_mode")),
                "article_framework": clean_text(request.get("article_framework")),
            },
            "source_summary": deepcopy(source_summary),
            "evidence_digest": deepcopy(evidence_digest),
            "analysis_brief": deepcopy(effective_analysis_brief),
        },
    }
    refresh_article_package(package, request.get("must_avoid", []))
    return package, selected_images


def build_article_draft(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    evidence_bundle = ensure_evidence_bundle(request)
    request["evidence_bundle"] = evidence_bundle
    source_summary = safe_dict(evidence_bundle.get("source_summary"))
    evidence_digest = safe_dict(evidence_bundle.get("evidence_digest"))
    citations = deepcopy(safe_list(evidence_bundle.get("citations")))
    image_candidates = deepcopy(safe_list(evidence_bundle.get("image_candidates")))
    analysis_brief = safe_dict(request.get("analysis_brief"))
    if not analysis_brief:
        analysis_brief_result = build_analysis_brief(
            {
                "source_result": request["source_result"],
                "source_result_path": request.get("source_result_path"),
                "topic": request.get("topic"),
                "analysis_time": isoformat_or_blank(request["analysis_time"]),
            }
        )
        analysis_brief = safe_dict(analysis_brief_result.get("analysis_brief"))
    analysis_brief = analysis_brief or derive_analysis_brief_from_digest(
        source_summary,
        evidence_digest,
        citations,
        image_candidates,
    )
    request["analysis_brief"] = analysis_brief
    article_package, selected_images = assemble_article_package(
        request,
        source_summary,
        evidence_digest,
        citations,
        image_candidates,
        analysis_brief,
    )
    if clean_string_list(request.get("applied_feedback_profiles")):
        article_package["editor_notes"] = clean_string_list(
            safe_list(article_package.get("editor_notes"))
            + [f"Applied feedback profiles: {', '.join(clean_string_list(request.get('applied_feedback_profiles')))}"]
        )
    asset_localization = localize_selected_images(article_package, request)
    selected_images = deepcopy(safe_list(article_package.get("selected_images") or article_package.get("image_blocks")))
    image_candidates = merge_localized_image_candidates(image_candidates, selected_images)
    evidence_bundle["image_candidates"] = deepcopy(image_candidates)

    result = {
        "request": {
            **request,
            "analysis_time": isoformat_or_blank(request["analysis_time"]),
            "source_result": None,
            "evidence_bundle": {
                "contract_version": clean_text(evidence_bundle.get("contract_version")),
                "citation_count": len(citations),
                "image_candidate_count": len(image_candidates),
            },
        },
        "source_summary": source_summary,
        "source_context": {
            "source_kind": source_summary.get("source_kind"),
            "topic": source_summary.get("topic"),
            "analysis_time": source_summary.get("analysis_time"),
            "source_result_path": request.get("source_result_path", ""),
        },
        "evidence_digest": evidence_digest,
        "evidence_bundle": evidence_bundle,
        "analysis_brief": analysis_brief,
        "draft_context": {
            "source_summary": source_summary,
            "evidence_digest": evidence_digest,
            "analysis_brief": analysis_brief,
            "citation_candidates": citations,
            "image_candidates": image_candidates,
            "selected_images": deepcopy(selected_images),
            "evidence_bundle": evidence_bundle,
            "source_result_path": request.get("source_result_path", ""),
            "applied_feedback_profiles": clean_string_list(request.get("applied_feedback_profiles")),
            "asset_output_dir": clean_text(request.get("asset_output_dir")),
        },
        "article_package": article_package,
        "asset_localization": asset_localization,
        "preview_html": build_article_preview_html(article_package),
        "revision_history": [],
        "revision_log": [],
    }
    result["report_markdown"] = build_report_markdown(article_package)
    return result


ARTICLE_META_TEXT_PATTERNS = (
    "real event, trend, or public dispute",
    "drawing multi-source attention",
    "business, industry, or investing relevance",
    "pure social chatter",
    "still need verification before the article turns them into settled facts",
    "already entered public discussion",
    "已经进入公开讨论的真实事件、趋势或争议",
    "有解释价值，不只是情绪型热度",
    "仍有关键细节、影响路径或真假边界需要继续核实",
)


def is_article_meta_text(text: str) -> bool:
    cleaned = strip_terminal_punctuation(clean_text(text))
    lowered = cleaned.lower()
    if not cleaned:
        return False
    return any(pattern in cleaned or pattern in lowered for pattern in ARTICLE_META_TEXT_PATTERNS)


def article_ready_fact_texts(
    canonical_facts: list[dict[str, Any]],
    *,
    mode: str,
    limit: int = 3,
) -> list[str]:
    texts: list[str] = []
    for item in canonical_facts:
        text = preferred_brief_item_text(item, mode=mode, field="claim_text", zh_field="claim_text_zh")
        if text and not is_article_meta_text(text) and text not in texts:
            texts.append(text)
        if len(texts) >= limit:
            break
    return texts


def localized_trend_texts(trend_lines: list[dict[str, Any]], *, mode: str, limit: int = 2) -> list[str]:
    texts: list[str] = []
    for item in trend_lines:
        text = localized_brief_text(
            preferred_brief_item_text(item, mode=mode, field="detail", zh_field="detail_zh"),
            mode,
        )
        if text:
            texts.append(text)
        if len(texts) >= limit:
            break
    return texts


def chinese_market_focus(text: str) -> str:
    cleaned = strip_terminal_punctuation(clean_text(text))
    lowered = cleaned.lower()
    if not cleaned:
        return ""
    if "背景" in cleaned and "传导路径" in cleaned:
        return "事件背景、传导路径和后续影响"
    if "融资意愿" in cleaned or "订单能见度" in cleaned or "预算和采购" in cleaned or "预算投放" in cleaned:
        return "融资意愿、订单能见度和预算投放"
    if "航运" in cleaned and "供应链成本" in cleaned:
        return "航运、保险和供应链成本"
    if "商品价格" in cleaned and "风险偏好" in cleaned:
        return "商品价格、政策空间和风险偏好传导"
    if "企业经营" in cleaned and "资本市场" in cleaned:
        return "企业经营、资本市场和融资环境"
    if has_cjk(cleaned):
        return cleaned
    if "chinese business and investing readers" in lowered or "event background" in lowered or "transmission path" in lowered:
        return "事件背景、传导路径和后续影响"
    if "funding appetite" in lowered or "order visibility" in lowered or "real budgets" in lowered:
        return "融资意愿、订单能见度和预算投放"
    if "commodity prices" in lowered or "risk appetite" in lowered or "policy room" in lowered:
        return "商品价格、政策空间和风险偏好传导"
    if "corporate operations" in lowered or "capital markets" in lowered or "financing environment" in lowered:
        return "企业经营、资本市场和融资环境"
    if any(token in cleaned for token in ("能源", "油", "气", "霍尔木兹", "LNG", "天然气")):
        return "能源安全和输入性通胀压力"
    if any(token in cleaned for token in ("航运", "保险", "供应链", "商船", "油轮")):
        return "航运、保险和供应链成本"
    if any(token in cleaned for token in ("外交", "中东布局", "撤离", "撤侨", "公民", "表态")):
        return "外交回旋空间和中东布局"
    if any(token in cleaned for token in ("炼化", "化工", "制造业", "利润")):
        return "炼化、化工和制造业利润"
    return cleaned


def chinese_watch_item(text: str) -> str:
    cleaned = chinese_market_focus(text)
    if not cleaned:
        return ""
    if "事件背景、传导路径和后续影响" in cleaned:
        return "这波热度会不会继续往真实决策和行业判断上传导"
    if "融资意愿、订单能见度和预算投放" in cleaned:
        return "融资、订单和预算会不会继续改善，而不是只热几天"
    if "商品价格、政策空间和风险偏好传导" in cleaned:
        return "商品价格、政策空间和风险偏好会不会继续往行业里压"
    if "企业经营、资本市场和融资环境" in cleaned:
        return "企业经营、资本市场和融资环境会不会出现更明确的读穿"
    if "能源安全" in cleaned:
        return "霍尔木兹、油气价格和输入性通胀这条线会不会继续往上推"
    if "航运、保险和供应链成本" in cleaned:
        return "航运、保险和供应链成本会不会继续抬升"
    if "外交回旋空间和中东布局" in cleaned:
        return "中方后续表态、撤离安排和地区外交动作会不会出现新变化"
    if "炼化、化工和制造业利润" in cleaned:
        return "成本压力会不会继续往中下游利润表里传"
    return f"{cleaned}会不会继续扩大"


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    not_proven = safe_list(analysis_brief.get("not_proven"))
    lead_fact = article_ready_fact_texts(canonical_facts, mode=language_mode, limit=1)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    voice_prefix = pick_voice_prefix(request, "lede")
    if lead_fact:
        zh_relevance = strip_terminal_punctuation(chinese_market_focus(market_relevance[0])) if market_relevance else "它开始影响后面的判断和动作"
        zh = f"{lead_fact[0]}。真正值得往下写的，不只是热度，而是{zh_relevance}这条线会怎么继续传导。"
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, zh, mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    boundary_claims = preferred_brief_texts(not_proven, mode=language_mode, limit=1)
    boundary_claim = boundary_claims[0] if boundary_claims else ""
    chinese_focus = [chinese_market_focus(item) for item in market_relevance[:3] if chinese_market_focus(item)]
    trend_texts = localized_trend_texts(safe_list(analysis_brief.get("trend_lines")), mode=language_mode, limit=1)
    if language_mode == "chinese" and chinese_focus:
        zh = (
            f"{topic}最近会被反复提起，不只是因为热度冲上来了，"
            f"更因为{strip_terminal_punctuation(trend_texts[0]) if trend_texts else '它已经开始往更硬的变量上传导'}。"
            f"真正值得往下写的，是{join_with_commas(chinese_focus[:2], '后续影响')}会不会继续压到真实决策上。"
        )
        if boundary_claim:
            zh += f" 但像“{boundary_claim}”这样的判断，现阶段还别写满。"
        en = (
            f"{topic} is worth following because the story is starting to move into "
            f"{join_with_commas(market_relevance[:2], 'actual downstream decisions')}, not because the headline simply looks louder."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, zh, mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    if language_mode == "chinese" and boundary_claim and chinese_focus:
        zh = (
            f"先别把“{boundary_claim}”当成已经落地的结论。"
            f"真正压到桌面上的，是{join_with_commas(chinese_focus, '能源、成本和外部环境')}这几条传导链。"
        )
        en = (
            f"Do not treat '{boundary_claim}' as a settled outcome yet. "
            f"What actually matters for {topic} is the transmission into {join_with_commas(market_relevance[:3], 'costs, policy room, and real-world decision pressure')}."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, zh, mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    zh = (
        f"围绕{topic}，现在更值得先看的，是"
        f"{join_with_commas(chinese_focus[:3], '几条已经开始发生传导的影响路径')}。"
        "因为真正会压到台面上的，从来不是口号本身，而是这些变量怎么一层层往里走。"
    )
    en = (
        f"For {topic}, the most useful starting point is "
        f"{join_with_commas(market_relevance[:3], 'the small set of transmission paths already on the table')}. "
        "The real question is not the slogan around the story, but how those variables move through decisions next."
    )
    return bilingual_text(zh, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance_raw = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    market_relevance = [chinese_market_focus(item) if language_mode == "chinese" else item for item in market_relevance_raw]
    open_questions = (
        (clean_string_list(analysis_brief.get("open_questions_zh")) or clean_string_list(analysis_brief.get("open_questions")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("open_questions")) or clean_string_list(analysis_brief.get("open_questions_zh")))
    )
    fact_texts = article_ready_fact_texts(canonical_facts, mode=language_mode, limit=3)
    meta_fact_texts = preferred_brief_texts(canonical_facts, mode=language_mode, limit=3)
    not_proven_texts = preferred_brief_texts(not_proven, mode=language_mode, limit=2)
    trend_texts = localized_trend_texts(trend_lines, mode=language_mode, limit=2)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")
    if language_mode == "chinese" and not fact_texts:
        watch_items = preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)
    else:
        watch_items = open_questions[:3] or preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)

    if fact_texts:
        fact_zh = (
            "台面上先能站住的，不外乎这几条："
            + join_with_semicolons(fact_texts, f"{topic}还在发展中")
            + "。先把这些抓稳，再往下谈更大的判断。"
        )
        fact_en = (
            "Start with the points that can already stand on the record: "
            + join_with_semicolons(fact_texts, f"{topic} is still developing")
            + ". Hold those steady first, then widen the frame."
        )
    elif meta_fact_texts and language_mode == "chinese":
        trend_line = join_with_semicolons(trend_texts, "多源讨论已经把这件事往更硬的层面推")
        focus_line = join_with_commas(market_relevance[:3], "后续传导和真实影响")
        fact_zh = f"先把一个判断放前面：{topic}已经不只是标题层面的热闹。{trend_line}，所以更值得写的是{focus_line}。"
        if not_proven_texts:
            fact_zh += f" 不过像“{not_proven_texts[0]}”这种话，现阶段还不能直接写成既成事实。"
        fact_en = (
            f"The story around {topic} has moved beyond raw attention. "
            f"What matters more now is {join_with_commas(market_relevance_raw[:3], 'the next round of transmission and decision impact')}."
        )
    else:
        boundary = not_proven_texts[0] if not_proven_texts else ""
        fact_zh = f"先别把“{boundary}”当成已经落地的结论。" if boundary else "先别急着往最大的结论上靠。"
        fact_zh += "眼下更能落到纸面上的，是" + join_with_commas(market_relevance[:3], "几条已经开始发生传导的影响路径") + "这几条传导线。"
        fact_en = (
            f"Do not treat '{boundary}' as settled yet. " if boundary else "Do not rush straight to the biggest conclusion yet. "
        ) + ("The part that is easier to write cleanly right now is " + join_with_commas(market_relevance_raw[:3], "the transmission paths already moving into view") + ".")

    fact_paragraph = bilingual_text(
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_zh, mode="chinese"),
        prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_en, mode="english"),
        language_mode,
    )
    spread_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "这件事还会继续发酵，不只是因为热度没退，而是因为"
            + join_with_semicolons(trend_texts, "讨论开始从情绪转向真实的影响路径")
            + "。一旦讨论落到成本、行业或执行层面，它就不只是流量题了。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "spread"),
            "The discussion keeps moving not because the headline sounds louder, but because "
            + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to actual transmission")
            + ". Once the topic starts hitting costs, industry positioning, or execution, it stops being pure traffic.",
            mode="english",
        ),
        language_mode,
    )
    impact_focus = (
        [
            item
            if has_cjk(item) and len(strip_terminal_punctuation(item)) <= 18
            else chinese_market_focus(item)
            for item in market_relevance_raw
        ]
        if language_mode == "chinese"
        else market_relevance_raw
    )
    impact_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "真正值得盯的，不是表面热度，而是它会传到谁、改变谁的判断。现在最直接的观察对象是"
            + join_with_commas(impact_focus[:3], "后续决策、行业情绪和资源分配")
            + "。这才是它从话题变成变量的地方。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "impact"),
            "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
            + join_with_commas(market_relevance_raw[:3], "follow-on decisions, industry positioning, and resource allocation")
            + ". That is where a topic stops being noise and becomes a variable.",
            mode="english",
        ),
        language_mode,
    )
    watch_paragraph = bilingual_text(
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "接下来别盯情绪，盯这几件事：" + join_with_semicolons(watch_items, "新的公开确认、后续动作，以及市场会不会继续加码") + "。这些点谁先被验证，谁就会把叙事往前推一步。",
            mode="chinese",
        ),
        prepend_voice_prefix(
            pick_voice_prefix(request, "watch"),
            "The next useful checkpoints are "
            + join_with_semicolons(watch_items, "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
            + ". Whichever of those gets verified first will move the story forward.",
            mode="english",
        ),
        language_mode,
    )
    caution_paragraph = bilingual_text(
        "这里最容易被说过头的地方是："
        + join_with_semicolons(not_proven_texts, "不要把还在发酵的推演，当成已经落地的事实")
        + "。写到这里，克制本身就是质量。",
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar.",
        language_mode,
    )
    image_paragraph = bilingual_text(
        "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
        + image_sentence(images),
        language_mode,
    )

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "先只说图像层真正能支撑的部分：" + visual_evidence_sentence(images),
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections


def strip_terminal_punctuation(text: str) -> str:
    return clean_text(text).rstrip(" .;:。；，、!?！？")


def join_with_semicolons(items: list[str], empty_text: str) -> str:
    clean_items = [strip_terminal_punctuation(item) for item in items if strip_terminal_punctuation(item)]
    if not clean_items:
        return empty_text
    separator = "；" if any(has_cjk(item) for item in clean_items) or has_cjk(empty_text) else "; "
    return separator.join(clean_items)


DEBATE_TEXT_HINTS = ("还是", "争论", "分歧", "debate", "whether", "controvers", "争议")
IMPLICATION_TEXT_HINTS = ("不再", "真正稀缺", "意味着", "说明", "scarce", "shortage", "核心")
GENERIC_CHINESE_FOCUS = {"事件背景、传导路径和后续影响"}


def unique_texts(items: list[str]) -> list[str]:
    results: list[str] = []
    for item in items:
        cleaned = strip_terminal_punctuation(clean_text(item))
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def chinese_sentence(text: str) -> str:
    cleaned = strip_terminal_punctuation(clean_text(text))
    if not cleaned:
        return ""
    return f"{cleaned}。"


def join_chinese_sentences(items: list[str]) -> str:
    return "".join(chinese_sentence(item) for item in items if strip_terminal_punctuation(clean_text(item)))


def normalized_chinese_focus_items(items: list[str], *, concrete_only: bool = False) -> list[str]:
    normalized = unique_texts([chinese_market_focus(item) for item in items if chinese_market_focus(item)])
    if concrete_only:
        concrete = [item for item in normalized if item not in GENERIC_CHINESE_FOCUS]
        return concrete or normalized
    return normalized


def chinese_focus_cluster(items: list[str], fallback: str = "更实的经营变量") -> str:
    clean_items = unique_texts(items)
    if not clean_items:
        return fallback
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        linker = "，以及" if any("和" in item for item in clean_items) else "和"
        return f"{clean_items[0]}{linker}{clean_items[1]}这些更实的变量"
    return f"{clean_items[0]}、{clean_items[1]}，以及{clean_items[2]}这些更实的变量"


def chinese_progression_phrase(items: list[str], fallback: str = "先看更实的经营变量会不会继续动") -> str:
    clean_items = unique_texts(items)
    if not clean_items:
        return fallback
    if len(clean_items) == 1:
        return f"先看{clean_items[0]}"
    if len(clean_items) == 2:
        return f"先看{clean_items[0]}，再看{clean_items[1]}"
    return f"先看{clean_items[0]}，再看{clean_items[1]}，最后看{clean_items[2]}"


def looks_like_debate_text(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(hint in lowered or hint in text for hint in DEBATE_TEXT_HINTS)


def looks_like_implication_text(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(hint in lowered or hint in text for hint in IMPLICATION_TEXT_HINTS)


def split_fact_roles(fact_texts: list[str]) -> tuple[str, str, str]:
    clean_items = unique_texts(fact_texts)
    if not clean_items:
        return "", "", ""
    primary = next((item for item in clean_items if not looks_like_debate_text(item)), clean_items[0])
    debate = next((item for item in clean_items if item != primary and looks_like_debate_text(item)), "")
    implication = next(
        (item for item in clean_items if item not in {primary, debate} and looks_like_implication_text(item)),
        "",
    )
    if not implication:
        implication = next((item for item in clean_items if item not in {primary, debate}), "")
    return primary, debate, implication


def request_style_memory(request: dict[str, Any]) -> dict[str, Any]:
    return safe_dict(request.get("style_memory"))


def style_memory_slot_lines(request: dict[str, Any], slot: str) -> list[str]:
    return clean_string_list(safe_dict(request_style_memory(request).get("slot_lines")).get(slot))


def style_memory_slot_guidance(request: dict[str, Any], slot: str) -> list[str]:
    return clean_string_list(safe_dict(request_style_memory(request).get("slot_guidance")).get(slot))


def normalize_headline_hook_mode(value: Any) -> str:
    mode = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    if mode in {"", "auto", "default"}:
        return "auto"
    if mode in {"off", "none", "neutral"}:
        return "neutral"
    if mode in {"traffic", "click", "high_ctr"}:
        return "traffic"
    if mode in {"aggressive", "breaking", "urgent"}:
        return "aggressive"
    return "auto"


def headline_hook_prefixes(request: dict[str, Any], *, mode: str) -> list[str]:
    custom_prefixes = clean_string_list(request.get("headline_hook_prefixes"))
    if custom_prefixes:
        return custom_prefixes
    if mode == "aggressive":
        return ["突发！", "刚刚，", "最新，"]
    if mode == "traffic":
        return ["刚刚，", "突发！", "最新，"]
    return []


def title_has_headline_hook(title: Any) -> bool:
    cleaned = clean_text(title)
    if not cleaned:
        return False
    for prefix in ("突发！", "刚刚，", "刚刚：", "刚刚", "最新，", "最新：", "重磅！", "重磅，"):
        if cleaned.startswith(prefix):
            return True
    return False


def resolve_headline_hook_mode(request: dict[str, Any], source_summary: dict[str, Any]) -> str:
    configured_mode = normalize_headline_hook_mode(request.get("headline_hook_mode"))
    if configured_mode != "auto":
        return configured_mode
    if clean_text(request.get("language_mode")) != "chinese":
        return "neutral"
    if resolve_article_framework(request, source_summary) in {"hot_comment", "deep_analysis", "story", "list", "opinion"}:
        return "traffic"
    return "neutral"


def apply_headline_hook(title: str, request: dict[str, Any], source_summary: dict[str, Any]) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return title
    compact_title = compact_chinese_title(title, limit=30) or title
    if title_has_headline_hook(compact_title):
        return compact_title
    hook_mode = resolve_headline_hook_mode(request, source_summary)
    if hook_mode == "neutral":
        return compact_title
    prefixes = headline_hook_prefixes(request, mode=hook_mode)
    if not prefixes:
        return compact_title
    prefix = prefixes[0]
    hooked_title = compact_chinese_title(compact_title, limit=max(12, 30 - len(prefix))) or compact_title
    return f"{prefix}{hooked_title}"


def style_memory_summary(request: dict[str, Any]) -> dict[str, Any]:
    memory = request_style_memory(request)
    if not memory:
        return {}
    sample_sources_all = safe_list(memory.get("sample_sources"))
    sample_sources = deepcopy(sample_sources_all[:5])
    sample_source_declared_count = len(sample_sources_all)
    sample_source_path_count = sum(1 for item in sample_sources_all if clean_text(safe_dict(item).get("path")))
    sample_source_loaded_count = sum(1 for item in sample_sources_all if path_exists(safe_dict(item).get("path")))
    slot_lines: dict[str, list[str]] = {}
    slot_guidance: dict[str, list[str]] = {}
    for slot in ("title", "subtitle", "lede", "facts", "spread", "impact", "watch"):
        lines = style_memory_slot_lines(request, slot)
        guidance = style_memory_slot_guidance(request, slot)
        if lines:
            slot_lines[slot] = lines[:2]
        if guidance:
            slot_guidance[slot] = guidance[:2]
    summary = {
        "target_band": clean_text(memory.get("target_band")),
        "voice_summary": clean_text(memory.get("voice_summary")),
        "preferred_transitions": clean_string_list(memory.get("preferred_transitions")),
        "must_land": clean_string_list(memory.get("must_land")),
        "avoid_patterns": clean_string_list(memory.get("avoid_patterns")),
        "slot_lines": slot_lines,
        "slot_guidance": slot_guidance,
        "sample_sources": sample_sources,
        "sample_source_declared_count": sample_source_declared_count,
        "sample_source_loaded_count": sample_source_loaded_count,
        "sample_source_available_count": sample_source_loaded_count,
        "sample_source_missing_count": max(0, sample_source_path_count - sample_source_loaded_count),
        "sample_source_runtime_mode": "curated_profile_only",
        "raw_sample_text_loaded": False,
        "corpus_derived_transitions": clean_string_list(memory.get("preferred_transitions"))[:3],
    }
    return {key: value for key, value in summary.items() if value not in ("", [], {}, None)}


def append_unique_sentence(sentences: list[str], sentence: str) -> list[str]:
    cleaned = strip_terminal_punctuation(sentence)
    if not cleaned:
        return sentences
    existing = [strip_terminal_punctuation(item) for item in sentences if strip_terminal_punctuation(item)]
    if cleaned in existing:
        return sentences
    if any(cleaned in item or item in cleaned for item in existing):
        return sentences
    return [*sentences, cleaned]


def sentence_core_key(text: str) -> str:
    cleaned = strip_terminal_punctuation(clean_text(text)).lower()
    if not cleaned:
        return ""
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", cleaned)


def sentence_is_redundant(candidate: str, references: list[str]) -> bool:
    candidate_key = sentence_core_key(candidate)
    if not candidate_key:
        return True
    candidate_charset = set(candidate_key)
    for reference in references:
        reference_key = sentence_core_key(reference)
        if not reference_key:
            continue
        if candidate_key in reference_key or reference_key in candidate_key:
            return True
        reference_charset = set(reference_key)
        if len(candidate_key) < 10 or len(reference_key) < 10:
            continue
        overlap = len(candidate_charset & reference_charset)
        denominator = max(1, min(len(candidate_charset), len(reference_charset)))
        if overlap / denominator >= 0.75:
            return True
    return False


def requested_focus_sentences(request: dict[str, Any], slot: str, *, mode: str) -> list[str]:
    guidance = clean_string_list(request.get("must_include"))
    if not guidance:
        return []
    lowered = " ".join(item.lower() for item in guidance)
    sentences: list[str] = []
    if mode == "chinese":
        if slot in {"lede", "facts"} and any(
            token in lowered for token in ("事实", "确认", "未证实", "边界", "fact", "confirmed", "unconfirmed", "inference", "boundary")
        ):
            sentences.append("先把已确认的变化写清，再谈后面的推演")
        if slot in {"lede", "impact"} and any(
            token in lowered for token in ("传导", "影响路径", "市场", "读者", "经营", "定价", "transmission", "market", "reader", "pricing", "budget", "order")
        ):
            sentences.append("真正该看的，是后面那条会继续落到经营和定价上的线")
        if slot == "subtitle" and any(token in lowered for token in ("结论", "判断", "直说", "conclusion", "judgment")):
            sentences.append("先把最实的判断拎出来，再看后面的影响路径")
        if slot == "watch" and any(token in lowered for token in ("信号", "验证", "确认", "市场", "watch", "signal", "confirm", "market")):
            sentences.append("真正能把叙事坐实的，还是后面几个硬信号")
        return clean_string_list(sentences)
    if slot in {"lede", "facts"} and any(token in lowered for token in ("fact", "confirmed", "unconfirmed", "boundary", "inference")):
        sentences.append("Keep the confirmed facts steady before widening into inference.")
    if slot in {"lede", "impact"} and any(token in lowered for token in ("transmission", "market", "reader", "pricing", "budget", "order")):
        sentences.append("The useful angle is the path into real operating and market decisions.")
    if slot == "watch" and any(token in lowered for token in ("watch", "signal", "confirm", "market")):
        sentences.append("Focus on the hard signals that would actually upgrade the story.")
    return clean_string_list(sentences)


STYLE_ALIGNMENT_STOP_TERMS_ZH = {
    "这件",
    "件事",
    "这波",
    "事情",
    "真正",
    "接下",
    "下来",
    "继续",
    "变化",
    "影响",
    "传导",
    "结论",
    "信号",
    "叙事",
    "热度",
    "判断",
    "市场",
    "后面",
    "前面",
    "现在",
    "眼下",
    "问题",
    "变量",
    "路径",
    "层面",
    "开始",
    "不是",
    "只是",
    "已经",
    "会不",
    "不会",
    "改写",
    "坐实",
}

STYLE_ALIGNMENT_STOP_TERMS_EN = {
    "story",
    "topic",
    "angle",
    "signal",
    "signals",
    "watch",
    "next",
    "really",
    "matters",
    "matter",
    "change",
    "changes",
    "impact",
    "impacts",
    "market",
    "markets",
}


def requested_target_length_chars(request: dict[str, Any], *, default: int = 1000) -> int:
    value = request.get("target_length_chars", request.get("target_length", default))
    try:
        numeric = int(value or default)
    except (TypeError, ValueError):
        numeric = default
    return max(0, numeric)


def style_alignment_terms(text: Any, *, mode: str) -> set[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return set()
    terms: set[str] = set()
    latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", cleaned)
    for token in latin_tokens:
        lowered = token.lower()
        if lowered not in STYLE_ALIGNMENT_STOP_TERMS_EN:
            terms.add(lowered)
    if mode != "chinese":
        word_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", cleaned.lower())
        return {token for token in word_tokens if token not in STYLE_ALIGNMENT_STOP_TERMS_EN} | terms
    cjk_only = re.sub(r"[^\u4e00-\u9fff]+", "", cleaned)
    for size in (2, 3, 4):
        for index in range(max(0, len(cjk_only) - size + 1)):
            token = cjk_only[index : index + size]
            if token in STYLE_ALIGNMENT_STOP_TERMS_ZH:
                continue
            terms.add(token)
    return terms


def style_line_is_topic_aligned(
    line: str,
    request: dict[str, Any],
    context_lines: list[str] | None = None,
    *,
    mode: str,
) -> bool:
    line_terms = style_alignment_terms(line, mode=mode)
    if not line_terms:
        return False
    anchors = [public_topic_text(request), *clean_string_list(request.get("must_include")), *(context_lines or [])]
    anchor_terms: set[str] = set()
    for item in anchors:
        anchor_terms.update(style_alignment_terms(item, mode=mode))
    if not anchor_terms:
        return False
    shared = line_terms & anchor_terms
    if not shared:
        return False
    if any(len(item) >= 4 or re.search(r"[A-Za-z0-9]", item) for item in shared):
        return True
    return len(shared) >= 2


def target_section_count(
    request: dict[str, Any],
    framework: str,
    *,
    canonical_count: int,
    not_proven_count: int,
    trend_count: int,
    relevance_count: int,
    question_count: int,
) -> int:
    target_length = requested_target_length_chars(request)
    section_count = 4
    if framework == "deep_analysis":
        if target_length >= 2600:
            section_count = 6
        elif target_length >= 1800:
            section_count = 5
        evidence_points = canonical_count + not_proven_count + trend_count + relevance_count + question_count
        if target_length >= 2200 and evidence_points >= 7:
            section_count = max(section_count, 6)
    elif framework in {"story", "opinion", "hot_comment"} and target_length >= 2200:
        section_count = 5
    return min(6, max(4, section_count))


def apply_slot_memory(
    sentences: list[str],
    request: dict[str, Any],
    slot: str,
    *,
    mode: str,
    context_lines: list[str] | None = None,
) -> list[str]:
    updated = list(sentences)
    custom_lines = style_memory_slot_lines(request, slot)[:1]
    for item in custom_lines:
        if sentence_is_redundant(item, updated):
            continue
        if not style_line_is_topic_aligned(item, request, context_lines or updated, mode=mode):
            continue
        updated = append_unique_sentence(updated, item)
    if mode == "chinese" and slot in {"lede", "facts", "watch"} and len(updated) >= 3:
        return updated
    for item in requested_focus_sentences(request, slot, mode=mode)[:1]:
        if sentence_is_redundant(item, updated):
            continue
        updated = append_unique_sentence(updated, item)
    return updated


def compact_chinese_title(text: Any, *, limit: int = 24) -> str:
    cleaned = strip_source_branding(text)
    cleaned = strip_terminal_punctuation(cleaned)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(目前|眼下|现在|这轮|部分)\s*", "", cleaned)
    cleaned = re.sub(r"^真正稀缺的不再是概念，而是", "", cleaned)
    cleaned = re.sub(r"^围绕", "", cleaned)
    if "，" in cleaned and len(cleaned) > limit:
        cleaned = clean_text(cleaned.split("，", 1)[0])
    if "：" in cleaned and len(cleaned) > limit:
        cleaned = clean_text(cleaned.split("：", 1)[0])
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip("，、；： ")
    return cleaned


def derive_chinese_title(request: dict[str, Any], analysis_brief: dict[str, Any], source_summary: dict[str, Any]) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return ""
    custom_titles = style_memory_slot_lines(request, "title")
    if custom_titles:
        return compact_chinese_title(custom_titles[0], limit=28)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "")
    if has_cjk(topic):
        return compact_chinese_title(topic, limit=30)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    chinese_facts = article_ready_fact_texts(canonical_facts, mode="chinese", limit=3)
    for candidate in chinese_facts:
        compact = compact_chinese_title(candidate, limit=26)
        if compact:
            return compact
    relevance = clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(
        analysis_brief.get("market_or_reader_relevance")
    )
    focus_items = normalized_chinese_focus_items(relevance, concrete_only=True)
    if focus_items:
        return compact_chinese_title(f"{focus_items[0]}开始压到经营层", limit=22)
    return ""


def finalize_article_title(
    title: str,
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return title
    explicit_hint = clean_text(request.get("title_hint_zh")) or clean_text(request.get("title_hint"))
    custom_titles = style_memory_slot_lines(request, "title")
    if explicit_hint:
        return compact_chinese_title(explicit_hint, limit=30) or title
    if custom_titles:
        base_title = compact_chinese_title(custom_titles[0], limit=30) or title
        return apply_headline_hook(base_title, request, source_summary)
    public_topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "")
    if has_cjk(public_topic):
        base_title = compact_chinese_title(public_topic, limit=30) or title
        return apply_headline_hook(base_title, request, source_summary)
    derived = derive_chinese_title(request, analysis_brief, source_summary)
    return apply_headline_hook(derived or title, request, source_summary)


def build_public_lede(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> str:
    language_mode = request.get("language_mode", "english")
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    market_relevance = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    not_proven = safe_list(analysis_brief.get("not_proven"))
    fact_texts = article_ready_fact_texts(canonical_facts, mode=language_mode, limit=3)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "the story")
    voice_prefix = pick_voice_prefix(request, "lede")
    longform_mode = requested_target_length_chars(request) >= 1800

    if language_mode == "chinese":
        primary_fact, debate_fact, implication_fact = split_fact_roles(fact_texts)
        concrete_focus = normalized_chinese_focus_items(market_relevance, concrete_only=True)
        boundary_claims = preferred_brief_texts(not_proven, mode=language_mode, limit=1)
        sentences: list[str] = []

        if primary_fact:
            sentences.append(primary_fact)
            if concrete_focus:
                sentences.append(
                    f"这事之所以值得继续写，不在于它又上了热度，而在于后面连着{chinese_focus_cluster(concrete_focus[:3])}"
                )
            elif implication_fact:
                sentences.append(f"这事之所以值得继续写，不在于它又上了热度，而在于{implication_fact}")
            if debate_fact:
                sentences.append(f"但眼下还不能把结论写死，{debate_fact}")
            if not debate_fact and boundary_claims:
                sentences.append(f"但像“{boundary_claims[0]}”这样的判断，现阶段还不能直接写成结论。")
            if longform_mode:
                if concrete_focus:
                    sentences.append(
                        f"现在更该分清的，不是立场，而是{chinese_focus_cluster(concrete_focus[:2], fallback='后续传导变量')}里哪一条已经开始从讨论层往下走。"
                    )
                else:
                    sentences.append("写深这类题材的关键，是先把已经落地的变化、仍待验证的判断和后续传导变量分开。")
            sentences = apply_slot_memory(
                sentences,
                request,
                "lede",
                mode="chinese",
                context_lines=[primary_fact, debate_fact, implication_fact, *concrete_focus, *boundary_claims],
            )
            return bilingual_text(
                prepend_voice_prefix(voice_prefix, join_chinese_sentences(sentences), mode="chinese"),
                prepend_voice_prefix(
                    voice_prefix,
                    f"{primary_fact}. What keeps this worth following is not the headline heat alone, but the real decisions that could follow next.",
                    mode="english",
                ),
                language_mode,
            )

        if concrete_focus:
            sentences.append(f"{topic}最近会被反复提起，不只是因为热度起来了")
            sentences.append(f"更重要的是，它已经开始碰到{chinese_focus_cluster(concrete_focus[:3])}")
            if boundary_claims:
                sentences.append(f"不过像“{boundary_claims[0]}”这样的判断，现阶段还不能写成定论")
            if longform_mode:
                sentences.append(
                    f"写深这件事的关键，不是继续堆热度，而是看{chinese_focus_cluster(concrete_focus[:3])}里哪一条会先出现连续验证。"
                )
            sentences = apply_slot_memory(
                sentences,
                request,
                "lede",
                mode="chinese",
                context_lines=[*concrete_focus, *boundary_claims, *fact_texts],
            )
            return bilingual_text(
                prepend_voice_prefix(voice_prefix, join_chinese_sentences(sentences), mode="chinese"),
                prepend_voice_prefix(
                    voice_prefix,
                    f"{topic} is worth following because the story is starting to reach harder downstream variables, not because the headline simply looks louder.",
                    mode="english",
                ),
                language_mode,
            )

    lead_fact = fact_texts[:1]
    if lead_fact:
        en = (
            f"{lead_fact[0]}. What keeps this worth following is not the heat alone, "
            f"but {strip_terminal_punctuation(market_relevance[0]) if market_relevance else 'the way it can still change real decisions next'}."
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, lead_fact[0], mode="chinese"),
            prepend_voice_prefix(voice_prefix, en, mode="english"),
            language_mode,
        )

    boundary_claims = preferred_brief_texts(not_proven, mode=language_mode, limit=1)
    boundary_claim = boundary_claims[0] if boundary_claims else ""
    if language_mode == "chinese":
        sentences = (
            [f"先别把“{boundary_claim}”当成已经落地的结论"]
            if boundary_claim
            else [f"{topic}现在更值得先看的，是它会不会继续往真实决策上传导"]
        )
        if longform_mode and not boundary_claim:
            sentences.append("这类题材真正拉开差距的，不是喊出更大的结论，而是先看哪条传导路径已经有了第一手验证。")
        sentences = apply_slot_memory(
            sentences,
            request,
            "lede",
            mode="chinese",
            context_lines=[boundary_claim, *market_relevance, *fact_texts],
        )
        return bilingual_text(
            prepend_voice_prefix(voice_prefix, join_chinese_sentences(sentences), mode="chinese"),
            prepend_voice_prefix(
                voice_prefix,
                f"For {topic}, the most useful starting point is the small set of transmission paths already on the table.",
                mode="english",
            ),
            language_mode,
        )
    en = (
        f"Do not treat '{boundary_claim}' as a settled outcome yet. "
        if boundary_claim
        else f"For {topic}, the most useful starting point is the small set of transmission paths already on the table. "
    )
    if not boundary_claim:
        en += "The real question is how those variables move through decisions next."
    return bilingual_text(topic, en, language_mode)


def build_sections_from_brief(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    citations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    analysis_brief: dict[str, Any],
) -> list[dict[str, Any]]:
    del citations
    language_mode = request.get("language_mode", "english")
    framework = resolve_article_framework(request, source_summary)
    canonical_facts = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    trend_lines = safe_list(analysis_brief.get("trend_lines"))
    market_relevance_raw = (
        (clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")) or clean_string_list(analysis_brief.get("market_or_reader_relevance")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("market_or_reader_relevance")) or clean_string_list(analysis_brief.get("market_or_reader_relevance_zh")))
    )
    market_relevance = [chinese_market_focus(item) if language_mode == "chinese" else item for item in market_relevance_raw]
    open_questions = (
        (clean_string_list(analysis_brief.get("open_questions_zh")) or clean_string_list(analysis_brief.get("open_questions")))
        if language_mode == "chinese"
        else (clean_string_list(analysis_brief.get("open_questions")) or clean_string_list(analysis_brief.get("open_questions_zh")))
    )
    fact_texts = article_ready_fact_texts(canonical_facts, mode=language_mode, limit=3)
    meta_fact_texts = preferred_brief_texts(canonical_facts, mode=language_mode, limit=3)
    not_proven_texts = preferred_brief_texts(not_proven, mode=language_mode, limit=2)
    trend_texts = localized_trend_texts(trend_lines, mode=language_mode, limit=2)
    topic = public_topic_text(request, clean_text(source_summary.get("topic")) or "this story")
    if language_mode == "chinese" and not fact_texts:
        watch_items = preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)
    else:
        watch_items = open_questions[:3] or preliminary_watch_items(market_relevance, not_proven_texts, mode=language_mode)

    if language_mode == "chinese":
        primary_fact, debate_fact, implication_fact = split_fact_roles(fact_texts or meta_fact_texts)
        all_focus_items = normalized_chinese_focus_items(market_relevance_raw)
        concrete_focus = normalized_chinese_focus_items(market_relevance_raw, concrete_only=True)
        focus_for_progression = concrete_focus[:3] or all_focus_items[:3]
        watch_list = unique_texts(watch_items)[:3]
        core_source_count = int(source_summary.get("core_source_count", 0) or 0)
        shadow_source_count = int(source_summary.get("shadow_source_count", 0) or 0)
        section_count = target_section_count(
            request,
            framework,
            canonical_count=len(canonical_facts),
            not_proven_count=len(not_proven),
            trend_count=len(trend_lines),
            relevance_count=len(market_relevance_raw),
            question_count=len(open_questions),
        )
        longform_mode = section_count >= 5
        max_longform_mode = section_count >= 6

        fact_sentences: list[str] = []
        if primary_fact:
            fact_sentences.append(f"最先能确认的变化其实很具体：{primary_fact}")
        elif meta_fact_texts:
            fact_sentences.append(f"{topic}现在已经不只是标题层面的热闹")
        else:
            if not_proven_texts:
                fact_sentences.append(f"先别把“{not_proven_texts[0]}”当成已经落地的结论")
            else:
                fact_sentences.append(f"{topic}现在最该写的，不是最大结论，而是已经能落到纸面上的那部分")
        if debate_fact:
            fact_sentences.append(f"但这还不等于结论已经写完，{debate_fact}")
        elif not_proven_texts and primary_fact:
            fact_sentences.append(f"不过像“{not_proven_texts[0]}”这样的判断，现阶段还不能直接写成既成事实")
        if implication_fact:
            fact_sentences.append(f"更值得注意的是，{implication_fact}")
        elif concrete_focus:
            if primary_fact or meta_fact_texts:
                fact_sentences.append(f"真正该往下看的，是{chinese_focus_cluster(concrete_focus[:3])}")
            else:
                fact_sentences.append(f"眼下更该盯的，是{chinese_focus_cluster(concrete_focus[:3])}这几条传导线")
        if longform_mode:
            fact_sentences.append("这一步最重要的，不是把所有判断一次写满，而是先把已经落地的变化和还在路上的推演拆开。")
        fact_sentences = apply_slot_memory(
            fact_sentences,
            request,
            "facts",
            mode="chinese",
            context_lines=[primary_fact, debate_fact, implication_fact, *not_proven_texts, *market_relevance_raw, *open_questions],
        )
        fact_zh = join_chinese_sentences(fact_sentences)
        fact_en = (
            "Start with the points that can already stand on the record: "
            + join_with_semicolons(fact_texts or meta_fact_texts, f"{topic} is still developing")
            + ". Hold those steady first, then widen the frame."
        )

        spread_sentences: list[str] = []
        if core_source_count > 1:
            spread_sentences.append(f"这轮讨论没有很快掉下去，一个原因是已经有{core_source_count}个较高置信度来源给到交叉印证")
        elif core_source_count == 1:
            spread_sentences.append("这轮讨论能继续往前走，至少说明已经出现了高置信度确认")
        elif trend_texts:
            spread_sentences.append(f"这轮讨论还在往前走，核心不是热度，而是{trend_texts[0]}")
        if shadow_source_count > 0:
            spread_sentences.append(f"与此同时，还有{shadow_source_count}路更新更快但噪音也更大的信号在不断抬高情绪")
        spread_sentences.append(
            f"所以你现在看到的，不只是一个标题在回潮，而是在看它会不会继续落到{chinese_focus_cluster(focus_for_progression[:2], fallback='更实的经营变量')}"
        )
        if longform_mode:
            spread_sentences.append("换句话说，这里不是情绪在原地打转，而是不同来源在争夺哪条传导链会先被坐实。")
        spread_sentences = apply_slot_memory(
            spread_sentences,
            request,
            "spread",
            mode="chinese",
            context_lines=[*trend_texts, *fact_texts, *market_relevance_raw],
        )
        spread_zh = join_chinese_sentences(spread_sentences)
        spread_en = (
            "The discussion keeps moving not because the headline sounds louder, but because "
            + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to actual transmission")
            + ". Once the topic starts hitting costs, industry positioning, or execution, it stops being pure traffic."
        )

        impact_sentences: list[str] = []
        if focus_for_progression:
            impact_sentences.append(f"如果这波变化继续往下走，{chinese_progression_phrase(focus_for_progression)}")
            impact_sentences.append("这些变量一旦连续改善，这件事就不再只是热度题，而会变成经营层面要拿结果回答的问题")
        else:
            impact_sentences.append("真正值得盯的，不是表面热度，而是它会不会开始改变真实决策")
        if implication_fact and not sentence_is_redundant(implication_fact, fact_sentences):
            impact_sentences.append(implication_fact)
        if longform_mode and focus_for_progression:
            impact_sentences.append(
                f"先看{chinese_focus_cluster(focus_for_progression[:2], fallback='这条传导链')}有没有从单点信号变成连续验证，再谈更大的结论才更稳。"
            )
        impact_sentences = apply_slot_memory(
            impact_sentences,
            request,
            "impact",
            mode="chinese",
            context_lines=[*market_relevance_raw, *trend_texts, implication_fact, *watch_list],
        )
        impact_zh = join_chinese_sentences(impact_sentences)
        impact_en = (
            "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
            + join_with_commas(market_relevance_raw[:3], "follow-on decisions, industry positioning, and resource allocation")
            + ". That is where a topic stops being noise and becomes a variable."
        )

        watch_sentences: list[str] = []
        if watch_list:
            watch_intro = "接下来最该盯的，是几件更实的变量"
            if not sentence_is_redundant(watch_intro, impact_sentences):
                watch_sentences.append(watch_intro)
            labels = ("第一", "第二", "第三")
            for index, item in enumerate(watch_list):
                watch_sentences.append(f"{labels[index]}，{item}")
            watch_close = "这些点里只要两项开始连续被验证，叙事就会继续往前推；反过来，如果一项都落不了地，热度很快会回头"
            if not sentence_is_redundant(watch_close, impact_sentences):
                watch_sentences.append(watch_close)
        else:
            watch_sentences.append("接下来先盯新的公开确认、后续动作和市场会不会继续加码")
        watch_sentences = apply_slot_memory(
            watch_sentences,
            request,
            "watch",
            mode="chinese",
            context_lines=[*watch_list, *not_proven_texts, *open_questions],
        )
        watch_zh = join_chinese_sentences(watch_sentences)
        watch_en = (
            "The next useful checkpoints are "
            + join_with_semicolons(watch_items, "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
            + ". Whichever of those gets verified first will move the story forward."
        )

        caution_zh = join_chinese_sentences(
            [
                "这里最容易被写过头的地方，其实是把还在发酵的推演写成已经落地的事实"
                if not not_proven_texts
                else "这里最容易被写过头的地方，是" + join_with_semicolons(not_proven_texts, "还在发酵的推演")
            ]
            + ["写到这里，克制本身就是质量"]
        )
        caution_en = (
            "The easiest place to overstate the story is "
            + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
            + ". At this stage, restraint is part of the quality bar."
        )
        verification_sentences: list[str] = []
        if primary_fact:
            verification_sentences.append(f"第一层已经能写进记录的，是{primary_fact}")
        elif meta_fact_texts:
            verification_sentences.append(f"目前最稳的，还是{meta_fact_texts[0]}")
        if not_proven_texts:
            verification_sentences.append(f"第二层必须留边界的，是{join_with_semicolons(not_proven_texts, '那些还没落地的判断')}")
        else:
            verification_sentences.append("现在最需要克制的，不是回避判断，而是别把仍在路上的推演写成既成事实。")
        if trend_texts:
            verification_sentences.append(f"第三层正在把讨论往前推的，是{trend_texts[0]}")
        elif watch_list:
            verification_sentences.append(f"真正会把这件事往前推的，不会是口号本身，而是{watch_list[0]}")
        verification_zh = join_chinese_sentences(unique_texts(verification_sentences))
        verification_en = (
            "Separate the layers before making the judgment: what is already on the record; what still needs boundary language; "
            "and which signal is actually moving the discussion forward."
        )
        judgment_sentences: list[str] = []
        if focus_for_progression:
            judgment_sentences.append(
                f"把这件事再往前推一步看，真正的分水岭在于{chinese_focus_cluster(focus_for_progression[:3], fallback='后续传导变量')}里哪一条先出现连续信号。"
            )
        if watch_list:
            judgment_sentences.append(f"一旦{watch_list[0]}开始被连续验证，讨论就会从围观转向更强判断。")
        if implication_fact and not sentence_is_redundant(implication_fact, judgment_sentences):
            judgment_sentences.append(f"反过来看，{implication_fact}")
        elif not_proven_texts:
            judgment_sentences.append(f"如果后面只剩“{not_proven_texts[0]}”这类大结论，却没有新的公开验证，这轮热度反而更容易回头。")
        judgment_zh = join_chinese_sentences(unique_texts(judgment_sentences))
        judgment_en = (
            "The real divide is not between louder and quieter takes, but between signals that have started compounding and claims still waiting for proof."
        )

        fact_paragraph = bilingual_text(
            prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_zh, mode="chinese"),
            prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_en, mode="english"),
            language_mode,
        )
        spread_paragraph = bilingual_text(
            prepend_voice_prefix(pick_voice_prefix(request, "spread"), spread_zh, mode="chinese"),
            prepend_voice_prefix(pick_voice_prefix(request, "spread"), spread_en, mode="english"),
            language_mode,
        )
        impact_paragraph = bilingual_text(
            prepend_voice_prefix(pick_voice_prefix(request, "impact"), impact_zh, mode="chinese"),
            prepend_voice_prefix(pick_voice_prefix(request, "impact"), impact_en, mode="english"),
            language_mode,
        )
        watch_paragraph = bilingual_text(
            prepend_voice_prefix(pick_voice_prefix(request, "watch"), watch_zh, mode="chinese"),
            prepend_voice_prefix(pick_voice_prefix(request, "watch"), watch_en, mode="english"),
            language_mode,
        )
        caution_paragraph = bilingual_text(caution_zh, caution_en, language_mode)
        verification_paragraph = bilingual_text(verification_zh, verification_en, language_mode)
        judgment_paragraph = bilingual_text(judgment_zh, judgment_en, language_mode)
        image_paragraph = bilingual_text(
            "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
            "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
            + image_sentence(images),
            language_mode,
        )

        if request.get("draft_mode") == "image_only":
            return [
                {
                    "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                    "paragraph": bilingual_text(
                        "先只说图像层真正能支撑的那部分：" + visual_evidence_sentence(images),
                        "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                        language_mode,
                    ),
                },
                {
                    "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                    "paragraph": caution_paragraph,
                },
                {
                    "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                    "paragraph": watch_paragraph,
                },
            ]

        if framework == "deep_analysis" and section_count > 4:
            sections = [
                {
                    "heading": bilingual_heading("先看变化本身", "What Changed", language_mode),
                    "paragraph": fact_paragraph,
                },
                {
                    "heading": bilingual_heading("哪些已经确认，哪些还不能写死", "What Is Confirmed vs Still Open", language_mode),
                    "paragraph": verification_paragraph,
                },
                {
                    "heading": bilingual_heading("这轮讨论为什么没有退潮", "Why The Discussion Is Still Spreading", language_mode),
                    "paragraph": spread_paragraph,
                },
                {
                    "heading": bilingual_heading("真正的传导链条", "The Transmission Path", language_mode),
                    "paragraph": impact_paragraph,
                },
            ]
            if max_longform_mode:
                sections.append(
                    {
                        "heading": bilingual_heading("这件事的分水岭在哪", "Where The Real Divide Sits", language_mode),
                        "paragraph": judgment_paragraph,
                    }
                )
            sections.append(
                {
                    "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                    "paragraph": watch_paragraph,
                }
            )
            if request.get("draft_mode") == "image_first" and images:
                sections.insert(
                    1,
                    {
                        "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                        "paragraph": image_paragraph,
                    },
                )
            return sections

        headings = framework_headings(framework)
        paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
        if framework == "tutorial":
            paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
        elif framework == "list":
            paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
        elif framework == "opinion":
            paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

        sections = [
            {
                "heading": bilingual_heading(heading_zh, heading_en, language_mode),
                "paragraph": paragraph,
            }
            for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
        ]
        if request.get("draft_mode") == "image_first" and images:
            sections.insert(
                1,
                {
                    "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                    "paragraph": image_paragraph,
                },
            )
        return sections

    if fact_texts:
        fact_en = (
            "Start with the points that can already stand on the record: "
            + join_with_semicolons(fact_texts, f"{topic} is still developing")
            + ". Hold those steady first, then widen the frame."
        )
    else:
        fact_en = (
            f"The story around {topic} has moved beyond raw attention. "
            f"What matters more now is {join_with_commas(market_relevance_raw[:3], 'the next round of transmission and decision impact')}."
        )

    spread_en = (
        "The discussion keeps moving not because the headline sounds louder, but because "
        + join_with_semicolons(trend_texts, "the conversation is shifting from reaction to actual transmission")
        + ". Once the topic starts hitting costs, industry positioning, or execution, it stops being pure traffic."
    )
    impact_en = (
        "The thing worth tracking is not the headline heat itself, but who it reaches and which decisions it changes next. The clearest read-through now is "
        + join_with_commas(market_relevance_raw[:3], "follow-on decisions, industry positioning, and resource allocation")
        + ". That is where a topic stops being noise and becomes a variable."
    )
    watch_en = (
        "The next useful checkpoints are "
        + join_with_semicolons(watch_items, "fresh public confirmation, concrete follow-through, and whether the market keeps leaning in")
        + ". Whichever of those gets verified first will move the story forward."
    )
    caution_en = (
        "The easiest place to overstate the story is "
        + join_with_semicolons(not_proven_texts, "turning a moving inference into a settled fact")
        + ". At this stage, restraint is part of the quality bar."
    )
    image_paragraph = bilingual_text(
        "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。当前值得保留的视觉线索是：" + image_sentence(images),
        "Images can restore a sense of scene, but they should support the story instead of replacing the judgment. The strongest visual thread here is: "
        + image_sentence(images),
        language_mode,
    )
    fact_paragraph = bilingual_text("", prepend_voice_prefix(pick_voice_prefix(request, "facts"), fact_en, mode="english"), language_mode)
    spread_paragraph = bilingual_text("", prepend_voice_prefix(pick_voice_prefix(request, "spread"), spread_en, mode="english"), language_mode)
    impact_paragraph = bilingual_text("", prepend_voice_prefix(pick_voice_prefix(request, "impact"), impact_en, mode="english"), language_mode)
    watch_paragraph = bilingual_text("", prepend_voice_prefix(pick_voice_prefix(request, "watch"), watch_en, mode="english"), language_mode)
    caution_paragraph = bilingual_text("", caution_en, language_mode)

    if request.get("draft_mode") == "image_only":
        return [
            {
                "heading": bilingual_heading("图里能确认什么", "What The Images Show", language_mode),
                "paragraph": bilingual_text(
                    "",
                    "Start with the part the image layer can genuinely support: " + visual_evidence_sentence(images),
                    language_mode,
                ),
            },
            {
                "heading": bilingual_heading("图里不能替代什么", "What The Images Cannot Prove", language_mode),
                "paragraph": caution_paragraph,
            },
            {
                "heading": bilingual_heading("接下来盯什么", "What To Watch Next", language_mode),
                "paragraph": watch_paragraph,
            },
        ]

    headings = framework_headings(framework)
    paragraphs = [fact_paragraph, spread_paragraph, impact_paragraph, watch_paragraph]
    if framework == "tutorial":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]
    elif framework == "list":
        paragraphs = [fact_paragraph, impact_paragraph, caution_paragraph, watch_paragraph]
    elif framework == "opinion":
        paragraphs = [fact_paragraph, caution_paragraph, impact_paragraph, watch_paragraph]

    sections = [
        {
            "heading": bilingual_heading(heading_zh, heading_en, language_mode),
            "paragraph": paragraph,
        }
        for (heading_zh, heading_en), paragraph in zip(headings, paragraphs)
    ]
    if request.get("draft_mode") == "image_first" and images:
        sections.insert(
            1,
            {
                "heading": bilingual_heading("图里能补什么", "What The Images Add", language_mode),
                "paragraph": image_paragraph,
            },
        )
    return sections


__all__ = [
    "apply_must_avoid",
    "assemble_article_package",
    "build_article_draft",
    "build_article_markdown",
    "build_body_markdown",
    "build_citations",
    "build_image_candidates",
    "build_report_markdown",
    "build_sections",
    "build_selected_images",
    "build_source_summary",
    "build_subtitle",
    "build_title",
    "clean_string_list",
    "clean_text",
    "draft_metrics",
    "load_json",
    "merge_localized_image_candidates",
    "normalize_latest_signals",
    "normalize_request",
    "path_exists",
    "safe_dict",
    "safe_list",
    "write_json",
]


