---
description: Build one operator-facing summary that rolls up completion, evaluation, publication gate, and push readiness signals
argument-hint: "[request-json]"
---

# Operator Summary Command

Use this command when you do not want to flip through 4 to 5 different reports
to decide whether a workflow result is actually safe to move forward.

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

1. loads an existing workflow result
2. reuses embedded or companion `completion-check` artifacts when available
3. reuses embedded or companion `eval-harness` artifacts when available, or
   runs a lightweight inline fallback
4. surfaces `workflow_publication_gate`, `automatic_acceptance`,
   `push_readiness`, `iterative_retrieval`, and `bridge_summary` surfaces when
   applicable
5. emits one JSON plus an optional markdown summary page for operators

Notes:

- `hot-topics` can now emit companion
  `hot-topic-discovery-completion-check.*` and
  `hot-topic-discovery-operator-summary.*` artifacts when the runtime can infer
  an input artifact directory
- `article-publish-regression-check` is treated as its own workflow kind, but
  its result is still summarized through the shared `automatic_acceptance`
  section so operators do not lose the publish-regression decision context
- `wechat-draft-push` can now emit companion
  `wechat-draft-push-completion-check.*` and
  `wechat-draft-push-operator-summary.*` artifacts when the runtime can infer
  the input artifact directory
- discovery / bridge targets such as `reddit-bridge`, `agent-reach-bridge`,
  `opencli-index`, and `fieldtheory-index` now summarize through a shared
  `bridge_summary` block
- publication-gate sections are only shown for publish-like workflows; bridge
  and lookup commands no longer emit a meaningless
  `publication_readiness: unknown` banner

This command is the operator-facing aggregation layer above:

- `completion-check`
- `eval-harness`
- `workflow_publication_gate`
- `automatic_acceptance`
- `wechat-push-readiness`

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_operator_summary.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Current automatic companions:

- `x-index` now writes `x-index-operator-summary.json` and
  `x-index-operator-summary.md`
- `reddit-bridge` now writes `reddit-bridge-operator-summary.json` and
  `reddit-bridge-operator-summary.md`
- `agent-reach-bridge` now writes `agent-reach-bridge-operator-summary.json`
  and `agent-reach-bridge-operator-summary.md`
- `opencli-index` now writes `opencli-bridge-operator-summary.json` and
  `opencli-bridge-operator-summary.md`
- `fieldtheory-index` now writes `fieldtheory-index-operator-summary.json` and
  `fieldtheory-index-operator-summary.md`
- `hot-topics` now writes `hot-topic-discovery-operator-summary.json` and
  `hot-topic-discovery-operator-summary.md`

Template:

- `financial-analysis\skills\autoresearch-info-index\examples\operator-summary-request.template.json`
