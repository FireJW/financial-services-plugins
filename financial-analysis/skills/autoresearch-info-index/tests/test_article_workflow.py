#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import py_compile
import unittest
from argparse import Namespace
from pathlib import Path
from time import time
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_cleanup_runtime import cleanup_article_temp_dirs
from article_brief_runtime import build_analysis_brief
from article_draft_flow_runtime import (
    build_article_draft,
    build_draft_claim_map,
    build_sections,
    chinese_watch_item,
    normalize_request as normalize_article_draft_request,
    polish_chinese_wechat_paragraph,
    requested_focus_sentences,
    split_chinese_wechat_breaths,
    topic_prefers_business_shorthand,
)
from article_feedback_markdown import parse_feedback_markdown
from article_feedback_profiles import feedback_profile_status as real_feedback_profile_status
from article_revise import build_payload as build_article_revise_payload
from article_revise_flow_runtime import build_article_revision, build_red_team_review, rewrite_request_after_attack
from article_batch_workflow_runtime import run_article_batch_workflow
from article_auto_queue_runtime import run_article_auto_queue
from article_workflow_runtime import build_revision_template, run_article_workflow, summarize_review_decisions
from macro_note_workflow_runtime import run_macro_note_workflow
from news_index_core import read_json, run_news_index
from x_index_runtime import run_x_index


class ArticleWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.news_request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.realistic_news_request = read_json(cls.examples / "news-index-realistic-offline-request.json")
        cls.temp_root = Path.cwd() / ".tmp" / "article-workflow-tests"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def empty_profile_dir(self, name: str) -> str:
        path = self.case_dir(name)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

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
                    "used_browser_session": True,
                    "session_source": "remote_debugging",
                    "session_status": "ready",
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

    def build_remote_image_source_result(self, tmpdir: Path) -> dict:
        remote_asset = tmpdir / "remote-image.png"
        remote_asset.write_bytes(b"remote-image")
        return run_news_index(
            {
                "topic": "Revision image reuse",
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

    def test_article_draft_normalize_request_applies_tech_lane_defaults(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Agentic AI reprices the semiconductor supply chain",
                "analysis_time": "2026-04-25T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "A large AI infrastructure deal is pushing compute demand upstream.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "tech-1",
                        "source_name": "The Information",
                        "source_type": "major_news",
                        "published_at": "2026-04-25T11:00:00+00:00",
                        "observed_at": "2026-04-25T11:05:00+00:00",
                        "url": "https://example.com/tech-1",
                        "text_excerpt": (
                            "Google and Anthropic are expanding TPU and GPU capacity, "
                            "pulling Broadcom, TSMC, packaging, and cloud infrastructure into focus."
                        ),
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        request = normalize_article_draft_request(
            {
                "source_result": source_result,
                "language_mode": "chinese",
            }
        )

        self.assertEqual(request["article_framework"], "deep_analysis")
        self.assertEqual(request["style_memory"]["target_band"], "tech_supply_chain_commentary")
        self.assertEqual(request["target_length_chars"], 2800)
        self.assertEqual(request["human_signal_ratio"], 72)
        self.assertIn("顺着钱的流向看下去", request["personal_phrase_bank"])
        self.assertIn(
            "把公司新闻翻译成资金流向、订单流向、产能流向或部署变量",
            request["must_include"],
        )
        self.assertTrue(request["style_memory"].get("sample_sources"))
        sample_names = [item.get("name", "") for item in request["style_memory"]["sample_sources"]]
        self.assertIn("SemiAnalysis", sample_names)
        self.assertIn("User benchmark / Nvidia real moat", sample_names)
        self.assertIn("User benchmark / TSMC ASML AI infra capex", sample_names)

    def test_article_draft_normalize_request_applies_model_governance_lane_defaults(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Musk xAI used OpenAI models to train Grok",
                "analysis_time": "2026-05-02T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "xAI and Grok are being scrutinized over whether OpenAI model outputs were used during training.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "model-1",
                        "source_name": "TechCrunch",
                        "source_type": "major_news",
                        "published_at": "2026-05-02T11:00:00+00:00",
                        "observed_at": "2026-05-02T11:05:00+00:00",
                        "url": "https://example.com/model-1",
                        "text_excerpt": (
                            "Elon Musk, xAI, OpenAI, Grok, distillation, model training, "
                            "API terms, and enterprise trust are all part of the dispute."
                        ),
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        request = normalize_article_draft_request(
            {
                "source_result": source_result,
                "language_mode": "chinese",
            }
        )

        self.assertEqual(request["article_framework"], "deep_analysis")
        self.assertEqual(request["style_memory"]["target_band"], "tech_model_governance_commentary")
        self.assertIn("先简单描述下发生了什么", request["personal_phrase_bank"])
        self.assertIn(
            "开头先抓人物或公司身份冲突，再把事实收束成一个行业边界问题",
            request["must_include"],
        )
        self.assertIn(
            "不要在开头堆媒体名单、英文标题差异或完整出处列表",
            request["must_avoid"],
        )
        self.assertIn(
            "事实段用一句“多个可靠信息来源”先收住，详细来源放到后文或文末。",
            request["style_memory"]["slot_guidance"]["facts"],
        )
        self.assertNotEqual(request["style_memory"]["target_band"], "tech_supply_chain_commentary")

    def test_article_draft_normalize_request_defaults_longform_quality_for_chinese_deep_analysis(self) -> None:
        request = normalize_article_draft_request(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
            }
        )

        self.assertEqual(request["target_length_chars"], 2400)
        self.assertEqual(request["human_signal_ratio"], 68)
        self.assertEqual(request["humanization_level"], "medium")

    def test_article_draft_normalize_request_respects_explicit_quality_overrides(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Agentic AI reprices the semiconductor supply chain",
                "analysis_time": "2026-04-25T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "A large AI infrastructure deal is pushing compute demand upstream.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "tech-1",
                        "source_name": "The Information",
                        "source_type": "major_news",
                        "published_at": "2026-04-25T11:00:00+00:00",
                        "observed_at": "2026-04-25T11:05:00+00:00",
                        "url": "https://example.com/tech-1",
                        "text_excerpt": (
                            "Google and Anthropic are expanding TPU and GPU capacity, "
                            "pulling Broadcom, TSMC, packaging, and cloud infrastructure into focus."
                        ),
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        request = normalize_article_draft_request(
            {
                "source_result": source_result,
                "language_mode": "chinese",
                "target_length_chars": 1600,
                "human_signal_ratio": 44,
            }
        )

        self.assertEqual(request["target_length_chars"], 1600)
        self.assertEqual(request["human_signal_ratio"], 44)

    def test_article_draft_normalize_request_keeps_non_tech_topics_out_of_tech_lane(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Consumer beverage brand refresh sparks debate",
                "analysis_time": "2026-04-25T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "A beverage brand refresh is driving marketing debate.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "brand-1",
                        "source_name": "Campaign",
                        "source_type": "major_news",
                        "published_at": "2026-04-25T11:00:00+00:00",
                        "observed_at": "2026-04-25T11:05:00+00:00",
                        "url": "https://example.com/brand-1",
                        "text_excerpt": "The redesign is polarizing consumers and advertisers, but it is mainly a branding story.",
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        request = normalize_article_draft_request(
            {
                "source_result": source_result,
                "language_mode": "chinese",
            }
        )

        self.assertEqual(request["article_framework"], "auto")
        self.assertNotEqual(request.get("style_memory", {}).get("target_band"), "tech_supply_chain_commentary")
        self.assertNotIn("顺着钱的流向看下去", request["personal_phrase_bank"])

    def test_article_draft_normalize_request_applies_macro_conflict_lane_defaults(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Hormuz oil shock reprices inflation expectations and Fed path",
                "analysis_time": "2026-04-25T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "A Hormuz disruption is feeding through oil, inflation expectations, and equity discount rates.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "macro-1",
                        "source_name": "Bloomberg Opinion",
                        "source_type": "major_news",
                        "published_at": "2026-04-25T11:00:00+00:00",
                        "observed_at": "2026-04-25T11:05:00+00:00",
                        "url": "https://example.com/macro-1",
                        "text_excerpt": (
                            "A Hormuz shock is pushing Brent higher and forcing investors to revisit inflation, "
                            "Fed timing, and equity multiple compression."
                        ),
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        request = normalize_article_draft_request(
            {
                "source_result": source_result,
                "language_mode": "chinese",
            }
        )

        self.assertEqual(request["article_framework"], "deep_analysis")
        self.assertEqual(request["style_memory"]["target_band"], "macro_conflict_transmission")
        self.assertEqual(request["target_length_chars"], 2800)
        self.assertEqual(request["human_signal_ratio"], 70)
        self.assertIn("先看结论", request["personal_phrase_bank"])
        self.assertIn("把事件翻译成油价、通胀预期、Fed 路径和权益贴现率的传导链", request["must_include"])
        self.assertTrue(request["style_memory"].get("sample_sources"))
        sample_names = [item.get("name", "") for item in request["style_memory"]["sample_sources"]]
        self.assertIn("HFI Research", sample_names)
        self.assertIn("Bloomberg Opinion / Javier Blas", sample_names)

    def test_requested_focus_sentences_macro_impact_writes_full_market_chain(self) -> None:
        request = {
            "topic": "Hormuz oil shock reprices inflation expectations and Fed path",
            "language_mode": "chinese",
            "must_include": ["把事件翻译成油价、通胀预期、Fed 路径和权益贴现率的传导链"],
        }

        sentences = requested_focus_sentences(request, "impact", mode="chinese")
        joined = " ".join(sentences)

        self.assertIn("通胀预期", joined)
        self.assertIn("Fed", joined)
        self.assertIn("贴现率", joined)
        self.assertIn("权益估值", joined)

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
                    "used_browser_session": True,
                    "session_source": "remote_debugging",
                    "session_status": "ready",
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

    def build_shadow_only_news_result(self) -> dict:
        return run_news_index(
            {
                "topic": "Shadow-only rumor",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-shadow",
                        "claim_text": "The United States has already committed to a ground entry.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "social-1",
                        "source_name": "Social rumor account",
                        "source_type": "social",
                        "published_at": "2026-03-24T11:56:00+00:00",
                        "observed_at": "2026-03-24T11:57:00+00:00",
                        "url": "https://example.com/social-rumor",
                        "text_excerpt": "Ground entry is already decided.",
                        "claim_ids": ["claim-shadow"],
                        "claim_states": {"claim-shadow": "support"},
                    }
                ],
            }
        )

    def build_clean_core_news_result(self) -> dict:
        return run_news_index(
            {
                "topic": "Clear core fact",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "Indirect talks continue through intermediaries.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "gov-1",
                        "source_name": "Oman Foreign Ministry",
                        "source_type": "government",
                        "published_at": "2026-03-24T11:20:00+00:00",
                        "observed_at": "2026-03-24T11:25:00+00:00",
                        "url": "https://example.com/oman-talks",
                        "text_excerpt": "Indirect talks continue through intermediaries.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    }
                ],
            }
        )

    def build_reddit_operator_review_source_result(self) -> dict:
        source_result = json.loads(json.dumps(self.build_clean_core_news_result()))
        retrieval_result = source_result.get("retrieval_result", source_result)
        retrieval_result["operator_review_queue"] = [
            {
                "title": "Semicap capex thread",
                "priority_level": "high",
                "priority_score": 90,
                "summary": "Partial Reddit comment sampling and duplicate replies still need operator review.",
                "recommended_action": "manual_review_before_promotion",
            }
        ]
        return source_result

    def build_energy_war_news_result(self) -> dict:
        return run_news_index(
            {
                "topic": "Hormuz energy shock",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "mode": "crisis",
                "preset": "energy-war",
                "claims": [
                    {
                        "claim_id": "claim-energy",
                        "claim_text": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "wire-1",
                        "source_name": "Reuters",
                        "source_type": "wire",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:31:00+00:00",
                        "url": "https://example.com/reuters-energy",
                        "text_excerpt": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                        "claim_ids": ["claim-energy"],
                        "claim_states": {"claim-energy": "support"},
                    }
                ],
            }
        )

    def test_article_brief_builds_fact_firewall_fields(self) -> None:
        brief = build_analysis_brief({"source_result": run_news_index(self.news_request)})
        analysis_brief = brief["analysis_brief"]
        self.assertIn("canonical_facts", analysis_brief)
        self.assertIn("not_proven", analysis_brief)
        self.assertIn("open_questions", analysis_brief)
        self.assertIn("scenario_matrix", analysis_brief)
        self.assertIn("story_angles", analysis_brief)
        self.assertIn("image_keep_reasons", analysis_brief)
        self.assertIn("voice_constraints", analysis_brief)
        self.assertIn("misread_risks", analysis_brief)
        self.assertIn("recommended_thesis", analysis_brief)
        self.assertTrue(brief["supporting_citations"])
        self.assertIn("## Open Questions", brief["report_markdown"])
        self.assertIn("## Scenario Matrix", brief["report_markdown"])

    def test_article_brief_not_proven_entries_include_reasoning_fields(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_shadow_only_news_result()})
        not_proven = brief["analysis_brief"]["not_proven"]
        self.assertTrue(not_proven)
        first = not_proven[0]
        self.assertIn("why_not_proven", first)
        self.assertIn("support_count", first)
        self.assertIn("contradiction_count", first)
        self.assertTrue(first["why_not_proven"])

    def test_article_brief_outputs_macro_note_fields(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_energy_war_news_result()})
        analysis_brief = brief["analysis_brief"]
        self.assertIn("macro_note_fields", analysis_brief)
        self.assertIn("one_line_judgment", analysis_brief)
        self.assertIn("benchmark_map", analysis_brief)
        self.assertIn("bias_table", analysis_brief)
        self.assertIn("horizon_table", analysis_brief)
        self.assertTrue(analysis_brief["benchmark_map"]["primary_benchmarks"])
        self.assertIn("## Macro Note Fields", brief["report_markdown"])

    def test_article_brief_preserves_market_relevance_zh_from_news_index_request(self) -> None:
        source_result = run_news_index(
            {
                "topic": "AI Agent hiring rebound becomes a business story",
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "AI Agent hiring is becoming a business signal rather than a pure hiring headline.",
                        "claim_text_zh": "AI Agent 招聘回暖，正在从岗位新闻变成经营信号。",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "major-1",
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "observed_at": "2026-03-29T10:10:00+00:00",
                        "url": "https://example.com/36kr-agent-hiring",
                        "text_excerpt": "36kr reports selected AI agent startups are hiring again.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    }
                ],
                "market_relevance": [
                    "Chinese business and investing readers still need a clean explanation of the event background, the transmission path, and what matters next."
                ],
                "market_relevance_zh": [
                    "中文商业与投资读者需要看清这件事的背景、传导路径，以及它接下来会影响什么。"
                ],
            }
        )

        brief = build_analysis_brief({"source_result": source_result})
        self.assertEqual(
            brief["source_summary"]["market_relevance_zh"],
            ["中文商业与投资读者需要看清这件事的背景、传导路径，以及它接下来会影响什么。"],
        )
        self.assertEqual(
            brief["analysis_brief"]["market_or_reader_relevance_zh"],
            ["中文商业与投资读者需要看清这件事的背景、传导路径，以及它接下来会影响什么。"],
        )
        self.assertTrue(all("Chinese business and investing readers" not in item for item in brief["analysis_brief"]["open_questions_zh"]))

    def test_article_brief_recommended_thesis_zh_avoids_operator_prompt_phrasing(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_clean_core_news_result()})
        thesis_zh = brief["analysis_brief"]["recommended_thesis_zh"]
        self.assertTrue(thesis_zh)
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in thesis_zh))
        self.assertNotIn("\u6700\u7a33\u59a5", thesis_zh)
        self.assertNotIn("\u5199\u6cd5", thesis_zh)
        self.assertNotIn("\u89d2\u5ea6", thesis_zh)

    def test_article_brief_report_surfaces_image_keep_reasons(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_seed_x_index_result(self.case_dir("brief-x-seed"))})
        self.assertTrue(brief["analysis_brief"]["image_keep_reasons"])
        self.assertIn("## Image Keep Reasons", brief["report_markdown"])

    def test_article_brief_surfaces_reddit_operator_review_gate(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_reddit_operator_review_source_result()})
        source_summary = brief["source_summary"]
        gate = source_summary["reddit_comment_review_gate"]
        self.assertEqual(source_summary["operator_review_required_count"], 1)
        self.assertEqual(source_summary["operator_review_high_priority_count"], 1)
        self.assertEqual(source_summary["operator_review_queue"][0]["priority_level"], "high")
        self.assertTrue(gate["required"])
        self.assertEqual(gate["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertTrue(any("Reddit comment-derived material" in item for item in brief["analysis_brief"]["voice_constraints"]))
        self.assertIn("## Reddit Operator Review", brief["report_markdown"])

    def test_build_sections_localizes_chinese_brief_snippets_and_joiners(self) -> None:
        sections = build_sections(
            {
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "balanced",
            },
            {
                "topic": "美伊战争对中国的战略影响",
                "source_kind": "news_index",
            },
            {},
            [],
            [],
            {
                "canonical_facts": [
                    {"claim_text": "中方已启动撤侨"},
                    {"claim_text": "霍尔木兹仍是关键油气通道"},
                ],
                "not_proven": [
                    {"claim_text": "中国会直接在中东军事护航"},
                ],
                "trend_lines": [
                    {"detail": "5 tracked claim(s) are still denied, unclear, or inference-only."},
                ],
                "market_or_reader_relevance": [
                    "中国能源安全与输入性通胀",
                    "航运、保险与供应链成本",
                    "中国外交回旋空间与中东布局",
                ],
                "open_questions": [
                    "下一轮官方表态是否升级",
                    "油运保险费率会不会继续上跳",
                ],
            },
        )

        self.assertEqual(sections[0]["heading"], "先看变化本身")
        self.assertIn("中方已启动撤侨", sections[0]["paragraph"])
        self.assertNotIn("tracked claim(s)", sections[1]["paragraph"])
        self.assertIn("目前仍有5条关键判断处在未证实、被否认或仅能推演的状态", sections[1]["paragraph"])
        self.assertIn("先看中国能源安全与输入性通胀，其次看航运、保险和供应链成本，最重要的是看中国外交回旋空间与中东布局", sections[2]["paragraph"])
        self.assertIn("第一，下一轮官方表态是否升级", sections[3]["paragraph"])
        self.assertIn("第二，油运保险费率会不会继续上跳", sections[3]["paragraph"])

    def test_build_sections_preliminary_chinese_draft_avoids_meta_public_record_copy(self) -> None:
        sections = build_sections(
            {
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "balanced",
                "human_signal_ratio": 80,
                "personal_phrase_bank": ["先说结论", "更关键的是", "最后盯三件事"],
            },
            {
                "topic": "美伊战争对中国的战略影响",
                "source_kind": "news_index",
            },
            {},
            [],
            [],
            {
                "canonical_facts": [],
                "not_proven": [
                    {"claim_text": "中国会因为这场冲突直接在中东选边站队并进行军事护航。"},
                ],
                "trend_lines": [
                    {"detail": "5 tracked claim(s) are still denied, unclear, or inference-only."},
                ],
                "market_or_reader_relevance": [
                    "中国能源安全与输入性通胀",
                    "航运、保险与供应链成本",
                    "中国外交回旋空间与中东布局",
                ],
                "open_questions": [
                    "中国商船和油轮穿越霍尔木兹的活动会不会继续收缩",
                    "国内成品油和输入性成本会不会继续上行",
                ],
            },
        )

        self.assertNotIn("更多公开信息来补全", sections[0]["paragraph"])
        self.assertIn("先别把", sections[0]["paragraph"])
        self.assertIn("传导", sections[0]["paragraph"])
        self.assertIn("航运、保险和供应链成本", sections[3]["paragraph"])

    def test_build_sections_target_length_expands_deep_analysis_structure(self) -> None:
        sections = build_sections(
            {
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "balanced",
                "target_length_chars": 2800,
            },
            {
                "topic": "Claude Code 泄露代码里暴露出的秘密功能",
                "source_kind": "news_index",
                "core_source_count": 3,
                "shadow_source_count": 2,
            },
            {},
            [],
            [],
            {
                "canonical_facts": [
                    {"claim_text": "泄露代码里出现了多个未公开能力入口。"},
                    {"claim_text": "部分能力已经能从命令结构和调用链中看出雏形。"},
                ],
                "not_proven": [
                    {"claim_text": "这些能力都会在公开版本里全部放开。"},
                    {"claim_text": "目前看到的每个入口都已经在生产环境稳定启用。"},
                ],
                "trend_lines": [
                    {"detail": "讨论没有退潮，因为更多人开始沿着调用链追真实执行路径。"},
                ],
                "market_or_reader_relevance": [
                    "代码代理的真实能力边界",
                    "工具调用、权限与自动化工作流",
                    "未来产品路线和灰度入口判断",
                ],
                "open_questions": [
                    "哪些入口只是实验残留，哪些已经对应真实功能",
                    "权限边界会不会继续收紧或显式化",
                    "后续版本会先开放哪一层能力",
                ],
            },
        )

        headings = [section["heading"] for section in sections]
        self.assertEqual(len(sections), 6)
        self.assertEqual(headings[0], "先看变化本身")
        self.assertIn("哪些已经确认，哪些还不能写死", headings)
        self.assertIn("这件事的分水岭在哪", headings)
        self.assertIn("第一层", sections[1]["paragraph"])
        self.assertIn("分水岭", sections[4]["paragraph"])

    def test_article_draft_preserves_longform_structure_and_avoids_business_shorthand_for_developer_tooling(self) -> None:
        source_result = run_news_index(
            {
                "topic": "Claude Code 泄露源码后，真正值得看的隐藏能力",
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "The leaked code exposes browser control and tool-calling entrypoints.",
                        "claim_text_zh": "泄露代码已经露出了浏览器控制和工具调用入口。",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "social-1",
                        "source_name": "X @agintender",
                        "source_type": "social",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "observed_at": "2026-03-29T10:05:00+00:00",
                        "url": "https://x.com/agintender/status/1",
                        "text_excerpt": "The thread walks through browser control, subagents, and workflow orchestration entrypoints.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    },
                    {
                        "source_id": "docs-1",
                        "source_name": "Anthropic docs / Chrome",
                        "source_type": "major_news",
                        "published_at": "2026-03-29T09:50:00+00:00",
                        "observed_at": "2026-03-29T09:55:00+00:00",
                        "url": "https://docs.anthropic.com/en/docs/claude-code/chrome",
                        "text_excerpt": "Official docs describe browser control and Chrome integration.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    },
                ],
                "market_relevance_zh": [
                    "产品能力表面、工具调用边界和权限设计",
                    "浏览器控制、工作流编排与多步开发者执行",
                    "后续版本开放哪些入口与边界",
                ],
            }
        )

        draft = build_article_draft(
            {
                "source_result": source_result,
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "balanced",
                "target_length_chars": 2800,
                "headline_hook_mode": "traffic",
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-claude-code-longform"),
            }
        )

        package = draft["article_package"]
        headings = [section["heading"] for section in package["sections"]]
        joined_text = "\n".join([package["lede"], *(section["paragraph"] for section in package["sections"])])

        self.assertEqual(package["render_context"]["request"]["target_length_chars"], 2800)
        self.assertFalse(package["title"].startswith("刚刚，"))
        self.assertEqual(len(package["sections"]), 6)
        self.assertGreaterEqual(len(joined_text), 1300)
        self.assertIn("哪些已经确认，哪些还不能写死", headings)
        self.assertIn("这件事的分水岭在哪", headings)
        self.assertFalse(any("经营和投资判断题" in item for item in draft["analysis_brief"]["open_questions_zh"]))
        self.assertNotIn("预算", joined_text)
        self.assertNotIn("订单", joined_text)
        self.assertNotIn("定价", joined_text)
        self.assertNotIn("经营变量", joined_text)
        self.assertNotIn("经营层", joined_text)
        self.assertLessEqual(joined_text.count("产品边界、权限设计"), 2)
        self.assertLessEqual(joined_text.count("浏览器控制、工作流编排"), 2)
        self.assertLessEqual(joined_text.count("能力边界和开发者工作流"), 2)

    def test_article_draft_applies_human_signal_ratio_and_personal_phrase_bank(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "human_signal_ratio": 82,
                "personal_phrase_bank": ["先说结论", "更关键的是"],
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-human-signal"),
            }
        )
        effective_request = draft["article_package"]["style_profile_applied"]["effective_request"]
        self.assertEqual(effective_request["human_signal_ratio"], 82)
        self.assertEqual(effective_request["personal_phrase_bank"], ["先说结论", "更关键的是"])
        self.assertTrue(draft["article_package"]["lede"].startswith("先说结论"))

    def test_article_draft_applies_style_memory_from_feedback_profile(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-style-memory")
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "global.json").write_text(
            json.dumps(
                {
                    "scope": "global",
                    "topic": "global",
                    "request_defaults": {
                        "language_mode": "chinese",
                        "human_signal_ratio": 76,
                    },
                    "style_memory": {
                        "target_band": "3.4",
                        "voice_summary": "结论先行，判断明确，但别写成模板审稿口吻。",
                        "preferred_transitions": ["先说结论", "更关键的是"],
                        "must_land": ["把影响路径写在前面", "优先回答读者真正关心的变量"],
                        "avoid_patterns": ["当前最稳妥的写法是"],
                        "slot_lines": {
                            "subtitle": ["先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。"],
                            "impact": ["真正该盯的，是这件事会不会继续改写预算、预期和定价。"],
                            "watch": ["接下来别忙着站队，先盯那几个会把叙事坐实的硬信号。"],
                        },
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "feedback_profile_dir": str(profile_dir),
            }
        )

        self.assertEqual(draft["request"]["style_memory"]["target_band"], "3.4")
        self.assertIn("先说结论", draft["request"]["personal_phrase_bank"])
        self.assertIn("把影响路径写在前面", draft["request"]["must_include"])
        self.assertIn("当前最稳妥的写法是", draft["request"]["must_avoid"])
        self.assertEqual(
            draft["article_package"]["subtitle"],
            "先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。",
        )
        self.assertEqual(draft["article_package"]["style_profile_applied"]["style_memory"]["target_band"], "3.4")

    def test_article_draft_style_memory_summary_reports_sample_source_availability(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-sample-source-summary")
        profile_dir.mkdir(parents=True, exist_ok=True)
        available_sample = profile_dir / "available-sample.md"
        available_sample.write_text("Sample source content.", encoding="utf-8")
        (profile_dir / "global.json").write_text(
            json.dumps(
                {
                    "scope": "global",
                    "topic": "global",
                    "request_defaults": {
                        "language_mode": "chinese",
                    },
                    "style_memory": {
                        "target_band": "3.4",
                        "preferred_transitions": ["先说结论", "问题在于"],
                        "sample_sources": [
                            {
                                "name": "Available sample",
                                "path": str(available_sample),
                                "note": "Should count as available on disk.",
                            },
                            {
                                "name": "Missing sample",
                                "path": str(profile_dir / "missing-sample.md"),
                                "note": "Should stay visible as missing.",
                            },
                        ],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "feedback_profile_dir": str(profile_dir),
            }
        )

        style_memory = draft["article_package"]["style_profile_applied"]["style_memory"]
        self.assertEqual(style_memory["sample_source_declared_count"], 2)
        self.assertEqual(style_memory["sample_source_loaded_count"], 1)
        self.assertEqual(style_memory["sample_source_missing_count"], 1)
        self.assertEqual(style_memory["sample_source_available_count"], 1)
        self.assertEqual(style_memory["sample_source_runtime_mode"], "curated_profile_only")
        self.assertFalse(style_memory["raw_sample_text_loaded"])
        self.assertEqual(style_memory["corpus_derived_transitions"], ["先说结论", "问题在于"])

    def test_article_draft_applies_traffic_headline_hook_when_requested(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "headline_hook_mode": "traffic",
            }
        )

        self.assertTrue(draft["article_package"]["title"].startswith("刚刚，"))
        self.assertEqual(
            draft["article_package"]["style_profile_applied"]["effective_request"]["headline_hook_mode"],
            "traffic",
        )

    def test_article_draft_inline_style_memory_slot_lines_stay_scoped(self) -> None:
        subtitle_line = "Lead with the concrete variable."
        impact_line = "Watch whether this starts rewriting budgets, order flow, and pricing."
        watch_line = "Do not pick a side yet; wait for the hard signals."
        style_memory = {
            "target_band": "3.4",
            "preferred_transitions": ["put simply", "more importantly", "three things matter next"],
            "slot_lines": {
                "subtitle": [subtitle_line],
                "impact": [impact_line],
                "watch": [watch_line],
            },
        }
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "human_signal_ratio": 78,
                "style_memory": style_memory,
            }
        )

        article_package = draft["article_package"]
        self.assertEqual(article_package["subtitle"], subtitle_line)
        self.assertTrue(article_package["lede"].startswith("先说结论"))
        combined_text = "\n".join(
            [article_package["lede"], *(section["paragraph"] for section in article_package["sections"])]
        )
        self.assertNotIn(impact_line, combined_text)
        self.assertNotIn(watch_line, combined_text)

    def test_article_draft_unrelated_slot_lines_are_filtered(self) -> None:
        subtitle_line = "Lead with the concrete variable."
        impact_line = "Watch whether this starts rewriting budgets, order flow, and pricing."
        watch_line = "Do not pick a side yet; wait for the hard signals."
        style_memory = {
            "target_band": "3.4",
            "preferred_transitions": ["put simply", "more importantly", "three things matter next"],
            "slot_lines": {
                "subtitle": [subtitle_line],
                "impact": [impact_line],
                "watch": [watch_line],
            },
        }
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "human_signal_ratio": 78,
                "style_memory": style_memory,
            }
        )

        self.assertEqual(draft["article_package"]["subtitle"], subtitle_line)
        self.assertTrue(draft["article_package"]["lede"])
        all_paragraphs = "\n".join(section["paragraph"] for section in draft["article_package"]["sections"])
        self.assertNotIn(impact_line, all_paragraphs)
        self.assertNotIn(watch_line, all_paragraphs)

    def test_article_draft_filters_business_shorthand_for_macro_conflict_topics(self) -> None:
        style_memory = {
            "target_band": "3.4",
            "slot_lines": {
                "subtitle": ["先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。"],
                "impact": ["真正该盯的，是这件事会不会继续改写预算、预期和定价。"],
                "watch": ["接下来别忙着站队，先盯订单、预算和定价会不会一起动。"],
            },
        }
        draft = build_article_draft(
            {
                "source_result": self.build_energy_war_news_result(),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "style_memory": style_memory,
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-macro-gating"),
            }
        )

        package = draft["article_package"]
        joined_text = "\n".join([package["subtitle"], package["lede"], *(section["paragraph"] for section in package["sections"])])

        self.assertNotEqual(package["subtitle"], style_memory["slot_lines"]["subtitle"][0])
        self.assertEqual(len(package["sections"]), 6)
        self.assertNotIn("预算", joined_text)
        self.assertNotIn("订单", joined_text)
        self.assertNotIn("经营层", joined_text)
        self.assertNotIn("经营和定价", joined_text)
        self.assertNotIn("预算、预期和定价", joined_text)
        self.assertTrue(any(keyword in joined_text for keyword in ("霍尔木兹", "原油", "油价", "航运")))

    def test_chinese_draft_localizes_english_topic_title_and_avoids_story_framework_false_positive(self) -> None:
        source_result = run_news_index(
            {
                "topic": "AI Agent hiring rebound becomes a business story",
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "Selected AI Agent startups are hiring again across engineering and delivery roles.",
                        "claim_text_zh": "AI Agent 创业公司重新开始招聘，岗位集中在工程和交付。",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "major-1",
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "observed_at": "2026-03-29T10:10:00+00:00",
                        "url": "https://example.com/36kr-agent-hiring",
                        "text_excerpt": "Selected AI Agent startups are hiring again across engineering and delivery roles.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    }
                ],
                "market_relevance_zh": [
                    "融资意愿、订单能见度和预算投放",
                    "招聘节奏、组织扩张和行业景气度",
                ],
            }
        )

        draft = build_article_draft({"source_result": source_result, "language_mode": "chinese"})
        package = draft["article_package"]

        self.assertEqual(package["article_framework"], "deep_analysis")
        self.assertEqual(package["sections"][0]["heading"], "先看变化本身")
        self.assertIn("AI Agent", package["title"])
        self.assertNotEqual(package["title"], "AI Agent hiring rebound becomes a business story")
        self.assertIn("## 来源", package["article_markdown"])
        self.assertNotIn("## Sources", package["article_markdown"])

    def test_article_draft_strips_source_branding_and_factcheck_suffix_from_title(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "topic": "「微元合成」获3亿元A+轮融资，联合发布AI生物计算开放合作平台 | 36氪首发：哪些已经确认，哪些仍未确认",
            }
        )
        title = draft["article_package"]["title"]
        self.assertNotIn("36氪", title)
        self.assertNotIn("首发", title)
        self.assertNotIn("哪些已经确认", title)

    def test_article_draft_chinese_mode_avoids_instructional_focus_sentence_leakage(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "must_include": [
                    "separate facts from inference",
                    "keep transmission path practical for business readers",
                ],
            }
        )
        markdown = draft["article_package"]["article_markdown"]
        self.assertNotIn("\u8fd9\u4e00\u6b65\u6700\u6015", markdown)
        self.assertNotIn("\u5f53\u524d\u6700\u7a33\u59a5\u7684\u5199\u6cd5\u662f", markdown)

    def test_article_draft_from_x_index_selects_images_and_citations(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_seed_x_index_result(self.case_dir("x-seed")),
                "max_images": 2,
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-x-seed"),
            }
        )
        package = draft["article_package"]
        self.assertEqual(draft["source_summary"]["source_kind"], "x_index")
        self.assertGreaterEqual(package["draft_metrics"]["image_count"], 1)
        self.assertGreaterEqual(package["draft_metrics"]["citation_count"], 1)
        self.assertIn("What Changed", package["body_markdown"])
        self.assertIn("What To Watch Next", package["body_markdown"])
        self.assertNotIn("Images And Screenshots", package["body_markdown"])
        self.assertIn(f"![{package['selected_images'][0]['image_id']}](", package["article_markdown"])
        self.assertTrue(any(item["status"] == "local_ready" for item in package["selected_images"]))
        self.assertTrue(any(item["role"] == "post_media" and item["status"] == "local_ready" for item in package["selected_images"]))
        self.assertTrue(any("origins" in item["caption"].lower() or "ovda" in item["caption"].lower() for item in package["selected_images"]))
        self.assertEqual(len(package["selected_images"]), len(package["image_blocks"]))
        self.assertTrue(draft["analysis_brief"])
        self.assertTrue(package["draft_claim_map"])
        self.assertIn("draft_thesis", package)
        self.assertIn("style_profile_applied", package)
        self.assertIn("writer_risk_notes", package)
        self.assertTrue(any(item.get("access_mode") == "browser_session" for item in draft["draft_context"]["citation_candidates"]))

    def test_article_draft_browser_session_media_without_ocr_uses_capture_caption(self) -> None:
        source_result = self.build_seed_x_index_result(self.case_dir("x-seed-capture-caption"))
        media_item = source_result["x_posts"][0]["media_items"][0]
        media_item["ocr_text_raw"] = ""
        media_item["ocr_summary"] = ""
        media_item["alt_text"] = ""
        media_item["capture_method"] = "dom_clip"
        draft = build_article_draft(
            {
                "source_result": source_result,
                "language_mode": "english",
                "max_images": 2,
                "image_strategy": "prefer_images",
            }
        )
        selected_post_media = next(item for item in draft["article_package"]["selected_images"] if item["role"] == "post_media")
        self.assertEqual(selected_post_media["caption"], "Browser-captured image from the original X post.")
        self.assertEqual(selected_post_media["status"], "local_ready")

    def test_article_draft_from_blocked_x_index_keeps_screenshot_boundary(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_blocked_x_index_result(self.case_dir("x-blocked")),
                "image_strategy": "screenshots_only",
                "draft_mode": "image_only",
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-x-blocked"),
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

    def test_article_draft_realistic_offline_request_prefers_screenshot_captions_and_dedupes_assets(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.realistic_news_request),
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 3,
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-realistic-offline-images"),
            }
        )

        package = draft["article_package"]
        selected_images = package["selected_images"]
        self.assertGreaterEqual(len(selected_images), 2)
        self.assertEqual(selected_images[0]["role"], "root_post_screenshot")
        self.assertEqual(selected_images[0]["source_name"], "Axios")
        self.assertEqual(selected_images[0]["caption"], "Blocked page card kept only as a limitation-aware artifact.")
        self.assertEqual(selected_images[1]["role"], "root_post_screenshot")
        self.assertEqual(selected_images[1]["source_name"], "MarineTraffic")
        self.assertEqual(selected_images[1]["caption"], "Offline fixture screenshot for public ship-tracker evidence.")
        render_targets = [item["render_target"] for item in selected_images]
        self.assertEqual(len(render_targets), len(set(render_targets)))
        image_section = next(section for section in package["sections"] if section["heading"] == "What The Images Add")
        self.assertIn("Blocked page card kept only as a limitation-aware artifact.", image_section["paragraph"])
        self.assertIn("Offline fixture screenshot for public ship-tracker evidence.", image_section["paragraph"])
        self.assertNotIn("Blocked major-news page card indicating the envoy channel remains active", image_section["paragraph"])

    def test_article_draft_from_news_index_result_builds_without_x_posts(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "target_length_chars": 800,
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-news-index"),
            }
        )
        self.assertEqual(draft["source_summary"]["source_kind"], "news_index")
        self.assertGreaterEqual(draft["article_package"]["draft_metrics"]["citation_count"], 1)
        self.assertIn("What Changed", draft["article_package"]["body_markdown"])
        self.assertIn("Why This Matters", draft["article_package"]["body_markdown"])
        self.assertIn("What To Watch Next", draft["article_package"]["body_markdown"])
        self.assertIn("Sources", draft["article_package"]["article_markdown"])
        self.assertNotIn("core claim(s)", draft["article_package"]["body_markdown"])
        self.assertNotIn("current indexed result", draft["article_package"]["article_markdown"].lower())
        self.assertIn("<html>", draft["preview_html"])

    def test_article_draft_title_strips_source_branding_and_keeps_publishable_copy(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "topic": "微元合成获3亿元A+轮融资，联合发布AI生物计算开放合作平台 | 36氪首发",
            }
        )
        package = draft["article_package"]
        self.assertNotIn("36氪", package["title"])
        self.assertNotIn("首发", package["title"])
        self.assertTrue(package["publishability_checks"]["passed"])

    def test_macro_note_workflow_runs_and_writes_stage_outputs(self) -> None:
        output_dir = self.case_dir("macro-note-workflow")
        result = run_macro_note_workflow(
            {
                "source_result": self.build_energy_war_news_result(),
                "topic": "Hormuz energy shock",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(output_dir),
            }
        )
        self.assertEqual(result["workflow_kind"], "macro_note_workflow")
        self.assertTrue(Path(result["macro_note_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["macro_note_stage"]["report_path"]).exists())
        self.assertIn("one_line_judgment", result["macro_note_result"]["macro_note"])
        self.assertIn("# Macro Note:", result["macro_note_result"]["report_markdown"])

    def test_article_workflow_marks_reddit_operator_review_as_publication_gate(self) -> None:
        output_dir = self.case_dir("article-workflow-reddit-operator-review")
        result = run_article_workflow(
            {
                "source_result": self.build_reddit_operator_review_source_result(),
                "topic": "Semicap capex thread",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(output_dir),
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-reddit-operator-review"),
            }
        )

        self.assertEqual(result["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertTrue(result["manual_review"]["required"])
        self.assertEqual(result["manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["final_stage"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(
            result["final_stage"]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertTrue(result["final_article_result"]["manual_review"]["required"])
        self.assertEqual(
            result["final_article_result"]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("## Reddit Operator Review", result["report_markdown"])

    def test_macro_note_workflow_marks_reddit_operator_review_as_publication_gate(self) -> None:
        output_dir = self.case_dir("macro-note-workflow-reddit-operator-review")
        result = run_macro_note_workflow(
            {
                "source_result": self.build_reddit_operator_review_source_result(),
                "topic": "Semicap capex thread",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(output_dir),
            }
        )

        self.assertEqual(result["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertTrue(result["manual_review"]["required"])
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["macro_note_stage"]["manual_review_status"], "awaiting_reddit_operator_review")
        self.assertEqual(
            result["macro_note_stage"]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertTrue(result["macro_note_result"]["manual_review"]["required"])
        self.assertEqual(
            result["macro_note_result"]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("## Reddit Operator Review", result["macro_note_result"]["report_markdown"])

    def test_macro_note_workflow_defaults_analysis_time_for_fresh_news_request(self) -> None:
        request = json.loads(json.dumps(self.news_request))
        request.pop("analysis_time", None)
        result = run_macro_note_workflow(request)
        self.assertEqual(result["workflow_kind"], "macro_note_workflow")
        self.assertTrue(result["analysis_time"])

    def test_macro_note_workflow_threads_staged_source_result_path(self) -> None:
        output_dir = self.case_dir("macro-note-workflow-staged-source")
        result = run_macro_note_workflow(
            {
                "source_result": self.build_energy_war_news_result(),
                "topic": "Hormuz energy shock",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(output_dir),
            }
        )
        self.assertEqual(result["macro_note_result"]["request"]["source_result_path"], result["source_stage"]["result_path"])

    def test_macro_note_workflow_x_request_reuses_output_tree_for_source_stage(self) -> None:
        output_dir = self.case_dir("macro-note-workflow-x-request")
        result = run_macro_note_workflow(
            {
                **self.build_seed_x_request(self.case_dir("macro-note-workflow-x-request-seed")),
                "output_dir": str(output_dir),
            }
        )
        x_output_dir = result["source_result"]["request"]["output_dir"]
        self.assertTrue(x_output_dir.startswith(str((output_dir / "source-stage").resolve())))

    def test_macro_note_workflow_news_request_can_augment_with_agent_reach(self) -> None:
        output_dir = self.case_dir("macro-note-workflow-agent-reach")
        base_request = {
            "topic": "Hormuz energy shock",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-energy",
                    "claim_text": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                }
            ],
            "candidates": [
                {
                    "source_id": "wire-1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T11:30:00+00:00",
                    "observed_at": "2026-03-24T11:31:00+00:00",
                    "url": "https://example.com/reuters-energy",
                    "text_excerpt": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                    "claim_ids": ["claim-energy"],
                    "claim_states": {"claim-energy": "support"},
                }
            ],
            "agent_reach": {"enabled": True, "channels": ["youtube"]},
            "output_dir": str(output_dir),
        }
        fake_bridge = {
            "channels_attempted": ["youtube"],
            "channels_succeeded": ["youtube"],
            "channels_failed": [],
            "observations_imported": 1,
            "report_markdown": "# Agent Reach Bridge Report",
            "retrieval_request": {
                "candidates": [
                    {
                        "source_id": "agent-youtube-1",
                        "source_name": "YouTube CBS News",
                        "source_type": "social",
                        "origin": "agent_reach",
                        "agent_reach_channel": "youtube",
                        "published_at": "2026-03-24T11:40:00+00:00",
                        "observed_at": "2026-03-24T11:45:00+00:00",
                        "url": "https://www.youtube.com/watch?v=test",
                        "claim_ids": ["claim-energy"],
                        "claim_states": {"claim-energy": "support"},
                        "text_excerpt": "Video recap of Hormuz disruption risk.",
                        "channel": "shadow",
                        "access_mode": "public",
                    }
                ]
            },
        }
        with patch("macro_note_workflow_runtime.run_agent_reach_bridge", return_value=fake_bridge):
            result = run_macro_note_workflow(base_request)

        self.assertEqual(result["source_stage"]["source_kind"], "news_index_agent_reach")
        self.assertTrue(Path(result["source_stage"]["agent_reach_stage"]["result_path"]).exists())
        self.assertTrue(any(item.get("origin") == "agent_reach" for item in result["source_result"]["observations"]))
        self.assertIn("Agent Reach Augmentation", result["report_markdown"])

    def test_macro_note_workflow_respects_agent_reach_enabled_false(self) -> None:
        output_dir = self.case_dir("macro-note-workflow-agent-reach-disabled")
        request = {
            "topic": "Hormuz energy shock",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-energy",
                    "claim_text": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                }
            ],
            "candidates": [
                {
                    "source_id": "wire-1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T11:30:00+00:00",
                    "observed_at": "2026-03-24T11:31:00+00:00",
                    "url": "https://example.com/reuters-energy",
                    "text_excerpt": "Hormuz disruption remains a primary transmission channel for oil and LNG stress.",
                    "claim_ids": ["claim-energy"],
                    "claim_states": {"claim-energy": "support"},
                }
            ],
            "agent_reach": {"enabled": False, "channels": ["youtube"]},
            "output_dir": str(output_dir),
        }
        with patch("macro_note_workflow_runtime.run_agent_reach_bridge") as bridge_mock:
            result = run_macro_note_workflow(request)

        bridge_mock.assert_not_called()
        self.assertEqual(result["source_stage"]["source_kind"], "news_index")
        self.assertEqual(result["source_stage"].get("agent_reach_stage") or {}, {})

    def test_build_sections_without_analysis_brief_uses_derived_brief_path(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "target_length_chars": 800,
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-sections"),
            }
        )
        sections = build_sections(
            draft["request"],
            draft["source_summary"],
            draft["evidence_digest"],
            draft["draft_context"]["citation_candidates"],
            draft["draft_context"]["selected_images"],
            None,
        )
        headings = [section["heading"] for section in sections]
        self.assertIn("What Changed", headings)
        self.assertIn("Why This Matters", headings)

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
        self.assertIn("What Changed", draft["article_package"]["body_markdown"])
        self.assertIn("为什么这事值得关注", draft["article_package"]["body_markdown"])
        self.assertNotIn("Bottom Line", draft["article_package"]["body_markdown"])
        self.assertIn("English title", draft["article_package"]["title"])
        self.assertNotIn("# English title", draft["article_package"]["article_markdown"])

    def test_draft_claim_map_uses_fallback_citations_for_derived_thesis(self) -> None:
        claim_map = build_draft_claim_map(
            [
                {"citation_id": "S1", "source_id": "wire-1", "channel": "core"},
                {"citation_id": "S2", "source_id": "gov-1", "channel": "core"},
            ],
            {
                "recommended_thesis": "The safest current read is cautious de-escalation.",
                "canonical_facts": [
                    {
                        "claim_id": "fact-1",
                        "claim_text": "Talks remain indirect.",
                        "source_ids": [],
                    }
                ],
            },
        )
        thesis = claim_map[0]
        self.assertEqual(thesis["claim_label"], "thesis")
        self.assertEqual(thesis["citation_ids"], ["S1", "S2"])
        self.assertEqual(thesis["citation_channels"], ["core"])
        self.assertEqual(thesis["support_level"], "derived")

    def test_article_draft_style_profile_applied_exposes_effective_request(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "language_mode": "bilingual",
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "tone": "urgent-but-cautious",
                "target_length_chars": 1200,
                "max_images": 2,
                "must_include": ["separate facts from inference"],
                "must_avoid": ["guaranteed"],
            }
        )
        style = draft["article_package"]["style_profile_applied"]
        effective = style["effective_request"]
        self.assertEqual(effective["language_mode"], "bilingual")
        self.assertEqual(effective["draft_mode"], "image_first")
        self.assertEqual(effective["image_strategy"], "prefer_images")
        self.assertEqual(effective["tone"], "urgent-but-cautious")
        self.assertEqual(effective["target_length_chars"], 1200)
        self.assertEqual(effective["max_images"], 2)
        self.assertIn("separate facts from inference", effective["must_include"])
        self.assertIn("guaranteed", effective["must_avoid"])
        self.assertIn("separate facts from inference", style["constraints"]["must_include"])
        self.assertIn("guaranteed", style["constraints"]["must_avoid"])

    def test_article_draft_uses_derived_brief_when_brief_builder_returns_empty(self) -> None:
        with patch("article_draft_flow_runtime.build_analysis_brief", return_value={}):
            draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        self.assertTrue(draft["analysis_brief"])
        self.assertTrue(draft["analysis_brief"]["recommended_thesis"])
        self.assertEqual(draft["draft_context"]["analysis_brief"], draft["analysis_brief"])
        self.assertEqual(draft["article_package"]["render_context"]["analysis_brief"], draft["analysis_brief"])
        self.assertTrue(draft["article_package"]["draft_claim_map"])

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
        self.assertIn("review_rewrite_package", revised)
        self.assertIn("quality_gate", revised["review_rewrite_package"])
        self.assertIn("revision_diff", revised)
        self.assertTrue(revised["revision_diff"]["title"]["changed"])
        self.assertIn("style_learning", revised)
        self.assertTrue(revised["style_learning"]["change_summary"])
        self.assertIn("## Style Learning", revised["report_markdown"])

    def test_polish_chinese_wechat_paragraph_adds_breath_breaks_for_dense_developer_tooling_copy(self) -> None:
        request = {
            "language_mode": "chinese",
            "target_length_chars": 2800,
            "topic": "Claude Code hidden features",
        }
        source_summary = {
            "topic": "Claude Code hidden features",
            "core_verdict": "browser control and workflow changes are the real point",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["浏览器控制、工作流编排", "产品边界、权限设计"],
            "open_questions_zh": ["哪些入口会开放、哪些权限会收口"],
        }
        paragraph = (
            "图像素材能帮你把现场感补回来，但它更适合做补充，不适合替代判断。"
            "对这类题材来说，截图的价值不只是占位，而是把入口、页面状态和当时上下文一起保留下来。"
            "多一张帖子配图的意义，不是把版面铺满，而是让截图里的入口、帖子里的强调点和当时的页面状态彼此校验。"
            "对这种同时有截图和帖子配图的 case，最稳的不是单看哪张图更抓眼，而是看图像层、帖子文案和文档命名能不能指向同一件事。"
        )
        polished = polish_chinese_wechat_paragraph(
            paragraph,
            request,
            source_summary,
            analysis_brief,
            allow_numbered_breaks=True,
            allow_breath_breaks=True,
        )

        self.assertIn("图像素材能把现场感补回来，但它最多是补充，替代不了判断。", polished)
        self.assertIn("\n\n对这类题材来说", polished)
        self.assertIn("\n\n多一张帖子配图的意义", polished)
        self.assertIn("像这种同时有截图和帖子配图的情况", polished)
        self.assertNotIn(" case", polished)

    def test_split_chinese_wechat_breaths_breaks_on_natural_transition_markers(self) -> None:
        paragraph = (
            "这轮讨论能继续往下走，不是靠单一爆料，而是官方文档、recovered 代码和社区拆解开始互相补位。"
            "说白了，官方文档先证明入口已经摆上台面，源码和社区拆解则在提示后面还有多深的工作流层。"
            "这里最容易看走眼的，是把 feature flag 和实验入口直接当成已经公开承诺的产品路线图。"
            "说到底，下一阶段最关键的，不是再多几个内部名词，而是能不能把文档、入口、调用和权限连成闭环。"
        )

        updated = split_chinese_wechat_breaths(paragraph)

        self.assertIn("\n\n说白了", updated)
        self.assertIn("\n\n这里最容易看走眼的", updated)
        self.assertIn("\n\n说到底", updated)

    def test_split_chinese_wechat_breaths_breaks_on_new_tail_tone_marker(self) -> None:
        paragraph = (
            "顺序最好也别看反：先看文档有没有补页，再看入口能不能调用，最后看权限边界是不是被写清。"
            "文档、入口、权限这条线一旦开始补齐。这东西就更像真要进日常开发了。"
            "要是一直补不齐，这事大概率还是停在挖源码、猜功能。"
            "只要这里面有两项开始连续被验证，叙事就还能往前走。"
            "要是截图、文档和调用痕迹始终对不上，再热的讨论最后也会回到围观层面。"
        )

        updated = split_chinese_wechat_breaths(paragraph)

        self.assertIn("\n\n这东西就更像真要进日常开发了", updated)
        self.assertIn("\n\n要是一直补不齐", updated)

    def test_chinese_watch_item_prefers_more_conversational_developer_tooling_copy(self) -> None:
        self.assertEqual(chinese_watch_item("产品边界、权限设计"), "哪些入口真会放出来，哪些权限还是会卡着")
        self.assertEqual(chinese_watch_item("浏览器控制、工作流编排"), "浏览器协同这条线会不会真进日常开发")
        self.assertEqual(
            chinese_watch_item("能力边界和开发者工作流"),
            "这波讨论会不会从围观源码，走到团队到底会不会真用",
        )

    def test_article_revision_style_learning_tiers_explicit_style_controls(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "tone": "urgent-but-cautious",
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 2,
            }
        )
        learning = revised["style_learning"]
        high_keys = {item["key"] for item in learning["high_confidence_rules"]}
        self.assertIn("tone", high_keys)
        self.assertIn("draft_mode", high_keys)
        self.assertIn("image_strategy", high_keys)
        self.assertIn("max_images", high_keys)
        self.assertEqual(revised["profile_update_decision"]["status"], "suggest_only")
        self.assertEqual(learning["proposed_profile_feedback"]["defaults"]["tone"], "urgent-but-cautious")
        self.assertEqual(learning["proposed_profile_feedback"]["defaults"]["draft_mode"], "image_first")

    def test_article_revision_uses_explicit_edit_reason_feedback(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_body_markdown": "# Revised body\n\nLead with the strongest confirmed fact before scenarios.\n",
                "edit_reason_feedback": {
                    "summary": "I want to be more explicit about why I changed the structure.",
                    "changes": [
                        {
                            "area": "body",
                            "change": "Lead with the strongest confirmed fact before scenarios.",
                            "reason_tag": "structure",
                            "why": "Lead with confirmed facts before any scenario language.",
                            "reuse_scope": "topic",
                        }
                    ],
                    "reusable_preferences": [
                        {
                            "key": "must_include",
                            "value": "Lead with the strongest confirmed fact before any scenario.",
                            "scope": "topic",
                            "reason_tag": "structure",
                            "why": "This is the framing I want for geopolitical pieces.",
                        },
                        {
                            "key": "tone",
                            "value": "neutral-cautious",
                            "scope": "global",
                            "reason_tag": "voice",
                            "why": "Keep the tone careful even when the news is fast moving.",
                        },
                    ],
                },
            }
        )
        learning = revised["style_learning"]
        self.assertTrue(learning["used_explicit_feedback"])
        self.assertEqual(learning["explicit_change_count"], 1)
        self.assertEqual(learning["explicit_preference_count"], 2)
        self.assertEqual(learning["proposed_profile_feedback"]["defaults"]["tone"], "neutral-cautious")
        self.assertIn(
            "Lead with the strongest confirmed fact before any scenario.",
            learning["proposed_profile_feedback"]["defaults"]["must_include"],
        )
        self.assertTrue(any(item["rule_type"] == "explicit_preference" for item in learning["high_confidence_rules"]))
        self.assertIn("Human summary:", " ".join(learning["change_summary"]))
        self.assertIn("Lead with the strongest confirmed fact before scenarios.", " ".join(learning["change_summary"]))
        self.assertEqual(revised["request"]["edit_reason_feedback"]["changes"][0]["change"], "Lead with the strongest confirmed fact before scenarios.")
        self.assertIn("Human change reasons used", revised["report_markdown"])

    def test_article_revision_accepts_human_feedback_form(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_body_markdown": "# Revised body\n\nReaders should see the strongest confirmed fact first.\n",
                "human_feedback_form": {
                    "overall_goal_in_plain_english": "Make the opening clearer and safer.",
                    "what_to_change": [
                        {
                            "area": "body",
                            "change": "Lead with confirmed facts before scenarios.",
                            "why": "Readers should see what is known before what is possible.",
                            "reason_tag": "clarity",
                            "remember_for": "topic",
                        }
                    ],
                    "what_to_remember_next_time": [
                        {
                            "key": "must_include",
                            "value": "Lead with the strongest confirmed fact before any scenario.",
                            "scope": "topic",
                            "why": "This framing should repeat for this topic.",
                            "reason_tag": "structure",
                        }
                    ],
                    "one_off_fixes_not_style": [
                        {
                            "area": "claims",
                            "change": "Removed the line implying talks were already agreed.",
                            "why": "That was a fact correction, not a reusable preference.",
                            "reason_tag": "factual_caution",
                        }
                    ],
                },
            }
        )
        self.assertIn("human_feedback_form", revised["request"])
        self.assertEqual(revised["human_feedback_form"]["overall_goal_in_plain_english"], "Make the opening clearer and safer.")
        self.assertTrue(revised["style_learning"]["used_explicit_feedback"])
        self.assertEqual(revised["style_learning"]["explicit_change_count"], 2)
        self.assertEqual(revised["style_learning"]["explicit_preference_count"], 1)
        self.assertIn(
            "Lead with the strongest confirmed fact before any scenario.",
            revised["style_learning"]["proposed_profile_feedback"]["defaults"]["must_include"],
        )
        self.assertEqual(revised["request"]["edit_reason_feedback"]["changes"][0]["change"], "Lead with confirmed facts before scenarios.")
        self.assertTrue(any("evidence-bound editing" in item for item in revised["style_learning"]["excluded_signals"]))

    def test_article_revision_accepts_simple_human_feedback_change_without_tags(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "human_feedback_form": {
                    "overall_goal_in_plain_english": "Make the opening easier to trust.",
                    "what_to_change": [
                        {
                            "change": "Move the clearest confirmed development to the top.",
                            "why": "Readers should not have to hunt for what is actually confirmed.",
                        }
                    ],
                },
            }
        )
        normalized_change = revised["human_feedback_form"]["what_to_change"][0]
        self.assertEqual(normalized_change["area"], "other")
        self.assertEqual(normalized_change["reason_tag"], "other")
        self.assertEqual(normalized_change["reuse_scope"], "review")
        self.assertEqual(
            revised["request"]["edit_reason_feedback"]["changes"][0]["change"],
            "Move the clearest confirmed development to the top.",
        )

    def test_summarize_review_decisions_exposes_learning_previews(self) -> None:
        summary = summarize_review_decisions(
            {
                "review_rewrite_package": {
                    "quality_gate": "pass",
                    "attacks": [
                        {
                            "severity": "major",
                            "title": "Overclaim",
                            "detail": "The draft briefly outran the evidence layer.",
                        }
                    ],
                    "claims_removed_or_softened": ["Removed the sentence that sounded too final."],
                    "remaining_risks": ["A fast-moving headline could still tempt overclaiming."],
                },
                "style_learning": {
                    "high_confidence_rules": [
                        {
                            "key": "tone",
                            "scope": "global",
                            "confidence": 0.98,
                            "rule_type": "explicit_preference",
                            "reason": "Keep the tone careful when evidence is still moving.",
                        }
                    ],
                    "medium_confidence_rules": [
                        {
                            "key": "must_include",
                            "scope": "topic",
                            "confidence": 0.65,
                            "rule_type": "constraint_candidate",
                            "reason": "Lead with the strongest confirmed fact before scenarios.",
                        }
                    ],
                    "low_confidence_rules": [
                        {
                            "key": "manual_rewrite",
                            "scope": "review",
                            "confidence": 0.25,
                            "rule_type": "rewrite_observation",
                            "reason": "The rewrite was substantial but not yet reusable.",
                        }
                    ],
                    "change_summary": [
                        "Human summary: tighten the opening.",
                        "Human change [body/structure]: Lead with the strongest confirmed fact first.",
                    ],
                    "excluded_signals": [
                        "Citation maintenance should not be promoted into style memory.",
                    ],
                    "explicit_change_count": 1,
                    "explicit_preference_count": 1,
                    "used_explicit_feedback": True,
                    "proposed_profile_feedback": {
                        "defaults": {
                            "tone": "neutral-cautious",
                            "must_include": ["Lead with the strongest confirmed fact before any scenario."],
                        }
                    },
                },
                "profile_update_decision": {
                    "status": "suggest_only",
                    "reason": "Reusable defaults were detected but still require human review.",
                },
            }
        )

        learning = summary["style_learning"]
        self.assertEqual(learning["decision"], "suggest_only")
        self.assertEqual(learning["high_confidence_rule_preview"][0]["key"], "tone")
        self.assertEqual(learning["medium_confidence_rule_preview"][0]["key"], "must_include")
        self.assertEqual(learning["low_confidence_rule_preview"][0]["key"], "manual_rewrite")
        self.assertIn("Human summary: tighten the opening.", learning["change_summary_preview"])
        self.assertIn(
            "Citation maintenance should not be promoted into style memory.",
            learning["excluded_signals_preview"],
        )
        self.assertEqual(learning["proposed_default_keys"], ["must_include", "tone"])

    def test_feedback_markdown_parses_into_revision_payload(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        template = build_revision_template(draft)
        payload = parse_feedback_markdown(
            """
# Article Feedback

Persist feedback scope: topic
Auto rewrite after manual: true

## Overall Goal

Make the opening clearer and more cautious.

## Keep

- Keep the strongest confirmed fact near the top.

## Change Requests

- Change: Lead with confirmed facts before scenarios.
  Why: Readers should see what is known before what is possible.
  Area: lede
  Reason Tag: clarity

## Remember Next Time

- Key: must_include
  Value: Lead with the strongest confirmed fact before any scenario.
  Why: This framing should repeat for this topic.
  Scope: topic

## One-Off Fact Fixes

- Change: Remove the line implying a final deal already exists.
  Why: That was a fact correction, not a style preference.
  Area: claims

## Images To Keep Near Front

- IMG-01

## Images To Drop

- IMG-02

## Optional Full Rewrite

```md
# Revised draft

Lead with the strongest confirmed fact.
```
            """,
            base_template=template,
        )
        self.assertEqual(payload["persist_feedback"]["scope"], "topic")
        self.assertEqual(payload["feedback"]["keep_image_asset_ids"], ["IMG-01"])
        self.assertEqual(payload["feedback"]["drop_image_asset_ids"], ["IMG-02"])
        self.assertTrue(payload["allow_auto_rewrite_after_manual"])
        self.assertEqual(payload["human_feedback_form"]["overall_goal_in_plain_english"], "Make the opening clearer and more cautious.")
        self.assertEqual(payload["human_feedback_form"]["what_to_keep"], ["Keep the strongest confirmed fact near the top."])
        self.assertEqual(payload["human_feedback_form"]["what_to_change"][0]["change"], "Lead with confirmed facts before scenarios.")
        self.assertEqual(payload["human_feedback_form"]["what_to_remember_next_time"][0]["key"], "must_include")
        self.assertEqual(payload["human_feedback_form"]["one_off_fixes_not_style"][0]["area"], "claims")
        self.assertIn("Lead with the strongest confirmed fact.", payload["edited_article_markdown"])

    def test_article_revise_payload_accepts_markdown_feedback_file(self) -> None:
        case_dir = self.case_dir("markdown-feedback-input")
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        draft_path = case_dir / "article-draft-result.json"
        template_path = case_dir / "article-revise-template.json"
        feedback_path = case_dir / "ARTICLE-FEEDBACK.md"
        draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
        template_path.write_text(json.dumps(build_revision_template(draft), ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")
        feedback_path.write_text(
            """
# Article Feedback

Persist feedback scope: none
Auto rewrite after manual: false

## Overall Goal

Make the article easier to trust.

## Change Requests

- Change: Move the clearest confirmed development to the top.
  Why: Readers should not have to hunt for the confirmed point.
            """.strip()
            + "\n",
            encoding="utf-8-sig",
        )
        payload = build_article_revise_payload(
            Namespace(
                draft=str(draft_path),
                revision_input=str(feedback_path),
                revision_template=None,
                output=None,
                markdown_output=None,
                title_hint=None,
                subtitle_hint=None,
                angle=None,
                tone=None,
                target_length=None,
                max_images=None,
                image_strategy=None,
                draft_mode=None,
                pin_image=[],
                drop_image=[],
                revision_note=None,
                allow_auto_rewrite_after_manual=False,
                quiet=True,
            )
        )
        self.assertEqual(payload["human_feedback_form"]["overall_goal_in_plain_english"], "Make the article easier to trust.")
        self.assertEqual(
            payload["human_feedback_form"]["what_to_change"][0]["change"],
            "Move the clearest confirmed development to the top.",
        )

    def test_article_revision_skips_auto_rewrite_when_red_team_passes(self) -> None:
        draft = build_article_draft({"source_result": self.build_clean_core_news_result()})
        revised = build_article_revision({"draft_result": draft})
        self.assertEqual(revised["review_rewrite_package"]["rewrite_mode"], "no_rewrite_needed")
        self.assertEqual(revised["review_rewrite_package"]["base_package_mode"], "reused_draft_package")
        self.assertEqual(revised["review_rewrite_package"]["quality_gate"], "pass")
        self.assertEqual(revised["final_article_result"]["article_markdown"], draft["article_package"]["article_markdown"])
        self.assertIn("Base package mode", revised["report_markdown"])
        self.assertIn("Rewrite decision", revised["report_markdown"])

    def test_article_revision_blocks_shadow_only_thesis(self) -> None:
        draft = build_article_draft({"source_result": self.build_shadow_only_news_result()})
        revised = build_article_revision({"draft_result": draft})
        self.assertEqual(revised["review_rewrite_package"]["pre_rewrite_quality_gate"], "block")
        self.assertEqual(revised["review_rewrite_package"]["quality_gate"], "block")
        self.assertTrue(revised["review_rewrite_package"]["attacks"])
        self.assertIn("final_article_result", revised)

    def test_red_team_flags_uncited_promoted_claims(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        package = draft["article_package"]
        package["draft_claim_map"] = [
            {
                "claim_label": "thesis",
                "claim_text": package["draft_thesis"],
                "citation_ids": [],
                "support_level": "derived",
            }
        ]
        review = build_red_team_review(
            package,
            draft["analysis_brief"],
            draft["source_summary"],
            draft["draft_context"]["citation_candidates"],
            package["selected_images"],
        )
        attack_ids = [item["attack_id"] for item in review["attacks"]]
        self.assertIn("uncited-promoted-claims", attack_ids)
        self.assertEqual(review["quality_gate"], "block")

    def test_red_team_flags_non_core_promoted_claims(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        package = draft["article_package"]
        package["draft_claim_map"] = [
            {
                "claim_label": "canonical_fact",
                "claim_text": "This promoted claim still lacks core confirmation.",
                "citation_ids": ["S1"],
                "support_level": "core",
            }
        ]
        review = build_red_team_review(
            package,
            draft["analysis_brief"],
            draft["source_summary"],
            [{**draft["draft_context"]["citation_candidates"][0], "channel": "shadow"}],
            package["selected_images"],
        )
        attack_ids = [item["attack_id"] for item in review["attacks"]]
        self.assertIn("non-core-promoted-claims", attack_ids)
        self.assertEqual(review["quality_gate"], "revise")

    def test_rewrite_request_after_attack_localizes_chinese_guidance(self) -> None:
        rewritten = rewrite_request_after_attack(
            {
                "language_mode": "chinese",
                "must_include": ["保留已有判断"],
                "must_avoid": [],
                "tone": "professional-calm",
            },
            {
                "not_proven": [{"claim_text": "某项升级动作已经板上钉钉"}],
                "story_angles": [{"angle": "Lead with the strongest confirmed development first."}],
            },
            {
                "quality_gate": "revise",
                "attacks": [
                    {"attack_id": "non-core-promoted-claims"},
                    {"attack_id": "blocked-sources-hidden"},
                ],
            },
        )

        self.assertIn("先写已确认的事实，再写情景判断和影响传导", rewritten["must_include"])
        self.assertIn("这条内容仍属未证实，不要写成已落地事实：某项升级动作已经板上钉钉", rewritten["must_include"])
        self.assertIn("低置信度或非核心信号只能作为补充，不能放进已确认事实段落", rewritten["must_include"])
        self.assertNotIn("Lead with the strongest confirmed development first.", rewritten["must_include"])
        self.assertEqual(rewritten["angle_zh"], "先把已确认事实说清，再解释影响路径和仍待确认的边界")

    def test_article_revision_preserves_style_memory_from_prior_request(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "style_memory": {
                    "target_band": "3.4",
                    "slot_lines": {
                        "subtitle": ["先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。"],
                    },
                },
            }
        )
        revised = build_article_revision({"draft_result": draft, "title_hint": "改一个标题但保留风格记忆"})
        self.assertEqual(revised["request"]["style_memory"]["target_band"], "3.4")
        self.assertEqual(revised["article_package"]["style_profile_applied"]["style_memory"]["target_band"], "3.4")
        self.assertEqual(
            revised["article_package"]["subtitle"],
            "先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。",
        )

    def test_article_revision_preserves_headline_hook_preferences(self) -> None:
        draft = build_article_draft(
            {
                "source_result": self.build_clean_core_news_result(),
                "language_mode": "chinese",
                "headline_hook_mode": "traffic",
                "headline_hook_prefixes": ["刚刚，"],
            }
        )
        revised = build_article_revision({"draft_result": draft})
        self.assertEqual(revised["request"]["headline_hook_mode"], "traffic")
        self.assertEqual(revised["request"]["headline_hook_prefixes"], ["刚刚，"])
        self.assertTrue(revised["article_package"]["title"].startswith("刚刚，"))

    def test_article_revision_preserves_manual_override_and_skips_auto_rewrite(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        manual_text = "# Manual draft\n\nThis version makes the point directly and never states what is still unconfirmed.\n"
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_body_markdown": manual_text,
                "edited_article_markdown": manual_text,
            }
        )
        review_package = revised["review_rewrite_package"]
        self.assertEqual(review_package["rewrite_mode"], "manual_preserved")
        self.assertEqual(review_package["pre_rewrite_quality_gate"], review_package["quality_gate"])
        self.assertTrue(review_package["pre_rewrite_attacks"])
        self.assertEqual(revised["final_article_result"]["body_markdown"], manual_text)
        self.assertEqual(revised["final_article_result"]["article_markdown"], manual_text)
        self.assertTrue(revised["revision_history"][-1]["manual_override"])
        self.assertEqual(revised["revision_history"][-1]["rewrite_mode"], "manual_preserved")
        self.assertTrue(revised["article_package"]["manual_body_override"])
        self.assertTrue(revised["article_package"]["manual_article_override"])
        self.assertIn("Manual override preserved; auto-rewrite skipped.", revised["article_package"]["editor_notes"])
        self.assertIn("Pre-rewrite quality gate", revised["report_markdown"])

    def test_article_revision_manual_opt_in_allows_auto_rewrite(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        manual_text = "# Manual draft\n\nUnique marker: REWRITE-ME.\n"
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_body_markdown": manual_text,
                "edited_article_markdown": manual_text,
                "allow_auto_rewrite_after_manual": True,
            }
        )
        review_package = revised["review_rewrite_package"]
        self.assertEqual(review_package["rewrite_mode"], "manual_opt_in_auto_rewrite")
        self.assertTrue(review_package["pre_rewrite_attacks"])
        self.assertEqual(revised["request"]["allow_auto_rewrite_after_manual"], True)
        self.assertTrue(revised["revision_history"][-1]["manual_override"])
        self.assertTrue(revised["revision_history"][-1]["allow_auto_rewrite_after_manual"])
        self.assertNotEqual(revised["final_article_result"]["body_markdown"], manual_text)
        self.assertNotIn("REWRITE-ME", revised["final_article_result"]["article_markdown"])
        self.assertIn(
            "Manual override was reviewed and then auto-rewritten because allow_auto_rewrite_after_manual was enabled.",
            revised["article_package"]["editor_notes"],
        )

    def test_article_revision_manual_opt_in_without_manual_text_is_noop(self) -> None:
        draft = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "feedback_profile_dir": self.empty_profile_dir("feedback-empty-manual-opt-in"),
            }
        )
        revised = build_article_revision({"draft_result": draft, "allow_auto_rewrite_after_manual": True})
        self.assertEqual(revised["review_rewrite_package"]["rewrite_mode"], "no_rewrite_needed")
        self.assertFalse(revised["revision_history"][-1]["manual_override"])
        self.assertTrue(revised["revision_history"][-1]["allow_auto_rewrite_after_manual"])

    def test_article_revision_preserves_manual_article_markdown_independently(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        manual_article = "# Manual article\n\nUnique marker: KEEP-ME-ARTICLE.\n"
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_article_markdown": manual_article,
            }
        )
        self.assertEqual(revised["review_rewrite_package"]["rewrite_mode"], "manual_preserved")
        self.assertEqual(revised["final_article_result"]["article_markdown"], manual_article)
        self.assertIn("KEEP-ME-ARTICLE", revised["final_article_result"]["article_markdown"])
        self.assertTrue(revised["article_package"]["manual_article_override"])
        self.assertFalse(revised["article_package"]["manual_body_override"])

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

    def test_article_draft_reuses_loaded_profiles_when_building_status(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-status-cache")
        with patch("article_draft_flow_runtime.feedback_profile_status", wraps=real_feedback_profile_status) as status_mock:
            build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        self.assertTrue(status_mock.called)
        self.assertIn("profiles", status_mock.call_args.kwargs)
        self.assertIsInstance(status_mock.call_args.kwargs["profiles"], dict)

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

    def test_revision_human_feedback_preferences_auto_save_when_scope_is_consistent(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-auto-derived")
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        revised = build_article_revision(
            {
                "draft_result": draft,
                "feedback_profile_dir": str(profile_dir),
                "human_feedback_form": {
                    "overall_goal_in_plain_english": "Keep the opening grounded in what is confirmed.",
                    "what_to_remember_next_time": [
                        {
                            "key": "must_include",
                            "value": "Lead with the strongest confirmed fact before any scenario.",
                            "scope": "topic",
                            "why": "This is the default framing I want for this topic.",
                        }
                    ],
                },
            }
        )
        self.assertTrue(revised["saved_feedback_profiles"])
        self.assertEqual(revised["request"]["persist_feedback"]["scope"], "topic")
        self.assertIn(
            "Lead with the strongest confirmed fact before any scenario.",
            revised["request"]["persist_feedback"]["defaults"]["must_include"],
        )

        applied = build_article_draft(
            {
                "source_result": run_news_index(self.news_request),
                "feedback_profile_dir": str(profile_dir),
                "topic": draft["request"]["topic"],
            }
        )
        self.assertIn(
            "Lead with the strongest confirmed fact before any scenario.",
            applied["request"]["must_include"],
        )

    def test_article_revision_uses_evidence_bundle_when_draft_context_lists_are_missing(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "draft_mode": "image_first", "image_strategy": "prefer_images"})
        expected_citations = draft["evidence_bundle"]["citations"]
        expected_images = draft["evidence_bundle"]["image_candidates"]
        draft["draft_context"]["citation_candidates"] = []
        draft["draft_context"]["image_candidates"] = []
        draft["article_package"]["citations"] = []
        draft["article_package"]["selected_images"] = []
        draft["article_package"]["image_blocks"] = []

        revised = build_article_revision({"draft_result": draft})

        self.assertEqual(revised["draft_context"]["citation_candidates"], expected_citations)
        self.assertEqual(revised["draft_context"]["image_candidates"], expected_images)
        self.assertEqual(revised["evidence_bundle"]["citations"], expected_citations)
        self.assertEqual(revised["evidence_bundle"]["image_candidates"], expected_images)

    def test_article_revision_reuses_cached_feedback_profile_status_when_no_profile_save_occurs(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-revision-status-cache")
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})

        with patch("article_revise_flow_runtime.feedback_profile_status", wraps=real_feedback_profile_status) as status_mock:
            revised = build_article_revision({"draft_result": draft, "feedback_profile_dir": str(profile_dir)})

        self.assertFalse(status_mock.called)
        self.assertEqual(revised["feedback_profile_status"], draft["article_package"]["feedback_profile_status"])

    def test_article_revision_rebuild_preserves_localized_images_without_refetch(self) -> None:
        case_dir = self.case_dir("revision-localized-image-rebuild")
        draft = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": True,
                "draft_mode": "balanced",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        original_image = draft["article_package"]["selected_images"][0]
        original_path = original_image["path"]
        self.assertEqual(original_image["status"], "local_ready")
        self.assertTrue(Path(original_path).exists())

        with patch("article_draft_flow_runtime.fetch_remote_asset", side_effect=AssertionError("refetch should not run")):
            revised = build_article_revision(
                {
                    "draft_result": draft,
                    "title_hint": "Rebuilt title keeps image cache",
                }
            )

        revised_image = revised["article_package"]["selected_images"][0]
        self.assertEqual(revised_image["status"], "local_ready")
        self.assertEqual(revised_image["path"], original_path)
        self.assertEqual(revised["asset_localization"]["downloaded_count"], 0)
        self.assertEqual(revised["draft_context"]["image_candidates"][0]["path"], original_path)
        self.assertEqual(revised["evidence_bundle"]["image_candidates"][0]["path"], original_path)

    def test_article_revision_auto_rewrite_preserves_localized_images_without_refetch(self) -> None:
        case_dir = self.case_dir("revision-localized-image-auto-rewrite")
        draft = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": True,
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        original_path = draft["article_package"]["selected_images"][0]["path"]
        self.assertTrue(Path(original_path).exists())

        with patch("article_draft_flow_runtime.fetch_remote_asset", side_effect=AssertionError("refetch should not run")):
            revised = build_article_revision(
                {
                    "draft_result": draft,
                    "edited_body_markdown": "# Manual body\n\nOverstated claim.",
                    "edited_article_markdown": "# Manual body\n\nOverstated claim.",
                    "allow_auto_rewrite_after_manual": True,
                }
            )

        revised_image = revised["article_package"]["selected_images"][0]
        self.assertEqual(revised["review_rewrite_package"]["rewrite_mode"], "manual_opt_in_auto_rewrite")
        self.assertEqual(revised_image["status"], "local_ready")
        self.assertEqual(revised_image["path"], original_path)
        self.assertEqual(revised["asset_localization"]["downloaded_count"], 0)
        self.assertEqual(revised["draft_context"]["image_candidates"][0]["path"], original_path)

    def test_revision_feedback_profiles_write_history_backups_before_overwrite(self) -> None:
        profile_dir = self.case_dir("feedback-profiles-history")
        first_draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        build_article_revision(
            {
                "draft_result": first_draft,
                "feedback_profile_dir": str(profile_dir),
                "persist_feedback": {
                    "scope": "global",
                    "defaults": {"tone": "neutral-cautious"},
                },
            }
        )

        second_draft = build_article_draft({"source_result": run_news_index(self.news_request), "feedback_profile_dir": str(profile_dir)})
        revised = build_article_revision(
            {
                "draft_result": second_draft,
                "feedback_profile_dir": str(profile_dir),
                "persist_feedback": {
                    "scope": "global",
                    "defaults": {"tone": "urgent-but-cautious"},
                },
            }
        )
        self.assertTrue(revised["profile_backup_paths"])
        backup_path = Path(revised["profile_backup_paths"][0])
        self.assertTrue(backup_path.exists())
        status = revised["feedback_profile_status"]
        self.assertGreaterEqual(status["global_history_count"], 1)
        self.assertTrue(status["latest_global_backup_path"])

    def test_style_learning_does_not_turn_manual_fact_edits_into_reusable_defaults(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
        manual_article = "# Manual article\n\nIran has already accepted a final ground-war deal and the sources are settled.\n"
        revised = build_article_revision(
            {
                "draft_result": draft,
                "edited_body_markdown": manual_article,
                "edited_article_markdown": manual_article,
                "edit_reason_feedback": {
                    "summary": "This was a factual correction, not a house style preference.",
                    "changes": [
                        {
                            "area": "claims",
                            "reason_tag": "factual_caution",
                            "why": "I was correcting what the draft implied about negotiation certainty.",
                            "reuse_scope": "none",
                        }
                    ],
                },
            }
        )
        learning = revised["style_learning"]
        defaults_blob = json.dumps(learning["proposed_profile_feedback"]["defaults"], ensure_ascii=False)
        self.assertEqual(learning["proposed_profile_feedback"]["defaults"], {})
        self.assertNotIn("ground-war deal", defaults_blob)
        self.assertTrue(learning["low_confidence_rules"])
        self.assertTrue(any("evidence-bound editing" in item for item in learning["excluded_signals"]))
        self.assertTrue(learning["excluded_signals"] or learning["profile_update_decision"]["status"] in {"record_only", "hold"})

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
        self.assertTrue(Path(result["brief_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["preview_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["revision_template_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["revision_form_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["feedback_markdown_path"]).exists())
        self.assertTrue(Path(result["final_stage"]["result_path"]).exists())
        draft_result = read_json(Path(result["draft_stage"]["result_path"]))
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["citation_count"], 1)
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["image_count"], 1)
        revision_template = read_json(Path(result["review_stage"]["revision_template_path"]))
        self.assertEqual(revision_template["persist_feedback"]["use_current_request_defaults"], True)
        self.assertIn("feedback_profile_status", revision_template)
        self.assertIn("language_mode", revision_template)
        self.assertIn("image_strategy", revision_template)
        self.assertIn("edited_article_markdown", revision_template)
        self.assertIn("human_feedback_form", revision_template)
        self.assertIn("review_form_quickstart", revision_template)
        self.assertIn("review_focus_suggestions", revision_template)
        self.assertIn("how_to_use", revision_template["human_feedback_form"]["help"])
        self.assertIn("edit_reason_feedback", revision_template)
        self.assertIn("reason_tags", revision_template["edit_reason_feedback"]["help"])
        self.assertIn("preference_keys", revision_template["edit_reason_feedback"]["help"])
        self.assertEqual(revision_template["allow_auto_rewrite_after_manual"], False)
        self.assertIn("human_signal_ratio", revision_template)
        self.assertIn("personal_phrase_bank", revision_template)
        self.assertIn("human_signal_ratio", revision_template["persist_feedback"]["defaults"])
        self.assertIn("personal_phrase_bank", revision_template["persist_feedback"]["defaults"])
        self.assertIn("decision_trace", result)
        self.assertIn("recommended_thesis", result["decision_trace"]["brief"])
        self.assertIn("style_effective_request", result["decision_trace"]["draft"])
        self.assertIn("human_signal_ratio", result["decision_trace"]["draft"]["style_effective_request"])
        self.assertIn("quality_gate", result["decision_trace"]["review"])
        self.assertIn("## Why This Draft Looks This Way", result["report_markdown"])
        self.assertIn("## Claim Support Map", result["report_markdown"])
        self.assertIn("## Red Team Summary", result["report_markdown"])
        self.assertIn("## Learning Signals", result["report_markdown"])
        self.assertIn("## Images", result["report_markdown"])
        self.assertIn("## Feedback Reuse", result["report_markdown"])
        self.assertIn("## Files", result["report_markdown"])
        self.assertIn("Review form", result["report_markdown"])
        self.assertIn("Feedback markdown", result["report_markdown"])
        self.assertIn("Rewrite mode", result["report_markdown"])
        self.assertIn("Pre-rewrite quality gate", result["report_markdown"])
        self.assertIn("learning_stage", result)
        self.assertIn("change_summary_preview", result["learning_stage"])
        self.assertIn("high_confidence_rule_preview", result["learning_stage"])
        self.assertIn("proposed_default_keys", result["learning_stage"])
        self.assertIn("brief_stage", result)
        self.assertIn("review_result", result)
        self.assertIn("rewrite_mode", result["final_stage"])
        self.assertIn("pre_rewrite_quality_gate", result["final_stage"])
        self.assertIn("learning_decision", result["review_stage"])
        self.assertIn("learning_change_summary_preview", result["review_stage"])
        self.assertIn("Learning summary:", result["report_markdown"])
        revision_form_markdown = Path(result["review_stage"]["revision_form_path"]).read_text(encoding="utf-8-sig")
        self.assertIn("# Article Feedback", revision_form_markdown)
        self.assertIn("## Overall Goal", revision_form_markdown)
        self.assertIn("## Suggested Review Focus", revision_form_markdown)
        self.assertIn("## Optional Full Rewrite", revision_form_markdown)
        self.assertIn("ARTICLE-FEEDBACK.md", result["review_stage"]["feedback_markdown_path"])
        self.assertIn("ARTICLE-FEEDBACK.md", result["review_stage"]["suggested_revise_command"])

    def test_article_workflow_runs_from_realistic_offline_request(self) -> None:
        workflow_dir = self.case_dir("workflow-realistic-run")
        result = run_article_workflow(
            {
                **self.realistic_news_request,
                "output_dir": str(workflow_dir / "out"),
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 3,
            }
        )
        self.assertEqual(result["source_stage"]["source_kind"], "news_index")
        self.assertTrue(Path(result["source_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["final_stage"]["result_path"]).exists())
        draft_result = read_json(Path(result["draft_stage"]["result_path"]))
        citation_urls = [item["url"] for item in draft_result["draft_context"]["citation_candidates"]]
        blocked_sources = result["source_result"]["retrieval_run_report"]["sources_blocked"]
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["citation_count"], 6)
        self.assertTrue(any("reuters.com" in url for url in citation_urls))
        self.assertTrue(any(item["source_name"] == "Axios" for item in blocked_sources))
        self.assertGreaterEqual(result["draft_stage"]["image_count"], 1)
        self.assertGreaterEqual(result["asset_stage"]["local_ready_count"], 1)
        self.assertIn("Rewrite mode", result["report_markdown"])
        self.assertIn("Red Team Summary", result["report_markdown"])

    def test_article_workflow_news_request_can_augment_with_agent_reach(self) -> None:
        workflow_dir = self.case_dir("workflow-agent-reach-run")
        request = {
            "topic": "Indirect talks and energy shock",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-core",
                    "claim_text": "Indirect talks continue through intermediaries.",
                }
            ],
            "candidates": [
                {
                    "source_id": "gov-1",
                    "source_name": "Oman Foreign Ministry",
                    "source_type": "government",
                    "published_at": "2026-03-24T11:20:00+00:00",
                    "observed_at": "2026-03-24T11:25:00+00:00",
                    "url": "https://example.com/oman-talks",
                    "text_excerpt": "Indirect talks continue through intermediaries.",
                    "claim_ids": ["claim-core"],
                    "claim_states": {"claim-core": "support"},
                }
            ],
            "agent_reach": {"enabled": True, "channels": ["youtube"]},
            "output_dir": str(workflow_dir / "out"),
        }
        fake_bridge = {
            "channels_attempted": ["youtube"],
            "channels_succeeded": ["youtube"],
            "channels_failed": [],
            "observations_imported": 1,
            "report_markdown": "# Agent Reach Bridge Report",
            "retrieval_request": {
                "candidates": [
                    {
                        "source_id": "agent-youtube-1",
                        "source_name": "YouTube CBS News",
                        "source_type": "social",
                        "origin": "agent_reach",
                        "agent_reach_channel": "youtube",
                        "published_at": "2026-03-24T11:40:00+00:00",
                        "observed_at": "2026-03-24T11:45:00+00:00",
                        "url": "https://www.youtube.com/watch?v=test",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                        "text_excerpt": "Video recap of talks and energy disruption.",
                        "channel": "shadow",
                        "access_mode": "public",
                    }
                ]
            },
        }
        with patch("article_workflow_runtime.run_agent_reach_bridge", return_value=fake_bridge):
            result = run_article_workflow(request)

        self.assertEqual(result["source_stage"]["source_kind"], "news_index_agent_reach")
        self.assertTrue(Path(result["source_stage"]["agent_reach_stage"]["result_path"]).exists())
        self.assertTrue(any(item.get("origin") == "agent_reach" for item in result["source_result"]["observations"]))
        self.assertIn("Agent Reach Augmentation", result["report_markdown"])
        self.assertIn("agent-reach-bridge-result.json", result["report_markdown"])

    def test_article_workflow_respects_agent_reach_enabled_false(self) -> None:
        workflow_dir = self.case_dir("workflow-agent-reach-disabled")
        request = {
            "topic": "Indirect talks and energy shock",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-core",
                    "claim_text": "Indirect talks continue through intermediaries.",
                }
            ],
            "candidates": [
                {
                    "source_id": "gov-1",
                    "source_name": "Oman Foreign Ministry",
                    "source_type": "government",
                    "published_at": "2026-03-24T11:20:00+00:00",
                    "observed_at": "2026-03-24T11:25:00+00:00",
                    "url": "https://example.com/oman-talks",
                    "text_excerpt": "Indirect talks continue through intermediaries.",
                    "claim_ids": ["claim-core"],
                    "claim_states": {"claim-core": "support"},
                }
            ],
            "agent_reach": {"enabled": False, "channels": ["youtube"]},
            "output_dir": str(workflow_dir / "out"),
        }
        with patch("article_workflow_runtime.run_agent_reach_bridge") as bridge_mock:
            result = run_article_workflow(request)

        bridge_mock.assert_not_called()
        self.assertEqual(result["source_stage"]["source_kind"], "news_index")
        self.assertEqual(result["source_stage"].get("agent_reach_stage") or {}, {})

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
                "max_parallel_topics": 2,
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
        self.assertTrue(Path(result["items"][0]["final_article_result_path"]).exists())
        self.assertTrue(Path(result["items"][1]["final_article_result_path"]).exists())
        self.assertIn("rewrite_mode", result["items"][0])
        self.assertIn("pre_rewrite_quality_gate", result["items"][0])
        self.assertIn("quality_gate", result["items"][0])
        self.assertEqual(result["max_parallel_topics"], 2)
        self.assertIn("Local images ready", result["report_markdown"])
        self.assertIn("Rewrite mode", result["report_markdown"])
        self.assertIn("Final quality gate", result["report_markdown"])

    def test_article_auto_queue_ranks_candidates_and_runs_batch_for_top_items(self) -> None:
        auto_dir = self.case_dir("auto-run")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "prefer_visuals": True,
                "max_parallel_candidates": 2,
                "max_parallel_topics": 2,
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
        self.assertEqual(result["max_parallel_candidates"], 2)
        self.assertEqual(result["max_parallel_topics"], 2)
        self.assertEqual(result["ranked_candidates"][0]["selection_status"], "selected")
        self.assertEqual(result["ranked_candidates"][1]["selection_status"], "skipped")
        self.assertIn("Final quality gate", result["report_markdown"])
        self.assertIn("Selection", result["report_markdown"])

    def test_article_batch_workflow_surfaces_reddit_operator_review_gate(self) -> None:
        batch_dir = self.case_dir("batch-reddit-review-gate")
        result = run_article_batch_workflow(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(batch_dir / "out"),
                "items": [
                    {
                        "label": "reddit-reviewed-item",
                        "payload": self.build_reddit_operator_review_source_result(),
                    }
                ],
            }
        )

        self.assertEqual(result["succeeded_items"], 1)
        self.assertEqual(result["items"][0]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["items"][0]["manual_review_status"], "awaiting_reddit_operator_review")
        self.assertEqual(
            result["items"][0]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertEqual(
            result["items"][0]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertEqual(result["items"][0]["manual_review_required_count"], 1)
        self.assertEqual(result["items"][0]["manual_review_high_priority_count"], 1)
        self.assertIn("Publication readiness", result["report_markdown"])
        self.assertIn("Reddit operator review", result["report_markdown"])

    def test_article_auto_queue_surfaces_reddit_operator_review_gate(self) -> None:
        auto_dir = self.case_dir("auto-reddit-review-gate")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "candidates": [
                    {
                        "label": "reddit-reviewed-candidate",
                        "payload": self.build_reddit_operator_review_source_result(),
                    }
                ],
            }
        )

        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["ranked_candidates"][0]["final_publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["ranked_candidates"][0]["final_manual_review_status"], "awaiting_reddit_operator_review")
        self.assertEqual(
            result["ranked_candidates"][0]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertEqual(
            result["ranked_candidates"][0]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertEqual(result["ranked_candidates"][0]["final_manual_review_required_count"], 1)
        self.assertEqual(result["ranked_candidates"][0]["final_manual_review_high_priority_count"], 1)
        self.assertIn("Publication readiness", result["report_markdown"])
        self.assertIn("Reddit operator review", result["report_markdown"])

    def test_key_article_scripts_compile_cleanly(self) -> None:
        script_dir = Path(__file__).resolve().parents[1] / "scripts"
        for name in [
            "article_brief.py",
            "article_draft.py",
            "article_feedback_markdown.py",
            "article_revise.py",
            "article_workflow.py",
            "article_brief_runtime.py",
            "article_draft_flow_runtime.py",
            "article_revise_flow_runtime.py",
            "article_workflow_runtime.py",
        ]:
            py_compile.compile(str(script_dir / name), doraise=True)

    def test_article_auto_queue_propagates_default_language_mode(self) -> None:
        auto_dir = self.case_dir("auto-language")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "default_language_mode": "bilingual",
                "candidates": [
                    {
                        "label": "news-candidate",
                        "payload": self.news_request,
                    }
                ],
            }
        )
        batch_request = read_json(Path(result["batch_request_path"]))
        self.assertEqual(batch_request["default_language_mode"], "bilingual")
        batch_result = read_json(Path(result["batch_result"]["result_path"]))
        workflow_result = read_json(Path(batch_result["items"][0]["workflow_result_path"]))
        self.assertEqual(workflow_result["draft_result"]["request"]["language_mode"], "bilingual")

    def test_article_auto_queue_can_rank_news_candidate_with_agent_reach_augmentation(self) -> None:
        auto_dir = self.case_dir("auto-agent-reach")
        request = {
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "output_dir": str(auto_dir / "out"),
            "top_n": 1,
            "candidates": [
                {
                    "label": "agent-reach-news-candidate",
                    "payload": {
                        "topic": "Indirect talks and energy shock",
                        "analysis_time": "2026-03-24T12:00:00+00:00",
                        "claims": [
                            {
                                "claim_id": "claim-core",
                                "claim_text": "Indirect talks continue through intermediaries.",
                            }
                        ],
                        "candidates": [
                            {
                                "source_id": "gov-1",
                                "source_name": "Oman Foreign Ministry",
                                "source_type": "government",
                                "published_at": "2026-03-24T11:20:00+00:00",
                                "observed_at": "2026-03-24T11:25:00+00:00",
                                "url": "https://example.com/oman-talks",
                                "text_excerpt": "Indirect talks continue through intermediaries.",
                                "claim_ids": ["claim-core"],
                                "claim_states": {"claim-core": "support"},
                            }
                        ],
                        "agent_reach": {"enabled": True, "channels": ["youtube"]},
                    },
                }
            ],
        }
        fake_bridge = {
            "channels_attempted": ["youtube"],
            "channels_succeeded": ["youtube"],
            "channels_failed": [],
            "observations_imported": 1,
            "retrieval_request": {
                "candidates": [
                    {
                        "source_id": "agent-youtube-1",
                        "source_name": "YouTube CBS News",
                        "source_type": "social",
                        "origin": "agent_reach",
                        "agent_reach_channel": "youtube",
                        "published_at": "2026-03-24T11:40:00+00:00",
                        "observed_at": "2026-03-24T11:45:00+00:00",
                        "url": "https://www.youtube.com/watch?v=test",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                        "text_excerpt": "Video recap of talks and energy disruption.",
                        "channel": "shadow",
                        "access_mode": "public",
                    }
                ]
            },
        }
        with patch("article_auto_queue_runtime.run_agent_reach_bridge", return_value=fake_bridge):
            result = run_article_auto_queue(request)

        self.assertEqual(result["ranked_candidates"][0]["source_kind"], "news_index_agent_reach")
        batch_result = read_json(Path(result["batch_result"]["result_path"]))
        workflow_result = read_json(Path(batch_result["items"][0]["workflow_result_path"]))
        self.assertTrue(any(item.get("origin") == "agent_reach" for item in workflow_result["source_result"]["observations"]))

    def test_article_auto_queue_survives_parallel_candidate_failure(self) -> None:
        auto_dir = self.case_dir("auto-partial")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "max_parallel_candidates": 2,
                "candidates": [
                    {
                        "label": "broken-candidate",
                    },
                    {
                        "label": "good-candidate",
                        "payload": self.news_request,
                    },
                ],
            }
        )
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["batch_result"]["succeeded_items"], 1)
        self.assertTrue(any(item["status"] == "error" for item in result["ranked_candidates"]))
        self.assertTrue(Path(result["batch_result"]["result_path"]).exists())

    def test_news_index_survives_parallel_candidate_normalization_failure(self) -> None:
        class ExplodingText:
            def __str__(self) -> str:
                raise RuntimeError("boom")

        result = run_news_index(
            {
                "topic": "Normalization failure",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "max_parallel_candidates": 2,
                "claims": [
                    {
                        "claim_id": "claim-test",
                        "claim_text": "A transport movement is underway.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "good-source",
                        "source_name": "Wire Desk",
                        "source_type": "wire",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:31:00+00:00",
                        "url": "https://example.com/good",
                        "text_excerpt": "A transport movement is underway.",
                        "claim_ids": ["claim-test"],
                        "claim_states": {"claim-test": "support"},
                    },
                    {
                        "source_id": "bad-source",
                        "source_name": "Broken Feed",
                        "source_type": "social",
                        "published_at": "2026-03-24T11:50:00+00:00",
                        "observed_at": "2026-03-24T11:51:00+00:00",
                        "url": "https://example.com/bad",
                        "text_excerpt": ExplodingText(),
                        "claim_ids": ["claim-test"],
                    },
                ],
            }
        )
        self.assertEqual(len(result["observations"]), 2)
        blocked = [item for item in result["observations"] if item["access_mode"] == "blocked"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["channel"], "background")
        self.assertIn("normalization failed", blocked[0]["text_excerpt"].lower())
        self.assertEqual(result["retrieval_run_report"]["sources_blocked"][0]["source_id"], "bad-source")
        self.assertGreaterEqual(result["retrieval_quality"]["blocked_source_handling_score"], 80)


