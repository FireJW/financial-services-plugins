---
description: Run the weekly institutional-content workflow: X watchlist update first, then content discovery summarization
argument-hint: "[request-json]"
---

# Market Intelligence Weekly

Use this as the default weekly operating entrypoint when the goal is:

1. update the watched X institutional-content sources
2. import only new high-signal posts into Obsidian
3. summarize the current week's content findings into a compact discovery layer
4. optionally run a paused similar-author sidecar without changing the main
  watchlist logic
5. optionally run a cross-market X-style mapping sidecar that converts global
   AI / semi / supply-chain commentary into A-share advisory baskets

Local helper:

- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_market_intelligence_weekly.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_market_intelligence_weekly_live.cmd`
- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_market_intelligence_weekly_from_source.cmd`

Recommended templates:

- `financial-analysis\\skills\\autoresearch-info-index\\examples\\market-intelligence-weekly.template.json`
- `financial-analysis\\skills\\autoresearch-info-index\\examples\\market-intelligence-weekly-from-source.template.json`

Operator note:

- use the live template for a full fresh weekly run
- use the `from-source` template when you already have a good saved X result
  and only want to rerun the import + content-discovery leg
- `run_similar_author_discovery` is currently `false` by default
- only turn it on when you explicitly want a sidecar candidate scan, not as the
  default weekly path
- `run_cross_market_style_mapping` is also optional and should be used for
  handles such as `aleabitoreddit` / `jukan05` where the value is in
  cross-market logic and ecosystem mapping, not direct picks

Scheduler note:

- see `docs/runtime/market-intelligence-weekly-scheduler-playbook.md`
  for the minimal Windows Task Scheduler setup
