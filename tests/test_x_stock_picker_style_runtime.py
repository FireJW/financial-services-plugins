from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "x-stock-picker-style"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from x_stock_picker_style_runtime import normalize_request, run_x_stock_picker_style, run_x_stock_picker_style_batch


def build_simple_history(
    *,
    start: date,
    closes: list[float],
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for offset, close in enumerate(closes):
        trade_date = start + timedelta(days=offset)
        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
            }
        )
    return rows


class XStockPickerStyleRuntimeTests(unittest.TestCase):
    def test_request_requires_a_source_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "Request must include one of"):
            normalize_request({"subject": {"handle": "twikejin"}})

    def test_request_accepts_x_index_request_payload(self) -> None:
        request = normalize_request(
            {
                "subject_url": "https://x.com/twikejin",
                "x_index_request": {"topic": "twikejin style study"},
            }
        )
        self.assertEqual(request["payload_specs"][0]["kind"], "x_index_request")

    def test_request_accepts_subject_url_and_extracts_handle(self) -> None:
        request = normalize_request(
            {
                "subject_url": "https://x.com/tuolaji2024",
                "source_board_seed": {"source_board": []},
            }
        )
        self.assertEqual(request["subject"]["handle"], "tuolaji2024")
        self.assertEqual(request["subject"]["url"], "https://x.com/tuolaji2024")

    def test_request_enriches_subject_from_registry(self) -> None:
        request = normalize_request(
            {
                "subject_url": "https://x.com/tuolaji2024",
                "subject_registry": {
                    "subjects": [
                        {
                            "handle": "tuolaji2024",
                            "display_name": "tuolaji2024",
                            "url": "https://x.com/tuolaji2024",
                            "notes": "Operator supplied seed account for method study.",
                            "tags": ["A-share", "industry-chain"],
                            "candidate_names": ["新易盛"],
                            "theme_aliases": {"optical_interconnect": ["光模块", "EML"]},
                        }
                    ]
                },
                "source_board_seed": {"source_board": []},
            }
        )
        self.assertEqual(request["subject"]["display_name"], "tuolaji2024")
        self.assertEqual(request["subject"]["notes"], "Operator supplied seed account for method study.")
        self.assertEqual(request["subject"]["tags"], ["A-share", "industry-chain"])

    def test_request_merges_registry_theme_aliases_and_logic_baskets_for_single_subject_mode(self) -> None:
        request = normalize_request(
            {
                "subject_url": "https://x.com/aleabitoreddit",
                "subject_registry": {
                    "subjects": [
                        {
                            "handle": "aleabitoreddit",
                            "display_name": "aleabitoreddit",
                            "url": "https://x.com/aleabitoreddit",
                            "candidate_names": ["沪电股份"],
                            "theme_aliases": {"optical_interconnect": ["photonics", "800G"]},
                            "logic_basket_rules": [
                                {
                                    "rule_name": "optical_a_share_basket",
                                    "basket_name": "optical_a_share",
                                    "sector_or_chain": "optical_interconnect",
                                    "match_any": ["photonics", "800G"],
                                    "candidate_names": ["中际旭创", "新易盛"],
                                }
                            ],
                        }
                    ]
                },
                "source_board_seed": {"source_board": []},
            }
        )
        self.assertEqual(request["candidate_names"], ["沪电股份"])
        self.assertEqual(request["theme_aliases"]["optical_interconnect"], ["photonics", "800G"])
        self.assertEqual(request["logic_basket_rules"][0]["basket_name"], "optical_a_share")

    def test_builds_source_board_from_x_index_payload(self) -> None:
        request = {
            "analysis_time": "2026-04-10T08:00:00+00:00",
            "subject": {"platform": "x", "handle": "twikejin", "display_name": "laofashi"},
            "x_index_result": {
                "workflow_kind": "x_index",
                "x_posts": [
                    {
                        "post_url": "https://x.com/twikejin/status/2042086801285034245",
                        "author_handle": "twikejin",
                        "author_display_name": "laofashi",
                        "posted_at": "2026-04-09T03:46:48+00:00",
                        "post_text_raw": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                        "post_text_source": "dom",
                        "post_summary": "High-end weaving machine shortage supports related names.",
                        "thread_posts": [
                            {
                                "post_url": "https://x.com/twikejin/status/2042119840232857769",
                                "posted_at": "2026-04-09T05:58:05+00:00",
                                "post_text_raw": "CCL utilization is high, so weaving-machine shortage still matters.",
                            }
                        ],
                        "artifact_manifest": [
                            {
                                "role": "root_post_screenshot",
                                "path": "C:\\artifacts\\root.png",
                                "media_type": "screenshot",
                            }
                        ],
                    }
                ],
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["workflow_stage"], "style_card")
        self.assertEqual(len(result["source_board"]), 1)
        source = result["source_board"][0]
        self.assertEqual(source["status_id"], "2042086801285034245")
        self.assertEqual(source["direct_text_kind"], "raw_post_text")
        self.assertEqual(source["author_handle"], "twikejin")
        self.assertEqual(len(source["same_author_context"]), 1)
        self.assertFalse(source["needs_operator_review"])
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "logic_support")

    def test_summary_fallback_marks_operator_review(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "x_index_result": {
                "x_posts": [
                    {
                        "post_url": "https://x.com/twikejin/status/2042093511617737052",
                        "author_handle": "twikejin",
                        "posted_at": "2026-04-09T04:13:28+00:00",
                        "post_summary": "Electronic cleanroom global expansion remains high boom.",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        source = result["source_board"][0]
        self.assertEqual(source["direct_text_kind"], "summary_fallback")
        self.assertTrue(source["needs_operator_review"])
        self.assertIn("missing_raw_post_text", source["operator_review_reasons"])
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "logic_support")

    def test_builds_source_board_from_timeline_scan_and_dedupes(self) -> None:
        request = {
            "subject": {"handle": "twikejin", "display_name": "laofashi"},
            "timeline_scan": {
                "scanned_at": "2026-04-09T13:03:50.074Z",
                "pages": [
                    {
                        "handle": "twikejin",
                        "page": "posts",
                        "articles": [
                            {
                                "author_handle": "twikejin",
                                "status_url": "https://x.com/twikejin/status/2042119840232857769",
                                "datetime": "2026-04-09T05:58:05.000Z",
                                "text": "",
                                "quoted_text": "",
                                "raw_text": "",
                            }
                        ],
                    },
                    {
                        "handle": "twikejin",
                        "page": "with_replies",
                        "articles": [
                            {
                                "author_handle": "twikejin",
                                "status_url": "https://x.com/twikejin/status/2042119840232857769",
                                "datetime": "2026-04-09T05:58:05.000Z",
                                "text": "CCL utilization is high, so weaving-machine shortage still matters.",
                                "quoted_text": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                                "raw_text": "full raw text",
                            },
                            {
                                "author_handle": "other_account",
                                "status_url": "https://x.com/other_account/status/2042000000000000000",
                                "datetime": "2026-04-09T01:00:00.000Z",
                                "text": "noise",
                                "quoted_text": "",
                            },
                        ],
                    },
                ],
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(len(result["source_board"]), 1)
        source = result["source_board"][0]
        self.assertEqual(source["source_kind"], "timeline_scan")
        self.assertEqual(source["direct_text_kind"], "timeline_text")
        self.assertEqual(source["quoted_text"], "AI server electronic cloth bottleneck sits in high-end weaving machines.")
        self.assertEqual(source["extraction_method"], "timeline_scan:with_replies")
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "logic_support")

    def test_extracts_direct_pick_when_single_named_core_stock_is_present(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["东山精密"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2041534482210242629",
                        "status_id": "2041534482210242629",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-07T02:00:00+00:00",
                        "direct_text": "东山精密(002384)Q1净利预增119%-152%，第一目标市值仍有翻倍空间。核心股(东山精密)。",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        event = result["recommendation_ledger"][0]
        self.assertEqual(event["classification"], "direct_pick")
        self.assertEqual(event["strength"], "strong_direct")
        self.assertEqual(event["names"], ["东山精密"])
        self.assertEqual(event["catalyst_type"], "earnings")

    def test_extracts_theme_basket_when_multiple_names_are_listed(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["中国巨石", "国际复材", "中材科技", "宏和科技"],
            "theme_aliases": {"electronic_cloth": ["电子布"]},
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2038991266449592742",
                        "status_id": "2038991266449592742",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-31T02:00:00+00:00",
                        "direct_text": "电子布4月报价全面上调。核心股(中国巨石,国际复材,中材科技,宏和科技)",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        event = result["recommendation_ledger"][0]
        self.assertEqual(event["classification"], "theme_basket")
        self.assertEqual(event["strength"], "theme_basket_high_conviction")
        self.assertEqual(event["sector_or_chain"], "electronic_cloth")
        self.assertEqual(event["names"], ["中国巨石", "国际复材", "中材科技", "宏和科技"])

    def test_candidate_names_gate_prevents_noise_name_extraction(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["中国巨石"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2038991240222699527",
                        "status_id": "2038991240222699527",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-31T14:46:08+00:00",
                        "direct_text": "电子布4月报价全面上调，中国巨石单米净利约2.3元，明早7点44分继续看。",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["recommendation_ledger"][0]["names"], ["中国巨石"])

    def test_quote_only_source_is_not_upgraded_to_new_pick(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["世纪华通", "三七互娱", "神州泰岳"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2032267491838144866",
                        "status_id": "2032267491838144866",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-13T02:00:00+00:00",
                        "direct_text": "",
                        "direct_text_kind": "missing",
                        "quoted_text": "游戏出海(世纪华通,三七互娱,神州泰岳)",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        event = result["recommendation_ledger"][0]
        self.assertEqual(event["classification"], "quote_only")
        self.assertTrue(event["needs_operator_review"])
        self.assertIn("quote_only_not_counted_as_new_pick", event["ambiguity_flags"])

    def test_non_finance_daily_post_is_ignored(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["中国巨石"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2041004373489463516",
                        "status_id": "2041004373489463516",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-06T04:05:37+00:00",
                        "direct_text": "过去2年写了几百篇教程，我把自己蒸馏了，是不是可以躺平了？",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["recommendation_ledger"], [])

    def test_source_start_date_filters_out_older_posts(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "source_start_date": "2026-03-01",
            "candidate_names": ["中国巨石"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/1997164084228473052",
                        "status_id": "1997164084228473052",
                        "author_handle": "twikejin",
                        "published_at": "2025-12-06T04:39:57+00:00",
                        "direct_text": "旧帖子，不应进入当前学习窗口。",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2038991240222699527",
                        "status_id": "2038991240222699527",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-31T14:46:08+00:00",
                        "direct_text": "电子布4月报价全面上调，中国巨石单米净利约2.3元。",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(len(result["source_board"]), 1)
        self.assertEqual(result["source_board"][0]["status_id"], "2038991240222699527")

    def test_quote_only_with_finance_context_is_kept_for_review(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["世纪华通", "三七互娱", "神州泰岳"],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2032267491838144866",
                        "status_id": "2032267491838144866",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-13T02:00:00+00:00",
                        "direct_text": "",
                        "direct_text_kind": "missing",
                        "quoted_text": "游戏出海(世纪华通,三七互娱,神州泰岳)",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(len(result["recommendation_ledger"]), 1)
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "quote_only")

    def test_builds_style_card_that_summarizes_method_biases(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["中国巨石", "国际复材", "中材科技", "宏和科技", "柏诚股份", "华康洁净", "东山精密"],
            "theme_aliases": {
                "electronic_cloth": ["电子布", "织布机", "CCL"],
                "cleanroom": ["洁净室"],
            },
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2038991266449592742",
                        "status_id": "2038991266449592742",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-31T02:00:00+00:00",
                        "direct_text": "电子布4月报价全面上调。核心股(中国巨石,国际复材,中材科技,宏和科技)",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2042093511617737052",
                        "status_id": "2042093511617737052",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-09T04:13:28+00:00",
                        "direct_text": "电子洁净室全球扩产高景气，今年高增预期。出海(亚翔集成,圣晖集成) 国产(柏诚股份,华康洁净)",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2041534482210242629",
                        "status_id": "2041534482210242629",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-07T02:00:00+00:00",
                        "direct_text": "东山精密(002384)Q1净利预增119%-152%，第一目标市值仍有翻倍空间。核心股(东山精密)。",
                        "direct_text_kind": "raw_post_text",
                    },
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        style = result["style_card"]
        self.assertEqual(result["workflow_stage"], "style_card")
        self.assertEqual(style["evidence_stage"], "pre_score_pattern_only")
        self.assertEqual(style["preferred_setup_types"][0]["value"], "theme_basket")
        self.assertEqual(style["preferred_setup_types"][0]["count"], 2)
        self.assertEqual(style["sample_summary"]["actionable_event_count"], 3)
        self.assertTrue(any(item["value"] == "electronic_cloth" for item in style["preferred_sectors"]))
        self.assertTrue(any(item["value"] == "cleanroom" for item in style["preferred_sectors"]))
        self.assertTrue(any(item["value"] == "earnings" for item in style["preferred_catalysts"]))
        self.assertTrue(any(item["value"] == "price_hike" for item in style["preferred_catalysts"]))
        self.assertEqual(style["timing_model"]["dominant_horizon"], "swing_1_4w")
        self.assertTrue(any(item["value"] == "high_conviction_language" for item in style["language_clues"]))
        self.assertTrue(len(style["named_pick_hints"]) >= 1)
        self.assertTrue(
            any(claim["value"] == "theme_basket" for claim in style["confirmed_patterns"] if claim["pattern_type"] == "setup_type")
        )
        self.assertIn("basket-first", style["one_line_style"])
        overlay = result["overlay_pack"]
        self.assertEqual(overlay["overlay_name"], "x_style_twikejin")
        self.assertTrue(overlay["advisory_only"])
        self.assertTrue(any(item["theme"] == "electronic_cloth" for item in overlay["theme_biases"]))
        self.assertTrue(any(item["setup_type"] == "theme_basket" for item in overlay["setup_biases"]))
        self.assertTrue(len(overlay["named_pick_hints"]) >= 1)

    def test_optical_theme_alias_maps_tuolaji_style_posts(self) -> None:
        request = {
            "subject": {"handle": "tuolaji2024"},
            "candidate_names": ["新易盛"],
            "theme_aliases": {"optical_interconnect": ["光模块", "光互联", "EML", "CPO", "OCS"]},
            "logic_basket_rules": [
                {
                    "rule_name": "optical_interconnect_a_share_basket",
                    "basket_name": "optical_interconnect_a_share",
                    "sector_or_chain": "optical_interconnect",
                    "match_any": ["光模块", "光互联", "EML", "CPO", "OCS"],
                    "candidate_names": ["新易盛", "中际旭创", "天孚通信"],
                    "note": "optical chain basket hint",
                }
            ],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/tuolaji2024/status/2042465436810559801",
                        "status_id": "2042465436810559801",
                        "author_handle": "tuolaji2024",
                        "published_at": "2026-04-10T04:51:21+00:00",
                        "direct_text": "光模块/光互联——EML缺货的下游受益者，已锁定产能的光模块厂利润弹性最大。可能大概率光模块要涨价了。",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["style_card"]["preferred_sectors"][0]["value"], "optical_interconnect")
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_name"], "optical_interconnect_a_share")
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_candidates"], ["新易盛", "中际旭创", "天孚通信"])
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_core_candidates"], ["新易盛", "中际旭创", "天孚通信"])
        self.assertEqual(result["style_card"]["sample_summary"]["mapped_logic_basket_count"], 1)
        self.assertEqual(result["style_card"]["advisory_basket_hints"][0]["value"], "optical_interconnect_a_share")

    def test_cross_market_memory_logic_can_map_to_a_share_basket(self) -> None:
        request = {
            "subject": {"handle": "jukan05"},
            "theme_aliases": {
                "memory_hbm": ["HBM", "memory", "DRAM"],
                "advanced_packaging": ["CoWoS", "advanced packaging"],
            },
            "logic_basket_rules": [
                {
                    "rule_name": "memory_hbm_a_share_basket",
                    "basket_name": "memory_hbm_a_share",
                    "sector_or_chain": "memory_hbm",
                    "match_any": ["HBM", "memory", "DRAM"],
                    "candidate_names": ["香农芯创", "雅克科技", "深科技", "兆易创新"],
                    "note": "memory mapping",
                },
                {
                    "rule_name": "advanced_packaging_a_share_basket",
                    "basket_name": "advanced_packaging_a_share",
                    "sector_or_chain": "advanced_packaging",
                    "match_any": ["CoWoS", "advanced packaging"],
                    "candidate_names": ["长电科技", "通富微电", "华天科技"],
                    "note": "packaging mapping",
                },
            ],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/jukan05/status/2044000000000000001",
                        "status_id": "2044000000000000001",
                        "author_handle": "jukan05",
                        "published_at": "2026-04-10T04:51:21+00:00",
                        "direct_text": "HBM shortage is still the core issue for AI servers and CoWoS capacity remains tight across the supply chain.",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "logic_support")
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_name"], "memory_hbm_a_share")
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_candidates"], ["香农芯创", "雅克科技", "深科技", "兆易创新"])
        self.assertEqual(result["style_card"]["advisory_basket_hints"][0]["value"], "memory_hbm_a_share")

    def test_cross_market_power_logic_can_map_to_a_share_basket(self) -> None:
        request = {
            "subject": {"handle": "aleabitoreddit"},
            "theme_aliases": {
                "ai_infra": ["AI infra", "datacenter", "networking"],
                "power_grid_ai": ["power", "grid", "electricity demand"],
            },
            "logic_basket_rules": [
                {
                    "rule_name": "ai_infra_a_share_basket",
                    "basket_name": "ai_infra_a_share",
                    "sector_or_chain": "ai_infra",
                    "match_any": ["AI infra", "datacenter", "networking"],
                    "candidate_names": ["工业富联", "沪电股份", "深南电路"],
                    "note": "ai infra mapping",
                },
                {
                    "rule_name": "power_grid_ai_a_share_basket",
                    "basket_name": "power_grid_ai_a_share",
                    "sector_or_chain": "power_grid_ai",
                    "match_any": ["power", "grid", "electricity demand"],
                    "candidate_names": ["国电南瑞", "中国西电", "平高电气"],
                    "note": "grid mapping",
                },
            ],
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/aleabitoreddit/status/2044000000000000002",
                        "status_id": "2044000000000000002",
                        "author_handle": "aleabitoreddit",
                        "published_at": "2026-04-10T05:51:21+00:00",
                        "direct_text": "AI infra keeps pushing datacenter power demand higher and grid spending has to catch up.",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["recommendation_ledger"][0]["classification"], "logic_support")
        self.assertEqual(result["recommendation_ledger"][0]["suggested_basket_name"], "ai_infra_a_share")
        self.assertEqual(result["style_card"]["advisory_basket_hints"][0]["value"], "ai_infra_a_share")

    def test_batch_child_request_merges_registry_candidate_names_and_theme_aliases(self) -> None:
        result = run_x_stock_picker_style_batch(
            {
                "subject_registry": {
                    "subjects": [
                        {
                            "handle": "tuolaji2024",
                            "display_name": "tuolaji2024",
                            "url": "https://x.com/tuolaji2024",
                            "candidate_names": ["新易盛"],
                            "theme_aliases": {"optical_interconnect": ["光模块", "EML"]},
                            "logic_basket_rules": [
                                {
                                    "rule_name": "optical_interconnect_a_share_basket",
                                    "basket_name": "optical_interconnect_a_share",
                                    "sector_or_chain": "optical_interconnect",
                                    "match_any": ["光模块", "EML"],
                                    "candidate_names": ["新易盛", "中际旭创"],
                                }
                            ],
                        }
                    ]
                },
                "shared_request": {
                    "source_board_seed": {
                        "source_board": [
                            {
                                "status_url": "https://x.com/tuolaji2024/status/2042465436810559801",
                                "status_id": "2042465436810559801",
                                "author_handle": "tuolaji2024",
                                "published_at": "2026-04-10T04:51:21+00:00",
                                "direct_text": "光模块/光互联——EML缺货的下游受益者。",
                                "direct_text_kind": "raw_post_text",
                            }
                        ]
                    }
                },
            }
        )
        subject_run = result["subject_runs"][0]
        self.assertEqual(subject_run["style_card"]["preferred_sectors"][0]["value"], "optical_interconnect")
        self.assertEqual(subject_run["style_card"]["sample_summary"]["mapped_logic_basket_count"], 1)
        self.assertEqual(subject_run["overlay_pack"]["advisory_basket_hints"][0]["basket_name"], "optical_interconnect_a_share")

    def test_style_card_prefers_actionable_events_over_logic_only_posts(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "candidate_names": ["卓郎智能", "泰坦股份", "东山精密"],
            "theme_aliases": {"electronic_cloth": ["电子布", "织布机"]},
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2042180903955534193",
                        "status_id": "2042180903955534193",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-09T10:00:44+00:00",
                        "direct_text": "PCB材料持续紧缺，向上游传导，缺口明显。",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2042086801285034245",
                        "status_id": "2042086801285034245",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-09T03:46:48+00:00",
                        "direct_text": "AI服务器电子布核心卡点是高端织布机。卓郎智能，绝对龙头。泰坦股份，弹性最大。",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2041534482210242629",
                        "status_id": "2041534482210242629",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-07T02:00:00+00:00",
                        "direct_text": "东山精密Q1净利预增，第一目标市值仍有翻倍空间。核心股(东山精密)。",
                        "direct_text_kind": "raw_post_text",
                    }
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        style = result["style_card"]
        self.assertNotIn("logic-first", style["one_line_style"])
        self.assertEqual(style["sample_summary"]["actionable_event_count"], 2)
        self.assertIn(style["preferred_setup_types"][0]["value"], {"theme_basket", "direct_pick"})

    def test_style_card_keeps_uncertain_patterns_as_inference_only(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2032267491838144866",
                        "status_id": "2032267491838144866",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-13T02:00:00+00:00",
                        "direct_text": "",
                        "direct_text_kind": "missing",
                        "quoted_text": "游戏出海(世纪华通,三七互娱,神州泰岳)",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2042086801285034245",
                        "status_id": "2042086801285034245",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-09T03:46:48+00:00",
                        "direct_text": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                        "direct_text_kind": "raw_post_text",
                    },
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        style = result["style_card"]
        self.assertTrue(any(item["value"] == "quote_only_material_exists" for item in style["inference_only_patterns"]))
        self.assertTrue(any(item["value"] == "logic_notes_without_named_stocks" for item in style["inference_only_patterns"]))
        self.assertTrue(
            any("operator review" in note.lower() for note in result["overlay_pack"]["notes_for_month_end_shortlist"])
        )

    def test_score_calibration_updates_style_card_without_overriding_method_focus(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "analysis_date": "2026-04-10",
            "score_mode": "latest_close_review",
            "candidate_names": ["中国巨石", "国际复材", "东山精密"],
            "theme_aliases": {"electronic_cloth": ["电子布"]},
            "ticker_resolution_by_name": {
                "中国巨石": {"ticker": "600176.SS", "resolved_name": "中国巨石", "board": "Main"},
                "国际复材": {"ticker": "301526.SZ", "resolved_name": "国际复材", "board": "ChiNext"},
                "东山精密": {"ticker": "002384.SZ", "resolved_name": "东山精密", "board": "Main"},
            },
            "history_by_ticker": {
                "600176.SS": build_simple_history(start=date(2026, 3, 31), closes=[10.0, 10.2, 10.4, 10.8, 11.0, 11.3, 11.6, 11.9, 12.1, 12.4]),
                "301526.SZ": build_simple_history(start=date(2026, 3, 31), closes=[8.0, 8.1, 8.3, 8.5, 8.6, 8.9, 9.1, 9.4, 9.6, 9.8]),
                "002384.SZ": build_simple_history(start=date(2026, 4, 7), closes=[20.0, 20.1, 20.4, 20.6]),
            },
            "source_board_seed": {
                "source_board": [
                    {
                        "status_url": "https://x.com/twikejin/status/2038991266449592742",
                        "status_id": "2038991266449592742",
                        "author_handle": "twikejin",
                        "published_at": "2026-03-31T02:00:00+00:00",
                        "direct_text": "电子布4月报价全面上调。核心股(中国巨石,国际复材)",
                        "direct_text_kind": "raw_post_text",
                    },
                    {
                        "status_url": "https://x.com/twikejin/status/2041534482210242629",
                        "status_id": "2041534482210242629",
                        "author_handle": "twikejin",
                        "published_at": "2026-04-07T02:00:00+00:00",
                        "direct_text": "东山精密(002384)Q1净利预增119%-152%，第一目标市值仍有翻倍空间。核心股(东山精密)。",
                        "direct_text_kind": "raw_post_text",
                    },
                ]
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertEqual(result["score_summary"]["scoreable_name_count"], 3)
        self.assertEqual(result["style_card"]["evidence_stage"], "score_calibrated")
        self.assertGreater(result["score_summary"]["overall"]["avg_return"], 0.0)
        self.assertIn("Post-score calibration", " ".join(result["style_card"]["where_the_edge_seems_real"]))
        self.assertIn("Post-score summary", result["report_markdown"])
        basket_stats = result["score_summary"]["by_classification"]["theme_basket"]
        direct_stats = result["score_summary"]["by_classification"]["direct_pick"]
        self.assertGreater(basket_stats["avg_return"], direct_stats["avg_return"])

    def test_markdown_report_is_present(self) -> None:
        request = {
            "subject": {"handle": "twikejin"},
            "timeline_scan": {
                "scanned_at": "2026-04-09T13:03:50.074Z",
                "pages": [
                    {
                        "handle": "twikejin",
                        "page": "posts",
                        "articles": [
                            {
                                "author_handle": "twikejin",
                                "status_url": "https://x.com/twikejin/status/2042086801285034245",
                                "datetime": "2026-04-09T03:46:48.000Z",
                                "text": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                                "quoted_text": "",
                            }
                        ],
                    }
                ],
            },
        }
        result = run_x_stock_picker_style(request)
        self.assertIn("X Stock Picker Style Report", result["report_markdown"])
        self.assertIn("Recommendation Ledger", result["report_markdown"])
        self.assertIn("Style Card", result["report_markdown"])
        self.assertIn("Overlay Pack", result["report_markdown"])

    def test_markdown_report_surfaces_subject_metadata(self) -> None:
        result = run_x_stock_picker_style(
            {
                "subject_url": "https://x.com/tuolaji2024",
                "subject_notes": "Operator supplied seed account for method study.",
                "subject_tags": ["A-share", "industry-chain"],
                "timeline_scan": {
                    "scanned_at": "2026-04-09T13:03:50.074Z",
                    "pages": [],
                },
            }
        )
        self.assertIn("Subject URL", result["report_markdown"])
        self.assertIn("Subject notes", result["report_markdown"])
        self.assertIn("Subject tags", result["report_markdown"])

    @patch("x_stock_picker_style_runtime.run_x_index_request")
    def test_run_can_chain_x_index_request_before_style_learning(self, run_x_index_request_mock) -> None:
        run_x_index_request_mock.return_value = {
            "workflow_kind": "x_index",
            "x_posts": [
                {
                    "post_url": "https://x.com/twikejin/status/2042086801285034245",
                    "author_handle": "twikejin",
                    "posted_at": "2026-04-09T03:46:48+00:00",
                    "post_text_raw": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                    "post_text_source": "dom",
                }
            ],
        }
        result = run_x_stock_picker_style(
            {
                "subject_url": "https://x.com/twikejin",
                "x_index_request": {"topic": "twikejin style study"},
            }
        )
        run_x_index_request_mock.assert_called_once()
        self.assertEqual(result["workflow_stage"], "style_card")
        self.assertEqual(result["source_board"][0]["status_id"], "2042086801285034245")

    @patch("x_stock_picker_style_runtime.run_x_index_request")
    def test_x_index_request_failure_surfaces_warning(self, run_x_index_request_mock) -> None:
        run_x_index_request_mock.side_effect = RuntimeError("x-index failed")
        result = run_x_stock_picker_style(
            {
                "subject_url": "https://x.com/twikejin",
                "x_index_request": {"topic": "twikejin style study"},
            }
        )
        self.assertEqual(result["source_board"], [])
        self.assertTrue(any("x_index_request_failed" in warning for warning in result["warnings"]))

    def test_batch_mode_compares_multiple_subjects_from_registry(self) -> None:
        result = run_x_stock_picker_style_batch(
            {
                "analysis_time": "2026-04-10T08:00:00+00:00",
                "analysis_date": "2026-04-10",
                "subject_registry": {
                    "subjects": [
                        {
                            "handle": "twikejin",
                            "display_name": "laofashi",
                            "url": "https://x.com/twikejin",
                            "tags": ["theme-basket"],
                        },
                        {
                            "handle": "tuolaji2024",
                            "display_name": "tuolaji2024",
                            "url": "https://x.com/tuolaji2024",
                            "tags": ["industry-chain"],
                        },
                    ]
                },
                "selected_handles": ["twikejin", "tuolaji2024"],
                "shared_request": {
                    "score_mode": "off",
                },
                "subject_overrides_by_handle": {
                    "twikejin": {
                        "candidate_names": ["中国巨石", "国际复材"],
                        "theme_aliases": {"electronic_cloth": ["电子布"]},
                        "source_board_seed": {
                            "source_board": [
                                {
                                    "status_url": "https://x.com/twikejin/status/2038991266449592742",
                                    "status_id": "2038991266449592742",
                                    "author_handle": "twikejin",
                                    "published_at": "2026-03-31T02:00:00+00:00",
                                    "direct_text": "电子布4月报价全面上调。核心股(中国巨石,国际复材)",
                                    "direct_text_kind": "raw_post_text",
                                }
                            ]
                        },
                    },
                    "tuolaji2024": {
                        "candidate_names": ["东方锆业"],
                        "theme_aliases": {"zirconium": ["锆", "锆业"]},
                        "source_board_seed": {
                            "source_board": [
                                {
                                    "status_url": "https://x.com/tuolaji2024/status/2043000000000000000",
                                    "status_id": "2043000000000000000",
                                    "author_handle": "tuolaji2024",
                                    "published_at": "2026-04-09T02:00:00+00:00",
                                    "direct_text": "锆价修复和事件驱动仍值得看，核心股(东方锆业)",
                                    "direct_text_kind": "raw_post_text",
                                }
                            ]
                        },
                    },
                },
            }
        )
        self.assertEqual(result["workflow_kind"], "x_stock_picker_style_batch")
        self.assertEqual(result["workflow_stage"], "batch_compare")
        self.assertEqual(len(result["subject_runs"]), 2)
        self.assertEqual(len(result["comparison_summary"]), 2)
        twikejin_summary = next(item for item in result["comparison_summary"] if item["handle"] == "twikejin")
        tuolaji_summary = next(item for item in result["comparison_summary"] if item["handle"] == "tuolaji2024")
        self.assertEqual(twikejin_summary["preferred_setup"], "theme_basket")
        self.assertEqual(twikejin_summary["preferred_sector"], "electronic_cloth")
        self.assertEqual(tuolaji_summary["preferred_setup"], "direct_pick")
        self.assertEqual(tuolaji_summary["preferred_sector"], "zirconium")
        self.assertIn("X Stock Picker Style Batch Report", result["report_markdown"])

    def test_batch_x_index_template_prefers_account_allowlist_for_profile_subjects(self) -> None:
        captured_requests: list[dict[str, object]] = []

        def fake_run_x_index_request(payload: dict[str, object]) -> dict[str, object]:
            captured_requests.append(payload)
            handle = payload["account_allowlist"][0]
            return {
                "workflow_kind": "x_index",
                "x_posts": [
                    {
                        "post_url": f"https://x.com/{handle}/status/2042086801285034245",
                        "author_handle": handle,
                        "posted_at": "2026-04-09T03:46:48+00:00",
                        "post_text_raw": "AI server electronic cloth bottleneck sits in high-end weaving machines.",
                        "post_text_source": "dom",
                    }
                ],
            }

        with patch("x_stock_picker_style_runtime.run_x_index_request", side_effect=fake_run_x_index_request):
            result = run_x_stock_picker_style_batch(
                {
                    "analysis_time": "2026-04-10T08:00:00+00:00",
                    "subject_registry": {
                        "subjects": [
                            {
                                "handle": "tuolaji2024",
                                "display_name": "tuolaji2024",
                                "url": "https://x.com/tuolaji2024",
                            }
                        ]
                    },
                    "shared_request": {
                        "x_index_request_template": {
                            "browser_session": {
                                "strategy": "remote_debugging",
                                "cdp_endpoint": "http://127.0.0.1:9222",
                                "required": True,
                            }
                        }
                    },
                }
            )

        self.assertEqual(len(captured_requests), 1)
        self.assertEqual(captured_requests[0]["account_allowlist"], ["tuolaji2024"])
        self.assertEqual(captured_requests[0]["manual_urls"], [])
        self.assertEqual(result["subject_runs"][0]["subject"]["handle"], "tuolaji2024")

    # ---- P0 fix: logic basket min_match_score threshold ----

    def test_logic_basket_requires_min_match_score(self) -> None:
        """A single generic keyword match (score=1) should NOT trigger an
        advisory basket when the default min_match_score=3 is in effect."""
        from x_stock_picker_style_runtime import infer_logic_basket_hint
        request = {
            "logic_basket_rules": [
                {
                    "rule_name": "ai_infra_a_share_basket",
                    "basket_name": "ai_infra_a_share",
                    "sector_or_chain": "ai_infra",
                    "match_any": ["AI", "GPU", "ASIC", "datacenter", "server", "networking"],
                    "candidate_names": ["工业富联", "沪电股份", "深南电路"],
                }
            ],
        }
        # Single generic keyword "AI" should be blocked by min_match_score
        result = infer_logic_basket_hint("AI is changing everything", request)
        self.assertEqual(result, {})

    def test_logic_basket_fires_when_score_meets_threshold(self) -> None:
        """Three match_any hits (score=3) should meet the default threshold."""
        from x_stock_picker_style_runtime import infer_logic_basket_hint
        request = {
            "logic_basket_rules": [
                {
                    "rule_name": "ai_infra_a_share_basket",
                    "basket_name": "ai_infra_a_share",
                    "sector_or_chain": "ai_infra",
                    "match_any": ["AI", "GPU", "ASIC", "datacenter", "server", "networking"],
                    "candidate_names": ["工业富联", "沪电股份", "深南电路"],
                }
            ],
        }
        result = infer_logic_basket_hint(
            "AI datacenter GPU demand is surging for next-gen server builds", request
        )
        self.assertNotEqual(result, {})
        self.assertEqual(result["basket_name"], "ai_infra_a_share")
        self.assertGreaterEqual(result["match_score"], 3)

    def test_logic_basket_match_all_always_meets_threshold(self) -> None:
        """A match_all hit (score=3 per term) should always meet the default
        threshold even with a single required term."""
        from x_stock_picker_style_runtime import infer_logic_basket_hint
        request = {
            "logic_basket_rules": [
                {
                    "rule_name": "hbm_basket",
                    "basket_name": "memory_hbm_a_share",
                    "sector_or_chain": "memory_hbm",
                    "match_all": ["HBM"],
                    "match_any": ["memory", "DRAM", "SK hynix"],
                    "candidate_names": ["雅克科技"],
                }
            ],
        }
        result = infer_logic_basket_hint("HBM shortage is the core bottleneck", request)
        self.assertNotEqual(result, {})
        self.assertEqual(result["basket_name"], "memory_hbm_a_share")

    def test_logic_basket_custom_min_score_overrides_default(self) -> None:
        """The min_logic_basket_match_score request field should override
        the default threshold."""
        from x_stock_picker_style_runtime import infer_logic_basket_hint
        request = {
            "min_logic_basket_match_score": 1,
            "logic_basket_rules": [
                {
                    "rule_name": "ai_infra_a_share_basket",
                    "basket_name": "ai_infra_a_share",
                    "sector_or_chain": "ai_infra",
                    "match_any": ["AI"],
                    "candidate_names": ["工业富联"],
                }
            ],
        }
        result = infer_logic_basket_hint("AI is changing everything", request)
        self.assertNotEqual(result, {})
        self.assertEqual(result["basket_name"], "ai_infra_a_share")

    def test_shortlist_extract_x_style_overlays_marks_stale_batch_result(self) -> None:
        """Batch results older than 48h should carry a stale_result_warning into
        the extracted shortlist overlay."""
        month_end_scripts = (
            Path(__file__).resolve().parents[1]
            / "financial-analysis"
            / "skills"
            / "month-end-shortlist"
            / "scripts"
        )
        if str(month_end_scripts) not in sys.path:
            sys.path.insert(0, str(month_end_scripts))
        from month_end_shortlist_runtime import extract_x_style_overlays_from_result

        raw = {
            "analysis_time": "2026-04-10T00:00:00+00:00",
            "subject_runs": [
                {
                    "subject": {"handle": "aleabitoreddit"},
                    "overlay_pack": {
                        "overlay_name": "aleabitoreddit",
                        "evidence_stage": "pre_score_pattern_only",
                        "theme_biases": [],
                        "setup_biases": [],
                        "advisory_basket_hints": [],
                        "subject_tags": ["cross-market"],
                    },
                }
            ],
        }
        with patch("month_end_shortlist_runtime.now_utc") as now_mock:
            from datetime import UTC, datetime
            now_mock.return_value = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
            overlays = extract_x_style_overlays_from_result(raw)
        self.assertEqual(len(overlays), 1)
        self.assertIn("stale_result_warning", overlays[0])
        self.assertIn("older than 48h", overlays[0]["stale_result_warning"])


if __name__ == "__main__":
    unittest.main()
