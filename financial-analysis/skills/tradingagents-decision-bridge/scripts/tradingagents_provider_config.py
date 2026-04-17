#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": None,
}
PROXY_MANAGED_MARKERS = {"PROXY_MANAGED"}
AUTO_PROVIDER_MARKERS = {"", "auto", "default", "detect"}
DEFAULT_PROVIDER = "openai"
AUXILIARY_ENV_KEYS = (
    "ALPHA_VANTAGE_API_KEY",
    "TUSHARE_TOKEN",
    "TUSHARE_PRO_TOKEN",
)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_non_empty_string(value: Any) -> str:
    return clean_text(value)


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalize_provider_name(value: Any) -> str:
    text = clean_text(value).lower()
    if text in AUTO_PROVIDER_MARKERS:
        return ""
    aliases = {
        "claude": "anthropic",
        "gemini": "google",
        "grok": "xai",
    }
    if text in aliases:
        return aliases[text]
    if "anthropic" in text or "claude" in text:
        return "anthropic"
    if "google" in text or "gemini" in text:
        return "google"
    if "openrouter" in text:
        return "openrouter"
    if text == "x.ai" or "xai" in text or "grok" in text:
        return "xai"
    if "ollama" in text:
        return "ollama"
    if "openai" in text:
        return "openai"
    return text


def resolve_home(env: Mapping[str, str], env_key: str, default_dir_name: str) -> Path:
    configured = first_non_empty_string(env.get(env_key))
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / default_dir_name).resolve()


def resolve_codex_paths(env: Mapping[str, str]) -> dict[str, Path]:
    codex_home = resolve_home(env, "CODEX_HOME", ".codex")
    config_path = Path(first_non_empty_string(env.get("CODEX_CONFIG_PATH")) or codex_home / "config.toml").expanduser().resolve()
    auth_path = Path(first_non_empty_string(env.get("CODEX_AUTH_PATH")) or codex_home / "auth.json").expanduser().resolve()
    return {
        "home": codex_home,
        "config_path": config_path,
        "auth_path": auth_path,
    }


def resolve_claude_paths(env: Mapping[str, str]) -> dict[str, Path]:
    claude_home = resolve_home(env, "CLAUDE_HOME", ".claude")
    settings_path = Path(first_non_empty_string(env.get("CLAUDE_SETTINGS_PATH")) or claude_home / "settings.json").expanduser().resolve()
    settings_local_path = Path(
        first_non_empty_string(env.get("CLAUDE_SETTINGS_LOCAL_PATH")) or claude_home / "settings.local.json"
    ).expanduser().resolve()
    return {
        "home": claude_home,
        "settings_path": settings_path,
        "settings_local_path": settings_local_path,
    }


