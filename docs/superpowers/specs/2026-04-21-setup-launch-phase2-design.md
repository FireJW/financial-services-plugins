# Setup Launch Phase 2 Design

**Date:** 2026-04-21  
**Status:** Approved design  
**Scope:** Upgrade the existing `setup_launch_candidates` lane from a light
Phase 1 visibility layer into a more reliable early-launch detector for
theme-scoped base-repair setups.

## 1. Goal

Phase 1 already solved one important product problem:

- the system can now see certain names that look like base-completion /
  early-launch candidates

But the current lane is still too simple. It behaves more like:

- a lightweight rules filter

than:

- a dependable early-launch detector

Phase 2 should improve signal quality without changing the product boundary.

The upgraded lane should:

- remain a supplement lane rather than a formal execution engine
- keep scanning only:
  - live priority themes
  - `strategic_base_watch_themes`
- improve the distinction between:
  - bottom drift
  - early launch
  - late extension
- remain restricted to:
  - `T3`
  - `T4`
  - report-only watch surfaces

It must not:

- directly promote names into `T1`
- directly promote names into `T2`
- loosen the main event-driven shortlist thresholds

## 2. Root Cause

The current Phase 1 implementation is intentionally light:

- `structure_repair` is dominated by simple `ma20` / `ma50` recovery
- `volume_return` is still mostly threshold-based
- `rs_improvement` is approximated by absolute `rs90`, `pct_from_ytd`, and
  positive `day_pct`
- `distance_from_bottom_state` is only a coarse three-state check

That creates three recurring problems:

1. stocks that merely bounce above a moving average can look repaired too early
2. one-day turnover spikes can look like genuine volume return
3. names that are already extended can still score like early-launch setups

So the Phase 1 lane is useful for visibility, but not yet strong enough to be
trusted as a higher-quality setup detector.

## 3. Design Principle

Do not redesign the lane into a different product.

Phase 2 should remain:

- deterministic
- explainable
- theme-aware
- lightweight enough to live in the existing shortlist runtime

The correct move is:

- upgrade setup-stage signals
- add a small amount of theme-aware weighting
- improve reporting explanations

The wrong move would be:

- turning this into a new formal execution engine
- adding opaque ML classification
- merging it into `market_strength_candidates`

## 4. What Phase 2 Should Detect

The target setup remains:

- a former or potential trend theme name
- after a prolonged base or contraction period
- with structure now improving
- with volume beginning to return
- with relative strength turning better
- but before the name becomes an obviously overextended momentum leader

This means Phase 2 should reward:

- repair
- reacceleration
- early expansion

It should reject:

- flat base drift with no real turn
- weak dead-cat bounce
- already overextended momentum continuation

## 5. Signal Upgrades

### 5.1 Structure Repair Phase 2

Replace the current simple recovery logic with a more layered check.

Phase 2 structure repair should consider:

- `close > ma20`
- `close > ma50`
- `ma20` slope improving
- recent lows no longer making lower lows
- short-term structure no longer in obvious downtrend

Recommended output remains categorical:

- `low`
- `medium`
- `high`

Suggested interpretation:

- `high`
  - price has recovered both `ma20` and `ma50`
  - `ma20` is flattening or rising
  - recent lows are stabilizing or lifting
- `medium`
  - price has recovered `ma20`
  - some improvement exists, but `ma50` recovery or low-structure repair is
    incomplete
- `low`
  - still mostly drift / bounce behavior

### 5.2 Volume Return Phase 2

Phase 1 mainly used single-point thresholds.

Phase 2 should shift to:

- relative improvement versus the prior quiet base

Examples:

- recent `3-5` session average volume versus prior `10-20` session base volume
- turnover improvement across a short rolling window
- repeated participation rather than a one-day pulse

The lane should reward:

- consistent reacceleration

It should not over-reward:

- one isolated volume spike

### 5.3 Relative Strength Improvement Phase 2

Phase 1 used absolute RS-adjacent shortcuts.

Phase 2 should explicitly model:

