# Trading System Optimization Migration Design

Date: 2026-04-17

## Problem

PR #4 merged trading system optimization into an older `main` history.
GitHub `main` was later force-updated to a different root history.
The optimization code is now unreachable from current `main`.

## Strategy

Use `git checkout origin/feat/codex-plan-followup -- <path>` to extract
files from the old history line into a new feature branch based on
`origin/main`.

Branch: `feat/migrate-trading-optimization` (based on `origin/main`)

## Files to Migrate

### Core Scripts (5)

- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist.py`
- `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- `financial-analysis/skills/month-end-shortlist/scripts/macro_health_assisted_shortlist.py`
- `financial-analysis/skills/month-end-shortlist/scripts/x_style_assisted_shortlist.py`

### Templates / Examples (7)

All files under `financial-analysis/skills/month-end-shortlist/examples/`

### Tradingagents Supplement (1)

- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_package_support.py`

### Tests (9)

- `tests/test_earnings_momentum_discovery.py`
- `tests/test_month_end_shortlist_benchmark_fallback.py`
- `tests/test_month_end_shortlist_candidate_fetch_fallback.py`
- `tests/test_month_end_shortlist_candidate_snapshot_enrichment.py`
- `tests/test_month_end_shortlist_degraded_reporting.py`
- `tests/test_month_end_shortlist_discovery_merge.py`
- `tests/test_month_end_shortlist_profile_passthrough.py`
- `tests/test_month_end_shortlist_shim.py`
- `tests/test_tradingagents_package_support.py`

### Test Fixtures (6)

- `tests/fixtures/runtime-state/sample-session-input.json`
- `tests/fixtures/runtime-state/sample-user-intent-multilingual.md`
- `tests/fixtures/runtime-state/sample-user-intent.md`
- `tests/fixtures/runtime-state/sample-user-request-multilingual.txt`
- `tests/fixtures/runtime-state/sample-user-request.txt`
- `tests/fixtures/x_discovery_real/multi-source-batch.request.json`

### Quarantine Tests (3)

- `tests/quarantine-corrupted/README.md`
- `tests/quarantine-corrupted/test_month_end_shortlist_runtime.py`
- `tests/quarantine-corrupted/test_month_end_shortlist_runtime_1.py`
- `tests/quarantine-corrupted/test_tradingagents_pilot_matrix.py`

### Other (2)

- `financial-analysis/skills/macro-health-overlay/examples/macro-health-overlay-public-mix.request.template.json`
- `routing-index.md`

## Not Migrated

- `docs/superpowers/` notes and plans (process docs, not feature code)

## Dependencies

- `month_end_shortlist_runtime.py` loads a `.pyc` from
  `short-horizon-shortlist/scripts/__pycache__/` — this artifact lives
  on local disk only, not in Git. Preserved as-is.
- Runtime imports from `earnings_momentum_discovery` (co-located),
  `tradingagents-decision-bridge`, and `x-stock-picker-style` — both
  exist on new `main`.

## Verification

1. Run `pytest` after migration to confirm tests pass
2. Verify `.pyc` dependency path resolves correctly on disk
