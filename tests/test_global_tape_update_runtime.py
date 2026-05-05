#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from global_tape_update_runtime import load_json, render_global_tape_update, run_global_tape_update


class GlobalTapeUpdateRuntimeTests(unittest.TestCase):
    def _shortlist_result(self) -> dict[str, object]:
        return {
            "filter_summary": {
                "cache_baseline_trade_date": "2026-04-30",
                "live_supplement_status": "unavailable",
            },
            "run_completeness": {"status": "degraded"},
            "diagnostic_scorecard": [
                {"ticker": "002281.SZ", "name": "光迅科技"},
                {"ticker": "002384.SZ", "name": "东山精密"},
                {"ticker": "600111.SS", "name": "北方稀土"},
                {"ticker": "601138.SS", "name": "工业富联"},
            ],
        }

    def _tape_update(self) -> dict[str, object]:
        return {
            "target_trade_date": "2026-05-06",
            "analysis_date": "2026-05-05",
            "local_artifacts": [
                ".tmp/plan-2026-05-01-postholiday/result.month-end-shortlist.focused.json",
                ".tmp/plan-2026-05-01-postholiday/report.x-index.holiday-themes.md",
            ],
            "external_boundary": [
                "港股使用 2026-05-05 最新可见交易数据",
                "日本最新完成交易日为 2026-05-01",
                "韩国最新完成交易日为 2026-05-04",
            ],
            "markets": [
                {
                    "title": "港股：5 月 5 日风险偏好降温",
                    "bullets": [
                        "恒生指数约 25,713 点，日内跌约 1.5%。",
                        "港股科技权重走弱，抵消日韩半导体强 tape 的一部分加分。",
                    ],
                },
                {
                    "title": "韩国：半导体最强，但需防高开消化",
                    "bullets": [
                        "KOSPI 约 6,937 点，涨约 5.1%，创历史新高。",
                        "SK hynix 和 Samsung Electronics 强势，对 AI 硬件链加分。",
                    ],
                },
            ],
            "events": [
                {
                    "title": "美伊 / 中东冲突",
                    "bullets": [
                        "霍尔木兹事件升级给油运和能源链加分。",
                        "冲突也压制整体风险偏好，不能直接升级为主线。",
                    ],
                }
            ],
            "directions": [
                {
                    "name": "AI 硬件 / 光模块 / PCB",
                    "previous": "第一观察方向",
                    "current": "第一观察方向，维持偏多",
                    "adjustment": "小幅加分但不升级仓位",
                    "reason": "韩国半导体 record tape 强，但港股科技权重走弱。",
                },
                {
                    "name": "油运 / 中东冲突",
                    "previous": "事件副线",
                    "current": "事件副线，观察优先级上调",
                    "adjustment": "加分但不进主仓",
                    "reason": "冲突升级但油价和港股能源未形成全面主线。",
                },
            ],
            "core_levels": [
                {
                    "ticker": "002281.SZ",
                    "role": "AI 光模块主观察",
                    "confirm": "146.16",
                    "target": "153.47 参考压力",
                    "abandon": "115.53",
                    "handling": "只有 146.16 上方放量站稳且光模块/PCB 扩散才执行",
                },
                {
                    "ticker": "600111.SS",
                    "role": "稀土资源次主线",
                    "confirm": "53.04 上方承接",
                    "target": "58.30 / 63.57",
                    "abandon": "49.72",
                    "handling": "只在资源/稀土链同步时升权",
                },
            ],
            "intraday_triggers": [
                "AI 链双核心确认：`002281.SZ` 站稳 146.16，`002384.SZ` 站稳 196.00。",
                "稀土资源确认：`600111.SS` 在 53.04 上方放量承接。",
            ],
            "position_rules": [
                "原执行版仓位框架不提高。",
                "无确认：0%，保持空仓观察。",
            ],
            "empty_watch_rules": [
                "09:45-10:30 没有任何核心票站稳确认位。",
            ],
            "remaining_risks": [
                "Longbridge CLI 当前未登录，未能用本地 Longbridge 账户拉取实时 quote。",
                "5 月 6 日 A 股盘中成交和主线涨停结构尚未发生。",
            ],
            "sources": [
                {"label": "Trading Economics Hong Kong", "url": "https://tradingeconomics.com/hong-kong/stock-market"},
            ],
        }

    def test_render_global_tape_update_uses_local_names_and_required_sections(self) -> None:
        markdown = render_global_tape_update(self._shortlist_result(), self._tape_update())

        self.assertIn("# 2026-05-06 节后交易计划：全球 tape 更新版", markdown)
        self.assertIn("## 代码名称映射", markdown)
        self.assertIn("| `002281.SZ` | 光迅科技 | AI 光模块主观察 |", markdown)
        self.assertIn("| `600111.SS` | 北方稀土 | 稀土资源次主线 |", markdown)
        self.assertIn("## 外盘信号", markdown)
        self.assertIn("## 事件信号", markdown)
        self.assertIn("## 方向权重", markdown)
        self.assertIn("## 分时触发", markdown)
        self.assertIn("## 仓位", markdown)
        self.assertIn("## 确认 / 放弃规则", markdown)
        self.assertIn("`002281.SZ` 光迅科技站稳 146.16", markdown)
        self.assertIn("`002384.SZ` 东山精密站稳 196.00", markdown)
        self.assertIn("`600111.SS` 北方稀土在 53.04 上方放量承接", markdown)
        self.assertIn("Longbridge CLI 当前未登录", markdown)
        self.assertNotIn("`002281.SZ` 站稳", markdown)

    def test_run_global_tape_update_writes_markdown_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "global-tape-update.md"
            result = run_global_tape_update(
                self._shortlist_result(),
                self._tape_update(),
                markdown_output=output,
            )

            self.assertEqual(result["markdown_path"], str(output))
            self.assertTrue(output.exists())
            self.assertIn("## 盘中需要确认的数据", output.read_text(encoding="utf-8"))

    def test_load_json_accepts_utf8_sig_files_from_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tape.json"
            path.write_text(json.dumps({"target_trade_date": "2026-05-06"}, ensure_ascii=False), encoding="utf-8-sig")

            self.assertEqual(load_json(path)["target_trade_date"], "2026-05-06")


if __name__ == "__main__":
    unittest.main()
