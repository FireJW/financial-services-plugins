#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_SCRIPT_DIR = REPO_ROOT / "china-portal-adapter" / "skills" / "china-portal-adapter" / "scripts"
SHORTLIST_SCRIPT_DIR = REPO_ROOT / "china-portal-adapter" / "skills" / "china-portal-match-bridge" / "scripts"
for candidate in [str(LIVE_SCRIPT_DIR), str(SHORTLIST_SCRIPT_DIR)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import boss_live_scan_from_config
import boss_shortlist_from_config


class ChinaPortalConfigWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = REPO_ROOT / ".tmp-china-portal-wrapper-tests"
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            for path in sorted(self.tmp_root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()

    def test_boss_live_wrapper_defaults_to_stable_output_paths(self) -> None:
        args = argparse.Namespace(
            config_path=str(self.tmp_root / "config.json"),
            outputs_root=str(self.tmp_root),
            keywords=None,
            cities=None,
            minimum_monthly_rmb=0,
            timeout_ms=15000,
            max_jobs=20,
            output=None,
            markdown_output=None,
        )

        output_path, markdown_output_path = boss_live_scan_from_config.prepare_output_paths(args)
        request = boss_live_scan_from_config.build_request(args)

        self.assertIn("boss-live", str(output_path))
        self.assertEqual(output_path.name, "boss-live-result.json")
        self.assertEqual(markdown_output_path.name, "boss-live-report.md")
        self.assertEqual(request["platforms"], ["boss"])
        self.assertTrue(request["live_scan"]["enabled"])

    def test_boss_shortlist_wrapper_reuses_same_run_root_across_helpers(self) -> None:
        args = argparse.Namespace(
            config_path=str(self.tmp_root / "config.json"),
            candidate_profile_dir=str(self.tmp_root / "profile"),
            tracker_path=str(self.tmp_root / "tracker.csv"),
            upstream_root=str(self.tmp_root / "upstream"),
            outputs_root=str(self.tmp_root),
            keywords=None,
            cities=None,
            minimum_monthly_rmb=0,
            timeout_ms=15000,
            max_jobs=20,
            role_pack="ai_platform_pm",
            minimum_fit_score=60,
            top_n=5,
            tailor_execution_strategy="hybrid",
            tailor_export_pdf=False,
            language="zh-CN",
            dry_run=True,
            output_dir="",
            output=None,
            markdown_output=None,
        )

        run_root, output_path, markdown_output_path = boss_shortlist_from_config.prepare_output_paths(args)
        request = boss_shortlist_from_config.build_request(args)
        run_root_again, _, _ = boss_shortlist_from_config.prepare_output_paths(args)

        self.assertEqual(run_root, run_root_again)
        self.assertEqual(Path(request["output_dir"]), run_root)
        self.assertIn("boss-shortlist", str(run_root))
        self.assertEqual(output_path.name, "boss-shortlist-result.json")
        self.assertEqual(markdown_output_path.name, "boss-shortlist-report.md")
        self.assertEqual(request["adapter_request"]["platforms"], ["boss"])


if __name__ == "__main__":
    unittest.main()
