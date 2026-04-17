from __future__ import annotations

import sys
import unittest
import shutil
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

import macro_health_assisted_shortlist as module_under_test


class MacroHealthAssistedShortlistTests(unittest.TestCase):
    def test_parse_args_allows_omitting_macro_request(self) -> None:
        args = module_under_test.parse_args(["base.json"])
        self.assertEqual(args.shortlist_request_json, "base.json")
        self.assertEqual(args.macro_health_request_json, "")

    def test_default_macro_request_template_exists(self) -> None:
        self.assertTrue(module_under_test.DEFAULT_MACRO_HEALTH_REQUEST.exists())

    def test_main_uses_default_macro_request_when_omitted(self) -> None:
        loaded_paths: list[Path] = []
        writes: list[tuple[Path, dict]] = []

        def fake_load_json(path: Path) -> dict:
            loaded_paths.append(path)
            if path == Path("C:/base.json"):
                return {"template_name": "month_end_shortlist"}
            if path == module_under_test.DEFAULT_MACRO_HEALTH_REQUEST:
                return {"live_data_provider": "public_macro_mix"}
            raise AssertionError(path)

        def fake_build_macro_health_overlay_result(request: dict) -> dict:
            self.assertEqual(request["live_data_provider"], "public_macro_mix")
            return {"macro_health_overlay": {"health_label": "mixed_or_neutral_window"}}

        def fake_run_month_end_shortlist(request: dict) -> dict:
            self.assertEqual(request["macro_health_overlay"]["health_label"], "mixed_or_neutral_window")
            return {"request": request, "report_markdown": "# ok\n"}

        def fake_write_json(path: Path, payload: dict) -> None:
            writes.append((path, payload))

        with patch.object(module_under_test, "load_json", side_effect=fake_load_json), patch.object(
            module_under_test, "build_macro_health_overlay_result", side_effect=fake_build_macro_health_overlay_result
        ), patch.object(module_under_test, "run_month_end_shortlist", side_effect=fake_run_month_end_shortlist), patch.object(
            module_under_test, "write_json", side_effect=fake_write_json
        ):
            exit_code = module_under_test.main(
                ["C:/base.json", "--output", "C:/out.json", "--overlay-output", "C:/overlay.json", "--resolved-request-output", "C:/resolved.json"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded_paths[0], Path("C:/base.json"))
        self.assertEqual(loaded_paths[1], module_under_test.DEFAULT_MACRO_HEALTH_REQUEST)
        self.assertEqual(len(writes), 3)

    def test_main_can_also_merge_sentiment_overlay_when_requested(self) -> None:
        loaded_paths: list[Path] = []
        writes: list[tuple[Path, dict]] = []

        def fake_load_json(path: Path) -> dict:
            loaded_paths.append(path)
            if path == Path("C:/base.json"):
                return {"template_name": "month_end_shortlist"}
            if path == module_under_test.DEFAULT_MACRO_HEALTH_REQUEST:
                return {"live_data_provider": "public_macro_mix"}
            if path == Path("C:/sentiment.json"):
                return {"broad_iv_percentile": 44.0, "growth_iv_percentile": 94.0, "skew_percentile": 90.0}
            raise AssertionError(path)

        def fake_build_macro_health_overlay_result(request: dict) -> dict:
            return {"macro_health_overlay": {"health_label": "mixed_or_neutral_window"}}

        def fake_build_a_share_sentiment_overlay_result(request: dict) -> dict:
            self.assertEqual(request["growth_iv_percentile"], 94.0)
            return {"sentiment_vol_overlay": {"sentiment_regime": "panic_in_growth_not_broad_market"}}

        def fake_run_month_end_shortlist(request: dict) -> dict:
            self.assertEqual(request["macro_health_overlay"]["health_label"], "mixed_or_neutral_window")
            self.assertEqual(request["sentiment_vol_overlay"]["sentiment_regime"], "panic_in_growth_not_broad_market")
            return {"request": request, "report_markdown": "# ok\n"}

        def fake_write_json(path: Path, payload: dict) -> None:
            writes.append((path, payload))

        with patch.object(module_under_test, "load_json", side_effect=fake_load_json), patch.object(
            module_under_test, "build_macro_health_overlay_result", side_effect=fake_build_macro_health_overlay_result
        ), patch.object(
            module_under_test, "build_a_share_sentiment_overlay_result", side_effect=fake_build_a_share_sentiment_overlay_result
        ), patch.object(module_under_test, "run_month_end_shortlist", side_effect=fake_run_month_end_shortlist), patch.object(
            module_under_test, "write_json", side_effect=fake_write_json
        ):
            exit_code = module_under_test.main(
                [
                    "C:/base.json",
                    "--output",
                    "C:/out.json",
                    "--overlay-output",
                    "C:/overlay.json",
                    "--resolved-request-output",
                    "C:/resolved.json",
                    "--sentiment-request-json",
                    "C:/sentiment.json",
                    "--sentiment-output",
                    "C:/sentiment-out.json",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded_paths[0], Path("C:/base.json"))
        self.assertEqual(loaded_paths[1], module_under_test.DEFAULT_MACRO_HEALTH_REQUEST)
        self.assertEqual(loaded_paths[2], Path("C:/sentiment.json"))
        self.assertEqual(len(writes), 4)

    def test_main_writes_markdown_output_with_utf8_bom(self) -> None:
        tmp_path = Path.cwd() / ".tmp" / "test-macro-health-markdown-bom"
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_request = tmp_path / "base.json"
            macro_request = tmp_path / "macro.json"
            markdown_path = tmp_path / "report.md"
            base_request.write_text('{"template_name":"month_end_shortlist","target_date":"2026-04-30"}', encoding="utf-8")
            macro_request.write_text('{"live_data_provider":"public_macro_mix"}', encoding="utf-8")

            with (
                patch.object(module_under_test, "load_json", side_effect=[{"template_name": "month_end_shortlist"}, {"live_data_provider": "public_macro_mix"}]),
                patch.object(module_under_test, "build_macro_health_overlay_result", return_value={"macro_health_overlay": {"health_label": "mixed"}}),
                patch.object(module_under_test, "run_month_end_shortlist", return_value={"report_markdown": "# macro\n"}),
            ):
                exit_code = module_under_test.main(
                    [
                        str(base_request),
                        str(macro_request),
                        "--markdown-output",
                        str(markdown_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(markdown_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertIn("# macro", markdown_path.read_text(encoding="utf-8-sig"))
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
