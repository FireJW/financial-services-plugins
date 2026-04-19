# Geopolitics Regime Overlay Design

**Date:** 2026-04-18  
**Status:** Phase 1 approved design  
**Scope:** `month-end-shortlist` wrapper/runtime layer only

## 1. Goal

Add a lightweight `macro_geopolitics_overlay` to the existing shortlist and trade-plan pipeline so recurring geopolitical tension, especially the US-Iran / Strait of Hormuz / oil-risk context, can influence:

- shortlist observation-layer ranking
- chain/theme bias
- execution constraints in the final trade plan

without replacing stock-specific structure, catalyst, and validation as the primary driver.

The target behavior is:

- `T1` remains primarily stock-driven
- `T3/T4` become more context-aware
- the final report explicitly explains how the current geopolitical regime changes bias and execution posture

## 2. Phase 1 Boundary

Phase 1 is intentionally narrow.

Included:

- manual or semi-structured regime input from the request payload
- three regime states:
  - `escalation`
  - `de_escalation`
  - `whipsaw`
- lightweight score bias
- ranking bias
- execution constraints / risk notes

Excluded:

- automatic regime inference from headlines, X, oil futures, or shipping data
- direct rewriting of compiled shortlist core logic
- any rule that allows the overlay alone to create a new `T1` candidate
- board-specific geopolitical logic beyond normal board-aware shortlist behavior

## 3. Design Principle

This overlay is **balanced**, not dominant.

That means:

- it can tilt borderline names
- it can reorder observation candidates
- it can tighten or loosen execution posture
- it cannot, by itself, overrule a structurally weak stock into `T1`

The overlay is treated as a **regime bias layer**, not a standalone stock selector.

## 4. Regime States

Phase 1 uses a discrete three-state regime model.

### 4.1 `escalation`

Use when the market is repricing conflict expansion, shipping disruption risk, oil-supply uncertainty, or a broader flight-to-safety posture.

Expected bias:

- beneficiary chains get a mild positive tilt
- headwind chains get a mild negative tilt
- execution constraints become stricter
- overnight / headline reversal warnings become more prominent

### 4.2 `de_escalation`

Use when talks, reopening, ceasefire-like behavior, or reduced disruption risk support lower oil risk premium and stronger risk appetite.

Expected bias:

- growth / risk-on chains can recover ranking
- defensive / crisis-beta trades lose urgency
- execution constraints may loosen slightly

### 4.3 `whipsaw`

Use when the market is alternating rapidly between escalation and de-escalation signals and headline reversals dominate tape behavior.

Expected bias:

- ranking shifts become smaller and more defensive
- execution constraints become the most important output
- reports should emphasize:
  - smaller size
  - no aggressive chasing
  - headline reversal risk
  - lower confidence in overnight holding

## 5. Request Contract

Phase 1 introduces a new optional request field:

```json
{
  "macro_geopolitics_overlay": {
    "regime_label": "escalation",
    "confidence": "medium",
    "headline_risk": "high",
    "beneficiary_chains": ["oil_shipping", "energy", "gold", "defense"],
    "headwind_chains": ["airlines", "cost_sensitive_chemicals", "export_chain", "high_beta_growth"],
    "notes": "Hormuz disruption risk repriced; market sensitive to headline reversals."
  }
}
```

### 5.1 Required in Phase 1

- `regime_label`

### 5.2 Optional

- `confidence`
- `headline_risk`
- `beneficiary_chains`
- `headwind_chains`
- `notes`

### 5.3 Validation Rules

- unknown or missing overlay should behave as “overlay absent”
- unknown chain names should be ignored, not error
- invalid `regime_label` should downgrade to “overlay absent”

## 6. Phase 1 Chain Coverage

Phase 1 supports a wider but still curated chain map.

### 6.1 Beneficiary Chains

- `oil_shipping`
- `energy`
- `gold`
- `defense`

### 6.2 Headwind Chains

- `cost_sensitive_chemicals`
- `airlines`
- `export_chain`
- `high_beta_growth`

These names are canonical overlay categories. Existing chain/theme aliases in the current runtime can map into them later, but Phase 1 should not depend on a fully automated alias expansion pipeline.

## 7. Where It Should Apply

