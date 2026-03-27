#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_draft_flow_runtime import build_article_draft, localize_selected_images
from article_revise_flow_runtime import build_article_revision
from news_index_core import run_news_index


class ArticleImageLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path.cwd() / ".tmp" / "article-image-localization-tests"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def build_remote_image_source_result(self, case_dir: Path) -> dict:
        remote_asset = case_dir / "remote-image.png"
        remote_asset.write_bytes(b"remote-image")
        return run_news_index(
            {
                "topic": "Image localization fast path",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [{"claim_id": "claim-1", "claim_text": "A public image is available."}],
                "candidates": [
                    {
                        "source_id": "img-1",
                        "source_name": "DVIDS",
                        "source_type": "specialist_outlet",
                        "published_at": "2026-03-24T11:00:00+00:00",
                        "observed_at": "2026-03-24T11:05:00+00:00",
                        "url": "https://example.com/dvids",
                        "text_excerpt": "A public image is available.",
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                        "root_post_screenshot_path": remote_asset.resolve().as_uri(),
                        "media_summary": "Remote image summary",
                    }
                ],
            }
        )

    def test_balanced_localization_skips_body_rebuild_when_only_targets_change(self) -> None:
        case_dir = self.case_dir("balanced-fast-path")
        draft_result = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": False,
                "draft_mode": "balanced",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        article_package = draft_result["article_package"]
        body_before = article_package["body_markdown"]
        article_before = article_package["article_markdown"]

        with patch("article_draft_flow_runtime.build_sections", wraps=sys.modules["article_draft_flow_runtime"].build_sections) as build_sections_mock:
            localization = localize_selected_images(
                article_package,
                {
                    "asset_output_dir": str(case_dir / "out" / "assets"),
                    "download_remote_images": True,
                    "must_avoid": [],
                },
            )

        self.assertEqual(localization["downloaded_count"], 1)
        self.assertEqual(article_package["selected_images"][0]["status"], "local_ready")
        self.assertEqual(article_package["body_markdown"], body_before)
        self.assertNotEqual(article_package["article_markdown"], article_before)
        self.assertEqual(build_sections_mock.call_count, 0)

    def test_image_first_localization_rebuilds_body_when_status_text_changes(self) -> None:
        case_dir = self.case_dir("image-first-refresh")
        draft_result = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": False,
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        article_package = draft_result["article_package"]
        body_before = article_package["body_markdown"]
        self.assertIn("[remote_only]", body_before)

        with patch("article_draft_flow_runtime.build_sections", wraps=sys.modules["article_draft_flow_runtime"].build_sections) as build_sections_mock:
            localization = localize_selected_images(
                article_package,
                {
                    "asset_output_dir": str(case_dir / "out" / "assets"),
                    "download_remote_images": True,
                    "must_avoid": [],
                },
            )

        self.assertEqual(localization["downloaded_count"], 1)
        self.assertEqual(article_package["selected_images"][0]["status"], "local_ready")
        self.assertIn("[local_ready]", article_package["body_markdown"])
        self.assertNotEqual(article_package["body_markdown"], body_before)
        self.assertEqual(build_sections_mock.call_count, 1)

    def test_draft_writes_localized_image_path_back_to_evidence_bundle(self) -> None:
        case_dir = self.case_dir("draft-bundle-localized")
        draft_result = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": True,
                "draft_mode": "balanced",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )

        bundle_candidate = draft_result["evidence_bundle"]["image_candidates"][0]
        context_candidate = draft_result["draft_context"]["image_candidates"][0]

        self.assertEqual(bundle_candidate["status"], "local_ready")
        self.assertTrue(Path(bundle_candidate["path"]).exists())
        self.assertEqual(context_candidate["path"], bundle_candidate["path"])
        self.assertEqual(context_candidate["status"], "local_ready")

    def test_revision_rebuild_reuses_localized_asset_without_refetch(self) -> None:
        case_dir = self.case_dir("revision-rebuild-localized")
        draft_result = build_article_draft(
            {
                "source_result": self.build_remote_image_source_result(case_dir),
                "asset_output_dir": str(case_dir / "out" / "assets"),
                "download_remote_images": True,
                "draft_mode": "balanced",
                "image_strategy": "prefer_images",
                "max_images": 1,
            }
        )
        localized_path = draft_result["article_package"]["selected_images"][0]["path"]

        with patch("article_draft_flow_runtime.fetch_remote_asset", wraps=sys.modules["article_draft_flow_runtime"].fetch_remote_asset) as fetch_mock:
            revised = build_article_revision(
                {
                    "draft_result": draft_result,
                    "title_hint": "Rebuilt title to force package regeneration",
                }
            )

        revised_image = revised["article_package"]["selected_images"][0]
        self.assertEqual(fetch_mock.call_count, 0)
        self.assertEqual(revised_image["status"], "local_ready")
        self.assertEqual(revised_image["path"], localized_path)
        self.assertEqual(revised["evidence_bundle"]["image_candidates"][0]["path"], localized_path)


if __name__ == "__main__":
    unittest.main()
