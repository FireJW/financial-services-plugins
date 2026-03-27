#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent

from benchmark_library_refresh_runtime import case_fingerprint, clean_text, load_case_collection, load_seeds, safe_dict, safe_list


def unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = clean_text(item)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def host_for_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    return clean_text(parsed.netloc).lower()


def normalize_refresh_surface_policy(value: Any) -> str:
    text = clean_text(value).lower()
    if text in {"mirror_allowed", "proxy_allowed"}:
        return text
    return "first_party_required"


def is_non_primary_fetch_allowed(fetch_provenance: str, refresh_surface_policy: str) -> bool:
    provenance = clean_text(fetch_provenance).lower()
    policy = normalize_refresh_surface_policy(refresh_surface_policy)
    if provenance.startswith("first_party"):
        return True
    if policy == "mirror_allowed" and provenance == "mirror":
        return True
    if policy == "proxy_allowed" and provenance:
        return True
    return False


def format_non_primary_fetch(item: dict[str, Any]) -> str:
    shape = clean_text(item.get("benchmark_case_shape")) or "article"
    return (
        f"- {clean_text(item.get('case_id'))} | {clean_text(item.get('fetch_provenance'))} | "
        f"policy={clean_text(item.get('refresh_surface_policy'))} | shape={shape} | "
        f"{clean_text(item.get('fetch_url'))}"
    )


def resolve_audit_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    library_path = Path(clean_text(raw_payload.get("library_path"))).expanduser()
    if not clean_text(raw_payload.get("library_path")):
        raise ValueError("benchmark-readiness requires library_path")

    resolved_library_path = library_path.resolve()
    cases_dir = resolved_library_path.parent
    candidate_library_path = (
        Path(clean_text(raw_payload.get("candidate_library_path"))).expanduser()
        if clean_text(raw_payload.get("candidate_library_path"))
        else cases_dir / "benchmark-case-candidates.json"
    )
    seeds_path = (
        Path(clean_text(raw_payload.get("seeds_path"))).expanduser()
        if clean_text(raw_payload.get("seeds_path"))
        else cases_dir / "benchmark-refresh-seeds.json"
    )
    observations_path = (
        Path(clean_text(raw_payload.get("observations_path"))).expanduser()
        if clean_text(raw_payload.get("observations_path"))
        else cases_dir / "benchmark-case-observations.jsonl"
    )
    return {
        "library_path": resolved_library_path,
        "candidate_library_path": candidate_library_path.resolve() if candidate_library_path.exists() else candidate_library_path,
        "seeds_path": seeds_path.resolve() if seeds_path.exists() else seeds_path,
        "observations_path": observations_path.resolve() if observations_path.exists() else observations_path,
        "refresh_existing_cases": bool(raw_payload.get("refresh_existing_cases", True)),
        "discover_new_cases": bool(raw_payload.get("discover_new_cases", True)),
        "auto_add_new_cases": bool(raw_payload.get("auto_add_new_cases", True)),
        "allow_reference_url_fallback": bool(raw_payload.get("allow_reference_url_fallback", False)),
        "run_benchmark_index_after_refresh": bool(raw_payload.get("run_benchmark_index_after_refresh", True)),
    }


