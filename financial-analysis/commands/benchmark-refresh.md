---
description: Refresh reviewed benchmark cases, append machine observations, discover new candidates, and rerun the reviewed benchmark snapshot
argument-hint: "[benchmark-refresh-request-json]"
---

# Benchmark Refresh Command

Use this when you want a durable benchmark maintenance loop instead of manually
rebuilding `cases[]`.

This command now maintains three separate artifacts:

1. `cases/benchmark-case-library.json` for reviewed benchmark cases
2. `cases/benchmark-case-candidates.json` for auto-discovered candidate cases
3. `cases/benchmark-case-observations.jsonl` for append-only machine observations
4. `cases/benchmark-refresh-seeds.json` for discovery source definitions

What it does:

1. refreshes machine state for reviewed and candidate cases
2. appends every refresh outcome into JSONL history, including `skipped` and `error`
3. discovers new candidate links from `benchmark-refresh-seeds.json`
4. writes only successful discoveries into the candidate library, not the reviewed library
5. reruns `benchmark-index` against the reviewed library only

Important defaults:

1. `allow_reference_url_fallback=false`
   This prevents the refresh job from treating secondary commentary pages as the
   canonical fetch target. Add `fetch_url` per reviewed case when you want true
   article refreshes.
2. `auto_add_new_cases=true`
   New successful discoveries are added as `curation_status="candidate"` in the
   candidate library, never as reviewed benchmarks.
3. the reviewed library stays curated, but its machine state is refreshed in place
4. the reviewed library's `machine_state` is the latest readable snapshot; the
   JSONL log is the append-only audit trail
5. when the CLI request omits `analysis_time`, the wrapper injects the current
   local timestamp before calling the strict runtime validator
6. scheduling should be external, for example Codex automation or Windows Task Scheduler

Local helper:

- `financial-analysis\skills\decision-journal-publishing\scripts\run_benchmark_library_refresh.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Checked-in requests:

1. `cases/benchmark-refresh-daily-request.json` for the real cases directory
2. `examples/benchmark-refresh-demo-request.json` for the local fixture demo
