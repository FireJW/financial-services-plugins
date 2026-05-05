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

    def test_normalize_weekend_market_candidate_input_keeps_zero_post_x_result_metadata(self) -> None:
        normalized = module_under_test.normalize_weekend_market_candidate_input(
            {
                "x_live_index_results": [
                    {
                        "source_result_path": ".tmp/plan/result.x-index.json",
                        "run_completeness": {"status": "full", "x_posts_captured": 0},
                        "x_posts": [],
                    }
                ]
            }
        )

        self.assertIsNotNone(normalized)
        live_result = normalized["x_live_index_results"][0]
        self.assertEqual(live_result["source_result_path"], ".tmp/plan/result.x-index.json")
        self.assertEqual(live_result["run_completeness"]["x_posts_captured"], 0)
        self.assertEqual(live_result["x_posts"], [])

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

    def test_english_alias_matching_does_not_treat_launched_as_launch(self) -> None:
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/dd/status/1",
                                "author_handle": "DD_Geopolitics",
                                "combined_summary": "The administration launched a new campaign to reopen Hormuz while commercial shipping stayed blocked.",
                            }
                        ]
                    }
                ]
            }
        )

        topic_names = [item["topic_name"] for item in candidate["candidate_topics"]]
        self.assertIn("oil_shipping", topic_names)
        self.assertNotIn("commercial_space", topic_names)


