#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from stock_watch_workflow import (
    apply_driver_state_guardrails,
    build_opencli_bridge_result_for_request,
    build_gs_quant_bundle_plans,
    build_compare_note_payload,
    build_source_delta,
    build_stock_workflow_summary,
    build_result_summary,
    choose_execution_mode,
    maybe_generate_gs_quant_workflows,
    normalize_gs_quant_ticker,
    project_opencli_candidates_for_request,
    refresh_single_stock,
    render_compare_note_markdown,
    workflow_paths,
)


def make_observation(
    source_id: str,
    *,
    source_name: str,
    source_type: str,
    claim_ids: list[str] | None = None,
    claim_states: dict[str, str] | None = None,
    raw_metadata: dict[str, object] | None = None,
    access_mode: str = "public",
    age_minutes: float = 5.0,
    source_tier: int = 0,
    channel: str = "core",
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_type": source_type,
        "published_at": "2026-04-02T11:55:00+00:00",
        "observed_at": "2026-04-02T11:56:00+00:00",
        "claim_ids": claim_ids or [],
        "claim_states": claim_states or {},
        "text_excerpt": f"{source_name} evidence",
        "access_mode": access_mode,
        "age_minutes": age_minutes,
        "age_label": "5m",
        "source_tier": source_tier,
        "channel": channel,
        "raw_metadata": raw_metadata or {},
        "origin": "",
        "agent_reach_channel": "",
        "url": "",
    }


def make_compare_updates() -> list[dict[str, object]]:
    return [
        {
            "stock": {"slug": "chalco-a", "name": "Chalco", "ticker": "601600.SH"},
            "workflow_summary": {
                "strongest_request": "driver_state",
                "total_new_sources": 1,
                "total_new_baseline_sources": 0,
                "total_new_external_sources": 1,
            },
            "run_results": [
                {
                    "request_name": "company_state",
                    "summary": {
                        "core_verdict": "Company state looks better anchored.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [10, 58],
                        "confirmed_count": 1,
                        "external_source_count": 3,
                        "fresh_external_source_count": 1,
                    },
                },
                {
                    "request_name": "earnings_freshness",
                    "summary": {
                        "core_verdict": "Earnings freshness still thin.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [8, 50],
                        "confirmed_count": 0,
                        "external_source_count": 2,
                        "fresh_external_source_count": 0,
                    },
                },
                {
                    "request_name": "driver_state",
                    "summary": {
                        "core_verdict": "Driver state has at least some external checks.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [12, 60],
                        "confirmed_count": 1,
                        "external_source_count": 4,
                        "fresh_external_source_count": 1,
                        "driver_evidence_status": "fresh_external_evidence",
                    },
                },
            ],
        },
        {
            "stock": {"slug": "envicool-a", "name": "Envicool", "ticker": "002837.SZ"},
            "workflow_summary": {
                "strongest_request": "company_state",
                "total_new_sources": 0,
                "total_new_baseline_sources": 0,
                "total_new_external_sources": 0,
            },
            "run_results": [
                {
                    "request_name": "company_state",
                    "summary": {
                        "core_verdict": "Company state is still mostly shadow tape.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [5, 40],
                        "confirmed_count": 0,
                        "external_source_count": 0,
                        "fresh_external_source_count": 0,
                    },
                },
                {
                    "request_name": "earnings_freshness",
                    "summary": {
                        "core_verdict": "No external filing anchor yet.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [5, 35],
                        "confirmed_count": 0,
                        "external_source_count": 0,
                        "fresh_external_source_count": 0,
                    },
                },
                {
                    "request_name": "driver_state",
                    "summary": {
                        "core_verdict": "Still baseline driven.",
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [5, 38],
                        "confirmed_count": 0,
                        "external_source_count": 0,
                        "fresh_external_source_count": 0,
                        "driver_evidence_status": "baseline_only",
                    },
                },
            ],
        },
    ]


