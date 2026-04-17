#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
for raw_path in reversed((os.environ.get("TRADINGAGENTS_PYTHONPATH") or "").split(os.pathsep)):
    candidate = raw_path.strip()
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from tradingagents_package_support import clean_text, package_origin, probe_runtime_imports, resolve_package_version
from tradingagents_provider_config import PROVIDER_ENV_VARS, resolve_provider_runtime


SpecFinder = Callable[[str], Any]
VersionLookup = Callable[[str], str]
ImportCheck = Callable[[], tuple[bool, str]]
EndpointCheck = Callable[[str, str | None], tuple[bool, str, str | None]]
DEFAULT_PROVIDER_ENDPOINTS = {
    "ollama": "http://localhost:11434/v1",
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def isoformat_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_bool(value: Any) -> bool:
    text = clean_text(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def normalize_llm_provider(value: Any) -> str:
    text = clean_text(value).lower()
    return text if text in PROVIDER_ENV_VARS else "openai"


def provider_key_present(provider: str, env_map: dict[str, str]) -> bool:
    env_var = PROVIDER_ENV_VARS.get(provider)
    if not env_var:
        return True
    return bool(clean_text(env_map.get(env_var)))


def available_provider_keys(env_map: dict[str, str]) -> dict[str, bool]:
    return {
        provider: provider_key_present(provider, env_map)
        for provider in PROVIDER_ENV_VARS
    }


def provider_health_url(provider: str, backend_url: str | None) -> str | None:
    if provider != "ollama":
        return None
    base_url = clean_text(backend_url) or DEFAULT_PROVIDER_ENDPOINTS["ollama"]
    if base_url.endswith("/v1"):
        return f"{base_url[:-3]}/api/tags"
    return f"{base_url.rstrip('/')}/api/tags"


def probe_provider_endpoint(provider: str, backend_url: str | None) -> tuple[bool, str, str | None]:
    health_url = provider_health_url(provider, backend_url)
    if not health_url:
        return True, "", None
    try:
        with urlopen(health_url, timeout=3) as response:
            status = getattr(response, "status", 200)
        return 200 <= int(status) < 400, "", health_url
    except URLError as exc:
        return False, clean_text(str(exc.reason or exc)), health_url
    except Exception as exc:  # pragma: no cover
        message = clean_text(str(exc))
        return False, message or exc.__class__.__name__, health_url


def collect_operator_probe(
    *,
    env: dict[str, str] | None = None,
    spec_finder: SpecFinder | None = None,
    version_lookup: VersionLookup | None = None,
    import_check: ImportCheck | None = None,
    llm_provider: str | None = None,
    backend_url: str | None = None,
    endpoint_check: EndpointCheck | None = None,
    python_executable: str | None = None,
    python_version: str | None = None,
) -> dict[str, Any]:
    env_map = dict(os.environ) if env is None else dict(env)
    probe_spec = spec_finder or util.find_spec
    lookup_version = version_lookup

    package_spec = probe_spec("tradingagents")
    package_installed = package_spec is not None
    package_version = ""
    package_runtime_importable = False
    package_runtime_import_error = ""
    if package_installed:
        package_version = resolve_package_version("tradingagents", spec=package_spec, version_lookup=lookup_version)
        package_runtime_importable, package_runtime_import_error = (
            import_check() if import_check is not None else probe_runtime_imports()
        )

    requested_llm_provider = clean_text(llm_provider or env_map.get("TRADINGAGENTS_LLM_PROVIDER"))
    provider_resolution = resolve_provider_runtime(
        env=env_map,
        selected_provider=requested_llm_provider,
        backend_url=backend_url or env_map.get("TRADINGAGENTS_BACKEND_URL"),
    )
    selected_llm_provider = normalize_llm_provider(provider_resolution.get("selected_provider"))
    effective_env = dict(provider_resolution.get("resolved_env") or env_map)
    required_llm_env_var = provider_resolution.get("credential_env_var")
    selected_provider_key_present = bool(provider_resolution.get("credential_present"))
    provider_key_map = available_provider_keys(effective_env)
    alpha_vantage_api_key_present = bool(clean_text(effective_env.get("ALPHA_VANTAGE_API_KEY")))
    tushare_token_present = bool(clean_text(effective_env.get("TUSHARE_TOKEN")) or clean_text(effective_env.get("TUSHARE_PRO_TOKEN")))
    configured_backend_url = clean_text(provider_resolution.get("backend_url")) or None
    provider_endpoint_reachable, provider_endpoint_error, provider_endpoint_url = (
        endpoint_check(selected_llm_provider, configured_backend_url)
        if endpoint_check is not None
        else probe_provider_endpoint(selected_llm_provider, configured_backend_url)
    )
    enabled = to_bool(env_map.get("TRADINGAGENTS_ENABLED"))
    version_guard = clean_text(env_map.get("TRADINGAGENTS_VERSION_GUARD")) or None
    blocking_items: list[str] = []
    warnings: list[str] = []

    if not package_installed:
        blocking_items.append("TradingAgents package is not installed in the operator Python environment.")
    elif not package_runtime_importable:
        blocking_items.append("TradingAgents runtime imports failed in the selected Python environment.")
    if version_guard and package_installed and not package_version:
        blocking_items.append("TradingAgents version could not be determined, so the configured version guard cannot be enforced.")
    if version_guard and package_version and not package_version.startswith(version_guard):
        blocking_items.append(
            f"TradingAgents version guard failed: detected `{package_version}` but expected `{version_guard}`."
        )
    if not selected_provider_key_present:
        if required_llm_env_var:
            blocking_items.append(
                f"{required_llm_env_var} is missing from the operator environment for llm_provider `{selected_llm_provider}`."
            )
        else:
            blocking_items.append(f"Credential requirements for llm_provider `{selected_llm_provider}` are not currently recognized by the probe.")
    if not provider_endpoint_reachable:
        blocking_items.append(
            f"Provider endpoint check failed for llm_provider `{selected_llm_provider}` at `{provider_endpoint_url or 'unknown'}`."
        )
    if provider_resolution.get("credential_mode") == "proxy_managed":
        warnings.append("Selected provider credential is proxy-managed via local Claude settings; verify the local proxy is active before live pilot.")
    if not enabled:
        warnings.append("TRADINGAGENTS_ENABLED is not set to true, so live bridge runs stay disabled by default.")
    if not alpha_vantage_api_key_present:
        warnings.append(
            "ALPHA_VANTAGE_API_KEY is not set; upstream data vendors may remain on yfinance, which can rate-limit live pilot runs."
        )
    if not tushare_token_present:
        warnings.append(
            "TUSHARE_TOKEN is not set; the `free_tushare_market` local-market profile is not available, so tokenless mainland runs should prefer `free_eastmoney_market`."
        )

    return {
        "status": "ready" if not blocking_items else "blocked",
        "checked_at": isoformat_z(now_utc()),
        "python": {
            "executable": clean_text(python_executable or sys.executable),
            "version": clean_text(python_version or sys.version.split()[0]),
        },
        "package": {
            "name": "tradingagents",
            "installed": package_installed,
            "version": clean_text(package_version) or None,
            "origin": package_origin(package_spec) or None,
            "runtime_importable": package_runtime_importable,
            "runtime_import_error": clean_text(package_runtime_import_error) or None,
        },
        "credentials": {
            "llm_provider": selected_llm_provider,
            "requested_llm_provider": requested_llm_provider or None,
            "selected_provider_source": provider_resolution.get("selected_provider_source"),
            "selected_provider_auto": bool(provider_resolution.get("selected_provider_auto")),
            "required_llm_env_var": required_llm_env_var,
            "llm_api_key_present": selected_provider_key_present,
            "selected_provider_credential_source": provider_resolution.get("credential_source"),
            "selected_provider_credential_mode": provider_resolution.get("credential_mode"),
            "available_provider_keys": provider_key_map,
            "provider_endpoint_url": provider_endpoint_url,
            "provider_endpoint_reachable": provider_endpoint_reachable,
            "provider_endpoint_error": clean_text(provider_endpoint_error) or None,
            "alpha_vantage_api_key_present": alpha_vantage_api_key_present,
            "tushare_token_present": tushare_token_present,
            "auxiliary_env_sources": dict(provider_resolution.get("auxiliary_env_sources") or {}),
            "openai_api_key_present": provider_key_map.get("openai", False),
        },
        "config": {
            "tradingagents_python": clean_text(env_map.get("TRADINGAGENTS_PYTHON")) or None,
            "tradingagents_pythonpath": clean_text(env_map.get("TRADINGAGENTS_PYTHONPATH")) or None,
            "tradingagents_llm_provider": selected_llm_provider,
            "requested_tradingagents_llm_provider": requested_llm_provider or None,
            "tradingagents_backend_url": clean_text(env_map.get("TRADINGAGENTS_BACKEND_URL")) or None,
            "resolved_backend_url": configured_backend_url,
            "resolved_backend_source": provider_resolution.get("backend_source"),
            "tradingagents_enabled": enabled,
            "cost_budget_tokens": clean_text(env_map.get("TRADINGAGENTS_COST_BUDGET_TOKENS")) or None,
            "timeout_seconds": clean_text(env_map.get("TRADINGAGENTS_TIMEOUT_SECONDS")) or None,
            "version_guard": version_guard,
            "codex_config_path": clean_text((provider_resolution.get("codex") or {}).get("config_path")) or None,
            "codex_auth_path": clean_text((provider_resolution.get("codex") or {}).get("auth_path")) or None,
            "claude_settings_path": clean_text((provider_resolution.get("claude") or {}).get("settings_path")) or None,
            "claude_settings_local_path": clean_text((provider_resolution.get("claude") or {}).get("settings_local_path")) or None,
        },
        "blocking_items": blocking_items,
        "warnings": warnings,
    }


def build_operator_probe_markdown(result: dict[str, Any]) -> str:
    python_info = result.get("python") or {}
    package_info = result.get("package") or {}
    credentials = result.get("credentials") or {}
    config = result.get("config") or {}

    lines = [
        "# TradingAgents Operator Probe",
        "",
        f"- Status: `{clean_text(result.get('status')) or 'unknown'}`",
        f"- Checked at: `{clean_text(result.get('checked_at')) or 'unknown'}`",
        f"- Python: `{clean_text(python_info.get('executable')) or 'unknown'}` (`{clean_text(python_info.get('version')) or 'unknown'}`)",
        f"- TradingAgents installed: `{str(bool(package_info.get('installed'))).lower()}`",
        f"- TradingAgents version: `{clean_text(package_info.get('version')) or 'unknown'}`",
        f"- TradingAgents origin: `{clean_text(package_info.get('origin')) or 'unknown'}`",
        f"- TradingAgents runtime importable: `{str(bool(package_info.get('runtime_importable'))).lower()}`",
        f"- LLM provider: `{clean_text(credentials.get('llm_provider')) or 'openai'}`",
        f"- Requested LLM provider: `{clean_text(credentials.get('requested_llm_provider')) or 'auto'}`",
        f"- Provider selection source: `{clean_text(credentials.get('selected_provider_source')) or 'unknown'}`",
        f"- Provider auto-selected: `{str(bool(credentials.get('selected_provider_auto'))).lower()}`",
        f"- Required provider env var: `{clean_text(credentials.get('required_llm_env_var')) or 'none'}`",
        f"- Selected provider key present: `{str(bool(credentials.get('llm_api_key_present'))).lower()}`",
        f"- Credential source: `{clean_text(credentials.get('selected_provider_credential_source')) or 'unknown'}`",
        f"- Credential mode: `{clean_text(credentials.get('selected_provider_credential_mode')) or 'unknown'}`",
        f"- Provider endpoint URL: `{clean_text(credentials.get('provider_endpoint_url')) or 'none'}`",
        f"- Provider endpoint reachable: `{str(bool(credentials.get('provider_endpoint_reachable'))).lower()}`",
        f"- OPENAI_API_KEY present: `{str(bool(credentials.get('openai_api_key_present'))).lower()}`",
        f"- ALPHA_VANTAGE_API_KEY present: `{str(bool(credentials.get('alpha_vantage_api_key_present'))).lower()}`",
        f"- TUSHARE_TOKEN present: `{str(bool(credentials.get('tushare_token_present'))).lower()}`",
        f"- TRADINGAGENTS_PYTHON: `{clean_text(config.get('tradingagents_python')) or 'unset'}`",
        f"- TRADINGAGENTS_PYTHONPATH: `{clean_text(config.get('tradingagents_pythonpath')) or 'unset'}`",
        f"- TRADINGAGENTS_LLM_PROVIDER: `{clean_text(config.get('tradingagents_llm_provider')) or 'openai'}`",
        f"- Requested TRADINGAGENTS_LLM_PROVIDER: `{clean_text(config.get('requested_tradingagents_llm_provider')) or 'auto'}`",
        f"- TRADINGAGENTS_BACKEND_URL: `{clean_text(config.get('tradingagents_backend_url')) or 'unset'}`",
        f"- Resolved backend URL: `{clean_text(config.get('resolved_backend_url')) or 'unset'}`",
        f"- Resolved backend source: `{clean_text(config.get('resolved_backend_source')) or 'unknown'}`",
        f"- TRADINGAGENTS_ENABLED: `{str(bool(config.get('tradingagents_enabled'))).lower()}`",
        f"- Cost budget tokens: `{clean_text(config.get('cost_budget_tokens')) or 'unset'}`",
        f"- Timeout seconds: `{clean_text(config.get('timeout_seconds')) or 'unset'}`",
        f"- Version guard: `{clean_text(config.get('version_guard')) or 'unset'}`",
    ]
    import_error = clean_text(package_info.get("runtime_import_error"))
    if import_error:
        lines.append(f"- TradingAgents runtime import error: `{import_error}`")
    endpoint_error = clean_text(credentials.get("provider_endpoint_error"))
    if endpoint_error:
        lines.append(f"- Provider endpoint error: `{endpoint_error}`")
    auxiliary_env_sources = dict(credentials.get("auxiliary_env_sources") or {})
    for env_key, source in sorted(auxiliary_env_sources.items()):
        lines.append(f"- {clean_text(env_key)} source: `{clean_text(source) or 'unknown'}`")
    claude_settings_local_path = clean_text(config.get("claude_settings_local_path"))
    if claude_settings_local_path:
        lines.append(f"- Claude local settings path: `{claude_settings_local_path}`")

    blocking_items = result.get("blocking_items") or []
    if blocking_items:
        lines.extend(["", "## Blocking Items", ""])
        lines.extend([f"- {clean_text(item)}" for item in blocking_items])

    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend([f"- {clean_text(item)}" for item in warnings])

    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe the operator environment for TradingAgents live pilot readiness.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--markdown-output", help="Optional markdown output path.")
    parser.add_argument("--llm-provider", help="Override the intended TradingAgents llm_provider for credential checks.")
    parser.add_argument("--backend-url", help="Override the intended provider backend URL for endpoint checks.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = collect_operator_probe(llm_provider=args.llm_provider, backend_url=args.backend_url)
    if not args.quiet:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
    if args.markdown_output:
        output_path = Path(args.markdown_output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build_operator_probe_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
