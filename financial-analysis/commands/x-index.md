---
description: Index X / Twitter posts and threads into a reusable structured evidence pack
argument-hint: "[request-json]"
---

# X Index

## Dual-Track Hints

- start from `routing-index.md`
- use `Complex` when the request needs batch extraction, cross-platform verification, or article-pipeline reuse
- check `financial-services-docs/docs/runtime/codex-dual-track/delivery-contract.md` before finalizing the answer
- search `obsidian-kb-v2` for `#recurring/x-evidence` before rebuilding a familiar workflow from scratch

Use this command when the user wants one runnable X / Twitter collection flow that:

1. fetches posts or threads with a signed session or reusable browser state
2. normalizes post text, timestamps, authors, media, and source links
3. emits a structured `x-index` result for downstream workflows
4. keeps X collection on the native repository path instead of ad hoc scraping

Good fits:

- "collect the evidence from this X thread"
- "turn these X posts into a reusable evidence pack"
- "capture the latest posts from these watched authors"
- "prepare X evidence for article, completion-check, or operator-summary workflows"

Native skill:

- `financial-analysis/skills/autoresearch-info-index/SKILL.md`

Local helper:

- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\x_index.py "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Default output:

- one structured `x-index-result.json`
- one markdown report
- normalized post records with timestamps, authors, and evidence links

Guardrails:

- `x-index` is the repository-native X / Twitter route
- prefer `remote_debugging` on Windows when a signed browser session is available
- `browser_session.strategy = "codex_iab"` records that an operator-side Codex
  Browser Use capture is required; it does not pretend the Python runtime can
  launch or own the in-app browser
- reuse recent successful `x-index` results when they are still relevant before
  recollecting the same evidence
- do not start with public X page scraping when the native workflow can reuse a
  signed session
- when a downstream workflow only consumes curated handles, URLs, or summaries,
  do not describe that as a live native X run

Priority order:

1. live native `x-index`
2. reused relevant `x-index` results
3. public fallback only after native signed-session paths are unavailable
