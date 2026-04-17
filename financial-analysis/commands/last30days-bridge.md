---
description: Import a last30days-style result as upstream discovery and bridge it into news-index
argument-hint: "[request-json]"
---

# Last30Days Bridge Command

Use this command when you want to treat `last30days` as a separate discovery
layer, then feed selected findings into the current recency-first workflow
without replacing the existing fact firewall.

This command should:

1. read a `last30days`-style result or a normalized bridge request
2. convert supported findings into `news-index` candidates
3. import them as `shadow` by default
4. run `news-index` on top of that imported candidate set
5. return both the import summary and the bridged `retrieval_result`

Default expectations:

- imported findings stay `shadow` or `background` by default
- imported findings keep `origin=last30days`
- imported findings do not raise the main conclusion by themselves
- stronger confirmation still has to happen inside the current workflow

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_last30days_bridge.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\skills\autoresearch-info-index\scripts\run_last30days_bridge_demo.cmd`

Use this when you want broader discovery breadth from `last30days`, but still
want `news-index`, `article-brief`, `article-draft`, and `article-revise` to
remain the authoritative downstream pipeline.
