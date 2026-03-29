# Review Checklist

Use this checklist for Codex reviews, self-review, and handoff review.

## Scope And Routing

- Did we work in the correct directory?
- Did we use the repository's native workflow before inventing a new one?
- Did we keep the change inside the user-requested scope?

## Correctness

- Are paths, commands, and examples executable as written?
- Are new defaults safe and explicit?
- Are fallbacks observable rather than silent?

## Repository Hygiene

- Were `.tmp/`, `.claude/`, caches, screenshots, and other runtime artifacts kept out of versioned scope unless intended?
- Did we avoid broad cleanup unrelated to the task?
- If staging happened, was safe staging used?

## Maintainability

- Is the workflow understandable to the next session without re-discovery?
- Did we document non-obvious assumptions?
- Did we prefer lightweight helpers over one-off opaque commands?

## Verification

- Was there at least one concrete verification step?
- If verification could not run, was the blocker stated precisely?
- Do docs and handoff files match the actual current state?

## Cross-Project Awareness

- If a task touches both this repo and a sibling project, are boundaries and responsibilities clearly stated?
- If only one side was changed, is that asymmetry documented?
