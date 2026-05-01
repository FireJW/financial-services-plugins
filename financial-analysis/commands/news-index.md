---
description: Build a one-shot recency-first current-state report for a fast-moving topic
argument-hint: "[request-json]"
---

# News Index Command

Use this command when the user wants a single current-state note built from a
recency-first retrieval pass.

The output should separate:

- `core_verdict`
- `live_tape`
- `confirmed / not confirmed / inference only`
- `latest signals first`
- `conflict matrix`
- `10m / 1h / 6h / 24h` freshness windows

Default behavior:

1. build a `retrieval_request`
2. discover and normalize source candidates
3. rank by source tier, recency, corroboration, contradiction, and staleness
4. merge duplicates and build a `claim_ledger`
5. emit a `verdict_output` plus `retrieval_run_report`

If the topic is geopolitical, military, sanctions, negotiations, or energy
shock related, prefer `mode=crisis`.

Preset option:

- `preset=energy-war`
  - automatically runs through the `crisis` path
  - adds an energy-war watchlist for `Brent`, `WTI`, `TTF`, `JKM-style LNG`,
    `Henry Hub`, tanker rates, prompt spreads, reserve releases, OPEC spare
    capacity, Qatar LNG flows, and Hormuz flows
  - expands the default watch items toward physical disruption vs risk premium
  - keeps the existing ranking logic; it does not bypass evidence checks
  - preserves user-supplied `benchmark_watchlist`, `preset_watch_items`, and
    `market_relevance` when you provide them, and only backfills defaults when
    they are missing

The structured result currently carries:

- `request`
- `observations`
- `claim_ledger`
- `verdict_output`
- `retrieval_run_report`
- `retrieval_quality`
- `report_markdown`

With `preset=energy-war`, the result also carries:

- `verdict_output.energy_war_preset`
- `retrieval_run_report.benchmark_watchlist`

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index_demo.cmd`

TrendRadar direct input:

- include `trendradar.result` or `trendradar.result_path` in the `news-index`
  request to import TrendRadar MCP/API items as `origin=trendradar`,
  `channel=shadow`, `access_mode=local_mcp` candidates
- this is not a default fetch; the request must explicitly provide the
  TrendRadar payload or result path
- use `trendradar-bridge` when you want a standalone adapter report before
  entering the normal `news-index` result builder

For the local helper path, pass a `retrieval_request` JSON file. The helper
prints JSON to stdout by default and writes the human-readable Markdown report
only when `--markdown-output` is provided.
