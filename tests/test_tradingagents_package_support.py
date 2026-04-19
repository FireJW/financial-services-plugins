#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

from tradingagents_package_support import clean_text, package_origin, probe_runtime_imports, resolve_package_version


class TradingAgentsPackageSupportTests(unittest.TestCase):
    def test_clean_text_collapses_whitespace(self) -> None:
        self.assertEqual(clean_text("  alpha \u200b beta\n gamma  "), "alpha beta gamma")

    def test_package_origin_prefers_spec_origin(self) -> None:
        spec = SimpleNamespace(
            origin="C:\\operator\\TradingAgents\\tradingagents\\__init__.py",
            submodule_search_locations=["C:\\operator\\TradingAgents\\tradingagents"],
        )

        self.assertEqual(package_origin(spec), "C:\\operator\\TradingAgents\\tradingagents\\__init__.py")

    def test_resolve_package_version_prefers_explicit_lookup(self) -> None:
        self.assertEqual(
            resolve_package_version("tradingagents", version_lookup=lambda _: "0.2.3"),
            "0.2.3",
        )

    def test_resolve_package_version_reads_dunder_version_from_init_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir) / "tradingagents"
            init_path = package_dir / "__init__.py"
            package_dir.mkdir(parents=True, exist_ok=True)
            init_path.write_text('__version__ = "0.2.3"\n', encoding="utf-8")
            spec = SimpleNamespace(origin=str(init_path), submodule_search_locations=[str(package_dir)])

            self.assertEqual(resolve_package_version("tradingagents", spec=spec), "0.2.3")

    def test_probe_runtime_imports_reports_import_failure(self) -> None:
        with patch("tradingagents_package_support.import_module", side_effect=ModuleNotFoundError("crewai")):
            ok, error = probe_runtime_imports()

        self.assertFalse(ok)
        self.assertIn("crewai", error)


if __name__ == "__main__":
    unittest.main()
