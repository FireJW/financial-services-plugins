# Setup Launch Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `setup_launch_candidates` so the existing supplement lane more reliably distinguishes true early-launch setups from bottom drift and late extension while preserving `T1/T2` discipline.

**Architecture:** Keep the current `setup_launch_candidates` product boundary and output contract, but replace the light Phase 1 setup heuristics with better stage-discrimination helpers for structure repair, volume return, RS improvement, and distance-from-bottom state. Add a small theme-aware weighting layer for the four strategic base-watch themes, and keep the lane confined to `T3`, `T4`, and the `筑底启动补充` report section.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime, existing `setup_launch_candidates` lane, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - upgrade Phase 1 setup helpers into stronger stage-discrimination logic
  - add lightweight theme-aware weighting for the four strategic themes
  - preserve the current `setup_launch_candidates` contract and late-merge flow
- Modify: `tests/test_setup_launch_supplement_lane.py`
  - expand discrimination coverage for structure, volume, RS, and distance state
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - add or refine one regression that keeps `筑底启动补充` interpretable after richer reasons are added

### Responsibility Boundaries

- Do not change:
  - formal shortlist `keep_threshold`
  - `strict_top_pick_threshold`
  - `T1` / `T2` promotion rules
- Do not merge this logic into `market_strength_candidates`.
- Keep `setup_launch_candidates` as a distinct supplement lane.

---

## Task 1: Add Failing Discrimination Tests

**Files:**
- Modify: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add a failing test for structure-repair discrimination**

Create two rows:

- one is a one-day bounce above `ma20`
- one has recovered `ma20` and `ma50`, with better low-structure behavior

Expected:

- the recovered structure scores higher

- [ ] **Step 2: Add a failing test for repeated volume return versus one-day spike**

Create two rows:

- one only looks active because of a single turnover spike
- one shows repeated `3-5` day volume improvement behavior

Expected:

- the repeated reacceleration row scores higher

- [ ] **Step 3: Add a failing test for RS trend improvement**

Create rows where:

- one has moderate but improving RS behavior
- one has flat or deteriorating RS behavior

Expected:

- the improving RS row receives the better classification

- [ ] **Step 4: Add a failing test for early-extension handling**

Expected:

- `off_bottom_not_extended` remains valid
- `early_extension` is lower quality but still visible
- `too_extended` is excluded

- [ ] **Step 5: Run focused tests and confirm failure**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- failures because the current Phase 1 helper logic is too coarse

---

## Task 2: Upgrade the Four Setup Signals

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Upgrade `classify_structure_repair(...)`**

Add more layered logic using the existing row / snapshot shape.

Phase 2 should consider:

- `close > ma20`
- `close > ma50`
- `ma20` slope proxy
- recent low-structure stabilization proxy

Keep output:

- `low`
- `medium`
- `high`

- [ ] **Step 2: Upgrade `classify_volume_return(...)`**

Shift from single-point thresholding toward relative improvement.

Phase 2 should prefer:

- repeated participation
- short rolling-window improvement

and reduce false positives from:

- one-day spikes

- [ ] **Step 3: Upgrade `classify_rs_improvement(...)`**

Make the helper reflect trend improvement rather than mostly absolute RS proxies.

Phase 2 should reward:

- improving RS direction
- improving local relative performance

without requiring:

- very high absolute RS

- [ ] **Step 4: Upgrade `classify_distance_from_bottom_state(...)`**

Replace the coarse three-state logic with:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

- [ ] **Step 5: Re-run focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- signal-specific tests now pass

---

## Task 3: Add Lightweight Theme-Aware Weighting

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add a small theme-weight helper**

Recommended shape:

```python
def setup_launch_theme_weights(theme_name: str) -> dict[str, float]:
    ...
```

Phase 2 themes:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

- [ ] **Step 2: Apply weights inside `setup_launch_score(...)`**

Keep one shared algorithm.

Do not fork into separate per-theme engines.

Suggested behavior:

- `commercial_space`: slightly favor volume return and early separation
- `controlled_fusion`: slightly favor structure repair
- `humanoid_robotics`: slightly favor RS improvement
- `semiconductor_equipment`: slightly favor orderly structure repair

- [ ] **Step 3: Add a theme-weight sanity test**

Expected:

- the same base row can score slightly differently under different themes
- but eligibility behavior remains broadly shared

- [ ] **Step 4: Re-run focused setup-lane tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- PASS

---

## Task 4: Improve Setup Reasons and Reporting Readability

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Expand `setup_reasons` to explain signal upgrades**

Use reason strings such as:

- `ma20_turning_up`
- `reclaimed_ma50`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

- [ ] **Step 2: Keep the top-level contract stable**

Do not rename:

- `setup_launch_candidates`
- `structure_repair`
- `volume_return`
- `rs_improvement`
- `distance_from_bottom_state`
- `source`

- [ ] **Step 3: Add or refine one markdown regression**

Lock that `筑底启动补充` still renders:

- ticker / name
- reasons
- stage fields
- source

without getting confused with:

- `市场强势补充`

- [ ] **Step 4: Re-run focused reporting tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS

---

## Task 5: Final Focused Verification

**Files:**
- No new files beyond the ones above

- [ ] **Step 1: Run the final focused regression ladder**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS
- no regression in `market_strength_candidates`
- no regression in report separation

- [ ] **Step 2: Verify no tier pollution**

Re-check with tests and code inspection that Phase 2 still does not directly
promote setup-lane names into:

- `T1`
- `T2`

---

## Spec Coverage Self-Review

- Spec requirement: improve structure / volume / RS / distance signal quality
  - Covered by Task 2.
- Spec requirement: add lightweight theme-specific weighting for four themes
  - Covered by Task 3.
- Spec requirement: preserve lane boundary and output contract
  - Covered by Tasks 4 and 5.
- Spec requirement: no `T1/T2` promotion
  - Covered by Task 5.

Placeholder scan result:

- No `TODO`, `TBD`, or unresolved references remain.

Type / naming consistency:

- `setup_launch_candidates`
- `setup_launch_score`
- `classify_structure_repair`
- `classify_volume_return`
- `classify_rs_improvement`
- `classify_distance_from_bottom_state`

These names remain consistent across tasks.
