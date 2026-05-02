#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import json
import mimetypes
import os
import re
import subprocess
import urllib.request
import uuid
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


def extract_benchmark_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("benchmarks", "feeds", "items", "notes", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, (dict, list)):
        return extract_benchmark_items(data)
    return []


def load_benchmark_inputs(request: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = str(request.get("benchmark_source") or "inline")
    benchmark_file = request.get("benchmark_file")
    if benchmark_file:
        path = Path(str(benchmark_file)).resolve()
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        items = extract_benchmark_items(payload)
        return rank_benchmarks(items), {
            "source": source,
            "count": len(items),
            "path": str(path),
        }
    items = extract_benchmark_items(request.get("benchmarks") or [])
    return rank_benchmarks(items), {
        "source": source,
        "count": len(items),
        "path": "",
    }


def build_readiness_report(request: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env if env is not None else os.environ
    image_config = dict(request.get("image_generation") or {})
    mode = str(image_config.get("mode") or "dry_run")
    benchmark_file = request.get("benchmark_file")
    inline_benchmarks = extract_benchmark_items(request.get("benchmarks") or [])
    benchmark_file_exists = True
    if benchmark_file:
        benchmark_file_exists = Path(str(benchmark_file)).resolve().exists()
    benchmark_input_ok = (bool(benchmark_file) and benchmark_file_exists) or bool(inline_benchmarks)

    api_key_ok = True
    if mode == "openai":
        api_key_ok = bool(image_config.get("api_key") or env.get("OPENAI_API_KEY"))

    reference_images = normalize_reference_images(list(image_config.get("reference_images") or []))
    reference_images_ok = True
    missing_references = []
    if mode == "openai":
        for reference in reference_images:
            path_text = reference.get("path", "")
            if path_text.startswith("http://") or path_text.startswith("https://"):
                missing_references.append(f"remote URL not supported for openai edits: {path_text}")
                continue
            if not Path(path_text).resolve().exists():
                missing_references.append(path_text)
        reference_images_ok = not missing_references

    output_dir = Path(str(request.get("output_dir") or "output/xhs-workflow")).resolve()
    output_parent = output_dir if output_dir.exists() else output_dir.parent
    output_dir_ok = output_parent.exists()

    checks = {
        "benchmark_input": {"passed": benchmark_input_ok, "value": len(inline_benchmarks) if not benchmark_file else str(benchmark_file)},
        "benchmark_file": {"passed": benchmark_file_exists, "value": str(benchmark_file or "")},
        "openai_api_key": {"passed": api_key_ok, "value": "required" if mode == "openai" else "not_required"},
        "reference_images": {"passed": reference_images_ok, "value": len(reference_images), "missing": missing_references},
        "output_dir": {"passed": output_dir_ok, "value": str(output_dir)},
    }
    blockers = [name for name, check in checks.items() if not check["passed"]]
    return {
        "status": "blocked" if blockers else "ready",
        "mode": mode,
        "checks": checks,
        "blockers": blockers,
        "next_action": "fix blockers before generation" if blockers else "safe to run dry-run package generation",
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


def build_collector_plan(request: dict[str, Any]) -> dict[str, Any]:
    collector = dict(request.get("collector") or {})
    collector_type = str(collector.get("type") or "").strip()
    if not collector_type:
        return {"status": "not_configured", "source": "", "command": [], "cwd": ""}
    if collector_type != "xiaohongshu-skills":
        return {
            "status": "unsupported",
            "source": collector_type,
            "command": [],
            "cwd": "",
            "message": "Only xiaohongshu-skills collector plans are supported in this workflow.",
        }

    skills_dir_text = str(collector.get("skills_dir") or "").strip()
    skills_dir = Path(skills_dir_text).resolve() if skills_dir_text else Path(".").resolve()
    keyword = str(collector.get("keyword") or request.get("topic") or "").strip()
    sort_by = str(collector.get("sort_by") or "最多点赞")
    note_type = str(collector.get("note_type") or "图文")
    limit = int(collector.get("limit") or 20)
    command = [
        "python",
        "scripts/cli.py",
        "search-feeds",
        "--keyword",
        keyword,
        "--sort-by",
        sort_by,
        "--note-type",
        note_type,
        "--limit",
        str(limit),
    ]
    return {
        "status": "ready" if skills_dir.exists() and keyword else "needs_configuration",
        "source": "xiaohongshu-skills.search-feeds",
        "cwd": str(skills_dir),
        "command": command,
        "output_next_step": "Save the JSON result and pass it back with --benchmark-file.",
    }


def build_publish_preview_plan(
    request: dict[str, Any],
    package_dir: Path,
    card_plan: dict[str, Any],
) -> dict[str, Any]:
    publish = dict(request.get("publish") or {})
    publish_type = str(publish.get("type") or "").strip()
    if not publish_type:
        return {"status": "not_configured", "source": "", "command": [], "cwd": "", "click_publish": False}
    if publish_type != "xiaohongshu-skills":
        return {
            "status": "unsupported",
            "source": publish_type,
            "command": [],
            "cwd": "",
            "click_publish": False,
            "message": "Only xiaohongshu-skills publish preview plans are supported.",
        }

    image_paths = sorted((package_dir / "images").glob("*.png"))
    if not image_paths:
        return {
            "status": "images_missing",
            "source": "xiaohongshu-skills.fill-publish",
            "command": [],
            "cwd": str(Path(str(publish.get("skills_dir") or ".")).resolve()),
            "click_publish": False,
            "message": "Generate or provide XHS card images before creating a publish preview.",
        }

    title_file = package_dir / "publish" / "title.txt"
    content_file = package_dir / "publish" / "content.txt"
    title_file.parent.mkdir(parents=True, exist_ok=True)
    title_file.write_text(str(publish.get("title") or card_plan.get("topic") or "XHS note"), encoding="utf-8")
    caption_path = package_dir / "caption.md"
    hashtags_path = package_dir / "hashtags.txt"
    caption = caption_path.read_text(encoding="utf-8") if caption_path.exists() else ""
    hashtags = hashtags_path.read_text(encoding="utf-8") if hashtags_path.exists() else ""
    content_file.write_text((caption + "\n" + hashtags).strip() + "\n", encoding="utf-8")

    skills_dir = Path(str(publish.get("skills_dir") or ".")).resolve()
    command = [
        "python",
        "scripts/cli.py",
        "fill-publish",
        "--title-file",
        str(title_file),
        "--content-file",
        str(content_file),
        "--images",
        *[str(path) for path in image_paths],
    ]
    return {
        "status": "ready_preview",
        "source": "xiaohongshu-skills.fill-publish",
        "cwd": str(skills_dir),
        "command": command,
        "click_publish": False,
        "image_count": len(image_paths),
        "title_file": str(title_file),
        "content_file": str(content_file),
    }


def build_performance_collection_plan(request: dict[str, Any]) -> dict[str, Any]:
    collection = dict(request.get("performance_collection") or {})
    collection_type = str(collection.get("type") or "").strip()
    if not collection_type:
        return {"status": "not_configured", "source": "", "command": [], "cwd": ""}
    if collection_type != "xiaohongshu-skills":
        return {
            "status": "unsupported",
            "source": collection_type,
            "command": [],
            "cwd": "",
            "message": "Only xiaohongshu-skills performance collection plans are supported.",
        }
    skills_dir = Path(str(collection.get("skills_dir") or ".")).resolve()
    feed_id = str(collection.get("feed_id") or "").strip()
    xsec_token = str(collection.get("xsec_token") or "").strip()
    command = [
        "python",
        "scripts/cli.py",
        "get-feed-detail",
        "--feed-id",
        feed_id,
        "--xsec-token",
        xsec_token,
    ]
    return {
        "status": "ready" if skills_dir.exists() and feed_id and xsec_token else "needs_configuration",
        "source": "xiaohongshu-skills.get-feed-detail",
        "cwd": str(skills_dir),
        "command": command,
        "output_next_step": "Save the JSON result and pass it back as performance_file.",
    }


def load_performance_metrics(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("performance_file"):
        path = Path(str(request["performance_file"])).resolve()
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        note = dict(payload.get("note") or payload.get("data") or {})
        interactions = dict(payload.get("interactions") or note.get("interactions") or payload.get("stats") or {})
        return {
            "post_url": str(note.get("url") or payload.get("post_url") or ""),
            "after_24h": {
                "likes": _int_metric(interactions, "liked_count", "likes", "like_count"),
                "collects": _int_metric(interactions, "collected_count", "collects", "collect_count"),
                "comments": _int_metric(interactions, "comment_count", "comments"),
                "shares": _int_metric(interactions, "share_count", "shares"),
            },
            "notes": [f"imported from {path}"],
        }
    return dict(request.get("performance_metrics") or {})


def run_collector_plan(
    plan: dict[str, Any],
    output_path: Path,
    runner: Any = subprocess.run,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    if plan.get("status") != "ready":
        return {
            "status": "skipped",
            "reason": f"collector plan is {plan.get('status')}",
            "source": plan.get("source", ""),
            "output_path": str(output_path),
        }
    completed = runner(
        list(plan.get("command") or []),
        cwd=str(plan.get("cwd") or "."),
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "status": "collector_failed",
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "returncode": completed.returncode,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "status": "failed",
            "source": plan.get("source", ""),
            "returncode": completed.returncode,
            "stderr": completed.stderr,
            "output_path": str(output_path),
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(completed.stdout, encoding="utf-8")
    try:
        payload = json.loads(completed.stdout or "{}")
        count = len(extract_benchmark_items(payload))
    except json.JSONDecodeError:
        count = 0
    return {
        "status": "collected",
        "source": plan.get("source", ""),
        "count": count,
        "output_path": str(output_path),
    }


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


def normalize_reference_images(items: list[Any]) -> list[dict[str, str]]:
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"path": item, "role": "source_material"})
            continue
        if isinstance(item, dict):
            path = str(item.get("path") or item.get("url") or "").strip()
            if not path:
                continue
            normalized.append(
                {
                    "path": path,
                    "role": str(item.get("role") or "source_material"),
                }
            )
    return normalized


def build_image_prompt(
    card: dict[str, Any],
    style_profile: dict[str, Any] | None = None,
    reference_images: list[dict[str, str]] | None = None,
) -> str:
    style = style_profile or {}
    visual_style = style.get("visual_style", "premium Xiaohongshu editorial image post")
    material_policy = style.get("material_policy", "use user-owned material when provided")
    reference_line = (
        "Use the provided reference images as the primary visual material; preserve their concrete details while improving composition. "
        if reference_images
        else ""
    )
    return (
        f"{visual_style}. vertical 9:16 Xiaohongshu card. "
        f"Card type: {card.get('type')}. Title intent: {card.get('title')}. "
        f"Main message: {card.get('message')}. "
        f"{reference_line}"
        "Use clear Chinese typography, strong hierarchy, clean composition, realistic material texture, "
        f"and no copied competitor assets. Material policy: {material_policy}."
    )


def prepare_image_generation(card_plan: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    mode = str(config.get("mode") or "dry_run")
    model = str(config.get("model") or DEFAULT_IMAGE_MODEL)
    size = str(config.get("size") or DEFAULT_IMAGE_SIZE)
    style_profile = dict(config.get("style_profile") or {})
    reference_images = normalize_reference_images(list(config.get("reference_images") or []))
    prompts = [
        {
            "card_index": card.get("index"),
            "card_type": card.get("type"),
            "model": model,
            "size": size,
            "reference_images": reference_images,
            "prompt": build_image_prompt(card, style_profile, reference_images),
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


def build_multipart_form_data(
    fields: dict[str, Any],
    files: list[dict[str, Any]],
    boundary: str | None = None,
) -> tuple[bytes, str]:
    boundary = boundary or f"----xhsworkflow{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for file_item in files:
        field = str(file_item["field"])
        filename = str(file_item["filename"])
        content_type = str(file_item.get("content_type") or "application/octet-stream")
        content = bytes(file_item["content"])
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def build_reference_image_files(reference_images: list[dict[str, str]]) -> list[dict[str, Any]]:
    files = []
    for reference in reference_images:
        path_text = reference.get("path", "")
        if path_text.startswith("http://") or path_text.startswith("https://"):
            raise ValueError("OpenAI image edit currently requires local reference image paths, not URLs")
        path = Path(path_text).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Reference image not found: {path}")
        files.append(
            {
                "field": "image[]",
                "filename": path.name,
                "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "content": path.read_bytes(),
            }
        )
    return files


def generate_openai_image_edit(
    prompt: str,
    reference_images: list[dict[str, str]],
    config: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when image_generation.mode=openai")
    fields = {
        "model": config.get("model") or DEFAULT_IMAGE_MODEL,
        "prompt": prompt,
        "size": config.get("size") or DEFAULT_IMAGE_SIZE,
        "quality": config.get("quality") or "medium",
        "n": 1,
    }
    body, content_type = build_multipart_form_data(fields, build_reference_image_files(reference_images))
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/edits",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.get("timeout_seconds") or 180)) as response:
        response_body = json.loads(response.read().decode("utf-8"))
    b64 = response_body["data"][0].get("b64_json")
    if not b64:
        raise ValueError("OpenAI image edit response did not include b64_json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(b64))
    return {"status": "edited", "path": str(output_path), "model": fields["model"]}


def maybe_generate_images(package_dir: Path, generation: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if generation["mode"] != "openai":
        return generation
    results = []
    for prompt in generation.get("prompts", []):
        output_path = package_dir / "images" / f"card-{int(prompt['card_index']):02d}.png"
        if prompt.get("reference_images"):
            result = generate_openai_image_edit(prompt["prompt"], prompt["reference_images"], config, output_path)
            result["route"] = result.get("route") or "openai_images_edits"
        else:
            result = generate_openai_image(prompt["prompt"], config, output_path)
            result["route"] = result.get("route") or "openai_images_generations"
        result["card_index"] = prompt.get("card_index")
        results.append(result)
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


def _metric(payload: dict[str, Any], key: str) -> int:
    try:
        return int(float(payload.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def build_performance_review(request: dict[str, Any]) -> dict[str, Any]:
    metrics = load_performance_metrics(request)
    if not metrics:
        return {"status": "not_provided", "metrics": {}, "scores": {}, "notes": []}
    after_24h = dict(metrics.get("after_24h") or metrics.get("latest") or {})
    likes = _metric(after_24h, "likes")
    collects = _metric(after_24h, "collects")
    comments = _metric(after_24h, "comments")
    shares = _metric(after_24h, "shares")
    total_engagement = likes + collects + comments + shares
    save_intent_score = round((collects * 1.5 + comments * 0.8 + shares) / max(likes, 1), 3)
    return {
        "status": "recorded",
        "metrics": metrics,
        "scores": {
            "total_engagement": total_engagement,
            "save_intent_score": save_intent_score,
        },
        "notes": [str(item) for item in metrics.get("notes", [])],
        "next_action": "compare this pattern with the next XHS workflow run",
    }


def render_performance_review_markdown(review: dict[str, Any]) -> str:
    lines = ["# XHS Performance Review", "", f"Status: `{review.get('status')}`", ""]
    if review.get("status") != "recorded":
        lines.append("No published-post metrics were provided for this run.")
        lines.append("")
        return "\n".join(lines)
    metrics = dict(review.get("metrics") or {})
    scores = dict(review.get("scores") or {})
    lines.extend(
        [
            f"- Post URL: {metrics.get('post_url', '')}",
            f"- Total engagement: {scores.get('total_engagement', 0)}",
            f"- Save-intent score: {scores.get('save_intent_score', 0)}",
            "",
            "## Notes",
            "",
        ]
    )
    notes = review.get("notes") or []
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- No manual notes provided.")
    lines.extend(["", f"Next action: {review.get('next_action', '')}", ""])
    return "\n".join(lines)


def run_xhs_workflow(request: dict[str, Any], collector_runner: Any = subprocess.run) -> dict[str, Any]:
    package_dir = resolve_package_dir(request)
    package_dir.mkdir(parents=True, exist_ok=True)
    for child in ["raw", "generation", "preview", "images"]:
        (package_dir / child).mkdir(parents=True, exist_ok=True)

    collector_plan = build_collector_plan(request)
    collector_run = {"status": "not_requested", "source": collector_plan.get("source", "")}
    if dict(request.get("collector") or {}).get("auto_run"):
        collector_output = package_dir / "collector_result.json"
        collector_run = run_collector_plan(
            collector_plan,
            collector_output,
            runner=collector_runner,
            timeout_seconds=int(dict(request.get("collector") or {}).get("timeout_seconds") or 180),
        )
        if collector_run.get("status") == "collected":
            request = dict(request)
            request["benchmark_file"] = collector_run["output_path"]
            request["benchmark_source"] = collector_plan.get("source", "xiaohongshu-skills.search-feeds")

    benchmarks, benchmark_import = load_benchmark_inputs(request)
    source_ledger = build_source_ledger(benchmarks)
    patterns = deconstruct_benchmarks(benchmarks)
    content_brief = build_content_brief(request)
    card_plan = build_card_plan(request, patterns)
    image_config = dict(request.get("image_generation") or {})
    generation = prepare_image_generation(card_plan, image_config)
    generation = maybe_generate_images(package_dir, generation, image_config)
    qc = build_qc_report(card_plan, generation, source_ledger)
    performance_review = build_performance_review(request)
    performance_collection_plan = build_performance_collection_plan(request)

    write_json(package_dir / "request.json", request)
    write_json(package_dir / "source_ledger.json", {"sources": source_ledger})
    write_json(package_dir / "benchmarks.json", {"benchmarks": benchmarks, "import": benchmark_import})
    write_json(package_dir / "collector_plan.json", collector_plan)
    write_json(package_dir / "collector_run.json", collector_run)
    write_json(package_dir / "patterns.json", patterns)
    write_json(package_dir / "content_brief.json", content_brief)
    write_json(package_dir / "card_plan.json", card_plan)
    write_json(package_dir / "generation" / "prompts.json", {"prompts": generation["prompts"]})
    write_json(package_dir / "generation" / "model_run.json", generation)
    write_json(package_dir / "qc_report.json", qc)
    write_json(package_dir / "performance_review.json", performance_review)
    (package_dir / "deconstruction.md").write_text(render_deconstruction_markdown(patterns), encoding="utf-8")
    (package_dir / "draft.md").write_text(render_draft(card_plan), encoding="utf-8")
    (package_dir / "caption.md").write_text(render_caption(request, card_plan), encoding="utf-8")
    (package_dir / "hashtags.txt").write_text(render_hashtags(request), encoding="utf-8")
    publish_plan = build_publish_preview_plan(request, package_dir, card_plan)
    write_json(package_dir / "publish_plan.json", publish_plan)
    write_json(package_dir / "performance_collection_plan.json", performance_collection_plan)
    (package_dir / "qc_report.md").write_text(render_qc_markdown(qc), encoding="utf-8")
    (package_dir / "review.md").write_text(render_performance_review_markdown(performance_review), encoding="utf-8")

    result = {
        "status": "ready_for_review",
        "package_dir": str(package_dir),
        "benchmark_count": len(benchmarks),
        "benchmark_import": benchmark_import,
        "collector_plan": collector_plan,
        "collector_run": collector_run,
        "card_count": len(card_plan["cards"]),
        "image_generation_mode": generation["mode"],
        "qc_status": qc["status"],
        "performance_review": {"status": performance_review["status"]},
        "performance_collection_plan": performance_collection_plan,
        "publish_plan": publish_plan,
        "publish_gate": {"status": "manual approval required before XHS publishing"},
    }
    write_json(package_dir / "meta.json", result)
    return result
