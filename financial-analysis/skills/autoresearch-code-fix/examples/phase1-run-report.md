# Phase 1 Run Report
Date: 2026-03-23
Profile: code-fix
Sample Set: code-fix-sample-v1
Baseline Version: baseline-v1
Candidate Version: candidate-v2
Owner: Codex
Goal: Improve repeatable handling of api input validation accepts malformed payload: A create endpoint accepts a malformed payload and returns success instead of rejecting the request with a validation error.

## Summary
- Total Runs: 1
- Keep: 0
- Rollback: 1
- Hard Check Failures: 1
- Avg Baseline Score: 0
- Avg Candidate Score: 0
- Avg Delta: 0
- First-Pass Success Rate:
  Baseline: 0%
  Candidate: 0%
- New Critical Regressions:
  Baseline: 0
  Candidate: 0

## Decision
- Overall Result: ROLLBACK
- Why:
  - Keep count: 0, rollback count: 1
  - Average score delta: 0
  - Hard-check failures: 1
- Next Action:
  - Return to the last stable baseline version
  - Fix hard-check discipline before attempting another iteration

## Run Table

| Run ID | Bug ID | Baseline | Candidate | Delta | Hard Checks | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|
| 001 | bug-001 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |

## Hard Check Failures
- bug-001: Issue was not reproducible before the fix
- bug-001: Fix was not verified after the change
- bug-001: New critical failure was introduced
- bug-001: Change scope exceeded the allowed boundary
- bug-001: Fix does not match the stated root cause

## Score Trends

### By Dimension

| Dimension | Avg Baseline | Avg Candidate | Delta | Note |
|---|---:|---:|---:|---|
| Debugging Efficiency | 0.00 | 0.00 | 0 |  |
| Fix Minimality | 0.00 | 0.00 | 0 |  |
| Regression Risk Control | 0.00 | 0.00 | 0 |  |
| Reuse Value | 0.00 | 0.00 | 0 |  |
| Root Cause Quality | 0.00 | 0.00 | 0 | Largest improvement |
| Verification Completeness | 0.00 | 0.00 | 0 |  |

## Winning Patterns
- None recorded yet

## Losing Patterns
- A broad fix could accidentally reject valid payload variants already used by clients

## Recommendation
- Keep using candidate? No
- If No:
  - Roll back to: baseline-v1
  - Fix hard-check discipline first

## Appendix
- Thresholds:
  - Min Improvement: 2
  - Large Regression: 5
- Stop Rule:
  - pause after 3 rounds with less than 2-point gain
- Notes:
  - this report covers only the phase 1 code-fix sample pool
