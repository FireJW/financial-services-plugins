#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import shutil
import sys
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import run_article_publish


_TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnSUs8AAAAASUVORK5CYII="


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def replace_tokens(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        replaced = value
        for needle, replacement in mapping.items():
            replaced = replaced.replace(needle, replacement)
        return replaced
    if isinstance(value, list):
        return [replace_tokens(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: replace_tokens(item, mapping) for key, item in value.items()}
    return value


class ArticlePublishCanonicalSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace_root = Path(__file__).resolve().parents[4]
        cls.fixtures_root = Path(__file__).resolve().parent / "fixtures" / "article-publish-canonical"
        cls.temp_root = Path.cwd() / ".tmp" / "article-publish-canonical-snapshots"
        cls.temp_root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, name: str) -> Path:
        path = self.temp_root / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def expected_snapshot(self, name: str) -> dict[str, Any]:
        return read_json(self.fixtures_root / f"{name}.json")

    def build_root_post_screenshot(self, path: Path) -> None:
        path.write_bytes(base64.b64decode(_TINY_PNG_BASE64))

    def build_post_media_image(self, path: Path) -> None:
        path.write_bytes(base64.b64decode(_TINY_PNG_BASE64))

    def load_request_fixture(self, fixture_name: str, *, screenshot_path: Path, post_media_path: Path) -> dict[str, Any]:
        request = read_json(self.fixtures_root / f"{fixture_name}.json")
        mapping = {
            "__WORKSPACE_ROOT__": str(self.workspace_root),
            "__ROOT_POST_SCREENSHOT_PATH__": str(screenshot_path),
            "__POST_MEDIA_PATH__": str(post_media_path),
        }
        return replace_tokens(request, mapping)

    def normalize_text(self, value: str, *, screenshot_path: Path, post_media_path: Path) -> str:
        normalized = value
        replacements = [
            (f"file:///{screenshot_path.as_posix()}", "file:///__ROOT_POST_SCREENSHOT_PATH__"),
            (f"file:///{post_media_path.as_posix()}", "file:///__POST_MEDIA_PATH__"),
            (f"file:///{self.workspace_root.as_posix()}", "file:///__WORKSPACE_ROOT__"),
            (screenshot_path.as_posix(), "__ROOT_POST_SCREENSHOT_PATH__"),
            (str(screenshot_path), "__ROOT_POST_SCREENSHOT_PATH__"),
            (post_media_path.as_posix(), "__POST_MEDIA_PATH__"),
            (str(post_media_path), "__POST_MEDIA_PATH__"),
            (self.workspace_root.as_posix(), "__WORKSPACE_ROOT__"),
            (str(self.workspace_root), "__WORKSPACE_ROOT__"),
        ]
        for needle, replacement in replacements:
            normalized = normalized.replace(needle, replacement)
        return normalized

    def normalize_value(self, value: Any, *, screenshot_path: Path, post_media_path: Path) -> Any:
        if isinstance(value, str):
            return self.normalize_text(value, screenshot_path=screenshot_path, post_media_path=post_media_path)
        if isinstance(value, list):
            return [
                self.normalize_value(item, screenshot_path=screenshot_path, post_media_path=post_media_path)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: self.normalize_value(item, screenshot_path=screenshot_path, post_media_path=post_media_path)
                for key, item in value.items()
            }
        return value

    def publish_snapshot(self, result: dict[str, Any], *, screenshot_path: Path, post_media_path: Path) -> dict[str, Any]:
        publish_package = result["publish_package"]
        regression = publish_package["regression_checks"]
        auto = result["automatic_acceptance"]
        workflow_publication_gate = result.get("workflow_publication_gate") or {}
        workflow_manual_review = workflow_publication_gate.get("manual_review") or {}
        acceptance_gate = auto.get("workflow_publication_gate") or {}
        acceptance_manual_review = acceptance_gate.get("manual_review") or {}
        draft_result = read_json(Path(result["workflow_stage"]["draft_result_path"]))
        article_package = draft_result["article_package"]
        style_profile = publish_package.get("style_profile_applied") or {}
        effective_request = style_profile.get("effective_request") or {}
        style_memory = effective_request.get("style_memory") or {}
        feedback_status = publish_package.get("feedback_profile_status") or {}
        normalized_body_markdown = self.normalize_text(
            publish_package.get("content_markdown", ""),
            screenshot_path=screenshot_path,
            post_media_path=post_media_path,
        )

        snapshot = {
            "title": publish_package.get("title"),
            "subtitle": publish_package.get("subtitle"),
            "body_markdown": normalized_body_markdown,
            "section_count": regression.get("section_count"),
            "body_char_count": regression.get("body_char_count"),
            "content_char_count": len(normalized_body_markdown),
            "section_headings": regression.get("section_headings"),
            "section_paragraphs": [item.get("paragraph") for item in article_package.get("sections", [])],
            "selected_images": [
                {
                    "asset_id": item.get("asset_id"),
                    "role": item.get("role"),
                    "status": item.get("status"),
                    "caption": item.get("caption"),
                    "placement": item.get("placement"),
                    "path": item.get("path"),
                }
                for item in article_package.get("selected_images", [])
            ],
            "cover_candidate_roles": [
                item.get("role")
                for item in (publish_package.get("cover_plan") or {}).get("cover_candidates", [])
            ],
            "forbidden_phrase_hits": regression.get("forbidden_phrase_hits"),
            "developer_focus_phrase_hits": regression.get("developer_focus_phrase_hits"),
            "wechat_transition_phrase_hits": regression.get("wechat_transition_phrase_hits"),
            "wechat_tail_tone_phrase_hits": regression.get("wechat_tail_tone_phrase_hits"),
            "checks": regression.get("checks"),
            "first_image": regression.get("first_image"),
            "cover": {
                "selected_cover_asset_id": regression.get("cover", {}).get("selected_cover_asset_id"),
                "selected_cover_role": regression.get("cover", {}).get("selected_cover_role"),
                "selected_cover_caption": regression.get("cover", {}).get("selected_cover_caption"),
                "selection_mode": regression.get("cover", {}).get("selection_mode"),
                "cover_source": regression.get("cover", {}).get("cover_source"),
            },
            "style_effective_request": {
                "language_mode": effective_request.get("language_mode"),
                "draft_mode": effective_request.get("draft_mode"),
                "image_strategy": effective_request.get("image_strategy"),
                "target_length_chars": effective_request.get("target_length_chars"),
                "headline_hook_mode": effective_request.get("headline_hook_mode"),
                "human_signal_ratio": effective_request.get("human_signal_ratio"),
                "personal_phrase_bank": effective_request.get("personal_phrase_bank"),
                "must_avoid": effective_request.get("must_avoid"),
                "style_memory": {
                    "target_band": style_memory.get("target_band"),
                    "preferred_transitions": style_memory.get("preferred_transitions"),
                    "slot_lines": style_memory.get("slot_lines"),
                },
            },
            "feedback_profile_status": {
                "global_exists": feedback_status.get("global_exists"),
                "topic_exists": feedback_status.get("topic_exists"),
                "global_history_count": feedback_status.get("global_history_count"),
                "topic_history_count": feedback_status.get("topic_history_count"),
                "global_style_memory_keys": feedback_status.get("global_style_memory_keys"),
                "topic_style_memory_keys": feedback_status.get("topic_style_memory_keys"),
                "applied_paths_count": len(feedback_status.get("applied_paths", [])),
            },
            "workflow_publication_gate": {
                "publication_readiness": workflow_publication_gate.get("publication_readiness"),
                "manual_review_status": workflow_manual_review.get("status"),
                "required_count": workflow_manual_review.get("required_count"),
                "high_priority_count": workflow_manual_review.get("high_priority_count"),
            },
            "automatic_acceptance": {
                "accepted": auto.get("accepted"),
                "status": auto.get("status"),
                "decision_required": auto.get("decision_required"),
                "blocking_optimization_count": len(auto.get("optimization_options") or []),
                "advisory_optimization_count": len(auto.get("advisory_options") or []),
                "recommended_next_action": auto.get("recommended_next_action"),
                "workflow_publication_gate": {
                    "publication_readiness": acceptance_gate.get("publication_readiness"),
                    "manual_review_status": acceptance_manual_review.get("status"),
                    "required_count": acceptance_manual_review.get("required_count"),
                    "high_priority_count": acceptance_manual_review.get("high_priority_count"),
                },
            },
        }
        return self.normalize_value(snapshot, screenshot_path=screenshot_path, post_media_path=post_media_path)

    def assert_publish_matches_snapshot(self, fixture_stem: str, case_name: str) -> None:
        case_dir = self.case_dir(case_name)
        screenshot_path = case_dir / "root-post-screenshot.png"
        post_media_path = case_dir / "post-media.png"
        self.build_root_post_screenshot(screenshot_path)
        self.build_post_media_image(post_media_path)

        request = self.load_request_fixture(
            f"{fixture_stem}_request",
            screenshot_path=screenshot_path,
            post_media_path=post_media_path,
        )
        request["output_dir"] = str(case_dir / "out")
        request["feedback_profile_dir"] = str(self.fixtures_root / "feedback-profile")

        result = run_article_publish(request)
        actual = self.publish_snapshot(
            result,
            screenshot_path=screenshot_path,
            post_media_path=post_media_path,
        )
        expected = self.expected_snapshot(f"{fixture_stem}_snapshot")

        self.maxDiff = None
        self.assertEqual(actual, expected)

    def test_claude_code_publish_request_matches_canonical_snapshot(self) -> None:
        self.assert_publish_matches_snapshot(
            "claude_code_deep_analysis_screenshots_2800",
            "claude-code-publish",
        )

    def test_claude_code_prefer_images_request_keeps_screenshot_priority_snapshot(self) -> None:
        self.assert_publish_matches_snapshot(
            "claude_code_deep_analysis_prefer_images_2800",
            "claude-code-publish-prefer-images",
        )

    def test_claude_code_prefer_images_mixed_visual_request_keeps_screenshot_cover_snapshot(self) -> None:
        self.assert_publish_matches_snapshot(
            "claude_code_deep_analysis_prefer_images_mixed_2800",
            "claude-code-publish-prefer-images-mixed",
        )


if __name__ == "__main__":
    unittest.main()
