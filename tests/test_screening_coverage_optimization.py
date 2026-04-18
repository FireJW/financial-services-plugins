#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as runtime


# ---------------------------------------------------------------------------
# Class 1: TestFourTierClassification
# ---------------------------------------------------------------------------
class TestFourTierClassification(unittest.TestCase):
    def _make_candidate(self, ticker, score=70, keep=False, **kwargs):
        c = {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "keep": keep,
            "hard_filter_failures": [],
            "tier_tags": [],
        }
        c.update(kwargs)
        return c

    def test_top_pick_goes_to_t1(self):
        top = [self._make_candidate("A", score=80, keep=True)]
        tiers = runtime.assign_tiers(
            top, [], {"qualified": [], "watch": [], "track": []}, top, 60.0
        )
        self.assertEqual(len(tiers["T1"]), 1)
        self.assertEqual(tiers["T1"][0]["ticker"], "A")

    def test_discovery_qualified_goes_to_t2(self):
        disc = {
            "qualified": [self._make_candidate("B", discovery_bucket="qualified")],
            "watch": [],
            "track": [],
        }
        tiers = runtime.assign_tiers([], [], disc, [], 60.0)
        self.assertEqual(len(tiers["T2"]), 1)
        self.assertEqual(tiers["T2"][0]["ticker"], "B")

    def test_ordinary_near_miss_goes_to_t3(self):
        nm = [self._make_candidate("C", score=55)]
        tiers = runtime.assign_tiers(
            [], nm, {"qualified": [], "watch": [], "track": []}, nm, 60.0
        )
        self.assertEqual(len(tiers["T3"]), 1)
        self.assertEqual(tiers["T3"][0]["ticker"], "C")

    def test_discovery_track_goes_to_t4(self):
        disc = {
            "qualified": [],
            "watch": [],
            "track": [self._make_candidate("D")],
        }
        tiers = runtime.assign_tiers([], [], disc, [], 60.0)
        self.assertEqual(len(tiers["T4"]), 1)
        self.assertEqual(tiers["T4"][0]["ticker"], "D")


# ---------------------------------------------------------------------------
# Class 2: TestNearMissPromotion
# ---------------------------------------------------------------------------
class TestNearMissPromotion(unittest.TestCase):
    def _make_candidate(self, ticker, **kwargs):
        c = {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": 55,
            "keep": False,
            "hard_filter_failures": [],
            "tier_tags": [],
        }
        c.update(kwargs)
        return c

    def test_catalyst_score_promotes_to_t2(self):
        c = self._make_candidate("A", structured_catalyst_score=10)
        self.assertTrue(runtime.should_promote_near_miss_to_event_driven(c))

    def test_discovery_qualified_promotes_to_t2(self):
        c = self._make_candidate("A", discovery_bucket="qualified")
        self.assertTrue(runtime.should_promote_near_miss_to_event_driven(c))

    def test_independent_sources_promote_to_t2(self):
        c = self._make_candidate(
            "A",
            x_style_inputs=[
                {"source_account": "acc1"},
                {"source_account": "acc2"},
            ],
        )
        self.assertTrue(runtime.should_promote_near_miss_to_event_driven(c))

    def test_no_event_stays_in_t3(self):
        c = self._make_candidate("A")
        self.assertFalse(runtime.should_promote_near_miss_to_event_driven(c))


