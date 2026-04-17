#!/usr/bin/env python3
"""Tests for summarize_* helpers in article_workflow_runtime."""
from __future__ import annotations

import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import (
    clean_text_list_preview,
    summarize_asset_stage,
    summarize_brief_decisions,
    summarize_draft_decisions,
    summarize_feedback_stage,
    summarize_learning_rules_preview,
    summarize_style_learning_surface,
)


class TestCleanTextListPreview(unittest.TestCase):

    def test_basic_list(self) -> None:
        result = clean_text_list_preview(["alpha", "beta", "gamma"], limit=2)
        self.assertEqual(result, ["alpha", "beta"])

    def test_empty_input(self) -> None:
        self.assertEqual(clean_text_list_preview([], limit=3), [])
        self.assertEqual(clean_text_list_preview(None, limit=3), [])

    def test_filters_blank_strings(self) -> None:
        result = clean_text_list_preview(["ok", "", "  ", "fine"], limit=5)
        self.assertEqual(result, ["ok", "fine"])

    def test_limit_at_least_one(self) -> None:
        result = clean_text_list_preview(["a", "b", "c"], limit=0)
        self.assertEqual(len(result), 1)

    def test_non_list_input(self) -> None:
        self.assertEqual(clean_text_list_preview("not a list", limit=3), [])


class TestSummarizeLearningRulesPreview(unittest.TestCase):

    def test_basic_rules(self) -> None:
        rules = [
            {"key": "tone", "scope": "global", "confidence": 0.9, "rule_type": "preference", "reason": "user said so"},
            {"key": "draft_mode", "scope": "topic", "confidence": 0.7, "rule_type": "inferred", "reason": "pattern match"},
        ]
        result = summarize_learning_rules_preview(rules, limit=3)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["key"], "tone")
        self.assertAlmostEqual(result[0]["confidence"], 0.9)

    def test_filters_missing_key(self) -> None:
        rules = [{"scope": "global", "confidence": 0.5}]
        result = summarize_learning_rules_preview(rules, limit=3)
        self.assertEqual(result, [])

    def test_empty_input(self) -> None:
        self.assertEqual(summarize_learning_rules_preview([], limit=3), [])
        self.assertEqual(summarize_learning_rules_preview(None, limit=3), [])


class TestSummarizeBriefDecisions(unittest.TestCase):

    def test_full_brief(self) -> None:
        brief = {
            "analysis_brief": {
                "recommended_thesis": "Markets are cautious.",
                "canonical_facts": [
                    {"claim_text": "GDP grew 3%"},
                    {"claim_text": "Inflation fell"},
                ],
                "not_proven": [
                    {"claim_text": "Rate cut likely"},
                ],
                "story_angles": [
                    {"angle": "Risk-off sentiment"},
                ],
                "voice_constraints": ["Be cautious", "Cite sources"],
            }
        }
        result = summarize_brief_decisions(brief)
        self.assertEqual(result["recommended_thesis"], "Markets are cautious.")
        self.assertEqual(result["lead_canonical_fact"], "GDP grew 3%")
        self.assertEqual(result["lead_not_proven"], "Rate cut likely")
        self.assertEqual(result["top_story_angle"], "Risk-off sentiment")
        self.assertEqual(result["canonical_fact_count"], 2)
        self.assertEqual(result["not_proven_count"], 1)

    def test_empty_brief(self) -> None:
        result = summarize_brief_decisions({})
        self.assertEqual(result["recommended_thesis"], "")
        self.assertEqual(result["lead_canonical_fact"], "")
        self.assertEqual(result["canonical_fact_count"], 0)
        self.assertEqual(result["not_proven_count"], 0)


class TestSummarizeDraftDecisions(unittest.TestCase):

    def test_with_article_package(self) -> None:
        draft = {
            "article_package": {
                "title": "Test Title",
                "draft_thesis": "This is the thesis.",
                "draft_claim_map": [
                    {
                        "claim_label": "C1",
                        "claim_text": "Claim text",
                        "citation_ids": ["cit-1"],
                    },
                ],
                "style_profile_applied": {
                    "effective_request": {
                        "language_mode": "english",
                        "draft_mode": "balanced",
                    }
                },
                "writer_risk_notes": ["Check date accuracy"],
            },
        }
        result = summarize_draft_decisions(draft)
        self.assertEqual(result["title"], "Test Title")
        self.assertEqual(result["draft_thesis"], "This is the thesis.")
        self.assertIsInstance(result["top_claims"], list)

    def test_empty_draft(self) -> None:
        result = summarize_draft_decisions({})
        self.assertEqual(result["title"], "")
        self.assertEqual(result["draft_thesis"], "")


