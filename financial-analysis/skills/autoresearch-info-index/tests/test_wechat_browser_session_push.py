from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
HELPER_PATH = SCRIPT_DIR / "wechat_browser_session_push.js"


class WechatBrowserSessionPushTests(unittest.TestCase):
    def run_helper(self, expression: str) -> str:
        node_path = shutil.which("node")
        if not node_path:
            self.skipTest("node runtime is required")
        completed = subprocess.run(
            [node_path, "-e", expression],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return completed.stdout.strip()

    def helper_expression(self, body: str) -> str:
        helper_path = json.dumps(str(HELPER_PATH))
        return (
            f"const helper = require({helper_path});\n"
            f"{body}\n"
        )

    def test_choose_wechat_target_prefers_existing_editor_tab(self) -> None:
        tabs = [
            {
                "id": "read-page",
                "type": "page",
                "title": "Article",
                "url": "https://mp.weixin.qq.com/s/example",
            },
            {
                "id": "editor-page",
                "type": "page",
                "title": "公众号",
                "url": "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&token=1952701323&lang=zh_CN",
            },
            {
                "id": "other-page",
                "type": "page",
                "title": "Example",
                "url": "https://example.com/",
            },
        ]
        expression = self.helper_expression(
            "const result = helper.chooseWechatTarget("
            f"{json.dumps(tabs)}, "
            "{ editorUrl: 'https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&token=1952701323&lang=zh_CN', homeUrl: 'https://mp.weixin.qq.com/' }"
            ");\n"
            "process.stdout.write(JSON.stringify(result));"
        )
        raw_output = self.run_helper(expression)
        payload = json.loads(raw_output)

        self.assertEqual(payload["target"]["id"], "editor-page")
        self.assertTrue(payload["reusedExisting"])
        self.assertFalse(payload["shouldNavigate"])
        self.assertFalse(payload["shouldClose"])

    def test_choose_wechat_target_refreshes_stale_editor_draft(self) -> None:
        tabs = [
            {
                "id": "editor-page",
                "type": "page",
                "title": "公众号",
                "url": "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&reprint_confirm=0&timestamp=1776827043386&type=77&appmsgid=100000122&token=1952701323&lang=zh_CN",
            }
        ]
        expression = self.helper_expression(
            "const result = helper.chooseWechatTarget("
            f"{json.dumps(tabs)}, "
            "{ editorUrl: 'https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&token=1952701323&lang=zh_CN', homeUrl: 'https://mp.weixin.qq.com/' }"
            ");\n"
            "process.stdout.write(JSON.stringify(result));"
        )
        raw_output = self.run_helper(expression)
        payload = json.loads(raw_output)

        self.assertEqual(payload["target"]["id"], "editor-page")
        self.assertTrue(payload["reusedExisting"])
        self.assertTrue(payload["shouldNavigate"])
        self.assertEqual(
            payload["navigateUrl"],
            "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77&token=1952701323&lang=zh_CN",
        )

    def test_content_setter_targets_prosemirror_and_input_events(self) -> None:
        expression = self.helper_expression(
            "const value = helper.buildContentSetterExpression('<p>hello</p>');\n"
            "process.stdout.write(value);"
        )
        output = self.run_helper(expression)

        self.assertIn(".ProseMirror", output)
        self.assertIn("createContextualFragment", output)
        self.assertIn("new InputEvent('input'", output)
        self.assertNotIn("innerHTML = html", output)

    def test_cover_picker_expression_targets_current_wechat_dialog(self) -> None:
        expression = self.helper_expression(
            "const value = helper.buildCoverPickerPreparationExpression();\n"
            "process.stdout.write(value);"
        )
        output = self.run_helper(expression)

        self.assertIn("#js_cover_area", output)
        self.assertIn("#js_cover_null .js_imagedialog", output)
        self.assertIn(".weui-desktop-dialog_img-picker", output)
        self.assertIn("js_upload_btn_container", output)

    def test_save_click_expression_prefers_send_wording_button(self) -> None:
        expression = self.helper_expression(
            "const value = helper.buildSaveDraftClickExpression();\n"
            "process.stdout.write(value);"
        )
        output = self.run_helper(expression)

        self.assertIn(".send_wording", output)
        self.assertIn("保存为草稿", output)
        self.assertIn("closest('button')", output)


if __name__ == "__main__":
    unittest.main()
