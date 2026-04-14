#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_operator_probe import build_operator_probe_markdown, collect_operator_probe


TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp-tradingagents-tests"


class TradingAgentsOperatorProbeTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TMP_ROOT.exists():
            for path in sorted(TMP_ROOT.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()

    def test_collect_operator_probe_reports_blocked_when_package_and_key_are_missing(self) -> None:
        result = collect_operator_probe(
            env={
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
            },
            spec_finder=lambda name: None,
            version_lookup=lambda name: "",
            import_check=lambda: (False, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["package"]["installed"])
        self.assertFalse(result["credentials"]["llm_api_key_present"])
        self.assertEqual(result["credentials"]["llm_provider"], "openai")
        self.assertEqual(len(result["blocking_items"]), 2)

    def test_collect_operator_probe_reports_ready_when_everything_is_present(self) -> None:
        result = collect_operator_probe(
            env={
                "OPENAI_API_KEY": "masked",
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_PYTHON": "C:\\operator\\python.exe",
                "TRADINGAGENTS_PYTHONPATH": "C:\\operator\\TradingAgents;C:\\operator\\deps",
                "TRADINGAGENTS_LLM_PROVIDER": "openai",
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_COST_BUDGET_TOKENS": "40000",
                "TRADINGAGENTS_TIMEOUT_SECONDS": "90",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["package"]["version"], "0.2.3")
        self.assertTrue(result["package"]["runtime_importable"])
        self.assertEqual(result["package"]["origin"], "C:\\operator\\TradingAgents\\tradingagents\\__init__.py")
        self.assertTrue(result["credentials"]["llm_api_key_present"])
        self.assertFalse(result["credentials"]["tushare_token_present"])
        self.assertEqual(result["credentials"]["required_llm_env_var"], "OPENAI_API_KEY")
        self.assertEqual(result["credentials"]["selected_provider_source"], "explicit")
        self.assertEqual(result["config"]["tradingagents_python"], "C:\\operator\\python.exe")
        self.assertEqual(result["config"]["tradingagents_pythonpath"], "C:\\operator\\TradingAgents;C:\\operator\\deps")
        self.assertTrue(result["config"]["tradingagents_enabled"])

    def test_collect_operator_probe_supports_google_provider_credentials(self) -> None:
        result = collect_operator_probe(
            env={
                "GOOGLE_API_KEY": "masked",
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_LLM_PROVIDER": "google",
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["credentials"]["llm_provider"], "google")
        self.assertEqual(result["credentials"]["required_llm_env_var"], "GOOGLE_API_KEY")
        self.assertTrue(result["credentials"]["llm_api_key_present"])

    def test_collect_operator_probe_reports_tushare_token_when_present(self) -> None:
        result = collect_operator_probe(
            env={
                "OPENAI_API_KEY": "masked",
                "TUSHARE_TOKEN": "tushare-token",
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertTrue(result["credentials"]["tushare_token_present"])
        self.assertNotIn("free_tushare_market", " ".join(result["warnings"]))

    def test_collect_operator_probe_reads_auxiliary_tokens_from_claude_settings(self) -> None:
        claude_home = TMP_ROOT / "claude-aux"
        claude_home.mkdir(parents=True, exist_ok=True)
        (claude_home / "settings.json").write_text(
            json.dumps(
                {
                    "env": {
                        "ALPHA_VANTAGE_API_KEY": "alpha-test",
                        "TUSHARE_TOKEN": "tushare-test",
                    }
                }
            ),
            encoding="utf-8",
        )

        result = collect_operator_probe(
            env={
                "OPENAI_API_KEY": "masked",
                "CLAUDE_HOME": str(claude_home),
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertTrue(result["credentials"]["alpha_vantage_api_key_present"])
        self.assertTrue(result["credentials"]["tushare_token_present"])
        self.assertEqual(result["credentials"]["auxiliary_env_sources"]["ALPHA_VANTAGE_API_KEY"], "claude_settings_env")
        self.assertEqual(result["credentials"]["auxiliary_env_sources"]["TUSHARE_TOKEN"], "claude_settings_env")

    def test_collect_operator_probe_blocks_when_runtime_imports_fail(self) -> None:
        result = collect_operator_probe(
            env={
                "OPENAI_API_KEY": "masked",
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (False, "ModuleNotFoundError: crewai"),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["package"]["runtime_importable"])
        self.assertIn("runtime imports failed", " ".join(result["blocking_items"]))
        self.assertIn("ModuleNotFoundError", result["package"]["runtime_import_error"])

    def test_collect_operator_probe_blocks_when_ollama_endpoint_is_unreachable(self) -> None:
        result = collect_operator_probe(
            env={
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_LLM_PROVIDER": "ollama",
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (False, "Connection refused", "http://localhost:11434/api/tags"),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["credentials"]["llm_provider"], "ollama")
        self.assertFalse(result["credentials"]["provider_endpoint_reachable"])
        self.assertIn("Provider endpoint check failed", " ".join(result["blocking_items"]))

    def test_collect_operator_probe_auto_detects_codex_provider(self) -> None:
        codex_home = TMP_ROOT / "codex-auto"
        codex_home.mkdir(parents=True, exist_ok=True)
        (codex_home / "config.toml").write_text(
            (
                'model_provider = "custom"\n\n'
                "[model_providers.custom]\n"
                "requires_openai_auth = true\n"
                'base_url = "https://n.example.com"\n'
            ),
            encoding="utf-8",
        )
        (codex_home / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": "sk-auto"}),
            encoding="utf-8",
        )

        result = collect_operator_probe(
            env={
                "CODEX_HOME": str(codex_home),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["credentials"]["llm_provider"], "openai")
        self.assertEqual(result["credentials"]["requested_llm_provider"], None)
        self.assertEqual(result["credentials"]["selected_provider_source"], "codex_config")
        self.assertTrue(result["credentials"]["selected_provider_auto"])
        self.assertTrue(result["credentials"]["llm_api_key_present"])
        self.assertEqual(result["config"]["resolved_backend_url"], "https://n.example.com")

    def test_collect_operator_probe_auto_detects_claude_provider(self) -> None:
        claude_home = TMP_ROOT / "claude-auto"
        claude_home.mkdir(parents=True, exist_ok=True)
        (claude_home / "settings.json").write_text(
            json.dumps(
                {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "PROXY_MANAGED",
                        "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
                    }
                }
            ),
            encoding="utf-8",
        )

        result = collect_operator_probe(
            env={
                "CLAUDE_HOME": str(claude_home),
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "TRADINGAGENTS_ENABLED": "true",
                "TRADINGAGENTS_VERSION_GUARD": "0.2.3",
            },
            spec_finder=lambda name: SimpleNamespace(origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py"),
            version_lookup=lambda name: "0.2.3",
            import_check=lambda: (True, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["credentials"]["llm_provider"], "anthropic")
        self.assertEqual(result["credentials"]["selected_provider_source"], "claude_settings")
        self.assertTrue(result["credentials"]["selected_provider_auto"])
        self.assertEqual(result["credentials"]["selected_provider_credential_mode"], "proxy_managed")
        self.assertIn("proxy-managed", " ".join(result["warnings"]))

    def test_build_operator_probe_markdown_lists_blocking_items(self) -> None:
        result = collect_operator_probe(
            env={
                "CODEX_HOME": str(TMP_ROOT / "missing-codex"),
                "CLAUDE_HOME": str(TMP_ROOT / "missing-claude"),
            },
            spec_finder=lambda name: None,
            version_lookup=lambda name: "",
            import_check=lambda: (False, ""),
            endpoint_check=lambda provider, backend_url: (True, "", None),
            python_executable="python.exe",
            python_version="3.12.0",
        )

        markdown = build_operator_probe_markdown(result)

        self.assertIn("# TradingAgents Operator Probe", markdown)
        self.assertIn("Blocking Items", markdown)
        self.assertIn("Provider selection source", markdown)
        self.assertIn("TUSHARE_TOKEN present", markdown)
        self.assertIn("source:", markdown)
        self.assertIn("Required provider env var", markdown)


if __name__ == "__main__":
    unittest.main()
