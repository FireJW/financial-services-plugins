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
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import tradingagents_decision_bridge_runtime as module_under_test


class TradingAgentsLongbridgeIntegrationTests(unittest.TestCase):
    def test_profile_presets_include_longbridge_market(self) -> None:
        preset = module_under_test.ANALYSIS_PROFILE_PRESETS["longbridge_market"]

        self.assertEqual(preset["selected_analysts"], ["market"])
        self.assertEqual(preset["data_vendors"]["core_stock_apis"], "longbridge_market")
        self.assertEqual(preset["tool_vendors"]["get_stock_data"], "longbridge_market")

    def test_smart_free_prefers_longbridge_when_authenticated(self) -> None:
        with patch.object(module_under_test, "longbridge_available", return_value=True):
            self.assertEqual(module_under_test.smart_free_profile_name("AAPL.US"), "longbridge_market")
            self.assertEqual(module_under_test.smart_free_profile_name("601600.SH"), "longbridge_market")
            self.assertEqual(module_under_test.smart_free_profile_name("00700.HK"), "longbridge_market")

    def test_market_snapshot_profile_accepts_explicit_longbridge_profile(self) -> None:
        profile = module_under_test.market_snapshot_profile_name(
            {"analysis_profile": "longbridge_market"},
            "AAPL.US",
        )

        self.assertEqual(profile, "longbridge_market")


if __name__ == "__main__":
    unittest.main()
