from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from multiplatform_repurpose_runtime import (
    ALL_PLATFORM_TARGETS,
    build_multiplatform_repurpose,
    load_json,
)


class MultiplatformRepurposeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_dir = Path(__file__).resolve().parent / "fixtures" / "multiplatform-repurpose"
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-multiplatform-repurpose"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_builds_dist_packages_for_requested_platforms(self) -> None:
        request = load_json(self.fixture_dir / "request.json")
        request["output_dir"] = str(self.temp_dir / "run")
        request["source_article"]["markdown_path"] = str(self.fixture_dir / "source-article.md")

        result = build_multiplatform_repurpose(request)

        self.assertEqual(result["contract_version"], "multiplatform_repurpose_manifest/v1")
        self.assertEqual(result["run_id"], "sample-agent-budget-discipline")
        self.assertEqual(result["source_integrity"]["status"], "ok")
        self.assertEqual(set(result["platforms"].keys()), {"wechat_article", "xiaohongshu_cards", "douyin_short_video", "x_thread"})
        self.assertEqual(result["source_integrity"]["core_thesis"], result["platforms"]["wechat_article"]["core_thesis"])

        manifest_path = Path(result["manifest_path"])
        self.assertTrue(manifest_path.exists())
        self.assertTrue((self.temp_dir / "run" / "dist" / "wechat_article" / "article.md").exists())
        self.assertTrue((self.temp_dir / "run" / "dist" / "xiaohongshu_cards" / "cards.md").exists())
        self.assertTrue((self.temp_dir / "run" / "dist" / "douyin_short_video" / "script.md").exists())
        self.assertTrue((self.temp_dir / "run" / "dist" / "x_thread" / "thread.md").exists())

        wechat = result["platforms"]["wechat_article"]
        xhs = result["platforms"]["xiaohongshu_cards"]
        douyin = result["platforms"]["douyin_short_video"]
        self.assertIn("framework", wechat["body_or_script"].lower())
        self.assertIn("Card 1", xhs["body_or_script"])
        self.assertIn("3-second hook", douyin["body_or_script"])
        self.assertNotEqual(wechat["body_or_script"], xhs["body_or_script"])
        self.assertTrue(
            any(
                "Customer case studies are still thin" in item
                for item in wechat["caveats_preserved"]
            )
        )

    def test_preserves_citations_and_caveats_from_publish_package_and_brief(self) -> None:
        publish_package = {
            "contract_version": "publish-package/v1",
            "title": "Agent budget discipline",
            "draft_thesis": "Agent budgets need measurable retention and cycle-time proof before the market pays for them.",
            "content_markdown": "# Agent budget discipline\n\nAgent budgets need measurable retention and cycle-time proof.",
            "citations": [
                {
                    "citation_id": "P1",
                    "source_name": "Company Blog",
                    "title": "Agent workflow rollout",
                    "url": "https://example.com/company-agent-rollout"
                }
            ],
            "operator_notes": ["Keep the unsupported margin-expansion claim out of the article."]
        }
        article_brief = {
            "analysis_brief": {
                "recommended_thesis": "Agent budgets need measurable retention and cycle-time proof before the market pays for them.",
                "not_proven": [
                    {
                        "claim_text": "AI agents have already improved margins across the sector.",
                        "why_not_proven": "No audited customer-level margin evidence was supplied.",
                        "citation_ids": []
                    }
                ],
                "misread_risks": ["Readers may mistake adoption announcements for retention proof."]
            }
        }
        result = build_multiplatform_repurpose(
            {
                "run_id": "package-input",
                "source_article": {},
                "existing_publish_package": publish_package,
                "article_brief": article_brief,
                "platform_targets": ["linkedin_post"],
                "output_dir": str(self.temp_dir / "package-input"),
            }
        )

        platform = result["platforms"]["linkedin_post"]
        self.assertEqual(result["source_integrity"]["status"], "ok")
        self.assertEqual(platform["source_integrity_status"], "ok")
        self.assertEqual(platform["citations_used"][0]["citation_id"], "P1")
        self.assertTrue(any("already improved margins" in item for item in platform["caveats_preserved"]))
        self.assertTrue(any("adoption announcements" in item for item in platform["what_not_to_say"]))
        self.assertTrue(platform["human_edit_required"])

    def test_missing_citations_are_marked_without_fabricating_sources(self) -> None:
        result = build_multiplatform_repurpose(
            {
                "run_id": "missing-citations",
                "source_article": {
                    "markdown": "# Thin Source\n\nThe thesis is that weak evidence must stay labeled as weak."
                },
                "platform_targets": ["substack_article"],
                "output_dir": str(self.temp_dir / "missing-citations"),
            }
        )

        platform = result["platforms"]["substack_article"]
        self.assertEqual(result["source_integrity"]["status"], "needs_human_review")
        self.assertEqual(platform["source_integrity_status"], "needs_human_review")
        self.assertEqual(platform["citations_used"], [{"status": "missing", "note": "No citations were supplied."}])
        self.assertTrue(any("missing citation" in item.lower() for item in platform["what_not_to_say"]))

    def test_platform_profiles_add_length_voice_and_review_scorecard(self) -> None:
        request = load_json(self.fixture_dir / "request.json")
        request["output_dir"] = str(self.temp_dir / "quality-profile")
        request["source_article"]["markdown_path"] = str(self.fixture_dir / "source-article.md")
        request["platform_targets"] = ["xiaohongshu_cards", "x_thread"]
        request["platform_profiles"] = {
            "xiaohongshu_cards": {
                "voice": "calm creator, plain language, saveable checklist",
                "target_length": "6 cards, one idea per card",
                "must_include": ["keep evidence caveat visible", "end with a practical checklist"],
            }
        }

        result = build_multiplatform_repurpose(request)

        xhs = result["platforms"]["xiaohongshu_cards"]
        x_thread = result["platforms"]["x_thread"]
        self.assertEqual(xhs["platform_profile"]["target_length"], "6 cards, one idea per card")
        self.assertIn("saveable checklist", xhs["platform_profile"]["voice"])
        self.assertIn("keep evidence caveat visible", xhs["platform_profile"]["must_include"])
        self.assertIn("thread", x_thread["platform_profile"]["format"].lower())
        self.assertTrue(any(item["check"] == "target_length" for item in xhs["quality_scorecard"]))
        self.assertTrue(any(item["check"] == "citation_integrity" for item in xhs["quality_scorecard"]))
        self.assertEqual(xhs["citations_used"][0]["citation_id"], "S1")
        self.assertTrue((self.temp_dir / "quality-profile" / "dist" / "xiaohongshu_cards" / "platform-profile.json").exists())
        self.assertTrue((self.temp_dir / "quality-profile" / "dist" / "xiaohongshu_cards" / "quality-scorecard.md").exists())

    def test_platform_packages_include_rewrite_packet_for_model_or_editor(self) -> None:
        request = load_json(self.fixture_dir / "request.json")
        request["output_dir"] = str(self.temp_dir / "rewrite-packet")
        request["source_article"]["markdown_path"] = str(self.fixture_dir / "source-article.md")
        request["platform_targets"] = ["wechat_article"]

        result = build_multiplatform_repurpose(request)

        package = result["platforms"]["wechat_article"]
        rewrite_packet_path = Path(package["files"]["rewrite_packet"])
        self.assertTrue(rewrite_packet_path.exists())
        rewrite_packet = rewrite_packet_path.read_text(encoding="utf-8-sig")
        self.assertIn("Preserve this core thesis", rewrite_packet)
        self.assertIn(package["core_thesis"], rewrite_packet)
        self.assertIn("Platform profile", rewrite_packet)
        self.assertIn("Quality scorecard", rewrite_packet)
        self.assertIn("What not to say", rewrite_packet)
        self.assertIn("S1", rewrite_packet)
        self.assertIn("Customer case studies are still thin", rewrite_packet)
        self.assertIn("Framework\n- What changed", rewrite_packet)

    def test_report_surfaces_review_queue_file_paths(self) -> None:
        request = load_json(self.fixture_dir / "request.json")
        request["output_dir"] = str(self.temp_dir / "review-queue")
        request["source_article"]["markdown_path"] = str(self.fixture_dir / "source-article.md")
        request["platform_targets"] = ["wechat_article", "x_thread"]

        result = build_multiplatform_repurpose(request)

        report = Path(result["report_path"]).read_text(encoding="utf-8-sig")
        wechat = result["platforms"]["wechat_article"]
        x_thread = result["platforms"]["x_thread"]
        self.assertIn("## Review Queue", report)
        self.assertIn("### wechat_article", report)
        self.assertIn("### x_thread", report)
        self.assertIn(f"- Content: {wechat['files']['content']}", report)
        self.assertIn(f"- Rewrite packet: {wechat['files']['rewrite_packet']}", report)
        self.assertIn(f"- Quality scorecard: {wechat['files']['quality_scorecard']}", report)
        self.assertIn(f"- Human edit checklist: {x_thread['files']['human_edit_required']}", report)

    def test_defaults_to_all_supported_platform_targets(self) -> None:
        result = build_multiplatform_repurpose(
            {
                "run_id": "all-platforms",
                "source_article": {
                    "markdown": "# Platform Test\n\nThe thesis is that one source can become many platform-native packages."
                },
                "citations": [{"citation_id": "S1", "source_name": "Fixture", "url": "https://example.com/source"}],
                "output_dir": str(self.temp_dir / "all-platforms"),
            }
        )

        self.assertEqual(set(result["platforms"].keys()), set(ALL_PLATFORM_TARGETS))
        for platform_name, package in result["platforms"].items():
            with self.subTest(platform=platform_name):
                self.assertTrue(package["what_not_to_say"])
                self.assertTrue(package["human_edit_required"])
                self.assertTrue(Path(package["files"]["json"]).exists())

    def test_cli_output_dir_override_resolves_relative_to_cwd(self) -> None:
        output_dir = self.temp_dir / "cli-run"
        relative_output_dir = output_dir.relative_to(Path.cwd())
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "multiplatform_repurpose.py"),
                str(self.fixture_dir / "request.json"),
                "--output-dir",
                str(relative_output_dir),
            ],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = json.loads(completed.stdout)
        self.assertEqual(Path(manifest["manifest_path"]).resolve(), (output_dir / "manifest.json").resolve())
        self.assertTrue((output_dir / "dist" / "wechat_article" / "article.md").exists())


if __name__ == "__main__":
    unittest.main()
