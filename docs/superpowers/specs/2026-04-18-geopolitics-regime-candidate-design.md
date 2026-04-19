# Geopolitics Regime Candidate Design

**Date:** 2026-04-18  
**Status:** Phase 2 approved design  
**Scope:** `month-end-shortlist` wrapper/runtime layer only

## 1. Goal

Add a Phase 2 `macro_geopolitics_candidate` layer ahead of the existing
`macro_geopolitics_overlay` so the system can synthesize a regime candidate from
mixed news, X, and market signals without directly rewriting shortlist behavior.

The target behavior is:

- mixed geopolitical inputs can be normalized into one evidence model
- the runtime can output a deterministic candidate regime or
  `insufficient_signal`
- the candidate remains advisory until explicitly accepted as a formal overlay
- the current Phase 1 shortlist path stays intact and stable

## 2. Phase 2 Boundary

Included:

- a new optional request block:
  - `macro_geopolitics_candidate_input`
- a new derived result block:
  - `macro_geopolitics_candidate`
- mixed input support for:
  - structured news summaries
  - structured X summaries
  - limited raw links / raw posts with short notes
  - structured market signals
- evidence-block synthesis
- deterministic rule-weighted regime inference
- lightweight report surfacing of the candidate

Excluded:

- automatic writing of the candidate into `macro_geopolitics_overlay`
- direct shortlist impact from the candidate alone
- LLM-first candidate inference
- fully automatic extraction from arbitrary raw URLs without an upstream summary
- Phase 3 acceptance automation

## 3. Design Principle

Phase 2 adds a **candidate judgment layer**, not a second overlay.

The runtime will now distinguish between:

1. `macro_geopolitics_candidate_input`
   - raw or semi-structured multi-source inputs
2. `macro_geopolitics_candidate`
   - synthesized candidate output
3. `macro_geopolitics_overlay`
   - the only formal overlay that can influence shortlist ranking and execution

This separation is mandatory. Phase 2 is successful only if candidate synthesis
becomes more informative without making shortlist behavior less predictable.

## 4. Candidate Output Contract

Phase 2 adds a new derived result block:

```json
{
  "macro_geopolitics_candidate": {
    "candidate_regime": "escalation",
    "confidence": "medium",
    "signal_alignment": "news+x+market",
    "status": "candidate_only",
    "evidence_summary": [
      "Shipping disruption headlines point to escalation.",
      "X discussion remains biased toward supply-risk repricing.",
      "Oil and gold are confirming while airlines lag."
    ],
    "beneficiary_bias": ["oil_shipping", "energy", "gold", "defense"],
    "headwind_bias": ["airlines", "cost_sensitive_chemicals", "high_beta_growth"]
  }
}
```

Allowed `candidate_regime` values:

- `escalation`
- `de_escalation`
- `whipsaw`
- `insufficient_signal`

Allowed `status` values:

- `candidate_only`
- `accepted_as_overlay`
- `conflicts_with_overlay`
- `insufficient_signal`

## 5. Input Contract

Phase 2 introduces:

```json
{
  "macro_geopolitics_candidate_input": {
    "news_signals": [...],
    "x_signals": [...],
    "market_signals": {...}
  }
}
```

### 5.1 News Signals

News entries may be:

- structured summaries
- or raw links plus a short human note

Preferred fields:

- `source`
- `headline`
- `summary`
- `direction_hint`
- `timestamp`
- `url` (optional)

### 5.2 X Signals

X entries may be:

- structured summaries
- or raw post links / copied post snippets plus a short note

Preferred fields:

- `account`
- `url`
- `summary`
- `direction_hint`
- `timestamp`

### 5.3 Market Signals

Market signals should be structured in Phase 2.

Supported families:

- `oil`
- `gold`
- `shipping`
- `risk_style`
- `usd_rates`
- `airlines`
- `industrials`

Preferred values are directional, not raw time series, for example:

- `up / down / flat`
- `risk_on / risk_off / mixed`
- `tightening / loosening / mixed`

## 6. Evidence Block Synthesis

Before scoring, heterogeneous inputs must be normalized into a single internal
evidence model:

- `news_evidence`
- `x_evidence`
- `market_evidence`

Each evidence row should be normalized to a structure like:

```json
{
  "source_type": "news",
  "signal_family": "shipping_disruption_risk",
  "direction": "escalation",
  "strength": "medium",
  "summary": "Hormuz disruption risk repriced in shipping headlines.",
  "timestamp": "2026-04-18T09:30:00+08:00"
}
```

Required normalized fields:

- `source_type`
- `signal_family`
- `direction`
- `strength`
- `summary`

Optional:

- `timestamp`
- `source_ref`

