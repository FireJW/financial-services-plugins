# Market Strength Top Movers Universe Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Add a dedicated top-movers / close-strength universe fetch path for
the `market_strength_candidates` supplement lane

## 1. Goal

Replace the supplement lane's current dependence on the default shortlist
universe with a dedicated market-strength universe that is designed to surface
obvious strong names.

This new fetch path should:

- serve only the `market_strength_candidates` supplement lane
- prioritize same-day strong movers rather than turnover-heavy broad-market
  leaders
- continue feeding the existing supplement contract and late-merge path
- preserve the existing hard boundary that supplement names only reach:
  - `T3`
  - `T4`
  - clearly labeled reference/report surfaces

## 2. Root Cause

The current auto-generator already works as designed, but its upstream input is
too narrow.

The runtime currently reuses `default_universe_fetcher(...)`, which is not a
true full-market strength view.

Observed behavior:

- the compiled fetcher uses Eastmoney `clist`
- it sorts by `fid = f6`
- the default limit is `80`
- even when the page size is increased, the response remains a bounded turnover
  list rather than a broad strength universe

This means the current supplement lane is effectively consuming:

- a turnover-ranked shortlist snapshot

instead of:

- a strong-movers universe

As a result, names such as `002980.SZ` or `603268.SS` can be absent before the
supplement scoring logic even runs.

That is an upstream universe-coverage problem, not a downstream ranking bug.

## 3. Design Principle

Do not try to fix this by repeatedly adjusting `market_strength_score(...)`.

The scoring function is already doing the correct Phase 1 job:

- reward same-day strength
- reward strong close location
- reward turnover participation
- exclude low-quality names

The required fix is to change the input universe for the supplement lane.

The main event-driven shortlist spine should continue using the existing
`default_universe_fetcher(...)`.

Only the supplement lane should gain a new upstream source.

## 4. New Fetcher

Add a dedicated fetch helper:

- `default_market_strength_universe_fetcher(...)`

This helper should use Eastmoney `clist`, but with a universe definition that
is better aligned with strong-mover detection.

Phase 1 shape:

- still use the existing mainland market groups
- sort by a strength-oriented field, not turnover-first
- prefer top movers / same-day strength ordering
- fetch a wider bounded set than the current default universe path

Recommended Phase 1 direction:

- use Eastmoney `clist`
- move away from `fid = f6`
- prefer a mover-oriented ordering such as:
  - `fid = f3`
- fetch a bounded wider candidate set such as:
  - `200`
  - or `300`

The fetched rows are then passed into the existing
`build_market_strength_candidates_from_universe(...)` helper for final
close-strength ranking and hard exclusions.

## 5. Pipeline Placement

The supplement lane should stop auto-generating from the main shortlist
universe.

Recommended Phase 1 flow:

1. main shortlist continues to fetch its normal universe with
   `default_universe_fetcher(...)`
2. supplement lane separately calls
   `default_market_strength_universe_fetcher(...)`
3. `build_market_strength_candidates_from_universe(...)` ranks and filters those
   rows
4. generated rows merge into `market_strength_candidates`
5. existing supplement-lane late-merge logic handles the report and tier
   surfaces

This keeps the responsibilities clear:

- main universe powers event-driven shortlist evaluation
- top-movers universe powers strength-supplement discovery

## 6. Hard Boundaries

This design must preserve the current supplement-lane discipline.

Required boundaries:

- supplement names still must not enter `T1` on this lane alone
- the new fetcher must not replace the main shortlist universe
- the supplement lane remains a late-merge observer layer, not a primary
  execution engine
- report labeling remains explicit:
  - `market strength supplement`

The new fetcher changes discovery coverage, not execution authority.

## 7. Failure Handling

The new top-movers fetch path must fail softly.

If `default_market_strength_universe_fetcher(...)` fails:

- the main shortlist should still run normally
- event-driven and known-chain logic should still produce a result
- the supplement lane should degrade gracefully
- the result should not pretend supplement names were generated

In other words:

- top-movers fetch failure must not collapse the whole report

## 8. Output Contract

Phase 1 should not introduce a new downstream contract.

The top-movers fetcher still feeds the existing:

- `market_strength_candidates`

Each generated row should keep the same candidate shape:

- `ticker`
- `name`
- `strength_reason`
- `close_strength`
- `volume_signal`
- `board_context`
- `theme_guess`
- `source`

The only recommended source refinement is:

- allow a more specific source label such as
  `market_strength_top_movers`

This helps distinguish:

- manually provided supplement rows
- turnover-list supplement rows from older runs
- new top-movers-derived supplement rows

## 9. Success Criteria

This design is successful if:

1. the supplement lane no longer depends on a turnover-ranked top-80 universe
2. strong names that are clearly moving on the day are less likely to vanish
   before ranking
3. obvious same-day strength names can surface without manual ticker entry
4. supplement names still remain constrained to:
   - `T3`
   - `T4`
   - reference/report layers
5. the main event-driven shortlist path remains unchanged

## 10. Non-Goals

Phase 1 does not attempt to:

- redesign the main shortlist universe
- replace Eastmoney entirely
- solve all market-coverage issues in one step
- create a full standalone momentum engine
- promote strong movers directly into the formal execution layer

## 11. Future Extensions

If this works, later phases can add:

- multi-list union fetch:
  - turnover list
  - top movers list
  - near-limit / strong-close list
- board-specific mover universes
- richer theme inference for supplement names
- explicit diagnostics showing why a strong name was absent:
  - not in universe
  - excluded by hard filter
  - out-ranked by stronger movers
