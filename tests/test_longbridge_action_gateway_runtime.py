#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "longbridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from longbridge_action_gateway_runtime import load_json, run_longbridge_action_gateway
from longbridge_action_plan_bridge import screen_result_to_gateway_actions


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 20) -> Any:
        del env, timeout_seconds
        self.calls.append(args)
        return {"ok": True, "args": args}


class LongbridgeActionGatewayRuntimeTests(unittest.TestCase):
    def test_load_json_accepts_control_character_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_bytes(b'{"actions":[],"note":"raw \x01 control"}')
            payload = load_json(path)

        self.assertEqual(payload["note"], "raw \x01 control")

    def test_screen_result_bridge_converts_tracking_suggestions_with_context(self) -> None:
        actions = screen_result_to_gateway_actions(
            {
                "ranked_candidates": [
                    {
                        "symbol": "600111.SH",
                        "screen_score": 72.5,
                        "signal": "momentum_breakout",
                        "tracking_plan": {
                            "suggested_watchlist_bucket": "breakout_with_catalyst",
                            "watchlist_action_suggestions": [
                                {"operation": "add", "target_bucket": "breakout_with_catalyst"}
                            ],
                            "alert_action_suggestions": [
                                {"operation": "add", "price": 53.46, "direction": "rise"},
                                {"operation": "disable", "id": "alert-stale"},
                            ],
                        },
                    }
                ]
            }
        )

        self.assertEqual(
            actions,
            [
                {
                    "type": "watchlist",
                    "operation": "add_stocks",
                    "group": "breakout_with_catalyst",
                    "symbols": ["600111.SH"],
                    "source": "longbridge-screen",
                    "source_candidate": {
                        "symbol": "600111.SH",
                        "screen_score": 72.5,
                        "signal": "momentum_breakout",
                        "suggested_watchlist_bucket": "breakout_with_catalyst",
                    },
                    "source_suggestion": {"operation": "add", "target_bucket": "breakout_with_catalyst"},
                },
                {
                    "type": "alert",
                    "operation": "add",
                    "symbol": "600111.SH",
                    "price": 53.46,
                    "direction": "rise",
                    "source": "longbridge-screen",
                    "source_candidate": {
                        "symbol": "600111.SH",
                        "screen_score": 72.5,
                        "signal": "momentum_breakout",
                        "suggested_watchlist_bucket": "breakout_with_catalyst",
                    },
                    "source_suggestion": {"operation": "add", "price": 53.46, "direction": "rise"},
                },
                {
                    "type": "alert",
                    "operation": "disable",
                    "id": "alert-stale",
                    "symbol": "600111.SH",
                    "source": "longbridge-screen",
                    "source_candidate": {
                        "symbol": "600111.SH",
                        "screen_score": 72.5,
                        "signal": "momentum_breakout",
                        "suggested_watchlist_bucket": "breakout_with_catalyst",
                    },
                    "source_suggestion": {"operation": "disable", "id": "alert-stale"},
                },
            ],
        )

    def test_gateway_consumes_screen_result_through_bridge_without_execution(self) -> None:
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {
                "screen_result": {
                    "ranked_candidates": [
                        {
                            "symbol": "600111.SH",
                            "screen_score": 72.5,
                            "signal": "momentum_breakout",
                            "tracking_plan": {
                                "suggested_watchlist_bucket": "breakout_with_catalyst",
                                "watchlist_action_suggestions": [
                                    {"operation": "add", "target_bucket": "breakout_with_catalyst"}
                                ],
                                "alert_action_suggestions": [
                                    {"operation": "add", "price": 53.46, "direction": "rise"}
                                ],
                            },
                        }
                    ]
                }
            },
            runner=runner,
            env={},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["rejected_actions"], [])
        self.assertEqual([plan["operation"] for plan in result["action_plans"]], ["watchlist.add_stocks", "alert.add"])
        self.assertTrue(all(plan["source_action"]["source"] == "longbridge-screen" for plan in result["action_plans"]))
        self.assertFalse(any(plan["should_apply"] for plan in result["action_plans"]))
        self.assertEqual(result["side_effects"], "none")

    def test_dry_run_watchlist_add_plan(self) -> None:
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {
                "actions": [
                    {
                        "type": "watchlist",
                        "operation": "add_stocks",
                        "group": "breakout_with_catalyst",
                        "symbols": ["600111.SH"],
                    }
                ]
            },
            runner=runner,
            env={},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["rejected_actions"], [])
        plan = result["action_plans"][0]
        self.assertEqual(plan["operation"], "watchlist.add_stocks")
        self.assertIn("longbridge watchlist update", plan["command_preview"])
        self.assertEqual(plan["symbol"], "600111.SH")
        self.assertEqual(plan["account_target"], "breakout_with_catalyst")
        self.assertEqual(plan["risk_level"], "medium")
        self.assertTrue(plan["required_confirmation"])
        self.assertFalse(plan["should_apply"])
        self.assertEqual(plan["side_effects"], "none")

    def test_dry_run_alert_add_and_delete_plan(self) -> None:
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {
                "actions": [
                    {
                        "type": "alert",
                        "operation": "add",
                        "symbol": "600111.SH",
                        "price": 53.46,
                        "direction": "rise",
                    },
                    {
                        "type": "alert",
                        "operation": "delete",
                        "id": "alert-stale",
                        "symbol": "000969.SZ",
                    },
                ]
            },
            runner=runner,
            env={},
        )

        self.assertEqual(runner.calls, [])
        add_plan, delete_plan = result["action_plans"]
        self.assertEqual(add_plan["operation"], "alert.add")
        self.assertIn("longbridge alert add 600111.SH", add_plan["command_preview"])
        self.assertEqual(add_plan["symbol"], "600111.SH")
        self.assertEqual(add_plan["account_target"], "price_alert")
        self.assertEqual(add_plan["side_effects"], "none")
        self.assertEqual(delete_plan["operation"], "alert.delete")
        self.assertIn("longbridge alert delete alert-stale", delete_plan["command_preview"])
        self.assertEqual(delete_plan["account_target"], "alert-stale")
        self.assertFalse(delete_plan["should_apply"])

    def test_order_buy_planner_blocked_by_default(self) -> None:
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {
                "actions": [
                    {
                        "type": "order",
                        "operation": "buy",
                        "symbol": "AAPL.US",
                        "quantity": 10,
                        "price": 180.5,
                    }
                ]
            },
            runner=runner,
            env={},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["apply"]["status"], "dry_run")
        plan = result["action_plans"][0]
        self.assertEqual(plan["operation"], "order.buy")
        self.assertEqual(plan["risk_level"], "critical")
        self.assertTrue(plan["hard_blocked"])
        self.assertIn("longbridge order buy AAPL.US 10", plan["command_preview"])
        self.assertFalse(plan["should_apply"])
        self.assertEqual(plan["side_effects"], "none")

    def test_order_apply_blocked_without_env(self) -> None:
        request = {
            "actions": [
                {
                    "type": "order",
                    "operation": "buy",
                    "symbol": "AAPL.US",
                    "quantity": 10,
                    "price": 180.5,
                }
            ]
        }
        dry_plan = run_longbridge_action_gateway(request, runner=RecordingRunner(), env={})["action_plans"][0]
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {**request, "apply": True, "confirmation_text": dry_plan["confirmation_text"]},
            runner=runner,
            env={},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["apply"]["status"], "blocked")
        self.assertIn("LONGBRIDGE_ALLOW_WRITE", result["apply"]["blocked_reasons"])

    def test_order_apply_blocked_without_exact_confirmation(self) -> None:
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {
                "apply": True,
                "confirmation_text": "CONFIRM THE WRONG ACTION",
                "actions": [
                    {
                        "type": "order",
                        "operation": "buy",
                        "symbol": "AAPL.US",
                        "quantity": 10,
                        "price": 180.5,
                    }
                ],
            },
            runner=runner,
            env={"LONGBRIDGE_ALLOW_WRITE": "1"},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["apply"]["status"], "blocked")
        self.assertIn("confirmation_text mismatch", result["apply"]["blocked_reasons"])

    def test_statement_export_rejects_path_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            repo_root = temp_root / "repo"
            repo_root.mkdir()
            outside_path = temp_root / "statement.csv"

            result = run_longbridge_action_gateway(
                {
                    "actions": [
                        {
                            "type": "statement",
                            "operation": "export",
                            "file_key": "statement-20260429",
                            "section": "equity_holdings",
                            "output_path": str(outside_path),
                        }
                    ]
                },
                runner=RecordingRunner(),
                env={},
                repo_root=repo_root,
            )

        self.assertEqual(result["action_plans"], [])
        self.assertEqual(result["rejected_actions"][0]["operation"], "statement.export")
        self.assertIn(".tmp/longbridge-statements", result["rejected_actions"][0]["reason"])

    def test_statement_export_accepts_repo_tmp_statement_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir()
            output_path = repo_root / ".tmp" / "longbridge-statements" / "statement.csv"

            result = run_longbridge_action_gateway(
                {
                    "actions": [
                        {
                            "type": "statement",
                            "operation": "export",
                            "file_key": "statement-20260429",
                            "section": "equity_holdings",
                            "output_path": str(output_path),
                        }
                    ]
                },
                runner=RecordingRunner(),
                env={},
                repo_root=repo_root,
            )

        self.assertEqual(result["rejected_actions"], [])
        plan = result["action_plans"][0]
        self.assertEqual(plan["operation"], "statement.export")
        self.assertIn("longbridge statement export", plan["command_preview"])
        self.assertIn(str(output_path), plan["command_preview"])
        self.assertEqual(plan["account_target"], str(output_path))
        self.assertFalse(plan["should_apply"])
        self.assertEqual(plan["side_effects"], "none")

    def test_apply_executes_allowlisted_watchlist_alert_and_statement_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir()
            output_path = repo_root / ".tmp" / "longbridge-statements" / "statement.csv"
            request = {
                "actions": [
                    {
                        "type": "watchlist",
                        "operation": "add_stocks",
                        "group": "breakout_with_catalyst",
                        "symbols": ["600111.SH"],
                    },
                    {
                        "type": "alert",
                        "operation": "add",
                        "symbol": "600111.SH",
                        "price": 53.46,
                        "direction": "rise",
                    },
                    {
                        "type": "statement",
                        "operation": "export",
                        "file_key": "statement-20260429",
                        "section": "equity_holdings",
                        "output_path": str(output_path),
                    },
                ]
            }
            dry_plan = run_longbridge_action_gateway(
                request,
                runner=RecordingRunner(),
                env={},
                repo_root=repo_root,
            )
            runner = RecordingRunner()

            result = run_longbridge_action_gateway(
                {**request, "apply": True, "confirmation_text": dry_plan["confirmation_text"]},
                runner=runner,
                env={"LONGBRIDGE_ALLOW_WRITE": "1"},
                repo_root=repo_root,
            )

        self.assertEqual(result["apply"]["status"], "executed")
        self.assertEqual(len(result["apply"]["executed"]), 3)
        self.assertEqual(
            runner.calls,
            [
                [
                    "watchlist",
                    "update",
                    "breakout_with_catalyst",
                    "--add",
                    "600111.SH",
                    "--format",
                    "json",
                ],
                [
                    "alert",
                    "add",
                    "600111.SH",
                    "--price",
                    "53.46",
                    "--direction",
                    "rise",
                    "--format",
                    "json",
                ],
                [
                    "statement",
                    "export",
                    "--file-key",
                    "statement-20260429",
                    "--section",
                    "equity_holdings",
                    "-o",
                    str(output_path),
                    "--format",
                    "json",
                ],
            ],
        )

    def test_apply_rejects_read_only_order_plan_outside_apply_allowlist(self) -> None:
        request = {"actions": [{"type": "order", "operation": "list", "symbol": "AAPL.US"}]}
        dry_plan = run_longbridge_action_gateway(request, runner=RecordingRunner(), env={})
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {**request, "apply": True, "confirmation_text": dry_plan["confirmation_text"]},
            runner=runner,
            env={"LONGBRIDGE_ALLOW_WRITE": "1"},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["apply"]["status"], "blocked")
        self.assertIn("operation not allowlisted for apply: order.list", result["apply"]["blocked_reasons"])

    def test_dca_apply_remains_hard_blocked_even_with_env_and_confirmation(self) -> None:
        request = {
            "actions": [
                {
                    "type": "dca",
                    "operation": "create",
                    "symbol": "AAPL.US",
                    "amount": 500,
                    "frequency": "monthly",
                }
            ]
        }
        dry_plan = run_longbridge_action_gateway(request, runner=RecordingRunner(), env={})
        runner = RecordingRunner()

        result = run_longbridge_action_gateway(
            {**request, "apply": True, "confirmation_text": dry_plan["confirmation_text"]},
            runner=runner,
            env={"LONGBRIDGE_ALLOW_WRITE": "1"},
        )

        self.assertEqual(runner.calls, [])
        self.assertEqual(result["apply"]["status"], "blocked")
        self.assertIn("hard-blocked operations cannot be applied: dca.create", result["apply"]["blocked_reasons"])


if __name__ == "__main__":
    unittest.main()
