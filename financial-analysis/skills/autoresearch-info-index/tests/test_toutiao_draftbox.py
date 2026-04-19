# tests/test_toutiao_draftbox.py
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

from toutiao_draftbox_runtime import push_fast_card_to_toutiao


class ToutiaoDraftboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-toutiao-push"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_fast_card_package(self) -> dict:
        return {
            "contract_version": "toutiao-fast-card-package/v1",
            "title": "美联储意外按兵不动",
            "one_line_takeaway": "利率不变，市场读出鸽派信号",
            "confirmed": "利率维持 5.25-5.50%",
            "unconfirmed": "9月降息概率升至 68%",
            "conflict_point": "就业数据仍强，通胀粘性未消",
            "next_watch": "6月非农",
            "cta": "👉 完整证据链见公众号原文",
            "boundary": "以上判断基于截稿前公开信息，不构成投资建议",
            "segments": [
                {"index": 1, "role": "title", "text": "美联储意外按兵不动"},
                {"index": 2, "role": "one_line_takeaway", "text": "利率不变，市场读出鸽派信号"},
                {"index": 3, "role": "confirmed_vs_unconfirmed", "text": "✅ 利率维持\n❓ 降息概率"},
                {"index": 4, "role": "conflict_point", "text": "就业数据仍强"},
                {"index": 5, "role": "next_watch", "text": "6月非农"},
                {"index": 6, "role": "cta", "text": "👉 完整证据链见公众号原文"},
                {"index": 7, "role": "boundary", "text": "不构成投资建议"},
            ],
            "plain_text": "美联储意外按兵不动\n\n利率不变\n\n...",
            "keywords": ["Fed", "利率"],
            "author": "Codex",
            "analysis_time": "2026-04-18T10:00:00+00:00",
        }

    def test_push_requires_human_review_approval(self) -> None:
        result = push_fast_card_to_toutiao({
            "fast_card_package": self._make_fast_card_package(),
            "human_review_approved": False,
        })
        self.assertEqual(result["status"], "blocked_review_gate")
        self.assertEqual(result["blocked_reason"], "human_review_not_approved")

    def test_push_browser_session_builds_manifest_and_calls_runner(self) -> None:
        seen: dict[str, object] = {}

        def fake_runner(manifest_path: Path, session_context: dict, timeout_seconds: int) -> dict:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            seen["manifest"] = manifest
            return {
                "status": "ok",
                "article_url": "https://mp.toutiao.com/profile_v4/graphic/publish?draft_id=123",
            }

        result = push_fast_card_to_toutiao(
            {
                "fast_card_package": self._make_fast_card_package(),
                "human_review_approved": True,
                "human_review_approved_by": "Editor",
                "push_backend": "browser_session",
                "browser_session": {
                    "strategy": "remote_debugging",
                    "cdp_endpoint": "http://127.0.0.1:9222",
                },
            },
            browser_runner=fake_runner,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["push_backend"], "browser_session")
        self.assertIn("美联储", seen["manifest"]["title"])
        self.assertTrue(seen["manifest"]["plain_text"])
        self.assertTrue(Path(result["browser_session"]["manifest_path"]).exists())

    def test_push_defaults_to_browser_session_when_no_api(self) -> None:
        result = push_fast_card_to_toutiao(
            {
                "fast_card_package": self._make_fast_card_package(),
                "human_review_approved": True,
                "push_backend": "auto",
                "browser_session": {
                    "strategy": "remote_debugging",
                    "cdp_endpoint": "http://127.0.0.1:9222",
                },
            },
            browser_runner=lambda mp, sc, ts: {"status": "ok", "article_url": ""},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["push_backend"], "browser_session")


if __name__ == "__main__":
    unittest.main()
