# Review Report: <task-name>

## Scope

- Branch: <branch>
- Working directory: C:\path\to\repo
- Local checkpoint note:
- Reviewed diff:
- Reviewed files:
- Reviewer:

## Summary

<One-paragraph overall assessment>

## Critical

- [ ] file:line - issue, impact, required fix

## Warning

- [ ] file:line - issue, impact, suggested fix

## Info

- [ ] file:line - optional improvement

## Passed Checks

- [ ] scope stayed bounded
- [ ] verification ran or blocker was stated
- [ ] docs and handoff stayed in sync
- [ ] local HEAD checkpoint was refreshed when current branch state mattered

## Recommendation

- `PASS`
- `NEEDS_CHANGES`

## Resume Commands

```powershell
Set-Location 'C:\path\to\repo'
git status --short
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1
Get-Content .\.context\current\branches\<branch>\latest-commit.md
```

Use the commit-checkpoint helper first when the true local `HEAD` matters more
than versioned durable history.

## Follow-Up

- owner:
- next action:
