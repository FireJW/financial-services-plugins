#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
    / "weekend_market_candidate_runtime.py"
)
SPEC = importlib.util.spec_from_file_location("weekend_market_candidate_runtime", MODULE_PATH)
module_under_test = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module_under_test)


class WeekendMarketCandidateRuntimeTests(unittest.TestCase):
    def test_normalize_weekend_market_candidate_input_keeps_live_x_seed_expansion_and_reddit_rows(self) -> None:
        normalized = module_under_test.normalize_weekend_market_candidate_input(
            {
                "x_seed_inputs": [
                    {"handle": "tuolaji2024", "tags": ["optical"], "ignored": "drop-me"}
                ],
                "x_expansion_inputs": [
                    {"handle": "aleabitoreddit", "theme_overlap": ["optical_interconnect"]}
                ],
                "reddit_inputs": [
                    {"subreddit": "wallstreetbets", "thread_summary": "Optics supply chain still hot"}
                ],
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/LinQingV/status/1",
                                "author_handle": "LinQingV",
                                "combined_summary": "商业航天和卫星互联网讨论升温。",
                            }
                        ]
                    }
                ],
                "x_live_index_result_paths": [
                    "D:\\Users\\rickylu\\dev\\financial-services-plugins-clean\\.tmp\\weekend-market-candidate-actual\\result.x-index.linqingv.live.json"
                ],
            }
        )

        self.assertEqual(normalized["x_seed_inputs"][0]["handle"], "tuolaji2024")
        self.assertNotIn("ignored", normalized["x_seed_inputs"][0])
        self.assertEqual(normalized["x_expansion_inputs"][0]["handle"], "aleabitoreddit")
        self.assertEqual(normalized["reddit_inputs"][0]["subreddit"], "wallstreetbets")
        self.assertEqual(normalized["x_live_index_results"][0]["x_posts"][0]["author_handle"], "LinQingV")
        self.assertEqual(
            normalized["x_live_index_result_paths"][0],
            "D:\\Users\\rickylu\\dev\\financial-services-plugins-clean\\.tmp\\weekend-market-candidate-actual\\result.x-index.linqingv.live.json",
        )

    def test_build_weekend_market_candidate_infers_commercial_space_from_live_x_results(self) -> None:
        candidate, reference_map = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/live_seed/status/1",
                                "author_handle": "live_seed",
                                "author_display_name": "Live Seed",
                                "combined_summary": "商业航天和卫星互联网继续发酵，SpaceX 与 Starlink 带动卫星链讨论。",
                            }
                        ]
                    }
                ]
            }
        )

        self.assertEqual(candidate["status"], "candidate_only")
        topic_names = [item["topic_name"] for item in candidate["candidate_topics"]]
        self.assertIn("commercial_space", topic_names)
        self.assertIn("satellite_chain", topic_names)
        commercial_topic = next(item for item in candidate["candidate_topics"] if item["topic_name"] == "commercial_space")
        self.assertEqual(commercial_topic["key_sources"][0]["source_kind"], "x_live_index")
        self.assertEqual(reference_map[0]["direction_key"], candidate["candidate_topics"][0]["topic_name"])

    def test_build_weekend_market_candidate_prefers_seed_consensus_and_returns_reference_map(self) -> None:
        candidate, reference_map = module_under_test.build_weekend_market_candidate(
            {
                "x_seed_inputs": [
                    {
                        "handle": "seed_one",
                        "url": "https://x.com/seed_one",
                        "display_name": "seed_one",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                        "quality_hint": "preferred_seed",
                    },
                    {
                        "handle": "seed_two",
                        "url": "https://x.com/seed_two",
                        "display_name": "seed_two",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "仕佳光子"],
                        "quality_hint": "preferred_seed",
                    },
                ],
                "x_expansion_inputs": [
                    {
                        "handle": "expansion_one",
                        "url": "https://x.com/expansion_one/status/1",
                        "why_included": "Confirmed the same theme",
                        "theme_overlap": ["optical_interconnect"],
                        "candidate_names": ["太辰光", "仕佳光子"],
                        "quality_hint": "theme_confirmation",
                    }
                ],
                "reddit_inputs": [
                    {
                        "subreddit": "stocks",
                        "thread_url": "https://reddit.com/example",
                        "thread_summary": "AI networking demand still supports optics",
                        "theme_tags": ["optical_interconnect"],
                        "direction_hint": "confirming",
                        "quality_hint": "high_activity",
                    }
                ],
            }
        )

        topic = candidate["candidate_topics"][0]
        self.assertEqual(candidate["status"], "candidate_only")
        self.assertEqual(topic["topic_name"], "optical_interconnect")
        self.assertEqual(topic["priority_rank"], 1)
        self.assertEqual(topic["ranking_logic"]["seed_alignment"], "high")
        self.assertEqual(topic["ranking_logic"]["expansion_confirmation"], "high")
        self.assertEqual(topic["ranking_logic"]["reddit_confirmation"], "high")
        self.assertEqual(topic["ranking_logic"]["noise_or_disagreement"], "low")
        self.assertIn("ranking_reason", topic)
        self.assertGreaterEqual(len(topic["key_sources"]), 2)
        self.assertIn("source_name", topic["key_sources"][0])
        self.assertIn("source_kind", topic["key_sources"][0])
        self.assertIn("url", topic["key_sources"][0])
        self.assertIn("summary", topic["key_sources"][0])
        self.assertEqual(reference_map[0]["direction_key"], "optical_interconnect")
        self.assertEqual(reference_map[0]["leaders"][0]["name"], "中际旭创")
        self.assertEqual(reference_map[0]["high_beta_names"][0]["name"], "太辰光")

    def test_build_weekend_market_candidate_emits_top_three_topics_from_live_evidence_and_paths(self) -> None:
        live_result = {
            "x_posts": [
                {
                    "post_url": "https://x.com/optics/status/1",
                    "author_handle": "optics",
                    "combined_summary": "光通信和光互联周末继续发酵，光模块与硅光子仍是主线。",
                },
                {
                    "post_url": "https://x.com/shipping/status/1",
                    "author_handle": "shipping",
                    "combined_summary": "Hormuz blocked again, oil shipping and tanker rates remain the focus.",
                },
                {
                    "post_url": "https://x.com/space/status/1",
                    "author_handle": "space",
                    "combined_summary": "商业航天、卫星互联网和火箭发射链条讨论明显升温。",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = pathlib.Path(temp_dir) / "live-x.json"
            payload_path.write_text(json.dumps(live_result, ensure_ascii=False), encoding="utf-8")

            candidate, reference_map = module_under_test.build_weekend_market_candidate(
                {
                    "x_seed_inputs": [
                        {
                            "handle": "seed_one",
                            "display_name": "seed_one",
                            "url": "https://x.com/seed_one",
                            "tags": ["optical_interconnect"],
                            "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                        }
                    ],
                    "reddit_inputs": [
                        {
                            "subreddit": "stocks",
                            "thread_url": "https://reddit.com/example",
                            "thread_summary": "Hormuz risk keeps shipping discussion active",
                            "theme_tags": ["oil_shipping"],
                        }
                    ],
                    "x_live_index_result_paths": [str(payload_path)],
                }
            )

        topic_names = [item["topic_name"] for item in candidate["candidate_topics"]]
        self.assertLessEqual(len(topic_names), 3)
        self.assertEqual(topic_names, ["optical_interconnect", "oil_shipping", "commercial_space"])
        self.assertEqual([item["priority_rank"] for item in candidate["candidate_topics"]], [1, 2, 3])
        self.assertEqual(reference_map[0]["direction_key"], "optical_interconnect")
        self.assertEqual(reference_map[1]["direction_key"], "oil_shipping")
        self.assertEqual(reference_map[2]["direction_key"], "commercial_space")
        oil_topic = candidate["candidate_topics"][1]
        self.assertTrue(any(row["source_kind"] == "x_live_index" for row in oil_topic["key_sources"]))


if __name__ == "__main__":
    unittest.main()
