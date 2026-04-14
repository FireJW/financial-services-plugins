# X Signal Triage And Codex Collaboration Spec

> Version: 0.2.0  
> Date: 2026-04-13

## 1. Purpose

This spec defines how cloud-side Codex work and local runtime work cooperate
for X author discovery, quality screening, triage, and hit-rate validation.

The design goal is simple:

- let Codex do web discovery and structured handoff
- let local code do deterministic screening and workflow integration
- keep X as a bounded signal layer instead of a free-form research dump

## 2. High-Level Architecture

```text
Codex / Claude / external agent
  -> discovers authors
  -> fetches profile metadata
  -> fetches recent sample posts
  -> optionally spot-checks hit rate
  -> writes structured JSON into .tmp/codex-handoff/

Local pipeline
  -> screens authors with author_quality_screen.py
  -> adds passing authors into x-source-whitelist.json tier 2
  -> uses x-index for signed-session fetch
  -> uses curator + post_triage for per-post scoring
  -> uses scorecard fields for later promotion / demotion
```

## 3. Responsibility Split

### 3.1 Codex-side responsibilities

- discover candidate authors
- fetch profile metadata
- fetch recent sample posts
- preserve raw post text and basic metadata
- optionally run hit-rate spot checks
- write results into `.tmp/codex-handoff/`

### 3.2 Local responsibilities

- run `author_quality_screen.py`
- decide `pass | review | reject`
- manage `obsidian-kb-local/config/x-source-whitelist.json`
- run signed-session `x-index`
- run curator + `post_triage.py`
- maintain rolling scorecard fields

## 4. Core Design Rules

1. Codex should hand off raw structured evidence, not overfit local labels.
2. Local code remains the authority for pass/review/reject.
3. X is a bounded signal layer, not the main evidence contract.
4. Author discovery quality matters more than coverage count.
5. Hit-rate checks should be conservative, not flattering.

## 5. Handoff Directory Layout

```text
.tmp/codex-handoff/
  README.md
  discovery/
    README.md
    <handle>-profile.json
    <handle>-posts.json
  validation/
    README.md
    <handle>-hit-rate.json
```

Use one file set per handle. Do not pack everything into one giant JSON blob.

## 6. Data Contracts

### 6.1 codex_author_profile

This is the per-author discovery record.

```jsonc
{
  "$schema": "codex_author_profile_v1",
  "handle": "SomeAuthor",
  "platform": "x",
  "profile_url": "https://x.com/SomeAuthor",
  "display_name": "Some Author",
  "bio": "Former sell-side analyst",
  "follower_count": 12400,
  "following_count": 320,
  "account_created_at": "2021-03-15",
  "verified": false,
  "fetched_at": "2026-04-13T14:00:00+08:00",

  "discovery_source": "similar_author_expansion",
  "discovery_gap": "consumer_healthcare",
  "discovery_seed_authors": ["Ariston_Macro", "LinQingV"],
  "keyword_overlap_score": 0.72,
  "bio_relevance_tags": ["sell-side", "macro", "A-share"],

  "sample_post_count": 30,
  "sample_window_days": 30,
  "sample_stats": {
    "avg_posts_per_week": 8.2,
    "retweet_ratio": 0.15,
    "media_ratio": 0.45,
    "avg_text_length": 280,
    "language_distribution": {
      "zh": 0.7,
      "en": 0.3
    }
  }
}
```

### 6.2 codex_post_samples

This is the raw sample-post handoff for one author.

Important:

- local screening reads `sample_window_days` and `sample_stats` from this
  payload first
- so include those fields here too

```jsonc
{
  "$schema": "codex_post_samples_v1",
  "handle": "SomeAuthor",
  "platform": "x",
  "fetched_at": "2026-04-13T14:00:00+08:00",
  "sample_window_days": 30,
  "sample_stats": {
    "avg_posts_per_week": 8.2,
    "retweet_ratio": 0.15,
    "media_ratio": 0.45,
    "avg_text_length": 280,
    "language_distribution": {
      "zh": 0.7,
      "en": 0.3
    }
  },
  "posts": [
    {
      "post_url": "https://x.com/SomeAuthor/status/123456",
      "posted_at": "2026-04-12T09:30:00+08:00",
      "text": "raw post text here",
      "is_retweet": false,
      "is_reply": false,
      "is_thread_head": true,
      "thread_length": 5,
      "media_count": 3,
      "like_count": 42,
      "retweet_count": 15,
      "reply_count": 8,
      "quote_count": 3,
      "language": "zh",
      "outbound_urls": ["https://example.com/report.pdf"]
    }
  ]
}
```

### 6.3 codex_hit_rate_check

This is the per-author hit-rate validation result.

```jsonc
{
  "$schema": "codex_hit_rate_check_v1",
  "handle": "SomeAuthor",
  "check_window_days": 90,
  "checked_at": "2026-04-13T14:00:00+08:00",
  "picks": [
    {
      "post_url": "https://x.com/SomeAuthor/status/111",
      "posted_at": "2026-02-10",
      "ticker_mentioned": "600519.SH",
      "direction": "bullish",
      "market": "CN",
      "benchmark_symbol": "000300.SH",
      "price_reference_rule": "same_day_close",
      "price_at_post": 1680.0,
      "price_after_30d": 1750.0,
      "return_30d": 0.042,
      "benchmark_return_30d": 0.015,
      "beat_benchmark": true
    }
  ],
  "summary": {
    "total_picks": 12,
    "beat_benchmark_count": 8,
    "hit_rate": 0.667,
    "avg_excess_return": 0.027,
    "pending_count": 1,
    "excluded_count": 4
  },
  "caveats": [
    "Small sample size"
  ]
}
```

