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

    def test_build_auto_discovery_candidates_extracts_structured_preview_events(self) -> None:
        assessed_candidates = [
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "sector": "optical",
                "volume_ratio": 1.8,
                "trend_template": {"trend_pass": True},
                "score_components": {"structured_catalyst_score": 12, "rs_and_leadership_score": 15},
                "price_snapshot": {"distance_to_high52_pct": 20.0, "rs90": 1169.07},
                "structured_catalyst_snapshot": {
                    "structured_catalyst_within_window": True,
                    "performance_preview": [
                        {"notice_date": "2026-04-14", "summary": "预计一季报净利润同比显著增长"}
                    ],
                    "structured_company_events": [
                        {"date": "2026-04-16", "event_type": "股东大会", "detail": "召开年度股东大会"}
                    ],
                },
            }
        ]

        rows = module_under_test.build_auto_discovery_candidates(assessed_candidates)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "000988.SZ")
        self.assertEqual(rows[0]["event_type"], "quarterly_preview")
        self.assertEqual(rows[0]["chain_name"], "optical")
        self.assertEqual(rows[0]["sources"][0]["source_type"], "official_filing")

    def test_build_x_style_discovery_candidates_extracts_direct_pick_and_logic_basket(self) -> None:
        batch_payload = {
            "subject_runs": [
                {
                    "subject": {"handle": "twikejin"},
                    "recommendation_ledger": [
                        {
                            "classification": "direct_pick",
                            "strength": "strong_direct",
                            "names": ["东山精密"],
                            "sector_or_chain": "electronic_cloth",
                            "catalyst_type": "earnings",
                            "thesis_excerpt": "东山精密Q1净利预增，核心股。",
                            "status_url": "https://x.com/twikejin/status/2041534482210242629",
                            "scored_names": [{"name": "东山精密", "ticker": "002384.SZ"}],
                        },
                        {
                            "classification": "logic_support",
                            "strength": "logic_support_high_conviction",
                            "names": [],
                            "suggested_basket_sector": "optical_interconnect",
                            "suggested_basket_core_candidates": ["新易盛", "中际旭创"],
                            "thesis_excerpt": "光模块/光互联——EML缺货的下游受益者。",
                            "status_url": "https://x.com/tuolaji2024/status/2042465436810559801",
                        },
                    ],
                }
            ]
        }

        rows = module_under_test.build_x_style_discovery_candidates(batch_payload)

        self.assertEqual(rows[0]["ticker"], "002384.SZ")
        self.assertEqual(rows[0]["event_type"], "earnings")
        self.assertEqual(rows[0]["chain_role"], "direct_pick")
        self.assertEqual(rows[0]["sources"][0]["account"], "twikejin")
        self.assertEqual(rows[1]["name"], "新易盛")
        self.assertEqual(rows[1]["chain_name"], "optical_interconnect")
        self.assertEqual(rows[1]["chain_role"], "logic_support")

    def test_build_x_style_discovery_candidates_accepts_single_run_payload(self) -> None:
        single_run = {
            "subject": {"handle": "twikejin"},
            "recommendation_ledger": [
                {
                    "classification": "direct_pick",
                    "strength": "strong_direct",
                    "names": ["东山精密"],
                    "sector_or_chain": "electronic_cloth",
                    "catalyst_type": "earnings",
                    "thesis_excerpt": "东山精密Q1净利预增，核心股。",
                    "status_url": "https://x.com/twikejin/status/2041534482210242629",
                    "scored_names": [{"name": "东山精密", "ticker": "002384.SZ"}],
                }
            ],
        }

        rows = module_under_test.build_x_style_discovery_candidates(single_run)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "002384.SZ")

    def test_response_denial_downgrades_rumor_to_track(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "sources": [
                    {"source_type": "market_rumor", "summary": "存在合作传闻"},
                    {"source_type": "x_summary", "summary": "公司回应：相关传闻不属实"},
                ],
                "market_validation": {"volume_multiple_5d": 2.5, "breakout": True, "relative_strength": "strong"},
            }
        )

        state = module_under_test.classify_event_state(candidate)
        usability = module_under_test.classify_trading_usability(candidate)
        bucket = module_under_test.assign_discovery_bucket(candidate)

        self.assertEqual(state["label"], "response_denied")
        self.assertEqual(usability["label"], "low")
        self.assertEqual(bucket, "track")

    def test_response_confirmation_can_upgrade_rumor_to_qualified(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "sources": [
                    {"source_type": "market_rumor", "summary": "存在合作传闻"},
                    {"source_type": "x_summary", "summary": "公司回应：相关合作属实"},
                ],
                "market_validation": {"volume_multiple_5d": 2.5, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
            }
        )

        state = module_under_test.classify_event_state(candidate)
        usability = module_under_test.classify_trading_usability(candidate)
        bucket = module_under_test.assign_discovery_bucket(candidate)

        self.assertEqual(state["label"], "response_confirmed")
        self.assertEqual(usability["label"], "high")
        self.assertEqual(bucket, "qualified")

    def test_official_confirmation_without_strong_validation_still_has_medium_usability(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 1.1, "breakout": False, "relative_strength": "normal"},
            }
        )

        state = module_under_test.classify_event_state(candidate)
        usability = module_under_test.classify_trading_usability(candidate)

        self.assertEqual(state["label"], "official_confirmed")
        self.assertEqual(usability["label"], "medium")

    def test_build_event_cards_merges_official_x_summary_and_response_for_same_ticker(self) -> None:
        rows = [
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [{"source_type": "official_filing", "summary": "一季报预告显示利润显著增长"}],
                    "market_validation": {"volume_multiple_5d": 1.8, "breakout": True, "relative_strength": "strong"},
                }
            ),
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "x_logic_signal",
                    "event_strength": "strong",
                    "chain_name": "optical",
                    "chain_role": "logic_support",
                    "benefit_type": "mapping",
                    "sources": [
                        {"source_type": "x_summary", "account": "Ariston_Macro", "summary": "市场把这次预告理解成板块盈利预期修复信号"},
                        {"source_type": "company_response", "summary": "公司回应：相关业绩预增信息属实"},
                    ],
                    "market_validation": {"volume_multiple_5d": 2.2, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                }
            ),
        ]

        cards = module_under_test.build_event_cards(rows)

        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["ticker"], "000988.SZ")
        self.assertEqual(card["primary_event_type"], "quarterly_preview")
        self.assertEqual(card["event_state"]["label"], "official_confirmed")
        self.assertEqual(card["trading_usability"]["label"], "high")
        self.assertEqual(card["source_count"], 3)
        self.assertIn("Ariston_Macro", card["source_accounts"])
        self.assertIn("official_filing_reference", card["source_roles"])
        self.assertIn("summary_or_relay", card["source_roles"])

    def test_build_event_cards_assigns_priority_score_and_why_now_summary(self) -> None:
        rows = [
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [
                        {"source_type": "official_filing", "summary": "一季报预告显示利润显著增长"},
                        {"source_type": "x_summary", "account": "Ariston_Macro", "summary": "板块盈利预期修复信号"},
                        {"source_type": "company_response", "summary": "公司回应：相关业绩预增信息属实"},
                    ],
                    "market_validation": {"volume_multiple_5d": 2.2, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                }
            )
        ]

        cards = module_under_test.build_event_cards(rows)

        self.assertGreater(cards[0]["priority_score"], 0)
        self.assertIn("official_confirmed", cards[0]["why_now"])
        self.assertIn("Ariston_Macro", cards[0]["why_now"])


if __name__ == "__main__":
    unittest.main()
