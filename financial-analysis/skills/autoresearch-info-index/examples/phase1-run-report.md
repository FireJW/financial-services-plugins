# Phase 1 Run Report
Date: 2026-03-23
Profile: info-index
Sample Set: info-index-sample-v1
Baseline Version: baseline-v1
Candidate Version: candidate-v2
Owner: Codex
Goal: Trump said the war was moving toward a ceasefire after productive conversations. How reliable is that claim right now?

## Summary
- Total Runs: 1
- Keep: 0
- Rollback: 1
- Runs With Hard Check Failures: 1
- Hard Check Failure Messages: 5
- Avg Baseline Score: 0
- Avg Candidate Score: 0
- Avg Delta: 0
- Avg Evidence Confidence Score: 78
- Avg Source Strength: 78
- Avg Agreement Score: 87
- Avg Evidence Band: 58-98
- Avg Evidence Band Width: 40
- Confidence Labels: usable-high=0, usable-medium=0, usable-low=0, blocked=1
- Confidence Gates: usable=0, blocked=1

- Benchmark Confidence Band Hits: 0/1
- Full Benchmark Alignment Hits: 0/1

## Decision
- Overall Result: ROLLBACK
- Why:
  - Keep count: 0, rollback count: 1
  - Average score delta: 0
  - Runs with hard-check failures: 1
  - Average evidence confidence score: 78
- Next Action:
  - Return to the last stable baseline version
  - Fix hard-check discipline before trusting the evidence-confidence metrics

## Run Table

| Run ID | Item ID | Candidate | Delta | Evidence | Band | Gate | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|---|
| 001 | news-001 | 0 | 0 | 78 | 58-98 | blocked_by_hard_checks | Rollback | Rollback because one or more hard checks failed |

## Hard Check Failures
- news-001: Relative timing was not anchored to absolute dates
- news-001: Key claims are not traceable to specific sources
- news-001: Facts and inference are mixed together
- news-001: Conflicting or missing confirmations were not disclosed
- news-001: Source recency was not checked before writing the conclusion

## Evidence Snapshot

| Metric | Average |
|---|---:|
| Source Strength | 78.00 |
| Claim Confirmation | 53.00 |
| Timeliness | 100.00 |
| Agreement | 87.00 |
| Evidence Confidence Score | 78.00 |
| Evidence Band Width | 40.00 |

## Benchmark Alignment

| Item ID | Target Band | Actual Score | In Band | Checks Passed | Expected Judgment |
|---|---|---:|---|---:|---|
| news-001 | 35-55 | 78 | No | 1/3 | Moderate confidence in de-escalation signaling, low confidence in a finalized ceasefire. |

## Score Trends

### By Dimension

| Dimension | Avg Baseline | Avg Candidate | Delta | Note |
|---|---:|---:|---:|---|
| Claim Traceability | 0.00 | 0.00 | 0 |  |
| Contradiction Handling | 0.00 | 0.00 | 0 |  |
| Recency Discipline | 0.00 | 0.00 | 0 |  |
| Retrieval Efficiency | 0.00 | 0.00 | 0 |  |
| Signal Extraction | 0.00 | 0.00 | 0 |  |
| Source Coverage | 0.00 | 0.00 | 0 |  |

## Winning Patterns
- None recorded yet

## Losing Patterns
- Treating Trump's wording as proof that a ceasefire framework already exists.

## Recommendation
- Keep using candidate? No
- If No:
  - Roll back to: baseline-v1
  - Fix hard-check discipline first, then recalibrate against the benchmark bands

## Appendix
- Thresholds:
  - Min Improvement: 2
  - Large Regression: 5
- Stop Rule:
  - pause after 3 rounds with less than 2-point gain
- Notes:
  - this report covers only the phase 1 info-index sample pool
