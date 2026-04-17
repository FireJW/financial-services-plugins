#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
import shutil


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "china-portal-adapter"
    / "skills"
    / "china-portal-adapter"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from china_portal_adapter_runtime import run_china_portal_adapter


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "china-portal-adapter"


class ChinaPortalAdapterRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / ".tmp-china-portal-adapter-tests"
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def request(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "task": "scan_jobs",
            "platforms": ["boss", "liepin"],
            "keywords": ["ai", "platform"],
            "cities": ["Shanghai"],
            "salary_filters": {
                "minimum_monthly_rmb": 30000
            },
            "blacklist_companies": [],
            "blacklist_recruiters": [],
            "session_mode": "existing_local_only",
            "notifications": {"enabled": False},
            "fixture": {
                "enabled": True,
                "source": str(FIXTURE_ROOT / "scan-multi-platform.json")
            }
        }
        payload.update(overrides)
        return payload

    def test_platform_probe_uses_fixture_status(self) -> None:
        result = run_china_portal_adapter(
            self.request(
                task="platform_probe",
                fixture={"enabled": True, "source": str(FIXTURE_ROOT / "platform-probe.json")}
            )
        )

        self.assertEqual(result["scan_status"], "partial")
        self.assertEqual(result["session_status"]["platforms_signed_in"], ["boss", "job51"])
        self.assertEqual(result["platform_status"]["zhilian"]["discovery"], "error")
        self.assertEqual(result["jobs"], [])

    def test_scan_jobs_filters_by_keyword_city_and_salary(self) -> None:
        result = run_china_portal_adapter(self.request())

        self.assertEqual(result["scan_status"], "ready")
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["job_card"]["company"], "Alpha AI")
        self.assertEqual(result["jobs"][0]["platform_meta"]["platform"], "boss")

    def test_blacklists_remove_matching_jobs(self) -> None:
        result = run_china_portal_adapter(
            self.request(
                blacklist_companies=["Alpha AI"],
                blacklist_recruiters=["External Headhunter"],
            )
        )

        self.assertEqual(result["scan_status"], "partial")
        self.assertEqual(result["jobs"], [])
        self.assertIn("filtered out", " ".join(result["warnings"]).lower())

    def test_requires_fixture_mode_in_v1(self) -> None:
        result = run_china_portal_adapter(
            {
                "task": "scan_jobs",
                "platforms": ["boss"],
                "fixture": {"enabled": False}
            }
        )

        self.assertEqual(result["scan_status"], "skipped")
        self.assertIn("readiness_gate", result)
        self.assertIn("live scan", " ".join(result["warnings"]).lower())

    def test_platform_probe_can_run_without_fixture_when_local_browser_and_profile_exist(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        default_dir = profile_root / "Default"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        default_dir.mkdir(parents=True, exist_ok=True)
        (default_dir / "Cookies").write_text("", encoding="utf-8")

        result = run_china_portal_adapter(
            {
                "task": "platform_probe",
                "platforms": ["boss", "zhilian"],
                "session_mode": "existing_local_only",
                "fixture": {"enabled": False},
                "browser_executable_paths": [str(browser)],
                "browser_profile_paths": [str(profile_root)],
            }
        )

        self.assertEqual(result["scan_status"], "partial")
        self.assertIn(str(browser), result["session_status"]["browser_executables_detected"])
        self.assertIn(str(profile_root), result["session_status"]["browser_profile_roots_detected"])
        self.assertTrue(result["session_status"]["browser_profile_probe_details"][0]["has_local_state"])
        self.assertTrue(result["session_status"]["browser_profile_probe_details"][0]["has_cookies"])
        self.assertEqual(result["platform_status"]["boss"]["discovery"], "ready")
        self.assertEqual(result["platform_status"]["zhilian"]["discovery"], "partial")

    def test_platform_probe_detects_modern_network_cookie_path(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        default_network = profile_root / "Default" / "Network"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        default_network.mkdir(parents=True, exist_ok=True)
        (default_network / "Cookies").write_text("", encoding="utf-8")

        result = run_china_portal_adapter(
            {
                "task": "platform_probe",
                "platforms": ["boss"],
                "session_mode": "existing_local_only",
                "fixture": {"enabled": False},
                "browser_executable_paths": [str(browser)],
                "browser_profile_paths": [str(profile_root)],
            }
        )

        self.assertEqual(result["scan_status"], "ready")
        self.assertTrue(result["session_status"]["browser_profile_probe_details"][0]["has_cookies"])

    def test_platform_probe_reports_missing_browser_cleanly(self) -> None:
        result = run_china_portal_adapter(
            {
                "task": "platform_probe",
                "platforms": ["boss"],
                "session_mode": "existing_local_only",
                "fixture": {"enabled": False},
                "browser_executable_paths": [str(self.tmp_root / "missing-chrome.exe")],
                "browser_profile_paths": [str(self.tmp_root / "missing-profile")],
            }
        )

        self.assertEqual(result["scan_status"], "error")
        self.assertIn("No local Chrome or Edge executable", " ".join(result["warnings"]))

    def test_platform_probe_can_load_browser_paths_from_local_config(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        config_path = self.tmp_root / "china_portal_adapter.local.json"
        config_path.write_text(
            json.dumps(
                {
                    "platforms": ["boss"],
                    "browser_executable_paths": [str(browser)],
                    "browser_profile_paths": [str(profile_root)],
                    "session_mode": "existing_local_only",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_china_portal_adapter(
            {
                "task": "platform_probe",
                "fixture": {"enabled": False},
                "config_path": str(config_path),
            }
        )

        self.assertIn(str(browser), result["session_status"]["browser_executables_detected"])
        self.assertIn(str(profile_root), result["session_status"]["browser_profile_roots_detected"])

    def test_explicit_request_browser_paths_override_config(self) -> None:
        config_browser = self.tmp_root / "config-browser.exe"
        request_browser = self.tmp_root / "request-browser.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        config_browser.write_text("", encoding="utf-8")
        request_browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        config_path = self.tmp_root / "china_portal_adapter.local.json"
        config_path.write_text(
            json.dumps(
                {
                    "platforms": ["boss"],
                    "browser_executable_paths": [str(config_browser)],
                    "browser_profile_paths": [str(profile_root)],
                    "session_mode": "existing_local_only",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_china_portal_adapter(
            {
                "task": "platform_probe",
                "fixture": {"enabled": False},
                "config_path": str(config_path),
                "browser_executable_paths": [str(request_browser)],
                "browser_profile_paths": [str(profile_root)],
            }
        )

        self.assertIn(str(request_browser), result["session_status"]["browser_executables_detected"])
        self.assertNotIn(str(config_browser), result["session_status"]["browser_executables_detected"])

    def test_live_scan_runner_can_be_invoked_when_ready_and_enabled(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")

        def fake_live_runner(request: dict[str, object], probe_result: dict[str, object]) -> dict[str, object]:
            del request, probe_result
            return {
                "jobs_by_platform": {
                    "boss": [
                        {
                            "job_card": {
                                "job_id": "boss-live-001",
                                "company": "Boss Alpha",
                                "role_title": "AI Platform Product Manager",
                                "level": "senior",
                                "location": "Shanghai",
                                "reports_to": "",
                                "summary": "Build AI platform workflows.",
                                "responsibilities": [],
                                "must_haves": [],
                                "nice_to_have": [],
                                "keywords": ["ai", "platform"],
                                "source": {
                                    "type": "portal_scan",
                                    "url": "https://www.zhipin.com/job_detail/boss-live-001",
                                    "path": ""
                                },
                                "raw_text_excerpt": "Build AI platform workflows."
                            },
                            "platform_meta": {
                                "platform": "boss",
                                "recruiter_type": "direct",
                                "recruiter_name": "Boss Recruiter",
                                "salary_text": "40-60K"
                              },
                              "apply_support": {
                                  "available": False,
                                  "mode": "manual_only"
                              }
                        }
                    ]
                },
                "warnings": []
            }

        result = run_china_portal_adapter(
            {
                "task": "scan_jobs",
                "platforms": ["boss"],
                "keywords": ["ai"],
                "cities": ["Shanghai"],
                "salary_filters": {"minimum_monthly_rmb": 30000},
                "session_mode": "existing_local_only",
                "fixture": {"enabled": False},
                "browser_executable_paths": [str(browser)],
                "browser_profile_paths": [str(profile_root)],
                "live_scan": {
                    "enabled": True,
                    "platforms": {
                        "boss": {
                            "url": "file:///tmp/boss-live-list.html",
                            "selectors": {
                                "card": ".job-card",
                                "title": ".job-title",
                                "company": ".company-name",
                                "location": ".job-location",
                                "summary": ".job-summary",
                                "salary": ".salary",
                                "link": ".job-link",
                                "recruiter_name": ".recruiter-name",
                                "recruiter_type": ".recruiter-type"
                            }
                        }
                    }
                }
            },
            live_scan_runner=fake_live_runner,
        )

        self.assertEqual(result["scan_status"], "ready")
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["job_card"]["company"], "Boss Alpha")

    def test_readiness_gate_surfaces_missing_live_scan_config_for_ready_boss(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")

        result = run_china_portal_adapter(
            {
                "task": "scan_jobs",
                "platforms": ["boss", "liepin"],
                "session_mode": "existing_local_only",
                "fixture": {"enabled": False},
                "browser_executable_paths": [str(browser)],
                "browser_profile_paths": [str(profile_root)],
                "live_scan": {
                    "enabled": True,
                    "platforms": {
                        "boss": {
                            "url": "",
                            "selectors": {"card": ".job-card"}
                        }
                    }
                },
            }
        )

        self.assertEqual(result["scan_status"], "skipped")
        self.assertIn("boss", result["readiness_gate"]["missing_live_scan_config"])
        self.assertIn("liepin", result["readiness_gate"]["unsupported_live_scan_platforms"])
        self.assertIn("config", " ".join(result["readiness_gate"]["next_steps"]).lower())
        self.assertIn("missing live-scan url/config", " ".join(result["warnings"]).lower())

    def test_request_live_scan_overlays_local_config_platform_settings(self) -> None:
        browser = self.tmp_root / "chrome.exe"
        profile_root = self.tmp_root / "ChromeUserData"
        browser.write_text("", encoding="utf-8")
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "Local State").write_text("{}", encoding="utf-8")
        config_path = self.tmp_root / "china_portal_adapter.local.json"
        config_path.write_text(
            json.dumps(
                {
                    "platforms": ["boss"],
                    "session_mode": "existing_local_only",
                    "browser_executable_paths": [str(browser)],
                    "browser_profile_paths": [str(profile_root)],
                    "live_scan": {
                        "enabled": False,
                        "platforms": {
                            "boss": {
                                "url": "file:///tmp/boss-live-list.html",
                                "selectors": {
                                    "card": ".job-card",
                                    "title": ".job-title",
                                    "company": ".company-name",
                                    "location": ".job-location",
                                    "summary": ".job-summary",
                                    "salary": ".salary",
                                    "link": ".job-link",
                                    "recruiter_name": ".recruiter-name",
                                    "recruiter_type": ".recruiter-type"
                                }
                            }
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        seen: dict[str, object] = {}

        def fake_live_runner(request: dict[str, object], probe_result: dict[str, object]) -> dict[str, object]:
            del probe_result
            seen["request"] = request
            return {
                "jobs_by_platform": {
                    "boss": [
                        {
                            "job_card": {
                                "job_id": "boss-live-002",
                                "company": "Boss Beta",
                                "role_title": "AI Product Manager",
                                "level": "senior",
                                "location": "Shanghai",
                                "reports_to": "",
                                "summary": "Drive AI roadmap.",
                                "responsibilities": [],
                                "must_haves": [],
                                "nice_to_have": [],
                                "keywords": ["ai", "product"],
                                "source": {
                                    "type": "portal_scan",
                                    "url": "https://www.zhipin.com/job_detail/boss-live-002",
                                    "path": ""
                                },
                                "raw_text_excerpt": "Drive AI roadmap."
                            },
                            "platform_meta": {
                                "platform": "boss",
                                "recruiter_type": "direct",
                                "recruiter_name": "Boss Recruiter",
                                "salary_text": "35-50K"
                            },
                            "apply_support": {
                                "available": False,
                                "mode": "manual_only"
                            }
                        }
                    ]
                },
                "warnings": []
            }

        result = run_china_portal_adapter(
            {
                "task": "scan_jobs",
                "config_path": str(config_path),
                "fixture": {"enabled": False},
                "live_scan": {
                    "enabled": True,
                    "timeout_ms": 12345,
                    "max_jobs": 7
                },
            },
            live_scan_runner=fake_live_runner,
        )

        self.assertEqual(result["scan_status"], "ready")
        request_seen = seen["request"]
        self.assertEqual(request_seen["live_scan_timeout_ms"], 12345)
        self.assertEqual(request_seen["live_scan_max_jobs"], 7)
        self.assertEqual(
            request_seen["live_scan_platforms"]["boss"]["url"],
            "file:///tmp/boss-live-list.html",
        )


if __name__ == "__main__":
    unittest.main()
