# Next Implementation Slice For Claude

## Recommended next slice

The highest-value next slice is no longer "add trading-profile buckets."

That part is already implemented locally.

The highest-value next slice now is:

1. inspect and preserve the current local trading-profile/reporting work
2. fix the real-X example regeneration path
3. regenerate fresh artifacts
4. then keep tightening editorial synthesis

## What already exists locally

Before writing code, confirm the local tree already contains:

- `trading_profile_bucket`
- `trading_profile_subtype`
- `trading_profile_reason`
- `trading_profile_playbook`
- `trading_profile_judgment`
- `trading_profile_usage`
- `chain_playbook`

Likely files:

- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

## Concrete immediate task

### Step 1: Fix the real-X example rerun path

Current failure to reproduce:

- `ValueError: could not convert string to float: '-'`

Observed when rerunning:

- `.tmp/real-x-event-card-example/normalized-request.json`

through:

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist.py`

Likely interpretation:

- one stale/sample request value still reaches compiled shortlist parsing as a
  numeric field
- the example payload needs cleanup or wrapper-level guarding before artifact
  regeneration can succeed

### Step 2: Regenerate artifacts once the rerun works

Target outputs:

- `.tmp/real-x-event-card-example/report.md`
- `.tmp/real-x-event-card-example/result.json`

Goal:

- make the artifacts reflect current local source/tests
- verify that `判断 / 用法` actually appear in the fresh report

### Step 3: Only then continue synthesis polish

After artifact regeneration, keep improving:

- Event Board brevity
- Event Cards scanability
- chain expansion quality
- same-industry / same-subsector peer quality

## Tests to run first

Most relevant tests:

- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`
- `tests/test_x_style_assisted_shortlist.py`
- `tests/test_month_end_shortlist_discovery_merge.py`

Current known local regression state:

- focused discovery/reporting slice: `47 passed`

## If only one concrete task is executed

Do this one:

- fix the stale real-X example rerun path and regenerate the example artifacts

That is the fastest way to make Claude's later judgment about report quality
line up with the actual latest code.
