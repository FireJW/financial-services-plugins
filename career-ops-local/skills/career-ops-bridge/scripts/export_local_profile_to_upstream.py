#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_LOCAL_ROOT = Path(r"D:\career-ops-local")
DEFAULT_UPSTREAM_ROOT = Path(r"D:\career-ops-upstream")


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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml  # type: ignore

        payload = yaml.safe_load(text)
        return payload if payload is not None else {}


def write_text(path: Path, payload: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def extract_markdown_heading(text: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = clean_text(raw_line)
        if line.startswith("# "):
            return clean_text(line[2:])
    return "Candidate"


def extract_markdown_section(text: str, heading: str) -> str:
    lines = str(text or "").splitlines()
    target = heading.lower()
    active = False
    captured: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip()
        normalized = clean_text(line).rstrip(":").lower()
        if normalized == target:
            active = True
            continue
        if active and normalized.startswith("## "):
            break
        if active:
            captured.append(line)
    return "\n".join(captured).strip()


def extract_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in str(section_text or "").splitlines():
        line = clean_text(raw_line)
        if re.match(r"^[-*]\s+", raw_line.lstrip()) or re.match(r"^\d+[.)]\s+", raw_line.lstrip()):
            line = re.sub(r"^[-*]\s*", "", line)
            line = re.sub(r"^\d+[.)]\s*", "", line)
            if line and line not in bullets:
                bullets.append(line)
    return bullets


def detect_contact(master_resume_text: str) -> dict[str, str]:
    patterns = {
        "email": r"email:\s*([^\s]+@[^\s]+)",
        "linkedin": r"linkedin:\s*([^\s]+)",
        "portfolio": r"portfolio:\s*([^\s]+)",
        "github": r"github:\s*([^\s]+)",
        "twitter": r"(?:twitter|x):\s*([^\s]+)",
        "phone": r"phone:\s*([^\n]+)",
        "location": r"location:\s*([^\n]+)",
    }
    result: dict[str, str] = {}
    lower = master_resume_text.lower()
    for key, pattern in patterns.items():
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            result[key] = clean_text(match.group(1))
    return result


def infer_location_fields(preferred_location: str) -> dict[str, str]:
    location = clean_text(preferred_location) or "Remote"
    city = location.split("/")[0].strip()
    country = "China" if "shanghai" in city.lower() else ""
    timezone = "Asia/Shanghai" if "shanghai" in city.lower() else ""
    return {
        "location": location,
        "city": city,
        "country": country,
        "timezone": timezone,
    }


def load_role_display_names(local_root: Path) -> list[str]:
    roles_dir = local_root / "roles"
    display_names: list[str] = []
    if not roles_dir.exists():
        return display_names
    for role_file in sorted(roles_dir.glob("*.yml")):
        payload = safe_dict(load_structured(role_file))
        name = clean_text(payload.get("display_name"))
        if name and name not in display_names:
            display_names.append(name)
    return display_names


def yaml_quote(value: str) -> str:
    escaped = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_profile_yaml(*, candidate: dict[str, str], role_names: list[str], constraints: dict[str, Any], stories: list[dict[str, Any]]) -> str:
    superpowers = []
    for story in stories[:3]:
        title = clean_text(story.get("title"))
        if title:
            superpowers.append(title)
    proof_points = []
    for story in stories[:3]:
        proof_points.append(
            {
                "name": clean_text(story.get("title")) or clean_text(story.get("id")) or "Proof point",
                "url": "",
                "hero_metric": clean_text(story.get("summary")),
            }
        )

    lines = [
        "candidate:",
        f"  full_name: {yaml_quote(candidate['full_name'])}",
        f"  email: {yaml_quote(candidate['email'])}",
        f"  phone: {yaml_quote(candidate['phone'])}",
        f"  location: {yaml_quote(candidate['location'])}",
        f"  linkedin: {yaml_quote(candidate['linkedin'])}",
        f"  portfolio_url: {yaml_quote(candidate['portfolio_url'])}",
        f"  github: {yaml_quote(candidate['github'])}",
        f"  twitter: {yaml_quote(candidate['twitter'])}",
        "",
        "target_roles:",
        "  primary:",
    ]
    for name in role_names[:3]:
        lines.append(f"    - {yaml_quote(name)}")
    lines.extend(
        [
            "  archetypes:",
        ]
    )
    for name in role_names[:3]:
        lines.extend(
            [
                f"    - name: {yaml_quote(name)}",
                '      level: "Senior"',
                '      fit: "primary"',
            ]
        )
    lines.extend(
        [
            "",
            "narrative:",
            f"  headline: {yaml_quote(candidate['headline'])}",
            f"  exit_story: {yaml_quote(candidate['exit_story'])}",
            "  superpowers:",
        ]
    )
    for item in superpowers or ["Cross-functional product execution", "AI workflow thinking", "Platform product judgment"]:
        lines.append(f"    - {yaml_quote(item)}")
    lines.append("  proof_points:")
    for point in proof_points:
        lines.extend(
            [
                f"    - name: {yaml_quote(point['name'])}",
                f"      url: {yaml_quote(point['url'])}",
                f"      hero_metric: {yaml_quote(point['hero_metric'])}",
            ]
        )
    lines.extend(
        [
            "",
            "compensation:",
            f"  target_range: {yaml_quote(clean_text(constraints.get('compensation_expectation')) or 'Role-specific')}",
            '  currency: "USD"',
            '  minimum: "TBD"',
            f"  location_flexibility: {yaml_quote(clean_text(constraints.get('remote_preference')) or 'Flexible')}",
            "",
            "location:",
            f"  country: {yaml_quote(candidate['country'])}",
            f"  city: {yaml_quote(candidate['city'])}",
            f"  timezone: {yaml_quote(candidate['timezone'])}",
            f"  visa_status: {yaml_quote(clean_text(constraints.get('work_authorization')) or 'Confirm per role')}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_cv_markdown(*, candidate: dict[str, str], summary: str, experience_bullets: list[str], stories: list[dict[str, Any]], skills: list[str]) -> str:
    project_lines = []
    for story in stories:
        project_lines.append(f"- **{clean_text(story.get('title')) or clean_text(story.get('id')) or 'Project'}** -- {clean_text(story.get('summary'))}")
    skill_line = ", ".join(skills[:12]) if skills else "AI workflows, product strategy, execution"
    return "\n".join(
        [
            f"# CV -- {candidate['full_name']}",
            "",
            f"**Location:** {candidate['location']}",
            f"**Email:** {candidate['email']}",
            f"**LinkedIn:** {candidate['linkedin']}",
            f"**Portfolio:** {candidate['portfolio_url']}",
            f"**GitHub:** {candidate['github']}",
            "",
            "## Professional Summary",
            "",
            summary or candidate["headline"],
            "",
            "## Work Experience",
            "",
            "### Selected Experience",
            *[f"- {bullet}" for bullet in experience_bullets],
            "",
            "## Projects",
            "",
            *project_lines,
            "",
            "## Skills",
            "",
            f"- **Core:** {skill_line}",
            "",
        ]
    )


def build_article_digest(stories: list[dict[str, Any]]) -> str:
    lines = ["# Article Digest", ""]
    for story in stories:
        lines.append(f"## {clean_text(story.get('title')) or clean_text(story.get('id')) or 'Project'}")
        lines.append("")
        lines.append(clean_text(story.get("summary")))
        lines.append("")
        for bullet in normalize_string_list(story.get("bullets")):
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export local private profile data into the upstream career-ops format.")
    parser.add_argument("--local-root", default=str(DEFAULT_LOCAL_ROOT))
    parser.add_argument("--upstream-root", default=str(DEFAULT_UPSTREAM_ROOT))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    local_root = Path(args.local_root).expanduser().resolve()
    upstream_root = Path(args.upstream_root).expanduser().resolve()
    profile_root = local_root / "profile"
    master_resume_path = profile_root / "master_resume.md"
    constraints_path = profile_root / "constraints.yml"
    stories_path = profile_root / "stories_bank.yml"
    brag_bank_path = profile_root / "brag_bank.md"

    master_resume_text = master_resume_path.read_text(encoding="utf-8")
    constraints = safe_dict(load_structured(constraints_path)) if constraints_path.exists() else {}
    stories_payload = safe_dict(load_structured(stories_path))
    stories = [safe_dict(item) for item in safe_list(stories_payload.get("stories"))]
    brag_bank_text = brag_bank_path.read_text(encoding="utf-8") if brag_bank_path.exists() else ""

    contact = detect_contact(master_resume_text)
    location_fields = infer_location_fields(clean_text(contact.get("location")) or clean_text(constraints.get("preferred_location")))
    role_names = load_role_display_names(local_root) or ["AI / Platform Product Manager", "General Product Manager", "Product Strategy / Operations"]
    summary = extract_markdown_section(master_resume_text, "## summary")
    experience_bullets = extract_bullets(extract_markdown_section(master_resume_text, "## experience highlights")) or extract_bullets(brag_bank_text)
    candidate = {
        "full_name": extract_markdown_heading(master_resume_text) or "Candidate",
        "email": clean_text(contact.get("email")) or "candidate@example.com",
        "phone": clean_text(contact.get("phone")) or "",
        "location": location_fields["location"],
        "linkedin": clean_text(contact.get("linkedin")) or "linkedin.com/in/candidate",
        "portfolio_url": clean_text(contact.get("portfolio")) or "https://example.com",
        "github": clean_text(contact.get("github")) or "github.com/candidate",
        "twitter": clean_text(contact.get("twitter")) or "",
        "city": location_fields["city"],
        "country": location_fields["country"],
        "timezone": location_fields["timezone"],
        "headline": summary.splitlines()[0] if summary else "Product leader focused on AI workflows and platform execution",
        "exit_story": "Exported from local-first career ops profile. Replace placeholders with your real narrative where needed.",
    }
    skill_terms: list[str] = []
    for story in stories:
        for theme in normalize_string_list(story.get("themes")):
            if theme not in skill_terms:
                skill_terms.append(theme)

    cv_markdown = build_cv_markdown(
        candidate=candidate,
        summary=summary or candidate["headline"],
        experience_bullets=experience_bullets,
        stories=stories,
        skills=skill_terms,
    )
    profile_yaml = build_profile_yaml(
        candidate=candidate,
        role_names=role_names,
        constraints=constraints,
        stories=stories,
    )
    article_digest = build_article_digest(stories)

    targets = {
        "cv": upstream_root / "cv.md",
        "profile": upstream_root / "config" / "profile.yml",
        "article_digest": upstream_root / "article-digest.md",
    }

    warnings: list[str] = []
    if candidate["email"] == "candidate@example.com":
        warnings.append("Email was not found in the local profile, so a placeholder value was exported.")
    if candidate["linkedin"] == "linkedin.com/in/candidate":
        warnings.append("LinkedIn was not found in the local profile, so a placeholder value was exported.")
    if candidate["portfolio_url"] == "https://example.com":
        warnings.append("Portfolio URL was not found in the local profile, so a placeholder value was exported.")

    for key, target in targets.items():
        if target.exists() and not args.force:
            warnings.append(f"Skipped existing upstream file without --force: {target}")
            continue
        payload = {
            "cv": cv_markdown,
            "profile": profile_yaml,
            "article_digest": article_digest,
        }[key]
        write_text(target, payload, args.dry_run)

    result = {
        "status": "ready",
        "local_root": str(local_root),
        "upstream_root": str(upstream_root),
        "written": {key: str(path) for key, path in targets.items()},
        "warnings": warnings,
        "generated_at": now_z(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
