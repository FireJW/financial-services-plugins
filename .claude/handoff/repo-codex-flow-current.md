# Handoff: repo-codex-flow-current

## Goal

Stabilize the repo-level Codex workflow so future Codex desktop and Windows
PowerShell CLI sessions can continue without rediscovering process context.

## Current State

- Status: plan, review, and handoff scaffolding now exist on disk, and the
  workflow layer now includes a branch-local operator status board plus durable
  commit-history sync, commit enrichment, and a CLI-readable recent-summary
  helper plus a one-command workflow refresh entrypoint and a dedicated
  local-only current-HEAD checkpoint helper so a CLI session can resume from
  one generated checkpoint and a repo-local change ledger instead of reading
  raw git history first.
- Scope boundary: repo-level workflow only. No plugin behavior or quant logic
  was changed.

## Managed Snapshot

<!-- codex:handoff-meta:start -->
- Last updated: 2026-04-04T15:57:00.4962142+08:00
- Branch: main
- Working directory: C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins
<!-- codex:handoff-meta:end -->

## Files In Play

- changed:
  - `.claude/handoff/README.md`
  - `.claude/handoff/TEMPLATE.md`
  - `.context/README.md`
  - `.context/templates/handoff-template.md`
  - `CLAUDE.md`
  - `CODEX_DEVELOPMENT_FLOW.md`
  - `.context/prefs/workflow.md`
  - `.context/prefs/review-checklist.md`
  - `.context/templates/review-report-template.md`
  - `.context/templates/handoff-template.md`
  - `.claude/plan/README.md`
  - `.claude/plan/TEMPLATE.md`
  - `.claude/plan/repo-codex-flow-followups.md`
  - `.claude/handoff/README.md`
  - `.claude/handoff/TEMPLATE.md`
  - `.claude/handoff/repo-codex-flow-current.md`
  - `scripts/codex-plan-init.ps1`
  - `scripts/codex-review-init.ps1`
  - `scripts/codex-handoff-init.ps1`
  - `scripts/codex-handoff-refresh.ps1`
  - `scripts/codex-commit-checkpoint.ps1`
  - `scripts/codex-workflow-status.ps1`
  - `scripts/codex-commit-history-sync.ps1`
  - `scripts/codex-commit-history-enrich.ps1`
  - `scripts/codex-release-summary.ps1`
  - `scripts/codex-workflow-refresh.ps1`
- reviewed:
  - `.context/current/reviews/workflow-review-smoke-2-review.md`
- still pending:
  - decide whether plan or review templates should surface the dedicated
    commit-checkpoint helper, or whether handoff plus status is the right
    boundary

## Verification Already Run

- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-log.ps1 -Summary 'workflow helper smoke test' -Decision 'added plan review handoff assets' -Reason 'docs already referenced them but files were missing'`
  result: appended an entry to `.context/current/branches/main/session.log`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name 'workflow-smoke-test-plan'`
  result: created `.claude/plan/workflow-smoke-test-plan.md`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-review-init.ps1 -Name 'workflow-review-smoke-2'`
  result: created `.context/current/reviews/workflow-review-smoke-2-review.md`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path '.\.claude\handoff\repo-codex-flow-current.md'`
  result: refreshed the managed timestamp, branch, working directory, and git snapshot in this handoff
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name 'handoff-refresh-smoke'`
  result: created a handoff file and auto-populated its managed snapshot, then the smoke file was removed
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1`
  result: printed a readable status board and refreshed
  `.context/current/branches/main/status.md`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 5`
  result: refreshed `.context/history/commits.jsonl` and
  `.context/history/commits.md`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-enrich.ps1 -Commit 2f29ff3 -ContextId 'repo-codex-flow-followups' ...`
  result: updated the matching `commits.jsonl` entry without hand-editing JSONL
- command:
  reran commit-history sync after enrichment
  result: `context_id`, `decisions`, and `risk` were preserved in both
  generated history files
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 30`
  result: created `.context/history/latest-summary.md` from durable commit
  history
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 30 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md`
  result: reran durable history sync, summary generation, status refresh, and
  active handoff refresh in one CLI-safe command
