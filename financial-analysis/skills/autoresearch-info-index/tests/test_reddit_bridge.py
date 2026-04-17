from __future__ import annotations

import csv
import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
EXAMPLE_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "reddit-universal-scraper-sample"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import reddit_bridge_runtime
from reddit_bridge_runtime import run_reddit_bridge


class RedditBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-reddit-bridge"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bridge_can_import_external_export_root_with_selector(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "NVIDIA Blackwell demand",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result_path": str(EXAMPLE_FIXTURE_ROOT),
                "subreddit": "stocks",
                "claims": [{"claim_id": "claim-nvda", "claim_text": "NVIDIA Blackwell demand remains strong."}],
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["payload_source"], "csv_export_root")
        self.assertEqual(result["import_summary"]["comment_sample_count"], 2)
        self.assertTrue(result["import_summary"]["source_path"].endswith("data\\r_stocks\\posts.csv"))
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["source_name"], "Reddit r/stocks")
        self.assertEqual(
            observation["url"],
            "https://www.reddit.com/r/stocks/comments/nvda123/nvidia_blackwell_demand_thread/",
        )
        self.assertEqual(
            observation["raw_metadata"]["reddit_outbound_url"],
            "https://www.reuters.com/technology/nvidia-supply-chain-2026-04-04/",
        )
        self.assertEqual(observation["raw_metadata"]["bridge_export_target"], "r_stocks")
        self.assertEqual(observation["raw_metadata"]["subreddit_kind"], "broad_market")
        self.assertEqual(observation["raw_metadata"]["reddit_outbound_domain"], "www.reuters.com")
        self.assertEqual(observation["raw_metadata"]["top_comment_count"], 2)
        self.assertIn("CoWoS packaging remains the real bottleneck", observation["raw_metadata"]["top_comment_excerpt"])
        self.assertIn("supplier leverage only lasts", observation["raw_metadata"]["top_comment_summary"])
        self.assertIn("subreddit_kind:broad_market", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("outbound_domain:www.reuters.com", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("score 1820", observation["discovery_reason"])
        self.assertIn("410 comments", observation["discovery_reason"])
        self.assertIn("2/410 comments sampled", observation["discovery_reason"])

    def test_bridge_can_import_external_user_export_directory(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "LNG shipping retail thread",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result_path": str(EXAMPLE_FIXTURE_ROOT / "data" / "u_macroalpha"),
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["payload_source"], "csv_directory")
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["bridge_export_kind"], "user")
        self.assertEqual(observation["raw_metadata"]["bridge_export_user"], "macroalpha")
        self.assertEqual(observation["raw_metadata"]["author_normalized"], "u/macroalpha")
        self.assertIn("export_target:u_macroalpha", observation["raw_metadata"]["bridge_tags"])

    def test_bridge_requires_selector_when_export_root_has_multiple_targets(self) -> None:
        with self.assertRaisesRegex(ValueError, "multiple export targets"):
            run_reddit_bridge(
                {
                    "topic": "Ambiguous Reddit export root",
                    "analysis_time": "2026-04-04T04:00:00+00:00",
                    "reddit_result_path": str(EXAMPLE_FIXTURE_ROOT),
                }
            )

    def test_bridge_can_import_posts_csv_directory(self) -> None:
        export_dir = self.temp_dir / "r_stocks"
        export_dir.mkdir(parents=True, exist_ok=True)
        posts_path = export_dir / "posts.csv"
        with posts_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["title", "subreddit", "permalink", "selftext", "score", "num_comments", "created_utc"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "title": "NVIDIA Blackwell demand thread",
                    "subreddit": "stocks",
                    "permalink": "/r/stocks/comments/test123/nvidia_blackwell_demand_thread/",
                    "selftext": "Retail investors are debating supplier leverage and timing.",
                    "score": "1820",
                    "num_comments": "410",
                    "created_utc": "2026-04-04T03:20:00+00:00",
                }
            )

        result = run_reddit_bridge(
            {
                "topic": "NVIDIA Blackwell demand",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result_path": str(export_dir),
                "claims": [{"claim_id": "claim-nvda", "claim_text": "NVIDIA Blackwell demand remains strong."}],
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["payload_source"], "csv_directory")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["origin"], "reddit_bridge")
        self.assertEqual(observation["source_name"], "Reddit r/stocks")
        self.assertEqual(
            observation["url"],
            "https://www.reddit.com/r/stocks/comments/test123/nvidia_blackwell_demand_thread/",
        )
        self.assertIn("supplier leverage and timing", observation["text_excerpt"])

    def test_bridge_can_import_inline_reddit_posts_payload(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "TSMC CoWoS bottleneck",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result": {
                    "posts": [
                        {
                            "title": "TSMC CoWoS bottleneck discussion",
                            "subreddit": "investing",
                            "permalink": "/r/investing/comments/test456/tsmc_cowos_bottleneck_discussion/",
                            "selftext": "The thread debates packaging constraints and AI demand spillover.",
                            "score": 980,
                            "num_comments": 220,
                            "created_utc": "2026-04-04T03:10:00+00:00",
                        }
                    ]
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["payload_source"], "reddit_result")
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["source_name"], "Reddit r/investing")
        self.assertEqual(observation["source_type"], "social")
        self.assertEqual(observation["channel"], "shadow")

    def test_bridge_preserves_listing_window_and_subreddit_profile_metadata(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Security analysis read-through",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result": {
                    "posts": [
                        {
                            "title": "Deep dive on supplier leverage",
                            "author": "forensic-gaap",
                            "subreddit": "SecurityAnalysis",
                            "permalink": "/r/SecurityAnalysis/comments/test999/deep_dive_on_supplier_leverage/",
                            "url": "https://www.ft.com/content/test-security-analysis",
                            "selftext": "Long-form discussion about supply chain bottlenecks and gross margin durability.",
                            "score": 640,
                            "num_comments": 95,
                            "created_utc": "2026-04-04T03:05:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ]
                },
            }
        )

        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["subreddit_kind"], "deep_research")
        self.assertEqual(observation["raw_metadata"]["reddit_listing_normalized"], "top")
        self.assertEqual(observation["raw_metadata"]["reddit_listing_window_normalized"], "week")
        self.assertEqual(observation["raw_metadata"]["reddit_outbound_domain"], "www.ft.com")
        self.assertIn("subreddit_kind:deep_research", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("listing:top", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("listing_window:week", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("outbound_domain:www.ft.com", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("listing top/week", observation["discovery_reason"])

    def test_bridge_can_merge_inline_comment_payload_into_post_metadata(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Retail AI infra debate",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result": {
                    "posts": [
                        {
                            "id": "wsb123",
                            "title": "I am still long AI infra",
                            "author": "degentrader",
                            "subreddit": "wallstreetbets",
                            "permalink": "/r/wallstreetbets/comments/wsb123/i_am_still_long_ai_infra/",
                            "url": "https://www.reddit.com/r/wallstreetbets/comments/wsb123/i_am_still_long_ai_infra/",
                            "selftext": "The post itself is noisy but has real discussion in comments.",
                            "score": 1200,
                            "num_comments": 340,
                            "created_utc": "2026-04-04T03:15:00+00:00"
                        }
                    ],
                    "comments": [
                        {
                            "id": "wsbc1",
                            "link_id": "t3_wsb123",
                            "author": "cashflowlurker",
                            "score": 130,
                            "created_utc": "2026-04-04T03:20:00+00:00",
                            "body": "Top reply says hyperscaler capex still matters more than meme sentiment.",
                            "permalink": "/r/wallstreetbets/comments/wsb123/i_am_still_long_ai_infra/wsbc1/"
                        }
                    ]
                },
            }
        )

        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["subreddit_kind"], "speculative_flow")
        self.assertEqual(observation["raw_metadata"]["subreddit_signal_level"], "low")
        self.assertEqual(observation["raw_metadata"]["top_comment_count"], 1)
        self.assertIn("hyperscaler capex still matters", observation["raw_metadata"]["top_comment_summary"])
        self.assertEqual(observation["raw_metadata"]["comment_declared_count"], 340)
        self.assertAlmostEqual(observation["raw_metadata"]["comment_sample_coverage_ratio"], 0.0029, places=4)
        self.assertTrue(observation["raw_metadata"]["comment_count_mismatch"])
        self.assertEqual(observation["raw_metadata"]["comment_sample_status"], "partial")
        operator_review = observation["raw_metadata"]["comment_operator_review"]
        operator_priority = observation["raw_metadata"]["operator_review_priority"]
        self.assertTrue(operator_review["review_required"])
        self.assertTrue(operator_review["has_partial_sample"])
        self.assertFalse(operator_review["has_exact_duplicates"])
        self.assertFalse(operator_review["has_near_duplicates"])
        self.assertEqual(operator_review["comment_sample_status"], "partial")
        self.assertEqual(operator_review["comment_declared_count"], 340)
        self.assertEqual(operator_review["top_comment_count"], 1)
        self.assertEqual(operator_review["comment_sample_coverage_ratio"], 0.0029)
        self.assertTrue(any("partial comment sample: 1/340" in caution for caution in operator_review["cautions"]))
        self.assertTrue(operator_priority["review_required"])
        self.assertEqual(operator_priority["priority_level"], "medium")
        self.assertIn("partial_comment_sample", operator_priority["reasons"])
        self.assertIn("very_thin_comment_sample", operator_priority["reasons"])
        self.assertIn("low_signal_subreddit", operator_priority["reasons"])
        self.assertIn("subreddit_signal:low", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("comment_sample:partial", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("1/340 comments sampled", observation["discovery_reason"])
        self.assertEqual(result["import_summary"]["comment_sample_count"], 1)
        self.assertEqual(result["import_summary"]["comment_count_mismatch_count"], 1)
        self.assertEqual(result["import_summary"]["operator_review_required_count"], 1)
        self.assertEqual(result["import_summary"]["operator_review_high_priority_count"], 0)
        self.assertEqual(result["operator_review_queue"][0]["priority_level"], "medium")
        self.assertIn("## Operator Review", result["report_markdown"])
        self.assertIn("[medium]", result["report_markdown"])
        self.assertIn("partial comment sample: 1/340", result["report_markdown"])

    def test_bridge_can_read_nested_comment_payload_aliases_with_hybrid_sorting(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Nested Reddit comments",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "comment_sort_strategy": "hybrid",
                "reddit_result": {
                    "posts": [
                        {
                            "id": "mix123",
                            "title": "AI infra mixed thread",
                            "subreddit": "stocks",
                            "permalink": "/r/stocks/comments/mix123/ai_infra_mixed_thread/",
                            "selftext": "Post body stays secondary to the comment layer here.",
                            "score": 880,
                            "num_comments": 220,
                            "created_utc": "2026-04-04T03:10:00+00:00",
                            "comments": [
                                {
                                    "comment_id": "mixc1",
                                    "submission_id": "mix123",
                                    "user": "slower-bull",
                                    "upvotes": 120,
                                    "time": "2026-04-04T03:20:00+00:00",
                                    "comment_text": "Older high-score comment says demand is real but capex discipline still matters.",
                                },
                                {
                                    "comment_id": "mixc2",
                                    "submission_url": "https://www.reddit.com/r/stocks/comments/mix123/ai_infra_mixed_thread/",
                                    "author_name": "faster-bull",
                                    "vote_score": 118,
                                    "created": "2026-04-04T03:58:00+00:00",
                                    "body_text": "Fresher reply says supplier bottlenecks matter more than headline momentum.",
                                },
                            ],
                        }
                    ]
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["comment_sort_strategy"], "hybrid")
        self.assertEqual(result["import_summary"]["comment_sample_count"], 2)
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["top_comment_sort_strategy"], "hybrid")
        self.assertEqual(observation["raw_metadata"]["top_comment_count"], 2)
        self.assertIn("supplier bottlenecks matter more", observation["raw_metadata"]["top_comment_excerpt"])
        self.assertIn("u/faster-bull", observation["raw_metadata"]["top_comment_authors"])
        self.assertIn("u/slower-bull", observation["raw_metadata"]["top_comment_authors"])
        self.assertIn("comment_sort:hybrid", observation["raw_metadata"]["bridge_tags"])

    def test_bridge_deduplicates_repeated_comment_snapshots(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Duplicate Reddit comments",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result": {
                    "posts": [
                        {
                            "id": "dup123",
                            "title": "Duplicate comment thread",
                            "subreddit": "stocks",
                            "permalink": "/r/stocks/comments/dup123/duplicate_comment_thread/",
                            "selftext": "Thread body is not the main point here.",
                            "score": 760,
                            "num_comments": 210,
                            "created_utc": "2026-04-04T03:00:00+00:00",
                        }
                    ],
                    "comments": [
                        {
                            "id": "dupc1",
                            "link_id": "t3_dup123",
                            "author": "repeatbull",
                            "score": 96,
                            "created_utc": "2026-04-04T03:12:00+00:00",
                            "body": "Capex discipline still matters more than headline excitement.",
                        },
                        {
                            "id": "dupc1b",
                            "link_id": "t3_dup123",
                            "author": "repeatbull",
                            "score": 96,
                            "created_utc": "2026-04-04T03:12:10+00:00",
                            "body": "Capex discipline still matters more than headline excitement.",
                        },
                        {
                            "id": "dupc2",
                            "link_id": "t3_dup123",
                            "author": "semicapwatch",
                            "score": 82,
                            "created_utc": "2026-04-04T03:18:00+00:00",
                            "body": "Packaging bottlenecks still cap upside through the quarter.",
                        }
                    ],
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["comment_sample_count"], 3)
        self.assertEqual(result["import_summary"]["comment_duplicate_count_total"], 1)
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["comment_raw_count"], 3)
        self.assertEqual(observation["raw_metadata"]["comment_duplicate_count"], 1)
        self.assertEqual(observation["raw_metadata"].get("comment_near_duplicate_count", 0), 0)
        self.assertEqual(observation["raw_metadata"]["top_comment_count"], 2)
        self.assertIn("comment_deduped", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("deduped 1 duplicate comments", observation["discovery_reason"])

    def test_bridge_flags_near_duplicate_comments_without_deduping_them(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Value investing supplier leverage debate",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "comment_sort_strategy": "hybrid",
                "reddit_result": {
                    "posts": [
                        {
                            "id": "val123",
                            "title": "Is supplier leverage durable or just another AI squeeze?",
                            "subreddit": "ValueInvesting",
                            "permalink": "/r/ValueInvesting/comments/val123/is_supplier_leverage_durable_or_just_another_ai_squeeze/",
                            "selftext": "Thread body is less important than the comment read-through.",
                            "score": 410,
                            "num_comments": 48,
                            "created_utc": "2026-04-04T03:05:00+00:00",
                            "listing": "top",
                            "time_filter": "week",
                        }
                    ],
                    "comments": [
                        {
                            "id": "valc1",
                            "link_id": "t3_val123",
                            "author": "grossmarginmap",
                            "score": 76,
                            "created_utc": "2026-04-04T03:18:00+00:00",
                            "body": "Best reply says supplier leverage lasts only while packaging lead times stay tight and customers cannot dual-source.",
                        },
                        {
                            "id": "valc2",
                            "link_id": "t3_val123",
                            "author": "grossmarginmap-alt",
                            "score": 73,
                            "created_utc": "2026-04-04T03:26:00+00:00",
                            "body": "Best reply says supplier leverage only lasts while packaging lead times stay tight and customers cannot dual source.",
                        },
                        {
                            "id": "valc3",
                            "link_id": "t3_val123",
                            "author": "forensic-gaap",
                            "score": 84,
                            "created_utc": "2026-04-04T03:41:00+00:00",
                            "body": "A different reply says earnings durability depends more on what happens after capacity expands.",
                        },
                    ],
                },
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["import_summary"]["comment_near_duplicate_count_total"], 1)
        self.assertEqual(result["import_summary"]["comment_near_duplicate_cross_author_count_total"], 1)
        self.assertEqual(result["import_summary"]["comment_near_duplicate_same_author_count_total"], 0)
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["subreddit_kind"], "deep_research")
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_count"], 1)
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_cross_author_count"], 1)
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_same_author_count"], 0)
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_level"], "cross_author")
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_example_count"], 1)
        self.assertTrue(observation["raw_metadata"]["comment_near_duplicate_examples"])
        self.assertIn(
            "cross_author:u/grossmarginmap -> u/grossmarginmap-alt",
            observation["raw_metadata"]["comment_near_duplicate_examples"][0],
        )
        self.assertEqual(observation["raw_metadata"]["top_comment_count"], 3)
        operator_review = observation["raw_metadata"]["comment_operator_review"]
        operator_priority = observation["raw_metadata"]["operator_review_priority"]
        self.assertTrue(operator_review["review_required"])
        self.assertTrue(operator_review["has_partial_sample"])
        self.assertFalse(operator_review["has_exact_duplicates"])
        self.assertTrue(operator_review["has_near_duplicates"])
        self.assertEqual(operator_review["near_duplicate_level"], "cross_author")
        self.assertEqual(operator_review["comment_near_duplicate_example_count"], 1)
        self.assertTrue(any("partial comment sample" in caution for caution in operator_review["cautions"]))
        self.assertTrue(any("near-duplicate comments flagged: 1 (cross-author 1)" in caution for caution in operator_review["cautions"]))
        self.assertIn("grossmarginmap", operator_review["comment_near_duplicate_examples"][0])
        self.assertTrue(operator_priority["review_required"])
        self.assertEqual(operator_priority["priority_level"], "high")
        self.assertIn("cross_author_near_duplicates", operator_priority["reasons"])
        self.assertIn("comment_near_duplicate", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("comment_near_duplicate:cross_author", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("flagged 1 near-duplicate comments (cross-author 1)", observation["discovery_reason"])
        self.assertEqual(result["import_summary"]["operator_review_required_count"], 1)
        self.assertEqual(result["import_summary"]["operator_review_high_priority_count"], 1)
        self.assertEqual(result["operator_review_queue"][0]["priority_level"], "high")
        self.assertIn("## Operator Review", result["report_markdown"])
        self.assertIn("[high]", result["report_markdown"])
        self.assertIn("near-duplicate comments flagged: 1 (cross-author 1)", result["report_markdown"])

    def test_bridge_can_distinguish_same_author_near_duplicate_comments(self) -> None:
        result = run_reddit_bridge(
            {
                "topic": "Same author reply drift",
                "analysis_time": "2026-04-04T04:00:00+00:00",
                "reddit_result": {
                    "posts": [
                        {
                            "id": "same123",
                            "title": "Same author update thread",
                            "subreddit": "stocks",
                            "permalink": "/r/stocks/comments/same123/same_author_update_thread/",
                            "selftext": "Watching whether one author's repeated wording gets overcounted.",
                            "score": 280,
                            "num_comments": 20,
                            "created_utc": "2026-04-04T03:00:00+00:00"
                        }
                    ],
                    "comments": [
                        {
                            "id": "samec1",
                            "link_id": "t3_same123",
                            "author": "revisionbull",
                            "score": 22,
                            "created_utc": "2026-04-04T03:14:00+00:00",
                            "body": "Margins hold while packaging stays constrained and customers still have limited alternatives."
                        },
                        {
                            "id": "samec2",
                            "link_id": "t3_same123",
                            "author": "revisionbull",
                            "score": 21,
                            "created_utc": "2026-04-04T03:17:00+00:00",
                            "body": "Margins hold while packaging remains constrained and customers still have limited alternatives."
                        }
                    ]
                }
            }
        )

        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_count"], 1)
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_same_author_count"], 1)
        self.assertEqual(observation["raw_metadata"].get("comment_near_duplicate_cross_author_count", 0), 0)
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_level"], "same_author_only")
        self.assertEqual(observation["raw_metadata"]["comment_near_duplicate_example_count"], 1)
        self.assertIn(
            "same_author:u/revisionbull -> u/revisionbull",
            observation["raw_metadata"]["comment_near_duplicate_examples"][0],
        )
        self.assertIn("comment_near_duplicate:same_author_only", observation["raw_metadata"]["bridge_tags"])
        self.assertIn("flagged 1 near-duplicate comments (same-author 1)", observation["discovery_reason"])


if __name__ == "__main__":
    unittest.main()
