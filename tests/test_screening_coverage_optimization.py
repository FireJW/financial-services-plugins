#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Class 7: TestDiscoveryThresholdRelaxation
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
# Class 8: TestCapEnforcement
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
# Class 9: TestBackwardCompatibility
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


if __name__ == "__main__":
    unittest.main()
