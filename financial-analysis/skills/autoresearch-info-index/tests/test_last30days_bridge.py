#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import run_article_workflow
from last30days_bridge_runtime import run_last30days_bridge
from macro_note_workflow_runtime import run_macro_note_workflow


def sample_last30days_payload() -> dict:
    return {
        "topic": "Morgan Stanley focus list screenshots",
        "analysis_time": "2026-04-02T12:00:00+00:00",
        "results": [
            {
                "platform": "x",
                "url": "https://x.com/LinQingV/status/123",
                "summary": "Morgan Stanley focus list screenshot notes Aluminum Corp. of China Ltd. 601600.SS.",
                "post_text_raw": "Morgan Stanley focus list screenshot notes Aluminum Corp. of China Ltd. 601600.SS.",
                "author_handle": "LinQingV",
                "media_items": [
                    {
                        "source_url": "https://pbs.twimg.com/media/focus-list.jpg",
                        "ocr_text_raw": "Morgan Stanley China/HK Focus List 601600.SS",
                    }
                ],
            }
        ],
    }


class Last30DaysBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-last30days-bridge"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_last30days_bridge_imports_x_result_into_news_index_shape(self) -> None:
        result = run_last30days_bridge(sample_last30days_payload())
        self.assertEqual(result["request"]["topic"], "Morgan Stanley focus list screenshots")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(result["retrieval_request"]["candidates"][0]["origin"], "last30days")
        self.assertEqual(result["retrieval_request"]["candidates"][0]["source_type"], "social")
        self.assertEqual(result["retrieval_result"]["status"], "ok")

    def test_article_workflow_accepts_last30days_result_as_source_entry(self) -> None:
        payload = {
            "analysis_time": "2026-04-02T12:00:00+00:00",
            "topic": "Morgan Stanley focus list screenshots",
            "output_dir": str(self.temp_dir / "article-workflow"),
            "last30days_result": sample_last30days_payload(),
        }
        result = run_article_workflow(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source_stage"]["source_kind"], "last30days_bridge")
        self.assertTrue(Path(result["source_stage"]["result_path"]).exists())

    def test_macro_note_workflow_accepts_last30days_result_as_source_entry(self) -> None:
        payload = {
            "analysis_time": "2026-04-02T12:00:00+00:00",
            "topic": "Morgan Stanley focus list screenshots",
            "output_dir": str(self.temp_dir / "macro-note-workflow"),
            "last30days_result": sample_last30days_payload(),
        }
        result = run_macro_note_workflow(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source_stage"]["source_kind"], "last30days_bridge")
        self.assertTrue(Path(result["source_stage"]["result_path"]).exists())


if __name__ == "__main__":
    unittest.main()
