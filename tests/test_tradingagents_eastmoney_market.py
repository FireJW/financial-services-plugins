#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_eastmoney_market import (
    _RETRY_ATTEMPTS,
    cache_path,
    eastmoney_api_request,
    eastmoney_hk_secid,
    eastmoney_secid,
    fetch_hk_quote_snapshot,
    get_indicator,
    get_stock_data,
    normalize_eastmoney_hk_symbol,
    normalize_eastmoney_symbol,
)


def build_kline_payload(secid: str, start_date: str, count: int) -> dict[str, object]:
    start = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    rows: list[str] = []
    close = 10.0
    for offset in range(count):
        trade_date = start + dt.timedelta(days=offset)
        open_price = close
        high = close + 0.8
        low = close - 0.6
        close = close + 0.2
        pre_close = close - 0.2
        change = close - pre_close
        pct_chg = (change / pre_close) * 100 if pre_close else 0
        vol = 1000 + offset
        amount = 5000 + offset * 10
        amplitude = ((high - low) / pre_close) * 100 if pre_close else 0
        turnover = 1.0 + offset * 0.01
        rows.append(
            ",".join(
                [
                    trade_date.strftime("%Y-%m-%d"),
                    f"{open_price:.4f}",
                    f"{close:.4f}",
                    f"{high:.4f}",
                    f"{low:.4f}",
                    f"{vol:.4f}",
                    f"{amount:.4f}",
                    f"{amplitude:.4f}",
                    f"{pct_chg:.4f}",
                    f"{change:.4f}",
                    f"{turnover:.4f}",
                ]
            )
        )
    return {
        "rc": 0,
        "data": {
            "code": secid.split(".", 1)[1],
            "market": int(secid.split(".", 1)[0]),
            "name": "测试样本",
            "klines": rows,
        },
    }


def fake_fetcher(params: dict[str, object], max_age_seconds: int, env: dict[str, str] | None = None) -> dict[str, object]:
    del max_age_seconds, env
    return build_kline_payload(str(params["secid"]), "2024-01-01", 320)


def fake_hk_quote_fetcher(params: dict[str, object], max_age_seconds: int, env: dict[str, str] | None = None) -> dict[str, object]:
    del max_age_seconds, env
    return {
        "rc": 0,
        "data": {
            "f43": 489200,
            "f57": "00700",
            "f58": "腾讯控股",
        },
    }


class TradingAgentsEastmoneyMarketTests(unittest.TestCase):
    def test_normalize_eastmoney_symbol_maps_ss_to_sh(self) -> None:
        self.assertEqual(normalize_eastmoney_symbol("601600.SS"), "601600.SH")
        self.assertEqual(normalize_eastmoney_symbol("002837.SZ"), "002837.SZ")

    def test_normalize_eastmoney_symbol_rejects_us_ticker(self) -> None:
        with self.assertRaises(ValueError):
            normalize_eastmoney_symbol("NVDA")

    def test_eastmoney_secid_maps_market_prefix(self) -> None:
        self.assertEqual(eastmoney_secid("601600.SS"), "1.601600")
        self.assertEqual(eastmoney_secid("002837.SZ"), "0.002837")

    def test_normalize_eastmoney_hk_symbol_zero_pads(self) -> None:
        self.assertEqual(normalize_eastmoney_hk_symbol("700.HK"), "00700.HK")

    def test_eastmoney_hk_secid_uses_hk_market_prefix(self) -> None:
        self.assertEqual(eastmoney_hk_secid("00700.HK"), "116.00700")

    def test_cache_path_sanitizes_windows_unsafe_characters(self) -> None:
        path = cache_path('kline-{"secid": "1.601600", "beg": "20260301"}.json')
        self.assertNotIn('"', str(path))
        self.assertTrue(path.name.endswith(".json"))

    def test_get_stock_data_renders_csv(self) -> None:
        report = get_stock_data(
            "601600.SS",
            "2024-01-01",
            "2024-12-31",
            fetcher=fake_fetcher,
        )

        self.assertIn("# Stock data for 601600.SH", report)
        self.assertIn("Date,Open,High,Low,Close,PreClose,Change,PctChg,Volume,Amount", report)
        self.assertIn("2024-01-01", report)

    def test_get_indicator_renders_50_sma_values(self) -> None:
        report = get_indicator(
            "601600.SS",
            "close_50_sma",
            "2024-11-15",
            30,
            fetcher=fake_fetcher,
        )

        self.assertIn("## close_50_sma values", report)
        self.assertIn("2024-11-15", report)
        self.assertIn("50 SMA", report)

    def test_get_indicator_renders_macd_values(self) -> None:
        report = get_indicator(
            "601600.SS",
            "macd",
            "2024-11-15",
            20,
            fetcher=fake_fetcher,
        )

        self.assertIn("## macd values", report)
        self.assertIn("MACD", report)

    def test_fetch_hk_quote_snapshot_parses_price_and_name(self) -> None:
        snapshot = fetch_hk_quote_snapshot(
            "00700.HK",
            fetcher=fake_hk_quote_fetcher,
        )

        self.assertEqual(snapshot["symbol"], "00700.HK")
        self.assertEqual(snapshot["name"], "腾讯控股")
        self.assertEqual(snapshot["last_price"], 489.2)

    def test_fetch_hk_quote_snapshot_rejects_non_hk_symbol(self) -> None:
        with self.assertRaises(ValueError):
            fetch_hk_quote_snapshot("AAPL", fetcher=fake_hk_quote_fetcher)


