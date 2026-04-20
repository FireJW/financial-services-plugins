# Market Strength Supplement Lane Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Add a market-first supplemental discovery lane for strong names that
the current event-driven shortlist misses

## 1. Goal

Add a separate `market_strength_candidates` lane that catches obvious
same-day strong stocks which are currently invisible to the system because they
never enter:

- `event_discovery_candidates`
- X-driven discovery inputs
- manual board whitelists
- the pre-existing candidate pool

This lane exists to improve **coverage**, not to replace the current
event-driven shortlist architecture.

Phase 1 must:

- surface full-market strong names that the main pipeline missed
- keep them outside `T1`
- allow them into `T3`, `T4`, or direction-reference surfaces only
- preserve the existing event-driven engine as the formal primary path

## 2. Problem Statement

The current shortlist behaves more like:

- event-driven shortlist
- plus known-chain expansion

It does **not** behave like a full-market strong-stock catcher.

The evidence is structural:

- request payloads often provide only a very small
  `event_discovery_candidates` set
- `auto_discovery_candidates` are built from `assessed_candidates`, not from a
  fresh market-wide strength scan
- if a stock never enters the assessed pool, it never has a chance to be
  ranked later

This creates a visible blind spot:

- obvious strong names such as `华盛昌` or `松发股份` can be fully absent from
  reports even when they were among the day’s most visible movers

The problem is therefore not just "thresholds are too strict".

The problem is:

- the pipeline often never sees these names at all

## 3. Design Principle

The fix should be a **parallel supplement lane**, not a redesign of the main
engine.

That means:

- keep the current event-driven shortlist unchanged as the formal spine
- add a second lane for market-first strong names
- merge this second lane only at the discovery/tier-render stage
- impose hard promotion limits so the supplement lane cannot silently become a
  new execution engine

This keeps the tradeoff clean:

- better market coverage
- without polluting `T1`
- without downgrading the discipline of structured-event names

## 4. New Lane

### 4.1 Name

Add a new input/output surface:

- `market_strength_candidates`

This lane sits beside:

- `event_discovery_candidates`

and does not overwrite it.

### 4.2 Role

`market_strength_candidates` is responsible for:

- catching today’s strongest and most recognizable names
- even when no formal event packet exists yet
- even when no X-derived subject pack named them in advance

It is explicitly **market-first**, not event-first.

### 4.3 What It Is Not

It is not:

- a replacement for `event_discovery_candidates`
- a shortcut around structured catalyst validation
- a path into `T1`
- a hidden second execution engine

## 5. Phase 1 Selection Philosophy

Phase 1 should be:

- market-first
- close-strength-first

This means the lane should prioritize names that look strongest by end-of-day
structure, not just intraday noise.

The design should favor names that show:

- near-limit close or locked strength
- close near session high
- strong day-over-day performance
- visible turnover or participation expansion
- market-wide recognizability on the day

The lane should **not** start by optimizing for:

- intraday amplitude alone
- fleeting board hits without close confirmation
- pure narrative guessing with no tape confirmation

## 6. Candidate Shape

Each `market_strength_candidates` entry should be lightweight and structured.

Phase 1 minimum fields:

- `ticker`
- `name`
- `strength_reason`
- `close_strength`
- `volume_signal`
- `board_context`
- `theme_guess`
- `source`

Example:

```json
{
  "ticker": "002980.SZ",
  "name": "华盛昌",
  "strength_reason": "near_limit_close",
  "close_strength": "high",
  "volume_signal": "expanding",
  "board_context": "high_conviction_momentum",
  "theme_guess": ["short_term_momentum"],
  "source": "market_strength_scan"
}
```

### 6.1 Field Intent

- `strength_reason`
  - why this name was pulled in at all
  - examples:
    - `limit_close`
    - `near_limit_close`
    - `close_near_high`
    - `strong_trend_continuation`

- `close_strength`
  - coarse quality label:
    - `high`
    - `medium`
    - `low`

- `volume_signal`
  - coarse tape participation label:
    - `expanding`
    - `normal`
    - `unclear`

- `board_context`
  - describes how the tape looked in broad trading terms
  - examples:
    - `high_conviction_momentum`
    - `trend_follow_through`
    - `squeeze_extension`

- `theme_guess`
  - optional rough thematic mapping
  - not required to be perfect in Phase 1

- `source`
  - fixed value in Phase 1:
    - `market_strength_scan`

## 7. Integration Point

The new lane should merge late, not early.

Recommended flow:

1. Existing main lane
   - `event_discovery_candidates`
   - X discovery
   - structured catalyst logic

2. New supplemental lane
   - `market_strength_candidates`

3. Merge layer
   - discovery/event-card enrichment
   - tier rendering
   - reference/report output

This means the lane can enrich what the user sees without changing the
foundational scoring assumptions of the main engine.

## 8. Tier Boundaries

These constraints are mandatory.

### 8.1 Hard Boundaries

Phase 1 `market_strength_candidates`:

- may enter `T3`
- may enter `T4`
- may appear in direction/reference sections
- may be labeled as market-strength supplement names

Phase 1 `market_strength_candidates`:

- may **not** enter `T1`
- should not directly create "可执行" output
- should not outrank formal event-driven `T1` names by themselves

### 8.2 Why This Boundary Exists

The supplement lane is fixing a coverage problem, not making a claim that pure
price strength is sufficient for execution.

This keeps the user-visible meaning clean:

- "the system now sees more of the tape"
- not
- "the system now buys anything that ran hard today"

## 9. Reporting

The report should make these names visible without confusing them with formal
event-led picks.

Recommended labels:

- `市场强势补充`
- `market-strength supplement`

They should render separately from:

- direct event-driven actionable names
- formal structured catalyst names

Suggested user-facing semantics:

- "These names were too strong to ignore today"
- "They were not primary event-led shortlist names"
- "Keep them in observation/reference, not formal execution by default"

## 10. Success Criteria

Phase 1 is successful if all of the following become true:

1. Names like `华盛昌` and `松发股份` no longer disappear entirely when they are
   among the day’s strongest stocks
2. The new lane improves market coverage without weakening event discipline
3. `T1` remains controlled by the existing formal engine
4. The report clearly distinguishes:
   - formal event-driven names
   - market-strength supplement names

## 11. Non-Goals

Phase 1 does not attempt to:

- build a full-market ranking engine
- replace formal catalyst logic
- solve intraday momentum trading
- perfectly classify all themes
- promote supplement names directly into execution decisions

## 12. Implementation Notes

Phase 1 should be designed so future upgrades remain easy:

- a later phase can refine `theme_guess`
- a later phase can add stricter momentum heuristics
- a later phase can allow selective uplift from supplement lane into more
  meaningful tiers

But none of those expansions should be assumed in this phase.

The correct first step is simply:

- make the system stop being blind to obvious full-market strength
- while preserving the event-driven spine
