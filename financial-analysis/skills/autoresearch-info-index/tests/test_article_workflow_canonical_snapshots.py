#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import run_article_workflow
from news_index_core import read_json, run_news_index


class ArticleWorkflowCanonicalSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.realistic_news_request = read_json(cls.examples / "news-index-realistic-offline-request.json")
        cls.fixtures_root = Path(__file__).resolve().parent / "fixtures" / "article-workflow-canonical"
        cls.temp_root = Path.cwd() / ".tmp" / "article-workflow-canonical-snapshots"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def expected_snapshot(self, name: str) -> dict:
        return json.loads((self.fixtures_root / f"{name}.json").read_text(encoding="utf-8"))

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
                        "source_id": "reuters-1",
                        "source_name": "Reuters",
                        "source_type": "wire",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:35:00+00:00",
                        "url": "https://example.com/reuters-clear-core",
                        "text_excerpt": "Indirect talks continue through intermediaries.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    },
                    {
                        "source_id": "official-1",
                        "source_name": "Oman Foreign Ministry",
                        "source_type": "government_release",
                        "published_at": "2026-03-24T11:20:00+00:00",
                        "observed_at": "2026-03-24T11:25:00+00:00",
                        "url": "https://example.com/oman-clear-core",
                        "text_excerpt": "Officials said indirect contacts continue through mediators.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                    },
                ],
            }
        )

    @staticmethod
    def workflow_snapshot(result: dict) -> dict:
        draft_result = read_json(Path(result["draft_stage"]["result_path"]))
        article = draft_result["article_package"]
        style_applied = article.get("style_profile_applied", {})
        effective_request = style_applied.get("effective_request", {})
        style_memory = effective_request.get("style_memory") or {}
        feedback_status = article.get("feedback_profile_status") or {}
        manual_review = result.get("manual_review", {})
        workflow_publication_gate = result.get("workflow_publication_gate") or {}
        workflow_manual_review = workflow_publication_gate.get("manual_review") or {}
        return {
            "source_kind": result["source_stage"]["source_kind"],
            "quality_gate": result["final_stage"]["quality_gate"],
            "rewrite_mode": result["final_stage"]["rewrite_mode"],
            "pre_rewrite_quality_gate": result["final_stage"]["pre_rewrite_quality_gate"],
            "publication_readiness": result.get("publication_readiness"),
            "workflow_publication_gate": {
                "publication_readiness": workflow_publication_gate.get("publication_readiness"),
                "manual_review_status": workflow_manual_review.get("status"),
            },
            "manual_review": {
                "status": manual_review.get("status"),
                "required": manual_review.get("required"),
                "required_count": manual_review.get("required_count"),
                "high_priority_count": manual_review.get("high_priority_count"),
            },
            "draft_metrics": article.get("draft_metrics", {}),
            "title": article.get("title"),
            "subtitle": article.get("subtitle"),
            "lede": article.get("lede"),
            "section_headings": [item.get("heading") for item in article.get("sections", [])],
            "section_paragraphs": [item.get("paragraph") for item in article.get("sections", [])],
            "selected_images": [
                {
                    "image_id": item.get("image_id") or item.get("asset_id"),
                    "role": item.get("role"),
                    "source_name": item.get("source_name"),
                    "placement": item.get("placement"),
                    "status": item.get("status"),
                }
                for item in article.get("selected_images", [])
            ],
            "style_effective_request": {
                "language_mode": effective_request.get("language_mode"),
                "draft_mode": effective_request.get("draft_mode"),
                "image_strategy": effective_request.get("image_strategy"),
                "target_length_chars": effective_request.get("target_length_chars"),
                "human_signal_ratio": effective_request.get("human_signal_ratio"),
                "headline_hook_mode": effective_request.get("headline_hook_mode"),
                "personal_phrase_bank": effective_request.get("personal_phrase_bank"),
                "style_memory": {
                    "target_band": style_memory.get("target_band"),
                    "preferred_transitions": style_memory.get("preferred_transitions"),
                    "slot_lines": style_memory.get("slot_lines"),
                },
            },
            "feedback_profile_status": {
                "global_exists": feedback_status.get("global_exists"),
                "topic_exists": feedback_status.get("topic_exists"),
                "global_history_count": feedback_status.get("global_history_count"),
                "topic_history_count": feedback_status.get("topic_history_count"),
                "global_style_memory_keys": feedback_status.get("global_style_memory_keys"),
                "topic_style_memory_keys": feedback_status.get("topic_style_memory_keys"),
                "applied_paths_count": len(feedback_status.get("applied_paths", [])),
            },
        }

    @staticmethod
    def workflow_surface_snapshot(result: dict) -> dict:
        report_lines = [
            line.strip()
            for line in result.get("report_markdown", "").splitlines()
            if line.startswith("- Decision:")
            or line.startswith("- Reason:")
            or line.startswith("- High-confidence")
            or line.startswith("- Medium-confidence")
            or line.startswith("- Low-confidence")
            or line.startswith("- Human change reasons used:")
            or line.startswith("- Human reusable preferences used:")
            or line.startswith("- Human feedback path used:")
            or line.startswith("- Learning summary:")
            or line.startswith("- Excluded signal:")
            or line.startswith("- Proposed default:")
        ]
        return {
            "learning_stage": result.get("learning_stage"),
            "review_stage": {
                "attack_count": result["review_stage"].get("attack_count"),
                "claims_softened_count": result["review_stage"].get("claims_softened_count"),
                "learning_decision": result["review_stage"].get("learning_decision"),
                "learning_reason": result["review_stage"].get("learning_reason"),
                "learning_change_summary_preview": result["review_stage"].get("learning_change_summary_preview"),
                "learning_proposed_default_keys": result["review_stage"].get("learning_proposed_default_keys"),
            },
            "report_learning_lines": report_lines,
        }

    def assert_workflow_matches_snapshot(self, name: str, request: dict) -> None:
        result = run_article_workflow(request)
        actual = self.workflow_snapshot(result)
        expected = self.expected_snapshot(name)
        self.maxDiff = None
        self.assertEqual(actual, expected)

    def assert_workflow_surface_matches_snapshot(self, name: str, request: dict) -> None:
        result = run_article_workflow(request)
        actual = self.workflow_surface_snapshot(result)
        expected = self.expected_snapshot(name)
        self.maxDiff = None
        self.assertEqual(actual, expected)

    def test_realistic_offline_request_matches_canonical_snapshot(self) -> None:
        case_dir = self.case_dir("realistic-offline")
        self.assert_workflow_matches_snapshot(
            "realistic_offline_empty_profile",
            {
                **self.realistic_news_request,
                "output_dir": str(case_dir / "out"),
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 3,
                "feedback_profile_dir": str(self.fixtures_root / "empty-profile"),
            },
        )

    def test_style_profile_request_matches_canonical_snapshot(self) -> None:
        case_dir = self.case_dir("style-profile-english")
        self.assert_workflow_matches_snapshot(
            "style_profile_english",
            {
                "source_result": self.build_clean_core_news_result(),
                "output_dir": str(case_dir / "out"),
                "feedback_profile_dir": str(self.fixtures_root / "feedback-profile-english"),
            },
        )

    def test_realistic_offline_request_keeps_learning_surface_snapshot(self) -> None:
        case_dir = self.case_dir("realistic-offline-learning-surface")
        self.assert_workflow_surface_matches_snapshot(
            "realistic_offline_empty_profile_learning_surface",
            {
                **self.realistic_news_request,
                "output_dir": str(case_dir / "out"),
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 3,
                "feedback_profile_dir": str(self.fixtures_root / "empty-profile"),
            },
        )

    def test_style_profile_request_keeps_learning_surface_snapshot(self) -> None:
        case_dir = self.case_dir("style-profile-english-learning-surface")
        self.assert_workflow_surface_matches_snapshot(
            "style_profile_english_learning_surface",
            {
                "source_result": self.build_clean_core_news_result(),
                "output_dir": str(case_dir / "out"),
                "feedback_profile_dir": str(self.fixtures_root / "feedback-profile-english"),
            },
        )


if __name__ == "__main__":
    unittest.main()
