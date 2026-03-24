# Code-Fix Scoring

Use this scorecard only after all hard checks pass.

## Hard Checks

These are pass or fail:

- reproducible before change
- verifiable after change
- no new critical regression
- root cause and fix are aligned
- change scope is controlled

If any hard check fails, reject the candidate without scoring it as a winner.

## Soft Score Dimensions

Total possible score: 100

### 1. Root-Cause Quality: 25

- 20-25: clearly explains the true trigger and failure path
- 10-19: partially correct but still shallow or incomplete
- 0-9: mostly symptom description or unsupported guess

### 2. Fix Minimality: 20

- 16-20: narrow change with little unrelated movement
- 8-15: acceptable but broader than necessary
- 0-7: large or noisy change for a small bug

### 3. Verification Completeness: 20

- 16-20: covers repro path and relevant edge or regression checks
- 8-15: covers the main path only
- 0-7: weak or incomplete verification

### 4. Regression Risk Control: 15

- 12-15: upstream and downstream risk checked well
- 6-11: some risk review, but gaps remain
- 0-5: little evidence of regression thinking

### 5. Debugging Efficiency: 10

- 8-10: converges quickly with little blind trial and error
- 4-7: some waste, but still reasonably focused
- 0-3: repeated blind edits or churn

### 6. Reuse Value: 10

- 8-10: notes are reusable for future similar bugs
- 4-7: some reuse value but not cleanly stated
- 0-3: little reusable learning captured

## Decision Guidance

Default thresholds:

- keep only if score improves by at least 2 points
- treat a drop of 5 or more points as a large regression
- stop after repeated low-gain rounds unless a hard issue was fixed
