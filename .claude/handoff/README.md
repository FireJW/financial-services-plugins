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
   This auto-fills the current branch and repository path in the generated
   resume commands and pre-fills a default local checkpoint note.
2. Refresh the managed snapshot when the branch state changes:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\task-name.md`
3. Refresh the local commit checkpoint before handoff review:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1`
4. Refresh local status when you also need the broader git and session snapshot:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1`
5. Read `.context/current/branches/<branch>/latest-commit.md` when you need the true local `HEAD` and durable history may lag.
6. Fill in the current state, changed files, verification, and next actions.
7. Keep commands copy-pasteable and Windows-friendly.
8. Reference related plan files under `.claude/plan/` when they exist.

## Minimum Standard

Every handoff should contain:

- exact target directories
- exact files changed or still pending
- exact verification that already ran
- refreshed timestamp, branch, and git snapshot
- an explicit local checkpoint note when `latest-commit.md` matters
- next steps in priority order
- resume commands that work from Windows PowerShell
