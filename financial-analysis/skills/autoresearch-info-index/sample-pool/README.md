# Phase 1 Information Index Sample Pool

Use this folder for the first fixed benchmark set for the `info-index` loop.

The goal is not to mirror the live news cycle. The goal is to keep a small,
stable set of recurring message-evaluation problems so different prompt,
checklist, and scoring changes can be compared fairly.

## Target Size

- 10 to 20 items

Phase 1 starts with 5 fixed items so the batch loop can run end to end before
the pool is expanded.

## Selection Rules

- each item should represent a repeatable message-indexing problem
- each item should include an absolute analysis date
- each item should include a small but stable source pack
- each item should force the workflow to separate confirmed facts from inference
- each item should include a target source-strength and confidence reference
- keep the output shape stable enough to compare runs fairly

## Suggested Layout

```text
sample-pool/
+-- README.md
+-- sample-index.md
+-- items/
    +-- item-template.json
    +-- news-001.json
    +-- news-002.json
```

## Core Fields

Every sample should include:

- `item_id`
- `title`
- `topic`
- `analysis_date`
- `claim_to_evaluate`
- `baseline_goal`
- `required_output_sections`
- `source_pack`
- `credibility_reference`
- `rollback`
- `notes`

## Credibility Reference

Each sample includes a `credibility_reference` block so later evaluators can
score not only structure, but also how well the workflow expresses confidence.

Use these fields:

- `source_strength`
  One of `high`, `medium-high`, `medium`, `mixed`, `low`
- `source_agreement`
  One of `aligned`, `mostly-aligned`, `mixed`, `conflicted`
- `confidence_interval_pct`
  A two-number range such as `[35, 55]`
- `expected_judgment`
  A one-line summary of the right confidence posture

This is not a truth oracle. It is the benchmark expectation for how the indexed
note should frame reliability.

## Workflow

1. Add one item record per benchmark sample.
2. Keep sample IDs stable over time.
3. Do not swap sample definitions mid-benchmark.
4. If a sample becomes outdated, replace it only in a new sample-set version.
5. Treat this as a fixed benchmark pool, not a live news feed.
