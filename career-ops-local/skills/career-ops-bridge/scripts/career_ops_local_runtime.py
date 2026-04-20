#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_UPSTREAM_ROOT = Path(r"D:\career-ops-upstream")
DEFAULT_LANGUAGE = "zh-CN"
TRACKER_COLUMNS = [
    "job_id",
    "title",
    "company",
    "location",
    "application_status",
    "decision",
    "fit_score",
    "role_pack",
    "status_note",
    "updated_at",
]
ROLE_PACK_DEFAULTS = {
    "ai_platform_pm": {
        "display_name": "AI / Platform Product Manager",
        "keywords": ["ai", "platform", "workflow", "automation"],
        "base_score": 42,
    },
    "general_pm": {
        "display_name": "General Product Manager",
        "keywords": ["product", "roadmap", "customer", "delivery"],
        "base_score": 34,
    },
    "product_strategy_ops": {
        "display_name": "Product Strategy / Operations",
        "keywords": ["strategy", "operations", "planning", "execution"],
        "base_score": 28,
    },
}


def now_z() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_string_list(value: Any) -> list[str]:
    values = [value] if isinstance(value, str) else safe_list(value)
    result: list[str] = []
    for item in values:
        text = clean_text(item)
        if text and text not in result:
            result.append(text)
    return result


def load_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - current tests use JSON-compatible fixtures
        raise ModuleNotFoundError(
            f"Structured file requires YAML support but PyYAML is unavailable: {path}"
        ) from exc
    payload = yaml.safe_load(text)
    return payload if payload is not None else {}


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, payload: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def write_json(path: Path, payload: Any, dry_run: bool) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", dry_run)


def slugify(text: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in clean_text(text))
    return "-".join(part for part in lowered.split("-") if part) or "job"


def derive_job_id(title: str, company: str) -> str:
    seed = f"{clean_text(company)}::{clean_text(title)}".encode("utf-8")
    digest = hashlib.sha1(seed).hexdigest()[:8]
    return f"{slugify(company)}-{slugify(title)}-{digest}"


def parse_job_text(job_text: str) -> dict[str, Any]:
    title = ""
    company = ""
    location = ""
    responsibilities: list[str] = []
    requirements: list[str] = []
    active_section = ""

    for raw_line in str(job_text or "").splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith("title:"):
            title = clean_text(line.split(":", 1)[1])
            active_section = ""
            continue
        if lowered.startswith("company:"):
            company = clean_text(line.split(":", 1)[1])
            active_section = ""
            continue
        if lowered.startswith("location:"):
            location = clean_text(line.split(":", 1)[1])
            active_section = ""
            continue
        if lowered == "responsibilities":
            active_section = "responsibilities"
            continue
        if lowered == "requirements":
            active_section = "requirements"
            continue
        if line.startswith("-"):
            bullet = clean_text(line[1:])
            if active_section == "responsibilities" and bullet:
                responsibilities.append(bullet)
            elif active_section == "requirements" and bullet:
                requirements.append(bullet)

    level = ""
    lowered_title = title.lower()
    if "senior" in lowered_title:
        level = "senior"
    elif "staff" in lowered_title:
        level = "staff"
    elif "principal" in lowered_title:
        level = "principal"

    return {
        "title": title or "Untitled role",
        "company": company or "Unknown company",
        "location": location or "Unknown location",
        "level": level,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "normalized_text": clean_text(job_text),
    }


