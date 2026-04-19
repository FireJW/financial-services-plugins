# Eastmoney Cache Preheat Design

Date: 2026-04-19
Status: Proposed
Owner: Codex
Related:
- `docs/superpowers/specs/2026-04-19-eastmoney-cache-fallback-design.md`
- `docs/superpowers/specs/2026-04-19-bars-fallback-observation-rescue-design.md`

## 1. Goal

Add a small standalone command that explicitly preheats Eastmoney cache files for a chosen ticker set before running shortlist flows.

The immediate purpose is operational:

- reduce false-empty shortlist runs caused by transient Eastmoney live failures
- make the new cache fallback path actually usable in a tokenless environment
- give the operator a direct way to prepare cache ahead of a shortlist run instead of hoping the cache appears naturally

This command should be fast, bounded, and easy to run manually.

## 2. Why This Exists

The new shortlist fallback logic can now:

- use same-day Eastmoney cache as normal bars recovery
- use one-day-stale cache for low-confidence observation rescue

But a real smoke run showed that the fallback did not trigger because the local cache directory was empty. The current “natural” cache creation path depends on at least one successful Eastmoney live request. When Eastmoney is already unstable, that natural path is not reliable enough.

So the missing piece is not more shortlist logic. The missing piece is a direct cache warming tool.

## 3. Non-Goals

This design does not:

- replace Eastmoney as the main provider
- create a new market data abstraction
- redesign shortlist CLI behavior
- guarantee that every ticker will preheat successfully
- solve long-term provider diversification

It only adds a practical operator tool for warming cache ahead of time.

## 4. Command Shape

Phase 1 should be a standalone script under:

- `financial-analysis/skills/month-end-shortlist/scripts`

Suggested filename:

- `preheat_eastmoney_cache.py`

The command should not be folded into `month_end_shortlist.py` yet. Keeping it separate makes it easier to:

- run independently
- inspect operational output
- avoid complicating the shortlist command surface

## 5. Inputs

Phase 1 should support both of these ticker input modes:

### 5.1 Direct Ticketers Argument

Example:

```bash
py.exe preheat_eastmoney_cache.py --tickers 000988.SZ,002384.SZ,300476.SZ
```

This is the quickest manual path.

### 5.2 Tickers File

Example:

```bash
py.exe preheat_eastmoney_cache.py --tickers-file D:\path\to\tickers.txt
```

Supported file formats:

- `txt`
  - one ticker per line
- `json`
  - array of ticker strings

If both `--tickers` and `--tickers-file` are provided, the command should merge and deduplicate them.

## 6. Default Time Window

Phase 1 should use a bounded short window:

- **120 calendar days back from target date**

This is intentionally shorter than the full shortlist bars window. The preheat command is for operational warming, not for filling every possible historical need in one run.

The target date should default to “today” in local time, but the command may also accept an explicit target date later. Phase 1 does not need to require that flag if it complicates the command too much.

## 7. Success Definition

Phase 1 success should be practical, not strict.

A ticker counts as successful if either:

- cache already existed and was usable (`cache_hit`)
- or a new cache file was written successfully (`cache_written`)

It does **not** need to prove full shortlist readiness as part of the command’s success definition.

That stricter freshness interpretation belongs to the shortlist fallback logic, not to the preheat tool itself.

## 8. Output

Phase 1 output should be:

- **per-ticker result**
- **final summary**

### 8.1 Per-Ticker Result States

Each ticker should end in one of:

- `cache_hit`
- `cache_written`
- `failed`

The command should print these directly to stdout in a human-readable way.

Example style:

```text
[cache_written] 000988.SZ
[cache_hit] 002384.SZ
[failed] 300476.SZ - Eastmoney request failed: Remote end closed connection without response
```

### 8.2 Final Summary

At the end, print a short summary such as:

```text
Summary:
- total: 12
- cache_hit: 4
- cache_written: 6
- failed: 2
```

Phase 1 does **not** need a dedicated output JSON file.

## 9. Reuse Strategy

The command should reuse the existing Eastmoney cache-writing path, not invent a new cache format.

Specifically:

- reuse the same request/query shape used by Eastmoney daily bars fetch
- reuse the same cache directory:
  - `.tmp/tradingagents-eastmoney-cache`
- reuse the same payload format that `tradingagents_eastmoney_market.py` already writes

The preheat tool is just an explicit cache producer sitting on top of the current Eastmoney implementation.

## 10. Failure Handling

Failures should be explicit but non-fatal to the whole batch.

If one ticker fails:

- record it as `[failed]`
- continue with the remaining tickers

The command should only fail the whole process if:

- there are no valid tickers after parsing
- or the input arguments are invalid

Normal per-ticker network/provider failures should not stop the batch.

## 11. Integration Boundary

The preheat command is an operator tool, not an automatic shortlist dependency.

Phase 1 should **not**:

- auto-run preheat before every shortlist execution
- mutate shortlist request files
- silently trigger cache warming inside `month_end_shortlist.py`

The intended workflow is:

1. operator runs preheat on a shortlist-worthy ticker set
2. cache is written where available
3. shortlist run can later consume that cache through the already-built cache fallback logic

## 12. Testing Strategy

At minimum, tests should cover:

1. **ticker parsing from CLI string**
   - comma-separated tickers
   - whitespace trimming
   - deduplication

2. **ticker parsing from txt file**
   - one ticker per line
   - blank lines ignored

3. **ticker parsing from json file**
   - array of strings

4. **success classification**
   - existing cache => `cache_hit`
   - newly written cache => `cache_written`

5. **batch continues after per-ticker failure**
   - one failure does not abort later tickers

6. **final summary**
   - counts match emitted per-ticker statuses

Phase 1 tests do not need real network calls. They should use targeted monkeypatching/stubbing around the Eastmoney fetch/write path.

## 13. Success Criteria

This design is successful if:

1. an operator can preheat Eastmoney cache for a chosen ticker list with one command
2. the command makes it obvious which tickers hit cache, wrote cache, or failed
3. the command reuses the existing cache directory and payload format
4. the later shortlist fallback flow can benefit from those cache files without additional translation work

## 14. Open Caveat

This is still Eastmoney-dependent. It improves resiliency only when Eastmoney works at preheat time and later fails at shortlist time.

That is acceptable for phase 1 because the immediate problem is not provider diversity. The immediate problem is that the new cache fallback path has no reliable way to obtain cache artifacts before a live shortlist run.
