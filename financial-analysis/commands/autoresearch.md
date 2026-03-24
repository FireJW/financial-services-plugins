---
description: Run the autoresearch improvement loop for a repeatable task
argument-hint: "[task type] [goal]"
---

# Autoresearch Loop Command

Use the `autoresearch-loop` skill when the user wants Codex to get better at a
repeatable workflow over time instead of just finishing a one-off task.

Route by task type:

- If the user is improving bug fixing, debugging, or regression handling, use
  the **code-fix** profile.
- If the user is improving document cleanup, restructuring, or consolidation,
  use the **doc-workflow** profile.
- If the user is improving equity or stock analysis output quality, use the
  **stock-template** profile.
- If the user is improving fast-moving news indexing, signal extraction, or
  source-traceable event notes, use the **info-index** profile.

Before iterating:

1. Define the task boundary.
2. Define the scorecard and hard failure conditions.
3. Define how a failed attempt will be rolled back.
4. Use absolute dates for any time-sensitive market or company data.

For local phase 1 `code-fix` work in this repo:

- use `financial-analysis\skills\autoresearch-code-fix\scripts\python-local.cmd`
  as the workspace-local Python entrypoint
- use `financial-analysis\skills\autoresearch-code-fix\scripts\run_phase1_demo.cmd`
  as the single-sample demo entry for the local phase 1 path
- use
  `financial-analysis\skills\autoresearch-code-fix\scripts\run_phase1_batch_demo.cmd`
  as the full-sample demo entry for the local batch phase 1 path
- use `financial-analysis\skills\autoresearch-code-fix\scripts\run_init_run_record.cmd`
  to turn one bug sample into a starter run record
- use
  `financial-analysis\skills\autoresearch-code-fix\scripts\run_init_all_run_records.cmd`
  to generate starter run records for the full fixed bug set in one pass
- use `financial-analysis\skills\autoresearch-code-fix\scripts\run_evaluate_code_fix.cmd`
  to score one run record
- use
  `financial-analysis\skills\autoresearch-code-fix\scripts\run_evaluate_all_run_records.cmd`
  to score a full run-record directory into a separate evaluated output
  directory
- use `financial-analysis\skills\autoresearch-code-fix\scripts\build_run_report.py`
  to summarize evaluated result JSON files into one Markdown report
- use `financial-analysis\skills\autoresearch-code-fix\sample-pool\`
  as the fixed bug sample set for phase 1

Recommended local phase 1 flow:

1. choose whether you want a single-sample walkthrough or a full-batch walkthrough
2. use `run_phase1_demo.cmd` for the single-sample path, or
   `run_phase1_batch_demo.cmd` for the full-sample path
3. otherwise choose whether to generate one starter run record or a full batch
4. use `run_init_run_record.cmd` for one bug, or
   `run_init_all_run_records.cmd` for the full sample set
5. fill in real baseline and candidate scores
6. evaluate one run record with `run_evaluate_code_fix.cmd`, or run batch
   evaluation into a dedicated evaluated output directory
7. point `build_run_report.py` at that evaluated results directory to produce
   the Markdown summary

For local phase 1 `info-index` work in this repo:

- use `financial-analysis\skills\autoresearch-info-index\scripts\python-local.cmd`
  as the workspace-local Python entrypoint
- use `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index.cmd`
  to build the new recency-first retrieval front half for one topic
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index_demo.cmd`
  to regenerate the bundled one-shot request/result/report example
- use `financial-analysis\skills\autoresearch-info-index\scripts\run_news_refresh.cmd`
  to refresh only the newest evidence windows without rebuilding all history;
  it expects an existing result JSON plus a refresh request JSON
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_news_refresh_demo.cmd`
  to regenerate the bundled refresh example result/report
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index_to_run_record.cmd`
  to bridge a retrieval result into the existing phase 1 run-record format
- use `financial-analysis\skills\autoresearch-info-index\scripts\run_phase1_demo.cmd`
  as the single-sample demo entry for the local phase 1 path
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_phase1_batch_demo.cmd`
  as the fixed-sample batch demo entry; it now upgrades the benchmark items
  through `news-index -> run-record -> evaluate`
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_validate_sample_pool.cmd`
  to validate the fixed benchmark sample set
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_init_run_record.cmd`
  to turn one benchmark item into a starter run record
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_init_all_run_records.cmd`
  to generate starter run records for the full benchmark set in one pass
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_evaluate_info_index.cmd`
  to score one run record
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_evaluate_all_run_records.cmd`
  to score a full run-record directory into a separate evaluated output
  directory
- use
  `financial-analysis\skills\autoresearch-info-index\scripts\run_build_run_report.cmd`
  to summarize evaluated result JSON files into one Markdown report
- use `financial-analysis\skills\autoresearch-info-index\sample-pool\`
  as the fixed benchmark sample set for phase 1

Recommended local phase 1 info-index flow:

1. use `run_news_index_demo.cmd` if you want to regenerate the bundled example,
   or `run_news_index.cmd` for your own request file
2. use `run_news_refresh_demo.cmd` if you want to regenerate the bundled
   refresh example, or `run_news_refresh.cmd <existing-result> <refresh-request>`
   when only the most recent windows need updating for your own prior result
3. bridge the retrieval result into the phase 1 evaluator input with
   `run_news_index_to_run_record.cmd`
4. otherwise choose whether to generate one starter run record or a full batch
5. use `run_init_run_record.cmd` for one fixed benchmark item, or
   `run_init_all_run_records.cmd` for the full sample set
6. fill in real hard checks and baseline/candidate scores
7. evaluate one run record with `run_evaluate_info_index.cmd`, or run batch
   evaluation into a dedicated evaluated output directory
8. use `run_phase1_batch_demo.cmd` when you want the fixed benchmark sample-pool
   workflow pushed through the recency-first front half rather than only the
   one-shot/refresh demo
8. point `run_build_run_report.cmd` at that evaluated results directory to produce
   the Markdown summary

Then load `autoresearch-loop` and follow its workflow.
