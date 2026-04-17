---
description: Debug and audit a financial model for errors
argument-hint: "[path to .xlsx model file]"
---

Load the `audit-xls` skill with scope `model` and audit the specified financial model for broken formulas, balance sheet imbalances, hardcoded overrides, circular references, and logic errors.

If a file path is provided, use it. Otherwise ask the user for the model to review.
