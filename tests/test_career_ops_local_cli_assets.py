from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "career-ops-local"
    / "skills"
    / "career-ops-bridge"
    / "scripts"
)
EXAMPLES_DIR = (
    Path(__file__).resolve().parents[1]
    / "career-ops-local"
    / "skills"
    / "career-ops-bridge"
    / "examples"
)
CLI_PATH = SCRIPTS_DIR / "career_ops_local.py"
TRACK_TEMPLATE_PATH = EXAMPLES_DIR / "job-track-request.template.json"


class CareerOpsLocalCliAssetTests(unittest.TestCase):
    def load_cli_module(self):
        self.assertTrue(CLI_PATH.exists(), f"Missing CLI entrypoint: {CLI_PATH}")

        module_name = "career_ops_local_cli_under_test"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(module_name, CLI_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_json_template(self, path: Path) -> dict[str, object]:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # pragma: no cover - failure path is asserted via self.fail
            self.fail(f"{path.name} should be valid JSON: {exc}")

    def test_parse_args_accepts_request_and_optional_outputs(self) -> None:
        module_under_test = self.load_cli_module()

        args = module_under_test.parse_args(
            [
                "request.json",
                "--output",
                "result.json",
                "--markdown-output",
                "report.md",
            ]
        )

        self.assertEqual(args.request, "request.json")
        self.assertEqual(args.output, "result.json")
        self.assertEqual(args.markdown_output, "report.md")

    def test_main_writes_result_json_and_markdown_outputs(self) -> None:
        module_under_test = self.load_cli_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            request_path = tmp_root / "request.json"
            output_path = tmp_root / "result.json"
            report_path = tmp_root / "report.md"
            request_payload = {"task": "match"}
            result_payload = {
                "task": "match",
                "status": "ready",
                "report_markdown": "# ok\n",
            }
            request_path.write_text(json.dumps(request_payload), encoding="utf-8")

            writes: list[tuple[str, Path, object]] = []

            def fake_write_json(path: Path, payload: dict[str, object]) -> None:
                writes.append(("json", path, payload))

            def fake_write_text(path: Path, payload: str) -> None:
                writes.append(("text", path, payload))

            with patch.object(
                module_under_test,
                "run_career_ops_local",
                return_value=result_payload,
            ) as run_mock, patch.object(
                module_under_test,
                "write_json",
                side_effect=fake_write_json,
            ), patch.object(
                module_under_test,
                "write_text",
                side_effect=fake_write_text,
            ):
                exit_code = module_under_test.main(
                    [
                        str(request_path),
                        "--output",
                        str(output_path),
                        "--markdown-output",
                        str(report_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once_with(request_payload)
        self.assertIn(("json", output_path.resolve(), result_payload), writes)
        self.assertIn(("text", report_path.resolve(), "# ok\n"), writes)

    def test_job_track_request_template_is_valid_json(self) -> None:
        request = self.load_json_template(TRACK_TEMPLATE_PATH)

        self.assertEqual(request["task"], "track")
        self.assertEqual(request["application_status"], "applied")
        self.assertIn("tracker_path", request)
        self.assertIn("status_note", request)


if __name__ == "__main__":
    unittest.main()
