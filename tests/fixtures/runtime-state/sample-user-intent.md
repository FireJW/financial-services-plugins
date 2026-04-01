# User Intent Brief

## User Intent
- Build the P0/P1 runtime hardening layer first.
- Keep the solution at the wrapper layer before touching vendor runtime.

## Hard Constraints
- File safety and disk safety are the highest priority.
- Do not break the current headless runtime regression tests.

## Non-goals
- Do not implement the full Dream Memory pipeline.
- Do not start productizing the financial CLI in this step.
