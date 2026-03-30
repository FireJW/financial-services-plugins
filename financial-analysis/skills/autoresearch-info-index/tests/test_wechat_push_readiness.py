from __future__ import annotations

import json
import os
import py_compile
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wechat_push_readiness_runtime import run_wechat_push_readiness_audit


class WechatPushReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-wechat-readiness"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cover_path = self.temp_dir / "cover.png"
        self.cover_path.write_bytes(b"cover-image")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_publish_package(self, *, asset_local_path: str = "", asset_source_url: str = "") -> dict:
        preview_src = Path(asset_local_path).resolve().as_uri() if asset_local_path and Path(asset_local_path).exists() else asset_source_url
        html = "<article><h1>Agent hiring reset</h1><p>Preview body</p></article>"
        return {
            "contract_version": "wechat-draft-package/v1",
            "title": "Agent hiring reset",
            "author": "Codex",
            "digest": "A short digest",
            "content_html": html,
            "image_assets": [
                {
                    "asset_id": "hero-01",
                    "placement": "after_lede",
                    "caption": "Hero chart",
                    "source_name": "fixture",
                    "local_path": asset_local_path,
                    "source_url": asset_source_url,
                    "render_src": preview_src,
                    "upload_token": "{{WECHAT_IMAGE_hero-01}}",
                    "upload_required": True,
                    "status": "local_ready" if asset_local_path else "remote_only",
                }
            ],
            "cover_plan": {
                "primary_image_asset_id": "hero-01",
                "primary_image_render_src": preview_src,
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

    def test_readiness_audit_blocks_when_upload_source_and_credentials_are_missing(self) -> None:
        missing_path = str(self.temp_dir / "missing-cover.png")
        with patch.dict(
            os.environ,
            {"WECHAT_APP_ID": "", "WECHAT_APP_SECRET": "", "WECHAT_APPID": "", "WECHAT_APPSECRET": ""},
            clear=False,
        ):
            with patch("wechat_draftbox_runtime.load_local_wechat_credentials", return_value={}):
                result = run_wechat_push_readiness_audit(
                    {
                        "publish_package": self.build_publish_package(asset_local_path=missing_path),
                    }
                )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["readiness_level"], "blocked")
        self.assertFalse(result["ready_for_real_push"])
        self.assertEqual(result["push_readiness"]["status"], "missing_cover_image")
        self.assertEqual(result["credential_check"]["status"], "missing_credentials")
        self.assertIn("hero-01", result["push_readiness"]["missing_upload_source_asset_ids"])
        self.assertIn("Human review approval is still required", "\n".join(result["blockers"]))

    def test_readiness_audit_ready_with_local_env_file_and_live_auth(self) -> None:
        env_file = self.temp_dir / ".env.wechat.local"
        env_file.write_text(
            "WECHAT_APP_ID=wx-local-test\nWECHAT_APP_SECRET=local-secret-test\n",
            encoding="utf-8",
        )

        def fake_request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
            self.assertEqual(method, "GET")
            self.assertIn("cgi-bin/token", url)
            return json.dumps({"access_token": "token-123", "expires_in": 7200}).encode("utf-8")

        with patch.dict(os.environ, {"WECHAT_ENV_FILE": str(env_file)}, clear=False):
            result = run_wechat_push_readiness_audit(
                {
                    "publish_package": self.build_publish_package(asset_local_path=str(self.cover_path)),
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "validate_live_auth": True,
                },
                request_fn=fake_request,
            )

        self.assertEqual(result["readiness_level"], "ready")
        self.assertTrue(result["ready_for_real_push"])
        self.assertEqual(result["credential_check"]["source"], "env_file")
        self.assertEqual(result["live_auth_check"]["status"], "ok")
        self.assertEqual(result["push_readiness"]["status"], "ready_for_api_push")

    def test_readiness_audit_accepts_utf8_bom_env_file(self) -> None:
        env_file = self.temp_dir / ".env.wechat.local"
        env_file.write_text(
            "WECHAT_APP_ID=wx-local-bom\nWECHAT_APP_SECRET=local-secret-bom\n",
            encoding="utf-8-sig",
        )

        def fake_request(method: str, url: str, data: bytes | None, headers: dict[str, str], timeout_seconds: int) -> bytes:
            self.assertEqual(method, "GET")
            self.assertIn("appid=wx-local-bom", url)
            return json.dumps({"access_token": "token-bom", "expires_in": 7200}).encode("utf-8")

        with patch.dict(os.environ, {"WECHAT_ENV_FILE": str(env_file)}, clear=False):
            result = run_wechat_push_readiness_audit(
                {
                    "publish_package": self.build_publish_package(asset_local_path=str(self.cover_path)),
                    "human_review_approved": True,
                    "validate_live_auth": True,
                },
                request_fn=fake_request,
            )

        self.assertEqual(result["readiness_level"], "ready")
        self.assertEqual(result["credential_check"]["source"], "env_file")
        self.assertEqual(result["live_auth_check"]["status"], "ok")

    def test_readiness_audit_warns_on_insecure_inline_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {"WECHAT_APP_ID": "", "WECHAT_APP_SECRET": "", "WECHAT_APPID": "", "WECHAT_APPSECRET": ""},
            clear=False,
        ):
            with patch("wechat_draftbox_runtime.load_local_wechat_credentials", return_value={}):
                result = run_wechat_push_readiness_audit(
                    {
                        "publish_package": self.build_publish_package(asset_local_path=str(self.cover_path)),
                        "human_review_approved": True,
                        "wechat_app_id": "wx-test-inline",
                        "wechat_app_secret": "secret-test-inline",
                        "allow_insecure_inline_credentials": True,
                    }
                )

        self.assertEqual(result["readiness_level"], "warning")
        self.assertFalse(result["ready_for_real_push"])
        self.assertEqual(result["credential_check"]["status"], "warning_insecure_inline")
        self.assertEqual(result["push_readiness"]["status"], "ready_for_api_push")
        self.assertIn("insecure inline override", "\n".join(result["warnings"]))

    def test_readiness_audit_accepts_dedicated_cover_from_cover_plan(self) -> None:
        publish_package = self.build_publish_package(asset_local_path="")
        publish_package["image_assets"] = []
        publish_package["cover_plan"] = {
            "primary_image_asset_id": "cover-99",
            "selected_cover_asset_id": "cover-99",
            "selected_cover_local_path": str(self.cover_path),
            "selected_cover_render_src": self.cover_path.resolve().as_uri(),
            "selection_mode": "dedicated_candidate",
            "thumb_media_id_placeholder": "{{WECHAT_THUMB_MEDIA_ID}}",
        }

        result = run_wechat_push_readiness_audit(
            {
                "publish_package": publish_package,
                "human_review_approved": True,
            }
        )

        self.assertEqual(result["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(result["push_readiness"]["cover_source"], "dedicated_cover_candidate")

    def test_readiness_scripts_compile_cleanly(self) -> None:
        for name in [
            "wechat_push_readiness_runtime.py",
            "wechat_push_readiness.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
