from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_reuse_runtime import build_reuse_publish_result


class ArticlePublishReuseRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-article-publish-reuse"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_base_publish_result(self, *, editor_anchor_mode: str = "hidden") -> dict:
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
                "editor_anchor_mode": editor_anchor_mode,
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

    def build_revised_article_result(
        self,
        *,
        revision_manual_override: bool | None = True,
        manual_body_override: bool = False,
        manual_article_override: bool = False,
    ) -> dict:
        result = {
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
                "body_markdown": "Manual revised body for digest and review.",
                "article_markdown": "# Agent hiring reset\n\nManual revised body for digest and review.\n\n## Why it matters\n\nManual revised publish copy.",
                "selected_images": [],
                "citations": [],
            },
            "draft_context": {
                "image_candidates": [],
            },
        }
        if manual_body_override:
            result["article_package"]["manual_body_override"] = True
        if manual_article_override:
            result["article_package"]["manual_article_override"] = True
        if revision_manual_override is not None:
            result["revision_diff"] = {
                "manual_override": revision_manual_override,
            }
        return result

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
        self.assertTrue(Path(result["report_path"]).exists())
        self.assertTrue(Path(result["result_path"]).exists())

    def test_build_reuse_publish_result_preserves_manual_revised_markdown_in_chinese_mode(self) -> None:
        revised = self.build_revised_article_result()

        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(),
                "revised_article_result": revised,
                "output_dir": str(self.temp_dir / "out-manual"),
            }
        )

        expected_article_markdown = revised["article_package"]["article_markdown"]
        expected_body_markdown = revised["article_package"]["body_markdown"]

        self.assertEqual(result["publish_package"]["content_markdown"], expected_article_markdown)
        self.assertIn("Manual revised publish copy.", result["publish_package"]["content_html"])
        self.assertEqual(result["publish_package"]["digest"], expected_body_markdown)

    def test_build_reuse_publish_result_preserves_manual_markdown_from_article_package_flags(self) -> None:
        revised = self.build_revised_article_result(
            revision_manual_override=False,
            manual_body_override=True,
            manual_article_override=True,
        )

        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(),
                "revised_article_result": revised,
                "output_dir": str(self.temp_dir / "out-manual-flags"),
            }
        )

        self.assertEqual(result["publish_package"]["content_markdown"], revised["article_package"]["article_markdown"])
        self.assertEqual(result["publish_package"]["digest"], revised["article_package"]["body_markdown"])

    def test_build_reuse_publish_result_without_manual_markers_keeps_normal_publish_rebuild(self) -> None:
        revised = self.build_revised_article_result(revision_manual_override=False)

        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(),
                "revised_article_result": revised,
                "output_dir": str(self.temp_dir / "out-auto-rebuild"),
            }
        )

        self.assertNotEqual(result["publish_package"]["content_markdown"], revised["article_package"]["article_markdown"])
        self.assertNotEqual(result["publish_package"]["digest"], revised["article_package"]["body_markdown"])

    def test_build_reuse_publish_result_preserve_mode_skips_inline_editor_anchor_mutation(self) -> None:
        revised = self.build_revised_article_result(
            revision_manual_override=False,
            manual_article_override=True,
        )

        result = build_reuse_publish_result(
            {
                "base_publish_result": self.build_base_publish_result(editor_anchor_mode="inline"),
                "revised_article_result": revised,
                "output_dir": str(self.temp_dir / "out-inline-preserve"),
            }
        )

        self.assertEqual(result["publish_package"]["content_markdown"], revised["article_package"]["article_markdown"])
        self.assertNotIn("编辑锚点", result["publish_package"]["content_markdown"])

    def test_build_reuse_publish_result_preserve_mode_skips_plain_title_in_digest_and_promotes_html_heading(self) -> None:
        base_publish_result = self.build_base_publish_result()
        base_publish_result["publish_package"]["digest"] = "D" * 80
        revised = self.build_revised_article_result(
            revision_manual_override=False,
            manual_body_override=True,
            manual_article_override=True,
        )
        revised["article_package"]["body_markdown"] = (
            "Agent hiring reset\n\nManual revised body for digest and review.\n\nSecond paragraph for context."
        )
        revised["article_package"]["article_markdown"] = (
            "Agent hiring reset\n\nManual revised body for digest and review.\n\n## Why it matters\n\nManual revised publish copy."
        )

        result = build_reuse_publish_result(
            {
                "base_publish_result": base_publish_result,
                "revised_article_result": revised,
                "output_dir": str(self.temp_dir / "out-plain-title-preserve"),
            }
        )

        self.assertEqual(result["publish_package"]["content_markdown"], revised["article_package"]["article_markdown"])
        self.assertEqual(
            result["publish_package"]["digest"],
            "Manual revised body for digest and review. Second paragraph for context.",
        )
        self.assertIn("<h1>Agent hiring reset</h1>", result["publish_package"]["content_html"])
        self.assertNotIn("<p>Agent hiring reset</p>", result["publish_package"]["content_html"])


if __name__ == "__main__":
    unittest.main()
