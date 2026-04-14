---
description: Audit a spreadsheet for formula errors, balance issues, and model integrity problems
argument-hint: "[path to .xlsx file] [optional scope: selection|sheet|model]"
---

Load the `audit-xls` skill and review the specified spreadsheet.

Default to scope `model` when the user is auditing an integrated financial model.
If the user provides a narrower scope such as a range or a single sheet, keep the audit scoped there.

If a file path is provided, use it. Otherwise ask the user for the workbook to audit.
