# Bars Fallback Observation Rescue Design

**Date:** 2026-04-19  
**Status:** Approved design  
**Scope:** `month-end-shortlist` wrapper/runtime layer only

## 1. Goal

Add a balanced fallback path for mainland stock history failures so the shortlist
does not collapse into mass `bars_fetch_failed` blocks when the primary bars
provider is unavailable.

The target behavior is:

- keep the current primary bars path unchanged
- when primary bars fail, try an existing repo-local market snapshot path as a
  secondary source
- only rescue names that already have real event/discovery/chain support
- rescued names may enter **low-confidence `T3`** only
- no rescued name may enter `T1`
- the report must clearly label rescued names as fallback-driven observation
  candidates rather than normal shortlist names

## 2. Problem Statement

Current shortlist behavior is too binary under a provider outage:

- primary bars fetch fails
- wrapper turns the candidate into `bars_fetch_failed`
- candidate becomes `blocked`
- the front-layer plan becomes artificially empty even when the stock still has:
  - a valid structured catalyst
  - discovery/watch support
  - chain/theme support

This is not a stock-quality failure. It is a data-path failure that currently
propagates too aggressively into the trade plan.

## 3. Phase Boundary

Included:

- wrapper/runtime-only fallback behavior
- secondary source reuse from the existing repo-local market snapshot path
- fallback rescue eligibility based on existing evidence
- low-confidence `T3` rescue output
- explicit report labeling

Excluded:

- compiled shortlist core changes
- automatic provider replacement for all runs
- any fallback path that can create `T1`
- any attempt to treat snapshot data as equivalent to full bars history
- any silent rescue without user-visible labeling

## 4. Design Principle

This is a **data-path repair**, not a scoring relaxation.

The system should not respond to provider failure by pretending the missing bars
do not matter. Instead, it should:

1. admit that the primary bars path failed
2. use a weaker secondary source only to decide whether the stock still merits
   observation
3. rescue only the names that were already justified by other evidence
4. label the result explicitly as low-confidence

In short:

- rescue observation
- do not fake execution confidence

## 5. High-Level Data Flow

The new flow is:

1. primary bars fetch runs as usual
2. if the stock gets a normal bars result:
   - continue existing shortlist logic
3. if the stock gets `bars_fetch_failed`:
   - try secondary repo-local market snapshot
4. if secondary snapshot is unavailable or too weak:
   - keep the stock blocked
5. if secondary snapshot is available and the stock has real support evidence:
   - rescue it into low-confidence `T3`
6. report the fallback identity explicitly

This keeps the primary pipeline intact while softening provider outages into
bounded observation-layer degradation.

## 6. Secondary Source

Phase 1 of this repair reuses the existing repo-local market snapshot path that
already exists elsewhere in the repository.

That means:

- do **not** introduce a new market vendor abstraction first
- do **not** build a second custom Eastmoney client inside shortlist
- do **not** require `TUSHARE_TOKEN`

The intention is to borrow the existing local-market snapshot capability that
already understands tokenless free-market paths, and use it as a narrow recovery
mechanism for shortlist.

## 7. Rescue Eligibility

A `bars_fetch_failed` name may only be rescued if it has **at least one**
meaningful support source already present in the pipeline.

Allowed support sources in Phase 1:

### 7.1 Structured Catalyst Support

The candidate already has a real structured catalyst, such as:

- official filing / formal preview
- structured company event within window
- other existing structured-catalyst support already recognized by shortlist

### 7.2 Discovery Support

The candidate already has discovery-layer support, such as:

- `qualified`
- `watch`

This means the system had already judged the stock worth monitoring before the
bars path failed.

### 7.3 Event Card / Chain Support

The candidate already has meaningful event-card or chain/theme support, such as:

- event-card presence
- chain/theme bias that already exists in the wrapper output

This is the weakest acceptable rescue basis and should rank below structured
event support and discovery support.

### 7.4 Explicitly Excluded Rescue Inputs

