# Theme-Aware Base Launch Supplement Lane Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing `setup_launch_candidates` lane so it more reliably identifies true base-completion / early-launch setups while keeping the lane confined to `筑底启动补充` and preserving all current `T1/T2` execution discipline.

**Architecture:** Keep the existing lane shape, output contract, and report placement, but replace the current coarse setup heuristics with stronger four-part stage detection: structure repair, volume return, RS improvement, and bottom-state classification. Add small theme-weight hooks for `commercial_space`, `controlled_fusion`, `humanoid_robotics`, and `semiconductor_equipment`, but do not fork the algorithm into separate per-theme engines.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime, existing `setup_launch_candidates` lane, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - upgrade Phase 1 setup helpers into Phase 2 stage detectors
  - add richer setup details and theme-weight hooks
  - keep lane semantics and `T3/T4`-only behavior unchanged
- Modify: `tests/test_setup_launch_supplement_lane.py`
  - add focused tests for structure-repair quality, volume-window comparison, RS repair behavior, early extension, and theme weights
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - lock richer `筑底启动补充` explanations if new setup reasons/details become visible in markdown

### Responsibility Boundaries

- `setup_launch_candidates` remains a supplement lane only.
- No changes are allowed to:
  - `keep_threshold`
  - `strict_top_pick_threshold`
  - direct `T1/T2` promotion rules
- `market_strength_candidates` remains same-day strong-close oriented and is not refactored in this iteration.

---

## Task 1: Add Failing Tests for Phase 2 Detection Quality

**Files:**
- Modify: `tests/test_setup_launch_supplement_lane.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py` only if richer reporting changes are added

- [ ] **Step 1: Add a failing test for one-day rebound noise**

Create a row that:

- closes above `ma20` once
- has no real low-point improvement
- has weak recent participation

Expected:

- `classify_structure_repair(...)` should not return `high`
- the row should not qualify as a strong Phase 2 early-launch candidate

- [ ] **Step 2: Add a failing test for recent-vs-base volume reacceleration**

Use a row or helper input where:

- recent `3-5` session participation is clearly above the earlier quiet/base window
- same-day turnover alone is not the deciding factor

Expected:

- `classify_volume_return(...)` reflects true reacceleration

- [ ] **Step 3: Add a failing test for RS repair without elite absolute RS**

Use a row where:

- absolute `rs90` is only moderate
- but RS is improving across a short lookback

Expected:

- `classify_rs_improvement(...)` returns at least `medium`

- [ ] **Step 4: Add a failing test for `early_extension` vs `too_extended`**

Expected:

- `early_extension` is still allowed but scores lower than `off_bottom_not_extended`
- `too_extended` is excluded

- [ ] **Step 5: Add a failing test for theme weights not breaking the shared contract**

For each strategic theme, assert:

- weights can nudge the score
- but the row still emits the same outward contract:
  - `setup_launch_candidates`
  - `source = setup_launch_scan`
  - no direct `T1/T2`

- [ ] **Step 6: Run the focused Phase 2 tests and confirm failure before implementation**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- failures because the stronger Phase 2 detectors do not exist yet

---

## Task 2: Upgrade Structure Repair and Bottom-State Detection

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Add short-lookback structure helpers**

Add focused helpers that can evaluate:

- whether `ma20` is improving versus a recent lookback
- whether recent lows are stabilizing or rising

Keep them small and self-contained.

- [ ] **Step 2: Upgrade `classify_structure_repair(...)`**

Phase 2 should consider:

- `close > ma20`
- stronger: `close > ma50`
- `ma20` direction improvement
- low-point stabilization / improvement

- [ ] **Step 3: Upgrade `classify_distance_from_bottom_state(...)`**

Replace the current 3-state model with:

- `still_bottoming`
- `off_bottom_not_extended`
- `early_extension`
- `too_extended`

