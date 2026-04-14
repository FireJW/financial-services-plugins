#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "china-portal-adapter" / "skills" / "china-portal-adapter" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import china_portal_doctor_from_config


class ChinaPortalDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = REPO_ROOT / ".tmp-china-portal-doctor-tests"
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            for path in sorted(self.tmp_root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()

    def test_doctor_reports_partial_when_boss_is_ready_but_missing_live_url(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        config_path = self.tmp_root / "china_portal_adapter.local.json"
        config_path.write_text(
            json.dumps(
                {
                    "platforms": ["boss", "liepin"],
                    "session_mode": "existing_local_only",
                    "browser_executable_paths": [str(browser)],
                    "browser_profile_paths": [str(profile_root)],
                    "live_scan": {
                        "enabled": False,
                        "platforms": {
                            "boss": {
                                "url": "",
                                "selectors": {
                                    "card": ".job-card"
                                }
                            }
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = china_portal_doctor_from_config.run_doctor(str(config_path))

        self.assertEqual(result["summary"]["doctor_status"], "partial")
        self.assertIn("boss", result["summary"]["ready_platforms"])
        self.assertIn("boss", result["summary"]["missing_live_scan_config"])
        self.assertIn("liepin", result["summary"]["unsupported_live_scan_platforms"])
        self.assertIn("Fill in live-scan URL/config", " ".join(result["next_steps"]))
        self.assertEqual(len(result["warnings"]), len(set(result["warnings"])))


if __name__ == "__main__":
    unittest.main()
