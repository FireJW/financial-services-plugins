# Handoff Files

Use this directory for operator-facing handoff documents that help the next
Codex or PowerShell CLI session continue without rediscovering context.

## When To Create One

- the task will continue in another session
- a different tool or operator will take over
- the next step depends on exact commands, paths, or verification notes

## Usage

1. Create a new handoff:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name "task-name"`
2. Refresh the managed snapshot when the branch state changes:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\task-name.md`
3. Fill in the current state, changed files, verification, and next actions.
4. Keep commands copy-pasteable and Windows-friendly.
5. Reference related plan files under `.claude/plan/` when they exist.

## Minimum Standard

Every handoff should contain:

- exact target directories
- exact files changed or still pending
- exact verification that already ran
- refreshed timestamp, branch, and git snapshot
- next steps in priority order
- resume commands that work from Windows PowerShell
