# Handoff: Daily Trade Plan Validation And X Cause Analysis

> as of 2026-04-13

## Goal

Turn the repo's current trading-plan capabilities into one repeatable daily loop:

1. read the latest trade plan
2. validate it with intraday and postclose market data
3. review the original plan logic
4. use X as a bounded supplemental explanation layer
5. accumulate real win-rate, failure modes, and rule updates for incremental improvement

## Current State

- Existing plan-generation and review chain:
  - `obsidian-kb-local/scripts/draft-trading-plan.mjs`
  - `obsidian-kb-local/scripts/legendary-investor-workbench.mjs`
  - `obsidian-kb-local/scripts/legendary-investor-runner.mjs`
  - `obsidian-kb-local/scripts/legendary-investor-decision.mjs`
  - `obsidian-kb-local/scripts/legendary-investor-review.mjs`
- Existing handoff artifacts:
  - `obsidian-kb-local/handoff/legendary-investor-current-plan.md`
  - `obsidian-kb-local/handoff/legendary-investor-last-run.json`
  - `obsidian-kb-local/handoff/legendary-investor-last-decision.json`
  - `obsidian-kb-local/handoff/legendary-investor-last-review.json`
- Existing X-native routes:
  - `financial-analysis/commands/x-index.md`
  - `financial-analysis/commands/x-market-intelligence-watchlist.md`
  - `financial-analysis/commands/x-stock-picker-style.md`
  - `financial-analysis/commands/x-style-assisted-shortlist.md`
- Existing X watchlist inputs:
  - `docs/runtime/x-market-intelligence-watchlist-playbook.md`
  - `financial-analysis/skills/autoresearch-info-index/examples/x-market-intelligence-watchlist-workflow.template.json`
  - `financial-analysis/skills/autoresearch-info-index/examples/x-index-market-intelligence-watchlist-profile-recent.template.json`
  - `obsidian-kb-local/config/x-source-whitelist.json`
- Existing author-quality support pieces already present:
  - `financial-analysis/skills/autoresearch-info-index/scripts/author_quality_screen.py`
  - `financial-analysis/skills/autoresearch-info-index/scripts/run_author_quality_screen.cmd`
  - `financial-analysis/commands/x-similar-author-discovery.md`
  - `financial-analysis/skills/autoresearch-info-index/examples/x-similar-author-discovery.template.json`

## What Is Missing

The main gap is not "another prompt". The main gap is this loop is not yet tight:

`plan -> intraday facts -> postclose facts -> review verdict -> x cause analysis -> method delta`

More specifically, we still need:

1. one daily validation entrypoint
2. one small reusable facts-file contract
3. one bounded X integration layer that helps explain, but does not override market evidence
4. one ledger that can accumulate real win-rate, failure modes, and rule changes

## Adjacent X Author Indexing Loop

There is already an adjacent workflow for author discovery and validation.
Treat it as a support layer for the X side of this project, not as the first
milestone of the daily validation loop.

The operator flow proposed earlier was:

1. send an author-discovery prompt to Codex
2. write discovery outputs under a handoff folder
3. run `run_author_quality_screen.cmd` on the discovery folder
4. move passing authors into `x-source-whitelist.json` tier 2
5. let weekly `x-index -> curator` runs accumulate triage labels
6. periodically review `scorecard.hit_rate` and promote / demote authors

Important note:

- this is no longer purely hypothetical
- `obsidian-kb-local/config/x-source-whitelist.json` is already `version: 2`
- it already has:
  - `tier_definitions`
  - per-author `tier`
  - per-author `refresh_hours`
  - per-author `scorecard`
  - `scorecard.hit_rate`

So for this task, do not redesign the author-indexing loop from scratch.
Instead:

1. reuse it where it helps X supplementation quality
2. keep it clearly secondary to the daily trade-plan validation loop
3. only extend it when a real validation need depends on better author quality

## Read First: Minimal Core Files

Read only these first:

- `obsidian-kb-local/scripts/legendary-investor-workbench.mjs`
- `obsidian-kb-local/scripts/legendary-investor-runner.mjs`
- `obsidian-kb-local/scripts/legendary-investor-decision.mjs`
- `obsidian-kb-local/scripts/legendary-investor-review.mjs`
- `obsidian-kb-local/src/legendary-investor-reasoner.mjs`
- `obsidian-kb-local/src/legendary-investor-decision.mjs`
- `obsidian-kb-local/src/legendary-investor-review.mjs`
- `obsidian-kb-local/handoff/legendary-investor-current-plan.md`
- `obsidian-kb-local/handoff/legendary-investor-last-run.json`
- `financial-analysis/commands/x-market-intelligence-watchlist.md`
- `financial-analysis/commands/x-stock-picker-style.md`
- `financial-analysis/skills/autoresearch-info-index/scripts/run_author_quality_screen.cmd`
- `obsidian-kb-local/config/x-source-whitelist.json`
- `docs/runtime/x-market-intelligence-watchlist-playbook.md`
- `docs/runtime/x-style-assisted-shortlist-playbook.md`

