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
    build_platform_profile,
    build_quality_scorecard,
    build_what_not_to_say,
    platform_body,
    platform_citations_used,
    platform_title,
)

REQUEST_CONTRACT_VERSION = "multiplatform_repurpose_request/v1"
MANIFEST_CONTRACT_VERSION = "multiplatform_repurpose_manifest/v1"
COMPLETION_CHECK_CONTRACT_VERSION = "multiplatform_completion_check/v1"
DEFAULT_ROOT = Path(".tmp") / "multiplatform-content-repurposer"
PUBLISH_ARTIFACT_WORKFLOW_KINDS = {"article_publish", "article_publish_reuse"}
REQUIRED_PLATFORM_FILE_KEYS = [
    "json",
    "content",
    "platform_profile",
    "quality_scorecard",
    "rewrite_packet",
    "what_not_to_say",
    "human_edit_required",
]
REQUIRED_SCORECARD_CHECKS = {"core_thesis", "citation_integrity", "caveat_visibility"}


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


def path_exists(path_value: Any) -> bool:
    path_text = clean_text(path_value)
    return bool(path_text) and Path(path_text).exists()


def resolve_optional_path(path_value: Any, *, base_dir: Path | None = None) -> Path | None:
    path_text = clean_text(path_value)
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path.resolve()


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
    path = resolve_optional_path(path_value, base_dir=base_dir)
    if path is None:
        return {}
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


def is_publish_artifact_payload(payload: dict[str, Any]) -> bool:
    contract_version = clean_text(payload.get("contract_version"))
    workflow_kind = clean_text(payload.get("workflow_kind"))
    return contract_version.startswith("publish-package/") or workflow_kind in PUBLISH_ARTIFACT_WORKFLOW_KINDS


def publish_artifact_kind(payload: dict[str, Any]) -> str:
    contract_version = clean_text(payload.get("contract_version"))
    if contract_version.startswith("publish-package/"):
        return "publish_package"
    return clean_text(payload.get("workflow_kind")) or "publish_artifact"


def load_publish_package_from_artifact(
    payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
    artifact_path: Path | None = None,
) -> tuple[dict[str, Any], Path | None]:
    if clean_text(payload.get("contract_version")).startswith("publish-package/"):
        return deepcopy(payload), artifact_path.resolve() if artifact_path else None

    publish_package_path = resolve_optional_path(payload.get("publish_package_path"), base_dir=base_dir)
    publish_package = deepcopy(safe_dict(payload.get("publish_package")))
    if not publish_package and publish_package_path is not None:
        loaded = load_json(publish_package_path)
        publish_package = deepcopy(safe_dict(loaded.get("publish_package")) or loaded)
    if not publish_package:
        raise ValueError("publish artifact input requires publish_package or publish_package_path")
    return publish_package, publish_package_path


def publish_package_markdown(publish_package: dict[str, Any]) -> str:
    for key in ["content_markdown", "edited_article_markdown", "article_markdown", "markdown"]:
        if clean_text(publish_package.get(key)):
            return str(publish_package.get(key) or "")
    return ""


def default_creator_voice_guide_from_publish_package(publish_package: dict[str, Any]) -> dict[str, str]:
    style_profile = safe_dict(publish_package.get("style_profile_applied"))
    style_constraints = safe_dict(style_profile.get("constraints"))
    must_include = [clean_text(item) for item in safe_list(style_constraints.get("must_include")) if clean_text(item)]
    if must_include:
        return {
            "text": "Follow the source publish package style and preserve these constraints: "
            + "; ".join(must_include)
            + ". Do not add new sourcing or unverified claims.",
        }
    return {
        "text": "Follow the source publish package voice. Preserve thesis, citations, caveats, and operator notes. Do not add new sourcing or unverified claims.",
    }


