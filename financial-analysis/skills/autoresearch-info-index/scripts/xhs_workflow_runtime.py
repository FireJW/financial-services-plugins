#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_CARD_COUNT = 7
DEFAULT_IMAGE_SIZE = "1024x1536"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("JSON input must contain an object")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return text[:48] or "xhs-package"


def resolve_package_dir(request: dict[str, Any]) -> Path:
    root = Path(request.get("output_dir") or "output/xhs-workflow").resolve()
    topic = str(request.get("topic") or request.get("title") or "xhs-package")
    stamp = str(request.get("run_id") or dt.datetime.now().strftime("%Y%m%d%H%M%S"))
    return root / f"{slugify(topic)}_{stamp}"


def _int_metric(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def normalize_benchmark(raw: dict[str, Any], index: int) -> dict[str, Any]:
    likes = _int_metric(raw, "likes", "like_count")
    collects = _int_metric(raw, "collects", "favorites", "collect_count", "favorite_count")
    comments = _int_metric(raw, "comments", "comment_count")
    shares = _int_metric(raw, "shares", "share_count")
    engagement_score = likes + collects * 1.4 + comments * 2.0 + shares * 1.2
    return {
        "rank": index + 1,
        "url": str(raw.get("url") or raw.get("note_url") or ""),
        "title": str(raw.get("title") or ""),
        "author": str(raw.get("author") or raw.get("nickname") or ""),
        "posted_at": str(raw.get("posted_at") or raw.get("created_at") or ""),
        "metrics": {
            "likes": likes,
            "collects": collects,
            "comments": comments,
            "shares": shares,
        },
        "engagement_score": round(engagement_score, 2),
        "source": raw,
    }


def rank_benchmarks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_benchmark(item, index) for index, item in enumerate(items)]
    ranked = sorted(normalized, key=lambda item: item["engagement_score"], reverse=True)
    for index, item in enumerate(ranked):
        item["rank"] = index + 1
    return ranked


