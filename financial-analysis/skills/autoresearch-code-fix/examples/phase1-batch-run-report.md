# Phase 1 Run Report
Date: 2026-03-23
Profile: code-fix
Sample Set: code-fix-sample-v1
Baseline Version: baseline-v1
Candidate Version: candidate-v2
Owner: Codex
Goal: Batch review across 10 distinct code-fix tasks

## Summary
- Total Runs: 10
- Keep: 0
- Rollback: 10
- Hard Check Failures: 10
- Avg Baseline Score: 0
- Avg Candidate Score: 0
- Avg Delta: 0
- First-Pass Success Rate:
  Baseline: 0%
  Candidate: 0%
- New Critical Regressions:
  Baseline: 0
  Candidate: 0

## Task Mix
- bug-001: api input validation accepts malformed payload
- bug-002: report export drops a required section when one field is empty
- bug-003: search results stay stale after filter reset
- bug-004: bulk upload accepts duplicate external ids in the same batch
- bug-005: submit button stays disabled after fixing a form validation error
- bug-006: notification retry marks delivery successful after provider timeout
- bug-007: csv import silently duplicates rows on retry
- bug-008: notification badge does not clear after inbox is read
- bug-009: scheduled job skips records created near midnight boundary
- bug-010: access-control check allows archived record read to wrong role

## Decision
- Overall Result: ROLLBACK
- Why:
  - Keep count: 0, rollback count: 10
  - Average score delta: 0
  - Hard-check failures: 10
- Next Action:
  - Return to the last stable baseline version
  - Fix hard-check discipline before attempting another iteration

## Run Table

| Run ID | Bug ID | Baseline | Candidate | Delta | Hard Checks | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|
| 001 | bug-001 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 002 | bug-002 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 003 | bug-003 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 004 | bug-004 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 005 | bug-005 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 006 | bug-006 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 007 | bug-007 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 008 | bug-008 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 009 | bug-009 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |
| 010 | bug-010 | 0 | 0 | 0 | Fail | Rollback | Rollback because one or more hard checks failed |

## Hard Check Failures
- bug-001: Issue was not reproducible before the fix
- bug-001: Fix was not verified after the change
- bug-001: New critical failure was introduced
- bug-001: Change scope exceeded the allowed boundary
- bug-001: Fix does not match the stated root cause
- bug-002: Issue was not reproducible before the fix
- bug-002: Fix was not verified after the change
- bug-002: New critical failure was introduced
- bug-002: Change scope exceeded the allowed boundary
- bug-002: Fix does not match the stated root cause
- bug-003: Issue was not reproducible before the fix
- bug-003: Fix was not verified after the change
- bug-003: New critical failure was introduced
- bug-003: Change scope exceeded the allowed boundary
- bug-003: Fix does not match the stated root cause
- bug-004: Issue was not reproducible before the fix
- bug-004: Fix was not verified after the change
- bug-004: New critical failure was introduced
- bug-004: Change scope exceeded the allowed boundary
- bug-004: Fix does not match the stated root cause
- bug-005: Issue was not reproducible before the fix
- bug-005: Fix was not verified after the change
- bug-005: New critical failure was introduced
- bug-005: Change scope exceeded the allowed boundary
- bug-005: Fix does not match the stated root cause
- bug-006: Issue was not reproducible before the fix
- bug-006: Fix was not verified after the change
- bug-006: New critical failure was introduced
- bug-006: Change scope exceeded the allowed boundary
- bug-006: Fix does not match the stated root cause
- bug-007: Issue was not reproducible before the fix
- bug-007: Fix was not verified after the change
- bug-007: New critical failure was introduced
- bug-007: Change scope exceeded the allowed boundary
- bug-007: Fix does not match the stated root cause
- bug-008: Issue was not reproducible before the fix
- bug-008: Fix was not verified after the change
- bug-008: New critical failure was introduced
- bug-008: Change scope exceeded the allowed boundary
- bug-008: Fix does not match the stated root cause
- bug-009: Issue was not reproducible before the fix
- bug-009: Fix was not verified after the change
- bug-009: New critical failure was introduced
- bug-009: Change scope exceeded the allowed boundary
- bug-009: Fix does not match the stated root cause
- bug-010: Issue was not reproducible before the fix
- bug-010: Fix was not verified after the change
- bug-010: New critical failure was introduced
- bug-010: Change scope exceeded the allowed boundary
- bug-010: Fix does not match the stated root cause

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
- A naive fallback could duplicate the section or alter report ordering
- A broad reset fix could break pagination, default sorting, or optimistic UI behavior

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