class FreshnessFilterTests(unittest.TestCase):
    """Tests for X evidence freshness filtering (signal quality improvement #1)."""

    def test_stale_post_excluded_from_topic_scoring(self) -> None:
        """Live post older than 7 days should get zero weight in topic scoring."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reference_date": "2026-04-22",
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/old/status/1",
                                "author_handle": "old_poster",
                                "posted_at": "2026-04-10T12:00:00+00:00",
                                "combined_summary": "光通信和光模块继续发酵。",
                            }
                        ]
                    }
                ],
            }
        )
        # Post is 12 days old (> 7 day threshold) → should not produce a topic
        self.assertEqual(candidate["status"], "insufficient_signal")

    def test_fresh_post_included_in_topic_scoring(self) -> None:
        """Live post within 7 days should get full weight in topic scoring."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reference_date": "2026-04-22",
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/fresh/status/1",
                                "author_handle": "fresh_poster",
                                "posted_at": "2026-04-20T12:00:00+00:00",
                                "combined_summary": "光通信和光模块继续发酵。",
                            }
                        ]
                    }
                ],
            }
        )
        topic_names = [t["topic_name"] for t in candidate["candidate_topics"]]
        self.assertIn("optical_interconnect", topic_names)

    def test_geopolitics_topic_uses_stricter_threshold(self) -> None:
        """Posts about geopolitics topics older than 3 days should be stale."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reference_date": "2026-04-22",
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/geo/status/1",
                                "author_handle": "geo_poster",
                                "posted_at": "2026-04-17T12:00:00+00:00",
                                "combined_summary": "Hormuz blocked again, oil shipping and tanker rates remain elevated.",
                            }
                        ]
                    }
                ],
            }
        )
        # Post is 5 days old, but oil_shipping is geopolitics → 3-day threshold → stale
        self.assertEqual(candidate["status"], "insufficient_signal")

    def test_missing_posted_at_treated_as_fresh(self) -> None:
        """Posts without posted_at should not be penalized (treated as fresh)."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reference_date": "2026-04-22",
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/no_date/status/1",
                                "author_handle": "no_date_poster",
                                "combined_summary": "光通信和光模块继续发酵。",
                            }
                        ]
                    }
                ],
            }
        )
        topic_names = [t["topic_name"] for t in candidate["candidate_topics"]]
        self.assertIn("optical_interconnect", topic_names)

    def test_no_reference_date_skips_freshness_check(self) -> None:
        """When no reference_date is provided, all posts are treated as fresh (backward compat)."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/old/status/2",
                                "author_handle": "old_poster",
                                "posted_at": "2026-01-01T12:00:00+00:00",
                                "combined_summary": "光通信和光模块继续发酵。",
                            }
                        ]
                    }
                ],
            }
        )
        # No reference_date → no filtering → post counts
        topic_names = [t["topic_name"] for t in candidate["candidate_topics"]]
        self.assertIn("optical_interconnect", topic_names)


class MixedSignalDetectionTests(unittest.TestCase):
    """Tests for mixed-signal detection in live posts (signal quality improvement #2)."""

    def test_mixed_signal_post_gets_reduced_weight(self) -> None:
        """Post with both topic keywords and headwind keywords gets weight 1 instead of 2."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/mixed/status/1",
                                "author_handle": "mixed_poster",
                                "combined_summary": "Hormuz blocked again, oil shipping rates elevated. 但油价跳涨带来通胀压力。",
                            }
                        ]
                    }
                ],
            }
        )
        # oil_shipping topic inferred, but headwind "通胀" present → weight 1 instead of 2
        # With only weight 1, score < 6, so signal_strength should be "medium" not "high"
        topic_names = [t["topic_name"] for t in candidate["candidate_topics"]]
        self.assertIn("oil_shipping", topic_names)
        oil_topic = next(t for t in candidate["candidate_topics"] if t["topic_name"] == "oil_shipping")
        self.assertEqual(oil_topic["signal_strength"], "medium")

    def test_pure_bullish_post_gets_full_weight(self) -> None:
        """Post with only topic keywords (no headwind) gets full weight 2."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/bull/status/1",
                                "author_handle": "bull_poster",
                                "combined_summary": "光通信和光模块继续发酵，光器件需求强劲。",
                            }
                        ]
                    }
                ],
            }
        )
        topic_names = [t["topic_name"] for t in candidate["candidate_topics"]]
        self.assertIn("optical_interconnect", topic_names)

    def test_headwind_only_post_not_flagged_as_mixed(self) -> None:
        """Post with only headwind keywords but no topic match should not produce topics."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_live_index_results": [
                    {
                        "x_posts": [
                            {
                                "post_url": "https://x.com/bear/status/1",
                                "author_handle": "bear_poster",
                                "combined_summary": "通胀压力持续，降息推迟预期升温。",
                            }
                        ]
                    }
                ],
            }
        )
        self.assertEqual(candidate["status"], "insufficient_signal")


class RedditSkepticalDetectionTests(unittest.TestCase):
    """Tests for Reddit skeptical title detection (signal quality improvement #5)."""

    def test_skeptical_reddit_title_gets_zero_weight(self) -> None:
        """Reddit thread with 'why still ripping' pattern should get zero weight."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reddit_inputs": [
                    {
                        "subreddit": "ValueInvesting",
                        "thread_url": "https://reddit.com/example",
                        "thread_summary": "why are these shipping stocks still ripping?",
                        "theme_tags": ["oil_shipping"],
                        "direction_hint": "confirming",
                    }
                ],
            }
        )
        # Skeptical title → zero weight → no topic produced (only source was reddit)
        self.assertEqual(candidate["status"], "insufficient_signal")

    def test_confirming_reddit_gets_full_weight(self) -> None:
        """Reddit thread with confirming sentiment should get full weight."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_seed_inputs": [
                    {
                        "handle": "seed",
                        "url": "https://x.com/seed",
                        "display_name": "seed",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创"],
                    }
                ],
                "reddit_inputs": [
                    {
                        "subreddit": "stocks",
                        "thread_url": "https://reddit.com/example",
                        "thread_summary": "AI networking demand still supports optics",
                        "theme_tags": ["optical_interconnect"],
                        "direction_hint": "confirming",
                    }
                ],
            }
        )
        topic = candidate["candidate_topics"][0]
        self.assertEqual(topic["ranking_logic"]["reddit_confirmation"], "high")

    def test_direction_hint_questioning_overrides(self) -> None:
        """direction_hint='questioning' should override regardless of title content."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "reddit_inputs": [
                    {
                        "subreddit": "stocks",
                        "thread_url": "https://reddit.com/example",
                        "thread_summary": "Great outlook for optics sector",
                        "theme_tags": ["optical_interconnect"],
                        "direction_hint": "questioning",
                    }
                ],
            }
        )
        self.assertEqual(candidate["status"], "insufficient_signal")

    def test_reddit_confirmation_set_to_questioning(self) -> None:
        """When only skeptical reddit exists for a topic, reddit_confirmation should be 'questioning'."""
        candidate, _ = module_under_test.build_weekend_market_candidate(
            {
                "x_seed_inputs": [
                    {
                        "handle": "seed",
                        "url": "https://x.com/seed",
                        "display_name": "seed",
                        "tags": ["oil_shipping"],
                        "candidate_names": ["招商南油"],
                    },
                    {
                        "handle": "seed2",
                        "url": "https://x.com/seed2",
                        "display_name": "seed2",
                        "tags": ["oil_shipping"],
                        "candidate_names": ["中远海能"],
                    },
                ],
                "reddit_inputs": [
                    {
                        "subreddit": "ValueInvesting",
                        "thread_url": "https://reddit.com/example",
                        "thread_summary": "why are these shipping stocks still ripping?",
                        "theme_tags": ["oil_shipping"],
                        "direction_hint": "confirming",
                    }
                ],
            }
        )
        topic = next(t for t in candidate["candidate_topics"] if t["topic_name"] == "oil_shipping")
        self.assertEqual(topic["ranking_logic"]["reddit_confirmation"], "questioning")
        self.assertEqual(topic["ranking_logic"]["noise_or_disagreement"], "medium")


if __name__ == "__main__":
    unittest.main()
