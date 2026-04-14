---
name: 3-statement-model
description: Complete and populate a 3-statement financial model template with formula-driven linkages across the income statement, balance sheet, and cash flow statement.
---

# 3-Statement Model

Use the same core modeling workflow as `3-statements`, but apply the principles below before populating anything.

## Critical Principles

- Use formulas for every projected cell, roll-forward, subtotal, and linkage.
- Only historical actuals and explicit assumption-driver cells should contain hardcoded values.
- If running inside Excel, write formulas with Office JS.
- If generating a standalone workbook, write formulas with openpyxl and preserve the workbook's calculation logic.
- Validate the model statement by statement instead of filling the entire workbook in one pass.

## Required Validation Order

1. Map the workbook structure and identify input vs formula cells.
2. Populate and verify historical periods.
3. Build the income statement and verify subtotal logic.
4. Build the balance sheet and prove that Assets = Liabilities + Equity in every period.
5. Build the cash flow statement and prove that ending cash ties back to the balance sheet.
6. Only then finish the supporting schedules and scenario logic.

## Formatting Guidance

Default to the workbook's existing formatting. If you must introduce new formatting, keep it restrained:
- dark blue for section headers
- light blue for column headers
- grey or white for input areas
- black formulas
- green cross-sheet links only if that is already the workbook convention

## Quality Gates

Before finishing, verify:
- balance sheet balances in every period
- cash ties out in every period
- retained earnings roll forward correctly
- depreciation ties to PP&E
- debt balances tie to the debt schedule
- working capital signs are consistent

If the template depends on public filings, use `../3-statements/references/sec-filings.md`.

If the user asks you to fully populate the workbook, follow the detailed modeling workflow from the existing `3-statements` skill after applying the principles above.
