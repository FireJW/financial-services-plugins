---
description: Clean spreadsheet data by normalizing text, numbers, dates, and duplicates
argument-hint: "[path to .xlsx file] [optional range]"
---

Load the `clean-data-xls` skill and clean the specified workbook or range.

Prefer non-destructive cleanup by default:
- profile the data first
- show the proposed fixes
- use helper columns instead of overwriting originals unless the user explicitly asks for in-place edits

If a file path is provided, use it. Otherwise ask the user for the workbook to clean.
