---
description: Curate report/chart-heavy X authors into a reusable market intelligence snapshot
argument-hint: "[x-index-result-json]"
---

# X Market Intelligence Curator

Use this when the author is valuable mainly because they surface:

- sell-side report summaries
- desk / call takeaways
- industry chart threads
- macro / policy snapshots

This command is for information-source enhancement, not stock-picker learning.

Recommended input:

- an existing `x-index` result built from allowlisted authors such as:
  - `Ariston_Macro`
  - `LinQingV`

Local helper:

- `financial-analysis\\skills\\autoresearch-info-index\\scripts\\run_x_market_intelligence_curator.cmd "<x-index-result.json>" [--output <result.json>] [--markdown-output <report.md>]`
