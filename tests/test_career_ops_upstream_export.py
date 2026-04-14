#!/usr/bin/env python3
from __future__ import annotations

import json
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

from export_local_profile_to_upstream import main as export_main


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "career-ops-local" / "private-root"


class CareerOpsUpstreamExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / ".tmp-career-ops-export-tests"
        self.local_root = self.tmp_root / "local"
        self.upstream_root = self.tmp_root / "upstream"
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        shutil.copytree(FIXTURE_ROOT, self.local_root)
        self.upstream_root.mkdir(parents=True, exist_ok=True)
        (self.upstream_root / "config").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def test_export_writes_cv_profile_and_article_digest(self) -> None:
        argv = sys.argv[:]
        try:
            sys.argv = [
                "export_local_profile_to_upstream.py",
                "--local-root",
                str(self.local_root),
                "--upstream-root",
                str(self.upstream_root),
            ]
            rc = export_main()
        finally:
            sys.argv = argv

        self.assertEqual(rc, 0)
        cv_path = self.upstream_root / "cv.md"
        profile_path = self.upstream_root / "config" / "profile.yml"
        digest_path = self.upstream_root / "article-digest.md"

        self.assertTrue(cv_path.exists())
        self.assertTrue(profile_path.exists())
        self.assertTrue(digest_path.exists())
        self.assertIn("CV -- Candidate Name", cv_path.read_text(encoding="utf-8"))
        self.assertIn("candidate:", profile_path.read_text(encoding="utf-8"))
        self.assertIn("Article Digest", digest_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
