#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "financial-analysis"
    / "skills"
    / "autoresearch-info-index"
    / "scripts"
    / "xhs_workflow_runtime.py"
)
SCRIPT_DIR = MODULE_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("xhs_workflow_runtime", MODULE_PATH)
module_under_test = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["xhs_workflow_runtime"] = module_under_test
SPEC.loader.exec_module(module_under_test)


class XhsWorkflowRuntimeTests(unittest.TestCase):
    def test_run_xhs_workflow_writes_reviewable_package_without_external_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex earnings",
                "run_id": "20260502120000",
                "local_material": {
                    "title": "Big Tech capex signal",
                    "summary": "Four large technology companies are raising AI infrastructure spend.",
                    "key_points": ["capex acceleration", "power demand", "investor scrutiny"],
                },
                "benchmarks": [
                    {
                        "url": "https://www.xiaohongshu.com/explore/demo",
                        "title": "3 signals to understand AI investment",
                        "likes": 1200,
                        "collects": 800,
                        "comments": 96,
                        "posted_at": "2026-05-01",
                    }
                ],
                "output_dir": temp_dir,
                "image_generation": {"mode": "dry_run"},
            }

            result = module_under_test.run_xhs_workflow(request)

            package_dir = pathlib.Path(result["package_dir"])
            self.assertEqual(result["status"], "ready_for_review")
            self.assertTrue((package_dir / "request.json").exists())
            self.assertTrue((package_dir / "benchmarks.json").exists())
            self.assertTrue((package_dir / "source_ledger.json").exists())
            self.assertTrue((package_dir / "deconstruction.md").exists())
            self.assertTrue((package_dir / "patterns.json").exists())
            self.assertTrue((package_dir / "content_brief.json").exists())
            self.assertTrue((package_dir / "card_plan.json").exists())
            self.assertTrue((package_dir / "draft.md").exists())
            self.assertTrue((package_dir / "caption.md").exists())
            self.assertTrue((package_dir / "hashtags.txt").exists())
            self.assertTrue((package_dir / "generation" / "prompts.json").exists())
            self.assertTrue((package_dir / "generation" / "model_run.json").exists())
            self.assertTrue((package_dir / "qc_report.md").exists())
            self.assertIn("manual approval required", result["publish_gate"]["status"])

    def test_rank_benchmarks_prioritizes_collects_and_comments(self) -> None:
        ranked = module_under_test.rank_benchmarks(
            [
                {"title": "Many likes", "likes": 1000, "collects": 10, "comments": 1},
                {"title": "High intent", "likes": 500, "collects": 500, "comments": 80},
            ]
        )

        self.assertEqual(ranked[0]["title"], "High intent")
        self.assertGreater(ranked[0]["engagement_score"], ranked[1]["engagement_score"])

    def test_load_benchmark_inputs_accepts_xiaohongshu_skills_search_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            benchmark_path = pathlib.Path(temp_dir) / "xhs-search.json"
            benchmark_path.write_text(
                json.dumps(
                    {
                        "feeds": [
                            {
                                "feed_id": "abc",
                                "xsec_token": "token",
                                "title": "3 signals from AI capex",
                                "note_url": "https://www.xiaohongshu.com/explore/abc",
                                "like_count": 200,
                                "collect_count": 150,
                                "comment_count": 20,
                                "nickname": "operator",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            benchmarks, import_meta = module_under_test.load_benchmark_inputs(
                {
                    "benchmark_file": str(benchmark_path),
                    "benchmark_source": "xiaohongshu-skills.search-feeds",
                }
            )

        self.assertEqual(import_meta["source"], "xiaohongshu-skills.search-feeds")
        self.assertEqual(import_meta["count"], 1)
        self.assertEqual(benchmarks[0]["title"], "3 signals from AI capex")
        self.assertEqual(benchmarks[0]["source"]["feed_id"], "abc")
        self.assertEqual(benchmarks[0]["source"]["xsec_token"], "token")

    def test_deconstructs_benchmarks_into_reusable_patterns_without_copying_source_text(self) -> None:
        benchmarks = module_under_test.rank_benchmarks(
            [{"title": "3 signals to understand AI investment", "likes": 100, "collects": 50, "comments": 20}]
        )

        patterns = module_under_test.deconstruct_benchmarks(benchmarks)

        self.assertEqual(patterns["count"], 1)
        self.assertEqual(patterns["patterns"][0]["title_formula"], "numbered_signal")
        self.assertIn("structure_only", patterns["reuse_policy"])
        self.assertIn("do not copy", patterns["patterns"][0]["reuse_boundary"])

    def test_build_card_plan_defaults_to_seven_xhs_cards(self) -> None:
        request = {
            "topic": "AI capex earnings",
            "local_material": {
                "title": "AI capex is becoming the earnings question",
                "summary": "Investors are checking whether large AI spend creates measurable returns.",
                "key_points": ["capex", "power", "ROI"],
            },
        }
        patterns = {"patterns": [{"title_formula": "numbered_signal", "card_sequence": ["cover", "why_now"]}]}

        card_plan = module_under_test.build_card_plan(request, patterns)

        self.assertEqual(len(card_plan["cards"]), 7)
        self.assertEqual(card_plan["cards"][0]["type"], "cover")
        self.assertEqual(card_plan["cards"][-1]["type"], "cta")

    def test_prepare_image_generation_prompts_uses_configurable_model_and_portrait_size(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
                {"index": 2, "type": "why_now", "title": "Why now", "message": "Earnings pressure."},
            ]
        }

        generation = module_under_test.prepare_image_generation(
            card_plan,
            {"mode": "dry_run", "model": "gpt-image-2", "size": "1024x1536"},
        )

        self.assertEqual(generation["mode"], "dry_run")
        self.assertEqual(generation["model"], "gpt-image-2")
        self.assertEqual(len(generation["prompts"]), 2)
        self.assertIn("vertical 9:16", generation["prompts"][0]["prompt"])

    def test_prepare_image_generation_keeps_reference_images_for_image_to_image(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            ]
        }

        generation = module_under_test.prepare_image_generation(
            card_plan,
            {
                "mode": "dry_run",
                "reference_images": [
                    "D:/source/product-shot.png",
                    {"path": "D:/source/chart.png", "role": "chart"},
                ],
            },
        )

        prompt = generation["prompts"][0]
        self.assertEqual(len(prompt["reference_images"]), 2)
        self.assertEqual(prompt["reference_images"][0]["role"], "source_material")
        self.assertEqual(prompt["reference_images"][1]["role"], "chart")
        self.assertIn("Use the provided reference images", prompt["prompt"])

    def test_qc_report_requires_manual_publish_approval_and_source_ledger(self) -> None:
        card_plan = {
            "cards": [
                {"index": index, "type": "content", "title": str(index), "message": str(index)}
                for index in range(1, 8)
            ]
        }
        generation = {
            "mode": "dry_run",
            "prompts": [{"card_index": index, "prompt": "vertical 9:16"} for index in range(1, 8)],
        }
        qc = module_under_test.build_qc_report(card_plan, generation, [{"url": "https://example.com"}])

        self.assertEqual(qc["status"], "needs_human_review")
        self.assertTrue(qc["checks"]["card_count"]["passed"])
        self.assertTrue(qc["checks"]["source_ledger"]["passed"])
        self.assertFalse(qc["checks"]["publish_approval"]["passed"])

    def test_xhs_workflow_cli_writes_output(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            output_path = temp_path / "result.json"
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
                        "run_id": "20260502121000",
                        "output_dir": str(temp_path / "out"),
                        "benchmarks": [{"title": "3 signals", "likes": 10}],
                        "image_generation": {"mode": "dry_run"},
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["xhs_workflow.py", str(input_path), "--output", str(output_path), "--quiet"],
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

            self.assertEqual(exit_context.exception.code, 0)
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["status"], "ready_for_review")

    def test_xhs_workflow_cli_accepts_benchmark_file_override(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_override_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            output_path = temp_path / "result.json"
            benchmark_path = temp_path / "benchmarks.json"
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
                        "run_id": "20260502124000",
                        "output_dir": str(temp_path / "out"),
                        "image_generation": {"mode": "dry_run"},
                    }
                ),
                encoding="utf-8",
            )
            benchmark_path.write_text(
                json.dumps({"items": [{"title": "3 signals", "likes": 10, "collects": 3}]}),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "xhs_workflow.py",
                    str(input_path),
                    "--benchmark-file",
                    str(benchmark_path),
                    "--benchmark-source",
                    "xiaohongshu-skills.search-feeds",
                    "--output",
                    str(output_path),
                    "--quiet",
                ],
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_context.exception.code, 0)
            self.assertEqual(result["benchmark_count"], 1)
            self.assertEqual(result["benchmark_import"]["source"], "xiaohongshu-skills.search-feeds")


if __name__ == "__main__":
    unittest.main()
