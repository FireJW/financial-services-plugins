---
description: Run the end-to-end macro note workflow from indexed evidence or a fresh index request
argument-hint: "[request-json]"
---

# Macro Note Workflow Command

Use this command when the user wants one runnable flow that:

1. takes an existing `news-index` or `x-index` result, or a fresh request
2. builds a structured analysis brief from that evidence
3. emits a macro-note result with `one_line_judgment`, `benchmark_map`,
   `bias_table`, `horizon_table`, and `what_changes_the_view`
4. writes staged outputs so the run can be replayed without rebuilding by hand

The workflow writes staged outputs for:

- the source result
- the source report
- the analysis brief result
- the analysis brief report
- the macro note result
- the macro note report
- the workflow summary report

Accepted inputs:

- an existing indexed result JSON
- an `x-index` request JSON
- a `news-index` request JSON

Recommended use:

- use this instead of `article-workflow` when the end product is a macro note,
  not a publishable article with images and revision passes
- use `preset=energy-war` on the `news-index` request when the macro note is
  about oil, gas, Hormuz, Qatar LNG, shipping, or war-driven energy shocks

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_macro_note_workflow.cmd "<request.json>" [--output <result.json>] [--markdown-output <macro-note.md>] [--workflow-markdown-output <workflow-report.md>] [--output-dir <dir>]`

Notes:

- `analysis_time` is optional on fresh `news-index` and `x-index` requests; if
  omitted, the workflow defaults it the same way as the source stage does
- when the workflow wraps a fresh `x-index` request, it keeps the source-stage
  artifacts under the macro workflow output tree by default
- if you need a separate X source directory, pass `x_output_dir` or
  `source_output_dir` in the request JSON
