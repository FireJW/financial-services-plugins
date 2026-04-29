# Emergent Theme Promotion For Shortlist Design

**Date:** 2026-04-29  
**Status:** Draft design  
**Scope:** Add a repository-native way for non-preconfigured themes that are
simultaneously strengthened by X discussion, earnings/news flow, and market
behavior to participate in the formal shortlist ranking path instead of being
limited to manual watchlist handling.

## 1. Goal

The current shortlist stack should stop missing themes that were not manually
preloaded into:

- `strategic_base_watch_themes`
- `TOPIC_ALIASES`
- `run_theme_supplements.py`
- explicit `x_index` query presets

The target class of misses is:

- many relevant X users discussing the same direction
- earnings / announcement flow broadly confirming that direction
- market behavior showing non-trivial confirmation
- but the direction not belonging to the current preconfigured theme set

The design must allow such themes to:

- be detected as candidate themes
- enter the active theme pool for the current run
- participate in formal shortlist ranking
- still respect existing execution discipline and data-quality gates

This is explicitly broader than solving one name such as `002709.SZ 天赐材料`.

## 2. Root Cause

The miss is caused by two independent failures that stack on top of each other.

### 2.1 Data-path failure

`天赐材料` was dropped in the 2026-04-27 rerun because of:

- `bars_fetch_failed`

The relevant artifact already records:

- `drop_reason = bars_fetch_failed`
- `bars_fetch_error = Eastmoney request failed after 3 attempts: Remote end closed connection without response`

This means the stock never reached full technical / execution scoring.

### 2.2 Theme-entry failure

Even without the bars failure, the current system has no durable way to elevate
many non-preconfigured themes into active scanning.

Current configured strategic themes are:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

That means themes such as:

- lithium upstream / battery materials
- rare earth / strategic materials
- copper foil / PCB-adjacent materials
- other emergent post-earnings sectors

are structurally disadvantaged unless they are:

- manually added to the request
- manually added to the supplement script
- or happen to be captured via generic market-strength ranking only

### 2.3 X-index dependency on explicit prompts

`x_index_runtime.py` derives search behavior from explicit request surfaces:

- `keywords`
- `phrase_clues`
- `entity_clues`
- `query_overrides`

It is not an open-ended topic miner.

### 2.4 Weekend candidate dependency on predeclared aliases

`weekend_market_candidate_runtime.py` only recognizes topics that exist in
`TOPIC_ALIASES`.

If a direction is not already represented there, repeated X discussion does not
automatically become a first-class topic inside the shortlist pipeline.

## 3. Non-Goals

This design does **not** attempt to:

- fully automate unconstrained topic discovery for the entire market
- eliminate the existing strategic theme pool
- bypass technical / execution quality controls
- force any theme directly into `T1` / `T2`
- solve all `bars_fetch_failed` problems by itself

## 4. Product Shape

Add a new intermediate theme family:

- `emergent_theme_candidates`

This family sits between:

- raw signal collection (`x_index`, earnings/news, market snapshots)

and:

- active shortlist theme participation

It should behave like a promotion layer:

1. collect evidence for themes not already preconfigured
2. score them
3. promote qualified ones into the active theme pool
4. allow stocks aligned with those promoted themes to participate in formal
   shortlist ranking

## 5. Two Approaches Considered

### Approach A: Expand the static strategic theme pool

Add more themes manually:

- lithium upstream
- rare earth
- copper foil
- chemical materials

Pros:

- simple
- low implementation risk

Cons:

- endless manual maintenance
- still misses the next non-preconfigured theme
- does not react to changing discussion / earnings clusters

### Approach B: Pure market-strength fallback

Rely on `market_strength_candidates` to catch overlooked sectors.

Pros:

- no new theme machinery

Cons:

- catches names, not directions
- too late for many early or mid-stage opportunities
- cannot explain theme-level conviction

### Approach C: Recommended

Add `emergent_theme_candidates` driven by:

- X discussion density
- earnings/news confirmation density
- market confirmation density

This is the recommended path because it solves the real problem:

- not just missing one stock
- but missing entire non-preconfigured opportunity clusters

## 6. Emergent Theme Inputs

Phase 1 should use three signal families.

### 6.1 X discussion signal

Source:

- repo-native `x_index` results
- reused relevant recent `x_index` results when still fresh

Desired extracted information:

- repeated theme words / aliases
- repeated company-cluster mentions
- repeated industry phrases from tracked accounts or search results

Examples:

- `锂电上游`
- `电解液`
- `六氟磷酸锂`
- `正极材料`
- `铜箔`
- `稀土`

### 6.2 Earnings / announcement signal

Source:

- structured earnings-preview / official-report inputs already used in shortlist
- local announcement enrichments when available
- same-day manually or automatically assembled earnings confirmation rows

Desired extracted information:

- multiple companies in the same direction showing strong revenue / profit trends
- same-theme earnings narrative concentration
- clear industry-level readthrough rather than isolated single-name beats

