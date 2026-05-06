#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "financial-analysis"
    / "skills"
    / "autoresearch-info-index"
    / "scripts"
    / "x_index_runtime.py"
)
SCRIPT_DIR = MODULE_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("x_index_runtime", MODULE_PATH)
module_under_test = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["x_index_runtime"] = module_under_test
SPEC.loader.exec_module(module_under_test)


class XIndexRuntimeTests(unittest.TestCase):
    def test_run_x_index_returns_partial_when_retrieval_bridge_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "commercial space",
                "analysis_time": "2026-05-01T20:30:00+08:00",
                "manual_urls": ["https://x.com/Test/status/123"],
                "output_dir": temp_dir,
            }
            x_post = {
                "post_url": "https://x.com/Test/status/123",
                "author_handle": "Test",
                "posted_at": "2026-05-01T12:00:00+00:00",
                "collected_at": "2026-05-01T12:01:00+00:00",
                "post_text_raw": "commercial space test post",
                "post_summary": "commercial space test post",
                "media_summary": "",
                "combined_summary": "commercial space test post",
                "artifact_manifest": [],
                "claim_candidates": [],
                "best_images": [],
                "thread_posts": [],
                "media_items": [],
                "engagement": {},
                "session_health": "effective",
                "session_source": "remote_debugging",
                "session_status": "ready",
                "access_mode": "browser_session",
                "discovery_reason": "manual_url",
                "crawl_notes": [],
                "post_text_source": "dom",
                "post_text_confidence": 0.9,
                "root_post_screenshot_path": "",
            }

            with patch.object(
                module_under_test,
                "collect_candidates",
                return_value=[{"post_url": "https://x.com/Test/status/123"}],
            ), patch.object(
                module_under_test,
                "build_x_post_record",
                return_value=x_post,
            ), patch.object(
                module_under_test,
                "run_news_index",
                side_effect=RuntimeError("bridge failed"),
            ):
                result = module_under_test.run_x_index(request)

            result_path = pathlib.Path(temp_dir) / "x-index-result.json"
            report_path = pathlib.Path(temp_dir) / "x-index-report.md"
            self.assertTrue(result_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["status"], "partial")
            self.assertIn("degraded repo-native X run", report_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["partial_stage"], "retrieval_bridge")
        self.assertEqual(len(result["x_posts"]), 1)
        self.assertIn("bridge failed", result["fatal_error"])
        self.assertEqual(result["run_completeness"]["status"], "partial")
        self.assertEqual(result["run_completeness"]["report_status"], "complete")

    def test_build_markdown_report_discloses_partial_degraded_status(self) -> None:
        report = module_under_test.build_markdown_report(
            {
                "request": {
                    "topic": "commercial space",
                    "analysis_time": "2026-05-01T20:30:00+08:00",
                },
                "status": "partial",
                "partial_stage": "retrieval_bridge",
                "fatal_error": "bridge failed",
                "run_completeness": {
                    "status": "partial",
                    "candidates_collected": 1,
                    "x_posts_captured": 1,
                    "blocked_candidates_count": 0,
                    "retrieval_bridge_status": "failed",
                    "report_status": "partial",
                },
                "session_bootstrap": {"strategy": "remote_debugging", "status": "ready"},
                "x_posts": [
                    {
                        "author_handle": "Test",
                        "post_url": "https://x.com/Test/status/123",
                        "combined_summary": "commercial space test post",
                    }
                ],
            }
        )

        self.assertIn("Run completeness: partial", report)
        self.assertIn("Partial stage: retrieval_bridge", report)
        self.assertIn("degraded repo-native X run", report)

    def test_run_x_index_blocks_degraded_unusable_posts_before_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "commercial space",
                "analysis_time": "2026-05-01T20:30:00+08:00",
                "keywords": ["launch"],
                "phrase_clues": ["satellite launch delay"],
                "entity_clues": ["SPACE"],
                "manual_urls": ["https://x.com/Noise/status/999"],
                "output_dir": temp_dir,
            }
            degraded_post = {
                "post_url": "https://x.com/Noise/status/999",
                "author_handle": "Noise",
                "posted_at": "2026-05-01T12:00:00+00:00",
                "collected_at": "2026-05-01T12:01:00+00:00",
                "post_text_raw": "",
                "post_summary": "",
                "media_summary": "",
                "combined_summary": "",
                "artifact_manifest": [],
                "thread_posts": [],
                "media_items": [],
                "engagement": {},
                "session_health": "degraded",
                "session_source": "remote_debugging",
                "session_status": "failed",
                "access_mode": "blocked",
                "discovery_reason": "manual_url",
                "crawl_notes": ["page appeared blocked during browser extraction"],
                "post_text_source": "unavailable",
                "post_text_confidence": 0.0,
                "root_post_screenshot_path": "",
            }

            with patch.object(
                module_under_test,
                "collect_candidates",
                return_value=[{"post_url": "https://x.com/Noise/status/999"}],
            ), patch.object(
                module_under_test,
                "build_x_post_record",
                return_value=degraded_post,
            ), patch.object(
                module_under_test,
                "run_news_index",
                return_value={"status": "skipped"},
            ):
                result = module_under_test.run_x_index(request)

        self.assertEqual(result["x_posts"], [])
        self.assertEqual(len(result["discovery_summary"]["blocked_candidates"]), 1)
        self.assertEqual(
            result["discovery_summary"]["blocked_candidates"][0]["block_reason"],
            "blocked_or_unusable_post",
        )
        self.assertNotIn("@Noise", result["report_markdown"])

    def test_x_index_wrapper_writes_partial_outputs_and_exits_nonzero(self) -> None:
        cli_path = SCRIPT_DIR / "x_index.py"
        cli_spec = importlib.util.spec_from_file_location("x_index_cli_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            output_path = temp_path / "result.json"
            markdown_path = temp_path / "report.md"
            input_path.write_text("{}", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "x_index.py",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--markdown-output",
                    str(markdown_path),
                    "--quiet",
                ],
            ), patch.object(
                cli_module,
                "run_x_index",
                return_value={
                    "status": "partial",
                    "report_markdown": "# Partial Report\n",
                    "request": {"output_dir": temp_dir},
                },
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

            self.assertNotEqual(exit_context.exception.code, 0)
            self.assertTrue(output_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["status"], "partial")
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Partial Report\n")

    def test_discover_search_candidates_prefers_live_x_search_results_when_remote_debugging_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = module_under_test.parse_request(
                {
                    "topic": "commercial space",
                    "analysis_time": "2026-04-20T20:30:00+08:00",
                    "query_overrides": ["commercial space satellite launch"],
                    "output_dir": temp_dir,
                    "browser_session": {
                        "strategy": "remote_debugging",
                        "cdp_endpoint": "http://127.0.0.1:9222",
                        "required": True,
                    },
                }
            )
            session_context = {
                "strategy": "remote_debugging",
                "active": True,
                "source": "remote_debugging",
            }

            with patch.object(
                module_under_test,
                "maybe_fetch_x_search_results",
                return_value=[
                    "https://x.com/SpaceIntel101/status/2001",
                    "https://x.com/LaunchClock/status/2002",
                ],
            ) as live_mock, patch.object(
                module_under_test,
                "maybe_fetch_search_results",
                return_value=[],
            ) as public_mock:
                discovered = module_under_test.discover_search_candidates(request, session_context)

        self.assertGreaterEqual(len(discovered), 2)
        self.assertEqual(discovered[0]["post_url"], "https://x.com/SpaceIntel101/status/2001")
        self.assertTrue(discovered[0]["discovery_reason"].startswith("x_live_search:"))
        self.assertEqual(discovered[0]["session_source"], "remote_debugging")
        live_mock.assert_called()
        public_mock.assert_called()

    def test_discover_search_candidates_falls_back_to_public_search_when_live_x_search_finds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = module_under_test.parse_request(
                {
                    "topic": "commercial space",
                    "analysis_time": "2026-04-20T20:30:00+08:00",
                    "query_overrides": ["commercial space satellite launch"],
                    "output_dir": temp_dir,
                    "browser_session": {
                        "strategy": "remote_debugging",
                        "cdp_endpoint": "http://127.0.0.1:9222",
                        "required": True,
                    },
                }
            )
            session_context = {
                "strategy": "remote_debugging",
                "active": True,
                "source": "remote_debugging",
            }

            with patch.object(
                module_under_test,
                "maybe_fetch_x_search_results",
                return_value=[],
            ), patch.object(
                module_under_test,
                "maybe_fetch_search_results",
                return_value=["https://x.com/PublicSearch/status/3001"],
            ):
                discovered = module_under_test.discover_search_candidates(request, session_context)

        self.assertEqual(discovered[0]["post_url"], "https://x.com/PublicSearch/status/3001")
        self.assertEqual(discovered[0]["discovery_reason"], "query_override")

    def test_discover_search_candidates_marks_trusted_rumor_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = module_under_test.parse_request(
                {
                    "topic": "AI compute utilization",
                    "analysis_time": "2026-05-06T20:30:00+08:00",
                    "keywords": ["token cost"],
                    "trusted_rumor_accounts": [
                        {
                            "handle": "dmjk001",
                            "domains": ["ai_compute", "semiconductors"],
                            "confidence": "high",
                            "historical_hit_rate": "high",
                        }
                    ],
                    "output_dir": temp_dir,
                }
            )

            with patch.object(
                module_under_test,
                "maybe_fetch_search_results",
                return_value=["https://x.com/dmjk001/status/2051886835606097938"],
            ):
                discovered = module_under_test.discover_search_candidates(request)

        self.assertEqual(discovered[0]["post_url"], "https://x.com/dmjk001/status/2051886835606097938")
        self.assertEqual(discovered[0]["source_lane"], "trusted_rumor")
        self.assertEqual(discovered[0]["rumor_status"], "rumor_high_confidence")
        self.assertEqual(discovered[0]["trusted_source"]["handle"], "dmjk001")
        self.assertIn("ai_compute", discovered[0]["trusted_source"]["domains"])
        self.assertTrue(discovered[0]["discovery_reason"].startswith("trusted_rumor_"))

    def test_run_x_index_surfaces_trusted_rumor_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI token economics",
                "analysis_time": "2026-05-06T20:30:00+08:00",
                "keywords": ["token cost"],
                "trusted_rumor_accounts": [{"handle": "dmjk001", "domains": ["ai_compute"], "confidence": "high"}],
                "manual_urls": ["https://x.com/dmjk001/status/2051886835606097938"],
                "output_dir": temp_dir,
            }
            x_post = {
                "post_url": "https://x.com/dmjk001/status/2051886835606097938",
                "author_handle": "dmjk001",
                "posted_at": "2026-05-06T12:00:00+00:00",
                "collected_at": "2026-05-06T12:01:00+00:00",
                "post_text_raw": "AI token cost and inference demand are moving faster than capex headlines.",
                "post_summary": "Trusted early signal on AI token economics.",
                "media_summary": "",
                "combined_summary": "Trusted early signal on AI token economics.",
                "artifact_manifest": [],
                "claim_candidates": [],
                "best_images": [],
                "thread_posts": [],
                "media_items": [],
                "engagement": {"likes": 1800, "reposts": 900, "replies": 120},
                "session_health": "effective",
                "session_source": "remote_debugging",
                "session_status": "ready",
                "access_mode": "browser_session",
                "discovery_reason": "trusted_rumor_keyword:@dmjk001|keyword:token cost",
                "source_lane": "trusted_rumor",
                "rumor_status": "rumor_high_confidence",
                "trusted_source": {"handle": "dmjk001", "domains": ["ai_compute"], "confidence": "high"},
                "crawl_notes": [],
                "post_text_source": "dom",
                "post_text_confidence": 0.9,
                "root_post_screenshot_path": "",
            }

            with patch.object(
                module_under_test,
                "collect_candidates",
                return_value=[{"post_url": "https://x.com/dmjk001/status/2051886835606097938"}],
            ), patch.object(
                module_under_test,
                "build_x_post_record",
                return_value=x_post,
            ), patch.object(
                module_under_test,
                "run_news_index",
                return_value={"status": "skipped"},
            ):
                result = module_under_test.run_x_index(request)

        trusted_items = result["evidence_pack"]["trusted_rumor_items"]
        self.assertEqual(len(trusted_items), 1)
        self.assertEqual(trusted_items[0]["rumor_status"], "rumor_high_confidence")
        self.assertEqual(trusted_items[0]["author_handle"], "dmjk001")
        self.assertIn("## Trusted Rumor Lane", result["report_markdown"])

    def test_extract_status_urls_from_blob_dedupes_multiple_sources(self) -> None:
        urls = module_under_test.extract_status_urls_from_blob(
            "https://x.com/A/status/1 https://x.com/A/status/1",
            "<a href='https://x.com/B/status/2'>link</a>",
            "https://x.com/C/status/3",
        )
        self.assertEqual(
            urls,
            [
                "https://x.com/A/status/1",
                "https://x.com/B/status/2",
                "https://x.com/C/status/3",
            ],
        )


if __name__ == "__main__":
    unittest.main()
