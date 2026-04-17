---
name: autoresearch-code-fix
description: Improve repeatable bug-fix workflows through strict reproduce-root-cause-fix-verify-rollback discipline. Use when the goal is not just to patch one bug, but to make code-fix work more reliable over time with clear hard checks, scoring, and rollback rules. Works with autoresearch-loop.
---

# Autoresearch Code Fix

Use this skill only for repeated code-fix workflows.

This skill is the task-specific layer for `autoresearch-loop`. It does not
manage the whole improvement system. It defines what "good" looks like for bug
fixing.

## When To Use

Use when:

- the same kind of bug-fix work happens repeatedly
- success can be verified with tests or repeatable checks
- the goal is to improve the repair process, not just finish one patch

Do not use when:

- the issue cannot be reproduced
- there is no practical validation path
- the task is mainly refactoring, feature work, or research

## Required Inputs

Before starting, collect:

- bug description
- reproduction steps
- logs or error output
- affected module or file boundary
- validation command or manual verification steps
- last known stable version for rollback

If any of these is missing, stop and mark the run as not ready.

## Core Rule

Never keep a fix that cannot be:

1. reproduced before the change
2. explained by a root cause
3. verified after the change
4. rolled back safely if it fails

## Workflow

### Step 1: Reproduce

Confirm the bug is real and repeatable.

Record:

- exact repro steps
- expected behavior
- actual behavior
- failing test or failing check if available

If the issue cannot be reproduced, do not continue the loop.

### Step 2: State Root Cause

Write a short root-cause statement before changing code.

Good root cause:

- explains why the system fails
- points to the actual trigger
- matches the observed behavior

Bad root cause:

- only repeats the symptom
- guesses without evidence
- describes a workaround instead of the break point

### Step 3: Make the Smallest Fix

Change as little as needed to address the root cause.

Prefer:

- narrow edits
- local fixes
- explicit regression protection

Avoid:

- broad cleanup during bug fixing
- unrelated refactors
- global behavior changes without proof they are needed

### Step 4: Verify

Run the strongest practical verification available.

Priority order:

1. targeted automated test
2. broader relevant regression checks
3. lint, type, or build checks for the touched area
4. repeatable manual verification if automation does not exist

A fix is not valid unless the original failure is gone and no new critical
failure appears.

### Step 5: Score

Use task-specific scoring only after hard checks pass.

Hard checks:

- bug was reproducible before the fix
- fix is verifiable after the change
- no new critical regression
- change matches the stated root cause
- change stays within allowed scope unless justified

Suggested score dimensions:

- root-cause quality
- fix minimality
- verification completeness
- regression risk control
- debugging efficiency
- reuse value of the final notes

Read:

- [references/scoring.md](references/scoring.md)
- [references/verification-checklist.md](references/verification-checklist.md)
- [references/run-report-template.md](references/run-report-template.md)

### Step 6: Keep Or Roll Back

Keep the candidate only if:

- all hard checks pass
- score improves enough versus baseline
- no new severe issue appears

Otherwise roll back to the last stable version.

### Step 7: Record The Result

For each run, record:

- bug id or task id
- reproduction status
- root cause statement
- files changed
- verification results
- score breakdown
- keep or rollback decision
- why the attempt won or lost

The helper script below can evaluate one run record:

- [scripts/evaluate_code_fix.py](scripts/evaluate_code_fix.py)
- [scripts/run_evaluate_code_fix.cmd](scripts/run_evaluate_code_fix.cmd)

For local use in this repo:

- [scripts/python-local.cmd](scripts/python-local.cmd) runs the D-drive Python
  runtime without needing system PATH changes
- [scripts/run_phase1_demo.cmd](scripts/run_phase1_demo.cmd) is the
  single-sample demo entry for the local phase 1 chain
- [scripts/run_phase1_batch_demo.cmd](scripts/run_phase1_batch_demo.cmd) is the
  full-sample demo entry for the local batch phase 1 chain
- [scripts/init_run_record.py](scripts/init_run_record.py) creates a starter run
  record from one bug sample in `sample-pool`
- [scripts/run_init_run_record.cmd](scripts/run_init_run_record.cmd) runs the
  run-record initializer through the local Python wrapper
- [scripts/init_all_run_records.py](scripts/init_all_run_records.py) creates
  starter run records for the full validated sample pool
- [scripts/run_init_all_run_records.cmd](scripts/run_init_all_run_records.cmd)
  runs the batch initializer through the local Python wrapper
- [scripts/run_evaluate_code_fix.cmd](scripts/run_evaluate_code_fix.cmd)
  evaluates one run record
- [scripts/run_evaluate_all_run_records.cmd](scripts/run_evaluate_all_run_records.cmd)
  evaluates a full run-record directory into a separate evaluated output
  directory
- [scripts/build_run_report.py](scripts/build_run_report.py) summarizes
  evaluated result JSON files into one Markdown run report
- [scripts/run_build_run_report.cmd](scripts/run_build_run_report.cmd) runs the
  batch report builder through the local Python wrapper
- [scripts/validate_sample_pool.py](scripts/validate_sample_pool.py) checks the
  sample-pool JSON files for phase 1 completeness
- [scripts/run_validate_sample_pool.cmd](scripts/run_validate_sample_pool.cmd)
  runs the sample-pool validator through the local Python wrapper

For phase 1 sample management:

- use [sample-pool/README.md](sample-pool/README.md) for pool rules
- use [sample-pool/sample-index.md](sample-pool/sample-index.md) to track the
  active bug set
- use [sample-pool/bugs/bug-template.json](sample-pool/bugs/bug-template.json)
  when creating new bug samples

Recommended local phase 1 flow in this repo:

1. run `scripts/run_phase1_demo.cmd` for a one-command single-sample walk
   through, or `scripts/run_phase1_batch_demo.cmd` for the full sample pool
2. otherwise choose one bug sample from `sample-pool/bugs`
3. for one bug, generate a starter run record from that sample
4. for a batch, use the batch initializer
5. fill in baseline and candidate scoring fields
6. evaluate one run record directly, or batch-evaluate a run-record directory
   into a dedicated evaluated output directory
7. use that evaluated output directory as the input set for
   `scripts/build_run_report.py`
8. rebuild the phase 1 run report

## Operating Constraints

- one meaningful change per iteration
- no "fix first, explain later"
- no "tests are flaky so assume pass"
- no bundling refactor work into bug-fix iterations
- no silent fallback when verification fails

## References

- [references/debug-loop.md](references/debug-loop.md)
- [references/scoring.md](references/scoring.md)
- [references/verification-checklist.md](references/verification-checklist.md)
- [references/run-report-template.md](references/run-report-template.md)
- [references/sample-pool-layout.md](references/sample-pool-layout.md)
