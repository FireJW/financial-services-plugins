# Sub-agent Contract

## Goal

Keep worker output machine-checkable and stable before expanding memory or
batch orchestration.

## Required Worker Sections

Workers must emit these sections exactly once and in this order:

1. `Conclusion`
2. `Confirmed`
3. `Unconfirmed`
4. `Risks`
5. `Next Step`

Use `##` headings.

## Content Rules

### Conclusion

- Short answer first.
- One concise paragraph or 1-3 bullets.

### Confirmed

- Bullet list of facts verified during the task.
- If none, use `- None.`

### Unconfirmed

- Bullet list of unresolved items or facts that still require validation.
- If none, use `- None.`

### Risks

- Bullet list of invalidation points, failure modes, or follow-up concerns.
- If none, use `- None.`

### Next Step

- One actionable next step.
- Must reflect the current task, not a speculative future roadmap.

## Failure Conditions

Treat worker output as invalid if any of these are true:

- A required section is missing.
- Required sections appear out of order.
- `Confirmed`, `Unconfirmed`, or `Risks` is empty and does not explicitly say
  `- None.`
- `Next Step` is blank.

## Notes

- This contract is intentionally Markdown-first.
- Do not introduce a more complex schema until this wrapper layer proves
  stable in tests.
