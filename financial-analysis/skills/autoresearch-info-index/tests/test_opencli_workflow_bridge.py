#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import run_article_workflow
from macro_note_workflow_runtime import run_macro_note_workflow


def fake_news_index_result(topic: str) -> dict:
    return {
        "request": {
            "topic": topic,
            "analysis_time": "2026-04-03T08:00:00+00:00",
        },
        "observations": [],
        "claim_ledger": [],
        "report_markdown": f"# News Index {topic}\n",
    }


def fake_opencli_bridge_result() -> dict:
    return {
        "request": {
            "topic": "China aluminum broker note check",
            "analysis_time": "2026-04-03T08:00:00+00:00",
            "site_profile": "broker-research-portal",
            "input_mode": "result_path",
        },
        "import_summary": {
            "payload_source": "result_path",
            "imported_candidate_count": 1,
        },
        "runner_summary": {},
        "retrieval_request": {
            "candidates": [
                {
                    "source_id": "opencli-note-1",
                    "source_name": "Broker portal note",
                    "source_type": "research_note",
                    "origin": "opencli",
                    "published_at": "2026-04-03T07:20:00+00:00",
                    "observed_at": "2026-04-03T07:25:00+00:00",
                    "url": "https://research.example.com/china-aluminum-note",
                    "claim_ids": ["driver-state-known"],
                    "claim_states": {"driver-state-known": "support"},
                    "text_excerpt": "OpenCLI imported broker note excerpt.",
                    "channel": "shadow",
                    "access_mode": "browser_session",
                    "artifact_manifest": [],
                    "raw_metadata": {"opencli": {"site_profile": "broker-research-portal"}},
                }
            ]
        },
        "report_markdown": "# OpenCLI Bridge\n",
    }


def fake_brief_result() -> dict:
    return {
        "analysis_brief": {
            "recommended_thesis": "OpenCLI-enriched evidence is available.",
            "canonical_facts": [],
            "not_proven": [],
            "story_angles": [{"angle": "Broker note bridge"}],
            "macro_note_fields": {
                "one_line_judgment": {"text": "Macro note one-line judgment."},
                "confidence_markers": {"confidence_label": "medium", "confidence_interval": [0.4, 0.6], "confidence_gate": "watch", "evidence_mode": "mixed"},
                "current_state_rows": [{"state": "Confirmed", "detail": "OpenCLI candidate merged."}],
                "physical_vs_risk_premium": [{"bucket": "Risk premium", "assessment": "Still narrative-heavy."}],
                "benchmark_map": {"primary_benchmarks": ["SHFE aluminum"], "secondary_benchmarks": [], "benchmark_note": "Watch spread moves.", "benchmark_rows": []},
                "bias_table": [],
                "horizon_table": [],
                "what_changes_the_view": {"upgrades": ["A second high-tier confirmation arrives."], "downgrades": ["The portal note is contradicted by filings."]},
            },
            "scenario_matrix": [],
            "policy_pressure_overlay": {},
            "market_or_reader_relevance": [],
        },
        "source_summary": {},
        "evidence_bundle": {
            "contract_version": "1",
            "citations": [],
            "image_candidates": [],
        },
        "supporting_citations": [],
        "report_markdown": "# Brief\n",
    }


def fake_draft_result() -> dict:
    return {
        "article_package": {
            "title": "Draft title",
            "draft_thesis": "Draft thesis",
            "draft_mode": "balanced",
            "style_profile_applied": {},
            "selected_images": [],
            "citations": [],
        },
        "analysis_brief": {},
        "report_markdown": "# Draft\n",
        "preview_html": "<html></html>",
    }


def fake_review_result() -> dict:
    return {
        "review_rewrite_package": {
            "attacks": [],
            "claims_removed_or_softened": [],
            "rewrite_mode": "light",
            "pre_rewrite_quality_gate": "pass",
            "quality_gate": "pass",
        },
        "final_article_result": {
            "draft_thesis": "Final thesis",
        },
        "report_markdown": "# Review\n",
        "preview_html": "<html></html>",
    }


class OpenCliWorkflowBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-opencli-workflow-bridge"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_article_workflow_merges_opencli_candidates_and_records_stage_summary(self) -> None:
        captured_payloads: list[dict] = []

        def fake_run_news_index(payload: dict) -> dict:
            captured_payloads.append(payload)
            return fake_news_index_result("article-opencli")

        with (
            patch("article_workflow_runtime.prepare_opencli_bridge", return_value=fake_opencli_bridge_result()),
            patch("article_workflow_runtime.run_news_index", side_effect=fake_run_news_index),
            patch("article_workflow_runtime.build_analysis_brief", return_value=fake_brief_result()),
            patch("article_workflow_runtime.build_article_draft", return_value=fake_draft_result()),
            patch("article_workflow_runtime.build_article_revision", return_value=fake_review_result()),
            patch("article_workflow_runtime.build_revision_template", return_value={}),
            patch("article_workflow_runtime.build_feedback_markdown", return_value="# Feedback\n"),
            patch("article_workflow_runtime.summarize_asset_stage", return_value={}),
            patch("article_workflow_runtime.summarize_feedback_stage", return_value={}),
            patch("article_workflow_runtime.build_decision_trace", return_value={"review": {"style_learning": {}}}),
        ):
            result = run_article_workflow(
                {
                    "topic": "China aluminum broker note check",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "output_dir": str(self.temp_dir / "article"),
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "The latest external driver can be described with an exact date.",
                        }
                    ],
                    "opencli_config": {
                        "enabled": True,
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\opencli-result.json",
                    },
                }
            )

        self.assertEqual(result["source_stage"]["source_kind"], "news_index_opencli")
        self.assertEqual(result["source_stage"]["opencli_stage"]["imported_candidate_count"], 1)
        self.assertIn("OpenCLI Augmentation", result["report_markdown"])
        self.assertTrue(captured_payloads)
        merged_candidates = captured_payloads[0]["candidates"]
        self.assertEqual(len(merged_candidates), 1)
        self.assertEqual(merged_candidates[0]["origin"], "opencli")

    def test_macro_note_workflow_records_opencli_stage_summary(self) -> None:
        captured_payloads: list[dict] = []

        def fake_run_news_index(payload: dict) -> dict:
            captured_payloads.append(payload)
            return fake_news_index_result("macro-opencli")

        with (
            patch("macro_note_workflow_runtime.prepare_opencli_bridge", return_value=fake_opencli_bridge_result()),
            patch("macro_note_workflow_runtime.run_news_index", side_effect=fake_run_news_index),
            patch("macro_note_workflow_runtime.build_analysis_brief", return_value=fake_brief_result()),
        ):
            result = run_macro_note_workflow(
                {
                    "topic": "China aluminum broker note check",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "output_dir": str(self.temp_dir / "macro"),
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "The latest external driver can be described with an exact date.",
                        }
                    ],
                    "opencli_config": {
                        "enabled": True,
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\opencli-result.json",
                    },
                }
            )

        self.assertEqual(result["source_stage"]["source_kind"], "news_index_opencli")
        self.assertEqual(result["source_stage"]["opencli_stage"]["status"], "ok")
        self.assertEqual(result["source_stage"]["opencli_stage"]["payload_source"], "result_path")
        self.assertIn("OpenCLI Augmentation", result["report_markdown"])
        self.assertEqual(captured_payloads[0]["candidates"][0]["origin"], "opencli")

    def test_macro_note_workflow_continues_when_opencli_is_optional_and_fails(self) -> None:
        with (
            patch("macro_note_workflow_runtime.prepare_opencli_bridge", side_effect=ValueError("runner failed")),
            patch("macro_note_workflow_runtime.run_news_index", return_value=fake_news_index_result("macro-opencli-fallback")),
            patch("macro_note_workflow_runtime.build_analysis_brief", return_value=fake_brief_result()),
        ):
            result = run_macro_note_workflow(
                {
                    "topic": "China aluminum broker note check",
                    "analysis_time": "2026-04-03T08:00:00+00:00",
                    "output_dir": str(self.temp_dir / "macro-fallback"),
                    "opencli_config": {
                        "enabled": True,
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\missing.json",
                    },
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source_stage"]["opencli_stage"]["status"], "error")
        self.assertEqual(result["source_stage"]["opencli_stage"]["error"], "runner failed")

    def test_macro_note_workflow_raises_when_opencli_is_required_and_fails(self) -> None:
        with (
            patch("macro_note_workflow_runtime.prepare_opencli_bridge", side_effect=ValueError("runner failed")),
            patch("macro_note_workflow_runtime.run_news_index", return_value=fake_news_index_result("macro-opencli-required")),
            patch("macro_note_workflow_runtime.build_analysis_brief", return_value=fake_brief_result()),
        ):
            with self.assertRaisesRegex(ValueError, "runner failed"):
                run_macro_note_workflow(
                    {
                        "topic": "China aluminum broker note check",
                        "analysis_time": "2026-04-03T08:00:00+00:00",
                        "output_dir": str(self.temp_dir / "macro-required"),
                        "opencli_config": {
                            "enabled": True,
                            "required": True,
                            "site_profile": "broker-research-portal",
                            "result_path": "C:\\path\\to\\missing.json",
                        },
                    }
                )


if __name__ == "__main__":
    unittest.main()
