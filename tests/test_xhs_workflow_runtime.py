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


def make_xiaohongshu_skills_dir(root: pathlib.Path) -> pathlib.Path:
    skills_dir = root / "xiaohongshu-skills"
    scripts_dir = skills_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "cli.py").write_text("# fake xiaohongshu-skills cli\n", encoding="utf-8")
    return skills_dir


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
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
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
        self.assertNotIn("--limit", plan["command"])
        self.assertEqual(plan["requested_limit"], 20)

    def test_build_collector_plan_omits_filter_clicks_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
            request = {
                "topic": "AI capex",
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "keyword": "AI capex",
                    "limit": 20,
                },
            }

            plan = module_under_test.build_collector_plan(request)

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["command"], ["python", "scripts/cli.py", "search-feeds", "--keyword", "AI capex"])
        self.assertNotIn("--sort-by", plan["command"])
        self.assertNotIn("--note-type", plan["command"])
        self.assertEqual(plan["filter_mode"], "keyword_only")
        self.assertEqual(plan["requested_limit"], 20)

    def test_build_collector_plan_can_disable_requested_filter_clicks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
            request = {
                "topic": "AI capex",
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "keyword": "AI capex",
                    "sort_by": "最多点赞",
                    "note_type": "图文",
                    "apply_filters": False,
                },
            }

            plan = module_under_test.build_collector_plan(request)

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["command"], ["python", "scripts/cli.py", "search-feeds", "--keyword", "AI capex"])
        self.assertEqual(plan["filter_mode"], "disabled")

    def test_build_collector_plan_uses_env_skills_dir_when_request_omits_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
            request = {
                "topic": "AI capex",
                "collector": {
                    "type": "xiaohongshu-skills",
                    "keyword": "AI capex",
                },
            }

            plan = module_under_test.build_collector_plan(
                request,
                env={"XIAOHONGSHU_SKILLS_DIR": str(skills_dir)},
            )

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["cwd"], str(skills_dir.resolve()))
        self.assertEqual(plan["skills_dir_source"], "env:XIAOHONGSHU_SKILLS_DIR")

    def test_build_collector_plan_reports_missing_cli_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = pathlib.Path(temp_dir) / "xiaohongshu-skills"
            skills_dir.mkdir()
            request = {
                "topic": "AI capex",
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "keyword": "AI capex",
                },
            }

            plan = module_under_test.build_collector_plan(request)

        self.assertEqual(plan["status"], "missing_cli")
        self.assertEqual(plan["command"], [])
        self.assertIn("scripts", plan["message"])

    def test_build_publish_preview_plan_uses_fill_publish_and_blocks_click_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = pathlib.Path(temp_dir) / "package"
            package_dir.mkdir()
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
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
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
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

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                self.assertEqual(command, plan["command"])
                self.assertEqual(cwd, temp_dir)
                self.assertEqual(timeout, 120)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                self.assertFalse(check)
                self.assertEqual(encoding, "utf-8")
                self.assertEqual(errors, "replace")
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

    def test_run_collector_plan_blocks_when_bridge_preflight_is_not_connected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = pathlib.Path(temp_dir) / "benchmarks.json"
            plan = {
                "status": "ready",
                "source": "xiaohongshu-skills.search-feeds",
                "cwd": temp_dir,
                "command": ["python", "scripts/cli.py", "search-feeds", "--keyword", "AI capex"],
                "bridge_preflight_command": ["python", "-c", "print('bridge')"],
            }
            calls = []

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                calls.append(command)
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"server_running": True, "extension_connected": False}),
                    stderr="",
                )

            result = module_under_test.run_collector_plan(plan, output_path, runner=fake_runner, timeout_seconds=120)

        self.assertEqual(result["status"], "bridge_not_connected")
        self.assertEqual(calls, [plan["bridge_preflight_command"]])
        self.assertFalse(output_path.exists())

    def test_run_publish_preview_plan_executes_fill_publish_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = {
                "status": "ready_preview",
                "source": "xiaohongshu-skills.fill-publish",
                "cwd": temp_dir,
                "command": ["python", "scripts/cli.py", "fill-publish", "--title-file", "title.txt"],
                "click_publish": False,
            }

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                self.assertEqual(command, plan["command"])
                self.assertNotIn("click-publish", command)
                self.assertEqual(cwd, temp_dir)
                self.assertEqual(timeout, 90)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                self.assertFalse(check)
                self.assertEqual(encoding, "utf-8")
                self.assertEqual(errors, "replace")
                return types.SimpleNamespace(returncode=0, stdout='{"status":"filled"}', stderr="")

            result = module_under_test.run_publish_preview_plan(plan, runner=fake_runner, timeout_seconds=90)

        self.assertEqual(result["status"], "filled_preview")
        self.assertEqual(result["source"], "xiaohongshu-skills.fill-publish")
        self.assertFalse(result["click_publish"])

    def test_run_publish_preview_plan_blocks_when_bridge_preflight_is_not_connected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = {
                "status": "ready_preview",
                "source": "xiaohongshu-skills.fill-publish",
                "cwd": temp_dir,
                "command": ["python", "scripts/cli.py", "fill-publish", "--title-file", "title.txt"],
                "bridge_preflight_command": ["python", "-c", "print('bridge')"],
                "click_publish": False,
            }
            calls = []

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                calls.append(command)
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"server_running": True, "extension_connected": False}),
                    stderr="",
                )

            result = module_under_test.run_publish_preview_plan(plan, runner=fake_runner, timeout_seconds=90)

        self.assertEqual(result["status"], "bridge_not_connected")
        self.assertEqual(calls, [plan["bridge_preflight_command"]])
        self.assertFalse(result["click_publish"])

    def test_run_publish_preview_plan_refuses_click_publish_command(self) -> None:
        plan = {
            "status": "ready_preview",
            "source": "xiaohongshu-skills.fill-publish",
            "cwd": ".",
            "command": ["python", "scripts/cli.py", "click-publish"],
            "click_publish": False,
        }

        result = module_under_test.run_publish_preview_plan(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("click-publish", result["reason"])

    def test_run_xhs_workflow_auto_runs_collector_when_explicitly_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = make_xiaohongshu_skills_dir(pathlib.Path(temp_dir))
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

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                self.assertEqual(encoding, "utf-8")
                self.assertEqual(errors, "replace")
                if command == module_under_test.build_collector_plan(request)["bridge_preflight_command"]:
                    return types.SimpleNamespace(
                        returncode=0,
                        stdout=json.dumps({"server_running": True, "extension_connected": True}),
                        stderr="",
                    )
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

    def test_run_xhs_workflow_auto_runs_publish_preview_when_explicitly_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            skills_dir = make_xiaohongshu_skills_dir(temp_path)
            request = {
                "topic": "AI capex",
                "run_id": "20260502133000",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run"},
                "publish": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "mode": "preview",
                    "auto_run_preview": True,
                },
            }

            def fake_generate(package_dir, generation, config):
                image_path = package_dir / "images" / "card-01.png"
                image_path.write_bytes(b"fake")
                generation["results"] = [{"status": "generated", "path": str(image_path)}]
                return generation

            def fake_runner(command, cwd, timeout, capture_output, text, check, encoding, errors):
                self.assertEqual(cwd, str(skills_dir.resolve()))
                self.assertEqual(encoding, "utf-8")
                self.assertEqual(errors, "replace")
                if "-c" in command:
                    return types.SimpleNamespace(
                        returncode=0,
                        stdout=json.dumps({"server_running": True, "extension_connected": True}),
                        stderr="",
                    )
                self.assertIn("fill-publish", command)
                self.assertNotIn("click-publish", command)
                return types.SimpleNamespace(returncode=0, stdout='{"status":"filled"}', stderr="")

            with patch.object(module_under_test, "maybe_generate_images", side_effect=fake_generate):
                result = module_under_test.run_xhs_workflow(request, publish_preview_runner=fake_runner)

            package_dir = pathlib.Path(result["package_dir"])
            self.assertTrue((package_dir / "publish_preview_run.json").exists())

        self.assertEqual(result["publish_preview_run"]["status"], "filled_preview")
        self.assertFalse(result["publish_plan"]["click_publish"])

    def test_run_xhs_workflow_skips_publish_preview_when_text_qc_needs_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            skills_dir = make_xiaohongshu_skills_dir(temp_path)
            request = {
                "topic": "AI capex",
                "run_id": "20260505130000",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run", "text_strategy": "model_text_with_qc"},
                "publish": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "mode": "preview",
                    "auto_run_preview": True,
                },
            }
            preview_calls = []

            def fake_generate(package_dir, generation, config):
                results = []
                for prompt in generation["prompts"]:
                    card_index = int(prompt["card_index"])
                    image_path = package_dir / "images" / f"card-{card_index:02d}.png"
                    image_path.write_bytes(b"fake")
                    results.append(
                        {
                            "status": "generated",
                            "path": str(image_path),
                            "text_source": "model_text_with_qc",
                            "allowed_text": prompt["allowed_text"],
                        }
                    )
                generation["results"] = results
                return generation

            def fake_runner(*args, **kwargs):
                preview_calls.append((args, kwargs))
                return types.SimpleNamespace(returncode=0, stdout='{"status":"filled"}', stderr="")

            with patch.object(module_under_test, "maybe_generate_images", side_effect=fake_generate), patch.object(
                module_under_test,
                "is_tesseract_available",
                return_value=False,
            ):
                result = module_under_test.run_xhs_workflow(request, publish_preview_runner=fake_runner)

        self.assertEqual(result["qc_status"], "needs_manual_text_qc")
        self.assertEqual(result["publish_plan"]["status"], "blocked_qc")
        self.assertEqual(result["publish_plan"]["command"], [])
        self.assertEqual(result["publish_preview_run"]["status"], "skipped")
        self.assertEqual(result["publish_preview_run"]["reason"], "qc status is needs_manual_text_qc")
        self.assertEqual(preview_calls, [])

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

    def test_prepare_image_generation_prompts_request_textless_backgrounds(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            ]
        }

        generation = module_under_test.prepare_image_generation(card_plan, {"mode": "openai"})

        prompt = generation["prompts"][0]["prompt"]
        self.assertIn("background only", prompt)
        self.assertIn("Do not render any readable text", prompt)
        self.assertIn("no dates", prompt)
        self.assertNotIn("clear Chinese typography", prompt)
        self.assertEqual(generation["text_rendering"]["mode"], "local_overlay")
        self.assertEqual(generation["text_rendering"]["allowed_text"][0], ["AI capex", "Watch the ROI question."])

    def test_prepare_image_generation_model_text_with_qc_locks_prompt_to_allowed_text(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            ]
        }

        generation = module_under_test.prepare_image_generation(
            card_plan,
            {"mode": "openai", "text_strategy": "model_text_with_qc"},
        )

        prompt = generation["prompts"][0]["prompt"]
        prompt_meta = generation["prompts"][0]
        self.assertEqual(generation["text_rendering"]["mode"], "model_text_with_qc")
        self.assertTrue(generation["text_rendering"]["qc_required"])
        self.assertEqual(prompt_meta["allowed_text"], ["AI capex", "Watch the ROI question."])
        self.assertTrue(prompt_meta["qc_required"])
        self.assertIn("Only render the exact allowed text strings", prompt)
        self.assertIn("AI capex", prompt)
        self.assertIn("Watch the ROI question.", prompt)
        self.assertIn("Do not invent or add dates, years, times, numbers, company names, tickers, logos, watermarks", prompt)
        self.assertNotIn("background only", prompt)

    def test_prepare_image_generation_hybrid_overlay_keeps_local_fact_overlay(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            ]
        }

        generation = module_under_test.prepare_image_generation(
            card_plan,
            {"mode": "openai", "text_strategy": "hybrid_overlay"},
        )

        prompt = generation["prompts"][0]["prompt"]
        self.assertEqual(generation["text_rendering"]["mode"], "hybrid_overlay")
        self.assertFalse(generation["text_rendering"]["qc_required"])
        self.assertIn("layout-rich", prompt)
        self.assertIn("Do not render readable factual text", prompt)
        self.assertIn("local overlay", prompt)

    def test_run_xhs_workflow_records_model_text_policy_in_prompts_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex earnings",
                "run_id": "20260503120000",
                "output_dir": temp_dir,
                "local_material": {
                    "title": "Big Tech capex signal",
                    "summary": "Watch the ROI question.",
                    "key_points": ["capex acceleration", "power demand", "investor scrutiny"],
                },
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run", "text_strategy": "model_text_with_qc"},
            }

            result = module_under_test.run_xhs_workflow(request)

            package_dir = pathlib.Path(result["package_dir"])
            prompts_payload = json.loads((package_dir / "generation" / "prompts.json").read_text(encoding="utf-8"))

        self.assertEqual(prompts_payload["text_strategy"], "model_text_with_qc")
        self.assertTrue(prompts_payload["qc_required"])
        self.assertEqual(prompts_payload["allowed_text"][0], ["AI capex earnings", "Watch the ROI question."])
        self.assertIn("forbidden_text_policy", prompts_payload)

    def test_ocr_text_qc_rejects_unallowed_date_string(self) -> None:
        result = module_under_test.evaluate_ocr_text_against_allowed(
            "AI capex Watch the ROI question 2024-01",
            ["AI capex", "Watch the ROI question"],
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["violations"][0]["type"], "forbidden_pattern")
        self.assertIn("2024-01", result["violations"][0]["text"])

    def test_resolve_tesseract_command_uses_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tesseract_path = pathlib.Path(temp_dir) / "tesseract.exe"
            tesseract_path.write_bytes(b"fake")

            with patch.dict(module_under_test.os.environ, {"TESSERACT_CMD": str(tesseract_path)}):
                command = module_under_test.resolve_tesseract_command()

        self.assertEqual(command, str(tesseract_path))

    def test_resolve_tesseract_command_uses_d_tools_fallback_when_path_is_stale(self) -> None:
        fallback = pathlib.Path("D:/Tools/Tesseract-OCR/tesseract.exe")

        with patch.dict(module_under_test.os.environ, {}, clear=True), patch.object(
            module_under_test.shutil,
            "which",
            return_value=None,
        ), patch.object(
            module_under_test.Path,
            "exists",
            lambda path: pathlib.Path(path) == fallback,
        ):
            command = module_under_test.resolve_tesseract_command()

        self.assertEqual(pathlib.Path(command), fallback)

    def test_qc_report_marks_model_text_as_manual_text_qc_when_ocr_unavailable(self) -> None:
        card_plan = {
            "cards": [
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            ]
        }
        generation = {
            "mode": "openai",
            "prompts": [{"card_index": 1, "prompt": "model text", "allowed_text": ["AI capex", "Watch the ROI question."]}],
            "results": [
                {
                    "status": "generated",
                    "path": "card-01.png",
                    "card_index": 1,
                    "text_source": "model_text_with_qc",
                    "allowed_text": ["AI capex", "Watch the ROI question."],
                }
            ],
            "text_rendering": {
                "mode": "model_text_with_qc",
                "qc_required": True,
                "allowed_text": [["AI capex", "Watch the ROI question."]],
            },
        }

        with patch.object(module_under_test, "is_tesseract_available", return_value=False):
            qc = module_under_test.build_qc_report(card_plan, generation, [{"url": "https://example.com"}])

        self.assertEqual(qc["status"], "needs_manual_text_qc")
        self.assertFalse(qc["checks"]["text_qc"]["passed"])
        self.assertEqual(qc["text_qc"]["status"], "needs_manual_text_qc")

    def test_qc_report_blocks_model_text_when_ocr_finds_forbidden_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = pathlib.Path(temp_dir) / "card-01.png"
            image_path.write_bytes(b"fake")
            card_plan = {
                "cards": [
                    {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
                ]
            }
            generation = {
                "mode": "openai",
                "prompts": [{"card_index": 1, "prompt": "model text", "allowed_text": ["AI capex", "Watch the ROI question."]}],
                "results": [
                    {
                        "status": "generated",
                        "path": str(image_path),
                        "card_index": 1,
                        "text_source": "model_text_with_qc",
                        "allowed_text": ["AI capex", "Watch the ROI question."],
                    }
                ],
                "text_rendering": {
                    "mode": "model_text_with_qc",
                    "qc_required": True,
                    "allowed_text": [["AI capex", "Watch the ROI question."]],
                },
            }

            with patch.object(module_under_test, "is_tesseract_available", return_value=True), patch.object(
                module_under_test,
                "run_tesseract_ocr",
                return_value="AI capex Watch the ROI question 2024-01",
            ):
                qc = module_under_test.build_qc_report(card_plan, generation, [{"url": "https://example.com"}])

        self.assertEqual(qc["status"], "blocked_text_qc")
        self.assertFalse(qc["checks"]["text_qc"]["passed"])
        self.assertIn("2024-01", qc["text_qc"]["results"][0]["violations"][0]["text"])

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

    def test_render_local_card_overlay_writes_exact_text_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            background_path = temp_path / "background.png"
            output_path = temp_path / "card-01.png"
            module_under_test.create_placeholder_background(background_path, size=(320, 480))

            result = module_under_test.render_local_card_overlay(
                background_path,
                {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
                output_path,
                {"size": "320x480"},
            )

        self.assertEqual(result["status"], "rendered")
        self.assertEqual(result["text_source"], "local_overlay")
        self.assertEqual(result["allowed_text"], ["AI capex", "Watch the ROI question."])
        self.assertGreater(result["bytes"], 0)

    def test_build_openai_api_url_uses_configurable_base_url(self) -> None:
        self.assertEqual(
            module_under_test.build_openai_api_url(
                {"base_url": "https://proxy.example/v1"},
                "images/generations",
            ),
            "https://proxy.example/v1/images/generations",
        )
        self.assertEqual(
            module_under_test.build_openai_api_url(
                {"base_url": "https://proxy.example"},
                "images/edits",
            ),
            "https://proxy.example/v1/images/edits",
        )

    def test_build_openai_api_url_uses_openai_base_url_env(self) -> None:
        with patch.dict(module_under_test.os.environ, {"OPENAI_BASE_URL": "https://env-proxy.example/v1"}):
            url = module_under_test.build_openai_api_url({}, "images/generations")

        self.assertEqual(url, "https://env-proxy.example/v1/images/generations")

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
                side_effect=lambda prompt, references, config, output_path: (
                    module_under_test.create_placeholder_background(output_path),
                    {"status": "edited", "path": str(output_path)},
                )[1],
            ) as edit_mock, patch.object(module_under_test, "generate_openai_image") as generate_mock:
                result = module_under_test.maybe_generate_images(pathlib.Path(temp_dir), generation, {"mode": "openai"})
                background_exists = pathlib.Path(result["results"][0]["background_path"]).exists()
                card_exists = pathlib.Path(result["results"][0]["path"]).exists()

        self.assertEqual(result["results"][0]["status"], "rendered")
        self.assertEqual(result["results"][0]["route"], "openai_images_edits")
        self.assertEqual(result["results"][0]["text_source"], "local_overlay")
        self.assertTrue(background_exists)
        self.assertTrue(card_exists)
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
                side_effect=lambda prompt, config, output_path: (
                    module_under_test.create_placeholder_background(output_path),
                    {"status": "generated", "path": str(output_path)},
                )[1],
            ) as generate_mock, patch.object(module_under_test, "generate_openai_image_edit") as edit_mock:
                result = module_under_test.maybe_generate_images(pathlib.Path(temp_dir), generation, {"mode": "openai"})
                background_exists = pathlib.Path(result["results"][0]["background_path"]).exists()
                card_exists = pathlib.Path(result["results"][0]["path"]).exists()

        self.assertEqual(result["results"][0]["status"], "rendered")
        self.assertEqual(result["results"][0]["route"], "openai_images_generations")
        self.assertEqual(result["results"][0]["text_source"], "local_overlay")
        self.assertTrue(background_exists)
        self.assertTrue(card_exists)
        generate_mock.assert_called_once()
        edit_mock.assert_not_called()

    def test_maybe_generate_images_composes_provided_backgrounds_without_openai(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            background_path = temp_path / "manual-background.png"
            module_under_test.create_placeholder_background(background_path)
            generation = {
                "mode": "compose",
                "prompts": [
                    {
                        "card_index": 1,
                        "card_type": "cover",
                        "card_title": "AI capex",
                        "card_message": "Watch the ROI question.",
                        "prompt": "background only",
                        "reference_images": [],
                        "background_image": str(background_path),
                    }
                ],
            }

            with patch.object(module_under_test, "generate_openai_image") as generate_mock, patch.object(
                module_under_test,
                "generate_openai_image_edit",
            ) as edit_mock:
                result = module_under_test.maybe_generate_images(temp_path, generation, {"mode": "compose"})

        self.assertEqual(result["results"][0]["status"], "rendered")
        self.assertEqual(result["results"][0]["route"], "manual_background_compose")
        self.assertEqual(result["results"][0]["text_source"], "local_overlay")
        generate_mock.assert_not_called()
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

    def test_build_readiness_report_blocks_compose_without_background_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "compose"},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["background_images"]["passed"])
        self.assertIn("background_images", report["blockers"])

    def test_build_readiness_report_accepts_compose_with_local_background_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            background_paths = []
            for index in range(1, 8):
                background_path = pathlib.Path(temp_dir) / f"background-{index:02d}.png"
                module_under_test.create_placeholder_background(background_path)
                background_paths.append(str(background_path))
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "compose", "background_images": background_paths},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["checks"]["background_images"]["passed"])

    def test_build_readiness_report_blocks_compose_with_too_few_background_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            background_path = pathlib.Path(temp_dir) / "background.png"
            module_under_test.create_placeholder_background(background_path)
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "compose", "background_images": [str(background_path)]},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["background_images"]["passed"])

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

    def test_build_readiness_report_displays_ocr_text_qc_capability_without_blocking_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex",
                "output_dir": temp_dir,
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "image_generation": {"mode": "dry_run", "text_strategy": "model_text_with_qc"},
            }

            with patch.object(module_under_test, "is_tesseract_available", return_value=False):
                report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "ready")
        self.assertFalse(report["checks"]["ocr_available"]["passed"])
        self.assertEqual(report["checks"]["text_qc_executable"]["value"], "needs_manual_text_qc_without_ocr")
        self.assertIn("ocr_available", report["warnings"])

    def test_build_readiness_report_accepts_ready_collector_as_benchmark_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            skills_dir = make_xiaohongshu_skills_dir(temp_path)
            request = {
                "topic": "AI capex",
                "output_dir": str(temp_path / "out"),
                "collector": {
                    "type": "xiaohongshu-skills",
                    "skills_dir": str(skills_dir),
                    "auto_run": True,
                },
                "image_generation": {"mode": "dry_run"},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["checks"]["benchmark_input"]["passed"])
        self.assertTrue(report["checks"]["collector_plan"]["passed"])
        self.assertEqual(report["collector_plan"]["status"], "ready")

    def test_build_readiness_report_blocks_auto_collector_without_collector_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            request = {
                "topic": "AI capex",
                "output_dir": str(pathlib.Path(temp_dir) / "out"),
                "benchmarks": [{"title": "3 signals", "likes": 10}],
                "collector": {"auto_run": True},
                "image_generation": {"mode": "dry_run"},
            }

            report = module_under_test.build_readiness_report(request, env={})

        self.assertEqual(report["status"], "blocked")
        self.assertIn("collector_plan", report["blockers"])
        self.assertFalse(report["checks"]["collector_plan"]["passed"])
        self.assertEqual(report["collector_plan"]["status"], "not_configured")

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

    def test_xhs_workflow_cli_doctor_blocks_run_collector_without_collector_config(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_doctor_collector_under_test", cli_path)
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
                [
                    "xhs_workflow.py",
                    str(input_path),
                    "--run-collector",
                    "--doctor",
                    "--output",
                    str(output_path),
                    "--quiet",
                ],
            ):
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_context.exception.code, 1)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("collector_plan", result["blockers"])

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

    def test_xhs_workflow_cli_run_publish_preview_flag_sets_preview_only_auto_run(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_publish_preview_under_test", cli_path)
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
                        "benchmarks": [{"title": "3 signals", "likes": 10}],
                        "publish": {"type": "xiaohongshu-skills", "skills_dir": str(temp_path)},
                        "image_generation": {"mode": "dry_run"},
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["xhs_workflow.py", str(input_path), "--run-publish-preview", "--quiet"],
            ), patch.object(
                cli_module,
                "run_xhs_workflow",
                return_value={"status": "ready_for_review"},
            ) as run_mock:
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = run_mock.call_args.args[0]
        self.assertTrue(payload["publish"]["auto_run_preview"])
        self.assertFalse(payload["publish"].get("click_publish", False))

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

    def test_xhs_workflow_cli_background_image_sets_compose_mode(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_background_under_test", cli_path)
        cli_module = importlib.util.module_from_spec(cli_spec)
        assert cli_spec and cli_spec.loader
        cli_spec.loader.exec_module(cli_module)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            input_path = temp_path / "request.json"
            background_path = temp_path / "background.png"
            background_path.write_bytes(b"fake")
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
                ["xhs_workflow.py", str(input_path), "--background-image", str(background_path), "--quiet"],
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
        self.assertEqual(image_config["mode"], "compose")
        self.assertEqual(image_config["background_images"], [str(background_path)])

    def test_xhs_workflow_cli_text_strategy_flag_sets_generation_config(self) -> None:
        cli_path = SCRIPT_DIR / "xhs_workflow.py"
        cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_text_strategy_under_test", cli_path)
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
                        "benchmarks": [{"title": "3 signals", "likes": 10}],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                ["xhs_workflow.py", str(input_path), "--text-strategy", "model_text_with_qc", "--quiet"],
            ), patch.object(
                cli_module,
                "run_xhs_workflow",
                return_value={"status": "ready_for_review"},
            ) as run_mock:
                with self.assertRaises(SystemExit) as exit_context:
                    cli_module.main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = run_mock.call_args.args[0]
        self.assertEqual(payload["image_generation"]["text_strategy"], "model_text_with_qc")

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
