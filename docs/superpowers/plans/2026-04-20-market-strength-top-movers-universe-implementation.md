# Market Strength Top Movers Universe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated top-movers / close-strength universe fetcher for the
`market_strength_candidates` supplement lane so obvious strong names do not
depend on the main shortlist's turnover-ranked universe.

**Architecture:** Keep the main event-driven shortlist on the existing
`default_universe_fetcher(...)`, add a new
`default_market_strength_universe_fetcher(...)` that uses a mover-oriented
Eastmoney `clist` query, and feed that result into the existing
`build_market_strength_candidates_from_universe(...)` helper. Preserve all
existing supplement-lane boundaries so generated names still surface only in
`T3`, `T4`, and labeled report/reference sections.

**Tech Stack:** Python 3.12, existing `month-end-shortlist` runtime, Eastmoney
`clist`, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - add the dedicated top-movers universe fetcher
  - keep the current main shortlist universe fetcher unchanged
  - rewire supplement auto-generation to use the new fetcher
- Modify: `tests/test_market_strength_supplement_lane.py`
  - add focused tests for the new fetcher defaults and supplement-lane source
    behavior
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - lock integration behavior when `run_month_end_shortlist(...)` calls the new
    market-strength universe fetcher
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - optionally add a small reporting regression if the source label becomes more
    specific

### Responsibility Boundaries

- `default_universe_fetcher(...)` remains the main shortlist input and must not
  change behavior.
- `default_market_strength_universe_fetcher(...)` exists only for the supplement
  lane.
- No changes to compiled core or `T1` promotion rules are allowed.

---

## Task 1: Add Failing Tests for the New Universe Fetch Path

**Files:**
- Modify: `tests/test_market_strength_supplement_lane.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Add a focused unit test for the top-movers fetcher defaults**

Verify the new fetcher uses:

- Eastmoney `clist`
- mover-oriented ordering rather than `fid = f6`
- a wider bounded size such as `200` or `300`

Example test shape:

```python
def test_default_market_strength_universe_fetcher_uses_top_movers_query(self) -> None:
    ...
    self.assertEqual(parsed["fid"], "f3")
    self.assertEqual(parsed["pz"], "200")
```

- [ ] **Step 2: Add an integration-style failing test**

Lock that `run_month_end_shortlist(...)`:

- still calls the main `universe_fetcher(...)` for the shortlist
- separately calls the new market-strength fetcher for supplement discovery
- merges the generated rows into `market_strength_candidates`

- [ ] **Step 3: Run focused tests and confirm failure before implementation**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- tests fail because the new fetcher and wiring do not exist yet

---

## Task 2: Implement `default_market_strength_universe_fetcher(...)`

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Add the new fetch helper**

Add a new helper near the existing universe fetch logic:

```python
def default_market_strength_universe_fetcher(request: dict[str, Any]) -> list[dict[str, Any]]:
    ...
```

- [ ] **Step 2: Keep the request contract simple**

Support one optional override only:

- `market_strength_universe_limit`

If missing, use a fixed default such as:

- `200`

- [ ] **Step 3: Use a mover-oriented Eastmoney query**

Phase 1 should:

- keep the current mainland market groups
- stop using turnover-first ordering
- prefer `fid = f3`

Keep the response field set compatible with the current
`build_market_strength_candidates_from_universe(...)` helper.

- [ ] **Step 4: Preserve soft-failure expectations**

If the fetch fails:

- raise a distinct fetch error internally or return an empty list based on the
  current runtime error-handling pattern
- do not let the supplement fetch collapse the whole report

---

## Task 3: Rewire Supplement Auto-Generation to Use the New Fetcher

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Extend `run_month_end_shortlist(...)` signature**

Add an injectable fetcher parameter:

```python
market_strength_universe_fetcher: Any = default_market_strength_universe_fetcher
```

- [ ] **Step 2: Keep the main universe flow untouched**

This logic should remain as-is:

```python
full_universe = universe_fetcher(prepared_payload)
```

That fetch continues to power:

- board split
- main shortlist evaluation

- [ ] **Step 3: Call the new top-movers fetcher only for supplement generation**

Recommended structure:

```python
market_strength_universe = market_strength_universe_fetcher(prepared_payload)
generated_market_strength = build_market_strength_candidates_from_universe(
    market_strength_universe,
    existing_tickers=existing_tickers,
    max_names=10,
)
```

- [ ] **Step 4: Keep existing merge semantics**

Continue using:

- `merge_market_strength_candidate_inputs(...)`

Request-provided rows must still win over generated rows.

---

## Task 4: Add or Update Reporting Expectations

**Files:**
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py` only if needed

- [ ] **Step 1: Decide whether to keep or refine the source label**

If Phase 1 keeps:

- `market_strength_scan`

then no reporting change is required.

If Phase 1 refines to:

- `market_strength_top_movers`

then add a regression that confirms the report still renders:

- `市场强势补充`

without confusing this lane with formal execution rows.

- [ ] **Step 2: Verify no `T1` behavior changes**

The new universe fetch path must not affect:

- `T1`
- `T2`
- main event-driven rankings

Reuse existing supplement-lane coverage tests where possible.

---

## Task 5: Verification Ladder

- [ ] **Step 1: Focused fetcher and wiring tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

- [ ] **Step 2: Focused supplement-lane regression**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

- [ ] **Step 3: Real runtime smoke**

Run one real next-session request and verify:

- auto-generated supplement names appear
- the supplement lane still does not create `T1`
- names previously absent due to the turnover-ranked universe can now appear if
  they are in the mover-oriented fetch

Suggested artifacts:

- `.tmp/next-session-2026-04-21/result.full.top-movers-market-strength.json`
- `.tmp/next-session-2026-04-21/report.full.top-movers-market-strength.md`

---

## Task 6: Completion Criteria

- [ ] `default_universe_fetcher(...)` behavior remains unchanged
- [ ] new `default_market_strength_universe_fetcher(...)` exists and is covered
      by tests
- [ ] supplement auto-generation no longer depends on the turnover-ranked main
      universe
- [ ] generated names still only reach:
  - `T3`
  - `T4`
  - reference/report layers
- [ ] focused verification passes
- [ ] at least one real runtime smoke confirms the new fetch path is used
