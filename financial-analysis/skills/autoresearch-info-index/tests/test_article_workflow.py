#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest
from pathlib import Path
from time import time

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_cleanup_runtime import cleanup_article_temp_dirs
from article_draft_flow_runtime import build_article_draft
from article_revise_flow_runtime import build_article_revision
from article_batch_workflow_runtime import run_article_batch_workflow
from article_auto_queue_runtime import run_article_auto_queue
from article_workflow_runtime import run_article_workflow
from news_index_core import read_json, run_news_index
from x_index_runtime import run_x_index


class ArticleWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.news_request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.temp_root = Path.cwd() / ".tmp" / "article-workflow-tests"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def build_seed_x_index_result(self, tmpdir: Path) -> dict:
        screenshot_path = tmpdir / "root.png"
        media_path = tmpdir / "airlift.png"
        screenshot_path.write_bytes(b"root")
        media_path.write_bytes(b"seed-image")
        request = {
            "topic": "US military airlift chatter",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-airlift",
                    "claim_text": "A significant movement from CONUS to the Middle East is underway.",
                }
            ],
            "seed_posts": [
                {
                    "post_url": "https://x.com/sentdefender/status/2036153038906196133",
                    "html": """
                        <html>
                          <head>
                            <meta property="og:title" content="SentDefender on X">
                            <meta property="og:description" content="A significant movement is underway from US bases to the Middle East with at least 35 C-17 flights since March 12th.">
                          </head>
                          <body><time datetime="2026-03-24T09:30:00+00:00"></time></body>
                        </html>
                    """,
                    "root_post_screenshot_path": str(screenshot_path),
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "local_artifact_path": str(media_path),
                            "ocr_text_raw": "Origins: 12 Hunter Army Air Field. Destinations: 17 Ovda Air Base.",
                        }
                    ],
                }
            ],
        }
        return run_x_index(request)

    def build_seed_x_request(self, tmpdir: Path) -> dict:
        tmpdir.mkdir(parents=True, exist_ok=True)
        screenshot_path = tmpdir / "workflow-root.png"
        media_path = tmpdir / "workflow-media.png"
        screenshot_path.write_bytes(b"workflow-root")
        media_path.write_bytes(b"workflow-media")
        return {
            "topic": "Workflow seed topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-workflow",
                    "claim_text": "A significant movement from CONUS to the Middle East is underway.",
                }
            ],
            "seed_posts": [
                {
                    "post_url": "https://x.com/sentdefender/status/2036153038906196133",
                    "html": """
                        <html>
                          <head>
                            <meta property="og:title" content="SentDefender on X">
                            <meta property="og:description" content="A significant movement is underway from US bases to the Middle East with at least 35 C-17 flights since March 12th.">
                          </head>
                          <body><time datetime="2026-03-24T09:30:00+00:00"></time></body>
                        </html>
                    """,
                    "root_post_screenshot_path": str(screenshot_path),
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "local_artifact_path": str(media_path),
                            "ocr_text_raw": "Origins: 12 Hunter Army Air Field. Destinations: 17 Ovda Air Base.",
                        }
                    ],
                }
            ],
        }

    def build_blocked_x_index_result(self, tmpdir: Path) -> dict:
        screenshot_path = tmpdir / "blocked-root.png"
        screenshot_path.write_bytes(b"blocked")
        request = {
            "topic": "Blocked capture",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "seed_posts": [
                {
                    "post_url": "https://x.com/example/status/1",
                    "html": "<html><body>Something went wrong</body></html>",
                    "visible_text": "",
                    "accessibility_text": "",
                    "root_post_screenshot_path": str(screenshot_path),
                }
            ],
        }
        return run_x_index(request)

    def test_article_draft_from_x_index_selects_images_and_citations(self) -> None:
        draft = build_article_draft({"source_result": self.build_seed_x_index_result(self.case_dir("x-seed")), "max_images": 2})
        package = draft["article_package"]
        self.assertEqual(draft["source_summary"]["source_kind"], "x_index")
        self.assertGreaterEqual(package["draft_metrics"]["image_count"], 1)
        self.assertGreaterEqual(package["draft_metrics"]["citation_count"], 1)
        self.assertIn("Images And Screenshots", package["body_markdown"])
        self.assertIn(f"![{package['selected_images'][0]['image_id']}](", package["article_markdown"])
        self.assertTrue(any(item["status"] == "local_ready" for item in package["selected_images"]))
        self.assertEqual(len(package["selected_images"]), len(package["image_blocks"]))

    def test_article_draft_from_blocked_x_index_keeps_screenshot_boundary(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_blocked_x_index_result(self.case_dir("x-blocked")),
                "image_strategy": "screenshots_only",
                "draft_mode": "image_only",
            }
        )
        package = draft["article_package"]
        self.assertEqual(draft["source_summary"]["blocked_source_count"], 1)
        self.assertGreaterEqual(package["draft_metrics"]["image_count"], 1)
        self.assertEqual(package["selected_images"][0]["role"], "root_post_screenshot")
        self.assertIn("blocked", package["selected_images"][0]["caption"].lower())
        self.assertEqual(package["selected_images"][0]["status"], "local_ready")
        self.assertIn(package["selected_images"][0]["embed_markdown"], package["article_markdown"])
        self.assertTrue(package["verification"]["blocked_images_labeled"])
        self.assertIn("What The Images Show", package["body_markdown"])

    def test_article_draft_from_news_index_result_builds_without_x_posts(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "target_length_chars": 800})
        self.assertEqual(draft["source_summary"]["source_kind"], "news_index")
        self.assertGreaterEqual(draft["article_package"]["draft_metrics"]["citation_count"], 1)
        self.assertIn("Bottom Line", draft["article_package"]["body_markdown"])
        self.assertIn("Why This Matters", draft["article_package"]["body_markdown"])
        self.assertIn("Sources", draft["article_package"]["article_markdown"])
        self.assertNotIn("core claim(s)", draft["article_package"]["body_markdown"])
        self.assertIn("<html>", draft["preview_html"])

    def test_article_draft_bilingual_mode_emits_zh_and_en_sections(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "language_mode": "bilingual",
                "title_hint": "English title",
                "title_hint_zh": "中文标题",
                "angle_zh": "区分已确认信息和市场想象",
            }
        )
        self.assertIn("核心判断 | Bottom Line", draft["article_package"]["body_markdown"])
        self.assertIn("截至", draft["article_package"]["body_markdown"])
        self.assertIn("English title", draft["article_package"]["article_markdown"])

    def test_article_revision_preserves_citations_and_pinned_image(self) -> None:
        draft = build_article_draft({"source_result": self.build_seed_x_index_result(self.case_dir("x-revise")), "max_images": 2})
        pinned_image_id = draft["article_package"]["selected_images"][0]["asset_id"]
        revised = build_article_revision(
            {
                "draft_result": draft,
                "title_hint": "Market impact angle",
                "angle": "market impact",
                "pinned_image_ids": [pinned_image_id],
                "revision_note": "Emphasize market impact and keep the lead image.",
            }
        )
        self.assertEqual(revised["article_package"]["title"], "Market impact angle")
        self.assertEqual(revised["article_package"]["selected_images"][0]["asset_id"], pinned_image_id)
        self.assertEqual(
            revised["article_package"]["draft_metrics"]["citation_count"],
            draft["article_package"]["draft_metrics"]["citation_count"],
        )
        self.assertEqual(len(revised["revision_history"]), 1)
        self.assertEqual(len(revised["revision_log"]), 1)
        self.assertIn("market impact", revised["article_package"]["body_markdown"].lower())

    def test_article_workflow_localizes_remote_image_assets(self) -> None:
        workflow_dir = self.case_dir("workflow-remote-image")
        remote_asset = workflow_dir / "remote-source.png"
        remote_asset.write_bytes(b"remote-image")
        source_result = run_news_index(
            {
                "topic": "Remote image localization",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [{"claim_id": "claim-1", "claim_text": "A public image is available."}],
                "candidates": [
                    {
                        "source_id": "img-1",
                        "source_name": "DVIDS",
                        "source_type": "specialist_outlet",
                        "published_at": "2026-03-24T11:00:00+00:00",
                        "observed_at": "2026-03-24T11:05:00+00:00",
                        "url": "https://example.com/dvids",
                        "text_excerpt": "A public image is available.",
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                        "root_post_screenshot_path": remote_asset.resolve().as_uri(),
                        "media_summary": "Remote image summary",
                    }
                ],
            }
        )
        draft_result = build_article_draft(
            {
                "source_result": source_result,
                "asset_output_dir": str(workflow_dir / "out" / "assets"),
                "download_remote_images": True,
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        selected = draft_result["article_package"]["selected_images"]
        self.assertEqual(selected[0]["status"], "local_ready")
        self.assertTrue(Path(selected[0]["path"]).exists())
        self.assertEqual(draft_result["asset_localization"]["downloaded_count"], 1)
        self.assertIn("Status: local_ready", draft_result["report_markdown"])
        self.assertNotIn("remote_only", draft_result["report_markdown"])

    def test_revision_feedback_profiles_can_be_saved_and_applied(self) -> None:
        profile_dir = self.case_dir("feedback-profiles")
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "feedback_profile_dir": str(profile_dir),
                "persist_feedback": {
                    "scope": "global",
                    "defaults": {
                        "language_mode": "bilingual",
                        "image_strategy": "prefer_images",
                        "must_include": ["keep market relevance explicit"],
                    },
                    "notes": ["Prefer bilingual output by default."],
                },
            }
        )
        self.assertTrue(revised["saved_feedback_profiles"])
        saved_profile = Path(revised["saved_feedback_profiles"][0])
        self.assertTrue(saved_profile.exists())

        applied = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        self.assertEqual(applied["request"]["language_mode"], "bilingual")
        self.assertIn("keep market relevance explicit", applied["request"]["must_include"])
        self.assertIn("Applied feedback profiles", " ".join(applied["article_package"]["editor_notes"]))

    def test_revision_feedback_profiles_can_capture_current_request_defaults(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-current-request")
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "feedback_profile_dir": str(profile_dir),
                "language_mode": "bilingual",
                "image_strategy": "prefer_images",
                "draft_mode": "image_first",
                "must_include": ["lead with the latest confirmed development"],
                "persist_feedback": {
                    "scope": "topic",
                    "use_current_request_defaults": True,
                    "notes": ["Carry this article style for this topic."],
                },
            }
        )
        self.assertTrue(revised["saved_feedback_profiles"])
        applied = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "feedback_profile_dir": str(profile_dir),
                "topic": draft["request"]["topic"],
            }
        )
        self.assertEqual(applied["request"]["language_mode"], "bilingual")
        self.assertEqual(applied["request"]["image_strategy"], "prefer_images")
        self.assertEqual(applied["request"]["draft_mode"], "image_first")
        self.assertIn("lead with the latest confirmed development", applied["request"]["must_include"])

    def test_article_workflow_runs_from_x_request_and_writes_revision_template(self) -> None:
        workflow_dir = self.case_dir("workflow-run")
        result = run_article_workflow(
            {
                **self.build_seed_x_request(workflow_dir),
                "output_dir": str(workflow_dir / "out"),
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 2,
            }
        )
        self.assertEqual(result["source_stage"]["source_kind"], "x_index")
        self.assertTrue(Path(result["source_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["preview_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["revision_template_path"]).exists())
        draft_result = read_json(Path(result["draft_stage"]["result_path"]))
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["citation_count"], 1)
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["image_count"], 1)
        revision_template = read_json(Path(result["review_stage"]["revision_template_path"]))
        self.assertEqual(revision_template["persist_feedback"]["use_current_request_defaults"], True)
        self.assertIn("feedback_profile_status", revision_template)
        self.assertIn("language_mode", revision_template)
        self.assertIn("image_strategy", revision_template)
        self.assertIn("## Images", result["report_markdown"])
        self.assertIn("## Feedback Reuse", result["report_markdown"])

    def test_article_cleanup_runtime_removes_old_dirs_and_keeps_recent(self) -> None:
        cleanup_root = self.case_dir("cleanup-runtime")
        old_dir = cleanup_root / "article-workflow-old"
        recent_dir = cleanup_root / "article-workflow-recent"
        old_dir.mkdir(parents=True, exist_ok=True)
        recent_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "article-draft-result.json").write_text("{}", encoding="utf-8")
        (recent_dir / "article-draft-result.json").write_text("{}", encoding="utf-8")

        seven_days_ago = time() - 7 * 24 * 60 * 60
        recent_timestamp = time()
        os.utime(old_dir, (seven_days_ago, seven_days_ago))
        os.utime(old_dir / "article-draft-result.json", (seven_days_ago, seven_days_ago))
        os.utime(recent_dir, (recent_timestamp, recent_timestamp))
        os.utime(recent_dir / "article-draft-result.json", (recent_timestamp, recent_timestamp))

        result = cleanup_article_temp_dirs({"root_dir": str(cleanup_root), "retention_days": 4})
        self.assertEqual(result["removed_count"], 1)
        self.assertFalse(old_dir.exists())
        self.assertTrue(recent_dir.exists())

    def test_article_workflow_reports_cleanup_stage(self) -> None:
        workflow_dir = self.case_dir("workflow-cleanup-report")
        stale_dir = workflow_dir / "article-workflow-stale"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_file = stale_dir / "article-draft-result.json"
        stale_file.write_text("{}", encoding="utf-8")
        old_timestamp = time() - 7 * 24 * 60 * 60
        os.utime(stale_dir, (old_timestamp, old_timestamp))
        os.utime(stale_file, (old_timestamp, old_timestamp))

        result = run_article_workflow(
            {
                **self.build_seed_x_request(workflow_dir),
                "output_dir": str(workflow_dir / "out"),
                "cleanup_enabled": True,
                "cleanup_days": 4,
                "cleanup_root_dir": str(workflow_dir),
            }
        )
        self.assertIn("## Cleanup", result["report_markdown"])
        self.assertFalse(stale_dir.exists())

    def test_article_batch_workflow_builds_review_queue(self) -> None:
        batch_dir = self.case_dir("batch-run")
        result = run_article_batch_workflow(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(batch_dir / "out"),
                "default_draft_mode": "image_first",
                "default_image_strategy": "prefer_images",
                "items": [
                    {
                        "label": "x-seed",
                        "payload": self.build_seed_x_request(batch_dir / "x-seed"),
                    },
                    {
                        "label": "news-seed",
                        "payload": self.news_request,
                        "draft_mode": "balanced",
                    },
                ],
            }
        )
        self.assertEqual(result["total_items"], 2)
        self.assertEqual(result["succeeded_items"], 2)
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(Path(result["items"][0]["workflow_result_path"]).exists())
        self.assertTrue(Path(result["items"][1]["workflow_result_path"]).exists())
        self.assertTrue(Path(result["items"][0]["preview_path"]).exists())
        self.assertTrue(Path(result["items"][1]["preview_path"]).exists())
        self.assertTrue(Path(result["items"][0]["revision_template_path"]).exists())
        self.assertTrue(Path(result["items"][1]["revision_template_path"]).exists())
        self.assertIn("Local images ready", result["report_markdown"])

    def test_article_auto_queue_ranks_candidates_and_runs_batch_for_top_items(self) -> None:
        auto_dir = self.case_dir("auto-run")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "prefer_visuals": True,
                "candidates": [
                    {
                        "label": "x-candidate",
                        "payload": self.build_seed_x_request(auto_dir / "x-candidate"),
                    },
                    {
                        "label": "news-candidate",
                        "payload": self.news_request,
                    },
                ],
            }
        )
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["selected_count"], 1)
        self.assertGreaterEqual(result["ranked_candidates"][0]["priority_score"], result["ranked_candidates"][1]["priority_score"])
        self.assertEqual(result["ranked_candidates"][0]["label"], "x-candidate")
        self.assertTrue(Path(result["batch_result"]["result_path"]).exists())
        self.assertTrue(Path(result["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