### 7.1 Score Bias

Apply a mild overlay adjustment in wrapper space only.

Recommended Phase 1 behavior:

- beneficiary chain candidate: small positive bias
- headwind chain candidate: small negative bias
- neutral chain candidate: no bias

The exact value can be simple and deterministic in Phase 1, for example:

- `+1 to +2` equivalent observation bias for beneficiary chains in `escalation`
- `-1 to -2` equivalent observation bias for headwind chains in `escalation`
- mirrored behavior for `de_escalation`
- smaller absolute bias in `whipsaw`

This is intentionally a **wrapper-side bias**, not a replacement for score components in compiled core.

### 7.2 Ranking Bias

The main target is observation-layer ordering.

Expected result:

- `T3/T4` ordering becomes regime-aware
- borderline names in favored chains rise in the watch stack
- names in pressured chains fall lower unless stock-specific evidence is clearly stronger

### 7.3 Execution Constraints

The overlay must affect the final plan text directly.

Examples:

- `escalation`
  - smaller size
  - avoid chasing after headline spikes
  - stronger overnight caution
- `de_escalation`
  - less crisis-beta urgency
  - better tolerance for risk-on setups
- `whipsaw`
  - prioritize confirmed follow-through only
  - no aggressive gap-chasing
  - high headline reversal warning

## 8. What It Must Not Do

Phase 1 must not:

- promote a candidate into `T1` solely due to geopolitical context
- override hard failures
- bypass existing board-aware threshold logic
- duplicate the separate `macro_health_overlay` with a generic risk-on/risk-off abstraction

`macro_geopolitics_overlay` is narrower and more event-regime specific than `macro_health_overlay`.

## 9. Runtime Integration Points

Phase 1 should stay in wrapper/runtime space and avoid compiled core changes.

Primary integration targets:

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

Likely touch points:

- request normalization / overlay extraction
- ranking and tier ordering after track enrichment
- decision factor generation
- decision flow card generation
- report markdown synthesis

Secondary integration options:

- existing macro-assisted entrypoints, if they need to pass the overlay through cleanly

## 10. Report Output Changes

The final report should surface the overlay explicitly without making it the dominant section.

Phase 1 additions should include:

- regime label in the summary/meta layer
- chain bias explanation for affected observation names
- execution constraint text in the trade-plan card

### 10.1 Desired User-Facing Behavior

The report should read like:

- “This name was already on the observation layer, and the current geopolitical regime lifts/suppresses its priority.”

not:

- “This stock is selected because of geopolitics alone.”

## 11. Interaction With Existing Layers

This overlay should sit alongside, not replace:

- `macro_health_overlay`
- board-aware shortlist thresholds
- discovery/event-card logic
- trading profile and decision-flow synthesis

Recommended mental model:

1. stock-specific structure and event evidence form the base case
2. geopolitical overlay tilts observation-layer order and execution posture
3. final report explains both

## 12. Testing Strategy

Phase 1 tests should prove:

1. request normalization safely accepts `macro_geopolitics_overlay`
2. beneficiary chains receive the intended mild positive bias
3. headwind chains receive the intended mild negative bias
4. `whipsaw` applies more execution caution than outright ranking aggression
5. `T1` is not created purely by overlay bias
6. report markdown clearly shows:
   - regime
   - bias
   - execution constraint

Primary likely test files:

- `tests/test_month_end_shortlist_degraded_reporting.py`
- `tests/test_screening_coverage_optimization.py`
- `tests/test_board_threshold_overrides.py`

## 13. Phase 2 Direction

If Phase 1 works, the next expansion can be:

- semi-automatic regime construction from news/X/oil/shipping inputs
- chain alias mapping expansion
- more refined chain-level bias tables
- integration with scenario-specific plan templates

Phase 2 should remain a separate design cycle.

## 14. Implementation Recommendation

Use a Phase 1 implementation that is:

- deterministic
- wrapper-only
- easy to test
- small enough to revert if it proves too noisy

Success for Phase 1 is not perfect geopolitical prediction.

Success means:

- the shortlist and trade plan stop treating repeated geopolitical tape as invisible
- the effect is visible in observation ranking and execution posture
- `T1` discipline remains intact
