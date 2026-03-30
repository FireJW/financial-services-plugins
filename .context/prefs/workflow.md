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

## Staging And Commit Safety

- Prefer targeted staging over broad `git add`.
- Use `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\git-stage-safe.ps1 <path>...`
  when staging manually.
- Treat staged `.tmp` content as a stop condition.
- Before commit, inspect:
  - `git status --short`
  - `git diff --cached --stat`

## Environment Notes

- This machine may not expose `python` or `py` on PATH.
- If a task depends on Python under a prototype or local tool, prefer the known
  vendor interpreter path when available.
- Keep PowerShell examples explicit and copy-pasteable.