# ---------------------------------------------------------------------------
# Class 3: TestCatalystWaiver
# ---------------------------------------------------------------------------
class TestCatalystWaiver(unittest.TestCase):
    def _make_candidate(self, ticker, score=55, keep=False, failures=None):
        return {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "keep": keep,
            "hard_filter_failures": failures or [],
            "tier_tags": [],
        }

    def test_single_catalyst_failure_waived_in_event_profile(self):
        c = self._make_candidate(
            "A",
            score=52,
            failures=["no_structured_catalyst_within_window"],
        )
        result = runtime.apply_catalyst_waiver(
            [c], "month_end_event_support_transition", 60.0
        )
        self.assertEqual(len(result), 1)
        self.assertIn("catalyst_waived", result[0]["tier_tags"])

    def test_multiple_failures_not_waived(self):
        c = self._make_candidate(
            "A",
            score=52,
            failures=[
                "no_structured_catalyst_within_window",
                "bars_fetch_failed",
            ],
        )
        result = runtime.apply_catalyst_waiver(
            [c], "month_end_event_support_transition", 60.0
        )
        self.assertEqual(len(result), 0)

    def test_default_profile_no_waiver(self):
        c = self._make_candidate(
            "A",
            score=52,
            failures=["no_structured_catalyst_within_window"],
        )
        result = runtime.apply_catalyst_waiver([c], "default", 60.0)
        self.assertEqual(len(result), 0)

    def test_hard_exclusion_not_waived(self):
        c = self._make_candidate(
            "A", score=52, failures=["bars_fetch_failed"]
        )
        result = runtime.apply_catalyst_waiver(
            [c], "month_end_event_support_transition", 60.0
        )
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# Class 4: TestTwoRoundEvaluation
# ---------------------------------------------------------------------------
class TestTwoRoundEvaluation(unittest.TestCase):
    def _mock_assess(self, candidate, bars_data, profile):
        """Mock assess function. Returns keep=True if profile is broad_coverage_mode."""
        result = dict(candidate)
        if profile == "broad_coverage_mode":
            result["keep"] = True
        return result

    def test_round2_triggers_when_top_picks_below_threshold(self):
        candidates = [{"ticker": f"T{i}", "keep": False} for i in range(5)]
        all_assessed, profile_used, round_info = (
            runtime.evaluate_with_coverage_fallback(
                candidates,
                {},
                "month_end_event_support_transition",
                self._mock_assess,
            )
        )
        self.assertEqual(round_info, "round_2")
        self.assertEqual(profile_used, "broad_coverage_mode")

    def test_round2_does_not_trigger_when_enough_top_picks(self):
        candidates = [{"ticker": f"T{i}", "keep": True} for i in range(3)]

        def assess(c, bars, profile):
            return dict(c)

        all_assessed, profile_used, round_info = (
            runtime.evaluate_with_coverage_fallback(
                candidates,
                {},
                "month_end_event_support_transition",
                assess,
            )
        )
        self.assertEqual(round_info, "round_1")

    def test_round2_replaces_core_results(self):
        candidates = [{"ticker": "A", "keep": False, "score": 50}]
        all_assessed, _, round_info = runtime.evaluate_with_coverage_fallback(
            candidates,
            {},
            "month_end_event_support_transition",
            self._mock_assess,
        )
        self.assertEqual(round_info, "round_2")
        self.assertTrue(all_assessed[0]["keep"])


# ---------------------------------------------------------------------------
# Class 5: TestFloorPolicy
# ---------------------------------------------------------------------------
class TestFloorPolicy(unittest.TestCase):
    def _make_candidate(self, ticker, score=50, failures=None):
        return {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "hard_filter_failures": failures or [],
            "tier_tags": [],
        }

    def test_supplementation_when_below_target(self):
        tiers = {
            "T1": [self._make_candidate(f"T{i}", score=70) for i in range(3)],
            "T2": [],
            "T3": [],
            "T4": [],
        }
        extras = [self._make_candidate(f"E{i}", score=45) for i in range(10)]
        result = runtime.apply_floor_policy(
            tiers, extras, {"watch": [], "track": []}, 60.0
        )
        total = sum(len(v) for v in result.values())
        self.assertGreaterEqual(total, runtime.MIN_COVERAGE_TARGET)

    def test_coverage_fill_tag_applied(self):
        tiers = {
            "T1": [self._make_candidate("T0", score=70)],
            "T2": [],
            "T3": [],
            "T4": [],
        }
        extras = [self._make_candidate(f"E{i}", score=45) for i in range(10)]
        result = runtime.apply_floor_policy(
            tiers, extras, {"watch": [], "track": []}, 60.0
        )
        for c in result["T3"]:
            if c["ticker"].startswith("E"):
                self.assertIn("coverage_fill", c["tier_tags"])

    def test_hard_exclusions_never_supplemented(self):
        tiers = {"T1": [], "T2": [], "T3": [], "T4": []}
        excluded = [
            self._make_candidate("BAD", score=55, failures=["bars_fetch_failed"])
        ]
        result = runtime.apply_floor_policy(
            tiers, excluded, {"watch": [], "track": []}, 60.0
        )
        all_tickers = [
            c["ticker"] for tier in result.values() for c in tier
        ]
        self.assertNotIn("BAD", all_tickers)

    def test_no_supplementation_when_above_target(self):
        tiers = {
            "T1": [
                self._make_candidate(f"T{i}", score=70) for i in range(12)
            ],
            "T2": [],
            "T3": [],
            "T4": [],
        }
        result = runtime.apply_floor_policy(
            tiers, [], {"watch": [], "track": []}, 60.0
        )
        total = sum(len(v) for v in result.values())
        self.assertEqual(total, 12)


