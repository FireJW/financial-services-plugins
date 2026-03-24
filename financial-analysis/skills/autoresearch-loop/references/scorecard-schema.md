# Shared Scorecard Schema

Use this schema for every autoresearch loop run.

The purpose is consistency, not forced uniformity. Every profile should use the
same top-level shape, while keeping task-specific checks inside its own section.

## Required Fields

```yaml
profile: code-fix | doc-workflow | stock-template | info-index
sample_set_version: string
task_goal: string
baseline_version: string
candidate_version: string
hard_checks:
  passed: true | false
  failures:
    - string
soft_scores:
  total: number
  dimensions:
    - name: string
      score: number
      weight: number
decision:
  keep: true | false
  rollback_to: string
  reason: string
stop_signal:
  reached: true | false
  reason: string
notes:
  winner_pattern: string
  loser_pattern: string
```

## Decision Rule

Keep a candidate only if all are true:

1. `hard_checks.passed = true`
2. no new severe failure was introduced
3. `soft_scores.total` improves by the agreed threshold

Otherwise:

- reject the candidate
- roll back to the last stable version
- record the failure reason

## Threshold Guidance

Use simple thresholds at first.

- minimum meaningful gain: 2 points on a 100-point scale
- large regression: 5 points or more
- stop after 3 rounds of less than 2-point gain

Adjust only after enough runs exist to justify a change.

## Profile Notes

### `code-fix`

Hard checks usually include:

- issue can be reproduced before the fix
- related validation passes after the fix
- no new critical regression is introduced
- fix matches the root cause

### `doc-workflow`

Hard checks usually include:

- no key information was lost
- structure remains complete
- terminology and versioning are consistent
- no major contradiction is introduced

### `stock-template`

Hard checks usually include:

- all relative time references are anchored to absolute dates
- key facts are traceable to sources
- required sections are present
- valuation method matches company type and data period

### `info-index`

Hard checks usually include:

- all relative time references are anchored to absolute dates
- key claims are traceable to specific sources
- fact and judgment are clearly separated
- contradictory or missing confirmations are disclosed
- source recency is checked before the conclusion is written

## Logging Rule

Every run must record both:

- the score outcome
- the explanation for why the version won or lost

Do not store only totals. The dimension-level score movement is part of the
learning signal.
