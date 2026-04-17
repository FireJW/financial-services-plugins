# Verification Checklist

Use this checklist for the P0 verification pass.

The logical checks apply to both:

- classic markdown verifier reports
- structured verifier reports that encode the same checks in JSON

## Contract Checks

- The worker output includes all required sections.
- The sections appear in the required order.
- The required sections are non-empty.

## Evidence Checks

- `Confirmed` contains only established facts or explicitly says `- None.`
- `Unconfirmed` captures remaining uncertainty or explicitly says `- None.`
- `Risks` captures failure modes, invalidation, or explicitly says `- None.`

## Scope Checks

- `Conclusion` answers the task that was actually asked.
- `Next Step` is actionable and tied to the current task.
- The output does not silently escalate into unrelated work.

## Verifier Verdicts

- `PASS`: all required checks pass
- `FAIL`: contract or evidence checks fail
- `PARTIAL`: reserved for environmental blockers, not weak analysis
