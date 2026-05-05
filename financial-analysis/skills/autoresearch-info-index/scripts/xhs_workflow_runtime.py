#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import difflib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_CARD_COUNT = 7
DEFAULT_IMAGE_SIZE = "1024x1536"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_OVERLAY_TEXT_COLOR = (248, 250, 252, 255)
DEFAULT_OVERLAY_MUTED_COLOR = (203, 213, 225, 255)
DEFAULT_OVERLAY_ACCENT_COLOR = (56, 189, 248, 255)
TEXT_STRATEGIES = {"local_overlay", "model_text_with_qc", "hybrid_overlay"}
TEXT_STRATEGY_ALIASES = {
    "hybrid": "hybrid_overlay",
    "recommended": "hybrid_overlay",
}
FORBIDDEN_TEXT_POLICY = (
    "Only allowed_text may appear in model-rendered text. Do not invent or add dates, years, times, numbers, "
    "company names, tickers, logos, watermarks, labels, hashtags, chart axes, timestamps, or metadata unless they "
    "are explicitly present in allowed_text. OCR/QC is required before publish preview for model text."
)
FORBIDDEN_OCR_PATTERNS = [
    ("yyyy_month", re.compile(r"\b20[2-9]\d[-/.](?:0?[1-9]|1[0-2])\b")),
    ("year", re.compile(r"\b20[2-9]\d\b")),
    ("time", re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")),
    ("date_or_number", re.compile(r"\b\d{1,2}[-/.]\d{1,2}\b|\b\d{2,}\b|[+-]?\d+(?:\.\d+)?%")),
]
DEFAULT_TESSERACT_PATHS = [
    Path("D:/Tools/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
]


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
    text_strategy = normalize_text_strategy(image_config.get("text_strategy"))
    collector = dict(request.get("collector") or {})
    collector_plan = build_collector_plan(request, env=env)
    collector_requested = bool(collector.get("auto_run") or collector.get("type"))
    collector_ready = collector_plan.get("status") == "ready"
    benchmark_file = request.get("benchmark_file")
    inline_benchmarks = extract_benchmark_items(request.get("benchmarks") or [])
    benchmark_file_exists = True
    if benchmark_file:
        benchmark_file_exists = Path(str(benchmark_file)).resolve().exists()
    benchmark_input_ok = (
        (bool(benchmark_file) and benchmark_file_exists)
        or bool(inline_benchmarks)
        or (bool(collector.get("auto_run")) and collector_ready)
    )

    api_key_ok = True
    if mode == "openai":
        api_key_ok = bool(image_config.get("api_key") or env.get("OPENAI_API_KEY"))
    ocr_available = is_tesseract_available()
    text_qc_required = text_strategy == "model_text_with_qc"

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

    background_images = normalize_background_images(list(image_config.get("background_images") or []))
    background_images_ok = True
    missing_backgrounds = []
    if mode == "compose":
        for path_text in background_images:
            if path_text.startswith("http://") or path_text.startswith("https://"):
                missing_backgrounds.append(f"remote URL not supported for compose backgrounds: {path_text}")
                continue
            if not Path(path_text).resolve().exists():
                missing_backgrounds.append(path_text)
        if len(background_images) < DEFAULT_CARD_COUNT:
            missing_backgrounds.append(f"expected at least {DEFAULT_CARD_COUNT} background images, got {len(background_images)}")
        background_images_ok = bool(background_images) and not missing_backgrounds

    output_dir = Path(str(request.get("output_dir") or "output/xhs-workflow")).resolve()
    output_parent = output_dir if output_dir.exists() else output_dir.parent
    output_dir_ok = output_parent.exists()

    checks = {
        "benchmark_input": {"passed": benchmark_input_ok, "value": len(inline_benchmarks) if not benchmark_file else str(benchmark_file)},
        "benchmark_file": {"passed": benchmark_file_exists, "value": str(benchmark_file or "")},
        "openai_api_key": {"passed": api_key_ok, "value": "required" if mode == "openai" else "not_required"},
        "reference_images": {"passed": reference_images_ok, "value": len(reference_images), "missing": missing_references},
        "background_images": {"passed": background_images_ok, "value": len(background_images), "missing": missing_backgrounds},
        "output_dir": {"passed": output_dir_ok, "value": str(output_dir)},
        "ocr_available": {
            "passed": ocr_available,
            "value": "available" if ocr_available else "not_found",
            "blocking": False,
        },
        "text_qc_executable": {
            "passed": (not text_qc_required) or ocr_available,
            "value": (
                "not_required"
                if not text_qc_required
                else ("ocr_qc_ready" if ocr_available else "needs_manual_text_qc_without_ocr")
            ),
            "blocking": False,
        },
    }
    if collector_requested:
        checks["collector_plan"] = {
            "passed": collector_ready,
            "value": collector_plan.get("status", ""),
            "source": collector_plan.get("source", ""),
            "cwd": collector_plan.get("cwd", ""),
            "message": collector_plan.get("message", ""),
        }
    blockers = [name for name, check in checks.items() if not check["passed"] and check.get("blocking") is not False]
    warnings = [name for name, check in checks.items() if not check["passed"] and check.get("blocking") is False]
    report = {
        "status": "blocked" if blockers else "ready",
        "mode": mode,
        "text_strategy": text_strategy,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "fix blockers before generation" if blockers else "safe to run dry-run package generation",
    }
    if collector_requested:
        report["collector_plan"] = collector_plan
    return report


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


def resolve_xiaohongshu_skills_dir(
    config: dict[str, Any],
    env: dict[str, str] | None = None,
) -> tuple[Path, str]:
    env = env if env is not None else os.environ
    skills_dir_text = str(config.get("skills_dir") or "").strip()
    if skills_dir_text:
        return Path(skills_dir_text).resolve(), "request.skills_dir"
    env_key = "XIAOHONGSHU_SKILLS_DIR"
    if env.get(env_key):
        return Path(str(env[env_key])).resolve(), f"env:{env_key}"
    return Path(".").resolve(), "default:cwd"


def check_xiaohongshu_skills_cli(skills_dir: Path) -> dict[str, Any]:
    cli_path = skills_dir / "scripts" / "cli.py"
    if not skills_dir.exists():
        return {
            "status": "missing_skills_dir",
            "cli_path": str(cli_path),
            "message": f"xiaohongshu-skills directory not found: {skills_dir}",
        }
    if not cli_path.exists():
        return {
            "status": "missing_cli",
            "cli_path": str(cli_path),
            "message": f"xiaohongshu-skills CLI not found at {cli_path}",
        }
    return {"status": "ready", "cli_path": str(cli_path), "message": ""}


def build_bridge_preflight_command(bridge_url: str) -> list[str]:
    code = (
        "import json,sys;"
        "sys.path.insert(0,'scripts');"
        "from xhs.bridge import BridgePage;"
        f"page=BridgePage({json.dumps(bridge_url)});"
        "print(json.dumps({"
        "'server_running': page.is_server_running(), "
        "'extension_connected': page.is_extension_connected()"
        "}))"
    )
    return ["python", "-c", code]


def bool_config(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("0", "false", "no", "off"):
        return False
    if text in ("1", "true", "yes", "on"):
        return True
    return default


def normalize_text_strategy(value: Any) -> str:
    text = str(value or "local_overlay").strip().lower()
    text = TEXT_STRATEGY_ALIASES.get(text, text)
    if text not in TEXT_STRATEGIES:
        raise ValueError(
            "image_generation.text_strategy must be one of: "
            + ", ".join(sorted(TEXT_STRATEGIES))
        )
    return text


def optional_cli_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_collector_plan(request: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
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

    skills_dir, skills_dir_source = resolve_xiaohongshu_skills_dir(collector, env=env)
    cli_check = check_xiaohongshu_skills_cli(skills_dir)
    keyword = str(collector.get("keyword") or request.get("topic") or "").strip()
    apply_filters = bool_config(collector.get("apply_filters"), default=True)
    sort_by = optional_cli_value(collector.get("sort_by")) if apply_filters else ""
    note_type = optional_cli_value(collector.get("note_type")) if apply_filters else ""
    limit = int(collector.get("limit") or 20)
    bridge_url = str(collector.get("bridge_url") or "ws://localhost:9333")
    if cli_check["status"] != "ready":
        return {
            "status": cli_check["status"],
            "source": "xiaohongshu-skills.search-feeds",
            "cwd": str(skills_dir),
            "command": [],
            "skills_dir_source": skills_dir_source,
            "cli_path": cli_check["cli_path"],
            "message": cli_check["message"],
        }
    if not keyword:
        return {
            "status": "needs_configuration",
            "source": "xiaohongshu-skills.search-feeds",
            "cwd": str(skills_dir),
            "command": [],
            "skills_dir_source": skills_dir_source,
            "cli_path": cli_check["cli_path"],
            "message": "collector keyword is required",
        }
    command = [
        "python",
        "scripts/cli.py",
        "search-feeds",
        "--keyword",
        keyword,
    ]
    if sort_by:
        command.extend(["--sort-by", sort_by])
    if note_type:
        command.extend(["--note-type", note_type])
    filter_mode = "disabled" if not apply_filters else ("requested" if sort_by or note_type else "keyword_only")
    return {
        "status": "ready",
        "source": "xiaohongshu-skills.search-feeds",
        "cwd": str(skills_dir),
        "command": command,
        "skills_dir_source": skills_dir_source,
        "cli_path": cli_check["cli_path"],
        "requested_limit": limit,
        "bridge_url": bridge_url,
        "filter_mode": filter_mode,
        "filters": {"apply_filters": apply_filters, "sort_by": sort_by, "note_type": note_type},
        "bridge_preflight_command": build_bridge_preflight_command(bridge_url),
        "output_next_step": "Save the JSON result and pass it back with --benchmark-file.",
    }


def build_publish_preview_plan(
    request: dict[str, Any],
    package_dir: Path,
    card_plan: dict[str, Any],
    env: dict[str, str] | None = None,
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

    skills_dir, skills_dir_source = resolve_xiaohongshu_skills_dir(publish, env=env)
    bridge_url = str(publish.get("bridge_url") or "ws://localhost:9333")
    cli_check = check_xiaohongshu_skills_cli(skills_dir)
    if cli_check["status"] != "ready":
        return {
            "status": cli_check["status"],
            "source": "xiaohongshu-skills.fill-publish",
            "command": [],
            "cwd": str(skills_dir),
            "click_publish": False,
            "skills_dir_source": skills_dir_source,
            "cli_path": cli_check["cli_path"],
            "message": cli_check["message"],
        }
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
        "skills_dir_source": skills_dir_source,
        "cli_path": cli_check["cli_path"],
        "bridge_url": bridge_url,
        "bridge_preflight_command": build_bridge_preflight_command(bridge_url),
        "image_count": len(image_paths),
        "title_file": str(title_file),
        "content_file": str(content_file),
    }


def build_performance_collection_plan(request: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
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
    skills_dir, skills_dir_source = resolve_xiaohongshu_skills_dir(collection, env=env)
    bridge_url = str(collection.get("bridge_url") or "ws://localhost:9333")
    cli_check = check_xiaohongshu_skills_cli(skills_dir)
    feed_id = str(collection.get("feed_id") or "").strip()
    xsec_token = str(collection.get("xsec_token") or "").strip()
    if cli_check["status"] != "ready":
        return {
            "status": cli_check["status"],
            "source": "xiaohongshu-skills.get-feed-detail",
            "cwd": str(skills_dir),
            "command": [],
            "skills_dir_source": skills_dir_source,
            "cli_path": cli_check["cli_path"],
            "message": cli_check["message"],
        }
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
        "status": "ready" if feed_id and xsec_token else "needs_configuration",
        "source": "xiaohongshu-skills.get-feed-detail",
        "cwd": str(skills_dir),
        "command": command,
        "skills_dir_source": skills_dir_source,
        "cli_path": cli_check["cli_path"],
        "bridge_url": bridge_url,
        "bridge_preflight_command": build_bridge_preflight_command(bridge_url),
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
    bridge_preflight = run_bridge_preflight_plan(plan, runner=runner)
    if bridge_preflight.get("status") not in ("not_configured", "ready"):
        return {
            "status": bridge_preflight["status"],
            "source": plan.get("source", ""),
            "reason": bridge_preflight.get("message", ""),
            "bridge_preflight": bridge_preflight,
            "output_path": str(output_path),
        }
    completed = runner(
        list(plan.get("command") or []),
        cwd=str(plan.get("cwd") or "."),
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
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
        "bridge_preflight": bridge_preflight,
    }


def run_bridge_preflight_plan(
    plan: dict[str, Any],
    runner: Any = subprocess.run,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    command = [str(item) for item in plan.get("bridge_preflight_command") or []]
    if not command:
        return {"status": "not_configured"}
    completed = runner(
        command,
        cwd=str(plan.get("cwd") or "."),
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return {
            "status": "bridge_preflight_failed",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "message": "bridge preflight command failed",
        }
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "status": "bridge_preflight_failed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "message": "bridge preflight did not return JSON",
        }
    server_running = bool(payload.get("server_running"))
    extension_connected = bool(payload.get("extension_connected"))
    if not server_running:
        return {
            "status": "bridge_server_not_running",
            "server_running": False,
            "extension_connected": False,
            "message": "XHS Bridge server is not running; start bridge_server.py before running the collector.",
        }
    if not extension_connected:
        return {
            "status": "bridge_not_connected",
            "server_running": True,
            "extension_connected": False,
            "message": "XHS Bridge extension is not connected; reload the Edge extension and retry.",
        }
    return {
        "status": "ready",
        "server_running": True,
        "extension_connected": True,
        "message": "",
    }


def run_publish_preview_plan(
    plan: dict[str, Any],
    runner: Any = subprocess.run,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    command = [str(item) for item in plan.get("command") or []]
    if plan.get("status") != "ready_preview":
        return {
            "status": "skipped",
            "reason": f"publish preview plan is {plan.get('status')}",
            "source": plan.get("source", ""),
            "click_publish": False,
        }
    if plan.get("click_publish") or any("click-publish" in item for item in command):
        return {
            "status": "blocked",
            "reason": "click-publish is not allowed from xhs_workflow",
            "source": plan.get("source", ""),
            "click_publish": False,
        }
    if "fill-publish" not in command:
        return {
            "status": "blocked",
            "reason": "publish preview may only run fill-publish",
            "source": plan.get("source", ""),
            "click_publish": False,
        }
    bridge_preflight = run_bridge_preflight_plan(plan, runner=runner)
    if bridge_preflight.get("status") not in ("not_configured", "ready"):
        return {
            "status": bridge_preflight["status"],
            "reason": bridge_preflight.get("message", ""),
            "source": plan.get("source", ""),
            "bridge_preflight": bridge_preflight,
            "click_publish": False,
        }
    completed = runner(
        command,
        cwd=str(plan.get("cwd") or "."),
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return {
            "status": "failed",
            "source": plan.get("source", ""),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "click_publish": False,
        }
    return {
        "status": "filled_preview",
        "source": plan.get("source", ""),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "bridge_preflight": bridge_preflight,
        "click_publish": False,
    }


def gate_publish_preview_plan_by_qc(plan: dict[str, Any], qc: dict[str, Any]) -> dict[str, Any]:
    qc_status = str(qc.get("status") or "")
    if plan.get("status") != "ready_preview" or qc_status == "needs_human_review":
        return plan
    gated = dict(plan)
    gated.update(
        {
            "status": "blocked_qc",
            "command": [],
            "click_publish": False,
            "qc_status": qc_status,
            "reason": f"qc status is {qc_status}",
            "message": "Resolve text QC before creating a publish preview.",
        }
    )
    return gated


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


def normalize_background_images(items: list[Any]) -> list[str]:
    normalized = []
    for item in items:
        if isinstance(item, str):
            path = item.strip()
        elif isinstance(item, dict):
            path = str(item.get("path") or "").strip()
        else:
            path = ""
        if path:
            normalized.append(path)
    return normalized


def build_image_prompt(
    card: dict[str, Any],
    style_profile: dict[str, Any] | None = None,
    reference_images: list[dict[str, str]] | None = None,
    text_strategy: str = "local_overlay",
) -> str:
    style = style_profile or {}
    visual_style = style.get("visual_style", "premium Xiaohongshu editorial image post")
    material_policy = style.get("material_policy", "use user-owned material when provided")
    text_strategy = normalize_text_strategy(text_strategy)
    title = str(card.get("title") or "")
    message = str(card.get("message") or "")
    reference_line = (
        "Use the provided reference images as the primary visual material; preserve their concrete details while improving composition. "
        if reference_images
        else ""
    )
    if text_strategy == "model_text_with_qc":
        return (
            f"{visual_style}. vertical 9:16 Xiaohongshu editorial card with controlled typography. "
            f"Card type: {card.get('type')}. Visual concept: {title} / {message}. "
            f"{reference_line}"
            "Only render the exact allowed text strings below, with no paraphrase and no extra text. "
            f"Allowed title text: {json.dumps(title, ensure_ascii=False)}. "
            f"Allowed message text: {json.dumps(message, ensure_ascii=False)}. "
            "Do not invent or add dates, years, times, numbers, company names, tickers, logos, watermarks, "
            "labels, hashtags, chart axis values, timestamps, or metadata. "
            "If a character or fact is not present in the allowed text strings, leave it out. "
            "Make the allowed text legible and unchanged. No copied competitor assets. "
            f"Material policy: {material_policy}."
        )
    if text_strategy == "hybrid_overlay":
        return (
            f"{visual_style}. vertical 9:16 Xiaohongshu layout-rich editorial background only for local overlay. "
            f"Card type: {card.get('type')}. Visual concept: {title} / {message}. "
            f"{reference_line}"
            "Create a strong composition with realistic finance/technology material, structured panels, empty headline "
            "zones, and visual hierarchy that leaves clear space for local overlay. Do not render readable factual text, "
            "letters, numbers, dates, time stamps, calendar UI, logos, watermarks, labels, tickers, chart axis values, "
            "or metadata. Critical facts will be added by local overlay. No copied competitor assets. "
            f"Material policy: {material_policy}."
        )
    return (
        f"{visual_style}. vertical 9:16 Xiaohongshu editorial background only. "
        f"Card type: {card.get('type')}. Visual concept: {title} / {message}. "
        f"{reference_line}"
        "Create a clean finance/technology visual background with realistic material texture, data-center, chip, "
        "earnings-dashboard, or infrastructure motifs where appropriate. Leave generous negative space for later "
        "local text overlay. Do not render any readable text, letters, numbers; no dates, time stamps, calendar UI, "
        "logos, watermarks, labels, tickers, or chart axis values. No copied competitor assets. "
        f"Material policy: {material_policy}."
    )


def prepare_image_generation(card_plan: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    mode = str(config.get("mode") or "dry_run")
    model = str(config.get("model") or DEFAULT_IMAGE_MODEL)
    size = str(config.get("size") or DEFAULT_IMAGE_SIZE)
    text_strategy = normalize_text_strategy(config.get("text_strategy"))
    style_profile = dict(config.get("style_profile") or {})
    reference_images = normalize_reference_images(list(config.get("reference_images") or []))
    background_images = normalize_background_images(list(config.get("background_images") or []))
    prompts = [
        {
            "card_index": card.get("index"),
            "card_type": card.get("type"),
            "card_title": str(card.get("title") or ""),
            "card_message": str(card.get("message") or ""),
            "model": model,
            "size": size,
            "reference_images": reference_images,
            "background_image": background_images[index] if index < len(background_images) else "",
            "allowed_text": [str(card.get("title") or ""), str(card.get("message") or "")],
            "forbidden_text_policy": FORBIDDEN_TEXT_POLICY,
            "qc_required": text_strategy == "model_text_with_qc",
            "text_strategy": text_strategy,
            "prompt": build_image_prompt(card, style_profile, reference_images, text_strategy=text_strategy),
        }
        for index, card in enumerate(card_plan.get("cards", []))
    ]
    allowed_text = [[prompt["card_title"], prompt["card_message"]] for prompt in prompts]
    return {
        "mode": mode,
        "model": model,
        "size": size,
        "text_strategy": text_strategy,
        "prompts": prompts,
        "results": [],
        "text_rendering": {
            "mode": text_strategy,
            "allowed_text": allowed_text,
            "forbidden_text_policy": FORBIDDEN_TEXT_POLICY,
            "forbidden_model_text": text_strategy != "model_text_with_qc",
            "qc_required": text_strategy == "model_text_with_qc",
        },
    }


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
        build_openai_api_url(config, "images/generations"),
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


def build_openai_api_url(config: dict[str, Any], path: str) -> str:
    base_url = str(config.get("base_url") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).strip()
    if not base_url:
        base_url = DEFAULT_OPENAI_BASE_URL
    root = base_url.rstrip("/")
    if not root.endswith("/v1"):
        root = f"{root}/v1"
    return f"{root}/{path.lstrip('/')}"


def parse_image_size(size: str | tuple[int, int] | list[int]) -> tuple[int, int]:
    if isinstance(size, (tuple, list)) and len(size) == 2:
        return int(size[0]), int(size[1])
    match = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", str(size or DEFAULT_IMAGE_SIZE))
    if not match:
        return 1024, 1536
    return int(match.group(1)), int(match.group(2))


def create_placeholder_background(path: Path, size: str | tuple[int, int] = DEFAULT_IMAGE_SIZE) -> None:
    from PIL import Image, ImageDraw

    width, height = parse_image_size(size)
    image = Image.new("RGB", (width, height), (12, 18, 28))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        red = int(12 + ratio * 10)
        green = int(18 + ratio * 28)
        blue = int(28 + ratio * 44)
        draw.line([(0, y), (width, y)], fill=(red, green, blue))
    for offset in range(0, width, max(width // 8, 1)):
        draw.line([(offset, int(height * 0.18)), (offset + int(width * 0.28), int(height * 0.82))], fill=(24, 42, 65), width=max(width // 180, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def load_overlay_font(size: int, bold: bool = False) -> Any:
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def text_width(draw: Any, text: str, font: Any) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def wrap_text(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    words = value.split()
    if len(words) > 1:
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines
    lines = []
    current = ""
    for char in value:
        candidate = current + char
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = char
    if current:
        lines.append(current)
    return lines


def render_local_card_overlay(
    background_path: Path,
    card: dict[str, Any],
    output_path: Path,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from PIL import Image, ImageDraw, ImageFilter

    config = config or {}
    target_size = parse_image_size(config.get("size") or DEFAULT_IMAGE_SIZE)
    if not background_path.exists():
        raise FileNotFoundError(f"Background image not found: {background_path}")
    base = Image.open(background_path).convert("RGB")
    base.thumbnail(target_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target_size, (11, 18, 32))
    left = (target_size[0] - base.width) // 2
    top = (target_size[1] - base.height) // 2
    canvas.paste(base, (left, top))
    image = canvas.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    margin = int(width * 0.08)
    panel_top = int(height * 0.56)
    panel_bottom = int(height * 0.92)
    panel_radius = int(width * 0.035)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    panel_box = (margin, panel_top, width - margin, panel_bottom)
    shadow_draw.rounded_rectangle(panel_box, radius=panel_radius, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(width // 80, 8)))
    overlay.alpha_composite(shadow)
    draw.rounded_rectangle(panel_box, radius=panel_radius, fill=(8, 13, 24, 225), outline=(56, 189, 248, 120), width=max(width // 220, 2))
    draw.rectangle((margin, panel_top, margin + int(width * 0.018), panel_bottom), fill=DEFAULT_OVERLAY_ACCENT_COLOR)

    card_index = int(card.get("index") or 0)
    card_type = str(card.get("type") or "").upper()
    label_font = load_overlay_font(max(int(width * 0.026), 16), bold=True)
    title_font = load_overlay_font(max(int(width * 0.066), 34), bold=True)
    message_font = load_overlay_font(max(int(width * 0.041), 24), bold=False)
    label = f"{card_index:02d} / {card_type}" if card_index else card_type
    x = margin + int(width * 0.05)
    y = panel_top + int(height * 0.04)
    draw.text((x, y), label, font=label_font, fill=DEFAULT_OVERLAY_ACCENT_COLOR)
    y += int(height * 0.055)
    max_text_width = width - (2 * margin) - int(width * 0.1)
    title_lines = wrap_text(draw, str(card.get("title") or ""), title_font, max_text_width)[:2]
    for line in title_lines:
        draw.text((x, y), line, font=title_font, fill=DEFAULT_OVERLAY_TEXT_COLOR)
        y += int(height * 0.065)
    y += int(height * 0.018)
    message_lines = wrap_text(draw, str(card.get("message") or ""), message_font, max_text_width)[:3]
    for line in message_lines:
        draw.text((x, y), line, font=message_font, fill=DEFAULT_OVERLAY_MUTED_COLOR)
        y += int(height * 0.048)

    image = Image.alpha_composite(image, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    allowed_text = [str(card.get("title") or ""), str(card.get("message") or "")]
    return {
        "status": "rendered",
        "path": str(output_path),
        "background_path": str(background_path),
        "text_source": "local_overlay",
        "allowed_text": allowed_text,
        "bytes": output_path.stat().st_size,
    }


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
        build_openai_api_url(config, "images/edits"),
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
    if generation["mode"] not in ("openai", "compose"):
        return generation
    text_strategy = normalize_text_strategy(
        generation.get("text_strategy") or dict(generation.get("text_rendering") or {}).get("mode")
    )
    results = []
    for prompt in generation.get("prompts", []):
        card_index = int(prompt["card_index"])
        output_path = package_dir / "images" / f"card-{card_index:02d}.png"
        background_path = package_dir / "backgrounds" / f"card-{card_index:02d}.png"
        route = "manual_background_compose"
        if generation["mode"] == "compose":
            manual_background = Path(str(prompt.get("background_image") or "")).resolve()
            if not manual_background.exists():
                raise FileNotFoundError(f"Background image not found for card {card_index}: {manual_background}")
            if text_strategy == "model_text_with_qc":
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(manual_background.read_bytes())
                results.append(
                    {
                        "status": "generated",
                        "path": str(output_path),
                        "source_path": str(manual_background),
                        "text_source": "model_text_with_qc",
                        "allowed_text": list(prompt.get("allowed_text") or []),
                        "route": "manual_model_text_compose",
                        "card_index": card_index,
                    }
                )
                continue
            background_path.parent.mkdir(parents=True, exist_ok=True)
            background_path.write_bytes(manual_background.read_bytes())
        else:
            if prompt.get("reference_images"):
                generated_path = output_path if text_strategy == "model_text_with_qc" else background_path
                generated = generate_openai_image_edit(prompt["prompt"], prompt["reference_images"], config, generated_path)
                route = generated.get("route") or "openai_images_edits"
            else:
                generated_path = output_path if text_strategy == "model_text_with_qc" else background_path
                generated = generate_openai_image(prompt["prompt"], config, generated_path)
                route = generated.get("route") or "openai_images_generations"
            if text_strategy == "model_text_with_qc":
                generated.update(
                    {
                        "path": str(output_path),
                        "text_source": "model_text_with_qc",
                        "allowed_text": list(prompt.get("allowed_text") or []),
                        "route": route,
                        "card_index": card_index,
                    }
                )
                results.append(generated)
                continue
        card = {
            "index": card_index,
            "type": prompt.get("card_type"),
            "title": prompt.get("card_title"),
            "message": prompt.get("card_message"),
        }
        result = render_local_card_overlay(background_path, card, output_path, {"size": prompt.get("size") or config.get("size")})
        result["route"] = route
        result["card_index"] = card_index
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


def resolve_tesseract_command(env: dict[str, str] | None = None) -> str | None:
    env = env if env is not None else os.environ
    configured = str(env.get("TESSERACT_CMD") or env.get("TESSERACT_EXE") or "").strip()
    if configured:
        expanded = os.path.expanduser(os.path.expandvars(configured))
        configured_path = Path(expanded)
        if configured_path.exists():
            return str(configured_path)
        found = shutil.which(expanded)
        if found:
            return found
        return None

    found = shutil.which("tesseract")
    if found:
        return found

    for candidate in DEFAULT_TESSERACT_PATHS:
        if candidate.exists():
            return str(candidate)
    return None


def is_tesseract_available() -> bool:
    return resolve_tesseract_command() is not None


def run_tesseract_ocr(
    image_path: str | Path,
    runner: Any = subprocess.run,
    timeout_seconds: int = 60,
) -> str:
    tesseract = resolve_tesseract_command()
    if not tesseract:
        raise RuntimeError("tesseract OCR is not available")
    command = [tesseract, str(image_path), "stdout", "-l", "chi_sim+eng"]
    completed = runner(
        command,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0 and ("Failed loading language" in completed.stderr or "Error opening data file" in completed.stderr):
        completed = runner(
            [tesseract, str(image_path), "stdout"],
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or "tesseract OCR failed")
    return str(completed.stdout or "")


def flatten_allowed_text(allowed_text: Any) -> list[str]:
    flattened: list[str] = []
    if isinstance(allowed_text, str):
        return [allowed_text] if allowed_text.strip() else []
    if isinstance(allowed_text, list):
        for item in allowed_text:
            flattened.extend(flatten_allowed_text(item))
    elif isinstance(allowed_text, tuple):
        for item in allowed_text:
            flattened.extend(flatten_allowed_text(item))
    return [item for item in (str(value).strip() for value in flattened) if item]


def normalize_ocr_compare_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "")).casefold()


def allowed_fragment(fragment: str, allowed_text: list[str]) -> bool:
    raw = str(fragment or "").strip()
    if not raw:
        return True
    if any(raw in allowed for allowed in allowed_text):
        return True
    normalized = normalize_ocr_compare_text(raw)
    if not normalized:
        return True
    allowed_normalized = [normalize_ocr_compare_text(item) for item in allowed_text]
    if any(normalized in item for item in allowed_normalized):
        return True
    for allowed in allowed_normalized:
        if len(normalized) >= 4 and difflib.SequenceMatcher(None, normalized, allowed).ratio() >= 0.82:
            return True
    return False


def evaluate_ocr_text_against_allowed(ocr_text: str, allowed_text: list[str]) -> dict[str, Any]:
    allowed = flatten_allowed_text(allowed_text)
    text = str(ocr_text or "")
    violations: list[dict[str, str]] = []
    for pattern_name, pattern in FORBIDDEN_OCR_PATTERNS:
        for match in pattern.finditer(text):
            fragment = match.group(0)
            if not allowed_fragment(fragment, allowed):
                violations.append(
                    {
                        "type": "forbidden_pattern",
                        "pattern": pattern_name,
                        "text": fragment,
                    }
                )
    if not violations:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9$._-]{2,}|[\u4e00-\u9fff]{2,}|\d+(?:[.,:/-]\d+)*%?", text)
        for token in tokens:
            if not allowed_fragment(token, allowed):
                violations.append({"type": "unallowed_text", "pattern": "token", "text": token})
                break
    return {
        "passed": not violations,
        "ocr_text": text,
        "allowed_text": allowed,
        "violations": violations,
    }


def build_text_qc_report(generation: dict[str, Any]) -> dict[str, Any]:
    text_rendering = dict(generation.get("text_rendering") or {})
    text_strategy = normalize_text_strategy(text_rendering.get("mode") or generation.get("text_strategy"))
    required = bool(text_rendering.get("qc_required")) or text_strategy == "model_text_with_qc"
    if not required:
        return {"status": "not_required", "required": False, "passed": True, "results": []}

    results = [dict(result) for result in generation.get("results") or []]
    if not results:
        return {
            "status": "needs_manual_text_qc",
            "required": True,
            "passed": False,
            "ocr_available": is_tesseract_available(),
            "results": [],
            "message": "No final model-text images were available for OCR.",
        }
    if not is_tesseract_available():
        return {
            "status": "needs_manual_text_qc",
            "required": True,
            "passed": False,
            "ocr_available": False,
            "results": [],
            "message": "tesseract OCR is not available; manual text QC is required before publish preview.",
        }

    qc_results = []
    for result in results:
        path_text = str(result.get("path") or "")
        allowed = flatten_allowed_text(result.get("allowed_text") or text_rendering.get("allowed_text") or [])
        if not path_text or not Path(path_text).exists():
            qc_results.append(
                {
                    "path": path_text,
                    "passed": False,
                    "ocr_text": "",
                    "allowed_text": allowed,
                    "violations": [{"type": "missing_image", "pattern": "path", "text": path_text}],
                }
            )
            continue
        try:
            ocr_text = run_tesseract_ocr(path_text)
            evaluated = evaluate_ocr_text_against_allowed(ocr_text, allowed)
            evaluated["path"] = path_text
            qc_results.append(evaluated)
        except Exception as exc:
            qc_results.append(
                {
                    "path": path_text,
                    "passed": False,
                    "ocr_text": "",
                    "allowed_text": allowed,
                    "violations": [{"type": "ocr_error", "pattern": "tesseract", "text": str(exc)}],
                }
            )
    passed = all(item.get("passed") for item in qc_results)
    return {
        "status": "passed" if passed else "blocked_text_qc",
        "required": True,
        "passed": passed,
        "ocr_available": True,
        "results": qc_results,
    }


def renderable_text_sources_pass(generation: dict[str, Any], rendered_results: list[dict[str, Any]]) -> bool:
    result_count = len(generation.get("results") or [])
    if result_count == 0:
        return True
    text_rendering = dict(generation.get("text_rendering") or {})
    text_strategy = normalize_text_strategy(text_rendering.get("mode") or generation.get("text_strategy"))
    expected = "model_text_with_qc" if text_strategy == "model_text_with_qc" else "local_overlay"
    return len([result for result in generation.get("results") or [] if result.get("text_source") == expected]) == result_count


def build_qc_report(
    card_plan: dict[str, Any],
    generation: dict[str, Any],
    source_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    card_count = len(card_plan.get("cards", []))
    prompt_count = len(generation.get("prompts", []))
    text_rendering = dict(generation.get("text_rendering") or {})
    text_strategy = normalize_text_strategy(text_rendering.get("mode") or generation.get("text_strategy"))
    result_count = len(generation.get("results") or [])
    rendered_results = [result for result in generation.get("results", []) if result.get("text_source") == "local_overlay"]
    text_qc = build_text_qc_report(generation)
    checks = {
        "card_count": {"passed": 5 <= card_count <= 9, "value": card_count},
        "prompt_count": {"passed": prompt_count == card_count, "value": prompt_count},
        "source_ledger": {"passed": bool(source_ledger), "value": len(source_ledger)},
        "text_rendering": {"passed": text_strategy in TEXT_STRATEGIES, "value": text_strategy},
        "rendered_cards": {
            "passed": renderable_text_sources_pass(generation, rendered_results),
            "value": f"{len(rendered_results)}/{result_count}" if text_strategy != "model_text_with_qc" else f"{result_count}/{result_count}",
        },
        "text_qc": {"passed": bool(text_qc.get("passed")), "value": text_qc.get("status", "")},
        "publish_approval": {"passed": False, "value": "manual approval required"},
    }
    status = "needs_human_review"
    if text_qc.get("status") == "needs_manual_text_qc":
        status = "needs_manual_text_qc"
    elif text_qc.get("status") == "blocked_text_qc":
        status = "blocked_text_qc"
    return {
        "status": status,
        "checks": checks,
        "text_strategy": text_strategy,
        "text_qc": text_qc,
        "blocked_from_auto_publish": True,
    }


def render_qc_markdown(qc: dict[str, Any]) -> str:
    lines = ["# XHS Workflow QC", "", f"Status: `{qc.get('status')}`", ""]
    for name, check in qc.get("checks", {}).items():
        marker = "PASS" if check.get("passed") else "REVIEW"
        lines.append(f"- {marker} `{name}`: {check.get('value')}")
    text_qc = dict(qc.get("text_qc") or {})
    if text_qc:
        lines.extend(["", "## Text QC", "", f"- Status: `{text_qc.get('status')}`"])
        lines.append(f"- OCR available: `{str(bool(text_qc.get('ocr_available'))).lower()}`")
        if text_qc.get("message"):
            lines.append(f"- Note: {text_qc.get('message')}")
        for result in text_qc.get("results") or []:
            marker = "PASS" if result.get("passed") else "REVIEW"
            lines.append(f"- {marker} `{result.get('path', '')}`")
            for violation in result.get("violations") or []:
                lines.append(f"  - {violation.get('type')}: `{violation.get('text')}`")
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


def run_xhs_workflow(
    request: dict[str, Any],
    collector_runner: Any = subprocess.run,
    publish_preview_runner: Any = subprocess.run,
) -> dict[str, Any]:
    package_dir = resolve_package_dir(request)
    package_dir.mkdir(parents=True, exist_ok=True)
    for child in ["raw", "generation", "preview", "backgrounds", "images"]:
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
    text_rendering = dict(generation.get("text_rendering") or {})
    write_json(
        package_dir / "generation" / "prompts.json",
        {
            "text_strategy": normalize_text_strategy(text_rendering.get("mode") or generation.get("text_strategy")),
            "allowed_text": text_rendering.get("allowed_text") or [],
            "forbidden_text_policy": text_rendering.get("forbidden_text_policy") or FORBIDDEN_TEXT_POLICY,
            "qc_required": bool(text_rendering.get("qc_required")),
            "prompts": generation["prompts"],
        },
    )
    write_json(package_dir / "generation" / "model_run.json", generation)
    write_json(package_dir / "qc_report.json", qc)
    write_json(package_dir / "performance_review.json", performance_review)
    (package_dir / "deconstruction.md").write_text(render_deconstruction_markdown(patterns), encoding="utf-8")
    (package_dir / "draft.md").write_text(render_draft(card_plan), encoding="utf-8")
    (package_dir / "caption.md").write_text(render_caption(request, card_plan), encoding="utf-8")
    (package_dir / "hashtags.txt").write_text(render_hashtags(request), encoding="utf-8")
    publish_plan = gate_publish_preview_plan_by_qc(build_publish_preview_plan(request, package_dir, card_plan), qc)
    publish_preview_run = {"status": "not_requested", "source": publish_plan.get("source", ""), "click_publish": False}
    publish = dict(request.get("publish") or {})
    if publish.get("auto_run_preview"):
        if qc["status"] != "needs_human_review":
            publish_preview_run = {
                "status": "skipped",
                "reason": f"qc status is {qc['status']}",
                "source": publish_plan.get("source", ""),
                "click_publish": False,
            }
        else:
            publish_preview_run = run_publish_preview_plan(
                publish_plan,
                runner=publish_preview_runner,
                timeout_seconds=int(publish.get("timeout_seconds") or 180),
            )
    write_json(package_dir / "publish_plan.json", publish_plan)
    write_json(package_dir / "publish_preview_run.json", publish_preview_run)
    write_json(package_dir / "performance_collection_plan.json", performance_collection_plan)
    (package_dir / "qc_report.md").write_text(render_qc_markdown(qc), encoding="utf-8")
    (package_dir / "review.md").write_text(render_performance_review_markdown(performance_review), encoding="utf-8")

    result = {
        "status": "ready_for_review" if qc["status"] == "needs_human_review" else qc["status"],
        "package_dir": str(package_dir),
        "benchmark_count": len(benchmarks),
        "benchmark_import": benchmark_import,
        "collector_plan": collector_plan,
        "collector_run": collector_run,
        "card_count": len(card_plan["cards"]),
        "image_generation_mode": generation["mode"],
        "text_strategy": normalize_text_strategy(text_rendering.get("mode") or generation.get("text_strategy")),
        "qc_status": qc["status"],
        "performance_review": {"status": performance_review["status"]},
        "performance_collection_plan": performance_collection_plan,
        "publish_plan": publish_plan,
        "publish_preview_run": publish_preview_run,
        "publish_gate": {"status": "manual approval required before XHS publishing"},
    }
    write_json(package_dir / "meta.json", result)
    return result
