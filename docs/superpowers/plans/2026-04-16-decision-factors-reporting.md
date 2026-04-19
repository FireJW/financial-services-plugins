# Decision Factors Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current shortlist wrapper output from compact action labels into a richer decision-factors layer that explains why a candidate is `可执行`, `继续观察`, or `不执行`.

**Architecture:** Keep all logic in the Python wrapper/postprocessing layer around the compiled shortlist runtime. Reuse already available `history_by_ticker`, `price_snapshot`, `structured_catalyst_snapshot`, `trade_card`, and score/threshold data to build readable narratives and structured decision-factor records. Do not modify the compiled shortlist core or scoring logic.

**Tech Stack:** Python 3.12, wrapper module `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`, pytest.

---

### Task 1: Add Failing Tests For Decision-Factors Output

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`
- Test: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add a failing test for detailed `near_miss` decision factors**

Add a test that builds an `enrich_live_result_reporting(...)` input with:
- `filter_summary.keep_threshold = 70.0`
- one `diagnostic_scorecard` item for `002837.SZ`
- populated `price_snapshot`, `structured_catalyst_snapshot`, and `trade_card`

Assert the enriched result contains a new `decision_factors` structure and the report contains:
- `## Decision Factors`
- `### 继续观察`
- a per-ticker block for `002837.SZ`
- narrative lines covering:
  - current shape
  - what it likely means
  - what may happen next
  - why action is `继续观察`

- [ ] **Step 2: Add a failing test for detailed `qualified` decision factors**

Add a test that starts from a result with non-empty `top_picks` for a qualified name (e.g. `001309.SZ`) and asserts the enriched output contains:
- action `可执行`
- a decision-factor entry under `qualified`
- report content with:
  - `### 可执行`
  - technical-factor explanation
  - event/catalyst explanation
  - action rationale

- [ ] **Step 3: Add a failing test for concise `blocked` decision factors**

Add a test that uses a blocked candidate (e.g. `601600.SS`) and asserts:
- action `不执行`
- entry under `blocked`
- report content under `### 不执行`
- concise explanation only, not the full long-form template used for qualified/near_miss

- [ ] **Step 4: Run the focused test file and confirm it fails for the new behavior**

Run: `& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest 'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py' -q`

Expected: FAIL on missing `decision_factors` structure / report sections.


### Task 2: Implement Wrapper-Level Decision-Factors Builders

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add helper functions for narrative building**

In `month_end_shortlist_runtime.py`, add small focused helpers for:
- `build_technical_factor_summary(...)`
- `build_catalyst_factor_summary(...)`
- `build_action_rationale(...)`
- `build_next_watch_items(...)`

Rules:
- Use existing fields only
- Prefer `history_by_ticker` when available
- If technical evidence is insufficient, explicitly say so
- Do not print raw MACD/KDJ/BOLL numeric values; translate them into readable shape language

- [ ] **Step 2: Add a structured `decision_factors` builder**

Add a helper like:
- `build_decision_factor_entry(candidate, action, request, history_by_ticker)`
- `build_decision_factors_from_result(enriched_result)`

Expected output shape:

```python
{
  "qualified": [...],
  "near_miss": [...],
  "blocked": [...]
}
```

Each `qualified` / `near_miss` entry should include:
- `ticker`
- `name`
- `action`
- `status`
- `score`
- `keep_threshold_gap`
- `technical_summary`
- `event_summary`
- `logic_summary`
- `next_watch_items`

Each `blocked` entry should include the same identity/action fields but a shorter explanation payload.

- [ ] **Step 3: Integrate `decision_factors` into `enrich_live_result_reporting(...)`**

After the existing `midday_action_summary` is built:
- compute the `decision_factors` structure
- attach it to the enriched JSON result
- append a new report section:

```markdown
## Decision Factors

### 可执行
...

### 继续观察
...

### 不执行
...
```

Formatting rules:
- `qualified` and `near_miss`: richer multi-line blocks
- `blocked`: concise 3-5 lines

- [ ] **Step 4: Keep existing behavior intact**

Do not remove or rename:
- `Dropped Candidates`
- `Diagnostic Scorecard`
- `Near Miss Candidates`
- `午盘操作建议摘要`

The new section should layer on top of the existing output rather than replace it.


### Task 3: Verify Wrapper Regression And Real Samples

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\result.json`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\report.md`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\result.json`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\report.md`

- [ ] **Step 1: Run the wrapper regression set**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py' `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_candidate_snapshot_enrichment.py' `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_candidate_fetch_fallback.py' `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_benchmark_fallback.py' `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_shim.py' -q
```

Expected: all pass.

- [ ] **Step 2: Re-run the live two-ticker sample**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' `
  'D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py' `
  'D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\request.json' `
  --output 'D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\result.json' `
  --markdown-output 'D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\report.md'
```

Expected:
- result still completes successfully
- summary still says `不执行` / `继续观察`
- report now includes `## Decision Factors`

- [ ] **Step 3: Re-run the qualified sample postprocessor**

Run a small Python snippet that:
- loads `D:\Users\rickylu\dev\financial-services-plugins\.tmp\month-end-shortlist-live-baseline-2026-04-10.result.json`
- calls `enrich_live_result_reporting(...)`
- writes:
  - `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\result.json`
  - `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\report.md`

Expected:
- `midday_action_summary` still marks the names `可执行`
- report includes `## Decision Factors`

- [ ] **Step 4: Commit**

```powershell
git add D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py `
        D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py `
        D:\Users\rickylu\dev\financial-services-stock\docs\superpowers\plans\2026-04-16-decision-factors-reporting.md
git commit -m "feat: add detailed decision-factors reporting"
```
