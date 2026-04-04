#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from opencli_bridge_runtime import prepare_opencli_bridge, run_opencli_bridge


class OpenCliBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-opencli-bridge"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bridge_imports_opencli_items_with_shadow_defaults_and_preserves_blocked_rows(self) -> None:
        screenshot_path = self.temp_dir / "note.png"
        screenshot_path.write_bytes(b"png")
        result = run_opencli_bridge(
            {
                "topic": "China aluminum broker note check",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "questions": ["What changed in the latest broker note?"],
                "claims": [
                    {
                        "claim_id": "driver-state-known",
                        "claim_text": "The latest external driver can be described with an exact date.",
                    }
                ],
                "opencli": {
                    "site_profile": "broker-research-portal",
                    "result": {
                        "items": [
                            {
                                "title": "China Aluminum Daily Note",
                                "url": "https://research.example.com/china-aluminum-note",
                                "published_at": "2026-04-03T07:15:00+00:00",
                                "captured_at": "2026-04-03T07:20:00+00:00",
                                "summary": "A broker note says aluminum demand expectations improved.",
                                "claim_ids": ["driver-state-known"],
                                "claim_states": {"driver-state-known": "support"},
                                "artifact_manifest": [
                                    {
                                        "role": "page_screenshot",
                                        "path": str(screenshot_path),
                                        "source_url": "https://research.example.com/china-aluminum-note",
                                        "media_type": "image/png",
                                    }
                                ],
                            },
                            {
                                "title": "Portal login wall",
                                "url": "https://research.example.com/login",
                                "captured_at": "2026-04-03T07:21:00+00:00",
                                "status": "login_required",
                                "blocked_reason": "session expired",
                            },
                        ]
                    },
                },
            }
        )

        observations = result["retrieval_result"]["observations"]
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 2)
        self.assertEqual(result["import_summary"]["artifact_count"], 1)

        note = next(item for item in observations if item.get("url") == "https://research.example.com/china-aluminum-note")
        blocked = next(item for item in observations if item.get("url") == "https://research.example.com/login")

        self.assertEqual(note["origin"], "opencli")
        self.assertEqual(note["channel"], "shadow")
        self.assertEqual(note["access_mode"], "browser_session")
        self.assertEqual(note["source_type"], "research_note")
        self.assertEqual(blocked["access_mode"], "blocked")
        self.assertEqual(blocked["channel"], "background")
        self.assertEqual(
            blocked["raw_metadata"]["opencli"]["blocked_reason"],
            "session expired",
        )

    def test_bridge_can_load_result_path_with_trailing_text_noise(self) -> None:
        result_path = self.temp_dir / "opencli-output.txt"
        result_path.write_text(
            '{"items":[{"title":"Portal note","url":"https://research.example.com/note-1","captured_at":"2026-04-03T07:20:00+00:00","summary":"Imported from result path."}]}\nOPENCLI LOG TRAILER\n',
            encoding="utf-8",
        )

        result = run_opencli_bridge(
            {
                "topic": "OpenCLI file import",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "driver-state-known",
                        "claim_text": "The latest external driver can be described with an exact date.",
                    }
                ],
                "opencli": {
                    "site_profile": "broker-research-portal",
                    "result_path": str(result_path),
                },
            }
        )

        self.assertEqual(result["import_summary"]["payload_source"], "result_path")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertIn(str(result_path.resolve()), result["report_markdown"])

    def test_bridge_rejects_native_x_and_wechat_routes(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not support X or WeChat routes"):
            run_opencli_bridge(
                {
                    "topic": "X route should not go through OpenCLI",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "opencli": {
                        "site_profile": "x",
                        "result": {
                            "items": [
                                {
                                    "title": "X post",
                                    "url": "https://x.com/example/status/123",
                                    "summary": "This should be rejected.",
                                }
                            ]
                        },
                    },
                }
            )

    def test_bridge_falls_back_to_observed_at_when_policy_allows_missing_publication_time(self) -> None:
        result = run_opencli_bridge(
            {
                "topic": "Observed-at fallback check",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "driver-state-known",
                        "claim_text": "The latest external driver can be described with an exact date.",
                    }
                ],
                "opencli": {
                    "site_profile": "broker-research-portal",
                    "result": {
                        "items": [
                            {
                                "title": "Untimestamped portal note",
                                "url": "https://research.example.com/untimestamped-note",
                                "captured_at": "2026-04-03T07:20:00+00:00",
                                "summary": "No publication time was exposed on the page.",
                            }
                        ]
                    },
                },
            }
        )

        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["published_at"], "2026-04-03T07:20:00+00:00")
        self.assertEqual(observation["observed_at"], "2026-04-03T07:20:00+00:00")
        self.assertEqual(
            observation["raw_metadata"]["opencli"]["timestamp_fallback"],
            "observed_at",
        )
        self.assertEqual(result["import_summary"]["timestamp_fallback_count"], 1)

    def test_bridge_dedupes_duplicate_items_and_preserves_richer_artifacts(self) -> None:
        screenshot_path = self.temp_dir / "duplicate-note.png"
        screenshot_path.write_bytes(b"png")

        result = run_opencli_bridge(
            {
                "topic": "Duplicate OpenCLI rows",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "driver-state-known",
                        "claim_text": "The latest external driver can be described with an exact date.",
                    }
                ],
                "opencli": {
                    "site_profile": "broker-research-portal",
                    "result": {
                        "items": [
                            {
                                "title": "China Aluminum Daily Note",
                                "url": "https://research.example.com/china-aluminum-note",
                                "published_at": "2026-04-03T07:15:00+00:00",
                                "captured_at": "2026-04-03T07:20:00+00:00",
                                "summary": "Short summary.",
                                "claim_ids": ["driver-state-known"],
                            },
                            {
                                "title": "China Aluminum Daily Note",
                                "url": "https://research.example.com/china-aluminum-note",
                                "published_at": "2026-04-03T07:15:00+00:00",
                                "captured_at": "2026-04-03T07:20:00+00:00",
                                "summary": "A longer summary that should win when duplicate rows are merged together.",
                                "claim_ids": ["driver-state-known"],
                                "artifact_manifest": [
                                    {
                                        "role": "page_screenshot",
                                        "path": str(screenshot_path),
                                        "source_url": "https://research.example.com/china-aluminum-note",
                                        "media_type": "image/png",
                                    }
                                ],
                            },
                        ]
                    },
                },
            }
        )

        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(result["import_summary"]["skipped_duplicate_count"], 1)
        observation = result["retrieval_result"]["observations"][0]
        self.assertIn("longer summary", observation["text_excerpt"])
        self.assertEqual(len(observation["artifact_manifest"]), 1)

    def test_bridge_skips_items_missing_both_url_and_explicit_text(self) -> None:
        result = run_opencli_bridge(
            {
                "topic": "Malformed OpenCLI item",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "driver-state-known",
                        "claim_text": "The latest external driver can be described with an exact date.",
                    }
                ],
                "opencli": {
                    "site_profile": "generic-dynamic-page",
                    "result": {
                        "items": [
                            {
                                "title": "Label only row"
                            }
                        ]
                    },
                },
            }
        )

        self.assertEqual(result["import_summary"]["imported_candidate_count"], 0)
        self.assertEqual(result["import_summary"]["skipped_invalid_count"], 1)

    def test_prepare_bridge_can_reuse_preloaded_payload_without_running_news_index(self) -> None:
        raw_payload = {
            "topic": "Preloaded OpenCLI import",
            "analysis_time": "2026-04-03T08:00:00+00:00",
            "claims": [
                {
                    "claim_id": "driver-state-known",
                    "claim_text": "The latest external driver can be described with an exact date.",
                }
            ],
            "opencli": {
                "site_profile": "broker-research-portal",
            },
        }
        preloaded_payload = {
            "items": [
                {
                    "title": "Preloaded portal note",
                    "url": "https://research.example.com/preloaded-note",
                    "captured_at": "2026-04-03T07:20:00+00:00",
                    "summary": "Imported from a reused OpenCLI capture.",
                }
            ]
        }

        with patch("opencli_bridge_runtime.run_news_index", side_effect=AssertionError("prepare_opencli_bridge should not run news_index")):
            result = prepare_opencli_bridge(
                raw_payload,
                preloaded_payload=preloaded_payload,
                payload_source_override="command_result_path",
                result_path_override="C:\\path\\to\\opencli-result.json",
                runner_summary_override={"status": "ok", "mode": "command"},
            )

        self.assertEqual(result["import_summary"]["payload_source"], "command_result_path")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(result["runner_summary"]["status"], "ok")
        self.assertNotIn("retrieval_result", result)
        self.assertEqual(result["retrieval_request"]["candidates"][0]["url"], "https://research.example.com/preloaded-note")
        self.assertIn("OpenCLI runner completed successfully before import.", result["report_markdown"])

    def test_bridge_can_run_command_mode_from_result_path_and_report_runner_summary(self) -> None:
        result_path = self.temp_dir / "opencli-command-output.json"
        artifact_root = self.temp_dir / "artifacts"
        result_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "title": "Portal note from command",
                            "url": "https://research.example.com/command-note",
                            "captured_at": "2026-04-03T07:20:00+00:00",
                            "summary": "Imported after mocked command execution.",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "opencli_bridge_runtime.subprocess.run",
            return_value=subprocess.CompletedProcess(
                ["opencli", "capture"],
                0,
                stdout="capture complete",
                stderr="",
            ),
        ):
            result = run_opencli_bridge(
                {
                    "topic": "Command mode import",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "The latest external driver can be described with an exact date.",
                        }
                    ],
                    "opencli": {
                        "input_mode": "command",
                        "command": ["opencli", "capture"],
                        "result_path": str(result_path),
                        "artifact_root": str(artifact_root),
                        "timeout_seconds": 15,
                    },
                }
            )

        self.assertEqual(result["import_summary"]["payload_source"], "command_result_path")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(result["runner_summary"]["status"], "ok")
        self.assertEqual(result["runner_summary"]["payload_source"], "command_result_path")
        self.assertEqual(result["runner_summary"]["artifact_root"], str(artifact_root.resolve()))
        self.assertIn(str(result_path.resolve()), result["report_markdown"])

    def test_bridge_surfaces_command_timeout_without_false_success(self) -> None:
        with patch(
            "opencli_bridge_runtime.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["opencli", "capture"], timeout=9),
        ):
            result = run_opencli_bridge(
                {
                    "topic": "Command timeout",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "The latest external driver can be described with an exact date.",
                        }
                    ],
                    "opencli": {
                        "input_mode": "command",
                        "command": ["opencli", "capture"],
                        "timeout_seconds": 9,
                    },
                }
            )

        self.assertEqual(result["import_summary"]["imported_candidate_count"], 0)
        self.assertEqual(result["runner_summary"]["status"], "failed_capture")
        self.assertTrue(result["runner_summary"]["timed_out"])
        self.assertEqual(result["retrieval_result"]["observations"], [])

    def test_bridge_surfaces_command_parse_errors_cleanly(self) -> None:
        with patch(
            "opencli_bridge_runtime.subprocess.run",
            return_value=subprocess.CompletedProcess(
                ["opencli", "capture"],
                0,
                stdout="not json",
                stderr="",
            ),
        ):
            result = run_opencli_bridge(
                {
                    "topic": "Command parse failure",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "The latest external driver can be described with an exact date.",
                        }
                    ],
                    "opencli": {
                        "input_mode": "command",
                        "command": ["opencli", "capture"],
                    },
                }
            )

        self.assertEqual(result["import_summary"]["imported_candidate_count"], 0)
        self.assertEqual(result["runner_summary"]["status"], "parse_error")
        self.assertEqual(result["retrieval_result"]["observations"], [])


if __name__ == "__main__":
    unittest.main()
