#!/usr/bin/env python3
"""Tests for build_draft_payload, build_brief_payload, and build_revision_template."""
from __future__ import annotations

import shutil
import unittest
from copy import deepcopy
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import (
    build_brief_payload,
    build_draft_payload,
    build_revision_template,
    normalize_workflow_request,
)
from news_index_core import run_news_index


def _minimal_news_result() -> dict:
    return run_news_index(
        {
            "topic": "Test topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [{"claim_id": "c1", "claim_text": "Claim one."}],
            "candidates": [
                {
                    "source_id": "s1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T11:30:00+00:00",
                    "url": "https://example.com/r1",
                    "text_excerpt": "Claim one confirmed.",
                    "claim_ids": ["c1"],
                    "claim_states": {"c1": "support"},
                },
            ],
        }
    )


def _normalized_request(**overrides: object) -> dict:
    base = {
        "source_result": _minimal_news_result(),
        "output_dir": str(Path.cwd() / ".tmp" / "test-draft-payload"),
    }
    base.update(overrides)
    return normalize_workflow_request(base)


class TestBuildDraftPayload(unittest.TestCase):
    """Tests for build_draft_payload field forwarding."""

    def test_source_result_included(self) -> None:
        req = _normalized_request()
        source = _minimal_news_result()
        payload = build_draft_payload(req, source)
        self.assertIn("source_result", payload)
        self.assertIsInstance(payload["source_result"], dict)

    def test_topic_forwarded(self) -> None:
        req = _normalized_request(topic="Custom topic")
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["topic"], "Custom topic")

    def test_image_strategy_forwarded(self) -> None:
        req = _normalized_request(image_strategy="prefer_images")
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["image_strategy"], "prefer_images")

    def test_draft_mode_forwarded(self) -> None:
        req = _normalized_request(draft_mode="image_first")
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["draft_mode"], "image_first")

    def test_max_images_forwarded(self) -> None:
        req = _normalized_request(max_images=5)
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["max_images"], 5)

    def test_language_mode_forwarded(self) -> None:
        req = _normalized_request(language_mode="chinese")
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["language_mode"], "chinese")

    def test_asset_output_dir_set(self) -> None:
        req = _normalized_request()
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertIn("asset_output_dir", payload)
        self.assertTrue(payload["asset_output_dir"].endswith("assets"))

    def test_download_remote_images_enabled(self) -> None:
        req = _normalized_request()
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertTrue(payload["download_remote_images"])

    def test_none_fields_not_forwarded(self) -> None:
        req = _normalized_request()
        payload = build_draft_payload(req, _minimal_news_result())
        # angle is None by default, should not appear
        self.assertNotIn("angle", payload)

    def test_feedback_profile_dir_forwarded(self) -> None:
        fixtures = Path(__file__).resolve().parent / "fixtures" / "article-workflow-canonical" / "empty-profile"
        req = _normalized_request(feedback_profile_dir=str(fixtures))
        payload = build_draft_payload(req, _minimal_news_result())
        self.assertEqual(payload["feedback_profile_dir"], str(fixtures))


class TestBuildBriefPayload(unittest.TestCase):
    """Tests for build_brief_payload."""

    def test_source_result_included(self) -> None:
        req = _normalized_request()
        payload = build_brief_payload(req, _minimal_news_result())
        self.assertIn("source_result", payload)

    def test_topic_included(self) -> None:
        req = _normalized_request(topic="Brief topic")
        payload = build_brief_payload(req, _minimal_news_result())
        self.assertEqual(payload["topic"], "Brief topic")

    def test_analysis_time_is_string(self) -> None:
        req = _normalized_request()
        payload = build_brief_payload(req, _minimal_news_result())
        self.assertIsInstance(payload["analysis_time"], str)
        self.assertIn("2026", payload["analysis_time"])


class TestBuildRevisionTemplate(unittest.TestCase):
    """Tests for build_revision_template structure."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path.cwd() / ".tmp" / "test-revision-template"
        cls.temp_root.mkdir(parents=True, exist_ok=True)
        cls.fixtures = Path(__file__).resolve().parent / "fixtures" / "article-workflow-canonical"

    def _build_draft_result(self) -> dict:
        """Build a minimal draft result for revision template testing."""
        from article_draft_flow_runtime import build_article_draft
        source = _minimal_news_result()
        req = _normalized_request(
            output_dir=str(self.temp_root / "revision-template-draft"),
            feedback_profile_dir=str(self.fixtures / "empty-profile"),
        )
        draft_payload = build_draft_payload(req, source)
        return build_article_draft(draft_payload)

    def test_template_has_feedback_section(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("feedback", template)
        self.assertIn("summary", template["feedback"])
        self.assertIn("keep_image_asset_ids", template["feedback"])
        self.assertIn("drop_image_asset_ids", template["feedback"])

    def test_template_has_language_mode(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("language_mode", template)
        self.assertIsInstance(template["language_mode"], str)

    def test_template_has_persist_feedback(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("persist_feedback", template)
        pf = template["persist_feedback"]
        self.assertIn("scope", pf)
        self.assertIn("defaults", pf)
        self.assertEqual(pf["scope"], "none")

    def test_template_has_human_feedback_form(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("human_feedback_form", template)
        hff = template["human_feedback_form"]
        self.assertIn("overall_goal_in_plain_english", hff)
        self.assertIn("what_to_keep", hff)
        self.assertIn("what_to_change", hff)
        self.assertIn("what_to_remember_next_time", hff)

    def test_template_has_edit_reason_feedback(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("edit_reason_feedback", template)
        erf = template["edit_reason_feedback"]
        self.assertIn("summary", erf)
        self.assertIn("changes", erf)
        self.assertIn("reusable_preferences", erf)

    def test_template_has_review_focus_suggestions(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("review_focus_suggestions", template)
        rfs = template["review_focus_suggestions"]
        self.assertIn("recommended_first_checks", rfs)
        self.assertIsInstance(rfs["recommended_first_checks"], list)

    def test_template_has_review_form_quickstart(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("review_form_quickstart", template)
        self.assertIn("recommended_path", template["review_form_quickstart"])

    def test_template_has_feedback_profile_status(self) -> None:
        draft = self._build_draft_result()
        template = build_revision_template(draft)
        self.assertIn("feedback_profile_status", template)

    def test_hero_image_in_keep_list(self) -> None:
        draft = self._build_draft_result()
        article = draft.get("article_package", {})
        images = article.get("selected_images", []) or article.get("image_blocks", [])
        template = build_revision_template(draft)
        keep_ids = template["feedback"]["keep_image_asset_ids"]
        if images:
            self.assertTrue(len(keep_ids) > 0)
        else:
            self.assertEqual(keep_ids, [])


if __name__ == "__main__":
    unittest.main()
