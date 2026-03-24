---
description: Index and review WeChat / Toutiao benchmark article cases for acquisition fit vs commercial fit
argument-hint: "[benchmark-index-request-json]"
---

# Benchmark Index Command

Use this when you already have a benchmark case pool and need a strict review
layer instead of vague inspiration.

Input modes:

1. direct request with `cases[]`
2. library-backed request with `library_path`

What it does:

1. loads a benchmark case library or direct `cases[]`
2. scores each case on acquisition fit, commercial fit, and decision density
3. defaults to `include_curation_statuses=["reviewed"]`
4. keeps unreviewed candidates out of reviewed benchmark counts
5. separates threshold-qualified reviewed cases from below-threshold exceptions
6. outputs JSON plus a markdown report

Key rule:

- `candidate` cases stay out of the default reviewed benchmark pool unless you
  explicitly override `include_curation_statuses`

Local helper:

- `financial-analysis\skills\decision-journal-publishing\scripts\run_benchmark_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Recommended workflow:

1. keep reviewed cases in `cases/benchmark-case-library.json`
2. keep auto-discovered candidates in `cases/benchmark-case-candidates.json`
3. keep machine refreshes in `cases/benchmark-case-observations.jsonl`
4. point `benchmark-index` at the reviewed library for the canonical benchmark view
5. override `include_curation_statuses=["candidate"]` only when you want triage, not the
   canonical benchmark snapshot
