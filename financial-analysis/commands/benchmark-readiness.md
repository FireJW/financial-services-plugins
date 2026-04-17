---
description: Audit whether the checked-in benchmark refresh request is actually ready for safe daily execution
argument-hint: "[benchmark-refresh-request-json]"
---

# Benchmark Readiness Command

Use this before turning on a 24h benchmark refresh loop.

It audits the refresh request and the files it points to, then tells you:

1. whether the current setup is actually ready for daily execution
2. which reviewed cases are missing `fetch_url`
3. whether discovery has any enabled seeds to crawl
4. whether enabled seeds are incomplete or too loose
5. what to fix next before automation

Local helper:

- `financial-analysis\skills\decision-journal-publishing\scripts\run_benchmark_readiness.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Recommended first run:

- `financial-analysis\skills\decision-journal-publishing\scripts\run_benchmark_readiness.cmd "financial-analysis\skills\decision-journal-publishing\cases\benchmark-refresh-daily-request.json"`

Readiness rules:

1. if reviewed refresh is enabled and `allow_reference_url_fallback=false`, reviewed cases need explicit `fetch_url`
2. if discovery is enabled, the seeds file needs enabled sources with `seed_url`
3. enabled seeds should have include/exclude filters so the candidate inbox does not get flooded
4. warnings do not block execution, but blockers mean daily automation should stay paused
