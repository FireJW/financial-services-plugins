# Eastmoney Cache Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse existing Eastmoney cache data to prevent false-empty shortlist runs when live Eastmoney bars fail, treating same-day cache as normal bars and one-day-stale cache as low-confidence observation rescue only.

**Architecture:** Keep Eastmoney as the primary provider and add a wrapper/runtime cache consumer that reads the existing `.tmp/tradingagents-eastmoney-cache` artifacts. Classify cache freshness by the last covered bar date relative to the target trade date, then route each candidate into normal bars recovery, low-confidence rescue, or blocked without changing the compiled shortlist core.

**Tech Stack:** Python, pytest, `month_end_shortlist_runtime.py`, existing Eastmoney cache artifacts, shortlist reporting/runtime wrapper.

---

### Task 1: Add failing tests for Eastmoney cache freshness classification

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Write failing tests for freshness classification**

Add these tests to `tests/test_month_end_shortlist_candidate_fetch_fallback.py`:

```python
    def test_classify_eastmoney_cache_freshness_marks_same_day_as_fresh(self) -> None:
        rows = [
            {"date": "2026-04-17"},
            {"date": "2026-04-18"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "fresh_cache")
        self.assertEqual(outcome["last_bar_date"], "2026-04-18")

    def test_classify_eastmoney_cache_freshness_marks_one_day_gap_as_stale_rescue(self) -> None:
        rows = [
            {"date": "2026-04-16"},
            {"date": "2026-04-17"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "stale_one_day")
        self.assertEqual(outcome["last_bar_date"], "2026-04-17")

    def test_classify_eastmoney_cache_freshness_marks_older_gap_as_stale_blocked(self) -> None:
        rows = [
            {"date": "2026-04-15"},
            {"date": "2026-04-16"},
        ]
        outcome = module_under_test.classify_eastmoney_cache_freshness(rows, "2026-04-18")
        self.assertEqual(outcome["mode"], "stale_too_old")
        self.assertEqual(outcome["last_bar_date"], "2026-04-16")
```

- [ ] **Step 2: Run only the candidate fetch fallback tests to verify they fail**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- FAIL with missing helper such as `classify_eastmoney_cache_freshness`

- [ ] **Step 3: Implement minimal cache freshness helpers**

Add small pure helpers in `month_end_shortlist_runtime.py`:

```python
def last_bar_date_from_rows(rows: list[dict[str, Any]]) -> str:
    for row in reversed(rows or []):
        if not isinstance(row, dict):
            continue
        for key in ("date", "trade_date"):
            value = clean_text(row.get(key))
            if value:
                return value[:10]
    return ""


def classify_eastmoney_cache_freshness(
    rows: list[dict[str, Any]] | None,
    target_trade_date: str,
) -> dict[str, str]:
    normalized_target = clean_text(target_trade_date)[:10]
    last_bar_date = last_bar_date_from_rows(rows or [])
    if not normalized_target or not last_bar_date:
        return {"mode": "missing_cache", "last_bar_date": last_bar_date}
    if last_bar_date == normalized_target:
        return {"mode": "fresh_cache", "last_bar_date": last_bar_date}
    try:
        target_dt = datetime.strptime(normalized_target, "%Y-%m-%d").date()
        last_dt = datetime.strptime(last_bar_date, "%Y-%m-%d").date()
    except ValueError:
        return {"mode": "missing_cache", "last_bar_date": last_bar_date}
    gap_days = (target_dt - last_dt).days
    if gap_days == 1:
        return {"mode": "stale_one_day", "last_bar_date": last_bar_date}
    return {"mode": "stale_too_old", "last_bar_date": last_bar_date}
```

Also export them in `__all__`.

- [ ] **Step 4: Re-run the candidate fetch fallback tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_month_end_shortlist_candidate_fetch_fallback.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: classify eastmoney cache freshness"
```

### Task 2: Reuse same-day Eastmoney cache as normal bars recovery

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py`

- [ ] **Step 1: Add failing tests for fresh-cache recovery**

Extend `tests/test_month_end_shortlist_candidate_fetch_fallback.py` with tests like:

```python
    def test_cached_bars_covering_target_date_are_accepted_as_normal_recovery(self) -> None:
        rows = [
            {"date": "2026-04-17", "close": 5.5},
            {"date": "2026-04-18", "close": 5.8},
        ]
        recovered = module_under_test.choose_eastmoney_cache_recovery_mode(rows, "2026-04-18")
        self.assertEqual(recovered["mode"], "fresh_cache")
        self.assertEqual(recovered["bars_source"], "eastmoney_cache")
        self.assertEqual(recovered["rows"][-1]["date"], "2026-04-18")
```

