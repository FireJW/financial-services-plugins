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
EXAMPLES_DIR = SCRIPT_DIR.parent / "examples"
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
            template_path = EXAMPLES_DIR / "month-end-shortlist-x-style-assisted.template.json"
            request = load_json(template_path)
            request["x_style_batch_result_path"] = str(batch_path)
            normalized = normalize_request(request)
        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)
        self.assertEqual(normalized["x_style_selected_handles"], ["twikejin", "tuolaji2024"])
        self.assertEqual([item["overlay_name"] for item in normalized["x_style_overlays"]], ["x_style_twikejin", "x_style_tuolaji2024"])

    def test_normalize_request_derives_event_discovery_candidates_from_x_batch_result(self) -> None:
        cache_dir = Path.cwd() / ".tmp" / "test-x-style-discovery-candidates"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        batch_path = cache_dir / "batch-result.json"
        batch_payload = {
            "subject_runs": [
                {
                    "subject": {"handle": "twikejin"},
                    "overlay_pack": {"overlay_name": "x_style_twikejin"},
                    "recommendation_ledger": [
                        {
                            "classification": "direct_pick",
                            "strength": "strong_direct",
                            "names": ["东山精密"],
                            "sector_or_chain": "electronic_cloth",
                            "catalyst_type": "earnings",
                            "thesis_excerpt": "东山精密Q1净利预增，核心股。",
                            "status_url": "https://x.com/twikejin/status/2041534482210242629",
                            "scored_names": [{"name": "东山精密", "ticker": "002384.SZ"}],
                        }
                    ],
                }
            ]
        }
        try:
            batch_path.write_text(json.dumps(batch_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            request = {
                "template_name": "month_end_shortlist",
                "target_date": "2026-04-30",
                "x_style_batch_result_path": str(batch_path),
                "x_style_selected_handles": ["twikejin"],
            }
            normalized = normalize_request(request)
        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)

        self.assertEqual(normalized["event_discovery_candidates"][0]["ticker"], "002384.SZ")
        self.assertEqual(normalized["event_discovery_candidates"][0]["event_type"], "earnings")

    def test_normalize_request_derives_event_discovery_candidates_from_x_discovery_request(self) -> None:
        request = {
            "template_name": "month_end_shortlist",
            "target_date": "2026-04-30",
            "x_discovery_request": {
                "subject": {"handle": "twikejin"},
                "candidate_names": ["东山精密"],
                "source_board_seed": {
                    "source_board": [
                        {
                            "status_url": "https://x.com/twikejin/status/2041534482210242629",
                            "status_id": "2041534482210242629",
                            "author_handle": "twikejin",
                            "published_at": "2026-04-07T02:00:00+00:00",
                            "direct_text": "东山精密(002384)Q1净利预增119%-152%，第一目标市值仍有翻倍空间。核心股(东山精密)。",
                            "direct_text_kind": "raw_post_text"
                        }
                    ]
                }
            },
        }

        normalized = normalize_request(request)

        self.assertEqual(normalized["event_discovery_candidates"][0]["ticker"], "002384.SZ")
        self.assertEqual(normalized["event_discovery_candidates"][0]["chain_role"], "direct_pick")


if __name__ == "__main__":
    unittest.main()
