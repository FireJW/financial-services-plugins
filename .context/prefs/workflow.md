# Development Workflow Rules

This file defines the default Codex development flow for this repository.

## Read First

Before substantial work, read:

1. `AGENTS.md`
2. `CLAUDE.md`
3. `.context/prefs/coding-style.md`
4. `.context/prefs/workflow.md`
5. task-specific docs nearest the target files

## Workspace Selection

- Confirm the real target directory before editing.
- Do not assume `.tmp/` is the target unless the task explicitly lives there.
- For plugin work, prefer the repository root plugin structure first.

## Capability-First Routing

Before generic browsing, scraping, or ad hoc automation:

1. check `commands/` for an existing entrypoint
2. read the linked `skills/*/SKILL.md`
3. use native repo workflows first
4. fall back only when the repo has no suitable path

## Default Execution Loop

1. Clarify scope and target files.
2. Inspect existing patterns before proposing changes.
3. For multi-file or risky work, write down the intended steps before editing.
4. Implement in small increments.
5. Run the narrowest meaningful verification after each increment.
6. Review the changed scope before staging.
7. Update related docs if workflow or entrypoints changed.

## Verification Rules

Choose the smallest verification that can falsify the change:

- Markdown / commands / skills:
  - verify referenced paths, command names, and examples
- Scripts and code:
  - run targeted smoke tests, linters, type checks, or local execution
- Git safety tooling:
  - inspect `git status --short` and `git diff --cached --stat`

If verification cannot run, record why.

## Review Gate

- Before handoff or commit-ready status, walk through `.context/prefs/review-checklist.md`.
- For non-trivial changes, prefer a written review artifact under `.context/current/reviews/`.
- If process or operator behavior changed, verify docs and handoff artifacts match reality.

## Decision Logging

Record meaningful decisions in:

` .context/current/branches/<branch>/session.log `

Use it for:

- architecture choices
- tradeoff decisions
- bug root causes and fixes
- rejected alternatives with rationale

Append entries using this structure:

```markdown
## 2026-03-29T12:00:00Z
Decision: chose approach A
Alternatives: B, C
Reason: narrower blast radius and easier verification
Risk: may need follow-up if requirement expands
```

PowerShell helpers:

- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 ...`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-show.ps1`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "task-name"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-review-init.ps1 -Name "task-name"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name "task-name"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path ".\.claude\handoff\task-name.md"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 10 -HandoffPath ".\.claude\handoff\task-name.md"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 10`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-enrich.ps1 -Commit <hash> -ContextId "task-id" -Decisions "why this changed" -Risk "what could drift"`
- `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 10`

The plan, review, and handoff init helpers should prefill the current branch,
working directory, resume commands, and a default local checkpoint note.

## Status Check

Before resuming after a pause, prefer:

1. `scripts/codex-workflow-refresh.ps1 -Count 10 -HandoffPath ".\.claude\handoff\task-name.md"` when you need every checkpoint regenerated
2. `scripts/codex-commit-checkpoint.ps1` when only the true local `HEAD` checkpoint matters
3. `scripts/codex-workflow-status.ps1` for a broader snapshot refresh
4. the branch-local commit checkpoint under `.context/current/branches/<branch>/latest-commit.md`
5. the active handoff under `.claude/handoff/`
6. the branch-local session log under `.context/current/branches/<branch>/session.log`

The commit-checkpoint helper writes
`.context/current/branches/<branch>/latest-commit.md` so the true local `HEAD`
is readable even when versioned durable history is one refresh behind.
The status helper writes a local snapshot under
`.context/current/branches/<branch>/status.md` and also refreshes the same
commit checkpoint through the dedicated helper.
The workflow-refresh helper now prints the commit-checkpoint refresh as its own
step before status so the broader refresh chain is visible in CLI output.

## Durable History Flow

When repository workflow or operator-facing behavior changes:

1. prefer `scripts/codex-workflow-refresh.ps1` when the default refresh chain is enough
2. sync the recent commits into `.context/history/commits.jsonl`
3. enrich any commit rows that need durable `context_id`, `decisions`, `bugs`,
   or `risk`
4. regenerate `.context/history/latest-summary.md`
5. review `.context/history/commits.md` for CLI readability
6. refresh the active handoff if the next operator will depend on the new state

## Staging And Commit Safety

- Prefer targeted staging over broad `git add`.
- Use `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\git-stage-safe.ps1 <path>...`
  when staging manually.
- Treat staged `.tmp` content as a stop condition.
- Before commit, inspect:
  - `git status --short`
  - `git diff --cached --stat`
- If `git commit` fails because Git for Windows cannot launch the hook shell
  (for example `sh.exe ... couldn't create signal pipe`), run:
  - `git diff --cached --check`
  - `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\check_staged_artifacts.ps1`
  - `git commit --no-verify -m "..."`
- Use the `--no-verify` fallback only after the direct PowerShell guard passes,
  and only when the failing layer is the shell launcher rather than the guard
  itself.

## Environment Notes

- This machine may not expose `python` or `py` on PATH.
- If a task depends on Python under a prototype or local tool, prefer the known
  vendor interpreter path when available.
- Keep PowerShell examples explicit and copy-pasteable.
