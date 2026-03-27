#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_auto_queue_runtime import run_article_auto_queue
from article_batch_workflow_runtime import run_article_batch_workflow
from news_index_core import read_json


def build_seed_x_request(tmpdir: Path) -> dict:
    tmpdir.mkdir(parents=True, exist_ok=True)
    screenshot_path = tmpdir / "root.png"
    media_path = tmpdir / "airlift.png"
    screenshot_path.write_bytes(b"root")
    media_path.write_bytes(b"seed-image")
    return {
        "topic": "US military airlift chatter",
        "analysis_time": "2026-03-24T12:00:00+00:00",
        "claims": [
            {
                "claim_id": "claim-airlift",
                "claim_text": "A significant movement from CONUS to the Middle East is underway.",
            }
        ],
        "seed_posts": [
            {
                "post_url": "https://x.com/sentdefender/status/2036153038906196133",
                "html": """
                    <html>
                      <head>
                        <meta property="og:title" content="SentDefender on X">
                        <meta property="og:description" content="A significant movement is underway from US Army, Navy and Air Force bases in CONUS to the Middle East comprised of at least 35 C-17 flights since March 12th.">
                        <meta property="og:image" content="https://pbs.twimg.com/media/test-airlift.jpg">
                      </head>
                      <body>
                        <time datetime="2026-03-24T09:30:00+00:00"></time>
                      </body>
                    </html>
                """,
                "root_post_screenshot_path": str(screenshot_path),
                "media_items": [
                    {
                        "source_url": "file://" + str(media_path.resolve()).replace("\\", "/"),
                        "ocr_text_raw": "Origins: Hunter Army Air Field. Destinations: Ovda Air Base.",
                    }
                ],
                "engagement": {"views": 1500000, "likes": 32000, "reposts": 11000, "replies": 4200},
            }
        ],
    }


class ArticleBatchOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.news_request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.temp_root = Path.cwd() / ".tmp" / "article-batch-optimizations"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_batch_workflow_accepts_inline_payloads_and_keeps_candidate_index(self) -> None:
        batch_dir = self.case_dir("batch-inline-payload")
        result = run_article_batch_workflow(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(batch_dir / "out"),
                "items": [
                    {
                        "candidate_index": 7,
                        "label": "news-inline",
                        "payload": self.news_request,
                    }
                ],
            }
        )
        self.assertEqual(result["succeeded_items"], 1)
        self.assertEqual(result["items"][0]["candidate_index"], 7)
        self.assertEqual(result["items"][0]["source_request_path"], "")
        self.assertTrue(Path(result["items"][0]["workflow_result_path"]).exists())

    def test_auto_queue_passes_selected_source_payloads_inline_without_temp_source_files(self) -> None:
        auto_dir = self.case_dir("auto-inline-payload")
        result = run_article_auto_queue(
            {
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "output_dir": str(auto_dir / "out"),
                "top_n": 1,
                "prefer_visuals": True,
                "candidates": [
                    {
                        "label": "x-candidate",
                        "payload": build_seed_x_request(auto_dir / "x-candidate"),
                    },
                    {
                        "label": "news-candidate",
                        "payload": self.news_request,
                    },
                ],
            }
        )
        batch_request = read_json(Path(result["batch_request_path"]))
        self.assertEqual(len(batch_request["items"]), 1)
        self.assertIn("payload", batch_request["items"][0])
        self.assertNotIn("request_path", batch_request["items"][0])
        self.assertEqual(batch_request["items"][0]["candidate_index"], result["ranked_candidates"][0]["index"])
        self.assertFalse(list((auto_dir / "out" / "sources").glob("*source-result.json")))


if __name__ == "__main__":
    unittest.main()
