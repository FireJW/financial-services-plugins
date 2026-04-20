# Theme-Aware Base Launch Supplement Lane Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Add a theme-aware supplement lane that surfaces base-completion /
early-launch setups which are not yet strong enough to be captured by the
current event-driven shortlist or the existing market-strength supplement lane.

## 1. Goal

The current shortlist stack is good at finding:

- event-confirmed names
- already-strong follow-through names
- same-day strong-close supplement names

It is weak at finding a different class of stock:

- former leadership themes that spent time basing
- names that have largely completed bottom formation
- names whose structure and volume are starting to improve
- names that are not yet near the strongest breakout / close-strength profile

This design adds a new supplement lane to cover that blind spot without
loosening the main execution engine.

The new lane should:

- detect early launch setups inside selected themes
- stay separate from the existing `market_strength_candidates` lane
- preserve the existing event-driven shortlist discipline
- surface candidates only into:
  - `T3`
  - `T4`
  - clearly labeled report-only / watchlist surfaces
- never promote names directly into `T1` or `T2` by itself

## 2. Root Cause

The current runtime is structurally biased toward later-stage confirmation.

### 2.1 Event / discovery lane bias

`earnings_momentum_discovery.py` currently treats market validation as:

- `volume_multiple_5d >= 1.5`
- `breakout = trend_pass && distance_to_high52_pct <= 25.0`
- `relative_strength = strong if rs90 >= 500`
- optional `chain_resonance`

That means the discovery lane is more suited to names that have already:

- repaired structure strongly enough to satisfy `trend_pass`
- approached the upper part of their longer-range price structure
- reached a high absolute RS threshold

This is a poor fit for names that are only beginning to emerge from a long base.

### 2.2 Market-strength lane bias

The newly added `market_strength_candidates` lane is intentionally same-day
strength oriented.

Its ranking logic emphasizes:

- positive `day_pct`
- close location near the intraday high
- meaningful turnover

That is the correct behavior for a strong-mover supplement lane, but it is not
an early-launch detector. A stock can be at the start of a base-completion
move while still failing to look like a same-day strength leader.

### 2.3 Coverage consequence

The system can therefore miss names that a human discretionary operator notices
more easily, especially inside former high-beta trend themes such as:

- commercial space / satellite chain
- controlled fusion
- humanoid robotics
- semiconductor equipment

Those themes often produce a recognizable pre-breakout phase where:

- downside pressure has faded
- structure starts to repair
- volume starts to return
- but the stock is not yet in a fully confirmed breakout state

## 3. Product Shape

Add a dedicated new supplement lane:

- `setup_launch_candidates`

This lane should run in parallel with:

- `event_discovery_candidates`
- `market_strength_candidates`

Its product meaning is:

- bottom-completion / early-launch watchlist candidates

It is not:

- a formal execution layer
- a replacement for the event-driven shortlist spine
- a replacement for the same-day market-strength supplement lane

## 4. Theme-Aware Scope

This lane should not run as a naked full-market setup screener.

Instead, it should scan the union of two theme pools.

### 4.1 Live priority themes

Themes currently surfaced by `weekend_market_candidate`, especially the top
`2-3` directions from live X topic discovery.

### 4.2 Strategic base-watch themes

Add a durable configured theme pool for former major-trend groups that may not
be the hottest weekend topic every week, but are still important for detecting
base-completion setups.

New configuration surface:

- `strategic_base_watch_themes`

Phase 1 seed set:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

This creates the right behavior:

- live weekend topics can influence what the system cares about right now
- long-cycle base themes do not disappear simply because a given weekend did
  not produce the highest X / Reddit discussion volume

## 5. Phase 1 Detection Philosophy

The lane should deliberately look for a different setup stage than the current
runtime.

It should prefer names that exhibit most of the following:

- structure repair
- early volume return
- improving relative strength trend
- clear separation from the absolute bottom
- but not yet fully mature breakout / strongest-close behavior

### 5.1 Structure repair

Phase 1 should recognize structure repair using practical, explainable signals,
not shape-heavy pattern taxonomy.

Examples of acceptable signals:

- price has reclaimed `ma20`
- stronger case: price has also reclaimed `ma50`
- `ma20` is flattening or turning up
- recent lows are no longer making obvious lower lows

The stock does not need to be near a 52-week high.

### 5.2 Early volume return

Phase 1 should reward volume that is improving relative to the prior quiet base,
without requiring a climax-strength surge.

