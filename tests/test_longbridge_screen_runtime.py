#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "longbridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from longbridge_screen_runtime import build_markdown_report, load_json, normalize_analysis_layers, run_longbridge_screen
from longbridge_screen_runtime import score_catalysts


def fake_quote_runner(args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
    del env, timeout_seconds
    symbol = args[-1] if args[:3] == ["quote", "--format", "json"] else args[1]
    quote_map = {
        "600111.SH": {
            "symbol": "600111.SH",
            "last": "53.04",
            "open": "51.88",
            "high": "53.35",
            "low": "51.36",
            "prev_close": "50.95",
            "volume": 2713210,
            "turnover": "14301953714.00",
            "status": "Normal",
        },
        "000969.SZ": {
            "symbol": "000969.SZ",
            "last": "21.37",
            "open": "21.03",
            "high": "21.40",
            "low": "20.95",
            "prev_close": "21.14",
            "volume": 200584,
            "turnover": "425102182.44",
            "status": "Normal",
        },
        "TSLA.US": {
            "symbol": "TSLA.US",
            "last": "212.40",
            "open": "209.10",
            "high": "214.00",
            "low": "207.80",
            "prev_close": "208.20",
            "volume": 48123000,
            "turnover": "10120000000.00",
            "status": "Normal",
        },
    }
    if args[:3] == ["quote", "--format", "json"]:
        return [quote_map[symbol]]
    if args[:2] == ["news", "detail"]:
        return {"id": args[2], "title": "Rare earth leader reports stronger earnings", "content": "Full article text"}
    if args[:2] == ["filing", "detail"]:
        return {"symbol": args[2], "id": args[3], "content": "Full filing markdown"}
    if args[:1] == ["news"]:
        if symbol == "600111.SH":
            return [
                {
                    "id": "n1",
                    "title": "Rare earth leader reports stronger earnings and tight supply",
                    "published_at": 1777367830,
                    "url": "https://longbridge.cn/news/n1",
                }
            ]
        return []
    if args[:1] == ["topic"]:
        if symbol == "600111.SH":
            return [
                {
                    "id": "t1",
                    "title": "Rare earth sector attracts capital inflows",
                    "description": "Northern Rare Earth led a sector breakout with active participation.",
                    "published_at": 1777367830,
                    "likes_count": 4,
                    "comments_count": 2,
                }
            ]
        return []
    if args[:1] == ["filing"]:
        if symbol == "600111.SH":
            return [
                {
                    "id": "f1",
                    "title": "Q1 earnings report",
                    "publish_at": 1777367830,
                    "file_count": 1,
                }
            ]
        return []
    if args[:1] == ["valuation"]:
        if symbol == "600111.SH":
            return {
                "overview": {
                    "metrics": {
                        "pe": {
                            "metric": "35.00x",
                            "industry_median": "50.00",
                            "part": "0.25",
                            "desc": "Current PE is below industry median.",
                        }
                    }
                }
            }
        return {
            "overview": {
                "metrics": {
                    "pe": {
                        "metric": "58.00x",
                        "industry_median": "44.00",
                        "part": "0.85",
                    }
                }
            }
        }
    if args[:1] == ["institution-rating"]:
        if symbol == "600111.SH":
            return {
                "instratings": {
                    "recommend": "strong_buy",
                    "target": "65.00",
                    "evaluate": {"strong_buy": 4, "buy": 3, "hold": 0, "under": 0, "sell": 0},
                }
            }
        return {
            "instratings": {
                "recommend": "hold",
                "target": "20.00",
                "evaluate": {"strong_buy": 0, "buy": 1, "hold": 4, "under": 0, "sell": 0},
            }
        }
    if args[:1] == ["forecast-eps"]:
        return {
            "items": [
                {
                    "forecast_start_date": "1777367830",
                    "forecast_eps_mean": "1.04",
                    "institution_up": 2 if symbol == "600111.SH" else 0,
                    "institution_down": 0 if symbol == "600111.SH" else 1,
                    "institution_total": 3,
                }
            ]
        }
    if args[:1] == ["consensus"]:
        if symbol == "600111.SH":
            return {
                "list": [
                    {
                        "period_text": "Q1 2026",
                        "details": [
                            {"key": "eps", "comp": "beat_est", "is_released": True},
                            {"key": "revenue", "comp": "beat_est", "is_released": True},
                        ],
                    }
                ]
            }
        return {
            "list": [
                {
                    "period_text": "Q1 2026",
                    "details": [{"key": "eps", "comp": "miss_est", "is_released": True}],
                }
            ]
        }
    if args[:1] == ["watchlist"]:
        return [
            {
                "id": "rare-watch",
                "name": "Rare Earth Watch",
                "securities": [
                    {"symbol": "000969.SZ", "name": "Antai Technology"},
                    {"symbol": "OLD.US", "name": "Old Candidate"},
                ],
            }
        ]
    if args[:1] == ["alert"]:
        return [
            {
                "id": "alert-enable",
                "symbol": "600111.SH",
                "price": "53.46",
                "direction": "rise",
                "status": "disabled",
                "enabled": False,
            },
            {
                "id": "alert-stale",
                "symbol": "000969.SZ",
                "price": "15.00",
                "direction": "fall",
                "status": "enabled",
                "enabled": True,
            },
        ]
    if args[:1] == ["portfolio"]:
        return {
            "overview": {
                "total_asset": "120000",
                "market_cap": "83000",
                "total_cash": "37000",
                "total_pl": "-2200",
                "total_today_pl": "-850",
                "risk_level": "medium",
                "currency": "USD",
            },
            "holdings": [
                {
                    "symbol": "000969.SZ",
                    "name": "Antai Technology",
                    "quantity": "2000",
                    "market_value": "42740",
                    "cost_price": "24.80",
                    "today_pl": "-320",
                    "total_pl": "-6860",
                }
            ],
        }
    if args[:1] == ["positions"]:
        return [
            {
                "symbol": "000969.SZ",
                "name": "Antai Technology",
                "quantity": "2000",
                "available_quantity": "2000",
                "cost_price": "24.80",
                "currency": "CNY",
                "market": "SZ",
            }
        ]
    if args[:1] == ["assets"]:
        return {
            "currency": "USD",
            "net_assets": "120000",
            "total_cash": "37000",
            "buy_power": "61000",
            "margin_call": "0",
            "risk_level": "medium",
        }
    if args[:1] == ["cash-flow"]:
        return [
            {
                "flow_name": "Dividend",
                "symbol": "000969.SZ",
                "business_type": "DIVIDEND",
                "balance": "120",
                "currency": "CNY",
                "business_time": "2026-04-20",
            }
        ]
    if args[:1] == ["profit-analysis"]:
        return {
            "summary": {
                "total_pl": "-2200",
                "today_pl": "-850",
                "simple_yield": "-0.018",
                "twr": "-0.012",
            }
        }
    if args[:1] == ["capital"]:
        if symbol == "600111.SH":
            return {"net_inflow": "8500000", "large_order_inflow": "3600000", "large_order_outflow": "1200000"}
        return {"net_inflow": "-250000", "large_order_inflow": "200000", "large_order_outflow": "450000"}
    if args[:1] == ["depth"]:
        if symbol == "600111.SH":
            return {
                "bids": [{"price": "53.02", "volume": "18000"}, {"price": "53.00", "volume": "15000"}],
                "asks": [{"price": "53.08", "volume": "9000"}, {"price": "53.12", "volume": "7000"}],
            }
        return {
            "bids": [{"price": "21.35", "volume": "3000"}],
            "asks": [{"price": "21.39", "volume": "9000"}],
        }
    if args[:1] == ["trades"]:
        if symbol == "600111.SH":
            return [
                {"price": "53.10", "volume": "1000", "direction": "up"},
                {"price": "53.12", "volume": "1200", "direction": "up"},
                {"price": "53.02", "volume": "400", "direction": "down"},
            ]
        return [
            {"price": "21.36", "volume": "800", "direction": "down"},
            {"price": "21.37", "volume": "500", "direction": "neutral"},
        ]
    if args[:1] == ["trade-stats"]:
        return {"price_distribution": [{"price": str(quote_map[symbol]["last"]), "volume": "250000"}]}
    if args[:1] == ["anomaly"]:
        return [] if "--symbol" in args and args[args.index("--symbol") + 1] == "600111.SH" else [{"symbol": symbol, "type": "volume_spike"}]
    if args[:1] == ["market-temp"]:
        return {"market": args[1] if len(args) > 1 else "HK", "temperature": "62"}
    if args[:1] == ["company"]:
        return {
            "symbol": symbol,
            "name": "Northern Rare Earth" if symbol == "600111.SH" else "Antai Technology",
            "industry": "Rare Earth",
            "employees": "9800",
            "ipo_date": "1997-09-24",
        }
    if args[:1] == ["industry-valuation"]:
        return {
            "industry": "Rare Earth",
            "pe": "35",
            "industry_median": "50",
            "percentile": "0.25" if symbol == "600111.SH" else "0.82",
            "peers": [{"symbol": "600111.SH"}, {"symbol": "000969.SZ"}],
        }
    if args[:1] == ["constituent"]:
        return [
            {"symbol": "600111.SH", "name": "Northern Rare Earth", "weight": "8.5"},
            {"symbol": "000969.SZ", "name": "Antai Technology", "weight": "1.2"},
        ]
    if args[:1] == ["shareholder"]:
        return [{"name": "Strategic Holder", "owned_ratio": "12.5", "change": "inc", "report_date": "2026-03-31"}]
    if args[:1] == ["fund-holder"]:
        return [{"name": "Rare Earth ETF", "symbol": "RAREETF.HK", "weight": "4.2", "report_date": "2026-03-31"}]
    if args[:1] == ["corp-action"]:
        return []
    if args[:2] == ["statement", "list"]:
        return [
            {
                "dt": "2026-04-29",
                "file_key": "statement-20260429",
                "type": "daily",
            }
        ]
    if args[:1] == ["fund-positions"]:
        return [
            {
                "symbol": "FUND123.HK",
                "name": "Money Market Fund",
                "current_net_asset_value": "10080",
                "cost_net_asset_value": "10000",
                "currency": "HKD",
                "holding_units": "1000",
            }
        ]
    if args[:1] == ["exchange-rate"]:
        return [
            {"from_currency": "USD", "to_currency": "HKD", "rate": "7.80"},
            {"from_currency": "CNY", "to_currency": "HKD", "rate": "1.08"},
        ]
    if args[:1] == ["margin-ratio"]:
        return {"symbol": symbol, "im_factor": "0.5", "mm_factor": "0.3", "fm_factor": "0.2"}
    if args[:1] == ["max-qty"]:
        side = args[args.index("--side") + 1]
        return {
            "symbol": symbol,
            "side": side,
            "cash_max_qty": "1000" if side == "buy" else "0",
            "margin_max_qty": "1800" if side == "buy" else "2000",
        }
    if args[:1] == ["financial-report"]:
        return {
            "symbol": symbol,
            "reports": [
                {
                    "period": "2025",
                    "revenue": "1200000000",
                    "net_income": "180000000",
                    "net_income_yoy": "35.0",
                    "operating_cash_flow": "-42000000",
                    "eps": "1.20",
                }
            ],
        }
    if args[:1] == ["finance-calendar"]:
        return [
            {
                "symbol": symbol,
                "event_type": args[1],
                "event_date": "2026-05-15",
                "title": "Annual report release",
            }
        ]
    if args[:1] == ["dividend"]:
        if len(args) > 1 and args[1] == "detail":
            return {"symbol": symbol, "plans": [{"year": "2025", "cash": "0.35", "currency": "CNY"}]}
        return [{"symbol": symbol, "year": "2025", "cash": "0.35", "ex_date": "2026-06-01"}]
    if args[:1] == ["operating"]:
        return {
            "symbol": symbol,
            "reviews": [{"period": "2025", "gross_margin": "0.28", "roe": "0.15", "summary": "steady"}],
        }
    if args[:1] == ["insider-trades"]:
        return {
            "items": [
                {
                    "symbol": symbol,
                    "insider": "Example CFO",
                    "transaction_type": "SELL",
                    "shares": "15000",
                    "price": "212.40",
                    "transaction_date": "2026-04-28",
                }
            ]
        }
    if args[:1] == ["short-positions"]:
        return {
            "items": [
                {
                    "symbol": symbol,
                    "short_ratio": "18.6",
                    "days_to_cover": "7.4",
                    "settlement_date": "2026-04-15",
                }
            ]
        }
    if args[:1] == ["investors"]:
        if len(args) > 1 and args[1].isdigit():
            return {
                "cik": args[1],
                "holdings": [{"symbol": "TSLA.US", "name": "Tesla", "value": "125000000"}],
            }
        return {"items": [{"cik": "0001067983", "manager": "Berkshire Hathaway", "aum": "347000000000"}]}
    if args[:2] == ["quant", "run"]:
        return {
            "symbol": args[2],
            "series": {"momentum": [-0.2, 0.4, 1.3]},
            "plots": [{"name": "momentum", "values": [-0.2, 0.4, 1.3]}],
        }
    if args[:2] == ["kline", symbol]:
        if symbol == "600111.SH":
            closes = [46.0, 46.2, 46.4, 46.5, 46.8, 47.1, 47.5, 48.0, 48.3, 48.6, 49.0, 49.4, 49.9, 50.2, 50.6, 50.9, 51.2, 51.6, 52.0, 53.04]
            highs = [c + 0.45 for c in closes[:-1]] + [53.35]
            lows = [c - 0.55 for c in closes]
            volumes = [900000, 880000, 910000, 920000, 930000, 950000, 960000, 980000, 990000, 1010000, 1030000, 1040000, 1050000, 1060000, 1080000, 1100000, 1120000, 1200000, 1800000, 2713210]
        else:
            closes = [20.6, 20.4, 20.2, 20.3, 20.5, 20.4, 20.6, 20.7, 20.8, 20.9, 21.0, 21.1, 21.2, 21.0, 20.8, 20.7, 20.9, 21.1, 21.14, 21.37]
            highs = [c + 0.35 for c in closes[:-1]] + [21.40]
            lows = [c - 0.30 for c in closes]
            volumes = [210000, 205000, 190000, 185000, 180000, 175000, 170000, 168000, 166000, 165000, 164000, 163000, 162000, 161000, 160000, 158000, 170000, 180000, 193938, 200584]
        rows = []
        for idx, close in enumerate(closes):
            rows.append(
                {
                    "time": f"2026-04-{idx + 1:02d} 16:00:00",
                    "open": f"{close - 0.10:.2f}",
                    "high": f"{highs[idx]:.2f}",
                    "low": f"{lows[idx]:.2f}",
                    "close": f"{close:.2f}",
                    "volume": str(volumes[idx]),
                    "turnover": f"{close * volumes[idx]:.2f}",
                }
            )
        return rows
    raise AssertionError(f"unexpected args: {args}")


def fake_optional_failure_runner(args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
    if args and args[0] in {"news", "topic", "filing", "valuation", "institution-rating", "forecast-eps", "consensus"}:
        raise RuntimeError(f"{args[0]} blocked for this account")
    return fake_quote_runner(args, env, timeout_seconds)


def fake_financial_event_failure_runner(args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
    financial_event_commands = {
        "financial-report",
        "finance-calendar",
        "dividend",
        "operating",
        "news detail",
        "filing detail",
    }
    command = " ".join(args[:2]) if len(args) >= 2 and args[1] == "detail" else (args[0] if args else "")
    if command in financial_event_commands:
        raise RuntimeError(f"{command} blocked for this account")
    return fake_quote_runner(args, env, timeout_seconds)


class LongbridgeScreenRuntimeTests(unittest.TestCase):
    def test_load_json_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_text('{"analysis_date":"2026-04-29","tickers":["600111.SH"]}', encoding="utf-8-sig")
            payload = load_json(path)

        self.assertEqual(payload["tickers"], ["600111.SH"])

    def test_load_json_accepts_powershell_control_character_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_bytes(b'{"analysis_date":"2026-04-29","note":"raw \x01 control","tickers":["600111.SH"]}')
            payload = load_json(path)

        self.assertEqual(payload["note"], "raw \x01 control")

    def test_explicit_analysis_layers_preserve_catalyst_and_valuation(self) -> None:
        layers = normalize_analysis_layers({"analysis_layers": ["catalyst", "valuation"]})

        self.assertEqual(layers, {"catalyst", "valuation"})

    def test_financial_event_aliases_normalize_to_canonical_layer(self) -> None:
        for alias in ["financial_event", "financial", "report", "event", "earnings", "calendar", "dividend", "operating"]:
            with self.subTest(alias=alias):
                layers = normalize_analysis_layers({"analysis_layers": [alias]})

                self.assertEqual(layers, {"financial_event"})

    def test_p1_layer_aliases_normalize_to_canonical_layers(self) -> None:
        layers = normalize_analysis_layers({"analysis_layers": ["ownership", "ownership_risk", "quant", "indicator"]})

        self.assertEqual(layers, {"ownership_risk", "quant"})

    def test_catalyst_score_rewards_event_quality_more_than_raw_count(self) -> None:
        neutral_count_only = {
            "catalysts": {
                "news": [{"title": ""}, {"title": ""}, {"title": ""}],
                "topics": [{"title": ""}, {"title": ""}, {"title": ""}],
                "filings": [{"title": ""}, {"title": ""}, {"title": ""}],
            }
        }
        positive_event = {
            "catalysts": {
                "news": [{"title": "Strong earnings growth and tight supply", "likes_count": 3}],
                "topics": [{"description": "Sector breakout with active capital inflow"}],
                "filings": [{"title": "Investment project announcement"}],
            }
        }

        self.assertGreater(score_catalysts(positive_event), score_catalysts(neutral_count_only))

    def test_run_longbridge_screen_ranks_stronger_name_first(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
            },
            runner=fake_quote_runner,
        )

        ranked = result["ranked_candidates"]
        self.assertEqual(ranked[0]["symbol"], "600111.SH")
        self.assertGreater(ranked[0]["screen_score"], ranked[1]["screen_score"])
        self.assertEqual(result["summary"]["winner"], "600111.SH")

    def test_run_longbridge_screen_adds_catalyst_and_valuation_scores(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        enrichment = candidate["longbridge_analysis"]
        self.assertEqual(candidate["symbol"], "600111.SH")
        self.assertGreater(candidate["catalyst_score"], 0)
        self.assertGreater(candidate["valuation_score"], 0)
        self.assertGreater(candidate["screen_score"], candidate["technical_score"])
        self.assertEqual(enrichment["data_coverage"]["news_count"], 1)
        self.assertEqual(enrichment["data_coverage"]["topic_count"], 1)
        self.assertEqual(enrichment["data_coverage"]["filing_count"], 1)
        self.assertIn("suggested_watchlist_bucket", candidate["tracking_plan"])
        self.assertIn("alert_suggestions", candidate["tracking_plan"])

    def test_optional_analysis_failures_do_not_block_technical_screen(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH"],
                "analysis_date": "2026-04-29",
            },
            runner=fake_optional_failure_runner,
        )

        candidate = result["ranked_candidates"][0]
        self.assertEqual(candidate["symbol"], "600111.SH")
        self.assertEqual(candidate["screen_score"], candidate["technical_score"])
        self.assertEqual(candidate["catalyst_score"], 0)
        self.assertEqual(candidate["valuation_score"], 0)
        self.assertGreaterEqual(len(candidate["longbridge_analysis"]["unavailable"]), 1)

    def test_run_longbridge_screen_emits_trade_levels(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH"],
                "analysis_date": "2026-04-29",
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        self.assertIn("trigger_price", candidate)
        self.assertIn("stop_loss", candidate)
        self.assertIn("abandon_below", candidate)
        self.assertEqual(candidate["signal"], "momentum_breakout")

    def test_build_markdown_report_mentions_ranking_and_levels(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
            },
            runner=fake_quote_runner,
        )
        report = build_markdown_report(result)

        self.assertIn("# Longbridge Screen", report)
        self.assertIn("600111.SH", report)
        self.assertIn("trigger", report.lower())
        self.assertIn("stop", report.lower())
        self.assertIn("catalyst_score", report)
        self.assertIn("valuation_score", report)
        self.assertIn("watchlist", report.lower())

    def test_screen_adds_qualitative_evaluation_omissions_and_dry_run_plan(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH", "000969.SZ"],
                "analysis_date": "2026-05-02",
                "analysis_layers": ["catalyst", "valuation", "financial_event"],
            },
            runner=fake_quote_runner,
        )

        candidates = result["ranked_candidates"]
        self.assertTrue(all("qualitative_evaluation" in item for item in candidates[:2]))
        qualitative = candidates[0]["qualitative_evaluation"]
        self.assertEqual(
            set(qualitative),
            {
                "catalyst_summary",
                "financial_report_summary",
                "cashflow_quality",
                "valuation_assessment",
                "rating_target_price_assessment",
                "filing_event_summary",
                "research_or_topic_quality",
                "key_risks",
                "qualitative_verdict",
            },
        )
        self.assertIn("cash-flow", qualitative["cashflow_quality"].lower())
        issues = {item["issue"] for item in result["missed_attention_priorities"]}
        self.assertIn("profit_cashflow_divergence", issues)
        self.assertIn("p1_intraday_non_trading_day_followup", issues)
        self.assertFalse(result["dry_run_action_plan"]["should_apply"])
        self.assertEqual(result["dry_run_action_plan"]["side_effects"], "none")
        self.assertTrue(result["dry_run_action_plan"]["actions"])

        report = build_markdown_report(result)
        self.assertIn("Qualitative Evaluation", report)
        self.assertIn("Missed Attention Priorities", report)
        self.assertIn("Dry-run Action Plan", report)

    def test_run_longbridge_screen_emits_read_only_watchlist_and_alert_suggestions(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["all"],
            },
            runner=fake_quote_runner,
        )

        account_state = result["account_state"]
        self.assertFalse(account_state["should_apply"])
        self.assertEqual(account_state["side_effects"], "none")
        self.assertTrue(account_state["data_coverage"]["watchlist_available"])
        self.assertTrue(account_state["data_coverage"]["alert_available"])
        self.assertIn("sensitive_account_data", account_state)
        suggestions = result["ranked_candidates"][0]["tracking_plan"]
        self.assertFalse(suggestions["should_apply"])
        self.assertEqual(suggestions["side_effects"], "none")
        self.assertTrue(any(item["operation"] == "add" for item in suggestions["watchlist_action_suggestions"]))
        self.assertTrue(any(item["operation"] == "enable" for item in suggestions["alert_action_suggestions"]))

    def test_run_longbridge_screen_cross_checks_portfolio_positions_and_assets(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["all"],
            },
            runner=fake_quote_runner,
        )

        inspection = result["portfolio_inspection"]
        self.assertTrue(inspection["sensitive_account_data"])
        self.assertFalse(inspection["should_apply"])
        self.assertEqual(inspection["side_effects"], "none")
        self.assertTrue(inspection["data_coverage"]["portfolio_available"])
        self.assertTrue(inspection["data_coverage"]["positions_available"])
        self.assertTrue(inspection["data_coverage"]["assets_available"])
        self.assertTrue(any(item["symbol"] == "000969.SZ" for item in inspection["held_weakening"]))
        self.assertTrue(any(item["symbol"] == "600111.SH" for item in inspection["unheld_strong_watch"]))

    def test_run_longbridge_screen_adds_intraday_confirmation_layer(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["all"],
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        confirmation = candidate["intraday_confirmation"]
        self.assertEqual(candidate["symbol"], "600111.SH")
        self.assertEqual(confirmation["side_effects"], "none")
        self.assertTrue(confirmation["data_coverage"]["capital_available"])
        self.assertTrue(confirmation["data_coverage"]["depth_available"])
        self.assertTrue(confirmation["data_coverage"]["trades_available"])
        self.assertGreater(confirmation["short_term_confirmation_score"], 0)
        self.assertGreater(candidate["workbench_score"], candidate["screen_score"])

    def test_run_longbridge_screen_adds_theme_chain_analysis(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["all"],
                "theme_indexes": ["RAREIDX.HK"],
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        chain = candidate["theme_chain_analysis"]
        self.assertEqual(candidate["symbol"], "600111.SH")
        self.assertEqual(chain["side_effects"], "none")
        self.assertTrue(chain["data_coverage"]["company_available"])
        self.assertTrue(chain["data_coverage"]["industry_valuation_available"])
        self.assertTrue(chain["data_coverage"]["constituent_available"])
        self.assertIn("RAREIDX.HK", chain["index_memberships"])
        self.assertGreater(chain["theme_chain_score"], 0)

    def test_run_longbridge_screen_adds_read_only_account_health_layer(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["000969.SZ", "600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["account_health"],
            },
            runner=fake_quote_runner,
        )

        health = result["account_health"]
        self.assertTrue(health["sensitive_account_data"])
        self.assertFalse(health["should_apply"])
        self.assertEqual(health["side_effects"], "none")
        self.assertEqual(health["statement_summary"]["latest_date"], "2026-04-29")
        self.assertEqual(health["fund_positions"][0]["symbol"], "FUND123.HK")
        self.assertTrue(health["data_coverage"]["exchange_rate_available"])
        self.assertTrue(any(item["symbol"] == "600111.SH" for item in health["symbol_margin_checks"]))
        self.assertTrue(any(item["side"] == "buy" for item in health["max_quantity_checks"]))

    def test_run_longbridge_screen_adds_event_depth_layer(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["event_depth"],
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        depth = candidate["longbridge_analysis"]["event_depth"]
        self.assertFalse(depth["should_apply"])
        self.assertEqual(depth["side_effects"], "none")
        self.assertTrue(depth["data_coverage"]["financial_report_available"])
        self.assertTrue(depth["data_coverage"]["finance_calendar_available"])
        self.assertTrue(depth["data_coverage"]["dividend_available"])
        self.assertTrue(depth["data_coverage"]["operating_available"])
        self.assertTrue(depth["data_coverage"]["news_detail_available"])
        self.assertTrue(depth["data_coverage"]["filing_detail_available"])
        self.assertEqual(depth["news_details"][0]["id"], "n1")
        self.assertEqual(depth["filing_details"][0]["id"], "f1")

    def test_run_longbridge_screen_adds_financial_event_analysis_on_candidate(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["financial_event"],
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        financial_event = candidate["financial_event_analysis"]
        self.assertFalse(financial_event["should_apply"])
        self.assertEqual(financial_event["side_effects"], "none")
        self.assertTrue(financial_event["data_coverage"]["financial_reports_available"])
        self.assertTrue(financial_event["data_coverage"]["finance_calendar_available"])
        self.assertTrue(financial_event["data_coverage"]["dividends_available"])
        self.assertTrue(financial_event["data_coverage"]["operating_metrics_available"])
        self.assertTrue(financial_event["data_coverage"]["news_details_available"])
        self.assertTrue(financial_event["data_coverage"]["filing_details_available"])
        self.assertEqual(financial_event["financial_reports"]["symbol"], "600111.SH")
        self.assertEqual(financial_event["news_details"][0]["id"], "n1")
        self.assertEqual(financial_event["filing_details"][0]["id"], "f1")

    def test_run_longbridge_screen_adds_ownership_and_quant_candidate_layers(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["TSLA.US"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["ownership_risk", "quant"],
                "investor_ciks": ["0001067983"],
                "investor_top": 3,
            },
            runner=fake_quote_runner,
        )

        candidate = result["ranked_candidates"][0]
        self.assertEqual(candidate["symbol"], "TSLA.US")
        self.assertIn("ownership_risk", result)
        self.assertIn("quant_analysis", result)
        self.assertFalse(candidate["ownership_risk_analysis"]["should_apply"])
        self.assertEqual(candidate["ownership_risk_analysis"]["side_effects"], "none")
        self.assertTrue(any(item["flag"] == "insider_sell_activity" for item in candidate["ownership_risk_analysis"]["risk_flags"]))
        self.assertEqual(candidate["quant_analysis"]["signal_alignment"]["overall"], "bullish")
        self.assertFalse(candidate["quant_analysis"]["should_apply"])
        self.assertEqual(candidate["quant_analysis"]["side_effects"], "none")

    def test_financial_event_endpoint_failures_do_not_block_screen(self) -> None:
        result = run_longbridge_screen(
            {
                "tickers": ["600111.SH"],
                "analysis_date": "2026-04-29",
                "analysis_layers": ["financial_event"],
            },
            runner=fake_financial_event_failure_runner,
        )

        candidate = result["ranked_candidates"][0]
        financial_event = candidate["financial_event_analysis"]
        self.assertEqual(candidate["symbol"], "600111.SH")
        self.assertFalse(financial_event["should_apply"])
        self.assertEqual(financial_event["side_effects"], "none")
        self.assertFalse(financial_event["data_coverage"]["financial_reports_available"])
        self.assertGreaterEqual(len(financial_event["unavailable"]), 1)


if __name__ == "__main__":
    unittest.main()
