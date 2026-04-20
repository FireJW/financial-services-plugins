#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
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
