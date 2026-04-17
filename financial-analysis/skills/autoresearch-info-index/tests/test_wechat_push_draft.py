from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wechat_push_draft import build_markdown


class WechatPushDraftCliTests(unittest.TestCase):
    def test_build_markdown_surfaces_workflow_publication_gate(self) -> None:
        markdown = build_markdown(
            {
                "status": "ok",
                "push_backend": "api",
                "workflow_publication_gate": {
                    "publication_readiness": "blocked_by_reddit_operator_review",
                    "manual_review": {
                        "status": "awaiting_reddit_operator_review",
                    },
                },
                "draft_result": {"media_id": "draft-123", "draft_url": "https://mp.weixin.qq.com/draft/123"},
                "uploaded_inline_images": [{"asset_id": "hero-01"}],
                "uploaded_cover": {"media_id": "cover-123"},
            }
        )

        self.assertIn("Workflow publication readiness: blocked_by_reddit_operator_review", markdown)
        self.assertIn("Workflow Reddit operator review: awaiting_reddit_operator_review", markdown)


if __name__ == "__main__":
    unittest.main()
