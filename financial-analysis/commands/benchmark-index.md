---
description: Index and review WeChat / Toutiao benchmark article cases for acquisition fit vs commercial fit
argument-hint: "[benchmark-index-request-json]"
---

# Benchmark Index Command

Use this command when you already have a candidate pool of benchmark articles,
ranklist picks, or manually collected cases and want a structured review instead
of vague inspiration.

Input modes:

1. direct request with `cases[]`
2. library-backed request with `library_path`

What it does:

1. loads a benchmark-case request JSON
2. normalizes WeChat and Toutiao case metadata
3. filters around a minimum read band such as `5w+` or `10w+`
4. scores each case on:
   - acquisition success
   - commercial fit
   - decision density
   - publicness
   - paid-linkage strength
5. labels each case as:
   - `acquisition`
   - `commercial-fit`
   - `mixed`
   - `reject`
6. outputs a review-ready report with:
   - what to copy
   - what to avoid
   - strategy implications

This is the benchmark equivalent of `news-index`:

- one structured request
- one normalized result JSON
- one markdown report

Local helper:

- `financial-analysis\skills\decision-journal-publishing\scripts\run_benchmark_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when you want:

- a reusable cases library reviewed the same way every week
- `5W+` or `10W+` cases separated from high-commercial-fit exceptions
- benchmark review that matches a pro-first finance account
- a reusable benchmark-index file you can update every week

Request toggle:

- keep `strict_read_gate=false` to preserve below-threshold but high-commercial-fit exceptions
- set `strict_read_gate=true` when you want a pure `10W+` sample pool only

Recommended workflow:

1. store cases in `cases/benchmark-case-library.json`
2. point a small request file at that library with `library_path`
3. run `benchmark-index`
4. update the cases library every week instead of rebuilding `cases[]` by hand
