#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from news_index_runtime import isoformat_or_blank, parse_datetime, slugify
from runtime_paths import runtime_subdir


PROFILE_REQUEST_KEYS = (
    "author",
    "language_mode",
    "tone",
    "draft_mode",
    "image_strategy",
    "headline_hook_mode",
    "headline_hook_prefixes",
    "max_images",
    "human_signal_ratio",
    "personal_phrase_bank",
    "angle",
    "angle_zh",
    "must_include",
    "must_avoid",
)

LIST_PROFILE_REQUEST_KEYS = {"must_include", "must_avoid", "personal_phrase_bank", "headline_hook_prefixes"}
STYLE_MEMORY_TEXT_KEYS = {"target_band", "voice_summary"}
STYLE_MEMORY_LIST_KEYS = {"preferred_transitions", "must_land", "avoid_patterns", "corpus_notes"}
STYLE_MEMORY_SLOT_KEYS = ("title", "subtitle", "lede", "facts", "spread", "impact", "watch")
REFERENCE_SAMPLE_DIR = Path(__file__).resolve().parents[1] / "references" / "article-quality-samples"


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_string_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in safe_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def merge_string_lists(primary: Any, secondary: Any = None) -> list[str]:
    primary_items = clean_string_list(primary)
    secondary_items = clean_string_list(secondary)
    return primary_items + [item for item in secondary_items if item not in primary_items]


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_style_memory(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    normalized: dict[str, Any] = {}
    for key in STYLE_MEMORY_TEXT_KEYS:
        text = clean_text(payload.get(key))
        if text:
            normalized[key] = text
    for key in STYLE_MEMORY_LIST_KEYS:
        items = clean_string_list(payload.get(key))
        if items:
            normalized[key] = items

    slot_guidance_payload = safe_dict(payload.get("slot_guidance"))
    slot_guidance: dict[str, list[str]] = {}
    for slot in STYLE_MEMORY_SLOT_KEYS:
        items = clean_string_list(slot_guidance_payload.get(slot))
        if items:
            slot_guidance[slot] = items
    if slot_guidance:
        normalized["slot_guidance"] = slot_guidance

    slot_lines_payload = safe_dict(payload.get("slot_lines"))
    slot_lines: dict[str, list[str]] = {}
    for slot in STYLE_MEMORY_SLOT_KEYS:
        items = clean_string_list(slot_lines_payload.get(slot))
        if items:
            slot_lines[slot] = items
    if slot_lines:
        normalized["slot_lines"] = slot_lines

    sample_sources: list[dict[str, str]] = []
    seen_sources: set[tuple[str, str]] = set()
    for item in safe_list(payload.get("sample_sources") or payload.get("source_samples")):
        entry = safe_dict(item)
        normalized_entry = {
            "name": clean_text(entry.get("name") or entry.get("title")),
            "path": clean_text(entry.get("path")),
            "note": clean_text(entry.get("note") or entry.get("why")),
        }
        if not any(normalized_entry.values()):
            continue
        source_key = (
            normalized_entry["path"].lower(),
            normalized_entry["name"].lower(),
        )
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        sample_sources.append(normalized_entry)
    if sample_sources:
        normalized["sample_sources"] = sample_sources

    return normalized


def merge_style_memory(existing: Any, update: Any) -> dict[str, Any]:
    base = normalize_style_memory(existing)
    incoming = normalize_style_memory(update)
    if not base:
        return incoming
    if not incoming:
        return base

    merged: dict[str, Any] = {}
    for key in STYLE_MEMORY_TEXT_KEYS:
        text = clean_text(incoming.get(key) or base.get(key))
        if text:
            merged[key] = text
    for key in STYLE_MEMORY_LIST_KEYS:
        items = merge_string_lists(incoming.get(key), base.get(key))
        if items:
            merged[key] = items

    for key in ("slot_guidance", "slot_lines"):
        slot_payload: dict[str, list[str]] = {}
        incoming_slots = safe_dict(incoming.get(key))
        base_slots = safe_dict(base.get(key))
        for slot in STYLE_MEMORY_SLOT_KEYS:
            items = merge_string_lists(incoming_slots.get(slot), base_slots.get(slot))
            if items:
                slot_payload[slot] = items
        if slot_payload:
            merged[key] = slot_payload

    merged_sources: list[dict[str, str]] = []
    seen_sources: set[tuple[str, str]] = set()
    for raw_item in safe_list(incoming.get("sample_sources")) + safe_list(base.get("sample_sources")):
        entry = {
            "name": clean_text(safe_dict(raw_item).get("name")),
            "path": clean_text(safe_dict(raw_item).get("path")),
            "note": clean_text(safe_dict(raw_item).get("note")),
        }
        if not any(entry.values()):
            continue
        source_key = (entry["path"].lower(), entry["name"].lower())
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        merged_sources.append(entry)
    if merged_sources:
        merged["sample_sources"] = merged_sources

    return merged


def apply_style_memory_defaults(request: dict[str, Any], style_memory: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(request)
    if not style_memory:
        return merged
    merged["personal_phrase_bank"] = merge_string_lists(style_memory.get("preferred_transitions"), merged.get("personal_phrase_bank"))
    merged["must_include"] = merge_string_lists(style_memory.get("must_land"), merged.get("must_include"))
    merged["must_avoid"] = merge_string_lists(style_memory.get("avoid_patterns"), merged.get("must_avoid"))
    merged["style_memory"] = deepcopy(style_memory)
    return merged


def sample_source_entry(name: str, filename: str, note: str) -> dict[str, str]:
    return {
        "name": clean_text(name),
        "path": str(REFERENCE_SAMPLE_DIR / filename),
        "note": clean_text(note),
    }


GENERAL_COMMENTARY_STYLE_MEMORY = {
    "target_band": "commentary_variable_first",
    "voice_summary": (
        "Lead with one clear judgment, not chronology. Use one anchor event or signal, "
        "then explain why it changes the variable readers should track."
    ),
    "preferred_transitions": [
        "先看结论",
        "表面上看",
        "真正值得注意的",
    ],
    "must_land": [
        "先用一句总判断说明这条新闻为什么值得写",
        "用一个最强锚点事件、交易或经营信号带出主线",
        "把新闻翻译成后续值得跟踪的变量，而不是只复述标题",
    ],
    "avoid_patterns": [
        "只按时间顺序复述新闻，不解释为什么重要",
        "只堆数字和公司名，不说明变量传导",
    ],
}


MACRO_CONFLICT_SAMPLE_SOURCES = [
    sample_source_entry(
        "HFI Research",
        "macro-oil-hfi-research.md",
        "Use for physical market framing, inventory stress, and oil-market-specific voice.",
    ),
    sample_source_entry(
        "Bloomberg Opinion / Javier Blas",
        "macro-oil-javier-blas-real-oil-price.md",
        "Use for separating quoted oil price from actual market stress and pricing mechanics.",
    ),
    sample_source_entry(
        "Bloomberg Opinion / Javier Blas",
        "macro-oil-javier-blas-hormuz-blueprints.md",
        "Use for writing geopolitics as market structure rather than headline chronology.",
    ),
    sample_source_entry(
        "Citi Private Bank",
        "macro-oil-citi-energy-shock.md",
        "Use for oil to inflation to Fed to cross-asset transmission.",
    ),
    sample_source_entry(
        "JKempEnergy.com / John Kemp",
        "macro-oil-jkempenergy-archive.md",
        "Use for evidence density, balances, infrastructure, and market plumbing discipline.",
    ),
]


TECH_INFRA_STYLE_MEMORY = {
    "target_band": "tech_supply_chain_commentary",
    "voice_summary": (
        "Treat technology headlines as supply-chain and deployment variables. "
        "Start with one thesis, anchor on one transaction, partnership, capex plan, "
        "or capacity signal, then follow the flow of money, orders, capacity, and infrastructure."
    ),
    "preferred_transitions": [
        "往下拆",
        "顺着钱的流向看下去",
        "真正值得重估的",
    ],
    "must_land": [
        "把公司新闻翻译成资金流向、订单流向、产能流向或部署变量",
        "解释这条线最终落到哪些芯片、封装、服务器、云资源或上游环节",
        "不要停在模型热度，要落到资本开支、部署成本、供给约束或基础设施受益者",
    ],
    "avoid_patterns": [
        "只写模型热度，不落到部署、产能、资本开支或供应链",
        "把融资或合作新闻直接等同于长期产业胜负",
    ],
    "corpus_notes": [
        "Approved benchmark set emphasizes capital intensity, supply-chain consequences, and valuation tension instead of generic AI enthusiasm.",
    ],
    "slot_guidance": {
        "lede": [
            "用一句判断说明这不是普通公司新闻，而是一条会传导到上游变量的信号",
        ],
        "facts": [
            "先给出一个最强锚点交易、合作、capex 或 capacity signal",
        ],
        "impact": [
            "顺着钱流、订单流、产能流往上游写，讲清楚谁会被重新定价",
        ],
        "watch": [
            "把后续跟踪点落到 GPU、TPU、封装、服务器、云厂商或数据中心约束",
        ],
    },
    "sample_sources": [
        sample_source_entry(
            "Stratechery / Ben Thompson",
            "tech-ai-stratechery-google-cloud-llms.md",
            "Use for turning earnings into strategy and capex consequences rather than recap.",
        ),
        sample_source_entry(
            "Stratechery / Ben Thompson",
            "tech-ai-stratechery-amazon-capex.md",
            "Use for handling capex anxiety, investor debate, and strategic nuance in one piece.",
        ),
        sample_source_entry(
            "SemiAnalysis",
            "tech-ai-semianalysis-silicon-shortage.md",
            "Use for bottleneck analysis, silicon constraints, and hyperscaler capex reset logic.",
        ),
        sample_source_entry(
            "SemiAnalysis",
            "tech-ai-semianalysis-memory-mania.md",
            "Use for writing second-order supply-chain consequences instead of surface hype.",
        ),
        sample_source_entry(
            "Citi Private Bank",
            "tech-ai-citi-capex-returns.md",
            "Use for linking AI capex to returns, beneficiaries, and macro constraints.",
        ),
    ],
}


MACRO_CONFLICT_STYLE_MEMORY = {
    "target_band": "macro_conflict_transmission",
    "voice_summary": (
        "Treat macro conflict topics as pricing-chain stories. Start with one hard judgment, "
        "anchor on the variable that moved first, then walk through oil, inflation expectations, "
        "Fed path, discount rates, and the equity or cross-asset consequence."
    ),
    "preferred_transitions": [
        "先看结论",
        "真正要重估的",
        "顺着这条传导链往下看",
    ],
    "must_land": [
        "把事件翻译成油价、通胀预期、Fed 路径和权益贴现率的传导链",
        "区分物理供应扰动、风险溢价和二级市场叙事，不要只写 headline",
        "结尾必须落到接下来该盯什么的市场观察项，而不是停在事件总结",
    ],
    "avoid_patterns": [
        "只复述地缘冲突经过，不解释它如何改写市场定价框架",
        "把 OPEC、制裁或航运当作并列信息堆砌，不建立主次和传导顺序",
    ],
    "corpus_notes": [
        "Approved benchmark set emphasizes market transmission, physical-vs-financial pricing, and policy-to-asset linkage.",
    ],
    "slot_guidance": {
        "lede": [
            "开头先说这不是普通 headline，而是一条会重写市场定价顺序的变量。",
        ],
        "facts": [
            "先钉住最强锚点变量，比如 Brent、运价、库存、保险或供应中断线索。",
        ],
        "spread": [
            "把背景因素降级成结构解释，不要让背景抢走主线。",
        ],
        "impact": [
            "从油价到通胀预期，再到 Fed 路径、长端利率、贴现率和权益估值，按顺序写清。",
        ],
        "watch": [
            "最后给出 3 个后续观察点，优先价格曲线、政策路径和资产内部结构。",
        ],
    },
    "sample_sources": MACRO_CONFLICT_SAMPLE_SOURCES,
}


TECH_TOPIC_TOKENS = (
    "ai",
    "agentic ai",
    "agent",
    "model",
    "llm",
    "gpu",
    "tpu",
    "semiconductor",
    "chip",
    "chips",
    "datacenter",
    "data center",
    "cloud",
    "inference",
    "training",
    "broadcom",
    "nvidia",
    "anthropic",
    "google cloud",
    "tsmc",
    "intel",
    "台积",
    "半导体",
    "芯片",
    "算力",
    "云厂商",
    "推理",
    "训练",
    "封装",
    "服务器",
    "数据中心",
    "昇腾",
    "英伟达",
    "博通",
    "台积电",
)


MACRO_CONFLICT_TOPIC_TOKENS = (
    "hormuz",
    "strait of hormuz",
    "brent",
    "wti",
    "oil",
    "crude",
    "opec",
    "opec+",
    "iran",
    "inflation expectations",
    "fed",
    "discount rate",
    "equities",
    "risk premium",
    "tanker",
    "shipping",
    "lng",
    "霍尔木兹",
    "布伦特",
    "油价",
    "原油",
    "伊朗",
    "通胀预期",
    "美联储",
    "贴现率",
    "折现率",
    "风险溢价",
    "航运",
    "油运",
    "股市",
)


def topic_lane_text(request: dict[str, Any], extra_text: Any = None) -> str:
    parts = [
        clean_text(request.get("topic")),
        clean_text(request.get("title_hint")),
        clean_text(request.get("title_hint_zh")),
        clean_text(request.get("subtitle_hint")),
        clean_text(request.get("subtitle_hint_zh")),
        clean_text(request.get("angle")),
        clean_text(request.get("angle_zh")),
    ]
    for item in clean_string_list(request.get("must_include")):
        parts.append(item)
    if extra_text not in (None, "", [], {}):
        if isinstance(extra_text, (list, tuple, set)):
            parts.extend(clean_text(item) for item in extra_text)
        else:
            parts.append(clean_text(extra_text))
    return " ".join(part for part in parts if part).lower()


def is_technology_topic(text: str) -> bool:
    lowered = clean_text(text).lower()
    if not lowered:
        return False
    return any(token in lowered for token in TECH_TOPIC_TOKENS)


def is_macro_conflict_topic(text: str) -> bool:
    lowered = clean_text(text).lower()
    if not lowered:
        return False
    return any(token in lowered for token in MACRO_CONFLICT_TOPIC_TOKENS)


def apply_topic_lane_defaults(request: dict[str, Any], *, extra_text: Any = None) -> dict[str, Any]:
    merged = deepcopy(request)
    lane_text = topic_lane_text(merged, extra_text)
    if is_technology_topic(lane_text):
        style_memory = merge_style_memory(GENERAL_COMMENTARY_STYLE_MEMORY, safe_dict(merged.get("style_memory")))
        style_memory = merge_style_memory(style_memory, TECH_INFRA_STYLE_MEMORY)
        if clean_text(merged.get("article_framework")) in {"", "auto"}:
            merged["article_framework"] = "deep_analysis"
        return apply_style_memory_defaults(merged, style_memory)
    if is_macro_conflict_topic(lane_text):
        style_memory = merge_style_memory(GENERAL_COMMENTARY_STYLE_MEMORY, safe_dict(merged.get("style_memory")))
        style_memory = merge_style_memory(style_memory, MACRO_CONFLICT_STYLE_MEMORY)
        if clean_text(merged.get("article_framework")) in {"", "auto"}:
            merged["article_framework"] = "deep_analysis"
        return apply_style_memory_defaults(merged, style_memory)

    return merged


def default_profile_dir() -> Path:
    return runtime_subdir("article-feedback-profiles")


def resolve_profile_dir(path_value: Any) -> Path:
    path_text = clean_text(path_value)
    return Path(path_text).expanduser() if path_text else default_profile_dir()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8-sig")


def global_profile_path(profile_dir: Path) -> Path:
    return profile_dir / "global.json"


def topic_profile_path(profile_dir: Path, topic: str) -> Path:
    return profile_dir / f"topic-{slugify(clean_text(topic), 'topic')}.json"


def profile_history_root(profile_dir: Path) -> Path:
    return profile_dir / "history"


def profile_history_dir(profile_dir: Path, scope: str, topic: str) -> Path:
    if scope == "global":
        return profile_history_root(profile_dir) / "global"
    return profile_history_root(profile_dir) / f"topic-{slugify(clean_text(topic), 'topic')}"


def list_history_snapshots(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.glob("*.json") if item.is_file())


def history_timestamp(analysis_time: Any) -> str:
    parsed = parse_datetime(analysis_time, fallback=None)
    if parsed is None:
        return "snapshot"
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def next_history_snapshot_path(history_dir: Path, analysis_time: Any) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = history_timestamp(analysis_time)
    candidate = history_dir / f"{stamp}.json"
    index = 1
    while candidate.exists():
        candidate = history_dir / f"{stamp}-{index}.json"
        index += 1
    return candidate


def backup_profile_snapshot(profile_dir: Path, path: Path, payload: dict[str, Any], *, scope: str, topic: str, analysis_time: Any) -> str:
    if not path.exists():
        return ""
    history_dir = profile_history_dir(profile_dir, scope, topic)
    snapshot_path = next_history_snapshot_path(history_dir, analysis_time)
    snapshot_payload = {
        "scope": scope,
        "topic": clean_text(topic),
        "source_path": str(path),
        "backed_up_at": isoformat_or_blank(analysis_time),
        "payload": deepcopy(payload),
    }
    write_json_file(snapshot_path, snapshot_payload)
    return str(snapshot_path)


def load_feedback_profiles(profile_dir: Path, topic: str) -> dict[str, Any]:
    global_path = global_profile_path(profile_dir)
    topic_path = topic_profile_path(profile_dir, topic)
    global_profile = load_json_file(global_path)
    topic_profile = load_json_file(topic_path)
    applied_paths = [str(path) for path in (global_path, topic_path) if path.exists()]
    return {
        "global": global_profile,
        "topic": topic_profile,
        "applied_paths": applied_paths,
    }


def feedback_profile_status(profile_dir: Path, topic: str, *, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    loaded_profiles = profiles if isinstance(profiles, dict) else load_feedback_profiles(profile_dir, topic)
    global_path = global_profile_path(profile_dir)
    topic_path = topic_profile_path(profile_dir, topic)
    global_history_dir = profile_history_dir(profile_dir, "global", topic)
    topic_history_dir = profile_history_dir(profile_dir, "topic", topic)
    global_history_paths = list_history_snapshots(global_history_dir)
    topic_history_paths = list_history_snapshots(topic_history_dir)
    global_style_memory = normalize_style_memory(safe_dict(loaded_profiles.get("global")).get("style_memory"))
    topic_style_memory = normalize_style_memory(safe_dict(loaded_profiles.get("topic")).get("style_memory"))
    return {
        "profile_dir": str(profile_dir),
        "topic": clean_text(topic),
        "global_profile_path": str(global_path),
        "topic_profile_path": str(topic_path),
        "global_exists": global_path.exists(),
        "topic_exists": topic_path.exists(),
        "applied_paths": clean_string_list(loaded_profiles.get("applied_paths")),
        "history_root": str(profile_history_root(profile_dir)),
        "global_history_dir": str(global_history_dir),
        "topic_history_dir": str(topic_history_dir),
        "global_history_count": len(global_history_paths),
        "topic_history_count": len(topic_history_paths),
        "latest_global_backup_path": str(global_history_paths[-1]) if global_history_paths else "",
        "latest_topic_backup_path": str(topic_history_paths[-1]) if topic_history_paths else "",
        "global_style_memory_keys": sorted(global_style_memory.keys()),
        "topic_style_memory_keys": sorted(topic_style_memory.keys()),
    }


def merge_request_with_profiles(request: dict[str, Any], profiles: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(request)
    profile_style_memory: dict[str, Any] = {}
    for profile in (safe_dict(profiles.get("global")), safe_dict(profiles.get("topic"))):
        defaults = safe_dict(profile.get("request_defaults"))
        profile_style_memory = merge_style_memory(profile_style_memory, safe_dict(profile.get("style_memory")))
        for key in PROFILE_REQUEST_KEYS:
            if key in LIST_PROFILE_REQUEST_KEYS:
                merged[key] = clean_string_list(defaults.get(key)) + [item for item in clean_string_list(merged.get(key)) if item not in clean_string_list(defaults.get(key))]
                continue
            current = merged.get(key)
            if current not in (None, "", []):
                continue
            if defaults.get(key) not in (None, "", []):
                merged[key] = defaults.get(key)
    merged_style_memory = merge_style_memory(profile_style_memory, safe_dict(merged.get("style_memory")))
    merged = apply_style_memory_defaults(merged, merged_style_memory)
    merged["applied_feedback_profiles"] = clean_string_list(profiles.get("applied_paths"))
    return merged


def normalize_profile_feedback(value: Any) -> dict[str, Any]:
    payload = safe_dict(value)
    scope = clean_text(payload.get("scope")).lower()
    if scope not in {"global", "topic", "both"}:
        scope = "none"
    defaults = safe_dict(payload.get("defaults"))
    normalized_defaults: dict[str, Any] = {}
    for key in PROFILE_REQUEST_KEYS:
        if key in LIST_PROFILE_REQUEST_KEYS:
            cleaned = clean_string_list(defaults.get(key))
            if cleaned:
                normalized_defaults[key] = cleaned
        else:
            text = defaults.get(key)
            if text not in (None, "", []):
                normalized_defaults[key] = text
    normalized = {
        "scope": scope,
        "defaults": normalized_defaults,
        "notes": clean_string_list(payload.get("notes")),
        "use_current_request_defaults": parse_bool(
            payload.get("use_current_request_defaults", payload.get("inherit_current_request_defaults")),
            default=False,
        ),
    }
    style_memory = normalize_style_memory(payload.get("style_memory"))
    if style_memory:
        normalized["style_memory"] = style_memory
    return normalized


def request_defaults_from_request(request: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for key in PROFILE_REQUEST_KEYS:
        if key in LIST_PROFILE_REQUEST_KEYS:
            cleaned = clean_string_list(request.get(key))
            if cleaned:
                defaults[key] = cleaned
            continue
        value = request.get(key)
        if value not in (None, "", []):
            defaults[key] = value
    return defaults


def merge_profile_payload(existing: dict[str, Any], update: dict[str, Any], *, scope: str, topic: str, analysis_time: Any) -> dict[str, Any]:
    merged = deepcopy(existing)
    merged["scope"] = scope
    merged["topic"] = clean_text(topic)
    merged["updated_at"] = isoformat_or_blank(analysis_time)
    merged["request_defaults"] = {**safe_dict(existing.get("request_defaults")), **safe_dict(update.get("defaults"))}
    merged["notes"] = clean_string_list(safe_list(existing.get("notes")) + safe_list(update.get("notes")))
    style_memory = merge_style_memory(existing.get("style_memory"), update.get("style_memory"))
    if style_memory:
        merged["style_memory"] = style_memory
    merged["revision_count"] = int(existing.get("revision_count", 0) or 0) + 1
    return merged


def save_feedback_profiles_detailed(
    profile_dir: Path,
    topic: str,
    analysis_time: Any,
    profile_feedback: dict[str, Any],
    request_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    update = normalize_profile_feedback(profile_feedback)
    if update.get("scope") == "none":
        return {"saved_paths": [], "backup_paths": []}
    merged_defaults = {}
    if update.get("use_current_request_defaults"):
        merged_defaults = request_defaults_from_request(safe_dict(request_defaults))
    for key in PROFILE_REQUEST_KEYS:
        if key in LIST_PROFILE_REQUEST_KEYS:
            merged = clean_string_list(merged_defaults.get(key)) + [
                item for item in clean_string_list(update["defaults"].get(key)) if item not in clean_string_list(merged_defaults.get(key))
            ]
            if merged:
                merged_defaults[key] = merged
            elif key in merged_defaults:
                del merged_defaults[key]
            continue
        if update["defaults"].get(key) not in (None, "", []):
            merged_defaults[key] = update["defaults"][key]
    update = {**update, "defaults": merged_defaults}
    written: list[str] = []
    backup_paths: list[str] = []
    profile_dir.mkdir(parents=True, exist_ok=True)
    targets: list[tuple[str, Path]] = []
    if update["scope"] in {"global", "both"}:
        targets.append(("global", global_profile_path(profile_dir)))
    if update["scope"] in {"topic", "both"}:
        targets.append(("topic", topic_profile_path(profile_dir, topic)))
    for scope, path in targets:
        existing = load_json_file(path)
        backup_path = backup_profile_snapshot(profile_dir, path, existing, scope=scope, topic=topic, analysis_time=analysis_time)
        if backup_path:
            backup_paths.append(backup_path)
        merged = merge_profile_payload(existing, update, scope=scope, topic=topic, analysis_time=analysis_time)
        write_json_file(path, merged)
        written.append(str(path))
    return {"saved_paths": written, "backup_paths": backup_paths}


def save_feedback_profiles(
    profile_dir: Path,
    topic: str,
    analysis_time: Any,
    profile_feedback: dict[str, Any],
    request_defaults: dict[str, Any] | None = None,
) -> list[str]:
    return clean_string_list(
        save_feedback_profiles_detailed(
            profile_dir,
            topic,
            analysis_time,
            profile_feedback,
            request_defaults=request_defaults,
        ).get("saved_paths")
    )


__all__ = [
    "apply_style_memory_defaults",
    "clean_string_list",
    "clean_text",
    "default_profile_dir",
    "feedback_profile_status",
    "load_feedback_profiles",
    "merge_style_memory",
    "merge_request_with_profiles",
    "normalize_profile_feedback",
    "normalize_style_memory",
    "request_defaults_from_request",
    "resolve_profile_dir",
    "save_feedback_profiles",
    "save_feedback_profiles_detailed",
]
