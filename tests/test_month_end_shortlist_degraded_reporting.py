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


class MonthEndShortlistDegradedReportingTests(unittest.TestCase):
    def _build_enriched_for_decision_flow(self) -> dict[str, object]:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "001309.SZ", "name": "德明利", "drop_reason": "no_structured_catalyst_within_window"},
                {"ticker": "002460.SZ", "name": "赣锋锂业", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "001309.SZ",
                "name": "德明利",
                "keep": False,
                "scores": {"adjusted_total_score": 65.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {"close": 118.0, "ma20": 112.0, "ma50": 108.0, "ma150": 95.0, "ma200": 88.0, "rsi14": 63.0, "rs90": 104.0},
                "trend_template": {"trend_pass": True, "passed_count": 8},
                "structured_catalyst_snapshot": {"earnings_events": []},
                "hard_filter_failures": ["no_structured_catalyst_within_window"],
            },
            {
                "ticker": "002460.SZ",
                "name": "赣锋锂业",
                "keep": False,
                "scores": {"adjusted_total_score": 60.0},
                "score_components": {
                    "trend_template_score": 24.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 17.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {"close": 45.0, "ma20": 42.0, "ma50": 40.0, "ma150": 37.0, "ma200": 35.0, "rsi14": 58.0, "rs90": 101.0},
                "trend_template": {"trend_pass": True, "passed_count": 8},
                "structured_catalyst_snapshot": {
                    "earnings_events": [
                        {"event_date": "2026-04-16", "headline": "一季报业绩预告", "kind": "quarterly_preview"}
                    ]
                },
                "hard_filter_failures": [],
            },
        ]
        discovery_candidates = [
            {
                "ticker": "002460.SZ",
                "name": "赣锋锂业",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "lithium_chain",
                "chain_role": "midstream_material",
                "benefit_type": "direct",
                "sources": [{"source_type": "official_filing", "summary": "公司披露一季报业绩预告，预计净利润160000万元至210000万元，同比扭亏。"}],
                "market_validation": {"volume_multiple_5d": 2.1, "breakout": True, "relative_strength": "strong"},
            }
        ]
        return module_under_test.enrich_live_result_reporting(result, [], assessed_candidates, discovery_candidates)

    def _build_enriched_for_geopolitics_overlay(self) -> dict[str, object]:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "request": {
                "macro_geopolitics_overlay": {
                    "regime_label": "escalation",
                    "confidence": "medium",
                    "headline_risk": "high",
                    "beneficiary_chains": ["oil_shipping"],
                    "headwind_chains": ["airlines"],
                    "notes": "Hormuz disruption risk repriced.",
                }
            },
            "dropped": [
                {"ticker": "601975.SS", "name": "招商南油", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
        }
        assessed_candidates = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "keep": False,
                "scores": {"adjusted_total_score": 60.0},
                "score_components": {
                    "adjusted_total_score": 60.0,
                    "trend_template_score": 24.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 14.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {"close": 5.8, "ma20": 5.5, "ma50": 5.3, "ma150": 4.9, "ma200": 4.5, "rsi14": 58.0, "rs90": 102.0},
                "trend_template": {"trend_pass": True, "passed_count": 8},
                "structured_catalyst_snapshot": {
                    "structured_company_events": [
                        {"date": "2026-04-21", "event_type": "油运景气跟踪"}
                    ]
                },
                "trade_card": {"watch_action": "等强势承接", "invalidation": "跌破关键均线"},
                "hard_filter_failures": [],
            }
        ]
        discovery_candidates = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "event_type": "structured_catalyst",
                "event_strength": "moderate",
                "chain_name": "oil_shipping",
                "chain_role": "direct_beneficiary",
                "benefit_type": "direct",
                "sources": [{"source_type": "x_summary", "account": "macroalpha", "summary": "油运受益于航线风险溢价回升"}],
                "market_validation": {"volume_multiple_5d": 1.7, "breakout": True, "relative_strength": "strong"},
            }
        ]
        return module_under_test.enrich_live_result_reporting(result, [], assessed_candidates, discovery_candidates)

    def _build_enriched_for_geopolitics_candidate(self) -> dict[str, object]:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "request": {
                "macro_geopolitics_candidate_input": {
                    "news_signals": [
                        {
                            "headline": "Shipping disruption fears rise",
                            "summary": "Hormuz disruption risk repriced.",
                            "direction_hint": "escalation",
                        }
                    ],
                    "x_signals": [
                        {
                            "account": "MacroDesk",
                            "summary": "Energy traders lean toward renewed supply fear.",
                            "direction_hint": "escalation",
                        }
                    ],
                    "market_signals": {
                        "oil": "up",
                        "gold": "up",
                        "shipping": "up",
                        "risk_style": "risk_off",
                        "airlines": "down",
                    },
                }
            },
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
        }
        assessed_candidates = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "keep": False,
                "scores": {"adjusted_total_score": 60.0},
                "score_components": {
                    "adjusted_total_score": 60.0,
                    "trend_template_score": 24.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 14.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {"close": 5.8, "ma20": 5.5, "ma50": 5.3, "ma150": 4.9, "ma200": 4.5, "rsi14": 58.0, "rs90": 102.0},
                "trend_template": {"trend_pass": True, "passed_count": 8},
                "structured_catalyst_snapshot": {
                    "structured_company_events": [
                        {"date": "2026-04-21", "event_type": "油运景气跟踪"}
                    ]
                },
                "trade_card": {"watch_action": "等强势承接", "invalidation": "跌破关键均线"},
                "hard_filter_failures": [],
            }
        ]
        discovery_candidates = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "event_type": "structured_catalyst",
                "event_strength": "moderate",
                "chain_name": "oil_shipping",
                "chain_role": "direct_beneficiary",
                "benefit_type": "direct",
                "sources": [{"source_type": "x_summary", "account": "macroalpha", "summary": "油运受益于航线风险溢价回升"}],
                "market_validation": {"volume_multiple_5d": 1.7, "breakout": True, "relative_strength": "strong"},
            }
        ]
        return module_under_test.enrich_live_result_reporting(result, [], assessed_candidates, discovery_candidates)

    def test_enrich_live_result_reporting_adds_decision_flow_cards(self) -> None:
        enriched = self._build_enriched_for_decision_flow()

        self.assertIn("decision_flow", enriched)
        self.assertEqual([item["ticker"] for item in enriched["decision_flow"]], ["002460.SZ", "001309.SZ"])

        first = enriched["decision_flow"][0]
        self.assertEqual(first["action"], "继续观察")
        self.assertEqual(first["trading_profile_bucket"], "高弹性")
        self.assertEqual(first["keep_threshold"], 70.0)
        self.assertEqual(first["gap"], -10.0)
        self.assertEqual(first["chain_name"], "lithium_chain")
        self.assertEqual(first["chain_role"], "midstream_material")
        self.assertIsNone(first["trigger_overrides"])
        self.assertIn("评分", first["conclusion"])
        self.assertIn("均线多头结构", first["watch_points"]["technical"])
        self.assertIn("upgrade", first["triggers"])
        self.assertIn("operation_reminder", first)

    def test_decision_flow_triggers_include_upgrade_downgrade_and_event_risk_when_available(self) -> None:
        enriched = self._build_enriched_for_decision_flow()
        card = enriched["decision_flow"][0]

        self.assertIn("评分从 60.0 修复至 70.0+", card["triggers"]["upgrade"])
        self.assertTrue(card["triggers"]["downgrade"])
        self.assertIn("实际净利润低于预告下限 160000 万元", card["triggers"]["event_risk"])

    def test_enriches_result_with_blocked_candidate_summary_and_report_section(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "bars_fetch_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "bars_fetch_failed"},
                {"ticker": "603000.SS", "name": "人民网", "drop_reason": "trend_template_failed"},
            ],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        failures = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "sector": "有色",
                "board": "main_board",
                "bars_fetch_error": "bars_fetch_failed for `601600.SS`: boom",
            },
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "sector": "液冷",
                "board": "main_board",
                "bars_fetch_error": "bars_fetch_failed for `002837.SZ`: boom",
            },
        ]

        enriched = module_under_test.enrich_degraded_live_result(result, failures)

        self.assertEqual(enriched["filter_summary"]["blocked_candidate_count"], 2)
        self.assertEqual(enriched["filter_summary"]["bars_fetch_failed_tickers"], ["601600.SS", "002837.SZ"])
        self.assertEqual(len(enriched["blocked_candidates"]), 2)
        self.assertEqual(enriched["dropped"][0]["sector"], "有色")
        self.assertIn("## Blocked Candidates", enriched["report_markdown"])
        self.assertIn("601600.SS", enriched["report_markdown"])

    def test_report_includes_global_cache_baseline_metadata(self) -> None:
        result = {
            "filter_summary": {
                "cache_baseline_trade_date": "2026-04-18",
                "cache_baseline_only": True,
                "live_supplement_status": "unavailable",
            },
            "report_markdown": "# Month-End Shortlist Report: 2026-04-20\n",
            "top_picks": [],
            "dropped": [],
        }

        enriched = module_under_test.enrich_degraded_live_result(result, [])

        self.assertIn("数据基线：最近交易日盘后缓存（2026-04-18）", enriched["report_markdown"])
        self.assertIn("实时补充：不可用，沿用缓存基线", enriched["report_markdown"])

    def test_enrich_degraded_live_result_is_noop_without_failures(self) -> None:
        result = {
            "filter_summary": {"kept_count": 1},
            "dropped": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_degraded_live_result(result, [])

        self.assertEqual(enriched["filter_summary"]["kept_count"], 1)
        self.assertNotIn("blocked_candidate_count", enriched["filter_summary"])
        self.assertNotIn("blocked_candidates", enriched)
        self.assertNotIn("## Blocked Candidates", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_drop_reason_summary_and_report_section(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "price_below_floor"},
            ],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [])

        self.assertEqual(enriched["filter_summary"]["drop_reason_counts"]["price_below_floor"], 2)
        self.assertEqual(enriched["filter_summary"]["drop_reason_counts"]["trend_template_failed"], 1)
        self.assertIn("## Dropped Candidates", enriched["report_markdown"])
        self.assertIn("601600.SS", enriched["report_markdown"])
        self.assertIn("price_below_floor", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_diagnostic_scorecard_when_no_top_picks(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "keep": False,
                "scores": {"adjusted_total_score": 42.0},
                "score_components": {
                    "trend_template_score": 21.88,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": ["price_below_floor", "trend_template_failed"],
            },
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 66.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": ["score_below_keep_threshold"],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        self.assertEqual(enriched["filter_summary"]["diagnostic_scorecard_count"], 2)
        self.assertEqual(len(enriched["diagnostic_scorecard"]), 2)
        self.assertEqual(enriched["diagnostic_scorecard"][1]["ticker"], "002837.SZ")
        self.assertEqual(enriched["diagnostic_scorecard"][1]["score"], 66.0)
        self.assertEqual(enriched["diagnostic_scorecard"][1]["keep_threshold_gap"], -4.0)
        self.assertIn("## Diagnostic Scorecard", enriched["report_markdown"])
        self.assertIn("002837.SZ", enriched["report_markdown"])
        self.assertIn("score=`66.0`", enriched["report_markdown"])
        self.assertIn("gap=`-4.0`", enriched["report_markdown"])
        self.assertIn("trend=`25.0`", enriched["report_markdown"])
        self.assertIn("score_below_keep_threshold", enriched["report_markdown"])

    def test_enrich_live_result_reporting_renders_decision_flow_and_removes_event_board_and_chain_map(self) -> None:
        enriched = self._build_enriched_for_decision_flow()
        report = enriched["report_markdown"]

        self.assertIn("## 决策流", report)
        self.assertNotIn("## Event Board", report)
        self.assertNotIn("## Chain Map", report)
        self.assertIn("## Decision Factors", report)
        self.assertIn("## Event Cards", report)
        self.assertLess(report.index("## 直接可执行"), report.index("## 决策流"))
        self.assertLess(report.index("## 决策流"), report.index("## Event Cards"))

    def test_decision_flow_card_marks_cache_baseline_only_state(self) -> None:
        card = {
            "ticker": "002384.SZ",
            "name": "东山精密",
            "action": "继续观察",
            "fallback_cache_only": False,
            "bars_source": "eastmoney_cache",
            "cache_baseline_only": True,
            "trading_profile_bucket": "补涨候选",
        }

        reminder = module_under_test.build_decision_flow_card(
            card,
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
            geopolitics_overlay=None,
        )["operation_reminder"]

        self.assertIn("数据状态：仍沿用缓存基线", reminder)

    def test_enrich_live_result_reporting_renders_response_state_for_discovery_candidates(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "chain_name": "chip_design",
                "chain_role": "logic_support",
                "benefit_type": "mapping",
                "sources": [
                    {"source_type": "market_rumor", "summary": "市场传闻"},
                    {"source_type": "x_summary", "summary": "公司回应：相关传闻不属实"},
                ],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            }
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates)

        self.assertIn("事件状态", enriched["report_markdown"])
        self.assertIn("response_denied", enriched["report_markdown"])
        self.assertIn("交易可用性", enriched["report_markdown"])

    def test_enrich_live_result_reporting_renders_event_cards_section(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "300308.SZ",
                "name": "中际旭创",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "optical_interconnect",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [
                    {"source_type": "official_filing", "summary": "公司将2026年第一季度报告披露时间提前至4月17日，市场普遍解读为业绩可能超预期。"},
                    {"source_type": "x_summary", "account": "twikejin", "summary": "9.4GW算力租赁、EML紧缺、光模块价格可能上行，今晚中际要发财报。"},
                    {"source_type": "x_summary", "account": "tuolaji2024", "summary": "EML缺货的下游受益者，已锁定产能的光模块厂利润弹性最大。"},
                ],
                "market_validation": {"volume_multiple_5d": 2.3, "breakout": True, "relative_strength": "strong", "chain_resonance": True},
                "peer_tier_1": ["中际旭创", "新易盛"],
                "peer_tier_2": ["天孚通信"],
            },
        ]
        discovery_context = {
            "chain_map": [
                {
                    "chain_name": "optical_interconnect",
                    "leaders": ["中际旭创", "新易盛"],
                    "tier_1": ["中际旭创", "新易盛"],
                    "tier_2": ["天孚通信"],
                }
            ]
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates, discovery_context)

        self.assertIn("## Event Cards", enriched["report_markdown"])
        self.assertIn("阶段", enriched["report_markdown"])
        self.assertIn("预期判断", enriched["report_markdown"])
        self.assertIn("关键数据", enriched["report_markdown"])
        self.assertIn("社区反应", enriched["report_markdown"])
        self.assertIn("预期驱动", enriched["report_markdown"])
        self.assertIn("兑现风险", enriched["report_markdown"])
        self.assertIn("priority_score", enriched["report_markdown"])
        self.assertIn("市场押注超预期", enriched["report_markdown"])
        self.assertIn("market_signal_summary", enriched["report_markdown"])
        self.assertIn("chain_path_summary", enriched["report_markdown"])
        self.assertIn("key_evidence", enriched["report_markdown"])
        self.assertIn("判断:", enriched["report_markdown"])
        self.assertIn("用法:", enriched["report_markdown"])
        self.assertIn("稳健核心", enriched["report_markdown"])
        self.assertNotIn("交易属性分层", enriched["report_markdown"])
        self.assertNotIn("交易属性细分", enriched["report_markdown"])
        self.assertNotIn("分层依据", enriched["report_markdown"])
        self.assertNotIn("交易打法:", enriched["report_markdown"])
        self.assertNotIn("  - 一线:", enriched["report_markdown"])
        self.assertNotIn("  - 二线:", enriched["report_markdown"])

    def test_enrich_live_result_reporting_realigns_chain_by_known_context_membership(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "300750.SZ",
                "name": "宁德时代",
                "event_type": "price_hike",
                "event_strength": "medium",
                "chain_name": "ai_infra",
                "chain_role": "direct_pick",
                "benefit_type": "direct",
                "sources": [{"source_type": "x_summary", "account": "twikejin", "summary": "宁德时代业绩太硬，带着整个新能源产业链修复。"}],
                "market_validation": {},
            },
        ]
        discovery_context = {
            "chain_map": [
                {
                    "chain_name": "ai_infra",
                    "leaders": ["协创数据", "华工科技"],
                    "tier_1": ["协创数据", "华工科技"],
                    "tier_2": ["润泽科技", "数据港"],
                    "all_candidates": ["协创数据", "华工科技", "润泽科技", "数据港"],
                },
                {
                    "chain_name": "lithium_chain",
                    "leaders": ["宁德时代", "赣锋锂业"],
                    "tier_1": ["宁德时代", "赣锋锂业"],
                    "tier_2": [],
                    "all_candidates": ["宁德时代", "赣锋锂业"],
                },
            ]
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates, discovery_context)

        self.assertEqual(enriched["event_cards"][0]["chain_name"], "lithium_chain")
        self.assertIn("lithium_chain", enriched["report_markdown"])

    def test_enrich_live_result_reporting_recomputes_trading_profile_after_chain_context_enrichment(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "ai_infra",
                "chain_role": "direct_pick",
                "benefit_type": "direct",
                "sources": [
                    {"source_type": "official_filing", "summary": "公司将于4月27日披露一季报。"},
                ],
                "market_validation": {"volume_multiple_5d": 1.8, "breakout": True, "relative_strength": "strong"},
            },
        ]
        discovery_context = {
            "chain_map": [
                {
                    "chain_name": "ai_infra",
                    "leaders": ["协创数据", "华工科技"],
                    "tier_1": ["协创数据", "华工科技"],
                    "tier_2": ["润泽科技", "数据港"],
                    "all_candidates": ["协创数据", "华工科技", "润泽科技", "数据港"],
                }
            ]
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates, discovery_context)

        self.assertEqual(enriched["event_cards"][0]["trading_profile_bucket"], "稳健核心")
        self.assertIn("稳健核心", enriched["report_markdown"])
        self.assertIn("华工科技", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_near_miss_candidates(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "keep": False,
                "scores": {"adjusted_total_score": 55.88},
                "score_components": {
                    "trend_template_score": 21.88,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": ["price_below_floor", "trend_template_failed"],
            },
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 57.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": [],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        self.assertEqual(enriched["filter_summary"]["near_miss_candidate_count"], 1)
        self.assertEqual(len(enriched["near_miss_candidates"]), 1)
        self.assertEqual(enriched["near_miss_candidates"][0]["ticker"], "002837.SZ")
        self.assertIn("## Near Miss Candidates", enriched["report_markdown"])
        self.assertIn("002837.SZ", enriched["report_markdown"])

    def test_enrich_live_result_reporting_assigns_midday_status_labels(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "keep": False,
                "scores": {"adjusted_total_score": 55.88},
                "score_components": {
                    "trend_template_score": 21.88,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": ["price_below_floor", "trend_template_failed"],
            },
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 57.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": [],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        diagnostic = {item["ticker"]: item for item in enriched["diagnostic_scorecard"]}
        self.assertEqual(diagnostic["601600.SS"]["midday_status"], "blocked")
        self.assertEqual(diagnostic["002837.SZ"]["midday_status"], "near_miss")
        self.assertEqual(enriched["near_miss_candidates"][0]["midday_status"], "near_miss")
        self.assertIn("status=`blocked`", enriched["report_markdown"])
        self.assertIn("status=`near_miss`", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_midday_action_summary(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "keep": False,
                "scores": {"adjusted_total_score": 55.88},
                "score_components": {
                    "trend_template_score": 21.88,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": ["price_below_floor", "trend_template_failed"],
            },
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 57.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "hard_filter_failures": [],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        self.assertEqual(enriched["midday_action_summary"][0]["action"], "不执行")
        self.assertEqual(enriched["midday_action_summary"][1]["action"], "继续观察")
        self.assertIn("## 午盘操作建议摘要", enriched["report_markdown"])
        self.assertIn("不执行", enriched["report_markdown"])
        self.assertIn("继续观察", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_qualified_action_summary_from_top_picks(self) -> None:
        result = {
            "filter_summary": {"kept_count": 3, "keep_threshold": 70.0},
            "dropped": [],
            "top_picks": [
                {
                    "ticker": "001309.SZ",
                    "name": "德明利",
                    "score": 90.0,
                    "selection_mode": "strict",
                    "hard_filter_failures": [],
                },
                {
                    "ticker": "002460.SZ",
                    "name": "赣锋锂业",
                    "score": 90.0,
                    "selection_mode": "strict",
                    "hard_filter_failures": [],
                },
            ],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [])

        self.assertEqual(len(enriched["midday_action_summary"]), 2)
        self.assertEqual(enriched["midday_action_summary"][0]["status"], "qualified")
        self.assertEqual(enriched["midday_action_summary"][0]["action"], "可执行")
        self.assertIn("## 午盘操作建议摘要", enriched["report_markdown"])
        self.assertIn("可执行", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_near_miss_decision_factors(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 57.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {
                    "close": 105.14,
                    "ma20": 95.59,
                    "ma50": 100.72,
                    "ma150": 88.18,
                    "ma200": 76.64,
                    "ma200_slope_20d": 6.707,
                    "rsi14": 58.2,
                    "rs90": 1072.44,
                    "distance_to_high52_pct": 10.37,
                    "distance_from_low52_pct": 345.51,
                    "avg_turnover_20d": 4097572416.94,
                },
                "trend_template": {
                    "passed_count": 8,
                    "trend_pass": True,
                },
                "structured_catalyst_snapshot": {
                    "structured_catalyst_within_window": True,
                    "earnings_events": [
                        {"date": "2026-04-21", "event_type": "年报预披露", "detail": "于2026-04-21披露2025年年报"}
                    ],
                },
                "trade_card": {
                    "watch_action": "等回踩确认",
                    "invalidation": "跌破关键均线",
                },
                "hard_filter_failures": [],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        self.assertIn("decision_factors", enriched)
        self.assertEqual(len(enriched["decision_factors"]["near_miss"]), 1)
        factor = enriched["decision_factors"]["near_miss"][0]
        self.assertEqual(factor["ticker"], "002837.SZ")
        self.assertEqual(factor["action"], "继续观察")
        self.assertIn("均线", factor["technical_summary"])
        self.assertIn("2026-04-21", factor["event_summary"])
        self.assertIn("继续观察", factor["logic_summary"])
        self.assertIn("## Decision Factors", enriched["report_markdown"])
        self.assertIn("### 继续观察", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_blocked_decision_factors(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "601600.SS", "name": "中国铝业", "drop_reason": "price_below_floor,trend_template_failed"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "keep": False,
                "scores": {"adjusted_total_score": 55.88},
                "score_components": {
                    "trend_template_score": 21.88,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 15.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {
                    "close": 12.34,
                    "ma20": 12.9,
                    "ma50": 13.4,
                    "ma150": 14.2,
                    "ma200": 15.1,
                    "rsi14": 41.0,
                },
                "structured_catalyst_snapshot": {
                    "structured_catalyst_within_window": False,
                    "earnings_events": [],
                },
                "hard_filter_failures": ["price_below_floor", "trend_template_failed"],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        self.assertEqual(len(enriched["decision_factors"]["blocked"]), 1)
        factor = enriched["decision_factors"]["blocked"][0]
        self.assertEqual(factor["action"], "不执行")
        self.assertIn("price_below_floor", factor["logic_summary"])
        self.assertIn("## Decision Factors", enriched["report_markdown"])
        self.assertIn("### 不执行", enriched["report_markdown"])

    def test_enrich_live_result_reporting_adds_qualified_decision_factors(self) -> None:
        result = {
            "filter_summary": {"kept_count": 1, "keep_threshold": 70.0},
            "dropped": [],
            "top_picks": [
                {
                    "ticker": "001309.SZ",
                    "name": "德明利",
                    "score": 90.0,
                    "selection_mode": "strict",
                    "hard_filter_failures": [],
                    "price": 447.24,
                    "price_paths": {"base": [465.13, 483.02]},
                    "trade_card": {"watch_action": "回踩不破可继续拿", "invalidation": "跌破429.35"},
                    "structured_catalyst_within_window": True,
                    "scheduled_earnings_date": "2026-04-30",
                    "score_components": {
                        "trend_template_score": 25.0,
                        "rs_and_leadership_score": 15.0,
                        "structured_catalyst_score": 15.0,
                        "liquidity_and_participation_score": 10.0,
                    },
                }
            ],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [])

        self.assertEqual(len(enriched["decision_factors"]["qualified"]), 1)
        factor = enriched["decision_factors"]["qualified"][0]
        self.assertEqual(factor["action"], "可执行")
        self.assertIn("可执行", factor["logic_summary"])
        self.assertIn("2026-04-30", factor["event_summary"])
        self.assertIn("## Decision Factors", enriched["report_markdown"])
        self.assertIn("### 可执行", enriched["report_markdown"])

    def test_enrich_live_result_reporting_caps_qualified_decision_factors_at_top10(self) -> None:
        result = {
            "filter_summary": {"kept_count": 12, "keep_threshold": 70.0},
            "dropped": [],
            "top_picks": [
                {
                    "ticker": f"{i:06d}.SZ",
                    "name": f"Name{i}",
                    "score": 90.0 - i,
                    "selection_mode": "strict",
                    "hard_filter_failures": [],
                }
                for i in range(1, 13)
            ],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [])

        self.assertEqual(len(enriched["decision_factors"]["qualified"]), 10)
        self.assertIn("000001.SZ", enriched["report_markdown"])
        self.assertIn("000010.SZ", enriched["report_markdown"])
        self.assertNotIn("000011.SZ", enriched["report_markdown"])

    def test_qualified_decision_factor_includes_trade_layer_and_likely_next(self) -> None:
        result = {
            "filter_summary": {"kept_count": 1, "keep_threshold": 70.0},
            "dropped": [],
            "top_picks": [
                {
                    "ticker": "001309.SZ",
                    "name": "德明利",
                    "score": 90.0,
                    "selection_mode": "strict",
                    "hard_filter_failures": [],
                    "price": 447.24,
                    "price_paths": {"base": [465.13, 483.02]},
                    "trade_card": {"watch_action": "回踩不破可继续拿", "invalidation": "跌破429.35"},
                    "structured_catalyst_within_window": True,
                    "scheduled_earnings_date": "2026-04-30",
                    "score_components": {
                        "trend_template_score": 25.0,
                        "rs_and_leadership_score": 15.0,
                        "structured_catalyst_score": 15.0,
                        "liquidity_and_participation_score": 10.0,
                    },
                    "price_snapshot": {
                        "close": 447.24,
                        "ma20": 430.0,
                        "ma50": 410.0,
                        "ma150": 360.0,
                        "ma200": 330.0,
                        "ma200_slope_20d": 10.0,
                        "rsi14": 62.0,
                        "rs90": 2478.67,
                    },
                }
            ],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, [], [])
        factor = enriched["decision_factors"]["qualified"][0]

        self.assertIn("likely_next_summary", factor)
        self.assertIn("trade_layer_summary", factor)
        self.assertIn("## Decision Factors", enriched["report_markdown"])
        self.assertIn("下一步推演", enriched["report_markdown"])
        self.assertIn("交易层", enriched["report_markdown"])

    def test_near_miss_decision_factor_includes_likely_next_and_watch_items(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "002837.SZ", "name": "英维克", "drop_reason": "score_below_keep_threshold"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "002837.SZ",
                "name": "英维克",
                "keep": False,
                "scores": {"adjusted_total_score": 57.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 13.0,
                    "liquidity_and_participation_score": 4.0,
                },
                "price_snapshot": {
                    "close": 105.14,
                    "ma20": 95.59,
                    "ma50": 100.72,
                    "ma150": 88.18,
                    "ma200": 76.64,
                    "ma200_slope_20d": 6.707,
                    "rsi14": 58.2,
                    "rs90": 1072.44,
                    "distance_to_high52_pct": 10.37,
                    "distance_from_low52_pct": 345.51,
                    "avg_turnover_20d": 4097572416.94,
                },
                "trend_template": {"passed_count": 8, "trend_pass": True},
                "structured_catalyst_snapshot": {
                    "structured_catalyst_within_window": True,
                    "earnings_events": [{"date": "2026-04-21", "event_type": "年报预披露"}],
                },
                "trade_card": {"watch_action": "等回踩确认", "invalidation": "跌破关键均线"},
                "hard_filter_failures": [],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)
        factor = enriched["decision_factors"]["near_miss"][0]

        self.assertIn("likely_next_summary", factor)
        self.assertGreaterEqual(len(factor["next_watch_items"]), 1)
        self.assertIn("下一步推演", enriched["report_markdown"])
        self.assertIn("观察点", enriched["report_markdown"])

    def test_decision_factors_near_miss_can_source_from_rendered_t3(self) -> None:
        enriched = {
            "top_picks": [],
            "near_miss_candidates": [],
            "diagnostic_scorecard": [
                {
                    "ticker": "300476.SZ",
                    "name": "胜宏科技",
                    "score": 67.88,
                    "keep_threshold_gap": -2.12,
                    "midday_status": "near_miss",
                    "price_snapshot": {
                        "close": 120.0,
                        "ma20": 110.0,
                        "ma50": 100.0,
                        "ma150": 90.0,
                        "ma200": 80.0,
                        "ma200_slope_20d": 3.0,
                        "rsi14": 62.0,
                        "rs90": 1500.0,
                    },
                    "trend_template": {"passed_count": 8, "trend_pass": True},
                    "structured_catalyst_snapshot": {
                        "structured_catalyst_within_window": True,
                        "structured_company_events": [
                            {"date": "2026-04-21", "event_type": "股东大会"}
                        ],
                    },
                    "trade_card": {"watch_action": "等强势承接", "invalidation": "跌破关键均线"},
                    "hard_filter_failures": [],
                    "tier_tags": [],
                }
            ],
            "tier_output": {
                "T1": [],
                "T2": [],
                "T3": [
                    {
                        "ticker": "300476.SZ",
                        "name": "胜宏科技",
                        "score": 67.88,
                        "wrapper_tier": "T3",
                        "tier_tags": ["coverage_fill"],
                        "track_name": "chinext",
                    }
                ],
                "T4": [],
            },
        }

        factors = module_under_test.build_decision_factors_from_result(enriched)

        self.assertEqual(len(factors["near_miss"]), 1)
        factor = factors["near_miss"][0]
        self.assertEqual(factor["ticker"], "300476.SZ")
        self.assertIn("继续观察", factor["logic_summary"])

    def test_blocked_decision_factor_mentions_event_support_weakness_when_missing(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "dropped": [
                {"ticker": "001309.SZ", "name": "德明利", "drop_reason": "no_structured_catalyst_within_window"},
            ],
            "top_picks": [],
            "scorecard": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
        }
        assessed_candidates = [
            {
                "ticker": "001309.SZ",
                "name": "德明利",
                "keep": False,
                "scores": {"adjusted_total_score": 65.0},
                "score_components": {
                    "trend_template_score": 25.0,
                    "rs_and_leadership_score": 15.0,
                    "structured_catalyst_score": 0.0,
                    "liquidity_and_participation_score": 5.0,
                },
                "price_snapshot": {
                    "close": 447.24,
                    "ma20": 430.0,
                    "ma50": 410.0,
                    "ma150": 360.0,
                    "ma200": 330.0,
                    "rsi14": 80.4,
                },
                "structured_catalyst_snapshot": {
                    "structured_catalyst_within_window": False,
                    "earnings_events": [],
                },
                "hard_filter_failures": ["no_structured_catalyst_within_window"],
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)
        factor = enriched["decision_factors"]["blocked"][0]

        self.assertIn("事件驱动支持偏弱", factor["event_summary"])
        self.assertIn("关键事件", enriched["report_markdown"])
        self.assertIn("事件驱动支持偏弱", enriched["report_markdown"])


    def _build_enriched_with_event_cards(self):
        """Helper to build enriched result with at least one event card for layout testing."""
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "000001.SZ",
                "name": "TestStock",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "TestChain",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [
                    {"source_type": "official_filing", "summary": "正式业绩预告"},
                    {"source_type": "x_summary", "account": "account1", "summary": "看多"},
                    {"source_type": "x_summary", "account": "account2", "summary": "看多"},
                ],
                "market_validation": {"volume_multiple_5d": 2.1, "breakout": True, "relative_strength": "strong"},
            }
        ]
        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates)
        return enriched

    def test_decision_flow_card_has_conclusion_watchpoints_triggers_and_operation_reminder(self) -> None:
        enriched = self._build_enriched_for_decision_flow()
        report = enriched["report_markdown"]
        flow = report.split("## 决策流", 1)[1].split("## Decision Factors", 1)[0] if "## 决策流" in report else ""

        self.assertIn("### 002460.SZ | 继续观察 | 60.0分 | 高弹性", flow)
        self.assertIn("结论：当前没有硬伤", flow)
        self.assertIn("评分 60.0", flow)
        self.assertIn("执行门槛 70.0", flow)
        self.assertIn("盘中观察点", flow)
        self.assertIn("社区一致性: low", flow)
        self.assertIn("量价验证: strong", flow)
        self.assertIn("lithium_chain", flow)
        self.assertIn("高弹性", flow)
        self.assertIn("触发条件", flow)
        self.assertIn("操作提醒", flow)
        self.assertIn("等待下一次趋势确认或分数修复后再评估", flow)

    def test_decision_flow_markdown_surfaces_geopolitics_regime(self) -> None:
        enriched = self._build_enriched_for_geopolitics_overlay()
        report = enriched["report_markdown"]
        flow = report.split("## 决策流", 1)[1].split("## Decision Factors", 1)[0] if "## 决策流" in report else ""

        self.assertIn("地缘 regime: `escalation`", flow)

    def test_decision_flow_card_includes_geopolitics_bias_and_execution_constraint(self) -> None:
        enriched = self._build_enriched_for_geopolitics_overlay()
        report = enriched["report_markdown"]
        flow = report.split("## 决策流", 1)[1].split("## Decision Factors", 1)[0] if "## 决策流" in report else ""

        self.assertIn("链条偏置：地缘升级下的受益链条", flow)
        self.assertIn("执行约束：轻仓，不追高，隔夜谨慎", flow)

    def test_decision_flow_markdown_surfaces_geopolitics_candidate_summary(self) -> None:
        enriched = self._build_enriched_for_geopolitics_candidate()
        report = enriched["report_markdown"]
        flow = report.split("## 决策流", 1)[1].split("## Decision Factors", 1)[0] if "## 决策流" in report else ""

        self.assertIn("地缘候选判断", flow)
        self.assertIn("信号对齐", flow)

    def test_candidate_block_does_not_claim_formal_overlay_acceptance(self) -> None:
        enriched = self._build_enriched_for_geopolitics_candidate()
        report = enriched["report_markdown"]
        flow = report.split("## 决策流", 1)[1].split("## Decision Factors", 1)[0] if "## 决策流" in report else ""

        self.assertIn("状态：候选判断，尚未写入正式 overlay", flow)

    def test_report_renders_weekend_candidate_before_decision_flow(self) -> None:
        enriched = self._build_enriched_for_decision_flow()
        enriched["request"] = {
            "weekend_market_candidate_input": {
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
        }

        rendered = module_under_test.enrich_live_result_reporting(enriched, failure_candidates=[], assessed_candidates=[])
        report = rendered["report_markdown"]

        self.assertIn("## 周末主线候选", report)
        self.assertIn("## 周一优先盯的方向", report)
        self.assertIn("## 方向参考映射", report)
        self.assertLess(report.index("## 周末主线候选"), report.index("## 决策流"))

    def test_direction_reference_map_is_marked_as_reference_only(self) -> None:
        lines = module_under_test.build_weekend_market_candidate_markdown(
            {"candidate_topics": [], "priority_watch_directions": [], "evidence_summary": [], "status": "candidate_only"},
            [
                {
                    "direction_key": "optical_interconnect",
                    "direction_label": "光通信 / 光模块",
                    "leaders": [{"ticker": "300308.SZ", "name": "中际旭创"}],
                    "high_beta_names": [{"ticker": "300570.SZ", "name": "太辰光"}],
                    "mapping_note": "Direction reference only. Not a formal execution layer.",
                }
            ],
        )
        text = "\n".join(lines)
        self.assertIn("Direction reference only. Not a formal execution layer.", text)

    def test_weekend_candidate_markdown_renders_ranking_logic_and_key_sources(self) -> None:
        lines = module_under_test.build_weekend_market_candidate_markdown(
            {
                "candidate_topics": [
                    {
                        "topic_name": "optical_interconnect",
                        "topic_label": "光通信 / 光模块",
                        "priority_rank": 1,
                        "signal_strength": "high",
                        "why_it_matters": "Preferred X seeds aligned.",
                        "monday_watch": "Watch optics first on Monday.",
                        "ranking_logic": {
                            "seed_alignment": "high",
                            "expansion_confirmation": "high",
                            "reddit_confirmation": "high",
                            "noise_or_disagreement": "low",
                        },
                        "ranking_reason": "This direction ranks first because seed and confirmation layers aligned most cleanly.",
                        "key_sources": [
                            {
                                "source_name": "aleabitoreddit",
                                "source_kind": "x_seed",
                                "url": "https://x.com/aleabitoreddit",
                                "summary": "Continued to frame photonics as an AI bottleneck.",
                            }
                        ],
                    }
                ],
                "priority_watch_directions": ["光通信 / 光模块"],
                "status": "candidate_only",
            },
            [
                {
                    "direction_key": "optical_interconnect",
                    "direction_label": "光通信 / 光模块",
                    "leaders": [{"ticker": "300308.SZ", "name": "中际旭创"}],
                    "high_beta_names": [{"ticker": "300570.SZ", "name": "太辰光"}],
                    "mapping_note": "Direction reference only. Not a formal execution layer.",
                }
            ],
        )
        text = "\n".join(lines)
        self.assertIn("### 排序逻辑", text)
        self.assertIn("种子共振：高", text)
        self.assertIn("扩展确认：高", text)
        self.assertIn("Reddit 验证：高", text)
        self.assertIn("分歧 / 噪音：低", text)
        self.assertIn("### 为什么排第一", text)
        self.assertIn("### 最关键 source", text)
        self.assertIn("aleabitoreddit", text)
        self.assertIn("https://x.com/aleabitoreddit", text)

    def test_weekend_candidate_markdown_renders_multiple_topics_and_live_x_sources(self) -> None:
        lines = module_under_test.build_weekend_market_candidate_markdown(
            {
                "candidate_topics": [
                    {
                        "topic_name": "oil_shipping",
                        "topic_label": "油运 / Hormuz",
                        "priority_rank": 1,
                        "signal_strength": "high",
                        "why_it_matters": "Live X headlines concentrated on Hormuz disruption.",
                        "monday_watch": "Watch shipping first on Monday.",
                        "ranking_logic": {
                            "seed_alignment": "medium",
                            "expansion_confirmation": "medium",
                            "reddit_confirmation": "medium",
                            "noise_or_disagreement": "low",
                        },
                        "ranking_reason": "Live X evidence was the most concentrated here.",
                        "key_sources": [
                            {
                                "source_name": "DeItaone",
                                "source_kind": "x_live_index",
                                "url": "https://x.com/DeItaone/status/1",
                                "summary": "Hormuz remained blocked in the weekend discussion.",
                            }
                        ],
                    },
                    {
                        "topic_name": "commercial_space",
                        "topic_label": "商业航天 / 卫星链",
                        "priority_rank": 2,
                        "signal_strength": "medium",
                        "why_it_matters": "Commercial-space discussion stayed visible on live X.",
                        "monday_watch": "Watch commercial-space follow-through.",
                        "ranking_logic": {
                            "seed_alignment": "low",
                            "expansion_confirmation": "medium",
                            "reddit_confirmation": "low",
                            "noise_or_disagreement": "medium",
                        },
                        "ranking_reason": "Satellite-chain discussion ranked second after oil shipping.",
                        "key_sources": [
                            {
                                "source_name": "LinQingV",
                                "source_kind": "x_live_index",
                                "url": "https://x.com/LinQingV/status/1",
                                "summary": "Focused on TGV and upstream glass-furnace constraints tied to future advanced packaging demand.",
                            }
                        ],
                    },
                ],
                "priority_watch_directions": ["油运 / Hormuz", "商业航天 / 卫星链"],
                "status": "candidate_only",
            },
            [],
        )
        text = "\n".join(lines)
        self.assertIn("油运 / Hormuz", text)
        self.assertIn("商业航天 / 卫星链", text)
        self.assertIn("### 为什么排第二", text)
        self.assertIn("DeItaone", text)
        self.assertIn("LinQingV", text)
        self.assertIn("https://x.com/DeItaone/status/1", text)

    def test_weekend_candidate_markdown_falls_back_when_rich_fields_are_missing(self) -> None:
        text = "\n".join(
            module_under_test.build_weekend_market_candidate_markdown(
                {
                    "candidate_topics": [
                        {
                            "topic_name": "oil_shipping",
                            "topic_label": "油运",
                            "signal_strength": "high",
                            "why_it_matters": "Shipping risk remains elevated.",
                            "monday_watch": "Watch oil shipping first on Monday.",
                        }
                    ],
                    "priority_watch_directions": ["油运"],
                    "status": "candidate_only",
                },
                [],
            )
        )
        self.assertIn("为什么重要: Shipping risk remains elevated.", text)
        self.assertNotIn("### 排序逻辑", text)

    def test_weekend_reference_map_does_not_create_formal_tiers(self) -> None:
        result = {
            "top_picks": [],
            "filter_summary": {},
            "near_miss_candidates": [],
            "request": {
                "analysis_date": "2026-04-21",
                "weekend_market_candidate_input": {
                    "x_seed_inputs": [
                        {
                            "handle": "seed_one",
                            "tags": ["optical_interconnect"],
                            "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                        }
                    ]
                },
            },
            "dropped": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
        }

        enriched = module_under_test.enrich_live_result_reporting(result, failure_candidates=[], assessed_candidates=[])

        self.assertEqual(enriched.get("top_picks", []), [])
        self.assertIn("## 方向参考映射", enriched["report_markdown"])
        self.assertNotIn("正式执行层", enriched["report_markdown"].split("## 方向参考映射", 1)[0])

    def test_merge_track_results_labels_market_strength_supplement_names(self) -> None:
        merged = module_under_test.merge_track_results(
            track_results={
                "main_board": {
                    "filter_summary": {
                        "track_name": "main_board",
                        "track_label": "主板",
                        "keep_threshold": 58.0,
                        "universe_count": 0,
                        "kept_count": 0,
                    },
                    "top_picks": [],
                    "dropped": [],
                    "diagnostic_scorecard": [],
                    "near_miss_candidates": [],
                    "midday_action_summary": [],
                    "tier_output": {"T1": [], "T2": [], "T3": [], "T4": []},
                    "report_markdown": "",
                }
            },
            track_configs={"main_board": {"label": "主板"}},
            base_request={
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-21",
                "market_strength_candidates": [
                    {
                        "ticker": "002980.SZ",
                        "name": "华盛昌",
                        "strength_reason": "near_limit_close",
                        "close_strength": "high",
                        "volume_signal": "expanding",
                        "board_context": "high_conviction_momentum",
                        "theme_guess": ["short_term_momentum"],
                        "source": "market_strength_scan",
                    }
                ],
            },
        )

        self.assertIn("市场强势补充", merged["report_markdown"])
        self.assertIn("002980.SZ", merged["report_markdown"])

    def test_enrich_live_result_reporting_renders_setup_launch_section(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {
                    "setup_launch_candidates": [
                        {
                            "ticker": "603698.SS",
                            "name": "航天工程",
                            "theme_guess": ["commercial_space"],
                            "setup_reasons": ["structure_repair_visible", "volume_return_visible"],
                            "structure_repair": "high",
                            "volume_return": "medium",
                            "rs_improvement": "medium",
                            "distance_from_bottom_state": "off_bottom_not_extended",
                            "source": "setup_launch_scan",
                        }
                    ]
                },
                "filter_summary": {},
                "top_picks": [],
                "dropped": [],
                "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
            },
            failure_candidates=[],
            assessed_candidates=[],
        )

        self.assertIn("setup_launch_candidates", enriched)
        self.assertEqual(enriched["setup_launch_candidates"][0]["ticker"], "603698.SS")
        self.assertIn("筑底启动补充", enriched["report_markdown"])
        self.assertIn("603698.SS", enriched["report_markdown"])
        self.assertIn("setup_launch_scan", enriched["report_markdown"])

    def test_chain_map_does_not_produce_expectation_gap_without_evidence(self) -> None:
        """B5: chain map should not assign names to 预期差最大 without evidence."""
        entries = module_under_test.build_chain_map_entries(
            event_cards=[],
            discovery_context={
                "chain_map": [
                    {
                        "chain_name": "光模块",
                        "leaders": ["中际旭创"],
                        "tier_1": ["中际旭创", "新易盛"],
                        "tier_2": ["天孚通信"],
                        "all_candidates": ["中际旭创", "新易盛", "天孚通信", "ExtraName"],
                    }
                ]
            },
        )
        self.assertEqual(len(entries), 1)
        profiles = entries[0]["profiles"]
        self.assertEqual(profiles["预期差最大"], [])

    def test_chain_map_tier1_gets_elastic_when_chain_has_strong_validation(self) -> None:
        """B5: tier_1 names should get 高弹性 when an event_card in the same chain has strong validation."""
        event_cards = [
            {
                "ticker": "000001.SZ",
                "name": "中际旭创",
                "chain_name": "光模块",
                "trading_profile_bucket": "稳健核心",
                "market_validation_summary": {"label": "strong", "summary": "强"},
            }
        ]
        entries = module_under_test.build_chain_map_entries(
            event_cards=event_cards,
            discovery_context={
                "chain_map": [
                    {
                        "chain_name": "光模块",
                        "leaders": ["中际旭创"],
                        "tier_1": ["中际旭创", "新易盛"],
                        "tier_2": ["天孚通信"],
                    }
                ]
            },
        )
        self.assertEqual(len(entries), 1)
        profiles = entries[0]["profiles"]
        # 新易盛 is tier_1 (not leader), chain has strong validation → 高弹性
        self.assertIn("新易盛", profiles["高弹性"])
        # 天孚通信 is tier_2 → 补涨候选
        self.assertIn("天孚通信", profiles["补涨候选"])

    def test_chain_map_tier1_gets_catchup_when_chain_has_weak_validation(self) -> None:
        """B5: tier_1 names should get 补涨候选 when no event_card in chain has strong validation."""
        event_cards = [
            {
                "ticker": "000001.SZ",
                "name": "中际旭创",
                "chain_name": "光模块",
                "trading_profile_bucket": "稳健核心",
                "market_validation_summary": {"label": "weak", "summary": "弱"},
            }
        ]
        entries = module_under_test.build_chain_map_entries(
            event_cards=event_cards,
            discovery_context={
                "chain_map": [
                    {
                        "chain_name": "光模块",
                        "leaders": ["中际旭创"],
                        "tier_1": ["中际旭创", "新易盛"],
                        "tier_2": ["天孚通信"],
                    }
                ]
            },
        )
        profiles = entries[0]["profiles"]
        self.assertIn("新易盛", profiles["补涨候选"])

    def test_decision_flow_marks_rescued_name_as_low_confidence_fallback(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
            "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
        }
        assessed_candidates = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "adjusted_total_score": 0.0,
                "keep": False,
                "hard_filter_failures": ["bars_fetch_failed"],
                "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                "structured_catalyst_snapshot": {
                    "structured_company_events": [
                        {"date": "2026-04-21", "event_type": "油运景气跟踪"}
                    ]
                },
                "tier_tags": [],
                "trade_card": {"watch_action": "等强势承接", "invalidation": "跌破关键均线"},
                "scores": {"adjusted_total_score": 0.0},
                "score_components": {"structured_catalyst_score": 0.0},
            }
        ]
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }

        with patch.object(module_under_test, "local_market_snapshot_for_candidate", return_value=snapshot):
            enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)

        flow = enriched["report_markdown"].split("## 决策流", 1)[1]
        self.assertIn("继续观察（low-confidence fallback）", flow)
        self.assertIn("数据路径降级：local market snapshot only", flow)
        self.assertIn("保留原因：structured_catalyst", flow)

    def test_decision_flow_lightly_marks_fresh_cache_source(self) -> None:
        card = module_under_test.build_decision_flow_card(
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "action": "继续观察",
                "score": 60.0,
                "keep_threshold_gap": -10.0,
                "tier_tags": [],
                "bars_source": "eastmoney_cache",
            },
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
        )
        self.assertIn("数据来源：Eastmoney cache", card["operation_reminder"])

    def test_prune_rescued_blocked_candidates_removes_cache_rescues_from_blocked_wall(self) -> None:
        enriched = {
            "filter_summary": {
                "blocked_candidate_count": 1,
                "bars_fetch_failed_tickers": ["601975.SS"],
            },
            "blocked_candidates": [
                {
                    "ticker": "601975.SS",
                    "name": "招商南油",
                    "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                }
            ],
            "report_markdown": "# Test Report\n\n## Blocked Candidates\n\n- `601975.SS` 招商南油: `bars_fetch_failed for `601975.SS`: Eastmoney request failed`\n",
        }

        pruned = module_under_test.prune_rescued_blocked_candidates(
            enriched,
            [
                {
                    "ticker": "601975.SS",
                    "execution_state": "stale_cache",
                    "fallback_cache_only": True,
                }
            ],
        )

        self.assertEqual(pruned["filter_summary"]["blocked_candidate_count"], 0)
        self.assertEqual(pruned["filter_summary"]["bars_fetch_failed_tickers"], [])
        self.assertEqual(pruned["blocked_candidates"], [])
        self.assertNotIn("## Blocked Candidates", pruned["report_markdown"])

    def test_decision_flow_marks_stale_cache_rescue_as_low_confidence_fallback(self) -> None:
        card = module_under_test.build_decision_flow_card(
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "action": "继续观察",
                "score": 60.0,
                "keep_threshold_gap": -10.0,
                "tier_tags": ["low_confidence_fallback", "fallback_cache_only"],
                "fallback_support_reason": "structured_catalyst",
            },
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
        )
        self.assertEqual(card["action_label"], "继续观察（low-confidence fallback）")
        self.assertIn("数据路径降级：Eastmoney cache only", card["operation_reminder"])

    def test_prune_rescued_blocked_candidates_removes_cache_rescues_from_blocked_wall(self) -> None:
        enriched = {
            "filter_summary": {
                "blocked_candidate_count": 1,
                "bars_fetch_failed_tickers": ["601975.SS"],
            },
            "blocked_candidates": [
                {
                    "ticker": "601975.SS",
                    "name": "招商南油",
                    "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                }
            ],
            "report_markdown": "# Test Report\n\n## Blocked Candidates\n\n- `601975.SS` 招商南油: `bars_fetch_failed for `601975.SS`: Eastmoney request failed`\n",
        }

        pruned = module_under_test.prune_rescued_blocked_candidates(
            enriched,
            [
                {
                    "ticker": "601975.SS",
                    "execution_state": "stale_cache",
                    "fallback_cache_only": True,
                }
            ],
        )

        self.assertEqual(pruned["filter_summary"]["blocked_candidate_count"], 0)
        self.assertEqual(pruned["filter_summary"]["bars_fetch_failed_tickers"], [])
        self.assertEqual(pruned["blocked_candidates"], [])
        self.assertNotIn("## Blocked Candidates", pruned["report_markdown"])


if __name__ == "__main__":
    unittest.main()
