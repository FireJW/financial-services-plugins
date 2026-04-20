# Market Strength Auto Generator Design

**Date:** 2026-04-20  
**Status:** Approved design  
**Scope:** Automatically generate daily `market_strength_candidates` from the
existing full-universe snapshot

## 1. Goal

Add a Phase 1 automatic generator that produces daily
`market_strength_candidates` without requiring manual ticker entry.

This generator should:

- reuse the existing full-market universe snapshot already fetched by the
  shortlist runtime
- select only a small set of top same-day strong names
- feed those names into the already-built `market_strength_candidates`
  supplement lane
- keep the resulting names constrained to `T3`, `T4`, and clearly labeled
  reference/report surfaces

The generator solves:

- "the supplement lane works if we manually name strong stocks"

Phase 1 extends that into:

- "the system can automatically find 5-10 strong names from the daily market
  snapshot"

## 2. Problem Statement

The new supplement lane now works when the user explicitly provides names such
as:

- `华盛昌`
- `松发股份`

That proves the lane integration is correct, but it still leaves a major gap:

- the system does not yet generate these supplement names on its own

Without an automatic generator, the current flow is still dependent on:

- manual operator input
- prior recognition that a name mattered

This means the coverage issue is only partially solved.

The lane can now carry strong names, but it cannot yet discover them.

## 3. Design Principle

Phase 1 should reuse the current universe fetch rather than creating a separate
market-strength fetch path.

Why:

- the runtime already pulls a full universe snapshot
- adding a second dedicated universe fetcher would increase complexity and
  drift risk
- the generator only needs to rank a small set of obvious same-day strong
  names, not build a second standalone market scanner

This keeps the design minimal:

- existing universe fetch remains the only market snapshot source
- the new generator is a deterministic filter over that existing data
- the existing supplement lane remains the only place where these generated
  names are integrated into the user-facing result

## 4. Placement in the Pipeline

The generator should run after the full universe has been fetched and before
the wrapper builds shared discovery/event-card surfaces.

Recommended flow:

1. full universe fetch
2. board split for existing track flow
3. `build_market_strength_candidates_from_universe(...)`
4. feed generated rows into `market_strength_candidates`
5. existing supplement-lane merge handles surfacing and tier boundaries

The key separation is:

- generator finds names
- supplement lane governs how those names appear

## 5. Phase 1 Output Size

Phase 1 should generate a small bounded set:

- `5-10` names per run

This is deliberate.

The generator is not meant to produce:

- a long ranked market list
- a full momentum monitor
- a second shortlist universe

It is meant to answer:

- which few names were strong enough today that the system should not ignore
  them entirely

## 6. Selection Philosophy

Phase 1 should be:

- market-first
- close-strength-first

The generator should prioritize names that look strongest by closing structure,
not just intraday noise.

The preferred characteristics are:

- large same-day gain or obvious same-day strength
- close near session high
- strong finish rather than a failed spike
- visible volume or turnover participation
- broad recognizability as a strong tape name on the day

This avoids overfitting the first version to fleeting intraday spikes.

## 7. Hard Exclusions

Phase 1 must exclude obvious low-signal or unusable cases.

Required hard exclusions:

- ST / risk-warning names
- extremely low-liquidity names
- essentially untradeable one-word limit cases with no meaningful turnover
- names already present in the formal event-driven execution path

The purpose of these exclusions is not to make the lane timid.

The purpose is to keep it from devolving into:

- noisy board-chasing
- non-usable reference clutter
- duplicate names that are already handled elsewhere

## 8. Candidate Shape

The generator should emit the same Phase 1 contract already defined for the
supplement lane:

- `ticker`
- `name`
- `strength_reason`
- `close_strength`
- `volume_signal`
- `board_context`
- `theme_guess`
- `source`

`source` remains:

- `market_strength_scan`

This is important because:

- the generator should not invent a second contract
- it should only automate how those rows are produced

## 9. Integration Contract

The automatic generator should behave as if the request had included:

- `market_strength_candidates`

That means the runtime can implement this as:

- explicit request rows, if provided by the user
- plus generated rows, if auto-generation is enabled by default

The merge rule for Phase 1 should be:

- explicit request-provided `market_strength_candidates` remain valid
- auto-generated rows are appended
- duplicate tickers are deduplicated by ticker
- request-provided rows should win if both exist

## 10. Success Criteria

Phase 1 is successful if:

1. the runtime can automatically produce `5-10` supplement names from the
   existing market snapshot
2. obvious strong names such as `华盛昌` or `松发股份` no longer require manual
   ticker entry
3. those generated names still only surface in:
   - `T3`
   - `T4`
   - clearly labeled reference/report sections
4. the existing event-driven shortlist spine remains untouched

## 11. Non-Goals

Phase 1 does not attempt to:

- create a standalone market scanner outside the shortlist pipeline
- perfectly infer every theme behind a strong stock
- replace event-driven discovery
- promote supplement names into formal execution
- solve intraday momentum trading

## 12. Future Extensions

If Phase 1 works, later phases can add:

- more refined strength heuristics
- better `theme_guess` inference
- better duplicate suppression against existing discovery/event lanes
- more explicit “why this name was auto-selected” reporting

But those should not be part of the first version.

The first version should stay focused on one thing:

- automatically filling the supplement lane with the few strongest names the
  current event-driven system would otherwise miss
