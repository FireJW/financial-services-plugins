# Setup Launch Phase 2 Quality Upgrade Design

**Date:** 2026-04-21  
**Status:** Approved design  
**Scope:** Upgrade the quality of `setup_launch_candidates` detection so the
lane can better distinguish true bottom-completion / early-launch setups from
pure bottom drift and already-extended strength.

## 1. Goal

Phase 1 already solved a visibility problem:

- the system can now surface a dedicated `筑底启动补充` lane
- the lane is theme-aware
- the lane does not pollute `T1` / `T2`

Phase 2 should solve a quality problem:

- improve the precision of what counts as a true early-launch setup
- reduce weak false positives
- reduce accidental inclusion of already-extended names
- keep the lane explainable and lightweight

This is a scoring and setup-detection upgrade, not a redesign of the shortlist
architecture.

## 2. Current Weaknesses

The current Phase 1 implementation is intentionally simple, but that simplicity
creates several weak spots.

### 2.1 Structure repair is too coarse

Current logic is close to:

- `close > ma20 > ma50` => high
- `close > ma20` => medium
- fallback to `pct_from_60d` and positive day move

This is enough to find obvious improvements, but not enough to distinguish:

- one-day reclaim
- genuine base repair

### 2.2 Volume return is static-threshold based

Current logic uses static thresholds such as:

- `volume_ratio`
- `turnover_rate_pct`
- `day_turnover_cny`

This can identify active names, but it does not really answer:

- is volume returning relative to the prior quiet base

### 2.3 RS improvement is still approximated by absolute level

Current `rs_improvement` is still largely inferred from:

- `rs90`
- `pct_from_ytd`
- positive day move

That is still too close to a later-stage strength framework.

### 2.4 Distance state is useful but too shallow

Current states:

- `still_bottoming`
- `off_bottom_not_extended`
- `too_extended`

This is directionally correct, but it still does not separate:

- clean early extension
- already over-pushed extension

## 3. Phase 2 Boundary

Phase 2 should only improve the quality of setup detection.

It must not:

- redesign the main event-driven shortlist engine
- change `keep_threshold`
- change `strict_top_pick_threshold`
- allow direct `T1` / `T2` promotion
- add machine learning or large historical modeling
- replace `market_strength_candidates`

This remains a supplement lane.

## 4. Design Principle

Keep the current lane shape:

- `setup_launch_candidates`
- `strategic_base_watch_themes`
- `筑底启动补充`

Only upgrade:

- structure classification
- volume-return classification
- RS-improvement classification
- distance-from-bottom classification
- scoring weights and setup reasons

This keeps Phase 2 bounded and reversible.

## 5. Phase 2 Detection Upgrades

### 5.1 Better structure-repair judgment

Replace the current binary-style reclaim logic with a more stage-aware signal.

Phase 2 should incorporate signals such as:

- `close > ma20`
- `close > ma50`
- `ma20` is higher than its recent value
- recent swing lows are no longer falling
- price is not merely bouncing inside a still-broken structure

Target behavior:

- single-day reclaim with no follow-through should not score as strongly as
  sustained repair
- sustained reclaim + rising short moving average should score higher

### 5.2 Better volume-return judgment

Phase 2 should stop treating raw turnover thresholds as the main answer.

Instead, it should compare:

- recent `3-5` session participation
- versus the immediately prior quiet / compressed window

Examples of acceptable Phase 2 logic:

- recent average turnover > prior base-window average turnover by a meaningful ratio
- recent average volume ratio > prior base-window volume ratio

Target behavior:

- one noisy day should not dominate
- genuine re-accumulation should be rewarded

### 5.3 Better RS-improvement judgment

Phase 2 should shift from:

- absolute RS proxy

to:

- RS direction and slope

Examples:

- current RS above recent RS baseline
- RS no longer deteriorating
- RS improvement over the last few sessions

Target behavior:

- medium-strength improving names can enter
- flat or fading names should be penalized

### 5.4 Better distance-state classification

Upgrade the current bottom-distance classification to:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

Meaning:

- `still_bottoming`: not meaningfully off the bottom yet
- `off_bottom_not_extended`: ideal Phase 2 setup window
- `early_extension`: usable but lower-quality
- `too_extended`: exclude

This lets the lane better distinguish:

- early launch
- already obvious momentum continuation

## 6. Theme-Aware Weighting

Phase 2 should remain theme-aware, but only lightly.

Do not create fully separate algorithm families per theme.

Instead, add a small configuration surface such as:

- `SETUP_LAUNCH_THEME_WEIGHTS`

This can slightly change the relative importance of:

- structure repair
- volume return
- RS improvement
- distance state

for:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

Example intention:

- equipment-heavy themes may care more about structure repair
- sentiment-heavy themes may care more about early volume return

But the core algorithm remains shared.

## 7. Better Setup Reasons

Current reasons are generic:

- `structure_repair_visible`
- `volume_return_visible`
- `rs_trend_improving`

Phase 2 should upgrade them to more specific, operator-readable reasons.

Examples:

- `ma20_reclaimed`
- `ma50_reclaimed`
- `ma20_turning_up`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

The goal is to make the `筑底启动补充` section more useful in practice.

## 8. Reporting Behavior

The report contract should remain stable:

- still under `筑底启动补充`
- still separate from `市场强势补充`
- still not treated as direct execution

What should change is the explanation quality:

- more precise setup reasons
- better distinction between:
  - early launch
  - weak repair
  - already extended

## 9. Testing Requirements

Phase 2 tests must cover:

1. structure-repair upgrades
   - distinguish single reclaim from stronger sustained repair
2. volume-return upgrades
   - distinguish one-off high turnover from real re-accumulation
3. RS-improvement upgrades
   - distinguish improving RS from flat or fading RS
4. distance-state upgrades
   - classify `off_bottom_not_extended` vs `early_extension` vs `too_extended`
5. theme-aware weighting
   - verify weights can differ by configured theme without changing lane shape
6. report behavior
   - `筑底启动补充` still renders separately
   - `T1` / `T2` remain untouched

## 10. Out of Scope

Phase 2 must not include:

- historical backtest optimization
- ML ranking
- per-theme custom detectors with fully separate logic
- automatic execution-tier promotion
- global report redesign

Those are later-phase concerns.

## 11. Success Criteria

Phase 2 is successful if:

1. the lane becomes better at surfacing true early-launch names
2. obvious pure-bottom drifters are excluded more often
3. already-extended names are excluded or downgraded more consistently
4. `筑底启动补充` explanations become more actionable
5. the event-driven shortlist and `market_strength` lane remain intact

## 12. Recommended Next Step

Write an implementation plan that only changes:

- setup helper logic
- setup scoring / weighting
- setup tests
- setup report reasons

Do not expand scope beyond the setup lane itself.
