# Debug Loop

Use this loop for every code-fix improvement run.

## Sequence

1. Reproduce the bug.
2. State the root cause.
3. Make the smallest fix that targets that root cause.
4. Verify that the original failure is gone.
5. Check that no new critical issue was introduced.
6. Record the result.
7. Keep or roll back.

## What Good Looks Like

- the bug exists before the change
- the explanation matches the observed failure
- the fix is narrow
- the verification is stronger than a quick glance
- the result is easy to compare against baseline

## Common Failure Modes

- patching the symptom instead of the trigger
- editing multiple areas without proof they matter
- calling a fix successful without reproducing the original issue first
- skipping regression checks because the main test is green
- keeping a candidate that passes softly but fails a hard check

## Keep The Loop Small

In phase 1, this loop is for bug fixing only. Do not expand it into:

- broad refactoring
- general code quality review
- feature delivery
- research exploration

The point is to prove that a repeatable code-fix process can improve over time.
