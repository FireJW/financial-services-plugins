# tests/test_toutiao_fast_card.py
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from toutiao_fast_card_runtime import build_toutiao_fast_card_package


class ToutiaoFastCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-toutiao-fast-card"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_selected_topic(self) -> dict:
        return {
            "title": "美联储意外按兵不动，科技股应声反弹",
            "summary": "Fed holds rates steady; tech stocks rally on dovish signal.",
            "keywords": ["Fed", "利率", "科技股"],
            "source_items": [
                {
                    "source_name": "reuters",
                    "source_type": "major_news",
                    "url": "https://example.com/reuters-fed",
                    "published_at": "2026-04-18T08:00:00+00:00",
                    "summary": "Reuters reports the Fed held rates steady.",
                },
                {
                    "source_name": "zhihu",
                    "source_type": "social",
                    "url": "https://example.com/zhihu-fed",
                    "published_at": "2026-04-18T09:00:00+00:00",
                    "summary": "Zhihu users debate whether this signals a pivot.",
                },
            ],
        }

    def _make_workflow_result(self) -> dict:
        return {
            "final_article_result": {
                "title": "美联储意外按兵不动，科技股应声反弹",
                "body_markdown": (
                    "# 美联储意外按兵不动\n\n"
                    "## 一句话结论\n利率不变，市场读出鸽派信号。\n\n"
                    "## 已确认\n- 利率维持 5.25-5.50%\n- 声明删除\u201c进一步加息\u201d措辞\n\n"
                    "## 未确认 / 仅推断\n- 9月降息概率升至 68%（CME FedWatch）\n\n"
                    "## 最关键的冲突点\n就业数据仍强，通胀粘性未消。\n\n"
                    "## 接下来要盯的 3 个变量\n1. 6月非农\n2. 核心PCE\n3. 日元走势\n\n"
                    "## 什么会改变我的判断\n若6月CPI超预期反弹，鸽派叙事失效。\n"
                ),
                "article_markdown": "same as body_markdown for test",
                "manual_review": {},
                "publication_readiness": "ready",
            },
            "review_result": {},
            "draft_result": {},
        }

    def _make_request(self) -> dict:
        return {
            "analysis_time": "2026-04-18T10:00:00+00:00",
            "author": "Codex",
            "language_mode": "chinese",
            "wechat_cta_text": "👉 完整证据链 + 模板骨架，见公众号原文",
        }

    def test_builds_valid_contract(self) -> None:
        result = build_toutiao_fast_card_package(
            self._make_workflow_result(),
            self._make_selected_topic(),
            self._make_request(),
        )
        self.assertEqual(result["contract_version"], "toutiao-fast-card-package/v1")
        self.assertTrue(result["title"])
        self.assertTrue(result["one_line_takeaway"])
        self.assertTrue(result["confirmed"])
        self.assertTrue(result["unconfirmed"])
        self.assertTrue(result["conflict_point"])
        self.assertTrue(result["next_watch"])
        self.assertTrue(result["cta"])
        self.assertIsInstance(result["segments"], list)
        self.assertEqual(len(result["segments"]), 7)
        self.assertTrue(result["plain_text"])
        self.assertIn("toutiao-fast-card-package/v1", result["contract_version"])


if __name__ == "__main__":
    unittest.main()