Examples:

- recent `3-5` session volume is clearly above the prior contraction window
- `volume_ratio` or equivalent participation metric is rising
- volume expansion is visible but not necessarily extreme

### 5.3 Relative-strength improvement, not high absolute RS

Do not reuse the strict later-stage definition:

- `rs90 >= 500 => strong`

Phase 1 should instead look for improvement behavior.

Examples:

- RS is rising over recent sessions
- RS is no longer deteriorating
- RS rank is improving even if the absolute value is still moderate

### 5.4 Away from the bottom, but not near long-term highs

The setup should not still be glued to the absolute bottom of the recent range.

But it also should not be required to sit close to 52-week highs.

This lane is intended to live in the middle stage between:

- pure bottom drift
- already-confirmed breakout leadership

## 6. Candidate Contract

Add a new normalized input / internal candidate family:

- `setup_launch_candidates`

Each row should minimally carry:

- `ticker`
- `name`
- `theme_guess`
- `setup_reasons`
- `structure_repair`
- `volume_return`
- `rs_improvement`
- `distance_from_bottom_state`
- `source = setup_launch_scan`

Example shape:

```json
{
  "ticker": "603698.SS",
  "name": "航天工程",
  "theme_guess": ["commercial_space"],
  "setup_reasons": [
    "reclaimed_ma20_ma50",
    "volume_return_visible",
    "rs_trend_improving"
  ],
  "structure_repair": "high",
  "volume_return": "medium",
  "rs_improvement": "medium",
  "distance_from_bottom_state": "off_bottom_not_extended",
  "source": "setup_launch_scan"
}
```

## 7. Report Semantics

This new lane must be visually and semantically distinct from the existing
`market_strength_candidates` lane.

The report should clearly separate:

1. event-driven main candidates
2. `市场强势补充`
3. `筑底启动补充`

Recommended placement order:

1. weekend market candidate / direction layer
2. direction reference map
3. direct execution layer
4. event-driven observation layer
5. `市场强势补充`
6. `筑底启动补充`

The purpose is to avoid mixing:

- already-strong names
- early-launch names

### 7.1 Labeling

Phase 1 report labels should explicitly state:

- `筑底启动补充`

Each card should explain why the stock is here using language such as:

- bottom structure is repairing
- volume is returning
- relative strength is improving
- still early in the launch phase

### 7.2 Tier boundary

Hard rule:

- `setup_launch_candidates` may only reach:
  - `T3`
  - `T4`
  - report-only / watchlist surfaces
- they may not directly enter:
  - `T1`
  - `T2`

This lane solves a visibility problem, not an execution-confirmation problem.

## 8. Relation To Existing Lanes

### 8.1 Main event-driven shortlist

Unchanged.

Do not loosen:

- keep thresholds
- strict top-pick thresholds
- later-stage breakout / RS confirmation logic

### 8.2 Market-strength supplement lane

Unchanged in purpose.

`market_strength_candidates` continues to answer:

- what already looked obviously strong on the day

`setup_launch_candidates` answers a different question:

- what is beginning to look ready after a prolonged base

### 8.3 Weekend market candidate

`weekend_market_candidate` continues to provide the live directional layer.

Its outputs help define part of the scan universe for the new lane, but it does
not replace the strategic base-watch theme pool.

## 9. Phase 1 Out Of Scope

Do not do these in Phase 1:

- full-market unconstrained setup scanning
- pattern-recognition taxonomy for every cup / handle / VCP variant
- machine-learning classification of base quality
- direct T1/T2 promotion
- redesign of the current event-driven shortlist scoring engine

## 10. Success Criteria

Phase 1 is successful if:

1. stocks like `航天工程` can become visible to the system as early-launch
   observation candidates when their setup actually improves
2. the lane surfaces names inside both:
   - current live priority themes
   - strategic base-watch themes
3. the system no longer relies only on:
   - event confirmation
   - same-day strong-close behavior
   to notice these names
4. the existing execution discipline remains intact
5. report output clearly distinguishes:
   - event-driven main names
   - `市场强势补充`
   - `筑底启动补充`

## 11. Recommended Next Step

The implementation plan should focus on three bounded tasks:

1. add a durable `strategic_base_watch_themes` configuration surface
2. add a `setup_launch_candidates` generator that scans only the combined
   theme-scoped universe
3. wire the new lane into the existing late-merge and report pipeline without
   altering `T1/T2` rules