def build_report(result: dict[str, Any]) -> str:
    summary = safe_dict(result.get("summary"))
    lines = [
        "# Benchmark Refresh Readiness",
        "",
        f"- Readiness level: {clean_text(result.get('readiness_level'))}",
        f"- Ready for daily refresh: {str(bool(result.get('ready_for_daily_refresh'))).lower()}",
        f"- Reviewed cases: {summary.get('reviewed_cases', 0)}",
        f"- Candidate cases: {summary.get('candidate_cases', 0)}",
        f"- Enabled seeds: {summary.get('enabled_seed_sources', 0)}",
        f"- Reviewed cases missing fetch_url: {summary.get('reviewed_cases_missing_fetch_url', 0)}",
        f"- Reviewed fetch_url coverage: {summary.get('reviewed_fetch_url_coverage_pct', 0)}%",
        f"- Reviewed non-primary fetch surfaces: {summary.get('reviewed_non_primary_fetches', 0)}",
        f"- Reviewed non-primary fetches requiring upgrade: {summary.get('reviewed_non_primary_fetches_requiring_upgrade', 0)}",
        f"- Reviewed allowed proxy or mirror fetches: {summary.get('reviewed_non_primary_fetches_allowed', 0)}",
        f"- Enabled seeds missing seed_url: {summary.get('enabled_seed_sources_missing_seed_url', 0)}",
        f"- Enabled seeds without filters: {summary.get('enabled_seed_sources_without_filters', 0)}",
        f"- Duplicate candidate case IDs: {summary.get('duplicate_candidate_case_ids', 0)}",
        f"- Duplicate candidate URLs: {summary.get('duplicate_candidate_urls', 0)}",
        f"- Observation paths consistent: {str(bool(summary.get('observations_path_consistent'))).lower()}",
        "",
        "## Blockers",
        "",
    ]
    blockers = safe_list(result.get("blockers"))
    if not blockers:
        lines.append("- none")
    else:
        for item in blockers:
            lines.append(f"- {clean_text(item)}")
    lines.extend(["", "## Warnings", ""])
    warnings = safe_list(result.get("warnings"))
    if not warnings:
        lines.append("- none")
    else:
        for item in warnings:
            lines.append(f"- {clean_text(item)}")
    lines.extend(["", "## Next Actions", ""])
    for item in safe_list(result.get("next_actions")) or ["none"]:
        lines.append(f"- {clean_text(item)}")
    lines.extend(["", "## Fetch URL Gaps", ""])
    fetch_gaps = safe_list(result.get("reviewed_case_fetch_url_gaps"))
    if not fetch_gaps:
        lines.append("- none")
    else:
        for item in fetch_gaps:
            lines.append(
                f"- {clean_text(item.get('case_id'))} | {clean_text(item.get('account_name'))} | "
                f"{clean_text(item.get('title'))} | {clean_text(item.get('reference_url_host'))}"
            )
    lines.extend(["", "## Non-Primary Fetch Surfaces Requiring Upgrade", ""])
    non_primary = safe_list(result.get("reviewed_non_primary_fetches_requiring_upgrade"))
    if not non_primary:
        lines.append("- none")
    else:
        for item in non_primary:
            lines.append(format_non_primary_fetch(item))
    lines.extend(["", "## Accepted Proxy Or Mirror Fetch Surfaces", ""])
    allowed_non_primary = safe_list(result.get("reviewed_non_primary_fetches_allowed"))
    if not allowed_non_primary:
        lines.append("- none")
    else:
        for item in allowed_non_primary:
            lines.append(format_non_primary_fetch(item))
    lines.extend(["", "## Seed Gaps", ""])
    seed_gaps = safe_list(result.get("seed_findings"))
    if not seed_gaps:
        lines.append("- none")
    else:
        for item in seed_gaps:
            lines.append(
                f"- {clean_text(item.get('source_id'))} | enabled={str(bool(item.get('enabled'))).lower()} | "
                f"seed_url={clean_text(item.get('seed_url')) or 'missing'} | "
                f"has_filters={str(bool(item.get('has_filters'))).lower()}"
            )
    return "\n".join(lines).strip() + "\n"


