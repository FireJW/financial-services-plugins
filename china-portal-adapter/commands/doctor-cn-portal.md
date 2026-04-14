---
description: Diagnose China portal local config, browser/profile readiness, and live-scan next steps
argument-hint: "[request-json]"
---

# Doctor China Portal Command

Use this command before real scanning when you want one bounded diagnosis of:

1. local browser executable detection
2. browser profile-root/session detection
3. platform readiness
4. missing live-scan config
5. next safe command to run

Fast local wrapper:

- `cmd /c china-portal-adapter\skills\china-portal-adapter\scripts\run_china_portal_doctor_from_config.cmd`

Default config:

- `D:\career-ops-local\config\china_portal_adapter.local.json`

Default outputs:

- `D:\career-ops-local\outputs\china-portal-adapter\doctor\...`

Hard boundary:

- no page automation
- no apply
- diagnosis only
