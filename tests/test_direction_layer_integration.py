#!/usr/bin/env python3
"""Tests for direction layer execution integration."""
from __future__ import annotations

import sys
import unittest
from copy import deepcopy
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


class ResolveDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.2: build-time ticker resolution."""

    def _make_direction_map(self):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "", "name": "中际旭创"},
                    {"ticker": "", "name": "新易盛"},
                ],
                "high_beta_names": [
                    {"ticker": "", "name": "天孚通信"},
                ],
                "mapping_note": "Direction reference only. Not a formal execution layer.",
            }
        ]

    def test_resolve_direction_tickers_fills_known_names(self):
        """Mock resolver returns tickers for known names, verify tickers are filled."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()
        mock_results = {"中际旭创": "300308", "新易盛": "300502", "天孚通信": "300394"}

        def mock_resolver(name: str) -> str | None:
            return mock_results.get(name)

        resolved = resolve_direction_tickers(direction_map, resolver=mock_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "300308")
        self.assertEqual(entry["leaders"][1]["ticker"], "300502")
        self.assertEqual(entry["high_beta_names"][0]["ticker"], "300394")
        self.assertIn("Tickers resolved", entry["mapping_note"])

    def test_resolve_direction_tickers_keeps_empty_on_failure(self):
        """Resolver returns None → ticker stays empty string."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()

        def failing_resolver(name: str) -> str | None:
            return None

        resolved = resolve_direction_tickers(direction_map, resolver=failing_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "")
        self.assertEqual(entry["leaders"][1]["ticker"], "")


class CrossCheckDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.3: execution-time cross-check against universe."""

    def test_cross_check_direction_tickers_against_universe(self):
        """Names matched against universe by name, in_universe flag set correctly."""
        import month_end_shortlist_runtime as runtime

        direction_map = [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "300308", "name": "中际旭创"},
                    {"ticker": "", "name": "未知公司"},
                ],
                "high_beta_names": [
                    {"ticker": "300394", "name": "天孚通信"},
                ],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]
        universe = [
            {"ticker": "300308", "name": "中际旭创", "f12": "300308", "f14": "中际旭创"},
            {"ticker": "300394", "name": "天孚通信", "f12": "300394", "f14": "天孚通信"},
            {"ticker": "002236", "name": "大华股份", "f12": "002236", "f14": "大华股份"},
        ]

        enriched = runtime.cross_check_direction_tickers(direction_map, universe)
        entry = enriched[0]
        # 300308 is in universe
        self.assertTrue(entry["leaders"][0]["in_universe"])
        # 未知公司 has no ticker and no name match
        self.assertFalse(entry["leaders"][1]["in_universe"])
        # 300394 is in universe
        self.assertTrue(entry["high_beta_names"][0]["in_universe"])