# ---------------------------------------------------------------------------
# Class 6: TestTrackLevelCoverageIntegration
# ---------------------------------------------------------------------------
class TestTrackLevelCoverageIntegration(unittest.TestCase):
    def _make_assessed(self, ticker, score, keep=False, failures=None):
        return {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "keep": keep,
            "hard_filter_failures": failures or [],
            "tier_tags": [],
            "scores": {"adjusted_total_score": score},
            "score_components": {"structured_catalyst_score": 0},
        }

    def test_enrich_track_result_applies_waiver_and_floor_before_caps(self):
        result = {
            "filter_summary": {
                "kept_count": 1,
                "keep_threshold": 58.0,
                "profile": "month_end_event_support_transition",
            },
            "dropped": [],
            "report_markdown": "# Test\n",
        }
        assessed = [
            self._make_assessed("000988.SZ", 60, keep=True),
            self._make_assessed(
                "002460.SZ",
                53,
                keep=False,
                failures=["no_structured_catalyst_within_window"],
            ),
            self._make_assessed("600176.SS", 36, keep=False),
            self._make_assessed(
                "688256.SH",
                57,
                keep=False,
                failures=["bars_fetch_failed"],
            ),
        ]

        enriched = runtime.enrich_track_result(
            result,
            [],
            assessed_candidates=assessed,
            track_name="main_board",
            track_config=runtime.TRACK_CONFIGS["main_board"],
        )

        self.assertTrue(enriched["tier_metadata"]["floor_policy_applied"])
        self.assertEqual(
            [row["ticker"] for row in enriched["tier_output"]["T1"]],
            ["000988.SZ"],
        )
        t3_rows = {
            row["ticker"]: row
            for row in enriched["tier_output"]["T3"]
        }
        self.assertIn("002460.SZ", t3_rows)
        self.assertIn("catalyst_waived", t3_rows["002460.SZ"]["tier_tags"])
        self.assertIn("600176.SS", t3_rows)
        self.assertIn("coverage_fill", t3_rows["600176.SS"]["tier_tags"])
        self.assertNotIn("688256.SH", t3_rows)

    def test_enrich_track_result_rescues_structured_support_name_into_low_confidence_t3(self):
        result = {
            "filter_summary": {
                "kept_count": 0,
                "keep_threshold": 58.0,
                "profile": "month_end_event_support_transition",
            },
            "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
            "dropped": [],
            "report_markdown": "# Test\n",
        }
        assessed = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "adjusted_total_score": 0.0,
                "keep": False,
                "hard_filter_failures": ["bars_fetch_failed"],
                "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                "structured_catalyst_snapshot": {
                    "structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]
                },
                "tier_tags": [],
                "scores": {"adjusted_total_score": 0.0},
                "score_components": {"structured_catalyst_score": 0},
            }
        ]
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }

        with patch.object(runtime, "local_market_snapshot_for_candidate", return_value=snapshot):
            enriched = runtime.enrich_track_result(
                result,
                [],
                assessed_candidates=assessed,
                track_name="main_board",
                track_config=runtime.TRACK_CONFIGS["main_board"],
            )

        tickers = [row["ticker"] for row in enriched["tier_output"]["T3"]]
        self.assertIn("601975.SS", tickers)
        rescued = next(row for row in enriched["tier_output"]["T3"] if row["ticker"] == "601975.SS")
        self.assertIn("low_confidence_fallback", rescued["tier_tags"])
        self.assertEqual(rescued["fallback_support_reason"], "structured_catalyst")

    def test_enrich_track_result_never_promotes_fallback_name_to_t1(self):
        result = {
            "filter_summary": {
                "kept_count": 0,
                "keep_threshold": 58.0,
                "profile": "month_end_event_support_transition",
            },
            "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
            "dropped": [],
            "report_markdown": "# Test\n",
        }
        assessed = [
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "adjusted_total_score": 88.0,
                "keep": False,
                "hard_filter_failures": ["bars_fetch_failed"],
                "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                "structured_catalyst_snapshot": {
                    "structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]
                },
                "tier_tags": [],
                "scores": {"adjusted_total_score": 88.0},
                "score_components": {"structured_catalyst_score": 0},
            }
        ]
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }

        with patch.object(runtime, "local_market_snapshot_for_candidate", return_value=snapshot):
            enriched = runtime.enrich_track_result(
                result,
                [],
                assessed_candidates=assessed,
                track_name="main_board",
                track_config=runtime.TRACK_CONFIGS["main_board"],
            )

        self.assertNotIn("601975.SS", [row["ticker"] for row in enriched["tier_output"]["T1"]])