def build_source_ledger(benchmarks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat()
    return [
        {
            "url": item["url"],
            "title": item["title"],
            "author": item["author"],
            "posted_at": item["posted_at"],
            "captured_at": captured_at,
            "collection_method": "manual_import",
            "metrics": item["metrics"],
        }
        for item in benchmarks
    ]


def classify_title_formula(title: str) -> str:
    if re.search(r"\d+\s*(signals?|points?|steps?|things?|rules?)", title, flags=re.IGNORECASE):
        return "numbered_signal"
    if re.search(r"\d+\s*[个条点步]", title):
        return "numbered_signal"
    lowered = title.lower()
    if any(token in lowered for token in ["why", "how", "what"]):
        return "question_hook"
    if any(token in lowered for token in ["avoid", "mistake", "warning", "risk"]):
        return "risk_warning"
    if any(token in title for token in ["为什么", "怎么", "如何"]):
        return "question_hook"
    if any(token in title for token in ["避坑", "别再", "不要"]):
        return "risk_warning"
    return "statement_hook"


def deconstruct_benchmarks(benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = []
    for item in benchmarks:
        patterns.append(
            {
                "source_url": item.get("url", ""),
                "title_formula": classify_title_formula(str(item.get("title") or "")),
                "cover_promise": "make the reader understand one concrete change quickly",
                "card_sequence": ["cover", "why_now", "key_signal", "proof", "implication", "action", "cta"],
                "visual_style": "high-contrast editorial XHS image deck",
                "interaction_trigger": "save for later comparison",
                "reuse_boundary": "reuse structure and pacing only; do not copy source wording or media",
            }
        )
    return {
        "count": len(patterns),
        "reuse_policy": "structure_only",
        "patterns": patterns,
    }


def render_deconstruction_markdown(patterns: dict[str, Any]) -> str:
    lines = [
        "# XHS Benchmark Deconstruction",
        "",
        f"Reuse policy: `{patterns.get('reuse_policy', 'structure_only')}`",
        "",
    ]
    if not patterns.get("patterns"):
        lines.extend(["No benchmark patterns were imported.", ""])
        return "\n".join(lines)

    for index, pattern in enumerate(patterns.get("patterns", []), start=1):
        lines.extend(
            [
                f"## Pattern {index}",
                "",
                f"- Source: {pattern.get('source_url', '')}",
                f"- Title formula: `{pattern.get('title_formula', '')}`",
                f"- Cover promise: {pattern.get('cover_promise', '')}",
                f"- Card sequence: {', '.join(pattern.get('card_sequence', []))}",
                f"- Interaction trigger: {pattern.get('interaction_trigger', '')}",
                f"- Reuse boundary: {pattern.get('reuse_boundary', '')}",
                "",
            ]
        )
    return "\n".join(lines)


def build_content_brief(request: dict[str, Any]) -> dict[str, Any]:
    material = dict(request.get("local_material") or {})
    topic = str(request.get("topic") or material.get("title") or "XHS note")
    key_points = [str(item) for item in material.get("key_points") or [] if str(item).strip()]
    return {
        "topic": topic,
        "title": str(material.get("title") or topic),
        "summary": str(material.get("summary") or topic),
        "key_points": key_points,
        "account_profile": request.get("account_profile") or {},
        "source_material_path": request.get("source_material_path") or "",
    }


def build_card_plan(request: dict[str, Any], patterns: dict[str, Any]) -> dict[str, Any]:
    brief = build_content_brief(request)
    topic = brief["topic"]
    key_points = list(brief["key_points"])
    while len(key_points) < 3:
        key_points.append(topic)
    cards = [
        {"index": 1, "type": "cover", "title": topic, "message": brief["summary"]},
        {"index": 2, "type": "why_now", "title": "Why it matters now", "message": key_points[0]},
        {"index": 3, "type": "signal", "title": "Signal 1", "message": key_points[0]},
        {"index": 4, "type": "proof", "title": "What proves it", "message": key_points[1]},
        {"index": 5, "type": "implication", "title": "What changes next", "message": key_points[2]},
        {"index": 6, "type": "action", "title": "How to track it", "message": "Turn the claim into checkable signals."},
        {"index": 7, "type": "cta", "title": "One-line close", "message": "Save this checklist and compare it in the next review."},
    ]
    return {
        "topic": topic,
        "card_count": len(cards),
        "patterns_used": patterns.get("patterns", [])[:3],
        "cards": cards[:DEFAULT_CARD_COUNT],
    }


def build_image_prompt(card: dict[str, Any], style_profile: dict[str, Any] | None = None) -> str:
    style = style_profile or {}
    visual_style = style.get("visual_style", "premium Xiaohongshu editorial image post")
    material_policy = style.get("material_policy", "use user-owned material when provided")
    return (
        f"{visual_style}. vertical 9:16 Xiaohongshu card. "
        f"Card type: {card.get('type')}. Title intent: {card.get('title')}. "
        f"Main message: {card.get('message')}. "
        "Use clear Chinese typography, strong hierarchy, clean composition, realistic material texture, "
        f"and no copied competitor assets. Material policy: {material_policy}."
    )


def prepare_image_generation(card_plan: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    mode = str(config.get("mode") or "dry_run")
    model = str(config.get("model") or DEFAULT_IMAGE_MODEL)
    size = str(config.get("size") or DEFAULT_IMAGE_SIZE)
    style_profile = dict(config.get("style_profile") or {})
    prompts = [
        {
            "card_index": card.get("index"),
            "card_type": card.get("type"),
            "model": model,
            "size": size,
            "prompt": build_image_prompt(card, style_profile),
        }
        for card in card_plan.get("cards", [])
    ]
    return {"mode": mode, "model": model, "size": size, "prompts": prompts, "results": []}


def generate_openai_image(prompt: str, config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when image_generation.mode=openai")
    payload = {
        "model": config.get("model") or DEFAULT_IMAGE_MODEL,
        "prompt": prompt,
        "size": config.get("size") or DEFAULT_IMAGE_SIZE,
        "quality": config.get("quality") or "medium",
        "n": 1,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.get("timeout_seconds") or 180)) as response:
        body = json.loads(response.read().decode("utf-8"))
    b64 = body["data"][0].get("b64_json")
    if not b64:
        raise ValueError("OpenAI image response did not include b64_json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(b64))
    return {"status": "generated", "path": str(output_path), "model": payload["model"]}


def maybe_generate_images(package_dir: Path, generation: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if generation["mode"] != "openai":
        return generation
    results = []
    for prompt in generation.get("prompts", []):
        output_path = package_dir / "images" / f"card-{int(prompt['card_index']):02d}.png"
        results.append(generate_openai_image(prompt["prompt"], config, output_path))
    generation["results"] = results
    return generation


def render_draft(card_plan: dict[str, Any]) -> str:
    lines = [f"# {card_plan.get('topic', 'XHS note')}", ""]
    for card in card_plan.get("cards", []):
        lines.append(f"## Card {card.get('index')}: {card.get('title')}")
        lines.append(str(card.get("message") or ""))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_caption(request: dict[str, Any], card_plan: dict[str, Any]) -> str:
    topic = card_plan.get("topic") or request.get("topic") or "This signal set"
    return (
        f"{topic}\n\n"
        "Use this image deck as a review checklist: first identify the change, "
        "then check the evidence, then track the next validation point."
    )


def render_hashtags(request: dict[str, Any]) -> str:
    base = ["#XHSImagePost", "#KnowledgeCards", "#DeepReview"]
    topic = str(request.get("topic") or "").strip()
    if topic:
        base.insert(0, "#" + re.sub(r"\s+", "", topic)[:24])
    return "\n".join(base) + "\n"


def build_qc_report(
    card_plan: dict[str, Any],
    generation: dict[str, Any],
    source_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    card_count = len(card_plan.get("cards", []))
    prompt_count = len(generation.get("prompts", []))
    checks = {
        "card_count": {"passed": 5 <= card_count <= 9, "value": card_count},
        "prompt_count": {"passed": prompt_count == card_count, "value": prompt_count},
        "source_ledger": {"passed": bool(source_ledger), "value": len(source_ledger)},
        "publish_approval": {"passed": False, "value": "manual approval required"},
    }
    return {
        "status": "needs_human_review",
        "checks": checks,
        "blocked_from_auto_publish": True,
    }


def render_qc_markdown(qc: dict[str, Any]) -> str:
    lines = ["# XHS Workflow QC", "", f"Status: `{qc.get('status')}`", ""]
    for name, check in qc.get("checks", {}).items():
        marker = "PASS" if check.get("passed") else "REVIEW"
        lines.append(f"- {marker} `{name}`: {check.get('value')}")
    lines.extend(["", "Publishing remains blocked until explicit human approval is recorded.", ""])
    return "\n".join(lines)


def run_xhs_workflow(request: dict[str, Any]) -> dict[str, Any]:
    package_dir = resolve_package_dir(request)
    package_dir.mkdir(parents=True, exist_ok=True)
    for child in ["raw", "generation", "preview", "images"]:
        (package_dir / child).mkdir(parents=True, exist_ok=True)

    benchmarks = rank_benchmarks(list(request.get("benchmarks") or []))
    source_ledger = build_source_ledger(benchmarks)
    patterns = deconstruct_benchmarks(benchmarks)
    content_brief = build_content_brief(request)
    card_plan = build_card_plan(request, patterns)
    image_config = dict(request.get("image_generation") or {})
    generation = prepare_image_generation(card_plan, image_config)
    generation = maybe_generate_images(package_dir, generation, image_config)
    qc = build_qc_report(card_plan, generation, source_ledger)

    write_json(package_dir / "request.json", request)
    write_json(package_dir / "source_ledger.json", {"sources": source_ledger})
    write_json(package_dir / "benchmarks.json", {"benchmarks": benchmarks})
    write_json(package_dir / "patterns.json", patterns)
    write_json(package_dir / "content_brief.json", content_brief)
    write_json(package_dir / "card_plan.json", card_plan)
    write_json(package_dir / "generation" / "prompts.json", {"prompts": generation["prompts"]})
    write_json(package_dir / "generation" / "model_run.json", generation)
    write_json(package_dir / "qc_report.json", qc)
    (package_dir / "deconstruction.md").write_text(render_deconstruction_markdown(patterns), encoding="utf-8")
    (package_dir / "draft.md").write_text(render_draft(card_plan), encoding="utf-8")
    (package_dir / "caption.md").write_text(render_caption(request, card_plan), encoding="utf-8")
    (package_dir / "hashtags.txt").write_text(render_hashtags(request), encoding="utf-8")
    (package_dir / "qc_report.md").write_text(render_qc_markdown(qc), encoding="utf-8")

    result = {
        "status": "ready_for_review",
        "package_dir": str(package_dir),
        "benchmark_count": len(benchmarks),
        "card_count": len(card_plan["cards"]),
        "image_generation_mode": generation["mode"],
        "qc_status": qc["status"],
        "publish_gate": {"status": "manual approval required before XHS publishing"},
    }
    write_json(package_dir / "meta.json", result)
    return result
