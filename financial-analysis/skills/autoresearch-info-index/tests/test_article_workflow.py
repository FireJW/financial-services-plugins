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
from article_draft_flow_runtime import build_article_draft, build_draft_claim_map, build_sections
from article_feedback_markdown import parse_feedback_markdown
from article_feedback_profiles import feedback_profile_status as real_feedback_profile_status
from article_revise import build_payload as build_article_revise_payload
from article_revise_flow_runtime import build_article_revision, build_red_team_review
from article_batch_workflow_runtime import run_article_batch_workflow
from article_auto_queue_runtime import run_article_auto_queue
from article_workflow_runtime import build_revision_template, run_article_workflow
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

    def test_article_brief_report_surfaces_image_keep_reasons(self) -> None:
        brief = build_analysis_brief({"source_result": self.build_seed_x_index_result(self.case_dir("brief-x-seed"))})
        self.assertTrue(brief["analysis_brief"]["image_keep_reasons"])
        self.assertIn("## Image Keep Reasons", brief["report_markdown"])

    def test_article_draft_from_x_index_selects_images_and_citations(self) -> None:
        draft = build_article_draft({"source_result": self.build_seed_x_index_result(self.case_dir("x-seed")), "max_images": 2})
        package = draft["article_package"]
        self.assertEqual(draft["source_summary"]["source_kind"], "x_index")
        self.assertGreaterEqual(package["draft_metrics"]["image_count"], 1)
        self.assertGreaterEqual(package["draft_metrics"]["citation_count"], 1)
        self.assertIn("Images And Screenshots", package["body_markdown"])
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
        draft = build_article_draft({"source_result": source_result, "max_images": 2, "image_strategy": "prefer_images"})
        selected_post_media = next(item for item in draft["article_package"]["selected_images"] if item["role"] == "post_media")
        self.assertEqual(selected_post_media["caption"], "Browser-captured image from the original X post.")
        self.assertEqual(selected_post_media["status"], "local_ready")

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

    def test_build_sections_without_analysis_brief_uses_derived_brief_path(self) -> None:
        draft = build_article_draft({"source_result": run_news_index(self.news_request), "target_length_chars": 800})
        sections = build_sections(
            draft["request"],
            draft["source_summary"],
            draft["evidence_digest"],
            draft["draft_context"]["citation_candidates"],
            draft["draft_context"]["selected_images"],
            None,
        )
        headings = [section["heading"] for section in sections]
        self.assertIn("Story Angles", headings)
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
        self.assertIn("核心判断 | Bottom Line", draft["article_package"]["body_markdown"])
        self.assertIn("截至", draft["article_package"]["body_markdown"])
        self.assertIn("English title", draft["article_package"]["article_markdown"])

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
        draft = build_article_draft({"source_result": run_news_index(self.news_request)})
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
        self.assertIn("decision_trace", result)
        self.assertIn("recommended_thesis", result["decision_trace"]["brief"])
        self.assertIn("style_effective_request", result["decision_trace"]["draft"])
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
        self.assertIn("brief_stage", result)
        self.assertIn("review_result", result)
        self.assertIn("rewrite_mode", result["final_stage"])
        self.assertIn("pre_rewrite_quality_gate", result["final_stage"])
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


if __name__ == "__main__":
    unittest.main()