def run_benchmark_readiness_audit(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = resolve_audit_request(raw_payload)
    reviewed_library = load_case_collection(
        request["library_path"],
        default_name="decision-journal-benchmark-cases",
        default_status="reviewed",
        include_statuses=["reviewed"],
    )
    candidate_library = load_case_collection(
        request["candidate_library_path"],
        default_name="decision-journal-benchmark-candidates",
        default_status="candidate",
        include_statuses=["candidate"],
    )
    seeds_payload = load_seeds(request["seeds_path"])

    reviewed_cases = safe_list(reviewed_library.get("cases"))
    candidate_cases = safe_list(candidate_library.get("cases"))
    seed_sources = safe_list(seeds_payload.get("sources"))
    enabled_seed_sources = [source for source in seed_sources if source.get("enabled", True) is not False]
    reviewed_case_count = len(reviewed_cases)

    reviewed_case_fetch_url_gaps = [
        {
            "case_id": clean_text(case.get("case_id")),
            "account_name": clean_text(case.get("account_name")),
            "title": clean_text(case.get("title")),
            "reference_url": clean_text(case.get("canonical_url") or case.get("url")),
            "reference_url_host": host_for_url(case.get("canonical_url") or case.get("url")),
        }
        for case in reviewed_cases
        if not clean_text(case.get("fetch_url"))
    ]
    reviewed_non_primary_fetches = []
    reviewed_non_primary_fetches_allowed = []
    reviewed_non_primary_fetches_requiring_upgrade = []
    for case in reviewed_cases:
        fetch_url = clean_text(case.get("fetch_url"))
        fetch_provenance = clean_text(case.get("fetch_provenance")) or "unknown"
        if not fetch_url or fetch_provenance.lower().startswith("first_party"):
            continue
        item = {
            "case_id": clean_text(case.get("case_id")),
            "fetch_provenance": fetch_provenance,
            "fetch_url": fetch_url,
            "refresh_surface_policy": normalize_refresh_surface_policy(case.get("refresh_surface_policy")),
            "benchmark_case_shape": clean_text(case.get("benchmark_case_shape")) or "article",
        }
        reviewed_non_primary_fetches.append(item)
        if is_non_primary_fetch_allowed(fetch_provenance, item["refresh_surface_policy"]):
            reviewed_non_primary_fetches_allowed.append(item)
        else:
            reviewed_non_primary_fetches_requiring_upgrade.append(item)

    seed_findings = []
    enabled_seed_sources_missing_seed_url = []
    enabled_seed_sources_without_filters = []
    for source in seed_sources:
        enabled = source.get("enabled", True) is not False
        seed_url = clean_text(source.get("seed_url") or source.get("fetch_url") or source.get("url"))
        has_filters = any(
            safe_list(source.get(key))
            for key in (
                "include_url_patterns",
                "exclude_url_patterns",
                "include_title_keywords",
                "exclude_title_keywords",
            )
        )
        finding = {
            "source_id": clean_text(source.get("source_id")) or clean_text(source.get("account_name")) or "unknown-source",
            "enabled": enabled,
            "seed_url": seed_url,
            "has_filters": has_filters,
        }
        seed_findings.append(finding)
        if not enabled:
            continue
        if not seed_url:
            enabled_seed_sources_missing_seed_url.append(finding)
        if not has_filters:
            enabled_seed_sources_without_filters.append(finding)

    candidate_case_id_counts: dict[str, int] = {}
    candidate_url_counts: dict[str, int] = {}
    candidate_fingerprint_counts: dict[str, int] = {}
    for case in candidate_cases:
        case_id = clean_text(case.get("case_id"))
        canonical_url = clean_text(case.get("canonical_url"))
        fingerprint = case_fingerprint(case)
        if case_id:
            candidate_case_id_counts[case_id] = candidate_case_id_counts.get(case_id, 0) + 1
        if canonical_url:
            candidate_url_counts[canonical_url] = candidate_url_counts.get(canonical_url, 0) + 1
        if fingerprint:
            candidate_fingerprint_counts[fingerprint] = candidate_fingerprint_counts.get(fingerprint, 0) + 1
    duplicate_candidate_case_ids = sorted([case_id for case_id, count in candidate_case_id_counts.items() if count > 1])
    duplicate_candidate_urls = sorted([url for url, count in candidate_url_counts.items() if count > 1])
    duplicate_candidate_fingerprints = sorted(
        [fingerprint for fingerprint, count in candidate_fingerprint_counts.items() if count > 1]
    )
    reviewed_status_leaks = sorted(
        unique_keep_order(
            [clean_text(case.get("case_id")) for case in reviewed_cases if clean_text(case.get("curation_status")) not in {"", "reviewed"}]
        )
    )
    candidate_status_leaks = sorted(
        unique_keep_order(
            [clean_text(case.get("case_id")) for case in candidate_cases if clean_text(case.get("curation_status")) not in {"", "candidate"}]
        )
    )
    observations_path_name = request["observations_path"].name
    observations_path_consistent = (
        clean_text(reviewed_library.get("observation_log_path")) in {"", observations_path_name}
        and clean_text(candidate_library.get("observation_log_path")) in {"", observations_path_name}
    )

    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if request["refresh_existing_cases"] and not request["allow_reference_url_fallback"] and reviewed_case_fetch_url_gaps:
        blockers.append(
            f"{len(reviewed_case_fetch_url_gaps)} reviewed cases are missing fetch_url while reference fallback is disabled."
        )
        next_actions.append("Populate first-party fetch_url for reviewed cases before relying on daily refresh.")
    if request["discover_new_cases"] and not enabled_seed_sources:
        blockers.append("Discovery is enabled but benchmark-refresh-seeds.json has no enabled sources.")
        next_actions.append("Add 2-4 tightly scoped enabled seeds before enabling daily candidate discovery.")
    if request["discover_new_cases"] and enabled_seed_sources_missing_seed_url:
        blockers.append(
            f"{len(enabled_seed_sources_missing_seed_url)} enabled seed sources are missing seed_url."
        )
        next_actions.append("Fill seed_url for every enabled source or disable the incomplete source.")
    if reviewed_status_leaks:
        blockers.append(f"Reviewed library contains non-reviewed statuses: {', '.join(reviewed_status_leaks)}.")
        next_actions.append("Keep reviewed library status-pure before using it as benchmark ground truth.")
    if candidate_status_leaks:
        blockers.append(f"Candidate library contains non-candidate statuses: {', '.join(candidate_status_leaks)}.")
        next_actions.append("Keep candidate inbox status-pure before enabling automatic discovery.")
    if request["allow_reference_url_fallback"]:
        warnings.append("Reference URL fallback is enabled; aggregator or commentary pages may be scraped as article truth.")
        next_actions.append("Prefer explicit fetch_url over reference fallback for reviewed cases.")
    if reviewed_non_primary_fetches_requiring_upgrade:
        warnings.append(
            f"{len(reviewed_non_primary_fetches_requiring_upgrade)} reviewed cases still rely on mirror or commentary surfaces without an allowed refresh policy."
        )
        next_actions.append("Upgrade fetch_url to first-party public surfaces when durable originals can be confirmed.")
    if enabled_seed_sources_without_filters:
        warnings.append(
            f"{len(enabled_seed_sources_without_filters)} enabled seed sources have no include/exclude filters and may flood the candidate inbox."
        )
        next_actions.append("Add URL or title filters to every enabled seed to keep candidate discovery tight.")
    if not request["run_benchmark_index_after_refresh"]:
        warnings.append("Post-refresh benchmark indexing is disabled, so the reviewed snapshot will not auto-update.")
    if not candidate_cases:
        warnings.append("Candidate inbox is currently empty.")
    if request["auto_add_new_cases"] and not request["discover_new_cases"]:
        warnings.append("auto_add_new_cases is enabled but discover_new_cases is disabled.")
    if duplicate_candidate_case_ids or duplicate_candidate_urls or duplicate_candidate_fingerprints:
        warnings.append("Candidate inbox has duplicate case IDs, URLs, or fingerprints.")
        next_actions.append("Deduplicate candidate inbox before scaling up discovery volume.")
    if not observations_path_consistent:
        warnings.append("Observed artifact paths are inconsistent between request and checked-in libraries.")
        next_actions.append("Align observation_log_path across request, reviewed library, and candidate library.")

    readiness_level = "ready"
    if blockers:
        readiness_level = "blocked"
    elif warnings:
        readiness_level = "warning"

    result = {
        "status": "ok",
        "workflow_kind": "benchmark_readiness_audit",
        "readiness_level": readiness_level,
        "ready_for_daily_refresh": not blockers,
        "files": {
            "reviewed_library_path": str(request["library_path"]),
            "candidate_library_path": str(request["candidate_library_path"]),
            "seeds_path": str(request["seeds_path"]),
            "observations_path": str(request["observations_path"]),
        },
        "request_flags": {
            "refresh_existing_cases": request["refresh_existing_cases"],
            "discover_new_cases": request["discover_new_cases"],
            "auto_add_new_cases": request["auto_add_new_cases"],
            "allow_reference_url_fallback": request["allow_reference_url_fallback"],
            "run_benchmark_index_after_refresh": request["run_benchmark_index_after_refresh"],
        },
        "summary": {
            "reviewed_cases": reviewed_case_count,
            "candidate_cases": len(candidate_cases),
            "enabled_seed_sources": len(enabled_seed_sources),
            "reviewed_cases_missing_fetch_url": len(reviewed_case_fetch_url_gaps),
            "reviewed_fetch_url_coverage_pct": round(
                ((reviewed_case_count - len(reviewed_case_fetch_url_gaps)) / reviewed_case_count * 100.0) if reviewed_case_count else 0.0,
                1,
            ),
            "reviewed_non_primary_fetches": len(reviewed_non_primary_fetches),
            "reviewed_non_primary_fetches_requiring_upgrade": len(reviewed_non_primary_fetches_requiring_upgrade),
            "reviewed_non_primary_fetches_allowed": len(reviewed_non_primary_fetches_allowed),
            "enabled_seed_sources_missing_seed_url": len(enabled_seed_sources_missing_seed_url),
            "enabled_seed_sources_without_filters": len(enabled_seed_sources_without_filters),
            "duplicate_candidate_case_ids": len(duplicate_candidate_case_ids),
            "duplicate_candidate_urls": len(duplicate_candidate_urls),
            "duplicate_candidate_fingerprints": len(duplicate_candidate_fingerprints),
            "observations_path_consistent": observations_path_consistent,
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": unique_keep_order(next_actions),
        "reviewed_case_fetch_url_gaps": reviewed_case_fetch_url_gaps,
        "reviewed_non_primary_fetches": reviewed_non_primary_fetches,
        "reviewed_non_primary_fetches_requiring_upgrade": reviewed_non_primary_fetches_requiring_upgrade,
        "reviewed_non_primary_fetches_allowed": reviewed_non_primary_fetches_allowed,
        "seed_findings": seed_findings,
        "candidate_hygiene": {
            "duplicate_candidate_case_ids": duplicate_candidate_case_ids,
            "duplicate_candidate_urls": duplicate_candidate_urls,
            "duplicate_candidate_fingerprints": duplicate_candidate_fingerprints,
        },
        "curation_boundary": {
            "reviewed_status_leaks": reviewed_status_leaks,
            "candidate_status_leaks": candidate_status_leaks,
        },
    }
    result["report_markdown"] = build_report(result)
    return result