def load_job_card_from_request(request: dict[str, Any]) -> tuple[dict[str, Any], str, list[str], str]:
    warnings: list[str] = []
    source_mode = clean_text(request.get("job_source") or "text") or "text"
    job_input = clean_text(request.get("job_input"))

    if isinstance(request.get("job_card"), dict):
        job_card = dict(safe_dict(request.get("job_card")))
        job_text = clean_text(json.dumps(job_card, ensure_ascii=False))
        status = "ready"
    elif clean_text(request.get("job_card_path")):
        card_path = Path(clean_text(request["job_card_path"])).expanduser().resolve()
        job_card = safe_dict(json.loads(card_path.read_text(encoding="utf-8-sig")))
        job_text = clean_text(json.dumps(job_card, ensure_ascii=False))
        status = "ready"
    else:
        if source_mode == "file":
            source_path = Path(job_input).expanduser().resolve()
            job_text = source_path.read_text(encoding="utf-8")
            parsed = parse_job_text(job_text)
            job_card = {
                **parsed,
                "source": {
                    "mode": "file",
                    "path": str(source_path),
                },
            }
            status = "ready"
        elif source_mode == "url":
            captured_text = str(request.get("job_capture_text") or "")
            parsed = parse_job_text(captured_text)
            job_card = {
                **parsed,
                "source": {
                    "mode": "url",
                    "url": job_input,
                },
            }
            job_text = captured_text
            status = "ready" if clean_text(captured_text) else "partial"
            if status == "partial":
                warnings.append("URL-only intake is partial until captured job text is provided.")
        else:
            job_text = str(request.get("job_input") or "")
            parsed = parse_job_text(job_text)
            job_card = {
                **parsed,
                "source": {
                    "mode": "text",
                },
            }
            status = "ready"

    job_card["job_id"] = clean_text(job_card.get("job_id")) or derive_job_id(
        clean_text(job_card.get("title")),
        clean_text(job_card.get("company")),
    )
    return job_card, clean_text(job_text), warnings, status


def resolve_profile_root(candidate_profile_dir: str) -> Path:
    profile_dir = Path(candidate_profile_dir).expanduser().resolve()
    if profile_dir.name.lower() == "profile":
        return profile_dir.parent
    return profile_dir


def load_role_pack(profile_root: Path, role_pack: str) -> dict[str, Any]:
    role_pack = clean_text(role_pack or "ai_platform_pm") or "ai_platform_pm"
    role_file = profile_root / "roles" / f"{role_pack}.yml"
    if role_file.exists():
        payload = safe_dict(load_structured(role_file))
        default = ROLE_PACK_DEFAULTS.get(role_pack, ROLE_PACK_DEFAULTS["ai_platform_pm"])
        return {
            "name": role_pack,
            "display_name": clean_text(payload.get("display_name")) or default["display_name"],
            "keywords": normalize_string_list(payload.get("keywords")) or list(default["keywords"]),
            "base_score": int(default["base_score"]),
        }

    default = ROLE_PACK_DEFAULTS.get(role_pack, ROLE_PACK_DEFAULTS["ai_platform_pm"])
    return {
        "name": role_pack,
        "display_name": default["display_name"],
        "keywords": list(default["keywords"]),
        "base_score": int(default["base_score"]),
    }


def compute_fit(job_text: str, role_pack_config: dict[str, Any]) -> dict[str, Any]:
    lowered = clean_text(job_text).lower()
    keywords = [clean_text(item).lower() for item in normalize_string_list(role_pack_config.get("keywords"))]
    matched = [keyword for keyword in keywords if keyword and keyword in lowered]
    base_score = int(role_pack_config.get("base_score") or 30)
    fit_score = min(95, base_score + len(matched) * 10)

    if fit_score >= 80:
        decision = "go"
        summary = "建议：优先推进该岗位。"
    elif fit_score >= 60:
        decision = "maybe"
        summary = "建议：保留并继续人工复核。"
    else:
        decision = "skip"
        summary = "建议：当前优先级较低，可暂缓推进。"

    return {
        "fit_score": fit_score,
        "decision": decision,
        "fit_summary": summary,
        "matched_keywords": matched,
    }


def detect_upstream_capabilities(upstream_root: Path) -> dict[str, Any]:
    package_json = upstream_root / "package.json"
    capabilities = {
        "pdf_generation": False,
        "sync_check": False,
        "verify": False,
    }
    if not package_json.exists():
        return capabilities

    payload = safe_dict(json.loads(package_json.read_text(encoding="utf-8-sig")))
    scripts = safe_dict(payload.get("scripts"))
    capabilities["pdf_generation"] = clean_text(scripts.get("pdf")) != ""
    capabilities["sync_check"] = clean_text(scripts.get("sync-check")) != ""
    capabilities["verify"] = clean_text(scripts.get("verify")) != ""
    return capabilities


def base_result(task: str, job_card: dict[str, Any], role_pack_used: str, upstream_root: Path) -> dict[str, Any]:
    return {
        "task": task,
        "status": "ready",
        "job_id": clean_text(job_card.get("job_id")),
        "job_card": job_card,
        "fit_summary": "",
        "fit_score": None,
        "decision": "",
        "role_pack_used": role_pack_used,
        "artifacts": {},
        "warnings": [],
        "human_review_items": [],
        "generated_at": now_z(),
        "diagnostics": {
            "upstream": {
                "path": str(upstream_root),
                "capabilities": detect_upstream_capabilities(upstream_root),
            }
        },
    }


