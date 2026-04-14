#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from china_portal_adapter_contract import (
    APPLY_SUPPORT_VALUES,
    PLATFORM_VALUES,
    STATUS_VALUES,
    TASK_VALUES,
    contract_errors,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_LOCAL_CONFIG_PATH = Path(r"D:\career-ops-local\config\china_portal_adapter.local.json")
DEFAULT_SESSION_MODE = "existing_local_only"
DEFAULT_SOURCE = "china-portal-adapter"
SUPPORTED_LIVE_SCAN_PLATFORMS = {"boss"}
PLATFORM_BASELINES = {
    "boss": {
        "discovery": "ready",
        "apply_support": "manual_only",
        "risk_level": "high",
        "warning": "boss currently has elevated anti-automation risk and should remain manual-only.",
    },
    "liepin": {
        "discovery": "ready",
        "apply_support": "manual_only",
        "risk_level": "medium",
        "warning": "",
    },
    "job51": {
        "discovery": "ready",
        "apply_support": "manual_only",
        "risk_level": "medium",
        "warning": "",
    },
    "zhilian": {
        "discovery": "partial",
        "apply_support": "disabled",
        "risk_level": "high",
        "warning": "zhilian is treated as unstable in the initial adapter posture.",
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


def merge_dicts(base: Any, override: Any) -> dict[str, Any]:
    merged = dict(safe_dict(base))
    for key, value in safe_dict(override).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_string_list(value: Any) -> list[str]:
    values = [value] if isinstance(value, str) else safe_list(value)
    result: list[str] = []
    for item in values:
        text = clean_text(item)
        if text and text not in result:
            result.append(text)
    return result


def resolve_path(path_text: str) -> Path:
    candidate = Path(clean_text(path_text)).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def run_command_capture(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
    }


def load_local_config(path: Path) -> dict[str, Any]:
    if not safe_path_exists(path):
        return {}
    try:
        return safe_dict(load_json(path))
    except Exception:
        return {}


def normalize_platforms(value: Any) -> list[str]:
    requested = [platform.lower() for platform in normalize_string_list(value)]
    valid = [platform for platform in requested if platform in PLATFORM_VALUES]
    return valid or sorted(PLATFORM_VALUES)


def safe_path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except PermissionError:
        return False


def browser_candidates(request: dict[str, Any]) -> list[Path]:
    explicit = [resolve_path(path) for path in request["browser_executable_paths"]]
    if explicit:
        return explicit
    home = Path.home()
    return [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        home / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
        home / "AppData" / "Local" / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]


def browser_profile_roots(request: dict[str, Any]) -> list[Path]:
    explicit = [resolve_path(path) for path in request["browser_profile_paths"]]
    if explicit:
        return explicit
    home = Path.home()
    return [
        home / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
        home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data",
        Path(r"D:\career-ops-local\portal-sessions"),
        REPO_ROOT / ".tmp-x-chrome-profile",
        REPO_ROOT / ".tmp-x-edge-profile",
        REPO_ROOT / ".tmp-x-session",
    ]


def safe_iterdir(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except (PermissionError, FileNotFoundError, NotADirectoryError):
        return []


def probe_profile_root(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    local_state = resolved / "Local State"
    default_dir = resolved / "Default"
    profile_dirs = [item for item in safe_iterdir(resolved) if item.is_dir() and item.name.lower().startswith("profile")]
    cookies_candidates = [
        default_dir / "Cookies",
        default_dir / "Network" / "Cookies",
        *(item / "Cookies" for item in profile_dirs),
        *(item / "Network" / "Cookies" for item in profile_dirs),
    ]
    has_local_state = safe_path_exists(local_state)
    has_default_dir = safe_path_exists(default_dir)
    has_profile_dirs = len(profile_dirs) > 0
    has_cookies = any(safe_path_exists(candidate) for candidate in cookies_candidates)
    usable = has_local_state or has_default_dir or has_profile_dirs or has_cookies
    return {
        "root": str(resolved),
        "has_local_state": has_local_state,
        "has_default_dir": has_default_dir,
        "profile_dirs": [item.name for item in profile_dirs[:5]],
        "has_cookies": has_cookies,
        "usable": usable,
    }


def status_rank(status: str) -> int:
    order = {"error": 0, "partial": 1, "ready": 2}
    return order.get(clean_text(status), 0)


def combine_status(base: str, local: str) -> str:
    return base if status_rank(base) <= status_rank(local) else local


def normalize_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    explicit_config_path = clean_text(raw_request.get("config_path"))
    config_path = resolve_path(explicit_config_path) if explicit_config_path else DEFAULT_LOCAL_CONFIG_PATH
    local_config = load_local_config(config_path)
    salary_filters = merge_dicts(local_config.get("salary_filters"), raw_request.get("salary_filters"))
    notifications = merge_dicts(local_config.get("notifications"), raw_request.get("notifications"))
    live_scan = merge_dicts(local_config.get("live_scan"), raw_request.get("live_scan"))
    task = clean_text(raw_request.get("task")).lower()
    fixture = safe_dict(raw_request.get("fixture"))
    return {
        "task": task,
        "config_path": str(config_path),
        "platforms": normalize_platforms(raw_request.get("platforms") or local_config.get("platforms")),
        "keywords": [keyword.lower() for keyword in normalize_string_list(raw_request.get("keywords"))],
        "cities": normalize_string_list(raw_request.get("cities")),
        "salary_min_monthly_rmb": int(salary_filters.get("minimum_monthly_rmb") or 0),
        "salary_max_monthly_rmb": int(salary_filters.get("maximum_monthly_rmb") or 0),
        "blacklist_companies": normalize_string_list(raw_request.get("blacklist_companies") or local_config.get("blacklist_companies")),
        "blacklist_recruiters": normalize_string_list(raw_request.get("blacklist_recruiters") or local_config.get("blacklist_recruiters")),
        "session_mode": clean_text(raw_request.get("session_mode") or local_config.get("session_mode") or DEFAULT_SESSION_MODE) or DEFAULT_SESSION_MODE,
        "notifications_enabled": to_bool(notifications.get("enabled"), False),
        "fixture_enabled": to_bool(fixture.get("enabled"), False),
        "fixture_source": clean_text(fixture.get("source")),
        "browser_executable_paths": normalize_string_list(raw_request.get("browser_executable_paths") or local_config.get("browser_executable_paths")),
        "browser_profile_paths": normalize_string_list(raw_request.get("browser_profile_paths") or local_config.get("browser_profile_paths")),
        "live_scan_enabled": to_bool(live_scan.get("enabled"), False),
        "live_scan_timeout_ms": int(live_scan.get("timeout_ms") or 15000),
        "live_scan_max_jobs": int(live_scan.get("max_jobs") or 20),
        "live_scan_platforms": safe_dict(live_scan.get("platforms")),
    }


def normalize_job_row(row: dict[str, Any]) -> dict[str, Any]:
    job_card = safe_dict(row.get("job_card"))
    platform_meta = safe_dict(row.get("platform_meta"))
    apply_support = safe_dict(row.get("apply_support"))
    role_title = clean_text(job_card.get("role_title"))
    summary = clean_text(job_card.get("summary"))
    raw_text_excerpt = clean_text(job_card.get("raw_text_excerpt")) or summary
    level = clean_text(job_card.get("level"))
    if not level:
        lowered = role_title.lower()
        if "senior" in lowered:
            level = "senior"
        elif "staff" in lowered:
            level = "staff"
        elif "lead" in lowered:
            level = "lead"
    keywords = normalize_string_list(job_card.get("keywords"))
    if not keywords:
        token_source = f"{role_title} {summary}".lower()
        candidates = re.findall(r"[a-zA-Z][a-zA-Z0-9+/#-]{1,}", token_source)
        stop = {"the", "and", "for", "with", "product", "manager", "role", "team", "build"}
        derived: list[str] = []
        for item in candidates:
            token = clean_text(item).lower()
            if len(token) < 2 or token in stop or token in derived:
                continue
            derived.append(token)
        keywords = derived[:8]
    return {
        "job_card": {
            "job_id": clean_text(job_card.get("job_id")),
            "company": clean_text(job_card.get("company")),
            "role_title": role_title,
            "level": level,
            "location": clean_text(job_card.get("location")),
            "reports_to": clean_text(job_card.get("reports_to")),
            "summary": summary or raw_text_excerpt,
            "responsibilities": normalize_string_list(job_card.get("responsibilities")),
            "must_haves": normalize_string_list(job_card.get("must_haves")),
            "nice_to_have": normalize_string_list(job_card.get("nice_to_have")),
            "keywords": keywords,
            "source": safe_dict(job_card.get("source")),
            "raw_text_excerpt": raw_text_excerpt,
        },
        "platform_meta": {
            "platform": clean_text(platform_meta.get("platform")).lower(),
            "recruiter_type": clean_text(platform_meta.get("recruiter_type")),
            "recruiter_name": clean_text(platform_meta.get("recruiter_name")),
            "salary_text": clean_text(platform_meta.get("salary_text")),
        },
        "apply_support": {
            "available": bool(apply_support.get("available", False)),
            "mode": clean_text(apply_support.get("mode") or "manual_only"),
        },
    }


def parse_salary_range(salary_text: str) -> tuple[int, int] | None:
    text = clean_text(salary_text).lower()
    if not text:
        return None
    match = re.search(r"(\d+)\s*-\s*(\d+)\s*k", text)
    if not match:
        return None
    low = int(match.group(1)) * 1000
    high = int(match.group(2)) * 1000
    return low, high


def matches_keywords(job: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    card = safe_dict(job.get("job_card"))
    haystack = "\n".join(
        [
            clean_text(card.get("role_title")),
            clean_text(card.get("summary")),
            " ".join(normalize_string_list(card.get("keywords"))),
            " ".join(normalize_string_list(card.get("responsibilities"))),
        ]
    ).lower()
    return any(keyword in haystack for keyword in keywords)


def matches_cities(job: dict[str, Any], cities: list[str]) -> bool:
    if not cities:
        return True
    location = clean_text(safe_dict(job.get("job_card")).get("location")).lower()
    return any(city.lower() in location for city in cities)


def matches_salary(job: dict[str, Any], salary_min: int, salary_max: int) -> bool:
    if salary_min <= 0 and salary_max <= 0:
        return True
    salary = parse_salary_range(clean_text(safe_dict(job.get("platform_meta")).get("salary_text")))
    if salary is None:
        return True
    low, high = salary
    if salary_min > 0 and high < salary_min:
        return False
    if salary_max > 0 and low > salary_max:
        return False
    return True


def matches_blacklists(job: dict[str, Any], company_blacklist: list[str], recruiter_blacklist: list[str]) -> bool:
    card = safe_dict(job.get("job_card"))
    meta = safe_dict(job.get("platform_meta"))
    company = clean_text(card.get("company")).lower()
    recruiter = clean_text(meta.get("recruiter_name")).lower()
    if any(item.lower() == company for item in company_blacklist):
        return False
    if recruiter and any(item.lower() == recruiter for item in recruiter_blacklist):
        return False
    return True


def filter_jobs(jobs: list[dict[str, Any]], request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    filtered: list[dict[str, Any]] = []
    warnings: list[str] = []
    for job in jobs:
        platform = clean_text(safe_dict(job.get("platform_meta")).get("platform")).lower()
        if platform not in request["platforms"]:
            continue
        if not matches_keywords(job, request["keywords"]):
            continue
        if not matches_cities(job, request["cities"]):
            continue
        if not matches_salary(job, request["salary_min_monthly_rmb"], request["salary_max_monthly_rmb"]):
            continue
        if not matches_blacklists(job, request["blacklist_companies"], request["blacklist_recruiters"]):
            continue
        filtered.append(job)
    if not filtered and jobs:
        warnings.append("All jobs were filtered out by the current platform, keyword, city, salary, or blacklist rules.")
    return filtered, warnings


def status_for_probe(platform_status: dict[str, Any]) -> str:
    discoveries = [clean_text(safe_dict(item).get("discovery")) for item in platform_status.values()]
    if discoveries and all(item == "ready" for item in discoveries):
        return "ready"
    if any(item in {"ready", "partial"} for item in discoveries):
        return "partial"
    return "error"


def build_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# China Portal Adapter",
        "",
        f"- Task: `{clean_text(result.get('task'))}`",
        f"- Status: `{clean_text(result.get('scan_status'))}`",
        f"- Session mode: `{clean_text(safe_dict(result.get('session_status')).get('mode'))}`",
        "",
        "## Platforms",
    ]
    for platform, payload in safe_dict(result.get("platform_status")).items():
        row = safe_dict(payload)
        lines.append(
            f"- `{platform}`: discovery=`{clean_text(row.get('discovery'))}`, apply=`{clean_text(row.get('apply_support'))}`, risk=`{clean_text(row.get('risk_level'))}`"
        )
    jobs = safe_list(result.get("jobs"))
    lines.extend(["", "## Jobs", f"- Count: `{len(jobs)}`"])
    for job in jobs[:5]:
        card = safe_dict(safe_dict(job).get("job_card"))
        lines.append(f"- `{clean_text(card.get('company'))}` / `{clean_text(card.get('role_title'))}` / `{clean_text(card.get('location'))}`")
    readiness_gate = safe_dict(result.get("readiness_gate"))
    if readiness_gate:
        ready = normalize_string_list(readiness_gate.get("ready_platforms"))
        blocked = normalize_string_list(readiness_gate.get("blocked_platforms"))
        next_steps = normalize_string_list(readiness_gate.get("next_steps"))
        lines.extend(["", "## Readiness Gate"])
        lines.append(f"- Ready platforms: `{', '.join(ready) or 'none'}`")
        lines.append(f"- Blocked platforms: `{', '.join(blocked) or 'none'}`")
        for step in next_steps:
            lines.append(f"- Next: {step}")
    warnings = normalize_string_list(result.get("warnings"))
    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def load_fixture_payload(request: dict[str, Any]) -> dict[str, Any]:
    source = request["fixture_source"]
    if not source:
        raise ValueError("fixture.source is required when fixture mode is enabled")
    payload = safe_dict(load_json(resolve_path(source)))
    payload["jobs"] = [normalize_job_row(job) for job in safe_list(payload.get("jobs"))]
    return payload


def run_local_platform_probe(request: dict[str, Any]) -> dict[str, Any]:
    browsers = [path for path in browser_candidates(request) if safe_path_exists(path)]
    profile_probes = [probe_profile_root(path) for path in browser_profile_roots(request)]
    usable_profile_probes = [item for item in profile_probes if item["usable"]]
    profiles = [item["root"] for item in usable_profile_probes]

    if browsers and profiles:
        local_status = "ready"
    elif browsers:
        local_status = "partial"
    else:
        local_status = "error"

    platform_status: dict[str, Any] = {}
    warnings: list[str] = []
    for platform in request["platforms"]:
        baseline = safe_dict(PLATFORM_BASELINES.get(platform))
        discovery = combine_status(clean_text(baseline.get("discovery") or "ready"), local_status)
        platform_status[platform] = {
            "discovery": discovery,
            "apply_support": clean_text(baseline.get("apply_support") or "manual_only"),
            "risk_level": clean_text(baseline.get("risk_level") or "medium"),
        }
        warning = clean_text(baseline.get("warning"))
        if warning:
            warnings.append(warning)

    if not browsers:
        warnings.append("No local Chrome or Edge executable was detected for China portal probing.")
    if browsers and not profiles:
        warnings.append("Browser executables were found, but no reusable browser profile/session roots were detected.")

    result = {
        "task": "platform_probe",
        "source": DEFAULT_SOURCE,
        "scan_status": status_for_probe(platform_status),
        "session_status": {
            "mode": request["session_mode"],
            "platforms_signed_in": [],
            "stale_platforms": [],
            "browser_executables_detected": [str(path) for path in browsers],
            "browser_profile_roots_detected": profiles,
            "browser_profile_probe_details": profile_probes,
        },
        "platform_status": platform_status,
        "jobs": [],
        "warnings": warnings,
        "generated_at": now_z(),
    }
    return result


def build_readiness_gate(probe_result: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
    platform_status = safe_dict(probe_result.get("platform_status"))
    ready_platforms = [
        platform for platform, payload in platform_status.items()
        if clean_text(safe_dict(payload).get("discovery")) == "ready"
    ]
    blocked_platforms = [
        platform for platform, payload in platform_status.items()
        if clean_text(safe_dict(payload).get("discovery")) != "ready"
    ]
    platform_requests = safe_dict(safe_dict(request).get("live_scan_platforms")) if request else {}
    supported_ready_platforms = [platform for platform in ready_platforms if platform in SUPPORTED_LIVE_SCAN_PLATFORMS]
    runnable_platforms = [
        platform for platform in supported_ready_platforms
        if clean_text(safe_dict(platform_requests.get(platform)).get("url"))
    ]
    missing_live_scan_config = [
        platform for platform in supported_ready_platforms
        if platform not in runnable_platforms
    ]
    unsupported_live_scan_platforms = [
        platform for platform in ready_platforms
        if platform not in SUPPORTED_LIVE_SCAN_PLATFORMS
    ]
    next_steps: list[str] = []
    if runnable_platforms:
        next_steps.append(
            f"Live scan can run now for: {', '.join(runnable_platforms)}. Keep the scan bounded to list pages and manual-only apply posture."
        )
    elif ready_platforms:
        next_steps.append(
            f"Ready platforms detected: {', '.join(ready_platforms)}."
        )
    if missing_live_scan_config:
        config_path = clean_text(safe_dict(request).get("config_path")) if request else clean_text(DEFAULT_LOCAL_CONFIG_PATH)
        next_steps.append(
            f"Add or update live-scan URLs under `{config_path}` for: {', '.join(missing_live_scan_config)}."
        )
    if blocked_platforms:
        next_steps.append(
            f"Blocked or partial platforms still need session work or a more conservative adapter path: {', '.join(blocked_platforms)}."
        )
    if unsupported_live_scan_platforms:
        next_steps.append(
            f"Ready but not yet implemented for live scan: {', '.join(unsupported_live_scan_platforms)}. Only `boss` has a live list-page scanner in v1."
        )
    return {
        "ready_platforms": ready_platforms,
        "blocked_platforms": blocked_platforms,
        "runnable_platforms": runnable_platforms,
        "missing_live_scan_config": missing_live_scan_config,
        "unsupported_live_scan_platforms": unsupported_live_scan_platforms,
        "next_steps": next_steps,
    }


def preferred_browser_path(probe_result: dict[str, Any]) -> str:
    browsers = normalize_string_list(safe_dict(probe_result.get("session_status")).get("browser_executables_detected"))
    return browsers[0] if browsers else ""


def preferred_profile_root(probe_result: dict[str, Any]) -> str:
    profiles = normalize_string_list(safe_dict(probe_result.get("session_status")).get("browser_profile_roots_detected"))
    prioritized = sorted(
        profiles,
        key=lambda item: (
            0 if ".tmp-x-" in item or "portal-sessions" in item.lower() else 1,
            item.lower(),
        ),
    )
    return prioritized[0] if prioritized else ""


def live_scan_plan(request: dict[str, Any], probe_result: dict[str, Any]) -> dict[str, Any]:
    readiness = build_readiness_gate(probe_result, request)
    return {
        "ready_platforms": normalize_string_list(readiness.get("ready_platforms")),
        "runnable_platforms": normalize_string_list(readiness.get("runnable_platforms")),
        "missing_live_scan_config": normalize_string_list(readiness.get("missing_live_scan_config")),
        "unsupported_live_scan_platforms": normalize_string_list(readiness.get("unsupported_live_scan_platforms")),
        "browser_executable": preferred_browser_path(probe_result),
        "browser_profile_root": preferred_profile_root(probe_result),
        "timeout_ms": request["live_scan_timeout_ms"],
        "max_jobs": request["live_scan_max_jobs"],
    }


def normalize_live_scan_jobs(platform: str, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for job in jobs:
        row = normalize_job_row(job)
        meta = safe_dict(row.get("platform_meta"))
        meta["platform"] = platform
        row["platform_meta"] = meta
        normalized.append(row)
    return normalized


def base_result(task: str, request: dict[str, Any]) -> dict[str, Any]:
    platform_status = {
        platform: {
            "discovery": "skipped",
            "apply_support": "disabled",
            "risk_level": "medium",
        }
        for platform in request["platforms"]
    }
    return {
        "task": task,
        "source": DEFAULT_SOURCE,
        "scan_status": "ready",
        "session_status": {
            "mode": request["session_mode"],
            "platforms_signed_in": [],
            "stale_platforms": [],
        },
        "platform_status": platform_status,
        "jobs": [],
        "warnings": [],
        "generated_at": now_z(),
    }


def default_live_scan_runner(request: dict[str, Any], probe_result: dict[str, Any]) -> dict[str, Any]:
    plan = live_scan_plan(request, probe_result)
    browser_executable = clean_text(plan.get("browser_executable"))
    user_data_dir = clean_text(plan.get("browser_profile_root"))
    helper_script = REPO_ROOT / "china-portal-adapter" / "skills" / "china-portal-adapter" / "scripts" / "boss_live_scan_with_local_browser.mjs"
    upstream_root = Path(r"D:\career-ops-upstream")
    jobs_by_platform: dict[str, Any] = {}
    warnings: list[str] = []

    if not browser_executable:
        raise RuntimeError("No browser executable is available for live scan.")
    if not user_data_dir:
        raise RuntimeError("No reusable browser profile root is available for live scan.")

    for platform in normalize_string_list(plan.get("runnable_platforms")):
        if platform != "boss":
            warnings.append(f"Live scan helper is not implemented for platform `{platform}` yet.")
            continue
        platform_request = safe_dict(safe_dict(request.get("live_scan_platforms")).get(platform))
        scan_url = clean_text(platform_request.get("url"))
        selectors = safe_dict(platform_request.get("selectors"))
        if not scan_url or clean_text(selectors.get("card")) == "":
            warnings.append(f"Live scan for `{platform}` is missing url or selectors.card.")
            continue
        result = run_command_capture(
            [
                "node",
                str(helper_script),
                "--upstream-root",
                str(upstream_root),
                "--browser-executable",
                browser_executable,
                "--user-data-dir",
                user_data_dir,
                "--platform",
                platform,
                "--scan-url",
                scan_url,
                "--timeout-ms",
                str(int(request.get("live_scan_timeout_ms") or 15000)),
                "--max-jobs",
                str(int(request.get("live_scan_max_jobs") or 20)),
                "--selectors-json",
                json.dumps(selectors, ensure_ascii=False),
            ],
            cwd=REPO_ROOT,
        )
        if not result["ok"]:
            warnings.append(f"Live scan helper failed for `{platform}`: {clean_text(result['stderr']) or clean_text(result['stdout'])}")
            continue
        payload = safe_dict(json.loads(result["stdout"]))
        jobs_by_platform[platform] = safe_list(payload.get("jobs"))
        warnings.extend(normalize_string_list(payload.get("warnings")))

    return {
        "jobs_by_platform": jobs_by_platform,
        "warnings": warnings,
    }


def error_result(task: str, request: dict[str, Any], message: str) -> dict[str, Any]:
    result = base_result(task or "scan_jobs", request)
    result["scan_status"] = "error"
    result["warnings"] = [clean_text(message)]
    result["report_markdown"] = build_markdown_report(result)
    return result


def live_scan_skip_warning(request: dict[str, Any], plan: dict[str, Any]) -> str:
    if not request["live_scan_enabled"]:
        return "Live scan remains disabled in the current request or local config; readiness gate returned instead of browser automation."
    if plan["missing_live_scan_config"]:
        return (
            "Live scan is enabled, but at least one ready platform is missing live-scan URL/config. "
            "Update the local config and retry."
        )
    if plan["unsupported_live_scan_platforms"]:
        return (
            "Live scan is enabled, but the remaining ready platforms do not have a bounded live scanner yet."
        )
    return "Live scan was not attempted because no ready platform satisfied the current scanner and config requirements."


def run_china_portal_adapter(raw_request: dict[str, Any], *, live_scan_runner: Any = None) -> dict[str, Any]:
    request = normalize_request(raw_request)
    if request["task"] not in TASK_VALUES:
        return error_result(request["task"], request, "task must be platform_probe or scan_jobs")

    if not request["fixture_enabled"] and request["task"] == "platform_probe":
        result = run_local_platform_probe(request)
        errors = contract_errors(result)
        if errors:
            result["scan_status"] = "error"
            result["warnings"].extend(errors)
        result["report_markdown"] = build_markdown_report(result)
        return result

    if not request["fixture_enabled"] and request["task"] == "scan_jobs":
        probe_result = run_local_platform_probe(request)
        plan = live_scan_plan(request, probe_result)
        if request["live_scan_enabled"] and plan["runnable_platforms"]:
            runner = live_scan_runner or default_live_scan_runner
            try:
                runner_payload = safe_dict(runner(request, probe_result))
                jobs = []
                for platform, payload in safe_dict(runner_payload.get("jobs_by_platform")).items():
                    jobs.extend(normalize_live_scan_jobs(platform, safe_list(payload)))
                jobs, filter_warnings = filter_jobs(jobs, request)
                result = {
                    "task": "scan_jobs",
                    "source": DEFAULT_SOURCE,
                    "scan_status": "ready" if jobs else "partial",
                    "session_status": safe_dict(probe_result.get("session_status")),
                    "platform_status": safe_dict(probe_result.get("platform_status")),
                    "jobs": jobs,
                    "readiness_gate": {
                        **build_readiness_gate(probe_result, request),
                        "next_steps": [
                            f"Live scan attempted for: {', '.join(plan['runnable_platforms'])}.",
                            "Review normalized jobs before sending them into shortlist or tailor flows.",
                        ],
                    },
                    "warnings": [
                        *normalize_string_list(probe_result.get("warnings")),
                        *normalize_string_list(runner_payload.get("warnings")),
                        *filter_warnings,
                    ],
                    "generated_at": now_z(),
                }
                errors = contract_errors(result)
                if errors:
                    result["scan_status"] = "error"
                    result["warnings"].extend(errors)
                result["report_markdown"] = build_markdown_report(result)
                return result
            except Exception as exc:
                result = {
                    "task": "scan_jobs",
                    "source": DEFAULT_SOURCE,
                    "scan_status": "error",
                    "session_status": safe_dict(probe_result.get("session_status")),
                    "platform_status": safe_dict(probe_result.get("platform_status")),
                    "jobs": [],
                    "readiness_gate": {
                        **build_readiness_gate(probe_result, request),
                    },
                    "warnings": [
                        *normalize_string_list(probe_result.get("warnings")),
                        f"Live scan attempt failed: {clean_text(exc)}",
                    ],
                    "generated_at": now_z(),
                }
                result["report_markdown"] = build_markdown_report(result)
                return result
        result = {
            "task": "scan_jobs",
            "source": DEFAULT_SOURCE,
            "scan_status": "skipped",
            "session_status": safe_dict(probe_result.get("session_status")),
            "platform_status": safe_dict(probe_result.get("platform_status")),
            "jobs": [],
            "readiness_gate": {
                **build_readiness_gate(probe_result, request),
            },
            "warnings": [
                *normalize_string_list(probe_result.get("warnings")),
                live_scan_skip_warning(request, plan),
            ],
            "generated_at": now_z(),
        }
        errors = contract_errors(result)
        if errors:
            result["scan_status"] = "error"
            result["warnings"].extend(errors)
        result["report_markdown"] = build_markdown_report(result)
        return result

    try:
        fixture = load_fixture_payload(request)
    except Exception as exc:
        return error_result(request["task"], request, str(exc))

    result = base_result(request["task"], request)
    result["session_status"] = safe_dict(fixture.get("session_status")) or result["session_status"]
    result["platform_status"] = safe_dict(fixture.get("platform_status")) or result["platform_status"]
    result["warnings"] = normalize_string_list(fixture.get("warnings"))

    if request["task"] == "platform_probe":
        result["scan_status"] = status_for_probe(result["platform_status"])
        result["jobs"] = []
    else:
        jobs, filter_warnings = filter_jobs(safe_list(fixture.get("jobs")), request)
        result["jobs"] = jobs
        result["warnings"].extend(filter_warnings)
        result["scan_status"] = "ready" if jobs else "partial" if safe_list(fixture.get("jobs")) else "error"

    errors = contract_errors(result)
    if errors:
        result["scan_status"] = "error"
        result["warnings"].extend(errors)
    result["report_markdown"] = build_markdown_report(result)
    return result
