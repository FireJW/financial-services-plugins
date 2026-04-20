# Setup Launch Phase 2 Quality Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `setup_launch_candidates` so the lane can more reliably distinguish true early-launch setups from weak bottom drift and already-extended strength while keeping `T1/T2` execution rules unchanged.

**Architecture:** Keep the existing `setup_launch_candidates` lane shape, but upgrade the helper logic behind structure repair, volume return, RS improvement, distance-from-bottom classification, and setup reasons. Add a light theme-weight surface for the strategic setup themes, keep the lane under `筑底启动补充`, and preserve existing `event-driven` and `market_strength` behavior.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - upgrade setup helper logic
  - add light theme-weight configuration
  - refine scoring and setup reasons
- Modify: `tests/test_setup_launch_supplement_lane.py`
  - add focused tests for refined structure, volume, RS, and distance-state behavior
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - lock richer `筑底启动补充` reason rendering if the explanation surface changes

### Responsibility Boundaries

- `setup_launch_candidates` remains a supplement lane only.
- `event_discovery_candidates` and `market_strength_candidates` stay semantically unchanged.
- No `T1` / `T2` promotion change is allowed.
- No historical optimization, ML, or backtest-driven ranking belongs in this phase.

---

## Task 1: Add Failing Tests for the Phase 2 Setup Classifiers

**Files:**
- Modify: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add a failing structure-repair test**

Cover at least two cases:

- one-day reclaim with weak follow-through
- stronger sustained repair with `ma20` rising and both `ma20` / `ma50` reclaimed

Expected:

- stronger repair scores above the weak reclaim

- [ ] **Step 2: Add a failing volume-return test**

Create cases where:

- one row has one noisy high-turnover day only
- one row has recent average participation clearly above a prior quiet window

Expected:

- true re-accumulation is classified stronger than the one-day spike

- [ ] **Step 3: Add a failing RS-improvement test**

Create cases where:

- RS absolute level is only moderate but improving
- RS is flat or fading

Expected:

- improving RS classifies higher than flat/fading RS

- [ ] **Step 4: Add a failing distance-state test**

Cover all four target states:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

Expected:

- the helper emits the correct refined label

- [ ] **Step 5: Run the focused setup-lane tests and confirm failure**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- failures because the refined Phase 2 setup logic does not exist yet

---

## Task 2: Upgrade Structure and Volume Logic

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Refine `classify_structure_repair(...)`**

Add logic that distinguishes:

- weak one-day reclaim
- sustained reclaim
- rising short moving-average behavior
- improving recent low structure

Do not add a full pattern library.

- [ ] **Step 2: Refine `classify_volume_return(...)`**

Replace purely static thresholds with simple relative-window logic.

Phase 2 should compare:

- recent `3-5` session participation
- versus a prior quiet window

- [ ] **Step 3: Keep the helpers explainable**

Do not hide multiple judgments inside one opaque score.

The helper outputs should still be interpretable as:

- `high`
- `medium`
- `low`

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- structure and volume tests now pass
- RS / distance-state tests may still fail

---

## Task 3: Upgrade RS Improvement and Distance-State Logic

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Refine `classify_rs_improvement(...)`**

Shift judgment from mostly absolute value to trend improvement.

Examples of acceptable implementation inputs:

- current RS versus recent RS baseline
- recent RS direction
- no-longer-deteriorating behavior

- [ ] **Step 2: Expand `classify_distance_from_bottom_state(...)`**

Upgrade the helper to emit:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

- [ ] **Step 3: Update exclusion / score logic accordingly**

Ensure:

- `too_extended` remains excluded
- `off_bottom_not_extended` remains ideal
- `early_extension` is lower quality but not automatically the same as `too_extended`

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- PASS for refined structure / volume / RS / distance-state behavior

---

## Task 4: Add Light Theme-Aware Weighting

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add `SETUP_LAUNCH_THEME_WEIGHTS`**

Create a small configuration surface for:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

Each theme may slightly adjust the relative weight of:

- structure repair
- volume return
- RS improvement
- distance state

- [ ] **Step 2: Keep one shared algorithm**

Do not branch into separate theme-specific scoring functions.

Theme weighting must remain a light modifier only.

- [ ] **Step 3: Add a focused test for weighting**

Lock that:

- the same raw setup can score differently by theme weight
- but the lane contract remains unchanged

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- PASS

---

## Task 5: Upgrade Setup Reasons and Reporting Output

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Replace generic setup reasons with richer reasons**

Move from generic values such as:

- `structure_repair_visible`
- `volume_return_visible`
- `rs_trend_improving`

to more specific reason labels such as:

- `ma20_reclaimed`
- `ma50_reclaimed`
- `ma20_turning_up`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

- [ ] **Step 2: Keep `筑底启动补充` as the same report section**

Do not move this lane or merge it into:

- `市场强势补充`
- `直接可执行`

- [ ] **Step 3: Add a report regression**

Verify the markdown now exposes richer setup reasons while preserving:

- section title `筑底启动补充`
- separation from `市场强势补充`

- [ ] **Step 4: Run the reporting-focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS

---

## Task 6: Run the Full Focused Phase 2 Regression Ladder

**Files:**
- No new files beyond the runtime and test files above

- [ ] **Step 1: Run the full focused regression set**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS
- no regression in `market_strength_candidates`
- no regression in report layering
- no change to `T1/T2` semantics

- [ ] **Step 2: Commit**

Use a commit message such as:

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_setup_launch_supplement_lane.py tests/test_month_end_shortlist_degraded_reporting.py
git commit -m "feat: improve setup launch scoring quality"
```

---

## Spec Coverage Self-Review

- Spec requirement: improve structure-repair quality
  - Covered by Task 2.
- Spec requirement: improve volume-return quality
  - Covered by Task 2.
- Spec requirement: improve RS trend judgment
  - Covered by Task 3.
- Spec requirement: refine bottom-distance states
  - Covered by Task 3.
- Spec requirement: add light theme-aware weights only
  - Covered by Task 4.
- Spec requirement: richer `筑底启动补充` explanations
  - Covered by Task 5.
- Spec requirement: no `T1/T2` promotion changes
  - Covered by Tasks 5 and 6 regression expectations.

Placeholder scan result:

- no `TODO`
- no `TBD`
- no vague “handle later” steps

Type / naming consistency:

- `setup_launch_candidates`
- `SETUP_LAUNCH_THEME_WEIGHTS`
- `classify_structure_repair`
- `classify_volume_return`
- `classify_rs_improvement`
- `classify_distance_from_bottom_state`

These names are used consistently across the plan.
