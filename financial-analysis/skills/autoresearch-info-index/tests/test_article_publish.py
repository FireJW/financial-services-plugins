from __future__ import annotations

from datetime import UTC, datetime
import json
import py_compile
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import (
    build_news_request_from_topic,
    build_publish_package,
    build_regression_checks,
    build_report_markdown,
    normalize_request,
    run_article_publish,
)
from article_publish import parse_args
from article_publish_regression_check import parse_args as parse_regression_check_args
from article_publish_regression_check_runtime import run_publish_regression_check
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
        citations: list[dict] | None = None,
        style_profile_applied: dict | None = None,
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
            "citations": citations or [],
            "style_profile_applied": style_profile_applied or {},
        }
        return {
            "review_result": {"article_package": article_package},
            "draft_result": {
                "draft_context": {
                    "image_candidates": draft_image_candidates,
                }
            },
        }

    def test_normalize_request_inherits_author_from_feedback_profile(self) -> None:
        profile_dir = self.temp_dir / "feedback-profile-author"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "global.json").write_text(
            json.dumps(
                {
                    "scope": "global",
                    "topic": "global",
                    "request_defaults": {
                        "author": "不万能的阿伟",
                        "language_mode": "chinese",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        request = normalize_request(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "account_name": "Test Account",
                "feedback_profile_dir": str(profile_dir),
            }
        )

        self.assertEqual(request["author"], "不万能的阿伟")
        self.assertEqual(request["feedback_profile_dir"], str(profile_dir))

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
        self.assertTrue(Path(result["automatic_acceptance_path"]).exists())
        self.assertTrue(Path(result["automatic_acceptance_report_path"]).exists())
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")
        self.assertFalse(result["review_gate"]["approved"])
        self.assertEqual(result["publication_readiness"], "ready")
        self.assertEqual(result["workflow_manual_review"]["status"], "not_required")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertEqual(result["automatic_acceptance"]["status"], "accepted")
        self.assertEqual(result["automatic_acceptance"]["workflow_publication_gate"]["publication_readiness"], "ready")
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
        self.assertIn("Automatic Acceptance", result["report_markdown"])
        self.assertIn("Publish Readiness", result["report_markdown"])
        self.assertNotIn("Chinese business and investing readers", package["content_markdown"])
        self.assertNotIn("AI and technology readers will care", package["content_markdown"])
        self.assertNotIn("真实事件、趋势或争议", package["content_markdown"])
        self.assertNotIn("有解释价值，不只是情绪型热度", package["content_markdown"])
        self.assertNotIn("google-news-search, 36kr", package["content_markdown"])
        self.assertNotIn("现在最直接的观察对象是", package["content_markdown"])
        self.assertIn("最先能确认的变化其实很具体", package["content_markdown"])
        self.assertIn("这轮讨论没有很快掉下去", package["content_markdown"])
        self.assertIn("## 接下来盯什么", package["content_markdown"])
        self.assertIn("第一，", package["content_markdown"])

    def test_build_publish_package_emits_shared_contract_fields(self) -> None:
        package = build_publish_package(
            self.build_publish_workflow_result(selected_images=[], draft_image_candidates=[]),
            {"title": "AI agent hiring rebound becomes a business story", "keywords": ["AI", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["contract_version"], "publish-package/v1")
        self.assertIn("content_markdown", package)
        self.assertIn("content_html", package)
        self.assertIn("platform_hints", package)
        self.assertIn("operator_notes", package)
        self.assertIn("sections", package)
        self.assertIn("cover_plan", package)
        self.assertIn("lede", package)
        self.assertIn("selected_images", package)
        self.assertIn("draft_thesis", package)
        self.assertIn("citations", package)
        self.assertIsInstance(package["platform_hints"], dict)
        self.assertIsInstance(package["operator_notes"], list)

    def test_article_publish_routes_shared_package_to_requested_channel(self) -> None:
        fake_toutiao_push_result = {
            "status": "ok",
            "push_backend": "browser_session",
            "review_gate": {"status": "approved"},
            "browser_session": {"manifest_path": "", "result_path": ""},
            "article_url": "",
            "title": "AI agent hiring rebound becomes a business story",
        }

        with patch("article_publish_runtime.push_publish_package_to_toutiao", return_value=fake_toutiao_push_result) as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "output_dir": str(self.temp_dir / "publish-channel-toutiao"),
                    "publish_channel": "toutiao",
                    "push_to_channel": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "cover_image_path": str(self.temp_dir / "cover-channel.png"),
                }
            )

        push_mock.assert_called_once()
        self.assertEqual(result["channel_push_stage"]["channel"], "toutiao")
        self.assertEqual(result["channel_push_stage"]["status"], "ok")
        self.assertEqual(result["status"], "ok")
        self.assertIn("publish_package", result)

    def test_article_publish_channel_push_does_not_duplicate_legacy_wechat_push(self) -> None:
        fake_wechat_push_result = {
            "status": "ok",
            "push_backend": "api",
            "review_gate": {"status": "approved"},
            "workflow_publication_gate": {"publication_readiness": "ready", "manual_review": {}},
            "draft_result": {"media_id": "draft-123"},
            "push_readiness": {"status": "ready_for_api_push"},
        }

        with patch("article_publish_runtime.push_publish_package_to_wechat", return_value=fake_wechat_push_result) as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "output_dir": str(self.temp_dir / "publish-channel-wechat-no-dup"),
                    "publish_channel": "wechat",
                    "push_to_channel": True,
                    "push_to_wechat": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                    "cover_image_path": str(self.temp_dir / "cover-channel-wechat.png"),
                }
            )

        push_mock.assert_called_once()
        self.assertEqual(result["channel_push_stage"]["status"], "ok")
        self.assertEqual(result["push_stage"]["status"], "not_requested")

    def test_article_publish_surfaces_workflow_publication_gate_on_result_and_acceptance(self) -> None:
        workflow_result = self.build_publish_workflow_result(
            selected_images=[],
            draft_image_candidates=[],
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 2,
            "high_priority_count": 1,
            "summary": "Queued Reddit comment signals still need operator review before publication.",
            "next_step": "Review the queued Reddit comment signals before publication.",
            "queue": [
                {
                    "title": "Semicap capex thread",
                    "priority_level": "high",
                    "summary": "Partial Reddit comment sampling still needs operator review.",
                }
            ],
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"

        with patch("article_publish_runtime.run_article_workflow", return_value=workflow_result):
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "account_name": "Test Account",
                    "author": "Codex",
                    "output_dir": str(self.temp_dir / "reddit-gate"),
                }
            )

        self.assertEqual(result["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["workflow_manual_review"]["required_count"], 2)
        self.assertEqual(
            result["automatic_acceptance"]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertEqual(
            result["automatic_acceptance"]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("## Workflow Publication Gate", result["automatic_acceptance"]["report_markdown"])
        self.assertIn("blocked_by_reddit_operator_review", result["automatic_acceptance"]["report_markdown"])
        self.assertIn("awaiting_reddit_operator_review", result["automatic_acceptance"]["report_markdown"])

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
        self.assertIn("## 接下来盯什么", package["content_markdown"])
        self.assertIn("第一，", package["content_markdown"])

    def test_article_publish_defaults_to_traffic_headline_hook_for_chinese_mode(self) -> None:
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "traffic-title"),
                "language_mode": "chinese",
            }
        )

        package = result["publish_package"]
        self.assertTrue(package["title"].startswith("刚刚，"))
        self.assertEqual(
            package["style_profile_applied"]["effective_request"]["headline_hook_mode"],
            "traffic",
        )

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

    def test_build_news_request_from_topic_uses_developer_tooling_relevance_without_business_shorthand(self) -> None:
        selected_topic = {
            "title": "Claude Code 泄露源码后，真正值得看的隐藏能力",
            "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
            "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            "score_breakdown": {"relevance": 72, "debate": 58},
            "source_count": 2,
            "source_items": [
                {
                    "source_name": "X @agintender",
                    "source_type": "social",
                    "url": "https://x.com/agintender/status/1",
                    "published_at": "2026-03-29T10:00:00+00:00",
                    "summary": "The thread walks through browser control and multi-step task execution entrypoints.",
                }
            ],
        }

        request = build_news_request_from_topic(
            selected_topic,
            {
                "analysis_time": datetime(2026, 3, 29, 10, 30, tzinfo=UTC),
                "topic": "",
                "language_mode": "chinese",
            },
        )

        joined_zh = " ".join(request["market_relevance_zh"])
        claim_zh = " ".join(item["claim_text_zh"] for item in request["claims"])
        candidate_copy = " ".join(
            str(candidate.get(field) or "").strip()
            for candidate in request["candidates"]
            for field in ("text_excerpt", "post_summary", "media_summary")
            if str(candidate.get(field) or "").strip()
        )
        self.assertIn("产品边界、工具调用与权限设计", request["market_relevance_zh"])
        self.assertIn("浏览器控制、工作流编排", request["market_relevance_zh"])
        self.assertIn("这条线程顺着浏览器控制和多步任务执行入口做了拆解。", claim_zh)
        self.assertNotIn("产品能力表面、工具调用边界和权限设计", joined_zh)
        self.assertNotIn("浏览器控制、工作流编排与多步开发者执行", joined_zh)
        self.assertNotIn("融资意愿、订单能见度和预算投放", joined_zh)
        self.assertNotIn("预算", joined_zh)
        self.assertNotIn("订单", joined_zh)
        self.assertNotIn("thread walks through browser control", claim_zh.lower())
        self.assertNotIn("thread walks through browser control", candidate_copy.lower())
        self.assertNotIn("Official docs describe Claude Code browser control and Chrome integration", candidate_copy)

    def test_article_publish_preserves_manual_screenshot_enrichment_and_uses_screenshot_cover(self) -> None:
        screenshot_path = self.temp_dir / "claude-code-root.png"
        screenshot_path.write_bytes(b"claude-code-root")

        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "Claude Code 泄露源码后，真正值得看的 7 个秘密功能",
                        "summary": "The leaked code and docs point to browser control, tool use boundaries, and workflow orchestration changes.",
                        "source_items": [
                            {
                                "source_name": "X @agintender",
                                "source_type": "social",
                                "url": "https://x.com/agintender/status/2038921508999901274",
                                "published_at": "2026-03-29T10:00:00+00:00",
                                "summary": "The thread captures browser control entrypoints, subagents, and permission boundaries.",
                                "root_post_screenshot_path": str(screenshot_path),
                                "artifact_manifest": [
                                    {
                                        "role": "root_post_screenshot",
                                        "path": str(screenshot_path),
                                        "summary": "Screenshot of the original X thread discussing Claude Code hidden capabilities.",
                                    }
                                ],
                                "post_summary": "Screenshot-backed thread about Claude Code browser control and hidden capabilities.",
                            },
                            {
                                "source_name": "Anthropic docs / Chrome",
                                "source_type": "major_news",
                                "url": "https://docs.anthropic.com/en/docs/claude-code/chrome",
                                "published_at": "2026-03-29T09:50:00+00:00",
                                "summary": "Official docs describe Claude Code browser control and Chrome integration.",
                            },
                        ],
                    }
                ],
                "audience_keywords": ["Claude Code", "developer tools", "workflow", "browser"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "claude-code-screenshot-publish"),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
                "target_length_chars": 2800,
                "headline_hook_mode": "traffic",
                "max_images": 2,
            }
        )

        selected_source = result["selected_topic"]["source_items"][0]
        self.assertEqual(selected_source["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(selected_source["artifact_manifest"]), 1)

        news_request = json.loads(Path(result["news_request_path"]).read_text(encoding="utf-8-sig"))
        candidate = news_request["candidates"][0]
        self.assertEqual(candidate["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(candidate["artifact_manifest"]), 1)

        draft_result = json.loads(Path(result["workflow_stage"]["draft_result_path"]).read_text(encoding="utf-8-sig"))
        package = draft_result["article_package"]
        headings = [section["heading"] for section in package["sections"]]
        joined_text = "\n".join([package["lede"], *(section["paragraph"] for section in package["sections"])])

        self.assertGreaterEqual(len(package["selected_images"]), 1)
        self.assertEqual(package["selected_images"][0]["role"], "root_post_screenshot")
        self.assertTrue(package["selected_images"][0]["caption"])
        self.assertNotIn("登录", package["selected_images"][0]["caption"])
        self.assertNotIn("/url:", package["selected_images"][0]["caption"])
        self.assertGreaterEqual(len(package["sections"]), 6)
        self.assertIn("哪些已经确认，哪些还不能写死", headings)
        self.assertIn("这件事的分水岭在哪", headings)
        self.assertNotIn("预算", joined_text)
        self.assertNotIn("订单", joined_text)
        self.assertNotIn("定价", joined_text)
        self.assertNotIn("经营变量", joined_text)
        self.assertNotIn("登录", joined_text)
        self.assertNotIn("/url:", joined_text)

        publish_package = result["publish_package"]
        self.assertEqual(publish_package["cover_plan"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(publish_package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(publish_package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertIn("screenshot cover candidate", publish_package["cover_plan"]["selection_reason"].lower())
        self.assertIn("真正值得看的", publish_package["title"])
        self.assertFalse(publish_package["title"].startswith("刚刚，"))
        self.assertNotEqual(publish_package["title"], "刚刚，Claude Code 泄露源码后")
        self.assertNotIn("产品能力表面、工具调用边界和权限设计", publish_package["content_markdown"])
        self.assertNotIn("浏览器控制、工作流编排与多步开发者执行", publish_package["content_markdown"])
        self.assertNotIn("登录", publish_package["content_markdown"])
        self.assertNotIn("/url:", publish_package["content_markdown"])
        self.assertLessEqual(publish_package["content_markdown"].count("产品边界、权限设计"), 1)
        self.assertLessEqual(publish_package["content_markdown"].count("浏览器控制、工作流编排"), 1)
        self.assertLessEqual(publish_package["content_markdown"].count("能力边界和开发者工作流"), 1)
        self.assertEqual(
            publish_package["cover_plan"]["selection_reason"],
            publish_package["cover_plan"]["cover_selection_reason"],
        )
        self.assertTrue(publish_package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("登录", publish_package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("/url:", publish_package["cover_plan"]["selected_cover_caption"])
        regression = publish_package["regression_checks"]
        self.assertEqual(regression["section_count"], 7)
        self.assertEqual(regression["target_length_chars"], 2800)
        self.assertGreaterEqual(regression["body_char_count"], 2100)
        self.assertGreaterEqual(regression["content_char_count"], 2200)
        self.assertTrue(regression["checks"]["title_complete"])
        self.assertTrue(regression["checks"]["expanded_sections_ok"])
        self.assertTrue(regression["checks"]["ui_capture_noise_clean"])
        self.assertTrue(regression["checks"]["generic_business_talk_clean"])
        self.assertTrue(regression["checks"]["developer_focus_copy_clean"])
        self.assertTrue(regression["checks"]["developer_focus_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_transition_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_tail_tone_clean"])
        self.assertLessEqual(max(regression["developer_focus_phrase_hits"].values(), default=0), 1)
        self.assertEqual(sum(regression["wechat_tail_tone_phrase_hits"].values()), 0)
        self.assertTrue(regression["checks"]["localized_copy_expected"])
        self.assertTrue(regression["checks"]["localized_copy_clean"])
        self.assertTrue(regression["checks"]["first_image_is_screenshot"])
        self.assertTrue(regression["checks"]["screenshot_cover_preferred"])
        self.assertTrue(regression["checks"]["cover_reason_present"])
        self.assertTrue(regression["checks"]["cover_caption_clean"])
        self.assertEqual(regression["cover"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(regression["cover"]["cover_source"], "dedicated_cover_candidate")
        self.assertEqual(regression["first_image"]["role"], "root_post_screenshot")
        self.assertTrue(regression["first_image"]["caption"])
        self.assertFalse(regression["english_leak_samples"])
        self.assertEqual(regression["forbidden_phrase_hits"]["登录"], 0)
        self.assertEqual(regression["forbidden_phrase_hits"]["/url:"], 0)
        self.assertLessEqual(max(regression["wechat_transition_phrase_hits"].values(), default=0), 1)
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertFalse(result["automatic_acceptance"]["decision_required"])
        self.assertFalse(result["automatic_acceptance"]["optimization_options"])
        self.assertFalse(result["automatic_acceptance"]["advisory_options"])

    def test_article_publish_prefer_images_keeps_screenshot_cover_with_mixed_visual_candidates(self) -> None:
        screenshot_path = self.temp_dir / "claude-code-mixed-root.png"
        media_path = self.temp_dir / "claude-code-mixed-media.png"
        screenshot_path.write_bytes(b"claude-code-mixed-root")
        media_path.write_bytes(b"claude-code-mixed-media")

        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "Claude Code 娉勯湶婧愮爜鍚庯紝鐪熸鍊煎緱鐪嬬殑 7 涓瀵嗗姛鑳?",
                        "summary": "The leaked code and docs point to browser control, tool use boundaries, and workflow orchestration changes.",
                        "source_items": [
                            {
                                "source_name": "X @agintender",
                                "source_type": "social",
                                "url": "https://x.com/agintender/status/2038921508999901274",
                                "published_at": "2026-03-29T10:00:00+00:00",
                                "summary": "The thread captures browser control entrypoints, subagents, and permission boundaries.",
                                "root_post_screenshot_path": str(screenshot_path),
                                "artifact_manifest": [
                                    {
                                        "role": "root_post_screenshot",
                                        "path": str(screenshot_path),
                                        "summary": "Screenshot of the original X thread discussing Claude Code hidden capabilities.",
                                    }
                                ],
                                "media_items": [
                                    {
                                        "source_url": "https://pbs.twimg.com/media/claude-code-hidden-capabilities.jpg",
                                        "local_artifact_path": str(media_path),
                                        "ocr_text_raw": "Browser mode entrypoint shown next to remote control and workflow panels.",
                                    }
                                ],
                                "post_summary": "Screenshot-backed thread about Claude Code browser control and hidden capabilities.",
                                "media_summary": "Browser-captured image from the original X post showing workflow panels.",
                            },
                            {
                                "source_name": "Anthropic docs / Chrome",
                                "source_type": "major_news",
                                "url": "https://docs.anthropic.com/en/docs/claude-code/chrome",
                                "published_at": "2026-03-29T09:50:00+00:00",
                                "summary": "Official docs describe Claude Code browser control and Chrome integration.",
                            },
                        ],
                    }
                ],
                "audience_keywords": ["Claude Code", "developer tools", "workflow", "browser"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "claude-code-prefer-images-mixed-publish"),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "target_length_chars": 2800,
                "headline_hook_mode": "traffic",
                "max_images": 2,
            }
        )

        selected_source = result["selected_topic"]["source_items"][0]
        self.assertEqual(selected_source["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(selected_source["artifact_manifest"]), 1)
        self.assertEqual(len(selected_source["media_items"]), 1)
        self.assertEqual(selected_source["media_items"][0]["local_artifact_path"], str(media_path))

        news_request = json.loads(Path(result["news_request_path"]).read_text(encoding="utf-8-sig"))
        candidate = news_request["candidates"][0]
        self.assertEqual(candidate["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(candidate["artifact_manifest"]), 1)
        self.assertEqual(len(candidate["media_items"]), 1)
        self.assertEqual(candidate["media_items"][0]["local_artifact_path"], str(media_path))

        draft_result = json.loads(Path(result["workflow_stage"]["draft_result_path"]).read_text(encoding="utf-8-sig"))
        package = draft_result["article_package"]
        selected_images = package["selected_images"]
        selected_roles = [item["role"] for item in selected_images]
        post_media = next(item for item in selected_images if item["role"] == "post_media")

        self.assertGreaterEqual(len(selected_images), 2)
        self.assertEqual(selected_images[0]["role"], "root_post_screenshot")
        self.assertNotEqual(selected_images[0]["caption"], selected_source["media_summary"])
        self.assertIn("post_media", selected_roles)
        self.assertEqual(post_media["path"], str(media_path))
        self.assertEqual(post_media["status"], "local_ready")
        self.assertNotEqual(selected_images[0]["path"], post_media["path"])
        self.assertEqual(
            selected_images[0]["caption"],
            "这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力。",
        )
        self.assertEqual(
            post_media["caption"],
            "图里能看到浏览器模式入口，旁边就是远程控制和工作流面板。",
        )

        publish_package = result["publish_package"]
        cover_candidates = publish_package["cover_plan"]["cover_candidates"]
        cover_candidate_roles = [item["role"] for item in cover_candidates]

        self.assertEqual(cover_candidates[0]["role"], "post_media")
        self.assertIn("post_media", cover_candidate_roles)
        self.assertIn("root_post_screenshot", cover_candidate_roles)
        self.assertEqual(publish_package["cover_plan"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(publish_package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(publish_package["push_readiness"]["cover_source"], "dedicated_cover_candidate")

        regression = publish_package["regression_checks"]
        self.assertTrue(regression["checks"]["first_image_is_screenshot"])
        self.assertTrue(regression["checks"]["screenshot_cover_preferred"])
        self.assertTrue(regression["checks"]["localized_copy_expected"])
        self.assertTrue(regression["checks"]["localized_copy_clean"])
        self.assertEqual(regression["first_image"]["role"], "root_post_screenshot")
        self.assertEqual(regression["cover"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(regression["cover"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(regression["cover"]["cover_source"], "dedicated_cover_candidate")
        self.assertGreaterEqual(regression["body_char_count"], 2300)
        self.assertGreaterEqual(regression["content_char_count"], 2900)
        self.assertFalse(regression["english_leak_samples"])
        self.assertLessEqual(max(regression["developer_focus_phrase_hits"].values(), default=0), 1)
        self.assertTrue(regression["checks"]["wechat_transition_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_tail_tone_clean"])
        self.assertLessEqual(max(regression["wechat_transition_phrase_hits"].values(), default=0), 1)
        self.assertEqual(sum(regression["wechat_tail_tone_phrase_hits"].values()), 0)
        self.assertNotIn("Official docs describe Claude Code", publish_package["content_markdown"])
        self.assertNotIn("thread captures browser control", publish_package["content_markdown"].lower())
        self.assertNotIn("Browser mode entrypoint shown next to remote control", publish_package["content_markdown"])
        self.assertNotIn("Screenshot-backed thread about Claude Code", publish_package["content_markdown"])
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertFalse(result["automatic_acceptance"]["advisory_options"])

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
        self.assertIn("dedicated cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertIn("Prefer a text-free cover", package["cover_plan"]["cover_prompt"])
        self.assertIn("No Chinese text", package["cover_plan"]["cover_prompt"])

    def test_build_publish_package_prefers_clean_body_caption_for_screenshot_cover(self) -> None:
        body_image = self.temp_dir / "body-screenshot-clean.png"
        body_image.write_bytes(b"body-screenshot-clean")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-01",
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "原始帖子截图，保留了页面上下文。",
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
                    "summary": '- text: 新鲜事一网打尽 - link "登录": - /url: /login - progressbar "加载中":',
                    "source_name": "fixture",
                    "score": 88,
                }
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "Claude Code 真正值得看的 7 个秘密功能", "keywords": ["Claude Code", "browser", "workflow"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-01")
        self.assertEqual(package["cover_plan"]["selected_cover_caption"], "原始帖子截图，保留了页面上下文。")
        self.assertNotIn("登录", package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("/url:", package["cover_plan"]["selected_cover_caption"])

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
        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertIn("screenshot cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertTrue(package["regression_checks"]["checks"]["screenshot_cover_preferred"])
        self.assertTrue(package["regression_checks"]["checks"]["cover_reason_present"])

    def test_build_publish_package_keeps_first_body_order_when_zero_indexed(self) -> None:
        first_body = self.temp_dir / "body-first.png"
        second_body = self.temp_dir / "body-second.png"
        first_body.write_bytes(b"body-first")
        second_body.write_bytes(b"body-second")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(first_body),
                    "source_url": "",
                    "caption": "First body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                },
                {
                    "image_id": "IMG-32",
                    "role": "root_post_screenshot",
                    "path": str(second_body),
                    "source_url": "",
                    "caption": "Second body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_section_2",
                },
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(first_body),
                    "source_url": "",
                    "summary": "First body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
                {
                    "image_id": "IMG-32",
                    "role": "root_post_screenshot",
                    "path": str(second_body),
                    "source_url": "",
                    "summary": "Second body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-31")
        self.assertEqual(package["cover_plan"]["cover_candidates"][0]["body_order"], 0)
        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertIn("screenshot cover candidate", package["cover_plan"]["selection_reason"].lower())

    def test_build_publish_package_can_use_dedicated_news_page_screenshot_as_cover(self) -> None:
        body_image = self.temp_dir / "body-hero.png"
        dedicated_screenshot = self.temp_dir / "news-page-cover.png"
        body_image.write_bytes(b"body-hero")
        dedicated_screenshot.write_bytes(b"news-page-cover")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-21",
                    "image_id": "IMG-21",
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
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
                {
                    "image_id": "IMG-22",
                    "role": "article_page_screenshot",
                    "path": str(dedicated_screenshot),
                    "source_url": "",
                    "summary": "Dedicated news page screenshot",
                    "source_name": "Example News",
                    "capture_method": "page_hints",
                    "score": 82,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-22")
        self.assertEqual(package["cover_plan"]["selected_cover_role"], "article_page_screenshot")
        self.assertEqual(package["cover_plan"]["selection_mode"], "dedicated_candidate")
        self.assertIn("dedicated cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")

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

    def test_build_publish_package_uses_source_titles_and_exposes_style_profile(self) -> None:
        workflow_result = self.build_publish_workflow_result(
            selected_images=[],
            draft_image_candidates=[],
            citations=[
                {
                    "citation_id": "S1",
                    "source_name": "Reuters",
                    "title": "Iran says diplomacy still needs new terms",
                    "url": "https://example.com/reuters-story",
                    "published_at": "2026-03-26T10:00:00+00:00",
                }
            ],
            style_profile_applied={
                "global_profile_applied": True,
                "topic_profile_applied": False,
                "applied_paths": [".tmp/article-feedback-profiles/global.json"],
                "style_memory": {
                    "target_band": "3.4",
                    "sample_source_declared_count": 3,
                    "sample_source_available_count": 3,
                    "sample_source_loaded_count": 3,
                    "sample_source_missing_count": 0,
                    "sample_source_runtime_mode": "curated_profile_only",
                    "corpus_derived_transitions": ["先说结论"],
                },
            },
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 1,
            "high_priority_count": 1,
            "summary": "Queued Reddit comment signals still need operator review before publication.",
            "next_step": "Review the queued Reddit comment signals before publication.",
            "queue": [
                {
                    "title": "Semicap capex thread",
                    "priority_level": "high",
                    "summary": "Partial Reddit comment sampling still needs operator review.",
                }
            ],
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )
        report_markdown = build_report_markdown(
            {
                "selected_topic": {"title": "AI agent hiring rebound"},
                "publish_package": package,
                "manual_review": {"required": True, "approved": False, "status": "awaiting_human_review"},
                "push_stage": {},
                "discovery_stage": {},
                "workflow_stage": {},
                "next_push_command": "",
            }
        )

        self.assertNotIn("<h1", package["content_html"])
        self.assertIn("Iran says diplomacy still needs new terms", package["content_html"])
        self.assertIn("https://example.com/reuters-story", package["content_html"])
        self.assertEqual(package["style_profile_applied"]["style_memory"]["sample_source_loaded_count"], 3)
        self.assertIn("Target band: 3.4", report_markdown)
        self.assertIn("Sample source references: 3", report_markdown)
        self.assertIn("Available sample source paths: 3", report_markdown)
        self.assertIn("Runtime style source mode: curated_profile_only", report_markdown)
        self.assertIn("## Automatic Acceptance", report_markdown)
        self.assertIn("## Regression Checks", report_markdown)
        self.assertIn("Cover reason present: yes", report_markdown)
        self.assertEqual(package["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(package["workflow_manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertIn("## Workflow Reddit Operator Review", report_markdown)
        self.assertIn("Workflow queue: [high] Semicap capex thread", report_markdown)
        self.assertIn("## Optimization Options", report_markdown)

    def test_article_publish_cli_accepts_hyphenated_framework_alias(self) -> None:
        with patch.object(sys, "argv", ["article_publish.py", "--article-framework", "hot-comment"]):
            args = parse_args()
        self.assertEqual(args.article_framework, "hot_comment")

    def test_article_publish_cli_accepts_headline_hook_options(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "article_publish.py",
                "--headline-hook-mode",
                "traffic",
                "--headline-hook-prefixes",
                "刚刚，",
                "突发！",
            ],
        ):
            args = parse_args()
        self.assertEqual(args.headline_hook_mode, "traffic")
        self.assertEqual(args.headline_hook_prefixes, ["刚刚，", "突发！"])

    def test_article_publish_regression_check_cli_accepts_target(self) -> None:
        with patch.object(sys, "argv", ["article_publish_regression_check.py", "C:\\tmp\\publish-run"]):
            args = parse_regression_check_args()
        self.assertEqual(args.target, "C:\\tmp\\publish-run")

    def test_article_publish_regression_check_validates_output_dir(self) -> None:
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
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        output_dir = self.temp_dir / "publish-regression-output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["decision_required"])
        self.assertEqual(result["regression_source"], "publish_package")
        self.assertFalse(result["failures"])
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertTrue(result["regression_checks"]["checks"]["cover_reason_present"])
        self.assertIn("Publish Automatic Acceptance", result["report_markdown"])
        self.assertIn("## Workflow Publication Gate", result["report_markdown"])

    def test_article_publish_regression_check_can_fallback_to_workflow_draft(self) -> None:
        body_image = self.temp_dir / "body-hero-fallback.png"
        body_image.write_bytes(b"body-hero-fallback")
        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-21",
                    "image_id": "IMG-21",
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
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 82,
                }
            ],
        )
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )
        package.pop("regression_checks", None)

        output_dir = self.temp_dir / "publish-regression-fallback"
        workflow_dir = output_dir / "workflow"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")
        draft_result = {
            "request": request,
            "article_package": workflow_result["review_result"]["article_package"],
        }
        (workflow_dir / "article-draft-result.json").write_text(json.dumps(draft_result, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["regression_source"], "workflow_draft_fallback")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertFalse(result["regression_checks"]["checks"]["expanded_sections_expected"])
        self.assertTrue(result["regression_checks"]["checks"]["expanded_sections_ok"])
        self.assertTrue(result["regression_checks"]["checks"]["screenshot_cover_preferred"])

    def test_article_publish_regression_check_surfaces_workflow_publication_gate(self) -> None:
        body_image = self.temp_dir / "body-hero-gate.png"
        body_image.write_bytes(b"body-hero-gate")
        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-31",
                    "image_id": "IMG-31",
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
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 82,
                }
            ],
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 1,
            "high_priority_count": 1,
            "next_step": "Review the queued Reddit comment signals before publication.",
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        output_dir = self.temp_dir / "publish-regression-gate"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(
            result["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("blocked_by_reddit_operator_review", result["report_markdown"])
        self.assertIn("awaiting_reddit_operator_review", result["report_markdown"])

    def test_article_publish_regression_check_returns_optimization_options_when_changes_are_recommended(self) -> None:
        output_dir = self.temp_dir / "publish-regression-recommended"
        output_dir.mkdir(parents=True, exist_ok=True)
        package = {
            "cover_plan": {
                "selection_mode": "body_image_fallback",
                "selected_cover_role": "post_media",
                "selected_cover_asset_id": "IMG-77",
            },
            "push_readiness": {"cover_source": "article_image"},
            "regression_checks": {
                "section_count": 4,
                "section_headings": ["先看变化本身", "真正的传导链条", "接下来盯什么", "补充说明"],
                "first_image": {
                    "asset_id": "IMG-77",
                    "role": "post_media",
                    "status": "local_ready",
                    "caption": "login /url: noisy screenshot",
                    "placement": "after_lede",
                },
                "cover": {
                    "selected_cover_asset_id": "IMG-77",
                    "selected_cover_role": "post_media",
                    "selection_mode": "body_image_fallback",
                    "selection_reason": "",
                    "cover_source": "article_image",
                },
                "forbidden_phrase_hits": {
                    "登录": 1,
                    "/url:": 1,
                    "预算": 0,
                    "订单": 0,
                    "定价": 1,
                    "经营变量": 1,
                    "经营层": 0,
                    "经营和投资判断题": 0,
                },
                "checks": {
                    "expanded_sections_expected": True,
                    "expanded_sections_ok": False,
                    "ui_capture_noise_clean": False,
                    "generic_business_talk_clean": False,
                    "first_image_is_screenshot": False,
                    "screenshot_cover_preferred": False,
                    "cover_reason_present": False,
                },
            },
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "changes_recommended")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["decision_required"])
        self.assertTrue(result["failures"])
        self.assertGreaterEqual(len(result["optimization_options"]), 3)
        option_areas = {item["area"] for item in result["optimization_options"]}
        self.assertIn("structure", option_areas)
        self.assertIn("screenshot_caption", option_areas)
        self.assertIn("observability", option_areas)
        self.assertIn("workflow", result["recommended_next_action"])
        self.assertIn("Optimization Options", result["report_markdown"])

    def test_article_publish_regression_check_reports_missing_screenshot_upload_source(self) -> None:
        output_dir = self.temp_dir / "publish-regression-missing-screenshot-upload-source"
        output_dir.mkdir(parents=True, exist_ok=True)
        cover_plan = {
            "selected_cover_asset_id": "IMG-02",
            "selected_cover_role": "post_media",
            "selected_cover_caption": "Body image fallback",
            "selection_mode": "body_image_fallback",
            "selection_reason": "Falling back to body image IMG-02 because no dedicated cover candidate was ready.",
        }
        push_readiness = {
            "cover_source": "article_image",
            "missing_upload_source_asset_ids": ["IMG-01"],
        }
        regression_checks = build_regression_checks(
            {
                "title": "Claude Code screenshot fallback",
                "article_framework": "quick_take",
                "lede": "We traced why the screenshot cover fell back.",
                "sections": [
                    {
                        "heading": "What broke",
                        "paragraph": "The screenshot still appears in the body, but the publish package no longer carries a usable upload source for it.",
                    }
                ],
                "selected_images": [
                    {
                        "asset_id": "IMG-01",
                        "image_id": "IMG-01",
                        "role": "root_post_screenshot",
                        "status": "missing",
                        "caption": "Root post screenshot",
                        "placement": "after_lede",
                    },
                    {
                        "asset_id": "IMG-02",
                        "image_id": "IMG-02",
                        "role": "post_media",
                        "status": "remote_only",
                        "caption": "Body image fallback",
                        "placement": "after_section_1",
                    },
                ],
            },
            {
                "article_framework": "quick_take",
                "target_length_chars": 1200,
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "language_mode": "english",
            },
            cover_plan,
            push_readiness,
            {},
        )
        package = {
            "cover_plan": cover_plan,
            "push_readiness": push_readiness,
            "regression_checks": regression_checks,
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "changes_recommended")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["regression_checks"]["cover"]["screenshot_upload_source_missing"])
        self.assertIn(
            "Screenshot cover candidate is missing a usable upload source, so cover selection fell back to a body image.",
            result["failures"],
        )
        self.assertNotIn("Cover selection no longer prefers a screenshot path.", result["failures"])
        option_areas = {item["area"] for item in result["optimization_options"]}
        self.assertIn("cover_upload_source", option_areas)
        self.assertNotIn("cover_selection", option_areas)

    def test_build_regression_checks_flags_generic_business_talk_for_macro_topics(self) -> None:
        regression_checks = build_regression_checks(
            {
                "article_framework": "deep_analysis",
                "lede": "特朗普讲话之后，市场先交易预期。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": "如果后面继续改写预算和定价，这条线就会越走越远。",
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "特朗普今天讲话后，市场重新交易美伊战争和布油",
                "summary": "真正的核心是战争持续时间和布伦特原油会不会继续冲高。",
                "keywords": ["特朗普", "伊朗", "战争", "布油"],
            },
        )

        self.assertTrue(regression_checks["checks"]["generic_business_talk_expected"])
        self.assertFalse(regression_checks["checks"]["generic_business_talk_clean"])
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["预算"], 1)
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["定价"], 1)

    def test_build_regression_checks_flags_hanging_title_and_longhand_developer_copy(self) -> None:
        regression_checks = build_regression_checks(
            {
                "title": "刚刚，Claude Code 泄露源码后",
                "article_framework": "deep_analysis",
                "lede": "这篇文章试图解释为什么这条线索会继续发酵。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": "真正值得看的地方，还是产品能力表面、工具调用边界和权限设计，以及浏览器控制、工作流编排与多步开发者执行。",
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "Claude Code 泄露源码后，真正值得看的 7 个秘密功能",
                "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
                "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            },
        )

        self.assertFalse(regression_checks["checks"]["title_complete"])
        self.assertTrue(regression_checks["checks"]["developer_focus_copy_expected"])
        self.assertFalse(regression_checks["checks"]["developer_focus_copy_clean"])
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["产品能力表面、工具调用边界和权限设计"], 1)
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["浏览器控制、工作流编排与多步开发者执行"], 1)

    def test_build_regression_checks_tracks_repetitive_developer_focus_short_phrases(self) -> None:
        regression_checks = build_regression_checks(
            {
                "title": "Claude Code 真正值得看的 7 个秘密功能",
                "article_framework": "deep_analysis",
                "lede": "产品边界、权限设计已经反复被提起，产品边界、权限设计也开始进入正文。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": (
                            "浏览器控制、工作流编排也在反复出现。"
                            "能力边界和开发者工作流被反复复读。"
                            "哪些入口会开放、哪些权限会收口，哪些入口会开放、哪些权限会收口。"
                        ),
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "Claude Code 真正值得看的 7 个秘密功能",
                "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
                "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            },
        )

        self.assertTrue(regression_checks["checks"]["developer_focus_copy_expected"])
        self.assertTrue(regression_checks["checks"]["developer_focus_copy_clean"])
        self.assertFalse(regression_checks["checks"]["developer_focus_phrase_varied"])
        self.assertGreaterEqual(regression_checks["developer_focus_phrase_hits"]["产品边界、权限设计"], 2)
        self.assertGreaterEqual(regression_checks["developer_focus_phrase_hits"]["哪些入口会开放、哪些权限会收口"], 2)

    def test_article_publish_regression_check_returns_optional_improvements_for_threshold_pass(self) -> None:
        output_dir = self.temp_dir / "publish-regression-advisory"
        output_dir.mkdir(parents=True, exist_ok=True)
        package = {
            "cover_plan": {
                "selection_mode": "screenshot_candidate",
                "selected_cover_role": "root_post_screenshot",
                "selected_cover_asset_id": "IMG-01",
                "selection_reason": "screenshot cover candidate",
            },
            "push_readiness": {"cover_source": "dedicated_cover_candidate"},
            "regression_checks": {
                "section_count": 5,
                "target_length_chars": 2800,
                "body_char_count": 1600,
                "content_char_count": 4681,
                "section_headings": ["先看变化本身", "为什么没那么快结束", "真正的传导链条", "我的预测", "最后一句话总结"],
                "first_image": {
                    "asset_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "status": "local_ready",
                    "caption": "首页截图",
                    "placement": "after_lede",
                },
                "cover": {
                    "selected_cover_asset_id": "IMG-01",
                    "selected_cover_role": "root_post_screenshot",
                    "selected_cover_caption": "首页截图",
                    "selection_mode": "screenshot_candidate",
                    "selection_reason": "screenshot cover candidate",
                    "cover_source": "dedicated_cover_candidate",
                },
                "forbidden_phrase_hits": {
                    "登录": 0,
                    "/url:": 0,
                    "预算": 0,
                    "订单": 0,
                    "定价": 0,
                    "经营变量": 0,
                    "经营层": 0,
                    "经营和投资判断题": 0,
                },
                "developer_focus_phrase_hits": {
                    "产品边界、权限设计": 3,
                    "浏览器控制、工作流编排": 1,
                    "能力边界和开发者工作流": 1,
                    "哪些入口会开放、哪些权限会收口": 2,
                },
                "wechat_transition_phrase_hits": {
                    "换句话说": 2,
                    "反过来看": 2,
                    "真正把讨论撑住的": 1,
                    "最容易误判的地方": 1,
                    "判断有没有走到这一步": 1,
                },
                "wechat_tail_tone_phrase_hits": {
                    "默认工作流": 1,
                    "源码考古": 2,
                    "真实开发流程判断题": 1,
                },
                "checks": {
                    "expanded_sections_expected": True,
                    "expanded_sections_ok": True,
                    "ui_capture_noise_clean": True,
                    "generic_business_talk_expected": True,
                    "generic_business_talk_clean": True,
                    "developer_focus_copy_expected": True,
                    "developer_focus_copy_clean": True,
                    "developer_focus_phrase_varied": False,
                    "wechat_transition_phrase_varied": False,
                    "wechat_tail_tone_expected": True,
                    "wechat_tail_tone_clean": False,
                    "screenshot_path_expected": True,
                    "first_image_is_screenshot": True,
                    "screenshot_cover_preferred": True,
                    "cover_reason_present": True,
                    "cover_caption_clean": True,
                },
            },
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["decision_required"])
        self.assertFalse(result["optimization_options"])
        self.assertGreaterEqual(len(result["advisory_options"]), 1)
        option_areas = {item["area"] for item in result["advisory_options"]}
        self.assertIn("developer_focus_repetition_margin", option_areas)
        self.assertIn("wechat_transition_repetition_margin", option_areas)
        self.assertIn("wechat_tail_tone_margin", option_areas)
        self.assertIn("structure_margin", option_areas)
        self.assertIn("length_budget_margin", option_areas)
        self.assertIn("screenshot_caption_margin", option_areas)
        self.assertIn("可选优化项", result["recommended_next_action"])
        self.assertIn("Optional Improvements", result["report_markdown"])

    def test_publish_scripts_compile_cleanly(self) -> None:
        for name in [
            "hot_topic_discovery_runtime.py",
            "hot_topic_discovery.py",
            "article_publish_runtime.py",
            "article_publish.py",
            "article_publish_regression_check_runtime.py",
            "article_publish_regression_check.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
