# Plan: repo-codex-flow-followups

## Goal

Turn the repo-level Codex workflow into something operators can actually reuse
from the desktop app and from Windows PowerShell CLI sessions.

## Scope

- In scope:
  - repo-level workflow docs
  - plan, review, and handoff templates
  - lightweight PowerShell helpers for repeatable operator flow
- Out of scope:
  - changing plugin behavior
  - refactoring financial-analysis or quant strategy logic
  - cleaning unrelated worktree changes

## Constraints

- Technical:
  - keep changes lightweight and repo-local
  - assume Windows PowerShell is available
  - do not assume `pwsh` is installed or on `PATH`
- Product/workflow:
  - prefer durable process assets over chat-only context
  - preserve capability-first routing and git safety rules
- Environment:
  - this worktree may contain unrelated user changes
  - `.tmp/` and runtime artifacts must stay out of versioned scope

## Success Criteria

- [x] Docs and examples use copy-pasteable Windows PowerShell commands
- [x] Plan and review helpers are present and runnable
- [x] Handoff creation is standardized for future sessions
- [x] Handoff refresh is standardized for future sessions
- [x] Follow-up work is concrete enough to continue without rediscovery

## Target Files

| File | Why it matters | Expected change |
|------|----------------|-----------------|
| `.context/prefs/workflow.md` | defines default operator flow | update |
| `CODEX_DEVELOPMENT_FLOW.md` | operator guide | verify |
| `.context/templates/review-report-template.md` | structured review seed | add |
| `.context/templates/handoff-template.md` | handoff seed | add |
| `.claude/plan/TEMPLATE.md` | reusable plan scaffold | add |
| `.claude/handoff/TEMPLATE.md` | reusable handoff scaffold | add |
| `scripts/codex-plan-init.ps1` | create plan files | add |
| `scripts/codex-review-init.ps1` | create review files | add |
| `scripts/codex-handoff-init.ps1` | create handoff files | add |
| `scripts/codex-handoff-refresh.ps1` | refresh git snapshot in handoff files | add |

## Execution Steps

1. Confirm the current workflow docs and helper scripts that already exist.
2. Add missing plan, review, and handoff scaffolding.
3. Update documentation to point at the actual Windows PowerShell commands.
4. Smoke-test each helper with a throwaway task name.
5. Refresh the handoff so the next session can continue without rediscovery.

## Verification

| Command / Check | Purpose | Expected result |
|-----------------|---------|-----------------|
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 -Summary "workflow check"` | verify decision logging works | session log path is printed |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "workflow-smoke-test"` | verify plan helper works | plan file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-review-init.ps1 -Name "workflow-smoke-test"` | verify review helper works | review file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name "workflow-smoke-test"` | verify handoff helper works | handoff file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\workflow-smoke-test.md` | verify handoff refresh works | handoff file gets a fresh managed snapshot |
| manual doc read-through | catch stale filenames or commands | docs match actual files |

## Risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| docs drift from helper behavior | operators stop trusting the workflow | update docs and helpers together |
| too much automation too early | flow becomes brittle | keep helpers thin and explicit |
| handoff docs become generic sludge | future sessions still need rediscovery | require exact file paths, next steps, and commands |

## Open Questions

- Should commit-history summarization be the next helper after handoff refresh?
- Should there be one repo-level active handoff file in addition to per-task handoffs?

## Notes

- decision log: `.context/current/branches/main/session.log`
- operator guide: `CODEX_DEVELOPMENT_FLOW.md`
