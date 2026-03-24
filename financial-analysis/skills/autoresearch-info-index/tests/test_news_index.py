#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from news_index_core import build_markdown_report, read_json, refresh_news_index, result_to_run_record, run_news_index
from evaluate_info_index import build_result
from x_index_runtime import run_x_index


class NewsIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.refresh = read_json(cls.examples / "news-index-refresh-update.json")

    def test_crisis_request_builds_dual_track_result(self) -> None:
        result = run_news_index(self.request)
        self.assertEqual(result["retrieval_request"]["mode"], "crisis")
        self.assertIn("US and Iran are in active indirect contacts today.", result["verdict_output"]["confirmed"])
        self.assertIn("A US amphibious group could reach a relevant public watch position within roughly one to two days.", result["verdict_output"]["not_confirmed"])
        self.assertTrue(result["verdict_output"]["latest_signals"][0]["rank_score"] >= result["verdict_output"]["latest_signals"][-1]["rank_score"])
        self.assertIn("crisis_mode", result)

    def test_refresh_adds_new_evidence_without_dropping_prior_context(self) -> None:
        first = run_news_index(self.request)
        refreshed = refresh_news_index(first, self.refresh)
        latest_sources = [item["source_name"] for item in refreshed["verdict_output"]["latest_signals"]]
        self.assertIn("AP", latest_sources)
        self.assertGreaterEqual(len(refreshed["source_observations"]), len(first["source_observations"]))
        self.assertEqual(refreshed["refresh_context"]["mode"], "refresh")

    def test_bridge_run_record_includes_retrieval_quality(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        self.assertIn("retrieval_result", run_record)
        self.assertIn("retrieval_quality", run_record["retrieval_result"])
        self.assertTrue(run_record["hard_checks"]["key_claims_traceable"])

    def test_run_record_preserves_precise_source_timestamps(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        first_source = run_record["source_pack"]["sources"][0]
        self.assertIn("source_id", first_source)
        self.assertIn("T", first_source["published_at"])

    def test_phase1_evaluation_keeps_gap_visibility_and_true_timeliness(self) -> None:
        result = run_news_index(self.request)
        evaluated = build_result(result_to_run_record(result))
        self.assertGreater(evaluated["credibility_metrics"]["timeliness_score"], 80)
        blocked_sources = [item["source_name"] for item in evaluated["retrieval_observability"]["blocked_sources"]]
        self.assertIn("Axios", blocked_sources)
        self.assertIn("public_ais", evaluated["retrieval_observability"]["missing_expected_source_families"])

    def test_fallback_retrieval_quality_does_not_penalize_clean_no_blocked_case(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        fallback_record = deepcopy(run_record)
        fallback_record["retrieval_result"].pop("retrieval_quality", None)
        fallback_record["retrieval_result"]["retrieval_run_report"]["sources_blocked"] = []
        for observation in fallback_record["retrieval_result"]["observations"]:
            observation["access_mode"] = "public"
        evaluated = build_result(fallback_record)
        self.assertEqual(evaluated["retrieval_quality_metrics"]["blocked_source_handling_score"], 100)

    def test_markdown_mentions_last_public_indication_sections(self) -> None:
        result = run_news_index(self.request)
        report = build_markdown_report(result)
        self.assertIn("Latest Signals First", report)
        self.assertIn("Vessel Movement Table", report)
        self.assertIn("Escalation Scenarios", report)
        self.assertIn("Last Public Indication", report)

    def test_x_index_prefers_direct_post_text_and_keeps_thread_and_media_fields(self) -> None:
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
                            <meta property=\"og:title\" content=\"SentDefender on X\">
                            <meta property=\"og:description\" content=\"A significant movement is underway from US Army, Navy and Air Force bases in CONUS to the Middle East comprised of at least 35 C-17 flights since March 12th.\">
                            <meta property=\"og:image\" content=\"https://pbs.twimg.com/media/test-airlift.jpg\">
                          </head>
                          <body>
                            <time datetime=\"2026-03-24T09:30:00+00:00\"></time>
                          </body>
                        </html>
                    """,
                    "root_post_screenshot_path": "C:\\artifacts\\sentdefender-root.png",
                    "thread_posts": [
                        {
                            "post_url": "https://x.com/sentdefender/status/2036153038906196134",
                            "posted_at": "2026-03-24T09:35:00+00:00",
                            "post_text_raw": "Origins include Hunter Army Air Field and JB Lewis-McChord.",
                            "post_text_source": "dom",
                        }
                    ],
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "ocr_text_raw": "Origins: 12 Hunter Army Air Field, 7 JBLM. Destinations: 17 Ovda Air Base, 13 King Faisal Air Base.",
                        }
                    ],
                    "engagement": {"views": 1500000, "likes": 32000, "reposts": 11000, "replies": 4200},
                }
            ],
        }

        result = run_x_index(request)
        post = result["x_posts"][0]
        self.assertEqual(post["post_text_source"], "dom")
        self.assertIn("35 C-17 flights", post["post_text_raw"])
        self.assertIn("Hunter Army Air Field", post["post_summary"])
        self.assertIn("Ovda Air Base", post["media_summary"])
        self.assertEqual(post["root_post_screenshot_path"], "C:\\artifacts\\sentdefender-root.png")
        retrieval_observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(retrieval_observation["post_text_raw"], post["post_text_raw"])
        self.assertIn("Source Artifacts", result["retrieval_result"]["report_markdown"])

    def test_x_index_uses_ocr_fallback_when_direct_text_is_unavailable(self) -> None:
        request = {
            "topic": "Fallback capture",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "seed_posts": [
                {
                    "post_url": "https://x.com/example/status/1",
                    "html": "<html><body></body></html>",
                    "visible_text": "",
                    "accessibility_text": "",
                    "ocr_root_text": "Fallback text copied from the screenshot says 36 flights.",
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/fallback.jpg",
                            "ocr_text_raw": "Chart says 48 flights.",
                        }
                    ],
                }
            ],
        }

        result = run_x_index(request)
        post = result["x_posts"][0]
        self.assertEqual(post["post_text_source"], "ocr_fallback")
        self.assertIn("Fallback text copied", post["post_text_raw"])
        self.assertIn("Conflict note", post["combined_summary"])

    def test_x_index_bridge_preserves_artifact_fields_in_run_record(self) -> None:
        request = {
            "topic": "Bridge preservation",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "seed_posts": [
                {
                    "post_url": "https://x.com/example/status/2",
                    "html": """
                        <html>
                          <head>
                            <meta property=\"og:title\" content=\"Example on X\">
                            <meta property=\"og:description\" content=\"Direct text from the main post.\">
                          </head>
                        </html>
                    """,
                    "root_post_screenshot_path": "C:\\artifacts\\example-root.png",
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/example.jpg",
                            "ocr_text_raw": "Image text for downstream citation.",
                        }
                    ],
                }
            ],
        }

        result = run_x_index(request)
        run_record = result_to_run_record(result["retrieval_result"])
        first_source = run_record["source_pack"]["sources"][0]
        self.assertEqual(first_source["root_post_screenshot_path"], "C:\\artifacts\\example-root.png")
        self.assertTrue(first_source["artifact_manifest"])
        self.assertIn("Image text", first_source["media_summary"])

    def test_load_json_accepts_windows_bom(self) -> None:
        bom_path = self.examples / "tmp-bom-request.json"
        bom_path.write_text('{"topic":"bom"}', encoding="utf-8-sig")
        try:
            payload = read_json(bom_path)
            self.assertEqual(payload["topic"], "bom")
        finally:
            if bom_path.exists():
                bom_path.unlink()


if __name__ == "__main__":
    unittest.main()
