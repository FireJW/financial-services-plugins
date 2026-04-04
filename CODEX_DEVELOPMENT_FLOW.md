# Codex Development Flow

This document translates the useful parts of the `.ccg` system into a repository-local flow that works well with Codex, PowerShell, and long-running handoffs.

## Why This Exists

The `.ccg` setup under `C:\Users\rickylu\.claude\.ccg` has strong ideas:

- role-based analysis and review
- explicit plan and execute phases
- durable context and decision logging
- strict review and verification gates

This repository does not need the full external runtime to benefit from those ideas.
Instead, we keep the reusable parts here in lightweight form.

## The Default Codex Loop

1. Orient
   Read `AGENTS.md`, `CLAUDE.md`, `.context/prefs/*`, and the nearest project docs.
2. Route
   Use native commands, skills, and scripts before inventing a new path.
3. Plan
   For larger tasks, capture a plan in `.claude/plan/` or at least log decisions in `.context/current/branches/...`.
4. Execute
   Work in small verified steps. Parallelize independent analysis when it helps.
5. Review
   Use `.context/prefs/review-checklist.md`.
6. Handoff
   Update prompts, handoff docs, and exact commands when future sessions depend on them.

## Where To Put What

| Artifact | Where it belongs |
|----------|------------------|
| Runtime state, experiment output | `.tmp/`, `.claude/` |
| Branch-local session notes | `.context/current/branches/<branch>/session.log` |
| Durable repo-wide rules | `.context/prefs/` |
| Durable commit history | `.context/history/` |
| Task-specific plans | `.claude/plan/` |
| Task-specific handoffs | `.claude/handoff/` |
| User-facing handoff docs | project root or task root |

## PowerShell Quickstart

### Preflight

```powershell
Set-Location 'C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins'
Get-Content .\AGENTS.md
Get-Content .\CLAUDE.md
Get-Content .\.context\prefs\workflow.md
```

### Log A Decision

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 -Summary "Selected approach" -Decision "Use native skill first" -Reason "Matches repo routing rules"
```

### Start A Plan File

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "example-task"
```

The plan and review helpers prefill the current branch, working directory,
resume commands, and a default local checkpoint note.

### Show The Current Branch Notes

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-show.ps1
```

### Start A Review Report

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-review-init.ps1 -Name "example-task"
```

### Start A Handoff File

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name "example-task"
```

### Refresh A Handoff File

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\example-task.md
```

### Refresh The Workflow Checkpoint

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 10 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md
```

This reruns recent history sync, recent-summary generation, operator status
refresh, and active handoff refresh in one command.
It now prints the local commit checkpoint as its own step before status so the
refresh chain is easier to follow from PowerShell output.

### Refresh The Local Commit Checkpoint

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1
```

Use this when you only need the true local `HEAD` checkpoint and do not want to
rebuild the full status board.

### Show Operator Status

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1
```

This prints a current status board and refreshes a local snapshot at
`.context/current/branches/<branch>/status.md`.

### Sync Commit History

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 10
```

This refreshes `.context/history/commits.jsonl` and `.context/history/commits.md`
from recent git history while preserving durable manual metadata fields.

### Enrich A Commit Entry

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-enrich.ps1 -Commit 2f29ff3 -ContextId "repo-codex-flow-followups" -Decisions "why this changed" -Risk "what could drift"
```

This updates durable metadata for an already-synced commit without hand-editing
`.context/history/commits.jsonl`.

### Generate A Recent Summary

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 10
```

This writes `.context/history/latest-summary.md` so the next CLI session can
skim recent durable changes without reading the full commit ledger first.

### Read The Local Commit Checkpoint

```powershell
Get-Content .\.context\current\branches\main\latest-commit.md
```

This local-only file is refreshed by `codex-commit-checkpoint.ps1` and also by
`codex-workflow-status.ps1`, and shows whether versioned durable history is
synced with the current `HEAD` or lagging.

## Repo-Specific Defaults

- Prefer repository-native workflows over generic scraping.
- Prefer safe staging scripts over broad `git add`.
- Keep temp artifacts out of git.
- When a task depends on sibling projects, state exact paths and split responsibilities clearly.

## Windows Hook Fallback

If `git commit` fails on Windows with a Git-for-Windows shell launcher error such
as `sh.exe ... couldn't create signal pipe`, treat that as a hook-launch
problem, not an automatic reason to skip validation.

Use this fallback sequence:

1. run `git diff --cached --check`
2. run `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\check_staged_artifacts.ps1`
3. only if both checks pass, retry with `git commit --no-verify -m "..."`

Use `--no-verify` only when the hook launcher is the failing layer and the
PowerShell guard was run manually in the same staged state.

## For `.tmp` Prototype Work

When working in `.tmp` prototype areas:

- still follow the same orient/plan/verify loop
- keep runtime state in `.claude/`
- keep durable process rules in `.context/`
- document interpreter assumptions explicitly if `python` is not on `PATH`

## Practical Adoption Order

If you are extending this system later, do it in this order:

1. keep `.context/prefs/*` current
2. use the logging helpers during meaningful decisions
3. add task plans to `.claude/plan/` for multi-step work
4. leave a `.claude/handoff/` note when another CLI session needs to resume work
5. prefer `scripts/codex-workflow-refresh.ps1` before pausing when history,
   status, and handoff all changed together
6. use `scripts/codex-commit-checkpoint.ps1` when the true local `HEAD` matters
   more than the broader status snapshot
7. use `scripts/codex-workflow-status.ps1` before resuming after a pause when
   you also need git/session context
8. sync `.context/history/` after meaningful commits when durable history matters
9. enrich important commit rows when raw subjects are not enough context
10. regenerate `.context/history/latest-summary.md` when recent change context
   should be resumable from CLI
11. use `.context/current/branches/<branch>/latest-commit.md` when you need the
    true local `HEAD` checkpoint and the versioned history snapshot may lag
12. use structured review reports when a change needs explicit sign-off
13. only then consider more automation
