---
description: Run a completion check before treating a workflow result as truly done
argument-hint: "[request-json]"
---

# Completion Check Command

Use this command when you want a final "verification-before-completion" pass on
an existing workflow result before you treat it as done.

Currently supported targets:

- `x-index`
- `hot-topics`
- `reddit-bridge`
- `agent-reach-bridge`
- `opencli-index`
- `fieldtheory-index`
- `article-workflow`
- `macro-note-workflow`
- `article-publish`
- `article-publish-regression-check`
- `article-publish-reuse`
- `article-batch`
- `article-auto-queue`
- `wechat-draft-push`
- `wechat-push-readiness`

What it does:

1. loads an existing result JSON
2. checks whether the minimum completion conditions are satisfied
3. returns `ready`, `warning`, or `blocked`
4. emits JSON plus an optional markdown report

Bridge and discovery defaults:

- `x-index`
  - blocks when no kept X posts or no bridged observations survive into
    `news-index`
  - warns when the browser session is degraded / failed or when search
    discovery still contains blocked candidates
- `reddit-bridge`
  - blocks when `import_summary`, `retrieval_result`, or bridged observations
    are missing
  - warns when `operator_review_queue` is still non-empty
- `agent-reach-bridge`
  - blocks when no channel succeeded, or no bridged observations were imported
  - warns when one or more channels failed but other channels still succeeded
- `opencli-index`
  - blocks when import or retrieval output is missing
  - warns when the optional runner was executed but ended in a non-`ok` state
- `fieldtheory-index`
  - requires a valid `fieldtheory_summary`
  - treats `no matches` as a warning, not a hard block, because the lookup may
    still be a useful negative check

This command is intentionally narrower than `eval-harness`:

- `eval-harness` asks "how strong is this result overall?"
- `completion-check` asks "is this done enough to proceed?"

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_completion_check.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Current automatic companions:

- `x-index` now writes `x-index-completion-check.json` and
  `x-index-completion-check.md`
- `hot-topics` now writes `hot-topic-discovery-completion-check.json` and
  `hot-topic-discovery-completion-check.md` when the runtime can infer an input
  artifact directory
- `reddit-bridge` now writes `reddit-bridge-completion-check.json` and
  `reddit-bridge-completion-check.md`
- `agent-reach-bridge` now writes
  `agent-reach-bridge-completion-check.json` and
  `agent-reach-bridge-completion-check.md`
- `opencli-index` now writes `opencli-bridge-completion-check.json` and
  `opencli-bridge-completion-check.md`
- `fieldtheory-index` now writes `fieldtheory-index-completion-check.json` and
  `fieldtheory-index-completion-check.md`
- `article-workflow` now writes `workflow-completion-check.json` and
  `workflow-completion-check.md`
- `article-publish` now writes `article-publish-completion-check.json` and
  `article-publish-completion-check.md`
- `article-publish-regression-check` now writes
  `publish-regression-completion-check.json` and
  `publish-regression-completion-check.md`
- `wechat-draft-push` writes `wechat-draft-push-completion-check.json` and
  `wechat-draft-push-completion-check.md` when the runtime can infer an input
  artifact directory
- `wechat-push-readiness` writes `wechat-push-readiness-completion-check.json`
  and `wechat-push-readiness-completion-check.md` when the runtime can infer an
  input artifact directory

Template:

- `financial-analysis\skills\autoresearch-info-index\examples\completion-check-request.template.json`
