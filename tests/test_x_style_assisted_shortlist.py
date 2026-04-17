from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from x_style_assisted_shortlist import build_x_style_assisted_request, normalize_handle_list
from month_end_shortlist_runtime import load_json, normalize_request


class XStyleAssistedShortlistTests(unittest.TestCase):
    def test_normalize_handle_list_dedupes_and_strips_prefixes(self) -> None:
        self.assertEqual(
            normalize_handle_list(["@twikejin", "tuolaji2024, @twikejin"]),
            ["twikejin", "tuolaji2024"],
        )

    def test_build_x_style_assisted_request_injects_batch_path_and_handles(self) -> None:
        request = build_x_style_assisted_request(
            {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-30",
            },
            x_style_batch_result_path="C:\\temp\\batch.json",
            selected_handles=["@twikejin", "tuolaji2024"],
            analysis_time="2026-04-10T15:30:00+08:00",
        )
        self.assertEqual(request["x_style_batch_result_path"], "C:\\temp\\batch.json")
        self.assertEqual(request["x_style_selected_handles"], ["twikejin", "tuolaji2024"])
        self.assertEqual(request["analysis_time"], "2026-04-10T15:30:00+08:00")

    def test_new_template_resolves_x_style_overlays_from_batch_result(self) -> None:
        cache_dir = Path.cwd() / ".tmp" / "test-x-style-assisted-shortlist"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        batch_path = cache_dir / "batch-result.json"
        batch_payload = {
            "subject_runs": [
                {
                    "subject": {"handle": "twikejin"},
                    "overlay_pack": {"overlay_name": "x_style_twikejin", "theme_biases": [{"theme": "electronic_cloth", "weight": 2}]},
                },
                {
                    "subject": {"handle": "tuolaji2024"},
                    "overlay_pack": {"overlay_name": "x_style_tuolaji2024", "theme_biases": [{"theme": "optical_interconnect", "weight": 8}]},
                },
            ]
        }
        try:
            batch_path.write_text(json.dumps(batch_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            template_path = Path(
                "financial-analysis/skills/month-end-shortlist/examples/month-end-shortlist-x-style-assisted.template.json"
            )
            request = load_json(template_path)
            request["x_style_batch_result_path"] = str(batch_path)
            normalized = normalize_request(request)
        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)
        self.assertEqual(normalized["x_style_selected_handles"], ["twikejin", "tuolaji2024"])
        self.assertEqual([item["overlay_name"] for item in normalized["x_style_overlays"]], ["x_style_twikejin", "x_style_tuolaji2024"])


if __name__ == "__main__":
    unittest.main()
