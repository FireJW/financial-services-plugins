#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_workflow_runtime import run_article_workflow
from last30days_bridge_runtime import run_last30days_bridge
from last30days_deploy_check_runtime import run_last30days_deploy_check


class Last30DaysBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path.cwd() / ".tmp" / "last30days-bridge-tests"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def build_bridge_request(self, tmpdir: Path) -> dict:
        screenshot_path = tmpdir / "root.png"
        screenshot_path.write_bytes(b"root")
        media_path = tmpdir / "chart.png"
        media_path.write_bytes(b"chart")
        return {
            "topic": "Hormuz escalation watch",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "mode": "crisis",
            "questions": ["What is fresh, what is background, and what still is not proven?"],
            "claims": [
                {
                    "claim_id": "claim-talks",
                    "claim_text": "Indirect mediation contacts are still active.",
                },
                {
                    "claim_id": "claim-airlift",
                    "claim_text": "US regional airlift activity has intensified.",
                },
            ],
            "findings": [
                {
                    "platform": "x",
                    "author_handle": "sentdefender",
                    "url": "https://x.com/sentdefender/status/2036153038906196133",
                    "published_at": "2026-03-24T09:30:00+00:00",
                    "post_text_raw": "A significant movement is underway from CONUS to the Middle East with at least 35 C-17 flights.",
                    "post_text_source": "dom",
                    "post_text_confidence": 0.94,
                    "post_summary": "SentDefender says at least 35 C-17 flights moved into the region.",
                    "media_summary": "Attached chart lists Fort Stewart, JBLM, and Jordanian destinations.",
                    "combined_summary": "SentDefender claims at least 35 C-17 flights moved into the region and attached a chart listing key bases.",
                    "claim_ids": ["claim-airlift"],
                    "claim_states": {"claim-airlift": "support"},
                    "root_post_screenshot_path": str(screenshot_path),
                    "artifact_manifest": [
                        {
                            "role": "root_post_screenshot",
                            "path": str(screenshot_path),
                            "source_url": "https://x.com/sentdefender/status/2036153038906196133",
                            "media_type": "image/png",
                        },
                        {
                            "role": "attached_media_1",
                            "path": str(media_path),
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "media_type": "image/png",
                        },
                    ],
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "local_artifact_path": str(media_path),
                            "ocr_summary": "Origins include Fort Stewart and JBLM; destinations include Ovda and Jordan.",
                            "image_relevance_to_post": "high",
                        }
                    ],
                }
            ],
            "web": [
                {
                    "source_name": "Reuters",
                    "url": "https://www.reuters.com/world/middle-east/mediators-push-fresh-iran-contact-2026-03-24/",
                    "published_at": "2026-03-24T10:40:00+00:00",
                    "summary": "Reuters says mediators remain in contact and no breakthrough has been announced.",
                    "claim_ids": ["claim-talks"],
                    "claim_states": {"claim-talks": "support"},
                }
            ],
            "polymarket": [
                {
                    "platform": "polymarket",
                    "url": "https://polymarket.com/event/hormuz-reopens-before-april",
                    "published_at": "2026-03-22T06:00:00+00:00",
                    "summary": "An older market note says traders still price a delayed reopening.",
                    "claim_ids": ["claim-talks"],
                    "claim_states": {"claim-talks": "unclear"},
                }
            ],
        }

    def test_bridge_imports_last30days_items_as_shadow_or_background_and_preserves_origin(self) -> None:
        result = run_last30days_bridge(self.build_bridge_request(self.case_dir("bridge-shadow")))
        observations = result["retrieval_result"]["observations"]
        self.assertTrue(observations)
        self.assertTrue(all(item.get("origin") == "last30days" for item in observations))

        reuters = next(item for item in observations if item.get("source_name") == "Reuters")
        polymarket = next(item for item in observations if "polymarket.com" in item.get("url", ""))
        claim_talks = next(item for item in result["retrieval_result"]["claim_ledger"] if item.get("claim_id") == "claim-talks")

        self.assertEqual(reuters["channel"], "shadow")
        self.assertEqual(polymarket["channel"], "background")
        self.assertNotEqual(claim_talks["promotion_state"], "core")
        self.assertGreaterEqual(result["import_summary"]["with_artifacts"], 1)

    def test_bridge_result_can_feed_article_workflow_without_reindexing(self) -> None:
        bridge_result = run_last30days_bridge(self.build_bridge_request(self.case_dir("bridge-workflow")))
        output_dir = self.case_dir("workflow-output")
        workflow = run_article_workflow(
            {
                **bridge_result,
                "output_dir": str(output_dir),
                "language_mode": "english",
            }
        )

        self.assertEqual(workflow["source_stage"]["source_kind"], "news_index")
        self.assertGreaterEqual(workflow["draft_stage"]["image_count"], 1)
        self.assertTrue(Path(workflow["source_stage"]["result_path"]).exists())
        selected_images = workflow["draft_result"]["article_package"]["selected_images"]
        self.assertTrue(any(item.get("status") == "local_ready" for item in selected_images))

    def test_bridge_can_load_result_path_with_trailing_text_noise(self) -> None:
        tmpdir = self.case_dir("bridge-result-path")
        result_path = tmpdir / "last30days-output.txt"
        result_path.write_text(
            '{"topic":"Iran war","generated_at":"2026-03-24T16:05:03+00:00","hackernews":[{"id":"HN1","title":"Iran war energy shock sparks global push","url":"https://www.reuters.com/world/middle-east/example","hn_url":"https://news.ycombinator.com/item?id=47437516","date":"2026-03-19","why_relevant":"HN story about Iran war energy shock"}],"polymarket":[{"id":"PM1","question":"US forces enter Iran by March 31?","url":"https://polymarket.com/event/us-forces-enter-iran-by","date":"2026-03-24","why_relevant":"Prediction market: US forces enter Iran by March 31?"}]}\nWEBSEARCH REQUIRED\n',
            encoding="utf-8",
        )

        result = run_last30days_bridge(
            {
                "topic": "Iran war",
                "analysis_time": "2026-03-24T16:10:00+00:00",
                "last30days_result_path": str(result_path),
            }
        )

        self.assertGreaterEqual(result["import_summary"]["imported_candidate_count"], 2)
        self.assertIn("hacker_news", result["import_summary"]["platform_counts"])
        self.assertIn("polymarket", result["import_summary"]["platform_counts"])

    def test_deploy_check_handles_missing_install_root_cleanly(self) -> None:
        missing_root = self.case_dir("deploy-missing") / "not-installed"
        result = run_last30days_deploy_check(
            {
                "install_root": str(missing_root),
                "binary_groups": [],
            }
        )

        self.assertEqual(result["status"], "missing_install")
        self.assertFalse(any(item["exists"] for item in result["required_files"]))
        self.assertIn("Install root is missing", "\n".join(result["notes"]))

    def test_deploy_check_marks_ready_when_expected_files_and_storage_exist(self) -> None:
        install_root = self.case_dir("deploy-ready")
        (install_root / "scripts").mkdir(parents=True, exist_ok=True)
        (install_root / "SKILL.md").write_text("# skill", encoding="utf-8")
        (install_root / "README.md").write_text("# readme", encoding="utf-8")
        (install_root / "scripts" / "last30days.py").write_text("print('ok')\n", encoding="utf-8")

        env_dir = self.case_dir("deploy-ready-env")
        env_file = env_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=test\n", encoding="utf-8")

        storage_dir = self.case_dir("deploy-ready-storage")
        sqlite_path = storage_dir / "history.sqlite"
        sqlite_path.write_bytes(b"sqlite")

        result = run_last30days_deploy_check(
            {
                "install_root": str(install_root),
                "env_file_path": str(env_file),
                "storage_paths": [str(storage_dir)],
                "binary_groups": [],
            }
        )

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["env_status"]["env_file"]["exists"])
        self.assertIn(str(sqlite_path), result["sqlite_candidates"])


if __name__ == "__main__":
    unittest.main()
