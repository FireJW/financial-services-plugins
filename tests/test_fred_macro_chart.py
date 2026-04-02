#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fred_macro_chart import generate_gold_pricing_chart, load_api_key
from stock_watch_workflow import render_nightly_summary_markdown


SERIES_VALUES = {
    "DFII10": {
        "2026-03-30": 1.15,
        "2026-03-31": 1.04,
        "2026-04-01": 0.95,
    },
    "THREEFYTP10": {
        "2026-03-30": 0.41,
        "2026-03-31": 0.39,
        "2026-04-01": 0.36,
    },
    "DFII5": {
        "2026-03-30": 0.88,
        "2026-03-31": 0.82,
        "2026-04-01": 0.79,
    },
}


def fake_fetcher(url: str) -> dict[str, object]:
    query = parse_qs(urlparse(url).query)
    series_id = query["series_id"][0]
    observations = [
        {"date": observed_date, "value": str(value)}
        for observed_date, value in SERIES_VALUES[series_id].items()
    ]
    return {"observations": observations}


class FredMacroChartTests(unittest.TestCase):
    def test_load_api_key_falls_back_to_windows_user_env(self) -> None:
        with patch.dict(os.environ, {"FRED_API_KEY": ""}, clear=False):
            with patch("fred_macro_chart.load_windows_user_env", return_value="registry-key"):
                self.assertEqual(load_api_key(), "registry-key")

    def test_generate_gold_pricing_chart_skips_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FRED_API_KEY": ""}, clear=False):
                with patch("fred_macro_chart.load_windows_user_env", return_value=""):
                    payload = generate_gold_pricing_chart(Path(tmpdir))

        self.assertEqual(payload["status"], "skipped")
        self.assertIn("FRED_API_KEY", payload["reason"])

    def test_generate_gold_pricing_chart_writes_svg_and_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ,
                {
                    "FRED_API_KEY": "test-key",
                    "STOCK_WATCH_FRED_START_DATE": "2026-03-30",
                    "STOCK_WATCH_FRED_END_DATE": "2026-04-01",
                    "STOCK_WATCH_FRED_TITLE": "Gold Pricing: Three-Layer Structure",
                },
                clear=False,
            ):
                payload = generate_gold_pricing_chart(Path(tmpdir), fetcher=fake_fetcher)

            chart_path = Path(payload["chart_path"])
            summary_path = Path(payload["summary_path"])
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(chart_path.exists())
            self.assertTrue(summary_path.exists())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["actual_start_date"], "2026-03-30")
            self.assertEqual(summary_payload["actual_end_date"], "2026-04-01")
            self.assertEqual(summary_payload["point_count"], 3)
            self.assertEqual(
                summary_payload["latest_values"]["10Y Real Yield (Core)"]["latest_value"],
                0.95,
            )
            svg = chart_path.read_text(encoding="utf-8")
            self.assertIn("Gold Pricing: Three-Layer Structure", svg)
            self.assertIn("10Y Real Yield (Core)", svg)
            self.assertIn("10Y Term Premium (Risk)", svg)
            self.assertIn("5Y Real Yield (Policy)", svg)

    def test_render_nightly_summary_markdown_includes_macro_chart_section(self) -> None:
        payload = {
            "refreshed_at": "2026-04-02T13:00:00+00:00",
            "stock_count": 1,
            "workflow_summary": {
                "execution_mode_requested": "auto",
                "total_new_external_sources": 1,
                "total_new_sources": 2,
                "total_new_baseline_sources": 1,
                "one_line": "Nightly summary looks healthy.",
            },
            "gs_quant_postprocess": {"status": "ready"},
            "macro_chart": {
                "status": "ok",
                "chart_path": "C:/tmp/gold_pricing_three_layer.svg",
                "summary_path": "C:/tmp/gold_pricing_three_layer.json",
                "actual_start_date": "2026-03-30",
                "actual_end_date": "2026-04-01",
                "one_line": "10Y Real Yield (Core) 0.95 (2026-04-01)",
            },
            "stocks": [
                {
                    "stock": {"name": "中国铝业", "ticker": "601600.SH"},
                    "workflow_summary": {
                        "one_line": "No fresh filings.",
                        "total_new_sources": 0,
                        "total_new_baseline_sources": 0,
                        "total_new_external_sources": 0,
                    },
                }
            ],
            "compare_note_path": "C:/tmp/compare.md",
            "gs_quant_summary_path": "C:/tmp/gs_quant_summary.md",
        }

        markdown = render_nightly_summary_markdown(payload)

        self.assertIn("- FRED 宏观图表: `ok`", markdown)
        self.assertIn("## 宏观图表", markdown)
        self.assertIn("- 图表: `C:/tmp/gold_pricing_three_layer.svg`", markdown)
        self.assertIn("- 摘要文件: `C:/tmp/gold_pricing_three_layer.json`", markdown)
        self.assertIn("- 实际日期范围: `2026-03-30` to `2026-04-01`", markdown)
        self.assertIn("- 快照: 10Y Real Yield (Core) 0.95 (2026-04-01)", markdown)


if __name__ == "__main__":
    unittest.main()



