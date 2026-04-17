from __future__ import annotations

import shutil
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_evidence_bundle import (
    CONTRACT_VERSION,
    build_citations,
    build_image_candidates,
    build_shared_evidence_bundle,
    citation_by_source_id,
    summarize_reddit_operator_review,
)


class ArticleEvidenceBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-article-evidence-bundle"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def base_request(self) -> dict:
        return {
            "topic": "Indirect talks tracker",
            "analysis_time": datetime(2026, 3, 24, 12, 0, tzinfo=UTC),
            "draft_mode": "image_first",
            "image_strategy": "prefer_images",
        }

    def base_source_result(self) -> dict:
        screenshot_path = self.temp_dir / "root-shot.png"
        media_path = self.temp_dir / "post-media.png"
        screenshot_path.write_bytes(b"png")
        media_path.write_bytes(b"png")
        return {
            "request": {
                "claims": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "Indirect talks continue through intermediaries.",
                        "claim_text_zh": "间接谈判仍通过中间方持续进行。",
                    },
                    {
                        "claim_id": "claim-breakthrough",
                        "claim_text": "A final breakthrough has already been confirmed.",
                        "claim_text_zh": "最终突破已经被确认。",
                    },
                ],
                "market_relevance_zh": ["油气", "航运"],
            },
            "retrieval_result": {
                "observations": [
                    {
                        "source_id": "reuters-1",
                        "source_name": "Reuters",
                        "source_type": "wire",
                        "source_tier": 1,
                        "channel": "core",
                        "access_mode": "public",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:35:00+00:00",
                        "url": "https://example.com/reuters-talks",
                        "text_excerpt": "Indirect talks continue through intermediaries according to diplomats.",
                        "combined_summary": "Indirect talks continue through intermediaries according to diplomats.",
                        "claim_ids": ["claim-core"],
                        "claim_states": {"claim-core": "support"},
                        "root_post_screenshot_path": str(screenshot_path),
                        "media_items": [
                            {
                                "local_artifact_path": str(media_path),
                                "source_url": "https://cdn.example.com/reuters-talks.png",
                                "caption": "A chart showing mediator contacts over time.",
                                "image_relevance_to_post": "high",
                                "capture_method": "manual_download",
                            }
                        ],
                        "public_page_hints": {
                            "text_excerpt": "Fallback page hint excerpt.",
                            "post_summary": "Fallback page hint summary.",
                            "media_summary": "Fallback page hint media summary.",
                        },
                    },
                    {
                        "source_id": "portal-1",
                        "source_name": "Research Portal",
                        "source_type": "research_note",
                        "source_tier": 2,
                        "channel": "shadow",
                        "access_mode": "blocked",
                        "published_at": "",
                        "observed_at": "2026-03-24T11:40:00+00:00",
                        "url": "https://example.com/login-wall",
                        "media_summary": "Log in to continue",
                        "text_excerpt": "Browser session was required before the note body could be verified.",
                        "claim_ids": ["claim-breakthrough"],
                        "claim_states": {"claim-breakthrough": "unclear"},
                    },
                ],
                "claim_ledger": [
                    {
                        "claim_id": "claim-core",
                        "claim_text": "Indirect talks continue through intermediaries.",
                        "status": "confirmed",
                    }
                ],
                "verdict_output": {
                    "confidence_interval": [72, 88],
                    "confidence_gate": "pass",
                    "core_verdict": "confirmed",
                    "market_relevance": ["energy", "shipping"],
                    "confirmed": [
                        {
                            "claim_id": "claim-core",
                            "claim_text": "Indirect talks continue through intermediaries.",
                        }
                    ],
                    "not_confirmed": [
                        {
                            "claim_id": "claim-breakthrough",
                            "claim_text": "A final breakthrough has already been confirmed.",
                        }
                    ],
                    "inference_only": [
                        {
                            "claim_id": "claim-sanctions",
                            "claim_text": "Sanctions relief is imminent.",
                        }
                    ],
                    "latest_signals": [
                        {
                            "source_name": "Reuters",
                            "source_tier": 1,
                            "channel": "core",
                            "age": "30m",
                            "text_excerpt": "Indirect talks continue through intermediaries.",
                        }
                    ],
                    "next_watch_items": [
                        "Watch for a fresh Tier 0 confirmation.",
                        "Track whether mediator statements change.",
                    ],
                },
            },
        }

    def test_build_shared_evidence_bundle_keeps_digest_and_citation_map(self) -> None:
        bundle = build_shared_evidence_bundle(self.base_source_result(), self.base_request())

        self.assertEqual(bundle["contract_version"], CONTRACT_VERSION)
        self.assertEqual(bundle["topic"], "Indirect talks tracker")
        self.assertEqual(bundle["source_kind"], "news_index")
        self.assertEqual(bundle["source_summary"]["observation_count"], 2)
        self.assertEqual(bundle["source_summary"]["blocked_source_count"], 1)
        self.assertEqual(bundle["source_summary"]["core_source_count"], 1)
        self.assertEqual(bundle["evidence_digest"]["confirmed_zh"], ["间接谈判仍通过中间方持续进行。"])
        self.assertEqual(bundle["evidence_digest"]["not_confirmed_zh"], ["最终突破已经被确认。"])
        self.assertEqual(bundle["citation_by_source_id"]["reuters-1"], "S1")
        self.assertEqual(bundle["claim_ledger"][0]["status"], "confirmed")

    def test_build_citations_prefers_meaningful_text_over_ui_noise(self) -> None:
        citations = build_citations(self.base_source_result())
        mapping = citation_by_source_id(citations)

        self.assertEqual(len(citations), 2)
        self.assertEqual(mapping["reuters-1"], "S1")
        self.assertEqual(mapping["portal-1"], "S2")
        self.assertIn("Indirect talks continue", citations[0]["title"])
        self.assertNotIn("Log in to continue", citations[1]["title"])
        self.assertIn("Browser session was required", citations[1]["excerpt"])

    def test_build_image_candidates_prefers_post_media_when_images_requested(self) -> None:
        candidates = build_image_candidates(self.base_source_result(), self.base_request())
        roles = [item["role"] for item in candidates]

        self.assertGreaterEqual(len(candidates), 2)
        self.assertIn("post_media", roles)
        self.assertIn("root_post_screenshot", roles)
        post_media = next(item for item in candidates if item["role"] == "post_media")
        self.assertTrue(Path(post_media["path"]).exists())
        self.assertIn("chart showing mediator contacts", post_media["caption"].lower())

    def test_summarize_reddit_operator_review_builds_blocking_gate(self) -> None:
        source_result = {
            "operator_review_queue": [
                {
                    "title": "AI infra thread",
                    "priority_level": "high",
                    "priority_score": 95,
                    "review_required": True,
                    "summary": "Cross-author near-duplicate comments need a human check.",
                    "recommended_action": "Review Reddit comment evidence before promotion.",
                }
            ],
            "retrieval_result": {
                "observations": [
                    {
                        "source_name": "Reddit r/stocks",
                        "url": "https://www.reddit.com/r/stocks/comments/abc123/ai_infra_thread/",
                        "raw_metadata": {
                            "operator_review_priority": {
                                "priority_level": "high",
                                "priority_score": 95,
                                "review_required": True,
                                "summary": "Cross-author near-duplicate comments need a human check.",
                                "recommended_action": "Review Reddit comment evidence before promotion.",
                            }
                        },
                    }
                ],
                "import_summary": {
                    "operator_review_required_count": 1,
                    "operator_review_high_priority_count": 1,
                },
            },
        }

        summary = summarize_reddit_operator_review(source_result)
        gate = summary["reddit_comment_review_gate"]

        self.assertGreaterEqual(summary["operator_review_required_count"], 1)
        self.assertGreaterEqual(summary["operator_review_high_priority_count"], 1)
        self.assertTrue(gate["required"])
        self.assertEqual(gate["status"], "awaiting_reddit_operator_review")
        self.assertEqual(gate["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertGreaterEqual(gate["queue_size"], 1)
        self.assertEqual(gate["priority_level"], "high")
        self.assertIn("Review Reddit comment evidence", gate["recommended_action"])


if __name__ == "__main__":
    unittest.main()
