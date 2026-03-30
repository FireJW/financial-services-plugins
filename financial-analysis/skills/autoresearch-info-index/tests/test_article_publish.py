from __future__ import annotations

import py_compile
import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import run_article_publish
from hot_topic_discovery_runtime import run_hot_topic_discovery


class ArticlePublishRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-article-publish"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def manual_topic_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI agent hiring rebound becomes a business story",
                "summary": "Multiple sources debate whether hiring demand is really returning and what it means for startups.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-agent-hiring",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "36kr reports hiring is returning at selected AI agent startups.",
                    },
                    {
                        "source_name": "zhihu",
                        "source_type": "social",
                        "url": "https://example.com/zhihu-agent-hiring",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "Zhihu users debate whether the rebound reflects real demand or another short-lived wave.",
                    },
                    {
                        "source_name": "google-news-search",
                        "source_type": "major_news",
                        "url": "https://example.com/google-agent-hiring",
                        "published_at": "2026-03-29T10:15:00+00:00",
                        "summary": "Overseas outlets argue the real shortage is operators who can ship business outcomes.",
                    },
                ],
            },
            {
                "title": "Celebrity airport outfit goes viral again",
                "summary": "A pure entertainment topic with very little business relevance.",
                "source_items": [
                    {
                        "source_name": "weibo",
                        "source_type": "social",
                        "url": "https://example.com/weibo-celebrity",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "Mostly image-driven social chatter.",
                    }
                ],
            },
        ]

    def test_hot_topic_discovery_ranks_business_candidate_first(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "top_n": 2,
            }
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["ranked_topics"]), 2)
        self.assertEqual(result["ranked_topics"][0]["title"], "AI agent hiring rebound becomes a business story")
        self.assertGreater(
            result["ranked_topics"][0]["score_breakdown"]["total_score"],
            result["ranked_topics"][1]["score_breakdown"]["total_score"],
        )
        self.assertIn("Hot Topic Discovery", result["report_markdown"])

    def test_article_publish_exports_wechat_draft_package(self) -> None:
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir),
                "draft_mode": "balanced",
            }
        )
        package = result["publish_package"]
        payload = package["draftbox_payload_template"]["articles"][0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected_topic"]["title"], "AI agent hiring rebound becomes a business story")
        self.assertTrue(Path(result["wechat_html_path"]).exists())
        self.assertTrue(Path(result["publish_package_path"]).exists())
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")
        self.assertFalse(result["review_gate"]["approved"])
        self.assertEqual(result["push_stage"]["status"], "not_requested")
        self.assertLessEqual(len(package["digest"]), 120)
        self.assertFalse(package["push_ready"])
        self.assertEqual(package["push_readiness"]["status"], "missing_cover_image")
        self.assertTrue(package["push_readiness"]["credentials_required"])
        self.assertEqual(package["push_readiness"]["cover_source"], "missing")
        self.assertEqual(payload["title"], package["title"])
        self.assertEqual(payload["content"], package["content_html"])
        self.assertEqual(payload["thumb_media_id"], "{{WECHAT_THUMB_MEDIA_ID}}")
        self.assertIn("run_wechat_push_draft.cmd", result["next_push_command"])
        self.assertIn("Human Review Gate", result["report_markdown"])
        self.assertIn("Publish Readiness", result["report_markdown"])

    def test_article_publish_can_be_push_ready_with_explicit_cover_override(self) -> None:
        cover_path = self.temp_dir / "cover.png"
        cover_path.write_bytes(b"fake-cover")
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "output_dir": str(self.temp_dir / "with-cover"),
                "cover_image_path": str(cover_path),
            }
        )
        readiness = result["publish_package"]["push_readiness"]
        self.assertTrue(result["publish_package"]["push_ready"])
        self.assertEqual(readiness["status"], "ready_for_api_push")
        self.assertEqual(readiness["cover_source"], "request_override")
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")

    def test_publish_scripts_compile_cleanly(self) -> None:
        for name in [
            "hot_topic_discovery_runtime.py",
            "hot_topic_discovery.py",
            "article_publish_runtime.py",
            "article_publish.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
