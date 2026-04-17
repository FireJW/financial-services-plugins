#!/usr/bin/env python3
"""Tests for article_revise_flow_runtime: red team, rewrite, rebuild, reorder."""
from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_revise_flow_runtime import (
    build_red_team_review,
    collect_non_core_promoted_claims,
    derive_persist_feedback,
    has_boundary_language,
    reorder_candidates,
    request_needs_package_rebuild,
    rewrite_request_after_attack,
)
from article_draft_flow_runtime import clean_text, safe_dict, safe_list


# ── helpers ──


def _article_package(**overrides: Any) -> dict:
    base: dict[str, Any] = {
        "title": "Test Article",
        "lede": "This is a test lede about confirmed facts.",
        "sections": [
            {"heading": "Background", "paragraph": "Some background text. Not confirmed yet."},
        ],
        "draft_claim_map": [],
        "selected_images": [],
        "writer_risk_notes": [],
    }
    base.update(overrides)
    return base


def _analysis_brief(**overrides: Any) -> dict:
    base: dict[str, Any] = {
        "canonical_facts": [{"claim_text": "GDP grew 3%"}],
        "not_proven": [],
        "story_angles": [{"angle": "Risk-off"}],
        "misread_risks": [],
    }
    base.update(overrides)
    return base


def _source_summary(**overrides: Any) -> dict:
    base: dict[str, Any] = {"blocked_source_count": 0}
    base.update(overrides)
    return base


# ── build_red_team_review ──


