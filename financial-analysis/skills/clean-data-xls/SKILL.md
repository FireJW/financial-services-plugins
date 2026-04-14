---
name: clean-data-xls
description: Clean messy spreadsheet data by trimming whitespace, normalizing casing, converting numbers stored as text, standardizing dates, removing duplicates, and flagging mixed-type columns.
---

# Clean Data

Clean messy data in the active sheet or a specified range.

## Environment

- If running inside Excel, use Office JS directly.
- If operating on a standalone `.xlsx` file, use Python and openpyxl.

## Step 1: Scope

- If the user specifies a range, use it.
- Otherwise use the active sheet or full used range.
- Profile each column before changing anything.

For each column, identify:
- dominant type: text, number, date, mixed
- outlier count
- blank count
- likely normalization steps

## Step 2: Detect Issues

| Issue | What to look for |
|---|---|
| Whitespace | leading, trailing, or repeated spaces |
| Casing drift | `usa`, `USA`, `Usa` in the same categorical field |
| Numbers as text | `$`, `%`, commas, or spaces blocking numeric conversion |
| Date drift | mixed formats in the same column |
| Duplicates | exact or near duplicates |
| Blanks | empty cells in mostly populated columns |
| Mixed types | mostly numeric columns with stray text values |
| Encoding issues | mojibake or non-printing characters |
| Formula errors | `#REF!`, `#N/A`, `#VALUE!`, `#DIV/0!` |

## Step 3: Propose Fixes

Before changing data, show a summary table:

| Column | Issue | Count | Proposed Fix |
|---|---|---|---|

## Step 4: Apply Carefully

Default to non-destructive cleanup:
- prefer helper columns for formula-based cleanup
- preserve original columns unless the user explicitly asks for in-place replacement

Examples:
- `=TRIM(A2)`
- `=UPPER(C2)`
- `=VALUE(SUBSTITUTE(B2,"$",""))`
- `=DATEVALUE(D2)`

For destructive actions, ask first:
- removing duplicates
- overwriting source values
- filling blanks
- deleting rows

Apply changes in small groups and show a before/after sample after each category.

## Step 5: Report

Summarize:
- what was changed
- what was only flagged
- what still needs user confirmation

Call out any columns that remain ambiguous after profiling.
