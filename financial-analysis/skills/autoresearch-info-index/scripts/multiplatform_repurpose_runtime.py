#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from multiplatform_repurpose_platforms import (
    ALL_PLATFORM_TARGETS,
    PLATFORM_OUTPUT_FILES,
    build_human_edit_required,
    build_what_not_to_say,
    platform_body,
    platform_citations_used,
    platform_title,
)

REQUEST_CONTRACT_VERSION = "multiplatform_repurpose_request/v1"
MANIFEST_CONTRACT_VERSION = "multiplatform_repurpose_manifest/v1"
DEFAULT_ROOT = Path(".tmp") / "multiplatform-content-repurposer"


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", clean_text(value).lower()).strip("-")
    return slug or fallback


def read_optional_text(path_value: Any, *, base_dir: Path | None = None) -> str:
    path_text = clean_text(path_value)
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path.read_text(encoding="utf-8-sig")


def load_optional_json(path_value: Any, *, base_dir: Path | None = None) -> dict[str, Any]:
    path_text = clean_text(path_value)
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return load_json(path)


def extract_title(markdown: str, fallback: str = "") -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return clean_text(line.removeprefix("# "))
    return clean_text(fallback) or "Untitled source article"


def markdown_paragraphs(markdown: str) -> list[str]:
    blocks = [clean_text(block) for block in re.split(r"\n\s*\n", markdown) if clean_text(block)]
    return [block for block in blocks if not block.startswith("#")]


def extract_core_thesis(markdown: str, *fallbacks: Any) -> str:
    for item in fallbacks:
        if clean_text(item):
            return clean_text(item)
    for paragraph in markdown_paragraphs(markdown):
        lowered = paragraph.lower()
        if "core thesis" in lowered or "the thesis" in lowered:
            return paragraph
    paragraphs = markdown_paragraphs(markdown)
    return paragraphs[0] if paragraphs else ""


