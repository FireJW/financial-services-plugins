#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hot_topic_discovery_runtime import run_hot_topic_discovery
from news_index_runtime import run_news_index


class TrendRadarIntegrationTests(unittest.TestCase):
    def test_news_index_imports_trendradar_block_directly(self) -> None:
        result = run_news_index(
            {
                "topic": "TrendRadar direct import",
                "analysis_time": "2026-05-01T08:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "trendradar-signal-usable",
                        "claim_text": "TrendRadar produced a usable shadow signal.",
                    }
                ],
                "trendradar": {
                    "result": {
                        "success": True,
                        "data": {
                            "items": [
                                {
                                    "title": "AI data center power equipment demand rises",
                                    "summary": "Multiple hot lists mention power equipment for AI data centers.",
                                    "url": "https://example.com/ai-power",
                                    "platform": "weibo",
                                    "rank": 3,
                                    "heat": 987654,
                                    "published_at": "2026-05-01T07:30:00+00:00",
                                }
                            ]
                        },
                    }
                },
            }
        )

        self.assertEqual(len(result["observations"]), 1)
        observation = result["observations"][0]
        self.assertEqual(observation["origin"], "trendradar")
        self.assertEqual(observation["source_name"], "trendradar:weibo")
        self.assertEqual(observation["source_type"], "social")
        self.assertEqual(observation["access_mode"], "local_mcp")
        self.assertIn("AI data center power equipment demand rises", observation["text_excerpt"])

    def test_hot_topics_can_pull_trendradar_as_an_explicit_source(self) -> None:
        result = run_hot_topic_discovery(
            {
                "topic": "AI infrastructure heat",
                "query": "AI infrastructure",
                "analysis_time": "2026-05-01T08:00:00+00:00",
                "sources": ["trendradar"],
                "trendradar": {
                    "result": {
                        "success": True,
                        "data": {
                            "items": [
                                {
                                    "title": "AI data center power equipment demand rises",
                                    "summary": "Multiple hot lists mention power equipment for AI data centers.",
                                    "url": "https://example.com/ai-power",
                                    "platform": "weibo",
                                    "rank": 3,
                                    "heat": 987654,
                                    "published_at": "2026-05-01T07:30:00+00:00",
                                }
                            ]
                        },
                    }
                },
            }
        )

        self.assertEqual(result["sources_attempted"], ["trendradar"])
        self.assertEqual(len(result["ranked_topics"]), 1)
        topic = result["ranked_topics"][0]
        self.assertEqual(topic["source_count"], 1)
        self.assertEqual(topic["source_items"][0]["source_name"], "trendradar:weibo")
        self.assertIn("AI data center power equipment demand rises", topic["source_items"][0]["title"])


if __name__ == "__main__":
    unittest.main()
