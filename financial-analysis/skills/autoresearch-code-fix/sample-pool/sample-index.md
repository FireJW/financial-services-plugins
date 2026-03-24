# Sample Index

| Sample ID | Title | Module | Repro Ready | Validation Ready | Rollback Ready | Notes |
|---|---|---|---|---|---|---|
| bug-001 | API input validation accepts malformed payload | request validation | Yes | Yes | Yes | Good starter for narrow server-side bugfix loops |
| bug-002 | Report export drops a required section when one field is empty | report generation | Yes | Yes | Yes | Good starter for output-integrity and regression checks |
| bug-003 | Search results stay stale after filter reset | UI state management | Yes | Yes | Yes | Good starter for reproduce-verify-manual-check discipline |
| bug-004 | Bulk upload accepts duplicate external IDs in the same batch | import validation | Yes | Yes | Yes | Good starter for batch-validation and narrow server-side fixes |
| bug-005 | Submit button stays disabled after fixing a form validation error | form state | Yes | Yes | Yes | Good starter for UI validation-state and immediate feedback bugs |
| bug-006 | Notification retry marks delivery successful after provider timeout | retry status handling | Yes | Yes | Yes | Good starter for async error-path and status-transition verification |
| bug-007 | CSV import silently duplicates rows on retry | data import | Yes | Yes | Yes | Good starter for idempotency and side-effect checks |
| bug-008 | Notification badge does not clear after inbox is read | client state sync | Yes | Yes | Yes | Good starter for UI state and manual verification discipline |
| bug-009 | Scheduled job skips records created near midnight boundary | time window processing | Yes | Yes | Yes | Good starter for boundary-condition fixes with narrow scope |
| bug-010 | Access-control check allows read on archived records to wrong role | authorization | Yes | Yes | Yes | Good starter for security-sensitive but still bounded fixes |
