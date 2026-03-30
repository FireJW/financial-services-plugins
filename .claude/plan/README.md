# Plan Files

Use this directory for task plans that should survive a single chat session.

## When To Create A Plan

- the task spans multiple steps or sessions
- verification will happen in stages
- another operator may need to continue the work later

## Usage

1. Create a new plan from the template:
   `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "task-name"`
2. Fill in the scope, target files, execution steps, and verification.
3. Update the file as decisions change.
4. Reference the plan path in future handoff documents.

## Conventions

- keep one file per task or initiative
- prefer lowercase kebab-case filenames
- update the success criteria and verification table as work progresses
