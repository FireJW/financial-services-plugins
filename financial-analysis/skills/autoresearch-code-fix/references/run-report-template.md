# Phase 1 Run Report Template

Use this report after a small batch of code-fix runs. Keep it simple enough for
manual review.

```md
# Phase 1 Run Report
Date: YYYY-MM-DD
Profile: code-fix
Sample Set: code-fix-sample-v1
Baseline Version: baseline-v1
Candidate Version: candidate-v2
Owner: Codex
Goal: Improve repeatable bug-fix reliability while reducing regressions

## Summary
- Total Runs: 12
- Keep: 7
- Rollback: 5
- Hard Check Failures: 3
- Avg Baseline Score: 61
- Avg Candidate Score: 69
- Avg Delta: +8
- First-Pass Success Rate:
  Baseline: 42%
  Candidate: 67%
- New Critical Regressions:
  Baseline: 0
  Candidate: 1

## Decision
- Overall Result: KEEP | ROLLBACK | MIXED
- Why:
  - state whether the candidate beat baseline overall
  - state the main gain
  - state the main risk
- Next Action:
  - what to keep iterating
  - what to pause
  - whether to fall back to the last stable version

## Run Table

| Run ID | Bug ID | Baseline | Candidate | Delta | Hard Checks | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|
| 001 | bug-101 | 53 | 78 | +25 | Pass | Keep | Better verification with still-controlled scope |
| 002 | bug-102 | 78 | 83 | +5 | Fail | Rollback | Post-fix verification did not hold |

## Hard Check Failures
- bug-102: post-fix verification failed
- bug-107: change exceeded scope boundary
- bug-111: new critical regression introduced

## Score Trends

### By Dimension
| Dimension | Avg Baseline | Avg Candidate | Delta | Note |
|---|---:|---:|---:|---|
| Root Cause Quality | 15 | 19 | +4 | Root-cause statements became more precise |
| Fix Minimality | 14 | 15 | +1 | Slightly tighter edits |
| Verification Completeness | 11 | 17 | +6 | Largest improvement |
| Regression Risk Control | 9 | 11 | +2 | Better, but not yet stable |
| Debugging Efficiency | 6 | 5 | -1 | Still some blind edits |
| Reuse Value | 6 | 8 | +2 | Notes became more reusable |

## Winning Patterns
- state the 2-3 patterns that appear most often in kept runs

## Losing Patterns
- state the 2-3 patterns that appear most often in rolled-back runs

## Recommendation
- Keep using candidate? Yes | No
- If Yes:
  - name the next dimension to improve
- If No:
  - state rollback target
  - state what discipline to fix first

## Appendix
- Thresholds:
  - Min Improvement: 2
  - Large Regression: 5
- Stop Rule:
  - pause after 3 rounds with less than 2-point gain
- Notes:
  - this report covers only the phase 1 code-fix sample pool
```

## Minimum Sections

If you need a shorter report, keep at least:

1. Summary
2. Decision
3. Run Table
4. Winning Patterns and Losing Patterns
5. Recommendation
