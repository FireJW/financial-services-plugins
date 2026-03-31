from __future__ import annotations

import os
import py_compile
import json
import shutil
import sys
import urllib.error
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_reach_bridge_runtime import run_agent_reach_bridge
from agent_reach_deploy_check_runtime import run_agent_reach_deploy_check
from hot_topic_discovery_runtime import run_hot_topic_discovery


class AgentReachRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-agent-reach"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deploy_check_handles_missing_install_root_cleanly(self) -> None:
        missing_root = self.temp_dir / "missing-install"
        result = run_agent_reach_deploy_check({"install_root": str(missing_root)})
        self.assertEqual(result["status"], "missing_install")
        self.assertFalse(result["core_channels_ready"])
        self.assertIn("Install root is missing", "\n".join(result["notes"]))

    def test_deploy_check_can_report_core_channels_ready_from_explicit_probes(self) -> None:
        install_root = self.temp_dir / "ready-install"
        (install_root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        (install_root / ".venv" / "Scripts" / "agent-reach.exe").write_bytes(b"stub")
        state_root = install_root / ".agent-reach"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "version.lock").write_text(
            '{"repo":"https://github.com/Panniantong/agent-reach","pinned_commit":"abc","pinned_date":"2026-03-31T00:00:00+00:00","x_backend":"bird"}',
            encoding="utf-8",
        )
        (state_root / "doctor-report.json").write_text('{"x_backend":"bird"}', encoding="utf-8")

        result = run_agent_reach_deploy_check(
            {
                "install_root": str(install_root),
                "python_binary": sys.executable,
                "channel_probes": {
                    "web_jina": {"status": "ok"},
                    "github": {"status": "ok"},
                    "rss": {"status": "ok"},
                },
            }
        )
        self.assertTrue(result["core_channels_ready"])
        self.assertEqual(result["channels"]["web_jina"], "ok")
        self.assertEqual(result["channels"]["github"], "ok")
        self.assertEqual(result["channels"]["rss"], "ok")

    def test_deploy_check_can_probe_core_channels_automatically(self) -> None:
        install_root = self.temp_dir / "auto-probe-install"
        (install_root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        (install_root / ".venv" / "Scripts" / "agent-reach.exe").write_bytes(b"stub")
        state_root = install_root / ".agent-reach"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "version.lock").write_text(
            '{"repo":"https://github.com/Panniantong/agent-reach","pinned_commit":"abc","pinned_date":"2026-03-31T00:00:00+00:00","x_backend":"bird"}',
            encoding="utf-8",
        )
        (state_root / "doctor-report.json").write_text('{"x_backend":"bird"}', encoding="utf-8")

        with patch("agent_reach_deploy_check_runtime.inspect_binary") as inspect_binary_mock:
            def fake_binary(name: str, _install_root: Path) -> dict[str, object]:
                if name in {"agent-reach", "gh", "yt-dlp", "node", "npm", "mcporter", "bird"}:
                    return {"name": name, "status": "ok", "path": f"C:/stub/{name}.exe", "version": "1.0", "error": ""}
                return {"name": name, "status": "missing", "path": "", "version": "", "error": ""}

            inspect_binary_mock.side_effect = fake_binary
            with patch("agent_reach_deploy_check_runtime.probe_channel_live", return_value=("ok", "")):
                result = run_agent_reach_deploy_check(
                    {
                        "install_root": str(install_root),
                        "python_binary": sys.executable,
                        "channels": ["web_jina", "github", "rss"],
                    }
                )

        self.assertTrue(result["core_channels_ready"])
        self.assertEqual(result["channels"]["web_jina"], "ok")
        self.assertEqual(result["channels"]["github"], "ok")
        self.assertEqual(result["channels"]["rss"], "ok")

    def test_deploy_check_marks_x_missing_credentials_even_when_bird_is_installed(self) -> None:
        install_root = self.temp_dir / "x-credentials-install"
        (install_root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        (install_root / ".venv" / "Scripts" / "agent-reach.exe").write_bytes(b"stub")
        state_root = install_root / ".agent-reach"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "version.lock").write_text(
            '{"repo":"https://github.com/Panniantong/agent-reach","pinned_commit":"abc","pinned_date":"2026-03-31T00:00:00+00:00","x_backend":"bird"}',
            encoding="utf-8",
        )
        (state_root / "doctor-report.json").write_text('{"x_backend":"bird"}', encoding="utf-8")

        with patch("agent_reach_deploy_check_runtime.inspect_binary") as inspect_binary_mock:
            def fake_binary(name: str, _install_root: Path) -> dict[str, object]:
                if name in {"agent-reach", "gh", "yt-dlp", "node", "npm", "mcporter", "bird"}:
                    return {"name": name, "status": "ok", "path": f"C:/stub/{name}.exe", "version": "1.0", "error": ""}
                return {"name": name, "status": "missing", "path": "", "version": "", "error": ""}

            inspect_binary_mock.side_effect = fake_binary
            result = run_agent_reach_deploy_check(
                {
                    "install_root": str(install_root),
                    "python_binary": sys.executable,
                    "channels": ["x"],
                }
            )

        self.assertEqual(result["channels"]["x_twitter"], "missing_credentials")
        self.assertTrue(any(item.startswith("x_twitter:") for item in result["credential_gaps"]))

    def test_bridge_preserves_shadow_origin_and_partial_failures(self) -> None:
        dedupe_store = self.temp_dir / "dedupe.json"
        request = {
            "topic": "Huawei AI chip orders",
            "analysis_time": "2026-03-31T03:00:00+00:00",
            "questions": ["What is fresh and what still needs stronger confirmation?"],
            "claims": [{"claim_id": "claim-huawei", "claim_text": "Huawei AI chip orders are rising."}],
            "channels": ["github", "youtube"],
            "channel_payloads": {
                "github": [
                    {
                        "full_name": "example/huawei-chip-watch",
                        "description": "Tracks Huawei AI chip supply-chain chatter.",
                        "url": "https://github.com/example/huawei-chip-watch",
                        "updatedAt": "2026-03-31T02:30:00+00:00",
                    }
                ]
            },
            "channel_commands": {
                "youtube": ["missing-ytdlp-binary"],
            },
            "dedupe_store_path": str(dedupe_store),
        }
        result = run_agent_reach_bridge(request)
        observations = result["retrieval_result"]["observations"]
        self.assertEqual(result["channels_succeeded"], ["github"])
        self.assertTrue(any(item["channel"] == "youtube" for item in result["channels_failed"]))
        self.assertEqual(result["observations_imported"], 1)
        self.assertEqual(observations[0]["origin"], "agent_reach")
        self.assertEqual(observations[0]["channel"], "shadow")
        self.assertEqual(observations[0]["agent_reach_channel"], "github")

        rerun = run_agent_reach_bridge(request)
        self.assertEqual(rerun["observations_imported"], 0)
        self.assertEqual(rerun["observations_skipped_duplicate"], 1)

    def test_bridge_can_fetch_github_without_gh_auth(self) -> None:
        class FakeResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                self.status = 200
                self._payload = json.dumps(payload).encode("utf-8")

            def read(self) -> bytes:
                return self._payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        with patch(
            "agent_reach_bridge_runtime.urllib.request.urlopen",
            return_value=FakeResponse(
                {
                    "items": [
                        {
                            "full_name": "example/agent-reach-watch",
                            "description": "Tracks cross-platform discovery ideas.",
                            "html_url": "https://github.com/example/agent-reach-watch",
                            "updated_at": "2026-03-31T02:45:00+00:00",
                            "stargazers_count": 42,
                            "owner": {"login": "example"},
                        }
                    ]
                }
            ),
        ):
            result = run_agent_reach_bridge(
                {
                    "topic": "agent reach",
                    "analysis_time": "2026-03-31T03:00:00+00:00",
                    "channels": ["github"],
                    "dedupe_store_path": str(self.temp_dir / "github-live.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["github"])
        self.assertEqual(result["observations_imported"], 1)
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["origin"], "agent_reach")
        self.assertEqual(observation["agent_reach_channel"], "github")
        self.assertEqual(observation["source_name"], "GitHub @example")

    def test_bridge_youtube_uses_cookies_from_pseudo_home_config(self) -> None:
        pseudo_home = self.temp_dir / "agent-reach-home"
        config_root = pseudo_home / ".agent-reach"
        config_root.mkdir(parents=True, exist_ok=True)
        (config_root / "config.yaml").write_text("youtube_cookies_from: edge\n", encoding="utf-8")
        captured_commands: list[list[str]] = []

        def fake_subprocess_run(command: list[str], capture_output: bool, text: bool, timeout: int, check: bool) -> CompletedProcess[str]:
            captured_commands.append(list(command))
            return CompletedProcess(command, 0, stdout='{"entries":[]}', stderr="")

        with patch("agent_reach_bridge_runtime.subprocess.run", side_effect=fake_subprocess_run):
            result = run_agent_reach_bridge(
                {
                    "topic": "Trump Iran ground troops",
                    "analysis_time": "2026-03-31T03:00:00+00:00",
                    "channels": ["youtube"],
                    "pseudo_home": str(pseudo_home),
                    "dedupe_store_path": str(self.temp_dir / "youtube-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["youtube"])
        self.assertTrue(captured_commands)
        self.assertIn("--cookies-from-browser", captured_commands[0])
        self.assertIn("edge", captured_commands[0])

    def test_bridge_default_live_channels_skip_unconfigured_x_and_rss(self) -> None:
        result = run_agent_reach_bridge(
            {
                "topic": "Trump Iran ground troops",
                "analysis_time": "2026-03-31T03:00:00+00:00",
                "channel_payloads": {
                    "github": [
                        {
                            "full_name": "example/trump-iran-watch",
                            "description": "Tracks topic references.",
                            "url": "https://github.com/example/trump-iran-watch",
                            "updatedAt": "2026-03-31T02:30:00+00:00",
                        }
                    ],
                    "youtube": [
                        {
                            "title": "Trump Iran ground troops explainer",
                            "url": "https://www.youtube.com/watch?v=test",
                            "description": "Topic video",
                        }
                    ],
                },
                "dedupe_store_path": str(self.temp_dir / "default-live-dedupe.json"),
            }
        )

        self.assertEqual(result["channels_attempted"], ["github", "youtube"])
        self.assertEqual(result["channels_succeeded"], ["github", "youtube"])

    def test_hot_topic_discovery_passes_agent_reach_pseudo_home(self) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def fake_fetch_agent_reach_channels(payload: dict[str, Any]) -> dict[str, Any]:
            captured_payloads.append(payload)
            return {
                "topic": payload["topic"],
                "fetched_at": payload["analysis_time"],
                "channels_attempted": payload["channels"],
                "channels_succeeded": payload["channels"],
                "channels_failed": [],
                "results_by_channel": {
                    "youtube": {
                        "channel": "youtube",
                        "status": "ok",
                        "reason": "",
                        "items": [
                            {
                                "title": "Iran ground troops explainer",
                                "url": "https://www.youtube.com/watch?v=test",
                                "description": "Topic video",
                            }
                        ],
                    }
                },
                "request": payload,
            }

        with patch("hot_topic_discovery_runtime.fetch_agent_reach_channels", side_effect=fake_fetch_agent_reach_channels):
            run_hot_topic_discovery(
                {
                    "analysis_time": "2026-03-31T05:00:00+00:00",
                    "query": "Trump Iran ground troops",
                    "sources": ["agent-reach:youtube"],
                    "agent_reach_pseudo_home": "D:/Users/rickylu/.codex/vendor/agent-reach-home",
                }
            )

        self.assertTrue(captured_payloads)
        self.assertEqual(captured_payloads[0]["pseudo_home"], "D:/Users/rickylu/.codex/vendor/agent-reach-home")

    def test_bridge_normalizes_relative_and_unparseable_timestamps(self) -> None:
        request = {
            "topic": "Iran negotiation signals",
            "analysis_time": "2026-03-31T06:00:00+00:00",
            "channels": ["x"],
            "channel_payloads": {
                "x": [
                    {
                        "text": "Indirect mediation talks may still be active.",
                        "url": "https://x.com/example/status/1",
                        "published_at": "2 hours ago",
                    },
                    {
                        "text": "Another post with vague time language.",
                        "url": "https://x.com/example/status/2",
                        "published_at": "soon-ish",
                    },
                ]
            },
            "dedupe_store_path": str(self.temp_dir / "timestamp-dedupe.json"),
        }
        result = run_agent_reach_bridge(request)
        observations = {item["url"]: item for item in result["retrieval_result"]["observations"]}
        self.assertTrue(observations["https://x.com/example/status/1"]["published_at"].endswith("+00:00"))
        self.assertEqual(observations["https://x.com/example/status/2"]["published_at"], "")
        self.assertTrue(observations["https://x.com/example/status/2"]["raw_metadata"]["timestamp_unparseable"])

    def test_hot_topic_discovery_keeps_default_sources_when_agent_reach_not_enabled(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "AI chips remain a major supply-chain topic",
                        "source_items": [
                            {
                                "source_name": "36kr",
                                "source_type": "major_news",
                                "url": "https://example.com/ai-chip",
                                "published_at": "2026-03-31T04:00:00+00:00",
                            }
                        ],
                    }
                ],
            }
        )
        self.assertEqual(result["sources_attempted"], ["weibo", "zhihu", "36kr", "google-news-world"])

    def test_hot_topic_discovery_can_opt_in_agent_reach_via_env(self) -> None:
        with patch("hot_topic_discovery_runtime.fetch_google_news_search", return_value=[]):
            with patch.dict(os.environ, {"AGENT_REACH_PROVIDERS": "github"}, clear=False):
                result = run_hot_topic_discovery(
                    {
                        "analysis_time": "2026-03-31T05:00:00+00:00",
                        "query": "Huawei AI chip",
                        "top_n": 3,
                        "agent_reach_channel_payloads": {
                            "github": [
                                {
                                    "full_name": "example/huawei-ai-chip",
                                    "description": "Research repo tracking Huawei AI chip adoption.",
                                    "url": "https://github.com/example/huawei-ai-chip",
                                    "updatedAt": "2026-03-31T04:55:00+00:00",
                                    "stargazersCount": 2500,
                                }
                            ]
                        },
                    }
                )
        self.assertIn("agent-reach:github", result["sources_attempted"])
        self.assertTrue(any("provider:agent-reach:github" in item.get("tags", []) for topic in result["ranked_topics"] for item in topic["source_items"]))

    def test_hot_topic_discovery_one_agent_reach_family_failure_does_not_block_others(self) -> None:
        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = run_hot_topic_discovery(
                {
                    "analysis_time": "2026-03-31T05:00:00+00:00",
                    "query": "Middle East energy shock",
                    "sources": ["agent-reach:web", "agent-reach:github"],
                    "agent_reach_channel_payloads": {
                        "web": [
                            {
                                "title": "Energy shock note",
                                "summary": "Web discovery says shipping insurance costs are rising.",
                                "url": "https://example.com/energy-shock-note",
                                "published_at": "2026-03-31T04:40:00+00:00",
                            }
                        ]
                    },
                }
            )
        self.assertTrue(result["ranked_topics"])
        self.assertTrue(any(item["source"] == "agent-reach:github" for item in result["errors"]))

    def test_new_scripts_compile_cleanly(self) -> None:
        for name in [
            "agent_reach_bridge_runtime.py",
            "agent_reach_bridge.py",
            "agent_reach_deploy_check_runtime.py",
            "agent_reach_deploy_check.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
