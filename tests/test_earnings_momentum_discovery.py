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

    def test_build_event_cards_adds_evidence_mix_urls_and_market_signal_summary(self) -> None:
        rows = [
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical_interconnect",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [
                        {
                            "source_type": "official_filing",
                            "date": "2026-04-16",
                            "summary": "一季报预告显示利润显著增长",
                            "status_url": "https://example.com/official/huagong-q1",
                        }
                    ],
                    "market_validation": {"volume_multiple_5d": 2.2, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                }
            ),
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "000988.SZ",
                    "name": "华工科技",
                    "event_type": "x_logic_signal",
                    "event_strength": "strong",
                    "chain_name": "optical_interconnect",
                    "chain_role": "logic_support",
                    "benefit_type": "mapping",
                    "sources": [
                        {
                            "source_type": "x_summary",
                            "account": "Ariston_Macro",
                            "summary": "板块把这次预告理解为业绩拐点确认",
                            "evidence_excerpt": "板块把这次预告理解为业绩拐点确认，叠加EML紧缺和算力光互联需求修复。",
                            "status_url": "https://x.com/Ariston_Macro/status/2044000000000000001",
                        }
                    ],
                    "market_validation": {"volume_multiple_5d": 2.4, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                }
            ),
        ]

        cards = module_under_test.build_event_cards(rows)

        self.assertEqual(cards[0]["evidence_mix"]["official_filing"], 1)
        self.assertEqual(cards[0]["evidence_mix"]["x_summary"], 1)
        self.assertIn("https://x.com/Ariston_Macro/status/2044000000000000001", cards[0]["source_urls"])
        self.assertTrue(any("Ariston_Macro" in item for item in cards[0]["key_evidence"]))
        self.assertIn("volume_5d=2.4x", cards[0]["market_signal_summary"])
        self.assertIn("optical_interconnect / midstream_manufacturing / direct", cards[0]["chain_path_summary"])

    def test_build_event_cards_synthesizes_phase_verdict_metrics_and_community_reaction(self) -> None:
        rows = [
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "300308.SZ",
                    "name": "中际旭创",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical_interconnect",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [
                        {
                            "source_type": "official_filing",
                            "date": "2026-04-14",
                            "summary": "公司将2026年第一季度报告披露时间提前至4月17日，市场普遍解读为业绩可能超预期。",
                            "status_url": "https://example.com/official/300308-schedule",
                        },
                        {
                            "source_type": "x_summary",
                            "account": "twikejin",
                            "published_at": "2026-04-16T13:22:00+00:00",
                            "summary": "9.4GW算力租赁、EML紧缺、光模块价格可能上行，今晚中际要发财报。",
                        },
                        {
                            "source_type": "x_summary",
                            "account": "tuolaji2024",
                            "published_at": "2026-04-10T04:51:21+00:00",
                            "summary": "EML缺货的下游受益者，已锁定产能的光模块厂利润弹性最大。",
                        },
                        {
                            "source_type": "x_summary",
                            "account": "dmjk001",
                            "published_at": "2026-04-16T14:18:53+00:00",
                            "summary": "中际旭创2026Q1交流takeaway：800G和1.6T产品Q1均放量攀升，后续有机会保持环比增长；毛利率通过硅光渗透、高端占比提升、提高良率，后续稳中有升。",
                        },
                    ],
                    "market_validation": {"volume_multiple_5d": 2.3, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                    "peer_tier_1": ["中际旭创", "新易盛"],
                    "peer_tier_2": ["天孚通信"],
                }
            )
        ]

        cards = module_under_test.build_event_cards(rows)

        self.assertEqual(cards[0]["event_phase"], "预期交易")
        self.assertEqual(cards[0]["expectation_verdict"], "市场押注超预期")
        self.assertTrue(any("9.4GW" in item for item in cards[0]["headline_metrics"]))
        self.assertTrue(any("800G" in item for item in cards[0]["headline_metrics"]))
        self.assertTrue(any("1.6T" in item for item in cards[0]["headline_metrics"]))
        self.assertIn("twikejin", cards[0]["community_reaction_summary"])
        self.assertIn("tuolaji2024", cards[0]["community_reaction_summary"])
        self.assertIn("dmjk001", cards[0]["community_reaction_summary"])
        self.assertEqual(cards[0]["community_conviction"], "high")
        self.assertIn("800G/1.6T放量", cards[0]["expectation_basis_summary"])
        self.assertIn("EML紧缺", cards[0]["expectation_basis_summary"])
        self.assertIn("毛利率改善", cards[0]["expectation_basis_summary"])
        self.assertIn("若财报兑现弱于这些线索", cards[0]["expectation_risk_summary"])
        self.assertEqual(cards[0]["trading_profile_bucket"], "稳健核心")
        self.assertIn("核心", cards[0]["trading_profile_reason"])
        self.assertIn("打法", cards[0]["trading_profile_playbook"])

    def test_classify_trading_profile_distinguishes_core_catchup_and_realization_risk(self) -> None:
        core_profile = module_under_test.classify_trading_profile(
            {
                "name": "中际旭创",
                "benefit_type": "direct",
                "chain_role": "midstream_manufacturing",
                "leaders": ["中际旭创", "新易盛"],
                "peer_tier_1": ["中际旭创", "新易盛"],
                "peer_tier_2": ["天孚通信"],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "high", "summary": "交易可用性高"},
                "market_validation_summary": {"label": "strong", "summary": "强资金先行"},
                "expectation_verdict": "市场押注超预期",
                "community_conviction": "high",
                "priority_score": 100,
            }
        )
        catchup_profile = module_under_test.classify_trading_profile(
            {
                "name": "天孚通信",
                "benefit_type": "mapping",
                "chain_role": "logic_support",
                "leaders": ["中际旭创", "新易盛"],
                "peer_tier_1": ["中际旭创", "新易盛"],
                "peer_tier_2": ["天孚通信"],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "medium", "summary": "交易可用性中等"},
                "market_validation_summary": {"label": "medium", "summary": "中等资金先行"},
                "expectation_verdict": "市场押注超预期",
                "community_conviction": "medium",
                "priority_score": 72,
            }
        )
        elastic_profile = module_under_test.classify_trading_profile(
            {
                "name": "沪电股份",
                "benefit_type": "direct",
                "chain_role": "midstream_manufacturing",
                "leaders": ["中际旭创", "新易盛"],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "官方预告",
                "event_state": {"label": "official_confirmed"},
                "trading_usability": {"label": "medium", "summary": "交易可用性中等"},
                "market_validation_summary": {"label": "medium", "summary": "中等资金先行"},
                "expectation_verdict": "符合预期",
                "community_conviction": "low",
                "priority_score": 75,
            }
        )
        elastic_leader_profile = module_under_test.classify_trading_profile(
            {
                "name": "新易盛",
                "benefit_type": "mapping",
                "chain_role": "logic_support",
                "leaders": ["中际旭创", "新易盛"],
                "peer_tier_1": ["中际旭创", "新易盛"],
                "peer_tier_2": ["天孚通信"],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "medium", "summary": "交易可用性中等"},
                "market_validation_summary": {"label": "medium", "summary": "中等资金先行"},
                "expectation_verdict": "市场押注超预期",
                "community_conviction": "medium",
                "priority_score": 68,
            }
        )
        realized_risk_profile = module_under_test.classify_trading_profile(
            {
                "name": "兆易创新",
                "benefit_type": "direct",
                "chain_role": "midstream_manufacturing",
                "leaders": ["兆易创新"],
                "peer_tier_1": ["兆易创新"],
                "peer_tier_2": ["深科技", "澜起科技"],
                "event_phase": "正式结果",
                "event_state": {"label": "official_confirmed"},
                "trading_usability": {"label": "medium", "summary": "交易可用性中等"},
                "market_validation_summary": {"label": "medium", "summary": "中等资金先行"},
                "expectation_verdict": "符合预期",
                "community_conviction": "low",
                "priority_score": 80,
            }
        )
        risk_profile = module_under_test.classify_trading_profile(
            {
                "name": "宁德时代",
                "benefit_type": "direct",
                "chain_role": "downstream_brand",
                "leaders": ["宁德时代", "赣锋锂业"],
                "peer_tier_1": ["宁德时代", "赣锋锂业"],
                "peer_tier_2": [],
                "event_phase": "正式结果",
                "event_state": {"label": "official_confirmed"},
                "trading_usability": {"label": "high", "summary": "交易可用性高"},
                "market_validation_summary": {"label": "strong", "summary": "强资金先行"},
                "expectation_verdict": "超预期",
                "community_conviction": "high",
                "priority_score": 96,
            }
        )

        self.assertEqual(core_profile["bucket"], "稳健核心")
        self.assertIn("核心", core_profile["reason"])
        self.assertEqual(catchup_profile["bucket"], "补涨候选")
        self.assertIn("补涨", catchup_profile["reason"])
        self.assertIn("扩散", catchup_profile["subtype"])
        self.assertEqual(elastic_profile["bucket"], "高弹性")
        self.assertIn("弹性", elastic_profile["reason"])
        self.assertIn("事件确认", elastic_profile["subtype"])
        self.assertEqual(elastic_leader_profile["bucket"], "高弹性")
        self.assertIn("攻击性", elastic_leader_profile["subtype"])
        self.assertEqual(realized_risk_profile["bucket"], "兑现风险最高")
        self.assertIn("兑现", realized_risk_profile["reason"])
        self.assertEqual(risk_profile["bucket"], "兑现风险最高")
        self.assertIn("兑现", risk_profile["reason"])
        self.assertIn("回踩确认", module_under_test.build_trading_profile_playbook(core_profile))
        self.assertIn("轮动", module_under_test.build_trading_profile_playbook(catchup_profile))
        self.assertIn("进攻", module_under_test.build_trading_profile_playbook(elastic_profile))
        self.assertIn("兑现", module_under_test.build_trading_profile_playbook(realized_risk_profile))

    def test_build_event_cards_merges_name_only_signal_into_ticker_backed_card(self) -> None:
        rows = [
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "300308.SZ",
                    "name": "中际旭创",
                    "event_type": "quarterly_preview",
                    "event_strength": "strong",
                    "chain_name": "optical_interconnect",
                    "chain_role": "midstream_manufacturing",
                    "benefit_type": "direct",
                    "sources": [{"source_type": "official_filing", "summary": "公司将一季报披露时间提前至4月17日。"}],
                    "market_validation": {"volume_multiple_5d": 2.3, "breakout": True, "relative_strength": "strong"},
                }
            ),
            module_under_test.normalize_event_candidate(
                {
                    "ticker": "",
                    "name": "中际旭创",
                    "event_type": "price_hike",
                    "event_strength": "medium",
                    "chain_name": "optical_interconnect",
                    "chain_role": "logic_support",
                    "benefit_type": "mapping",
                    "sources": [{"source_type": "x_summary", "account": "tuolaji2024", "summary": "EML缺货的下游受益者。"}],
                    "market_validation": {},
                }
            ),
        ]

        cards = module_under_test.build_event_cards(rows)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["ticker"], "300308.SZ")
        self.assertIn("tuolaji2024", cards[0]["source_accounts"])
        self.assertIn("midstream_manufacturing", cards[0]["chain_path_summary"])


    def test_to_int_safe_handles_non_numeric_strings(self) -> None:
        self.assertEqual(module_under_test.to_int_safe(42), 42)
        self.assertEqual(module_under_test.to_int_safe("85"), 85)
        self.assertEqual(module_under_test.to_int_safe("-"), 0)
        self.assertEqual(module_under_test.to_int_safe("N/A"), 0)
        self.assertEqual(module_under_test.to_int_safe(None), 0)
        self.assertEqual(module_under_test.to_int_safe("", default=5), 5)
        self.assertEqual(module_under_test.to_int_safe(0), 0)

    def test_to_float_safe_handles_non_numeric_strings(self) -> None:
        self.assertAlmostEqual(module_under_test.to_float_safe(1.5), 1.5)
        self.assertAlmostEqual(module_under_test.to_float_safe("2.0"), 2.0)
        self.assertAlmostEqual(module_under_test.to_float_safe("-"), 0.0)
        self.assertAlmostEqual(module_under_test.to_float_safe("N/A"), 0.0)
        self.assertAlmostEqual(module_under_test.to_float_safe(None), 0.0)

    def test_classify_trading_profile_market_bet_outperform_routes_to_elastic_not_gap(self) -> None:
        """Fix 1: 市场押注超预期 with weak validation should go to 高弹性, not 预期差最大."""
        profile = module_under_test.classify_trading_profile(
            {
                "name": "TestName",
                "benefit_type": "direct",
                "chain_role": "unknown",
                "leaders": [],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "low", "summary": "低"},
                "market_validation_summary": {"label": "weak", "summary": "弱"},
                "expectation_verdict": "市场押注超预期",
                "community_conviction": "low",
                "priority_score": 50,
            }
        )
        self.assertNotEqual(profile["bucket"], "预期差最大")

    def test_classify_trading_profile_low_conviction_alone_not_gap(self) -> None:
        """Fix 2: community_conviction == low alone should not trigger 预期差最大."""
        profile = module_under_test.classify_trading_profile(
            {
                "name": "TestName2",
                "benefit_type": "direct",
                "chain_role": "unknown",
                "leaders": [],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "low", "summary": "低"},
                "market_validation_summary": {"label": "medium", "summary": "中等"},
                "expectation_verdict": "符合预期",
                "community_conviction": "low",
                "priority_score": 40,
            }
        )
        self.assertNotEqual(profile["bucket"], "预期差最大")

    def test_classify_trading_profile_mapping_strong_validation_routes_to_elastic(self) -> None:
        """Fix 4: mapping + strong validation + high usability → 高弹性, not 补涨候选."""
        profile = module_under_test.classify_trading_profile(
            {
                "name": "MappingStrong",
                "benefit_type": "mapping",
                "chain_role": "midstream_manufacturing",
                "leaders": [],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "high", "summary": "高"},
                "market_validation_summary": {"label": "strong", "summary": "强"},
                "expectation_verdict": "市场押注超预期",
                "community_conviction": "medium",
                "priority_score": 70,
            }
        )
        self.assertEqual(profile["bucket"], "高弹性")
        self.assertIn("映射", profile["subtype"])

    def test_classify_trading_profile_final_fallback_is_catchup_not_gap(self) -> None:
        """Fix 5: final fallback with weak validation → 补涨候选, not 预期差最大."""
        profile = module_under_test.classify_trading_profile(
            {
                "name": "FallbackName",
                "benefit_type": "direct",
                "chain_role": "unknown",
                "leaders": [],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "low", "summary": "低"},
                "market_validation_summary": {"label": "weak", "summary": "弱"},
                "expectation_verdict": "符合预期",
                "community_conviction": "medium",
                "priority_score": 30,
            }
        )
        self.assertEqual(profile["bucket"], "补涨候选")
        self.assertIn("证据不足", profile["subtype"])

    def test_classify_trading_profile_genuine_gap_has_evidence_strength(self) -> None:
        """Fix 3: genuine 预期差最大 entries carry evidence_strength marker."""
        profile = module_under_test.classify_trading_profile(
            {
                "name": "GapName",
                "benefit_type": "direct",
                "chain_role": "unknown",
                "leaders": [],
                "peer_tier_1": [],
                "peer_tier_2": [],
                "event_phase": "预期交易",
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "low", "summary": "低"},
                "market_validation_summary": {"label": "weak", "summary": "弱"},
                "expectation_verdict": "暂无一致预期",
                "community_conviction": "low",
                "priority_score": 30,
            }
        )
        self.assertEqual(profile["bucket"], "预期差最大")
        self.assertIn("evidence_strength", profile)


if __name__ == "__main__":
    unittest.main()
