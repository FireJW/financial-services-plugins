# Theme-Aware Base Launch Supplement Lane Phase 2 Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Upgrade the first-pass `setup_launch_candidates` lane so it can more
reliably distinguish true base-completion / early-launch setups from pure bottom
drift and already-extended strength names.

## 1. Goal

Phase 1 solved a visibility problem:

- the system can now surface a dedicated `筑底启动补充` layer
- it can do so inside both live priority themes and strategic base-watch themes

Phase 2 should improve the quality of that layer.

The goal is not to redesign the lane. The goal is to make it more selective and
more explainable, especially for former high-beta trend themes such as:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

Phase 2 should help the system better distinguish three states:

1. still drifting at the bottom
2. genuine early-launch setup
3. already-extended move that no longer belongs in the early-launch bucket

## 2. What Is Weak In Phase 1

The current Phase 1 implementation is intentionally lightweight, but its logic
is still too coarse.

### 2.1 Structure repair is too shallow

Current logic largely treats structure repair as:

- above `ma20`
- better if above `ma50`
- otherwise a rough `pct_from_60d` fallback

This is enough to detect obvious recovery, but not enough to distinguish:

- one-day rebound noise
- real structure repair

### 2.2 Volume return is too static

Current volume logic is based on simple thresholds such as:

- `volume_ratio`
- turnover rate
- same-day turnover amount

That catches participation, but it does not really answer the more important
question for setup work:

- is volume returning relative to the earlier contraction window?

### 2.3 Relative-strength improvement is still too close to absolute RS

Current RS logic still approximates strength by using:

- `rs90`
- `pct_from_ytd`
- positive day action

That is an acceptable first pass, but it is not yet a proper
"relative-strength repair" detector.

### 2.4 Distance state is too coarse

Current bottom-state logic is:

- `still_bottoming`
- `off_bottom_not_extended`
- `too_extended`

That is useful, but not granular enough to separate:

- newly lifted names
- healthy early extension
- already late extension

## 3. Phase 2 Principle

Do not change the lane's product semantics.

This remains:

- a supplement lane
- a `筑底启动补充` layer
- a `T3/T4` and report/watchlist-only source

Do not let Phase 2 become a stealth rewrite of the formal shortlist engine.

Specifically, Phase 2 must not:

- alter `keep_threshold`
- alter `strict_top_pick_threshold`
- promote setup-lane rows directly into `T1` or `T2`
- replace `market_strength_candidates`
- replace `event_discovery_candidates`

## 4. Phase 2 Detection Upgrade

Keep the same four major dimensions, but upgrade each from a coarse threshold to
an actual stage detector.

### 4.1 Structure repair v2

Phase 2 structure repair should consider more than simple spot price location.

Signals to include:

- `close > ma20`
- stronger: `close > ma50`
- `ma20` improving relative to a recent lookback (for example versus 5 or 10
  sessions ago)
- recent lows are stabilizing or rising
- optional support from `trend_template` fields when already available, but only
  as supporting evidence, not a hard requirement

Desired output labels remain:

- `high`
- `medium`
- `low`

But they should now reflect true structure quality, not just one-day position.

### 4.2 Volume return v2

Phase 2 volume return should explicitly compare recent activity with the earlier
base period.

Suggested shape:

- define a recent volume window (for example `3-5` sessions)
- define a prior quiet/base window (for example `10-20` sessions before that)
- compare average volume / turnover between those windows

The lane should reward:

- visible reacceleration in participation

It should not require:

- same-day climax volume

Desired labels remain:

- `high`
- `medium`
- `low`

### 4.3 Relative-strength improvement v2

Phase 2 should stop treating RS improvement as a rough stand-in for absolute RS.

Instead, it should evaluate direction of repair.

Examples of acceptable Phase 2 signals:

- `rs90` slope is positive over a short lookback
- RS is higher than it was several sessions ago
- RS is no longer collapsing even if the absolute level is still moderate

This lets the lane keep names that are genuinely improving before they become
obvious leaders.

### 4.4 Distance-from-bottom v2

Upgrade the bottom-state classifier to separate early launch from already-late
extension more clearly.

Recommended states:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

Desired semantics:

- `still_bottoming`: not ready
- `off_bottom_not_extended`: ideal phase
- `early_extension`: still allowed, but lower quality than ideal phase
- `too_extended`: exclude

## 5. Better Setup Reasons

Phase 1 uses generic reasons such as:

- `structure_repair_visible`
- `volume_return_visible`
- `rs_trend_improving`

Phase 2 should surface more specific reasons so the report becomes more useful
for discretionary review.

Examples:

- `ma20_turning_up`
- `reclaimed_ma20_ma50`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

This change should improve the readability of `筑底启动补充` without turning it
into a long narrative block.

## 6. Theme-Specific Weight Hooks

Phase 2 should prepare for theme-aware tuning, but should remain lightweight.

Add a small configuration surface such as:

- `SETUP_LAUNCH_THEME_WEIGHTS`

for the Phase 2 theme set:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

These weights may slightly tilt:

- structure repair
- volume return
- RS improvement
- distance-state preference

However, Phase 2 should not create four completely separate detection engines.

This is a weighting hook, not a per-theme algorithm fork.

## 7. Output Contract

The lane keeps the same outward contract:

- `setup_launch_candidates`
- `source = setup_launch_scan`
- `筑底启动补充`

Phase 2 may extend the row with richer internals such as:

- `setup_score`
- `structure_repair_detail`
- `volume_return_detail`
- `rs_improvement_detail`

But this should remain additive and backward-compatible.

## 8. Report Semantics

Do not change report placement.

The report should still separate:

1. event-driven main names
2. `市场强势补充`
3. `筑底启动补充`

Phase 2 improvement is quality of reasoning, not report hierarchy.

The visible change should be that a `筑底启动补充` card now explains *why* it is
an early-launch setup in a more concrete way.

## 9. Testing Focus

Phase 2 tests should explicitly cover:

1. a one-day rebound that should **not** be treated as real structure repair
2. a stock with rising short-window participation vs prior contraction window
3. a stock whose RS is improving even though absolute RS is not elite
4. a stock in `early_extension` that still qualifies but ranks lower
5. a stock in `too_extended` that is excluded
6. one case for each strategic theme where theme weights do not break the shared
   contract

## 10. Out Of Scope

Phase 2 does not include:

- historical win-rate backtesting for the lane
- machine-learning setup classification
- fully theme-specific detection engines
- new execution-tier promotion rules
- formal integration into `T1/T2`
- redesign of `market_strength_candidates`

## 11. Success Criteria

Phase 2 is successful if:

1. fewer pure bottom-drift names slip into `筑底启动补充`
2. fewer already-late momentum names are misclassified as early-launch setups
3. true base-completion names score more consistently
4. cards are more interpretable because their setup reasons are more specific
5. existing execution-layer discipline remains untouched

## 12. Recommended Next Step

The implementation plan should focus on:

1. upgrading the four existing setup dimensions rather than replacing them
2. introducing a tiny theme-weight surface for the four strategic themes
3. adding focused tests that distinguish bottom drift, true early launch, early
   extension, and overextension
