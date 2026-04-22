# Claude Handoff: Cache-First Execution Closure

Date: `2026-04-21`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `feat/cache-first-execution-closure`

## 1. Why this handoff exists

The user asked to stop here and hand the remaining Iteration 3 work to Claude.

This branch is already aligned to the new implementation plan:

- Plan:
  `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\plans\2026-04-21-cache-first-execution-closure-implementation.md`
- Spec/design context:
  `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\specs\2026-04-21-cache-first-execution-closure-design.md`

I started exactly where the plan says to start:

- use `executing-plans`
- use `test-driven-development`
- stay out of `main`
- do **not** create a git worktree from the Codex sandbox because repo
  `AGENTS.md` forbids it

No production code has been changed yet. The work is still in the red-test
phase for Task 1.

## 2. Current repo state

Current branch:

- `feat/cache-first-execution-closure`

Current modified file:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`

Other current untracked docs in tree:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\notes\2026-04-19-claude-handoff-eastmoney-push2his-instability.md`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\plans\2026-04-21-cache-first-execution-closure-implementation.md`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\specs\2026-04-21-cache-first-execution-closure-design.md`

Leave those alone unless the user explicitly asks to clean them up.

## 3. What has already been done

I added the Task 1 red tests in:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`

Specifically:

1. Added `test_infer_execution_state_defaults_plain_candidates_to_live`
2. Added `test_bars_fetch_failure_record_is_marked_as_blocked_execution_state`
3. Tightened same-day cache replay coverage to assert
   `result["execution_state"] == "fresh_cache"`

I then ran the focused Task 1 pytest command from the plan.

Command used:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py" -q
```

Result:

- `3 failed, 53 passed`

This is the expected red state for Task 1.

## 4. Exact failing signals

Current failing tests:

1. `test_infer_execution_state_defaults_plain_candidates_to_live`
   - failure:
     `AttributeError: module 'month_end_shortlist_runtime' has no attribute 'infer_execution_state'`

2. `test_bars_fetch_failure_record_is_marked_as_blocked_execution_state`
   - failure:
     `KeyError: 'execution_state'`
   - source path missing the field:
     `build_bars_fetch_failed_candidate(...)`

3. `test_wrap_assess_candidate_recovers_from_same_day_eastmoney_cache`
   - failure:
     `KeyError: 'execution_state'`
   - source path missing the field:
     same-day Eastmoney cache replay inside
     `wrap_assess_candidate_with_bars_failure_fallback(...)`

This is a good TDD checkpoint because the failures are about the intended
behavior gap, not broken tests.

## 5. One important gap still left in Task 1 test setup

The plan also says to tighten the stale-cache rescue assertion in:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`

That test already exists:

- `test_one_day_stale_cache_with_support_can_rescue_into_low_confidence_t3`

It currently asserts:

- rescue is not `None`
- `low_confidence_fallback` is present
- `fallback_cache_only` is present
- `fallback_support_reason == "structured_catalyst"`

It does **not** yet assert:

```python
self.assertEqual(recovered["execution_state"], "stale_cache")
```

So Claude should add that assertion first to fully match Task 1 Step 1 of the
plan, then re-run the same focused pytest command to confirm the red state is
still the intended one.

## 6. Immediate next implementation steps for Claude

Follow Task 1 of the plan in order.

### Step 1

Finish the missing stale-cache red assertion in:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`

### Step 2

Implement the minimal execution-state helper in:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

Plan target:

```python
def infer_execution_state(candidate: dict[str, Any]) -> str:
    tier_tags = set(candidate.get("tier_tags", []) or [])
    failures = set(candidate.get("hard_filter_failures", []) or [])
    if candidate.get("fallback_cache_only") or "fallback_cache_only" in tier_tags:
        return "stale_cache"
    if clean_text(candidate.get("bars_source")) == "eastmoney_cache":
        return "fresh_cache"
    if candidate.get("fallback_snapshot_only") or "bars_fetch_failed" in failures:
        return "blocked"
    return "live"
```

### Step 3

Thread `execution_state` through the existing candidate-shaping paths called out
by the plan:

1. `build_bars_fetch_failed_candidate(...)` -> `"blocked"`
2. `build_bars_fallback_rescue_candidate(...)` -> `"blocked"`
3. `build_bars_cache_rescue_candidate(...)` -> `"stale_cache"`
4. same-day cache replay path in
   `wrap_assess_candidate_with_bars_failure_fallback(...)` -> `"fresh_cache"`
5. export `infer_execution_state` via `__all__`

### Step 4

Re-run the focused Task 1 pytest command until green.

### Step 5

Only after Task 1 is green, continue with Task 2 and Task 3 from the same
implementation plan.

## 7. Repo-specific constraints to remember

From repo `AGENTS.md`:

- do **not** create `git worktree add` directories from the sandbox
- use the existing repo and branch instead
- run git commands serially, not in parallel

That constraint was already followed for this branch.

## 8. Safe starting point for Claude

Claude can start by opening these files:

1. `D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\plans\2026-04-21-cache-first-execution-closure-implementation.md`
2. `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
3. `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`
4. `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

The key fact is simple:

- red tests are already established for the fresh-cache / blocked gaps
- one stale-cache assertion still needs to be added
- production implementation has not started yet
