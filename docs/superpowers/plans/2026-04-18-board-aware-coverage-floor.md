# Board-Aware Coverage Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect wrapper-side board-aware coverage expansion into the multi-track shortlist flow without relaxing T1 qualified picks.

**Architecture:** Keep compiled core unchanged. Extend `enrich_track_result()` so each track can merge catalyst-waived names into the observation pool and apply floor-policy supplementation before tier caps are rendered. Verify on focused screening tests and fresh multi-track report outputs.

**Tech Stack:** Python, pytest, month-end shortlist runtime wrapper.

---

### Task 1: Add failing regression for track-level coverage fill

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_screening_coverage_optimization.py`

- [ ] Add a regression test that calls `enrich_track_result()` with a sparse main-board track result and asserts:
  - catalyst-only failures can be tagged into the observation tier under an eligible profile
  - floor supplementation can mark names with `coverage_fill`
  - `tier_metadata["floor_policy_applied"]` becomes `True`

- [ ] Run only the new regression and confirm it fails for the right reason before implementation.

### Task 2: Wire track-level waiver and floor policy

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] In `enrich_track_result()`, merge eligible catalyst-waived candidates into track near-miss candidates before tier assignment.
- [ ] Apply wrapper-side floor supplementation after `assign_tiers()` and before `apply_rendered_caps()`.
- [ ] Keep compiled `keep=True` semantics unchanged so T1 remains strict.
- [ ] Preserve track metadata and tags so supplemented names are still visible as `coverage_fill` or `catalyst_waived`.

### Task 3: Focused verification and fresh report regeneration

**Files:**
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_screening_coverage_optimization.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_board_threshold_overrides.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_month_end_shortlist_profile_passthrough.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-board-aware-coverage-floor\tests\test_x_style_assisted_shortlist.py`

- [ ] Run the focused shortlist/board/discovery suite.
- [ ] Regenerate the fresh multi-track report and result JSON from `.tmp\next-session-2026-04-21\request.full.json`.
- [ ] Confirm the rendered plan still keeps T1 strict while expanding only observation tiers.
