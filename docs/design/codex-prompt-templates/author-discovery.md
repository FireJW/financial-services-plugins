# Codex Task: X Author Discovery

## Goal

Discover new X authors that are good enough to enter the research watchlist
trial tier.

This is not a generic "find finance accounts" task.
The output must be usable by the local screening flow:

- discovery -> `run_author_quality_screen.cmd` -> pass/review/reject
- pass -> `obsidian-kb-local/config/x-source-whitelist.json` tier 2

Quality matters more than count.
Do not fill every gap at any cost.

## Read First

Read these before searching:

- `docs/design/x-signal-triage-codex-collaboration-spec.md`
- `financial-analysis/commands/x-similar-author-discovery.md`
- `financial-analysis/skills/autoresearch-info-index/examples/x-similar-author-discovery.template.json`
- `obsidian-kb-local/config/x-source-whitelist.json`

## Seed Authors Already Tracked

Use these as the current quality bar and style anchor:

- `Ariston_Macro`
- `LinQingV`
- `twikejin`
- `tuolaji2024`
- `aleabitoreddit`
- `jukan05`

## Priority Coverage Gaps

Fill these in order:

1. `consumer_healthcare`
2. `quant_flow_microstructure`
3. `grassroots_research_channel_checks`
4. `contrarian_risk_short`
5. `hk_stock_adr_cross_market`
6. `policy_regulation`

## Hard Constraints

Only return authors who look useful for investment research over time.

Required qualities:

- continuous output, not one-off bursts
- enough signal density to matter
- content still worth rereading after a few days or weeks
- reasoning can survive follow-up checking
- low dependence on pure emotion or engagement farming
- some chance of helping later trade-plan validation, postmortem, or method improvement

Do not return:

- paid course / paid group / private circle / "planet" sellers
- accounts with less than 6 months of history
- pure retweet or repost accounts
- board-hitting / dragon-tiger / pure tape-chasing accounts
- anonymous "insider tip" accounts
- accounts where emotional hype dominates the sample
- accounts with no stable domain focus or no recurring framework

If a gap has no strong candidate, return none for that gap instead of forcing weak names.

## Discovery Instructions

For each coverage gap:

1. find 2-3 candidate authors on X
2. fetch profile metadata
3. fetch 30 recent posts
4. keep raw post text and metadata
5. do not over-classify locally useful fields that the local pipeline will score later
6. if a field is unknown, use `null` or omit it; do not guess

The purpose is to hand structured raw evidence to the local screener, not to
replace the local screener.

## Output Contracts

For each candidate author, produce:

1. one `codex_author_profile`
2. one `codex_post_samples`

Follow the schemas defined in:

- `docs/design/x-signal-triage-codex-collaboration-spec.md`

## Additional Required Fields

In `codex_author_profile`, make sure these are populated:

- `discovery_source`
- `discovery_gap`
- `keyword_overlap_score`
- `bio_relevance_tags`
- `sample_post_count`
- `sample_window_days`
- `sample_stats.avg_posts_per_week`
- `sample_stats.retweet_ratio`
- `sample_stats.media_ratio`
- `sample_stats.avg_text_length`
- `sample_stats.language_distribution`

In `codex_post_samples`, preserve:

- `sample_window_days`
- `sample_stats.avg_posts_per_week`
- `sample_stats.retweet_ratio`
- `sample_stats.media_ratio`
- `sample_stats.avg_text_length`
- `sample_stats.language_distribution`
- `post_url`
- `posted_at`
- `text`
- `is_retweet`
- `is_reply`
- `is_thread_head`
- `thread_length`
- `media_count`
- `like_count`
- `retweet_count`
- `reply_count`
- `quote_count` when available
- `language`
- `outbound_urls`

Important:

- the local screener reads `sample_window_days` and `sample_stats` from the
  post-samples payload first
- so mirror those fields into `codex_post_samples`, not only into
  `codex_author_profile`
- preserve the post text as raw as possible; do not paraphrase or compress it

## Search And Filtering Guidance

Prefer authors who are one of these:

- report-summary amplifiers with real substance
- industry-chain researchers
- recurring framework writers
- flow / positioning interpreters with evidence discipline
- cross-market mappers whose logic is reusable in A-share work

Prefer authors with:

- recurring themes across posts
- named institutions, reports, filings, or data references
- enough output frequency to survive rolling review
- useful depth even when not giving explicit stock picks

Prefer against authors with:

- high reply-only behavior and little standalone content
- recycled market-color posts with no traceable source
- a lot of emotional verbs, certainty language, or "must buy / must sell" framing

Prefer lower false-positive risk over broader coverage.

It is better to return 6 strong candidates than 20 weak ones.

## Output Location

Write files to:

```text
.tmp/codex-handoff/discovery/
  <handle>-profile.json
  <handle>-posts.json
```

If the directory does not exist, create it.

Use one file pair per handle. Do not pack all authors into one giant JSON file.

## Final Console Summary

At the end, print only:

1. candidate handles
2. which gap each one fills
3. any candidates you rejected but almost kept
4. gaps where you found no strong candidate

Do not write a long narrative report.
