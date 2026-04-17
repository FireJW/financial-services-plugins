---
description: Update the local application tracker without duplicating job rows
argument-hint: "[request-json]"
---

# Job Track Command

Use this command when a job moves through:

- `new`
- `shortlisted`
- `tailored`
- `applied`
- `replied`
- `interview`
- `rejected`
- `closed`

Native skill:

- `career-ops-local/skills/job-track/SKILL.md`

Local helper:

- `career-ops-local\skills\career-ops-bridge\scripts\run_career_ops_local.cmd "<request.json>" --output <result.json> --markdown-output <report.md>`

Template:

- `career-ops-local/skills/career-ops-bridge/examples/job-track-request.template.json`
