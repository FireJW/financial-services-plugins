# Phase 1 Run Report
Date: 2026-03-24
Profile: info-index
Sample Set: info-index-news-index-v1
Baseline Version: baseline-v1
Candidate Version: candidate-news-index-v1
Owner: Codex
Goal: Hormuz negotiation realistic offline fixture

## Summary
- Total Runs: 1
- Keep: 1
- Rollback: 0
- Runs With Hard Check Failures: 0
- Hard Check Failure Messages: 0
- Avg Baseline Score: 57
- Avg Candidate Score: 95
- Avg Delta: +38
- Avg Evidence Confidence Score: 76
- Avg Source Strength: 71
- Avg Agreement Score: 100
- Avg Evidence Band: 68-84
- Avg Evidence Band Width: 16
- Confidence Labels: usable-high=0, usable-medium=1, usable-low=0, blocked=0
- Confidence Gates: usable=1, blocked=0
- Avg Freshness Capture Score: 100
- Avg Shadow Signal Discipline: 100
- Avg Promotion Discipline: 100
- Avg Blocked Source Handling: 100
- Runs With Blocked Sources: 1
- Runs With Missing Expected Source Families: 1

## Decision
- Overall Result: KEEP
- Why:
  - Keep count: 1, rollback count: 0
  - Average score delta: +38
  - Runs with hard-check failures: 0
  - Average evidence confidence score: 76
- Next Action:
  - Keep the current candidate and improve only the weakest scoring dimension next
  - Use the confidence snapshot to compare message quality across the next sample batch

## Run Table

| Run ID | Item ID | Candidate | Delta | Evidence | Band | Gate | Decision | Core Reason |
|---|---|---:|---:|---:|---|---|---|---|
| 001 | hormuz-negotiation-realistic-offline-fixture | 95 | +38 | 76 | 68-84 | usable | Keep | Keep because hard checks passed and score improved by 38 |

## Hard Check Failures
- None

## Evidence Snapshot

| Metric | Average |
|---|---:|
| Source Strength | 71.00 |
| Claim Confirmation | 41.00 |
| Timeliness | 92.00 |
| Agreement | 100.00 |
| Evidence Confidence Score | 76.00 |
| Evidence Band Width | 16.00 |
| Freshness Capture Score | 100.00 |
| Shadow Signal Discipline | 100.00 |
| Promotion Discipline | 100.00 |
| Blocked Source Handling | 100.00 |

## Retrieval Gaps
- Common blocked sources: Axios
- Common missing expected source families: public_ais

| Item ID | Blocked Sources | Missing Expected Source Families |
|---|---|---|
| hormuz-negotiation-realistic-offline-fixture | Axios | public_ais |

## Benchmark Alignment
- Not available in these result files

## Score Trends

### By Dimension

| Dimension | Avg Baseline | Avg Candidate | Delta | Note |
|---|---:|---:|---:|---|
| Claim Traceability | 12.00 | 20.00 | +8 |  |
| Contradiction Handling | 9.00 | 15.00 | +6 |  |
| Recency Discipline | 12.00 | 20.00 | +8 |  |
| Retrieval Efficiency | 6.00 | 10.00 | +4 |  |
| Signal Extraction | 6.00 | 10.00 | +4 |  |
| Source Coverage | 12.00 | 20.00 | +8 | Largest improvement |

## Winning Patterns
- Recency-first ranking with a separate live tape and explicit conflict disclosure.

## Losing Patterns
- None recorded yet

## Recommendation
- Keep using candidate? Yes
- If Yes:
  - Next dimension to improve: signal extraction
  - Keep comparing benchmark confidence bands, not only total scores

## Appendix
- Thresholds:
  - Min Improvement: 2
  - Large Regression: 5
- Stop Rule:
  - pause after 3 rounds with less than 2-point gain
- Notes:
  - this report summarizes whichever evaluated phase 1 result files were passed into the report builder
