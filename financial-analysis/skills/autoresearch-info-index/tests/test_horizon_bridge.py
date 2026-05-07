#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from horizon_bridge_runtime import prepare_horizon_bridge, run_horizon_bridge


class HorizonBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-horizon-bridge"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bridge_imports_horizon_items_as_shadow_news_index_candidates(self) -> None:
        result = run_horizon_bridge(
            {
                "topic": "AI infrastructure upstream discovery",
                "analysis_time": "2026-05-07T08:00:00+08:00",
                "questions": ["Which Horizon findings are usable as upstream discovery signals?"],
                "claims": [
                    {
                        "claim_id": "ai-power-demand",
                        "claim_text": "AI data center power equipment demand is rising.",
                    }
                ],
                "horizon": {
                    "result": {
                        "summary": "Horizon found two upstream candidates",
                        "filtered_items": [
                            {
                                "title": "AI data center power gear appears in Horizon radar",
                                "url": "https://example.com/horizon-ai-power",
                                "source": "TechWire",
                                "published_at": "2026-05-07T07:30:00+08:00",
                                "summary": "Horizon detected a fresh AI power-equipment item.",
                                "score": 0.91,
                                "rank": 1,
                                "tags": ["ai", "power"],
                                "platform": "rss",
                            }
                        ],
                        "enriched_items": [
                            {
                                "headline": "Optical module orders discussed by supply chain",
                                "link": "https://example.com/horizon-optical",
                                "source_name": "Supply Chain Blog",
                                "description": "Horizon enrichment kept the optical-module read-through.",
                                "heat": 72,
                                "published_time": "2026-05-07T07:40:00+08:00",
                                "metadata": {"cluster": "optical"},
                            }
                        ],
                    },
                },
            }
        )

        observations = result["retrieval_result"]["observations"]
        self.assertEqual(result["workflow_kind"], "horizon_bridge")
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 2)
        self.assertEqual(result["import_summary"]["payload_source"], "inline_result")
        self.assertEqual(result["import_summary"]["channel_counts"], {"shadow": 2})
        self.assertEqual(result["import_summary"]["access_mode_counts"], {"local_mcp": 2})

        first = next(item for item in observations if item["url"] == "https://example.com/horizon-ai-power")
        second = next(item for item in observations if item["url"] == "https://example.com/horizon-optical")

        self.assertEqual(first["origin"], "horizon")
        self.assertEqual(first["channel"], "shadow")
        self.assertEqual(first["access_mode"], "local_mcp")
        self.assertEqual(first["source_name"], "horizon:TechWire")
        self.assertEqual(first["raw_metadata"]["horizon"]["score"], 0.91)
        self.assertEqual(first["raw_metadata"]["horizon"]["rank"], 1)
        self.assertEqual(first["raw_metadata"]["horizon"]["tags"], ["ai", "power"])
        self.assertEqual(first["raw_metadata"]["horizon"]["score_policy"], "discovery_heat_only_not_claim_confirmation")
        self.assertEqual(first["claim_states"], {"ai-power-demand": "support"})

        self.assertEqual(second["raw_metadata"]["horizon"]["heat"], 72)
        self.assertEqual(second["raw_metadata"]["source_item"]["metadata"], {"cluster": "optical"})
        self.assertIn("Horizon enrichment", second["text_excerpt"])
        self.assertEqual(result["completion_check"]["status"], "ready")
        self.assertEqual(result["operator_summary"]["operator_status"], "ready")

    def test_prepare_bridge_loads_result_path_and_data_items(self) -> None:
        result_path = self.temp_dir / "horizon-output.json"
        result_path.write_text(
            """{
              "data": {
                "items": [
                  {
                    "title": "Commercial aerospace result from Horizon",
                    "url": "https://example.com/horizon-aerospace",
                    "source": "Aerospace Daily",
                    "published_at": "2026-05-07T07:20:00+08:00",
                    "summary": "Horizon saved artifact with nested data.items.",
                    "rank": 3
                  }
                ]
              }
            }""",
            encoding="utf-8",
        )

        result = prepare_horizon_bridge(
            {
                "topic": "Commercial aerospace upstream radar",
                "analysis_time": "2026-05-07T08:00:00+08:00",
                "horizon": {
                    "result_path": str(result_path),
                    "access_mode": "external_artifact",
                },
            }
        )

        candidates = result["retrieval_request"]["candidates"]
        self.assertEqual(result["import_summary"]["payload_source"], "result_path")
        self.assertEqual(result["import_summary"]["raw_item_count"], 1)
        self.assertEqual(result["import_summary"]["imported_candidate_count"], 1)
        self.assertEqual(candidates[0]["origin"], "horizon")
        self.assertEqual(candidates[0]["channel"], "shadow")
        self.assertEqual(candidates[0]["access_mode"], "external_artifact")
        self.assertIn(str(result_path.resolve()), result["report_markdown"])

    def test_command_mode_runs_local_horizon_export_command_and_imports_stdout_payload(self) -> None:
        script = (
            "import json; "
            "print(json.dumps({'items':[{'title':'Command mode Horizon item','url':'https://example.com/horizon-command',"
            "'source':'Horizon CLI','summary':'Command stdout supplied this Horizon payload.',"
            "'published_at':'2026-05-07T07:45:00+08:00','score':0.77}] }))"
        )

        result = run_horizon_bridge(
            {
                "topic": "Horizon command mode",
                "analysis_time": "2026-05-07T08:00:00+08:00",
                "horizon": {
                    "input_mode": "command",
                    "command": [sys.executable, "-c", script],
                    "timeout_seconds": 5,
                },
            }
        )

        self.assertEqual(result["runner_summary"]["mode"], "command")
        self.assertEqual(result["runner_summary"]["status"], "ok")
        self.assertEqual(result["runner_summary"]["payload_source"], "command_stdout")
        self.assertEqual(result["import_summary"]["payload_source"], "command_stdout")
        observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(observation["origin"], "horizon")
        self.assertEqual(observation["channel"], "shadow")
        self.assertEqual(observation["access_mode"], "local_mcp")
        self.assertEqual(observation["url"], "https://example.com/horizon-command")


if __name__ == "__main__":
    unittest.main()