def fake_opencli_bridge_result() -> dict[str, object]:
    return {
        "request": {
            "topic": "tracked stock opencli check",
            "analysis_time": "2026-04-03T08:00:00+00:00",
            "site_profile": "broker-research-portal",
            "input_mode": "result_path",
        },
        "import_summary": {
            "payload_source": "result_path",
            "imported_candidate_count": 1,
        },
        "runner_summary": {
            "status": "ok",
        },
        "retrieval_request": {
            "candidates": [
                {
                    "source_id": "opencli-shared-note",
                    "source_name": "Broker portal note",
                    "source_type": "research_note",
                    "origin": "opencli",
                    "published_at": "2026-04-03T07:20:00+00:00",
                    "observed_at": "2026-04-03T07:25:00+00:00",
                    "url": "https://research.example.com/china-aluminum-note",
                    "claim_ids": [],
                    "claim_states": {},
                    "text_excerpt": "OpenCLI imported broker note excerpt.",
                    "channel": "shadow",
                    "access_mode": "browser_session",
                    "artifact_manifest": [],
                    "raw_metadata": {
                        "opencli": {"site_profile": "broker-research-portal"},
                        "source_item": {"claim_state": "support"},
                    },
                }
            ]
        },
        "report_markdown": "# OpenCLI Bridge\n",
    }


def fake_stock_result(request: dict[str, object], *, core_verdict: str = "Result ready.") -> dict[str, object]:
    return {
        "request": {
            "topic": request.get("topic", ""),
            "analysis_time": request.get("analysis_time", "2026-04-03T08:00:00+00:00"),
        },
        "observations": [],
        "verdict_output": {
            "core_verdict": core_verdict,
            "confidence_gate": "shadow-heavy",
            "confidence_interval": [8, 42],
            "confirmed": [],
            "not_confirmed": [],
            "inference_only": [],
            "freshness_panel": [],
        },
        "workflow_context": {
            "external_source_count": 0,
            "fresh_external_source_count": 0,
        },
        "report_markdown": "# News Index Report\n",
    }


