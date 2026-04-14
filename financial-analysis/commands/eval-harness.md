---
description: Evaluate an existing workflow result with a light cross-workflow scorecard
argument-hint: "[request-json]"
---

# Eval Harness Command

Use this command when you want one lightweight evaluation pass over an existing
workflow result without rerunning the workflow itself.

Currently supported targets:

- `x-index`
- `reddit-bridge`
- `hot-topics`
- `article-workflow`
- `macro-note-workflow`
- `article-publish`
- `article-publish-regression-check`
- `article-publish-reuse`
- `article-batch`
- `article-auto-queue`
- `wechat-draft-push`
- `wechat-push-readiness`
- `agent-reach-bridge`
- `opencli-index`
- `fieldtheory-index`

What it does:

1. loads an existing result JSON
2. detects the workflow kind
3. applies workflow-specific hard checks and a small scorecard
4. emits JSON plus an optional markdown report

This is not a replacement for workflow-specific acceptance or regression
checks. It is the first shared evaluation layer across multiple workflow
surfaces.

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_eval_harness.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Template:

- `financial-analysis\skills\autoresearch-info-index\examples\eval-harness-request.template.json`
