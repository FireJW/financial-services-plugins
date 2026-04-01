# Workflow Improvement Loop Pack

As of 2026-04-01.

## Fixed Task Profile

- Workflow: runtime host reliability regression
- Stable sample set:
  - Jenny feedback workflow
  - A-share macro shock chain map
  - latest-event verification
  - X-post evidence
  - evidence-to-article

## Current Baseline

- Baseline version: `baseline-v1`
- Current pass rate: 54/54
- Baseline strengths:
  stable structure checks, prompt budget warnings, real-task fixture coverage
- Baseline weakness:
  no explicit keep/rollback judgment artifact for workflow-level upgrades

## Candidate Change

- Candidate version: `candidate-v2`
- Proposed change:
  add a workflow-improvement decision layer that records sample-set coverage,
  score dimensions, and a final keep/rollback call after each expansion.

## Score Dimensions

- sample stability
- regression safety
- scorecard clarity
- operator readability
- rollback clarity

## Verification Result

- Hard checks:
  stable sample set: pass
  score dimensions declared: pass
  rollback rule declared: pass
  mixed task types in one loop: pass, because the loop is explicitly the runtime reliability suite

- Baseline summary:
  strong on runtime behavior visibility, weaker on explicit workflow-level decision framing

- Candidate summary:
  stronger on keep/rollback framing and scorecard visibility, with no regression in the stable sample set shown in the pack

## Decision Hint

- The candidate should only be kept if the decision layer stays lightweight and does not replace the native workflow outputs themselves.
