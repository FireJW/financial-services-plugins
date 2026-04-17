# Decision Flow Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `## 决策流` summary layer that replaces `Event Board` and absorbs the actionable summary role of `Chain Map`, while keeping `Decision Factors` and `Event Cards` intact in phase 1.

**Architecture:** Keep all behavior changes in the wrapper/reporting layer. Build `decision_flow` cards from the already-enriched shortlist result (`decision_factors`, `event_cards`, `chain_map_entries`, `filter_summary`) inside `month_end_shortlist_runtime.py`, then render them into markdown as the new main summary section. Do not touch the compiled shortlist core. Do not change `Event Cards` format in this slice.

**Tech Stack:** Python 3.12, wrapper module `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`, pytest/unittest, Windows PowerShell.

---

## File Structure

### Files to modify

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
  - Add `decision_flow` data builders
  - Add trigger sentence helpers
  - Add markdown rendering for `## 决策流`
  - Remove `## Event Board` and standalone `## Chain Map` from markdown in phase 1
  - Keep `Decision Factors`, `直接可执行`, `重点观察`, `链条跟踪`, and `Event Cards`

- `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
  - Add/adjust reporting contract tests for `decision_flow`
  - Assert markdown section replacement behavior
  - Assert card ordering and trigger rendering

### Files to verify only

- `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\earnings_momentum_discovery.py`
  - Reuse existing:
    - `trading_profile_judgment`
    - `trading_profile_usage`
    - profile bucket/subtype/reason/playbook fields
  - Do **not** modify unless runtime-only implementation becomes unreasonably messy

- `D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\validate-yesterday-plan-midday-2026-04-17\request.json`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\validate-yesterday-plan-midday-2026-04-17\report.md`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\validate-yesterday-plan-midday-2026-04-17\result.json`
  - Re-run/regenerate after implementation as a user-facing smoke check

## Task 0: Create an Isolated Worktree

**Files:**
- Verify only: current repo state

- [ ] **Step 1: Create a fresh feature branch in a new worktree**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\financial-services-plugins-clean' -c safe.directory='D:/Users/rickylu/dev/financial-services-plugins-clean' worktree add 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' -b feat/decision-flow-restructure main
```

Expected:

- New worktree created successfully
- New branch `feat/decision-flow-restructure`

- [ ] **Step 2: Verify branch and cleanliness**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' -c safe.directory='D:/Users/rickylu/dev/.worktrees/financial-services-plugins-clean/feat-decision-flow-restructure' status --short --branch
```

Expected:

- `## feat/decision-flow-restructure`
- No tracked-file modifications

## Task 1: Add Failing Tests for `decision_flow` Data

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add a fixture helper that produces one near-miss event card and one blocked diagnostic candidate**

Add/extend a helper near the existing reporting tests so it returns an enriched result with:

```python
result = {
    "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
    "dropped": [
        {"ticker": "001309.SZ", "name": "德明利", "drop_reason": "no_structured_catalyst_within_window"},
        {"ticker": "002460.SZ", "name": "赣锋锂业", "drop_reason": "score_below_keep_threshold"},
    ],
    "top_picks": [],
    "report_markdown": "# Month-End Shortlist Report: 2026-04-30\n",
}
```

and `assessed_candidates` / `discovery_candidates` sufficient to produce:

- `001309.SZ` as blocked
- `002460.SZ` as near_miss with an event card

- [ ] **Step 2: Add a failing test for the new `decision_flow` JSON key**

Add:

```python
def test_enrich_live_result_reporting_adds_decision_flow_cards(self) -> None:
    enriched = self._build_enriched_for_decision_flow()

    self.assertIn("decision_flow", enriched)
    self.assertEqual([item["ticker"] for item in enriched["decision_flow"]], ["002460.SZ", "001309.SZ"])

    first = enriched["decision_flow"][0]
    self.assertEqual(first["action"], "继续观察")
    self.assertEqual(first["trading_profile_bucket"], "高弹性")
    self.assertIn("评分", first["conclusion"])
    self.assertIn("技术", first["watch_points"])
    self.assertIn("upgrade", first["triggers"])
    self.assertIn("operation_reminder", first)
```

