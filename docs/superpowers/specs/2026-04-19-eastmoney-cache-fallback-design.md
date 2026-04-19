# Eastmoney Cache Fallback Design

Date: 2026-04-19
Status: Proposed
Owner: Codex
Related:
- `docs/superpowers/specs/2026-04-19-bars-fallback-observation-rescue-design.md`
- `docs/superpowers/plans/2026-04-19-bars-fallback-observation-rescue-implementation.md`

## 1. Goal

Add a practical fallback path for mainland A-share shortlist runs when live Eastmoney bars fail but repo-local Eastmoney cache data is already available.

This design keeps Eastmoney as the primary source and reuses the existing `.tmp/tradingagents-eastmoney-cache` artifacts as a bounded fallback source. The purpose is not to invent a new provider. The purpose is to distinguish three cases more cleanly:

1. live Eastmoney failed but cache already covers the target trade date
2. live Eastmoney failed and cache is only one trading day stale
3. live Eastmoney failed and cache is older than that

This should reduce false-empty shortlist runs in the common case where the provider fails transiently but cached bars are still good enough to preserve normal scoring or bounded observation continuity.

## 2. Why This Exists

The current bars-fallback rescue implementation can recover a candidate into low-confidence `T3` only when a secondary market snapshot path succeeds. In the current tokenless environment, that secondary path still resolves to `free_eastmoney_market`, so it is not truly independent from the primary failure.

That means:

- the rescue logic is implemented and tested
- but real smoke runs can still fail to surface rescued names because both primary and secondary paths depend on Eastmoney

Reusing the existing Eastmoney cache solves a more realistic problem:

- live requests can fail intermittently
- cached bars may already exist for the same ticker and date range
- the shortlist should use that cached evidence instead of collapsing into mass `bars_fetch_failed`

## 3. Non-Goals

This design does not:

- introduce a brand-new mainland provider
- require `TUSHARE_TOKEN`
- change compiled shortlist scoring logic
- remove the existing low-confidence rescue path
- treat stale cache as equal to fresh live bars in every case

## 4. High-Level Behavior

When the live Eastmoney bars request fails for a ticker:

1. try to recover bars from the existing Eastmoney cache
2. inspect the last cached bar date relative to the target trade date
3. choose one of three outcomes

### 4.1 Outcome A: Cache Covers the Target Trade Date

If the cached bars include the target trade date:

- treat the cached rows as normal bars input
- continue normal shortlist scoring and tiering
- do not downgrade the candidate just because cache was used
- add a light metadata marker that the data source was `eastmoney_cache`

This is the “fresh enough to behave like normal bars” path.

### 4.2 Outcome B: Cache Is Exactly One Trading Day Stale

If the cached bars stop one trading day before the target trade date:

- do not allow the candidate to enter `T1`
- only allow fallback rescue into low-confidence `T3`
- only if the candidate already has at least one valid support source:
  - structured catalyst
  - discovery watch/qualified
  - chain support

This reuses the same low-confidence observation semantics already defined in the bars rescue spec.

### 4.3 Outcome C: Cache Is Older Than One Trading Day

If the cache is older than one trading day:

- keep the candidate blocked
- preserve the existing `bars_fetch_failed` behavior

## 5. Data Flow

The intended wrapper/runtime flow becomes:

1. primary bars fetch via the existing Eastmoney path
2. on failure, inspect Eastmoney cache for the same ticker
3. classify cache freshness relative to the requested trade date
4. choose one of:
   - normal bars recovery from cache
   - low-confidence observation rescue
   - blocked

The compiled shortlist core remains unchanged. All logic lives in the wrapper/runtime layer.

## 6. Cache Source and Reuse Policy

Phase 1 should directly reuse the existing Eastmoney cache directory and format:

- `.tmp/tradingagents-eastmoney-cache`

Do not introduce a new shortlist-specific cache.

The shortlist runtime should implement only the minimum additional logic required to:

- locate the existing cached payload for a ticker/date request
- parse rows into the same bar-row shape already expected by the shortlist wrapper
- compute the last cached trading date