- [ ] **Step 4: Re-run the structure-focused tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -k "structure or extension or bottom" -v --tb=short
```

Expected:

- structure and bottom-state tests pass
- volume / RS tests may still fail

---

## Task 3: Upgrade Volume Return and RS Improvement Detection

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Add recent-vs-base volume comparison logic**

Implement a small helper that compares:

- recent participation window
- prior quiet/base window

Use whichever existing row fields are already available in the runtime. Do not add a brand-new heavy data dependency in this iteration.

- [ ] **Step 2: Upgrade `classify_volume_return(...)`**

Phase 2 should reward:

- clear reacceleration relative to the prior base

It should not depend only on same-day turnover.

- [ ] **Step 3: Add RS repair direction logic**

Implement a helper that evaluates whether RS is improving over a short lookback.

- [ ] **Step 4: Upgrade `classify_rs_improvement(...)`**

Phase 2 should support:

- moderate absolute RS + improving trend
- not just high absolute RS

- [ ] **Step 5: Re-run focused tests for volume and RS**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -k "volume or rs" -v --tb=short
```

Expected:

- PASS

---

## Task 4: Add Theme-Weight Hooks Without Forking the Algorithm

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add a small `SETUP_LAUNCH_THEME_WEIGHTS` configuration surface**

Phase 2 themes:

- `commercial_space`
- `controlled_fusion`
- `humanoid_robotics`
- `semiconductor_equipment`

- [ ] **Step 2: Apply theme weights only as scoring nudges**

Weights may slightly tilt:

- structure repair
- volume return
- RS improvement
- distance-state preference

Do not split the generator into four different algorithms.

- [ ] **Step 3: Keep defaults conservative**

If a theme is missing from the weight map:

- use neutral default behavior

- [ ] **Step 4: Run the focused theme-weight tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -k "theme" -v --tb=short
```

Expected:

- PASS

---

## Task 5: Improve Setup Reasons and Preserve Report Semantics

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py` if needed

- [ ] **Step 1: Replace generic reasons with more specific setup reasons**

Prefer outputs such as:

- `ma20_turning_up`
- `reclaimed_ma20_ma50`
- `higher_recent_lows`
- `volume_reacceleration`
- `rs_trend_repair`
- `off_bottom_not_extended`

- [ ] **Step 2: Keep the outward contract backward-compatible**

The lane should still expose:

- `setup_launch_candidates`
- `source = setup_launch_scan`
- `筑底启动补充`

Extra detail fields may be additive only.

- [ ] **Step 3: Keep report placement unchanged**

Do not move `筑底启动补充` above existing formal sections.

- [ ] **Step 4: Add a report regression if the richer reasons are rendered**

Lock that the report includes:

- `筑底启动补充`
- ticker/name
- at least one richer setup reason

without affecting:

- `市场强势补充`
- event-driven sections

---

## Task 6: Run Full Focused Regression for Phase 2

**Files:**
- No new files beyond the runtime/tests above

- [ ] **Step 1: Run the focused setup + reporting suite**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS

- [ ] **Step 2: Verify no formal-execution regression**

Check that no new Phase 2 behavior directly mutates:

- `T1`
- `T2`
- event-driven keep logic

Use existing assertions and add one targeted guard if needed.

---

## Spec Coverage Self-Review

- Spec requirement: improve the four existing setup dimensions rather than replacing the lane
  - Covered by Tasks 2 and 3.
- Spec requirement: add theme-weight hooks for the four strategic themes
  - Covered by Task 4.
- Spec requirement: keep the same outward contract and report placement
  - Covered by Task 5.
- Spec requirement: do not alter `T1/T2` behavior or main engine thresholds
  - Covered by Responsibility Boundaries and Task 6.

Placeholder scan result:

- No `TODO`, `TBD`, or unresolved references remain.

Type / naming consistency:

- `setup_launch_candidates`
- `setup_launch_scan`
- `SETUP_LAUNCH_THEME_WEIGHTS`
- `classify_structure_repair`
- `classify_volume_return`
- `classify_rs_improvement`
- `classify_distance_from_bottom_state`

These names are used consistently across the plan.