class TestBuildRedTeamReview(unittest.TestCase):

    def test_clean_pass_no_attacks(self) -> None:
        """No attacks → quality_gate = pass."""
        review = build_red_team_review(
            _article_package(
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "Markets are cautious.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        self.assertEqual(review["quality_gate"], "pass")
        self.assertEqual(len(review["attacks"]), 0)

    def test_shadow_single_source_thesis_triggers_block(self) -> None:
        """Thesis backed by a single shadow citation → critical → block."""
        review = build_red_team_review(
            _article_package(
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "Rate cut is imminent.",
                        "support_level": "shadow-heavy",
                        "citation_ids": ["cit-shadow"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[{"citation_id": "cit-shadow", "channel": "shadow"}],
            images=[],
        )
        self.assertEqual(review["quality_gate"], "block")
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("shadow-single-source-thesis", attack_ids)

    def test_uncited_promoted_claims_thesis_is_critical(self) -> None:
        """Uncited thesis → critical severity."""
        review = build_red_team_review(
            _article_package(
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "Markets will crash.",
                        "support_level": "core",
                        "citation_ids": [],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("uncited-promoted-claims", attack_ids)
        uncited = [a for a in review["attacks"] if a["attack_id"] == "uncited-promoted-claims"][0]
        self.assertEqual(uncited["severity"], "critical")

    def test_uncited_promoted_non_thesis_is_major(self) -> None:
        """Uncited non-thesis promoted claim → major severity."""
        review = build_red_team_review(
            _article_package(
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK thesis.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    },
                    {
                        "claim_label": "supporting",
                        "claim_text": "Uncited claim.",
                        "support_level": "core",
                        "citation_ids": [],
                    },
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        uncited = [a for a in review["attacks"] if a["attack_id"] == "uncited-promoted-claims"]
        self.assertEqual(len(uncited), 1)
        self.assertEqual(uncited[0]["severity"], "major")

    def test_non_core_promoted_claims_attack(self) -> None:
        """Promoted claim backed only by shadow citations → major."""
        review = build_red_team_review(
            _article_package(
                draft_claim_map=[
                    {
                        "claim_label": "supporting",
                        "claim_text": "Shadow-backed claim.",
                        "support_level": "core",
                        "citation_ids": ["cit-s"],
                    },
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[{"citation_id": "cit-s", "channel": "shadow"}],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("non-core-promoted-claims", attack_ids)

    def test_missing_boundary_language_attack(self) -> None:
        """Unresolved claims exist but article lacks boundary markers → major."""
        review = build_red_team_review(
            _article_package(
                lede="Everything is confirmed and settled.",
                sections=[{"heading": "H", "paragraph": "All facts are clear."}],
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(not_proven=[{"claim_text": "Rate cut likely"}]),
            _source_summary(),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("missing-boundary-language", attack_ids)

    def test_boundary_language_present_no_attack(self) -> None:
        """Boundary markers present → no missing-boundary-language attack."""
        review = build_red_team_review(
            _article_package(
                lede="This is not confirmed yet. Inference only.",
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(not_proven=[{"claim_text": "Rate cut likely"}]),
            _source_summary(),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertNotIn("missing-boundary-language", attack_ids)

    def test_blocked_sources_hidden_attack(self) -> None:
        """Blocked sources exist but article doesn't mention them."""
        review = build_red_team_review(
            _article_package(
                lede="All sources are fine.",
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(blocked_source_count=2),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("blocked-sources-hidden", attack_ids)

    def test_blocked_sources_disclosed_no_attack(self) -> None:
        """Blocked sources mentioned → no blocked-sources-hidden attack."""
        review = build_red_team_review(
            _article_package(
                lede="Some sources were blocked or inaccessible.",
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(blocked_source_count=2),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertNotIn("blocked-sources-hidden", attack_ids)

    def test_visual_overreach_attack(self) -> None:
        """Location overreach markers + shadow images → critical."""
        review = build_red_team_review(
            _article_package(
                lede="The carrier is confirmed position near the strait.",
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[{"image_id": "img-1", "access_mode": "blocked", "source_tier": 3}],
        )
        attack_ids = {a["attack_id"] for a in review["attacks"]}
        self.assertIn("visual-overreach", attack_ids)

    def test_quality_gate_revise_for_major_only(self) -> None:
        """Only major attacks (no critical) → quality_gate = revise."""
        review = build_red_team_review(
            _article_package(
                lede="All facts are clear.",
                draft_claim_map=[
                    {
                        "claim_label": "thesis",
                        "claim_text": "OK.",
                        "support_level": "core",
                        "citation_ids": ["cit-1"],
                    }
                ],
            ),
            _analysis_brief(),
            _source_summary(blocked_source_count=1),
            citations=[{"citation_id": "cit-1", "channel": "core"}],
            images=[],
        )
        self.assertEqual(review["quality_gate"], "revise")


# ── has_boundary_language ──


class TestHasBoundaryLanguage(unittest.TestCase):

    def test_english_markers(self) -> None:
        self.assertTrue(has_boundary_language("This is not confirmed yet."))
        self.assertTrue(has_boundary_language("The claim remains unclear."))
        self.assertTrue(has_boundary_language("This is inference only."))
        self.assertTrue(has_boundary_language("It is not proven that rates will fall."))

    def test_chinese_markers(self) -> None:
        self.assertTrue(has_boundary_language("这一说法未证实。"))
        self.assertTrue(has_boundary_language("目前情况不明确。"))
        self.assertTrue(has_boundary_language("这只是推断。"))

    def test_no_markers(self) -> None:
        self.assertFalse(has_boundary_language("Everything is settled and confirmed."))
        self.assertFalse(has_boundary_language(""))


# ── reorder_candidates ──


class TestReorderCandidates(unittest.TestCase):

    def _candidates(self) -> list[dict]:
        return [
            {"image_id": "a", "score": 10},
            {"image_id": "b", "score": 20},
            {"image_id": "c", "score": 30},
            {"image_id": "d", "score": 40},
        ]

    def test_keep_ids_move_to_front(self) -> None:
        result = reorder_candidates(self._candidates(), keep_image_ids=["c"], drop_image_ids=[])
        self.assertEqual(result[0]["image_id"], "c")

    def test_drop_ids_removed(self) -> None:
        result = reorder_candidates(self._candidates(), keep_image_ids=[], drop_image_ids=["b"])
        ids = [item["image_id"] for item in result]
        self.assertNotIn("b", ids)
        self.assertEqual(len(result), 3)

    def test_keep_and_drop_combined(self) -> None:
        result = reorder_candidates(self._candidates(), keep_image_ids=["d"], drop_image_ids=["a"])
        ids = [item["image_id"] for item in result]
        self.assertEqual(ids[0], "d")
        self.assertNotIn("a", ids)

    def test_empty_lists_preserve_order(self) -> None:
        result = reorder_candidates(self._candidates(), keep_image_ids=[], drop_image_ids=[])
        ids = [item["image_id"] for item in result]
        self.assertEqual(ids, ["a", "b", "c", "d"])


# ── request_needs_package_rebuild ──


class TestRequestNeedsPackageRebuild(unittest.TestCase):

    def test_identical_requests_no_rebuild(self) -> None:
        req = {"language_mode": "english", "draft_mode": "balanced", "max_images": 3}
        self.assertFalse(request_needs_package_rebuild(req, deepcopy(req)))

    def test_changed_language_mode_triggers_rebuild(self) -> None:
        old = {"language_mode": "english"}
        new = {"language_mode": "chinese"}
        self.assertTrue(request_needs_package_rebuild(new, old))

    def test_changed_draft_mode_triggers_rebuild(self) -> None:
        old = {"draft_mode": "balanced"}
        new = {"draft_mode": "image_first"}
        self.assertTrue(request_needs_package_rebuild(new, old))

    def test_keep_image_ids_trigger_rebuild(self) -> None:
        req = {"feedback": {"keep_image_ids": ["img-1"]}}
        self.assertTrue(request_needs_package_rebuild(req, {}))


# ── derive_persist_feedback ──


class TestDerivePersistFeedback(unittest.TestCase):

    def test_explicit_scope_used(self) -> None:
        result = derive_persist_feedback(
            {"scope": "global", "defaults": {"tone": "cautious"}},
            {},
        )
        self.assertEqual(result["scope"], "global")

    def test_none_scope_falls_through_to_auto(self) -> None:
        result = derive_persist_feedback(
            {"scope": "none"},
            {"reusable_preferences": [{"key": "tone", "value": "cautious", "reuse_scope": "topic"}]},
        )
        # Should auto-derive from reusable_preferences
        self.assertIn("scope", result)

    def test_empty_inputs(self) -> None:
        result = derive_persist_feedback({}, {})
        self.assertEqual(result["scope"], "none")


# ── rewrite_request_after_attack ──


class TestRewriteRequestAfterAttack(unittest.TestCase):

    def test_adds_must_include_from_not_proven(self) -> None:
        request = {"language_mode": "english"}
        brief = {"not_proven": [{"claim_text": "Rate cut likely"}]}
        review = {"attacks": [{"attack_id": "missing-boundary-language"}]}
        result = rewrite_request_after_attack(request, brief, review)
        self.assertIn("must_include", result)
        self.assertTrue(any("not proven" in item.lower() or "rate cut" in item.lower() for item in result["must_include"]))

    def test_preserves_existing_must_include(self) -> None:
        request = {"language_mode": "english", "must_include": ["Keep this"]}
        brief = {"not_proven": [{"claim_text": "Unresolved"}]}
        review = {"attacks": [{"attack_id": "missing-boundary-language"}]}
        result = rewrite_request_after_attack(request, brief, review)
        self.assertIn("Keep this", result["must_include"])

    def test_red_team_applied_flag_set(self) -> None:
        request = {"language_mode": "english"}
        brief = {"not_proven": []}
        review = {"attacks": [{"attack_id": "blocked-sources-hidden"}]}
        result = rewrite_request_after_attack(request, brief, review)
        self.assertTrue(result.get("red_team_applied"))


if __name__ == "__main__":
    unittest.main()