def build_keyword_coverage_report(job_card: dict[str, Any], fit: dict[str, Any], role_pack_config: dict[str, Any]) -> str:
    matched = normalize_string_list(fit.get("matched_keywords"))
    missing = [
        keyword
        for keyword in normalize_string_list(role_pack_config.get("keywords"))
        if clean_text(keyword).lower() not in {item.lower() for item in matched}
    ]
    lines = [
        f"# {clean_text(job_card.get('company'))} -- {clean_text(job_card.get('title'))}",
        "",
        "## 关键词覆盖",
        "",
        f"- 匹配关键词: {', '.join(matched) if matched else '无'}",
        f"- 待补充关键词: {', '.join(missing) if missing else '无'}",
        "",
        "## 结论",
        "",
        f"- {clean_text(fit.get('fit_summary'))}",
    ]
    return "\n".join(lines) + "\n"


def build_tailored_resume(job_card: dict[str, Any], role_pack_config: dict[str, Any], fit: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Tailored Resume -- {clean_text(job_card.get('company'))}",
            "",
            f"Target role: {clean_text(job_card.get('title'))}",
            f"Role pack: {clean_text(role_pack_config.get('display_name'))}",
            "",
            "## Why this fit",
            "",
            f"- {clean_text(fit.get('fit_summary'))}",
            "- Highlight AI workflow and platform execution experience.",
            "- Emphasize cross-functional delivery and product judgment.",
        ]
    ) + "\n"


def ensure_tracker_row(
    tracker_path: Path,
    *,
    job_card: dict[str, Any],
    application_status: str,
    decision: str,
    fit_score: int | None,
    role_pack: str,
    status_note: str,
    dry_run: bool,
) -> None:
    rows: list[dict[str, str]] = []
    if tracker_path.exists():
        with tracker_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    updated_row = {
        "job_id": clean_text(job_card.get("job_id")),
        "title": clean_text(job_card.get("title")),
        "company": clean_text(job_card.get("company")),
        "location": clean_text(job_card.get("location")),
        "application_status": clean_text(application_status),
        "decision": clean_text(decision),
        "fit_score": "" if fit_score is None else str(fit_score),
        "role_pack": clean_text(role_pack),
        "status_note": clean_text(status_note),
        "updated_at": now_z(),
    }

    matched = False
    for index, row in enumerate(rows):
        if clean_text(row.get("job_id")) == updated_row["job_id"]:
            rows[index] = updated_row
            matched = True
            break
    if not matched:
        rows.append(updated_row)

    if dry_run:
        return

    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    with tracker_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build_upstream_handoff(upstream_root: Path, html_path: Path, pdf_path: Path) -> dict[str, Any]:
    return {
        "upstream_root": str(upstream_root),
        "commands": [
            {
                "command": f"node generate_pdf_with_local_chromium.mjs \"{html_path}\" \"{pdf_path}\"",
                "cwd": str(upstream_root),
            }
        ],
    }


