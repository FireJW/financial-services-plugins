from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_reuse_runtime import build_reuse_publish_result
from publication_contract_runtime import validate_publication_contract


class ArticlePublishReuseRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-article-publish-reuse"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_base_publish_result(self) -> dict:
        html = "<article><h1>Agent hiring reset</h1><p>Original body</p></article>"
        return {
            "selected_topic": {
                "title": "AI agent hiring rebound",
                "keywords": ["AI", "agent", "hiring"],
            },
            "publish_package": {
                "account_name": "Test Account",
                "author": "Codex",
                "digest": "A short digest",
                "editor_anchor_mode": "hidden",
                "article_framework": "deep_analysis",
                "publication_readiness": "blocked_by_reddit_operator_review",
                "workflow_manual_review": {
                    "required": True,
                    "status": "awaiting_reddit_operator_review",
                    "required_count": 1,
                    "high_priority_count": 1,
                    "summary": "Queued Reddit comment signals still need operator review before publication.",
                    "next_step": "Review the queued Reddit comment signals before publication.",
                },
                "style_profile_applied": {
                    "effective_request": {
                        "article_framework": "deep_analysis",
                        "headline_hook_mode": "traffic",
                        "draft_mode": "balanced",
                        "image_strategy": "mixed",
                        "language_mode": "chinese",
                    }
                },
                "draftbox_payload_template": {
                    "articles": [
                        {
                            "title": "Agent hiring reset",
                            "author": "Codex",
                            "digest": "A short digest",
                            "content": html,
                            "content_source_url": "",
                            "thumb_media_id": "{{WECHAT_THUMB_MEDIA_ID}}",
                            "need_open_comment": 0,
                            "only_fans_can_comment": 0,
                        }
                    ]
                },
            },
            "workflow_stage": {
                "publication_readiness": "blocked_by_reddit_operator_review",
            },
        }

    def build_revised_article_result(self) -> dict:
        return {
            "request": {
                "headline_hook_mode": "traffic",
                "draft_mode": "balanced",
                "image_strategy": "mixed",
                "language_mode": "chinese",
            },
            "article_package": {
                "title": "Agent hiring reset",
                "subtitle": "A concise subtitle",
                "lede": "This is the opening paragraph.",
                "sections": [
                    {
                        "heading": "What changed",
                        "paragraph": "The market is re-pricing the story, but the evidence still matters.",
                    }
                ],
                "article_markdown": "# Agent hiring reset\n\nThe market is re-pricing the story.",
                "selected_images": [],
                "citations": [],
            },
            "draft_context": {
                "image_candidates": [],
            },
        }

    def test_build_reuse_publish_result_preserves_workflow_gate(self) -> None:
        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(),
                "revised_article_result": self.build_revised_article_result(),
                "output_dir": str(self.temp_dir / "out"),
            }
        )

        self.assertEqual(result["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(
            result["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertEqual(result["publish_package"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(
            result["publish_package"]["workflow_manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertEqual(
            result["automatic_acceptance"]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertIn("## Workflow Publication Gate", result["automatic_acceptance"]["report_markdown"])
        self.assertIn("Publication readiness: blocked_by_reddit_operator_review", result["report_markdown"])
        self.assertIn("Workflow Reddit operator review: awaiting_reddit_operator_review", result["report_markdown"])
        self.assertEqual(validate_publication_contract(result["publish_package"])["status"], "ok")
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertTrue(Path(result["result_path"]).exists())

    def test_build_reuse_publish_result_preserves_manual_revised_markdown(self) -> None:
        revised_result = self.build_revised_article_result()
        revised_result["article_package"]["manual_article_override"] = True
        revised_result["article_package"]["manual_body_override"] = True
        revised_result["article_package"]["article_markdown"] = (
            "# 阿联酋退出 OPEC：油价之外，更大的裂缝出现了\n\n"
            "MANUAL_MARKER_DO_NOT_REWRITE\n\n"
            "这是一段人工修订后的正文，不能再被中文发布模板覆盖。"
        )
        revised_result["article_package"]["body_markdown"] = revised_result["article_package"]["article_markdown"]

        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(),
                "revised_article_result": revised_result,
                "output_dir": str(self.temp_dir / "manual-out"),
            }
        )

        package = result["publish_package"]
        self.assertEqual(validate_publication_contract(package)["status"], "ok")
        self.assertEqual(package["title"], "阿联酋退出 OPEC：油价之外，更大的裂缝出现了")
        self.assertIn("MANUAL_MARKER_DO_NOT_REWRITE", package["content_markdown"])
        self.assertIn("MANUAL_MARKER_DO_NOT_REWRITE", package["content_html"])
        self.assertNotIn("融资意愿", package["content_markdown"])


if __name__ == "__main__":
    unittest.main()