Only expand if blocked:

- `financial-analysis/commands/x-index.md`
- `financial-analysis/commands/x-similar-author-discovery.md`
- `financial-analysis/commands/x-style-assisted-shortlist.md`
- `financial-analysis/commands/month-end-shortlist.md`
- `financial-analysis/skills/autoresearch-info-index/SKILL.md`

## Hard Decisions

1. Reuse the native routes first. Do not build a parallel system.
   - keep plan structure on `legendary-investor-*`
   - keep X supplementation on `x-index` / `x-market-intelligence-watchlist` / `x-stock-picker-style`

2. Build the daily validation loop first. Do not start with broad automation.
   - first make it easy to answer: how much of today's plan worked, what failed, and why
   - only then consider scheduling, batching, or auto-writeback

3. X is a supplemental explanation layer, not the main evidence layer.
   - price, turnover, close behavior, invalidation hits, and execution outcome must come from market data first
   - X can help explain why the market moved or what the plan may have missed
   - do not promote a single X post into fact confirmation

4. Force `as_of`.
   - both intraday and postclose validation must use absolute timestamps
   - do not leave "today", "just now", or similar relative phrasing unresolved

5. Keep two output layers separate.
   - `trade_outcome`: how this plan performed today
   - `method_delta`: what this result should change in the method

## Recommended Minimum Contracts

If you add new contracts, keep them small.

### 1. Intraday Facts

Suggested minimum fields:

- `trade_day`
- `as_of`
- `plan_source`
- `market`
- `ticker_snapshots[]`
- `fact_flags{}`
- `operator_notes`

### 2. Postclose Facts

Suggested minimum fields:

- `trade_day`
- `as_of`
- `ticker_snapshots[]`
- `fact_flags{}`
- `execution_result`
- `missed_or_wrong_assumptions[]`

### 3. Validation Record

Suggested minimum fields:

- `plan_id`
- `trade_day`
- `status = success | partial | fail | too_early`
- `decision_verdict`
- `review_verdict`
- `x_supporting_signals[]`
- `x_contradicting_signals[]`
- `why_right[]`
- `why_wrong[]`
- `method_delta[]`
- `next_rule_changes[]`

## Native Routing For X

Default order:

1. `x-market-intelligence-watchlist`
   - best for recent posts from already-screened high-quality accounts
   - lower noise than global keyword search

2. `x-index` profile recent
   - best for adding recent context around one handle

3. `x-stock-picker-style`
   - best for reviewing how an author's method led to a right call, miss, or bad read
   - not the main route for same-day validation

4. `x-style-assisted-shortlist`
   - only connect this after real results are ready to feed back into shortlist ranking rules

## How The Author Indexing Loop Fits

Use the author-indexing loop only as a quality-control layer for X inputs:

1. `x-similar-author-discovery`
   - finds candidate authors
2. `run_author_quality_screen.cmd`
   - screens them into pass / review / reject
3. `x-source-whitelist.json`
   - stores tier, refresh cadence, and scorecard state
4. weekly `x-index -> curator`
   - accumulates triage behavior
5. periodic hit-rate review
   - updates author tiering over time

Do not let this support loop delay the first daily validation milestone.

## What Good Looks Like

The valuable outcome here is not "one more report". It is:

1. given one trade plan, we can run one intraday validation and one postclose validation
2. the output clearly says `success`, `partial`, `fail`, or `too_early`
3. the system can explain:
   - which layer was right
   - which layer was wrong
   - whether the problem was facts, timing, confirmation, execution, or bad X interpretation
4. the result becomes reusable rule updates for the next plan

## Recommended Optimization Order

Use this order:

1. `P0`
   - build one minimal daily validation loop
   - prefer one small script or wrapper over large rewrites

2. `P1`
   - define and persist `intraday facts`, `postclose facts`, and `validation record`

3. `P2`
   - add X supplementation
   - start with watchlist / profile-recent, not broad noisy search

4. `P3`
   - add `win_rate / failure_mode / rule_delta` aggregation
   - feed real results back into shortlist or workbench rules

## Verification Baseline

At minimum, keep these runnable:

```powershell
cmd /c "cd obsidian-kb-local && npm test"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-workbench.mjs --plan-file handoff/legendary-investor-current-plan.md --dry-run"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-runner.mjs --mode preopen --json-file handoff/legendary-investor-last-run.json"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-runner.mjs --mode postclose --json-file handoff/legendary-investor-last-run.json"
```

If you add a new daily validation entrypoint, add its own minimal dry-run or fixture test too.

## Do Not Do First

- do not start with full automation
- do not start with Reddit
- do not start with a broad database
- do not let X become the main evidence
- do not spend the first pass on wording or doctrine polish without real-result writeback

## Best Next Step

Make this chain stable first:

`one plan + one intraday facts file + one postclose facts file + one X supplement result -> one validation record`

Only after this is stable do win-rate stats and method iteration have a real foundation.
