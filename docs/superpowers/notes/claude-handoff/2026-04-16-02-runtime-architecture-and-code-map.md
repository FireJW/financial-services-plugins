# Runtime Architecture And Code Map

## Canonical repo context

Work only in:

- `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup`

Do not use:

- `D:\Users\rickylu\dev\financial-services-stock` as the main git target
- `D:\Users\rickylu\dev\financial-services-plugins` for active development

## Main runtime entry points

### 1. Shortlist wrapper runtime

Primary file:

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

This is the main orchestration layer. It handles:

- request normalization
- wrapper profile overrides
- X/discovery input fusion
- compiled shortlist invocation
- report enrichment and markdown synthesis

It is still the safest main extension point.

### 2. Discovery helper

Primary file:

- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`

This is where wrapper-level discovery logic lives. It currently handles:

- discovery-candidate normalization
- rumor confidence
- market validation
- event state
- trading usability
- discovery bucket assignment
- auto-derived discovery candidates
- X-style candidate extraction
- multi-source event-card synthesis
- trading-profile classification
- trading-profile playbook generation
- compact `判断 / 用法` generation

If you are changing event-card logic, grouping logic, playbook logic, or
report-facing classification, this is one of the main files to edit.

### 3. X-assisted wrapper

Related file:

- `financial-analysis/skills/month-end-shortlist/scripts/x_style_assisted_shortlist.py`

Useful when tracing:

- `x_style_batch_result_path`
- inline `x_discovery_request`
- file-based `x_discovery_request_path`
- subject registry logic basket processing

## Current local reporting surface

The wrapper can already render:

- `## 午盘/盘后操作建议摘要`
- `## Decision Factors`
- `## 直接可执行`
- `## 重点观察`
- `## 链条跟踪`
- `## Event Board`
- `## Chain Map`
- `## Event Cards`

Current local-only reporting direction already implemented in source/tests:

- buckets:
  - `稳健核心`
  - `高弹性`
  - `补涨候选`
  - `预期差最大`
  - `兑现风险最高`
- per-card support:
  - `trading_profile_subtype`
  - `trading_profile_playbook`
  - `trading_profile_judgment`
  - `trading_profile_usage`
- per-chain support:
  - `chain_playbook`

Meaning:

- `Event Board / Event Cards` should be read as judgment-first surfaces
- `Chain Map` should be read as chain-level tactic summary + grouped names

## Tests that matter most

If you change this subsystem, the most relevant tests are:

- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`
- `tests/test_month_end_shortlist_discovery_merge.py`
- `tests/test_x_style_assisted_shortlist.py`

## Current local diffs that Claude should inspect first

The latest local work is concentrated in:

- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`

Those files are ahead of the last pushed commit.

## Current safe boundary

Do not rewrite the compiled shortlist core unless there is no alternative.

Safe extension boundary:

- wrapper/orchestration layer
- helper logic
- report rendering
- request normalization
- input fusion

In practice:

- prefer edits in `month_end_shortlist_runtime.py`
- prefer edits in `earnings_momentum_discovery.py`
- add or adjust wrapper-level tests first

## Current verification state

Fresh local focused regression:

- discovery/reporting slice: `47 passed`

Relevant verification command family:

- `tests/test_x_style_assisted_shortlist.py`
- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_discovery_merge.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`
