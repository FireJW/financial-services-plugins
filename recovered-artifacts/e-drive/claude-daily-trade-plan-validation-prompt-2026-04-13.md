You are not doing a generic trade recap. You are turning the repo's current capabilities into one `daily trade plan validation loop`.

Read first:

- `.claude/handoff/claude-daily-trade-plan-validation-handoff-2026-04-13.md`
- `obsidian-kb-local/scripts/legendary-investor-workbench.mjs`
- `obsidian-kb-local/scripts/legendary-investor-runner.mjs`
- `obsidian-kb-local/scripts/legendary-investor-decision.mjs`
- `obsidian-kb-local/scripts/legendary-investor-review.mjs`
- `obsidian-kb-local/src/legendary-investor-reasoner.mjs`
- `obsidian-kb-local/src/legendary-investor-decision.mjs`
- `obsidian-kb-local/src/legendary-investor-review.mjs`
- `obsidian-kb-local/handoff/legendary-investor-current-plan.md`
- `obsidian-kb-local/handoff/legendary-investor-last-run.json`
- `obsidian-kb-local/handoff/legendary-investor-last-decision.json`
- `obsidian-kb-local/handoff/legendary-investor-last-review.json`
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

## Goal

Use each trading day's latest intraday and postclose data to validate whether a trade plan succeeded, failed, or only partially worked. Review the plan-generation logic. Use X as supplemental explanation. Then make the stock-selection method improve from real outcomes instead of static reasoning.

## Priority

1. Reuse native routes first.
   - keep plan logic on `legendary-investor-*`
   - keep X supplementation on `x-market-intelligence-watchlist` / `x-index` / `x-stock-picker-style`

2. Build one minimal full loop.
   - `plan -> intraday facts -> postclose facts -> review -> x cause analysis -> method delta`

3. Land stable artifacts first.
   - only after that, think about automation or aggregation

## Hard Constraints

- force absolute timestamps with `as_of`
- keep `trade_outcome` separate from `method_delta`
- X is supplemental, not main evidence
- do not redesign the author-indexing loop from scratch if existing pieces already cover it
- do not start with Reddit
- do not start with large automation or database work
- do not only add prompts without reusable artifact contracts

## Suggested Minimum Deliverable

Prefer this over a large refactor:

1. one new daily validation entrypoint
   - a small script or wrapper is fine
   - it should connect the existing `decision / review / dashboard / x supplement` pieces

2. three small contracts
   - `intraday facts`
   - `postclose facts`
   - `validation record`

3. one clear output
   - `success | partial | fail | too_early`
   - why it worked
   - why it failed
   - what was wrong at the fact layer
   - what was wrong at the timing / confirmation / execution layer
   - what X helped explain
   - what rules should change next time

## X Routing Order

Default order:

1. `x-market-intelligence-watchlist`
   - use this first for recent posts from already-screened accounts

2. `x-index` profile recent
   - use this when one handle needs more recent context

3. `x-stock-picker-style`
   - use this when you need to review how one author's method worked or failed
   - do not use it as the main same-day validation route

4. `x-style-assisted-shortlist`
   - only connect this after real outcomes are ready to feed back into shortlist ranking

## Existing Author Quality Loop

There is already an adjacent author-quality workflow. Reuse it instead of inventing a new one.

Current usable pieces already exist:

- `x-similar-author-discovery`
- `run_author_quality_screen.cmd`
- `obsidian-kb-local/config/x-source-whitelist.json`
  - already supports `tier`
  - already supports `refresh_hours`
  - already supports `scorecard.hit_rate`

Treat that loop as support infrastructure for X-quality control:

1. discover candidate authors
2. screen them into pass / review / reject
3. move passing authors into whitelist tier 2
4. let recurring X capture accumulate triage evidence
5. review hit rate later for promotion / demotion

Do not let this side loop take priority over the first working daily validation loop.

## Recommended Implementation Order

1. inspect the current `legendary-investor` inputs and outputs
2. define the smallest useful `facts-file` and `validation-record`
3. add one minimal daily validation entrypoint
4. add X supplementation
5. connect the existing author-quality loop only where it improves X signal quality
6. add `win_rate / failure_mode` aggregation last

## If You Change Code

Prioritize:

- `obsidian-kb-local/scripts/legendary-investor-runner.mjs`
- `obsidian-kb-local/scripts/legendary-investor-decision.mjs`
- `obsidian-kb-local/scripts/legendary-investor-review.mjs`
- `obsidian-kb-local/src/legendary-investor-decision.mjs`
- `obsidian-kb-local/src/legendary-investor-review.mjs`
- if needed, add one small script under `obsidian-kb-local/scripts/`

If you connect X supplementation, reuse:

- `financial-analysis/commands/x-market-intelligence-watchlist.md`
- `financial-analysis/commands/x-stock-picker-style.md`

## Verification

At minimum run:

```powershell
cmd /c "cd obsidian-kb-local && npm test"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-workbench.mjs --plan-file handoff/legendary-investor-current-plan.md --dry-run"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-runner.mjs --mode preopen --json-file handoff/legendary-investor-last-run.json"
cmd /c "cd obsidian-kb-local && node scripts/legendary-investor-runner.mjs --mode postclose --json-file handoff/legendary-investor-last-run.json"
```

If you add a daily validation entrypoint, add its own minimal test or fixture too.

## Final Response

Keep the final answer direct. Only say:

- which files changed
- how the new loop runs
- how intraday and postclose data are fed in
- how X supplementation is connected
- how the existing author-quality loop is reused
- how real win-rate and failure modes can be accumulated later
- what you deliberately did not build yet, and why

Do not give a long roadmap.
Do not stay at analysis only.
Ship the smallest valuable loop first.
