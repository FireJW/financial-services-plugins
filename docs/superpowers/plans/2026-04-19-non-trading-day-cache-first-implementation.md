# Non-Trading-Day Cache-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make non-trading-day shortlist analysis use the most recent cached post-close trading session as the baseline, while allowing live data to supplement it when available.

**Architecture:** Keep all logic in `month_end_shortlist_runtime.py`. Add a small cache-baseline resolution helper, thread baseline metadata through the runtime result, and surface it in the markdown report plus light per-stock annotations. Do not change compiled shortlist logic or add a trading-calendar dependency.

**Tech Stack:** Python, pytest, existing Eastmoney cache helpers, month-end shortlist runtime/reporting.

---

### Task 1: Add cache-baseline resolution tests and helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Write failing tests for baseline date resolution**

Extend `tests/test_month_end_shortlist_candidate_fetch_fallback.py` with:

```python
    def test_last_cached_trade_date_from_row_sets_picks_latest_available_date(self) -> None:
        row_sets = [
            [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
            [{"date": "2026-04-16"}, {"date": "2026-04-18"}],
            [],
        ]
        self.assertEqual(
            module_under_test.last_cached_trade_date_from_row_sets(row_sets),
            "2026-04-18",
        )

    def test_resolve_cache_baseline_metadata_reports_baseline_only_when_cache_lags_target(self) -> None:
        metadata = module_under_test.resolve_cache_baseline_metadata(
            "2026-04-20",
            [
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
                [{"date": "2026-04-18"}],
            ],
        )
        self.assertEqual(metadata["baseline_trade_date"], "2026-04-18")
        self.assertTrue(metadata["cache_baseline_only"])

    def test_resolve_cache_baseline_metadata_stays_empty_when_target_is_covered(self) -> None:
        metadata = module_under_test.resolve_cache_baseline_metadata(
            "2026-04-18",
            [
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
            ],
        )
        self.assertEqual(metadata["baseline_trade_date"], "")
        self.assertFalse(metadata["cache_baseline_only"])
```

- [ ] **Step 2: Run the focused test file to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" -q
```

Expected:
- FAIL because the new helpers do not exist yet

- [ ] **Step 3: Add minimal helper implementations**

Modify `month_end_shortlist_runtime.py` near the existing cache helpers:

```python
def last_cached_trade_date_from_row_sets(row_sets: list[list[dict[str, Any]]]) -> str:
    latest = ""
    for rows in row_sets:
        current = last_bar_date_from_rows(rows or [])
        if current and (not latest or current > latest):
            latest = current
    return latest


