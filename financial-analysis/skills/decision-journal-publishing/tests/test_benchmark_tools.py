#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import unittest
from uuid import uuid4
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

WORKSPACE_TMP = Path(__file__).resolve().parents[4] / ".tmp" / "benchmark-tool-tests"
WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)

from benchmark_index_runtime import run_benchmark_index
from benchmark_library_refresh_runtime import run_benchmark_library_refresh
from benchmark_readiness_runtime import run_benchmark_readiness_audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def fresh_case_dir(prefix: str) -> Path:
    path = WORKSPACE_TMP / f"{prefix}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class BenchmarkToolTests(unittest.TestCase):
    def test_benchmark_index_prefers_reviewed_cases_and_latest_observation(self) -> None:
        base = fresh_case_dir("index")
        try:
            library_path = base / "benchmark-case-library.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "observation_log_path": "benchmark-case-observations.jsonl",
                    "default_request": {
                        "minimum_read_band": "5w+",
                        "include_curation_statuses": ["reviewed"],
                    },
                    "cases": [
                        {
                            "case_id": "reviewed-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Reviewed",
                            "title": "Reviewed case",
                            "url": "https://example.com/reviewed",
                            "canonical_url": "https://example.com/reviewed",
                            "read_signal": "3w+",
                            "machine_state": {
                                "current_read_signal": "50w+",
                                "current_read_count_estimate": 500000,
                                "current_observation_id": "obs-1",
                                "last_observation_at": "2026-03-24T12:00:00+00:00"
                            },
                            "account_positioning": "institutional finance readers",
                            "topic_type": "event explainer",
                            "hook_type": "policy consequence",
                            "affected_group": "research users",
                            "cta_type": "membership",
                            "paid_asset_linkage": "high",
                        },
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "toutiao",
                            "account_name": "Candidate",
                            "title": "Candidate case",
                            "url": "https://example.com/candidate",
                            "canonical_url": "https://example.com/candidate",
                            "read_signal": "100w+",
                        },
                    ],
                },
            )
            observations_path.write_text("", encoding="utf-8")
            result = run_benchmark_index(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                }
            )
            self.assertEqual(result["summary"]["considered_cases"], 1)
            self.assertEqual(result["summary"]["candidate_queue_excluded"], 1)
            self.assertEqual(result["cases"][0]["case_id"], "reviewed-case")
            self.assertEqual(result["cases"][0]["read_signal_source"], "machine_state.current_read_signal")
            self.assertEqual(result["cases"][0]["read_band"], "50w+")
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_benchmark_index_respects_human_locked_read_signal(self) -> None:
        base = fresh_case_dir("index-locked")
        try:
            library_path = base / "benchmark-case-library.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "default_request": {
                        "minimum_read_band": "5w+",
                        "include_curation_statuses": ["reviewed"],
                    },
                    "cases": [
                        {
                            "case_id": "locked-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Locked",
                            "title": "Locked case",
                            "url": "https://example.com/locked",
                            "canonical_url": "https://example.com/locked",
                            "read_signal": "5w+",
                            "machine_state": {
                                "current_read_signal": "100w+",
                                "current_read_count_estimate": 1000000,
                            },
                            "human_locks": {
                                "read_signal": True,
                            },
                            "account_positioning": "institutional finance readers",
                            "topic_type": "event explainer",
                            "hook_type": "policy consequence",
                            "affected_group": "research users",
                            "cta_type": "membership",
                            "paid_asset_linkage": "high",
                        }
                    ],
                },
            )
            result = run_benchmark_index(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                }
            )
            self.assertEqual(result["cases"][0]["read_signal"], "5w+")
            self.assertEqual(result["cases"][0]["read_signal_source"], "curated.read_signal")
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_updates_reviewed_machine_state_and_candidate_inbox(self) -> None:
        base = fresh_case_dir("refresh")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            (fixtures / "case.html").write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="Reviewed case refreshed" />
                    <meta property="article:published_time" content="2026-03-24T09:00:00+08:00" />
                  </head>
                  <body>阅读 12w+</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            (fixtures / "source.html").write_text(
                """
                <html><body><a href="candidate.html">Candidate discovery</a></body></html>
                """.strip(),
                encoding="utf-8",
            )
            (fixtures / "candidate.html").write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="Candidate discovery" />
                    <meta property="article:published_time" content="2026-03-24T10:00:00+08:00" />
                  </head>
                  <body>阅读 8w+</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            library_path = base / "benchmark-case-library.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "observation_log_path": "benchmark-case-observations.jsonl",
                    "default_request": {
                        "minimum_read_band": "5w+",
                        "include_curation_statuses": ["reviewed"],
                    },
                    "cases": [
                        {
                            "case_id": "reviewed-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Reviewed",
                            "title": "Reviewed case",
                            "url": "https://example.com/reviewed",
                            "canonical_url": "https://example.com/reviewed",
                            "fetch_url": str(fixtures / "case.html"),
                            "read_signal": "3w+",
                            "account_positioning": "institutional finance readers",
                            "topic_type": "event explainer",
                            "hook_type": "policy consequence",
                            "affected_group": "research users",
                            "cta_type": "membership",
                            "paid_asset_linkage": "high",
                        }
                    ],
                },
            )
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "fixture-source",
                            "platform": "wechat",
                            "account_name": "Fixture Source",
                            "seed_url": str(fixtures / "source.html"),
                            "include_url_patterns": [r"candidate\.html$"],
                            "candidate_defaults": {
                                "notes": "Fixture candidate"
                            }
                        }
                    ]
                },
            )
            original_library_text = library_path.read_text(encoding="utf-8")
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(base / "benchmark-case-candidates.json"),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                }
            )
            observations = read_jsonl(observations_path)
            self.assertGreaterEqual(len(observations), 1)
            self.assertEqual(result["summary"]["reviewed_cases_refreshed"], 1)
            self.assertGreaterEqual(result["summary"]["candidates_discovered"], 0)
            self.assertEqual(result["benchmark_index_result"]["summary"]["considered_cases"], 1)
            refreshed_library = json.loads(library_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed_library["cases"][0]["read_signal"], "3w+")
            self.assertEqual(refreshed_library["cases"][0]["machine_state"]["current_read_signal"], "12w+")
            candidate_library = json.loads((base / "benchmark-case-candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(len(candidate_library["cases"]), 1)
            self.assertNotEqual(library_path.read_text(encoding="utf-8"), original_library_text)
            self.assertTrue(Path(result["report_path"]).exists())
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_logs_skipped_cases_and_ignores_failed_candidate_fetches(self) -> None:
        base = fresh_case_dir("refresh-skip")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            (fixtures / "source.html").write_text(
                """
                <html><body><a href="missing-candidate.html">Broken candidate</a></body></html>
                """.strip(),
                encoding="utf-8",
            )
            library_path = base / "benchmark-case-library.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            candidate_library_path = base / "benchmark-case-candidates.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "reviewed-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Reviewed",
                            "title": "Reviewed case",
                            "url": "https://example.com/reviewed",
                            "canonical_url": "https://example.com/reviewed",
                            "read_signal": "3w+",
                        }
                    ],
                },
            )
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "fixture-source",
                            "platform": "wechat",
                            "account_name": "Fixture Source",
                            "seed_url": str(fixtures / "source.html"),
                            "include_url_patterns": [r"missing-candidate\.html$"],
                        }
                    ]
                },
            )
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "run_benchmark_index_after_refresh": False,
                }
            )
            observations = read_jsonl(observations_path)
            self.assertEqual(len(observations), 2)
            self.assertEqual(observations[0]["fetch_status"], "skipped")
            self.assertEqual(observations[1]["fetch_status"], "error")
            self.assertEqual(result["summary"]["reviewed_cases_refreshed"], 1)
            self.assertEqual(result["summary"]["candidates_discovered"], 0)
            self.assertEqual(result["summary"]["source_failures"], 0)
            self.assertEqual(result["source_runs"][0]["status"], "partial")
            refreshed_library = json.loads(library_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed_library["cases"][0]["machine_state"]["last_fetch_status"], "skipped")
            candidate_library = json.loads(candidate_library_path.read_text(encoding="utf-8"))
            self.assertEqual(candidate_library["cases"], [])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_readiness_audit_blocks_when_fetch_urls_and_seeds_are_missing(self) -> None:
        base = fresh_case_dir("readiness")
        try:
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "reviewed-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Reviewed",
                            "title": "Reviewed case",
                            "url": "https://example.com/reviewed",
                            "canonical_url": "https://example.com/reviewed",
                        }
                    ],
                },
            )
            write_json(candidate_library_path, {"library_name": "candidate-library", "version": "1", "cases": []})
            write_json(seeds_path, {"sources": []})
            result = run_benchmark_readiness_audit(
                {
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "refresh_existing_cases": True,
                    "discover_new_cases": True,
                    "allow_reference_url_fallback": False,
                }
            )
            self.assertEqual(result["readiness_level"], "blocked")
            self.assertFalse(result["ready_for_daily_refresh"])
            self.assertEqual(result["summary"]["reviewed_fetch_url_coverage_pct"], 0.0)
            self.assertEqual(result["summary"]["enabled_seed_sources"], 0)
            self.assertEqual(len(result["blockers"]), 2)
            self.assertIn("reviewed cases are missing fetch_url", " ".join(result["blockers"]))
            self.assertIn("Discovery is enabled", " ".join(result["blockers"]))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_discovers_candidates_from_sina_newmedia_json_seed(self) -> None:
        base = fresh_case_dir("refresh-json-seed")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            candidate_path = fixtures / "candidate.html"
            candidate_path.write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="金融八卦女：行业故事样例" />
                    <meta property="article:published_time" content="2026-03-24T10:00:00+08:00" />
                  </head>
                  <body>阅读 12w+</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            feed_path = fixtures / "sina-feed.json"
            write_json(
                feed_path,
                {
                    "status": 0,
                    "data": [
                        {
                            "title": "金融八卦女：行业故事样例",
                            "longTitle": "金融八卦女：行业故事样例",
                            "link": candidate_path.resolve().as_uri()
                        }
                    ],
                },
            )
            library_path = base / "benchmark-case-library.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            candidate_library_path = base / "benchmark-case-candidates.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [],
                },
            )
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "jinrongbaguanv-json-seed",
                            "platform": "toutiao",
                            "account_name": "金融八卦女",
                            "seed_mode": "sina_newmedia_json",
                            "seed_url": feed_path.resolve().as_uri(),
                            "feed_url": feed_path.resolve().as_uri(),
                            "include_url_patterns": [r"candidate\.html$"],
                            "candidate_defaults": {
                                "notes": "JSON seed fixture"
                            }
                        }
                    ]
                },
            )
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "run_benchmark_index_after_refresh": False,
                }
            )
            candidate_library = json.loads(candidate_library_path.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["source_failures"], 0)
            self.assertEqual(result["summary"]["candidates_discovered"], 1)
            self.assertEqual(result["source_runs"][0]["links_considered"], 1)
            self.assertEqual(candidate_library["cases"][0]["account_name"], "金融八卦女")
            self.assertEqual(candidate_library["cases"][0]["curation_status"], "candidate")
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_repairs_duplicate_and_weak_candidate_case_ids(self) -> None:
        base = fresh_case_dir("refresh-candidate-id-repair")
        try:
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [],
                },
            )
            write_json(
                candidate_library_path,
                {
                    "library_name": "candidate-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "示例账号",
                            "title": "第一篇文章",
                            "url": "https://example.com/candidate-a",
                            "canonical_url": "https://example.com/candidate-a",
                            "discovery_state": {"source_id": "sample-seed"},
                        },
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "示例账号",
                            "title": "第二篇文章",
                            "url": "https://example.com/candidate-b",
                            "canonical_url": "https://example.com/candidate-b",
                            "discovery_state": {"source_id": "sample-seed"},
                        },
                        {
                            "case_id": "5",
                            "curation_status": "candidate",
                            "platform": "toutiao",
                            "account_name": "另一个账号",
                            "title": "第三篇文章",
                            "url": "https://example.com/candidate-c",
                            "canonical_url": "https://example.com/candidate-c",
                            "discovery_state": {"source_id": "another-seed"},
                        },
                    ],
                },
            )
            write_json(seeds_path, {"sources": []})
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "refresh_existing_cases": False,
                    "discover_new_cases": False,
                    "run_benchmark_index_after_refresh": False,
                }
            )
            candidate_library = json.loads(candidate_library_path.read_text(encoding="utf-8"))
            case_ids = [case["case_id"] for case in candidate_library["cases"]]
            self.assertEqual(len(case_ids), 3)
            self.assertEqual(len(set(case_ids)), 3)
            self.assertTrue(all(case_id != "candidate-case" for case_id in case_ids))
            self.assertTrue(all(case_id != "5" for case_id in case_ids))
            self.assertEqual(result["summary"]["candidate_case_id_repairs"], 3)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_readiness_audit_warns_on_duplicate_candidate_case_ids(self) -> None:
        base = fresh_case_dir("readiness-duplicate-case-ids")
        try:
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [],
                },
            )
            write_json(
                candidate_library_path,
                {
                    "library_name": "candidate-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "示例账号",
                            "title": "第一篇文章",
                            "url": "https://example.com/candidate-a",
                            "canonical_url": "https://example.com/candidate-a",
                        },
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "示例账号",
                            "title": "第二篇文章",
                            "url": "https://example.com/candidate-b",
                            "canonical_url": "https://example.com/candidate-b",
                        },
                    ],
                },
            )
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "fixture-source",
                            "enabled": True,
                            "seed_url": "https://example.com/source",
                            "exclude_url_patterns": ["/video/"],
                        }
                    ]
                },
            )
            result = run_benchmark_readiness_audit(
                {
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "refresh_existing_cases": False,
                    "discover_new_cases": True,
                }
            )
            self.assertEqual(result["summary"]["duplicate_candidate_case_ids"], 1)
            self.assertIn("duplicate case IDs", " ".join(result["warnings"]))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_readiness_audit_distinguishes_allowed_proxy_cases_from_upgrade_gaps(self) -> None:
        base = fresh_case_dir("readiness-refresh-policy")
        try:
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "mirror-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Mirror",
                            "title": "Mirror article",
                            "url": "https://example.com/article",
                            "canonical_url": "https://example.com/article",
                            "fetch_url": "https://mirror.example.com/article",
                            "fetch_provenance": "mirror",
                        },
                        {
                            "case_id": "proxy-case",
                            "curation_status": "reviewed",
                            "platform": "toutiao",
                            "account_name": "Proxy",
                            "title": "Proxy benchmark",
                            "url": "https://example.com/case-study",
                            "canonical_url": "https://example.com/case-study",
                            "fetch_url": "https://commentary.example.com/case-study",
                            "fetch_provenance": "commentary_only",
                            "refresh_surface_policy": "proxy_allowed",
                            "benchmark_case_shape": "cited_case_proxy",
                        },
                    ],
                },
            )
            write_json(
                candidate_library_path,
                {
                    "library_name": "candidate-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "Candidate",
                            "title": "Candidate case",
                            "url": "https://example.com/candidate",
                            "canonical_url": "https://example.com/candidate",
                        }
                    ],
                },
            )
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "fixture-source",
                            "enabled": True,
                            "seed_url": "https://example.com/source",
                            "exclude_url_patterns": ["/video/"],
                        }
                    ]
                },
            )
            result = run_benchmark_readiness_audit(
                {
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "refresh_existing_cases": True,
                    "discover_new_cases": True,
                    "allow_reference_url_fallback": False,
                }
            )
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches"], 2)
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches_requiring_upgrade"], 1)
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches_allowed"], 1)
            self.assertEqual(result["reviewed_non_primary_fetches_requiring_upgrade"][0]["case_id"], "mirror-case")
            self.assertEqual(result["reviewed_non_primary_fetches_allowed"][0]["case_id"], "proxy-case")
            self.assertIn("without an allowed refresh policy", " ".join(result["warnings"]))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_readiness_audit_accepts_declared_proxy_and_mirror_refresh_policies(self) -> None:
        base = fresh_case_dir("readiness-allowed-proxy")
        try:
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "mirror-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Mirror",
                            "title": "Mirror benchmark",
                            "url": "https://example.com/reference-mirror",
                            "canonical_url": "https://example.com/reference-mirror",
                            "fetch_url": "https://example.com/fetch-mirror",
                            "fetch_provenance": "mirror",
                            "refresh_surface_policy": "mirror_allowed",
                            "benchmark_case_shape": "article",
                            "read_signal": "10w+",
                        },
                        {
                            "case_id": "proxy-case",
                            "curation_status": "reviewed",
                            "platform": "toutiao",
                            "account_name": "Proxy",
                            "title": "Proxy benchmark",
                            "url": "https://example.com/reference-proxy",
                            "canonical_url": "https://example.com/reference-proxy",
                            "fetch_url": "https://example.com/fetch-proxy",
                            "fetch_provenance": "commentary_only",
                            "refresh_surface_policy": "proxy_allowed",
                            "benchmark_case_shape": "account_model",
                            "read_signal": "5w+",
                        },
                    ],
                },
            )
            write_json(
                candidate_library_path,
                {
                    "library_name": "candidate-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "candidate-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "Candidate",
                            "title": "Candidate benchmark",
                            "url": "https://example.com/candidate",
                            "canonical_url": "https://example.com/candidate",
                        }
                    ],
                },
            )
            result = run_benchmark_readiness_audit(
                {
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "discover_new_cases": False,
                    "auto_add_new_cases": False,
                }
            )
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches"], 2)
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches_requiring_upgrade"], 0)
            self.assertEqual(result["summary"]["reviewed_non_primary_fetches_allowed"], 2)
            self.assertFalse(
                any("mirror or commentary surfaces" in warning for warning in result["warnings"])
            )
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_benchmark_index_surfaces_proxy_evidence_mode(self) -> None:
        base = fresh_case_dir("index-proxy-evidence")
        try:
            library_path = base / "benchmark-case-library.json"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "default_request": {
                        "minimum_read_band": "5w+",
                        "include_curation_statuses": ["reviewed"],
                    },
                    "cases": [
                        {
                            "case_id": "proxy-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Proxy",
                            "title": "Proxy benchmark",
                            "url": "https://example.com/reference-proxy",
                            "canonical_url": "https://example.com/reference-proxy",
                            "fetch_provenance": "commentary_only",
                            "refresh_surface_policy": "proxy_allowed",
                            "benchmark_case_shape": "account_model",
                            "read_signal": "5w+",
                            "account_positioning": "institutional finance readers",
                            "topic_type": "account analysis",
                            "hook_type": "business model",
                            "affected_group": "research users",
                            "cta_type": "membership",
                            "paid_asset_linkage": "high",
                        }
                    ],
                },
            )
            result = run_benchmark_index(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                }
            )
            case = result["cases"][0]
            self.assertEqual(case["benchmark_case_shape"], "account_model")
            self.assertEqual(case["refresh_surface_policy"], "proxy_allowed")
            self.assertEqual(case["fetch_provenance"], "commentary_only")
            self.assertIn("- Evidence surface: account_model via commentary_only", result["report_markdown"])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_does_not_treat_plain_business_metrics_as_read_signal(self) -> None:
        base = fresh_case_dir("refresh-read-signal-guard")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            candidate_path = fixtures / "candidate.html"
            candidate_path.write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="Wallstreet candidate" />
                    <meta property="article:published_time" content="2026-03-24T10:00:00+08:00" />
                  </head>
                  <body>2025年净利润38.22亿，同比增长47.74%</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            feed_path = fixtures / "sina-feed.json"
            write_json(
                feed_path,
                {
                    "status": 0,
                    "data": [
                        {
                            "title": "Wallstreet candidate",
                            "longTitle": "Wallstreet candidate",
                            "link": candidate_path.resolve().as_uri(),
                        }
                    ],
                },
            )
            library_path = base / "benchmark-case-library.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            candidate_library_path = base / "benchmark-case-candidates.json"
            write_json(library_path, {"library_name": "test-library", "version": "1", "cases": []})
            write_json(
                seeds_path,
                {
                    "sources": [
                        {
                            "source_id": "wallstreetcn-json-seed",
                            "platform": "wechat",
                            "account_name": "Wallstreet",
                            "seed_mode": "sina_newmedia_json",
                            "seed_url": feed_path.resolve().as_uri(),
                            "feed_url": feed_path.resolve().as_uri(),
                            "include_url_patterns": [r"candidate\.html$"],
                        }
                    ]
                },
            )
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "run_benchmark_index_after_refresh": False,
                }
            )
            candidate_library = json.loads(candidate_library_path.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["candidates_discovered"], 1)
            self.assertEqual(candidate_library["cases"][0]["read_signal"], "")
            self.assertEqual(candidate_library["cases"][0]["machine_state"]["current_read_signal"], "")
            self.assertFalse(candidate_library["cases"][0]["human_locks"]["read_signal"])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_clears_stale_candidate_read_signal_when_detection_is_blank(self) -> None:
        base = fresh_case_dir("refresh-clear-candidate-read-signal")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            candidate_path = fixtures / "candidate.html"
            candidate_path.write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="Existing candidate" />
                    <meta property="article:published_time" content="2026-03-24T10:00:00+08:00" />
                  </head>
                  <body>2025年净利润38.22亿，同比增长47.74%</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(library_path, {"library_name": "test-library", "version": "1", "cases": []})
            write_json(
                candidate_library_path,
                {
                    "library_name": "candidate-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "wallstreetcn-old-case",
                            "curation_status": "candidate",
                            "platform": "wechat",
                            "account_name": "Wallstreet",
                            "title": "Existing candidate",
                            "url": candidate_path.resolve().as_uri(),
                            "canonical_url": candidate_path.resolve().as_uri(),
                            "fetch_url": candidate_path.resolve().as_uri(),
                            "read_signal": "38.22亿",
                            "machine_state": {
                                "current_read_signal": "38.22亿",
                                "current_read_count_estimate": 3822000000,
                            },
                            "human_locks": {
                                "read_signal": False,
                            },
                        }
                    ],
                },
            )
            write_json(seeds_path, {"sources": []})
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "discover_new_cases": False,
                    "run_benchmark_index_after_refresh": False,
                }
            )
            candidate_library = json.loads(candidate_library_path.read_text(encoding="utf-8"))
            refreshed = candidate_library["cases"][0]
            self.assertEqual(result["summary"]["candidate_cases_refreshed"], 1)
            self.assertEqual(refreshed["read_signal"], "")
            self.assertEqual(refreshed["machine_state"]["current_read_signal"], "")
            self.assertIsNone(refreshed["machine_state"]["current_read_count_estimate"])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_keeps_reviewed_read_signal_when_detection_is_blank(self) -> None:
        base = fresh_case_dir("refresh-keep-reviewed-read-signal")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            reviewed_path = fixtures / "reviewed.html"
            reviewed_path.write_text(
                """
                <html>
                  <head>
                    <meta property="og:title" content="Reviewed candidate" />
                    <meta property="article:published_time" content="2026-03-24T10:00:00+08:00" />
                  </head>
                  <body>2025年净利润38.22亿，同比增长47.74%</body>
                </html>
                """.strip(),
                encoding="utf-8",
            )
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "reviewed-case",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Reviewed",
                            "title": "Reviewed candidate",
                            "url": reviewed_path.resolve().as_uri(),
                            "canonical_url": reviewed_path.resolve().as_uri(),
                            "fetch_url": reviewed_path.resolve().as_uri(),
                            "read_signal": "5w+",
                            "machine_state": {
                                "current_read_signal": "5w+",
                                "current_read_count_estimate": 50000,
                            },
                            "human_locks": {
                                "read_signal": True,
                            },
                        }
                    ],
                },
            )
            write_json(candidate_library_path, {"library_name": "candidate-library", "version": "1", "cases": []})
            write_json(seeds_path, {"sources": []})
            result = run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "discover_new_cases": False,
                    "run_benchmark_index_after_refresh": False,
                }
            )
            library = json.loads(library_path.read_text(encoding="utf-8"))
            refreshed = library["cases"][0]
            self.assertEqual(result["summary"]["reviewed_cases_refreshed"], 1)
            self.assertEqual(refreshed["read_signal"], "5w+")
            self.assertEqual(refreshed["machine_state"]["current_read_signal"], "5w+")
            self.assertEqual(refreshed["machine_state"]["current_read_count_estimate"], 50000)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_refresh_reviewed_case_can_use_sina_newmedia_feed_as_fetch_surface(self) -> None:
        base = fresh_case_dir("refresh-reviewed-sina-feed")
        try:
            fixtures = base / "fixtures"
            fixtures.mkdir(parents=True, exist_ok=True)
            feed_path = fixtures / "sina-feed.json"
            write_json(
                feed_path,
                {
                    "status": 0,
                    "data": [
                        {
                            "title": "Feed top line",
                            "longTitle": "Feed top line",
                            "ctime": "1774361256",
                            "link": "https://example.com/article",
                        }
                    ],
                },
            )
            library_path = base / "benchmark-case-library.json"
            candidate_library_path = base / "benchmark-case-candidates.json"
            seeds_path = base / "benchmark-refresh-seeds.json"
            observations_path = base / "benchmark-case-observations.jsonl"
            write_json(
                library_path,
                {
                    "library_name": "test-library",
                    "version": "1",
                    "cases": [
                        {
                            "case_id": "feed-reviewed",
                            "curation_status": "reviewed",
                            "platform": "wechat",
                            "account_name": "Feed account",
                            "title": "Curated title",
                            "url": "https://example.com/reference",
                            "canonical_url": "https://example.com/reference",
                            "fetch_url": feed_path.resolve().as_uri(),
                            "fetch_provenance": "first_party_feed",
                            "read_signal": "5w+",
                            "machine_state": {
                                "current_title": "Old title",
                                "current_published_at": "",
                            },
                        }
                    ],
                },
            )
            write_json(candidate_library_path, {"library_name": "candidate-library", "version": "1", "cases": []})
            write_json(seeds_path, {"sources": []})
            run_benchmark_library_refresh(
                {
                    "analysis_time": "2026-03-24T20:00:00+08:00",
                    "library_path": str(library_path),
                    "candidate_library_path": str(candidate_library_path),
                    "seeds_path": str(seeds_path),
                    "observations_path": str(observations_path),
                    "output_dir": str(base / "output"),
                    "discover_new_cases": False,
                    "run_benchmark_index_after_refresh": False,
                }
            )
            library = json.loads(library_path.read_text(encoding="utf-8"))
            refreshed = library["cases"][0]
            self.assertEqual(refreshed["machine_state"]["current_title"], "Feed top line")
            self.assertEqual(refreshed["machine_state"]["current_published_at"], "2026-03-24T14:07:36+00:00")
            self.assertEqual(refreshed["read_signal"], "5w+")
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
