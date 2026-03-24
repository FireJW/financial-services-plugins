# Examples Directory

This folder contains small example files for the phase 1 `autoresearch-code-fix`
workflow.

Use it to understand the end-to-end path:

1. start from a bug sample
2. create a run record
3. evaluate the run record
4. collect multiple results into one report
5. repeat the same flow across the full sample pool

## File Types

### `pass-case.json`

A hand-written example input for the scoring script.

Use this when you want to see what a candidate looks like when it should be
kept.

### `rollback-case.json`

A hand-written example input for the scoring script.

Use this when you want to see what a candidate looks like when it should be
rolled back.

### `pass-result.json`

The real scoring output produced from `pass-case.json`.

This shows the expected result shape when a candidate passes hard checks and is
kept.

### `rollback-result.json`

The real scoring output produced from `rollback-case.json`.

This shows the expected result shape when a candidate fails hard checks and is
rolled back.

### `run-record-template.json`

A blank starter template for a run record.

Use this when you want to create a new run record manually without starting
from a bug sample file.

### `bug-001-run-record.json`

A generated run record created from one bug sample in `sample-pool/bugs/`.

This is the bridge between a bug sample and the scoring workflow.

### `bug-001-evaluated.json`

The scoring output produced from `bug-001-run-record.json`.

This shows what happens when a generated starter run record is evaluated before
real execution data has been filled in. It defaults to a conservative rollback
result.

### `phase1-run-report.md`

A Markdown summary built from multiple result JSON files.

Use this when you want a human-readable view of keep vs. rollback outcomes
across a batch of runs.

### `batch-run-records/`

A generated directory of starter run records for the full phase 1 sample pool.

Use this when you want to batch-score every fixed bug sample without creating
each run record by hand.

### `batch-evaluated/`

A generated directory of evaluated outputs built from `batch-run-records/`.

Use this when you want a clean input directory for report generation that only
contains evaluated results plus the batch summary JSON.

### `phase1-batch-run-report.md`

A Markdown summary built from the full `batch-evaluated/` directory.

This is the current full-sample report for the validated phase 1 bug set.

## Recommended Reading Order

If you are new to this folder, read files in this order:

1. `run-record-template.json`
2. `pass-case.json`
3. `pass-result.json`
4. `rollback-case.json`
5. `rollback-result.json`
6. `bug-001-run-record.json`
7. `bug-001-evaluated.json`
8. `phase1-run-report.md`
9. `batch-run-records/`
10. `batch-evaluated/`
11. `phase1-batch-run-report.md`

## Notes

- `sample-pool/` is separate from this folder. It contains the fixed bug sample
  set used to generate run records.
- Files ending in `-result.json` or `-evaluated.json` are outputs, not inputs.
- The examples here are intentionally small and only meant to demonstrate the
  workflow shape for phase 1.
