#!/usr/bin/env python3
from __future__ import annotations

import csv
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

from career_ops_local_runtime import run_career_ops_local


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "career-ops-local"
PROFILE_DIR = FIXTURE_ROOT / "private-root" / "profile"
JOB_TEXT = (FIXTURE_ROOT / "job_sources" / "ai_platform_pm.txt").read_text(encoding="utf-8")


class CareerOpsLocalRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / ".tmp-career-ops-local-tests"
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def request(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "task": "match",
            "job_source": "text",
            "job_input": JOB_TEXT,
            "role_pack": "ai_platform_pm",
            "candidate_profile_dir": str(PROFILE_DIR),
            "output_dir": str(self.tmp_root / "outputs"),
            "tracker_path": str(self.tmp_root / "tracker.csv"),
            "require_human_review": True,
            "language": "zh-CN",
        }
        payload.update(overrides)
        return payload

    def test_intake_supports_text_file_and_url_modes(self) -> None:
        text_result = run_career_ops_local(self.request(task="intake", job_source="text", job_input=JOB_TEXT))
        self.assertEqual(text_result["status"], "ready")
        self.assertEqual(text_result["job_card"]["company"], "Example AI")
        self.assertEqual(text_result["job_card"]["level"], "senior")

        file_result = run_career_ops_local(
            self.request(
                task="intake",
                job_source="file",
                job_input=str(FIXTURE_ROOT / "job_sources" / "ai_platform_pm.txt"),
            )
        )
        self.assertEqual(file_result["status"], "ready")
        self.assertTrue(file_result["job_card"]["source"]["path"].endswith("ai_platform_pm.txt"))

        url_result = run_career_ops_local(
            self.request(
                task="intake",
                job_source="url",
                job_input="https://jobs.example.ai/senior-ai-platform-product-manager",
                job_capture_text=JOB_TEXT,
            )
        )
        self.assertEqual(url_result["status"], "ready")
        self.assertEqual(url_result["job_card"]["source"]["url"], "https://jobs.example.ai/senior-ai-platform-product-manager")

        partial_url = run_career_ops_local(
            self.request(
                task="intake",
                job_source="url",
                job_input="https://jobs.example.ai/senior-ai-platform-product-manager",
            )
        )
        self.assertEqual(partial_url["status"], "partial")

    def test_missing_profile_returns_bootstrap_guidance(self) -> None:
        result = run_career_ops_local(
            self.request(candidate_profile_dir=str(self.tmp_root / "missing-profile"))
        )

        self.assertEqual(result["status"], "error")
        joined = "\n".join(result["warnings"])
        self.assertIn("run_bootstrap_career_ops_local.cmd", joined)

    def test_role_packs_return_different_scores_for_same_job(self) -> None:
        ai_result = run_career_ops_local(self.request(role_pack="ai_platform_pm"))
        general_result = run_career_ops_local(self.request(role_pack="general_pm"))
        strategy_result = run_career_ops_local(self.request(role_pack="product_strategy_ops"))

        self.assertEqual(ai_result["status"], "ready")
        self.assertNotEqual(ai_result["fit_score"], general_result["fit_score"])
        self.assertNotEqual(general_result["fit_score"], strategy_result["fit_score"])
        self.assertIn(ai_result["decision"], {"go", "maybe"})
        self.assertIn("建议", ai_result["fit_summary"])

    def test_tailor_includes_human_review_and_artifacts(self) -> None:
        result = run_career_ops_local(self.request(task="tailor"))

        self.assertEqual(result["status"], "ready")
        self.assertIn("tailored_resume_markdown", result["artifacts"])
        self.assertTrue(result["human_review_items"])
        self.assertIn("关键词覆盖", result["report_markdown"])

    def test_track_updates_existing_row_without_duplicates(self) -> None:
        first = run_career_ops_local(self.request(task="track", application_status="applied"))
        second = run_career_ops_local(
            self.request(
                task="track",
                application_status="interview",
                status_note="Moved to interview loop.",
            )
        )

        self.assertEqual(first["status"], "ready")
        self.assertEqual(second["status"], "ready")

        with Path(self.tmp_root / "tracker.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["application_status"], "interview")
        self.assertEqual(rows[0]["status_note"], "Moved to interview loop.")

    def test_apply_assist_stays_packaging_only(self) -> None:
        result = run_career_ops_local(self.request(task="apply_assist"))

        self.assertEqual(result["status"], "ready")
        self.assertIn("application_assist_markdown", result["artifacts"])
        joined = " ".join(result["warnings"])
        self.assertIn("packaging-only", joined)
        self.assertIn("manual", joined.lower())

    def test_generated_timestamps_are_absolute(self) -> None:
        result = run_career_ops_local(self.request())

        self.assertTrue(result["generated_at"].endswith("Z"))
        self.assertTrue(result["diagnostics"]["upstream"]["path"].endswith("career-ops-upstream"))

    def test_hybrid_tailor_builds_upstream_handoff_when_pdf_surface_exists(self) -> None:
        upstream_root = self.tmp_root / "fake-upstream"
        upstream_root.mkdir(parents=True, exist_ok=True)
        (upstream_root / "package.json").write_text(
            '{"scripts":{"pdf":"node generate-pdf.mjs","sync-check":"node cv-sync-check.mjs","verify":"node verify-pipeline.mjs"}}\n',
            encoding="utf-8",
        )
        (upstream_root / "generate-pdf.mjs").write_text("console.log('pdf');\n", encoding="utf-8")
        (upstream_root / "cv-sync-check.mjs").write_text("console.log('sync');\n", encoding="utf-8")
        (upstream_root / "verify-pipeline.mjs").write_text("console.log('verify');\n", encoding="utf-8")
        (upstream_root / "batch").mkdir(exist_ok=True)
        (upstream_root / "modes").mkdir(exist_ok=True)
        (upstream_root / "modes" / "scan.md").write_text("# scan\n", encoding="utf-8")

        result = run_career_ops_local(
            self.request(
                task="tailor",
                execution_strategy="hybrid",
                upstream_root=str(upstream_root),
            )
        )

        self.assertEqual(result["status"], "ready")
        self.assertIn("upstream_handoff_json", result["artifacts"])
        self.assertIn("Hybrid mode", " ".join(result["warnings"]))
        self.assertTrue(result["diagnostics"]["upstream"]["capabilities"]["pdf_generation"])
        handoff = json.loads(Path(result["artifacts"]["upstream_handoff_json"]).read_text(encoding="utf-8"))
        self.assertIn("generate_pdf_with_local_chromium.mjs", handoff["commands"][0]["command"])

    def test_tailor_dry_run_can_stage_pdf_and_upstream_checks(self) -> None:
        upstream_root = self.tmp_root / "fake-upstream-checks"
        upstream_root.mkdir(parents=True, exist_ok=True)
        (upstream_root / "package.json").write_text(
            '{"scripts":{"pdf":"node generate-pdf.mjs","sync-check":"node cv-sync-check.mjs","verify":"node verify-pipeline.mjs"}}\n',
            encoding="utf-8",
        )
        (upstream_root / "generate-pdf.mjs").write_text("console.log('pdf');\n", encoding="utf-8")
        (upstream_root / "cv-sync-check.mjs").write_text("console.log('sync');\n", encoding="utf-8")
        (upstream_root / "verify-pipeline.mjs").write_text("console.log('verify');\n", encoding="utf-8")

        result = run_career_ops_local(
            self.request(
                task="tailor",
                execution_strategy="hybrid",
                export_pdf=True,
                run_upstream_sync_check=True,
                run_upstream_verify=True,
                upstream_root=str(upstream_root),
                dry_run=True,
            )
        )

        self.assertEqual(result["status"], "ready")
        self.assertIn("tailored_resume_html", result["artifacts"])
        self.assertIn("tailored_resume_pdf", result["artifacts"])
        self.assertIn("upstream_profile_export_artifact", result["artifacts"])
        self.assertIn("upstream_sync_check_artifact", result["artifacts"])
        self.assertIn("upstream_verify_artifact", result["artifacts"])


if __name__ == "__main__":
    unittest.main()