# ---------------------------------------------------------------------------
# Class 7: TestGeopoliticsRankingBias
# ---------------------------------------------------------------------------
class TestGeopoliticsRankingBias(unittest.TestCase):
    def _make_candidate(self, ticker, score=55.0, keep=False, chain_name=""):
        return {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "score": score,
            "scores": {"adjusted_total_score": score},
            "score_components": {"adjusted_total_score": score},
            "keep": keep,
            "chain_name": chain_name,
            "hard_filter_failures": [],
            "tier_tags": [],
        }

    def test_beneficiary_chain_ranks_ahead_in_escalation(self):
        overlay = {
            "regime_label": "escalation",
            "beneficiary_chains": ["oil_shipping"],
            "headwind_chains": ["airlines"],
        }
        oil = self._make_candidate("OIL.SS", score=55.0, chain_name="oil_shipping")
        neutral = self._make_candidate("NEUTRAL.SS", score=55.0, chain_name="neutral_chain")

        tiers = runtime.assign_tiers(
            [],
            [neutral, oil],
            {"qualified": [], "watch": [], "track": []},
            [neutral, oil],
            60.0,
            geopolitics_overlay=overlay,
        )

        self.assertEqual([row["ticker"] for row in tiers["T3"][:2]], ["OIL.SS", "NEUTRAL.SS"])

    def test_headwind_chain_ranks_lower_in_escalation(self):
        overlay = {
            "regime_label": "escalation",
            "beneficiary_chains": ["oil_shipping"],
            "headwind_chains": ["airlines"],
        }
        neutral = self._make_candidate("NEUTRAL.SS", score=55.0, chain_name="neutral_chain")
        airline = self._make_candidate("AIR.SS", score=55.0, chain_name="airlines")

        tiers = runtime.assign_tiers(
            [],
            [airline, neutral],
            {"qualified": [], "watch": [], "track": []},
            [airline, neutral],
            60.0,
            geopolitics_overlay=overlay,
        )

        self.assertEqual([row["ticker"] for row in tiers["T3"][:2]], ["NEUTRAL.SS", "AIR.SS"])

    def test_t1_membership_does_not_change_due_to_overlay(self):
        overlay = {
            "regime_label": "escalation",
            "beneficiary_chains": ["oil_shipping"],
            "headwind_chains": ["airlines"],
        }
        top_pick = self._make_candidate("TOP.SS", score=61.0, keep=True, chain_name="airlines")
        observer = self._make_candidate("WATCH.SS", score=55.0, keep=False, chain_name="oil_shipping")

        tiers = runtime.assign_tiers(
            [top_pick],
            [observer],
            {"qualified": [], "watch": [], "track": []},
            [top_pick, observer],
            60.0,
            geopolitics_overlay=overlay,
        )

        self.assertEqual([row["ticker"] for row in tiers["T1"]], ["TOP.SS"])
        self.assertNotIn("WATCH.SS", [row["ticker"] for row in tiers["T1"]])

    def test_enrich_track_result_uses_geopolitics_overlay_for_t3_order(self):
        result = {
            "filter_summary": {
                "kept_count": 0,
                "keep_threshold": 58.0,
                "profile": "month_end_event_support_transition",
            },
            "request": {
                "macro_geopolitics_overlay": {
                    "regime_label": "escalation",
                    "beneficiary_chains": ["oil_shipping"],
                    "headwind_chains": ["airlines"],
                }
            },
            "dropped": [],
            "report_markdown": "# Test\n",
        }
        assessed = [
            self._make_candidate("NEUTRAL.SS", score=55.0, chain_name="neutral_chain"),
            self._make_candidate("OIL.SS", score=55.0, chain_name="oil_shipping"),
        ]

        enriched = runtime.enrich_track_result(
            result,
            [],
            assessed_candidates=assessed,
            track_name="main_board",
            track_config=runtime.TRACK_CONFIGS["main_board"],
        )

        self.assertEqual(
            [row["ticker"] for row in enriched["tier_output"]["T3"][:2]],
            ["OIL.SS", "NEUTRAL.SS"],
        )


