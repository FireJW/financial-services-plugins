from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "a-share-sentiment-overlay"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from a_share_sentiment_overlay_runtime import (
    build_a_share_sentiment_overlay_result,
    build_sentiment_vol_overlay,
    classify_positioning_posture,
    classify_sentiment_regime,
    normalize_request,
    strip_html_tags,
)


class AShareSentimentOverlayRuntimeTests(unittest.TestCase):
    def test_classifies_growth_panic_when_growth_iv_and_skew_are_extreme(self) -> None:
        request = normalize_request(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "growth_iv_percentile": 94.0,
                "skew_percentile": 90.0,
                "breadth_stress_score": 78.0,
            }
        )
        self.assertEqual(classify_sentiment_regime(request), "panic_in_growth_not_broad_market")
        self.assertEqual(classify_positioning_posture("panic_in_growth_not_broad_market"), "buy_panic_reduce_euphoria")

    def test_classifies_euphoria_when_iv_and_skew_are_depressed(self) -> None:
        request = normalize_request(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "broad_iv_percentile": 12.0,
                "growth_iv_percentile": 18.0,
                "skew_percentile": 20.0,
                "breadth_stress_score": 18.0,
            }
        )
        self.assertEqual(classify_sentiment_regime(request), "euphoria")
        overlay = build_sentiment_vol_overlay(request)
        self.assertEqual(overlay["positioning_posture"], "reduce_euphoria")

    def test_merges_overlay_into_shortlist_request_when_path_is_supplied(self) -> None:
        shortlist_path = Path.cwd() / ".tmp" / "test-a-share-sentiment-shortlist.json"
        shortlist_path.parent.mkdir(parents=True, exist_ok=True)
        shortlist_path.write_text('{"template_name":"demo"}', encoding="utf-8")
        result = build_a_share_sentiment_overlay_result(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "broad_iv_percentile": 44.0,
                "growth_iv_percentile": 94.0,
                "skew_percentile": 90.0,
                "breadth_stress_score": 78.0,
                "shortlist_request_path": str(shortlist_path),
            }
        )
        self.assertEqual(result["sentiment_vol_overlay"]["sentiment_regime"], "panic_in_growth_not_broad_market")
        self.assertIn("resolved_shortlist_request", result)
        self.assertIn("sentiment_vol_overlay", result["resolved_shortlist_request"])

    def test_live_provider_can_fill_breadth_only(self) -> None:
        with patch("a_share_sentiment_overlay_runtime.eastmoney_breadth_snapshot") as breadth_mock:
            breadth_mock.return_value = {
                "sample_count": 3000,
                "advancers": 900,
                "decliners": 2100,
                "advance_decline_ratio": 0.429,
                "median_pct_change": -2.1,
                "up_limit_count": 12,
                "down_limit_count": 84,
                "breadth_stress_score": 82.0,
            }
            result = build_a_share_sentiment_overlay_result(
                {
                    "analysis_time": "2026-04-12T00:00:00+00:00",
                    "live_data_provider": "eastmoney_breadth",
                    "breadth_stress_score": None,
                }
            )
        self.assertIn("live_fetch_summary", result)
        self.assertEqual(result["live_fetch_summary"]["provider"], "eastmoney_breadth")
        self.assertEqual(result["sentiment_vol_overlay"]["breadth_stress_score"], 82.0)

    def test_source_parse_mode_can_extract_option_percentiles_from_text(self) -> None:
        text = (
            "300ETF期权加权隐含波动率位于历史44%分位附近。"
            "500ETF期权加权隐含波动率仍处于历史94%分位以上。"
            "创业板ETF与科创50ETF Skew位于历史90%分位以上。"
        )
        result = build_a_share_sentiment_overlay_result(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "source_parse_mode": "cn_option_weekly_note",
                "source_text": text,
            }
        )
        overlay = result["sentiment_vol_overlay"]
        self.assertEqual(overlay["broad_iv_percentile"], 44.0)
        self.assertEqual(overlay["growth_iv_percentile"], 94.0)
        self.assertEqual(overlay["skew_percentile"], 90.0)
        self.assertEqual(overlay["sentiment_regime"], "panic_in_growth")

    def test_source_parse_mode_can_extract_option_percentiles_from_english_text(self) -> None:
        text = (
            "300ETF weighted implied volatility is around the 44% percentile. "
            "500ETF weighted implied volatility remains above the 94% percentile. "
            "ChiNext ETF Skew is above the 90% percentile."
        )
        result = build_a_share_sentiment_overlay_result(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "source_parse_mode": "cn_option_weekly_note",
                "source_text": text,
            }
        )
        overlay = result["sentiment_vol_overlay"]
        self.assertEqual(overlay["broad_iv_percentile"], 44.0)
        self.assertEqual(overlay["growth_iv_percentile"], 94.0)
        self.assertEqual(overlay["skew_percentile"], 90.0)

    def test_strip_html_tags_preserves_option_note_sentences(self) -> None:
        html = """
        <html><body>
        <p>300ETF期权加权隐含波动率位于历史44%分位附近。</p>
        <p>500ETF期权加权隐含波动率仍处于历史94%分位以上。</p>
        <p>创业板ETF与科创50ETF Skew位于历史90%分位以上。</p>
        </body></html>
        """
        text = strip_html_tags(html)
        self.assertIn("300ETF期权加权隐含波动率位于历史44%分位附近。", text)
        self.assertIn("500ETF期权加权隐含波动率仍处于历史94%分位以上。", text)

    def test_source_parse_prefers_body_reading_over_title_duplicate(self) -> None:
        text = (
            "信·期权 | ETF期权加权隐含波动率大幅下降，300ETF期权加权隐波降至历史5%分位以下。"
            "正文 "
            "当前只有500ETF期权加权隐波仍在长期中位数以上，其他所有ETF期权加权隐波均降至长期中位数以下，"
            "其中300ETF期权加权隐波已降至历史2.9%分位的极低水平。"
        )
        result = build_a_share_sentiment_overlay_result(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "source_parse_mode": "cn_option_weekly_note",
                "source_text": text,
            }
        )
        self.assertEqual(result["sentiment_vol_overlay"]["broad_iv_percentile"], 2.9)

    # ---- P0 fix: data_insufficient regime when IV/Skew are all missing ----

    def test_returns_data_insufficient_when_all_iv_and_skew_are_none(self) -> None:
        """When no IV percentile or skew data is available, the overlay must
        return data_insufficient rather than silently defaulting to neutral."""
        request = normalize_request(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
            }
        )
        self.assertEqual(classify_sentiment_regime(request), "data_insufficient")
        self.assertEqual(classify_positioning_posture("data_insufficient"), "overlay_inoperative")

    def test_returns_data_insufficient_breadth_only_when_only_breadth_present(self) -> None:
        """When only breadth_stress_score is available but all IV/Skew are
        missing, the overlay should signal that it has breadth data but cannot
        classify panic vs euphoria."""
        request = normalize_request(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "breadth_stress_score": 82.0,
            }
        )
        self.assertEqual(classify_sentiment_regime(request), "data_insufficient_breadth_only")
        self.assertEqual(classify_positioning_posture("data_insufficient_breadth_only"), "overlay_inoperative")

    def test_data_insufficient_takeaway_warns_user(self) -> None:
        """The takeaway for data_insufficient must explicitly warn the user
        that the overlay is inoperative, not just say 'neutral'."""
        from a_share_sentiment_overlay_runtime import build_takeaway
        takeaway = build_takeaway("data_insufficient", "overlay_inoperative")
        self.assertIn("IV/Skew data is missing", takeaway)
        self.assertIn("inoperative", takeaway)

    # ---- P1 fix: source_parse_summary degraded when no fields extracted ----

    def test_source_parse_returns_degraded_when_no_fields_extracted(self) -> None:
        """When source_parse_mode is active but the text yields zero
        percentile fields, status should be degraded, not ok."""
        result = build_a_share_sentiment_overlay_result(
            {
                "analysis_time": "2026-04-12T00:00:00+00:00",
                "source_parse_mode": "cn_option_weekly_note",
                "source_text": "This text has no option percentile data at all.",
            }
        )
        summary = result["source_parse_summary"]
        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(len(summary["parsed_fields"]), 0)
        self.assertIn("source_text_parsed_but_no_percentile_fields_extracted", summary["warnings"])



if __name__ == "__main__":
    unittest.main()
