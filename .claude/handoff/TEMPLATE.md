# Handoff: <task-name>

## Goal

<What this task is trying to achieve>

## Current State

- Status:
- Scope boundary:

## Managed Snapshot

<!-- codex:handoff-meta:start -->
- Last updated:
- Branch:
- Working directory:
<!-- codex:handoff-meta:end -->

## Files In Play

- changed:
- reviewed:
- still pending:

## Verification Already Run

- command:
  result:
- command:
  result:

## Decisions

- decision:
  reason:

## Risks / Open Questions

- risk or open question

## Next Steps

1. highest-priority next action
2. second next action
3. verification after that action

## Git Snapshot

<!-- codex:handoff-git-status:start -->
```text
<refresh with scripts/codex-handoff-refresh.ps1>
```
<!-- codex:handoff-git-status:end -->

## Resume Commands

```powershell
Set-Location 'C:\path\to\repo'
git status --short
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-show.ps1
```

## References

- plan:
- review:
- related docs:
