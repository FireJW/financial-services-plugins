# Market Strength Supplement Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Phase 1 `market_strength_candidates` supplement lane so the shortlist can surface obvious same-day strong names that the current event-driven pipeline never sees, while keeping them out of `T1`.

**Architecture:** Extend the request/runtime contract with a new late-merge `market_strength_candidates` input, normalize it alongside existing discovery inputs, convert it into lightweight event-card style rows, and merge it only at discovery/tier-report surfaces. Keep the existing event-driven shortlist spine unchanged and enforce a hard boundary so supplement names only land in `T3`, `T4`, or clearly labeled reference/report sections.

**Tech Stack:** Python 3.12, existing `month-end-shortlist` runtime, existing discovery/event-card helpers, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - Normalize the new `market_strength_candidates` request field
  - Add helper functions to convert supplement rows into discovery/event-card compatible structures
  - Late-merge supplement rows into discovery/tier output
  - Enforce `T3/T4`-only boundary
  - Add report labeling for market-strength supplement names
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - Lock request passthrough / normalization behavior
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - Lock report labeling and placement
- Modify: `tests/test_screening_coverage_optimization.py`
  - Lock tier-boundary behavior so supplement names cannot enter `T1`
- Add: `tests/test_market_strength_supplement_lane.py`
  - Focused unit tests for supplement normalization and late-merge behavior

### Responsibility Boundaries

- `month_end_shortlist_runtime.py` owns all Phase 1 supplement-lane logic.
- The supplement lane is an additive late merge, not a replacement for event discovery.
- No compiled core changes are required in Phase 1.
- No formal execution / `T1` promotion may depend solely on supplement-lane inputs.

---

### Task 1: Normalize `market_strength_candidates` Input

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Add: `tests/test_market_strength_supplement_lane.py`

- [ ] **Step 1: Write the failing normalization test**

```python
def test_normalize_request_preserves_market_strength_candidates() -> None:
    normalized = module_under_test.normalize_request(
        {
            "template_name": "month_end_shortlist",
            "target_date": "2026-04-21",
            "market_strength_candidates": [
                {
                    "ticker": "002980.SZ",
                    "name": "华盛昌",
                    "strength_reason": "near_limit_close",
                    "close_strength": "high",
                    "volume_signal": "expanding",
                    "board_context": "high_conviction_momentum",
                    "theme_guess": ["short_term_momentum"],
                    "source": "market_strength_scan",
                }
            ],
        }
    )

    rows = normalized.get("market_strength_candidates")
    assert isinstance(rows, list)
    assert rows[0]["ticker"] == "002980.SZ"
    assert rows[0]["close_strength"] == "high"
    assert rows[0]["source"] == "market_strength_scan"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: FAIL because the normalization path does not preserve the new field yet

- [ ] **Step 3: Add minimal normalization helper**

```python
def normalize_market_strength_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": clean_text(raw.get("ticker")),
        "name": clean_text(raw.get("name")) or clean_text(raw.get("ticker")),
        "strength_reason": clean_text(raw.get("strength_reason")) or "close_near_high",
        "close_strength": clean_text(raw.get("close_strength")) or "medium",
        "volume_signal": clean_text(raw.get("volume_signal")) or "unclear",
        "board_context": clean_text(raw.get("board_context")) or "high_conviction_momentum",
        "theme_guess": [clean_text(item) for item in raw.get("theme_guess", []) if clean_text(item)],
        "source": clean_text(raw.get("source")) or "market_strength_scan",
    }
```

Then wire it inside `normalize_request(...)`:

```python
market_strength_rows = raw_payload.get("market_strength_candidates")
if isinstance(market_strength_rows, list):
    normalized["market_strength_candidates"] = [
        normalize_market_strength_candidate(item)
        for item in market_strength_rows
        if isinstance(item, dict) and clean_text(item.get("ticker"))
    ]
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_market_strength_supplement_lane.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: normalize market strength supplement inputs"
```

### Task 2: Convert Supplement Rows into Discovery/Event-Card Compatible Rows

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Add: `tests/test_market_strength_supplement_lane.py`

- [ ] **Step 1: Write the failing conversion test**

```python
def test_build_market_strength_discovery_candidates_converts_rows() -> None:
    rows = module_under_test.build_market_strength_discovery_candidates(
        [
            {
                "ticker": "002980.SZ",
                "name": "华盛昌",
                "strength_reason": "near_limit_close",
                "close_strength": "high",
                "volume_signal": "expanding",
                "board_context": "high_conviction_momentum",
                "theme_guess": ["short_term_momentum"],
                "source": "market_strength_scan",
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "002980.SZ"
    assert rows[0]["event_type"] == "market_strength_scan"
    assert rows[0]["benefit_type"] == "mapping"
    assert rows[0]["market_validation"]["relative_strength"] == "strong"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: FAIL because the helper does not exist yet

- [ ] **Step 3: Add the conversion helper**

```python
def build_market_strength_discovery_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = clean_text(row.get("ticker"))
        if not ticker:
            continue
        converted.append(
            {
                "ticker": ticker,
                "name": clean_text(row.get("name")) or ticker,
                "event_type": "market_strength_scan",
                "event_strength": "strong" if clean_text(row.get("close_strength")) == "high" else "medium",
                "chain_name": clean_text((row.get("theme_guess") or ["unknown"])[0]) or "unknown",
                "chain_role": "unknown",
                "benefit_type": "mapping",
                "sources": [
                    {
                        "source_type": "community_post",
                        "summary": clean_text(row.get("strength_reason")) or "market strength supplement",
                    }
                ],
                "market_validation": {
                    "volume_multiple_5d": 2.0 if clean_text(row.get("volume_signal")) == "expanding" else 1.0,
                    "breakout": clean_text(row.get("close_strength")) == "high",
                    "relative_strength": "strong" if clean_text(row.get("close_strength")) == "high" else "normal",
                    "chain_resonance": False,
                },
                "market_strength_source": clean_text(row.get("source")) or "market_strength_scan",
                "market_strength_reason": clean_text(row.get("strength_reason")),
                "market_strength_board_context": clean_text(row.get("board_context")),
            }
        )
    return converted
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_market_strength_supplement_lane.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add market strength supplement conversion helper"
```

### Task 3: Late-Merge Supplement Lane into Discovery Surfaces

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Write the failing merge test**

```python
def test_run_month_end_shortlist_merges_market_strength_candidates_into_discovery_surfaces() -> None:
    payload = {
        "template_name": "month_end_shortlist",
        "target_date": "2026-04-21",
        "market_strength_candidates": [
            {
                "ticker": "002980.SZ",
                "name": "华盛昌",
                "strength_reason": "near_limit_close",
                "close_strength": "high",
                "volume_signal": "expanding",
                "board_context": "high_conviction_momentum",
                "theme_guess": ["short_term_momentum"],
                "source": "market_strength_scan",
            }
        ],
    }

    with patch.object(module_under_test._compiled, "run_month_end_shortlist", return_value={
        "top_picks": [],
        "near_miss_candidates": [],
        "dropped_candidates": [],
        "diagnostic_scorecard": [],
        "filter_summary": {},
    }):
        result = module_under_test.run_month_end_shortlist(payload)

    tickers = [row["ticker"] for row in result.get("chain_tracking", [])]
    assert "002980.SZ" in tickers
```

- [ ] **Step 2: Run the focused passthrough test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v`

Expected: FAIL because supplement rows are not merged yet

- [ ] **Step 3: Wire late merge into `run_month_end_shortlist(...)`**

Inside wrapper runtime preparation:

```python
market_strength_candidates = deepcopy(prepared_payload.get("market_strength_candidates") or [])
```

Then before `build_discovery_candidates(...)`:

```python
supplement_rows = build_market_strength_discovery_candidates(market_strength_candidates)
discovery_rows = build_discovery_candidates(
    merge_discovery_candidate_inputs(
        list(discovery_candidates or []) + supplement_rows,
        auto_discovery_candidates,
    )
)
```

Also stamp supplement rows after `build_event_cards(...)`:

```python
for row in event_cards:
    if clean_text(row.get("primary_event_type")) == "market_strength_scan":
        row["market_strength_supplement"] = True
```

- [ ] **Step 4: Run the focused passthrough test to verify it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_profile_passthrough.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: merge market strength supplement lane late in runtime"
```

### Task 4: Enforce `T3/T4`-Only Boundary

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_screening_coverage_optimization.py`

- [ ] **Step 1: Write the failing tier-boundary tests**

```python
def test_market_strength_supplement_names_never_promote_into_t1() -> None:
    discovery_results = {
        "qualified": [
            {
                "ticker": "002980.SZ",
                "name": "华盛昌",
                "market_strength_supplement": True,
                "priority_score": 95,
                "discovery_bucket": "qualified",
            }
        ],
        "watch": [],
        "track": [],
    }

    tiers = module_under_test.assign_tiers(
        top_picks=[],
        near_miss_candidates=[],
        discovery_results=discovery_results,
        all_candidates=[],
        keep_threshold=60.0,
    )

    assert all(item["ticker"] != "002980.SZ" for item in tiers["T1"])
```

- [ ] **Step 2: Run the tier test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py -v`

Expected: FAIL because no supplement-specific boundary exists yet

- [ ] **Step 3: Add explicit boundary logic**

When assigning tiers, strip supplement rows from `qualified` before `T1/T2` promotion:

```python
qualified_rows = [
    row for row in discovery_results.get("qualified", [])
    if not bool(row.get("market_strength_supplement"))
]
supplement_watch_rows = [
    row for row in discovery_results.get("qualified", []) + discovery_results.get("watch", []) + discovery_results.get("track", [])
    if bool(row.get("market_strength_supplement"))
]
```

Then:

- use `qualified_rows` for normal `T2` discovery-qualified flow
- append `supplement_watch_rows` only to `T3` or `T4`
- stamp:

```python
row["tier_tags"] = row.get("tier_tags", []) + ["market_strength_supplement"]
```

- [ ] **Step 4: Run the tier test to verify it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_screening_coverage_optimization.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: keep market strength supplement names out of t1"
```

### Task 5: Render Clear Report Labeling

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Write the failing reporting test**

```python
def test_report_markdown_labels_market_strength_supplement_names() -> None:
    markdown = module_under_test.build_markdown_report(
        {
            "template_name": "month_end_shortlist",
            "target_date": "2026-04-21",
        },
        {
            "tier_output": {
                "T3": [
                    {
                        "ticker": "002980.SZ",
                        "name": "华盛昌",
                        "score": 0,
                        "wrapper_tier": "T3",
                        "tier_tags": ["market_strength_supplement"],
                    }
                ],
                "T1": [],
                "T2": [],
                "T4": [],
            }
        },
    )

    assert "市场强势补充" in markdown
    assert "002980.SZ" in markdown
```

- [ ] **Step 2: Run the degraded-reporting test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: FAIL because the label is not rendered yet

- [ ] **Step 3: Add minimal report labeling**

In tier-card / markdown rendering, when `market_strength_supplement` or
`market_strength_supplement` tag exists:

```python
if "market_strength_supplement" in tier_tags:
    descriptor = "市场强势补充"
```

Render that descriptor:

```python
lines.append(f"- `{ticker}` {name}: `市场强势补充`")
```

or append it into existing card subtitles where the file already follows that pattern.

- [ ] **Step 4: Run the degraded-reporting test to verify it passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: label market strength supplement names in reports"
```

### Task 6: Run Focused Regression and Sanity Review

**Files:**
- Modify: none
- Test: `tests/test_market_strength_supplement_lane.py`
- Test: `tests/test_month_end_shortlist_profile_passthrough.py`
- Test: `tests/test_screening_coverage_optimization.py`
- Test: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Run the focused regression set**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v
```

Expected:

- all tests PASS
- supplement names appear in discovery/report surfaces
- no supplement name reaches `T1`

- [ ] **Step 2: Perform a `.tmp` sanity run with a synthetic supplement name**

Create a minimal request file under `.tmp`:

```json
{
  "template_name": "month_end_shortlist",
  "target_date": "2026-04-21",
  "market_strength_candidates": [
    {
      "ticker": "002980.SZ",
      "name": "华盛昌",
      "strength_reason": "near_limit_close",
      "close_strength": "high",
      "volume_signal": "expanding",
      "board_context": "high_conviction_momentum",
      "theme_guess": ["short_term_momentum"],
      "source": "market_strength_scan"
    }
  ]
}
```

Run:

```bash
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" "D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py" "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\market-strength-supplement-smoke\request.json" --output "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\market-strength-supplement-smoke\result.json" --markdown-output "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\market-strength-supplement-smoke\report.md"
```

Expected:

- `002980.SZ` appears in `T3` or `T4`, or discovery/reference surfaces
- it does not appear in `T1`
- markdown includes `市场强势补充`

- [ ] **Step 3: Commit final verified state**

```bash
git add tests/test_market_strength_supplement_lane.py tests/test_month_end_shortlist_profile_passthrough.py tests/test_screening_coverage_optimization.py tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add market strength supplement lane"
```

---

## Self-Review

### Spec Coverage

- New lane contract: covered in Task 1 and Task 2
- Late merge: covered in Task 3
- `T3/T4`-only boundary: covered in Task 4
- Report labeling: covered in Task 5
- Sanity smoke and focused regression: covered in Task 6

### Placeholder Scan

- No `TBD` / `TODO`
- Every code-changing step contains concrete code
- Every validation step contains an exact command

### Type Consistency

- New contract name stays consistent: `market_strength_candidates`
- New discovery helper name stays consistent: `build_market_strength_discovery_candidates`
- New report tag stays consistent: `market_strength_supplement`
