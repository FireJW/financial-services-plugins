---
name: deck-refresh
description: Update an existing presentation with new numbers while preserving formatting. Use for earnings refreshes, comp table rolls, market data updates, or any targeted numeric replacement across a deck.
---

# Deck Refresh

Update numbers across the deck. The deck is the source of truth for layout and formatting; you are only changing values.

## Environment Check

This workflow applies in both environments:
- Add-in: edit the live open deck
- Chat: edit the uploaded `.pptx` file

Use the smallest possible change. Do not restyle the deck.

## Phase 1: Get the Mapping

Determine how the new numbers are arriving:
- pasted old-to-new mapping
- uploaded spreadsheet
- loose new values that still need mapping

Also ask whether derived numbers should be recalculated or only direct values should be updated.

## Phase 2: Find Every Occurrence

Read every slide and build a full replacement plan.

For each number, find all variants:
- `$485M`, `$0.485B`, `$485,000,000`
- `$485M`, `$485.0M`, `485M`
- body text, table cells, chart labels, chart data, footnotes, speaker notes if requested

Build a list of:
- old value
- new value
- slide number
- exact text context
- whether the value looks derived

## Phase 3: Approval Gate

Before editing anything, show the full change plan in a grouped list.

Include a flagged section for derived numbers that may now be stale, such as:
- growth rates
- market-share percentages
- margin deltas

Do not edit until the user approves the plan.

## Phase 4: Execute

Make the smallest possible edit for each approved change:
- change the text run, not the whole shape
- change the table cell, not the whole table
- update chart source data, not just the label

Preserve:
- font
- color
- size
- alignment
- surrounding layout

## Phase 5: Report

After editing, report:
- how many values changed
- which slides changed
- which flagged items were left untouched

Run visual verification on each edited slide and flag overflow or alignment issues before finishing.
