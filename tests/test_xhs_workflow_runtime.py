#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import types
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

    def test_run_xhs_workflow_writes_performance_review_when_metrics_are_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex earnings",
                "run_id": "20260502124500",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run"},
                "performance_metrics": {
                    "post_url": "https://www.xiaohongshu.com/explore/published",
                    "after_24h": {"likes": 120, "collects": 60, "comments": 12, "shares": 5},
                    "notes": ["collect rate is strong"],
                },
            }

            result = module_under_test.run_xhs_workflow(request)

            package_dir = pathlib.Path(result["package_dir"])
            self.assertEqual(result["performance_review"]["status"], "recorded")
            self.assertTrue((package_dir / "performance_review.json").exists())
            self.assertTrue((package_dir / "review.md").exists())
            review = json.loads((package_dir / "performance_review.json").read_text(encoding="utf-8"))
            self.assertEqual(review["metrics"]["post_url"], "https://www.xiaohongshu.com/explore/published")
            self.assertGreater(review["scores"]["save_intent_score"], 0)

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

    def test_build_collector_plan_creates_xiaohongshu_skills_search_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = pathlib.Path(temp_dir) / "xiaohongshu-skills"
            skills_dir.mkdir()
            request = {
                "topic": "AI capex",
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "keyword": "AI capex",
                    "sort_by": "最多点赞",
                    "note_type": "图文",
                    "limit": 20,
                },
            }

            plan = module_under_test.build_collector_plan(request)

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["source"], "xiaohongshu-skills.search-feeds")
        self.assertEqual(plan["cwd"], str(skills_dir.resolve()))
        self.assertEqual(plan["command"][:3], ["python", "scripts/cli.py", "search-feeds"])
        self.assertIn("--keyword", plan["command"])
        self.assertIn("AI capex", plan["command"])
        self.assertIn("--sort-by", plan["command"])
        self.assertIn("最多点赞", plan["command"])
        self.assertIn("--note-type", plan["command"])
        self.assertIn("图文", plan["command"])
        self.assertIn("--limit", plan["command"])
        self.assertIn("20", plan["command"])

    def test_build_publish_preview_plan_uses_fill_publish_and_blocks_click_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = pathlib.Path(temp_dir) / "package"
            package_dir.mkdir()
            skills_dir = pathlib.Path(temp_dir) / "xiaohongshu-skills"
            skills_dir.mkdir()
            images_dir = package_dir / "images"
            images_dir.mkdir()
            image_path = images_dir / "card-01.png"
            image_path.write_bytes(b"fake")
            card_plan = {"topic": "AI capex"}
            request = {
                "publish": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "mode": "preview",
                }
            }

            plan = module_under_test.build_publish_preview_plan(request, package_dir, card_plan)

        self.assertEqual(plan["status"], "ready_preview")
        self.assertEqual(plan["source"], "xiaohongshu-skills.fill-publish")
        self.assertEqual(plan["cwd"], str(skills_dir.resolve()))
        self.assertEqual(plan["command"][:3], ["python", "scripts/cli.py", "fill-publish"])
        self.assertIn("--title-file", plan["command"])
        self.assertIn("--content-file", plan["command"])
        self.assertIn("--images", plan["command"])
        self.assertIn(str(image_path), plan["command"])
        self.assertFalse(plan["click_publish"])

    def test_build_publish_preview_plan_reports_missing_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = pathlib.Path(temp_dir) / "package"
            package_dir.mkdir()
            plan = module_under_test.build_publish_preview_plan(
                {"publish": {"type": "xiaohongshu-skills", "skills_dir": temp_dir}},
                package_dir,
                {"topic": "AI capex"},
            )

        self.assertEqual(plan["status"], "images_missing")
        self.assertEqual(plan["command"], [])

    def test_build_performance_collection_plan_creates_feed_detail_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = pathlib.Path(temp_dir) / "xiaohongshu-skills"
            skills_dir.mkdir()
            request = {
                "performance_collection": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "feed_id": "abc",
                    "xsec_token": "token",
                }
            }

            plan = module_under_test.build_performance_collection_plan(request)

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["source"], "xiaohongshu-skills.get-feed-detail")
        self.assertEqual(plan["cwd"], str(skills_dir.resolve()))
        self.assertEqual(plan["command"][:3], ["python", "scripts/cli.py", "get-feed-detail"])
        self.assertIn("--feed-id", plan["command"])
        self.assertIn("abc", plan["command"])
        self.assertIn("--xsec-token", plan["command"])
        self.assertIn("token", plan["command"])

    def test_load_performance_metrics_accepts_detail_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_path = pathlib.Path(temp_dir) / "detail.json"
            metrics_path.write_text(
                json.dumps(
                    {
                        "note": {"url": "https://www.xiaohongshu.com/explore/abc"},
                        "interactions": {"liked_count": 120, "collected_count": 60, "comment_count": 12},
                    }
                ),
                encoding="utf-8",
            )

            metrics = module_under_test.load_performance_metrics({"performance_file": str(metrics_path)})

        self.assertEqual(metrics["post_url"], "https://www.xiaohongshu.com/explore/abc")
        self.assertEqual(metrics["after_24h"]["likes"], 120)
        self.assertEqual(metrics["after_24h"]["collects"], 60)
        self.assertEqual(metrics["after_24h"]["comments"], 12)

    def test_run_collector_plan_writes_stdout_json_for_benchmark_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = pathlib.Path(temp_dir) / "benchmarks.json"
            plan = {
                "status": "ready",
                "source": "xiaohongshu-skills.search-feeds",
                "cwd": temp_dir,
                "command": ["python", "scripts/cli.py", "search-feeds", "--keyword", "AI capex"],
            }

            def fake_runner(command, cwd, timeout, capture_output, text, check):
                self.assertEqual(command, plan["command"])
                self.assertEqual(cwd, temp_dir)
                self.assertEqual(timeout, 120)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                self.assertFalse(check)
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"feeds": [{"title": "3 signals", "like_count": 10}]}),
                    stderr="",
                )

            result = module_under_test.run_collector_plan(plan, output_path, runner=fake_runner, timeout_seconds=120)

            self.assertEqual(result["status"], "collected")
            self.assertEqual(result["source"], "xiaohongshu-skills.search-feeds")
            self.assertEqual(result["count"], 1)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["feeds"][0]["title"], "3 signals")

    def test_run_xhs_workflow_auto_runs_collector_when_explicitly_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = pathlib.Path(temp_dir) / "xiaohongshu-skills"
            skills_dir.mkdir()
            request = {
                "topic": "AI capex",
                "run_id": "20260502130000",
                "output_dir": temp_dir,
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "keyword": "AI capex",
                    "auto_run": True,
                },
                "image_generation": {"mode": "dry_run"},
            }

            def fake_runner(command, cwd, timeout, capture_output, text, check):
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"feeds": [{"title": "3 signals", "like_count": 10}]}),
                    stderr="",
                )

            result = module_under_test.run_xhs_workflow(request, collector_runner=fake_runner)

            package_dir = pathlib.Path(result["package_dir"])

            self.assertEqual(result["collector_run"]["status"], "collected")
            self.assertEqual(result["benchmark_count"], 1)
            self.assertTrue((package_dir / "collector_result.json").exists())

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

    def test_build_multipart_form_data_supports_openai_image_edit_reference_images(self) -> None:
        body, content_type = module_under_test.build_multipart_form_data(
            fields={"model": "gpt-image-2", "prompt": "Create an XHS card"},
            files=[
                {
                    "field": "image[]",
                    "filename": "product-shot.png",
                    "content_type": "image/png",
                    "content": b"fake-png",
                }
            ],
            boundary="TESTBOUNDARY",
        )

        self.assertEqual(content_type, "multipart/form-data; boundary=TESTBOUNDARY")
        self.assertIn(b'name="model"', body)
        self.assertIn(b"gpt-image-2", body)
        self.assertIn(b'name="image[]"', body)
        self.assertIn(b'filename="product-shot.png"', body)
        self.assertTrue(body.endswith(b"--TESTBOUNDARY--\r\n"))

    def test_maybe_generate_images_routes_reference_images_to_edit_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            generation = {
                "mode": "openai",
                "prompts": [
                    {
                        "card_index": 1,
                        "prompt": "Create card",
                        "reference_images": [{"path": "D:/source/product.png", "role": "source_material"}],
                    }
                ],
            }

            with patch.object(
                module_under_test,
                "generate_openai_image_edit",
                return_value={"status": "edited", "path": "card-01.png"},
            ) as edit_mock, patch.object(module_under_test, "generate_openai_image") as generate_mock:
                result = module_under_test.maybe_generate_images(pathlib.Path(temp_dir), generation, {"mode": "openai"})

        self.assertEqual(result["results"][0]["status"], "edited")
        self.assertEqual(result["results"][0]["route"], "openai_images_edits")
        edit_mock.assert_called_once()
        generate_mock.assert_not_called()

    def test_maybe_generate_images_routes_text_only_cards_to_generation_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            generation = {
                "mode": "openai",
                "prompts": [
                    {
                        "card_index": 1,
                        "prompt": "Create card",
                        "reference_images": [],
                    }
                ],
            }

            with patch.object(
                module_under_test,
                "generate_openai_image",
                return_value={"status": "generated", "path": "card-01.png"},
            ) as generate_mock, patch.object(module_under_test, "generate_openai_image_edit") as edit_mock:
                result = module_under_test.maybe_generate_images(pathlib.Path(temp_dir), generation, {"mode": "openai"})

        self.assertEqual(result["results"][0]["status"], "generated")
        self.assertEqual(result["results"][0]["route"], "openai_images_generations")
        generate_mock.assert_called_once()
        edit_mock.assert_not_called()

    def test_build_readiness_report_blocks_openai_without_api_key_and_missing_reference_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_image = pathlib.Path(temp_dir) / "missing.png"
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmark_file": str(pathlib.Path(temp_dir) / "missing-benchmarks.json"),
                "image_generation": {
                    "mode": "openai",
                    "reference_images": [str(missing_image)],
                },
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["benchmark_file"]["passed"])
        self.assertFalse(report["checks"]["openai_api_key"]["passed"])
        self.assertFalse(report["checks"]["reference_images"]["passed"])
        self.assertGreaterEqual(len(report["blockers"]), 3)

    def test_build_readiness_report_passes_for_dry_run_with_inline_benchmarks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run"},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["checks"]["benchmark_input"]["passed"])
        self.assertTrue(report["checks"]["openai_api_key"]["passed"])

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

    def test_xhs_workflow_cli_doctor_writes_readiness_without_generating_package(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_doctor_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            output_path = temp_path / "doctor.json"
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
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
                ["xhs_workflow.py", str(input_path), "--doctor", "--output", str(output_path), "--quiet"],
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

            self.assertEqual(exit_context.exception.code, 0)
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["status"], "ready")
            self.assertFalse((temp_path / "out").exists())

    def test_xhs_workflow_cli_run_collector_flag_sets_explicit_auto_run(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_collector_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
                        "output_dir": str(temp_path / "out"),
                        "collector": {"type": "xiaohongshu-skills", "skills_dir": str(temp_path)},
                        "image_generation": {"mode": "dry_run"},
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["xhs_workflow.py", str(input_path), "--run-collector", "--quiet"],
            ), patch.object(
                cli_module,
                "run_xhs_workflow",
                return_value={"status": "ready_for_review"},
            ) as run_mock:
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = run_mock.call_args.args[0]
        self.assertTrue(payload["collector"]["auto_run"])

    def test_xhs_workflow_cli_image_flags_override_generation_config(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_image_flags_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            reference_path = temp_path / "reference.png"
            reference_path.write_bytes(b"fake")
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
                        "output_dir": str(temp_path / "out"),
                        "benchmarks": [{"title": "3 signals", "likes": 10}],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "xhs_workflow.py",
                    str(input_path),
                    "--image-mode",
                    "openai",
                    "--image-model",
                    "gpt-image-2",
                    "--image-size",
                    "1024x1536",
                    "--reference-image",
                    str(reference_path),
                    "--quiet",
                ],
            ), patch.object(
                cli_module,
                "run_xhs_workflow",
                return_value={"status": "ready_for_review"},
            ) as run_mock:
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = run_mock.call_args.args[0]
        image_config = payload["image_generation"]
        self.assertEqual(image_config["mode"], "openai")
        self.assertEqual(image_config["model"], "gpt-image-2")
        self.assertEqual(image_config["size"], "1024x1536")
        self.assertEqual(image_config["reference_images"][0], str(reference_path))

    def test_xhs_workflow_cli_performance_file_override(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_performance_file_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            performance_path = temp_path / "detail.json"
            input_path.write_text(
                json.dumps(
                    {
                        "topic": "AI capex",
                        "output_dir": str(temp_path / "out"),
                        "benchmarks": [{"title": "3 signals", "likes": 10}],
                    }
                ),
                encoding="utf-8",
            )
            performance_path.write_text(json.dumps({"interactions": {"liked_count": 1}}), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                ["xhs_workflow.py", str(input_path), "--performance-file", str(performance_path), "--quiet"],
            ), patch.object(
                cli_module,
                "run_xhs_workflow",
                return_value={"status": "ready_for_review"},
            ) as run_mock:
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = run_mock.call_args.args[0]
        self.assertEqual(payload["performance_file"], str(performance_path))


if __name__ == "__main__":
    unittest.main()
