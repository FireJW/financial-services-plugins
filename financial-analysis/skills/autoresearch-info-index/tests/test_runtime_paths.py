#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_paths import resolve_runtime_root


class RuntimePathsTests(unittest.TestCase):
    def test_resolve_runtime_root_falls_back_when_env_root_is_not_usable(self) -> None:
        fallback = (Path.cwd() / ".tmp").resolve()
        with patch.dict(os.environ, {"FINANCIAL_ANALYSIS_RUNTIME_ROOT": r"D:\Users\rickylu\codex-runtime\financial-services-plugins"}, clear=False):
            with patch("runtime_paths.is_usable_runtime_root", return_value=False):
                self.assertEqual(resolve_runtime_root(), fallback)

    def test_resolve_runtime_root_preserves_explicit_path(self) -> None:
        explicit = Path(".tmp/runtime-paths-explicit").resolve()
        with patch.dict(os.environ, {"FINANCIAL_ANALYSIS_RUNTIME_ROOT": r"D:\Users\rickylu\codex-runtime\financial-services-plugins"}, clear=False):
            with patch("runtime_paths.is_usable_runtime_root", return_value=False):
                self.assertEqual(resolve_runtime_root(str(explicit)), explicit)


if __name__ == "__main__":
    unittest.main()