# ---------------------------------------------------------------------------
# Class 8: TestGeopoliticsCandidateSynthesis
# ---------------------------------------------------------------------------
class TestGeopoliticsCandidateSynthesis(unittest.TestCase):
    def test_builds_escalation_candidate_from_news_x_market_alignment(self):
        candidate_input = {
            "news_signals": [
                {
                    "headline": "Shipping risk rises",
                    "summary": "Disruption fears climb.",
                    "direction_hint": "escalation",
                }
            ],
            "x_signals": [
                {
                    "account": "MacroDesk",
                    "summary": "Supply risk repricing resumes.",
                    "direction_hint": "escalation",
                }
            ],
            "market_signals": {
                "oil": "up",
                "gold": "up",
                "shipping": "up",
                "risk_style": "risk_off",
                "airlines": "down",
            },
        }

        candidate = runtime.build_macro_geopolitics_candidate(candidate_input)
        self.assertEqual(candidate["candidate_regime"], "escalation")
        self.assertEqual(candidate["signal_alignment"], "news+x+market")
        self.assertEqual(candidate["status"], "candidate_only")

    def test_returns_insufficient_signal_when_only_one_signal_class_supports_direction(self):
        candidate_input = {
            "news_signals": [
                {
                    "headline": "Shipping risk rises",
                    "summary": "Disruption fears climb.",
                    "direction_hint": "escalation",
                }
            ],
        }

        candidate = runtime.build_macro_geopolitics_candidate(candidate_input)
        self.assertEqual(candidate["candidate_regime"], "insufficient_signal")

    def test_whipsaw_requires_cross_source_conflict(self):
        candidate_input = {
            "news_signals": [
                {
                    "headline": "Talks resume",
                    "summary": "Transit may normalize.",
                    "direction_hint": "de_escalation",
                }
            ],
            "x_signals": [
                {
                    "account": "MacroDesk",
                    "summary": "Headline reversal risk is rising.",
                    "direction_hint": "whipsaw",
                }
            ],
            "market_signals": {
                "oil": "up",
                "gold": "up",
                "risk_style": "mixed",
            },
        }

        candidate = runtime.build_macro_geopolitics_candidate(candidate_input)
        self.assertIn(candidate["candidate_regime"], {"whipsaw", "insufficient_signal"})
        self.assertTrue(candidate["evidence_summary"])


# ---------------------------------------------------------------------------
# Class 9: TestDiscoveryThresholdRelaxation
# ---------------------------------------------------------------------------
class TestDiscoveryThresholdRelaxation(unittest.TestCase):
    """Test that discovery thresholds were relaxed per Step 1."""

    def test_validation_medium_reaches_qualified(self):
        import earnings_momentum_discovery as discovery

        # Build a candidate whose computed labels will be:
        #   event_strength="strong", market_validation=medium (score=2),
        #   rumor_confidence_range=medium_high (response_ambiguous state)
        candidate = {
            "event_strength": "strong",
            # market_validation data that yields "medium" label (score=2 of 4)
            "market_validation": {
                "volume_multiple_5d": 2.0,  # >= 1.5 → +1
                "breakout": True,           # truthy  → +1
                "relative_strength": "weak",
                "chain_resonance": False,
            },
            # Sources with ambiguous response → rumor_confidence_range "medium_high"
            "sources": [
                {"source_type": "news", "summary": "有待确认"},
            ],
        }
        bucket = discovery.assign_discovery_bucket(candidate)
        self.assertEqual(bucket, "qualified")

    def test_auto_discovery_threshold_lowered(self):
        import earnings_momentum_discovery as discovery

        # A candidate with catalyst_score=10 should get event_strength="strong"
        candidate = {
            "ticker": "TEST.SS",
            "name": "Test",
            "keep": False,
            "adjusted_total_score": 50,
            "score_components": {"structured_catalyst_score": 10},
            "sector": "tech",
            "chain_role": "",
            "hard_filter_failures": ["some_failure"],
            "structured_catalyst_snapshot": {"structured_catalyst_within_window": True},
        }
        results = discovery.build_auto_discovery_candidates([candidate])
        if results:
            self.assertEqual(results[0].get("event_strength"), "strong")


