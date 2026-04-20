# Market Strength Auto Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically generate daily `market_strength_candidates` from the existing full-universe market snapshot so obvious strong names enter the supplement lane without manual ticker input.

**Architecture:** Add a deterministic universe-scanning helper in `month_end_shortlist_runtime.py` that ranks a small set of close-strength-first names, applies hard exclusions, deduplicates against request-provided supplement rows and formal event-discovery names, and then feeds the generated rows into the already-built `market_strength_candidates` lane. Keep the existing supplement-lane boundaries unchanged so auto-generated names still surface only in `T3`, `T4`, and labeled reference/report sections.

**Tech Stack:** Python 3.12, existing `month-end-shortlist` runtime, existing supplement-lane helper path, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - add the auto-generation helper
  - add exclusion, scoring, dedup, and merge helpers
  - wire generated rows into `run_month_end_shortlist(...)`
- Modify: `tests/test_market_strength_supplement_lane.py`
  - add focused unit tests for generator ranking, exclusions, and dedup behavior
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - lock integration behavior when `run_month_end_shortlist(...)` auto-generates supplement names from `full_universe`
- Modify: `tests/test_board_threshold_overrides.py`
  - add a small integration-style regression proving board-split flow still works when generated supplement rows are fed after full-universe fetch

### Responsibility Boundaries

- `month_end_shortlist_runtime.py` owns all Phase 1 auto-generation logic.
- The auto-generator must only produce `market_strength_candidates`; it must not invent a new downstream contract.
- The existing supplement lane remains the only place where the generated names get surfaced into discovery, tiers, and reports.
- No changes to compiled core or `T1` promotion rules are allowed in this plan.

---

### Task 1: Add Failing Tests for Generator Selection and Exclusions

**Files:**
- Modify: `tests/test_market_strength_supplement_lane.py`

- [ ] **Step 1: Write the failing generator tests**

```python
def test_build_market_strength_candidates_from_universe_selects_strongest_close_names(self) -> None:
    rows = module_under_test.build_market_strength_candidates_from_universe(
        [
            {
                "ticker": "603268.SS",
                "name": "松发股份",
                "day_pct": 9.6,
                "price": 21.9,
                "high": 22.0,
                "low": 20.2,
                "pre_close": 20.0,
                "day_turnover_cny": 880000000.0,
                "turnover_rate_pct": 11.2,
            },
            {
                "ticker": "002980.SZ",
                "name": "华盛昌",
                "day_pct": 7.4,
                "price": 33.5,
                "high": 33.8,
                "low": 31.8,
                "pre_close": 31.2,
                "day_turnover_cny": 620000000.0,
                "turnover_rate_pct": 9.1,
            },
        ],
        existing_tickers=set(),
        max_names=5,
    )

    self.assertEqual([item["ticker"] for item in rows], ["603268.SS", "002980.SZ"])
    self.assertEqual(rows[0]["source"], "market_strength_scan")
```

```python
def test_build_market_strength_candidates_from_universe_excludes_st_illiquid_and_duplicate_names(self) -> None:
    rows = module_under_test.build_market_strength_candidates_from_universe(
        [
            {
                "ticker": "000001.SZ",
                "name": "*ST示例",
                "day_pct": 5.0,
                "price": 5.2,
                "high": 5.2,
                "low": 5.0,
                "pre_close": 4.95,
                "day_turnover_cny": 500000000.0,
                "turnover_rate_pct": 6.0,
            },
            {
                "ticker": "000002.SZ",
                "name": "低流动性样本",
                "day_pct": 8.0,
                "price": 8.5,
                "high": 8.5,
                "low": 8.0,
                "pre_close": 7.8,
                "day_turnover_cny": 30000000.0,
                "turnover_rate_pct": 0.4,
            },
            {
                "ticker": "603268.SS",
                "name": "松发股份",
                "day_pct": 9.6,
                "price": 21.9,
                "high": 22.0,
                "low": 20.2,
                "pre_close": 20.0,
                "day_turnover_cny": 880000000.0,
                "turnover_rate_pct": 11.2,
            },
        ],
        existing_tickers={"603268.SS"},
        max_names=5,
    )

    self.assertEqual(rows, [])
```

- [ ] **Step 2: Run the focused test file to verify the new tests fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: FAIL because the generator helper does not exist yet

- [ ] **Step 3: Commit the failing-test checkpoint only if your workflow requires it**

```bash
git add tests/test_market_strength_supplement_lane.py
git commit -m "test: add failing market strength auto-generator cases"
```

If you prefer not to commit red tests, skip this commit and proceed directly to Task 2.

### Task 2: Implement the Generator Helper and Merge Helpers

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Add the minimal helper skeleton**

```python
def build_market_strength_candidates_from_universe(
    universe_rows: list[dict[str, Any]],
    *,
    existing_tickers: set[str],
    max_names: int = 10,
) -> list[dict[str, Any]]:
    ...
```