def extract_caveats_from_markdown(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    in_caveats = False
    caveats: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            caveats.append(clean_text(" ".join(paragraph_buffer)))
            paragraph_buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()
        lowered = line.lower().strip("# ")
        if line.startswith("## "):
            flush_paragraph()
            in_caveats = "caveat" in lowered or "evidence boundary" in lowered
            continue
        if in_caveats and line.startswith(("- ", "* ")):
            flush_paragraph()
            caveats.append(clean_text(line[2:]))
        elif in_caveats and line:
            paragraph_buffer.append(line)
        elif in_caveats:
            flush_paragraph()
    flush_paragraph()
    return caveats


def normalize_platform_targets(value: Any) -> list[str]:
    targets = [clean_text(item).lower().replace("-", "_") for item in safe_list(value)]
    if not targets:
        return list(ALL_PLATFORM_TARGETS)
    normalized: list[str] = []
    for target in targets:
        if target not in ALL_PLATFORM_TARGETS:
            raise ValueError(f"unsupported platform target: {target}")
        if target not in normalized:
            normalized.append(target)
    return normalized


def normalize_citations(*sources: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        for raw_item in safe_list(source):
            item = safe_dict(raw_item)
            if not item:
                continue
            normalized = {
                "citation_id": clean_text(item.get("citation_id")) or f"S{len(citations) + 1}",
                "source_name": clean_text(item.get("source_name")),
                "title": clean_text(item.get("title") or item.get("summary")),
                "url": clean_text(item.get("url")),
                "published_at": clean_text(item.get("published_at") or item.get("observed_at")),
            }
            key = (normalized["source_name"].lower(), normalized["title"].lower(), normalized["url"].lower())
            if key in seen:
                continue
            seen.add(key)
            citations.append(normalized)
    return citations


def collect_brief_caveats(article_brief: dict[str, Any]) -> tuple[list[str], list[str]]:
    brief = safe_dict(article_brief.get("analysis_brief"))
    caveats: list[str] = []
    for item in safe_list(brief.get("not_proven")):
        claim = clean_text(safe_dict(item).get("claim_text") or safe_dict(item).get("claim_text_zh"))
        reason = clean_text(safe_dict(item).get("why_not_proven"))
        if claim and reason:
            caveats.append(f"{claim} ({reason})")
        elif claim:
            caveats.append(claim)
    for item in safe_list(brief.get("open_questions"))[:3]:
        if clean_text(item):
            caveats.append(f"Open question: {clean_text(item)}")
    misread_risks = [clean_text(item) for item in safe_list(brief.get("misread_risks")) if clean_text(item)]
    return caveats, misread_risks


def normalize_request(raw_payload: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    publish_package = safe_dict(payload.get("existing_publish_package")) or safe_dict(payload.get("publish_package"))
    if not publish_package:
        publish_package = load_optional_json(
            payload.get("existing_publish_package_path") or payload.get("publish_package_path"),
            base_dir=base_dir,
        )
        publish_package = safe_dict(publish_package.get("publish_package")) or publish_package
    article_brief = safe_dict(payload.get("article_brief")) or load_optional_json(payload.get("article_brief_path"), base_dir=base_dir)
    evidence_bundle = safe_dict(payload.get("evidence_bundle")) or load_optional_json(payload.get("evidence_bundle_path"), base_dir=base_dir)

    source_article = safe_dict(payload.get("source_article"))
    source_markdown = str(source_article.get("markdown") or "")
    if not clean_text(source_markdown):
        source_markdown = read_optional_text(source_article.get("markdown_path"), base_dir=base_dir)
    if not clean_text(source_markdown):
        source_markdown = str(publish_package.get("content_markdown") or "")
    title = clean_text(source_article.get("title")) or extract_title(source_markdown, publish_package.get("title"))

    run_id = clean_text(payload.get("run_id")) or slugify(title, "run")
    output_dir = Path(clean_text(payload.get("output_dir")) or str(DEFAULT_ROOT / run_id)).expanduser().resolve()
    brief_inner = safe_dict(article_brief.get("analysis_brief"))

    return {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "run_id": run_id,
        "output_dir": output_dir,
        "platform_targets": normalize_platform_targets(payload.get("platform_targets")),
        "source_article": {
            "title": title,
            "markdown": source_markdown,
            "markdown_path": clean_text(source_article.get("markdown_path")),
            "language": clean_text(source_article.get("language") or payload.get("language") or "mixed"),
        },
        "creator_voice_guide": safe_dict(payload.get("creator_voice_guide")),
        "source_notes": safe_dict(payload.get("source_notes")),
        "citations": normalize_citations(
            payload.get("citations"),
            publish_package.get("citations"),
            article_brief.get("supporting_citations"),
            evidence_bundle.get("citations"),
        ),
        "publish_package": publish_package,
        "article_brief": article_brief,
        "evidence_bundle": evidence_bundle,
        "core_thesis": extract_core_thesis(
            source_markdown,
            source_article.get("core_thesis"),
            publish_package.get("draft_thesis"),
            brief_inner.get("recommended_thesis") or brief_inner.get("recommended_thesis_zh"),
        ),
    }


def build_source_integrity(request: dict[str, Any]) -> dict[str, Any]:
    markdown = str(safe_dict(request.get("source_article")).get("markdown") or "")
    brief_caveats, misread_risks = collect_brief_caveats(safe_dict(request.get("article_brief")))
    markdown_caveats = extract_caveats_from_markdown(markdown)
    package_notes = [clean_text(item) for item in safe_list(safe_dict(request.get("publish_package")).get("operator_notes")) if clean_text(item)]
    caveats = list(dict.fromkeys(markdown_caveats + brief_caveats + package_notes))
    missing_inputs: list[str] = []
    if not request["citations"]:
        missing_inputs.append("citations")
    if not clean_text(safe_dict(request.get("creator_voice_guide")).get("text")) and not clean_text(safe_dict(request.get("creator_voice_guide")).get("path")):
        missing_inputs.append("creator_voice_guide")
    if not safe_list(safe_dict(request.get("source_notes")).get("items")) and not safe_list(safe_dict(request.get("source_notes")).get("paths")):
        missing_inputs.append("source_notes")
    if not clean_text(request.get("core_thesis")):
        status = "blocked"
    elif "citations" in missing_inputs:
        status = "needs_human_review"
    else:
        status = "ok"
    return {
        "status": status,
        "core_thesis": clean_text(request.get("core_thesis")),
        "key_caveats": caveats,
        "misread_risks": misread_risks,
        "citation_inventory": deepcopy(request["citations"]),
        "missing_inputs": missing_inputs,
    }


def build_platform_package(platform: str, request: dict[str, Any], integrity: dict[str, Any], platform_dir: Path) -> dict[str, Any]:
    title = clean_text(safe_dict(request.get("source_article")).get("title"))
    citations = deepcopy(safe_list(integrity.get("citation_inventory")))
    caveats = [clean_text(item) for item in safe_list(integrity.get("key_caveats")) if clean_text(item)]
    body = platform_body(platform, title, integrity["core_thesis"], caveats, citations)
    content_file = platform_dir / PLATFORM_OUTPUT_FILES[platform]
    package_path = platform_dir / "platform-package.json"
    what_not_path = platform_dir / "what-not-to-say.md"
    human_edit_path = platform_dir / "human-edit-required.md"
    package = {
        "contract_version": "multiplatform_platform_package/v1",
        "platform": platform,
        "title": platform_title(platform, title),
        "hook": body.splitlines()[0].lstrip("# ").strip(),
        "core_thesis": integrity["core_thesis"],
        "body_or_script": body,
        "citations_used": platform_citations_used(citations),
        "caveats_preserved": caveats,
        "what_not_to_say": build_what_not_to_say(platform, integrity),
        "human_edit_required": build_human_edit_required(platform, integrity),
        "source_integrity_status": clean_text(integrity.get("status")),
        "files": {
            "json": str(package_path),
            "content": str(content_file),
            "what_not_to_say": str(what_not_path),
            "human_edit_required": str(human_edit_path),
        },
    }
    platform_dir.mkdir(parents=True, exist_ok=True)
    content_file.write_text(body, encoding="utf-8-sig")
    what_not_path.write_text("\n".join(f"- {item}" for item in package["what_not_to_say"]) + "\n", encoding="utf-8-sig")
    human_edit_path.write_text("\n".join(f"- {item}" for item in package["human_edit_required"]) + "\n", encoding="utf-8-sig")
    write_json(package_path, package)
    return package


def build_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Multiplatform Content Repurposer: {clean_text(result.get('run_id'))}",
        "",
        f"- Source integrity: {clean_text(safe_dict(result.get('source_integrity')).get('status'))}",
        f"- Output dir: {clean_text(result.get('output_dir'))}",
        f"- Platforms: {', '.join(result.get('platforms', {}).keys())}",
        "",
        "## Human Review",
    ]
    for platform, package in safe_dict(result.get("platforms")).items():
        lines.append(f"- {platform}: {clean_text(package.get('source_integrity_status'))}")
    return "\n".join(lines) + "\n"


def build_multiplatform_repurpose(raw_payload: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    request = normalize_request(raw_payload, base_dir=base_dir)
    output_dir = Path(request["output_dir"])
    dist_dir = output_dir / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    integrity = build_source_integrity(request)
    platform_packages = {
        platform: build_platform_package(platform, request, integrity, dist_dir / platform)
        for platform in request["platform_targets"]
    }
    result = {
        "contract_version": MANIFEST_CONTRACT_VERSION,
        "run_id": request["run_id"],
        "generated_at": datetime.now(UTC).isoformat(),
        "output_dir": str(output_dir),
        "request": {
            "contract_version": request["contract_version"],
            "platform_targets": request["platform_targets"],
            "source_article": request["source_article"],
        },
        "source_integrity": integrity,
        "platforms": platform_packages,
        "manifest_path": str(output_dir / "manifest.json"),
        "report_path": str(output_dir / "report.md"),
    }
    write_json(output_dir / "request.normalized.json", result["request"])
    write_json(output_dir / "source-integrity.json", integrity)
    result["report_markdown"] = build_report_markdown(result)
    Path(result["report_path"]).write_text(result["report_markdown"], encoding="utf-8-sig")
    write_json(result["manifest_path"], result)
    return result


__all__ = [
    "ALL_PLATFORM_TARGETS",
    "MANIFEST_CONTRACT_VERSION",
    "REQUEST_CONTRACT_VERSION",
    "build_multiplatform_repurpose",
    "load_json",
    "normalize_request",
    "write_json",
]
