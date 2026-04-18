#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as module_under_test


class MonthEndShortlistProfilePassthroughTests(unittest.TestCase):
    def test_normalize_request_preserves_cleaned_geopolitics_candidate_input(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_candidate_input": {
                    "news_signals": [
                        {
                            "source": "ap",
                            "headline": "Shipping disruption fears rise",
                            "summary": "Hormuz disruption risk repriced.",
                            "direction_hint": "escalation",
                            "timestamp": "2026-04-18T09:30:00+08:00",
                        }
                    ],
                    "x_signals": [
                        {
                            "account": "MacroDesk",
                            "url": "https://x.com/example/status/1",
                            "summary": "Energy traders lean toward renewed supply fear.",
                            "direction_hint": "escalation",
                            "timestamp": "2026-04-18T09:40:00+08:00",
                        }
                    ],
                    "market_signals": {
                        "oil": "up",
                        "gold": "up",
                        "shipping": "up",
                        "risk_style": "risk_off",
                        "usd_rates": "tightening",
                        "airlines": "down",
                        "industrials": "down",
                    },
                    "ignored_field": "drop-me",
                },
            }
        )

        self.assertIn("macro_geopolitics_candidate_input", normalized)
        candidate_input = normalized["macro_geopolitics_candidate_input"]
        self.assertEqual(candidate_input["news_signals"][0]["direction_hint"], "escalation")
        self.assertEqual(candidate_input["x_signals"][0]["account"], "MacroDesk")
        self.assertEqual(candidate_input["market_signals"]["oil"], "up")
        self.assertNotIn("ignored_field", candidate_input)

    def test_candidate_input_does_not_auto_create_formal_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_candidate_input": {
                    "news_signals": [
                        {
                            "headline": "Talks resume",
                            "summary": "Transit may normalize.",
                            "direction_hint": "de_escalation",
                        }
                    ],
                    "market_signals": {
                        "oil": "down",
                        "gold": "down",
                    },
                },
            }
        )

        self.assertIn("macro_geopolitics_candidate_input", normalized)
        self.assertNotIn("macro_geopolitics_overlay", normalized)

    def test_normalize_request_preserves_cleaned_geopolitics_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_overlay": {
                    "regime_label": "escalation",
                    "confidence": "medium",
                    "headline_risk": "high",
                    "beneficiary_chains": ["oil_shipping", "gold", "unknown_chain"],
                    "headwind_chains": ["airlines", "high_beta_growth", "mystery"],
                    "notes": "Hormuz disruption risk repriced.",
                    "extra_field": "drop-me",
                },
            }
        )

        self.assertIn("macro_geopolitics_overlay", normalized)
        overlay = normalized["macro_geopolitics_overlay"]
        self.assertEqual(overlay["regime_label"], "escalation")
        self.assertEqual(overlay["beneficiary_chains"], ["oil_shipping", "gold"])
        self.assertEqual(overlay["headwind_chains"], ["airlines", "high_beta_growth"])
        self.assertEqual(overlay["notes"], "Hormuz disruption risk repriced.")
        self.assertNotIn("extra_field", overlay)

    def test_normalize_request_drops_invalid_geopolitics_overlay(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "filter_profile": "month_end_event_support_transition",
                "macro_geopolitics_overlay": {
                    "regime_label": "headline_noise",
                    "beneficiary_chains": ["oil_shipping"],
                    "headwind_chains": ["airlines"],
                },
            }
        )

        self.assertNotIn("macro_geopolitics_overlay", normalized)

    def test_normalize_request_preserves_event_support_transition_profile(self) -> None:
        normalized = module_under_test.normalize_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-17",
                "analysis_time": "2026-04-16T15:25:00+08:00",
                "filter_profile": "month_end_event_support_transition",
            }
        )

        self.assertEqual(normalized["filter_profile"], "month_end_event_support_transition")
        self.assertEqual(normalized["keep_threshold"], 56.0)
        self.assertEqual(normalized["strict_top_pick_threshold"], 58.0)
        self.assertEqual(normalized["profile_settings"]["keep_threshold"], 56.0)
        self.assertEqual(normalized["profile_settings"]["strict_top_pick_threshold"], 58.0)

    def test_run_month_end_shortlist_preserves_profile_inside_compiled_runtime(self) -> None:
        captured: dict[str, object] = {}

        def fake_compiled_run(payload: dict, **_: object) -> dict:
            captured["compiled_internal_request"] = module_under_test._compiled.normalize_request(payload)
            return {
                "status": "ok",
                "request": captured["compiled_internal_request"],
                "filter_summary": {},
                "dropped": [],
                "top_picks": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
            }

        with (
            patch.object(module_under_test, "prepare_request_with_candidate_snapshots", side_effect=lambda payload, **__: payload),
            patch.object(module_under_test, "enrich_live_result_reporting", side_effect=lambda result, *_: result),
            patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run),
        ):
            result = module_under_test.run_month_end_shortlist(
                {
                    "template_name": "month_end_shortlist",
                    "target_date": "2026-04-17",
                    "analysis_time": "2026-04-16T15:25:00+08:00",
                    "filter_profile": "month_end_event_support_transition",
                }
            )

        self.assertEqual(result["request"]["filter_profile"], "month_end_event_support_transition")
        self.assertEqual(result["request"]["keep_threshold"], 56.0)
        self.assertEqual(result["request"]["strict_top_pick_threshold"], 58.0)


if __name__ == "__main__":
    unittest.main()