## 7. Local Screening Expectations

`author_quality_screen.py` currently evaluates:

- monetization signals
- emotion-word ratio
- sample size
- retweet ratio
- post frequency
- source citation rate
- recurring framework / theme recurrence

This means Codex-side discovery should preserve enough raw text and sample
statistics for those checks to work.

## 8. Unified Post Schema After Local Processing

After local processing, X and Reddit posts may converge into a shared internal
shape like this:

```jsonc
{
  "platform": "x",
  "source_id": "Ariston_Macro",
  "source_type": "author",
  "post_url": "https://x.com/...",
  "posted_at": "2026-04-12T09:30:00+08:00",

  "text": "...",
  "media_count": 3,
  "thread_length": 5,
  "summary": "first 280 chars",

  "classification": "sell_side_summary",

  "triage": {
    "tradability": "directional",
    "verifiability": "sourced",
    "time_value": "durable_month",
    "triage_score": 0.78,
    "triage_method": "keyword_heuristic"
  },

  "content_hash": "sha256:abc123...",
  "dedup_status": "unique",
  "theme_tags": ["AI_infra", "industry_chain"],

  "reddit_metadata": null
}
```

## 9. Scorecard Shape In x-source-whitelist.json

The local whitelist is already `version: 2` and supports:

- per-author `tier`
- per-author `refresh_hours`
- per-author `scorecard`
- rolling `scorecard.hit_rate`

Representative shape:

```jsonc
{
  "handle": "Ariston_Macro",
  "tier": 0,
  "refresh_hours": 48,
  "status": "allowlisted",
  "scorecard": {
    "tracked_since": "2026-04-06",
    "last_review": "2026-04-13",
    "window_days": 90,
    "posts_indexed": 48,
    "posts_promoted": 12,
    "promotion_rate": 0.25,
    "source_citation_rate": 0.65,
    "avg_logic_depth": 2.4,
    "framework_count": 3,
    "tradability_profile": {
      "actionable": 0.10,
      "directional": 0.35,
      "contextual": 0.45,
      "noise": 0.10
    },
    "time_value_profile": {
      "perishable_24h": 0.20,
      "perishable_week": 0.35,
      "durable_month": 0.30,
      "durable_quarter_plus": 0.15
    },
    "hit_rate": null,
    "hit_rate_checked_at": null,
    "hit_rate_sample_size": null,
    "promotion_candidate": false,
    "demotion_candidate": false,
    "demotion_reason": null
  }
}
```

## 10. Triage Scoring Rules

`post_triage.py` currently uses deterministic keyword heuristics for:

- `tradability`
  - `actionable | directional | contextual | noise`
- `verifiability`
  - `sourced | logic_chain | opinion_only | unverifiable`
- `time_value`
  - `perishable_24h | perishable_week | durable_month | durable_quarter_plus`

Composite score is a 0-1 weighted score across those three dimensions.

## 11. Hit-Rate Validation Rules

Use conservative rules:

1. only count explicit directional posts
2. ignore vague commentary
3. if direction is ambiguous, exclude
4. if ticker mapping is ambiguous, exclude
5. keep benchmark choice explicit per pick

Price-reference rule:

- post during market hours -> same-day close
- post after market close -> next trading-day close
- post on non-trading day -> next trading-day close

Do not switch conventions pick by pick.

## 12. Recommended Operator Flow

### 12.1 Discovery flow

1. send `docs/design/codex-prompt-templates/author-discovery.md` to Codex
2. receive files under `.tmp/codex-handoff/discovery/`
3. run:
   - `financial-analysis/skills/autoresearch-info-index/scripts/run_author_quality_screen.cmd .tmp/codex-handoff/discovery/`
4. move passing authors into `obsidian-kb-local/config/x-source-whitelist.json` tier 2

### 12.2 Validation flow

1. send `docs/design/codex-prompt-templates/hit-rate-validation.md` to Codex
2. receive files under `.tmp/codex-handoff/validation/`
3. update:
   - `scorecard.hit_rate`
   - `scorecard.hit_rate_checked_at`
   - `scorecard.hit_rate_sample_size`
4. decide promotion / demotion later from combined quality + hit-rate evidence

## 13. File Locations

| Artifact | Path |
|----------|------|
| This spec | `docs/design/x-signal-triage-codex-collaboration-spec.md` |
| Discovery prompt | `docs/design/codex-prompt-templates/author-discovery.md` |
| Hit-rate prompt | `docs/design/codex-prompt-templates/hit-rate-validation.md` |
| Whitelist | `obsidian-kb-local/config/x-source-whitelist.json` |
| Quality screen | `financial-analysis/skills/autoresearch-info-index/scripts/author_quality_screen.py` |
| Quality screen runner | `financial-analysis/skills/autoresearch-info-index/scripts/run_author_quality_screen.cmd` |
| Triage scoring | `financial-analysis/skills/autoresearch-info-index/scripts/post_triage.py` |
| Similar-author command | `financial-analysis/commands/x-similar-author-discovery.md` |
| Handoff root | `.tmp/codex-handoff/` |
