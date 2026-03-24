#!/usr/bin/env python3
from __future__ import annotations

import os
import py_compile
import unittest
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
from article_revise_flow_runtime import build_article_revision, build_red_team_review
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
        self.assertEqual(len(package["selected_images"]), len(package["image_blocks"]))
        self.assertTrue(draft["analysis_brief"])
        self.assertTrue(package["draft_claim_map"])
        self.assertIn("draft_thesis", package)
        self.assertIn("style_profile_applied", package)
        self.assertIn("writer_risk_notes", package)

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
                {"citation_id": "S1", "source_id": "wire-1"},
                {"citation_id": "S2", "source_id": "gov-1"},
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
        self.assertTrue(Path(result["brief_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["draft_stage"]["preview_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["result_path"]).exists())
        self.assertTrue(Path(result["review_stage"]["revision_template_path"]).exists())
        self.assertTrue(Path(result["final_stage"]["result_path"]).exists())
        draft_result = read_json(Path(result["draft_stage"]["result_path"]))
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["citation_count"], 1)
        self.assertGreaterEqual(draft_result["article_package"]["draft_metrics"]["image_count"], 1)
        revision_template = read_json(Path(result["review_stage"]["revision_template_path"]))
        self.assertEqual(revision_template["persist_feedback"]["use_current_request_defaults"], True)
        self.assertIn("feedback_profile_status", revision_template)
        self.assertIn("language_mode", revision_template)
        self.assertIn("image_strategy", revision_template)
        self.assertIn("decision_trace", result)
        self.assertIn("recommended_thesis", result["decision_trace"]["brief"])
        self.assertIn("style_effective_request", result["decision_trace"]["draft"])
        self.assertIn("quality_gate", result["decision_trace"]["review"])
        self.assertIn("## Why This Draft Looks This Way", result["report_markdown"])
        self.assertIn("## Claim Support Map", result["report_markdown"])
        self.assertIn("## Red Team Summary", result["report_markdown"])
        self.assertIn("## Images", result["report_markdown"])
        self.assertIn("## Feedback Reuse", result["report_markdown"])
        self.assertIn("## Files", result["report_markdown"])
        self.assertIn("Rewrite mode", result["report_markdown"])
        self.assertIn("Pre-rewrite quality gate", result["report_markdown"])
        self.assertIn("brief_stage", result)
        self.assertIn("review_result", result)
        self.assertIn("rewrite_mode", result["final_stage"])
        self.assertIn("pre_rewrite_quality_gate", result["final_stage"])

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
        self.assertEqual(result["max_parallel_topics"], 2)
        self.assertIn("Local images ready", result["report_markdown"])

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

    def test_key_article_scripts_compile_cleanly(self) -> None:
        script_dir = Path(__file__).resolve().parents[1] / "scripts"
        for name in [
            "article_brief.py",
            "article_draft.py",
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
