# Trading Profile Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current discovery report's `龙头 / 一线 / 二线` emphasis with the user-confirmed trading-profile buckets and surface that classification on event cards and chain-map output.

**Architecture:** Keep the compiled shortlist core unchanged. Add a wrapper-level trading-profile classifier in the discovery helper, then update report synthesis and markdown rendering to use the new buckets while keeping old peer/leader metadata as internal support.

**Tech Stack:** Python 3.12, wrapper modules under `financial-analysis/skills/month-end-shortlist/scripts`, pytest/unittest.

---

### Task 1: Add Trading Profile Classification With TDD

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\earnings_momentum_discovery.py`

- [ ] **Step 1: Write failing tests for trading-profile bucket assignment**
- [ ] **Step 2: Run the targeted test file and verify RED**
- [ ] **Step 3: Implement the minimal classifier and wire it into built event cards**
- [ ] **Step 4: Re-run the targeted test file and verify GREEN**

### Task 2: Rebuild Report Rendering Around Trading Profiles

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Write failing report tests that expect the new buckets and profile lines**
- [ ] **Step 2: Run the targeted report test file and verify RED**
- [ ] **Step 3: Implement chain-map aggregation and markdown rendering for the five trading-profile buckets**
- [ ] **Step 4: Re-run the targeted report test file and verify GREEN**

### Task 3: Run Focused Discovery/Reporting Regression

**Files:**
- Verify only:
  - `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_x_style_assisted_shortlist.py`
  - `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py`
  - `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_discovery_merge.py`
  - `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Run the focused regression slice**
- [ ] **Step 2: Confirm the new buckets appear and old report behavior is not otherwise broken**

### Task 4: Regenerate The Real-X Example

**Files:**
- Verify/update local artifact:
  - `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\.tmp\real-x-event-card-example\report.md`

- [ ] **Step 1: Re-run the existing real-X example flow**
- [ ] **Step 2: Verify the report now highlights trading-profile buckets instead of `一线 / 二线`**