class EastmoneyRetryTests(unittest.TestCase):
    """Tests for retry logic in eastmoney_api_request()."""

    VALID_PAYLOAD = '{"rc": 0, "data": {"klines": ["2026-04-22,10,11,12,9,1000,5000,5.0,2.0,0.2,1.0"]}}'

    @patch("tradingagents_eastmoney_market.write_cached_json")
    @patch("tradingagents_eastmoney_market.read_cached_json", return_value=None)
    @patch("tradingagents_eastmoney_market.time.sleep")
    @patch("tradingagents_eastmoney_market.urlopen")
    def test_retries_on_transport_error(self, mock_urlopen, mock_sleep, _mock_cache_read, _mock_cache_write) -> None:
        """urlopen fails twice with URLError, succeeds on 3rd attempt."""
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = self.VALID_PAYLOAD.encode("utf-8")

        mock_urlopen.side_effect = [
            URLError("Connection reset"),
            URLError("Connection reset"),
            mock_response,
        ]

        result = eastmoney_api_request({"secid": "1.600105"}, 3600)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("tradingagents_eastmoney_market.read_cached_json", return_value=None)
    @patch("tradingagents_eastmoney_market.time.sleep")
    @patch("tradingagents_eastmoney_market.urlopen")
    def test_no_retry_on_4xx(self, mock_urlopen, mock_sleep, _mock_cache_read) -> None:
        """4xx HTTP errors should fail immediately without retry."""
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com", code=403, msg="Forbidden",
            hdrs=None, fp=io.BytesIO(b""),  # type: ignore[arg-type]
        )

        with self.assertRaises(RuntimeError) as ctx:
            eastmoney_api_request({"secid": "1.600105"}, 3600)
        self.assertIn("HTTP 403", str(ctx.exception))
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("tradingagents_eastmoney_market.write_cached_json")
    @patch("tradingagents_eastmoney_market.read_cached_json", return_value=None)
    @patch("tradingagents_eastmoney_market.time.sleep")
    @patch("tradingagents_eastmoney_market.urlopen")
    def test_retries_on_5xx(self, mock_urlopen, mock_sleep, _mock_cache_read, _mock_cache_write) -> None:
        """5xx HTTP errors should be retried."""
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = self.VALID_PAYLOAD.encode("utf-8")

        mock_urlopen.side_effect = [
            HTTPError(url="https://example.com", code=502, msg="Bad Gateway",
                      hdrs=None, fp=io.BytesIO(b"")),  # type: ignore[arg-type]
            HTTPError(url="https://example.com", code=503, msg="Service Unavailable",
                      hdrs=None, fp=io.BytesIO(b"")),  # type: ignore[arg-type]
            mock_response,
        ]

        result = eastmoney_api_request({"secid": "1.600105"}, 3600)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("tradingagents_eastmoney_market.read_cached_json", return_value=None)
    @patch("tradingagents_eastmoney_market.time.sleep")
    @patch("tradingagents_eastmoney_market.urlopen")
    def test_fails_after_max_retries(self, mock_urlopen, mock_sleep, _mock_cache_read) -> None:
        """After exhausting all retry attempts, should raise RuntimeError."""
        mock_urlopen.side_effect = URLError("Connection reset")

        with self.assertRaises(RuntimeError) as ctx:
            eastmoney_api_request({"secid": "1.600105"}, 3600)
        self.assertIn(f"after {_RETRY_ATTEMPTS} attempts", str(ctx.exception))
        self.assertEqual(mock_urlopen.call_count, _RETRY_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, _RETRY_ATTEMPTS - 1)


if __name__ == "__main__":
    unittest.main()
