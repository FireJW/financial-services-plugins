#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import earnings_momentum_discovery as module_under_test


class EarningsMomentumDiscoveryTests(unittest.TestCase):
    def test_normalize_event_candidate_preserves_upstream_chain_metadata(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "002463.SZ",
                "name": "沪电股份",
                "event_type": "price_hike",
                "event_strength": "strong",
                "chain_name": "pcb",
                "chain_role": "upstream_material",
                "benefit_type": "direct",
                "sources": [
                    {"source_type": "x_summary", "account": "Ariston_Macro", "summary": "PCB 上游材料/电子布涨价弹性更强"}
                ],
            }
        )

        self.assertEqual(candidate["ticker"], "002463.SZ")
        self.assertEqual(candidate["chain_name"], "pcb")
        self.assertEqual(candidate["chain_role"], "upstream_material")
        self.assertEqual(candidate["benefit_type"], "direct")
        self.assertEqual(candidate["source_roles"], ["summary_or_relay"])

    def test_compute_rumor_confidence_range_distinguishes_confirmed_vs_rumor_only(self) -> None:
        rumor_only = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "medium",
                "sources": [{"source_type": "market_rumor", "summary": "存在订单/合作传闻"}],
                "market_validation": {"volume_multiple_5d": 2.2, "breakout": True, "relative_strength": "strong"},
            }
        )
        confirmed = module_under_test.normalize_event_candidate(
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "sources": [
                    {"source_type": "official_filing", "summary": "一季报预告大幅增长"},
                    {"source_type": "company_response", "summary": "公司公告确认最新业绩预增"},
                ],
                "market_validation": {"volume_multiple_5d": 1.9, "breakout": True, "relative_strength": "strong"},
            }
        )

        rumor_range = module_under_test.compute_rumor_confidence_range(rumor_only)
        confirmed_range = module_under_test.compute_rumor_confidence_range(confirmed)

        self.assertEqual(rumor_range["label"], "medium")
        self.assertEqual(confirmed_range["label"], "high")

    def test_classify_market_validation_labels_strong_funds_entered_early(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "300857.SZ",
                "name": "协创数据",
                "event_type": "large_order",
                "event_strength": "strong",
                "market_validation": {
                    "volume_multiple_5d": 2.4,
                    "breakout": True,
                    "relative_strength": "strong",
                    "chain_resonance": True,
                },
            }
        )

        validation = module_under_test.classify_market_validation(candidate)

        self.assertEqual(validation["label"], "strong")
        self.assertIn("资金先行", validation["summary"])

    def test_assign_discovery_bucket_keeps_rumor_only_names_out_of_qualified(self) -> None:
        rumor_candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "sources": [{"source_type": "market_rumor", "summary": "传闻发酵"}],
                "market_validation": {"volume_multiple_5d": 2.5, "breakout": True, "relative_strength": "strong"},
            }
        )
        confirmed_candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            }
        )

        rumor_bucket = module_under_test.assign_discovery_bucket(rumor_candidate)
        confirmed_bucket = module_under_test.assign_discovery_bucket(confirmed_candidate)

        self.assertEqual(rumor_bucket, "watch")
        self.assertEqual(confirmed_bucket, "qualified")


if __name__ == "__main__":
    unittest.main()
