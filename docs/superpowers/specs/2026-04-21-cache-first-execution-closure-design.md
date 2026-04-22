# Cache-First Execution Closure Design

**Date:** 2026-04-21  
**Status:** Approved design  
**Scope:** Close the execution-layer gap by turning the repo's existing cache
and fallback pieces into a practical cache-first execution path, especially for
non-trading-day and degraded Eastmoney conditions.

## 1. Goal

The repo already has several important building blocks:

- Eastmoney cache fallback
- Eastmoney cache preheat
- non-trading-day cache-first baseline behavior
- degraded reporting and low-confidence rescue semantics

But the execution layer still breaks too easily in real runs because these
pieces do not yet behave like one coherent execution-closure system.

Iteration 3 should solve that problem.

The objective is:

- reduce mass `bars_fetch_failed` outcomes
- preserve more valid names in the formal runtime when cache is already usable
- make non-trading-day and degraded-day execution rely on cache-first behavior
  by default
- expose cache / live / fallback state clearly in the final report

This is not a new provider project.

It is an execution-closure project that consolidates the repo's existing
cache-first infrastructure into the normal shortlist operating path.

## 2. Why This Exists

Current repo state is asymmetric:

- direction discovery is increasingly strong
  - live X topic discovery
  - weekend candidate
  - market-strength supplement
  - setup-launch supplement
- but formal execution confirmation still collapses when Eastmoney bars fail

That creates an undesirable product state:

- the system often knows *what* direction matters
- but the execution layer still goes empty because `bars_fetch_failed` becomes
  the dominant runtime outcome

That means the missing work is not another discovery lane.

The missing work is:

- a stable execution baseline
- built on the cache behaviors already implemented

## 3. Non-Goals

This design does not:

- introduce a brand-new mainland data provider
- replace Eastmoney as the main path
- redesign the event-driven shortlist engine
- change formal `T1` / `T2` scoring thresholds
- remove the distinction between:
  - fresh cache
  - stale cache
  - blocked names

This design is specifically about runtime closure and execution continuity.

## 4. Existing Building Blocks To Reuse

Iteration 3 must build on existing repo functionality rather than inventing a
parallel stack.

### 4.1 Eastmoney Cache Fallback

Already implemented:

- same-day cache can behave as normal bars recovery
- one-day-stale cache can rescue only into low-confidence observation behavior

### 4.2 Eastmoney Cache Preheat

Already implemented:

- standalone preheat CLI
- operator-controlled cache warming

### 4.3 Non-Trading-Day Cache-First Baseline

Already implemented:

- choose the most recent cached trading date as baseline on non-trading days
- treat live supplementation as optional

Iteration 3 should make these three surfaces behave like one operational
execution path.

## 5. Design Principle

The formal execution layer should no longer behave like:

- live bars success or total collapse

It should instead behave like:

1. try live bars
2. if live fails, use the strongest valid cache state
3. if cache is insufficient, degrade or block according to existing rules

In other words:

- cache-first should become the runtime resilience model
- not just a side utility

## 6. High-Level Behavior

### 6.1 Trading Days

On trading days:

- keep live bars as the first choice
- but automatically fall back to cache before collapsing the candidate

Priority:

1. live bars
2. same-day cache baseline
3. one-day-stale low-confidence fallback
4. blocked

### 6.2 Non-Trading Days

On non-trading days:

- default baseline should be cache-first
- live bars become optional supplementation

Priority:

1. most recent cached trading-session baseline
2. live supplementation if available
3. stale-cache rescue if necessary
4. blocked only when no usable cache path exists

### 6.3 Explicit Preheat Path

Preheat should remain operator-invoked, not silently mandatory.

But Iteration 3 should make it easier for an operator or upstream workflow to
use preheat as a normal preparation step rather than an isolated utility.

This means:

- better request / runtime visibility when cache coverage is thin
- clearer operator path to preheat likely execution names before re-running