The shortlist layer should not become the cache owner. It should only become a cache consumer.

## 7. Freshness Rules

Freshness must be judged by **bar coverage**, not file modification time.

The key comparison is:

- `last_cached_bar_date`
- `target_trade_date`

### 7.1 Fresh Cache

If:

- `last_cached_bar_date == target_trade_date`

Then the cached bars are treated as normal bars.

### 7.2 One-Day-Stale Cache

If:

- `last_cached_bar_date` is exactly one trading day before `target_trade_date`

Then only low-confidence rescue is allowed.

### 7.3 Too-Stale Cache

If the difference is larger than one trading day:

- treat cache as insufficient
- keep the candidate blocked

## 8. Candidate Classification Rules

### 8.1 Normal Cache Recovery

When cache covers the target trade date:

- the candidate may proceed through normal scoring
- `keep=True` is still controlled by normal compiled/runtime logic
- the candidate may enter `T1`, `T2`, `T3`, or `T4` according to normal rules

This path should carry a lightweight source marker such as:

- `bars_source = eastmoney_cache`

### 8.2 One-Day-Stale Rescue

When cache is one trading day stale:

- normal `T1` eligibility is disabled
- rescue only into low-confidence `T3`
- only for candidates with one of:
  - `structured_catalyst`
  - `discovery_qualified`
  - `discovery_watch`
  - `chain_support`

Suggested tags:

- `low_confidence_fallback`
- `fallback_cache_only`
- `fallback_support_reason = ...`

### 8.3 No-Support Case

If cache is one day stale but the candidate has no valid support source:

- do not rescue it
- keep blocked

## 9. Reporting Behavior

### 9.1 Fresh Cache Used as Normal Bars

If cached bars cover the target trade date:

- keep the report lightweight
- do not downgrade the action label
- surface only a small transparency note, for example:
  - `数据来源：Eastmoney cache`

This can appear in summary metadata, card metadata, or another low-noise location.

### 9.2 One-Day-Stale Low-Confidence Rescue

If rescued through one-day-stale cache:

- keep the stronger visual labeling already defined by the observation rescue spec
- title should read:
  - `继续观察（low-confidence fallback）`
- card should clearly state:
  - `数据路径降级：Eastmoney cache only`
  - `保留原因：<support reason>`

## 10. Implementation Surface

The most likely integration points are:

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- existing Eastmoney cache helpers in:
  - `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py`
  - or a small wrapper/runtime adapter that can read the same cache artifacts safely

The preferred wrapper additions are:

- cache lookup helper
- cache freshness classifier
- decision helper that chooses:
  - normal cache recovery
  - low-confidence rescue
  - blocked

## 11. Testing Strategy

At minimum, tests should cover:

1. **fresh cache path**
   - live request fails
   - cache rows exist and cover target trade date
   - candidate proceeds through normal bars evaluation

2. **one-day-stale rescue path**
   - live request fails
   - cache is one trading day stale
   - candidate has valid support
   - candidate becomes low-confidence `T3`

3. **one-day-stale without support**
   - remains blocked

4. **too-stale cache**
   - remains blocked

5. **report labeling**
   - fresh cache recovery uses light source labeling only
   - one-day-stale rescue uses explicit fallback labeling

6. **never promote stale-cache rescue to T1**
   - even with strong score-like conditions

## 12. Success Criteria

This design is successful if:

1. transient Eastmoney failures no longer force empty shortlist runs when same-day cache already exists
2. one-day-stale cache can preserve a small number of evidence-backed observation names
3. `T1` discipline is preserved
4. reporting makes it clear whether a name came from:
   - normal bars
   - fresh cache recovery
   - stale-cache low-confidence fallback

## 13. Open Caveat

This is still not a true independent provider backup. It is a practical resiliency layer on top of Eastmoney’s existing cached artifacts.

That is acceptable for this phase because the immediate goal is to reduce false-empty plans caused by transient live-request failures, not to solve long-term provider diversification.
