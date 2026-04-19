# Non-Trading-Day Cache-First Design

Date: 2026-04-19
Status: Proposed
Owner: Codex
Related:
- `docs/superpowers/specs/2026-04-19-eastmoney-cache-fallback-design.md`
- `docs/superpowers/specs/2026-04-19-eastmoney-cache-preheat-design.md`
- `docs/superpowers/specs/2026-04-19-bars-fallback-observation-rescue-design.md`

## 1. Goal

Make non-trading-day shortlist analysis depend on a **recent post-close cache
baseline first**, instead of assuming live bars APIs will be available.

Phase 1 should treat all **non-trading days** the same way:

- weekends
- exchange holidays
- other market-closed days

The primary behavior becomes:

1. locate the most recent cached trading-day bars before or on the requested
   target date
2. use that cached dataset as the baseline input
3. if live data is available, allow it to supplement or refresh the baseline
4. surface the baseline date clearly in the report

This is meant to prevent non-trading-day analysis from collapsing just because
public APIs are throttled, degraded, or selectively unavailable outside market
hours.

## 2. Why This Exists

Recent investigation showed:

- Eastmoney quote API may remain reachable while historical kline API becomes
  unstable or unavailable
- this can happen on non-trading days
- the current runtime is still too dependent on successful live bars fetches
  for downstream ranking and report completeness

In practice, non-trading-day analysis does **not** need truly live intraday
data. It needs a reliable, recent, post-close market baseline.

That means the system should explicitly optimize for:

- **stability first** on non-trading days
- **freshest recent closed-session data** as the default
- optional live supplementation only when available

## 3. Non-Goals

This design does not:

- replace normal live-first behavior on trading days
- require a full exchange trading-calendar dependency in phase 1
- require a brand-new provider
- change compiled shortlist scoring logic
- guarantee that live updates will always be available on non-trading days

## 4. High-Level Behavior

### 4.1 Trading Days

On normal trading days, keep the current live-oriented behavior.

This design does **not** change the primary policy for live market sessions.

### 4.2 Non-Trading Days

On non-trading days, the runtime should switch to:

- **cache-first baseline**
- **live supplement if available**

That means the baseline assumption changes from:

- "live bars should exist"

to:

- "the most recent completed trading session should exist in cache"

## 5. Baseline Selection Rule

Phase 1 should use the lightest possible rule:

- starting from the requested target date
- search backward
- choose the most recent cached trading date that actually has bars

This intentionally avoids introducing a full trading-calendar dependency.

In other words, the runtime should not begin by asking:

- "is this date a holiday by calendar?"

It should begin by asking:

- "what is the most recent cached date that actually has complete bars?"

That makes the behavior more robust against:

- weekends
- long holidays
- partial cache population

## 6. Data Flow

For non-trading-day requests, the intended flow becomes:

1. receive request with target date
2. inspect available cache history for required tickers/universe
3. determine the most recent cached bars date at or before the target date
4. treat that date as the **baseline trading session**
5. run shortlist analysis from this cached baseline
6. optionally attempt live supplementation
7. if supplementation succeeds, enrich or refresh affected candidates
8. report both:
   - baseline date
   - whether live supplementation happened

## 7. Baseline vs. Live Supplement Semantics

Phase 1 needs a clear semantic distinction:

### 7.1 Baseline

The baseline is:

- the most recent cached post-close trading session
- the minimum required dataset for non-trading-day analysis

If baseline exists, the report should still be considered valid.

### 7.2 Live Supplement

Live supplement is optional.

If available, it may:

- refresh some bars
- refill cache
- improve confidence on affected names

If unavailable, it should **not** invalidate the report.

The baseline report should still stand.

## 8. Report and Output Requirements

Phase 1 should surface this in two layers.

### 8.1 Global Report Metadata

At the top of the report, show a short global line such as:

- `数据基线：最近交易日盘后缓存（2026-04-18）`

If live supplement succeeded, append a short status such as:

- `实时补充：已更新部分数据`

If live supplement did not succeed, append a short status such as:

- `实时补充：不可用，沿用缓存基线`

This global line is the primary visibility layer.

### 8.2 Per-Stock Light Annotation

Per-stock cards should remain light.

Only add per-stock annotations when they materially differ from the global
baseline, for example:

- `数据状态：已补实时更新`
- `数据状态：仍沿用缓存基线`

Do **not** turn every stock card into a long data-source explanation block.

## 9. Cache Requirements

This design assumes the repo already has or can build cache artifacts via:

- Eastmoney cache fallback
- Eastmoney cache preheat
- normal successful bars runs

Phase 1 should reuse the existing cache directory and cache model.

Do not create a second non-trading-day-only cache.

## 10. Failure Handling

### 10.1 Baseline Exists, Live Supplement Fails

This is an acceptable and expected non-trading-day outcome.

Behavior:

- continue with baseline-backed analysis
- mark live supplement unavailable
- do not collapse the report into mass `bars_fetch_failed`

### 10.2 No Baseline Cache Exists

If no usable cached baseline exists:

- fall back to current failure handling
- report clearly that no recent cached trading session was available

### 10.3 Partial Baseline Coverage

If some names have baseline cache but others do not:

- use baseline where available
- keep missing names on existing fallback / blocked logic

Phase 1 does not need to solve perfect completeness.

## 11. Success Criteria

This design is successful if, on non-trading days:

1. shortlist analysis can still produce a useful report from Friday or latest
   cached post-close data
2. live API outages no longer automatically collapse the whole report
3. the report clearly tells the user which cached trading day is serving as the
   baseline
4. users can distinguish:
   - baseline-only output
   - baseline plus live supplement

## 12. Expected User Experience

On a Saturday or holiday, the user should see something like:

- `数据基线：最近交易日盘后缓存（2026-04-18）`
- `实时补充：不可用，沿用缓存基线`

Then the rest of the trading plan should remain readable and actionable, rather
than collapsing because live bars APIs are intermittently unavailable.
