#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment-dependent optional dependency
    yaml = None

from news_index_runtime import load_json, write_json


SUPPORTED_CHANNELS = {
    "web_jina": "web_jina",
    "web": "web_jina",
    "github": "github",
    "youtube": "youtube",
    "rss": "rss",
    "x": "x_twitter",
    "twitter": "x_twitter",
    "x_twitter": "x_twitter",
    "wechat": "wechat",
    "reddit": "reddit",
    "bilibili": "bilibili",
    "douyin": "douyin",
    "xiaohongshu": "xiaohongshu",
    "linkedin": "linkedin",
}
ALLOWED_CHANNEL_STATUSES = {
    "ok",
    "blocked",
    "unchecked",
    "missing_credentials",
    "missing_proxy",
    "missing_toolchain",
    "missing_mcp_service",
    "missing_login",
}
CORE_CHANNELS = ("web_jina", "github", "rss")
DEFAULT_REQUIRED_BINARIES = ("agent-reach", "gh", "yt-dlp", "node", "npm", "mcporter")
DEFAULT_CHANNEL_ORDER = (
    "web_jina",
    "github",
    "youtube",
    "rss",
    "x_twitter",
    "wechat",
    "reddit",
    "bilibili",
    "douyin",
    "xiaohongshu",
    "linkedin",
)
DEFAULT_PROBE_URLS = {
    "web_jina": "https://r.jina.ai/http://example.com",
    "github": "https://api.github.com/search/repositories?q=agent+reach&per_page=1",
    "rss": "https://feeds.bbci.co.uk/news/world/rss.xml",
}
DEFAULT_PROBE_QUERY = "agent reach"


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def coerce_yaml_scalar(value: str) -> Any:
    text = clean_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def load_yaml_mapping(text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            loaded = yaml.safe_load(text) or {}
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            return loaded
    result: dict[str, Any] = {}
    current_list_key = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            if current_list_key and stripped.startswith("- "):
                existing = result.get(current_list_key)
                if isinstance(existing, list):
                    existing.append(coerce_yaml_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            current_list_key = ""
            continue
        key, value = stripped.split(":", 1)
        normalized_key = clean_text(key)
        normalized_value = value.strip()
        if not normalized_key:
            current_list_key = ""
            continue
        if not normalized_value:
            result[normalized_key] = []
            current_list_key = normalized_key
            continue
        result[normalized_key] = coerce_yaml_scalar(normalized_value)
        current_list_key = ""
    return result


def preferred_user_root() -> Path:
    return Path("D:/Users") / Path.home().name


def default_vendor_root() -> Path:
    return preferred_user_root() / ".codex" / "vendor"


def default_install_root() -> Path:
    return default_vendor_root() / "agent-reach"


def default_pseudo_home() -> Path:
    return default_vendor_root() / "agent-reach-home"


def load_agent_reach_config(pseudo_home: Path) -> dict[str, Any]:
    config_path = pseudo_home / ".agent-reach" / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        return load_yaml_mapping(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def has_twitter_credentials(request: dict[str, Any]) -> bool:
    config = safe_dict(request.get("agent_reach_config"))
    if clean_text(config.get("twitter_auth_token")) and clean_text(config.get("twitter_ct0")):
        return True
    pseudo_home = request.get("pseudo_home")
    if not isinstance(pseudo_home, Path):
        return False
    bird_env_path = pseudo_home / ".config" / "bird" / "credentials.env"
    if not bird_env_path.exists():
        return False
    try:
        bird_env_text = bird_env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "AUTH_TOKEN=" in bird_env_text and "CT0=" in bird_env_text


def candidate_python_binaries() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("AGENT_REACH_PYTHON_BINARY", "AGENT_REACH_FULL_PYTHON", "CODEX_LOCAL_PYTHON"):
        env_value = clean_text(os.environ.get(env_name))
        if env_value:
            candidates.append(Path(env_value).expanduser())
    candidates.append(default_vendor_root() / "python312-full" / "python.exe")
    accio_root = Path.home() / "AppData" / "Roaming" / "Accio" / "pre-install"
    try:
        if accio_root.exists():
            accio_candidates = sorted(
                accio_root.glob("*/python/python.exe"),
                key=lambda path: path.stat().st_mtime if path.exists() else 0,
                reverse=True,
            )
            candidates.extend(accio_candidates)
    except OSError:
        pass
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = clean_text(candidate)
        if text and text not in seen:
            seen.add(text)
            unique.append(candidate)
    return unique


def default_python_binary() -> Path:
    candidates = candidate_python_binaries()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def state_root(install_root: Path) -> Path:
    return install_root / ".agent-reach"


def version_lock_path(install_root: Path) -> Path:
    return state_root(install_root) / "version.lock"


def doctor_report_path(install_root: Path) -> Path:
    return state_root(install_root) / "doctor-report.json"


def normalize_path(value: Any, default: Path) -> Path:
    text = clean_text(value)
    return Path(text).expanduser().resolve() if text else default.resolve()


def normalize_channel_name(value: Any) -> str:
    normalized = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    return SUPPORTED_CHANNELS.get(normalized, normalized)


def binary_candidates(name: str, install_root: Path) -> list[Path]:
    if name == "agent-reach":
        return [
            install_root / ".venv" / "Scripts" / "agent-reach.exe",
            install_root / ".venv" / "Scripts" / "agent-reach",
        ]
    if name == "npm":
        return [Path("npm.cmd"), Path("npm")]
    if name == "gh":
        return [default_vendor_root() / "gh" / "bin" / "gh.exe", Path("gh")]
    if name == "yt-dlp":
        return [default_vendor_root() / "yt-dlp" / "yt-dlp.exe", Path("yt-dlp")]
    if name == "mcporter":
        return [
            default_vendor_root() / "mcporter" / "mcporter.exe",
            default_vendor_root() / "mcporter" / "mcporter.cmd",
            Path("mcporter"),
        ]
    if name == "bird":
        return [
            default_vendor_root() / "bird" / "bird.exe",
            default_vendor_root() / "bird" / "bird.cmd",
            Path("bird"),
        ]
    if name == "xreach":
        return [default_vendor_root() / "xreach" / "xreach.exe", Path("xreach")]
    return [Path(name)]


def inspect_binary(name: str, install_root: Path) -> dict[str, Any]:
    resolved = ""
    explicit_candidates = binary_candidates(name, install_root)
    for candidate in explicit_candidates:
        if candidate.is_absolute() and candidate.exists():
            resolved = str(candidate)
            break
    if not resolved:
        for candidate in explicit_candidates:
            lookup = shutil.which(str(candidate))
            if lookup:
                resolved = lookup
                break

    entry = {
        "name": name,
        "status": "ok" if resolved else "missing",
        "path": resolved,
        "version": "",
        "error": "",
    }
    if not resolved:
        return entry

    version_args = ["--version"]
    if name == "agent-reach":
        version_args = ["doctor", "--help"]
    try:
        completed = subprocess.run(
            [resolved, *version_args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        version_text = clean_text(completed.stdout or completed.stderr)
        entry["version"] = version_text.splitlines()[0] if version_text else ""
    except (OSError, subprocess.SubprocessError) as exc:
        entry["error"] = clean_text(exc)
    return entry


def inspect_python_binary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "missing", "version": "", "supports_venv": False, "error": ""}
    supports_venv = False
    version = ""
    error = ""
    try:
        version_completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        version = clean_text(version_completed.stdout or version_completed.stderr)
    except Exception as exc:  # noqa: BLE001
        version = ""
        error = clean_text(exc)
    try:
        probe = subprocess.run(
            [str(path), "-m", "venv", "--help"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        supports_venv = probe.returncode == 0
    except Exception as exc:  # noqa: BLE001
        supports_venv = False
        if not error:
            error = clean_text(exc)
    return {
        "path": str(path),
        "status": "ok" if path.exists() else "missing",
        "version": version.splitlines()[0] if version else "",
        "supports_venv": supports_venv,
        "error": error,
    }


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}


def infer_x_backend(version_lock: dict[str, Any], doctor_payload: dict[str, Any], doctor_text: str) -> str:
    explicit = clean_text(version_lock.get("x_backend"))
    if explicit:
        return explicit
    for key in ("x_backend", "twitter_backend"):
        value = clean_text(doctor_payload.get(key))
        if value:
            return value
    lowered = doctor_text.lower()
    if "xreach" in lowered:
        return "xreach"
    if "bird" in lowered:
        return "bird"
    return ""


def inspect_partial_state(install_root: Path, pseudo_home: Path, binary_entry: dict[str, Any], version_lock: dict[str, Any]) -> dict[str, Any]:
    signals: list[str] = []
    repo_root = install_root / "repo"
    venv_root = install_root / ".venv"
    if pseudo_home.exists() and not install_root.exists():
        signals.append("pseudo_home_without_install_root")
    if install_root.exists() and not binary_entry.get("path"):
        signals.append("install_root_without_agent_reach_binary")
    if repo_root.exists() and not venv_root.exists():
        signals.append("repo_present_without_venv")
    if venv_root.exists() and not version_lock:
        signals.append("venv_present_without_version_lock")
    return {
        "is_partial": bool(signals),
        "signals": signals,
    }


def probe_url(url: str, timeout_seconds: int) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-AgentReachCheck/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            if 200 <= getattr(response, "status", 200) < 400:
                return "ok", ""
            return "blocked", f"http_{getattr(response, 'status', 'unknown')}"
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return "blocked", f"http_{exc.code}"
        return "blocked", f"http_{exc.code}"
    except urllib.error.URLError as exc:
        return "blocked", clean_text(exc.reason or exc)
    except OSError as exc:
        return "blocked", clean_text(exc)


def probe_command(command: list[str], timeout_seconds: int) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return "missing_toolchain", f"{command[0]} not installed"
    except subprocess.TimeoutExpired:
        return "blocked", f"timeout after {timeout_seconds}s"
    except OSError as exc:
        return "blocked", clean_text(exc)
    if completed.returncode == 0:
        return "ok", ""
    return "blocked", clean_text(completed.stderr or completed.stdout) or f"command exited {completed.returncode}"


def default_probe_command(channel: str, request: dict[str, Any], binary_map: dict[str, dict[str, Any]]) -> list[str] | None:
    query = clean_text(request.get("probe_query")) or DEFAULT_PROBE_QUERY
    if channel == "youtube":
        yt_dlp_path = clean_text(binary_map.get("yt-dlp", {}).get("path")) or "yt-dlp"
        command = [yt_dlp_path]
        youtube_cookies_from = clean_text(request.get("agent_reach_config", {}).get("youtube_cookies_from"))
        if youtube_cookies_from:
            command.extend(["--cookies-from-browser", youtube_cookies_from])
        command.extend(["--flat-playlist", "--dump-single-json", f"ytsearch1:{query}"])
        return command
    if channel == "x_twitter":
        backend_name = clean_text(request.get("x_backend_name"))
        backend_path = clean_text(binary_map.get(backend_name, {}).get("path"))
        if backend_name and backend_path:
            if backend_name == "bird":
                return [backend_path, "check"]
            return [backend_path, "--help"]
    return None


def probe_channel_live(
    channel: str,
    request: dict[str, Any],
    binary_map: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    if channel in request["channel_probe_urls"]:
        return probe_url(clean_text(request["channel_probe_urls"][channel]), request["timeout_seconds"])
    if channel in {"web_jina", "github", "rss"}:
        return probe_url(DEFAULT_PROBE_URLS[channel], request["timeout_seconds"])
    if channel in request["channel_probe_commands"]:
        command = request["channel_probe_commands"][channel]
        return probe_command(command if isinstance(command, list) else [str(command)], request["timeout_seconds"])
    command = default_probe_command(channel, request, binary_map)
    if command:
        return probe_command(command, request["timeout_seconds"])
    return "unchecked", ""


def normalize_probe_status(status: str) -> str:
    normalized = clean_text(status).lower().replace("-", "_")
    return normalized if normalized in ALLOWED_CHANNEL_STATUSES else "blocked"


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    install_root = normalize_path(raw_payload.get("install_root"), default_install_root())
    pseudo_home = normalize_path(raw_payload.get("pseudo_home"), default_pseudo_home())
    python_binary = normalize_path(raw_payload.get("python_binary"), default_python_binary())
    requested_channels = [
        normalize_channel_name(name)
        for name in (raw_payload.get("channels") or list(DEFAULT_CHANNEL_ORDER))
        if normalize_channel_name(name) in DEFAULT_CHANNEL_ORDER
    ]
    if not requested_channels:
        requested_channels = list(DEFAULT_CHANNEL_ORDER)
    required_binaries = [
        clean_text(name)
        for name in (raw_payload.get("required_binaries") or list(DEFAULT_REQUIRED_BINARIES))
        if clean_text(name)
    ]
    return {
        "install_root": install_root,
        "pseudo_home": pseudo_home,
        "python_binary": python_binary,
        "agent_reach_config": load_agent_reach_config(pseudo_home),
        "required_binaries": required_binaries,
        "channels": requested_channels,
        "channel_probes": safe_dict(raw_payload.get("channel_probes")),
        "channel_probe_urls": safe_dict(raw_payload.get("channel_probe_urls")),
        "channel_probe_commands": {
            normalize_channel_name(key): value
            for key, value in safe_dict(raw_payload.get("channel_probe_commands")).items()
            if normalize_channel_name(key)
        },
        "probe_live_channels": bool(raw_payload.get("probe_live_channels", True)),
        "probe_query": clean_text(raw_payload.get("probe_query")) or DEFAULT_PROBE_QUERY,
        "timeout_seconds": max(1, int(raw_payload.get("timeout_seconds", 8) or 8)),
    }


def inspect_channels(
    request: dict[str, Any],
    binary_map: dict[str, dict[str, Any]],
    version_lock: dict[str, Any],
    doctor_payload: dict[str, Any],
    doctor_text: str,
    *,
    allow_live_probes: bool,
) -> tuple[dict[str, str], list[dict[str, str]], list[str]]:
    statuses: dict[str, str] = {channel: "unchecked" for channel in DEFAULT_CHANNEL_ORDER}
    failures: list[dict[str, str]] = []
    credential_gaps: list[str] = []

    explicit_probes = request["channel_probes"]
    x_backend_name = infer_x_backend(version_lock, doctor_payload, doctor_text)
    request["x_backend_name"] = x_backend_name

    for channel in request["channels"]:
        if channel in explicit_probes:
            probe = safe_dict(explicit_probes.get(channel))
            status = normalize_probe_status(probe.get("status"))
            reason = clean_text(probe.get("reason"))
            statuses[channel] = status
            if status not in {"ok", "unchecked"}:
                failures.append({"channel": channel, "reason": reason or status})
            gap = clean_text(probe.get("credential_gap"))
            if gap:
                credential_gaps.append(f"{channel}: {gap}")
            continue

        if channel == "github":
            if binary_map["gh"]["status"] != "ok":
                statuses[channel] = "missing_toolchain"
                failures.append({"channel": channel, "reason": "gh not installed"})
                continue
            if allow_live_probes:
                status, reason = probe_channel_live(channel, request, binary_map)
                statuses[channel] = normalize_probe_status(status)
                if statuses[channel] != "ok":
                    failures.append({"channel": channel, "reason": reason or statuses[channel]})
            else:
                statuses[channel] = "unchecked"
            continue
        if channel == "youtube":
            if binary_map["yt-dlp"]["status"] != "ok":
                statuses[channel] = "missing_toolchain"
                failures.append({"channel": channel, "reason": "yt-dlp not installed"})
                continue
            if allow_live_probes:
                status, reason = probe_channel_live(channel, request, binary_map)
                statuses[channel] = normalize_probe_status(status)
                if statuses[channel] != "ok":
                    failures.append({"channel": channel, "reason": reason or statuses[channel]})
            else:
                statuses[channel] = "unchecked"
            continue
        if channel == "rss":
            if allow_live_probes:
                status, reason = probe_channel_live(channel, request, binary_map)
                statuses[channel] = normalize_probe_status(status)
                if statuses[channel] != "ok":
                    failures.append({"channel": channel, "reason": reason or statuses[channel]})
            else:
                statuses[channel] = "unchecked"
            continue
        if channel == "web_jina":
            if allow_live_probes:
                status, reason = probe_channel_live(channel, request, binary_map)
                statuses[channel] = normalize_probe_status(status)
                if statuses[channel] != "ok":
                    failures.append({"channel": channel, "reason": reason or statuses[channel]})
            else:
                statuses[channel] = "unchecked"
            continue
        if channel == "x_twitter":
            if x_backend_name and clean_text(binary_map.get(x_backend_name, {}).get("status")) == "ok":
                if not has_twitter_credentials(request):
                    statuses[channel] = "missing_credentials"
                    failures.append({"channel": channel, "reason": "twitter credentials not configured"})
                    credential_gaps.append("x_twitter: missing twitter_auth_token/ct0 credentials")
                elif allow_live_probes:
                    status, reason = probe_channel_live(channel, request, binary_map)
                    statuses[channel] = normalize_probe_status(status)
                    if statuses[channel] != "ok":
                        failures.append({"channel": channel, "reason": reason or statuses[channel]})
                else:
                    statuses[channel] = "unchecked"
            elif x_backend_name:
                statuses[channel] = "missing_toolchain"
                failures.append({"channel": channel, "reason": f"{x_backend_name} not installed"})
            else:
                statuses[channel] = "missing_credentials"
                failures.append({"channel": channel, "reason": "x backend not resolved from doctor/version lock"})
                credential_gaps.append("x_twitter: missing x backend resolution or credentials")
            continue
        if channel in {"wechat", "xiaohongshu", "linkedin"}:
            statuses[channel] = "missing_login"
            failures.append({"channel": channel, "reason": "interactive login state not configured"})
            credential_gaps.append(f"{channel}: login state not configured")
            continue
        if channel in {"reddit", "bilibili"}:
            statuses[channel] = "missing_proxy"
            failures.append({"channel": channel, "reason": "proxy or session requirements not configured"})
            credential_gaps.append(f"{channel}: proxy or session requirements not configured")
            continue
        if channel == "douyin":
            statuses[channel] = "missing_mcp_service"
            failures.append({"channel": channel, "reason": "required MCP/browser service not configured"})
            credential_gaps.append("douyin: required MCP/browser service not configured")
            continue

    return statuses, failures, sorted(set(credential_gaps))


def build_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Agent Reach Deploy Check",
        "",
        f"- Status: {result.get('status', 'unknown')}",
        f"- Install root: {result.get('install_root', '')}",
        f"- Pseudo-home: {result.get('pseudo_home', '')}",
        f"- Python binary: {result.get('python_binary', '')}",
        "",
        "## Binaries",
    ]
    for name, status in result.get("binaries", {}).items():
        lines.append(f"- {name}: {status}")
    lines.extend(["", "## Channels"])
    for name, status in result.get("channels", {}).items():
        lines.append(f"- {name}: {status}")
    if result.get("credential_gaps"):
        lines.extend(["", "## Credential Gaps"])
        lines.extend([f"- {item}" for item in result.get("credential_gaps", [])])
    if result.get("partial_state", {}).get("signals"):
        lines.extend(["", "## Partial Install Signals"])
        lines.extend([f"- {item}" for item in result["partial_state"]["signals"]])
    if result.get("notes"):
        lines.extend(["", "## Notes"])
        lines.extend([f"- {item}" for item in result.get("notes", [])])
    return "\n".join(lines).strip() + "\n"


def run_agent_reach_deploy_check(raw_payload: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw_payload)
    install_root = request["install_root"]
    pseudo_home = request["pseudo_home"]
    python_binary = request["python_binary"]
    doctor_path = doctor_report_path(install_root)
    version_path = version_lock_path(install_root)

    binary_details = {
        name: inspect_binary(name, install_root)
        for name in sorted(set(request["required_binaries"] + ["bird", "xreach"]))
    }
    binaries = {
        name: ("ok" if binary_details.get(name, {}).get("status") == "ok" else "missing")
        for name in request["required_binaries"]
    }
    python_status = inspect_python_binary(python_binary)
    doctor_payload = load_optional_json(doctor_path)
    doctor_text = ""
    if doctor_path.exists():
        try:
            doctor_text = doctor_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            doctor_text = ""
    version_lock = load_optional_json(version_path)
    partial_state = inspect_partial_state(install_root, pseudo_home, binary_details.get("agent-reach", {}), version_lock)
    allow_live_probes = bool(request["probe_live_channels"] and install_root.exists() and not partial_state["is_partial"])
    channels, channel_failures, credential_gaps = inspect_channels(
        request,
        binary_details,
        version_lock,
        doctor_payload,
        doctor_text,
        allow_live_probes=allow_live_probes,
    )

    notes: list[str] = []
    if not install_root.exists():
        notes.append("Install root is missing. Separate Agent Reach deployment has not been created yet.")
        status = "missing_install"
    elif partial_state["is_partial"]:
        status = "partial"
        notes.append("Partial install signals were detected. Run scripts/agent-reach/clean-partial.ps1 before retrying install.")
    else:
        status = "ready"
    if python_status["status"] != "ok":
        notes.append("Expected full Python runtime is missing.")
        status = "partial" if status != "missing_install" else status
    elif not python_status["supports_venv"]:
        notes.append("Configured Python exists but does not support venv creation.")
        status = "partial" if status != "missing_install" else status
    if not version_lock:
        notes.append("Version lock file is missing. Upstream commit and x backend are not pinned yet.")
    if not doctor_path.exists():
        notes.append("Doctor report is missing. Channel readiness can only be inferred, not confirmed.")
    if any(channels[channel] != "ok" for channel in CORE_CHANNELS):
        notes.append("Core discovery channels are not all actively verified yet.")
    if channels.get("youtube") == "ok" and not clean_text(request["agent_reach_config"].get("youtube_cookies_from")):
        notes.append("YouTube probe only verified flat search discovery. Detail metadata or subtitles may still require cookies.")

    result = {
        "status": status,
        "install_root": str(install_root),
        "pseudo_home": str(pseudo_home),
        "python_binary": str(python_binary),
        "python_status": python_status,
        "binaries": binaries,
        "binary_details": binary_details,
        "channels": channels,
        "channels_failed": channel_failures,
        "credential_gaps": credential_gaps,
        "last_doctor_report": str(doctor_path) if doctor_path.exists() else None,
        "version_lock_path": str(version_path) if version_path.exists() else None,
        "version_lock": version_lock,
        "partial_state": partial_state,
        "core_channels_ready": all(channels.get(channel) == "ok" for channel in CORE_CHANNELS),
        "notes": notes,
    }
    result["report_markdown"] = build_report_markdown(result)
    return result


__all__ = [
    "CORE_CHANNELS",
    "build_report_markdown",
    "default_install_root",
    "default_pseudo_home",
    "default_python_binary",
    "doctor_report_path",
    "run_agent_reach_deploy_check",
    "state_root",
    "version_lock_path",
]
