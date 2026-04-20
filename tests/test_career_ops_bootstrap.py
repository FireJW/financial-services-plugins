#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "career-ops-local"
    / "skills"
    / "career-ops-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bootstrap_career_ops_local as bootstrap_module
from export_local_profile_to_upstream import main as export_main


class CareerOpsBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / ".tmp-career-ops-bootstrap-tests"
        self.local_root = self.tmp_root / "local-root"
        self.upstream_root = self.tmp_root / "upstream-root"
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def test_all_bootstrap_template_sources_exist(self) -> None:
        for template_rel in bootstrap_module.TEMPLATE_MAP:
            template_path = bootstrap_module.TEMPLATES_ROOT / template_rel
            self.assertTrue(template_path.exists(), f"Missing bootstrap template source: {template_path}")

    def test_bootstrap_generates_profile_and_exportable_placeholders(self) -> None:
        argv = sys.argv[:]
        try:
            sys.argv = [
                "bootstrap_career_ops_local.py",
                "--root",
                str(self.local_root),
                "--upstream-root",
                str(self.upstream_root),
            ]
            bootstrap_rc = bootstrap_module.main()
            self.assertEqual(bootstrap_rc, 0)

            self.assertTrue((self.local_root / "profile" / "master_resume.md").exists())
            self.assertTrue((self.local_root / "profile" / "constraints.yml").exists())
            self.assertTrue((self.local_root / "roles" / "ai_platform_pm.yml").exists())
            self.assertTrue((self.local_root / "config" / "career_ops.local.json").exists())
            self.assertTrue((self.local_root / "applications" / "tracker.csv").exists())
            self.assertTrue((self.upstream_root / "README.local.txt").exists())

            sys.argv = [
                "export_local_profile_to_upstream.py",
                "--local-root",
                str(self.local_root),
                "--upstream-root",
                str(self.upstream_root),
                "--force",
            ]
            export_rc = export_main()
        finally:
            sys.argv = argv

        self.assertEqual(export_rc, 0)
        self.assertTrue((self.upstream_root / "cv.md").exists())
        self.assertTrue((self.upstream_root / "config" / "profile.yml").exists())
        self.assertTrue((self.upstream_root / "article-digest.md").exists())


if __name__ == "__main__":
    unittest.main()