```python
def merge_market_strength_candidate_inputs(
    request_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ...
```

- [ ] **Step 2: Implement hard exclusions first**

Use explicit exclusion helpers instead of burying conditions inline:

```python
def is_market_strength_excluded(row: dict[str, Any], existing_tickers: set[str]) -> bool:
    name = clean_text(row.get("name"))
    ticker = clean_text(row.get("ticker"))
    if not ticker or ticker in existing_tickers:
        return True
    if "ST" in name.upper():
        return True
    if to_float(row.get("day_turnover_cny")) < 100_000_000:
        return True
    if (
        to_float(row.get("turnover_rate_pct")) < 0.5
        and to_float(row.get("price")) == to_float(row.get("high"))
        and to_float(row.get("price")) == to_float(row.get("low"))
    ):
        return True
    return False
```

- [ ] **Step 3: Implement a simple close-strength-first score**

Use a deterministic formula that rewards:

- same-day strength
- close near high
- enough turnover

Keep it intentionally simple:

```python
def market_strength_score(row: dict[str, Any]) -> float:
    pre_close = max(to_float(row.get("pre_close")), 0.01)
    price = to_float(row.get("price"))
    high = to_float(row.get("high"))
    low = to_float(row.get("low"))
    day_pct = to_float(row.get("day_pct"))
    turnover = to_float(row.get("day_turnover_cny"))

    close_to_high = 0.0
    if high > low:
        close_to_high = (price - low) / (high - low)

    turnover_score = min(turnover / 1_000_000_000, 3.0)
    return round(day_pct * 2.0 + close_to_high * 5.0 + turnover_score, 4)
```

- [ ] **Step 4: Build generated rows using the existing supplement contract**

```python
generated.append(
    normalize_market_strength_candidate(
        {
            "ticker": ticker,
            "name": name,
            "strength_reason": "near_limit_close" if day_pct >= 8.0 and close_to_high >= 0.8 else "close_near_high",
            "close_strength": "high" if close_to_high >= 0.8 else "medium",
            "volume_signal": "expanding" if turnover >= 300_000_000 else "normal",
            "board_context": "high_conviction_momentum" if day_pct >= 8.0 else "trend_follow_through",
            "theme_guess": [],
            "source": "market_strength_scan",
        }
    )
)
```

- [ ] **Step 5: Deduplicate with request rows winning**

```python
def merge_market_strength_candidate_inputs(
    request_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in request_rows + generated_rows:
        ticker = clean_text(row.get("ticker"))
        if not ticker or ticker in seen:
            continue
        merged.append(row)
        seen.add(ticker)
    return merged
```

- [ ] **Step 6: Run the focused generator test file and make sure it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_market_strength_supplement_lane.py
git commit -m "feat: add market strength auto-generator helper"
```

### Task 3: Wire the Generator into `run_month_end_shortlist(...)`

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Write the failing integration test**

```python
def test_run_month_end_shortlist_auto_generates_market_strength_candidates_from_universe(self) -> None:
    universe_rows = [
        {
            "ticker": "603268.SS",
            "name": "松发股份",
            "day_pct": 9.6,
            "price": 21.9,
            "high": 22.0,
            "low": 20.2,
            "pre_close": 20.0,
            "day_turnover_cny": 880000000.0,
            "turnover_rate_pct": 11.2,
        }
    ]

    def fake_compiled_run(payload: dict, **_: object) -> dict:
        return {
            "status": "ok",
            "request": payload,
            "filter_summary": {},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-21\n",
        }

    with patch.object(module_under_test._compiled, "run_month_end_shortlist", side_effect=fake_compiled_run):
        result = module_under_test.run_month_end_shortlist(
            {"template_name": "month_end_shortlist", "target_date": "2026-04-21"},
            universe_fetcher=lambda _: universe_rows,
        )

    tickers = [row["ticker"] for row in result.get("priority_watchlist", [])]
    self.assertIn("603268.SS", tickers)
```

- [ ] **Step 2: Run the passthrough test file to verify the new test fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v`

Expected: FAIL because the runtime does not auto-generate supplement names yet

- [ ] **Step 3: Wire the generator right after `full_universe` fetch**

Inside `run_month_end_shortlist(...)`, after:

```python
full_universe = universe_fetcher(prepared_payload)
```

add:

```python
request_market_strength = deepcopy(prepared_payload.get("market_strength_candidates") or [])
request_tickers = {clean_text(row.get("ticker")) for row in request_market_strength if clean_text(row.get("ticker"))}
event_tickers = {clean_text(row.get("ticker")) for row in discovery_candidates if clean_text(row.get("ticker"))}
existing_tickers = request_tickers | event_tickers
generated_market_strength = build_market_strength_candidates_from_universe(
    full_universe,
    existing_tickers=existing_tickers,
    max_names=10,
)
market_strength_candidates = merge_market_strength_candidate_inputs(
    request_market_strength,
    generated_market_strength,
)
```

