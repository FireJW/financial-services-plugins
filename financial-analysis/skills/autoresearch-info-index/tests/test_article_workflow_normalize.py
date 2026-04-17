#!/usr/bin/env python3
"""Tests for normalize_workflow_request in article_workflow_runtime."""
from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import normalize_workflow_request
from news_index_core import run_news_index


def _minimal_news_result() -> dict:
    return run_news_index(
        {
            "topic": "Test topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {"claim_id": "c1", "claim_text": "Claim one."}
            ],
            "candidates": [
                {
                    "source_id": "s1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T11:30:00+00:00",
                    "url": "https://example.com/r1",
                    "text_excerpt": "Claim one confirmed.",
                    "claim_ids": ["c1"],
                    "claim_states": {"c1": "support"},
                },
            ],
        }
    )


def _base_indexed_request(**overrides: object) -> dict:
    base = {
        "source_result": _minimal_news_result(),
        "output_dir": str(Path.cwd() / ".tmp" / "test-normalize"),
    }
    base.update(overrides)
    return base


class TestNormalizeWorkflowRequest(unittest.TestCase):
    """Unit tests for normalize_workflow_request."""

    # ── payload kind detection ──

    def test_indexed_result_detected_from_source_result(self) -> None:
        req = normalize_workflow_request(_base_indexed_request())
        self.assertEqual(req["payload_kind"], "indexed_result")

    def test_news_request_detected_from_topic_and_claims(self) -> None:
        req = normalize_workflow_request({
            "topic": "News topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [{"claim_id": "c1", "claim_text": "Claim."}],
            "candidates": [],
            "output_dir": "/tmp/out",
        })
        self.assertEqual(req["payload_kind"], "news_request")

    def test_x_request_detected_from_seed_posts(self) -> None:
        req = normalize_workflow_request({
            "seed_posts": [{"url": "https://x.com/post/1"}],
            "topic": "X topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "output_dir": "/tmp/out",
        })
        self.assertEqual(req["payload_kind"], "x_request")

    def test_x_request_detected_from_manual_urls(self) -> None:
        req = normalize_workflow_request({
            "manual_urls": ["https://x.com/post/1"],
            "topic": "X topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "output_dir": "/tmp/out",
        })
        self.assertEqual(req["payload_kind"], "x_request")

    def test_last30days_request_detected(self) -> None:
        req = normalize_workflow_request({
            "last30days_result_path": "/tmp/last30days.json",
            "topic": "30d topic",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "output_dir": "/tmp/out",
        })
        self.assertEqual(req["payload_kind"], "last30days_request")

    # ── analysis_time resolution ──

    def test_analysis_time_from_top_level(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(
            analysis_time="2026-04-01T08:00:00+00:00",
        ))
        self.assertEqual(req["analysis_time"].year, 2026)
        self.assertEqual(req["analysis_time"].month, 4)

    def test_analysis_time_falls_back_to_source_result(self) -> None:
        base = _base_indexed_request()
        base.pop("analysis_time", None)
        req = normalize_workflow_request(base)
        self.assertIsNotNone(req["analysis_time"])

    def test_missing_analysis_time_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            normalize_workflow_request({
                "topic": "No time",
                "claims": [],
                "candidates": [],
                "output_dir": "/tmp/out",
            })

    # ── topic resolution ──

    def test_topic_from_top_level(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(topic="Custom topic"))
        self.assertEqual(req["topic"], "Custom topic")

    def test_topic_falls_back_to_source(self) -> None:
        base = _base_indexed_request()
        base.pop("topic", None)
        req = normalize_workflow_request(base)
        self.assertTrue(len(req["topic"]) > 0)

    # ── output_dir ──

    def test_explicit_output_dir_used(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(
            output_dir="/custom/out",
        ))
        self.assertEqual(str(req["output_dir"]), str(Path("/custom/out").expanduser()))

    def test_output_dir_auto_generated_when_missing(self) -> None:
        base = _base_indexed_request()
        base.pop("output_dir", None)
        req = normalize_workflow_request(base)
        self.assertIsInstance(req["output_dir"], Path)
        self.assertTrue(str(req["output_dir"]))

    # ── field aliases ──

    def test_headline_hook_mode_alias(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(
            title_hook_mode="bold",
        ))
        self.assertEqual(req["headline_hook_mode"], "bold")

    def test_language_mode_alias(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(
            output_language="chinese",
        ))
        self.assertEqual(req["language_mode"], "chinese")

    def test_headline_hook_prefixes_alias(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(
            title_prefixes=["BREAKING"],
        ))
        self.assertEqual(req["headline_hook_prefixes"], ["BREAKING"])

    # ── cleanup config ──

    def test_cleanup_enabled_from_cleanup_days(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(cleanup_days=7))
        self.assertTrue(req["cleanup_enabled"])
        self.assertEqual(req["cleanup_days"], 7)

    def test_cleanup_disabled_by_default(self) -> None:
        req = normalize_workflow_request(_base_indexed_request())
        self.assertFalse(req["cleanup_enabled"])

    # ── optional fields forwarded ──

    def test_image_strategy_forwarded(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(image_strategy="prefer_images"))
        self.assertEqual(req["image_strategy"], "prefer_images")

    def test_draft_mode_forwarded(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(draft_mode="image_first"))
        self.assertEqual(req["draft_mode"], "image_first")

    def test_max_images_forwarded(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(max_images=5))
        self.assertEqual(req["max_images"], 5)

    def test_tone_forwarded(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(tone="cautious"))
        self.assertEqual(req["tone"], "cautious")

    def test_angle_forwarded(self) -> None:
        req = normalize_workflow_request(_base_indexed_request(angle="geopolitical risk"))
        self.assertEqual(req["angle"], "geopolitical risk")


if __name__ == "__main__":
    unittest.main()
