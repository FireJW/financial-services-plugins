#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import article_draft_flow_runtime as draft_runtime
import article_workflow_runtime as workflow_runtime
from article_brief_runtime import build_analysis_brief
from article_draft_flow_runtime import build_article_draft as real_build_article_draft
from news_index_core import read_json, run_news_index


class ArticleEvidenceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.news_request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.realistic_news_request = read_json(cls.examples / "news-index-realistic-offline-request.json")
        cls.temp_root = Path.cwd() / ".tmp" / "article-evidence-bundle-tests"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def test_article_brief_exposes_shared_evidence_bundle(self) -> None:
        brief = build_analysis_brief({"source_result": run_news_index(self.news_request)})
        bundle = brief["evidence_bundle"]
        self.assertEqual(bundle["contract_version"], "article_evidence_bundle_v1")
        self.assertIn("source_summary", bundle)
        self.assertIn("evidence_digest", bundle)
        self.assertIn("citations", bundle)
        self.assertIn("image_candidates", bundle)
        self.assertIn("observations", bundle)
        self.assertIn("claim_ledger", bundle)
        self.assertEqual(brief["supporting_citations"], bundle["citations"])
        self.assertEqual(bundle["source_summary"]["topic"], brief["source_summary"]["topic"])

    def test_article_workflow_passes_evidence_bundle_to_draft_stage(self) -> None:
        captured_payload: dict[str, object] = {}

        def spy_build_article_draft(payload: dict[str, object]) -> dict[str, object]:
            captured_payload["payload"] = payload
            return real_build_article_draft(payload)

        output_dir = self.temp_root / "workflow-pass-through"
        output_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(workflow_runtime, "build_article_draft", side_effect=spy_build_article_draft):
            result = workflow_runtime.run_article_workflow(
                {
                    **self.realistic_news_request,
                    "output_dir": str(output_dir),
                    "draft_mode": "image_first",
                    "image_strategy": "prefer_images",
                    "max_images": 2,
                }
            )

        payload = captured_payload["payload"]
        self.assertIn("evidence_bundle", payload)
        bundle = payload["evidence_bundle"]
        self.assertEqual(bundle["contract_version"], "article_evidence_bundle_v1")
        self.assertTrue(bundle["citations"])
        self.assertIn("image_candidates", bundle)
        self.assertEqual(result["brief_stage"]["evidence_bundle_contract"], "article_evidence_bundle_v1")
        self.assertEqual(result["brief_stage"]["evidence_bundle_citation_count"], len(bundle["citations"]))

    def test_article_draft_reuses_passed_evidence_bundle(self) -> None:
        source_result = run_news_index(self.news_request)
        brief = build_analysis_brief({"source_result": source_result})
        bundle = brief["evidence_bundle"]

        with patch.object(draft_runtime, "build_shared_evidence_bundle", side_effect=AssertionError("bundle should be reused")):
            draft = draft_runtime.build_article_draft(
                {
                    "source_result": source_result,
                    "analysis_brief": brief["analysis_brief"],
                    "evidence_bundle": bundle,
                    "draft_mode": "image_first",
                    "image_strategy": "prefer_images",
                    "max_images": 2,
                }
            )

        self.assertEqual(draft["evidence_bundle"]["contract_version"], "article_evidence_bundle_v1")
        self.assertEqual(
            draft["draft_context"]["citation_candidates"],
            bundle["citations"],
        )
        self.assertEqual(
            draft["draft_context"]["image_candidates"],
            bundle["image_candidates"],
        )


if __name__ == "__main__":
    unittest.main()
