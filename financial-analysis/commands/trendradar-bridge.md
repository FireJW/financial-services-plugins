---
description: Bridge TrendRadar MCP/API results into news-index as shadow discovery signals
argument-hint: "[request-json]"
---

# TrendRadar Bridge Command

Use this command when TrendRadar has already collected hot-list, RSS, or MCP
query results and you want those items to enter the repo-native `news-index`
flow as source-traceable candidates.

The same payload can also be passed directly to:

- `news-index`, using `trendradar.result` or `trendradar.result_path`
- `hot-topics`, using `sources=["trendradar"]` plus `trendradar.result` or
  `trendradar.result_path`

This command is an upstream discovery adapter. It does not replace:

- `news-index` claim ledger, freshness windows, or confirmation logic
- `x-index` signed-session X collection
- `opencli-index` authenticated dynamic-page capture
- `hot-topics` ranking policy

Default behavior:

1. load a TrendRadar MCP/API payload from `trendradar.result` or
   `trendradar.result_path`
2. flatten common result shapes such as `data.items`, `results`, `news`,
   `articles`, and `trending_topics`
3. normalize each item into a `news-index` candidate with
   `origin=trendradar`, `channel=shadow`, and `access_mode=local_mcp`
4. preserve TrendRadar rank, heat, score, keyword, platform, and MCP metadata
   under `raw_metadata.trendradar`
5. run the normal `news-index` result builder

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_trendradar_bridge.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Template:

- `financial-analysis\skills\autoresearch-info-index\examples\trendradar-bridge-request.template.json`

Operator note:

- Keep TrendRadar as a signal source. Treat imported items as `shadow` evidence
  until stronger native or primary sources confirm the claim.