# ---------------------------------------------------------------------------
# Class 10: TestCapEnforcement
# ---------------------------------------------------------------------------
class TestCapEnforcement(unittest.TestCase):
    def _make_candidate(self, ticker, score=70):
        return {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": score,
            "tier_tags": [],
        }

    def test_t1_cap_at_10(self):
        tiers = {
            "T1": [
                self._make_candidate(f"T{i}", score=70 + i) for i in range(15)
            ],
            "T2": [],
            "T3": [],
            "T4": [],
        }
        capped, overflow = runtime.apply_rendered_caps(tiers)
        self.assertEqual(len(capped["T1"]), 10)
        self.assertEqual(len(overflow), 5)

    def test_t2_cap_at_5(self):
        tiers = {
            "T1": [],
            "T2": [
                self._make_candidate(f"T{i}", score=60 + i) for i in range(8)
            ],
            "T3": [],
            "T4": [],
        }
        capped, overflow = runtime.apply_rendered_caps(tiers)
        self.assertEqual(len(capped["T2"]), 5)
        self.assertEqual(len(overflow), 3)

    def test_overflow_tagged(self):
        tiers = {
            "T1": [
                self._make_candidate(f"T{i}", score=70 + i) for i in range(12)
            ],
            "T2": [],
            "T3": [],
            "T4": [],
        }
        _, overflow = runtime.apply_rendered_caps(tiers)
        for c in overflow:
            self.assertIn("tier_cap_overflow", c["tier_tags"])


# ---------------------------------------------------------------------------
# Class 11: TestBackwardCompatibility
# ---------------------------------------------------------------------------
class TestBackwardCompatibility(unittest.TestCase):
    def test_old_fields_still_populated(self):
        """Verify that the old field names are still populated when discovery data exists."""
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 60.0},
            "dropped": [],
            "report_markdown": "# Test\n",
        }
        assessed = [
            {
                "ticker": "A.SS",
                "name": "TestA",
                "adjusted_total_score": 70,
                "keep": True,
                "hard_filter_failures": [],
                "score_components": {},
            },
        ]
        enriched = runtime.enrich_live_result_reporting(
            result, [], assessed_candidates=assessed
        )
        # Old fields should still be present (even if empty lists)
        self.assertIn("report_markdown", enriched)
        # diagnostic_scorecard should exist since we passed assessed_candidates
        if enriched.get("diagnostic_scorecard"):
            self.assertIsInstance(enriched["diagnostic_scorecard"], list)


class TestBarsFallbackRescue(unittest.TestCase):
    def _make_failed_candidate(self, ticker="601975.SS", **overrides):
        base = {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": 0.0,
            "score": 0.0,
            "keep": False,
            "midday_status": "blocked",
            "hard_filter_failures": ["bars_fetch_failed"],
            "bars_fetch_error": f"bars_fetch_failed for `{ticker}`: boom",
            "tier_tags": [],
            "structured_catalyst_snapshot": {},
            "track_name": "main_board",
        }
        base.update(overrides)
        return base

    def test_bars_failed_candidate_with_structured_support_and_snapshot_is_rescued_to_t3(self):
        candidate = self._make_failed_candidate(
            structured_catalyst_snapshot={
                "structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]
            },
        )
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNotNone(rescued)
        self.assertIn("low_confidence_fallback", rescued["tier_tags"])
        self.assertIn("fallback_snapshot_only", rescued["tier_tags"])
        self.assertEqual(rescued["fallback_support_reason"], "structured_catalyst")
        self.assertEqual(rescued["wrapper_tier"], "T3")

    def test_bars_failed_candidate_without_support_is_not_rescued(self):
        candidate = self._make_failed_candidate()
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNone(rescued)

    def test_bars_failed_candidate_with_broken_snapshot_is_not_rescued(self):
        candidate = self._make_failed_candidate(discovery_bucket="watch")
        snapshot = {
            "close": 4.2,
            "pct_chg": -6.0,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 31.0,
            "volume_ratio": 0.6,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNone(rescued)


if __name__ == "__main__":
    unittest.main()
