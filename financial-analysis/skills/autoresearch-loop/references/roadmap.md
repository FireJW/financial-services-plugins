# Autoresearch Loop Roadmap

This roadmap is the current working plan for making Codex better at fixed,
repeatable tasks.

## Goal

Improve recurring workflows over time through:

- stable task boundaries
- mechanical checks
- score-based comparison
- rollback on failed attempts
- explicit learning records

The first objective is not to build a general autonomous platform. The first
objective is to prove that a small closed-loop process can measurably improve a
real task.

## Why This Lives Under `financial-analysis`

The near-term target tasks fit best here:

- stock analysis templates already belong in this plugin
- document cleanup is often part of analysis output cleanup
- code-fix is not finance-specific, but it is the best first proving ground for
  the loop itself

This keeps the first implementation close to real workflows without opening a
new top-level plugin too early.

## Three-Step Rollout

### Phase 1: Code Fix Loop

Time horizon: about 1 week

Why first:

- easiest to verify
- easiest to compare against a baseline
- lowest risk of fake improvement

Target outcome:

- repeated bug-fix tasks can be run through one stable loop
- every attempt is logged
- failed attempts are rolled back
- success rate and regression rate can be compared to baseline

Minimum acceptance:

- fixed task pool
- repeatable validation path
- baseline vs. improved comparison
- explicit keep or rollback decision for each attempt

### Phase 2: Document Workflow Loop

Time horizon: about 2 to 4 weeks

Why second:

- tests whether the same loop works outside pure code tasks
- still easier to judge than stock analysis

Target outcome:

- document cleanup tasks can use the same high-level loop
- shared logging and rollback stay the same
- task-specific checks cover structure, consistency, and information retention

Minimum acceptance:

- stable checklist-driven evaluation
- reduced omissions, contradictions, or duplication
- clear evidence that the loop improves usability for the target reader

### Phase 3: Stock Template Loop

Time horizon: about 1 to 2 months

Why last:

- most subjective of the three
- highest dependence on reliable scoring
- time-sensitive data creates extra noise

Target outcome:

- analysis output uses a stable template
- fact quality and template quality are scored separately
- the loop improves structure and traceability before trying to optimize thesis
  quality

Minimum acceptance:

- absolute-date discipline
- source traceability
- required sections always present
- fewer factual and structural errors than the baseline

## What Not To Build Yet

Do not build these in phase 1:

- a general multi-agent orchestration framework
- a database-heavy run history system
- a UI layer
- a universal plugin that tries to own every workflow
- automatic full-web data collection for every task
- a self-learning memory system with uncontrolled growth

The loop must prove value before infrastructure expands.

## Core Principles

1. Prove one task improves before expanding to the next.
2. Define scoring and rollback before automation polish.
3. Keep task-specific rules separate from the shared control loop.
4. Use hard gates before soft scores.
5. Treat "looks better" as insufficient without evidence.