- RS trend improvement

Examples:

- `rs90` rising versus recent history
- RS no longer deteriorating
- current price performance improving relative to a recent local window

The key product rule is:

- a setup can qualify with improving RS even if it is not yet a high absolute
  RS leader

### 5.4 Distance-From-Bottom State Phase 2

Replace the simple three-state logic with a more useful stage classifier:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

Meaning:

- `still_bottoming`
  - not yet sufficiently separated from the base
- `off_bottom_not_extended`
  - desired Phase 2 sweet spot
- `early_extension`
  - still possibly valid but lower quality than the sweet spot
- `too_extended`
  - should be excluded from this lane

This improves the distinction between:

- valid early-launch candidates
- names that already belong to momentum / strength logic

## 6. Theme-Aware Phase 2 Weighting

Phase 2 should still avoid a fully custom algorithm per theme.

But it should introduce a lightweight theme-specific weighting layer for:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

This weighting layer should:

- reuse the same core signal framework
- allow modest differences in signal emphasis

Examples:

- `commercial_space`
  - slightly higher weight on volume return and early separation from bottom
- `controlled_fusion`
  - slightly higher weight on structure repair because moves can be more stop /
    start
- `humanoid_robotics`
  - slightly higher weight on RS improvement because names often re-rate through
    sentiment rotation
- `semiconductor_equipment`
  - slightly higher weight on orderly structure repair over short-term intraday
    strength

Important boundary:

- this is weighting, not separate rule engines

## 7. Candidate Contract Changes

The lane should keep the existing top-level contract:

- `ticker`
- `name`
- `theme_guess`
- `setup_reasons`
- `structure_repair`
- `volume_return`
- `rs_improvement`
- `distance_from_bottom_state`
- `source = setup_launch_scan`

Phase 2 should add more explainable `setup_reasons`, for example:

- `ma20_turning_up`
- `reclaimed_ma50`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

The purpose is not more verbosity.

The purpose is:

- when a name appears in `筑底启动补充`, the user can see *why*

## 8. Reporting Behavior

Phase 2 should keep the existing report placement:

- `筑底启动补充` remains its own section

But the section should become more explainable.

Each card should emphasize:

- what is repaired
- what is improving
- why this is still early-stage rather than strong-momentum continuation

The lane must remain clearly distinct from:

- `市场强势补充`

That distinction is part of the product.

## 9. Testing Requirements

Phase 2 tests should focus on stage discrimination.

Required coverage:

1. **Structure-repair discrimination**
   - a simple one-day bounce should not score like a repaired setup
   - a recovered `ma20/ma50` plus higher-lows case should score better

2. **Volume-return discrimination**
   - repeated volume improvement should score better than a one-day spike

3. **RS-improvement discrimination**
   - an improving RS trend should beat a flat or deteriorating RS trend

4. **Distance-state discrimination**
   - `off_bottom_not_extended` should outrank `still_bottoming`
   - `too_extended` should be excluded

5. **Theme-weighting sanity**
   - the same row can receive modestly different scoring emphasis by theme
   - but core eligibility rules remain shared

6. **No tier pollution**
   - no Phase 2 setup candidate should directly enter `T1/T2`

## 10. Out Of Scope

Phase 2 should not include:

- per-theme fully separate algorithms
- backtest-driven optimization loops
- machine learning classification
- new execution-tier promotion rules
- changes to formal event shortlist thresholds

Those are later cycles, not this one.

## 11. Success Criteria

Phase 2 is successful if:

1. the lane more reliably separates true early-launch setups from noise
2. obviously overextended names stop leaking into `setup_launch_candidates`
3. the four strategic themes feel more realistic without becoming four separate
   systems
4. report output becomes more interpretable
5. `T1/T2` discipline remains unchanged

## 12. Recommended Next Step

The implementation plan should focus on:

1. upgrading the four setup signals
2. adding lightweight theme-specific weighting
3. improving tests around stage discrimination
4. keeping the output contract stable so downstream report code changes stay
   small
