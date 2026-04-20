#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


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


class MarketStrengthSupplementLaneTests(unittest.TestCase):
    def test_default_market_strength_universe_fetcher_uses_top_movers_query(self) -> None:
        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":{"diff":[]}}'

        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout=0):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            return _FakeResponse()

        with patch.object(module_under_test, "urlopen", side_effect=fake_urlopen):
            rows = module_under_test.default_market_strength_universe_fetcher({})

        self.assertEqual(rows, [])
        parsed = parse_qs(urlsplit(captured["url"]).query)
        self.assertEqual(parsed["fid"], ["f3"])
        self.assertEqual(parsed["pz"], ["200"])
        self.assertEqual(parsed["fs"], [module_under_test.MARKET_STRENGTH_MARKET_GROUPS])

    def test_build_market_strength_candidates_from_universe_selects_strongest_close_names(self) -> None:
        rows = module_under_test.build_market_strength_candidates_from_universe(
            [
                {
                    "ticker": "603268.SS",
                    "name": "松发股份",
                    "day_pct": 9.6,
                    "price": 21.9,
                    "high": 22.0,
                    "low": 20.2,
                    "pre_close": 20.0,
                    "day_turnover_cny": 880000000.0,
                    "turnover_rate_pct": 11.2,
                },
                {
                    "ticker": "002980.SZ",
                    "name": "华盛昌",
                    "day_pct": 7.4,
                    "price": 33.5,
                    "high": 33.8,
                    "low": 31.8,
                    "pre_close": 31.2,
                    "day_turnover_cny": 620000000.0,
                    "turnover_rate_pct": 9.1,
                },
            ],
            existing_tickers=set(),
            max_names=5,
        )

        self.assertEqual([item["ticker"] for item in rows], ["603268.SS", "002980.SZ"])
        self.assertEqual(rows[0]["source"], "market_strength_scan")

    def test_build_market_strength_candidates_from_universe_adds_exchange_suffix_from_f13(self) -> None:
        rows = module_under_test.build_market_strength_candidates_from_universe(
            [
                {
                    "f12": "603268",
                    "f13": "1",
                    "f14": "松发股份",
                    "f3": 10.0,
                    "f2": 133.34,
                    "f15": 133.34,
                    "f16": 122.01,
                    "f18": 121.22,
                    "f6": 1744684384.0,
                    "f8": 5.68,
                }
            ],
            existing_tickers=set(),
            max_names=5,
        )

        self.assertEqual(rows[0]["ticker"], "603268.SS")

    def test_build_market_strength_candidates_from_universe_excludes_st_illiquid_and_duplicate_names(self) -> None:
        rows = module_under_test.build_market_strength_candidates_from_universe(
            [
                {
                    "ticker": "000001.SZ",
                    "name": "*ST示例",
                    "day_pct": 5.0,
                    "price": 5.2,
                    "high": 5.2,
                    "low": 5.0,
                    "pre_close": 4.95,
                    "day_turnover_cny": 500000000.0,
                    "turnover_rate_pct": 6.0,
                },
                {
                    "ticker": "000002.SZ",
                    "name": "低流动性样本",
                    "day_pct": 8.0,
                    "price": 8.5,
                    "high": 8.5,
                    "low": 8.0,
                    "pre_close": 7.8,
                    "day_turnover_cny": 30000000.0,
                    "turnover_rate_pct": 0.4,
                },
                {
                    "ticker": "603268.SS",
                    "name": "松发股份",
                    "day_pct": 9.6,
                    "price": 21.9,
                    "high": 22.0,
                    "low": 20.2,
                    "pre_close": 20.0,
                    "day_turnover_cny": 880000000.0,
                    "turnover_rate_pct": 11.2,
                },
            ],
            existing_tickers={"603268.SS"},
            max_names=5,
        )

        self.assertEqual(rows, [])

    def test_merge_market_strength_candidate_inputs_prefers_request_rows(self) -> None:
        merged = module_under_test.merge_market_strength_candidate_inputs(
            [
                {
                    "ticker": "603268.SS",
                    "name": "松发股份",
                    "strength_reason": "manual_override",
                    "close_strength": "medium",
                    "volume_signal": "normal",
                    "board_context": "trend_follow_through",
                    "theme_guess": [],
                    "source": "market_strength_scan",
                }
            ],
            [
                {
                    "ticker": "603268.SS",
                    "name": "松发股份",
                    "strength_reason": "near_limit_close",
                    "close_strength": "high",
                    "volume_signal": "expanding",
                    "board_context": "high_conviction_momentum",
                    "theme_guess": [],
                    "source": "market_strength_scan",
                }
            ],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["strength_reason"], "manual_override")

    def test_default_market_strength_universe_fetcher_retries_then_raises(self) -> None:
        with patch.object(module_under_test, "urlopen", side_effect=RuntimeError("boom")), patch.object(
            module_under_test.time, "sleep", side_effect=lambda *_: None
        ):
            with self.assertRaises(RuntimeError) as ctx:
                module_under_test.default_market_strength_universe_fetcher({})

        self.assertIn("market_strength_universe_fetch_failed", str(ctx.exception))

    def test_normalize_request_preserves_market_strength_candidates(self) -> None:
        normalized = module_under_test.normalize_request(
            {
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
                        "ignored": "drop-me",
                    }
                ],
            }
        )

        rows = normalized.get("market_strength_candidates")
        self.assertIsInstance(rows, list)
        self.assertEqual(rows[0]["ticker"], "002980.SZ")
        self.assertEqual(rows[0]["close_strength"], "high")
        self.assertEqual(rows[0]["source"], "market_strength_scan")
        self.assertNotIn("ignored", rows[0])

    def test_build_market_strength_discovery_candidates_converts_rows(self) -> None:
        rows = module_under_test.build_market_strength_discovery_candidates(
            [
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
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "002980.SZ")
        self.assertEqual(rows[0]["event_type"], "market_strength_scan")
        self.assertEqual(rows[0]["benefit_type"], "mapping")
        self.assertEqual(rows[0]["market_validation"]["relative_strength"], "strong")
        self.assertEqual(rows[0]["market_strength_source"], "market_strength_scan")

    def test_enrich_live_result_reporting_merges_market_strength_candidates_into_watch_surfaces(self) -> None:
        enriched = module_under_test.enrich_live_result_reporting(
            {
                "status": "ok",
                "request": {
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

        self.assertIn("priority_watchlist", enriched)
        tickers = [row["ticker"] for row in enriched["priority_watchlist"]]
        self.assertIn("002980.SZ", tickers)
        row = next(item for item in enriched["priority_watchlist"] if item["ticker"] == "002980.SZ")
        self.assertTrue(row.get("market_strength_supplement"))


if __name__ == "__main__":
    unittest.main()
