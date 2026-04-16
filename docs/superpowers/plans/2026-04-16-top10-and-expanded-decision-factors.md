# Top10 And Expanded Decision Factors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand shortlist reporting so the output can review up to 10 top picks and provide denser per-name decision factors without changing the compiled shortlist core.

**Architecture:** Keep all changes in the wrapper/reporting layer around the compiled month-end-shortlist runtime. Reuse the existing result payload (`top_picks`, `diagnostic_scorecard`, `price_snapshot`, `structured_catalyst_snapshot`, `trade_card`, `score_components`) to enrich the rendered report and JSON structure. Do not modify compiled scoring, ranking, or filtering internals.

**Tech Stack:** Python 3.12, wrapper module `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`, pytest.

---

### Task 1: Add Failing Tests For Top10 And Expanded Decision Factors

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`
- Test: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add a failing test that caps rendered qualified picks at 10**

Add a test that builds a result with `top_picks` length `12` and asserts the enriched output:
- keeps only `10` items in a new wrapper-facing rendered list (or capped decision-factor qualified section)
- includes the first ten qualified names in report output
- excludes the 11th and 12th names from the `Decision Factors` report section

- [ ] **Step 2: Add a failing test for richer qualified card content**

Create a `top_picks` item containing:
- `score`
- `price`
- `price_snapshot`
- `structured_catalyst_within_window`
- `scheduled_earnings_date`
- `trade_card`
- `price_paths`
- `score_components`

Assert the enriched report contains for the qualified section:
- `技术形态`
- `关键事件`
- `判断逻辑`
- `观察点`
- a brief trading-layer readout (`trade_card` / invalidation / scenario or risk-reward)

- [ ] **Step 3: Add a failing test for richer near-miss card content**

Use a near-miss assessed candidate with:
- `price_snapshot`
- `structured_catalyst_snapshot`
- `trade_card`
- `score_components`

Assert the near-miss factor includes:
- what the current shape is
- what it likely means
- what is more likely next
- what to watch this afternoon / next session

- [ ] **Step 4: Add a failing test for concise blocked card content**

Use a blocked candidate and assert:
- it still gets a shorter card than qualified/near_miss
- it includes the core structural issue
- it includes event support weakness when applicable
- it does not dump a full trade-card style block

- [ ] **Step 5: Run the focused test file to confirm RED**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected: FAIL for missing top10 cap and missing expanded narrative content.


### Task 2: Implement Wrapper-Level Top10 And Expanded Decision Factors

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add constants for reporting limits**

Add wrapper-only constants near the top of `month_end_shortlist_runtime.py`:

```python
MAX_REPORTED_TOP_PICKS = 10
MAX_REPORTED_NEAR_MISS = 5
MAX_REPORTED_BLOCKED = 5
MAX_REPORTED_WATCH_ITEMS = 3
```

- [ ] **Step 2: Add helper(s) for richer narrative assembly**

Add focused helpers such as:
- `build_shape_interpretation(...)`
- `build_likely_next_move(...)`
- `build_trade_layer_summary(...)`

Rules:
- Use existing fields only
- Prefer readable Chinese decision language
- Do not print raw MACD/KDJ/BOLL values
- Translate available evidence into:
  - 当前形态
  - 大概率意味着什么
  - 接下来更可能发生什么
  - 对应动作为什么成立

- [ ] **Step 3: Expand `build_decision_factor_entry(...)`**

Extend the returned payload so qualified and near-miss entries include:
- `shape_summary`
- `likely_next_summary`
- `trade_layer_summary`
- `event_summary`
- `logic_summary`
- `next_watch_items`

Blocked entries should still include the same schema but with shorter content.

- [ ] **Step 4: Cap the rendered counts in report generation**

When building sections:
- `qualified`: at most `10`
- `near_miss`: at most `5`
- `blocked`: at most `5`

Do not mutate compiled shortlist internals. This is a report/output cap only.

- [ ] **Step 5: Upgrade the `Decision Factors` report section**

Keep the section structure:

```markdown
## Decision Factors

### 可执行
...

### 继续观察
...

### 不执行
...
```

But render richer blocks:
- `qualified`: 6-10 lines
- `near_miss`: 5-8 lines
- `blocked`: 3-5 lines

Each block should include:
- 动作
- 分数
- 与 keep line 差距（if present）
- 技术形态
- 关键事件
- 判断逻辑
- 观察点 / 失效条件（where applicable)

- [ ] **Step 6: Keep existing sections intact**

Do not remove or rename:
- `午盘/盘后操作建议摘要`
- `Dropped Candidates`
- `Diagnostic Scorecard`
- `Near Miss Candidates`

The expanded `Decision Factors` layer is additive.


### Task 3: Verify On Focused Samples

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\postclose-plan-review-all\result.json`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\postclose-plan-review-all\report.md`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\result.json`
- Modify: `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\report.md`

- [ ] **Step 1: Run wrapper regression**

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

- [ ] **Step 2: Re-run the three-name post-close review sample**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' `
  'D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py' `
  'D:\Users\rickylu\dev\financial-services-stock\.tmp\postclose-plan-review-all\request.json' `
  --output 'D:\Users\rickylu\dev\financial-services-stock\.tmp\postclose-plan-review-all\result.json' `
  --markdown-output 'D:\Users\rickylu\dev\financial-services-stock\.tmp\postclose-plan-review-all\report.md'
```

Expected:
- result completes successfully
- report contains richer `Decision Factors`
- current three-name sample still shows `不执行 / 继续观察` as appropriate

- [ ] **Step 3: Re-run the qualified sample postprocessor**

Run a small Python snippet that:
- loads `D:\Users\rickylu\dev\financial-services-plugins\.tmp\month-end-shortlist-live-baseline-2026-04-10.result.json`
- calls `enrich_live_result_reporting(...)`
- writes:
  - `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\result.json`
  - `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\report.md`

Expected:
- `可执行` section exists
- decision-factor cards are richer than the current one-line summary

- [ ] **Step 4: Commit**

```powershell
git add D:\Users\rickylu\dev\financial-services-stock\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py `
        D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_degraded_reporting.py `
        D:\Users\rickylu\dev\financial-services-stock\docs\superpowers\plans\2026-04-16-top10-and-expanded-decision-factors.md
git commit -m "feat: expand top10 reporting and decision factors"
```
