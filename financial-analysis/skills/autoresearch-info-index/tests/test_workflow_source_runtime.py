#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_source_runtime import (
    augment_news_payload_with_workflow_sources,
    build_agent_reach_augmentation_lines,
    build_opencli_augmentation_lines,
    build_source_stage_file_lines,
    resolve_indexed_source_kind,
    write_source_stage_outputs,
)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


class WorkflowSourceRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / ".tmp-workflow-source-runtime"
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_source_stage_outputs_persists_source_and_bridge_artifacts(self) -> None:
        source_stage = write_source_stage_outputs(
            self.temp_dir,
            source_kind="news_index_opencli",
            source_payload={"report_markdown": "# Source Report\n", "observations": []},
            agent_reach_stage={
                "bridge_result": {
                    "report_markdown": "# Agent Reach Report\n",
                    "channels_attempted": ["youtube"],
                }
            },
            opencli_stage={
                "bridge_result": {
                    "report_markdown": "# OpenCLI Report\n",
                    "retrieval_request": {"candidates": []},
                }
            },
            write_json=write_json,
        )

        self.assertEqual(source_stage["source_kind"], "news_index_opencli")
        self.assertTrue(Path(source_stage["result_path"]).exists())
        self.assertTrue(Path(source_stage["report_path"]).exists())
        self.assertTrue(Path(source_stage["agent_reach_stage"]["result_path"]).exists())
        self.assertTrue(Path(source_stage["agent_reach_stage"]["report_path"]).exists())
        self.assertTrue(Path(source_stage["opencli_stage"]["result_path"]).exists())
        self.assertTrue(Path(source_stage["opencli_stage"]["report_path"]).exists())

    def test_build_source_stage_file_lines_respects_report_toggles(self) -> None:
        source_stage = {
            "result_path": "source-result.json",
            "report_path": "source-report.md",
            "agent_reach_stage": {
                "result_path": "agent-reach-result.json",
                "report_path": "agent-reach-report.md",
            },
            "opencli_stage": {
                "result_path": "opencli-result.json",
                "report_path": "opencli-report.md",
            },
        }

        compact_lines = build_source_stage_file_lines(source_stage, include_source_report=False, include_bridge_reports=False)
        full_lines = build_source_stage_file_lines(source_stage, include_source_report=True, include_bridge_reports=True)

        self.assertEqual(
            compact_lines,
            [
                "- Source result: source-result.json",
                "- Agent Reach bridge result: agent-reach-result.json",
                "- OpenCLI bridge result: opencli-result.json",
            ],
        )
        self.assertEqual(
            full_lines,
            [
                "- Source result: source-result.json",
                "- Source report: source-report.md",
                "- Agent Reach bridge result: agent-reach-result.json",
                "- Agent Reach bridge report: agent-reach-report.md",
                "- OpenCLI bridge result: opencli-result.json",
                "- OpenCLI bridge report: opencli-report.md",
            ],
        )

    def test_build_agent_reach_augmentation_lines_includes_failures(self) -> None:
        lines = build_agent_reach_augmentation_lines(
            {
                "channels_attempted": ["youtube", "rss"],
                "channels_succeeded": ["youtube"],
                "channels_failed": [{"channel": "rss", "reason": "timeout"}],
                "imported_candidate_count": 2,
            }
        )

        self.assertIn("## Agent Reach Augmentation", lines)
        self.assertIn("- Channels attempted: youtube, rss", lines)
        self.assertIn("- Channel failure: rss | timeout", lines)
        self.assertEqual(build_agent_reach_augmentation_lines({}), [])

    def test_build_opencli_augmentation_lines_includes_error(self) -> None:
        lines = build_opencli_augmentation_lines(
            {
                "status": "error",
                "required": True,
                "payload_source": "result_path",
                "runner_status": "failed",
                "imported_candidate_count": 0,
                "error": "runner failed",
            }
        )

        self.assertIn("## OpenCLI Augmentation", lines)
        self.assertIn("- Status: error", lines)
        self.assertIn("- Required: yes", lines)
        self.assertIn("- Error: runner failed", lines)
        self.assertEqual(build_opencli_augmentation_lines({}), [])

    def test_augment_news_payload_with_workflow_sources_merges_agent_reach_and_opencli_candidates(self) -> None:
        request = {
            "payload": {
                "topic": "China aluminum broker note check",
                "candidates": [{"source_id": "base-1"}],
            },
            "agent_reach_enabled": True,
            "opencli_enabled": True,
            "opencli_required": False,
        }

        def fake_build_agent_payload(request: dict, *, default_use_case: str) -> dict:
            return {"use_case": default_use_case, "topic": request["payload"]["topic"]}

        def fake_build_opencli_payload(request: dict, *, default_use_case: str) -> dict:
            return {"use_case": default_use_case, "topic": request["payload"]["topic"]}

        def fake_merge(payload: dict, bridge_result: dict) -> dict:
            merged = dict(payload)
            merged["candidates"] = list(payload.get("candidates", [])) + list(bridge_result["retrieval_request"]["candidates"])
            return merged

        merged_payload, agent_reach_stage, opencli_stage = augment_news_payload_with_workflow_sources(
            request,
            default_agent_reach_use_case="article-workflow-agent-reach",
            default_opencli_use_case="article-workflow-opencli",
            run_agent_reach_bridge=lambda payload: {
                "request": payload,
                "retrieval_request": {"candidates": [{"source_id": "agent-1", "origin": "agent_reach"}]},
                "channels_attempted": ["youtube"],
                "channels_succeeded": ["youtube"],
                "channels_failed": [],
                "observations_imported": 1,
            },
            build_agent_reach_bridge_payload=fake_build_agent_payload,
            merge_news_payload_with_agent_reach_candidates=fake_merge,
            summarize_agent_reach_stage=lambda bridge_result: {
                "bridge_result": bridge_result,
                "channels_attempted": bridge_result["channels_attempted"],
                "channels_succeeded": bridge_result["channels_succeeded"],
                "channels_failed": bridge_result["channels_failed"],
                "imported_candidate_count": bridge_result["observations_imported"],
            },
            prepare_opencli_bridge=lambda payload: {
                "request": payload,
                "retrieval_request": {"candidates": [{"source_id": "opencli-1", "origin": "opencli"}]},
                "import_summary": {"payload_source": "result_path", "imported_candidate_count": 1},
                "runner_summary": {"status": "ok"},
            },
            build_opencli_bridge_payload=fake_build_opencli_payload,
            merge_news_payload_with_opencli_candidates=fake_merge,
            summarize_opencli_stage=lambda bridge_result, *, required, status="ok", error="": {
                "bridge_result": bridge_result,
                "required": required,
                "status": status,
                "error": error,
                "payload_source": bridge_result.get("import_summary", {}).get("payload_source", ""),
                "runner_status": bridge_result.get("runner_summary", {}).get("status", ""),
                "imported_candidate_count": bridge_result.get("import_summary", {}).get("imported_candidate_count", 0),
            },
        )

        self.assertEqual(
            [item["source_id"] for item in merged_payload["candidates"]],
            ["base-1", "agent-1", "opencli-1"],
        )
        self.assertEqual(agent_reach_stage["imported_candidate_count"], 1)
        self.assertEqual(opencli_stage["status"], "ok")
        self.assertEqual(opencli_stage["payload_source"], "result_path")

    def test_augment_news_payload_with_workflow_sources_handles_optional_opencli_failure(self) -> None:
        merged_payload, agent_reach_stage, opencli_stage = augment_news_payload_with_workflow_sources(
            {
                "payload": {"topic": "China aluminum broker note check"},
                "agent_reach_enabled": False,
                "opencli_enabled": True,
                "opencli_required": False,
            },
            default_agent_reach_use_case="unused-agent-reach",
            default_opencli_use_case="macro-note-workflow-opencli",
            run_agent_reach_bridge=lambda payload: payload,
            build_agent_reach_bridge_payload=lambda request, *, default_use_case: {},
            merge_news_payload_with_agent_reach_candidates=lambda payload, bridge_result: payload,
            summarize_agent_reach_stage=lambda bridge_result: bridge_result,
            prepare_opencli_bridge=lambda payload: (_ for _ in ()).throw(ValueError("runner failed")),
            build_opencli_bridge_payload=lambda request, *, default_use_case: {"use_case": default_use_case},
            merge_news_payload_with_opencli_candidates=lambda payload, bridge_result: payload,
            summarize_opencli_stage=lambda bridge_result, *, required, status="ok", error="": {
                "bridge_result": bridge_result,
                "required": required,
                "status": status,
                "error": error,
            },
        )

        self.assertEqual(merged_payload["topic"], "China aluminum broker note check")
        self.assertEqual(agent_reach_stage, {})
        self.assertEqual(opencli_stage["status"], "error")
        self.assertEqual(opencli_stage["error"], "runner failed")

    def test_augment_news_payload_with_workflow_sources_raises_when_opencli_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "runner failed"):
            augment_news_payload_with_workflow_sources(
                {
                    "payload": {"topic": "China aluminum broker note check"},
                    "agent_reach_enabled": False,
                    "opencli_enabled": True,
                    "opencli_required": True,
                },
                default_agent_reach_use_case="unused-agent-reach",
                default_opencli_use_case="macro-note-workflow-opencli",
                run_agent_reach_bridge=lambda payload: payload,
                build_agent_reach_bridge_payload=lambda request, *, default_use_case: {},
                merge_news_payload_with_agent_reach_candidates=lambda payload, bridge_result: payload,
                summarize_agent_reach_stage=lambda bridge_result: bridge_result,
                prepare_opencli_bridge=lambda payload: (_ for _ in ()).throw(ValueError("runner failed")),
                build_opencli_bridge_payload=lambda request, *, default_use_case: {"use_case": default_use_case},
                merge_news_payload_with_opencli_candidates=lambda payload, bridge_result: payload,
                summarize_opencli_stage=lambda bridge_result, *, required, status="ok", error="": {
                    "bridge_result": bridge_result,
                    "required": required,
                    "status": status,
                    "error": error,
                },
            )

    def test_resolve_indexed_source_kind_distinguishes_x_and_news(self) -> None:
        self.assertEqual(resolve_indexed_source_kind({"x_posts": [{"post_id": "1"}]}), "x_index")
        self.assertEqual(resolve_indexed_source_kind({"evidence_pack": {"root_posts": []}}), "x_index")
        self.assertEqual(resolve_indexed_source_kind({"observations": []}), "news_index")


if __name__ == "__main__":
    unittest.main()
