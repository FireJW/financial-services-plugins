from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import run_article_publish
from wechat_draftbox_runtime import push_publish_package_to_wechat


class WechatDraftPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-wechat-push"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.image_path = self.temp_dir / "hero.png"
        self.image_path.write_bytes(b"fake-image-bytes")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_publish_package(self) -> dict:
        preview_src = self.image_path.resolve().as_uri()
        html = f'<article><h1>Agent hiring reset</h1><img src="{preview_src}" alt="hero" /></article>'
        return {
            "contract_version": "wechat-draft-package/v1",
            "title": "Agent hiring reset",
            "author": "Codex",
            "content_html": html,
            "image_assets": [
                {
                    "asset_id": "hero-01",
                    "placement": "after_lede",
                    "caption": "Hero chart",
                    "source_name": "fixture",
                    "local_path": str(self.image_path),
                    "source_url": "",
                    "render_src": preview_src,
                    "upload_token": "{{WECHAT_IMAGE_hero-01}}",
                    "upload_required": True,
                    "status": "local_ready",
                }
            ],
            "cover_plan": {
                "primary_image_asset_id": "hero-01",
                "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
            },
            "draftbox_payload_template": {
                "articles": [
                    {
                        "title": "Agent hiring reset",
                        "author": "Codex",
                        "digest": "A short digest",
                        "content": html,
                        "content_source_url": "",
                        "thumb_media_id": "{{WECHAT_THUMB_MEDIA_ID}}",
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                        "show_cover_pic": 1,
                    }
                ]
            },
        }

    def manual_topic_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI Agent hiring reset becomes a business story",
                "summary": "Multiple sources debate whether the hiring rebound is real and what it means for startups.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-agent-hiring",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "36kr reports hiring is returning at selected AI Agent startups.",
                    },
                    {
                        "source_name": "zhihu",
                        "source_type": "social",
                        "url": "https://example.com/zhihu-agent-hiring",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "Zhihu users debate whether the rebound reflects real demand or another short-lived wave.",
                    },
                ],
            }
        ]

    def test_push_publish_package_uploads_images_and_creates_draft(self) -> None:
        seen = {"inline": 0, "draft_payload": None}

        def fake_request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
            if "cgi-bin/token" in url:
                return json.dumps({"access_token": "token-123", "expires_in": 7200}).encode("utf-8")
            if "media/uploadimg" in url:
                seen["inline"] += 1
                return json.dumps({"url": f"https://mmbiz.qpic.cn/inline/{seen['inline']}.png"}).encode("utf-8")
            if "material/add_material" in url:
                return json.dumps({"media_id": "cover-123", "url": "https://mmbiz.qpic.cn/cover.png"}).encode("utf-8")
            if "draft/add" in url:
                seen["draft_payload"] = json.loads((data or b"{}").decode("utf-8"))
                return json.dumps({"media_id": "draft-456"}).encode("utf-8")
            raise AssertionError(f"Unexpected URL: {url}")

        result = push_publish_package_to_wechat(
            {
                "publish_package": self.build_publish_package(),
                "wechat_app_id": "wx-test",
                "wechat_app_secret": "secret-test",
                "allow_insecure_inline_credentials": True,
                "human_review_approved": True,
                "human_review_approved_by": "Editor",
            },
            request_fn=fake_request,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["review_gate"]["status"], "approved")
        self.assertEqual(len(result["uploaded_inline_images"]), 1)
        self.assertEqual(result["uploaded_cover"]["media_id"], "cover-123")
        self.assertEqual(result["draft_result"]["media_id"], "draft-456")
        self.assertIn("https://mmbiz.qpic.cn/inline/1.png", result["resolved_content_html"])
        self.assertNotIn("file://", result["resolved_content_html"])
        self.assertEqual(seen["draft_payload"]["articles"][0]["thumb_media_id"], "cover-123")
        self.assertIn("https://mmbiz.qpic.cn/inline/1.png", seen["draft_payload"]["articles"][0]["content"])

    def test_push_publish_package_uses_dedicated_cover_reference_outside_inline_assets(self) -> None:
        dedicated_cover = self.temp_dir / "dedicated-cover.png"
        dedicated_cover.write_bytes(b"dedicated-cover-bytes")
        package = self.build_publish_package()
        package["cover_plan"] = {
            "primary_image_asset_id": "cover-99",
            "selected_cover_asset_id": "cover-99",
            "selected_cover_local_path": str(dedicated_cover),
            "selected_cover_render_src": dedicated_cover.resolve().as_uri(),
            "selection_mode": "dedicated_candidate",
            "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
        }
        seen = {"cover_body": b""}

        def fake_request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
            if "cgi-bin/token" in url:
                return json.dumps({"access_token": "token-123", "expires_in": 7200}).encode("utf-8")
            if "media/uploadimg" in url:
                return json.dumps({"url": "https://mmbiz.qpic.cn/inline/1.png"}).encode("utf-8")
            if "material/add_material" in url:
                seen["cover_body"] = data or b""
                return json.dumps({"media_id": "cover-999", "url": "https://mmbiz.qpic.cn/cover-999.png"}).encode("utf-8")
            if "draft/add" in url:
                return json.dumps({"media_id": "draft-999"}).encode("utf-8")
            raise AssertionError(f"Unexpected URL: {url}")

        result = push_publish_package_to_wechat(
            {
                "publish_package": package,
                "wechat_app_id": "wx-test",
                "wechat_app_secret": "secret-test",
                "allow_insecure_inline_credentials": True,
                "human_review_approved": True,
            },
            request_fn=fake_request,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["uploaded_cover"]["media_id"], "cover-999")
        self.assertIn(b"dedicated-cover.png", seen["cover_body"])

    def test_push_publish_package_blocks_inline_credentials_by_default(self) -> None:
        with patch.dict(
            os.environ,
            {"WECHAT_APP_ID": "", "WECHAT_APP_SECRET": "", "WECHAT_APPID": "", "WECHAT_APPSECRET": ""},
            clear=False,
        ):
            with patch("wechat_draftbox_runtime.load_local_wechat_credentials", return_value={}):
                with self.assertRaisesRegex(ValueError, "Inline WeChat credentials are blocked by default"):
                    push_publish_package_to_wechat(
                        {
                            "publish_package": self.build_publish_package(),
                            "wechat_app_id": "wx-test-inline-blocked",
                            "wechat_app_secret": "secret-test-inline-blocked",
                            "human_review_approved": True,
                        }
                    )

    def test_push_publish_package_loads_credentials_from_local_env_file(self) -> None:
        seen: dict[str, str] = {}
        env_file = self.temp_dir / ".env.wechat.local"
        env_file.write_text(
            "WECHAT_APP_ID=wx-local-test\nWECHAT_APP_SECRET=local-secret-test\n",
            encoding="utf-8",
        )

        def fake_request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
            if "cgi-bin/token" in url:
                seen["token_url"] = url
                return json.dumps({"access_token": "token-xyz", "expires_in": 7200}).encode("utf-8")
            if "media/uploadimg" in url:
                return json.dumps({"url": "https://mmbiz.qpic.cn/inline/local.png"}).encode("utf-8")
            if "material/add_material" in url:
                return json.dumps({"media_id": "cover-local", "url": "https://mmbiz.qpic.cn/cover-local.png"}).encode("utf-8")
            if "draft/add" in url:
                return json.dumps({"media_id": "draft-local"}).encode("utf-8")
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.dict(os.environ, {"WECHAT_ENV_FILE": str(env_file)}, clear=False):
            result = push_publish_package_to_wechat(
                {
                    "publish_package": self.build_publish_package(),
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                },
                request_fn=fake_request,
            )

        self.assertEqual(result["status"], "ok")
        self.assertIn("appid=wx-local-test", seen["token_url"])

    def test_push_publish_package_requires_human_review_approval(self) -> None:
        result = push_publish_package_to_wechat(
            {
                "publish_package": self.build_publish_package(),
                "wechat_app_id": "wx-test",
                "wechat_app_secret": "secret-test",
            }
        )
        self.assertEqual(result["status"], "blocked_review_gate")
        self.assertEqual(result["blocked_reason"], "human_review_not_approved")
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")
        self.assertIn("Human review approval is required", result["error_message"])

    def test_article_publish_records_push_stage_when_push_is_requested(self) -> None:
        fake_push_result = {
            "status": "ok",
            "review_gate": {"status": "approved"},
            "draft_result": {"media_id": "draft-123"},
            "uploaded_cover": {"media_id": "cover-123"},
            "uploaded_inline_images": [{"asset_id": "hero-01", "inline_url": "https://mmbiz.qpic.cn/inline/1.png"}],
        }
        with patch("article_publish_runtime.push_publish_package_to_wechat", return_value=fake_push_result):
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing"],
                    "output_dir": str(self.temp_dir / "publish-flow"),
                    "push_to_wechat": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                    "cover_image_path": str(self.image_path),
                }
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["push_stage"]["status"], "ok")
        self.assertTrue(result["push_stage"]["attempted"])
        self.assertEqual(result["push_stage"]["review_gate_status"], "approved")
        self.assertEqual(result["push_stage"]["push_readiness_status"], "ready_for_api_push")
        self.assertEqual(result["push_stage"]["draft_media_id"], "draft-123")
        self.assertTrue(Path(result["push_stage"]["result_path"]).exists())
        self.assertIn("## WeChat Push", result["report_markdown"])

    def test_article_publish_requires_human_review_before_push(self) -> None:
        with patch("article_publish_runtime.push_publish_package_to_wechat") as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing"],
                    "output_dir": str(self.temp_dir / "publish-flow-review"),
                    "push_to_wechat": True,
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "cover_image_path": str(self.image_path),
                }
            )
        push_mock.assert_not_called()
        self.assertEqual(result["status"], "blocked_review_gate")
        self.assertEqual(result["manual_review"]["status"], "awaiting_human_review")
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")
        self.assertEqual(result["push_stage"]["status"], "blocked_review_gate")
        self.assertFalse(result["push_stage"]["attempted"])
        self.assertEqual(result["push_stage"]["blocked_reason"], "human_review_not_approved")
        self.assertEqual(result["push_stage"]["review_gate_status"], "awaiting_human_review")

    def test_article_publish_blocks_push_when_package_is_not_ready_even_after_review(self) -> None:
        with patch("article_publish_runtime.push_publish_package_to_wechat") as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing"],
                    "output_dir": str(self.temp_dir / "publish-flow-blocked"),
                    "push_to_wechat": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                }
            )
        push_mock.assert_not_called()
        self.assertEqual(result["status"], "blocked_push_readiness")
        self.assertEqual(result["review_gate"]["status"], "approved")
        self.assertEqual(result["push_stage"]["status"], "blocked_push_readiness")
        self.assertFalse(result["push_stage"]["attempted"])
        self.assertEqual(result["push_stage"]["blocked_reason"], "push_not_ready:missing_cover_image")
        self.assertEqual(result["push_stage"]["push_readiness_status"], "missing_cover_image")

    def test_article_publish_keeps_exported_files_when_push_fails(self) -> None:
        with patch("article_publish_runtime.push_publish_package_to_wechat", side_effect=ValueError("push failed")):
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing"],
                    "output_dir": str(self.temp_dir / "publish-flow-error"),
                    "push_to_wechat": True,
                    "human_review_approved": True,
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                    "cover_image_path": str(self.image_path),
                }
            )
        self.assertEqual(result["status"], "push_error")
        self.assertEqual(result["push_stage"]["status"], "error")
        self.assertTrue(result["push_stage"]["attempted"])
        self.assertEqual(result["push_stage"]["blocked_reason"], "push_failed")
        self.assertEqual(result["push_stage"]["error_message"], "push failed")
        self.assertTrue(Path(result["publish_package_path"]).exists())
        self.assertTrue(Path(result["wechat_html_path"]).exists())


if __name__ == "__main__":
    unittest.main()
