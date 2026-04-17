from __future__ import annotations

import base64
import os
import py_compile
import json
import shutil
import subprocess
import sys
import urllib.error
import unittest
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import hot_topic_discovery_runtime
import agent_reach_bridge_runtime
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

    def test_parse_rss_items_resolves_google_news_wrapper_links_to_canonical_urls(self) -> None:
        xml_text = """
            <rss>
              <channel>
                <item>
                  <title>Canonical article title</title>
                  <link>https://news.google.com/rss/articles/CBMiT2h0dHBzOi8vbmV3cy5leGFtcGxlLmNvbS9zdG9yeS1hYmM?oc=5</link>
                  <description><![CDATA[<p>Wrapper description</p>]]></description>
                  <pubDate>Wed, 16 Apr 2026 08:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>
        """
        canonical_url = "https://news.example.com/story-abc"

        with patch(
            "hot_topic_discovery_runtime.resolve_google_news_rss_target_url",
            return_value=canonical_url,
        ) as resolver_mock:
            items = hot_topic_discovery_runtime.parse_rss_items(
                xml_text,
                "google-news-search",
                "major_news",
                10,
                hot_topic_discovery_runtime.parse_datetime("2026-04-16T08:05:00+00:00", fallback=None),
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], canonical_url)
        self.assertEqual(items[0]["source_name"], "google-news-search")
        self.assertEqual(items[0]["source_type"], "major_news")
        self.assertEqual(items[0]["summary"], "Wrapper description")
        resolver_mock.assert_called_once()

    def test_parse_rss_items_keeps_google_wrapper_link_when_resolution_fails(self) -> None:
        wrapper_url = "https://news.google.com/rss/articles/CBMiP2h0dHBzOi8vbmV3cy5leGFtcGxlLmNvbS9mYWlsYmFjaw?oc=5"
        xml_text = f"""
            <rss>
              <channel>
                <item>
                  <title>Fallback article title</title>
                  <link>{wrapper_url}</link>
                  <description><![CDATA[<p>Fallback description</p>]]></description>
                </item>
              </channel>
            </rss>
        """

        with patch(
            "hot_topic_discovery_runtime.resolve_google_news_rss_target_url",
            return_value="",
        ):
            items = hot_topic_discovery_runtime.parse_rss_items(
                xml_text,
                "google-news-world",
                "major_news",
                10,
                hot_topic_discovery_runtime.parse_datetime("2026-04-16T08:05:00+00:00", fallback=None),
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], wrapper_url)
        self.assertEqual(items[0]["source_name"], "google-news-world")

    def test_parse_rss_items_splits_google_news_title_suffix_into_source_name(self) -> None:
        xml_text = """
            <rss>
              <channel>
                <item>
                  <title>腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！ - C114通信网</title>
                  <link>https://example.com/google-wrapper</link>
                  <description><![CDATA[腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！ C114通信网]]></description>
                </item>
              </channel>
            </rss>
        """

        items = hot_topic_discovery_runtime.parse_rss_items(
            xml_text,
            "google-news-search",
            "major_news",
            10,
            hot_topic_discovery_runtime.parse_datetime("2026-04-16T08:05:00+00:00", fallback=None),
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！")
        self.assertEqual(items[0]["source_name"], "C114通信网")
        self.assertEqual(items[0]["summary"], "腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！")
        self.assertEqual(items[0]["publisher_domain_hint"], "C114通信网")

    def test_parse_rss_items_preserves_google_wrapper_preview_hints_for_downstream_images(self) -> None:
        wrapper_url = "https://news.google.com/rss/articles/CBMiP2h0dHBzOi8vbmV3cy5leGFtcGxlLmNvbS9wcmV2aWV3?oc=5"
        xml_text = f"""
            <rss>
              <channel>
                <item>
                  <title>腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！ - C114通信网</title>
                  <link>{wrapper_url}</link>
                  <description><![CDATA[腾讯发布并开源混元世界模型 2.0，一句话造出3D世界，兼容游戏引擎！ C114通信网]]></description>
                </item>
              </channel>
            </rss>
        """
        preview_url = "https://lh3.googleusercontent.com/preview-image=s1600"

        with patch(
            "hot_topic_discovery_runtime.fetch_google_news_wrapper_page_hints",
            return_value={
                "post_summary": "Wrapper preview summary",
                "media_summary": "Wrapper preview alt",
                "artifact_manifest": [
                    {
                        "role": "post_media",
                        "path": "",
                        "source_url": preview_url,
                        "media_type": "image",
                    }
                ],
            },
        ):
            items = hot_topic_discovery_runtime.parse_rss_items(
                xml_text,
                "google-news-search",
                "major_news",
                10,
                hot_topic_discovery_runtime.parse_datetime("2026-04-16T08:05:00+00:00", fallback=None),
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_summary"], "Wrapper preview summary")
        self.assertEqual(items[0]["media_summary"], "Wrapper preview alt")
        self.assertEqual(items[0]["artifact_manifest"][0]["source_url"], preview_url)

    def test_resolve_google_news_rss_target_url_decodes_direct_url_from_legacy_path_payload(self) -> None:
        canonical_url = "https://publisher.example.com/articles/alpha?from=rss"
        payload = b"\x08\x13\x22" + bytes([len(canonical_url)]) + canonical_url.encode("utf-8") + b"\xd2\x01\x00"
        token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        wrapper_url = f"https://news.google.com/rss/articles/{token}?oc=5"

        resolved = hot_topic_discovery_runtime.resolve_google_news_rss_target_url(wrapper_url)

        self.assertEqual(resolved, canonical_url)

    def test_resolve_google_news_rss_target_url_decodes_au_yql_wrapper_via_batch_execute(self) -> None:
        wrapper_url = (
            "https://news.google.com/rss/articles/"
            "CBMiZkFVX3lxTE1pcDFXMmxSZmMzM29VU0RsbEJFY0xuS25hNC04em9kbXlIa3gzVnk1OThKQTBwRFhnYXVMVTQ0a2I4eTRS"
            "S214SU5lX0xQMFJTOTV4eFNvaEkyZWJ2UVNxQUNoWWlldw?oc=5"
        )
        token = hot_topic_discovery_runtime.extract_google_news_wrapper_token(wrapper_url)
        canonical_url = "https://publisher.example.com/world-model-2"
        requests_seen: list[urllib.request.Request] = []

        class FakeResponse:
            def __init__(self, body: str, *, final_url: str = "") -> None:
                self._body = body.encode("utf-8")
                self._final_url = final_url

            def read(self) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request)
            if request.full_url == "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je":
                return FakeResponse(
                    ')]}\'\n\n'
                    + json.dumps(
                        [
                            ["wrb.fr", "Fbv4je", json.dumps(["garturlres", canonical_url, 1]), None, None, None, "generic"],
                            ["di", 27],
                            ["af.httprm", 27, "0", 8],
                        ]
                    )
                )
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("hot_topic_discovery_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            resolved = hot_topic_discovery_runtime.resolve_google_news_rss_target_url(wrapper_url)

        self.assertEqual(resolved, canonical_url)
        self.assertEqual(len(requests_seen), 1)
        self.assertEqual(requests_seen[0].full_url, "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je")
        self.assertIn(token.encode("utf-8"), requests_seen[0].data)

    def test_resolve_google_news_rss_target_url_falls_back_to_wrapper_page_for_decode_params(self) -> None:
        wrapper_url = (
            "https://news.google.com/rss/articles/"
            "CBMiWEFVX3lxTE9KYjJqaTNKcm1XWHZyOVp6Rm5CbVlscVQ4YVV1c1VSc2xUVGs4SGpuaDVkM2loWGV3c0JJeTlRUF9fVndp"
            "LU10bTNTN1VrOVNjMWJlQ1pWT3U?oc=5"
        )
        token = hot_topic_discovery_runtime.extract_google_news_wrapper_token(wrapper_url)
        article_url = f"https://news.google.com/articles/{token}"
        canonical_url = "https://publisher.example.com/world-model-2"
        requests_seen: list[urllib.request.Request] = []

        class FakeResponse:
            def __init__(self, body: str, *, final_url: str = "") -> None:
                self._body = body.encode("utf-8")
                self._final_url = final_url

            def read(self, _limit: int | None = None) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request)
            if request.full_url == "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je":
                raise urllib.error.URLError("decode endpoint unavailable")
            if request.full_url == article_url:
                return FakeResponse("<html><body>missing params</body></html>")
            if request.full_url == wrapper_url:
                return FakeResponse('<div data-n-a-sg="sig-456" data-n-a-ts="1744777000"></div>')
            if request.full_url == "https://news.google.com/_/DotsSplashUi/data/batchexecute":
                return FakeResponse(
                    json.dumps(
                        [
                            ["wrb.fr", "Fbv4je", json.dumps(["garturlres", canonical_url, 1]), None, None, None, "generic"],
                        ]
                    )
                )
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("hot_topic_discovery_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            resolved = hot_topic_discovery_runtime.resolve_google_news_rss_target_url(wrapper_url)

        self.assertEqual(resolved, canonical_url)
        self.assertEqual(requests_seen[0].full_url, "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je")
        self.assertEqual(requests_seen[1].full_url, article_url)
        self.assertEqual(requests_seen[2].full_url, wrapper_url)
        self.assertEqual(requests_seen[3].full_url, "https://news.google.com/_/DotsSplashUi/data/batchexecute")
        self.assertIn(b"sig-456", requests_seen[3].data)
        self.assertIn(b"1744777000", requests_seen[3].data)

    def test_resolve_google_news_rss_target_url_uses_simple_batch_execute_when_decode_params_absent(self) -> None:
        wrapper_url = (
            "https://news.google.com/rss/articles/"
            "CBMiWEFVX3lxTE9KYjJqaTNKcm1XWHZyOVp6Rm5CbVlscVQ4YVV1c1VSc2xUVGs4SGpuaDVkM2loWGV3c0JJeTlRUF9fVndp"
            "LU10bTNTN1VrOVNjMWJlQ1pWT3U?oc=5"
        )
        token = hot_topic_discovery_runtime.extract_google_news_wrapper_token(wrapper_url)
        article_url = f"https://news.google.com/articles/{token}"
        canonical_url = "https://publisher.example.com/world-model-simple"
        requests_seen: list[urllib.request.Request] = []

        class FakeResponse:
            def __init__(self, body: str, *, final_url: str = "") -> None:
                self._body = body.encode("utf-8")
                self._final_url = final_url

            def read(self, _limit: int | None = None) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request)
            if request.full_url == "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je":
                return FakeResponse(
                    json.dumps(
                        [
                            ["wrb.fr", "Fbv4je", json.dumps(["garturlres", canonical_url, 1]), None, None, None, "generic"],
                        ]
                    )
                )
            if request.full_url == article_url:
                return FakeResponse("<html><body>missing params</body></html>")
            if request.full_url == wrapper_url:
                return FakeResponse("<html><body>still missing params</body></html>")
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("hot_topic_discovery_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            resolved = hot_topic_discovery_runtime.resolve_google_news_rss_target_url(wrapper_url)

        self.assertEqual(resolved, canonical_url)
        self.assertEqual(requests_seen[0].full_url, "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je")
        self.assertIn(token.encode("utf-8"), requests_seen[0].data)

    def test_extract_google_news_wrapper_page_hints_recovers_canonical_url_and_preview_image(self) -> None:
        wrapper_url = "https://news.google.com/rss/articles/CBMifWh0dHBzOi8vbmV3cy5nb29nbGUuY29tL3Jzcy9hcnRpY2xlcy9vbGFxdWU?oc=5"
        canonical_url = "https://publisher.example.com/markets/deal-story?utm_source=google"
        preview_url = "https://lh3.googleusercontent.com/preview-image=s1600"
        html_text = f"""
            <html>
              <head>
                <meta property="og:image" content="{preview_url}" />
                <meta property="og:image:alt" content="Deal site preview" />
              </head>
              <body>
                <c-wiz>
                  "https://uberproxy-pen-redirect.corp.google.com/uberproxy/pen?url={urllib.parse.quote(canonical_url, safe='')}&amp;foo=bar"
                </c-wiz>
              </body>
            </html>
        """

        hints = hot_topic_discovery_runtime.extract_google_news_wrapper_page_hints(wrapper_url, html_text)

        self.assertEqual(hints["final_url"], canonical_url)
        self.assertEqual(hints["title"], "")
        self.assertEqual(hints["media_summary"], "Deal site preview")
        self.assertEqual(len(hints["artifact_manifest"]), 1)
        self.assertEqual(hints["artifact_manifest"][0]["role"], "post_media")
        self.assertEqual(hints["artifact_manifest"][0]["source_url"], preview_url)

    def test_resolve_google_news_rss_target_url_extracts_canonical_url_from_wrapper_html_when_geturl_stays_wrapper(self) -> None:
        wrapper_url = "https://news.google.com/rss/articles/CBMifWh0dHBzOi8vbmV3cy5nb29nbGUuY29tL3Jzcy9hcnRpY2xlcy9vbGFxdWU?oc=5"
        canonical_url = "https://publisher.example.com/markets/deal-story"

        class FakeResponse:
            def __init__(self, body: str, *, final_url: str) -> None:
                self._body = body.encode("utf-8")
                self._final_url = final_url

            def read(self) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        html_text = (
            '<html><body>'
            f'"https://uberproxy-pen-redirect.corp.google.com/uberproxy/pen?url={urllib.parse.quote(canonical_url, safe="")}"'
            "</body></html>"
        )

        with patch(
            "hot_topic_discovery_runtime.urllib.request.urlopen",
            return_value=FakeResponse(html_text, final_url=wrapper_url),
        ):
            resolved = hot_topic_discovery_runtime.resolve_google_news_rss_target_url(wrapper_url)

        self.assertEqual(resolved, canonical_url)

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

        def fake_subprocess_run(command: list[str], capture_output: bool, text: bool, timeout: int, check: bool, **kwargs: object) -> CompletedProcess[str]:
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

    def test_bridge_reddit_can_fetch_queryless_curated_hot_feeds(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._payload = body.encode("utf-8")

            def read(self) -> bytes:
                return self._payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        requests_seen: list[str] = []
        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Global chip supply chain thread</title>
            <link href="https://www.reddit.com/r/stocks/comments/abc123/global_chip_supply_chain_thread/" />
            <updated>2026-03-31T05:30:00+00:00</updated>
            <content>Retail investors are debating global chip supply bottlenecks.</content>
            <category term="stocks" />
          </entry>
        </feed>
        """
        empty_rss_text = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request.full_url)
            if "/search.json?" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/r/stocks/hot.rss"):
                return FakeResponse(rss_text)
            if request.full_url.startswith("https://www.reddit.com/r/") and request.full_url.endswith("/hot.rss"):
                return FakeResponse(empty_rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with (
            patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen),
            patch(
                "agent_reach_bridge_runtime.run_news_index",
                return_value={
                    "status": "ok",
                    "observations": [
                        {
                            "source_name": "Reddit r/stocks",
                            "url": "https://www.reddit.com/r/stocks/comments/abc123/global_chip_supply_chain_thread/",
                        }
                    ],
                },
            ),
        ):
            result = run_agent_reach_bridge(
                {
                    "analysis_time": "2026-03-31T06:00:00+00:00",
                    "channels": ["reddit"],
                    "dedupe_store_path": str(self.temp_dir / "reddit-queryless-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["reddit"])
        self.assertTrue(any("reddit.com/r/stocks/hot.rss" in url for url in requests_seen))
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["source_name"], "Reddit r/stocks")
        self.assertEqual(
            observation["url"],
            "https://www.reddit.com/r/stocks/comments/abc123/global_chip_supply_chain_thread/",
        )

    def test_bridge_reddit_queryless_curated_feeds_collect_multiple_entries_from_ai_subreddits(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._payload = body.encode("utf-8")

            def read(self) -> bytes:
                return self._payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        requests_seen: list[str] = []
        ml_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>AI agent startup sees enterprise demand rising</title>
            <link href="https://www.reddit.com/r/MachineLearning/comments/abc111/ai_agent_startup_sees_enterprise_demand_rising/" />
            <updated>2026-03-31T05:30:00+00:00</updated>
            <content>Users debate enterprise AI demand and monetization.</content>
          </entry>
          <entry>
            <title>NVIDIA packaging bottleneck may finally ease</title>
            <link href="https://www.reddit.com/r/MachineLearning/comments/abc222/nvidia_packaging_bottleneck_may_finally_ease/" />
            <updated>2026-03-31T05:20:00+00:00</updated>
            <content>Users compare packaging bottlenecks and HBM supply checks.</content>
          </entry>
        </feed>
        """
        hardware_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Open-source model cost curve breaks again</title>
            <link href="https://www.reddit.com/r/hardware/comments/def333/open_source_model_cost_curve_breaks_again/" />
            <updated>2026-03-31T05:10:00+00:00</updated>
            <content>Users compare inference economics and model deployment cost curves.</content>
          </entry>
        </feed>
        """
        empty_rss_text = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request.full_url)
            if "/search.json?" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/r/MachineLearning/hot.rss"):
                return FakeResponse(ml_rss)
            if request.full_url.endswith("/r/hardware/hot.rss"):
                return FakeResponse(hardware_rss)
            if request.full_url.startswith("https://www.reddit.com/r/") and request.full_url.endswith("/hot.rss"):
                return FakeResponse(empty_rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertIn("AI agent startup sees enterprise demand rising", titles)
        self.assertIn("NVIDIA packaging bottleneck may finally ease", titles)
        self.assertIn("Open-source model cost curve breaks again", titles)
        self.assertTrue(any(url.endswith("/r/MachineLearning/hot.rss") for url in requests_seen))
        self.assertTrue(any(url.endswith("/r/hardware/hot.rss") for url in requests_seen))

    def test_bridge_reddit_queryless_uses_thematic_searches_before_curated_feeds(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        requests_seen: list[str] = []

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            requests_seen.append(request.full_url)
            if "/r/MachineLearning/search.json" in request.full_url and "AI+chips+semiconductors" in request.full_url:
                return FakeResponse(
                    json.dumps(
                        {
                            "data": {
                                "children": [
                                    {
                                        "data": {
                                            "title": "AI chip supplier checks tighten again",
                                            "permalink": "/r/stocks/comments/q12345/ai_chip_supplier_checks_tighten_again/",
                                            "subreddit_name_prefixed": "r/stocks",
                                            "selftext": "Users are debating AI chip supply checks and HBM constraints.",
                                            "score": 120,
                                            "num_comments": 44,
                                            "created_utc": 1774963200,
                                        }
                                    }
                                ]
                            }
                        }
                    )
                )
            if "search.json" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse("""<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""")
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertIn("AI chip supplier checks tighten again", titles)
        self.assertTrue(any("/r/MachineLearning/search.json" in url for url in requests_seen))

    def test_bridge_reddit_queryless_feed_falls_back_to_rss_when_json_endpoint_is_blocked(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Global chip bottleneck discussion</title>
            <link href="https://www.reddit.com/r/stocks/comments/xyz789/global_chip_bottleneck_discussion/" />
            <updated>2026-03-31T05:30:00+00:00</updated>
            <content>Retail investors are debating packaging and chip bottlenecks.</content>
            <category term="stocks" />
          </entry>
        </feed>
        """

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            if "search.json" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)
            if request.full_url.endswith("/hot.json?limit=20"):
                raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse(rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with (
            patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen),
            patch(
                "agent_reach_bridge_runtime.run_news_index",
                return_value={
                    "status": "ok",
                    "observations": [
                        {
                            "source_name": "Reddit r/stocks",
                            "text_excerpt": "Retail investors are debating packaging and chip bottlenecks.",
                            "url": "https://www.reddit.com/r/stocks/comments/xyz789/global_chip_bottleneck_discussion/",
                        }
                    ],
                },
            ),
        ):
            result = run_agent_reach_bridge(
                {
                    "analysis_time": "2026-03-31T06:00:00+00:00",
                    "channels": ["reddit"],
                    "max_results_per_channel": 20,
                    "dedupe_store_path": str(self.temp_dir / "reddit-rss-fallback-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["reddit"])
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["source_name"], "Reddit r/stocks")
        self.assertIn("packaging and chip bottlenecks", observation["text_excerpt"])

    def test_bridge_reddit_queryless_skips_meta_threads_before_collecting_records(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Rate My Portfolio - r/Stocks Quarterly Thread March 2026</title>
            <link href="https://www.reddit.com/r/stocks/comments/meta111/rate_my_portfolio/" />
            <updated>2026-04-17T00:01:00+00:00</updated>
            <content>Meta portfolio thread.</content>
          </entry>
          <entry>
            <title>Daily General Discussion and Advice Thread - April 17, 2026</title>
            <link href="https://www.reddit.com/r/stocks/comments/meta222/daily_discussion/" />
            <updated>2026-04-17T00:02:00+00:00</updated>
            <content>Meta discussion thread.</content>
          </entry>
          <entry>
            <title>AMD board partners hint at new X3D channel checks</title>
            <link href="https://www.reddit.com/r/stocks/comments/live333/amd_board_partners_hint_at_new_x3d_channel_checks/" />
            <updated>2026-04-17T00:03:00+00:00</updated>
            <content>Users compare AMD channel checks and attach supplier notes.</content>
          </entry>
        </feed>
        """

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            if "search.json" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse(rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertEqual(titles, ["AMD board partners hint at new X3D channel checks"])

    def test_bridge_reddit_queryless_skips_stale_pinned_records(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Reminder: Please do not submit tech support or build questions to /r/hardware</title>
            <link href="https://www.reddit.com/r/hardware/comments/3n9tky/reminder_please_do_not_submit_tech_support_or/" />
            <updated>2015-10-02T21:04:56+00:00</updated>
            <content>Old pinned reminder.</content>
          </entry>
          <entry>
            <title>Samsung foundry customers pull forward advanced packaging orders</title>
            <link href="https://www.reddit.com/r/hardware/comments/live444/samsung_foundry_customers_pull_forward_advanced_packaging_orders/" />
            <updated>2026-04-17T00:05:00+00:00</updated>
            <content>Users compare packaging demand and foundry backlog data.</content>
          </entry>
        </feed>
        """

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            if "search.json" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse(rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "analysis_time": datetime(2026, 4, 17, 0, 30, tzinfo=UTC),
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertEqual(titles, ["Samsung foundry customers pull forward advanced packaging orders"])

    def test_bridge_reddit_queryless_keeps_thematic_market_or_ai_titles(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>MacBook Neo sells out for April as demand for Apple's $599 laptop outpaces supply</title>
            <link href="https://www.reddit.com/r/hardware/comments/live555/macbook_neo_sells_out/" />
            <updated>2026-04-17T00:06:00+00:00</updated>
            <content>Consumer laptop demand chatter.</content>
          </entry>
          <entry>
            <title>AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition</title>
            <link href="https://www.reddit.com/r/hardware/comments/live666/amd_5800x3d_anniversary/" />
            <updated>2026-04-17T00:07:00+00:00</updated>
            <content>Users debate AMD channel checks and chip roadmap implications.</content>
          </entry>
        </feed>
        """

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            if "search.json" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse(rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "analysis_time": datetime(2026, 4, 17, 0, 30, tzinfo=UTC),
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertEqual(titles, ["AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition"])

    def test_bridge_reddit_queryless_ignores_summary_only_model_noise(self) -> None:
        class FakeResponse:
            def __init__(self, body: str) -> None:
                self._body = body.encode("utf-8")

            def read(self) -> bytes:
                return self._body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        rss_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>MacBook Neo sells out for April as demand for Apple's $599 laptop outpaces supply</title>
            <link href="https://www.reddit.com/r/hardware/comments/live777/macbook_neo_sells_out/" />
            <updated>2026-04-17T00:08:00+00:00</updated>
            <content>Inventory remains available, but the 256GB pink model is moving fastest.</content>
          </entry>
          <entry>
            <title>Netflix earnings beat by $0.44, revenue topped estimates</title>
            <link href="https://www.reddit.com/r/stocks/comments/live888/netflix_earnings_beat/" />
            <updated>2026-04-17T00:09:00+00:00</updated>
            <content>Revenue topped estimates and guidance stayed resilient.</content>
          </entry>
        </feed>
        """

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0) -> FakeResponse:
            if "search.json" in request.full_url:
                return FakeResponse(json.dumps({"data": {"children": []}}))
            if request.full_url.endswith("/hot.rss"):
                return FakeResponse(rss_text)
            raise AssertionError(f"Unexpected URL opened: {request.full_url}")

        with patch("agent_reach_bridge_runtime.urllib.request.urlopen", side_effect=fake_urlopen):
            records = agent_reach_bridge_runtime.reddit_default_records(
                "",
                {
                    "analysis_time": datetime(2026, 4, 17, 0, 30, tzinfo=UTC),
                    "max_results_per_channel": 10,
                    "timeout_per_channel": 10,
                },
            )

        titles = [item["title"] for item in records]
        self.assertEqual(titles, ["Netflix earnings beat by $0.44, revenue topped estimates"])

    def test_bridge_x_can_fetch_queryless_news_feed_via_bird(self) -> None:
        captured_commands: list[list[str]] = []

        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            captured_commands.append(list(command))
            query = " ".join(command)
            if "chip" in query.lower():
                return {
                    "tweets": [
                        {
                            "text": "Chip packaging bottleneck is easing faster than expected.",
                            "url": "https://x.com/example/status/123",
                            "published_at": "2026-03-31T05:20:00+00:00",
                            "author_handle": "example",
                        }
                    ]
                }
            return {
                "tweets": [
                    {
                        "text": "Jet fuel shortage and shipping risk are back on the radar.",
                        "url": "https://x.com/example/status/456",
                        "published_at": "2026-03-31T05:25:00+00:00",
                        "author_handle": "macrodesk",
                    }
                ]
            }

        with (
            patch("agent_reach_bridge_runtime.has_twitter_credentials", return_value=True),
            patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess),
        ):
            result = run_agent_reach_bridge(
                {
                    "analysis_time": "2026-03-31T06:00:00+00:00",
                    "channels": ["x"],
                    "dedupe_store_path": str(self.temp_dir / "x-queryless-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["x"])
        self.assertTrue(captured_commands)
        self.assertGreater(len(captured_commands), 1)
        self.assertTrue(all("search" in cmd for cmd in captured_commands))
        self.assertTrue(any("chip" in " ".join(cmd).lower() for cmd in captured_commands))
        self.assertTrue(any("jet fuel" in " ".join(cmd).lower() or "hormuz" in " ".join(cmd).lower() for cmd in captured_commands))
        observation = result["retrieval_result"]["observations"][0]
        self.assertIn(observation["source_name"], {"X @example", "X @macrodesk"})

    def test_bridge_x_queryless_survives_single_query_timeout(self) -> None:
        captured_commands: list[list[str]] = []

        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            captured_commands.append(list(command))
            query = " ".join(command).lower()
            if "ai chips semiconductors" in query:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            if "robotaxi" in query:
                return {
                    "tweets": [
                        {
                            "text": "Tesla AI5 roadmap points straight at robotaxi inference scaling.",
                            "url": "https://x.com/example/status/789",
                            "published_at": "2026-03-31T05:28:00+00:00",
                            "author_handle": "robotaxiwatch",
                        }
                    ]
                }
            return {"tweets": []}

        with (
            patch("agent_reach_bridge_runtime.has_twitter_credentials", return_value=True),
            patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess),
        ):
            records = agent_reach_bridge_runtime.x_queryless_records(
                {
                    "timeout_per_channel": 30,
                    "max_results_per_channel": 10,
                }
            )

        self.assertGreaterEqual(len(captured_commands), 2)
        self.assertEqual(records[0]["author_handle"], "robotaxiwatch")
        self.assertIn("robotaxi inference scaling", records[0]["text"])

    def test_bridge_x_queryless_survives_single_query_fetch_error(self) -> None:
        captured_commands: list[list[str]] = []

        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            captured_commands.append(list(command))
            query = " ".join(command).lower()
            if "ai chips semiconductors" in query:
                raise RuntimeError("❌ Search failed: fetch failed")
            if "robotaxi" in query:
                return {
                    "tweets": [
                        {
                            "text": "Tesla AI5 roadmap points straight at robotaxi inference scaling.",
                            "url": "https://x.com/example/status/790",
                            "published_at": "2026-03-31T05:29:00+00:00",
                            "author_handle": "robotaxiwatch",
                        }
                    ]
                }
            return {"tweets": []}

        with patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess):
            records = agent_reach_bridge_runtime.x_queryless_records(
                {
                    "timeout_per_channel": 30,
                    "max_results_per_channel": 10,
                }
            )

        self.assertGreaterEqual(len(captured_commands), 2)
        self.assertEqual(records[0]["author_handle"], "robotaxiwatch")
        self.assertIn("robotaxi inference scaling", records[0]["text"])

    def test_bridge_x_queryless_skips_reply_tweets(self) -> None:
        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            query = " ".join(command).lower()
            if "robotaxi" in query:
                return {
                    "tweets": [
                        {
                            "text": "@elonmusk It's the Tesla Cybercab—the new autonomous robotaxi model.",
                            "url": "https://x.com/grok/status/2044940703688536400",
                            "published_at": "2026-04-17T00:47:11+00:00",
                            "author_handle": "grok",
                            "inReplyToStatusId": "2044940628354580969",
                        },
                        {
                            "text": "Tesla commits to a two-year HW roadmap aimed at unsupervised robotaxi deployment.",
                            "url": "https://x.com/example/status/2044446527100448899",
                            "published_at": "2026-04-17T00:30:00+00:00",
                            "author_handle": "robotaxiwatch",
                        },
                    ]
                }
            return {"tweets": []}

        with patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess):
            records = agent_reach_bridge_runtime.x_queryless_records(
                {
                    "timeout_per_channel": 30,
                    "max_results_per_channel": 10,
                }
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["author_handle"], "robotaxiwatch")
        self.assertNotIn("@elonmusk It's the Tesla Cybercab", records[0]["text"])

    def test_bridge_x_uses_config_tokens_for_queryless_trending(self) -> None:
        pseudo_home = self.temp_dir / "agent-reach-home"
        config_root = pseudo_home / ".agent-reach"
        config_root.mkdir(parents=True, exist_ok=True)
        (config_root / "config.yaml").write_text(
            "twitter_auth_token: auth-token-from-config\n"
            "twitter_ct0: ct0-from-config\n",
            encoding="utf-8",
        )
        captured: dict[str, object] = {}

        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            captured["command"] = list(command)
            captured["timeout"] = timeout_seconds
            captured["env"] = dict(extra_env or {})
            return {
                "tweets": [
                    {
                        "text": "A specific X trend worth tracking.",
                        "url": "https://x.com/example/status/456",
                        "published_at": "2026-03-31T05:25:00+00:00",
                        "author_handle": "example",
                    }
                ]
            }

        with patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess):
            result = run_agent_reach_bridge(
                {
                    "analysis_time": "2026-03-31T06:00:00+00:00",
                    "channels": ["x"],
                    "pseudo_home": str(pseudo_home),
                    "dedupe_store_path": str(self.temp_dir / "x-config-creds-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["x"])
        self.assertEqual(captured["env"], {"AUTH_TOKEN": "auth-token-from-config", "CT0": "ct0-from-config"})
        self.assertIn("search", captured["command"])

    def test_bridge_x_uses_bird_credentials_env_for_queryless_trending(self) -> None:
        pseudo_home = self.temp_dir / "agent-reach-home-env"
        bird_root = pseudo_home / ".config" / "bird"
        bird_root.mkdir(parents=True, exist_ok=True)
        (bird_root / "credentials.env").write_text(
            "AUTH_TOKEN=auth-token-from-env-file\nCT0=ct0-from-env-file\n",
            encoding="utf-8",
        )
        captured: dict[str, object] = {}

        def fake_run_channel_subprocess(command: list[str], timeout_seconds: int, extra_env: dict[str, str] | None = None) -> object:
            captured["command"] = list(command)
            captured["timeout"] = timeout_seconds
            captured["env"] = dict(extra_env or {})
            return {
                "tweets": [
                    {
                        "text": "Another specific X trend worth tracking.",
                        "url": "https://x.com/example/status/789",
                        "published_at": "2026-03-31T05:35:00+00:00",
                        "author_handle": "example",
                    }
                ]
            }

        with patch("agent_reach_bridge_runtime.run_channel_subprocess", side_effect=fake_run_channel_subprocess):
            result = run_agent_reach_bridge(
                {
                    "analysis_time": "2026-03-31T06:00:00+00:00",
                    "channels": ["x"],
                    "pseudo_home": str(pseudo_home),
                    "dedupe_store_path": str(self.temp_dir / "x-env-creds-dedupe.json"),
                }
            )

        self.assertEqual(result["channels_succeeded"], ["x"])
        self.assertEqual(captured["env"], {"AUTH_TOKEN": "auth-token-from-env-file", "CT0": "ct0-from-env-file"})
        self.assertIn("search", captured["command"])

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

    def test_bridge_channel_result_path_accepts_full_fetch_result_wrapper(self) -> None:
        wrapper_path = self.temp_dir / "x-wrapper-result.json"
        wrapper_path.write_text(
            json.dumps(
                {
                    "results_by_channel": {
                        "x": {
                            "channel": "x",
                            "status": "ok",
                            "reason": "",
                            "items": [
                                {
                                    "id": "2044948612782915717",
                                    "text": "Okay, something just shifted in how I think about AI agents.",
                                    "createdAt": "Fri Apr 17 01:18:37 +0000 2026",
                                    "author": {
                                        "username": "coo_pr_notes",
                                        "name": "Ken Startup COO & PR",
                                    },
                                }
                            ],
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_agent_reach_bridge(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "channels": ["x"],
                "channel_result_paths": {"x": str(wrapper_path)},
                "dedupe_store_path": str(self.temp_dir / "x-wrapper-dedupe.json"),
            }
        )

        self.assertEqual(result["channels_succeeded"], ["x"])
        self.assertEqual(result["import_summary"]["channel_counts"]["x"], 1)
        self.assertEqual(result["observations_imported"], 1)

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

    def test_bridge_reddit_normalizes_posts_payload_permalink_and_subreddit_name(self) -> None:
        result = run_agent_reach_bridge(
            {
                "topic": "NVIDIA Blackwell supplier checks",
                "analysis_time": "2026-03-31T06:00:00+00:00",
                "channels": ["reddit"],
                "channel_payloads": {
                    "reddit": {
                        "posts": [
                            {
                                "title": "NVIDIA Blackwell supplier checks",
                                "permalink": "/r/stocks/comments/abc123/nvidia_blackwell_supplier_checks/",
                                "subreddit": "stocks",
                                "selftext": "Retail investors are debating which memory suppliers benefit first.",
                                "score": 1820,
                                "num_comments": 410,
                                "created_utc": "2026-03-31T05:20:00+00:00",
                            }
                        ]
                    }
                },
                "dedupe_store_path": str(self.temp_dir / "reddit-dedupe.json"),
            }
        )

        self.assertEqual(result["channels_succeeded"], ["reddit"])
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["source_name"], "Reddit r/stocks")
        self.assertEqual(
            observation["url"],
            "https://www.reddit.com/r/stocks/comments/abc123/nvidia_blackwell_supplier_checks/",
        )
        self.assertEqual(observation["source_type"], "social")
        self.assertIn("Retail investors are debating", observation["text_excerpt"])
        self.assertEqual(observation["raw_metadata"]["subreddit"], "stocks")

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

    def test_hot_topic_discovery_can_rank_agent_reach_reddit_payload(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "NVIDIA Blackwell demand",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "NVIDIA Blackwell demand check",
                            "permalink": "/r/stocks/comments/xyz789/nvidia_blackwell_demand_check/",
                            "subreddit": "stocks",
                            "selftext": "The thread debates memory bottlenecks, supplier leverage, and timing.",
                            "score": 2450,
                            "num_comments": 620,
                            "upvote_ratio": 0.93,
                            "created_utc": "2026-03-31T04:40:00+00:00",
                        }
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertTrue(result["ranked_topics"])
        source_item = result["ranked_topics"][0]["source_items"][0]
        self.assertEqual(source_item["source_name"], "Reddit r/stocks")
        self.assertEqual(
            source_item["url"],
            "https://www.reddit.com/r/stocks/comments/xyz789/nvidia_blackwell_demand_check/",
        )
        self.assertEqual(source_item["source_type"], "social")
        self.assertIn("subreddit:r/stocks", source_item["tags"])
        self.assertIn("provider:agent-reach:reddit", source_item["tags"])
        self.assertGreater(source_item["heat_score"], 10000)

    def test_hot_topic_discovery_reddit_preserves_listing_window_and_velocity(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "TSMC CoWoS bottleneck",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "TSMC CoWoS bottleneck discussion",
                            "permalink": "/r/investing/comments/cowos123/tsmc_cowos_bottleneck_discussion/",
                            "subreddit": "investing",
                            "selftext": "The thread debates packaging constraints and AI demand spillover.",
                            "score": 860,
                            "num_comments": 220,
                            "upvote_ratio": 0.92,
                            "created_utc": "2026-03-31T04:20:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        }
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        source_item = result["ranked_topics"][0]["source_items"][0]
        self.assertEqual(source_item["reddit_listing"], "rising")
        self.assertEqual(source_item["reddit_listing_window"], "day")
        self.assertIn("listing:rising", source_item["tags"])
        self.assertIn("listing_window:day", source_item["tags"])
        self.assertTrue(any(tag.startswith("velocity:") for tag in source_item["tags"]))
        self.assertGreaterEqual(source_item["velocity_score"], 60)

    def test_hot_topic_discovery_reddit_can_use_top_comment_summary_as_context(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra debate",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra thread",
                            "permalink": "/r/stocks/comments/ai111/ai_infra_thread/",
                            "subreddit": "stocks",
                            "score": 520,
                            "num_comments": 160,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "top_comment_summary": "Top reply says hyperscaler capex discipline still matters more than meme flow.",
                            "top_comment_excerpt": "Hyperscaler capex discipline still matters more than meme flow.",
                            "top_comment_count": 2,
                        }
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        source_item = result["ranked_topics"][0]["source_items"][0]
        self.assertIn("Top reply says hyperscaler capex discipline", source_item["summary"])
        self.assertEqual(source_item["top_comment_count"], 2)
        self.assertTrue(any("reddit comments sampled 2" in reason for reason in result["ranked_topics"][0]["score_reasons"]))

    def test_hot_topic_discovery_reddit_surfaces_comment_operator_context(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra debate",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra thread",
                            "permalink": "/r/stocks/comments/aictx1/ai_infra_thread/",
                            "subreddit": "stocks",
                            "score": 540,
                            "num_comments": 160,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "top_comment_summary": "Top reply says hyperscaler capex discipline still matters more than meme flow.",
                            "top_comment_count": 2,
                            "top_comment_authors": ["u/cashflowlurker", "u/semicapbull"],
                            "top_comment_max_score": 130,
                            "comment_raw_count": 3,
                            "comment_duplicate_count": 1,
                            "comment_near_duplicate_count": 1,
                            "comment_near_duplicate_same_author_count": 0,
                            "comment_near_duplicate_cross_author_count": 1,
                            "comment_near_duplicate_level": "cross_author",
                            "comment_near_duplicate_examples": [
                                "cross_author:u/cashflowlurker -> u/semicapbull | Hyperscaler capex discipline still matters more than meme flow. || Hyperscaler capex discipline still matters more than meme enthusiasm."
                            ],
                            "comment_near_duplicate_example_count": 1,
                            "comment_declared_count": 160,
                            "comment_sample_coverage_ratio": 0.0125,
                            "comment_count_mismatch": True,
                        },
                        {
                            "title": "AI infra thread",
                            "permalink": "/r/SecurityAnalysis/comments/aictx2/ai_infra_thread/",
                            "subreddit": "SecurityAnalysis",
                            "score": 520,
                            "num_comments": 120,
                            "created_utc": "2026-03-31T04:11:00+00:00",
                            "top_comment_summary": "Second thread says packaging lead times still cap upside near term.",
                            "top_comment_count": 3,
                            "top_comment_authors": ["u/forensic-gaap"],
                            "top_comment_max_score": 145,
                            "comment_raw_count": 3,
                            "comment_duplicate_count": 0,
                            "comment_near_duplicate_count": 0,
                            "comment_near_duplicate_same_author_count": 0,
                            "comment_near_duplicate_cross_author_count": 0,
                            "comment_declared_count": 120,
                            "comment_sample_coverage_ratio": 0.025,
                            "comment_count_mismatch": True,
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        topic = result["ranked_topics"][0]
        source_item = topic["source_items"][0]
        self.assertIn("u/cashflowlurker", topic["top_comment_authors"])
        self.assertIn("u/forensic-gaap", topic["top_comment_authors"])
        self.assertEqual(topic["top_comment_author_count"], 3)
        self.assertEqual(topic["top_comment_max_score"], 145)
        self.assertEqual(topic["comment_raw_count"], 6)
        self.assertEqual(topic["comment_duplicate_count"], 1)
        self.assertEqual(topic["comment_near_duplicate_count"], 1)
        self.assertEqual(topic["comment_near_duplicate_cross_author_count"], 1)
        self.assertEqual(topic["comment_near_duplicate_same_author_count"], 0)
        self.assertEqual(topic["comment_near_duplicate_level"], "cross_author")
        self.assertEqual(topic["comment_near_duplicate_example_count"], 1)
        self.assertIn("cross_author:u/cashflowlurker -> u/semicapbull", topic["comment_near_duplicate_examples"][0])
        self.assertIn("cross_author:u/cashflowlurker -> u/semicapbull", source_item["comment_near_duplicate_examples"][0])
        self.assertEqual(topic["comment_count_mismatch_count"], 2)
        self.assertIn("deduped 1", topic["community_spread_summary"])
        self.assertIn("near-duplicate caution 1 (cross-author 1)", topic["community_spread_summary"])
        self.assertTrue(any("reddit deduped duplicate comments 1" in reason for reason in topic["score_reasons"]))
        self.assertTrue(any("reddit near-duplicate comment caution 1 (cross-author 1)" in reason for reason in topic["score_reasons"]))
        self.assertIn("partial comments 2", topic["community_spread_summary"])
        self.assertTrue(any("reddit partial comment samples 2" in reason for reason in topic["score_reasons"]))
        self.assertTrue(source_item["comment_count_mismatch"])
        self.assertGreater(source_item["comment_sample_coverage_ratio"], 0.0)
        source_operator_review = source_item["comment_operator_review"]
        source_operator_priority = source_item["operator_review_priority"]
        self.assertTrue(source_operator_review["review_required"])
        self.assertTrue(source_operator_review["has_partial_sample"])
        self.assertTrue(source_operator_review["has_exact_duplicates"])
        self.assertTrue(source_operator_review["has_near_duplicates"])
        self.assertEqual(source_operator_review["near_duplicate_level"], "cross_author")
        self.assertEqual(source_operator_review["comment_sample_coverage_ratio"], 0.0125)
        self.assertTrue(any("partial comment sample: 2/160" in caution for caution in source_operator_review["cautions"]))
        self.assertEqual(source_operator_priority["priority_level"], "high")
        self.assertTrue(source_operator_priority["review_required"])
        self.assertIn("cross_author_near_duplicates", source_operator_priority["reasons"])
        topic_operator_review = topic["comment_operator_review"]
        topic_operator_priority = topic["operator_review_priority"]
        self.assertTrue(topic_operator_review["review_required"])
        self.assertTrue(topic_operator_review["has_partial_sample"])
        self.assertTrue(topic_operator_review["has_exact_duplicates"])
        self.assertTrue(topic_operator_review["has_near_duplicates"])
        self.assertEqual(topic_operator_review["comment_count_mismatch_count"], 2)
        self.assertEqual(topic_operator_review["comment_sample_coverage_ratio_min"], 0.0125)
        self.assertEqual(topic_operator_review["comment_sample_coverage_ratio_max"], 0.025)
        self.assertIn("Top reply says hyperscaler capex discipline still matters more than meme flow", topic_operator_review["top_comment_summary"])
        self.assertIn("Second thread says packaging lead times still cap upside near term", topic_operator_review["top_comment_summary"])
        self.assertEqual(topic_operator_priority["priority_level"], "high")
        self.assertTrue(topic_operator_priority["review_required"])
        self.assertIn("multi_source_partial_sample", topic_operator_priority["reasons"])
        self.assertEqual(result["operator_review_queue"][0]["priority_level"], "high")
        self.assertEqual(result["operator_review_queue"][0]["title"], topic["title"])
        self.assertIn("## Reddit Operator Review", result["report_markdown"])
        self.assertIn("## Operator Queue", result["report_markdown"])
        self.assertIn("[high] AI infra thread", result["report_markdown"])
        self.assertIn("near-duplicate comments flagged: 1 (cross-author 1)", result["report_markdown"])

    def test_hot_topic_discovery_reddit_multi_subreddit_cluster_surfaces_spread(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "CoreWeave IPO readthrough",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "CoreWeave IPO readthrough",
                            "permalink": "/r/stocks/comments/core111/coreweave_ipo_readthrough/",
                            "subreddit": "stocks",
                            "selftext": "Retail investors are debating GPU lease economics and IPO optics.",
                            "score": 520,
                            "num_comments": 160,
                            "upvote_ratio": 0.89,
                            "created_utc": "2026-03-31T04:15:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "CoreWeave IPO readthrough",
                            "permalink": "/r/investing/comments/core222/coreweave_ipo_readthrough/",
                            "subreddit": "investing",
                            "selftext": "A parallel thread is debating whether the IPO resets AI infra comps.",
                            "score": 460,
                            "num_comments": 140,
                            "upvote_ratio": 0.90,
                            "created_utc": "2026-03-31T04:10:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        topic = result["ranked_topics"][0]
        self.assertEqual(topic["reddit_subreddit_count"], 2)
        self.assertIn("r/stocks", topic["reddit_subreddits"])
        self.assertIn("r/investing", topic["reddit_subreddits"])
        self.assertIn("hot", topic["reddit_listings"])
        self.assertIn("rising", topic["reddit_listings"])
        self.assertIn("2 subreddit(s)", topic["community_spread_summary"])
        self.assertTrue(any("reddit spread 2 subreddits" in reason for reason in topic["score_reasons"]))

    def test_hot_topic_discovery_reddit_surfaces_community_kind_mix_author_diversity_and_outbound_domain(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "NVIDIA supply chain",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "Blackwell suppliers look constrained again",
                            "author": "retailflow99",
                            "permalink": "/r/stocks/comments/nvda901/blackwell_suppliers_look_constrained_again/",
                            "subreddit": "stocks",
                            "url": "https://www.reuters.com/technology/nvidia-supply-chain-2026-03-31/",
                            "selftext": "Retail flow is debating supplier leverage after the Reuters link spread.",
                            "score": 640,
                            "num_comments": 180,
                            "upvote_ratio": 0.91,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "SecurityAnalysis thread on NVIDIA packaging bottlenecks",
                            "author": "forensic-gaap",
                            "permalink": "/r/SecurityAnalysis/comments/nvda902/securityanalysis_thread_on_nvidia_packaging_bottlenecks/",
                            "subreddit": "SecurityAnalysis",
                            "url": "https://www.reuters.com/technology/nvidia-supply-chain-2026-03-31/",
                            "selftext": "A deeper thread focuses on bottleneck persistence and supplier pass-through.",
                            "score": 590,
                            "num_comments": 120,
                            "upvote_ratio": 0.94,
                            "created_utc": "2026-03-31T04:09:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        topic = result["ranked_topics"][0]
        self.assertIn("broad_market", topic["reddit_subreddit_kinds"])
        self.assertIn("deep_research", topic["reddit_subreddit_kinds"])
        self.assertEqual(topic["reddit_subreddit_kind_count"], 2)
        self.assertEqual(topic["reddit_author_count"], 2)
        self.assertIn("u/retailflow99", topic["reddit_authors"])
        self.assertIn("u/forensic-gaap", topic["reddit_authors"])
        self.assertIn("www.reuters.com", topic["reddit_outbound_domains"])
        self.assertIn("signal broad_market, deep_research", topic["community_spread_summary"])
        self.assertIn("outbound www.reuters.com", topic["community_spread_summary"])
        self.assertTrue(any("reddit community mix broad_market, deep_research" in reason for reason in topic["score_reasons"]))

    def test_hot_topic_discovery_reddit_applies_low_signal_profile_weighting(self) -> None:
        high_signal = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra trade",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra trade setup",
                            "permalink": "/r/SecurityAnalysis/comments/sa100/ai_infra_trade_setup/",
                            "subreddit": "SecurityAnalysis",
                            "score": 600,
                            "num_comments": 140,
                            "upvote_ratio": 0.93,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ]
                },
            }
        )
        low_signal = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra trade",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra trade setup",
                            "permalink": "/r/wallstreetbets/comments/wsb100/ai_infra_trade_setup/",
                            "subreddit": "wallstreetbets",
                            "score": 600,
                            "num_comments": 140,
                            "upvote_ratio": 0.93,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ]
                },
            }
        )

        self.assertFalse(high_signal["errors"])
        self.assertFalse(low_signal["errors"])
        high_item = high_signal["ranked_topics"][0]["source_items"][0]
        low_item = low_signal["ranked_topics"][0]["source_items"][0]
        self.assertGreater(high_item["heat_score"], low_item["heat_score"])
        self.assertGreater(high_item["score_float"], low_item["score_float"])
        self.assertFalse(high_item["reddit_low_signal"])
        self.assertTrue(low_item["reddit_low_signal"])
        self.assertIn("subreddit_kind:deep_research", high_item["tags"])
        self.assertIn("subreddit_signal:low", low_item["tags"])
        self.assertTrue(any("reddit low-signal caution r/wallstreetbets" in reason for reason in low_signal["ranked_topics"][0]["score_reasons"]))

    def test_hot_topic_discovery_reddit_can_cluster_different_titles_by_same_outbound_url(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "NVIDIA supply chain",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "Blackwell suppliers look constrained again",
                            "permalink": "/r/stocks/comments/nvda111/blackwell_suppliers_look_constrained_again/",
                            "subreddit": "stocks",
                            "url": "https://www.reuters.com/technology/nvidia-supply-chain-2026-03-31/",
                            "selftext": "The post links a Reuters supply-chain piece and debates memory packaging limits.",
                            "score": 640,
                            "num_comments": 180,
                            "upvote_ratio": 0.91,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why Reddit thinks NVIDIA packaging bottlenecks are real",
                            "permalink": "/r/investing/comments/nvda222/why_reddit_thinks_nvidia_packaging_bottlenecks_are_real/",
                            "subreddit": "investing",
                            "url": "https://www.reuters.com/technology/nvidia-supply-chain-2026-03-31/",
                            "selftext": "Another subreddit is using the same Reuters link to argue about supplier leverage.",
                            "score": 590,
                            "num_comments": 165,
                            "upvote_ratio": 0.90,
                            "created_utc": "2026-03-31T04:12:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        topic = result["ranked_topics"][0]
        self.assertEqual(topic["source_count"], 2)
        self.assertEqual(topic["reddit_subreddit_count"], 2)
        self.assertTrue(all(item.get("outbound_url") == "https://www.reuters.com/technology/nvidia-supply-chain-2026-03-31/" for item in topic["source_items"]))

    def test_hot_topic_discovery_reddit_can_cluster_different_titles_by_topic_tokens(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "CoreWeave IPO",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "CoreWeave IPO resets GPU lessor comps",
                            "permalink": "/r/stocks/comments/core333/coreweave_ipo_resets_gpu_lessor_comps/",
                            "subreddit": "stocks",
                            "selftext": "The thread argues the IPO changes how investors value GPU lessors.",
                            "score": 430,
                            "num_comments": 120,
                            "upvote_ratio": 0.88,
                            "created_utc": "2026-03-31T04:08:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why the CoreWeave IPO could reprice GPU lessors",
                            "permalink": "/r/SecurityAnalysis/comments/core444/why_the_coreweave_ipo_could_reprice_gpu_lessors/",
                            "subreddit": "SecurityAnalysis",
                            "selftext": "A second thread debates whether the IPO reprices the whole GPU leasing peer set.",
                            "score": 390,
                            "num_comments": 105,
                            "upvote_ratio": 0.87,
                            "created_utc": "2026-03-31T04:04:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        topic = result["ranked_topics"][0]
        self.assertEqual(topic["source_count"], 2)
        self.assertIn("r/stocks", topic["reddit_subreddits"])
        self.assertIn("r/SecurityAnalysis", topic["reddit_subreddits"])
        self.assertTrue(any("reddit listings" in reason for reason in topic["score_reasons"]))

    def test_hot_topic_discovery_reddit_token_clustering_requires_query_alignment(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "CoreWeave IPO",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "GPU lessors still look underpriced after funding wave",
                            "permalink": "/r/stocks/comments/gpu111/gpu_lessors_still_look_underpriced_after_funding_wave/",
                            "subreddit": "stocks",
                            "selftext": "Retail investors argue GPU lessors may rerate after another funding wave.",
                            "score": 310,
                            "num_comments": 92,
                            "upvote_ratio": 0.84,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why GPU lessors may rerate after funding wave",
                            "permalink": "/r/investing/comments/gpu222/why_gpu_lessors_may_rerate_after_funding_wave/",
                            "subreddit": "investing",
                            "selftext": "A parallel thread makes the same GPU lessor and funding wave argument.",
                            "score": 285,
                            "num_comments": 88,
                            "upvote_ratio": 0.83,
                            "created_utc": "2026-03-31T04:12:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 2)
        self.assertTrue(all(topic["source_count"] == 1 for topic in result["ranked_topics"]))

    def test_hot_topic_discovery_reddit_can_cluster_complementary_query_coverage_with_normalized_tokens(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "NVIDIA supply chain",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "Blackwell suppliers look tighter again",
                            "permalink": "/r/stocks/comments/nvda333/blackwell_suppliers_look_tighter_again/",
                            "subreddit": "stocks",
                            "selftext": "Supply chain stress is spreading through advanced packaging capacity.",
                            "score": 360,
                            "num_comments": 96,
                            "upvote_ratio": 0.86,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why NVIDIA supplier bottlenecks keep showing up",
                            "permalink": "/r/investing/comments/nvda444/why_nvidia_supplier_bottlenecks_keep_showing_up/",
                            "subreddit": "investing",
                            "selftext": "Retail debate now centers on advanced packaging capacity again.",
                            "score": 340,
                            "num_comments": 90,
                            "upvote_ratio": 0.85,
                            "created_utc": "2026-03-31T04:10:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        topic = result["ranked_topics"][0]
        self.assertEqual(topic["source_count"], 2)
        self.assertEqual(topic["reddit_subreddit_count"], 2)

    def test_hot_topic_discovery_reddit_can_cluster_ticker_and_company_aliases(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "NVDA supply chain",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "NVDA packaging squeeze gets worse",
                            "permalink": "/r/stocks/comments/nvda555/nvda_packaging_squeeze_gets_worse/",
                            "subreddit": "stocks",
                            "selftext": "Retail thread watches foundry queues and packaging lead times.",
                            "score": 330,
                            "num_comments": 88,
                            "upvote_ratio": 0.85,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why NVIDIA bottlenecks still matter",
                            "permalink": "/r/investing/comments/nvda666/why_nvidia_bottlenecks_still_matter/",
                            "subreddit": "investing",
                            "selftext": "Another subreddit debates vendor bottlenecks and allocation risk.",
                            "score": 315,
                            "num_comments": 85,
                            "upvote_ratio": 0.84,
                            "created_utc": "2026-03-31T04:11:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        self.assertEqual(result["ranked_topics"][0]["source_count"], 2)

    def test_hot_topic_discovery_reddit_can_cluster_cross_language_aliases(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "TSMC CoWoS bottleneck",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "台积电 产能还是紧",
                            "permalink": "/r/stocks/comments/tsmc111/tsmc_capacity_still_tight/",
                            "subreddit": "stocks",
                            "selftext": "中文帖子讨论 CoWoS 排产和先进封装约束。",
                            "score": 300,
                            "num_comments": 80,
                            "upvote_ratio": 0.83,
                            "created_utc": "2026-03-31T04:16:00+00:00",
                            "listing": "hot",
                        },
                        {
                            "title": "Why TSMC packaging constraints still matter",
                            "permalink": "/r/investing/comments/tsmc222/why_tsmc_packaging_constraints_still_matter/",
                            "subreddit": "investing",
                            "selftext": "English thread debates advanced packaging lead times again.",
                            "score": 295,
                            "num_comments": 78,
                            "upvote_ratio": 0.82,
                            "created_utc": "2026-03-31T04:09:00+00:00",
                            "listing": "rising",
                            "time_filter": "day",
                        },
                    ]
                },
            }
        )

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        self.assertEqual(result["ranked_topics"][0]["source_count"], 2)

    def test_reddit_cluster_alias_config_is_parseable(self) -> None:
        payload = json.loads(
            (Path(__file__).resolve().parents[1] / "references" / "reddit-cluster-aliases.json").read_text(encoding="utf-8")
        )
        self.assertIn("ticker_alias_groups", payload)
        self.assertIn("company_alias_groups", payload)
        self.assertIn("cross_language_alias_groups", payload)
        self.assertIn({"nvidia", "nvda"}, [set(group) for group in payload["ticker_alias_groups"]])
        self.assertIn({"google", "alphabet"}, [set(group) for group in payload["company_alias_groups"]])
        self.assertIn({"tsmc", "台积电", "台積電"}, [set(group) for group in payload["cross_language_alias_groups"]])

        config_path = Path(__file__).resolve().parents[1] / "references" / "reddit-cluster-aliases.json"
        with patch.object(hot_topic_discovery_runtime, "REDDIT_CLUSTER_ALIAS_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()
            alias_groups = [set(group) for group in hot_topic_discovery_runtime.load_reddit_cluster_alias_groups()]
            self.assertIn({"google", "alphabet", "googl", "goog"}, alias_groups)
            self.assertIn({"tsmc", "台积电", "台積電"}, alias_groups)
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()

    def test_reddit_cluster_alias_loader_accepts_legacy_alias_groups(self) -> None:
        config_path = self.temp_dir / "reddit-cluster-aliases-legacy.json"
        config_path.write_text(
            json.dumps(
                {
                    "alias_groups": [
                        ["NVDA", "NVIDIA"],
                        ["TSMC", "台积电", "台積電"],
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with patch.object(hot_topic_discovery_runtime, "REDDIT_CLUSTER_ALIAS_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()
            alias_groups = [set(group) for group in hot_topic_discovery_runtime.load_reddit_cluster_alias_groups()]
            self.assertIn({"nvda", "nvidia"}, alias_groups)
            self.assertIn({"tsmc", "台积电", "台積電"}, alias_groups)
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()

    def test_reddit_cluster_alias_loader_falls_back_to_defaults_on_invalid_config(self) -> None:
        config_path = self.temp_dir / "reddit-cluster-aliases-invalid.json"
        config_path.write_text("{not valid json", encoding="utf-8")

        with patch.object(hot_topic_discovery_runtime, "REDDIT_CLUSTER_ALIAS_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()
            alias_groups = [set(group) for group in hot_topic_discovery_runtime.load_reddit_cluster_alias_groups()]
            self.assertIn({"nvidia", "nvda"}, alias_groups)
            self.assertIn({"tsmc", "台积电", "台積電"}, alias_groups)
            hot_topic_discovery_runtime.load_reddit_cluster_alias_groups.cache_clear()

    def test_reddit_community_profile_config_is_parseable(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "references" / "reddit-community-profiles.json"
        payload = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertIn("broad_market_subreddits", payload)
        self.assertIn("deep_research_subreddits", payload)
        self.assertIn("kind_score_multipliers", payload)
        self.assertIn("subreddit_score_overrides", payload)
        self.assertIn("low_signal_subreddits", payload)
        self.assertIn("r/stocks", payload["broad_market_subreddits"])
        self.assertIn("r/StockMarket", payload["broad_market_subreddits"])
        self.assertIn("r/SecurityAnalysis", payload["deep_research_subreddits"])
        self.assertIn("r/ValueInvesting", payload["deep_research_subreddits"])
        self.assertEqual(payload["kind_score_multipliers"]["deep_research"], 1.06)
        self.assertEqual(payload["subreddit_score_overrides"]["r/wallstreetbets"], 0.86)
        self.assertEqual(payload["subreddit_score_overrides"]["r/options"], 0.9)
        self.assertIn("r/wallstreetbets", payload["low_signal_subreddits"])
        self.assertIn("r/options", payload["low_signal_subreddits"])

        with patch.object(hot_topic_discovery_runtime, "REDDIT_COMMUNITY_PROFILE_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            kind_map = hot_topic_discovery_runtime.load_reddit_subreddit_kind_map()
            self.assertEqual(kind_map["r/stocks"], "broad_market")
            self.assertEqual(kind_map["r/stockmarket"], "broad_market")
            self.assertEqual(kind_map["r/securityanalysis"], "deep_research")
            self.assertEqual(kind_map["r/valueinvesting"], "deep_research")
            self.assertEqual(kind_map["r/options"], "speculative_flow")
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_kind_score_multipliers()["deep_research"], 1.06)
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides()["r/wallstreetbets"], 0.86)
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides()["r/options"], 0.9)
            self.assertIn("r/wallstreetbets", hot_topic_discovery_runtime.load_reddit_low_signal_subreddits())
            self.assertIn("r/options", hot_topic_discovery_runtime.load_reddit_low_signal_subreddits())
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()

    def test_hot_topic_discovery_reddit_applies_expanded_profile_buckets(self) -> None:
        high_signal = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra trade",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra trade setup",
                            "permalink": "/r/ValueInvesting/comments/vi100/ai_infra_trade_setup/",
                            "subreddit": "ValueInvesting",
                            "score": 600,
                            "num_comments": 140,
                            "upvote_ratio": 0.93,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ]
                },
            }
        )
        low_signal = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-31T05:00:00+00:00",
                "query": "AI infra trade",
                "sources": ["agent-reach:reddit"],
                "agent_reach_channel_payloads": {
                    "reddit": [
                        {
                            "title": "AI infra trade setup",
                            "permalink": "/r/options/comments/op100/ai_infra_trade_setup/",
                            "subreddit": "options",
                            "score": 600,
                            "num_comments": 140,
                            "upvote_ratio": 0.93,
                            "created_utc": "2026-03-31T04:18:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ]
                },
            }
        )

        self.assertFalse(high_signal["errors"])
        self.assertFalse(low_signal["errors"])
        high_item = high_signal["ranked_topics"][0]["source_items"][0]
        low_item = low_signal["ranked_topics"][0]["source_items"][0]
        self.assertEqual(high_item["reddit_subreddit_kind"], "deep_research")
        self.assertEqual(low_item["reddit_subreddit_kind"], "speculative_flow")
        self.assertFalse(high_item["reddit_low_signal"])
        self.assertTrue(low_item["reddit_low_signal"])
        self.assertGreater(high_item["score_float"], low_item["score_float"])
        self.assertIn("subreddit_kind:deep_research", high_item["tags"])
        self.assertIn("subreddit_signal:low", low_item["tags"])

    def test_reddit_community_profile_loader_falls_back_to_defaults_on_invalid_config(self) -> None:
        config_path = self.temp_dir / "reddit-community-profiles-invalid.json"
        config_path.write_text("{not valid json", encoding="utf-8")

        with patch.object(hot_topic_discovery_runtime, "REDDIT_COMMUNITY_PROFILE_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            kind_map = hot_topic_discovery_runtime.load_reddit_subreddit_kind_map()
            self.assertEqual(kind_map["r/stocks"], "broad_market")
            self.assertEqual(kind_map["r/securityanalysis"], "deep_research")
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_kind_score_multipliers()["deep_research"], 1.06)
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides()["r/wallstreetbets"], 0.86)
            self.assertIn("r/wallstreetbets", hot_topic_discovery_runtime.load_reddit_low_signal_subreddits())
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()

    def test_reddit_community_profile_loader_accepts_legacy_group_map(self) -> None:
        config_path = self.temp_dir / "reddit-community-profiles-legacy.json"
        config_path.write_text(
            json.dumps(
                {
                    "subreddit_kind_groups": {
                        "broad_market": ["r/stocks", "r/investing"],
                        "deep_research": ["r/SecurityAnalysis"],
                    },
                    "kind_score_multipliers": {"deep_research": 1.08},
                    "subreddit_score_overrides": {"r/wallstreetbets": 0.85},
                    "low_signal_subreddits": ["r/wallstreetbets"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with patch.object(hot_topic_discovery_runtime, "REDDIT_COMMUNITY_PROFILE_PATH", config_path):
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            kind_map = hot_topic_discovery_runtime.load_reddit_subreddit_kind_map()
            self.assertEqual(kind_map["r/stocks"], "broad_market")
            self.assertEqual(kind_map["r/securityanalysis"], "deep_research")
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_kind_score_multipliers()["deep_research"], 1.08)
            self.assertEqual(hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides()["r/wallstreetbets"], 0.85)
            self.assertIn("r/wallstreetbets", hot_topic_discovery_runtime.load_reddit_low_signal_subreddits())
            hot_topic_discovery_runtime.load_reddit_low_signal_subreddits.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_score_overrides.cache_clear()
            hot_topic_discovery_runtime.load_reddit_kind_score_multipliers.cache_clear()
            hot_topic_discovery_runtime.load_reddit_subreddit_kind_map.cache_clear()
            hot_topic_discovery_runtime.load_reddit_community_profile_payload.cache_clear()

    def test_hot_topic_discovery_reddit_realistic_multi_post_fixture_clusters_stably(self) -> None:
        request = json.loads((FIXTURES_ROOT / "reddit-hot-topic" / "reddit-multi-post-request.json").read_text(encoding="utf-8"))
        result = run_hot_topic_discovery(request)

        self.assertFalse(result["errors"])
        self.assertEqual(len(result["ranked_topics"]), 3)
        source_counts = sorted((topic["source_count"] for topic in result["ranked_topics"]), reverse=True)
        self.assertEqual(source_counts, [3, 2, 1])

        first_cluster = next(topic for topic in result["ranked_topics"] if topic["source_count"] == 3)
        self.assertEqual(first_cluster["reddit_subreddit_count"], 3)
        self.assertIn("r/stocks", first_cluster["reddit_subreddits"])
        self.assertIn("r/investing", first_cluster["reddit_subreddits"])
        self.assertIn("r/SecurityAnalysis", first_cluster["reddit_subreddits"])
        self.assertTrue(any("reddit spread 3 subreddits" in reason for reason in first_cluster["score_reasons"]))

        second_cluster = next(topic for topic in result["ranked_topics"] if topic["source_count"] == 2)
        self.assertEqual(second_cluster["reddit_subreddit_count"], 2)
        self.assertIn("r/stocks", second_cluster["reddit_subreddits"])
        self.assertIn("r/investing", second_cluster["reddit_subreddits"])

        standalone_topic = next(topic for topic in result["ranked_topics"] if topic["source_count"] == 1)
        self.assertEqual(standalone_topic["title"], "Broadcom custom silicon upside check")

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
            "hot_topic_discovery_runtime.py",
            "reddit_bridge_runtime.py",
            "reddit_bridge.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
