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

    @patch("news_index_runtime.urllib.request.urlopen")
    def test_public_news_og_image_becomes_real_image_candidate_not_page_url(self, mock_urlopen) -> None:
        class FakeResponse:
            def __init__(self, html: str, final_url: str) -> None:
                self._html = html.encode("utf-8")
                self._final_url = final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self, limit: int = -1) -> bytes:
                return self._html if limit < 0 else self._html[:limit]

            def geturl(self) -> str:
                return self._final_url

        mock_urlopen.return_value = FakeResponse(
            """
                <html>
                  <head>
                    <title>Example funding story</title>
                    <meta property="og:image" content="/images/hero.png">
                    <meta property="og:image:alt" content="Funding story hero chart">
                  </head>
                  <body>
                    <p>Funding story body text.</p>
                  </body>
                </html>
            """,
            "https://example.com/story",
        )

        source_result = run_news_index(
            {
                "topic": "Funding story with OG image",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "The funding story has a reusable hero image.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "news-1",
                        "source_name": "Example News",
                        "source_type": "major_news",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:35:00+00:00",
                        "url": "https://example.com/story",
                        "summary": "Funding story summary from discovery.",
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )
        brief = build_analysis_brief({"source_result": source_result})
        draft = draft_runtime.build_article_draft(
            {
                "source_result": source_result,
                "analysis_brief": brief["analysis_brief"],
                "evidence_bundle": brief["evidence_bundle"],
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 2,
            }
        )

        image_candidates = draft["draft_context"]["image_candidates"]
        self.assertTrue(any(item["role"] == "post_media" for item in image_candidates))
        self.assertTrue(any("https://example.com/images/hero.png" == item["source_url"] for item in image_candidates))
        self.assertFalse(
            any(item["role"] == "root_post_screenshot" and item["source_url"] == "https://example.com/story" for item in image_candidates)
        )


if __name__ == "__main__":
    unittest.main()