def _override_test_article_draft_applies_style_memory_from_feedback_profile(self: ArticleWorkflowTests) -> None:
    profile_dir = self.case_dir("feedback-profiles-style-memory")
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "global.json").write_text(
        json.dumps(
            {
                "scope": "global",
                "topic": "global",
                "request_defaults": {
                    "language_mode": "chinese",
                    "human_signal_ratio": 76,
                },
                "style_memory": {
                    "target_band": "3.4",
                    "voice_summary": "结论先行，判断明确，但别写成模板审查口吻。",
                    "preferred_transitions": ["先说结论", "更关键的是"],
                    "must_land": ["把影响路径写在前面", "优先回答读者真正关心的变量"],
                    "avoid_patterns": ["当前最稳妥的写法是"],
                    "slot_lines": {
                        "subtitle": ["先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。"],
                        "impact": ["真正该盯的，是这件事会不会继续改写预算、预期和定价。"],
                        "watch": ["接下来别忙着站队，先盯那几个会把叙事坐实的硬信号。"],
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    draft = build_article_draft(
        {
            "source_result": self.build_clean_core_news_result(),
            "feedback_profile_dir": str(profile_dir),
        }
    )

    self.assertEqual(draft["request"]["style_memory"]["target_band"], "3.4")
    self.assertIn("先说结论", draft["request"]["personal_phrase_bank"])
    self.assertIn("把影响路径写在前面", draft["request"]["must_include"])
    self.assertIn("当前最稳妥的写法是", draft["request"]["must_avoid"])
    self.assertEqual(draft["article_package"]["subtitle"], "先把发生了什么说清楚，再看这件事为什么会继续发酵。")
    self.assertEqual(draft["article_package"]["style_profile_applied"]["style_memory"]["target_band"], "3.4")


def _override_test_article_revision_preserves_style_memory_from_prior_request(self: ArticleWorkflowTests) -> None:
    draft = build_article_draft(
        {
            "source_result": self.build_clean_core_news_result(),
            "language_mode": "chinese",
            "style_memory": {
                "target_band": "3.4",
                "slot_lines": {
                    "subtitle": ["先把更硬的变量拎出来，再看这波讨论会不会继续往经营和定价上传。"],
                },
            },
        }
    )
    revised = build_article_revision({"draft_result": draft, "title_hint": "改一个标题但保留风格记忆"})
    self.assertEqual(revised["request"]["style_memory"]["target_band"], "3.4")
    self.assertEqual(revised["article_package"]["style_profile_applied"]["style_memory"]["target_band"], "3.4")
    self.assertEqual(revised["article_package"]["subtitle"], "先把发生了什么说清楚，再看这件事为什么会继续发酵。")


ArticleWorkflowTests.test_article_draft_applies_style_memory_from_feedback_profile = (
    _override_test_article_draft_applies_style_memory_from_feedback_profile
)
ArticleWorkflowTests.test_article_revision_preserves_style_memory_from_prior_request = (
    _override_test_article_revision_preserves_style_memory_from_prior_request
)


def _test_article_draft_keeps_business_shorthand_for_business_topics(self: ArticleWorkflowTests) -> None:
    request = {
        "topic": "AI Agent hiring rebound starts showing up in startup budgets and pricing",
        "must_include": [
            "招聘节奏、订单转化和预算投放开始重新联动",
            "商业化交付和定价能力开始变得更重要",
        ],
    }

    self.assertTrue(topic_prefers_business_shorthand(request))


ArticleWorkflowTests.test_article_draft_keeps_business_shorthand_for_business_topics = (
    _test_article_draft_keeps_business_shorthand_for_business_topics
)


if __name__ == "__main__":
    unittest.main()
