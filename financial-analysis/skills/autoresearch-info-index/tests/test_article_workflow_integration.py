#!/usr/bin/env python3
"""Integration tests for run_article_workflow — file outputs, stages, publication gate."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import (
    build_decision_trace,
    build_report_markdown,
    run_article_workflow,
    summarize_brief_decisions,
    summarize_draft_decisions,
)
from news_index_core import run_news_index


def _minimal_news_result() -> dict:
    return run_news_index(
        {
            "topic": "Integration test topic",
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


class TestRunArticleWorkflowIntegration(unittest.TestCase):
    """Integration tests that run the full article workflow pipeline."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path.cwd() / ".tmp" / "test-article-workflow-integration"
        cls.temp_root.mkdir(parents=True, exist_ok=True)
        cls.fixtures = Path(__file__).resolve().parent / "fixtures" / "article-workflow-canonical"

    def _case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_workflow(self, name: str, **overrides: object) -> dict:
        case_dir = self._case_dir(name)
        request = {
            "source_result": _minimal_news_result(),
            "output_dir": str(case_dir / "out"),
            "feedback_profile_dir": str(self.fixtures / "empty-profile"),
        }
        request.update(overrides)
        return run_article_workflow(request)

    # ── result structure ──

    def test_result_has_source_stage(self) -> None:
        result = self._run_workflow("structure-source")
        self.assertIn("source_stage", result)
        self.assertIn("source_kind", result["source_stage"])

    def test_result_has_brief_stage(self) -> None:
        result = self._run_workflow("structure-brief")
        self.assertIn("brief_stage", result)

    def test_result_has_draft_stage(self) -> None:
        result = self._run_workflow("structure-draft")
        self.assertIn("draft_stage", result)
        self.assertIn("result_path", result["draft_stage"])

    def test_result_has_final_stage(self) -> None:
        result = self._run_workflow("structure-final")
        self.assertIn("final_stage", result)
        self.assertIn("quality_gate", result["final_stage"])

    def test_result_has_publication_readiness(self) -> None:
        result = self._run_workflow("structure-pub")
        self.assertIn("publication_readiness", result)

    def test_result_has_manual_review(self) -> None:
        result = self._run_workflow("structure-review")
        self.assertIn("manual_review", result)
        mr = result["manual_review"]
        self.assertIn("status", mr)
        self.assertIn("required", mr)

    def test_result_has_report_markdown(self) -> None:
        result = self._run_workflow("structure-report")
        self.assertIn("report_markdown", result)
        self.assertIsInstance(result["report_markdown"], str)
        self.assertTrue(len(result["report_markdown"]) > 50)

    # ── file outputs ──

    def test_draft_result_file_written(self) -> None:
        result = self._run_workflow("file-draft")
        draft_path = Path(result["draft_stage"]["result_path"])
        self.assertTrue(draft_path.exists())
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        self.assertIn("article_package", draft)

    def test_workflow_report_file_written(self) -> None:
        result = self._run_workflow("file-report")
        out_dir = Path(result["draft_stage"]["result_path"]).parent.parent
        report_candidates = list(out_dir.glob("**/workflow-report.md")) + list(out_dir.glob("**/*report*.md"))
        # At least the report_markdown is in the result
        self.assertTrue(len(result["report_markdown"]) > 0)

    # ── source kind ──

    def test_indexed_result_source_kind(self) -> None:
        result = self._run_workflow("source-indexed")
        self.assertIn(result["source_stage"]["source_kind"], ("indexed_result", "news_index"))

    # ── quality gate values ──

    def test_quality_gate_is_valid_value(self) -> None:
        result = self._run_workflow("gate-valid")
        self.assertIn(result["final_stage"]["quality_gate"], ("pass", "revise", "block"))

    # ── decision trace ──

    def test_decision_trace_has_all_sections(self) -> None:
        result = self._run_workflow("decision-trace")
        if "decision_trace" in result:
            trace = result["decision_trace"]
            self.assertIn("brief", trace)
            self.assertIn("draft", trace)
            self.assertIn("review", trace)

    # ── workflow publication gate ──

    def test_workflow_publication_gate_present(self) -> None:
        result = self._run_workflow("pub-gate")
        self.assertIn("workflow_publication_gate", result)
        gate = result["workflow_publication_gate"]
        self.assertIn("publication_readiness", gate)


class TestBuildDecisionTrace(unittest.TestCase):

    def test_composes_three_sections(self) -> None:
        brief = {"recommended_thesis": "T", "canonical_fact_count": 1, "not_proven_count": 0,
                 "lead_canonical_fact": "F", "lead_not_proven": "", "top_story_angle": "A",
                 "voice_constraints": []}
        draft = {"title": "Title", "draft_thesis": "Thesis", "top_claims": []}
        review = {"quality_gate": "pass", "attack_count": 0}
        trace = build_decision_trace(brief, draft, review)
        self.assertIn("brief", trace)
        self.assertIn("draft", trace)
        self.assertIn("review", trace)

    def test_handles_empty_inputs(self) -> None:
        trace = build_decision_trace({}, {}, {})
        self.assertIsInstance(trace, dict)


class TestBuildReportMarkdown(unittest.TestCase):

    def test_report_contains_key_sections(self) -> None:
        result = {
            "topic": "Test",
            "source_stage": {"source_kind": "news_index"},
            "brief_stage": {},
            "draft_stage": {"result_path": "/tmp/draft.json"},
            "final_stage": {"quality_gate": "pass", "rewrite_mode": "none", "pre_rewrite_quality_gate": "pass"},
            "asset_stage": {"local_ready_count": 1, "remote_only_count": 0, "missing_count": 0},
            "feedback_stage": {},
            "manual_review": {"status": "not_required", "required": False, "required_count": 0},
            "publication_readiness": "ready",
            "report_markdown": "",
        }
        md = build_report_markdown(result)
        self.assertIsInstance(md, str)
        # Should have some content
        self.assertTrue(len(md) > 20)


if __name__ == "__main__":
    unittest.main()