class TestSummarizeAssetStage(unittest.TestCase):

    def test_counts_image_statuses(self) -> None:
        draft_result = {
            "article_package": {
                "selected_images": [
                    {"image_id": "i1", "status": "local_ready"},
                    {"image_id": "i2", "status": "remote_only"},
                    {"image_id": "i3", "status": "missing"},
                    {"image_id": "i4", "status": "local_ready"},
                ],
            },
            "asset_localization": {
                "asset_output_dir": "/tmp/assets",
                "downloaded_count": 2,
                "failed_count": 1,
            },
        }
        result = summarize_asset_stage(draft_result, Path("/tmp/draft.json"))
        self.assertEqual(result["local_ready_count"], 2)
        self.assertEqual(result["remote_only_count"], 1)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["downloaded_count"], 2)
        self.assertEqual(result["failed_count"], 1)

    def test_hydrate_command_present_when_remote_only(self) -> None:
        draft = {
            "article_package": {
                "selected_images": [{"image_id": "i1", "status": "remote_only"}],
            },
        }
        result = summarize_asset_stage(draft, Path("/tmp/draft.json"))
        self.assertTrue(len(result["suggested_asset_hydrate_command"]) > 0)

    def test_hydrate_command_empty_when_all_local(self) -> None:
        draft = {
            "article_package": {
                "selected_images": [{"image_id": "i1", "status": "local_ready"}],
            },
        }
        result = summarize_asset_stage(draft, Path("/tmp/draft.json"))
        self.assertEqual(result["suggested_asset_hydrate_command"], "")

    def test_empty_images(self) -> None:
        result = summarize_asset_stage({}, Path("/tmp/draft.json"))
        self.assertEqual(result["local_ready_count"], 0)
        self.assertEqual(result["remote_only_count"], 0)
        self.assertEqual(result["missing_count"], 0)


class TestSummarizeFeedbackStage(unittest.TestCase):

    def test_returns_cached_status_when_present(self) -> None:
        cached = {
            "global_exists": True,
            "topic_exists": False,
            "global_history_count": 3,
        }
        result = summarize_feedback_stage({"feedback_profile_status": cached})
        self.assertTrue(result["global_exists"])
        self.assertEqual(result["global_history_count"], 3)

    def test_returns_fresh_status_from_request(self) -> None:
        fixtures = Path(__file__).resolve().parent / "fixtures" / "article-workflow-canonical" / "empty-profile"
        draft = {
            "request": {
                "feedback_profile_dir": str(fixtures),
                "topic": "test-topic",
            }
        }
        result = summarize_feedback_stage(draft)
        self.assertIn("global_exists", result)
        self.assertIn("topic_exists", result)


class TestSummarizeStyleLearningSurface(unittest.TestCase):

    def test_full_surface(self) -> None:
        learning = {
            "high_confidence_rules": [
                {"key": "tone", "scope": "global", "confidence": 0.95, "rule_type": "preference", "reason": "explicit"},
            ],
            "medium_confidence_rules": [],
            "low_confidence_rules": [],
            "explicit_change_count": 2,
            "explicit_preference_count": 1,
            "used_explicit_feedback": True,
            "change_summary": ["Changed tone to cautious"],
            "excluded_signals": [],
            "proposed_profile_feedback": {
                "defaults": {"tone": "cautious", "language_mode": "english"},
            },
        }
        decision = {"status": "applied", "reason": "Strong signal"}
        result = summarize_style_learning_surface(learning, decision)
        self.assertEqual(result["decision"], "applied")
        self.assertEqual(result["reason"], "Strong signal")
        self.assertEqual(result["high_confidence_rule_count"], 1)
        self.assertEqual(result["explicit_change_count"], 2)
        self.assertTrue(result["used_explicit_feedback"])
        self.assertIn("tone", result["proposed_default_keys"])

    def test_empty_learning(self) -> None:
        result = summarize_style_learning_surface({}, {})
        self.assertEqual(result["decision"], "")
        self.assertEqual(result["high_confidence_rule_count"], 0)


if __name__ == "__main__":
    unittest.main()
