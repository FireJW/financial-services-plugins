#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
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
    def test_normalize_weekend_market_candidate_input_keeps_seed_expansion_and_reddit_rows(self) -> None:
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
            }
        )

        self.assertEqual(normalized["x_seed_inputs"][0]["handle"], "tuolaji2024")
        self.assertNotIn("ignored", normalized["x_seed_inputs"][0])
        self.assertEqual(normalized["x_expansion_inputs"][0]["handle"], "aleabitoreddit")
        self.assertEqual(normalized["reddit_inputs"][0]["subreddit"], "wallstreetbets")

    def test_build_weekend_market_candidate_prefers_seed_consensus_and_returns_reference_map(self) -> None:
        candidate, reference_map = module_under_test.build_weekend_market_candidate(
            {
                "x_seed_inputs": [
                    {
                        "handle": "seed_one",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                    },
                    {
                        "handle": "seed_two",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "仕佳光子"],
                    },
                ],
                "x_expansion_inputs": [
                    {
                        "handle": "expansion_one",
                        "theme_overlap": ["optical_interconnect"],
                        "candidate_names": ["太辰光", "仕佳光子"],
                    }
                ],
                "reddit_inputs": [
                    {
                        "subreddit": "stocks",
                        "thread_summary": "AI networking demand still supports optics",
                        "theme_tags": ["optical_interconnect"],
                        "direction_hint": "confirming",
                    }
                ],
            }
        )

        self.assertEqual(candidate["status"], "candidate_only")
        self.assertEqual(candidate["candidate_topics"][0]["topic_name"], "optical_interconnect")
        self.assertEqual(reference_map[0]["direction_key"], "optical_interconnect")
        self.assertEqual(reference_map[0]["leaders"][0]["name"], "中际旭创")
        self.assertEqual(reference_map[0]["high_beta_names"][0]["name"], "太辰光")


if __name__ == "__main__":
    unittest.main()