- [ ] **Step 2: Run the candidate fetch fallback tests to confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- FAIL with missing helper such as `choose_eastmoney_cache_recovery_mode`

- [ ] **Step 3: Implement a minimal cache recovery decision helper**

Add a helper in `month_end_shortlist_runtime.py`:

```python
def choose_eastmoney_cache_recovery_mode(
    rows: list[dict[str, Any]] | None,
    target_trade_date: str,
) -> dict[str, Any]:
    freshness = classify_eastmoney_cache_freshness(rows or [], target_trade_date)
    mode = freshness["mode"]
    if mode == "fresh_cache":
        return {
            "mode": "fresh_cache",
            "bars_source": "eastmoney_cache",
            "rows": list(rows or []),
            "last_bar_date": freshness.get("last_bar_date", ""),
        }
    return {
        "mode": mode,
        "bars_source": "",
        "rows": [],
        "last_bar_date": freshness.get("last_bar_date", ""),
    }
```

Export it in `__all__`.

- [ ] **Step 4: Re-run the candidate fetch fallback tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_month_end_shortlist_candidate_fetch_fallback.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: recover fresh eastmoney cache as normal bars"
```

### Task 3: Route one-day-stale cache into low-confidence fallback rescue

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py`

- [ ] **Step 1: Add failing tests for one-day-stale cache rescue**

Add tests to `tests/test_screening_coverage_optimization.py` like:

```python
    def test_one_day_stale_cache_with_support_can_rescue_into_low_confidence_t3(self):
        candidate = self._make_failed_candidate(
            structured_catalyst_snapshot={
                "structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]
            }
        )
        rows = [
            {"date": "2026-04-17", "close": 5.5},
            {"date": "2026-04-18", "close": 5.8},
        ]
        recovered = runtime.build_bars_cache_rescue_candidate(candidate, rows, "2026-04-19")
        self.assertIsNotNone(recovered)
        self.assertIn("low_confidence_fallback", recovered["tier_tags"])
        self.assertIn("fallback_cache_only", recovered["tier_tags"])
        self.assertEqual(recovered["fallback_support_reason"], "structured_catalyst")

    def test_too_old_cache_does_not_rescue_candidate(self):
        candidate = self._make_failed_candidate(discovery_bucket="watch")
        rows = [
            {"date": "2026-04-15", "close": 5.2},
            {"date": "2026-04-16", "close": 5.1},
        ]
        recovered = runtime.build_bars_cache_rescue_candidate(candidate, rows, "2026-04-19")
        self.assertIsNone(recovered)
```

- [ ] **Step 2: Run the screening tests to confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py -q
```

Expected:
- FAIL with missing helper such as `build_bars_cache_rescue_candidate`

- [ ] **Step 3: Implement one-day-stale cache rescue helper**

Add a helper in `month_end_shortlist_runtime.py`:

```python
def build_bars_cache_rescue_candidate(
    candidate: dict[str, Any],
    cached_rows: list[dict[str, Any]] | None,
    target_trade_date: str,
) -> dict[str, Any] | None:
    cache_mode = classify_eastmoney_cache_freshness(cached_rows or [], target_trade_date)
    if cache_mode.get("mode") != "stale_one_day":
        return None
    snapshot_rows = list(cached_rows or [])
    if not snapshot_rows:
        return None
    latest = snapshot_rows[-1]
    snapshot = {
        "close": latest.get("close"),
        "pct_chg": latest.get("pct_chg"),
        "sma20": latest.get("boll"),
        "sma50": latest.get("close_50_sma"),
        "rsi14": latest.get("rsi"),
        "volume_ratio": latest.get("volume_ratio"),
    }
    rescued = build_bars_fallback_rescue_candidate(candidate, snapshot)
    if not rescued:
        return None
    rescued["bars_source"] = "eastmoney_cache"
    rescued["fallback_cache_only"] = True
    rescued["tier_tags"] = unique_strings(list(rescued.get("tier_tags", [])) + ["fallback_cache_only"])
    return rescued
```

Export it in `__all__`.

- [ ] **Step 4: Re-run the screening tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_screening_coverage_optimization.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: rescue one-day stale eastmoney cache into T3"
```

