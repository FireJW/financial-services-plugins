# Context System

This directory provides a repository-level development memory and workflow layer
for Codex and other coding agents.

The design is adapted from the strongest parts of the local CCG workflow system,
but stripped of wrapper-specific runtime dependencies. The goal is portability:
the rules here should remain useful whether work happens in Codex desktop, a
PowerShell CLI session, or another coding environment.

## What Belongs Here

- Shared coding and workflow rules that should survive across sessions
- Decision history worth preserving with the repository
- Branch-local scratch logs that help active work without polluting git history

## Directory Layout

```text
.context/
|-- .gitignore
|-- .gitattributes
|-- README.md
|-- prefs/
|   |-- coding-style.md
|   |-- workflow.md
|   `-- review-checklist.md
|-- templates/
|   |-- review-report-template.md
|   `-- handoff-template.md
|-- current/
|   |-- branches/
|   |   `-- .gitkeep
|   `-- reviews/
`-- history/
    |-- commits.jsonl
    |-- commits.md
    `-- archives/
        `-- .gitkeep
```

## Usage

1. Read `prefs/coding-style.md` and `prefs/workflow.md` before broad changes.
2. Use `prefs/review-checklist.md` for self-review and handoff review.
3. Use `../CODEX_DEVELOPMENT_FLOW.md` as the repository-level operator guide.
4. Keep branch-local notes in `current/branches/<branch>/session.log`.
5. Use `templates/review-report-template.md` for structured review notes.
6. Use `templates/handoff-template.md` when another CLI session needs to resume.
7. Preserve durable decisions in `history/`.
8. Treat this directory as repository infrastructure, not task output.

## Commit Boundaries

- `prefs/` and `history/` are intended to be versioned.
- `current/` is intentionally local-only and ignored by git.

## Relationship To Existing Repo Rules

This folder complements, not replaces:

- `AGENTS.md`
- `CLAUDE.md`
- `CODEX_DEVELOPMENT_FLOW.md`
- `README.md`
- `.claude/plan/`
- `.claude/handoff/`
- `.githooks/`
- `scripts/codex-context-log.ps1`
- `scripts/codex-context-show.ps1`
- `scripts/codex-plan-init.ps1`
- `scripts/codex-review-init.ps1`
- `scripts/codex-handoff-init.ps1`
- `scripts/codex-handoff-refresh.ps1`
- `scripts/git-stage-safe.ps1`

If rules conflict, prefer the more specific repository safety rule.