- [ ] **Step 3: Run the targeted test and verify RED**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- FAIL because `decision_flow` does not exist yet

- [ ] **Step 4: Implement minimal runtime helpers for `decision_flow` data**

Add to `month_end_shortlist_runtime.py` the following new helpers:

```python
def build_upgrade_trigger(card: dict[str, Any], keep_threshold: float | None) -> str: ...
def build_downgrade_trigger(card: dict[str, Any]) -> str: ...
def build_event_risk_trigger(card: dict[str, Any]) -> str: ...
def build_decision_flow_card(
    factor: dict[str, Any],
    *,
    keep_threshold: float | None,
    event_card: dict[str, Any] | None,
    chain_entry: dict[str, Any] | None,
) -> dict[str, Any]: ...
def build_decision_flow(enriched: dict[str, Any]) -> list[dict[str, Any]]: ...
```

Implementation rules:

- Build cards from `decision_factors` as the base population
- Merge in matching `event_card` by `ticker` when present
- Use `trading_profile_bucket` from the event card when available
- Fallback title/profile values from `action` if an event card is missing
- Sort cards:
  - `qualified`
  - then `near_miss` by score descending
  - then `blocked`

- [ ] **Step 5: Re-run the targeted test and verify GREEN**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- PASS for the new `decision_flow` data test

- [ ] **Step 6: Commit**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' commit -m "feat: add decision flow data model"
```

## Task 2: Add Failing Tests for Markdown Restructure

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing markdown assertions for `## 决策流`**

Add:

```python
def test_report_renders_decision_flow_and_removes_event_board_and_chain_map(self) -> None:
    enriched = self._build_enriched_for_decision_flow()
    report = enriched["report_markdown"]

    self.assertIn("## 决策流", report)
    self.assertNotIn("## Event Board", report)
    self.assertNotIn("## Chain Map", report)
    self.assertIn("## Decision Factors", report)
    self.assertIn("## Event Cards", report)
```

- [ ] **Step 2: Add failing assertions for card line ordering**

Add:

```python
def test_decision_flow_card_has_conclusion_watchpoints_triggers_and_operation_reminder(self) -> None:
    enriched = self._build_enriched_for_decision_flow()
    report = enriched["report_markdown"]
    flow = report.split("## 决策流")[1].split("## ")[0]

    self.assertIn("### 002460.SZ | 继续观察 | 60.0分 | 高弹性", flow)
    self.assertIn("结论", flow)
    self.assertIn("盘中观察点", flow)
    self.assertIn("触发条件", flow)
    self.assertIn("操作提醒", flow)
```

- [ ] **Step 3: Run the targeted test file and verify RED**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- FAIL because `## 决策流` is not rendered yet

- [ ] **Step 4: Implement `build_decision_flow_markdown()` and wire it into `enrich_live_result_reporting()`**

Add:

```python
def build_decision_flow_markdown(decision_flow: list[dict[str, Any]]) -> list[str]:
    lines = ["", "## 决策流", ""]
    for item in decision_flow:
        lines.append(f"### {item['ticker']} | {item['action']} | {item['score']}分 | {item['trading_profile_bucket']}")
        lines.append("")
        lines.append(f"- 结论：{item['conclusion']}")
        lines.append(f"- 盘中观察点：")
        lines.append(f"  - 技术：{item['watch_points']['technical']}")
        lines.append(f"  - 事件：{item['watch_points']['event']}")
        lines.append(f"  - 链条：{item['watch_points']['chain']}")
        lines.append(f"- 触发条件：")
        lines.append(f"  - ↑ upgrade：{item['triggers']['upgrade']}")
        lines.append(f"  - ↓ downgrade：{item['triggers']['downgrade']}")
        if item['triggers'].get('event_risk'):
            lines.append(f"  - ⚡ event risk：{item['triggers']['event_risk']}")
        lines.append(f"- 操作提醒：{item['operation_reminder']}")
        lines.append("")
    return lines
```

