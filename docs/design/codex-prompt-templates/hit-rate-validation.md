# Codex Task: Author Hit Rate Validation

## Goal

Spot-check whether tracked X authors have real predictive value, instead of
only sounding smart.

This task is for scorecard maintenance, not for generic author commentary.
The output should be usable to update:

- `obsidian-kb-local/config/x-source-whitelist.json`
- `scorecard.hit_rate`
- author promotion / demotion decisions

Do not optimize for finding flattering examples.
Use conservative inclusion rules.

## Read First

Read these before validating:

- `docs/design/x-signal-triage-codex-collaboration-spec.md`
- `obsidian-kb-local/config/x-source-whitelist.json`
- `docs/design/codex-prompt-templates/author-discovery.md`

## Authors To Validate

Replace this list when running:

- `Ariston_Macro`
- `LinQingV`
- `twikejin`

## Validation Rules

For each author:

1. look back 90 days
2. find posts with an explicit directional view on a specific ticker
3. ignore vague macro mood posts or posts with no actionable direction
4. for each valid pick:
   - record the ticker
   - record bullish or bearish direction
   - record the post date
   - get the closing price on the post date
   - get the closing price 30 calendar days later
   - get the benchmark return over the same 30-day window
5. decide whether the call beat the benchmark

If a post uses non-standard language, normalize direction conservatively:

- `buy`, `bullish`, `overweight`, `best expression`, `target up` -> `bullish`
- `sell`, `bearish`, `avoid`, `short`, `do not touch` -> `bearish`
- neutral, hedged, or mixed wording -> exclude

## What Counts As A Valid Pick

Count it only if the post contains at least one of these:

- explicit bullish / bearish stance
- buy / sell / avoid language
- target price or target range
- clear "best expression" / "do not touch" style directional wording

Do not count:

- pure industry commentary
- broad basket talk with no ticker-level direction
- reposts of someone else without owned view
- ambiguous or hedged mentions with no directional stance
- pure sector or macro framework posts with no ticker-level view

If ticker mapping is ambiguous, exclude the post and mention it in caveats.

## Benchmark Rules

Use:

- `000300.SH` / CSI 300 for A-share names
- Hang Seng benchmark for HK names
- suitable US benchmark only if the author is being checked on US names

If one author mixes markets, keep benchmark choice explicit per pick.

Price-reference rule:

- if the post lands during market hours, use that market's same-day close
- if the post lands after market close, use the next trading day's close
- if the post lands on a non-trading day, use the next trading day's close

Be explicit and consistent. Do not switch conventions pick by pick.

## Output Contract

Return one `codex_hit_rate_check` JSON per author.

Use the schema in:

- `docs/design/x-signal-triage-codex-collaboration-spec.md`

Minimum required fields:

- `handle`
- `check_window_days`
- `checked_at`
- `picks[]`
- `summary.total_picks`
- `summary.beat_benchmark_count`
- `summary.hit_rate`

When available, also include:

- `summary.avg_excess_return`
- `summary.pending_count`
- `summary.excluded_count`

## Per-Pick Required Fields

For each pick, preserve:

- `post_url`
- `posted_at`
- `ticker_mentioned`
- `direction`
- `price_at_post`
- `price_after_30d`
- `return_30d`
- `benchmark_return_30d`
- `beat_benchmark`

When available, also include:

- `benchmark_symbol`
- `market`
- `price_reference_rule`

If the 30-day-later price is not yet available:

- mark the pick as pending
- do not silently drop it

If the author has too few valid picks to say much:

- still write the JSON
- keep the small sample visible in caveats
- do not overstate confidence

## Output Location

Write files to:

```text
.tmp/codex-handoff/validation/
  <handle>-hit-rate.json
```

If the directory does not exist, create it.

Use one JSON file per author. Do not merge all authors into one file.

## Final Console Summary

At the end, print only:

1. author
2. total picks
3. hit rate
4. obvious caveats
5. whether the sample is too shallow for a strong tiering decision

Do not write a long narrative report.
