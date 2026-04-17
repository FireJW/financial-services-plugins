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
                "sources": [{"source_type": "official_filing", "summary": "公司披露一季报业绩预告，同比扭亏。"}],
                "market_validation": {"volume_multiple_5d": 2.1, "breakout": True, "relative_strength": "strong"},
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
        self.assertIn("评分", first["conclusion"])
        self.assertIn("技术", first["watch_points"]["technical"])
        self.assertIn("upgrade", first["triggers"])
        self.assertIn("operation_reminder", first)

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
        self.assertIn("结论", flow)
        self.assertIn("盘中观察点", flow)
        self.assertIn("触发条件", flow)
        self.assertIn("操作提醒", flow)

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


if __name__ == "__main__":
    unittest.main()