class DirectionAlignmentBoostTests(unittest.TestCase):
    """Spec Section 2: two-tier direction alignment scoring."""

    def _make_weekend_candidate(self, signal_strength="high", status="candidate_only"):
        return {
            "candidate_topics": [{"topic_name": "optical_interconnect", "topic_label": "光通信 / 光模块"}],
            "signal_strength": signal_strength,
            "status": status,
        }

    def _make_direction_map(self, leader_ticker="300308", hb_ticker="300394"):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": leader_ticker, "name": "中际旭创", "in_universe": True}],
                "high_beta_names": [{"ticker": hb_ticker, "name": "天孚通信", "in_universe": True}],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]

    def _make_candidate(self, ticker="300308", score=50.0, matched_themes=None):
        return {
            "ticker": ticker,
            "name": "中际旭创",
            "score": score,
            "adjusted_total_score": score,
            "matched_themes": matched_themes or [],
            "tier_tags": [],
        }

    def test_theme_alignment_boost_high_signal(self):
        """Theme match + high signal → +3."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 0)

    def test_theme_alignment_boost_medium_signal(self):
        """Theme match + medium signal → +1."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("medium"),
        )
        self.assertEqual(result[0]["direction_boost"]["theme_delta"], 1)

    def test_reference_map_leader_boost(self):
        """Leader ticker match → +6."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["direction_role"], "leader")

    def test_reference_map_high_beta_boost(self):
        """High-beta ticker match → +4."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300394", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 4)
        self.assertEqual(boost["direction_role"], "high_beta")

    def test_leader_and_theme_boost_stack(self):
        """Both match → +3 + +6 = +9."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0, matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["total_delta"], 9)
        self.assertEqual(result[0]["adjusted_total_score"], 59.0)

    def test_no_boost_when_insufficient_signal(self):
        """Direction status insufficient → candidates unchanged."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        wmc = self._make_weekend_candidate(status="insufficient_signal")
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), wmc,
        )
        self.assertNotIn("direction_boost", result[0])
        self.assertEqual(result[0]["adjusted_total_score"], 50.0)

    def test_no_boost_when_no_direction(self):
        """weekend_market_candidate is None → no-op."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        result = runtime.direction_alignment_boost([cand], [], None)
        self.assertNotIn("direction_boost", result[0])


class DirectionTierPromotionTests(unittest.TestCase):
    """Spec Section 3: direction-based tier promotion."""

    def _make_weekend_candidate(self, signal_strength="high"):
        return {
            "candidate_topics": [{"topic_name": "optical_interconnect", "topic_label": "光通信 / 光模块"}],
            "signal_strength": signal_strength,
            "status": "candidate_only",
        }

    def _make_direction_map(self):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": "300308", "name": "中际旭创", "in_universe": True}],
                "high_beta_names": [{"ticker": "300394", "name": "天孚通信", "in_universe": True}],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]

    def _make_tiered(self, t1_count=3, t2_count=2, t3_count=2):
        tiers = {"T1": [], "T2": [], "T3": [], "T4": []}
        for i in range(t1_count):
            tiers["T1"].append({"ticker": f"T1_{i:03d}", "name": f"T1股{i}", "tier_tags": [], "wrapper_tier": "T1"})
        for i in range(t2_count):
            tiers["T2"].append({"ticker": f"T2_{i:03d}", "name": f"T2股{i}", "tier_tags": [], "wrapper_tier": "T2"})
        for i in range(t3_count):
            tiers["T3"].append({"ticker": f"T3_{i:03d}", "name": f"T3股{i}", "tier_tags": [], "wrapper_tier": "T3"})
        return tiers

    def test_tier_promotion_t2_to_t1_leader(self):
        """Leader in T2 promoted to T1 when T1 < 10."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=3, t2_count=2)
        tiers["T2"].append({"ticker": "300308", "name": "中际旭创", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        result = runtime.direction_tier_promotion(tiers, self._make_direction_map(), self._make_weekend_candidate())
        t1_tickers = [c["ticker"] for c in result["T1"]]
        self.assertIn("300308", t1_tickers)
        promoted = [c for c in result["T1"] if c["ticker"] == "300308"][0]
        self.assertIn("direction_promoted", promoted["tier_tags"])

    def test_tier_promotion_respects_cap(self):
        """No promotion when T1 is full (10)."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=10, t2_count=2)
        tiers["T2"].append({"ticker": "300308", "name": "中际旭创", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        result = runtime.direction_tier_promotion(tiers, self._make_direction_map(), self._make_weekend_candidate())
        t1_tickers = [c["ticker"] for c in result["T1"]]
        self.assertNotIn("300308", t1_tickers)

    def test_tier_promotion_max_2_per_run(self):
        """Third promotion blocked by max-2 cap."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=3, t2_count=0)
        for i, ticker in enumerate(["300308", "300394", "300999"]):
            tiers["T2"].append({"ticker": ticker, "name": f"Stock{i}", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        drm = [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "300308", "name": "A", "in_universe": True},
                    {"ticker": "300394", "name": "B", "in_universe": True},
                    {"ticker": "300999", "name": "C", "in_universe": True},
                ],
                "high_beta_names": [],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]
        result = runtime.direction_tier_promotion(tiers, drm, self._make_weekend_candidate())
        promoted_count = sum(1 for c in result["T1"] if "direction_promoted" in c.get("tier_tags", []))
        self.assertEqual(promoted_count, 2)


class ConfirmationGateBypassTests(unittest.TestCase):
    """Spec Section 4: confirmation gate bypass for direction-aligned candidates."""

    def _base_candidate(self, **overrides):
        base = {
            "ticker": "300308",
            "name": "中际旭创",
            "keep": True,
            "score": 58.0,
            "keep_threshold_gap": 1.5,  # marginal — would normally trigger gate
            "midday_status": "qualified",
            "midday_action": "可执行",
            "structured_catalyst_score": 15.0,
            "execution_state": "live",
            "hard_filter_failures": [],
            "tier_tags": ["direction_leader"],
            "direction_boost": {
                "signal_strength": "high",
                "direction_key": "optical_interconnect",
            },
        }
        base.update(overrides)
        return base

    def test_gate_bypass_for_direction_leader_high_signal(self):
        """Direction leader + high signal → stays 可执行 despite marginal gap."""
        import month_end_shortlist_runtime as runtime

        cand = self._base_candidate()
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "可执行")

    def test_gate_bypass_blocked_by_review_force_gate(self):
        """review_force_gate overrides direction bypass → gate triggers."""
        import month_end_shortlist_runtime as runtime

        cand = self._base_candidate(review_force_gate=True)
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")


class MomentumProxyTests(unittest.TestCase):
    """Spec Section 5: postclose review as momentum proxy."""

    def _make_review_output(self, candidates_reviewed):
        return {
            "trade_date": "2026-04-21",
            "candidates_reviewed": candidates_reviewed,
            "summary": {},
            "prior_review_adjustments": [],
        }

    def test_momentum_confirmed_full_boost(self):
        """>=50% correct, zero too_aggressive → confirmed."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
            {"ticker": "300394", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "high_beta"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "confirmed")
        self.assertEqual(entry["aligned_correct"], 2)
        self.assertEqual(entry["aligned_too_aggressive"], 0)

    def test_momentum_caution_halves_boost(self):
        """Any too_aggressive among aligned → caution."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
            {"ticker": "300394", "judgment": "plan_too_aggressive", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "high_beta"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "caution")

    def test_momentum_fading_zeros_boost(self):
        """All aligned are correct_negative → fading."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct_negative", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "fading")


class DecisionFlowCardDirectionTests(unittest.TestCase):
    """Spec Section 6: decision flow card direction labels."""

    def test_decision_flow_card_direction_labels(self):
        """Card contains direction labels when direction_boost is present."""
        import month_end_shortlist_runtime as runtime

        factor = {
            "ticker": "300308",
            "name": "中际旭创",
            "action": "可执行",
            "score": 58.0,
            "keep_threshold_gap": 5.0,
            "tier_tags": ["direction_leader", "direction_theme_aligned", "direction_promoted"],
            "direction_boost": {
                "theme_delta": 3,
                "reference_delta": 6,
                "total_delta": 9,
                "direction_key": "optical_interconnect",
                "direction_role": "leader",
                "signal_strength": "high",
                "momentum_signal": "confirmed",
            },
            "wrapper_tier": "T1",
            "original_tier": "T2",
        }
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=53.0, event_card=None, chain_entry=None,
        )
        card_str = str(card)
        self.assertIn("方向层加分", card_str)
        self.assertIn("方向信号强度", card_str)


if __name__ == "__main__":
    unittest.main()
