from __future__ import annotations

from datetime import UTC, datetime
import py_compile
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import build_news_request_from_topic, build_publish_package, run_article_publish
from article_publish import parse_args
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

    def build_publish_request(self) -> dict:
        return {
            "account_name": "Test Account",
            "author": "Codex",
            "digest_max_chars": 120,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }

    def build_publish_workflow_result(
        self,
        *,
        selected_images: list[dict],
        draft_image_candidates: list[dict],
    ) -> dict:
        article_package = {
            "title": "Agent hiring reset",
            "subtitle": "A concise subtitle",
            "lede": "This is the opening paragraph.",
            "sections": [
                {
                    "heading": "What changed",
                    "paragraph": "The market is re-pricing the story, but the evidence still matters.",
                }
            ],
            "draft_thesis": "The rebound is real enough to matter, but still needs verification.",
            "article_markdown": "# Agent hiring reset\n\nThe market is re-pricing the story.",
            "selected_images": selected_images,
            "citations": [],
        }
        return {
            "review_result": {"article_package": article_package},
            "draft_result": {
                "draft_context": {
                    "image_candidates": draft_image_candidates,
                }
            },
        }

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
        self.assertTrue(result["ranked_topics"][0]["score_reasons"][0].startswith("新鲜度 "))
        self.assertIn("Hot Topic Discovery", result["report_markdown"])

    def test_hot_topic_discovery_applies_operator_topic_controls(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "preferred_topic_keywords": ["AI", "agent"],
                "excluded_topic_keywords": ["Celebrity"],
                "min_source_count": 2,
                "top_n": 5,
            }
        )
        self.assertEqual(len(result["ranked_topics"]), 1)
        self.assertEqual(result["ranked_topics"][0]["title"], "AI agent hiring rebound becomes a business story")
        self.assertEqual(result["filtered_out_topics"][0]["title"], "Celebrity airport outfit goes viral again")
        self.assertIn("Preferred keywords: AI, agent", result["report_markdown"])
        self.assertIn("Filtered out topics: 1", result["report_markdown"])

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
        self.assertEqual(package["editor_anchor_mode"], "hidden")
        self.assertEqual(payload["title"], package["title"])
        self.assertEqual(payload["content"], package["content_html"])
        self.assertEqual(payload["thumb_media_id"], "{{WECHAT_THUMB_MEDIA_ID}}")
        self.assertNotIn(package["editor_anchors"][0]["text"], package["content_html"])
        self.assertIn("run_wechat_push_draft.cmd", result["next_push_command"])
        self.assertIn("Human Review Gate", result["report_markdown"])
        self.assertIn("Publish Readiness", result["report_markdown"])
        self.assertNotIn("Chinese business and investing readers", package["content_markdown"])
        self.assertNotIn("AI and technology readers will care", package["content_markdown"])
        self.assertNotIn("真实事件、趋势或争议", package["content_markdown"])
        self.assertNotIn("有解释价值，不只是情绪型热度", package["content_markdown"])
        self.assertNotIn("google-news-search, 36kr", package["content_markdown"])
        self.assertNotIn("现在最直接的观察对象是", package["content_markdown"])
        self.assertIn("最先能确认的变化其实很具体", package["content_markdown"])
        self.assertIn("这轮讨论没有很快掉下去", package["content_markdown"])
        self.assertIn("接下来最该盯的", package["content_markdown"])
        self.assertIn("更实", package["content_markdown"])

    def test_article_publish_chinese_mode_localizes_sources_and_title(self) -> None:
        request = {
            "analysis_time": "2026-03-29T10:30:00+00:00",
            "manual_topic_candidates": self.manual_topic_candidates(),
            "audience_keywords": ["AI", "business", "investing", "industry"],
            "account_name": "Test Account",
            "author": "Codex",
            "output_dir": str(self.temp_dir / "zh-article"),
            "draft_mode": "balanced",
            "language_mode": "chinese",
            "max_images": 2,
        }
        result = run_article_publish(request)
        package = result["publish_package"]

        self.assertEqual(package["article_framework"], "deep_analysis")
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in package["title"]))
        self.assertIn("## 来源", package["content_markdown"])
        self.assertNotEqual(package["article_framework"], "story")
        self.assertIn("接下来最该盯的", package["content_markdown"])
        self.assertIn("更实", package["content_markdown"])

    def test_article_publish_chinese_mode_strips_noisy_source_branding_title_copy(self) -> None:
        noisy_candidates = [
            {
                "title": "MicroYuan completes A+ round financing | 36kr first release: what is confirmed, what is not",
                "summary": "A biotech AI startup announced financing and a new collaboration platform.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-weiyuan",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "36kr reports the financing round and platform release.",
                    }
                ],
            }
        ]
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": noisy_candidates,
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "zh-noisy-title"),
                "language_mode": "chinese",
            }
        )
        package = result["publish_package"]
        self.assertNotIn("36kr", package["title"].lower())
        self.assertNotIn("first release", package["title"].lower())
        self.assertNotIn("what is confirmed", package["title"].lower())
        self.assertIn("## \u6765\u6e90", package["content_markdown"])

    def test_build_news_request_from_topic_adds_clean_public_title_and_bilingual_fields(self) -> None:
        selected_topic = {
            "title": "微元合成获3亿元A+轮融资，联合发布AI生物计算开放合作平台 | 36氪首发：哪些已经确认，哪些仍未确认",
            "summary": "一家 AI 生物计算公司完成融资并发布平台。",
            "keywords": ["AI", "融资", "平台"],
            "score_breakdown": {"relevance": 70, "debate": 55},
            "source_count": 2,
            "source_items": [
                {
                    "source_name": "36kr",
                    "source_type": "major_news",
                    "url": "https://example.com/36kr-weiyuan",
                    "published_at": "2026-03-29T10:00:00+00:00",
                    "summary": "36kr reports the financing round and platform release.",
                }
            ],
        }
        request = build_news_request_from_topic(
            selected_topic,
            {
                "analysis_time": datetime(2026, 3, 29, 10, 30, tzinfo=UTC),
                "topic": "",
            },
        )

        self.assertEqual(request["topic"], "微元合成获3亿元A+轮融资，联合发布AI生物计算开放合作平台")
        self.assertTrue(all(item.get("claim_text_zh") for item in request["claims"]))
        self.assertTrue(request["market_relevance_zh"])
        self.assertIn("哪些事实已经能被多源确认", request["questions"][0])
        self.assertEqual(request["claims"][0]["claim_text_zh"], "微元合成获3亿元A+轮融资")
        self.assertEqual(request["claims"][1]["claim_text_zh"], "联合发布AI生物计算开放合作平台")
        self.assertNotIn("真实事件、趋势或争议", request["claims"][0]["claim_text_zh"])

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
                "wechat_app_id": "wx-test",
                "wechat_app_secret": "secret",
                "allow_insecure_inline_credentials": True,
            }
        )
        readiness = result["publish_package"]["push_readiness"]
        self.assertTrue(result["publish_package"]["push_ready"])
        self.assertEqual(readiness["status"], "ready_for_api_push")
        self.assertEqual(readiness["cover_source"], "request_override")
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")

    def test_build_publish_package_prefers_dedicated_cover_candidate_before_body_fallback(self) -> None:
        body_image = self.temp_dir / "body-screenshot.png"
        dedicated_cover = self.temp_dir / "dedicated-cover.png"
        body_image.write_bytes(b"body-screenshot")
        dedicated_cover.write_bytes(b"dedicated-cover")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-01",
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body screenshot",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body screenshot",
                    "source_name": "fixture",
                    "score": 88,
                },
                {
                    "image_id": "IMG-02",
                    "role": "post_media",
                    "path": str(dedicated_cover),
                    "source_url": "",
                    "summary": "Dedicated cover image",
                    "source_name": "fixture",
                    "score": 72,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-02")
        self.assertEqual(package["cover_plan"]["selection_mode"], "dedicated_candidate")
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertIn("Prefer a text-free cover", package["cover_plan"]["cover_prompt"])
        self.assertIn("No Chinese text", package["cover_plan"]["cover_prompt"])

    def test_build_publish_package_falls_back_to_first_usable_body_image_when_no_dedicated_cover_exists(self) -> None:
        body_image = self.temp_dir / "body-hero.png"
        body_image.write_bytes(b"body-hero")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-11",
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 80,
                }
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-11")
        self.assertEqual(package["cover_plan"]["selection_mode"], "body_image_fallback")
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "article_image")

    def test_build_publish_package_can_render_editor_anchors_inline_when_requested(self) -> None:
        workflow_result = {
            "review_result": {
                "article_package": {
                    "title": "Agent hiring reset",
                    "subtitle": "A concise subtitle",
                    "lede": "This is the opening paragraph.",
                    "sections": [
                        {"heading": "What changed", "paragraph": "Paragraph one."},
                        {"heading": "Why this matters", "paragraph": "Paragraph two."},
                    ],
                    "draft_thesis": "The rebound is real enough to matter.",
                    "article_markdown": "# Agent hiring reset",
                    "selected_images": [],
                    "citations": [],
                }
            },
            "draft_result": {"draft_context": {"image_candidates": []}},
        }
        request = self.build_publish_request()
        request["editor_anchor_mode"] = "inline"
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        self.assertEqual(package["editor_anchor_mode"], "inline")
        self.assertEqual(package["editor_anchor_visibility"], "visible_inline")
        self.assertIn(package["editor_anchors"][0]["text"], package["content_html"])
        self.assertIn("编辑锚点", package["content_html"])

    def test_article_publish_cli_accepts_hyphenated_framework_alias(self) -> None:
        with patch.object(sys, "argv", ["article_publish.py", "--article-framework", "hot-comment"]):
            args = parse_args()
        self.assertEqual(args.article_framework, "hot_comment")

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
