---
description: Scan supported China job portals and normalize results into local job_card output
argument-hint: "[request-json]"
---

# Scan China Jobs Command

Use this command when you want a bounded local scan of:

- Boss
- 猎聘
- 51job
- 智联

Native skill:

- `china-portal-adapter/skills/china-portal-adapter/SKILL.md`

Expected v1 behavior:

- `platform_probe` supports real local browser/session-root detection
- `scan_jobs` in fixture mode returns normalized jobs
- `scan_jobs` in non-fixture mode returns a `readiness_gate` instead of attempting live browser automation
- normalize into `job_card`
- preserve platform/session metadata
- no auto-submit

Useful explicit probe inputs:

- `browser_executable_paths`
- `browser_profile_paths`
- `config_path`

Templates:

- `china-portal-adapter/skills/china-portal-adapter/examples/scan-cn-jobs-request.template.json`
