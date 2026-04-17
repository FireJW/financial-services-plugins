---
description: Refresh only the recent windows of an existing news index result
argument-hint: "[existing-result-json] [refresh-request-json]"
---

# News Refresh Command

Use this command when the user already has a prior `news-index` result and only
needs the newest evidence windows updated.

Refresh mode should:

1. keep the prior topic, mode, and historical context
2. append only new source observations
3. rerank the newest evidence
4. update `latest_signals`, freshness windows, and the verdict
5. keep older evidence older than 24 hours as `background` unless reactivated

This is lighter than rebuilding a full historical pack from scratch.

The refresh input is a second `retrieval_request`-style JSON that is applied on
top of the prior `news-index` result JSON. Topic and mode are inherited from
the prior result unless the refresh payload overrides them explicitly.

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_news_refresh.cmd "<existing-result.json>" "<refresh-request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\skills\autoresearch-info-index\scripts\run_news_refresh_demo.cmd`

For the local helper path, pass the existing `news-index` result JSON plus a
refresh request JSON. The helper prints JSON to stdout by default and writes
the Markdown report only when `--markdown-output` is provided.