class StockWatchWorkflowTests(unittest.TestCase):
    def test_project_opencli_candidates_for_request_assigns_single_claim_from_source_item(self) -> None:
        projected = project_opencli_candidates_for_request(
            [
                {
                    "source_id": "opencli-shared-note",
                    "claim_ids": [],
                    "claim_states": {},
                    "raw_metadata": {
                        "source_item": {
                            "claim_states": {"latest-report-identified": "contradict"},
                        }
                    },
                }
            ],
            {
                "claims": [
                    {
                        "claim_id": "latest-report-identified",
                        "claim_text": "The latest report is identified with an exact release date.",
                    }
                ]
            },
        )

        self.assertEqual(projected[0]["claim_ids"], ["latest-report-identified"])
        self.assertEqual(projected[0]["claim_states"], {"latest-report-identified": "contradict"})

    def test_build_opencli_bridge_result_for_request_leaves_multi_claim_requests_unassigned(self) -> None:
        bridge_result = build_opencli_bridge_result_for_request(
            fake_opencli_bridge_result(),
            {
                "topic": "中国铝业 latest company-state verification",
                "analysis_time": "2026-04-03T08:00:00+00:00",
                "questions": ["What changed?"],
                "use_case": "tracked-stock-company-state",
                "source_preferences": ["public-first"],
                "mode": "generic",
                "windows": ["1h"],
                "claims": [
                    {"claim_id": "latest-filing-known", "claim_text": "Latest filing known."},
                    {"claim_id": "material-update-exists", "claim_text": "Material update exists."},
                ],
                "market_relevance": ["company state"],
                "expected_source_families": ["broker-research"],
            },
        )

        opencli_candidate = bridge_result["retrieval_request"]["candidates"][0]
        self.assertEqual(bridge_result["request"]["topic"], "中国铝业 latest company-state verification")
        self.assertEqual(opencli_candidate["claim_ids"], [])
        self.assertEqual(opencli_candidate["claim_states"], {})

    def test_choose_execution_mode_distinguishes_auto_refresh_and_full(self) -> None:
        config = {"prefer_news_refresh": True, "default_execution_mode": "auto"}
        tmp_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-workflow"
        tmp_root.mkdir(parents=True, exist_ok=True)
        result_path = tmp_root / "mode.result.json"
        if result_path.exists():
            result_path.unlink()

        self.assertEqual(choose_execution_mode("auto", config, result_path), "news_index")
        self.assertEqual(choose_execution_mode("refresh", config, result_path), "news_index_bootstrap")
        self.assertEqual(choose_execution_mode("full", config, result_path), "news_index")

        result_path.write_text("{}", encoding="utf-8")
        self.assertEqual(choose_execution_mode("auto", config, result_path), "news_refresh")
        self.assertEqual(choose_execution_mode("refresh", config, result_path), "news_refresh")
        self.assertEqual(choose_execution_mode("full", config, result_path), "news_rebuild")

    def test_build_source_delta_separates_baseline_and_external_sources(self) -> None:
        previous_result = {
            "observations": [
                make_observation(
                    "driver-keywords-baseline",
                    source_name="Driver keywords baseline",
                    source_type="analysis",
                    raw_metadata={"baseline_only": True, "baseline_group": "driver_profile"},
                    source_tier=2,
                    channel="background",
                ),
                make_observation(
                    "eastmoney-old",
                    source_name="Eastmoney filing",
                    source_type="company_filing",
                ),
            ]
        }
        current_result = {
            "observations": previous_result["observations"]
            + [
                make_observation(
                    "watch-items-baseline",
                    source_name="Watch items baseline",
                    source_type="analysis",
                    raw_metadata={"baseline_only": True, "baseline_group": "driver_profile"},
                    source_tier=2,
                    channel="background",
                ),
                make_observation(
                    "eastmoney-new",
                    source_name="Eastmoney new filing",
                    source_type="company_filing",
                ),
            ]
        }

        delta = build_source_delta(previous_result, current_result)

        self.assertEqual(delta["new_source_count"], 2)
        self.assertEqual(delta["new_baseline_source_count"], 1)
        self.assertEqual(delta["new_external_source_count"], 1)
        self.assertEqual(delta["new_baseline_source_ids"], ["watch-items-baseline"])
        self.assertEqual(delta["new_external_source_ids"], ["eastmoney-new"])
        self.assertFalse(delta["captured_only_baseline_sources"])

    def test_build_stock_workflow_summary_calls_out_baseline_only_changes(self) -> None:
        summary = build_stock_workflow_summary(
            [
                {
                    "mode": "news_refresh",
                    "captured_new_sources": True,
                    "captured_new_external_sources": False,
                    "captured_only_baseline_sources": True,
                    "request_name": "driver_state",
                    "summary": {
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [5, 45],
                        "external_source_count": 0,
                        "driver_evidence_status": "baseline_only",
                    },
                    "source_delta": {
                        "new_source_count": 2,
                        "new_baseline_source_count": 2,
                        "new_external_source_count": 0,
                    },
                }
            ],
            "auto",
        )

        self.assertEqual(summary["total_new_sources"], 2)
        self.assertEqual(summary["total_new_baseline_sources"], 2)
        self.assertEqual(summary["requests_with_only_baseline_source_changes"], 1)
        self.assertIn("只变动了 baseline/profile 输入", summary["one_line"])

    def test_build_stock_workflow_summary_supports_explicit_english_output(self) -> None:
        summary = build_stock_workflow_summary(
            [
                {
                    "mode": "news_index",
                    "captured_new_sources": False,
                    "captured_new_external_sources": False,
                    "captured_only_baseline_sources": False,
                    "request_name": "company_state",
                    "summary": {
                        "confidence_gate": "shadow-heavy",
                        "confidence_interval": [5, 30],
                        "external_source_count": 0,
                    },
                    "source_delta": {
                        "new_source_count": 0,
                        "new_baseline_source_count": 0,
                        "new_external_source_count": 0,
                    },
                }
            ],
            "auto",
            output_language="en",
        )

        self.assertEqual(summary["output_language"], "en")
        self.assertIn("No new source was captured in this run", summary["one_line"])

    def test_apply_driver_state_guardrails_keeps_baseline_only_case_non_usable(self) -> None:
        guarded = apply_driver_state_guardrails(
            {
                "request": {
                    "topic": "Driver test",
                    "analysis_time": "2026-04-02T12:00:00+00:00",
                    "claims": [
                        {
                            "claim_id": "driver-state-known",
                            "claim_text": "Driver state is known with exact dates.",
                        }
                    ],
                    "candidates": [],
                },
                "observations": [
                    make_observation(
                        "driver-keywords-baseline",
                        source_name="Driver keywords",
                        source_type="analysis",
                        claim_ids=["driver-state-known"],
                        claim_states={"driver-state-known": "support"},
                        raw_metadata={"baseline_only": True, "baseline_group": "driver_profile"},
                        source_tier=2,
                        channel="shadow",
                    )
                ],
            }
        )

        summary = build_result_summary(guarded)

        self.assertEqual(summary["driver_evidence_status"], "baseline_only")
        self.assertEqual(summary["external_source_count"], 0)
        self.assertNotEqual(summary["confidence_gate"], "usable")
        self.assertIn("did not capture fresh external driver evidence", summary["core_verdict"])
        self.assertEqual(guarded["observations"][0]["claim_ids"], [])

    def test_compare_note_payload_and_markdown_rank_leader_and_laggard(self) -> None:
        updates = [
            {
                "stock": {"slug": "chalco-a", "name": "中国铝业", "ticker": "601600.SH"},
                "workflow_summary": {
                    "strongest_request": "driver_state",
                    "total_new_sources": 1,
                    "total_new_baseline_sources": 0,
                    "total_new_external_sources": 1,
                },
                "run_results": [
                    {
                        "request_name": "company_state",
                        "summary": {
                            "core_verdict": "Company state looks better anchored.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [10, 58],
                            "confirmed_count": 1,
                            "external_source_count": 3,
                            "fresh_external_source_count": 1,
                        },
                    },
                    {
                        "request_name": "earnings_freshness",
                        "summary": {
                            "core_verdict": "Earnings freshness still thin.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [8, 50],
                            "confirmed_count": 0,
                            "external_source_count": 2,
                            "fresh_external_source_count": 0,
                        },
                    },
                    {
                        "request_name": "driver_state",
                        "summary": {
                            "core_verdict": "Driver state has at least some external checks.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [12, 60],
                            "confirmed_count": 1,
                            "external_source_count": 4,
                            "fresh_external_source_count": 1,
                            "driver_evidence_status": "fresh_external_evidence",
                        },
                    },
                ],
            },
            {
                "stock": {"slug": "envicool-a", "name": "英维克", "ticker": "002837.SZ"},
                "workflow_summary": {
                    "strongest_request": "company_state",
                    "total_new_sources": 0,
                    "total_new_baseline_sources": 0,
                    "total_new_external_sources": 0,
                },
                "run_results": [
                    {
                        "request_name": "company_state",
                        "summary": {
                            "core_verdict": "Company state is still mostly shadow tape.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [5, 40],
                            "confirmed_count": 0,
                            "external_source_count": 0,
                            "fresh_external_source_count": 0,
                        },
                    },
                    {
                        "request_name": "earnings_freshness",
                        "summary": {
                            "core_verdict": "No external filing anchor yet.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [5, 35],
                            "confirmed_count": 0,
                            "external_source_count": 0,
                            "fresh_external_source_count": 0,
                        },
                    },
                    {
                        "request_name": "driver_state",
                        "summary": {
                            "core_verdict": "Still baseline driven.",
                            "confidence_gate": "shadow-heavy",
                            "confidence_interval": [5, 38],
                            "confirmed_count": 0,
                            "external_source_count": 0,
                            "fresh_external_source_count": 0,
                            "driver_evidence_status": "baseline_only",
                        },
                    },
                ],
            },
        ]

        payload = build_compare_note_payload(updates, "2026-04-02T12:30:00+00:00")
        markdown = render_compare_note_markdown(payload)

        self.assertEqual(payload["leader_slug"], "chalco-a")
        self.assertEqual(payload["laggard_slug"], "envicool-a")
        self.assertEqual(payload["stocks"][0]["slug"], "chalco-a")
        self.assertIn("外部来源深度", payload["comparison_basis"])
        self.assertIn("- 领先项: `中国铝业`", markdown)
        self.assertIn("- 落后项: `英维克`", markdown)
        self.assertIn("证据快照：", markdown)

    def test_compare_note_payload_can_render_english_template(self) -> None:
        payload = build_compare_note_payload(make_compare_updates(), "2026-04-02T12:30:00+00:00", output_language="en")
        markdown = render_compare_note_markdown(payload, output_language="en")

        self.assertEqual(payload["output_language"], "en")
        self.assertIn("external-source depth", payload["comparison_basis"])
        self.assertIn("# Tracked Stock Compare Note", markdown)
        self.assertIn("- Leader: `Chalco`", markdown)
        self.assertIn("- Laggard: `Envicool`", markdown)
        self.assertIn("- Evidence snapshot: 9 external source(s), 2 fresh external source(s), best upper confidence 60", markdown)

    def test_normalize_gs_quant_ticker_maps_sh_to_ss(self) -> None:
        self.assertEqual(normalize_gs_quant_ticker("601600.SH"), "601600.SS")
        self.assertEqual(normalize_gs_quant_ticker("002837.SZ"), "002837.SZ")

    def test_build_gs_quant_bundle_plans_targets_top_two_stocks(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        compare_payload = build_compare_note_payload(make_compare_updates(), "2026-04-02T12:30:00+00:00")

        plans = build_gs_quant_bundle_plans(repo_root, compare_payload, workflow_paths(repo_root))

        self.assertEqual(
            [plan["command_name"] for plan in plans],
            ["thesis-to-backtest", "basket-scenario-check", "gs-quant-backtesting"],
        )
        self.assertTrue(all("--workflow-file" in plan["command"] for plan in plans))
        self.assertTrue(all("--task" not in plan["command"] for plan in plans))
        self.assertTrue(all("chalco-a-envicool-a" in str(plan["output_dir"]) for plan in plans))

    def test_maybe_generate_gs_quant_workflows_uses_workflow_bridge_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-gs-quant"
        repo_root.mkdir(parents=True, exist_ok=True)
        paths = workflow_paths(repo_root)
        config = {"generate_gs_quant_workflows": True, "output_language": "zh-CN"}
        observed_commands: list[list[str]] = []

        def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            observed_commands.append(command)
            self.assertIn("--workflow-file", command)
            self.assertNotIn("--task", command)
            self.assertEqual(kwargs.get("encoding"), "utf-8")
            self.assertEqual(kwargs.get("errors"), "replace")
            workflow_path = Path(command[command.index("--workflow-file") + 1])
            output_dir = Path(command[command.index("--output-dir") + 1])
            self.assertTrue(workflow_path.exists())
            self.assertIn("## Scaffold Spec", workflow_path.read_text(encoding="utf-8"))
            if output_dir.name == "thesis-to-backtest":
                self.assertIn("Compare note: Chalco currently carries the richer evidence base", workflow_path.read_text(encoding="utf-8"))
            output_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = output_dir / "bridge-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "generatedAt": "2026-04-02T12:30:00Z",
                        "inputMode": "workflow",
                        "outputDir": str(output_dir),
                        "materialization": {
                            "mode": output_dir.name,
                            "strategyName": f"{output_dir.name}-strategy",
                        },
                        "artifacts": {
                            "workflow": {
                                "path": str(workflow_path),
                                "exists": True,
                                "written": False,
                                "bytes": workflow_path.stat().st_size,
                            },
                            "manifest": {
                                "path": str(manifest_path),
                                "exists": True,
                                "written": True,
                                "bytes": 1,
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "inputMode": "workflow",
                        "artifactStage": "full",
                        "materialization": {
                            "mode": output_dir.name,
                            "strategyName": f"{output_dir.name}-strategy",
                        },
                        "statuses": {
                            "workflowWritten": False,
                            "specWritten": True,
                            "pythonWritten": True,
                            "manifestWritten": True,
                        },
                    }
                ),
                stderr="",
            )

        summary = maybe_generate_gs_quant_workflows(
            repo_root,
            paths,
            config,
            make_compare_updates(),
            prepare_only=False,
            command_runner=fake_runner,
        )

        self.assertEqual(summary["status"], "ready")
        self.assertEqual(len(summary["bundles"]), 3)
        self.assertEqual(len(observed_commands), 3)
        self.assertTrue(all(bundle["bridge_summary"]["inputMode"] == "workflow" for bundle in summary["bundles"]))
        self.assertTrue(all(bundle["bridge_summary"]["mode"] == bundle["command_name"] for bundle in summary["bundles"]))
        self.assertTrue(all(bundle["stdout_tail"] == "" for bundle in summary["bundles"]))
        self.assertTrue(paths["gs_quant_summary"].exists())
        self.assertTrue(paths["gs_quant_summary_md"].exists())
        self.assertIn("# 股票池 GS Quant 工作流摘要", paths["gs_quant_summary_md"].read_text(encoding="utf-8"))
        self.assertIn("- 对比结论:", paths["gs_quant_summary_md"].read_text(encoding="utf-8"))

    def test_refresh_single_stock_merges_opencli_candidates_into_news_index_request(self) -> None:
        repo_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-opencli-news-index"
        repo_root.mkdir(parents=True, exist_ok=True)
        paths = workflow_paths(repo_root)
        stock = {
            "slug": "chalco-a",
            "name": "中国铝业",
            "ticker": "601600.SH",
            "market": "A-share",
            "aliases": [],
            "peer_keywords": [],
            "driver_keywords": ["aluminum"],
            "watch_items": ["LME aluminum"],
            "sector": "Metals",
            "status": "active",
        }
        captured_requests: list[dict[str, object]] = []

        def fake_run_news_index(payload: dict[str, object]) -> dict[str, object]:
            captured_requests.append(payload)
            return fake_stock_result(payload)

        with (
            patch(
                "stock_watch_workflow.resolve_opencli_payload",
                return_value=([{"url": "https://research.example.com/china-aluminum-note"}], "result_path", "C:\\path\\to\\opencli-result.json", {"status": "ok"}),
            ) as resolve_capture,
            patch("stock_watch_workflow.prepare_opencli_bridge", return_value=fake_opencli_bridge_result()) as prepare_bridge,
            patch("stock_watch_workflow.run_news_index", side_effect=fake_run_news_index),
        ):
            update = refresh_single_stock(
                repo_root,
                stock,
                paths=paths,
                config={
                    "use_opencli": True,
                    "opencli": {
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\opencli-result.json",
                    },
                },
                execution_mode_requested="full",
                prepare_only=False,
            )

        self.assertEqual(resolve_capture.call_count, 1)
        self.assertEqual(prepare_bridge.call_count, 1)
        self.assertEqual(len(captured_requests), 3)
        self.assertTrue(all(any(item.get("origin") == "opencli" for item in request.get("candidates", [])) for request in captured_requests))
        company_opencli = next(item for item in captured_requests[0]["candidates"] if item.get("origin") == "opencli")
        earnings_opencli = next(item for item in captured_requests[1]["candidates"] if item.get("origin") == "opencli")
        driver_opencli = next(item for item in captured_requests[2]["candidates"] if item.get("origin") == "opencli")
        self.assertEqual(company_opencli["claim_ids"], [])
        self.assertEqual(company_opencli["claim_states"], {})
        self.assertEqual(earnings_opencli["claim_ids"], ["latest-report-identified"])
        self.assertEqual(earnings_opencli["claim_states"], {"latest-report-identified": "support"})
        self.assertEqual(driver_opencli["claim_ids"], ["driver-state-known"])
        self.assertEqual(driver_opencli["claim_states"], {"driver-state-known": "support"})
        self.assertEqual(update["run_results"][0]["opencli_stage"]["status"], "ok")
        self.assertEqual(update["run_results"][0]["opencli_stage"]["imported_candidate_count"], 1)
        self.assertTrue(
            (repo_root / ".tmp" / "stock-watch-workflow" / "cases" / "chalco-a" / "results" / "company_state.opencli-bridge.result.json").exists()
        )
        self.assertTrue(
            (repo_root / ".tmp" / "stock-watch-workflow" / "cases" / "chalco-a" / "reports" / "company_state.opencli-bridge.report.md").exists()
        )

    def test_refresh_single_stock_merges_opencli_candidates_into_refresh_request(self) -> None:
        repo_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-opencli-refresh"
        repo_root.mkdir(parents=True, exist_ok=True)
        paths = workflow_paths(repo_root)
        stock = {
            "slug": "envicool-a",
            "name": "英维克",
            "ticker": "002837.SZ",
            "market": "A-share",
            "aliases": [],
            "peer_keywords": [],
            "driver_keywords": ["cooling"],
            "watch_items": ["data center cooling"],
            "sector": "Thermal management",
            "status": "active",
        }
        case_dir = repo_root / ".tmp" / "stock-watch-workflow" / "cases" / "envicool-a"
        (case_dir / "results").mkdir(parents=True, exist_ok=True)
        for result_name in ("company_state", "earnings_freshness", "driver_state"):
            previous_result_path = case_dir / "results" / f"{result_name}.result.json"
            previous_result_path.write_text(
                json.dumps(fake_stock_result({"topic": "previous", "analysis_time": "2026-04-02T08:00:00+00:00"})),
                encoding="utf-8",
            )

        captured_refresh_requests: list[dict[str, object]] = []

        def fake_merge_refresh(existing_result: dict[str, object], refresh_payload: dict[str, object]) -> dict[str, object]:
            captured_refresh_requests.append(refresh_payload)
            return fake_stock_result(refresh_payload, core_verdict="Refresh result ready.")

        with (
            patch(
                "stock_watch_workflow.resolve_opencli_payload",
                return_value=([{"url": "https://research.example.com/china-aluminum-note"}], "result_path", "C:\\path\\to\\opencli-result.json", {"status": "ok"}),
            ) as resolve_capture,
            patch("stock_watch_workflow.prepare_opencli_bridge", return_value=fake_opencli_bridge_result()) as prepare_bridge,
            patch("stock_watch_workflow.merge_refresh", side_effect=fake_merge_refresh),
            patch("stock_watch_workflow.run_news_index", side_effect=AssertionError("run_news_index should not be used in refresh mode")),
        ):
            update = refresh_single_stock(
                repo_root,
                stock,
                paths=paths,
                config={
                    "use_opencli": True,
                    "opencli": {
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\opencli-result.json",
                    },
                    "prefer_news_refresh": True,
                },
                execution_mode_requested="auto",
                prepare_only=False,
            )

        self.assertEqual(resolve_capture.call_count, 1)
        self.assertEqual(prepare_bridge.call_count, 1)
        self.assertEqual(len(captured_refresh_requests), 3)
        self.assertTrue(all(any(item.get("origin") == "opencli" for item in request.get("candidates", [])) for request in captured_refresh_requests))
        company_opencli = next(item for item in captured_refresh_requests[0]["candidates"] if item.get("origin") == "opencli")
        earnings_opencli = next(item for item in captured_refresh_requests[1]["candidates"] if item.get("origin") == "opencli")
        driver_opencli = next(item for item in captured_refresh_requests[2]["candidates"] if item.get("origin") == "opencli")
        self.assertEqual(company_opencli["claim_ids"], [])
        self.assertEqual(company_opencli["claim_states"], {})
        self.assertEqual(earnings_opencli["claim_ids"], ["latest-report-identified"])
        self.assertEqual(earnings_opencli["claim_states"], {"latest-report-identified": "support"})
        self.assertEqual(driver_opencli["claim_ids"], ["driver-state-known"])
        self.assertEqual(driver_opencli["claim_states"], {"driver-state-known": "support"})
        self.assertTrue(all(item["mode"] == "news_refresh" for item in update["run_results"]))

    def test_refresh_single_stock_continues_when_opencli_is_optional_and_fails(self) -> None:
        repo_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-opencli-fallback"
        repo_root.mkdir(parents=True, exist_ok=True)
        paths = workflow_paths(repo_root)
        stock = {
            "slug": "chalco-a",
            "name": "中国铝业",
            "ticker": "601600.SH",
            "market": "A-share",
            "aliases": [],
            "peer_keywords": [],
            "driver_keywords": ["aluminum"],
            "watch_items": ["LME aluminum"],
            "sector": "Metals",
            "status": "active",
        }
        captured_requests: list[dict[str, object]] = []

        def fake_run_news_index(payload: dict[str, object]) -> dict[str, object]:
            captured_requests.append(payload)
            return fake_stock_result(payload, core_verdict="Fallback result ready.")

        with (
            patch("stock_watch_workflow.resolve_opencli_payload", side_effect=ValueError("runner failed")),
            patch("stock_watch_workflow.prepare_opencli_bridge", side_effect=AssertionError("prepare_opencli_bridge should not run after capture failure")),
            patch("stock_watch_workflow.run_news_index", side_effect=fake_run_news_index),
        ):
            update = refresh_single_stock(
                repo_root,
                stock,
                paths=paths,
                config={
                    "use_opencli": True,
                    "opencli": {
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\missing.json",
                    },
                },
                execution_mode_requested="full",
                prepare_only=False,
            )

        self.assertEqual(len(captured_requests), 3)
        self.assertTrue(all(not any(item.get("origin") == "opencli" for item in request.get("candidates", [])) for request in captured_requests))
        self.assertTrue(all(item["status"] == "ok" for item in update["run_results"]))
        self.assertTrue(all(item["opencli_stage"]["status"] == "error" for item in update["run_results"]))

    def test_refresh_single_stock_marks_error_when_opencli_is_required_and_fails(self) -> None:
        repo_root = Path(__file__).resolve().parents[1] / ".tmp" / "test-stock-watch-opencli-required"
        repo_root.mkdir(parents=True, exist_ok=True)
        paths = workflow_paths(repo_root)
        stock = {
            "slug": "envicool-a",
            "name": "英维克",
            "ticker": "002837.SZ",
            "market": "A-share",
            "aliases": [],
            "peer_keywords": [],
            "driver_keywords": ["cooling"],
            "watch_items": ["data center cooling"],
            "sector": "Thermal management",
            "status": "active",
        }

        with (
            patch("stock_watch_workflow.resolve_opencli_payload", side_effect=ValueError("runner failed")),
            patch("stock_watch_workflow.prepare_opencli_bridge", side_effect=AssertionError("prepare_opencli_bridge should not run after capture failure")),
            patch("stock_watch_workflow.run_news_index", side_effect=AssertionError("run_news_index should not run when opencli is required")),
        ):
            update = refresh_single_stock(
                repo_root,
                stock,
                paths=paths,
                config={
                    "use_opencli": True,
                    "require_opencli": True,
                    "opencli": {
                        "site_profile": "broker-research-portal",
                        "result_path": "C:\\path\\to\\missing.json",
                    },
                },
                execution_mode_requested="full",
                prepare_only=False,
            )

        self.assertTrue(all(item["status"] == "error" for item in update["run_results"]))
        self.assertTrue(all(item["opencli_stage"]["status"] == "error" for item in update["run_results"]))
        self.assertTrue(all(item["error"] == "runner failed" for item in update["run_results"]))


if __name__ == "__main__":
    unittest.main()