## 7. Execution Closure Policy

Iteration 3 should formalize execution closure around four candidate states.

### 7.1 Live Confirmed

- live bars succeeded
- normal execution logic applies

### 7.2 Fresh Cache Confirmed

- live bars failed or were skipped
- same-day cache covers the target trade date
- normal execution logic still applies

This means the formal layer can still produce:

- `T1`
- `T2`
- `T3`
- `T4`

when the cached bars are sufficiently fresh.

### 7.3 Stale Cache Degraded

- cache exists but is exactly one trading day stale
- only low-confidence observation behavior is allowed

This must preserve the current rule:

- stale cache cannot directly create full execution confidence

### 7.4 Hard Blocked

- no usable live bars
- no usable cache baseline
- or cache too stale

Only this state should produce the hard blocked behavior that currently shows
up as mass `bars_fetch_failed`.

## 8. Runtime Integration Shape

Iteration 3 should not create a separate runtime entrypoint.

It should strengthen the existing shortlist runtime path by:

1. making cache-state classification first-class in the wrapper/runtime layer
2. letting preheated cache participate naturally in the same path
3. making non-trading-day baseline selection visible and authoritative

The runtime should carry a small structured execution-state summary such as:

- `live`
- `fresh_cache`
- `stale_cache`
- `blocked`

both globally and per candidate where helpful.

## 9. Reporting Requirements

Iteration 3 must make the execution state visible without overloading every
stock card.

### 9.1 Global Summary

At the top-level report / summary metadata, show:

- baseline trade date
- live supplementation status
- counts by execution-state category

Examples:

- `bars_source_summary.live_count`
- `bars_source_summary.fresh_cache_count`
- `bars_source_summary.stale_cache_count`
- `bars_source_summary.blocked_count`

### 9.2 Per-Name Light Annotation

Per stock, only annotate when it materially differs from the default path.

Examples:

- `数据来源：Eastmoney cache`
- `数据状态：低置信度 fallback`
- `数据路径：cache baseline only`

### 9.3 Avoid Report Collapse

The report should no longer default to a giant blocked wall when the cache path
is still usable.

That means:

- fewer names should end up in the blocked section when cache is available
- more names should remain eligible for formal ranking or bounded observation

## 10. Preheat Integration Boundary

Iteration 3 should not automatically run preheat on every shortlist execution.

But it should:

- make cache insufficiency visible enough that preheat becomes an obvious next
  operational step
- allow future operator wrappers to invoke preheat before rerunning shortlist
- preserve the standalone CLI contract

That means the preheat tool remains a separate script, but the runtime becomes
better at consuming its output and signaling when it would help.

## 11. Failure Handling

### 11.1 Live Fails But Fresh Cache Exists

- treat as execution-continuable
- do not mark blocked

### 11.2 Live Fails And One-Day-Stale Cache Exists

- downgrade to low-confidence observation only
- do not pretend this is full execution certainty

### 11.3 Live Fails And No Usable Cache Exists

- blocked remains valid

### 11.4 Preheat Fails

- do not break the shortlist runtime because preheat could not run earlier
- just surface cache insufficiency honestly

## 12. Success Criteria

Iteration 3 is successful if:

1. real shortlist runs no longer collapse into mass `bars_fetch_failed` when a
   usable cache baseline already exists
2. non-trading-day runs stand on recent cached baseline data by default
3. fresh cache can preserve formal execution-layer eligibility
4. stale cache remains clearly degraded rather than over-trusted
5. reports clearly explain cache / live / blocked state without excessive noise

## 13. Recommended Next Step

The implementation plan should focus on three bounded tasks:

1. standardize execution-state classification and summary fields in the
   shortlist runtime
2. tighten non-trading-day and live-failure fallback ordering around fresh /
   stale cache behavior
3. improve reporting so cache-first execution closure is visible and
   operationally useful
