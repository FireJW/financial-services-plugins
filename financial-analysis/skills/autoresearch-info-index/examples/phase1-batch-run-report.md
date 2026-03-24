# Phase 1 Run Report
Date: 2026-03-24
Profile: info-index
Sample Set: info-index-news-index-v1
Baseline Version: baseline-v1
Candidate Version: candidate-news-index-v1
Owner: Codex
Goal: Batch review across 5 distinct information-index tasks

## Summary
- Total Runs: 5
- Keep: 5
- Rollback: 0
- Runs With Hard Check Failures: 0
- Hard Check Failure Messages: 0
- Avg Baseline Score: 42.2
- Avg Candidate Score: 71
- Avg Delta: +28.8
- Avg Evidence Confidence Score: 87.6
- Avg Source Strength: 73.4
- Avg Agreement Score: 100
- Avg Evidence Band: 76.4-98.2
- Avg Evidence Band Width: 21.8
- Confidence Labels: usable-high=4, usable-medium=1, usable-low=0, blocked=0
- Confidence Gates: usable=5, blocked=0
- Avg Freshness Capture Score: 76
- Avg Shadow Signal Discipline: 100
- Avg Promotion Discipline: 100
- Avg Blocked Source Handling: 100
- Runs With Blocked Sources: 0
- Runs With Missing Expected Source Families: 0

## Task Mix
- news-001: geopolitics
- news-002: policy
- news-003: earnings
- news-004: rumor-denial
- news-005: macro

## Decision
- Overall Result: KEEP
- Why:
  - Keep count: 5, rollback count: 0
  - Average score delta: +28.8
  - Runs with hard-check failures: 0
  - Average evidence confidence score: 87.6
- Next Action:
  - Keep the current candidate and improve only the weakest scoring dimension next
  - Use the confidence snapshot to compare message quality across the next sample batch

## Run Table

| Run ID | Item ID | Candidate | Delta | Evidence | Band | Gate | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|---|
| 001 | news-001 | 66 | +27 | 91 | 79-100 | usable | Keep | Keep because hard checks passed and score improved by 27 |
| 002 | news-002 | 73 | +29 | 89 | 78-100 | usable | Keep | Keep because hard checks passed and score improved by 29 |
| 003 | news-003 | 78 | +32 | 83 | 72-94 | usable | Keep | Keep because hard checks passed and score improved by 32 |
| 004 | news-004 | 69 | +28 | 86 | 75-97 | usable | Keep | Keep because hard checks passed and score improved by 28 |
| 005 | news-005 | 69 | +28 | 89 | 78-100 | usable | Keep | Keep because hard checks passed and score improved by 28 |

## Hard Check Failures
- None

## Evidence Snapshot

| Metric | Average |
|---|---:|
| Source Strength | 73.40 |
| Claim Confirmation | 90.00 |
| Timeliness | 88.00 |
| Agreement | 100.00 |
| Evidence Confidence Score | 87.60 |
| Evidence Band Width | 21.80 |
| Freshness Capture Score | 76.00 |
| Shadow Signal Discipline | 100.00 |
| Promotion Discipline | 100.00 |
| Blocked Source Handling | 100.00 |

## Retrieval Gaps
- Common blocked sources: None
- Common missing expected source families: None

| Item ID | Blocked Sources | Missing Expected Source Families |
|---|---|---|
| news-001 | None | None |
| news-002 | None | None |
| news-003 | None | None |
| news-004 | None | None |
| news-005 | None | None |

## Benchmark Alignment
- Not available in these result files

## Score Trends

### By Dimension

| Dimension | Avg Baseline | Avg Candidate | Delta | Note |
|---|---:|---:|---:|---|
| Claim Traceability | 12.00 | 20.00 | +8 | Largest improvement |
| Contradiction Handling | 5.00 | 9.00 | +4 |  |
| Recency Discipline | 9.20 | 15.20 | +6 |  |
| Retrieval Efficiency | 6.00 | 10.00 | +4 |  |
| Signal Extraction | 6.00 | 10.00 | +4 |  |
| Source Coverage | 4.00 | 6.80 | +2.8 |  |

## Winning Patterns
- Recency-first ranking with a separate live tape and explicit conflict disclosure.

## Losing Patterns
- None recorded yet

## Recommendation
- Keep using candidate? Yes
- If Yes:
  - Next dimension to improve: source coverage
  - Keep comparing benchmark confidence bands, not only total scores

## Appendix
- Thresholds:
  - Min Improvement: 2
  - Large Regression: 5
- Stop Rule:
  - pause after 3 rounds with less than 2-point gain
- Notes:
  - this report summarizes whichever evaluated phase 1 result files were passed into the report builder
