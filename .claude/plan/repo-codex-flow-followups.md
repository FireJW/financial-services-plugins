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
- [x] A local operator status board can be refreshed in one PowerShell command
- [x] Recent commit history can be synced into `.context/history/`
- [x] Commit enrichment can be updated from PowerShell without hand-editing JSONL
- [x] A CLI-friendly recent summary can be regenerated from durable history
- [x] A one-command refresh helper can rebuild history, summary, status, and handoff together
- [x] The current local `HEAD` can be checkpointed outside versioned durable history
- [x] The current local `HEAD` checkpoint can be refreshed without rebuilding the full status board
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
| `scripts/codex-commit-checkpoint.ps1` | refresh the local-only HEAD checkpoint directly | add |
| `scripts/codex-workflow-status.ps1` | show current operator status and resume cues | add |
| `scripts/codex-commit-history-sync.ps1` | sync durable commit history | add |
| `scripts/codex-commit-history-enrich.ps1` | enrich durable commit metadata | add |
| `scripts/codex-release-summary.ps1` | regenerate recent summary from durable history | add |
| `scripts/codex-workflow-refresh.ps1` | rerun the default checkpoint refresh chain | add |
| `.context/current/branches/<branch>/latest-commit.md` | local-only HEAD checkpoint when durable history lags | add |

## Execution Steps

1. Confirm the current workflow docs and helper scripts that already exist.
2. Add missing plan, review, and handoff scaffolding.
3. Update documentation to point at the actual Windows PowerShell commands.
4. Smoke-test each helper with a throwaway task name.
5. Add a branch-local operator status helper.
6. Add a durable commit-history sync helper.
7. Add a durable commit-history enrichment helper.
8. Add a CLI-friendly recent summary helper.
9. Add a one-command workflow refresh helper.
10. Add a local-only current-HEAD checkpoint.
11. Add a dedicated helper for refreshing the local-only current-HEAD checkpoint.
12. Refresh the handoff so the next session can continue without rediscovery.

## Verification

| Command / Check | Purpose | Expected result |
|-----------------|---------|-----------------|
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 -Summary "workflow check"` | verify decision logging works | session log path is printed |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "workflow-smoke-test"` | verify plan helper works | plan file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-review-init.ps1 -Name "workflow-smoke-test"` | verify review helper works | review file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name "workflow-smoke-test"` | verify handoff helper works | handoff file is created |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\workflow-smoke-test.md` | verify handoff refresh works | handoff file gets a fresh managed snapshot |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1` | verify operator status helper works | a readable status board is printed and `.context/current/branches/<branch>/status.md` is refreshed |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 5` | verify durable history sync works | `.context/history/commits.jsonl` and `.context/history/commits.md` are refreshed |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-enrich.ps1 -Commit 2f29ff3 -ContextId "repo-codex-flow-followups"` | verify durable history enrichment works | the matching commit row is updated in `.context/history/commits.jsonl` |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 10` | verify recent summary helper works | `.context/history/latest-summary.md` is refreshed |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 10 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md` | verify the default checkpoint refresh chain works | history, summary, status, and handoff are all refreshed in one command |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1` | verify the dedicated local HEAD helper works | `.context/current/branches/<branch>/latest-commit.md` is refreshed without rebuilding the full status board |
| `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1` followed by `Get-Content .\.context\current\branches\main\latest-commit.md` | verify local HEAD checkpoint works | the local checkpoint shows current `HEAD` and whether durable history is synced or lagging |
| manual doc read-through | catch stale filenames or commands | docs match actual files |

## Risks

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| docs drift from helper behavior | operators stop trusting the workflow | update docs and helpers together |
| too much automation too early | flow becomes brittle | keep helpers thin and explicit |
| handoff docs become generic sludge | future sessions still need rediscovery | require exact file paths, next steps, and commands |

## Open Questions

- Should there be one repo-level active handoff file in addition to per-task handoffs?
- Should future enrichment helpers support multiline notes or keep a strict one-line CLI format?
- Should plan and review templates surface the dedicated checkpoint helper, or is handoff plus status the right default boundary?

## Notes

- decision log: `.context/current/branches/main/session.log`
- operator guide: `CODEX_DEVELOPMENT_FLOW.md`