def default_source_notes_from_publish_artifact(
    payload: dict[str, Any],
    *,
    publish_package_path: Path | None,
    artifact_path: Path | None,
) -> dict[str, list[dict[str, str]]]:
    items = [
        {
            "note": "Generated from a repo-native publish artifact for local multiplatform repurposing only; this does not authorize live publishing.",
        }
    ]
    if artifact_path is not None:
        items.append({"note": f"Source artifact: {artifact_path.resolve()}"})
    if publish_package_path is not None and (artifact_path is None or publish_package_path.resolve() != artifact_path.resolve()):
        items.append({"note": f"Publish package: {publish_package_path.resolve()}"})
    workflow_kind = clean_text(payload.get("workflow_kind"))
    if workflow_kind:
        items.append({"note": f"Upstream workflow: {workflow_kind}"})
    return {"items": items}


def build_request_from_publish_artifact(
    raw_payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    publish_package, publish_package_path = load_publish_package_from_artifact(
        payload,
        base_dir=base_dir,
        artifact_path=artifact_path,
    )
    title = clean_text(publish_package.get("title")) or extract_title(publish_package_markdown(publish_package))
    kind = publish_artifact_kind(payload)
    source_artifact = {
        "kind": kind,
        "workflow_kind": clean_text(payload.get("workflow_kind")),
        "input_path": str(artifact_path.resolve()) if artifact_path is not None else "",
        "publish_package_path": str(publish_package_path.resolve()) if publish_package_path is not None else "",
    }
    request = {
        "contract_version": REQUEST_CONTRACT_VERSION,
        "run_id": clean_text(payload.get("run_id")) or slugify(title, "publish-package"),
        "source_article": {
            "title": title,
            "markdown": publish_package_markdown(publish_package),
            "language": clean_text(publish_package.get("language") or payload.get("language") or "mixed"),
        },
        "existing_publish_package": publish_package,
        "existing_publish_package_path": str(publish_package_path) if publish_package_path is not None else "",
        "platform_targets": safe_list(payload.get("platform_targets")),
        "platform_profiles": safe_dict(payload.get("platform_profiles")),
        "creator_voice_guide": safe_dict(payload.get("creator_voice_guide"))
        or safe_dict(publish_package.get("creator_voice_guide"))
        or default_creator_voice_guide_from_publish_package(publish_package),
        "source_notes": safe_dict(payload.get("source_notes"))
        or safe_dict(publish_package.get("source_notes"))
        or default_source_notes_from_publish_artifact(payload, publish_package_path=publish_package_path, artifact_path=artifact_path),
        "source_artifact": source_artifact,
    }
    for key in ["article_brief", "article_brief_path", "evidence_bundle", "evidence_bundle_path", "citations", "output_dir"]:
        if key in payload:
            request[key] = payload[key]
    return request


def normalize_request(
    raw_payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    payload = deepcopy(raw_payload)
    if is_publish_artifact_payload(payload):
        payload = build_request_from_publish_artifact(payload, base_dir=base_dir, artifact_path=artifact_path)
    publish_package = safe_dict(payload.get("existing_publish_package")) or safe_dict(payload.get("publish_package"))
    publish_package_path = resolve_optional_path(
        payload.get("existing_publish_package_path") or payload.get("publish_package_path"),
        base_dir=base_dir,
    )
    if not publish_package:
        publish_package = load_json(publish_package_path) if publish_package_path is not None else {}
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
        "platform_profiles": safe_dict(payload.get("platform_profiles")),
        "source_artifact": safe_dict(payload.get("source_artifact")),
        "existing_publish_package_path": str(publish_package_path) if publish_package_path is not None else "",
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


def scorecard_markdown(scorecard: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- [{item['status']}] {item['check']}: {item['requirement']}"
        for item in scorecard
    ) + "\n"


def bullet_markdown(items: list[Any]) -> str:
    cleaned = [clean_text(item) for item in items if clean_text(item)]
    return "\n".join(f"- {item}" for item in cleaned) + ("\n" if cleaned else "- None supplied.\n")


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```\n"


def build_rewrite_packet_markdown(package: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Rewrite Packet: {clean_text(package.get('platform'))}",
            "",
            "Use this packet for model-assisted or human rewrite. It is not a publish command.",
            "",
            "## Preserve this core thesis",
            clean_text(package.get("core_thesis")) or "Missing core thesis. Stop and repair the request before rewriting.",
            "",
            "## Platform profile",
            json_block(safe_dict(package.get("platform_profile"))).rstrip(),
            "",
            "## Quality scorecard",
            scorecard_markdown([safe_dict(item) for item in safe_list(package.get("quality_scorecard"))]).rstrip(),
            "",
            "## Caveats to preserve",
            bullet_markdown(safe_list(package.get("caveats_preserved"))).rstrip(),
            "",
            "## Citations allowed",
            json_block(safe_list(package.get("citations_used"))).rstrip(),
            "",
            "## What not to say",
            bullet_markdown(safe_list(package.get("what_not_to_say"))).rstrip(),
            "",
            "## Human edit required",
            bullet_markdown(safe_list(package.get("human_edit_required"))).rstrip(),
            "",
            "## Draft to improve",
            str(package.get("body_or_script") or "").strip(),
            "",
        ]
    )


def build_platform_package(platform: str, request: dict[str, Any], integrity: dict[str, Any], platform_dir: Path) -> dict[str, Any]:
    title = clean_text(safe_dict(request.get("source_article")).get("title"))
    citations = deepcopy(safe_list(integrity.get("citation_inventory")))
    caveats = [clean_text(item) for item in safe_list(integrity.get("key_caveats")) if clean_text(item)]
    profile = build_platform_profile(platform, safe_dict(safe_dict(request.get("platform_profiles")).get(platform)))
    scorecard = build_quality_scorecard(platform, profile, integrity)
    body = platform_body(platform, title, integrity["core_thesis"], caveats, citations)
    content_file = platform_dir / PLATFORM_OUTPUT_FILES[platform]
    package_path = platform_dir / "platform-package.json"
    profile_path = platform_dir / "platform-profile.json"
    scorecard_path = platform_dir / "quality-scorecard.md"
    rewrite_packet_path = platform_dir / "rewrite-packet.md"
    what_not_path = platform_dir / "what-not-to-say.md"
    human_edit_path = platform_dir / "human-edit-required.md"
    package = {
        "contract_version": "multiplatform_platform_package/v1",
        "platform": platform,
        "title": platform_title(platform, title),
        "hook": body.splitlines()[0].lstrip("# ").strip(),
        "core_thesis": integrity["core_thesis"],
        "body_or_script": body,
        "platform_profile": profile,
        "quality_scorecard": scorecard,
        "citations_used": platform_citations_used(citations),
        "caveats_preserved": caveats,
        "what_not_to_say": build_what_not_to_say(platform, integrity),
        "human_edit_required": build_human_edit_required(platform, integrity),
        "source_integrity_status": clean_text(integrity.get("status")),
        "files": {
            "json": str(package_path),
            "content": str(content_file),
            "platform_profile": str(profile_path),
            "quality_scorecard": str(scorecard_path),
            "rewrite_packet": str(rewrite_packet_path),
            "what_not_to_say": str(what_not_path),
            "human_edit_required": str(human_edit_path),
        },
    }
    platform_dir.mkdir(parents=True, exist_ok=True)
    content_file.write_text(body, encoding="utf-8-sig")
    write_json(profile_path, profile)
    scorecard_path.write_text(scorecard_markdown(scorecard), encoding="utf-8-sig")
    rewrite_packet_path.write_text(build_rewrite_packet_markdown(package), encoding="utf-8-sig")
    what_not_path.write_text("\n".join(f"- {item}" for item in package["what_not_to_say"]) + "\n", encoding="utf-8-sig")
    human_edit_path.write_text("\n".join(f"- {item}" for item in package["human_edit_required"]) + "\n", encoding="utf-8-sig")
    write_json(package_path, package)
    return package


def build_report_markdown(result: dict[str, Any]) -> str:
    completion_check = safe_dict(result.get("completion_check"))
    lines = [
        f"# Multiplatform Content Repurposer: {clean_text(result.get('run_id'))}",
        "",
        f"- Source integrity: {clean_text(safe_dict(result.get('source_integrity')).get('status'))}",
        f"- Completion check: {clean_text(completion_check.get('status')) or 'not_run'}",
        f"- Output dir: {clean_text(result.get('output_dir'))}",
        f"- Platforms: {', '.join(result.get('platforms', {}).keys())}",
        "",
        "## Human Review",
    ]
    for platform, package in safe_dict(result.get("platforms")).items():
        lines.append(f"- {platform}: {clean_text(package.get('source_integrity_status'))}")
    lines.extend(["", "## Review Queue"])
    for platform, package in safe_dict(result.get("platforms")).items():
        files = safe_dict(package.get("files"))
        lines.extend(
            [
                "",
                f"### {platform}",
                f"- Status: {clean_text(package.get('source_integrity_status'))}",
                f"- Content: {clean_text(files.get('content')) or 'n/a'}",
                f"- Rewrite packet: {clean_text(files.get('rewrite_packet')) or 'n/a'}",
                f"- Quality scorecard: {clean_text(files.get('quality_scorecard')) or 'n/a'}",
                f"- Human edit checklist: {clean_text(files.get('human_edit_required')) or 'n/a'}",
                f"- What not to say: {clean_text(files.get('what_not_to_say')) or 'n/a'}",
            ]
        )
    return "\n".join(lines) + "\n"


def package_has_missing_citation(package: dict[str, Any]) -> bool:
    return any(clean_text(safe_dict(item).get("status")) == "missing" for item in safe_list(package.get("citations_used")))


def build_platform_completion_result(platform: str, package: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    files = safe_dict(package.get("files"))
    missing_file_keys = [key for key in REQUIRED_PLATFORM_FILE_KEYS if not path_exists(files.get(key))]
    if missing_file_keys:
        blockers.append(f"Missing required files: {', '.join(missing_file_keys)}")
    if not clean_text(package.get("core_thesis")):
        blockers.append("Missing core thesis.")
    if not clean_text(package.get("body_or_script")):
        blockers.append("Missing platform body_or_script.")
    if not safe_list(package.get("what_not_to_say")):
        blockers.append("Missing what_not_to_say boundaries.")
    if not safe_list(package.get("human_edit_required")):
        blockers.append("Missing human_edit_required checklist.")
    if not safe_list(package.get("caveats_preserved")):
        warnings.append("No caveats were preserved for review.")
    present_scorecard_checks = {clean_text(safe_dict(item).get("check")) for item in safe_list(package.get("quality_scorecard"))}
    missing_scorecard_checks = sorted(REQUIRED_SCORECARD_CHECKS - present_scorecard_checks)
    if missing_scorecard_checks:
        blockers.append(f"Missing quality scorecard checks: {', '.join(missing_scorecard_checks)}")
    source_integrity_status = clean_text(package.get("source_integrity_status"))
    if source_integrity_status == "blocked":
        blockers.append("Source integrity is blocked.")
    elif source_integrity_status and source_integrity_status != "ok":
        warnings.append(f"Source integrity needs human review: {source_integrity_status}.")
    if package_has_missing_citation(package):
        warnings.append("Missing citation marker is present; verify sources before reuse.")
    status = "blocked" if blockers else "warning" if warnings else "ready"
    return {
        "platform": platform,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "files": {key: clean_text(files.get(key)) for key in REQUIRED_PLATFORM_FILE_KEYS},
    }


def build_completion_check_markdown(check: dict[str, Any]) -> str:
    lines = [
        f"# Multiplatform Completion Check: {clean_text(check.get('status'))}",
        "",
        f"- Recommendation: {clean_text(check.get('recommendation'))}",
        f"- Platforms: {safe_dict(check.get('summary')).get('ready_platform_count', 0)}/{safe_dict(check.get('summary')).get('platform_count', 0)} ready",
        f"- Blockers: {safe_dict(check.get('summary')).get('blocker_count', 0)}",
        f"- Warnings: {safe_dict(check.get('summary')).get('warning_count', 0)}",
        "",
        "## Platform Results",
    ]
    for platform, platform_result in safe_dict(check.get("platforms")).items():
        lines.extend(["", f"### {platform}", f"- Status: {clean_text(platform_result.get('status'))}"])
        for blocker in safe_list(platform_result.get("blockers")):
            lines.append(f"- Blocker: {clean_text(blocker)}")
        for warning in safe_list(platform_result.get("warnings")):
            lines.append(f"- Warning: {clean_text(warning)}")
    if safe_list(check.get("blockers")):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {clean_text(item)}" for item in safe_list(check.get("blockers")))
    if safe_list(check.get("warnings")):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {clean_text(item)}" for item in safe_list(check.get("warnings")))
    return "\n".join(lines) + "\n"


def build_multiplatform_completion_check(result: dict[str, Any]) -> dict[str, Any]:
    platforms = safe_dict(result.get("platforms"))
    blockers: list[str] = []
    warnings: list[str] = []
    if not platforms:
        blockers.append("No platform packages were generated.")
    source_integrity = safe_dict(result.get("source_integrity"))
    source_status = clean_text(source_integrity.get("status"))
    if source_status == "blocked":
        blockers.append("Source integrity is blocked.")
    elif source_status and source_status != "ok":
        warnings.append(f"Source integrity needs human review: {source_status}.")
    missing_inputs = [clean_text(item) for item in safe_list(source_integrity.get("missing_inputs")) if clean_text(item)]
    if missing_inputs:
        warnings.append(f"Missing source inputs: {', '.join(missing_inputs)}.")
    platform_results = {
        platform: build_platform_completion_result(platform, safe_dict(package))
        for platform, package in platforms.items()
    }
    for platform, platform_result in platform_results.items():
        blockers.extend(f"{platform}: {item}" for item in safe_list(platform_result.get("blockers")))
        warnings.extend(f"{platform}: {item}" for item in safe_list(platform_result.get("warnings")))
    ready_platform_count = sum(1 for item in platform_results.values() if item["status"] == "ready")
    status = "blocked" if blockers else "warning" if warnings else "ready"
    recommendation = (
        "resolve_blockers_before_reuse"
        if status == "blocked"
        else "review_warnings_before_reuse"
        if status == "warning"
        else "proceed_to_human_edit"
    )
    return {
        "contract_version": COMPLETION_CHECK_CONTRACT_VERSION,
        "status": status,
        "recommendation": recommendation,
        "summary": {
            "platform_count": len(platform_results),
            "ready_platform_count": ready_platform_count,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "blockers": blockers,
        "warnings": warnings,
        "platforms": platform_results,
    }


def build_multiplatform_repurpose(
    raw_payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    request = normalize_request(raw_payload, base_dir=base_dir, artifact_path=artifact_path)
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
            "platform_profiles": request["platform_profiles"],
            "source_artifact": request["source_artifact"],
            "existing_publish_package_path": request["existing_publish_package_path"],
            "creator_voice_guide": request["creator_voice_guide"],
            "source_notes": request["source_notes"],
        },
        "source_integrity": integrity,
        "platforms": platform_packages,
        "manifest_path": str(output_dir / "manifest.json"),
        "report_path": str(output_dir / "report.md"),
        "completion_check_path": str(output_dir / "multiplatform-completion-check.json"),
        "completion_check_report_path": str(output_dir / "multiplatform-completion-check.md"),
    }
    result["completion_check"] = build_multiplatform_completion_check(result)
    result["completion_check_markdown"] = build_completion_check_markdown(result["completion_check"])
    write_json(output_dir / "request.normalized.json", result["request"])
    write_json(output_dir / "source-integrity.json", integrity)
    write_json(result["completion_check_path"], result["completion_check"])
    Path(result["completion_check_report_path"]).write_text(result["completion_check_markdown"], encoding="utf-8-sig")
    result["report_markdown"] = build_report_markdown(result)
    Path(result["report_path"]).write_text(result["report_markdown"], encoding="utf-8-sig")
    write_json(result["manifest_path"], result)
    return result


__all__ = [
    "ALL_PLATFORM_TARGETS",
    "COMPLETION_CHECK_CONTRACT_VERSION",
    "MANIFEST_CONTRACT_VERSION",
    "REQUEST_CONTRACT_VERSION",
    "build_multiplatform_repurpose",
    "load_json",
    "normalize_request",
    "write_json",
]
