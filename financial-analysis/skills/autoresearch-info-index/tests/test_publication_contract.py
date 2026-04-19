from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from publication_contract_runtime import load_publication_contract, validate_publication_contract


class PublicationContractTests(unittest.TestCase):
    def test_validate_requires_core_shared_fields(self) -> None:
        package = {
            "contract_version": "publish-package/v1",
            "title": "测试标题",
            "subtitle": "测试副题",
            "lede": "测试导语",
            "sections": [{"heading": "一", "paragraph": "内容"}],
            "content_markdown": "# 标题\n\n正文",
            "content_html": "<p>正文</p>",
            "selected_images": [],
            "cover_plan": {},
            "platform_hints": {},
            "style_profile_applied": {},
            "operator_notes": [],
            "draft_thesis": "一句话结论",
            "citations": [],
        }
        result = validate_publication_contract(package)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing_fields"], [])

    def test_load_contract_accepts_direct_package_or_wrapper(self) -> None:
        package = {
            "contract_version": "publish-package/v1",
            "title": "测试标题",
            "subtitle": "测试副题",
            "lede": "测试导语",
            "sections": [],
            "content_markdown": "正文",
            "content_html": "<p>正文</p>",
            "selected_images": [],
            "cover_plan": {},
            "platform_hints": {},
            "style_profile_applied": {},
            "operator_notes": [],
            "draft_thesis": "一句话结论",
            "citations": [],
        }
        self.assertEqual(load_publication_contract(package)["title"], "测试标题")
        self.assertEqual(load_publication_contract({"publish_package": package})["title"], "测试标题")

    def test_validate_requires_supported_contract_version(self) -> None:
        package = {
            "contract_version": "wechat-draft-package/v1",
            "title": "测试标题",
            "subtitle": "测试副题",
            "lede": "测试导语",
            "sections": [],
            "content_markdown": "正文",
            "content_html": "<p>正文</p>",
            "selected_images": [],
            "cover_plan": {},
            "platform_hints": {},
            "style_profile_applied": {},
            "operator_notes": [],
            "draft_thesis": "一句话结论",
            "citations": [],
        }
        result = validate_publication_contract(package)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["expected_contract_version"], "publish-package/v1")
        self.assertEqual(result["actual_contract_version"], "wechat-draft-package/v1")


if __name__ == "__main__":
    unittest.main()