### Task 4: Surface cache source semantics in the report

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add failing report tests for fresh-cache and stale-cache wording**

Add tests like:

```python
    def test_decision_flow_lightly_marks_fresh_cache_source(self) -> None:
        card = module_under_test.build_decision_flow_card(
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "action": "继续观察",
                "score": 60.0,
                "keep_threshold_gap": -10.0,
                "tier_tags": [],
                "bars_source": "eastmoney_cache",
            },
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
        )
        self.assertIn("数据来源：Eastmoney cache", card["operation_reminder"])

    def test_decision_flow_marks_stale_cache_rescue_as_low_confidence_fallback(self) -> None:
        card = module_under_test.build_decision_flow_card(
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "action": "继续观察",
                "score": 60.0,
                "keep_threshold_gap": -10.0,
                "tier_tags": ["low_confidence_fallback", "fallback_cache_only"],
                "fallback_support_reason": "structured_catalyst",
            },
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
        )
        self.assertEqual(card["action_label"], "继续观察（low-confidence fallback）")
        self.assertIn("数据路径降级：Eastmoney cache only", card["operation_reminder"])
```

- [ ] **Step 2: Run degraded-reporting tests and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- FAIL because cache-source wording is not yet implemented

- [ ] **Step 3: Implement reporting semantics**

In `month_end_shortlist_runtime.py`:

- when `bars_source == "eastmoney_cache"` and the card is **not** low-confidence fallback:
  - append `数据来源：Eastmoney cache` to operation reminder
- when `fallback_cache_only` is present:
  - continue using `继续观察（low-confidence fallback）`
  - use `数据路径降级：Eastmoney cache only`

Suggested shape:

```python
    bars_source = clean_text(card.get("bars_source"))
    if is_fallback and "fallback_cache_only" in tier_tags:
        operation_parts.append("数据路径降级：Eastmoney cache only")
    elif bars_source == "eastmoney_cache":
        operation_parts.append("数据来源：Eastmoney cache")
```

- [ ] **Step 4: Re-run degraded-reporting tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_month_end_shortlist_degraded_reporting.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: surface eastmoney cache fallback semantics in reports"
```

### Task 5: Focused verification and smoke confirmation

**Files:**
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_profile_passthrough.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_board_threshold_overrides.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_x_style_assisted_shortlist.py`

- [ ] **Step 1: Run the focused shortlist suite**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_board_threshold_overrides.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_earnings_momentum_discovery.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_discovery_merge.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_x_style_assisted_shortlist.py -q
```

Expected:
- all tests pass

- [ ] **Step 2: Run the real shortlist smoke**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.full.geopolitics-candidate.json --output D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\.tmp\next-session-2026-04-21\result.full.cache-fallback.json --markdown-output D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\.tmp\next-session-2026-04-21\report.full.cache-fallback.md
```

Expected:
- run completes
- if same-day cache exists, some candidates recover with `bars_source = eastmoney_cache`
- if only one-day-stale cache exists, some supported names appear as low-confidence fallback

- [ ] **Step 3: Verify smoke artifacts**

Check:

- `result.full.cache-fallback.json`
  - same-day cache recoveries carry `bars_source = eastmoney_cache`
  - stale-cache rescues carry `low_confidence_fallback` and `fallback_cache_only`
  - stale-cache rescues are never in `T1`
- `report.full.cache-fallback.md`
  - fresh cache recoveries use the light `数据来源：Eastmoney cache` wording
  - stale-cache rescues use the explicit fallback wording

- [ ] **Step 4: Do not commit `.tmp` smoke artifacts**

If smoke artifacts remain only under `.tmp`, leave them uncommitted.

## Self-Review

- Spec coverage:
  - reuse existing Eastmoney cache: Tasks 1-2
  - trade-date freshness rules: Tasks 1-3
  - one-day-stale rescue only: Task 3
  - light source labeling for fresh cache: Task 4
  - focused verification and smoke: Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “similar to” shortcuts remain
  - every test task includes concrete test code
  - every code task includes concrete helper or logic snippets
- Type consistency:
  - `classify_eastmoney_cache_freshness(...)`
  - `choose_eastmoney_cache_recovery_mode(...)`
  - `build_bars_cache_rescue_candidate(...)`
  - `bars_source = eastmoney_cache`
  - `fallback_cache_only`
