---
description: Build a local application-assist package without auto-submitting anything
argument-hint: "[request-json]"
---

# Job Apply Assist Command

Use this command when you want:

- common form answers
- a short candidate pitch
- why-this-role bullets
- constraints-based suggestions
- a final manual submit checklist

Native skill:

- `career-ops-local/skills/job-apply-assist/SKILL.md`

Local helper:

- `career-ops-local\skills\career-ops-bridge\scripts\run_career_ops_local.cmd "<request.json>" --output <result.json> --markdown-output <report.md>`

Template:

- `career-ops-local/skills/career-ops-bridge/examples/job-apply-assist-request.template.json`

Hard rule:

- this command never submits an application

