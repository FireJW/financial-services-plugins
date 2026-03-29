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
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 -Summary "Selected approach" -Decision "Use native skill first" -Reason "Matches repo routing rules"
```

### Show The Current Branch Notes

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-show.ps1
```

## Repo-Specific Defaults

- Prefer repository-native workflows over generic scraping.
- Prefer safe staging scripts over broad `git add`.
- Keep temp artifacts out of git.
- When a task depends on sibling projects, state exact paths and split responsibilities clearly.

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
4. only then consider more automation, such as commit summarizers or review helpers
