---
description: Scan supported China job portals and score the normalized jobs through career-ops-local role-pack matching
argument-hint: "[request-json]"
---

# Scan China Shortlist Command

Use this command when you want:

1. China portal discovery
2. normalization into `job_card`
3. immediate role-pack fit scoring
4. one shortlist sorted by fit score

Native skill:

- `china-portal-adapter/skills/china-portal-match-bridge/SKILL.md`

Expected behavior:

- scan-only on the portal side
- scoring on the local `career-ops-local` side
- emits a `tailor_queue.json` plus per-job tailor request files
- no auto-submit

Templates:

- `china-portal-adapter/skills/china-portal-match-bridge/examples/scan-cn-shortlist-request.template.json`

Fast Boss wrapper:

- `cmd /c china-portal-adapter\skills\china-portal-match-bridge\scripts\run_boss_shortlist_from_config.cmd`

Default config:

- `D:\career-ops-local\config\china_portal_adapter.local.json`

Default outputs:

- `D:\career-ops-local\outputs\china-portal-adapter\boss-shortlist\...`