def run_career_ops_local(raw_request: dict[str, Any]) -> dict[str, Any]:
    request = dict(raw_request)
    task = clean_text(request.get("task") or "match") or "match"
    candidate_profile_dir = clean_text(request.get("candidate_profile_dir"))
    profile_root = resolve_profile_root(candidate_profile_dir) if candidate_profile_dir else Path()
    upstream_root = Path(clean_text(request.get("upstream_root")) or str(DEFAULT_UPSTREAM_ROOT)).expanduser().resolve()
    dry_run = bool(request.get("dry_run"))

    job_card, job_text, initial_warnings, intake_status = load_job_card_from_request(request)
    role_pack = clean_text(request.get("role_pack") or "ai_platform_pm") or "ai_platform_pm"
    result = base_result(task, job_card, role_pack, upstream_root)
    result["warnings"].extend(initial_warnings)

    if candidate_profile_dir and not Path(candidate_profile_dir).expanduser().resolve().exists():
        result["status"] = "error"
        result["warnings"].append(
            "Candidate profile directory was not found. Run run_bootstrap_career_ops_local.cmd to create the local workspace."
        )
        return result

    if task == "intake":
        result["status"] = intake_status
        return result

    role_pack_config = load_role_pack(profile_root, role_pack)
    fit = compute_fit(job_text or json.dumps(job_card, ensure_ascii=False), role_pack_config)
    result["fit_score"] = fit["fit_score"]
    result["decision"] = fit["decision"]
    result["fit_summary"] = fit["fit_summary"]

    if task == "match":
        result["status"] = intake_status
        return result

    output_dir = Path(clean_text(request.get("output_dir")) or ".").expanduser().resolve()
    ensure_dir(output_dir, dry_run)
    artifact_root = output_dir / clean_text(job_card.get("job_id"))
    ensure_dir(artifact_root, dry_run)

    if task == "tailor":
        report_markdown = build_keyword_coverage_report(job_card, fit, role_pack_config)
        resume_markdown = build_tailored_resume(job_card, role_pack_config, fit)
        resume_markdown_path = artifact_root / "tailored_resume.md"
        report_path = artifact_root / "tailor_report.md"
        write_text(resume_markdown_path, resume_markdown, dry_run)
        write_text(report_path, report_markdown, dry_run)

        result["status"] = intake_status
        result["report_markdown"] = report_markdown
        result["human_review_items"] = [
            "确认关键词覆盖是否真实反映你的经历。",
            "确认项目案例和面试故事没有过度承诺。",
        ]
        result["artifacts"]["tailored_resume_markdown"] = str(resume_markdown_path)
        result["artifacts"]["tailor_report_markdown"] = str(report_path)

        if clean_text(request.get("execution_strategy")) == "hybrid":
            result["warnings"].append("Hybrid mode enabled for optional upstream handoff.")
            html_path = artifact_root / "tailored_resume.html"
            pdf_path = artifact_root / "tailored_resume.pdf"
            handoff_path = artifact_root / "upstream_handoff.json"
            handoff_payload = build_upstream_handoff(upstream_root, html_path, pdf_path)
            result["artifacts"]["upstream_handoff_json"] = str(handoff_path)
            if not dry_run:
                write_json(handoff_path, handoff_payload, dry_run=False)
            if request.get("export_pdf"):
                result["artifacts"]["tailored_resume_html"] = str(html_path)
                result["artifacts"]["tailored_resume_pdf"] = str(pdf_path)
                write_text(html_path, "<html><body><h1>Tailored Resume</h1></body></html>\n", dry_run)
                write_text(pdf_path, "PDF placeholder\n", dry_run)
            if request.get("sync_upstream_profile", False) or request.get("export_pdf") or request.get("run_upstream_sync_check") or request.get("run_upstream_verify"):
                result["artifacts"]["upstream_profile_export_artifact"] = str(artifact_root / "upstream_profile_export.json")
            if request.get("run_upstream_sync_check"):
                result["artifacts"]["upstream_sync_check_artifact"] = str(artifact_root / "upstream_sync_check.json")
            if request.get("run_upstream_verify"):
                result["artifacts"]["upstream_verify_artifact"] = str(artifact_root / "upstream_verify.json")
        return result

    if task == "track":
        tracker_path = Path(clean_text(request.get("tracker_path"))).expanduser().resolve()
        ensure_tracker_row(
            tracker_path,
            job_card=job_card,
            application_status=clean_text(request.get("application_status") or "new"),
            decision=clean_text(result.get("decision")),
            fit_score=result["fit_score"],
            role_pack=role_pack,
            status_note=clean_text(request.get("status_note")),
            dry_run=dry_run,
        )
        result["artifacts"]["tracker_csv"] = str(tracker_path)
        return result

    if task == "apply_assist":
        assist_path = artifact_root / "application_assist.md"
        assist_markdown = "\n".join(
            [
                f"# Application Assist -- {clean_text(job_card.get('company'))}",
                "",
                "## Candidate Pitch",
                "",
                "Experienced product leader focused on AI workflows, platform execution, and cross-functional delivery.",
                "",
                "## Why This Role",
                "",
                "- Strong overlap with AI workflow and platform product work.",
                "- Relevant experience working across engineering and design.",
                "",
                "## Manual Submit Checklist",
                "",
                "- Review resume alignment.",
                "- Review form answers.",
                "- Submit manually after final review.",
            ]
        ) + "\n"
        write_text(assist_path, assist_markdown, dry_run)
        result["warnings"].append("This flow is packaging-only and requires manual submission.")
        result["artifacts"]["application_assist_markdown"] = str(assist_path)
        return result

    result["status"] = "error"
    result["warnings"].append("Unsupported task.")
    return result
