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

from toutiao_article_draftbox_runtime import push_publish_package_to_toutiao


class ToutiaoArticleDraftboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-toutiao-article-push"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.image_path = self.temp_dir / "hero.png"
        self.image_path.write_bytes(b"fake-image-bytes")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def sample_publish_package(self) -> dict:
        return {
            "contract_version": "publish-package/v1",
            "title": "美国中期选举风险开始传到市场",
            "subtitle": "从华尔街已经开始重新定价的那条风险线，看压力会怎样传到政策和市场。",
            "lede": "一场华尔街内部闭门讨论已经把风险提前摆上了桌面。",
            "sections": [{"heading": "核心矛盾", "paragraph": "真正的压力来自投票结构和政策传导之间的错位。"}],
            "content_markdown": "# 美国中期选举风险开始传到市场\n\n## 核心矛盾\n\n真正的压力来自投票结构和政策传导之间的错位。",
            "content_html": "<p>美国中期选举风险开始传到市场</p>",
            "selected_images": [
                {
                    "asset_id": "IMG-01",
                    "role": "post_media",
                    "path": str(self.image_path),
                    "caption": "国会山现场图",
                    "source_url": "https://example.com/hero.png",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            "cover_plan": {
                "selected_cover_asset_id": "IMG-01",
                "selected_cover_local_path": str(self.image_path),
                "selected_cover_source_url": "https://example.com/hero.png",
                "selection_mode": "dedicated_candidate",
            },
            "platform_hints": {"preferred_image_slots": ["after_lede"], "section_emphasis": ["核心矛盾"], "heading_density": "normal"},
            "style_profile_applied": {},
            "operator_notes": ["Prefer one real inline image after the lede."],
            "draft_thesis": "真正该看的不是 headline，而是政策风险会不会先传到国会和美联储人事。",
            "citations": [],
        }

    def test_push_requires_human_review_approval(self) -> None:
        result = push_publish_package_to_toutiao({"publish_package": self.sample_publish_package(), "human_review_approved": False})
        self.assertEqual(result["status"], "blocked_review_gate")
        self.assertEqual(result["blocked_reason"], "human_review_not_approved")

    def test_toutiao_article_adapter_uses_publish_package_content(self) -> None:
        seen: dict[str, object] = {}

        def fake_runner(manifest_path: Path, session_context: dict, timeout_seconds: int) -> dict:
            seen["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
            return {"status": "ok", "article_url": "https://mp.toutiao.com/profile_v4/graphic/publish?draft_id=123"}

        result = push_publish_package_to_toutiao(
            {
                "publish_package": self.sample_publish_package(),
                "browser_session": {"strategy": "remote_debugging", "cdp_endpoint": "http://127.0.0.1:9222"},
                "human_review_approved": True,
            },
            browser_runner=fake_runner,
        )

        self.assertEqual(result["push_backend"], "browser_session")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(seen["manifest"]["title"], "美国中期选举风险开始传到市场")
        self.assertIn("核心矛盾", seen["manifest"]["content_markdown"])
        self.assertEqual(seen["manifest"]["cover_plan"]["selected_cover_asset_id"], "IMG-01")

    def test_toutiao_article_adapter_uses_default_browser_session_runner(self) -> None:
        with patch(
            "toutiao_article_draftbox_runtime.run_toutiao_article_browser_session",
            return_value={"status": "ok", "article_url": "https://mp.toutiao.com/profile_v4/graphic/publish?draft_id=123"},
        ) as runner_mock:
            result = push_publish_package_to_toutiao(
                {
                    "publish_package": self.sample_publish_package(),
                    "browser_session": {"strategy": "remote_debugging", "cdp_endpoint": "http://127.0.0.1:9222"},
                    "human_review_approved": True,
                }
            )

        runner_mock.assert_called_once()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["push_backend"], "browser_session")


if __name__ == "__main__":
    unittest.main()
