# Examples Directory

This folder contains example inputs and generated outputs for both the
recency-first `news-index` flow and the phase 1 `autoresearch-info-index`
workflow.

Use it to understand two related paths:

1. `news-index`: build a one-shot current-state result, optionally refresh it,
   and inspect the generated markdown report
2. phase 1: bridge a retrieval result into a run record, evaluate it, and
   collect evaluated outputs into one report

## Recency-First News-Index Outputs

- `news-index-crisis-request.json`
- `news-index-crisis-result.json`
- `news-index-crisis-report.md`
- `news-index-refresh-update.json`
- `news-index-crisis-refreshed.json`
- `news-index-crisis-refreshed.md`
- `news-index-crisis-run-record.json`
- `news-index-crisis-evaluated.json`
- `news-index-phase1-report.md`

These are the default generated artifacts for the single-sample recency-first
demo chain.

## Realistic Offline Fixture

- `news-index-realistic-offline-request.json`
- `news-index-realistic-offline-refresh.json`
- `fixtures/`

This fixture set is still fully deterministic and offline, but it uses more
realistic source domains, source families, conflict patterns, and local visual
artifacts than the smaller baseline demo request. Use it when you want a smoke
run that looks closer to a real geopolitical monitoring case without depending
on live web access.

Recommended smoke commands:

```text
scripts\run_news_index_realistic_demo.cmd
scripts\run_phase1_realistic_demo.cmd
scripts\run_article_workflow_realistic_demo.cmd
```

## Last30Days Bridge Fixture

- `last30days-bridge-input.json`

This request is a deterministic offline sample that treats `last30days` as a
separate upstream discovery layer and then bridges the imported findings into
`news-index`.

Recommended smoke command:

```text
scripts\run_last30days_bridge_demo.cmd
```

## Generated Scaffold Outputs

- `batch-news-index-results/`
- `single-run-records/`
- `single-evaluated/`
- `batch-run-records/`
- `batch-evaluated/`
- `phase1-run-report.md`
- `phase1-batch-run-report.md`

These are the current scripted outputs produced by the fixed-sample phase 1
batch and single-item helper commands.

## Curated / Legacy Examples

- `trump-ceasefire-run-record.json`
- `trump-ceasefire-evaluated.json`
- `news-001-run-record.json`
- `news-001-evaluated.json`

These top-level files are standalone examples. They are useful for inspection,
but they are not the default outputs of the current single-demo script.

## Notes

- `sample-pool/` is the stable benchmark set for the evaluator path.
- `run_phase1_batch_demo.cmd` now pushes those fixed samples through the new
  recency-first retrieval front half before evaluation.
- Files ending in `-evaluated.json` are generated outputs.
- The batch directories are meant to stay small and reproducible for phase 1.
- When hard checks fail, treat evidence-confidence metrics as diagnostic context,
  not as approval to keep the candidate.