### 6.3 Market confirmation signal

Source:

- existing universe snapshot
- market-strength generator
- setup-launch generator
- direction-aligned assessed candidates

Desired extracted information:

- several related names showing unusual strength
- or at least one clear leader plus multiple aligned secondary names

## 7. Emergent Theme Contract

Add an internal normalized structure:

```json
{
  "theme_name": "lithium_upstream",
  "theme_label": "锂电上游 / 电解液材料",
  "source_signals": {
    "x_discussion_strength": "high",
    "earnings_confirmation_strength": "high",
    "market_confirmation_strength": "medium"
  },
  "supporting_names": [
    "002709.SZ",
    "002466.SZ",
    "002407.SZ"
  ],
  "promotion_score": 0.78,
  "promotion_reason": "X discussion, earnings confirmation, and aligned market action all reached promotion threshold."
}
```

Required fields:

- `theme_name`
- `theme_label`
- `source_signals`
- `supporting_names`
- `promotion_score`
- `promotion_reason`

## 8. Promotion Logic

Phase 1 should stay heuristic and explainable.

### 8.1 Promotion dimensions

Use three main dimensions:

- `x_discussion_strength`
- `earnings_confirmation_strength`
- `market_confirmation_strength`

Optional fourth dimension:

- `theme_density`

`theme_density` answers:

- how concentrated the evidence is around a coherent direction

### 8.2 Phase 1 scoring

Phase 1 does not need a complex statistical model.

It can use coarse levels:

- `high`
- `medium`
- `low`

Then combine them into a bounded promotion score.

Recommended intuition:

- X alone is not enough
- earnings alone is not enough
- market alone is not enough
- at least two of the three must be meaningful

### 8.3 Promotion threshold

Promote into the active theme pool when:

- at least two major dimensions are `medium` or better
- and at least one dimension is `high`

This avoids promoting thin or noisy themes.

## 9. Active Theme Pool Integration

Today the effective active theme pool is mostly:

- weekend candidate themes
- `strategic_base_watch_themes`

After this change it becomes:

- weekend candidate themes
- `strategic_base_watch_themes`
- promoted `emergent_theme_candidates`

Proposed internal merge order:

1. explicit request themes
2. weekend candidate themes
3. strategic base-watch themes
4. promoted emergent themes

Deduplicate by `theme_name`.

## 10. Shortlist Participation Rules

User requirement for this design:

- promoted emergent themes are allowed to participate directly in formal
  shortlist ranking

That means they are **not** limited to report-only observation.

But this should still preserve discipline.

### 10.1 Allowed

- emergent themes can influence:
  - candidate theme pools
  - setup-launch theme pools
  - supplement discovery context
  - direction-layer ranking
  - formal shortlist competition

### 10.2 Not Allowed

Promotion of the theme does **not** mean:

- automatic `T1`
- automatic `T2`
- automatic buy recommendation

Names aligned to promoted themes still need to clear the existing execution
gates or their degraded equivalents.

## 11. Degraded Data Handling

The current behavior is too binary when data fails:

- theme may be right
- name may be relevant
- but `bars_fetch_failed` makes it disappear as an execution object

Phase 1 should add a degraded but visible state for theme-confirmed names.

Proposed behavior:

- if a name is strongly aligned to a promoted emergent theme
- and the theme itself is promoted
- but bars fail

then preserve the name as:

- `data_blocked_theme_confirmed`

This does not make it executable.

It does make it visible in the report so the system does not behave as if the
name never existed.

## 12. Minimum Implementation Surface

Keep the change narrow.

Phase 1 should add:

1. a builder for `emergent_theme_candidates`
2. a promotion merge into the active theme pool
3. a small report surface for promoted emergent themes
4. a degraded visibility state for theme-confirmed but data-blocked names

Do **not** rewrite:

- the entire shortlist scoring engine
- the entire X-index pipeline
- all existing strategic theme machinery

## 13. Reporting

Add a report section such as:

- `新兴共振主题`

Each promoted theme should show:

- ranking / promotion order
- why it was promoted
- key supporting names
- strongest sources
- whether it entered formal shortlist competition

If a relevant aligned name was blocked by data failure, explicitly show:

- `theme_confirmed_but_data_blocked`

## 14. Success Criteria

This change succeeds if:

1. directions like lithium upstream can be promoted without being manually
   preloaded into the strategic theme pool
2. names such as `天赐材料` are no longer silently absent when the theme is
   strong but bars fail
3. promoted emergent themes can influence formal shortlist ranking
4. noisy one-off themes do not flood the active theme pool

## 15. Future Extensions

Later phases can add:

- auto-derived alias expansion for newly promoted themes
- better topic clustering from X and earnings text
- historical validation of promotion-score thresholds
- automated addition of recurring emergent themes into the long-lived strategic
  theme pool when they repeatedly promote across runs