- command:
  `git commit -m "feat(workflow): add codex resume checkpoint helpers"`
  result: failed because Git for Windows could not launch the `pre-commit`
  shell wrapper and raised `sh.exe ... couldn't create signal pipe, Win32 error 5`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\.githooks\check_staged_artifacts.ps1`
  result: the direct PowerShell staged-artifact guard passed, confirming the
  failure was in hook launch rather than repository validation
- command:
  `git commit --no-verify -m "feat(workflow): add codex resume checkpoint helpers"`
  result: created local commit `40ce727` on `main`
- command:
  `git commit --no-verify -m "docs(workflow): document windows hook fallback"`
  result: created local commit `b8898a6` on `main`
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1`
  result: refreshed `.context/current/branches/main/latest-commit.md` and
  surfaced that durable history is lagging the current `HEAD` by 2 commits
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name 'workflow-autofill-smoke'`
  result: generated a temporary handoff whose resume commands already used the
  real repo path and branch-local `latest-commit.md` path; the smoke file was
  removed after validation
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-refresh.ps1 -Path .\.claude\handoff\repo-codex-flow-current.md` followed by `git diff --check -- .\.claude\handoff\repo-codex-flow-current.md`
  result: refreshed the active handoff without reintroducing the EOF blank-line
  formatting failure
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1`
  result: refreshed `.context/current/branches/main/latest-commit.md` without
  rebuilding the full status board
- command:
  `& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-handoff-init.ps1 -Name 'workflow-checkpoint-helper-smoke'`
  result: generated a temporary handoff whose resume commands already included
  `codex-commit-checkpoint.ps1` and still auto-filled the real repo path; the
  smoke file was removed after validation

## Decisions

- decision: implement the missing filesystem assets instead of only editing docs
  reason: the docs already referenced plan/review/handoff scripts, so missing
  files were the real blocker for CLI continuation
- decision: use explicit Windows PowerShell commands in examples
  reason: this machine does not reliably expose `pwsh` on `PATH`
- decision: keep handoff templates in `.context/templates/` and generated task
  handoffs in `.claude/handoff/`
  reason: template logic stays durable and versioned while per-task handoffs get
  a predictable operator-facing location
- decision: refresh only dedicated marker blocks inside handoff files
  reason: this keeps automation narrow and avoids clobbering operator-written notes
- decision: write a branch-local status board under
  `.context/current/branches/<branch>/status.md`
  reason: the next CLI session should have one local checkpoint that can be
  refreshed without committing repo state
- decision: keep durable commit history in `.context/history/commits.jsonl`
  with a generated markdown mirror
  reason: raw `git log` is not enough once workflow-specific context needs to
  survive across CLI sessions
- decision: keep commit enrichment as a separate helper from history sync
  reason: syncing and annotating have different failure modes, and CLI sessions
  need a safe way to update one row without rebuilding the flow manually
- decision: derive the recent summary from `.context/history/commits.jsonl`
  instead of direct `git log`
  reason: manual enrichment fields need to survive repeated regeneration
- decision: keep the one-command refresh helper as a thin composition layer over
  the existing scripts
  reason: operators need a fast resume/handoff command without introducing a
  second source of truth for workflow state
- decision: document a Windows hook-launch fallback instead of silently relying
  on `--no-verify`
  reason: the guard logic still matters, but Git for Windows can fail before
  the PowerShell guard script even starts
- decision: solve post-commit durable-history lag with a local-only
  `latest-commit.md` checkpoint instead of forcing versioned history files to
  self-reference the commit they live inside
  reason: tracked `commits.jsonl` and `latest-summary.md` cannot describe the
  commit that introduces them without recursive refresh churn
- decision: teach handoff templates and handoff README to point operators at
  `latest-commit.md` before versioned durable history when resuming
  reason: the local checkpoint is now the authoritative answer for true local
  `HEAD`, so new handoffs should make that recovery order explicit
- decision: auto-fill branch and repo-root placeholders during
  `codex-handoff-init.ps1`
  reason: a generated handoff should be directly usable in PowerShell or Claude
  CLI without a manual placeholder cleanup pass
- decision: normalize trailing newlines inside `codex-handoff-refresh.ps1`
  reason: refresh should not create a formatting-only diff that blocks
  workflow-only commits on `git diff --check`
- decision: graduate the local HEAD checkpoint into a dedicated
  `codex-commit-checkpoint.ps1` helper and have `codex-workflow-status.ps1`
  consume it
  reason: operators sometimes need the true local `HEAD` without rebuilding the
  full status board, and the shared path keeps status and handoffs aligned

## Risks / Open Questions

- `README.md` and `scripts/git-commit-safe.ps1` were already dirty before this
  workflow work. Do not treat them as part of this scope without re-checking.
- Review the workflow-only diff before staging anything, because several files
  now carry both prior and new modifications.
- The refresh helper defaults to the repo-level active handoff file, so
  task-specific handoffs should pass an explicit `-HandoffPath`.
- Durable history snapshots are still based on the last explicit refresh, so
  the committed `commits.jsonl`/`latest-summary.md` may lag newer commits until
  operators rerun the refresh flow, even though the local checkpoint now makes
  that lag visible.

## Next Steps

1. Decide whether review or plan templates also need the same local checkpoint
   cue, or whether keeping it handoff-plus-status-only is the right boundary.
2. Decide whether plan/review init scripts should auto-fill any environment
   placeholders, or whether that convenience should stay handoff-only.
3. Decide whether `codex-workflow-refresh.ps1` should surface the checkpoint
   helper as its own labeled step, or keep it implicit through status refresh.

## Git Snapshot

<!-- codex:handoff-git-status:start -->
```text
 M .claude-plugin/marketplace.json
 M .claude/handoff/README.md
 M .claude/handoff/TEMPLATE.md
 M .claude/handoff/repo-codex-flow-current.md
 M .claude/plan/repo-codex-flow-followups.md
 M .context/README.md
 M .context/prefs/workflow.md
 M .context/templates/handoff-template.md
 M AGENTS.md
 M CLAUDE.md
 M CODEX_DEVELOPMENT_FLOW.md
 M README.md
 M docs/runtime/OPERATOR-MANUAL.md
 M docs/runtime/README.md
 M financial-analysis/commands/wechat-push-draft.md
 M financial-analysis/commands/x-index.md
 M financial-analysis/skills/autoresearch-info-index/SKILL.md
 M financial-analysis/skills/autoresearch-info-index/examples/README.md
 M financial-analysis/skills/autoresearch-info-index/references/cases/x-post-first-response.md
 M financial-analysis/skills/autoresearch-info-index/scripts/agent_reach_bridge_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_brief_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_evidence_bundle.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_feedback_profiles.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_publish.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/article_style_learning.py
 M financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/launch_edge_remote_debug.cmd
 M financial-analysis/skills/autoresearch-info-index/scripts/news_index_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/wechat_draftbox_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/wechat_push_draft.py
 M financial-analysis/skills/autoresearch-info-index/scripts/x_index_runtime.py
 M financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py
 M financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
 M financial-analysis/skills/autoresearch-info-index/tests/test_article_workflow.py
 M financial-analysis/skills/autoresearch-info-index/tests/test_news_index.py
 M financial-analysis/skills/autoresearch-info-index/tests/test_wechat_draft_push.py
 M financial-analysis/skills/classic-case-router/references/x-post-evidence.md
 M scripts/codex-workflow-status.ps1
 M scripts/runtime/run-financial-headless.ps1
