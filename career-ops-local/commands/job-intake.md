---
description: Normalize a job posting into a bounded local job_card
argument-hint: "[request-json]"
---

# Job Intake Command

Use this command when you want to turn:

- a pasted JD
- a saved JD file
- a URL plus captured JD text

into one normalized `job_card`.

Native skill:

- `career-ops-local/skills/job-intake/SKILL.md`

Local helper:

- `career-ops-local\skills\career-ops-bridge\scripts\run_career_ops_local.cmd "<request.json>" --output <result.json> --markdown-output <report.md>`

Template:

- `career-ops-local/skills/career-ops-bridge/examples/job-intake-request.template.json`

Boundary:

- local normalization first
- URL-only requests may return `partial` if no JD body is available
- no browser login or auto-submission

