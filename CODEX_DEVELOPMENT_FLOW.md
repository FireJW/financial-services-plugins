# Codex Development Flow

This document translates the useful parts of the `.ccg` system into a repository-local flow that works well with Codex, PowerShell, and long-running handoffs.

## Why This Exists

The `.ccg` setup under `%USERPROFILE%\.claude\.ccg` has strong ideas:

- role-based analysis and review
- explicit plan and execute phases
- durable context and decision logging
- strict review and verification gates

This repository does not need the full external runtime to benefit from those ideas.
Instead, we keep the reusable parts here in lightweight form.

## The Default Codex Loop

1. Orient
   Read `AGENTS.md`, `CLAUDE.md`, `.context/prefs/*`, and the nearest project docs.
2. Classify
   Decide `Simple` vs `Complex` using the hard rules in the dual-track runtime docs.
3. Route
   Check `routing-index.md`, then use native commands, skills, and scripts before inventing a new path.
4. Plan
   For larger tasks, capture a plan in `.claude/plan/` or at least log decisions in `.context/current/branches/...`.
5. Execute
   Keep simple work light. For complex work, build a context pack and execute in checkpoints.
6. Review
   Use `.context/prefs/review-checklist.md` and verify according to task complexity.
7. Deliver
   Finish with the delivery contract.
8. Handoff
   Update prompts, handoff docs, and exact commands when future sessions depend on them.

## Complex-Task Discovery Order

For `Complex` tasks, discover context in this order:

1. `routing-index.md`
2. matching `command` or `skill`
3. related docs in `financial-services-docs/docs/runtime/codex-dual-track/`
4. related recurring notes in `obsidian-kb-v2`
5. only then start fresh execution

## Local Obsidian KB Capture Contract

This file is the canonical workflow contract for persisting Codex conversation
results into the local Obsidian KB.

### Trigger Phrases

When the user says any of the following, treat it as a direct execution request
to persist the current exchange into the local Obsidian KB:

- `落进本地obsidian知识库`
- `同步到obsidian知识库`
- `记到obsidian`
- `落到raw`
- `存进本地知识库`
- close paraphrases with the same intent

### What To Capture

Default capture unit:

1. the current user request
2. the assistant's final substantive answer
3. optional `Key Artifacts` if there are commands, files, logs, note paths, or
   generated outputs worth preserving

Default body shape:

```md
## User Request

...

## Assistant Response

...

## Key Artifacts

- ...
```

### Where It Goes

Default sink:

- raw lane: `08-AI知识库/10-raw/manual/`
- native command:
  `node scripts/capture-codex-thread.mjs`

Default source provenance:

1. if the conversation already contains an explicit `codex://threads/...` URI,
   use it
2. otherwise use the runtime-safe fallback
   `codex://threads/current-thread`

### Default Execution Rule

Use the native command:

```powershell
@'
...captured markdown body...
'@ | node scripts/capture-codex-thread.mjs --thread-uri "codex://threads/current-thread" --topic "specific topic" --title "YYYY-MM-DD specific title" --source-label "Codex thread capture" --compile --timeout-ms 240000
```

Execution defaults:

- choose a specific topic, not a vague umbrella topic
- use a date-prefixed title
- default to `--compile` for reusable knowledge-bearing content
- skip compile only for trivial chatter or content with no durable value
- after capture, keep links/views refreshed

### Batch Import

When multiple historical Codex threads need to be imported together, use the
batch manifest route instead of repeating the single-thread command manually:

1. generate a skeleton manifest plus body templates:

```powershell
node scripts/init-codex-thread-batch.mjs --output-dir ".tmp-codex-thread-handoff-batch" --thread-id "019d5746-28de-7631-ad1c-d35ca5815b94" --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab" --topic "历史 Codex 线程沉淀" --title-prefix "历史线程待整理"
```

2. fill the generated `bodies/*.md`
3. run the batch import:

```powershell
node scripts/capture-codex-thread-batch.mjs --manifest ".\obsidian-kb-local\examples\codex-thread-batch.template.json" --compile --timeout-ms 240000
```

Batch rules:

- manifest entries may use either inline `body` or relative `body_file`
- an explicit `codex://threads/...` URI is preferred when known
- `thread_id` is acceptable and will be normalized into a thread URI
- if neither is present, the single-thread runtime fallback still resolves to
  `codex://threads/current-thread`
- links/views should be refreshed once at the end of the batch, not once per
  entry

### Verification

To verify whether one or more Codex threads actually landed in the local
Obsidian KB, use the verifier:

```powershell
node scripts/verify-codex-thread-capture.mjs --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"
node scripts/verify-codex-thread-capture.mjs --manifest ".\obsidian-kb-local\.tmp-codex-thread-handoff-batch\manifest.json"
```

The verifier reports:

- whether each thread was captured at all
- matching raw notes
- matching wiki notes
- a final summary of captured vs missing threads

The live Obsidian panel for this workflow is:

- `08-AI知识库/30-views/00-System/08-Codex Thread Capture Status.md`
- `08-AI知识库/30-views/00-System/09-Codex Thread Recovery Queue.md`
- `08-AI知识库/30-views/00-System/10-Codex Thread Audit Log.md`

It is refreshed by the normal `refresh-wiki-views` flow and summarizes tracked
thread URIs, recent raw captures, derived wiki notes, and the most recent
`verify` / `reconcile` runs.

For a terminal-side snapshot of the same audit surface, use:

```powershell
node scripts/codex-thread-audit-report.mjs
node scripts/codex-thread-audit-doctor.mjs
```

To archive expired synthetic/demo audit entries into `logs/archive/`:

```powershell
node scripts/backfill-codex-thread-audit-run-ids.mjs
node scripts/backfill-codex-thread-audit-run-ids.mjs --apply
node scripts/prune-codex-thread-audit-logs.mjs --days 7
node scripts/prune-codex-thread-audit-logs.mjs --days 7 --apply
```

On 2026-04-08 the refresh script was hardened so it now defaults to:

1. try the Obsidian CLI first
2. fall back to direct filesystem writes if the CLI stalls or fails
3. stop retrying the CLI for the remaining view notes after the first CLI
   fallback in the same run

Use `node scripts/refresh-wiki-views.mjs --force-cli` only when you explicitly
want strict CLI-only behavior.

### Reconciliation / Missing Recovery

When you already have a target set of threads and want to auto-generate a
recovery package for only the missing ones, use:

```powershell
node scripts/reconcile-codex-thread-capture.mjs --output-dir ".tmp-codex-thread-reconcile-smoke" --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab" --thread-id "019d-missing-demo-thread" --topic "历史 Codex 线程补录" --title-prefix "待补录线程"
```

This writes:

- `verification-report.json`
- `missing-manifest.json`
- `bodies/*.md` templates for only the missing threads

### When To Compile By Default

Compile by default for:

- research results
- market / trading analysis
- planning documents
- workflow and tooling changes
- KB operating rules
- implementation notes with durable reuse value

Usually skip compile for:

- greetings
- tiny one-off logistics
- content that would only create noise in the KB

### Sync Rule

When KB capture behavior changes:

1. update this file first
2. keep the short trigger rules in `AGENTS.md` aligned
3. keep the short trigger rules in `CLAUDE.md` aligned
4. update `obsidian-kb-local` usage docs if the command surface changed

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
Set-Location '<repo-root>'
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
