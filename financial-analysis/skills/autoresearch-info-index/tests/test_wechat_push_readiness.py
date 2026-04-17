from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wechat_push_readiness import build_payload, parse_args
from wechat_push_readiness_runtime import run_wechat_push_readiness_audit


class WechatPushReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-wechat-push-readiness"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cover_path = self.temp_dir / "cover.png"
        self.cover_path.write_bytes(b"fake-cover")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_publish_package(self) -> dict:
        return {
            "contract_version": "wechat-draft-package/v1",
            "title": "Agent hiring reset",
            "author": "Codex",
            "content_html": "<article><h1>Agent hiring reset</h1></article>",
            "image_assets": [],
            "cover_plan": {
                "selected_cover_asset_id": "",
                "selected_cover_role": "",
                "selected_cover_caption": "",
                "selection_mode": "manual_required",
                "selection_reason": "No usable cover candidate is ready yet. Provide cover_image_path or cover_image_url.",
                "cover_source": "missing",
            },
            "push_readiness": {
                "status": "missing_cover_image",
                "ready_for_api_push": False,
                "cover_source": "missing",
                "missing_upload_source_asset_ids": [],
                "next_step": "Provide cover_image_path or cover_image_url before a real WeChat push.",
            },
            "draftbox_payload_template": {
                "articles": [
                    {
                        "title": "Agent hiring reset",
                        "author": "Codex",
                        "digest": "A short digest",
                        "content": "<article><h1>Agent hiring reset</h1></article>",
                        "content_source_url": "",
                        "thumb_media_id": "{{WECHAT_THUMB_MEDIA_ID}}",
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                        "show_cover_pic": 1,
                    }
                ]
            },
        }

    def test_audit_blocks_when_review_cover_and_credentials_are_missing(self) -> None:
        with patch("wechat_push_readiness_runtime.inspect_wechat_credentials") as inspect_mock:
            inspect_mock.return_value = {
                "ready": False,
                "status": "missing",
                "source": "none",
                "warning": "",
                "error_message": "No usable WeChat credentials were found",
            }
            result = run_wechat_push_readiness_audit({"publish_package": self.build_publish_package()})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["readiness_level"], "blocked")
        self.assertFalse(result["ready_for_real_push"])
        self.assertEqual(result["push_readiness"]["status"], "missing_cover_image")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertIn("Human review approval is still required before a real WeChat push.", result["blockers"])
        self.assertIn("Provide cover_image_path or cover_image_url before a real WeChat push.", result["blockers"])
        self.assertIn("No usable WeChat credentials were found", result["blockers"])

    def test_audit_can_be_ready_with_cover_override_human_review_and_inline_credentials(self) -> None:
        with patch("wechat_push_readiness_runtime.inspect_wechat_credentials") as inspect_mock:
            inspect_mock.return_value = {
                "ready": True,
                "status": "ready",
                "source": "inline_override",
                "warning": "inline_override",
                "error_message": "",
            }
            result = run_wechat_push_readiness_audit(
                {
                    "publish_package": self.build_publish_package(),
                    "cover_image_path": str(self.cover_path),
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                }
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["readiness_level"], "warning")
        self.assertFalse(result["ready_for_real_push"])
        self.assertEqual(result["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(result["credential_check"]["status"], "ready")
        self.assertFalse(result["blockers"])
        self.assertTrue(result["warnings"])

    def test_build_payload_maps_positional_publish_package_path(self) -> None:
        package_path = self.temp_dir / "publish-package.json"
        package_path.write_text(json.dumps(self.build_publish_package(), ensure_ascii=False), encoding="utf-8")
        with patch.object(sys, "argv", ["wechat_push_readiness.py", str(package_path)]):
            args = parse_args()
        payload = build_payload(args)
        self.assertEqual(payload["publish_package_path"], str(package_path.resolve()))
        self.assertEqual(payload["_input_path"], str(package_path.resolve()))

    def test_audit_accepts_explicit_wechat_env_file_from_request(self) -> None:
        env_file = self.temp_dir / ".env.wechat.local"
        env_file.write_text(
            "WECHAT_APP_ID=wx-explicit-test\nWECHAT_APP_SECRET=explicit-secret-test\n",
            encoding="utf-8",
        )
        result = run_wechat_push_readiness_audit(
            {
                "publish_package": self.build_publish_package(),
                "cover_image_path": str(self.cover_path),
                "human_review_approved": True,
                "wechat_env_file": str(env_file),
            }
        )
        self.assertEqual(result["credential_check"]["status"], "ready")
        self.assertEqual(result["credential_check"]["source"], "env_file")


if __name__ == "__main__":
    unittest.main()