def resolve_cache_baseline_metadata(
    target_trade_date: str,
    row_sets: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    target = clean_text(target_trade_date)[:10]
    baseline = last_cached_trade_date_from_row_sets(row_sets)
    if not target or not baseline:
        return {
            "baseline_trade_date": "",
            "cache_baseline_only": False,
            "live_supplement_status": "",
        }
    if baseline >= target:
        return {
            "baseline_trade_date": "",
            "cache_baseline_only": False,
            "live_supplement_status": "",
        }
    return {
        "baseline_trade_date": baseline,
        "cache_baseline_only": True,
        "live_supplement_status": "unavailable",
    }
```

- [ ] **Step 4: Re-run the focused test file**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_candidate_fetch_fallback.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: add non-trading-day cache baseline helpers"
```

### Task 2: Attach cache-baseline metadata to shortlist runs

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`

- [ ] **Step 1: Add a failing test for request-level baseline metadata**

Extend `tests/test_month_end_shortlist_candidate_fetch_fallback.py` with:

```python
    def test_attach_cache_baseline_metadata_uses_recent_cached_rows(self) -> None:
        result = {"request": {"analysis_time": "2026-04-20T10:00:00+08:00"}}
        candidates = [
            {"ticker": "000988.SZ"},
            {"ticker": "002384.SZ"},
        ]
        with patch.object(
            module_under_test,
            "eastmoney_cached_bars_for_candidate",
            side_effect=[
                [{"date": "2026-04-17"}, {"date": "2026-04-18"}],
                [{"date": "2026-04-18"}],
            ],
        ):
            enriched = module_under_test.attach_cache_baseline_metadata(result, candidates)
        self.assertEqual(enriched["filter_summary"]["cache_baseline_trade_date"], "2026-04-18")
        self.assertTrue(enriched["filter_summary"]["cache_baseline_only"])
        self.assertEqual(enriched["filter_summary"]["live_supplement_status"], "unavailable")
```

- [ ] **Step 2: Run the focused test file to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" -q
```

Expected:
- FAIL because `attach_cache_baseline_metadata` does not exist

- [ ] **Step 3: Implement request-level metadata attachment**

Add to `month_end_shortlist_runtime.py`:

```python
def attach_cache_baseline_metadata(
    result: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched = deepcopy(result)
    request_obj = dict(enriched.get("request") or {})
    target_trade_date = clean_text(request_obj.get("analysis_time") or request_obj.get("target_date"))[:10]
    if not target_trade_date or not candidates:
        return enriched

    target_dt = parse_date(target_trade_date)
    if not target_dt:
        return enriched

    start_date = (target_dt - timedelta(days=420)).isoformat()
    row_sets: list[list[dict[str, Any]]] = []
    for candidate in candidates:
        ticker = clean_text(candidate.get("ticker"))
        if not ticker:
            continue
        row_sets.append(eastmoney_cached_bars_for_candidate(ticker, start_date, target_trade_date))

    metadata = resolve_cache_baseline_metadata(target_trade_date, row_sets)
    filter_summary = dict(enriched.get("filter_summary") or {})
    filter_summary["cache_baseline_trade_date"] = metadata["baseline_trade_date"]
    filter_summary["cache_baseline_only"] = bool(metadata["cache_baseline_only"])
    filter_summary["live_supplement_status"] = metadata["live_supplement_status"]
    enriched["filter_summary"] = filter_summary
    return enriched
```

Then call it in `run_month_end_shortlist(...)` after merge/final result assembly, using the best available candidate set:

```python
    merged = merge_track_results(track_results, prepared_payload, out_of_scope, failure_log, assessed_log)
    baseline_candidates = list(merged.get("assessed_candidates") or merged.get("blocked_candidates") or [])
    merged = attach_cache_baseline_metadata(merged, baseline_candidates)
    return merged
```

If `assessed_candidates` is not already present on `merged`, use the nearest existing merged candidate list already available in the runtime rather than inventing a new contract.

- [ ] **Step 4: Re-run the focused test file**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_candidate_fetch_fallback.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: attach non-trading-day cache baseline metadata"
```

### Task 3: Surface global cache-baseline metadata in the markdown report

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing markdown-report tests**

Extend `tests/test_month_end_shortlist_degraded_reporting.py` with:

```python
    def test_report_includes_global_cache_baseline_metadata(self) -> None:
        result = {
            "filter_summary": {
                "cache_baseline_trade_date": "2026-04-18",
                "cache_baseline_only": True,
                "live_supplement_status": "unavailable",
            },
            "report_markdown": "# Month-End Shortlist Report: 2026-04-20\n",
            "top_picks": [],
            "dropped": [],
        }
        enriched = module_under_test.enrich_degraded_live_result(result, [])
        self.assertIn("数据基线：最近交易日盘后缓存（2026-04-18）", enriched["report_markdown"])
        self.assertIn("实时补充：不可用，沿用缓存基线", enriched["report_markdown"])
```

- [ ] **Step 2: Run the markdown reporting test file to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- FAIL because the metadata line is not rendered yet

- [ ] **Step 3: Add a small report helper**

In `month_end_shortlist_runtime.py`, add a helper near other report-building utilities:

```python
def build_cache_baseline_report_lines(result: dict[str, Any]) -> list[str]:
    summary = dict(result.get("filter_summary") or {})
    baseline_trade_date = clean_text(summary.get("cache_baseline_trade_date"))
    if not baseline_trade_date:
        return []

    lines = [f"- 数据基线：最近交易日盘后缓存（{baseline_trade_date}）"]
    if clean_text(summary.get("live_supplement_status")) == "unavailable":
        lines.append("- 实时补充：不可用，沿用缓存基线")
    elif clean_text(summary.get("live_supplement_status")) == "updated":
        lines.append("- 实时补充：已更新部分数据")
    return lines
```

Then, in the function that appends degraded/blocked reporting lines, prepend these lines under the main report header without duplicating them.

- [ ] **Step 4: Re-run the markdown reporting test file**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_degraded_reporting.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: show non-trading-day cache baseline in report"
```

### Task 4: Add light per-stock data-state annotation and verify end-to-end behavior

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing per-card annotation tests**

Extend `tests/test_month_end_shortlist_degraded_reporting.py` with:

```python
    def test_decision_flow_card_marks_cache_baseline_only_state(self) -> None:
        card = {
            "ticker": "002384.SZ",
            "name": "东山精密",
            "action": "继续观察",
            "fallback_cache_only": False,
            "bars_source": "eastmoney_cache",
            "cache_baseline_only": True,
            "trading_profile_bucket": "补涨候选",
        }
        reminder = module_under_test.build_operation_reminder(card)
        self.assertIn("数据状态：仍沿用缓存基线", reminder)
```

If `build_operation_reminder(...)` is not the exact helper name, target the existing helper that assembles the per-card operation/reminder line.

- [ ] **Step 2: Run the markdown reporting test file to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- FAIL because cache-baseline-only per-card annotations are not emitted yet

- [ ] **Step 3: Thread a light annotation through card assembly**

In the card-building path within `month_end_shortlist_runtime.py`, add:

```python
if card.get("cache_baseline_only"):
    operation_parts.append("数据状态：仍沿用缓存基线")
elif clean_text(card.get("live_supplement_status")) == "updated":
    operation_parts.append("数据状态：已补实时更新")
```

Only surface this when it materially differs from the global line. Do not add a long explanation block.

If cards are synthesized from candidate dicts, copy the request-level
`cache_baseline_only` / `live_supplement_status` flags into the card context in
the narrowest possible way.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_candidate_fetch_fallback.py" `
  "tests/test_month_end_shortlist_degraded_reporting.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: annotate cache-first non-trading-day cards"
```

### Task 5: Focused verification and a non-trading-day smoke

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Run the focused shortlist/reporting suite**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- PASS

- [ ] **Step 2: Run a real non-trading-day smoke**

Use an existing weekend-style request or clone one into `.tmp` with a target date
like `2026-04-20` and run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.full.geopolitics-candidate.json" `
  --output "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\result.non-trading-cache-first.json" `
  --markdown-output "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\report.non-trading-cache-first.md"
```

Expected:
- if cache baseline exists, report contains:
  - `数据基线：最近交易日盘后缓存（...）`
- live supplement may still be unavailable; that is acceptable
- the report should not collapse solely because live kline fetches are degraded

- [ ] **Step 3: Verify `.tmp` artifacts remain uncommitted**

Run:

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" status --short
```

Expected:
- no `.tmp` artifacts staged or committed

## Self-Review

- Spec coverage:
  - cache-first baseline on non-trading days: Tasks 1-2
  - baseline chosen by searching backward for cached bars: Tasks 1-2
  - live supplement optional and non-fatal: Tasks 2-3
  - global report metadata: Task 3
  - light per-stock annotations: Task 4
- Placeholder scan:
  - no `TODO`, `TBD`, or vague “handle later” placeholders
  - all changed-code steps contain concrete snippets
  - verification steps use exact commands
- Type consistency:
  - `last_cached_trade_date_from_row_sets`
  - `resolve_cache_baseline_metadata`
  - `attach_cache_baseline_metadata`
  - `cache_baseline_trade_date`
  - `cache_baseline_only`
  - `live_supplement_status`
