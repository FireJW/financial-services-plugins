---
name: autoresearch-loop
description: Build a repeatable improvement loop for a fixed workflow so Codex can get better over time. Use when the goal is not just to finish one task, but to improve a recurring process such as code fixing, document cleanup, or stock analysis templates through scoring, rollback, and iteration.
---

# Autoresearch Loop

Use this skill when the user wants Codex to improve a **repeatable workflow**
instead of solving a single isolated task.

This skill is the control layer. It does not try to be a full autonomous
platform. Its job is to keep the loop disciplined:

1. Fix the task boundary.
2. Standardize inputs.
3. Define hard checks before any scoring.
4. Run one change at a time.
5. Keep the new version only if it passes and improves.
6. Roll back failed attempts.
7. Record why a version won or lost.

## Use Cases

- Repeated bug-fix flows where success can be tested
- Repeated document cleanup or restructuring tasks
- Repeated equity or stock analysis templates with a stable output format
- Repeated news and message indexing with a stable source-traceable output

Do not use this skill for:

- one-off ad hoc work with no repeated pattern
- tasks with no practical way to judge better vs. worse
- broad autonomous systems design with no clear stopping condition

## Workflow

### Step 1: Choose the task profile

Choose one of:

- `code-fix`
- `doc-workflow`
- `stock-template`
- `info-index`

If the task is mixed, pick the dominant outcome being improved. Do not optimize
multiple task types in the same loop.

Current task-specific companion skills:

- `code-fix`: [../autoresearch-code-fix/SKILL.md](../autoresearch-code-fix/SKILL.md)
- `info-index`: [../autoresearch-info-index/SKILL.md](../autoresearch-info-index/SKILL.md)

### Step 2: Freeze the task contract

Before any iteration, define:

- task goal
- in-scope inputs
- expected output shape
- hard-fail conditions
- scoring dimensions
- stop conditions
- rollback rule

Use:

- [references/scorecard-schema.md](references/scorecard-schema.md) for the
  shared contract
- [references/task-profiles.md](references/task-profiles.md) for the current
  task profiles

For `code-fix`, also load:

- [../autoresearch-code-fix/SKILL.md](../autoresearch-code-fix/SKILL.md)

### Step 3: Establish a baseline

Create or collect a fixed sample set before trying to improve the workflow.

Examples:

- 10-20 historical bug-fix tasks
- 10-20 document cleanup samples
- 5-10 stock analysis samples using the same template

The baseline must stay stable during comparison. Do not change the sample set
mid-run unless the user explicitly wants a new benchmark cycle.

### Step 4: Run single-change iterations

Each iteration may change only one of:

- prompt or instruction wording
- checklist order
- output template
- verification rule
- rollback threshold

Do not change several things at once unless the user is intentionally starting a
new experiment branch.

### Step 5: Gate before scoring

If a candidate fails any hard check, reject it immediately. Do not keep a
version that scores well on softer dimensions but fails a core requirement.

Typical hard checks:

- code fix: cannot reproduce, cannot verify, or introduces new failures
- doc workflow: drops key information or creates contradictions
- stock template: mixes time periods, lacks traceable sources, or omits required
  sections

### Step 6: Decide keep vs. rollback

Keep the new version only when all three are true:

1. hard checks pass
2. no new severe problem is introduced
3. score improves by the agreed threshold

Otherwise roll back to the last stable version.

### Step 7: Record the result

For every run, record:

- profile
- sample set version
- baseline score
- candidate score
- pass/fail on hard checks
- rollback decision
- brief explanation of why it won or lost

## Operating Rules

- Prefer task-specific loops over general-purpose frameworks.
- Prefer mechanical checks over subjective judgments.
- Use absolute dates for all time-sensitive market data.
- Separate fact quality from opinion quality.
- Do not optimize for speed until correctness and stability are proven.

## References

- [references/roadmap.md](references/roadmap.md)
- [references/scorecard-schema.md](references/scorecard-schema.md)
- [references/task-profiles.md](references/task-profiles.md)
