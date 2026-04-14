---
name: audit-xls
description: Audit a spreadsheet for formula accuracy, logic errors, and model-integrity issues. Use for formula QA, model debugging, balance sheet tie-outs, cash flow mismatches, or pre-delivery spreadsheet review.
---

# Audit Spreadsheet

Audit formulas and data for mistakes. Scope determines depth:
- `selection` for a specific range
- `sheet` for the active sheet
- `model` for the full workbook, including model-integrity checks

## Environment

- If running inside Excel, use Office JS directly.
- If operating on a standalone `.xlsx` file, use Python and openpyxl.

## Step 1: Confirm Scope

If the user already gave a scope, use it. Otherwise ask:
- `selection`
- `sheet`
- `model`

Default to `model` for DCF, LBO, merger, 3-statement, or any integrated financial model.

## Step 2: Formula-Level Checks

Run these checks for every scope:

| Check | What to look for |
|---|---|
| Formula errors | `#REF!`, `#VALUE!`, `#N/A`, `#DIV/0!`, `#NAME?` |
| Hardcodes inside formulas | values like `=A1*1.05` that should reference input cells |
| Inconsistent formulas | a row or column where one formula breaks the pattern |
| Off-by-one ranges | missing the first or last row in a sum or average |
| Pasted-over formulas | hardcoded numbers where a formula should exist |
| Broken cross-sheet links | moved or deleted references |
| Unit mismatches | thousands mixed with millions, percents stored as whole numbers |
| Hidden overrides | hidden rows, columns, or tabs with stale logic |

## Step 3: Model-Integrity Checks

If scope is `model`, identify the model type and run the relevant integrity checks.

### Structural Review

Check:
- input vs formula separation
- color convention consistency
- tab flow and dependency order
- date header consistency
- unit consistency across tabs

### Balance Sheet

Verify:
- Assets = Liabilities + Equity for every period
- retained earnings roll forward correctly
- goodwill and intangibles follow acquisition assumptions where applicable

If the balance sheet does not balance, quantify the gap by period and trace where it breaks before doing anything else.

### Cash Flow

Verify:
- ending cash ties to the balance sheet
- CFO + CFI + CFF = change in cash
- D&A matches across statements
- CapEx matches PP&E logic
- working capital signs match balance-sheet movements

### Income Statement

Verify:
- revenue ties to the supporting build
- tax logic is coherent
- share count ties to dilution schedules

### Circular References

If a circular reference exists:
- verify whether it is intentional
- if intentional, confirm iteration is enabled and stable
- if accidental, trace the loop and explain how to break it

### Reasonableness

Flag:
- unrealistic growth or margins
- terminal value dominance in DCF
- hockey-stick projections
- leverage or liquidity outputs that do not make economic sense

## Step 4: Model-Type-Specific Checks

### DCF

- discount timing
- terminal value discounting
- WACC inputs
- unlevered vs levered FCF
- tax shield double counting

### LBO

- cash sweep and debt paydown logic
- PIK accrual
- management rollover treatment
- exit multiple period selection
- fees and uses at close

### Merger

- accretion / dilution share count
- synergy phasing
- purchase price allocation balance
- foregone interest on cash
- transaction fees in sources and uses

### 3-Statement

- working capital sign convention
- depreciation vs PP&E schedule
- debt maturity vs principal repayment
- dividends vs retained earnings logic

## Step 5: Report

Output a findings table:

| # | Sheet | Cell/Range | Severity | Category | Issue | Suggested Fix |
|---|---|---|---|---|---|---|

Severity:
- `Critical` for wrong outputs or broken statements
- `Warning` for risky or brittle logic
- `Info` for style or best-practice issues

For `model` scope, lead with a one-line summary:

`Model type: [type] - Overall: [Clean / Minor Issues / Major Issues] - [N] critical, [N] warnings, [N] info`

Do not change anything unless the user asks. Report first, then fix on request.
