# Verification Checklist

Use this checklist before keeping a candidate.

## Required

- [ ] The bug was reproducible before the fix.
- [ ] The bug is no longer reproducible after the fix.
- [ ] Relevant tests or repeatable verification steps pass.
- [ ] No new critical regression was introduced.
- [ ] The fix matches the stated root cause.
- [ ] The change scope is reasonable for the issue.
- [ ] The last stable version is known for rollback.

## Stronger Evidence

- [ ] A targeted regression test was added or updated.
- [ ] The touched area passed lint, type, or build checks when applicable.
- [ ] Nearby or dependent behavior was sanity-checked.
- [ ] The attempt record explains why this version won or lost.