Wire it so that:

- `decision_flow = build_decision_flow(enriched)` runs after `decision_factors`
- markdown rendering:
  - keeps `Decision Factors`
  - removes `Event Board`
  - removes standalone `Chain Map`
  - inserts `## 决策流` before `## Event Cards`

- [ ] **Step 5: Re-run the targeted file and verify GREEN**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- PASS for the new markdown layout tests

- [ ] **Step 6: Commit**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' commit -m "feat: render decision flow summary section"
```

## Task 3: Add Trigger Template Coverage

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add a failing test for upgrade/downgrade/event-risk trigger strings**

Add:

```python
def test_decision_flow_triggers_include_upgrade_downgrade_and_event_risk_when_available(self) -> None:
    enriched = self._build_enriched_for_decision_flow()
    card = enriched["decision_flow"][0]

    self.assertIn("评分从 60.0 修复至 70.0+", card["triggers"]["upgrade"])
    self.assertTrue(card["triggers"]["downgrade"])
    self.assertIn("实际净利润低于预告下限", card["triggers"]["event_risk"])
```

- [ ] **Step 2: Run the targeted file and verify RED**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- FAIL because trigger text is still incomplete or absent

- [ ] **Step 3: Implement minimal trigger sentence builders**

Implement rules:

- `build_upgrade_trigger(...)`
  - always mention score, keep line, and the most relevant next driver
- `build_downgrade_trigger(...)`
  - use `hard_filter_failures` if present
  - otherwise derive a fragile condition from current trend context
- `build_event_risk_trigger(...)`
  - use `key_evidence` lines when they contain explicit guided numbers / thresholds
  - else return empty string

- [ ] **Step 4: Re-run the targeted file and verify GREEN**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- PASS for trigger tests

- [ ] **Step 5: Commit**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' commit -m "feat: add decision flow trigger templates"
```

## Task 4: Run Focused Regression And Regenerate Midday Validation Example

**Files:**
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_x_style_assisted_shortlist.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\.tmp\validate-yesterday-plan-midday-2026-04-17\request.json`

- [ ] **Step 1: Run the focused regression slice**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_x_style_assisted_shortlist.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_earnings_momentum_discovery.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_discovery_merge.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected:

- All targeted tests pass

- [ ] **Step 2: Regenerate the midday validation artifact**

Run:

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312-full\python.exe' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\.tmp\validate-yesterday-plan-midday-2026-04-17\request.json' `
  --output 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\.tmp\validate-yesterday-plan-midday-2026-04-17\result.json' `
  --markdown-output 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure\.tmp\validate-yesterday-plan-midday-2026-04-17\report.md'
```

Expected:

- Report contains `## 决策流`
- Report does not contain `## Event Board`
- Report does not contain standalone `## Chain Map`
- Report still contains `## Decision Factors`
- Existing midday actions remain:
  - `001309.SZ -> 不执行`
  - `002460.SZ -> 继续观察`
  - `002709.SZ -> 继续观察`

- [ ] **Step 3: Commit**

Run:

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_month_end_shortlist_degraded_reporting.py
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-decision-flow-restructure' commit -m "test: verify decision flow output on midday validation sample"
```

## Self-Review

- Spec coverage:
  - goal of adding `## 决策流`: covered by Task 2
  - new `decision_flow` JSON key: covered by Task 1
  - trigger generation: covered by Task 3
  - phase-1 markdown scope (`Decision Factors` kept, `Event Board` replaced, `Chain Map` folded): covered by Task 2 and Task 4
- Placeholder scan:
  - no `TODO` / `TBD`
  - all tasks point to exact files and exact commands
- Boundary check:
  - runtime is the main implementation file
  - helper changes are intentionally avoided in the base plan unless runtime-only implementation becomes messy

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-decision-flow-restructure-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
