# Plan: <task-name>

## Goal

<What outcome this task should produce>

## Operator Context

- Branch: <branch>
- Working directory: C:\path\to\repo
- Local checkpoint note:

## Scope

- In scope:
- Out of scope:

## Constraints

- Technical:
- Product/workflow:
- Environment:

## Success Criteria

- [ ] Primary outcome is implemented
- [ ] Verification is defined and runnable
- [ ] Docs or handoff are updated if needed

## Target Files

| File | Why it matters | Expected change |
|------|----------------|-----------------|
| `path/to/file` | context | create / update / verify |

## Execution Steps

1. Inspect the target area and confirm patterns.
2. Implement the smallest useful increment.
3. Verify the increment before expanding scope.
4. Update docs, handoff, or follow-up notes if behavior changed.

## Verification

| Command / Check | Purpose | Expected result |
|-----------------|---------|-----------------|
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\...` | smoke test | command succeeds |

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

## Risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| example risk | example impact | example mitigation |

## Open Questions

- unresolved item

## Notes

- related docs:
- decision log:
