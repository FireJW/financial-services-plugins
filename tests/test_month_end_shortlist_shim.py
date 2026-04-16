#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
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

import month_end_shortlist as cli_module
import month_end_shortlist_runtime as runtime_module


class MonthEndShortlistShimTests(unittest.TestCase):
    def test_runtime_exports_normalize_request(self) -> None:
        self.assertTrue(callable(getattr(runtime_module, "normalize_request", None)))

    def test_cli_exports_main(self) -> None:
        self.assertTrue(callable(getattr(cli_module, "main", None)))

    def test_cli_main_routes_through_wrapper_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            request_path = tmp_path / "request.json"
            output_path = tmp_path / "result.json"
            markdown_path = tmp_path / "report.md"
            request_path.write_text('{"template_name":"month_end_shortlist","target_date":"2026-04-17"}', encoding="utf-8")

            fake_result = {"status": "ok", "report_markdown": "# wrapped\n"}
            with (
                patch.object(cli_module, "load_compiled_module", return_value=object()),
                patch("month_end_shortlist_runtime.load_json", return_value={"template_name": "month_end_shortlist"}),
                patch("month_end_shortlist_runtime.run_month_end_shortlist", return_value=fake_result) as run_mock,
            ):
                exit_code = cli_module.main(
                    [
                        str(request_path),
                        "--output",
                        str(output_path),
                        "--markdown-output",
                        str(markdown_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with({"template_name": "month_end_shortlist"})
            self.assertTrue(output_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertIn("# wrapped", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
