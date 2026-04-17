---
description: Discover high-value report summaries, chart threads, and deep analysis content across X and Reddit
argument-hint: "[request-json]"
---

# Market Intelligence Content Discovery

Use this when the goal is to find the content itself rather than the person:

- sell-side report summaries
- chart/deck threads
- call takeaways
- deep long-form analysis

This command treats X and Reddit as content surfaces, not creator-ranking surfaces.

Current default:

- `X` is the primary surface
- `Reddit` is a secondary supplement only
- if Reddit strict queries do not yield A-share / institution-relevant material,
  keep Reddit out of the main loop instead of forcing weak matches

Current non-goal:

- this command is not for expanding an author roster
- use `x-similar-author-discovery` only as a paused / optional exploration
  layer, not as the default next step

Local helper:

- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_market_intelligence_content_discovery.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Recommended reading:

- `docs/runtime/market-intelligence-content-discovery-playbook.md`
