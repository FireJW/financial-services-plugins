#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "china-portal-adapter"
    / "skills"
    / "china-portal-match-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from china_portal_match_bridge_runtime import run_china_portal_match_bridge


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "china-portal-adapter"
PROFILE_DIR = Path(__file__).resolve().parent / "fixtures" / "career-ops-local" / "private-root" / "profile"


class ChinaPortalMatchBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / ".tmp-china-portal-match-bridge-tests"
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def request(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "adapter_request": {
                "task": "scan_jobs",
                "platforms": ["boss", "liepin"],
                "keywords": ["ai", "platform"],
                "cities": ["Shanghai"],
                "salary_filters": {"minimum_monthly_rmb": 30000},
                "blacklist_companies": [],
                "blacklist_recruiters": [],
                "session_mode": "existing_local_only",
                "notifications": {"enabled": False},
                "fixture": {
                    "enabled": True,
                    "source": str(FIXTURE_ROOT / "scan-multi-platform.json"),
                },
            },
            "role_pack": "ai_platform_pm",
            "candidate_profile_dir": str(PROFILE_DIR),
            "tracker_path": str(self.tmp_root / "tracker.csv"),
            "output_dir": str(self.tmp_root / "outputs"),
            "minimum_fit_score": 0,
            "top_n": 5,
            "language": "zh-CN",
            "dry_run": True,
            "emit_tailor_queue": True,
            "tailor_execution_strategy": "hybrid",
            "tailor_export_pdf": False,
        }
        payload.update(overrides)
        return payload

    def test_shortlist_scores_adapter_jobs_through_local_match(self) -> None:
        result = run_china_portal_match_bridge(self.request())

        self.assertEqual(result["shortlist_status"], "ready")
        self.assertEqual(result["adapter_scan_status"], "ready")
        self.assertEqual(result["total_jobs"], 1)
        self.assertEqual(len(result["shortlisted_jobs"]), 1)
        first = result["shortlisted_jobs"][0]
        self.assertEqual(first["job_card"]["company"], "Alpha AI")
        self.assertIsInstance(first["fit_score"], int)
        self.assertIn(first["decision"], {"go", "maybe", "skip"})
        self.assertIn("tailor_queue_json", result["artifacts"])
        self.assertIn("tailor_request_paths", result["artifacts"])

    def test_minimum_fit_score_can_filter_shortlist(self) -> None:
        result = run_china_portal_match_bridge(self.request(minimum_fit_score=90))

        self.assertEqual(result["shortlist_status"], "partial")
        self.assertEqual(result["shortlisted_jobs"], [])
        self.assertIn("threshold", " ".join(result["warnings"]).lower())

    def test_can_load_precomputed_adapter_result_path(self) -> None:
        result = run_china_portal_match_bridge(
            self.request(
                adapter_request={},
                adapter_result_path=str(FIXTURE_ROOT / "basic-scan.json"),
            )
        )

        self.assertIn(result["adapter_scan_status"], {"ready", "partial"})
        self.assertGreaterEqual(result["total_jobs"], 1)

    def test_non_dry_run_writes_tailor_queue_files(self) -> None:
        result = run_china_portal_match_bridge(
            self.request(
                dry_run=False,
                output_dir=str(self.tmp_root / "shortlist-output"),
            )
        )

        self.assertEqual(result["shortlist_status"], "ready")
        self.assertTrue(Path(result["artifacts"]["tailor_queue_json"]).exists())
        self.assertTrue(Path(result["artifacts"]["tailor_queue_markdown"]).exists())
        for path in result["artifacts"]["tailor_request_paths"]:
            self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