?? .claude/handoff/stock-analysis-thread-413-migration.md
?? .tmp-chrome-cookies.db
?? docs/ideation/2026-04-01-local-codex-capability-next-optimizations.md
?? docs/plans/2026-04-03-001-feat-opencli-source-adapter-plan.md
?? docs/plans/2026-04-04-001-feat-reddit-community-signal-adapter-plan.md
?? docs/plans/2026-04-04-002-feat-local-obsidian-kb-deployment-plan.md
?? docs/solutions/best-practices/x-window-first-session-reuse-2026-04-02.md
?? financial-analysis/commands/reddit-bridge.md
?? financial-analysis/skills/autoresearch-info-index/examples/article-workflow-style-profile-request.json
?? financial-analysis/skills/autoresearch-info-index/examples/fixtures/feedback-profile-english/
?? financial-analysis/skills/autoresearch-info-index/examples/fixtures/reddit-universal-scraper-sample/
?? financial-analysis/skills/autoresearch-info-index/examples/hot-topic-reddit-multi-post-request.json
?? financial-analysis/skills/autoresearch-info-index/examples/reddit-bridge-duplicate-comments-request.json
?? financial-analysis/skills/autoresearch-info-index/examples/reddit-bridge-export-root-request.json
?? financial-analysis/skills/autoresearch-info-index/examples/reddit-bridge-inline-comments-request.json
?? financial-analysis/skills/autoresearch-info-index/examples/reddit-bridge-low-signal-request.json
?? financial-analysis/skills/autoresearch-info-index/references/reddit-cluster-aliases.json
?? financial-analysis/skills/autoresearch-info-index/references/reddit-community-profiles.json
?? financial-analysis/skills/autoresearch-info-index/scripts/article_publish_regression_check.py
?? financial-analysis/skills/autoresearch-info-index/scripts/article_publish_regression_check_runtime.py
?? financial-analysis/skills/autoresearch-info-index/scripts/article_publish_reuse.py
?? financial-analysis/skills/autoresearch-info-index/scripts/article_publish_reuse_runtime.py
?? financial-analysis/skills/autoresearch-info-index/scripts/launch_edge_remote_debug_wechat.cmd
?? financial-analysis/skills/autoresearch-info-index/scripts/reddit_bridge.py
?? financial-analysis/skills/autoresearch-info-index/scripts/reddit_bridge_runtime.py
?? financial-analysis/skills/autoresearch-info-index/scripts/run_article_publish_acceptance.cmd
?? financial-analysis/skills/autoresearch-info-index/scripts/run_article_publish_regression_check.cmd
?? financial-analysis/skills/autoresearch-info-index/scripts/run_article_publish_reuse.cmd
?? financial-analysis/skills/autoresearch-info-index/scripts/run_reddit_bridge.cmd
?? financial-analysis/skills/autoresearch-info-index/scripts/wechat_browser_session_push.js
?? financial-analysis/skills/autoresearch-info-index/tests/fixtures/
?? financial-analysis/skills/autoresearch-info-index/tests/test_article_publish_canonical_snapshots.py
?? financial-analysis/skills/autoresearch-info-index/tests/test_article_workflow_canonical_snapshots.py
?? financial-analysis/skills/autoresearch-info-index/tests/test_reddit_bridge.py
?? obsidian-kb-local/
?? scripts/codex-commit-checkpoint.ps1
?? scripts/safe_automation_cleanup.py
```
<!-- codex:handoff-git-status:end -->

## Resume Commands

```powershell
Set-Location 'C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins'
git status --short
Get-Content .\CODEX_DEVELOPMENT_FLOW.md
Get-Content .\.claude\plan\repo-codex-flow-followups.md
Get-Content .\.claude\handoff\repo-codex-flow-current.md
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-context-show.ps1
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 10 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1
Get-Content .\.context\current\branches\main\latest-commit.md
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 5
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-enrich.ps1 -Commit 2f29ff3 -ContextId 'repo-codex-flow-followups' -Decisions 'why this changed' -Risk 'what could drift'
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 5
```

## References

- plan: `.claude/plan/repo-codex-flow-followups.md`
- review: `.context/current/reviews/workflow-review-smoke-2-review.md`
- related docs:
  - `CODEX_DEVELOPMENT_FLOW.md`
  - `.context/README.md`
  - `.context/prefs/workflow.md`