These must **not** be used as rescue justification on their own:

- name looks familiar
- old score used to be high
- user might care about the stock
- geopolitics candidate/overlay alone
- broad theme similarity without event/discovery support

## 8. Secondary Snapshot Minimum Fields

The fallback path does **not** need to reconstruct full bars history. It only
needs enough snapshot information to answer whether the stock is obviously broken
or still worthy of observation.

Minimum useful fields:

- latest price / latest percent change
- short-to-medium moving-average context
  - e.g. `sma20`, `sma50`
- momentum / strength proxy
  - e.g. `rsi14`
- relative volume / participation proxy
  - e.g. `volume_ratio`

The fallback path does **not** need to reproduce:

- full 150/200-day structure logic
- full breakout history
- full VCP sequencing
- every score component from the normal bars path

The fallback snapshot only needs to answer:

1. Did price clearly break?
2. Is short/medium support obviously lost?
3. Is momentum obviously broken?
4. Is there enough evidence left to keep watching?

## 9. Rescue Classification

Rescued names must never be treated as normal observation candidates.

### 9.1 Tier Placement

Allowed:

- `T3`

Forbidden:

- `T1`
- `T2`
- normal-confidence `T3`

### 9.2 Internal Tags

Rescued names should carry explicit tags such as:

- `low_confidence_fallback`
- `fallback_support_reason=<...>`
- `fallback_snapshot_only`

Recommended support-reason values:

- `structured_catalyst`
- `discovery_watch`
- `discovery_qualified`
- `chain_support`

### 9.3 Snapshot Gate

Even if support exists, a rescued name must still fail rescue if the secondary
snapshot shows obvious breakdown behavior.

Examples of no-rescue conditions:

- clearly below short/medium support
- clearly broken momentum
- obviously weak reaction despite the supposed support

In those cases, the stock remains `blocked`.

## 10. Report Behavior

The report must make rescued names visually distinct.

### 10.1 Title-Level Label

Use a visible title label such as:

- `继续观察（low-confidence fallback）`

### 10.2 Card-Level Explanation

Within the card, add clear fallback phrasing such as:

- `数据路径降级：local market snapshot only`
- `保留原因：structured catalyst`
- `保留原因：discovery watch`

### 10.3 What Not To Do

Do not:

- mix rescued names into ordinary `继续观察` with no label
- hide fallback identity only in JSON tags
- write a long provider failure essay in each card

One or two short explanatory lines are enough.

## 11. Relationship to Existing Trade Plan

The fallback rescue layer should sit after provider failure handling but before
final tier rendering.

It should influence:

- whether some failed names remain visible in `T3`
- how those names are labeled in decision flow / reporting

It must not change:

- Phase 1 geopolitics overlay semantics
- candidate/overlay separation
- normal `T1` discipline
- normal observation ordering for fully supported bars-backed names

## 12. Testing Strategy

At minimum, Phase 1 tests must prove:

1. primary failure + support + acceptable snapshot -> rescued low-confidence `T3`
2. primary failure + no support -> still blocked
3. primary failure + support + broken snapshot -> still blocked
4. rescued names never reach `T1`
5. report labeling clearly identifies fallback rescue

Likely primary test files:

- `tests/test_screening_coverage_optimization.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`
- a new focused fallback test file if the logic grows large enough

## 13. Success Criteria

This repair is successful if:

- provider outages no longer flatten the entire plan into mass `bars_fetch_failed`
- event/discovery-supported names can remain visible in observation flow
- rescued names are clearly labeled as low-confidence fallback observations
- no rescued name reaches `T1`
- users can distinguish:
  - normal observation candidates
  - fallback rescue candidates

## 14. Non-Goals

This repair is **not** intended to:

- hide provider instability
- simulate complete bars analysis from weak data
- restore full confidence under outage conditions
- make shortlist less strict overall

It only converts a provider outage from “total blindness” into “bounded
low-confidence watch continuity.”