def load_json_dict(path: Path) -> dict[str, Any]:
    try:
        return safe_dict(json.loads(path.read_text(encoding="utf-8-sig")))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def load_toml_dict(path: Path) -> dict[str, Any]:
    try:
        return safe_dict(tomllib.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def get_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    normalized_key = clean_text(key).lower()
    if not normalized_key:
        return None
    for candidate_key, candidate_value in mapping.items():
        if clean_text(candidate_key).lower() == normalized_key:
            return candidate_value
    return None


def load_codex_provider_config(env: Mapping[str, str]) -> dict[str, Any]:
    paths = resolve_codex_paths(env)
    parsed_config = load_toml_dict(paths["config_path"])
    auth_config = load_json_dict(paths["auth_path"])
    configured_providers = safe_dict(parsed_config.get("model_providers"))
    provider_name = first_non_empty_string(env.get("CODEX_MODEL_PROVIDER")) or first_non_empty_string(parsed_config.get("model_provider"))
    provider_block = safe_dict(get_case_insensitive(configured_providers, provider_name) or {})
    provider_display_name = first_non_empty_string(provider_block.get("name")) or provider_name
    base_url = (
        first_non_empty_string(env.get("OPENAI_BASE_URL"))
        or first_non_empty_string(env.get("CODEX_BASE_URL"))
        or first_non_empty_string(provider_block.get("base_url"))
    )
    api_key = first_non_empty_string(env.get("OPENAI_API_KEY")) or first_non_empty_string(auth_config.get("OPENAI_API_KEY"))
    provider_name_normalized = normalize_provider_name(provider_name or provider_display_name)
    provider_requires_openai_auth = to_bool(provider_block.get("requires_openai_auth"), False)
    provider_kind = provider_name_normalized if provider_name_normalized in PROVIDER_ENV_VARS else ""
    if not provider_kind and (
        provider_requires_openai_auth
        or bool(api_key)
        or bool(base_url)
    ):
        provider_kind = "openai"
    return {
        "home": str(paths["home"]),
        "config_path": str(paths["config_path"]),
        "auth_path": str(paths["auth_path"]),
        "config_exists": paths["config_path"].exists(),
        "auth_exists": paths["auth_path"].exists(),
        "provider_name": provider_name or None,
        "provider_display_name": provider_display_name or None,
        "provider_name_normalized": provider_name_normalized or None,
        "provider_kind": provider_kind or None,
        "provider_requires_openai_auth": provider_requires_openai_auth,
        "wire_api": first_non_empty_string(provider_block.get("wire_api")) or None,
        "base_url": base_url or None,
        "openai_api_key": api_key or None,
    }


def load_claude_settings_config(env: Mapping[str, str]) -> dict[str, Any]:
    paths = resolve_claude_paths(env)
    settings = load_json_dict(paths["settings_path"])
    settings_local = load_json_dict(paths["settings_local_path"])
    base_settings_env = {
        clean_text(key): clean_text(value)
        for key, value in safe_dict(settings.get("env")).items()
        if clean_text(key) and clean_text(value)
    }
    local_settings_env = {
        clean_text(key): clean_text(value)
        for key, value in safe_dict(settings_local.get("env")).items()
        if clean_text(key) and clean_text(value)
    }
    settings_env = {
        **base_settings_env,
        **local_settings_env,
    }
    return {
        "home": str(paths["home"]),
        "settings_path": str(paths["settings_path"]),
        "settings_local_path": str(paths["settings_local_path"]),
        "settings_exists": paths["settings_path"].exists(),
        "settings_local_exists": paths["settings_local_path"].exists(),
        "settings_env": settings_env,
    }


def infer_provider_from_env(env: Mapping[str, str]) -> tuple[str, str] | None:
    for provider, env_var in PROVIDER_ENV_VARS.items():
        if env_var and first_non_empty_string(env.get(env_var)):
            return provider, "env_credential"
    if first_non_empty_string(env.get("OPENAI_BASE_URL")) or first_non_empty_string(env.get("CODEX_BASE_URL")):
        return "openai", "env_backend"
    if first_non_empty_string(env.get("ANTHROPIC_BASE_URL")):
        return "anthropic", "env_backend"
    return None


def infer_provider_from_codex(codex_config: Mapping[str, Any]) -> tuple[str, str] | None:
    provider_kind = first_non_empty_string(codex_config.get("provider_kind"))
    if provider_kind in PROVIDER_ENV_VARS:
        return provider_kind, "codex_config"
    return None


def infer_provider_from_claude(claude_config: Mapping[str, Any]) -> tuple[str, str] | None:
    env_map = safe_dict(claude_config.get("settings_env"))
    if (
        first_non_empty_string(env_map.get("ANTHROPIC_API_KEY"))
        or first_non_empty_string(env_map.get("ANTHROPIC_AUTH_TOKEN"))
        or first_non_empty_string(env_map.get("ANTHROPIC_BASE_URL"))
    ):
        return "anthropic", "claude_settings"
    return None


def resolve_selected_provider(
    requested_provider: Any,
    *,
    env: Mapping[str, str],
    codex_config: Mapping[str, Any],
    claude_config: Mapping[str, Any],
) -> tuple[str, str, bool]:
    requested_text = first_non_empty_string(requested_provider)
    normalized_requested = normalize_provider_name(requested_text)
    if normalized_requested in PROVIDER_ENV_VARS:
        return normalized_requested, "explicit", False

    for inference in (
        infer_provider_from_env(env),
        infer_provider_from_codex(codex_config),
        infer_provider_from_claude(claude_config),
    ):
        if inference is not None:
            return inference[0], inference[1], True
    return DEFAULT_PROVIDER, "default", True


def resolve_provider_runtime(
    *,
    env: Mapping[str, str] | None = None,
    selected_provider: str = "",
    backend_url: str | None = None,
) -> dict[str, Any]:
    env_map = dict(os.environ) if env is None else dict(env)
    codex_config = load_codex_provider_config(env_map)
    claude_config = load_claude_settings_config(env_map)
    claude_env = safe_dict(claude_config.get("settings_env"))
    provider, selected_provider_source, provider_auto_selected = resolve_selected_provider(
        selected_provider,
        env=env_map,
        codex_config=codex_config,
        claude_config=claude_config,
    )
    credential_env_var = PROVIDER_ENV_VARS.get(provider)

    resolved_env = dict(env_map)
    env_overrides: dict[str, str] = {}
    auxiliary_env_sources: dict[str, str] = {}
    credential_source = None
    credential_mode = "missing"

    if credential_env_var:
        credential_value = first_non_empty_string(env_map.get(credential_env_var))
        if credential_value:
            credential_source = "env"
            credential_mode = "direct"
        elif provider == "openai":
            credential_value = first_non_empty_string(codex_config.get("openai_api_key"))
            if credential_value:
                resolved_env[credential_env_var] = credential_value
                env_overrides[credential_env_var] = credential_value
                credential_source = "codex_auth"
                credential_mode = "direct"
        elif provider == "anthropic":
            credential_value = first_non_empty_string(claude_env.get("ANTHROPIC_API_KEY"))
            if credential_value:
                resolved_env[credential_env_var] = credential_value
                env_overrides[credential_env_var] = credential_value
                credential_source = "claude_settings_env"
                credential_mode = "direct"
            else:
                credential_value = first_non_empty_string(claude_env.get("ANTHROPIC_AUTH_TOKEN"))
                if credential_value:
                    resolved_env[credential_env_var] = credential_value
                    env_overrides[credential_env_var] = credential_value
                    credential_source = "claude_settings_env"
                    credential_mode = "proxy_managed" if credential_value.upper() in PROXY_MANAGED_MARKERS else "direct"
    else:
        credential_source = "not_required"
        credential_mode = "not_required"

    resolved_backend_url = first_non_empty_string(backend_url)
    backend_source = "argument" if resolved_backend_url else None
    if not resolved_backend_url:
        resolved_backend_url = first_non_empty_string(env_map.get("TRADINGAGENTS_BACKEND_URL"))
        if resolved_backend_url:
            backend_source = "env"
    if not resolved_backend_url and provider == "openai":
        resolved_backend_url = first_non_empty_string(env_map.get("OPENAI_BASE_URL")) or first_non_empty_string(codex_config.get("base_url"))
        if resolved_backend_url:
            backend_source = "env" if first_non_empty_string(env_map.get("OPENAI_BASE_URL")) else "codex_config"
    if not resolved_backend_url and provider == "anthropic":
        resolved_backend_url = first_non_empty_string(env_map.get("ANTHROPIC_BASE_URL")) or first_non_empty_string(
            claude_env.get("ANTHROPIC_BASE_URL")
        )
        if resolved_backend_url:
            backend_source = "env" if first_non_empty_string(env_map.get("ANTHROPIC_BASE_URL")) else "claude_settings_env"

    if provider == "openai" and resolved_backend_url and not first_non_empty_string(env_map.get("OPENAI_BASE_URL")):
        env_overrides["OPENAI_BASE_URL"] = resolved_backend_url
        resolved_env["OPENAI_BASE_URL"] = resolved_backend_url
    if provider == "anthropic" and resolved_backend_url and not first_non_empty_string(env_map.get("ANTHROPIC_BASE_URL")):
        env_overrides["ANTHROPIC_BASE_URL"] = resolved_backend_url
        resolved_env["ANTHROPIC_BASE_URL"] = resolved_backend_url

    for env_key in AUXILIARY_ENV_KEYS:
        if first_non_empty_string(resolved_env.get(env_key)):
            auxiliary_env_sources[env_key] = "env"
            continue
        claude_value = first_non_empty_string(claude_env.get(env_key))
        if claude_value:
            resolved_env[env_key] = claude_value
            env_overrides[env_key] = claude_value
            auxiliary_env_sources[env_key] = "claude_settings_env"

    credential_present = bool(first_non_empty_string(resolved_env.get(credential_env_var))) if credential_env_var else True
    return {
        "requested_provider": first_non_empty_string(selected_provider) or None,
        "selected_provider": provider,
        "selected_provider_source": selected_provider_source,
        "selected_provider_auto": provider_auto_selected,
        "credential_env_var": credential_env_var,
        "credential_present": credential_present,
        "credential_source": credential_source,
        "credential_mode": credential_mode,
        "auxiliary_env_sources": auxiliary_env_sources,
        "backend_url": resolved_backend_url or None,
        "backend_source": backend_source,
        "resolved_env": resolved_env,
        "env_overrides": env_overrides,
        "codex": {
            "home": codex_config.get("home"),
            "config_path": codex_config.get("config_path"),
            "auth_path": codex_config.get("auth_path"),
            "provider_name": codex_config.get("provider_name"),
            "provider_display_name": codex_config.get("provider_display_name"),
            "provider_name_normalized": codex_config.get("provider_name_normalized"),
            "provider_kind": codex_config.get("provider_kind"),
            "provider_requires_openai_auth": bool(codex_config.get("provider_requires_openai_auth")),
            "wire_api": codex_config.get("wire_api"),
            "config_exists": bool(codex_config.get("config_exists")),
            "auth_exists": bool(codex_config.get("auth_exists")),
        },
        "claude": {
            "home": claude_config.get("home"),
            "settings_path": claude_config.get("settings_path"),
            "settings_local_path": claude_config.get("settings_local_path"),
            "settings_exists": bool(claude_config.get("settings_exists")),
            "settings_local_exists": bool(claude_config.get("settings_local_exists")),
            "env_keys": sorted(safe_dict(claude_config.get("settings_env")).keys()),
        },
    }


@contextmanager
def temporary_environment_overrides(overrides: Mapping[str, str] | None) -> Iterator[None]:
    normalized = {
        clean_text(key): clean_text(value)
        for key, value in dict(overrides or {}).items()
        if clean_text(key) and clean_text(value)
    }
    previous = {key: os.environ.get(key) for key in normalized}
    try:
        for key, value in normalized.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