Invalid or incomplete raw entries should be ignored rather than treated as
errors.

## 7. Rule Engine

Phase 2 uses deterministic rule-weighted scoring, not LLM-first inference.

The rule engine maintains three score buckets:

- `escalation_score`
- `de_escalation_score`
- `whipsaw_score`

Each normalized evidence row contributes to one or more buckets based on:

- `source_type`
- `signal_family`
- `direction`
- `strength`

### 7.1 Directional Mapping

Examples:

- shipping disruption risk, supply interruption, conflict expansion
  - contributes to `escalation_score`
- talks, reopening, resumed transit, risk premium unwind
  - contributes to `de_escalation_score`
- rapid headline reversals, cross-source contradiction, market/news mismatch
  - contributes to `whipsaw_score`

### 7.2 Strength Mapping

Phase 2 should use small, discrete weights, for example:

- `low = 1`
- `medium = 2`
- `high = 3`

No hidden heuristics are needed in Phase 2.

## 8. Conservative Output Rule

Phase 2 must prefer no-call over noisy calls.

### 8.1 Minimum Signal Alignment Requirement

A formal candidate regime may only be emitted when at least two signal classes
align in the same direction:

- `news + x`
- `news + market`
- `x + market`

If that requirement is not met, output:

- `candidate_regime = insufficient_signal`

### 8.2 Regime Margin Requirement

The top regime score must exceed the second score by a minimum margin.

If the top score does not clearly lead, output:

- `candidate_regime = insufficient_signal`

Phase 2 should not force a weak `whipsaw` call as a fallback default.

### 8.3 Whipsaw Rule

`whipsaw` should only be emitted when evidence shows genuine cross-source
conflict or rapid reversal characteristics, such as:

- headlines and market signals diverging materially
- news/X direction flipping inside the same decision window
- oil, gold, shipping, and risk-style signals not confirming the same story

`whipsaw` is not a garbage bucket for uncertainty.

## 9. Integration With Phase 1 Overlay

Phase 2 must not auto-write into `macro_geopolitics_overlay`.

The valid flow is:

1. user or upstream system provides `macro_geopolitics_candidate_input`
2. runtime builds `macro_geopolitics_candidate`
3. user or higher-level workflow decides whether to accept the candidate
4. only accepted overlay data is written into `macro_geopolitics_overlay`
5. shortlist ranking and execution constraints continue to consume only the
   formal overlay

This means:

- candidate generation is advisory
- overlay remains the sole formal shortlist input
- Phase 1 behavior remains reproducible and isolated

## 10. Report Behavior

Phase 2 should surface the candidate lightly, not as a new dominant section.

### 10.1 Summary Layer

The report may add a short candidate summary near the report meta block, for
example:

- `地缘候选判断：escalation（medium）`
- `信号对齐：news + X + market`
- `状态：候选判断，尚未写入正式 overlay`

### 10.2 Card Layer

Individual stock cards may reference candidate bias only when relevant, for
example:

- `地缘候选偏置：受益链条，优先级上调`
- `地缘候选偏置：承压链条，追高约束更强`

Do not repeat the entire candidate explanation on every card.

### 10.3 Supporting Block

If a dedicated supporting block is shown, it should remain short and include
only:

- `candidate_regime`
- `confidence`
- `signal_alignment`
- `top evidence`
- `status`

## 11. No-Regression Constraints

Phase 2 must not:

- change `T1` membership directly
- silently convert candidate output into overlay input
- displace the current dual-mode trade report structure
- turn report output back into a macro essay

The candidate should increase judgment transparency, not increase report weight.

## 12. Testing Strategy

Phase 2 tests must cover:

1. candidate-input normalization
2. evidence-block synthesis from mixed input shapes
3. deterministic regime scoring
4. conservative fallback to `insufficient_signal`
5. explicit proof that candidate does not auto-become overlay
6. lightweight report surfacing

Primary likely test files:

- `tests/test_month_end_shortlist_profile_passthrough.py`
- `tests/test_screening_coverage_optimization.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`

## 13. Success Criteria

Phase 2 is successful if:

- the system can turn mixed geopolitical inputs into a single candidate block
- the candidate can clearly distinguish:
  - `escalation`
  - `de_escalation`
  - `whipsaw`
  - `insufficient_signal`
- the candidate remains separate from the formal overlay
- the report makes the candidate visible without letting it dominate the trade
  plan

## 14. Phase 3 Direction

If Phase 2 proves useful, the next design cycle can consider:

- semi-automatic acceptance from candidate to overlay
- richer alias mapping for beneficiary/headwind chains
- stronger upstream extraction from raw links/posts
- scenario-template integration in the final trade plan

Those are Phase 3 concerns and should not be folded into this Phase 2 design.