Then pass `market_strength_candidates` down to `merge_track_results(...)` just as the supplement-lane work already expects.

- [ ] **Step 4: Run the passthrough test file and make sure it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_month_end_shortlist_profile_passthrough.py
git commit -m "feat: auto-generate market strength supplement names"
```

### Task 4: Lock Board-Split and Duplicate-Suppression Regressions

**Files:**
- Modify: `tests/test_board_threshold_overrides.py`
- Modify: `tests/test_market_strength_supplement_lane.py`

- [ ] **Step 1: Add a regression that board-split behavior is unaffected**

```python
def test_split_universe_by_board_ignores_market_strength_generation_inputs(self):
    payload = {
        "universe_candidates": [
            {"ticker": "000988.SZ", "name": "华工科技"},
            {"ticker": "300857.SZ", "name": "协创数据"},
        ],
        "market_strength_candidates": [
            {"ticker": "603268.SS", "name": "松发股份"}
        ],
    }
    tracks, out_of_scope = m.split_universe_by_board(payload)
    self.assertEqual(sorted(c["ticker"] for c in tracks["main_board"]["universe_candidates"]), ["000988.SZ"])
    self.assertEqual(sorted(c["ticker"] for c in tracks["chinext"]["universe_candidates"]), ["300857.SZ"])
    self.assertEqual(out_of_scope, [])
```

- [ ] **Step 2: Add a regression that request-provided rows win on duplicate tickers**

```python
def test_merge_market_strength_candidate_inputs_prefers_request_rows(self) -> None:
    merged = module_under_test.merge_market_strength_candidate_inputs(
        [
            {
                "ticker": "603268.SS",
                "name": "松发股份",
                "strength_reason": "manual_override",
                "close_strength": "medium",
                "volume_signal": "normal",
                "board_context": "trend_follow_through",
                "theme_guess": [],
                "source": "market_strength_scan",
            }
        ],
        [
            {
                "ticker": "603268.SS",
                "name": "松发股份",
                "strength_reason": "near_limit_close",
                "close_strength": "high",
                "volume_signal": "expanding",
                "board_context": "high_conviction_momentum",
                "theme_guess": [],
                "source": "market_strength_scan",
            }
        ],
    )

    self.assertEqual(len(merged), 1)
    self.assertEqual(merged[0]["strength_reason"], "manual_override")
```

- [ ] **Step 3: Run the three focused files together**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py -v --tb=short
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_market_strength_supplement_lane.py tests/test_month_end_shortlist_profile_passthrough.py tests/test_board_threshold_overrides.py
git commit -m "test: lock market strength auto-generator regressions"
```

### Task 5: Run Final Focused Regression and a Deterministic Sanity Check

**Files:**
- Modify: none

- [ ] **Step 1: Run the full focused regression set**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- all tests PASS
- no regressions to existing supplement-lane behavior
- no regressions to board split logic

- [ ] **Step 2: Run a deterministic sanity check with a mocked universe**

Use an inline Python one-off that imports `month_end_shortlist_runtime`, supplies a mocked `universe_fetcher`, and verifies the result contains a generated supplement name in `priority_watchlist` or `chain_tracking` but not in `directly_actionable`.

```python
result = runtime.run_month_end_shortlist(
    {"template_name": "month_end_shortlist", "target_date": "2026-04-21"},
    universe_fetcher=lambda _: [
        {
            "ticker": "603268.SS",
            "name": "松发股份",
            "day_pct": 9.6,
            "price": 21.9,
            "high": 22.0,
            "low": 20.2,
            "pre_close": 20.0,
            "day_turnover_cny": 880000000.0,
            "turnover_rate_pct": 11.2,
        }
    ],
)
assert "603268.SS" in {row["ticker"] for row in result.get("priority_watchlist", [])}
assert "603268.SS" not in {row["ticker"] for row in result.get("directly_actionable", [])}
```

- [ ] **Step 3: Commit final verified state**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_market_strength_supplement_lane.py tests/test_month_end_shortlist_profile_passthrough.py tests/test_board_threshold_overrides.py
git commit -m "feat: auto-generate market strength supplement names from universe"
```

---

## Self-Review

### Spec Coverage

- reuse existing full-universe snapshot: covered in Task 3
- bounded `5-10` name output: covered in Task 2 / Task 3
- close-strength-first ranking: covered in Task 2
- hard exclusions: covered in Task 2
- request rows win over generated duplicates: covered in Task 4
- no new downstream contract: covered in Task 2 and Task 3
- no `T1` promotion changes: inherited by existing supplement-lane tests and re-verified in Task 5

### Placeholder Scan

- no `TBD` / `TODO`
- every code-changing step contains concrete code
- every verification step contains exact commands

### Type Consistency

- new helper name stays consistent: `build_market_strength_candidates_from_universe`
- merge helper name stays consistent: `merge_market_strength_candidate_inputs`
- generated rows still use existing `market_strength_candidates` contract
