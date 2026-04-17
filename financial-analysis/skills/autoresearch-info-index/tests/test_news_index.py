#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from news_index_core import build_markdown_report, read_json, refresh_news_index, result_to_run_record, run_news_index
from evaluate_info_index import build_result
from x_index_runtime import (
    FetchArtifact,
    build_same_author_scan_queries,
    build_chain_commands,
    build_search_queries,
    build_window_capture_hints,
    extract_post_text,
    fetch_thread_posts,
    parse_request,
    prepare_session_context,
    run_x_index,
)


class NewsIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = Path(__file__).resolve().parents[1] / "examples"
        cls.request = read_json(cls.examples / "news-index-crisis-request.json")
        cls.refresh = read_json(cls.examples / "news-index-refresh-update.json")
        cls.realistic_request = read_json(cls.examples / "news-index-realistic-offline-request.json")
        cls.realistic_refresh = read_json(cls.examples / "news-index-realistic-offline-refresh.json")

    def test_crisis_request_builds_dual_track_result(self) -> None:
        result = run_news_index(self.request)
        self.assertEqual(result["retrieval_request"]["mode"], "crisis")
        self.assertIn("US and Iran are in active indirect contacts today.", result["verdict_output"]["confirmed"])
        self.assertIn("A US amphibious group could reach a relevant public watch position within roughly one to two days.", result["verdict_output"]["not_confirmed"])
        self.assertTrue(result["verdict_output"]["latest_signals"][0]["rank_score"] >= result["verdict_output"]["latest_signals"][-1]["rank_score"])
        self.assertIn("crisis_mode", result)

    def test_refresh_adds_new_evidence_without_dropping_prior_context(self) -> None:
        first = run_news_index(self.request)
        refreshed = refresh_news_index(first, self.refresh)
        latest_sources = [item["source_name"] for item in refreshed["verdict_output"]["latest_signals"]]
        self.assertIn("AP", latest_sources)
        self.assertGreaterEqual(len(refreshed["source_observations"]), len(first["source_observations"]))
        self.assertEqual(refreshed["refresh_context"]["mode"], "refresh")

    def test_bridge_run_record_includes_retrieval_quality(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        self.assertIn("retrieval_result", run_record)
        self.assertIn("retrieval_quality", run_record["retrieval_result"])
        self.assertTrue(run_record["hard_checks"]["key_claims_traceable"])

    def test_run_record_preserves_precise_source_timestamps(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        first_source = run_record["source_pack"]["sources"][0]
        self.assertIn("source_id", first_source)
        self.assertIn("T", first_source["published_at"])

    def test_phase1_evaluation_keeps_gap_visibility_and_true_timeliness(self) -> None:
        result = run_news_index(self.request)
        evaluated = build_result(result_to_run_record(result))
        self.assertGreater(evaluated["credibility_metrics"]["timeliness_score"], 80)
        blocked_sources = [item["source_name"] for item in evaluated["retrieval_observability"]["blocked_sources"]]
        self.assertIn("Axios", blocked_sources)
        self.assertIn("public_ais", evaluated["retrieval_observability"]["missing_expected_source_families"])

    def test_fallback_retrieval_quality_does_not_penalize_clean_no_blocked_case(self) -> None:
        result = run_news_index(self.request)
        run_record = result_to_run_record(result)
        fallback_record = deepcopy(run_record)
        fallback_record["retrieval_result"].pop("retrieval_quality", None)
        fallback_record["retrieval_result"]["retrieval_run_report"]["sources_blocked"] = []
        for observation in fallback_record["retrieval_result"]["observations"]:
            observation["access_mode"] = "public"
        evaluated = build_result(fallback_record)
        self.assertEqual(evaluated["retrieval_quality_metrics"]["blocked_source_handling_score"], 100)

    def test_markdown_mentions_last_public_indication_sections(self) -> None:
        result = run_news_index(self.request)
        report = build_markdown_report(result)
        self.assertIn("Latest Signals First", report)
        self.assertIn("Vessel Movement Table", report)
        self.assertIn("Escalation Scenarios", report)
        self.assertIn("Last Public Indication", report)

    def test_realistic_offline_fixture_keeps_source_mix_and_blocked_visibility(self) -> None:
        result = run_news_index(self.realistic_request)
        latest_urls = [item["url"] for item in result["verdict_output"]["latest_signals"]]
        blocked_names = [item["source_name"] for item in result["retrieval_run_report"]["sources_blocked"]]
        source_artifacts = result["verdict_output"]["source_artifacts"]
        self.assertTrue(any("reuters.com" in url for url in latest_urls))
        self.assertIn("Axios", blocked_names)
        self.assertIn(
            "US and Iran are still in active indirect contacts today.",
            result["verdict_output"]["confirmed"],
        )
        self.assertIn(
            "A finalized settlement or ceasefire has already been agreed.",
            result["verdict_output"]["not_confirmed"],
        )
        self.assertTrue(any(item.get("root_post_screenshot_path") for item in source_artifacts))
        self.assertTrue(any("marinetraffic.com" in item.get("url", "") for item in source_artifacts))

    def test_realistic_offline_refresh_adds_second_tracker_source(self) -> None:
        first = run_news_index(self.realistic_request)
        refreshed = refresh_news_index(first, self.realistic_refresh)
        latest_sources = [item["source_name"] for item in refreshed["verdict_output"]["latest_signals"]]
        self.assertIn("VesselFinder", latest_sources)
        self.assertGreaterEqual(len(refreshed["source_observations"]), len(first["source_observations"]))

    @patch("news_index_runtime.urllib.request.urlopen")
    def test_public_news_candidate_extracts_open_graph_image_artifact(self, mock_urlopen) -> None:
        class FakeResponse:
            def __init__(self, html: str, final_url: str) -> None:
                self._html = html.encode("utf-8")
                self._final_url = final_url

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self, limit: int = -1) -> bytes:
                return self._html if limit < 0 else self._html[:limit]

            def geturl(self) -> str:
                return self._final_url

        mock_urlopen.return_value = FakeResponse(
            """
                <html>
                  <head>
                    <title>Example funding story</title>
                    <meta property="og:image" content="/images/hero.png">
                    <meta property="og:image:alt" content="Hero chart from the funding story">
                  </head>
                  <body>
                    <p>Funding story paragraph used for the public excerpt.</p>
                  </body>
                </html>
            """,
            "https://example.com/story",
        )

        result = run_news_index(
            {
                "topic": "Funding story with image",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim_text": "The funding story is real and has a reusable hero image.",
                    }
                ],
                "candidates": [
                    {
                        "source_id": "news-1",
                        "source_name": "Example News",
                        "source_type": "major_news",
                        "published_at": "2026-03-24T11:30:00+00:00",
                        "observed_at": "2026-03-24T11:35:00+00:00",
                        "url": "https://example.com/story",
                        "summary": "Funding story summary from discovery.",
                        "claim_ids": ["claim-1"],
                        "claim_states": {"claim-1": "support"},
                    }
                ],
            }
        )

        first_observation = result["source_observations"][0]
        self.assertTrue(first_observation["artifact_manifest"])
        self.assertEqual(first_observation["artifact_manifest"][0]["role"], "post_media")
        self.assertEqual(first_observation["artifact_manifest"][0]["source_url"], "https://example.com/images/hero.png")
        self.assertIn("Hero chart", first_observation["media_summary"])
        self.assertTrue(result["verdict_output"]["source_artifacts"][0]["artifact_manifest"])

    def test_tier_two_sources_can_promote_to_core_without_changing_rank_ordering(self) -> None:
        request = {
            "topic": "Tier two promotion",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim_text": "Multiple public trackers and a wire confirm the same movement.",
                }
            ],
            "candidates": [
                {
                    "source_id": "wire-1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T10:30:00+00:00",
                    "observed_at": "2026-03-24T10:35:00+00:00",
                    "url": "https://example.com/reuters",
                    "text_excerpt": "Reuters confirms the movement.",
                    "claim_ids": ["claim-1"],
                    "claim_states": {"claim-1": "support"},
                },
                {
                    "source_id": "tracker-1",
                    "source_name": "MarineTraffic",
                    "source_type": "public_ship_tracker",
                    "published_at": "2026-03-24T11:45:00+00:00",
                    "observed_at": "2026-03-24T11:46:00+00:00",
                    "url": "https://example.com/tracker-1",
                    "text_excerpt": "Tracker one shows the same movement.",
                    "claim_ids": ["claim-1"],
                    "claim_states": {"claim-1": "support"},
                },
                {
                    "source_id": "tracker-2",
                    "source_name": "VesselFinder",
                    "source_type": "public_ship_tracker",
                    "published_at": "2026-03-24T11:40:00+00:00",
                    "observed_at": "2026-03-24T11:41:00+00:00",
                    "url": "https://example.com/tracker-2",
                    "text_excerpt": "Tracker two shows the same movement.",
                    "claim_ids": ["claim-1"],
                    "claim_states": {"claim-1": "support"},
                },
            ],
        }

        result = run_news_index(request)
        promoted_trackers = [
            item
            for item in result["source_observations"]
            if item["source_tier"] == 2 and item["channel"] == "core"
        ]
        self.assertGreaterEqual(len(promoted_trackers), 2)
        latest_signals = result["verdict_output"]["latest_signals"]
        self.assertTrue(
            all(
                latest_signals[index]["rank_score"] >= latest_signals[index + 1]["rank_score"]
                for index in range(len(latest_signals) - 1)
            )
        )

    def test_energy_war_preset_adds_watchlist_and_report_section(self) -> None:
        request = {
            "topic": "Hormuz oil shock nowcast",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "mode": "crisis",
            "preset": "energy-war",
            "claims": [
                {
                    "claim_id": "claim-energy",
                    "claim_text": "Hormuz stress is lifting oil and LNG risk.",
                }
            ],
            "candidates": [
                {
                    "source_id": "wire-1",
                    "source_name": "Reuters",
                    "source_type": "wire",
                    "published_at": "2026-03-24T11:45:00+00:00",
                    "observed_at": "2026-03-24T11:46:00+00:00",
                    "url": "https://example.com/reuters-energy",
                    "text_excerpt": "Hormuz stress is lifting Brent and LNG risk.",
                    "claim_ids": ["claim-energy"],
                    "claim_states": {"claim-energy": "support"},
                }
            ],
        }
        result = run_news_index(request)
        self.assertEqual(result["request"]["preset"], "energy-war")
        self.assertIn("Brent", result["request"]["benchmark_watchlist"])
        self.assertIn("energy_war_preset", result["verdict_output"])
        self.assertIn("benchmark_watchlist", result["retrieval_run_report"])
        self.assertIn("## Energy-War Preset", result["report_markdown"])

    def test_x_index_prefers_direct_post_text_and_keeps_thread_and_media_fields(self) -> None:
        request = {
            "topic": "US military airlift chatter",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "claims": [
                {
                    "claim_id": "claim-airlift",
                    "claim_text": "A significant movement from CONUS to the Middle East is underway.",
                }
            ],
            "seed_posts": [
                {
                    "post_url": "https://x.com/sentdefender/status/2036153038906196133",
                    "html": """
                        <html>
                          <head>
                            <meta property=\"og:title\" content=\"SentDefender on X\">
                            <meta property=\"og:description\" content=\"A significant movement is underway from US Army, Navy and Air Force bases in CONUS to the Middle East comprised of at least 35 C-17 flights since March 12th.\">
                            <meta property=\"og:image\" content=\"https://pbs.twimg.com/media/test-airlift.jpg\">
                          </head>
                          <body>
                            <time datetime=\"2026-03-24T09:30:00+00:00\"></time>
                          </body>
                        </html>
                    """,
                    "root_post_screenshot_path": "C:\\artifacts\\sentdefender-root.png",
                    "thread_posts": [
                        {
                            "post_url": "https://x.com/sentdefender/status/2036153038906196134",
                            "posted_at": "2026-03-24T09:35:00+00:00",
                            "post_text_raw": "Origins include Hunter Army Air Field and JB Lewis-McChord.",
                            "post_text_source": "dom",
                        }
                    ],
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/test-airlift.jpg",
                            "ocr_text_raw": "Origins: 12 Hunter Army Air Field, 7 JBLM. Destinations: 17 Ovda Air Base, 13 King Faisal Air Base.",
                        }
                    ],
                    "engagement": {"views": 1500000, "likes": 32000, "reposts": 11000, "replies": 4200},
                }
            ],
        }

        result = run_x_index(request)
        post = result["x_posts"][0]
        self.assertEqual(post["post_text_source"], "dom")
        self.assertIn("35 C-17 flights", post["post_text_raw"])
        self.assertIn("Hunter Army Air Field", post["post_summary"])
        self.assertIn("Ovda Air Base", post["media_summary"])
        self.assertEqual(post["root_post_screenshot_path"], "C:\\artifacts\\sentdefender-root.png")
        retrieval_observation = result["retrieval_result"]["observations"][0]
        self.assertEqual(retrieval_observation["post_text_raw"], post["post_text_raw"])
        self.assertIn("Source Artifacts", result["retrieval_result"]["report_markdown"])

    def test_x_index_uses_ocr_fallback_when_direct_text_is_unavailable(self) -> None:
        request = {
            "topic": "Fallback capture",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "seed_posts": [
                {
                    "post_url": "https://x.com/example/status/1",
                    "html": "<html><body></body></html>",
                    "visible_text": "",
                    "accessibility_text": "",
                    "ocr_root_text": "Fallback text copied from the screenshot says 36 flights.",
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/fallback.jpg",
                            "ocr_text_raw": "Chart says 48 flights.",
                        }
                    ],
                }
            ],
        }

        result = run_x_index(request)
        post = result["x_posts"][0]
        self.assertEqual(post["post_text_source"], "ocr_fallback")
        self.assertIn("Fallback text copied", post["post_text_raw"])
        self.assertIn("Conflict note", post["combined_summary"])

    def test_x_index_bridge_preserves_artifact_fields_in_run_record(self) -> None:
        request = {
            "topic": "Bridge preservation",
            "analysis_time": "2026-03-24T12:00:00+00:00",
            "seed_posts": [
                {
                    "post_url": "https://x.com/example/status/2",
                    "html": """
                        <html>
                          <head>
                            <meta property=\"og:title\" content=\"Example on X\">
                            <meta property=\"og:description\" content=\"Direct text from the main post.\">
                          </head>
                        </html>
                    """,
                    "root_post_screenshot_path": "C:\\artifacts\\example-root.png",
                    "media_items": [
                        {
                            "source_url": "https://pbs.twimg.com/media/example.jpg",
                            "ocr_text_raw": "Image text for downstream citation.",
                        }
                    ],
                }
            ],
        }

        result = run_x_index(request)
        run_record = result_to_run_record(result["retrieval_result"])
        first_source = run_record["source_pack"]["sources"][0]
        self.assertEqual(first_source["root_post_screenshot_path"], "C:\\artifacts\\example-root.png")
        self.assertTrue(first_source["artifact_manifest"])
        self.assertIn("Image text", first_source["media_summary"])

    def test_prepare_session_context_copies_cookie_file_into_output_dir(self) -> None:
        output_dir = self.examples / "tmp-cookie-session"
        cookie_source = self.examples / "tmp-source-cookies.json"
        cookie_source.write_text("[]", encoding="utf-8")
        try:
            request = parse_request(
                {
                    "topic": "Cookie bootstrap",
                    "analysis_time": "2026-03-24T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "browser_session": {
                        "strategy": "cookie_file",
                        "cookie_file": str(cookie_source),
                    },
                }
            )
            context = prepare_session_context(request)
            self.assertEqual(context["status"], "ready")
            self.assertTrue(context["active"])
            self.assertTrue(Path(context["cookie_file"]).exists())
            self.assertTrue(str(Path(context["cookie_file"]).parent).startswith(str(output_dir)))
        finally:
            if cookie_source.exists():
                cookie_source.unlink()
            if output_dir.exists():
                for item in output_dir.rglob("*"):
                    if item.is_file():
                        item.unlink()
                for item in sorted(output_dir.rglob("*"), reverse=True):
                    if item.is_dir():
                        item.rmdir()
                output_dir.rmdir()

    def test_build_chain_commands_prepends_cookie_import_when_requested(self) -> None:
        commands = build_chain_commands(
            "https://x.com/example/status/3",
            Path("C:\\artifacts\\cookie-root.png"),
            {
                "strategy": "cookie_file",
                "active": True,
                "cookie_file": "C:\\workspace\\.tmp\\cookies.json",
            },
        )
        self.assertEqual(commands[0], ["cookie-import", "C:\\workspace\\.tmp\\cookies.json"])
        self.assertEqual(commands[1], ["goto", "https://x.com/example/status/3"])

    def test_extract_post_text_prefers_accessibility_root_quote_for_reply_pages(self) -> None:
        text, source, confidence = extract_post_text(
            """
                <html>
                  <head>
                    <meta property="og:description" content="Long root-thread text that should not win for the reply page.">
                  </head>
                  <body>
                    <div data-testid="tweetText">Long root-thread text that should not win for the reply page.</div>
                  </body>
                </html>
            """,
            "Long root-thread text that should not win for the reply page.",
            'RootWebArea: X 上的 Jason Zhu：“@iBigQiang 收录了 https://t.co/example” / X',
            "",
        )
        self.assertEqual(text, "@iBigQiang 收录了 https://t.co/example")
        self.assertEqual(source, "accessibility_root")
        self.assertGreaterEqual(confidence, 0.9)

    def test_x_index_reports_session_bootstrap_and_browser_session_post_metadata(self) -> None:
        output_dir = self.examples / "tmp-x-session-report"
        cookie_source = self.examples / "tmp-report-cookies.json"
        cookie_source.write_text("[]", encoding="utf-8")
        try:
            result = run_x_index(
                {
                    "topic": "Session report",
                    "analysis_time": "2026-03-24T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "browser_session": {
                        "strategy": "cookie_file",
                        "cookie_file": str(cookie_source),
                    },
                    "seed_posts": [
                        {
                            "post_url": "https://x.com/example/status/9",
                            "html": """
                                <html>
                                  <head>
                                    <meta property=\"og:title\" content=\"Example on X\">
                                    <meta property=\"og:description\" content=\"Browser-backed post text.\">
                                  </head>
                                </html>
                            """,
                            "used_browser_session": True,
                            "session_source": "cookie_file",
                            "session_status": "ready",
                            "session_notes": ["imported cookies before fetch"],
                        }
                    ],
                }
            )
            self.assertEqual(result["session_bootstrap"]["strategy"], "cookie_file")
            self.assertEqual(result["session_bootstrap"]["status"], "ready")
            self.assertEqual(result["session_bootstrap"]["health"], "effective")
            self.assertEqual(result["x_posts"][0]["access_mode"], "browser_session")
            self.assertEqual(result["x_posts"][0]["session_source"], "cookie_file")
            self.assertEqual(result["x_posts"][0]["session_health"], "effective")
            self.assertIn("## Session Bootstrap", result["report_markdown"])
            self.assertIn("Session: cookie_file | ready", result["report_markdown"])
        finally:
            if cookie_source.exists():
                cookie_source.unlink()
            if output_dir.exists():
                for item in output_dir.rglob("*"):
                    if item.is_file():
                        item.unlink()
                for item in sorted(output_dir.rglob("*"), reverse=True):
                    if item.is_dir():
                        item.rmdir()
                output_dir.rmdir()

    @patch("x_index_runtime.probe_cdp_endpoint", return_value=(False, "connection refused"))
    def test_prepare_session_context_remote_debugging_marks_unavailable_and_prefers_new_window(
        self,
        _mock_probe,
    ) -> None:
        request = parse_request(
            {
                "topic": "Remote debugging bootstrap",
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "browser_session": {
                    "strategy": "remote_debugging",
                    "cdp_endpoint": "http://127.0.0.1:9222",
                    "required": True,
                },
            }
        )
        context = prepare_session_context(request)
        self.assertEqual(context["status"], "unavailable")
        self.assertFalse(context["active"])
        self.assertTrue(any("new Edge window" in note for note in context["notes"]))

    def test_build_window_capture_hints_outputs_direct_x_search_urls(self) -> None:
        request = parse_request(
            {
                "topic": "Morgan Stanley focus list screenshots",
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "keywords": ["Morgan Stanley"],
                "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                "entity_clues": ["601600.SS"],
                "account_allowlist": ["LinQingV"],
                "manual_urls": ["https://x.com/LinQingV/status/1234567890"],
            }
        )
        hints = build_window_capture_hints(request)
        self.assertTrue(hints["preferred"])
        self.assertIn("https://x.com/LinQingV/status/1234567890", hints["manual_urls"])
        self.assertTrue(any("from%3ALinQingV" in item["url"] or "from%3ALinQingV+" in item["url"] for item in hints["search_urls"]))
        self.assertTrue(any("new Edge window" in note for note in hints["notes"]))

    def test_x_index_does_not_treat_scriptloadfailure_token_as_blocked_by_itself(self) -> None:
        result = run_x_index(
            {
                "topic": "Healthy X HTML with script token",
                "analysis_time": "2026-03-24T12:00:00+00:00",
                "seed_posts": [
                    {
                        "post_url": "https://x.com/example/status/10",
                        "html": """
                            <html>
                              <head>
                                <meta property=\"og:title\" content=\"Example on X\">
                                <meta property=\"og:description\" content=\"Direct post text still loads normally.\">
                              </head>
                              <body>
                                <div id=\"ScriptLoadFailure\" style=\"display:none\"></div>
                              </body>
                            </html>
                        """,
                        "visible_text": "Direct post text still loads normally.",
                        "used_browser_session": True,
                        "session_source": "remote_debugging",
                        "session_status": "ready",
                    }
                ],
            }
        )
        post = result["x_posts"][0]
        self.assertEqual(post["access_mode"], "browser_session")
        self.assertEqual(post["post_text_source"], "dom")
        self.assertIn("Direct post text still loads normally.", post["post_text_raw"])

    @patch("x_index_runtime.fetch_page")
    def test_x_index_live_session_media_candidates_become_media_items(self, mock_fetch_page) -> None:
        output_dir = self.examples / "tmp-session-media"
        screenshot_path = output_dir / "root.png"
        media_path = output_dir / "root-media-1.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(b"root")
        media_path.write_bytes(b"media")
        mock_fetch_page.return_value = FetchArtifact(
            url="https://x.com/example/status/11",
            final_url="https://x.com/example/status/11",
            html="""
                <html>
                  <head>
                    <meta property=\"og:title\" content=\"Example on X\">
                    <meta property=\"og:description\" content=\"Live post text from a browser session.\">
                  </head>
                  <body>
                    <img src=\"https://pbs.twimg.com/media/test-live\">
                  </body>
                </html>
            """,
            visible_text="Live post text from a browser session.",
            accessibility_text="Live post text from a browser session.",
            links_text="",
            screenshot_path=str(screenshot_path),
            error="",
            media_items=[
                {
                    "source_url": "https://pbs.twimg.com/media/test-live?format=jpg&name=small",
                    "local_artifact_path": str(media_path),
                    "ocr_source": "screenshot_crop",
                    "ocr_text_raw": "Map labels and movement arrows.",
                    "alt_text": "Airlift map image",
                    "capture_method": "dom_clip",
                }
            ],
            session_used=True,
            session_source="remote_debugging",
            session_status="ready",
            session_notes=["attached to http://127.0.0.1:9222"],
        )
        try:
            result = run_x_index(
                {
                    "topic": "Live media",
                    "analysis_time": "2026-03-24T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "manual_urls": ["https://x.com/example/status/11"],
                    "browser_session": {
                        "strategy": "remote_debugging",
                        "cdp_endpoint": "http://127.0.0.1:9222",
                        "required": True,
                    },
                }
            )
            post = result["x_posts"][0]
            self.assertEqual(post["access_mode"], "browser_session")
            self.assertEqual(post["session_health"], "effective")
            self.assertEqual(len(post["media_items"]), 1)
            self.assertTrue(any(item.get("local_artifact_path") == str(media_path) for item in post["media_items"]))
            self.assertEqual(post["media_items"][0]["alt_text"], "Airlift map image")
            self.assertEqual(post["media_items"][0]["capture_method"], "dom_clip")
            self.assertTrue(any(item.get("role") == "post_media" for item in post["artifact_manifest"]))
        finally:
            for item in sorted(output_dir.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()

    @patch("x_index_runtime.fetch_page")
    def test_x_index_session_failure_or_fallback_is_explicit(self, mock_fetch_page) -> None:
        output_dir = self.examples / "tmp-session-failure"
        output_dir.mkdir(parents=True, exist_ok=True)
        mock_fetch_page.return_value = FetchArtifact(
            url="https://x.com/example/status/12",
            final_url="https://x.com/example/status/12",
            html="",
            visible_text="",
            accessibility_text="",
            links_text="",
            screenshot_path="",
            error="remote debugging fetch failed",
            media_items=[],
            session_used=False,
            session_source="remote_debugging",
            session_status="failed",
            session_notes=["remote debugging fetch failed"],
        )
        try:
            result = run_x_index(
                {
                    "topic": "Session failure",
                    "analysis_time": "2026-03-24T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "manual_urls": ["https://x.com/example/status/12"],
                    "browser_session": {
                        "strategy": "remote_debugging",
                        "cdp_endpoint": "http://127.0.0.1:9222",
                        "required": True,
                    },
                }
            )
            post = result["x_posts"][0]
            self.assertEqual(post["session_status"], "failed")
            self.assertEqual(post["session_health"], "degraded")
            self.assertIn(post["access_mode"], {"public", "blocked"})
            self.assertTrue(any("remote debugging" in note.lower() for note in post["crawl_notes"]))
            self.assertEqual(result["session_bootstrap"]["health"], "degraded")
        finally:
            for item in sorted(output_dir.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()

    def test_x_index_parse_request_derives_phrase_and_entity_clues_from_ocr_text(self) -> None:
        request = parse_request(
            {
                "topic": "Morgan Stanley focus list screenshots",
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "ocr_root_text": (
                    "Exhibit 4: Morgan Stanley China/HK Focus List\n"
                    "Exhibit 5: Morgan Stanley China A-share Thematic Focus List\n"
                    "Aluminum Corp. of China Ltd. 601600.SS\n"
                    "Data as of March 23, 2026."
                ),
            }
        )
        self.assertIn("Exhibit 4: Morgan Stanley China/HK Focus List", request["phrase_clues"])
        self.assertIn("Morgan Stanley China/HK Focus List", request["phrase_clues"])
        self.assertIn("601600.SS", request["entity_clues"])

    def test_x_index_build_search_queries_uses_phrase_entity_and_allowlist_clues(self) -> None:
        request = parse_request(
            {
                "topic": "Morgan Stanley focus list screenshots",
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "keywords": ["Morgan Stanley"],
                "phrase_clues": [
                    "Morgan Stanley China/HK Focus List",
                    "Morgan Stanley China A-share Thematic Focus List",
                ],
                "entity_clues": ["601600.SS", "Aluminum Corp. of China Ltd."],
                "account_allowlist": ["LinQingV"],
                "max_search_queries": 20,
            }
        )
        queries = [item["query"] for item in build_search_queries(request)]
        self.assertIn('site:x.com/LinQingV/status "Morgan Stanley China/HK Focus List"', queries)
        self.assertTrue(any('"Morgan Stanley China/HK Focus List" "601600.SS"' in query for query in queries))
        self.assertIn(
            'site:x.com/LinQingV/status "Morgan Stanley" "Aluminum Corp. of China Ltd."',
            queries,
        )

    def test_x_index_build_same_author_scan_queries_uses_author_and_ocr_clues(self) -> None:
        request = parse_request(
            {
                "topic": "Morgan Stanley focus list screenshots",
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "keywords": ["Morgan Stanley"],
                "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                "entity_clues": ["601600.SS"],
                "same_author_scan_limit": 8,
            }
        )
        queries = [item["query"] for item in build_same_author_scan_queries({"author_handle": "LinQingV"}, request)]
        self.assertIn('site:x.com/LinQingV/status "Morgan Stanley China/HK Focus List"', queries)
        self.assertIn('site:x.com/LinQingV/status "601600.SS"', queries)
        self.assertTrue(any('"Morgan Stanley China/HK Focus List" "601600.SS"' in query for query in queries))

    def test_x_index_parse_request_can_seed_from_last30days_result(self) -> None:
        request = parse_request(
            {
                "analysis_time": "2026-04-02T12:00:00+00:00",
                "last30days_result": {
                    "results": [
                        {
                            "platform": "x",
                            "url": "https://x.com/LinQingV/status/123",
                            "summary": "Morgan Stanley focus list screenshot notes Aluminum Corp. of China Ltd. 601600.SS.",
                            "post_text_raw": "Morgan Stanley focus list screenshot notes Aluminum Corp. of China Ltd. 601600.SS.",
                            "author_handle": "LinQingV",
                        }
                    ]
                },
            }
        )
        self.assertEqual(request["manual_urls"], ["https://x.com/LinQingV/status/123"])
        self.assertEqual(request["account_allowlist"], ["LinQingV"])
        self.assertTrue(any("Morgan Stanley" in item for item in request["phrase_clues"]))
        self.assertIn("601600.SS", request["entity_clues"])
        self.assertEqual(len(request["seed_posts"]), 1)
        self.assertEqual(request["seed_posts"][0]["post_url"], "https://x.com/LinQingV/status/123")

    @patch("x_index_runtime.discover_search_candidates", return_value=[])
    @patch("x_index_runtime.fetch_page", side_effect=AssertionError("cached reuse should not refetch"))
    def test_x_index_reuses_recent_cached_result_without_refetch(
        self,
        _mock_fetch_page,
        _mock_discover_search,
    ) -> None:
        source_dir = self.examples / "tmp-x-reuse-source"
        target_dir = self.examples / "tmp-x-reuse-target"
        try:
            first = run_x_index(
                {
                    "topic": "Morgan Stanley reusable cache probe",
                    "analysis_time": "2026-04-02T12:00:00+00:00",
                    "output_dir": str(source_dir),
                    "account_allowlist": ["LinQingV"],
                    "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                    "entity_clues": ["601600.SS"],
                    "seed_posts": [
                        {
                            "post_url": "https://x.com/LinQingV/status/111",
                            "html": """
                                <html>
                                  <head>
                                    <meta property=\"og:title\" content=\"LinQingV on X\">
                                    <meta property=\"og:description\" content=\"Morgan Stanley adds Aluminum Corp. of China to the focus list.\">
                                  </head>
                                </html>
                            """,
                            "author_handle": "LinQingV",
                            "posted_at": "2026-03-24T10:00:00+00:00",
                            "root_post_screenshot_path": "C:\\artifacts\\linqingv-root.png",
                            "media_items": [
                                {
                                    "source_url": "https://pbs.twimg.com/media/example.jpg",
                                    "local_artifact_path": "C:\\artifacts\\linqingv-media.jpg",
                                    "ocr_text_raw": "Exhibit 4 Morgan Stanley China/HK Focus List",
                                    "ocr_summary": "Morgan Stanley China/HK Focus List image.",
                                }
                            ],
                            "used_browser_session": True,
                            "session_source": "remote_debugging",
                            "session_status": "ready",
                        }
                    ],
                }
            )
            self.assertEqual(len(first["x_posts"]), 1)
            self.assertTrue((source_dir / "x-index-result.json").exists())
            self.assertTrue((source_dir / "x-index-report.md").exists())

            second = run_x_index(
                {
                    "topic": "Morgan Stanley reusable cache probe",
                    "analysis_time": "2026-04-02T12:05:00+00:00",
                    "output_dir": str(target_dir),
                    "account_allowlist": ["LinQingV"],
                    "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                    "entity_clues": ["601600.SS"],
                }
            )
            self.assertEqual(len(second["x_posts"]), 1)
            self.assertGreaterEqual(second["reuse_summary"]["reused_posts"], 1)
            self.assertTrue(second["x_posts"][0]["discovery_reason"].startswith("reused_recent_result:"))
            self.assertEqual(second["x_posts"][0]["root_post_screenshot_path"], "C:\\artifacts\\linqingv-root.png")
            self.assertIn("reused cached x-index output", " ".join(second["x_posts"][0]["crawl_notes"]))
        finally:
            for output_dir in (source_dir, target_dir):
                if output_dir.exists():
                    for item in sorted(output_dir.rglob("*"), reverse=True):
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            item.rmdir()

    @patch("x_index_runtime.fetch_page")
    @patch("x_index_runtime.maybe_fetch_search_results")
    def test_x_index_fetch_thread_posts_prefers_same_author_time_window_scan(
        self,
        mock_search_results,
        mock_fetch_page,
    ) -> None:
        output_dir = self.examples / "tmp-thread-scan"
        output_dir.mkdir(parents=True, exist_ok=True)

        def fake_search(query: str) -> list[str]:
            if '"Morgan Stanley China/HK Focus List"' in query:
                return [
                    "https://x.com/LinQingV/status/112",
                    "https://x.com/LinQingV/status/113",
                    "https://x.com/LinQingV/status/999",
                ]
            return []

        def fake_fetch(url: str, screenshot_path: Path, session_context=None) -> FetchArtifact:
            posted_at_map = {
                "https://x.com/LinQingV/status/112": "2026-03-24T09:58:00+00:00",
                "https://x.com/LinQingV/status/113": "2026-03-24T10:04:00+00:00",
                "https://x.com/LinQingV/status/999": "2026-03-30T10:04:00+00:00",
            }
            posted_at = posted_at_map[url]
            status_id = url.rsplit("/", 1)[-1]
            return FetchArtifact(
                url=url,
                final_url=url,
                html=(
                    f'<html><head><meta property="og:title" content="@LinQingV on X">'
                    f'<meta property="article:published_time" content="{posted_at}">'
                    f'<meta property="og:description" content="Thread update {status_id}"></head></html>'
                ),
                visible_text=f"Thread update {status_id}",
                accessibility_text="",
                links_text="",
                screenshot_path="",
                error="",
                media_items=[],
            )

        mock_search_results.side_effect = fake_search
        mock_fetch_page.side_effect = fake_fetch

        try:
            request = parse_request(
                {
                    "topic": "Morgan Stanley focus list screenshots",
                    "analysis_time": "2026-04-02T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                    "entity_clues": ["601600.SS"],
                    "same_author_scan_window_hours": 48,
                    "same_author_scan_limit": 8,
                }
            )
            posts = fetch_thread_posts(
                {
                    "author_handle": "LinQingV",
                    "post_url": "https://x.com/LinQingV/status/111",
                    "posted_at": "2026-03-24T10:00:00+00:00",
                },
                "",
                request,
                output_dir,
                {"https://x.com/LinQingV/status/111"},
            )
            self.assertEqual([item["post_url"] for item in posts], [
                "https://x.com/LinQingV/status/112",
                "https://x.com/LinQingV/status/113",
            ])
            self.assertTrue(mock_search_results.called)
        finally:
            for item in sorted(output_dir.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()

    @patch("x_index_runtime.fetch_page")
    @patch("x_index_runtime.maybe_fetch_search_results", return_value=[])
    def test_x_index_fetch_thread_posts_falls_back_to_same_author_links(
        self,
        _mock_search_results,
        mock_fetch_page,
    ) -> None:
        output_dir = self.examples / "tmp-thread-fallback"
        output_dir.mkdir(parents=True, exist_ok=True)

        mock_fetch_page.return_value = FetchArtifact(
            url="https://x.com/LinQingV/status/121",
            final_url="https://x.com/LinQingV/status/121",
            html=(
                '<html><head><meta property="og:title" content="@LinQingV on X">'
                '<meta property="article:published_time" content="2026-03-24T10:05:00+00:00">'
                '<meta property="og:description" content="Fallback thread post"></head></html>'
            ),
            visible_text="Fallback thread post",
            accessibility_text="",
            links_text="",
            screenshot_path="",
            error="",
            media_items=[],
        )

        try:
            request = parse_request(
                {
                    "topic": "Morgan Stanley focus list screenshots",
                    "analysis_time": "2026-04-02T12:00:00+00:00",
                    "output_dir": str(output_dir),
                    "phrase_clues": ["Morgan Stanley China/HK Focus List"],
                    "same_author_scan_window_hours": 48,
                }
            )
            posts = fetch_thread_posts(
                {
                    "author_handle": "LinQingV",
                    "post_url": "https://x.com/LinQingV/status/111",
                    "posted_at": "2026-03-24T10:00:00+00:00",
                },
                "https://x.com/LinQingV/status/121 https://x.com/Other/status/222",
                request,
                output_dir,
                {"https://x.com/LinQingV/status/111"},
            )
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["post_url"], "https://x.com/LinQingV/status/121")
        finally:
            for item in sorted(output_dir.rglob("*"), reverse=True):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()

    def test_load_json_accepts_windows_bom(self) -> None:
        bom_path = self.examples / "tmp-bom-request.json"
        bom_path.write_text('{"topic":"bom"}', encoding="utf-8-sig")
        try:
            payload = read_json(bom_path)
            self.assertEqual(payload["topic"], "bom")
        finally:
            if bom_path.exists():
                bom_path.unlink()


if __name__ == "__main__":
    unittest.main()
