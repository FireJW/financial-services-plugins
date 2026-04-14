---
name: x-stock-picker-style
description: Learn how a specific X user picks stocks by turning signed-session X evidence into a reusable source board, recommendation ledger, and later style card.
---

# X Stock Picker Style

Use this skill when the user wants to:

- learn an X user's stock-picking logic
- audit whether a social account has real edge
- convert X posts into a structured recommendation study
- reuse the learned style as an advisory overlay for shortlist work
- paste an X profile URL and have the workflow infer the handle directly

## Default Route

1. start from `x-index` or an already captured signed-session X artifact
2. normalize into `source_board`
3. later units can extract recommendation events, score outcomes, and build a
   `style_card`

## Current v1 Scope

This initial implementation focuses on:

- request normalization
- source board building
- bounded recommendation event extraction
- preliminary style-card distillation from event patterns
- advisory overlay export
- explicit `named_pick_hints` export
- advisory `basket_hint` export
- optional ticker-resolution and latest-close replay calibration
- stable output contract
- fixture-first tests

Current boundary:

- `month_end_shortlist` can now consume either:
  - `overlay_pack` directly
  - or a saved batch result via `x_style_batch_result_path`
- this skill still does not turn X content into a hard-filter source
- full market-wide scoring still depends on the downstream shortlist workflow
  rather than this skill alone

Operator convenience:

- the request can now start from `subject_url` like `https://x.com/tuolaji2024`
- optional subject metadata can come from a small local registry template
- the workflow can also accept `x_index_request` / `x_index_request_path` and
  run `x-index` first before style learning
- batch mode can compare multiple handles from the same subject registry

## References

- `financial-analysis/commands/x-index.md`
- `docs/plans/2026-04-10-001-feat-x-stock-picker-style-learning-plan.md`
- `docs/runtime/x-stock-picker-style-learning-playbook.md`
- `docs/runtime/x-stock-picker-style-overlay-boundary.md`
