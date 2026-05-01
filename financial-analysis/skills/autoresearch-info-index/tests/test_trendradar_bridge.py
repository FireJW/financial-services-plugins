#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trendradar_bridge_runtime import prepare_trendradar_bridge, run_trendradar_bridge


class TrendRadarBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-trendradar-bridge"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bridge_imports_mcp_news_items_as_shadow_candidates(self) -> None:
        result = run_trendradar_bridge(
            {
                "topic": "AI infrastructure trend check",
                "analysis_time": "2026-05-01T08:00:00+08:00",
                "questions": ["Which AI infrastructure topic is rising across Chinese platforms?"],
                "claims": [
                    {
                        "claim_id": "ai-infra-rising",
                        "claim_text": "AI infrastructure demand is rising in public discussion today.",
                    }
                ],
                "trendradar": {
                    "result": {
                        "success": True,
                        "summary": "2 matching news items",
                        "data": {
                            "items": [
                                {
                                    "title": "AI data center power equipment demand rises",
                                    "summary": "Multiple hot lists mention power equipment for AI data centers.",
                                    "url": "https://example.com/ai-power",
                                    "platform": "weibo",
                                    "rank": 3,
                                    "heat": 987654,
                                    "published_at": "2026-05-01T07:30:00+08:00",
                                    "keyword": "AI data center",
                                },
                                {
                                    "title": "Optical module orders discussed by investors",
                                    "description": "Investor channels are watching optical module demand.",
                                    "link": "https://example.com/optical",
                                    "source": "rss:tech-media",
                                    "score": 82,
                                    "collected_at": "2026-05-01T07:45:00+08:00",
                                },
                            ]
                        },
                    },
                },
            }
        )

        observations = result["retrieval_result"]["observations"]
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 2)
        self.assertEqual(result["import_summary"]["payload_source"], "inline_result")
        self.assertEqual(result["import_summary"]["platform_counts"], {"weibo": 1, "rss:tech-media": 1})

        weibo = next(item for item in observations if item["url"] == "https://example.com/ai-power")
        rss = next(item for item in observations if item["url"] == "https://example.com/optical")

        self.assertEqual(weibo["origin"], "trendradar")
        self.assertEqual(weibo["source_name"], "trendradar:weibo")
        self.assertEqual(weibo["source_type"], "social")
        self.assertEqual(weibo["channel"], "shadow")
        self.assertEqual(weibo["access_mode"], "local_mcp")
        self.assertIn("AI data center power equipment demand rises", weibo["text_excerpt"])
        self.assertEqual(weibo["raw_metadata"]["trendradar"]["rank"], 3)
        self.assertEqual(weibo["raw_metadata"]["trendradar"]["heat"], 987654)
        self.assertEqual(weibo["claim_states"], {"ai-infra-rising": "support"})

        self.assertEqual(rss["source_name"], "trendradar:rss:tech-media")
        self.assertEqual(rss["source_type"], "news")
        self.assertEqual(rss["published_at"], "2026-04-30T23:45:00+00:00")
        self.assertEqual(
            rss["raw_metadata"]["trendradar"]["timestamp_fallback"],
            "observed_at",
        )

    def test_prepare_bridge_loads_result_path_dedupes_and_preserves_payload_metadata(self) -> None:
        result_path = self.temp_dir / "trendradar-output.json"
        result_path.write_text(
            """{
              "success": true,
              "summary": "duplicate hotlist rows",
              "data": [
                {
                  "title": "Commercial aerospace topic enters hot list",
                  "url": "https://example.com/aerospace",
                  "platform": "zhihu",
                  "rank": 7,
                  "last_seen": "2026-05-01T07:50:00+08:00"
                },
                {
                  "title": "Commercial aerospace topic enters hot list",
                  "url": "https://example.com/aerospace",
                  "platform": "zhihu",
                  "rank": 12,
                  "last_seen": "2026-05-01T07:55:00+08:00"
                }
              ]
            }""",
            encoding="utf-8",
        )

        result = prepare_trendradar_bridge(
            {
                "topic": "Commercial aerospace heat check",
                "analysis_time": "2026-05-01T08:00:00+08:00",
                "trendradar": {
                    "result_path": str(result_path),
                },
            }
        )

        candidates = result["retrieval_request"]["candidates"]
        self.assertEqual(result["import_summary"]["payload_source"], "result_path")
        self.assertEqual(result["import_summary"]["raw_item_count"], 2)
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(result["import_summary"]["skipped_duplicate_count"], 1)
        self.assertEqual(candidates[0]["raw_metadata"]["trendradar"]["mcp_success"], True)
        self.assertEqual(candidates[0]["raw_metadata"]["trendradar"]["mcp_summary"], "duplicate hotlist rows")
        self.assertIn(str(result_path.resolve()), result["report_markdown"])


if __name__ == "__main__":
    unittest.main()
